# Changelog

## 0.2.0

On open-meridian 0.36.0, contract 30, on core aae501d's harness (chart
0.1.538); `meridian` 0.1.60 in the check. What the plugin records is
unchanged.

- **Terrapin's terms in words** (ruling 1032): each dataset's
  `terms_and_pricing` summarises Terrapin's published terms as
  docs/terms.md does (internal or personal use by tier, self-serve tiers
  non-commercial, no redistribution, no model training on self-serve tiers,
  the Startup tier's subscription and quotas, Enterprise by agreement) and
  its source for that feed, shown on Data sources and in the Datasets
  page's row details. The plugin still declares no licence.
- **A gap recovered by backfill** (`gap_recovery`): Terrapin serves each
  feed's history, a year on the Startup tier, read again on a want. No
  `sessions_calendar_id`: MSRB's reporting hours are no calendar the
  platform curates yet, and curves and inflation are published daily or
  monthly.
- **Row keys checked against the lake's rule 5** (ruled 2026-11-12): curves
  and inflation go through the SDK's `rates.Feed`, keyed by their day and
  record. A municipal print is keyed by its ISIN and Terrapin's trade ID
  (`msrb:<ISIN>:<id>`), valid at its trade time; a print Terrapin marks
  cancelled is the same key's next version, `cancelled`. An MSRB
  modification that moves a print's time of trade would restate the key
  under another valid time; the plugin holds no earlier version to cancel.
  Listed for step 3d, unchanged.
- `meridian plugin migrate --to 0.36.0` moved the pins (the base by
  digest, `meridian` 0.1.60); the test of the absent licence reads the
  words instead.
- Core's runtime and harness images at `aae501d`, by digest.

## 0.1.0

The first version, on open-meridian 0.35.3 (contract v29), built from
Terrapin's public API documentation (rulings 868, 869, 1059).

- `data`: each region's government par yield curve (`government_curves`:
  US, UK, Germany), each country's inflation index level (`inflation`) and
  municipal bonds' MSRB prints (`msrb_prints`), with the fixed-income trade
  characteristics and the price per 100 of par; a print Terrapin marks
  cancelled recorded again as withdrawn. Terrapin's own curves and indexes
  are local records, their rates recorded once a person accepts them.
- `reference`: the listed bonds' and CDs' terms offered to the deployment's
  records under the `bond` and `certificate_of_deposit` templates, the
  issuer's LEI resolved to its `ENT-` company record, each value with its
  provenance; a person's value never offered over.
- Not recorded until Terrapin answers (ruling 871): its end-of-day prices
  (source and clean or dirty not stated, 900's R7), its zero curve
  (compounding not stated); its benchmark curve, whose points name no
  maturity; a print's capacity and traded flat (900's R4), and its yield
  (day count not stated).
- No default licence declared (rulings 1030 to 1032): docs/terms.md describes
  Terrapin's published terms in plain words.
