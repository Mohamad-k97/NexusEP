"""
ABBEY moisture / humidity model architecture.

- formally defines the moisture modelling decision
- no moisture solver yet
- no psychrometric calculations yet
- no wall moisture storage yet
- no hygrothermal envelope model yet

Decision:
    Moisture state = humidity_ratio_kg_water_per_kg_dry_air.
    Relative humidity = derived from humidity ratio + temperature + pressure.

Dependency rule:
    thermal state provides zone air temperature.
    airflow network provides outdoor/interzone air exchange.
    weather provides outdoor RH, outdoor temperature, and pressure.
    agents/actions provide clean moisture source inputs later.
"""

from dataclasses import dataclass, replace
from typing import Any, Dict, List
import math
import copy


MOISTURE_MODEL_FAMILY = "zone_level_moisture_balance"
MOISTURE_STATE_VARIABLE = "humidity_ratio_kg_water_per_kg_dry_air"
MOISTURE_DERIVED_VARIABLE = "relative_humidity_percent"

MOISTURE_SPATIAL_RESOLUTION = "zone"
MOISTURE_MULTIZONE_MODE = "multizone"

MOISTURE_OUTDOOR_BOUNDARY_SOURCE = "WeatherState"
MOISTURE_AIRFLOW_SOURCE = "BuildingAirflowNetwork"
MOISTURE_TEMPERATURE_SOURCE = "BuildingThermalState"
MOISTURE_PARAMETER_SOURCE = "ZoneModel"

MOISTURE_PEOPLE_SOURCE_MODE = "people_moisture_generation"
MOISTURE_ACTIVITY_SOURCE_MODE = "activity_moisture_generation_later"

MOISTURE_WALL_STORAGE_MODE = "not_in_phase_6"
MOISTURE_HYGROTHERMAL_UPGRADE_READY = True

MOISTURE_MODEL_DECISION = (
    "zone_level_humidity_ratio_mass_balance_with_relative_humidity_derived"
)

DEFAULT_INITIAL_RELATIVE_HUMIDITY_PERCENT = 50.0
DEFAULT_INITIAL_AIR_TEMPERATURE_C = 20.0
DEFAULT_ATMOSPHERIC_PRESSURE_PA = 101325.0

MIN_RELATIVE_HUMIDITY_PERCENT = 0.0
MAX_RELATIVE_HUMIDITY_PERCENT = 100.0

MOISTURE_SOURCE_PEOPLE = "people"
MOISTURE_SOURCE_COOKING = "cooking"
MOISTURE_SOURCE_SHOWER = "shower"
MOISTURE_SOURCE_LAUNDRY_DRYING = "laundry_drying"
MOISTURE_SOURCE_PLANTS_LATER = "plants_later"
MOISTURE_SOURCE_GENERIC = "generic"

VALID_MOISTURE_SOURCE_TYPES = {
    MOISTURE_SOURCE_PEOPLE,
    MOISTURE_SOURCE_COOKING,
    MOISTURE_SOURCE_SHOWER,
    MOISTURE_SOURCE_LAUNDRY_DRYING,
    MOISTURE_SOURCE_PLANTS_LATER,
    MOISTURE_SOURCE_GENERIC,
}

MIN_HUMIDITY_RATIO_KG_KG = 0.0

MOISTURE_MOLECULAR_WEIGHT_RATIO = 0.62198

MAX_HUMIDITY_RATIO_KG_KG = 0.20
MIN_ATMOSPHERIC_PRESSURE_PA = 50000.0
MAX_ATMOSPHERIC_PRESSURE_PA = 120000.0

MOISTURE_AIR_DENSITY_KG_M3 = 1.2

DEFAULT_MOISTURE_BUFFERING_ENABLED = False
DEFAULT_ZONE_AIR_VOLUME_M3 = 50.0

DEFAULT_MOISTURE_GENERATION_PER_PERSON_KG_H = 0.055

DEFAULT_OUTDOOR_RELATIVE_HUMIDITY_PERCENT = 50.0
DEFAULT_OUTDOOR_TEMPERATURE_C = 20.0

OUTDOOR_MOISTURE_BOUNDARY_SOURCE = "WeatherState"

MOISTURE_GENERATION_SOURCE_PEOPLE = "ZoneOccupancyInput + default_people_latent_moisture"

MOISTURE_TRANSPORT_SOURCE_OUTDOOR = "outdoor_air_exchange"
MOISTURE_TRANSPORT_SOURCE_INTERZONE = "interzone_air_exchange"

MOISTURE_TRANSPORT_TARGET_OUTDOOR = "outdoor"
MOISTURE_TRANSPORT_TARGET_INTERZONE = "interzone"

MOISTURE_TIMESTEP_METHOD = "semi_implicit_humidity_ratio_mass_balance"
DEFAULT_MOISTURE_DT_MINUTES = 15.0

MOISTURE_MODEL_INTERFACE_MODE = "runner_facing_moisture_model"

MOISTURE_COUPLING_THERMAL_TO_MOISTURE = "thermal_to_moisture"
MOISTURE_COUPLING_AIRFLOW_TO_MOISTURE = "airflow_to_moisture"
MOISTURE_COUPLING_MOISTURE_TO_COMFORT = "moisture_to_comfort"

MOISTURE_COUPLING_NOT_MOISTURE_TO_THERMAL = "not_moisture_to_thermal_in_phase_6"

MOISTURE_THERMAL_INPUT = "BuildingThermalState.zone_air_temperature"
MOISTURE_AIRFLOW_INPUT = "BuildingAirflowNetwork"
MOISTURE_COMFORT_OUTPUT = "relative_humidity_percent"

MOISTURE_FUTURE_LATENT_HEAT_EFFECTS = "latent_heat_effects_later"
MOISTURE_FUTURE_CONDENSATION_RISK = "condensation_risk_later"
MOISTURE_FUTURE_MOLD_RISK = "mold_risk_later"
MOISTURE_FUTURE_WALL_BUFFERING = "wall_moisture_buffering_later"
MOISTURE_FUTURE_HYGROTHERMAL_ENVELOPE = "hygrothermal_envelope_model_later"


@dataclass
class MoistureArchitectureDecision:
    """
    Formal architecture decision for ABBEY moisture/humidity modelling.

    This is intentionally not a solver.
    It only locks the modelling structure before implementation.
    """

    model_family: str = MOISTURE_MODEL_FAMILY

    state_variable: str = MOISTURE_STATE_VARIABLE
    derived_variable: str = MOISTURE_DERIVED_VARIABLE

    spatial_resolution: str = MOISTURE_SPATIAL_RESOLUTION
    multizone_mode: str = MOISTURE_MULTIZONE_MODE

    outside_boundary_source: str = MOISTURE_OUTDOOR_BOUNDARY_SOURCE
    airflow_source: str = MOISTURE_AIRFLOW_SOURCE
    temperature_source: str = MOISTURE_TEMPERATURE_SOURCE
    parameter_source: str = MOISTURE_PARAMETER_SOURCE

    people_source_mode: str = MOISTURE_PEOPLE_SOURCE_MODE
    activity_source_mode: str = MOISTURE_ACTIVITY_SOURCE_MODE

    wall_storage_mode: str = MOISTURE_WALL_STORAGE_MODE
    hygrothermal_upgrade_ready: bool = MOISTURE_HYGROTHERMAL_UPGRADE_READY

    state_variables: List[str] = None
    derived_variables: List[str] = None

    decision: str = MOISTURE_MODEL_DECISION

    def __post_init__(self) -> None:
        if self.state_variables is None:
            self.state_variables = [
                MOISTURE_STATE_VARIABLE,
            ]

        if self.derived_variables is None:
            self.derived_variables = [
                MOISTURE_DERIVED_VARIABLE,
            ]

        self.model_family = str(self.model_family).strip().lower()
        self.state_variable = str(self.state_variable).strip().lower()
        self.derived_variable = str(self.derived_variable).strip().lower()

        self.spatial_resolution = str(self.spatial_resolution).strip().lower()
        self.multizone_mode = str(self.multizone_mode).strip().lower()

        self.outside_boundary_source = str(self.outside_boundary_source).strip()
        self.airflow_source = str(self.airflow_source).strip()
        self.temperature_source = str(self.temperature_source).strip()
        self.parameter_source = str(self.parameter_source).strip()

        self.people_source_mode = str(self.people_source_mode).strip().lower()
        self.activity_source_mode = str(self.activity_source_mode).strip().lower()

        self.wall_storage_mode = str(self.wall_storage_mode).strip().lower()
        self.decision = str(self.decision).strip().lower()

        self._validate()

    def _validate(self) -> None:
        if self.model_family != MOISTURE_MODEL_FAMILY:
            raise ValueError(
                "model_family must be " + MOISTURE_MODEL_FAMILY + "."
            )

        if self.state_variable != MOISTURE_STATE_VARIABLE:
            raise ValueError(
                "Moisture state variable must be humidity ratio."
            )

        if self.derived_variable != MOISTURE_DERIVED_VARIABLE:
            raise ValueError(
                "Moisture derived variable must be relative humidity."
            )

        if self.spatial_resolution != MOISTURE_SPATIAL_RESOLUTION:
            raise ValueError(
                "Moisture model spatial_resolution must be zone."
            )

        if self.multizone_mode != MOISTURE_MULTIZONE_MODE:
            raise ValueError(
                "Moisture model must be multizone."
            )

        if self.outside_boundary_source != MOISTURE_OUTDOOR_BOUNDARY_SOURCE:
            raise ValueError(
                "outside_boundary_source must be WeatherState."
            )

        if self.airflow_source != MOISTURE_AIRFLOW_SOURCE:
            raise ValueError(
                "airflow_source must be BuildingAirflowNetwork."
            )

        if self.temperature_source != MOISTURE_TEMPERATURE_SOURCE:
            raise ValueError(
                "temperature_source must be BuildingThermalState."
            )

        if self.parameter_source != MOISTURE_PARAMETER_SOURCE:
            raise ValueError(
                "parameter_source must be ZoneModel."
            )

        if self.people_source_mode != MOISTURE_PEOPLE_SOURCE_MODE:
            raise ValueError(
                "people_source_mode must be "
                + MOISTURE_PEOPLE_SOURCE_MODE
                + "."
            )

        if self.activity_source_mode != MOISTURE_ACTIVITY_SOURCE_MODE:
            raise ValueError(
                "activity_source_mode must be "
                + MOISTURE_ACTIVITY_SOURCE_MODE
                + "."
            )

        if self.wall_storage_mode != MOISTURE_WALL_STORAGE_MODE:
            raise ValueError(
                "Phase 6 must not include wall moisture storage yet."
            )

        if not self.hygrothermal_upgrade_ready:
            raise ValueError(
                "Phase 6 architecture must keep future hygrothermal upgrade open."
            )

        if self.state_variables != [MOISTURE_STATE_VARIABLE]:
            raise ValueError(
                "state_variables must contain only humidity_ratio_kg_water_per_kg_dry_air."
            )

        if self.derived_variables != [MOISTURE_DERIVED_VARIABLE]:
            raise ValueError(
                "derived_variables must contain only relative_humidity_percent."
            )

    def copy(self, **updates: Any) -> "MoistureArchitectureDecision":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_family": self.model_family,
            "state_variable": self.state_variable,
            "derived_variable": self.derived_variable,
            "spatial_resolution": self.spatial_resolution,
            "multizone_mode": self.multizone_mode,
            "outside_boundary_source": self.outside_boundary_source,
            "airflow_source": self.airflow_source,
            "temperature_source": self.temperature_source,
            "parameter_source": self.parameter_source,
            "people_source_mode": self.people_source_mode,
            "activity_source_mode": self.activity_source_mode,
            "wall_storage_mode": self.wall_storage_mode,
            "hygrothermal_upgrade_ready": self.hygrothermal_upgrade_ready,
            "state_variables": list(self.state_variables),
            "derived_variables": list(self.derived_variables),
            "decision": self.decision,
        }

@dataclass
class MoistureCouplingRules:
    """
    Explicit coupling rules for Phase 6 moisture model.

    Correct Phase 6 dependency direction:

        thermal -> moisture
        airflow -> moisture
        moisture -> comfort/perception

    Not yet:

        moisture -> thermal

    Later we can add latent loads, condensation risk, mold risk,
    wall buffering, and hygrothermal envelope modelling.
    """

    thermal_to_moisture: str = MOISTURE_COUPLING_THERMAL_TO_MOISTURE
    airflow_to_moisture: str = MOISTURE_COUPLING_AIRFLOW_TO_MOISTURE
    moisture_to_comfort: str = MOISTURE_COUPLING_MOISTURE_TO_COMFORT

    moisture_to_thermal: str = MOISTURE_COUPLING_NOT_MOISTURE_TO_THERMAL

    thermal_input: str = MOISTURE_THERMAL_INPUT
    airflow_input: str = MOISTURE_AIRFLOW_INPUT
    comfort_output: str = MOISTURE_COMFORT_OUTPUT

    future_latent_heat_effects: str = MOISTURE_FUTURE_LATENT_HEAT_EFFECTS
    future_condensation_risk: str = MOISTURE_FUTURE_CONDENSATION_RISK
    future_mold_risk: str = MOISTURE_FUTURE_MOLD_RISK
    future_wall_buffering: str = MOISTURE_FUTURE_WALL_BUFFERING
    future_hygrothermal_envelope: str = MOISTURE_FUTURE_HYGROTHERMAL_ENVELOPE

    def __post_init__(self) -> None:
        self.thermal_to_moisture = str(self.thermal_to_moisture).strip().lower()
        self.airflow_to_moisture = str(self.airflow_to_moisture).strip().lower()
        self.moisture_to_comfort = str(self.moisture_to_comfort).strip().lower()
        self.moisture_to_thermal = str(self.moisture_to_thermal).strip().lower()

        self._validate()

    def _validate(self) -> None:
        if self.thermal_to_moisture != MOISTURE_COUPLING_THERMAL_TO_MOISTURE:
            raise ValueError(
                "Phase 6 coupling must include thermal -> moisture."
            )

        if self.airflow_to_moisture != MOISTURE_COUPLING_AIRFLOW_TO_MOISTURE:
            raise ValueError(
                "Phase 6 coupling must include airflow -> moisture."
            )

        if self.moisture_to_comfort != MOISTURE_COUPLING_MOISTURE_TO_COMFORT:
            raise ValueError(
                "Phase 6 coupling must include moisture -> comfort/perception."
            )

        if self.moisture_to_thermal != MOISTURE_COUPLING_NOT_MOISTURE_TO_THERMAL:
            raise ValueError(
                "Phase 6 must not send moisture effects back to thermal yet."
            )

    def coupling_order(self) -> List[str]:
        return [
            self.thermal_to_moisture,
            self.airflow_to_moisture,
            self.moisture_to_comfort,
        ]

    def future_extensions(self) -> List[str]:
        return [
            self.future_latent_heat_effects,
            self.future_condensation_risk,
            self.future_mold_risk,
            self.future_wall_buffering,
            self.future_hygrothermal_envelope,
        ]

    def copy(self, **updates: Any) -> "MoistureCouplingRules":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "coupling_order": self.coupling_order(),
            "thermal_to_moisture": self.thermal_to_moisture,
            "airflow_to_moisture": self.airflow_to_moisture,
            "moisture_to_comfort": self.moisture_to_comfort,
            "moisture_to_thermal": self.moisture_to_thermal,
            "thermal_input": self.thermal_input,
            "airflow_input": self.airflow_input,
            "comfort_output": self.comfort_output,
            "future_extensions": self.future_extensions(),
        }



@dataclass
class ZoneMoistureState:
    """
    Dynamic moisture state for one zone.

    Main transported state:
        humidity_ratio_kg_kg

    Derived/debug output:
        relative_humidity_percent

    Relative humidity depends on temperature and pressure, so it is not the
    conserved transported state.
    """

    zone_id: str
    humidity_ratio_kg_kg: float
    relative_humidity_percent: float = DEFAULT_INITIAL_RELATIVE_HUMIDITY_PERCENT

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneMoistureState.zone_id cannot be empty.")

        self.humidity_ratio_kg_kg = clamp_humidity_ratio(
            self.humidity_ratio_kg_kg
        )

        self.relative_humidity_percent = _clamp_relative_humidity_percent(
            self.relative_humidity_percent
        )

    def copy(self, **updates: Any) -> "ZoneMoistureState":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "humidity_ratio_kg_kg": self.humidity_ratio_kg_kg,
            "relative_humidity_percent": self.relative_humidity_percent,
        }
    
@dataclass
class BuildingMoistureState:
    """
    Dynamic moisture state for all zones.
    """

    zone_states: Dict[str, ZoneMoistureState] = None

    def __post_init__(self) -> None:
        if self.zone_states is None:
            self.zone_states = {}

        cleaned = {}

        for zone_id, state in self.zone_states.items():
            if not isinstance(state, ZoneMoistureState):
                raise TypeError(
                    "BuildingMoistureState.zone_states must contain "
                    "ZoneMoistureState objects."
                )

            if zone_id != state.zone_id:
                raise ValueError(
                    "BuildingMoistureState key "
                    + zone_id
                    + " does not match ZoneMoistureState.zone_id "
                    + state.zone_id
                )

            cleaned[zone_id] = state

        self.zone_states = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_states.keys())

    def has_zone(self, zone_id: str) -> bool:
        return zone_id in self.zone_states

    def get_zone_state(self, zone_id: str) -> ZoneMoistureState:
        if zone_id not in self.zone_states:
            raise KeyError(
                "Moisture state for zone "
                + zone_id
                + " not found."
            )

        return self.zone_states[zone_id]

    def set_zone_state(self, zone_state: ZoneMoistureState) -> None:
        if not isinstance(zone_state, ZoneMoistureState):
            raise TypeError("zone_state must be ZoneMoistureState.")

        self.zone_states[zone_state.zone_id] = zone_state

    def humidity_ratio_by_zone_kg_kg(self) -> Dict[str, float]:
        return {
            zone_id: state.humidity_ratio_kg_kg
            for zone_id, state in self.zone_states.items()
        }

    def relative_humidity_by_zone_percent(self) -> Dict[str, float]:
        return {
            zone_id: state.relative_humidity_percent
            for zone_id, state in self.zone_states.items()
        }

    def copy(self, **updates: Any) -> "BuildingMoistureState":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "humidity_ratio_by_zone_kg_kg": self.humidity_ratio_by_zone_kg_kg(),
            "relative_humidity_by_zone_percent": self.relative_humidity_by_zone_percent(),
            "zone_states": {
                zone_id: state.to_dict()
                for zone_id, state in self.zone_states.items()
            },
        }

@dataclass
class ZoneMoistureParameters:
    """
    Static moisture parameters for one zone.

    Phase 6.4:
    - maps ZoneModel moisture-relevant inputs
    - derives dry air mass from air volume
    - does not model wall moisture buffering yet
    """

    zone_id: str

    air_volume_m3: float
    dry_air_mass_kg: float

    initial_relative_humidity_percent: float = DEFAULT_INITIAL_RELATIVE_HUMIDITY_PERCENT

    moisture_buffering_enabled: bool = DEFAULT_MOISTURE_BUFFERING_ENABLED

    source: str = "ZoneModel"

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneMoistureParameters.zone_id cannot be empty.")

        self.air_volume_m3 = _positive_float(
            self.air_volume_m3,
            "air_volume_m3",
            self.zone_id,
        )

        if self.dry_air_mass_kg <= 0.0:
            self.dry_air_mass_kg = (
                MOISTURE_AIR_DENSITY_KG_M3
                * self.air_volume_m3
            )

        self.dry_air_mass_kg = _positive_float(
            self.dry_air_mass_kg,
            "dry_air_mass_kg",
            self.zone_id,
        )

        self.initial_relative_humidity_percent = clamp_relative_humidity(
            self.initial_relative_humidity_percent
        )

        self.moisture_buffering_enabled = bool(
            self.moisture_buffering_enabled
        )

        if self.moisture_buffering_enabled:
            raise ValueError(
                "moisture_buffering_enabled is reserved for later phases. "
                "Phase 6.4 must not activate moisture buffering yet."
            )

    def copy(self, **updates: Any) -> "ZoneMoistureParameters":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "air_volume_m3": self.air_volume_m3,
            "dry_air_mass_kg": self.dry_air_mass_kg,
            "initial_relative_humidity_percent": self.initial_relative_humidity_percent,
            "moisture_buffering_enabled": self.moisture_buffering_enabled,
            "source": self.source,
        }
    
@dataclass
class BuildingMoistureParameters:
    """
    Static moisture parameters for all zones.
    """

    zone_parameters: Dict[str, ZoneMoistureParameters] = None

    def __post_init__(self) -> None:
        if self.zone_parameters is None:
            self.zone_parameters = {}

        cleaned = {}

        for zone_id, parameters in self.zone_parameters.items():
            if not isinstance(parameters, ZoneMoistureParameters):
                raise TypeError(
                    "BuildingMoistureParameters.zone_parameters must contain "
                    "ZoneMoistureParameters objects."
                )

            if zone_id != parameters.zone_id:
                raise ValueError(
                    "BuildingMoistureParameters key "
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

    def get_zone_parameters(self, zone_id: str) -> ZoneMoistureParameters:
        if zone_id not in self.zone_parameters:
            raise KeyError(
                "Moisture parameters for zone "
                + zone_id
                + " not found."
            )

        return self.zone_parameters[zone_id]

    def dry_air_mass_by_zone_kg(self) -> Dict[str, float]:
        return {
            zone_id: parameters.dry_air_mass_kg
            for zone_id, parameters in self.zone_parameters.items()
        }

    def air_volume_by_zone_m3(self) -> Dict[str, float]:
        return {
            zone_id: parameters.air_volume_m3
            for zone_id, parameters in self.zone_parameters.items()
        }

    def copy(self, **updates: Any) -> "BuildingMoistureParameters":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dry_air_mass_by_zone_kg": self.dry_air_mass_by_zone_kg(),
            "air_volume_by_zone_m3": self.air_volume_by_zone_m3(),
            "zone_parameters": {
                zone_id: parameters.to_dict()
                for zone_id, parameters in self.zone_parameters.items()
            },
        }
    
@dataclass
class ZoneMoistureSourceInput:
    """
    Clean bridge input for moisture generation in one zone.

    This is the coupling boundary.

    Agents/actions/controllers are converted outside moisture.py.
    This module only receives physical moisture generation in kg/h.
    """

    zone_id: str
    moisture_generation_kg_h: float = 0.0
    source_type: str = MOISTURE_SOURCE_GENERIC

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneMoistureSourceInput.zone_id cannot be empty.")

        self.moisture_generation_kg_h = _non_negative_float(
            self.moisture_generation_kg_h,
            "moisture_generation_kg_h",
            self.zone_id,
        )

        self.source_type = str(self.source_type).strip().lower()

        if self.source_type not in VALID_MOISTURE_SOURCE_TYPES:
            raise ValueError(
                "Invalid moisture source_type: "
                + self.source_type
                + ". Valid source types are: "
                + str(sorted(list(VALID_MOISTURE_SOURCE_TYPES)))
            )

    def moisture_generation_kg_s(self) -> float:
        return self.moisture_generation_kg_h / 3600.0

    def copy(self, **updates: Any) -> "ZoneMoistureSourceInput":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "moisture_generation_kg_h": self.moisture_generation_kg_h,
            "moisture_generation_kg_s": self.moisture_generation_kg_s(),
            "source_type": self.source_type,
        }
    
@dataclass
class BuildingMoistureSourceInputs:
    """
    Building-level container for clean moisture source inputs.

    Structure:
        sources_by_zone = {
            zone_id: [
                ZoneMoistureSourceInput(...),
                ZoneMoistureSourceInput(...),
            ]
        }
    """

    sources_by_zone: Dict[str, List[ZoneMoistureSourceInput]] = None

    def __post_init__(self) -> None:
        if self.sources_by_zone is None:
            self.sources_by_zone = {}

        cleaned = {}

        for zone_id, sources in self.sources_by_zone.items():
            if sources is None:
                sources = []

            if not isinstance(sources, list):
                raise TypeError(
                    "BuildingMoistureSourceInputs.sources_by_zone values must be lists."
                )

            cleaned_sources = []

            for source in sources:
                if not isinstance(source, ZoneMoistureSourceInput):
                    raise TypeError(
                        "sources_by_zone must contain ZoneMoistureSourceInput objects."
                    )

                if source.zone_id != zone_id:
                    raise ValueError(
                        "Moisture source zone_id "
                        + source.zone_id
                        + " does not match sources_by_zone key "
                        + zone_id
                    )

                cleaned_sources.append(source)

            cleaned[zone_id] = cleaned_sources

        self.sources_by_zone = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.sources_by_zone.keys())

    def get_sources_for_zone(
        self,
        zone_id: str,
    ) -> List[ZoneMoistureSourceInput]:
        return list(self.sources_by_zone.get(zone_id, []))

    def add_source(
        self,
        source: ZoneMoistureSourceInput,
    ) -> None:
        if not isinstance(source, ZoneMoistureSourceInput):
            raise TypeError("source must be ZoneMoistureSourceInput.")

        if source.zone_id not in self.sources_by_zone:
            self.sources_by_zone[source.zone_id] = []

        self.sources_by_zone[source.zone_id].append(source)

    def moisture_generation_kg_h_by_zone(self) -> Dict[str, float]:
        out = {}

        for zone_id, sources in self.sources_by_zone.items():
            out[zone_id] = sum(
                source.moisture_generation_kg_h
                for source in sources
            )

        return out

    def moisture_generation_kg_s_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: moisture_generation_kg_h / 3600.0
            for zone_id, moisture_generation_kg_h
            in self.moisture_generation_kg_h_by_zone().items()
        }

    def total_moisture_generation_kg_h(self) -> float:
        return sum(
            self.moisture_generation_kg_h_by_zone().values()
        )

    def total_moisture_generation_kg_s(self) -> float:
        return self.total_moisture_generation_kg_h() / 3600.0

    def copy(self, **updates: Any) -> "BuildingMoistureSourceInputs":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "moisture_generation_kg_h_by_zone": self.moisture_generation_kg_h_by_zone(),
            "moisture_generation_kg_s_by_zone": self.moisture_generation_kg_s_by_zone(),
            "total_moisture_generation_kg_h": self.total_moisture_generation_kg_h(),
            "total_moisture_generation_kg_s": self.total_moisture_generation_kg_s(),
            "sources_by_zone": {
                zone_id: [
                    source.to_dict()
                    for source in sources
                ]
                for zone_id, sources in self.sources_by_zone.items()
            },
        }
    
@dataclass
class MoistureGenerationRecord:
    """
    Moisture generation record for one zone.

    Phase 6.6:
    - people moisture generation only
    - no activity/metabolic dependency yet

    Later:
    - sleeping
    - cooking
    - showering
    - exercise
    - activity-specific latent moisture
    """

    zone_id: str

    number_of_people: float = 0.0
    moisture_generation_per_person_kg_h: float = DEFAULT_MOISTURE_GENERATION_PER_PERSON_KG_H

    moisture_generation_kg_h: float = 0.0

    source_type: str = MOISTURE_SOURCE_PEOPLE
    source: str = MOISTURE_GENERATION_SOURCE_PEOPLE

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("MoistureGenerationRecord.zone_id cannot be empty.")

        self.number_of_people = _non_negative_float(
            self.number_of_people,
            "number_of_people",
            self.zone_id,
        )

        self.moisture_generation_per_person_kg_h = _non_negative_float(
            self.moisture_generation_per_person_kg_h,
            "moisture_generation_per_person_kg_h",
            self.zone_id,
        )

        if self.moisture_generation_kg_h <= 0.0:
            self.moisture_generation_kg_h = (
                self.number_of_people
                * self.moisture_generation_per_person_kg_h
            )

        self.moisture_generation_kg_h = _non_negative_float(
            self.moisture_generation_kg_h,
            "moisture_generation_kg_h",
            self.zone_id,
        )

        self.source_type = str(self.source_type).strip().lower()

        if self.source_type not in VALID_MOISTURE_SOURCE_TYPES:
            raise ValueError(
                "Invalid moisture source_type: "
                + self.source_type
            )

    def moisture_generation_kg_s(self) -> float:
        return self.moisture_generation_kg_h / 3600.0

    def to_source_input(self) -> ZoneMoistureSourceInput:
        return ZoneMoistureSourceInput(
            zone_id=self.zone_id,
            moisture_generation_kg_h=self.moisture_generation_kg_h,
            source_type=self.source_type,
        )

    def copy(self, **updates: Any) -> "MoistureGenerationRecord":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "number_of_people": self.number_of_people,
            "moisture_generation_per_person_kg_h": self.moisture_generation_per_person_kg_h,
            "moisture_generation_kg_h": self.moisture_generation_kg_h,
            "moisture_generation_kg_s": self.moisture_generation_kg_s(),
            "source_type": self.source_type,
            "source": self.source,
        }
    
@dataclass
class BuildingMoistureGenerationResult:
    """
    Moisture generation result for all zones.
    """

    zone_records: Dict[str, MoistureGenerationRecord] = None

    def __post_init__(self) -> None:
        if self.zone_records is None:
            self.zone_records = {}

        cleaned = {}

        for zone_id, record in self.zone_records.items():
            if not isinstance(record, MoistureGenerationRecord):
                raise TypeError(
                    "BuildingMoistureGenerationResult.zone_records must contain "
                    "MoistureGenerationRecord objects."
                )

            if zone_id != record.zone_id:
                raise ValueError(
                    "BuildingMoistureGenerationResult key "
                    + zone_id
                    + " does not match record.zone_id "
                    + record.zone_id
                )

            cleaned[zone_id] = record

        self.zone_records = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_records.keys())

    def get_zone_record(self, zone_id: str) -> MoistureGenerationRecord:
        if zone_id not in self.zone_records:
            return MoistureGenerationRecord(
                zone_id=zone_id,
                number_of_people=0.0,
                moisture_generation_per_person_kg_h=DEFAULT_MOISTURE_GENERATION_PER_PERSON_KG_H,
                source_type=MOISTURE_SOURCE_PEOPLE,
                source="default_empty_zone",
            )

        return self.zone_records[zone_id]

    def moisture_generation_kg_h_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: record.moisture_generation_kg_h
            for zone_id, record in self.zone_records.items()
        }

    def moisture_generation_kg_s_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: record.moisture_generation_kg_s()
            for zone_id, record in self.zone_records.items()
        }

    def total_moisture_generation_kg_h(self) -> float:
        return sum(
            record.moisture_generation_kg_h
            for record in self.zone_records.values()
        )

    def total_moisture_generation_kg_s(self) -> float:
        return self.total_moisture_generation_kg_h() / 3600.0

    def to_source_inputs(self) -> BuildingMoistureSourceInputs:
        sources_by_zone = {}

        for zone_id, record in self.zone_records.items():
            sources_by_zone[zone_id] = [
                record.to_source_input()
            ]

        return BuildingMoistureSourceInputs(
            sources_by_zone=sources_by_zone,
        )

    def copy(self, **updates: Any) -> "BuildingMoistureGenerationResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "moisture_generation_kg_h_by_zone": self.moisture_generation_kg_h_by_zone(),
            "moisture_generation_kg_s_by_zone": self.moisture_generation_kg_s_by_zone(),
            "total_moisture_generation_kg_h": self.total_moisture_generation_kg_h(),
            "total_moisture_generation_kg_s": self.total_moisture_generation_kg_s(),
            "zone_records": {
                zone_id: record.to_dict()
                for zone_id, record in self.zone_records.items()
            },
        }
    
@dataclass
class OutdoorMoistureBoundary:
    """
    Outdoor moisture boundary condition.

    Converts outdoor weather humidity into humidity ratio.

    Main transported quantity:
        outdoor_humidity_ratio_kg_kg

    Derived/reference quantities:
        outdoor_relative_humidity_percent
        outdoor_temperature_c
        atmospheric_pressure_pa
    """

    outdoor_humidity_ratio_kg_kg: float

    outdoor_relative_humidity_percent: float = DEFAULT_OUTDOOR_RELATIVE_HUMIDITY_PERCENT
    outdoor_temperature_c: float = DEFAULT_OUTDOOR_TEMPERATURE_C
    atmospheric_pressure_pa: float = DEFAULT_ATMOSPHERIC_PRESSURE_PA

    source: str = OUTDOOR_MOISTURE_BOUNDARY_SOURCE

    def __post_init__(self) -> None:
        self.outdoor_humidity_ratio_kg_kg = clamp_humidity_ratio(
            self.outdoor_humidity_ratio_kg_kg
        )

        self.outdoor_relative_humidity_percent = clamp_relative_humidity(
            self.outdoor_relative_humidity_percent
        )

        self.outdoor_temperature_c = float(self.outdoor_temperature_c)

        self.atmospheric_pressure_pa = clamp_atmospheric_pressure_pa(
            self.atmospheric_pressure_pa
        )

    def copy(self, **updates: Any) -> "OutdoorMoistureBoundary":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outdoor_humidity_ratio_kg_kg": self.outdoor_humidity_ratio_kg_kg,
            "outdoor_relative_humidity_percent": self.outdoor_relative_humidity_percent,
            "outdoor_temperature_c": self.outdoor_temperature_c,
            "atmospheric_pressure_pa": self.atmospheric_pressure_pa,
            "source": self.source,
        }
    
@dataclass
class MoistureTransportTarget:
    """
    Moisture transport target connected to one zone by airflow.

    The transported quantity is humidity ratio, not relative humidity.

    Airflow comes from Phase 5 BuildingAirflowNetwork.
    This module does not calculate airflow.
    """

    target_id: str
    target_type: str

    humidity_ratio_kg_kg: float
    airflow_m3_s: float

    dry_air_mass_flow_kg_s: float = 0.0

    source_zone_id: str = ""
    source: str = ""

    def __post_init__(self) -> None:
        if not self.target_id:
            raise ValueError("MoistureTransportTarget.target_id cannot be empty.")

        if not self.target_type:
            raise ValueError("MoistureTransportTarget.target_type cannot be empty.")

        self.target_type = str(self.target_type).strip().lower()

        self.humidity_ratio_kg_kg = clamp_humidity_ratio(
            self.humidity_ratio_kg_kg
        )

        self.airflow_m3_s = _non_negative_float(
            self.airflow_m3_s,
            "airflow_m3_s",
            self.target_id,
        )

        if self.dry_air_mass_flow_kg_s <= 0.0:
            self.dry_air_mass_flow_kg_s = (
                MOISTURE_AIR_DENSITY_KG_M3
                * self.airflow_m3_s
            )

        self.dry_air_mass_flow_kg_s = _non_negative_float(
            self.dry_air_mass_flow_kg_s,
            "dry_air_mass_flow_kg_s",
            self.target_id,
        )

    def copy(self, **updates: Any) -> "MoistureTransportTarget":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id": self.target_id,
            "target_type": self.target_type,
            "humidity_ratio_kg_kg": self.humidity_ratio_kg_kg,
            "airflow_m3_s": self.airflow_m3_s,
            "dry_air_mass_flow_kg_s": self.dry_air_mass_flow_kg_s,
            "source_zone_id": self.source_zone_id,
            "source": self.source,
        }
    
@dataclass
class ZoneMoistureTransportTargets:
    """
    Moisture transport targets for one zone.
    """

    zone_id: str
    targets: List[MoistureTransportTarget] = None

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneMoistureTransportTargets.zone_id cannot be empty.")

        if self.targets is None:
            self.targets = []

        cleaned = []

        for target in self.targets:
            if not isinstance(target, MoistureTransportTarget):
                raise TypeError(
                    "ZoneMoistureTransportTargets.targets must contain "
                    "MoistureTransportTarget objects."
                )

            cleaned.append(target)

        self.targets = cleaned

    def add_target(self, target: MoistureTransportTarget) -> None:
        if not isinstance(target, MoistureTransportTarget):
            raise TypeError("target must be MoistureTransportTarget.")

        self.targets.append(target)

    def total_airflow_m3_s(self) -> float:
        return sum(
            target.airflow_m3_s
            for target in self.targets
        )

    def total_dry_air_mass_flow_kg_s(self) -> float:
        return sum(
            target.dry_air_mass_flow_kg_s
            for target in self.targets
        )

    def copy(self, **updates: Any) -> "ZoneMoistureTransportTargets":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "total_airflow_m3_s": self.total_airflow_m3_s(),
            "total_dry_air_mass_flow_kg_s": self.total_dry_air_mass_flow_kg_s(),
            "targets": [
                target.to_dict()
                for target in self.targets
            ],
        }


@dataclass
class BuildingMoistureTransportResult:
    """
    Moisture transport targets for all zones.

    This is the bridge between:
        BuildingAirflowNetwork -> Moisture timestep update
    """

    zone_targets: Dict[str, ZoneMoistureTransportTargets] = None

    def __post_init__(self) -> None:
        if self.zone_targets is None:
            self.zone_targets = {}

        cleaned = {}

        for zone_id, targets in self.zone_targets.items():
            if not isinstance(targets, ZoneMoistureTransportTargets):
                raise TypeError(
                    "BuildingMoistureTransportResult.zone_targets must contain "
                    "ZoneMoistureTransportTargets objects."
                )

            if zone_id != targets.zone_id:
                raise ValueError(
                    "BuildingMoistureTransportResult key "
                    + zone_id
                    + " does not match targets.zone_id "
                    + targets.zone_id
                )

            cleaned[zone_id] = targets

        self.zone_targets = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_targets.keys())

    def get_targets_for_zone(self, zone_id: str) -> ZoneMoistureTransportTargets:
        if zone_id not in self.zone_targets:
            return ZoneMoistureTransportTargets(zone_id=zone_id)

        return self.zone_targets[zone_id]

    def total_airflow_m3_s_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: targets.total_airflow_m3_s()
            for zone_id, targets in self.zone_targets.items()
        }

    def total_dry_air_mass_flow_kg_s_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: targets.total_dry_air_mass_flow_kg_s()
            for zone_id, targets in self.zone_targets.items()
        }

    def copy(self, **updates: Any) -> "BuildingMoistureTransportResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_airflow_m3_s_by_zone": self.total_airflow_m3_s_by_zone(),
            "total_dry_air_mass_flow_kg_s_by_zone": self.total_dry_air_mass_flow_kg_s_by_zone(),
            "zone_targets": {
                zone_id: targets.to_dict()
                for zone_id, targets in self.zone_targets.items()
            },
        }
    
@dataclass
class ZoneMoistureUpdateResult:
    """
    Moisture timestep update result for one zone.

    Stored/conserved state:
        humidity_ratio_kg_kg

    Derived output:
        relative_humidity_percent
    """

    zone_id: str

    old_humidity_ratio_kg_kg: float
    new_humidity_ratio_kg_kg: float

    old_relative_humidity_percent: float
    new_relative_humidity_percent: float

    dry_air_mass_kg: float
    moisture_generation_kg_s: float

    temperature_c: float
    atmospheric_pressure_pa: float

    targets: List[MoistureTransportTarget] = None

    dt_seconds: float = 0.0
    method: str = MOISTURE_TIMESTEP_METHOD

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneMoistureUpdateResult.zone_id cannot be empty.")

        self.old_humidity_ratio_kg_kg = clamp_humidity_ratio(
            self.old_humidity_ratio_kg_kg
        )

        self.new_humidity_ratio_kg_kg = clamp_humidity_ratio(
            self.new_humidity_ratio_kg_kg
        )

        self.old_relative_humidity_percent = clamp_relative_humidity(
            self.old_relative_humidity_percent
        )

        self.new_relative_humidity_percent = clamp_relative_humidity(
            self.new_relative_humidity_percent
        )

        self.dry_air_mass_kg = _positive_float(
            self.dry_air_mass_kg,
            "dry_air_mass_kg",
            self.zone_id,
        )

        self.moisture_generation_kg_s = _non_negative_float(
            self.moisture_generation_kg_s,
            "moisture_generation_kg_s",
            self.zone_id,
        )

        self.temperature_c = float(self.temperature_c)

        self.atmospheric_pressure_pa = clamp_atmospheric_pressure_pa(
            self.atmospheric_pressure_pa
        )

        if self.targets is None:
            self.targets = []

        cleaned = []

        for target in self.targets:
            if not isinstance(target, MoistureTransportTarget):
                raise TypeError(
                    "ZoneMoistureUpdateResult.targets must contain "
                    "MoistureTransportTarget objects."
                )

            cleaned.append(target)

        self.targets = cleaned

        self.dt_seconds = _positive_float(
            self.dt_seconds,
            "dt_seconds",
            self.zone_id,
        )

    def to_zone_moisture_state(self) -> ZoneMoistureState:
        return ZoneMoistureState(
            zone_id=self.zone_id,
            humidity_ratio_kg_kg=self.new_humidity_ratio_kg_kg,
            relative_humidity_percent=self.new_relative_humidity_percent,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "old_humidity_ratio_kg_kg": self.old_humidity_ratio_kg_kg,
            "new_humidity_ratio_kg_kg": self.new_humidity_ratio_kg_kg,
            "old_relative_humidity_percent": self.old_relative_humidity_percent,
            "new_relative_humidity_percent": self.new_relative_humidity_percent,
            "dry_air_mass_kg": self.dry_air_mass_kg,
            "moisture_generation_kg_s": self.moisture_generation_kg_s,
            "temperature_c": self.temperature_c,
            "atmospheric_pressure_pa": self.atmospheric_pressure_pa,
            "dt_seconds": self.dt_seconds,
            "method": self.method,
            "targets": [
                target.to_dict()
                for target in self.targets
            ],
        }


@dataclass
class BuildingMoistureStepResult:
    """
    Moisture timestep update result for all zones.
    """

    updated_moisture_state: BuildingMoistureState
    zone_results: Dict[str, ZoneMoistureUpdateResult] = None

    dt_minutes: float = DEFAULT_MOISTURE_DT_MINUTES
    method: str = MOISTURE_TIMESTEP_METHOD

    def __post_init__(self) -> None:
        if not isinstance(self.updated_moisture_state, BuildingMoistureState):
            raise TypeError(
                "updated_moisture_state must be BuildingMoistureState."
            )

        if self.zone_results is None:
            self.zone_results = {}

        cleaned = {}

        for zone_id, result in self.zone_results.items():
            if not isinstance(result, ZoneMoistureUpdateResult):
                raise TypeError(
                    "BuildingMoistureStepResult.zone_results must contain "
                    "ZoneMoistureUpdateResult objects."
                )

            if zone_id != result.zone_id:
                raise ValueError(
                    "BuildingMoistureStepResult key "
                    + zone_id
                    + " does not match result.zone_id "
                    + result.zone_id
                )

            cleaned[zone_id] = result

        self.zone_results = cleaned

        self.dt_minutes = _positive_float(
            self.dt_minutes,
            "dt_minutes",
            "BuildingMoistureStepResult",
        )

    def humidity_ratio_by_zone_kg_kg(self) -> Dict[str, float]:
        return self.updated_moisture_state.humidity_ratio_by_zone_kg_kg()

    def relative_humidity_by_zone_percent(self) -> Dict[str, float]:
        return self.updated_moisture_state.relative_humidity_by_zone_percent()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "updated_moisture_state": self.updated_moisture_state.to_dict(),
            "humidity_ratio_by_zone_kg_kg": self.humidity_ratio_by_zone_kg_kg(),
            "relative_humidity_by_zone_percent": self.relative_humidity_by_zone_percent(),
            "dt_minutes": self.dt_minutes,
            "method": self.method,
            "zone_results": {
                zone_id: result.to_dict()
                for zone_id, result in self.zone_results.items()
            },
        }
    
@dataclass
class ZoneMoistureDebugRecord:
    """
    Debug record for one zone after one moisture timestep.
    """

    zone_id: str

    old_humidity_ratio_kg_kg: float
    new_humidity_ratio_kg_kg: float

    old_relative_humidity_percent: float
    new_relative_humidity_percent: float

    temperature_c: float
    atmospheric_pressure_pa: float

    dry_air_mass_kg: float
    moisture_generation_kg_h: float = 0.0
    moisture_generation_kg_s: float = 0.0

    total_transport_airflow_m3_s: float = 0.0
    total_transport_dry_air_mass_flow_kg_s: float = 0.0

    dt_minutes: float = DEFAULT_MOISTURE_DT_MINUTES
    method: str = MOISTURE_TIMESTEP_METHOD

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneMoistureDebugRecord.zone_id cannot be empty.")

        self.old_humidity_ratio_kg_kg = clamp_humidity_ratio(
            self.old_humidity_ratio_kg_kg
        )

        self.new_humidity_ratio_kg_kg = clamp_humidity_ratio(
            self.new_humidity_ratio_kg_kg
        )

        self.old_relative_humidity_percent = clamp_relative_humidity(
            self.old_relative_humidity_percent
        )

        self.new_relative_humidity_percent = clamp_relative_humidity(
            self.new_relative_humidity_percent
        )

        self.temperature_c = float(self.temperature_c)

        self.atmospheric_pressure_pa = clamp_atmospheric_pressure_pa(
            self.atmospheric_pressure_pa
        )

        self.dry_air_mass_kg = _positive_float(
            self.dry_air_mass_kg,
            "dry_air_mass_kg",
            self.zone_id,
        )

        self.moisture_generation_kg_h = _non_negative_float(
            self.moisture_generation_kg_h,
            "moisture_generation_kg_h",
            self.zone_id,
        )

        self.moisture_generation_kg_s = _non_negative_float(
            self.moisture_generation_kg_s,
            "moisture_generation_kg_s",
            self.zone_id,
        )

        self.total_transport_airflow_m3_s = _non_negative_float(
            self.total_transport_airflow_m3_s,
            "total_transport_airflow_m3_s",
            self.zone_id,
        )

        self.total_transport_dry_air_mass_flow_kg_s = _non_negative_float(
            self.total_transport_dry_air_mass_flow_kg_s,
            "total_transport_dry_air_mass_flow_kg_s",
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
            "old_humidity_ratio_kg_kg": self.old_humidity_ratio_kg_kg,
            "new_humidity_ratio_kg_kg": self.new_humidity_ratio_kg_kg,
            "old_relative_humidity_percent": self.old_relative_humidity_percent,
            "new_relative_humidity_percent": self.new_relative_humidity_percent,
            "temperature_c": self.temperature_c,
            "atmospheric_pressure_pa": self.atmospheric_pressure_pa,
            "dry_air_mass_kg": self.dry_air_mass_kg,
            "moisture_generation_kg_h": self.moisture_generation_kg_h,
            "moisture_generation_kg_s": self.moisture_generation_kg_s,
            "total_transport_airflow_m3_s": self.total_transport_airflow_m3_s,
            "total_transport_dry_air_mass_flow_kg_s": self.total_transport_dry_air_mass_flow_kg_s,
            "dt_minutes": self.dt_minutes,
            "method": self.method,
        }


@dataclass
class MoistureStepResult:
    """
    Public result returned by MoistureModel.step(...).
    """

    updated_moisture_state: BuildingMoistureState

    moisture_step_result: BuildingMoistureStepResult
    moisture_transport_result: BuildingMoistureTransportResult
    moisture_source_inputs: BuildingMoistureSourceInputs
    outdoor_moisture_boundary: OutdoorMoistureBoundary

    debug_records: List[ZoneMoistureDebugRecord] = None

    dt_minutes: float = DEFAULT_MOISTURE_DT_MINUTES
    interface_mode: str = MOISTURE_MODEL_INTERFACE_MODE
    coupling_rules: MoistureCouplingRules = None

    def __post_init__(self) -> None:
        if not isinstance(self.updated_moisture_state, BuildingMoistureState):
            raise TypeError(
                "updated_moisture_state must be BuildingMoistureState."
            )

        if not isinstance(self.moisture_step_result, BuildingMoistureStepResult):
            raise TypeError(
                "moisture_step_result must be BuildingMoistureStepResult."
            )

        if not isinstance(self.moisture_transport_result, BuildingMoistureTransportResult):
            raise TypeError(
                "moisture_transport_result must be BuildingMoistureTransportResult."
            )

        if not isinstance(self.moisture_source_inputs, BuildingMoistureSourceInputs):
            raise TypeError(
                "moisture_source_inputs must be BuildingMoistureSourceInputs."
            )

        if not isinstance(self.outdoor_moisture_boundary, OutdoorMoistureBoundary):
            raise TypeError(
                "outdoor_moisture_boundary must be OutdoorMoistureBoundary."
            )

        if self.debug_records is None:
            self.debug_records = []
            
        if self.coupling_rules is None:
            self.coupling_rules = MoistureCouplingRules()

        if not isinstance(self.coupling_rules, MoistureCouplingRules):
            raise TypeError(
                "coupling_rules must be MoistureCouplingRules."
            )
        cleaned = []

        for record in self.debug_records:
            if not isinstance(record, ZoneMoistureDebugRecord):
                raise TypeError(
                    "debug_records must contain ZoneMoistureDebugRecord objects."
                )

            cleaned.append(record)

        self.debug_records = cleaned

        self.dt_minutes = _positive_float(
            self.dt_minutes,
            "dt_minutes",
            "MoistureStepResult",
        )

    def humidity_ratio_by_zone_kg_kg(self) -> Dict[str, float]:
        return self.updated_moisture_state.humidity_ratio_by_zone_kg_kg()

    def relative_humidity_by_zone_percent(self) -> Dict[str, float]:
        return self.updated_moisture_state.relative_humidity_by_zone_percent()

    def moisture_generation_records(self) -> Dict[str, List[ZoneMoistureSourceInput]]:
        return self.moisture_source_inputs.sources_by_zone

    def moisture_generation_kg_h_by_zone(self) -> Dict[str, float]:
        return self.moisture_source_inputs.moisture_generation_kg_h_by_zone()

    def moisture_generation_kg_s_by_zone(self) -> Dict[str, float]:
        return self.moisture_source_inputs.moisture_generation_kg_s_by_zone()

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
            "updated_moisture_state": self.updated_moisture_state.to_dict(),
            "humidity_ratio_by_zone_kg_kg": self.humidity_ratio_by_zone_kg_kg(),
            "relative_humidity_by_zone_percent": self.relative_humidity_by_zone_percent(),
            "moisture_generation_kg_h_by_zone": self.moisture_generation_kg_h_by_zone(),
            "moisture_generation_kg_s_by_zone": self.moisture_generation_kg_s_by_zone(),
            "outdoor_moisture_boundary": self.outdoor_moisture_boundary.to_dict(),
            "moisture_transport_result": self.moisture_transport_result.to_dict(),
            "coupling_rules": self.coupling_rules.to_dict(),
            "moisture_step_result": self.moisture_step_result.to_dict(),
            "moisture_source_inputs": self.moisture_source_inputs.to_dict(),
            "debug_records": self.debug_records_as_dicts(),
            "dt_minutes": self.dt_minutes,
            "interface_mode": self.interface_mode,
        }

@dataclass
class MoistureModel:
    """
    Runner-facing moisture model interface.

    Clean dependency rule:
    - no imports from agents/actions/controllers
    - no airflow calculation
    - no thermal calculation
    - reads thermal_state for zone air temperature
    - reads airflow_network for moisture transport
    - reads weather_state for outdoor moisture boundary
    """

    architecture: MoistureArchitectureDecision = None
    coupling_rules: MoistureCouplingRules = None
    default_dt_minutes: float = DEFAULT_MOISTURE_DT_MINUTES

    def __post_init__(self) -> None:
        if self.architecture is None:
            self.architecture = MoistureArchitectureDecision()

        if not isinstance(self.architecture, MoistureArchitectureDecision):
            raise TypeError(
                "MoistureModel.architecture must be MoistureArchitectureDecision."
            )
        if self.coupling_rules is None:
            self.coupling_rules = MoistureCouplingRules()

        if not isinstance(self.coupling_rules, MoistureCouplingRules):
            raise TypeError(
                "MoistureModel.coupling_rules must be MoistureCouplingRules."
            )

        self.default_dt_minutes = _positive_float(
            self.default_dt_minutes,
            "default_dt_minutes",
            "MoistureModel",
        )

    def make_initial_state(
        self,
        building_model: Any,
        thermal_state: Any = None,
        atmospheric_pressure_pa: float = DEFAULT_ATMOSPHERIC_PRESSURE_PA,
    ) -> BuildingMoistureState:
        return make_initial_building_moisture_state(
            building_model=building_model,
            thermal_state=thermal_state,
            atmospheric_pressure_pa=atmospheric_pressure_pa,
        )

    def step(
        self,
        building_model: Any,
        moisture_state: BuildingMoistureState,
        thermal_state: Any,
        airflow_network: Any,
        weather_state: Any,
        moisture_source_inputs: BuildingMoistureSourceInputs = None,
        dt_minutes: float = None,
    ) -> MoistureStepResult:
        """
        Advance moisture model by one timestep.

        Expected runner call:

            MoistureModel.step(
                building_model,
                moisture_state,
                thermal_state,
                airflow_network,
                weather_state,
                moisture_source_inputs,
                dt_minutes
            )

        moisture_source_inputs:
            clean bridge object from agents/actions/occupancy/activity.
        """

        if building_model is None:
            raise ValueError("building_model cannot be None.")

        if not isinstance(moisture_state, BuildingMoistureState):
            raise TypeError("moisture_state must be BuildingMoistureState.")

        if airflow_network is None:
            raise ValueError("airflow_network cannot be None.")

        if weather_state is None:
            raise ValueError("weather_state cannot be None.")
            
        validate_moisture_coupling_inputs(
            moisture_state=moisture_state,
            thermal_state=thermal_state,
            airflow_network=airflow_network,
        )

        if moisture_source_inputs is None:
            moisture_source_inputs = make_empty_moisture_source_inputs()

        if not isinstance(moisture_source_inputs, BuildingMoistureSourceInputs):
            raise TypeError(
                "moisture_source_inputs must be BuildingMoistureSourceInputs."
            )

        if dt_minutes is None:
            dt_minutes = self.default_dt_minutes

        dt_minutes = _positive_float(
            dt_minutes,
            "dt_minutes",
            "MoistureModel.step",
        )

        building_moisture_parameters = make_building_moisture_parameters(
            building_model
        )

        outdoor_moisture_boundary = make_outdoor_moisture_boundary_from_weather_state(
            weather_state
        )

        moisture_transport_result = make_building_moisture_transport_result(
            moisture_state=moisture_state,
            airflow_network=airflow_network,
            outdoor_moisture_boundary=outdoor_moisture_boundary,
        )

        moisture_step_result = step_building_moisture_state(
            moisture_state=moisture_state,
            building_moisture_parameters=building_moisture_parameters,
            moisture_transport_result=moisture_transport_result,
            moisture_source_inputs=moisture_source_inputs,
            thermal_state=thermal_state,
            atmospheric_pressure_pa=outdoor_moisture_boundary.atmospheric_pressure_pa,
            dt_minutes=dt_minutes,
        )

        debug_records = self._make_debug_records(
            old_moisture_state=moisture_state,
            moisture_step_result=moisture_step_result,
            moisture_transport_result=moisture_transport_result,
            moisture_source_inputs=moisture_source_inputs,
            thermal_state=thermal_state,
            atmospheric_pressure_pa=outdoor_moisture_boundary.atmospheric_pressure_pa,
            dt_minutes=dt_minutes,
        )

        return MoistureStepResult(
            updated_moisture_state=moisture_step_result.updated_moisture_state,
            moisture_step_result=moisture_step_result,
            moisture_transport_result=moisture_transport_result,
            moisture_source_inputs=moisture_source_inputs,
            outdoor_moisture_boundary=outdoor_moisture_boundary,
            debug_records=debug_records,
            dt_minutes=dt_minutes,
            interface_mode=MOISTURE_MODEL_INTERFACE_MODE,
        )

    def _make_debug_records(
        self,
        old_moisture_state: BuildingMoistureState,
        moisture_step_result: BuildingMoistureStepResult,
        moisture_transport_result: BuildingMoistureTransportResult,
        moisture_source_inputs: BuildingMoistureSourceInputs,
        thermal_state: Any,
        atmospheric_pressure_pa: float,
        dt_minutes: float,
    ) -> List[ZoneMoistureDebugRecord]:
        records = []

        moisture_generation_kg_h_by_zone = (
            moisture_source_inputs.moisture_generation_kg_h_by_zone()
        )

        moisture_generation_kg_s_by_zone = (
            moisture_source_inputs.moisture_generation_kg_s_by_zone()
        )

        transport_airflow_by_zone = (
            moisture_transport_result.total_airflow_m3_s_by_zone()
        )

        transport_mass_flow_by_zone = (
            moisture_transport_result.total_dry_air_mass_flow_kg_s_by_zone()
        )

        for zone_id in moisture_step_result.updated_moisture_state.zone_ids():
            old_state = old_moisture_state.get_zone_state(zone_id)
            new_state = (
                moisture_step_result
                .updated_moisture_state
                .get_zone_state(zone_id)
            )

            zone_result = moisture_step_result.zone_results[zone_id]

            temperature_c = _zone_air_temperature_from_thermal_state(
                thermal_state=thermal_state,
                zone_id=zone_id,
                default_temperature_c=DEFAULT_INITIAL_AIR_TEMPERATURE_C,
            )

            records.append(
                ZoneMoistureDebugRecord(
                    zone_id=zone_id,
                    old_humidity_ratio_kg_kg=old_state.humidity_ratio_kg_kg,
                    new_humidity_ratio_kg_kg=new_state.humidity_ratio_kg_kg,
                    old_relative_humidity_percent=zone_result.old_relative_humidity_percent,
                    new_relative_humidity_percent=new_state.relative_humidity_percent,
                    temperature_c=temperature_c,
                    atmospheric_pressure_pa=atmospheric_pressure_pa,
                    dry_air_mass_kg=zone_result.dry_air_mass_kg,
                    moisture_generation_kg_h=moisture_generation_kg_h_by_zone.get(zone_id, 0.0),
                    moisture_generation_kg_s=moisture_generation_kg_s_by_zone.get(zone_id, 0.0),
                    total_transport_airflow_m3_s=transport_airflow_by_zone.get(zone_id, 0.0),
                    total_transport_dry_air_mass_flow_kg_s=transport_mass_flow_by_zone.get(zone_id, 0.0),
                    dt_minutes=dt_minutes,
                    method=MOISTURE_TIMESTEP_METHOD,
                )
            )

        return records
    

DEFAULT_MOISTURE_COUPLING_RULES = MoistureCouplingRules()
    
DEFAULT_MOISTURE_ARCHITECTURE = MoistureArchitectureDecision()

def make_default_moisture_model() -> MoistureModel:
    return MoistureModel()

def validate_moisture_coupling_inputs(
    moisture_state: BuildingMoistureState,
    thermal_state: Any,
    airflow_network: Any,
) -> None:
    """
    Validate Phase 6 coupling inputs.

    This does not calculate anything.
    It only protects the dependency boundary.
    """

    if not isinstance(moisture_state, BuildingMoistureState):
        raise TypeError("moisture_state must be BuildingMoistureState.")

    if thermal_state is None:
        raise ValueError(
            "thermal_state is required because moisture needs zone air temperature."
        )

    if airflow_network is None:
        raise ValueError(
            "airflow_network is required because moisture transport uses airflow."
        )

    if not hasattr(airflow_network, "outdoor_airflows_by_zone"):
        raise TypeError(
            "airflow_network must provide outdoor_airflows_by_zone."
        )

    if not hasattr(airflow_network, "interzone_airflow_links"):
        raise TypeError(
            "airflow_network must provide interzone_airflow_links."
        )
        
def semi_implicit_humidity_ratio_update(
    dry_air_mass_kg: float,
    old_humidity_ratio_kg_kg: float,
    targets: List[MoistureTransportTarget],
    moisture_generation_kg_s: float,
    dt_seconds: float,
) -> float:
    """
    Stable humidity-ratio mass-balance update.

    Formula:

        w_next =
            (M_air/dt * w_old + sum(m_dot_i * w_i) + G)
            /
            (M_air/dt + sum(m_dot_i))

    Units:
        w     = kg_water/kg_dry_air
        M_air = kg_dry_air
        m_dot = kg_dry_air/s
        G     = kg_water/s
        dt    = s
    """

    dry_air_mass_kg = _positive_float(
        dry_air_mass_kg,
        "dry_air_mass_kg",
        "semi_implicit_humidity_ratio_update",
    )

    old_humidity_ratio_kg_kg = clamp_humidity_ratio(
        old_humidity_ratio_kg_kg
    )

    moisture_generation_kg_s = _non_negative_float(
        moisture_generation_kg_s,
        "moisture_generation_kg_s",
        "semi_implicit_humidity_ratio_update",
    )

    dt_seconds = _positive_float(
        dt_seconds,
        "dt_seconds",
        "semi_implicit_humidity_ratio_update",
    )

    if targets is None:
        targets = []

    mass_over_dt = dry_air_mass_kg / dt_seconds

    numerator = (
        mass_over_dt * old_humidity_ratio_kg_kg
        + moisture_generation_kg_s
    )

    denominator = mass_over_dt

    for target in targets:
        if not isinstance(target, MoistureTransportTarget):
            raise TypeError(
                "targets must contain MoistureTransportTarget objects."
            )

        numerator += (
            target.dry_air_mass_flow_kg_s
            * target.humidity_ratio_kg_kg
        )

        denominator += target.dry_air_mass_flow_kg_s

    if denominator <= 0.0:
        raise ValueError(
            "Humidity-ratio update denominator became non-positive."
        )

    return clamp_humidity_ratio(numerator / denominator)

def update_zone_moisture_state(
    zone_moisture_state: ZoneMoistureState,
    zone_moisture_parameters: ZoneMoistureParameters,
    transport_targets: List[MoistureTransportTarget],
    moisture_generation_kg_s: float,
    temperature_c: float,
    atmospheric_pressure_pa: float = DEFAULT_ATMOSPHERIC_PRESSURE_PA,
    dt_minutes: float = DEFAULT_MOISTURE_DT_MINUTES,
) -> ZoneMoistureUpdateResult:
    """
    Update moisture state for one zone.

    Includes:
    - moisture storage in dry air
    - internal moisture generation
    - outdoor transport
    - interzone transport

    Relative humidity is derived after the humidity-ratio update.
    """

    if not isinstance(zone_moisture_state, ZoneMoistureState):
        raise TypeError("zone_moisture_state must be ZoneMoistureState.")

    if not isinstance(zone_moisture_parameters, ZoneMoistureParameters):
        raise TypeError(
            "zone_moisture_parameters must be ZoneMoistureParameters."
        )

    if zone_moisture_state.zone_id != zone_moisture_parameters.zone_id:
        raise ValueError(
            "zone_moisture_state.zone_id does not match "
            "zone_moisture_parameters.zone_id."
        )

    moisture_generation_kg_s = _non_negative_float(
        moisture_generation_kg_s,
        "moisture_generation_kg_s",
        zone_moisture_state.zone_id,
    )

    atmospheric_pressure_pa = clamp_atmospheric_pressure_pa(
        atmospheric_pressure_pa
    )

    dt_seconds = _positive_float(
        float(dt_minutes) * 60.0,
        "dt_seconds",
        zone_moisture_state.zone_id,
    )

    if transport_targets is None:
        transport_targets = []

    new_humidity_ratio_kg_kg = semi_implicit_humidity_ratio_update(
        dry_air_mass_kg=zone_moisture_parameters.dry_air_mass_kg,
        old_humidity_ratio_kg_kg=zone_moisture_state.humidity_ratio_kg_kg,
        targets=transport_targets,
        moisture_generation_kg_s=moisture_generation_kg_s,
        dt_seconds=dt_seconds,
    )

    new_relative_humidity_percent = relative_humidity_from_humidity_ratio(
        humidity_ratio_kg_kg=new_humidity_ratio_kg_kg,
        temperature_c=temperature_c,
        atmospheric_pressure_pa=atmospheric_pressure_pa,
    )

    old_relative_humidity_percent = relative_humidity_from_humidity_ratio(
        humidity_ratio_kg_kg=zone_moisture_state.humidity_ratio_kg_kg,
        temperature_c=temperature_c,
        atmospheric_pressure_pa=atmospheric_pressure_pa,
    )

    return ZoneMoistureUpdateResult(
        zone_id=zone_moisture_state.zone_id,
        old_humidity_ratio_kg_kg=zone_moisture_state.humidity_ratio_kg_kg,
        new_humidity_ratio_kg_kg=new_humidity_ratio_kg_kg,
        old_relative_humidity_percent=old_relative_humidity_percent,
        new_relative_humidity_percent=new_relative_humidity_percent,
        dry_air_mass_kg=zone_moisture_parameters.dry_air_mass_kg,
        moisture_generation_kg_s=moisture_generation_kg_s,
        temperature_c=temperature_c,
        atmospheric_pressure_pa=atmospheric_pressure_pa,
        targets=transport_targets,
        dt_seconds=dt_seconds,
        method=MOISTURE_TIMESTEP_METHOD,
    )

def step_building_moisture_state(
    moisture_state: BuildingMoistureState,
    building_moisture_parameters: BuildingMoistureParameters,
    moisture_transport_result: BuildingMoistureTransportResult,
    moisture_source_inputs: BuildingMoistureSourceInputs,
    thermal_state: Any = None,
    atmospheric_pressure_pa: float = DEFAULT_ATMOSPHERIC_PRESSURE_PA,
    dt_minutes: float = DEFAULT_MOISTURE_DT_MINUTES,
) -> BuildingMoistureStepResult:
    """
    Update moisture state for all zones.

    Inputs:
    - existing BuildingMoistureState
    - BuildingMoistureParameters
    - BuildingMoistureTransportResult from Phase 6.8
    - BuildingMoistureSourceInputs from Phase 6.5 / 6.6
    - thermal_state for zone air temperature, if available

    This function does not calculate airflow.
    """

    if not isinstance(moisture_state, BuildingMoistureState):
        raise TypeError("moisture_state must be BuildingMoistureState.")

    if not isinstance(building_moisture_parameters, BuildingMoistureParameters):
        raise TypeError(
            "building_moisture_parameters must be BuildingMoistureParameters."
        )

    if not isinstance(moisture_transport_result, BuildingMoistureTransportResult):
        raise TypeError(
            "moisture_transport_result must be BuildingMoistureTransportResult."
        )

    if not isinstance(moisture_source_inputs, BuildingMoistureSourceInputs):
        raise TypeError(
            "moisture_source_inputs must be BuildingMoistureSourceInputs."
        )

    atmospheric_pressure_pa = clamp_atmospheric_pressure_pa(
        atmospheric_pressure_pa
    )

    updated_zone_states = {}
    zone_results = {}

    for zone_id in moisture_state.zone_ids():
        zone_state = moisture_state.get_zone_state(zone_id)

        zone_parameters = building_moisture_parameters.get_zone_parameters(
            zone_id
        )

        transport_targets = (
            moisture_transport_result
            .get_targets_for_zone(zone_id)
            .targets
        )

        moisture_generation_kg_s = _moisture_generation_kg_s_for_zone(
            moisture_source_inputs=moisture_source_inputs,
            zone_id=zone_id,
        )

        temperature_c = _zone_air_temperature_from_thermal_state(
            thermal_state=thermal_state,
            zone_id=zone_id,
            default_temperature_c=DEFAULT_INITIAL_AIR_TEMPERATURE_C,
        )

        result = update_zone_moisture_state(
            zone_moisture_state=zone_state,
            zone_moisture_parameters=zone_parameters,
            transport_targets=transport_targets,
            moisture_generation_kg_s=moisture_generation_kg_s,
            temperature_c=temperature_c,
            atmospheric_pressure_pa=atmospheric_pressure_pa,
            dt_minutes=dt_minutes,
        )

        updated_zone_states[zone_id] = result.to_zone_moisture_state()
        zone_results[zone_id] = result

    updated_moisture_state = BuildingMoistureState(
        zone_states=updated_zone_states,
    )

    return BuildingMoistureStepResult(
        updated_moisture_state=updated_moisture_state,
        zone_results=zone_results,
        dt_minutes=dt_minutes,
        method=MOISTURE_TIMESTEP_METHOD,
    )

def make_outdoor_moisture_transport_target(
    zone_id: str,
    outdoor_airflow_record: Any,
    outdoor_moisture_boundary: OutdoorMoistureBoundary,
) -> MoistureTransportTarget:
    """
    Outdoor air exchange transports outdoor humidity ratio into the zone.
    """

    if not zone_id:
        raise ValueError("zone_id cannot be empty.")

    if not isinstance(outdoor_moisture_boundary, OutdoorMoistureBoundary):
        raise TypeError(
            "outdoor_moisture_boundary must be OutdoorMoistureBoundary."
        )

    if outdoor_airflow_record is None:
        airflow_m3_s = 0.0
    elif hasattr(outdoor_airflow_record, "mixing_exchange_m3_s"):
        airflow_m3_s = outdoor_airflow_record.mixing_exchange_m3_s()
    else:
        airflow_m3_h = _get_attr_or_default(
            outdoor_airflow_record,
            "mixing_exchange_m3_h",
            0.0,
        )
        airflow_m3_s = float(airflow_m3_h) / 3600.0

    return MoistureTransportTarget(
        target_id=zone_id + "__outdoor",
        target_type=MOISTURE_TRANSPORT_TARGET_OUTDOOR,
        humidity_ratio_kg_kg=outdoor_moisture_boundary.outdoor_humidity_ratio_kg_kg,
        airflow_m3_s=airflow_m3_s,
        source_zone_id="outdoor",
        source=MOISTURE_TRANSPORT_SOURCE_OUTDOOR,
    )


def make_interzone_moisture_transport_targets_for_zone(
    zone_id: str,
    moisture_state: BuildingMoistureState,
    airflow_network: Any,
) -> List[MoistureTransportTarget]:
    """
    Interzone mixing transports adjacent zone humidity ratio.

    Uses old/current BuildingMoistureState values.
    """

    if not zone_id:
        raise ValueError("zone_id cannot be empty.")

    if not isinstance(moisture_state, BuildingMoistureState):
        raise TypeError("moisture_state must be BuildingMoistureState.")

    if airflow_network is None:
        raise ValueError("airflow_network cannot be None.")

    targets = []

    if hasattr(airflow_network, "interzone_links_for_zone"):
        interzone_links = airflow_network.interzone_links_for_zone(zone_id)
    else:
        interzone_links = []

        links = _get_attr_or_default(
            airflow_network,
            "interzone_airflow_links",
            {},
        )

        for link in links.values():
            if (
                _get_attr_or_default(link, "zone_a_id", "") == zone_id
                or _get_attr_or_default(link, "zone_b_id", "") == zone_id
            ):
                interzone_links.append(link)

    for link in interzone_links:
        adjacent_zone_id = _interzone_link_other_zone_id(
            link=link,
            zone_id=zone_id,
        )

        if not moisture_state.has_zone(adjacent_zone_id):
            continue

        adjacent_state = moisture_state.get_zone_state(adjacent_zone_id)

        if hasattr(link, "mixing_flow_m3_s"):
            airflow_m3_s = link.mixing_flow_m3_s()
        else:
            airflow_m3_h = _get_attr_or_default(
                link,
                "mixing_flow_m3_h",
                0.0,
            )
            airflow_m3_s = float(airflow_m3_h) / 3600.0

        targets.append(
            MoistureTransportTarget(
                target_id=str(_get_attr_or_default(link, "link_id", "link"))
                + "__"
                + adjacent_zone_id,
                target_type=MOISTURE_TRANSPORT_TARGET_INTERZONE,
                humidity_ratio_kg_kg=adjacent_state.humidity_ratio_kg_kg,
                airflow_m3_s=airflow_m3_s,
                source_zone_id=adjacent_zone_id,
                source=MOISTURE_TRANSPORT_SOURCE_INTERZONE,
            )
        )

    return targets

def moisture_transport_targets_for_zone(
    moisture_transport_result: BuildingMoistureTransportResult,
    zone_id: str,
) -> List[MoistureTransportTarget]:
    if not isinstance(moisture_transport_result, BuildingMoistureTransportResult):
        raise TypeError(
            "moisture_transport_result must be BuildingMoistureTransportResult."
        )

    return moisture_transport_result.get_targets_for_zone(zone_id).targets


def dry_air_mass_flow_kg_s_by_zone(
    moisture_transport_result: BuildingMoistureTransportResult,
) -> Dict[str, float]:
    if not isinstance(moisture_transport_result, BuildingMoistureTransportResult):
        raise TypeError(
            "moisture_transport_result must be BuildingMoistureTransportResult."
        )

    return moisture_transport_result.total_dry_air_mass_flow_kg_s_by_zone()


def make_zone_moisture_transport_targets(
    zone_id: str,
    moisture_state: BuildingMoistureState,
    airflow_network: Any,
    outdoor_moisture_boundary: OutdoorMoistureBoundary,
) -> ZoneMoistureTransportTargets:
    """
    Assemble outdoor + interzone moisture transport targets for one zone.
    """

    if not zone_id:
        raise ValueError("zone_id cannot be empty.")

    targets = []

    outdoor_airflows_by_zone = _get_attr_or_default(
        airflow_network,
        "outdoor_airflows_by_zone",
        {},
    )

    outdoor_airflow_record = outdoor_airflows_by_zone.get(zone_id)

    targets.append(
        make_outdoor_moisture_transport_target(
            zone_id=zone_id,
            outdoor_airflow_record=outdoor_airflow_record,
            outdoor_moisture_boundary=outdoor_moisture_boundary,
        )
    )

    targets.extend(
        make_interzone_moisture_transport_targets_for_zone(
            zone_id=zone_id,
            moisture_state=moisture_state,
            airflow_network=airflow_network,
        )
    )

    return ZoneMoistureTransportTargets(
        zone_id=zone_id,
        targets=targets,
    )


def make_building_moisture_transport_result(
    moisture_state: BuildingMoistureState,
    airflow_network: Any,
    outdoor_moisture_boundary: OutdoorMoistureBoundary,
) -> BuildingMoistureTransportResult:
    """
    Assemble moisture transport through already-calculated airflow network.

    Important:
        This function does not calculate airflow.
        It only reads BuildingAirflowNetwork.
    """

    if not isinstance(moisture_state, BuildingMoistureState):
        raise TypeError("moisture_state must be BuildingMoistureState.")

    if airflow_network is None:
        raise ValueError("airflow_network cannot be None.")

    if not isinstance(outdoor_moisture_boundary, OutdoorMoistureBoundary):
        raise TypeError(
            "outdoor_moisture_boundary must be OutdoorMoistureBoundary."
        )

    zone_targets = {}

    for zone_id in moisture_state.zone_ids():
        zone_targets[zone_id] = make_zone_moisture_transport_targets(
            zone_id=zone_id,
            moisture_state=moisture_state,
            airflow_network=airflow_network,
            outdoor_moisture_boundary=outdoor_moisture_boundary,
        )

    return BuildingMoistureTransportResult(
        zone_targets=zone_targets,
    )

def make_outdoor_moisture_boundary_from_weather_state(
    weather_state: Any,
) -> OutdoorMoistureBoundary:
    """
    Build outdoor moisture boundary from WeatherState.

    Inputs:
    - WeatherState.relative_humidity_percent
    - WeatherState.outdoor_temperature_c
    - WeatherState.atmospheric_pressure_pa

    Fallbacks:
    - RH = 50%
    - pressure = 101325 Pa
    - outdoor temperature = 20 C if missing
    """

    if weather_state is None:
        raise ValueError("weather_state cannot be None.")

    outdoor_relative_humidity_percent = _get_attr_or_default(
        weather_state,
        "relative_humidity_percent",
        DEFAULT_OUTDOOR_RELATIVE_HUMIDITY_PERCENT,
    )

    outdoor_temperature_c = _get_attr_or_default(
        weather_state,
        "outdoor_temperature_c",
        DEFAULT_OUTDOOR_TEMPERATURE_C,
    )

    atmospheric_pressure_pa = _get_attr_or_default(
        weather_state,
        "atmospheric_pressure_pa",
        DEFAULT_ATMOSPHERIC_PRESSURE_PA,
    )

    outdoor_relative_humidity_percent = clamp_relative_humidity(
        outdoor_relative_humidity_percent
    )

    atmospheric_pressure_pa = clamp_atmospheric_pressure_pa(
        atmospheric_pressure_pa
    )

    outdoor_humidity_ratio_kg_kg = humidity_ratio_from_rh(
        relative_humidity_percent=outdoor_relative_humidity_percent,
        temperature_c=outdoor_temperature_c,
        atmospheric_pressure_pa=atmospheric_pressure_pa,
    )

    return OutdoorMoistureBoundary(
        outdoor_humidity_ratio_kg_kg=outdoor_humidity_ratio_kg_kg,
        outdoor_relative_humidity_percent=outdoor_relative_humidity_percent,
        outdoor_temperature_c=outdoor_temperature_c,
        atmospheric_pressure_pa=atmospheric_pressure_pa,
        source=OUTDOOR_MOISTURE_BOUNDARY_SOURCE,
    )

def calculate_people_moisture_generation_record(
    occupancy_input: Any,
    moisture_generation_per_person_kg_h: float = DEFAULT_MOISTURE_GENERATION_PER_PERSON_KG_H,
) -> MoistureGenerationRecord:
    """
    Calculate people moisture generation for one zone.

    Expected occupancy_input:
        ZoneOccupancyInput-like object with:
        - zone_id
        - number_of_people
    """

    if occupancy_input is None:
        raise ValueError("occupancy_input cannot be None.")

    zone_id = _required_attr(
        occupancy_input,
        "zone_id",
    )

    number_of_people = _get_attr_or_default(
        occupancy_input,
        "number_of_people",
        0.0,
    )

    return MoistureGenerationRecord(
        zone_id=zone_id,
        number_of_people=number_of_people,
        moisture_generation_per_person_kg_h=moisture_generation_per_person_kg_h,
        source_type=MOISTURE_SOURCE_PEOPLE,
        source=MOISTURE_GENERATION_SOURCE_PEOPLE,
    )


def calculate_building_people_moisture_generation(
    building_moisture_parameters: BuildingMoistureParameters,
    airflow_control_inputs: Any,
    moisture_generation_per_person_kg_h: float = DEFAULT_MOISTURE_GENERATION_PER_PERSON_KG_H,
) -> BuildingMoistureGenerationResult:
    """
    Calculate people moisture generation for all zones.

    Inputs:
    - BuildingMoistureParameters for zone list
    - BuildingAirflowControlInputs-like object for occupancy

    The function does not import airflow.py.
    It only expects airflow_control_inputs to provide:
        get_occupancy_for_zone(zone_id)
    """

    if not isinstance(building_moisture_parameters, BuildingMoistureParameters):
        raise TypeError(
            "building_moisture_parameters must be BuildingMoistureParameters."
        )

    if airflow_control_inputs is None:
        raise ValueError("airflow_control_inputs cannot be None.")

    if not hasattr(airflow_control_inputs, "get_occupancy_for_zone"):
        raise TypeError(
            "airflow_control_inputs must provide get_occupancy_for_zone(zone_id)."
        )

    zone_records = {}

    for zone_id in building_moisture_parameters.zone_ids():
        occupancy_input = airflow_control_inputs.get_occupancy_for_zone(
            zone_id
        )

        zone_records[zone_id] = calculate_people_moisture_generation_record(
            occupancy_input=occupancy_input,
            moisture_generation_per_person_kg_h=moisture_generation_per_person_kg_h,
        )

    return BuildingMoistureGenerationResult(
        zone_records=zone_records,
    )


def calculate_building_people_moisture_generation_from_model(
    building_model: Any,
    airflow_control_inputs: Any,
    moisture_generation_per_person_kg_h: float = DEFAULT_MOISTURE_GENERATION_PER_PERSON_KG_H,
) -> BuildingMoistureGenerationResult:
    """
    Convenience function.

    Builds moisture parameters from BuildingModel, then calculates people
    moisture generation from occupancy inputs.
    """

    building_moisture_parameters = make_building_moisture_parameters(
        building_model
    )

    return calculate_building_people_moisture_generation(
        building_moisture_parameters=building_moisture_parameters,
        airflow_control_inputs=airflow_control_inputs,
        moisture_generation_per_person_kg_h=moisture_generation_per_person_kg_h,
    )


def people_moisture_generation_kg_h_by_zone(
    moisture_generation_result: BuildingMoistureGenerationResult,
) -> Dict[str, float]:
    if not isinstance(moisture_generation_result, BuildingMoistureGenerationResult):
        raise TypeError(
            "moisture_generation_result must be BuildingMoistureGenerationResult."
        )

    return moisture_generation_result.moisture_generation_kg_h_by_zone()


def people_moisture_generation_kg_s_by_zone(
    moisture_generation_result: BuildingMoistureGenerationResult,
) -> Dict[str, float]:
    if not isinstance(moisture_generation_result, BuildingMoistureGenerationResult):
        raise TypeError(
            "moisture_generation_result must be BuildingMoistureGenerationResult."
        )

    return moisture_generation_result.moisture_generation_kg_s_by_zone()

def make_empty_moisture_source_inputs() -> BuildingMoistureSourceInputs:
    return BuildingMoistureSourceInputs(
        sources_by_zone={},
    )


def make_moisture_source_inputs(
    moisture_generation_kg_h_by_zone: Dict[str, float] = None,
    source_type: str = MOISTURE_SOURCE_GENERIC,
) -> BuildingMoistureSourceInputs:
    """
    Convenience builder for simple source maps.

    Example:
        {"kitchen": 0.20, "bathroom": 0.50}
    """

    if moisture_generation_kg_h_by_zone is None:
        moisture_generation_kg_h_by_zone = {}

    sources_by_zone = {}

    for zone_id, moisture_generation_kg_h in moisture_generation_kg_h_by_zone.items():
        sources_by_zone[zone_id] = [
            ZoneMoistureSourceInput(
                zone_id=zone_id,
                moisture_generation_kg_h=moisture_generation_kg_h,
                source_type=source_type,
            )
        ]

    return BuildingMoistureSourceInputs(
        sources_by_zone=sources_by_zone,
    )


def moisture_generation_kg_h_by_zone(
    moisture_source_inputs: BuildingMoistureSourceInputs,
) -> Dict[str, float]:
    if not isinstance(moisture_source_inputs, BuildingMoistureSourceInputs):
        raise TypeError(
            "moisture_source_inputs must be BuildingMoistureSourceInputs."
        )

    return moisture_source_inputs.moisture_generation_kg_h_by_zone()


def moisture_generation_kg_s_by_zone(
    moisture_source_inputs: BuildingMoistureSourceInputs,
) -> Dict[str, float]:
    if not isinstance(moisture_source_inputs, BuildingMoistureSourceInputs):
        raise TypeError(
            "moisture_source_inputs must be BuildingMoistureSourceInputs."
        )

    return moisture_source_inputs.moisture_generation_kg_s_by_zone()

def make_zone_moisture_parameters_from_zone_model(
    zone_model: Any,
) -> ZoneMoistureParameters:
    """
    Build ZoneMoistureParameters from ZoneModel.

    Source priority for air volume:
    - ZoneModel.air_volume_m3
    - ZoneModel.volume_m3
    - ZoneModel.floor_area_m2 * ZoneModel.height_m
    - default fallback

    Source priority for initial RH:
    - ZoneModel.initial_relative_humidity_percent
    - ZoneModel.relative_humidity_percent
    - ZoneModel.initial_rh_percent
    - default 50%
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

    if air_volume_m3 is None:
        air_volume_m3 = DEFAULT_ZONE_AIR_VOLUME_M3

    air_volume_m3 = _positive_float(
        air_volume_m3,
        "air_volume_m3",
        zone_id,
    )

    dry_air_mass_kg = MOISTURE_AIR_DENSITY_KG_M3 * air_volume_m3

    initial_relative_humidity_percent = _first_existing_attr_or_default(
        zone_model,
        [
            "initial_relative_humidity_percent",
            "relative_humidity_percent",
            "initial_rh_percent",
        ],
        DEFAULT_INITIAL_RELATIVE_HUMIDITY_PERCENT,
    )

    moisture_buffering_enabled = _get_attr_or_default(
        zone_model,
        "moisture_buffering_enabled",
        DEFAULT_MOISTURE_BUFFERING_ENABLED,
    )

    return ZoneMoistureParameters(
        zone_id=zone_id,
        air_volume_m3=air_volume_m3,
        dry_air_mass_kg=dry_air_mass_kg,
        initial_relative_humidity_percent=initial_relative_humidity_percent,
        moisture_buffering_enabled=moisture_buffering_enabled,
        source="ZoneModel",
    )

def outdoor_humidity_ratio_from_weather_state(
    weather_state: Any,
) -> float:
    """
    Convenience helper.

    Returns outdoor humidity ratio [kg_water/kg_dry_air].
    """

    boundary = make_outdoor_moisture_boundary_from_weather_state(
        weather_state
    )

    return boundary.outdoor_humidity_ratio_kg_kg


def outdoor_relative_humidity_from_weather_state(
    weather_state: Any,
) -> float:
    """
    Convenience helper.

    Returns outdoor RH [%].
    """

    boundary = make_outdoor_moisture_boundary_from_weather_state(
        weather_state
    )

    return boundary.outdoor_relative_humidity_percent

def make_building_moisture_parameters(
    building_model: Any,
) -> BuildingMoistureParameters:
    """
    Build BuildingMoistureParameters from BuildingModel.
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
        zone_parameters[zone_id] = make_zone_moisture_parameters_from_zone_model(
            zone_model
        )

    return BuildingMoistureParameters(
        zone_parameters=zone_parameters,
    )

def make_initial_zone_moisture_state_from_zone_model(
    zone_model: Any,
    temperature_c: Any = None,
    atmospheric_pressure_pa: float = DEFAULT_ATMOSPHERIC_PRESSURE_PA,
) -> ZoneMoistureState:
    """
    Create initial ZoneMoistureState from ZoneModel.

    Initial RH source priority:
    - ZoneModel.initial_relative_humidity_percent
    - ZoneModel.relative_humidity_percent
    - ZoneModel.initial_rh_percent
    - default 50%

    Temperature is needed because RH -> humidity ratio depends on temperature.
    """

    if zone_model is None:
        raise ValueError("zone_model cannot be None.")

    zone_id = _required_attr(zone_model, "zone_id")

    initial_rh_percent = _first_existing_attr_or_default(
        zone_model,
        [
            "initial_relative_humidity_percent",
            "relative_humidity_percent",
            "initial_rh_percent",
        ],
        DEFAULT_INITIAL_RELATIVE_HUMIDITY_PERCENT,
    )

    if temperature_c is None:
        temperature_c = _first_existing_attr_or_default(
            zone_model,
            [
                "initial_air_temperature_c",
                "initial_temp_c",
            ],
            DEFAULT_INITIAL_AIR_TEMPERATURE_C,
        )

    humidity_ratio_kg_kg = humidity_ratio_from_relative_humidity_percent(
        relative_humidity_percent=initial_rh_percent,
        temperature_c=temperature_c,
        atmospheric_pressure_pa=atmospheric_pressure_pa,
    )

    derived_rh_percent = relative_humidity_percent_from_humidity_ratio(
        humidity_ratio_kg_kg=humidity_ratio_kg_kg,
        temperature_c=temperature_c,
        atmospheric_pressure_pa=atmospheric_pressure_pa,
    )

    return ZoneMoistureState(
        zone_id=zone_id,
        humidity_ratio_kg_kg=humidity_ratio_kg_kg,
        relative_humidity_percent=derived_rh_percent,
    )


def make_initial_building_moisture_state(
    building_model: Any,
    thermal_state: Any = None,
    atmospheric_pressure_pa: float = DEFAULT_ATMOSPHERIC_PRESSURE_PA,
) -> BuildingMoistureState:
    """
    Create initial BuildingMoistureState from BuildingModel / ZoneModel.

    If thermal_state is provided, zone air temperatures are read from it.
    Otherwise, initial temperatures are read from ZoneModel.
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
        temperature_c = None

        if thermal_state is not None and hasattr(thermal_state, "has_zone"):
            if thermal_state.has_zone(zone_id):
                thermal_zone_state = thermal_state.get_zone_state(zone_id)
                temperature_c = _get_attr_or_default(
                    thermal_zone_state,
                    "air_temperature_c",
                    None,
                )

        zone_states[zone_id] = make_initial_zone_moisture_state_from_zone_model(
            zone_model=zone_model,
            temperature_c=temperature_c,
            atmospheric_pressure_pa=atmospheric_pressure_pa,
        )

    return BuildingMoistureState(
        zone_states=zone_states,
    )

def dry_air_mass_by_zone_kg(
    building_moisture_parameters: BuildingMoistureParameters,
) -> Dict[str, float]:
    if not isinstance(building_moisture_parameters, BuildingMoistureParameters):
        raise TypeError(
            "building_moisture_parameters must be BuildingMoistureParameters."
        )

    return building_moisture_parameters.dry_air_mass_by_zone_kg()

def saturation_vapor_pressure_pa(
    temperature_c: float,
) -> float:
    """
    Saturation vapor pressure over liquid water [Pa].

    Uses a Tetens/Magnus-type approximation.

    Input:
        temperature_c [degC]

    Output:
        saturation vapor pressure [Pa]
    """

    temperature_c = float(temperature_c)

    denominator = temperature_c + 243.04

    if abs(denominator) < 1e-9:
        denominator = 1e-9

    saturation_pressure_pa = 610.94 * math.exp(
        (17.625 * temperature_c) / denominator
    )

    return _positive_float(
        saturation_pressure_pa,
        "saturation_vapor_pressure_pa",
        "saturation_vapor_pressure_pa",
    )


def vapor_pressure_from_humidity_ratio(
    humidity_ratio_kg_kg: float,
    atmospheric_pressure_pa: float = DEFAULT_ATMOSPHERIC_PRESSURE_PA,
) -> float:
    """
    Convert humidity ratio to water vapor partial pressure.

    Inputs:
        humidity_ratio_kg_kg [kg_water/kg_dry_air]
        atmospheric_pressure_pa [Pa]

    Output:
        vapor pressure [Pa]
    """

    humidity_ratio_kg_kg = clamp_humidity_ratio(
        humidity_ratio_kg_kg
    )

    atmospheric_pressure_pa = clamp_atmospheric_pressure_pa(
        atmospheric_pressure_pa
    )

    vapor_pressure_pa = (
        atmospheric_pressure_pa
        * humidity_ratio_kg_kg
        / (MOISTURE_MOLECULAR_WEIGHT_RATIO + humidity_ratio_kg_kg)
    )

    if vapor_pressure_pa < 0.0:
        return 0.0

    max_vapor_pressure_pa = 0.99 * atmospheric_pressure_pa

    if vapor_pressure_pa > max_vapor_pressure_pa:
        return max_vapor_pressure_pa

    return vapor_pressure_pa


def humidity_ratio_from_vapor_pressure(
    vapor_pressure_pa: float,
    atmospheric_pressure_pa: float = DEFAULT_ATMOSPHERIC_PRESSURE_PA,
) -> float:
    """
    Convert water vapor partial pressure to humidity ratio.

    Inputs:
        vapor_pressure_pa [Pa]
        atmospheric_pressure_pa [Pa]

    Output:
        humidity ratio [kg_water/kg_dry_air]
    """

    atmospheric_pressure_pa = clamp_atmospheric_pressure_pa(
        atmospheric_pressure_pa
    )

    vapor_pressure_pa = _non_negative_float(
        vapor_pressure_pa,
        "vapor_pressure_pa",
        "humidity_ratio_from_vapor_pressure",
    )

    max_vapor_pressure_pa = 0.99 * atmospheric_pressure_pa

    if vapor_pressure_pa > max_vapor_pressure_pa:
        vapor_pressure_pa = max_vapor_pressure_pa

    denominator = atmospheric_pressure_pa - vapor_pressure_pa

    if denominator <= 0.0:
        denominator = 1e-9

    humidity_ratio_kg_kg = (
        MOISTURE_MOLECULAR_WEIGHT_RATIO
        * vapor_pressure_pa
        / denominator
    )

    return clamp_humidity_ratio(humidity_ratio_kg_kg)


def humidity_ratio_from_rh(
    relative_humidity_percent: float,
    temperature_c: float,
    atmospheric_pressure_pa: float = DEFAULT_ATMOSPHERIC_PRESSURE_PA,
) -> float:
    """
    Convert relative humidity to humidity ratio.

    Inputs:
        relative_humidity_percent [%]
        temperature_c [degC]
        atmospheric_pressure_pa [Pa]

    Output:
        humidity ratio [kg_water/kg_dry_air]

    Important:
        RH is not conserved.
        Humidity ratio is the transported state.
    """

    relative_humidity_percent = clamp_relative_humidity(
        relative_humidity_percent
    )

    atmospheric_pressure_pa = clamp_atmospheric_pressure_pa(
        atmospheric_pressure_pa
    )

    saturation_pressure_pa = saturation_vapor_pressure_pa(
        temperature_c
    )

    vapor_pressure_pa = (
        relative_humidity_percent
        / 100.0
        * saturation_pressure_pa
    )

    return humidity_ratio_from_vapor_pressure(
        vapor_pressure_pa=vapor_pressure_pa,
        atmospheric_pressure_pa=atmospheric_pressure_pa,
    )
def humidity_ratio_by_zone_after_step(
    moisture_step_result: BuildingMoistureStepResult,
) -> Dict[str, float]:
    if not isinstance(moisture_step_result, BuildingMoistureStepResult):
        raise TypeError(
            "moisture_step_result must be BuildingMoistureStepResult."
        )

    return moisture_step_result.humidity_ratio_by_zone_kg_kg()


def relative_humidity_by_zone_after_step(
    moisture_step_result: BuildingMoistureStepResult,
) -> Dict[str, float]:
    if not isinstance(moisture_step_result, BuildingMoistureStepResult):
        raise TypeError(
            "moisture_step_result must be BuildingMoistureStepResult."
        )

    return moisture_step_result.relative_humidity_by_zone_percent()

def relative_humidity_from_humidity_ratio(
    humidity_ratio_kg_kg: float,
    temperature_c: float,
    atmospheric_pressure_pa: float = DEFAULT_ATMOSPHERIC_PRESSURE_PA,
) -> float:
    """
    Convert humidity ratio to relative humidity.

    Inputs:
        humidity_ratio_kg_kg [kg_water/kg_dry_air]
        temperature_c [degC]
        atmospheric_pressure_pa [Pa]

    Output:
        relative humidity [%]

    Important:
        Relative humidity is derived from humidity ratio, temperature, and pressure.
    """

    humidity_ratio_kg_kg = clamp_humidity_ratio(
        humidity_ratio_kg_kg
    )

    atmospheric_pressure_pa = clamp_atmospheric_pressure_pa(
        atmospheric_pressure_pa
    )

    vapor_pressure_pa = vapor_pressure_from_humidity_ratio(
        humidity_ratio_kg_kg=humidity_ratio_kg_kg,
        atmospheric_pressure_pa=atmospheric_pressure_pa,
    )

    saturation_pressure_pa = saturation_vapor_pressure_pa(
        temperature_c
    )

    if saturation_pressure_pa <= 0.0:
        return MIN_RELATIVE_HUMIDITY_PERCENT

    relative_humidity_percent = (
        100.0
        * vapor_pressure_pa
        / saturation_pressure_pa
    )

    return clamp_relative_humidity(relative_humidity_percent)

def humidity_ratio_from_relative_humidity_percent(
    relative_humidity_percent: float,
    temperature_c: float,
    atmospheric_pressure_pa: float = DEFAULT_ATMOSPHERIC_PRESSURE_PA,
) -> float:
    """
    Backward-compatible wrapper.
    Prefer humidity_ratio_from_rh(...) in new code.
    """

    return humidity_ratio_from_rh(
        relative_humidity_percent=relative_humidity_percent,
        temperature_c=temperature_c,
        atmospheric_pressure_pa=atmospheric_pressure_pa,
    )


def relative_humidity_percent_from_humidity_ratio(
    humidity_ratio_kg_kg: float,
    temperature_c: float,
    atmospheric_pressure_pa: float = DEFAULT_ATMOSPHERIC_PRESSURE_PA,
) -> float:
    """
    Backward-compatible wrapper.
    Prefer relative_humidity_from_humidity_ratio(...) in new code.
    """

    return relative_humidity_from_humidity_ratio(
        humidity_ratio_kg_kg=humidity_ratio_kg_kg,
        temperature_c=temperature_c,
        atmospheric_pressure_pa=atmospheric_pressure_pa,
    )


def _clamp_relative_humidity_percent(
    relative_humidity_percent: float,
) -> float:
    """
    Backward-compatible internal wrapper.
    """

    return clamp_relative_humidity(relative_humidity_percent)

def clamp_relative_humidity(
    relative_humidity_percent: float,
) -> float:
    """
    Clamp relative humidity to the Phase 6 output range.
    """

    relative_humidity_percent = float(relative_humidity_percent)

    if relative_humidity_percent < MIN_RELATIVE_HUMIDITY_PERCENT:
        return MIN_RELATIVE_HUMIDITY_PERCENT

    if relative_humidity_percent > MAX_RELATIVE_HUMIDITY_PERCENT:
        return MAX_RELATIVE_HUMIDITY_PERCENT

    return relative_humidity_percent

def _moisture_generation_kg_s_for_zone(
    moisture_source_inputs: BuildingMoistureSourceInputs,
    zone_id: str,
) -> float:
    sources = moisture_source_inputs.get_sources_for_zone(zone_id)

    return sum(
        source.moisture_generation_kg_s()
        for source in sources
    )


def _zone_air_temperature_from_thermal_state(
    thermal_state: Any,
    zone_id: str,
    default_temperature_c: float = DEFAULT_INITIAL_AIR_TEMPERATURE_C,
) -> float:
    """
    Compatibility helper.

    Reads zone air temperature from BuildingThermalState-like object.

    No import from thermal.py.
    """

    if thermal_state is None:
        return float(default_temperature_c)

    if hasattr(thermal_state, "has_zone") and hasattr(thermal_state, "get_zone_state"):
        if thermal_state.has_zone(zone_id):
            zone_thermal_state = thermal_state.get_zone_state(zone_id)

            temperature_c = _get_attr_or_default(
                zone_thermal_state,
                "air_temperature_c",
                default_temperature_c,
            )

            return float(temperature_c)

    if hasattr(thermal_state, "zone_states"):
        zone_states = _get_attr_or_default(
            thermal_state,
            "zone_states",
            {},
        )

        if zone_id in zone_states:
            zone_thermal_state = zone_states[zone_id]

            temperature_c = _get_attr_or_default(
                zone_thermal_state,
                "air_temperature_c",
                default_temperature_c,
            )

            return float(temperature_c)

    return float(default_temperature_c)

def clamp_humidity_ratio(
    humidity_ratio_kg_kg: float,
) -> float:
    """
    Clamp humidity ratio to a safe physical range.

    This is the conserved transported moisture state.
    """

    humidity_ratio_kg_kg = float(humidity_ratio_kg_kg)

    if humidity_ratio_kg_kg < MIN_HUMIDITY_RATIO_KG_KG:
        return MIN_HUMIDITY_RATIO_KG_KG

    if humidity_ratio_kg_kg > MAX_HUMIDITY_RATIO_KG_KG:
        return MAX_HUMIDITY_RATIO_KG_KG

    return humidity_ratio_kg_kg


def clamp_atmospheric_pressure_pa(
    atmospheric_pressure_pa: float,
) -> float:
    """
    Clamp atmospheric pressure to a safe range for psychrometric calculations.
    """

    atmospheric_pressure_pa = float(atmospheric_pressure_pa)

    if atmospheric_pressure_pa < MIN_ATMOSPHERIC_PRESSURE_PA:
        return MIN_ATMOSPHERIC_PRESSURE_PA

    if atmospheric_pressure_pa > MAX_ATMOSPHERIC_PRESSURE_PA:
        return MAX_ATMOSPHERIC_PRESSURE_PA

    return atmospheric_pressure_pa

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

def _interzone_link_other_zone_id(
    link: Any,
    zone_id: str,
) -> str:
    if hasattr(link, "other_zone_id"):
        return link.other_zone_id(zone_id)

    zone_a_id = _get_attr_or_default(
        link,
        "zone_a_id",
        "",
    )

    zone_b_id = _get_attr_or_default(
        link,
        "zone_b_id",
        "",
    )

    if zone_id == zone_a_id:
        return zone_b_id

    if zone_id == zone_b_id:
        return zone_a_id

    raise ValueError(
        "Zone "
        + zone_id
        + " is not connected by interzone airflow link."
    )
    

def _clamp_relative_humidity_percent(
    relative_humidity_percent: Any,
) -> float:
    relative_humidity_percent = float(relative_humidity_percent)

    if relative_humidity_percent < MIN_RELATIVE_HUMIDITY_PERCENT:
        return MIN_RELATIVE_HUMIDITY_PERCENT

    if relative_humidity_percent > MAX_RELATIVE_HUMIDITY_PERCENT:
        return MAX_RELATIVE_HUMIDITY_PERCENT

    return relative_humidity_percent
