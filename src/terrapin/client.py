"""Terrapin's API, and its stand-in.

Terrapin (terrapinfinance.com, its public documentation at
docs.terrapinfinance.com) answers every request as a `POST` of a JSON body
to `https://terrapinfinance.com/api/v1/<endpoint>`, with the key as a bearer
token. The plugin asks these endpoints, and nothing else:

- `securities_reference` and `muni_reference` -- a security's terms, by
  ISIN, up to a thousand at a time;
- `muni_pricing_history` -- a municipal bond's prints, MSRB's, over a range
  of days;
- `government_yield_curve` -- a region's curve of one type for a date;
- `inflation_factors` -- a country's inflation index over a range of days;
- `securities_cashflows` -- a security's cash flows, read by the tests as
  the engine's accrual oracle (no lake kind holds a cash flow).

**The key.** Terrapin's API key, the plugin's one secret setting, is sent
as `Authorization: Bearer <key>` and nowhere else: an answer, a log line, an
error and a page never hold it. Without a key nothing is asked.

**Pacing is the plugin's** (ruling 1028). Terrapin counts requests over a
rolling 60 seconds, its limit the subscription tier's (Startup: 25 a
minute), and says the policy in its `ratelimit-policy` header; a 429 says
how long to wait in `retry-after`. The plugin asks one request at a time,
keeps under the limit it last read (25 until it reads one), and waits out a
429's `retry-after` before asking again. Terrapin's monthly quota of
distinct ISINs is the subscription's: the plugin asks only for the
securities a deployment lists or a reader wants.

`SyntheticTerrapin` answers from the answers committed under sample/,
made in the shape of Terrapin's public documentation's examples, so the
plugin's tests and sample data run offline, the same on any day.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import urllib.error
import urllib.request
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from importlib import resources
from typing import Any, Protocol

BASE = "https://terrapinfinance.com/api/v1/"
USER_AGENT = "meridian-terrapin (+https://github.com/open-meridian/plugin-terrapin)"
TIMEOUT = 60.0
#: The most of an answer read: a thousand securities' terms is well under it.
MOST_BYTES = 32 * 1024 * 1024
#: Terrapin's rolling window, and the limit kept until a policy is read: its
#: Startup tier's 25 requests a minute.
WINDOW_SECONDS = 60.0
DEFAULT_LIMIT = 25
#: The most ISINs one request names: Terrapin answers up to a thousand items.
MOST_ISINS = 1000

ENDPOINTS = (
    "securities_reference",
    "muni_reference",
    "muni_pricing_history",
    "government_yield_curve",
    "inflation_factors",
    "securities_cashflows",
)

_POLICY = re.compile(r"(\d+)\s*;\s*w=(\d+)")


class Unreachable(Exception):  # noqa: N818 - what Terrapin was
    """Terrapin could not be asked: no answer, or not in time."""


class NoKey(Exception):  # noqa: N818 - what the plugin lacks
    """No API key is set, so Terrapin is not asked."""


@dataclass(frozen=True)
class Fetched:
    """One answer of Terrapin's, as received: the endpoint, the body asked,
    the status and the answer's text. It never holds the key."""

    endpoint: str
    asked: dict[str, Any]
    status: int
    body: str
    fetched_at: datetime

    @property
    def ok(self) -> bool:
        return self.status == 200

    @property
    def error(self) -> str:
        """Terrapin's own words for a refusal, or the status."""
        try:
            said = json.loads(self.body)
        except ValueError:
            said = None
        if isinstance(said, dict):
            for name in ("detail", "message", "error"):
                if said.get(name):
                    return f"{self.endpoint} answered {self.status}: {str(said[name])[:200]}"
        return f"{self.endpoint} answered {self.status}"


class Terrapin(Protocol):
    mode: str
    calls: int
    last_call_at: str
    rate_limited: int
    limit: int
    failed: str

    def today(self, now: datetime) -> date: ...

    async def post(self, endpoint: str, body: dict[str, Any]) -> Fetched: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


def redacted(text: str, key: str) -> str:
    """`text` with the key, wherever it appears, said as `***`."""
    return text.replace(key, "***") if key else text


def policy_limit(header: str) -> int | None:
    """The request limit a `ratelimit-policy` header states for a 60-second
    window (`25;w=60`), or None."""
    for count, window in _POLICY.findall(header or ""):
        if int(window) == int(WINDOW_SECONDS) and int(count) > 0:
            return int(count)
    return None


@dataclass
class LiveTerrapin:
    """Terrapin itself, asked with `key` (see the module)."""

    key: str = field(repr=False)
    now: Callable[[], datetime] = utc_now
    mode: str = "live"
    calls: int = 0
    rate_limited: int = 0
    limit: int = DEFAULT_LIMIT
    failed: str = ""
    last_call_at: str = ""
    _sent: deque[float] = field(default_factory=deque)
    _not_before: float = 0.0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def today(self, now: datetime) -> date:
        return now.date()

    async def _paced(self) -> None:
        """Wait until a request keeps under the limit over the rolling
        window, and past any `retry-after`."""
        while True:
            at = time.monotonic()
            while self._sent and at - self._sent[0] >= WINDOW_SECONDS:
                self._sent.popleft()
            wait = max(
                self._not_before - at,
                (self._sent[0] + WINDOW_SECONDS - at) if len(self._sent) >= self.limit else 0.0,
            )
            if wait <= 0:
                self._sent.append(at)
                return
            await asyncio.sleep(wait)

    async def post(self, endpoint: str, body: dict[str, Any]) -> Fetched:
        if not self.key:
            raise NoKey("no Terrapin API key is set")
        async with self._lock:
            await self._paced()
            self.calls += 1
            self.last_call_at = self.now().isoformat(timespec="seconds")
            try:
                got, headers = await asyncio.to_thread(self._post, endpoint, body)
            except Unreachable as failed:
                self.failed = str(failed)
                raise
        limit = policy_limit(headers.get("ratelimit-policy", ""))
        if limit is not None:
            self.limit = limit
        if got.status == 429:
            self.rate_limited += 1
            try:
                after = float(headers.get("retry-after", "") or WINDOW_SECONDS)
            except ValueError:
                after = WINDOW_SECONDS
            self._not_before = time.monotonic() + after
        self.failed = "" if got.ok else got.error
        return got

    def _post(self, endpoint: str, body: dict[str, Any]) -> tuple[Fetched, dict[str, str]]:
        request = urllib.request.Request(
            BASE + endpoint,
            data=json.dumps(body).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as answer:  # noqa: S310 - Terrapin's https address
                raw = answer.read(MOST_BYTES + 1)
                status = answer.status
                headers = {k.lower(): v for k, v in answer.headers.items()}
        except urllib.error.HTTPError as refused:
            raw = refused.read(MOST_BYTES + 1) if refused.fp else b""
            status = refused.code
            headers = {k.lower(): v for k, v in (refused.headers or {}).items()}
        except (urllib.error.URLError, TimeoutError, OSError) as failed:
            reason = getattr(failed, "reason", failed)
            raise Unreachable(f"{BASE}{endpoint}: {type(reason).__name__}") from failed
        if len(raw) > MOST_BYTES:
            raise Unreachable(f"{BASE}{endpoint}: answered more than {MOST_BYTES} bytes")
        text = redacted(raw.decode("utf-8", errors="replace"), self.key)
        return Fetched(endpoint, body, status, text, self.now()), headers


def _canonical(body: dict[str, Any]) -> str:
    return json.dumps(body, sort_keys=True)


class SyntheticTerrapin:
    """The answers committed under sample/ (sample/answers.json): each
    request answered as recorded there; a security's request answered with
    the recorded items among the ISINs asked, a range with the rows in it,
    and anything else with Terrapin's empty answer."""

    mode = "synthetic"
    limit = DEFAULT_LIMIT

    def __init__(self, now: Callable[[], datetime] = utc_now) -> None:
        self._now = now
        held = resources.files(__package__).joinpath("sample")
        recorded = json.loads(held.joinpath("answers.json").read_text(encoding="utf-8"))
        self.today_is = date.fromisoformat(recorded["today"])
        self.reference: dict[str, dict[str, Any]] = recorded["securities_reference"]
        self.muni_reference: dict[str, dict[str, Any]] = recorded["muni_reference"]
        self.prints: dict[str, list[dict[str, Any]]] = recorded["muni_pricing_history"]
        self.curves: dict[str, list[dict[str, Any]]] = recorded["government_yield_curve"]
        self.inflation: dict[str, list[dict[str, Any]]] = recorded["inflation_factors"]
        self.cashflows: dict[str, dict[str, Any]] = recorded["securities_cashflows"]
        self.asked: list[tuple[str, str]] = []
        self.calls = 0
        self.rate_limited = 0
        self.failed = ""
        self.last_call_at = ""

    def today(self, now: datetime) -> date:
        """The recording's last day, whatever the clock says."""
        return self.today_is

    async def post(self, endpoint: str, body: dict[str, Any]) -> Fetched:
        self.calls += 1
        self.last_call_at = self._now().isoformat(timespec="seconds")
        self.asked.append((endpoint, _canonical(body)))
        at = self._now()
        data: list[Any]
        if endpoint in ("securities_reference", "muni_reference", "securities_cashflows"):
            held = {
                "securities_reference": self.reference,
                "muni_reference": self.muni_reference,
                "securities_cashflows": self.cashflows,
            }[endpoint]
            data = [held[i] for i in body.get("isins", []) if i in held]
        elif endpoint == "muni_pricing_history":
            start, end = body.get("start_date", "0000"), body.get("end_date", "9999")
            data = [
                p
                for p in self.prints.get(str(body.get("isin", "")), [])
                if start <= str(p["trade_datetime"])[:10] <= end
            ]
        elif endpoint == "government_yield_curve":
            key = f"{body.get('region')}:{body.get('type')}:{body.get('date')}"
            data = list(self.curves.get(key, []))
        elif endpoint == "inflation_factors":
            start, end = body.get("start_date", "0000"), body.get("end_date", "9999")
            data = [
                f
                for f in self.inflation.get(str(body.get("country", "")), [])
                if start <= str(f["date"]) <= end
            ]
        else:
            return Fetched(endpoint, body, 404, '{"detail": "Not Found"}', at)
        text = json.dumps({"data": data, "total": len(data)})
        return Fetched(endpoint, body, 200, text, at)


def terrapin(synthetic: bool, key: str, now: Callable[[], datetime] = utc_now) -> Terrapin:
    return SyntheticTerrapin(now) if synthetic else LiveTerrapin(key, now)
