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
1032): each dataset describes Terrapin's published terms in words
(`terms_and_pricing`, contract 30), as docs/terms.md does, for the
deployment admin, who sets each dataset's licence on the Data sources page.
**A gap** is recovered by `backfill` (`gap_recovery`): Terrapin serves each
feed's history, read again on a want.
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
#: Terrapin's published terms in plain words (contract 30, ruling 1032), as
#: read on 30 October 2026 (terrapinfinance.com/terms, updated 29 October
#: 2026): docs/terms.md, shortened.
TERMS = (
    "Terrapin Finance Ltd's data, under your subscription: use for internal business "
    "purposes or personal use as your tier specifies. The self-serve tiers (Starter, Build, "
    "Startup) are for personal, development and non-commercial use: no commercial products, "
    "client-facing applications or reports, or production systems such as trading or risk; "
    "commercial and production use is under an Enterprise agreement. No redistribution, "
    "resale, sublicensing or third-party access beyond the AI use Terrapin permits; no "
    "caching beyond the tier's legitimate use; no competing or (on self-serve tiers) "
    "production derived products; no training models on the data on self-serve tiers; "
    "credit Terrapin where display is permitted. Pricing: the Startup tier is a monthly "
    "subscription with monthly quotas of distinct and search ISINs, a year of history and "
    "a request rate limit; Enterprise is by agreement."
)
SOURCES = {
    "curves": " Its government curves are its own construction from benchmark bonds' "
    "end-of-day prices.",
    "inflation": "",
    "msrb": " Its municipal prints come from MSRB's post-trade feeds, and MSRB's terms "
    "for its data may apply alongside Terrapin's.",
}


CURVES = DatasetDeclaration(
    key=CURVES_KEY,
    vendor=VENDOR,
    data_types=[RATE],
    modes=["push", "pull"],
    cadence=DAY,
    history=HISTORY,
    day_time_zone="Etc/UTC",
    terms_and_pricing=TERMS + SOURCES["curves"],
    gap_recovery="backfill",
)


INFLATION = DatasetDeclaration(
    key=INFLATION_KEY,
    vendor=VENDOR,
    data_types=[RATE],
    modes=["push", "pull"],
    cadence=MONTH,
    history=HISTORY,
    day_time_zone="Etc/UTC",
    terms_and_pricing=TERMS + SOURCES["inflation"],
    gap_recovery="backfill",
)

TRADES = DatasetDeclaration(
    key=MSRB_PRINTS,
    vendor=VENDOR,
    data_types=[TRADE],
    modes=["push", "pull"],
    cadence=3600,
    history=HISTORY,
    day_time_zone="America/New_York",
    terms_and_pricing=TERMS + SOURCES["msrb"],
    gap_recovery="backfill",
)

CATALOGUE = [CURVES, INFLATION, TRADES]
