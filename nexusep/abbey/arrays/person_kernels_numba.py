"""
ABBEY numba person kernels.

This module mirrors stable pieces of person_kernels.py.

Do not import this from the readable API.
Do not pass dataclasses here.
"""

from nexusep.abbey.arrays import schema
from nexusep.abbey.arrays.numba_support import optional_njit


PERSON_OCCUPANCY_STATE = schema.PERSON_OCCUPANCY_STATE
PERSON_CURRENT_ACTION_TYPE = schema.PERSON_CURRENT_ACTION_TYPE
PERSON_IS_HOME = schema.PERSON_IS_HOME
PERSON_HUNGER = schema.PERSON_HUNGER
PERSON_FATIGUE = schema.PERSON_FATIGUE
PERSON_DIRTY_CLOTHES = schema.PERSON_DIRTY_CLOTHES
PERSON_SICKNESS = schema.PERSON_SICKNESS
PERSON_LAZINESS = schema.PERSON_LAZINESS
PERSON_THERMAL_STRESS = schema.PERSON_THERMAL_STRESS
PERSON_AIR_QUALITY_STRESS = schema.PERSON_AIR_QUALITY_STRESS
PERSON_ACOUSTIC_STRESS = schema.PERSON_ACOUSTIC_STRESS

OCCUPANCY_HOME_SLEEPING = schema.OCCUPANCY_HOME_SLEEPING

ACTION_TYPE_SLEEP = schema.ACTION_TYPE_SLEEP
ACTION_TYPE_EAT = schema.ACTION_TYPE_EAT
ACTION_TYPE_COOK = schema.ACTION_TYPE_COOK
ACTION_TYPE_IDLE = schema.ACTION_TYPE_IDLE
ACTION_TYPE_DO_LAUNDRY = schema.ACTION_TYPE_DO_LAUNDRY


@optional_njit(cache=True)
def smooth_bounded_update_scalar_numba(x, up, down, dt_hours):
    return x + dt_hours * (up * (1.0 - x) - down * x)


@optional_njit(cache=True)
def clamp01_numba(x):
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


@optional_njit(cache=True)
def is_person_sleeping_numba(person_state, person_i):
    occupancy_state = int(person_state[person_i, PERSON_OCCUPANCY_STATE])
    action_type = int(person_state[person_i, PERSON_CURRENT_ACTION_TYPE])

    if occupancy_state == OCCUPANCY_HOME_SLEEPING:
        return True

    if action_type == ACTION_TYPE_SLEEP:
        return True

    return False


@optional_njit(cache=True)
def is_person_home_numba(person_state, person_i):
    return person_state[person_i, PERSON_IS_HOME] > 0.0


@optional_njit(cache=True)
def update_person_health_numba(
    person_state,
    dt_minutes,
    sickness_spontaneous_up=0.0,
    sickness_recovery_down=0.05,
):
    """
    Numba version of update_person_health(...).
    """
    dt_hours = dt_minutes / 60.0

    for person_i in range(person_state.shape[0]):
        person_state[person_i, PERSON_SICKNESS] = smooth_bounded_update_scalar_numba(
            person_state[person_i, PERSON_SICKNESS],
            sickness_spontaneous_up,
            sickness_recovery_down,
            dt_hours,
        )

    return True


@optional_njit(cache=True)
def update_person_needs_numba(
    person_state,
    person_static,
    zone_state,
    schedule_array,
    time_state,
    dt_minutes,
    sleep_pressure_scores,
    hunger_base_up=0.08,
    hunger_sleep_multiplier=0.25,
    hunger_fatigue_up=0.03,
    hunger_eat_down=2.5,
    hunger_cook_down=1.2,
    fatigue_base_up=0.02,
    fatigue_awake_up=0.05,
    fatigue_hunger_up=0.05,
    fatigue_sickness_up=0.10,
    fatigue_thermal_up=0.05,
    fatigue_air_up=0.04,
    fatigue_acoustic_up=0.03,
    fatigue_sleep_down=1.2,
    fatigue_rest_down=0.08,
    dirty_base_up=0.01,
    dirty_home_up=0.01,
    dirty_sickness_up=0.02,
    dirty_laundry_down=1.5,
    laziness_fatigue_up=0.08,
    laziness_sickness_up=0.05,
    laziness_sleep_pressure_up=0.04,
    laziness_base_down=0.04,
    laziness_sleep_down=0.08,
):
    """
    Numba version of update_person_needs(...).

    Differences from Python version:
        - sleep_pressure_scores is required
        - no None branch
        - returns True
    """
    dt_hours = dt_minutes / 60.0

    for person_i in range(person_state.shape[0]):
        action_type = int(person_state[person_i, PERSON_CURRENT_ACTION_TYPE])
        sleeping = is_person_sleeping_numba(person_state, person_i)
        home = is_person_home_numba(person_state, person_i)

        # Hunger
        hunger_up = hunger_base_up

        if sleeping:
            hunger_up *= hunger_sleep_multiplier

        hunger_up += hunger_fatigue_up * person_state[person_i, PERSON_FATIGUE]

        hunger_down = 0.0

        if action_type == ACTION_TYPE_EAT:
            hunger_down += hunger_eat_down

        if action_type == ACTION_TYPE_COOK:
            hunger_down += hunger_cook_down

        person_state[person_i, PERSON_HUNGER] = smooth_bounded_update_scalar_numba(
            person_state[person_i, PERSON_HUNGER],
            hunger_up,
            hunger_down,
            dt_hours,
        )

        # Fatigue
        fatigue_up = fatigue_base_up

        if not sleeping:
            fatigue_up += fatigue_awake_up

        fatigue_up += fatigue_hunger_up * person_state[person_i, PERSON_HUNGER]
        fatigue_up += fatigue_sickness_up * person_state[person_i, PERSON_SICKNESS]
        fatigue_up += fatigue_thermal_up * person_state[person_i, PERSON_THERMAL_STRESS]
        fatigue_up += fatigue_air_up * person_state[person_i, PERSON_AIR_QUALITY_STRESS]
        fatigue_up += fatigue_acoustic_up * person_state[person_i, PERSON_ACOUSTIC_STRESS]

        fatigue_down = 0.0

        if sleeping or action_type == ACTION_TYPE_SLEEP:
            fatigue_down += fatigue_sleep_down

        if action_type == ACTION_TYPE_IDLE:
            fatigue_down += fatigue_rest_down

        person_state[person_i, PERSON_FATIGUE] = smooth_bounded_update_scalar_numba(
            person_state[person_i, PERSON_FATIGUE],
            fatigue_up,
            fatigue_down,
            dt_hours,
        )

        # Dirty clothes
        dirty_up = dirty_base_up

        if home:
            dirty_up += dirty_home_up

        dirty_up += dirty_sickness_up * person_state[person_i, PERSON_SICKNESS]

        dirty_down = 0.0

        if action_type == ACTION_TYPE_DO_LAUNDRY:
            dirty_down += dirty_laundry_down

        person_state[person_i, PERSON_DIRTY_CLOTHES] = smooth_bounded_update_scalar_numba(
            person_state[person_i, PERSON_DIRTY_CLOTHES],
            dirty_up,
            dirty_down,
            dt_hours,
        )

        # Laziness / effort-friction proxy
        laziness_up = 0.0
        laziness_up += laziness_fatigue_up * person_state[person_i, PERSON_FATIGUE]
        laziness_up += laziness_sickness_up * person_state[person_i, PERSON_SICKNESS]
        laziness_up += laziness_sleep_pressure_up * sleep_pressure_scores[person_i]

        laziness_down = laziness_base_down

        if sleeping:
            laziness_down += laziness_sleep_down

        person_state[person_i, PERSON_LAZINESS] = smooth_bounded_update_scalar_numba(
            person_state[person_i, PERSON_LAZINESS],
            laziness_up,
            laziness_down,
            dt_hours,
        )

    return True