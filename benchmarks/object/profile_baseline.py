"""Reproducible object-runner timing and memory baseline for Phase 1.6."""

from __future__ import annotations

import argparse
import cProfile
import csv
import gc
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import pstats
import statistics
import subprocess
import sys
import threading
import time
from typing import Any

import numpy as np
import pandas as pd
import psutil

from benchmarks.object.baseline import (
    APPLICATION_SEED,
    CONFIG_SNAPSHOT,
    PROJECT_ROOT,
    START_TIMESTAMP,
    TIMEZONE_NAME,
    create_simulation,
)


ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "profiles" / "phase1_6_object"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "baseline" / "object_profile.json"
THREAD_ENV_NAMES = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMBA_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


class NullLogger:
    """Supported logger surface with no retained per-timestep records."""

    def record_step(self, **_: Any) -> None:
        return None

    @staticmethod
    def to_dataframe() -> pd.DataFrame:
        return pd.DataFrame()

    @staticmethod
    def people_to_dataframe() -> pd.DataFrame:
        return pd.DataFrame()

    @staticmethod
    def zones_to_dataframe() -> pd.DataFrame:
        return pd.DataFrame()


class RssSampler:
    def __init__(self, interval_s: float = 0.02) -> None:
        self.interval_s = interval_s
        self.process = psutil.Process(os.getpid())
        self.start_rss_bytes = int(self.process.memory_info().rss)
        self.peak_rss_bytes = self.start_rss_bytes
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self) -> None:
        while not self._stop.wait(self.interval_s):
            self.peak_rss_bytes = max(
                self.peak_rss_bytes,
                int(self.process.memory_info().rss),
            )

    def __enter__(self) -> "RssSampler":
        self._thread.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.peak_rss_bytes = max(
            self.peak_rss_bytes,
            int(self.process.memory_info().rss),
        )
        self._stop.set()
        self._thread.join(timeout=2.0)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_output(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout.strip()


def _cpu_name() -> str:
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            ) as key:
                return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    return platform.processor()


def environment_metadata() -> dict[str, Any]:
    dirty_status = _git_output("status", "--short", "--untracked-files=all")
    return {
        "cpu": {
            "model": _cpu_name(),
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
        },
        "ram_bytes": int(psutil.virtual_memory().total),
        "operating_system": {
            "platform": platform.platform(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "executable": sys.executable,
        },
        "packages": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "psutil": psutil.__version__,
        },
        "thread_environment": {
            name: os.environ.get(name) for name in THREAD_ENV_NAMES
        },
        "repository": {
            "commit": _git_output("rev-parse", "HEAD"),
            "branch": _git_output("branch", "--show-current"),
            "dirty": bool(dirty_status),
            "dirty_status_sha256": hashlib.sha256(
                dirty_status.encode("utf-8")
            ).hexdigest(),
        },
    }


def measure_imports(repetitions: int = 3) -> dict[str, Any]:
    samples = []
    code = (
        "import time; t=time.perf_counter(); "
        "from nexusep.abbey.simulation.runner import AbbeySimulation; "
        "print(time.perf_counter()-t)"
    )
    for repetition in range(1, repetitions + 1):
        started = time.perf_counter()
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        total_s = time.perf_counter() - started
        import_s = float(completed.stdout.splitlines()[-1])
        samples.append(
            {
                "repetition": repetition,
                "module_import_s": import_s,
                "fresh_process_total_s": total_s,
            }
        )
    return {
        "samples": samples,
        "module_import_s": summarise_values(
            [sample["module_import_s"] for sample in samples]
        ),
        "fresh_process_total_s": summarise_values(
            [sample["fresh_process_total_s"] for sample in samples]
        ),
    }


def retained_record_counts(simulation: Any) -> dict[str, int]:
    collections = {
        "logger_main": getattr(simulation.logger, "records", []),
        "logger_people": getattr(simulation.logger, "person_records", []),
        "logger_zones": getattr(simulation.logger, "zone_records", []),
        "building_zone": simulation.building_zone_records,
        "building_dwelling": simulation.building_dwelling_records,
        "building": simulation.building_records,
        "interzone_thermal": simulation.building_interzone_thermal_records,
        "interzone_airflow": simulation.building_interzone_airflow_records,
        "window_airflow": simulation.building_window_airflow_records,
        "control_bridge": simulation.building_control_bridge_records,
        "action_events": simulation.building_action_event_records,
        "internal_source": simulation.building_internal_source_records,
        "internal_source_zone": simulation.building_internal_source_zone_records,
        "internal_source_building": simulation.building_internal_source_building_records,
    }
    return {name: len(value) for name, value in collections.items()}


def summarise_values(values: list[float]) -> dict[str, float]:
    return {
        "median": float(statistics.median(values)),
        "min": float(min(values)),
        "max": float(max(values)),
        "range": float(max(values) - min(values)),
    }


def measure_case(
    name: str,
    timesteps: int,
    logs_enabled: bool,
    repetitions: int,
) -> dict[str, Any]:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    checkpoint_path = ARTIFACT_ROOT / f"{name}_measurements.json"
    samples = []
    if checkpoint_path.is_file():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if (
            checkpoint.get("timesteps") == timesteps
            and checkpoint.get("logs_enabled") is logs_enabled
        ):
            samples = checkpoint.get("samples", [])[:repetitions]

    for repetition in range(len(samples) + 1, repetitions + 1):
        gc.collect()
        logger = None if logs_enabled else NullLogger()
        with RssSampler() as memory:
            init_started = time.perf_counter()
            simulation = create_simulation(timesteps, 60, logger=logger)
            initialization_s = time.perf_counter() - init_started
            rss_after_initialization = int(psutil.Process().memory_info().rss)

            loop_started = time.perf_counter()
            for _ in range(timesteps):
                simulation.step()
            loop_s = time.perf_counter() - loop_started
            rss_after_loop = int(psutil.Process().memory_info().rss)

            inspection_started = time.perf_counter()
            counts = retained_record_counts(simulation)
            output_inspection_s = time.perf_counter() - inspection_started

        simulated_hours = float(timesteps)
        samples.append(
            {
                "repetition": repetition,
                "initialization_s": initialization_s,
                "simulation_loop_s": loop_s,
                "output_inspection_s": output_inspection_s,
                "total_s": initialization_s + loop_s + output_inspection_s,
                "seconds_per_timestep": loop_s / timesteps,
                "simulated_hours_per_second": simulated_hours / loop_s,
                "rss_start_bytes": memory.start_rss_bytes,
                "rss_after_initialization_bytes": rss_after_initialization,
                "rss_after_loop_bytes": rss_after_loop,
                "peak_rss_bytes": memory.peak_rss_bytes,
                "peak_rss_growth_bytes": (
                    memory.peak_rss_bytes - memory.start_rss_bytes
                ),
                "retained_record_counts": counts,
                "retained_record_count_total": sum(counts.values()),
            }
        )
        checkpoint_path.write_text(
            json.dumps(
                {
                    "name": name,
                    "timesteps": timesteps,
                    "logs_enabled": logs_enabled,
                    "samples": samples,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        del simulation
        gc.collect()

    summary_fields = (
        "initialization_s",
        "simulation_loop_s",
        "total_s",
        "seconds_per_timestep",
        "simulated_hours_per_second",
        "peak_rss_bytes",
        "peak_rss_growth_bytes",
        "retained_record_count_total",
    )
    return {
        "name": name,
        "timesteps": timesteps,
        "dt_minutes": 60,
        "simulated_hours": float(timesteps),
        "logs_enabled": logs_enabled,
        "repetitions": repetitions,
        "samples": samples,
        "checkpoint": str(checkpoint_path.relative_to(PROJECT_ROOT)),
        "summary": {
            field: summarise_values([float(sample[field]) for sample in samples])
            for field in summary_fields
        },
    }


def run_warmup() -> dict[str, Any]:
    logger = NullLogger()
    started = time.perf_counter()
    simulation = create_simulation(24, 60, logger=logger)
    for _ in range(24):
        simulation.step()
    elapsed = time.perf_counter() - started
    return {
        "timesteps": 24,
        "logs_enabled": False,
        "total_s": elapsed,
        "included_in_measured_repetitions": False,
    }


def _profile_rows(profile: cProfile.Profile, top_n: int = 40) -> list[dict[str, Any]]:
    stats = pstats.Stats(profile)
    rows = []
    for (filename, line_number, function_name), values in stats.stats.items():
        primitive_calls, total_calls, total_s, cumulative_s, _ = values
        rows.append(
            {
                "filename": filename,
                "line_number": line_number,
                "function_name": function_name,
                "primitive_calls": primitive_calls,
                "total_calls": total_calls,
                "total_time_s": total_s,
                "cumulative_time_s": cumulative_s,
            }
        )
    rows.sort(key=lambda row: row["cumulative_time_s"], reverse=True)
    return rows[:top_n]


def run_cprofile(timesteps: int = 168) -> dict[str, Any]:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    simulation = create_simulation(timesteps, 60, logger=NullLogger())
    profile = cProfile.Profile()
    started = time.perf_counter()
    profile.enable()
    for _ in range(timesteps):
        simulation.step()
    profile.disable()
    elapsed = time.perf_counter() - started

    text_path = ARTIFACT_ROOT / "object_short_integration_profile.txt"
    csv_path = ARTIFACT_ROOT / "object_short_integration_profile.csv"
    stream = io.StringIO()
    stats = pstats.Stats(profile, stream=stream)
    stats.strip_dirs().sort_stats("cumulative").print_stats(80)
    text_path.write_text(stream.getvalue(), encoding="utf-8")
    rows = _profile_rows(profile, top_n=1000000)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return {
        "timesteps": timesteps,
        "logs_enabled": False,
        "profiled_loop_s": elapsed,
        "scope_note": (
            "cProfile is collected on the 168-step integration case; annual "
            "runs use unprofiled repetitions to avoid profiler distortion"
        ),
        "top_functions": rows[:25],
        "artifacts": [
            {
                "path": str(text_path.relative_to(PROJECT_ROOT)),
                "bytes": text_path.stat().st_size,
                "sha256": _sha256(text_path),
            },
            {
                "path": str(csv_path.relative_to(PROJECT_ROOT)),
                "bytes": csv_path.stat().st_size,
                "sha256": _sha256(csv_path),
            },
        ],
    }


def annual_logs_on_feasibility(short_case: dict[str, Any]) -> dict[str, Any]:
    short_steps = int(short_case["timesteps"])
    projected_loop_s = (
        short_case["summary"]["simulation_loop_s"]["median"]
        * 8760.0
        / short_steps
    )
    projected_growth = (
        short_case["summary"]["peak_rss_growth_bytes"]["max"]
        * 8760.0
        / short_steps
    )
    available_limit = psutil.virtual_memory().total * 0.60
    feasible = projected_loop_s <= 360.0 and projected_growth <= available_limit
    return {
        "feasible": bool(feasible),
        "projected_loop_s_per_repetition": projected_loop_s,
        "projected_peak_rss_growth_bytes": projected_growth,
        "memory_safety_limit_bytes": available_limit,
        "policy": (
            "run when projected loop <= 360 s and projected retained-memory "
            "growth <= 60% of physical RAM"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scope",
        choices=["pilot", "full"],
        default="full",
        help="pilot stops after import/warmup/one-step/short-integration cases",
    )
    arguments = parser.parse_args()

    print("Measuring fresh-process imports", flush=True)
    imports = measure_imports(3)
    print("Running separate warm-up", flush=True)
    warmup = run_warmup()
    print("Measuring one-step object smoke", flush=True)
    one_step = measure_case("one_step", 1, True, 3)
    print("Measuring short object integration", flush=True)
    short = measure_case("short_integration", 168, True, 3)
    print("Collecting short-integration cProfile", flush=True)
    profile = run_cprofile(168)

    cases = {
        "one_step": one_step,
        "short_integration": short,
    }
    feasibility = annual_logs_on_feasibility(short)
    if arguments.scope == "full":
        print("Measuring 8760-hour object run with logs off", flush=True)
        cases["annual_logs_off"] = measure_case(
            "annual_logs_off", 8760, False, 2
        )
        if feasibility["feasible"]:
            print("Measuring 8760-hour object run with logs on", flush=True)
            cases["annual_logs_on"] = measure_case(
                "annual_logs_on", 8760, True, 2
            )
        else:
            print("Skipping unsafe annual logs-on case", flush=True)

    example = create_simulation(1, 60)
    physical_system_specs = (
        sum(
            len(dwelling.system_specs)
            for dwelling in example.building_model.dwellings.values()
        )
        + len(example.building_model.shared_system_specs)
        + len(example.building_model.building_system_specs)
    )
    configured_actions = [
        name
        for name in example.config.get("actions", {})
        if not str(name).startswith("_")
    ]
    report = {
        "schema_version": 1,
        "runner": "trusted object runner (AbbeySimulation)",
        "environment": environment_metadata(),
        "scenario": {
            "config_snapshot": str(CONFIG_SNAPSHOT.relative_to(PROJECT_ROOT)),
            "config_snapshot_sha256": _sha256(CONFIG_SNAPSHOT),
            "seed": APPLICATION_SEED,
            "timezone": TIMEZONE_NAME,
            "start_timestamp": START_TIMESTAMP,
            "dt_minutes": 60,
            "buildings": 1,
            "dwellings": len(example.building_model.dwellings),
            "zones": len(example.building_model.all_zone_models()),
            "people": len(example.people),
            "physical_system_specs": physical_system_specs,
            "configured_actions": len(configured_actions),
            "logging_definition": {
                "on": "SimulationLogger retains main/person/zone records",
                "off": (
                    "NullLogger suppresses main/person/zone records; building "
                    "physics records remain enabled and retained"
                ),
            },
        },
        "import_initialization_smoke": imports,
        "warmup": warmup,
        "cases": cases,
        "annual_logs_on_feasibility": feasibility,
        "profiler": profile,
        "measurement_policy": {
            "small_case_repetitions": 3,
            "annual_case_repetitions": 2,
            "reported_statistic": "median with min/max/range",
            "peak_memory": "process RSS sampled every 20 ms",
            "cold_vs_warm": (
                "fresh-process imports reported separately; one unmeasured "
                "24-step warm-up precedes every measured case group"
            ),
            "output_size_proxies": (
                "retained record counts and RSS growth; deterministic 24-hour "
                "and 720-hour serialized CSV sizes are in the object manifest"
            ),
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
