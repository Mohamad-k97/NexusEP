"""Regression coverage for the supported pandas weather pipeline.

Provenance: added after the real-EPW building example failed under pandas 3,
where ``NDFrame.fillna(method=...)`` is no longer accepted.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from nexusep.abbey.building.physics.weather import (
    WeatherSourceMetadata,
    WeatherTimeSeries,
    interpolate_weather_to_timestep,
    preprocess_wind,
)


def test_missing_weather_values_use_supported_forward_and_backward_fill() -> None:
    hourly = pd.DataFrame(
        {
            "datetime": pd.date_range("2026-01-01", periods=3, freq="h"),
            "outdoor_temperature_c": [1.0, 2.0, 3.0],
            "relative_humidity_percent": [80.0, 79.0, 78.0],
            "atmospheric_pressure_pa": [101325.0, 101300.0, 101275.0],
            "wind_speed_m_s": [1.0, np.nan, 2.0],
            "wind_direction_deg": [90.0, np.nan, 180.0],
            "direct_normal_radiation_w_m2": [0.0, 0.0, 0.0],
            "diffuse_horizontal_radiation_w_m2": [0.0, 0.0, 0.0],
            "global_horizontal_radiation_w_m2": [0.0, 0.0, 0.0],
            "outdoor_illuminance_lux": [0.0, 0.0, 0.0],
            "outdoor_co2_ppm": [420.0, 420.0, 420.0],
            "outdoor_noise_db": [40.0, 40.0, 40.0],
            "sky_condition": ["clear", None, "cloudy"],
        }
    )
    series = WeatherTimeSeries(
        metadata=WeatherSourceMetadata(
            source_type="manual",
            data_timestep_minutes=60,
        ),
        hourly_dataframe=hourly,
    )

    wind_ready = preprocess_wind(series)
    assert wind_ready.hourly_dataframe["wind_direction_deg"].tolist() == [
        90.0,
        0.0,
        180.0,
    ]

    interpolated = interpolate_weather_to_timestep(
        weather_series=wind_ready,
        dt_minutes=15,
        allow_extrapolation=True,
    )
    assert len(interpolated.timestep_dataframe) == 9
    assert not interpolated.timestep_dataframe[
        ["wind_direction_deg", "sky_condition"]
    ].isna().any().any()
