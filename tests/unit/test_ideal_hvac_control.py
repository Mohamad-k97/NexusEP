"""Analytical verification of the declared ideal/full-capacity HVAC control."""

from __future__ import annotations

import pytest

from nexusep.abbey.building.controllers import ThermostatController
from nexusep.abbey.building.model import ZoneModel, ZoneState
from nexusep.abbey.building.performance import BuildingPhysicsPerformanceModel
from nexusep.abbey.building.physics.thermal import semi_implicit_temperature_update
from nexusep.abbey.building.systems import (
    ZoneControlCommand,
    ZoneControlState,
    ZoneSystemSpec,
    cooling_power_w_from_zone_control_command,
    heating_power_w_from_zone_control_command,
    hvac_thermal_gain_w_from_zone_control_command,
)

pytestmark = [pytest.mark.unit]
VALIDATION_CATEGORY = "verification"


def _state(temperature_c: float) -> ZoneState:
    return ZoneState(
        zone_id="zone",
        dwelling_id="dwelling",
        building_id="building",
        indoor_temp_c=temperature_c,
    )


def _control() -> ZoneControlState:
    return ZoneControlState(
        zone_id="zone",
        dwelling_id="dwelling",
        building_id="building",
        heating_mode="semi_auto",
        heating_setpoint_c=20.0,
        cooling_mode="semi_auto",
        cooling_setpoint_c=24.0,
        thermostat_deadband_c=1.0,
        ventilation_mode="off",
        lighting_mode="off",
        window_mode="off",
        shading_mode="off",
    )


def _system(**updates: object) -> ZoneSystemSpec:
    values: dict[str, object] = {
        "zone_id": "zone",
        "dwelling_id": "dwelling",
        "building_id": "building",
        "heating_capacity_w": 3_000.0,
        "cooling_capacity_w": 4_000.0,
        "has_heating": True,
        "has_cooling": True,
        "has_ventilation": False,
        "has_lighting": False,
        "has_operable_window": False,
        "has_shading": False,
    }
    values.update(updates)
    return ZoneSystemSpec(**values)


def _command(*, heating: bool = False, cooling: bool = False) -> ZoneControlCommand:
    return ZoneControlCommand(
        zone_id="zone",
        dwelling_id="dwelling",
        building_id="building",
        heating_on=heating,
        heating_power_fraction=1.0 if heating else 0.0,
        cooling_on=cooling,
        cooling_power_fraction=1.0 if cooling else 0.0,
    )


def test_heating_below_setpoint_uses_full_declared_capacity() -> None:
    system = _system()
    command = ThermostatController().step(_state(19.49), _control(), system)

    assert command.heating_on
    assert not command.cooling_on
    assert command.heating_power_fraction == 1.0
    assert heating_power_w_from_zone_control_command(command, system) == 3_000.0
    assert hvac_thermal_gain_w_from_zone_control_command(command, system) == 3_000.0


def test_cooling_above_setpoint_uses_full_declared_capacity() -> None:
    system = _system()
    command = ThermostatController().step(_state(24.51), _control(), system)

    assert command.cooling_on
    assert not command.heating_on
    assert command.cooling_power_fraction == 1.0
    assert cooling_power_w_from_zone_control_command(command, system) == 4_000.0
    assert hvac_thermal_gain_w_from_zone_control_command(command, system) == -4_000.0


def test_deadband_is_off_without_history_and_hysteretic_with_history() -> None:
    controller = ThermostatController()
    control = _control()
    system = _system()

    assert not controller.step(_state(20.0), control, system).heating_on
    assert not controller.step(_state(24.0), control, system).cooling_on

    heating_hold = controller.step(
        _state(20.0), control, system, previous_command=_command(heating=True)
    )
    cooling_hold = controller.step(
        _state(24.0), control, system, previous_command=_command(cooling=True)
    )
    assert heating_hold.heating_on
    assert cooling_hold.cooling_on

    assert not controller.step(
        _state(20.51), control, system, previous_command=heating_hold
    ).heating_on
    assert not controller.step(
        _state(23.49), control, system, previous_command=cooling_hold
    ).cooling_on


def test_unavailable_system_cannot_receive_heating_or_cooling_command() -> None:
    system = _system(
        heating_capacity_w=0.0,
        cooling_capacity_w=0.0,
        has_heating=False,
        has_cooling=False,
    )
    controller = ThermostatController()

    cold = controller.step(_state(-10.0), _control(), system)
    hot = controller.step(_state(50.0), _control(), system)

    assert (cold.heating_on, cold.cooling_on) == (False, False)
    assert (hot.heating_on, hot.cooling_on) == (False, False)
    assert hvac_thermal_gain_w_from_zone_control_command(cold, system) == 0.0
    assert hvac_thermal_gain_w_from_zone_control_command(hot, system) == 0.0


def test_full_capacity_controller_never_exceeds_the_capacity_limit() -> None:
    system = _system(heating_capacity_w=1_234.5, cooling_capacity_w=2_345.6)
    controller = ThermostatController()

    heating = controller.step(_state(-100.0), _control(), system)
    cooling = controller.step(_state(100.0), _control(), system)

    assert heating_power_w_from_zone_control_command(heating, system) == 1_234.5
    assert cooling_power_w_from_zone_control_command(cooling, system) == 2_345.6


def test_command_affects_the_current_interval_without_an_extra_step_delay() -> None:
    """The interval-start state selects a command that changes the next state."""

    system = _system()
    control = _control()
    controller = ThermostatController()
    first_command = controller.step(_state(18.0), control, system)
    first_gain_w = hvac_thermal_gain_w_from_zone_control_command(
        first_command, system
    )

    next_temperature_c = semi_implicit_temperature_update(
        capacity_j_k=900_000.0,
        old_temperature_c=18.0,
        targets=[],
        gain_w=first_gain_w,
        dt_seconds=900.0,
    )
    next_command = controller.step(
        _state(next_temperature_c),
        control,
        system,
        previous_command=first_command,
    )

    assert first_command.heating_on
    assert next_temperature_c == pytest.approx(21.0, abs=1e-12)
    assert not next_command.heating_on


@pytest.mark.parametrize(
    "temperature_c", (-100.0, 19.49, 20.0, 22.0, 24.0, 24.51, 100.0)
)
def test_thermostat_never_commands_simultaneous_heating_and_cooling(
    temperature_c: float,
) -> None:
    command = ThermostatController().step(
        _state(temperature_c), _control(), _system()
    )
    assert not (command.heating_on and command.cooling_on)


def test_power_to_energy_and_cop_accounting_are_exact() -> None:
    model = object.__new__(BuildingPhysicsPerformanceModel)
    zone = ZoneModel(
        zone_id="zone",
        zone_name="Zone",
        dwelling_id="dwelling",
        building_id="building",
    )
    system = _system(
        heating_efficiency_or_cop=0.8,
        cooling_efficiency_or_cop=4.0,
    )

    heating = model._calculate_zone_energy(
        zone_model=zone,
        system_spec=system,
        command=_command(heating=True),
        appliance_energy_wh=0.0,
        lighting_energy_wh=0.0,
        dt_hours=0.25,
    )
    cooling = model._calculate_zone_energy(
        zone_model=zone,
        system_spec=system,
        command=_command(cooling=True),
        appliance_energy_wh=0.0,
        lighting_energy_wh=0.0,
        dt_hours=0.25,
    )

    assert heating.heating_delivered_energy_wh == 750.0
    assert heating.heating_energy_wh == 937.5
    assert heating.hvac_delivered_energy_wh == 750.0
    assert heating.hvac_input_energy_wh == 937.5
    assert cooling.cooling_delivered_energy_wh == 1_000.0
    assert cooling.cooling_energy_wh == 250.0
    assert cooling.hvac_delivered_energy_wh == 1_000.0
    assert cooling.hvac_input_energy_wh == 250.0
