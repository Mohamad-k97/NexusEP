"""
ABBEY internal source mapping.

Maps action/appliance records to physical source terms:
- sensible heat
- latent heat placeholder
- noise placeholder

No physics solver here.
This only prepares source records for later thermal/air/noise modules.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional


def _clamp_fraction(value: float) -> float:
    value = float(value)

    if value < 0.0:
        return 0.0

    if value > 1.0:
        return 1.0

    return value

@dataclass
class ActionInternalSourceSpec:
    action_name: str
    default_zone_role: str = "current"

    sensible_heat_fraction: float = 1.0
    latent_heat_fraction: float = 0.0
    noise_source_db: float = 0.0

    def __post_init__(self) -> None:
        self.sensible_heat_fraction = _clamp_fraction(
            self.sensible_heat_fraction
        )
        self.latent_heat_fraction = _clamp_fraction(
            self.latent_heat_fraction
        )

        if self.noise_source_db < 0.0:
            raise ValueError(
                "noise_source_db cannot be negative for action "
                + self.action_name
            )


@dataclass
class InternalSourceRecord:
    action_name: str
    actor_id: str
    zone_id: str

    power_w: float = 0.0
    energy_wh: float = 0.0
    sensible_heat_wh: float = 0.0
    latent_heat_wh: float = 0.0
    noise_source_db: float = 0.0


DEFAULT_ACTION_INTERNAL_SOURCE_SPECS = {
    "cook": ActionInternalSourceSpec(
        action_name="cook",
        default_zone_role="kitchen",
        sensible_heat_fraction=0.85,
        latent_heat_fraction=0.15,
        noise_source_db=50.0,
    ),
    "make_hot_drink": ActionInternalSourceSpec(
        action_name="make_hot_drink",
        default_zone_role="kitchen",
        sensible_heat_fraction=0.90,
        latent_heat_fraction=0.10,
        noise_source_db=40.0,
    ),
    "shower": ActionInternalSourceSpec(
        action_name="shower",
        default_zone_role="bathroom",
        sensible_heat_fraction=0.30,
        latent_heat_fraction=0.70,
        noise_source_db=45.0,
    ),
    "run_washing_machine": ActionInternalSourceSpec(
        action_name="run_washing_machine",
        default_zone_role="laundry",
        sensible_heat_fraction=0.90,
        latent_heat_fraction=0.05,
        noise_source_db=55.0,
    ),
    "use_laptop": ActionInternalSourceSpec(
        action_name="use_laptop",
        default_zone_role="work",
        sensible_heat_fraction=1.0,
        latent_heat_fraction=0.0,
        noise_source_db=25.0,
    ),
    "watch_tv": ActionInternalSourceSpec(
        action_name="watch_tv",
        default_zone_role="living_room",
        sensible_heat_fraction=1.0,
        latent_heat_fraction=0.0,
        noise_source_db=45.0,
    ),
    "listen_music": ActionInternalSourceSpec(
        action_name="listen_music",
        default_zone_role="living_room",
        sensible_heat_fraction=1.0,
        latent_heat_fraction=0.0,
        noise_source_db=50.0,
    ),
}


def get_action_internal_source_spec(
    action_name: str,
) -> ActionInternalSourceSpec:
    return DEFAULT_ACTION_INTERNAL_SOURCE_SPECS.get(
        action_name,
        ActionInternalSourceSpec(
            action_name=action_name,
            default_zone_role="current",
            sensible_heat_fraction=1.0,
            latent_heat_fraction=0.0,
            noise_source_db=0.0,
        ),
    )


def internal_source_records_from_chunk_records(
    chunk_records: List[Mapping[str, Any]],
    locations: Optional[Dict[str, Any]] = None,
) -> List[InternalSourceRecord]:
    """
    Convert chunk_records into physical source records.

    Preferred source zone:
        item["target_space_id"]

    Fallback:
        actor current location, if available
    """

    locations = locations or {}
    records = []

    for chunk in chunk_records:
        breakdown = chunk.get("power_breakdown", [])

        for item in breakdown:
            if not isinstance(item, Mapping):
                continue

            action_name = str(item.get("name", ""))
            actor_id = str(item.get("actor_id", ""))

            power_w = float(item.get("power_w", 0.0))
            energy_wh = float(item.get("energy_wh", 0.0))

            if energy_wh <= 0.0 and power_w <= 0.0:
                continue

            zone_id = str(item.get("target_space_id", ""))

            if not zone_id:
                zone_id = _zone_for_actor(
                    actor_id=actor_id,
                    locations=locations,
                )

            if not zone_id:
                continue

            spec = get_action_internal_source_spec(action_name)

            sensible_heat_wh = energy_wh * spec.sensible_heat_fraction
            latent_heat_wh = energy_wh * spec.latent_heat_fraction

            records.append(
                InternalSourceRecord(
                    action_name=action_name,
                    actor_id=actor_id,
                    zone_id=zone_id,
                    power_w=power_w,
                    energy_wh=energy_wh,
                    sensible_heat_wh=sensible_heat_wh,
                    latent_heat_wh=latent_heat_wh,
                    noise_source_db=spec.noise_source_db,
                )
            )

    return records


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

    is_home = _get_attr_or_key(location, "is_home", False)

    if not is_home:
        return ""

    return str(_get_attr_or_key(location, "current_space_id", ""))


def _get_attr_or_key(
    obj: Any,
    key: str,
    default: Any = None,
) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)

    return getattr(obj, key, default)

