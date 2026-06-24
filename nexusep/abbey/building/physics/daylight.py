"""
ABBEY daylight / lighting / visual comfort architecture.

Phase 7.1 only defines the modelling decision.

No daylight solver yet.
No artificial lighting calculation yet.
No visual comfort calculation yet.

Decision:
    Outdoor illuminance from WeatherState is transmitted through windows
    using simplified window/daylight factors to estimate zone indoor illuminance.

Dependency rule:
    weather -> daylight
    graph/window geometry -> daylight
    zone parameters -> daylight
    daylight -> visual comfort/perception
    lighting controls -> artificial lighting later

Not yet:
    daylight -> thermal
    thermal -> daylight
"""

from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional
import copy


DAYLIGHT_MODEL_FAMILY = "simplified_zone_daylight"
LIGHTING_MODEL_FAMILY = "zone_level_artificial_lighting_later"

DAYLIGHT_STATE_VARIABLE = "indoor_illuminance_lux"
DAYLIGHT_DERIVED_VARIABLE = "visual_comfort_status"

DAYLIGHT_SPATIAL_RESOLUTION = "zone"
DAYLIGHT_MULTIZONE_MODE = "independent_zone_daylight"

DAYLIGHT_OUTDOOR_BOUNDARY_SOURCE = "WeatherState"
DAYLIGHT_TOPOLOGY_SOURCE = "BuildingPhysicsGraph"
DAYLIGHT_PARAMETER_SOURCE = "ZoneModel"
DAYLIGHT_WINDOW_SOURCE = "BoundaryConnection"

DAYLIGHT_WEATHER_INPUT = "WeatherState.outdoor_illuminance_lux"
DAYLIGHT_WINDOW_INPUT = "BoundaryConnection.window_visible_transmittance"
DAYLIGHT_ZONE_INPUT = "ZoneModel.daylight_utilization_factor"

DAYLIGHT_CONTROL_INPUT_MODE = "clean_lighting_control_bridge_later"

DAYLIGHT_TO_COMFORT = "daylight_to_visual_comfort"
DAYLIGHT_NOT_TO_THERMAL = "not_daylight_to_thermal_in_phase_7"
THERMAL_NOT_TO_DAYLIGHT = "not_thermal_to_daylight_in_phase_7"

DAYLIGHT_SOLAR_CONSISTENCY_LATER = "solar_daylight_consistency_later"
DAYLIGHT_GLARE_RISK_LATER = "glare_risk_later"
DAYLIGHT_BLIND_CONTROL_LATER = "blind_control_later"
DAYLIGHT_HIGH_FIDELITY_RADIANCE_LATER = "high_fidelity_radiance_later"

DAYLIGHT_MODEL_DECISION = (
    "simplified_zone_indoor_illuminance_from_weather_windows_and_zone_factors"
)

DEFAULT_INDOOR_ILLUMINANCE_LUX = 0.0
DEFAULT_DAYLIGHT_ILLUMINANCE_LUX = 0.0
DEFAULT_ARTIFICIAL_LIGHTING_ILLUMINANCE_LUX = 0.0
DEFAULT_VISUAL_COMFORT_TARGET_LUX = 300.0

MIN_ILLUMINANCE_LUX = 0.0
MAX_REASONABLE_ILLUMINANCE_LUX = 200000.0

VISUAL_COMFORT_STATUS_DARK = "dark"
VISUAL_COMFORT_STATUS_UNDERLIT = "underlit"
VISUAL_COMFORT_STATUS_COMFORTABLE = "comfortable"
VISUAL_COMFORT_STATUS_OVERLIT = "overlit"

DEFAULT_WINDOW_VISIBLE_TRANSMITTANCE = 0.60
DEFAULT_WINDOW_FRAME_FRACTION = 0.20
DEFAULT_WINDOW_DAYLIGHT_UTILIZATION_FACTOR = 0.50
DEFAULT_WINDOW_SHADING_FACTOR = 1.00
DEFAULT_CURTAIN_DAYLIGHT_REDUCTION_FACTOR = 0.35

WINDOW_DAYLIGHT_SOURCE = "BoundaryConnection + ZoneModel"

DEFAULT_OUTDOOR_ILLUMINANCE_LUX = 0.0
DEFAULT_DIRECT_NORMAL_RADIATION_W_M2 = 0.0
DEFAULT_DIFFUSE_HORIZONTAL_RADIATION_W_M2 = 0.0
DEFAULT_GLOBAL_HORIZONTAL_RADIATION_W_M2 = 0.0
DEFAULT_SKY_CONDITION = "unknown"

OUTDOOR_DAYLIGHT_BOUNDARY_SOURCE = "WeatherState"

DAYLIGHT_ESTIMATE_SOURCE = "OutdoorDaylightBoundary + WindowDaylightParameters + ZoneModel"

DEFAULT_DAYLIGHT_FLOOR_AREA_M2 = 20.0
DEFAULT_DAYLIGHT_MIN_FLOOR_AREA_M2 = 1.0

LIGHTING_CONTROL_SOURCE_EXTERNAL_BRIDGE = "external_lighting_control_bridge"

LIGHTING_CONTROL_MODE_MANUAL = "manual"
LIGHTING_CONTROL_MODE_AUTO = "auto"
LIGHTING_CONTROL_MODE_SCHEDULE = "schedule"
LIGHTING_CONTROL_MODE_OCCUPANT = "occupant"
LIGHTING_CONTROL_MODE_OFF = "off"

VALID_LIGHTING_CONTROL_MODES = {
    LIGHTING_CONTROL_MODE_MANUAL,
    LIGHTING_CONTROL_MODE_AUTO,
    LIGHTING_CONTROL_MODE_SCHEDULE,
    LIGHTING_CONTROL_MODE_OCCUPANT,
    LIGHTING_CONTROL_MODE_OFF,
}

DEFAULT_LIGHTS_ON = False
DEFAULT_LIGHTING_DIMMING_FRACTION = 0.0
DEFAULT_REQUESTED_ARTIFICIAL_LIGHTING_LUX = 0.0

DEFAULT_LIGHTING_POWER_DENSITY_W_M2 = 8.0
DEFAULT_INSTALLED_LIGHTING_LUX = 500.0
DEFAULT_LIGHTING_SYSTEM_AVAILABLE = True

LIGHTING_POWER_SOURCE = "ZoneModel_or_ZoneSystemSpec + BuildingLightingControlInputs"

VISUAL_COMFORT_SOURCE = "BuildingLightState + ZoneModel"

DEFAULT_VISUAL_COMFORT_LOWER_FRACTION = 0.80
DEFAULT_VISUAL_COMFORT_UPPER_FRACTION = 2.50
DEFAULT_VISUAL_DARK_FRACTION = 0.10

DEFAULT_GLARE_RISK_INDEX = 0.0
DAYLIGHT_MODEL_INTERFACE_MODE = "runner_facing_daylight_lighting_model"
DEFAULT_DAYLIGHT_DT_MINUTES = 15.0

@dataclass
class DaylightArchitectureDecision:
    """
    Formal architecture decision for ABBEY Phase 7 daylight modelling.

    Phase 7.1 only locks the modelling structure.

    Correct dependency direction:

        weather -> daylight
        graph/window geometry -> daylight
        zone parameters -> daylight
        daylight -> visual comfort/perception

    Not yet:

        daylight -> thermal
        thermal -> daylight
    """

    daylight_model_family: str = DAYLIGHT_MODEL_FAMILY
    lighting_model_family: str = LIGHTING_MODEL_FAMILY

    state_variable: str = DAYLIGHT_STATE_VARIABLE
    derived_variable: str = DAYLIGHT_DERIVED_VARIABLE

    spatial_resolution: str = DAYLIGHT_SPATIAL_RESOLUTION
    multizone_mode: str = DAYLIGHT_MULTIZONE_MODE

    outdoor_boundary_source: str = DAYLIGHT_OUTDOOR_BOUNDARY_SOURCE
    topology_source: str = DAYLIGHT_TOPOLOGY_SOURCE
    parameter_source: str = DAYLIGHT_PARAMETER_SOURCE
    window_source: str = DAYLIGHT_WINDOW_SOURCE

    weather_input: str = DAYLIGHT_WEATHER_INPUT
    window_input: str = DAYLIGHT_WINDOW_INPUT
    zone_input: str = DAYLIGHT_ZONE_INPUT

    control_input_mode: str = DAYLIGHT_CONTROL_INPUT_MODE

    daylight_to_comfort: str = DAYLIGHT_TO_COMFORT
    daylight_to_thermal: str = DAYLIGHT_NOT_TO_THERMAL
    thermal_to_daylight: str = THERMAL_NOT_TO_DAYLIGHT

    solar_consistency_later: str = DAYLIGHT_SOLAR_CONSISTENCY_LATER
    glare_risk_later: str = DAYLIGHT_GLARE_RISK_LATER
    blind_control_later: str = DAYLIGHT_BLIND_CONTROL_LATER
    high_fidelity_radiance_later: str = DAYLIGHT_HIGH_FIDELITY_RADIANCE_LATER

    state_variables: List[str] = None
    derived_variables: List[str] = None

    decision: str = DAYLIGHT_MODEL_DECISION

    def __post_init__(self) -> None:
        if self.state_variables is None:
            self.state_variables = [
                DAYLIGHT_STATE_VARIABLE,
            ]

        if self.derived_variables is None:
            self.derived_variables = [
                DAYLIGHT_DERIVED_VARIABLE,
            ]

        self.daylight_model_family = str(self.daylight_model_family).strip().lower()
        self.lighting_model_family = str(self.lighting_model_family).strip().lower()

        self.state_variable = str(self.state_variable).strip().lower()
        self.derived_variable = str(self.derived_variable).strip().lower()

        self.spatial_resolution = str(self.spatial_resolution).strip().lower()
        self.multizone_mode = str(self.multizone_mode).strip().lower()

        self.outdoor_boundary_source = str(self.outdoor_boundary_source).strip()
        self.topology_source = str(self.topology_source).strip()
        self.parameter_source = str(self.parameter_source).strip()
        self.window_source = str(self.window_source).strip()

        self.weather_input = str(self.weather_input).strip()
        self.window_input = str(self.window_input).strip()
        self.zone_input = str(self.zone_input).strip()

        self.control_input_mode = str(self.control_input_mode).strip().lower()

        self.daylight_to_comfort = str(self.daylight_to_comfort).strip().lower()
        self.daylight_to_thermal = str(self.daylight_to_thermal).strip().lower()
        self.thermal_to_daylight = str(self.thermal_to_daylight).strip().lower()

        self.decision = str(self.decision).strip().lower()

        self._validate()

    def _validate(self) -> None:
        if self.daylight_model_family != DAYLIGHT_MODEL_FAMILY:
            raise ValueError(
                "daylight_model_family must be "
                + DAYLIGHT_MODEL_FAMILY
                + "."
            )

        if self.lighting_model_family != LIGHTING_MODEL_FAMILY:
            raise ValueError(
                "lighting_model_family must be "
                + LIGHTING_MODEL_FAMILY
                + "."
            )

        if self.state_variable != DAYLIGHT_STATE_VARIABLE:
            raise ValueError(
                "Daylight state variable must be indoor_illuminance_lux."
            )

        if self.derived_variable != DAYLIGHT_DERIVED_VARIABLE:
            raise ValueError(
                "Daylight derived variable must be visual_comfort_status."
            )

        if self.spatial_resolution != DAYLIGHT_SPATIAL_RESOLUTION:
            raise ValueError(
                "Daylight model spatial_resolution must be zone."
            )

        if self.multizone_mode != DAYLIGHT_MULTIZONE_MODE:
            raise ValueError(
                "Phase 7 daylight model must use independent zone daylight."
            )

        if self.outdoor_boundary_source != DAYLIGHT_OUTDOOR_BOUNDARY_SOURCE:
            raise ValueError(
                "outdoor_boundary_source must be WeatherState."
            )

        if self.topology_source != DAYLIGHT_TOPOLOGY_SOURCE:
            raise ValueError(
                "topology_source must be BuildingPhysicsGraph."
            )

        if self.parameter_source != DAYLIGHT_PARAMETER_SOURCE:
            raise ValueError(
                "parameter_source must be ZoneModel."
            )

        if self.window_source != DAYLIGHT_WINDOW_SOURCE:
            raise ValueError(
                "window_source must be BoundaryConnection."
            )

        if self.daylight_to_comfort != DAYLIGHT_TO_COMFORT:
            raise ValueError(
                "Phase 7 must include daylight -> visual comfort/perception."
            )

        if self.daylight_to_thermal != DAYLIGHT_NOT_TO_THERMAL:
            raise ValueError(
                "Phase 7 must not send daylight effects back to thermal yet."
            )

        if self.thermal_to_daylight != THERMAL_NOT_TO_DAYLIGHT:
            raise ValueError(
                "Phase 7 must not depend on thermal state for daylight yet."
            )

        if self.state_variables != [DAYLIGHT_STATE_VARIABLE]:
            raise ValueError(
                "state_variables must contain only indoor_illuminance_lux."
            )

        if self.derived_variables != [DAYLIGHT_DERIVED_VARIABLE]:
            raise ValueError(
                "derived_variables must contain only visual_comfort_status."
            )

    def coupling_order(self) -> List[str]:
        return [
            "weather_to_daylight",
            "graph_windows_to_daylight",
            "zone_parameters_to_daylight",
            "daylight_to_visual_comfort",
        ]

    def future_extensions(self) -> List[str]:
        return [
            self.solar_consistency_later,
            self.glare_risk_later,
            self.blind_control_later,
            self.high_fidelity_radiance_later,
        ]

    def copy(self, **updates: Any) -> "DaylightArchitectureDecision":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "daylight_model_family": self.daylight_model_family,
            "lighting_model_family": self.lighting_model_family,
            "state_variable": self.state_variable,
            "derived_variable": self.derived_variable,
            "spatial_resolution": self.spatial_resolution,
            "multizone_mode": self.multizone_mode,
            "outdoor_boundary_source": self.outdoor_boundary_source,
            "topology_source": self.topology_source,
            "parameter_source": self.parameter_source,
            "window_source": self.window_source,
            "weather_input": self.weather_input,
            "window_input": self.window_input,
            "zone_input": self.zone_input,
            "control_input_mode": self.control_input_mode,
            "daylight_to_comfort": self.daylight_to_comfort,
            "daylight_to_thermal": self.daylight_to_thermal,
            "thermal_to_daylight": self.thermal_to_daylight,
            "state_variables": list(self.state_variables),
            "derived_variables": list(self.derived_variables),
            "coupling_order": self.coupling_order(),
            "future_extensions": self.future_extensions(),
            "decision": self.decision,
        }

@dataclass
class ZoneLightState:
    """
    Dynamic daylight / lighting state for one zone.

    Phase 7 state:
        indoor_illuminance_lux

    Components:
        daylight_illuminance_lux
        artificial_lighting_illuminance_lux

    Derived:
        visual_comfort_status
    """

    zone_id: str

    indoor_illuminance_lux: float = DEFAULT_INDOOR_ILLUMINANCE_LUX

    daylight_illuminance_lux: float = DEFAULT_DAYLIGHT_ILLUMINANCE_LUX
    artificial_lighting_illuminance_lux: float = DEFAULT_ARTIFICIAL_LIGHTING_ILLUMINANCE_LUX

    visual_comfort_target_lux: float = DEFAULT_VISUAL_COMFORT_TARGET_LUX
    visual_comfort_status: str = VISUAL_COMFORT_STATUS_DARK

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneLightState.zone_id cannot be empty.")

        self.daylight_illuminance_lux = clamp_illuminance_lux(
            self.daylight_illuminance_lux
        )

        self.artificial_lighting_illuminance_lux = clamp_illuminance_lux(
            self.artificial_lighting_illuminance_lux
        )

        self.indoor_illuminance_lux = clamp_illuminance_lux(
            self.indoor_illuminance_lux
        )

        self.visual_comfort_target_lux = _positive_float(
            self.visual_comfort_target_lux,
            "visual_comfort_target_lux",
            self.zone_id,
        )

        if self.indoor_illuminance_lux <= 0.0:
            self.indoor_illuminance_lux = (
                self.daylight_illuminance_lux
                + self.artificial_lighting_illuminance_lux
            )

        self.indoor_illuminance_lux = clamp_illuminance_lux(
            self.indoor_illuminance_lux
        )

        self.visual_comfort_status = visual_comfort_status_from_illuminance(
            indoor_illuminance_lux=self.indoor_illuminance_lux,
            target_lux=self.visual_comfort_target_lux,
        )

    def copy(self, **updates: Any) -> "ZoneLightState":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "indoor_illuminance_lux": self.indoor_illuminance_lux,
            "daylight_illuminance_lux": self.daylight_illuminance_lux,
            "artificial_lighting_illuminance_lux": self.artificial_lighting_illuminance_lux,
            "visual_comfort_target_lux": self.visual_comfort_target_lux,
            "visual_comfort_status": self.visual_comfort_status,
        }
    
@dataclass
class BuildingLightState:
    """
    Dynamic daylight / lighting state for all zones.
    """

    zone_states: Dict[str, ZoneLightState] = None

    def __post_init__(self) -> None:
        if self.zone_states is None:
            self.zone_states = {}

        cleaned = {}

        for zone_id, state in self.zone_states.items():
            if not isinstance(state, ZoneLightState):
                raise TypeError(
                    "BuildingLightState.zone_states must contain ZoneLightState objects."
                )

            if zone_id != state.zone_id:
                raise ValueError(
                    "BuildingLightState key "
                    + zone_id
                    + " does not match ZoneLightState.zone_id "
                    + state.zone_id
                )

            cleaned[zone_id] = state

        self.zone_states = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_states.keys())

    def has_zone(self, zone_id: str) -> bool:
        return zone_id in self.zone_states

    def get_zone_state(self, zone_id: str) -> ZoneLightState:
        if zone_id not in self.zone_states:
            raise KeyError(
                "Light state for zone "
                + zone_id
                + " not found."
            )

        return self.zone_states[zone_id]

    def set_zone_state(self, zone_state: ZoneLightState) -> None:
        if not isinstance(zone_state, ZoneLightState):
            raise TypeError("zone_state must be ZoneLightState.")

        self.zone_states[zone_state.zone_id] = zone_state

    def indoor_illuminance_by_zone_lux(self) -> Dict[str, float]:
        return {
            zone_id: state.indoor_illuminance_lux
            for zone_id, state in self.zone_states.items()
        }

    def daylight_illuminance_by_zone_lux(self) -> Dict[str, float]:
        return {
            zone_id: state.daylight_illuminance_lux
            for zone_id, state in self.zone_states.items()
        }

    def artificial_lighting_illuminance_by_zone_lux(self) -> Dict[str, float]:
        return {
            zone_id: state.artificial_lighting_illuminance_lux
            for zone_id, state in self.zone_states.items()
        }

    def visual_comfort_status_by_zone(self) -> Dict[str, str]:
        return {
            zone_id: state.visual_comfort_status
            for zone_id, state in self.zone_states.items()
        }

    def copy(self, **updates: Any) -> "BuildingLightState":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "indoor_illuminance_by_zone_lux": self.indoor_illuminance_by_zone_lux(),
            "daylight_illuminance_by_zone_lux": self.daylight_illuminance_by_zone_lux(),
            "artificial_lighting_illuminance_by_zone_lux": self.artificial_lighting_illuminance_by_zone_lux(),
            "visual_comfort_status_by_zone": self.visual_comfort_status_by_zone(),
            "zone_states": {
                zone_id: state.to_dict()
                for zone_id, state in self.zone_states.items()
            },
        }

@dataclass
class WindowDaylightParameters:
    """
    Daylight-relevant parameters for one window boundary.

    Phase 7.3 only maps window parameters.
    It does not calculate indoor illuminance yet.
    """

    boundary_connection_id: str
    zone_id: str

    area_m2: float
    orientation_deg: Optional[float] = None

    visible_transmittance: float = DEFAULT_WINDOW_VISIBLE_TRANSMITTANCE
    frame_fraction: float = DEFAULT_WINDOW_FRAME_FRACTION
    shading_factor: float = DEFAULT_WINDOW_SHADING_FACTOR

    curtain_open: bool = True
    curtain_daylight_reduction_factor: float = DEFAULT_CURTAIN_DAYLIGHT_REDUCTION_FACTOR

    daylight_utilization_factor: float = DEFAULT_WINDOW_DAYLIGHT_UTILIZATION_FACTOR

    source: str = WINDOW_DAYLIGHT_SOURCE

    def __post_init__(self) -> None:
        if not self.boundary_connection_id:
            raise ValueError(
                "WindowDaylightParameters.boundary_connection_id cannot be empty."
            )

        if not self.zone_id:
            raise ValueError("WindowDaylightParameters.zone_id cannot be empty.")

        self.area_m2 = _non_negative_float(
            self.area_m2,
            "area_m2",
            self.boundary_connection_id,
        )

        if self.orientation_deg is not None:
            self.orientation_deg = normalize_orientation_deg(
                self.orientation_deg
            )

        self.visible_transmittance = _clamp_unit_interval(
            self.visible_transmittance
        )

        self.frame_fraction = _clamp_unit_interval(
            self.frame_fraction
        )

        self.shading_factor = _clamp_unit_interval(
            self.shading_factor
        )

        self.curtain_open = bool(self.curtain_open)

        self.curtain_daylight_reduction_factor = _clamp_unit_interval(
            self.curtain_daylight_reduction_factor
        )

        self.daylight_utilization_factor = _clamp_unit_interval(
            self.daylight_utilization_factor
        )

    def effective_glazed_area_m2(self) -> float:
        return self.area_m2 * (1.0 - self.frame_fraction)

    def effective_visible_transmittance(self) -> float:
        curtain_factor = 1.0

        if not self.curtain_open:
            curtain_factor = self.curtain_daylight_reduction_factor

        return (
            self.visible_transmittance
            * self.shading_factor
            * curtain_factor
        )

    def effective_daylight_area_m2(self) -> float:
        return (
            self.effective_glazed_area_m2()
            * self.effective_visible_transmittance()
            * self.daylight_utilization_factor
        )

    def copy(self, **updates: Any) -> "WindowDaylightParameters":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_connection_id": self.boundary_connection_id,
            "zone_id": self.zone_id,
            "area_m2": self.area_m2,
            "orientation_deg": self.orientation_deg,
            "visible_transmittance": self.visible_transmittance,
            "frame_fraction": self.frame_fraction,
            "shading_factor": self.shading_factor,
            "curtain_open": self.curtain_open,
            "curtain_daylight_reduction_factor": self.curtain_daylight_reduction_factor,
            "daylight_utilization_factor": self.daylight_utilization_factor,
            "effective_glazed_area_m2": self.effective_glazed_area_m2(),
            "effective_visible_transmittance": self.effective_visible_transmittance(),
            "effective_daylight_area_m2": self.effective_daylight_area_m2(),
            "source": self.source,
        }
    
@dataclass
class ZoneWindowDaylightParameters:
    """
    Daylight-relevant window parameters for one zone.
    """

    zone_id: str
    windows: List[WindowDaylightParameters] = None

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError(
                "ZoneWindowDaylightParameters.zone_id cannot be empty."
            )

        if self.windows is None:
            self.windows = []

        cleaned = []

        for window in self.windows:
            if not isinstance(window, WindowDaylightParameters):
                raise TypeError(
                    "ZoneWindowDaylightParameters.windows must contain "
                    "WindowDaylightParameters objects."
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

    def add_window(self, window: WindowDaylightParameters) -> None:
        if not isinstance(window, WindowDaylightParameters):
            raise TypeError("window must be WindowDaylightParameters.")

        if window.zone_id != self.zone_id:
            raise ValueError(
                "Window zone_id does not match ZoneWindowDaylightParameters.zone_id."
            )

        self.windows.append(window)

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

    def total_effective_daylight_area_m2(self) -> float:
        return sum(
            window.effective_daylight_area_m2()
            for window in self.windows
        )

    def window_count(self) -> int:
        return len(self.windows)

    def copy(self, **updates: Any) -> "ZoneWindowDaylightParameters":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "window_count": self.window_count(),
            "total_window_area_m2": self.total_window_area_m2(),
            "total_effective_glazed_area_m2": self.total_effective_glazed_area_m2(),
            "total_effective_daylight_area_m2": self.total_effective_daylight_area_m2(),
            "windows": [
                window.to_dict()
                for window in self.windows
            ],
        }


@dataclass
class BuildingWindowDaylightParameters:
    """
    Daylight-relevant window parameters for all zones.
    """

    zone_window_parameters: Dict[str, ZoneWindowDaylightParameters] = None

    def __post_init__(self) -> None:
        if self.zone_window_parameters is None:
            self.zone_window_parameters = {}

        cleaned = {}

        for zone_id, parameters in self.zone_window_parameters.items():
            if not isinstance(parameters, ZoneWindowDaylightParameters):
                raise TypeError(
                    "BuildingWindowDaylightParameters.zone_window_parameters "
                    "must contain ZoneWindowDaylightParameters objects."
                )

            if zone_id != parameters.zone_id:
                raise ValueError(
                    "BuildingWindowDaylightParameters key "
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
    ) -> ZoneWindowDaylightParameters:
        if zone_id not in self.zone_window_parameters:
            return ZoneWindowDaylightParameters(
                zone_id=zone_id,
            )

        return self.zone_window_parameters[zone_id]

    def total_effective_daylight_area_by_zone_m2(self) -> Dict[str, float]:
        return {
            zone_id: parameters.total_effective_daylight_area_m2()
            for zone_id, parameters in self.zone_window_parameters.items()
        }

    def window_count_by_zone(self) -> Dict[str, int]:
        return {
            zone_id: parameters.window_count()
            for zone_id, parameters in self.zone_window_parameters.items()
        }

    def copy(self, **updates: Any) -> "BuildingWindowDaylightParameters":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_effective_daylight_area_by_zone_m2": self.total_effective_daylight_area_by_zone_m2(),
            "window_count_by_zone": self.window_count_by_zone(),
            "zone_window_parameters": {
                zone_id: parameters.to_dict()
                for zone_id, parameters in self.zone_window_parameters.items()
            },
        }

@dataclass
class OutdoorDaylightBoundary:
    """
    Outdoor daylight boundary condition.

    Phase 7.4 converts WeatherState into daylight-ready outdoor inputs.

    Main daylight input:
        outdoor_illuminance_lux

    Supporting weather fields:
        direct_normal_radiation_w_m2
        diffuse_horizontal_radiation_w_m2
        global_horizontal_radiation_w_m2
        sky_condition
    """

    outdoor_illuminance_lux: float = DEFAULT_OUTDOOR_ILLUMINANCE_LUX

    direct_normal_radiation_w_m2: float = DEFAULT_DIRECT_NORMAL_RADIATION_W_M2
    diffuse_horizontal_radiation_w_m2: float = DEFAULT_DIFFUSE_HORIZONTAL_RADIATION_W_M2
    global_horizontal_radiation_w_m2: float = DEFAULT_GLOBAL_HORIZONTAL_RADIATION_W_M2

    sky_condition: str = DEFAULT_SKY_CONDITION

    source: str = OUTDOOR_DAYLIGHT_BOUNDARY_SOURCE

    def __post_init__(self) -> None:
        self.outdoor_illuminance_lux = clamp_illuminance_lux(
            self.outdoor_illuminance_lux
        )

        self.direct_normal_radiation_w_m2 = _non_negative_float(
            self.direct_normal_radiation_w_m2,
            "direct_normal_radiation_w_m2",
            "OutdoorDaylightBoundary",
        )

        self.diffuse_horizontal_radiation_w_m2 = _non_negative_float(
            self.diffuse_horizontal_radiation_w_m2,
            "diffuse_horizontal_radiation_w_m2",
            "OutdoorDaylightBoundary",
        )

        self.global_horizontal_radiation_w_m2 = _non_negative_float(
            self.global_horizontal_radiation_w_m2,
            "global_horizontal_radiation_w_m2",
            "OutdoorDaylightBoundary",
        )

        self.sky_condition = str(self.sky_condition).strip().lower()

        if not self.sky_condition:
            self.sky_condition = DEFAULT_SKY_CONDITION

    def has_daylight(self) -> bool:
        return self.outdoor_illuminance_lux > 0.0

    def copy(self, **updates: Any) -> "OutdoorDaylightBoundary":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outdoor_illuminance_lux": self.outdoor_illuminance_lux,
            "direct_normal_radiation_w_m2": self.direct_normal_radiation_w_m2,
            "diffuse_horizontal_radiation_w_m2": self.diffuse_horizontal_radiation_w_m2,
            "global_horizontal_radiation_w_m2": self.global_horizontal_radiation_w_m2,
            "sky_condition": self.sky_condition,
            "has_daylight": self.has_daylight(),
            "source": self.source,
        }

@dataclass
class WindowIndoorDaylightRecord:
    """
    Indoor daylight contribution from one window.

    Simplified Phase 7.5 estimate:

        indoor_lux_contribution =
            outdoor_lux
            * effective_daylight_area_m2
            / floor_area_m2

    This is not a Radiance model.
    It is a lightweight zone-level daylight estimate.
    """

    boundary_connection_id: str
    zone_id: str

    outdoor_illuminance_lux: float
    floor_area_m2: float

    effective_daylight_area_m2: float
    indoor_daylight_illuminance_lux: float

    source: str = DAYLIGHT_ESTIMATE_SOURCE

    def __post_init__(self) -> None:
        if not self.boundary_connection_id:
            raise ValueError(
                "WindowIndoorDaylightRecord.boundary_connection_id cannot be empty."
            )

        if not self.zone_id:
            raise ValueError("WindowIndoorDaylightRecord.zone_id cannot be empty.")

        self.outdoor_illuminance_lux = clamp_illuminance_lux(
            self.outdoor_illuminance_lux
        )

        self.floor_area_m2 = _positive_float(
            self.floor_area_m2,
            "floor_area_m2",
            self.zone_id,
        )

        self.effective_daylight_area_m2 = _non_negative_float(
            self.effective_daylight_area_m2,
            "effective_daylight_area_m2",
            self.boundary_connection_id,
        )

        self.indoor_daylight_illuminance_lux = clamp_illuminance_lux(
            self.indoor_daylight_illuminance_lux
        )

    def copy(self, **updates: Any) -> "WindowIndoorDaylightRecord":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_connection_id": self.boundary_connection_id,
            "zone_id": self.zone_id,
            "outdoor_illuminance_lux": self.outdoor_illuminance_lux,
            "floor_area_m2": self.floor_area_m2,
            "effective_daylight_area_m2": self.effective_daylight_area_m2,
            "indoor_daylight_illuminance_lux": self.indoor_daylight_illuminance_lux,
            "source": self.source,
        }
    
@dataclass
class ZoneIndoorDaylightResult:
    """
    Indoor daylight estimate for one zone.
    """

    zone_id: str
    daylight_illuminance_lux: float = 0.0
    window_records: List[WindowIndoorDaylightRecord] = None

    source: str = DAYLIGHT_ESTIMATE_SOURCE

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneIndoorDaylightResult.zone_id cannot be empty.")

        self.daylight_illuminance_lux = clamp_illuminance_lux(
            self.daylight_illuminance_lux
        )

        if self.window_records is None:
            self.window_records = []

        cleaned = []

        for record in self.window_records:
            if not isinstance(record, WindowIndoorDaylightRecord):
                raise TypeError(
                    "ZoneIndoorDaylightResult.window_records must contain "
                    "WindowIndoorDaylightRecord objects."
                )

            if record.zone_id != self.zone_id:
                raise ValueError(
                    "Window record zone_id "
                    + record.zone_id
                    + " does not match zone result "
                    + self.zone_id
                )

            cleaned.append(record)

        self.window_records = cleaned

    def window_count(self) -> int:
        return len(self.window_records)

    def to_light_state(
        self,
        artificial_lighting_illuminance_lux: float = 0.0,
        visual_comfort_target_lux: float = DEFAULT_VISUAL_COMFORT_TARGET_LUX,
    ) -> ZoneLightState:
        return ZoneLightState(
            zone_id=self.zone_id,
            daylight_illuminance_lux=self.daylight_illuminance_lux,
            artificial_lighting_illuminance_lux=artificial_lighting_illuminance_lux,
            indoor_illuminance_lux=(
                self.daylight_illuminance_lux
                + artificial_lighting_illuminance_lux
            ),
            visual_comfort_target_lux=visual_comfort_target_lux,
        )

    def copy(self, **updates: Any) -> "ZoneIndoorDaylightResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "daylight_illuminance_lux": self.daylight_illuminance_lux,
            "window_count": self.window_count(),
            "window_records": [
                record.to_dict()
                for record in self.window_records
            ],
            "source": self.source,
        }


@dataclass
class BuildingIndoorDaylightResult:
    """
    Indoor daylight estimate for all zones.
    """

    zone_results: Dict[str, ZoneIndoorDaylightResult] = None

    source: str = DAYLIGHT_ESTIMATE_SOURCE

    def __post_init__(self) -> None:
        if self.zone_results is None:
            self.zone_results = {}

        cleaned = {}

        for zone_id, result in self.zone_results.items():
            if not isinstance(result, ZoneIndoorDaylightResult):
                raise TypeError(
                    "BuildingIndoorDaylightResult.zone_results must contain "
                    "ZoneIndoorDaylightResult objects."
                )

            if zone_id != result.zone_id:
                raise ValueError(
                    "BuildingIndoorDaylightResult key "
                    + zone_id
                    + " does not match result.zone_id "
                    + result.zone_id
                )

            cleaned[zone_id] = result

        self.zone_results = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_results.keys())

    def has_zone(self, zone_id: str) -> bool:
        return zone_id in self.zone_results

    def get_zone_result(self, zone_id: str) -> ZoneIndoorDaylightResult:
        if zone_id not in self.zone_results:
            return ZoneIndoorDaylightResult(
                zone_id=zone_id,
                daylight_illuminance_lux=0.0,
                window_records=[],
            )

        return self.zone_results[zone_id]

    def daylight_illuminance_by_zone_lux(self) -> Dict[str, float]:
        return {
            zone_id: result.daylight_illuminance_lux
            for zone_id, result in self.zone_results.items()
        }

    def to_light_state(
        self,
        building_model: Any = None,
        artificial_lighting_by_zone_lux: Dict[str, float] = None,
    ) -> BuildingLightState:
        if artificial_lighting_by_zone_lux is None:
            artificial_lighting_by_zone_lux = {}

        zone_states = {}

        for zone_id, result in self.zone_results.items():
            target_lux = DEFAULT_VISUAL_COMFORT_TARGET_LUX

            if building_model is not None and hasattr(building_model, "all_zone_models"):
                zone_models = building_model.all_zone_models()

                if zone_id in zone_models:
                    target_lux = _get_attr_or_default(
                        zone_models[zone_id],
                        "visual_comfort_target_lux",
                        DEFAULT_VISUAL_COMFORT_TARGET_LUX,
                    )

            zone_states[zone_id] = result.to_light_state(
                artificial_lighting_illuminance_lux=artificial_lighting_by_zone_lux.get(zone_id, 0.0),
                visual_comfort_target_lux=target_lux,
            )

        return BuildingLightState(
            zone_states=zone_states,
        )

    def copy(self, **updates: Any) -> "BuildingIndoorDaylightResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "daylight_illuminance_by_zone_lux": self.daylight_illuminance_by_zone_lux(),
            "zone_results": {
                zone_id: result.to_dict()
                for zone_id, result in self.zone_results.items()
            },
            "source": self.source,
        }
    
@dataclass
class ZoneLightingControlInput:
    """
    Clean bridge input for artificial lighting control in one zone.

    Agents/controllers/schedules are converted outside daylight.py.

    daylight.py only sees:
    - lights_on
    - dimming fraction
    - requested artificial lighting lux
    """

    zone_id: str

    lights_on: bool = DEFAULT_LIGHTS_ON
    dimming_fraction: float = DEFAULT_LIGHTING_DIMMING_FRACTION
    requested_artificial_lighting_lux: float = DEFAULT_REQUESTED_ARTIFICIAL_LIGHTING_LUX

    control_mode: str = LIGHTING_CONTROL_MODE_MANUAL
    source: str = LIGHTING_CONTROL_SOURCE_EXTERNAL_BRIDGE

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneLightingControlInput.zone_id cannot be empty.")

        self.lights_on = bool(self.lights_on)

        self.dimming_fraction = _clamp_unit_interval(
            self.dimming_fraction
        )

        self.requested_artificial_lighting_lux = clamp_illuminance_lux(
            self.requested_artificial_lighting_lux
        )

        self.control_mode = str(self.control_mode).strip().lower()

        if self.control_mode not in VALID_LIGHTING_CONTROL_MODES:
            raise ValueError(
                "Invalid lighting control_mode: "
                + self.control_mode
                + ". Valid modes are: "
                + str(sorted(list(VALID_LIGHTING_CONTROL_MODES)))
            )

        if not self.lights_on:
            self.dimming_fraction = 0.0
            self.requested_artificial_lighting_lux = 0.0

    def is_active(self) -> bool:
        return (
            self.lights_on
            and self.dimming_fraction > 0.0
            and self.requested_artificial_lighting_lux > 0.0
        )

    def copy(self, **updates: Any) -> "ZoneLightingControlInput":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "lights_on": self.lights_on,
            "dimming_fraction": self.dimming_fraction,
            "requested_artificial_lighting_lux": self.requested_artificial_lighting_lux,
            "control_mode": self.control_mode,
            "is_active": self.is_active(),
            "source": self.source,
        }
    
@dataclass
class BuildingLightingControlInputs:
    """
    Building-level container for clean artificial lighting control inputs.

    Structure:
        controls_by_zone = {
            zone_id: ZoneLightingControlInput(...)
        }
    """

    controls_by_zone: Dict[str, ZoneLightingControlInput] = None
    source: str = LIGHTING_CONTROL_SOURCE_EXTERNAL_BRIDGE

    def __post_init__(self) -> None:
        if self.controls_by_zone is None:
            self.controls_by_zone = {}

        cleaned = {}

        for zone_id, control in self.controls_by_zone.items():
            if not isinstance(control, ZoneLightingControlInput):
                raise TypeError(
                    "BuildingLightingControlInputs.controls_by_zone must contain "
                    "ZoneLightingControlInput objects."
                )

            if zone_id != control.zone_id:
                raise ValueError(
                    "BuildingLightingControlInputs key "
                    + zone_id
                    + " does not match control.zone_id "
                    + control.zone_id
                )

            cleaned[zone_id] = control

        self.controls_by_zone = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.controls_by_zone.keys())

    def has_zone(self, zone_id: str) -> bool:
        return zone_id in self.controls_by_zone

    def get_control_for_zone(
        self,
        zone_id: str,
    ) -> ZoneLightingControlInput:
        if zone_id not in self.controls_by_zone:
            return ZoneLightingControlInput(
                zone_id=zone_id,
                lights_on=False,
                dimming_fraction=0.0,
                requested_artificial_lighting_lux=0.0,
                control_mode=LIGHTING_CONTROL_MODE_OFF,
                source="default_lighting_off",
            )

        return self.controls_by_zone[zone_id]

    def set_control(
        self,
        control: ZoneLightingControlInput,
    ) -> None:
        if not isinstance(control, ZoneLightingControlInput):
            raise TypeError("control must be ZoneLightingControlInput.")

        self.controls_by_zone[control.zone_id] = control

    def active_zone_ids(self) -> List[str]:
        return [
            zone_id
            for zone_id, control in self.controls_by_zone.items()
            if control.is_active()
        ]

    def requested_artificial_lighting_by_zone_lux(self) -> Dict[str, float]:
        return {
            zone_id: control.requested_artificial_lighting_lux
            for zone_id, control in self.controls_by_zone.items()
        }

    def dimming_fraction_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: control.dimming_fraction
            for zone_id, control in self.controls_by_zone.items()
        }

    def lights_on_by_zone(self) -> Dict[str, bool]:
        return {
            zone_id: control.lights_on
            for zone_id, control in self.controls_by_zone.items()
        }

    def copy(self, **updates: Any) -> "BuildingLightingControlInputs":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_zone_ids": self.active_zone_ids(),
            "requested_artificial_lighting_by_zone_lux": self.requested_artificial_lighting_by_zone_lux(),
            "dimming_fraction_by_zone": self.dimming_fraction_by_zone(),
            "lights_on_by_zone": self.lights_on_by_zone(),
            "controls_by_zone": {
                zone_id: control.to_dict()
                for zone_id, control in self.controls_by_zone.items()
            },
            "source": self.source,
        }
    
@dataclass
class ZoneLightingParameters:
    """
    Static artificial-lighting parameters for one zone.

    Phase 7.7:
    - installed lighting level
    - lighting power density
    - max lighting power

    No lighting control logic is stored here.
    """

    zone_id: str

    floor_area_m2: float
    installed_lighting_lux: float = DEFAULT_INSTALLED_LIGHTING_LUX
    lighting_power_density_w_m2: float = DEFAULT_LIGHTING_POWER_DENSITY_W_M2

    lighting_available: bool = DEFAULT_LIGHTING_SYSTEM_AVAILABLE

    source: str = LIGHTING_POWER_SOURCE

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneLightingParameters.zone_id cannot be empty.")

        self.floor_area_m2 = _positive_float(
            self.floor_area_m2,
            "floor_area_m2",
            self.zone_id,
        )

        self.installed_lighting_lux = clamp_illuminance_lux(
            self.installed_lighting_lux
        )

        self.lighting_power_density_w_m2 = _non_negative_float(
            self.lighting_power_density_w_m2,
            "lighting_power_density_w_m2",
            self.zone_id,
        )

        self.lighting_available = bool(self.lighting_available)

        if not self.lighting_available:
            self.installed_lighting_lux = 0.0
            self.lighting_power_density_w_m2 = 0.0

    def max_lighting_power_w(self) -> float:
        return self.floor_area_m2 * self.lighting_power_density_w_m2

    def copy(self, **updates: Any) -> "ZoneLightingParameters":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "floor_area_m2": self.floor_area_m2,
            "installed_lighting_lux": self.installed_lighting_lux,
            "lighting_power_density_w_m2": self.lighting_power_density_w_m2,
            "lighting_available": self.lighting_available,
            "max_lighting_power_w": self.max_lighting_power_w(),
            "source": self.source,
        }


@dataclass
class BuildingLightingParameters:
    """
    Static artificial-lighting parameters for all zones.
    """

    zone_parameters: Dict[str, ZoneLightingParameters] = None

    def __post_init__(self) -> None:
        if self.zone_parameters is None:
            self.zone_parameters = {}

        cleaned = {}

        for zone_id, parameters in self.zone_parameters.items():
            if not isinstance(parameters, ZoneLightingParameters):
                raise TypeError(
                    "BuildingLightingParameters.zone_parameters must contain "
                    "ZoneLightingParameters objects."
                )

            if zone_id != parameters.zone_id:
                raise ValueError(
                    "BuildingLightingParameters key "
                    + zone_id
                    + " does not match parameters.zone_id "
                    + parameters.zone_id
                )

            cleaned[zone_id] = parameters

        self.zone_parameters = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_parameters.keys())

    def get_zone_parameters(self, zone_id: str) -> ZoneLightingParameters:
        if zone_id not in self.zone_parameters:
            raise KeyError(
                "Lighting parameters for zone "
                + zone_id
                + " not found."
            )

        return self.zone_parameters[zone_id]

    def max_lighting_power_by_zone_w(self) -> Dict[str, float]:
        return {
            zone_id: parameters.max_lighting_power_w()
            for zone_id, parameters in self.zone_parameters.items()
        }

    def copy(self, **updates: Any) -> "BuildingLightingParameters":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_lighting_power_by_zone_w": self.max_lighting_power_by_zone_w(),
            "zone_parameters": {
                zone_id: parameters.to_dict()
                for zone_id, parameters in self.zone_parameters.items()
            },
        }
    
@dataclass
class ZoneLightingPowerResult:
    """
    Artificial lighting result for one zone.

    Delivered lighting:
        artificial_lighting_illuminance_lux

    Electric power:
        lighting_power_w

    Energy:
        lighting_energy_wh
    """

    zone_id: str

    lights_on: bool
    dimming_fraction: float
    requested_artificial_lighting_lux: float

    installed_lighting_lux: float
    artificial_lighting_illuminance_lux: float

    lighting_power_w: float
    lighting_energy_wh: float

    control_mode: str = LIGHTING_CONTROL_MODE_MANUAL
    source: str = LIGHTING_POWER_SOURCE

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneLightingPowerResult.zone_id cannot be empty.")

        self.lights_on = bool(self.lights_on)

        self.dimming_fraction = _clamp_unit_interval(
            self.dimming_fraction
        )

        self.requested_artificial_lighting_lux = clamp_illuminance_lux(
            self.requested_artificial_lighting_lux
        )

        self.installed_lighting_lux = clamp_illuminance_lux(
            self.installed_lighting_lux
        )

        self.artificial_lighting_illuminance_lux = clamp_illuminance_lux(
            self.artificial_lighting_illuminance_lux
        )

        self.lighting_power_w = _non_negative_float(
            self.lighting_power_w,
            "lighting_power_w",
            self.zone_id,
        )

        self.lighting_energy_wh = _non_negative_float(
            self.lighting_energy_wh,
            "lighting_energy_wh",
            self.zone_id,
        )

        self.control_mode = str(self.control_mode).strip().lower()

    def copy(self, **updates: Any) -> "ZoneLightingPowerResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "lights_on": self.lights_on,
            "dimming_fraction": self.dimming_fraction,
            "requested_artificial_lighting_lux": self.requested_artificial_lighting_lux,
            "installed_lighting_lux": self.installed_lighting_lux,
            "artificial_lighting_illuminance_lux": self.artificial_lighting_illuminance_lux,
            "lighting_power_w": self.lighting_power_w,
            "lighting_energy_wh": self.lighting_energy_wh,
            "control_mode": self.control_mode,
            "source": self.source,
        }


@dataclass
class BuildingLightingPowerResult:
    """
    Artificial lighting result for all zones.
    """

    zone_results: Dict[str, ZoneLightingPowerResult] = None

    dt_minutes: float = 15.0
    source: str = LIGHTING_POWER_SOURCE

    def __post_init__(self) -> None:
        if self.zone_results is None:
            self.zone_results = {}

        cleaned = {}

        for zone_id, result in self.zone_results.items():
            if not isinstance(result, ZoneLightingPowerResult):
                raise TypeError(
                    "BuildingLightingPowerResult.zone_results must contain "
                    "ZoneLightingPowerResult objects."
                )

            if zone_id != result.zone_id:
                raise ValueError(
                    "BuildingLightingPowerResult key "
                    + zone_id
                    + " does not match result.zone_id "
                    + result.zone_id
                )

            cleaned[zone_id] = result

        self.zone_results = cleaned

        self.dt_minutes = _positive_float(
            self.dt_minutes,
            "dt_minutes",
            "BuildingLightingPowerResult",
        )

    def zone_ids(self) -> List[str]:
        return list(self.zone_results.keys())

    def get_zone_result(self, zone_id: str) -> ZoneLightingPowerResult:
        if zone_id not in self.zone_results:
            return ZoneLightingPowerResult(
                zone_id=zone_id,
                lights_on=False,
                dimming_fraction=0.0,
                requested_artificial_lighting_lux=0.0,
                installed_lighting_lux=0.0,
                artificial_lighting_illuminance_lux=0.0,
                lighting_power_w=0.0,
                lighting_energy_wh=0.0,
                control_mode=LIGHTING_CONTROL_MODE_OFF,
                source="default_lighting_off",
            )

        return self.zone_results[zone_id]

    def artificial_lighting_by_zone_lux(self) -> Dict[str, float]:
        return {
            zone_id: result.artificial_lighting_illuminance_lux
            for zone_id, result in self.zone_results.items()
        }

    def lighting_power_by_zone_w(self) -> Dict[str, float]:
        return {
            zone_id: result.lighting_power_w
            for zone_id, result in self.zone_results.items()
        }

    def lighting_energy_by_zone_wh(self) -> Dict[str, float]:
        return {
            zone_id: result.lighting_energy_wh
            for zone_id, result in self.zone_results.items()
        }

    def total_lighting_power_w(self) -> float:
        return sum(
            result.lighting_power_w
            for result in self.zone_results.values()
        )

    def total_lighting_energy_wh(self) -> float:
        return sum(
            result.lighting_energy_wh
            for result in self.zone_results.values()
        )

    def copy(self, **updates: Any) -> "BuildingLightingPowerResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artificial_lighting_by_zone_lux": self.artificial_lighting_by_zone_lux(),
            "lighting_power_by_zone_w": self.lighting_power_by_zone_w(),
            "lighting_energy_by_zone_wh": self.lighting_energy_by_zone_wh(),
            "total_lighting_power_w": self.total_lighting_power_w(),
            "total_lighting_energy_wh": self.total_lighting_energy_wh(),
            "dt_minutes": self.dt_minutes,
            "zone_results": {
                zone_id: result.to_dict()
                for zone_id, result in self.zone_results.items()
            },
            "source": self.source,
        }

@dataclass
class ZoneVisualComfortParameters:
    """
    Static visual-comfort parameters for one zone.

    Phase 7.8:
    - target illuminance
    - dark threshold
    - underlit / comfortable / overlit thresholds

    No glare model yet.
    """

    zone_id: str

    visual_comfort_target_lux: float = DEFAULT_VISUAL_COMFORT_TARGET_LUX

    dark_fraction: float = DEFAULT_VISUAL_DARK_FRACTION
    lower_comfort_fraction: float = DEFAULT_VISUAL_COMFORT_LOWER_FRACTION
    upper_comfort_fraction: float = DEFAULT_VISUAL_COMFORT_UPPER_FRACTION

    source: str = VISUAL_COMFORT_SOURCE

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneVisualComfortParameters.zone_id cannot be empty.")

        self.visual_comfort_target_lux = _positive_float(
            self.visual_comfort_target_lux,
            "visual_comfort_target_lux",
            self.zone_id,
        )

        self.dark_fraction = _clamp_unit_interval(
            self.dark_fraction
        )

        self.lower_comfort_fraction = _positive_float(
            self.lower_comfort_fraction,
            "lower_comfort_fraction",
            self.zone_id,
        )

        self.upper_comfort_fraction = _positive_float(
            self.upper_comfort_fraction,
            "upper_comfort_fraction",
            self.zone_id,
        )

        if self.dark_fraction >= self.lower_comfort_fraction:
            raise ValueError(
                "dark_fraction must be lower than lower_comfort_fraction."
            )

        if self.lower_comfort_fraction >= self.upper_comfort_fraction:
            raise ValueError(
                "lower_comfort_fraction must be lower than upper_comfort_fraction."
            )

    def dark_threshold_lux(self) -> float:
        return self.visual_comfort_target_lux * self.dark_fraction

    def lower_comfort_threshold_lux(self) -> float:
        return self.visual_comfort_target_lux * self.lower_comfort_fraction

    def upper_comfort_threshold_lux(self) -> float:
        return self.visual_comfort_target_lux * self.upper_comfort_fraction

    def copy(self, **updates: Any) -> "ZoneVisualComfortParameters":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "visual_comfort_target_lux": self.visual_comfort_target_lux,
            "dark_fraction": self.dark_fraction,
            "lower_comfort_fraction": self.lower_comfort_fraction,
            "upper_comfort_fraction": self.upper_comfort_fraction,
            "dark_threshold_lux": self.dark_threshold_lux(),
            "lower_comfort_threshold_lux": self.lower_comfort_threshold_lux(),
            "upper_comfort_threshold_lux": self.upper_comfort_threshold_lux(),
            "source": self.source,
        }

@dataclass
class BuildingVisualComfortParameters:
    """
    Static visual-comfort parameters for all zones.
    """

    zone_parameters: Dict[str, ZoneVisualComfortParameters] = None

    def __post_init__(self) -> None:
        if self.zone_parameters is None:
            self.zone_parameters = {}

        cleaned = {}

        for zone_id, parameters in self.zone_parameters.items():
            if not isinstance(parameters, ZoneVisualComfortParameters):
                raise TypeError(
                    "BuildingVisualComfortParameters.zone_parameters must contain "
                    "ZoneVisualComfortParameters objects."
                )

            if zone_id != parameters.zone_id:
                raise ValueError(
                    "BuildingVisualComfortParameters key "
                    + zone_id
                    + " does not match parameters.zone_id "
                    + parameters.zone_id
                )

            cleaned[zone_id] = parameters

        self.zone_parameters = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_parameters.keys())

    def get_zone_parameters(self, zone_id: str) -> ZoneVisualComfortParameters:
        if zone_id not in self.zone_parameters:
            raise KeyError(
                "Visual comfort parameters for zone "
                + zone_id
                + " not found."
            )

        return self.zone_parameters[zone_id]

    def target_lux_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: parameters.visual_comfort_target_lux
            for zone_id, parameters in self.zone_parameters.items()
        }

    def copy(self, **updates: Any) -> "BuildingVisualComfortParameters":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_lux_by_zone": self.target_lux_by_zone(),
            "zone_parameters": {
                zone_id: parameters.to_dict()
                for zone_id, parameters in self.zone_parameters.items()
            },
        }
    
@dataclass
class ZoneVisualComfortResult:
    """
    Visual comfort result for one zone.

    Phase 7.8:
    - evaluates illuminance against target
    - no glare model yet
    """

    zone_id: str

    indoor_illuminance_lux: float
    daylight_illuminance_lux: float
    artificial_lighting_illuminance_lux: float

    visual_comfort_target_lux: float

    visual_comfort_status: str
    illuminance_ratio_to_target: float

    glare_risk_index: float = DEFAULT_GLARE_RISK_INDEX

    source: str = VISUAL_COMFORT_SOURCE

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneVisualComfortResult.zone_id cannot be empty.")

        self.indoor_illuminance_lux = clamp_illuminance_lux(
            self.indoor_illuminance_lux
        )

        self.daylight_illuminance_lux = clamp_illuminance_lux(
            self.daylight_illuminance_lux
        )

        self.artificial_lighting_illuminance_lux = clamp_illuminance_lux(
            self.artificial_lighting_illuminance_lux
        )

        self.visual_comfort_target_lux = _positive_float(
            self.visual_comfort_target_lux,
            "visual_comfort_target_lux",
            self.zone_id,
        )

        self.illuminance_ratio_to_target = _non_negative_float(
            self.illuminance_ratio_to_target,
            "illuminance_ratio_to_target",
            self.zone_id,
        )

        self.visual_comfort_status = str(
            self.visual_comfort_status
        ).strip().lower()

        if self.visual_comfort_status not in {
            VISUAL_COMFORT_STATUS_DARK,
            VISUAL_COMFORT_STATUS_UNDERLIT,
            VISUAL_COMFORT_STATUS_COMFORTABLE,
            VISUAL_COMFORT_STATUS_OVERLIT,
        }:
            raise ValueError(
                "Invalid visual_comfort_status: "
                + self.visual_comfort_status
            )

        self.glare_risk_index = _clamp_unit_interval(
            self.glare_risk_index
        )

    def is_comfortable(self) -> bool:
        return self.visual_comfort_status == VISUAL_COMFORT_STATUS_COMFORTABLE

    def needs_artificial_lighting(self) -> bool:
        return self.visual_comfort_status in {
            VISUAL_COMFORT_STATUS_DARK,
            VISUAL_COMFORT_STATUS_UNDERLIT,
        }

    def copy(self, **updates: Any) -> "ZoneVisualComfortResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "indoor_illuminance_lux": self.indoor_illuminance_lux,
            "daylight_illuminance_lux": self.daylight_illuminance_lux,
            "artificial_lighting_illuminance_lux": self.artificial_lighting_illuminance_lux,
            "visual_comfort_target_lux": self.visual_comfort_target_lux,
            "visual_comfort_status": self.visual_comfort_status,
            "illuminance_ratio_to_target": self.illuminance_ratio_to_target,
            "is_comfortable": self.is_comfortable(),
            "needs_artificial_lighting": self.needs_artificial_lighting(),
            "glare_risk_index": self.glare_risk_index,
            "source": self.source,
        }


@dataclass
class BuildingVisualComfortResult:
    """
    Visual comfort result for all zones.
    """

    zone_results: Dict[str, ZoneVisualComfortResult] = None

    source: str = VISUAL_COMFORT_SOURCE

    def __post_init__(self) -> None:
        if self.zone_results is None:
            self.zone_results = {}

        cleaned = {}

        for zone_id, result in self.zone_results.items():
            if not isinstance(result, ZoneVisualComfortResult):
                raise TypeError(
                    "BuildingVisualComfortResult.zone_results must contain "
                    "ZoneVisualComfortResult objects."
                )

            if zone_id != result.zone_id:
                raise ValueError(
                    "BuildingVisualComfortResult key "
                    + zone_id
                    + " does not match result.zone_id "
                    + result.zone_id
                )

            cleaned[zone_id] = result

        self.zone_results = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_results.keys())

    def get_zone_result(self, zone_id: str) -> ZoneVisualComfortResult:
        if zone_id not in self.zone_results:
            raise KeyError(
                "Visual comfort result for zone "
                + zone_id
                + " not found."
            )

        return self.zone_results[zone_id]

    def visual_comfort_status_by_zone(self) -> Dict[str, str]:
        return {
            zone_id: result.visual_comfort_status
            for zone_id, result in self.zone_results.items()
        }

    def illuminance_ratio_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: result.illuminance_ratio_to_target
            for zone_id, result in self.zone_results.items()
        }

    def comfortable_zone_ids(self) -> List[str]:
        return [
            zone_id
            for zone_id, result in self.zone_results.items()
            if result.is_comfortable()
        ]

    def zones_needing_artificial_lighting(self) -> List[str]:
        return [
            zone_id
            for zone_id, result in self.zone_results.items()
            if result.needs_artificial_lighting()
        ]

    def copy(self, **updates: Any) -> "BuildingVisualComfortResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "visual_comfort_status_by_zone": self.visual_comfort_status_by_zone(),
            "illuminance_ratio_by_zone": self.illuminance_ratio_by_zone(),
            "comfortable_zone_ids": self.comfortable_zone_ids(),
            "zones_needing_artificial_lighting": self.zones_needing_artificial_lighting(),
            "zone_results": {
                zone_id: result.to_dict()
                for zone_id, result in self.zone_results.items()
            },
            "source": self.source,
        }
    
@dataclass
class ZoneDaylightDebugRecord:
    """
    Debug record for one zone after one daylight/lighting timestep.
    """

    zone_id: str

    outdoor_illuminance_lux: float
    daylight_illuminance_lux: float
    artificial_lighting_illuminance_lux: float
    indoor_illuminance_lux: float

    visual_comfort_target_lux: float
    visual_comfort_status: str

    lighting_power_w: float = 0.0
    lighting_energy_wh: float = 0.0

    lights_on: bool = False
    dimming_fraction: float = 0.0

    dt_minutes: float = DEFAULT_DAYLIGHT_DT_MINUTES
    source: str = DAYLIGHT_MODEL_INTERFACE_MODE

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneDaylightDebugRecord.zone_id cannot be empty.")

        self.outdoor_illuminance_lux = clamp_illuminance_lux(
            self.outdoor_illuminance_lux
        )

        self.daylight_illuminance_lux = clamp_illuminance_lux(
            self.daylight_illuminance_lux
        )

        self.artificial_lighting_illuminance_lux = clamp_illuminance_lux(
            self.artificial_lighting_illuminance_lux
        )

        self.indoor_illuminance_lux = clamp_illuminance_lux(
            self.indoor_illuminance_lux
        )

        self.visual_comfort_target_lux = _positive_float(
            self.visual_comfort_target_lux,
            "visual_comfort_target_lux",
            self.zone_id,
        )

        self.visual_comfort_status = str(
            self.visual_comfort_status
        ).strip().lower()

        self.lighting_power_w = _non_negative_float(
            self.lighting_power_w,
            "lighting_power_w",
            self.zone_id,
        )

        self.lighting_energy_wh = _non_negative_float(
            self.lighting_energy_wh,
            "lighting_energy_wh",
            self.zone_id,
        )

        self.lights_on = bool(self.lights_on)

        self.dimming_fraction = _clamp_unit_interval(
            self.dimming_fraction
        )

        self.dt_minutes = _positive_float(
            self.dt_minutes,
            "dt_minutes",
            self.zone_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "outdoor_illuminance_lux": self.outdoor_illuminance_lux,
            "daylight_illuminance_lux": self.daylight_illuminance_lux,
            "artificial_lighting_illuminance_lux": self.artificial_lighting_illuminance_lux,
            "indoor_illuminance_lux": self.indoor_illuminance_lux,
            "visual_comfort_target_lux": self.visual_comfort_target_lux,
            "visual_comfort_status": self.visual_comfort_status,
            "lighting_power_w": self.lighting_power_w,
            "lighting_energy_wh": self.lighting_energy_wh,
            "lights_on": self.lights_on,
            "dimming_fraction": self.dimming_fraction,
            "dt_minutes": self.dt_minutes,
            "source": self.source,
        }


@dataclass
class DaylightStepResult:
    """
    Public result returned by DaylightModel.step(...).
    """

    updated_light_state: BuildingLightState

    outdoor_daylight_boundary: OutdoorDaylightBoundary
    window_daylight_parameters: BuildingWindowDaylightParameters
    daylight_result: BuildingIndoorDaylightResult
    lighting_power_result: BuildingLightingPowerResult
    visual_comfort_result: BuildingVisualComfortResult

    lighting_control_inputs: BuildingLightingControlInputs

    debug_records: List[ZoneDaylightDebugRecord] = None

    dt_minutes: float = DEFAULT_DAYLIGHT_DT_MINUTES
    interface_mode: str = DAYLIGHT_MODEL_INTERFACE_MODE

    def __post_init__(self) -> None:
        if not isinstance(self.updated_light_state, BuildingLightState):
            raise TypeError("updated_light_state must be BuildingLightState.")

        if not isinstance(self.outdoor_daylight_boundary, OutdoorDaylightBoundary):
            raise TypeError(
                "outdoor_daylight_boundary must be OutdoorDaylightBoundary."
            )

        if not isinstance(self.window_daylight_parameters, BuildingWindowDaylightParameters):
            raise TypeError(
                "window_daylight_parameters must be BuildingWindowDaylightParameters."
            )

        if not isinstance(self.daylight_result, BuildingIndoorDaylightResult):
            raise TypeError(
                "daylight_result must be BuildingIndoorDaylightResult."
            )

        if not isinstance(self.lighting_power_result, BuildingLightingPowerResult):
            raise TypeError(
                "lighting_power_result must be BuildingLightingPowerResult."
            )

        if not isinstance(self.visual_comfort_result, BuildingVisualComfortResult):
            raise TypeError(
                "visual_comfort_result must be BuildingVisualComfortResult."
            )

        if not isinstance(self.lighting_control_inputs, BuildingLightingControlInputs):
            raise TypeError(
                "lighting_control_inputs must be BuildingLightingControlInputs."
            )

        if self.debug_records is None:
            self.debug_records = []

        cleaned = []

        for record in self.debug_records:
            if not isinstance(record, ZoneDaylightDebugRecord):
                raise TypeError(
                    "debug_records must contain ZoneDaylightDebugRecord objects."
                )

            cleaned.append(record)

        self.debug_records = cleaned

        self.dt_minutes = _positive_float(
            self.dt_minutes,
            "dt_minutes",
            "DaylightStepResult",
        )

    def indoor_illuminance_by_zone_lux(self) -> Dict[str, float]:
        return self.updated_light_state.indoor_illuminance_by_zone_lux()

    def daylight_illuminance_by_zone_lux(self) -> Dict[str, float]:
        return self.updated_light_state.daylight_illuminance_by_zone_lux()

    def artificial_lighting_illuminance_by_zone_lux(self) -> Dict[str, float]:
        return self.updated_light_state.artificial_lighting_illuminance_by_zone_lux()

    def visual_comfort_status_by_zone(self) -> Dict[str, str]:
        return self.visual_comfort_result.visual_comfort_status_by_zone()

    def lighting_power_by_zone_w(self) -> Dict[str, float]:
        return self.lighting_power_result.lighting_power_by_zone_w()

    def lighting_energy_by_zone_wh(self) -> Dict[str, float]:
        return self.lighting_power_result.lighting_energy_by_zone_wh()

    def total_lighting_power_w(self) -> float:
        return self.lighting_power_result.total_lighting_power_w()

    def total_lighting_energy_wh(self) -> float:
        return self.lighting_power_result.total_lighting_energy_wh()

    def debug_records_as_dicts(self) -> List[Dict[str, Any]]:
        return [
            record.to_dict()
            for record in self.debug_records
        ]

    def to_debug_dataframe(self) -> Any:
        import pandas as pd

        return pd.DataFrame(self.debug_records_as_dicts())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "updated_light_state": self.updated_light_state.to_dict(),
            "indoor_illuminance_by_zone_lux": self.indoor_illuminance_by_zone_lux(),
            "daylight_illuminance_by_zone_lux": self.daylight_illuminance_by_zone_lux(),
            "artificial_lighting_illuminance_by_zone_lux": self.artificial_lighting_illuminance_by_zone_lux(),
            "visual_comfort_status_by_zone": self.visual_comfort_status_by_zone(),
            "lighting_power_by_zone_w": self.lighting_power_by_zone_w(),
            "lighting_energy_by_zone_wh": self.lighting_energy_by_zone_wh(),
            "total_lighting_power_w": self.total_lighting_power_w(),
            "total_lighting_energy_wh": self.total_lighting_energy_wh(),
            "outdoor_daylight_boundary": self.outdoor_daylight_boundary.to_dict(),
            "window_daylight_parameters": self.window_daylight_parameters.to_dict(),
            "daylight_result": self.daylight_result.to_dict(),
            "lighting_power_result": self.lighting_power_result.to_dict(),
            "visual_comfort_result": self.visual_comfort_result.to_dict(),
            "lighting_control_inputs": self.lighting_control_inputs.to_dict(),
            "debug_records": self.debug_records_as_dicts(),
            "dt_minutes": self.dt_minutes,
            "interface_mode": self.interface_mode,
        }
    
@dataclass
class DaylightModel:
    """
    Runner-facing daylight / lighting / visual comfort model.

    Clean dependency rule:
    - no imports from agents/actions/controllers
    - no thermal calculation
    - no moisture calculation
    - no airflow calculation
    - reads WeatherState for outdoor illuminance
    - reads BuildingPhysicsGraph for windows
    - reads BuildingModel / ZoneModel for zone parameters
    - reads clean lighting control bridge inputs
    """

    architecture: DaylightArchitectureDecision = None
    default_dt_minutes: float = DEFAULT_DAYLIGHT_DT_MINUTES

    def __post_init__(self) -> None:
        if self.architecture is None:
            self.architecture = DaylightArchitectureDecision()

        if not isinstance(self.architecture, DaylightArchitectureDecision):
            raise TypeError(
                "DaylightModel.architecture must be DaylightArchitectureDecision."
            )

        self.default_dt_minutes = _positive_float(
            self.default_dt_minutes,
            "default_dt_minutes",
            "DaylightModel",
        )

    def make_initial_state(
        self,
        building_model: Any,
    ) -> BuildingLightState:
        return make_initial_building_light_state(
            building_model=building_model,
        )

    def step(
        self,
        building_model: Any,
        physics_graph: Any,
        light_state: BuildingLightState,
        weather_state: Any,
        lighting_control_inputs: BuildingLightingControlInputs = None,
        zone_system_specs: Dict[str, Any] = None,
        dt_minutes: float = None,
    ) -> DaylightStepResult:
        """
        Advance daylight / lighting model by one timestep.

        Expected runner call:

            DaylightModel.step(
                building_model,
                physics_graph,
                light_state,
                weather_state,
                lighting_control_inputs,
                zone_system_specs,
                dt_minutes
            )

        lighting_control_inputs:
            clean bridge object from agents/controllers/schedules.
        """

        if building_model is None:
            raise ValueError("building_model cannot be None.")

        if physics_graph is None:
            raise ValueError("physics_graph cannot be None.")

        if not isinstance(light_state, BuildingLightState):
            raise TypeError("light_state must be BuildingLightState.")

        if weather_state is None:
            raise ValueError("weather_state cannot be None.")

        if lighting_control_inputs is None:
            lighting_control_inputs = make_empty_lighting_control_inputs()

        if not isinstance(lighting_control_inputs, BuildingLightingControlInputs):
            raise TypeError(
                "lighting_control_inputs must be BuildingLightingControlInputs."
            )

        if zone_system_specs is None:
            zone_system_specs = {}

        if dt_minutes is None:
            dt_minutes = self.default_dt_minutes

        dt_minutes = _positive_float(
            dt_minutes,
            "dt_minutes",
            "DaylightModel.step",
        )

        outdoor_daylight_boundary = make_outdoor_daylight_boundary_from_weather_state(
            weather_state
        )

        window_daylight_parameters = make_building_window_daylight_parameters(
            physics_graph=physics_graph,
            building_model=building_model,
        )

        daylight_result = calculate_building_indoor_daylight_result(
            building_model=building_model,
            building_window_daylight_parameters=window_daylight_parameters,
            outdoor_daylight_boundary=outdoor_daylight_boundary,
        )

        building_lighting_parameters = make_building_lighting_parameters(
            building_model=building_model,
            zone_system_specs=zone_system_specs,
        )

        lighting_power_result = calculate_building_lighting_power_result(
            building_lighting_parameters=building_lighting_parameters,
            lighting_control_inputs=lighting_control_inputs,
            dt_minutes=dt_minutes,
        )

        updated_light_state = make_building_light_state_from_daylight_and_lighting(
            building_model=building_model,
            daylight_result=daylight_result,
            lighting_power_result=lighting_power_result,
        )

        visual_comfort_parameters = make_building_visual_comfort_parameters(
            building_model
        )

        visual_comfort_result = calculate_building_visual_comfort_result(
            building_light_state=updated_light_state,
            building_visual_comfort_parameters=visual_comfort_parameters,
        )

        debug_records = self._make_debug_records(
            building_model=building_model,
            outdoor_daylight_boundary=outdoor_daylight_boundary,
            updated_light_state=updated_light_state,
            lighting_power_result=lighting_power_result,
            visual_comfort_result=visual_comfort_result,
            lighting_control_inputs=lighting_control_inputs,
            dt_minutes=dt_minutes,
        )

        return DaylightStepResult(
            updated_light_state=updated_light_state,
            outdoor_daylight_boundary=outdoor_daylight_boundary,
            window_daylight_parameters=window_daylight_parameters,
            daylight_result=daylight_result,
            lighting_power_result=lighting_power_result,
            visual_comfort_result=visual_comfort_result,
            lighting_control_inputs=lighting_control_inputs,
            debug_records=debug_records,
            dt_minutes=dt_minutes,
            interface_mode=DAYLIGHT_MODEL_INTERFACE_MODE,
        )

    def _make_debug_records(
        self,
        building_model: Any,
        outdoor_daylight_boundary: OutdoorDaylightBoundary,
        updated_light_state: BuildingLightState,
        lighting_power_result: BuildingLightingPowerResult,
        visual_comfort_result: BuildingVisualComfortResult,
        lighting_control_inputs: BuildingLightingControlInputs,
        dt_minutes: float,
    ) -> List[ZoneDaylightDebugRecord]:
        records = []

        for zone_id in updated_light_state.zone_ids():
            zone_light_state = updated_light_state.get_zone_state(zone_id)

            lighting_result = lighting_power_result.get_zone_result(
                zone_id
            )

            visual_result = visual_comfort_result.get_zone_result(
                zone_id
            )

            control = lighting_control_inputs.get_control_for_zone(
                zone_id
            )

            records.append(
                ZoneDaylightDebugRecord(
                    zone_id=zone_id,
                    outdoor_illuminance_lux=outdoor_daylight_boundary.outdoor_illuminance_lux,
                    daylight_illuminance_lux=zone_light_state.daylight_illuminance_lux,
                    artificial_lighting_illuminance_lux=zone_light_state.artificial_lighting_illuminance_lux,
                    indoor_illuminance_lux=zone_light_state.indoor_illuminance_lux,
                    visual_comfort_target_lux=zone_light_state.visual_comfort_target_lux,
                    visual_comfort_status=visual_result.visual_comfort_status,
                    lighting_power_w=lighting_result.lighting_power_w,
                    lighting_energy_wh=lighting_result.lighting_energy_wh,
                    lights_on=control.lights_on,
                    dimming_fraction=control.dimming_fraction,
                    dt_minutes=dt_minutes,
                    source=DAYLIGHT_MODEL_INTERFACE_MODE,
                )
            )

        return records
    
    
DEFAULT_DAYLIGHT_ARCHITECTURE = DaylightArchitectureDecision()
LightingModel = DaylightModel


def make_default_daylight_model() -> DaylightModel:
    return DaylightModel()


def make_default_lighting_model() -> DaylightModel:
    return DaylightModel()

def make_default_daylight_architecture() -> DaylightArchitectureDecision:
    return DaylightArchitectureDecision()

def calculate_window_indoor_daylight_record(
    window_parameters: WindowDaylightParameters,
    outdoor_daylight_boundary: OutdoorDaylightBoundary,
    floor_area_m2: float,
) -> WindowIndoorDaylightRecord:
    """
    Estimate indoor daylight contribution from one window.
    """

    if not isinstance(window_parameters, WindowDaylightParameters):
        raise TypeError(
            "window_parameters must be WindowDaylightParameters."
        )

    if not isinstance(outdoor_daylight_boundary, OutdoorDaylightBoundary):
        raise TypeError(
            "outdoor_daylight_boundary must be OutdoorDaylightBoundary."
        )

    floor_area_m2 = _positive_float(
        floor_area_m2,
        "floor_area_m2",
        window_parameters.zone_id,
    )

    effective_daylight_area_m2 = window_parameters.effective_daylight_area_m2()

    indoor_daylight_illuminance_lux = (
        outdoor_daylight_boundary.outdoor_illuminance_lux
        * effective_daylight_area_m2
        / floor_area_m2
    )

    return WindowIndoorDaylightRecord(
        boundary_connection_id=window_parameters.boundary_connection_id,
        zone_id=window_parameters.zone_id,
        outdoor_illuminance_lux=outdoor_daylight_boundary.outdoor_illuminance_lux,
        floor_area_m2=floor_area_m2,
        effective_daylight_area_m2=effective_daylight_area_m2,
        indoor_daylight_illuminance_lux=indoor_daylight_illuminance_lux,
        source=DAYLIGHT_ESTIMATE_SOURCE,
    )


def calculate_zone_indoor_daylight_result(
    zone_window_parameters: ZoneWindowDaylightParameters,
    outdoor_daylight_boundary: OutdoorDaylightBoundary,
    floor_area_m2: float,
) -> ZoneIndoorDaylightResult:
    """
    Estimate daylight illuminance for one zone from all its windows.
    """

    if not isinstance(zone_window_parameters, ZoneWindowDaylightParameters):
        raise TypeError(
            "zone_window_parameters must be ZoneWindowDaylightParameters."
        )

    if not isinstance(outdoor_daylight_boundary, OutdoorDaylightBoundary):
        raise TypeError(
            "outdoor_daylight_boundary must be OutdoorDaylightBoundary."
        )

    floor_area_m2 = _positive_float(
        floor_area_m2,
        "floor_area_m2",
        zone_window_parameters.zone_id,
    )

    window_records = []

    for window_parameters in zone_window_parameters.windows:
        window_records.append(
            calculate_window_indoor_daylight_record(
                window_parameters=window_parameters,
                outdoor_daylight_boundary=outdoor_daylight_boundary,
                floor_area_m2=floor_area_m2,
            )
        )

    daylight_illuminance_lux = sum(
        record.indoor_daylight_illuminance_lux
        for record in window_records
    )

    daylight_illuminance_lux = clamp_illuminance_lux(
        daylight_illuminance_lux
    )

    return ZoneIndoorDaylightResult(
        zone_id=zone_window_parameters.zone_id,
        daylight_illuminance_lux=daylight_illuminance_lux,
        window_records=window_records,
        source=DAYLIGHT_ESTIMATE_SOURCE,
    )

def calculate_zone_lighting_power_result(
    zone_lighting_parameters: ZoneLightingParameters,
    lighting_control_input: ZoneLightingControlInput,
    dt_minutes: float = 15.0,
) -> ZoneLightingPowerResult:
    """
    Calculate artificial lighting illuminance and power for one zone.

    Logic:
    - if lights are off -> zero lux, zero power
    - if lights are on:
        available_lux = installed_lighting_lux * dimming_fraction
        delivered_lux = min(requested_lux, available_lux)
        power_fraction = delivered_lux / installed_lighting_lux
        power = max_power * power_fraction

    This gives linear dimming behaviour.
    """

    if not isinstance(zone_lighting_parameters, ZoneLightingParameters):
        raise TypeError(
            "zone_lighting_parameters must be ZoneLightingParameters."
        )

    if not isinstance(lighting_control_input, ZoneLightingControlInput):
        raise TypeError(
            "lighting_control_input must be ZoneLightingControlInput."
        )

    if zone_lighting_parameters.zone_id != lighting_control_input.zone_id:
        raise ValueError(
            "zone_lighting_parameters.zone_id does not match "
            "lighting_control_input.zone_id."
        )

    dt_minutes = _positive_float(
        dt_minutes,
        "dt_minutes",
        zone_lighting_parameters.zone_id,
    )

    if (
        not zone_lighting_parameters.lighting_available
        or not lighting_control_input.lights_on
        or lighting_control_input.dimming_fraction <= 0.0
        or lighting_control_input.requested_artificial_lighting_lux <= 0.0
        or zone_lighting_parameters.installed_lighting_lux <= 0.0
    ):
        return ZoneLightingPowerResult(
            zone_id=zone_lighting_parameters.zone_id,
            lights_on=False,
            dimming_fraction=0.0,
            requested_artificial_lighting_lux=0.0,
            installed_lighting_lux=zone_lighting_parameters.installed_lighting_lux,
            artificial_lighting_illuminance_lux=0.0,
            lighting_power_w=0.0,
            lighting_energy_wh=0.0,
            control_mode=lighting_control_input.control_mode,
            source=LIGHTING_POWER_SOURCE,
        )

    available_lighting_lux = (
        zone_lighting_parameters.installed_lighting_lux
        * lighting_control_input.dimming_fraction
    )

    delivered_lighting_lux = min(
        lighting_control_input.requested_artificial_lighting_lux,
        available_lighting_lux,
    )

    delivered_lighting_lux = clamp_illuminance_lux(
        delivered_lighting_lux
    )

    power_fraction = (
        delivered_lighting_lux
        / zone_lighting_parameters.installed_lighting_lux
    )

    power_fraction = _clamp_unit_interval(
        power_fraction
    )

    lighting_power_w = (
        zone_lighting_parameters.max_lighting_power_w()
        * power_fraction
    )

    lighting_energy_wh = (
        lighting_power_w
        * dt_minutes
        / 60.0
    )

    return ZoneLightingPowerResult(
        zone_id=zone_lighting_parameters.zone_id,
        lights_on=True,
        dimming_fraction=lighting_control_input.dimming_fraction,
        requested_artificial_lighting_lux=lighting_control_input.requested_artificial_lighting_lux,
        installed_lighting_lux=zone_lighting_parameters.installed_lighting_lux,
        artificial_lighting_illuminance_lux=delivered_lighting_lux,
        lighting_power_w=lighting_power_w,
        lighting_energy_wh=lighting_energy_wh,
        control_mode=lighting_control_input.control_mode,
        source=LIGHTING_POWER_SOURCE,
    )


def calculate_building_lighting_power_result(
    building_lighting_parameters: BuildingLightingParameters,
    lighting_control_inputs: BuildingLightingControlInputs,
    dt_minutes: float = 15.0,
) -> BuildingLightingPowerResult:
    """
    Calculate artificial lighting power for all zones.
    """

    if not isinstance(building_lighting_parameters, BuildingLightingParameters):
        raise TypeError(
            "building_lighting_parameters must be BuildingLightingParameters."
        )

    if not isinstance(lighting_control_inputs, BuildingLightingControlInputs):
        raise TypeError(
            "lighting_control_inputs must be BuildingLightingControlInputs."
        )

    zone_results = {}

    for zone_id in building_lighting_parameters.zone_ids():
        parameters = building_lighting_parameters.get_zone_parameters(
            zone_id
        )

        control = lighting_control_inputs.get_control_for_zone(
            zone_id
        )

        zone_results[zone_id] = calculate_zone_lighting_power_result(
            zone_lighting_parameters=parameters,
            lighting_control_input=control,
            dt_minutes=dt_minutes,
        )

    return BuildingLightingPowerResult(
        zone_results=zone_results,
        dt_minutes=dt_minutes,
        source=LIGHTING_POWER_SOURCE,
    )

def make_zone_visual_comfort_parameters(
    zone_model: Any,
) -> ZoneVisualComfortParameters:
    """
    Build ZoneVisualComfortParameters from ZoneModel.

    Optional ZoneModel attributes:
    - visual_comfort_target_lux
    - visual_dark_fraction
    - visual_lower_comfort_fraction
    - visual_upper_comfort_fraction
    """

    if zone_model is None:
        raise ValueError("zone_model cannot be None.")

    zone_id = _required_attr(
        zone_model,
        "zone_id",
    )

    target_lux = _get_attr_or_default(
        zone_model,
        "visual_comfort_target_lux",
        DEFAULT_VISUAL_COMFORT_TARGET_LUX,
    )

    dark_fraction = _get_attr_or_default(
        zone_model,
        "visual_dark_fraction",
        DEFAULT_VISUAL_DARK_FRACTION,
    )

    lower_comfort_fraction = _get_attr_or_default(
        zone_model,
        "visual_lower_comfort_fraction",
        DEFAULT_VISUAL_COMFORT_LOWER_FRACTION,
    )

    upper_comfort_fraction = _get_attr_or_default(
        zone_model,
        "visual_upper_comfort_fraction",
        DEFAULT_VISUAL_COMFORT_UPPER_FRACTION,
    )

    return ZoneVisualComfortParameters(
        zone_id=zone_id,
        visual_comfort_target_lux=target_lux,
        dark_fraction=dark_fraction,
        lower_comfort_fraction=lower_comfort_fraction,
        upper_comfort_fraction=upper_comfort_fraction,
        source=VISUAL_COMFORT_SOURCE,
    )


def make_building_visual_comfort_parameters(
    building_model: Any,
) -> BuildingVisualComfortParameters:
    """
    Build visual comfort parameters for all zones.
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
        zone_parameters[zone_id] = make_zone_visual_comfort_parameters(
            zone_model
        )

    return BuildingVisualComfortParameters(
        zone_parameters=zone_parameters,
    )

def visual_comfort_status_from_parameters(
    indoor_illuminance_lux: float,
    parameters: ZoneVisualComfortParameters,
) -> str:
    """
    Evaluate visual comfort status using zone-specific thresholds.
    """

    if not isinstance(parameters, ZoneVisualComfortParameters):
        raise TypeError(
            "parameters must be ZoneVisualComfortParameters."
        )

    indoor_illuminance_lux = clamp_illuminance_lux(
        indoor_illuminance_lux
    )

    if indoor_illuminance_lux < parameters.dark_threshold_lux():
        return VISUAL_COMFORT_STATUS_DARK

    if indoor_illuminance_lux < parameters.lower_comfort_threshold_lux():
        return VISUAL_COMFORT_STATUS_UNDERLIT

    if indoor_illuminance_lux <= parameters.upper_comfort_threshold_lux():
        return VISUAL_COMFORT_STATUS_COMFORTABLE

    return VISUAL_COMFORT_STATUS_OVERLIT


def calculate_zone_visual_comfort_result(
    zone_light_state: ZoneLightState,
    visual_comfort_parameters: ZoneVisualComfortParameters,
) -> ZoneVisualComfortResult:
    """
    Calculate visual comfort for one zone.
    """

    if not isinstance(zone_light_state, ZoneLightState):
        raise TypeError("zone_light_state must be ZoneLightState.")

    if not isinstance(visual_comfort_parameters, ZoneVisualComfortParameters):
        raise TypeError(
            "visual_comfort_parameters must be ZoneVisualComfortParameters."
        )

    if zone_light_state.zone_id != visual_comfort_parameters.zone_id:
        raise ValueError(
            "zone_light_state.zone_id does not match "
            "visual_comfort_parameters.zone_id."
        )

    status = visual_comfort_status_from_parameters(
        indoor_illuminance_lux=zone_light_state.indoor_illuminance_lux,
        parameters=visual_comfort_parameters,
    )

    ratio = (
        zone_light_state.indoor_illuminance_lux
        / visual_comfort_parameters.visual_comfort_target_lux
    )

    return ZoneVisualComfortResult(
        zone_id=zone_light_state.zone_id,
        indoor_illuminance_lux=zone_light_state.indoor_illuminance_lux,
        daylight_illuminance_lux=zone_light_state.daylight_illuminance_lux,
        artificial_lighting_illuminance_lux=zone_light_state.artificial_lighting_illuminance_lux,
        visual_comfort_target_lux=visual_comfort_parameters.visual_comfort_target_lux,
        visual_comfort_status=status,
        illuminance_ratio_to_target=ratio,
        glare_risk_index=DEFAULT_GLARE_RISK_INDEX,
        source=VISUAL_COMFORT_SOURCE,
    )

def calculate_visual_comfort_from_light_state(
    building_model: Any,
    building_light_state: BuildingLightState,
) -> BuildingVisualComfortResult:
    """
    Convenience pipeline:

        BuildingModel -> visual comfort parameters
        BuildingLightState -> illuminance by zone
        result -> visual comfort by zone
    """

    building_visual_comfort_parameters = make_building_visual_comfort_parameters(
        building_model
    )

    return calculate_building_visual_comfort_result(
        building_light_state=building_light_state,
        building_visual_comfort_parameters=building_visual_comfort_parameters,
    )

def calculate_building_visual_comfort_result(
    building_light_state: BuildingLightState,
    building_visual_comfort_parameters: BuildingVisualComfortParameters,
) -> BuildingVisualComfortResult:
    """
    Calculate visual comfort for all zones.
    """

    if not isinstance(building_light_state, BuildingLightState):
        raise TypeError(
            "building_light_state must be BuildingLightState."
        )

    if not isinstance(building_visual_comfort_parameters, BuildingVisualComfortParameters):
        raise TypeError(
            "building_visual_comfort_parameters must be BuildingVisualComfortParameters."
        )

    zone_results = {}

    for zone_id in building_light_state.zone_ids():
        zone_light_state = building_light_state.get_zone_state(
            zone_id
        )

        parameters = building_visual_comfort_parameters.get_zone_parameters(
            zone_id
        )

        zone_results[zone_id] = calculate_zone_visual_comfort_result(
            zone_light_state=zone_light_state,
            visual_comfort_parameters=parameters,
        )

    return BuildingVisualComfortResult(
        zone_results=zone_results,
        source=VISUAL_COMFORT_SOURCE,
    )

def make_empty_lighting_control_inputs() -> BuildingLightingControlInputs:
    return BuildingLightingControlInputs(
        controls_by_zone={},
    )

def make_building_light_state_from_daylight_and_lighting(
    building_model: Any,
    daylight_result: BuildingIndoorDaylightResult,
    lighting_power_result: BuildingLightingPowerResult,
) -> BuildingLightState:
    """
    Combine daylight estimate and artificial lighting result into BuildingLightState.
    """

    if building_model is None:
        raise ValueError("building_model cannot be None.")

    if not hasattr(building_model, "all_zone_models"):
        raise TypeError(
            "building_model must provide all_zone_models()."
        )

    if not isinstance(daylight_result, BuildingIndoorDaylightResult):
        raise TypeError(
            "daylight_result must be BuildingIndoorDaylightResult."
        )

    if not isinstance(lighting_power_result, BuildingLightingPowerResult):
        raise TypeError(
            "lighting_power_result must be BuildingLightingPowerResult."
        )

    zone_models = building_model.all_zone_models()

    zone_states = {}

    for zone_id, zone_model in zone_models.items():
        daylight_lux = (
            daylight_result
            .get_zone_result(zone_id)
            .daylight_illuminance_lux
        )

        lighting_lux = (
            lighting_power_result
            .get_zone_result(zone_id)
            .artificial_lighting_illuminance_lux
        )

        target_lux = _get_attr_or_default(
            zone_model,
            "visual_comfort_target_lux",
            DEFAULT_VISUAL_COMFORT_TARGET_LUX,
        )

        zone_states[zone_id] = ZoneLightState(
            zone_id=zone_id,
            daylight_illuminance_lux=daylight_lux,
            artificial_lighting_illuminance_lux=lighting_lux,
            indoor_illuminance_lux=daylight_lux + lighting_lux,
            visual_comfort_target_lux=target_lux,
        )

    return BuildingLightState(
        zone_states=zone_states,
    )

def make_zone_lighting_parameters(
    zone_model: Any,
    zone_system_spec: Any = None,
) -> ZoneLightingParameters:
    """
    Build ZoneLightingParameters from ZoneModel and optional ZoneSystemSpec-like object.

    No import from systems.py.

    Optional ZoneSystemSpec-like attributes:
    - has_lighting
    - lighting_power_density_w_m2
    - installed_lighting_lux
    """

    if zone_model is None:
        raise ValueError("zone_model cannot be None.")

    zone_id = _required_attr(
        zone_model,
        "zone_id",
    )

    floor_area_m2 = zone_floor_area_for_daylight_m2(
        zone_model
    )

    lighting_available = _first_existing_attr_or_default(
        zone_system_spec,
        [
            "has_lighting",
            "lighting_available",
        ],
        DEFAULT_LIGHTING_SYSTEM_AVAILABLE,
    )

    installed_lighting_lux = _first_existing_attr_or_default(
        zone_system_spec,
        [
            "installed_lighting_lux",
        ],
        _get_attr_or_default(
            zone_model,
            "installed_lighting_lux",
            DEFAULT_INSTALLED_LIGHTING_LUX,
        ),
    )

    lighting_power_density_w_m2 = _first_existing_attr_or_default(
        zone_system_spec,
        [
            "lighting_power_density_w_m2",
        ],
        _get_attr_or_default(
            zone_model,
            "lighting_power_density_w_m2",
            DEFAULT_LIGHTING_POWER_DENSITY_W_M2,
        ),
    )

    return ZoneLightingParameters(
        zone_id=zone_id,
        floor_area_m2=floor_area_m2,
        installed_lighting_lux=installed_lighting_lux,
        lighting_power_density_w_m2=lighting_power_density_w_m2,
        lighting_available=lighting_available,
        source=LIGHTING_POWER_SOURCE,
    )

def calculate_building_lighting_from_controls(
    building_model: Any,
    lighting_control_inputs: BuildingLightingControlInputs,
    zone_system_specs: Dict[str, Any] = None,
    dt_minutes: float = 15.0,
) -> BuildingLightingPowerResult:
    """
    Convenience pipeline for artificial lighting only.

    Does not calculate daylight.
    """

    building_lighting_parameters = make_building_lighting_parameters(
        building_model=building_model,
        zone_system_specs=zone_system_specs,
    )

    return calculate_building_lighting_power_result(
        building_lighting_parameters=building_lighting_parameters,
        lighting_control_inputs=lighting_control_inputs,
        dt_minutes=dt_minutes,
    )

def make_building_lighting_parameters(
    building_model: Any,
    zone_system_specs: Dict[str, Any] = None,
) -> BuildingLightingParameters:
    """
    Build BuildingLightingParameters for all zones.

    zone_system_specs is optional and duck-typed:
        {zone_id: ZoneSystemSpec-like object}
    """

    if building_model is None:
        raise ValueError("building_model cannot be None.")

    if not hasattr(building_model, "all_zone_models"):
        raise TypeError(
            "building_model must provide all_zone_models()."
        )

    if zone_system_specs is None:
        zone_system_specs = {}

    zone_models = building_model.all_zone_models()

    zone_parameters = {}

    for zone_id, zone_model in zone_models.items():
        zone_parameters[zone_id] = make_zone_lighting_parameters(
            zone_model=zone_model,
            zone_system_spec=zone_system_specs.get(zone_id),
        )

    return BuildingLightingParameters(
        zone_parameters=zone_parameters,
    )


def make_lighting_control_inputs(
    lights_on_by_zone: Dict[str, bool] = None,
    dimming_fraction_by_zone: Dict[str, float] = None,
    requested_artificial_lighting_by_zone_lux: Dict[str, float] = None,
    control_mode: str = LIGHTING_CONTROL_MODE_MANUAL,
) -> BuildingLightingControlInputs:
    """
    Convenience builder for artificial lighting control inputs.

    Example:
        make_lighting_control_inputs(
            lights_on_by_zone={"kitchen": True},
            dimming_fraction_by_zone={"kitchen": 1.0},
            requested_artificial_lighting_by_zone_lux={"kitchen": 300.0},
        )
    """

    if lights_on_by_zone is None:
        lights_on_by_zone = {}

    if dimming_fraction_by_zone is None:
        dimming_fraction_by_zone = {}

    if requested_artificial_lighting_by_zone_lux is None:
        requested_artificial_lighting_by_zone_lux = {}

    zone_ids = set()
    zone_ids.update(lights_on_by_zone.keys())
    zone_ids.update(dimming_fraction_by_zone.keys())
    zone_ids.update(requested_artificial_lighting_by_zone_lux.keys())

    controls_by_zone = {}

    for zone_id in zone_ids:
        controls_by_zone[zone_id] = ZoneLightingControlInput(
            zone_id=zone_id,
            lights_on=lights_on_by_zone.get(zone_id, False),
            dimming_fraction=dimming_fraction_by_zone.get(zone_id, 0.0),
            requested_artificial_lighting_lux=requested_artificial_lighting_by_zone_lux.get(zone_id, 0.0),
            control_mode=control_mode,
            source=LIGHTING_CONTROL_SOURCE_EXTERNAL_BRIDGE,
        )

    return BuildingLightingControlInputs(
        controls_by_zone=controls_by_zone,
        source=LIGHTING_CONTROL_SOURCE_EXTERNAL_BRIDGE,
    )


def make_lights_on_full_output_inputs(
    zone_ids: List[str],
    requested_lux: float = DEFAULT_VISUAL_COMFORT_TARGET_LUX,
    control_mode: str = LIGHTING_CONTROL_MODE_MANUAL,
) -> BuildingLightingControlInputs:
    """
    Convenience builder: lights fully on in selected zones.
    """

    if zone_ids is None:
        zone_ids = []

    controls_by_zone = {}

    for zone_id in zone_ids:
        controls_by_zone[zone_id] = ZoneLightingControlInput(
            zone_id=zone_id,
            lights_on=True,
            dimming_fraction=1.0,
            requested_artificial_lighting_lux=requested_lux,
            control_mode=control_mode,
            source=LIGHTING_CONTROL_SOURCE_EXTERNAL_BRIDGE,
        )

    return BuildingLightingControlInputs(
        controls_by_zone=controls_by_zone,
        source=LIGHTING_CONTROL_SOURCE_EXTERNAL_BRIDGE,
    )

def calculate_building_indoor_daylight_result(
    building_model: Any,
    building_window_daylight_parameters: BuildingWindowDaylightParameters,
    outdoor_daylight_boundary: OutdoorDaylightBoundary,
) -> BuildingIndoorDaylightResult:
    """
    Estimate indoor daylight illuminance for all zones.

    Inputs:
    - BuildingModel for zone floor areas
    - BuildingWindowDaylightParameters from Phase 7.3
    - OutdoorDaylightBoundary from Phase 7.4

    No artificial lighting is calculated here.
    """

    if building_model is None:
        raise ValueError("building_model cannot be None.")

    if not hasattr(building_model, "all_zone_models"):
        raise TypeError(
            "building_model must provide all_zone_models()."
        )

    if not isinstance(building_window_daylight_parameters, BuildingWindowDaylightParameters):
        raise TypeError(
            "building_window_daylight_parameters must be BuildingWindowDaylightParameters."
        )

    if not isinstance(outdoor_daylight_boundary, OutdoorDaylightBoundary):
        raise TypeError(
            "outdoor_daylight_boundary must be OutdoorDaylightBoundary."
        )

    zone_models = building_model.all_zone_models()

    zone_results = {}

    for zone_id, zone_model in zone_models.items():
        floor_area_m2 = zone_floor_area_for_daylight_m2(
            zone_model
        )

        zone_window_parameters = (
            building_window_daylight_parameters
            .get_zone_window_parameters(zone_id)
        )

        zone_results[zone_id] = calculate_zone_indoor_daylight_result(
            zone_window_parameters=zone_window_parameters,
            outdoor_daylight_boundary=outdoor_daylight_boundary,
            floor_area_m2=floor_area_m2,
        )

    return BuildingIndoorDaylightResult(
        zone_results=zone_results,
        source=DAYLIGHT_ESTIMATE_SOURCE,
    )

def estimate_building_indoor_daylight_from_weather_and_graph(
    building_model: Any,
    physics_graph: Any,
    weather_state: Any,
) -> BuildingIndoorDaylightResult:
    """
    Convenience pipeline:

        WeatherState
            -> OutdoorDaylightBoundary

        BuildingPhysicsGraph + BuildingModel
            -> BuildingWindowDaylightParameters

        Both
            -> BuildingIndoorDaylightResult

    This function does not calculate artificial lighting.
    """

    outdoor_daylight_boundary = make_outdoor_daylight_boundary_from_weather_state(
        weather_state
    )

    building_window_daylight_parameters = make_building_window_daylight_parameters(
        physics_graph=physics_graph,
        building_model=building_model,
    )

    return calculate_building_indoor_daylight_result(
        building_model=building_model,
        building_window_daylight_parameters=building_window_daylight_parameters,
        outdoor_daylight_boundary=outdoor_daylight_boundary,
    )


def make_outdoor_daylight_boundary_from_weather_state(
    weather_state: Any,
) -> OutdoorDaylightBoundary:
    """
    Build OutdoorDaylightBoundary from WeatherState.

    Expected WeatherState attributes:
    - outdoor_illuminance_lux
    - direct_normal_radiation_w_m2
    - diffuse_horizontal_radiation_w_m2
    - global_horizontal_radiation_w_m2
    - sky_condition

    Fallbacks:
    - outdoor illuminance = 0 lux
    - radiation = 0 W/m2
    - sky condition = unknown
    """

    if weather_state is None:
        raise ValueError("weather_state cannot be None.")

    outdoor_illuminance_lux = _get_attr_or_default(
        weather_state,
        "outdoor_illuminance_lux",
        DEFAULT_OUTDOOR_ILLUMINANCE_LUX,
    )

    direct_normal_radiation_w_m2 = _get_attr_or_default(
        weather_state,
        "direct_normal_radiation_w_m2",
        DEFAULT_DIRECT_NORMAL_RADIATION_W_M2,
    )

    diffuse_horizontal_radiation_w_m2 = _get_attr_or_default(
        weather_state,
        "diffuse_horizontal_radiation_w_m2",
        DEFAULT_DIFFUSE_HORIZONTAL_RADIATION_W_M2,
    )

    global_horizontal_radiation_w_m2 = _get_attr_or_default(
        weather_state,
        "global_horizontal_radiation_w_m2",
        DEFAULT_GLOBAL_HORIZONTAL_RADIATION_W_M2,
    )

    sky_condition = _get_attr_or_default(
        weather_state,
        "sky_condition",
        DEFAULT_SKY_CONDITION,
    )

    return OutdoorDaylightBoundary(
        outdoor_illuminance_lux=outdoor_illuminance_lux,
        direct_normal_radiation_w_m2=direct_normal_radiation_w_m2,
        diffuse_horizontal_radiation_w_m2=diffuse_horizontal_radiation_w_m2,
        global_horizontal_radiation_w_m2=global_horizontal_radiation_w_m2,
        sky_condition=sky_condition,
        source=OUTDOOR_DAYLIGHT_BOUNDARY_SOURCE,
    )

def outdoor_illuminance_from_weather_state(
    weather_state: Any,
) -> float:
    boundary = make_outdoor_daylight_boundary_from_weather_state(
        weather_state
    )

    return boundary.outdoor_illuminance_lux


def outdoor_has_daylight_from_weather_state(
    weather_state: Any,
) -> bool:
    boundary = make_outdoor_daylight_boundary_from_weather_state(
        weather_state
    )

    return boundary.has_daylight()


def make_window_daylight_parameters_from_boundary_connection(
    boundary_connection: Any,
    zone_model: Any = None,
) -> WindowDaylightParameters:
    """
    Build WindowDaylightParameters from a BoundaryConnection-like object.

    Expected BoundaryConnection attributes:
    - connection_id
    - zone_id
    - area_m2
    - orientation_deg
    - window_visible_transmittance
    - frame_fraction
    - shading_factor
    - curtain_open
    - curtain_daylight_reduction_factor

    Optional ZoneModel attribute:
    - daylight_utilization_factor
    """

    if boundary_connection is None:
        raise ValueError("boundary_connection cannot be None.")

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
            "BoundaryConnection must provide connection_id."
        )

    zone_id = _required_attr(
        boundary_connection,
        "zone_id",
    )

    area_m2 = _get_attr_or_default(
        boundary_connection,
        "area_m2",
        0.0,
    )

    orientation_deg = _get_attr_or_default(
        boundary_connection,
        "orientation_deg",
        None,
    )

    visible_transmittance = _first_existing_attr_or_default(
        boundary_connection,
        [
            "window_visible_transmittance",
            "visible_transmittance",
            "glazing_visible_transmittance",
            "glazing_transmittance",
        ],
        DEFAULT_WINDOW_VISIBLE_TRANSMITTANCE,
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

    curtain_open = _get_attr_or_default(
        boundary_connection,
        "curtain_open",
        True,
    )

    curtain_daylight_reduction_factor = _get_attr_or_default(
        boundary_connection,
        "curtain_daylight_reduction_factor",
        DEFAULT_CURTAIN_DAYLIGHT_REDUCTION_FACTOR,
    )

    daylight_utilization_factor = DEFAULT_WINDOW_DAYLIGHT_UTILIZATION_FACTOR

    if zone_model is not None:
        daylight_utilization_factor = _get_attr_or_default(
            zone_model,
            "daylight_utilization_factor",
            DEFAULT_WINDOW_DAYLIGHT_UTILIZATION_FACTOR,
        )

    return WindowDaylightParameters(
        boundary_connection_id=boundary_connection_id,
        zone_id=zone_id,
        area_m2=area_m2,
        orientation_deg=orientation_deg,
        visible_transmittance=visible_transmittance,
        frame_fraction=frame_fraction,
        shading_factor=shading_factor,
        curtain_open=curtain_open,
        curtain_daylight_reduction_factor=curtain_daylight_reduction_factor,
        daylight_utilization_factor=daylight_utilization_factor,
        source=WINDOW_DAYLIGHT_SOURCE,
    )


def make_building_window_daylight_parameters(
    physics_graph: Any,
    building_model: Any,
) -> BuildingWindowDaylightParameters:
    """
    Build daylight-relevant window parameters from BuildingPhysicsGraph.

    This function only extracts window parameters.
    It does not calculate indoor illuminance.
    """

    if physics_graph is None:
        raise ValueError("physics_graph cannot be None.")

    if building_model is None:
        raise ValueError("building_model cannot be None.")

    if not hasattr(physics_graph, "boundary_connections"):
        raise TypeError(
            "physics_graph must provide boundary_connections."
        )

    if not hasattr(building_model, "all_zone_models"):
        raise TypeError(
            "building_model must provide all_zone_models()."
        )

    zone_models = building_model.all_zone_models()

    zone_window_parameters = {}

    for zone_id in zone_models.keys():
        zone_window_parameters[zone_id] = ZoneWindowDaylightParameters(
            zone_id=zone_id,
            windows=[],
        )

    for boundary_connection in physics_graph.boundary_connections.values():
        if not is_window_boundary_for_daylight(boundary_connection):
            continue

        zone_id = _required_attr(
            boundary_connection,
            "zone_id",
        )

        if zone_id not in zone_window_parameters:
            zone_window_parameters[zone_id] = ZoneWindowDaylightParameters(
                zone_id=zone_id,
                windows=[],
            )

        zone_model = zone_models.get(zone_id)

        window_parameters = make_window_daylight_parameters_from_boundary_connection(
            boundary_connection=boundary_connection,
            zone_model=zone_model,
        )

        zone_window_parameters[zone_id].add_window(
            window_parameters
        )

    return BuildingWindowDaylightParameters(
        zone_window_parameters=zone_window_parameters,
    )

def make_initial_zone_light_state_from_zone_model(
    zone_model: Any,
) -> ZoneLightState:
    """
    Create initial ZoneLightState from ZoneModel.

    Optional ZoneModel attributes:
    - initial_indoor_illuminance_lux
    - initial_daylight_illuminance_lux
    - initial_artificial_lighting_illuminance_lux
    - visual_comfort_target_lux
    """

    if zone_model is None:
        raise ValueError("zone_model cannot be None.")

    zone_id = _required_attr(
        zone_model,
        "zone_id",
    )

    indoor_illuminance_lux = _get_attr_or_default(
        zone_model,
        "initial_indoor_illuminance_lux",
        DEFAULT_INDOOR_ILLUMINANCE_LUX,
    )

    daylight_illuminance_lux = _get_attr_or_default(
        zone_model,
        "initial_daylight_illuminance_lux",
        DEFAULT_DAYLIGHT_ILLUMINANCE_LUX,
    )

    artificial_lighting_illuminance_lux = _get_attr_or_default(
        zone_model,
        "initial_artificial_lighting_illuminance_lux",
        DEFAULT_ARTIFICIAL_LIGHTING_ILLUMINANCE_LUX,
    )

    visual_comfort_target_lux = _get_attr_or_default(
        zone_model,
        "visual_comfort_target_lux",
        DEFAULT_VISUAL_COMFORT_TARGET_LUX,
    )

    return ZoneLightState(
        zone_id=zone_id,
        indoor_illuminance_lux=indoor_illuminance_lux,
        daylight_illuminance_lux=daylight_illuminance_lux,
        artificial_lighting_illuminance_lux=artificial_lighting_illuminance_lux,
        visual_comfort_target_lux=visual_comfort_target_lux,
    )


def make_initial_building_light_state(
    building_model: Any,
) -> BuildingLightState:
    """
    Create initial BuildingLightState from BuildingModel / ZoneModel.
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
        zone_states[zone_id] = make_initial_zone_light_state_from_zone_model(
            zone_model
        )

    return BuildingLightState(
        zone_states=zone_states,
    )


def clamp_illuminance_lux(
    illuminance_lux: float,
) -> float:
    illuminance_lux = float(illuminance_lux)

    if illuminance_lux < MIN_ILLUMINANCE_LUX:
        return MIN_ILLUMINANCE_LUX

    if illuminance_lux > MAX_REASONABLE_ILLUMINANCE_LUX:
        return MAX_REASONABLE_ILLUMINANCE_LUX

    return illuminance_lux


def visual_comfort_status_from_illuminance(
    indoor_illuminance_lux: float,
    target_lux: float = DEFAULT_VISUAL_COMFORT_TARGET_LUX,
) -> str:
    indoor_illuminance_lux = clamp_illuminance_lux(
        indoor_illuminance_lux
    )

    target_lux = _positive_float(
        target_lux,
        "target_lux",
        "visual_comfort_status_from_illuminance",
    )

    if indoor_illuminance_lux < 0.10 * target_lux:
        return VISUAL_COMFORT_STATUS_DARK

    if indoor_illuminance_lux < 0.80 * target_lux:
        return VISUAL_COMFORT_STATUS_UNDERLIT

    if indoor_illuminance_lux <= 2.50 * target_lux:
        return VISUAL_COMFORT_STATUS_COMFORTABLE

    return VISUAL_COMFORT_STATUS_OVERLIT

def lighting_control_for_zone(
    lighting_control_inputs: BuildingLightingControlInputs,
    zone_id: str,
) -> ZoneLightingControlInput:
    if not isinstance(lighting_control_inputs, BuildingLightingControlInputs):
        raise TypeError(
            "lighting_control_inputs must be BuildingLightingControlInputs."
        )

    return lighting_control_inputs.get_control_for_zone(zone_id)


def requested_artificial_lighting_lux_by_zone(
    lighting_control_inputs: BuildingLightingControlInputs,
) -> Dict[str, float]:
    if not isinstance(lighting_control_inputs, BuildingLightingControlInputs):
        raise TypeError(
            "lighting_control_inputs must be BuildingLightingControlInputs."
        )

    return lighting_control_inputs.requested_artificial_lighting_by_zone_lux()


def lighting_dimming_fraction_by_zone(
    lighting_control_inputs: BuildingLightingControlInputs,
) -> Dict[str, float]:
    if not isinstance(lighting_control_inputs, BuildingLightingControlInputs):
        raise TypeError(
            "lighting_control_inputs must be BuildingLightingControlInputs."
        )

    return lighting_control_inputs.dimming_fraction_by_zone()

def is_window_boundary_for_daylight(
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

def zone_floor_area_for_daylight_m2(
    zone_model: Any,
) -> float:
    if zone_model is None:
        return DEFAULT_DAYLIGHT_FLOOR_AREA_M2

    floor_area_m2 = _get_attr_or_default(
        zone_model,
        "floor_area_m2",
        DEFAULT_DAYLIGHT_FLOOR_AREA_M2,
    )

    floor_area_m2 = float(floor_area_m2)

    if floor_area_m2 < DEFAULT_DAYLIGHT_MIN_FLOOR_AREA_M2:
        return DEFAULT_DAYLIGHT_MIN_FLOOR_AREA_M2

    return floor_area_m2


def normalize_orientation_deg(
    orientation_deg: float,
) -> float:
    orientation_deg = float(orientation_deg)

    while orientation_deg < 0.0:
        orientation_deg += 360.0

    while orientation_deg >= 360.0:
        orientation_deg -= 360.0

    return orientation_deg


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

