"""Verification of the object engine's graph-owned envelope contract."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nexusep.abbey.building.factory import (
    make_default_family_building,
    make_default_family_physics_graph,
)
from nexusep.abbey.building.performance import BuildingPhysicsPerformanceModel
from nexusep.abbey.building.physics.engine import (
    BuildingPhysicsStepInput,
    run_building_physics_step,
)
from nexusep.abbey.building.physics.graph import BuildingPhysicsGraph
from nexusep.abbey.building.physics.thermal import (
    InterzoneThermalLink,
    ZoneThermalState,
    calculate_simplified_window_solar_gains,
    make_zone_thermal_parameters,
    update_zone_thermal_state_semi_implicit,
)
from nexusep.abbey.building.physics.weather import WeatherState

pytestmark = [pytest.mark.contract]
VALIDATION_CATEGORY = "verification"


def test_default_conditioned_zones_derive_nonzero_envelope_from_graph() -> None:
    building = make_default_family_building()
    graph = make_default_family_physics_graph(building)

    for zone in building.all_zone_models().values():
        assert zone.ua_w_per_k > 0.0  # compatibility input remains inspectable
        assert zone.thermal_envelope_model == "graph_boundaries"
        assert zone.external_wall_area_m2 > 0.0
        assert zone.derived_envelope_ua_w_per_k is not None
        expected_ua = sum(
            float(edge.area_m2) * float(edge.u_value_w_m2k)
            for edge in graph.boundary_connections_for_zone(zone.zone_id)
            if edge.connection_type == "external_wall"
        )
        assert zone.derived_envelope_ua_w_per_k == pytest.approx(expected_ua)
        assert "derived_from_BuildingPhysicsGraph" in zone.envelope_provenance


def test_cold_outdoor_boundary_causes_heat_loss_through_derived_envelope() -> None:
    building = make_default_family_building()
    make_default_family_physics_graph(building)
    zone = next(iter(building.all_zone_models().values()))
    parameters = make_zone_thermal_parameters(zone)
    assert parameters.h_external_w_k > 0.0

    result = update_zone_thermal_state_semi_implicit(
        zone_state=ZoneThermalState(
            zone_id=zone.zone_id,
            air_temperature_c=20.0,
            mass_temperature_c=20.0,
        ),
        zone_parameters=parameters,
        outdoor_temperature_c=-5.0,
        ventilation_h_w_k=0.0,
        dt_minutes=10.0,
    )
    assert result.new_air_temperature_c < result.old_air_temperature_c


def test_window_presence_changes_solar_behavior() -> None:
    building = make_default_family_building()
    graph = make_default_family_physics_graph(building)
    no_windows = BuildingPhysicsGraph(
        building_model=building,
        zone_connections=dict(graph.zone_connections),
        boundary_connections={
            key: value
            for key, value in graph.boundary_connections.items()
            if not value.is_window
        },
    )
    weather = WeatherState(
        datetime=datetime(2025, 1, 1, 12, tzinfo=UTC),
        direct_normal_radiation_w_m2=500.0,
        diffuse_horizontal_radiation_w_m2=100.0,
        global_horizontal_radiation_w_m2=400.0,
    )
    with_windows = calculate_simplified_window_solar_gains(graph, weather)
    without_windows = calculate_simplified_window_solar_gains(no_windows, weather)
    assert with_windows.total_solar_gain_w() > 0.0
    assert without_windows.total_solar_gain_w() == 0.0


def test_connected_zones_exchange_heat_conservatively() -> None:
    link = InterzoneThermalLink(
        link_id="west_to_east",
        connection_id="west_to_east",
        zone_a_id="zone-west",
        zone_b_id="zone-east",
        area_m2=8.0,
        u_value_w_m2k=1.5,
    )
    gain_west = link.heat_gain_to_zone_a_w(25.0, 15.0)
    gain_east = link.heat_gain_to_zone_b_w(25.0, 15.0)
    assert gain_west < 0.0
    assert gain_east > 0.0
    assert gain_west + gain_east == pytest.approx(0.0, abs=1e-12)


def test_incomplete_graph_fails_before_timestep_zero() -> None:
    building = make_default_family_building()
    graph = make_default_family_physics_graph(building)
    missing_edge = next(
        key
        for key, edge in graph.boundary_connections.items()
        if edge.connection_type == "external_wall"
    )
    affected_zone = graph.boundary_connections[missing_edge].zone_id
    del graph.boundary_connections[missing_edge]
    with pytest.raises(ValueError, match=affected_zone):
        graph.validate()


def test_graph_omission_is_not_a_silent_feature_disable() -> None:
    with pytest.raises(ValueError, match="physics_graph is required"):
        BuildingPhysicsPerformanceModel(
            building_model=make_default_family_building(),
            use_physics_engine=True,
        )


def test_enabled_window_feature_requires_an_openable_graph_connection() -> None:
    building = make_default_family_building()
    complete_graph = make_default_family_physics_graph(building)
    graph_without_windows = BuildingPhysicsGraph(
        building_model=building,
        zone_connections=dict(complete_graph.zone_connections),
        boundary_connections={
            connection_id: connection
            for connection_id, connection in complete_graph.boundary_connections.items()
            if not connection.is_window
        },
    )
    specs = {
        zone_id: spec
        for dwelling in building.dwellings.values()
        for zone_id, spec in dwelling.system_specs.items()
    }
    affected_zone = next(
        zone_id
        for zone_id, spec in specs.items()
        if spec.has_operable_window
    )
    with pytest.raises(ValueError, match=affected_zone):
        run_building_physics_step(
            BuildingPhysicsStepInput(
                building_model=building,
                physics_graph=graph_without_windows,
                weather_state=WeatherState(
                    datetime=datetime(2025, 1, 1, tzinfo=UTC)
                ),
                zone_system_specs=specs,
                dt_minutes=10.0,
            )
        )
