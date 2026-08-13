"""Strict adapters for official weather-source validation fixtures.

These functions normalize source fields and units but retain each source's
time semantics.  They do not silently manufacture fields required by the
canonical simulation weather contract.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from io import StringIO
from typing import Any, Literal

import numpy as np
import pandas as pd

WeatherTimeSemantic = Literal[
    "instantaneous_sample",
    "hourly_mean",
    "interval_start_hourly_mean",
]

NORMALIZED_COLUMNS = (
    "timestamp_utc",
    "outdoor_temperature_c",
    "relative_humidity_fraction",
    "atmospheric_pressure_pa",
    "wind_speed_m_s",
    "wind_direction_deg",
    "direct_normal_radiation_w_m2",
    "diffuse_horizontal_radiation_w_m2",
    "global_horizontal_radiation_w_m2",
)


@dataclass(frozen=True)
class WeatherIngestionResult:
    source: str
    data: pd.DataFrame
    time_semantic: WeatherTimeSemantic
    source_timezone: str
    missing_canonical_fields: tuple[str, ...]
    derived_fields: tuple[str, ...]
    warnings: tuple[str, ...]


def parse_pvgis_hourly_json(payload: Mapping[str, Any]) -> WeatherIngestionResult:
    """Normalize a PVGIS ``seriescalc`` JSON response.

    PVGIS-SARAH irradiance is an instantaneous satellite-image value, not an
    interval average.  ``Gb(i)`` is direct irradiance on the requested plane;
    this adapter only accepts a horizontal plane and derives DNI away from the
    horizon using the reported sun height.
    """

    try:
        inputs = payload["inputs"]
        rows = payload["outputs"]["hourly"]
        variables = payload["meta"]["outputs"]["hourly"]["variables"]
    except (KeyError, TypeError) as exc:
        raise ValueError("invalid PVGIS hourly JSON structure") from exc
    fixed = inputs.get("mounting_system", {}).get("fixed", {})
    slope = fixed.get("slope", {}).get("value")
    if float(slope) != 0.0:
        raise ValueError("PVGIS validation ingestion requires a horizontal plane")
    _require_units(
        variables,
        {
            "Gb(i)": "W/m2",
            "Gd(i)": "W/m2",
            "Gr(i)": "W/m2",
            "H_sun": "degree",
            "T2m": "degree Celsius",
            "WS10m": "m/s",
        },
        source="PVGIS",
    )
    normalized: list[dict[str, Any]] = []
    dni_undefined = 0
    for row in rows:
        timestamp = datetime.strptime(str(row["time"]), "%Y%m%d:%H%M").replace(
            tzinfo=UTC
        )
        direct_horizontal = _non_negative(row["Gb(i)"], "Gb(i)")
        diffuse = _non_negative(row["Gd(i)"], "Gd(i)")
        reflected = _non_negative(row["Gr(i)"], "Gr(i)")
        sun_height = float(row["H_sun"])
        sine_height = math.sin(math.radians(sun_height))
        if direct_horizontal == 0.0:
            dni = 0.0
        elif sine_height > 0.01:
            dni = direct_horizontal / sine_height
        else:
            dni = np.nan
            dni_undefined += 1
        normalized.append(
            {
                "timestamp_utc": timestamp,
                "outdoor_temperature_c": float(row["T2m"]),
                "relative_humidity_fraction": np.nan,
                "atmospheric_pressure_pa": np.nan,
                "wind_speed_m_s": _non_negative(row["WS10m"], "WS10m"),
                "wind_direction_deg": np.nan,
                "direct_normal_radiation_w_m2": dni,
                "diffuse_horizontal_radiation_w_m2": diffuse,
                "global_horizontal_radiation_w_m2": (
                    direct_horizontal + diffuse + reflected
                ),
            }
        )
    frame = _frame(normalized)
    radiation_db = str(inputs.get("meteo_data", {}).get("radiation_db", ""))
    semantic: WeatherTimeSemantic = (
        "instantaneous_sample"
        if "SARAH" in radiation_db.upper()
        else "hourly_mean"
    )
    warnings = [
        (
            "PVGIS hourly irradiance and reanalysis meteorology do not share one "
            "universal interval semantic"
        )
    ]
    if dni_undefined:
        warnings.append(
            f"DNI could not be derived for {dni_undefined} low-sun records"
        )
    return WeatherIngestionResult(
        source="pvgis",
        data=frame,
        time_semantic=semantic,
        source_timezone="UTC",
        missing_canonical_fields=(
            "relative_humidity_fraction",
            "atmospheric_pressure_pa",
            "wind_direction_deg",
        ),
        derived_fields=(
            "direct_normal_radiation_w_m2",
            "global_horizontal_radiation_w_m2",
        ),
        warnings=tuple(warnings),
    )


def parse_nasa_power_hourly_json(
    payload: Mapping[str, Any], *, require_utc: bool = True
) -> WeatherIngestionResult:
    """Normalize a NASA POWER hourly point JSON response."""

    try:
        parameters = payload["parameters"]
        series = payload["properties"]["parameter"]
        header = payload["header"]
    except (KeyError, TypeError) as exc:
        raise ValueError("invalid NASA POWER hourly JSON structure") from exc
    time_standard = str(header.get("time_standard", "")).upper()
    if require_utc and time_standard != "UTC":
        raise ValueError(
            "NASA POWER response must declare UTC; LST is not a civil timezone"
        )
    expected_units = {
        "T2M": "C",
        "RH2M": "%",
        "PS": "kPa",
        "WS10M": "m/s",
        "WD10M": "Degrees",
        "ALLSKY_SFC_SW_DWN": "W m-2",
        "ALLSKY_SFC_SW_DNI": "W m-2",
        "ALLSKY_SFC_SW_DIFF": "W m-2",
    }
    missing = sorted(set(expected_units) - set(series))
    if missing:
        raise ValueError(f"NASA POWER response is missing parameters: {missing}")
    for name, unit in expected_units.items():
        if parameters.get(name, {}).get("units") != unit:
            raise ValueError(
                f"NASA POWER unit mismatch for {name}: "
                f"{parameters.get(name, {}).get('units')!r} != {unit!r}"
            )
    keys = list(series["T2M"])
    if any(list(series[name]) != keys for name in expected_units):
        raise ValueError("NASA POWER parameters do not share identical timestamps")
    normalized = []
    for key in keys:
        timestamp = datetime.strptime(key, "%Y%m%d%H").replace(tzinfo=UTC)
        normalized.append(
            {
                "timestamp_utc": timestamp,
                "outdoor_temperature_c": _power_value(series["T2M"][key]),
                "relative_humidity_fraction": _power_value(
                    series["RH2M"][key]
                )
                / 100.0,
                "atmospheric_pressure_pa": _power_value(series["PS"][key])
                * 1000.0,
                "wind_speed_m_s": _power_value(series["WS10M"][key]),
                "wind_direction_deg": _power_value(series["WD10M"][key])
                % 360.0,
                "direct_normal_radiation_w_m2": _power_value(
                    series["ALLSKY_SFC_SW_DNI"][key]
                ),
                "diffuse_horizontal_radiation_w_m2": _power_value(
                    series["ALLSKY_SFC_SW_DIFF"][key]
                ),
                "global_horizontal_radiation_w_m2": _power_value(
                    series["ALLSKY_SFC_SW_DWN"][key]
                ),
            }
        )
    return WeatherIngestionResult(
        source="nasa_power",
        data=_frame(normalized),
        time_semantic="interval_start_hourly_mean",
        source_timezone=time_standard,
        missing_canonical_fields=(),
        derived_fields=(
            "relative_humidity_fraction",
            "atmospheric_pressure_pa",
        ),
        warnings=(
            (
                "POWER satellite/reanalysis values are forcing-plausibility evidence, "
                "not exact ground truth"
            ),
        ),
    )


def parse_nsrdb_psm3_csv(text: str) -> WeatherIngestionResult:
    """Normalize an NSRDB PSM3 CSV response without leaking numeric IDs."""

    rows = list(csv.reader(StringIO(text)))
    if len(rows) < 4:
        raise ValueError("NSRDB CSV must contain metadata, headers, and data")
    metadata_names, metadata_values, field_names = rows[:3]
    if len(metadata_names) != len(metadata_values):
        raise ValueError("NSRDB metadata names and values have different lengths")
    metadata = dict(zip(metadata_names, metadata_values, strict=True))
    required = {
        "Year",
        "Month",
        "Day",
        "Hour",
        "Minute",
        "Temperature",
        "Relative Humidity",
        "Pressure",
        "Wind Speed",
        "Wind Direction",
        "DNI",
        "DHI",
        "GHI",
    }
    missing = sorted(required - set(field_names))
    if missing:
        raise ValueError(f"NSRDB CSV is missing fields: {missing}")
    try:
        offset_hours = float(metadata["Time Zone"])
    except (KeyError, ValueError) as exc:
        raise ValueError("NSRDB metadata must declare numeric Time Zone") from exc
    source_tz = timezone(timedelta(hours=offset_hours))
    normalized = []
    for raw in rows[3:]:
        if not raw or not any(value.strip() for value in raw):
            continue
        if len(raw) != len(field_names):
            raise ValueError("NSRDB data row length does not match field header")
        row = dict(zip(field_names, raw, strict=True))
        source_timestamp = datetime(
            int(row["Year"]),
            int(row["Month"]),
            int(row["Day"]),
            int(row["Hour"]),
            int(row["Minute"]),
            tzinfo=source_tz,
        )
        normalized.append(
            {
                "timestamp_utc": source_timestamp.astimezone(UTC),
                "outdoor_temperature_c": float(row["Temperature"]),
                "relative_humidity_fraction": float(row["Relative Humidity"])
                / 100.0,
                "atmospheric_pressure_pa": float(row["Pressure"]),
                "wind_speed_m_s": _non_negative(row["Wind Speed"], "Wind Speed"),
                "wind_direction_deg": float(row["Wind Direction"]) % 360.0,
                "direct_normal_radiation_w_m2": _non_negative(row["DNI"], "DNI"),
                "diffuse_horizontal_radiation_w_m2": _non_negative(row["DHI"], "DHI"),
                "global_horizontal_radiation_w_m2": _non_negative(row["GHI"], "GHI"),
            }
        )
    return WeatherIngestionResult(
        source="nsrdb_psm3",
        data=_frame(normalized),
        time_semantic="interval_start_hourly_mean",
        source_timezone=f"{offset_hours:+g}:00",
        missing_canonical_fields=(),
        derived_fields=("relative_humidity_fraction", "timestamp_utc"),
        warnings=(
            "NSRDB data retrieval requires an API key and identifying request metadata",
        ),
    )


def radiation_component_residual_w_m2(
    frame: pd.DataFrame, solar_zenith_deg: Sequence[float]
) -> pd.Series:
    """Return GHI - (DHI + DNI*cos(zenith)), clipped only below the horizon."""

    zenith = np.asarray(solar_zenith_deg, dtype=float)
    if len(zenith) != len(frame):
        raise ValueError("solar_zenith_deg must have one value per weather row")
    cosine = np.maximum(0.0, np.cos(np.deg2rad(zenith)))
    expected = (
        frame["diffuse_horizontal_radiation_w_m2"].to_numpy(dtype=float)
        + frame["direct_normal_radiation_w_m2"].to_numpy(dtype=float) * cosine
    )
    return pd.Series(
        frame["global_horizontal_radiation_w_m2"].to_numpy(dtype=float)
        - expected,
        index=frame.index,
        name="radiation_component_residual_w_m2",
    )


def _require_units(
    variables: Mapping[str, Any], expected: Mapping[str, str], *, source: str
) -> None:
    for name, unit in expected.items():
        actual = variables.get(name, {}).get("units")
        if actual != unit:
            raise ValueError(
                f"{source} unit mismatch for {name}: {actual!r} != {unit!r}"
            )


def _power_value(value: Any) -> float:
    number = float(value)
    if number <= -900.0 or not math.isfinite(number):
        return np.nan
    return number


def _non_negative(value: Any, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")
    return result


def _frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        raise ValueError("weather response contains no records")
    frame = pd.DataFrame.from_records(records, columns=NORMALIZED_COLUMNS)
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
    if frame["timestamp_utc"].duplicated().any():
        raise ValueError("weather response has duplicate timestamps")
    if not frame["timestamp_utc"].is_monotonic_increasing:
        raise ValueError("weather timestamps must be monotonic increasing")
    for column in NORMALIZED_COLUMNS[1:]:
        values = frame[column].dropna().to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f"weather field {column} contains non-finite values")
    return frame
