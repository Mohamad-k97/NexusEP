"""
ABBEY internal source mapping.

Phase 9.1:
- formal internal source data model
- people/action/appliance/lighting/HVAC source containers
- no physics solver
- no imports from agents or physics modules

Purpose:
    agents/actions/controllers
        -> clean internal source records
        -> thermal / airflow-CO2 / moisture / electricity outputs later
"""

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Mapping, Optional
import copy



INTERNAL_SOURCE_MODEL_FAMILY = "zone_internal_source_bridge"
INTERNAL_SOURCE_INTERFACE_MODE = "agent_action_to_physics_sources"

INTERNAL_SOURCE_KIND_PERSON = "person"
INTERNAL_SOURCE_KIND_APPLIANCE = "appliance"
INTERNAL_SOURCE_KIND_ACTIVITY = "activity"
INTERNAL_SOURCE_KIND_LIGHTING = "lighting"
INTERNAL_SOURCE_KIND_HVAC = "hvac"
INTERNAL_SOURCE_KIND_GENERIC = "generic"

VALID_INTERNAL_SOURCE_KINDS = {
    INTERNAL_SOURCE_KIND_PERSON,
    INTERNAL_SOURCE_KIND_APPLIANCE,
    INTERNAL_SOURCE_KIND_ACTIVITY,
    INTERNAL_SOURCE_KIND_LIGHTING,
    INTERNAL_SOURCE_KIND_HVAC,
    INTERNAL_SOURCE_KIND_GENERIC,
}

INTERNAL_SOURCE_TYPE_PEOPLE = "people"
INTERNAL_SOURCE_TYPE_COOKING = "cooking"
INTERNAL_SOURCE_TYPE_SHOWER = "shower"
INTERNAL_SOURCE_TYPE_LAUNDRY = "laundry"
INTERNAL_SOURCE_TYPE_LAPTOP = "laptop"
INTERNAL_SOURCE_TYPE_TV = "tv"
INTERNAL_SOURCE_TYPE_MUSIC = "music"
INTERNAL_SOURCE_TYPE_LIGHTING = "lighting"
INTERNAL_SOURCE_TYPE_HVAC = "hvac"
INTERNAL_SOURCE_TYPE_GENERIC = "generic"

DEFAULT_INTERNAL_SOURCE_DT_MINUTES = 15.0

DEFAULT_PERSON_SENSIBLE_HEAT_W = 75.0
DEFAULT_PERSON_CO2_GENERATION_M3_H = 0.018
DEFAULT_PERSON_MOISTURE_GENERATION_KG_H = 0.055
DEFAULT_PERSON_NOISE_SOURCE_DB = 0.0

DEFAULT_ELECTRICITY_TO_HEAT_FRACTION = 1.0

INTERNAL_SOURCE_RECORD_SOURCE_CHUNK = "chunk_records"
INTERNAL_SOURCE_RECORD_SOURCE_PEOPLE = "people_locations"
INTERNAL_SOURCE_RECORD_SOURCE_LIGHTING = "zone_control_commands_later"
INTERNAL_SOURCE_RECORD_SOURCE_HVAC = "zone_control_commands_later"

INTERNAL_SOURCE_RESULT_SOURCE = (
    "people + locations + chunk_records + optional controls"
)


PERSON_ACTIVITY_IDLE = "idle"
PERSON_ACTIVITY_SLEEPING = "sleeping"
PERSON_ACTIVITY_WORKING = "working"
PERSON_ACTIVITY_COOKING = "cooking"
PERSON_ACTIVITY_CLEANING = "cleaning"
PERSON_ACTIVITY_EXERCISING = "exercising"
PERSON_ACTIVITY_AWAY = "away"

PERSON_ACTIVITY_INTERNAL_SOURCE_MULTIPLIERS = {
    PERSON_ACTIVITY_IDLE: 1.00,
    PERSON_ACTIVITY_SLEEPING: 0.80,
    PERSON_ACTIVITY_WORKING: 1.10,
    PERSON_ACTIVITY_COOKING: 1.20,
    PERSON_ACTIVITY_CLEANING: 1.30,
    PERSON_ACTIVITY_EXERCISING: 1.80,
    PERSON_ACTIVITY_AWAY: 0.00,
}

APPLIANCE_INTERNAL_SOURCE_TYPES = {
    INTERNAL_SOURCE_TYPE_COOKING,
    INTERNAL_SOURCE_TYPE_LAUNDRY,
    INTERNAL_SOURCE_TYPE_LAPTOP,
    INTERNAL_SOURCE_TYPE_TV,
    INTERNAL_SOURCE_TYPE_MUSIC,
    INTERNAL_SOURCE_TYPE_GENERIC,
}

APPLIANCE_HEAT_SOURCE_MODE = "electricity_consumption_converted_to_heat"

DEFAULT_APPLIANCE_ELECTRICITY_TO_HEAT_FRACTION = 1.0

MOISTURE_INTERNAL_SOURCE_TYPES = {
    INTERNAL_SOURCE_TYPE_PEOPLE,
    INTERNAL_SOURCE_TYPE_COOKING,
    INTERNAL_SOURCE_TYPE_SHOWER,
    INTERNAL_SOURCE_TYPE_LAUNDRY,
    INTERNAL_SOURCE_TYPE_GENERIC,
}

MOISTURE_SOURCE_MODE_ACTION_DURATION_WEIGHTED = (
    "action_duration_weighted_moisture_generation"
)

LIGHTING_INTERNAL_SOURCE_MODE_POWER_RESULT = "lighting_power_result"
LIGHTING_INTERNAL_SOURCE_MODE_CONTROL_COMMAND = "zone_control_command"

DEFAULT_LIGHTING_ELECTRICITY_TO_HEAT_FRACTION = 1.0

HVAC_INTERNAL_SOURCE_MODE_CONTROL_COMMAND_AND_SYSTEM_SPEC = (
    "zone_control_command_and_zone_system_spec"
)

DEFAULT_HVAC_HEATING_EFFICIENCY_OR_COP = 1.0
DEFAULT_HVAC_COOLING_EFFICIENCY_OR_COP = 3.0

INTERNAL_SOURCE_AGGREGATION_MODE_TIMESTEP_AVERAGE = (
    "timestep_average_from_energy_or_mass"
)

INTERNAL_SOURCE_AGGREGATION_MODE_RAW_ACTIVE_RATE = (
    "raw_active_source_rate"
)

INTERNAL_SOURCE_TO_THERMAL_BRIDGE_SOURCE = (
    "BuildingInternalSourceResult_to_BuildingThermalGains"
)

INTERNAL_SOURCE_TO_AIRFLOW_BRIDGE_SOURCE = (
    "BuildingInternalSourceResult_to_BuildingAirflowControlInputs"
)

INTERNAL_SOURCE_TO_CO2_BRIDGE_SOURCE = (
    "BuildingInternalSourceResult_to_BuildingCO2GenerationResult"
)

INTERNAL_SOURCE_TO_MOISTURE_BRIDGE_SOURCE = (
    "BuildingInternalSourceResult_to_BuildingMoistureSourceInputs"
)

def _clamp_fraction(value: Any) -> float:
    value = float(value)

    if value < 0.0:
        return 0.0

    if value > 1.0:
        return 1.0

    return value


def _non_negative_float(
    value: Any,
    field_name: str,
    object_id: str = "",
) -> float:
    value = float(value)

    if value < 0.0:
        raise ValueError(
            field_name
            + " cannot be negative"
            + (" for " + object_id if object_id else "")
            + ". Got: "
            + str(value)
        )

    return value


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _safe_list(value: Any) -> List[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    return [value]


def _get_attr_or_key(
    obj: Any,
    key: str,
    default: Any = None,
) -> Any:
    if obj is None:
        return default

    if isinstance(obj, Mapping):
        return obj.get(key, default)

    return getattr(obj, key, default)


def _normalize_source_kind(value: Any) -> str:
    value = str(value).strip().lower().replace(" ", "_")

    if not value:
        value = INTERNAL_SOURCE_KIND_GENERIC

    if value not in VALID_INTERNAL_SOURCE_KINDS:
        raise ValueError(
            "Invalid internal source kind: "
            + value
            + ". Valid values: "
            + str(sorted(VALID_INTERNAL_SOURCE_KINDS))
        )

    return value


def _average_power_from_energy_wh(
    energy_wh: float,
    dt_minutes: float,
) -> float:
    energy_wh = float(energy_wh)
    dt_minutes = float(dt_minutes)

    if abs(energy_wh) <= 0.0:
        return 0.0

    if dt_minutes <= 0.0:
        return 0.0

    return energy_wh / (dt_minutes / 60.0)


def _energy_wh_from_average_power(
    power_w: float,
    dt_minutes: float,
) -> float:
    power_w = float(power_w)
    dt_minutes = float(dt_minutes)

    if dt_minutes <= 0.0:
        return 0.0

    return power_w * dt_minutes / 60.0


# ============================================================
# SOURCE SPECS
# ============================================================

@dataclass
class ActionInternalSourceSpec:
    """
    Default source behaviour for an action.

    This is a mapping rule, not an active source.
    """

    action_name: str
    default_zone_role: str = "current"

    source_kind: str = INTERNAL_SOURCE_KIND_APPLIANCE
    source_type: str = INTERNAL_SOURCE_TYPE_GENERIC

    electricity_to_heat_fraction: float = DEFAULT_ELECTRICITY_TO_HEAT_FRACTION
    sensible_heat_fraction: float = 1.0
    latent_heat_fraction: float = 0.0

    moisture_generation_kg_h: float = 0.0
    co2_generation_m3_h: float = 0.0

    noise_source_db: float = 0.0


    prefer_default_zone_role_when_target_is_current: bool = False

    def __post_init__(self) -> None:
        if not self.action_name:
            raise ValueError("ActionInternalSourceSpec.action_name cannot be empty.")

        self.default_zone_role = str(self.default_zone_role).strip().lower()
        if not self.default_zone_role:
            self.default_zone_role = "current"

        self.source_kind = _normalize_source_kind(self.source_kind)

        self.source_type = str(self.source_type).strip().lower()
        if not self.source_type:
            self.source_type = INTERNAL_SOURCE_TYPE_GENERIC

        self.electricity_to_heat_fraction = _clamp_fraction(
            self.electricity_to_heat_fraction
        )

        self.sensible_heat_fraction = _clamp_fraction(
            self.sensible_heat_fraction
        )

        self.latent_heat_fraction = _clamp_fraction(
            self.latent_heat_fraction
        )

        self.moisture_generation_kg_h = _non_negative_float(
            self.moisture_generation_kg_h,
            "moisture_generation_kg_h",
            self.action_name,
        )

        self.co2_generation_m3_h = _non_negative_float(
            self.co2_generation_m3_h,
            "co2_generation_m3_h",
            self.action_name,
        )

        self.noise_source_db = _non_negative_float(
            self.noise_source_db,
            "noise_source_db",
            self.action_name,
        )
        
        self.prefer_default_zone_role_when_target_is_current = bool(
            self.prefer_default_zone_role_when_target_is_current
        )

    def copy(self, **updates: Any) -> "ActionInternalSourceSpec":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_name": self.action_name,
            "default_zone_role": self.default_zone_role,
            "prefer_default_zone_role_when_target_is_current": (
                self.prefer_default_zone_role_when_target_is_current
            ),
            "source_kind": self.source_kind,
            "source_type": self.source_type,
            "electricity_to_heat_fraction": self.electricity_to_heat_fraction,
            "sensible_heat_fraction": self.sensible_heat_fraction,
            "latent_heat_fraction": self.latent_heat_fraction,
            "moisture_generation_kg_h": self.moisture_generation_kg_h,
            "co2_generation_m3_h": self.co2_generation_m3_h,
            "noise_source_db": self.noise_source_db,
        }


@dataclass
class PersonInternalSourceSpec:
    """
    Default physical source profile for one occupant.
    """

    sensible_heat_w: float = DEFAULT_PERSON_SENSIBLE_HEAT_W
    co2_generation_m3_h: float = DEFAULT_PERSON_CO2_GENERATION_M3_H
    moisture_generation_kg_h: float = DEFAULT_PERSON_MOISTURE_GENERATION_KG_H
    noise_source_db: float = DEFAULT_PERSON_NOISE_SOURCE_DB

    source_type: str = INTERNAL_SOURCE_TYPE_PEOPLE

    def __post_init__(self) -> None:
        self.sensible_heat_w = _non_negative_float(
            self.sensible_heat_w,
            "sensible_heat_w",
            "person",
        )

        self.co2_generation_m3_h = _non_negative_float(
            self.co2_generation_m3_h,
            "co2_generation_m3_h",
            "person",
        )

        self.moisture_generation_kg_h = _non_negative_float(
            self.moisture_generation_kg_h,
            "moisture_generation_kg_h",
            "person",
        )

        self.noise_source_db = _non_negative_float(
            self.noise_source_db,
            "noise_source_db",
            "person",
        )

        self.source_type = str(self.source_type).strip().lower()
        if not self.source_type:
            self.source_type = INTERNAL_SOURCE_TYPE_PEOPLE

    def copy(self, **updates: Any) -> "PersonInternalSourceSpec":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensible_heat_w": self.sensible_heat_w,
            "co2_generation_m3_h": self.co2_generation_m3_h,
            "moisture_generation_kg_h": self.moisture_generation_kg_h,
            "noise_source_db": self.noise_source_db,
            "source_type": self.source_type,
        }


DEFAULT_PERSON_INTERNAL_SOURCE_SPEC = PersonInternalSourceSpec()


DEFAULT_ACTION_INTERNAL_SOURCE_SPECS = {
    "cook": ActionInternalSourceSpec(
        action_name="cook",
        default_zone_role="kitchen",
        source_kind=INTERNAL_SOURCE_KIND_APPLIANCE,
        source_type=INTERNAL_SOURCE_TYPE_COOKING,
        electricity_to_heat_fraction=1.0,
        sensible_heat_fraction=0.85,
        latent_heat_fraction=0.15,
        moisture_generation_kg_h=0.20,
        noise_source_db=50.0,
        prefer_default_zone_role_when_target_is_current=True,
    ),
    "make_hot_drink": ActionInternalSourceSpec(
        action_name="make_hot_drink",
        default_zone_role="kitchen",
        source_kind=INTERNAL_SOURCE_KIND_APPLIANCE,
        source_type=INTERNAL_SOURCE_TYPE_COOKING,
        electricity_to_heat_fraction=1.0,
        sensible_heat_fraction=0.90,
        latent_heat_fraction=0.10,
        moisture_generation_kg_h=0.03,
        noise_source_db=40.0,
        prefer_default_zone_role_when_target_is_current=True,
    ),
    "shower": ActionInternalSourceSpec(
        action_name="shower",
        default_zone_role="bathroom",
        source_kind=INTERNAL_SOURCE_KIND_ACTIVITY,
        source_type=INTERNAL_SOURCE_TYPE_SHOWER,
        electricity_to_heat_fraction=0.0,
        sensible_heat_fraction=0.0,
        latent_heat_fraction=0.0,
        moisture_generation_kg_h=1.20,
        noise_source_db=45.0,
        prefer_default_zone_role_when_target_is_current=True,
    ),
    "run_washing_machine": ActionInternalSourceSpec(
        action_name="run_washing_machine",
        default_zone_role="laundry",
        source_kind=INTERNAL_SOURCE_KIND_APPLIANCE,
        source_type=INTERNAL_SOURCE_TYPE_LAUNDRY,
        electricity_to_heat_fraction=0.90,
        sensible_heat_fraction=0.95,
        latent_heat_fraction=0.05,
        moisture_generation_kg_h=0.03,
        noise_source_db=55.0,
        prefer_default_zone_role_when_target_is_current=True,
    ),
    "use_laptop": ActionInternalSourceSpec(
        action_name="use_laptop",
        default_zone_role="work",
        source_kind=INTERNAL_SOURCE_KIND_APPLIANCE,
        source_type=INTERNAL_SOURCE_TYPE_LAPTOP,
        electricity_to_heat_fraction=1.0,
        sensible_heat_fraction=1.0,
        latent_heat_fraction=0.0,
        noise_source_db=25.0,
        prefer_default_zone_role_when_target_is_current=True,
    ),
    "watch_tv": ActionInternalSourceSpec(
        action_name="watch_tv",
        default_zone_role="living_room",
        source_kind=INTERNAL_SOURCE_KIND_APPLIANCE,
        source_type=INTERNAL_SOURCE_TYPE_TV,
        electricity_to_heat_fraction=1.0,
        sensible_heat_fraction=1.0,
        latent_heat_fraction=0.0,
        noise_source_db=45.0,
        prefer_default_zone_role_when_target_is_current=True,
    ),
    "listen_music": ActionInternalSourceSpec(
        action_name="listen_music",
        default_zone_role="living_room",
        source_kind=INTERNAL_SOURCE_KIND_APPLIANCE,
        source_type=INTERNAL_SOURCE_TYPE_MUSIC,
        electricity_to_heat_fraction=1.0,
        sensible_heat_fraction=1.0,
        latent_heat_fraction=0.0,
        noise_source_db=50.0,
        prefer_default_zone_role_when_target_is_current=True,
    ),
}


def get_action_internal_source_spec(
    action_name: str,
) -> ActionInternalSourceSpec:
    action_name = str(action_name).strip()

    return DEFAULT_ACTION_INTERNAL_SOURCE_SPECS.get(
        action_name,
        ActionInternalSourceSpec(
            action_name=action_name,
            default_zone_role="current",
            source_kind=INTERNAL_SOURCE_KIND_APPLIANCE,
            source_type=INTERNAL_SOURCE_TYPE_GENERIC,
            electricity_to_heat_fraction=1.0,
            sensible_heat_fraction=1.0,
            latent_heat_fraction=0.0,
            moisture_generation_kg_h=0.0,
            co2_generation_m3_h=0.0,
            noise_source_db=0.0,
        ),
    )


# ============================================================
# SOURCE RECORDS
# ============================================================

@dataclass
class InternalSourceRecord:
    """
    One internal source assigned to one physical zone.

    Can represent:
    - person source
    - appliance/action source
    - lighting source
    - HVAC source
    """

    zone_id: str

    source_kind: str = INTERNAL_SOURCE_KIND_GENERIC
    source_type: str = INTERNAL_SOURCE_TYPE_GENERIC
    source_id: str = ""

    actor_id: str = ""
    action_name: str = ""

    duration_minutes: float = 0.0

    power_w: float = 0.0
    electricity_wh: float = 0.0

    sensible_heat_w: float = 0.0
    sensible_heat_wh: float = 0.0

    latent_heat_w: float = 0.0
    latent_heat_wh: float = 0.0

    co2_generation_m3_h: float = 0.0
    moisture_generation_kg_h: float = 0.0

    noise_source_db: float = 0.0

    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("InternalSourceRecord.zone_id cannot be empty.")

        self.source_kind = _normalize_source_kind(self.source_kind)

        self.source_type = str(self.source_type).strip().lower()
        if not self.source_type:
            self.source_type = INTERNAL_SOURCE_TYPE_GENERIC

        self.actor_id = str(self.actor_id)
        self.action_name = str(self.action_name)

        self.duration_minutes = _non_negative_float(
            self.duration_minutes,
            "duration_minutes",
            self.zone_id,
        )

        self.power_w = _non_negative_float(
            self.power_w,
            "power_w",
            self.zone_id,
        )

        self.electricity_wh = _non_negative_float(
            self.electricity_wh,
            "electricity_wh",
            self.zone_id,
        )

        self.sensible_heat_w = float(self.sensible_heat_w)
        self.sensible_heat_wh = float(self.sensible_heat_wh)

        self.latent_heat_w = float(self.latent_heat_w)
        self.latent_heat_wh = float(self.latent_heat_wh)

        if self.sensible_heat_w == 0.0 and self.sensible_heat_wh != 0.0:
            self.sensible_heat_w = _average_power_from_energy_wh(
                energy_wh=self.sensible_heat_wh,
                dt_minutes=self.duration_minutes,
            )

        if self.sensible_heat_wh == 0.0 and self.sensible_heat_w != 0.0:
            self.sensible_heat_wh = _energy_wh_from_average_power(
                power_w=self.sensible_heat_w,
                dt_minutes=self.duration_minutes,
            )

        if self.latent_heat_w == 0.0 and self.latent_heat_wh != 0.0:
            self.latent_heat_w = _average_power_from_energy_wh(
                energy_wh=self.latent_heat_wh,
                dt_minutes=self.duration_minutes,
            )

        if self.latent_heat_wh == 0.0 and self.latent_heat_w != 0.0:
            self.latent_heat_wh = _energy_wh_from_average_power(
                power_w=self.latent_heat_w,
                dt_minutes=self.duration_minutes,
            )

        self.co2_generation_m3_h = _non_negative_float(
            self.co2_generation_m3_h,
            "co2_generation_m3_h",
            self.zone_id,
        )

        self.moisture_generation_kg_h = _non_negative_float(
            self.moisture_generation_kg_h,
            "moisture_generation_kg_h",
            self.zone_id,
        )

        self.noise_source_db = _non_negative_float(
            self.noise_source_db,
            "noise_source_db",
            self.zone_id,
        )

        if self.metadata is None:
            self.metadata = {}

        if not isinstance(self.metadata, dict):
            self.metadata = dict(self.metadata)

        if not self.source_id:
            parts = [
                self.source_kind,
                self.source_type,
                self.actor_id,
                self.action_name,
                self.zone_id,
            ]

            self.source_id = "_".join(
                [
                    str(part)
                    for part in parts
                    if str(part).strip()
                ]
            )

        if not self.source:
            self.source = "internal_source_bridge"

    def moisture_generation_kg(self) -> float:
        return moisture_generation_kg_from_rate(
            moisture_generation_kg_h=self.moisture_generation_kg_h,
            duration_minutes=self.duration_minutes,
        )

    def co2_generation_m3(self) -> float:
        return (
            self.co2_generation_m3_h
            * self.duration_minutes
            / 60.0
        )
    def copy(self, **updates: Any) -> "InternalSourceRecord":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "zone_id": self.zone_id,
            "source_kind": self.source_kind,
            "source_type": self.source_type,
            "actor_id": self.actor_id,
            "action_name": self.action_name,
            "duration_minutes": self.duration_minutes,
            "power_w": self.power_w,
            "electricity_wh": self.electricity_wh,
            "sensible_heat_w": self.sensible_heat_w,
            "sensible_heat_wh": self.sensible_heat_wh,
            "latent_heat_w": self.latent_heat_w,
            "latent_heat_wh": self.latent_heat_wh,
            "co2_generation_m3_h": self.co2_generation_m3_h,
            "moisture_generation_kg_h": self.moisture_generation_kg_h,
            "moisture_generation_kg": self.moisture_generation_kg(),
            "co2_generation_m3": self.co2_generation_m3(),
            "noise_source_db": self.noise_source_db,
            "source": self.source,
            "metadata": dict(self.metadata),
        }


@dataclass
class ZoneInternalSourceSummary:
    """
    Aggregated internal sources for one zone.
    """

    zone_id: str
    records: List[InternalSourceRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneInternalSourceSummary.zone_id cannot be empty.")

        cleaned = []

        for record in self.records:
            if not isinstance(record, InternalSourceRecord):
                raise TypeError(
                    "ZoneInternalSourceSummary.records must contain InternalSourceRecord objects."
                )

            if record.zone_id != self.zone_id:
                raise ValueError(
                    "Record zone_id "
                    + record.zone_id
                    + " does not match summary zone_id "
                    + self.zone_id
                )

            cleaned.append(record)

        self.records = cleaned

    def records_by_kind(
        self,
        source_kind: str,
    ) -> List[InternalSourceRecord]:
        source_kind = _normalize_source_kind(source_kind)

        return [
            record
            for record in self.records
            if record.source_kind == source_kind
        ]

    def electricity_wh(self) -> float:
        return sum(record.electricity_wh for record in self.records)

    def sensible_heat_w(self) -> float:
        return sum(record.sensible_heat_w for record in self.records)

    def sensible_heat_wh(self) -> float:
        return sum(record.sensible_heat_wh for record in self.records)

    def latent_heat_w(self) -> float:
        return sum(record.latent_heat_w for record in self.records)

    def latent_heat_wh(self) -> float:
        return sum(record.latent_heat_wh for record in self.records)

    def people_sensible_heat_w(self) -> float:
        return sum(
            record.sensible_heat_w
            for record in self.records_by_kind(INTERNAL_SOURCE_KIND_PERSON)
        )

    def appliance_sensible_heat_w(self) -> float:
        return sum(
            record.sensible_heat_w
            for record in self.records_by_kind(INTERNAL_SOURCE_KIND_APPLIANCE)
        )

    def activity_sensible_heat_w(self) -> float:
        return sum(
            record.sensible_heat_w
            for record in self.records_by_kind(INTERNAL_SOURCE_KIND_ACTIVITY)
        )

    def appliance_and_activity_sensible_heat_w(self) -> float:
        return (
            self.appliance_sensible_heat_w()
            + self.activity_sensible_heat_w()
        )

    def appliance_records(self) -> List[InternalSourceRecord]:
        return self.records_by_kind(INTERNAL_SOURCE_KIND_APPLIANCE)

    def appliance_power_w(self) -> float:
        return sum(
            record.power_w
            for record in self.appliance_records()
        )

    def appliance_total_heat_w(self) -> float:
        return sum(
            record.sensible_heat_w + record.latent_heat_w
            for record in self.appliance_records()
        )

    def appliance_total_heat_wh(self) -> float:
        return sum(
            record.sensible_heat_wh + record.latent_heat_wh
            for record in self.appliance_records()
        )

    def appliance_latent_heat_w(self) -> float:
        return sum(
            record.latent_heat_w
            for record in self.appliance_records()
        )

    def appliance_latent_heat_wh(self) -> float:
        return sum(
            record.latent_heat_wh
            for record in self.appliance_records()
        )

    def appliance_electricity_by_source_type_wh(self) -> Dict[str, float]:
        out = {}

        for record in self.appliance_records():
            out[record.source_type] = (
                out.get(record.source_type, 0.0)
                + record.electricity_wh
            )

        return out

    def appliance_sensible_heat_by_source_type_w(self) -> Dict[str, float]:
        out = {}

        for record in self.appliance_records():
            out[record.source_type] = (
                out.get(record.source_type, 0.0)
                + record.sensible_heat_w
            )

        return out
    
    def lighting_sensible_heat_w(self) -> float:
        return sum(
            record.sensible_heat_w
            for record in self.records_by_kind(INTERNAL_SOURCE_KIND_LIGHTING)
        )

    def hvac_sensible_gain_w(self) -> float:
        return sum(
            record.sensible_heat_w
            for record in self.records_by_kind(INTERNAL_SOURCE_KIND_HVAC)
        )

    def hvac_records(self):
        return self.records_by_kind(INTERNAL_SOURCE_KIND_HVAC)

    def hvac_electricity_wh(self):
        return sum(
            record.electricity_wh
            for record in self.hvac_records()
        )

    def hvac_heating_gain_w(self):
        return sum(
            max(0.0, record.sensible_heat_w)
            for record in self.hvac_records()
        )

    def hvac_cooling_gain_w(self):
        return sum(
            min(0.0, record.sensible_heat_w)
            for record in self.hvac_records()
        )

    def hvac_cooling_removal_w(self):
        return -self.hvac_cooling_gain_w()
    
    def appliance_electricity_wh(self) -> float:
        return sum(
            record.electricity_wh
            for record in self.records_by_kind(INTERNAL_SOURCE_KIND_APPLIANCE)
        )

    def lighting_electricity_wh(self) -> float:
        return sum(
            record.electricity_wh
            for record in self.records_by_kind(INTERNAL_SOURCE_KIND_LIGHTING)
        )

    def co2_generation_m3_h(self) -> float:
        return sum(record.co2_generation_m3_h for record in self.records)

    def moisture_generation_kg_h(self) -> float:
        return sum(record.moisture_generation_kg_h for record in self.records)
    
    def moisture_records(self) -> List[InternalSourceRecord]:
        return [
            record
            for record in self.records
            if internal_source_record_is_moisture_source(record)
        ]

    def moisture_generation_kg(self) -> float:
        return sum(
            record.moisture_generation_kg()
            for record in self.moisture_records()
        )

    def average_moisture_generation_kg_h(
        self,
        dt_minutes: float,
    ) -> float:
        return average_moisture_generation_kg_h_from_mass(
            moisture_generation_kg=self.moisture_generation_kg(),
            dt_minutes=dt_minutes,
        )

    def moisture_generation_by_source_type_kg(self) -> Dict[str, float]:
        out = {}

        for record in self.moisture_records():
            out[record.source_type] = (
                out.get(record.source_type, 0.0)
                + record.moisture_generation_kg()
            )

        return out

    def moisture_generation_by_source_type_kg_h_raw(self) -> Dict[str, float]:
        """
        Raw active-source rates, not duration-weighted over the timestep.
        Use average_moisture_generation_kg_h() for timestep coupling.
        """
        out = {}

        for record in self.moisture_records():
            out[record.source_type] = (
                out.get(record.source_type, 0.0)
                + record.moisture_generation_kg_h
            )

        return out

    def cooking_moisture_generation_kg(self) -> float:
        return self.moisture_generation_by_source_type_kg().get(
            INTERNAL_SOURCE_TYPE_COOKING,
            0.0,
        )

    def shower_moisture_generation_kg(self) -> float:
        return self.moisture_generation_by_source_type_kg().get(
            INTERNAL_SOURCE_TYPE_SHOWER,
            0.0,
        )

    def laundry_moisture_generation_kg(self) -> float:
        return self.moisture_generation_by_source_type_kg().get(
            INTERNAL_SOURCE_TYPE_LAUNDRY,
            0.0,
        )

    def noise_sources_db(self) -> List[float]:
        return [
            record.noise_source_db
            for record in self.records
            if record.noise_source_db > 0.0
        ]
    
    def records_by_source_kind(self):
        return aggregate_records_by_kind(self.records)

    def records_by_source_type(self):
        return aggregate_records_by_source_type(self.records)

    def record_count_by_source_kind(self):
        return {
            source_kind: len(records)
            for source_kind, records in self.records_by_source_kind().items()
        }

    def electricity_wh_by_source_kind(self):
        out = {}

        for source_kind, records in self.records_by_source_kind().items():
            out[source_kind] = sum(
                record.electricity_wh
                for record in records
            )

        return out

    def sensible_heat_wh_by_source_kind(self):
        out = {}

        for source_kind, records in self.records_by_source_kind().items():
            out[source_kind] = sum(
                record.sensible_heat_wh
                for record in records
            )

        return out

    def latent_heat_wh_by_source_kind(self):
        out = {}

        for source_kind, records in self.records_by_source_kind().items():
            out[source_kind] = sum(
                record.latent_heat_wh
                for record in records
            )

        return out

    def co2_generation_m3_by_source_kind(self):
        out = {}

        for source_kind, records in self.records_by_source_kind().items():
            out[source_kind] = sum(
                record.co2_generation_m3()
                for record in records
            )

        return out

    def moisture_generation_kg_by_source_kind(self):
        out = {}

        for source_kind, records in self.records_by_source_kind().items():
            out[source_kind] = sum(
                record.moisture_generation_kg()
                for record in records
            )

        return out

    def average_electricity_power_w(
        self,
        dt_minutes,
    ):
        return average_rate_from_quantity_over_timestep(
            quantity=self.electricity_wh(),
            dt_minutes=dt_minutes,
        )

    def average_sensible_heat_w(
        self,
        dt_minutes,
    ):
        return average_rate_from_quantity_over_timestep(
            quantity=self.sensible_heat_wh(),
            dt_minutes=dt_minutes,
        )

    def average_latent_heat_w(
        self,
        dt_minutes,
    ):
        return average_rate_from_quantity_over_timestep(
            quantity=self.latent_heat_wh(),
            dt_minutes=dt_minutes,
        )

    def average_electricity_power_w_by_source_kind(
        self,
        dt_minutes,
    ):
        return {
            source_kind: average_rate_from_quantity_over_timestep(
                quantity=electricity_wh,
                dt_minutes=dt_minutes,
            )
            for source_kind, electricity_wh
            in self.electricity_wh_by_source_kind().items()
        }

    def average_sensible_heat_w_by_source_kind(
        self,
        dt_minutes,
    ):
        return {
            source_kind: average_rate_from_quantity_over_timestep(
                quantity=sensible_heat_wh,
                dt_minutes=dt_minutes,
            )
            for source_kind, sensible_heat_wh
            in self.sensible_heat_wh_by_source_kind().items()
        }

    def average_latent_heat_w_by_source_kind(
        self,
        dt_minutes,
    ):
        return {
            source_kind: average_rate_from_quantity_over_timestep(
                quantity=latent_heat_wh,
                dt_minutes=dt_minutes,
            )
            for source_kind, latent_heat_wh
            in self.latent_heat_wh_by_source_kind().items()
        }

    def co2_generation_m3(self):
        return sum(
            record.co2_generation_m3()
            for record in self.records
        )

    def average_co2_generation_m3_h(
        self,
        dt_minutes,
    ):
        return average_rate_from_quantity_over_timestep(
            quantity=self.co2_generation_m3(),
            dt_minutes=dt_minutes,
        )

    def average_co2_generation_m3_h_by_source_kind(
        self,
        dt_minutes,
    ):
        return {
            source_kind: average_rate_from_quantity_over_timestep(
                quantity=co2_m3,
                dt_minutes=dt_minutes,
            )
            for source_kind, co2_m3
            in self.co2_generation_m3_by_source_kind().items()
        }

    def average_moisture_generation_kg_h_by_source_kind(
        self,
        dt_minutes,
    ):
        return {
            source_kind: average_rate_from_quantity_over_timestep(
                quantity=moisture_kg,
                dt_minutes=dt_minutes,
            )
            for source_kind, moisture_kg
            in self.moisture_generation_kg_by_source_kind().items()
        }

    def aggregate_dict(
        self,
        dt_minutes,
    ):
        return {
            "zone_id": self.zone_id,
            "record_count": len(self.records),
            "record_count_by_source_kind": self.record_count_by_source_kind(),

            "electricity_wh": self.electricity_wh(),
            "average_electricity_power_w": self.average_electricity_power_w(
                dt_minutes=dt_minutes,
            ),

            "sensible_heat_wh": self.sensible_heat_wh(),
            "average_sensible_heat_w": self.average_sensible_heat_w(
                dt_minutes=dt_minutes,
            ),

            "latent_heat_wh": self.latent_heat_wh(),
            "average_latent_heat_w": self.average_latent_heat_w(
                dt_minutes=dt_minutes,
            ),

            "co2_generation_m3": self.co2_generation_m3(),
            "average_co2_generation_m3_h": self.average_co2_generation_m3_h(
                dt_minutes=dt_minutes,
            ),

            "moisture_generation_kg": self.moisture_generation_kg(),
            "average_moisture_generation_kg_h": self.average_moisture_generation_kg_h(
                dt_minutes=dt_minutes,
            ),

            "electricity_wh_by_source_kind": self.electricity_wh_by_source_kind(),
            "sensible_heat_wh_by_source_kind": self.sensible_heat_wh_by_source_kind(),
            "latent_heat_wh_by_source_kind": self.latent_heat_wh_by_source_kind(),
            "co2_generation_m3_by_source_kind": self.co2_generation_m3_by_source_kind(),
            "moisture_generation_kg_by_source_kind": self.moisture_generation_kg_by_source_kind(),

            "average_electricity_power_w_by_source_kind": self.average_electricity_power_w_by_source_kind(
                dt_minutes=dt_minutes,
            ),
            "average_sensible_heat_w_by_source_kind": self.average_sensible_heat_w_by_source_kind(
                dt_minutes=dt_minutes,
            ),
            "average_latent_heat_w_by_source_kind": self.average_latent_heat_w_by_source_kind(
                dt_minutes=dt_minutes,
            ),
            "average_co2_generation_m3_h_by_source_kind": self.average_co2_generation_m3_h_by_source_kind(
                dt_minutes=dt_minutes,
            ),
            "average_moisture_generation_kg_h_by_source_kind": self.average_moisture_generation_kg_h_by_source_kind(
                dt_minutes=dt_minutes,
            ),

            "noise_sources_db": self.noise_sources_db(),
        }

    def copy(self, **updates: Any) -> "ZoneInternalSourceSummary":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "record_count": len(self.records),
            "electricity_wh": self.electricity_wh(),
            "sensible_heat_w": self.sensible_heat_w(),
            "sensible_heat_wh": self.sensible_heat_wh(),
            "latent_heat_w": self.latent_heat_w(),
            "latent_heat_wh": self.latent_heat_wh(),
            "people_sensible_heat_w": self.people_sensible_heat_w(),
            "appliance_sensible_heat_w": self.appliance_sensible_heat_w(),
            "activity_sensible_heat_w": self.activity_sensible_heat_w(),
            "appliance_and_activity_sensible_heat_w": self.appliance_and_activity_sensible_heat_w(),
            "appliance_power_w": self.appliance_power_w(),
            "appliance_total_heat_w": self.appliance_total_heat_w(),
            "appliance_total_heat_wh": self.appliance_total_heat_wh(),
            "appliance_latent_heat_w": self.appliance_latent_heat_w(),
            "appliance_latent_heat_wh": self.appliance_latent_heat_wh(),
            "appliance_electricity_by_source_type_wh": self.appliance_electricity_by_source_type_wh(),
            "appliance_sensible_heat_by_source_type_w": self.appliance_sensible_heat_by_source_type_w(),
            "lighting_sensible_heat_w": self.lighting_sensible_heat_w(),
            "hvac_sensible_gain_w": self.hvac_sensible_gain_w(),
            "hvac_electricity_wh": self.hvac_electricity_wh(),
            "hvac_heating_gain_w": self.hvac_heating_gain_w(),
            "hvac_cooling_gain_w": self.hvac_cooling_gain_w(),
            "hvac_cooling_removal_w": self.hvac_cooling_removal_w(),
            "appliance_electricity_wh": self.appliance_electricity_wh(),
            "lighting_electricity_wh": self.lighting_electricity_wh(),
            "co2_generation_m3_h": self.co2_generation_m3_h(),
            "moisture_generation_kg_h": self.moisture_generation_kg_h(),
            "moisture_generation_kg": self.moisture_generation_kg(),
            "moisture_generation_by_source_type_kg": self.moisture_generation_by_source_type_kg(),
            "moisture_generation_by_source_type_kg_h_raw": self.moisture_generation_by_source_type_kg_h_raw(),
            "cooking_moisture_generation_kg": self.cooking_moisture_generation_kg(),
            "shower_moisture_generation_kg": self.shower_moisture_generation_kg(),
            "laundry_moisture_generation_kg": self.laundry_moisture_generation_kg(),
            "noise_sources_db": self.noise_sources_db(),
            "record_count_by_source_kind": self.record_count_by_source_kind(),
            "electricity_wh_by_source_kind": self.electricity_wh_by_source_kind(),
            "sensible_heat_wh_by_source_kind": self.sensible_heat_wh_by_source_kind(),
            "latent_heat_wh_by_source_kind": self.latent_heat_wh_by_source_kind(),
            "co2_generation_m3": self.co2_generation_m3(),
            "co2_generation_m3_by_source_kind": self.co2_generation_m3_by_source_kind(),
            "moisture_generation_kg_by_source_kind": self.moisture_generation_kg_by_source_kind(),
            "records": [
                record.to_dict()
                for record in self.records
            ],
        }


@dataclass
class BuildingInternalSourceResult:
    """
    Building-level internal source result for one timestep.

    This is the Phase 9 bridge object.
    """

    records: List[InternalSourceRecord] = field(default_factory=list)
    expected_zone_ids: List[str] = field(default_factory=list)

    dt_minutes: float = DEFAULT_INTERNAL_SOURCE_DT_MINUTES
    source: str = INTERNAL_SOURCE_RESULT_SOURCE

    def __post_init__(self) -> None:
        self.dt_minutes = _non_negative_float(
            self.dt_minutes,
            "dt_minutes",
            "BuildingInternalSourceResult",
        )

        cleaned = []

        for record in self.records:
            if not isinstance(record, InternalSourceRecord):
                raise TypeError(
                    "BuildingInternalSourceResult.records must contain InternalSourceRecord objects."
                )

            cleaned.append(record)

        self.records = cleaned

        if self.expected_zone_ids is None:
            self.expected_zone_ids = []

        self.expected_zone_ids = [
            str(zone_id)
            for zone_id in self.expected_zone_ids
            if str(zone_id).strip()
        ]

    def all_zone_ids(self) -> List[str]:
        out = []

        for zone_id in self.expected_zone_ids:
            if zone_id not in out:
                out.append(zone_id)

        for record in self.records:
            if record.zone_id not in out:
                out.append(record.zone_id)

        return out

    def records_for_zone(
        self,
        zone_id: str,
    ) -> List[InternalSourceRecord]:
        return [
            record
            for record in self.records
            if record.zone_id == zone_id
        ]

    def records_by_zone(self) -> Dict[str, List[InternalSourceRecord]]:
        return {
            zone_id: self.records_for_zone(zone_id)
            for zone_id in self.all_zone_ids()
        }

    def summary_for_zone(
        self,
        zone_id: str,
    ) -> ZoneInternalSourceSummary:
        return ZoneInternalSourceSummary(
            zone_id=zone_id,
            records=self.records_for_zone(zone_id),
        )

    def summaries_by_zone(self) -> Dict[str, ZoneInternalSourceSummary]:
        return {
            zone_id: self.summary_for_zone(zone_id)
            for zone_id in self.all_zone_ids()
        }

    def total_electricity_wh_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.electricity_wh()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def appliance_electricity_wh_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.appliance_electricity_wh()
            for zone_id, summary in self.summaries_by_zone().items()
        }
    
    def appliance_records(self) -> List[InternalSourceRecord]:
        return [
            record
            for record in self.records
            if record.source_kind == INTERNAL_SOURCE_KIND_APPLIANCE
        ]

    def appliance_records_by_zone(self) -> Dict[str, List[InternalSourceRecord]]:
        return {
            zone_id: [
                record
                for record in self.records_for_zone(zone_id)
                if record.source_kind == INTERNAL_SOURCE_KIND_APPLIANCE
            ]
            for zone_id in self.all_zone_ids()
        }

    def appliance_power_w_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.appliance_power_w()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def appliance_total_heat_w_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.appliance_total_heat_w()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def appliance_total_heat_wh_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.appliance_total_heat_wh()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def appliance_latent_heat_w_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.appliance_latent_heat_w()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def appliance_latent_heat_wh_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.appliance_latent_heat_wh()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def appliance_electricity_by_source_type_wh(self) -> Dict[str, float]:
        out = {}

        for record in self.appliance_records():
            out[record.source_type] = (
                out.get(record.source_type, 0.0)
                + record.electricity_wh
            )

        return out

    def appliance_sensible_heat_by_source_type_w(self) -> Dict[str, float]:
        out = {}

        for record in self.appliance_records():
            out[record.source_type] = (
                out.get(record.source_type, 0.0)
                + record.sensible_heat_w
            )

        return out

    def total_appliance_electricity_wh(self) -> float:
        return sum(
            record.electricity_wh
            for record in self.appliance_records()
        )

    def total_appliance_sensible_heat_w(self) -> float:
        return sum(
            record.sensible_heat_w
            for record in self.appliance_records()
        )

    def total_appliance_heat_w(self) -> float:
        return sum(
            record.sensible_heat_w + record.latent_heat_w
            for record in self.appliance_records()
        )

    def lighting_electricity_wh_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.lighting_electricity_wh()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def total_sensible_heat_w_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.sensible_heat_w()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def people_sensible_heat_w_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.people_sensible_heat_w()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def appliance_sensible_heat_w_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.appliance_sensible_heat_w()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def activity_sensible_heat_w_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.activity_sensible_heat_w()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def appliance_and_activity_sensible_heat_w_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.appliance_and_activity_sensible_heat_w()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def lighting_sensible_heat_w_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.lighting_sensible_heat_w()
            for zone_id, summary in self.summaries_by_zone().items()
        }
    
    def lighting_records(self):
        return [
            record
            for record in self.records
            if record.source_kind == INTERNAL_SOURCE_KIND_LIGHTING
        ]

    def lighting_power_w_by_zone(self):
        return {
            zone_id: sum(record.power_w for record in records)
            for zone_id, records in self._records_by_zone_and_kind(
                INTERNAL_SOURCE_KIND_LIGHTING
            ).items()
        }

    def total_lighting_electricity_wh(self):
        return sum(
            record.electricity_wh
            for record in self.lighting_records()
        )

    def total_lighting_sensible_heat_w(self):
        return sum(
            record.sensible_heat_w
            for record in self.lighting_records()
        )

    def _records_by_zone_and_kind(self, source_kind):
        source_kind = _normalize_source_kind(source_kind)

        out = {
            zone_id: []
            for zone_id in self.all_zone_ids()
        }

        for record in self.records:
            if record.source_kind != source_kind:
                continue

            if record.zone_id not in out:
                out[record.zone_id] = []

            out[record.zone_id].append(record)

        return out

    def hvac_sensible_gain_w_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.hvac_sensible_gain_w()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def total_latent_heat_w_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.latent_heat_w()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def co2_generation_m3_h_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.co2_generation_m3_h()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def co2_generation_m3_s_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: value / 3600.0
            for zone_id, value in self.co2_generation_m3_h_by_zone().items()
        }

    def moisture_generation_kg_h_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.moisture_generation_kg_h()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def moisture_generation_kg_s_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: value / 3600.0
            for zone_id, value in self.moisture_generation_kg_h_by_zone().items()
        }
    
    def moisture_records(self) -> List[InternalSourceRecord]:
        return [
            record
            for record in self.records
            if internal_source_record_is_moisture_source(record)
        ]

    def moisture_generation_kg_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.moisture_generation_kg()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def average_moisture_generation_kg_h_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.average_moisture_generation_kg_h(
                dt_minutes=self.dt_minutes
            )
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def moisture_generation_by_source_type_kg(self) -> Dict[str, float]:
        out = {}

        for record in self.moisture_records():
            out[record.source_type] = (
                out.get(record.source_type, 0.0)
                + record.moisture_generation_kg()
            )

        return out

    def average_moisture_generation_by_source_type_kg_h(self) -> Dict[str, float]:
        out = {}

        for source_type, moisture_kg in self.moisture_generation_by_source_type_kg().items():
            out[source_type] = average_moisture_generation_kg_h_from_mass(
                moisture_generation_kg=moisture_kg,
                dt_minutes=self.dt_minutes,
            )

        return out

    def cooking_moisture_generation_kg_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.cooking_moisture_generation_kg()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def shower_moisture_generation_kg_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.shower_moisture_generation_kg()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def laundry_moisture_generation_kg_by_zone(self) -> Dict[str, float]:
        return {
            zone_id: summary.laundry_moisture_generation_kg()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def total_moisture_generation_kg(self) -> float:
        return sum(
            record.moisture_generation_kg()
            for record in self.moisture_records()
        )

    def average_total_moisture_generation_kg_h(self) -> float:
        return average_moisture_generation_kg_h_from_mass(
            moisture_generation_kg=self.total_moisture_generation_kg(),
            dt_minutes=self.dt_minutes,
        )

    def hvac_records(self):
        return [
            record
            for record in self.records
            if record.source_kind == INTERNAL_SOURCE_KIND_HVAC
        ]

    def hvac_electricity_wh_by_zone(self):
        return {
            zone_id: summary.hvac_electricity_wh()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def hvac_heating_gain_w_by_zone(self):
        return {
            zone_id: summary.hvac_heating_gain_w()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def hvac_cooling_gain_w_by_zone(self):
        return {
            zone_id: summary.hvac_cooling_gain_w()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def hvac_cooling_removal_w_by_zone(self):
        return {
            zone_id: summary.hvac_cooling_removal_w()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def total_hvac_electricity_wh(self):
        return sum(
            record.electricity_wh
            for record in self.hvac_records()
        )

    def total_hvac_heating_gain_w(self):
        return sum(
            max(0.0, record.sensible_heat_w)
            for record in self.hvac_records()
        )

    def total_hvac_cooling_removal_w(self):
        return sum(
            max(0.0, -record.sensible_heat_w)
            for record in self.hvac_records()
        )
    
    def moisture_source_input_dicts_by_zone(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Pure-dict adapter for moisture.py.

        Does not import moisture.py to avoid coupling.
        Later 9.9 can convert these dictionaries into
        ZoneMoistureSourceInput / BuildingMoistureSourceInputs.
        """

        out = {}

        for zone_id in self.all_zone_ids():
            summary = self.summary_for_zone(zone_id)

            moisture_by_type_kg = summary.moisture_generation_by_source_type_kg()

            zone_sources = []

            for source_type, moisture_kg in moisture_by_type_kg.items():
                average_kg_h = average_moisture_generation_kg_h_from_mass(
                    moisture_generation_kg=moisture_kg,
                    dt_minutes=self.dt_minutes,
                )

                if average_kg_h <= 0.0:
                    continue

                zone_sources.append(
                    {
                        "zone_id": zone_id,
                        "moisture_generation_kg_h": average_kg_h,
                        "source_type": source_type,
                        "source": MOISTURE_SOURCE_MODE_ACTION_DURATION_WEIGHTED,
                    }
                )

            out[zone_id] = zone_sources

        return out

    def noise_sources_by_zone(self) -> Dict[str, List[float]]:
        return {
            zone_id: summary.noise_sources_db()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def total_electricity_wh(self) -> float:
        return sum(record.electricity_wh for record in self.records)

    def total_sensible_heat_w(self) -> float:
        return sum(record.sensible_heat_w for record in self.records)

    def total_co2_generation_m3_h(self) -> float:
        return sum(record.co2_generation_m3_h for record in self.records)

    def total_moisture_generation_kg_h(self) -> float:
        return sum(record.moisture_generation_kg_h for record in self.records)
    
    def aggregate_dict_by_zone(self):
        return {
            zone_id: summary.aggregate_dict(
                dt_minutes=self.dt_minutes
            )
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def aggregate_rows_by_zone(self):
        return [
            row
            for row in self.aggregate_dict_by_zone().values()
        ]

    def average_electricity_power_w_by_zone(self):
        return {
            zone_id: summary.average_electricity_power_w(
                dt_minutes=self.dt_minutes
            )
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def average_sensible_heat_w_by_zone(self):
        return {
            zone_id: summary.average_sensible_heat_w(
                dt_minutes=self.dt_minutes
            )
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def average_latent_heat_w_by_zone(self):
        return {
            zone_id: summary.average_latent_heat_w(
                dt_minutes=self.dt_minutes
            )
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def co2_generation_m3_by_zone(self):
        return {
            zone_id: summary.co2_generation_m3()
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def average_co2_generation_m3_h_by_zone(self):
        return {
            zone_id: summary.average_co2_generation_m3_h(
                dt_minutes=self.dt_minutes
            )
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def average_electricity_power_w_by_zone_and_kind(self):
        return {
            zone_id: summary.average_electricity_power_w_by_source_kind(
                dt_minutes=self.dt_minutes
            )
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def average_sensible_heat_w_by_zone_and_kind(self):
        return {
            zone_id: summary.average_sensible_heat_w_by_source_kind(
                dt_minutes=self.dt_minutes
            )
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def average_latent_heat_w_by_zone_and_kind(self):
        return {
            zone_id: summary.average_latent_heat_w_by_source_kind(
                dt_minutes=self.dt_minutes
            )
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def average_co2_generation_m3_h_by_zone_and_kind(self):
        return {
            zone_id: summary.average_co2_generation_m3_h_by_source_kind(
                dt_minutes=self.dt_minutes
            )
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def average_moisture_generation_kg_h_by_zone_and_kind(self):
        return {
            zone_id: summary.average_moisture_generation_kg_h_by_source_kind(
                dt_minutes=self.dt_minutes
            )
            for zone_id, summary in self.summaries_by_zone().items()
        }

    def physics_bridge_inputs_by_zone(self):
        """
        Canonical Phase 9.8 aggregate output.

        This is the object later phases should consume:
        - thermal uses average_sensible_heat_w
        - airflow/CO2 uses average_co2_generation_m3_h
        - moisture uses average_moisture_generation_kg_h
        - electricity/output uses average_electricity_power_w or electricity_wh
        """

        out = {}

        for zone_id, summary in self.summaries_by_zone().items():
            out[zone_id] = {
                "zone_id": zone_id,
                "dt_minutes": self.dt_minutes,

                "average_sensible_heat_w": summary.average_sensible_heat_w(
                    dt_minutes=self.dt_minutes,
                ),
                "average_latent_heat_w": summary.average_latent_heat_w(
                    dt_minutes=self.dt_minutes,
                ),
                "average_electricity_power_w": summary.average_electricity_power_w(
                    dt_minutes=self.dt_minutes,
                ),
                "electricity_wh": summary.electricity_wh(),

                "average_co2_generation_m3_h": summary.average_co2_generation_m3_h(
                    dt_minutes=self.dt_minutes,
                ),
                "average_moisture_generation_kg_h": summary.average_moisture_generation_kg_h(
                    dt_minutes=self.dt_minutes,
                ),

                "average_sensible_heat_w_by_source_kind": summary.average_sensible_heat_w_by_source_kind(
                    dt_minutes=self.dt_minutes,
                ),
                "average_electricity_power_w_by_source_kind": summary.average_electricity_power_w_by_source_kind(
                    dt_minutes=self.dt_minutes,
                ),
                "average_co2_generation_m3_h_by_source_kind": summary.average_co2_generation_m3_h_by_source_kind(
                    dt_minutes=self.dt_minutes,
                ),
                "average_moisture_generation_kg_h_by_source_kind": summary.average_moisture_generation_kg_h_by_source_kind(
                    dt_minutes=self.dt_minutes,
                ),

                "record_count": len(summary.records),
                "record_count_by_source_kind": summary.record_count_by_source_kind(),
            }

        return out

    def total_average_electricity_power_w(self):
        return average_rate_from_quantity_over_timestep(
            quantity=self.total_electricity_wh(),
            dt_minutes=self.dt_minutes,
        )

    def total_average_sensible_heat_w(self):
        return average_rate_from_quantity_over_timestep(
            quantity=sum(record.sensible_heat_wh for record in self.records),
            dt_minutes=self.dt_minutes,
        )

    def total_average_latent_heat_w(self):
        return average_rate_from_quantity_over_timestep(
            quantity=sum(record.latent_heat_wh for record in self.records),
            dt_minutes=self.dt_minutes,
        )

    def copy(self, **updates: Any) -> "BuildingInternalSourceResult":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "dt_minutes": self.dt_minutes,
            "zone_ids": self.all_zone_ids(),
            "record_count": len(self.records),
            "total_electricity_wh": self.total_electricity_wh(),
            "total_sensible_heat_w": self.total_sensible_heat_w(),
            "total_co2_generation_m3_h": self.total_co2_generation_m3_h(),
            "total_moisture_generation_kg_h": self.total_moisture_generation_kg_h(),
            "total_electricity_wh_by_zone": self.total_electricity_wh_by_zone(),
            "total_sensible_heat_w_by_zone": self.total_sensible_heat_w_by_zone(),
            "people_sensible_heat_w_by_zone": self.people_sensible_heat_w_by_zone(),
            "appliance_sensible_heat_w_by_zone": self.appliance_sensible_heat_w_by_zone(),
            "total_appliance_electricity_wh": self.total_appliance_electricity_wh(),
            "total_appliance_sensible_heat_w": self.total_appliance_sensible_heat_w(),
            "total_appliance_heat_w": self.total_appliance_heat_w(),
            "appliance_power_w_by_zone": self.appliance_power_w_by_zone(),
            "appliance_total_heat_w_by_zone": self.appliance_total_heat_w_by_zone(),
            "appliance_total_heat_wh_by_zone": self.appliance_total_heat_wh_by_zone(),
            "appliance_latent_heat_w_by_zone": self.appliance_latent_heat_w_by_zone(),
            "appliance_latent_heat_wh_by_zone": self.appliance_latent_heat_wh_by_zone(),
            "appliance_electricity_by_source_type_wh": self.appliance_electricity_by_source_type_wh(),
            "appliance_sensible_heat_by_source_type_w": self.appliance_sensible_heat_by_source_type_w(),
            "activity_sensible_heat_w_by_zone": self.activity_sensible_heat_w_by_zone(),
            "appliance_and_activity_sensible_heat_w_by_zone": self.appliance_and_activity_sensible_heat_w_by_zone(),
            "lighting_sensible_heat_w_by_zone": self.lighting_sensible_heat_w_by_zone(),
            "total_lighting_electricity_wh": self.total_lighting_electricity_wh(),
            "total_lighting_sensible_heat_w": self.total_lighting_sensible_heat_w(),
            "lighting_power_w_by_zone": self.lighting_power_w_by_zone(),
            "hvac_sensible_gain_w_by_zone": self.hvac_sensible_gain_w_by_zone(),
            "total_hvac_electricity_wh": self.total_hvac_electricity_wh(),
            "total_hvac_heating_gain_w": self.total_hvac_heating_gain_w(),
            "total_hvac_cooling_removal_w": self.total_hvac_cooling_removal_w(),
            "hvac_electricity_wh_by_zone": self.hvac_electricity_wh_by_zone(),
            "hvac_heating_gain_w_by_zone": self.hvac_heating_gain_w_by_zone(),
            "hvac_cooling_gain_w_by_zone": self.hvac_cooling_gain_w_by_zone(),
            "hvac_cooling_removal_w_by_zone": self.hvac_cooling_removal_w_by_zone(),
            "total_latent_heat_w_by_zone": self.total_latent_heat_w_by_zone(),
            "co2_generation_m3_h_by_zone": self.co2_generation_m3_h_by_zone(),
            "moisture_generation_kg_h_by_zone": self.moisture_generation_kg_h_by_zone(),
            "total_moisture_generation_kg": self.total_moisture_generation_kg(),
            "average_total_moisture_generation_kg_h": self.average_total_moisture_generation_kg_h(),
            "moisture_generation_kg_by_zone": self.moisture_generation_kg_by_zone(),
            "average_moisture_generation_kg_h_by_zone": self.average_moisture_generation_kg_h_by_zone(),
            "moisture_generation_by_source_type_kg": self.moisture_generation_by_source_type_kg(),
            "average_moisture_generation_by_source_type_kg_h": self.average_moisture_generation_by_source_type_kg_h(),
            "cooking_moisture_generation_kg_by_zone": self.cooking_moisture_generation_kg_by_zone(),
            "shower_moisture_generation_kg_by_zone": self.shower_moisture_generation_kg_by_zone(),
            "laundry_moisture_generation_kg_by_zone": self.laundry_moisture_generation_kg_by_zone(),
            "moisture_source_input_dicts_by_zone": self.moisture_source_input_dicts_by_zone(),
            "noise_sources_by_zone": self.noise_sources_by_zone(),
            "aggregation_mode": INTERNAL_SOURCE_AGGREGATION_MODE_TIMESTEP_AVERAGE,
            "total_average_electricity_power_w": self.total_average_electricity_power_w(),
            "total_average_sensible_heat_w": self.total_average_sensible_heat_w(),
            "total_average_latent_heat_w": self.total_average_latent_heat_w(),
            "average_electricity_power_w_by_zone": self.average_electricity_power_w_by_zone(),
            "average_sensible_heat_w_by_zone": self.average_sensible_heat_w_by_zone(),
            "average_latent_heat_w_by_zone": self.average_latent_heat_w_by_zone(),
            "co2_generation_m3_by_zone": self.co2_generation_m3_by_zone(),
            "average_co2_generation_m3_h_by_zone": self.average_co2_generation_m3_h_by_zone(),
            "average_electricity_power_w_by_zone_and_kind": self.average_electricity_power_w_by_zone_and_kind(),
            "average_sensible_heat_w_by_zone_and_kind": self.average_sensible_heat_w_by_zone_and_kind(),
            "average_latent_heat_w_by_zone_and_kind": self.average_latent_heat_w_by_zone_and_kind(),
            "average_co2_generation_m3_h_by_zone_and_kind": self.average_co2_generation_m3_h_by_zone_and_kind(),
            "average_moisture_generation_kg_h_by_zone_and_kind": self.average_moisture_generation_kg_h_by_zone_and_kind(),
            "physics_bridge_inputs_by_zone": self.physics_bridge_inputs_by_zone(),
            "aggregate_dict_by_zone": self.aggregate_dict_by_zone(),
            "records": [
                record.to_dict()
                for record in self.records
            ],
        }


# ============================================================
# ZONE RESOLUTION
# ============================================================

OUTSIDE_ZONE_ID = "outside"

INTERNAL_SOURCE_ZONE_RESOLUTION_DIRECT_TARGET_SPACE = "direct_target_space_id"
INTERNAL_SOURCE_ZONE_RESOLUTION_TARGET_SPACE_AS_ROLE = "target_space_id_interpreted_as_role"
INTERNAL_SOURCE_ZONE_RESOLUTION_TARGET_ROLE = "target_zone_role"
INTERNAL_SOURCE_ZONE_RESOLUTION_ACTION_DEFAULT_ROLE = "action_default_zone_role"
INTERNAL_SOURCE_ZONE_RESOLUTION_ACTION_DEFAULT_ROLE_OVER_CURRENT = "action_default_zone_role_over_current_target"
INTERNAL_SOURCE_ZONE_RESOLUTION_ACTOR_LOCATION = "actor_current_location"
INTERNAL_SOURCE_ZONE_RESOLUTION_FIRST_BUILDING_ZONE = "first_building_zone"
INTERNAL_SOURCE_ZONE_RESOLUTION_UNRESOLVED = "unresolved"


INTERNAL_SOURCE_ROLE_TO_ZONE_USE_PRIORITY = {
    "idle": ["living_room", "generic"],
    "living_room": ["living_room"],
    "care": ["living_room"],
    "sleep": ["bedroom"],
    "child_sleep": ["bedroom"],
    "bedroom": ["bedroom"],
    "work": ["office", "living_room"],
    "schoolwork": ["office", "living_room"],
    "office": ["office"],
    "kitchen": ["kitchen"],
    "bathroom": ["bathroom"],
    "laundry": ["laundry"],
    "entrance": ["entrance", "corridor"],
    "door": ["entrance", "corridor"],
}


INTERNAL_SOURCE_ROLE_SUFFIX_PRIORITY = {
    "sleep": ["bedroom_1", "bedroom"],
    "child_sleep": ["bedroom_2", "bedroom"],
    "work": ["office"],
    "schoolwork": ["office"],
    "idle": ["living_room"],
    "care": ["living_room"],
}


@dataclass
class InternalSourceZoneResolution:
    zone_id: str = ""
    resolution_method: str = INTERNAL_SOURCE_ZONE_RESOLUTION_UNRESOLVED

    action_name: str = ""
    actor_id: str = ""

    target_space_id: str = ""
    target_zone_role: str = ""
    default_zone_role: str = ""

    preferred_dwelling_id: str = ""

    def resolved(self) -> bool:
        return bool(self.zone_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "resolution_method": self.resolution_method,
            "action_name": self.action_name,
            "actor_id": self.actor_id,
            "target_space_id": self.target_space_id,
            "target_zone_role": self.target_zone_role,
            "default_zone_role": self.default_zone_role,
            "preferred_dwelling_id": self.preferred_dwelling_id,
            "resolved": self.resolved(),
        }


def normalize_internal_zone_role(value: Any) -> str:
    role = str(value).strip().lower()
    role = role.replace(" ", "_")
    role = role.replace("-", "_")

    if role == "door":
        role = "entrance"

    return role


def all_zone_models_from_building_model(
    building_model: Any,
) -> Dict[str, Any]:
    if building_model is None:
        return {}

    if hasattr(building_model, "all_zone_models"):
        return dict(building_model.all_zone_models())

    return {}


def all_zone_ids_from_building_model(
    building_model: Any,
) -> List[str]:
    zone_models = all_zone_models_from_building_model(building_model)

    if zone_models:
        return [
            str(zone_id)
            for zone_id in zone_models.keys()
        ]

    if building_model is not None and hasattr(building_model, "all_zone_ids"):
        return [
            str(zone_id)
            for zone_id in building_model.all_zone_ids()
        ]

    return []


def zone_id_is_valid_for_building_model(
    zone_id: str,
    building_model: Any,
) -> bool:
    zone_id = str(zone_id).strip()

    if not zone_id:
        return False

    if zone_id == OUTSIDE_ZONE_ID:
        return False

    zone_ids = all_zone_ids_from_building_model(building_model)

    if not zone_ids:
        return True

    return zone_id in set(zone_ids)


def preferred_dwelling_id_for_actor(
    actor_id: str,
    locations: Optional[Dict[str, Any]] = None,
) -> str:
    locations = locations or {}

    if actor_id not in locations:
        return ""

    location = locations[actor_id]

    dwelling_id = str(
        _get_attr_or_key(location, "dwelling_id", "")
    ).strip()

    return dwelling_id


def _zone_model_dwelling_id(
    zone_model: Any,
) -> str:
    return str(
        _get_attr_or_key(zone_model, "dwelling_id", "")
    ).strip()


def _zone_model_zone_use(
    zone_model: Any,
) -> str:
    return normalize_internal_zone_role(
        _get_attr_or_key(zone_model, "zone_use", "")
    )


def _prefer_zone_candidates(
    candidates: List[str],
    zone_models: Dict[str, Any],
    preferred_dwelling_id: str = "",
) -> List[str]:
    out = []

    for zone_id in candidates:
        if zone_id not in out:
            out.append(zone_id)

    if not preferred_dwelling_id:
        return out

    same_dwelling = []
    other = []

    for zone_id in out:
        zone_model = zone_models.get(zone_id)

        if zone_model is not None and _zone_model_dwelling_id(zone_model) == preferred_dwelling_id:
            same_dwelling.append(zone_id)
        else:
            other.append(zone_id)

    return same_dwelling + other


def zone_ids_for_role_from_building_model(
    role: str,
    building_model: Any,
    preferred_dwelling_id: str = "",
) -> List[str]:
    """
    Return candidate physical zone IDs for a semantic role.

    Does not guess from agents.
    Only reads BuildingModel/ZoneModel.
    """

    role = normalize_internal_zone_role(role)

    if not role:
        return []

    if role in {"current", OUTSIDE_ZONE_ID}:
        return []

    zone_models = all_zone_models_from_building_model(building_model)

    if not zone_models:
        return []

    if role in zone_models:
        return [role]

    suffix_candidates = []

    suffixes = [role]
    suffixes.extend(INTERNAL_SOURCE_ROLE_SUFFIX_PRIORITY.get(role, []))

    for suffix in suffixes:
        for zone_id in zone_models.keys():
            if zone_id == suffix or zone_id.endswith("_" + suffix):
                suffix_candidates.append(zone_id)

    if suffix_candidates:
        return _prefer_zone_candidates(
            candidates=suffix_candidates,
            zone_models=zone_models,
            preferred_dwelling_id=preferred_dwelling_id,
        )

    zone_use_priority = INTERNAL_SOURCE_ROLE_TO_ZONE_USE_PRIORITY.get(
        role,
        [role],
    )

    use_candidates = []

    for preferred_use in zone_use_priority:
        for zone_id, zone_model in zone_models.items():
            if _zone_model_zone_use(zone_model) == preferred_use:
                use_candidates.append(zone_id)

    return _prefer_zone_candidates(
        candidates=use_candidates,
        zone_models=zone_models,
        preferred_dwelling_id=preferred_dwelling_id,
    )


def resolve_zone_role_to_zone_id(
    role: str,
    role_to_zone_id: Optional[Dict[str, str]] = None,
    building_model: Any = None,
    preferred_dwelling_id: str = "",
) -> str:
    role = normalize_internal_zone_role(role)

    if not role or role in {"current", OUTSIDE_ZONE_ID}:
        return ""

    role_to_zone_id = role_to_zone_id or {}

    mapped = str(role_to_zone_id.get(role, "")).strip()

    if mapped and zone_id_is_valid_for_building_model(
        zone_id=mapped,
        building_model=building_model,
    ):
        return mapped

    candidates = zone_ids_for_role_from_building_model(
        role=role,
        building_model=building_model,
        preferred_dwelling_id=preferred_dwelling_id,
    )

    if candidates:
        return candidates[0]

    return ""


def make_role_to_zone_id_map_from_building_model(
    building_model: Any,
    preferred_dwelling_id: str = "",
) -> Dict[str, str]:
    """
    Build a semantic role → physical zone_id map from BuildingModel.

    Useful for tests and for default bridge setup.
    """

    out = {}

    roles = sorted(INTERNAL_SOURCE_ROLE_TO_ZONE_USE_PRIORITY.keys())

    for role in roles:
        zone_id = resolve_zone_role_to_zone_id(
            role=role,
            role_to_zone_id={},
            building_model=building_model,
            preferred_dwelling_id=preferred_dwelling_id,
        )

        if zone_id:
            out[role] = zone_id

    return out


def resolve_internal_source_zone(
    action_name: str = "",
    actor_id: str = "",
    target_space_id: str = "",
    target_zone_role: str = "",
    locations: Optional[Dict[str, Any]] = None,
    role_to_zone_id: Optional[Dict[str, str]] = None,
    building_model: Any = None,
) -> InternalSourceZoneResolution:
    """
    Resolve an action/chunk record into a physical zone.

    Priority:
        1. valid target_space_id
        2. target_space_id interpreted as semantic role
        3. target_zone_role
        4. action default role
        5. actor current location
        6. first building zone

    Safety rule:
        For fixed-room actions such as shower/cook/washing machine,
        if target_zone_role is "current", prefer the action default room.
    """

    locations = locations or {}
    role_to_zone_id = role_to_zone_id or {}

    action_name = str(action_name).strip()
    actor_id = str(actor_id).strip()
    target_space_id = str(target_space_id).strip()
    target_zone_role = normalize_internal_zone_role(target_zone_role)

    spec = get_action_internal_source_spec(action_name)
    default_zone_role = normalize_internal_zone_role(spec.default_zone_role)

    preferred_dwelling_id = preferred_dwelling_id_for_actor(
        actor_id=actor_id,
        locations=locations,
    )

    base_kwargs = {
        "action_name": action_name,
        "actor_id": actor_id,
        "target_space_id": target_space_id,
        "target_zone_role": target_zone_role,
        "default_zone_role": default_zone_role,
        "preferred_dwelling_id": preferred_dwelling_id,
    }

    # Outside actions do not create indoor physical sources.
    if target_space_id == OUTSIDE_ZONE_ID or target_zone_role == OUTSIDE_ZONE_ID:
        return InternalSourceZoneResolution(**base_kwargs)

    # Safety override for fixed-room actions accidentally recorded as "current".
    if (
        target_space_id
        and target_zone_role in {"", "current"}
        and spec.prefer_default_zone_role_when_target_is_current
        and default_zone_role
        and default_zone_role != "current"
    ):
        zone_id = resolve_zone_role_to_zone_id(
            role=default_zone_role,
            role_to_zone_id=role_to_zone_id,
            building_model=building_model,
            preferred_dwelling_id=preferred_dwelling_id,
        )

        if zone_id:
            return InternalSourceZoneResolution(
                zone_id=zone_id,
                resolution_method=INTERNAL_SOURCE_ZONE_RESOLUTION_ACTION_DEFAULT_ROLE_OVER_CURRENT,
                **base_kwargs
            )

    # 1. Direct valid target_space_id.
    if target_space_id and zone_id_is_valid_for_building_model(
        zone_id=target_space_id,
        building_model=building_model,
    ):
        return InternalSourceZoneResolution(
            zone_id=target_space_id,
            resolution_method=INTERNAL_SOURCE_ZONE_RESOLUTION_DIRECT_TARGET_SPACE,
            **base_kwargs
        )

    # 2. target_space_id may be a role like "kitchen" or "living_room".
    if target_space_id:
        zone_id = resolve_zone_role_to_zone_id(
            role=target_space_id,
            role_to_zone_id=role_to_zone_id,
            building_model=building_model,
            preferred_dwelling_id=preferred_dwelling_id,
        )

        if zone_id:
            return InternalSourceZoneResolution(
                zone_id=zone_id,
                resolution_method=INTERNAL_SOURCE_ZONE_RESOLUTION_TARGET_SPACE_AS_ROLE,
                **base_kwargs
            )

    # 3. Explicit non-current target role.
    if target_zone_role and target_zone_role != "current":
        zone_id = resolve_zone_role_to_zone_id(
            role=target_zone_role,
            role_to_zone_id=role_to_zone_id,
            building_model=building_model,
            preferred_dwelling_id=preferred_dwelling_id,
        )

        if zone_id:
            return InternalSourceZoneResolution(
                zone_id=zone_id,
                resolution_method=INTERNAL_SOURCE_ZONE_RESOLUTION_TARGET_ROLE,
                **base_kwargs
            )

    # 4. Action default role.
    if default_zone_role and default_zone_role != "current":
        zone_id = resolve_zone_role_to_zone_id(
            role=default_zone_role,
            role_to_zone_id=role_to_zone_id,
            building_model=building_model,
            preferred_dwelling_id=preferred_dwelling_id,
        )

        if zone_id:
            return InternalSourceZoneResolution(
                zone_id=zone_id,
                resolution_method=INTERNAL_SOURCE_ZONE_RESOLUTION_ACTION_DEFAULT_ROLE,
                **base_kwargs
            )

    # 5. Actor current location.
    if actor_id:
        zone_from_actor = _zone_for_actor(
            actor_id=actor_id,
            locations=locations,
        )

        if zone_from_actor and zone_id_is_valid_for_building_model(
            zone_id=zone_from_actor,
            building_model=building_model,
        ):
            return InternalSourceZoneResolution(
                zone_id=zone_from_actor,
                resolution_method=INTERNAL_SOURCE_ZONE_RESOLUTION_ACTOR_LOCATION,
                **base_kwargs
            )

    # 6. First building zone.
    all_zone_ids = all_zone_ids_from_building_model(building_model)

    if all_zone_ids:
        return InternalSourceZoneResolution(
            zone_id=all_zone_ids[0],
            resolution_method=INTERNAL_SOURCE_ZONE_RESOLUTION_FIRST_BUILDING_ZONE,
            **base_kwargs
        )

    return InternalSourceZoneResolution(**base_kwargs)


def resolve_internal_source_zone_id(
    action_name: str = "",
    actor_id: str = "",
    target_space_id: str = "",
    target_zone_role: str = "",
    locations: Optional[Dict[str, Any]] = None,
    role_to_zone_id: Optional[Dict[str, str]] = None,
    building_model: Any = None,
) -> str:
    """
    Compatibility wrapper returning only zone_id.
    """

    result = resolve_internal_source_zone(
        action_name=action_name,
        actor_id=actor_id,
        target_space_id=target_space_id,
        target_zone_role=target_zone_role,
        locations=locations,
        role_to_zone_id=role_to_zone_id,
        building_model=building_model,
    )

    return result.zone_id

# ============================================================
# BUILDERS FROM CHUNK RECORDS
# ============================================================

def internal_source_records_from_chunk_records(
    chunk_records: List[Mapping[str, Any]],
    locations: Optional[Dict[str, Any]] = None,
    role_to_zone_id: Optional[Dict[str, str]] = None,
    building_model: Any = None,
) -> List[InternalSourceRecord]:
    """
    Convert execution chunk records into internal source records.

    Preferred zone:
        item["target_space_id"]

    Fallbacks:
        role map, action spec default role, actor current location.
    """

    locations = locations or {}
    role_to_zone_id = role_to_zone_id or {}
    records = []

    for chunk in _safe_list(chunk_records):
        if not isinstance(chunk, Mapping):
            continue

        breakdown = _safe_list(chunk.get("power_breakdown", []))

        for item in breakdown:
            if not isinstance(item, Mapping):
                continue

            action_name = str(item.get("name", "")).strip()
            actor_id = str(item.get("actor_id", "")).strip()

            if not action_name:
                continue

            spec = get_action_internal_source_spec(action_name)

            target_space_id = str(item.get("target_space_id", "")).strip()
            target_zone_role = str(
                item.get("target_zone_role", spec.default_zone_role)
            ).strip()

            resolution = resolve_internal_source_zone(
                action_name=action_name,
                actor_id=actor_id,
                target_space_id=target_space_id,
                target_zone_role=target_zone_role,
                locations=locations,
                role_to_zone_id=role_to_zone_id,
                building_model=building_model,
            )

            zone_id = resolution.zone_id


            if not zone_id:
                continue

            minutes = _safe_float(item.get("minutes", 0.0), 0.0)
            power_w = _safe_float(item.get("power_w", 0.0), 0.0)
            energy_wh = _safe_float(item.get("energy_wh", 0.0), 0.0)

            if energy_wh <= 0.0 and power_w > 0.0 and minutes > 0.0:
                energy_wh = _energy_wh_from_average_power(
                    power_w=power_w,
                    dt_minutes=minutes,
                )

            heat_energy_wh = appliance_heat_energy_wh_from_electricity(
                electricity_wh=energy_wh,
                electricity_to_heat_fraction=spec.electricity_to_heat_fraction,
            )

            sensible_heat_wh = heat_energy_wh * spec.sensible_heat_fraction
            latent_heat_wh = heat_energy_wh * spec.latent_heat_fraction

            sensible_heat_w = _average_power_from_energy_wh(
                energy_wh=sensible_heat_wh,
                dt_minutes=minutes,
            )

            latent_heat_w = _average_power_from_energy_wh(
                energy_wh=latent_heat_wh,
                dt_minutes=minutes,
            )

            has_physical_source = (
                energy_wh > 0.0
                or sensible_heat_wh > 0.0
                or latent_heat_wh > 0.0
                or spec.co2_generation_m3_h > 0.0
                or spec.moisture_generation_kg_h > 0.0
                or spec.noise_source_db > 0.0
            )

            if not has_physical_source:
                continue

            records.append(
                InternalSourceRecord(
                    zone_id=zone_id,
                    source_kind=spec.source_kind,
                    source_type=spec.source_type,
                    actor_id=actor_id,
                    action_name=action_name,
                    duration_minutes=minutes,
                    power_w=power_w,
                    electricity_wh=energy_wh,
                    sensible_heat_w=sensible_heat_w,
                    sensible_heat_wh=sensible_heat_wh,
                    latent_heat_w=latent_heat_w,
                    latent_heat_wh=latent_heat_wh,
                    co2_generation_m3_h=spec.co2_generation_m3_h,
                    moisture_generation_kg_h=spec.moisture_generation_kg_h,
                    noise_source_db=spec.noise_source_db,
                    source=INTERNAL_SOURCE_RECORD_SOURCE_CHUNK,
                    metadata={
                        "target_space_id": target_space_id,
                        "target_zone_role": target_zone_role,
                        "zone_resolution": resolution.to_dict(),
                        "electricity_to_heat_fraction": spec.electricity_to_heat_fraction,
                        "sensible_heat_fraction": spec.sensible_heat_fraction,
                        "latent_heat_fraction": spec.latent_heat_fraction,
                        "heat_energy_wh": heat_energy_wh,
                        "heat_source_mode": APPLIANCE_HEAT_SOURCE_MODE,
                        "moisture_generation_kg_h": spec.moisture_generation_kg_h,
                        "moisture_generation_kg": moisture_generation_kg_from_rate(
                            moisture_generation_kg_h=spec.moisture_generation_kg_h,
                            duration_minutes=minutes,
                        ),
                    },
                )
            )

    return records


def internal_source_records_from_people_locations(
    people: Optional[Dict[str, Any]] = None,
    locations: Optional[Dict[str, Any]] = None,
    person_source_specs: Optional[Dict[str, PersonInternalSourceSpec]] = None,
    role_to_zone_id: Optional[Dict[str, str]] = None,
    building_model: Any = None,
    dt_minutes: float = DEFAULT_INTERNAL_SOURCE_DT_MINUTES,
) -> List[InternalSourceRecord]:
    """
    Convert people + locations into physical occupant source records.

    People generate:
    - sensible heat
    - CO2
    - moisture placeholder
    - optional noise later

    Zone resolution:
    - current_space_id if already a valid physical zone
    - current_space_id as semantic role
    - current_space_role as semantic role
    - fallback through internal source resolver
    """

    people = people or {}
    locations = locations or {}
    person_source_specs = person_source_specs or {}
    role_to_zone_id = role_to_zone_id or {}

    records = []

    for occupant_id, person in people.items():
        location = locations.get(occupant_id)

        if location is None:
            continue

        if not person_is_home(person=person, location=location):
            continue

        current_space_id = str(
            _get_attr_or_key(location, "current_space_id", "")
        ).strip()

        current_space_role = str(
            _get_attr_or_key(location, "current_space_role", "current")
        ).strip()

        resolution = resolve_internal_source_zone(
            action_name=INTERNAL_SOURCE_TYPE_PEOPLE,
            actor_id=str(occupant_id),
            target_space_id=current_space_id,
            target_zone_role=current_space_role,
            locations=locations,
            role_to_zone_id=role_to_zone_id,
            building_model=building_model,
        )

        zone_id = resolution.zone_id

        if not zone_id:
            continue

        spec = person_source_specs.get(
            occupant_id,
            DEFAULT_PERSON_INTERNAL_SOURCE_SPEC,
        )

        values = effective_person_internal_source_values(
            person=person,
            location=location,
            person_source_spec=spec,
        )

        sensible_heat_w = values["sensible_heat_w"]
        co2_generation_m3_h = values["co2_generation_m3_h"]
        moisture_generation_kg_h = values["moisture_generation_kg_h"]
        noise_source_db = values["noise_source_db"]

        if (
            sensible_heat_w <= 0.0
            and co2_generation_m3_h <= 0.0
            and moisture_generation_kg_h <= 0.0
            and noise_source_db <= 0.0
        ):
            continue

        records.append(
            InternalSourceRecord(
                zone_id=zone_id,
                source_kind=INTERNAL_SOURCE_KIND_PERSON,
                source_type=spec.source_type,
                actor_id=str(occupant_id),
                action_name=str(
                    _get_attr_or_key(location, "current_activity", "occupancy")
                ),
                duration_minutes=dt_minutes,
                power_w=0.0,
                electricity_wh=0.0,
                sensible_heat_w=sensible_heat_w,
                sensible_heat_wh=_energy_wh_from_average_power(
                    power_w=sensible_heat_w,
                    dt_minutes=dt_minutes,
                ),
                latent_heat_w=0.0,
                latent_heat_wh=0.0,
                co2_generation_m3_h=co2_generation_m3_h,
                moisture_generation_kg_h=moisture_generation_kg_h,
                noise_source_db=noise_source_db,
                source=INTERNAL_SOURCE_RECORD_SOURCE_PEOPLE,
                metadata={
                    "zone_resolution": resolution.to_dict(),
                    "activity_multiplier": values["activity_multiplier"],
                    "current_space_id": current_space_id,
                    "current_space_role": current_space_role,
                },
            )
        )

    return records

def internal_source_records_from_lighting_power_result(
    lighting_power_result=None,
    dt_minutes=None,
):
    """
    Convert daylight.py BuildingLightingPowerResult-like objects into
    internal lighting source records.

    No import from daylight.py.
    Uses duck typing.
    """

    if lighting_power_result is None:
        return []

    if dt_minutes is None:
        dt_minutes = _get_attr_or_key(
            lighting_power_result,
            "dt_minutes",
            DEFAULT_INTERNAL_SOURCE_DT_MINUTES,
        )

    dt_minutes = _non_negative_float(
        dt_minutes,
        "dt_minutes",
        "lighting_power_result",
    )

    zone_results = _get_attr_or_key(
        lighting_power_result,
        "zone_results",
        {},
    )

    if zone_results is None:
        zone_results = {}

    records = []

    for zone_id, zone_result in zone_results.items():
        zone_id = str(zone_id).strip()

        if not zone_id:
            continue

        lights_on = bool(
            _get_attr_or_key(zone_result, "lights_on", False)
        )

        lighting_power_w = _safe_float(
            _get_attr_or_key(zone_result, "lighting_power_w", 0.0),
            0.0,
        )

        lighting_energy_wh = _safe_float(
            _get_attr_or_key(zone_result, "lighting_energy_wh", 0.0),
            0.0,
        )

        if lighting_energy_wh <= 0.0 and lighting_power_w > 0.0:
            lighting_energy_wh = _lighting_energy_wh_from_power(
                lighting_power_w=lighting_power_w,
                dt_minutes=dt_minutes,
            )

        if not lights_on and lighting_power_w <= 0.0 and lighting_energy_wh <= 0.0:
            continue

        if lighting_power_w <= 0.0 and lighting_energy_wh <= 0.0:
            continue

        heat_energy_wh = lighting_heat_energy_wh_from_electricity(
            electricity_wh=lighting_energy_wh,
        )

        sensible_heat_w = _average_power_from_energy_wh(
            energy_wh=heat_energy_wh,
            dt_minutes=dt_minutes,
        )

        records.append(
            InternalSourceRecord(
                zone_id=zone_id,
                source_kind=INTERNAL_SOURCE_KIND_LIGHTING,
                source_type=INTERNAL_SOURCE_TYPE_LIGHTING,
                source_id="lighting_" + zone_id,
                actor_id="",
                action_name="lighting",
                duration_minutes=dt_minutes,
                power_w=lighting_power_w,
                electricity_wh=lighting_energy_wh,
                sensible_heat_w=sensible_heat_w,
                sensible_heat_wh=heat_energy_wh,
                latent_heat_w=0.0,
                latent_heat_wh=0.0,
                co2_generation_m3_h=0.0,
                moisture_generation_kg_h=0.0,
                noise_source_db=0.0,
                source=LIGHTING_INTERNAL_SOURCE_MODE_POWER_RESULT,
                metadata={
                    "lights_on": lights_on,
                    "dimming_fraction": _safe_float(
                        _get_attr_or_key(zone_result, "dimming_fraction", 0.0),
                        0.0,
                    ),
                    "artificial_lighting_illuminance_lux": _safe_float(
                        _get_attr_or_key(
                            zone_result,
                            "artificial_lighting_illuminance_lux",
                            0.0,
                        ),
                        0.0,
                    ),
                    "electricity_to_heat_fraction": DEFAULT_LIGHTING_ELECTRICITY_TO_HEAT_FRACTION,
                },
            )
        )

    return records


def internal_source_records_from_zone_control_commands(
    zone_control_commands=None,
    dt_minutes=DEFAULT_INTERNAL_SOURCE_DT_MINUTES,
):
    """
    Convert ZoneControlCommand-like objects into lighting source records.

    This is fallback when daylight.py lighting_power_result is not available.
    """

    if zone_control_commands is None:
        return []

    dt_minutes = _non_negative_float(
        dt_minutes,
        "dt_minutes",
        "zone_control_commands",
    )

    if isinstance(zone_control_commands, Mapping):
        items = list(zone_control_commands.items())
    else:
        items = []

        for command in _safe_list(zone_control_commands):
            zone_id = str(_get_attr_or_key(command, "zone_id", "")).strip()
            items.append((zone_id, command))

    records = []

    for zone_id, command in items:
        zone_id = str(zone_id).strip()

        if not zone_id:
            zone_id = str(_get_attr_or_key(command, "zone_id", "")).strip()

        if not zone_id:
            continue

        lights_on = bool(
            _get_attr_or_key(command, "lights_on", False)
        )

        lighting_power_w = _safe_float(
            _get_attr_or_key(command, "lighting_power_w", 0.0),
            0.0,
        )

        if not lights_on or lighting_power_w <= 0.0:
            continue

        lighting_energy_wh = _lighting_energy_wh_from_power(
            lighting_power_w=lighting_power_w,
            dt_minutes=dt_minutes,
        )

        heat_energy_wh = lighting_heat_energy_wh_from_electricity(
            electricity_wh=lighting_energy_wh,
        )

        records.append(
            InternalSourceRecord(
                zone_id=zone_id,
                source_kind=INTERNAL_SOURCE_KIND_LIGHTING,
                source_type=INTERNAL_SOURCE_TYPE_LIGHTING,
                source_id="lighting_" + zone_id,
                actor_id="",
                action_name="lighting",
                duration_minutes=dt_minutes,
                power_w=lighting_power_w,
                electricity_wh=lighting_energy_wh,
                sensible_heat_w=lighting_power_w,
                sensible_heat_wh=heat_energy_wh,
                latent_heat_w=0.0,
                latent_heat_wh=0.0,
                co2_generation_m3_h=0.0,
                moisture_generation_kg_h=0.0,
                noise_source_db=0.0,
                source=LIGHTING_INTERNAL_SOURCE_MODE_CONTROL_COMMAND,
                metadata={
                    "lights_on": lights_on,
                    "electricity_to_heat_fraction": DEFAULT_LIGHTING_ELECTRICITY_TO_HEAT_FRACTION,
                },
            )
        )

    return records

def make_building_internal_source_result(
    chunk_records=None,
    people=None,
    locations=None,
    role_to_zone_id=None,
    building_model=None,
    dt_minutes=DEFAULT_INTERNAL_SOURCE_DT_MINUTES,
    include_people=True,
    include_lighting=True,
    include_hvac=False,
    zone_system_specs=None,
    lighting_power_result=None,
    zone_control_commands=None,
):
    """
    High-level Phase 9.1 builder.

    Produces one BuildingInternalSourceResult from:
    - people + locations
    - chunk records
    """

    expected_zone_ids = all_zone_ids_from_building_model(building_model)

    records = []

    records.extend(
        internal_source_records_from_chunk_records(
            chunk_records=chunk_records or [],
            locations=locations or {},
            role_to_zone_id=role_to_zone_id or {},
            building_model=building_model,
        )
    )

    if include_people:
        records.extend(
            internal_source_records_from_people_locations(
                people=people or {},
                locations=locations or {},
                role_to_zone_id=role_to_zone_id or {},
                building_model=building_model,
                dt_minutes=dt_minutes,
            )
        )


            
    if include_lighting:
        if lighting_power_result is not None:
            records.extend(
                internal_source_records_from_lighting_power_result(
                    lighting_power_result=lighting_power_result,
                    dt_minutes=dt_minutes,
                )
            )
        elif zone_control_commands is not None:
            records.extend(
                internal_source_records_from_zone_control_commands(
                    zone_control_commands=zone_control_commands,
                    dt_minutes=dt_minutes,
                )
            )

    if include_hvac and zone_control_commands is not None:
        records.extend(
            internal_source_records_from_hvac_commands(
                zone_control_commands=zone_control_commands,
                zone_system_specs=zone_system_specs,
                dt_minutes=dt_minutes,
            )
        )
    return BuildingInternalSourceResult(
        records=records,
        expected_zone_ids=expected_zone_ids,
        dt_minutes=dt_minutes,
    )


def make_empty_building_internal_source_result(
    building_model: Any = None,
    zone_ids: Optional[List[str]] = None,
    dt_minutes: float = DEFAULT_INTERNAL_SOURCE_DT_MINUTES,
) -> BuildingInternalSourceResult:
    if zone_ids is None:
        zone_ids = all_zone_ids_from_building_model(building_model)

    return BuildingInternalSourceResult(
        records=[],
        expected_zone_ids=list(zone_ids or []),
        dt_minutes=dt_minutes,
        source="empty_internal_source_result",
    )

def lighting_heat_energy_wh_from_electricity(
    electricity_wh,
    electricity_to_heat_fraction=DEFAULT_LIGHTING_ELECTRICITY_TO_HEAT_FRACTION,
):
    electricity_wh = _non_negative_float(
        electricity_wh,
        "electricity_wh",
        "lighting",
    )

    electricity_to_heat_fraction = _clamp_fraction(
        electricity_to_heat_fraction
    )

    return electricity_wh * electricity_to_heat_fraction


def internal_source_record_is_lighting(record):
    if not isinstance(record, InternalSourceRecord):
        raise TypeError("record must be InternalSourceRecord.")

    return record.source_kind == INTERNAL_SOURCE_KIND_LIGHTING


def _lighting_energy_wh_from_power(
    lighting_power_w,
    dt_minutes,
):
    lighting_power_w = _non_negative_float(
        lighting_power_w,
        "lighting_power_w",
        "lighting",
    )

    dt_minutes = _non_negative_float(
        dt_minutes,
        "dt_minutes",
        "lighting",
    )

    if dt_minutes <= 0.0:
        return 0.0

    return lighting_power_w * dt_minutes / 60.0

def normalize_person_activity_label(value: Any) -> str:
    activity = str(value).strip().lower()
    activity = activity.replace(" ", "_")
    activity = activity.replace("-", "_")

    if not activity:
        return PERSON_ACTIVITY_IDLE

    if activity in {"sleep", "asleep"}:
        return PERSON_ACTIVITY_SLEEPING

    if activity in {"work", "use_laptop", "study", "schoolwork"}:
        return PERSON_ACTIVITY_WORKING

    if activity in {"cook", "make_hot_drink"}:
        return PERSON_ACTIVITY_COOKING

    if activity in {"clean", "laundry", "run_washing_machine"}:
        return PERSON_ACTIVITY_CLEANING

    if activity in {"exercise", "workout"}:
        return PERSON_ACTIVITY_EXERCISING

    if activity in {"outside", "work_outside", "school", "away"}:
        return PERSON_ACTIVITY_AWAY

    return PERSON_ACTIVITY_IDLE


def person_is_home(
    person: Any = None,
    location: Any = None,
) -> bool:
    if location is not None:
        return bool(_get_attr_or_key(location, "is_home", False))

    if person is not None:
        return bool(_get_attr_or_key(person, "is_home", False))

    return False


def person_is_sleeping(
    person: Any = None,
    location: Any = None,
) -> bool:
    if person is not None:
        if bool(_get_attr_or_key(person, "is_sleeping", False)):
            return True

    activity = ""

    if location is not None:
        activity = str(_get_attr_or_key(location, "current_activity", ""))

    return normalize_person_activity_label(activity) == PERSON_ACTIVITY_SLEEPING


def person_activity_internal_source_multiplier(
    person: Any = None,
    location: Any = None,
) -> float:
    if not person_is_home(person=person, location=location):
        return 0.0

    if person_is_sleeping(person=person, location=location):
        return PERSON_ACTIVITY_INTERNAL_SOURCE_MULTIPLIERS[
            PERSON_ACTIVITY_SLEEPING
        ]

    activity = PERSON_ACTIVITY_IDLE

    if location is not None:
        activity = normalize_person_activity_label(
            _get_attr_or_key(location, "current_activity", PERSON_ACTIVITY_IDLE)
        )

    return PERSON_ACTIVITY_INTERNAL_SOURCE_MULTIPLIERS.get(
        activity,
        PERSON_ACTIVITY_INTERNAL_SOURCE_MULTIPLIERS[PERSON_ACTIVITY_IDLE],
    )


def effective_person_internal_source_values(
    person: Any = None,
    location: Any = None,
    person_source_spec: Optional[PersonInternalSourceSpec] = None,
) -> Dict[str, float]:
    if person_source_spec is None:
        person_source_spec = DEFAULT_PERSON_INTERNAL_SOURCE_SPEC

    if not isinstance(person_source_spec, PersonInternalSourceSpec):
        raise TypeError(
            "person_source_spec must be PersonInternalSourceSpec."
        )

    multiplier = person_activity_internal_source_multiplier(
        person=person,
        location=location,
    )

    return {
        "activity_multiplier": multiplier,
        "sensible_heat_w": person_source_spec.sensible_heat_w * multiplier,
        "co2_generation_m3_h": person_source_spec.co2_generation_m3_h * multiplier,
        "moisture_generation_kg_h": person_source_spec.moisture_generation_kg_h * multiplier,
        "noise_source_db": person_source_spec.noise_source_db,
    }

def internal_source_record_is_hvac(record):
    if not isinstance(record, InternalSourceRecord):
        raise TypeError("record must be InternalSourceRecord.")

    return record.source_kind == INTERNAL_SOURCE_KIND_HVAC


def hvac_electricity_wh_from_delivered_power(
    delivered_power_w,
    efficiency_or_cop,
    dt_minutes,
):
    delivered_power_w = _non_negative_float(
        delivered_power_w,
        "delivered_power_w",
        "hvac",
    )

    efficiency_or_cop = float(efficiency_or_cop)

    if efficiency_or_cop <= 0.0:
        raise ValueError(
            "efficiency_or_cop must be positive for HVAC. Got: "
            + str(efficiency_or_cop)
        )

    dt_minutes = _non_negative_float(
        dt_minutes,
        "dt_minutes",
        "hvac",
    )

    if dt_minutes <= 0.0:
        return 0.0

    return delivered_power_w / efficiency_or_cop * dt_minutes / 60.0


def _command_is_heating(command):
    return bool(_get_attr_or_key(command, "heating_on", False))


def _command_is_cooling(command):
    return bool(_get_attr_or_key(command, "cooling_on", False))


def _get_system_spec_for_zone(zone_system_specs, zone_id):
    if zone_system_specs is None:
        return None

    if isinstance(zone_system_specs, Mapping):
        return zone_system_specs.get(zone_id)

    for spec in _safe_list(zone_system_specs):
        spec_zone_id = str(_get_attr_or_key(spec, "zone_id", "")).strip()

        if spec_zone_id == zone_id:
            return spec

    return None

def internal_source_records_from_hvac_commands(
    zone_control_commands=None,
    zone_system_specs=None,
    dt_minutes=DEFAULT_INTERNAL_SOURCE_DT_MINUTES,
):
    """
    Convert ZoneControlCommand + ZoneSystemSpec-like objects into HVAC source records.

    Sign convention:
        heating -> positive sensible_heat_w
        cooling -> negative sensible_heat_w
    Warning:
        This function is diagnostic/backward-compatible only.
        In Phase 10.10+, HVAC should normally be recorded by the
        system-energy path, not as an internal source, to avoid
        double counting.
    electricity_wh is always non-negative.
    """

    if zone_control_commands is None:
        return []

    dt_minutes = _non_negative_float(
        dt_minutes,
        "dt_minutes",
        "hvac_commands",
    )

    if isinstance(zone_control_commands, Mapping):
        items = list(zone_control_commands.items())
    else:
        items = []

        for command in _safe_list(zone_control_commands):
            zone_id = str(_get_attr_or_key(command, "zone_id", "")).strip()
            items.append((zone_id, command))

    records = []

    for zone_id, command in items:
        zone_id = str(zone_id).strip()

        if not zone_id:
            zone_id = str(_get_attr_or_key(command, "zone_id", "")).strip()

        if not zone_id:
            continue

        system_spec = _get_system_spec_for_zone(
            zone_system_specs=zone_system_specs,
            zone_id=zone_id,
        )

        heating_capacity_w = _safe_float(
            _get_attr_or_key(system_spec, "heating_capacity_w", 0.0),
            0.0,
        )

        cooling_capacity_w = _safe_float(
            _get_attr_or_key(system_spec, "cooling_capacity_w", 0.0),
            0.0,
        )

        heating_efficiency_or_cop = _safe_float(
            _get_attr_or_key(
                system_spec,
                "heating_efficiency_or_cop",
                DEFAULT_HVAC_HEATING_EFFICIENCY_OR_COP,
            ),
            DEFAULT_HVAC_HEATING_EFFICIENCY_OR_COP,
        )

        cooling_efficiency_or_cop = _safe_float(
            _get_attr_or_key(
                system_spec,
                "cooling_efficiency_or_cop",
                DEFAULT_HVAC_COOLING_EFFICIENCY_OR_COP,
            ),
            DEFAULT_HVAC_COOLING_EFFICIENCY_OR_COP,
        )

        heating_fraction = _clamp_fraction(
            _get_attr_or_key(command, "heating_power_fraction", 0.0)
        )

        cooling_fraction = _clamp_fraction(
            _get_attr_or_key(command, "cooling_power_fraction", 0.0)
        )

        heating_on = _command_is_heating(command)
        cooling_on = _command_is_cooling(command)

        heating_power_w = 0.0
        cooling_power_w = 0.0

        if heating_on:
            heating_power_w = heating_capacity_w * heating_fraction

        if cooling_on:
            cooling_power_w = cooling_capacity_w * cooling_fraction

        if heating_power_w <= 0.0 and cooling_power_w <= 0.0:
            continue

        heating_electricity_wh = hvac_electricity_wh_from_delivered_power(
            delivered_power_w=heating_power_w,
            efficiency_or_cop=heating_efficiency_or_cop,
            dt_minutes=dt_minutes,
        )

        cooling_electricity_wh = hvac_electricity_wh_from_delivered_power(
            delivered_power_w=cooling_power_w,
            efficiency_or_cop=cooling_efficiency_or_cop,
            dt_minutes=dt_minutes,
        )

        net_sensible_gain_w = heating_power_w - cooling_power_w
        net_sensible_gain_wh = _energy_wh_from_average_power(
            power_w=net_sensible_gain_w,
            dt_minutes=dt_minutes,
        )

        electricity_wh = heating_electricity_wh + cooling_electricity_wh

        records.append(
            InternalSourceRecord(
                zone_id=zone_id,
                source_kind=INTERNAL_SOURCE_KIND_HVAC,
                source_type=INTERNAL_SOURCE_TYPE_HVAC,
                source_id="hvac_" + zone_id,
                actor_id="",
                action_name="hvac",
                duration_minutes=dt_minutes,
                power_w=_safe_float(
                    heating_power_w + cooling_power_w,
                    0.0,
                ),
                electricity_wh=electricity_wh,
                sensible_heat_w=net_sensible_gain_w,
                sensible_heat_wh=net_sensible_gain_wh,
                latent_heat_w=0.0,
                latent_heat_wh=0.0,
                co2_generation_m3_h=0.0,
                moisture_generation_kg_h=0.0,
                noise_source_db=0.0,
                source=HVAC_INTERNAL_SOURCE_MODE_CONTROL_COMMAND_AND_SYSTEM_SPEC,
                metadata={
                    "heating_on": heating_on,
                    "cooling_on": cooling_on,
                    "heating_capacity_w": heating_capacity_w,
                    "cooling_capacity_w": cooling_capacity_w,
                    "heating_power_fraction": heating_fraction,
                    "cooling_power_fraction": cooling_fraction,
                    "heating_delivered_power_w": heating_power_w,
                    "cooling_delivered_power_w": cooling_power_w,
                    "heating_electricity_wh": heating_electricity_wh,
                    "cooling_electricity_wh": cooling_electricity_wh,
                    "heating_efficiency_or_cop": heating_efficiency_or_cop,
                    "cooling_efficiency_or_cop": cooling_efficiency_or_cop,
                    "sign_convention": "heating_positive_cooling_negative",
                },
            )
        )

    return records

def action_internal_source_spec_is_appliance(
    spec: ActionInternalSourceSpec,
) -> bool:
    if not isinstance(spec, ActionInternalSourceSpec):
        raise TypeError("spec must be ActionInternalSourceSpec.")

    return spec.source_kind == INTERNAL_SOURCE_KIND_APPLIANCE


def action_name_is_appliance_source(
    action_name: str,
) -> bool:
    spec = get_action_internal_source_spec(action_name)
    return action_internal_source_spec_is_appliance(spec)


def internal_source_record_is_appliance(
    record: "InternalSourceRecord",
) -> bool:
    if not isinstance(record, InternalSourceRecord):
        raise TypeError("record must be InternalSourceRecord.")

    return record.source_kind == INTERNAL_SOURCE_KIND_APPLIANCE


def appliance_heat_energy_wh_from_electricity(
    electricity_wh: float,
    electricity_to_heat_fraction: float = DEFAULT_APPLIANCE_ELECTRICITY_TO_HEAT_FRACTION,
) -> float:
    electricity_wh = _non_negative_float(
        electricity_wh,
        "electricity_wh",
        "appliance",
    )

    electricity_to_heat_fraction = _clamp_fraction(
        electricity_to_heat_fraction
    )

    return electricity_wh * electricity_to_heat_fraction

def moisture_generation_kg_from_rate(
    moisture_generation_kg_h: float,
    duration_minutes: float,
) -> float:
    moisture_generation_kg_h = _non_negative_float(
        moisture_generation_kg_h,
        "moisture_generation_kg_h",
        "moisture_source",
    )

    duration_minutes = _non_negative_float(
        duration_minutes,
        "duration_minutes",
        "moisture_source",
    )

    return moisture_generation_kg_h * duration_minutes / 60.0


def average_moisture_generation_kg_h_from_mass(
    moisture_generation_kg: float,
    dt_minutes: float,
) -> float:
    moisture_generation_kg = _non_negative_float(
        moisture_generation_kg,
        "moisture_generation_kg",
        "moisture_source",
    )

    dt_minutes = _non_negative_float(
        dt_minutes,
        "dt_minutes",
        "moisture_source",
    )

    if dt_minutes <= 0.0:
        return 0.0

    return moisture_generation_kg / (dt_minutes / 60.0)


def internal_source_record_is_moisture_source(
    record: "InternalSourceRecord",
) -> bool:
    if not isinstance(record, InternalSourceRecord):
        raise TypeError("record must be InternalSourceRecord.")

    return record.moisture_generation_kg_h > 0.0


def action_name_is_moisture_source(
    action_name: str,
) -> bool:
    spec = get_action_internal_source_spec(action_name)
    return spec.moisture_generation_kg_h > 0.0


def average_rate_from_quantity_over_timestep(
    quantity,
    dt_minutes,
):
    dt_minutes = float(dt_minutes)

    if dt_minutes <= 0.0:
        return 0.0

    return float(quantity) / (dt_minutes / 60.0)


def aggregate_records_by_zone(
    records,
    expected_zone_ids=None,
):
    expected_zone_ids = expected_zone_ids or []

    out = {
        str(zone_id): []
        for zone_id in expected_zone_ids
        if str(zone_id).strip()
    }

    for record in records:
        if record.zone_id not in out:
            out[record.zone_id] = []

        out[record.zone_id].append(record)

    return out


def aggregate_records_by_kind(records):
    out = {}

    for record in records:
        source_kind = record.source_kind

        if source_kind not in out:
            out[source_kind] = []

        out[source_kind].append(record)

    return out


def aggregate_records_by_source_type(records):
    out = {}

    for record in records:
        source_type = record.source_type

        if source_type not in out:
            out[source_type] = []

        out[source_type].append(record)

    return out

def make_thermal_gains_from_internal_sources(
    internal_source_result,
    zone_ids=None,
    solar_gains_by_zone_w=None,
):
    """
    Convert BuildingInternalSourceResult into thermal.py BuildingThermalGains.

    Thermal convention:
        people      -> people gains
        appliances  -> appliance gains
        activities  -> appliance/internal gains
        lighting    -> lighting gains
        HVAC        -> HVAC gains, heating positive / cooling negative
        solar       -> kept external, optionally passed in
    """

    from nexusep.abbey.building.physics.thermal import (
        make_building_thermal_gains,
    )

    if not isinstance(internal_source_result, BuildingInternalSourceResult):
        raise TypeError(
            "internal_source_result must be BuildingInternalSourceResult."
        )

    if zone_ids is None:
        zone_ids = internal_source_result.all_zone_ids()

    solar_gains_by_zone_w = solar_gains_by_zone_w or {}

    by_zone_kind = internal_source_result.average_sensible_heat_w_by_zone_and_kind()

    people_gains_by_zone_w = {}
    appliance_gains_by_zone_w = {}
    lighting_gains_by_zone_w = {}
    hvac_gains_by_zone_w = {}

    for zone_id in zone_ids:
        zone_kind_values = by_zone_kind.get(zone_id, {})

        people_gains_by_zone_w[zone_id] = zone_kind_values.get(
            INTERNAL_SOURCE_KIND_PERSON,
            0.0,
        )

        appliance_gains_by_zone_w[zone_id] = (
            zone_kind_values.get(INTERNAL_SOURCE_KIND_APPLIANCE, 0.0)
            + zone_kind_values.get(INTERNAL_SOURCE_KIND_ACTIVITY, 0.0)
        )

        lighting_gains_by_zone_w[zone_id] = zone_kind_values.get(
            INTERNAL_SOURCE_KIND_LIGHTING,
            0.0,
        )

        hvac_gains_by_zone_w[zone_id] = zone_kind_values.get(
            INTERNAL_SOURCE_KIND_HVAC,
            0.0,
        )

    return make_building_thermal_gains(
        zone_ids=list(zone_ids),
        people_gains_by_zone_w=people_gains_by_zone_w,
        appliance_gains_by_zone_w=appliance_gains_by_zone_w,
        lighting_gains_by_zone_w=lighting_gains_by_zone_w,
        solar_gains_by_zone_w=solar_gains_by_zone_w,
        hvac_gains_by_zone_w=hvac_gains_by_zone_w,
    )

def make_airflow_control_inputs_from_internal_sources(
    internal_source_result,
    window_openings=None,
    door_openings=None,
):
    """
    Convert BuildingInternalSourceResult into airflow.py BuildingAirflowControlInputs.

    Only occupancy is created here.
    Window and door inputs should come from the existing window/control bridges.
    """

    from nexusep.abbey.building.physics.airflow import (
        ZoneOccupancyInput,
        BuildingAirflowControlInputs,
    )

    if not isinstance(internal_source_result, BuildingInternalSourceResult):
        raise TypeError(
            "internal_source_result must be BuildingInternalSourceResult."
        )

    occupancy_by_zone = {}

    for zone_id in internal_source_result.all_zone_ids():
        person_records = [
            record
            for record in internal_source_result.records_for_zone(zone_id)
            if record.source_kind == INTERNAL_SOURCE_KIND_PERSON
        ]

        occupancy_by_zone[zone_id] = ZoneOccupancyInput(
            zone_id=zone_id,
            number_of_people=float(len(person_records)),
            source=INTERNAL_SOURCE_TO_AIRFLOW_BRIDGE_SOURCE,
        )

    return BuildingAirflowControlInputs(
        occupancy_by_zone=occupancy_by_zone,
        window_openings=window_openings or {},
        door_openings=door_openings or {},
        source=INTERNAL_SOURCE_TO_AIRFLOW_BRIDGE_SOURCE,
    )

def make_co2_generation_result_from_internal_sources(
    internal_source_result,
    zone_ids=None,
):
    """
    Convert BuildingInternalSourceResult into airflow.py BuildingCO2GenerationResult.

    Uses actual average CO2 generation from internal sources, not only headcount.
    """

    from nexusep.abbey.building.physics.airflow import (
        ZoneCO2GenerationRecord,
        BuildingCO2GenerationResult,
    )

    if not isinstance(internal_source_result, BuildingInternalSourceResult):
        raise TypeError(
            "internal_source_result must be BuildingInternalSourceResult."
        )

    if zone_ids is None:
        zone_ids = internal_source_result.all_zone_ids()

    co2_by_zone = internal_source_result.average_co2_generation_m3_h_by_zone()

    zone_records = {}

    for zone_id in zone_ids:
        zone_records[zone_id] = ZoneCO2GenerationRecord(
            zone_id=zone_id,
            number_of_people=0.0,
            co2_generation_per_person_m3_h=0.0,
            co2_generation_m3_h=co2_by_zone.get(zone_id, 0.0),
            source=INTERNAL_SOURCE_TO_CO2_BRIDGE_SOURCE,
        )

    return BuildingCO2GenerationResult(
        zone_records=zone_records,
    )

def _moisture_source_type_from_internal_source_type(source_type):
    from nexusep.abbey.building.physics.moisture import (
        MOISTURE_SOURCE_PEOPLE,
        MOISTURE_SOURCE_COOKING,
        MOISTURE_SOURCE_SHOWER,
        MOISTURE_SOURCE_LAUNDRY_DRYING,
        MOISTURE_SOURCE_GENERIC,
    )

    source_type = str(source_type).strip().lower()

    if source_type == INTERNAL_SOURCE_TYPE_PEOPLE:
        return MOISTURE_SOURCE_PEOPLE

    if source_type == INTERNAL_SOURCE_TYPE_COOKING:
        return MOISTURE_SOURCE_COOKING

    if source_type == INTERNAL_SOURCE_TYPE_SHOWER:
        return MOISTURE_SOURCE_SHOWER

    if source_type == INTERNAL_SOURCE_TYPE_LAUNDRY:
        return MOISTURE_SOURCE_LAUNDRY_DRYING

    return MOISTURE_SOURCE_GENERIC


def make_moisture_source_inputs_from_internal_sources(
    internal_source_result,
):
    """
    Convert BuildingInternalSourceResult into moisture.py BuildingMoistureSourceInputs.
    """

    from nexusep.abbey.building.physics.moisture import (
        ZoneMoistureSourceInput,
        BuildingMoistureSourceInputs,
    )

    if not isinstance(internal_source_result, BuildingInternalSourceResult):
        raise TypeError(
            "internal_source_result must be BuildingInternalSourceResult."
        )

    sources_by_zone = {}

    for zone_id in internal_source_result.all_zone_ids():
        summary = internal_source_result.summary_for_zone(zone_id)
        moisture_by_internal_type_kg = summary.moisture_generation_by_source_type_kg()

        zone_sources = []

        for internal_source_type, moisture_kg in moisture_by_internal_type_kg.items():
            moisture_kg_h = average_moisture_generation_kg_h_from_mass(
                moisture_generation_kg=moisture_kg,
                dt_minutes=internal_source_result.dt_minutes,
            )

            if moisture_kg_h <= 0.0:
                continue

            zone_sources.append(
                ZoneMoistureSourceInput(
                    zone_id=zone_id,
                    moisture_generation_kg_h=moisture_kg_h,
                    source_type=_moisture_source_type_from_internal_source_type(
                        internal_source_type
                    ),
                )
            )

        sources_by_zone[zone_id] = zone_sources

    return BuildingMoistureSourceInputs(
        sources_by_zone=sources_by_zone,
    )

def make_physics_inputs_from_internal_sources(
    internal_source_result,
    zone_ids=None,
    solar_gains_by_zone_w=None,
    window_openings=None,
    door_openings=None,
):
    """
    Build all physics-facing source inputs from BuildingInternalSourceResult.

    Returns:
        {
            "thermal_gains": BuildingThermalGains,
            "airflow_control_inputs": BuildingAirflowControlInputs,
            "co2_generation_result": BuildingCO2GenerationResult,
            "moisture_source_inputs": BuildingMoistureSourceInputs,
        }
    """

    if zone_ids is None:
        zone_ids = internal_source_result.all_zone_ids()

    return {
        "thermal_gains": make_thermal_gains_from_internal_sources(
            internal_source_result=internal_source_result,
            zone_ids=zone_ids,
            solar_gains_by_zone_w=solar_gains_by_zone_w or {},
        ),
        "airflow_control_inputs": make_airflow_control_inputs_from_internal_sources(
            internal_source_result=internal_source_result,
            window_openings=window_openings or {},
            door_openings=door_openings or {},
        ),
        "co2_generation_result": make_co2_generation_result_from_internal_sources(
            internal_source_result=internal_source_result,
            zone_ids=zone_ids,
        ),
        "moisture_source_inputs": make_moisture_source_inputs_from_internal_sources(
            internal_source_result=internal_source_result,
        ),
    }


# ============================================================
# COMPATIBILITY AGGREGATORS
# ============================================================

def aggregate_sensible_heat_wh_by_zone(
    records: List[InternalSourceRecord],
) -> Dict[str, float]:
    out = {}

    for record in records:
        out[record.zone_id] = (
            out.get(record.zone_id, 0.0)
            + record.sensible_heat_wh
        )

    return out


def aggregate_sensible_heat_w_by_zone(
    records: List[InternalSourceRecord],
) -> Dict[str, float]:
    out = {}

    for record in records:
        out[record.zone_id] = (
            out.get(record.zone_id, 0.0)
            + record.sensible_heat_w
        )

    return out


def aggregate_latent_heat_wh_by_zone(
    records: List[InternalSourceRecord],
) -> Dict[str, float]:
    out = {}

    for record in records:
        out[record.zone_id] = (
            out.get(record.zone_id, 0.0)
            + record.latent_heat_wh
        )

    return out


def aggregate_latent_heat_w_by_zone(
    records: List[InternalSourceRecord],
) -> Dict[str, float]:
    out = {}

    for record in records:
        out[record.zone_id] = (
            out.get(record.zone_id, 0.0)
            + record.latent_heat_w
        )

    return out


def aggregate_electricity_wh_by_zone(
    records: List[InternalSourceRecord],
) -> Dict[str, float]:
    out = {}

    for record in records:
        out[record.zone_id] = (
            out.get(record.zone_id, 0.0)
            + record.electricity_wh
        )

    return out


def aggregate_co2_generation_m3_h_by_zone(
    records: List[InternalSourceRecord],
) -> Dict[str, float]:
    out = {}

    for record in records:
        out[record.zone_id] = (
            out.get(record.zone_id, 0.0)
            + record.co2_generation_m3_h
        )

    return out


def aggregate_moisture_generation_kg_h_by_zone(
    records: List[InternalSourceRecord],
) -> Dict[str, float]:
    out = {}

    for record in records:
        out[record.zone_id] = (
            out.get(record.zone_id, 0.0)
            + record.moisture_generation_kg_h
        )

    return out


def noise_sources_by_zone(
    records: List[InternalSourceRecord],
) -> Dict[str, List[float]]:
    out = {}

    for record in records:
        if record.noise_source_db <= 0.0:
            continue

        if record.zone_id not in out:
            out[record.zone_id] = []

        out[record.zone_id].append(record.noise_source_db)

    return out


def _zone_for_actor(
    actor_id: str,
    locations: Dict[str, Any],
) -> str:
    if actor_id not in locations:
        return ""

    location = locations[actor_id]

    is_home = bool(_get_attr_or_key(location, "is_home", False))

    if not is_home:
        return ""

    return str(_get_attr_or_key(location, "current_space_id", ""))