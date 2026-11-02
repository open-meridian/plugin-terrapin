"""Terrapin's government curves and inflation factors, as the lake's rates.

**A curve is one record and its points are rows**, every region's under
one dataset, `government_curves`` (the lake's rates slice,
`meridian.roles.data.rates`): each region's par curve is one referential
record of type `rate_curve`, named by Terrapin's own code for it under the
source `terrapin` (`TERRAPIN_US_PAR`), a vendor's code, so the deployment
keeps it local and never sends it (W3.25); each point is a `Rate` of kind
`par_yield` with its tenor.

**Which curves are recorded.** Terrapin's `government_yield_curve` answers
three types for the US, the UK and Germany:

- `par` -- par yields at exact tenors, derived from its zero curve. A par
  yield is by definition the coupon at which a bond of the market prices at
  par, so its convention is the market's coupon convention: semi-annual on
  actual/actual for US Treasuries and UK gilts, annual on actual/actual
  (ICMA) for German Bunds. Recorded.
- `zero` -- zero rates at exact tenors, bootstrapped by monotone convex
  interpolation. Terrapin does not state their compounding or day count,
  and a zero rate's convention is the curve builder's choice, not the
  market's: until Terrapin states it (asked, ruling 871), they are not
  recorded, since the lake never guesses a convention (decisions/023).
- `benchmark` -- the benchmark bonds' yields beside their years to maturity
  as a fraction (9.8 years). A fraction of a year is no tenor, and the
  answer names no bond, so a point has neither a tenor nor a maturity to
  record: not recorded, said on the Datasets page.

A par point's years to maturity is read as a whole number of years (`10Y`)
or of months (`0.5` years is `6M`); any other is not recorded and said.

**Inflation factors** (`inflation_factors`) are a country's price index
level by month, as its statistics office publishes it (BLS for the US, ONS
for the UK, Eurostat for the euro countries): each a `Rate` of kind
`index_level`, its value an `index`, under the record
`TERRAPIN_<country>_INFLATION`. A price index compounds nothing; the lake
requires every rate's convention, so an index level carries the convention
its daily value is read with by the bonds it indexes -- linear on the
actual days of the month (the TIPS reference CPI, 31 CFR 356 Appendix B;
the euro linkers' daily index ratio alike): actual/actual, simple.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from meridian.operations import RateConvention
from meridian.roles.data import rates

#: The source a vendor's code for one of its own records is scoped to.
SOURCE = "terrapin"

#: The par convention of each region's government bonds.
SEMI_ANNUAL = rates.BOND_EQUIVALENT
ANNUAL_ICMA = RateConvention(day_count="act_act_icma", compounding="compounded", periods_per_year=1)
#: An index level's daily value: linear on the actual days of the month.
INDEX_DAILY = RateConvention(day_count="act_act", compounding="simple")


#: The dataset every region's par curve is recorded under.
CURVES_KEY = "government_curves"


@dataclass(frozen=True)
class Region:
    """One of Terrapin's curve regions: Terrapin's region code, the curve's
    record, its currency, the day its business date is in (each point valid
    for that day there), and its par convention."""

    code: str
    name: str
    currency: str
    day_zone: str
    convention: RateConvention

    @property
    def symbol(self) -> str:
        return f"TERRAPIN_{self.code.upper()}_PAR"

    @property
    def description(self) -> str:
        return f"Terrapin {self.name} government par yield curve"


US = Region("us", "US", "USD", "America/New_York", SEMI_ANNUAL)
UK = Region("uk", "UK", "GBP", "Europe/London", SEMI_ANNUAL)
DE = Region("de", "German", "EUR", "Europe/Berlin", ANNUAL_ICMA)
REGIONS: tuple[Region, ...] = (US, UK, DE)
BY_CODE = {region.code: region for region in REGIONS}

#: The countries whose inflation factors Terrapin publishes, each with the
#: currency its record is stated in.
INFLATION_COUNTRIES = {
    "US": "USD",
    "UK": "GBP",
    "DE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "ES": "EUR",
    "CA": "CAD",
}
INFLATION_KEY = "inflation"


def inflation_symbol(country: str) -> str:
    return f"TERRAPIN_{country.upper()}_INFLATION"


def inflation_description(country: str, publisher: str) -> str:
    said = f" ({publisher})" if publisher else ""
    return f"Terrapin {country.upper()} inflation index{said}"


def tenor_of(years: Decimal) -> str | None:
    """A point's years to maturity as a tenor label: whole years (`10Y`),
    else whole months (`6M`); None for any other fraction."""
    if years <= 0:
        return None
    if years == years.to_integral_value():
        return f"{int(years)}Y"
    months = years * 12
    if months == months.to_integral_value():
        return f"{int(months)}M"
    return None
