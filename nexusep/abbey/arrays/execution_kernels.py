"""
ABBEY array execution kernels.

Purpose:
    Convert selected numeric actions into numeric execution state.

Foreground actions:
    Stored directly on person_state:
        PERSON_CURRENT_ACTION_TYPE
        PERSON_CURRENT_ACTION_ID
        PERSON_ACTION_TARGET_ZONE_ID
        PERSON_ACTION_TARGET_SYSTEM_ID
        PERSON_ACTION_TIME_LEFT_MIN

Background actions/processes:
    Stored in process_state:
        PROCESS_TYPE
        PROCESS_STATE
        PROCESS_PERSON_ID
        PROCESS_DWELLING_ID
        PROCESS_ZONE_ID
        PROCESS_SYSTEM_ID
        PROCESS_TIME_LEFT_MIN
        PROCESS_POWER_W
        PROCESS_HEAT_GAIN_W
        PROCESS_CO2_GAIN_KG_S
        PROCESS_MOISTURE_GAIN_KG_S

Important:
    - No Action objects.
    - No ActionState objects.
    - No Python lists of active actions.
    - No dicts in timestep-facing functions.
    - Background processes can continue while person is away.
"""

import numpy as np

from nexusep.abbey.arrays import schema


# =============================================================================
# Small helpers
# =============================================================================

def clamp01(x):
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def is_missing_id(value):
    return int(value) == schema.MISSING_ID


def get_action_row_from_action_id(action_static, action_id):
    """
    Find action_static row from ACTION_ID.

    In current encoder output, action_id usually equals the row index, but this
    helper avoids depending on that.
    """
    action_id = int(action_id)

    if action_id == schema.MISSING_ID:
        return schema.MISSING_ID

    for i in range(action_static.shape[0]):
        if int(action_static[i, schema.ACTION_ID]) == action_id:
            return i

    return schema.MISSING_ID


def person_foreground_active(person_state, person_i):
    action_id = int(person_state[person_i, schema.PERSON_CURRENT_ACTION_ID])
    time_left = person_state[person_i, schema.PERSON_ACTION_TIME_LEFT_MIN]

    return action_id != schema.MISSING_ID and time_left > 0.0


def clear_person_foreground_action(person_state, person_i):
    """
    Clear foreground action fields.
    """
    person_state[person_i, schema.PERSON_CURRENT_ACTION_TYPE] = schema.ACTION_TYPE_NONE
    person_state[person_i, schema.PERSON_CURRENT_ACTION_ID] = schema.MISSING_ID
    person_state[person_i, schema.PERSON_ACTION_TARGET_ZONE_ID] = schema.MISSING_ID
    person_state[person_i, schema.PERSON_ACTION_TARGET_SYSTEM_ID] = schema.MISSING_ID
    person_state[person_i, schema.PERSON_ACTION_TIME_LEFT_MIN] = 0.0

    return person_state


def get_action_target_zone_id(action_static, person_state, person_i, action_i):
    action_type = int(action_static[action_i, schema.ACTION_TYPE])
    
    target_zone_id = int(action_static[action_i, schema.ACTION_DEFAULT_TARGET_ZONE_ID])
    
    if action_type == schema.ACTION_TYPE_SLEEP:
        target_zone_id = int(person_state[person_i, schema.PERSON_STATIC_SLEEP_ZONE_ID])

    if target_zone_id != schema.MISSING_ID:
        return target_zone_id

    return int(person_state[person_i, schema.PERSON_CURRENT_ZONE_ID])


def find_first_system_for_zone(system_state, zone_id):
    if zone_id == schema.MISSING_ID:
        return schema.MISSING_ID

    for i in range(system_state.shape[0]):
        if int(system_state[i, schema.SYSTEM_ZONE_ID]) == int(zone_id):
            return i

    return schema.MISSING_ID


def get_action_target_system_id(action_static, system_state, zone_id, action_i):
    target_system_id = int(
        action_static[action_i, schema.ACTION_DEFAULT_TARGET_SYSTEM_ID]
    )

    if target_system_id != schema.MISSING_ID:
        return target_system_id

    return find_first_system_for_zone(system_state, zone_id)


def find_free_process_slot(process_state):
    for i in range(process_state.shape[0]):
        process_status = int(process_state[i, schema.PROCESS_STATE])

        if process_status == schema.PROCESS_STATE_INACTIVE:
            return i

        if process_status == schema.PROCESS_STATE_FINISHED:
            return i

    return schema.MISSING_ID


def action_type_to_process_type(action_type, appliance_type):
    """
    Convert action/appliance info to a process type.
    """
    action_type = int(action_type)
    appliance_type = int(appliance_type)

    if appliance_type == schema.APPLIANCE_TYPE_WASHING_MACHINE:
        return schema.PROCESS_TYPE_WASHING_MACHINE

    if appliance_type == schema.APPLIANCE_TYPE_DISHWASHER:
        return schema.PROCESS_TYPE_DISHWASHER

    if appliance_type == schema.APPLIANCE_TYPE_OVEN:
        return schema.PROCESS_TYPE_OVEN

    if appliance_type == schema.APPLIANCE_TYPE_STOVE:
        return schema.PROCESS_TYPE_STOVE

    if appliance_type == schema.APPLIANCE_TYPE_SHOWER:
        return schema.PROCESS_TYPE_SHOWER

    if appliance_type == schema.APPLIANCE_TYPE_COFFEE_MACHINE:
        return schema.PROCESS_TYPE_COFFEE_MACHINE

    if action_type == schema.ACTION_TYPE_COOK:
        return schema.PROCESS_TYPE_COOKING

    if action_type == schema.ACTION_TYPE_SHOWER:
        return schema.PROCESS_TYPE_SHOWER

    if action_type == schema.ACTION_TYPE_MAKE_COFFEE:
        return schema.PROCESS_TYPE_COFFEE_MACHINE

    return schema.PROCESS_TYPE_NONE


def same_background_process_running(process_state, process_type, person_id):
    """
    Prevent duplicate active process for the same person/process type.
    """
    for i in range(process_state.shape[0]):
        if int(process_state[i, schema.PROCESS_STATE]) != schema.PROCESS_STATE_ACTIVE:
            continue

        if int(process_state[i, schema.PROCESS_TYPE]) != int(process_type):
            continue

        if int(process_state[i, schema.PROCESS_PERSON_ID]) != int(person_id):
            continue

        return True

    return False


# =============================================================================
# Reset execution outputs
# =============================================================================

def reset_execution_outputs(
    person_state,
    zone_state,
    dwelling_state,
    building_state,
    internal_gains=None,
):
    """
    Reset per-timestep execution outputs.

    This does not erase environmental state.
    It only clears current power/gain accumulators.
    """
    person_state[:, schema.PERSON_CURRENT_POWER_W] = 0.0
    person_state[:, schema.PERSON_CURRENT_HEAT_GAIN_W] = 0.0
    person_state[:, schema.PERSON_CURRENT_CO2_GAIN_KG_S] = 0.0
    person_state[:, schema.PERSON_CURRENT_MOISTURE_GAIN_KG_S] = 0.0

    zone_state[:, schema.ZONE_INTERNAL_HEAT_GAIN_W] = 0.0
    zone_state[:, schema.ZONE_LIGHTING_GAIN_W] = 0.0
    zone_state[:, schema.ZONE_APPLIANCE_GAIN_W] = 0.0
    zone_state[:, schema.ZONE_CO2_GAIN_KG_S] = 0.0
    zone_state[:, schema.ZONE_MOISTURE_GAIN_KG_S] = 0.0

    dwelling_state[:, schema.DWELLING_TOTAL_POWER_W] = 0.0
    dwelling_state[:, schema.DWELLING_TOTAL_HEAT_GAIN_W] = 0.0
    dwelling_state[:, schema.DWELLING_TOTAL_CO2_GAIN_KG_S] = 0.0
    dwelling_state[:, schema.DWELLING_TOTAL_MOISTURE_GAIN_KG_S] = 0.0
    dwelling_state[:, schema.DWELLING_TOTAL_ELECTRICITY_DEMAND_W] = 0.0

    building_state[:, schema.BUILDING_TOTAL_POWER_W] = 0.0
    building_state[:, schema.BUILDING_TOTAL_ELECTRICITY_DEMAND_W] = 0.0

    if internal_gains is not None:
        internal_gains[:, :] = 0.0

        for zone_i in range(internal_gains.shape[0]):
            internal_gains[zone_i, schema.GAIN_ZONE_ID] = zone_i

    return True


# =============================================================================
# Gain aggregation
# =============================================================================

def add_execution_gains_to_zone_dwelling_building(
    zone_state,
    dwelling_state,
    building_state,
    internal_gains,
    zone_id,
    appliance_type,
    power_w,
    heat_gain_w,
    co2_gain_kg_s,
    moisture_gain_kg_s,
):
    """
    Add current action/process outputs to zone/dwelling/building arrays.
    """
    zone_id = int(zone_id)

    if zone_id == schema.MISSING_ID:
        return True

    dwelling_id = int(zone_state[zone_id, schema.ZONE_DWELLING_ID])
    building_id = int(zone_state[zone_id, schema.ZONE_BUILDING_ID])

    appliance_type = int(appliance_type)

    if appliance_type == schema.APPLIANCE_TYPE_LIGHTS:
        zone_state[zone_id, schema.ZONE_LIGHTING_GAIN_W] += heat_gain_w

        if internal_gains is not None:
            internal_gains[zone_id, schema.GAIN_LIGHTING_HEAT_W] += heat_gain_w
    else:
        zone_state[zone_id, schema.ZONE_APPLIANCE_GAIN_W] += heat_gain_w

        if internal_gains is not None:
            internal_gains[zone_id, schema.GAIN_APPLIANCE_HEAT_W] += heat_gain_w

    zone_state[zone_id, schema.ZONE_INTERNAL_HEAT_GAIN_W] += heat_gain_w
    zone_state[zone_id, schema.ZONE_CO2_GAIN_KG_S] += co2_gain_kg_s
    zone_state[zone_id, schema.ZONE_MOISTURE_GAIN_KG_S] += moisture_gain_kg_s

    if internal_gains is not None:
        internal_gains[zone_id, schema.GAIN_TOTAL_HEAT_W] += heat_gain_w
        internal_gains[zone_id, schema.GAIN_CO2_KG_S] += co2_gain_kg_s
        internal_gains[zone_id, schema.GAIN_MOISTURE_KG_S] += moisture_gain_kg_s
        internal_gains[zone_id, schema.GAIN_ELECTRIC_POWER_W] += power_w

    if dwelling_id != schema.MISSING_ID:
        dwelling_state[dwelling_id, schema.DWELLING_TOTAL_POWER_W] += power_w
        dwelling_state[dwelling_id, schema.DWELLING_TOTAL_HEAT_GAIN_W] += heat_gain_w
        dwelling_state[dwelling_id, schema.DWELLING_TOTAL_CO2_GAIN_KG_S] += co2_gain_kg_s
        dwelling_state[dwelling_id, schema.DWELLING_TOTAL_MOISTURE_GAIN_KG_S] += moisture_gain_kg_s
        dwelling_state[dwelling_id, schema.DWELLING_TOTAL_ELECTRICITY_DEMAND_W] += power_w

    if building_id != schema.MISSING_ID:
        building_state[building_id, schema.BUILDING_TOTAL_POWER_W] += power_w
        building_state[building_id, schema.BUILDING_TOTAL_ELECTRICITY_DEMAND_W] += power_w

    return True


def add_execution_gains_to_person(
    person_state,
    person_i,
    power_w,
    heat_gain_w,
    co2_gain_kg_s,
    moisture_gain_kg_s,
):
    person_state[person_i, schema.PERSON_CURRENT_POWER_W] += power_w
    person_state[person_i, schema.PERSON_CURRENT_HEAT_GAIN_W] += heat_gain_w
    person_state[person_i, schema.PERSON_CURRENT_CO2_GAIN_KG_S] += co2_gain_kg_s
    person_state[person_i, schema.PERSON_CURRENT_MOISTURE_GAIN_KG_S] += moisture_gain_kg_s

    return True


# =============================================================================
# System effects
# =============================================================================

def apply_action_system_effects(
    system_state,
    system_static,
    action_static,
    action_i,
    target_system_id,
):
    """
    Apply immediate control/system effects from one action.

    This is the numeric replacement for action.system_effects.
    """
    if target_system_id == schema.MISSING_ID:
        return True

    action_type = int(action_static[action_i, schema.ACTION_TYPE])

    if action_type == schema.ACTION_TYPE_OPEN_WINDOW:
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_WINDOW] > 0.0:
            system_state[target_system_id, schema.SYSTEM_WINDOW_STATE] = schema.WINDOW_STATE_OPEN
            system_state[target_system_id, schema.SYSTEM_WINDOW_OPEN_FRACTION] = 1.0

    elif action_type == schema.ACTION_TYPE_CLOSE_WINDOW:
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_WINDOW] > 0.0:
            system_state[target_system_id, schema.SYSTEM_WINDOW_STATE] = schema.WINDOW_STATE_CLOSED
            system_state[target_system_id, schema.SYSTEM_WINDOW_OPEN_FRACTION] = 0.0

    elif action_type == schema.ACTION_TYPE_TURN_LIGHT_ON:
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_LIGHTS] > 0.0:
            system_state[target_system_id, schema.SYSTEM_LIGHT_STATE] = schema.LIGHT_STATE_ON
            system_state[target_system_id, schema.SYSTEM_LIGHTING_POWER_W] = system_static[
                target_system_id,
                schema.SYSTEM_STATIC_MAX_LIGHTING_POWER_W,
            ]

    elif action_type == schema.ACTION_TYPE_TURN_LIGHT_OFF:
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_LIGHTS] > 0.0:
            system_state[target_system_id, schema.SYSTEM_LIGHT_STATE] = schema.LIGHT_STATE_OFF
            system_state[target_system_id, schema.SYSTEM_LIGHTING_POWER_W] = 0.0

    elif action_type == schema.ACTION_TYPE_TURN_HEATING_ON:
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_HEATING] > 0.0:
            system_state[target_system_id, schema.SYSTEM_HVAC_MODE] = schema.HVAC_MODE_HEATING
            system_state[target_system_id, schema.SYSTEM_HEATING_POWER_W] = system_static[
                target_system_id,
                schema.SYSTEM_STATIC_MAX_HEATING_POWER_W,
            ]

    elif action_type == schema.ACTION_TYPE_TURN_HEATING_OFF:
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_HEATING] > 0.0:
            if int(system_state[target_system_id, schema.SYSTEM_HVAC_MODE]) == schema.HVAC_MODE_HEATING:
                system_state[target_system_id, schema.SYSTEM_HVAC_MODE] = schema.HVAC_MODE_OFF
            system_state[target_system_id, schema.SYSTEM_HEATING_POWER_W] = 0.0

    elif action_type == schema.ACTION_TYPE_TURN_COOLING_ON:
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_COOLING] > 0.0:
            system_state[target_system_id, schema.SYSTEM_HVAC_MODE] = schema.HVAC_MODE_COOLING
            system_state[target_system_id, schema.SYSTEM_COOLING_POWER_W] = system_static[
                target_system_id,
                schema.SYSTEM_STATIC_MAX_COOLING_POWER_W,
            ]

    elif action_type == schema.ACTION_TYPE_TURN_COOLING_OFF:
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_COOLING] > 0.0:
            if int(system_state[target_system_id, schema.SYSTEM_HVAC_MODE]) == schema.HVAC_MODE_COOLING:
                system_state[target_system_id, schema.SYSTEM_HVAC_MODE] = schema.HVAC_MODE_OFF
            system_state[target_system_id, schema.SYSTEM_COOLING_POWER_W] = 0.0

    elif action_type == schema.ACTION_TYPE_OPEN_BLINDS:
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_BLINDS] > 0.0:
            system_state[target_system_id, schema.SYSTEM_BLIND_STATE] = schema.BLIND_STATE_OPEN
            system_state[target_system_id, schema.SYSTEM_BLIND_CLOSED_FRACTION] = 0.0

    elif action_type == schema.ACTION_TYPE_CLOSE_BLINDS:
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_BLINDS] > 0.0:
            system_state[target_system_id, schema.SYSTEM_BLIND_STATE] = schema.BLIND_STATE_CLOSED
            system_state[target_system_id, schema.SYSTEM_BLIND_CLOSED_FRACTION] = 1.0

    elif action_type == schema.ACTION_TYPE_TURN_VENTILATION_ON:
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_MECH_VENTILATION] > 0.0:
            system_state[target_system_id, schema.SYSTEM_VENTILATION_MODE] = schema.VENTILATION_MODE_MECHANICAL
            system_state[
                target_system_id,
                schema.SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S,
            ] = system_static[
                target_system_id,
                schema.SYSTEM_STATIC_MAX_MECH_VENT_FLOW_M3_S,
            ]

    elif action_type == schema.ACTION_TYPE_TURN_VENTILATION_OFF:
        if system_static[target_system_id, schema.SYSTEM_STATIC_HAS_MECH_VENTILATION] > 0.0:
            system_state[target_system_id, schema.SYSTEM_VENTILATION_MODE] = schema.VENTILATION_MODE_OFF
            system_state[
                target_system_id,
                schema.SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S,
            ] = 0.0

    return True


# =============================================================================
# Person start/finish effects
# =============================================================================

def apply_action_start_person_effects(
    person_state,
    person_static,
    action_static,
    person_i,
    action_i,
    target_zone_id,
):
    """
    Apply immediate person/location effects at action start.
    """
    action_type = int(action_static[action_i, schema.ACTION_TYPE])

    if action_type == schema.ACTION_TYPE_SLEEP:
        person_state[person_i, schema.PERSON_IS_HOME] = 1.0
        person_state[person_i, schema.PERSON_OCCUPANCY_STATE] = schema.OCCUPANCY_HOME_SLEEPING

        if target_zone_id != schema.MISSING_ID:
            person_state[person_i, schema.PERSON_PREVIOUS_ZONE_ID] = person_state[
                person_i,
                schema.PERSON_CURRENT_ZONE_ID,
            ]
            person_state[person_i, schema.PERSON_CURRENT_ZONE_ID] = target_zone_id

    elif action_type == schema.ACTION_TYPE_WAKE_UP:
        person_state[person_i, schema.PERSON_OCCUPANCY_STATE] = schema.OCCUPANCY_HOME_AWAKE

    elif action_type == schema.ACTION_TYPE_LEAVE_HOME:
        person_state[person_i, schema.PERSON_IS_HOME] = 0.0
        person_state[person_i, schema.PERSON_PREVIOUS_ZONE_ID] = person_state[
            person_i,
            schema.PERSON_CURRENT_ZONE_ID,
        ]
        person_state[person_i, schema.PERSON_CURRENT_ZONE_ID] = schema.MISSING_ID
        person_state[person_i, schema.PERSON_OCCUPANCY_STATE] = schema.OCCUPANCY_AWAY

    elif action_type == schema.ACTION_TYPE_RETURN_HOME:
        home_zone_id = int(person_static[person_i, schema.PERSON_STATIC_HOME_ZONE_ID])

        if target_zone_id != schema.MISSING_ID:
            home_zone_id = target_zone_id

        person_state[person_i, schema.PERSON_IS_HOME] = 1.0
        person_state[person_i, schema.PERSON_PREVIOUS_ZONE_ID] = schema.MISSING_ID
        person_state[person_i, schema.PERSON_CURRENT_ZONE_ID] = home_zone_id
        person_state[person_i, schema.PERSON_OCCUPANCY_STATE] = schema.OCCUPANCY_HOME_AWAKE

    elif action_type == schema.ACTION_TYPE_MOVE_ZONE:
        if target_zone_id != schema.MISSING_ID:
            person_state[person_i, schema.PERSON_PREVIOUS_ZONE_ID] = person_state[
                person_i,
                schema.PERSON_CURRENT_ZONE_ID,
            ]
            person_state[person_i, schema.PERSON_CURRENT_ZONE_ID] = target_zone_id

    return True


def apply_action_finish_person_effects(
    person_state,
    action_static,
    person_i,
    action_i,
):
    """
    Apply numerical person effects when an action finishes.

    Uses action_static effect columns:
        ACTION_HUNGER_EFFECT
        ACTION_FATIGUE_EFFECT
        ACTION_DIRTY_CLOTHES_EFFECT
        ACTION_COMFORT_EFFECT
    """
    hunger_effect = action_static[action_i, schema.ACTION_HUNGER_EFFECT]
    fatigue_effect = action_static[action_i, schema.ACTION_FATIGUE_EFFECT]
    dirty_effect = action_static[action_i, schema.ACTION_DIRTY_CLOTHES_EFFECT]
    comfort_effect = action_static[action_i, schema.ACTION_COMFORT_EFFECT]

    if hunger_effect != 0.0:
        person_state[person_i, schema.PERSON_HUNGER] = clamp01(
            person_state[person_i, schema.PERSON_HUNGER] + hunger_effect
        )

    if fatigue_effect != 0.0:
        person_state[person_i, schema.PERSON_FATIGUE] = clamp01(
            person_state[person_i, schema.PERSON_FATIGUE] + fatigue_effect
        )

    if dirty_effect != 0.0:
        person_state[person_i, schema.PERSON_DIRTY_CLOTHES] = clamp01(
            person_state[person_i, schema.PERSON_DIRTY_CLOTHES] + dirty_effect
        )

    if comfort_effect != 0.0:
        person_state[person_i, schema.PERSON_TOTAL_DISCOMFORT] = clamp01(
            person_state[person_i, schema.PERSON_TOTAL_DISCOMFORT] - comfort_effect
        )

    return True


# =============================================================================
# Start actions
# =============================================================================

def start_foreground_action_for_person(
    person_state,
    person_static,
    system_state,
    system_static,
    action_static,
    person_i,
    action_i,
):
    """
    Start one foreground action for one person.
    """
    action_type = int(action_static[action_i, schema.ACTION_TYPE])
    action_id = int(action_static[action_i, schema.ACTION_ID])

    # Wake-up and leave-home interrupt existing foreground action.
    if action_type in (
        schema.ACTION_TYPE_WAKE_UP,
        schema.ACTION_TYPE_LEAVE_HOME,
        schema.ACTION_TYPE_RETURN_HOME,
    ):
        clear_person_foreground_action(person_state, person_i)

    if person_foreground_active(person_state, person_i):
        return False

    target_zone_id = get_action_target_zone_id(
        action_static=action_static,
        person_state=person_state,
        person_i=person_i,
        action_i=action_i,
    )
    target_system_id = get_action_target_system_id(
        action_static=action_static,
        system_state=system_state,
        zone_id=target_zone_id,
        action_i=action_i,
    )

    person_state[person_i, schema.PERSON_CURRENT_ACTION_TYPE] = action_type
    person_state[person_i, schema.PERSON_CURRENT_ACTION_ID] = action_id
    person_state[person_i, schema.PERSON_ACTION_TARGET_ZONE_ID] = target_zone_id
    person_state[person_i, schema.PERSON_ACTION_TARGET_SYSTEM_ID] = target_system_id
    person_state[person_i, schema.PERSON_ACTION_TIME_LEFT_MIN] = action_static[
        action_i,
        schema.ACTION_DURATION_MIN,
    ]

    apply_action_start_person_effects(
        person_state=person_state,
        person_static=person_static,
        action_static=action_static,
        person_i=person_i,
        action_i=action_i,
        target_zone_id=target_zone_id,
    )

    apply_action_system_effects(
        system_state=system_state,
        system_static=system_static,
        action_static=action_static,
        action_i=action_i,
        target_system_id=target_system_id,
    )

    return True


def start_background_process_for_person(
    person_state,
    person_static,
    system_state,
    system_static,
    process_state,
    action_static,
    person_i,
    action_i,
):
    """
    Start one background process.

    Returns:
        process slot index, or MISSING_ID if no process was started.
    """
    action_type = int(action_static[action_i, schema.ACTION_TYPE])
    action_id = int(action_static[action_i, schema.ACTION_ID])
    appliance_type = int(action_static[action_i, schema.ACTION_DEFAULT_APPLIANCE_TYPE])
    process_type = action_type_to_process_type(action_type, appliance_type)

    person_id = int(person_state[person_i, schema.PERSON_ID])
    dwelling_id = int(person_state[person_i, schema.PERSON_DWELLING_ID])

    target_zone_id = get_action_target_zone_id(
        action_static=action_static,
        person_state=person_state,
        person_i=person_i,
        action_i=action_i,
    )
    target_system_id = get_action_target_system_id(
        action_static=action_static,
        system_state=system_state,
        zone_id=target_zone_id,
        action_i=action_i,
    )

    if same_background_process_running(
        process_state=process_state,
        process_type=process_type,
        person_id=person_id,
    ):
        return schema.MISSING_ID

    slot = find_free_process_slot(process_state)

    if slot == schema.MISSING_ID:
        return schema.MISSING_ID

    process_state[slot, schema.PROCESS_ID] = slot
    process_state[slot, schema.PROCESS_TYPE] = process_type
    process_state[slot, schema.PROCESS_STATE] = schema.PROCESS_STATE_ACTIVE

    process_state[slot, schema.PROCESS_PERSON_ID] = person_id
    process_state[slot, schema.PROCESS_DWELLING_ID] = dwelling_id
    process_state[slot, schema.PROCESS_ZONE_ID] = target_zone_id
    process_state[slot, schema.PROCESS_SYSTEM_ID] = target_system_id

    duration = action_static[action_i, schema.ACTION_DURATION_MIN]

    process_state[slot, schema.PROCESS_TIME_LEFT_MIN] = duration
    process_state[slot, schema.PROCESS_TOTAL_DURATION_MIN] = duration

    process_state[slot, schema.PROCESS_POWER_W] = action_static[action_i, schema.ACTION_POWER_W]
    process_state[slot, schema.PROCESS_HEAT_GAIN_W] = action_static[action_i, schema.ACTION_HEAT_GAIN_W]
    process_state[slot, schema.PROCESS_CO2_GAIN_KG_S] = action_static[action_i, schema.ACTION_CO2_GAIN_KG_S]
    process_state[slot, schema.PROCESS_MOISTURE_GAIN_KG_S] = action_static[action_i, schema.ACTION_MOISTURE_GAIN_KG_S]

    # Background actions apply their person-effect at start because process_state
    # does not store ACTION_ID. Example: laundry reduces dirty-clothes pressure.
    apply_action_finish_person_effects(
        person_state=person_state,
        action_static=action_static,
        person_i=person_i,
        action_i=action_i,
    )

    apply_action_system_effects(
        system_state=system_state,
        system_static=system_static,
        action_static=action_static,
        action_i=action_i,
        target_system_id=target_system_id,
    )

    return slot


def start_action_for_person(
    person_state,
    person_static,
    system_state,
    system_static,
    process_state,
    action_static,
    person_i,
    action_i,
):
    """
    Start selected action for one person.

    Background action:
        goes to process_state.

    Foreground action:
        goes to person_state current-action columns.
    """
    is_background = action_static[action_i, schema.ACTION_IS_BACKGROUND] > 0.0
    action_type = int(action_static[action_i, schema.ACTION_TYPE])

    if action_type == schema.ACTION_TYPE_SLEEP:
        sleep_zone_id = int(person_static[person_i, schema.PERSON_STATIC_SLEEP_ZONE_ID])
    
        if sleep_zone_id != schema.MISSING_ID:
            person_state[person_i, schema.PERSON_PREVIOUS_ZONE_ID] = person_state[
                person_i,
                schema.PERSON_CURRENT_ZONE_ID,
            ]
            person_state[person_i, schema.PERSON_CURRENT_ZONE_ID] = sleep_zone_id
            person_state[person_i, schema.PERSON_ACTION_TARGET_ZONE_ID] = sleep_zone_id
            person_state[person_i, schema.PERSON_IS_HOME] = 1.0
            person_state[person_i, schema.PERSON_OCCUPANCY_STATE] = schema.OCCUPANCY_HOME_SLEEPING
    if is_background:
        slot = start_background_process_for_person(
            person_state=person_state,
            person_static=person_static,
            system_state=system_state,
            system_static=system_static,
            process_state=process_state,
            action_static=action_static,
            person_i=person_i,
            action_i=action_i,
        )
        return slot != schema.MISSING_ID

    return start_foreground_action_for_person(
        person_state=person_state,
        person_static=person_static,
        system_state=system_state,
        system_static=system_static,
        action_static=action_static,
        person_i=person_i,
        action_i=action_i,
    )


def start_chosen_actions(
    person_state,
    person_static,
    system_state,
    system_static,
    process_state,
    action_static,
    chosen_action_indices,
):
    """
    Start one selected action per person.

    This function does not advance time.
    """
    n_persons = person_state.shape[0]
    started = np.zeros((n_persons,), dtype=np.float64)

    for person_i in range(n_persons):
        action_i = int(chosen_action_indices[person_i])

        if action_i < 0 or action_i >= action_static.shape[0]:
            started[person_i] = 0.0
            continue

        ok = start_action_for_person(
            person_state=person_state,
            person_static=person_static,
            system_state=system_state,
            system_static=system_static,
            process_state=process_state,
            action_static=action_static,
            person_i=person_i,
            action_i=action_i,
        )

        if ok:
            started[person_i] = 1.0
        else:
            started[person_i] = 0.0

    return started


# =============================================================================
# Advance foreground and background execution
# =============================================================================

def add_foreground_action_outputs(
    person_state,
    zone_state,
    dwelling_state,
    building_state,
    internal_gains,
    action_static,
    person_i,
    action_i,
    active_minutes,
    dt_minutes,
):
    """
    Add averaged foreground action power/gains for the current timestep.
    """
    if dt_minutes <= 0.0:
        return True

    factor = active_minutes / dt_minutes

    power_w = action_static[action_i, schema.ACTION_POWER_W] * factor
    heat_gain_w = action_static[action_i, schema.ACTION_HEAT_GAIN_W] * factor
    co2_gain = action_static[action_i, schema.ACTION_CO2_GAIN_KG_S] * factor
    moisture_gain = action_static[action_i, schema.ACTION_MOISTURE_GAIN_KG_S] * factor

    zone_id = int(person_state[person_i, schema.PERSON_ACTION_TARGET_ZONE_ID])
    appliance_type = int(action_static[action_i, schema.ACTION_DEFAULT_APPLIANCE_TYPE])

    add_execution_gains_to_person(
        person_state=person_state,
        person_i=person_i,
        power_w=power_w,
        heat_gain_w=heat_gain_w,
        co2_gain_kg_s=co2_gain,
        moisture_gain_kg_s=moisture_gain,
    )

    add_execution_gains_to_zone_dwelling_building(
        zone_state=zone_state,
        dwelling_state=dwelling_state,
        building_state=building_state,
        internal_gains=internal_gains,
        zone_id=zone_id,
        appliance_type=appliance_type,
        power_w=power_w,
        heat_gain_w=heat_gain_w,
        co2_gain_kg_s=co2_gain,
        moisture_gain_kg_s=moisture_gain,
    )

    return True


def advance_foreground_actions(
    person_state,
    zone_state,
    dwelling_state,
    building_state,
    internal_gains,
    action_static,
    dt_minutes,
):
    """
    Advance all foreground actions stored in person_state.
    """
    n_persons = person_state.shape[0]

    for person_i in range(n_persons):
        action_id = int(person_state[person_i, schema.PERSON_CURRENT_ACTION_ID])

        if action_id == schema.MISSING_ID:
            continue

        action_i = get_action_row_from_action_id(
            action_static=action_static,
            action_id=action_id,
        )

        if action_i == schema.MISSING_ID:
            clear_person_foreground_action(person_state, person_i)
            continue

        time_left = person_state[person_i, schema.PERSON_ACTION_TIME_LEFT_MIN]

        if time_left <= 0.0:
            apply_action_finish_person_effects(
                person_state=person_state,
                action_static=action_static,
                person_i=person_i,
                action_i=action_i,
            )
            clear_person_foreground_action(person_state, person_i)
            continue

        active_minutes = min(dt_minutes, time_left)

        add_foreground_action_outputs(
            person_state=person_state,
            zone_state=zone_state,
            dwelling_state=dwelling_state,
            building_state=building_state,
            internal_gains=internal_gains,
            action_static=action_static,
            person_i=person_i,
            action_i=action_i,
            active_minutes=active_minutes,
            dt_minutes=dt_minutes,
        )

        new_time_left = max(0.0, time_left - dt_minutes)
        person_state[person_i, schema.PERSON_ACTION_TIME_LEFT_MIN] = new_time_left

        if new_time_left <= 0.0:
            apply_action_finish_person_effects(
                person_state=person_state,
                action_static=action_static,
                person_i=person_i,
                action_i=action_i,
            )

            # If sleep finished, wake the person.
            if int(action_static[action_i, schema.ACTION_TYPE]) == schema.ACTION_TYPE_SLEEP:
                if person_state[person_i, schema.PERSON_IS_HOME] > 0.0:
                    person_state[person_i, schema.PERSON_OCCUPANCY_STATE] = schema.OCCUPANCY_HOME_AWAKE

            clear_person_foreground_action(person_state, person_i)

    return person_state


def clear_process_slot(process_state, process_i):
    process_state[process_i, schema.PROCESS_TYPE] = schema.PROCESS_TYPE_NONE
    process_state[process_i, schema.PROCESS_STATE] = schema.PROCESS_STATE_INACTIVE

    process_state[process_i, schema.PROCESS_PERSON_ID] = schema.MISSING_ID
    process_state[process_i, schema.PROCESS_DWELLING_ID] = schema.MISSING_ID
    process_state[process_i, schema.PROCESS_ZONE_ID] = schema.MISSING_ID
    process_state[process_i, schema.PROCESS_SYSTEM_ID] = schema.MISSING_ID

    process_state[process_i, schema.PROCESS_TIME_LEFT_MIN] = 0.0
    process_state[process_i, schema.PROCESS_TOTAL_DURATION_MIN] = 0.0

    process_state[process_i, schema.PROCESS_POWER_W] = 0.0
    process_state[process_i, schema.PROCESS_HEAT_GAIN_W] = 0.0
    process_state[process_i, schema.PROCESS_CO2_GAIN_KG_S] = 0.0
    process_state[process_i, schema.PROCESS_MOISTURE_GAIN_KG_S] = 0.0

    return process_state


def add_background_process_outputs(
    zone_state,
    dwelling_state,
    building_state,
    internal_gains,
    process_state,
    process_i,
    active_minutes,
    dt_minutes,
):
    """
    Add averaged background process outputs.
    """
    if dt_minutes <= 0.0:
        return True

    factor = active_minutes / dt_minutes

    process_type = int(process_state[process_i, schema.PROCESS_TYPE])
    zone_id = int(process_state[process_i, schema.PROCESS_ZONE_ID])

    power_w = process_state[process_i, schema.PROCESS_POWER_W] * factor
    heat_gain_w = process_state[process_i, schema.PROCESS_HEAT_GAIN_W] * factor
    co2_gain = process_state[process_i, schema.PROCESS_CO2_GAIN_KG_S] * factor
    moisture_gain = process_state[process_i, schema.PROCESS_MOISTURE_GAIN_KG_S] * factor

    appliance_type = schema.APPLIANCE_TYPE_NONE

    if process_type == schema.PROCESS_TYPE_WASHING_MACHINE:
        appliance_type = schema.APPLIANCE_TYPE_WASHING_MACHINE
    elif process_type == schema.PROCESS_TYPE_DISHWASHER:
        appliance_type = schema.APPLIANCE_TYPE_DISHWASHER
    elif process_type == schema.PROCESS_TYPE_OVEN:
        appliance_type = schema.APPLIANCE_TYPE_OVEN
    elif process_type == schema.PROCESS_TYPE_STOVE:
        appliance_type = schema.APPLIANCE_TYPE_STOVE
    elif process_type == schema.PROCESS_TYPE_SHOWER:
        appliance_type = schema.APPLIANCE_TYPE_SHOWER
    elif process_type == schema.PROCESS_TYPE_COFFEE_MACHINE:
        appliance_type = schema.APPLIANCE_TYPE_COFFEE_MACHINE

    add_execution_gains_to_zone_dwelling_building(
        zone_state=zone_state,
        dwelling_state=dwelling_state,
        building_state=building_state,
        internal_gains=internal_gains,
        zone_id=zone_id,
        appliance_type=appliance_type,
        power_w=power_w,
        heat_gain_w=heat_gain_w,
        co2_gain_kg_s=co2_gain,
        moisture_gain_kg_s=moisture_gain,
    )

    return True


def advance_background_processes(
    zone_state,
    dwelling_state,
    building_state,
    internal_gains,
    process_state,
    dt_minutes,
):
    """
    Advance all active background processes.

    Background processes continue even if the actor is away.
    """
    for process_i in range(process_state.shape[0]):
        if int(process_state[process_i, schema.PROCESS_STATE]) != schema.PROCESS_STATE_ACTIVE:
            continue

        time_left = process_state[process_i, schema.PROCESS_TIME_LEFT_MIN]

        if time_left <= 0.0:
            clear_process_slot(process_state, process_i)
            continue

        active_minutes = min(dt_minutes, time_left)

        add_background_process_outputs(
            zone_state=zone_state,
            dwelling_state=dwelling_state,
            building_state=building_state,
            internal_gains=internal_gains,
            process_state=process_state,
            process_i=process_i,
            active_minutes=active_minutes,
            dt_minutes=dt_minutes,
        )

        new_time_left = max(0.0, time_left - dt_minutes)
        process_state[process_i, schema.PROCESS_TIME_LEFT_MIN] = new_time_left

        if new_time_left <= 0.0:
            clear_process_slot(process_state, process_i)

    return process_state


# =============================================================================
# Occupancy aggregation
# =============================================================================

def recompute_occupancy_after_execution(
    person_state,
    zone_state,
    dwelling_state,
    building_state,
):
    """
    Recompute occupancy counts after movement/home-away changes.
    """
    zone_state[:, schema.ZONE_OCCUPANT_COUNT] = 0.0
    zone_state[:, schema.ZONE_IS_OCCUPIED] = 0.0

    dwelling_state[:, schema.DWELLING_OCCUPANT_COUNT] = 0.0
    dwelling_state[:, schema.DWELLING_IS_OCCUPIED] = 0.0

    building_state[:, schema.BUILDING_OCCUPANT_COUNT] = 0.0
    building_state[:, schema.BUILDING_IS_OCCUPIED] = 0.0

    for person_i in range(person_state.shape[0]):
        if person_state[person_i, schema.PERSON_IS_HOME] <= 0.0:
            continue

        zone_id = int(person_state[person_i, schema.PERSON_CURRENT_ZONE_ID])
        dwelling_id = int(person_state[person_i, schema.PERSON_DWELLING_ID])

        if zone_id != schema.MISSING_ID:
            zone_state[zone_id, schema.ZONE_OCCUPANT_COUNT] += 1.0
            zone_state[zone_id, schema.ZONE_IS_OCCUPIED] = 1.0

        if dwelling_id != schema.MISSING_ID:
            dwelling_state[dwelling_id, schema.DWELLING_OCCUPANT_COUNT] += 1.0
            dwelling_state[dwelling_id, schema.DWELLING_IS_OCCUPIED] = 1.0

            building_id = int(dwelling_state[dwelling_id, schema.DWELLING_BUILDING_ID])

            if building_id != schema.MISSING_ID:
                building_state[building_id, schema.BUILDING_OCCUPANT_COUNT] += 1.0
                building_state[building_id, schema.BUILDING_IS_OCCUPIED] = 1.0

    return True


# =============================================================================
# Main execution step
# =============================================================================

def advance_execution_state_arrays(
    person_state,
    zone_state,
    dwelling_state,
    building_state,
    process_state,
    action_static,
    dt_minutes,
    internal_gains=None,
):
    """
    Advance already-active foreground and background actions by dt_minutes.

    This function:
        - clears current timestep outputs
        - applies active power/gains
        - decreases timers
        - finishes completed actions/processes
    """
    reset_execution_outputs(
        person_state=person_state,
        zone_state=zone_state,
        dwelling_state=dwelling_state,
        building_state=building_state,
        internal_gains=internal_gains,
    )

    advance_foreground_actions(
        person_state=person_state,
        zone_state=zone_state,
        dwelling_state=dwelling_state,
        building_state=building_state,
        internal_gains=internal_gains,
        action_static=action_static,
        dt_minutes=dt_minutes,
    )

    advance_background_processes(
        zone_state=zone_state,
        dwelling_state=dwelling_state,
        building_state=building_state,
        internal_gains=internal_gains,
        process_state=process_state,
        dt_minutes=dt_minutes,
    )

    recompute_occupancy_after_execution(
        person_state=person_state,
        zone_state=zone_state,
        dwelling_state=dwelling_state,
        building_state=building_state,
    )

    return person_state, zone_state, dwelling_state, building_state, process_state

# =============================================================================
# Numba-prep in-place execution helpers
# =============================================================================

def start_chosen_actions_inplace(
    person_state,
    person_static,
    system_state,
    system_static,
    process_state,
    action_static,
    chosen_action_indices,
    started_actions,
):
    """
    In-place version of start_chosen_actions(...).

    Avoids allocating started array inside the kernel.
    """
    n_persons = person_state.shape[0]

    for person_i in range(n_persons):
        action_i = int(chosen_action_indices[person_i])

        if action_i < 0 or action_i >= action_static.shape[0]:
            started_actions[person_i] = 0.0
            continue

        ok = start_action_for_person(
            person_state=person_state,
            person_static=person_static,
            system_state=system_state,
            system_static=system_static,
            process_state=process_state,
            action_static=action_static,
            person_i=person_i,
            action_i=action_i,
        )

        if ok:
            started_actions[person_i] = 1.0
        else:
            started_actions[person_i] = 0.0

    return True


def run_execution_step_from_chosen_actions_inplace(
    person_state,
    person_static,
    zone_state,
    dwelling_state,
    building_state,
    system_state,
    system_static,
    process_state,
    action_static,
    chosen_action_indices,
    started_actions,
    dt_minutes,
    internal_gains,
):
    """
    Numba-prep execution wrapper.

    Difference from run_execution_step_from_chosen_actions(...):
        - started_actions is required
        - internal_gains is required
        - no optional None
        - no internally allocated started array
    """
    start_chosen_actions_inplace(
        person_state=person_state,
        person_static=person_static,
        system_state=system_state,
        system_static=system_static,
        process_state=process_state,
        action_static=action_static,
        chosen_action_indices=chosen_action_indices,
        started_actions=started_actions,
    )

    advance_execution_state_arrays(
        person_state=person_state,
        zone_state=zone_state,
        dwelling_state=dwelling_state,
        building_state=building_state,
        process_state=process_state,
        action_static=action_static,
        dt_minutes=dt_minutes,
        internal_gains=internal_gains,
    )

    return True

def run_execution_step_from_chosen_actions(
    person_state,
    person_static,
    zone_state,
    dwelling_state,
    building_state,
    system_state,
    system_static,
    process_state,
    action_static,
    chosen_action_indices,
    dt_minutes,
    internal_gains=None,
):
    """
    Phase 9 convenience function.

    Order:
        1. start selected actions
        2. advance foreground/background execution by dt_minutes
        3. update current power/gain arrays

    This is intentionally one decision per timestep.
    The old object runner could split one timestep into multiple chunks and
    choose again after short actions. That richer loop belongs in Phase 12.
    """
    started = start_chosen_actions(
        person_state=person_state,
        person_static=person_static,
        system_state=system_state,
        system_static=system_static,
        process_state=process_state,
        action_static=action_static,
        chosen_action_indices=chosen_action_indices,
    )

    advance_execution_state_arrays(
        person_state=person_state,
        zone_state=zone_state,
        dwelling_state=dwelling_state,
        building_state=building_state,
        process_state=process_state,
        action_static=action_static,
        dt_minutes=dt_minutes,
        internal_gains=internal_gains,
    )

    return started