"""Reduce official API responses to small, deterministic ingestion fixtures."""

from __future__ import annotations

import argparse
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

from nexusep.validation_data.weather_ingestion import (
    parse_nasa_power_hourly_json,
    parse_pvgis_hourly_json,
)


def _serialized_records(frame) -> list[dict[str, Any]]:
    records = []
    for record in frame.to_dict(orient="records"):
        records.append(
            {
                key: (
                    value.isoformat()
                    if key == "timestamp_utc"
                    else None
                    if isinstance(value, float) and not math.isfinite(value)
                    else value
                )
                for key, value in record.items()
            }
        )
    return records


def _pvgis_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload["outputs"]["hourly"]
    selected = [rows[index] for index in (0, 10, 12, 24, 4128, 4140)]
    reduced = deepcopy(payload)
    reduced["outputs"]["hourly"] = selected
    normalized = parse_pvgis_hourly_json(reduced)
    return {
        "fixture_version": "1.0.0",
        "source": "PVGIS 5.3 seriescalc",
        "source_payload": reduced,
        "expected": {
            "time_semantic": normalized.time_semantic,
            "source_timezone": normalized.source_timezone,
            "missing_canonical_fields": normalized.missing_canonical_fields,
            "derived_fields": normalized.derived_fields,
            "records": _serialized_records(normalized.data),
        },
    }


def _power_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    reduced = deepcopy(payload)
    parameters = reduced["properties"]["parameter"]
    selected_keys = list(parameters["T2M"])[0:13:4]
    for name, values in parameters.items():
        parameters[name] = {key: values[key] for key in selected_keys}
    normalized = parse_nasa_power_hourly_json(reduced)
    return {
        "fixture_version": "1.0.0",
        "source": "NASA POWER hourly API",
        "source_payload": reduced,
        "expected": {
            "time_semantic": normalized.time_semantic,
            "source_timezone": normalized.source_timezone,
            "missing_canonical_fields": normalized.missing_canonical_fields,
            "derived_fields": normalized.derived_fields,
            "records": _serialized_records(normalized.data),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", choices=("pvgis", "nasa_power"))
    parser.add_argument("raw_json", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.raw_json.read_text(encoding="utf-8"))
    fixture = (
        _pvgis_fixture(payload)
        if args.source == "pvgis"
        else _power_fixture(payload)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(fixture, indent=2, allow_nan=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
