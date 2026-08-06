"""Build deterministic object-runner golden summaries for Phase 1.5."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import random
import time
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from nexusep.abbey.building.physics.weather import WeatherState
from nexusep.abbey.simulation.runner import AbbeySimulation


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_SNAPSHOT = (
    PROJECT_ROOT / "artifacts" / "baseline" / "inputs" / "abbey_config_phase_1_5.jsonc"
)
RUN_ROOT = PROJECT_ROOT / "artifacts" / "benchmarks" / "phase1_5" / "object"
GOLDEN_PATH = (
    PROJECT_ROOT / "artifacts" / "baseline" / "deterministic_object_manifest.json"
)

APPLICATION_SEED = 20260806
NUMPY_SEED = 20260806
PYTHON_HASH_SEED = 0
TIMEZONE_NAME = "Europe/Rome"
START_TIMESTAMP = "2026-01-01T00:00:00+01:00"
FLOAT_RTOL = 1.0e-12
FLOAT_ATOL = 1.0e-12


@dataclass(frozen=True)
class Scenario:
    name: str
    timesteps: int
    dt_minutes: int
    description: str

    @property
    def simulated_hours(self) -> float:
        return self.timesteps * self.dt_minutes / 60.0


SCENARIOS = {
    "smoke": Scenario(
        name="smoke",
        timesteps=24,
        dt_minutes=60,
        description="24 deterministic hourly timesteps",
    ),
    "short_year": Scenario(
        name="short_year",
        timesteps=720,
        dt_minutes=60,
        description="30 deterministic days used as the short-year reference",
    ),
}


class DeterministicWeatherProvider:
    """Synthetic, timezone-aware weather with no random inputs."""

    def __init__(self, start_timestamp: str = START_TIMESTAMP) -> None:
        start = datetime.fromisoformat(start_timestamp)
        self.start = start.astimezone(ZoneInfo(TIMEZONE_NAME))

    def get_state_by_step(self, step: int) -> WeatherState:
        timestamp = self.start + timedelta(hours=int(step))
        hour = timestamp.hour + timestamp.minute / 60.0
        day_index = (timestamp.date() - self.start.date()).days
        daily = math.sin(2.0 * math.pi * (hour - 8.0) / 24.0)
        seasonal = math.sin(2.0 * math.pi * day_index / 365.0)
        if 7.0 <= hour <= 18.0:
            solar_shape = math.sin(math.pi * (hour - 7.0) / 11.0)
            ghi = max(0.0, 550.0 * solar_shape)
        else:
            ghi = 0.0
        return WeatherState(
            datetime=timestamp,
            outdoor_temperature_c=8.0 + 3.5 * daily + 7.0 * seasonal,
            wind_speed_m_s=2.0 + abs(daily),
            wind_direction_deg=180.0,
            direct_normal_radiation_w_m2=0.7 * ghi,
            diffuse_horizontal_radiation_w_m2=0.3 * ghi,
            global_horizontal_radiation_w_m2=ghi,
            outdoor_illuminance_lux=120.0 * ghi,
            sky_condition="clear" if ghi > 0.0 else "night",
            outdoor_co2_ppm=420.0,
            outdoor_noise_db=42.0,
            relative_humidity_percent=max(35.0, min(90.0, 68.0 - 8.0 * daily)),
            atmospheric_pressure_pa=101325.0,
        )


def reset_randomness() -> None:
    os.environ["PYTHONHASHSEED"] = str(PYTHON_HASH_SEED)
    os.environ["TZ"] = TIMEZONE_NAME
    random.seed(APPLICATION_SEED)
    np.random.seed(NUMPY_SEED)


def create_simulation(
    timesteps: int,
    dt_minutes: int,
    logger: Any | None = None,
) -> AbbeySimulation:
    reset_randomness()
    duration_hours = timesteps * dt_minutes / 60.0
    simulation = AbbeySimulation.initialize(
        config_path=CONFIG_SNAPSHOT,
        duration_hours=duration_hours,
        dt_minutes=dt_minutes,
        weather_provider=DeterministicWeatherProvider(),
        random_seed=APPLICATION_SEED,
    )
    if logger is not None:
        simulation.logger = logger
    return simulation


def collect_tables(simulation: AbbeySimulation) -> dict[str, pd.DataFrame]:
    return {
        "logger_main": simulation.logger.to_dataframe(),
        "logger_people": simulation.logger.people_to_dataframe(),
        "logger_zones": simulation.logger.zones_to_dataframe(),
        "building_zone": simulation.building_zone_records_to_dataframe(),
        "building_dwelling": simulation.building_dwelling_records_to_dataframe(),
        "building": simulation.building_records_to_dataframe(),
        "interzone_thermal": simulation.building_interzone_thermal_records_to_dataframe(),
        "interzone_airflow": simulation.building_interzone_airflow_records_to_dataframe(),
        "window_airflow": simulation.building_window_airflow_records_to_dataframe(),
        "control_bridge": simulation.building_control_bridge_records_to_dataframe(),
        "action_events": simulation.building_action_event_records_to_dataframe(),
        "internal_source": simulation.building_internal_source_records_to_dataframe(),
        "internal_source_zone": simulation.building_internal_source_zone_records_to_dataframe(),
        "internal_source_building": simulation.building_internal_source_building_records_to_dataframe(),
    }


def _canonical_scalar(value: Any) -> Any:
    if value is None or value is pd.NA:
        return {"null": True}
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, (datetime, pd.Timestamp)):
        return {"datetime": value.isoformat()}
    if isinstance(value, bool):
        return {"bool": value}
    if isinstance(value, int):
        return {"int": str(value)}
    if isinstance(value, float):
        if math.isnan(value):
            return {"float": "nan"}
        if math.isinf(value):
            return {"float": "inf" if value > 0 else "-inf"}
        return {"float": value.hex()}
    if isinstance(value, dict):
        return {
            "mapping": [
                [str(key), _canonical_scalar(item)]
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            ]
        }
    if isinstance(value, (list, tuple)):
        return {"sequence": [_canonical_scalar(item) for item in value]}
    try:
        if bool(pd.isna(value)):
            return {"null": True}
    except (TypeError, ValueError):
        pass
    return {"string": str(value)}


def _hash_json(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def table_signature(frame: pd.DataFrame) -> dict[str, Any]:
    numeric_columns = list(frame.select_dtypes(include=[np.number]).columns)
    categorical_columns = [
        column for column in frame.columns if column not in numeric_columns
    ]
    row_key_columns = [
        column
        for column in frame.columns
        if column in {"step", "day", "hour", "action_name", "source_kind"}
        or column.endswith("_id")
    ]
    canonical_rows = [
        [_canonical_scalar(value) for value in row]
        for row in frame.itertuples(index=False, name=None)
    ]
    categorical_rows = [
        [_canonical_scalar(value) for value in row]
        for row in frame[categorical_columns].itertuples(index=False, name=None)
    ] if categorical_columns else []
    row_keys = [
        [_canonical_scalar(value) for value in row]
        for row in frame[row_key_columns].itertuples(index=False, name=None)
    ] if row_key_columns else [[{"row": index}] for index in range(len(frame))]

    numeric_hash = None
    if numeric_columns:
        numeric_values = frame[numeric_columns].to_numpy(dtype="<f8", copy=True)
        numeric_hash = hashlib.sha256(numeric_values.tobytes(order="C")).hexdigest()

    return {
        "rows": int(len(frame)),
        "columns": list(frame.columns),
        "dtypes": [str(dtype) for dtype in frame.dtypes],
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "row_key_columns": row_key_columns,
        "row_order_sha256": _hash_json(row_keys),
        "categorical_sha256": _hash_json(categorical_rows),
        "numeric_sha256": numeric_hash,
        "full_sha256": _hash_json(canonical_rows),
    }


def compare_tables(
    first: dict[str, pd.DataFrame],
    second: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if list(first) != list(second):
        raise AssertionError("Table names or table order changed between object runs.")
    for name in first:
        left = first[name]
        right = second[name]
        schema_equal = (
            list(left.columns) == list(right.columns)
            and [str(dtype) for dtype in left.dtypes]
            == [str(dtype) for dtype in right.dtypes]
        )
        if not schema_equal:
            raise AssertionError(f"{name}: schema differs between deterministic runs")

        left_signature = table_signature(left)
        right_signature = table_signature(right)
        row_order_equal = (
            left_signature["row_order_sha256"]
            == right_signature["row_order_sha256"]
        )
        categorical_equal = (
            left_signature["categorical_sha256"]
            == right_signature["categorical_sha256"]
        )
        numeric_columns = left_signature["numeric_columns"]
        numeric_equal = True
        max_abs_numeric_difference = 0.0
        if numeric_columns:
            left_values = left[numeric_columns].to_numpy(dtype=np.float64)
            right_values = right[numeric_columns].to_numpy(dtype=np.float64)
            delta = np.abs(left_values - right_values)
            finite_delta = delta[np.isfinite(delta)]
            if finite_delta.size:
                max_abs_numeric_difference = float(finite_delta.max())
            numeric_equal = bool(
                np.allclose(
                    left_values,
                    right_values,
                    rtol=FLOAT_RTOL,
                    atol=FLOAT_ATOL,
                    equal_nan=True,
                )
            )

        result[name] = {
            "schema_equal": schema_equal,
            "row_order_equal": row_order_equal,
            "categorical_equal": categorical_equal,
            "numeric_within_tolerance": numeric_equal,
            "max_abs_numeric_difference": max_abs_numeric_difference,
            "exact_full_hash_equal": (
                left_signature["full_sha256"]
                == right_signature["full_sha256"]
            ),
        }
        if not all((row_order_equal, categorical_equal, numeric_equal)):
            raise AssertionError(f"{name}: deterministic output comparison failed")
    return result


def energy_invariants(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    zone = tables["building_zone"]
    dwelling = tables["building_dwelling"]
    building = tables["building"]

    zone_by_step = zone.groupby("step", sort=False)["total_energy_wh"].sum()
    dwelling_by_step = dwelling.groupby("step", sort=False)["zone_total_energy_wh"].sum()
    building_by_step = building.set_index("step")["zone_total_energy_wh"]

    zone_dwelling_delta = (
        zone_by_step.to_numpy(dtype=float)
        - dwelling_by_step.to_numpy(dtype=float)
    )
    zone_building_delta = (
        zone_by_step.to_numpy(dtype=float)
        - building_by_step.to_numpy(dtype=float)
    )
    max_zone_dwelling = float(np.max(np.abs(zone_dwelling_delta), initial=0.0))
    max_zone_building = float(np.max(np.abs(zone_building_delta), initial=0.0))
    all_nonnegative = bool(
        (zone["total_energy_wh"].fillna(0.0) >= -FLOAT_ATOL).all()
        and (dwelling["total_energy_wh"].fillna(0.0) >= -FLOAT_ATOL).all()
        and (building["total_energy_wh"].fillna(0.0) >= -FLOAT_ATOL).all()
    )
    zone_balance_ok = bool(zone["zone_energy_balance_ok"].fillna(False).all())
    dwelling_balance_ok = bool(dwelling["energy_balance_ok"].fillna(False).all())
    building_balance_ok = bool(
        building["building_zone_energy_balance_ok"].fillna(False).all()
    )
    if max_zone_dwelling > FLOAT_ATOL or max_zone_building > FLOAT_ATOL:
        raise AssertionError("Zone/dwelling/building energy aggregation changed.")
    if not all((all_nonnegative, zone_balance_ok, dwelling_balance_ok, building_balance_ok)):
        raise AssertionError("An energy non-negativity or balance invariant failed.")
    return {
        "max_abs_zone_to_dwelling_residual_wh": max_zone_dwelling,
        "max_abs_zone_to_building_residual_wh": max_zone_building,
        "all_energy_nonnegative": all_nonnegative,
        "zone_energy_balance_ok_all_steps": zone_balance_ok,
        "dwelling_energy_balance_ok_all_steps": dwelling_balance_ok,
        "building_energy_balance_ok_all_steps": building_balance_ok,
        "building_total_energy_wh": float(building["total_energy_wh"].sum()),
    }


def engine_path_invariants(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    zone = tables["building_zone"]
    building = tables["building"]
    values = {
        "zone_physics_engine_active": sorted(
            bool(value) for value in zone["physics_engine_active"].dropna().unique()
        ),
        "zone_physics_path": sorted(str(value) for value in zone["physics_path"].dropna().unique()),
        "zone_performance_path": sorted(
            str(value) for value in zone["performance_path"].dropna().unique()
        ),
        "building_physics_path": sorted(
            str(value) for value in building["physics_path"].dropna().unique()
        ),
        "building_performance_path": sorted(
            str(value) for value in building["performance_path"].dropna().unique()
        ),
        "legacy_fallback_steps": int(
            zone["legacy_fallback_used"].fillna(False).astype(bool).sum()
            + building["legacy_fallback_used"].fillna(False).astype(bool).sum()
        ),
    }
    if values["legacy_fallback_steps"] != 0:
        raise AssertionError("Trusted object baseline entered a legacy fallback path.")
    if values["zone_physics_engine_active"] != [True]:
        raise AssertionError("Object baseline did not remain on the physics engine.")
    return values


def _csv_ready(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    for column in output.columns:
        if output[column].dtype == object:
            output[column] = output[column].map(
                lambda value: json.dumps(
                    _canonical_scalar(value),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            )
    return output


def write_run_outputs(
    output_dir: Path,
    tables: dict[str, pd.DataFrame],
) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for name, frame in tables.items():
        path = output_dir / f"{name}.csv"
        _csv_ready(frame).to_csv(path, index=False, lineterminator="\n")
        outputs.append(
            {
                "path": path.relative_to(output_dir).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _hash_file(path),
            }
        )
    return outputs


def scenario_dimensions(simulation: AbbeySimulation, scenario: Scenario) -> dict[str, Any]:
    physical_system_specs = (
        sum(
            len(dwelling.system_specs)
            for dwelling in simulation.building_model.dwellings.values()
        )
        + len(simulation.building_model.shared_system_specs)
        + len(simulation.building_model.building_system_specs)
    )
    configured_actions = sorted(
        str(name)
        for name in simulation.config.get("actions", {})
        if not str(name).startswith("_")
    )
    return {
        "timesteps": scenario.timesteps,
        "dt_minutes": scenario.dt_minutes,
        "simulated_hours": scenario.simulated_hours,
        "buildings": 1,
        "dwellings": len(simulation.building_model.dwellings),
        "zones": len(simulation.building_model.all_zone_models()),
        "people": len(simulation.people),
        "physical_system_specs": physical_system_specs,
        "public_system_state_entries_at_initialization": len(
            simulation.systems.zone_systems
        ),
        "configured_action_count": len(configured_actions),
        "configured_action_names": configured_actions,
        "observed_action_names": sorted(
            {
                str(record.get("action_name"))
                for record in simulation.building_action_event_records
            }
        ),
    }


def run_scenario(scenario: Scenario) -> dict[str, Any]:
    runs = []
    table_sets = []
    for run_number in (1, 2):
        output_dir = RUN_ROOT / scenario.name / f"run_{run_number}"
        started = time.perf_counter()
        simulation = create_simulation(scenario.timesteps, scenario.dt_minutes)
        initialization_s = time.perf_counter() - started
        loop_started = time.perf_counter()
        for _ in range(scenario.timesteps):
            simulation.step()
        loop_s = time.perf_counter() - loop_started
        tables = collect_tables(simulation)
        table_sets.append(tables)
        files = write_run_outputs(output_dir, tables)
        run_result = {
            "run": run_number,
            "initialization_s_excluded_from_golden_comparison": initialization_s,
            "loop_s_excluded_from_golden_comparison": loop_s,
            "files": files,
            "table_signatures": {
                name: table_signature(frame) for name, frame in tables.items()
            },
        }
        (output_dir / "run_result.json").write_text(
            json.dumps(run_result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        runs.append(run_result)

    comparison = compare_tables(table_sets[0], table_sets[1])
    first_files = {item["path"]: item["sha256"] for item in runs[0]["files"]}
    second_files = {item["path"]: item["sha256"] for item in runs[1]["files"]}
    return {
        "description": scenario.description,
        "dimensions": scenario_dimensions(
            create_simulation(scenario.timesteps, scenario.dt_minutes), scenario
        ),
        "table_signatures": runs[0]["table_signatures"],
        "normalized_output_file_hashes": first_files,
        "normalized_output_files_exactly_repeat": first_files == second_files,
        "comparison": comparison,
        "energy_invariants": energy_invariants(table_sets[0]),
        "engine_path_invariants": engine_path_invariants(table_sets[0]),
        "isolated_run_directories": [
            str((RUN_ROOT / scenario.name / f"run_{number}").relative_to(PROJECT_ROOT))
            for number in (1, 2)
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        choices=["all", *SCENARIOS],
        default="all",
    )
    arguments = parser.parse_args()
    selected = (
        list(SCENARIOS.values())
        if arguments.scenario == "all"
        else [SCENARIOS[arguments.scenario]]
    )

    scenario_results = {}
    for scenario in selected:
        print(f"Running deterministic object scenario: {scenario.name}", flush=True)
        scenario_results[scenario.name] = run_scenario(scenario)
        print(f"  PASS: {scenario.name}", flush=True)

    existing = {}
    if GOLDEN_PATH.is_file():
        existing = json.loads(GOLDEN_PATH.read_text(encoding="utf-8")).get(
            "scenarios", {}
        )
    existing.update(scenario_results)
    manifest = {
        "schema_version": 1,
        "runner": "trusted object runner (AbbeySimulation)",
        "config_snapshot": str(CONFIG_SNAPSHOT.relative_to(PROJECT_ROOT)),
        "config_snapshot_sha256": _hash_file(CONFIG_SNAPSHOT),
        "randomness": {
            "application_seed": APPLICATION_SEED,
            "numpy_seed": NUMPY_SEED,
            "python_hash_seed": PYTHON_HASH_SEED,
        },
        "time": {
            "timezone": TIMEZONE_NAME,
            "start_timestamp": START_TIMESTAMP,
        },
        "comparison_policy": {
            "schema": "exact column order and dtype strings",
            "row_order": "exact key-column sequence hash",
            "categorical_and_status_values": "exact canonical hash",
            "floating_point": {
                "rtol": FLOAT_RTOL,
                "atol": FLOAT_ATOL,
                "equal_nan": True,
            },
            "excluded_fields": [
                "initialization_s",
                "loop_s",
                "filesystem timestamps",
                "profiler and wall-clock measurements",
            ],
        },
        "scenarios": existing,
    }
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote {GOLDEN_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
