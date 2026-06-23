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
from typing import Any, Dict, List
import copy


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


DEFAULT_AIR_CO2_ARCHITECTURE = AirCO2ArchitectureDecision()