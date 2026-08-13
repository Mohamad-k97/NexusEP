"""Analytical verification for fixed-temperature zone moisture balances."""

from __future__ import annotations

from math import exp

import pytest

from nexusep.abbey.building.physics.moisture import (
    MOISTURE_AIR_DENSITY_KG_M3,
    MOISTURE_BUILDING_TIMESTEP_METHOD,
    MOISTURE_SOURCE_COOKING,
    MOISTURE_SOURCE_PEOPLE,
    MOISTURE_SOURCE_SHOWER,
    MOISTURE_TRANSPORT_TARGET_INTERZONE,
    MOISTURE_TRANSPORT_TARGET_OUTDOOR,
    BuildingMoistureParameters,
    BuildingMoistureSourceInputs,
    BuildingMoistureState,
    BuildingMoistureTransportResult,
    MoistureTransportTarget,
    ZoneMoistureParameters,
    ZoneMoistureSourceInput,
    ZoneMoistureState,
    ZoneMoistureTransportTargets,
    humidity_ratio_from_rh,
    relative_humidity_from_humidity_ratio,
    step_building_moisture_state,
)
from nexusep.abbey.building.physics.thermal import (
    BuildingThermalState,
    ZoneThermalState,
)

pytestmark = [pytest.mark.unit]
VALIDATION_CATEGORY = "verification"
PRESSURE_PA = 101325.0


def _parameters(**dry_air_mass_kg_by_zone: float) -> BuildingMoistureParameters:
    return BuildingMoistureParameters(
        zone_parameters={
            zone_id: ZoneMoistureParameters(
                zone_id=zone_id,
                air_volume_m3=dry_air_mass_kg / MOISTURE_AIR_DENSITY_KG_M3,
                dry_air_mass_kg=dry_air_mass_kg,
            )
            for zone_id, dry_air_mass_kg in dry_air_mass_kg_by_zone.items()
        }
    )


def _state(**humidity_ratio_by_zone: float) -> BuildingMoistureState:
    return BuildingMoistureState(
        zone_states={
            zone_id: ZoneMoistureState(
                zone_id=zone_id,
                humidity_ratio_kg_kg=humidity_ratio,
                relative_humidity_percent=relative_humidity_from_humidity_ratio(
                    humidity_ratio,
                    20.0,
                    PRESSURE_PA,
                ),
            )
            for zone_id, humidity_ratio in humidity_ratio_by_zone.items()
        }
    )


def _thermal(temperature_c: float, *zone_ids: str) -> BuildingThermalState:
    return BuildingThermalState(
        zone_states={
            zone_id: ZoneThermalState(
                zone_id,
                air_temperature_c=temperature_c,
                mass_temperature_c=temperature_c,
            )
            for zone_id in zone_ids
        }
    )


def _outdoor_target(
    zone_id: str,
    humidity_ratio: float,
    dry_air_mass_flow_kg_s: float,
) -> MoistureTransportTarget:
    return MoistureTransportTarget(
        target_id=zone_id + "__outdoor",
        target_type=MOISTURE_TRANSPORT_TARGET_OUTDOOR,
        humidity_ratio_kg_kg=humidity_ratio,
        airflow_m3_s=dry_air_mass_flow_kg_s / MOISTURE_AIR_DENSITY_KG_M3,
        dry_air_mass_flow_kg_s=dry_air_mass_flow_kg_s,
        source_zone_id="outdoor",
        source="phase_4_15_outdoor",
    )


def _transport(**targets_by_zone) -> BuildingMoistureTransportResult:
    return BuildingMoistureTransportResult(
        zone_targets={
            zone_id: ZoneMoistureTransportTargets(
                zone_id=zone_id,
                targets=targets,
            )
            for zone_id, targets in targets_by_zone.items()
        }
    )


def _sources(**sources_by_zone) -> BuildingMoistureSourceInputs:
    return BuildingMoistureSourceInputs(sources_by_zone=sources_by_zone)


def _step(
    state: BuildingMoistureState,
    parameters: BuildingMoistureParameters,
    transport: BuildingMoistureTransportResult,
    sources: BuildingMoistureSourceInputs,
    *,
    dt_minutes: float,
    temperature_c: float = 20.0,
):
    result = step_building_moisture_state(
        moisture_state=state,
        building_moisture_parameters=parameters,
        moisture_transport_result=transport,
        moisture_source_inputs=sources,
        thermal_state=_thermal(temperature_c, *state.zone_ids()),
        atmospheric_pressure_pa=PRESSURE_PA,
        dt_minutes=dt_minutes,
    )
    assert result.method == MOISTURE_BUILDING_TIMESTEP_METHOD
    for zone_result in result.zone_results.values():
        assert zone_result.balance_residual_kg_s() == pytest.approx(
            0.0,
            abs=3e-18,
        )
    assert result.balance_residual_kg_s() == pytest.approx(0.0, abs=5e-18)
    return result


def _exact_humidity_ratio(
    initial: float,
    *,
    duration_h: float,
    dry_air_mass_kg: float,
    dry_air_mass_flow_kg_s: float,
    outdoor: float,
    generation_kg_h: float,
) -> float:
    generation_kg_s = generation_kg_h / 3600.0
    if dry_air_mass_flow_kg_s == 0.0:
        return initial + generation_kg_h * duration_h / dry_air_mass_kg
    steady_state = outdoor + generation_kg_s / dry_air_mass_flow_kg_s
    decay = exp(
        -dry_air_mass_flow_kg_s
        / dry_air_mass_kg
        * duration_h
        * 3600.0
    )
    return steady_state + (initial - steady_state) * decay


def test_constant_moisture_source_closes_water_mass_balance() -> None:
    parameters = _parameters(zone=120.0)
    state = _state(zone=0.008)
    source = ZoneMoistureSourceInput(
        zone_id="zone",
        moisture_generation_kg_h=0.06,
        source_type=MOISTURE_SOURCE_PEOPLE,
    )
    result = _step(
        state,
        parameters,
        _transport(zone=[]),
        _sources(zone=[source]),
        dt_minutes=60.0,
    )

    expected = 0.008 + 0.06 / 120.0
    assert result.humidity_ratio_by_zone_kg_kg()["zone"] == pytest.approx(
        expected,
        abs=1e-14,
    )
    assert result.total_storage_change_kg_s() == pytest.approx(
        result.total_generation_kg_s(),
        abs=3e-18,
    )


def test_constant_ventilation_and_source_follow_closed_form_response() -> None:
    dry_air_mass_kg = 120.0
    mass_flow_kg_s = 60.0 / 3600.0
    outdoor = 0.006
    generation_kg_h = 0.06
    parameters = _parameters(zone=dry_air_mass_kg)
    state = _state(zone=0.008)
    transport = _transport(
        zone=[_outdoor_target("zone", outdoor, mass_flow_kg_s)]
    )
    sources = _sources(
        zone=[
            ZoneMoistureSourceInput(
                "zone",
                generation_kg_h,
                MOISTURE_SOURCE_PEOPLE,
            )
        ]
    )

    for _ in range(8 * 12):
        result = _step(
            state,
            parameters,
            transport,
            sources,
            dt_minutes=5.0,
        )
        state = result.updated_moisture_state

    expected = _exact_humidity_ratio(
        0.008,
        duration_h=8.0,
        dry_air_mass_kg=dry_air_mass_kg,
        dry_air_mass_flow_kg_s=mass_flow_kg_s,
        outdoor=outdoor,
        generation_kg_h=generation_kg_h,
    )
    assert state.get_zone_state("zone").humidity_ratio_kg_kg == pytest.approx(
        expected,
        abs=2e-5,
    )


def test_source_removal_produces_analytical_ventilation_decay() -> None:
    dry_air_mass_kg = 120.0
    mass_flow_kg_s = 60.0 / 3600.0
    parameters = _parameters(zone=dry_air_mass_kg)
    state = _state(zone=0.014)
    transport = _transport(
        zone=[_outdoor_target("zone", 0.006, mass_flow_kg_s)]
    )

    for _ in range(6 * 60):
        result = _step(
            state,
            parameters,
            transport,
            _sources(zone=[]),
            dt_minutes=1.0,
        )
        state = result.updated_moisture_state

    expected = _exact_humidity_ratio(
        0.014,
        duration_h=6.0,
        dry_air_mass_kg=dry_air_mass_kg,
        dry_air_mass_flow_kg_s=mass_flow_kg_s,
        outdoor=0.006,
        generation_kg_h=0.0,
    )
    assert state.get_zone_state("zone").humidity_ratio_kg_kg == pytest.approx(
        expected,
        abs=2e-5,
    )


def test_multiple_people_and_cooking_shower_pulses_are_additive() -> None:
    parameters = _parameters(zone=120.0)
    state = _state(zone=0.007)
    pulse_sources = _sources(
        zone=[
            ZoneMoistureSourceInput("zone", 0.055, MOISTURE_SOURCE_PEOPLE),
            ZoneMoistureSourceInput("zone", 0.055, MOISTURE_SOURCE_PEOPLE),
            ZoneMoistureSourceInput("zone", 0.20, MOISTURE_SOURCE_COOKING),
            ZoneMoistureSourceInput("zone", 0.40, MOISTURE_SOURCE_SHOWER),
        ]
    )
    result = _step(
        state,
        parameters,
        _transport(zone=[]),
        pulse_sources,
        dt_minutes=15.0,
    )
    expected_generation_kg_h = 0.71
    expected = 0.007 + expected_generation_kg_h * 0.25 / 120.0

    assert pulse_sources.moisture_generation_kg_h_by_zone()["zone"] == (
        pytest.approx(expected_generation_kg_h)
    )
    assert result.humidity_ratio_by_zone_kg_kg()["zone"] == pytest.approx(
        expected,
        abs=1e-14,
    )

    after_pulse = _step(
        result.updated_moisture_state,
        parameters,
        _transport(zone=[]),
        _sources(zone=[]),
        dt_minutes=15.0,
    )
    assert after_pulse.humidity_ratio_by_zone_kg_kg()["zone"] == pytest.approx(
        expected,
        abs=1e-14,
    )


def test_outdoor_humidity_step_changes_transport_without_hidden_source() -> None:
    parameters = _parameters(zone=120.0)
    state = _state(zone=0.006)
    mass_flow_kg_s = 60.0 / 3600.0
    result = _step(
        state,
        parameters,
        _transport(
            zone=[_outdoor_target("zone", 0.012, mass_flow_kg_s)]
        ),
        _sources(zone=[]),
        dt_minutes=30.0,
    )

    assert 0.006 < result.humidity_ratio_by_zone_kg_kg()["zone"] < 0.012
    assert result.total_generation_kg_s() == 0.0
    assert result.total_storage_change_kg_s() == pytest.approx(
        result.total_transport_rate_kg_s(),
        abs=3e-18,
    )


def test_interzone_moisture_exchange_conserves_total_water_vapour() -> None:
    parameters = _parameters(wet=60.0, dry=120.0)
    state = _state(wet=0.014, dry=0.006)
    mass_flow_kg_s = 36.0 * MOISTURE_AIR_DENSITY_KG_M3 / 3600.0
    transport = _transport(
        wet=[
            MoistureTransportTarget(
                target_id="wet-dry__dry",
                target_type=MOISTURE_TRANSPORT_TARGET_INTERZONE,
                humidity_ratio_kg_kg=0.006,
                airflow_m3_s=36.0 / 3600.0,
                dry_air_mass_flow_kg_s=mass_flow_kg_s,
                source_zone_id="dry",
                source="phase_4_15_interzone",
            )
        ],
        dry=[
            MoistureTransportTarget(
                target_id="wet-dry__wet",
                target_type=MOISTURE_TRANSPORT_TARGET_INTERZONE,
                humidity_ratio_kg_kg=0.014,
                airflow_m3_s=36.0 / 3600.0,
                dry_air_mass_flow_kg_s=mass_flow_kg_s,
                source_zone_id="wet",
                source="phase_4_15_interzone",
            )
        ],
    )
    water_before_kg = 60.0 * 0.014 + 120.0 * 0.006
    result = _step(
        state,
        parameters,
        transport,
        _sources(wet=[], dry=[]),
        dt_minutes=60.0,
    )
    ratios = result.humidity_ratio_by_zone_kg_kg()
    water_after_kg = 60.0 * ratios["wet"] + 120.0 * ratios["dry"]

    assert water_after_kg == pytest.approx(water_before_kg, abs=1e-12)
    assert 0.006 < ratios["dry"] < ratios["wet"] < 0.014
    assert result.total_transport_rate_kg_s() == pytest.approx(0.0, abs=3e-18)


@pytest.mark.parametrize("temperature_c", (5.0, 20.0, 30.0))
@pytest.mark.parametrize("relative_humidity_percent", (20.0, 50.0, 80.0))
def test_humidity_ratio_relative_humidity_round_trip(
    temperature_c: float,
    relative_humidity_percent: float,
) -> None:
    humidity_ratio = humidity_ratio_from_rh(
        relative_humidity_percent,
        temperature_c,
        PRESSURE_PA,
    )
    recovered_rh = relative_humidity_from_humidity_ratio(
        humidity_ratio,
        temperature_c,
        PRESSURE_PA,
    )
    assert recovered_rh == pytest.approx(relative_humidity_percent, abs=1e-12)


def test_annex41_ce2_6_non_buffering_isothermal_limit_is_analytical() -> None:
    volume_m3 = 4.60
    ventilation_ach = 0.64
    temperature_c = 20.5
    outdoor_rh_percent = 51.0
    dry_air_mass_kg = volume_m3 * MOISTURE_AIR_DENSITY_KG_M3
    mass_flow_kg_s = (
        volume_m3
        * ventilation_ach
        * MOISTURE_AIR_DENSITY_KG_M3
        / 3600.0
    )
    outdoor = humidity_ratio_from_rh(
        outdoor_rh_percent,
        temperature_c,
        PRESSURE_PA,
    )
    pulse_generation_kg_h = 0.016
    parameters = _parameters(chamber=dry_air_mass_kg)
    state = _state(chamber=outdoor)
    transport = _transport(
        chamber=[_outdoor_target("chamber", outdoor, mass_flow_kg_s)]
    )
    pulse = _sources(
        chamber=[
            ZoneMoistureSourceInput(
                "chamber",
                pulse_generation_kg_h,
                MOISTURE_SOURCE_SHOWER,
            )
        ]
    )

    for _ in range(round(6.0 * 60.0 / 5.0)):
        result = _step(
            state,
            parameters,
            transport,
            pulse,
            dt_minutes=5.0,
            temperature_c=temperature_c,
        )
        state = result.updated_moisture_state
    expected_after_pulse = _exact_humidity_ratio(
        outdoor,
        duration_h=6.0,
        dry_air_mass_kg=dry_air_mass_kg,
        dry_air_mass_flow_kg_s=mass_flow_kg_s,
        outdoor=outdoor,
        generation_kg_h=pulse_generation_kg_h,
    )
    assert state.get_zone_state("chamber").humidity_ratio_kg_kg == pytest.approx(
        expected_after_pulse,
        abs=3e-5,
    )

    for _ in range(round(18.0 * 60.0 / 5.0)):
        result = _step(
            state,
            parameters,
            transport,
            _sources(chamber=[]),
            dt_minutes=5.0,
            temperature_c=temperature_c,
        )
        state = result.updated_moisture_state
    expected_after_decay = _exact_humidity_ratio(
        expected_after_pulse,
        duration_h=18.0,
        dry_air_mass_kg=dry_air_mass_kg,
        dry_air_mass_flow_kg_s=mass_flow_kg_s,
        outdoor=outdoor,
        generation_kg_h=0.0,
    )
    final_state = state.get_zone_state("chamber")
    assert final_state.humidity_ratio_kg_kg == pytest.approx(
        expected_after_decay,
        abs=3e-5,
    )
    assert final_state.relative_humidity_percent == pytest.approx(
        relative_humidity_from_humidity_ratio(
            final_state.humidity_ratio_kg_kg,
            temperature_c,
            PRESSURE_PA,
        ),
        abs=1e-12,
    )
