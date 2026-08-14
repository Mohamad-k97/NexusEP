"""Verification tests for explicit HVAC and ventilation thermal paths."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from nexusep.abbey.building.physics.engine import (
    _add_hvac_command_gains_to_thermal_gains,
)
from nexusep.abbey.building.physics.graph import BoundaryConnection
from nexusep.abbey.building.physics.thermal import (
    STEFAN_BOLTZMANN_W_M2_K4,
    ZoneVentilationAirflowInputs,
    ZoneVentilationHeatExchange,
    calculate_opaque_boundary_radiative_gains_by_zone_w,
    ventilation_conductance_from_airflow_m3_h,
)
from nexusep.abbey.building.systems import ZoneControlCommand, ZoneSystemSpec


def test_mechanical_supply_temperature_is_not_applied_to_infiltration() -> None:
    airflow = ZoneVentilationAirflowInputs(
        zone_id="zone-a",
        infiltration_airflow_m3_h=100.0,
        mechanical_ventilation_flow_m3_h=100.0,
    )
    exchange = ZoneVentilationHeatExchange(
        zone_id="zone-a",
        airflow_inputs=airflow,
        mechanical_supply_temperature_c=10.0,
    )

    assert exchange.effective_supply_temperature_c(0.0) == pytest.approx(5.0)
    assert exchange.heat_gain_from_outdoor_w(
        zone_air_temperature_c=20.0,
        outdoor_temperature_c=0.0,
    ) == pytest.approx(ventilation_conductance_from_airflow_m3_h(200.0) * (5.0 - 20.0))


def test_legacy_ventilation_defaults_to_outdoor_temperature() -> None:
    airflow = ZoneVentilationAirflowInputs(
        zone_id="zone-a",
        mechanical_ventilation_flow_m3_h=100.0,
    )
    exchange = ZoneVentilationHeatExchange(
        zone_id="zone-a",
        airflow_inputs=airflow,
    )

    assert exchange.effective_supply_temperature_c(3.0) == pytest.approx(3.0)
    assert exchange.heat_gain_from_outdoor_w(20.0, 3.0) == pytest.approx(
        ventilation_conductance_from_airflow_m3_h(100.0) * (3.0 - 20.0)
    )


def test_measured_supply_and_exhaust_have_distinct_energy_terms() -> None:
    airflow = ZoneVentilationAirflowInputs(
        zone_id="zone-a",
        infiltration_airflow_m3_h=10.0,
        mechanical_ventilation_flow_m3_h=100.0,
        mechanical_exhaust_flow_m3_h=120.0,
    )
    exchange = ZoneVentilationHeatExchange(
        zone_id="zone-a",
        airflow_inputs=airflow,
        mechanical_supply_temperature_c=15.0,
    )
    expected_w = (
        ventilation_conductance_from_airflow_m3_h(10.0) * (5.0 - 20.0)
        + ventilation_conductance_from_airflow_m3_h(100.0) * 15.0
        - ventilation_conductance_from_airflow_m3_h(120.0) * 20.0
    )

    assert exchange.heat_gain_from_outdoor_w(20.0, 5.0) == pytest.approx(expected_w)


def test_opaque_boundary_longwave_loss_uses_declared_surface_properties() -> None:
    boundary = BoundaryConnection(
        connection_id="wall-a",
        zone_id="zone-a",
        connection_type="external_wall",
        area_m2=10.0,
        orientation_deg=180.0,
        tilt_deg=90.0,
        u_value_w_m2k=0.2,
        exterior_solar_absorptance_fraction=0.0,
        exterior_longwave_emissivity_fraction=1.0,
        exterior_surface_heat_transfer_coefficient_w_m2_k=10.0,
    )
    graph = SimpleNamespace(boundary_connections={"wall-a": boundary})
    weather = SimpleNamespace(
        outdoor_temperature_c=20.0,
        sky_temperature_c=0.0,
        direct_normal_radiation_w_m2=0.0,
        diffuse_horizontal_radiation_w_m2=0.0,
        global_horizontal_radiation_w_m2=0.0,
    )
    expected_w = (
        0.2 * 10.0 / 10.0 * 0.5 * STEFAN_BOLTZMANN_W_M2_K4 * ((273.15**4) - (293.15**4))
    )

    assert calculate_opaque_boundary_radiative_gains_by_zone_w(graph, weather)[
        "zone-a"
    ] == pytest.approx(expected_w)


def test_measured_cardinal_plane_overrides_reconstructed_surface_radiation() -> None:
    boundary = BoundaryConnection(
        connection_id="south-wall",
        zone_id="zone-a",
        connection_type="external_wall",
        area_m2=10.0,
        orientation_deg=180.0,
        tilt_deg=90.0,
        u_value_w_m2k=0.2,
        exterior_solar_absorptance_fraction=1.0,
        exterior_longwave_emissivity_fraction=0.0,
        exterior_surface_heat_transfer_coefficient_w_m2_k=10.0,
    )
    graph = SimpleNamespace(boundary_connections={"south-wall": boundary})
    weather = SimpleNamespace(
        outdoor_temperature_c=20.0,
        sky_temperature_c=20.0,
        south_vertical_radiation_w_m2=100.0,
        direct_normal_radiation_w_m2=0.0,
        diffuse_horizontal_radiation_w_m2=0.0,
        global_horizontal_radiation_w_m2=0.0,
    )

    assert calculate_opaque_boundary_radiative_gains_by_zone_w(
        graph, weather
    )["zone-a"] == pytest.approx(20.0)


def test_hvac_command_preserves_explicit_convective_radiative_split() -> None:
    command = ZoneControlCommand(
        zone_id="zone-a",
        dwelling_id="dwelling-a",
        building_id="building-a",
        heating_on=True,
        heating_power_fraction=0.5,
        heating_convective_fraction=0.7,
    )
    system = ZoneSystemSpec(
        zone_id="zone-a",
        dwelling_id="dwelling-a",
        building_id="building-a",
        heating_capacity_w=1_000.0,
    )

    gains = _add_hvac_command_gains_to_thermal_gains(
        zone_ids=["zone-a"],
        base_thermal_gains=None,
        zone_control_commands={"zone-a": command},
        zone_system_specs={"zone-a": system},
    ).get_zone_gains("zone-a")

    assert gains.total_gain_w() == pytest.approx(500.0)
    assert gains.convective_gain_w() == pytest.approx(350.0)
    assert gains.radiative_gain_w() == pytest.approx(150.0)
