"""Verification tests for explicit HVAC and ventilation thermal paths."""

from __future__ import annotations

import pytest

from nexusep.abbey.building.physics.engine import (
    _add_hvac_command_gains_to_thermal_gains,
)
from nexusep.abbey.building.physics.thermal import (
    ZoneVentilationAirflowInputs,
    ZoneVentilationHeatExchange,
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
    ) == pytest.approx(
        ventilation_conductance_from_airflow_m3_h(200.0) * (5.0 - 20.0)
    )


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
