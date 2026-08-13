"""Build and run the open Annex 71 thermal calibration/holdout alternative."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import subprocess
import zipfile
from datetime import datetime, timedelta
from itertools import pairwise
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

import numpy as np
from scipy.optimize import least_squares

from nexusep.abbey.building.physics.thermal import (
    ThermalTemperatureTarget,
    semi_implicit_temperature_update,
)

RAW_DIRECTORY = Path(
    "data/raw/validation/annex71-twin-houses/03_Data_Main_Experiment"
)
DEFAULT_ARCHIVE = Path(
    "data/raw/validation/annex71-twin-houses/03_Data_Main_Experiment.zip"
)
DEFAULT_FIXTURE = Path(
    "data/validation/fixtures/annex71-twin-houses/"
    "n2-living-main-experiment-hourly.csv"
)
DEFAULT_RESULT = Path(
    "data/validation/fixtures/annex71-twin-houses/"
    "thermal-transfer-result-v1.json"
)
EXPECTED_ARCHIVE_SHA256 = (
    "832754489e0c513c8cb09b7e43d61a9f5249ff5502a781a672cae6d588a876a1"
)
DT_SECONDS = 3600.0
CALIBRATION_FRACTION = 0.60
PARAMETER_NAMES = (
    "capacity_j_k",
    "envelope_conductance_w_k",
    "heat_input_scale",
    "effective_solar_aperture_m2",
)
LOWER_BOUNDS = np.array([1.0e6, 30.0, 0.5, 0.0])
UPPER_BOUNDS = np.array([1.0e8, 1000.0, 1.5, 30.0])
INITIAL_PARAMETERS = np.array([2.0e7, 250.0, 1.0, 4.0])
CELL_REFERENCE = re.compile(r"([A-Z]+)([0-9]+)")


def ensure_extracted(archive: Path, raw_directory: Path) -> None:
    """Extract the Deflate64 source archive with 7-Zip when it is absent."""

    marker = (
        raw_directory
        / "Experiment1 - open"
        / "Twin_house_N2_exp1_full1_60min.xlsx"
    )
    if marker.is_file():
        return
    candidates = (
        shutil.which("7z"),
        shutil.which("7z.exe"),
        "C:/Program Files/7-Zip/7z.exe",
    )
    executable = next(
        (Path(item) for item in candidates if item and Path(item).is_file()), None
    )
    if executable is None:
        raise RuntimeError(
            "Annex 71 uses Deflate64 compression. Install 7-Zip or extract "
            f"{archive} so that {marker} exists."
        )
    raw_directory.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(executable),
            "x",
            str(archive),
            f"-o{raw_directory.parent}",
            "-y",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    if not marker.is_file():
        raise RuntimeError(f"7-Zip extraction did not create {marker}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _column_index(reference: str) -> int:
    match = CELL_REFERENCE.fullmatch(reference)
    if match is None:
        raise ValueError(f"invalid Excel cell reference: {reference!r}")
    result = 0
    for character in match.group(1):
        result = result * 26 + ord(character) - ord("A") + 1
    return result - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        payload = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ElementTree.fromstring(payload)
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    return [
        "".join(node.text or "" for node in item.iter(namespace + "t"))
        for item in root.findall(namespace + "si")
    ]


def read_first_worksheet(path: Path) -> list[dict[str, str | float | None]]:
    """Read the first worksheet with only Python's standard XLSX primitives."""

    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(path) as archive:
        shared_strings = _shared_strings(archive)
        rows: list[list[str | float | None]] = []
        with archive.open("xl/worksheets/sheet1.xml") as worksheet:
            for _event, element in ElementTree.iterparse(worksheet, events=("end",)):
                if element.tag != namespace + "row":
                    continue
                values: dict[int, str | float | None] = {}
                for cell in element.findall(namespace + "c"):
                    reference = cell.attrib.get("r")
                    if reference is None:
                        continue
                    value_node = cell.find(namespace + "v")
                    raw = None if value_node is None else value_node.text
                    cell_type = cell.attrib.get("t")
                    if raw is None:
                        value: str | float | None = None
                    elif cell_type == "s":
                        value = shared_strings[int(raw)]
                    elif cell_type == "b":
                        value = "1" if raw == "1" else "0"
                    else:
                        try:
                            value = float(raw)
                        except ValueError:
                            value = raw
                    values[_column_index(reference)] = value
                if values:
                    row = [None] * (max(values) + 1)
                    for index, value in values.items():
                        row[index] = value
                    rows.append(row)
                element.clear()
    if len(rows) < 2:
        raise ValueError(f"workbook has no data rows: {path}")
    headers = [None if value is None else str(value) for value in rows[0]]
    output = []
    for row in rows[1:]:
        record = {
            header: row[index] if index < len(row) else None
            for index, header in enumerate(headers)
            if header is not None
        }
        output.append(record)
    return output


def _finite_float(value: str | float | None) -> float | None:
    if value is None or value == "NA":
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _excel_timestamp(serial: float) -> datetime:
    return (
        datetime(1899, 12, 30, tzinfo=ZoneInfo("Europe/Berlin"))
        + timedelta(days=serial)
    ).replace(microsecond=0)


def _indexed(records: list[dict[str, str | float | None]]) -> dict[float, dict]:
    indexed = {}
    for record in records:
        serial = _finite_float(record.get("DATE"))
        if serial is not None:
            indexed[round(serial, 9)] = record
    return indexed


def build_records(raw_directory: Path) -> list[dict[str, float | str]]:
    full1 = read_first_worksheet(
        raw_directory
        / "Experiment1 - open"
        / "Twin_house_N2_exp1_full1_60min.xlsx"
    )
    full2 = _indexed(
        read_first_worksheet(
            raw_directory
            / "Experiment1 - open"
            / "Twin_house_N2_exp1_full2_60min.xlsx"
        )
    )
    weather = _indexed(
        read_first_worksheet(
            raw_directory
            / "Weather Data"
            / "Twin_house_weather_exp1_60min_compensated.xlsx"
        )
    )
    records: list[dict[str, float | str]] = []
    for row in full1:
        serial = _finite_float(row.get("DATE"))
        if serial is None:
            continue
        key = round(serial, 9)
        other = full2.get(key)
        weather_row = weather.get(key)
        if other is None or weather_row is None:
            continue
        fields = {
            "excel_serial": serial,
            "air_temperature_c": _finite_float(
                row.get("n2_aroom_living_110_AT")
            ),
            "outdoor_temperature_c": _finite_float(
                weather_row.get("AmbientAirTemperature")
            ),
            "heating_power_w": _finite_float(
                row.get("n2_aroom_living_heat_elP")
            ),
            "internal_gain_w": _finite_float(
                row.get("n2_aroom_living_IHS_elP")
            ),
            "solar_south_w_m2": _finite_float(other.get("n2_sol_S")),
            "ventilation_supply_temperature_c": _finite_float(
                row.get("n2_Vent_living_SUA_AT")
            ),
            "ventilation_supply_flow_m3_h": _finite_float(
                row.get("n2_Vent_living_SUA_VFR")
            ),
            "child1_window_position": _finite_float(
                row.get("n2_aroom_child1_win_pos")
            ),
            "kitchen_door_position": _finite_float(
                row.get("n2_aroom_kitchen_door_pos")
            ),
        }
        if any(value is None for value in fields.values()):
            continue
        records.append(
            {
                "timestamp": _excel_timestamp(serial).isoformat(),
                **{name: float(value) for name, value in fields.items()},
            }
        )
    if len(records) < 24 * 30:
        raise ValueError("Annex 71 alternative has fewer than 30 valid days")
    for previous, current in pairwise(records):
        delta = current["excel_serial"] - previous["excel_serial"]
        if not math.isclose(float(delta), 1.0 / 24.0, abs_tol=1e-8):
            raise ValueError("Annex 71 records are not a contiguous hourly series")
    return records


def _arrays(records: list[dict[str, float | str]]) -> dict[str, np.ndarray]:
    names = (
        "air_temperature_c",
        "outdoor_temperature_c",
        "heating_power_w",
        "internal_gain_w",
        "solar_south_w_m2",
        "ventilation_supply_temperature_c",
        "ventilation_supply_flow_m3_h",
        "child1_window_position",
        "kitchen_door_position",
    )
    return {
        name: np.asarray([float(record[name]) for record in records])
        for name in names
    }


def simulate(parameters: np.ndarray, arrays: dict[str, np.ndarray]) -> np.ndarray:
    capacity_j_k, conductance_w_k, heat_scale, solar_aperture_m2 = parameters
    measured = arrays["air_temperature_c"]
    prediction = np.empty_like(measured)
    prediction[0] = measured[0]
    for index in range(1, measured.size):
        flow_m3_h = max(0.0, arrays["ventilation_supply_flow_m3_h"][index])
        ventilation_h_w_k = 1.2 * 1005.0 * flow_m3_h / 3600.0
        gains_w = heat_scale * (
            arrays["heating_power_w"][index]
            + arrays["internal_gain_w"][index]
        ) + solar_aperture_m2 * max(0.0, arrays["solar_south_w_m2"][index])
        prediction[index] = semi_implicit_temperature_update(
            capacity_j_k=float(capacity_j_k),
            old_temperature_c=float(prediction[index - 1]),
            targets=[
                ThermalTemperatureTarget(
                    "outdoor",
                    "outside",
                    float(arrays["outdoor_temperature_c"][index]),
                    float(conductance_w_k),
                ),
                ThermalTemperatureTarget(
                    "ventilation_supply",
                    "ventilation",
                    float(arrays["ventilation_supply_temperature_c"][index]),
                    float(ventilation_h_w_k),
                ),
            ],
            gain_w=float(gains_w),
            dt_seconds=DT_SECONDS,
        )
    return prediction


def _metrics(measured: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    residual = predicted - measured
    return {
        "count": int(measured.size),
        "bias_c": float(np.mean(residual)),
        "mae_c": float(np.mean(np.abs(residual))),
        "rmse_c": float(np.sqrt(np.mean(np.square(residual)))),
        "maximum_abs_error_c": float(np.max(np.abs(residual))),
        "correlation": float(np.corrcoef(measured, predicted)[0, 1]),
    }


def run_study(records: list[dict[str, float | str]]) -> dict[str, object]:
    arrays = _arrays(records)
    split_index = int(len(records) * CALIBRATION_FRACTION)

    def residual(parameters: np.ndarray) -> np.ndarray:
        prediction = simulate(parameters, arrays)
        return prediction[1:split_index] - arrays["air_temperature_c"][1:split_index]

    fit = least_squares(
        residual,
        INITIAL_PARAMETERS,
        bounds=(LOWER_BOUNDS, UPPER_BOUNDS),
        x_scale="jac",
        max_nfev=500,
    )
    prediction = simulate(fit.x, arrays)
    calibration = _metrics(
        arrays["air_temperature_c"][1:split_index], prediction[1:split_index]
    )
    holdout = _metrics(
        arrays["air_temperature_c"][split_index:], prediction[split_index:]
    )
    rmse_pass = holdout["rmse_c"] <= 1.0
    bias_pass = abs(holdout["bias_c"]) <= 0.5
    calibration_solar_mean = float(
        np.mean(arrays["solar_south_w_m2"][:split_index])
    )
    holdout_solar_mean = float(
        np.mean(arrays["solar_south_w_m2"][split_index:])
    )
    calibration_operated_opening_hours = int(
        np.count_nonzero(
            (arrays["child1_window_position"][:split_index] > 0.01)
            | (arrays["kitchen_door_position"][:split_index] < 0.99)
        )
    )
    holdout_operated_opening_hours = int(
        np.count_nonzero(
            (arrays["child1_window_position"][split_index:] > 0.01)
            | (arrays["kitchen_door_position"][split_index:] < 0.99)
        )
    )
    bounds_margin = np.minimum(
        (fit.x - LOWER_BOUNDS) / (UPPER_BOUNDS - LOWER_BOUNDS),
        (UPPER_BOUNDS - fit.x) / (UPPER_BOUNDS - LOWER_BOUNDS),
    )
    return {
        "fit_success": bool(fit.success),
        "fit_message": fit.message,
        "parameter_order": list(PARAMETER_NAMES),
        "fitted_parameters": {
            name: float(value)
            for name, value in zip(PARAMETER_NAMES, fit.x, strict=True)
        },
        "physical_bounds": {
            name: {"lower": float(lower), "upper": float(upper)}
            for name, lower, upper in zip(
                PARAMETER_NAMES, LOWER_BOUNDS, UPPER_BOUNDS, strict=True
            )
        },
        "minimum_fractional_distance_from_bound": float(np.min(bounds_margin)),
        "parameter_bounds_gate_passed": bool(np.min(bounds_margin) >= 0.01),
        "forcing_shift_audit": {
            "calibration_mean_south_solar_w_m2": calibration_solar_mean,
            "holdout_mean_south_solar_w_m2": holdout_solar_mean,
            "holdout_to_calibration_solar_ratio": (
                holdout_solar_mean / calibration_solar_mean
            ),
            "calibration_operated_opening_hours": (
                calibration_operated_opening_hours
            ),
            "holdout_operated_opening_hours": holdout_operated_opening_hours,
        },
        "calibration": {
            "start_timestamp": records[1]["timestamp"],
            "end_timestamp_inclusive": records[split_index - 1]["timestamp"],
            **calibration,
        },
        "untouched_holdout": {
            "start_timestamp": records[split_index]["timestamp"],
            "end_timestamp_inclusive": records[-1]["timestamp"],
            **holdout,
        },
        "predeclared_acceptance": {
            "rmse_c_less_than_or_equal_1_0": rmse_pass,
            "absolute_bias_c_less_than_or_equal_0_5": bias_pass,
            "passed": bool(fit.success and rmse_pass and bias_pass),
        },
        "protocol_audit": {
            "implementation_under_test": "single_node_thermal_update_helper",
            "production_object_adapter_exercised": False,
            "production_array_adapter_exercised": False,
            "official_blind_open_protocol_followed": False,
            "official_experimental_periods_followed": False,
            "split_method": "arbitrary_chronological_60_40",
            "unmapped_operated_openings_present": bool(
                calibration_operated_opening_hours
                or holdout_operated_opening_hours
            ),
            "full_multizone_topology_mapped": False,
            "valid_empirical_thermal_claim": False,
            "classification": "mapping_diagnostic_rejected",
            "reasons": [
                "The helper is not the production multizone air/mass engine.",
                "The arbitrary split crosses changing solar and opening-operation regimes.",
                "Interzone, envelope, mass-node, and operated-opening inputs are not mapped.",
                "Measured target temperatures were exposed during fitting, so this is not the official blind/open workflow.",
            ],
        },
        "scientific_validation_gate_passed": False,
    }


def write_fixture(records: list[dict[str, float | str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    split_index = int(len(records) * CALIBRATION_FRACTION)
    fieldnames = [
        "timestamp",
        "air_temperature_c",
        "outdoor_temperature_c",
        "heating_power_w",
        "internal_gain_w",
        "solar_south_w_m2",
        "ventilation_supply_temperature_c",
        "ventilation_supply_flow_m3_h",
        "child1_window_position",
        "kitchen_door_position",
        "split_role",
        "experimental_regime",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, record in enumerate(records):
            writer.writerow(
                {
                    name: record[name]
                    for name in fieldnames
                    if name not in {"split_role", "experimental_regime"}
                }
                | {
                    "split_role": (
                        "calibration" if index < split_index else "untouched_holdout"
                    ),
                    "experimental_regime": (
                        "operated_openings_observed"
                        if (
                            float(record["child1_window_position"]) > 0.01
                            or float(record["kitchen_door_position"]) < 0.99
                        )
                        else "fixed_openings_observed"
                    ),
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--raw-directory", type=Path, default=RAW_DIRECTORY)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    args = parser.parse_args()
    archive_hash = sha256_file(args.archive)
    if archive_hash != EXPECTED_ARCHIVE_SHA256:
        raise ValueError(f"unexpected Annex 71 archive SHA-256: {archive_hash}")
    ensure_extracted(args.archive, args.raw_directory)
    records = build_records(args.raw_directory)
    write_fixture(records, args.fixture)
    study = run_study(records)
    payload = {
        "artifact_version": "1.0.0",
        "validation_category": "empirical_validation_alternative",
        "phase": "4.9-alternative",
        "study_id": "annex71-n2-living-thermal-transfer-v1",
        "source": {
            "title": "IEA EBC Annex 71 Twin House Main Experiment",
            "doi": "10.24406/fordatis/76.2",
            "license": "CC BY-SA 4.0",
            "download_url": (
                "https://fordatis.fraunhofer.de/bitstream/fordatis/161.2/4/"
                "03_Data_Main_Experiment.zip"
            ),
            "archive_sha256": archive_hash,
        },
        "scope": (
            "Forensic N2 living-room hourly single-node mapping diagnostic; "
            "not a production-engine or official blind/open validation"
        ),
        "record_count": len(records),
        "fixture": {
            "path": args.fixture.as_posix(),
            "sha256": sha256_file(args.fixture),
            "byte_size": args.fixture.stat().st_size,
        },
        "study": study,
        "blocked_gate_classification": "blocked and rejected with alternative",
        "reproduce": "uv run python scripts/validation_data/run_annex71_thermal_transfer.py",
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["study"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
