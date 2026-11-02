"""The plugin's settings, declared to the SDK, and what it makes of them.

In the data role's order (spec/plugin-pages-follow-their-role): no
`environment` (Terrapin has one API); the credential; the plugin's own;
then the role's sample data.

- `terrapin_api_key` -- the deployment's Terrapin API key, a secret, made
  in Terrapin's app. Without it nothing is asked of Terrapin. Set through
  the dashboard's Settings form, never read back, displayed, logged or put
  in a page; an agent never types it.
- `securities` -- the securities whose terms are offered to the
  deployment's records and, for municipal bonds, whose prints are kept
  current: a typed table, one column, each an ISIN or a CUSIP. Terrapin
  counts the distinct ISINs a key asks for each month against its tier's
  quota, so a deployment lists what it holds or watches. A security not
  listed is read when the lake wants it.
- `sample_data` -- a developer's setting: the answers committed under
  sample/ in place of Terrapin, for the e2e and for trying the plugin
  without a key.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import meridian

from . import read

API_KEY = "terrapin_api_key"
SECURITIES = "securities"
#: The table's one column: a security's ISIN or CUSIP.
SECURITY_COLUMN = "security"
SAMPLE_DATA = "sample_data"
#: The most securities listed.
MOST_SECURITIES = 500


@meridian.settings
class Declared:
    """The settings as declared, in the data role's order."""

    terrapin_api_key: str = meridian.setting(
        "Terrapin API key",
        secret=True,
        description=(
            "The deployment's Terrapin API key, made in Terrapin's app (API keys). "
            "Without it the plugin asks Terrapin nothing."
        ),
    )
    securities: list = meridian.setting(  # type: ignore[type-arg]
        "Securities",
        description=(
            "The bonds and CDs whose terms Terrapin offers to the deployment's records, "
            "and whose municipal prints are kept current. Terrapin counts each distinct "
            "ISIN asked for in a month against the key's quota."
        ),
        columns=[
            meridian.Column(
                SECURITY_COLUMN,
                kind="text",
                label="ISIN or CUSIP",
                required=True,
                description="The security's ISIN, or its nine-character CUSIP",
            )
        ],
        most_rows=MOST_SECURITIES,
    )
    sample_data: bool = meridian.sample_data(
        description=(
            "Serve the answers committed with the plugin, made in the shape of Terrapin's "
            "public documentation, instead of asking Terrapin: curves, inflation factors, "
            "terms and municipal prints to 30 October 2026. No key needed. Development "
            "deployments only."
        )
    )


DECLARED = Declared


@dataclass(frozen=True)
class Config:
    key: str = field(default="", repr=False)
    securities: tuple[str, ...] = ()
    sample_data: bool = False


def _securities(rows: object) -> tuple[str, ...]:
    """The table's securities, each an ISIN or a CUSIP, once each, in the
    table's order; a cell that is neither is left out."""
    held: list[str] = []
    if not isinstance(rows, Sequence) or isinstance(rows, str):
        return ()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        said = str(row.get(SECURITY_COLUMN, "")).strip().upper()
        if (read.is_isin(said) or read.isin_of(said)) and said not in held:
            held.append(said)
    return tuple(held)


def config_from(values: Mapping[str, object]) -> Config:
    """The configuration a delivery of the settings says."""
    key = values.get(API_KEY)
    return Config(
        key=key.strip() if isinstance(key, str) else "",
        securities=_securities(values.get(SECURITIES)),
        sample_data=values.get(SAMPLE_DATA) is True,
    )
