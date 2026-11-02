"""Terrapin's API as the plugin asks it: the key, the pacing, a 429, and
the stand-in's answers."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from terrapin import client, read
from terrapin.client import LiveTerrapin, NoKey, policy_limit

from conftest import AT, MUNI, source


def test_the_policy_header_sets_the_limit() -> None:
    assert policy_limit("25;w=60") == 25
    assert policy_limit("100;w=60, 5000;w=86400") == 100
    assert policy_limit("") is None and policy_limit("10;w=1") is None


def test_no_key_asks_nothing() -> None:
    with pytest.raises(NoKey):
        asyncio.run(LiveTerrapin("").post("muni_reference", {"isins": [MUNI]}))


def test_a_429_is_waited_out_and_the_key_never_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    live = LiveTerrapin("secret-key", lambda: AT)
    said: list[tuple[str, dict[str, Any]]] = []

    def post(endpoint: str, body: dict[str, Any]) -> tuple[client.Fetched, dict[str, str]]:
        said.append((endpoint, body))
        text = '{"detail": "Too many requests for secret-key"}'
        got = client.Fetched(endpoint, body, 429, client.redacted(text, "secret-key"), AT)
        return got, {"retry-after": "7", "ratelimit-policy": "30;w=60"}

    monkeypatch.setattr(live, "_post", post)
    got = asyncio.run(live.post("muni_reference", {"isins": [MUNI]}))
    assert got.status == 429 and live.rate_limited == 1 and live.limit == 30
    assert "secret-key" not in got.body and "secret-key" not in got.error
    assert live._not_before > 0 and live.failed


def test_the_stand_in_answers_in_terrapin_s_shape() -> None:
    sample = source()
    asked = {"isin": MUNI, "start_date": "2026-10-27", "end_date": "2026-10-28"}
    got = asyncio.run(sample.post("muni_pricing_history", asked))
    items = read.items(got.body)
    assert [i["id"] for i in items] == ["sB7c2Lr1Q0eV0m0pXl2a1w", "sC3d9Pq8RkuW2n4tYb7c5g"]
    assert json.loads(got.body)["total"] == 2
    missing = asyncio.run(sample.post("securities_reference", {"isins": [MUNI]}))
    assert read.items(missing.body) == []


def test_identifiers_read_from_an_isin() -> None:
    assert read.cusip_of("US037833ER75") == "037833ER7"
    assert read.isin_of("037833ER7") == "US037833ER75"
    assert read.is_isin("US005824LP01") and not read.is_isin("US005824LP02")
    assert read.cusip_of("XS2724510792") == ""
