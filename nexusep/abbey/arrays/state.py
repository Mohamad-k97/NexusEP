"""
ABBEY array simulation state.

This module defines containers for the array-core state.

Important:
    - These dataclasses are only containers.
    - They are not timestep logic.
    - They are allowed to hold arrays.
    - The timestep kernels should receive arrays directly.
    - Human-readable objects should not enter the timestep core.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any

import numpy as np

from nexusep.abbey.arrays import schema


# =============================================================================
# Static array container
# =============================================================================

@dataclass
class SimulationArrayStatic:
    """
    Static simulation arrays.

    These arrays describe things that normally do not change during the
    timestep loop: IDs, geometry, capacities, traits, mappings, system limits,
    action properties, etc.

    These are numeric arrays. Human-readable names belong in mappings/metadata,
    not in the timestep core.
    """

    person_static: np.ndarray
    zone_static: np.ndarray
    dwelling_static: np.ndarray
    building_static: np.ndarray
    system_static: np.ndarray
    action_static: np.ndarray


# =============================================================================
# Dynamic array container
# =============================================================================

@dataclass
class SimulationArrayDynamic:
    """
    Dynamic simulation arrays.

    These arrays change during the simulation.
    """

    person_state: np.ndarray
    zone_state: np.ndarray
    dwelling_state: np.ndarray
    building_state: np.ndarray
    system_state: np.ndarray

    # Background appliances/processes:
    # washing machine, dishwasher, oven, shower process, etc.
    process_state: np.ndarray

    # Candidate action scores:
    # shape: [n_persons, n_actions, N_ACTION_SCORE_COLS]
    action_scores: np.ndarray

    # Current weather and time state.
    # These may be one-row/current-state arrays during timestep execution.
    weather_state: np.ndarray
    time_state: np.ndarray

    # Intermediate calculation arrays.
    internal_gains: np.ndarray
    physics_result: np.ndarray


# =============================================================================
# Optional full time-series inputs
# =============================================================================

@dataclass
class SimulationArraySeries:
    """
    Optional time-series arrays.

    These are not always needed for a single timestep, but are useful for a full
    simulation runner.

    Example:
        weather_series[t, weather_col]
        time_series[t, time_col]
    """

    weather_series: Optional[np.ndarray] = None
    time_series: Optional[np.ndarray] = None


# =============================================================================
# Human-readable mappings
# =============================================================================

@dataclass
class SimulationArrayMappings:
    """
    Mappings between readable IDs/names and numeric IDs.

    These mappings are useful for encoding and decoding.

    They should not be used inside njit/timestep kernels.
    """

    person_name_to_id: Optional[Dict[str, int]] = None
    person_id_to_name: Optional[Dict[int, str]] = None

    zone_name_to_id: Optional[Dict[str, int]] = None
    zone_id_to_name: Optional[Dict[int, str]] = None

    dwelling_name_to_id: Optional[Dict[str, int]] = None
    dwelling_id_to_name: Optional[Dict[int, str]] = None

    building_name_to_id: Optional[Dict[str, int]] = None
    building_id_to_name: Optional[Dict[int, str]] = None

    system_name_to_id: Optional[Dict[str, int]] = None
    system_id_to_name: Optional[Dict[int, str]] = None

    action_name_to_id: Optional[Dict[str, int]] = None
    action_id_to_name: Optional[Dict[int, str]] = None


# =============================================================================
# Main simulation state
# =============================================================================

@dataclass
class SimulationArrayState:
    """
    Full ABBEY array simulation state.

    This is the main object passed around by the array runner.

    It separates:
        - static arrays
        - dynamic arrays
        - optional time-series inputs
        - optional readable mappings
        - optional metadata

    The timestep loop should mainly operate on:

        state.dynamic.person_state
        state.dynamic.zone_state
        state.dynamic.system_state
        ...

    But later, when preparing numba kernels, pass the raw arrays directly into
    kernels instead of passing this dataclass.
    """

    static: SimulationArrayStatic
    dynamic: SimulationArrayDynamic

    series: Optional[SimulationArraySeries] = None
    mappings: Optional[SimulationArrayMappings] = None
    metadata: Optional[Dict[str, Any]] = None

    def validate(self):
        """
        Validate schema consistency and array shapes.

        This is intentionally outside the timestep core.
        """
        validate_simulation_array_state(self)
        return True


# =============================================================================
# Shape helpers
# =============================================================================

def _require_2d_array(array, name):
    if not isinstance(array, np.ndarray):
        raise TypeError("%s must be a numpy array." % name)

    if array.ndim != 2:
        raise ValueError(
            "%s must be a 2D array. Got shape %s."
            % (name, str(array.shape))
        )


def _require_3d_array(array, name):
    if not isinstance(array, np.ndarray):
        raise TypeError("%s must be a numpy array." % name)

    if array.ndim != 3:
        raise ValueError(
            "%s must be a 3D array. Got shape %s."
            % (name, str(array.shape))
        )


def _require_1d_or_2d_array(array, name):
    if not isinstance(array, np.ndarray):
        raise TypeError("%s must be a numpy array." % name)

    if array.ndim not in (1, 2):
        raise ValueError(
            "%s must be a 1D or 2D array. Got shape %s."
            % (name, str(array.shape))
        )


def _require_last_dim(array, expected_cols, name):
    actual_cols = array.shape[-1]
    if actual_cols != expected_cols:
        raise ValueError(
            "%s has wrong number of columns. Expected %s, got %s. Shape: %s"
            % (name, expected_cols, actual_cols, str(array.shape))
        )


# =============================================================================
# Static validation
# =============================================================================

def validate_static_arrays(static):
    """
    Validate static arrays.
    """
    _require_2d_array(static.person_static, "person_static")
    _require_last_dim(
        static.person_static,
        schema.N_PERSON_STATIC_COLS,
        "person_static",
    )

    _require_2d_array(static.zone_static, "zone_static")
    _require_last_dim(
        static.zone_static,
        schema.N_ZONE_STATIC_COLS,
        "zone_static",
    )

    _require_2d_array(static.dwelling_static, "dwelling_static")
    _require_last_dim(
        static.dwelling_static,
        schema.N_DWELLING_STATIC_COLS,
        "dwelling_static",
    )

    _require_2d_array(static.building_static, "building_static")
    _require_last_dim(
        static.building_static,
        schema.N_BUILDING_STATIC_COLS,
        "building_static",
    )

    _require_2d_array(static.system_static, "system_static")
    _require_last_dim(
        static.system_static,
        schema.N_SYSTEM_STATIC_COLS,
        "system_static",
    )

    _require_2d_array(static.action_static, "action_static")
    _require_last_dim(
        static.action_static,
        schema.N_ACTION_STATIC_COLS,
        "action_static",
    )

    return True


# =============================================================================
# Dynamic validation
# =============================================================================

def validate_dynamic_arrays(dynamic):
    """
    Validate dynamic arrays.
    """
    _require_2d_array(dynamic.person_state, "person_state")
    _require_last_dim(
        dynamic.person_state,
        schema.N_PERSON_STATE_COLS,
        "person_state",
    )

    _require_2d_array(dynamic.zone_state, "zone_state")
    _require_last_dim(
        dynamic.zone_state,
        schema.N_ZONE_STATE_COLS,
        "zone_state",
    )

    _require_2d_array(dynamic.dwelling_state, "dwelling_state")
    _require_last_dim(
        dynamic.dwelling_state,
        schema.N_DWELLING_STATE_COLS,
        "dwelling_state",
    )

    _require_2d_array(dynamic.building_state, "building_state")
    _require_last_dim(
        dynamic.building_state,
        schema.N_BUILDING_STATE_COLS,
        "building_state",
    )

    _require_2d_array(dynamic.system_state, "system_state")
    _require_last_dim(
        dynamic.system_state,
        schema.N_SYSTEM_STATE_COLS,
        "system_state",
    )

    _require_2d_array(dynamic.process_state, "process_state")
    _require_last_dim(
        dynamic.process_state,
        schema.N_PROCESS_STATE_COLS,
        "process_state",
    )

    _require_3d_array(dynamic.action_scores, "action_scores")
    _require_last_dim(
        dynamic.action_scores,
        schema.N_ACTION_SCORE_COLS,
        "action_scores",
    )

    _require_1d_or_2d_array(dynamic.weather_state, "weather_state")
    _require_last_dim(
        dynamic.weather_state,
        schema.N_WEATHER_STATE_COLS,
        "weather_state",
    )

    _require_1d_or_2d_array(dynamic.time_state, "time_state")
    _require_last_dim(
        dynamic.time_state,
        schema.N_TIME_STATE_COLS,
        "time_state",
    )

    _require_2d_array(dynamic.internal_gains, "internal_gains")
    _require_last_dim(
        dynamic.internal_gains,
        schema.N_INTERNAL_GAIN_COLS,
        "internal_gains",
    )

    _require_2d_array(dynamic.physics_result, "physics_result")
    _require_last_dim(
        dynamic.physics_result,
        schema.N_PHYSICS_RESULT_COLS,
        "physics_result",
    )

    return True


# =============================================================================
# Series validation
# =============================================================================

def validate_series_arrays(series):
    """
    Validate optional time-series arrays.
    """
    if series is None:
        return True

    if series.weather_series is not None:
        _require_2d_array(series.weather_series, "weather_series")
        _require_last_dim(
            series.weather_series,
            schema.N_WEATHER_STATE_COLS,
            "weather_series",
        )

    if series.time_series is not None:
        _require_2d_array(series.time_series, "time_series")
        _require_last_dim(
            series.time_series,
            schema.N_TIME_STATE_COLS,
            "time_series",
        )

    return True


# =============================================================================
# Cross-shape validation
# =============================================================================

def validate_cross_shapes(state):
    """
    Validate consistency between array dimensions.

    This checks only simple shape relationships. Deeper ID validation belongs
    in the encoder/registry phase.
    """
    static = state.static
    dynamic = state.dynamic

    n_persons = dynamic.person_state.shape[0]
    n_zones = dynamic.zone_state.shape[0]
    n_dwellings = dynamic.dwelling_state.shape[0]
    n_buildings = dynamic.building_state.shape[0]
    n_systems = dynamic.system_state.shape[0]
    n_actions = static.action_static.shape[0]

    if static.person_static.shape[0] != n_persons:
        raise ValueError(
            "person_static and person_state have different number of persons: "
            "%s vs %s" % (static.person_static.shape[0], n_persons)
        )

    if static.zone_static.shape[0] != n_zones:
        raise ValueError(
            "zone_static and zone_state have different number of zones: "
            "%s vs %s" % (static.zone_static.shape[0], n_zones)
        )

    if static.dwelling_static.shape[0] != n_dwellings:
        raise ValueError(
            "dwelling_static and dwelling_state have different number of dwellings: "
            "%s vs %s" % (static.dwelling_static.shape[0], n_dwellings)
        )

    if static.building_static.shape[0] != n_buildings:
        raise ValueError(
            "building_static and building_state have different number of buildings: "
            "%s vs %s" % (static.building_static.shape[0], n_buildings)
        )

    if static.system_static.shape[0] != n_systems:
        raise ValueError(
            "system_static and system_state have different number of systems: "
            "%s vs %s" % (static.system_static.shape[0], n_systems)
        )

    if dynamic.action_scores.shape[0] != n_persons:
        raise ValueError(
            "action_scores first dimension must match number of persons. "
            "Expected %s, got %s."
            % (n_persons, dynamic.action_scores.shape[0])
        )

    if dynamic.action_scores.shape[1] != n_actions:
        raise ValueError(
            "action_scores second dimension must match number of actions. "
            "Expected %s, got %s."
            % (n_actions, dynamic.action_scores.shape[1])
        )

    if dynamic.internal_gains.shape[0] != n_zones:
        raise ValueError(
            "internal_gains first dimension must match number of zones. "
            "Expected %s, got %s."
            % (n_zones, dynamic.internal_gains.shape[0])
        )

    if dynamic.physics_result.shape[0] != n_zones:
        raise ValueError(
            "physics_result first dimension must match number of zones. "
            "Expected %s, got %s."
            % (n_zones, dynamic.physics_result.shape[0])
        )

    return True


# =============================================================================
# Full validation
# =============================================================================

def validate_simulation_array_state(state):
    """
    Validate a full SimulationArrayState.
    """
    schema.validate_schema()

    if not isinstance(state.static, SimulationArrayStatic):
        raise TypeError("state.static must be a SimulationArrayStatic.")

    if not isinstance(state.dynamic, SimulationArrayDynamic):
        raise TypeError("state.dynamic must be a SimulationArrayDynamic.")

    validate_static_arrays(state.static)
    validate_dynamic_arrays(state.dynamic)
    validate_series_arrays(state.series)
    validate_cross_shapes(state)

    return True


# =============================================================================
# Allocation helpers
# =============================================================================

def make_empty_static_arrays(
    n_persons,
    n_zones,
    n_dwellings,
    n_buildings,
    n_systems,
    n_actions,
    dtype=np.float64,
):
    """
    Allocate empty static arrays.

    Values are initialized to 0. The encoder should fill them properly.
    """
    return SimulationArrayStatic(
        person_static=np.zeros(
            (n_persons, schema.N_PERSON_STATIC_COLS),
            dtype=dtype,
        ),
        zone_static=np.zeros(
            (n_zones, schema.N_ZONE_STATIC_COLS),
            dtype=dtype,
        ),
        dwelling_static=np.zeros(
            (n_dwellings, schema.N_DWELLING_STATIC_COLS),
            dtype=dtype,
        ),
        building_static=np.zeros(
            (n_buildings, schema.N_BUILDING_STATIC_COLS),
            dtype=dtype,
        ),
        system_static=np.zeros(
            (n_systems, schema.N_SYSTEM_STATIC_COLS),
            dtype=dtype,
        ),
        action_static=np.zeros(
            (n_actions, schema.N_ACTION_STATIC_COLS),
            dtype=dtype,
        ),
    )


def make_empty_dynamic_arrays(
    n_persons,
    n_zones,
    n_dwellings,
    n_buildings,
    n_systems,
    n_actions,
    n_processes,
    dtype=np.float64,
):
    """
    Allocate empty dynamic arrays.

    Values are initialized to 0. The encoder or initialization routine should
    fill IDs and initial conditions.
    """
    return SimulationArrayDynamic(
        person_state=np.zeros(
            (n_persons, schema.N_PERSON_STATE_COLS),
            dtype=dtype,
        ),
        zone_state=np.zeros(
            (n_zones, schema.N_ZONE_STATE_COLS),
            dtype=dtype,
        ),
        dwelling_state=np.zeros(
            (n_dwellings, schema.N_DWELLING_STATE_COLS),
            dtype=dtype,
        ),
        building_state=np.zeros(
            (n_buildings, schema.N_BUILDING_STATE_COLS),
            dtype=dtype,
        ),
        system_state=np.zeros(
            (n_systems, schema.N_SYSTEM_STATE_COLS),
            dtype=dtype,
        ),
        process_state=np.zeros(
            (n_processes, schema.N_PROCESS_STATE_COLS),
            dtype=dtype,
        ),
        action_scores=np.zeros(
            (n_persons, n_actions, schema.N_ACTION_SCORE_COLS),
            dtype=dtype,
        ),
        weather_state=np.zeros(
            (schema.N_WEATHER_STATE_COLS,),
            dtype=dtype,
        ),
        time_state=np.zeros(
            (schema.N_TIME_STATE_COLS,),
            dtype=dtype,
        ),
        internal_gains=np.zeros(
            (n_zones, schema.N_INTERNAL_GAIN_COLS),
            dtype=dtype,
        ),
        physics_result=np.zeros(
            (n_zones, schema.N_PHYSICS_RESULT_COLS),
            dtype=dtype,
        ),
    )


def make_empty_simulation_array_state(
    n_persons,
    n_zones,
    n_dwellings,
    n_buildings,
    n_systems,
    n_actions,
    n_processes,
    dtype=np.float64,
    metadata=None,
):
    """
    Allocate a complete empty SimulationArrayState.

    This is mainly for tests and for the future encoder.
    """
    static = make_empty_static_arrays(
        n_persons=n_persons,
        n_zones=n_zones,
        n_dwellings=n_dwellings,
        n_buildings=n_buildings,
        n_systems=n_systems,
        n_actions=n_actions,
        dtype=dtype,
    )

    dynamic = make_empty_dynamic_arrays(
        n_persons=n_persons,
        n_zones=n_zones,
        n_dwellings=n_dwellings,
        n_buildings=n_buildings,
        n_systems=n_systems,
        n_actions=n_actions,
        n_processes=n_processes,
        dtype=dtype,
    )

    state = SimulationArrayState(
        static=static,
        dynamic=dynamic,
        series=None,
        mappings=None,
        metadata=metadata,
    )

    state.validate()
    return state