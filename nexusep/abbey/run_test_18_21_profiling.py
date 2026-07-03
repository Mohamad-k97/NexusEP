"""
ABBEY Phase 18.21 profiling.

Profiles the stable 8760-hour multizone dwelling benchmark.

Run:

    python -m nexusep.abbey.run_test_phase_18_21_profile_8760

Outputs:

    profiling_outputs/abbey_8760_logs_on_profile.txt
    profiling_outputs/abbey_8760_logs_on_profile.csv
    profiling_outputs/abbey_8760_logs_off_profile.txt
    profiling_outputs/abbey_8760_logs_off_profile.csv
"""

import cProfile
import csv
import io
import pstats
import time
from pathlib import Path

from nexusep.abbey.arrays import schema
from nexusep.abbey.arrays.encoder import compile_simulation_to_arrays
from nexusep.abbey.arrays.logger import allocate_logs_for_state
from nexusep.abbey.arrays.timestep import run_array_timestep

from nexusep.abbey.run_test_phase_18_0 import (
    make_8760_multizone_dwelling_input,
    N_TIMESTEPS,
    DT_MINUTES,
    RUN_ACOUSTICS,
)


OUTPUT_DIR = Path("profiling_outputs")
TOP_N = 80


def run_loop(state, logs):
    for time_index in range(N_TIMESTEPS):
        state, chosen_indices, chosen_ids, started = run_array_timestep(
            state=state,
            time_index=time_index,
            dt_minutes=DT_MINUTES,
            logs=logs,
            run_acoustics=RUN_ACOUSTICS,
        )

    return state


def validate_final_state(state):
    zone_temp = state.dynamic.zone_state[:, schema.ZONE_AIR_TEMPERATURE_C]
    zone_co2 = state.dynamic.zone_state[:, schema.ZONE_CO2_PPM]
    zone_rh = state.dynamic.zone_state[:, schema.ZONE_RELATIVE_HUMIDITY]

    person_hunger = state.dynamic.person_state[:, schema.PERSON_HUNGER]
    person_fatigue = state.dynamic.person_state[:, schema.PERSON_FATIGUE]

    assert zone_temp.min() > -50.0
    assert zone_temp.max() < 80.0
    assert zone_co2.min() > 0.0
    assert zone_co2.max() < 10000.0
    assert zone_rh.min() >= 0.0
    assert zone_rh.max() <= 1.0

    for value in person_hunger:
        assert value == value

    for value in person_fatigue:
        assert value == value


def write_profile_text(profile, output_path, sort_by="cumulative", top_n=80):
    stream = io.StringIO()

    stats = pstats.Stats(profile, stream=stream)
    stats.strip_dirs()
    stats.sort_stats(sort_by)
    stats.print_stats(top_n)

    output_path.write_text(stream.getvalue(), encoding="utf-8")


def write_profile_csv(profile, output_path):
    stats = pstats.Stats(profile)

    rows = []

    for func_key, stat in stats.stats.items():
        filename, line_number, function_name = func_key
        primitive_calls, total_calls, total_time, cumulative_time, callers = stat

        if total_calls > 0:
            total_time_per_call = total_time / float(total_calls)
            cumulative_time_per_call = cumulative_time / float(total_calls)
        else:
            total_time_per_call = 0.0
            cumulative_time_per_call = 0.0

        rows.append(
            {
                "filename": filename,
                "line_number": line_number,
                "function_name": function_name,
                "primitive_calls": primitive_calls,
                "total_calls": total_calls,
                "total_time_s": total_time,
                "cumulative_time_s": cumulative_time,
                "total_time_per_call_s": total_time_per_call,
                "cumulative_time_per_call_s": cumulative_time_per_call,
            }
        )

    rows.sort(
        key=lambda row: row["cumulative_time_s"],
        reverse=True,
    )

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "filename",
                "line_number",
                "function_name",
                "primitive_calls",
                "total_calls",
                "total_time_s",
                "cumulative_time_s",
                "total_time_per_call_s",
                "cumulative_time_per_call_s",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def run_profile_case(case_name, write_logs):
    print()
    print("Profiling case:", case_name)
    print("write_logs:", write_logs)

    readable_input = make_8760_multizone_dwelling_input()

    t0 = time.perf_counter()
    state = compile_simulation_to_arrays(readable_input)
    t1 = time.perf_counter()

    logs = None
    if write_logs:
        logs = allocate_logs_for_state(
            state=state,
            n_timesteps=N_TIMESTEPS,
            log_persons=True,
            log_zones=True,
            log_systems=True,
            log_dwellings=True,
            log_buildings=True,
        )

    t2 = time.perf_counter()

    profile = cProfile.Profile()

    loop_t0 = time.perf_counter()
    profile.enable()
    state = run_loop(state=state, logs=logs)
    profile.disable()
    loop_t1 = time.perf_counter()

    validate_final_state(state)

    compile_s = t1 - t0
    log_alloc_s = t2 - t1
    loop_s = loop_t1 - loop_t0

    simulated_hours = float(N_TIMESTEPS) * float(DT_MINUTES) / 60.0

    print("compile_s:", compile_s)
    print("log_alloc_s:", log_alloc_s)
    print("profiled_loop_s:", loop_s)
    print("seconds_per_timestep:", loop_s / float(N_TIMESTEPS))
    print("simulated_hours_per_second:", simulated_hours / loop_s)

    txt_path = OUTPUT_DIR / ("%s_profile.txt" % case_name)
    csv_path = OUTPUT_DIR / ("%s_profile.csv" % case_name)

    write_profile_text(
        profile=profile,
        output_path=txt_path,
        sort_by="cumulative",
        top_n=TOP_N,
    )

    write_profile_csv(
        profile=profile,
        output_path=csv_path,
    )

    print("wrote:", txt_path)
    print("wrote:", csv_path)

    print()
    print("Top cumulative functions:")
    stream = io.StringIO()
    stats = pstats.Stats(profile, stream=stream)
    stats.strip_dirs()
    stats.sort_stats("cumulative")
    stats.print_stats(25)
    print(stream.getvalue())

    return {
        "case_name": case_name,
        "write_logs": write_logs,
        "compile_s": compile_s,
        "log_alloc_s": log_alloc_s,
        "loop_s": loop_s,
        "seconds_per_timestep": loop_s / float(N_TIMESTEPS),
        "simulated_hours_per_second": simulated_hours / loop_s,
        "txt_path": str(txt_path),
        "csv_path": str(csv_path),
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    results.append(
        run_profile_case(
            case_name="abbey_8760_logs_on",
            write_logs=True,
        )
    )

    results.append(
        run_profile_case(
            case_name="abbey_8760_logs_off",
            write_logs=False,
        )
    )

    print()
    print("Summary")
    print("-------")

    for result in results:
        print(
            result["case_name"],
            "loop_s=",
            result["loop_s"],
            "seconds_per_timestep=",
            result["seconds_per_timestep"],
            "simulated_hours_per_second=",
            result["simulated_hours_per_second"],
        )

    if len(results) == 2:
        logs_on = results[0]["loop_s"]
        logs_off = results[1]["loop_s"]

        print()
        print("Logging overhead estimate")
        print("------------------------")
        print("logs_on_loop_s:", logs_on)
        print("logs_off_loop_s:", logs_off)
        print("difference_s:", logs_on - logs_off)

        if logs_on > 0.0:
            print("logging_share_of_logs_on:", (logs_on - logs_off) / logs_on)


if __name__ == "__main__":
    main()