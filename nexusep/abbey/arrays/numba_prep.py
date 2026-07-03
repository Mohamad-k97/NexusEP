"""
ABBEY Numba preparation utilities.

Phase 17:
    Prepare the array core for future @njit.

This module is NOT itself a numba kernel.

It is allowed to use:
    - dataclasses
    - validation
    - dtype conversion
    - convenience allocation

The future njit kernels should receive only the raw arrays from here.
"""

from dataclasses import dataclass
import numpy as np

from nexusep.abbey.arrays import schema
from nexusep.abbey.arrays.airflow_kernels import N_AIRFLOW_LINK_COLS

try:
    from nexusep.abbey.arrays.acoustic_kernels import (
        N_ACOUSTIC_LINK_COLS,
        N_ZONE_NOISE_SOURCE_COLS,
    )
except Exception:
    N_ACOUSTIC_LINK_COLS = 7
    N_ZONE_NOISE_SOURCE_COLS = 3


# =============================================================================
# Containers outside njit
# =============================================================================

@dataclass
class NumbaWorkArrays:
    """
    Preallocated timestep work arrays.

    This dataclass is not passed into njit. Future njit calls should pass the
    raw arrays individually.
    """

    chosen_action_indices: np.ndarray
    chosen_action_ids: np.ndarray
    started_actions: np.ndarray
    sleep_pressure_scores: np.ndarray
    humidity_ratio_snapshot: np.ndarray


@dataclass
class NumbaOptionalArrays:
    """
    Empty/sentinel arrays replacing optional None arguments.
    """

    airflow_link_array: np.ndarray
    acoustic_link_array: np.ndarray
    zone_noise_source_array: np.ndarray
    weather_series: np.ndarray
    time_series: np.ndarray


@dataclass
class NumbaPreparedState:
    """
    Prepared state plus preallocated work/optional arrays.

    This is only a Python-side convenience container.
    """

    state: object
    work: NumbaWorkArrays
    optional: NumbaOptionalArrays


# =============================================================================
# Dtype / layout helpers
# =============================================================================

def as_float64_c(array):
    """
    Return C-contiguous float64 array.

    If already correct, numpy usually returns the same object.
    """
    return np.ascontiguousarray(array, dtype=np.float64)


def as_int64_c(array):
    return np.ascontiguousarray(array, dtype=np.int64)


def require_numeric_array(array, name):
    if not isinstance(array, np.ndarray):
        raise TypeError("%s must be a numpy array." % name)

    if array.dtype.kind not in ("i", "u", "f", "b"):
        raise TypeError(
            "%s must be numeric. Got dtype %s." % (name, array.dtype)
        )

    if array.dtype.kind == "O":
        raise TypeError("%s must not be object dtype." % name)

    return True


def require_float64_c(array, name):
    require_numeric_array(array, name)

    if array.dtype != np.float64:
        raise TypeError(
            "%s must be float64. Got %s." % (name, array.dtype)
        )

    if not array.flags["C_CONTIGUOUS"]:
        raise ValueError("%s must be C-contiguous." % name)

    return True


def require_int64_c(array, name):
    require_numeric_array(array, name)

    if array.dtype != np.int64:
        raise TypeError(
            "%s must be int64. Got %s." % (name, array.dtype)
        )

    if not array.flags["C_CONTIGUOUS"]:
        raise ValueError("%s must be C-contiguous." % name)

    return True


# =============================================================================
# State preparation
# =============================================================================

def make_state_arrays_float64_c(state):
    """
    Convert all core state arrays to C-contiguous float64.

    Current ABBEY packed state arrays intentionally store IDs/modes inside
    float64 arrays. This keeps the schema compact and stable.

    Standalone work arrays use int64 where appropriate.
    """
    state.static.person_static = as_float64_c(state.static.person_static)
    state.static.zone_static = as_float64_c(state.static.zone_static)
    state.static.dwelling_static = as_float64_c(state.static.dwelling_static)
    state.static.building_static = as_float64_c(state.static.building_static)
    state.static.system_static = as_float64_c(state.static.system_static)
    state.static.action_static = as_float64_c(state.static.action_static)

    state.dynamic.person_state = as_float64_c(state.dynamic.person_state)
    state.dynamic.zone_state = as_float64_c(state.dynamic.zone_state)
    state.dynamic.dwelling_state = as_float64_c(state.dynamic.dwelling_state)
    state.dynamic.building_state = as_float64_c(state.dynamic.building_state)
    state.dynamic.system_state = as_float64_c(state.dynamic.system_state)
    state.dynamic.process_state = as_float64_c(state.dynamic.process_state)
    state.dynamic.action_scores = as_float64_c(state.dynamic.action_scores)
    state.dynamic.weather_state = as_float64_c(state.dynamic.weather_state)
    state.dynamic.time_state = as_float64_c(state.dynamic.time_state)
    state.dynamic.internal_gains = as_float64_c(state.dynamic.internal_gains)
    state.dynamic.physics_result = as_float64_c(state.dynamic.physics_result)

    if state.series is not None:
        if state.series.weather_series is not None:
            state.series.weather_series = as_float64_c(state.series.weather_series)
        if state.series.time_series is not None:
            state.series.time_series = as_float64_c(state.series.time_series)

    return state


def validate_numba_core_arrays(state):
    """
    Validate arrays that would enter future njit kernels.
    """
    require_float64_c(state.static.person_static, "person_static")
    require_float64_c(state.static.zone_static, "zone_static")
    require_float64_c(state.static.dwelling_static, "dwelling_static")
    require_float64_c(state.static.building_static, "building_static")
    require_float64_c(state.static.system_static, "system_static")
    require_float64_c(state.static.action_static, "action_static")

    require_float64_c(state.dynamic.person_state, "person_state")
    require_float64_c(state.dynamic.zone_state, "zone_state")
    require_float64_c(state.dynamic.dwelling_state, "dwelling_state")
    require_float64_c(state.dynamic.building_state, "building_state")
    require_float64_c(state.dynamic.system_state, "system_state")
    require_float64_c(state.dynamic.process_state, "process_state")
    require_float64_c(state.dynamic.action_scores, "action_scores")
    require_float64_c(state.dynamic.weather_state, "weather_state")
    require_float64_c(state.dynamic.time_state, "time_state")
    require_float64_c(state.dynamic.internal_gains, "internal_gains")
    require_float64_c(state.dynamic.physics_result, "physics_result")

    if state.series is not None:
        if state.series.weather_series is not None:
            require_float64_c(state.series.weather_series, "weather_series")
        if state.series.time_series is not None:
            require_float64_c(state.series.time_series, "time_series")

    return True


# =============================================================================
# Work and optional arrays
# =============================================================================

def make_numba_work_arrays(state):
    n_persons = state.dynamic.person_state.shape[0]
    n_zones = state.dynamic.zone_state.shape[0]

    return NumbaWorkArrays(
        chosen_action_indices=np.zeros((n_persons,), dtype=np.int64),
        chosen_action_ids=np.zeros((n_persons,), dtype=np.int64),
        started_actions=np.zeros((n_persons,), dtype=np.float64),
        sleep_pressure_scores=np.zeros((n_persons,), dtype=np.float64),
        humidity_ratio_snapshot=np.zeros((n_zones,), dtype=np.float64),
    )


def make_empty_airflow_link_array_numba():
    return np.zeros((0, N_AIRFLOW_LINK_COLS), dtype=np.float64)


def make_empty_acoustic_link_array_numba():
    return np.zeros((0, N_ACOUSTIC_LINK_COLS), dtype=np.float64)


def make_empty_zone_noise_source_array_numba():
    return np.zeros((0, N_ZONE_NOISE_SOURCE_COLS), dtype=np.float64)


def make_optional_arrays_for_numba(
    state,
    airflow_link_array=None,
    acoustic_link_array=None,
    zone_noise_source_array=None,
):
    """
    Replace optional None arrays with empty numeric arrays.
    """
    if airflow_link_array is None:
        airflow_link_array = make_empty_airflow_link_array_numba()

    if acoustic_link_array is None:
        acoustic_link_array = make_empty_acoustic_link_array_numba()

    if zone_noise_source_array is None:
        zone_noise_source_array = make_empty_zone_noise_source_array_numba()

    weather_series = state.series.weather_series
    time_series = state.series.time_series

    return NumbaOptionalArrays(
        airflow_link_array=as_float64_c(airflow_link_array),
        acoustic_link_array=as_float64_c(acoustic_link_array),
        zone_noise_source_array=as_float64_c(zone_noise_source_array),
        weather_series=as_float64_c(weather_series),
        time_series=as_float64_c(time_series),
    )


def validate_numba_work_arrays(work, state):
    n_persons = state.dynamic.person_state.shape[0]
    n_zones = state.dynamic.zone_state.shape[0]

    require_int64_c(work.chosen_action_indices, "chosen_action_indices")
    require_int64_c(work.chosen_action_ids, "chosen_action_ids")
    require_float64_c(work.started_actions, "started_actions")
    require_float64_c(work.sleep_pressure_scores, "sleep_pressure_scores")
    require_float64_c(work.humidity_ratio_snapshot, "humidity_ratio_snapshot")

    if work.chosen_action_indices.shape != (n_persons,):
        raise ValueError("chosen_action_indices has wrong shape.")

    if work.chosen_action_ids.shape != (n_persons,):
        raise ValueError("chosen_action_ids has wrong shape.")

    if work.started_actions.shape != (n_persons,):
        raise ValueError("started_actions has wrong shape.")

    if work.sleep_pressure_scores.shape != (n_persons,):
        raise ValueError("sleep_pressure_scores has wrong shape.")

    if work.humidity_ratio_snapshot.shape != (n_zones,):
        raise ValueError("humidity_ratio_snapshot has wrong shape.")

    return True


def validate_numba_optional_arrays(optional):
    require_float64_c(optional.airflow_link_array, "airflow_link_array")
    require_float64_c(optional.acoustic_link_array, "acoustic_link_array")
    require_float64_c(optional.zone_noise_source_array, "zone_noise_source_array")
    require_float64_c(optional.weather_series, "weather_series")
    require_float64_c(optional.time_series, "time_series")

    if optional.airflow_link_array.ndim != 2:
        raise ValueError("airflow_link_array must be 2D.")

    if optional.acoustic_link_array.ndim != 2:
        raise ValueError("acoustic_link_array must be 2D.")

    if optional.zone_noise_source_array.ndim != 2:
        raise ValueError("zone_noise_source_array must be 2D.")

    return True


def prepare_state_for_numba(
    state,
    airflow_link_array=None,
    acoustic_link_array=None,
    zone_noise_source_array=None,
):
    """
    Prepare state/work/optional arrays for future njit calls.
    """
    state = make_state_arrays_float64_c(state)

    work = make_numba_work_arrays(state)

    optional = make_optional_arrays_for_numba(
        state=state,
        airflow_link_array=airflow_link_array,
        acoustic_link_array=acoustic_link_array,
        zone_noise_source_array=zone_noise_source_array,
    )

    validate_numba_core_arrays(state)
    validate_numba_work_arrays(work, state)
    validate_numba_optional_arrays(optional)

    return NumbaPreparedState(
        state=state,
        work=work,
        optional=optional,
    )