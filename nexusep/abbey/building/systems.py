"""
Building system, control, command, and energy containers for ABBEY.

This module defines:
- zone-level system specifications
- dwelling/building-level system specifications
- control states
- physical control commands
- energy result containers
"""

from dataclasses import dataclass, replace
from typing import Any, Dict, Optional
import copy


VALID_CONTROL_MODES = {
    "off",
    "manual",
    "semi_auto",
    "auto",
}

VALID_SYSTEM_SCOPES = {
    "zone",
    "dwelling",
    "shared",
    "building",
}


# ============================================================
# SYSTEM SPECS
# ============================================================

@dataclass
class ZoneSystemSpec:
    """
    Static system/capability specification for one zone.

    This describes what systems are physically available and their capacities.
    It does not describe what the occupant/controller wants at a given timestep.
    """

    zone_id: str
    dwelling_id: str
    building_id: str

    heating_capacity_w: float = 0.0
    cooling_capacity_w: float = 0.0
    ventilation_flow_m3_h: float = 0.0
    lighting_power_w: float = 0.0

    heating_efficiency_or_cop: float = 1.0
    cooling_efficiency_or_cop: float = 3.0

    has_heating: bool = True
    has_cooling: bool = False
    has_ventilation: bool = True
    has_lighting: bool = True
    has_operable_window: bool = True
    has_shading: bool = True

    # Added in Phase 2.6
    lighting_power_density_w_m2: float = 8.0
    installed_lighting_lux: float = 300.0

    # Added in Phase 2.7
    system_scope: str = "zone"

    def __post_init__(self) -> None:
        _check_nonnegative(self.heating_capacity_w, "heating_capacity_w", self.zone_id)
        _check_nonnegative(self.cooling_capacity_w, "cooling_capacity_w", self.zone_id)
        _check_nonnegative(self.ventilation_flow_m3_h, "ventilation_flow_m3_h", self.zone_id)
        _check_nonnegative(self.lighting_power_w, "lighting_power_w", self.zone_id)

        _check_positive(
            self.heating_efficiency_or_cop,
            "heating_efficiency_or_cop",
            self.zone_id,
        )
        _check_positive(
            self.cooling_efficiency_or_cop,
            "cooling_efficiency_or_cop",
            self.zone_id,
        )

        _check_nonnegative(
            self.lighting_power_density_w_m2,
            "lighting_power_density_w_m2",
            self.zone_id,
        )
        _check_nonnegative(
            self.installed_lighting_lux,
            "installed_lighting_lux",
            self.zone_id,
        )

        _check_scope(self.system_scope, "ZoneSystemSpec", self.zone_id)

    def copy(self, **updates: Any) -> "ZoneSystemSpec":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "dwelling_id": self.dwelling_id,
            "building_id": self.building_id,
            "heating_capacity_w": self.heating_capacity_w,
            "cooling_capacity_w": self.cooling_capacity_w,
            "ventilation_flow_m3_h": self.ventilation_flow_m3_h,
            "lighting_power_w": self.lighting_power_w,
            "heating_efficiency_or_cop": self.heating_efficiency_or_cop,
            "cooling_efficiency_or_cop": self.cooling_efficiency_or_cop,
            "has_heating": self.has_heating,
            "has_cooling": self.has_cooling,
            "has_ventilation": self.has_ventilation,
            "has_lighting": self.has_lighting,
            "has_operable_window": self.has_operable_window,
            "has_shading": self.has_shading,
            "lighting_power_density_w_m2": self.lighting_power_density_w_m2,
            "installed_lighting_lux": self.installed_lighting_lux,
            "system_scope": self.system_scope,
        }

@dataclass
class DwellingSystemSpec:
    """
    Dwelling-level system specification.

    For MVP, this is mostly metadata.
    Later it can represent local dwelling systems or a dwelling served by shared systems.
    """

    dwelling_id: str
    building_id: str

    heating_system_type: str = "dummy_heater"
    cooling_system_type: str = "none"
    ventilation_system_type: str = "natural"
    dhw_system_type: str = "placeholder"

    system_scope: str = "dwelling"

    def __post_init__(self) -> None:
        _check_scope(self.system_scope, "DwellingSystemSpec", self.dwelling_id)

    def copy(self, **updates: Any) -> "DwellingSystemSpec":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dwelling_id": self.dwelling_id,
            "building_id": self.building_id,
            "heating_system_type": self.heating_system_type,
            "cooling_system_type": self.cooling_system_type,
            "ventilation_system_type": self.ventilation_system_type,
            "dhw_system_type": self.dhw_system_type,
            "system_scope": self.system_scope,
        }


@dataclass
class BuildingSystemSpec:
    """
    Building-level system specification.

    For MVP, this is mostly a placeholder for future multifamily/shared systems.
    """

    building_id: str

    has_central_heating: bool = False
    has_central_cooling: bool = False
    has_central_ventilation: bool = False
    has_central_dhw: bool = False

    central_system_type: str = "placeholder"

    def copy(self, **updates: Any) -> "BuildingSystemSpec":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "building_id": self.building_id,
            "has_central_heating": self.has_central_heating,
            "has_central_cooling": self.has_central_cooling,
            "has_central_ventilation": self.has_central_ventilation,
            "has_central_dhw": self.has_central_dhw,
            "central_system_type": self.central_system_type,
        }


# ============================================================
# CONTROL STATE
# ============================================================

@dataclass
class ZoneControlState:
    """
    Control intent/state for one zone.

    This is not the physical command.
    It represents what humans/controllers intend or request.
    """

    zone_id: str
    dwelling_id: str
    building_id: str

    heating_mode: str = "semi_auto"
    heating_setpoint_c: float = 20.0
    manual_heating_on: bool = False

    cooling_mode: str = "off"
    cooling_setpoint_c: float = 26.0
    manual_cooling_on: bool = False
    
    thermostat_deadband_c: float = 0.5

    ventilation_mode: str = "manual"
    manual_ventilation_on: bool = True

    lighting_mode: str = "manual"
    manual_lights_on: bool = False

    window_mode: str = "manual"
    manual_window_open: bool = False

    shading_mode: str = "manual"
    manual_curtain_open: bool = True

    def __post_init__(self) -> None:
        _check_control_mode(self.heating_mode, "heating_mode", self.zone_id)
        _check_control_mode(self.cooling_mode, "cooling_mode", self.zone_id)
        _check_control_mode(self.ventilation_mode, "ventilation_mode", self.zone_id)
        _check_control_mode(self.lighting_mode, "lighting_mode", self.zone_id)
        _check_control_mode(self.window_mode, "window_mode", self.zone_id)
        _check_control_mode(self.shading_mode, "shading_mode", self.zone_id)
        _check_nonnegative(
            self.thermostat_deadband_c,
            "thermostat_deadband_c",
            self.zone_id,
        )

    def copy(self, **updates: Any) -> "ZoneControlState":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "dwelling_id": self.dwelling_id,
            "building_id": self.building_id,
            "heating_mode": self.heating_mode,
            "heating_setpoint_c": self.heating_setpoint_c,
            "manual_heating_on": self.manual_heating_on,
            "cooling_mode": self.cooling_mode,
            "cooling_setpoint_c": self.cooling_setpoint_c,
            "manual_cooling_on": self.manual_cooling_on,
            "thermostat_deadband_c": self.thermostat_deadband_c,
            "ventilation_mode": self.ventilation_mode,
            "manual_ventilation_on": self.manual_ventilation_on,
            "lighting_mode": self.lighting_mode,
            "manual_lights_on": self.manual_lights_on,
            "window_mode": self.window_mode,
            "manual_window_open": self.manual_window_open,
            "shading_mode": self.shading_mode,
            "manual_curtain_open": self.manual_curtain_open,
        }


# ============================================================
# CONTROL COMMAND
# ============================================================

@dataclass
class ZoneControlCommand:
    """
    Physical command sent to the zone systems.

    This is what the controller actually decides the system should do.
    """

    zone_id: str
    dwelling_id: str
    building_id: str

    heating_on: bool = False
    heating_power_fraction: float = 0.0

    cooling_on: bool = False
    cooling_power_fraction: float = 0.0

    ventilation_flow_m3_h: float = 0.0

    lights_on: bool = False
    lighting_power_w: float = 0.0

    window_open: bool = False
    window_opening_fraction: float = 0.0

    curtain_open: bool = True

    def __post_init__(self) -> None:
        _check_fraction(self.heating_power_fraction, "heating_power_fraction", self.zone_id)
        _check_fraction(self.cooling_power_fraction, "cooling_power_fraction", self.zone_id)
        _check_fraction(self.window_opening_fraction, "window_opening_fraction", self.zone_id)
        _check_nonnegative(self.ventilation_flow_m3_h, "ventilation_flow_m3_h", self.zone_id)
        _check_nonnegative(self.lighting_power_w, "lighting_power_w", self.zone_id)

    def copy(self, **updates: Any) -> "ZoneControlCommand":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "dwelling_id": self.dwelling_id,
            "building_id": self.building_id,
            "heating_on": self.heating_on,
            "heating_power_fraction": self.heating_power_fraction,
            "cooling_on": self.cooling_on,
            "cooling_power_fraction": self.cooling_power_fraction,
            "ventilation_flow_m3_h": self.ventilation_flow_m3_h,
            "lights_on": self.lights_on,
            "lighting_power_w": self.lighting_power_w,
            "window_open": self.window_open,
            "window_opening_fraction": self.window_opening_fraction,
            "curtain_open": self.curtain_open,
        }


# ============================================================
# ENERGY RESULTS
# ============================================================

@dataclass
class ZoneEnergyResult:
    zone_id: str
    dwelling_id: str
    building_id: str

    heating_energy_wh: float = 0.0
    cooling_energy_wh: float = 0.0
    lighting_energy_wh: float = 0.0
    appliance_energy_wh: float = 0.0
    total_energy_wh: Optional[float] = None

    def __post_init__(self) -> None:
        _check_nonnegative(self.heating_energy_wh, "heating_energy_wh", self.zone_id)
        _check_nonnegative(self.cooling_energy_wh, "cooling_energy_wh", self.zone_id)
        _check_nonnegative(self.lighting_energy_wh, "lighting_energy_wh", self.zone_id)
        _check_nonnegative(self.appliance_energy_wh, "appliance_energy_wh", self.zone_id)

        if self.total_energy_wh is None:
            self.total_energy_wh = (
                self.heating_energy_wh
                + self.cooling_energy_wh
                + self.lighting_energy_wh
                + self.appliance_energy_wh
            )

    def copy(self, **updates: Any) -> "ZoneEnergyResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "dwelling_id": self.dwelling_id,
            "building_id": self.building_id,
            "heating_energy_wh": self.heating_energy_wh,
            "cooling_energy_wh": self.cooling_energy_wh,
            "lighting_energy_wh": self.lighting_energy_wh,
            "appliance_energy_wh": self.appliance_energy_wh,
            "total_energy_wh": self.total_energy_wh,
        }


@dataclass
class DwellingEnergyResult:
    dwelling_id: str
    building_id: str

    heating_energy_wh: float = 0.0
    cooling_energy_wh: float = 0.0
    lighting_energy_wh: float = 0.0
    appliance_energy_wh: float = 0.0
    total_energy_wh: Optional[float] = None

    def __post_init__(self) -> None:
        _check_nonnegative(self.heating_energy_wh, "heating_energy_wh", self.dwelling_id)
        _check_nonnegative(self.cooling_energy_wh, "cooling_energy_wh", self.dwelling_id)
        _check_nonnegative(self.lighting_energy_wh, "lighting_energy_wh", self.dwelling_id)
        _check_nonnegative(self.appliance_energy_wh, "appliance_energy_wh", self.dwelling_id)

        if self.total_energy_wh is None:
            self.total_energy_wh = (
                self.heating_energy_wh
                + self.cooling_energy_wh
                + self.lighting_energy_wh
                + self.appliance_energy_wh
            )

    @classmethod
    def from_zone_results(
        cls,
        dwelling_id: str,
        building_id: str,
        zone_results: Dict[str, ZoneEnergyResult],
    ) -> "DwellingEnergyResult":
        return cls(
            dwelling_id=dwelling_id,
            building_id=building_id,
            heating_energy_wh=sum(r.heating_energy_wh for r in zone_results.values()),
            cooling_energy_wh=sum(r.cooling_energy_wh for r in zone_results.values()),
            lighting_energy_wh=sum(r.lighting_energy_wh for r in zone_results.values()),
            appliance_energy_wh=sum(r.appliance_energy_wh for r in zone_results.values()),
        )

    def copy(self, **updates: Any) -> "DwellingEnergyResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dwelling_id": self.dwelling_id,
            "building_id": self.building_id,
            "heating_energy_wh": self.heating_energy_wh,
            "cooling_energy_wh": self.cooling_energy_wh,
            "lighting_energy_wh": self.lighting_energy_wh,
            "appliance_energy_wh": self.appliance_energy_wh,
            "total_energy_wh": self.total_energy_wh,
        }


@dataclass
class BuildingEnergyResult:
    building_id: str

    heating_energy_wh: float = 0.0
    cooling_energy_wh: float = 0.0
    lighting_energy_wh: float = 0.0
    appliance_energy_wh: float = 0.0
    shared_system_energy_wh: float = 0.0
    total_energy_wh: Optional[float] = None

    def __post_init__(self) -> None:
        _check_nonnegative(self.heating_energy_wh, "heating_energy_wh", self.building_id)
        _check_nonnegative(self.cooling_energy_wh, "cooling_energy_wh", self.building_id)
        _check_nonnegative(self.lighting_energy_wh, "lighting_energy_wh", self.building_id)
        _check_nonnegative(self.appliance_energy_wh, "appliance_energy_wh", self.building_id)
        _check_nonnegative(self.shared_system_energy_wh, "shared_system_energy_wh", self.building_id)

        if self.total_energy_wh is None:
            self.total_energy_wh = (
                self.heating_energy_wh
                + self.cooling_energy_wh
                + self.lighting_energy_wh
                + self.appliance_energy_wh
                + self.shared_system_energy_wh
            )

    @classmethod
    def from_dwelling_results(
        cls,
        building_id: str,
        dwelling_results: Dict[str, DwellingEnergyResult],
        shared_system_energy_wh: float = 0.0,
    ) -> "BuildingEnergyResult":
        return cls(
            building_id=building_id,
            heating_energy_wh=sum(r.heating_energy_wh for r in dwelling_results.values()),
            cooling_energy_wh=sum(r.cooling_energy_wh for r in dwelling_results.values()),
            lighting_energy_wh=sum(r.lighting_energy_wh for r in dwelling_results.values()),
            appliance_energy_wh=sum(r.appliance_energy_wh for r in dwelling_results.values()),
            shared_system_energy_wh=shared_system_energy_wh,
        )

    def copy(self, **updates: Any) -> "BuildingEnergyResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "building_id": self.building_id,
            "heating_energy_wh": self.heating_energy_wh,
            "cooling_energy_wh": self.cooling_energy_wh,
            "lighting_energy_wh": self.lighting_energy_wh,
            "appliance_energy_wh": self.appliance_energy_wh,
            "shared_system_energy_wh": self.shared_system_energy_wh,
            "total_energy_wh": self.total_energy_wh,
        }


# ============================================================
# VALIDATION HELPERS
# ============================================================

def _check_positive(value: float, field_name: str, object_id: str) -> None:
    if value <= 0:
        raise ValueError(
            field_name
            + " must be positive for "
            + object_id
            + ". Got: "
            + str(value)
        )

def _check_control_mode(value: str, field_name: str, object_id: str) -> None:
    if value not in VALID_CONTROL_MODES:
        raise ValueError(
            "Invalid "
            + field_name
            + " for "
            + object_id
            + ": "
            + str(value)
            + ". Valid modes: "
            + str(sorted(VALID_CONTROL_MODES))
        )


def _check_scope(value: str, class_name: str, object_id: str) -> None:
    if value not in VALID_SYSTEM_SCOPES:
        raise ValueError(
            "Invalid system_scope for "
            + class_name
            + " "
            + object_id
            + ": "
            + str(value)
            + ". Valid scopes: "
            + str(sorted(VALID_SYSTEM_SCOPES))
        )


def _check_nonnegative(value: float, field_name: str, object_id: str) -> None:
    if value < 0:
        raise ValueError(
            field_name
            + " must be non-negative for "
            + object_id
            + ". Got: "
            + str(value)
        )


def _check_fraction(value: float, field_name: str, object_id: str) -> None:
    if value < 0.0 or value > 1.0:
        raise ValueError(
            field_name
            + " must be between 0 and 1 for "
            + object_id
            + ". Got: "
            + str(value)
        )