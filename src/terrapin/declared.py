"""What this version declares beside its roles: its catalogue (W10.1,
contract v18), built from code and used twice -- `__main__` registers with
it, and `meridian plugin upload` reads it from the built image.

**Three datasets** (names proposed in the pull request, one per Terrapin
feed):

- `government_curves` -- each region's government par yield curve (US, UK,
  Germany), a `Rate` per tenor (curves.py), each curve its own record; each
  day's pushed when the hourly check reads it, and any past day pulled on a
  want. A point is valid for its curve's date in its region; the dataset's
  day is UTC, the three regions' dates all falling within it;
- `inflation` -- each country's inflation index level by month, a `Rate`
  of kind `index_level`, pushed and pulled, its day UTC;
- `msrb_prints` -- municipal bonds' prints as MSRB disseminates them, read
  through Terrapin, a `Trade` each (trades.py), pushed for the securities
  the deployment lists and pulled on a want, their day New York's.

**No price dataset.** Terrapin's end-of-day prices for government,
corporate and agency bonds are not declared until Terrapin states their
source and whether they are clean or dirty (rulings 871 and 900's R7): the
lake never guesses a basis (decisions/023). The plugin records terms
meanwhile, through its `reference` role.

**No calendar, no venue.** Terrapin's days follow each government bond
market's closes, which no calendar the platform curates holds yet; its
curves and prints are no venue's (a municipal print is reported to MSRB,
not executed on an exchange).

**Terms** are the deployment's to settle with Terrapin (rulings 1030 to
1032): no default licence is declared; docs/terms.md describes Terrapin's
published terms in plain words for the deployment admin, who sets each
dataset's licence on the Data sources page.
"""

from __future__ import annotations

from meridian import DatasetDeclaration

from .curves import CURVES_KEY, INFLATION_KEY
from .trades import MSRB_PRINTS

VENDOR = "Terrapin"
RATE = "meridian.v1.Rate"
TRADE = "meridian.v1.Trade"
#: A day, in seconds; a month, as the inflation indexes are published.
DAY = 86_400
MONTH = 30 * DAY
#: How far back Terrapin's Startup tier reaches: a year.
HISTORY = 365


CURVES = DatasetDeclaration(
    key=CURVES_KEY,
    vendor=VENDOR,
    data_types=[RATE],
    modes=["push", "pull"],
    cadence=DAY,
    history=HISTORY,
    day_time_zone="Etc/UTC",
)


INFLATION = DatasetDeclaration(
    key=INFLATION_KEY,
    vendor=VENDOR,
    data_types=[RATE],
    modes=["push", "pull"],
    cadence=MONTH,
    history=HISTORY,
    day_time_zone="Etc/UTC",
)

TRADES = DatasetDeclaration(
    key=MSRB_PRINTS,
    vendor=VENDOR,
    data_types=[TRADE],
    modes=["push", "pull"],
    cadence=3600,
    history=HISTORY,
    day_time_zone="America/New_York",
)

CATALOGUE = [CURVES, INFLATION, TRADES]
