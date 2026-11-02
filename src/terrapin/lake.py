"""The plugin's `data` role class: Terrapin's curves, inflation factors and
municipal prints into the lake, and the securities a deployment lists
resolved and handed to the `reference` role class for their terms.

**What it reads, and when** (`check`, at start and every hour, or at once
when the settings change):

- each region's par curve for today and the four business days before it
  (`government_curves`), a day Terrapin has not published
  yet answered empty and read again next time;
- each country's inflation factors for the last thirteen months
  (`inflation`);
- the securities the deployment lists (the `securities` setting, by ISIN
  or CUSIP): their terms (`securities_reference`, then `muni_reference` for
  those it does not hold), each resolved to the deployment's record and
  its issuer's LEI to the `ENT-` company record, the terms offered by the
  `reference` role (terms.py); and each municipal bond's prints over the
  last seven days (`msrb_prints`).

**What the lake wants** (`on_observations_wanted`): a curve for a date, a
country's index over a range, a municipal bond's prints over a range --
read from Terrapin and recorded against the want, a standing want kept
current by the hourly check until withdrawn. A subject Terrapin does not
cover is declined `not_covered`; a want of a kind a dataset does not hold
is declined too.

It mints nothing: a record the deployment does not hold is reported as a
miss (W3.2) once a day, and its rows are not recorded; a security is
resolved with what Terrapin states of it, its identifiers, description and
currency, so the deployment's instrument store may keep a local record of
it (W3.7), its CUSIP kept there and never sent (W3.25, ruling 976).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

import meridian
from meridian.operations import Rate
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles import data
from meridian.roles.data import rates

from . import curves, read, trades
from .client import NoKey, Terrapin, Unreachable, terrapin
from .curves import CURVES_KEY, INFLATION_KEY, REGIONS, Region
from .terms import Reference, Terms
from .terms import terms as terms_of

log = logging.getLogger("terrapin")

#: Its datasets' keys, as the catalogue declares them.
KEYS = (CURVES_KEY, INFLATION_KEY, trades.MSRB_PRINTS)
#: Why a curve's or an index's rates wait.
AWAITS = "its record awaits a person's acceptance at the Instruments page"
#: How far back the hourly check reads.
CURVE_DAYS = 5
INFLATION_MONTHS = 13
PRINT_DAYS = 7
#: How many days a want of prints with no range reaches back.
WANT_DAYS = 7


@dataclass
class Status:
    """What the pages show of the plugin's work (page.py)."""

    checked_at: str = ""
    last_error: str = ""
    #: Each curve's and index's record, by its symbol, or why there is none.
    records: dict[str, str] = field(default_factory=dict)
    #: Each listed security: its ISIN, the record it resolved to, its issuer.
    securities: dict[str, dict[str, str]] = field(default_factory=dict)
    #: What Terrapin stated that could not be recorded, each with its count.
    unread: dict[str, int] = field(default_factory=dict)
    #: Points not recorded by what they are, each with its count.
    not_recorded: dict[str, int] = field(default_factory=dict)
    #: What the lake refused at the last check, by what it was, and why.
    refused: dict[str, str] = field(default_factory=dict)

    def said(self, what: str, table: str = "unread") -> None:
        held = self.unread if table == "unread" else self.not_recorded
        held[what] = held.get(what, 0) + 1


def _day_ns(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp()) * 1_000_000_000


def _key(row: meridian.Trade) -> str:
    return row.meta.row_key if row.meta is not None else ""


def business_days(last: date, count: int) -> list[date]:
    """The `count` weekdays up to and including `last`, oldest first."""
    days: list[date] = []
    at = last
    while len(days) < count:
        if at.weekday() < 5:
            days.append(at)
        at -= timedelta(days=1)
    return sorted(days)


class Lake(data.Role):
    """The data role's class (see the module), bound to a recorder in its
    tests and registered by `meridian.run` beside the reference role's."""

    def __init__(
        self,
        source: Terrapin | None = None,
        reference: Reference | None = None,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        super().__init__()
        self.source: Terrapin = source or terrapin(False, "")
        self.reference = reference or Reference()
        self.now = now
        self.wants = data.Wants(self, KEYS, clock_ns=self.clock_ns)
        self.wants.latency = None
        self.feeds = {
            region.code: rates.Feed(self, curves.SOURCE, wants=self.wants,
                                   day_zone=region.day_zone, clock_ns=self.clock_ns)
            for region in REGIONS
        }  # fmt: skip
        self.feeds[INFLATION_KEY] = rates.Feed(
            self, curves.SOURCE, wants=self.wants, clock_ns=self.clock_ns
        )
        self.securities: tuple[str, ...] = ()
        self.has_key = False
        self.status = Status()
        #: Each record's ID by what names it: a curve's or an index's symbol,
        #: a security's ISIN.
        self.records: dict[str, str] = {}
        #: Each security held, by its record: its ISIN, and whether a muni.
        self.held: dict[str, tuple[str, bool]] = {}
        #: Misses reported, by what was missed, the day each was reported.
        self.missed: dict[str, date] = {}
        #: The day the inflation indexes and the terms were last read, and
        #: the securities they were read for: read again daily, or at once
        #: when the list changes.
        self.daily: tuple[date, tuple[str, ...]] | None = None
        #: Each print recorded unasked, by its row key, and whether it was
        #: cancelled when sent: the hourly check sends a print once, and again
        #: only when Terrapin marks it cancelled, so a print read again is
        #: never judged a duplicate at the edge.
        self.printed: dict[str, bool] = {}

    def clock_ns(self) -> int:
        return int(self.now().timestamp() * 1e9)

    def use(self, source: Terrapin, securities: tuple[str, ...], has_key: bool) -> None:
        self.source = source
        self.securities = securities
        self.has_key = has_key

    def today(self) -> date:
        return self.source.today(self.now())

    # ── Asking Terrapin ──────────────────────────────────────────────────

    async def ask(self, endpoint: str, body: dict[str, Any]) -> list[dict[str, Any]]:
        """Terrapin's items for one request; empty, the failure said, where
        it did not answer."""
        try:
            got = await self.source.post(endpoint, body)
        except NoKey:
            return []
        except Unreachable as failed:
            self.status.last_error = str(failed)
            return []
        if not got.ok:
            self.status.last_error = got.error
            return []
        return read.items(got.body)

    def raw(self, key: str) -> ops.RawRecordRef:
        held: ops.RawRecordRef = self.plugin.raw_record(key[:256])
        return held

    # ── Records ──────────────────────────────────────────────────────────

    async def _missed(
        self, what: str, identifiers: list[ops.Identifier], reason: Any, asset_class: str
    ) -> None:
        today = self.today()
        if self.missed.get(what) == today:
            return
        self.missed[what] = today
        await self.report_missing_instrument(
            source=curves.SOURCE,
            asset_class=asset_class,
            identifiers=identifiers,
            as_of_ns=self.clock_ns(),
            reason=reason or ops.MISS_REASON_NOT_FOUND,
        )

    async def referential(
        self, symbol: str, description: str, currency: str, instrument_type: str
    ) -> str:
        """The deployment's record of one of Terrapin's own curves or indexes,
        named by its code under the source `terrapin`; empty, the miss
        reported once a day, where it holds none.

        A vendor's own curve is no record the platform curates, so the
        deployment keeps it local, its class and type offered as the plugin
        states them; a rate is recorded on it only once a person has accepted
        them at the Instruments page (the lake takes a rate only on a
        referential record). Until then it is read again at each check, said
        on the Datasets page, and no rate is sent for it."""
        held = self.records.get(symbol)
        if held:
            return held
        named = [ops.Identifier(scheme="symbol", value=symbol, source=curves.SOURCE)]
        found = await self.resolve_identifier(
            identifiers=named,
            as_of_ns=self.clock_ns(),
            stated_asset_class="referential",
            stated_instrument_type=instrument_type,
            stated_currency=currency,
            stated_description=description,
        )
        if found.found and found.instrument_id:
            record = str(found.instrument_id)
            if not await self.accepted(record):
                self.status.records[symbol] = record
                self.status.refused[symbol] = AWAITS
                return ""
            self.records[symbol] = record
            self.status.records[symbol] = record
            self.status.refused.pop(symbol, None)
            return record
        self.status.records[symbol] = ops.MissReason.Name(found.miss_reason or 1)
        await self._missed(symbol, named, found.miss_reason, "referential")
        return ""

    async def accepted(self, record: str) -> bool:
        """Whether a person has accepted a local record as a referential one,
        a rate curve or an index; a record the store does not answer for is
        taken as it is."""
        read = await self.resolve_instrument(instrument_id=record, as_of_ns=self.clock_ns())
        if not read.found:
            return True
        return bool(
            read.instrument.asset_class == ops.ASSET_CLASS_REFERENTIAL
            and read.instrument.instrument_type
            in (ops.INSTRUMENT_TYPE_RATE_CURVE, ops.INSTRUMENT_TYPE_INDEX)
        )

    async def security(self, held: Terms) -> str:
        """The deployment's record of a security, resolved with what
        Terrapin states of it; empty, the miss reported once a day."""
        known = self.records.get(held.isin)
        if known:
            return known
        named = held.identifiers()
        found = await self.resolve_identifier(
            identifiers=named,
            as_of_ns=self.clock_ns(),
            stated_asset_class="debt",
            stated_instrument_type=held.instrument_type,
            stated_currency=held.currency,
            stated_description=held.description,
        )
        if found.found and found.instrument_id:
            self.records[held.isin] = str(found.instrument_id)
            self.held[str(found.instrument_id)] = (held.isin, held.muni)
            return str(found.instrument_id)
        await self._missed(held.isin, named, found.miss_reason, "debt")
        self.status.securities.setdefault(held.isin, {})["record"] = ops.MissReason.Name(
            found.miss_reason or 1
        )
        return ""

    async def issuer(self, lei: str) -> str:
        """The issuer's `ENT-` company record by its LEI (W3.32); empty where
        the deployment has none yet -- the platform asked, its staff's queue
        or unreachable -- asked again next time."""
        if not lei:
            return ""
        try:
            found = await self.resolve_company(
                identifiers=[ops.Identifier(scheme="lei", value=lei)], as_of_ns=self.clock_ns()
            )
        except meridian.MeridianError as refused:
            log.info("the issuer %s is not resolved yet: %s", lei, refused)
            return ""
        return str(found.company_id)

    # ── Curves and inflation ─────────────────────────────────────────────

    async def curve_rows(self, region: Region, day: date) -> list[Rate]:
        """One region's par curve for a date, as rates: a point whose years
        to maturity is no tenor is said, never recorded."""
        subject = await self.referential(region.symbol, region.description, region.currency,
                                         "rate_curve")  # fmt: skip
        if not subject:
            return []
        body = {"date": day.isoformat(), "region": region.code, "type": "par"}
        points: dict[str, Decimal] = {}
        for item in await self.ask("government_yield_curve", body):
            years = read.number(item.get("years_to_maturity"))
            value = read.number(item.get("rate"))
            label = curves.tenor_of(years) if years is not None else None
            if label is None or value is None:
                self.status.said(f"{region.code} par curve: a point at {years} years")
                continue
            points[label] = value
        feed = self.feeds[region.code]
        return feed.curve(
            subject, CURVES_KEY, "par_yield", cast(Any, points),
            business_date=day, convention=region.convention,
            raw_key=f"government_yield_curve/{region.code}/par/{day.isoformat()}",
        )  # fmt: skip

    async def inflation_rows(self, country: str, start: date, end: date) -> list[Rate]:
        """One country's inflation index over a range, as index levels."""
        body = {"country": country, "start_date": start.isoformat(), "end_date": end.isoformat()}
        found = await self.ask("inflation_factors", body)
        if not found:
            return []
        publisher = read.text(found[0].get("type"))
        subject = await self.referential(
            curves.inflation_symbol(country),
            curves.inflation_description(country, publisher),
            curves.INFLATION_COUNTRIES[country],
            "index",
        )
        if not subject:
            return []
        feed = self.feeds[INFLATION_KEY]
        rows = []
        for item in found:
            when, level = read.day(item.get("date")), read.number(item.get("factor"))
            if when is None or level is None:
                self.status.said(f"inflation: a {country} factor with no date or level")
                continue
            rows.append(
                feed.rate(
                    subject, INFLATION_KEY, "index_level", rates.index_level(level),
                    business_date=when, convention=curves.INDEX_DAILY,
                    series=curves.inflation_symbol(country),
                    raw_key=f"inflation_factors/{country}/{when.isoformat()}",
                )
            )  # fmt: skip
        return rows

    # ── Securities and prints ────────────────────────────────────────────

    async def reference_of(self, isins: list[str]) -> list[Terms]:
        """The listed securities' terms: Terrapin's corporate, government,
        agency and CD reference first, then its municipal reference for the
        ISINs that one does not hold."""
        found: list[Terms] = []
        for start in range(0, len(isins), 1000):
            asked = isins[start : start + 1000]
            items = await self.ask("securities_reference", {"isins": asked})
            found += [terms_of(item, muni=False) for item in items]
            seen = {t.isin for t in found}
            rest = [i for i in asked if i not in seen]
            if rest:
                munis = await self.ask("muni_reference", {"isins": rest})
                found += [terms_of(item, muni=True) for item in munis]
        return found

    async def terms(self) -> None:
        """Each listed security resolved, its issuer resolved and its terms
        offered by the reference role."""
        isins = [i for i in self.securities if read.is_isin(i)]
        isins += [
            read.isin_of(c) for c in self.securities if not read.is_isin(c) and read.isin_of(c)
        ]
        if not isins:
            return
        for held in await self.reference_of(sorted(set(isins))):
            for said in held.unmapped:
                self.status.said(f"terms: {said}")
            row = self.status.securities.setdefault(held.isin, {})
            row["description"] = held.description
            subject = await self.security(held)
            if not subject:
                continue
            row["record"] = subject
            company = await self.issuer(held.lei)
            row["issuer"] = company or ("LEI not resolved yet" if held.lei else "no LEI stated")
            endpoint = "muni_reference" if held.muni else "securities_reference"
            offered = await self.reference.offer(
                subject, held, company, self.raw(f"{endpoint}/{held.isin}")
            )
            row["offered"] = str(offered.offered)
            if offered.refused:
                row["refused"] = offered.refused

    async def print_rows(
        self, isin: str, subject: str, start: date, end: date
    ) -> list[meridian.Trade]:
        """A municipal bond's prints over a range, as trades."""
        body = {"isin": isin, "start_date": start.isoformat(), "end_date": end.isoformat()}
        rows: list[meridian.Trade] = []
        dataset = self.wants.dataset(trades.MSRB_PRINTS)
        for item in await self.ask("muni_pricing_history", body):
            trade_id = read.text(item.get("id"))
            made = trades.convert(item, subject, dataset,
                                  self.raw(f"muni_pricing_history/{isin}/{trade_id}"))  # fmt: skip
            if isinstance(made, trades.Unread):
                self.status.said(f"msrb_prints: {made.why}")
                continue
            rows.append(made)
        return rows

    # ── The check ────────────────────────────────────────────────────────

    async def check(self) -> None:
        """Read what is kept current (see the module), and record it."""
        if not self.has_key and self.source.mode != "synthetic":
            return
        today = self.today()
        for region in REGIONS:
            for day in business_days(today, CURVE_DAYS):
                rows = await self.curve_rows(region, day)
                await self.kept(
                    f"the {region.name} par curve", self.feeds[region.code].record(CURVES_KEY, rows)
                )
        if self.daily != (today, self.securities):
            start = today.replace(day=1) - timedelta(days=31 * (INFLATION_MONTHS - 1))
            for country in curves.INFLATION_COUNTRIES:
                rows = await self.inflation_rows(country, start.replace(day=1), today)
                await self.kept(f"the {country} inflation index",
                                self.feeds[INFLATION_KEY].record(INFLATION_KEY, rows))  # fmt: skip
            await self.terms()
            self.daily = (today, self.securities)
        for subject, (isin, muni) in sorted(self.held.items()):
            if muni:
                prints = await self.print_rows(
                    isin, subject, today - timedelta(days=PRINT_DAYS), today
                )
                fresh = [p for p in prints if self.printed.get(_key(p)) != p.cancelled]
                recording = self.wants.record("trades", fresh, trades.MSRB_PRINTS)
                if await self.kept(f"{isin}'s prints", recording):
                    self.printed.update({_key(p): p.cancelled for p in fresh})
        await self.kept_current(today)
        self.status.checked_at = self.now().isoformat(timespec="seconds")
        counts = self.wants.counts
        log.info(
            "checked: %d recorded, %d restated, %d unchanged in all; %d refused this time",
            counts.recorded, counts.restated, counts.unchanged, len(self.status.refused),
        )  # fmt: skip

    async def kept(self, what: str, recording: Awaitable[int]) -> bool:
        """A recording made, or its refusal said and the check gone on: a
        curve's or an index's record the deployment keeps local is used for
        rates only once a person accepts its class and type at the
        Instruments page, and until then the lake refuses its rows."""
        try:
            await recording
        except meridian.MeridianError as refused:
            said = str(refused)
            if "is no referential record" in said:
                said = AWAITS
            self.status.refused[what] = said[:300]
            log.info("%s not recorded: %s", what, said)
            return False
        self.status.refused.pop(what, None)
        return True

    async def kept_current(self, today: date) -> None:
        """Each standing want of prints answered again with what is current;
        the curves and indexes are read above whatever is wanted."""
        for want in list(self.wants.standing.values()):
            key = self.wants.key_of(want.dataset)
            if key != trades.MSRB_PRINTS:
                continue
            event = ops.ObservationsWantedEvent(
                want_id=want.want_id, dataset=want.dataset, data_type=want.data_type,
                subjects=[ops.SubjectRef(entity_id=s) for s in want.subjects],
                business_date=today.isoformat(), standing=True,
            )  # fmt: skip
            await self.answer(event, key, list(want.subjects), want.kinds)

    # ── Wants ────────────────────────────────────────────────────────────

    async def on_observations_wanted(
        self, heard: meridian.Heard[ops.ObservationsWantedEvent]
    ) -> None:
        await self.wants.hear(heard, self.answer)

    async def on_want_withdrawn(self, heard: meridian.Heard[ops.WantWithdrawnEvent]) -> None:
        self.wants.withdraw(heard.message.want_id)

    def _range(self, want: ops.ObservationsWantedEvent, days: int) -> tuple[date, date]:
        if want.business_date:
            day = date.fromisoformat(want.business_date)
            return day, day
        if want.valid_from_ns:
            start = datetime.fromtimestamp(want.valid_from_ns / 1e9, tz=UTC).date()
            end_ns = want.valid_until_ns or self.clock_ns()
            return start, datetime.fromtimestamp(end_ns / 1e9, tz=UTC).date()
        today = self.today()
        return today - timedelta(days=days), today

    async def isin_for(self, subject: str) -> tuple[str, bool] | None:
        """The ISIN of a held security a want names, and whether it is a
        municipal bond; one another source resolved is read from its record
        (its ISIN, or its CUSIP's) and asked of Terrapin's municipal
        reference."""
        if subject in self.held:
            return self.held[subject]
        found = await self.resolve_instrument(instrument_id=subject, as_of_ns=self.clock_ns())
        if not found.found:
            return None
        named = {i.scheme: i.value for i in found.instrument.identifiers}
        isin = named.get("isin", "") or read.isin_of(named.get("cusip", ""))
        if not isin:
            return None
        if await self.ask("muni_reference", {"isins": [isin]}):
            self.held[subject] = (isin, True)
            return self.held[subject]
        return None

    async def answer(
        self,
        want: ops.ObservationsWantedEvent,
        key: str,
        subjects: list[str],
        kinds: tuple[int, ...],
    ) -> dict[str, str]:
        """One want answered from Terrapin (see the module)."""
        declined: dict[str, str] = {}
        if key == CURVES_KEY:
            start, end = self._range(want, 0)
            by_record: dict[str, Region] = {}
            for region in REGIONS:
                held = await self.referential(region.symbol, region.description,
                                              region.currency, "rate_curve")  # fmt: skip
                by_record[held] = region
            rows: list[Rate] = []
            for s in subjects:
                found = by_record.get(s)
                if found is None:
                    declined[s] = "not_covered"
                    continue
                for day in business_days(end, max(1, (end - start).days * 5 // 7 + 1)):
                    if day >= start:
                        rows += await self.curve_rows(found, day)
            await self.feeds[REGIONS[0].code].record(CURVES_KEY, rows, want.want_id)
        elif key == INFLATION_KEY:
            start, end = self._range(want, 400)
            if start == end:
                start = start.replace(day=1)
            countries = {
                self.records.get(curves.inflation_symbol(c), ""): c
                for c in curves.INFLATION_COUNTRIES
            }
            rows = []
            for s in subjects:
                country = countries.get(s) if s else None
                if country is None:
                    declined[s] = "not_covered"
                    continue
                rows += await self.inflation_rows(country, start, end)
            await self.feeds[INFLATION_KEY].record(INFLATION_KEY, rows, want.want_id)
        elif key == trades.MSRB_PRINTS:
            start, end = self._range(want, WANT_DAYS)
            prints: list[meridian.Trade] = []
            for s in subjects:
                isin = await self.isin_for(s)
                if isin is None or not isin[1]:
                    declined[s] = "not_covered"
                    continue
                prints += await self.print_rows(isin[0], s, start, end)
            await self.wants.record("trades", prints, key, want.want_id)
        else:
            declined = {s: "not_covered" for s in subjects}
        if want.standing:
            self.wants.stand(want, [s for s in subjects if s not in declined], kinds)
        return declined
