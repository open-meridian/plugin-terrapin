"""The pages on sample data, each printed as one HTML file: for looking at
them without a deployment, and for `make preview SHOTS=<dir>`, which checks
each in a browser with the kit at 375, 582 and 1280 pixels.

    python -m terrapin.preview connection > preview/connection.html
    python -m terrapin.preview datasets > preview/datasets.html

The plugin's work runs against the suites' recorder in place of a sidecar --
each record resolved, every batch recorded, each security's record read
back naming its template -- on the sample answers (sample/answers.json),
after New York's close on 30 October 2026: the check run, a want of a
municipal bond's prints answered and one declined. `connection-first` and
`datasets-first` are the pages before the first check: the role's "not set
up yet" states.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.receive import Heard
from meridian.suites import Recorder
from meridian.testing import PageClient

from .client import SyntheticTerrapin
from .lake import Lake
from .page import hold, pages
from .terms import Reference

AT = datetime(2026, 10, 30, 22, 0, tzinfo=UTC)
#: The sample's listed securities.
LISTED = ("US037833ER75", "US912810UA42", "US3134HCZH51", "XS2724510792", "US06051XAB41",
          "US005824LP01")  # fmt: skip
#: A subject the deployment holds no record of, wanted and declined.
NOT_HELD = "not-a-record"
PAGES = {
    "connection": "/",
    "datasets": "/datasets",
    "connection-first": "/",
    "datasets-first": "/datasets",
}


def _want(want_id: str, subject: str, day: str) -> Heard[ops.ObservationsWantedEvent]:
    return Heard(
        row="ObservationsWanted",
        message=ops.ObservationsWantedEvent(
            want_id=want_id,
            dataset="terrapin:muni_trades",
            data_type="meridian.v1.Trade",
            subjects=[ops.SubjectRef(entity_id=subject)],
            business_date=day,
        ),
    )


def _lake(recorder: Recorder) -> Lake:
    own: set[str] = set()
    made: list[str] = []

    def resolve(params: ops.ResolveIdentifierParams) -> ops.ResolveIdentifierResult:
        local = any(i.source == "terrapin" for i in params.identifiers)
        made.append(f"{'LCL' if local else 'INS'}-PREVIEW-{len(made) + 1}")
        if local:
            own.add(made[-1])
        return ops.ResolveIdentifierResult(found=True, instrument_id=made[-1])

    def record(params: ops.ResolveInstrumentParams) -> ops.ResolveInstrumentResult:
        if params.instrument_id in own:
            # A curve's or an index's record, as a person accepted it.
            accepted = ops.InstrumentRecord(
                instrument_id=params.instrument_id,
                asset_class=ops.ASSET_CLASS_REFERENTIAL,
                instrument_type=ops.INSTRUMENT_TYPE_RATE_CURVE,
            )
            return ops.ResolveInstrumentResult(found=True, instrument=accepted)
        return ops.ResolveInstrumentResult(
            found=params.instrument_id != NOT_HELD,
            instrument=ops.InstrumentRecord(
                instrument_id=params.instrument_id, template_id="TPL-bond", template_version="1"
            ),
        )

    template = ops.SecurityTemplate(
        template_id="TPL-bond",
        template_version="1",
        fields=[ops.TemplateField(path=p) for p in (
            "description", "currency", "coupon_rate", "coupon_type", "day_count", "issue_date",
            "maturity_date", "calls", "issuer_company_id", "issuer_type", "municipal",
        )],
    )  # fmt: skip
    recorder.answer("ResolveIdentifier", resolve)
    recorder.answer("ResolveInstrument", record)
    recorder.answer("ReadTemplate", lambda _: ops.ReadTemplateResult(template=template))
    reference = recorder.bind(Reference())
    lake = recorder.bind(Lake(SyntheticTerrapin(lambda: AT), reference, now=lambda: AT))
    lake.use(lake.source, LISTED, False)
    return lake


async def _worked(recorder: Recorder) -> Lake:
    lake = _lake(recorder)
    await lake.check()
    muni = lake.records["US005824LP01"]
    await lake.on_observations_wanted(_want("want-1027", muni, "2026-10-27"))
    await lake.on_observations_wanted(_want("want-other", NOT_HELD, "2026-10-27"))
    return lake


def render(page: str) -> str:
    recorder = Recorder("terrapin")
    lake = _lake(recorder) if page.endswith("-first") else asyncio.run(_worked(recorder))
    hold(lake)
    answer = PageClient(pages, recorder.plugin, roles=("data", "reference")).get(
        PAGES[page], "admin"
    )
    if answer.status != 200:
        raise SystemExit(f"{page} answered {answer.status}: {answer.text[:200]}")
    return answer.text


def main() -> None:
    page = sys.argv[1] if len(sys.argv) > 1 else "connection"
    if page not in PAGES:
        raise SystemExit(f"no page {page!r}: {', '.join(PAGES)}")
    sys.stdout.write(render(page))


if __name__ == "__main__":
    main()
