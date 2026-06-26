"""
ABBEY airflow and CO2 model architecture.

Phase 5.1:
- formally defines the airflow/CO2 modelling decision
- no airflow solver yet
- no CO2 timestep update yet
- no pressure-network model yet

Decision:
    Phase 5 airflow model = simplified multizone airflow approximation.
    Phase 5 CO2 model = zone-level mass-balance model.

Agent-friendly rule:
    Agents, actions, and control states must be converted into clean physical
    bridge inputs before entering this module.
"""

from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional
import copy
import math


AIRFLOW_MODEL_FAMILY = "simplified_multizone_airflow"
CO2_MODEL_FAMILY = "zone_level_mass_balance"

AIRFLOW_SPATIAL_RESOLUTION = "zone"
AIRFLOW_MULTIZONE_MODE = "multizone"

AIRFLOW_PRESSURE_NETWORK_MODE = "not_pressure_network_yet"
AIRFLOW_FUTURE_PRESSURE_NETWORK_READY = True

AIRFLOW_OUTDOOR_BOUNDARY_SOURCE = "WeatherState"
AIRFLOW_TOPOLOGY_SOURCE = "BuildingPhysicsGraph"
AIRFLOW_PARAMETER_SOURCE = "ZoneModel"

AIRFLOW_WINDOW_MODEL = "wind_orientation_opening_approximation"
AIRFLOW_DOOR_MODEL = "interzone_mixing_approximation"
AIRFLOW_MECHANICAL_MODEL = "fixed_flow_input"

CO2_STATE_VARIABLE = "co2_ppm"
AIR_VOLUME_VARIABLE = "air_volume_m3"

AIR_CO2_MODEL_DECISION = (
    "simplified_multizone_airflow_plus_zone_level_co2_mass_balance"
)

DEFAULT_INITIAL_CO2_PPM = 600.0
DEFAULT_ZONE_AIR_VOLUME_M3 = 50.0
MIN_PHYSICAL_CO2_PPM = 300.0

DEFAULT_INFILTRATION_ACH = 0.0
DEFAULT_MECHANICAL_VENTILATION_FLOW_M3_H = 0.0
DEFAULT_CO2_GENERATION_PER_PERSON_M3_H = 0.018

DEFAULT_WINDOW_OPENING_FRACTION = 0.0
DEFAULT_DOOR_OPENING_FRACTION = 0.0
DEFAULT_NUMBER_OF_PEOPLE = 0.0

DEFAULT_WINDOW_DISCHARGE_COEFFICIENT = 0.60
DEFAULT_WINDOW_MAX_OPENING_AREA_M2 = 0.0
DEFAULT_WINDOW_WIND_ALIGNMENT_FACTOR_IF_UNKNOWN = 0.50

OUTDOOR_AIRFLOW_SOURCE_INFILTRATION = "default_infiltration"
OUTDOOR_AIRFLOW_SOURCE_MECHANICAL = "mechanical_ventilation"
OUTDOOR_AIRFLOW_SOURCE_WINDOW = "window_airflow"

OUTDOOR_AIRFLOW_MIXING_MODE = "balanced_outdoor_air_exchange_mixing"

DEFAULT_INTERZONE_DISCHARGE_COEFFICIENT = 0.60
DEFAULT_INTERZONE_MAX_OPENING_AREA_M2 = 0.0
DEFAULT_INTERZONE_MIXING_AIR_SPEED_M_S = 0.10
DEFAULT_INTERZONE_BASE_AIRFLOW_M3_H = 0.0

INTERZONE_AIRFLOW_SOURCE_BASE = "base_interzone_airflow"
INTERZONE_AIRFLOW_SOURCE_DOOR_OPENING = "door_opening"
INTERZONE_AIRFLOW_MIXING_MODE = "symmetric_interzone_mixing"
INTERZONE_AIRFLOW_SOURCE_STATIC_GRAPH_DOOR_STATE = (
    "static_graph_zone_connection_open_fraction"
)

AIRFLOW_NETWORK_MODE = "assembled_simplified_airflow_network"
AIRFLOW_NETWORK_PRESSURE_SOLVE = "not_solved"

DEFAULT_OUTDOOR_CO2_PPM = 420.0
CO2_TIMESTEP_METHOD = "semi_implicit_mass_balance"
CO2_GENERATION_PPM_FACTOR = 1000000.0

AIR_CO2_MODEL_INTERFACE_MODE = "runner_facing_airflow_co2_model"
DEFAULT_AIR_CO2_DT_MINUTES = 15.0

AIRFLOW_WINDOW_BOUNDARY_SOURCE = "BuildingWindowBoundaryResult"
AIRFLOW_PHASE8_WINDOW_COMPATIBILITY_MODE = "phase8_window_boundary_optional"
AIRFLOW_LEGACY_WINDOW_LOGIC = "legacy_boundary_connection_window_airflow"

@dataclass
class AirCO2ArchitectureDecision:
    """
    Formal architecture decision for ABBEY airflow and CO2 modelling.

    This is intentionally not a solver.
    It only locks the modelling structure before implementation.
    """

    airflow_model_family: str = AIRFLOW_MODEL_FAMILY
    co2_model_family: str = CO2_MODEL_FAMILY

    spatial_resolution: str = AIRFLOW_SPATIAL_RESOLUTION
    multizone_mode: str = AIRFLOW_MULTIZONE_MODE

    pressure_network_mode: str = AIRFLOW_PRESSURE_NETWORK_MODE
    future_pressure_network_ready: bool = AIRFLOW_FUTURE_PRESSURE_NETWORK_READY

    outside_boundary_source: str = AIRFLOW_OUTDOOR_BOUNDARY_SOURCE
    topology_source: str = AIRFLOW_TOPOLOGY_SOURCE
    parameter_source: str = AIRFLOW_PARAMETER_SOURCE

    window_airflow_model: str = AIRFLOW_WINDOW_MODEL
    door_airflow_model: str = AIRFLOW_DOOR_MODEL
    mechanical_ventilation_model: str = AIRFLOW_MECHANICAL_MODEL

    state_variables: List[str] = None

    decision: str = AIR_CO2_MODEL_DECISION

    def __post_init__(self) -> None:
        if self.state_variables is None:
            self.state_variables = [
                AIR_VOLUME_VARIABLE,
                CO2_STATE_VARIABLE,
            ]

        self.airflow_model_family = str(self.airflow_model_family).strip().lower()
        self.co2_model_family = str(self.co2_model_family).strip().lower()
        self.spatial_resolution = str(self.spatial_resolution).strip().lower()
        self.multizone_mode = str(self.multizone_mode).strip().lower()
        self.pressure_network_mode = str(self.pressure_network_mode).strip().lower()

        self.outside_boundary_source = str(self.outside_boundary_source).strip()
        self.topology_source = str(self.topology_source).strip()
        self.parameter_source = str(self.parameter_source).strip()

        self.window_airflow_model = str(self.window_airflow_model).strip().lower()
        self.door_airflow_model = str(self.door_airflow_model).strip().lower()
        self.mechanical_ventilation_model = str(
            self.mechanical_ventilation_model
        ).strip().lower()

        self.decision = str(self.decision).strip().lower()

        self._validate()

    def _validate(self) -> None:
        if self.airflow_model_family != AIRFLOW_MODEL_FAMILY:
            raise ValueError(
                "airflow_model_family must be " + AIRFLOW_MODEL_FAMILY + "."
            )

        if self.co2_model_family != CO2_MODEL_FAMILY:
            raise ValueError(
                "co2_model_family must be " + CO2_MODEL_FAMILY + "."
            )

        if self.spatial_resolution != AIRFLOW_SPATIAL_RESOLUTION:
            raise ValueError(
                "Airflow/CO2 spatial_resolution must be zone."
            )

        if self.multizone_mode != AIRFLOW_MULTIZONE_MODE:
            raise ValueError(
                "Airflow/CO2 model must be multizone."
            )

        if self.pressure_network_mode != AIRFLOW_PRESSURE_NETWORK_MODE:
            raise ValueError(
                "Phase 5 must not use full pressure-network airflow yet."
            )

        if not self.future_pressure_network_ready:
            raise ValueError(
                "Phase 5 architecture must keep future pressure-network upgrade open."
            )

        if self.outside_boundary_source != AIRFLOW_OUTDOOR_BOUNDARY_SOURCE:
            raise ValueError(
                "outside_boundary_source must be WeatherState."
            )

        if self.topology_source != AIRFLOW_TOPOLOGY_SOURCE:
            raise ValueError(
                "topology_source must be BuildingPhysicsGraph."
            )

        if self.parameter_source != AIRFLOW_PARAMETER_SOURCE:
            raise ValueError(
                "parameter_source must be ZoneModel."
            )

        if self.window_airflow_model != AIRFLOW_WINDOW_MODEL:
            raise ValueError(
                "window_airflow_model must be "
                + AIRFLOW_WINDOW_MODEL
                + "."
            )

        if self.door_airflow_model != AIRFLOW_DOOR_MODEL:
            raise ValueError(
                "door_airflow_model must be "
                + AIRFLOW_DOOR_MODEL
                + "."
            )

        if self.mechanical_ventilation_model != AIRFLOW_MECHANICAL_MODEL:
            raise ValueError(
                "mechanical_ventilation_model must be "
                + AIRFLOW_MECHANICAL_MODEL
                + "."
            )

        required_state_variables = {
            AIR_VOLUME_VARIABLE,
            CO2_STATE_VARIABLE,
        }

        if set(self.state_variables) != required_state_variables:
            raise ValueError(
                "Air/CO2 state variables must be air_volume_m3 and co2_ppm."
            )

    def copy(self, **updates: Any) -> "AirCO2ArchitectureDecision":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "airflow_model_family": self.airflow_model_family,
            "co2_model_family": self.co2_model_family,
            "spatial_resolution": self.spatial_resolution,
            "multizone_mode": self.multizone_mode,
            "pressure_network_mode": self.pressure_network_mode,
            "future_pressure_network_ready": self.future_pressure_network_ready,
            "outside_boundary_source": self.outside_boundary_source,
            "topology_source": self.topology_source,
            "parameter_source": self.parameter_source,
            "window_airflow_model": self.window_airflow_model,
            "door_airflow_model": self.door_airflow_model,
            "mechanical_ventilation_model": self.mechanical_ventilation_model,
            "state_variables": list(self.state_variables),
            "decision": self.decision,
        }

@dataclass
class ZoneAirState:
    """
    Dynamic air/CO2 state for one zone.

    Phase 5 tracks:
    - CO2 concentration
    - air volume used for CO2 storage calculations

    Humidity is intentionally not part of this state.
    It will be handled later by the moisture/humidity phase.
    """

    zone_id: str
    co2_ppm: float = DEFAULT_INITIAL_CO2_PPM
    air_volume_m3: float = DEFAULT_ZONE_AIR_VOLUME_M3

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneAirState.zone_id cannot be empty.")

        self.co2_ppm = _bounded_co2_ppm(self.co2_ppm)

        self.air_volume_m3 = _positive_float(
            self.air_volume_m3,
            "air_volume_m3",
            self.zone_id,
        )

    def copy(self, **updates: Any) -> "ZoneAirState":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "co2_ppm": self.co2_ppm,
            "air_volume_m3": self.air_volume_m3,
        }


@dataclass
class BuildingAirState:
    """
    Dynamic air/CO2 state for all zones.
    """

    zone_states: Dict[str, ZoneAirState] = None

    def __post_init__(self) -> None:
        if self.zone_states is None:
            self.zone_states = {}

        cleaned = {}

        for zone_id, state in self.zone_states.items():
            if not isinstance(state, ZoneAirState):
                raise TypeError(
                    "BuildingAirState.zone_states must contain ZoneAirState objects."
                )

            if zone_id != state.zone_id:
                raise ValueError(
                    "BuildingAirState key "
                    + zone_id
                    + " does not match ZoneAirState.zone_id "
                    + state.zone_id
                )

            cleaned[zone_id] = state

        self.zone_states = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_states.keys())

    def has_zone(self, zone_id: str) -> bool:
        return zone_id in self.zone_states

    def get_zone_state(self, zone_id: str) -> ZoneAirState:
        if zone_id not in self.zone_states:
            raise KeyError(
                "Air state for zone "
                + zone_id
                + " not found."
            )

        return self.zone_states[zone_id]

    def set_zone_state(self, zone_state: ZoneAirState) -> None:
        if not isinstance(zone_state, ZoneAirState):
            raise TypeError("zone_state must be ZoneAirState.")

        self.zone_states[zone_state.zone_id] = zone_state

    def copy(self, **updates: Any) -> "BuildingAirState":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_states": {
                zone_id: state.to_dict()
                for zone_id, state in self.zone_states.items()
            }
        }


@dataclass
class ZoneAirflowParameters:
    """
    Static airflow and CO2 parameters for one zone.

    Built from ZoneModel.

    These are parameters, not dynamic state:
    - air volume
    - default infiltration
    - mechanical ventilation capability
    - CO2 generation per person
    """

    zone_id: str

    air_volume_m3: float

    default_infiltration_ach: float = DEFAULT_INFILTRATION_ACH
    default_infiltration_flow_m3_h: float = 0.0

    mechanical_ventilation_available: bool = False
    mechanical_ventilation_flow_m3_h: float = DEFAULT_MECHANICAL_VENTILATION_FLOW_M3_H

    co2_generation_per_person_m3_h: float = DEFAULT_CO2_GENERATION_PER_PERSON_M3_H

    source: str = "ZoneModel"

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneAirflowParameters.zone_id cannot be empty.")

        self.air_volume_m3 = _positive_float(
            self.air_volume_m3,
            "air_volume_m3",
            self.zone_id,
        )

        self.default_infiltration_ach = _non_negative_float(
            self.default_infiltration_ach,
            "default_infiltration_ach",
            self.zone_id,
        )

        if self.default_infiltration_flow_m3_h <= 0.0:
            self.default_infiltration_flow_m3_h = (
                self.air_volume_m3
                * self.default_infiltration_ach
            )

        self.default_infiltration_flow_m3_h = _non_negative_float(
            self.default_infiltration_flow_m3_h,
            "default_infiltration_flow_m3_h",
            self.zone_id,
        )

        self.mechanical_ventilation_available = bool(
            self.mechanical_ventilation_available
        )

        self.mechanical_ventilation_flow_m3_h = _non_negative_float(
            self.mechanical_ventilation_flow_m3_h,
            "mechanical_ventilation_flow_m3_h",
            self.zone_id,
        )

        if not self.mechanical_ventilation_available:
            self.mechanical_ventilation_flow_m3_h = 0.0

        self.co2_generation_per_person_m3_h = _non_negative_float(
            self.co2_generation_per_person_m3_h,
            "co2_generation_per_person_m3_h",
            self.zone_id,
        )

    def default_infiltration_flow_m3_s(self) -> float:
        return self.default_infiltration_flow_m3_h / 3600.0

    def mechanical_ventilation_flow_m3_s(self) -> float:
        return self.mechanical_ventilation_flow_m3_h / 3600.0

    def co2_generation_per_person_m3_s(self) -> float:
        return self.co2_generation_per_person_m3_h / 3600.0

    def copy(self, **updates: Any) -> "ZoneAirflowParameters":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "air_volume_m3": self.air_volume_m3,
            "default_infiltration_ach": self.default_infiltration_ach,
            "default_infiltration_flow_m3_h": self.default_infiltration_flow_m3_h,
            "default_infiltration_flow_m3_s": self.default_infiltration_flow_m3_s(),
            "mechanical_ventilation_available": self.mechanical_ventilation_available,
            "mechanical_ventilation_flow_m3_h": self.mechanical_ventilation_flow_m3_h,
            "mechanical_ventilation_flow_m3_s": self.mechanical_ventilation_flow_m3_s(),
            "co2_generation_per_person_m3_h": self.co2_generation_per_person_m3_h,
            "co2_generation_per_person_m3_s": self.co2_generation_per_person_m3_s(),
            "source": self.source,
        }
    
@dataclass
class BuildingAirflowParameters:
    """
    Static airflow and CO2 parameters for all zones.
    """

    zone_parameters: Dict[str, ZoneAirflowParameters] = None

    def __post_init__(self) -> None:
        if self.zone_parameters is None:
            self.zone_parameters = {}

        cleaned = {}

        for zone_id, parameters in self.zone_parameters.items():
            if not isinstance(parameters, ZoneAirflowParameters):
                raise TypeError(
                    "BuildingAirflowParameters.zone_parameters must contain "
                    "ZoneAirflowParameters objects."
                )

            if zone_id != parameters.zone_id:
                raise ValueError(
                    "BuildingAirflowParameters key "
                    + zone_id
                    + " does not match parameters.zone_id "
                    + parameters.zone_id
                )

            cleaned[zone_id] = parameters

        self.zone_parameters = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_parameters.keys())

    def has_zone(self, zone_id: str) -> bool:
        return zone_id in self.zone_parameters

    def get_zone_parameters(self, zone_id: str) -> ZoneAirflowParameters:
        if zone_id not in self.zone_parameters:
            raise KeyError(
                "Airflow parameters for zone "
                + zone_id
                + " not found."
            )

        return self.zone_parameters[zone_id]

    def copy(self, **updates: Any) -> "BuildingAirflowParameters":
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
class ZoneOccupancyInput:
    """
    Clean occupancy input for airflow/CO2.

    Agent-friendly:
    agents are converted into this object outside airflow.py.
    """

    zone_id: str
    number_of_people: float = DEFAULT_NUMBER_OF_PEOPLE
    source: str = "external_bridge"

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneOccupancyInput.zone_id cannot be empty.")

        self.number_of_people = _non_negative_float(
            self.number_of_people,
            "number_of_people",
            self.zone_id,
        )

    def copy(self, **updates: Any) -> "ZoneOccupancyInput":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "number_of_people": self.number_of_people,
            "source": self.source,
        }


@dataclass
class WindowOpeningInput:
    """
    Clean window-opening input.

    This is the bridge between agents/controls and airflow physics.
    """

    boundary_connection_id: str
    zone_id: str
    opening_fraction: float = DEFAULT_WINDOW_OPENING_FRACTION
    source: str = "external_bridge"

    def __post_init__(self) -> None:
        if not self.boundary_connection_id:
            raise ValueError(
                "WindowOpeningInput.boundary_connection_id cannot be empty."
            )

        if not self.zone_id:
            raise ValueError("WindowOpeningInput.zone_id cannot be empty.")

        self.opening_fraction = _clamp_unit_interval(
            self.opening_fraction
        )

    def is_open(self) -> bool:
        return self.opening_fraction > 0.0

    def copy(self, **updates: Any) -> "WindowOpeningInput":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_connection_id": self.boundary_connection_id,
            "zone_id": self.zone_id,
            "opening_fraction": self.opening_fraction,
            "is_open": self.is_open(),
            "source": self.source,
        }


@dataclass
class DoorOpeningInput:
    """
    Clean door/opening input for interzone airflow.

    This does not know agents, schedules, or actions.
    It only knows physical opening fraction.
    """

    zone_connection_id: str
    zone_a_id: str
    zone_b_id: str
    opening_fraction: float = DEFAULT_DOOR_OPENING_FRACTION
    source: str = "external_bridge"

    def __post_init__(self) -> None:
        if not self.zone_connection_id:
            raise ValueError(
                "DoorOpeningInput.zone_connection_id cannot be empty."
            )

        if not self.zone_a_id:
            raise ValueError("DoorOpeningInput.zone_a_id cannot be empty.")

        if not self.zone_b_id:
            raise ValueError("DoorOpeningInput.zone_b_id cannot be empty.")

        if self.zone_a_id == self.zone_b_id:
            raise ValueError(
                "DoorOpeningInput cannot connect a zone to itself: "
                + self.zone_a_id
            )

        self.opening_fraction = _clamp_unit_interval(
            self.opening_fraction
        )

    def is_open(self) -> bool:
        return self.opening_fraction > 0.0

    def copy(self, **updates: Any) -> "DoorOpeningInput":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_connection_id": self.zone_connection_id,
            "zone_a_id": self.zone_a_id,
            "zone_b_id": self.zone_b_id,
            "opening_fraction": self.opening_fraction,
            "is_open": self.is_open(),
            "source": self.source,
        }

@dataclass
class MechanicalVentilationInput:
    """
    Clean mechanical ventilation command for one zone.

    This is dynamic control input, not static ZoneModel capability.
    The command must already be sanitized upstream against system availability.
    """

    zone_id: str
    ventilation_flow_m3_h: float = 0.0
    source: str = "ZoneControlCommand"

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("MechanicalVentilationInput.zone_id cannot be empty.")

        self.ventilation_flow_m3_h = _non_negative_float(
            self.ventilation_flow_m3_h,
            "ventilation_flow_m3_h",
            self.zone_id,
        )

    def ventilation_flow_m3_s(self) -> float:
        return self.ventilation_flow_m3_h / 3600.0

    def is_active(self) -> bool:
        return self.ventilation_flow_m3_h > 0.0

    def copy(self, **updates: Any) -> "MechanicalVentilationInput":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "ventilation_flow_m3_h": self.ventilation_flow_m3_h,
            "ventilation_flow_m3_s": self.ventilation_flow_m3_s(),
            "is_active": self.is_active(),
            "source": self.source,
        }
    
@dataclass
class BuildingAirflowControlInputs:
    """
    Clean physical control inputs for airflow/CO2.

    This is the only object airflow.py should receive from the agent/control side.

    Agent state / actions / controls are converted outside this module.
    """

    occupancy_by_zone: Dict[str, ZoneOccupancyInput] = None
    window_openings: Dict[str, WindowOpeningInput] = None
    door_openings: Dict[str, DoorOpeningInput] = None
    mechanical_ventilation_by_zone: Dict[str, MechanicalVentilationInput] = None
    source: str = "external_bridge"

    def __post_init__(self) -> None:
        if self.occupancy_by_zone is None:
            self.occupancy_by_zone = {}

        if self.window_openings is None:
            self.window_openings = {}

        if self.door_openings is None:
            self.door_openings = {}
        if self.mechanical_ventilation_by_zone is None:
            self.mechanical_ventilation_by_zone = {}
        self.occupancy_by_zone = self._validate_occupancy_inputs(
            self.occupancy_by_zone
        )

        self.window_openings = self._validate_window_inputs(
            self.window_openings
        )

        self.door_openings = self._validate_door_inputs(
            self.door_openings
        )
        self.mechanical_ventilation_by_zone = (
            self._validate_mechanical_ventilation_inputs(
                self.mechanical_ventilation_by_zone
            )
        )
        
    def _validate_mechanical_ventilation_inputs(
        self,
        inputs: Dict[str, MechanicalVentilationInput],
    ) -> Dict[str, MechanicalVentilationInput]:
        cleaned = {}

        for zone_id, item in inputs.items():
            if not isinstance(item, MechanicalVentilationInput):
                raise TypeError(
                    "mechanical_ventilation_by_zone must contain "
                    "MechanicalVentilationInput objects."
                )

            if zone_id != item.zone_id:
                raise ValueError(
                    "mechanical_ventilation_by_zone key "
                    + zone_id
                    + " does not match item.zone_id "
                    + item.zone_id
                )

            cleaned[zone_id] = item

        return cleaned
    
    def get_mechanical_ventilation_for_zone(
        self,
        zone_id: str,
    ) -> MechanicalVentilationInput:
        if zone_id not in self.mechanical_ventilation_by_zone:
            return MechanicalVentilationInput(
                zone_id=zone_id,
                ventilation_flow_m3_h=0.0,
                source="default_off",
            )

        return self.mechanical_ventilation_by_zone[zone_id]
    
    def _validate_occupancy_inputs(
        self,
        inputs: Dict[str, ZoneOccupancyInput],
    ) -> Dict[str, ZoneOccupancyInput]:
        cleaned = {}

        for zone_id, item in inputs.items():
            if not isinstance(item, ZoneOccupancyInput):
                raise TypeError(
                    "occupancy_by_zone must contain ZoneOccupancyInput objects."
                )

            if zone_id != item.zone_id:
                raise ValueError(
                    "occupancy_by_zone key "
                    + zone_id
                    + " does not match item.zone_id "
                    + item.zone_id
                )

            cleaned[zone_id] = item

        return cleaned

    def _validate_window_inputs(
        self,
        inputs: Dict[str, WindowOpeningInput],
    ) -> Dict[str, WindowOpeningInput]:
        cleaned = {}

        for boundary_connection_id, item in inputs.items():
            if not isinstance(item, WindowOpeningInput):
                raise TypeError(
                    "window_openings must contain WindowOpeningInput objects."
                )

            if boundary_connection_id != item.boundary_connection_id:
                raise ValueError(
                    "window_openings key "
                    + boundary_connection_id
                    + " does not match item.boundary_connection_id "
                    + item.boundary_connection_id
                )

            cleaned[boundary_connection_id] = item

        return cleaned

    def _validate_door_inputs(
        self,
        inputs: Dict[str, DoorOpeningInput],
    ) -> Dict[str, DoorOpeningInput]:
        cleaned = {}

        for zone_connection_id, item in inputs.items():
            if not isinstance(item, DoorOpeningInput):
                raise TypeError(
                    "door_openings must contain DoorOpeningInput objects."
                )

            if zone_connection_id != item.zone_connection_id:
                raise ValueError(
                    "door_openings key "
                    + zone_connection_id
                    + " does not match item.zone_connection_id "
                    + item.zone_connection_id
                )

            cleaned[zone_connection_id] = item

        return cleaned

    def get_occupancy_for_zone(
        self,
        zone_id: str,
    ) -> ZoneOccupancyInput:
        if zone_id not in self.occupancy_by_zone:
            return ZoneOccupancyInput(
                zone_id=zone_id,
                number_of_people=0.0,
                source="default_empty",
            )

        return self.occupancy_by_zone[zone_id]

    def get_window_opening(
        self,
        boundary_connection_id: str,
        zone_id: str,
    ) -> WindowOpeningInput:
        if boundary_connection_id not in self.window_openings:
            return WindowOpeningInput(
                boundary_connection_id=boundary_connection_id,
                zone_id=zone_id,
                opening_fraction=0.0,
                source="default_closed",
            )

        return self.window_openings[boundary_connection_id]

    def get_door_opening(
        self,
        zone_connection_id: str,
        zone_a_id: str,
        zone_b_id: str,
    ) -> DoorOpeningInput:
        if zone_connection_id not in self.door_openings:
            return DoorOpeningInput(
                zone_connection_id=zone_connection_id,
                zone_a_id=zone_a_id,
                zone_b_id=zone_b_id,
                opening_fraction=0.0,
                source="default_closed",
            )

        return self.door_openings[zone_connection_id]

    def occupied_zone_ids(self) -> List[str]:
        return [
            zone_id
            for zone_id, item in self.occupancy_by_zone.items()
            if item.number_of_people > 0.0
        ]

    def open_window_ids(self) -> List[str]:
        return [
            boundary_connection_id
            for boundary_connection_id, item in self.window_openings.items()
            if item.is_open()
        ]

    def open_door_ids(self) -> List[str]:
        return [
            zone_connection_id
            for zone_connection_id, item in self.door_openings.items()
            if item.is_open()
        ]

    def copy(self, **updates: Any) -> "BuildingAirflowControlInputs":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "occupancy_by_zone": {
                zone_id: item.to_dict()
                for zone_id, item in self.occupancy_by_zone.items()
            },
            "window_openings": {
                boundary_connection_id: item.to_dict()
                for boundary_connection_id, item in self.window_openings.items()
            },
            "door_openings": {
                zone_connection_id: item.to_dict()
                for zone_connection_id, item in self.door_openings.items()
            },
            "mechanical_ventilation_by_zone": {
                zone_id: item.to_dict()
                for zone_id, item in self.mechanical_ventilation_by_zone.items()
            },
            "occupied_zone_ids": self.occupied_zone_ids(),
            "open_window_ids": self.open_window_ids(),
            "open_door_ids": self.open_door_ids(),
            "source": self.source,
        }
    
@dataclass
class WindowOutdoorAirflowRecord:
    """
    Simplified wind-driven outdoor airflow through one window.

    Phase 5.5 formula:

        effective_opening_area = max_opening_area * opening_fraction

        flow_m3_s =
            discharge_coefficient
            * effective_opening_area
            * wind_speed_m_s
            * wind_alignment_factor

    No pressure-network model yet.
    """

    boundary_connection_id: str
    zone_id: str

    orientation_deg: float
    wind_direction_deg: float
    wind_speed_m_s: float

    max_opening_area_m2: float
    opening_fraction: float
    effective_opening_area_m2: float

    discharge_coefficient: float
    wind_alignment_factor: float

    airflow_m3_s: float
    airflow_m3_h: float

    source: str = "BoundaryConnection + WeatherState + WindowOpeningInput"

    def __post_init__(self) -> None:
        if not self.boundary_connection_id:
            raise ValueError(
                "WindowOutdoorAirflowRecord.boundary_connection_id cannot be empty."
            )

        if not self.zone_id:
            raise ValueError("WindowOutdoorAirflowRecord.zone_id cannot be empty.")

        self.orientation_deg = _normalize_degrees(self.orientation_deg)
        self.wind_direction_deg = _normalize_degrees(self.wind_direction_deg)

        self.wind_speed_m_s = _non_negative_float(
            self.wind_speed_m_s,
            "wind_speed_m_s",
            self.boundary_connection_id,
        )

        self.max_opening_area_m2 = _non_negative_float(
            self.max_opening_area_m2,
            "max_opening_area_m2",
            self.boundary_connection_id,
        )

        self.opening_fraction = _clamp_unit_interval(
            self.opening_fraction
        )

        self.effective_opening_area_m2 = _non_negative_float(
            self.effective_opening_area_m2,
            "effective_opening_area_m2",
            self.boundary_connection_id,
        )

        self.discharge_coefficient = _clamp_unit_interval(
            self.discharge_coefficient
        )

        self.wind_alignment_factor = _clamp_unit_interval(
            self.wind_alignment_factor
        )

        self.airflow_m3_s = _non_negative_float(
            self.airflow_m3_s,
            "airflow_m3_s",
            self.boundary_connection_id,
        )

        self.airflow_m3_h = _non_negative_float(
            self.airflow_m3_h,
            "airflow_m3_h",
            self.boundary_connection_id,
        )

    def copy(self, **updates: Any) -> "WindowOutdoorAirflowRecord":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_connection_id": self.boundary_connection_id,
            "zone_id": self.zone_id,
            "orientation_deg": self.orientation_deg,
            "wind_direction_deg": self.wind_direction_deg,
            "wind_speed_m_s": self.wind_speed_m_s,
            "max_opening_area_m2": self.max_opening_area_m2,
            "opening_fraction": self.opening_fraction,
            "effective_opening_area_m2": self.effective_opening_area_m2,
            "discharge_coefficient": self.discharge_coefficient,
            "wind_alignment_factor": self.wind_alignment_factor,
            "airflow_m3_s": self.airflow_m3_s,
            "airflow_m3_h": self.airflow_m3_h,
            "source": self.source,
        }
    
@dataclass
class BuildingWindowOutdoorAirflowResult:
    """
    Outdoor window airflow records for one timestep.
    """

    records: List[WindowOutdoorAirflowRecord] = None

    def __post_init__(self) -> None:
        if self.records is None:
            self.records = []

        cleaned = []

        for record in self.records:
            if not isinstance(record, WindowOutdoorAirflowRecord):
                raise TypeError(
                    "BuildingWindowOutdoorAirflowResult.records must contain "
                    "WindowOutdoorAirflowRecord objects."
                )

            cleaned.append(record)

        self.records = cleaned

    def airflow_by_zone_m3_h(self) -> Dict[str, float]:
        out = {}

        for record in self.records:
            out[record.zone_id] = (
                out.get(record.zone_id, 0.0)
                + record.airflow_m3_h
            )

        return out

    def airflow_by_zone_m3_s(self) -> Dict[str, float]:
        out = {}

        for record in self.records:
            out[record.zone_id] = (
                out.get(record.zone_id, 0.0)
                + record.airflow_m3_s
            )

        return out

    def total_airflow_m3_h(self) -> float:
        return sum(record.airflow_m3_h for record in self.records)

    def total_airflow_m3_s(self) -> float:
        return sum(record.airflow_m3_s for record in self.records)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "airflow_by_zone_m3_h": self.airflow_by_zone_m3_h(),
            "airflow_by_zone_m3_s": self.airflow_by_zone_m3_s(),
            "total_airflow_m3_h": self.total_airflow_m3_h(),
            "total_airflow_m3_s": self.total_airflow_m3_s(),
            "records": [
                record.to_dict()
                for record in self.records
            ],
        }
    
@dataclass
class ZoneOutdoorAirflowRecord:
    """
    Outdoor airflow exchange for one zone.

    Phase 5.6 simplification:
    - default infiltration is treated as outdoor air exchange
    - mechanical ventilation is treated as outdoor air exchange
    - window airflow is treated as outdoor air exchange
    - no detailed supply/exhaust balancing yet

    For now:
        outdoor_supply_m3_h  = total outdoor exchange
        outdoor_exhaust_m3_h = total outdoor exchange
        net_outdoor_exchange_m3_h = supply - exhaust = 0

    This is a mixing approximation for CO2 transport.
    """

    zone_id: str

    infiltration_flow_m3_h: float = 0.0
    mechanical_ventilation_flow_m3_h: float = 0.0
    window_airflow_m3_h: float = 0.0

    outdoor_supply_m3_h: float = 0.0
    outdoor_exhaust_m3_h: float = 0.0
    net_outdoor_exchange_m3_h: float = 0.0

    mixing_exchange_m3_h: float = 0.0

    source: str = OUTDOOR_AIRFLOW_MIXING_MODE

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneOutdoorAirflowRecord.zone_id cannot be empty.")

        self.infiltration_flow_m3_h = _non_negative_float(
            self.infiltration_flow_m3_h,
            "infiltration_flow_m3_h",
            self.zone_id,
        )

        self.mechanical_ventilation_flow_m3_h = _non_negative_float(
            self.mechanical_ventilation_flow_m3_h,
            "mechanical_ventilation_flow_m3_h",
            self.zone_id,
        )

        self.window_airflow_m3_h = _non_negative_float(
            self.window_airflow_m3_h,
            "window_airflow_m3_h",
            self.zone_id,
        )

        if self.mixing_exchange_m3_h <= 0.0:
            self.mixing_exchange_m3_h = (
                self.infiltration_flow_m3_h
                + self.mechanical_ventilation_flow_m3_h
                + self.window_airflow_m3_h
            )

        self.mixing_exchange_m3_h = _non_negative_float(
            self.mixing_exchange_m3_h,
            "mixing_exchange_m3_h",
            self.zone_id,
        )

        if self.outdoor_supply_m3_h <= 0.0:
            self.outdoor_supply_m3_h = self.mixing_exchange_m3_h

        if self.outdoor_exhaust_m3_h <= 0.0:
            self.outdoor_exhaust_m3_h = self.mixing_exchange_m3_h

        self.outdoor_supply_m3_h = _non_negative_float(
            self.outdoor_supply_m3_h,
            "outdoor_supply_m3_h",
            self.zone_id,
        )

        self.outdoor_exhaust_m3_h = _non_negative_float(
            self.outdoor_exhaust_m3_h,
            "outdoor_exhaust_m3_h",
            self.zone_id,
        )

        self.net_outdoor_exchange_m3_h = (
            self.outdoor_supply_m3_h
            - self.outdoor_exhaust_m3_h
        )

    def mixing_exchange_m3_s(self) -> float:
        return self.mixing_exchange_m3_h / 3600.0

    def outdoor_supply_m3_s(self) -> float:
        return self.outdoor_supply_m3_h / 3600.0

    def outdoor_exhaust_m3_s(self) -> float:
        return self.outdoor_exhaust_m3_h / 3600.0

    def active_sources(self) -> List[str]:
        sources = []

        if self.infiltration_flow_m3_h > 0.0:
            sources.append(OUTDOOR_AIRFLOW_SOURCE_INFILTRATION)

        if self.mechanical_ventilation_flow_m3_h > 0.0:
            sources.append(OUTDOOR_AIRFLOW_SOURCE_MECHANICAL)

        if self.window_airflow_m3_h > 0.0:
            sources.append(OUTDOOR_AIRFLOW_SOURCE_WINDOW)

        return sources

    def copy(self, **updates: Any) -> "ZoneOutdoorAirflowRecord":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "infiltration_flow_m3_h": self.infiltration_flow_m3_h,
            "mechanical_ventilation_flow_m3_h": self.mechanical_ventilation_flow_m3_h,
            "window_airflow_m3_h": self.window_airflow_m3_h,
            "outdoor_supply_m3_h": self.outdoor_supply_m3_h,
            "outdoor_exhaust_m3_h": self.outdoor_exhaust_m3_h,
            "net_outdoor_exchange_m3_h": self.net_outdoor_exchange_m3_h,
            "mixing_exchange_m3_h": self.mixing_exchange_m3_h,
            "mixing_exchange_m3_s": self.mixing_exchange_m3_s(),
            "active_sources": self.active_sources(),
            "source": self.source,
        }


@dataclass
class BuildingOutdoorAirflowResult:
    """
    Outdoor airflow exchange for all zones.
    """

    zone_records: Dict[str, ZoneOutdoorAirflowRecord] = None

    def __post_init__(self) -> None:
        if self.zone_records is None:
            self.zone_records = {}

        cleaned = {}

        for zone_id, record in self.zone_records.items():
            if not isinstance(record, ZoneOutdoorAirflowRecord):
                raise TypeError(
                    "BuildingOutdoorAirflowResult.zone_records must contain "
                    "ZoneOutdoorAirflowRecord objects."
                )

            if zone_id != record.zone_id:
                raise ValueError(
                    "BuildingOutdoorAirflowResult key "
                    + zone_id
                    + " does not match record.zone_id "
                    + record.zone_id
                )

            cleaned[zone_id] = record

        self.zone_records = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_records.keys())

    def get_zone_record(self, zone_id: str) -> ZoneOutdoorAirflowRecord:
        if zone_id not in self.zone_records:
            return ZoneOutdoorAirflowRecord(zone_id=zone_id)

        return self.zone_records[zone_id]

    def mixing_exchange_by_zone_m3_h(self) -> Dict[str, float]:
        return {
            zone_id: record.mixing_exchange_m3_h
            for zone_id, record in self.zone_records.items()
        }

    def mixing_exchange_by_zone_m3_s(self) -> Dict[str, float]:
        return {
            zone_id: record.mixing_exchange_m3_s()
            for zone_id, record in self.zone_records.items()
        }

    def outdoor_supply_by_zone_m3_h(self) -> Dict[str, float]:
        return {
            zone_id: record.outdoor_supply_m3_h
            for zone_id, record in self.zone_records.items()
        }

    def outdoor_exhaust_by_zone_m3_h(self) -> Dict[str, float]:
        return {
            zone_id: record.outdoor_exhaust_m3_h
            for zone_id, record in self.zone_records.items()
        }

    def net_outdoor_exchange_by_zone_m3_h(self) -> Dict[str, float]:
        return {
            zone_id: record.net_outdoor_exchange_m3_h
            for zone_id, record in self.zone_records.items()
        }

    def total_mixing_exchange_m3_h(self) -> float:
        return sum(
            record.mixing_exchange_m3_h
            for record in self.zone_records.values()
        )

    def copy(self, **updates: Any) -> "BuildingOutdoorAirflowResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mixing_exchange_by_zone_m3_h": self.mixing_exchange_by_zone_m3_h(),
            "mixing_exchange_by_zone_m3_s": self.mixing_exchange_by_zone_m3_s(),
            "outdoor_supply_by_zone_m3_h": self.outdoor_supply_by_zone_m3_h(),
            "outdoor_exhaust_by_zone_m3_h": self.outdoor_exhaust_by_zone_m3_h(),
            "net_outdoor_exchange_by_zone_m3_h": self.net_outdoor_exchange_by_zone_m3_h(),
            "total_mixing_exchange_m3_h": self.total_mixing_exchange_m3_h(),
            "zone_records": {
                zone_id: record.to_dict()
                for zone_id, record in self.zone_records.items()
            },
        }
    
@dataclass
class InterzoneAirflowLink:
    """
    Symmetric interzone airflow/mixing link.

    This is not a pressure-network result.

    Phase 5.7 approximation:

        flow_ab_m3_h = base_airflow_m3_h + opening_fraction * max_flow_m3_h

    The same mixing flow is applied both ways for CO2 transport:

        A loses to B and B gains from A
        B loses to A and A gains from B

    This conserves air approximately for the simplified model.
    """

    link_id: str
    zone_connection_id: str

    zone_a_id: str
    zone_b_id: str

    connection_type: str = "generic_interzone"

    base_airflow_m3_h: float = DEFAULT_INTERZONE_BASE_AIRFLOW_M3_H

    max_opening_area_m2: float = DEFAULT_INTERZONE_MAX_OPENING_AREA_M2
    discharge_coefficient: float = DEFAULT_INTERZONE_DISCHARGE_COEFFICIENT
    opening_fraction: float = DEFAULT_DOOR_OPENING_FRACTION

    assumed_mixing_air_speed_m_s: float = DEFAULT_INTERZONE_MIXING_AIR_SPEED_M_S

    max_flow_m3_h: float = 0.0
    mixing_flow_m3_h: float = 0.0

    source: str = INTERZONE_AIRFLOW_MIXING_MODE

    def __post_init__(self) -> None:
        if not self.link_id:
            raise ValueError("InterzoneAirflowLink.link_id cannot be empty.")

        if not self.zone_connection_id:
            raise ValueError(
                "InterzoneAirflowLink.zone_connection_id cannot be empty."
            )

        if not self.zone_a_id:
            raise ValueError("InterzoneAirflowLink.zone_a_id cannot be empty.")

        if not self.zone_b_id:
            raise ValueError("InterzoneAirflowLink.zone_b_id cannot be empty.")

        if self.zone_a_id == self.zone_b_id:
            raise ValueError(
                "InterzoneAirflowLink cannot connect a zone to itself: "
                + self.zone_a_id
            )

        self.base_airflow_m3_h = _non_negative_float(
            self.base_airflow_m3_h,
            "base_airflow_m3_h",
            self.link_id,
        )

        self.max_opening_area_m2 = _non_negative_float(
            self.max_opening_area_m2,
            "max_opening_area_m2",
            self.link_id,
        )

        self.discharge_coefficient = _clamp_unit_interval(
            self.discharge_coefficient
        )

        self.opening_fraction = _clamp_unit_interval(
            self.opening_fraction
        )

        self.assumed_mixing_air_speed_m_s = _non_negative_float(
            self.assumed_mixing_air_speed_m_s,
            "assumed_mixing_air_speed_m_s",
            self.link_id,
        )

        if self.max_flow_m3_h <= 0.0:
            self.max_flow_m3_h = (
                self.discharge_coefficient
                * self.max_opening_area_m2
                * self.assumed_mixing_air_speed_m_s
                * 3600.0
            )

        self.max_flow_m3_h = _non_negative_float(
            self.max_flow_m3_h,
            "max_flow_m3_h",
            self.link_id,
        )

        if self.mixing_flow_m3_h <= 0.0:
            self.mixing_flow_m3_h = (
                self.base_airflow_m3_h
                + self.opening_fraction * self.max_flow_m3_h
            )

        self.mixing_flow_m3_h = _non_negative_float(
            self.mixing_flow_m3_h,
            "mixing_flow_m3_h",
            self.link_id,
        )

    def mixing_flow_m3_s(self) -> float:
        return self.mixing_flow_m3_h / 3600.0

    def active_sources(self) -> List[str]:
        sources = []

        if self.base_airflow_m3_h > 0.0:
            sources.append(INTERZONE_AIRFLOW_SOURCE_BASE)

        if self.opening_fraction > 0.0 and self.max_flow_m3_h > 0.0:
            sources.append(INTERZONE_AIRFLOW_SOURCE_DOOR_OPENING)

        return sources

    def other_zone_id(self, zone_id: str) -> str:
        if zone_id == self.zone_a_id:
            return self.zone_b_id

        if zone_id == self.zone_b_id:
            return self.zone_a_id

        raise ValueError(
            "Zone "
            + zone_id
            + " is not connected by interzone link "
            + self.link_id
        )

    def copy(self, **updates: Any) -> "InterzoneAirflowLink":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "link_id": self.link_id,
            "zone_connection_id": self.zone_connection_id,
            "zone_a_id": self.zone_a_id,
            "zone_b_id": self.zone_b_id,
            "connection_type": self.connection_type,
            "base_airflow_m3_h": self.base_airflow_m3_h,
            "max_opening_area_m2": self.max_opening_area_m2,
            "discharge_coefficient": self.discharge_coefficient,
            "opening_fraction": self.opening_fraction,
            "assumed_mixing_air_speed_m_s": self.assumed_mixing_air_speed_m_s,
            "max_flow_m3_h": self.max_flow_m3_h,
            "mixing_flow_m3_h": self.mixing_flow_m3_h,
            "mixing_flow_m3_s": self.mixing_flow_m3_s(),
            "active_sources": self.active_sources(),
            "source": self.source,
        }


@dataclass
class InterzoneAirflowRecord:
    """
    Symmetric airflow record for one interzone connection.

    For the simplified model:
        flow_a_to_b_m3_h = flow_b_to_a_m3_h = mixing_flow_m3_h

    Net flow is zero, but mixing exchange is non-zero.
    """

    link_id: str
    zone_connection_id: str

    zone_a_id: str
    zone_b_id: str

    flow_a_to_b_m3_h: float
    flow_b_to_a_m3_h: float

    net_a_to_b_m3_h: float = 0.0

    source: str = INTERZONE_AIRFLOW_MIXING_MODE

    def __post_init__(self) -> None:
        if not self.link_id:
            raise ValueError("InterzoneAirflowRecord.link_id cannot be empty.")

        if not self.zone_connection_id:
            raise ValueError(
                "InterzoneAirflowRecord.zone_connection_id cannot be empty."
            )

        if not self.zone_a_id:
            raise ValueError("InterzoneAirflowRecord.zone_a_id cannot be empty.")

        if not self.zone_b_id:
            raise ValueError("InterzoneAirflowRecord.zone_b_id cannot be empty.")

        self.flow_a_to_b_m3_h = _non_negative_float(
            self.flow_a_to_b_m3_h,
            "flow_a_to_b_m3_h",
            self.link_id,
        )

        self.flow_b_to_a_m3_h = _non_negative_float(
            self.flow_b_to_a_m3_h,
            "flow_b_to_a_m3_h",
            self.link_id,
        )

        self.net_a_to_b_m3_h = (
            self.flow_a_to_b_m3_h
            - self.flow_b_to_a_m3_h
        )

    def flow_a_to_b_m3_s(self) -> float:
        return self.flow_a_to_b_m3_h / 3600.0

    def flow_b_to_a_m3_s(self) -> float:
        return self.flow_b_to_a_m3_h / 3600.0

    def is_symmetric(self, tolerance_m3_h: float = 1e-9) -> bool:
        return abs(self.net_a_to_b_m3_h) <= float(tolerance_m3_h)

    def to_dict(self) -> Dict[str, Any]:
        mixing_exchange_m3_h = max(
            self.flow_a_to_b_m3_h,
            self.flow_b_to_a_m3_h,
        )

        return {
            "link_id": self.link_id,

            # Original internal name.
            "zone_connection_id": self.zone_connection_id,

            # Stable output alias.
            "connection_id": self.zone_connection_id,

            "zone_a_id": self.zone_a_id,
            "zone_b_id": self.zone_b_id,

            # Original internal names.
            "flow_a_to_b_m3_h": self.flow_a_to_b_m3_h,
            "flow_b_to_a_m3_h": self.flow_b_to_a_m3_h,
            "flow_a_to_b_m3_s": self.flow_a_to_b_m3_s(),
            "flow_b_to_a_m3_s": self.flow_b_to_a_m3_s(),

            # Stable output aliases.
            "airflow_a_to_b_m3_h": self.flow_a_to_b_m3_h,
            "airflow_b_to_a_m3_h": self.flow_b_to_a_m3_h,
            "airflow_a_to_b_m3_s": self.flow_a_to_b_m3_s(),
            "airflow_b_to_a_m3_s": self.flow_b_to_a_m3_s(),

            # Symmetric mixing output.
            "mixing_exchange_m3_h": mixing_exchange_m3_h,
            "mixing_exchange_m3_s": mixing_exchange_m3_h / 3600.0,

            # Original net-flow diagnostic.
            "net_a_to_b_m3_h": self.net_a_to_b_m3_h,
            "is_symmetric": self.is_symmetric(),
            "source": self.source,
        }
    
@dataclass
class BuildingInterzoneAirflowResult:
    """
    Interzone airflow/mixing links and records for one timestep.
    """

    links: Dict[str, InterzoneAirflowLink] = None
    records: Dict[str, InterzoneAirflowRecord] = None

    def __post_init__(self) -> None:
        if self.links is None:
            self.links = {}

        if self.records is None:
            self.records = {}

        cleaned_links = {}

        for link_id, link in self.links.items():
            if not isinstance(link, InterzoneAirflowLink):
                raise TypeError(
                    "BuildingInterzoneAirflowResult.links must contain "
                    "InterzoneAirflowLink objects."
                )

            if link_id != link.link_id:
                raise ValueError(
                    "Interzone link key "
                    + link_id
                    + " does not match link.link_id "
                    + link.link_id
                )

            cleaned_links[link_id] = link

        cleaned_records = {}

        for record_id, record in self.records.items():
            if not isinstance(record, InterzoneAirflowRecord):
                raise TypeError(
                    "BuildingInterzoneAirflowResult.records must contain "
                    "InterzoneAirflowRecord objects."
                )

            if record_id != record.link_id:
                raise ValueError(
                    "Interzone record key "
                    + record_id
                    + " does not match record.link_id "
                    + record.link_id
                )

            cleaned_records[record_id] = record

        self.links = cleaned_links
        self.records = cleaned_records

    def link_ids(self) -> List[str]:
        return list(self.links.keys())

    def links_for_zone(self, zone_id: str) -> List[InterzoneAirflowLink]:
        return [
            link
            for link in self.links.values()
            if link.zone_a_id == zone_id or link.zone_b_id == zone_id
        ]

    def mixing_flow_for_zone_m3_h(self, zone_id: str) -> float:
        return sum(
            link.mixing_flow_m3_h
            for link in self.links_for_zone(zone_id)
        )

    def mixing_flow_for_zone_m3_s(self, zone_id: str) -> float:
        return self.mixing_flow_for_zone_m3_h(zone_id) / 3600.0

    def mixing_flow_by_zone_m3_h(self) -> Dict[str, float]:
        out = {}

        for link in self.links.values():
            out[link.zone_a_id] = (
                out.get(link.zone_a_id, 0.0)
                + link.mixing_flow_m3_h
            )

            out[link.zone_b_id] = (
                out.get(link.zone_b_id, 0.0)
                + link.mixing_flow_m3_h
            )

        return out

    def mixing_flow_by_zone_m3_s(self) -> Dict[str, float]:
        return {
            zone_id: flow_m3_h / 3600.0
            for zone_id, flow_m3_h in self.mixing_flow_by_zone_m3_h().items()
        }

    def all_records_symmetric(self, tolerance_m3_h: float = 1e-9) -> bool:
        for record in self.records.values():
            if not record.is_symmetric(tolerance_m3_h=tolerance_m3_h):
                return False

        return True

    def total_pair_mixing_flow_m3_h(self) -> float:
        return sum(
            link.mixing_flow_m3_h
            for link in self.links.values()
        )

    def copy(self, **updates: Any) -> "BuildingInterzoneAirflowResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mixing_flow_by_zone_m3_h": self.mixing_flow_by_zone_m3_h(),
            "mixing_flow_by_zone_m3_s": self.mixing_flow_by_zone_m3_s(),
            "total_pair_mixing_flow_m3_h": self.total_pair_mixing_flow_m3_h(),
            "all_records_symmetric": self.all_records_symmetric(),
            "links": {
                link_id: link.to_dict()
                for link_id, link in self.links.items()
            },
            "records": {
                record_id: record.to_dict()
                for record_id, record in self.records.items()
            },
        }
    
@dataclass
class BuildingAirflowNetwork:
    """
    Assembled airflow network for one timestep.

    Includes:
    - outdoor airflow by zone:
        infiltration
        mechanical ventilation
        window airflow

    - interzone airflow links:
        door/opening/base mixing

    This is only a flow-assembly layer.
    It does not solve a pressure network.
    """

    outdoor_airflows_by_zone: Dict[str, ZoneOutdoorAirflowRecord] = None
    interzone_airflow_links: Dict[str, InterzoneAirflowLink] = None
    interzone_airflow_records: Dict[str, InterzoneAirflowRecord] = None

    mode: str = AIRFLOW_NETWORK_MODE
    pressure_solution: str = AIRFLOW_NETWORK_PRESSURE_SOLVE

    def __post_init__(self) -> None:
        if self.outdoor_airflows_by_zone is None:
            self.outdoor_airflows_by_zone = {}

        if self.interzone_airflow_links is None:
            self.interzone_airflow_links = {}

        if self.interzone_airflow_records is None:
            self.interzone_airflow_records = {}

        self.outdoor_airflows_by_zone = self._validate_outdoor_records(
            self.outdoor_airflows_by_zone
        )

        self.interzone_airflow_links = self._validate_interzone_links(
            self.interzone_airflow_links
        )

        self.interzone_airflow_records = self._validate_interzone_records(
            self.interzone_airflow_records
        )

    def _validate_outdoor_records(
        self,
        records: Dict[str, ZoneOutdoorAirflowRecord],
    ) -> Dict[str, ZoneOutdoorAirflowRecord]:
        cleaned = {}

        for zone_id, record in records.items():
            if not isinstance(record, ZoneOutdoorAirflowRecord):
                raise TypeError(
                    "outdoor_airflows_by_zone must contain ZoneOutdoorAirflowRecord objects."
                )

            if zone_id != record.zone_id:
                raise ValueError(
                    "outdoor_airflows_by_zone key "
                    + zone_id
                    + " does not match record.zone_id "
                    + record.zone_id
                )

            cleaned[zone_id] = record

        return cleaned

    def _validate_interzone_links(
        self,
        links: Dict[str, InterzoneAirflowLink],
    ) -> Dict[str, InterzoneAirflowLink]:
        cleaned = {}

        for link_id, link in links.items():
            if not isinstance(link, InterzoneAirflowLink):
                raise TypeError(
                    "interzone_airflow_links must contain InterzoneAirflowLink objects."
                )

            if link_id != link.link_id:
                raise ValueError(
                    "interzone_airflow_links key "
                    + link_id
                    + " does not match link.link_id "
                    + link.link_id
                )

            cleaned[link_id] = link

        return cleaned

    def _validate_interzone_records(
        self,
        records: Dict[str, InterzoneAirflowRecord],
    ) -> Dict[str, InterzoneAirflowRecord]:
        cleaned = {}

        for record_id, record in records.items():
            if not isinstance(record, InterzoneAirflowRecord):
                raise TypeError(
                    "interzone_airflow_records must contain InterzoneAirflowRecord objects."
                )

            if record_id != record.link_id:
                raise ValueError(
                    "interzone_airflow_records key "
                    + record_id
                    + " does not match record.link_id "
                    + record.link_id
                )

            cleaned[record_id] = record

        return cleaned

    def zone_ids(self) -> List[str]:
        zone_ids = set(self.outdoor_airflows_by_zone.keys())

        for link in self.interzone_airflow_links.values():
            zone_ids.add(link.zone_a_id)
            zone_ids.add(link.zone_b_id)

        return sorted(list(zone_ids))

    def get_outdoor_airflow_for_zone(
        self,
        zone_id: str,
    ) -> ZoneOutdoorAirflowRecord:
        if zone_id not in self.outdoor_airflows_by_zone:
            return ZoneOutdoorAirflowRecord(zone_id=zone_id)

        return self.outdoor_airflows_by_zone[zone_id]

    def interzone_links_for_zone(
        self,
        zone_id: str,
    ) -> List[InterzoneAirflowLink]:
        return [
            link
            for link in self.interzone_airflow_links.values()
            if link.zone_a_id == zone_id or link.zone_b_id == zone_id
        ]

    def outdoor_mixing_by_zone_m3_h(self) -> Dict[str, float]:
        return {
            zone_id: record.mixing_exchange_m3_h
            for zone_id, record in self.outdoor_airflows_by_zone.items()
        }

    def outdoor_mixing_by_zone_m3_s(self) -> Dict[str, float]:
        return {
            zone_id: record.mixing_exchange_m3_s()
            for zone_id, record in self.outdoor_airflows_by_zone.items()
        }

    def interzone_mixing_by_zone_m3_h(self) -> Dict[str, float]:
        out = {}

        for link in self.interzone_airflow_links.values():
            out[link.zone_a_id] = (
                out.get(link.zone_a_id, 0.0)
                + link.mixing_flow_m3_h
            )

            out[link.zone_b_id] = (
                out.get(link.zone_b_id, 0.0)
                + link.mixing_flow_m3_h
            )

        return out

    def interzone_mixing_by_zone_m3_s(self) -> Dict[str, float]:
        return {
            zone_id: flow_m3_h / 3600.0
            for zone_id, flow_m3_h in self.interzone_mixing_by_zone_m3_h().items()
        }

    def total_air_exchange_by_zone_m3_h(self) -> Dict[str, float]:
        """
        Total exchange touching each zone.

        This is useful for CO2 timestep calculations.
        """

        out = {}

        outdoor = self.outdoor_mixing_by_zone_m3_h()
        interzone = self.interzone_mixing_by_zone_m3_h()

        for zone_id in self.zone_ids():
            out[zone_id] = (
                outdoor.get(zone_id, 0.0)
                + interzone.get(zone_id, 0.0)
            )

        return out

    def approximate_net_air_balance_by_zone_m3_h(self) -> Dict[str, float]:
        """
        Approximate net mass balance.

        For this simplified phase:
        - outdoor supply and exhaust are balanced
        - interzone flows are symmetric

        Therefore expected net balance is approximately zero.
        """

        out = {}

        for zone_id in self.zone_ids():
            outdoor_record = self.get_outdoor_airflow_for_zone(zone_id)
            out[zone_id] = outdoor_record.net_outdoor_exchange_m3_h

        return out

    def all_interzone_records_symmetric(
        self,
        tolerance_m3_h: float = 1e-9,
    ) -> bool:
        for record in self.interzone_airflow_records.values():
            if not record.is_symmetric(tolerance_m3_h=tolerance_m3_h):
                return False

        return True

    def copy(self, **updates: Any) -> "BuildingAirflowNetwork":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "pressure_solution": self.pressure_solution,
            "zone_ids": self.zone_ids(),
            "outdoor_mixing_by_zone_m3_h": self.outdoor_mixing_by_zone_m3_h(),
            "outdoor_mixing_by_zone_m3_s": self.outdoor_mixing_by_zone_m3_s(),
            "interzone_mixing_by_zone_m3_h": self.interzone_mixing_by_zone_m3_h(),
            "interzone_mixing_by_zone_m3_s": self.interzone_mixing_by_zone_m3_s(),
            "total_air_exchange_by_zone_m3_h": self.total_air_exchange_by_zone_m3_h(),
            "approximate_net_air_balance_by_zone_m3_h": self.approximate_net_air_balance_by_zone_m3_h(),
            "all_interzone_records_symmetric": self.all_interzone_records_symmetric(),
            "outdoor_airflows_by_zone": {
                zone_id: record.to_dict()
                for zone_id, record in self.outdoor_airflows_by_zone.items()
            },
            "interzone_airflow_links": {
                link_id: link.to_dict()
                for link_id, link in self.interzone_airflow_links.items()
            },
            "interzone_airflow_records": {
                record_id: record.to_dict()
                for record_id, record in self.interzone_airflow_records.items()
            },
        }
    
@dataclass
class ZoneCO2GenerationRecord:
    """
    CO2 generation from people in one zone.

    Phase 5.9:
    - based only on number of people
    - per-person generation rate comes from ZoneAirflowParameters
    - no activity/metabolic model yet

    Later:
    agent activity/metabolic state can be converted into an adjusted
    co2_generation_per_person_m3_h before entering this module.
    """

    zone_id: str

    number_of_people: float = 0.0
    co2_generation_per_person_m3_h: float = DEFAULT_CO2_GENERATION_PER_PERSON_M3_H

    co2_generation_m3_h: float = 0.0

    source: str = "ZoneOccupancyInput + ZoneAirflowParameters"

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneCO2GenerationRecord.zone_id cannot be empty.")

        self.number_of_people = _non_negative_float(
            self.number_of_people,
            "number_of_people",
            self.zone_id,
        )

        self.co2_generation_per_person_m3_h = _non_negative_float(
            self.co2_generation_per_person_m3_h,
            "co2_generation_per_person_m3_h",
            self.zone_id,
        )

        if self.co2_generation_m3_h <= 0.0:
            self.co2_generation_m3_h = (
                self.number_of_people
                * self.co2_generation_per_person_m3_h
            )

        self.co2_generation_m3_h = _non_negative_float(
            self.co2_generation_m3_h,
            "co2_generation_m3_h",
            self.zone_id,
        )

    def co2_generation_m3_s(self) -> float:
        return self.co2_generation_m3_h / 3600.0

    def copy(self, **updates: Any) -> "ZoneCO2GenerationRecord":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "number_of_people": self.number_of_people,
            "co2_generation_per_person_m3_h": self.co2_generation_per_person_m3_h,
            "co2_generation_m3_h": self.co2_generation_m3_h,
            "co2_generation_m3_s": self.co2_generation_m3_s(),
            "source": self.source,
        }



@dataclass
class BuildingCO2GenerationResult:
    """
    CO2 generation records for all zones.
    """

    zone_records: Dict[str, ZoneCO2GenerationRecord] = None

    def __post_init__(self) -> None:
        if self.zone_records is None:
            self.zone_records = {}

        cleaned = {}

        for zone_id, record in self.zone_records.items():
            if not isinstance(record, ZoneCO2GenerationRecord):
                raise TypeError(
                    "BuildingCO2GenerationResult.zone_records must contain "
                    "ZoneCO2GenerationRecord objects."
                )

            if zone_id != record.zone_id:
                raise ValueError(
                    "BuildingCO2GenerationResult key "
                    + zone_id
                    + " does not match record.zone_id "
                    + record.zone_id
                )

            cleaned[zone_id] = record

        self.zone_records = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_records.keys())

    def get_zone_record(self, zone_id: str) -> ZoneCO2GenerationRecord:
        if zone_id not in self.zone_records:
            return ZoneCO2GenerationRecord(
                zone_id=zone_id,
                number_of_people=0.0,
                co2_generation_per_person_m3_h=DEFAULT_CO2_GENERATION_PER_PERSON_M3_H,
                source="default_empty_zone",
            )

        return self.zone_records[zone_id]

    def co2_generation_m3_h_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: record.co2_generation_m3_h
            for zone_id, record in self.zone_records.items()
        }

    def co2_generation_m3_s_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: record.co2_generation_m3_s()
            for zone_id, record in self.zone_records.items()
        }

    def total_co2_generation_m3_h(self) -> float:
        return sum(
            record.co2_generation_m3_h
            for record in self.zone_records.values()
        )

    def total_co2_generation_m3_s(self) -> float:
        return self.total_co2_generation_m3_h() / 3600.0

    def copy(self, **updates: Any) -> "BuildingCO2GenerationResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "co2_generation_m3_h_by_zone": self.co2_generation_m3_h_by_zone(),
            "co2_generation_m3_s_by_zone": self.co2_generation_m3_s_by_zone(),
            "total_co2_generation_m3_h": self.total_co2_generation_m3_h(),
            "total_co2_generation_m3_s": self.total_co2_generation_m3_s(),
            "zone_records": {
                zone_id: record.to_dict()
                for zone_id, record in self.zone_records.items()
            },
        }

@dataclass
class CO2ConcentrationTarget:
    """
    A concentration source connected to a zone by airflow.

    Used in the stable CO2 update:

        C_next =
            (V/dt * C_old + sum(q_i * C_i) + G * 1e6)
            /
            (V/dt + sum(q_i))

    Units:
        C: ppm
        V: m3
        q: m3/s
        G: m3/s of pure CO2
    """

    target_id: str
    target_type: str
    co2_ppm: float
    airflow_m3_s: float

    def __post_init__(self) -> None:
        if not self.target_id:
            raise ValueError("CO2ConcentrationTarget.target_id cannot be empty.")

        if not self.target_type:
            raise ValueError("CO2ConcentrationTarget.target_type cannot be empty.")

        self.co2_ppm = _bounded_co2_ppm(self.co2_ppm)

        self.airflow_m3_s = _non_negative_float(
            self.airflow_m3_s,
            "airflow_m3_s",
            self.target_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id": self.target_id,
            "target_type": self.target_type,
            "co2_ppm": self.co2_ppm,
            "airflow_m3_s": self.airflow_m3_s,
        }


@dataclass
class ZoneCO2UpdateResult:
    """
    CO2 timestep update result for one zone.
    """

    zone_id: str

    old_co2_ppm: float
    new_co2_ppm: float

    air_volume_m3: float
    co2_generation_m3_s: float

    targets: List[CO2ConcentrationTarget] = None

    dt_seconds: float = 0.0
    method: str = CO2_TIMESTEP_METHOD

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneCO2UpdateResult.zone_id cannot be empty.")

        self.old_co2_ppm = _bounded_co2_ppm(self.old_co2_ppm)
        self.new_co2_ppm = _bounded_co2_ppm(self.new_co2_ppm)

        self.air_volume_m3 = _positive_float(
            self.air_volume_m3,
            "air_volume_m3",
            self.zone_id,
        )

        self.co2_generation_m3_s = _non_negative_float(
            self.co2_generation_m3_s,
            "co2_generation_m3_s",
            self.zone_id,
        )

        if self.targets is None:
            self.targets = []

        cleaned = []

        for target in self.targets:
            if not isinstance(target, CO2ConcentrationTarget):
                raise TypeError(
                    "ZoneCO2UpdateResult.targets must contain CO2ConcentrationTarget objects."
                )

            cleaned.append(target)

        self.targets = cleaned

        self.dt_seconds = _positive_float(
            self.dt_seconds,
            "dt_seconds",
            self.zone_id,
        )

    def to_zone_air_state(self) -> ZoneAirState:
        return ZoneAirState(
            zone_id=self.zone_id,
            co2_ppm=self.new_co2_ppm,
            air_volume_m3=self.air_volume_m3,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "old_co2_ppm": self.old_co2_ppm,
            "new_co2_ppm": self.new_co2_ppm,
            "air_volume_m3": self.air_volume_m3,
            "co2_generation_m3_s": self.co2_generation_m3_s,
            "dt_seconds": self.dt_seconds,
            "method": self.method,
            "targets": [
                target.to_dict()
                for target in self.targets
            ],
        }


@dataclass
class BuildingCO2StepResult:
    """
    CO2 timestep update result for all zones.
    """

    updated_air_state: BuildingAirState
    zone_results: Dict[str, ZoneCO2UpdateResult] = None

    dt_minutes: float = 0.0
    method: str = CO2_TIMESTEP_METHOD

    def __post_init__(self) -> None:
        if not isinstance(self.updated_air_state, BuildingAirState):
            raise TypeError("updated_air_state must be BuildingAirState.")

        if self.zone_results is None:
            self.zone_results = {}

        cleaned = {}

        for zone_id, result in self.zone_results.items():
            if not isinstance(result, ZoneCO2UpdateResult):
                raise TypeError(
                    "BuildingCO2StepResult.zone_results must contain ZoneCO2UpdateResult objects."
                )

            if zone_id != result.zone_id:
                raise ValueError(
                    "BuildingCO2StepResult key "
                    + zone_id
                    + " does not match result.zone_id "
                    + result.zone_id
                )

            cleaned[zone_id] = result

        self.zone_results = cleaned

    def co2_by_zone_ppm(self) -> Dict[str, float]:
        return {
            zone_id: state.co2_ppm
            for zone_id, state in self.updated_air_state.zone_states.items()
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "updated_air_state": self.updated_air_state.to_dict(),
            "co2_by_zone_ppm": self.co2_by_zone_ppm(),
            "dt_minutes": self.dt_minutes,
            "method": self.method,
            "zone_results": {
                zone_id: result.to_dict()
                for zone_id, result in self.zone_results.items()
            },
        }
    
@dataclass
class ZoneAirCO2DebugRecord:
    """
    Debug record for one zone after one airflow/CO2 timestep.
    """

    zone_id: str

    old_co2_ppm: float
    new_co2_ppm: float

    air_volume_m3: float

    outdoor_exchange_m3_h: float = 0.0
    interzone_exchange_m3_h: float = 0.0
    total_exchange_m3_h: float = 0.0

    number_of_people: float = 0.0
    co2_generation_m3_h: float = 0.0

    dt_minutes: float = DEFAULT_AIR_CO2_DT_MINUTES
    method: str = CO2_TIMESTEP_METHOD

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneAirCO2DebugRecord.zone_id cannot be empty.")

        self.old_co2_ppm = _bounded_co2_ppm(self.old_co2_ppm)
        self.new_co2_ppm = _bounded_co2_ppm(self.new_co2_ppm)

        self.air_volume_m3 = _positive_float(
            self.air_volume_m3,
            "air_volume_m3",
            self.zone_id,
        )

        self.outdoor_exchange_m3_h = _non_negative_float(
            self.outdoor_exchange_m3_h,
            "outdoor_exchange_m3_h",
            self.zone_id,
        )

        self.interzone_exchange_m3_h = _non_negative_float(
            self.interzone_exchange_m3_h,
            "interzone_exchange_m3_h",
            self.zone_id,
        )

        self.total_exchange_m3_h = _non_negative_float(
            self.total_exchange_m3_h,
            "total_exchange_m3_h",
            self.zone_id,
        )

        self.number_of_people = _non_negative_float(
            self.number_of_people,
            "number_of_people",
            self.zone_id,
        )

        self.co2_generation_m3_h = _non_negative_float(
            self.co2_generation_m3_h,
            "co2_generation_m3_h",
            self.zone_id,
        )

        self.dt_minutes = _positive_float(
            self.dt_minutes,
            "dt_minutes",
            self.zone_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "old_co2_ppm": self.old_co2_ppm,
            "new_co2_ppm": self.new_co2_ppm,
            "air_volume_m3": self.air_volume_m3,
            "outdoor_exchange_m3_h": self.outdoor_exchange_m3_h,
            "interzone_exchange_m3_h": self.interzone_exchange_m3_h,
            "total_exchange_m3_h": self.total_exchange_m3_h,
            "number_of_people": self.number_of_people,
            "co2_generation_m3_h": self.co2_generation_m3_h,
            "dt_minutes": self.dt_minutes,
            "method": self.method,
        }


@dataclass
class AirCO2StepResult:
    """
    Public result returned by AirCO2Model.step(...).
    """

    updated_air_state: BuildingAirState

    airflow_network: BuildingAirflowNetwork
    co2_generation_result: BuildingCO2GenerationResult
    co2_step_result: BuildingCO2StepResult

    debug_records: List[ZoneAirCO2DebugRecord] = None

    dt_minutes: float = DEFAULT_AIR_CO2_DT_MINUTES
    interface_mode: str = AIR_CO2_MODEL_INTERFACE_MODE

    def __post_init__(self) -> None:
        if not isinstance(self.updated_air_state, BuildingAirState):
            raise TypeError("updated_air_state must be BuildingAirState.")

        if not isinstance(self.airflow_network, BuildingAirflowNetwork):
            raise TypeError("airflow_network must be BuildingAirflowNetwork.")

        if not isinstance(self.co2_generation_result, BuildingCO2GenerationResult):
            raise TypeError(
                "co2_generation_result must be BuildingCO2GenerationResult."
            )

        if not isinstance(self.co2_step_result, BuildingCO2StepResult):
            raise TypeError("co2_step_result must be BuildingCO2StepResult.")

        if self.debug_records is None:
            self.debug_records = []

        cleaned = []

        for record in self.debug_records:
            if not isinstance(record, ZoneAirCO2DebugRecord):
                raise TypeError(
                    "debug_records must contain ZoneAirCO2DebugRecord objects."
                )

            cleaned.append(record)

        self.debug_records = cleaned

        self.dt_minutes = _positive_float(
            self.dt_minutes,
            "dt_minutes",
            "AirCO2StepResult",
        )

    def co2_by_zone_ppm(self) -> Dict[str, float]:
        return {
            zone_id: state.co2_ppm
            for zone_id, state in self.updated_air_state.zone_states.items()
        }

    def outdoor_airflow_records(self) -> Dict[str, ZoneOutdoorAirflowRecord]:
        return self.airflow_network.outdoor_airflows_by_zone

    def interzone_airflow_records(self) -> Dict[str, InterzoneAirflowRecord]:
        return self.airflow_network.interzone_airflow_records

    def co2_generation_records(self) -> Dict[str, ZoneCO2GenerationRecord]:
        return self.co2_generation_result.zone_records

    def debug_records_as_dicts(self) -> List[Dict[str, Any]]:
        return [
            record.to_dict()
            for record in self.debug_records
        ]

    def to_debug_dataframe(self) -> Any:
        """
        Optional convenience method.

        Keeps pandas optional. The model itself does not require pandas.
        """

        import pandas as pd

        return pd.DataFrame(self.debug_records_as_dicts())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "updated_air_state": self.updated_air_state.to_dict(),
            "co2_by_zone_ppm": self.co2_by_zone_ppm(),
            "airflow_network": self.airflow_network.to_dict(),
            "co2_generation_result": self.co2_generation_result.to_dict(),
            "co2_step_result": self.co2_step_result.to_dict(),
            "debug_records": self.debug_records_as_dicts(),
            "dt_minutes": self.dt_minutes,
            "interface_mode": self.interface_mode,
        }
    
@dataclass
class AirCO2Model:
    """
    Runner-facing airflow/CO2 model interface.

    Agent-friendly design:
    - no imports from agents/actions/controllers
    - agent outputs must be converted into BuildingAirflowControlInputs
      before calling this model
    """

    architecture: AirCO2ArchitectureDecision = None
    default_dt_minutes: float = DEFAULT_AIR_CO2_DT_MINUTES

    def __post_init__(self) -> None:
        if self.architecture is None:
            self.architecture = AirCO2ArchitectureDecision()

        if not isinstance(self.architecture, AirCO2ArchitectureDecision):
            raise TypeError(
                "AirCO2Model.architecture must be AirCO2ArchitectureDecision."
            )

        self.default_dt_minutes = _positive_float(
            self.default_dt_minutes,
            "default_dt_minutes",
            "AirCO2Model",
        )

    def make_initial_state(
        self,
        building_model: Any,
    ) -> BuildingAirState:
        return make_initial_building_air_state(building_model)

    def step(
        self,
        building_model: Any,
        physics_graph: Any,
        air_state: BuildingAirState,
        weather_state: Any,
        airflow_control_inputs: Optional[BuildingAirflowControlInputs] = None,
        dt_minutes: Optional[float] = None,
        window_boundary_result: Any = None,
    ) -> AirCO2StepResult:
        """
        Advance airflow/CO2 model by one timestep.

        Expected runner call:

            AirCO2Model.step(
                building_model,
                physics_graph,
                air_state,
                weather_state,
                airflow_control_inputs,
                dt_minutes
            )

        airflow_control_inputs:
            clean bridge object from agents/controls/actions.
        """

        if building_model is None:
            raise ValueError("building_model cannot be None.")

        if physics_graph is None:
            raise ValueError("physics_graph cannot be None.")

        if not isinstance(air_state, BuildingAirState):
            raise TypeError("air_state must be BuildingAirState.")

        if weather_state is None:
            raise ValueError("weather_state cannot be None.")

        if airflow_control_inputs is None:
            airflow_control_inputs = make_empty_airflow_control_inputs()

        if not isinstance(airflow_control_inputs, BuildingAirflowControlInputs):
            raise TypeError(
                "airflow_control_inputs must be BuildingAirflowControlInputs."
            )

        if dt_minutes is None:
            dt_minutes = self.default_dt_minutes

        dt_minutes = _positive_float(
            dt_minutes,
            "dt_minutes",
            "AirCO2Model.step",
        )

        building_airflow_parameters = make_building_airflow_parameters(
            building_model
        )

        airflow_network = calculate_building_airflow_network(
            building_model=building_model,
            physics_graph=physics_graph,
            weather_state=weather_state,
            airflow_control_inputs=airflow_control_inputs,
            window_boundary_result=window_boundary_result,
        )

        co2_generation_result = calculate_building_co2_generation(
            building_airflow_parameters=building_airflow_parameters,
            airflow_control_inputs=airflow_control_inputs,
        )

        co2_step_result = step_building_co2_state(
            air_state=air_state,
            airflow_network=airflow_network,
            co2_generation_result=co2_generation_result,
            weather_state=weather_state,
            dt_minutes=dt_minutes,
        )

        debug_records = self._make_debug_records(
            old_air_state=air_state,
            airflow_network=airflow_network,
            co2_generation_result=co2_generation_result,
            co2_step_result=co2_step_result,
            dt_minutes=dt_minutes,
        )

        return AirCO2StepResult(
            updated_air_state=co2_step_result.updated_air_state,
            airflow_network=airflow_network,
            co2_generation_result=co2_generation_result,
            co2_step_result=co2_step_result,
            debug_records=debug_records,
            dt_minutes=dt_minutes,
            interface_mode=AIR_CO2_MODEL_INTERFACE_MODE,
        )

    def _make_debug_records(
        self,
        old_air_state: BuildingAirState,
        airflow_network: BuildingAirflowNetwork,
        co2_generation_result: BuildingCO2GenerationResult,
        co2_step_result: BuildingCO2StepResult,
        dt_minutes: float,
    ) -> List[ZoneAirCO2DebugRecord]:
        outdoor_by_zone = airflow_network.outdoor_mixing_by_zone_m3_h()
        interzone_by_zone = airflow_network.interzone_mixing_by_zone_m3_h()
        total_by_zone = airflow_network.total_air_exchange_by_zone_m3_h()

        records = []

        for zone_id in co2_step_result.updated_air_state.zone_ids():
            old_state = old_air_state.get_zone_state(zone_id)
            new_state = co2_step_result.updated_air_state.get_zone_state(zone_id)
            generation_record = co2_generation_result.get_zone_record(zone_id)

            records.append(
                ZoneAirCO2DebugRecord(
                    zone_id=zone_id,
                    old_co2_ppm=old_state.co2_ppm,
                    new_co2_ppm=new_state.co2_ppm,
                    air_volume_m3=new_state.air_volume_m3,
                    outdoor_exchange_m3_h=outdoor_by_zone.get(zone_id, 0.0),
                    interzone_exchange_m3_h=interzone_by_zone.get(zone_id, 0.0),
                    total_exchange_m3_h=total_by_zone.get(zone_id, 0.0),
                    number_of_people=generation_record.number_of_people,
                    co2_generation_m3_h=generation_record.co2_generation_m3_h,
                    dt_minutes=dt_minutes,
                    method=CO2_TIMESTEP_METHOD,
                )
            )

        return records
    
    
DEFAULT_AIR_CO2_ARCHITECTURE = AirCO2ArchitectureDecision()

def make_default_air_co2_model() -> AirCO2Model:
    return AirCO2Model()

def semi_implicit_co2_update_ppm(
    air_volume_m3: float,
    old_co2_ppm: float,
    targets: List[CO2ConcentrationTarget],
    co2_generation_m3_s: float,
    dt_seconds: float,
) -> float:
    """
    Stable CO2 mass-balance update.

    Formula:

        C_next =
            (V/dt * C_old + sum(q_i * C_i) + G * 1e6)
            /
            (V/dt + sum(q_i))

    Units:
        V  = m3
        dt = s
        C  = ppm
        q  = m3/s
        G  = m3/s of pure CO2
    """

    air_volume_m3 = _positive_float(
        air_volume_m3,
        "air_volume_m3",
        "co2_update",
    )

    old_co2_ppm = _bounded_co2_ppm(old_co2_ppm)

    co2_generation_m3_s = _non_negative_float(
        co2_generation_m3_s,
        "co2_generation_m3_s",
        "co2_update",
    )

    dt_seconds = _positive_float(
        dt_seconds,
        "dt_seconds",
        "co2_update",
    )

    if targets is None:
        targets = []

    v_over_dt = air_volume_m3 / dt_seconds

    numerator = (
        v_over_dt * old_co2_ppm
        + co2_generation_m3_s * CO2_GENERATION_PPM_FACTOR
    )

    denominator = v_over_dt

    for target in targets:
        if not isinstance(target, CO2ConcentrationTarget):
            raise TypeError(
                "targets must contain CO2ConcentrationTarget objects."
            )

        numerator += target.airflow_m3_s * target.co2_ppm
        denominator += target.airflow_m3_s

    if denominator <= 0.0:
        raise ValueError("CO2 update denominator became non-positive.")

    return _bounded_co2_ppm(numerator / denominator)

def update_zone_co2_state(
    zone_air_state: ZoneAirState,
    co2_generation_record: ZoneCO2GenerationRecord,
    outdoor_co2_ppm: float,
    outdoor_exchange_m3_s: float = 0.0,
    interzone_targets: Optional[List[CO2ConcentrationTarget]] = None,
    dt_minutes: float = 15.0,
) -> ZoneCO2UpdateResult:
    """
    Update CO2 state for one zone.

    Includes:
    - storage
    - people generation
    - outdoor air exchange
    - interzone exchange targets
    """

    if not isinstance(zone_air_state, ZoneAirState):
        raise TypeError("zone_air_state must be ZoneAirState.")

    if not isinstance(co2_generation_record, ZoneCO2GenerationRecord):
        raise TypeError("co2_generation_record must be ZoneCO2GenerationRecord.")

    if zone_air_state.zone_id != co2_generation_record.zone_id:
        raise ValueError(
            "zone_air_state.zone_id does not match co2_generation_record.zone_id."
        )

    outdoor_exchange_m3_s = _non_negative_float(
        outdoor_exchange_m3_s,
        "outdoor_exchange_m3_s",
        zone_air_state.zone_id,
    )

    dt_seconds = _positive_float(
        float(dt_minutes) * 60.0,
        "dt_seconds",
        zone_air_state.zone_id,
    )

    if interzone_targets is None:
        interzone_targets = []

    targets = []

    if outdoor_exchange_m3_s > 0.0:
        targets.append(
            CO2ConcentrationTarget(
                target_id="outdoor",
                target_type="outdoor_air",
                co2_ppm=outdoor_co2_ppm,
                airflow_m3_s=outdoor_exchange_m3_s,
            )
        )

    for target in interzone_targets:
        targets.append(target)

    new_co2_ppm = semi_implicit_co2_update_ppm(
        air_volume_m3=zone_air_state.air_volume_m3,
        old_co2_ppm=zone_air_state.co2_ppm,
        targets=targets,
        co2_generation_m3_s=co2_generation_record.co2_generation_m3_s(),
        dt_seconds=dt_seconds,
    )

    return ZoneCO2UpdateResult(
        zone_id=zone_air_state.zone_id,
        old_co2_ppm=zone_air_state.co2_ppm,
        new_co2_ppm=new_co2_ppm,
        air_volume_m3=zone_air_state.air_volume_m3,
        co2_generation_m3_s=co2_generation_record.co2_generation_m3_s(),
        targets=targets,
        dt_seconds=dt_seconds,
        method=CO2_TIMESTEP_METHOD,
    )

def step_building_co2_state(
    air_state: BuildingAirState,
    airflow_network: BuildingAirflowNetwork,
    co2_generation_result: BuildingCO2GenerationResult,
    weather_state: Any,
    dt_minutes: float = 15.0,
) -> BuildingCO2StepResult:
    """
    Update CO2 concentration for all zones.

    Uses:
    - BuildingAirState
    - BuildingAirflowNetwork
    - BuildingCO2GenerationResult
    - WeatherState.outdoor_co2_ppm

    Uses old-state concentrations for interzone mixing.
    """

    if not isinstance(air_state, BuildingAirState):
        raise TypeError("air_state must be BuildingAirState.")

    if not isinstance(airflow_network, BuildingAirflowNetwork):
        raise TypeError("airflow_network must be BuildingAirflowNetwork.")

    if not isinstance(co2_generation_result, BuildingCO2GenerationResult):
        raise TypeError(
            "co2_generation_result must be BuildingCO2GenerationResult."
        )

    if weather_state is None:
        raise ValueError("weather_state cannot be None.")

    outdoor_co2_ppm = _bounded_co2_ppm(
        _get_attr_or_default(
            weather_state,
            "outdoor_co2_ppm",
            DEFAULT_OUTDOOR_CO2_PPM,
        )
    )

    updated_zone_states = {}
    zone_results = {}

    outdoor_exchange_by_zone_m3_s = (
        airflow_network.outdoor_mixing_by_zone_m3_s()
    )

    for zone_id in air_state.zone_ids():
        zone_air_state = air_state.get_zone_state(zone_id)

        co2_generation_record = co2_generation_result.get_zone_record(zone_id)

        interzone_targets = _make_interzone_co2_targets_for_zone(
            zone_id=zone_id,
            air_state=air_state,
            airflow_network=airflow_network,
        )

        result = update_zone_co2_state(
            zone_air_state=zone_air_state,
            co2_generation_record=co2_generation_record,
            outdoor_co2_ppm=outdoor_co2_ppm,
            outdoor_exchange_m3_s=outdoor_exchange_by_zone_m3_s.get(zone_id, 0.0),
            interzone_targets=interzone_targets,
            dt_minutes=dt_minutes,
        )

        updated_zone_states[zone_id] = result.to_zone_air_state()
        zone_results[zone_id] = result

    updated_air_state = BuildingAirState(
        zone_states=updated_zone_states,
    )

    return BuildingCO2StepResult(
        updated_air_state=updated_air_state,
        zone_results=zone_results,
        dt_minutes=dt_minutes,
        method=CO2_TIMESTEP_METHOD,
    )

def calculate_and_step_building_co2_state(
    building_model: Any,
    physics_graph: Any,
    air_state: BuildingAirState,
    weather_state: Any,
    airflow_control_inputs: Optional[BuildingAirflowControlInputs] = None,
    window_boundary_result: Any = None,
    dt_minutes: float = 15.0,
) -> BuildingCO2StepResult:
    """
    Convenience function for Phase 5.10.

    Calculates:
    - airflow network
    - CO2 generation
    - next CO2 state
    """

    if airflow_control_inputs is None:
        airflow_control_inputs = make_empty_airflow_control_inputs()

    building_airflow_parameters = make_building_airflow_parameters(
        building_model
    )

    airflow_network = calculate_building_airflow_network(
        building_model=building_model,
        physics_graph=physics_graph,
        weather_state=weather_state,
        airflow_control_inputs=airflow_control_inputs,
        window_boundary_result=window_boundary_result,
    )

    co2_generation_result = calculate_building_co2_generation(
        building_airflow_parameters=building_airflow_parameters,
        airflow_control_inputs=airflow_control_inputs,
    )

    return step_building_co2_state(
        air_state=air_state,
        airflow_network=airflow_network,
        co2_generation_result=co2_generation_result,
        weather_state=weather_state,
        dt_minutes=dt_minutes,
    )

def calculate_zone_co2_generation_record(
    zone_parameters: ZoneAirflowParameters,
    occupancy_input: ZoneOccupancyInput,
) -> ZoneCO2GenerationRecord:
    """
    Calculate CO2 generation for one zone.
    """

    if not isinstance(zone_parameters, ZoneAirflowParameters):
        raise TypeError("zone_parameters must be ZoneAirflowParameters.")

    if not isinstance(occupancy_input, ZoneOccupancyInput):
        raise TypeError("occupancy_input must be ZoneOccupancyInput.")

    if zone_parameters.zone_id != occupancy_input.zone_id:
        raise ValueError(
            "zone_parameters.zone_id does not match occupancy_input.zone_id."
        )

    return ZoneCO2GenerationRecord(
        zone_id=zone_parameters.zone_id,
        number_of_people=occupancy_input.number_of_people,
        co2_generation_per_person_m3_h=zone_parameters.co2_generation_per_person_m3_h,
        source="ZoneOccupancyInput + ZoneAirflowParameters",
    )


def calculate_building_co2_generation(
    building_airflow_parameters: BuildingAirflowParameters,
    airflow_control_inputs: BuildingAirflowControlInputs,
) -> BuildingCO2GenerationResult:
    """
    Calculate CO2 generation for all zones.

    Inputs:
    - ZoneOccupancyInput.number_of_people
    - ZoneAirflowParameters.co2_generation_per_person_m3_h
    """

    if not isinstance(building_airflow_parameters, BuildingAirflowParameters):
        raise TypeError(
            "building_airflow_parameters must be BuildingAirflowParameters."
        )

    if not isinstance(airflow_control_inputs, BuildingAirflowControlInputs):
        raise TypeError(
            "airflow_control_inputs must be BuildingAirflowControlInputs."
        )

    zone_records = {}

    for zone_id, parameters in building_airflow_parameters.zone_parameters.items():
        occupancy_input = airflow_control_inputs.get_occupancy_for_zone(
            zone_id
        )

        zone_records[zone_id] = calculate_zone_co2_generation_record(
            zone_parameters=parameters,
            occupancy_input=occupancy_input,
        )

    return BuildingCO2GenerationResult(
        zone_records=zone_records,
    )


def calculate_building_co2_generation_from_model(
    building_model: Any,
    airflow_control_inputs: BuildingAirflowControlInputs,
) -> BuildingCO2GenerationResult:
    """
    Convenience function.

    Builds airflow parameters from BuildingModel, then calculates CO2 generation.
    """

    building_airflow_parameters = make_building_airflow_parameters(
        building_model
    )

    return calculate_building_co2_generation(
        building_airflow_parameters=building_airflow_parameters,
        airflow_control_inputs=airflow_control_inputs,
    )


def co2_generation_m3_h_by_zone(
    co2_generation_result: BuildingCO2GenerationResult,
) -> Dict[str, float]:
    """
    Return CO2 generation by zone in m3/h.
    """

    if not isinstance(co2_generation_result, BuildingCO2GenerationResult):
        raise TypeError(
            "co2_generation_result must be BuildingCO2GenerationResult."
        )

    return co2_generation_result.co2_generation_m3_h_by_zone()


def co2_generation_m3_s_by_zone(
    co2_generation_result: BuildingCO2GenerationResult,
) -> Dict[str, float]:
    """
    Return CO2 generation by zone in m3/s.
    """

    if not isinstance(co2_generation_result, BuildingCO2GenerationResult):
        raise TypeError(
            "co2_generation_result must be BuildingCO2GenerationResult."
        )

    return co2_generation_result.co2_generation_m3_s_by_zone()

def assemble_building_airflow_network(
    outdoor_airflow_result: BuildingOutdoorAirflowResult,
    interzone_airflow_result: BuildingInterzoneAirflowResult,
) -> BuildingAirflowNetwork:
    """
    Assemble outdoor and interzone airflow into one network.

    This does not solve pressure.
    It only combines already calculated flow records.
    """

    if not isinstance(outdoor_airflow_result, BuildingOutdoorAirflowResult):
        raise TypeError(
            "outdoor_airflow_result must be BuildingOutdoorAirflowResult."
        )

    if not isinstance(interzone_airflow_result, BuildingInterzoneAirflowResult):
        raise TypeError(
            "interzone_airflow_result must be BuildingInterzoneAirflowResult."
        )

    return BuildingAirflowNetwork(
        outdoor_airflows_by_zone=outdoor_airflow_result.zone_records,
        interzone_airflow_links=interzone_airflow_result.links,
        interzone_airflow_records=interzone_airflow_result.records,
        mode=AIRFLOW_NETWORK_MODE,
        pressure_solution=AIRFLOW_NETWORK_PRESSURE_SOLVE,
    )

def calculate_building_mechanical_only_airflow_network(
    building_model: Any,
    airflow_control_inputs: Optional[BuildingAirflowControlInputs] = None,
) -> BuildingAirflowNetwork:
    """
    Build an outdoor-only airflow network without a physics graph.

    Used when mechanical ventilation exists but no window/interzone graph
    is available yet.

    Includes:
    - ZoneModel default infiltration
    - commanded mechanical ventilation
    - no window airflow
    - no interzone airflow
    """

    if building_model is None:
        raise ValueError("building_model cannot be None.")

    if airflow_control_inputs is None:
        airflow_control_inputs = make_empty_airflow_control_inputs()

    building_airflow_parameters = make_building_airflow_parameters(
        building_model
    )

    outdoor_airflow_result = make_building_outdoor_airflow_result(
        building_airflow_parameters=building_airflow_parameters,
        airflow_control_inputs=airflow_control_inputs,
    )

    return BuildingAirflowNetwork(
        outdoor_airflows_by_zone=outdoor_airflow_result.zone_records,
        interzone_airflow_links={},
        interzone_airflow_records={},
        mode=AIRFLOW_NETWORK_MODE,
        pressure_solution=AIRFLOW_NETWORK_PRESSURE_SOLVE,
    )

def calculate_building_airflow_network(
    building_model: Any,
    physics_graph: Any,
    weather_state: Any,
    airflow_control_inputs: Optional[BuildingAirflowControlInputs] = None,
    window_boundary_result: Any = None,
) -> BuildingAirflowNetwork:
    """
    Full Phase 5.8 airflow network calculation.

    Includes:
    - infiltration from ZoneModel
    - mechanical ventilation from ZoneModel
    - window airflow from WeatherState + BoundaryConnection + WindowOpeningInput
    - interzone/door mixing from ZoneConnection + DoorOpeningInput

    Still not a pressure-network solver.
    """

    if building_model is None:
        raise ValueError("building_model cannot be None.")

    if physics_graph is None:
        raise ValueError("physics_graph cannot be None.")

    if weather_state is None:
        raise ValueError("weather_state cannot be None.")

    if airflow_control_inputs is None:
        airflow_control_inputs = make_empty_airflow_control_inputs()

    if not isinstance(airflow_control_inputs, BuildingAirflowControlInputs):
        raise TypeError(
            "airflow_control_inputs must be BuildingAirflowControlInputs."
        )
    outdoor_airflow_result = calculate_building_outdoor_airflow_result(
        building_model=building_model,
        physics_graph=physics_graph,
        weather_state=weather_state,
        airflow_control_inputs=airflow_control_inputs,
        window_boundary_result=window_boundary_result,
    )

    interzone_airflow_result = calculate_building_interzone_airflows(
        physics_graph=physics_graph,
        airflow_control_inputs=airflow_control_inputs,
    )

    return assemble_building_airflow_network(
        outdoor_airflow_result=outdoor_airflow_result,
        interzone_airflow_result=interzone_airflow_result,
    )


def calculate_interzone_airflow_link(
    zone_connection: Any,
    door_opening_input: DoorOpeningInput,
) -> InterzoneAirflowLink:
    """
    Calculate simplified symmetric interzone airflow link.
    """

    if zone_connection is None:
        raise ValueError("zone_connection cannot be None.")

    if not isinstance(door_opening_input, DoorOpeningInput):
        raise TypeError("door_opening_input must be DoorOpeningInput.")

    zone_connection_id = _required_attr(
        zone_connection,
        "connection_id",
    )

    zone_a_id = _zone_connection_zone_a_id(zone_connection)
    zone_b_id = _zone_connection_zone_b_id(zone_connection)

    if door_opening_input.zone_connection_id != zone_connection_id:
        raise ValueError(
            "DoorOpeningInput zone_connection_id does not match ZoneConnection."
        )

    if door_opening_input.zone_a_id != zone_a_id:
        raise ValueError(
            "DoorOpeningInput zone_a_id does not match ZoneConnection."
        )

    if door_opening_input.zone_b_id != zone_b_id:
        raise ValueError(
            "DoorOpeningInput zone_b_id does not match ZoneConnection."
        )

    connection_type = _get_attr_or_default(
        zone_connection,
        "connection_type",
        "generic_interzone",
    )

    base_airflow_m3_h = _get_attr_or_default(
        zone_connection,
        "base_airflow_m3_h",
        DEFAULT_INTERZONE_BASE_AIRFLOW_M3_H,
    )

    max_opening_area_m2 = _get_attr_or_default(
        zone_connection,
        "max_opening_area_m2",
        DEFAULT_INTERZONE_MAX_OPENING_AREA_M2,
    )

    discharge_coefficient = _get_attr_or_default(
        zone_connection,
        "discharge_coefficient",
        DEFAULT_INTERZONE_DISCHARGE_COEFFICIENT,
    )

    return InterzoneAirflowLink(
        link_id=zone_connection_id,
        zone_connection_id=zone_connection_id,
        zone_a_id=zone_a_id,
        zone_b_id=zone_b_id,
        connection_type=connection_type,
        base_airflow_m3_h=base_airflow_m3_h,
        max_opening_area_m2=max_opening_area_m2,
        discharge_coefficient=discharge_coefficient,
        opening_fraction=door_opening_input.opening_fraction,
        assumed_mixing_air_speed_m_s=DEFAULT_INTERZONE_MIXING_AIR_SPEED_M_S,
        source=INTERZONE_AIRFLOW_MIXING_MODE,
    )


def make_interzone_airflow_record_from_link(
    link: InterzoneAirflowLink,
) -> InterzoneAirflowRecord:
    """
    Convert interzone link to symmetric airflow record.
    """

    if not isinstance(link, InterzoneAirflowLink):
        raise TypeError("link must be InterzoneAirflowLink.")

    return InterzoneAirflowRecord(
        link_id=link.link_id,
        zone_connection_id=link.zone_connection_id,
        zone_a_id=link.zone_a_id,
        zone_b_id=link.zone_b_id,
        flow_a_to_b_m3_h=link.mixing_flow_m3_h,
        flow_b_to_a_m3_h=link.mixing_flow_m3_h,
        source=INTERZONE_AIRFLOW_MIXING_MODE,
    )

def make_static_door_opening_input_from_zone_connection(
    zone_connection: Any,
) -> DoorOpeningInput:
    """
    Build default door airflow input from static graph state.

    Dynamic DoorOpeningInput still overrides this path.
    This is the Phase 12.2 bridge:

        ZoneConnection.open_fraction
            -> DoorOpeningInput.opening_fraction

    It keeps airflow.py agent-free and controller-free.
    """

    if zone_connection is None:
        raise ValueError("zone_connection cannot be None.")

    zone_connection_id = _required_attr(
        zone_connection,
        "connection_id",
    )

    zone_a_id = _zone_connection_zone_a_id(zone_connection)
    zone_b_id = _zone_connection_zone_b_id(zone_connection)

    is_openable = bool(
        _get_attr_or_default(
            zone_connection,
            "is_openable",
            False,
        )
    )

    if not is_openable:
        opening_fraction = 0.0
    else:
        opening_fraction = _get_attr_or_default(
            zone_connection,
            "open_fraction",
            DEFAULT_DOOR_OPENING_FRACTION,
        )

    return DoorOpeningInput(
        zone_connection_id=zone_connection_id,
        zone_a_id=zone_a_id,
        zone_b_id=zone_b_id,
        opening_fraction=opening_fraction,
        source=INTERZONE_AIRFLOW_SOURCE_STATIC_GRAPH_DOOR_STATE,
    )


def calculate_building_interzone_airflows(
    physics_graph: Any,
    airflow_control_inputs: BuildingAirflowControlInputs,
) -> BuildingInterzoneAirflowResult:
    """
    Calculate symmetric interzone airflow/mixing through all ZoneConnections.
    """

    if physics_graph is None:
        raise ValueError("physics_graph cannot be None.")

    if not isinstance(airflow_control_inputs, BuildingAirflowControlInputs):
        raise TypeError(
            "airflow_control_inputs must be BuildingAirflowControlInputs."
        )

    if not hasattr(physics_graph, "zone_connections"):
        raise TypeError(
            "physics_graph must provide zone_connections."
        )

    links = {}
    records = {}

    for connection_id, zone_connection in physics_graph.zone_connections.items():
        zone_a_id = _zone_connection_zone_a_id(zone_connection)
        zone_b_id = _zone_connection_zone_b_id(zone_connection)

        if connection_id in airflow_control_inputs.door_openings:
            door_opening = airflow_control_inputs.get_door_opening(
                zone_connection_id=connection_id,
                zone_a_id=zone_a_id,
                zone_b_id=zone_b_id,
            )
        else:
            door_opening = make_static_door_opening_input_from_zone_connection(
                zone_connection=zone_connection,
            )

        link = calculate_interzone_airflow_link(
            zone_connection=zone_connection,
            door_opening_input=door_opening,
        )

        record = make_interzone_airflow_record_from_link(link)

        links[link.link_id] = link
        records[record.link_id] = record

    return BuildingInterzoneAirflowResult(
        links=links,
        records=records,
    )

def make_zone_outdoor_airflow_record(
    zone_parameters: ZoneAirflowParameters,
    window_airflow_m3_h: float = 0.0,
    mechanical_ventilation_flow_m3_h: Optional[float] = None,
) -> ZoneOutdoorAirflowRecord:
    """
    Assemble outdoor airflow for one zone.

    Includes:
    - default infiltration
    - mechanical ventilation
    - window airflow
    """

    if not isinstance(zone_parameters, ZoneAirflowParameters):
        raise TypeError("zone_parameters must be ZoneAirflowParameters.")

    window_airflow_m3_h = _non_negative_float(
        window_airflow_m3_h,
        "window_airflow_m3_h",
        zone_parameters.zone_id,
    )
    if mechanical_ventilation_flow_m3_h is None:
        mechanical_ventilation_flow_m3_h = (
            zone_parameters.mechanical_ventilation_flow_m3_h
        )

    mechanical_ventilation_flow_m3_h = _non_negative_float(
        mechanical_ventilation_flow_m3_h,
        "mechanical_ventilation_flow_m3_h",
        zone_parameters.zone_id,
    )
    return ZoneOutdoorAirflowRecord(
        zone_id=zone_parameters.zone_id,
        infiltration_flow_m3_h=zone_parameters.default_infiltration_flow_m3_h,
        mechanical_ventilation_flow_m3_h=mechanical_ventilation_flow_m3_h,
        window_airflow_m3_h=window_airflow_m3_h,
        source=OUTDOOR_AIRFLOW_MIXING_MODE,
    )


def make_building_outdoor_airflow_result(
    building_airflow_parameters: BuildingAirflowParameters,
    window_airflow_result: Optional[BuildingWindowOutdoorAirflowResult] = None,
    window_boundary_result: Any = None,
    airflow_control_inputs: Optional[BuildingAirflowControlInputs] = None,
) -> BuildingOutdoorAirflowResult:
    """
    Assemble outdoor airflow records for all zones.

    Preferred Phase 8 source:
        BuildingWindowBoundaryResult

    Legacy fallback:
        BuildingWindowOutdoorAirflowResult
    """

    if not isinstance(building_airflow_parameters, BuildingAirflowParameters):
        raise TypeError(
            "building_airflow_parameters must be BuildingAirflowParameters."
        )

    window_airflow_by_zone = {}

    if window_boundary_result is not None:
        window_airflow_by_zone = window_boundary_outdoor_airflow_by_zone_m3_h(
            window_boundary_result
        )

    elif window_airflow_result is not None:
        if not isinstance(window_airflow_result, BuildingWindowOutdoorAirflowResult):
            raise TypeError(
                "window_airflow_result must be BuildingWindowOutdoorAirflowResult."
            )

        window_airflow_by_zone = window_airflow_result.airflow_by_zone_m3_h()

    zone_records = {}

    for zone_id, parameters in building_airflow_parameters.zone_parameters.items():
        mechanical_ventilation_flow_m3_h = None

        if airflow_control_inputs is not None:
            mechanical_ventilation_flow_m3_h = (
                airflow_control_inputs
                .get_mechanical_ventilation_for_zone(zone_id)
                .ventilation_flow_m3_h
            )

        zone_records[zone_id] = make_zone_outdoor_airflow_record(
            zone_parameters=parameters,
            window_airflow_m3_h=window_airflow_by_zone.get(zone_id, 0.0),
            mechanical_ventilation_flow_m3_h=mechanical_ventilation_flow_m3_h,
        )

    return BuildingOutdoorAirflowResult(
        zone_records=zone_records,
    )

def calculate_building_outdoor_airflow_result(
    building_model: Any,
    physics_graph: Any,
    weather_state: Any,
    airflow_control_inputs: BuildingAirflowControlInputs,
    window_boundary_result: Any = None,
) -> BuildingOutdoorAirflowResult:
    """
    Full outdoor airflow calculation.

    Phase 8 path:
        windows.py -> BuildingWindowBoundaryResult -> window airflow by zone

    Legacy direct window calculation remains available only through
    calculate_building_window_outdoor_airflows(...), but this function now
    prefers the shared window boundary model.
    """

    building_airflow_parameters = make_building_airflow_parameters(
        building_model
    )

    if window_boundary_result is None:
        window_boundary_result = calculate_window_boundary_result_for_airflow(
            building_model=building_model,
            physics_graph=physics_graph,
            weather_state=weather_state,
            airflow_control_inputs=airflow_control_inputs,
        )

    return make_building_outdoor_airflow_result(
        building_airflow_parameters=building_airflow_parameters,
        window_boundary_result=window_boundary_result,
        airflow_control_inputs=airflow_control_inputs,
    )

def calculate_window_outdoor_airflow_record(
    boundary_connection: Any,
    weather_state: Any,
    window_opening_input: WindowOpeningInput,
) -> WindowOutdoorAirflowRecord:
    """
    Calculate simplified outdoor airflow through one window.
    """

    if boundary_connection is None:
        raise ValueError("boundary_connection cannot be None.")

    if weather_state is None:
        raise ValueError("weather_state cannot be None.")

    if not isinstance(window_opening_input, WindowOpeningInput):
        raise TypeError("window_opening_input must be WindowOpeningInput.")

    boundary_connection_id = _required_attr(
        boundary_connection,
        "connection_id",
    )

    zone_id = _required_attr(
        boundary_connection,
        "zone_id",
    )

    if window_opening_input.boundary_connection_id != boundary_connection_id:
        raise ValueError(
            "WindowOpeningInput boundary id does not match BoundaryConnection."
        )

    if window_opening_input.zone_id != zone_id:
        raise ValueError(
            "WindowOpeningInput zone_id does not match BoundaryConnection.zone_id."
        )

    orientation_deg = _get_attr_or_default(
        boundary_connection,
        "orientation_deg",
        None,
    )

    wind_direction_deg = _get_attr_or_default(
        weather_state,
        "wind_direction_deg",
        0.0,
    )

    wind_speed_m_s = _get_attr_or_default(
        weather_state,
        "wind_speed_m_s",
        0.0,
    )

    max_opening_area_m2 = _first_existing_attr_or_default(
        boundary_connection,
        [
            "max_opening_area_m2",
            "area_m2",
        ],
        DEFAULT_WINDOW_MAX_OPENING_AREA_M2,
    )

    discharge_coefficient = _get_attr_or_default(
        boundary_connection,
        "discharge_coefficient",
        DEFAULT_WINDOW_DISCHARGE_COEFFICIENT,
    )

    opening_fraction = window_opening_input.opening_fraction

    effective_opening_area_m2 = (
        float(max_opening_area_m2)
        * float(opening_fraction)
    )

    wind_alignment_factor = window_wind_alignment_factor(
        wind_direction_deg=wind_direction_deg,
        window_orientation_deg=orientation_deg,
    )

    airflow_m3_s = (
        float(discharge_coefficient)
        * effective_opening_area_m2
        * float(wind_speed_m_s)
        * wind_alignment_factor
    )

    airflow_m3_h = airflow_m3_s * 3600.0

    if orientation_deg is None:
        orientation_deg = 0.0

    return WindowOutdoorAirflowRecord(
        boundary_connection_id=boundary_connection_id,
        zone_id=zone_id,
        orientation_deg=orientation_deg,
        wind_direction_deg=wind_direction_deg,
        wind_speed_m_s=wind_speed_m_s,
        max_opening_area_m2=max_opening_area_m2,
        opening_fraction=opening_fraction,
        effective_opening_area_m2=effective_opening_area_m2,
        discharge_coefficient=discharge_coefficient,
        wind_alignment_factor=wind_alignment_factor,
        airflow_m3_s=airflow_m3_s,
        airflow_m3_h=airflow_m3_h,
    )


def calculate_building_window_outdoor_airflows(
    physics_graph: Any,
    weather_state: Any,
    airflow_control_inputs: BuildingAirflowControlInputs,
) -> BuildingWindowOutdoorAirflowResult:
    """
    Calculate outdoor window airflow records for all window boundary connections.
    """

    if physics_graph is None:
        raise ValueError("physics_graph cannot be None.")

    if weather_state is None:
        raise ValueError("weather_state cannot be None.")

    if not isinstance(airflow_control_inputs, BuildingAirflowControlInputs):
        raise TypeError(
            "airflow_control_inputs must be BuildingAirflowControlInputs."
        )

    if not hasattr(physics_graph, "boundary_connections"):
        raise TypeError(
            "physics_graph must provide boundary_connections."
        )

    records = []

    for connection_id, boundary_connection in physics_graph.boundary_connections.items():
        if not _is_window_boundary_connection(boundary_connection):
            continue

        zone_id = _required_attr(boundary_connection, "zone_id")

        opening_input = airflow_control_inputs.get_window_opening(
            boundary_connection_id=connection_id,
            zone_id=zone_id,
        )

        record = calculate_window_outdoor_airflow_record(
            boundary_connection=boundary_connection,
            weather_state=weather_state,
            window_opening_input=opening_input,
        )

        records.append(record)

    return BuildingWindowOutdoorAirflowResult(
        records=records,
    )

def make_empty_airflow_control_inputs() -> BuildingAirflowControlInputs:
    return BuildingAirflowControlInputs(
        occupancy_by_zone={},
        window_openings={},
        door_openings={},
        mechanical_ventilation_by_zone={},
        source="empty",
    )

def is_building_window_boundary_result_like(
    window_boundary_result: Any,
) -> bool:
    """
    Duck-typed check.

    Avoids hard dependency/circular import problems.
    """

    if window_boundary_result is None:
        return False

    required_methods = [
        "outdoor_airflow_by_zone_m3_h",
        "airflow_opening_area_by_window_m2",
        "opening_fraction_by_window",
    ]

    for method_name in required_methods:
        if not hasattr(window_boundary_result, method_name):
            return False

    return True


def window_boundary_outdoor_airflow_by_zone_m3_h(
    window_boundary_result: Any,
) -> Dict[str, float]:
    """
    Read outdoor window airflow from BuildingWindowBoundaryResult-like object.

    This is the Phase 8 preferred window-airflow source.
    """

    if not is_building_window_boundary_result_like(window_boundary_result):
        raise TypeError(
            "window_boundary_result must behave like BuildingWindowBoundaryResult."
        )

    return window_boundary_result.outdoor_airflow_by_zone_m3_h()


def make_window_operation_inputs_from_airflow_control_inputs(
    airflow_control_inputs: "BuildingAirflowControlInputs",
):
    """
    Compatibility bridge.

    Existing airflow runner input:
        BuildingAirflowControlInputs.window_openings

    New shared window input:
        BuildingWindowOperationInputs

    This lets old Phase 5 tests keep using WindowOpeningInput while the actual
    window physics comes from windows.py.
    """

    if not isinstance(airflow_control_inputs, BuildingAirflowControlInputs):
        raise TypeError(
            "airflow_control_inputs must be BuildingAirflowControlInputs."
        )

    from nexusep.abbey.building.physics.windows import (
        BuildingWindowOperationInputs,
        ZoneWindowOperationInput,
    )

    operation_inputs_by_window = {}

    for window_id, window_opening in airflow_control_inputs.window_openings.items():
        operation_inputs_by_window[window_id] = ZoneWindowOperationInput(
            boundary_connection_id=window_opening.boundary_connection_id,
            zone_id=window_opening.zone_id,
            is_open=window_opening.opening_fraction > 0.0,
            opening_fraction=window_opening.opening_fraction,
            curtain_open=True,
            blind_open=True,
            blind_fraction=0.0,
            source="converted_from_BuildingAirflowControlInputs",
        )

    return BuildingWindowOperationInputs(
        operation_inputs_by_window=operation_inputs_by_window,
        source="converted_from_BuildingAirflowControlInputs",
    )


def calculate_window_boundary_result_for_airflow(
    building_model: Any,
    physics_graph: Any,
    weather_state: Any,
    airflow_control_inputs: "BuildingAirflowControlInputs",
):
    """
    Build BuildingWindowBoundaryResult for airflow.py.

    airflow.py does not calculate window physics anymore.
    It only prepares compatible bridge input and asks windows.py for the shared
    boundary result.
    """

    if building_model is None:
        raise ValueError("building_model cannot be None.")

    if physics_graph is None:
        raise ValueError("physics_graph cannot be None.")

    if weather_state is None:
        raise ValueError("weather_state cannot be None.")

    if not isinstance(airflow_control_inputs, BuildingAirflowControlInputs):
        raise TypeError(
            "airflow_control_inputs must be BuildingAirflowControlInputs."
        )

    from nexusep.abbey.building.physics.windows import (
        calculate_building_window_boundary_result,
    )

    window_operation_inputs = make_window_operation_inputs_from_airflow_control_inputs(
        airflow_control_inputs=airflow_control_inputs,
    )

    return calculate_building_window_boundary_result(
        physics_graph=physics_graph,
        building_model=building_model,
        building_window_operation_inputs=window_operation_inputs,
        weather_state=weather_state,
    )

def make_airflow_control_inputs(
    occupancy_by_zone_people: Dict[str, float] = None,
    window_opening_fractions: Dict[str, float] = None,
    window_zone_ids: Dict[str, str] = None,
    door_opening_fractions: Dict[str, float] = None,
    door_zone_pairs: Dict[str, List[str]] = None,
) -> BuildingAirflowControlInputs:
    """
    Convenience builder from plain dictionaries.

    Useful for runner tests and bridges.

    window_opening_fractions:
        boundary_connection_id -> opening_fraction

    window_zone_ids:
        boundary_connection_id -> zone_id

    door_opening_fractions:
        zone_connection_id -> opening_fraction

    door_zone_pairs:
        zone_connection_id -> [zone_a_id, zone_b_id]
    """

    occupancy_by_zone_people = occupancy_by_zone_people or {}
    window_opening_fractions = window_opening_fractions or {}
    window_zone_ids = window_zone_ids or {}
    door_opening_fractions = door_opening_fractions or {}
    door_zone_pairs = door_zone_pairs or {}

    occupancy_by_zone = {}

    for zone_id, number_of_people in occupancy_by_zone_people.items():
        occupancy_by_zone[zone_id] = ZoneOccupancyInput(
            zone_id=zone_id,
            number_of_people=number_of_people,
            source="dictionary_builder",
        )

    window_openings = {}

    for boundary_connection_id, opening_fraction in window_opening_fractions.items():
        zone_id = window_zone_ids.get(boundary_connection_id, "")

        if not zone_id:
            raise ValueError(
                "Missing zone_id for window boundary "
                + boundary_connection_id
            )

        window_openings[boundary_connection_id] = WindowOpeningInput(
            boundary_connection_id=boundary_connection_id,
            zone_id=zone_id,
            opening_fraction=opening_fraction,
            source="dictionary_builder",
        )

    door_openings = {}

    for zone_connection_id, opening_fraction in door_opening_fractions.items():
        zone_pair = door_zone_pairs.get(zone_connection_id, None)

        if zone_pair is None or len(zone_pair) != 2:
            raise ValueError(
                "door_zone_pairs must provide [zone_a_id, zone_b_id] for "
                + zone_connection_id
            )

        door_openings[zone_connection_id] = DoorOpeningInput(
            zone_connection_id=zone_connection_id,
            zone_a_id=zone_pair[0],
            zone_b_id=zone_pair[1],
            opening_fraction=opening_fraction,
            source="dictionary_builder",
        )

    return BuildingAirflowControlInputs(
        occupancy_by_zone=occupancy_by_zone,
        window_openings=window_openings,
        door_openings=door_openings,
        source="dictionary_builder",
    )

def make_zone_airflow_parameters_from_zone_model(
    zone_model: Any,
) -> ZoneAirflowParameters:
    """
    Build ZoneAirflowParameters from ZoneModel.
    """

    if zone_model is None:
        raise ValueError("zone_model cannot be None.")

    zone_id = _required_attr(zone_model, "zone_id")

    air_volume_m3 = _first_existing_attr_or_default(
        zone_model,
        [
            "air_volume_m3",
            "volume_m3",
        ],
        None,
    )

    if air_volume_m3 is None:
        floor_area_m2 = _get_attr_or_default(
            zone_model,
            "floor_area_m2",
            None,
        )

        height_m = _get_attr_or_default(
            zone_model,
            "height_m",
            None,
        )

        if floor_area_m2 is not None and height_m is not None:
            air_volume_m3 = float(floor_area_m2) * float(height_m)
        else:
            air_volume_m3 = DEFAULT_ZONE_AIR_VOLUME_M3

    default_infiltration_ach = _get_attr_or_default(
        zone_model,
        "default_infiltration_ach",
        DEFAULT_INFILTRATION_ACH,
    )

    mechanical_ventilation_available = bool(
        _get_attr_or_default(
            zone_model,
            "mechanical_ventilation_available",
            False,
        )
    )

    mechanical_ventilation_flow_m3_h = _get_attr_or_default(
        zone_model,
        "mechanical_ventilation_flow_m3_h",
        DEFAULT_MECHANICAL_VENTILATION_FLOW_M3_H,
    )

    co2_generation_per_person_m3_h = _get_attr_or_default(
        zone_model,
        "co2_generation_per_person_m3_h",
        DEFAULT_CO2_GENERATION_PER_PERSON_M3_H,
    )

    return ZoneAirflowParameters(
        zone_id=zone_id,
        air_volume_m3=air_volume_m3,
        default_infiltration_ach=default_infiltration_ach,
        default_infiltration_flow_m3_h=0.0,
        mechanical_ventilation_available=mechanical_ventilation_available,
        mechanical_ventilation_flow_m3_h=mechanical_ventilation_flow_m3_h,
        co2_generation_per_person_m3_h=co2_generation_per_person_m3_h,
        source="ZoneModel",
    )


def make_building_airflow_parameters(
    building_model: Any,
) -> BuildingAirflowParameters:
    """
    Build BuildingAirflowParameters from BuildingModel / ZoneModel.
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
        zone_parameters[zone_id] = make_zone_airflow_parameters_from_zone_model(
            zone_model
        )

    return BuildingAirflowParameters(
        zone_parameters=zone_parameters,
    )

def make_initial_zone_air_state_from_zone_model(
    zone_model: Any,
) -> ZoneAirState:
    """
    Create initial air/CO2 state from ZoneModel.
    """

    if zone_model is None:
        raise ValueError("zone_model cannot be None.")

    zone_id = _required_attr(zone_model, "zone_id")

    co2_ppm = _first_existing_attr_or_default(
        zone_model,
        [
            "co2_initial_ppm",
            "initial_co2_ppm",
        ],
        DEFAULT_INITIAL_CO2_PPM,
    )

    air_volume_m3 = _first_existing_attr_or_default(
        zone_model,
        [
            "air_volume_m3",
            "volume_m3",
        ],
        None,
    )

    if air_volume_m3 is None:
        floor_area_m2 = _get_attr_or_default(
            zone_model,
            "floor_area_m2",
            None,
        )

        height_m = _get_attr_or_default(
            zone_model,
            "height_m",
            None,
        )

        if floor_area_m2 is not None and height_m is not None:
            air_volume_m3 = float(floor_area_m2) * float(height_m)
        else:
            air_volume_m3 = DEFAULT_ZONE_AIR_VOLUME_M3

    return ZoneAirState(
        zone_id=zone_id,
        co2_ppm=co2_ppm,
        air_volume_m3=air_volume_m3,
    )


def make_initial_building_air_state(
    building_model: Any,
) -> BuildingAirState:
    """
    Create initial BuildingAirState from BuildingModel / ZoneModel.
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
        zone_states[zone_id] = make_initial_zone_air_state_from_zone_model(
            zone_model
        )

    return BuildingAirState(
        zone_states=zone_states,
    )

def outdoor_airflow_mixing_exchange_by_zone_m3_s(
    outdoor_airflow_result: BuildingOutdoorAirflowResult,
) -> Dict[str, float]:
    """
    Return outdoor mixing exchange by zone in m3/s.
    """

    if not isinstance(outdoor_airflow_result, BuildingOutdoorAirflowResult):
        raise TypeError(
            "outdoor_airflow_result must be BuildingOutdoorAirflowResult."
        )

    return outdoor_airflow_result.mixing_exchange_by_zone_m3_s()

def window_wind_alignment_factor(
    wind_direction_deg: Any,
    window_orientation_deg: Any,
) -> float:
    """
    Approximate how strongly wind drives airflow through a window.

    Convention:
    - wind_direction_deg is the direction wind comes from
    - window_orientation_deg is the outward normal of the facade/window

    If wind comes directly toward the facade, factor is near 1.
    If wind is parallel or opposite, factor approaches 0.

    If orientation is unknown, use a neutral default factor.
    """

    if window_orientation_deg is None:
        return DEFAULT_WINDOW_WIND_ALIGNMENT_FACTOR_IF_UNKNOWN

    wind_direction_deg = _normalize_degrees(wind_direction_deg)
    window_orientation_deg = _normalize_degrees(window_orientation_deg)

    difference_deg = _angular_difference_degrees(
        wind_direction_deg,
        window_orientation_deg,
    )

    factor = math.cos(math.radians(difference_deg))

    if factor < 0.0:
        factor = 0.0

    return _clamp_unit_interval(factor)

def interzone_mixing_flow_by_zone_m3_s(
    interzone_airflow_result: BuildingInterzoneAirflowResult,
) -> Dict[str, float]:
    """
    Return total interzone mixing flow touching each zone in m3/s.
    """

    if not isinstance(interzone_airflow_result, BuildingInterzoneAirflowResult):
        raise TypeError(
            "interzone_airflow_result must be BuildingInterzoneAirflowResult."
        )

    return interzone_airflow_result.mixing_flow_by_zone_m3_s()

def _make_interzone_co2_targets_for_zone(
    zone_id: str,
    air_state: BuildingAirState,
    airflow_network: BuildingAirflowNetwork,
) -> List[CO2ConcentrationTarget]:
    """
    Build interzone CO2 concentration targets for one zone.

    For symmetric mixing:
        each adjacent zone contributes q_mix * C_adjacent
    """

    targets = []

    for link in airflow_network.interzone_links_for_zone(zone_id):
        adjacent_zone_id = link.other_zone_id(zone_id)

        if not air_state.has_zone(adjacent_zone_id):
            continue

        adjacent_state = air_state.get_zone_state(adjacent_zone_id)

        targets.append(
            CO2ConcentrationTarget(
                target_id=link.link_id + "__" + adjacent_zone_id,
                target_type="interzone_air",
                co2_ppm=adjacent_state.co2_ppm,
                airflow_m3_s=link.mixing_flow_m3_s(),
            )
        )

    return targets

def check_interzone_airflow_symmetry(
    interzone_airflow_result: BuildingInterzoneAirflowResult,
    tolerance_m3_h: float = 1e-9,
) -> bool:
    """
    Check all interzone airflow records are symmetric.

    Required by Phase 5.7:
        mixing A↔B approximately conserves air.
    """

    if not isinstance(interzone_airflow_result, BuildingInterzoneAirflowResult):
        raise TypeError(
            "interzone_airflow_result must be BuildingInterzoneAirflowResult."
        )

    return interzone_airflow_result.all_records_symmetric(
        tolerance_m3_h=tolerance_m3_h
    )

def airflow_network_outdoor_exchange_by_zone_m3_s(
    airflow_network: BuildingAirflowNetwork,
) -> Dict[str, float]:
    if not isinstance(airflow_network, BuildingAirflowNetwork):
        raise TypeError("airflow_network must be BuildingAirflowNetwork.")

    return airflow_network.outdoor_mixing_by_zone_m3_s()


def airflow_network_interzone_exchange_by_zone_m3_s(
    airflow_network: BuildingAirflowNetwork,
) -> Dict[str, float]:
    if not isinstance(airflow_network, BuildingAirflowNetwork):
        raise TypeError("airflow_network must be BuildingAirflowNetwork.")

    return airflow_network.interzone_mixing_by_zone_m3_s()


def airflow_network_total_exchange_by_zone_m3_h(
    airflow_network: BuildingAirflowNetwork,
) -> Dict[str, float]:
    if not isinstance(airflow_network, BuildingAirflowNetwork):
        raise TypeError("airflow_network must be BuildingAirflowNetwork.")

    return airflow_network.total_air_exchange_by_zone_m3_h()


def check_airflow_network_mass_balance(
    airflow_network: BuildingAirflowNetwork,
    tolerance_m3_h: float = 1e-9,
) -> bool:
    """
    Check approximate mass balance.

    In this simplified model:
    - outdoor supply/exhaust are balanced
    - interzone records are symmetric
    """

    if not isinstance(airflow_network, BuildingAirflowNetwork):
        raise TypeError("airflow_network must be BuildingAirflowNetwork.")

    tolerance_m3_h = float(tolerance_m3_h)

    for value in airflow_network.approximate_net_air_balance_by_zone_m3_h().values():
        if abs(value) > tolerance_m3_h:
            return False

    if not airflow_network.all_interzone_records_symmetric(
        tolerance_m3_h=tolerance_m3_h
    ):
        return False

    return True

def _zone_connection_zone_a_id(
    zone_connection: Any,
) -> str:
    """
    Compatibility helper.

    Some graph versions use:
        zone_a_id / zone_b_id

    Current graph may use:
        from_zone_id / to_zone_id
    """

    zone_a_id = _first_existing_attr_or_default(
        zone_connection,
        [
            "zone_a_id",
            "from_zone_id",
        ],
        None,
    )

    if zone_a_id is None:
        raise AttributeError(
            "ZoneConnection must provide zone_a_id or from_zone_id."
        )

    return str(zone_a_id)


def _zone_connection_zone_b_id(
    zone_connection: Any,
) -> str:
    zone_b_id = _first_existing_attr_or_default(
        zone_connection,
        [
            "zone_b_id",
            "to_zone_id",
        ],
        None,
    )

    if zone_b_id is None:
        raise AttributeError(
            "ZoneConnection must provide zone_b_id or to_zone_id."
        )

    return str(zone_b_id)

def _normalize_degrees(
    angle_deg: Any,
) -> float:
    angle_deg = float(angle_deg)
    angle_deg = angle_deg % 360.0

    if angle_deg < 0.0:
        angle_deg += 360.0

    return angle_deg


def _angular_difference_degrees(
    angle_a_deg: Any,
    angle_b_deg: Any,
) -> float:
    angle_a_deg = _normalize_degrees(angle_a_deg)
    angle_b_deg = _normalize_degrees(angle_b_deg)

    difference = abs(angle_a_deg - angle_b_deg)

    if difference > 180.0:
        difference = 360.0 - difference

    return difference


def _is_window_boundary_connection(
    boundary_connection: Any,
) -> bool:
    connection_type = str(
        _get_attr_or_default(
            boundary_connection,
            "connection_type",
            "",
        )
    ).strip().lower()

    if connection_type == "window":
        return True

    return bool(
        _get_attr_or_default(
            boundary_connection,
            "is_window",
            False,
        )
    )

def _required_attr(
    obj: Any,
    attribute_name: str,
) -> Any:
    if obj is None:
        raise ValueError(
            "Cannot read required attribute "
            + attribute_name
            + " from None."
        )

    if not hasattr(obj, attribute_name):
        raise AttributeError(
            "Object is missing required attribute: "
            + attribute_name
        )

    value = getattr(obj, attribute_name)

    if value is None:
        raise ValueError(
            "Required attribute "
            + attribute_name
            + " cannot be None."
        )

    return value


def _get_attr_or_default(
    obj: Any,
    attribute_name: str,
    default: Any,
) -> Any:
    if obj is None:
        return default

    if not hasattr(obj, attribute_name):
        return default

    value = getattr(obj, attribute_name)

    if value is None:
        return default

    return value


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


def _positive_float(
    value: Any,
    field_name: str,
    context: str,
) -> float:
    value = float(value)

    if value <= 0.0:
        raise ValueError(
            field_name
            + " for "
            + context
            + " must be positive."
        )

    return value


def _bounded_co2_ppm(
    co2_ppm: Any,
) -> float:
    co2_ppm = float(co2_ppm)

    if co2_ppm < MIN_PHYSICAL_CO2_PPM:
        return MIN_PHYSICAL_CO2_PPM

    return co2_ppm

def _non_negative_float(
    value: Any,
    field_name: str,
    context: str,
) -> float:
    value = float(value)

    if value < 0.0:
        raise ValueError(
            field_name
            + " for "
            + context
            + " cannot be negative."
        )

    return value

def _clamp_unit_interval(
    value: Any,
) -> float:
    value = float(value)

    if value < 0.0:
        return 0.0

    if value > 1.0:
        return 1.0

    return value

