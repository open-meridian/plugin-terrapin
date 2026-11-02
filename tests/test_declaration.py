"""The catalogue and settings, from code, as the deployment approves them."""

from __future__ import annotations

from meridian.plugin.v1 import operations_pb2 as ops

from terrapin.declaration import DECLARATION
from terrapin.settings import config_from


def test_three_datasets_and_no_price() -> None:
    catalogue = DECLARATION.catalogue
    assert [d.key for d in catalogue] == [
        "government_curves", "inflation", "msrb_prints",
    ]  # fmt: skip
    for dataset in catalogue:
        assert dataset.vendor == "Terrapin"
        assert [ops.ObservationMode.Name(m) for m in dataset.modes] == [
            "OBSERVATION_MODE_PUSH", "OBSERVATION_MODE_PULL",
        ]  # fmt: skip
        # Terms are the deployment's to settle (rulings 1030 to 1032).
        assert dataset.licence_default is None
        assert "meridian.v1.Price" not in dataset.data_types
    assert [d.day_time_zone for d in catalogue] == [
        "Etc/UTC", "Etc/UTC", "America/New_York",
    ]  # fmt: skip


def test_the_securities_table_keeps_isins_and_cusips() -> None:
    config = config_from({
        "terrapin_api_key": " k ",
        "securities": [{"security": "us005824lp01"}, {"security": "037833ER7"},
                       {"security": "not one"}, {"security": "US005824LP01"}],
        "sample_data": False,
    })  # fmt: skip
    assert config.key == "k"
    assert config.securities == ("US005824LP01", "037833ER7")
