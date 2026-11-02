"""The data role's work on the sample: curves, inflation, prints, wants and
what is said rather than recorded."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal

from meridian.operations import as_decimal
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.suites import Recorder

from terrapin import curves
from terrapin.lake import Lake
from terrapin.trades import MUNI_TRADES

from conftest import LISTED, MUNI, holding, lake, want


def checked() -> tuple[Recorder, Lake]:
    recorder = Recorder("terrapin")
    holding(recorder)
    work = lake(recorder)
    asyncio.run(work.check())
    return recorder, work


def test_the_check_records_curves_indexes_and_prints() -> None:
    recorder, _ = checked()
    rates = [r for sent in recorder.on("RecordRates") for r in sent.rates]
    datasets = {r.meta.source.dataset for r in rates}
    assert datasets == {"terrapin:government_curves", "terrapin:inflation"}
    trades = [t for sent in recorder.on("RecordTrades") for t in sent.trades]
    assert len(trades) == 4 and {t.meta.source.dataset for t in trades} == {
        f"terrapin:{MUNI_TRADES}"
    }
    # Each listed security resolved, five offered terms (the muni's record a
    # bond's too), no price recorded.
    assert len(recorder.on("ResolveIdentifier")) >= len(LISTED)
    assert not recorder.on("RecordPrices")


def test_a_par_curve_carries_its_market_s_convention() -> None:
    recorder, work = checked()
    rates = [r for sent in recorder.on("RecordRates") for r in sent.rates
             if r.meta.business_date == "2026-10-30"]  # fmt: skip

    def of(region: curves.Region) -> list[ops.Rate]:
        record = work.records[region.symbol]
        return [r for r in rates if r.meta.subjects[0].entity_id == record]

    us, de = of(curves.US), of(curves.DE)
    assert {r.meta.source.dataset for r in us + de} == {"terrapin:government_curves"}
    assert len(us) == 10 and len(de) == 10
    ten = next(r for r in us if r.tenor.count == 10)
    assert ten.kind == ops.RATE_KIND_PAR_YIELD
    assert ten.convention.periods_per_year == 2
    assert ten.convention.day_count == ops.DAY_COUNT_ACT_ACT
    assert as_decimal(ten.value.value) == Decimal("4.109")
    assert next(r for r in de if r.tenor.count == 10).convention.day_count == (
        ops.DAY_COUNT_ACT_ACT_ICMA
    )


def test_an_index_level_is_an_index_value() -> None:
    recorder, _ = checked()
    rates = [r for sent in recorder.on("RecordRates") for r in sent.rates
             if r.meta.source.dataset == "terrapin:inflation"]  # fmt: skip
    us = [r for r in rates if r.meta.business_date == "2026-09-01"
          and "TERRAPIN_US_INFLATION" in r.meta.row_key]  # fmt: skip
    [september] = us
    assert september.kind == ops.RATE_KIND_INDEX_LEVEL
    assert september.value.unit == ops.VALUE_UNIT_INDEX
    assert as_decimal(september.value.value) == Decimal("329.932")
    assert september.convention.compounding == ops.COMPOUNDING_SIMPLE


def test_a_point_that_is_no_tenor_is_said() -> None:
    assert curves.tenor_of(Decimal("10")) == "10Y"
    assert curves.tenor_of(Decimal("0.5")) == "6M"
    assert curves.tenor_of(Decimal("9.8")) is None


def test_a_print_s_characteristics_and_what_is_kept_as_reported() -> None:
    recorder, _ = checked()
    trades = {t.meta.row_key: t for sent in recorder.on("RecordTrades") for t in sent.trades}
    ats = trades[f"msrb:{MUNI}:sB7c2Lr1Q0eV0m0pXl2a1w"]
    names = [ops.TradeCharacteristic.Name(c) for c in ats.attributes.characteristics]
    assert names == ["TRADE_CHARACTERISTIC_CONTRA_DEALER", "TRADE_CHARACTERISTIC_ATS_EXECUTED"]
    assert ats.basis == ops.PRICE_BASIS_PERCENT_OF_PAR
    assert as_decimal(ats.price.amount) == Decimal("108.902") and ats.price.currency_code == "USD"
    assert as_decimal(ats.quantity) == Decimal("25000")
    assert ats.meta.business_date == "2026-10-27"
    assert getattr(ats, "yield").kind == ops.YIELD_KIND_TO_MATURITY
    wap = trades[f"msrb:{MUNI}:sC3d9Pq8RkuW2n4tYb7c5g"]
    schemes = [u.scheme for u in wap.meta.unconverted]
    assert schemes == ["terrapin:is_weighted_avg_price_trade", "terrapin:trade_type"]
    assert not wap.attributes.HasField("consolidated")
    # Never a capacity or traded flat: Terrapin's prints do not state them.
    for trade in trades.values():
        for c in trade.attributes.characteristics:
            assert "CAPACITY" not in ops.TradeCharacteristic.Name(c)
            assert ops.TradeCharacteristic.Name(c) != "TRADE_CHARACTERISTIC_TRADED_FLAT"
    assert trades[f"msrb:{MUNI}:sD5f1Mw6TiyX8o2uZc3e7h"].cancelled


def test_a_want_of_a_muni_s_prints_is_recorded_against() -> None:
    recorder = Recorder("terrapin")
    holding(recorder)
    work = lake(recorder)
    asyncio.run(work.terms())
    record = work.records[MUNI]
    asyncio.run(work.on_observations_wanted(want("w-1", MUNI_TRADES, [record], day="2026-10-27")))
    [sent] = recorder.on("RecordTrades")
    assert sent.want_id == "w-1" and len(sent.trades) == 1


def test_a_want_of_a_curve_for_a_date() -> None:
    recorder = Recorder("terrapin")
    work = lake(recorder, securities=())
    record = asyncio.run(work.referential(curves.US.symbol, curves.US.description, "USD",
                                          "rate_curve"))  # fmt: skip
    heard = want("w-2", "government_curves", [record, "INS-OTHER"], data_type="meridian.v1.Rate",
                 day="2026-10-28")  # fmt: skip
    asyncio.run(work.on_observations_wanted(heard))
    [sent] = recorder.on("RecordRates")
    assert sent.want_id == "w-2" and {r.meta.business_date for r in sent.rates} == {"2026-10-28"}
    [declined] = recorder.on("DeclineWant")
    assert [s.entity_id for s in declined.subjects] == ["INS-OTHER"]


def test_a_curve_s_record_is_local_and_stated_with_its_currency() -> None:
    recorder = Recorder("terrapin")
    work = lake(recorder, securities=())
    asyncio.run(work.curve_rows(curves.US, date(2026, 10, 30)))
    [asked] = recorder.on("ResolveIdentifier")
    assert [(i.scheme, i.value, i.source) for i in asked.identifiers] == [
        ("symbol", "TERRAPIN_US_PAR", "terrapin")
    ]
    assert asked.stated_currency == "USD" and asked.stated_description
    assert asked.stated_instrument_type == ops.INSTRUMENT_TYPE_RATE_CURVE


def test_nothing_is_asked_without_a_key() -> None:
    from terrapin.client import LiveTerrapin

    recorder = Recorder("terrapin")
    work = lake(recorder, terrapin=LiveTerrapin(""))
    work.use(work.source, LISTED, False)
    asyncio.run(work.check())
    assert not recorder.sent
