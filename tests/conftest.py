"""Shared stand-ins: the sample answers (src/terrapin/sample/), a fixed
clock, the deployment's records as a recorder answers them, and the lake's
wants as the sidecar delivers them."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.receive import Heard
from meridian.suites import Recorder

from terrapin.client import Fetched, SyntheticTerrapin
from terrapin.lake import Lake
from terrapin.terms import Reference

#: The sample's last day, after New York's close: 22:00 UTC, Friday 30 October 2026.
AT = datetime(2026, 10, 30, 22, 0, tzinfo=UTC)
INSTANCE = "terrapin"
#: The sample's securities: a corporate (its FIGI one the harness mints
#: from), a Treasury, an agency, a euro FRN, a CD and a municipal bond.
APPLE = "US037833ER75"
TREASURY = "US912810UA42"
AGENCY = "US3134HCZH51"
EUROBANK = "XS2724510792"
CD = "US06051XAB41"
MUNI = "US005824LP01"
LISTED = (APPLE, TREASURY, AGENCY, EUROBANK, CD, MUNI)
BOND_TEMPLATE = "TPL-bond"
CD_TEMPLATE = "TPL-certificate-of-deposit"


def source() -> SyntheticTerrapin:
    return SyntheticTerrapin(lambda: AT)


class Revised(SyntheticTerrapin):
    """The sample, its US curve of 30 October revised on the second read:
    the 10-year one basis point higher, as Terrapin restates a day."""

    def __init__(self) -> None:
        super().__init__(lambda: AT)
        self.reads = 0

    async def post(self, endpoint: str, body: dict[str, Any]) -> Fetched:
        if endpoint == "government_yield_curve" and body.get("date") == "2026-10-30":
            self.reads += 1
            if self.reads > 1:
                key = f"us:par:{body['date']}"
                held = deepcopy(self.curves[key])
                for point in held:
                    if point["years_to_maturity"] == 10.0:
                        point["rate"] = round(point["rate"] + 0.01, 3)
                return Fetched(endpoint, body, 200, json.dumps({"data": held}), AT)
        return await super().post(endpoint, body)


def lake(recorder: Recorder, *, securities: tuple[str, ...] = LISTED, terrapin: Any = None) -> Lake:
    """The data role's class and the reference role's, bound to `recorder`
    as `meridian.run` registers them."""
    reference = recorder.bind(Reference())
    made = recorder.bind(Lake(terrapin or source(), reference, now=lambda: AT))
    made.use(made.source, securities, True)
    return made


def template(template_id: str = BOND_TEMPLATE) -> ops.SecurityTemplate:
    """The bond template's first version, as the platform publishes it
    (templates-v29), or the CD's."""
    bond = [
        ("identifiers", "mint"), ("description", "mint"), ("currency", "mint"),
        ("instrument_type", "mint"), ("security_type", "mint"), ("issuer_company_id", "mint"),
        ("issuer_type", "mint"), ("issue_date", "mint"), ("maturity_date", "mint"),
        ("coupon_rate", "mint"), ("coupon_type", "mint"), ("coupon_frequency", "mint"),
        ("day_count", "mint"), ("country_of_issue", "complete"), ("dated_date", "complete"),
        ("first_coupon_date", "complete"), ("business_day_convention", "complete"),
        ("minimum_denomination", "complete"), ("denomination_increment", "complete"),
        ("calls", "complete"), ("sinking_funds", "complete"),
        ("original_issue_amount", "optional"), ("seniority", "optional"),
        ("rule_144a", "optional"), ("reg_s", "optional"), ("puts", "optional"),
        ("municipal", "optional"), ("state_or_province_of_issue", "optional"),
    ]  # fmt: skip
    cd = [
        ("identifiers", "mint"), ("description", "mint"), ("currency", "mint"),
        ("instrument_type", "mint"), ("issuer_company_id", "mint"), ("issue_date", "mint"),
        ("maturity_date", "mint"), ("coupon_rate", "mint"), ("coupon_frequency", "complete"),
        ("day_count", "complete"), ("minimum_denomination", "complete"), ("calls", "optional"),
    ]  # fmt: skip
    fields = bond if template_id == BOND_TEMPLATE else cd
    return ops.SecurityTemplate(
        template_id=template_id,
        template_version="1",
        asset_class=ops.ASSET_CLASS_DEBT,
        fields=[
            ops.TemplateField(
                path=path,
                requirement=getattr(ops, f"FIELD_REQUIREMENT_{level.upper()}"),
                repeated=path in ("calls", "puts", "sinking_funds"),
            )
            for path, level in fields
        ],
        match_rule=["figi"],
    )


def holding(
    recorder: Recorder,
    *,
    template_id: str = BOND_TEMPLATE,
    person_set: tuple[str, ...] = (),
) -> None:
    """The deployment's records as the store answers them: a curve's or an
    index's, by Terrapin's code, `INS-ref-n`, read back as a person accepted
    it (referential); a security's `INS-debt-n`, read back naming its
    template, `person_set` the fields a person set; the template read at its
    version."""
    resolved: list[str] = []

    def resolve(params: Any) -> ops.ResolveIdentifierResult:
        own = any(i.scheme == "symbol" and i.source == "terrapin" for i in params.identifiers)
        resolved.append("ref" if own else "debt")
        made = f"INS-{resolved[-1]}-{len(resolved)}"
        return ops.ResolveIdentifierResult(found=True, instrument_id=made)

    def record(params: Any) -> ops.ResolveInstrumentResult:
        if params.instrument_id.startswith("INS-ref-"):
            return ops.ResolveInstrumentResult(
                found=True,
                instrument=ops.InstrumentRecord(
                    instrument_id=params.instrument_id,
                    asset_class=ops.ASSET_CLASS_REFERENTIAL,
                    instrument_type=ops.INSTRUMENT_TYPE_RATE_CURVE,
                ),
            )
        return ops.ResolveInstrumentResult(
            found=True,
            instrument=ops.InstrumentRecord(
                instrument_id=params.instrument_id,
                asset_class=ops.ASSET_CLASS_DEBT,
                template_id=template_id,
                template_version="1",
                version=1,
                sources=[
                    ops.InstrumentValueSource(
                        field=getattr(ops, f"INSTRUMENT_FIELD_{f.upper()}"), person="person:alice"
                    )
                    for f in person_set
                ],
            ),
        )

    recorder.answer("ResolveIdentifier", resolve)
    recorder.answer("ResolveInstrument", record)
    recorder.answer(
        "ReadTemplate", lambda p: ops.ReadTemplateResult(template=template(p.template_id))
    )


def want(
    want_id: str,
    dataset: str,
    subjects: list[str],
    *,
    data_type: str = "meridian.v1.Trade",
    day: str = "",
    standing: bool = False,
) -> Heard[ops.ObservationsWantedEvent]:
    return Heard(
        row="ObservationsWanted",
        message=ops.ObservationsWantedEvent(
            want_id=want_id,
            dataset=f"{INSTANCE}:{dataset}",
            data_type=data_type,
            subjects=[ops.SubjectRef(entity_id=s) for s in subjects],
            business_date=day,
            standing=standing,
        ),
    )
