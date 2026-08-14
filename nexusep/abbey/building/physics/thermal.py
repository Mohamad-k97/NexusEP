"""
ABBEY thermal model architecture.

Phase 4.1:
- formally defines the thermal modelling decision
- no thermal solver yet
- no heat balance calculation yet
- no timestep update yet

Decision:
    ABBEY thermal model = multi-zone 2-node reduced RC model
    inspired by ISO-style 5R1C thinking.

Each zone has:
    - air node
    - mass node

Boundary/source dependencies:
    - WeatherState provides outside boundary conditions
    - BuildingPhysicsGraph provides topology
    - ZoneModel provides thermal parameters
"""

import copy
import math
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional

import numpy as np

from nexusep.abbey.building.physics.solar import (
    calculate_surface_solar_irradiance,
)


THERMAL_MODEL_FAMILY = "reduced_order_rc"
THERMAL_REFERENCE_CONCEPT = "iso_style_5r1c"
THERMAL_SPATIAL_RESOLUTION = "zone"
THERMAL_MULTIZONE_MODE = "multizone"
THERMAL_NODE_STRUCTURE = "two_node_air_mass"

THERMAL_PATH_AIR_MASS = "air_mass"
THERMAL_PATH_OUTSIDE = "outside"
THERMAL_PATH_EXTERNAL_BOUNDARY = "external_boundary"
THERMAL_PATH_INTERZONE = "interzone"
THERMAL_PATH_VENTILATION = "ventilation"
THERMAL_PATH_HVAC = "hvac_input"

THERMAL_PATH_GROUND = "ground_later"
THERMAL_PATH_SHARED_SPACE = "shared_space_later"
THERMAL_PATH_SLAB = "slab_later"


THERMAL_AIR_NODE = "air"
THERMAL_MASS_NODE = "mass"

THERMAL_MODEL_DECISION = (
    "multi_zone_2_node_reduced_rc_model_inspired_by_5r1c"
)

THERMAL_AIR_DENSITY_KG_M3 = 1.2
THERMAL_AIR_SPECIFIC_HEAT_J_KG_K = 1005.0

DEFAULT_AIR_MASS_COUPLING_W_M2K = 3.45
DEFAULT_MIN_AIR_MASS_CONDUCTANCE_W_K = 0.1
DEFAULT_THERMAL_BRIDGE_FACTOR = 1.0

DEFAULT_INTERZONE_U_VALUE_W_M2K = 1.8

DEFAULT_INTERZONE_INTERNAL_WALL_U_VALUE_W_M2K = 1.8
DEFAULT_INTERZONE_FLOOR_CEILING_U_VALUE_W_M2K = 1.5
DEFAULT_INTERZONE_CLOSED_DOOR_U_VALUE_W_M2K = 2.5
DEFAULT_INTERZONE_GENERIC_U_VALUE_W_M2K = 1.8

DEFAULT_INTERZONE_DOOR_AREA_M2 = 1.7
DEFAULT_INTERZONE_OPEN_DOOR_EFFECTIVE_U_VALUE_W_M2K = 15.0

VENTILATION_SOURCE_INFILTRATION = "default_infiltration"
VENTILATION_SOURCE_MECHANICAL = "mechanical_ventilation"
VENTILATION_SOURCE_WINDOW_OPENING = "window_opening_later"
VENTILATION_SOURCE_INTERZONE_AIRFLOW = "interzone_airflow_later"

GAIN_SOURCE_PEOPLE = "people"
GAIN_SOURCE_APPLIANCES = "appliances"
GAIN_SOURCE_LIGHTING = "lighting"
GAIN_SOURCE_SOLAR = "solar"
GAIN_SOURCE_HVAC = "hvac"

DEFAULT_PEOPLE_CONVECTIVE_FRACTION = 0.50
DEFAULT_APPLIANCE_CONVECTIVE_FRACTION = 0.70
DEFAULT_LIGHTING_CONVECTIVE_FRACTION = 0.60
DEFAULT_SOLAR_CONVECTIVE_FRACTION = 0.10
DEFAULT_HVAC_CONVECTIVE_FRACTION = 1.00

DEFAULT_WINDOW_SOLAR_HEAT_GAIN_COEFFICIENT = 0.50
DEFAULT_WINDOW_SHADING_FACTOR = 1.00
DEFAULT_WINDOW_FRAME_FRACTION = 0.20
DEFAULT_CURTAIN_SOLAR_REDUCTION_FACTOR = 0.35

HVAC_MODE_OFF = "off"
HVAC_MODE_HEATING = "heating"
HVAC_MODE_COOLING = "cooling"
HVAC_MODE_UNAVAILABLE = "unavailable"

DEFAULT_HEATING_SETPOINT_C = 20.0
DEFAULT_COOLING_SETPOINT_C = 26.0
DEFAULT_THERMOSTAT_DEADBAND_C = 0.5

THERMAL_SOLUTION_METHOD = "semi_implicit_backward_euler_style"
DEFAULT_THERMAL_DT_MINUTES = 15.0

THERMAL_WINDOW_BOUNDARY_SOURCE = "BuildingWindowBoundaryResult"
THERMAL_AIRFLOW_NETWORK_SOURCE = "BuildingAirflowNetwork"
THERMAL_PHASE8_WINDOW_COMPATIBILITY_MODE = "phase8_window_boundary_optional"

THERMAL_SOLAR_GAIN_SOURCE_WINDOW_BOUNDARY = (
    "BuildingWindowBoundaryResult + WeatherState"
)
THERMAL_SOLAR_GAIN_SOURCE_PLANE_OF_ARRAY = (
    "NREL_SPA_position + isotropic_plane_of_array + WindowBoundaryResult"
)
THERMAL_SOLAR_GAIN_SOURCE_MEASURED_VERTICAL_PLANE = (
    "measured_cardinal_vertical_plane + WindowBoundaryResult"
)
STEFAN_BOLTZMANN_W_M2_K4 = 5.670374419e-8

THERMAL_VENTILATION_SOURCE_AIRFLOW_NETWORK = (
    "BuildingAirflowNetwork"
)

def _clamp_unit_interval(value: Any) -> float:
    value = float(value)

    if value < 0.0:
        return 0.0

    if value > 1.0:
        return 1.0

    return value


@dataclass
class ThermalArchitectureDecision:
    """
    Formal architecture decision for ABBEY thermal modelling.

    This is intentionally not a solver.
    It only locks the modelling structure before implementation.
    """

    model_family: str = THERMAL_MODEL_FAMILY
    reference_concept: str = THERMAL_REFERENCE_CONCEPT
    spatial_resolution: str = THERMAL_SPATIAL_RESOLUTION
    multizone_mode: str = THERMAL_MULTIZONE_MODE
    node_structure: str = THERMAL_NODE_STRUCTURE

    zone_nodes: List[str] = None

    outside_boundary_source: str = "WeatherState"
    topology_source: str = "BuildingPhysicsGraph"
    thermal_parameter_source: str = "ZoneModel"

    is_full_iso_5r1c_copy: bool = False

    decision: str = THERMAL_MODEL_DECISION

    def __post_init__(self) -> None:
        if self.zone_nodes is None:
            self.zone_nodes = [
                THERMAL_AIR_NODE,
                THERMAL_MASS_NODE,
            ]

        self.model_family = str(self.model_family).strip().lower()
        self.reference_concept = str(self.reference_concept).strip().lower()
        self.spatial_resolution = str(self.spatial_resolution).strip().lower()
        self.multizone_mode = str(self.multizone_mode).strip().lower()
        self.node_structure = str(self.node_structure).strip().lower()
        self.decision = str(self.decision).strip().lower()

        self._validate()

    def _validate(self) -> None:
        if self.model_family != THERMAL_MODEL_FAMILY:
            raise ValueError(
                "Thermal model_family must be "
                + THERMAL_MODEL_FAMILY
                + "."
            )

        if self.reference_concept != THERMAL_REFERENCE_CONCEPT:
            raise ValueError(
                "Thermal reference_concept must be "
                + THERMAL_REFERENCE_CONCEPT
                + "."
            )

        if self.spatial_resolution != THERMAL_SPATIAL_RESOLUTION:
            raise ValueError(
                "Thermal spatial_resolution must be zone."
            )

        if self.multizone_mode != THERMAL_MULTIZONE_MODE:
            raise ValueError(
                "Thermal model must be multizone."
            )

        if self.node_structure != THERMAL_NODE_STRUCTURE:
            raise ValueError(
                "Thermal node_structure must be "
                + THERMAL_NODE_STRUCTURE
                + "."
            )

        required_nodes = {
            THERMAL_AIR_NODE,
            THERMAL_MASS_NODE,
        }

        if set(self.zone_nodes) != required_nodes:
            raise ValueError(
                "Each thermal zone must have exactly air and mass nodes."
            )

        if self.outside_boundary_source != "WeatherState":
            raise ValueError(
                "outside_boundary_source must be WeatherState."
            )

        if self.topology_source != "BuildingPhysicsGraph":
            raise ValueError(
                "topology_source must be BuildingPhysicsGraph."
            )

        if self.thermal_parameter_source != "ZoneModel":
            raise ValueError(
                "thermal_parameter_source must be ZoneModel."
            )

        if self.is_full_iso_5r1c_copy:
            raise ValueError(
                "ABBEY thermal model is inspired by 5R1C, not a full ISO 5R1C copy."
            )

    def copy(self, **updates: Any) -> "ThermalArchitectureDecision":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_family": self.model_family,
            "reference_concept": self.reference_concept,
            "spatial_resolution": self.spatial_resolution,
            "multizone_mode": self.multizone_mode,
            "node_structure": self.node_structure,
            "zone_nodes": list(self.zone_nodes),
            "outside_boundary_source": self.outside_boundary_source,
            "topology_source": self.topology_source,
            "thermal_parameter_source": self.thermal_parameter_source,
            "is_full_iso_5r1c_copy": self.is_full_iso_5r1c_copy,
            "decision": self.decision,
        }


DEFAULT_THERMAL_ARCHITECTURE = ThermalArchitectureDecision()

@dataclass
class ZoneThermalState:
    """
    Dynamic thermal state of one zone.

    Phase 4.2:
    - air node temperature
    - mass node temperature

    No heat balance calculation here.
    """

    zone_id: str
    air_temperature_c: float = 20.0
    mass_temperature_c: float = 20.0

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneThermalState.zone_id cannot be empty.")

        self.air_temperature_c = float(self.air_temperature_c)
        self.mass_temperature_c = float(self.mass_temperature_c)

    def copy(self, **updates: Any) -> "ZoneThermalState":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "air_temperature_c": self.air_temperature_c,
            "mass_temperature_c": self.mass_temperature_c,
        }


@dataclass
class BuildingThermalState:
    """
    Dynamic thermal state of the full building.

    Stores one ZoneThermalState per thermal zone.
    """

    zone_states: Dict[str, ZoneThermalState] = field(default_factory=dict)

    def __post_init__(self) -> None:
        cleaned = {}

        for zone_id, state in self.zone_states.items():
            if not isinstance(state, ZoneThermalState):
                raise TypeError(
                    "BuildingThermalState.zone_states must contain "
                    "ZoneThermalState objects. Invalid zone: "
                    + str(zone_id)
                )

            if zone_id != state.zone_id:
                raise ValueError(
                    "BuildingThermalState key "
                    + str(zone_id)
                    + " does not match ZoneThermalState.zone_id "
                    + str(state.zone_id)
                )

            cleaned[zone_id] = state

        self.zone_states = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_states.keys())

    def has_zone(self, zone_id: str) -> bool:
        return zone_id in self.zone_states

    def get_zone_state(self, zone_id: str) -> ZoneThermalState:
        if zone_id not in self.zone_states:
            raise KeyError(
                "Thermal state for zone "
                + zone_id
                + " not found."
            )

        return self.zone_states[zone_id]

    def set_zone_state(
        self,
        zone_id: str,
        zone_state: ZoneThermalState,
    ) -> None:
        if zone_id != zone_state.zone_id:
            raise ValueError(
                "zone_id does not match zone_state.zone_id."
            )

        self.zone_states[zone_id] = zone_state

    def copy(self, **updates: Any) -> "BuildingThermalState":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_states": {
                zone_id: zone_state.to_dict()
                for zone_id, zone_state in self.zone_states.items()
            }
        }
    
@dataclass
class ZoneThermalParameters:
    """
    Derived thermal parameters for one zone.

    These are calculated from ZoneModel inputs.

    Conductance form is used internally:

        H = U * A      [W/K]

    This is not a solver.
    """

    zone_id: str

    c_air_j_k: float
    c_mass_j_k: float

    h_air_mass_w_k: float
    h_external_w_k: float
    h_interzone_w_k: float
    h_ventilation_w_k: float

    air_volume_m3: float
    infiltration_ach: float

    floor_area_m2: float
    effective_mass_area_m2: float
    external_wall_area_m2: float
    internal_wall_area_m2: float

    thermal_bridge_factor: float = DEFAULT_THERMAL_BRIDGE_FACTOR

    source: str = "ZoneModel"

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneThermalParameters.zone_id cannot be empty.")

        self.c_air_j_k = _positive_float(
            self.c_air_j_k,
            "c_air_j_k",
            self.zone_id,
        )

        self.c_mass_j_k = _positive_float(
            self.c_mass_j_k,
            "c_mass_j_k",
            self.zone_id,
        )

        self.h_air_mass_w_k = _non_negative_float(
            self.h_air_mass_w_k,
            "h_air_mass_w_k",
            self.zone_id,
        )

        if self.h_air_mass_w_k <= 0.0:
            self.h_air_mass_w_k = DEFAULT_MIN_AIR_MASS_CONDUCTANCE_W_K

        self.h_external_w_k = _non_negative_float(
            self.h_external_w_k,
            "h_external_w_k",
            self.zone_id,
        )

        self.h_interzone_w_k = _non_negative_float(
            self.h_interzone_w_k,
            "h_interzone_w_k",
            self.zone_id,
        )

        self.h_ventilation_w_k = _non_negative_float(
            self.h_ventilation_w_k,
            "h_ventilation_w_k",
            self.zone_id,
        )

        self.air_volume_m3 = _positive_float(
            self.air_volume_m3,
            "air_volume_m3",
            self.zone_id,
        )

        self.infiltration_ach = _non_negative_float(
            self.infiltration_ach,
            "infiltration_ach",
            self.zone_id,
        )

        self.floor_area_m2 = _positive_float(
            self.floor_area_m2,
            "floor_area_m2",
            self.zone_id,
        )

        self.effective_mass_area_m2 = _positive_float(
            self.effective_mass_area_m2,
            "effective_mass_area_m2",
            self.zone_id,
        )

        self.external_wall_area_m2 = _non_negative_float(
            self.external_wall_area_m2,
            "external_wall_area_m2",
            self.zone_id,
        )

        self.internal_wall_area_m2 = _non_negative_float(
            self.internal_wall_area_m2,
            "internal_wall_area_m2",
            self.zone_id,
        )

        self.thermal_bridge_factor = _non_negative_float(
            self.thermal_bridge_factor,
            "thermal_bridge_factor",
            self.zone_id,
        )

    def copy(self, **updates: Any) -> "ZoneThermalParameters":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "c_air_j_k": self.c_air_j_k,
            "c_mass_j_k": self.c_mass_j_k,
            "h_air_mass_w_k": self.h_air_mass_w_k,
            "h_external_w_k": self.h_external_w_k,
            "h_interzone_w_k": self.h_interzone_w_k,
            "h_ventilation_w_k": self.h_ventilation_w_k,
            "air_volume_m3": self.air_volume_m3,
            "infiltration_ach": self.infiltration_ach,
            "floor_area_m2": self.floor_area_m2,
            "effective_mass_area_m2": self.effective_mass_area_m2,
            "external_wall_area_m2": self.external_wall_area_m2,
            "internal_wall_area_m2": self.internal_wall_area_m2,
            "thermal_bridge_factor": self.thermal_bridge_factor,
            "source": self.source,
        }
    
@dataclass
class ThermalGainSplit:
    """
    Convective/radiative split of a sensible thermal gain.

    convective -> air node
    radiative  -> mass node
    """

    convective_fraction: float
    radiative_fraction: float

    def __post_init__(self) -> None:
        self.convective_fraction = _clamp_unit_interval(
            self.convective_fraction
        )

        self.radiative_fraction = _clamp_unit_interval(
            self.radiative_fraction
        )

        total = self.convective_fraction + self.radiative_fraction

        if abs(total - 1.0) > 1e-9:
            raise ValueError(
                "ThermalGainSplit fractions must sum to 1.0. Got "
                + str(total)
            )

    def split_gain_w(self, gain_w: float) -> Dict[str, float]:
        gain_w = float(gain_w)

        return {
            "convective_gain_w": gain_w * self.convective_fraction,
            "radiative_gain_w": gain_w * self.radiative_fraction,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "convective_fraction": self.convective_fraction,
            "radiative_fraction": self.radiative_fraction,
        }


DEFAULT_PEOPLE_GAIN_SPLIT = ThermalGainSplit(
    convective_fraction=DEFAULT_PEOPLE_CONVECTIVE_FRACTION,
    radiative_fraction=1.0 - DEFAULT_PEOPLE_CONVECTIVE_FRACTION,
)

DEFAULT_APPLIANCE_GAIN_SPLIT = ThermalGainSplit(
    convective_fraction=DEFAULT_APPLIANCE_CONVECTIVE_FRACTION,
    radiative_fraction=1.0 - DEFAULT_APPLIANCE_CONVECTIVE_FRACTION,
)

DEFAULT_LIGHTING_GAIN_SPLIT = ThermalGainSplit(
    convective_fraction=DEFAULT_LIGHTING_CONVECTIVE_FRACTION,
    radiative_fraction=1.0 - DEFAULT_LIGHTING_CONVECTIVE_FRACTION,
)

DEFAULT_SOLAR_GAIN_SPLIT = ThermalGainSplit(
    convective_fraction=DEFAULT_SOLAR_CONVECTIVE_FRACTION,
    radiative_fraction=1.0 - DEFAULT_SOLAR_CONVECTIVE_FRACTION,
)

DEFAULT_HVAC_GAIN_SPLIT = ThermalGainSplit(
    convective_fraction=DEFAULT_HVAC_CONVECTIVE_FRACTION,
    radiative_fraction=1.0 - DEFAULT_HVAC_CONVECTIVE_FRACTION,
)

@dataclass
class ZoneHVACInput:
    """
    Clean HVAC input for one zone.

    Agent-friendly design:
    - thermal.py does not import controllers, agents, or actions
    - ZoneSystemSpec and ZoneControlState are translated into this object
    - HVAC enters the thermal model as sensible gain:
        heating = positive gain
        cooling = negative gain
    """

    zone_id: str

    has_heating: bool = False
    has_cooling: bool = False

    heating_setpoint_c: float = DEFAULT_HEATING_SETPOINT_C
    cooling_setpoint_c: float = DEFAULT_COOLING_SETPOINT_C

    max_heating_power_w: float = 0.0
    max_cooling_power_w: float = 0.0

    thermostat_deadband_c: float = DEFAULT_THERMOSTAT_DEADBAND_C

    source: str = "ZoneSystemSpec + ZoneControlState"

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneHVACInput.zone_id cannot be empty.")

        self.heating_setpoint_c = float(self.heating_setpoint_c)
        self.cooling_setpoint_c = float(self.cooling_setpoint_c)

        self.max_heating_power_w = _non_negative_float(
            self.max_heating_power_w,
            "max_heating_power_w",
            self.zone_id,
        )

        self.max_cooling_power_w = _non_negative_float(
            self.max_cooling_power_w,
            "max_cooling_power_w",
            self.zone_id,
        )

        self.thermostat_deadband_c = _non_negative_float(
            self.thermostat_deadband_c,
            "thermostat_deadband_c",
            self.zone_id,
        )

        if self.heating_setpoint_c >= self.cooling_setpoint_c:
            raise ValueError(
                "heating_setpoint_c must be lower than cooling_setpoint_c "
                "for zone "
                + self.zone_id
            )

        if not self.has_heating:
            self.max_heating_power_w = 0.0

        if not self.has_cooling:
            self.max_cooling_power_w = 0.0

    def heating_activation_temperature_c(self) -> float:
        return self.heating_setpoint_c - 0.5 * self.thermostat_deadband_c

    def cooling_activation_temperature_c(self) -> float:
        return self.cooling_setpoint_c + 0.5 * self.thermostat_deadband_c

    def copy(self, **updates: Any) -> "ZoneHVACInput":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "has_heating": self.has_heating,
            "has_cooling": self.has_cooling,
            "heating_setpoint_c": self.heating_setpoint_c,
            "cooling_setpoint_c": self.cooling_setpoint_c,
            "max_heating_power_w": self.max_heating_power_w,
            "max_cooling_power_w": self.max_cooling_power_w,
            "thermostat_deadband_c": self.thermostat_deadband_c,
            "heating_activation_temperature_c": self.heating_activation_temperature_c(),
            "cooling_activation_temperature_c": self.cooling_activation_temperature_c(),
            "source": self.source,
        }


    
    
@dataclass
class ZoneThermalGainSource:
    """
    One thermal gain source for one zone.

    gain_w is sensible heat only.
    Positive gain_w heats the zone.
    Negative gain_w cools the zone, mainly used for HVAC cooling.
    """

    zone_id: str
    source_type: str
    gain_w: float = 0.0
    split: ThermalGainSplit = None
    source: str = ""

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneThermalGainSource.zone_id cannot be empty.")

        if not self.source_type:
            raise ValueError("ZoneThermalGainSource.source_type cannot be empty.")

        self.source_type = str(self.source_type).strip().lower()
        self.gain_w = float(self.gain_w)

        if self.split is None:
            self.split = default_gain_split_for_source_type(self.source_type)

        if not isinstance(self.split, ThermalGainSplit):
            raise TypeError(
                "ZoneThermalGainSource.split must be ThermalGainSplit."
            )

    def convective_gain_w(self) -> float:
        return self.split.split_gain_w(self.gain_w)["convective_gain_w"]

    def radiative_gain_w(self) -> float:
        return self.split.split_gain_w(self.gain_w)["radiative_gain_w"]

    def copy(self, **updates: Any) -> "ZoneThermalGainSource":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "source_type": self.source_type,
            "gain_w": self.gain_w,
            "convective_gain_w": self.convective_gain_w(),
            "radiative_gain_w": self.radiative_gain_w(),
            "split": self.split.to_dict(),
            "source": self.source,
        }
    
@dataclass
class ZoneThermalGains:
    """
    All thermal gains entering one zone during one timestep.

    Convective gains go to air node.
    Radiative gains go to mass node.
    """

    zone_id: str
    sources: List[ZoneThermalGainSource] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneThermalGains.zone_id cannot be empty.")

        cleaned = []

        for source in self.sources:
            if not isinstance(source, ZoneThermalGainSource):
                raise TypeError(
                    "ZoneThermalGains.sources must contain ZoneThermalGainSource objects."
                )

            if source.zone_id != self.zone_id:
                raise ValueError(
                    "Gain source zone_id "
                    + source.zone_id
                    + " does not match container zone_id "
                    + self.zone_id
                )

            cleaned.append(source)

        self.sources = cleaned

    def add_source(self, source: ZoneThermalGainSource) -> None:
        if source.zone_id != self.zone_id:
            raise ValueError(
                "Cannot add gain source for zone "
                + source.zone_id
                + " to zone "
                + self.zone_id
            )

        self.sources.append(source)

    def total_gain_w(self) -> float:
        return sum(source.gain_w for source in self.sources)

    def convective_gain_w(self) -> float:
        return sum(source.convective_gain_w() for source in self.sources)

    def radiative_gain_w(self) -> float:
        return sum(source.radiative_gain_w() for source in self.sources)

    def gains_by_source_type_w(self) -> Dict[str, float]:
        out = {}

        for source in self.sources:
            out[source.source_type] = (
                out.get(source.source_type, 0.0)
                + source.gain_w
            )

        return out

    def copy(self, **updates: Any) -> "ZoneThermalGains":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "total_gain_w": self.total_gain_w(),
            "convective_gain_w": self.convective_gain_w(),
            "radiative_gain_w": self.radiative_gain_w(),
            "gains_by_source_type_w": self.gains_by_source_type_w(),
            "sources": [
                source.to_dict()
                for source in self.sources
            ],
        }

@dataclass
class ThermalTemperatureTarget:
    """
    A temperature target connected to a thermal node through conductance H.

    Example:
        outside air
        adjacent zone air
        zone mass node
    """

    target_id: str
    target_type: str
    temperature_c: float
    h_w_k: float

    def __post_init__(self) -> None:
        if not self.target_id:
            raise ValueError("ThermalTemperatureTarget.target_id cannot be empty.")

        if not self.target_type:
            raise ValueError("ThermalTemperatureTarget.target_type cannot be empty.")

        self.temperature_c = float(self.temperature_c)

        self.h_w_k = _non_negative_float(
            self.h_w_k,
            "h_w_k",
            self.target_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id": self.target_id,
            "target_type": self.target_type,
            "temperature_c": self.temperature_c,
            "h_w_k": self.h_w_k,
        }




@dataclass
class BuildingThermalGains:
    """
    Thermal gains for all zones at one timestep.

    This is the clean coupling object between:
    - agents / occupancy
    - appliances / actions
    - lighting
    - solar
    - HVAC control

    and the thermal solver.

    thermal.py does not import agent modules.
    """

    zone_gains: Dict[str, ZoneThermalGains] = field(default_factory=dict)

    def __post_init__(self) -> None:
        cleaned = {}

        for zone_id, gains in self.zone_gains.items():
            if not isinstance(gains, ZoneThermalGains):
                raise TypeError(
                    "BuildingThermalGains.zone_gains must contain ZoneThermalGains objects."
                )

            if zone_id != gains.zone_id:
                raise ValueError(
                    "BuildingThermalGains key "
                    + zone_id
                    + " does not match gains.zone_id "
                    + gains.zone_id
                )

            cleaned[zone_id] = gains

        self.zone_gains = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_gains.keys())

    def get_zone_gains(self, zone_id: str) -> ZoneThermalGains:
        if zone_id not in self.zone_gains:
            return ZoneThermalGains(zone_id=zone_id)

        return self.zone_gains[zone_id]

    def set_zone_gains(self, zone_id: str, gains: ZoneThermalGains) -> None:
        if zone_id != gains.zone_id:
            raise ValueError("zone_id does not match gains.zone_id.")

        self.zone_gains[zone_id] = gains

    def convective_gains_by_zone_w(self) -> Dict[str, float]:
        return {
            zone_id: gains.convective_gain_w()
            for zone_id, gains in self.zone_gains.items()
        }

    def radiative_gains_by_zone_w(self) -> Dict[str, float]:
        return {
            zone_id: gains.radiative_gain_w()
            for zone_id, gains in self.zone_gains.items()
        }

    def total_gains_by_zone_w(self) -> Dict[str, float]:
        return {
            zone_id: gains.total_gain_w()
            for zone_id, gains in self.zone_gains.items()
        }

    def copy(self, **updates: Any) -> "BuildingThermalGains":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_gains": {
                zone_id: gains.to_dict()
                for zone_id, gains in self.zone_gains.items()
            }
        }


@dataclass
class BuildingThermalParameters:
    """
    Thermal parameters for all zones in the building.
    """

    zone_parameters: Dict[str, ZoneThermalParameters] = field(default_factory=dict)

    def __post_init__(self) -> None:
        cleaned = {}

        for zone_id, parameters in self.zone_parameters.items():
            if not isinstance(parameters, ZoneThermalParameters):
                raise TypeError(
                    "BuildingThermalParameters.zone_parameters must contain "
                    "ZoneThermalParameters objects. Invalid zone: "
                    + str(zone_id)
                )

            if zone_id != parameters.zone_id:
                raise ValueError(
                    "BuildingThermalParameters key "
                    + str(zone_id)
                    + " does not match ZoneThermalParameters.zone_id "
                    + str(parameters.zone_id)
                )

            cleaned[zone_id] = parameters

        self.zone_parameters = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_parameters.keys())

    def has_zone(self, zone_id: str) -> bool:
        return zone_id in self.zone_parameters

    def get_zone_parameters(self, zone_id: str) -> ZoneThermalParameters:
        if zone_id not in self.zone_parameters:
            raise KeyError(
                "Thermal parameters for zone "
                + zone_id
                + " not found."
            )

        return self.zone_parameters[zone_id]

    def copy(self, **updates: Any) -> "BuildingThermalParameters":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_parameters": {
                zone_id: parameters.to_dict()
                for zone_id, parameters in self.zone_parameters.items()
            }
        }
    
@dataclass
class ThermalConductancePath:
    """
    One heat-transfer path represented as conductance H [W/K].

    ABBEY uses conductance internally:

        H = U * A      [W/K]
        R = 1 / H      [K/W]

    This is not a heat-flow calculation yet.
    """

    path_id: str
    path_type: str

    from_zone_id: str
    from_node: str = THERMAL_AIR_NODE

    to_zone_id: Optional[str] = None
    to_node: Optional[str] = None

    boundary: str = ""

    h_w_k: float = 0.0

    is_symmetric: bool = False
    is_active: bool = True

    source: str = ""

    def __post_init__(self) -> None:
        if not self.path_id:
            raise ValueError("ThermalConductancePath.path_id cannot be empty.")

        if not self.path_type:
            raise ValueError("ThermalConductancePath.path_type cannot be empty.")

        if not self.from_zone_id:
            raise ValueError("ThermalConductancePath.from_zone_id cannot be empty.")

        if not self.from_node:
            raise ValueError("ThermalConductancePath.from_node cannot be empty.")

        self.h_w_k = _non_negative_float(
            self.h_w_k,
            "h_w_k",
            self.from_zone_id,
        )

    def resistance_k_w(self) -> Optional[float]:
        if self.h_w_k <= 0.0:
            return None

        return 1.0 / self.h_w_k

    def copy(self, **updates: Any) -> "ThermalConductancePath":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path_id": self.path_id,
            "path_type": self.path_type,
            "from_zone_id": self.from_zone_id,
            "from_node": self.from_node,
            "to_zone_id": self.to_zone_id,
            "to_node": self.to_node,
            "boundary": self.boundary,
            "h_w_k": self.h_w_k,
            "resistance_k_w": self.resistance_k_w(),
            "is_symmetric": self.is_symmetric,
            "is_active": self.is_active,
            "source": self.source,
        }


@dataclass
class ZoneThermalConductances:
    """
    Conductance paths attached to one zone.

    These are the thermal links used later by the solver.
    """

    zone_id: str
    paths: Dict[str, ThermalConductancePath] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneThermalConductances.zone_id cannot be empty.")

        cleaned = {}

        for path_id, path in self.paths.items():
            if not isinstance(path, ThermalConductancePath):
                raise TypeError(
                    "ZoneThermalConductances.paths must contain "
                    "ThermalConductancePath objects."
                )

            if path.from_zone_id != self.zone_id:
                raise ValueError(
                    "Thermal path "
                    + path_id
                    + " belongs to zone "
                    + path.from_zone_id
                    + " but is stored under zone "
                    + self.zone_id
                )

            cleaned[path_id] = path

        self.paths = cleaned

    def add_path(self, path: ThermalConductancePath) -> None:
        if path.from_zone_id != self.zone_id:
            raise ValueError(
                "Cannot add path from zone "
                + path.from_zone_id
                + " to conductance container for zone "
                + self.zone_id
            )

        self.paths[path.path_id] = path

    def paths_by_type(self, path_type: str) -> List[ThermalConductancePath]:
        return [
            path
            for path in self.paths.values()
            if path.path_type == path_type
        ]

    def total_h_by_type(self, path_type: str) -> float:
        return sum(
            path.h_w_k
            for path in self.paths_by_type(path_type)
            if path.is_active
        )

    def total_active_h_w_k(self) -> float:
        return sum(
            path.h_w_k
            for path in self.paths.values()
            if path.is_active
        )

    def copy(self, **updates: Any) -> "ZoneThermalConductances":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "paths": {
                path_id: path.to_dict()
                for path_id, path in self.paths.items()
            },
            "total_active_h_w_k": self.total_active_h_w_k(),
        }


@dataclass
class BuildingThermalConductanceNetwork:
    """
    Conductance network for the building thermal model.

    Stores zone-level conductance paths.
    Interzone symmetry is handled in Phase 4.5.
    """

    zone_conductances: Dict[str, ZoneThermalConductances] = field(default_factory=dict)

    def __post_init__(self) -> None:
        cleaned = {}

        for zone_id, conductances in self.zone_conductances.items():
            if not isinstance(conductances, ZoneThermalConductances):
                raise TypeError(
                    "BuildingThermalConductanceNetwork.zone_conductances must contain "
                    "ZoneThermalConductances objects."
                )

            if zone_id != conductances.zone_id:
                raise ValueError(
                    "BuildingThermalConductanceNetwork key "
                    + zone_id
                    + " does not match conductance zone_id "
                    + conductances.zone_id
                )

            cleaned[zone_id] = conductances

        self.zone_conductances = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_conductances.keys())

    def get_zone_conductances(self, zone_id: str) -> ZoneThermalConductances:
        if zone_id not in self.zone_conductances:
            raise KeyError(
                "Thermal conductances for zone "
                + zone_id
                + " not found."
            )

        return self.zone_conductances[zone_id]

    def copy(self, **updates: Any) -> "BuildingThermalConductanceNetwork":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_conductances": {
                zone_id: conductances.to_dict()
                for zone_id, conductances in self.zone_conductances.items()
            }
        }

@dataclass
class ZoneIdealHVACResult:
    """
    Ideal bang-bang HVAC result for one zone.

    Sign convention:
        heating_power_w >= 0
        cooling_power_w >= 0
        hvac_gain_w = heating_power_w - cooling_power_w

    Therefore:
        heating gives positive thermal gain
        cooling gives negative thermal gain
    """

    zone_id: str
    mode: str = HVAC_MODE_OFF

    heating_power_w: float = 0.0
    cooling_power_w: float = 0.0

    hvac_gain_w: float = 0.0

    heating_energy_wh: float = 0.0
    cooling_energy_wh: float = 0.0

    zone_air_temperature_c: float = 20.0

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneIdealHVACResult.zone_id cannot be empty.")

        self.heating_power_w = _non_negative_float(
            self.heating_power_w,
            "heating_power_w",
            self.zone_id,
        )

        self.cooling_power_w = _non_negative_float(
            self.cooling_power_w,
            "cooling_power_w",
            self.zone_id,
        )

        self.hvac_gain_w = float(self.hvac_gain_w)

        self.heating_energy_wh = _non_negative_float(
            self.heating_energy_wh,
            "heating_energy_wh",
            self.zone_id,
        )

        self.cooling_energy_wh = _non_negative_float(
            self.cooling_energy_wh,
            "cooling_energy_wh",
            self.zone_id,
        )

        self.zone_air_temperature_c = float(self.zone_air_temperature_c)

    def to_gain_source(self) -> ZoneThermalGainSource:
        return ZoneThermalGainSource(
            zone_id=self.zone_id,
            source_type=GAIN_SOURCE_HVAC,
            gain_w=self.hvac_gain_w,
            source="ideal_hvac",
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "mode": self.mode,
            "heating_power_w": self.heating_power_w,
            "cooling_power_w": self.cooling_power_w,
            "hvac_gain_w": self.hvac_gain_w,
            "heating_energy_wh": self.heating_energy_wh,
            "cooling_energy_wh": self.cooling_energy_wh,
            "zone_air_temperature_c": self.zone_air_temperature_c,
        }


@dataclass
class BuildingIdealHVACResult:
    """
    Ideal HVAC results for all zones at one timestep.
    """

    zone_results: Dict[str, ZoneIdealHVACResult] = field(default_factory=dict)

    def __post_init__(self) -> None:
        cleaned = {}

        for zone_id, result in self.zone_results.items():
            if not isinstance(result, ZoneIdealHVACResult):
                raise TypeError(
                    "BuildingIdealHVACResult.zone_results must contain "
                    "ZoneIdealHVACResult objects."
                )

            if zone_id != result.zone_id:
                raise ValueError(
                    "BuildingIdealHVACResult key "
                    + zone_id
                    + " does not match result.zone_id "
                    + result.zone_id
                )

            cleaned[zone_id] = result

        self.zone_results = cleaned

    def hvac_gains_by_zone_w(self) -> Dict[str, float]:
        return {
            zone_id: result.hvac_gain_w
            for zone_id, result in self.zone_results.items()
        }

    def heating_energy_by_zone_wh(self) -> Dict[str, float]:
        return {
            zone_id: result.heating_energy_wh
            for zone_id, result in self.zone_results.items()
        }

    def cooling_energy_by_zone_wh(self) -> Dict[str, float]:
        return {
            zone_id: result.cooling_energy_wh
            for zone_id, result in self.zone_results.items()
        }

    def total_heating_energy_wh(self) -> float:
        return sum(
            result.heating_energy_wh
            for result in self.zone_results.values()
        )

    def total_cooling_energy_wh(self) -> float:
        return sum(
            result.cooling_energy_wh
            for result in self.zone_results.values()
        )

    def to_thermal_gains(
        self,
        all_zone_ids: Optional[List[str]] = None,
    ) -> BuildingThermalGains:
        hvac_by_zone = self.hvac_gains_by_zone_w()

        if all_zone_ids is None:
            all_zone_ids = list(hvac_by_zone.keys())

        return make_building_thermal_gains(
            zone_ids=all_zone_ids,
            hvac_gains_by_zone_w=hvac_by_zone,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_heating_energy_wh": self.total_heating_energy_wh(),
            "total_cooling_energy_wh": self.total_cooling_energy_wh(),
            "hvac_gains_by_zone_w": self.hvac_gains_by_zone_w(),
            "zone_results": {
                zone_id: result.to_dict()
                for zone_id, result in self.zone_results.items()
            },
        }
@dataclass
class InterzoneThermalLink:
    """
    Symmetric thermal link between two adjacent zones.

    Heat-flow sign convention:

        q_to_a_w = H_ab * (T_b - T_a)
        q_to_b_w = -q_to_a_w

    Positive value means heat gain by that zone.
    """

    link_id: str
    connection_id: str

    zone_a_id: str
    zone_b_id: str

    connection_type: str = "generic_interzone"

    area_m2: float = 0.0
    u_value_w_m2k: float = DEFAULT_INTERZONE_U_VALUE_W_M2K
    h_w_k: float = 0.0

    is_openable: bool = False
    open_fraction: float = 0.0
    max_opening_area_m2: Optional[float] = None

    source: str = "ZoneConnection"

    def __post_init__(self) -> None:
        if not self.link_id:
            raise ValueError("InterzoneThermalLink.link_id cannot be empty.")

        if not self.connection_id:
            raise ValueError("InterzoneThermalLink.connection_id cannot be empty.")

        if not self.zone_a_id:
            raise ValueError("InterzoneThermalLink.zone_a_id cannot be empty.")

        if not self.zone_b_id:
            raise ValueError("InterzoneThermalLink.zone_b_id cannot be empty.")

        if self.zone_a_id == self.zone_b_id:
            raise ValueError(
                "InterzoneThermalLink cannot connect a zone to itself: "
                + self.zone_a_id
            )

        self.area_m2 = _non_negative_float(
            self.area_m2,
            "area_m2",
            self.link_id,
        )

        self.u_value_w_m2k = _non_negative_float(
            self.u_value_w_m2k,
            "u_value_w_m2k",
            self.link_id,
        )

        if self.h_w_k <= 0.0:
            self.h_w_k = conductance_from_u_area(
                u_value_w_m2k=self.u_value_w_m2k,
                area_m2=self.area_m2,
            )

        self.h_w_k = _non_negative_float(
            self.h_w_k,
            "h_w_k",
            self.link_id,
        )
        self.open_fraction = _clamp_unit_interval(self.open_fraction)

        if self.max_opening_area_m2 is not None:
            self.max_opening_area_m2 = _non_negative_float(
                self.max_opening_area_m2,
                "max_opening_area_m2",
                self.link_id,
            )
    def heat_gain_to_zone_a_w(
        self,
        zone_a_air_temperature_c: float,
        zone_b_air_temperature_c: float,
    ) -> float:
        return self.h_w_k * (
            float(zone_b_air_temperature_c)
            - float(zone_a_air_temperature_c)
        )

    def heat_gain_to_zone_b_w(
        self,
        zone_a_air_temperature_c: float,
        zone_b_air_temperature_c: float,
    ) -> float:
        return -self.heat_gain_to_zone_a_w(
            zone_a_air_temperature_c=zone_a_air_temperature_c,
            zone_b_air_temperature_c=zone_b_air_temperature_c,
        )

    def copy(self, **updates: Any) -> "InterzoneThermalLink":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "link_id": self.link_id,
            "connection_id": self.connection_id,
            "zone_a_id": self.zone_a_id,
            "zone_b_id": self.zone_b_id,
            "connection_type": self.connection_type,
            "area_m2": self.area_m2,
            "u_value_w_m2k": self.u_value_w_m2k,
            "h_w_k": self.h_w_k,
            "is_openable": self.is_openable,
            "open_fraction": self.open_fraction,
            "max_opening_area_m2": self.max_opening_area_m2,
            "resistance_k_w": resistance_from_conductance(self.h_w_k),
            "source": self.source,
        }


@dataclass
class InterzoneThermalFlowRecord:
    """
    Heat-flow record for one interzone thermal link.

    Positive q_to_* means heat gain by that zone.
    """

    link_id: str
    connection_id: str

    zone_a_id: str
    zone_b_id: str

    h_w_k: float

    zone_a_air_temperature_c: float
    zone_b_air_temperature_c: float

    q_to_zone_a_w: float
    q_to_zone_b_w: float

    connection_type: str = "generic_interzone"
    is_openable: bool = False
    open_fraction: float = 0.0
    
    def __post_init__(self) -> None:
        self.h_w_k = float(self.h_w_k)
        self.zone_a_air_temperature_c = float(self.zone_a_air_temperature_c)
        self.zone_b_air_temperature_c = float(self.zone_b_air_temperature_c)
        self.q_to_zone_a_w = float(self.q_to_zone_a_w)
        self.q_to_zone_b_w = float(self.q_to_zone_b_w)
        self.connection_type = str(self.connection_type).strip().lower()
        self.is_openable = bool(self.is_openable)
        self.open_fraction = _clamp_unit_interval(self.open_fraction)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "link_id": self.link_id,
            "connection_id": self.connection_id,
            "zone_a_id": self.zone_a_id,
            "zone_b_id": self.zone_b_id,
            "h_w_k": self.h_w_k,
            "zone_a_air_temperature_c": self.zone_a_air_temperature_c,
            "zone_b_air_temperature_c": self.zone_b_air_temperature_c,
            "q_to_zone_a_w": self.q_to_zone_a_w,
            "q_to_zone_b_w": self.q_to_zone_b_w,
            "connection_type": self.connection_type,
            "is_openable": self.is_openable,
            "open_fraction": self.open_fraction,
            "opening_fraction": self.open_fraction,
        }


@dataclass
class BuildingInterzoneThermalNetwork:
    """
    Pairwise symmetric interzone thermal network.
    """

    links: Dict[str, InterzoneThermalLink] = field(default_factory=dict)

    def __post_init__(self) -> None:
        cleaned = {}

        for link_id, link in self.links.items():
            if not isinstance(link, InterzoneThermalLink):
                raise TypeError(
                    "BuildingInterzoneThermalNetwork.links must contain "
                    "InterzoneThermalLink objects."
                )

            if link_id != link.link_id:
                raise ValueError(
                    "BuildingInterzoneThermalNetwork key "
                    + link_id
                    + " does not match InterzoneThermalLink.link_id "
                    + link.link_id
                )

            cleaned[link_id] = link

        self.links = cleaned

    def link_ids(self) -> List[str]:
        return list(self.links.keys())

    def links_for_zone(self, zone_id: str) -> List[InterzoneThermalLink]:
        return [
            link
            for link in self.links.values()
            if link.zone_a_id == zone_id or link.zone_b_id == zone_id
        ]

    def total_h_for_zone_w_k(self, zone_id: str) -> float:
        return sum(
            link.h_w_k
            for link in self.links_for_zone(zone_id)
        )

    def copy(self, **updates: Any) -> "BuildingInterzoneThermalNetwork":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "links": {
                link_id: link.to_dict()
                for link_id, link in self.links.items()
            }
        }
    
@dataclass
class ZoneVentilationAirflowInputs:
    """
    Airflow inputs for one zone.

    Agent-friendly design:
    - static defaults come from ZoneModel
    - dynamic window/control decisions can be converted into this object later
    - this class does not import agents, actions, or control modules

    Phase 4.6 implements default infiltration and optional mechanical ventilation.
    Window-driven and interzone airflow are placeholders for later.
    """

    zone_id: str

    infiltration_airflow_m3_h: float = 0.0
    mechanical_ventilation_flow_m3_h: float = 0.0
    mechanical_exhaust_flow_m3_h: float | None = None

    window_opening_airflow_m3_h: float = 0.0
    interzone_airflow_m3_h: float = 0.0

    source: str = "ZoneModel"

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneVentilationAirflowInputs.zone_id cannot be empty.")

        self.infiltration_airflow_m3_h = _non_negative_float(
            self.infiltration_airflow_m3_h,
            "infiltration_airflow_m3_h",
            self.zone_id,
        )

        self.mechanical_ventilation_flow_m3_h = _non_negative_float(
            self.mechanical_ventilation_flow_m3_h,
            "mechanical_ventilation_flow_m3_h",
            self.zone_id,
        )
        if self.mechanical_exhaust_flow_m3_h is None:
            self.mechanical_exhaust_flow_m3_h = self.mechanical_ventilation_flow_m3_h
        self.mechanical_exhaust_flow_m3_h = _non_negative_float(
            self.mechanical_exhaust_flow_m3_h,
            "mechanical_exhaust_flow_m3_h",
            self.zone_id,
        )

        self.window_opening_airflow_m3_h = _non_negative_float(
            self.window_opening_airflow_m3_h,
            "window_opening_airflow_m3_h",
            self.zone_id,
        )

        self.interzone_airflow_m3_h = _non_negative_float(
            self.interzone_airflow_m3_h,
            "interzone_airflow_m3_h",
            self.zone_id,
        )

    def outdoor_airflow_m3_h(self) -> float:
        """
        Airflow exchanging heat with outdoor air.

        Interzone airflow is excluded here because it exchanges with adjacent zones,
        not directly with outdoor weather.
        """

        return (
            self.infiltration_airflow_m3_h
            + self.mechanical_exhaust_flow_m3_h
            + self.window_opening_airflow_m3_h
        )

    def outdoor_airflow_m3_s(self) -> float:
        return self.outdoor_airflow_m3_h() / 3600.0

    def outdoor_ventilation_conductance_w_k(self) -> float:
        return ventilation_conductance_from_airflow_m3_h(
            self.outdoor_airflow_m3_h()
        )

    def active_sources(self) -> List[str]:
        sources = []

        if self.infiltration_airflow_m3_h > 0.0:
            sources.append(VENTILATION_SOURCE_INFILTRATION)

        if self.mechanical_ventilation_flow_m3_h > 0.0:
            sources.append(VENTILATION_SOURCE_MECHANICAL)

        if self.window_opening_airflow_m3_h > 0.0:
            sources.append(VENTILATION_SOURCE_WINDOW_OPENING)

        if self.interzone_airflow_m3_h > 0.0:
            sources.append(VENTILATION_SOURCE_INTERZONE_AIRFLOW)

        return sources

    def copy(self, **updates: Any) -> "ZoneVentilationAirflowInputs":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "infiltration_airflow_m3_h": self.infiltration_airflow_m3_h,
            "mechanical_ventilation_flow_m3_h": self.mechanical_ventilation_flow_m3_h,
            "mechanical_exhaust_flow_m3_h": self.mechanical_exhaust_flow_m3_h,
            "window_opening_airflow_m3_h": self.window_opening_airflow_m3_h,
            "interzone_airflow_m3_h": self.interzone_airflow_m3_h,
            "outdoor_airflow_m3_h": self.outdoor_airflow_m3_h(),
            "outdoor_airflow_m3_s": self.outdoor_airflow_m3_s(),
            "outdoor_ventilation_conductance_w_k": self.outdoor_ventilation_conductance_w_k(),
            "active_sources": self.active_sources(),
            "source": self.source,
        }


@dataclass
class ZoneVentilationHeatExchange:
    """
    Ventilation/infiltration thermal exchange for one zone.

    Heat exchange with outdoor or mechanically supplied air:

        q_vent_to_zone = sum(H_source * (T_source - T_zone_air))

    Positive = heat gain by the zone.
    Negative = heat loss from the zone.
    """

    zone_id: str

    airflow_inputs: ZoneVentilationAirflowInputs
    h_ventilation_w_k: float = 0.0
    mechanical_supply_temperature_c: float | None = None

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneVentilationHeatExchange.zone_id cannot be empty.")

        if not isinstance(self.airflow_inputs, ZoneVentilationAirflowInputs):
            raise TypeError(
                "ZoneVentilationHeatExchange.airflow_inputs must be "
                "ZoneVentilationAirflowInputs."
            )

        if self.airflow_inputs.zone_id != self.zone_id:
            raise ValueError(
                "Ventilation airflow_inputs.zone_id does not match zone_id."
            )

        if self.h_ventilation_w_k <= 0.0:
            self.h_ventilation_w_k = (
                self.airflow_inputs.outdoor_ventilation_conductance_w_k()
            )

        self.h_ventilation_w_k = _non_negative_float(
            self.h_ventilation_w_k,
            "h_ventilation_w_k",
            self.zone_id,
        )
        if self.mechanical_supply_temperature_c is not None:
            self.mechanical_supply_temperature_c = float(
                self.mechanical_supply_temperature_c
            )
            if not np.isfinite(self.mechanical_supply_temperature_c):
                raise ValueError(
                    "mechanical_supply_temperature_c must be finite for "
                    + self.zone_id
                )

    def mechanical_conductance_w_k(self) -> float:
        """Mechanical supply conductance."""

        return ventilation_conductance_from_airflow_m3_h(
            self.airflow_inputs.mechanical_ventilation_flow_m3_h
        )

    def mechanical_exhaust_conductance_w_k(self) -> float:
        return ventilation_conductance_from_airflow_m3_h(
            self.airflow_inputs.mechanical_exhaust_flow_m3_h
        )

    def effective_supply_temperature_c(self, outdoor_temperature_c: float) -> float:
        """Return the conductance-weighted ventilation source temperature."""

        outdoor_temperature_c = float(outdoor_temperature_c)
        if self.h_ventilation_w_k <= 0.0:
            return outdoor_temperature_c
        mechanical_h_w_k = self.mechanical_conductance_w_k()
        outdoor_h_w_k = max(
            0.0,
            self.h_ventilation_w_k - self.mechanical_exhaust_conductance_w_k(),
        )
        mechanical_temperature_c = (
            self.mechanical_supply_temperature_c
            if self.mechanical_supply_temperature_c is not None
            else outdoor_temperature_c
        )
        return (
            outdoor_h_w_k * outdoor_temperature_c
            + mechanical_h_w_k * mechanical_temperature_c
        ) / self.h_ventilation_w_k

    def heat_gain_from_outdoor_w(
        self,
        zone_air_temperature_c: float,
        outdoor_temperature_c: float,
    ) -> float:
        return self.h_ventilation_w_k * (
            self.effective_supply_temperature_c(outdoor_temperature_c)
            - float(zone_air_temperature_c)
        )

    def copy(self, **updates: Any) -> "ZoneVentilationHeatExchange":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "airflow_inputs": self.airflow_inputs.to_dict(),
            "h_ventilation_w_k": self.h_ventilation_w_k,
            "mechanical_supply_temperature_c": (
                self.mechanical_supply_temperature_c
            ),
            "mechanical_conductance_w_k": self.mechanical_conductance_w_k(),
            "mechanical_exhaust_conductance_w_k": (
                self.mechanical_exhaust_conductance_w_k()
            ),
        }

@dataclass
class WindowSolarGainRecord:
    """
    Simplified solar gain through one window.

    Phase 4 formula:

        solar_gain_w =
            window_area
            * SHGC
            * effective_solar_factor
            * global_horizontal_radiation

    No solar position.
    No incidence angle.
    No indoor distribution model.
    """

    zone_id: str
    boundary_connection_id: str

    window_area_m2: float
    solar_heat_gain_coefficient: float
    effective_solar_factor: float

    global_horizontal_radiation_w_m2: float
    direct_normal_radiation_w_m2: float = 0.0
    diffuse_horizontal_radiation_w_m2: float = 0.0

    solar_gain_w: Optional[float] = None

    source: str = "BoundaryConnection + WeatherState"

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("WindowSolarGainRecord.zone_id cannot be empty.")

        if not self.boundary_connection_id:
            raise ValueError(
                "WindowSolarGainRecord.boundary_connection_id cannot be empty."
            )

        self.window_area_m2 = _non_negative_float(
            self.window_area_m2,
            "window_area_m2",
            self.zone_id,
        )

        self.solar_heat_gain_coefficient = _clamp_unit_interval(
            self.solar_heat_gain_coefficient
        )

        self.effective_solar_factor = _clamp_unit_interval(
            self.effective_solar_factor
        )

        self.global_horizontal_radiation_w_m2 = _non_negative_float(
            self.global_horizontal_radiation_w_m2,
            "global_horizontal_radiation_w_m2",
            self.zone_id,
        )

        self.direct_normal_radiation_w_m2 = _non_negative_float(
            self.direct_normal_radiation_w_m2,
            "direct_normal_radiation_w_m2",
            self.zone_id,
        )

        self.diffuse_horizontal_radiation_w_m2 = _non_negative_float(
            self.diffuse_horizontal_radiation_w_m2,
            "diffuse_horizontal_radiation_w_m2",
            self.zone_id,
        )

        if self.solar_gain_w is None:
            self.solar_gain_w = (
                self.window_area_m2
                * self.solar_heat_gain_coefficient
                * self.effective_solar_factor
                * self.global_horizontal_radiation_w_m2
            )

        self.solar_gain_w = _non_negative_float(
            self.solar_gain_w,
            "solar_gain_w",
            self.zone_id,
        )

    def to_gain_source(self) -> ZoneThermalGainSource:
        return ZoneThermalGainSource(
            zone_id=self.zone_id,
            source_type=GAIN_SOURCE_SOLAR,
            gain_w=self.solar_gain_w,
            source=self.source,
        )

    def copy(self, **updates: Any) -> "WindowSolarGainRecord":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "boundary_connection_id": self.boundary_connection_id,
            "window_area_m2": self.window_area_m2,
            "solar_heat_gain_coefficient": self.solar_heat_gain_coefficient,
            "effective_solar_factor": self.effective_solar_factor,
            "global_horizontal_radiation_w_m2": self.global_horizontal_radiation_w_m2,
            "direct_normal_radiation_w_m2": self.direct_normal_radiation_w_m2,
            "diffuse_horizontal_radiation_w_m2": self.diffuse_horizontal_radiation_w_m2,
            "solar_gain_w": self.solar_gain_w,
            "source": self.source,
        }


@dataclass
class BuildingSolarGainResult:
    """
    Solar gain records for one timestep.
    """

    records: List[WindowSolarGainRecord] = field(default_factory=list)

    def solar_gains_by_zone_w(self) -> Dict[str, float]:
        out = {}

        for record in self.records:
            out[record.zone_id] = (
                out.get(record.zone_id, 0.0)
                + record.solar_gain_w
            )

        return out

    def to_thermal_gains(
        self,
        all_zone_ids: Optional[List[str]] = None,
    ) -> BuildingThermalGains:
        solar_by_zone = self.solar_gains_by_zone_w()

        if all_zone_ids is None:
            all_zone_ids = list(solar_by_zone.keys())

        return make_building_thermal_gains(
            zone_ids=all_zone_ids,
            solar_gains_by_zone_w=solar_by_zone,
        )

    def total_solar_gain_w(self) -> float:
        return sum(record.solar_gain_w for record in self.records)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_solar_gain_w": self.total_solar_gain_w(),
            "solar_gains_by_zone_w": self.solar_gains_by_zone_w(),
            "records": [
                record.to_dict()
                for record in self.records
            ],
        }
    
    
@dataclass
class BuildingVentilationHeatExchange:
    """
    Ventilation heat-exchange data for all zones.
    """

    zone_ventilation: Dict[str, ZoneVentilationHeatExchange] = field(default_factory=dict)

    def __post_init__(self) -> None:
        cleaned = {}

        for zone_id, item in self.zone_ventilation.items():
            if not isinstance(item, ZoneVentilationHeatExchange):
                raise TypeError(
                    "BuildingVentilationHeatExchange.zone_ventilation must contain "
                    "ZoneVentilationHeatExchange objects."
                )

            if zone_id != item.zone_id:
                raise ValueError(
                    "BuildingVentilationHeatExchange key "
                    + zone_id
                    + " does not match item.zone_id "
                    + item.zone_id
                )

            cleaned[zone_id] = item

        self.zone_ventilation = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_ventilation.keys())

    def get_zone_ventilation(self, zone_id: str) -> ZoneVentilationHeatExchange:
        if zone_id not in self.zone_ventilation:
            raise KeyError(
                "Ventilation heat exchange for zone "
                + zone_id
                + " not found."
            )

        return self.zone_ventilation[zone_id]

    def copy(self, **updates: Any) -> "BuildingVentilationHeatExchange":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_ventilation": {
                zone_id: item.to_dict()
                for zone_id, item in self.zone_ventilation.items()
            }
        }
    
@dataclass
class ZoneSemiImplicitThermalUpdateResult:
    """
    Result of one semi-implicit thermal update for one zone.
    """

    zone_id: str

    old_air_temperature_c: float
    old_mass_temperature_c: float

    new_air_temperature_c: float
    new_mass_temperature_c: float

    air_capacitance_j_k: float = 0.0
    mass_capacitance_j_k: float = 0.0
    convective_gain_w: float = 0.0
    radiative_gain_w: float = 0.0

    air_node_targets: List[ThermalTemperatureTarget] = field(default_factory=list)
    mass_node_targets: List[ThermalTemperatureTarget] = field(default_factory=list)

    dt_seconds: float = 0.0
    solution_method: str = THERMAL_SOLUTION_METHOD

    def to_zone_thermal_state(self) -> ZoneThermalState:
        return ZoneThermalState(
            zone_id=self.zone_id,
            air_temperature_c=self.new_air_temperature_c,
            mass_temperature_c=self.new_mass_temperature_c,
        )

    def building_balance_terms(self) -> Dict[str, float]:
        """Return terms that close when summed over the coupled building."""

        storage_w = (
            self.air_capacitance_j_k
            * (self.new_air_temperature_c - self.old_air_temperature_c)
            + self.mass_capacitance_j_k
            * (self.new_mass_temperature_c - self.old_mass_temperature_c)
        ) / self.dt_seconds
        external_gain_w = sum(
            target.h_w_k
            * (target.temperature_c - self.new_air_temperature_c)
            for target in self.air_node_targets
            if target.target_type
            not in {THERMAL_PATH_AIR_MASS, THERMAL_PATH_INTERZONE}
        )
        return {
            "storage_w": storage_w,
            "external_gain_w": external_gain_w,
            "source_gain_w": self.convective_gain_w + self.radiative_gain_w,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "old_air_temperature_c": self.old_air_temperature_c,
            "old_mass_temperature_c": self.old_mass_temperature_c,
            "new_air_temperature_c": self.new_air_temperature_c,
            "new_mass_temperature_c": self.new_mass_temperature_c,
            "air_capacitance_j_k": self.air_capacitance_j_k,
            "mass_capacitance_j_k": self.mass_capacitance_j_k,
            "convective_gain_w": self.convective_gain_w,
            "radiative_gain_w": self.radiative_gain_w,
            "air_node_targets": [
                target.to_dict()
                for target in self.air_node_targets
            ],
            "mass_node_targets": [
                target.to_dict()
                for target in self.mass_node_targets
            ],
            "dt_seconds": self.dt_seconds,
            "solution_method": self.solution_method,
        }


@dataclass
class BuildingSemiImplicitThermalStepResult:
    """
    Result of one thermal timestep for the whole building.
    """

    updated_state: BuildingThermalState
    zone_results: Dict[str, ZoneSemiImplicitThermalUpdateResult] = field(default_factory=dict)

    dt_minutes: float = DEFAULT_THERMAL_DT_MINUTES
    solution_method: str = THERMAL_SOLUTION_METHOD

    def balance_residual_w(self) -> float:
        """Whole-building storage minus external and source heat gains."""

        return sum(
            terms["storage_w"]
            - terms["external_gain_w"]
            - terms["source_gain_w"]
            for terms in (
                result.building_balance_terms()
                for result in self.zone_results.values()
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "updated_state": self.updated_state.to_dict(),
            "zone_results": {
                zone_id: result.to_dict()
                for zone_id, result in self.zone_results.items()
            },
            "dt_minutes": self.dt_minutes,
            "solution_method": self.solution_method,
            "balance_residual_w": self.balance_residual_w(),
        }

@dataclass
class ZoneThermalDebugRecord:
    """
    Debug record for one zone after one thermal timestep.
    """

    zone_id: str

    old_air_temperature_c: float
    old_mass_temperature_c: float

    new_air_temperature_c: float
    new_mass_temperature_c: float

    convective_gain_w: float
    radiative_gain_w: float

    hvac_gain_w: float = 0.0
    heating_energy_wh: float = 0.0
    cooling_energy_wh: float = 0.0
    solar_gain_w: float = 0.0
    internal_gain_w: float = 0.0

    solution_method: str = THERMAL_SOLUTION_METHOD

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "old_air_temperature_c": self.old_air_temperature_c,
            "old_mass_temperature_c": self.old_mass_temperature_c,
            "new_air_temperature_c": self.new_air_temperature_c,
            "new_mass_temperature_c": self.new_mass_temperature_c,
            "convective_gain_w": self.convective_gain_w,
            "radiative_gain_w": self.radiative_gain_w,
            "hvac_gain_w": self.hvac_gain_w,
            "heating_energy_wh": self.heating_energy_wh,
            "cooling_energy_wh": self.cooling_energy_wh,
            "solar_gain_w": self.solar_gain_w,
            "internal_gain_w": self.internal_gain_w,
            "solution_method": self.solution_method,
        }


@dataclass
class ThermalStepResult:
    """
    Public result returned by ThermalModel.step(...).
    """

    updated_thermal_state: BuildingThermalState

    thermal_kernel_result: BuildingSemiImplicitThermalStepResult
    building_gains: BuildingThermalGains

    hvac_result: BuildingIdealHVACResult
    solar_gain_result: BuildingSolarGainResult
    ventilation_exchange: BuildingVentilationHeatExchange

    debug_records: List[ZoneThermalDebugRecord] = field(default_factory=list)

    dt_minutes: float = DEFAULT_THERMAL_DT_MINUTES
    solution_method: str = THERMAL_SOLUTION_METHOD

    def heating_energy_by_zone_wh(self) -> Dict[str, float]:
        return self.hvac_result.heating_energy_by_zone_wh()

    def cooling_energy_by_zone_wh(self) -> Dict[str, float]:
        return self.hvac_result.cooling_energy_by_zone_wh()

    def total_heating_energy_wh(self) -> float:
        return self.hvac_result.total_heating_energy_wh()

    def total_cooling_energy_wh(self) -> float:
        return self.hvac_result.total_cooling_energy_wh()

    def debug_records_as_dicts(self) -> List[Dict[str, Any]]:
        return [
            record.to_dict()
            for record in self.debug_records
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "updated_thermal_state": self.updated_thermal_state.to_dict(),
            "heating_energy_by_zone_wh": self.heating_energy_by_zone_wh(),
            "cooling_energy_by_zone_wh": self.cooling_energy_by_zone_wh(),
            "total_heating_energy_wh": self.total_heating_energy_wh(),
            "total_cooling_energy_wh": self.total_cooling_energy_wh(),
            "building_gains": self.building_gains.to_dict(),
            "hvac_result": self.hvac_result.to_dict(),
            "solar_gain_result": self.solar_gain_result.to_dict(),
            "ventilation_exchange": self.ventilation_exchange.to_dict(),
            "thermal_kernel_result": self.thermal_kernel_result.to_dict(),
            "debug_records": self.debug_records_as_dicts(),
            "dt_minutes": self.dt_minutes,
            "solution_method": self.solution_method,
        }
    
@dataclass
class ThermalModel:
    """
    Public thermal model interface for ABBEY.

    Runner-facing interface.

    Agent-friendly design:
    - no imports from agents/actions/controllers
    - agent/control outputs must be converted into clean dictionaries or
      thermal input containers before calling this model
    """

    architecture: ThermalArchitectureDecision = field(
        default_factory=ThermalArchitectureDecision
    )
    default_dt_minutes: float = DEFAULT_THERMAL_DT_MINUTES

    def __post_init__(self) -> None:
        if not isinstance(self.architecture, ThermalArchitectureDecision):
            raise TypeError(
                "ThermalModel.architecture must be ThermalArchitectureDecision."
            )

        self.default_dt_minutes = float(self.default_dt_minutes)

        if self.default_dt_minutes <= 0.0:
            raise ValueError("ThermalModel.default_dt_minutes must be positive.")

    def make_initial_state(
        self,
        building_model: Any,
    ) -> BuildingThermalState:
        return make_initial_building_thermal_state(building_model)

    def step(
        self,
        building_model: Any,
        physics_graph: Any,
        thermal_state: BuildingThermalState,
        weather_state: Any,
        zone_system_specs: Optional[Dict[str, Any]] = None,
        zone_control_states: Optional[Dict[str, Any]] = None,
        internal_gains_by_zone: Optional[Dict[str, float]] = None,
        dt_minutes: Optional[float] = None,
        window_boundary_result: Any = None,
        airflow_network: Any = None,
    ) -> ThermalStepResult:
        """
        Advance the thermal model by one timestep.

        Expected runner call:

            ThermalModel.step(
                building_model,
                physics_graph,
                thermal_state,
                weather_state,
                zone_system_specs,
                zone_control_states,
                internal_gains_by_zone,
                dt_minutes
            )

        internal_gains_by_zone:
            sensible appliance/action/internal gains in W, keyed by zone_id.
        """

        if building_model is None:
            raise ValueError("building_model cannot be None.")

        if physics_graph is None and window_boundary_result is None:
            raise ValueError(
                "physics_graph cannot be None unless window_boundary_result is provided."
            )

        if not isinstance(thermal_state, BuildingThermalState):
            raise TypeError("thermal_state must be BuildingThermalState.")

        if weather_state is None:
            raise ValueError("weather_state cannot be None.")

        if dt_minutes is None:
            dt_minutes = self.default_dt_minutes

        dt_minutes = float(dt_minutes)

        if dt_minutes <= 0.0:
            raise ValueError("dt_minutes must be positive.")

        zone_system_specs = zone_system_specs or {}
        zone_control_states = zone_control_states or {}
        internal_gains_by_zone = internal_gains_by_zone or {}

        building_parameters = make_building_thermal_parameters(
            building_model
        )

        zone_ids = building_parameters.zone_ids()

        interzone_network = make_interzone_thermal_network_from_graph(
            physics_graph
        )

        ventilation_exchange = make_ventilation_heat_exchange_for_thermal(
            building_model=building_model,
            airflow_network=airflow_network,
        )

        solar_gain_result = calculate_solar_gains_for_thermal(
            physics_graph=physics_graph,
            weather_state=weather_state,
            window_boundary_result=window_boundary_result,
        )

        additional_outside_conductance_by_zone_w_k = {}

        if window_boundary_result is not None:
            additional_outside_conductance_by_zone_w_k = (
                window_closed_conductance_by_zone_from_boundary_w_k(
                    window_boundary_result
                )
            )

        hvac_inputs = make_building_hvac_inputs(
            zone_ids=zone_ids,
            zone_system_specs=zone_system_specs,
            zone_control_states=zone_control_states,
        )

        hvac_result = calculate_building_ideal_hvac_result(
            hvac_inputs_by_zone=hvac_inputs,
            thermal_state=thermal_state,
            dt_minutes=dt_minutes,
        )

        building_gains = self._assemble_building_gains(
            zone_ids=zone_ids,
            internal_gains_by_zone=internal_gains_by_zone,
            solar_gain_result=solar_gain_result,
            hvac_result=hvac_result,
        )

        thermal_kernel_result = step_building_thermal_state_semi_implicit(
            thermal_state=thermal_state,
            building_parameters=building_parameters,
            weather_state=weather_state,
            building_gains=building_gains,
            interzone_network=interzone_network,
            ventilation_exchange=ventilation_exchange,
            additional_outside_conductance_by_zone_w_k=additional_outside_conductance_by_zone_w_k,
            dt_minutes=dt_minutes,
        )

        debug_records = self._make_debug_records(
            thermal_kernel_result=thermal_kernel_result,
            building_gains=building_gains,
            hvac_result=hvac_result,
            solar_gain_result=solar_gain_result,
            internal_gains_by_zone=internal_gains_by_zone,
        )

        return ThermalStepResult(
            updated_thermal_state=thermal_kernel_result.updated_state,
            thermal_kernel_result=thermal_kernel_result,
            building_gains=building_gains,
            hvac_result=hvac_result,
            solar_gain_result=solar_gain_result,
            ventilation_exchange=ventilation_exchange,
            debug_records=debug_records,
            dt_minutes=dt_minutes,
            solution_method=THERMAL_SOLUTION_METHOD,
        )

    def _assemble_building_gains(
        self,
        zone_ids: List[str],
        internal_gains_by_zone: Dict[str, float],
        solar_gain_result: BuildingSolarGainResult,
        hvac_result: BuildingIdealHVACResult,
    ) -> BuildingThermalGains:
        """
        Merge internal, solar, and HVAC gains into one BuildingThermalGains object.
        """

        solar_gains_by_zone = solar_gain_result.solar_gains_by_zone_w()
        hvac_gains_by_zone = hvac_result.hvac_gains_by_zone_w()

        return make_building_thermal_gains(
            zone_ids=zone_ids,
            appliance_gains_by_zone_w=internal_gains_by_zone,
            solar_gains_by_zone_w=solar_gains_by_zone,
            hvac_gains_by_zone_w=hvac_gains_by_zone,
        )

    def _make_debug_records(
        self,
        thermal_kernel_result: BuildingSemiImplicitThermalStepResult,
        building_gains: BuildingThermalGains,
        hvac_result: BuildingIdealHVACResult,
        solar_gain_result: BuildingSolarGainResult,
        internal_gains_by_zone: Dict[str, float],
    ) -> List[ZoneThermalDebugRecord]:
        solar_by_zone = solar_gain_result.solar_gains_by_zone_w()
        hvac_by_zone = hvac_result.hvac_gains_by_zone_w()
        heating_by_zone = hvac_result.heating_energy_by_zone_wh()
        cooling_by_zone = hvac_result.cooling_energy_by_zone_wh()

        records = []

        for zone_id, kernel_result in thermal_kernel_result.zone_results.items():
            zone_gains = building_gains.get_zone_gains(zone_id)

            records.append(
                ZoneThermalDebugRecord(
                    zone_id=zone_id,
                    old_air_temperature_c=kernel_result.old_air_temperature_c,
                    old_mass_temperature_c=kernel_result.old_mass_temperature_c,
                    new_air_temperature_c=kernel_result.new_air_temperature_c,
                    new_mass_temperature_c=kernel_result.new_mass_temperature_c,
                    convective_gain_w=zone_gains.convective_gain_w(),
                    radiative_gain_w=zone_gains.radiative_gain_w(),
                    hvac_gain_w=hvac_by_zone.get(zone_id, 0.0),
                    heating_energy_wh=heating_by_zone.get(zone_id, 0.0),
                    cooling_energy_wh=cooling_by_zone.get(zone_id, 0.0),
                    solar_gain_w=solar_by_zone.get(zone_id, 0.0),
                    internal_gain_w=internal_gains_by_zone.get(zone_id, 0.0),
                )
            )

        return records
    
def make_default_thermal_model() -> ThermalModel:
    return ThermalModel()

    
def calculate_simplified_window_solar_gains(
    physics_graph: Any,
    weather_state: Any,
) -> BuildingSolarGainResult:
    """
    Calculate simplified window solar gains from graph + weather.

    Uses:
    - BoundaryConnection area
    - BoundaryConnection SHGC
    - BoundaryConnection shading/curtain/frame factors
    - WeatherState global horizontal radiation

    Agent-friendly:
    curtain/blind decisions should update boundary inputs or pass through
    a bridge before this function is called. No agent imports here.
    """

    if physics_graph is None:
        raise ValueError("physics_graph cannot be None.")

    if weather_state is None:
        raise ValueError("weather_state cannot be None.")

    if not hasattr(physics_graph, "boundary_connections"):
        raise TypeError(
            "physics_graph must provide boundary_connections."
        )

    ghi = _non_negative_float(
        _get_attr_or_default(
            weather_state,
            "global_horizontal_radiation_w_m2",
            0.0,
        ),
        "global_horizontal_radiation_w_m2",
        "weather",
    )

    dni = _non_negative_float(
        _get_attr_or_default(
            weather_state,
            "direct_normal_radiation_w_m2",
            0.0,
        ),
        "direct_normal_radiation_w_m2",
        "weather",
    )

    dhi = _non_negative_float(
        _get_attr_or_default(
            weather_state,
            "diffuse_horizontal_radiation_w_m2",
            0.0,
        ),
        "diffuse_horizontal_radiation_w_m2",
        "weather",
    )

    records = []

    for connection_id, boundary in physics_graph.boundary_connections.items():
        if not _is_window_boundary_connection(boundary):
            continue

        area_m2 = _get_attr_or_default(boundary, "area_m2", 0.0)

        if area_m2 is None:
            area_m2 = 0.0

        area_m2 = float(area_m2)

        if area_m2 <= 0.0:
            continue

        zone_id = _required_attr(boundary, "zone_id")

        shgc = _get_attr_or_default(
            boundary,
            "solar_heat_gain_coefficient",
            DEFAULT_WINDOW_SOLAR_HEAT_GAIN_COEFFICIENT,
        )

        if shgc is None:
            shgc = DEFAULT_WINDOW_SOLAR_HEAT_GAIN_COEFFICIENT

        effective_solar_factor = _effective_solar_factor_from_boundary(
            boundary
        )

        records.append(
            WindowSolarGainRecord(
                zone_id=zone_id,
                boundary_connection_id=connection_id,
                window_area_m2=area_m2,
                solar_heat_gain_coefficient=shgc,
                effective_solar_factor=effective_solar_factor,
                global_horizontal_radiation_w_m2=ghi,
                direct_normal_radiation_w_m2=dni,
                diffuse_horizontal_radiation_w_m2=dhi,
            )
        )

    return BuildingSolarGainResult(records=records)


def calculate_simplified_solar_gains_by_zone_w(
    physics_graph: Any,
    weather_state: Any,
) -> Dict[str, float]:
    """
    Convenience wrapper returning only zone-level solar gains.
    """

    result = calculate_simplified_window_solar_gains(
        physics_graph=physics_graph,
        weather_state=weather_state,
    )

    return result.solar_gains_by_zone_w()


def make_interzone_thermal_network_from_physics_graph(
    physics_graph: Any,
    skip_zero_conductance_links: bool = True,
) -> BuildingInterzoneThermalNetwork:
    """
    Build pairwise interzone thermal links from BuildingPhysicsGraph.

    This is the Phase 11.2 graph -> thermal adapter.

    Uses each ZoneConnection:
        from_zone_id / to_zone_id
        connection_type
        area_m2
        u_value_w_m2k
        open_fraction

    No timestep solving happens here.
    """

    if physics_graph is None:
        raise ValueError("physics_graph cannot be None.")

    if not hasattr(physics_graph, "zone_connections"):
        raise TypeError(
            "physics_graph must provide zone_connections."
        )

    links = {}

    for connection_id, connection in physics_graph.zone_connections.items():
        link = make_interzone_thermal_link_from_zone_connection(
            connection=connection
        )

        if skip_zero_conductance_links and link.h_w_k <= 0.0:
            continue

        links[link.link_id] = link

    return BuildingInterzoneThermalNetwork(
        links=links,
    )


def make_interzone_thermal_network_from_graph(
    physics_graph: Any,
    skip_zero_conductance_links: bool = True,
) -> BuildingInterzoneThermalNetwork:
    """
    Backward-compatible alias.

    Preferred Phase 11 name:
        make_interzone_thermal_network_from_physics_graph(...)
    """

    return make_interzone_thermal_network_from_physics_graph(
        physics_graph=physics_graph,
        skip_zero_conductance_links=skip_zero_conductance_links,
    )


def make_interzone_thermal_link_from_zone_connection(
    connection: Any,
) -> InterzoneThermalLink:
    """
    Convert one graph ZoneConnection into one thermal link.

    Rules:
        internal_wall:
            H = U_wall * area

        floor_ceiling:
            H = U_floor_ceiling * area

        closed door:
            H = U_closed_door * door_area

        open door:
            H = H_closed + open_fraction * U_open_effective * opening_area

        generic_interzone:
            H = U_generic * area
    """

    if connection is None:
        raise ValueError("connection cannot be None.")

    connection_id = _required_attr(connection, "connection_id")

    zone_a_id = _required_attr(connection, "from_zone_id")
    zone_b_id = _required_attr(connection, "to_zone_id")

    connection_type = str(
        _get_attr_or_default(
            connection,
            "connection_type",
            "generic_interzone",
        )
    ).strip().lower()

    area_m2 = _get_attr_or_default(
        connection,
        "area_m2",
        None,
    )

    if area_m2 is not None:
        area_m2 = _non_negative_float(
            area_m2,
            "area_m2",
            connection_id,
        )

    u_value_w_m2k = _get_attr_or_default(
        connection,
        "u_value_w_m2k",
        None,
    )

    if u_value_w_m2k is not None:
        u_value_w_m2k = _non_negative_float(
            u_value_w_m2k,
            "u_value_w_m2k",
            connection_id,
        )

    h_w_k = _interzone_conductance_from_zone_connection(
        connection=connection,
        connection_type=connection_type,
        area_m2=area_m2,
        u_value_w_m2k=u_value_w_m2k,
    )

    effective_area_m2 = area_m2

    if effective_area_m2 is None:
        effective_area_m2 = _default_interzone_area_for_connection_type(
            connection_type=connection_type
        )

    effective_u_value_w_m2k = u_value_w_m2k

    if effective_u_value_w_m2k is None:
        effective_u_value_w_m2k = _default_interzone_u_value_for_connection_type(
            connection_type=connection_type
        )
    is_openable = bool(
        _get_attr_or_default(
            connection,
            "is_openable",
            False,
        )
    )

    open_fraction = _clamp_unit_interval(
        _get_attr_or_default(
            connection,
            "open_fraction",
            0.0,
        )
    )

    max_opening_area_m2 = _get_attr_or_default(
        connection,
        "max_opening_area_m2",
        None,
    )

    if max_opening_area_m2 is not None:
        max_opening_area_m2 = _non_negative_float(
            max_opening_area_m2,
            "max_opening_area_m2",
            connection_id,
        )
    return InterzoneThermalLink(
        link_id=connection_id,
        connection_id=connection_id,
        zone_a_id=zone_a_id,
        zone_b_id=zone_b_id,
        connection_type=connection_type,
        area_m2=effective_area_m2,
        u_value_w_m2k=effective_u_value_w_m2k,
        h_w_k=h_w_k,
        is_openable=is_openable,
        open_fraction=open_fraction,
        max_opening_area_m2=max_opening_area_m2,
        source="BuildingPhysicsGraph.ZoneConnection",
    )


def _interzone_conductance_from_zone_connection(
    connection: Any,
    connection_type: str,
    area_m2: Optional[float],
    u_value_w_m2k: Optional[float],
) -> float:
    """
    Calculate interzone conductance H [W/K] from a graph connection.
    """

    connection_type = str(connection_type).strip().lower()

    if connection_type == "door":
        return _door_interzone_conductance_from_zone_connection(
            connection=connection,
            area_m2=area_m2,
            u_value_w_m2k=u_value_w_m2k,
        )

    if area_m2 is None:
        area_m2 = 0.0

    if u_value_w_m2k is None:
        u_value_w_m2k = _default_interzone_u_value_for_connection_type(
            connection_type=connection_type
        )

    return conductance_from_u_area(
        u_value_w_m2k=u_value_w_m2k,
        area_m2=area_m2,
    )


def _door_interzone_conductance_from_zone_connection(
    connection: Any,
    area_m2: Optional[float],
    u_value_w_m2k: Optional[float],
) -> float:
    """
    Simplified closed/open door thermal coupling.

    Closed part:
        conductive/moderate coupling through the door leaf.

    Open part:
        stronger effective coupling through the opening.
        This is not an airflow solver; airflow coupling remains in airflow.py.
    """

    if area_m2 is None:
        area_m2 = _get_attr_or_default(
            connection,
            "max_opening_area_m2",
            DEFAULT_INTERZONE_DOOR_AREA_M2,
        )

    if area_m2 is None:
        area_m2 = DEFAULT_INTERZONE_DOOR_AREA_M2

    area_m2 = _non_negative_float(
        area_m2,
        "door_area_m2",
        _required_attr(connection, "connection_id"),
    )

    if u_value_w_m2k is None:
        u_value_w_m2k = DEFAULT_INTERZONE_CLOSED_DOOR_U_VALUE_W_M2K

    closed_h_w_k = conductance_from_u_area(
        u_value_w_m2k=u_value_w_m2k,
        area_m2=area_m2,
    )

    is_openable = bool(
        _get_attr_or_default(
            connection,
            "is_openable",
            False,
        )
    )

    if not is_openable:
        return closed_h_w_k

    open_fraction = _clamp_unit_interval(
        _get_attr_or_default(
            connection,
            "open_fraction",
            0.0,
        )
    )

    max_opening_area_m2 = _get_attr_or_default(
        connection,
        "max_opening_area_m2",
        area_m2,
    )

    if max_opening_area_m2 is None:
        max_opening_area_m2 = area_m2

    max_opening_area_m2 = _non_negative_float(
        max_opening_area_m2,
        "max_opening_area_m2",
        _required_attr(connection, "connection_id"),
    )

    open_h_w_k = conductance_from_u_area(
        u_value_w_m2k=DEFAULT_INTERZONE_OPEN_DOOR_EFFECTIVE_U_VALUE_W_M2K,
        area_m2=max_opening_area_m2,
        multiplier=open_fraction,
    )

    return closed_h_w_k + open_h_w_k


def _default_interzone_u_value_for_connection_type(
    connection_type: str,
) -> float:
    connection_type = str(connection_type).strip().lower()

    if connection_type == "internal_wall":
        return DEFAULT_INTERZONE_INTERNAL_WALL_U_VALUE_W_M2K

    if connection_type == "floor_ceiling":
        return DEFAULT_INTERZONE_FLOOR_CEILING_U_VALUE_W_M2K

    if connection_type == "door":
        return DEFAULT_INTERZONE_CLOSED_DOOR_U_VALUE_W_M2K

    if connection_type == "generic_interzone":
        return DEFAULT_INTERZONE_GENERIC_U_VALUE_W_M2K

    return DEFAULT_INTERZONE_U_VALUE_W_M2K


def _default_interzone_area_for_connection_type(
    connection_type: str,
) -> float:
    connection_type = str(connection_type).strip().lower()

    if connection_type == "door":
        return DEFAULT_INTERZONE_DOOR_AREA_M2

    return 0.0

def add_interzone_links_to_conductance_network(
    conductance_network: BuildingThermalConductanceNetwork,
    interzone_network: BuildingInterzoneThermalNetwork,
    deactivate_aggregate_interzone_paths: bool = True,
) -> BuildingThermalConductanceNetwork:
    """
    Add pairwise interzone conductance paths to the building conductance network.

    For every A-B link, add:
    - path A -> B
    - path B -> A

    This prepares the network for a symmetric multizone solver.
    """

    if conductance_network is None:
        raise ValueError("conductance_network cannot be None.")

    if interzone_network is None:
        raise ValueError("interzone_network cannot be None.")

    network = conductance_network.copy()

    if deactivate_aggregate_interzone_paths:
        _deactivate_aggregate_interzone_paths(network)

    for link in interzone_network.links.values():
        _ensure_zone_conductance_container(network, link.zone_a_id)
        _ensure_zone_conductance_container(network, link.zone_b_id)

        network.zone_conductances[link.zone_a_id].add_path(
            ThermalConductancePath(
                path_id=link.link_id + "__" + link.zone_a_id + "_to_" + link.zone_b_id,
                path_type=THERMAL_PATH_INTERZONE,
                from_zone_id=link.zone_a_id,
                from_node=THERMAL_AIR_NODE,
                to_zone_id=link.zone_b_id,
                to_node=THERMAL_AIR_NODE,
                h_w_k=link.h_w_k,
                is_symmetric=True,
                source="InterzoneThermalLink",
            )
        )

        network.zone_conductances[link.zone_b_id].add_path(
            ThermalConductancePath(
                path_id=link.link_id + "__" + link.zone_b_id + "_to_" + link.zone_a_id,
                path_type=THERMAL_PATH_INTERZONE,
                from_zone_id=link.zone_b_id,
                from_node=THERMAL_AIR_NODE,
                to_zone_id=link.zone_a_id,
                to_node=THERMAL_AIR_NODE,
                h_w_k=link.h_w_k,
                is_symmetric=True,
                source="InterzoneThermalLink",
            )
        )

    return network
def make_zone_hvac_input(
    zone_id: str,
    zone_system_spec: Any = None,
    zone_control_state: Any = None,
) -> ZoneHVACInput:
    """
    Translate system/control objects into clean HVAC thermal input.

    No import from systems.py.
    No import from agents.
    """

    has_heating = bool(
        _get_attr_or_default(
            zone_system_spec,
            "has_heating",
            False,
        )
    )

    has_cooling = bool(
        _get_attr_or_default(
            zone_system_spec,
            "has_cooling",
            False,
        )
    )

    max_heating_power_w = _first_existing_attr_or_default(
        zone_system_spec,
        [
            "max_heating_power_w",
            "heating_capacity_w",
            "heating_power_w",
            "design_heating_power_w",
        ],
        0.0,
    )
    
    max_cooling_power_w = _first_existing_attr_or_default(
        zone_system_spec,
        [
            "max_cooling_power_w",
            "cooling_capacity_w",
            "cooling_power_w",
            "design_cooling_power_w",
        ],
        0.0,
    )

    heating_setpoint_c = _first_existing_attr_or_default(
        zone_control_state,
        [
            "heating_setpoint_c",
            "target_heating_setpoint_c",
        ],
        DEFAULT_HEATING_SETPOINT_C,
    )

    cooling_setpoint_c = _first_existing_attr_or_default(
        zone_control_state,
        [
            "cooling_setpoint_c",
            "target_cooling_setpoint_c",
        ],
        DEFAULT_COOLING_SETPOINT_C,
    )

    thermostat_deadband_c = _get_attr_or_default(
        zone_control_state,
        "thermostat_deadband_c",
        DEFAULT_THERMOSTAT_DEADBAND_C,
    )
    heating_mode = str(
        _get_attr_or_default(
            zone_control_state,
            "heating_mode",
            "off",
        )
    ).strip().lower()

    cooling_mode = str(
        _get_attr_or_default(
            zone_control_state,
            "cooling_mode",
            "off",
        )
    ).strip().lower()

    if heating_mode not in {"semi_auto", "auto", "bms"}:
        has_heating = False

    if cooling_mode not in {"semi_auto", "auto", "bms"}:
        has_cooling = False
    return ZoneHVACInput(
        zone_id=zone_id,
        has_heating=has_heating,
        has_cooling=has_cooling,
        heating_setpoint_c=heating_setpoint_c,
        cooling_setpoint_c=cooling_setpoint_c,
        max_heating_power_w=max_heating_power_w,
        max_cooling_power_w=max_cooling_power_w,
        thermostat_deadband_c=thermostat_deadband_c,
    )


def make_building_hvac_inputs(
    zone_ids: List[str],
    zone_system_specs: Optional[Dict[str, Any]] = None,
    zone_control_states: Optional[Dict[str, Any]] = None,
) -> Dict[str, ZoneHVACInput]:
    """
    Create HVAC thermal inputs for all zones.

    Agent/control friendly:
    upstream modules provide clean dictionaries keyed by zone_id.
    """

    zone_system_specs = zone_system_specs or {}
    zone_control_states = zone_control_states or {}

    out = {}

    for zone_id in zone_ids:
        out[zone_id] = make_zone_hvac_input(
            zone_id=zone_id,
            zone_system_spec=zone_system_specs.get(zone_id),
            zone_control_state=zone_control_states.get(zone_id),
        )

    return out

def calculate_zone_ideal_hvac_result(
    hvac_input: ZoneHVACInput,
    zone_thermal_state: ZoneThermalState,
    dt_minutes: float,
) -> ZoneIdealHVACResult:
    """
    Ideal bang-bang heating/cooling.

    If too cold:
        heating = max_heating_power_w

    If too hot:
        cooling = max_cooling_power_w

    Else:
        off
    """

    if not isinstance(hvac_input, ZoneHVACInput):
        raise TypeError("hvac_input must be ZoneHVACInput.")

    if not isinstance(zone_thermal_state, ZoneThermalState):
        raise TypeError("zone_thermal_state must be ZoneThermalState.")

    dt_hours = float(dt_minutes) / 60.0

    if dt_hours <= 0.0:
        raise ValueError("dt_minutes must be positive.")

    zone_temp = zone_thermal_state.air_temperature_c

    mode = HVAC_MODE_OFF
    heating_power_w = 0.0
    cooling_power_w = 0.0

    if (
        hvac_input.has_heating
        and hvac_input.max_heating_power_w > 0.0
        and zone_temp < hvac_input.heating_activation_temperature_c()
    ):
        mode = HVAC_MODE_HEATING
        heating_power_w = hvac_input.max_heating_power_w

    elif (
        hvac_input.has_cooling
        and hvac_input.max_cooling_power_w > 0.0
        and zone_temp > hvac_input.cooling_activation_temperature_c()
    ):
        mode = HVAC_MODE_COOLING
        cooling_power_w = hvac_input.max_cooling_power_w

    if (
        not hvac_input.has_heating
        and not hvac_input.has_cooling
    ):
        mode = HVAC_MODE_UNAVAILABLE

    hvac_gain_w = heating_power_w - cooling_power_w

    return ZoneIdealHVACResult(
        zone_id=hvac_input.zone_id,
        mode=mode,
        heating_power_w=heating_power_w,
        cooling_power_w=cooling_power_w,
        hvac_gain_w=hvac_gain_w,
        heating_energy_wh=heating_power_w * dt_hours,
        cooling_energy_wh=cooling_power_w * dt_hours,
        zone_air_temperature_c=zone_temp,
    )


def calculate_building_ideal_hvac_result(
    hvac_inputs_by_zone: Dict[str, ZoneHVACInput],
    thermal_state: BuildingThermalState,
    dt_minutes: float,
) -> BuildingIdealHVACResult:
    """
    Calculate ideal HVAC input for all zones.
    """

    if hvac_inputs_by_zone is None:
        hvac_inputs_by_zone = {}

    if not isinstance(thermal_state, BuildingThermalState):
        raise TypeError("thermal_state must be BuildingThermalState.")

    zone_results = {}

    for zone_id, hvac_input in hvac_inputs_by_zone.items():
        if not thermal_state.has_zone(zone_id):
            continue

        zone_results[zone_id] = calculate_zone_ideal_hvac_result(
            hvac_input=hvac_input,
            zone_thermal_state=thermal_state.get_zone_state(zone_id),
            dt_minutes=dt_minutes,
        )

    return BuildingIdealHVACResult(
        zone_results=zone_results,
    )


def make_zone_ventilation_airflow_inputs_from_zone_model(
    zone_model: Any,
    include_mechanical_ventilation: bool = True,
) -> ZoneVentilationAirflowInputs:
    """
    Build ventilation airflow inputs from ZoneModel.

    Phase 4.6:
    - default infiltration from ACH
    - optional mechanical ventilation flow if available

    Later:
    - window opening airflow from agent/control state
    - interzone airflow from airflow module
    """

    if zone_model is None:
        raise ValueError("zone_model cannot be None.")

    zone_id = _required_attr(zone_model, "zone_id")

    air_volume_m3 = _positive_attr(
        zone_model,
        "air_volume_m3",
        zone_id,
        default=_get_attr_or_default(zone_model, "volume_m3", None),
    )

    infiltration_ach = _non_negative_attr(
        zone_model,
        "default_infiltration_ach",
        zone_id,
        default=0.0,
    )

    infiltration_airflow_m3_h = air_volume_m3 * infiltration_ach

    mechanical_flow_m3_h = 0.0

    if include_mechanical_ventilation:
        mechanical_available = bool(
            _get_attr_or_default(
                zone_model,
                "mechanical_ventilation_available",
                False,
            )
        )

        if mechanical_available:
            mechanical_flow_m3_h = _non_negative_attr(
                zone_model,
                "mechanical_ventilation_flow_m3_h",
                zone_id,
                default=0.0,
            )

    return ZoneVentilationAirflowInputs(
        zone_id=zone_id,
        infiltration_airflow_m3_h=infiltration_airflow_m3_h,
        mechanical_ventilation_flow_m3_h=mechanical_flow_m3_h,
        window_opening_airflow_m3_h=0.0,
        interzone_airflow_m3_h=0.0,
        source="ZoneModel",
    )


def make_zone_ventilation_heat_exchange(
    zone_model: Any,
    airflow_inputs: Optional[ZoneVentilationAirflowInputs] = None,
    mechanical_supply_temperature_c: float | None = None,
) -> ZoneVentilationHeatExchange:
    """
    Create ventilation heat-exchange object for one zone.

    If airflow_inputs is provided, it can come from a later agent/control bridge.
    """

    if zone_model is None:
        raise ValueError("zone_model cannot be None.")

    zone_id = _required_attr(zone_model, "zone_id")

    if airflow_inputs is None:
        airflow_inputs = make_zone_ventilation_airflow_inputs_from_zone_model(
            zone_model
        )

    return ZoneVentilationHeatExchange(
        zone_id=zone_id,
        airflow_inputs=airflow_inputs,
        h_ventilation_w_k=airflow_inputs.outdoor_ventilation_conductance_w_k(),
        mechanical_supply_temperature_c=mechanical_supply_temperature_c,
    )


def make_building_ventilation_heat_exchange(
    building_model: Any,
    airflow_inputs_by_zone: Optional[Dict[str, ZoneVentilationAirflowInputs]] = None,
    mechanical_supply_temperature_by_zone_c: Optional[Dict[str, float]] = None,
) -> BuildingVentilationHeatExchange:
    """
    Build ventilation heat-exchange objects for all zones.

    airflow_inputs_by_zone is the agent-friendly coupling point:
    later, window states and control decisions can be converted into
    ZoneVentilationAirflowInputs and passed here.
    """

    if building_model is None:
        raise ValueError("building_model cannot be None.")

    if not hasattr(building_model, "all_zone_models"):
        raise TypeError(
            "building_model must provide all_zone_models()."
        )

    if airflow_inputs_by_zone is None:
        airflow_inputs_by_zone = {}
    if mechanical_supply_temperature_by_zone_c is None:
        mechanical_supply_temperature_by_zone_c = {}

    zone_models = building_model.all_zone_models()

    out = {}

    for zone_id, zone_model in zone_models.items():
        airflow_inputs = airflow_inputs_by_zone.get(zone_id, None)

        out[zone_id] = make_zone_ventilation_heat_exchange(
            zone_model=zone_model,
            airflow_inputs=airflow_inputs,
            mechanical_supply_temperature_c=(
                mechanical_supply_temperature_by_zone_c.get(zone_id)
            ),
        )

    return BuildingVentilationHeatExchange(
        zone_ventilation=out,
    )

def calculate_ventilation_heat_gains_by_zone_w(
    ventilation_exchange: BuildingVentilationHeatExchange,
    thermal_state: BuildingThermalState,
    weather_state: Any,
) -> Dict[str, float]:
    """
    Calculate ventilation heat gains/losses by zone.

    Positive = heat gain by zone.
    Negative = heat loss from zone.

        q_vent = H_vent * (T_effective_supply - T_zone_air)
    """

    if ventilation_exchange is None:
        raise ValueError("ventilation_exchange cannot be None.")

    if thermal_state is None:
        raise ValueError("thermal_state cannot be None.")

    if weather_state is None:
        raise ValueError("weather_state cannot be None.")

    outdoor_temperature_c = float(
        _get_attr_or_default(
            weather_state,
            "outdoor_temperature_c",
            20.0,
        )
    )

    out = {}

    for zone_id, item in ventilation_exchange.zone_ventilation.items():
        zone_state = thermal_state.get_zone_state(zone_id)

        out[zone_id] = item.heat_gain_from_outdoor_w(
            zone_air_temperature_c=zone_state.air_temperature_c,
            outdoor_temperature_c=outdoor_temperature_c,
        )

    return out

def update_ventilation_paths_in_conductance_network(
    conductance_network: BuildingThermalConductanceNetwork,
    ventilation_exchange: BuildingVentilationHeatExchange,
) -> BuildingThermalConductanceNetwork:
    """
    Update ventilation conductance paths with calculated H_vent values.

    This keeps the conductance network synchronized with static/dynamic
    ventilation inputs.
    """

    if conductance_network is None:
        raise ValueError("conductance_network cannot be None.")

    if ventilation_exchange is None:
        raise ValueError("ventilation_exchange cannot be None.")

    network = conductance_network.copy()

    for zone_id, item in ventilation_exchange.zone_ventilation.items():
        _ensure_zone_conductance_container(network, zone_id)

        zone_conductances = network.zone_conductances[zone_id]

        path_id = zone_id + "__ventilation"

        if path_id in zone_conductances.paths:
            zone_conductances.paths[path_id] = zone_conductances.paths[path_id].copy(
                h_w_k=item.h_ventilation_w_k,
                is_active=True,
                source="BuildingVentilationHeatExchange",
            )
        else:
            zone_conductances.add_path(
                ThermalConductancePath(
                    path_id=path_id,
                    path_type=THERMAL_PATH_VENTILATION,
                    from_zone_id=zone_id,
                    from_node=THERMAL_AIR_NODE,
                    boundary="outside_air",
                    h_w_k=item.h_ventilation_w_k,
                    is_symmetric=False,
                    source="BuildingVentilationHeatExchange",
                )
            )

    return network

def _is_window_boundary_connection(boundary: Any) -> bool:
    connection_type = str(
        _get_attr_or_default(
            boundary,
            "connection_type",
            "",
        )
    ).strip().lower()

    if connection_type == "window":
        return True

    return bool(
        _get_attr_or_default(
            boundary,
            "is_window",
            False,
        )
    )
def _first_existing_attr_or_default(
    obj: Any,
    attribute_names: List[str],
    default: Any,
) -> Any:
    if obj is None:
        return default

    for attribute_name in attribute_names:
        if hasattr(obj, attribute_name):
            value = getattr(obj, attribute_name)

            if value is not None:
                return value

    return default

def _effective_solar_factor_from_boundary(boundary: Any) -> float:
    """
    Simple effective solar factor.

    Includes:
    - frame fraction
    - shading factor
    - curtain reduction if curtain is closed

    Does not include SHGC, because SHGC is applied separately.
    """

    frame_fraction = _get_attr_or_default(
        boundary,
        "frame_fraction",
        DEFAULT_WINDOW_FRAME_FRACTION,
    )

    if frame_fraction is None:
        frame_fraction = DEFAULT_WINDOW_FRAME_FRACTION

    frame_fraction = _clamp_unit_interval(frame_fraction)

    shading_factor = _get_attr_or_default(
        boundary,
        "shading_factor",
        DEFAULT_WINDOW_SHADING_FACTOR,
    )

    if shading_factor is None:
        shading_factor = DEFAULT_WINDOW_SHADING_FACTOR

    shading_factor = _clamp_unit_interval(shading_factor)

    curtain_open = bool(
        _get_attr_or_default(
            boundary,
            "curtain_open",
            True,
        )
    )

    curtain_factor = 1.0

    if not curtain_open:
        curtain_factor = _get_attr_or_default(
            boundary,
            "curtain_solar_reduction_factor",
            DEFAULT_CURTAIN_SOLAR_REDUCTION_FACTOR,
        )

        if curtain_factor is None:
            curtain_factor = DEFAULT_CURTAIN_SOLAR_REDUCTION_FACTOR

        curtain_factor = _clamp_unit_interval(curtain_factor)

    glazing_area_factor = 1.0 - frame_fraction

    return _clamp_unit_interval(
        glazing_area_factor
        * shading_factor
        * curtain_factor
    )

def _deactivate_aggregate_interzone_paths(
    network: BuildingThermalConductanceNetwork,
) -> None:
    for conductances in network.zone_conductances.values():
        for path in conductances.paths.values():
            if path.path_type != THERMAL_PATH_INTERZONE:
                continue

            if path.to_zone_id is None:
                path.is_active = False

            if path.boundary == "adjacent_zone_air":
                path.is_active = False


def _ensure_zone_conductance_container(
    network: BuildingThermalConductanceNetwork,
    zone_id: str,
) -> None:
    if zone_id not in network.zone_conductances:
        network.zone_conductances[zone_id] = ZoneThermalConductances(
            zone_id=zone_id
        )
        
def calculate_interzone_heat_flow_records(
    interzone_network: BuildingInterzoneThermalNetwork,
    thermal_state: BuildingThermalState,
) -> List[InterzoneThermalFlowRecord]:
    """
    Calculate pairwise interzone heat-flow records.

    Positive q_to_zone means heat gain by that zone.

        q_to_a = H_ab * (T_b - T_a)
        q_to_b = -q_to_a
    """

    if interzone_network is None:
        raise ValueError("interzone_network cannot be None.")

    if thermal_state is None:
        raise ValueError("thermal_state cannot be None.")

    records = []

    for link in interzone_network.links.values():
        state_a = thermal_state.get_zone_state(link.zone_a_id)
        state_b = thermal_state.get_zone_state(link.zone_b_id)

        q_to_a_w = link.heat_gain_to_zone_a_w(
            zone_a_air_temperature_c=state_a.air_temperature_c,
            zone_b_air_temperature_c=state_b.air_temperature_c,
        )

        q_to_b_w = -q_to_a_w

        records.append(
            InterzoneThermalFlowRecord(
                link_id=link.link_id,
                connection_id=link.connection_id,
                zone_a_id=link.zone_a_id,
                zone_b_id=link.zone_b_id,
                h_w_k=link.h_w_k,
                zone_a_air_temperature_c=state_a.air_temperature_c,
                zone_b_air_temperature_c=state_b.air_temperature_c,
                q_to_zone_a_w=q_to_a_w,
                q_to_zone_b_w=q_to_b_w,
                connection_type=_get_attr_or_default(
                    link,
                    "connection_type",
                    "generic_interzone",
                ),
                is_openable=bool(
                    _get_attr_or_default(
                        link,
                        "is_openable",
                        False,
                    )
                ),
                open_fraction=_get_attr_or_default(
                    link,
                    "open_fraction",
                    0.0,
                ),
            )
        )

    return records


def aggregate_interzone_heat_gains_by_zone_w(
    records: List[InterzoneThermalFlowRecord],
) -> Dict[str, float]:
    """
    Aggregate interzone heat gains by zone.

    Positive = heat gain.
    Negative = heat loss.
    """

    out = {}

    for record in records:
        out[record.zone_a_id] = (
            out.get(record.zone_a_id, 0.0)
            + record.q_to_zone_a_w
        )

        out[record.zone_b_id] = (
            out.get(record.zone_b_id, 0.0)
            + record.q_to_zone_b_w
        )

    return out


def check_interzone_heat_flow_symmetry(
    records: List[InterzoneThermalFlowRecord],
    tolerance_w: float = 1e-9,
) -> bool:
    """
    Check that every interzone link is symmetric:

        q_to_a + q_to_b = 0
    """

    tolerance_w = float(tolerance_w)

    for record in records:
        residual = record.q_to_zone_a_w + record.q_to_zone_b_w

        if abs(residual) > tolerance_w:
            return False

    return True
 
def make_zone_thermal_conductances(
    parameters: ZoneThermalParameters,
) -> ZoneThermalConductances:
    """
    Create basic conductance paths for one zone.

    Includes:
    - air ↔ mass
    - air ↔ outside
    - air ↔ adjacent-zone aggregate placeholder
    - air ↔ ventilation/infiltration outside
    - HVAC input placeholder

    Detailed interzone pair paths are added in Phase 4.5.
    """

    zone_id = parameters.zone_id

    conductances = ZoneThermalConductances(zone_id=zone_id)

    conductances.add_path(
        ThermalConductancePath(
            path_id=zone_id + "__air_mass",
            path_type=THERMAL_PATH_AIR_MASS,
            from_zone_id=zone_id,
            from_node=THERMAL_AIR_NODE,
            to_zone_id=zone_id,
            to_node=THERMAL_MASS_NODE,
            h_w_k=parameters.h_air_mass_w_k,
            is_symmetric=True,
            source="ZoneThermalParameters.h_air_mass_w_k",
        )
    )

    conductances.add_path(
        ThermalConductancePath(
            path_id=zone_id + "__outside",
            path_type=THERMAL_PATH_OUTSIDE,
            from_zone_id=zone_id,
            from_node=THERMAL_AIR_NODE,
            boundary="outside",
            h_w_k=parameters.h_external_w_k,
            is_symmetric=False,
            source="ZoneThermalParameters.h_external_w_k",
        )
    )

    conductances.add_path(
        ThermalConductancePath(
            path_id=zone_id + "__interzone_aggregate",
            path_type=THERMAL_PATH_INTERZONE,
            from_zone_id=zone_id,
            from_node=THERMAL_AIR_NODE,
            boundary="adjacent_zone_air",
            h_w_k=parameters.h_interzone_w_k,
            is_symmetric=True,
            source="ZoneThermalParameters.h_interzone_w_k",
        )
    )

    conductances.add_path(
        ThermalConductancePath(
            path_id=zone_id + "__ventilation",
            path_type=THERMAL_PATH_VENTILATION,
            from_zone_id=zone_id,
            from_node=THERMAL_AIR_NODE,
            boundary="outside_air",
            h_w_k=parameters.h_ventilation_w_k,
            is_symmetric=False,
            source="ZoneThermalParameters.h_ventilation_w_k",
        )
    )

    conductances.add_path(
        ThermalConductancePath(
            path_id=zone_id + "__hvac_input",
            path_type=THERMAL_PATH_HVAC,
            from_zone_id=zone_id,
            from_node=THERMAL_AIR_NODE,
            boundary="system_input",
            h_w_k=0.0,
            is_symmetric=False,
            source="ZoneSystemSpec later",
        )
    )

    return conductances


def make_building_thermal_conductance_network(
    building_parameters: BuildingThermalParameters,
) -> BuildingThermalConductanceNetwork:
    """
    Create thermal conductance network from building thermal parameters.
    """

    zone_conductances = {}

    for zone_id, parameters in building_parameters.zone_parameters.items():
        zone_conductances[zone_id] = make_zone_thermal_conductances(parameters)

    return BuildingThermalConductanceNetwork(
        zone_conductances=zone_conductances,
    )

def conductance_from_u_area(
    u_value_w_m2k: float,
    area_m2: float,
    multiplier: float = 1.0,
) -> float:
    """
    Calculate conductance from U-value and area.

        H = U * A * multiplier
    """

    u_value_w_m2k = float(u_value_w_m2k)
    area_m2 = float(area_m2)
    multiplier = float(multiplier)

    if u_value_w_m2k < 0.0:
        raise ValueError("u_value_w_m2k cannot be negative.")

    if area_m2 < 0.0:
        raise ValueError("area_m2 cannot be negative.")

    if multiplier < 0.0:
        raise ValueError("multiplier cannot be negative.")

    return u_value_w_m2k * area_m2 * multiplier


def resistance_from_conductance(
    h_w_k: float,
) -> Optional[float]:
    """
    Calculate resistance from conductance.

        R = 1 / H

    Returns None when H <= 0.
    """

    h_w_k = float(h_w_k)

    if h_w_k <= 0.0:
        return None

    return 1.0 / h_w_k


def conductance_from_resistance(
    r_k_w: float,
) -> float:
    """
    Calculate conductance from resistance.

        H = 1 / R
    """

    r_k_w = float(r_k_w)

    if r_k_w <= 0.0:
        raise ValueError("r_k_w must be positive.")

    return 1.0 / r_k_w


def ventilation_conductance_from_airflow_m3_s(
    airflow_m3_s: float,
) -> float:
    """
    Convert airflow to heat-transfer conductance.

        H_vent = rho_air * cp_air * airflow_m3_s
    """

    airflow_m3_s = float(airflow_m3_s)

    if airflow_m3_s < 0.0:
        raise ValueError("airflow_m3_s cannot be negative.")

    return (
        THERMAL_AIR_DENSITY_KG_M3
        * THERMAL_AIR_SPECIFIC_HEAT_J_KG_K
        * airflow_m3_s
    )


def ventilation_conductance_from_airflow_m3_h(
    airflow_m3_h: float,
) -> float:
    airflow_m3_h = float(airflow_m3_h)

    if airflow_m3_h < 0.0:
        raise ValueError("airflow_m3_h cannot be negative.")

    return ventilation_conductance_from_airflow_m3_s(
        airflow_m3_h / 3600.0
    )


def ventilation_conductance_from_ach(
    air_volume_m3: float,
    ach: float,
) -> float:
    air_volume_m3 = float(air_volume_m3)
    ach = float(ach)

    if air_volume_m3 <= 0.0:
        raise ValueError("air_volume_m3 must be positive.")

    if ach < 0.0:
        raise ValueError("ach cannot be negative.")

    airflow_m3_h = air_volume_m3 * ach

    return ventilation_conductance_from_airflow_m3_h(airflow_m3_h)


def make_zone_thermal_parameters(
    zone_model: Any,
) -> ZoneThermalParameters:
    """
    Build ZoneThermalParameters from ZoneModel.

    Uses Phase 2 ZoneModel inputs:
    - air_heat_capacity_j_k
    - internal_heat_capacity_j_k
    - external_wall_area_m2
    - internal_wall_area_m2
    - u_value_external_wall_w_m2k
    - u_value_internal_wall_w_m2k
    - thermal_bridge_factor
    - air_volume_m3
    - default_infiltration_ach
    """

    if zone_model is None:
        raise ValueError("zone_model cannot be None.")

    zone_id = _required_attr(zone_model, "zone_id")

    floor_area_m2 = _positive_attr(
        zone_model,
        "floor_area_m2",
        zone_id,
        default=20.0,
    )

    air_volume_m3 = _positive_attr(
        zone_model,
        "air_volume_m3",
        zone_id,
        default=_get_attr_or_default(zone_model, "volume_m3", None),
    )

    if air_volume_m3 is None:
        air_volume_m3 = floor_area_m2 * 2.7

    c_air_j_k = _get_attr_or_default(
        zone_model,
        "air_heat_capacity_j_k",
        None,
    )

    if c_air_j_k is None:
        c_air_j_k = (
            air_volume_m3
            * THERMAL_AIR_DENSITY_KG_M3
            * THERMAL_AIR_SPECIFIC_HEAT_J_KG_K
        )

    c_mass_j_k = _get_attr_or_default(
        zone_model,
        "internal_heat_capacity_j_k",
        None,
    )

    if c_mass_j_k is None:
        c_mass_j_k = _get_attr_or_default(
            zone_model,
            "thermal_capacity_j_per_k",
            None,
        )

    if c_mass_j_k is None:
        c_mass_j_k = 165000.0 * floor_area_m2

    external_wall_area_m2 = _non_negative_attr(
        zone_model,
        "external_wall_area_m2",
        zone_id,
        default=0.0,
    )

    internal_wall_area_m2 = _non_negative_attr(
        zone_model,
        "internal_wall_area_m2",
        zone_id,
        default=0.0,
    )

    u_external = _non_negative_attr(
        zone_model,
        "u_value_external_wall_w_m2k",
        zone_id,
        default=1.2,
    )

    u_internal = _non_negative_attr(
        zone_model,
        "u_value_internal_wall_w_m2k",
        zone_id,
        default=1.8,
    )

    thermal_bridge_factor = _non_negative_attr(
        zone_model,
        "thermal_bridge_factor",
        zone_id,
        default=DEFAULT_THERMAL_BRIDGE_FACTOR,
    )

    infiltration_ach = _non_negative_attr(
        zone_model,
        "default_infiltration_ach",
        zone_id,
        default=0.3,
    )

    effective_mass_area_m2 = _get_attr_or_default(
        zone_model,
        "effective_thermal_mass_area_m2",
        None,
    )
    if effective_mass_area_m2 is None:
        # Compatibility path for legacy ZoneModel callers that have no
        # surface-derived mass-coupling area.
        effective_mass_area_m2 = _estimate_effective_mass_area_m2(
            floor_area_m2=floor_area_m2,
            internal_wall_area_m2=internal_wall_area_m2,
        )
    else:
        effective_mass_area_m2 = _positive_float(
            effective_mass_area_m2,
            "effective_thermal_mass_area_m2",
            zone_id,
        )

    h_air_mass_w_k = (
        DEFAULT_AIR_MASS_COUPLING_W_M2K
        * effective_mass_area_m2
    )

    h_external_w_k = conductance_from_u_area(
        u_value_w_m2k=u_external,
        area_m2=external_wall_area_m2,
        multiplier=thermal_bridge_factor,
    )

    h_interzone_w_k = conductance_from_u_area(
        u_value_w_m2k=u_internal,
        area_m2=internal_wall_area_m2,
    )

    h_ventilation_w_k = _ventilation_conductance_from_ach(
        air_volume_m3=air_volume_m3,
        ach=infiltration_ach,
    )

    return ZoneThermalParameters(
        zone_id=zone_id,
        c_air_j_k=c_air_j_k,
        c_mass_j_k=c_mass_j_k,
        h_air_mass_w_k=h_air_mass_w_k,
        h_external_w_k=h_external_w_k,
        h_interzone_w_k=h_interzone_w_k,
        h_ventilation_w_k=h_ventilation_w_k,
        air_volume_m3=air_volume_m3,
        infiltration_ach=infiltration_ach,
        floor_area_m2=floor_area_m2,
        effective_mass_area_m2=effective_mass_area_m2,
        external_wall_area_m2=external_wall_area_m2,
        internal_wall_area_m2=internal_wall_area_m2,
        thermal_bridge_factor=thermal_bridge_factor,
    )

def default_gain_split_for_source_type(
    source_type: str,
) -> ThermalGainSplit:
    source_type = str(source_type).strip().lower()

    if source_type == GAIN_SOURCE_PEOPLE:
        return DEFAULT_PEOPLE_GAIN_SPLIT

    if source_type == GAIN_SOURCE_APPLIANCES:
        return DEFAULT_APPLIANCE_GAIN_SPLIT

    if source_type == GAIN_SOURCE_LIGHTING:
        return DEFAULT_LIGHTING_GAIN_SPLIT

    if source_type == GAIN_SOURCE_SOLAR:
        return DEFAULT_SOLAR_GAIN_SPLIT

    if source_type == GAIN_SOURCE_HVAC:
        return DEFAULT_HVAC_GAIN_SPLIT

    return DEFAULT_APPLIANCE_GAIN_SPLIT


def make_zone_thermal_gains(
    zone_id: str,
    people_gain_w: float = 0.0,
    appliance_gain_w: float = 0.0,
    lighting_gain_w: float = 0.0,
    solar_gain_w: float = 0.0,
    hvac_gain_w: float = 0.0,
) -> ZoneThermalGains:
    """
    Create thermal gains for one zone.

    Positive HVAC = heating.
    Negative HVAC = cooling.
    """

    gains = ZoneThermalGains(zone_id=zone_id)

    if people_gain_w != 0.0:
        gains.add_source(
            ZoneThermalGainSource(
                zone_id=zone_id,
                source_type=GAIN_SOURCE_PEOPLE,
                gain_w=people_gain_w,
                source="people_input",
            )
        )

    if appliance_gain_w != 0.0:
        gains.add_source(
            ZoneThermalGainSource(
                zone_id=zone_id,
                source_type=GAIN_SOURCE_APPLIANCES,
                gain_w=appliance_gain_w,
                source="appliance_internal_sources",
            )
        )

    if lighting_gain_w != 0.0:
        gains.add_source(
            ZoneThermalGainSource(
                zone_id=zone_id,
                source_type=GAIN_SOURCE_LIGHTING,
                gain_w=lighting_gain_w,
                source="lighting_input",
            )
        )

    if solar_gain_w != 0.0:
        gains.add_source(
            ZoneThermalGainSource(
                zone_id=zone_id,
                source_type=GAIN_SOURCE_SOLAR,
                gain_w=solar_gain_w,
                source="solar_input",
            )
        )

    if hvac_gain_w != 0.0:
        gains.add_source(
            ZoneThermalGainSource(
                zone_id=zone_id,
                source_type=GAIN_SOURCE_HVAC,
                gain_w=hvac_gain_w,
                source="hvac_input",
            )
        )

    return gains


def make_building_thermal_gains(
    zone_ids: List[str],
    people_gains_by_zone_w: Optional[Dict[str, float]] = None,
    appliance_gains_by_zone_w: Optional[Dict[str, float]] = None,
    lighting_gains_by_zone_w: Optional[Dict[str, float]] = None,
    solar_gains_by_zone_w: Optional[Dict[str, float]] = None,
    hvac_gains_by_zone_w: Optional[Dict[str, float]] = None,
) -> BuildingThermalGains:
    """
    Create BuildingThermalGains from clean physical input dictionaries.

    Agent-friendly:
    upstream agent/action/control modules should be converted into these
    dictionaries before entering thermal.py.
    """

    people_gains_by_zone_w = people_gains_by_zone_w or {}
    appliance_gains_by_zone_w = appliance_gains_by_zone_w or {}
    lighting_gains_by_zone_w = lighting_gains_by_zone_w or {}
    solar_gains_by_zone_w = solar_gains_by_zone_w or {}
    hvac_gains_by_zone_w = hvac_gains_by_zone_w or {}

    zone_gains = {}

    for zone_id in zone_ids:
        zone_gains[zone_id] = make_zone_thermal_gains(
            zone_id=zone_id,
            people_gain_w=people_gains_by_zone_w.get(zone_id, 0.0),
            appliance_gain_w=appliance_gains_by_zone_w.get(zone_id, 0.0),
            lighting_gain_w=lighting_gains_by_zone_w.get(zone_id, 0.0),
            solar_gain_w=solar_gains_by_zone_w.get(zone_id, 0.0),
            hvac_gain_w=hvac_gains_by_zone_w.get(zone_id, 0.0),
        )

    return BuildingThermalGains(zone_gains=zone_gains)

def semi_implicit_temperature_update(
    capacity_j_k: float,
    old_temperature_c: float,
    targets: List[ThermalTemperatureTarget],
    gain_w: float,
    dt_seconds: float,
) -> float:
    """
    Stable backward-Euler-style temperature update.

        T_next =
            (C/dt * T_old + sum(H_i * T_i) + gains)
            /
            (C/dt + sum(H_i))

    gain_w:
        positive = heat added to node
        negative = heat removed from node
    """

    capacity_j_k = float(capacity_j_k)
    old_temperature_c = float(old_temperature_c)
    gain_w = float(gain_w)
    dt_seconds = float(dt_seconds)

    if capacity_j_k <= 0.0:
        raise ValueError("capacity_j_k must be positive.")

    if dt_seconds <= 0.0:
        raise ValueError("dt_seconds must be positive.")

    if targets is None:
        targets = []

    c_over_dt = capacity_j_k / dt_seconds

    numerator = c_over_dt * old_temperature_c + gain_w
    denominator = c_over_dt

    for target in targets:
        if not isinstance(target, ThermalTemperatureTarget):
            raise TypeError(
                "targets must contain ThermalTemperatureTarget objects."
            )

        numerator += target.h_w_k * target.temperature_c
        denominator += target.h_w_k

    if denominator <= 0.0:
        raise ValueError("Semi-implicit update denominator became non-positive.")

    return numerator / denominator

def update_zone_thermal_state_semi_implicit(
    zone_state: ZoneThermalState,
    zone_parameters: ZoneThermalParameters,
    outdoor_temperature_c: float,
    adjacent_air_targets: Optional[List[ThermalTemperatureTarget]] = None,
    ventilation_h_w_k: Optional[float] = None,
    additional_outside_h_w_k: float = 0.0,
    convective_gain_w: float = 0.0,
    radiative_gain_w: float = 0.0,
    dt_minutes: float = DEFAULT_THERMAL_DT_MINUTES,
) -> ZoneSemiImplicitThermalUpdateResult:
    """
    Update one zone with a two-node semi-implicit RC model.

    Air node receives:
    - exchange with mass node
    - exchange with outside envelope
    - exchange with ventilation/infiltration outside
    - exchange with adjacent zone air targets
    - convective gains

    Mass node receives:
    - exchange with air node
    - radiative gains

    The air and mass nodes are solved together. This retains the stable
    backward-Euler discretization while ensuring that internal air/mass heat
    exchange is equal and opposite within the timestep.
    """

    if not isinstance(zone_state, ZoneThermalState):
        raise TypeError("zone_state must be ZoneThermalState.")

    if not isinstance(zone_parameters, ZoneThermalParameters):
        raise TypeError("zone_parameters must be ZoneThermalParameters.")

    if zone_state.zone_id != zone_parameters.zone_id:
        raise ValueError(
            "zone_state.zone_id does not match zone_parameters.zone_id."
        )

    dt_seconds = float(dt_minutes) * 60.0

    if dt_seconds <= 0.0:
        raise ValueError("dt_minutes must be positive.")

    if adjacent_air_targets is None:
        adjacent_air_targets = []

    if ventilation_h_w_k is None:
        ventilation_h_w_k = zone_parameters.h_ventilation_w_k

    ventilation_h_w_k = _non_negative_float(
        ventilation_h_w_k,
        "ventilation_h_w_k",
        zone_state.zone_id,
    )

    additional_outside_h_w_k = _non_negative_float(
        additional_outside_h_w_k,
        "additional_outside_h_w_k",
        zone_state.zone_id,
    )

    total_outside_h_w_k = (
        zone_parameters.h_external_w_k
        + additional_outside_h_w_k
    )
    
    air_targets = []

    air_targets.append(
        ThermalTemperatureTarget(
            target_id=zone_state.zone_id + "__mass_old",
            target_type=THERMAL_PATH_AIR_MASS,
            temperature_c=zone_state.mass_temperature_c,
            h_w_k=zone_parameters.h_air_mass_w_k,
        )
    )

    air_targets.append(
        ThermalTemperatureTarget(
            target_id="outside_envelope_plus_windows",
            target_type=THERMAL_PATH_OUTSIDE,
            temperature_c=outdoor_temperature_c,
            h_w_k=total_outside_h_w_k,
        )
    )

    air_targets.append(
        ThermalTemperatureTarget(
            target_id="outside_ventilation",
            target_type=THERMAL_PATH_VENTILATION,
            temperature_c=outdoor_temperature_c,
            h_w_k=ventilation_h_w_k,
        )
    )

    for target in adjacent_air_targets:
        air_targets.append(target)

    c_air_over_dt = zone_parameters.c_air_j_k / dt_seconds
    c_mass_over_dt = zone_parameters.c_mass_j_k / dt_seconds
    h_air_mass_w_k = zone_parameters.h_air_mass_w_k

    fixed_air_targets = air_targets[1:]
    fixed_air_h_w_k = sum(target.h_w_k for target in fixed_air_targets)
    air_rhs_w = (
        c_air_over_dt * zone_state.air_temperature_c
        + sum(
            target.h_w_k * target.temperature_c
            for target in fixed_air_targets
        )
        + float(convective_gain_w)
    )
    mass_rhs_w = (
        c_mass_over_dt * zone_state.mass_temperature_c
        + float(radiative_gain_w)
    )

    air_diagonal_w_k = c_air_over_dt + h_air_mass_w_k + fixed_air_h_w_k
    mass_diagonal_w_k = c_mass_over_dt + h_air_mass_w_k
    determinant = (
        air_diagonal_w_k * mass_diagonal_w_k
        - h_air_mass_w_k * h_air_mass_w_k
    )
    if determinant <= 0.0:
        raise ValueError("Coupled thermal update matrix became non-positive.")

    new_air_temperature_c = (
        air_rhs_w * mass_diagonal_w_k
        + h_air_mass_w_k * mass_rhs_w
    ) / determinant
    new_mass_temperature_c = (
        air_diagonal_w_k * mass_rhs_w
        + h_air_mass_w_k * air_rhs_w
    ) / determinant

    mass_targets = [
        ThermalTemperatureTarget(
            target_id=zone_state.zone_id + "__air_new",
            target_type=THERMAL_PATH_AIR_MASS,
            temperature_c=new_air_temperature_c,
            h_w_k=zone_parameters.h_air_mass_w_k,
        )
    ]

    return ZoneSemiImplicitThermalUpdateResult(
        zone_id=zone_state.zone_id,
        old_air_temperature_c=zone_state.air_temperature_c,
        old_mass_temperature_c=zone_state.mass_temperature_c,
        new_air_temperature_c=new_air_temperature_c,
        new_mass_temperature_c=new_mass_temperature_c,
        air_capacitance_j_k=zone_parameters.c_air_j_k,
        mass_capacitance_j_k=zone_parameters.c_mass_j_k,
        convective_gain_w=convective_gain_w,
        radiative_gain_w=radiative_gain_w,
        air_node_targets=air_targets,
        mass_node_targets=mass_targets,
        dt_seconds=dt_seconds,
    )

def _measured_vertical_irradiance_w_m2(
    weather_state: Any,
    *,
    surface_tilt_deg: float,
    surface_azimuth_deg: float,
) -> float | None:
    """Return an exact measured cardinal-plane value when available."""

    if abs(float(surface_tilt_deg) - 90.0) > 1.0e-9:
        return None
    azimuth = float(surface_azimuth_deg) % 360.0
    fields = {
        0.0: "north_vertical_radiation_w_m2",
        90.0: "east_vertical_radiation_w_m2",
        180.0: "south_vertical_radiation_w_m2",
        270.0: "west_vertical_radiation_w_m2",
    }
    for cardinal, field_name in fields.items():
        difference = abs((azimuth - cardinal + 180.0) % 360.0 - 180.0)
        if difference <= 1.0e-9:
            value = _get_attr_or_default(weather_state, field_name, None)
            if value is None:
                return None
            return _non_negative_float(value, field_name, "weather")
    return None


def calculate_window_boundary_solar_gains(
    window_boundary_result: Any,
    weather_state: Any,
) -> BuildingSolarGainResult:
    """
    Calculate solar gains from the shared window boundary result.

    Canonical runs provide SPA solar position and use DNI/DHI/GHI resolved on
    each window plane.  Legacy callers without solar position remain on the
    explicitly labelled GHI/exposure compatibility path.
    """

    if not is_building_window_boundary_result_like(window_boundary_result):
        raise TypeError(
            "window_boundary_result must behave like BuildingWindowBoundaryResult."
        )

    if weather_state is None:
        raise ValueError("weather_state cannot be None.")

    ghi = _non_negative_float(
        _get_attr_or_default(
            weather_state,
            "global_horizontal_radiation_w_m2",
            0.0,
        ),
        "global_horizontal_radiation_w_m2",
        "weather",
    )

    dni = _non_negative_float(
        _get_attr_or_default(
            weather_state,
            "direct_normal_radiation_w_m2",
            0.0,
        ),
        "direct_normal_radiation_w_m2",
        "weather",
    )

    dhi = _non_negative_float(
        _get_attr_or_default(
            weather_state,
            "diffuse_horizontal_radiation_w_m2",
            0.0,
        ),
        "diffuse_horizontal_radiation_w_m2",
        "weather",
    )

    records = []

    solar_zenith_deg = _get_attr_or_default(
        weather_state, "solar_zenith_deg", None
    )
    solar_azimuth_deg = _get_attr_or_default(
        weather_state, "solar_azimuth_deg", None
    )
    ground_albedo_fraction = _get_attr_or_default(
        weather_state, "ground_albedo_fraction", 0.0
    )
    has_solar_position = (
        solar_zenith_deg is not None and solar_azimuth_deg is not None
    )

    for window_id, window_result in window_boundary_result.window_results_by_id.items():
        if window_result.area_m2 <= 0.0:
            continue

        measured_vertical_w_m2 = _measured_vertical_irradiance_w_m2(
            weather_state,
            surface_tilt_deg=window_result.tilt_deg,
            surface_azimuth_deg=window_result.orientation_deg,
        )
        if measured_vertical_w_m2 is not None:
            solar_gain_w = (
                measured_vertical_w_m2
                * window_result.area_m2
                * window_result.effective_solar_transmittance
            )
            effective_solar_factor = 1.0
            source = THERMAL_SOLAR_GAIN_SOURCE_MEASURED_VERTICAL_PLANE
        elif has_solar_position:
            irradiance = calculate_surface_solar_irradiance(
                solar_zenith_deg=float(solar_zenith_deg),
                solar_azimuth_deg=float(solar_azimuth_deg),
                surface_tilt_deg=window_result.tilt_deg,
                surface_azimuth_deg=window_result.orientation_deg,
                direct_normal_radiation_w_m2=dni,
                diffuse_horizontal_radiation_w_m2=dhi,
                global_horizontal_radiation_w_m2=ghi,
                ground_albedo_fraction=float(ground_albedo_fraction),
            )
            solar_gain_w = irradiance.transmitted_gain_w(
                area_m2=window_result.area_m2,
                solar_transmittance_fraction=(
                    window_result.effective_solar_transmittance
                ),
            )
            effective_solar_factor = 1.0
            source = THERMAL_SOLAR_GAIN_SOURCE_PLANE_OF_ARRAY
        else:
            solar_gain_w = None
            effective_solar_factor = window_result.effective_solar_factor
            source = THERMAL_SOLAR_GAIN_SOURCE_WINDOW_BOUNDARY

        records.append(
            WindowSolarGainRecord(
                zone_id=window_result.zone_id,
                boundary_connection_id=window_id,
                window_area_m2=window_result.area_m2,
                solar_heat_gain_coefficient=1.0,
                effective_solar_factor=effective_solar_factor,
                global_horizontal_radiation_w_m2=ghi,
                direct_normal_radiation_w_m2=dni,
                diffuse_horizontal_radiation_w_m2=dhi,
                solar_gain_w=solar_gain_w,
                source=source,
            )
        )

    return BuildingSolarGainResult(
        records=records,
    )


def calculate_solar_gains_for_thermal(
    physics_graph: Any,
    weather_state: Any,
    window_boundary_result: Any = None,
) -> BuildingSolarGainResult:
    """
    Compatibility wrapper.

    Preferred Phase 8:
        BuildingWindowBoundaryResult

    Legacy fallback:
        physics_graph BoundaryConnection extraction
    """

    if window_boundary_result is not None:
        return calculate_window_boundary_solar_gains(
            window_boundary_result=window_boundary_result,
            weather_state=weather_state,
        )

    return calculate_simplified_window_solar_gains(
        physics_graph=physics_graph,
        weather_state=weather_state,
    )


def calculate_opaque_boundary_radiative_gains_by_zone_w(
    physics_graph: Any,
    weather_state: Any,
) -> Dict[str, float]:
    """Calculate source-independent opaque solar and sky-longwave gains.

    The correction is the standard sol-air boundary term passed through the
    construction conductance::

        q_zone = U A / h_se * (alpha I + epsilon F_sky (L_sky - L_air))

    It is opt-in: a surface must declare absorptance, emissivity, and exterior
    heat-transfer coefficient.  This avoids hidden defaults changing existing
    scenarios.  Cellar and other named non-outdoor boundaries are excluded.
    """

    if physics_graph is None or not hasattr(physics_graph, "boundary_connections"):
        raise TypeError("physics_graph must provide boundary_connections")
    if weather_state is None:
        raise ValueError("weather_state cannot be None")

    outdoor_c = float(_get_attr_or_default(weather_state, "outdoor_temperature_c", 20.0))
    sky_c = _get_attr_or_default(weather_state, "sky_temperature_c", None)
    solar_zenith = _get_attr_or_default(weather_state, "solar_zenith_deg", None)
    solar_azimuth = _get_attr_or_default(weather_state, "solar_azimuth_deg", None)
    dni = float(_get_attr_or_default(weather_state, "direct_normal_radiation_w_m2", 0.0))
    dhi = float(_get_attr_or_default(weather_state, "diffuse_horizontal_radiation_w_m2", 0.0))
    ghi = float(_get_attr_or_default(weather_state, "global_horizontal_radiation_w_m2", 0.0))
    albedo = float(_get_attr_or_default(weather_state, "ground_albedo_fraction", 0.0))
    result: Dict[str, float] = {}

    for connection in physics_graph.boundary_connections.values():
        if bool(_get_attr_or_default(connection, "is_window", False)):
            continue
        if str(_get_attr_or_default(connection, "external_boundary_id", "outdoor_air")) != "outdoor_air":
            continue
        alpha = _get_attr_or_default(connection, "exterior_solar_absorptance_fraction", None)
        epsilon = _get_attr_or_default(connection, "exterior_longwave_emissivity_fraction", None)
        h_se = _get_attr_or_default(
            connection,
            "exterior_surface_heat_transfer_coefficient_w_m2_k",
            None,
        )
        if alpha is None or epsilon is None or h_se is None:
            continue
        area_m2 = float(_get_attr_or_default(connection, "area_m2", 0.0) or 0.0)
        u_value = float(_get_attr_or_default(connection, "u_value_w_m2k", 0.0) or 0.0)
        tilt_deg = float(_get_attr_or_default(connection, "tilt_deg", 90.0) or 0.0)
        azimuth_deg = float(
            _get_attr_or_default(connection, "orientation_deg", 0.0) or 0.0
        )
        irradiance_w_m2 = 0.0
        measured_vertical_w_m2 = _measured_vertical_irradiance_w_m2(
            weather_state,
            surface_tilt_deg=tilt_deg,
            surface_azimuth_deg=azimuth_deg,
        )
        if measured_vertical_w_m2 is not None:
            irradiance_w_m2 = measured_vertical_w_m2
        elif solar_zenith is not None and solar_azimuth is not None:
            irradiance_w_m2 = calculate_surface_solar_irradiance(
                solar_zenith_deg=float(solar_zenith),
                solar_azimuth_deg=float(solar_azimuth),
                surface_tilt_deg=tilt_deg,
                surface_azimuth_deg=azimuth_deg,
                direct_normal_radiation_w_m2=max(0.0, dni),
                diffuse_horizontal_radiation_w_m2=max(0.0, dhi),
                global_horizontal_radiation_w_m2=max(0.0, ghi),
                ground_albedo_fraction=albedo,
            ).total_w_m2
        longwave_w_m2 = 0.0
        if sky_c is not None:
            sky_view_factor = 0.5 * (1.0 + math.cos(math.radians(tilt_deg)))
            longwave_w_m2 = float(epsilon) * sky_view_factor * STEFAN_BOLTZMANN_W_M2_K4 * (
                (float(sky_c) + 273.15) ** 4 - (outdoor_c + 273.15) ** 4
            )
        gain_w = (
            u_value
            * area_m2
            / float(h_se)
            * (float(alpha) * irradiance_w_m2 + longwave_w_m2)
        )
        zone_id = str(_required_attr(connection, "zone_id"))
        result[zone_id] = result.get(zone_id, 0.0) + gain_w
    return result

def get_zone_outdoor_airflow_record_from_network(
    airflow_network: Any,
    zone_id: str,
) -> Any:
    """
    Read a ZoneOutdoorAirflowRecord-like object from BuildingAirflowNetwork.
    """

    if airflow_network is None:
        return None

    if hasattr(airflow_network, "get_outdoor_airflow_for_zone"):
        return airflow_network.get_outdoor_airflow_for_zone(zone_id)

    if hasattr(airflow_network, "outdoor_airflows_by_zone"):
        return airflow_network.outdoor_airflows_by_zone.get(zone_id)

    return None


def make_zone_ventilation_airflow_inputs_from_airflow_network(
    zone_model: Any,
    airflow_network: Any,
) -> ZoneVentilationAirflowInputs:
    """
    Build thermal ventilation inputs from airflow network.

    thermal.py does not calculate airflow here.
    It only consumes already-assembled airflow.
    """

    if zone_model is None:
        raise ValueError("zone_model cannot be None.")

    zone_id = _required_attr(zone_model, "zone_id")

    record = get_zone_outdoor_airflow_record_from_network(
        airflow_network=airflow_network,
        zone_id=zone_id,
    )

    if record is None:
        return make_zone_ventilation_airflow_inputs_from_zone_model(
            zone_model=zone_model,
            include_mechanical_ventilation=True,
        ).copy(
            source="ZoneModel fallback because airflow_network has no zone record"
        )

    infiltration_flow_m3_h = _get_attr_or_default(
        record,
        "infiltration_flow_m3_h",
        0.0,
    )

    mechanical_ventilation_flow_m3_h = _get_attr_or_default(
        record,
        "mechanical_ventilation_flow_m3_h",
        0.0,
    )
    mechanical_exhaust_flow_m3_h = _get_attr_or_default(
        record,
        "mechanical_exhaust_flow_m3_h",
        mechanical_ventilation_flow_m3_h,
    )

    window_airflow_m3_h = _get_attr_or_default(
        record,
        "window_airflow_m3_h",
        0.0,
    )

    return ZoneVentilationAirflowInputs(
        zone_id=zone_id,
        infiltration_airflow_m3_h=infiltration_flow_m3_h,
        mechanical_ventilation_flow_m3_h=mechanical_ventilation_flow_m3_h,
        mechanical_exhaust_flow_m3_h=mechanical_exhaust_flow_m3_h,
        window_opening_airflow_m3_h=window_airflow_m3_h,
        interzone_airflow_m3_h=0.0,
        source=THERMAL_VENTILATION_SOURCE_AIRFLOW_NETWORK,
    )


def make_building_ventilation_heat_exchange_from_airflow_network(
    building_model: Any,
    airflow_network: Any,
    mechanical_supply_temperature_by_zone_c: Optional[Dict[str, float]] = None,
) -> BuildingVentilationHeatExchange:
    """
    Build ventilation heat exchange from BuildingAirflowNetwork.

    Preferred Phase 8 thermal path:
        airflow.py calculates airflow network
        thermal.py consumes it

    No airflow is calculated here.
    """

    if building_model is None:
        raise ValueError("building_model cannot be None.")

    if not hasattr(building_model, "all_zone_models"):
        raise TypeError(
            "building_model must provide all_zone_models()."
        )

    if airflow_network is None:
        raise ValueError("airflow_network cannot be None.")

    airflow_inputs_by_zone = {}

    for zone_id, zone_model in building_model.all_zone_models().items():
        airflow_inputs_by_zone[zone_id] = (
            make_zone_ventilation_airflow_inputs_from_airflow_network(
                zone_model=zone_model,
                airflow_network=airflow_network,
            )
        )

    return make_building_ventilation_heat_exchange(
        building_model=building_model,
        airflow_inputs_by_zone=airflow_inputs_by_zone,
        mechanical_supply_temperature_by_zone_c=(
            mechanical_supply_temperature_by_zone_c
        ),
    )


def make_ventilation_heat_exchange_for_thermal(
    building_model: Any,
    airflow_network: Any = None,
    mechanical_supply_temperature_by_zone_c: Optional[Dict[str, float]] = None,
) -> BuildingVentilationHeatExchange:
    """
    Compatibility wrapper.

    Preferred Phase 8:
        consume BuildingAirflowNetwork

    Legacy fallback:
        use ZoneModel default infiltration/mechanical ventilation
    """

    if airflow_network is not None:
        return make_building_ventilation_heat_exchange_from_airflow_network(
            building_model=building_model,
            airflow_network=airflow_network,
            mechanical_supply_temperature_by_zone_c=(
                mechanical_supply_temperature_by_zone_c
            ),
        )

    return make_building_ventilation_heat_exchange(
        building_model=building_model,
        mechanical_supply_temperature_by_zone_c=(
            mechanical_supply_temperature_by_zone_c
        ),
    )


def make_external_boundary_conductance_by_zone_from_physics_graph(
    physics_graph: Any,
) -> Dict[str, Dict[str, float]]:
    """Aggregate opaque graph conductance by zone and named boundary.

    Windows remain on the shared window-boundary path. This function replaces
    the historical assumption that every opaque construction sees outdoor air.
    """

    if physics_graph is None or not hasattr(physics_graph, "boundary_connections"):
        raise TypeError("physics_graph must provide boundary_connections")
    result: Dict[str, Dict[str, float]] = {}
    for connection in physics_graph.boundary_connections.values():
        if bool(_get_attr_or_default(connection, "is_window", False)):
            continue
        zone_id = str(_required_attr(connection, "zone_id"))
        boundary_id = str(
            _get_attr_or_default(connection, "external_boundary_id", "outdoor_air")
        )
        area_m2 = _non_negative_float(
            _get_attr_or_default(connection, "area_m2", 0.0),
            "area_m2",
            zone_id,
        )
        u_value_w_m2k = _non_negative_float(
            _get_attr_or_default(connection, "u_value_w_m2k", 0.0),
            "u_value_w_m2k",
            zone_id,
        )
        by_boundary = result.setdefault(zone_id, {})
        by_boundary[boundary_id] = (
            by_boundary.get(boundary_id, 0.0)
            + area_m2 * u_value_w_m2k
            + _non_negative_float(
                _get_attr_or_default(
                    connection, "thermal_bridge_conductance_w_k", 0.0
                ),
                "thermal_bridge_conductance_w_k",
                zone_id,
            )
        )
    return result


def add_interzone_airflow_to_thermal_network(
    interzone_network: Optional[BuildingInterzoneThermalNetwork],
    airflow_network: Any,
) -> Optional[BuildingInterzoneThermalNetwork]:
    """Add conservative symmetric air-mixing conductance to thermal links."""

    if interzone_network is None or airflow_network is None:
        return interzone_network
    airflow_links = getattr(airflow_network, "interzone_airflow_links", None)
    if airflow_links is None:
        return interzone_network
    updated = interzone_network.copy()
    for link_id, link in updated.links.items():
        airflow_link = airflow_links.get(link.connection_id) or airflow_links.get(
            link_id
        )
        if airflow_link is None:
            continue
        airflow_model = str(
            _get_attr_or_default(airflow_link, "airflow_model", "")
        )
        if airflow_model == "two_opening_buoyancy":
            mixing_mass_flow_kg_s = _non_negative_float(
                _get_attr_or_default(
                    airflow_link, "mixing_mass_flow_kg_s", 0.0
                ),
                "mixing_mass_flow_kg_s",
                link_id,
            )
            link.h_w_k += (
                mixing_mass_flow_kg_s * THERMAL_AIR_SPECIFIC_HEAT_J_KG_K
            )
        else:
            mixing_flow_m3_h = _non_negative_float(
                _get_attr_or_default(airflow_link, "mixing_flow_m3_h", 0.0),
                "mixing_flow_m3_h",
                link_id,
            )
            link.h_w_k += ventilation_conductance_from_airflow_m3_h(
                mixing_flow_m3_h
            )
        link.source = link.source + " + BuildingAirflowNetwork"
    return updated

def step_building_thermal_state_semi_implicit(
    thermal_state: BuildingThermalState,
    building_parameters: BuildingThermalParameters,
    weather_state: Any,
    building_gains: Optional[BuildingThermalGains] = None,
    interzone_network: Optional[BuildingInterzoneThermalNetwork] = None,
    ventilation_exchange: Optional[BuildingVentilationHeatExchange] = None,
    additional_outside_conductance_by_zone_w_k: Optional[Dict[str, float]] = None,
    external_boundary_conductance_by_zone_w_k: Optional[
        Dict[str, Dict[str, float]]
    ] = None,
    external_boundary_temperatures_c: Optional[Dict[str, float]] = None,
    dt_minutes: float = DEFAULT_THERMAL_DT_MINUTES,
) -> BuildingSemiImplicitThermalStepResult:
    """
    Update all zone thermal states for one timestep.

    This is the Phase 4.10 timestep kernel.

    Important:
    - Solves every air/mass node and interzone link in one coupled linear
      system, so internal heat transfers conserve energy.
    - Keeps thermal.py independent from agents/controllers.
    - Agent/control/action outputs must be converted into BuildingThermalGains
      or ventilation/HVAC input objects before calling this function.
    """

    if not isinstance(thermal_state, BuildingThermalState):
        raise TypeError("thermal_state must be BuildingThermalState.")

    if not isinstance(building_parameters, BuildingThermalParameters):
        raise TypeError("building_parameters must be BuildingThermalParameters.")

    if weather_state is None:
        raise ValueError("weather_state cannot be None.")

    if building_gains is None:
        building_gains = BuildingThermalGains()
        
    if additional_outside_conductance_by_zone_w_k is None:
        additional_outside_conductance_by_zone_w_k = {}
    if external_boundary_temperatures_c is None:
        external_boundary_temperatures_c = {}

    outdoor_temperature_c = float(
        _get_attr_or_default(
            weather_state,
            "outdoor_temperature_c",
            20.0,
        )
    )

    dt_seconds = float(dt_minutes) * 60.0
    if dt_seconds <= 0.0:
        raise ValueError("dt_minutes must be positive.")

    zone_ids = [
        zone_id
        for zone_id in building_parameters.zone_ids()
        if thermal_state.has_zone(zone_id)
    ]
    zone_index = {zone_id: index for index, zone_id in enumerate(zone_ids)}
    node_count = 2 * len(zone_ids)
    matrix = np.zeros((node_count, node_count), dtype=np.float64)
    rhs = np.zeros(node_count, dtype=np.float64)
    air_targets_by_zone: Dict[str, List[ThermalTemperatureTarget]] = {}

    for zone_id, index in zone_index.items():
        air_index = 2 * index
        mass_index = air_index + 1
        zone_state = thermal_state.get_zone_state(zone_id)
        zone_parameters = building_parameters.get_zone_parameters(zone_id)
        zone_gains = building_gains.get_zone_gains(zone_id)

        ventilation_h_w_k = zone_parameters.h_ventilation_w_k
        ventilation_temperature_c = outdoor_temperature_c
        if (
            ventilation_exchange is not None
            and zone_id in ventilation_exchange.zone_ventilation
        ):
            zone_ventilation = ventilation_exchange.zone_ventilation[zone_id]
            ventilation_h_w_k = _non_negative_float(
                zone_ventilation.h_ventilation_w_k,
                "ventilation_h_w_k",
                zone_id,
            )
            ventilation_temperature_c = (
                zone_ventilation.effective_supply_temperature_c(
                    outdoor_temperature_c
                )
            )

        additional_outside_h_w_k = _non_negative_float(
            additional_outside_conductance_by_zone_w_k.get(zone_id, 0.0),
            "additional_outside_h_w_k",
            zone_id,
        )
        boundary_conductances = None
        if external_boundary_conductance_by_zone_w_k is not None:
            boundary_conductances = external_boundary_conductance_by_zone_w_k.get(
                zone_id, {}
            )
        if boundary_conductances is None:
            boundary_conductances = {"outdoor_air": zone_parameters.h_external_w_k}
        boundary_conductances = {
            str(boundary_id): _non_negative_float(
                conductance_w_k, "external_boundary_conductance_w_k", zone_id
            )
            for boundary_id, conductance_w_k in boundary_conductances.items()
        }
        boundary_conductances["outdoor_air"] = (
            boundary_conductances.get("outdoor_air", 0.0)
            + additional_outside_h_w_k
        )
        envelope_h_w_k = sum(boundary_conductances.values())
        boundary_rhs_w = 0.0
        boundary_targets = []
        for boundary_id, conductance_w_k in sorted(boundary_conductances.items()):
            if boundary_id == "outdoor_air":
                boundary_temperature_c = outdoor_temperature_c
                target_type = THERMAL_PATH_OUTSIDE
            else:
                if boundary_id not in external_boundary_temperatures_c:
                    raise ValueError(
                        "missing temperature for external boundary "
                        + boundary_id
                        + " in zone "
                        + zone_id
                    )
                boundary_temperature_c = float(
                    external_boundary_temperatures_c[boundary_id]
                )
                if not np.isfinite(boundary_temperature_c):
                    raise ValueError(
                        "external boundary temperature must be finite for "
                        + boundary_id
                    )
                target_type = THERMAL_PATH_EXTERNAL_BOUNDARY
            boundary_rhs_w += conductance_w_k * boundary_temperature_c
            boundary_targets.append(
                ThermalTemperatureTarget(
                    target_id="boundary:" + boundary_id,
                    target_type=target_type,
                    temperature_c=boundary_temperature_c,
                    h_w_k=conductance_w_k,
                )
            )
        outside_h_w_k = envelope_h_w_k + ventilation_h_w_k
        h_air_mass_w_k = zone_parameters.h_air_mass_w_k
        c_air_over_dt = zone_parameters.c_air_j_k / dt_seconds
        c_mass_over_dt = zone_parameters.c_mass_j_k / dt_seconds

        matrix[air_index, air_index] = (
            c_air_over_dt + h_air_mass_w_k + outside_h_w_k
        )
        matrix[air_index, mass_index] = -h_air_mass_w_k
        matrix[mass_index, air_index] = -h_air_mass_w_k
        matrix[mass_index, mass_index] = c_mass_over_dt + h_air_mass_w_k

        rhs[air_index] = (
            c_air_over_dt * zone_state.air_temperature_c
            + boundary_rhs_w
            + ventilation_h_w_k * ventilation_temperature_c
            + zone_gains.convective_gain_w()
        )
        rhs[mass_index] = (
            c_mass_over_dt * zone_state.mass_temperature_c
            + zone_gains.radiative_gain_w()
        )
        air_targets_by_zone[zone_id] = [
            ThermalTemperatureTarget(
                target_id=zone_id + "__mass_coupled",
                target_type=THERMAL_PATH_AIR_MASS,
                temperature_c=zone_state.mass_temperature_c,
                h_w_k=h_air_mass_w_k,
            ),
            ThermalTemperatureTarget(
                target_id="outside_ventilation",
                target_type=THERMAL_PATH_VENTILATION,
                temperature_c=ventilation_temperature_c,
                h_w_k=ventilation_h_w_k,
            ),
        ] + boundary_targets

    if interzone_network is not None:
        for link in interzone_network.links.values():
            if (
                link.zone_a_id not in zone_index
                or link.zone_b_id not in zone_index
            ):
                continue
            zone_a_air_index = 2 * zone_index[link.zone_a_id]
            zone_b_air_index = 2 * zone_index[link.zone_b_id]
            matrix[zone_a_air_index, zone_a_air_index] += link.h_w_k
            matrix[zone_b_air_index, zone_b_air_index] += link.h_w_k
            matrix[zone_a_air_index, zone_b_air_index] -= link.h_w_k
            matrix[zone_b_air_index, zone_a_air_index] -= link.h_w_k
            state_a = thermal_state.get_zone_state(link.zone_a_id)
            state_b = thermal_state.get_zone_state(link.zone_b_id)
            air_targets_by_zone[link.zone_a_id].append(
                ThermalTemperatureTarget(
                    target_id=link.link_id + "__" + link.zone_b_id,
                    target_type=THERMAL_PATH_INTERZONE,
                    temperature_c=state_b.air_temperature_c,
                    h_w_k=link.h_w_k,
                )
            )
            air_targets_by_zone[link.zone_b_id].append(
                ThermalTemperatureTarget(
                    target_id=link.link_id + "__" + link.zone_a_id,
                    target_type=THERMAL_PATH_INTERZONE,
                    temperature_c=state_a.air_temperature_c,
                    h_w_k=link.h_w_k,
                )
            )

    solution = np.linalg.solve(matrix, rhs) if node_count else np.empty(0)
    updated_zone_states = {}
    zone_results = {}
    for zone_id, index in zone_index.items():
        air_index = 2 * index
        mass_index = air_index + 1
        zone_state = thermal_state.get_zone_state(zone_id)
        zone_gains = building_gains.get_zone_gains(zone_id)
        new_air_temperature_c = float(solution[air_index])
        new_mass_temperature_c = float(solution[mass_index])
        result = ZoneSemiImplicitThermalUpdateResult(
            zone_id=zone_id,
            old_air_temperature_c=zone_state.air_temperature_c,
            old_mass_temperature_c=zone_state.mass_temperature_c,
            new_air_temperature_c=new_air_temperature_c,
            new_mass_temperature_c=new_mass_temperature_c,
            air_capacitance_j_k=building_parameters.get_zone_parameters(
                zone_id
            ).c_air_j_k,
            mass_capacitance_j_k=building_parameters.get_zone_parameters(
                zone_id
            ).c_mass_j_k,
            convective_gain_w=zone_gains.convective_gain_w(),
            radiative_gain_w=zone_gains.radiative_gain_w(),
            air_node_targets=air_targets_by_zone[zone_id],
            mass_node_targets=[
                ThermalTemperatureTarget(
                    target_id=zone_id + "__air_coupled",
                    target_type=THERMAL_PATH_AIR_MASS,
                    temperature_c=new_air_temperature_c,
                    h_w_k=building_parameters.get_zone_parameters(
                        zone_id
                    ).h_air_mass_w_k,
                )
            ],
            dt_seconds=dt_seconds,
        )
        updated_zone_states[zone_id] = result.to_zone_thermal_state()
        zone_results[zone_id] = result

    updated_state = BuildingThermalState(
        zone_states=updated_zone_states,
    )

    return BuildingSemiImplicitThermalStepResult(
        updated_state=updated_state,
        zone_results=zone_results,
        dt_minutes=dt_minutes,
    )

def is_building_window_boundary_result_like(
    window_boundary_result: Any,
) -> bool:
    if window_boundary_result is None:
        return False

    required_methods = [
        "effective_solar_area_by_zone_m2",
        "closed_window_conductance_by_zone_w_k",
        "window_results_for_zone",
    ]

    for method_name in required_methods:
        if not hasattr(window_boundary_result, method_name):
            return False

    return True


def is_airflow_network_like(
    airflow_network: Any,
) -> bool:
    if airflow_network is None:
        return False

    if not hasattr(airflow_network, "outdoor_airflows_by_zone"):
        return False

    return True


def indoor_temperature_by_zone_from_thermal_state(
    thermal_state: BuildingThermalState,
) -> Dict[str, float]:
    if not isinstance(thermal_state, BuildingThermalState):
        raise TypeError("thermal_state must be BuildingThermalState.")

    return {
        zone_id: zone_state.air_temperature_c
        for zone_id, zone_state in thermal_state.zone_states.items()
    }


def window_closed_conductance_by_zone_from_boundary_w_k(
    window_boundary_result: Any,
) -> Dict[str, float]:
    if not is_building_window_boundary_result_like(window_boundary_result):
        raise TypeError(
            "window_boundary_result must behave like BuildingWindowBoundaryResult."
        )

    return window_boundary_result.closed_window_conductance_by_zone_w_k()

def _make_adjacent_air_temperature_targets(
    zone_id: str,
    thermal_state: BuildingThermalState,
    interzone_network: Optional[BuildingInterzoneThermalNetwork],
) -> List[ThermalTemperatureTarget]:
    if interzone_network is None:
        return []

    targets = []

    for link in interzone_network.links_for_zone(zone_id):
        if link.zone_a_id == zone_id:
            adjacent_zone_id = link.zone_b_id
        else:
            adjacent_zone_id = link.zone_a_id

        if not thermal_state.has_zone(adjacent_zone_id):
            continue

        adjacent_state = thermal_state.get_zone_state(adjacent_zone_id)

        targets.append(
            ThermalTemperatureTarget(
                target_id=link.link_id + "__" + adjacent_zone_id,
                target_type=THERMAL_PATH_INTERZONE,
                temperature_c=adjacent_state.air_temperature_c,
                h_w_k=link.h_w_k,
            )
        )

    return targets

def appliance_energy_wh_to_average_gain_w(
    appliance_energy_wh_by_zone: Dict[str, float],
    dt_minutes: float,
) -> Dict[str, float]:
    """
    Convert timestep appliance/internal-source energy to average gain power.

        W = Wh / h

    Used to connect internal source records to the thermal model.
    """

    dt_hours = float(dt_minutes) / 60.0

    if dt_hours <= 0.0:
        raise ValueError("dt_minutes must be positive.")

    out = {}

    for zone_id, energy_wh in appliance_energy_wh_by_zone.items():
        out[zone_id] = float(energy_wh) / dt_hours

    return out




def make_building_thermal_parameters(
    building_model: Any,
) -> BuildingThermalParameters:
    """
    Build thermal parameters for all zones in a BuildingModel.
    """

    if building_model is None:
        raise ValueError("building_model cannot be None.")

    if not hasattr(building_model, "all_zone_models"):
        raise TypeError(
            "building_model must provide all_zone_models()."
        )

    zone_models = building_model.all_zone_models()

    zone_parameters = {}

    for zone_id, zone_model in zone_models.items():
        zone_parameters[zone_id] = make_zone_thermal_parameters(zone_model)

    return BuildingThermalParameters(
        zone_parameters=zone_parameters,
    )

def _required_attr(obj: Any, attribute_name: str) -> Any:
    value = getattr(obj, attribute_name, None)

    if value is None or not str(value).strip():
        raise ValueError(
            "Missing required attribute: " + attribute_name
        )

    return value


def _positive_attr(
    obj: Any,
    attribute_name: str,
    zone_id: str,
    default: Any = None,
) -> float:
    value = getattr(obj, attribute_name, default)

    if value is None:
        raise ValueError(
            attribute_name + " is required for zone " + zone_id
        )

    return _positive_float(value, attribute_name, zone_id)


def _non_negative_attr(
    obj: Any,
    attribute_name: str,
    zone_id: str,
    default: Any = None,
) -> float:
    value = getattr(obj, attribute_name, default)

    if value is None:
        value = default

    if value is None:
        raise ValueError(
            attribute_name + " is required for zone " + zone_id
        )

    return _non_negative_float(value, attribute_name, zone_id)


def _positive_float(
    value: Any,
    field_name: str,
    zone_id: str,
) -> float:
    value = float(value)

    if value <= 0.0:
        raise ValueError(
            field_name + " must be positive for zone " + zone_id
        )

    return value


def _non_negative_float(
    value: Any,
    field_name: str,
    zone_id: str,
) -> float:
    value = float(value)

    if value < 0.0:
        raise ValueError(
            field_name + " cannot be negative for zone " + zone_id
        )

    return value


def _estimate_effective_mass_area_m2(
    floor_area_m2: float,
    internal_wall_area_m2: float,
) -> float:
    """
    Estimate effective area coupled to the mass node.

    This is a practical reduced-order approximation.
    It is not a full ISO 5R1C surface-area implementation.
    """

    area = float(floor_area_m2) + float(internal_wall_area_m2)

    if area <= 0.0:
        area = float(floor_area_m2)

    return area


def _ventilation_conductance_from_ach(
    air_volume_m3: float,
    ach: float,
) -> float:
    """
    Convert ACH to ventilation heat-transfer conductance.

        H_vent = rho_air * cp_air * airflow_m3_s
    """

    airflow_m3_s = (
        float(air_volume_m3)
        * float(ach)
        / 3600.0
    )

    return (
        THERMAL_AIR_DENSITY_KG_M3
        * THERMAL_AIR_SPECIFIC_HEAT_J_KG_K
        * airflow_m3_s
    )


def make_initial_building_thermal_state(
    building_model: Any,
) -> BuildingThermalState:
    """
    Create initial BuildingThermalState from BuildingModel.

    Uses:
    - ZoneModel.initial_air_temperature_c
    - ZoneModel.initial_mass_temperature_c

    Falls back to:
    - ZoneModel.initial_temp_c
    - 20°C
    """

    if building_model is None:
        raise ValueError("building_model cannot be None.")

    if not hasattr(building_model, "all_zone_models"):
        raise TypeError(
            "building_model must provide all_zone_models()."
        )

    zone_models = building_model.all_zone_models()

    zone_states = {}

    for zone_id, zone_model in zone_models.items():
        air_temperature_c = _get_attr_or_default(
            zone_model,
            "initial_air_temperature_c",
            None,
        )

        if air_temperature_c is None:
            air_temperature_c = _get_attr_or_default(
                zone_model,
                "initial_temp_c",
                20.0,
            )

        mass_temperature_c = _get_attr_or_default(
            zone_model,
            "initial_mass_temperature_c",
            None,
        )

        if mass_temperature_c is None:
            mass_temperature_c = air_temperature_c

        zone_states[zone_id] = ZoneThermalState(
            zone_id=zone_id,
            air_temperature_c=air_temperature_c,
            mass_temperature_c=mass_temperature_c,
        )

    return BuildingThermalState(
        zone_states=zone_states,
    )


def _get_attr_or_default(
    obj: Any,
    attribute_name: str,
    default: Any,
) -> Any:
    if obj is None:
        return default

    return getattr(obj, attribute_name, default)
