"""Terrapin's municipal prints, as the lake's trades.

Terrapin's `muni_pricing_history` states each municipal bond's trades as
MSRB disseminates them through its post-trade feeds: the price as a
percentage of face, the face amount, the trade's time in UTC, the
settlement date, who traded with whom, MSRB's flags and the yields at the
price. Each becomes one `Trade` (W10.4; contract v29):

- **its key** Terrapin's trade ID, under the bond's ISIN, so a print stated
  again is answered unchanged and one Terrapin later marks cancelled is the
  same row's next version, `cancelled` (the data suite's
  `a-trade-withdrawn`);
- **its price** in US dollars, its basis `percent_of_par` (MSRB states a
  municipal trade's dollar price per 100 of par); no yield beside it: the
  lake asks a quoted yield's day count, which Terrapin does not state for
  the yields it computes on a print (asked, ruling 871), and a yield to
  call names no call date;
- **its quantity** the face amount traded, exactly as stated;
- **its characteristics** by meaning, in the platform's list
  (`meridian.helpers.debt.characteristics`, 685 and 900's R5): a customer
  or an inter-dealer trade (`contra_customer`, `contra_dealer`), executed
  on an ATS, when issued, list offering price or takedown, non-transaction
  compensation;
- **what does not convert** kept as reported (`ObservationMeta.unconverted`):
  MSRB's weighted average price flag, which the list does not hold, and
  which side the customer took, which no characteristic carries.

**Not stated, so not presented** (900's R4): the dealer's capacity and
traded flat, which Terrapin's prints do not carry; none listed means none
the source states, never "a regular trade". A regular print -- no flag
set -- is eligible for each statistic of a bar; a flagged one's
eligibility is left unstated, as MSRB does not say it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import meridian
from meridian.helpers import debt
from meridian.plugin.v1 import operations_pb2 as ops

from . import read

MUNI_TRADES = "muni_trades"
#: How the source is named on what is kept as reported.
SOURCE = "terrapin"

_CONTRA = {"customer_bought": "customer", "customer_sold": "customer", "inter_dealer": "dealer"}
_FLAGS = (
    "is_alt_trading_system",
    "is_when_issued_trade",
    "is_list_offering_price",
    "is_non_transaction_compensation",
    "is_weighted_avg_price_trade",
)
_ELIGIBLE = meridian.Eligibility(
    high_low="ELIGIBLE_ELIGIBLE", open="ELIGIBLE_ELIGIBLE", close="ELIGIBLE_ELIGIBLE",
    volume="ELIGIBLE_ELIGIBLE",
)  # fmt: skip


@dataclass(frozen=True)
class Unread:
    """What a print stated that could not be recorded, and why."""

    isin: str
    trade_id: str
    why: str


def convert(
    item: dict[str, Any], subject: str, dataset: str, raw: ops.RawRecordRef
) -> meridian.Trade | Unread:
    """One print as the lake's trade for `subject`, or why it is not one."""
    isin = read.text(item.get("isin"))
    trade_id = read.text(item.get("id"))
    price = read.number(item.get("price"))
    amount = read.number(item.get("amount"))
    moment = read.utc_moment(item.get("trade_datetime"))
    if not trade_id or price is None or moment is None:
        return Unread(isin, trade_id, "a print with no ID, price or time")
    if amount is None:
        return Unread(isin, trade_id, "a print stating no face amount")
    at = read.ns(moment)
    trade_type = read.text(item.get("trade_type"))
    flags = {name: item.get(name) is True for name in _FLAGS}
    found = debt.characteristics(
        contra_party=_CONTRA.get(trade_type, ""),
        ats=flags["is_alt_trading_system"],
        when_issued=flags["is_when_issued_trade"],
        list_offering_price_takedown=flags["is_list_offering_price"],
        non_transaction_compensation=flags["is_non_transaction_compensation"],
    )
    unconverted = []
    if flags["is_weighted_avg_price_trade"]:
        unconverted.append(
            ops.AsReported(
                scheme=f"{SOURCE}:is_weighted_avg_price_trade",
                code="true",
                text="a weighted average price trade (MSRB)",
            )
        )
    if trade_type in ("customer_bought", "customer_sold"):
        unconverted.append(
            ops.AsReported(
                scheme=f"{SOURCE}:trade_type", code=trade_type, text=trade_type.replace("_", " ")
            )
        )
    elif trade_type and trade_type not in _CONTRA:
        unconverted.append(ops.AsReported(scheme=f"{SOURCE}:trade_type", code=trade_type[:128],
                                          text=trade_type[:256]))  # fmt: skip
    regular = not any(v for k, v in flags.items() if k != "is_alt_trading_system")
    meta = meridian.ObservationMeta(
        row_key=f"msrb:{isin}:{trade_id}"[:128],
        subjects=[meridian.SubjectRef(entity_id=subject)],
        source=ops.Source(dataset=dataset),
        valid_from_ns=at,
        source_times=[meridian.SourceTime(kind="event", at_ns=at)],
        raw=raw,
        unconverted=unconverted,
    )
    return meridian.Trade(
        meta=meta,
        price=meridian.Money(price, currency_code="USD"),
        quantity=amount,
        basis="percent_of_par",
        cancelled=item.get("is_cancelled") is True,
        attributes=meridian.TradeAttributes(
            consolidated=_ELIGIBLE if regular else None,
            market_centre=_ELIGIBLE if regular else None,
            characteristics=found,
        ),
    )
