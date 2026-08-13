"""Compare NexusEP ideal/full-capacity HVAC with EnergyPlus Ideal Loads.

The comparison is intentionally narrow: heating, cooling, deadband, delivered
power, and one-hour energy integration. It does not compare equipment curves,
fans, ducts, cycling, latent control, or part-load performance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path

from nexusep.abbey.building.controllers import ThermostatController
from nexusep.abbey.building.model import ZoneState
from nexusep.abbey.building.systems import (
    ZoneControlState,
    ZoneSystemSpec,
    cooling_power_w_from_zone_control_command,
    heating_power_w_from_zone_control_command,
)

POWER_TOLERANCE_W = 1e-3
ENERGY_TOLERANCE_WH = 1e-3
TEMPERATURE_TOLERANCE_C = 1e-6


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _column(fieldnames: list[str], *parts: str) -> str:
    matches = [
        name
        for name in fieldnames
        if all(part.upper() in name.upper() for part in parts)
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one output column for {parts}, found {matches}")
    return matches[0]


def _mean(rows: list[dict[str, str]], column: str) -> float:
    return sum(float(row[column]) for row in rows) / len(rows)


def _maximum_absolute(rows: list[dict[str, str]], column: str) -> float:
    return max(abs(float(row[column])) for row in rows)


def _energyplus_summary(csv_path: Path) -> dict[str, float | int]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    if len(rows) != 24:
        raise ValueError(f"expected 24 hourly rows, found {len(rows)}")

    heating_rate = _column(
        fieldnames, "HEATING ZONE IDEAL LOADS", "SENSIBLE HEATING RATE"
    )
    heating_energy = _column(
        fieldnames, "HEATING ZONE IDEAL LOADS", "SENSIBLE HEATING ENERGY"
    )
    heating_cooling_rate = _column(
        fieldnames, "HEATING ZONE IDEAL LOADS", "SENSIBLE COOLING RATE"
    )
    cooling_rate = _column(
        fieldnames, "COOLING ZONE IDEAL LOADS", "SENSIBLE COOLING RATE"
    )
    cooling_energy = _column(
        fieldnames, "COOLING ZONE IDEAL LOADS", "SENSIBLE COOLING ENERGY"
    )
    cooling_heating_rate = _column(
        fieldnames, "COOLING ZONE IDEAL LOADS", "SENSIBLE HEATING RATE"
    )
    deadband_heating_rate = _column(
        fieldnames, "DEADBAND ZONE IDEAL LOADS", "SENSIBLE HEATING RATE"
    )
    deadband_cooling_rate = _column(
        fieldnames, "DEADBAND ZONE IDEAL LOADS", "SENSIBLE COOLING RATE"
    )
    heating_temperature = _column(
        fieldnames, "HEATING ZONE:ZONE AIR TEMPERATURE"
    )
    cooling_temperature = _column(
        fieldnames, "COOLING ZONE:ZONE AIR TEMPERATURE"
    )
    deadband_temperature = _column(
        fieldnames, "DEADBAND ZONE:ZONE AIR TEMPERATURE"
    )

    return {
        "hour_count": len(rows),
        "heating_power_w": _mean(rows, heating_rate),
        "heating_energy_wh_per_hour": _mean(rows, heating_energy) / 3600.0,
        "heating_zone_cooling_power_w_max_abs": _maximum_absolute(
            rows, heating_cooling_rate
        ),
        "cooling_power_w": _mean(rows, cooling_rate),
        "cooling_energy_wh_per_hour": _mean(rows, cooling_energy) / 3600.0,
        "cooling_zone_heating_power_w_max_abs": _maximum_absolute(
            rows, cooling_heating_rate
        ),
        "deadband_heating_power_w_max_abs": _maximum_absolute(
            rows, deadband_heating_rate
        ),
        "deadband_cooling_power_w_max_abs": _maximum_absolute(
            rows, deadband_cooling_rate
        ),
        "heating_zone_temperature_c": _mean(rows, heating_temperature),
        "cooling_zone_temperature_c": _mean(rows, cooling_temperature),
        "deadband_zone_temperature_c": _mean(rows, deadband_temperature),
    }


def _nexusep_summary() -> dict[str, float]:
    controller = ThermostatController(deadband_c=1.0)
    control = ZoneControlState(
        zone_id="zone",
        dwelling_id="dwelling",
        building_id="building",
        heating_mode="semi_auto",
        heating_setpoint_c=20.0,
        cooling_mode="semi_auto",
        cooling_setpoint_c=24.0,
        thermostat_deadband_c=1.0,
        ventilation_mode="off",
        lighting_mode="off",
        window_mode="off",
        shading_mode="off",
    )

    def command(temperature_c: float, heating_w: float, cooling_w: float):
        state = ZoneState(
            zone_id="zone",
            dwelling_id="dwelling",
            building_id="building",
            indoor_temp_c=temperature_c,
        )
        system = ZoneSystemSpec(
            zone_id="zone",
            dwelling_id="dwelling",
            building_id="building",
            heating_capacity_w=heating_w,
            cooling_capacity_w=cooling_w,
            has_heating=True,
            has_cooling=True,
            has_ventilation=False,
            has_lighting=False,
            has_operable_window=False,
            has_shading=False,
        )
        return controller.step(state, control, system), system

    heating, heating_system = command(19.0, 1000.0, 1500.0)
    cooling, cooling_system = command(25.0, 1000.0, 1500.0)
    deadband, deadband_system = command(22.0, 1000.0, 1500.0)
    heating_power_w = heating_power_w_from_zone_control_command(
        heating, heating_system
    )
    cooling_power_w = cooling_power_w_from_zone_control_command(
        cooling, cooling_system
    )
    return {
        "heating_power_w": heating_power_w,
        "heating_energy_wh_per_hour": heating_power_w,
        "heating_zone_cooling_power_w_max_abs": abs(
            cooling_power_w_from_zone_control_command(heating, heating_system)
        ),
        "cooling_power_w": cooling_power_w,
        "cooling_energy_wh_per_hour": cooling_power_w,
        "cooling_zone_heating_power_w_max_abs": abs(
            heating_power_w_from_zone_control_command(cooling, cooling_system)
        ),
        "deadband_heating_power_w_max_abs": abs(
            heating_power_w_from_zone_control_command(deadband, deadband_system)
        ),
        "deadband_cooling_power_w_max_abs": abs(
            cooling_power_w_from_zone_control_command(deadband, deadband_system)
        ),
    }


def compare(
    *,
    energyplus_exe: Path,
    input_file: Path,
    weather_file: Path,
    output_directory: Path,
) -> dict[str, object]:
    output_directory.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            str(energyplus_exe),
            "-x",
            "-w",
            str(weather_file),
            "-d",
            str(output_directory),
            str(input_file),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    error_log = (output_directory / "eplusout.err").read_text(
        encoding="utf-8", errors="replace"
    )
    if completed.returncode != 0 or "EnergyPlus Completed Successfully" not in error_log:
        raise RuntimeError(
            f"EnergyPlus failed with code {completed.returncode}:\n{error_log}"
        )
    if "0 Warning; 0 Severe Errors" not in error_log:
        raise RuntimeError(f"EnergyPlus completed with diagnostics:\n{error_log}")

    version = subprocess.run(
        [str(energyplus_exe), "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    reference = _energyplus_summary(output_directory / "eplusout.csv")
    candidate = _nexusep_summary()
    comparison: dict[str, object] = {}
    passed = True
    for quantity, nexus_value in candidate.items():
        reference_value = float(reference[quantity])
        tolerance = (
            ENERGY_TOLERANCE_WH if "energy_wh" in quantity else POWER_TOLERANCE_W
        )
        absolute_difference = abs(float(nexus_value) - reference_value)
        item_passed = absolute_difference <= tolerance
        passed = passed and item_passed
        comparison[quantity] = {
            "energyplus": reference_value,
            "nexusep": nexus_value,
            "absolute_difference": absolute_difference,
            "absolute_tolerance": tolerance,
            "passed": item_passed,
        }

    temperature_checks = {
        "heating_zone_temperature_c": 20.0,
        "cooling_zone_temperature_c": 24.0,
        "deadband_zone_temperature_c": 23.0,
    }
    for quantity, expected in temperature_checks.items():
        absolute_difference = abs(float(reference[quantity]) - expected)
        item_passed = absolute_difference <= TEMPERATURE_TOLERANCE_C
        passed = passed and item_passed
        comparison[quantity] = {
            "energyplus": reference[quantity],
            "expected": expected,
            "absolute_difference": absolute_difference,
            "absolute_tolerance": TEMPERATURE_TOLERANCE_C,
            "passed": item_passed,
        }

    return {
        "result_id": "energyplus-ideal-loads-25.1.0",
        "validation_category": "comparative_validation",
        "model_claim": "HVAC-1",
        "energyplus_version": version,
        "energyplus_executable_sha256": _sha256(energyplus_exe),
        "input_file_sha256": _sha256(input_file),
        "weather_file_sha256": _sha256(weather_file),
        "hour_count": reference["hour_count"],
        "comparison": comparison,
        "passed": passed,
        "scope": (
            "Ideal sensible delivered load, mode exclusivity, deadband, and "
            "one-hour power-to-energy integration only."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--energyplus-exe", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--weather", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args(argv)
    result = compare(
        energyplus_exe=args.energyplus_exe.resolve(),
        input_file=args.input.resolve(),
        weather_file=args.weather.resolve(),
        output_directory=args.output_directory.resolve(),
    )
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.result_json is not None:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
