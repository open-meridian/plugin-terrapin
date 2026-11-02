# Overview

## What it is

Terrapin (terrapinfinance.com) publishes bond reference data and prices
through a JSON API: government, corporate, US agency and municipal bonds and
certificates of deposit, government yield curves and inflation indexes. This
plugin reads that API with the deployment's own Terrapin key and holds two
roles, `data` and `reference`.

## What it records

- **`data`** -- records into the deployment's lake:
  - each region's **government par yield curve** (US, UK, Germany), a rate
    per tenor, the curve one record of the deployment's;
  - each country's **inflation index** level by month (US, UK, Germany,
    France, Italy, Spain, Canada), as its statistics office publishes it;
  - **municipal bonds' prints** as MSRB disseminates them, for the bonds you
    list and any a reader wants: the price per 100 of par, the face amount,
    the yield to maturity, and MSRB's flags as the platform's trade
    characteristics (customer or inter-dealer, ATS, when issued, list
    offering price or takedown, non-transaction compensation); a print
    Terrapin marks cancelled is recorded again as withdrawn.
## What it offers

- **`reference`** -- offers the **terms** of the bonds and CDs you list to
  your deployment's instrument records, field by field, each with where it
  came from: the issuer (its LEI resolved to your company record), dates,
  coupon and frequency, day count, denominations, amount issued, seniority,
  Rule 144A and Regulation S, the call schedule with make-whole spreads and
  notice periods, and for a municipal bond its tax status and bank
  qualification. An offer is never a decision: a value is used once a person
  accepts it at the Instruments page, and a value a person set is never
  offered over.

## What it does not record

- **Prices.** Terrapin's end-of-day prices for government, corporate and
  agency bonds are not recorded until Terrapin states where they come from
  and whether they are clean or dirty: a dirty price read as clean would
  misstate a value by its accrued interest, and the lake never guesses.
- **Zero and benchmark curves.** A zero rate's compounding is the curve
  builder's choice, which Terrapin does not state; a benchmark point's
  maturity is a fraction of a year with no bond named. Neither is recorded
  until Terrapin states it.
- **A print's dealer capacity and traded-flat flag**, which Terrapin's prints
  do not carry; no flag listed means none stated, never "a regular trade".
- **Official statements, municipal events, issuance statistics and cash
  flows**, which no kind of the lake holds yet.
- **Mortgage pools, TBAs and CMOs**, which Terrapin does not cover: the
  agencies' own disclosure plugins are their source.

## Records

It never mints a record: what your deployment does not hold is reported as a
miss and recorded once it resolves. A bond known only by its CUSIP or ISIN is
kept as a local record of your deployment, its CUSIP kept there and never
sent anywhere.
