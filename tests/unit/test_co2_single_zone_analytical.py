"""QICO2-equation verification for the single-zone CO2 solver."""

from __future__ import annotations

from datetime import UTC, datetime
from math import exp

import pytest

from nexusep.abbey.building.physics.airflow import (
    BuildingAirflowNetwork,
    BuildingAirState,
    BuildingCO2GenerationResult,
    ZoneAirState,
    ZoneCO2GenerationRecord,
    ZoneOutdoorAirflowRecord,
    step_building_co2_state,
)
from nexusep.abbey.building.physics.weather import WeatherState

pytestmark = [pytest.mark.unit]
VALIDATION_CATEGORY = "verification"

ZONE_ID = "lecture-room"
VOLUME_M3 = 100.0
OUTDOOR_CO2_PPM = 420.0
CO2_REFERENCE_DENSITY_KG_M3 = 1.842


def _weather() -> WeatherState:
    return WeatherState(
        datetime=datetime(2025, 1, 1, tzinfo=UTC),
        outdoor_co2_ppm=OUTDOOR_CO2_PPM,
    )


def _network(ventilation_m3_h: float) -> BuildingAirflowNetwork:
    return BuildingAirflowNetwork(
        outdoor_airflows_by_zone={
            ZONE_ID: ZoneOutdoorAirflowRecord(
                zone_id=ZONE_ID,
                mechanical_ventilation_flow_m3_h=ventilation_m3_h,
            )
        }
    )


def _generation(generation_m3_h: float) -> BuildingCO2GenerationResult:
    return BuildingCO2GenerationResult(
        zone_records={
            ZONE_ID: ZoneCO2GenerationRecord(
                zone_id=ZONE_ID,
                co2_generation_m3_h=generation_m3_h,
                source="phase_4_13_constant_source",
            )
        }
    )


def _state(co2_ppm: float) -> BuildingAirState:
    return BuildingAirState(
        zone_states={
            ZONE_ID: ZoneAirState(
                zone_id=ZONE_ID,
                co2_ppm=co2_ppm,
                air_volume_m3=VOLUME_M3,
            )
        }
    )


def _exact_co2_ppm(
    initial_ppm: float,
    *,
    duration_h: float,
    ventilation_m3_h: float,
    generation_m3_h: float,
) -> float:
    if ventilation_m3_h == 0.0:
        return initial_ppm + generation_m3_h * 1e6 * duration_h / VOLUME_M3
    steady_state_ppm = (
        OUTDOOR_CO2_PPM + generation_m3_h * 1e6 / ventilation_m3_h
    )
    decay = exp(-ventilation_m3_h / VOLUME_M3 * duration_h)
    return steady_state_ppm + (initial_ppm - steady_state_ppm) * decay


def _simulate(
    initial_ppm: float,
    *,
    duration_h: float,
    ventilation_m3_h: float,
    generation_m3_h: float,
    dt_minutes: float = 1.0,
) -> tuple[float, list]:
    state = _state(initial_ppm)
    results = []
    for _ in range(round(duration_h * 60.0 / dt_minutes)):
        result = step_building_co2_state(
            air_state=state,
            airflow_network=_network(ventilation_m3_h),
            co2_generation_result=_generation(generation_m3_h),
            weather_state=_weather(),
            dt_minutes=dt_minutes,
        )
        results.append(result)
        state = result.updated_air_state
    return state.get_zone_state(ZONE_ID).co2_ppm, results


def _assert_step_balance(result) -> None:
    zone = result.zone_results[ZONE_ID]
    assert zone.balance_residual_m3_s() == pytest.approx(0.0, abs=2e-18)
    assert result.balance_residual_m3_s() == pytest.approx(0.0, abs=2e-18)

    storage_mass_rate_kg_s = (
        zone.storage_change_m3_s() * CO2_REFERENCE_DENSITY_KG_M3
    )
    accounted_mass_rate_kg_s = (
        zone.co2_generation_m3_s + zone.transport_rate_m3_s()
    ) * CO2_REFERENCE_DENSITY_KG_M3
    assert storage_mass_rate_kg_s == pytest.approx(
        accounted_mass_rate_kg_s,
        abs=4e-18,
    )


def test_constant_occupancy_and_ventilation_follow_qico2_solution() -> None:
    actual_ppm, results = _simulate(
        OUTDOOR_CO2_PPM,
        duration_h=4.0,
        ventilation_m3_h=50.0,
        generation_m3_h=0.018,
    )
    expected_ppm = _exact_co2_ppm(
        OUTDOOR_CO2_PPM,
        duration_h=4.0,
        ventilation_m3_h=50.0,
        generation_m3_h=0.018,
    )

    assert actual_ppm == pytest.approx(expected_ppm, abs=0.5)
    assert actual_ppm < OUTDOOR_CO2_PPM + 0.018e6 / 50.0
    for result in results:
        _assert_step_balance(result)


def test_occupancy_step_uses_piecewise_qico2_solution() -> None:
    unoccupied_ppm, unoccupied_results = _simulate(
        500.0,
        duration_h=1.0,
        ventilation_m3_h=50.0,
        generation_m3_h=0.0,
    )
    occupied_ppm, occupied_results = _simulate(
        unoccupied_ppm,
        duration_h=2.0,
        ventilation_m3_h=50.0,
        generation_m3_h=0.018,
    )
    expected_unoccupied_ppm = _exact_co2_ppm(
        500.0,
        duration_h=1.0,
        ventilation_m3_h=50.0,
        generation_m3_h=0.0,
    )
    expected_occupied_ppm = _exact_co2_ppm(
        expected_unoccupied_ppm,
        duration_h=2.0,
        ventilation_m3_h=50.0,
        generation_m3_h=0.018,
    )

    assert unoccupied_ppm == pytest.approx(expected_unoccupied_ppm, abs=0.2)
    assert occupied_ppm == pytest.approx(expected_occupied_ppm, abs=0.6)
    for result in unoccupied_results + occupied_results:
        _assert_step_balance(result)


def test_ventilation_step_changes_the_time_constant_and_equilibrium() -> None:
    low_flow_ppm, low_flow_results = _simulate(
        OUTDOOR_CO2_PPM,
        duration_h=2.0,
        ventilation_m3_h=25.0,
        generation_m3_h=0.018,
    )
    high_flow_ppm, high_flow_results = _simulate(
        low_flow_ppm,
        duration_h=2.0,
        ventilation_m3_h=100.0,
        generation_m3_h=0.018,
    )
    expected_low_flow_ppm = _exact_co2_ppm(
        OUTDOOR_CO2_PPM,
        duration_h=2.0,
        ventilation_m3_h=25.0,
        generation_m3_h=0.018,
    )
    expected_high_flow_ppm = _exact_co2_ppm(
        expected_low_flow_ppm,
        duration_h=2.0,
        ventilation_m3_h=100.0,
        generation_m3_h=0.018,
    )

    assert low_flow_ppm == pytest.approx(expected_low_flow_ppm, abs=0.5)
    assert high_flow_ppm == pytest.approx(expected_high_flow_ppm, abs=0.7)
    assert high_flow_ppm < low_flow_ppm
    for result in low_flow_results + high_flow_results:
        _assert_step_balance(result)


def test_co2_decays_analytically_after_occupants_leave() -> None:
    actual_ppm, results = _simulate(
        1200.0,
        duration_h=4.0,
        ventilation_m3_h=50.0,
        generation_m3_h=0.0,
        dt_minutes=0.25,
    )
    expected_ppm = _exact_co2_ppm(
        1200.0,
        duration_h=4.0,
        ventilation_m3_h=50.0,
        generation_m3_h=0.0,
    )

    assert OUTDOOR_CO2_PPM < actual_ppm < 1200.0
    assert actual_ppm == pytest.approx(expected_ppm, abs=0.5)
    for result in results:
        _assert_step_balance(result)


@pytest.mark.parametrize(
    ("initial_ppm", "ventilation_m3_h"),
    ((OUTDOOR_CO2_PPM, 50.0), (700.0, 0.0)),
)
def test_zero_generation_has_no_unattributed_co2_source(
    initial_ppm: float,
    ventilation_m3_h: float,
) -> None:
    actual_ppm, results = _simulate(
        initial_ppm,
        duration_h=1.0,
        ventilation_m3_h=ventilation_m3_h,
        generation_m3_h=0.0,
    )
    expected_ppm = _exact_co2_ppm(
        initial_ppm,
        duration_h=1.0,
        ventilation_m3_h=ventilation_m3_h,
        generation_m3_h=0.0,
    )

    assert actual_ppm == pytest.approx(expected_ppm, abs=0.2)
    assert all(result.total_generation_m3_s() == 0.0 for result in results)
    for result in results:
        _assert_step_balance(result)
