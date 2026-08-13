"""Run the published-component Annex 71 runtime and temperature-error report.

Validation category: post-hoc empirical diagnostic for the Main Experiment and
predeclared holdout evaluation (not pristine blind evidence) for the Extended
Experiment under governance protocol 1.3.
"""

from __future__ import annotations

import argparse
import cProfile
import gc
import hashlib
import importlib.metadata
import json
import os
import platform
import pstats
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import psutil

from nexusep.validation_data.annex71 import (
    Annex71RunResult,
    load_annex71_intervals,
    run_object_scenario,
    select_interval,
    temperature_metrics,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = REPOSITORY_ROOT / "data" / "raw" / "validation" / "annex71-twin-houses"
MAIN_RAW = RAW_ROOT / "03_Data_Main_Experiment"
EXTENDED_RAW = RAW_ROOT / "04_Data_Extended_Experiment"
EXTENDED_ARCHIVE = RAW_ROOT / "04_Data_Extended_Experiment.zip"
FIXTURE_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "validation"
    / "fixtures"
    / "annex71-twin-houses"
    / "physical-runtime-error-v4.json"
)
REPORT_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "validation"
    / "results"
    / "annex71_physical_runtime_error_v4.md"
)
TIMEZONE = ZoneInfo("Etc/GMT-1")
WARMUP_HOURS = 24
PRIMARY_START = datetime(2019, 3, 22, 10, 30, tzinfo=TIMEZONE)
PRIMARY_END = datetime(2019, 4, 25, 10, 30, tzinfo=TIMEZONE)
MAIN_START = datetime(2018, 12, 19, 10, 0, tzinfo=TIMEZONE)
MAIN_END = datetime(2019, 2, 1, 10, 0, tzinfo=TIMEZONE)
ACCEPTANCE = {
    "pooled_temperature_rmse_c_max": 1.0,
    "pooled_absolute_temperature_bias_c_max": 0.5,
    "per_air_body_temperature_rmse_c_max": 1.5,
    "maximum_thermal_balance_residual_w": 1.0e-7,
    "fallback_permitted": False,
    "missing_scored_intervals_permitted": 0,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _memory_mb() -> dict[str, float]:
    memory = psutil.Process(os.getpid()).memory_info()
    return {
        "rss_mb": memory.rss / 1024**2,
        "peak_working_set_mb": getattr(memory, "peak_wset", memory.rss) / 1024**2,
    }


def _result_digest(result: Annex71RunResult) -> str:
    payload = json.dumps(
        {
            "timestamps": result.timestamps,
            "simulated_temperature_c": result.simulated_temperature_c,
            "residual": result.maximum_abs_thermal_balance_residual_w,
            "fallback": result.fallback_used,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _run_timed(records) -> tuple[Annex71RunResult, dict[str, float]]:
    gc.collect()
    memory_before = _memory_mb()
    start = time.perf_counter()
    result = run_object_scenario(records)
    elapsed = time.perf_counter() - start
    memory_after = _memory_mb()
    return result, {
        "runtime_seconds": elapsed,
        "timesteps": len(result.timestamps),
        "timesteps_per_second": len(result.timestamps) / elapsed,
        "seconds_per_timestep": elapsed / len(result.timestamps),
        "rss_before_mb": memory_before["rss_mb"],
        "rss_after_mb": memory_after["rss_mb"],
        "process_peak_working_set_mb": memory_after["peak_working_set_mb"],
    }


def _metrics_for_indices(
    result: Annex71RunResult, indices: np.ndarray
) -> dict[str, Any]:
    by_zone: dict[str, dict[str, float | int]] = {}
    pooled = []
    for zone_id in sorted(result.measured_temperature_c):
        measured = np.asarray(result.measured_temperature_c[zone_id])[indices]
        simulated = np.asarray(result.simulated_temperature_c[zone_id])[indices]
        residual = simulated - measured
        pooled.append(residual)
        by_zone[zone_id] = {
            "count": int(residual.size),
            "bias_c": float(np.mean(residual)),
            "mae_c": float(np.mean(np.abs(residual))),
            "rmse_c": float(np.sqrt(np.mean(np.square(residual)))),
            "maximum_abs_error_c": float(np.max(np.abs(residual))),
            "correlation": float(np.corrcoef(measured, simulated)[0, 1]),
        }
    residual = np.concatenate(pooled)
    return {
        "by_zone": by_zone,
        "pooled": {
            "count": int(residual.size),
            "bias_c": float(np.mean(residual)),
            "mae_c": float(np.mean(np.abs(residual))),
            "rmse_c": float(np.sqrt(np.mean(np.square(residual)))),
            "maximum_abs_error_c": float(np.max(np.abs(residual))),
        },
    }


def _error_diagnostics(
    result: Annex71RunResult, records, *, warmup_timesteps: int
) -> dict[str, Any]:
    timestamps = [datetime.fromisoformat(item) for item in result.timestamps]
    scored = np.arange(warmup_timesteps, len(timestamps), dtype=int)
    day = np.asarray(
        [index for index in scored if 8 <= timestamps[index].hour < 20], dtype=int
    )
    night = np.asarray(
        [index for index in scored if not 8 <= timestamps[index].hour < 20],
        dtype=int,
    )
    seven_days = max(1, round(7 * 24 * 60 / 10))
    record_by_timestamp = {item.timestamp.isoformat(): item for item in records}
    worst: list[dict[str, Any]] = []
    for zone_id in sorted(result.measured_temperature_c):
        measured = np.asarray(result.measured_temperature_c[zone_id])
        simulated = np.asarray(result.simulated_temperature_c[zone_id])
        for index in scored:
            source = record_by_timestamp[result.timestamps[index]]
            zone_source = source.zone(zone_id)
            worst.append(
                {
                    "timestamp": result.timestamps[index],
                    "zone_id": zone_id,
                    "measured_c": float(measured[index]),
                    "simulated_c": float(simulated[index]),
                    "error_c": float(simulated[index] - measured[index]),
                    "heating_power_w": zone_source.heating_power_w,
                    "internal_gain_w": zone_source.internal_gain_w,
                    "global_horizontal_radiation_w_m2": source.global_horizontal_radiation_w_m2,
                    "kitchen_door_opening_fraction": source.kitchen_door_opening_fraction,
                    "child1_window_opening_fraction": source.child1_window_opening_fraction,
                }
            )
    worst.sort(key=lambda row: abs(row["error_c"]), reverse=True)
    return {
        "day_definition": "08:00 <= fixed-CET interval-end timestamp < 20:00",
        "day": _metrics_for_indices(result, day),
        "night": _metrics_for_indices(result, night),
        "first_scored_week": _metrics_for_indices(result, scored[:seven_days]),
        "last_scored_week": _metrics_for_indices(result, scored[-seven_days:]),
        "ten_largest_absolute_errors": worst[:10],
    }


def _profile_sample(records) -> list[dict[str, Any]]:
    profiler = cProfile.Profile()
    profiler.enable()
    run_object_scenario(records)
    profiler.disable()
    stats = pstats.Stats(profiler)
    rows = []
    for (filename, line, function), values in sorted(
        stats.stats.items(), key=lambda item: item[1][3], reverse=True
    )[:15]:
        primitive_calls, total_calls, total_time, cumulative_time, _callers = values
        rows.append(
            {
                "function": function,
                "file": str(Path(filename).name),
                "line": line,
                "primitive_calls": primitive_calls,
                "total_calls": total_calls,
                "self_seconds": total_time,
                "cumulative_seconds": cumulative_time,
            }
        )
    return rows


def _gate(metrics: dict[str, Any], result: Annex71RunResult, missing: int) -> dict:
    checks = {
        "pooled_rmse": metrics["pooled"]["rmse_c"]
        <= ACCEPTANCE["pooled_temperature_rmse_c_max"],
        "pooled_bias": abs(metrics["pooled"]["bias_c"])
        <= ACCEPTANCE["pooled_absolute_temperature_bias_c_max"],
        "per_zone_rmse": all(
            item["rmse_c"] <= ACCEPTANCE["per_air_body_temperature_rmse_c_max"]
            for item in metrics["by_zone"].values()
        ),
        "thermal_balance": result.maximum_abs_thermal_balance_residual_w
        <= ACCEPTANCE["maximum_thermal_balance_residual_w"],
        "no_fallback": result.fallback_used is ACCEPTANCE["fallback_permitted"],
        "no_missing_scored_inputs": missing
        <= ACCEPTANCE["missing_scored_intervals_permitted"],
    }
    return {"checks": checks, "passed": all(checks.values())}


def _render_report(document: dict[str, Any]) -> str:
    ext = document["extended_primary_holdout"]
    main = document["main_experiment_posthoc"]
    lines = [
        "# Annex 71 physical-model runtime and error report v4",
        "",
        "Validation category: post-hoc empirical diagnostic for the Main Experiment; predeclared holdout evaluation with documented post-unsealing source-schedule, time, and RC-mapping corrections for the Extended Experiment. This is not pristine blind-validation evidence.",
        "",
        "## Decision",
        "",
        f"Strict gate: **{'passed' if ext['gate']['passed'] else 'rejected'}**. ",
        "The original Phase 4.9 row remains **blocked and rejected with alternative**. The temperature criteria fail and four missing outdoor-CO2 input rows independently violate the predeclared no-missing-input rule.",
        "",
        "## Runtime",
        "",
        "| Run | Timesteps | Runtime (s) | Steps/s | s/step | Process peak working set (MB) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, block in (("Main hourly", main), ("Extended 10-minute", ext)):
        runtime = block["runtime"]
        lines.append(
            f"| {name} | {runtime['timesteps']} | {runtime['runtime_seconds']:.3f} | "
            f"{runtime['timesteps_per_second']:.3f} | {runtime['seconds_per_timestep']:.6f} | "
            f"{runtime['process_peak_working_set_mb']:.1f} |"
        )
    benchmark = document["repeatability_benchmark"]
    lines.extend(
        [
            "",
            f"The {benchmark['sample_hours']}-hour 10-minute sample was run twice after warm-up: median {benchmark['median_runtime_seconds']:.3f} s, range {benchmark['runtime_range_seconds'][0]:.3f}-{benchmark['runtime_range_seconds'][1]:.3f} s. Output hashes were {'identical' if benchmark['deterministic'] else 'different'}.",
            "",
            "Runtime is wall-clock time on the recorded machine. Peak working set is process-wide Windows telemetry, so it includes Python, loaded source workbooks, and imported libraries.",
            "",
            "## Temperature error",
            "",
            "| Period | Bias (degC) | MAE (degC) | RMSE (degC) | Maximum abs. error (degC) |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for name, block in (("Main post-hoc", main), ("Extended primary", ext)):
        pooled = block["metrics"]["pooled"]
        lines.append(
            f"| {name} | {pooled['bias_c']:.3f} | {pooled['mae_c']:.3f} | "
            f"{pooled['rmse_c']:.3f} | {pooled['maximum_abs_error_c']:.3f} |"
        )
    lines.extend(
        [
            "",
            "### Extended primary holdout by air body",
            "",
            "| Air body | Bias (degC) | MAE (degC) | RMSE (degC) | Max abs. (degC) | Correlation |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for zone_id, metrics in ext["metrics"]["by_zone"].items():
        lines.append(
            f"| {zone_id} | {metrics['bias_c']:.3f} | {metrics['mae_c']:.3f} | "
            f"{metrics['rmse_c']:.3f} | {metrics['maximum_abs_error_c']:.3f} | "
            f"{metrics['correlation']:.3f} |"
        )
    lines.extend(
        [
            "",
            "### Error structure",
            "",
            f"Day pooled RMSE: {ext['diagnostics']['day']['pooled']['rmse_c']:.3f} degC; night pooled RMSE: {ext['diagnostics']['night']['pooled']['rmse_c']:.3f} degC. First scored week RMSE: {ext['diagnostics']['first_scored_week']['pooled']['rmse_c']:.3f} degC; last scored week RMSE: {ext['diagnostics']['last_scored_week']['pooled']['rmse_c']:.3f} degC.",
            "",
            f"Maximum absolute thermal-balance residual: {ext['maximum_abs_thermal_balance_residual_w']:.3e} W. Fallback used: {str(ext['fallback_used']).lower()}.",
            "",
            "## Model-error interpretation",
            "",
            "The component-resolved envelope, published thermal bridges, measured cellar boundary, fixed-CET alignment, measured opening/door states, and the specified blind states are now explicit. Remaining temperature residual is therefore not evidence for one more fitted whole-house conductance.",
            "",
            "The canonical adapter now couples the mass node through the full graph-derived opaque surface area instead of the incomplete floor-plus-interzone estimate. The coefficient itself remains the declared model constant; no residual-derived value was introduced.",
            "",
            "The strongest remaining structural risks are: (1) all construction layers are collapsed into one mass node per air body; (2) the single air-to-mass coefficient cannot represent layer-resolved surface transfer; (3) open-door exchange uses a prescribed symmetric 0.10 m/s mixing speed rather than a pressure/buoyancy large-opening network; (4) solar optics use normal-incidence glazing data and a generic 0.35 closed-blind multiplier; and (5) infiltration is the published whole-house estimate applied uniformly to each air body. The largest prior kitchen errors coincided with roughly 1.8 kW internal-heat pulses and an open kitchen/living door, exposing items (1)-(3). These are model-form uncertainties, not parameters authorized for post-hoc tuning.",
            "",
            "## Source and data-quality findings",
            "",
            f"Extended archive SHA-256: `{document['source']['extended_archive_sha256']}` ({document['source']['extended_archive_bytes']} bytes). The official source contains one conflicting duplicate row before the scored period and {ext['missing_scored_input_rows']} primary-period rows with missing outdoor CO2. The latter were carried forward only so thermal diagnostics could execute; the strict gate records failure.",
            "",
            "The workbook clock is fixed CET (UTC+1). Treating it as Europe/Berlin civil time creates duplicate UTC instants at the spring DST transition. Protocol 1.1 preserves the original protocol and documents this target-independent correction.",
            "",
            "## Reproduction",
            "",
            "```powershell",
            "uv run python scripts/validation_data/run_annex71_physical_runtime_error.py",
            "```",
            "",
            f"Implementation commit: `{document['software']['commit_sha']}`; dirty paths at execution: `{', '.join(document['software']['dirty_paths']) or 'none'}`.",
        ]
    )
    return "\n".join(lines) + "\n"


def run() -> dict[str, Any]:
    software = {
        "commit_sha": _git("rev-parse", "HEAD"),
        "branch": _git("branch", "--show-current"),
        "dirty_paths": _git("status", "--short").splitlines(),
        "python": sys.version,
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "ram_gib": psutil.virtual_memory().total / 1024**3,
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "pandas", "pydantic", "psutil", "pytest")
        },
    }

    load_start = time.perf_counter()
    main_all = load_annex71_intervals(MAIN_RAW, resolution_minutes=60)
    main_load_seconds = time.perf_counter() - load_start
    main_records = select_interval(
        main_all,
        start=MAIN_START - timedelta(hours=1),
        end_exclusive=MAIN_END,
    )

    load_start = time.perf_counter()
    extended_all = load_annex71_intervals(
        EXTENDED_RAW,
        resolution_minutes=10,
        experiment="extended",
        missing_outdoor_co2_policy="carry_forward_for_thermal_diagnostic",
        drop_duplicate_timestamps_before=PRIMARY_START,
    )
    extended_load_seconds = time.perf_counter() - load_start
    extended_records = select_interval(
        extended_all,
        start=PRIMARY_START - timedelta(minutes=10),
        end_exclusive=PRIMARY_END,
    )
    missing_rows = sum(bool(item.missing_source_fields) for item in extended_records)
    source_flags = [
        {"timestamp": item.timestamp.isoformat(), "flags": item.source_quality_flags}
        for item in extended_all
        if item.source_quality_flags
    ]

    run_object_scenario(extended_records[:13])
    repeat_records = extended_records[: 72 * 6 + 1]
    repeat_runs = [_run_timed(repeat_records) for _ in range(2)]
    repeat_times = [item[1]["runtime_seconds"] for item in repeat_runs]
    repeat_hashes = [_result_digest(item[0]) for item in repeat_runs]

    main_result, main_runtime = _run_timed(main_records)
    extended_result, extended_runtime = _run_timed(extended_records)
    main_metrics = temperature_metrics(main_result, warmup_timesteps=WARMUP_HOURS)
    extended_warmup = WARMUP_HOURS * 6
    extended_metrics = temperature_metrics(
        extended_result, warmup_timesteps=extended_warmup
    )
    gate = _gate(extended_metrics, extended_result, missing_rows)
    profile = _profile_sample(extended_records[:73])

    document = {
        "report_version": "4.0.0",
        "created_on": datetime.now(tz=TIMEZONE).isoformat(),
        "validation_category": {
            "main": "post_hoc_empirical_diagnostic",
            "extended": "predeclared_holdout_with_post_unsealing_source_and_model_mapping_corrections",
        },
        "blocked_gate_classification": "blocked and rejected with alternative"
        if not gate["passed"]
        else "blocked but passed with alternative",
        "protocols": [
            "data/validation/governance/annex71_extended_holdout_v1.json",
            "data/validation/governance/annex71_extended_holdout_v1_1.json",
            "data/validation/governance/annex71_extended_holdout_v1_2.json",
            "data/validation/governance/annex71_extended_holdout_v1_3.json",
        ],
        "software": software,
        "source": {
            "source_id": "iea-ebc-annex71-twin-houses-2020",
            "extended_archive_sha256": _sha256(EXTENDED_ARCHIVE),
            "extended_archive_bytes": EXTENDED_ARCHIVE.stat().st_size,
            "timezone": "Etc/GMT-1 fixed UTC+1/CET",
            "source_quality_flags": source_flags,
        },
        "main_experiment_posthoc": {
            "source_resolution_minutes": 60,
            "period_start": MAIN_START.isoformat(),
            "period_end_exclusive": MAIN_END.isoformat(),
            "load_runtime_seconds": main_load_seconds,
            "runtime": main_runtime,
            "metrics": main_metrics,
            "maximum_abs_thermal_balance_residual_w": main_result.maximum_abs_thermal_balance_residual_w,
            "fallback_used": main_result.fallback_used,
            "graph_sha256": main_result.graph_sha256,
        },
        "extended_primary_holdout": {
            "source_resolution_minutes": 10,
            "period_start": PRIMARY_START.isoformat(),
            "period_end_exclusive": PRIMARY_END.isoformat(),
            "warmup_hours": WARMUP_HOURS,
            "load_runtime_seconds": extended_load_seconds,
            "runtime": extended_runtime,
            "metrics": extended_metrics,
            "diagnostics": _error_diagnostics(
                extended_result,
                extended_records[1:],
                warmup_timesteps=extended_warmup,
            ),
            "maximum_abs_thermal_balance_residual_w": extended_result.maximum_abs_thermal_balance_residual_w,
            "fallback_used": extended_result.fallback_used,
            "graph_sha256": extended_result.graph_sha256,
            "missing_scored_input_rows": missing_rows,
            "acceptance": ACCEPTANCE,
            "gate": gate,
        },
        "repeatability_benchmark": {
            "sample_hours": 72,
            "measured_repetitions": 2,
            "runtime_seconds": repeat_times,
            "median_runtime_seconds": float(np.median(repeat_times)),
            "runtime_range_seconds": [min(repeat_times), max(repeat_times)],
            "output_sha256": repeat_hashes,
            "deterministic": len(set(repeat_hashes)) == 1,
        },
        "profile": {
            "sample_hours": 12,
            "sort": "cumulative_seconds",
            "top_functions": profile,
        },
        "known_limitations": [
            "The Extended result is not pristine blind evidence because source-loader corrections were required after target unsealing.",
            "Four missing outdoor-CO2 input rows were carried forward for thermal-only execution and fail the strict no-missing-input gate.",
            "One conflicting duplicate source row before the score period is dropped and reported.",
            "The two-node reduced-order model collapses all construction layers into one mass node per air body.",
            "Graph-derived opaque area now couples that mass node to zone air, but the transfer coefficient is still a single reduced-order value.",
            "Open-door exchange is prescribed symmetric mixing rather than a pressure-network solution.",
            "Closed-blind solar attenuation uses the declared generic object-engine multiplier, not a fitted optical model.",
        ],
    }
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(_render_report(document), encoding="utf-8")
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    document = run()
    summary = document["extended_primary_holdout"]
    print(
        json.dumps(
            {
                "report": str(REPORT_PATH.relative_to(REPOSITORY_ROOT)),
                "fixture": str(FIXTURE_PATH.relative_to(REPOSITORY_ROOT)),
                "runtime_seconds": summary["runtime"]["runtime_seconds"],
                "pooled_rmse_c": summary["metrics"]["pooled"]["rmse_c"],
                "pooled_bias_c": summary["metrics"]["pooled"]["bias_c"],
                "gate_passed": summary["gate"]["passed"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
