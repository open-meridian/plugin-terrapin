"""Reading Terrapin's answers, once, at the edge.

Terrapin writes its numbers as JSON numbers. Each is read from the answer's
own text as a `Decimal` (`json.loads(..., parse_float=Decimal)`), never
through a binary float, so a coupon of 4.875 is 4.875 exactly as Terrapin
wrote it; what Terrapin's own systems held before writing it is Terrapin's.

A security is named by its ISIN. A US or Canadian ISIN holds the CUSIP
(ISO 6166: the country code, the nine-character national number, a check
digit), so the CUSIP a custodian states is read from the ISIN, never
looked up; neither is ever mapped to a FIGI (ruling 976). Terrapin's FIGI,
where it states one, is kept beside them.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

#: The countries whose ISIN holds a CUSIP as its national number.
CUSIP_COUNTRIES = ("US", "CA")


def parse(text: str) -> dict[str, Any]:
    """Terrapin's JSON, every number a Decimal as Terrapin wrote it."""
    read = json.loads(text, parse_float=Decimal, parse_int=Decimal)
    return read if isinstance(read, dict) else {}


def items(text: str) -> list[dict[str, Any]]:
    """An answer's `data`, each item an object."""
    data = parse(text).get("data")
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def number(value: Any) -> Decimal | None:
    """A number as Terrapin wrote it, or None where it states none."""
    if isinstance(value, Decimal):
        return value
    return None


def text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def day(value: Any) -> date | None:
    """A date as Terrapin writes it (YYYY-MM-DD), or None."""
    try:
        return date.fromisoformat(str(value)[:10]) if isinstance(value, str) and value else None
    except ValueError:
        return None


def utc_moment(value: Any) -> datetime | None:
    """A print's `trade_datetime`, in UTC as Terrapin states it, without an
    offset (YYYY-MM-DDTHH:MM:SS)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def ns(moment: datetime) -> int:
    return int(moment.timestamp()) * 1_000_000_000 + moment.microsecond * 1_000


def cusip_of(isin: str) -> str:
    """The CUSIP a US or Canadian ISIN holds; empty for any other."""
    isin = isin.strip().upper()
    if len(isin) == 12 and isin[:2] in CUSIP_COUNTRIES:
        return isin[2:11]
    return ""


def _isin_check(body: str) -> str:
    digits = "".join(str(int(c, 36)) for c in body)
    total = 0
    for i, c in enumerate(reversed(digits)):
        n = int(c)
        if i % 2 == 0:
            n *= 2
            n = n - 9 if n > 9 else n
        total += n
    return str((10 - total % 10) % 10)


def isin_of(cusip: str, country: str = "US") -> str:
    """The ISIN of a CUSIP (ISO 6166: the country, the CUSIP, the check
    digit); empty for what is not a CUSIP."""
    cusip = cusip.strip().upper()
    if len(cusip) != 9 or not cusip.isalnum():
        return ""
    body = country + cusip
    return body + _isin_check(body)


def is_isin(value: str) -> bool:
    value = value.strip().upper()
    return (
        len(value) == 12
        and value[:2].isalpha()
        and value.isalnum()
        and value[-1].isdigit()
        and _isin_check(value[:11]) == value[-1]
    )
