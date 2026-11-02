"""Terrapin's reference answers as the bond and CD templates' fields, and
the reference role's offers: what is offered, by which path, with what
provenance, and what is never offered."""

from __future__ import annotations

import asyncio
from importlib import resources
from typing import Any

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.suites import Recorder

from terrapin import read, terms

from conftest import AGENCY, APPLE, CD, CD_TEMPLATE, EUROBANK, MUNI, TREASURY, holding, lake

#: The sample, read as the plugin reads Terrapin: every number a Decimal.
SAMPLE = read.parse(
    resources.files("terrapin").joinpath("sample/answers.json").read_text(encoding="utf-8")
)


def held(isin: str, muni: bool = False) -> terms.Terms:
    answers = SAMPLE["muni_reference" if muni else "securities_reference"]
    return terms.terms(answers[isin], muni=muni)


def test_a_corporate_with_its_make_whole_and_par_calls() -> None:
    apple = held(APPLE)
    said = terms.by_path(apple.offers)
    assert apple.instrument_type == "bond" and apple.figi == "BBG01BOND0001"
    assert said["security_type"] == "DEBT_SECURITY_TYPE_CORP"
    assert said["issuer_type"] == "ISSUER_TYPE_CORPORATE"
    assert said["coupon_rate"] == "4.875" and said["coupon_type"] == "COUPON_TYPE_FIXED"
    # Terrapin's 30/360 does not say which: the generic value, never a guess.
    assert said["day_count"] == "DAY_COUNT_THIRTY_360"
    assert said["coupon_frequency"] == "2"
    assert said["dated_date"] == "2026-02-05" and said["first_coupon_date"] == "2026-08-05"
    assert said["minimum_denomination"] == "2000" and said["denomination_increment"] == "1000"
    assert said["seniority"] == "SENIORITY_SENIOR"
    assert said["rule_144a"] == "false" and said["reg_s"] == "false"
    assert said["calls[0].kind"] == "REDEMPTION_KIND_MAKE_WHOLE"
    assert said["calls[0].make_whole_spread_bps"] == "15"
    assert said["calls[0].from_date"] == "2026-08-05" and said["calls[0].to_date"] == "2035-11-05"
    assert said["calls[0].style"] == "REDEMPTION_STYLE_CONTINUOUS"
    assert said["calls[1].kind"] == "REDEMPTION_KIND_PAR" and said["calls[1].price"] == "100"
    assert "calls[1].to_date" not in said
    # Its CUSIP read from its ISIN, kept on the deployment's record.
    named = [(i.scheme, i.value) for i in apple.identifiers()]
    assert named == [("figi", "BBG01BOND0001"), ("isin", APPLE), ("cusip", "037833ER7")]


def test_a_treasury_by_its_terms_and_an_agency_coupon() -> None:
    said = terms.by_path(held(TREASURY).offers)
    assert said["security_type"] == "DEBT_SECURITY_TYPE_TBOND"
    assert said["issuer_type"] == "ISSUER_TYPE_SOVEREIGN"
    assert said["day_count"] == "DAY_COUNT_ACT_ACT"
    agency = terms.by_path(held(AGENCY).offers)
    assert agency["security_type"] == "DEBT_SECURITY_TYPE_FAC"
    assert agency["calls[0].style"] == "REDEMPTION_STYLE_BERMUDAN"


def test_a_floater_offers_no_fixed_coupon() -> None:
    eurobank = held(EUROBANK)
    said = terms.by_path(eurobank.offers)
    assert said["coupon_type"] == "COUPON_TYPE_FLOATING"
    assert "coupon_rate" not in said
    assert said["day_count"] == "DAY_COUNT_ACT_ACT_ICMA"
    assert said["rule_144a"] == "true" and said["reg_s"] == "true"


def test_a_cd_is_its_own_template() -> None:
    cd = held(CD)
    said = terms.by_path(cd.offers)
    assert cd.instrument_type == "certificate_of_deposit"
    assert said["instrument_type"] == "INSTRUMENT_TYPE_CERTIFICATE_OF_DEPOSIT"
    assert said["day_count"] == "DAY_COUNT_ACT_365_FIXED"
    assert "security_type" not in said and "issuer_type" not in said


def test_a_municipal_bond_and_its_group() -> None:
    muni = held(MUNI, muni=True)
    said = terms.by_path(muni.offers)
    assert muni.muni and not muni.lei
    assert said["security_type"] == "DEBT_SECURITY_TYPE_GO"
    assert said["issuer_type"] == "ISSUER_TYPE_MUNICIPAL"
    assert said["state_or_province_of_issue"] == "IL"
    assert said["municipal.bank_qualified"] == "true"
    assert said["municipal.state_tax_exempt"] == "false"
    assert said["calls[0].kind"] == "REDEMPTION_KIND_PAR"
    assert said["calls[0].notice_days_min"] == "30" and said["calls[0].notice_days_max"] == "60"


def test_what_maps_to_no_value_is_said() -> None:
    item: dict[str, Any] = dict(SAMPLE["securities_reference"][TREASURY])
    item.update(interest_accrual_convention="30/365", seniority="SNDB", interest_type="misc.")
    made = terms.terms(item, muni=False)
    assert "interest_accrual_convention 30/365" in made.unmapped
    assert "seniority SNDB" in made.unmapped and "interest_type misc." in made.unmapped
    said = terms.by_path(made.offers)
    assert "day_count" not in said and "seniority" not in said and "coupon_type" not in said


def offered(recorder: Recorder) -> list[ops.OfferTemplateFieldsParams]:
    return [p for p in recorder.on("OfferTemplateFields")]


def test_offers_go_in_two_calls_with_their_provenance() -> None:
    recorder = Recorder("terrapin")
    holding(recorder)
    asyncio.run(lake(recorder, securities=(APPLE,)).terms())
    own, groups = offered(recorder)
    assert all("." not in f.path and "[" not in f.path for f in own.fields)
    assert all("[" in f.path or "." in f.path for f in groups.fields)
    paths = {f.path: f for f in own.fields}
    assert paths["issuer_company_id"].value.startswith("ENT-")
    coupon = paths["coupon_rate"]
    assert coupon.provenance.kind == ops.PROVENANCE_KIND_REPORTED
    assert coupon.provenance.source == "Terrapin"
    assert coupon.provenance.raw_record.key == f"securities_reference/{APPLE}"
    assert paths["day_count"].provenance.kind == ops.PROVENANCE_KIND_DERIVED
    # The template lacks fields Terrapin states nothing for: never offered.
    assert "business_day_convention" not in paths and "puts" not in paths


def test_a_person_s_value_is_never_offered_over() -> None:
    recorder = Recorder("terrapin")
    holding(recorder, person_set=("description", "currency"))
    asyncio.run(lake(recorder, securities=(APPLE,)).terms())
    sent = {f.path for p in offered(recorder) for f in p.fields}
    assert "description" not in sent and "currency" not in sent and "coupon_rate" in sent


def test_a_cd_is_offered_only_its_template_s_fields() -> None:
    recorder = Recorder("terrapin")
    holding(recorder, template_id=CD_TEMPLATE)
    asyncio.run(lake(recorder, securities=(CD,)).terms())
    [own] = offered(recorder)
    assert own.template_id == CD_TEMPLATE
    assert {f.path for f in own.fields} <= {f.path for f in _cd_fields()}


def _cd_fields() -> list[ops.TemplateField]:
    from conftest import template

    return list(template(CD_TEMPLATE).fields)


def test_a_refused_group_keeps_the_record_s_own_fields() -> None:
    import meridian

    recorder = Recorder("terrapin")
    holding(recorder)

    def offer(params: ops.OfferTemplateFieldsParams) -> ops.OfferTemplateFieldsResult:
        if any("[" in f.path for f in params.fields):
            raise meridian.MeridianError("fields[0].path: TPL-bond has no field calls[0].kind")
        return ops.OfferTemplateFieldsResult(
            instrument=ops.InstrumentRecord(instrument_id=params.instrument_id, version=2)
        )

    recorder.answer("OfferTemplateFields", offer)
    work = lake(recorder, securities=(APPLE,))
    asyncio.run(work.terms())
    [done] = work.reference.offered.values()
    assert done.version == 2 and "calls[0].kind" in done.refused
