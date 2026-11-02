"""The two pages under Manage, and their read tools: what each shows, to
whom, and that a tool answers what its page shows."""

from __future__ import annotations

import asyncio

import pytest
from meridian.suites import Recorder
from meridian.testing import PageClient

from terrapin.page import figures, hold, pages

from conftest import APPLE, MUNI, holding, lake, want


@pytest.fixture
def client() -> PageClient:
    recorder = Recorder("terrapin")
    holding(recorder)
    work = lake(recorder)

    async def run() -> None:
        await work.check()
        record = work.records[MUNI]
        await work.on_observations_wanted(want("w-1", "msrb_prints", [record], day="2026-10-27"))

    asyncio.run(run())
    hold(work)
    return PageClient(pages, recorder.plugin, roles=("data", "reference"))


def test_each_page_is_managed_alone(client: PageClient) -> None:
    served = {(r.page.path, r.level): r.response.status for r in client.every_page()}
    assert {level: status for (_, level), status in served.items()} == {
        "admin": 200, "write": 403, "read": 403,
    }  # fmt: skip
    # No rate, price or yield on any page: they are the reading roles'.
    client.assert_no_account_data("4.109", "108.902", "3.4447", "329.932")


def test_connection_lists_the_securities_and_their_terms(client: PageClient) -> None:
    text = client.get("/", "admin").text
    assert text.index("<h2>Key</h2>") < text.index('<th scope="row">Securities</th>')
    assert text.index('<th scope="row">Securities</th>') < text.index("<h2>Limits and use</h2>")
    assert "6 of 6 resolved" in text and "Sample data" in text
    assert APPLE in text and "terms offered" in text and "Does not stream" in text
    assert "/.meridian/ui/" in text
    assert "not recorded until Terrapin states their source" in text


def test_datasets_lists_each_dataset_and_its_records(client: PageClient) -> None:
    text = client.get("/datasets", "admin").text
    for key in ("government_curves", "inflation", "msrb_prints"):
        assert f"<code>terrapin:{key}</code>" in text
    assert "LCL-" in text or "INS-" in text


def test_the_tools_answer_what_the_pages_show(client: PageClient) -> None:
    connection = client.call_tool("read_connection").data
    assert connection["mode"] == "Sample data"
    assert [s["security"] for s in connection["securities"]] == sorted(
        s["security"] for s in connection["securities"]
    )
    assert connection["credentials"] == [{"label": "Terrapin API key", "set": True}]
    datasets = client.call_tool("read_datasets").data
    assert [s["dataset"] for s in datasets["served"]] == [
        f"terrapin:{k}" for k in ("government_curves", "inflation", "msrb_prints")
    ]
    assert {r["code"] for r in datasets["records"]} >= {"TERRAPIN_US_PAR", "TERRAPIN_US_INFLATION"}


def test_the_figures_are_the_role_s() -> None:
    recorder = Recorder("terrapin")
    work = lake(recorder)
    labels = [f.label for f in figures(work)]
    assert labels[:5] == [
        "Connection", "Entitled at the vendor", "Stream", "Last recorded", "Rate use",
    ]  # fmt: skip
