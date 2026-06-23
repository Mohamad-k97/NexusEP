"""
ABBEY Phase 3 weather-layer test using a real EPW file.

Tests:
- EPW loading
- metadata parsing
- hourly dataframe creation
- radiation/daylight preprocessing
- wind preprocessing
- outdoor boundary defaults
- timestep interpolation
- WeatherProvider
- WeatherState output
- validation

No building physics is calculated.
"""

import os
import sys

from nexusep.abbey.building.physics.weather import (
    WeatherProvider,
    WeatherState,
    interpolate_weather_to_timestep,
    load_epw_weather_timeseries,
    validate_weather_timeseries,
)


# Put your real EPW path here.
EPW_PATH = r"C:/Works/NexusEP/NexusEP/nexusep/abbey/SWE_UP_Uppsala.Univ.024620_TMYx.2009-2023.epw"

DT_MINUTES = 15


def assert_metadata_real_epw(weather_series):
    metadata = weather_series.metadata

    assert metadata.source_type == "epw"
    assert metadata.source_path is not None
    assert str(metadata.source_path).strip() != ""

    assert metadata.location_name is not None
    assert str(metadata.location_name).strip() != ""

    assert metadata.data_timestep_minutes == 60

    assert metadata.latitude is not None
    assert metadata.longitude is not None
    assert metadata.timezone is not None
    assert metadata.elevation_m is not None

    print("OK: metadata parsed")


def assert_hourly_dataframe(weather_series):
    df = weather_series.hourly_dataframe

    assert df is not None
    assert len(df) > 0

    required_columns = [
        "datetime",
        "outdoor_temperature_c",
        "wind_speed_m_s",
        "wind_direction_deg",
        "direct_normal_radiation_w_m2",
        "diffuse_horizontal_radiation_w_m2",
        "global_horizontal_radiation_w_m2",
        "outdoor_illuminance_lux",
    ]

    for column in required_columns:
        assert column in df.columns, "Missing hourly weather column: " + column

    print("OK: hourly weather table exists")


def assert_radiation_clamped(weather_series):
    df = weather_series.hourly_dataframe

    radiation_columns = [
        "direct_normal_radiation_w_m2",
        "diffuse_horizontal_radiation_w_m2",
        "global_horizontal_radiation_w_m2",
    ]

    for column in radiation_columns:
        assert (df[column] >= 0.0).all(), column + " has negative values"

    assert (df["outdoor_illuminance_lux"] >= 0.0).all()

    assert "is_night" in df.columns

    night_df = df[df["is_night"]]

    if len(night_df) > 0:
        for column in radiation_columns:
            assert (night_df[column] == 0.0).all()

        assert (night_df["outdoor_illuminance_lux"] == 0.0).all()

    print("OK: radiation and illuminance clamped")


def assert_wind_preprocessed(weather_series):
    df = weather_series.hourly_dataframe

    assert (df["wind_speed_m_s"] >= 0.0).all()
    assert (df["wind_direction_deg"] >= 0.0).all()
    assert (df["wind_direction_deg"] < 360.0).all()

    required_columns = [
        "wind_direction_sin",
        "wind_direction_cos",
        "wind_vector_east_m_s",
        "wind_vector_north_m_s",
    ]

    for column in required_columns:
        assert column in df.columns, "Missing wind preprocessing column: " + column

    print("OK: wind direction normalized")


def assert_outdoor_defaults(weather_series):
    df = weather_series.hourly_dataframe

    assert "outdoor_co2_ppm" in df.columns
    assert "outdoor_noise_db" in df.columns
    assert "sky_condition" in df.columns

    assert (df["outdoor_co2_ppm"] > 0.0).all()
    assert (df["outdoor_noise_db"] >= 0.0).all()

    assert abs(float(df["outdoor_co2_ppm"].iloc[0]) - 420.0) < 1e-9
    assert abs(float(df["outdoor_noise_db"].iloc[0]) - 45.0) < 1e-9

    print("OK: outdoor boundary defaults exist")


def assert_interpolation(weather_series, dt_minutes):
    interpolated = interpolate_weather_to_timestep(
        weather_series,
        dt_minutes=dt_minutes,
    )

    df = interpolated.timestep_dataframe

    assert df is not None
    assert len(df) > 0

    hourly_df = weather_series.hourly_dataframe
    start_time = hourly_df["datetime"].iloc[0]
    end_time = hourly_df["datetime"].iloc[-1]

    expected_steps = int(
        ((end_time - start_time).total_seconds() / 60.0) / dt_minutes
    ) + 1

    assert len(df) == expected_steps, (
        "Unexpected timestep count. Expected "
        + str(expected_steps)
        + ", got "
        + str(len(df))
    )

    non_negative_columns = [
        "wind_speed_m_s",
        "direct_normal_radiation_w_m2",
        "diffuse_horizontal_radiation_w_m2",
        "global_horizontal_radiation_w_m2",
        "outdoor_illuminance_lux",
        "outdoor_co2_ppm",
        "outdoor_noise_db",
    ]

    for column in non_negative_columns:
        assert (df[column] >= 0.0).all(), column + " has negative values"

    assert (df["wind_direction_deg"] >= 0.0).all()
    assert (df["wind_direction_deg"] < 360.0).all()

    print("OK: weather interpolated to timestep")

    return interpolated


def assert_weather_provider(weather_series):
    provider = WeatherProvider(weather_series)

    assert provider.number_of_steps() == len(weather_series.simulation_dataframe())

    state_0 = provider.get_state_by_step(0)
    assert isinstance(state_0, WeatherState)

    if provider.number_of_steps() > 10:
        some_datetime = provider.datetimes()[10]
    else:
        some_datetime = provider.datetimes()[0]

    state_t = provider.get_state(some_datetime)
    assert isinstance(state_t, WeatherState)

    assert state_0.outdoor_co2_ppm > 0.0
    assert state_0.outdoor_noise_db >= 0.0
    assert state_0.wind_direction_deg >= 0.0
    assert state_0.wind_direction_deg < 360.0

    print("OK: WeatherProvider returns WeatherState")


def assert_validation(weather_series, dt_minutes):
    report = validate_weather_timeseries(
        weather_series,
        require_timestep_dataframe=True,
        expected_dt_minutes=dt_minutes,
        raise_on_error=True,
    )

    print(report)
    print("OK: weather validation")


def assert_no_building_physics(weather_series):
    df = weather_series.simulation_dataframe()

    forbidden_columns = [
        "indoor_temp_c",
        "zone_temperature_c",
        "heating_energy_wh",
        "cooling_energy_wh",
        "solar_gain_wh",
        "zone_co2_ppm",
        "indoor_daylight",
        "indoor_noise",
    ]

    for column in forbidden_columns:
        assert column not in df.columns, (
            "Building physics column should not exist in Phase 3: " + column
        )

    print("OK: no building physics calculated")


def run_tests(epw_path, dt_minutes=15):
    if epw_path is None or not str(epw_path).strip():
        raise ValueError("epw_path cannot be empty.")

    epw_path = str(epw_path)

    if not os.path.exists(epw_path):
        raise FileNotFoundError("EPW file not found: " + epw_path)

    weather_series = load_epw_weather_timeseries(epw_path)

    assert_metadata_real_epw(weather_series)
    assert_hourly_dataframe(weather_series)
    assert_radiation_clamped(weather_series)
    assert_wind_preprocessed(weather_series)
    assert_outdoor_defaults(weather_series)

    weather_series = assert_interpolation(
        weather_series,
        dt_minutes=dt_minutes,
    )

    assert_weather_provider(weather_series)
    assert_validation(weather_series, dt_minutes)
    assert_no_building_physics(weather_series)

    print("")
    print("PHASE 3 WEATHER LAYER OK ✅")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        epw_path_arg = sys.argv[1]
    else:
        epw_path_arg = EPW_PATH

    run_tests(
        epw_path=epw_path_arg,
        dt_minutes=DT_MINUTES,
    )