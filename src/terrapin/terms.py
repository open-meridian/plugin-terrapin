"""Terrapin's reference data, as offers of a security's template fields
(the `reference` role, W3.23; contract v29's `bond` and
`certificate_of_deposit` templates).

**Offers, never decisions.** For a security the deployment holds, the
plugin reads its record and its template, and offers each field Terrapin
states that the template has, with its provenance: the value as Terrapin
wrote it (`reported`, its raw record named) or worked out from it by a
named rule (`derived`). A value a person set or accepted is never offered
over (the record's sources say who set it); a value is in force only once
a person accepts it (W3.10). The plugin never asks for a mint (W3.4).

**Paths** (W1.24, 574): a field by its name (`coupon_rate`), a group's
field dotted (`municipal.federal_tax_status`), a repeated group's row
indexed (`calls[0].kind`). A field's value is written as its type writes
it: a date ISO 8601, a number as Terrapin wrote it, a boolean `true` or
`false`, an enum by its value's name (`ISSUER_TYPE_CORPORATE`). Fields are
offered in two calls, the template's own first and the groups after, so a
store refusing a group's path still keeps the rest.

**What Terrapin states, mapped** (Terrapin's field, then the template's):

- `name` description; `currency` currency; `asset_class`
  `certificates_of_deposit` instrument type `certificate_of_deposit`, any
  other `bond`;
- `issuer_type` (Q4's six values): corporate, government (sovereign),
  government_linked (agency), international_organization (supranational),
  state (sub-sovereign), municipal (municipal);
- `lei` -> `issuer_company_id`, the issuer's `ENT-` company record the LEI
  resolves to (W3.32); none offered where it does not resolve;
- `issue_date`, `maturity_date`; `interest_accrual_date` dated date;
  `first_interest_payment_date` first coupon date; `country_code` country
  of issue; munis' `state` state of issue;
- `interest_rate` coupon rate where the coupon is fixed or steps;
  `interest_type` coupon type (fixed rate, step rate, zero rate / discount
  rate, variable rate as floating; fixed to float, float to fixed and the
  others not offered); `coupon_frequency`;
- `interest_accrual_convention` day count, by FIX CouponDayCount (1950):
  `30/360` as stated, 30/360 (`DAY_COUNT_THIRTY_360`, the generic value,
  since Terrapin does not say which 30/360); `act/360`, `act/365` (fixed),
  `act/act`, and the three named actual/actuals; `30/365` and RBA bond
  basis have no value and are not offered;
- `minimum_denomination`, `integral_multiple` denomination increment,
  `issued_amount` original issue amount; `is_144a` and `is_regs`;
- `seniority` (CDM's DebtSeniorityEnum, three values): senior, senior
  preferred and senior non-preferred senior; subordinate, junior and
  their kinds subordinated; munis' first and second lien secured; a
  `guarantee` of `secured` secured; anything else not offered;
- `optional_redemption_schedule` calls: a call at principal plus a spread
  over par is `par` (no spread) or `premium` at 100 plus the spread, a
  make-whole `make_whole` with its spread over the benchmark; its
  `call_date` from, `until` to, a continuous call (every day) `continuous`,
  any other period `bermudan`, a single date `one_date`; the notice period
  from munis' `optional_redemption_min_notice` and `_max_notice`. An
  accreted-value or amortized-value call has no kind and is not offered;
- munis: `is_federally_taxable` the federal tax status, `is_amt`,
  `is_state_taxable` (state tax exempt its negation), `is_bank_qualified`;
  `source_of_repayment` General Obligation or Revenue as the security type
  (FIX GO, REV); a corporate `CORP`, a US agency's coupon `FAC`, a US
  Treasury by its terms (a zero bill `TBILL`, an inflation-indexed `TIPS`,
  a floater `FRN`, else a note or a bond by its original term, ten years
  or less a note).

**Not offered, since Terrapin does not state them:** business-day
convention, payment calendar, end-of-month rule, record-date rule, puts'
schedules (it says only whether a bond is puttable), sinking funds outside
munis' mandatory redemption schedule (not yet read: its row shape is not
in the public documentation), a CD's deposit insurance (the FDIC
certificate stays the curator's BankFind source), a floater's index
record, an insurer's or obligor's `ENT-` (no LEI is stated for them).
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import meridian
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.replacements import TemplateCatalogue
from meridian.roles import reference

from . import read

#: How the source is named in an offer's provenance.
SOURCE = "Terrapin"
BOND = "bond"
CD = "certificate_of_deposit"

ISSUER_TYPES = {
    "corporate": "ISSUER_TYPE_CORPORATE",
    "government": "ISSUER_TYPE_SOVEREIGN",
    "government_linked": "ISSUER_TYPE_AGENCY",
    "international_organization": "ISSUER_TYPE_SUPRANATIONAL",
    "state": "ISSUER_TYPE_SUB_SOVEREIGN",
    "municipal": "ISSUER_TYPE_MUNICIPAL",
}
COUPON_TYPES = {
    "fixed rate": "COUPON_TYPE_FIXED",
    "step rate": "COUPON_TYPE_STEP",
    "zero rate / discount rate": "COUPON_TYPE_ZERO",
    "variable rate": "COUPON_TYPE_FLOATING",
}
DAY_COUNTS = {
    "30/360": "DAY_COUNT_THIRTY_360",
    "act/360": "DAY_COUNT_ACT_360",
    "act/365": "DAY_COUNT_ACT_365_FIXED",
    "act/act": "DAY_COUNT_ACT_ACT",
    "act/act (AFB)": "DAY_COUNT_ACT_ACT_AFB",
    "act/act (ICMA)": "DAY_COUNT_ACT_ACT_ICMA",
    "act/act (ISDA)": "DAY_COUNT_ACT_ACT_ISDA",
}
SENIORITIES = {
    "senior": "SENIORITY_SENIOR",
    "senior_preferred": "SENIORITY_SENIOR",
    "senior_non_preferred": "SENIORITY_SENIOR",
    "subordinate": "SENIORITY_SUBORDINATED",
    "senior_subordinate": "SENIORITY_SUBORDINATED",
    "junior": "SENIORITY_SUBORDINATED",
    "junior_subordinate": "SENIORITY_SUBORDINATED",
    "mezzanine": "SENIORITY_SUBORDINATED",
    "first_lien": "SENIORITY_SECURED",
    "second_lien": "SENIORITY_SECURED",
}
REPAYMENT = {"General Obligation": "DEBT_SECURITY_TYPE_GO", "Revenue": "DEBT_SECURITY_TYPE_REV"}
#: A Treasury note's longest original term, in years; longer is a bond.
NOTE_YEARS = 10


@dataclass(frozen=True)
class Offer:
    """One field's value as offered: its path, the value as its type writes
    it, and the rule that worked it out from what Terrapin wrote, empty
    where it is Terrapin's own."""

    path: str
    value: str
    rule: str = ""

    @property
    def top(self) -> str:
        """The template field the path is under (`calls` for `calls[0].kind`)."""
        return self.path.split(".", 1)[0].split("[", 1)[0]

    @property
    def grouped(self) -> bool:
        return self.top != self.path


@dataclass
class Terms:
    """A security's terms as Terrapin states them, mapped: the instrument
    type, what the deployment's record is resolved with, and each offer."""

    isin: str
    figi: str
    instrument_type: str
    currency: str
    description: str
    lei: str
    offers: list[Offer] = field(default_factory=list)
    #: What Terrapin stated that maps to no value, each said once.
    unmapped: list[str] = field(default_factory=list)
    muni: bool = False

    def identifiers(self) -> list[ops.Identifier]:
        """The identifiers the security is resolved by: Terrapin's FIGI where
        it states one (sent to the platform), its ISIN and, for a US or
        Canadian ISIN, the CUSIP it holds (kept on the deployment's record,
        never sent, W3.25)."""
        named = [ops.Identifier(scheme="isin", value=self.isin)]
        cusip = read.cusip_of(self.isin)
        if cusip:
            named.append(ops.Identifier(scheme="cusip", value=cusip))
        if self.figi:
            named.insert(0, ops.Identifier(scheme="figi", value=self.figi))
        return named


def _decimal(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _security_type(item: dict[str, Any], muni: bool) -> tuple[str, str] | None:
    """FIX SecurityType (167) and the rule naming it, where one fits."""
    if muni:
        found = REPAYMENT.get(read.text(item.get("source_of_repayment")))
        return (found, "source_of_repayment") if found else None
    asset = read.text(item.get("asset_class"))
    if asset == "corporate":
        return "DEBT_SECURITY_TYPE_CORP", "asset_class corporate"
    if asset == "us_agency":
        if read.text(item.get("interest_type")) == "zero rate / discount rate":
            return "DEBT_SECURITY_TYPE_FADN", "asset_class us_agency, a discount note"
        return "DEBT_SECURITY_TYPE_FAC", "asset_class us_agency, a coupon"
    if asset == "gov" and read.text(item.get("country_code")) == "US":
        kind = read.text(item.get("interest_type"))
        if kind == "zero rate / discount rate":
            return "DEBT_SECURITY_TYPE_TBILL", "a US Treasury paying no coupon"
        if kind == "variable rate":
            return "DEBT_SECURITY_TYPE_FRN", "a US Treasury paying a floating coupon"
        if "inflation" in read.text(item.get("name")).lower():
            return "DEBT_SECURITY_TYPE_TIPS", "a US Treasury indexed to inflation"
        issued, matures = read.day(item.get("issue_date")), read.day(item.get("maturity_date"))
        if issued and matures:
            years = (matures - issued).days / 365.25
            if years <= NOTE_YEARS + 0.5:
                return "DEBT_SECURITY_TYPE_TNOTE", "a US Treasury of ten years or less at issue"
            return "DEBT_SECURITY_TYPE_TBOND", "a US Treasury of more than ten years at issue"
    return None


def _calls(item: dict[str, Any], unmapped: list[str]) -> list[Offer]:
    """The optional redemption schedule's rows as the template's calls."""
    offers: list[Offer] = []
    rows = item.get("optional_redemption_schedule")
    if not isinstance(rows, list):
        return offers
    low = read.number(item.get("optional_redemption_min_notice"))
    high = read.number(item.get("optional_redemption_max_notice"))
    n = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        said = row.get("call_price")
        price: dict[str, Any] = said if isinstance(said, dict) else {}
        kind = read.text(price.get("type"))
        spread = read.number(price.get("spread_in_bps"))
        from_date = read.day(row.get("call_date"))
        if from_date is None or kind not in ("principal", "make-whole"):
            unmapped.append(f"a call at {kind or 'an unstated price'}")
            continue
        at = f"calls[{n}]"
        if kind == "make-whole":
            offers.append(Offer(f"{at}.kind", "REDEMPTION_KIND_MAKE_WHOLE"))
            if spread is not None:
                offers.append(Offer(f"{at}.make_whole_spread_bps", _decimal(spread)))
        elif spread is None or spread == 0:
            offers.append(Offer(f"{at}.kind", "REDEMPTION_KIND_PAR"))
            offers.append(Offer(f"{at}.price", "100", "principal, no spread over par"))
        else:
            offers.append(Offer(f"{at}.kind", "REDEMPTION_KIND_PREMIUM"))
            offers.append(Offer(f"{at}.price", _decimal(100 + spread / 100),
                                "principal plus the spread over par, in basis points"))  # fmt: skip
        offers.append(Offer(f"{at}.from_date", from_date.isoformat()))
        until = read.day(row.get("until"))
        if until is not None:
            offers.append(Offer(f"{at}.to_date", until.isoformat()))
        period = read.text(row.get("period_type"))
        amount = read.number(row.get("period_amount"))
        if row.get("is_periodic") is True:
            continuous = period == "day" and amount == 1
            style = "REDEMPTION_STYLE_CONTINUOUS" if continuous else "REDEMPTION_STYLE_BERMUDAN"
            offers.append(Offer(f"{at}.style", style, f"is_periodic, every {amount} {period}"))
        elif row.get("is_periodic") is False:
            offers.append(Offer(f"{at}.style", "REDEMPTION_STYLE_ONE_DATE", "is_periodic false"))
        if low is not None:
            offers.append(Offer(f"{at}.notice_days_min", _decimal(low)))
        if high is not None:
            offers.append(Offer(f"{at}.notice_days_max", _decimal(high)))
        n += 1
    return offers


def terms(item: dict[str, Any], *, muni: bool) -> Terms:
    """One security's reference answer as its terms (see the module)."""
    unmapped: list[str] = []
    isin = read.text(item.get("isin"))
    asset = "certificates_of_deposit" if not muni else ""
    asset = read.text(item.get("asset_class")) if not muni else asset
    kind = CD if asset == "certificates_of_deposit" else BOND
    description = read.text(item.get("name")) or read.text(item.get("ticker"))
    if muni and not read.text(item.get("name")):
        series = read.text(item.get("series"))
        issuer = read.text(item.get("issuer_name"))
        description = " ".join(p for p in (issuer, series) if p) or description
    held = Terms(
        isin=isin,
        figi=read.text(item.get("figi")),
        instrument_type=kind,
        currency=read.text(item.get("currency")),
        description=description,
        lei=read.text(item.get("lei")),
        unmapped=unmapped,
        muni=muni,
    )
    offers = held.offers
    if description:
        offers.append(Offer("description", description))
    if held.currency:
        offers.append(Offer("currency", held.currency))
    offers.append(Offer("instrument_type", f"INSTRUMENT_TYPE_{kind.upper()}",
                        "asset_class" if not muni else "muni_reference"))  # fmt: skip
    found_type = _security_type(item, muni)
    if found_type and kind == BOND:
        offers.append(Offer("security_type", found_type[0], found_type[1]))
    issuer_type = "municipal" if muni else read.text(item.get("issuer_type"))
    if issuer_type in ISSUER_TYPES and kind == BOND:
        offers.append(Offer("issuer_type", ISSUER_TYPES[issuer_type],
                            "" if not muni else "muni_reference: a municipal issuer"))  # fmt: skip
    elif issuer_type and issuer_type not in ISSUER_TYPES:
        unmapped.append(f"issuer_type {issuer_type}")
    for source, path in (
        ("issue_date", "issue_date"),
        ("maturity_date", "maturity_date"),
        ("interest_accrual_date", "dated_date"),
        ("first_interest_payment_date", "first_coupon_date"),
    ):
        when = read.day(item.get(source))
        if when is not None and not (kind == CD and path in ("dated_date", "first_coupon_date")):
            offers.append(Offer(path, when.isoformat()))
    coupon_type = COUPON_TYPES.get(read.text(item.get("interest_type")))
    if read.text(item.get("interest_type")) and coupon_type is None:
        unmapped.append(f"interest_type {read.text(item.get('interest_type'))}")
    if coupon_type and kind == BOND:
        offers.append(Offer("coupon_type", coupon_type, "interest_type"))
    rate = read.number(item.get("interest_rate"))
    if rate is not None and coupon_type in (
        "COUPON_TYPE_FIXED",
        "COUPON_TYPE_STEP",
        "COUPON_TYPE_ZERO",
    ):
        offers.append(Offer("coupon_rate", _decimal(rate)))
    frequency = read.number(item.get("coupon_frequency"))
    if frequency is not None:
        offers.append(Offer("coupon_frequency", _decimal(frequency)))
    convention = read.text(item.get("interest_accrual_convention"))
    if convention in DAY_COUNTS:
        offers.append(
            Offer("day_count", DAY_COUNTS[convention], f"interest_accrual_convention {convention}")
        )
    elif convention:
        unmapped.append(f"interest_accrual_convention {convention}")
    if kind == BOND:
        country = read.text(item.get("country_code"))
        if country:
            offers.append(Offer("country_of_issue", country))
        state = read.text(item.get("state"))
        if muni and state:
            offers.append(Offer("state_or_province_of_issue", state))
    for source, path in (
        ("minimum_denomination", "minimum_denomination"),
        ("integral_multiple", "denomination_increment"),
        ("issued_amount", "original_issue_amount"),
    ):
        amount = read.number(item.get(source))
        if amount is not None and not (kind == CD and path != "minimum_denomination"):
            offers.append(Offer(path, _decimal(amount)))
    if kind == BOND:
        for source, path in (("is_144a", "rule_144a"), ("is_regs", "reg_s")):
            if isinstance(item.get(source), bool):
                offers.append(Offer(path, "true" if item[source] else "false"))
        seniority = SENIORITIES.get(read.text(item.get("seniority")))
        if read.text(item.get("guarantee")) == "secured":
            offers.append(Offer("seniority", "SENIORITY_SECURED", "guarantee secured"))
        elif seniority:
            offers.append(Offer("seniority", seniority, f"seniority {item.get('seniority')}"))
        elif read.text(item.get("seniority")):
            unmapped.append(f"seniority {read.text(item.get('seniority'))}")
    offers.extend(_calls(item, unmapped))
    if muni:
        offers.extend(_municipal(item))
    return held


def _municipal(item: dict[str, Any]) -> list[Offer]:
    """The template's municipal group, from Terrapin's municipal fields."""
    found: list[Offer] = []
    taxable = item.get("is_federally_taxable")
    if isinstance(taxable, bool):
        status = "FEDERAL_TAX_STATUS_TAXABLE" if taxable else "FEDERAL_TAX_STATUS_EXEMPT"
        found.append(Offer("municipal.federal_tax_status", status, "is_federally_taxable"))
    for source, path, negated in (
        ("is_amt", "municipal.subject_to_amt", False),
        ("is_state_taxable", "municipal.state_tax_exempt", True),
        ("is_bank_qualified", "municipal.bank_qualified", False),
    ):
        value = item.get(source)
        if isinstance(value, bool):
            said = (not value) if negated else value
            found.append(Offer(path, "true" if said else "false",
                               f"{source}, negated" if negated else ""))  # fmt: skip
    return found


# ── The reference role ────────────────────────────────────────────────────


@dataclass(frozen=True)
class Offered:
    """One record's offer, as Datasets' "Terms offered" lists it."""

    instrument_id: str
    isin: str
    template: str
    offered: int
    skipped: int
    refused: str = ""
    version: int = 0


def person_set(record: ops.InstrumentRecord) -> set[str]:
    """The fields of a record a person set or accepted, by the template's
    paths: never offered over. The record names them by `InstrumentField`
    (description, currency, instrument type, asset class); a debt term a
    person set is not named there, and the store's invariant keeps it over
    any offer (W3's invariant)."""
    return {
        ops.InstrumentField.Name(source.field).removeprefix("INSTRUMENT_FIELD_").lower()
        for source in record.sources
        if source.person
    }


class Reference(reference.Role):
    """The plugin's `reference` role class (SDK 0.35): it reads the template
    catalogue on start, and offers a held security's fields from Terrapin's
    terms (`offer`)."""

    def __init__(self) -> None:
        super().__init__()
        self.catalogue = TemplateCatalogue()
        self.offered: dict[str, Offered] = {}

    async def on_start(self) -> None:
        """The debt templates, read once on start (W3.24)."""
        # Read again when a record names its template, where this fails.
        with contextlib.suppress(meridian.MeridianError):
            await self.catalogue.load(self, asset_class="debt")

    async def offer(
        self,
        instrument_id: str,
        held: Terms,
        issuer_company_id: str,
        raw: ops.RawRecordRef,
    ) -> Offered:
        """Offer `held`'s fields to the record `instrument_id`: read it and
        its template first, then offer each field the template has that no
        person set, its own fields first and its groups after."""
        found = await self.resolve_instrument(instrument_id=instrument_id)
        record = found.instrument
        if not found.found or not record.template_id:
            done = Offered(instrument_id, held.isin, "", 0, 0, "no template named on the record")
            self.offered[instrument_id] = done
            return done
        template = await self.catalogue.template(self, record.template_id, record.template_version)
        if template is None:
            done = Offered(instrument_id, held.isin, record.template_id, 0, 0,
                           "the store holds no such template")  # fmt: skip
            self.offered[instrument_id] = done
            return done
        paths = {f.path for f in template.fields}
        offers = list(held.offers)
        if issuer_company_id:
            offers.append(
                Offer("issuer_company_id", issuer_company_id, "the issuer's LEI, resolved")
            )
        taken = person_set(record)
        kept = [o for o in offers if o.top in paths and o.top not in taken]
        skipped = len(offers) - len(kept)
        version = record.version
        refused = ""
        for part in (
            [o for o in kept if not o.grouped],
            [o for o in kept if o.grouped],
        ):
            if not part:
                continue
            try:
                answer = await self.offer_template_fields(
                    instrument_id=record.instrument_id,
                    template_id=template.template_id,
                    template_version=template.template_version,
                    fields=[_field(o, raw) for o in part],
                )
            except meridian.MeridianError as failed:
                refused = str(failed)[:300]
                continue
            if answer.HasField("instrument"):
                version = answer.instrument.version
        named = f"{template.template_id} v{template.template_version}"
        done = Offered(instrument_id, held.isin, named, len(kept), skipped, refused, version)
        self.offered[instrument_id] = done
        return done


def _field(offer: Offer, raw: ops.RawRecordRef) -> meridian.TemplateFieldValue:
    return meridian.TemplateFieldValue(
        path=offer.path,
        value=offer.value,
        provenance=meridian.Provenance(
            field=offer.path,
            kind="derived" if offer.rule else "reported",
            raw_record=raw,
            source=SOURCE,
            rule=offer.rule[:200],
        ),
    )


def by_path(offers: Iterable[Offer]) -> dict[str, str]:
    return {o.path: o.value for o in offers}


def first(values: Sequence[date | None]) -> date | None:
    return next((v for v in values if v is not None), None)
