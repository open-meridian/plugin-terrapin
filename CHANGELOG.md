# Changelog

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
