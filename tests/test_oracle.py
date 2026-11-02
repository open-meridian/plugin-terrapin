"""Terrapin's cash flows as an oracle for the engine's accrual (Track D):
an agency coupon's schedule and amounts, as Terrapin's public
documentation states them for US3134H1HN66 (5.5 per cent, 30/360,
semi-annual, 20 April and 20 October to 2028), against the SDK's own
coupon dates and year fractions (`meridian.helpers.debt`). No lake kind
holds a cash flow, so the plugin records none; tests/oracle/ keeps the case
for the engine's suite to read."""

from __future__ import annotations

import json
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from meridian.helpers import debt

ORACLE = Path(__file__).parent / "oracle" / "accrual.json"


def test_terrapin_s_cash_flows_meet_the_sdk_s_accrual() -> None:
    case = json.loads(ORACLE.read_text(encoding="utf-8"), parse_float=Decimal)
    terms = case["terms"]
    flows = case["terrapin"]["cashflows"]
    coupons = [f for f in flows if f["type"] == "interest"]
    dates = debt.coupon_dates(terms["maturity_date"], terms["coupon_frequency"],
                              dated=terms["dated_date"])  # fmt: skip
    assert [d.isoformat() for d in dates] == [f["date"] for f in coupons]
    start = terms["dated_date"]
    for flow, pay in zip(coupons, dates, strict=True):
        fraction = debt.year_fraction(terms["day_count"], start, pay)
        assert Fraction(Decimal(terms["coupon_rate"])) * fraction == Fraction(flow["amount"])
        start = pay.isoformat()
    [principal] = [f for f in flows if f["type"] == "principal"]
    assert principal["date"] == terms["maturity_date"] and principal["amount"] == 100
