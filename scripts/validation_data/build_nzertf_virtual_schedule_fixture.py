"""Build a compact deterministic NZERTF virtual-occupant schedule fixture."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta
from pathlib import Path

OCCUPANT_COLUMNS = {
    "parent_a": ("Load_StatusSensHeatPrntADOWN", "Load_StatusSensHeatPrntAUP"),
    "parent_b": ("Load_StatusSensHeatPrntBDOWN", "Load_StatusSensHeatPrntBUP"),
    "child_a": ("Load_StatusSensHeatChildADOWN", "Load_StatusSensHeatChildAUP"),
    "child_b": ("Load_StatusSensHeatChildBDOWN", "Load_StatusSensHeatChildBUP"),
}
FIRST_FLOOR_LIGHT_COLUMNS = (
    "Load_StatusDRLights",
    "Load_StatusEntryHallLights",
    "Load_StatusKitchenLightsA",
    "Load_StatusKitchenLightsB",
    "Load_StatusKitchenLightsC",
    "Load_StatusLRLights1",
    "Load_StatusLRLights2",
    "Load_StatusLRLights3",
)
SECOND_FLOOR_LIGHT_COLUMNS = (
    "Load_StatusBA1Lights",
    "Load_StatusBA2Lights",
    "Load_StatusBR2Lights",
    "Load_StatusBR3Lights",
    "Load_StatusBR4Lights",
    "Load_StatusMBALights",
    "Load_StatusMBRLights1",
    "Load_StatusMBRLights2",
)
OUTPUT_FIELDS = (
    "timestamp",
    "source_timestamp",
    "time_index",
    "parent_a_location",
    "parent_b_location",
    "child_a_location",
    "child_b_location",
    "cooktop_on",
    "dishwasher_on",
    "oven_on",
    "first_floor_lights_on",
    "second_floor_lights_on",
    "first_floor_lighting_power_w",
    "second_floor_lighting_power_w",
)


def _flag(row: dict[str, str], field: str) -> int:
    value = float(row[field])
    if value not in (0.0, 1.0):
        raise ValueError(f"{field} is not binary: {value}")
    return int(value)


def _location(row: dict[str, str], down_field: str, up_field: str) -> str:
    down, up = _flag(row, down_field), _flag(row, up_field)
    if down and up:
        raise ValueError("occupant is simultaneously upstairs and downstairs")
    if down:
        return "downstairs"
    if up:
        return "upstairs"
    return "away"


def _any_flag(row: dict[str, str], fields: tuple[str, ...]) -> int:
    return int(any(_flag(row, field) for field in fields))


def build_fixture(source: Path, output: Path, *, row_count: int = 900) -> int:
    """Select a pre-gap record block and normalize documented flags."""

    selected: list[dict[str, str | int | float]] = []
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError("NZERTF source lacks a CSV header")
        required = {
            "Timestamp",
            "TimeStamp_Count",
            "Load_StatusApplianceCooktop",
            "Load_StatusApplianceDishwasher",
            "Load_StatusApplianceOven",
            "Load_1stFloorLightsPowerUsage",
            "Load_2ndFloorLightsPowerUsage",
            *FIRST_FLOOR_LIGHT_COLUMNS,
            *SECOND_FLOOR_LIGHT_COLUMNS,
            *(field for pair in OCCUPANT_COLUMNS.values() for field in pair),
        }
        missing = sorted(required - set(reader.fieldnames))
        if missing:
            raise ValueError(f"NZERTF source lacks required columns: {missing}")

        previous_timestamp: datetime | None = None
        first_timestamp: datetime | None = None
        previous_source_count: int | None = None
        for row in reader:
            if None in row or any(row.get(field) in (None, "") for field in required):
                continue
            timestamp = datetime.fromisoformat(row["Timestamp"])
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("NZERTF timestamp is not timezone-aware")
            if previous_timestamp is not None:
                elapsed_seconds = (timestamp - previous_timestamp).total_seconds()
                if not 55.0 <= elapsed_seconds <= 65.0:
                    raise ValueError(
                        "source timestamp departed from the expected one-minute "
                        f"cadence by more than five seconds: {elapsed_seconds}"
                    )
            source_count = int(row["TimeStamp_Count"])
            if previous_source_count is not None and source_count != previous_source_count + 1:
                raise ValueError("TimeStamp_Count is not contiguous")
            if first_timestamp is None:
                first_timestamp = timestamp
            previous_timestamp = timestamp
            previous_source_count = source_count
            canonical_timestamp = first_timestamp + timedelta(minutes=len(selected))

            normalized: dict[str, str | int | float] = {
                "timestamp": canonical_timestamp.isoformat(),
                "source_timestamp": timestamp.isoformat(),
                "time_index": len(selected),
                "cooktop_on": _flag(row, "Load_StatusApplianceCooktop"),
                "dishwasher_on": _flag(row, "Load_StatusApplianceDishwasher"),
                "oven_on": _flag(row, "Load_StatusApplianceOven"),
                "first_floor_lights_on": _any_flag(
                    row, FIRST_FLOOR_LIGHT_COLUMNS
                ),
                "second_floor_lights_on": _any_flag(
                    row, SECOND_FLOOR_LIGHT_COLUMNS
                ),
                "first_floor_lighting_power_w": float(
                    row["Load_1stFloorLightsPowerUsage"]
                ),
                "second_floor_lighting_power_w": float(
                    row["Load_2ndFloorLightsPowerUsage"]
                ),
            }
            for occupant_id, (down_field, up_field) in OCCUPANT_COLUMNS.items():
                normalized[f"{occupant_id}_location"] = _location(
                    row, down_field, up_field
                )
            selected.append(normalized)
            if len(selected) == row_count:
                break

    if len(selected) != row_count:
        raise ValueError(f"expected {row_count} complete rows, found {len(selected)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(selected)
    return len(selected)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--row-count", type=int, default=900)
    args = parser.parse_args(argv)
    count = build_fixture(args.source, args.output, row_count=args.row_count)
    print(f"wrote {count} normalized rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
