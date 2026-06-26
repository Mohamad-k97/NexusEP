"""

Important rule:
    Static window properties come from BoundaryConnection.
    Dynamic operation state comes from clean bridge inputs.
    Physics modules consume shared window boundary results.

No solver yet in Phase 8.1.
"""

from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional
import copy
import math

#%% defaults
WINDOW_MODEL_FAMILY = "shared_window_boundary_model"
WINDOW_MODEL_INTERFACE_MODE = "shared_window_boundary_adapter"

WINDOW_STATIC_SOURCE = "BoundaryConnection"
WINDOW_DYNAMIC_SOURCE = "WindowOperationInput"
WINDOW_WEATHER_SOURCE = "WeatherState"

WINDOW_TO_THERMAL = "window_to_thermal"
WINDOW_TO_AIRFLOW = "window_to_airflow"
WINDOW_TO_CO2 = "window_to_co2_via_airflow"
WINDOW_TO_MOISTURE = "window_to_moisture_via_airflow"
WINDOW_TO_DAYLIGHT = "window_to_daylight"
WINDOW_TO_LIGHTING = "window_to_lighting_via_daylight"

WINDOW_NOT_SOLVER = "window_model_is_boundary_adapter_not_physics_solver"

WINDOW_STATIC_PROPERTIES = [
    "orientation_deg",
    "area_m2",
    "window_u_value_w_m2k",
    "glazing_transmittance",
    "window_visible_transmittance",
    "solar_heat_gain_coefficient",
    "frame_fraction",
    "shading_factor",
    "max_opening_area_m2",
    "discharge_coefficient",
]

WINDOW_DYNAMIC_PROPERTIES = [
    "is_open",
    "opening_fraction",
    "curtain_open",
    "blind_open",
    "blind_fraction",
]

WINDOW_SHARED_OUTPUTS = [
    "effective_visible_transmittance",
    "effective_solar_factor",
    "effective_u_value_w_m2k",
    "opening_fraction",
    "airflow_opening_area_m2",
    "wind_alignment_factor",
    "solar_alignment_factor",
]

WINDOW_MODEL_DECISION = (
    "single_shared_window_boundary_adapter_for_thermal_airflow_moisture_and_daylight"
)

DEFAULT_WINDOW_AREA_M2 = 0.0
DEFAULT_WINDOW_U_VALUE_W_M2K = 1.6
DEFAULT_GLAZING_TRANSMITTANCE = 0.60
DEFAULT_WINDOW_VISIBLE_TRANSMITTANCE = 0.60
DEFAULT_SOLAR_HEAT_GAIN_COEFFICIENT = 0.50
DEFAULT_WINDOW_FRAME_FRACTION = 0.20
DEFAULT_WINDOW_SHADING_FACTOR = 1.00
DEFAULT_WINDOW_MAX_OPENING_AREA_M2 = 0.0
DEFAULT_WINDOW_DISCHARGE_COEFFICIENT = 0.60

WINDOW_STATIC_PARAMETER_SOURCE = "BoundaryConnection"

WINDOW_OPERATION_INPUT_SOURCE = "external_window_operation_bridge"
WINDOW_OPERATION_STATE_SOURCE = "WindowStaticParameters + WindowOperationInput"

DEFAULT_WINDOW_IS_OPEN = False
DEFAULT_WINDOW_OPENING_FRACTION = 0.0

DEFAULT_CURTAIN_OPEN = True
DEFAULT_BLIND_OPEN = True
DEFAULT_BLIND_FRACTION = 0.0

WINDOW_CONTROL_MODE_MANUAL = "manual"
WINDOW_CONTROL_MODE_AUTO = "auto"
WINDOW_CONTROL_MODE_SCHEDULE = "schedule"
WINDOW_CONTROL_MODE_OCCUPANT = "occupant"

VALID_WINDOW_CONTROL_MODES = {
    WINDOW_CONTROL_MODE_MANUAL,
    WINDOW_CONTROL_MODE_AUTO,
    WINDOW_CONTROL_MODE_SCHEDULE,
    WINDOW_CONTROL_MODE_OCCUPANT,
}

DEFAULT_CURTAIN_DAYLIGHT_REDUCTION_FACTOR = 0.35
DEFAULT_CURTAIN_SOLAR_REDUCTION_FACTOR = 0.50

DEFAULT_BLIND_DAYLIGHT_REDUCTION_FACTOR = 0.25
DEFAULT_BLIND_SOLAR_REDUCTION_FACTOR = 0.35

WINDOW_COVERING_EFFECT_SOURCE = "WindowStaticParameters + WindowOperationState"

ORIENTATION_NORTH = "north"
ORIENTATION_NORTH_EAST = "north_east"
ORIENTATION_EAST = "east"
ORIENTATION_SOUTH_EAST = "south_east"
ORIENTATION_SOUTH = "south"
ORIENTATION_SOUTH_WEST = "south_west"
ORIENTATION_WEST = "west"
ORIENTATION_NORTH_WEST = "north_west"

DIRECTION_ALIGNMENT_MODE_COSINE_FRONT_ONLY = "cosine_front_only"

WIND_DIRECTION_CONVENTION = (
    "wind_direction_deg_is_direction_wind_comes_from"
)

SOLAR_DIRECTION_CONVENTION = (
    "solar_azimuth_deg_is_direction_of_sun_position"
)
WINDOW_AIRFLOW_OPENING_SOURCE = (
    "WindowStaticParameters + WindowOperationState + WeatherState"
)

DEFAULT_WINDOW_WIND_SPEED_M_S = 0.0
DEFAULT_WINDOW_WIND_ALIGNMENT_FACTOR = 0.0

WINDOW_AIRFLOW_MODEL = "wind_aligned_opening_area_model"
WINDOW_AIRFLOW_UNIT = "m3_h"

WINDOW_THERMAL_CONDUCTANCE_SOURCE = "WindowStaticParameters + indoor_outdoor_temperature"
WINDOW_OPENING_THERMAL_EXCHANGE_SOURCE = "WindowAirflowOpeningResult + indoor_outdoor_temperature"

DEFAULT_WINDOW_INDOOR_TEMPERATURE_C = 20.0
DEFAULT_WINDOW_OUTDOOR_TEMPERATURE_C = 20.0

WINDOW_AIR_DENSITY_KG_M3 = 1.2
WINDOW_AIR_SPECIFIC_HEAT_J_KG_K = 1005.0

WINDOW_THERMAL_SIGN_CONVENTION = (
    "positive_heat_flow_w_means_heat_gain_to_zone"
)

WINDOW_SOLAR_EXPOSURE_SOURCE = "WindowStaticParameters + WeatherState"

DEFAULT_SOLAR_AZIMUTH_DEG = None
DEFAULT_SOLAR_ALTITUDE_DEG = None

DEFAULT_SKY_CONDITION = "unknown"

DEFAULT_CLEAR_SKY_EXPOSURE_FACTOR = 0.75
DEFAULT_PARTLY_CLOUDY_EXPOSURE_FACTOR = 0.55
DEFAULT_CLOUDY_EXPOSURE_FACTOR = 0.35
DEFAULT_OVERCAST_EXPOSURE_FACTOR = 0.25
DEFAULT_UNKNOWN_SKY_EXPOSURE_FACTOR = 0.50
DEFAULT_NIGHT_SKY_EXPOSURE_FACTOR = 0.0

DEFAULT_DIFFUSE_DAYLIGHT_EXPOSURE_FRACTION = 0.25
DEFAULT_DIFFUSE_SOLAR_EXPOSURE_FRACTION = 0.10

WINDOW_BOUNDARY_RESULT_SOURCE = (
    "WindowStaticParameters + WindowOperationState + covering + airflow + solar exposure"
)

WINDOW_BOUNDARY_RESULT_INTERFACE_MODE = "shared_cross_physics_window_boundary_result"

DEFAULT_EFFECTIVE_U_VALUE_W_M2K = DEFAULT_WINDOW_U_VALUE_W_M2K


#%% dataclasses

@dataclass
class WindowArchitectureDecision:
    """
    Formal architecture decision for ABBEY Phase 8.

    Correct ownership:

        BoundaryConnection
            -> static window geometry and physical properties

        WindowOperationInput / WindowOperationState
            -> dynamic operation state

        WindowBoundaryModel
            -> shared timestep-level boundary result

    Physics modules should not duplicate window logic.
    """

    model_family: str = WINDOW_MODEL_FAMILY
    interface_mode: str = WINDOW_MODEL_INTERFACE_MODE

    static_source: str = WINDOW_STATIC_SOURCE
    dynamic_source: str = WINDOW_DYNAMIC_SOURCE
    weather_source: str = WINDOW_WEATHER_SOURCE

    window_to_thermal: str = WINDOW_TO_THERMAL
    window_to_airflow: str = WINDOW_TO_AIRFLOW
    window_to_co2: str = WINDOW_TO_CO2
    window_to_moisture: str = WINDOW_TO_MOISTURE
    window_to_daylight: str = WINDOW_TO_DAYLIGHT
    window_to_lighting: str = WINDOW_TO_LIGHTING

    solver_role: str = WINDOW_NOT_SOLVER

    static_properties: List[str] = None
    dynamic_properties: List[str] = None
    shared_outputs: List[str] = None

    decision: str = WINDOW_MODEL_DECISION

    def __post_init__(self) -> None:
        if self.static_properties is None:
            self.static_properties = list(WINDOW_STATIC_PROPERTIES)

        if self.dynamic_properties is None:
            self.dynamic_properties = list(WINDOW_DYNAMIC_PROPERTIES)

        if self.shared_outputs is None:
            self.shared_outputs = list(WINDOW_SHARED_OUTPUTS)

        self.model_family = str(self.model_family).strip().lower()
        self.interface_mode = str(self.interface_mode).strip().lower()

        self.static_source = str(self.static_source).strip()
        self.dynamic_source = str(self.dynamic_source).strip()
        self.weather_source = str(self.weather_source).strip()

        self.window_to_thermal = str(self.window_to_thermal).strip().lower()
        self.window_to_airflow = str(self.window_to_airflow).strip().lower()
        self.window_to_co2 = str(self.window_to_co2).strip().lower()
        self.window_to_moisture = str(self.window_to_moisture).strip().lower()
        self.window_to_daylight = str(self.window_to_daylight).strip().lower()
        self.window_to_lighting = str(self.window_to_lighting).strip().lower()

        self.solver_role = str(self.solver_role).strip().lower()
        self.decision = str(self.decision).strip().lower()

        self._validate()

    def _validate(self) -> None:
        if self.model_family != WINDOW_MODEL_FAMILY:
            raise ValueError(
                "model_family must be " + WINDOW_MODEL_FAMILY + "."
            )

        if self.interface_mode != WINDOW_MODEL_INTERFACE_MODE:
            raise ValueError(
                "interface_mode must be " + WINDOW_MODEL_INTERFACE_MODE + "."
            )

        if self.static_source != WINDOW_STATIC_SOURCE:
            raise ValueError(
                "Window static properties must come from BoundaryConnection."
            )

        if self.dynamic_source != WINDOW_DYNAMIC_SOURCE:
            raise ValueError(
                "Window dynamic state must come from WindowOperationInput."
            )

        if self.weather_source != WINDOW_WEATHER_SOURCE:
            raise ValueError(
                "Window direction/weather effects must read WeatherState."
            )

        if self.solver_role != WINDOW_NOT_SOLVER:
            raise ValueError(
                "Phase 8 window model must be a boundary adapter, not a solver."
            )

        missing_static = []

        for property_name in WINDOW_STATIC_PROPERTIES:
            if property_name not in self.static_properties:
                missing_static.append(property_name)

        if missing_static:
            raise ValueError(
                "Window architecture is missing static properties: "
                + str(missing_static)
            )

        missing_dynamic = []

        for property_name in WINDOW_DYNAMIC_PROPERTIES:
            if property_name not in self.dynamic_properties:
                missing_dynamic.append(property_name)

        if missing_dynamic:
            raise ValueError(
                "Window architecture is missing dynamic properties: "
                + str(missing_dynamic)
            )

        missing_outputs = []

        for output_name in WINDOW_SHARED_OUTPUTS:
            if output_name not in self.shared_outputs:
                missing_outputs.append(output_name)

        if missing_outputs:
            raise ValueError(
                "Window architecture is missing shared outputs: "
                + str(missing_outputs)
            )

    def coupling_order(self) -> List[str]:
        return [
            "BoundaryConnection_to_static_window_parameters",
            "WindowOperationInput_to_dynamic_window_state",
            "WeatherState_to_directional_factors",
            "WindowBoundaryModel_to_shared_window_boundary_result",
            "shared_window_result_to_thermal",
            "shared_window_result_to_airflow",
            "airflow_to_co2",
            "airflow_to_moisture",
            "shared_window_result_to_daylight",
            "daylight_to_lighting_visual_comfort",
        ]

    def physics_consumers(self) -> List[str]:
        return [
            "thermal",
            "airflow",
            "co2_via_airflow",
            "moisture_via_airflow",
            "daylight",
            "lighting_via_daylight",
        ]

    def duplicate_logic_forbidden_in(self) -> List[str]:
        return [
            "thermal.py",
            "airflow.py",
            "moisture.py",
            "daylight.py",
        ]

    def copy(self, **updates: Any) -> "WindowArchitectureDecision":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_family": self.model_family,
            "interface_mode": self.interface_mode,
            "static_source": self.static_source,
            "dynamic_source": self.dynamic_source,
            "weather_source": self.weather_source,
            "window_to_thermal": self.window_to_thermal,
            "window_to_airflow": self.window_to_airflow,
            "window_to_co2": self.window_to_co2,
            "window_to_moisture": self.window_to_moisture,
            "window_to_daylight": self.window_to_daylight,
            "window_to_lighting": self.window_to_lighting,
            "solver_role": self.solver_role,
            "static_properties": list(self.static_properties),
            "dynamic_properties": list(self.dynamic_properties),
            "shared_outputs": list(self.shared_outputs),
            "coupling_order": self.coupling_order(),
            "physics_consumers": self.physics_consumers(),
            "duplicate_logic_forbidden_in": self.duplicate_logic_forbidden_in(),
            "decision": self.decision,
        }
    
@dataclass
class WindowStaticParameters:
    """
    Static window parameters extracted from BoundaryConnection.

    This class contains geometry and physical properties only.
    It does not contain open/closed state.
    It does not contain curtain/blind operation state.
    """

    boundary_connection_id: str
    zone_id: str

    orientation_deg: float
    area_m2: float = DEFAULT_WINDOW_AREA_M2

    window_u_value_w_m2k: float = DEFAULT_WINDOW_U_VALUE_W_M2K

    glazing_transmittance: float = DEFAULT_GLAZING_TRANSMITTANCE
    window_visible_transmittance: float = DEFAULT_WINDOW_VISIBLE_TRANSMITTANCE
    solar_heat_gain_coefficient: float = DEFAULT_SOLAR_HEAT_GAIN_COEFFICIENT

    frame_fraction: float = DEFAULT_WINDOW_FRAME_FRACTION
    shading_factor: float = DEFAULT_WINDOW_SHADING_FACTOR

    max_opening_area_m2: float = DEFAULT_WINDOW_MAX_OPENING_AREA_M2
    discharge_coefficient: float = DEFAULT_WINDOW_DISCHARGE_COEFFICIENT

    source: str = WINDOW_STATIC_PARAMETER_SOURCE

    def __post_init__(self) -> None:
        if not self.boundary_connection_id:
            raise ValueError(
                "WindowStaticParameters.boundary_connection_id cannot be empty."
            )

        if not self.zone_id:
            raise ValueError("WindowStaticParameters.zone_id cannot be empty.")

        self.orientation_deg = normalize_orientation_deg(
            self.orientation_deg
        )

        self.area_m2 = _non_negative_float(
            self.area_m2,
            "area_m2",
            self.boundary_connection_id,
        )

        self.window_u_value_w_m2k = _non_negative_float(
            self.window_u_value_w_m2k,
            "window_u_value_w_m2k",
            self.boundary_connection_id,
        )

        self.glazing_transmittance = _clamp_unit_interval(
            self.glazing_transmittance
        )

        self.window_visible_transmittance = _clamp_unit_interval(
            self.window_visible_transmittance
        )

        self.solar_heat_gain_coefficient = _clamp_unit_interval(
            self.solar_heat_gain_coefficient
        )

        self.frame_fraction = _clamp_unit_interval(
            self.frame_fraction
        )

        self.shading_factor = _clamp_unit_interval(
            self.shading_factor
        )

        self.max_opening_area_m2 = _non_negative_float(
            self.max_opening_area_m2,
            "max_opening_area_m2",
            self.boundary_connection_id,
        )

        self.discharge_coefficient = _clamp_unit_interval(
            self.discharge_coefficient
        )

    def effective_glazed_area_m2(self) -> float:
        return self.area_m2 * (1.0 - self.frame_fraction)

    def closed_window_conductance_w_k(self) -> float:
        return self.window_u_value_w_m2k * self.area_m2

    def copy(self, **updates: Any) -> "WindowStaticParameters":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_connection_id": self.boundary_connection_id,
            "zone_id": self.zone_id,
            "orientation_deg": self.orientation_deg,
            "area_m2": self.area_m2,
            "window_u_value_w_m2k": self.window_u_value_w_m2k,
            "glazing_transmittance": self.glazing_transmittance,
            "window_visible_transmittance": self.window_visible_transmittance,
            "solar_heat_gain_coefficient": self.solar_heat_gain_coefficient,
            "frame_fraction": self.frame_fraction,
            "shading_factor": self.shading_factor,
            "max_opening_area_m2": self.max_opening_area_m2,
            "discharge_coefficient": self.discharge_coefficient,
            "effective_glazed_area_m2": self.effective_glazed_area_m2(),
            "closed_window_conductance_w_k": self.closed_window_conductance_w_k(),
            "source": self.source,
        }
    
@dataclass
class ZoneWindowStaticParameters:
    """
    Static window parameters for one zone.
    """

    zone_id: str
    windows: List[WindowStaticParameters] = None

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError(
                "ZoneWindowStaticParameters.zone_id cannot be empty."
            )

        if self.windows is None:
            self.windows = []

        cleaned = []

        for window in self.windows:
            if not isinstance(window, WindowStaticParameters):
                raise TypeError(
                    "ZoneWindowStaticParameters.windows must contain "
                    "WindowStaticParameters objects."
                )

            if window.zone_id != self.zone_id:
                raise ValueError(
                    "Window zone_id "
                    + window.zone_id
                    + " does not match zone container "
                    + self.zone_id
                )

            cleaned.append(window)

        self.windows = cleaned

    def add_window(self, window: WindowStaticParameters) -> None:
        if not isinstance(window, WindowStaticParameters):
            raise TypeError("window must be WindowStaticParameters.")

        if window.zone_id != self.zone_id:
            raise ValueError(
                "Window zone_id does not match ZoneWindowStaticParameters.zone_id."
            )

        self.windows.append(window)

    def window_count(self) -> int:
        return len(self.windows)

    def total_window_area_m2(self) -> float:
        return sum(
            window.area_m2
            for window in self.windows
        )

    def total_effective_glazed_area_m2(self) -> float:
        return sum(
            window.effective_glazed_area_m2()
            for window in self.windows
        )

    def total_closed_window_conductance_w_k(self) -> float:
        return sum(
            window.closed_window_conductance_w_k()
            for window in self.windows
        )

    def copy(self, **updates: Any) -> "ZoneWindowStaticParameters":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "window_count": self.window_count(),
            "total_window_area_m2": self.total_window_area_m2(),
            "total_effective_glazed_area_m2": self.total_effective_glazed_area_m2(),
            "total_closed_window_conductance_w_k": self.total_closed_window_conductance_w_k(),
            "windows": [
                window.to_dict()
                for window in self.windows
            ],
        }


@dataclass
class BuildingWindowStaticParameters:
    """
    Static window parameters for all zones.
    """

    zone_window_parameters: Dict[str, ZoneWindowStaticParameters] = None

    def __post_init__(self) -> None:
        if self.zone_window_parameters is None:
            self.zone_window_parameters = {}

        cleaned = {}

        for zone_id, parameters in self.zone_window_parameters.items():
            if not isinstance(parameters, ZoneWindowStaticParameters):
                raise TypeError(
                    "BuildingWindowStaticParameters.zone_window_parameters "
                    "must contain ZoneWindowStaticParameters objects."
                )

            if zone_id != parameters.zone_id:
                raise ValueError(
                    "BuildingWindowStaticParameters key "
                    + zone_id
                    + " does not match parameters.zone_id "
                    + parameters.zone_id
                )

            cleaned[zone_id] = parameters

        self.zone_window_parameters = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_window_parameters.keys())

    def has_zone(self, zone_id: str) -> bool:
        return zone_id in self.zone_window_parameters

    def get_zone_window_parameters(
        self,
        zone_id: str,
    ) -> ZoneWindowStaticParameters:
        if zone_id not in self.zone_window_parameters:
            return ZoneWindowStaticParameters(
                zone_id=zone_id,
                windows=[],
            )

        return self.zone_window_parameters[zone_id]

    def window_count_by_zone(self) -> Dict[str, int]:
        return {
            zone_id: parameters.window_count()
            for zone_id, parameters in self.zone_window_parameters.items()
        }

    def total_window_area_by_zone_m2(self) -> Dict[str, float]:
        return {
            zone_id: parameters.total_window_area_m2()
            for zone_id, parameters in self.zone_window_parameters.items()
        }

    def total_closed_window_conductance_by_zone_w_k(self) -> Dict[str, float]:
        return {
            zone_id: parameters.total_closed_window_conductance_w_k()
            for zone_id, parameters in self.zone_window_parameters.items()
        }

    def copy(self, **updates: Any) -> "BuildingWindowStaticParameters":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_count_by_zone": self.window_count_by_zone(),
            "total_window_area_by_zone_m2": self.total_window_area_by_zone_m2(),
            "total_closed_window_conductance_by_zone_w_k": self.total_closed_window_conductance_by_zone_w_k(),
            "zone_window_parameters": {
                zone_id: parameters.to_dict()
                for zone_id, parameters in self.zone_window_parameters.items()
            },
        }
    
@dataclass
class ZoneWindowOperationInput:
    """
    Clean bridge input for one window operation state.

    This is the target object for agents/controllers/schedules.

    agents/controllers/schedules
        -> converted outside physics
        -> ZoneWindowOperationInput

    This class does not import agents, controllers, or schedules.
    """

    boundary_connection_id: str
    zone_id: str

    is_open: bool = DEFAULT_WINDOW_IS_OPEN
    opening_fraction: float = DEFAULT_WINDOW_OPENING_FRACTION

    curtain_open: bool = DEFAULT_CURTAIN_OPEN

    blind_open: bool = DEFAULT_BLIND_OPEN
    blind_fraction: float = DEFAULT_BLIND_FRACTION

    control_mode: str = WINDOW_CONTROL_MODE_MANUAL
    source: str = WINDOW_OPERATION_INPUT_SOURCE

    def __post_init__(self) -> None:
        if not self.boundary_connection_id:
            raise ValueError(
                "ZoneWindowOperationInput.boundary_connection_id cannot be empty."
            )

        if not self.zone_id:
            raise ValueError("ZoneWindowOperationInput.zone_id cannot be empty.")

        self.is_open = bool(self.is_open)

        self.opening_fraction = _clamp_unit_interval(
            self.opening_fraction
        )

        if not self.is_open:
            self.opening_fraction = 0.0

        self.curtain_open = bool(self.curtain_open)

        self.blind_open = bool(self.blind_open)

        self.blind_fraction = _clamp_unit_interval(
            self.blind_fraction
        )

        if self.blind_open:
            self.blind_fraction = 0.0

        self.control_mode = str(self.control_mode).strip().lower()

        if self.control_mode not in VALID_WINDOW_CONTROL_MODES:
            raise ValueError(
                "Invalid window control_mode: "
                + self.control_mode
                + ". Valid modes are: "
                + str(sorted(list(VALID_WINDOW_CONTROL_MODES)))
            )

    def copy(self, **updates: Any) -> "ZoneWindowOperationInput":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_connection_id": self.boundary_connection_id,
            "zone_id": self.zone_id,
            "is_open": self.is_open,
            "opening_fraction": self.opening_fraction,
            "curtain_open": self.curtain_open,
            "blind_open": self.blind_open,
            "blind_fraction": self.blind_fraction,
            "control_mode": self.control_mode,
            "source": self.source,
        }
    
@dataclass
class BuildingWindowOperationInputs:
    """
    Building-level clean bridge input for window operation.

    Stored by boundary_connection_id.
    """

    operation_inputs_by_window: Dict[str, ZoneWindowOperationInput] = None
    source: str = WINDOW_OPERATION_INPUT_SOURCE

    def __post_init__(self) -> None:
        if self.operation_inputs_by_window is None:
            self.operation_inputs_by_window = {}

        cleaned = {}

        for window_id, operation_input in self.operation_inputs_by_window.items():
            if not isinstance(operation_input, ZoneWindowOperationInput):
                raise TypeError(
                    "BuildingWindowOperationInputs.operation_inputs_by_window "
                    "must contain ZoneWindowOperationInput objects."
                )

            if window_id != operation_input.boundary_connection_id:
                raise ValueError(
                    "BuildingWindowOperationInputs key "
                    + window_id
                    + " does not match operation_input.boundary_connection_id "
                    + operation_input.boundary_connection_id
                )

            cleaned[window_id] = operation_input

        self.operation_inputs_by_window = cleaned

    def window_ids(self) -> List[str]:
        return list(self.operation_inputs_by_window.keys())

    def has_window(self, boundary_connection_id: str) -> bool:
        return boundary_connection_id in self.operation_inputs_by_window

    def get_operation_input_for_window(
        self,
        boundary_connection_id: str,
        zone_id: str = "",
    ) -> ZoneWindowOperationInput:
        if boundary_connection_id not in self.operation_inputs_by_window:
            return ZoneWindowOperationInput(
                boundary_connection_id=boundary_connection_id,
                zone_id=zone_id,
                is_open=False,
                opening_fraction=0.0,
                curtain_open=True,
                blind_open=True,
                blind_fraction=0.0,
                control_mode=WINDOW_CONTROL_MODE_MANUAL,
                source="default_window_closed_curtain_open_blind_open",
            )

        return self.operation_inputs_by_window[boundary_connection_id]

    def set_operation_input(
        self,
        operation_input: ZoneWindowOperationInput,
    ) -> None:
        if not isinstance(operation_input, ZoneWindowOperationInput):
            raise TypeError("operation_input must be ZoneWindowOperationInput.")

        self.operation_inputs_by_window[
            operation_input.boundary_connection_id
        ] = operation_input

    def operation_inputs_for_zone(
        self,
        zone_id: str,
    ) -> List[ZoneWindowOperationInput]:
        return [
            operation_input
            for operation_input in self.operation_inputs_by_window.values()
            if operation_input.zone_id == zone_id
        ]

    def opening_fraction_by_window(self) -> Dict[str, float]:
        return {
            window_id: operation_input.opening_fraction
            for window_id, operation_input in self.operation_inputs_by_window.items()
        }

    def curtain_open_by_window(self) -> Dict[str, bool]:
        return {
            window_id: operation_input.curtain_open
            for window_id, operation_input in self.operation_inputs_by_window.items()
        }

    def blind_fraction_by_window(self) -> Dict[str, float]:
        return {
            window_id: operation_input.blind_fraction
            for window_id, operation_input in self.operation_inputs_by_window.items()
        }

    def copy(self, **updates: Any) -> "BuildingWindowOperationInputs":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opening_fraction_by_window": self.opening_fraction_by_window(),
            "curtain_open_by_window": self.curtain_open_by_window(),
            "blind_fraction_by_window": self.blind_fraction_by_window(),
            "operation_inputs_by_window": {
                window_id: operation_input.to_dict()
                for window_id, operation_input in self.operation_inputs_by_window.items()
            },
            "source": self.source,
        }
    
@dataclass
class WindowOperationState:
    """
    Timestep-level dynamic operation state for one window.

    This is the normalized state consumed by shared window calculations.
    """

    boundary_connection_id: str
    zone_id: str

    is_open: bool = DEFAULT_WINDOW_IS_OPEN
    opening_fraction: float = DEFAULT_WINDOW_OPENING_FRACTION

    curtain_open: bool = DEFAULT_CURTAIN_OPEN

    blind_open: bool = DEFAULT_BLIND_OPEN
    blind_fraction: float = DEFAULT_BLIND_FRACTION

    source: str = WINDOW_OPERATION_STATE_SOURCE

    def __post_init__(self) -> None:
        if not self.boundary_connection_id:
            raise ValueError(
                "WindowOperationState.boundary_connection_id cannot be empty."
            )

        if not self.zone_id:
            raise ValueError("WindowOperationState.zone_id cannot be empty.")

        self.is_open = bool(self.is_open)

        self.opening_fraction = _clamp_unit_interval(
            self.opening_fraction
        )

        if not self.is_open:
            self.opening_fraction = 0.0

        self.curtain_open = bool(self.curtain_open)

        self.blind_open = bool(self.blind_open)

        self.blind_fraction = _clamp_unit_interval(
            self.blind_fraction
        )

        if self.blind_open:
            self.blind_fraction = 0.0

    def effective_opening_area_m2(
        self,
        window_static_parameters: WindowStaticParameters,
    ) -> float:
        if not isinstance(window_static_parameters, WindowStaticParameters):
            raise TypeError(
                "window_static_parameters must be WindowStaticParameters."
            )

        if (
            window_static_parameters.boundary_connection_id
            != self.boundary_connection_id
        ):
            raise ValueError(
                "WindowOperationState does not match WindowStaticParameters."
            )

        return (
            window_static_parameters.max_opening_area_m2
            * self.opening_fraction
        )

    def copy(self, **updates: Any) -> "WindowOperationState":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_connection_id": self.boundary_connection_id,
            "zone_id": self.zone_id,
            "is_open": self.is_open,
            "opening_fraction": self.opening_fraction,
            "curtain_open": self.curtain_open,
            "blind_open": self.blind_open,
            "blind_fraction": self.blind_fraction,
            "source": self.source,
        }
    
@dataclass
class BuildingWindowOperationState:
    """
    Dynamic operation state for all windows.

    Stored by boundary_connection_id.
    """

    states_by_window: Dict[str, WindowOperationState] = None

    def __post_init__(self) -> None:
        if self.states_by_window is None:
            self.states_by_window = {}

        cleaned = {}

        for window_id, state in self.states_by_window.items():
            if not isinstance(state, WindowOperationState):
                raise TypeError(
                    "BuildingWindowOperationState.states_by_window must contain "
                    "WindowOperationState objects."
                )

            if window_id != state.boundary_connection_id:
                raise ValueError(
                    "BuildingWindowOperationState key "
                    + window_id
                    + " does not match state.boundary_connection_id "
                    + state.boundary_connection_id
                )

            cleaned[window_id] = state

        self.states_by_window = cleaned

    def window_ids(self) -> List[str]:
        return list(self.states_by_window.keys())

    def has_window(self, boundary_connection_id: str) -> bool:
        return boundary_connection_id in self.states_by_window

    def get_state_for_window(
        self,
        boundary_connection_id: str,
    ) -> WindowOperationState:
        if boundary_connection_id not in self.states_by_window:
            raise KeyError(
                "Window operation state for "
                + boundary_connection_id
                + " not found."
            )

        return self.states_by_window[boundary_connection_id]

    def states_for_zone(
        self,
        zone_id: str,
    ) -> List[WindowOperationState]:
        return [
            state
            for state in self.states_by_window.values()
            if state.zone_id == zone_id
        ]

    def opening_fraction_by_window(self) -> Dict[str, float]:
        return {
            window_id: state.opening_fraction
            for window_id, state in self.states_by_window.items()
        }

    def open_window_ids(self) -> List[str]:
        return [
            window_id
            for window_id, state in self.states_by_window.items()
            if state.is_open and state.opening_fraction > 0.0
        ]

    def curtain_open_by_window(self) -> Dict[str, bool]:
        return {
            window_id: state.curtain_open
            for window_id, state in self.states_by_window.items()
        }

    def blind_fraction_by_window(self) -> Dict[str, float]:
        return {
            window_id: state.blind_fraction
            for window_id, state in self.states_by_window.items()
        }

    def copy(self, **updates: Any) -> "BuildingWindowOperationState":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "open_window_ids": self.open_window_ids(),
            "opening_fraction_by_window": self.opening_fraction_by_window(),
            "curtain_open_by_window": self.curtain_open_by_window(),
            "blind_fraction_by_window": self.blind_fraction_by_window(),
            "states_by_window": {
                window_id: state.to_dict()
                for window_id, state in self.states_by_window.items()
            },
        }

@dataclass
class WindowCoveringEffectResult:
    """
    Effective daylight and solar factors after curtain/blind effects.

    Used by:
    - daylight
    - thermal solar gains

    Not used by:
    - airflow
    """

    boundary_connection_id: str
    zone_id: str

    base_visible_transmittance: float
    base_solar_factor: float

    curtain_open: bool
    blind_open: bool
    blind_fraction: float

    curtain_daylight_reduction_factor: float = DEFAULT_CURTAIN_DAYLIGHT_REDUCTION_FACTOR
    curtain_solar_reduction_factor: float = DEFAULT_CURTAIN_SOLAR_REDUCTION_FACTOR

    blind_daylight_reduction_factor: float = DEFAULT_BLIND_DAYLIGHT_REDUCTION_FACTOR
    blind_solar_reduction_factor: float = DEFAULT_BLIND_SOLAR_REDUCTION_FACTOR

    effective_visible_transmittance: float = 0.0
    effective_solar_transmittance: float = 0.0

    effective_daylight_factor: float = 0.0
    effective_solar_factor: float = 0.0

    source: str = WINDOW_COVERING_EFFECT_SOURCE

    def __post_init__(self) -> None:
        if not self.boundary_connection_id:
            raise ValueError(
                "WindowCoveringEffectResult.boundary_connection_id cannot be empty."
            )

        if not self.zone_id:
            raise ValueError("WindowCoveringEffectResult.zone_id cannot be empty.")

        self.base_visible_transmittance = _clamp_unit_interval(
            self.base_visible_transmittance
        )

        self.base_solar_factor = _clamp_unit_interval(
            self.base_solar_factor
        )

        self.curtain_open = bool(self.curtain_open)
        self.blind_open = bool(self.blind_open)

        self.blind_fraction = _clamp_unit_interval(
            self.blind_fraction
        )

        if self.blind_open:
            self.blind_fraction = 0.0

        self.curtain_daylight_reduction_factor = _clamp_unit_interval(
            self.curtain_daylight_reduction_factor
        )

        self.curtain_solar_reduction_factor = _clamp_unit_interval(
            self.curtain_solar_reduction_factor
        )

        self.blind_daylight_reduction_factor = _clamp_unit_interval(
            self.blind_daylight_reduction_factor
        )

        self.blind_solar_reduction_factor = _clamp_unit_interval(
            self.blind_solar_reduction_factor
        )

        self.effective_visible_transmittance = _clamp_unit_interval(
            self.effective_visible_transmittance
        )

        self.effective_solar_transmittance = _clamp_unit_interval(
            self.effective_solar_transmittance
        )

        self.effective_daylight_factor = _clamp_unit_interval(
            self.effective_daylight_factor
        )

        self.effective_solar_factor = _clamp_unit_interval(
            self.effective_solar_factor
        )

    def copy(self, **updates: Any) -> "WindowCoveringEffectResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_connection_id": self.boundary_connection_id,
            "zone_id": self.zone_id,
            "base_visible_transmittance": self.base_visible_transmittance,
            "base_solar_factor": self.base_solar_factor,
            "curtain_open": self.curtain_open,
            "blind_open": self.blind_open,
            "blind_fraction": self.blind_fraction,
            "curtain_daylight_reduction_factor": self.curtain_daylight_reduction_factor,
            "curtain_solar_reduction_factor": self.curtain_solar_reduction_factor,
            "blind_daylight_reduction_factor": self.blind_daylight_reduction_factor,
            "blind_solar_reduction_factor": self.blind_solar_reduction_factor,
            "effective_visible_transmittance": self.effective_visible_transmittance,
            "effective_solar_transmittance": self.effective_solar_transmittance,
            "effective_daylight_factor": self.effective_daylight_factor,
            "effective_solar_factor": self.effective_solar_factor,
            "source": self.source,
        }
    
@dataclass
class BuildingWindowCoveringEffectResult:
    """
    Covering effects for all windows.
    """

    effects_by_window: Dict[str, WindowCoveringEffectResult] = None

    source: str = WINDOW_COVERING_EFFECT_SOURCE

    def __post_init__(self) -> None:
        if self.effects_by_window is None:
            self.effects_by_window = {}

        cleaned = {}

        for window_id, effect in self.effects_by_window.items():
            if not isinstance(effect, WindowCoveringEffectResult):
                raise TypeError(
                    "BuildingWindowCoveringEffectResult.effects_by_window "
                    "must contain WindowCoveringEffectResult objects."
                )

            if window_id != effect.boundary_connection_id:
                raise ValueError(
                    "BuildingWindowCoveringEffectResult key "
                    + window_id
                    + " does not match effect.boundary_connection_id "
                    + effect.boundary_connection_id
                )

            cleaned[window_id] = effect

        self.effects_by_window = cleaned

    def window_ids(self) -> List[str]:
        return list(self.effects_by_window.keys())

    def get_effect_for_window(
        self,
        boundary_connection_id: str,
    ) -> WindowCoveringEffectResult:
        if boundary_connection_id not in self.effects_by_window:
            raise KeyError(
                "Window covering effect for "
                + boundary_connection_id
                + " not found."
            )

        return self.effects_by_window[boundary_connection_id]

    def effects_for_zone(
        self,
        zone_id: str,
    ) -> List[WindowCoveringEffectResult]:
        return [
            effect
            for effect in self.effects_by_window.values()
            if effect.zone_id == zone_id
        ]

    def effective_daylight_factor_by_window(self) -> Dict[str, float]:
        return {
            window_id: effect.effective_daylight_factor
            for window_id, effect in self.effects_by_window.items()
        }

    def effective_solar_factor_by_window(self) -> Dict[str, float]:
        return {
            window_id: effect.effective_solar_factor
            for window_id, effect in self.effects_by_window.items()
        }

    def effective_visible_transmittance_by_window(self) -> Dict[str, float]:
        return {
            window_id: effect.effective_visible_transmittance
            for window_id, effect in self.effects_by_window.items()
        }

    def effective_solar_transmittance_by_window(self) -> Dict[str, float]:
        return {
            window_id: effect.effective_solar_transmittance
            for window_id, effect in self.effects_by_window.items()
        }

    def copy(self, **updates: Any) -> "BuildingWindowCoveringEffectResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "effective_daylight_factor_by_window": self.effective_daylight_factor_by_window(),
            "effective_solar_factor_by_window": self.effective_solar_factor_by_window(),
            "effective_visible_transmittance_by_window": self.effective_visible_transmittance_by_window(),
            "effective_solar_transmittance_by_window": self.effective_solar_transmittance_by_window(),
            "effects_by_window": {
                window_id: effect.to_dict()
                for window_id, effect in self.effects_by_window.items()
            },
            "source": self.source,
        }
    
@dataclass
class WindowAirflowOpeningResult:
    """
    Outdoor airflow potential through one window opening.

    Used by:
    - airflow.py

    Used indirectly by:
    - CO2 mass balance through airflow network
    - humidity/moisture transport through airflow network

    Not used directly by:
    - daylight
    - thermal solar gains
    """

    boundary_connection_id: str
    zone_id: str

    is_open: bool
    opening_fraction: float

    max_opening_area_m2: float
    effective_opening_area_m2: float
    discharge_coefficient: float

    wind_speed_m_s: float
    wind_direction_deg: float
    window_orientation_deg: float
    wind_alignment_factor: float

    outdoor_airflow_m3_s: float
    outdoor_airflow_m3_h: float

    source: str = WINDOW_AIRFLOW_OPENING_SOURCE

    def __post_init__(self) -> None:
        if not self.boundary_connection_id:
            raise ValueError(
                "WindowAirflowOpeningResult.boundary_connection_id cannot be empty."
            )

        if not self.zone_id:
            raise ValueError("WindowAirflowOpeningResult.zone_id cannot be empty.")

        self.is_open = bool(self.is_open)

        self.opening_fraction = _clamp_unit_interval(
            self.opening_fraction
        )

        if not self.is_open:
            self.opening_fraction = 0.0

        self.max_opening_area_m2 = _non_negative_float(
            self.max_opening_area_m2,
            "max_opening_area_m2",
            self.boundary_connection_id,
        )

        self.effective_opening_area_m2 = _non_negative_float(
            self.effective_opening_area_m2,
            "effective_opening_area_m2",
            self.boundary_connection_id,
        )

        self.discharge_coefficient = _clamp_unit_interval(
            self.discharge_coefficient
        )

        self.wind_speed_m_s = _non_negative_float(
            self.wind_speed_m_s,
            "wind_speed_m_s",
            self.boundary_connection_id,
        )

        self.wind_direction_deg = normalize_orientation_deg(
            self.wind_direction_deg
        )

        self.window_orientation_deg = normalize_orientation_deg(
            self.window_orientation_deg
        )

        self.wind_alignment_factor = _clamp_unit_interval(
            self.wind_alignment_factor
        )

        self.outdoor_airflow_m3_s = _non_negative_float(
            self.outdoor_airflow_m3_s,
            "outdoor_airflow_m3_s",
            self.boundary_connection_id,
        )

        self.outdoor_airflow_m3_h = _non_negative_float(
            self.outdoor_airflow_m3_h,
            "outdoor_airflow_m3_h",
            self.boundary_connection_id,
        )

    def has_airflow(self) -> bool:
        return self.outdoor_airflow_m3_h > 0.0

    def copy(self, **updates: Any) -> "WindowAirflowOpeningResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_connection_id": self.boundary_connection_id,
            "zone_id": self.zone_id,
            "is_open": self.is_open,
            "opening_fraction": self.opening_fraction,
            "max_opening_area_m2": self.max_opening_area_m2,
            "effective_opening_area_m2": self.effective_opening_area_m2,
            "discharge_coefficient": self.discharge_coefficient,
            "wind_speed_m_s": self.wind_speed_m_s,
            "wind_direction_deg": self.wind_direction_deg,
            "window_orientation_deg": self.window_orientation_deg,
            "wind_alignment_factor": self.wind_alignment_factor,
            "outdoor_airflow_m3_s": self.outdoor_airflow_m3_s,
            "outdoor_airflow_m3_h": self.outdoor_airflow_m3_h,
            "has_airflow": self.has_airflow(),
            "source": self.source,
        }
    
@dataclass
class BuildingWindowAirflowOpeningResult:
    """
    Window opening airflow potential for all windows.

    This result is intended to be consumed by airflow.py.
    """

    airflow_openings_by_window: Dict[str, WindowAirflowOpeningResult] = None

    source: str = WINDOW_AIRFLOW_OPENING_SOURCE

    def __post_init__(self) -> None:
        if self.airflow_openings_by_window is None:
            self.airflow_openings_by_window = {}

        cleaned = {}

        for window_id, result in self.airflow_openings_by_window.items():
            if not isinstance(result, WindowAirflowOpeningResult):
                raise TypeError(
                    "BuildingWindowAirflowOpeningResult.airflow_openings_by_window "
                    "must contain WindowAirflowOpeningResult objects."
                )

            if window_id != result.boundary_connection_id:
                raise ValueError(
                    "BuildingWindowAirflowOpeningResult key "
                    + window_id
                    + " does not match result.boundary_connection_id "
                    + result.boundary_connection_id
                )

            cleaned[window_id] = result

        self.airflow_openings_by_window = cleaned

    def window_ids(self) -> List[str]:
        return list(self.airflow_openings_by_window.keys())

    def get_result_for_window(
        self,
        boundary_connection_id: str,
    ) -> WindowAirflowOpeningResult:
        if boundary_connection_id not in self.airflow_openings_by_window:
            raise KeyError(
                "Window airflow opening result for "
                + boundary_connection_id
                + " not found."
            )

        return self.airflow_openings_by_window[boundary_connection_id]

    def results_for_zone(
        self,
        zone_id: str,
    ) -> List[WindowAirflowOpeningResult]:
        return [
            result
            for result in self.airflow_openings_by_window.values()
            if result.zone_id == zone_id
        ]

    def outdoor_airflow_by_window_m3_h(self) -> Dict[str, float]:
        return {
            window_id: result.outdoor_airflow_m3_h
            for window_id, result in self.airflow_openings_by_window.items()
        }

    def outdoor_airflow_by_zone_m3_h(self) -> Dict[str, float]:
        values = {}

        for result in self.airflow_openings_by_window.values():
            if result.zone_id not in values:
                values[result.zone_id] = 0.0

            values[result.zone_id] += result.outdoor_airflow_m3_h

        return values

    def effective_opening_area_by_window_m2(self) -> Dict[str, float]:
        return {
            window_id: result.effective_opening_area_m2
            for window_id, result in self.airflow_openings_by_window.items()
        }

    def wind_alignment_by_window(self) -> Dict[str, float]:
        return {
            window_id: result.wind_alignment_factor
            for window_id, result in self.airflow_openings_by_window.items()
        }

    def total_outdoor_airflow_m3_h(self) -> float:
        return sum(
            result.outdoor_airflow_m3_h
            for result in self.airflow_openings_by_window.values()
        )

    def copy(self, **updates: Any) -> "BuildingWindowAirflowOpeningResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outdoor_airflow_by_window_m3_h": self.outdoor_airflow_by_window_m3_h(),
            "outdoor_airflow_by_zone_m3_h": self.outdoor_airflow_by_zone_m3_h(),
            "effective_opening_area_by_window_m2": self.effective_opening_area_by_window_m2(),
            "wind_alignment_by_window": self.wind_alignment_by_window(),
            "total_outdoor_airflow_m3_h": self.total_outdoor_airflow_m3_h(),
            "airflow_openings_by_window": {
                window_id: result.to_dict()
                for window_id, result in self.airflow_openings_by_window.items()
            },
            "source": self.source,
        }

@dataclass
class WindowThermalConductanceResult:
    """
    Closed-window conductive heat exchange.

    Sign convention:
        heat_flow_to_zone_w > 0 means heat gain to the zone.
        heat_flow_to_zone_w < 0 means heat loss from the zone.

    Formula:
        heat_flow_to_zone_w = U * A * (T_outdoor - T_indoor)
    """

    boundary_connection_id: str
    zone_id: str

    area_m2: float
    window_u_value_w_m2k: float
    conductance_w_k: float

    indoor_temperature_c: float
    outdoor_temperature_c: float
    delta_t_outdoor_minus_indoor_k: float

    heat_flow_to_zone_w: float

    source: str = WINDOW_THERMAL_CONDUCTANCE_SOURCE

    def __post_init__(self) -> None:
        if not self.boundary_connection_id:
            raise ValueError(
                "WindowThermalConductanceResult.boundary_connection_id cannot be empty."
            )

        if not self.zone_id:
            raise ValueError("WindowThermalConductanceResult.zone_id cannot be empty.")

        self.area_m2 = _non_negative_float(
            self.area_m2,
            "area_m2",
            self.boundary_connection_id,
        )

        self.window_u_value_w_m2k = _non_negative_float(
            self.window_u_value_w_m2k,
            "window_u_value_w_m2k",
            self.boundary_connection_id,
        )

        self.conductance_w_k = _non_negative_float(
            self.conductance_w_k,
            "conductance_w_k",
            self.boundary_connection_id,
        )

        self.indoor_temperature_c = float(self.indoor_temperature_c)
        self.outdoor_temperature_c = float(self.outdoor_temperature_c)
        self.delta_t_outdoor_minus_indoor_k = float(
            self.delta_t_outdoor_minus_indoor_k
        )
        self.heat_flow_to_zone_w = float(self.heat_flow_to_zone_w)

    def copy(self, **updates: Any) -> "WindowThermalConductanceResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_connection_id": self.boundary_connection_id,
            "zone_id": self.zone_id,
            "area_m2": self.area_m2,
            "window_u_value_w_m2k": self.window_u_value_w_m2k,
            "conductance_w_k": self.conductance_w_k,
            "indoor_temperature_c": self.indoor_temperature_c,
            "outdoor_temperature_c": self.outdoor_temperature_c,
            "delta_t_outdoor_minus_indoor_k": self.delta_t_outdoor_minus_indoor_k,
            "heat_flow_to_zone_w": self.heat_flow_to_zone_w,
            "sign_convention": WINDOW_THERMAL_SIGN_CONVENTION,
            "source": self.source,
        }
 
@dataclass
class WindowOpeningThermalExchangeResult:
    """
    Opening-related ventilation heat exchange through a window.

    This class consumes airflow already calculated elsewhere.

    It does NOT calculate airflow.

    Sign convention:
        heat_flow_to_zone_w > 0 means heat gain to the zone.
        heat_flow_to_zone_w < 0 means heat loss from the zone.

    Formula:
        q_heat_w = rho_air * cp_air * airflow_m3_s * (T_outdoor - T_indoor)
    """

    boundary_connection_id: str
    zone_id: str

    outdoor_airflow_m3_h: float
    outdoor_airflow_m3_s: float

    indoor_temperature_c: float
    outdoor_temperature_c: float
    delta_t_outdoor_minus_indoor_k: float

    equivalent_ventilation_conductance_w_k: float
    heat_flow_to_zone_w: float

    source: str = WINDOW_OPENING_THERMAL_EXCHANGE_SOURCE

    def __post_init__(self) -> None:
        if not self.boundary_connection_id:
            raise ValueError(
                "WindowOpeningThermalExchangeResult.boundary_connection_id cannot be empty."
            )

        if not self.zone_id:
            raise ValueError(
                "WindowOpeningThermalExchangeResult.zone_id cannot be empty."
            )

        self.outdoor_airflow_m3_h = _non_negative_float(
            self.outdoor_airflow_m3_h,
            "outdoor_airflow_m3_h",
            self.boundary_connection_id,
        )

        self.outdoor_airflow_m3_s = _non_negative_float(
            self.outdoor_airflow_m3_s,
            "outdoor_airflow_m3_s",
            self.boundary_connection_id,
        )

        self.indoor_temperature_c = float(self.indoor_temperature_c)
        self.outdoor_temperature_c = float(self.outdoor_temperature_c)
        self.delta_t_outdoor_minus_indoor_k = float(
            self.delta_t_outdoor_minus_indoor_k
        )

        self.equivalent_ventilation_conductance_w_k = _non_negative_float(
            self.equivalent_ventilation_conductance_w_k,
            "equivalent_ventilation_conductance_w_k",
            self.boundary_connection_id,
        )

        self.heat_flow_to_zone_w = float(self.heat_flow_to_zone_w)

    def has_exchange(self) -> bool:
        return self.outdoor_airflow_m3_h > 0.0

    def copy(self, **updates: Any) -> "WindowOpeningThermalExchangeResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_connection_id": self.boundary_connection_id,
            "zone_id": self.zone_id,
            "outdoor_airflow_m3_h": self.outdoor_airflow_m3_h,
            "outdoor_airflow_m3_s": self.outdoor_airflow_m3_s,
            "indoor_temperature_c": self.indoor_temperature_c,
            "outdoor_temperature_c": self.outdoor_temperature_c,
            "delta_t_outdoor_minus_indoor_k": self.delta_t_outdoor_minus_indoor_k,
            "equivalent_ventilation_conductance_w_k": self.equivalent_ventilation_conductance_w_k,
            "heat_flow_to_zone_w": self.heat_flow_to_zone_w,
            "has_exchange": self.has_exchange(),
            "sign_convention": WINDOW_THERMAL_SIGN_CONVENTION,
            "source": self.source,
        }
    
@dataclass
class BuildingWindowThermalConductanceResult:
    """
    Closed-window conductive heat exchange for all windows.
    """

    conductance_results_by_window: Dict[str, WindowThermalConductanceResult] = None

    source: str = WINDOW_THERMAL_CONDUCTANCE_SOURCE

    def __post_init__(self) -> None:
        if self.conductance_results_by_window is None:
            self.conductance_results_by_window = {}

        cleaned = {}

        for window_id, result in self.conductance_results_by_window.items():
            if not isinstance(result, WindowThermalConductanceResult):
                raise TypeError(
                    "conductance_results_by_window must contain "
                    "WindowThermalConductanceResult objects."
                )

            if window_id != result.boundary_connection_id:
                raise ValueError(
                    "BuildingWindowThermalConductanceResult key "
                    + window_id
                    + " does not match result.boundary_connection_id "
                    + result.boundary_connection_id
                )

            cleaned[window_id] = result

        self.conductance_results_by_window = cleaned

    def heat_flow_by_window_w(self) -> Dict[str, float]:
        return {
            window_id: result.heat_flow_to_zone_w
            for window_id, result in self.conductance_results_by_window.items()
        }

    def heat_flow_by_zone_w(self) -> Dict[str, float]:
        values = {}

        for result in self.conductance_results_by_window.values():
            if result.zone_id not in values:
                values[result.zone_id] = 0.0

            values[result.zone_id] += result.heat_flow_to_zone_w

        return values

    def conductance_by_zone_w_k(self) -> Dict[str, float]:
        values = {}

        for result in self.conductance_results_by_window.values():
            if result.zone_id not in values:
                values[result.zone_id] = 0.0

            values[result.zone_id] += result.conductance_w_k

        return values

    def total_heat_flow_w(self) -> float:
        return sum(
            result.heat_flow_to_zone_w
            for result in self.conductance_results_by_window.values()
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "heat_flow_by_window_w": self.heat_flow_by_window_w(),
            "heat_flow_by_zone_w": self.heat_flow_by_zone_w(),
            "conductance_by_zone_w_k": self.conductance_by_zone_w_k(),
            "total_heat_flow_w": self.total_heat_flow_w(),
            "conductance_results_by_window": {
                window_id: result.to_dict()
                for window_id, result in self.conductance_results_by_window.items()
            },
            "source": self.source,
        }


@dataclass
class BuildingWindowOpeningThermalExchangeResult:
    """
    Opening-related ventilation heat exchange for all windows.

    This object consumes airflow results.
    It does not calculate airflow.
    """

    exchange_results_by_window: Dict[str, WindowOpeningThermalExchangeResult] = None

    source: str = WINDOW_OPENING_THERMAL_EXCHANGE_SOURCE

    def __post_init__(self) -> None:
        if self.exchange_results_by_window is None:
            self.exchange_results_by_window = {}

        cleaned = {}

        for window_id, result in self.exchange_results_by_window.items():
            if not isinstance(result, WindowOpeningThermalExchangeResult):
                raise TypeError(
                    "exchange_results_by_window must contain "
                    "WindowOpeningThermalExchangeResult objects."
                )

            if window_id != result.boundary_connection_id:
                raise ValueError(
                    "BuildingWindowOpeningThermalExchangeResult key "
                    + window_id
                    + " does not match result.boundary_connection_id "
                    + result.boundary_connection_id
                )

            cleaned[window_id] = result

        self.exchange_results_by_window = cleaned

    def heat_flow_by_window_w(self) -> Dict[str, float]:
        return {
            window_id: result.heat_flow_to_zone_w
            for window_id, result in self.exchange_results_by_window.items()
        }

    def heat_flow_by_zone_w(self) -> Dict[str, float]:
        values = {}

        for result in self.exchange_results_by_window.values():
            if result.zone_id not in values:
                values[result.zone_id] = 0.0

            values[result.zone_id] += result.heat_flow_to_zone_w

        return values

    def equivalent_ventilation_conductance_by_zone_w_k(self) -> Dict[str, float]:
        values = {}

        for result in self.exchange_results_by_window.values():
            if result.zone_id not in values:
                values[result.zone_id] = 0.0

            values[result.zone_id] += result.equivalent_ventilation_conductance_w_k

        return values

    def total_heat_flow_w(self) -> float:
        return sum(
            result.heat_flow_to_zone_w
            for result in self.exchange_results_by_window.values()
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "heat_flow_by_window_w": self.heat_flow_by_window_w(),
            "heat_flow_by_zone_w": self.heat_flow_by_zone_w(),
            "equivalent_ventilation_conductance_by_zone_w_k": self.equivalent_ventilation_conductance_by_zone_w_k(),
            "total_heat_flow_w": self.total_heat_flow_w(),
            "exchange_results_by_window": {
                window_id: result.to_dict()
                for window_id, result in self.exchange_results_by_window.items()
            },
            "source": self.source,
        }
    
@dataclass
class WindowSolarExposureResult:
    """
    Simplified solar/daylight directional exposure for one window.

    Used by:
    - thermal solar gains
    - daylight estimate

    This is not full solar geometry.
    """

    boundary_connection_id: str
    zone_id: str

    window_orientation_deg: float
    window_orientation_label: str

    solar_azimuth_deg: Optional[float]
    solar_altitude_deg: Optional[float]
    has_solar_direction: bool

    sky_condition: str

    outdoor_illuminance_lux: float
    direct_normal_radiation_w_m2: float
    diffuse_horizontal_radiation_w_m2: float
    global_horizontal_radiation_w_m2: float

    sky_condition_fallback_factor: float

    solar_alignment_factor: float
    daylight_alignment_factor: float

    solar_exposure_factor: float
    daylight_exposure_factor: float

    source: str = WINDOW_SOLAR_EXPOSURE_SOURCE

    def __post_init__(self) -> None:
        if not self.boundary_connection_id:
            raise ValueError(
                "WindowSolarExposureResult.boundary_connection_id cannot be empty."
            )

        if not self.zone_id:
            raise ValueError("WindowSolarExposureResult.zone_id cannot be empty.")

        self.window_orientation_deg = normalize_orientation_deg(
            self.window_orientation_deg
        )

        self.window_orientation_label = str(
            self.window_orientation_label
        ).strip().lower()

        if self.solar_azimuth_deg is not None:
            self.solar_azimuth_deg = normalize_orientation_deg(
                self.solar_azimuth_deg
            )

        if self.solar_altitude_deg is not None:
            self.solar_altitude_deg = float(self.solar_altitude_deg)

        self.has_solar_direction = bool(self.has_solar_direction)

        self.sky_condition = str(self.sky_condition).strip().lower()

        if not self.sky_condition:
            self.sky_condition = DEFAULT_SKY_CONDITION

        self.outdoor_illuminance_lux = _non_negative_float(
            self.outdoor_illuminance_lux,
            "outdoor_illuminance_lux",
            self.boundary_connection_id,
        )

        self.direct_normal_radiation_w_m2 = _non_negative_float(
            self.direct_normal_radiation_w_m2,
            "direct_normal_radiation_w_m2",
            self.boundary_connection_id,
        )

        self.diffuse_horizontal_radiation_w_m2 = _non_negative_float(
            self.diffuse_horizontal_radiation_w_m2,
            "diffuse_horizontal_radiation_w_m2",
            self.boundary_connection_id,
        )

        self.global_horizontal_radiation_w_m2 = _non_negative_float(
            self.global_horizontal_radiation_w_m2,
            "global_horizontal_radiation_w_m2",
            self.boundary_connection_id,
        )

        self.sky_condition_fallback_factor = _clamp_unit_interval(
            self.sky_condition_fallback_factor
        )

        self.solar_alignment_factor = _clamp_unit_interval(
            self.solar_alignment_factor
        )

        self.daylight_alignment_factor = _clamp_unit_interval(
            self.daylight_alignment_factor
        )

        self.solar_exposure_factor = _clamp_unit_interval(
            self.solar_exposure_factor
        )

        self.daylight_exposure_factor = _clamp_unit_interval(
            self.daylight_exposure_factor
        )

    def has_outdoor_light(self) -> bool:
        return (
            self.outdoor_illuminance_lux > 0.0
            or self.direct_normal_radiation_w_m2 > 0.0
            or self.diffuse_horizontal_radiation_w_m2 > 0.0
            or self.global_horizontal_radiation_w_m2 > 0.0
        )

    def copy(self, **updates: Any) -> "WindowSolarExposureResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_connection_id": self.boundary_connection_id,
            "zone_id": self.zone_id,
            "window_orientation_deg": self.window_orientation_deg,
            "window_orientation_label": self.window_orientation_label,
            "solar_azimuth_deg": self.solar_azimuth_deg,
            "solar_altitude_deg": self.solar_altitude_deg,
            "has_solar_direction": self.has_solar_direction,
            "sky_condition": self.sky_condition,
            "outdoor_illuminance_lux": self.outdoor_illuminance_lux,
            "direct_normal_radiation_w_m2": self.direct_normal_radiation_w_m2,
            "diffuse_horizontal_radiation_w_m2": self.diffuse_horizontal_radiation_w_m2,
            "global_horizontal_radiation_w_m2": self.global_horizontal_radiation_w_m2,
            "sky_condition_fallback_factor": self.sky_condition_fallback_factor,
            "solar_alignment_factor": self.solar_alignment_factor,
            "daylight_alignment_factor": self.daylight_alignment_factor,
            "solar_exposure_factor": self.solar_exposure_factor,
            "daylight_exposure_factor": self.daylight_exposure_factor,
            "has_outdoor_light": self.has_outdoor_light(),
            "source": self.source,
        }
    
@dataclass
class BuildingWindowSolarExposureResult:
    """
    Solar/daylight directional exposure for all windows.
    """

    exposures_by_window: Dict[str, WindowSolarExposureResult] = None

    source: str = WINDOW_SOLAR_EXPOSURE_SOURCE

    def __post_init__(self) -> None:
        if self.exposures_by_window is None:
            self.exposures_by_window = {}

        cleaned = {}

        for window_id, exposure in self.exposures_by_window.items():
            if not isinstance(exposure, WindowSolarExposureResult):
                raise TypeError(
                    "BuildingWindowSolarExposureResult.exposures_by_window "
                    "must contain WindowSolarExposureResult objects."
                )

            if window_id != exposure.boundary_connection_id:
                raise ValueError(
                    "BuildingWindowSolarExposureResult key "
                    + window_id
                    + " does not match exposure.boundary_connection_id "
                    + exposure.boundary_connection_id
                )

            cleaned[window_id] = exposure

        self.exposures_by_window = cleaned

    def window_ids(self) -> List[str]:
        return list(self.exposures_by_window.keys())

    def get_exposure_for_window(
        self,
        boundary_connection_id: str,
    ) -> WindowSolarExposureResult:
        if boundary_connection_id not in self.exposures_by_window:
            raise KeyError(
                "Window solar exposure for "
                + boundary_connection_id
                + " not found."
            )

        return self.exposures_by_window[boundary_connection_id]

    def exposures_for_zone(
        self,
        zone_id: str,
    ) -> List[WindowSolarExposureResult]:
        return [
            exposure
            for exposure in self.exposures_by_window.values()
            if exposure.zone_id == zone_id
        ]

    def solar_exposure_factor_by_window(self) -> Dict[str, float]:
        return {
            window_id: exposure.solar_exposure_factor
            for window_id, exposure in self.exposures_by_window.items()
        }

    def daylight_exposure_factor_by_window(self) -> Dict[str, float]:
        return {
            window_id: exposure.daylight_exposure_factor
            for window_id, exposure in self.exposures_by_window.items()
        }

    def solar_alignment_factor_by_window(self) -> Dict[str, float]:
        return {
            window_id: exposure.solar_alignment_factor
            for window_id, exposure in self.exposures_by_window.items()
        }

    def daylight_alignment_factor_by_window(self) -> Dict[str, float]:
        return {
            window_id: exposure.daylight_alignment_factor
            for window_id, exposure in self.exposures_by_window.items()
        }

    def copy(self, **updates: Any) -> "BuildingWindowSolarExposureResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "solar_exposure_factor_by_window": self.solar_exposure_factor_by_window(),
            "daylight_exposure_factor_by_window": self.daylight_exposure_factor_by_window(),
            "solar_alignment_factor_by_window": self.solar_alignment_factor_by_window(),
            "daylight_alignment_factor_by_window": self.daylight_alignment_factor_by_window(),
            "exposures_by_window": {
                window_id: exposure.to_dict()
                for window_id, exposure in self.exposures_by_window.items()
            },
            "source": self.source,
        }
    

@dataclass
class WindowBoundaryResult:
    """
    Shared timestep-level window boundary result.

    This is the object that thermal, airflow, moisture/CO2 through airflow,
    and daylight should read.

    It combines:
    - static window parameters
    - dynamic operation state
    - curtain/blind effects
    - airflow opening result
    - solar/daylight directional exposure
    """

    boundary_connection_id: str
    zone_id: str

    orientation_deg: float
    orientation_label: str
    area_m2: float

    effective_visible_transmittance: float
    effective_solar_factor: float
    effective_u_value_w_m2k: float

    opening_fraction: float
    airflow_opening_area_m2: float

    wind_alignment_factor: float
    solar_alignment_factor: float
    daylight_alignment_factor: float

    outdoor_airflow_m3_h: float = 0.0
    closed_window_conductance_w_k: float = 0.0

    curtain_open: bool = True
    blind_open: bool = True
    blind_fraction: float = 0.0

    source: str = WINDOW_BOUNDARY_RESULT_SOURCE

    def __post_init__(self) -> None:
        if not self.boundary_connection_id:
            raise ValueError(
                "WindowBoundaryResult.boundary_connection_id cannot be empty."
            )

        if not self.zone_id:
            raise ValueError("WindowBoundaryResult.zone_id cannot be empty.")

        self.orientation_deg = normalize_orientation_deg(
            self.orientation_deg
        )

        self.orientation_label = str(
            self.orientation_label
        ).strip().lower()

        self.area_m2 = _non_negative_float(
            self.area_m2,
            "area_m2",
            self.boundary_connection_id,
        )

        self.effective_visible_transmittance = _clamp_unit_interval(
            self.effective_visible_transmittance
        )

        self.effective_solar_factor = _clamp_unit_interval(
            self.effective_solar_factor
        )

        self.effective_u_value_w_m2k = _non_negative_float(
            self.effective_u_value_w_m2k,
            "effective_u_value_w_m2k",
            self.boundary_connection_id,
        )

        self.opening_fraction = _clamp_unit_interval(
            self.opening_fraction
        )

        self.airflow_opening_area_m2 = _non_negative_float(
            self.airflow_opening_area_m2,
            "airflow_opening_area_m2",
            self.boundary_connection_id,
        )

        self.wind_alignment_factor = _clamp_unit_interval(
            self.wind_alignment_factor
        )

        self.solar_alignment_factor = _clamp_unit_interval(
            self.solar_alignment_factor
        )

        self.daylight_alignment_factor = _clamp_unit_interval(
            self.daylight_alignment_factor
        )

        self.outdoor_airflow_m3_h = _non_negative_float(
            self.outdoor_airflow_m3_h,
            "outdoor_airflow_m3_h",
            self.boundary_connection_id,
        )

        self.closed_window_conductance_w_k = _non_negative_float(
            self.closed_window_conductance_w_k,
            "closed_window_conductance_w_k",
            self.boundary_connection_id,
        )

        self.curtain_open = bool(self.curtain_open)
        self.blind_open = bool(self.blind_open)

        self.blind_fraction = _clamp_unit_interval(
            self.blind_fraction
        )

    def effective_daylight_area_m2(self) -> float:
        return (
            self.area_m2
            * self.effective_visible_transmittance
        )

    def effective_solar_area_m2(self) -> float:
        return (
            self.area_m2
            * self.effective_solar_factor
        )

    def has_airflow_opening(self) -> bool:
        return (
            self.opening_fraction > 0.0
            and self.airflow_opening_area_m2 > 0.0
        )

    def copy(self, **updates: Any) -> "WindowBoundaryResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_connection_id": self.boundary_connection_id,

            "window_id": self.boundary_connection_id,

            "zone_id": self.zone_id,
            "orientation_deg": self.orientation_deg,
            "orientation_label": self.orientation_label,
            "area_m2": self.area_m2,
            "effective_visible_transmittance": self.effective_visible_transmittance,
            "effective_solar_factor": self.effective_solar_factor,
            "effective_u_value_w_m2k": self.effective_u_value_w_m2k,
            "opening_fraction": self.opening_fraction,
            "airflow_opening_area_m2": self.airflow_opening_area_m2,
            "wind_alignment_factor": self.wind_alignment_factor,
            "solar_alignment_factor": self.solar_alignment_factor,
            "daylight_alignment_factor": self.daylight_alignment_factor,
            "outdoor_airflow_m3_h": self.outdoor_airflow_m3_h,
            "closed_window_conductance_w_k": self.closed_window_conductance_w_k,
            "curtain_open": self.curtain_open,
            "blind_open": self.blind_open,
            "blind_fraction": self.blind_fraction,
            "effective_daylight_area_m2": self.effective_daylight_area_m2(),
            "effective_solar_area_m2": self.effective_solar_area_m2(),
            "has_airflow_opening": self.has_airflow_opening(),
            "source": self.source,
        }
    
@dataclass
class BuildingWindowBoundaryResult:
    """
    Shared timestep-level window boundary result for the whole building.

    This is the cross-physics output of Phase 8.
    """

    window_results_by_id: Dict[str, WindowBoundaryResult] = None

    source: str = WINDOW_BOUNDARY_RESULT_SOURCE
    interface_mode: str = WINDOW_BOUNDARY_RESULT_INTERFACE_MODE

    def __post_init__(self) -> None:
        if self.window_results_by_id is None:
            self.window_results_by_id = {}

        cleaned = {}

        for window_id, result in self.window_results_by_id.items():
            if not isinstance(result, WindowBoundaryResult):
                raise TypeError(
                    "BuildingWindowBoundaryResult.window_results_by_id "
                    "must contain WindowBoundaryResult objects."
                )

            if window_id != result.boundary_connection_id:
                raise ValueError(
                    "BuildingWindowBoundaryResult key "
                    + window_id
                    + " does not match result.boundary_connection_id "
                    + result.boundary_connection_id
                )

            cleaned[window_id] = result

        self.window_results_by_id = cleaned

    def window_ids(self) -> List[str]:
        return list(self.window_results_by_id.keys())

    def zone_ids(self) -> List[str]:
        zone_ids = []

        for result in self.window_results_by_id.values():
            if result.zone_id not in zone_ids:
                zone_ids.append(result.zone_id)

        return zone_ids

    def get_window_result(
        self,
        boundary_connection_id: str,
    ) -> WindowBoundaryResult:
        if boundary_connection_id not in self.window_results_by_id:
            raise KeyError(
                "Window boundary result for "
                + boundary_connection_id
                + " not found."
            )

        return self.window_results_by_id[boundary_connection_id]

    def window_results_for_zone(
        self,
        zone_id: str,
    ) -> List[WindowBoundaryResult]:
        return [
            result
            for result in self.window_results_by_id.values()
            if result.zone_id == zone_id
        ]

    def effective_visible_transmittance_by_window(self) -> Dict[str, float]:
        return {
            window_id: result.effective_visible_transmittance
            for window_id, result in self.window_results_by_id.items()
        }

    def effective_solar_factor_by_window(self) -> Dict[str, float]:
        return {
            window_id: result.effective_solar_factor
            for window_id, result in self.window_results_by_id.items()
        }

    def effective_u_value_by_window_w_m2k(self) -> Dict[str, float]:
        return {
            window_id: result.effective_u_value_w_m2k
            for window_id, result in self.window_results_by_id.items()
        }

    def opening_fraction_by_window(self) -> Dict[str, float]:
        return {
            window_id: result.opening_fraction
            for window_id, result in self.window_results_by_id.items()
        }

    def airflow_opening_area_by_window_m2(self) -> Dict[str, float]:
        return {
            window_id: result.airflow_opening_area_m2
            for window_id, result in self.window_results_by_id.items()
        }

    def wind_alignment_factor_by_window(self) -> Dict[str, float]:
        return {
            window_id: result.wind_alignment_factor
            for window_id, result in self.window_results_by_id.items()
        }

    def solar_alignment_factor_by_window(self) -> Dict[str, float]:
        return {
            window_id: result.solar_alignment_factor
            for window_id, result in self.window_results_by_id.items()
        }

    def daylight_alignment_factor_by_window(self) -> Dict[str, float]:
        return {
            window_id: result.daylight_alignment_factor
            for window_id, result in self.window_results_by_id.items()
        }

    def outdoor_airflow_by_zone_m3_h(self) -> Dict[str, float]:
        values = {}

        for result in self.window_results_by_id.values():
            if result.zone_id not in values:
                values[result.zone_id] = 0.0

            values[result.zone_id] += result.outdoor_airflow_m3_h

        return values

    def closed_window_conductance_by_zone_w_k(self) -> Dict[str, float]:
        values = {}

        for result in self.window_results_by_id.values():
            if result.zone_id not in values:
                values[result.zone_id] = 0.0

            values[result.zone_id] += result.closed_window_conductance_w_k

        return values

    def effective_daylight_area_by_zone_m2(self) -> Dict[str, float]:
        values = {}

        for result in self.window_results_by_id.values():
            if result.zone_id not in values:
                values[result.zone_id] = 0.0

            values[result.zone_id] += result.effective_daylight_area_m2()

        return values

    def effective_solar_area_by_zone_m2(self) -> Dict[str, float]:
        values = {}

        for result in self.window_results_by_id.values():
            if result.zone_id not in values:
                values[result.zone_id] = 0.0

            values[result.zone_id] += result.effective_solar_area_m2()

        return values

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_ids": self.window_ids(),
            "zone_ids": self.zone_ids(),
            "effective_visible_transmittance_by_window": self.effective_visible_transmittance_by_window(),
            "effective_solar_factor_by_window": self.effective_solar_factor_by_window(),
            "effective_u_value_by_window_w_m2k": self.effective_u_value_by_window_w_m2k(),
            "opening_fraction_by_window": self.opening_fraction_by_window(),
            "airflow_opening_area_by_window_m2": self.airflow_opening_area_by_window_m2(),
            "wind_alignment_factor_by_window": self.wind_alignment_factor_by_window(),
            "solar_alignment_factor_by_window": self.solar_alignment_factor_by_window(),
            "daylight_alignment_factor_by_window": self.daylight_alignment_factor_by_window(),
            "outdoor_airflow_by_zone_m3_h": self.outdoor_airflow_by_zone_m3_h(),
            "closed_window_conductance_by_zone_w_k": self.closed_window_conductance_by_zone_w_k(),
            "effective_daylight_area_by_zone_m2": self.effective_daylight_area_by_zone_m2(),
            "effective_solar_area_by_zone_m2": self.effective_solar_area_by_zone_m2(),
            "window_results_by_id": {
                window_id: result.to_dict()
                for window_id, result in self.window_results_by_id.items()
            },
            "source": self.source,
            "interface_mode": self.interface_mode,
        }
    

    
DEFAULT_WINDOW_ARCHITECTURE = WindowArchitectureDecision()

#%% functions

def make_default_window_architecture() -> WindowArchitectureDecision:
    return WindowArchitectureDecision()

def make_window_static_parameters_from_boundary_connection(
    boundary_connection: Any,
) -> WindowStaticParameters:
    """
    Extract static window parameters from a BoundaryConnection-like object.

    Expected:
    - connection_id or boundary_connection_id
    - zone_id
    - connection_type = window
    - orientation_deg
    - area_m2

    Optional:
    - window_u_value_w_m2k
    - glazing_transmittance
    - window_visible_transmittance
    - solar_heat_gain_coefficient
    - frame_fraction
    - shading_factor
    - max_opening_area_m2
    - discharge_coefficient
    """

    if boundary_connection is None:
        raise ValueError("boundary_connection cannot be None.")

    if not is_window_boundary_connection(boundary_connection):
        raise ValueError(
            "boundary_connection is not a window boundary connection."
        )

    boundary_connection_id = _first_existing_attr_or_default(
        boundary_connection,
        [
            "connection_id",
            "boundary_connection_id",
        ],
        "",
    )

    if not boundary_connection_id:
        raise ValueError(
            "Window BoundaryConnection must provide connection_id."
        )

    zone_id = _required_attr(
        boundary_connection,
        "zone_id",
    )

    orientation_deg = _required_attr(
        boundary_connection,
        "orientation_deg",
    )

    area_m2 = _get_attr_or_default(
        boundary_connection,
        "area_m2",
        DEFAULT_WINDOW_AREA_M2,
    )

    window_u_value_w_m2k = _first_existing_attr_or_default(
        boundary_connection,
        [
            "window_u_value_w_m2k",
            "u_value_w_m2k",
            "u_value",
        ],
        DEFAULT_WINDOW_U_VALUE_W_M2K,
    )

    glazing_transmittance = _first_existing_attr_or_default(
        boundary_connection,
        [
            "glazing_transmittance",
            "window_glazing_transmittance",
            "transmittance",
        ],
        DEFAULT_GLAZING_TRANSMITTANCE,
    )

    window_visible_transmittance = _first_existing_attr_or_default(
        boundary_connection,
        [
            "window_visible_transmittance",
            "visible_transmittance",
            "glazing_visible_transmittance",
        ],
        DEFAULT_WINDOW_VISIBLE_TRANSMITTANCE,
    )

    solar_heat_gain_coefficient = _first_existing_attr_or_default(
        boundary_connection,
        [
            "solar_heat_gain_coefficient",
            "shgc",
            "window_shgc",
        ],
        DEFAULT_SOLAR_HEAT_GAIN_COEFFICIENT,
    )

    frame_fraction = _get_attr_or_default(
        boundary_connection,
        "frame_fraction",
        DEFAULT_WINDOW_FRAME_FRACTION,
    )

    shading_factor = _get_attr_or_default(
        boundary_connection,
        "shading_factor",
        DEFAULT_WINDOW_SHADING_FACTOR,
    )

    max_opening_area_m2 = _get_attr_or_default(
        boundary_connection,
        "max_opening_area_m2",
        DEFAULT_WINDOW_MAX_OPENING_AREA_M2,
    )

    discharge_coefficient = _get_attr_or_default(
        boundary_connection,
        "discharge_coefficient",
        DEFAULT_WINDOW_DISCHARGE_COEFFICIENT,
    )

    return WindowStaticParameters(
        boundary_connection_id=boundary_connection_id,
        zone_id=zone_id,
        orientation_deg=orientation_deg,
        area_m2=area_m2,
        window_u_value_w_m2k=window_u_value_w_m2k,
        glazing_transmittance=glazing_transmittance,
        window_visible_transmittance=window_visible_transmittance,
        solar_heat_gain_coefficient=solar_heat_gain_coefficient,
        frame_fraction=frame_fraction,
        shading_factor=shading_factor,
        max_opening_area_m2=max_opening_area_m2,
        discharge_coefficient=discharge_coefficient,
        source=WINDOW_STATIC_PARAMETER_SOURCE,
    )

def make_window_boundary_result(
    window_static_parameters: WindowStaticParameters,
    window_operation_state: WindowOperationState,
    covering_effect_result: WindowCoveringEffectResult,
    airflow_opening_result: WindowAirflowOpeningResult,
    solar_exposure_result: WindowSolarExposureResult,
) -> WindowBoundaryResult:
    """
    Combine all Phase 8 window sub-results into one shared result.
    """

    if not isinstance(window_static_parameters, WindowStaticParameters):
        raise TypeError(
            "window_static_parameters must be WindowStaticParameters."
        )

    if not isinstance(window_operation_state, WindowOperationState):
        raise TypeError(
            "window_operation_state must be WindowOperationState."
        )

    if not isinstance(covering_effect_result, WindowCoveringEffectResult):
        raise TypeError(
            "covering_effect_result must be WindowCoveringEffectResult."
        )

    if not isinstance(airflow_opening_result, WindowAirflowOpeningResult):
        raise TypeError(
            "airflow_opening_result must be WindowAirflowOpeningResult."
        )

    if not isinstance(solar_exposure_result, WindowSolarExposureResult):
        raise TypeError(
            "solar_exposure_result must be WindowSolarExposureResult."
        )

    window_id = window_static_parameters.boundary_connection_id

    for other_id in [
        window_operation_state.boundary_connection_id,
        covering_effect_result.boundary_connection_id,
        airflow_opening_result.boundary_connection_id,
        solar_exposure_result.boundary_connection_id,
    ]:
        if other_id != window_id:
            raise ValueError(
                "Window sub-results do not refer to the same window."
            )

    effective_visible_transmittance = (
        covering_effect_result.effective_visible_transmittance
        * solar_exposure_result.daylight_exposure_factor
    )

    effective_solar_factor = (
        covering_effect_result.effective_solar_transmittance
        * solar_exposure_result.solar_exposure_factor
    )

    effective_visible_transmittance = _clamp_unit_interval(
        effective_visible_transmittance
    )

    effective_solar_factor = _clamp_unit_interval(
        effective_solar_factor
    )

    effective_u_value_w_m2k = window_static_parameters.window_u_value_w_m2k

    return WindowBoundaryResult(
        boundary_connection_id=window_id,
        zone_id=window_static_parameters.zone_id,
        orientation_deg=window_static_parameters.orientation_deg,
        orientation_label=orientation_label(
            window_static_parameters.orientation_deg
        ),
        area_m2=window_static_parameters.area_m2,
        effective_visible_transmittance=effective_visible_transmittance,
        effective_solar_factor=effective_solar_factor,
        effective_u_value_w_m2k=effective_u_value_w_m2k,
        opening_fraction=window_operation_state.opening_fraction,
        airflow_opening_area_m2=airflow_opening_result.effective_opening_area_m2,
        wind_alignment_factor=airflow_opening_result.wind_alignment_factor,
        solar_alignment_factor=solar_exposure_result.solar_alignment_factor,
        daylight_alignment_factor=solar_exposure_result.daylight_alignment_factor,
        outdoor_airflow_m3_h=airflow_opening_result.outdoor_airflow_m3_h,
        closed_window_conductance_w_k=window_static_parameters.closed_window_conductance_w_k(),
        curtain_open=window_operation_state.curtain_open,
        blind_open=window_operation_state.blind_open,
        blind_fraction=window_operation_state.blind_fraction,
        source=WINDOW_BOUNDARY_RESULT_SOURCE,
    )

def make_building_window_static_parameters(
    physics_graph: Any,
    building_model: Any = None,
) -> BuildingWindowStaticParameters:
    """
    Extract all static window parameters from BuildingPhysicsGraph.

    building_model is optional. If provided, all zones are initialized even
    when they have no windows.
    """

    if physics_graph is None:
        raise ValueError("physics_graph cannot be None.")

    if not hasattr(physics_graph, "boundary_connections"):
        raise TypeError(
            "physics_graph must provide boundary_connections."
        )

    zone_window_parameters = {}

    if building_model is not None:
        if not hasattr(building_model, "all_zone_models"):
            raise TypeError(
                "building_model must provide all_zone_models()."
            )

        for zone_id in building_model.all_zone_models().keys():
            zone_window_parameters[zone_id] = ZoneWindowStaticParameters(
                zone_id=zone_id,
                windows=[],
            )

    for boundary_connection in physics_graph.boundary_connections.values():
        if not is_window_boundary_connection(boundary_connection):
            continue

        window_parameters = make_window_static_parameters_from_boundary_connection(
            boundary_connection
        )

        zone_id = window_parameters.zone_id

        if zone_id not in zone_window_parameters:
            zone_window_parameters[zone_id] = ZoneWindowStaticParameters(
                zone_id=zone_id,
                windows=[],
            )

        zone_window_parameters[zone_id].add_window(
            window_parameters
        )

    return BuildingWindowStaticParameters(
        zone_window_parameters=zone_window_parameters,
    )

def make_building_window_boundary_result(
    building_window_static_parameters: BuildingWindowStaticParameters,
    building_window_operation_state: BuildingWindowOperationState,
    building_window_covering_effect_result: BuildingWindowCoveringEffectResult,
    building_window_airflow_opening_result: BuildingWindowAirflowOpeningResult,
    building_window_solar_exposure_result: BuildingWindowSolarExposureResult,
) -> BuildingWindowBoundaryResult:
    """
    Build shared cross-physics window boundary result.
    """

    if not isinstance(building_window_static_parameters, BuildingWindowStaticParameters):
        raise TypeError(
            "building_window_static_parameters must be BuildingWindowStaticParameters."
        )

    if not isinstance(building_window_operation_state, BuildingWindowOperationState):
        raise TypeError(
            "building_window_operation_state must be BuildingWindowOperationState."
        )

    if not isinstance(building_window_covering_effect_result, BuildingWindowCoveringEffectResult):
        raise TypeError(
            "building_window_covering_effect_result must be BuildingWindowCoveringEffectResult."
        )

    if not isinstance(building_window_airflow_opening_result, BuildingWindowAirflowOpeningResult):
        raise TypeError(
            "building_window_airflow_opening_result must be BuildingWindowAirflowOpeningResult."
        )

    if not isinstance(building_window_solar_exposure_result, BuildingWindowSolarExposureResult):
        raise TypeError(
            "building_window_solar_exposure_result must be BuildingWindowSolarExposureResult."
        )

    window_results_by_id = {}

    for zone_parameters in building_window_static_parameters.zone_window_parameters.values():
        for window_static_parameters in zone_parameters.windows:
            window_id = window_static_parameters.boundary_connection_id

            window_result = make_window_boundary_result(
                window_static_parameters=window_static_parameters,
                window_operation_state=building_window_operation_state.get_state_for_window(
                    window_id
                ),
                covering_effect_result=building_window_covering_effect_result.get_effect_for_window(
                    window_id
                ),
                airflow_opening_result=building_window_airflow_opening_result.get_result_for_window(
                    window_id
                ),
                solar_exposure_result=building_window_solar_exposure_result.get_exposure_for_window(
                    window_id
                ),
            )

            window_results_by_id[window_id] = window_result

    return BuildingWindowBoundaryResult(
        window_results_by_id=window_results_by_id,
        source=WINDOW_BOUNDARY_RESULT_SOURCE,
        interface_mode=WINDOW_BOUNDARY_RESULT_INTERFACE_MODE,
    )

def make_empty_window_operation_inputs() -> BuildingWindowOperationInputs:
    return BuildingWindowOperationInputs(
        operation_inputs_by_window={},
        source=WINDOW_OPERATION_INPUT_SOURCE,
    )


def make_window_operation_state(
    window_static_parameters: WindowStaticParameters,
    operation_input: ZoneWindowOperationInput = None,
) -> WindowOperationState:
    """
    Build normalized WindowOperationState for one window.

    If no operation input is provided:
        window closed
        curtain open
        blind open
    """

    if not isinstance(window_static_parameters, WindowStaticParameters):
        raise TypeError(
            "window_static_parameters must be WindowStaticParameters."
        )

    if operation_input is None:
        operation_input = ZoneWindowOperationInput(
            boundary_connection_id=window_static_parameters.boundary_connection_id,
            zone_id=window_static_parameters.zone_id,
            is_open=False,
            opening_fraction=0.0,
            curtain_open=True,
            blind_open=True,
            blind_fraction=0.0,
            control_mode=WINDOW_CONTROL_MODE_MANUAL,
            source="default_window_closed_curtain_open_blind_open",
        )

    if not isinstance(operation_input, ZoneWindowOperationInput):
        raise TypeError(
            "operation_input must be ZoneWindowOperationInput."
        )

    if (
        operation_input.boundary_connection_id
        != window_static_parameters.boundary_connection_id
    ):
        raise ValueError(
            "operation_input.boundary_connection_id does not match "
            "window_static_parameters.boundary_connection_id."
        )

    if operation_input.zone_id != window_static_parameters.zone_id:
        raise ValueError(
            "operation_input.zone_id does not match "
            "window_static_parameters.zone_id."
        )

    return WindowOperationState(
        boundary_connection_id=window_static_parameters.boundary_connection_id,
        zone_id=window_static_parameters.zone_id,
        is_open=operation_input.is_open,
        opening_fraction=operation_input.opening_fraction,
        curtain_open=operation_input.curtain_open,
        blind_open=operation_input.blind_open,
        blind_fraction=operation_input.blind_fraction,
        source=WINDOW_OPERATION_STATE_SOURCE,
    )


def make_building_window_operation_state(
    building_window_static_parameters: BuildingWindowStaticParameters,
    building_window_operation_inputs: BuildingWindowOperationInputs = None,
) -> BuildingWindowOperationState:
    """
    Build operation state for all known static windows.

    Static window list is authoritative.
    Operation inputs only override dynamic state.
    """

    if not isinstance(building_window_static_parameters, BuildingWindowStaticParameters):
        raise TypeError(
            "building_window_static_parameters must be BuildingWindowStaticParameters."
        )

    if building_window_operation_inputs is None:
        building_window_operation_inputs = make_empty_window_operation_inputs()

    if not isinstance(building_window_operation_inputs, BuildingWindowOperationInputs):
        raise TypeError(
            "building_window_operation_inputs must be BuildingWindowOperationInputs."
        )

    states_by_window = {}

    for zone_parameters in building_window_static_parameters.zone_window_parameters.values():
        for window_static_parameters in zone_parameters.windows:
            operation_input = (
                building_window_operation_inputs
                .get_operation_input_for_window(
                    boundary_connection_id=window_static_parameters.boundary_connection_id,
                    zone_id=window_static_parameters.zone_id,
                )
            )

            state = make_window_operation_state(
                window_static_parameters=window_static_parameters,
                operation_input=operation_input,
            )

            states_by_window[state.boundary_connection_id] = state

    return BuildingWindowOperationState(
        states_by_window=states_by_window,
    )


def make_window_operation_inputs(
    is_open_by_window: Dict[str, bool] = None,
    opening_fraction_by_window: Dict[str, float] = None,
    curtain_open_by_window: Dict[str, bool] = None,
    blind_open_by_window: Dict[str, bool] = None,
    blind_fraction_by_window: Dict[str, float] = None,
    zone_id_by_window: Dict[str, str] = None,
    control_mode: str = WINDOW_CONTROL_MODE_MANUAL,
) -> BuildingWindowOperationInputs:
    """
    Convenience builder for external bridge code.

    Requires zone_id_by_window for every window included.
    """

    if is_open_by_window is None:
        is_open_by_window = {}

    if opening_fraction_by_window is None:
        opening_fraction_by_window = {}

    if curtain_open_by_window is None:
        curtain_open_by_window = {}

    if blind_open_by_window is None:
        blind_open_by_window = {}

    if blind_fraction_by_window is None:
        blind_fraction_by_window = {}

    if zone_id_by_window is None:
        zone_id_by_window = {}

    window_ids = set()
    window_ids.update(is_open_by_window.keys())
    window_ids.update(opening_fraction_by_window.keys())
    window_ids.update(curtain_open_by_window.keys())
    window_ids.update(blind_open_by_window.keys())
    window_ids.update(blind_fraction_by_window.keys())

    operation_inputs_by_window = {}

    for window_id in window_ids:
        if window_id not in zone_id_by_window:
            raise ValueError(
                "zone_id_by_window must provide zone_id for window "
                + window_id
            )

        operation_inputs_by_window[window_id] = ZoneWindowOperationInput(
            boundary_connection_id=window_id,
            zone_id=zone_id_by_window[window_id],
            is_open=is_open_by_window.get(window_id, False),
            opening_fraction=opening_fraction_by_window.get(window_id, 0.0),
            curtain_open=curtain_open_by_window.get(window_id, True),
            blind_open=blind_open_by_window.get(window_id, True),
            blind_fraction=blind_fraction_by_window.get(window_id, 0.0),
            control_mode=control_mode,
            source=WINDOW_OPERATION_INPUT_SOURCE,
        )

    return BuildingWindowOperationInputs(
        operation_inputs_by_window=operation_inputs_by_window,
        source=WINDOW_OPERATION_INPUT_SOURCE,
    )

def curtain_daylight_multiplier(
    curtain_open: bool,
    curtain_daylight_reduction_factor: float = DEFAULT_CURTAIN_DAYLIGHT_REDUCTION_FACTOR,
) -> float:
    curtain_open = bool(curtain_open)

    curtain_daylight_reduction_factor = _clamp_unit_interval(
        curtain_daylight_reduction_factor
    )

    if curtain_open:
        return 1.0

    return curtain_daylight_reduction_factor


def curtain_solar_multiplier(
    curtain_open: bool,
    curtain_solar_reduction_factor: float = DEFAULT_CURTAIN_SOLAR_REDUCTION_FACTOR,
) -> float:
    curtain_open = bool(curtain_open)

    curtain_solar_reduction_factor = _clamp_unit_interval(
        curtain_solar_reduction_factor
    )

    if curtain_open:
        return 1.0

    return curtain_solar_reduction_factor


def blind_daylight_multiplier(
    blind_open: bool,
    blind_fraction: float = DEFAULT_BLIND_FRACTION,
    blind_daylight_reduction_factor: float = DEFAULT_BLIND_DAYLIGHT_REDUCTION_FACTOR,
) -> float:
    blind_open = bool(blind_open)

    blind_fraction = _clamp_unit_interval(
        blind_fraction
    )

    blind_daylight_reduction_factor = _clamp_unit_interval(
        blind_daylight_reduction_factor
    )

    if blind_open:
        return 1.0

    return (
        (1.0 - blind_fraction)
        + blind_fraction * blind_daylight_reduction_factor
    )


def blind_solar_multiplier(
    blind_open: bool,
    blind_fraction: float = DEFAULT_BLIND_FRACTION,
    blind_solar_reduction_factor: float = DEFAULT_BLIND_SOLAR_REDUCTION_FACTOR,
) -> float:
    blind_open = bool(blind_open)

    blind_fraction = _clamp_unit_interval(
        blind_fraction
    )

    blind_solar_reduction_factor = _clamp_unit_interval(
        blind_solar_reduction_factor
    )

    if blind_open:
        return 1.0

    return (
        (1.0 - blind_fraction)
        + blind_fraction * blind_solar_reduction_factor
    )

def calculate_window_covering_effect(
    window_static_parameters: WindowStaticParameters,
    window_operation_state: WindowOperationState,
    curtain_daylight_reduction_factor: float = DEFAULT_CURTAIN_DAYLIGHT_REDUCTION_FACTOR,
    curtain_solar_reduction_factor: float = DEFAULT_CURTAIN_SOLAR_REDUCTION_FACTOR,
    blind_daylight_reduction_factor: float = DEFAULT_BLIND_DAYLIGHT_REDUCTION_FACTOR,
    blind_solar_reduction_factor: float = DEFAULT_BLIND_SOLAR_REDUCTION_FACTOR,
) -> WindowCoveringEffectResult:
    """
    Calculate effective daylight and solar factors for one window.

    Airflow must not use this result.
    """

    if not isinstance(window_static_parameters, WindowStaticParameters):
        raise TypeError(
            "window_static_parameters must be WindowStaticParameters."
        )

    if not isinstance(window_operation_state, WindowOperationState):
        raise TypeError(
            "window_operation_state must be WindowOperationState."
        )

    if (
        window_static_parameters.boundary_connection_id
        != window_operation_state.boundary_connection_id
    ):
        raise ValueError(
            "window_static_parameters and window_operation_state refer to "
            "different windows."
        )

    daylight_multiplier = (
        curtain_daylight_multiplier(
            curtain_open=window_operation_state.curtain_open,
            curtain_daylight_reduction_factor=curtain_daylight_reduction_factor,
        )
        * blind_daylight_multiplier(
            blind_open=window_operation_state.blind_open,
            blind_fraction=window_operation_state.blind_fraction,
            blind_daylight_reduction_factor=blind_daylight_reduction_factor,
        )
    )

    solar_multiplier = (
        curtain_solar_multiplier(
            curtain_open=window_operation_state.curtain_open,
            curtain_solar_reduction_factor=curtain_solar_reduction_factor,
        )
        * blind_solar_multiplier(
            blind_open=window_operation_state.blind_open,
            blind_fraction=window_operation_state.blind_fraction,
            blind_solar_reduction_factor=blind_solar_reduction_factor,
        )
    )

    effective_visible_transmittance = (
        window_static_parameters.window_visible_transmittance
        * window_static_parameters.shading_factor
        * daylight_multiplier
    )

    effective_solar_transmittance = (
        window_static_parameters.solar_heat_gain_coefficient
        * window_static_parameters.shading_factor
        * solar_multiplier
    )

    effective_daylight_factor = _clamp_unit_interval(
        window_static_parameters.window_visible_transmittance
        * daylight_multiplier
    )

    effective_solar_factor = _clamp_unit_interval(
        window_static_parameters.solar_heat_gain_coefficient
        * solar_multiplier
    )

    return WindowCoveringEffectResult(
        boundary_connection_id=window_static_parameters.boundary_connection_id,
        zone_id=window_static_parameters.zone_id,
        base_visible_transmittance=window_static_parameters.window_visible_transmittance,
        base_solar_factor=window_static_parameters.solar_heat_gain_coefficient,
        curtain_open=window_operation_state.curtain_open,
        blind_open=window_operation_state.blind_open,
        blind_fraction=window_operation_state.blind_fraction,
        curtain_daylight_reduction_factor=curtain_daylight_reduction_factor,
        curtain_solar_reduction_factor=curtain_solar_reduction_factor,
        blind_daylight_reduction_factor=blind_daylight_reduction_factor,
        blind_solar_reduction_factor=blind_solar_reduction_factor,
        effective_visible_transmittance=effective_visible_transmittance,
        effective_solar_transmittance=effective_solar_transmittance,
        effective_daylight_factor=effective_daylight_factor,
        effective_solar_factor=effective_solar_factor,
        source=WINDOW_COVERING_EFFECT_SOURCE,
    )

def calculate_building_window_covering_effects(
    building_window_static_parameters: BuildingWindowStaticParameters,
    building_window_operation_state: BuildingWindowOperationState,
) -> BuildingWindowCoveringEffectResult:
    """
    Calculate curtain/blind effects for all known static windows.
    """

    if not isinstance(building_window_static_parameters, BuildingWindowStaticParameters):
        raise TypeError(
            "building_window_static_parameters must be BuildingWindowStaticParameters."
        )

    if not isinstance(building_window_operation_state, BuildingWindowOperationState):
        raise TypeError(
            "building_window_operation_state must be BuildingWindowOperationState."
        )

    effects_by_window = {}

    for zone_parameters in building_window_static_parameters.zone_window_parameters.values():
        for window_static_parameters in zone_parameters.windows:
            window_state = building_window_operation_state.get_state_for_window(
                window_static_parameters.boundary_connection_id
            )

            effect = calculate_window_covering_effect(
                window_static_parameters=window_static_parameters,
                window_operation_state=window_state,
            )

            effects_by_window[effect.boundary_connection_id] = effect

    return BuildingWindowCoveringEffectResult(
        effects_by_window=effects_by_window,
        source=WINDOW_COVERING_EFFECT_SOURCE,
    )

def calculate_covering_effects_from_static_and_inputs(
    building_window_static_parameters: BuildingWindowStaticParameters,
    building_window_operation_inputs: BuildingWindowOperationInputs = None,
) -> BuildingWindowCoveringEffectResult:
    """
    Convenience pipeline:

        static window parameters
        + operation bridge inputs
        -> operation state
        -> curtain/blind covering effects
    """

    operation_state = make_building_window_operation_state(
        building_window_static_parameters=building_window_static_parameters,
        building_window_operation_inputs=building_window_operation_inputs,
    )

    return calculate_building_window_covering_effects(
        building_window_static_parameters=building_window_static_parameters,
        building_window_operation_state=operation_state,
    )

def calculate_window_airflow_opening_result(
    window_static_parameters: WindowStaticParameters,
    window_operation_state: WindowOperationState,
    weather_state: Any,
) -> WindowAirflowOpeningResult:
    """
    Calculate outdoor airflow potential through one window.

    Simplified formula:

        q_m3_s =
            discharge_coefficient
            * effective_opening_area_m2
            * wind_speed_m_s
            * wind_alignment_factor

        q_m3_h = q_m3_s * 3600

    This is a shared window-boundary calculation.
    airflow.py should consume this result later instead of duplicating window logic.
    """

    if not isinstance(window_static_parameters, WindowStaticParameters):
        raise TypeError(
            "window_static_parameters must be WindowStaticParameters."
        )

    if not isinstance(window_operation_state, WindowOperationState):
        raise TypeError(
            "window_operation_state must be WindowOperationState."
        )

    if (
        window_static_parameters.boundary_connection_id
        != window_operation_state.boundary_connection_id
    ):
        raise ValueError(
            "window_static_parameters and window_operation_state refer to "
            "different windows."
        )

    wind_speed_m_s = DEFAULT_WINDOW_WIND_SPEED_M_S
    wind_direction_deg = 0.0

    if weather_state is not None:
        wind_speed_m_s = _get_attr_or_default(
            weather_state,
            "wind_speed_m_s",
            DEFAULT_WINDOW_WIND_SPEED_M_S,
        )

        wind_direction_deg = _get_attr_or_default(
            weather_state,
            "wind_direction_deg",
            0.0,
        )

    wind_speed_m_s = _non_negative_float(
        wind_speed_m_s,
        "wind_speed_m_s",
        window_static_parameters.boundary_connection_id,
    )

    wind_direction_deg = normalize_orientation_deg(
        wind_direction_deg
    )

    alignment_factor = wind_alignment_factor(
        window_orientation_deg=window_static_parameters.orientation_deg,
        wind_direction_deg=wind_direction_deg,
    )

    effective_opening_area_m2 = window_operation_state.effective_opening_area_m2(
        window_static_parameters
    )

    if (
        not window_operation_state.is_open
        or window_operation_state.opening_fraction <= 0.0
        or effective_opening_area_m2 <= 0.0
        or wind_speed_m_s <= 0.0
        or alignment_factor <= 0.0
    ):
        outdoor_airflow_m3_s = 0.0
    else:
        outdoor_airflow_m3_s = (
            window_static_parameters.discharge_coefficient
            * effective_opening_area_m2
            * wind_speed_m_s
            * alignment_factor
        )

    outdoor_airflow_m3_h = outdoor_airflow_m3_s * 3600.0

    return WindowAirflowOpeningResult(
        boundary_connection_id=window_static_parameters.boundary_connection_id,
        zone_id=window_static_parameters.zone_id,
        is_open=window_operation_state.is_open,
        opening_fraction=window_operation_state.opening_fraction,
        max_opening_area_m2=window_static_parameters.max_opening_area_m2,
        effective_opening_area_m2=effective_opening_area_m2,
        discharge_coefficient=window_static_parameters.discharge_coefficient,
        wind_speed_m_s=wind_speed_m_s,
        wind_direction_deg=wind_direction_deg,
        window_orientation_deg=window_static_parameters.orientation_deg,
        wind_alignment_factor=alignment_factor,
        outdoor_airflow_m3_s=outdoor_airflow_m3_s,
        outdoor_airflow_m3_h=outdoor_airflow_m3_h,
        source=WINDOW_AIRFLOW_OPENING_SOURCE,
    )

def calculate_building_window_airflow_openings(
    building_window_static_parameters: BuildingWindowStaticParameters,
    building_window_operation_state: BuildingWindowOperationState,
    weather_state: Any,
) -> BuildingWindowAirflowOpeningResult:
    """
    Calculate outdoor airflow potential for all windows.

    Output is meant to be consumed by airflow.py.
    CO2 and moisture should still use the airflow network, not windows directly.
    """

    if not isinstance(building_window_static_parameters, BuildingWindowStaticParameters):
        raise TypeError(
            "building_window_static_parameters must be BuildingWindowStaticParameters."
        )

    if not isinstance(building_window_operation_state, BuildingWindowOperationState):
        raise TypeError(
            "building_window_operation_state must be BuildingWindowOperationState."
        )

    airflow_openings_by_window = {}

    for zone_parameters in building_window_static_parameters.zone_window_parameters.values():
        for window_static_parameters in zone_parameters.windows:
            window_state = building_window_operation_state.get_state_for_window(
                window_static_parameters.boundary_connection_id
            )

            result = calculate_window_airflow_opening_result(
                window_static_parameters=window_static_parameters,
                window_operation_state=window_state,
                weather_state=weather_state,
            )

            airflow_openings_by_window[result.boundary_connection_id] = result

    return BuildingWindowAirflowOpeningResult(
        airflow_openings_by_window=airflow_openings_by_window,
        source=WINDOW_AIRFLOW_OPENING_SOURCE,
    )

def calculate_airflow_openings_from_static_inputs_and_weather(
    building_window_static_parameters: BuildingWindowStaticParameters,
    building_window_operation_inputs: BuildingWindowOperationInputs = None,
    weather_state: Any = None,
) -> BuildingWindowAirflowOpeningResult:
    """
    Convenience pipeline:

        static window parameters
        + operation bridge inputs
        + weather wind
        -> operation state
        -> window airflow opening result
    """

    operation_state = make_building_window_operation_state(
        building_window_static_parameters=building_window_static_parameters,
        building_window_operation_inputs=building_window_operation_inputs,
    )

    return calculate_building_window_airflow_openings(
        building_window_static_parameters=building_window_static_parameters,
        building_window_operation_state=operation_state,
        weather_state=weather_state,
    )

def calculate_window_thermal_conductance_result(
    window_static_parameters: WindowStaticParameters,
    indoor_temperature_c: float,
    outdoor_temperature_c: float,
) -> WindowThermalConductanceResult:
    """
    Calculate closed-window conductive heat exchange.
    """

    if not isinstance(window_static_parameters, WindowStaticParameters):
        raise TypeError(
            "window_static_parameters must be WindowStaticParameters."
        )

    indoor_temperature_c = float(indoor_temperature_c)
    outdoor_temperature_c = float(outdoor_temperature_c)

    conductance_w_k = window_static_parameters.closed_window_conductance_w_k()

    delta_t = outdoor_temperature_c - indoor_temperature_c

    heat_flow_to_zone_w = conductance_w_k * delta_t

    return WindowThermalConductanceResult(
        boundary_connection_id=window_static_parameters.boundary_connection_id,
        zone_id=window_static_parameters.zone_id,
        area_m2=window_static_parameters.area_m2,
        window_u_value_w_m2k=window_static_parameters.window_u_value_w_m2k,
        conductance_w_k=conductance_w_k,
        indoor_temperature_c=indoor_temperature_c,
        outdoor_temperature_c=outdoor_temperature_c,
        delta_t_outdoor_minus_indoor_k=delta_t,
        heat_flow_to_zone_w=heat_flow_to_zone_w,
        source=WINDOW_THERMAL_CONDUCTANCE_SOURCE,
    )


def calculate_building_window_thermal_conductance_results(
    building_window_static_parameters: BuildingWindowStaticParameters,
    indoor_temperature_by_zone_c: Dict[str, float],
    weather_state: Any = None,
    outdoor_temperature_c: float = None,
) -> BuildingWindowThermalConductanceResult:
    """
    Calculate closed-window conductive heat exchange for all windows.
    """

    if not isinstance(building_window_static_parameters, BuildingWindowStaticParameters):
        raise TypeError(
            "building_window_static_parameters must be BuildingWindowStaticParameters."
        )

    if indoor_temperature_by_zone_c is None:
        indoor_temperature_by_zone_c = {}

    if outdoor_temperature_c is None:
        outdoor_temperature_c = outdoor_temperature_from_weather_state(
            weather_state
        )

    conductance_results_by_window = {}

    for zone_parameters in building_window_static_parameters.zone_window_parameters.values():
        for window_static_parameters in zone_parameters.windows:
            indoor_temperature_c = indoor_temperature_by_zone_c.get(
                window_static_parameters.zone_id,
                DEFAULT_WINDOW_INDOOR_TEMPERATURE_C,
            )

            result = calculate_window_thermal_conductance_result(
                window_static_parameters=window_static_parameters,
                indoor_temperature_c=indoor_temperature_c,
                outdoor_temperature_c=outdoor_temperature_c,
            )

            conductance_results_by_window[result.boundary_connection_id] = result

    return BuildingWindowThermalConductanceResult(
        conductance_results_by_window=conductance_results_by_window,
        source=WINDOW_THERMAL_CONDUCTANCE_SOURCE,
    )

def calculate_window_opening_thermal_exchange_result(
    window_airflow_opening_result: WindowAirflowOpeningResult,
    indoor_temperature_c: float,
    outdoor_temperature_c: float,
    air_density_kg_m3: float = WINDOW_AIR_DENSITY_KG_M3,
    air_specific_heat_j_kg_k: float = WINDOW_AIR_SPECIFIC_HEAT_J_KG_K,
) -> WindowOpeningThermalExchangeResult:
    """
    Calculate opening-related ventilation heat exchange.

    Important:
        airflow is already provided by WindowAirflowOpeningResult.
        This function does not calculate airflow.
    """

    if not isinstance(window_airflow_opening_result, WindowAirflowOpeningResult):
        raise TypeError(
            "window_airflow_opening_result must be WindowAirflowOpeningResult."
        )

    indoor_temperature_c = float(indoor_temperature_c)
    outdoor_temperature_c = float(outdoor_temperature_c)

    air_density_kg_m3 = _non_negative_float(
        air_density_kg_m3,
        "air_density_kg_m3",
        window_airflow_opening_result.boundary_connection_id,
    )

    air_specific_heat_j_kg_k = _non_negative_float(
        air_specific_heat_j_kg_k,
        "air_specific_heat_j_kg_k",
        window_airflow_opening_result.boundary_connection_id,
    )

    airflow_m3_s = window_airflow_opening_result.outdoor_airflow_m3_s

    equivalent_conductance_w_k = (
        air_density_kg_m3
        * air_specific_heat_j_kg_k
        * airflow_m3_s
    )

    delta_t = outdoor_temperature_c - indoor_temperature_c

    heat_flow_to_zone_w = equivalent_conductance_w_k * delta_t

    return WindowOpeningThermalExchangeResult(
        boundary_connection_id=window_airflow_opening_result.boundary_connection_id,
        zone_id=window_airflow_opening_result.zone_id,
        outdoor_airflow_m3_h=window_airflow_opening_result.outdoor_airflow_m3_h,
        outdoor_airflow_m3_s=window_airflow_opening_result.outdoor_airflow_m3_s,
        indoor_temperature_c=indoor_temperature_c,
        outdoor_temperature_c=outdoor_temperature_c,
        delta_t_outdoor_minus_indoor_k=delta_t,
        equivalent_ventilation_conductance_w_k=equivalent_conductance_w_k,
        heat_flow_to_zone_w=heat_flow_to_zone_w,
        source=WINDOW_OPENING_THERMAL_EXCHANGE_SOURCE,
    )


def calculate_building_window_opening_thermal_exchange_results(
    building_window_airflow_opening_result: BuildingWindowAirflowOpeningResult,
    indoor_temperature_by_zone_c: Dict[str, float],
    weather_state: Any = None,
    outdoor_temperature_c: float = None,
) -> BuildingWindowOpeningThermalExchangeResult:
    """
    Calculate opening-related thermal exchange for all windows.

    This consumes window airflow results.
    It does not calculate airflow.
    """

    if not isinstance(building_window_airflow_opening_result, BuildingWindowAirflowOpeningResult):
        raise TypeError(
            "building_window_airflow_opening_result must be BuildingWindowAirflowOpeningResult."
        )

    if indoor_temperature_by_zone_c is None:
        indoor_temperature_by_zone_c = {}

    if outdoor_temperature_c is None:
        outdoor_temperature_c = outdoor_temperature_from_weather_state(
            weather_state
        )

    exchange_results_by_window = {}

    for window_id, airflow_result in building_window_airflow_opening_result.airflow_openings_by_window.items():
        indoor_temperature_c = indoor_temperature_by_zone_c.get(
            airflow_result.zone_id,
            DEFAULT_WINDOW_INDOOR_TEMPERATURE_C,
        )

        result = calculate_window_opening_thermal_exchange_result(
            window_airflow_opening_result=airflow_result,
            indoor_temperature_c=indoor_temperature_c,
            outdoor_temperature_c=outdoor_temperature_c,
        )

        exchange_results_by_window[window_id] = result

    return BuildingWindowOpeningThermalExchangeResult(
        exchange_results_by_window=exchange_results_by_window,
        source=WINDOW_OPENING_THERMAL_EXCHANGE_SOURCE,
    )

def calculate_window_solar_exposure_result(
    window_static_parameters: WindowStaticParameters,
    weather_state: Any,
) -> WindowSolarExposureResult:
    """
    Calculate simplified solar/daylight directional exposure for one window.

    Logic:
    - If solar azimuth is available, use window orientation + solar direction.
    - If solar altitude is available and <= 0, exposure becomes zero.
    - If solar direction is unavailable, use sky-condition fallback.
    - Diffuse light gives a small non-directional daylight/solar contribution.

    This is intentionally lightweight.
    """

    if not isinstance(window_static_parameters, WindowStaticParameters):
        raise TypeError(
            "window_static_parameters must be WindowStaticParameters."
        )

    sky_condition = DEFAULT_SKY_CONDITION

    outdoor_illuminance_lux = 0.0
    direct_normal_radiation_w_m2 = 0.0
    diffuse_horizontal_radiation_w_m2 = 0.0
    global_horizontal_radiation_w_m2 = 0.0

    solar_azimuth_deg = None
    solar_altitude_deg = None

    if weather_state is not None:
        sky_condition = _get_attr_or_default(
            weather_state,
            "sky_condition",
            DEFAULT_SKY_CONDITION,
        )

        outdoor_illuminance_lux = _get_attr_or_default(
            weather_state,
            "outdoor_illuminance_lux",
            0.0,
        )

        direct_normal_radiation_w_m2 = _get_attr_or_default(
            weather_state,
            "direct_normal_radiation_w_m2",
            0.0,
        )

        diffuse_horizontal_radiation_w_m2 = _get_attr_or_default(
            weather_state,
            "diffuse_horizontal_radiation_w_m2",
            0.0,
        )

        global_horizontal_radiation_w_m2 = _get_attr_or_default(
            weather_state,
            "global_horizontal_radiation_w_m2",
            0.0,
        )

        solar_azimuth_deg = _get_attr_or_default(
            weather_state,
            "solar_azimuth_deg",
            None,
        )

        solar_altitude_deg = _get_attr_or_default(
            weather_state,
            "solar_altitude_deg",
            None,
        )

    sky_factor = sky_condition_exposure_fallback_factor(
        sky_condition
    )

    has_outdoor_light = (
        float(outdoor_illuminance_lux) > 0.0
        or float(direct_normal_radiation_w_m2) > 0.0
        or float(diffuse_horizontal_radiation_w_m2) > 0.0
        or float(global_horizontal_radiation_w_m2) > 0.0
    )

    has_solar_direction = solar_azimuth_deg is not None

    if not has_outdoor_light:
        solar_alignment_value = 0.0
        daylight_alignment_value = 0.0
        solar_exposure_value = 0.0
        daylight_exposure_value = 0.0

    elif has_solar_direction:
        solar_alignment_value = solar_alignment_factor(
            window_orientation_deg=window_static_parameters.orientation_deg,
            solar_azimuth_deg=solar_azimuth_deg,
            solar_altitude_deg=solar_altitude_deg,
        )

        if solar_altitude_deg is not None and float(solar_altitude_deg) <= 0.0:
            solar_alignment_value = 0.0

        diffuse_daylight_factor = 0.0
        diffuse_solar_factor = 0.0

        if float(diffuse_horizontal_radiation_w_m2) > 0.0 or float(outdoor_illuminance_lux) > 0.0:
            diffuse_daylight_factor = (
                DEFAULT_DIFFUSE_DAYLIGHT_EXPOSURE_FRACTION
                * sky_factor
            )

        if float(diffuse_horizontal_radiation_w_m2) > 0.0:
            diffuse_solar_factor = (
                DEFAULT_DIFFUSE_SOLAR_EXPOSURE_FRACTION
                * sky_factor
            )

        solar_exposure_value = max(
            solar_alignment_value,
            diffuse_solar_factor,
        )

        daylight_exposure_value = max(
            solar_alignment_value,
            diffuse_daylight_factor,
        )

        daylight_alignment_value = daylight_exposure_value

    else:
        solar_alignment_value = sky_factor
        daylight_alignment_value = sky_factor
        solar_exposure_value = sky_factor
        daylight_exposure_value = sky_factor

    return WindowSolarExposureResult(
        boundary_connection_id=window_static_parameters.boundary_connection_id,
        zone_id=window_static_parameters.zone_id,
        window_orientation_deg=window_static_parameters.orientation_deg,
        window_orientation_label=orientation_label(
            window_static_parameters.orientation_deg
        ),
        solar_azimuth_deg=solar_azimuth_deg,
        solar_altitude_deg=solar_altitude_deg,
        has_solar_direction=has_solar_direction,
        sky_condition=sky_condition,
        outdoor_illuminance_lux=outdoor_illuminance_lux,
        direct_normal_radiation_w_m2=direct_normal_radiation_w_m2,
        diffuse_horizontal_radiation_w_m2=diffuse_horizontal_radiation_w_m2,
        global_horizontal_radiation_w_m2=global_horizontal_radiation_w_m2,
        sky_condition_fallback_factor=sky_factor,
        solar_alignment_factor=solar_alignment_value,
        daylight_alignment_factor=daylight_alignment_value,
        solar_exposure_factor=solar_exposure_value,
        daylight_exposure_factor=daylight_exposure_value,
        source=WINDOW_SOLAR_EXPOSURE_SOURCE,
    )

def calculate_building_window_solar_exposure_results(
    building_window_static_parameters: BuildingWindowStaticParameters,
    weather_state: Any,
) -> BuildingWindowSolarExposureResult:
    """
    Calculate simplified solar/daylight directional exposure for all windows.
    """

    if not isinstance(building_window_static_parameters, BuildingWindowStaticParameters):
        raise TypeError(
            "building_window_static_parameters must be BuildingWindowStaticParameters."
        )

    exposures_by_window = {}

    for zone_parameters in building_window_static_parameters.zone_window_parameters.values():
        for window_static_parameters in zone_parameters.windows:
            exposure = calculate_window_solar_exposure_result(
                window_static_parameters=window_static_parameters,
                weather_state=weather_state,
            )

            exposures_by_window[exposure.boundary_connection_id] = exposure

    return BuildingWindowSolarExposureResult(
        exposures_by_window=exposures_by_window,
        source=WINDOW_SOLAR_EXPOSURE_SOURCE,
    )

def calculate_building_window_boundary_result(
    physics_graph: Any,
    building_model: Any = None,
    building_window_operation_inputs: BuildingWindowOperationInputs = None,
    weather_state: Any = None,
) -> BuildingWindowBoundaryResult:
    """
    Full Phase 8 shared window pipeline.

    BoundaryConnection
        -> static window parameters

    WindowOperationInputs
        -> operation state

    WeatherState
        -> wind alignment and solar/daylight exposure

    Output:
        BuildingWindowBoundaryResult
    """

    building_window_static_parameters = make_building_window_static_parameters(
        physics_graph=physics_graph,
        building_model=building_model,
    )

    building_window_operation_state = make_building_window_operation_state(
        building_window_static_parameters=building_window_static_parameters,
        building_window_operation_inputs=building_window_operation_inputs,
    )

    building_window_covering_effect_result = calculate_building_window_covering_effects(
        building_window_static_parameters=building_window_static_parameters,
        building_window_operation_state=building_window_operation_state,
    )

    building_window_airflow_opening_result = calculate_building_window_airflow_openings(
        building_window_static_parameters=building_window_static_parameters,
        building_window_operation_state=building_window_operation_state,
        weather_state=weather_state,
    )

    building_window_solar_exposure_result = calculate_building_window_solar_exposure_results(
        building_window_static_parameters=building_window_static_parameters,
        weather_state=weather_state,
    )

    return make_building_window_boundary_result(
        building_window_static_parameters=building_window_static_parameters,
        building_window_operation_state=building_window_operation_state,
        building_window_covering_effect_result=building_window_covering_effect_result,
        building_window_airflow_opening_result=building_window_airflow_opening_result,
        building_window_solar_exposure_result=building_window_solar_exposure_result,
    )

#%% helpers


def window_boundary_outdoor_airflow_by_zone_m3_h(
    window_boundary_result: BuildingWindowBoundaryResult,
) -> Dict[str, float]:
    if not isinstance(window_boundary_result, BuildingWindowBoundaryResult):
        raise TypeError(
            "window_boundary_result must be BuildingWindowBoundaryResult."
        )

    return window_boundary_result.outdoor_airflow_by_zone_m3_h()


def window_boundary_closed_conductance_by_zone_w_k(
    window_boundary_result: BuildingWindowBoundaryResult,
) -> Dict[str, float]:
    if not isinstance(window_boundary_result, BuildingWindowBoundaryResult):
        raise TypeError(
            "window_boundary_result must be BuildingWindowBoundaryResult."
        )

    return window_boundary_result.closed_window_conductance_by_zone_w_k()


def window_boundary_effective_daylight_area_by_zone_m2(
    window_boundary_result: BuildingWindowBoundaryResult,
) -> Dict[str, float]:
    if not isinstance(window_boundary_result, BuildingWindowBoundaryResult):
        raise TypeError(
            "window_boundary_result must be BuildingWindowBoundaryResult."
        )

    return window_boundary_result.effective_daylight_area_by_zone_m2()


def window_boundary_effective_solar_area_by_zone_m2(
    window_boundary_result: BuildingWindowBoundaryResult,
) -> Dict[str, float]:
    if not isinstance(window_boundary_result, BuildingWindowBoundaryResult):
        raise TypeError(
            "window_boundary_result must be BuildingWindowBoundaryResult."
        )

    return window_boundary_result.effective_solar_area_by_zone_m2()

def solar_exposure_factor_by_window(
    solar_exposure_result: BuildingWindowSolarExposureResult,
) -> Dict[str, float]:
    if not isinstance(solar_exposure_result, BuildingWindowSolarExposureResult):
        raise TypeError(
            "solar_exposure_result must be BuildingWindowSolarExposureResult."
        )

    return solar_exposure_result.solar_exposure_factor_by_window()


def daylight_exposure_factor_by_window(
    solar_exposure_result: BuildingWindowSolarExposureResult,
) -> Dict[str, float]:
    if not isinstance(solar_exposure_result, BuildingWindowSolarExposureResult):
        raise TypeError(
            "solar_exposure_result must be BuildingWindowSolarExposureResult."
        )

    return solar_exposure_result.daylight_exposure_factor_by_window()


def solar_exposure_factor_for_window(
    solar_exposure_result: BuildingWindowSolarExposureResult,
    boundary_connection_id: str,
) -> float:
    return (
        solar_exposure_result
        .get_exposure_for_window(boundary_connection_id)
        .solar_exposure_factor
    )


def daylight_exposure_factor_for_window(
    solar_exposure_result: BuildingWindowSolarExposureResult,
    boundary_connection_id: str,
) -> float:
    return (
        solar_exposure_result
        .get_exposure_for_window(boundary_connection_id)
        .daylight_exposure_factor
    )
def outdoor_temperature_from_weather_state(
    weather_state: Any,
) -> float:
    if weather_state is None:
        return DEFAULT_WINDOW_OUTDOOR_TEMPERATURE_C

    return float(
        _get_attr_or_default(
            weather_state,
            "outdoor_temperature_c",
            DEFAULT_WINDOW_OUTDOOR_TEMPERATURE_C,
        )
    )


def window_closed_conductance_by_zone_w_k(
    conductance_result: BuildingWindowThermalConductanceResult,
) -> Dict[str, float]:
    if not isinstance(conductance_result, BuildingWindowThermalConductanceResult):
        raise TypeError(
            "conductance_result must be BuildingWindowThermalConductanceResult."
        )

    return conductance_result.conductance_by_zone_w_k()


def window_closed_heat_flow_by_zone_w(
    conductance_result: BuildingWindowThermalConductanceResult,
) -> Dict[str, float]:
    if not isinstance(conductance_result, BuildingWindowThermalConductanceResult):
        raise TypeError(
            "conductance_result must be BuildingWindowThermalConductanceResult."
        )

    return conductance_result.heat_flow_by_zone_w()


def window_opening_heat_flow_by_zone_w(
    opening_exchange_result: BuildingWindowOpeningThermalExchangeResult,
) -> Dict[str, float]:
    if not isinstance(opening_exchange_result, BuildingWindowOpeningThermalExchangeResult):
        raise TypeError(
            "opening_exchange_result must be BuildingWindowOpeningThermalExchangeResult."
        )

    return opening_exchange_result.heat_flow_by_zone_w()


def window_total_thermal_heat_flow_by_zone_w(
    conductance_result: BuildingWindowThermalConductanceResult,
    opening_exchange_result: BuildingWindowOpeningThermalExchangeResult = None,
) -> Dict[str, float]:
    """
    Adapter for thermal.py.

    Returns total window-related heat flow by zone:
        closed-window conductive heat flow
        + optional opening-related ventilation heat exchange

    Positive means heat gain to zone.
    """

    values = window_closed_heat_flow_by_zone_w(
        conductance_result
    )

    if opening_exchange_result is None:
        return values

    opening_values = window_opening_heat_flow_by_zone_w(
        opening_exchange_result
    )

    for zone_id, heat_flow_w in opening_values.items():
        if zone_id not in values:
            values[zone_id] = 0.0

        values[zone_id] += heat_flow_w

    return values

def outdoor_airflow_from_window_openings_by_zone_m3_h(
    window_airflow_opening_result: BuildingWindowAirflowOpeningResult,
) -> Dict[str, float]:
    """
    Adapter for airflow.py.

    airflow.py can use this as an external window-airflow contribution by zone.
    """

    if not isinstance(window_airflow_opening_result, BuildingWindowAirflowOpeningResult):
        raise TypeError(
            "window_airflow_opening_result must be BuildingWindowAirflowOpeningResult."
        )

    return window_airflow_opening_result.outdoor_airflow_by_zone_m3_h()

def is_window_boundary_connection(
    boundary_connection: Any,
) -> bool:
    if boundary_connection is None:
        return False

    connection_type = str(
        _get_attr_or_default(
            boundary_connection,
            "connection_type",
            "",
        )
    ).strip().lower()

    if connection_type == "window":
        return True

    if "window" in connection_type:
        return True

    return False


def normalize_orientation_deg(
    orientation_deg: float,
) -> float:
    """
    Normalize angle to [0, 360).

    Examples:
        -90  -> 270
        360  -> 0
        450  -> 90
    """

    orientation_deg = float(orientation_deg)

    orientation_deg = orientation_deg % 360.0

    if orientation_deg < 0.0:
        orientation_deg += 360.0

    return orientation_deg


def angular_difference_deg(
    angle_a_deg: float,
    angle_b_deg: float,
) -> float:
    """
    Smallest absolute angular difference between two directions.

    Returns:
        value in [0, 180]
    """

    angle_a_deg = normalize_orientation_deg(angle_a_deg)
    angle_b_deg = normalize_orientation_deg(angle_b_deg)

    difference = abs(angle_a_deg - angle_b_deg)

    if difference > 180.0:
        difference = 360.0 - difference

    return difference


def signed_angular_difference_deg(
    from_angle_deg: float,
    to_angle_deg: float,
) -> float:
    """
    Signed shortest angular difference from one direction to another.

    Returns:
        value in [-180, 180)

    Positive means counter-clockwise in mathematical angle convention.
    """

    from_angle_deg = normalize_orientation_deg(from_angle_deg)
    to_angle_deg = normalize_orientation_deg(to_angle_deg)

    difference = (to_angle_deg - from_angle_deg + 180.0) % 360.0 - 180.0

    return difference


def orientation_label(
    orientation_deg: float,
) -> str:
    """
    Convert orientation angle to 8-sector label.

    Convention:
        0/360 = north
        90    = east
        180   = south
        270   = west
    """

    orientation_deg = normalize_orientation_deg(orientation_deg)

    if orientation_deg >= 337.5 or orientation_deg < 22.5:
        return ORIENTATION_NORTH

    if orientation_deg < 67.5:
        return ORIENTATION_NORTH_EAST

    if orientation_deg < 112.5:
        return ORIENTATION_EAST

    if orientation_deg < 157.5:
        return ORIENTATION_SOUTH_EAST

    if orientation_deg < 202.5:
        return ORIENTATION_SOUTH

    if orientation_deg < 247.5:
        return ORIENTATION_SOUTH_WEST

    if orientation_deg < 292.5:
        return ORIENTATION_WEST

    return ORIENTATION_NORTH_WEST


def front_facing_cosine_alignment_factor(
    surface_orientation_deg: float,
    incoming_direction_deg: float,
) -> float:
    """
    Shared front-facing alignment factor.

    Used for:
    - wind-to-window exposure
    - sun-to-window exposure

    Returns:
        1.0 when direction is perfectly aligned with window outward normal
        0.0 when direction is 90 degrees or more away
    """

    difference_deg = angular_difference_deg(
        surface_orientation_deg,
        incoming_direction_deg,
    )

    difference_rad = math.radians(difference_deg)

    factor = math.cos(difference_rad)

    if factor < 0.0:
        return 0.0

    if factor > 1.0:
        return 1.0

    return factor


def wind_alignment_factor(
    window_orientation_deg: float,
    wind_direction_deg: float,
) -> float:
    """
    Wind-to-window alignment factor.

    Convention:
        window_orientation_deg = outward normal of the window/facade
        wind_direction_deg = direction wind comes from

    Example:
        south-facing window = 180 deg
        southerly wind      = 180 deg
        factor              = 1.0
    """

    return front_facing_cosine_alignment_factor(
        surface_orientation_deg=window_orientation_deg,
        incoming_direction_deg=wind_direction_deg,
    )


def solar_alignment_factor(
    window_orientation_deg: float,
    solar_azimuth_deg: float,
    solar_altitude_deg: float = None,
) -> float:
    """
    Sun-to-window alignment factor.

    Convention:
        window_orientation_deg = outward normal of the window/facade
        solar_azimuth_deg      = direction of the sun position

    If solar_altitude_deg is provided:
        altitude <= 0 gives zero exposure.
        positive altitude applies a simple sin(altitude) height factor.

    This is still simplified. It is not full solar geometry.
    """

    azimuth_factor = front_facing_cosine_alignment_factor(
        surface_orientation_deg=window_orientation_deg,
        incoming_direction_deg=solar_azimuth_deg,
    )

    if solar_altitude_deg is None:
        return azimuth_factor

    solar_altitude_deg = float(solar_altitude_deg)

    if solar_altitude_deg <= 0.0:
        return 0.0

    altitude_factor = math.sin(
        math.radians(solar_altitude_deg)
    )

    if altitude_factor < 0.0:
        altitude_factor = 0.0

    if altitude_factor > 1.0:
        altitude_factor = 1.0

    return azimuth_factor * altitude_factor

def wind_alignment_factor_from_weather_state(
    window_orientation_deg: float,
    weather_state: Any,
) -> float:
    """
    Read wind direction from WeatherState-like object and calculate alignment.
    """

    if weather_state is None:
        return 0.0

    wind_direction_deg = _get_attr_or_default(
        weather_state,
        "wind_direction_deg",
        None,
    )

    if wind_direction_deg is None:
        return 0.0

    return wind_alignment_factor(
        window_orientation_deg=window_orientation_deg,
        wind_direction_deg=wind_direction_deg,
    )


def solar_alignment_factor_from_weather_state(
    window_orientation_deg: float,
    weather_state: Any,
) -> float:
    """
    Read solar direction from WeatherState-like object if available.

    Optional WeatherState-like attributes:
    - solar_azimuth_deg
    - solar_altitude_deg

    If unavailable, returns 0.
    """

    if weather_state is None:
        return 0.0

    solar_azimuth_deg = _get_attr_or_default(
        weather_state,
        "solar_azimuth_deg",
        None,
    )

    if solar_azimuth_deg is None:
        return 0.0

    solar_altitude_deg = _get_attr_or_default(
        weather_state,
        "solar_altitude_deg",
        None,
    )

    return solar_alignment_factor(
        window_orientation_deg=window_orientation_deg,
        solar_azimuth_deg=solar_azimuth_deg,
        solar_altitude_deg=solar_altitude_deg,
    )

def sky_condition_exposure_fallback_factor(
    sky_condition: str,
) -> float:
    sky_condition = str(sky_condition).strip().lower()

    if not sky_condition:
        sky_condition = DEFAULT_SKY_CONDITION

    if "night" in sky_condition:
        return DEFAULT_NIGHT_SKY_EXPOSURE_FACTOR

    if "dark" in sky_condition:
        return DEFAULT_NIGHT_SKY_EXPOSURE_FACTOR

    if "clear" in sky_condition:
        return DEFAULT_CLEAR_SKY_EXPOSURE_FACTOR

    if "sun" in sky_condition:
        return DEFAULT_CLEAR_SKY_EXPOSURE_FACTOR

    if "partly" in sky_condition:
        return DEFAULT_PARTLY_CLOUDY_EXPOSURE_FACTOR

    if "partial" in sky_condition:
        return DEFAULT_PARTLY_CLOUDY_EXPOSURE_FACTOR

    if "cloudy" in sky_condition:
        return DEFAULT_CLOUDY_EXPOSURE_FACTOR

    if "cloud" in sky_condition:
        return DEFAULT_CLOUDY_EXPOSURE_FACTOR

    if "overcast" in sky_condition:
        return DEFAULT_OVERCAST_EXPOSURE_FACTOR

    return DEFAULT_UNKNOWN_SKY_EXPOSURE_FACTOR


def weather_has_outdoor_light(
    weather_state: Any,
) -> bool:
    if weather_state is None:
        return False

    outdoor_illuminance_lux = _get_attr_or_default(
        weather_state,
        "outdoor_illuminance_lux",
        0.0,
    )

    direct_normal_radiation_w_m2 = _get_attr_or_default(
        weather_state,
        "direct_normal_radiation_w_m2",
        0.0,
    )

    diffuse_horizontal_radiation_w_m2 = _get_attr_or_default(
        weather_state,
        "diffuse_horizontal_radiation_w_m2",
        0.0,
    )

    global_horizontal_radiation_w_m2 = _get_attr_or_default(
        weather_state,
        "global_horizontal_radiation_w_m2",
        0.0,
    )

    return (
        float(outdoor_illuminance_lux) > 0.0
        or float(direct_normal_radiation_w_m2) > 0.0
        or float(diffuse_horizontal_radiation_w_m2) > 0.0
        or float(global_horizontal_radiation_w_m2) > 0.0
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


def _clamp_unit_interval(
    value: Any,
) -> float:
    value = float(value)

    if value < 0.0:
        return 0.0

    if value > 1.0:
        return 1.0

    return value


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