"""The plugin's pages, as an admin of the plugin sees them through the
deployment's dashboard: the data role's common pages
(spec/plugin-pages-follow-their-role), built on `meridian.roles.data`.

A data plugin shows its connection and its datasets, never a value: rates
and prints are the reading roles' to show. So both pages are at `admin` of
the `data` role (a person's level is granted per role, contract v15), under
the dashboard's Manage, in the role's order:

- Connection (/): "Key", "Limits and use" and "Stream", from
  `ConnectionRead`; Terrapin's own row "Securities" in "Key" -- each listed
  security, the record it resolved to, its issuer's company record and how
  many of its terms were offered (the `reference` role);
- Datasets (/datasets): "Served", "Wants" and "Subjects", from
  `DatasetsRead`, with a notice of what Terrapin stated that was not
  recorded, and the curves' and indexes' records.

Each page declares the record it renders (`answers=`), so it is also a read
tool on the deployment's MCP surface: `read_connection` and
`read_datasets`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import meridian
from meridian.roles import data

if TYPE_CHECKING:
    from .lake import Lake

TITLE = "Terrapin"
#: The key's label, as the settings declare it.
KEY_LABEL = "Terrapin API key"

pages = meridian.Pages(TITLE, templates=Path(__file__).parent / "templates")

#: The running data role's class, which __main__.py gives the pages.
running: list[Lake] = []


def hold(lake: Lake) -> None:
    running[:] = [lake]


@dataclass(frozen=True)
class SecurityRead:
    """One listed security, as "Securities" lists it."""

    security: str
    description: str = ""
    record: str = ""
    issuer: str = ""
    offered: int = 0
    refused: str = ""
    #: Why it has no record, where the deployment answered none.
    miss: str = ""


@dataclass(frozen=True)
class ConnectionRead(data.ConnectionRead):
    """Connection's common fields, then Terrapin's: each listed security."""

    securities: list[SecurityRead] = field(default_factory=list)
    checked_at: str = ""
    #: Why no price is recorded (rulings 871, 900's R7).
    prices: str = ""


@dataclass(frozen=True)
class RecordRead:
    """A curve's or an index's record, by Terrapin's code for it, and the
    dataset its rows are recorded under."""

    dataset: str
    code: str
    record: str


@dataclass(frozen=True)
class DatasetsRead(data.DatasetsRead):
    """Datasets' common fields, then Terrapin's: the curves' and indexes'
    records, and what was stated but not recorded, each with its count."""

    served: list[data.Served] = field(default_factory=list)
    wants: list[data.WantHeard] = field(default_factory=list)  # type: ignore[assignment]
    records: list[RecordRead] = field(default_factory=list)
    not_recorded: list[str] = field(default_factory=list)


#: Why the plugin declares no price dataset (rulings 871, 900's R7).
PRICES = (
    "Terrapin's end-of-day prices are not recorded until Terrapin states their source "
    "and whether they are clean or dirty."
)


def mode(lake: Lake) -> str:
    if lake.source.mode == "synthetic":
        return "Sample data"
    return "Live" if lake.has_key else "No key"


def _held(record: str) -> str:
    return record if record.startswith(("INS-", "LCL-")) else ""


def connection_read(lake: Lake) -> ConnectionRead:
    source = lake.source
    return ConnectionRead(
        mode=mode(lake),
        credentials=[data.Credential(KEY_LABEL, lake.has_key)],
        entitled_at_vendor=f"{len(lake.securities)} securities listed",
        limit=f"{source.limit} a minute",
        calls=source.calls,
        rate_limited=source.rate_limited,
        last_call_at=source.last_call_at,
        last_error=source.failed or lake.status.last_error,
        sessions=None,
        securities=[
            SecurityRead(
                security=isin,
                description=row.get("description", ""),
                record=_held(row.get("record", "")),
                miss="" if _held(row.get("record", "")) else row.get("record", ""),
                issuer=row.get("issuer", ""),
                offered=int(row.get("offered", "0") or 0),
                refused=row.get("refused", ""),
            )
            for isin, row in sorted(lake.status.securities.items())
        ],
        checked_at=lake.status.checked_at,
        prices=PRICES,
    )


def datasets_read(lake: Lake) -> DatasetsRead:
    from .declaration import DECLARATION

    instance = lake.plugin.identity.instance_id if lake._role_plugin is not None else ""
    said = {**lake.status.unread, **lake.status.not_recorded}
    return DatasetsRead(
        served=data.served(DECLARATION.catalogue, instance, lake.wants,
                           f"{len(DECLARATION.catalogue)} datasets"),
        wants=list(data.want_rows(lake.wants)),
        records=[
            RecordRead(_dataset_of(instance, code), code, record)
            for code, record in sorted(lake.status.records.items())
        ],
        not_recorded=[f"{what} ({n})" for what, n in sorted(said.items())],
    )  # fmt: skip


def _dataset_of(instance: str, code: str) -> str:
    """The dataset a record's rows are under, by Terrapin's code for it."""
    from .curves import CURVES_KEY, INFLATION_KEY

    key = CURVES_KEY if code.endswith("_PAR") else INFLATION_KEY
    return f"{instance}:{key}"


def _lake() -> Lake:
    if running:
        return running[0]
    from .lake import Lake

    return Lake()


@pages.page(
    "/",
    "Connection",
    levels="admin",
    roles=["data"],
    answers=ConnectionRead,
    name="read_connection",
)
async def connection(request: meridian.Request) -> meridian.Response:
    """Whether Terrapin answers, what was asked of it, and each listed
    security's record and terms."""
    return pages.answer("connection.html", connection_read(_lake()))


@pages.page(
    "/datasets",
    "Datasets",
    levels="admin",
    roles=["data"],
    answers=DatasetsRead,
    name="read_datasets",
)
async def datasets(request: meridian.Request) -> meridian.Response:
    """Each dataset this plugin serves the lake, whether it is licensed, the
    wants it answered, and its curves' and indexes' records."""
    return pages.answer("datasets.html", datasets_read(_lake()))


def figures(lake: Lake) -> list[meridian.Figure]:
    """The data role's figures, in its order."""
    source = lake.source
    return data.figures(
        connection=mode(lake) if mode(lake) != "Live" else (
            "Not answering" if source.failed else "Answering"),
        entitled_at_vendor=f"{len(lake.securities)} securities listed",
        stream="Does not stream",
        last_recorded=lake.status.checked_at or "None yet",
        rate_use=f"{source.calls} calls, {source.limit} a minute",
    )  # fmt: skip
