"""Verification: official weather field, unit, time, and missing-data contracts."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nexusep.abbey.building.physics.solar import calculate_solar_position
from nexusep.abbey.building.physics.weather import (
    WeatherSourceMetadata,
    _make_epw_datetimes,
)
from nexusep.validation_data.weather_ingestion import (
    NORMALIZED_COLUMNS,
    parse_nasa_power_hourly_json,
    parse_nsrdb_psm3_csv,
    parse_pvgis_hourly_json,
    radiation_component_residual_w_m2,
)

FIXTURES = Path(__file__).parents[2] / "data" / "validation" / "fixtures"


@pytest.mark.parametrize(
    ("filename", "parser"),
    [
        ("pvgis_hourly_sample.json", parse_pvgis_hourly_json),
        ("nasa_power_hourly_sample.json", parse_nasa_power_hourly_json),
    ],
)
def test_official_fixture_field_unit_and_timestamp_mapping(filename, parser) -> None:
    fixture = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
    result = parser(fixture["source_payload"])
    expected = fixture["expected"]
    assert result.time_semantic == expected["time_semantic"]
    assert result.source_timezone == expected["source_timezone"]
    assert result.missing_canonical_fields == tuple(
        expected["missing_canonical_fields"]
    )
    assert result.derived_fields == tuple(expected["derived_fields"])
    expected_frame = pd.DataFrame.from_records(
        expected["records"], columns=NORMALIZED_COLUMNS
    )
    expected_frame["timestamp_utc"] = pd.to_datetime(
        expected_frame["timestamp_utc"], utc=True
    )
    for column in expected_frame.columns.drop("timestamp_utc"):
        expected_frame[column] = pd.to_numeric(expected_frame[column])
    pd.testing.assert_frame_equal(result.data, expected_frame, check_dtype=False)


def test_pvgis_sarah_is_not_mislabeled_as_hourly_average() -> None:
    fixture = json.loads(
        (FIXTURES / "pvgis_hourly_sample.json").read_text(encoding="utf-8")
    )
    result = parse_pvgis_hourly_json(fixture["source_payload"])
    assert result.time_semantic == "instantaneous_sample"
    assert result.source_timezone == "UTC"
    assert result.data["timestamp_utc"].dt.minute.nunique() == 1
    assert result.data["timestamp_utc"].dt.minute.iloc[0] == 10


def test_pvgis_horizontal_radiation_components_close_exactly() -> None:
    fixture = json.loads(
        (FIXTURES / "pvgis_hourly_sample.json").read_text(encoding="utf-8")
    )
    payload = fixture["source_payload"]
    result = parse_pvgis_hourly_json(payload)
    for source_row, (_, normalized) in zip(
        payload["outputs"]["hourly"], result.data.iterrows(), strict=True
    ):
        expected_ghi = source_row["Gb(i)"] + source_row["Gd(i)"] + source_row["Gr(i)"]
        assert normalized["global_horizontal_radiation_w_m2"] == pytest.approx(
            expected_ghi, abs=1e-12
        )


def test_nasa_hourly_mean_components_have_bounded_midpoint_residual() -> None:
    fixture = json.loads(
        (FIXTURES / "nasa_power_hourly_sample.json").read_text(encoding="utf-8")
    )
    result = parse_nasa_power_hourly_json(fixture["source_payload"])
    zenith = [
        calculate_solar_position(
            timestamp.to_pydatetime() + timedelta(minutes=30),
            latitude_deg=45.0,
            longitude_deg=8.0,
        ).zenith_deg
        for timestamp in result.data["timestamp_utc"]
    ]
    residual = radiation_component_residual_w_m2(result.data, zenith)
    # Component means are calculated independently. This is a plausibility
    # tolerance for the fixed official fixture, not an equality assertion.
    assert residual.abs().max() < 20.0


def test_nasa_power_lst_response_is_rejected_on_utc_path() -> None:
    fixture = json.loads(
        (FIXTURES / "nasa_power_hourly_sample.json").read_text(encoding="utf-8")
    )
    fixture["source_payload"]["header"]["time_standard"] = "LST"
    with pytest.raises(ValueError, match="LST is not a civil timezone"):
        parse_nasa_power_hourly_json(fixture["source_payload"])


def test_missing_values_are_masked_not_filled() -> None:
    fixture = json.loads(
        (FIXTURES / "nasa_power_hourly_sample.json").read_text(encoding="utf-8")
    )
    first_key = next(
        iter(fixture["source_payload"]["properties"]["parameter"]["T2M"])
    )
    fixture["source_payload"]["properties"]["parameter"]["T2M"][first_key] = -999.0
    result = parse_nasa_power_hourly_json(fixture["source_payload"])
    assert np.isnan(result.data.loc[0, "outdoor_temperature_c"])


def test_nsrdb_schema_and_fixed_offset_round_trip() -> None:
    csv_text = (
        "Source,Location ID,Time Zone,Elevation\n"
        "NSRDB,123,-7,1600\n"
        "Year,Month,Day,Hour,Minute,Temperature,Relative Humidity,Pressure,"
        "Wind Speed,Wind Direction,DNI,DHI,GHI\n"
        "2020,6,21,12,0,25,20,82000,3,180,800,100,700"
    )
    result = parse_nsrdb_psm3_csv(csv_text)
    assert result.data.loc[0, "timestamp_utc"].isoformat() == "2020-06-21T19:00:00+00:00"
    assert result.data.loc[0, "relative_humidity_fraction"] == 0.2
    assert result.data.loc[0, "atmospheric_pressure_pa"] == 82_000.0


def test_source_unit_metadata_mismatch_fails_loudly() -> None:
    fixture = json.loads(
        (FIXTURES / "pvgis_hourly_sample.json").read_text(encoding="utf-8")
    )
    fixture["source_payload"]["meta"]["outputs"]["hourly"]["variables"][
        "T2m"
    ]["units"] = "K"
    with pytest.raises(ValueError, match="unit mismatch"):
        parse_pvgis_hourly_json(fixture["source_payload"])


def test_epw_end_of_hour_labels_become_aware_interval_starts() -> None:
    raw = pd.DataFrame(
        [
            {"year": 2020, "month": 1, "day": 1, "hour": 1},
            {"year": 2020, "month": 1, "day": 1, "hour": 24},
        ]
    )
    metadata = WeatherSourceMetadata(
        source_type="epw",
        source_path="contract.epw",
        timezone=1.0,
        year=2020,
    )
    timestamps = _make_epw_datetimes(raw, metadata)
    assert timestamps[0].isoformat() == "2020-01-01T00:00:00+01:00"
    assert timestamps[1].isoformat() == "2020-01-01T23:00:00+01:00"


def test_epw_without_location_offset_is_rejected() -> None:
    raw = pd.DataFrame([{"year": 2020, "month": 1, "day": 1, "hour": 1}])
    metadata = WeatherSourceMetadata(
        source_type="epw", source_path="contract.epw", timezone=None, year=2020
    )
    with pytest.raises(ValueError, match="UTC offset"):
        _make_epw_datetimes(raw, metadata)
