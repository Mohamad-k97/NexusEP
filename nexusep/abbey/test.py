import sys
import math
from pathlib import Path

from nexusep.abbey.building.factory import (
    make_default_family_building,
    make_default_family_physics_graph,
)

from nexusep.abbey.building.physics.weather import (
    WeatherState,
    WeatherProvider,
    load_epw_weather_timeseries,
    interpolate_weather_to_timestep,
    validate_weather_timeseries,
)

from nexusep.abbey.building.physics.engine import (
    BuildingPhysicsStepInput,
    run_building_physics_step,
)


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def assert_greater(a, b, message):
    if not float(a) > float(b):
        raise AssertionError(message + " Got " + str(a) + " <= " + str(b))


def assert_finite(value, message):
    value = float(value)

    if not math.isfinite(value):
        raise AssertionError(message + " Got " + str(value))


def load_real_epw_provider(epw_path, dt_minutes=15):
    weather_series = load_epw_weather_timeseries(
        epw_path=str(epw_path),
        is_tmy=True,
        year=2021,
    )

    weather_series = interpolate_weather_to_timestep(
        weather_series=weather_series,
        dt_minutes=int(dt_minutes),
        allow_extrapolation=False,
    )

    report = validate_weather_timeseries(
        weather_series=weather_series,
        require_timestep_dataframe=True,
        expected_dt_minutes=int(dt_minutes),
        realistic_mode=True,
        raise_on_error=False,
    )

    assert_true(
        not report.has_errors(),
        "Real EPW validation failed. Errors: " + str(report.errors),
    )

    return WeatherProvider(
        weather_series=weather_series,
        use_timestep_dataframe=True,
    )


def find_daytime_solar_step(provider):
    df = provider.dataframe()

    candidates = df[
        (
            df["global_horizontal_radiation_w_m2"] > 100.0
        )
        & (
            df["direct_normal_radiation_w_m2"] >= 0.0
        )
        & (
            df["outdoor_illuminance_lux"] > 1000.0
        )
    ]

    assert_true(
        len(candidates) > 0,
        "Could not find a daytime solar timestep in the EPW.",
    )

    return int(candidates.index[0])


def test_real_epw_provider_returns_solar_daylight_weather_state(epw_path):
    provider = load_real_epw_provider(
        epw_path=epw_path,
        dt_minutes=15,
    )

    step_index = find_daytime_solar_step(provider)
    state = provider.get_state_by_step(step_index)

    assert_true(
        isinstance(state, WeatherState),
        "WeatherProvider should return WeatherState.",
    )

    for key, value in [
        ("outdoor_temperature_c", state.outdoor_temperature_c),
        ("wind_speed_m_s", state.wind_speed_m_s),
        ("wind_direction_deg", state.wind_direction_deg),
        ("direct_normal_radiation_w_m2", state.direct_normal_radiation_w_m2),
        ("diffuse_horizontal_radiation_w_m2", state.diffuse_horizontal_radiation_w_m2),
        ("global_horizontal_radiation_w_m2", state.global_horizontal_radiation_w_m2),
        ("outdoor_illuminance_lux", state.outdoor_illuminance_lux),
        ("outdoor_co2_ppm", state.outdoor_co2_ppm),
    ]:
        assert_finite(
            value,
            "WeatherState field should be finite: " + key,
        )

    assert_greater(
        state.global_horizontal_radiation_w_m2,
        100.0,
        "Selected EPW daytime step should have useful solar radiation.",
    )

    assert_greater(
        state.outdoor_illuminance_lux,
        1000.0,
        "Selected EPW daytime step should have useful outdoor illuminance.",
    )

    print("PASS: test_real_epw_provider_returns_solar_daylight_weather_state")


def test_real_epw_weather_state_runs_through_engine(epw_path):
    provider = load_real_epw_provider(
        epw_path=epw_path,
        dt_minutes=15,
    )

    step_index = find_daytime_solar_step(provider)
    weather_state = provider.get_state_by_step(step_index)

    building = make_default_family_building()
    graph = make_default_family_physics_graph(building)

    result = run_building_physics_step(
        BuildingPhysicsStepInput(
            building_model=building,
            dt_minutes=15.0,
            physics_graph=graph,
            weather_state=weather_state,
        ),
        require_physics_graph=True,
        write_back_to_building_model=False,
    )

    assert_true(
        result.window_boundary_result is not None,
        "Engine should produce window boundary result from real EPW WeatherState.",
    )

    assert_true(
        result.daylight_result is not None,
        "Engine should produce daylight result from real EPW WeatherState.",
    )

    assert_true(
        result.solar_gain_result is not None,
        "Engine should produce solar gain result from real EPW WeatherState.",
    )

    assert_true(
        result.thermal_step_result is not None,
        "Engine should complete thermal step with real EPW WeatherState.",
    )

    assert_true(
        result.building_record.get("has_solar_gain_result", False),
        "Building record should report solar gain result.",
    )

    if "total_solar_gain_w" in result.building_record:
        assert_finite(
            result.building_record["total_solar_gain_w"],
            "Total solar gain should be finite.",
        )

    print("PASS: test_real_epw_weather_state_runs_through_engine")


def test_real_epw_interpolation_preserves_non_negative_solar_fields(epw_path):
    provider = load_real_epw_provider(
        epw_path=epw_path,
        dt_minutes=15,
    )

    df = provider.dataframe()

    for col in [
        "direct_normal_radiation_w_m2",
        "diffuse_horizontal_radiation_w_m2",
        "global_horizontal_radiation_w_m2",
        "outdoor_illuminance_lux",
        "wind_speed_m_s",
    ]:
        assert_true(
            col in df.columns,
            "Interpolated weather dataframe missing column: " + col,
        )

        assert_true(
            (df[col] >= 0.0).all(),
            "Interpolated column should be non-negative: " + col,
        )

    print("PASS: test_real_epw_interpolation_preserves_non_negative_solar_fields")


if __name__ == "__main__":
    # if len(sys.argv) < 2:
    #     raise SystemExit(
    #         "Usage:\n"
    #         "python run_test_phase_13_1_real_epw_weather_adapter.py path/to/weather.epw"
    #     )

    epw_path = "C:/Works/NexusEP/NexusEP/nexusep/abbey/SWE_UP_Uppsala.Univ.024620_TMYx.2009-2023.epw"



    test_real_epw_provider_returns_solar_daylight_weather_state(epw_path)
    test_real_epw_weather_state_runs_through_engine(epw_path)
    test_real_epw_interpolation_preserves_non_negative_solar_fields(epw_path)

    print("Phase 13.1 real EPW weather solar-field adapter tests passed.")