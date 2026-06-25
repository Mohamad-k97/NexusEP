"""
Building controller logic for ABBEY.

Controllers convert:

    ZoneControlState  ->  ZoneControlCommand

Meaning:
- ZoneControlState = intent/request/mode
- ZoneControlCommand = physical command sent to systems
"""

from typing import Any, Optional

from nexusep.abbey.building.model import ZoneState
from nexusep.abbey.building.systems import (
    ZoneSystemSpec,
    ZoneControlState,
    ZoneControlCommand,
    constrain_zone_control_command_to_system_spec,
)

THERMOSTAT_CONTROL_MODES = {
    "semi_auto",
    "auto",
    "bms",
}

BMS_CONTROL_MODES = {
    "auto",
    "bms",
}

class ManualController:
    """
    Manual controller.

    Human intent directly becomes physical command.
    """

    def step(
        self,
        zone_state: ZoneState,
        control_state: ZoneControlState,
        system_spec: ZoneSystemSpec,
        previous_command: Optional[ZoneControlCommand] = None,
        context: Optional[dict] = None,
    ) -> ZoneControlCommand:
        heating_on = (
            system_spec.has_heating
            and control_state.heating_mode == "manual"
            and control_state.manual_heating_on
        )

        cooling_on = (
            system_spec.has_cooling
            and control_state.cooling_mode == "manual"
            and control_state.manual_cooling_on
        )

        ventilation_on = (
            system_spec.has_ventilation
            and control_state.ventilation_mode == "manual"
            and control_state.manual_ventilation_on
        )

        lights_on = (
            system_spec.has_lighting
            and control_state.lighting_mode == "manual"
            and control_state.manual_lights_on
        )

        window_open = (
            system_spec.has_operable_window
            and control_state.window_mode == "manual"
            and control_state.manual_window_open
        )

        curtain_open = (
            system_spec.has_shading
            and control_state.shading_mode == "manual"
            and control_state.manual_curtain_open
        )

        command = ZoneControlCommand(
            zone_id=control_state.zone_id,
            dwelling_id=control_state.dwelling_id,
            building_id=control_state.building_id,
            heating_on=heating_on,
            heating_power_fraction=1.0 if heating_on else 0.0,
            cooling_on=cooling_on,
            cooling_power_fraction=1.0 if cooling_on else 0.0,
            ventilation_flow_m3_h=(
                system_spec.ventilation_flow_m3_h if ventilation_on else 0.0
            ),
            lights_on=lights_on,
            lighting_power_w=system_spec.lighting_power_w if lights_on else 0.0,
            window_open=window_open,
            window_opening_fraction=1.0 if window_open else 0.0,
            curtain_open=curtain_open,
        )

        return constrain_zone_control_command_to_system_spec(
            command=command,
            system_spec=system_spec,
        ).command

class ThermostatController:
    """
    Semi-automatic thermostat controller.

    Human/controller sets setpoints.
    Thermostat decides final heating/cooling operation using deadband.
    """

    def __init__(self, deadband_c: float = 0.5):
        if deadband_c < 0:
            raise ValueError("deadband_c must be non-negative.")

        self.deadband_c = float(deadband_c)

    def step(
        self,
        zone_state: ZoneState,
        control_state: ZoneControlState,
        system_spec: ZoneSystemSpec,
        previous_command: Optional[ZoneControlCommand] = None,
        context: Optional[dict] = None,
    ) -> ZoneControlCommand:
        temp = float(zone_state.indoor_temp_c)

        heating_on = self._decide_heating(
            temp_c=temp,
            control_state=control_state,
            system_spec=system_spec,
            previous_command=previous_command,
        )

        cooling_on = self._decide_cooling(
            temp_c=temp,
            control_state=control_state,
            system_spec=system_spec,
            previous_command=previous_command,
        )

        # Avoid simultaneous heating and cooling.
        if heating_on and cooling_on:
            heating_error = abs(control_state.heating_setpoint_c - temp)
            cooling_error = abs(temp - control_state.cooling_setpoint_c)

            if heating_error >= cooling_error:
                cooling_on = False
            else:
                heating_on = False

        ventilation_flow_m3_h = self._decide_ventilation(
            control_state=control_state,
            system_spec=system_spec,
            zone_state=zone_state,
        )

        lights_on = self._decide_lights(
            control_state=control_state,
            system_spec=system_spec,
            zone_state=zone_state,
        )

        window_open = self._decide_window(
            control_state=control_state,
            system_spec=system_spec,
        )

        curtain_open = self._decide_curtain(
            control_state=control_state,
            system_spec=system_spec,
        )

        command = ZoneControlCommand(
            zone_id=control_state.zone_id,
            dwelling_id=control_state.dwelling_id,
            building_id=control_state.building_id,
            heating_on=heating_on,
            heating_power_fraction=1.0 if heating_on else 0.0,
            cooling_on=cooling_on,
            cooling_power_fraction=1.0 if cooling_on else 0.0,
            ventilation_flow_m3_h=ventilation_flow_m3_h,
            lights_on=lights_on,
            lighting_power_w=system_spec.lighting_power_w if lights_on else 0.0,
            window_open=window_open,
            window_opening_fraction=1.0 if window_open else 0.0,
            curtain_open=curtain_open,
        )

        return constrain_zone_control_command_to_system_spec(
            command=command,
            system_spec=system_spec,
        ).command

    def _deadband_for_control_state(
        self,
        control_state: ZoneControlState,
    ) -> float:
        value = getattr(control_state, "thermostat_deadband_c", self.deadband_c)

        if value is None:
            value = self.deadband_c

        value = float(value)

        if value < 0.0:
            return 0.0

        return value
    def _decide_heating(
        self,
        temp_c: float,
        control_state: ZoneControlState,
        system_spec: ZoneSystemSpec,
        previous_command: Optional[ZoneControlCommand],
    ) -> bool:
        if not system_spec.has_heating:
            return False

        if control_state.heating_mode == "off":
            return False

        if control_state.heating_mode == "manual":
            return bool(control_state.manual_heating_on)

        if control_state.heating_mode in THERMOSTAT_CONTROL_MODES:
            deadband_c = self._deadband_for_control_state(control_state)
            half_band = 0.5 * deadband_c

            turn_on_below_c = control_state.heating_setpoint_c - half_band
            turn_off_above_c = control_state.heating_setpoint_c + half_band

            if temp_c < turn_on_below_c:
                return True

            if temp_c > turn_off_above_c:
                return False

            if previous_command is not None:
                return bool(previous_command.heating_on)

            return False

        return False

    def _decide_cooling(
        self,
        temp_c: float,
        control_state: ZoneControlState,
        system_spec: ZoneSystemSpec,
        previous_command: Optional[ZoneControlCommand],
    ) -> bool:
        if not system_spec.has_cooling:
            return False

        if control_state.cooling_mode == "off":
            return False

        if control_state.cooling_mode == "manual":
            return bool(control_state.manual_cooling_on)

        if control_state.cooling_mode in THERMOSTAT_CONTROL_MODES:
            deadband_c = self._deadband_for_control_state(control_state)
            half_band = 0.5 * deadband_c

            turn_on_above_c = control_state.cooling_setpoint_c + half_band
            turn_off_below_c = control_state.cooling_setpoint_c - half_band

            if temp_c > turn_on_above_c:
                return True

            if temp_c < turn_off_below_c:
                return False

            if previous_command is not None:
                return bool(previous_command.cooling_on)

            return False

        return False

    def _decide_ventilation(
        self,
        control_state: ZoneControlState,
        system_spec: ZoneSystemSpec,
        zone_state: ZoneState,
    ) -> float:
        if not system_spec.has_ventilation:
            return 0.0

        if control_state.ventilation_mode == "off":
            return 0.0

        if control_state.ventilation_mode == "manual":
            if control_state.manual_ventilation_on:
                return system_spec.ventilation_flow_m3_h
            return 0.0

        if control_state.ventilation_mode in THERMOSTAT_CONTROL_MODES:
            if zone_state.number_of_people > 0:
                return system_spec.ventilation_flow_m3_h
            return 0.25 * system_spec.ventilation_flow_m3_h

        return 0.0

    def _decide_lights(
        self,
        control_state: ZoneControlState,
        system_spec: ZoneSystemSpec,
        zone_state: ZoneState,
    ) -> bool:
        if not system_spec.has_lighting:
            return False

        if control_state.lighting_mode == "off":
            return False

        if control_state.lighting_mode == "manual":
            return bool(control_state.manual_lights_on)

        if control_state.lighting_mode in THERMOSTAT_CONTROL_MODES:
            return (
                zone_state.number_of_people > 0
                and zone_state.indoor_daylight < 0.35
            )

        return False

    def _decide_window(
        self,
        control_state: ZoneControlState,
        system_spec: ZoneSystemSpec,
    ) -> bool:
        if not system_spec.has_operable_window:
            return False

        if control_state.window_mode == "off":
            return False

        if control_state.window_mode == "manual":
            return bool(control_state.manual_window_open)

        # v0.3: no smart window logic yet.
        if control_state.window_mode in THERMOSTAT_CONTROL_MODES:
            return bool(control_state.manual_window_open)

        return False

    def _decide_curtain(
        self,
        control_state: ZoneControlState,
        system_spec: ZoneSystemSpec,
    ) -> bool:
        if not system_spec.has_shading:
            return True

        if control_state.shading_mode == "off":
            return True

        if control_state.shading_mode == "manual":
            return bool(control_state.manual_curtain_open)

        # v0.3: no smart shading logic yet.
        if control_state.shading_mode in THERMOSTAT_CONTROL_MODES:
            return bool(control_state.manual_curtain_open)

        return True


class SimpleBMSController:
    """
    Placeholder BMS controller.

    Phase 10.7 behavior:
    - BMS/auto mode is available.
    - It delegates to the thermostat controller for now.
    - It does not optimize.
    - It does not apply physical effects directly.

    Future:
    - occupancy-predictive control
    - weather-predictive control
    - tariff-aware operation
    - centralized/shared HVAC coordination
    - load shifting
    """

    controller_family = "bms_placeholder"
    controller_strategy = "delegate_to_thermostat"

    def __init__(self, deadband_c: float = 0.5):
        self.thermostat = ThermostatController(deadband_c=deadband_c)

    def step(
        self,
        zone_state: ZoneState,
        control_state: ZoneControlState,
        system_spec: ZoneSystemSpec,
        previous_command: Optional[ZoneControlCommand] = None,
        context: Optional[dict] = None,
    ) -> ZoneControlCommand:
        return self.thermostat.step(
            zone_state=zone_state,
            control_state=control_state,
            system_spec=system_spec,
            previous_command=previous_command,
            context=context,
        )

def controller_for_control_state(
    control_state: ZoneControlState,
    deadband_c: Optional[float] = None,
) -> Any:
    """
    Return a controller suitable for the current control state.

    manual:
        direct human intent -> command

    semi_auto:
        setpoint thermostat -> command

    auto/bms:
        placeholder BMS -> currently delegates to thermostat -> command

    The returned controller still produces ZoneControlCommand.
    It never applies physical effects directly.
    """

    if deadband_c is None:
        deadband_c = getattr(control_state, "thermostat_deadband_c", 0.5)

    deadband_c = float(deadband_c)

    modes = {
        control_state.heating_mode,
        control_state.cooling_mode,
        control_state.ventilation_mode,
        control_state.lighting_mode,
        control_state.window_mode,
        control_state.shading_mode,
    }

    if modes.intersection(BMS_CONTROL_MODES):
        return SimpleBMSController(deadband_c=deadband_c)

    if "semi_auto" in modes:
        return ThermostatController(deadband_c=deadband_c)

    return ManualController()