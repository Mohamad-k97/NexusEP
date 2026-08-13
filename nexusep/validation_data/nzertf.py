"""Strict decoder for the compact NZERTF virtual-occupant fixture."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from nexusep.schema.timestep import ActionEvent, OccupantStepState

OCCUPANT_IDS = ("parent_a", "parent_b", "child_a", "child_b")
LOCATION_TO_ZONE = {
    "downstairs": "nzertf-downstairs",
    "upstairs": "nzertf-upstairs",
    "away": "nzertf-outside",
}
ACTION_TO_ZONE = {
    "cooktop": "nzertf-downstairs",
    "dishwasher": "nzertf-downstairs",
    "oven": "nzertf-downstairs",
    "first_floor_lights": "nzertf-downstairs",
    "second_floor_lights": "nzertf-upstairs",
}


@dataclass(frozen=True)
class NZERTFVirtualScheduleRow:
    timestamp: datetime
    time_index: int
    occupants: tuple[OccupantStepState, ...]
    active_actions: tuple[ActionEvent, ...]
    first_floor_lighting_power_w: float
    second_floor_lighting_power_w: float


def _binary(row: dict[str, str], field: str) -> bool:
    value = int(row[field])
    if value not in (0, 1):
        raise ValueError(f"{field} must be binary")
    return bool(value)


def decode_virtual_schedule_row(row: dict[str, str]) -> NZERTFVirtualScheduleRow:
    """Decode one normalized row into canonical occupant states and action events."""

    timestamp = datetime.fromisoformat(row["timestamp"])
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    time_index = int(row["time_index"])
    occupants = []
    for occupant_id in OCCUPANT_IDS:
        location = row[f"{occupant_id}_location"]
        if location not in LOCATION_TO_ZONE:
            raise ValueError(f"unknown NZERTF occupant location: {location!r}")
        is_present = location != "away"
        occupants.append(
            OccupantStepState(
                occupant_id=f"nzertf-{occupant_id.replace('_', '-')}",
                dwelling_id="nzertf-dwelling",
                zone_id=LOCATION_TO_ZONE[location],
                activity="awake" if is_present else "away",
                is_present=is_present,
            )
        )

    actions = []
    for action, zone_id in ACTION_TO_ZONE.items():
        if _binary(row, f"{action}_on"):
            actions.append(
                ActionEvent(
                    event_id=f"nzertf.{action}.{time_index}",
                    action=action,
                    occupant_id=None,
                    zone_id=zone_id,
                    status="active",
                )
            )
    first_floor_power = float(row["first_floor_lighting_power_w"])
    second_floor_power = float(row["second_floor_lighting_power_w"])
    if first_floor_power < 0.0 or second_floor_power < 0.0:
        raise ValueError("lighting power cannot be negative")
    return NZERTFVirtualScheduleRow(
        timestamp=timestamp,
        time_index=time_index,
        occupants=tuple(occupants),
        active_actions=tuple(actions),
        first_floor_lighting_power_w=first_floor_power,
        second_floor_lighting_power_w=second_floor_power,
    )


def load_virtual_schedule_fixture(path: str | Path) -> tuple[NZERTFVirtualScheduleRow, ...]:
    """Load a complete fixed-cadence fixture without guessing missing fields."""

    decoded: list[NZERTFVirtualScheduleRow] = []
    with Path(path).open("r", encoding="utf-8", newline="") as stream:
        for raw_row in csv.DictReader(stream):
            row = decode_virtual_schedule_row(raw_row)
            if row.time_index != len(decoded):
                raise ValueError("time_index must be contiguous and zero-based")
            if decoded and (row.timestamp - decoded[-1].timestamp).total_seconds() != 60:
                raise ValueError("fixture timestamps must have a one-minute cadence")
            decoded.append(row)
    if not decoded:
        raise ValueError("virtual schedule fixture is empty")
    return tuple(decoded)
