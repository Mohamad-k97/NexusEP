"""Closed-form verification cases for the reduced-order RC thermal solver."""

from __future__ import annotations

from datetime import UTC, datetime
from math import exp, log

import pytest

from nexusep.abbey.building.physics.thermal import (
    BuildingInterzoneThermalNetwork,
    BuildingThermalParameters,
    BuildingThermalState,
    InterzoneThermalLink,
    ThermalTemperatureTarget,
    ZoneThermalParameters,
    ZoneThermalState,
    calculate_interzone_heat_flow_records,
    check_interzone_heat_flow_symmetry,
    semi_implicit_temperature_update,
    step_building_thermal_state_semi_implicit,
    update_zone_thermal_state_semi_implicit,
)
from nexusep.abbey.building.physics.weather import WeatherState

pytestmark = [pytest.mark.unit]
VALIDATION_CATEGORY = "verification"


def _target(temperature_c: float, h_w_k: float) -> ThermalTemperatureTarget:
    return ThermalTemperatureTarget(
        target_id="outdoor",
        target_type="outside",
        temperature_c=temperature_c,
        h_w_k=h_w_k,
    )


def _parameters(
    zone_id: str,
    *,
    c_air_j_k: float = 120_000.0,
    c_mass_j_k: float = 1_200_000.0,
    h_air_mass_w_k: float = 80.0,
    h_external_w_k: float = 0.0,
) -> ZoneThermalParameters:
    return ZoneThermalParameters(
        zone_id=zone_id,
        c_air_j_k=c_air_j_k,
        c_mass_j_k=c_mass_j_k,
        h_air_mass_w_k=h_air_mass_w_k,
        h_external_w_k=h_external_w_k,
        h_interzone_w_k=0.0,
        h_ventilation_w_k=0.0,
        air_volume_m3=100.0,
        infiltration_ach=0.0,
        floor_area_m2=40.0,
        effective_mass_area_m2=40.0,
        external_wall_area_m2=0.0,
        internal_wall_area_m2=0.0,
        source="phase_4_7_analytical_fixture",
    )


def _weather(outdoor_temperature_c: float) -> WeatherState:
    return WeatherState(
        datetime=datetime(2025, 1, 1, tzinfo=UTC),
        outdoor_temperature_c=outdoor_temperature_c,
    )


def _stored_energy_j(
    state: BuildingThermalState,
    parameters: BuildingThermalParameters,
) -> float:
    return sum(
        parameters.get_zone_parameters(zone_id).c_air_j_k
        * zone_state.air_temperature_c
        + parameters.get_zone_parameters(zone_id).c_mass_j_k
        * zone_state.mass_temperature_c
        for zone_id, zone_state in state.zone_states.items()
    )


def test_exponential_decay_recovers_the_rc_time_constant() -> None:
    capacity_j_k = 360_000.0
    conductance_w_k = 100.0
    time_constant_s = capacity_j_k / conductance_w_k
    dt_seconds = 60.0
    step_count = 60
    outdoor_temperature_c = 10.0
    initial_temperature_c = 30.0
    temperature_c = initial_temperature_c

    for _ in range(step_count):
        temperature_c = semi_implicit_temperature_update(
            capacity_j_k=capacity_j_k,
            old_temperature_c=temperature_c,
            targets=[_target(outdoor_temperature_c, conductance_w_k)],
            gain_w=0.0,
            dt_seconds=dt_seconds,
        )

    discrete_decay = (1.0 + dt_seconds / time_constant_s) ** (-step_count)
    expected_temperature_c = outdoor_temperature_c + (
        initial_temperature_c - outdoor_temperature_c
    ) * discrete_decay
    assert temperature_c == pytest.approx(expected_temperature_c, abs=1e-12)

    observed_decay = (
        (temperature_c - outdoor_temperature_c)
        / (initial_temperature_c - outdoor_temperature_c)
    )
    inferred_time_constant_s = -(step_count * dt_seconds) / log(observed_decay)
    assert inferred_time_constant_s == pytest.approx(time_constant_s, rel=0.01)


def test_constant_internal_gain_reaches_the_analytical_equilibrium() -> None:
    capacity_j_k = 360_000.0
    conductance_w_k = 100.0
    gain_w = 200.0
    outdoor_temperature_c = 20.0
    equilibrium_temperature_c = outdoor_temperature_c + gain_w / conductance_w_k
    temperature_c = 8.0

    for _ in range(48 * 12):
        temperature_c = semi_implicit_temperature_update(
            capacity_j_k=capacity_j_k,
            old_temperature_c=temperature_c,
            targets=[_target(outdoor_temperature_c, conductance_w_k)],
            gain_w=gain_w,
            dt_seconds=300.0,
        )

    assert temperature_c == pytest.approx(equilibrium_temperature_c, abs=1e-9)
    assert conductance_w_k * (
        temperature_c - outdoor_temperature_c
    ) == pytest.approx(gain_w, abs=1e-7)


def test_step_change_in_outdoor_temperature_matches_backward_euler() -> None:
    capacity_j_k = 360_000.0
    conductance_w_k = 100.0
    dt_seconds = 600.0
    initial_temperature_c = 20.0
    new_outdoor_temperature_c = 0.0

    actual_temperature_c = semi_implicit_temperature_update(
        capacity_j_k=capacity_j_k,
        old_temperature_c=initial_temperature_c,
        targets=[_target(new_outdoor_temperature_c, conductance_w_k)],
        gain_w=0.0,
        dt_seconds=dt_seconds,
    )
    expected_temperature_c = (
        initial_temperature_c
        + dt_seconds * conductance_w_k / capacity_j_k
        * new_outdoor_temperature_c
    ) / (1.0 + dt_seconds * conductance_w_k / capacity_j_k)
    assert actual_temperature_c == pytest.approx(expected_temperature_c, abs=1e-12)


def test_step_heating_input_is_exact_for_an_adiabatic_node() -> None:
    capacity_j_k = 180_000.0
    heating_power_w = 600.0
    dt_seconds = 600.0
    initial_temperature_c = 20.0

    actual_temperature_c = semi_implicit_temperature_update(
        capacity_j_k=capacity_j_k,
        old_temperature_c=initial_temperature_c,
        targets=[],
        gain_w=heating_power_w,
        dt_seconds=dt_seconds,
    )
    expected_temperature_c = (
        initial_temperature_c + heating_power_w * dt_seconds / capacity_j_k
    )
    assert actual_temperature_c == pytest.approx(expected_temperature_c, abs=1e-12)


def test_two_zone_exchange_is_equal_opposite_and_energy_conservative() -> None:
    parameters = BuildingThermalParameters(
        zone_parameters={
            "west": _parameters(
                "west", c_air_j_k=100_000.0, c_mass_j_k=500_000.0
            ),
            "east": _parameters(
                "east", c_air_j_k=180_000.0, c_mass_j_k=900_000.0
            ),
        }
    )
    initial_state = BuildingThermalState(
        zone_states={
            "west": ZoneThermalState("west", 30.0, 22.0),
            "east": ZoneThermalState("east", 10.0, 18.0),
        }
    )
    network = BuildingInterzoneThermalNetwork(
        links={
            "west-east": InterzoneThermalLink(
                link_id="west-east",
                connection_id="west-east",
                zone_a_id="west",
                zone_b_id="east",
                h_w_k=40.0,
            )
        }
    )

    records = calculate_interzone_heat_flow_records(network, initial_state)
    assert check_interzone_heat_flow_symmetry(records, tolerance_w=1e-12)
    assert records[0].q_to_zone_a_w == pytest.approx(-800.0)
    assert records[0].q_to_zone_b_w == pytest.approx(800.0)

    initial_energy_j = _stored_energy_j(initial_state, parameters)
    result = step_building_thermal_state_semi_implicit(
        thermal_state=initial_state,
        building_parameters=parameters,
        weather_state=_weather(20.0),
        interzone_network=network,
        dt_minutes=10.0,
    )
    final_energy_j = _stored_energy_j(result.updated_state, parameters)

    assert final_energy_j == pytest.approx(initial_energy_j, abs=1e-6)
    initial_difference_c = 20.0
    final_difference_c = (
        result.updated_state.get_zone_state("west").air_temperature_c
        - result.updated_state.get_zone_state("east").air_temperature_c
    )
    assert 0.0 < final_difference_c < initial_difference_c


def test_adiabatic_two_node_zone_conserves_energy_and_equilibrates() -> None:
    parameters = _parameters(
        "zone",
        c_air_j_k=100_000.0,
        c_mass_j_k=900_000.0,
        h_air_mass_w_k=100.0,
    )
    state = ZoneThermalState("zone", 30.0, 20.0)
    initial_energy_j = (
        parameters.c_air_j_k * state.air_temperature_c
        + parameters.c_mass_j_k * state.mass_temperature_c
    )
    equilibrium_temperature_c = initial_energy_j / (
        parameters.c_air_j_k + parameters.c_mass_j_k
    )

    for _ in range(240):
        result = update_zone_thermal_state_semi_implicit(
            zone_state=state,
            zone_parameters=parameters,
            outdoor_temperature_c=-100.0,
            ventilation_h_w_k=0.0,
            dt_minutes=1.0,
        )
        state = result.to_zone_thermal_state()
        energy_j = (
            parameters.c_air_j_k * state.air_temperature_c
            + parameters.c_mass_j_k * state.mass_temperature_c
        )
        assert energy_j == pytest.approx(initial_energy_j, abs=1e-6)

    assert state.air_temperature_c == pytest.approx(
        equilibrium_temperature_c, abs=1e-3
    )
    assert state.mass_temperature_c == pytest.approx(
        equilibrium_temperature_c, abs=1e-3
    )


def test_zero_capacity_is_rejected_before_solving() -> None:
    with pytest.raises(ValueError, match="c_air_j_k must be positive"):
        _parameters("invalid", c_air_j_k=0.0)

    with pytest.raises(ValueError, match="capacity_j_k must be positive"):
        semi_implicit_temperature_update(
            capacity_j_k=0.0,
            old_temperature_c=20.0,
            targets=[],
            gain_w=0.0,
            dt_seconds=60.0,
        )


def test_backward_euler_converges_to_the_continuous_solution_as_dt_decreases() -> None:
    capacity_j_k = 360_000.0
    conductance_w_k = 100.0
    duration_s = 3_600.0
    initial_temperature_c = 30.0
    outdoor_temperature_c = 10.0
    exact_temperature_c = outdoor_temperature_c + (
        initial_temperature_c - outdoor_temperature_c
    ) * exp(-duration_s / (capacity_j_k / conductance_w_k))
    errors = []

    for dt_seconds in (1800.0, 900.0, 300.0, 60.0):
        temperature_c = initial_temperature_c
        for _ in range(round(duration_s / dt_seconds)):
            temperature_c = semi_implicit_temperature_update(
                capacity_j_k=capacity_j_k,
                old_temperature_c=temperature_c,
                targets=[_target(outdoor_temperature_c, conductance_w_k)],
                gain_w=0.0,
                dt_seconds=dt_seconds,
            )
        errors.append(abs(temperature_c - exact_temperature_c))

    assert errors == sorted(errors, reverse=True)
    assert errors[-1] < 0.07
