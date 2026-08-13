"""
ABBEY acoustic placeholder model.

Phase 14.1-14.2:
- basic dB math helpers
- acoustic parameter/state containers
- building-model adapters
- weather outdoor-noise adapter

Important:
    This is a placeholder, not a calibrated acoustic solver.
    Keep dB internally.
    Later engine integration should write normalized discomfort input
    to ZoneState.indoor_noise, not raw dB.
"""

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional
import copy
import math


ACOUSTIC_MODEL_FAMILY = "abbey_placeholder_acoustic_model"
ACOUSTIC_MODEL_PHASE = "14.1_14.2"
ACOUSTIC_MODEL_SOURCE = "physics.acoustics.Phase14.1_14.2"

ACOUSTIC_STATE_VARIABLE_DB = "indoor_noise_db"
ACOUSTIC_DISCOMFORT_VARIABLE = "indoor_noise_normalized_discomfort"

DEFAULT_INDOOR_NOISE_INITIAL_DB = 35.0
DEFAULT_BACKGROUND_NOISE_DB = 30.0
DEFAULT_OUTDOOR_NOISE_DB = 45.0
DEFAULT_ROOM_ABSORPTION_FACTOR = 0.3

DEFAULT_NOISE_COMFORT_DB = 35.0
DEFAULT_NOISE_STRESS_DB = 75.0

MIN_NOISE_DB = 0.0
MAX_REASONABLE_NOISE_DB = 140.0

REFERENCE_ENERGY = 1.0



def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)

    if not math.isfinite(out):
        return float(default)

    return out


def _non_negative_float(value: Any, field_name: str = "value") -> float:
    value = _safe_float(value, default=0.0)

    if value < 0.0:
        raise ValueError(field_name + " cannot be negative. Got: " + str(value))

    return value


def _clamp(value: Any, lower: float, upper: float) -> float:
    value = _safe_float(value, default=lower)

    if value < lower:
        return float(lower)

    if value > upper:
        return float(upper)

    return float(value)


def _clamp_fraction(value: Any) -> float:
    return _clamp(value, 0.0, 1.0)


def _get_attr_or_key(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(key, default)

    return getattr(obj, key, default)


def db_to_energy(noise_db: Any) -> float:
    """
    Convert a dB level into relative acoustic energy.

    This uses the standard logarithmic relation:
        E_rel = 10 ** (L_db / 10)

    Inputs are clamped to non-negative dB for ABBEY placeholder use.
    """

    noise_db = _non_negative_float(noise_db, "noise_db")

    if noise_db <= 0.0:
        return 0.0

    return REFERENCE_ENERGY * (10.0 ** (noise_db / 10.0))


def energy_to_db(energy: Any, default_db: float = 0.0) -> float:
    """
    Convert relative acoustic energy back to dB.

    Empty/zero energy returns default_db.
    """

    energy = _safe_float(energy, default=0.0)

    if energy <= 0.0:
        return _non_negative_float(default_db, "default_db")

    return 10.0 * math.log10(energy / REFERENCE_ENERGY)


def add_noise_levels_db(
    noise_levels_db: Optional[List[Any]],
    background_db: Optional[Any] = None,
    default_db: float = DEFAULT_BACKGROUND_NOISE_DB,
) -> float:
    """
    Logarithmically add noise levels.

    Empty source list:
        - returns background_db when given
        - otherwise returns default_db
    """

    levels = []

    if noise_levels_db is not None:
        levels = list(noise_levels_db)

    if background_db is not None:
        levels.append(background_db)

    if not levels:
        return _non_negative_float(default_db, "default_db")

    total_energy = 0.0

    for level in levels:
        level_db = _safe_float(level, default=0.0)

        if level_db <= 0.0:
            continue

        total_energy += db_to_energy(level_db)

    if total_energy <= 0.0:
        return _non_negative_float(default_db, "default_db")

    return energy_to_db(total_energy, default_db=default_db)


def attenuate_noise_db(
    source_noise_db: Any,
    attenuation_db: Any,
    floor_db: float = MIN_NOISE_DB,
) -> float:
    """
    Apply simple dB attenuation.

    Placeholder rule:
        received_db = max(floor_db, source_noise_db - attenuation_db)

    This never creates negative noise levels.
    """

    source_noise_db = _non_negative_float(source_noise_db, "source_noise_db")
    attenuation_db = _non_negative_float(attenuation_db, "attenuation_db")
    floor_db = _non_negative_float(floor_db, "floor_db")

    return max(floor_db, source_noise_db - attenuation_db)


def normalize_noise_discomfort_input(
    noise_db: Any,
    comfort_db: float = DEFAULT_NOISE_COMFORT_DB,
    stress_db: float = DEFAULT_NOISE_STRESS_DB,
) -> float:
    """
    Convert raw dB into ABBEY's current normalized acoustic discomfort input.

    0.0:
        at or below comfort_db

    1.0:
        at or above stress_db
    """

    noise_db = _non_negative_float(noise_db, "noise_db")
    comfort_db = _non_negative_float(comfort_db, "comfort_db")
    stress_db = _non_negative_float(stress_db, "stress_db")

    if stress_db <= comfort_db:
        stress_db = comfort_db + 1.0

    return _clamp_fraction(
        (noise_db - comfort_db) / (stress_db - comfort_db)
    )


@dataclass
class ZoneAcousticParameters:
    zone_id: str
    background_noise_db: float = DEFAULT_BACKGROUND_NOISE_DB
    indoor_noise_initial_db: float = DEFAULT_INDOOR_NOISE_INITIAL_DB
    room_absorption_factor: float = DEFAULT_ROOM_ABSORPTION_FACTOR
    source: str = ACOUSTIC_MODEL_SOURCE

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneAcousticParameters.zone_id cannot be empty.")

        self.background_noise_db = _non_negative_float(
            self.background_noise_db,
            "background_noise_db",
        )

        self.indoor_noise_initial_db = _non_negative_float(
            self.indoor_noise_initial_db,
            "indoor_noise_initial_db",
        )

        self.room_absorption_factor = _clamp_fraction(
            self.room_absorption_factor
        )

    def copy(self, **updates: Any) -> "ZoneAcousticParameters":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "background_noise_db": self.background_noise_db,
            "indoor_noise_initial_db": self.indoor_noise_initial_db,
            "room_absorption_factor": self.room_absorption_factor,
            "source": self.source,
        }


@dataclass
class BuildingAcousticParameters:
    zone_parameters: Dict[str, ZoneAcousticParameters] = field(default_factory=dict)
    source: str = ACOUSTIC_MODEL_SOURCE

    def __post_init__(self) -> None:
        cleaned = {}

        for zone_id, parameters in self.zone_parameters.items():
            if not isinstance(parameters, ZoneAcousticParameters):
                raise TypeError(
                    "BuildingAcousticParameters.zone_parameters must contain "
                    "ZoneAcousticParameters objects."
                )

            if parameters.zone_id != zone_id:
                raise ValueError(
                    "Zone acoustic parameter key "
                    + str(zone_id)
                    + " does not match parameters.zone_id "
                    + str(parameters.zone_id)
                )

            cleaned[zone_id] = parameters

        self.zone_parameters = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_parameters.keys())

    def has_zone(self, zone_id: str) -> bool:
        return zone_id in self.zone_parameters

    def get_zone_parameters(self, zone_id: str) -> ZoneAcousticParameters:
        if zone_id not in self.zone_parameters:
            raise KeyError("Acoustic parameters missing for zone: " + str(zone_id))

        return self.zone_parameters[zone_id]

    def background_noise_db_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: parameters.background_noise_db
            for zone_id, parameters in self.zone_parameters.items()
        }

    def copy(self, **updates: Any) -> "BuildingAcousticParameters":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "zone_count": len(self.zone_parameters),
            "zone_parameters": {
                zone_id: parameters.to_dict()
                for zone_id, parameters in self.zone_parameters.items()
            },
        }


@dataclass
class ZoneAcousticState:
    zone_id: str
    indoor_noise_db: float = DEFAULT_INDOOR_NOISE_INITIAL_DB
    source: str = ACOUSTIC_MODEL_SOURCE

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneAcousticState.zone_id cannot be empty.")

        self.indoor_noise_db = _non_negative_float(
            self.indoor_noise_db,
            "indoor_noise_db",
        )

    def normalized_discomfort_input(
        self,
        comfort_db: float = DEFAULT_NOISE_COMFORT_DB,
        stress_db: float = DEFAULT_NOISE_STRESS_DB,
    ) -> float:
        return normalize_noise_discomfort_input(
            noise_db=self.indoor_noise_db,
            comfort_db=comfort_db,
            stress_db=stress_db,
        )

    def copy(self, **updates: Any) -> "ZoneAcousticState":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "indoor_noise_db": self.indoor_noise_db,
            "indoor_noise_normalized_discomfort": self.normalized_discomfort_input(),
            "source": self.source,
        }


@dataclass
class BuildingAcousticState:
    zone_states: Dict[str, ZoneAcousticState] = field(default_factory=dict)
    source: str = ACOUSTIC_MODEL_SOURCE

    def __post_init__(self) -> None:
        cleaned = {}

        for zone_id, state in self.zone_states.items():
            if not isinstance(state, ZoneAcousticState):
                raise TypeError(
                    "BuildingAcousticState.zone_states must contain "
                    "ZoneAcousticState objects."
                )

            if state.zone_id != zone_id:
                raise ValueError(
                    "Zone acoustic state key "
                    + str(zone_id)
                    + " does not match state.zone_id "
                    + str(state.zone_id)
                )

            cleaned[zone_id] = state

        self.zone_states = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_states.keys())

    def has_zone(self, zone_id: str) -> bool:
        return zone_id in self.zone_states

    def get_zone_state(self, zone_id: str) -> ZoneAcousticState:
        if zone_id not in self.zone_states:
            raise KeyError("Acoustic state missing for zone: " + str(zone_id))

        return self.zone_states[zone_id]

    def indoor_noise_db_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: state.indoor_noise_db
            for zone_id, state in self.zone_states.items()
        }

    def normalized_discomfort_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: state.normalized_discomfort_input()
            for zone_id, state in self.zone_states.items()
        }

    def copy(self, **updates: Any) -> "BuildingAcousticState":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "zone_count": len(self.zone_states),
            "indoor_noise_db_by_zone": self.indoor_noise_db_by_zone(),
            "normalized_discomfort_by_zone": self.normalized_discomfort_by_zone(),
            "zone_states": {
                zone_id: state.to_dict()
                for zone_id, state in self.zone_states.items()
            },
        }


@dataclass
class OutdoorAcousticBoundary:
    outdoor_noise_db: float = DEFAULT_OUTDOOR_NOISE_DB
    source: str = ACOUSTIC_MODEL_SOURCE

    def __post_init__(self) -> None:
        self.outdoor_noise_db = _non_negative_float(
            self.outdoor_noise_db,
            "outdoor_noise_db",
        )

    def copy(self, **updates: Any) -> "OutdoorAcousticBoundary":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outdoor_noise_db": self.outdoor_noise_db,
            "source": self.source,
        }


# ============================================================
# PHASE 14.3-14.7: noise-source bridge and placeholder solver
# ============================================================

ACOUSTIC_NOISE_SOURCE_INPUT_SOURCE = (
    "BuildingInternalSourceResult_to_BuildingNoiseSourceInputs"
)

ACOUSTIC_STEP_SOURCE = "physics.acoustics.Phase14.3_14.7"

OUTDOOR_NOISE_SOURCE = "outdoor_boundary"
INTERZONE_NOISE_SOURCE = "interzone_transmission"
LOCAL_NOISE_SOURCE = "local_internal_source"


@dataclass
class ZoneNoiseSourceInput:
    zone_id: str
    noise_source_db: float

    source_id: str = ""
    source_kind: str = ""
    source_type: str = ""
    action_name: str = ""
    actor_id: str = ""

    duration_minutes: float = 0.0
    source: str = ACOUSTIC_NOISE_SOURCE_INPUT_SOURCE
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneNoiseSourceInput.zone_id cannot be empty.")

        self.noise_source_db = _non_negative_float(
            self.noise_source_db,
            "noise_source_db",
        )

        self.source_id = str(self.source_id)
        self.source_kind = str(self.source_kind)
        self.source_type = str(self.source_type)
        self.action_name = str(self.action_name)
        self.actor_id = str(self.actor_id)

        self.duration_minutes = _non_negative_float(
            self.duration_minutes,
            "duration_minutes",
        )

        if self.metadata is None:
            self.metadata = {}

        if not isinstance(self.metadata, dict):
            self.metadata = dict(self.metadata)

    def is_active(self) -> bool:
        return self.noise_source_db > 0.0

    def copy(self, **updates: Any) -> "ZoneNoiseSourceInput":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "noise_source_db": self.noise_source_db,
            "source_id": self.source_id,
            "source_kind": self.source_kind,
            "source_type": self.source_type,
            "action_name": self.action_name,
            "actor_id": self.actor_id,
            "duration_minutes": self.duration_minutes,
            "source": self.source,
            "metadata": dict(self.metadata),
        }


@dataclass
class BuildingNoiseSourceInputs:
    noise_sources_by_zone: Dict[str, List[ZoneNoiseSourceInput]] = field(default_factory=dict)
    source: str = ACOUSTIC_NOISE_SOURCE_INPUT_SOURCE

    def __post_init__(self) -> None:
        cleaned = {}

        for zone_id, sources in self.noise_sources_by_zone.items():
            zone_id = str(zone_id)

            if sources is None:
                sources = []

            cleaned_sources = []

            for item in sources:
                if not isinstance(item, ZoneNoiseSourceInput):
                    raise TypeError(
                        "BuildingNoiseSourceInputs must contain ZoneNoiseSourceInput objects."
                    )

                if item.zone_id != zone_id:
                    raise ValueError(
                        "Noise source zone_id "
                        + str(item.zone_id)
                        + " does not match container zone_id "
                        + str(zone_id)
                    )

                if item.is_active():
                    cleaned_sources.append(item)

            cleaned[zone_id] = cleaned_sources

        self.noise_sources_by_zone = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.noise_sources_by_zone.keys())

    def has_zone(self, zone_id: str) -> bool:
        return zone_id in self.noise_sources_by_zone

    def get_zone_sources(self, zone_id: str) -> List[ZoneNoiseSourceInput]:
        return list(self.noise_sources_by_zone.get(zone_id, []))

    def noise_levels_by_zone(self) -> Dict[str, List[float]]:
        return {
            zone_id: [
                source.noise_source_db
                for source in sources
                if source.noise_source_db > 0.0
            ]
            for zone_id, sources in self.noise_sources_by_zone.items()
        }

    def local_noise_source_db_by_zone(self) -> Dict[str, float]:
        out = {}

        for zone_id, sources in self.noise_sources_by_zone.items():
            out[zone_id] = add_noise_levels_db(
                [
                    source.noise_source_db
                    for source in sources
                    if source.noise_source_db > 0.0
                ],
                background_db=None,
                default_db=0.0,
            )

        return out

    def source_count_by_zone(self) -> Dict[str, int]:
        return {
            zone_id: len(sources)
            for zone_id, sources in self.noise_sources_by_zone.items()
        }

    def copy(self, **updates: Any) -> "BuildingNoiseSourceInputs":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "zone_count": len(self.noise_sources_by_zone),
            "source_count_by_zone": self.source_count_by_zone(),
            "local_noise_source_db_by_zone": self.local_noise_source_db_by_zone(),
            "noise_sources_by_zone": {
                zone_id: [
                    source.to_dict()
                    for source in sources
                ]
                for zone_id, sources in self.noise_sources_by_zone.items()
            },
        }


@dataclass
class ZoneAcousticStepResult:
    zone_id: str

    background_noise_db: float = DEFAULT_BACKGROUND_NOISE_DB
    local_noise_source_db: float = 0.0
    local_noise_source_count: int = 0

    outdoor_noise_contribution_db: float = 0.0
    interzone_noise_contribution_db: float = 0.0
    max_neighbor_noise_contribution_db: float = 0.0

    indoor_noise_db: float = DEFAULT_INDOOR_NOISE_INITIAL_DB
    acoustic_discomfort_input: float = 0.0

    local_source_levels_db: List[float] = field(default_factory=list)
    outdoor_source_levels_db: List[float] = field(default_factory=list)
    interzone_source_levels_db: List[float] = field(default_factory=list)

    source: str = ACOUSTIC_STEP_SOURCE

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneAcousticStepResult.zone_id cannot be empty.")

        self.background_noise_db = _non_negative_float(
            self.background_noise_db,
            "background_noise_db",
        )

        self.local_noise_source_db = _non_negative_float(
            self.local_noise_source_db,
            "local_noise_source_db",
        )

        self.local_noise_source_count = int(self.local_noise_source_count)

        if self.local_noise_source_count < 0:
            self.local_noise_source_count = 0

        self.outdoor_noise_contribution_db = _non_negative_float(
            self.outdoor_noise_contribution_db,
            "outdoor_noise_contribution_db",
        )

        self.interzone_noise_contribution_db = _non_negative_float(
            self.interzone_noise_contribution_db,
            "interzone_noise_contribution_db",
        )

        self.max_neighbor_noise_contribution_db = _non_negative_float(
            self.max_neighbor_noise_contribution_db,
            "max_neighbor_noise_contribution_db",
        )

        self.indoor_noise_db = _non_negative_float(
            self.indoor_noise_db,
            "indoor_noise_db",
        )

        self.acoustic_discomfort_input = _clamp_fraction(
            self.acoustic_discomfort_input
        )

        self.local_source_levels_db = [
            _non_negative_float(value, "local_source_level_db")
            for value in self.local_source_levels_db
            if _safe_float(value, default=0.0) > 0.0
        ]

        self.outdoor_source_levels_db = [
            _non_negative_float(value, "outdoor_source_level_db")
            for value in self.outdoor_source_levels_db
            if _safe_float(value, default=0.0) > 0.0
        ]

        self.interzone_source_levels_db = [
            _non_negative_float(value, "interzone_source_level_db")
            for value in self.interzone_source_levels_db
            if _safe_float(value, default=0.0) > 0.0
        ]

    def to_zone_state_indoor_noise(self) -> float:
        """
        Current agent compatibility:
        ZoneState.indoor_noise receives normalized discomfort input, not raw dB.
        """

        return self.acoustic_discomfort_input

    def copy(self, **updates: Any) -> "ZoneAcousticStepResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "background_noise_db": self.background_noise_db,
            "local_noise_source_db": self.local_noise_source_db,
            "local_noise_source_count": self.local_noise_source_count,
            "outdoor_noise_contribution_db": self.outdoor_noise_contribution_db,
            "interzone_noise_contribution_db": self.interzone_noise_contribution_db,
            "max_neighbor_noise_contribution_db": self.max_neighbor_noise_contribution_db,
            "indoor_noise_db": self.indoor_noise_db,
            "acoustic_discomfort_input": self.acoustic_discomfort_input,
            "indoor_noise": self.to_zone_state_indoor_noise(),
            "local_source_levels_db": list(self.local_source_levels_db),
            "outdoor_source_levels_db": list(self.outdoor_source_levels_db),
            "interzone_source_levels_db": list(self.interzone_source_levels_db),
            "source": self.source,
        }


@dataclass
class BuildingAcousticStepResult:
    updated_state: BuildingAcousticState
    zone_results: Dict[str, ZoneAcousticStepResult] = field(default_factory=dict)

    noise_source_inputs: Optional[BuildingNoiseSourceInputs] = None
    outdoor_boundary: Optional[OutdoorAcousticBoundary] = None

    source: str = ACOUSTIC_STEP_SOURCE

    def __post_init__(self) -> None:
        if not isinstance(self.updated_state, BuildingAcousticState):
            raise TypeError(
                "BuildingAcousticStepResult.updated_state must be BuildingAcousticState."
            )

        cleaned = {}

        for zone_id, result in self.zone_results.items():
            if not isinstance(result, ZoneAcousticStepResult):
                raise TypeError(
                    "BuildingAcousticStepResult.zone_results must contain ZoneAcousticStepResult objects."
                )

            if result.zone_id != zone_id:
                raise ValueError(
                    "Zone acoustic result key "
                    + str(zone_id)
                    + " does not match result.zone_id "
                    + str(result.zone_id)
                )

            cleaned[zone_id] = result

        self.zone_results = cleaned

    def zone_ids(self) -> List[str]:
        return list(self.zone_results.keys())

    def has_zone(self, zone_id: str) -> bool:
        return zone_id in self.zone_results

    def get_zone_result(self, zone_id: str) -> ZoneAcousticStepResult:
        if zone_id not in self.zone_results:
            raise KeyError("Acoustic result missing for zone: " + str(zone_id))

        return self.zone_results[zone_id]

    def indoor_noise_db_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: result.indoor_noise_db
            for zone_id, result in self.zone_results.items()
        }

    def normalized_indoor_noise_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: result.acoustic_discomfort_input
            for zone_id, result in self.zone_results.items()
        }

    def zone_records(self) -> List[Dict[str, Any]]:
        return [
            result.to_dict()
            for result in self.zone_results.values()
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "zone_count": len(self.zone_results),
            "indoor_noise_db_by_zone": self.indoor_noise_db_by_zone(),
            "normalized_indoor_noise_by_zone": self.normalized_indoor_noise_by_zone(),
            "updated_state": self.updated_state.to_dict(),
            "zone_results": {
                zone_id: result.to_dict()
                for zone_id, result in self.zone_results.items()
            },
            "noise_source_inputs": (
                self.noise_source_inputs.to_dict()
                if self.noise_source_inputs is not None
                else None
            ),
            "outdoor_boundary": (
                self.outdoor_boundary.to_dict()
                if self.outdoor_boundary is not None
                else None
            ),
        }


def _all_zone_ids_from_building_model(building_model: Any) -> List[str]:
    if building_model is None:
        return []

    if hasattr(building_model, "all_zone_ids"):
        return list(building_model.all_zone_ids())

    if hasattr(building_model, "all_zone_models"):
        return list(building_model.all_zone_models().keys())

    return []


def _all_zone_ids_for_acoustic_step(
    building_model: Any,
    internal_source_result: Any = None,
    expected_zone_ids: Optional[List[str]] = None,
) -> List[str]:
    out = []

    for zone_id in _all_zone_ids_from_building_model(building_model):
        if zone_id not in out:
            out.append(zone_id)

    if expected_zone_ids is not None:
        for zone_id in expected_zone_ids:
            zone_id = str(zone_id)

            if zone_id and zone_id not in out:
                out.append(zone_id)

    if internal_source_result is not None and hasattr(internal_source_result, "all_zone_ids"):
        for zone_id in internal_source_result.all_zone_ids():
            zone_id = str(zone_id)

            if zone_id and zone_id not in out:
                out.append(zone_id)

    return out


def make_noise_source_input_from_internal_source_record(
    record: Any,
) -> Optional[ZoneNoiseSourceInput]:
    if record is None:
        return None

    noise_source_db = _safe_float(
        _get_attr_or_key(record, "noise_source_db", 0.0),
        default=0.0,
    )

    if noise_source_db <= 0.0:
        return None

    zone_id = str(_get_attr_or_key(record, "zone_id", "")).strip()

    if not zone_id:
        return None

    metadata = _get_attr_or_key(record, "metadata", {}) or {}

    if not isinstance(metadata, dict):
        metadata = dict(metadata)

    return ZoneNoiseSourceInput(
        zone_id=zone_id,
        noise_source_db=noise_source_db,
        source_id=str(_get_attr_or_key(record, "source_id", "")),
        source_kind=str(_get_attr_or_key(record, "source_kind", "")),
        source_type=str(_get_attr_or_key(record, "source_type", "")),
        action_name=str(_get_attr_or_key(record, "action_name", "")),
        actor_id=str(_get_attr_or_key(record, "actor_id", "")),
        duration_minutes=_get_attr_or_key(record, "duration_minutes", 0.0),
        metadata=metadata,
    )


def make_empty_building_noise_source_inputs(
    zone_ids: Optional[List[str]] = None,
) -> BuildingNoiseSourceInputs:
    if zone_ids is None:
        zone_ids = []

    return BuildingNoiseSourceInputs(
        noise_sources_by_zone={
            str(zone_id): []
            for zone_id in zone_ids
            if str(zone_id).strip()
        }
    )


def make_building_noise_source_inputs_from_internal_source_result(
    internal_source_result: Any,
    expected_zone_ids: Optional[List[str]] = None,
) -> BuildingNoiseSourceInputs:
    zone_ids = []

    if expected_zone_ids is not None:
        zone_ids.extend([str(zone_id) for zone_id in expected_zone_ids])

    if internal_source_result is not None and hasattr(internal_source_result, "all_zone_ids"):
        for zone_id in internal_source_result.all_zone_ids():
            zone_id = str(zone_id)

            if zone_id not in zone_ids:
                zone_ids.append(zone_id)

    out = {
        zone_id: []
        for zone_id in zone_ids
        if str(zone_id).strip()
    }

    if internal_source_result is None:
        return BuildingNoiseSourceInputs(noise_sources_by_zone=out)

    records = list(getattr(internal_source_result, "records", []) or [])

    if records:
        for record in records:
            source_input = make_noise_source_input_from_internal_source_record(
                record
            )

            if source_input is None:
                continue

            if source_input.zone_id not in out:
                out[source_input.zone_id] = []

            out[source_input.zone_id].append(source_input)

        return BuildingNoiseSourceInputs(noise_sources_by_zone=out)

    # Fallback for objects that expose only noise_sources_by_zone().
    if hasattr(internal_source_result, "noise_sources_by_zone"):
        raw = internal_source_result.noise_sources_by_zone() or {}

        for zone_id, levels in raw.items():
            zone_id = str(zone_id)

            if zone_id not in out:
                out[zone_id] = []

            for index, level in enumerate(levels or []):
                level = _safe_float(level, default=0.0)

                if level <= 0.0:
                    continue

                out[zone_id].append(
                    ZoneNoiseSourceInput(
                        zone_id=zone_id,
                        noise_source_db=level,
                        source_id="noise_source_" + str(index),
                        source="noise_sources_by_zone_fallback",
                    )
                )

    return BuildingNoiseSourceInputs(noise_sources_by_zone=out)


def noise_levels_by_zone_from_internal_source_result(
    internal_source_result: Any,
    expected_zone_ids: Optional[List[str]] = None,
) -> Dict[str, List[float]]:
    inputs = make_building_noise_source_inputs_from_internal_source_result(
        internal_source_result=internal_source_result,
        expected_zone_ids=expected_zone_ids,
    )

    return inputs.noise_levels_by_zone()


def _boundary_connections_for_zone(
    physics_graph: Any,
    zone_id: str,
) -> List[Any]:
    if physics_graph is None:
        return []

    raw = getattr(physics_graph, "boundary_connections", {}) or {}

    return [
        connection
        for connection in raw.values()
        if str(_get_attr_or_key(connection, "zone_id", "")) == str(zone_id)
    ]


def _zone_connections_for_zone(
    physics_graph: Any,
    zone_id: str,
) -> List[Any]:
    if physics_graph is None:
        return []

    raw = getattr(physics_graph, "zone_connections", {}) or {}

    out = []

    for connection in raw.values():
        from_zone_id = str(_get_attr_or_key(connection, "from_zone_id", ""))
        to_zone_id = str(_get_attr_or_key(connection, "to_zone_id", ""))

        if from_zone_id == zone_id or to_zone_id == zone_id:
            out.append(connection)

    return out


def _noise_transmission_factor_to_extra_attenuation_db(
    transmission_factor: Any,
) -> float:
    transmission_factor = _clamp_fraction(transmission_factor)

    if transmission_factor <= 0.0:
        return MAX_REASONABLE_NOISE_DB

    if transmission_factor >= 1.0:
        return 0.0

    return -10.0 * math.log10(transmission_factor)


def calculate_outdoor_noise_contributions_by_zone(
    building_model: Any,
    physics_graph: Any,
    outdoor_boundary: OutdoorAcousticBoundary,
) -> Dict[str, List[float]]:
    zone_ids = _all_zone_ids_from_building_model(building_model)

    out = {
        zone_id: []
        for zone_id in zone_ids
    }

    if physics_graph is None or outdoor_boundary is None:
        return out

    outdoor_noise_db = outdoor_boundary.outdoor_noise_db

    if outdoor_noise_db <= 0.0:
        return out

    for zone_id in zone_ids:
        for boundary in _boundary_connections_for_zone(physics_graph, zone_id):
            if hasattr(boundary, "effective_outdoor_sound_reduction_db"):
                reduction_db = boundary.effective_outdoor_sound_reduction_db()
            else:
                reduction_db = _get_attr_or_key(
                    boundary,
                    "window_sound_reduction_db",
                    0.0,
                )

            if hasattr(boundary, "effective_outdoor_noise_transmission_factor"):
                transmission_factor = (
                    boundary.effective_outdoor_noise_transmission_factor()
                )
            else:
                transmission_factor = _get_attr_or_key(
                    boundary,
                    "outside_noise_transmission_factor",
                    1.0,
                )

            extra_reduction_db = _noise_transmission_factor_to_extra_attenuation_db(
                transmission_factor
            )

            contribution_db = attenuate_noise_db(
                source_noise_db=outdoor_noise_db,
                attenuation_db=float(reduction_db) + float(extra_reduction_db),
            )

            if contribution_db > 0.0:
                out[zone_id].append(contribution_db)

    return out


def calculate_outdoor_noise_contribution_db_by_zone(
    building_model: Any,
    physics_graph: Any,
    outdoor_boundary: OutdoorAcousticBoundary,
) -> Dict[str, float]:
    raw = calculate_outdoor_noise_contributions_by_zone(
        building_model=building_model,
        physics_graph=physics_graph,
        outdoor_boundary=outdoor_boundary,
    )

    return {
        zone_id: add_noise_levels_db(
            values,
            background_db=None,
            default_db=0.0,
        )
        for zone_id, values in raw.items()
    }


def calculate_interzone_noise_contributions_by_zone(
    building_model: Any,
    physics_graph: Any,
    source_noise_db_by_zone: Dict[str, float],
) -> Dict[str, List[float]]:
    zone_ids = _all_zone_ids_from_building_model(building_model)

    out = {
        zone_id: []
        for zone_id in zone_ids
    }

    if physics_graph is None:
        return out

    raw_connections = getattr(physics_graph, "zone_connections", {}) or {}

    for connection in raw_connections.values():
        from_zone_id = str(_get_attr_or_key(connection, "from_zone_id", ""))
        to_zone_id = str(_get_attr_or_key(connection, "to_zone_id", ""))

        if not from_zone_id or not to_zone_id:
            continue

        if hasattr(connection, "effective_sound_reduction_db"):
            reduction_db = connection.effective_sound_reduction_db()
        else:
            reduction_db = _get_attr_or_key(
                connection,
                "partition_sound_reduction_db",
                35.0,
            )

        for source_zone_id, receiver_zone_id in [
            (from_zone_id, to_zone_id),
            (to_zone_id, from_zone_id),
        ]:
            source_noise_db = _safe_float(
                source_noise_db_by_zone.get(source_zone_id, 0.0),
                default=0.0,
            )

            if source_noise_db <= 0.0:
                continue

            received_db = attenuate_noise_db(
                source_noise_db=source_noise_db,
                attenuation_db=reduction_db,
            )

            if received_db <= 0.0:
                continue

            if receiver_zone_id not in out:
                out[receiver_zone_id] = []

            out[receiver_zone_id].append(received_db)

    return out


def calculate_zone_acoustic_step_result(
    zone_id: str,
    parameters: ZoneAcousticParameters,
    local_sources: List[ZoneNoiseSourceInput],
    outdoor_source_levels_db: Optional[List[float]] = None,
    interzone_source_levels_db: Optional[List[float]] = None,
) -> ZoneAcousticStepResult:
    if outdoor_source_levels_db is None:
        outdoor_source_levels_db = []

    if interzone_source_levels_db is None:
        interzone_source_levels_db = []

    local_source_levels_db = [
        source.noise_source_db
        for source in local_sources
        if source.noise_source_db > 0.0
    ]

    local_noise_source_db = add_noise_levels_db(
        local_source_levels_db,
        background_db=None,
        default_db=0.0,
    )

    outdoor_noise_contribution_db = add_noise_levels_db(
        outdoor_source_levels_db,
        background_db=None,
        default_db=0.0,
    )

    interzone_noise_contribution_db = add_noise_levels_db(
        interzone_source_levels_db,
        background_db=None,
        default_db=0.0,
    )

    components = []

    if local_noise_source_db > 0.0:
        components.append(local_noise_source_db)

    if outdoor_noise_contribution_db > 0.0:
        components.append(outdoor_noise_contribution_db)

    if interzone_noise_contribution_db > 0.0:
        components.append(interzone_noise_contribution_db)

    indoor_noise_db = add_noise_levels_db(
        components,
        background_db=parameters.background_noise_db,
        default_db=parameters.background_noise_db,
    )

    acoustic_discomfort_input = normalize_noise_discomfort_input(
        indoor_noise_db
    )

    return ZoneAcousticStepResult(
        zone_id=zone_id,
        background_noise_db=parameters.background_noise_db,
        local_noise_source_db=local_noise_source_db,
        local_noise_source_count=len(local_source_levels_db),
        outdoor_noise_contribution_db=outdoor_noise_contribution_db,
        interzone_noise_contribution_db=interzone_noise_contribution_db,
        max_neighbor_noise_contribution_db=(
            max(interzone_source_levels_db)
            if interzone_source_levels_db
            else 0.0
        ),
        indoor_noise_db=indoor_noise_db,
        acoustic_discomfort_input=acoustic_discomfort_input,
        local_source_levels_db=local_source_levels_db,
        outdoor_source_levels_db=list(outdoor_source_levels_db),
        interzone_source_levels_db=list(interzone_source_levels_db),
    )


def step_building_acoustic_state(
    building_model: Any,
    physics_graph: Any = None,
    weather_state: Any = None,
    internal_source_result: Any = None,
    previous_acoustic_state: Optional[BuildingAcousticState] = None,
    dt_minutes: float = 15.0,
) -> BuildingAcousticStepResult:
    """
    Full placeholder acoustic step.

    Combines:
        background zone noise
        local internal-source noise
        outdoor noise through boundary/window attenuation
        one-hop interzone propagation

    Keeps raw dB internally.
    Returns normalized acoustic discomfort input for ZoneState.indoor_noise.
    """

    if building_model is None:
        raise ValueError("building_model cannot be None.")

    dt_minutes = _non_negative_float(dt_minutes, "dt_minutes")

    zone_ids = _all_zone_ids_for_acoustic_step(
        building_model=building_model,
        internal_source_result=internal_source_result,
    )

    parameters = make_building_acoustic_parameters(building_model)

    if previous_acoustic_state is None:
        previous_acoustic_state = make_initial_building_acoustic_state(
            building_model
        )

    outdoor_boundary = make_outdoor_acoustic_boundary_from_weather_state(
        weather_state
    )

    noise_source_inputs = make_building_noise_source_inputs_from_internal_source_result(
        internal_source_result=internal_source_result,
        expected_zone_ids=zone_ids,
    )

    outdoor_sources_by_zone = calculate_outdoor_noise_contributions_by_zone(
        building_model=building_model,
        physics_graph=physics_graph,
        outdoor_boundary=outdoor_boundary,
    )

    # First pass: active sources only.
    #
    # Important:
    #   Zone background noise is a receiver-side baseline.
    #   It must NOT propagate to adjacent zones.
    #
    # Interzone propagation should use active acoustic components:
    #   - local internal-source noise
    #   - transmitted outdoor noise
    #
    # Then the final zone result adds the receiver zone's own background.
    active_source_noise_db_by_zone = {}

    for zone_id in zone_ids:
        local_sources = noise_source_inputs.get_zone_sources(zone_id)

        local_levels = [
            source.noise_source_db
            for source in local_sources
            if source.noise_source_db > 0.0
        ]

        local_db = add_noise_levels_db(
            local_levels,
            background_db=None,
            default_db=0.0,
        )

        outdoor_db = add_noise_levels_db(
            outdoor_sources_by_zone.get(zone_id, []),
            background_db=None,
            default_db=0.0,
        )

        active_components = []

        if local_db > 0.0:
            active_components.append(local_db)

        if outdoor_db > 0.0:
            active_components.append(outdoor_db)

        active_source_noise_db_by_zone[zone_id] = add_noise_levels_db(
            active_components,
            background_db=None,
            default_db=0.0,
        )

    interzone_sources_by_zone = calculate_interzone_noise_contributions_by_zone(
        building_model=building_model,
        physics_graph=physics_graph,
        source_noise_db_by_zone=active_source_noise_db_by_zone,
    )

    zone_results = {}
    zone_states = {}

    for zone_id in zone_ids:
        zone_parameters = parameters.get_zone_parameters(zone_id)

        result = calculate_zone_acoustic_step_result(
            zone_id=zone_id,
            parameters=zone_parameters,
            local_sources=noise_source_inputs.get_zone_sources(zone_id),
            outdoor_source_levels_db=outdoor_sources_by_zone.get(zone_id, []),
            interzone_source_levels_db=interzone_sources_by_zone.get(zone_id, []),
        )

        zone_results[zone_id] = result

        zone_states[zone_id] = ZoneAcousticState(
            zone_id=zone_id,
            indoor_noise_db=result.indoor_noise_db,
        )

    updated_state = BuildingAcousticState(
        zone_states=zone_states,
    )

    return BuildingAcousticStepResult(
        updated_state=updated_state,
        zone_results=zone_results,
        noise_source_inputs=noise_source_inputs,
        outdoor_boundary=outdoor_boundary,
    )

def make_zone_acoustic_parameters_from_zone_model(
    zone_model: Any,
) -> ZoneAcousticParameters:
    if zone_model is None:
        raise ValueError("zone_model cannot be None.")

    zone_id = str(_get_attr_or_key(zone_model, "zone_id", "")).strip()

    if not zone_id:
        raise ValueError("zone_model.zone_id cannot be empty.")

    return ZoneAcousticParameters(
        zone_id=zone_id,
        background_noise_db=_get_attr_or_key(
            zone_model,
            "background_noise_db",
            DEFAULT_BACKGROUND_NOISE_DB,
        ),
        indoor_noise_initial_db=_get_attr_or_key(
            zone_model,
            "indoor_noise_initial_db",
            DEFAULT_INDOOR_NOISE_INITIAL_DB,
        ),
        room_absorption_factor=_get_attr_or_key(
            zone_model,
            "room_absorption_factor",
            DEFAULT_ROOM_ABSORPTION_FACTOR,
        ),
    )


def make_building_acoustic_parameters(
    building_model: Any,
) -> BuildingAcousticParameters:
    if building_model is None:
        raise ValueError("building_model cannot be None.")

    if not hasattr(building_model, "all_zone_models"):
        raise TypeError(
            "building_model must expose all_zone_models() for acoustic parameters."
        )

    zone_parameters = {}

    for zone_id, zone_model in building_model.all_zone_models().items():
        zone_parameters[zone_id] = make_zone_acoustic_parameters_from_zone_model(
            zone_model
        )

    return BuildingAcousticParameters(
        zone_parameters=zone_parameters,
    )


def make_initial_zone_acoustic_state_from_zone_model(
    zone_model: Any,
) -> ZoneAcousticState:
    if zone_model is None:
        raise ValueError("zone_model cannot be None.")

    zone_id = str(_get_attr_or_key(zone_model, "zone_id", "")).strip()

    if not zone_id:
        raise ValueError("zone_model.zone_id cannot be empty.")

    return ZoneAcousticState(
        zone_id=zone_id,
        indoor_noise_db=_get_attr_or_key(
            zone_model,
            "indoor_noise_initial_db",
            DEFAULT_INDOOR_NOISE_INITIAL_DB,
        ),
    )


def make_initial_building_acoustic_state(
    building_model: Any,
) -> BuildingAcousticState:
    if building_model is None:
        raise ValueError("building_model cannot be None.")

    if not hasattr(building_model, "all_zone_models"):
        raise TypeError(
            "building_model must expose all_zone_models() for acoustic state."
        )

    zone_states = {}

    for zone_id, zone_model in building_model.all_zone_models().items():
        zone_states[zone_id] = make_initial_zone_acoustic_state_from_zone_model(
            zone_model
        )

    return BuildingAcousticState(
        zone_states=zone_states,
    )


def make_current_building_acoustic_state(
    building_model: Any,
) -> BuildingAcousticState:
    """
    Make current acoustic state from BuildingModel.

    Since ZoneState.indoor_noise is currently normalized discomfort-like,
    not raw dB, this function uses ZoneModel.indoor_noise_initial_db.
    Later engine integration should keep raw dB in acoustic state/result
    and write normalized values into ZoneState.indoor_noise.
    """

    return make_initial_building_acoustic_state(building_model)


def make_outdoor_acoustic_boundary_from_weather_state(
    weather_state: Any,
) -> OutdoorAcousticBoundary:
    if weather_state is None:
        return OutdoorAcousticBoundary(
            outdoor_noise_db=DEFAULT_OUTDOOR_NOISE_DB,
        )

    return OutdoorAcousticBoundary(
        outdoor_noise_db=_get_attr_or_key(
            weather_state,
            "outdoor_noise_db",
            DEFAULT_OUTDOOR_NOISE_DB,
        )
    )
