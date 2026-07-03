"""
ABBEY array-core performance profiler.

Phase 16:
    Measure first. Optimize later.

This module profiles:
    - array compile time
    - log allocation time
    - timestep-loop time
    - per-timestep average time
    - final-state decoding time
    - log decoding/DataFrame time
    - cProfile function groups:
        person update
        action scoring
        execution
        system update
        daylight
        airflow
        thermal
        CO2
        moisture
        acoustics
        logging
        decoder
        encoder

It also supports optional old-runner profiling through a user-provided callable.

Important:
    - No numba here.
    - No changes to physics here.
    - No optimization decisions without measurements.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
import cProfile
import io
import pstats
import time

import numpy as np

from nexusep.abbey.arrays.encoder import compile_simulation_to_arrays
from nexusep.abbey.arrays.decoder import (
    decode_simulation_state,
    decoded_state_to_dataframes,
)
from nexusep.abbey.arrays.logger import allocate_logs_for_state
from nexusep.abbey.arrays.timestep import run_array_timestep


# =============================================================================
# Timing containers
# =============================================================================

@dataclass
class TimingStat:
    name: str
    total_seconds: float = 0.0
    call_count: int = 0

    def add(self, elapsed_seconds):
        self.total_seconds += float(elapsed_seconds)
        self.call_count += 1

    @property
    def seconds_per_call(self):
        if self.call_count <= 0:
            return 0.0

        return self.total_seconds / float(self.call_count)

    def to_dict(self, denominator=None):
        if denominator is None:
            denominator = self.total_seconds

        if denominator > 0.0:
            share_percent = 100.0 * self.total_seconds / denominator
        else:
            share_percent = 0.0

        return {
            "name": self.name,
            "total_seconds": self.total_seconds,
            "call_count": self.call_count,
            "seconds_per_call": self.seconds_per_call,
            "share_percent": share_percent,
        }


class ProfileTimer(object):
    """
    Small explicit timer.

    This avoids adding dependencies to the array core.
    """

    def __init__(self, enabled=True):
        self.enabled = bool(enabled)
        self.stats = {}

    def measure(self, name):
        return _TimerContext(self, name)

    def add(self, name, elapsed_seconds):
        if not self.enabled:
            return

        if name not in self.stats:
            self.stats[name] = TimingStat(name=name)

        self.stats[name].add(elapsed_seconds)

    def get_total(self, name, default=0.0):
        if name not in self.stats:
            return default

        return self.stats[name].total_seconds

    def summary_rows(self, root_name=None):
        if root_name is not None and root_name in self.stats:
            denominator = self.stats[root_name].total_seconds
        else:
            denominator = 0.0
            for stat in self.stats.values():
                denominator += stat.total_seconds

        rows = []

        items = sorted(
            self.stats.items(),
            key=lambda item: item[1].total_seconds,
            reverse=True,
        )

        for _name, stat in items:
            rows.append(stat.to_dict(denominator=denominator))

        return rows

    def print_summary(self, title="ABBEY profiling summary", root_name=None):
        print_timing_rows(
            rows=self.summary_rows(root_name=root_name),
            title=title,
            root_name=root_name,
        )


class _TimerContext(object):
    def __init__(self, timer, name):
        self.timer = timer
        self.name = name
        self.start = None

    def __enter__(self):
        if self.timer.enabled:
            self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.timer.enabled:
            elapsed = time.perf_counter() - self.start
            self.timer.add(self.name, elapsed)

        return False


# =============================================================================
# cProfile containers
# =============================================================================

@dataclass
class CProfileFunctionRow:
    filename: str
    line_number: int
    function_name: str
    primitive_calls: int
    total_calls: int
    self_seconds: float
    cumulative_seconds: float

    def to_dict(self):
        return {
            "filename": self.filename,
            "line_number": self.line_number,
            "function_name": self.function_name,
            "primitive_calls": self.primitive_calls,
            "total_calls": self.total_calls,
            "self_seconds": self.self_seconds,
            "cumulative_seconds": self.cumulative_seconds,
        }


@dataclass
class CProfileGroupRow:
    group_name: str
    self_seconds: float = 0.0
    cumulative_seconds: float = 0.0
    primitive_calls: int = 0
    total_calls: int = 0
    share_percent_self: float = 0.0
    share_percent_cumulative: float = 0.0

    def to_dict(self):
        return {
            "group_name": self.group_name,
            "self_seconds": self.self_seconds,
            "cumulative_seconds": self.cumulative_seconds,
            "primitive_calls": self.primitive_calls,
            "total_calls": self.total_calls,
            "share_percent_self": self.share_percent_self,
            "share_percent_cumulative": self.share_percent_cumulative,
        }


@dataclass
class ProfiledArrayRunResult:
    state: Any
    logs: Any
    decoded_state: Any
    dataframes: Optional[Dict[str, Any]]
    log_dataframes: Optional[Dict[str, Any]]
    timer: ProfileTimer
    cprofile_stats: Any
    cprofile_top_functions: List[CProfileFunctionRow]
    cprofile_group_rows: List[CProfileGroupRow]
    metadata: Dict[str, Any]

    def print_report(self, top_n=20):
        print_profile_report(
            result=self,
            top_n=top_n,
        )

    def group_dataframe(self):
        return profile_group_rows_to_dataframe(self.cprofile_group_rows)

    def timing_dataframe(self):
        return timing_rows_to_dataframe(
            self.timer.summary_rows(root_name="array.total")
        )

    def top_function_dataframe(self):
        return cprofile_function_rows_to_dataframe(
            self.cprofile_top_functions
        )


@dataclass
class ProfiledOldRunResult:
    old_result: Any
    timer: ProfileTimer
    cprofile_stats: Any
    cprofile_top_functions: List[CProfileFunctionRow]
    cprofile_group_rows: List[CProfileGroupRow]
    metadata: Dict[str, Any]

    def print_report(self, top_n=20):
        print_old_profile_report(
            result=self,
            top_n=top_n,
        )


@dataclass
class ProfileComparisonResult:
    array_profile: ProfiledArrayRunResult
    old_profile: Optional[ProfiledOldRunResult]
    comparison: Dict[str, Any]


# =============================================================================
# cProfile helpers
# =============================================================================

PROFILE_GROUP_PATTERNS = [
    (
        "person_update",
        [
            "person_kernels",
            "update_person_dynamics",
            "update_person_perception",
            "update_person_needs",
            "update_perception",
            "update_needs",
        ],
    ),
    (
        "action_scoring",
        [
            "action_kernels",
            "score_all_person_actions",
            "score_action",
            "choose_best_action",
            "choose_best_actions",
        ],
    ),
    (
        "execution",
        [
            "execution_kernels",
            "run_execution_step",
            "start_action",
            "advance_execution",
            "process_state",
        ],
    ),
    (
        "system_update",
        [
            "system_kernels",
            "update_system_control_state",
            "enforce_system_constraints",
            "apply_control",
        ],
    ),
    (
        "daylight",
        [
            "daylight_kernels",
            "run_daylight_step",
            "step_building_daylight",
        ],
    ),
    (
        "airflow",
        [
            "airflow_kernels",
            "run_airflow_step",
            "step_building_airflow",
        ],
    ),
    (
        "thermal",
        [
            "thermal_kernels",
            "run_thermal_step",
            "step_building_thermal",
            "step_zone_thermal",
        ],
    ),
    (
        "co2",
        [
            "co2_kernels",
            "run_co2_step",
            "step_building_co2",
            "step_zone_co2",
        ],
    ),
    (
        "moisture",
        [
            "moisture_kernels",
            "run_moisture_step",
            "step_building_moisture",
            "step_zone_moisture",
        ],
    ),
    (
        "acoustics",
        [
            "acoustic_kernels",
            "run_acoustic_step",
            "step_building_acoustics",
        ],
    ),
    (
        "logging",
        [
            "logger.py",
            "write_current_state_to_logs",
            "write_person_log",
            "write_zone_log",
            "write_system_log",
            "write_dwelling_log",
            "write_building_log",
        ],
    ),
    (
        "decoder",
        [
            "decoder.py",
            "decode_",
            "to_dataframes",
        ],
    ),
    (
        "encoder",
        [
            "encoder.py",
            "compile_simulation_to_arrays",
            "_fill_",
        ],
    ),
]


def make_cprofile_stats_from_profiler(profiler):
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.strip_dirs()
    return stats


def extract_cprofile_function_rows(stats, sort_by="cumulative", top_n=50):
    """
    Convert pstats.Stats into sorted function rows.

    pstats tuple:
        (cc, nc, tt, ct, callers)

    cc = primitive calls
    nc = total calls
    tt = self time
    ct = cumulative time
    """
    rows = []

    for func_key, stat_tuple in stats.stats.items():
        filename, line_number, function_name = func_key
        primitive_calls, total_calls, self_seconds, cumulative_seconds, _callers = stat_tuple

        rows.append(
            CProfileFunctionRow(
                filename=str(filename),
                line_number=int(line_number),
                function_name=str(function_name),
                primitive_calls=int(primitive_calls),
                total_calls=int(total_calls),
                self_seconds=float(self_seconds),
                cumulative_seconds=float(cumulative_seconds),
            )
        )

    if sort_by == "self":
        rows.sort(key=lambda row: row.self_seconds, reverse=True)
    else:
        rows.sort(key=lambda row: row.cumulative_seconds, reverse=True)

    if top_n is not None:
        return rows[:int(top_n)]

    return rows


def _match_group(filename, function_name):
    combined = (str(filename) + " " + str(function_name)).lower()

    for group_name, patterns in PROFILE_GROUP_PATTERNS:
        for pattern in patterns:
            if pattern.lower() in combined:
                return group_name

    return "other"


def aggregate_cprofile_groups(stats):
    groups = {}

    total_self_seconds = 0.0
    total_cumulative_seconds = 0.0

    for func_key, stat_tuple in stats.stats.items():
        filename, _line_number, function_name = func_key
        primitive_calls, total_calls, self_seconds, cumulative_seconds, _callers = stat_tuple

        group_name = _match_group(filename, function_name)

        if group_name not in groups:
            groups[group_name] = CProfileGroupRow(group_name=group_name)

        group = groups[group_name]
        group.self_seconds += float(self_seconds)
        group.cumulative_seconds += float(cumulative_seconds)
        group.primitive_calls += int(primitive_calls)
        group.total_calls += int(total_calls)

        total_self_seconds += float(self_seconds)
        total_cumulative_seconds += float(cumulative_seconds)

    rows = list(groups.values())

    for row in rows:
        if total_self_seconds > 0.0:
            row.share_percent_self = 100.0 * row.self_seconds / total_self_seconds
        else:
            row.share_percent_self = 0.0

        if total_cumulative_seconds > 0.0:
            row.share_percent_cumulative = 100.0 * row.cumulative_seconds / total_cumulative_seconds
        else:
            row.share_percent_cumulative = 0.0

    rows.sort(key=lambda row: row.self_seconds, reverse=True)

    return rows


def top_bottleneck_groups(group_rows, top_n=5):
    rows = sorted(
        group_rows,
        key=lambda row: row.self_seconds,
        reverse=True,
    )

    return rows[:int(top_n)]


# =============================================================================
# Array runner profiling
# =============================================================================

def infer_n_timesteps_from_state(state):
    if state.series is not None:
        if state.series.time_series is not None:
            return int(state.series.time_series.shape[0])
        if state.series.weather_series is not None:
            return int(state.series.weather_series.shape[0])

    if state.metadata is not None:
        if "n_timesteps" in state.metadata:
            return int(state.metadata["n_timesteps"])

    return 1


def infer_dt_minutes_from_state(state, fallback=15.0):
    if state.metadata is not None:
        if "dt_minutes" in state.metadata:
            return float(state.metadata["dt_minutes"])

    return float(fallback)


def run_profiled_array_runner(
    readable_input,
    n_timesteps=None,
    dt_minutes=None,
    dtype=np.float64,
    decode_final_state=True,
    decode_to_dataframes=False,
    decode_logs_to_dataframes=False,
    run_acoustics=False,
    cprofile_top_n=50,
    profile_timestep_loop=True,
    log_persons=True,
    log_zones=True,
    log_systems=True,
    log_dwellings=True,
    log_buildings=True,
    airflow_link_array=None,
    acoustic_link_array=None,
    zone_noise_source_array=None,
    outdoor_noise_db=None,
    electricity_tariff=0.25,
    enforce_work_schedule=True,
):
    """
    Profile the new array runner without numba.

    This intentionally reimplements the high-level runner loop so each stage
    can be timed separately.
    """
    timer = ProfileTimer(enabled=True)

    state = None
    logs = None
    decoded_state = None
    dataframes = None
    log_dataframes = None
    profiler = cProfile.Profile()

    with timer.measure("array.total"):
        with timer.measure("array.compile"):
            state = compile_simulation_to_arrays(
                readable_input=readable_input,
                dtype=dtype,
                include_metadata=True,
            )

        if n_timesteps is None:
            n_timesteps = infer_n_timesteps_from_state(state)

        n_timesteps = int(n_timesteps)

        if dt_minutes is None:
            dt_minutes = infer_dt_minutes_from_state(state)

        dt_minutes = float(dt_minutes)

        with timer.measure("array.allocate_logs"):
            logs = allocate_logs_for_state(
                state=state,
                n_timesteps=n_timesteps,
                log_persons=log_persons,
                log_zones=log_zones,
                log_systems=log_systems,
                log_dwellings=log_dwellings,
                log_buildings=log_buildings,
                dtype=dtype,
            )

        chosen_action_history = np.zeros(
            (n_timesteps, state.dynamic.person_state.shape[0]),
            dtype=np.int64,
        )
        started_action_history = np.zeros(
            (n_timesteps, state.dynamic.person_state.shape[0]),
            dtype=np.float64,
        )

        if profile_timestep_loop:
            profiler.enable()

        with timer.measure("array.timestep_loop"):
            for time_index in range(n_timesteps):
                with timer.measure("array.timestep_total"):
                    (
                        state,
                        chosen_action_indices,
                        chosen_action_ids,
                        started_actions,
                    ) = run_array_timestep(
                        state=state,
                        time_index=time_index,
                        dt_minutes=dt_minutes,
                        logs=logs,
                        airflow_link_array=airflow_link_array,
                        acoustic_link_array=acoustic_link_array,
                        zone_noise_source_array=zone_noise_source_array,
                        outdoor_noise_db=outdoor_noise_db,
                        electricity_tariff=electricity_tariff,
                        enforce_work_schedule=enforce_work_schedule,
                        run_acoustics=run_acoustics,
                    )

                chosen_action_history[time_index, :] = chosen_action_ids[:]
                started_action_history[time_index, :] = started_actions[:]

        if profile_timestep_loop:
            profiler.disable()

        if decode_final_state:
            with timer.measure("array.decode_final_state"):
                decoded_state = decode_simulation_state(state)

            if decode_to_dataframes:
                with timer.measure("array.decode_final_dataframes"):
                    dataframes = decoded_state_to_dataframes(decoded_state)

        if decode_logs_to_dataframes:
            with timer.measure("array.decode_log_dataframes"):
                log_dataframes = logs.to_dataframes(state)

    stats = make_cprofile_stats_from_profiler(profiler)
    top_functions = extract_cprofile_function_rows(
        stats=stats,
        sort_by="cumulative",
        top_n=cprofile_top_n,
    )
    group_rows = aggregate_cprofile_groups(stats)

    metadata = {
        "runner": "array",
        "n_timesteps": int(n_timesteps),
        "dt_minutes": float(dt_minutes),
        "seconds_per_timestep": (
            timer.get_total("array.timestep_loop") / float(n_timesteps)
            if n_timesteps > 0
            else 0.0
        ),
        "chosen_action_history": chosen_action_history,
        "started_action_history": started_action_history,
    }

    return ProfiledArrayRunResult(
        state=state,
        logs=logs,
        decoded_state=decoded_state,
        dataframes=dataframes,
        log_dataframes=log_dataframes,
        timer=timer,
        cprofile_stats=stats,
        cprofile_top_functions=top_functions,
        cprofile_group_rows=group_rows,
        metadata=metadata,
    )


# =============================================================================
# Old runner profiling
# =============================================================================

def run_profiled_old_runner(
    old_runner_callable,
    *args,
    **kwargs
):
    """
    Profile an old/object runner callable.

    old_runner_callable should be something like:

        lambda: sim.run(progress_every_steps=None)

    or:

        lambda: AbbeySimulation.initialize(...).run(progress_every_steps=None)

    This function does not guess your old runner signature. Pass a zero-arg
    callable to avoid ambiguity.
    """
    if not callable(old_runner_callable):
        raise TypeError("old_runner_callable must be callable.")

    timer = ProfileTimer(enabled=True)
    profiler = cProfile.Profile()

    old_result = None

    with timer.measure("old.total"):
        profiler.enable()

        with timer.measure("old.run_callable"):
            old_result = old_runner_callable(*args, **kwargs)

        profiler.disable()

    stats = make_cprofile_stats_from_profiler(profiler)
    top_functions = extract_cprofile_function_rows(
        stats=stats,
        sort_by="cumulative",
        top_n=50,
    )
    group_rows = aggregate_cprofile_groups(stats)

    metadata = {
        "runner": "old",
    }

    return ProfiledOldRunResult(
        old_result=old_result,
        timer=timer,
        cprofile_stats=stats,
        cprofile_top_functions=top_functions,
        cprofile_group_rows=group_rows,
        metadata=metadata,
    )


def collect_old_abbey_timer_rows(old_simulation):
    """
    Collect rows from an old AbbeySimulation.timer if it exists.

    The old object runner already has AbbeyTimer measurements in some branches.
    """
    timer = getattr(old_simulation, "timer", None)

    if timer is None:
        return []

    if not hasattr(timer, "summary_rows"):
        return []

    return timer.summary_rows(root_name="simulation.step_total")


# =============================================================================
# Compare old/new profiles
# =============================================================================

def compare_profiled_runners(
    readable_input,
    old_runner_callable=None,
    array_runner_kwargs=None,
):
    """
    Profile array runner and optionally profile old runner.

    old_runner_callable:
        optional zero-arg callable.

    array_runner_kwargs:
        optional dict passed to run_profiled_array_runner.
    """
    if array_runner_kwargs is None:
        array_runner_kwargs = {}

    array_profile = run_profiled_array_runner(
        readable_input=readable_input,
        **array_runner_kwargs
    )

    old_profile = None

    if old_runner_callable is not None:
        old_profile = run_profiled_old_runner(
            old_runner_callable=old_runner_callable,
        )

    comparison = {
        "array_total_seconds": array_profile.timer.get_total("array.total"),
        "array_timestep_loop_seconds": array_profile.timer.get_total("array.timestep_loop"),
        "array_seconds_per_timestep": array_profile.metadata["seconds_per_timestep"],
    }

    if old_profile is not None:
        comparison["old_total_seconds"] = old_profile.timer.get_total("old.total")

        if comparison["array_total_seconds"] > 0.0:
            comparison["old_over_array_total_ratio"] = (
                comparison["old_total_seconds"]
                / comparison["array_total_seconds"]
            )
        else:
            comparison["old_over_array_total_ratio"] = None

    return ProfileComparisonResult(
        array_profile=array_profile,
        old_profile=old_profile,
        comparison=comparison,
    )


# =============================================================================
# Reporting
# =============================================================================

def print_timing_rows(rows, title="Timing summary", root_name=None):
    print("\n" + title)

    if root_name is not None:
        print("  denominator:", root_name)

    if not rows:
        print("  no rows")
        return

    for row in rows:
        print(
            "  "
            + str(row["name"]).ljust(42)
            + " total="
            + ("%.6f" % row["total_seconds"]).rjust(12)
            + "s"
            + " calls="
            + str(row["call_count"]).rjust(8)
            + " per_call="
            + ("%.9f" % row["seconds_per_call"]).rjust(14)
            + "s"
            + " share="
            + ("%.1f" % row["share_percent"]).rjust(6)
            + "%"
        )


def print_cprofile_group_rows(rows, title="cProfile group summary", top_n=None):
    print("\n" + title)

    if not rows:
        print("  no rows")
        return

    if top_n is not None:
        rows = rows[:int(top_n)]

    for row in rows:
        print(
            "  "
            + row.group_name.ljust(24)
            + " self="
            + ("%.6f" % row.self_seconds).rjust(12)
            + "s"
            + " cum="
            + ("%.6f" % row.cumulative_seconds).rjust(12)
            + "s"
            + " calls="
            + str(row.total_calls).rjust(8)
            + " self_share="
            + ("%.1f" % row.share_percent_self).rjust(6)
            + "%"
        )


def print_top_cprofile_functions(rows, title="Top cProfile functions", top_n=20):
    print("\n" + title)

    if not rows:
        print("  no rows")
        return

    for row in rows[:int(top_n)]:
        print(
            "  "
            + row.function_name.ljust(38)
            + " cum="
            + ("%.6f" % row.cumulative_seconds).rjust(12)
            + "s"
            + " self="
            + ("%.6f" % row.self_seconds).rjust(12)
            + "s"
            + " calls="
            + str(row.total_calls).rjust(8)
            + " file="
            + row.filename
            + ":"
            + str(row.line_number)
        )


def print_profile_report(result, top_n=20):
    result.timer.print_summary(
        title="ABBEY array-runner timing summary",
        root_name="array.total",
    )

    print_cprofile_group_rows(
        rows=result.cprofile_group_rows,
        title="ABBEY array-runner cProfile group summary",
        top_n=None,
    )

    print_top_cprofile_functions(
        rows=result.cprofile_top_functions,
        title="ABBEY array-runner top functions by cumulative time",
        top_n=top_n,
    )

    bottlenecks = top_bottleneck_groups(
        group_rows=result.cprofile_group_rows,
        top_n=5,
    )

    print_cprofile_group_rows(
        rows=bottlenecks,
        title="ABBEY array-runner top 5 bottleneck groups by self time",
        top_n=5,
    )

    print("\nArray runner derived metrics")
    print("  n_timesteps:", result.metadata["n_timesteps"])
    print("  dt_minutes:", result.metadata["dt_minutes"])
    print("  seconds_per_timestep:", "%.9f" % result.metadata["seconds_per_timestep"])


def print_old_profile_report(result, top_n=20):
    result.timer.print_summary(
        title="ABBEY old-runner timing summary",
        root_name="old.total",
    )

    print_cprofile_group_rows(
        rows=result.cprofile_group_rows,
        title="ABBEY old-runner cProfile group summary",
        top_n=None,
    )

    print_top_cprofile_functions(
        rows=result.cprofile_top_functions,
        title="ABBEY old-runner top functions by cumulative time",
        top_n=top_n,
    )


# =============================================================================
# DataFrame export helpers
# =============================================================================

def _require_pandas():
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas is required for profiler DataFrame export.")

    return pd


def timing_rows_to_dataframe(rows):
    pd = _require_pandas()
    return pd.DataFrame(rows)


def profile_group_rows_to_dataframe(rows):
    pd = _require_pandas()
    return pd.DataFrame([row.to_dict() for row in rows])


def cprofile_function_rows_to_dataframe(rows):
    pd = _require_pandas()
    return pd.DataFrame([row.to_dict() for row in rows])


def export_profile_result_csv(result, output_dir):
    """
    Export profiler summaries to CSV.

    output_dir:
        folder path
    """
    import os

    os.makedirs(output_dir, exist_ok=True)

    result.timing_dataframe().to_csv(
        os.path.join(output_dir, "timing_summary.csv"),
        index=False,
    )
    result.group_dataframe().to_csv(
        os.path.join(output_dir, "cprofile_group_summary.csv"),
        index=False,
    )
    result.top_function_dataframe().to_csv(
        os.path.join(output_dir, "cprofile_top_functions.csv"),
        index=False,
    )

    return True