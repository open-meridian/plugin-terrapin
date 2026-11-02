# Setup

## Before launching

You need a Terrapin API key, made in Terrapin's app under API keys, on the
subscription your use calls for (see [Terms](terms.md)). Terrapin counts the
distinct ISINs a key asks for each month against its tier's quota.

## Launching it

Launch the plugin and approve its two roles, `data` and `reference`. In the
dashboard's Settings form:

- **Terrapin API key** -- the key, a secret: never shown again, logged or put
  on a page. Without it the plugin asks Terrapin nothing.
- **Securities** -- the bonds and CDs whose terms are offered to your
  records and whose municipal prints are kept current, one ISIN or CUSIP a
  row, up to 500. List what you hold or watch: each is asked of Terrapin's
  quota once a month.
- **Sample data**, on a deployment installed for development only: answers
  committed with the plugin, in the shape of Terrapin's public
  documentation, in place of Terrapin. For trying it without a key.

It reads Terrapin at once and every hour after: the last five business days'
curves and the listed bonds' prints of the last seven days; the inflation
indexes and the listed securities' terms once a day, or at once when the
list changes.

## Its datasets

On the deployment's **Data sources** page (deployment admins):

1. **License** `<instance>:government_curves`, `inflation` and
   `msrb_prints` on the terms your Terrapin agreement gives you. The
   plugin declares no default terms: they are yours and Terrapin's to settle.
2. **Entitle** each plugin that reads them.
3. **Priority**, where another dataset also records a curve's points or a
   bond's prints: put first the one your readers should read.

## Records

Each curve and inflation index is one record of your deployment, named by
Terrapin's code for it (`TERRAPIN_US_PAR`, `TERRAPIN_US_INFLATION`) and kept
local: they are Terrapin's own, no record the platform curates. The plugin
states each one's class (referential), type (a rate curve or an index),
currency and description; **accept them at the Instruments page** before
its rates are recorded. Until then the Datasets page says each waits, and
the plugin reads it again every hour. Each listed security is resolved by its FIGI where Terrapin states
one, else its ISIN and CUSIP, with Terrapin's description and currency. Its
offered terms wait at the **Instruments** page for a person to accept.
