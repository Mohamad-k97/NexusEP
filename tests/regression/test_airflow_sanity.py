"""
ABBEY airflow sanity test.

Run:
    python -m pytest tests/regression/test_airflow_sanity.py

Provenance:
    adapted from the surviving package-level `test.py` script at frozen HEAD.
"""

from datetime import datetime

from nexusep.abbey.building.physics.weather import WeatherState

from nexusep.abbey.building.physics.windows import (
    WindowStaticParameters,
    WindowOperationState,
    calculate_window_airflow_opening_result,
)

from nexusep.abbey.building.physics.airflow import (
    ZoneAirflowParameters,
    make_zone_outdoor_airflow_record,
)


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def test_window_airflow_is_not_thousands():
    weather = WeatherState(
        datetime=datetime(2021, 1, 1, 12, 0),
        outdoor_temperature_c=5.0,
        wind_speed_m_s=6.0,
        wind_direction_deg=180.0,
        atmospheric_pressure_pa=101325.0,
    )

    window_static = WindowStaticParameters(
        boundary_connection_id="w1",
        zone_id="bedroom_1",
        orientation_deg=180.0,
        area_m2=1.5,
        max_opening_area_m2=0.8,
        discharge_coefficient=0.60,
    )

    window_state = WindowOperationState(
        boundary_connection_id="w1",
        zone_id="bedroom_1",
        is_open=True,
        opening_fraction=1.0,
    )

    result = calculate_window_airflow_opening_result(
        window_static_parameters=window_static,
        window_operation_state=window_state,
        weather_state=weather,
    )

    assert_true(
        result.outdoor_airflow_m3_h <= 250.0 + 1e-9,
        "Window airflow should be capped. got="
        + str(result.outdoor_airflow_m3_h),
    )

    assert_true(
        result.outdoor_airflow_m3_h >= 0.0,
        "Window airflow should be non-negative.",
    )

    print("PASS: test_window_airflow_is_not_thousands")


def test_zone_airflow_cap_protects_thermal_path():
    zone_parameters = ZoneAirflowParameters(
        zone_id="bedroom_1",
        air_volume_m3=40.0,
        default_infiltration_ach=0.1,
        mechanical_ventilation_available=False,
    )

    record = make_zone_outdoor_airflow_record(
        zone_parameters=zone_parameters,
        window_airflow_m3_h=5000.0,
        mechanical_ventilation_flow_m3_h=0.0,
    )

    expected_cap = 40.0 * 4.0

    assert_true(
        record.window_airflow_m3_h <= expected_cap + 1e-9,
        "Zone window airflow should be capped by ACH. got="
        + str(record.window_airflow_m3_h)
        + ", expected_cap="
        + str(expected_cap),
    )

    assert_true(
        record.mixing_exchange_m3_h < 5000.0,
        "Thermal/CO2 path should not receive raw huge window airflow.",
    )

    print("PASS: test_zone_airflow_cap_protects_thermal_path")


def main():
    test_window_airflow_is_not_thousands()
    test_zone_airflow_cap_protects_thermal_path()

    print("Airflow sanity tests passed.")


if __name__ == "__main__":
    main()
