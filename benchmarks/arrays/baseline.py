"""Fair, reproducible Phase 1.7 array-runner benchmark."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys
import time
from typing import Any

import numba
import numpy as np
import pandas as pd
import psutil

from benchmarks.arrays.phase_18_20_8760 import (
    DT_MINUTES,
    N_TIMESTEPS,
    RUN_ACOUSTICS,
    make_8760_multizone_dwelling_input,
)
from benchmarks.object.baseline import (
    APPLICATION_SEED,
    NUMPY_SEED,
    PROJECT_ROOT,
    START_TIMESTAMP,
    TIMEZONE_NAME,
)
from benchmarks.object.profile_baseline import RssSampler, environment_metadata
from nexusep.abbey.arrays import schema
from nexusep.abbey.arrays.decoder import (
    decode_simulation_state,
    decoded_state_to_dataframes,
)
from nexusep.abbey.arrays.encoder import compile_simulation_to_arrays
from nexusep.abbey.arrays.logger import allocate_logs_for_state
from nexusep.abbey.arrays.timestep import run_array_timestep


REPORT_PATH = PROJECT_ROOT / "artifacts" / "baseline" / "array_benchmark.json"
PROFILE_ROOT = PROJECT_ROOT / "artifacts" / "benchmarks" / "phase1_4" / "phase18_21" / "generated"
OBJECT_MANIFEST_PATH = (
    PROJECT_ROOT / "artifacts" / "baseline" / "deterministic_object_manifest.json"
)
OBJECT_PROFILE_PATH = PROJECT_ROOT / "artifacts" / "baseline" / "object_profile.json"


def reset_randomness() -> None:
    random.seed(APPLICATION_SEED)
    np.random.seed(NUMPY_SEED)
    os.environ["TZ"] = TIMEZONE_NAME


def summarise(values: list[float]) -> dict[str, float]:
    return {
        "median": float(statistics.median(values)),
        "min": float(min(values)),
        "max": float(max(values)),
        "range": float(max(values) - min(values)),
    }


def _iter_arrays(value: Any, prefix: str = "", seen: set[int] | None = None):
    if seen is None:
        seen = set()
    identity = id(value)
    if identity in seen:
        return
    seen.add(identity)
    if isinstance(value, np.ndarray):
        yield prefix, value
        return
    if is_dataclass(value):
        for field in fields(value):
            child = getattr(value, field.name)
            child_prefix = f"{prefix}.{field.name}" if prefix else field.name
            yield from _iter_arrays(child, child_prefix, seen)
    elif isinstance(value, dict):
        for key in sorted(value, key=str):
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            yield from _iter_arrays(value[key], child_prefix, seen)
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            child_prefix = f"{prefix}[{index}]"
            yield from _iter_arrays(child, child_prefix, seen)


def array_bundle_signature(value: Any) -> dict[str, Any]:
    digest = hashlib.sha256()
    arrays = []
    for name, array in sorted(_iter_arrays(value), key=lambda item: item[0]):
        contiguous = np.ascontiguousarray(array)
        digest.update(name.encode("utf-8"))
        digest.update(contiguous.dtype.str.encode("ascii"))
        digest.update(json.dumps(contiguous.shape).encode("ascii"))
        digest.update(contiguous.tobytes(order="C"))
        arrays.append(
            {
                "name": name,
                "shape": list(array.shape),
                "dtype": str(array.dtype),
                "bytes": int(array.nbytes),
            }
        )
    return {
        "sha256": digest.hexdigest(),
        "array_count": len(arrays),
        "bytes": sum(item["bytes"] for item in arrays),
        "arrays": arrays,
    }


def dataframe_bytes(dataframes: dict[str, pd.DataFrame]) -> int:
    return int(
        sum(
            frame.memory_usage(index=True, deep=True).sum()
            for frame in dataframes.values()
        )
    )


def validate_state(state: Any, logs: Any | None) -> dict[str, Any]:
    zone = state.dynamic.zone_state
    person = state.dynamic.person_state
    building = state.dynamic.building_state

    temperatures = zone[:, schema.ZONE_AIR_TEMPERATURE_C]
    co2 = zone[:, schema.ZONE_CO2_PPM]
    humidity = zone[:, schema.ZONE_RELATIVE_HUMIDITY]
    demands = building[
        :,
        [
            schema.BUILDING_TOTAL_HEATING_DEMAND_W,
            schema.BUILDING_TOTAL_COOLING_DEMAND_W,
            schema.BUILDING_TOTAL_ELECTRICITY_DEMAND_W,
        ],
    ]
    checks = {
        "all_zone_state_finite": bool(np.isfinite(zone).all()),
        "all_person_state_finite": bool(np.isfinite(person).all()),
        "temperature_bounds": bool(
            temperatures.min() > -50.0 and temperatures.max() < 80.0
        ),
        "co2_bounds": bool(co2.min() > 0.0 and co2.max() < 10000.0),
        "relative_humidity_bounds": bool(
            humidity.min() >= 0.0 and humidity.max() <= 1.0
        ),
        "building_demands_nonnegative": bool((demands >= -1.0e-12).all()),
        "final_zone_temperature_min_c": float(temperatures.min()),
        "final_zone_temperature_max_c": float(temperatures.max()),
        "final_zone_co2_min_ppm": float(co2.min()),
        "final_zone_co2_max_ppm": float(co2.max()),
        "final_zone_relative_humidity_min": float(humidity.min()),
        "final_zone_relative_humidity_max": float(humidity.max()),
        "final_building_heating_demand_w": float(
            building[0, schema.BUILDING_TOTAL_HEATING_DEMAND_W]
        ),
        "final_building_cooling_demand_w": float(
            building[0, schema.BUILDING_TOTAL_COOLING_DEMAND_W]
        ),
        "final_building_electricity_demand_w": float(
            building[0, schema.BUILDING_TOTAL_ELECTRICITY_DEMAND_W]
        ),
    }
    if logs is not None:
        final_zone_log = logs.zone_log[-1]
        checks["final_zone_state_matches_log"] = bool(
            np.allclose(
                temperatures,
                final_zone_log[:, schema.ZONE_LOG_AIR_TEMPERATURE_C],
                rtol=0.0,
                atol=0.0,
            )
            and np.allclose(
                co2,
                final_zone_log[:, schema.ZONE_LOG_CO2_PPM],
                rtol=0.0,
                atol=0.0,
            )
            and np.allclose(
                humidity,
                final_zone_log[:, schema.ZONE_LOG_RELATIVE_HUMIDITY],
                rtol=0.0,
                atol=0.0,
            )
        )
    boolean_checks = [value for value in checks.values() if isinstance(value, bool)]
    if not all(boolean_checks):
        raise AssertionError(f"Array correctness invariant failed: {checks}")
    return checks


def make_input(timesteps: int = N_TIMESTEPS) -> dict[str, Any]:
    readable_input = make_8760_multizone_dwelling_input()
    if timesteps != N_TIMESTEPS:
        readable_input["n_timesteps"] = timesteps
        readable_input["weather_series"] = readable_input["weather_series"][:timesteps]
    return readable_input


def run_warmup() -> dict[str, Any]:
    reset_randomness()
    started = time.perf_counter()
    state = compile_simulation_to_arrays(make_input(24))
    compile_s = time.perf_counter() - started
    loop_started = time.perf_counter()
    for time_index in range(24):
        state, _, _, _ = run_array_timestep(
            state=state,
            time_index=time_index,
            dt_minutes=DT_MINUTES,
            logs=None,
            run_acoustics=RUN_ACOUSTICS,
        )
    return {
        "timesteps": 24,
        "compile_s": compile_s,
        "loop_s": time.perf_counter() - loop_started,
        "included_in_measured_repetitions": False,
    }


def run_repetition(repetition: int, logs_enabled: bool) -> dict[str, Any]:
    reset_randomness()
    gc.collect()
    with RssSampler() as memory:
        input_started = time.perf_counter()
        readable_input = make_input()
        input_construction_s = time.perf_counter() - input_started

        compile_started = time.perf_counter()
        state = compile_simulation_to_arrays(readable_input)
        compile_s = time.perf_counter() - compile_started

        allocation_started = time.perf_counter()
        logs = None
        if logs_enabled:
            logs = allocate_logs_for_state(
                state=state,
                n_timesteps=N_TIMESTEPS,
                log_persons=True,
                log_zones=True,
                log_systems=True,
                log_dwellings=True,
                log_buildings=True,
            )
        log_allocation_s = time.perf_counter() - allocation_started

        first_started = time.perf_counter()
        state, _, _, _ = run_array_timestep(
            state=state,
            time_index=0,
            dt_minutes=DT_MINUTES,
            logs=logs,
            run_acoustics=RUN_ACOUSTICS,
        )
        first_timestep_s = time.perf_counter() - first_started

        steady_started = time.perf_counter()
        for time_index in range(1, N_TIMESTEPS):
            state, _, _, _ = run_array_timestep(
                state=state,
                time_index=time_index,
                dt_minutes=DT_MINUTES,
                logs=logs,
                run_acoustics=RUN_ACOUSTICS,
            )
        steady_loop_s = time.perf_counter() - steady_started

        correctness = validate_state(state, logs)
        state_signature = array_bundle_signature(state)
        log_signature = array_bundle_signature(logs) if logs is not None else None

        decode_started = time.perf_counter()
        decoded_state = decode_simulation_state(state)
        final_dataframes = decoded_state_to_dataframes(decoded_state)
        log_dataframes = logs.to_dataframes(state) if logs is not None else {}
        decode_output_s = time.perf_counter() - decode_started
        decoded_output_bytes = dataframe_bytes(final_dataframes) + dataframe_bytes(
            log_dataframes
        )

    loop_s = first_timestep_s + steady_loop_s
    return {
        "repetition": repetition,
        "logs_enabled": logs_enabled,
        "input_construction_s": input_construction_s,
        "encoding_compilation_s": compile_s,
        "log_allocation_s": log_allocation_s,
        "first_timestep_s": first_timestep_s,
        "steady_state_loop_s": steady_loop_s,
        "total_loop_s": loop_s,
        "decoding_output_s": decode_output_s,
        "seconds_per_timestep": loop_s / N_TIMESTEPS,
        "simulated_hours_per_second": N_TIMESTEPS / loop_s,
        "peak_rss_bytes": memory.peak_rss_bytes,
        "peak_rss_growth_bytes": memory.peak_rss_bytes - memory.start_rss_bytes,
        "raw_state_array_bytes": state_signature["bytes"],
        "raw_log_array_bytes": 0 if log_signature is None else log_signature["bytes"],
        "decoded_output_bytes": decoded_output_bytes,
        "state_signature": state_signature,
        "log_signature": log_signature,
        "correctness": correctness,
    }


def benchmark_case(logs_enabled: bool, repetitions: int = 3) -> dict[str, Any]:
    samples = []
    for repetition in range(1, repetitions + 1):
        print(
            f"Array logs={'on' if logs_enabled else 'off'} repetition {repetition}",
            flush=True,
        )
        samples.append(run_repetition(repetition, logs_enabled))
    fields_to_summarise = (
        "input_construction_s",
        "encoding_compilation_s",
        "log_allocation_s",
        "first_timestep_s",
        "steady_state_loop_s",
        "total_loop_s",
        "decoding_output_s",
        "seconds_per_timestep",
        "simulated_hours_per_second",
        "peak_rss_bytes",
        "peak_rss_growth_bytes",
        "raw_state_array_bytes",
        "raw_log_array_bytes",
        "decoded_output_bytes",
    )
    state_hashes = [sample["state_signature"]["sha256"] for sample in samples]
    log_hashes = [
        None if sample["log_signature"] is None else sample["log_signature"]["sha256"]
        for sample in samples
    ]
    return {
        "logs_enabled": logs_enabled,
        "repetitions": repetitions,
        "samples": samples,
        "summary": {
            field: summarise([float(sample[field]) for sample in samples])
            for field in fields_to_summarise
        },
        "determinism": {
            "state_hashes": state_hashes,
            "state_exactly_repeatable": len(set(state_hashes)) == 1,
            "log_hashes": log_hashes,
            "logs_exactly_repeatable": len(set(log_hashes)) == 1,
        },
    }


def existing_cprofile() -> dict[str, Any]:
    result = {}
    for mode in ("logs_on", "logs_off"):
        path = PROFILE_ROOT / f"abbey_8760_{mode}_profile.csv"
        rows = []
        if path.is_file():
            frame = pd.read_csv(path).head(25)
            rows = frame.to_dict(orient="records")
        result[mode] = {
            "source": str(path.relative_to(PROJECT_ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
            "top_functions": rows,
        }
    return result


def object_correctness_reference(
    array_cases: dict[str, Any],
) -> dict[str, Any]:
    object_manifest = json.loads(OBJECT_MANIFEST_PATH.read_text(encoding="utf-8"))
    object_profile = json.loads(OBJECT_PROFILE_PATH.read_text(encoding="utf-8"))
    object_scenarios = object_manifest["scenarios"]
    object_repeatable = all(
        scenario["normalized_output_files_exactly_repeat"]
        and all(
            table["numeric_within_tolerance"]
            and table["categorical_equal"]
            and table["row_order_equal"]
            for table in scenario["comparison"].values()
        )
        for scenario in object_scenarios.values()
    )
    array_repeatable = all(
        case["determinism"]["state_exactly_repeatable"]
        and case["determinism"]["logs_exactly_repeatable"]
        for case in array_cases.values()
    )
    array_invariants = all(
        all(
            value
            for key, value in sample["correctness"].items()
            if isinstance(value, bool)
        )
        for case in array_cases.values()
        for sample in case["samples"]
    )
    return {
        "object_manifest": str(OBJECT_MANIFEST_PATH.relative_to(PROJECT_ROOT)),
        "object_profile": str(OBJECT_PROFILE_PATH.relative_to(PROJECT_ROOT)),
        "object_config_sha256": object_manifest["config_snapshot_sha256"],
        "checks": {
            "object_golden_repeatable": object_repeatable,
            "object_energy_and_engine_path_invariants": all(
                scenario["energy_invariants"]["all_energy_nonnegative"]
                and scenario["energy_invariants"]["building_energy_balance_ok_all_steps"]
                and scenario["engine_path_invariants"]["legacy_fallback_steps"] == 0
                for scenario in object_scenarios.values()
            ),
            "array_final_state_and_log_invariants": array_invariants,
            "array_exactly_repeatable": array_repeatable,
            "both_annual_performance_runs_completed": (
                "annual_logs_off" in object_profile["cases"]
                and "annual_logs_on" in object_profile["cases"]
            ),
        },
        "statewise_comparison": {
            "supported": False,
            "status": "known deviation",
            "reason": (
                "The surviving array benchmark is a synthetic five-zone/four-person "
                "readable-input scenario, while the trusted object baseline uses the "
                "current AbbeySimulation one-person/eight-zone config. No authoritative "
                "shared object-to-array scenario adapter exists in the frozen source, so "
                "claiming per-field equivalence would be misleading. Structural, physical, "
                "logging, repeatability, and energy/path invariants are checked instead."
            ),
        },
    }


def main() -> int:
    warmup = run_warmup()
    cases = {
        "logs_off": benchmark_case(False, 3),
        "logs_on": benchmark_case(True, 3),
    }
    environment = environment_metadata()
    environment["packages"]["numba"] = numba.__version__
    environment["packages"]["numpy"] = np.__version__
    sample_input = make_input()
    report = {
        "schema_version": 1,
        "runner": "Phase 18 reference array timestep path",
        "environment": environment,
        "scenario": {
            "timesteps": N_TIMESTEPS,
            "dt_minutes": DT_MINUTES,
            "simulated_hours": N_TIMESTEPS * DT_MINUTES / 60.0,
            "buildings": len(sample_input["buildings"]),
            "dwellings": len(sample_input["dwellings"]),
            "zones": len(sample_input["zones"]),
            "people": len(sample_input["persons"]),
            "systems": len(sample_input["systems"]),
            "actions": len(sample_input["actions"]),
            "logging_modes": ["off", "on"],
            "run_acoustics": RUN_ACOUSTICS,
            "other_optional_kernels": "thermal, airflow, CO2, moisture, daylight enabled",
            "seed": APPLICATION_SEED,
            "numpy_seed": NUMPY_SEED,
            "timezone": TIMEZONE_NAME,
            "object_reference_start_timestamp": START_TIMESTAMP,
        },
        "compilation_and_warmup": {
            "warmup": warmup,
            "numba_installed": True,
            "numba_used_by_run_array_timestep": False,
            "first_run_interpretation": (
                "first_timestep_s is reported separately, but this reference "
                "timestep path does not call Numba dispatchers; it is not JIT cost"
            ),
        },
        "cases": cases,
        "cprofile": existing_cprofile(),
        "correctness_against_object_baseline": object_correctness_reference(cases),
        "measurement_policy": {
            "warmup_separate": True,
            "measured_repetitions": 3,
            "reported_statistic": "median with min/max/range",
            "peak_memory": "process RSS sampled every 20 ms",
            "timing_boundaries": [
                "input construction",
                "array encoding/compilation",
                "log allocation",
                "first timestep (non-JIT)",
                "steady-state remaining loop",
                "final-state and optional log decoding",
            ],
        },
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote {REPORT_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
