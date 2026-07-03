"""
ABBEY v0.5 speed benchmark.

Goal:
    Measure yearly/hourly performance before deeper optimization.

Run examples:

    python -m nexusep.abbey.run_test_v0_5_speed --profile smoke_hourly --epw auto

    python -m nexusep.abbey.run_test_v0_5_speed --profile yearly_hourly --epw auto

    python -m nexusep.abbey.run_test_v0_5_speed --profile week_10min --epw auto

Development only:

    python -m nexusep.abbey.run_test_v0_5_speed --profile smoke_hourly --allow-synthetic-weather
"""

from pathlib import Path
import argparse
import copy
import json
import math
import time

import pandas as pd

from nexusep.abbey.run_test_v0_4 import (
    OUTPUT_ROOT,
    OUTPUT_MODE_MINIMAL,
    make_sim,
    make_weather_provider,
    validate_no_fallback,
    validate_physical_plausibility,
    validate_final_observation,
    validate_run_length,
    validate_output_records,
    assert_true,
    _paths_to_strings,
)


PROFILES = {
    "smoke_hourly": {
        "duration_hours": 24.0,
        "dt_minutes": 60,
        "start_weekday": 0,
        "holiday_days": [],
        "random_seed": 42,

        "require_epw": True,

        "save_yearly_outputs": True,
        "validate_minimal": True,
        "validate_debug": False,

        "progress_every_sim_hours": 6.0,
    },

    "week_hourly": {
        "duration_hours": 24.0 * 7.0,
        "dt_minutes": 60,
        "start_weekday": 0,
        "holiday_days": [],
        "random_seed": 42,

        "require_epw": True,

        "save_yearly_outputs": True,
        "validate_minimal": True,
        "validate_debug": False,

        "progress_every_sim_hours": 24.0,
    },

    "yearly_hourly": {
        "duration_hours": 24.0 * 365.0,
        "dt_minutes": 60,
        "start_weekday": 0,
        "holiday_days": [],
        "random_seed": 42,

        "require_epw": True,

        "save_yearly_outputs": True,
        "validate_minimal": True,
        "validate_debug": False,

        "progress_every_sim_hours": 24.0 * 7.0,
    },

    "week_10min": {
        "duration_hours": 24.0 * 7.0,
        "dt_minutes": 10,
        "start_weekday": 0,
        "holiday_days": [],
        "random_seed": 42,

        "require_epw": True,

        "save_yearly_outputs": True,
        "validate_minimal": True,
        "validate_debug": False,

        "progress_every_sim_hours": 24.0,
    },

    "yearly_10min": {
        "duration_hours": 24.0 * 365.0,
        "dt_minutes": 10,
        "start_weekday": 0,
        "holiday_days": [],
        "random_seed": 42,

        "require_epw": True,

        "save_yearly_outputs": True,
        "validate_minimal": True,
        "validate_debug": False,

        "progress_every_sim_hours": 24.0 * 7.0,
    },
}


def make_output_folder(output_root, profile_name):
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    index = 1

    while True:
        folder = output_root / (
            "abbey_v05_speed_"
            + str(profile_name)
            + "_run_{:03d}".format(index)
        )

        if not folder.exists():
            folder.mkdir(parents=True)
            (folder / "metadata").mkdir()
            (folder / "csv").mkdir()
            (folder / "building_yearly").mkdir()
            return folder

        index += 1


def save_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(
            payload,
            handle,
            indent=2,
            ensure_ascii=False,
            default=str,
        )


def seconds_to_minutes(value):
    return float(value) / 60.0


def finite_float(value, default=0.0):
    try:
        value = float(value)
    except Exception:
        return float(default)

    if not math.isfinite(value):
        return float(default)

    return value


def save_yearly_outputs_if_requested(settings, sim, run_folder):
    if not bool(settings.get("save_yearly_outputs", True)):
        return {}

    return sim.save_building_yearly_outputs(
        run_folder / "building_yearly",
        output_mode=OUTPUT_MODE_MINIMAL,
        include_timestep_diagnostics=False,
        include_long_records=False,
        include_interzone_summaries=False,
        include_interzone_timestep_records=False,
        include_window_detail_summaries=False,
        include_window_detail_timestep_records=False,
    )


def make_benchmark_summary(
    profile_name,
    settings,
    run_folder,
    weather_summary,
    simulation_seconds,
    export_seconds,
    sim,
    yearly_output_paths,
):
    duration_hours = float(settings["duration_hours"])
    dt_minutes = float(settings["dt_minutes"])

    expected_steps = int(round(duration_hours / (dt_minutes / 60.0)))
    simulated_days = duration_hours / 24.0

    seconds_per_step = simulation_seconds / max(float(expected_steps), 1.0)
    steps_per_second = float(expected_steps) / max(float(simulation_seconds), 1e-9)

    seconds_per_simulated_day = (
        simulation_seconds / max(float(simulated_days), 1e-9)
    )

    estimated_seconds_per_year = (
        simulation_seconds
        * (24.0 * 365.0)
        / max(duration_hours, 1e-9)
    )

    zone_count = len(list(sim.building_model.all_zone_ids()))

    return {
        "profile": profile_name,
        "version": "v0.5_speed",
        "output_folder": str(run_folder),

        "duration_hours": duration_hours,
        "dt_minutes": dt_minutes,
        "expected_steps": expected_steps,
        "zone_count": zone_count,

        "simulation_seconds": simulation_seconds,
        "simulation_minutes": seconds_to_minutes(simulation_seconds),
        "export_seconds": export_seconds,
        "export_minutes": seconds_to_minutes(export_seconds),
        "total_seconds": simulation_seconds + export_seconds,
        "total_minutes": seconds_to_minutes(simulation_seconds + export_seconds),

        "seconds_per_step": seconds_per_step,
        "steps_per_second": steps_per_second,
        "seconds_per_simulated_day": seconds_per_simulated_day,
        "estimated_seconds_per_year": estimated_seconds_per_year,
        "estimated_minutes_per_year": seconds_to_minutes(estimated_seconds_per_year),

        "building_zone_record_count": len(sim.building_zone_records),
        "building_dwelling_record_count": len(sim.building_dwelling_records),
        "building_record_count": len(sim.building_records),

        "weather": weather_summary,
        "yearly_output_paths": _paths_to_strings(yearly_output_paths),
    }


def validate_speed_run(settings, sim):
    validation_payload = validate_output_records(
        settings={
            "validate_debug": bool(settings.get("validate_debug", False)),
            "validate_minimal": bool(settings.get("validate_minimal", True)),
        },
        sim=sim,
    )

    zone_df = validation_payload["zone_df"]
    building_df = validation_payload["building_df"]

    validate_no_fallback(
        zone_df=zone_df,
        building_df=building_df,
    )

    validate_physical_plausibility(zone_df)
    validate_final_observation(sim)

    # For speed tests, run-length validation is still useful.
    validate_run_length(
        settings=settings,
        sim=sim,
    )

    return validation_payload


def run_profile(profile_name, settings, args):
    run_folder = make_output_folder(
        output_root=Path(args.output_root),
        profile_name=profile_name,
    )

    print("\nABBEY v0.5 speed benchmark")
    print("profile:", profile_name)
    print("duration_hours:", settings["duration_hours"])
    print("dt_minutes:", settings["dt_minutes"])
    print("output:", run_folder)

    weather_provider, weather_summary = make_weather_provider(
        settings={
            "duration_hours": settings["duration_hours"],
            "dt_minutes": settings["dt_minutes"],
            "require_epw": settings["require_epw"],
        },
        epw_arg=args.epw,
        allow_synthetic_weather=bool(args.allow_synthetic_weather),
    )

    sim_settings = copy.deepcopy(settings)

    # make_sim expects the v0.4 profile keys only for simulation setup.
    sim_settings.setdefault("start_weekday", 0)
    sim_settings.setdefault("holiday_days", [])
    sim_settings.setdefault("random_seed", 42)

    sim = make_sim(
        settings=sim_settings,
        weather_provider=weather_provider,
    )

    print("\nRunning simulation...")
    t0 = time.perf_counter()

    main_df = sim.run(
        progress_every_sim_hours=float(
            settings.get("progress_every_sim_hours", 24.0)
        ),
    )

    t1 = time.perf_counter()
    simulation_seconds = t1 - t0

    print("Simulation done.")
    print("simulation_seconds:", "{:.3f}".format(simulation_seconds))
    print("simulation_minutes:", "{:.3f}".format(seconds_to_minutes(simulation_seconds)))
    timer = getattr(sim, "timer", None)
    
    if timer is not None:
        timer.print_summary("ABBEY v0.5 internal timing")
    if timer is not None:
        save_json(
            run_folder / "metadata" / "timer_summary.json",
            timer.summary_rows(),
        )
    
        pd.DataFrame(timer.summary_rows()).to_csv(
            run_folder / "csv" / "timer_summary.csv",
            index=False,
        )
    print("\nValidating records...")
    validation_payload = validate_speed_run(
        settings=settings,
        sim=sim,
    )

    print("Validation done.")

    print("\nSaving yearly/minimal outputs...")
    export_t0 = time.perf_counter()

    yearly_output_paths = save_yearly_outputs_if_requested(
        settings=settings,
        sim=sim,
        run_folder=run_folder,
    )

    export_t1 = time.perf_counter()
    export_seconds = export_t1 - export_t0

    print("Export done.")
    print("export_seconds:", "{:.3f}".format(export_seconds))

    summary = make_benchmark_summary(
        profile_name=profile_name,
        settings=settings,
        run_folder=run_folder,
        weather_summary=weather_summary,
        simulation_seconds=simulation_seconds,
        export_seconds=export_seconds,
        sim=sim,
        yearly_output_paths=yearly_output_paths,
    )

    save_json(
        run_folder / "metadata" / "speed_summary.json",
        summary,
    )

    pd.DataFrame([summary]).to_csv(
        run_folder / "csv" / "speed_summary.csv",
        index=False,
    )

    print("\nSpeed summary:")
    print("steps_per_second:", "{:.3f}".format(summary["steps_per_second"]))
    print("seconds_per_step:", "{:.6f}".format(summary["seconds_per_step"]))
    print(
        "estimated_minutes_per_year:",
        "{:.3f}".format(summary["estimated_minutes_per_year"]),
    )
    print("output:", run_folder)

    return summary


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES.keys()),
        default="yearly_hourly",
    )

    parser.add_argument(
        "--epw",
        default="auto",
    )

    parser.add_argument(
        "--allow-synthetic-weather",
        action="store_true",
    )

    parser.add_argument(
        "--output-root",
        default=str(OUTPUT_ROOT),
    )

    return parser.parse_args()


def main():
    args = parse_args()

    profile_name = args.profile
    settings = copy.deepcopy(PROFILES[profile_name])

    summary = run_profile(
        profile_name=profile_name,
        settings=settings,
        args=args,
    )

    print("\nABBEY v0.5 speed benchmark passed.")


if __name__ == "__main__":
    main()