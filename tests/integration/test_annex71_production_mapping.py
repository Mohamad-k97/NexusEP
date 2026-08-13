"""Annex 71 canonical mapping and production-adapter regressions.

Validation category: verification of preprocessing and execution semantics.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from nexusep.abbey.building.physics.thermal import make_zone_thermal_parameters
from nexusep.adapters.object_engine import ObjectEngineAdapter
from nexusep.schema.timestep import (
    CanonicalStepContractError,
    PriorZonePhysicalState,
    validate_step_input_for_scenario,
)
from nexusep.validation_data.annex71 import (
    Annex71Interval,
    Annex71ZoneObservation,
    build_annex71_step_input,
    build_canonical_scenario,
    run_object_scenario,
    zone_capacity_fractions,
)
from nexusep.validation_data.annex71_audit import (
    audit_annex71_energy_paths,
    shift_annex71_source_rows,
)

ZONE_IDS = (
    "ground_airbody",
    "kitchen_airbody",
    "sleeping_airbody",
    "attic_airbody",
)


def _record(
    timestamp: datetime,
    temperature_c: float,
    *,
    heating_power_w: float = 0.0,
    internal_gain_w: float = 0.0,
    solar_w_m2: float = 0.0,
) -> Annex71Interval:
    return Annex71Interval(
        timestamp=timestamp,
        outdoor_temperature_c=10.0,
        relative_humidity_fraction=0.5,
        atmospheric_pressure_pa=95_000.0,
        outdoor_co2_ppm=420.0,
        wind_speed_m_s=0.0,
        wind_direction_deg=0.0,
        diffuse_horizontal_radiation_w_m2=solar_w_m2 * 0.25,
        global_horizontal_radiation_w_m2=solar_w_m2,
        rain=False,
        zones=tuple(
            Annex71ZoneObservation(
                zone_id=zone_id,
                air_temperature_c=temperature_c,
                relative_humidity_fraction=0.5,
                heating_power_w=heating_power_w,
                internal_gain_w=internal_gain_w,
                ventilation_supply_temperature_c=10.0,
                ventilation_supply_flow_m3_s=0.0,
            )
            for zone_id in ZONE_IDS
        ),
    )


def test_selected_hourly_alignment_maps_row_timestamp_to_interval_end() -> None:
    end = datetime(2018, 12, 20, 1, tzinfo=ZoneInfo("Europe/Berlin"))
    record = _record(end, 20.0)

    scenario, _graph = build_canonical_scenario((record,))

    assert scenario.simulation_period.start_datetime == end - timedelta(hours=1)
    assert scenario.weather_series[0].timestamp == end - timedelta(hours=1)


def test_four_air_bodies_execute_without_fallback_and_conserve_energy() -> None:
    start = datetime(2018, 12, 20, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    records = tuple(_record(start + timedelta(hours=index), 20.0) for index in range(3))

    result = run_object_scenario(records)

    assert result.engine_name == "object"
    assert set(result.simulated_temperature_c) == set(ZONE_IDS)
    assert result.timestamps == tuple(
        item.timestamp.isoformat() for item in records[1:]
    )
    assert result.fallback_used is False
    assert result.maximum_abs_thermal_balance_residual_w <= 1.0e-7


def test_observation_constrained_energy_audit_closes_steady_no_gain_case() -> None:
    start = datetime(2018, 12, 20, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    records = tuple(_record(start + timedelta(hours=index), 10.0) for index in range(3))

    audit = audit_annex71_energy_paths(records, warmup_timesteps=0)

    assert len(audit.records) == 8
    assert audit.summary["whole_building"]["unexplained_gain_rmse_w"] <= 1.0e-9
    assert all(abs(item.unexplained_air_node_gain_w) <= 1.0e-9 for item in audit.records)


def test_source_row_counterfactual_preserves_targets_and_common_period() -> None:
    start = datetime(2018, 12, 20, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    records = tuple(
        _record(
            start + timedelta(hours=index),
            20.0 + index,
            heating_power_w=100.0 * index,
            internal_gain_w=10.0 * index,
            solar_w_m2=50.0 * index,
        )
        for index in range(5)
    )

    shifted = shift_annex71_source_rows(records, "heating", 1)

    assert [item.timestamp for item in shifted] == [
        records[1].timestamp,
        records[2].timestamp,
        records[3].timestamp,
    ]
    assert shifted[0].zone("attic_airbody").air_temperature_c == 21.0
    assert shifted[0].zone("attic_airbody").heating_power_w == 200.0
    assert shifted[0].zone("attic_airbody").internal_gain_w == 10.0
    assert shifted[0].global_horizontal_radiation_w_m2 == 50.0


def test_capacity_allocation_bases_are_explicit_and_conservative() -> None:
    volume = zone_capacity_fractions("air_volume")
    floor = zone_capacity_fractions("floor_area")

    assert sum(volume.values()) == pytest.approx(1.0)
    assert sum(floor.values()) == pytest.approx(1.0)
    assert floor["attic_airbody"] > volume["attic_airbody"]


def test_roof_window_uses_published_thirty_degree_tilt() -> None:
    timestamp = datetime(2018, 12, 20, 1, tzinfo=ZoneInfo("Europe/Berlin"))

    scenario, graph = build_canonical_scenario((_record(timestamp, 20.0),))
    attic = next(
        zone
        for zone in scenario.building.dwelling.zones
        if zone.zone_id == "attic_airbody"
    )
    roof_surface = next(
        surface
        for surface in attic.surfaces
        if surface.surface_id == "attic_south_roof"
    )
    roof_connection = next(
        connection
        for connection in graph["connections"]
        if connection["connection_type"] == "opening"
        and connection["source_node_id"] == "attic_airbody"
        and connection["azimuth_deg"] == 180.0
    )

    assert roof_surface.tilt_deg == pytest.approx(30.0)
    assert roof_connection["tilt_deg"] == pytest.approx(30.0)
    assert all(
        surface.tilt_deg == pytest.approx(90.0)
        for surface in attic.surfaces
        if surface is not roof_surface
        and surface.surface_id not in {"attic_north_roof"}
    )


def test_published_component_model_exposes_cellar_fabric_and_dynamic_blind() -> None:
    timestamp = datetime(2018, 12, 20, 1, tzinfo=ZoneInfo("Europe/Berlin"))
    scenario, graph = build_canonical_scenario((_record(timestamp, 20.0),))

    surfaces = [
        surface
        for zone in scenario.building.dwelling.zones
        for surface in zone.surfaces
    ]
    openings = [opening for surface in surfaces for opening in surface.openings]
    assert sum(surface.heat_capacity_j_k for surface in surfaces) == pytest.approx(
        155_011_213.4944031
    )
    assert {
        surface.external_boundary_id
        for surface in surfaces
        if surface.surface_id.endswith("floor_to_cellar")
    } == {"cellar_air"}
    west_living = next(
        opening
        for opening in openings
        if opening.opening_id == "window_west_living_type1"
    )
    assert west_living.solar_shading_factor == pytest.approx(1.0)
    assert any(
        connection["external_boundary_id"] == "cellar_air"
        for connection in graph["connections"]
    )
    assert sum(
        float(connection["thermal_bridge_conductance_w_k"])
        for connection in graph["connections"]
        if connection["connection_type"] == "surface"
    ) > 50.0


def test_object_adapter_couples_all_canonical_opaque_mass_to_zone_air() -> None:
    timestamp = datetime(2018, 12, 20, 1, tzinfo=ZoneInfo("Europe/Berlin"))
    scenario, graph = build_canonical_scenario((_record(timestamp, 20.0),))
    adapter = ObjectEngineAdapter(scenario, graph)

    kitchen = next(
        zone
        for zone in scenario.building.dwelling.zones
        if zone.zone_id == "kitchen_airbody"
    )
    expected_area_m2 = sum(
        surface.area_m2
        - sum(opening.area_m2 for opening in surface.openings)
        for surface in kitchen.surfaces
    )
    native_zone = adapter.building_model.all_zone_models()[kitchen.zone_id]
    parameters = make_zone_thermal_parameters(native_zone)

    assert native_zone.effective_thermal_mass_area_m2 == pytest.approx(
        expected_area_m2
    )
    assert parameters.effective_mass_area_m2 == pytest.approx(expected_area_m2)
    assert parameters.effective_mass_area_m2 > (
        native_zone.floor_area_m2 + native_zone.internal_wall_area_m2
    )


def test_named_cellar_boundary_is_required_and_changes_the_solution() -> None:
    start = datetime(2018, 12, 20, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    base = tuple(
        replace(
            _record(start + timedelta(hours=index), 10.0),
            outdoor_temperature_c=0.0,
            cellar_temperature_c=20.0,
        )
        for index in range(3)
    )
    cold_cellar = tuple(replace(item, cellar_temperature_c=0.0) for item in base)

    warm_result = run_object_scenario(base)
    cold_result = run_object_scenario(cold_cellar)
    assert all(
        warm_result.simulated_temperature_c[zone_id][-1]
        > cold_result.simulated_temperature_c[zone_id][-1]
        for zone_id in ("ground_airbody", "kitchen_airbody", "sleeping_airbody")
    )

    scenario, graph = build_canonical_scenario(base[1:], initial_record=base[0])
    prior = tuple(
        PriorZonePhysicalState(
            zone_id=zone.zone_id,
            air_temperature_c=zone.initial_air_temperature_c,
            mean_radiant_temperature_c=zone.initial_mean_radiant_temperature_c,
            relative_humidity_fraction=zone.initial_relative_humidity_fraction,
            co2_ppm=zone.initial_co2_ppm,
        )
        for zone in scenario.building.dwelling.zones
    )
    step = build_annex71_step_input(scenario, graph, base[1], 0, prior)
    blind_states = {
        item.opening_id: item.shading_open_fraction
        for item in step.opening_control_commands
    }
    assert blind_states["window_west_living_type1"] == 0.0
    assert blind_states["window_west_kitchen_type1"] == 0.0
    missing = step.model_copy(update={"external_boundary_states": ()})
    with pytest.raises(CanonicalStepContractError, match="external boundary state"):
        validate_step_input_for_scenario(missing, scenario, graph)


def test_measured_window_and_door_positions_reach_native_controls() -> None:
    end = datetime(2018, 12, 20, 1, tzinfo=ZoneInfo("Europe/Berlin"))
    initial = _record(end - timedelta(hours=1), 20.0)
    operated = replace(
        _record(end, 20.0),
        child1_window_opening_fraction=0.6,
        kitchen_door_opening_fraction=0.0,
    )
    scenario, graph = build_canonical_scenario(
        (operated,), initial_record=initial
    )
    prior = tuple(
        PriorZonePhysicalState(
            zone_id=zone.zone_id,
            air_temperature_c=zone.initial_air_temperature_c,
            mean_radiant_temperature_c=zone.initial_mean_radiant_temperature_c,
            relative_humidity_fraction=zone.initial_relative_humidity_fraction,
            co2_ppm=zone.initial_co2_ppm,
        )
        for zone in scenario.building.dwelling.zones
    )
    step = build_annex71_step_input(scenario, graph, operated, 0, prior)

    result = ObjectEngineAdapter(scenario, graph).run_step(step, include_debug=True)
    assert result.debug is not None
    native = result.debug.engine_fields
    window_id = "opening:window_west_child1_type1"
    assert native["window_operation_inputs"]["opening_fraction_by_window"][
        window_id
    ] == pytest.approx(0.6)
    door_controls = native["airflow_control_inputs"]["door_openings"]
    kitchen_connection = next(
        connection["connection_id"]
        for connection in graph["connections"]
        if connection["boundary_type"] == "interzone"
        and "ground_airbody_to_kitchen_airbody" in connection["surface_ids"]
    )
    assert door_controls[kitchen_connection]["opening_fraction"] == 0.0
