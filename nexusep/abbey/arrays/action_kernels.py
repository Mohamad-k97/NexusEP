"""
ABBEY array action-scoring kernels.

Purpose:
    Score candidate actions numerically.

This module creates and fills:

    action_scores[person_i, action_i, score_col]

where action_scores columns are defined in schema.py.

Important:
    - No Action objects.
    - No ActionProposal objects.
    - No dicts in the scoring loop.
    - No strings in the scoring loop.
    - Deterministic argmax first.
    - Stochastic choice later.
"""

import math

import numpy as np

from nexusep.abbey.arrays import schema
from nexusep.abbey.arrays.person_kernels import (
    compute_sleep_pressure_scores,
    work_obligation_score_for_person,
)


# =============================================================================
# Constants
# =============================================================================

IMPOSSIBLE_SCORE = -1.0e9


# =============================================================================
# Small helpers
# =============================================================================

def _optional_schema_constant(name, fallback):
    """
    Allow action_kernels.py to work even if compatibility constants are not
    added to schema.py yet.
    """
    return getattr(schema, name, fallback)


ACTION_TYPE_DO_NOTHING = _optional_schema_constant(
    "ACTION_TYPE_DO_NOTHING",
    schema.ACTION_TYPE_IDLE,
)
ACTION_TYPE_EMERGENCY_EAT = _optional_schema_constant(
    "ACTION_TYPE_EMERGENCY_EAT",
    schema.ACTION_TYPE_EAT,
)
ACTION_TYPE_MAKE_HOT_DRINK = _optional_schema_constant(
    "ACTION_TYPE_MAKE_HOT_DRINK",
    schema.ACTION_TYPE_MAKE_COFFEE,
)
ACTION_TYPE_GO_TO_WORK = _optional_schema_constant(
    "ACTION_TYPE_GO_TO_WORK",
    schema.ACTION_TYPE_LEAVE_HOME,
)
ACTION_TYPE_GO_TO_SCHOOL = _optional_schema_constant(
    "ACTION_TYPE_GO_TO_SCHOOL",
    schema.ACTION_TYPE_LEAVE_HOME,
)
ACTION_TYPE_RUN_WASHING_MACHINE = _optional_schema_constant(
    "ACTION_TYPE_RUN_WASHING_MACHINE",
    schema.ACTION_TYPE_DO_LAUNDRY,
)
ACTION_TYPE_OPEN_CURTAIN = _optional_schema_constant(
    "ACTION_TYPE_OPEN_CURTAIN",
    schema.ACTION_TYPE_OPEN_BLINDS,
)
ACTION_TYPE_CLOSE_CURTAIN = _optional_schema_constant(
    "ACTION_TYPE_CLOSE_CURTAIN",
    schema.ACTION_TYPE_CLOSE_BLINDS,
)
ACTION_TYPE_TURN_LIGHTS_ON = _optional_schema_constant(
    "ACTION_TYPE_TURN_LIGHTS_ON",
    schema.ACTION_TYPE_TURN_LIGHT_ON,
)
ACTION_TYPE_TURN_LIGHTS_OFF = _optional_schema_constant(
    "ACTION_TYPE_TURN_LIGHTS_OFF",
    schema.ACTION_TYPE_TURN_LIGHT_OFF,
)


def clamp01(x):
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def safe_divide(x, scale):
    if scale <= 0.0:
        return 0.0
    return x / scale


def stress_from_excess(excess, scale):
    if scale <= 0.0:
        return 0.0

    if excess <= 0.0:
        return 0.0

    return math.tanh(excess / scale)


def is_person_home(person_state, person_i):
    return person_state[person_i, schema.PERSON_IS_HOME] > 0.0


def is_person_sleeping(person_state, person_i):
    occupancy_state = int(person_state[person_i, schema.PERSON_OCCUPANCY_STATE])
    action_type = int(person_state[person_i, schema.PERSON_CURRENT_ACTION_TYPE])

    if occupancy_state == schema.OCCUPANCY_HOME_SLEEPING:
        return True

    if action_type == schema.ACTION_TYPE_SLEEP:
        return True

    return False


def get_person_current_zone_id(person_state, person_i):
    return int(person_state[person_i, schema.PERSON_CURRENT_ZONE_ID])


def get_action_type(action_static, action_i):
    return int(action_static[action_i, schema.ACTION_TYPE])


def get_action_target_zone_id(action_static, person_state, person_i, action_i):
    target_zone_id = int(
        action_static[action_i, schema.ACTION_DEFAULT_TARGET_ZONE_ID]
    )

    if target_zone_id != schema.MISSING_ID:
        return target_zone_id

    return get_person_current_zone_id(person_state, person_i)


def find_first_system_for_zone(system_state, zone_id):
    n_systems = system_state.shape[0]

    for i in range(n_systems):
        if int(system_state[i, schema.SYSTEM_ZONE_ID]) == int(zone_id):
            return i

    return schema.MISSING_ID


def get_action_target_system_id(
    action_static,
    system_state,
    target_zone_id,
    action_i,
):
    target_system_id = int(
        action_static[action_i, schema.ACTION_DEFAULT_TARGET_SYSTEM_ID]
    )

    if target_system_id != schema.MISSING_ID:
        return target_system_id

    if target_zone_id == schema.MISSING_ID:
        return schema.MISSING_ID

    return find_first_system_for_zone(system_state, target_zone_id)


def is_heating_on(system_state, system_i):
    if system_i == schema.MISSING_ID:
        return False

    hvac_mode = int(system_state[system_i, schema.SYSTEM_HVAC_MODE])
    return hvac_mode == schema.HVAC_MODE_HEATING


def is_cooling_on(system_state, system_i):
    if system_i == schema.MISSING_ID:
        return False

    hvac_mode = int(system_state[system_i, schema.SYSTEM_HVAC_MODE])
    return hvac_mode == schema.HVAC_MODE_COOLING


def is_window_open(system_state, system_i):
    if system_i == schema.MISSING_ID:
        return False

    state = int(system_state[system_i, schema.SYSTEM_WINDOW_STATE])
    fraction = system_state[system_i, schema.SYSTEM_WINDOW_OPEN_FRACTION]

    return state == schema.WINDOW_STATE_OPEN or fraction > 0.0


def is_light_on(system_state, system_i):
    if system_i == schema.MISSING_ID:
        return False

    return int(system_state[system_i, schema.SYSTEM_LIGHT_STATE]) == schema.LIGHT_STATE_ON


def is_blind_closed(system_state, system_i):
    if system_i == schema.MISSING_ID:
        return False

    return system_state[system_i, schema.SYSTEM_BLIND_CLOSED_FRACTION] > 0.5


def action_is_light_on(action_type):
    return (
        action_type == schema.ACTION_TYPE_TURN_LIGHT_ON
        or action_type == ACTION_TYPE_TURN_LIGHTS_ON
    )


def action_is_light_off(action_type):
    return (
        action_type == schema.ACTION_TYPE_TURN_LIGHT_OFF
        or action_type == ACTION_TYPE_TURN_LIGHTS_OFF
    )


def action_is_laundry(action_type):
    return (
        action_type == schema.ACTION_TYPE_DO_LAUNDRY
        or action_type == ACTION_TYPE_RUN_WASHING_MACHINE
    )


def action_is_open_blinds_or_curtain(action_type):
    return (
        action_type == schema.ACTION_TYPE_OPEN_BLINDS
        or action_type == ACTION_TYPE_OPEN_CURTAIN
    )


def action_is_close_blinds_or_curtain(action_type):
    return (
        action_type == schema.ACTION_TYPE_CLOSE_BLINDS
        or action_type == ACTION_TYPE_CLOSE_CURTAIN
    )


def action_is_leave_home(action_type):
    return (
        action_type == schema.ACTION_TYPE_LEAVE_HOME
        or action_type == ACTION_TYPE_GO_TO_WORK
        or action_type == ACTION_TYPE_GO_TO_SCHOOL
    )


def action_is_return_home(action_type):
    return action_type == schema.ACTION_TYPE_RETURN_HOME


def action_is_idle(action_type):
    return (
        action_type == schema.ACTION_TYPE_IDLE
        or action_type == ACTION_TYPE_DO_NOTHING
    )


# =============================================================================
# Pressure helpers
# =============================================================================

def compute_zone_comfort_pressures(zone_state, zone_static, zone_id):
    """
    Return cold_pressure, heat_pressure for a zone.

    Cold pressure:
        current temp below min comfort temp

    Heat pressure:
        current temp above max comfort temp
    """
    if zone_id == schema.MISSING_ID:
        return 0.0, 0.0

    temp = zone_state[zone_id, schema.ZONE_AIR_TEMPERATURE_C]
    min_temp = zone_static[zone_id, schema.ZONE_STATIC_MIN_COMFORT_TEMP_C]
    max_temp = zone_static[zone_id, schema.ZONE_STATIC_MAX_COMFORT_TEMP_C]

    cold_pressure = stress_from_excess(min_temp - temp, 4.0)
    heat_pressure = stress_from_excess(temp - max_temp, 4.0)

    return cold_pressure, heat_pressure


def compute_zone_air_pressure(zone_state, zone_static, zone_id):
    if zone_id == schema.MISSING_ID:
        return 0.0

    co2 = zone_state[zone_id, schema.ZONE_CO2_PPM]
    max_co2 = zone_static[zone_id, schema.ZONE_STATIC_MAX_CO2_PPM]

    return stress_from_excess(co2 - max_co2, 700.0)


def compute_zone_visual_pressure(zone_state, zone_static, zone_id):
    if zone_id == schema.MISSING_ID:
        return 0.0

    lux = zone_state[zone_id, schema.ZONE_ILLUMINANCE_LUX]
    min_lux = zone_static[zone_id, schema.ZONE_STATIC_MIN_ILLUMINANCE_LUX]

    return stress_from_excess(min_lux - lux, 200.0)


def compute_zone_acoustic_pressure(zone_state, zone_static, zone_id):
    if zone_id == schema.MISSING_ID:
        return 0.0

    noise = zone_state[zone_id, schema.ZONE_NOISE_DB]
    max_noise = zone_static[zone_id, schema.ZONE_STATIC_MAX_NOISE_DB]

    return stress_from_excess(noise - max_noise, 15.0)


# =============================================================================
# Impossible-action masks
# =============================================================================

def action_impossible_for_person(
    person_state,
    person_static,
    zone_state,
    zone_static,
    system_state,
    system_static,
    process_state,
    action_static,
    schedule_array,
    time_state,
    person_i,
    action_i,
):
    """
    Return True if action_i is impossible for person_i.

    This is the array replacement for get_available_actions/is_action_available.
    """
    action_type = get_action_type(action_static, action_i)

    is_home = is_person_home(person_state, person_i)
    is_sleeping = is_person_sleeping(person_state, person_i)

    requires_home = action_static[action_i, schema.ACTION_REQUIRES_HOME] > 0.0
    requires_awake = action_static[action_i, schema.ACTION_REQUIRES_AWAKE] > 0.0
    can_run_while_away = (
        action_static[action_i, schema.ACTION_CAN_RUN_WHILE_AWAY] > 0.0
    )

    if requires_home and not is_home:
        return True

    if requires_awake and is_sleeping:
        return True

    if not is_home and not can_run_while_away:
        if not action_is_return_home(action_type):
            return True

    if action_is_leave_home(action_type):
        if not is_home:
            return True

    if action_is_return_home(action_type):
        if is_home:
            return True

    if action_type == schema.ACTION_TYPE_SLEEP:
        if not is_home:
            return True

    target_zone_id = get_action_target_zone_id(
        action_static=action_static,
        person_state=person_state,
        person_i=person_i,
        action_i=action_i,
    )

    target_system_id = get_action_target_system_id(
        action_static=action_static,
        system_state=system_state,
        target_zone_id=target_zone_id,
        action_i=action_i,
    )

    # System-control impossibility / no-op filters.
    if action_type == schema.ACTION_TYPE_OPEN_WINDOW:
        if target_system_id == schema.MISSING_ID:
            return True
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_WINDOW] <= 0.0:
            return True
        if is_window_open(system_state, target_system_id):
            return True

    if action_type == schema.ACTION_TYPE_CLOSE_WINDOW:
        if target_system_id == schema.MISSING_ID:
            return True
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_WINDOW] <= 0.0:
            return True
        if not is_window_open(system_state, target_system_id):
            return True

    if action_is_light_on(action_type):
        if target_system_id == schema.MISSING_ID:
            return True
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_LIGHTS] <= 0.0:
            return True
        if is_light_on(system_state, target_system_id):
            return True

    if action_is_light_off(action_type):
        if target_system_id == schema.MISSING_ID:
            return True
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_LIGHTS] <= 0.0:
            return True
        if not is_light_on(system_state, target_system_id):
            return True

    if action_type == schema.ACTION_TYPE_TURN_HEATING_ON:
        if target_system_id == schema.MISSING_ID:
            return True
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_HEATING] <= 0.0:
            return True
        if is_heating_on(system_state, target_system_id):
            return True

    if action_type == schema.ACTION_TYPE_TURN_HEATING_OFF:
        if target_system_id == schema.MISSING_ID:
            return True
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_HEATING] <= 0.0:
            return True
        if not is_heating_on(system_state, target_system_id):
            return True

    if action_type == schema.ACTION_TYPE_TURN_COOLING_ON:
        if target_system_id == schema.MISSING_ID:
            return True
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_COOLING] <= 0.0:
            return True
        if is_cooling_on(system_state, target_system_id):
            return True

    if action_type == schema.ACTION_TYPE_TURN_COOLING_OFF:
        if target_system_id == schema.MISSING_ID:
            return True
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_COOLING] <= 0.0:
            return True
        if not is_cooling_on(system_state, target_system_id):
            return True

    if action_is_open_blinds_or_curtain(action_type):
        if target_system_id == schema.MISSING_ID:
            return True
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_BLINDS] <= 0.0:
            return True
        if not is_blind_closed(system_state, target_system_id):
            return True

    if action_is_close_blinds_or_curtain(action_type):
        if target_system_id == schema.MISSING_ID:
            return True
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_BLINDS] <= 0.0:
            return True
        if is_blind_closed(system_state, target_system_id):
            return True

    if action_type == schema.ACTION_TYPE_TURN_VENTILATION_ON:
        if target_system_id == schema.MISSING_ID:
            return True
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_MECH_VENTILATION] <= 0.0:
            return True
        if int(system_state[target_system_id, schema.SYSTEM_VENTILATION_MODE]) != schema.VENTILATION_MODE_OFF:
            return True

    if action_type == schema.ACTION_TYPE_TURN_VENTILATION_OFF:
        if target_system_id == schema.MISSING_ID:
            return True
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_MECH_VENTILATION] <= 0.0:
            return True
        if int(system_state[target_system_id, schema.SYSTEM_VENTILATION_MODE]) == schema.VENTILATION_MODE_OFF:
            return True

    # Prevent starting the same background process twice.
    is_background = action_static[action_i, schema.ACTION_IS_BACKGROUND] > 0.0

    if is_background:
        for process_i in range(process_state.shape[0]):
            process_active = (
                int(process_state[process_i, schema.PROCESS_STATE])
                == schema.PROCESS_STATE_ACTIVE
            )

            if not process_active:
                continue

            process_type = int(process_state[process_i, schema.PROCESS_TYPE])
            appliance_type = int(
                action_static[action_i, schema.ACTION_DEFAULT_APPLIANCE_TYPE]
            )

            if appliance_type == schema.APPLIANCE_TYPE_WASHING_MACHINE:
                if process_type == schema.PROCESS_TYPE_WASHING_MACHINE:
                    return True

            if appliance_type == schema.APPLIANCE_TYPE_DISHWASHER:
                if process_type == schema.PROCESS_TYPE_DISHWASHER:
                    return True

    return False


# =============================================================================
# Score component functions
# =============================================================================

def score_hunger_component(
    person_state,
    action_static,
    person_i,
    action_i,
    hunger_food_weight=4.0,
    cook_bonus_threshold=0.65,
    cook_bonus=1.0,
    fatigue_cook_penalty_threshold=0.65,
    fatigue_cook_penalty_weight=1.5,
):
    action_type = get_action_type(action_static, action_i)

    hunger = person_state[person_i, schema.PERSON_HUNGER]
    fatigue = person_state[person_i, schema.PERSON_FATIGUE]

    score = 0.0

    if action_type == schema.ACTION_TYPE_EAT:
        score += hunger_food_weight * hunger

        hunger_effect = action_static[action_i, schema.ACTION_HUNGER_EFFECT]
        if hunger_effect < 0.0:
            score += abs(hunger_effect) * hunger

    if action_type == schema.ACTION_TYPE_COOK:
        score += hunger_food_weight * hunger

        if hunger >= cook_bonus_threshold:
            score += cook_bonus

        score -= fatigue_cook_penalty_weight * max(
            0.0,
            fatigue - fatigue_cook_penalty_threshold,
        )

    if action_type == ACTION_TYPE_EMERGENCY_EAT:
        if hunger < 0.85:
            score += -999.0
        else:
            score += 2.0 * hunger
            score += 1.5 * max(0.0, fatigue - 0.75)

    if action_type == ACTION_TYPE_MAKE_HOT_DRINK:
        sickness = person_state[person_i, schema.PERSON_SICKNESS]
        thermal = person_state[person_i, schema.PERSON_THERMAL_STRESS]

        score += 0.35
        score += 1.0 * sickness
        score += 0.03 * thermal

        if hunger > 0.65:
            score -= 1.0

        if fatigue > 0.75:
            score -= 1.0

    return score


def score_fatigue_sleep_component(
    person_state,
    action_static,
    sleep_pressure_scores,
    schedule_array,
    time_state,
    person_i,
    action_i,
    sleep_drive_weight=6.0,
    wake_drive_weight=4.0,
    work_penalty_weight=4.0,
    idle_rest_weight=0.5,
):
    action_type = get_action_type(action_static, action_i)

    fatigue = person_state[person_i, schema.PERSON_FATIGUE]
    sickness = person_state[person_i, schema.PERSON_SICKNESS]
    sleep_pressure = sleep_pressure_scores[person_i]
    sleeping = is_person_sleeping(person_state, person_i)

    minute_of_day = float(time_state[schema.TIME_MINUTE_OF_DAY])
    work_pressure = work_obligation_score_for_person(
        schedule_array=schedule_array,
        person_i=person_i,
        minute_of_day=minute_of_day,
    )

    score = 0.0

    if action_type == schema.ACTION_TYPE_SLEEP:
        score += sleep_drive_weight * (
            0.50 * sleep_pressure
            + 0.35 * fatigue
            + 0.15 * sickness
        )
        score -= work_penalty_weight * work_pressure

        if sleeping:
            score += 2.0

    if action_type == schema.ACTION_TYPE_WAKE_UP:
        if sleeping:
            wake_need = (
                0.45 * (1.0 - sleep_pressure)
                + 0.35 * (1.0 - fatigue)
                + 0.20 * work_pressure
            )
            score += wake_drive_weight * wake_need
        else:
            score -= 999.0

    if action_is_idle(action_type):
        score += idle_rest_weight * fatigue

    return score


def score_thermal_component(
    person_state,
    zone_state,
    zone_static,
    system_state,
    action_static,
    person_i,
    action_i,
    thermal_control_weight=5.0,
    heating_open_window_penalty=4.0,
    open_window_cold_penalty_weight=4.0,
    close_window_cold_bonus_weight=4.0,
):
    action_type = get_action_type(action_static, action_i)

    target_zone_id = get_action_target_zone_id(
        action_static=action_static,
        person_state=person_state,
        person_i=person_i,
        action_i=action_i,
    )
    target_system_id = get_action_target_system_id(
        action_static=action_static,
        system_state=system_state,
        target_zone_id=target_zone_id,
        action_i=action_i,
    )

    cold_pressure, heat_pressure = compute_zone_comfort_pressures(
        zone_state=zone_state,
        zone_static=zone_static,
        zone_id=target_zone_id,
    )

    thermal_discomfort = person_state[person_i, schema.PERSON_THERMAL_STRESS]
    cold_pressure *= max(0.25, thermal_discomfort)
    heat_pressure *= max(0.25, thermal_discomfort)

    window_open = is_window_open(system_state, target_system_id)

    score = 0.0

    if action_type == schema.ACTION_TYPE_TURN_HEATING_ON:
        score += thermal_control_weight * cold_pressure
        if window_open:
            score -= heating_open_window_penalty

    if action_type == schema.ACTION_TYPE_TURN_HEATING_OFF:
        score += thermal_control_weight * heat_pressure
        score -= 2.0 * cold_pressure

    if action_type == schema.ACTION_TYPE_TURN_COOLING_ON:
        score += thermal_control_weight * heat_pressure

    if action_type == schema.ACTION_TYPE_TURN_COOLING_OFF:
        score += thermal_control_weight * cold_pressure
        score -= 2.0 * heat_pressure

    if action_type == schema.ACTION_TYPE_OPEN_WINDOW:
        score += thermal_control_weight * heat_pressure
        score -= open_window_cold_penalty_weight * cold_pressure

    if action_type == schema.ACTION_TYPE_CLOSE_WINDOW:
        score += close_window_cold_bonus_weight * cold_pressure

    return score


def score_air_quality_component(
    person_state,
    zone_state,
    zone_static,
    system_state,
    action_static,
    person_i,
    action_i,
    window_weight=5.0,
    keep_window_open_high_co2_penalty=3.0,
):
    action_type = get_action_type(action_static, action_i)

    target_zone_id = get_action_target_zone_id(
        action_static=action_static,
        person_state=person_state,
        person_i=person_i,
        action_i=action_i,
    )

    air_pressure = compute_zone_air_pressure(
        zone_state=zone_state,
        zone_static=zone_static,
        zone_id=target_zone_id,
    )

    air_discomfort = person_state[person_i, schema.PERSON_AIR_QUALITY_STRESS]

    combined = max(air_pressure, air_discomfort)

    score = 0.0

    if action_type == schema.ACTION_TYPE_OPEN_WINDOW:
        score += window_weight * combined

    if action_type == schema.ACTION_TYPE_CLOSE_WINDOW:
        score -= keep_window_open_high_co2_penalty * combined

    if action_type == schema.ACTION_TYPE_TURN_VENTILATION_ON:
        score += window_weight * combined

    if action_type == schema.ACTION_TYPE_TURN_VENTILATION_OFF:
        score += window_weight * max(0.0, 1.0 - combined)

    return score


def score_visual_component(
    person_state,
    zone_state,
    zone_static,
    system_state,
    action_static,
    person_i,
    action_i,
    light_weight=4.0,
    blind_weight=2.0,
):
    action_type = get_action_type(action_static, action_i)

    target_zone_id = get_action_target_zone_id(
        action_static=action_static,
        person_state=person_state,
        person_i=person_i,
        action_i=action_i,
    )

    visual_pressure = compute_zone_visual_pressure(
        zone_state=zone_state,
        zone_static=zone_static,
        zone_id=target_zone_id,
    )

    visual_discomfort = person_state[person_i, schema.PERSON_VISUAL_STRESS]
    combined = max(visual_pressure, visual_discomfort)

    score = 0.0

    if action_is_light_on(action_type):
        score += light_weight * combined

    if action_is_light_off(action_type):
        score += light_weight * max(0.0, 1.0 - combined)

    if action_is_open_blinds_or_curtain(action_type):
        score += blind_weight * combined

    if action_is_close_blinds_or_curtain(action_type):
        score += blind_weight * max(0.0, 1.0 - combined)

    return score


def score_acoustic_component(
    person_state,
    zone_state,
    zone_static,
    system_state,
    action_static,
    person_i,
    action_i,
    close_window_noise_weight=3.0,
):
    action_type = get_action_type(action_static, action_i)

    target_zone_id = get_action_target_zone_id(
        action_static=action_static,
        person_state=person_state,
        person_i=person_i,
        action_i=action_i,
    )

    acoustic_pressure = compute_zone_acoustic_pressure(
        zone_state=zone_state,
        zone_static=zone_static,
        zone_id=target_zone_id,
    )

    acoustic_discomfort = person_state[person_i, schema.PERSON_ACOUSTIC_STRESS]
    combined = max(acoustic_pressure, acoustic_discomfort)

    score = 0.0

    if action_type == schema.ACTION_TYPE_CLOSE_WINDOW:
        score += close_window_noise_weight * combined

    if action_type == schema.ACTION_TYPE_OPEN_WINDOW:
        score -= close_window_noise_weight * combined

    return score


def score_laundry_component(
    person_state,
    action_static,
    person_i,
    action_i,
    laundry_weight=4.0,
):
    action_type = get_action_type(action_static, action_i)

    if not action_is_laundry(action_type):
        return 0.0

    dirty = person_state[person_i, schema.PERSON_DIRTY_CLOTHES]

    score = laundry_weight * dirty

    dirty_effect = action_static[action_i, schema.ACTION_DIRTY_CLOTHES_EFFECT]
    if dirty_effect < 0.0:
        score += abs(dirty_effect) * dirty

    return score


def score_tariff_component(
    action_static,
    action_i,
    electricity_tariff=0.25,
    tariff_weight=0.001,
):
    """
    Penalize electric power use.

    This is intentionally weak for now. Later this can use time-varying tariffs.
    """
    power_w = action_static[action_i, schema.ACTION_POWER_W]

    return -tariff_weight * electricity_tariff * power_w


def score_friction_component(
    person_state,
    person_static,
    action_static,
    person_i,
    action_i,
    effort_penalty_weight=1.0,
):
    """
    Effort/action-friction penalty.

    Current schema has:
        PERSON_LAZINESS
        PERSON_STATIC_ACTION_FRICTION
        ACTION_FRICTION

    The old object model used person.action_friction and action.effort.
    Here we combine available numeric columns.
    """
    laziness = person_state[person_i, schema.PERSON_LAZINESS]
    person_friction = person_static[person_i, schema.PERSON_STATIC_ACTION_FRICTION]
    action_friction = action_static[action_i, schema.ACTION_FRICTION]

    power_effort_proxy = 0.0
    duration_min = action_static[action_i, schema.ACTION_DURATION_MIN]

    if duration_min > 30.0:
        power_effort_proxy += min(1.0, duration_min / 240.0)

    penalty = (
        effort_penalty_weight
        * (action_friction + power_effort_proxy)
        * max(0.0, laziness)
        * max(0.0, person_friction)
    )

    return -penalty


def score_background_component(
    action_static,
    action_i,
    background_process_bonus=0.2,
):
    if action_static[action_i, schema.ACTION_IS_BACKGROUND] > 0.0:
        return background_process_bonus

    return 0.0


def score_work_travel_component(
    person_state,
    person_static,
    action_static,
    schedule_array,
    time_state,
    person_i,
    action_i,
    leave_work_weight=10.0,
    return_home_weight=8.0,
    sickness_leave_penalty=3.0,
    fatigue_leave_penalty=2.0,
):
    action_type = get_action_type(action_static, action_i)

    minute_of_day = float(time_state[schema.TIME_MINUTE_OF_DAY])
    work_pressure = work_obligation_score_for_person(
        schedule_array=schedule_array,
        person_i=person_i,
        minute_of_day=minute_of_day,
    )

    fatigue = person_state[person_i, schema.PERSON_FATIGUE]
    sickness = person_state[person_i, schema.PERSON_SICKNESS]

    score = 0.0

    if action_is_leave_home(action_type):
        score += leave_work_weight * work_pressure
        score -= sickness_leave_penalty * sickness
        score -= fatigue_leave_penalty * fatigue

    if action_is_return_home(action_type):
        score += return_home_weight * max(0.0, 1.0 - work_pressure)
        score += 0.5 * fatigue
        score += 0.8 * sickness

    return score


# =============================================================================
# Main scoring kernels
# =============================================================================

def reset_action_scores(action_scores):
    action_scores[:, :, :] = 0.0
    return action_scores

def score_all_person_actions(
    person_state,
    person_static,
    zone_state,
    zone_static,
    system_state,
    system_static,
    process_state,
    action_static,
    action_scores,
    schedule_array,
    time_state,
    sleep_pressure_scores=None,
    electricity_tariff=0.25,
    impossible_score=IMPOSSIBLE_SCORE,
):
    """
    Fast inlined action scorer.

    Same public function name and same output columns as the previous version.

    Main optimization:
        - avoid calling many tiny helper/component functions inside the
          person/action loop
        - cache person values once per person
        - cache action values once per action
        - compute work pressure once per person
        - resolve target zone/system once per action pair
    """
    n_persons = person_state.shape[0]
    n_actions = action_static.shape[0]
    n_systems = system_state.shape[0]
    n_processes = process_state.shape[0]

    if sleep_pressure_scores is None:
        sleep_pressure_scores = compute_sleep_pressure_scores(
            person_state=person_state,
            person_static=person_static,
            schedule_array=schedule_array,
            time_state=time_state,
        )

    # Fast reset.
    action_scores[:, :, :] = 0.0

    minute_of_day = float(time_state[schema.TIME_MINUTE_OF_DAY])

    for person_i in range(n_persons):
        # ---------------------------------------------------------------------
        # Cache person state.
        # ---------------------------------------------------------------------

        current_zone_id = int(
            person_state[person_i, schema.PERSON_CURRENT_ZONE_ID]
        )

        is_home = person_state[person_i, schema.PERSON_IS_HOME] > 0.0

        occupancy_state = int(
            person_state[person_i, schema.PERSON_OCCUPANCY_STATE]
        )
        current_action_type = int(
            person_state[person_i, schema.PERSON_CURRENT_ACTION_TYPE]
        )

        is_sleeping_now = (
            occupancy_state == schema.OCCUPANCY_HOME_SLEEPING
            or current_action_type == schema.ACTION_TYPE_SLEEP
        )

        hunger = person_state[person_i, schema.PERSON_HUNGER]
        fatigue = person_state[person_i, schema.PERSON_FATIGUE]
        dirty = person_state[person_i, schema.PERSON_DIRTY_CLOTHES]
        sickness = person_state[person_i, schema.PERSON_SICKNESS]
        laziness = person_state[person_i, schema.PERSON_LAZINESS]

        thermal_discomfort = person_state[
            person_i,
            schema.PERSON_THERMAL_STRESS,
        ]
        air_discomfort = person_state[
            person_i,
            schema.PERSON_AIR_QUALITY_STRESS,
        ]
        visual_discomfort = person_state[
            person_i,
            schema.PERSON_VISUAL_STRESS,
        ]
        acoustic_discomfort = person_state[
            person_i,
            schema.PERSON_ACOUSTIC_STRESS,
        ]

        person_friction = person_static[
            person_i,
            schema.PERSON_STATIC_ACTION_FRICTION,
        ]

        sleep_pressure = sleep_pressure_scores[person_i]

        work_pressure = work_obligation_score_for_person(
            schedule_array=schedule_array,
            person_i=person_i,
            minute_of_day=minute_of_day,
        )

        person_sleep_zone_id = int(
            person_static[person_i, schema.PERSON_STATIC_SLEEP_ZONE_ID]
        )

        for action_i in range(n_actions):
            # -----------------------------------------------------------------
            # Cache action static values.
            # -----------------------------------------------------------------

            action_type = int(action_static[action_i, schema.ACTION_TYPE])

            target_zone_id = int(
                action_static[
                    action_i,
                    schema.ACTION_DEFAULT_TARGET_ZONE_ID,
                ]
            )

            # Important for the sleep-zone patch:
            # sleep should be scored against the person's own sleep zone.
            if action_type == schema.ACTION_TYPE_SLEEP:
                if person_sleep_zone_id != schema.MISSING_ID:
                    target_zone_id = person_sleep_zone_id

            if target_zone_id == schema.MISSING_ID:
                target_zone_id = current_zone_id

            target_system_id = int(
                action_static[
                    action_i,
                    schema.ACTION_DEFAULT_TARGET_SYSTEM_ID,
                ]
            )

            if target_system_id == schema.MISSING_ID:
                if target_zone_id != schema.MISSING_ID:
                    for system_i in range(n_systems):
                        if int(system_state[system_i, schema.SYSTEM_ZONE_ID]) == target_zone_id:
                            target_system_id = system_i
                            break

            requires_home = (
                action_static[action_i, schema.ACTION_REQUIRES_HOME] > 0.0
            )
            requires_awake = (
                action_static[action_i, schema.ACTION_REQUIRES_AWAKE] > 0.0
            )
            can_run_while_away = (
                action_static[action_i, schema.ACTION_CAN_RUN_WHILE_AWAY] > 0.0
            )
            is_background = (
                action_static[action_i, schema.ACTION_IS_BACKGROUND] > 0.0
            )

            action_power_w = action_static[action_i, schema.ACTION_POWER_W]
            action_duration_min = action_static[
                action_i,
                schema.ACTION_DURATION_MIN,
            ]
            action_friction = action_static[action_i, schema.ACTION_FRICTION]
            action_hunger_effect = action_static[
                action_i,
                schema.ACTION_HUNGER_EFFECT,
            ]
            action_dirty_effect = action_static[
                action_i,
                schema.ACTION_DIRTY_CLOTHES_EFFECT,
            ]
            appliance_type = int(
                action_static[
                    action_i,
                    schema.ACTION_DEFAULT_APPLIANCE_TYPE,
                ]
            )

            # -----------------------------------------------------------------
            # Inline impossible-action mask.
            # -----------------------------------------------------------------

            impossible = False

            if requires_home and not is_home:
                impossible = True

            if not impossible and requires_awake and is_sleeping_now:
                impossible = True

            if not impossible:
                if not is_home and not can_run_while_away:
                    if action_type != schema.ACTION_TYPE_RETURN_HOME:
                        impossible = True

            if not impossible:
                if (
                    action_type == schema.ACTION_TYPE_LEAVE_HOME
                    or action_type == ACTION_TYPE_GO_TO_WORK
                    or action_type == ACTION_TYPE_GO_TO_SCHOOL
                ):
                    if not is_home:
                        impossible = True

            if not impossible:
                if action_type == schema.ACTION_TYPE_RETURN_HOME:
                    if is_home:
                        impossible = True

            if not impossible:
                if action_type == schema.ACTION_TYPE_SLEEP:
                    if not is_home:
                        impossible = True

            # System-control impossibility.
            if not impossible:
                has_target_system = target_system_id != schema.MISSING_ID

                if has_target_system:
                    hvac_mode = int(
                        system_state[
                            target_system_id,
                            schema.SYSTEM_HVAC_MODE,
                        ]
                    )
                    window_state = int(
                        system_state[
                            target_system_id,
                            schema.SYSTEM_WINDOW_STATE,
                        ]
                    )
                    window_fraction = system_state[
                        target_system_id,
                        schema.SYSTEM_WINDOW_OPEN_FRACTION,
                    ]
                    light_state = int(
                        system_state[
                            target_system_id,
                            schema.SYSTEM_LIGHT_STATE,
                        ]
                    )
                    blind_fraction = system_state[
                        target_system_id,
                        schema.SYSTEM_BLIND_CLOSED_FRACTION,
                    ]
                    ventilation_mode = int(
                        system_state[
                            target_system_id,
                            schema.SYSTEM_VENTILATION_MODE,
                        ]
                    )

                    has_window = (
                        system_static[
                            target_system_id,
                            schema.SYSTEM_STATIC_HAS_WINDOW,
                        ]
                        > 0.0
                    )
                    has_lights = (
                        system_static[
                            target_system_id,
                            schema.SYSTEM_STATIC_HAS_LIGHTS,
                        ]
                        > 0.0
                    )
                    has_heating = (
                        system_static[
                            target_system_id,
                            schema.SYSTEM_STATIC_HAS_HEATING,
                        ]
                        > 0.0
                    )
                    has_cooling = (
                        system_static[
                            target_system_id,
                            schema.SYSTEM_STATIC_HAS_COOLING,
                        ]
                        > 0.0
                    )
                    has_blinds = (
                        system_static[
                            target_system_id,
                            schema.SYSTEM_STATIC_HAS_BLINDS,
                        ]
                        > 0.0
                    )
                    has_mech_vent = (
                        system_static[
                            target_system_id,
                            schema.SYSTEM_STATIC_HAS_MECH_VENTILATION,
                        ]
                        > 0.0
                    )

                    window_open = (
                        window_state == schema.WINDOW_STATE_OPEN
                        or window_fraction > 0.0
                    )
                    light_on = light_state == schema.LIGHT_STATE_ON
                    blind_closed = blind_fraction > 0.5
                    heating_on = hvac_mode == schema.HVAC_MODE_HEATING
                    cooling_on = hvac_mode == schema.HVAC_MODE_COOLING
                else:
                    has_window = False
                    has_lights = False
                    has_heating = False
                    has_cooling = False
                    has_blinds = False
                    has_mech_vent = False
                    window_open = False
                    light_on = False
                    blind_closed = False
                    heating_on = False
                    cooling_on = False
                    ventilation_mode = schema.VENTILATION_MODE_OFF

                if action_type == schema.ACTION_TYPE_OPEN_WINDOW:
                    if not has_target_system or not has_window or window_open:
                        impossible = True

                elif action_type == schema.ACTION_TYPE_CLOSE_WINDOW:
                    if not has_target_system or not has_window or not window_open:
                        impossible = True

                elif (
                    action_type == schema.ACTION_TYPE_TURN_LIGHT_ON
                    or action_type == ACTION_TYPE_TURN_LIGHTS_ON
                ):
                    if not has_target_system or not has_lights or light_on:
                        impossible = True

                elif (
                    action_type == schema.ACTION_TYPE_TURN_LIGHT_OFF
                    or action_type == ACTION_TYPE_TURN_LIGHTS_OFF
                ):
                    if not has_target_system or not has_lights or not light_on:
                        impossible = True

                elif action_type == schema.ACTION_TYPE_TURN_HEATING_ON:
                    if not has_target_system or not has_heating or heating_on:
                        impossible = True

                elif action_type == schema.ACTION_TYPE_TURN_HEATING_OFF:
                    if not has_target_system or not has_heating or not heating_on:
                        impossible = True

                elif action_type == schema.ACTION_TYPE_TURN_COOLING_ON:
                    if not has_target_system or not has_cooling or cooling_on:
                        impossible = True

                elif action_type == schema.ACTION_TYPE_TURN_COOLING_OFF:
                    if not has_target_system or not has_cooling or not cooling_on:
                        impossible = True

                elif (
                    action_type == schema.ACTION_TYPE_OPEN_BLINDS
                    or action_type == ACTION_TYPE_OPEN_CURTAIN
                ):
                    if not has_target_system or not has_blinds or not blind_closed:
                        impossible = True

                elif (
                    action_type == schema.ACTION_TYPE_CLOSE_BLINDS
                    or action_type == ACTION_TYPE_CLOSE_CURTAIN
                ):
                    if not has_target_system or not has_blinds or blind_closed:
                        impossible = True

                elif action_type == schema.ACTION_TYPE_TURN_VENTILATION_ON:
                    if (
                        not has_target_system
                        or not has_mech_vent
                        or ventilation_mode != schema.VENTILATION_MODE_OFF
                    ):
                        impossible = True

                elif action_type == schema.ACTION_TYPE_TURN_VENTILATION_OFF:
                    if (
                        not has_target_system
                        or not has_mech_vent
                        or ventilation_mode == schema.VENTILATION_MODE_OFF
                    ):
                        impossible = True

            # Prevent starting same background appliance twice.
            if not impossible and is_background:
                for process_i in range(n_processes):
                    process_active = (
                        int(process_state[process_i, schema.PROCESS_STATE])
                        == schema.PROCESS_STATE_ACTIVE
                    )

                    if not process_active:
                        continue

                    process_type = int(
                        process_state[process_i, schema.PROCESS_TYPE]
                    )

                    if appliance_type == schema.APPLIANCE_TYPE_WASHING_MACHINE:
                        if process_type == schema.PROCESS_TYPE_WASHING_MACHINE:
                            impossible = True
                            break

                    if appliance_type == schema.APPLIANCE_TYPE_DISHWASHER:
                        if process_type == schema.PROCESS_TYPE_DISHWASHER:
                            impossible = True
                            break

            if impossible:
                action_scores[
                    person_i,
                    action_i,
                    schema.ACTION_SCORE_IMPOSSIBLE_MASK,
                ] = 1.0
                action_scores[
                    person_i,
                    action_i,
                    schema.ACTION_SCORE_TOTAL,
                ] = impossible_score
                continue

            # -----------------------------------------------------------------
            # Precompute target-zone pressures once.
            # -----------------------------------------------------------------

            cold_pressure = 0.0
            heat_pressure = 0.0
            air_pressure = 0.0
            visual_pressure = 0.0
            acoustic_pressure = 0.0

            if target_zone_id != schema.MISSING_ID:
                zone_temp = zone_state[
                    target_zone_id,
                    schema.ZONE_AIR_TEMPERATURE_C,
                ]
                min_temp = zone_static[
                    target_zone_id,
                    schema.ZONE_STATIC_MIN_COMFORT_TEMP_C,
                ]
                max_temp = zone_static[
                    target_zone_id,
                    schema.ZONE_STATIC_MAX_COMFORT_TEMP_C,
                ]

                cold_excess = min_temp - zone_temp
                heat_excess = zone_temp - max_temp

                if cold_excess > 0.0:
                    cold_pressure = math.tanh(cold_excess / 4.0)

                if heat_excess > 0.0:
                    heat_pressure = math.tanh(heat_excess / 4.0)

                zone_co2 = zone_state[target_zone_id, schema.ZONE_CO2_PPM]
                max_co2 = zone_static[
                    target_zone_id,
                    schema.ZONE_STATIC_MAX_CO2_PPM,
                ]
                co2_excess = zone_co2 - max_co2

                if co2_excess > 0.0:
                    air_pressure = math.tanh(co2_excess / 700.0)

                zone_lux = zone_state[
                    target_zone_id,
                    schema.ZONE_ILLUMINANCE_LUX,
                ]
                min_lux = zone_static[
                    target_zone_id,
                    schema.ZONE_STATIC_MIN_ILLUMINANCE_LUX,
                ]
                lux_excess = min_lux - zone_lux

                if lux_excess > 0.0:
                    visual_pressure = math.tanh(lux_excess / 200.0)

                zone_noise = zone_state[target_zone_id, schema.ZONE_NOISE_DB]
                max_noise = zone_static[
                    target_zone_id,
                    schema.ZONE_STATIC_MAX_NOISE_DB,
                ]
                noise_excess = zone_noise - max_noise

                if noise_excess > 0.0:
                    acoustic_pressure = math.tanh(noise_excess / 15.0)

            # -----------------------------------------------------------------
            # Hunger score.
            # -----------------------------------------------------------------
            
            hunger_score = 0.0
            
            # Keep these as independent if blocks, not if/elif.
            # Reason:
            #     compatibility constants can alias each other.
            #     Example:
            #         ACTION_TYPE_EMERGENCY_EAT can fall back to ACTION_TYPE_EAT.
            #     The reference scorer therefore applies both blocks.
            if action_type == schema.ACTION_TYPE_EAT:
                hunger_score += 4.0 * hunger
            
                if action_hunger_effect < 0.0:
                    hunger_score += abs(action_hunger_effect) * hunger
            
            if action_type == schema.ACTION_TYPE_COOK:
                hunger_score += 4.0 * hunger
            
                if hunger >= 0.65:
                    hunger_score += 1.0
            
                if fatigue > 0.65:
                    hunger_score -= 1.5 * (fatigue - 0.65)
            
            if action_type == ACTION_TYPE_EMERGENCY_EAT:
                if hunger < 0.85:
                    hunger_score += -999.0
                else:
                    hunger_score += 2.0 * hunger
            
                    if fatigue > 0.75:
                        hunger_score += 1.5 * (fatigue - 0.75)
            
            if action_type == ACTION_TYPE_MAKE_HOT_DRINK:
                hunger_score += 0.35
                hunger_score += 1.0 * sickness
                hunger_score += 0.03 * thermal_discomfort
            
                if hunger > 0.65:
                    hunger_score -= 1.0
            
                if fatigue > 0.75:
                    hunger_score -= 1.0
            # -----------------------------------------------------------------
            # Fatigue / sleep score.
            # -----------------------------------------------------------------

            fatigue_score = 0.0

            if action_type == schema.ACTION_TYPE_SLEEP:
                fatigue_score += 6.0 * (
                    0.50 * sleep_pressure
                    + 0.35 * fatigue
                    + 0.15 * sickness
                )
                fatigue_score -= 4.0 * work_pressure

                if is_sleeping_now:
                    fatigue_score += 2.0

            elif action_type == schema.ACTION_TYPE_WAKE_UP:
                if is_sleeping_now:
                    wake_need = (
                        0.45 * (1.0 - sleep_pressure)
                        + 0.35 * (1.0 - fatigue)
                        + 0.20 * work_pressure
                    )
                    fatigue_score += 4.0 * wake_need
                else:
                    fatigue_score -= 999.0

            elif (
                action_type == schema.ACTION_TYPE_IDLE
                or action_type == ACTION_TYPE_DO_NOTHING
            ):
                fatigue_score += 0.5 * fatigue

            # -----------------------------------------------------------------
            # Thermal score.
            # -----------------------------------------------------------------

            thermal_score = 0.0

            thermal_factor = thermal_discomfort
            if thermal_factor < 0.25:
                thermal_factor = 0.25

            cold_scaled = cold_pressure * thermal_factor
            heat_scaled = heat_pressure * thermal_factor

            if action_type == schema.ACTION_TYPE_TURN_HEATING_ON:
                thermal_score += 5.0 * cold_scaled
                if window_open:
                    thermal_score -= 4.0

            elif action_type == schema.ACTION_TYPE_TURN_HEATING_OFF:
                thermal_score += 5.0 * heat_scaled
                thermal_score -= 2.0 * cold_scaled

            elif action_type == schema.ACTION_TYPE_TURN_COOLING_ON:
                thermal_score += 5.0 * heat_scaled

            elif action_type == schema.ACTION_TYPE_TURN_COOLING_OFF:
                thermal_score += 5.0 * cold_scaled
                thermal_score -= 2.0 * heat_scaled

            elif action_type == schema.ACTION_TYPE_OPEN_WINDOW:
                thermal_score += 5.0 * heat_scaled
                thermal_score -= 4.0 * cold_scaled

            elif action_type == schema.ACTION_TYPE_CLOSE_WINDOW:
                thermal_score += 4.0 * cold_scaled

            # -----------------------------------------------------------------
            # Air-quality score.
            # -----------------------------------------------------------------

            air_score = 0.0

            air_combined = air_pressure
            if air_discomfort > air_combined:
                air_combined = air_discomfort

            if action_type == schema.ACTION_TYPE_OPEN_WINDOW:
                air_score += 5.0 * air_combined

            elif action_type == schema.ACTION_TYPE_CLOSE_WINDOW:
                air_score -= 3.0 * air_combined

            elif action_type == schema.ACTION_TYPE_TURN_VENTILATION_ON:
                air_score += 5.0 * air_combined

            elif action_type == schema.ACTION_TYPE_TURN_VENTILATION_OFF:
                remaining = 1.0 - air_combined
                if remaining < 0.0:
                    remaining = 0.0
                air_score += 5.0 * remaining

            # -----------------------------------------------------------------
            # Visual score.
            # -----------------------------------------------------------------

            visual_score = 0.0

            visual_combined = visual_pressure
            if visual_discomfort > visual_combined:
                visual_combined = visual_discomfort

            if (
                action_type == schema.ACTION_TYPE_TURN_LIGHT_ON
                or action_type == ACTION_TYPE_TURN_LIGHTS_ON
            ):
                visual_score += 4.0 * visual_combined

            elif (
                action_type == schema.ACTION_TYPE_TURN_LIGHT_OFF
                or action_type == ACTION_TYPE_TURN_LIGHTS_OFF
            ):
                remaining = 1.0 - visual_combined
                if remaining < 0.0:
                    remaining = 0.0
                visual_score += 4.0 * remaining

            elif (
                action_type == schema.ACTION_TYPE_OPEN_BLINDS
                or action_type == ACTION_TYPE_OPEN_CURTAIN
            ):
                visual_score += 2.0 * visual_combined

            elif (
                action_type == schema.ACTION_TYPE_CLOSE_BLINDS
                or action_type == ACTION_TYPE_CLOSE_CURTAIN
            ):
                remaining = 1.0 - visual_combined
                if remaining < 0.0:
                    remaining = 0.0
                visual_score += 2.0 * remaining

            # -----------------------------------------------------------------
            # Acoustic score.
            # -----------------------------------------------------------------

            acoustic_score = 0.0

            acoustic_combined = acoustic_pressure
            if acoustic_discomfort > acoustic_combined:
                acoustic_combined = acoustic_discomfort

            if action_type == schema.ACTION_TYPE_CLOSE_WINDOW:
                acoustic_score += 3.0 * acoustic_combined

            elif action_type == schema.ACTION_TYPE_OPEN_WINDOW:
                acoustic_score -= 3.0 * acoustic_combined

            # -----------------------------------------------------------------
            # Laundry score.
            # -----------------------------------------------------------------

            laundry_score = 0.0

            if (
                action_type == schema.ACTION_TYPE_DO_LAUNDRY
                or action_type == ACTION_TYPE_RUN_WASHING_MACHINE
            ):
                laundry_score += 4.0 * dirty

                if action_dirty_effect < 0.0:
                    laundry_score += abs(action_dirty_effect) * dirty

            # -----------------------------------------------------------------
            # Tariff score.
            # -----------------------------------------------------------------

            tariff_score = -0.001 * electricity_tariff * action_power_w

            # -----------------------------------------------------------------
            # Friction score.
            # -----------------------------------------------------------------

            power_effort_proxy = 0.0

            if action_duration_min > 30.0:
                power_effort_proxy = action_duration_min / 240.0
                if power_effort_proxy > 1.0:
                    power_effort_proxy = 1.0

            laziness_positive = laziness
            if laziness_positive < 0.0:
                laziness_positive = 0.0

            person_friction_positive = person_friction
            if person_friction_positive < 0.0:
                person_friction_positive = 0.0

            friction_score = -(
                (action_friction + power_effort_proxy)
                * laziness_positive
                * person_friction_positive
            )

            # -----------------------------------------------------------------
            # Work/travel score.
            # -----------------------------------------------------------------

            work_score = 0.0

            if (
                action_type == schema.ACTION_TYPE_LEAVE_HOME
                or action_type == ACTION_TYPE_GO_TO_WORK
                or action_type == ACTION_TYPE_GO_TO_SCHOOL
            ):
                work_score += 10.0 * work_pressure
                work_score -= 3.0 * sickness
                work_score -= 2.0 * fatigue

            elif action_type == schema.ACTION_TYPE_RETURN_HOME:
                remaining_work = 1.0 - work_pressure
                if remaining_work < 0.0:
                    remaining_work = 0.0

                work_score += 8.0 * remaining_work
                work_score += 0.5 * fatigue
                work_score += 0.8 * sickness

            # -----------------------------------------------------------------
            # Background score.
            # -----------------------------------------------------------------

            background_score = 0.0
            if is_background:
                background_score = 0.2

            total = (
                hunger_score
                + fatigue_score
                + thermal_score
                + air_score
                + visual_score
                + acoustic_score
                + laundry_score
                + tariff_score
                + friction_score
                + work_score
                + background_score
            )

            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_HUNGER,
            ] = hunger_score
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_FATIGUE,
            ] = fatigue_score
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_THERMAL,
            ] = thermal_score
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_AIR_QUALITY,
            ] = air_score
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_VISUAL,
            ] = visual_score
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_ACOUSTIC,
            ] = acoustic_score
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_LAUNDRY,
            ] = laundry_score
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_TARIFF,
            ] = tariff_score
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_FRICTION,
            ] = friction_score
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_IMPOSSIBLE_MASK,
            ] = 0.0
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_TOTAL,
            ] = total

    return action_scores

def score_all_person_actions_reference(
    person_state,
    person_static,
    zone_state,
    zone_static,
    system_state,
    system_static,
    process_state,
    action_static,
    action_scores,
    schedule_array,
    time_state,
    sleep_pressure_scores=None,
    electricity_tariff=0.25,
    impossible_score=IMPOSSIBLE_SCORE,
):
    """
    Fill action_scores for all person/action pairs.

    Writes:
        ACTION_SCORE_TOTAL
        ACTION_SCORE_HUNGER
        ACTION_SCORE_FATIGUE
        ACTION_SCORE_THERMAL
        ACTION_SCORE_AIR_QUALITY
        ACTION_SCORE_VISUAL
        ACTION_SCORE_ACOUSTIC
        ACTION_SCORE_LAUNDRY
        ACTION_SCORE_TARIFF
        ACTION_SCORE_FRICTION
        ACTION_SCORE_IMPOSSIBLE_MASK
    """
    n_persons = person_state.shape[0]
    n_actions = action_static.shape[0]

    if sleep_pressure_scores is None:
        sleep_pressure_scores = compute_sleep_pressure_scores(
            person_state=person_state,
            person_static=person_static,
            schedule_array=schedule_array,
            time_state=time_state,
        )

    reset_action_scores(action_scores)

    for person_i in range(n_persons):
        for action_i in range(n_actions):
            impossible = action_impossible_for_person(
                person_state=person_state,
                person_static=person_static,
                zone_state=zone_state,
                zone_static=zone_static,
                system_state=system_state,
                system_static=system_static,
                process_state=process_state,
                action_static=action_static,
                schedule_array=schedule_array,
                time_state=time_state,
                person_i=person_i,
                action_i=action_i,
            )

            if impossible:
                action_scores[
                    person_i,
                    action_i,
                    schema.ACTION_SCORE_IMPOSSIBLE_MASK,
                ] = 1.0
                action_scores[
                    person_i,
                    action_i,
                    schema.ACTION_SCORE_TOTAL,
                ] = impossible_score
                continue

            hunger_score = score_hunger_component(
                person_state=person_state,
                action_static=action_static,
                person_i=person_i,
                action_i=action_i,
            )

            fatigue_score = score_fatigue_sleep_component(
                person_state=person_state,
                action_static=action_static,
                sleep_pressure_scores=sleep_pressure_scores,
                schedule_array=schedule_array,
                time_state=time_state,
                person_i=person_i,
                action_i=action_i,
            )

            thermal_score = score_thermal_component(
                person_state=person_state,
                zone_state=zone_state,
                zone_static=zone_static,
                system_state=system_state,
                action_static=action_static,
                person_i=person_i,
                action_i=action_i,
            )

            air_score = score_air_quality_component(
                person_state=person_state,
                zone_state=zone_state,
                zone_static=zone_static,
                system_state=system_state,
                action_static=action_static,
                person_i=person_i,
                action_i=action_i,
            )

            visual_score = score_visual_component(
                person_state=person_state,
                zone_state=zone_state,
                zone_static=zone_static,
                system_state=system_state,
                action_static=action_static,
                person_i=person_i,
                action_i=action_i,
            )

            acoustic_score = score_acoustic_component(
                person_state=person_state,
                zone_state=zone_state,
                zone_static=zone_static,
                system_state=system_state,
                action_static=action_static,
                person_i=person_i,
                action_i=action_i,
            )

            laundry_score = score_laundry_component(
                person_state=person_state,
                action_static=action_static,
                person_i=person_i,
                action_i=action_i,
            )

            tariff_score = score_tariff_component(
                action_static=action_static,
                action_i=action_i,
                electricity_tariff=electricity_tariff,
            )

            friction_score = score_friction_component(
                person_state=person_state,
                person_static=person_static,
                action_static=action_static,
                person_i=person_i,
                action_i=action_i,
            )

            work_score = score_work_travel_component(
                person_state=person_state,
                person_static=person_static,
                action_static=action_static,
                schedule_array=schedule_array,
                time_state=time_state,
                person_i=person_i,
                action_i=action_i,
            )

            background_score = score_background_component(
                action_static=action_static,
                action_i=action_i,
            )

            total = (
                hunger_score
                + fatigue_score
                + thermal_score
                + air_score
                + visual_score
                + acoustic_score
                + laundry_score
                + tariff_score
                + friction_score
                + work_score
                + background_score
            )

            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_HUNGER,
            ] = hunger_score
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_FATIGUE,
            ] = fatigue_score
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_THERMAL,
            ] = thermal_score
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_AIR_QUALITY,
            ] = air_score
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_VISUAL,
            ] = visual_score
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_ACOUSTIC,
            ] = acoustic_score
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_LAUNDRY,
            ] = laundry_score
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_TARIFF,
            ] = tariff_score
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_FRICTION,
            ] = friction_score
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_IMPOSSIBLE_MASK,
            ] = 0.0
            action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_TOTAL,
            ] = total

    return action_scores


def choose_best_actions_from_scores(action_scores, action_static):
    """
    Deterministically select best action row for each person.

    Returns:
        chosen_action_ids[n_persons]

    Values are ACTION_IDs, not action array positions. In normal encoder output,
    these are the same as row indices, but keeping ACTION_ID is cleaner.
    """
    n_persons = action_scores.shape[0]
    chosen = np.zeros((n_persons,), dtype=np.int64)

    for person_i in range(n_persons):
        best_action_i = 0
        best_score = action_scores[
            person_i,
            0,
            schema.ACTION_SCORE_TOTAL,
        ]

        for action_i in range(1, action_scores.shape[1]):
            score = action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_TOTAL,
            ]

            if score > best_score:
                best_score = score
                best_action_i = action_i

        chosen[person_i] = int(action_static[best_action_i, schema.ACTION_ID])

    return chosen


def choose_best_action_indices_from_scores(action_scores):
    """
    Return best action row index for each person.

    This is useful when immediately indexing action_static.
    """
    n_persons = action_scores.shape[0]
    chosen = np.zeros((n_persons,), dtype=np.int64)

    for person_i in range(n_persons):
        best_action_i = 0
        best_score = action_scores[
            person_i,
            0,
            schema.ACTION_SCORE_TOTAL,
        ]

        for action_i in range(1, action_scores.shape[1]):
            score = action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_TOTAL,
            ]

            if score > best_score:
                best_score = score
                best_action_i = action_i

        chosen[person_i] = best_action_i

    return chosen

# =============================================================================
# Numba-prep in-place choice helpers
# =============================================================================

def choose_best_action_indices_from_scores_inplace(
    action_scores,
    chosen_action_indices,
):
    """
    In-place version of choose_best_action_indices_from_scores(...).

    Avoids allocating chosen array inside the kernel.
    """
    n_persons = action_scores.shape[0]
    n_actions = action_scores.shape[1]

    for person_i in range(n_persons):
        best_action_i = 0
        best_score = action_scores[
            person_i,
            0,
            schema.ACTION_SCORE_TOTAL,
        ]

        for action_i in range(1, n_actions):
            score = action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_TOTAL,
            ]

            if score > best_score:
                best_score = score
                best_action_i = action_i

        chosen_action_indices[person_i] = best_action_i

    return True


def choose_best_actions_from_scores_inplace(
    action_scores,
    action_static,
    chosen_action_ids,
):
    """
    In-place version of choose_best_actions_from_scores(...).

    Writes ACTION_IDs into chosen_action_ids.
    """
    n_persons = action_scores.shape[0]
    n_actions = action_scores.shape[1]

    for person_i in range(n_persons):
        best_action_i = 0
        best_score = action_scores[
            person_i,
            0,
            schema.ACTION_SCORE_TOTAL,
        ]

        for action_i in range(1, n_actions):
            score = action_scores[
                person_i,
                action_i,
                schema.ACTION_SCORE_TOTAL,
            ]

            if score > best_score:
                best_score = score
                best_action_i = action_i

        chosen_action_ids[person_i] = int(
            action_static[best_action_i, schema.ACTION_ID]
        )

    return True


def score_and_choose_actions(
    person_state,
    person_static,
    zone_state,
    zone_static,
    system_state,
    system_static,
    process_state,
    action_static,
    action_scores,
    schedule_array,
    time_state,
    sleep_pressure_scores=None,
    electricity_tariff=0.25,
):
    """
    Convenience wrapper:
        1. score all actions
        2. choose best action indices
        3. choose best action IDs
    """
    score_all_person_actions(
        person_state=person_state,
        person_static=person_static,
        zone_state=zone_state,
        zone_static=zone_static,
        system_state=system_state,
        system_static=system_static,
        process_state=process_state,
        action_static=action_static,
        action_scores=action_scores,
        schedule_array=schedule_array,
        time_state=time_state,
        sleep_pressure_scores=sleep_pressure_scores,
        electricity_tariff=electricity_tariff,
    )

    chosen_action_indices = choose_best_action_indices_from_scores(
        action_scores=action_scores,
    )

    chosen_action_ids = choose_best_actions_from_scores(
        action_scores=action_scores,
        action_static=action_static,
    )

    return chosen_action_indices, chosen_action_ids


def write_chosen_action_preview_to_person_state(
    person_state,
    action_static,
    chosen_action_indices,
):
    """
    Optional helper.

    This writes the selected action into person_state, but does not execute it.
    Real starting/advancing of actions belongs to Phase 9.

    Writes:
        PERSON_CURRENT_ACTION_TYPE
        PERSON_CURRENT_ACTION_ID
        PERSON_ACTION_TARGET_ZONE_ID
        PERSON_ACTION_TARGET_SYSTEM_ID
        PERSON_ACTION_TIME_LEFT_MIN
    """
    n_persons = person_state.shape[0]

    for person_i in range(n_persons):
        action_i = int(chosen_action_indices[person_i])

        person_state[person_i, schema.PERSON_CURRENT_ACTION_TYPE] = action_static[
            action_i,
            schema.ACTION_TYPE,
        ]
        person_state[person_i, schema.PERSON_CURRENT_ACTION_ID] = action_static[
            action_i,
            schema.ACTION_ID,
        ]
        person_state[person_i, schema.PERSON_ACTION_TARGET_ZONE_ID] = action_static[
            action_i,
            schema.ACTION_DEFAULT_TARGET_ZONE_ID,
        ]
        person_state[person_i, schema.PERSON_ACTION_TARGET_SYSTEM_ID] = action_static[
            action_i,
            schema.ACTION_DEFAULT_TARGET_SYSTEM_ID,
        ]
        person_state[person_i, schema.PERSON_ACTION_TIME_LEFT_MIN] = action_static[
            action_i,
            schema.ACTION_DURATION_MIN,
        ]

    return person_state