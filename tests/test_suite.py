"""The data suite and the reference suite (meridian.suites, contract v29),
each case Terrapin presents mapped to the plugin's own conversion of the
sample answers (src/terrapin/sample/), each it never presents named with
why.

**Data, presented:** a curve for a date, its tenor set changed from the day
before (30 October's US par curve after 29 October's, which states no
25-year point); a tenor not published (29 October's); a same-day revision
(30 October's 10-year restated); an index level (an inflation factor); a
trade recorded (a regular municipal print); a condition not converted
(MSRB's weighted average price flag); a trade withdrawn (a print Terrapin
marks cancelled); an asset that does not resolve; a subject declined; a
standing want withdrawn; its datasets' licences read; and the cases the
SDK answers.

**Data, not presented:** prices of every kind -- Terrapin's end-of-day
prices wait on its answer about their source and clean or dirty (871,
900's R7) -- with bars, quotes and a venue's prices; an odd-lot condition,
which a bond print never states; a print's aggressor; streaming, its
liveness and a restart's gap, since Terrapin is asked, never streamed;
publication times, which Terrapin does not state; a fixing, two
conventions for one tenor, a point from another source; the lake query, a
calendar and a settlement date, which it never asks; and the kinds it never
publishes (outcomes, chains, filings, holdings, corporate actions, ratings,
derived series, factors).

**Reference, presented:** a template filled (the sample corporate's terms
offered to its record); a licensed vendor's value kept as an offer, its
provenance Terrapin's raw record; a person's value never offered over; the
record read before it is filled; a security resolved by its identifiers;
and the cases the SDK answers. Not presented: calendars and settlement
dates, which its work never uses.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.suites import ANSWERED_BY_SDK, Recorder, run, suite

from terrapin.curves import CURVES_KEY, US
from terrapin.trades import MUNI_TRADES

from conftest import APPLE, MUNI, Revised, holding, lake, source, want

Producer = Callable[[Recorder], Awaitable[None]]

R7 = (
    "Terrapin's end-of-day prices are not recorded until it states their source and whether "
    "they are clean or dirty (rulings 871, 900's R7); it records rates, prints and terms"
)
#: Each kind of data a case may be about, and why Terrapin never presents it.
NEVER_KINDS = {
    "closes": R7,
    "bars": "Terrapin states no bars",
    "a currency's rate against another currency": "Terrapin states no currency's rate",
    "a crypto asset's price": "Terrapin states no crypto asset",
    "prices on a venue": R7,
    "a security's price": R7,
    "quotes": "Terrapin states no quotes",
    "outcomes": "Terrapin states no event contract",
    "disputed outcomes": "Terrapin states no event contract",
    "option chains": "Terrapin states no option",
    "filings": "Terrapin's municipal documents have no lake kind; not recorded",
    "holdings": "Terrapin states no holdings",
    "corporate actions": "Terrapin's municipal events have no lake kind; not recorded",
    "ratings": "Terrapin's composite ratings are not a rating agency's action; not recorded",
    "derived series": "it publishes no figure of its own",
    "factors": "Terrapin states no pool's or class's factor (the agencies' plugins do)",
    "streams": "Terrapin is asked hourly and on wants; it streams nothing, so records no liveness",
    "publication times": (
        "Terrapin states no publication time for a curve, an index or a print, so no feed "
        "delay is measured"
    ),
    "calendars": "it records what Terrapin states; it reads no calendar",
    "settlement dates": "it records what Terrapin states; it asks no settlement date",
}
DATA_NEVER = {
    "a-condition-converted": (
        "a bond print states no odd-lot condition; MSRB's flags convert to the fixed-income "
        "characteristics, presented by a-condition-not-converted and a-trade-recorded"
    ),
    "the-takers-side-stated": "MSRB's prints name no side that took liquidity",
    "the-makers-side-inverted": "MSRB's prints name no side that took liquidity",
    "a-standing-want-streamed": "Terrapin's prints are asked hourly and on wants, never streamed",
    "a-restarts-gap-backfilled": (
        "Terrapin's prints are asked hourly over the last seven days, never streamed, so a "
        "restart leaves no gap"
    ),
    "queries-the-lake-within-bounds": "it records what Terrapin states and reads nothing back",
    "a-rate-fixing": "Terrapin publishes curves and indexes, no reference rate's fixing",
    "two-conventions-one-tenor": "Terrapin's par curve states one convention for each tenor",
    "a-curve-point-from-another-source": "Terrapin publishes whole curves, never one point",
}


def not_presented(role: str, never: dict[str, str]) -> dict[str, str]:
    held = {
        case.name: NEVER_KINDS[case.about]
        for case in suite(role).cases
        if case.about in NEVER_KINDS and case.name not in ANSWERED_BY_SDK
    }
    return {**held, **never}


DATA_NOT_PRESENTED = not_presented("data", DATA_NEVER)
REFERENCE_NOT_PRESENTED = not_presented("reference", {})


async def curve_changed(recorder: Recorder) -> None:
    work = lake(recorder, securities=())
    for day in (date(2026, 10, 29), date(2026, 10, 30)):
        await work.feeds[US.code].record(CURVES_KEY, await work.curve_rows(US, day))
    first, second = recorder.on("RecordRates")
    assert len(first.rates) == 9 and len(second.rates) == 10


async def tenor_not_published(recorder: Recorder) -> None:
    work = lake(recorder, securities=())
    rows = await work.curve_rows(US, date(2026, 10, 29))
    await work.feeds[US.code].record(CURVES_KEY, rows)
    assert all(r.meta is not None and ":25Y:" not in r.meta.row_key for r in rows)


async def revised(recorder: Recorder) -> None:
    work = lake(recorder, securities=(), terrapin=Revised())
    day = date(2026, 10, 30)
    await work.feeds[US.code].record(CURVES_KEY, await work.curve_rows(US, day))
    again = [
        r
        for r in await work.curve_rows(US, day)
        if r.meta is not None and ":10Y:" in r.meta.row_key
    ]
    await work.feeds[US.code].record(CURVES_KEY, again)
    first, second = recorder.on("RecordRates")
    [after] = second.rates
    [before] = [r for r in first.rates if r.meta.row_key == after.meta.row_key]
    assert before.value != after.value


async def index_level(recorder: Recorder) -> None:
    work = lake(recorder, securities=())
    rows = await work.inflation_rows("US", date(2026, 1, 1), date(2026, 9, 30))
    await work.feeds["inflation"].record("inflation", rows)


def a_print(which: str) -> Producer:
    """One of the sample municipal bond's prints, recorded alone."""

    async def produce(recorder: Recorder) -> None:
        work = lake(recorder, securities=())
        rows = await work.print_rows(MUNI, "INS-MUNI", date(2026, 10, 23), date(2026, 10, 30))
        picked = {
            "regular": [r for r in rows if r.attributes and r.attributes.consolidated],
            "unconverted": [r for r in rows if r.meta and r.meta.unconverted
                            and "weighted" in r.meta.unconverted[0].scheme],
            "cancelled": [r for r in rows if r.cancelled],
        }[which]  # fmt: skip
        assert picked, which
        await work.wants.record("trades", picked[:1], MUNI_TRADES)

    return produce


async def ambiguous(recorder: Recorder) -> None:
    recorder.answer(
        "ResolveIdentifier",
        lambda _: ops.ResolveIdentifierResult(found=False, miss_reason=ops.MISS_REASON_AMBIGUOUS),
    )
    await lake(recorder, securities=(APPLE,)).terms()


async def declined(recorder: Recorder) -> None:
    recorder.answer("ResolveInstrument", lambda _: ops.ResolveInstrumentResult(found=False))
    work = lake(recorder, securities=())
    recorder.answer(
        "ObservationsWanted", lambda _: want("w-1", MUNI_TRADES, ["INS-NOT-A-MUNI"]).message
    )
    await recorder.hear(work, "ObservationsWanted")


async def withdrawn(recorder: Recorder) -> None:
    work = lake(recorder, securities=())
    recorder.answer(
        "WantWithdrawn",
        lambda _: ops.WantWithdrawnEvent(want_id="w-1", dataset=f"terrapin:{MUNI_TRADES}"),
    )
    await recorder.hear(work, "WantWithdrawn")


async def licences(recorder: Recorder) -> None:
    await lake(recorder, securities=()).wants.read_licences()


DATA: dict[str, Producer] = {
    "a-curve-for-a-date": curve_changed,
    "a-tenor-not-published": tenor_not_published,
    "a-same-day-revision": revised,
    "an-index-level": index_level,
    "a-trade-recorded": a_print("regular"),
    "a-condition-not-converted": a_print("unconverted"),
    "a-trade-withdrawn": a_print("cancelled"),
    "an-asset-that-does-not-resolve": ambiguous,
    "a-subject-declined": declined,
    "a-standing-want-withdrawn": withdrawn,
    "reads-its-datasets-licences": licences,
}


def filled(person_set: tuple[str, ...] = ()) -> Producer:
    async def produce(recorder: Recorder) -> None:
        holding(recorder, person_set=person_set)
        await lake(recorder, securities=(APPLE,)).terms()

    return produce


REFERENCE: dict[str, Producer] = {
    "fills-a-template": filled(),
    "licensed-vendor-value-stays": filled(),
    "offers-never-overwrite-a-person": filled(("description",)),
    "reads-the-record-it-fills": filled(),
    "resolves-a-security-it-reconciles": filled(),
}


def test_the_data_suite_passes() -> None:
    report = run("data", DATA, not_presented=DATA_NOT_PRESENTED, instance_id="terrapin")
    assert report.passed, report.failures
    assert set(report.passed_cases) == set(DATA) | set(ANSWERED_BY_SDK)


def test_the_reference_suite_passes() -> None:
    report = run(
        "reference", REFERENCE, not_presented=REFERENCE_NOT_PRESENTED, instance_id="terrapin"
    )
    assert report.passed, report.failures
    assert set(report.passed_cases) == set(REFERENCE) | set(ANSWERED_BY_SDK)
    assert sorted(report.not_presented) == ["asks-for-a-settlement-date", "reads-a-calendar"]


def test_every_price_case_says_why_ruling_900_r7() -> None:
    for case in suite("data").cases:
        if case.about in ("closes", "a security's price", "prices on a venue"):
            assert DATA_NOT_PRESENTED[case.name] == R7


def test_the_sample_is_read_from_the_package() -> None:
    assert source().today_is == date(2026, 10, 30)
