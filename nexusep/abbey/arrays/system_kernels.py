"""
ABBEY array system/control kernels.

Purpose:
    Keep windows, HVAC, lights, ventilation, and blinds/curtains numeric.

This module handles:
    - HVAC mode integers
    - heating/cooling setpoints
    - window state/fraction
    - light state/power
    - blind state/fraction
    - mechanical ventilation mode/flow
    - numeric control-action application
    - physical system constraints

Important:
    - No strings in core functions.
    - No ZoneControlState objects.
    - No ZoneControlCommand objects.
    - No dicts inside timestep-facing functions.
"""

import numpy as np

from nexusep.abbey.arrays import schema


# =============================================================================
# Availability mask columns
# =============================================================================

SYSTEM_MASK_HAS_HEATING = 0
SYSTEM_MASK_HAS_COOLING = 1
SYSTEM_MASK_HAS_WINDOW = 2
SYSTEM_MASK_HAS_LIGHTS = 3
SYSTEM_MASK_HAS_BLINDS = 4
SYSTEM_MASK_HAS_MECH_VENTILATION = 5
N_SYSTEM_AVAILABILITY_MASK_COLS = 6


# =============================================================================
# Small helpers
# =============================================================================

def clip(value, minimum, maximum):
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def clip01(value):
    return clip(value, 0.0, 1.0)


def is_missing_id(value):
    return int(value) == schema.MISSING_ID


def find_first_system_for_zone(system_state, zone_id):
    """
    Find first system row serving zone_id.
    """
    zone_id = int(zone_id)

    if zone_id == schema.MISSING_ID:
        return schema.MISSING_ID

    for i in range(system_state.shape[0]):
        if int(system_state[i, schema.SYSTEM_ZONE_ID]) == zone_id:
            return i

    return schema.MISSING_ID


def get_action_target_zone_id(action_static, person_state, person_i, action_i):
    target_zone_id = int(
        action_static[action_i, schema.ACTION_DEFAULT_TARGET_ZONE_ID]
    )

    if target_zone_id != schema.MISSING_ID:
        return target_zone_id

    return int(person_state[person_i, schema.PERSON_CURRENT_ZONE_ID])


def get_action_target_system_id(
    action_static,
    person_state,
    system_state,
    person_i,
    action_i,
):
    target_system_id = int(
        action_static[action_i, schema.ACTION_DEFAULT_TARGET_SYSTEM_ID]
    )

    if target_system_id != schema.MISSING_ID:
        return target_system_id

    target_zone_id = get_action_target_zone_id(
        action_static=action_static,
        person_state=person_state,
        person_i=person_i,
        action_i=action_i,
    )

    return find_first_system_for_zone(
        system_state=system_state,
        zone_id=target_zone_id,
    )


# =============================================================================
# Availability masks
# =============================================================================

def make_system_availability_masks(system_static):
    """
    Build compact numeric availability masks.

    Shape:
        [n_systems, 6]

    Columns:
        SYSTEM_MASK_HAS_HEATING
        SYSTEM_MASK_HAS_COOLING
        SYSTEM_MASK_HAS_WINDOW
        SYSTEM_MASK_HAS_LIGHTS
        SYSTEM_MASK_HAS_BLINDS
        SYSTEM_MASK_HAS_MECH_VENTILATION
    """
    n_systems = system_static.shape[0]
    masks = np.zeros(
        (n_systems, N_SYSTEM_AVAILABILITY_MASK_COLS),
        dtype=np.float64,
    )

    for i in range(n_systems):
        masks[i, SYSTEM_MASK_HAS_HEATING] = system_static[
            i,
            schema.SYSTEM_STATIC_HAS_HEATING,
        ]
        masks[i, SYSTEM_MASK_HAS_COOLING] = system_static[
            i,
            schema.SYSTEM_STATIC_HAS_COOLING,
        ]
        masks[i, SYSTEM_MASK_HAS_WINDOW] = system_static[
            i,
            schema.SYSTEM_STATIC_HAS_WINDOW,
        ]
        masks[i, SYSTEM_MASK_HAS_LIGHTS] = system_static[
            i,
            schema.SYSTEM_STATIC_HAS_LIGHTS,
        ]
        masks[i, SYSTEM_MASK_HAS_BLINDS] = system_static[
            i,
            schema.SYSTEM_STATIC_HAS_BLINDS,
        ]
        masks[i, SYSTEM_MASK_HAS_MECH_VENTILATION] = system_static[
            i,
            schema.SYSTEM_STATIC_HAS_MECH_VENTILATION,
        ]

    return masks


# =============================================================================
# Setpoint constraints
# =============================================================================

def enforce_setpoint_constraints_for_system(
    system_state,
    system_i,
    min_heating_setpoint_c=5.0,
    max_heating_setpoint_c=30.0,
    min_cooling_setpoint_c=10.0,
    max_cooling_setpoint_c=40.0,
    minimum_deadband_c=1.0,
):
    """
    Keep heating/cooling setpoints physically sane.
    """
    heating_setpoint = system_state[
        system_i,
        schema.SYSTEM_HEATING_SETPOINT_C,
    ]
    cooling_setpoint = system_state[
        system_i,
        schema.SYSTEM_COOLING_SETPOINT_C,
    ]

    heating_setpoint = clip(
        heating_setpoint,
        min_heating_setpoint_c,
        max_heating_setpoint_c,
    )
    cooling_setpoint = clip(
        cooling_setpoint,
        min_cooling_setpoint_c,
        max_cooling_setpoint_c,
    )

    if heating_setpoint + minimum_deadband_c >= cooling_setpoint:
        midpoint = 0.5 * (heating_setpoint + cooling_setpoint)
        heating_setpoint = midpoint - 0.5 * minimum_deadband_c
        cooling_setpoint = midpoint + 0.5 * minimum_deadband_c

        heating_setpoint = clip(
            heating_setpoint,
            min_heating_setpoint_c,
            max_heating_setpoint_c,
        )
        cooling_setpoint = clip(
            cooling_setpoint,
            min_cooling_setpoint_c,
            max_cooling_setpoint_c,
        )

    system_state[system_i, schema.SYSTEM_HEATING_SETPOINT_C] = heating_setpoint
    system_state[system_i, schema.SYSTEM_COOLING_SETPOINT_C] = cooling_setpoint

    return system_state


def enforce_all_setpoint_constraints(
    system_state,
    min_heating_setpoint_c=5.0,
    max_heating_setpoint_c=30.0,
    min_cooling_setpoint_c=10.0,
    max_cooling_setpoint_c=40.0,
    minimum_deadband_c=1.0,
):
    for system_i in range(system_state.shape[0]):
        enforce_setpoint_constraints_for_system(
            system_state=system_state,
            system_i=system_i,
            min_heating_setpoint_c=min_heating_setpoint_c,
            max_heating_setpoint_c=max_heating_setpoint_c,
            min_cooling_setpoint_c=min_cooling_setpoint_c,
            max_cooling_setpoint_c=max_cooling_setpoint_c,
            minimum_deadband_c=minimum_deadband_c,
        )

    return system_state


# =============================================================================
# HVAC power/mode logic
# =============================================================================

def update_hvac_power_for_system(
    system_state,
    system_static,
    zone_state,
    system_i,
    thermostat_deadband_c=0.5,
):
    """
    Convert HVAC mode and setpoints to heating/cooling powers.

    Mode behavior:
        OFF:
            heating = 0, cooling = 0

        HEATING:
            heating = max heating power if available

        COOLING:
            cooling = max cooling power if available

        AUTO:
            use zone temperature and setpoints

        VENTILATION_ONLY:
            no heating/cooling power
    """
    mode = int(system_state[system_i, schema.SYSTEM_HVAC_MODE])

    has_heating = system_static[system_i, schema.SYSTEM_STATIC_HAS_HEATING] > 0.0
    has_cooling = system_static[system_i, schema.SYSTEM_STATIC_HAS_COOLING] > 0.0

    max_heating_power = system_static[
        system_i,
        schema.SYSTEM_STATIC_MAX_HEATING_POWER_W,
    ]
    max_cooling_power = system_static[
        system_i,
        schema.SYSTEM_STATIC_MAX_COOLING_POWER_W,
    ]

    heating_power = 0.0
    cooling_power = 0.0

    if mode == schema.HVAC_MODE_HEATING:
        if has_heating:
            heating_power = max(0.0, max_heating_power)

    elif mode == schema.HVAC_MODE_COOLING:
        if has_cooling:
            cooling_power = max(0.0, max_cooling_power)

    elif mode == schema.HVAC_MODE_AUTO:
        zone_id = int(system_state[system_i, schema.SYSTEM_ZONE_ID])

        if zone_state is not None and zone_id != schema.MISSING_ID:
            zone_temp = zone_state[zone_id, schema.ZONE_AIR_TEMPERATURE_C]
            heating_setpoint = system_state[
                system_i,
                schema.SYSTEM_HEATING_SETPOINT_C,
            ]
            cooling_setpoint = system_state[
                system_i,
                schema.SYSTEM_COOLING_SETPOINT_C,
            ]

            if has_heating and zone_temp < heating_setpoint - thermostat_deadband_c:
                heating_power = max(0.0, max_heating_power)

            elif has_cooling and zone_temp > cooling_setpoint + thermostat_deadband_c:
                cooling_power = max(0.0, max_cooling_power)

    system_state[system_i, schema.SYSTEM_HEATING_POWER_W] = heating_power
    system_state[system_i, schema.SYSTEM_COOLING_POWER_W] = cooling_power

    return system_state


def update_all_hvac_powers(
    system_state,
    system_static,
    zone_state,
    thermostat_deadband_c=0.5,
):
    for system_i in range(system_state.shape[0]):
        update_hvac_power_for_system(
            system_state=system_state,
            system_static=system_static,
            zone_state=zone_state,
            system_i=system_i,
            thermostat_deadband_c=thermostat_deadband_c,
        )

    return system_state


# =============================================================================
# Window / light / blind / ventilation normalization
# =============================================================================

def normalize_window_state_for_system(system_state, system_static, system_i):
    has_window = system_static[system_i, schema.SYSTEM_STATIC_HAS_WINDOW] > 0.0

    if not has_window:
        system_state[system_i, schema.SYSTEM_WINDOW_STATE] = schema.WINDOW_STATE_CLOSED
        system_state[system_i, schema.SYSTEM_WINDOW_OPEN_FRACTION] = 0.0
        return system_state

    state = int(system_state[system_i, schema.SYSTEM_WINDOW_STATE])
    fraction = clip01(
        system_state[system_i, schema.SYSTEM_WINDOW_OPEN_FRACTION]
    )

    if state == schema.WINDOW_STATE_OPEN and fraction <= 0.0:
        fraction = 1.0

    if state == schema.WINDOW_STATE_CLOSED:
        fraction = 0.0

    if fraction > 0.0:
        state = schema.WINDOW_STATE_OPEN
    else:
        state = schema.WINDOW_STATE_CLOSED

    system_state[system_i, schema.SYSTEM_WINDOW_STATE] = state
    system_state[system_i, schema.SYSTEM_WINDOW_OPEN_FRACTION] = fraction

    return system_state


def normalize_light_state_for_system(system_state, system_static, system_i):
    has_lights = system_static[system_i, schema.SYSTEM_STATIC_HAS_LIGHTS] > 0.0

    if not has_lights:
        system_state[system_i, schema.SYSTEM_LIGHT_STATE] = schema.LIGHT_STATE_OFF
        system_state[system_i, schema.SYSTEM_LIGHTING_POWER_W] = 0.0
        return system_state

    state = int(system_state[system_i, schema.SYSTEM_LIGHT_STATE])
    max_power = system_static[
        system_i,
        schema.SYSTEM_STATIC_MAX_LIGHTING_POWER_W,
    ]
    power = system_state[system_i, schema.SYSTEM_LIGHTING_POWER_W]

    if state == schema.LIGHT_STATE_ON:
        if power <= 0.0:
            power = max_power

        power = clip(power, 0.0, max_power)

    else:
        state = schema.LIGHT_STATE_OFF
        power = 0.0

    system_state[system_i, schema.SYSTEM_LIGHT_STATE] = state
    system_state[system_i, schema.SYSTEM_LIGHTING_POWER_W] = power

    return system_state


def normalize_blind_state_for_system(system_state, system_static, system_i):
    has_blinds = system_static[system_i, schema.SYSTEM_STATIC_HAS_BLINDS] > 0.0

    if not has_blinds:
        system_state[system_i, schema.SYSTEM_BLIND_STATE] = schema.BLIND_STATE_OPEN
        system_state[system_i, schema.SYSTEM_BLIND_CLOSED_FRACTION] = 0.0
        return system_state

    state = int(system_state[system_i, schema.SYSTEM_BLIND_STATE])
    fraction = clip01(
        system_state[system_i, schema.SYSTEM_BLIND_CLOSED_FRACTION]
    )

    if state == schema.BLIND_STATE_CLOSED:
        fraction = 1.0

    elif state == schema.BLIND_STATE_OPEN:
        fraction = 0.0

    else:
        state = schema.BLIND_STATE_PARTIAL

    if fraction <= 0.0:
        state = schema.BLIND_STATE_OPEN
    elif fraction >= 1.0:
        state = schema.BLIND_STATE_CLOSED
    else:
        state = schema.BLIND_STATE_PARTIAL

    system_state[system_i, schema.SYSTEM_BLIND_STATE] = state
    system_state[system_i, schema.SYSTEM_BLIND_CLOSED_FRACTION] = fraction

    return system_state


def normalize_ventilation_state_for_system(system_state, system_static, system_i):
    has_mech = (
        system_static[
            system_i,
            schema.SYSTEM_STATIC_HAS_MECH_VENTILATION,
        ]
        > 0.0
    )

    mode = int(system_state[system_i, schema.SYSTEM_VENTILATION_MODE])
    flow = system_state[
        system_i,
        schema.SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S,
    ]
    max_flow = system_static[
        system_i,
        schema.SYSTEM_STATIC_MAX_MECH_VENT_FLOW_M3_S,
    ]

    if not has_mech:
        system_state[system_i, schema.SYSTEM_VENTILATION_MODE] = schema.VENTILATION_MODE_OFF
        system_state[
            system_i,
            schema.SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S,
        ] = 0.0
        return system_state

    if mode == schema.VENTILATION_MODE_OFF:
        flow = 0.0

    elif mode == schema.VENTILATION_MODE_MECHANICAL:
        if flow <= 0.0:
            flow = max_flow
        flow = clip(flow, 0.0, max_flow)

    elif mode == schema.VENTILATION_MODE_HYBRID:
        if flow <= 0.0:
            flow = max_flow
        flow = clip(flow, 0.0, max_flow)

    else:
        # Natural ventilation is represented by window state/airflow later.
        # No mechanical flow.
        mode = schema.VENTILATION_MODE_NATURAL
        flow = 0.0

    system_state[system_i, schema.SYSTEM_VENTILATION_MODE] = mode
    system_state[
        system_i,
        schema.SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S,
    ] = flow

    return system_state


# =============================================================================
# Full constraint enforcement
# =============================================================================

def enforce_system_constraints_reference(
    system_state,
    system_static,
    zone_state=None,
    thermostat_deadband_c=0.5,
):
    """
    Reference implementation of physical availability and consistency checks.

    Kept for temporary comparison/debugging. The public
    enforce_system_constraints(...) below uses the fast inlined path.
    """
    n_systems = system_state.shape[0]

    for system_i in range(n_systems):
        enforce_setpoint_constraints_for_system(
            system_state=system_state,
            system_i=system_i,
        )

        hvac_mode = int(system_state[system_i, schema.SYSTEM_HVAC_MODE])

        has_heating = system_static[system_i, schema.SYSTEM_STATIC_HAS_HEATING] > 0.0
        has_cooling = system_static[system_i, schema.SYSTEM_STATIC_HAS_COOLING] > 0.0

        if hvac_mode == schema.HVAC_MODE_HEATING and not has_heating:
            system_state[system_i, schema.SYSTEM_HVAC_MODE] = schema.HVAC_MODE_OFF

        if hvac_mode == schema.HVAC_MODE_COOLING and not has_cooling:
            system_state[system_i, schema.SYSTEM_HVAC_MODE] = schema.HVAC_MODE_OFF

        if hvac_mode == schema.HVAC_MODE_AUTO and not has_heating and not has_cooling:
            system_state[system_i, schema.SYSTEM_HVAC_MODE] = schema.HVAC_MODE_OFF

        normalize_window_state_for_system(
            system_state=system_state,
            system_static=system_static,
            system_i=system_i,
        )
        normalize_light_state_for_system(
            system_state=system_state,
            system_static=system_static,
            system_i=system_i,
        )
        normalize_blind_state_for_system(
            system_state=system_state,
            system_static=system_static,
            system_i=system_i,
        )
        normalize_ventilation_state_for_system(
            system_state=system_state,
            system_static=system_static,
            system_i=system_i,
        )
        update_hvac_power_for_system(
            system_state=system_state,
            system_static=system_static,
            zone_state=zone_state,
            system_i=system_i,
            thermostat_deadband_c=thermostat_deadband_c,
        )

    return system_state


def enforce_system_constraints(
    system_state,
    system_static,
    zone_state=None,
    thermostat_deadband_c=0.5,
):
    """
    Fast inlined physical availability and consistency checks.

    Same public API and same intended behavior as the previous implementation,
    but avoids many tiny helper calls inside the per-system loop.
    """
    n_systems = system_state.shape[0]

    min_heating_setpoint_c = 5.0
    max_heating_setpoint_c = 30.0
    min_cooling_setpoint_c = 10.0
    max_cooling_setpoint_c = 40.0
    minimum_deadband_c = 1.0

    for system_i in range(n_systems):
        # ---------------------------------------------------------------------
        # Setpoint constraints.
        # ---------------------------------------------------------------------

        heating_setpoint = system_state[
            system_i,
            schema.SYSTEM_HEATING_SETPOINT_C,
        ]
        cooling_setpoint = system_state[
            system_i,
            schema.SYSTEM_COOLING_SETPOINT_C,
        ]

        if heating_setpoint < min_heating_setpoint_c:
            heating_setpoint = min_heating_setpoint_c
        elif heating_setpoint > max_heating_setpoint_c:
            heating_setpoint = max_heating_setpoint_c

        if cooling_setpoint < min_cooling_setpoint_c:
            cooling_setpoint = min_cooling_setpoint_c
        elif cooling_setpoint > max_cooling_setpoint_c:
            cooling_setpoint = max_cooling_setpoint_c

        if heating_setpoint + minimum_deadband_c >= cooling_setpoint:
            midpoint = 0.5 * (heating_setpoint + cooling_setpoint)
            heating_setpoint = midpoint - 0.5 * minimum_deadband_c
            cooling_setpoint = midpoint + 0.5 * minimum_deadband_c

            if heating_setpoint < min_heating_setpoint_c:
                heating_setpoint = min_heating_setpoint_c
            elif heating_setpoint > max_heating_setpoint_c:
                heating_setpoint = max_heating_setpoint_c

            if cooling_setpoint < min_cooling_setpoint_c:
                cooling_setpoint = min_cooling_setpoint_c
            elif cooling_setpoint > max_cooling_setpoint_c:
                cooling_setpoint = max_cooling_setpoint_c

        system_state[
            system_i,
            schema.SYSTEM_HEATING_SETPOINT_C,
        ] = heating_setpoint
        system_state[
            system_i,
            schema.SYSTEM_COOLING_SETPOINT_C,
        ] = cooling_setpoint

        # ---------------------------------------------------------------------
        # Static availability.
        # ---------------------------------------------------------------------

        has_heating = system_static[
            system_i,
            schema.SYSTEM_STATIC_HAS_HEATING,
        ] > 0.0
        has_cooling = system_static[
            system_i,
            schema.SYSTEM_STATIC_HAS_COOLING,
        ] > 0.0
        has_window = system_static[
            system_i,
            schema.SYSTEM_STATIC_HAS_WINDOW,
        ] > 0.0
        has_lights = system_static[
            system_i,
            schema.SYSTEM_STATIC_HAS_LIGHTS,
        ] > 0.0
        has_blinds = system_static[
            system_i,
            schema.SYSTEM_STATIC_HAS_BLINDS,
        ] > 0.0
        has_mech = system_static[
            system_i,
            schema.SYSTEM_STATIC_HAS_MECH_VENTILATION,
        ] > 0.0

        # ---------------------------------------------------------------------
        # HVAC mode availability.
        # ---------------------------------------------------------------------

        hvac_mode = int(system_state[system_i, schema.SYSTEM_HVAC_MODE])

        if hvac_mode == schema.HVAC_MODE_HEATING and not has_heating:
            hvac_mode = schema.HVAC_MODE_OFF

        if hvac_mode == schema.HVAC_MODE_COOLING and not has_cooling:
            hvac_mode = schema.HVAC_MODE_OFF

        if hvac_mode == schema.HVAC_MODE_AUTO and not has_heating and not has_cooling:
            hvac_mode = schema.HVAC_MODE_OFF

        system_state[system_i, schema.SYSTEM_HVAC_MODE] = hvac_mode

        # ---------------------------------------------------------------------
        # Window normalization.
        # ---------------------------------------------------------------------

        if not has_window:
            system_state[
                system_i,
                schema.SYSTEM_WINDOW_STATE,
            ] = schema.WINDOW_STATE_CLOSED
            system_state[
                system_i,
                schema.SYSTEM_WINDOW_OPEN_FRACTION,
            ] = 0.0
        else:
            window_state = int(
                system_state[system_i, schema.SYSTEM_WINDOW_STATE]
            )
            window_fraction = system_state[
                system_i,
                schema.SYSTEM_WINDOW_OPEN_FRACTION,
            ]

            if window_fraction < 0.0:
                window_fraction = 0.0
            elif window_fraction > 1.0:
                window_fraction = 1.0

            if window_state == schema.WINDOW_STATE_OPEN and window_fraction <= 0.0:
                window_fraction = 1.0

            if window_state == schema.WINDOW_STATE_CLOSED:
                window_fraction = 0.0

            if window_fraction > 0.0:
                window_state = schema.WINDOW_STATE_OPEN
            else:
                window_state = schema.WINDOW_STATE_CLOSED

            system_state[
                system_i,
                schema.SYSTEM_WINDOW_STATE,
            ] = window_state
            system_state[
                system_i,
                schema.SYSTEM_WINDOW_OPEN_FRACTION,
            ] = window_fraction

        # ---------------------------------------------------------------------
        # Light normalization.
        # ---------------------------------------------------------------------

        if not has_lights:
            system_state[
                system_i,
                schema.SYSTEM_LIGHT_STATE,
            ] = schema.LIGHT_STATE_OFF
            system_state[
                system_i,
                schema.SYSTEM_LIGHTING_POWER_W,
            ] = 0.0
        else:
            light_state = int(system_state[system_i, schema.SYSTEM_LIGHT_STATE])
            max_lighting_power = system_static[
                system_i,
                schema.SYSTEM_STATIC_MAX_LIGHTING_POWER_W,
            ]
            lighting_power = system_state[
                system_i,
                schema.SYSTEM_LIGHTING_POWER_W,
            ]

            if light_state == schema.LIGHT_STATE_ON:
                if lighting_power <= 0.0:
                    lighting_power = max_lighting_power

                if lighting_power < 0.0:
                    lighting_power = 0.0
                elif lighting_power > max_lighting_power:
                    lighting_power = max_lighting_power
            else:
                light_state = schema.LIGHT_STATE_OFF
                lighting_power = 0.0

            system_state[
                system_i,
                schema.SYSTEM_LIGHT_STATE,
            ] = light_state
            system_state[
                system_i,
                schema.SYSTEM_LIGHTING_POWER_W,
            ] = lighting_power

        # ---------------------------------------------------------------------
        # Blind normalization.
        # ---------------------------------------------------------------------

        if not has_blinds:
            system_state[
                system_i,
                schema.SYSTEM_BLIND_STATE,
            ] = schema.BLIND_STATE_OPEN
            system_state[
                system_i,
                schema.SYSTEM_BLIND_CLOSED_FRACTION,
            ] = 0.0
        else:
            blind_state = int(system_state[system_i, schema.SYSTEM_BLIND_STATE])
            blind_fraction = system_state[
                system_i,
                schema.SYSTEM_BLIND_CLOSED_FRACTION,
            ]

            if blind_fraction < 0.0:
                blind_fraction = 0.0
            elif blind_fraction > 1.0:
                blind_fraction = 1.0

            if blind_state == schema.BLIND_STATE_CLOSED:
                blind_fraction = 1.0
            elif blind_state == schema.BLIND_STATE_OPEN:
                blind_fraction = 0.0
            else:
                blind_state = schema.BLIND_STATE_PARTIAL

            if blind_fraction <= 0.0:
                blind_state = schema.BLIND_STATE_OPEN
            elif blind_fraction >= 1.0:
                blind_state = schema.BLIND_STATE_CLOSED
            else:
                blind_state = schema.BLIND_STATE_PARTIAL

            system_state[
                system_i,
                schema.SYSTEM_BLIND_STATE,
            ] = blind_state
            system_state[
                system_i,
                schema.SYSTEM_BLIND_CLOSED_FRACTION,
            ] = blind_fraction

        # ---------------------------------------------------------------------
        # Mechanical ventilation normalization.
        # ---------------------------------------------------------------------

        if not has_mech:
            system_state[
                system_i,
                schema.SYSTEM_VENTILATION_MODE,
            ] = schema.VENTILATION_MODE_OFF
            system_state[
                system_i,
                schema.SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S,
            ] = 0.0
        else:
            ventilation_mode = int(
                system_state[system_i, schema.SYSTEM_VENTILATION_MODE]
            )
            ventilation_flow = system_state[
                system_i,
                schema.SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S,
            ]
            max_ventilation_flow = system_static[
                system_i,
                schema.SYSTEM_STATIC_MAX_MECH_VENT_FLOW_M3_S,
            ]

            if ventilation_mode == schema.VENTILATION_MODE_OFF:
                ventilation_flow = 0.0

            elif ventilation_mode == schema.VENTILATION_MODE_MECHANICAL:
                if ventilation_flow <= 0.0:
                    ventilation_flow = max_ventilation_flow

                if ventilation_flow < 0.0:
                    ventilation_flow = 0.0
                elif ventilation_flow > max_ventilation_flow:
                    ventilation_flow = max_ventilation_flow

            elif ventilation_mode == schema.VENTILATION_MODE_HYBRID:
                if ventilation_flow <= 0.0:
                    ventilation_flow = max_ventilation_flow

                if ventilation_flow < 0.0:
                    ventilation_flow = 0.0
                elif ventilation_flow > max_ventilation_flow:
                    ventilation_flow = max_ventilation_flow

            else:
                ventilation_mode = schema.VENTILATION_MODE_NATURAL
                ventilation_flow = 0.0

            system_state[
                system_i,
                schema.SYSTEM_VENTILATION_MODE,
            ] = ventilation_mode
            system_state[
                system_i,
                schema.SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S,
            ] = ventilation_flow

        # ---------------------------------------------------------------------
        # HVAC power update.
        # ---------------------------------------------------------------------

        max_heating_power = system_static[
            system_i,
            schema.SYSTEM_STATIC_MAX_HEATING_POWER_W,
        ]
        max_cooling_power = system_static[
            system_i,
            schema.SYSTEM_STATIC_MAX_COOLING_POWER_W,
        ]

        heating_power = 0.0
        cooling_power = 0.0

        if hvac_mode == schema.HVAC_MODE_HEATING:
            if has_heating:
                if max_heating_power > 0.0:
                    heating_power = max_heating_power

        elif hvac_mode == schema.HVAC_MODE_COOLING:
            if has_cooling:
                if max_cooling_power > 0.0:
                    cooling_power = max_cooling_power

        elif hvac_mode == schema.HVAC_MODE_AUTO:
            zone_id = int(system_state[system_i, schema.SYSTEM_ZONE_ID])

            if zone_state is not None and zone_id != schema.MISSING_ID:
                zone_temp = zone_state[zone_id, schema.ZONE_AIR_TEMPERATURE_C]

                if has_heating and zone_temp < heating_setpoint - thermostat_deadband_c:
                    if max_heating_power > 0.0:
                        heating_power = max_heating_power

                elif has_cooling and zone_temp > cooling_setpoint + thermostat_deadband_c:
                    if max_cooling_power > 0.0:
                        cooling_power = max_cooling_power

        system_state[
            system_i,
            schema.SYSTEM_HEATING_POWER_W,
        ] = heating_power
        system_state[
            system_i,
            schema.SYSTEM_COOLING_POWER_W,
        ] = cooling_power

    return system_state


# =============================================================================
# Direct numeric control setters
# =============================================================================

def set_hvac_off(system_state, system_i):
    system_state[system_i, schema.SYSTEM_HVAC_MODE] = schema.HVAC_MODE_OFF
    system_state[system_i, schema.SYSTEM_HEATING_POWER_W] = 0.0
    system_state[system_i, schema.SYSTEM_COOLING_POWER_W] = 0.0
    return system_state


def set_heating_on(system_state, system_static, system_i):
    if system_static[system_i, schema.SYSTEM_STATIC_HAS_HEATING] <= 0.0:
        return set_hvac_off(system_state, system_i)

    system_state[system_i, schema.SYSTEM_HVAC_MODE] = schema.HVAC_MODE_HEATING
    system_state[system_i, schema.SYSTEM_HEATING_POWER_W] = system_static[
        system_i,
        schema.SYSTEM_STATIC_MAX_HEATING_POWER_W,
    ]
    system_state[system_i, schema.SYSTEM_COOLING_POWER_W] = 0.0
    return system_state


def set_cooling_on(system_state, system_static, system_i):
    if system_static[system_i, schema.SYSTEM_STATIC_HAS_COOLING] <= 0.0:
        return set_hvac_off(system_state, system_i)

    system_state[system_i, schema.SYSTEM_HVAC_MODE] = schema.HVAC_MODE_COOLING
    system_state[system_i, schema.SYSTEM_COOLING_POWER_W] = system_static[
        system_i,
        schema.SYSTEM_STATIC_MAX_COOLING_POWER_W,
    ]
    system_state[system_i, schema.SYSTEM_HEATING_POWER_W] = 0.0
    return system_state


def set_hvac_auto(system_state, system_static, system_i):
    has_heating = system_static[system_i, schema.SYSTEM_STATIC_HAS_HEATING] > 0.0
    has_cooling = system_static[system_i, schema.SYSTEM_STATIC_HAS_COOLING] > 0.0

    if not has_heating and not has_cooling:
        return set_hvac_off(system_state, system_i)

    system_state[system_i, schema.SYSTEM_HVAC_MODE] = schema.HVAC_MODE_AUTO
    return system_state


def set_window_open(system_state, system_static, system_i, fraction=1.0):
    if system_static[system_i, schema.SYSTEM_STATIC_HAS_WINDOW] <= 0.0:
        system_state[system_i, schema.SYSTEM_WINDOW_STATE] = schema.WINDOW_STATE_CLOSED
        system_state[system_i, schema.SYSTEM_WINDOW_OPEN_FRACTION] = 0.0
        return system_state

    fraction = clip01(fraction)

    system_state[system_i, schema.SYSTEM_WINDOW_STATE] = (
        schema.WINDOW_STATE_OPEN if fraction > 0.0 else schema.WINDOW_STATE_CLOSED
    )
    system_state[system_i, schema.SYSTEM_WINDOW_OPEN_FRACTION] = fraction

    return system_state


def set_window_closed(system_state, system_i):
    system_state[system_i, schema.SYSTEM_WINDOW_STATE] = schema.WINDOW_STATE_CLOSED
    system_state[system_i, schema.SYSTEM_WINDOW_OPEN_FRACTION] = 0.0
    return system_state


def set_lights_on(system_state, system_static, system_i):
    if system_static[system_i, schema.SYSTEM_STATIC_HAS_LIGHTS] <= 0.0:
        system_state[system_i, schema.SYSTEM_LIGHT_STATE] = schema.LIGHT_STATE_OFF
        system_state[system_i, schema.SYSTEM_LIGHTING_POWER_W] = 0.0
        return system_state

    system_state[system_i, schema.SYSTEM_LIGHT_STATE] = schema.LIGHT_STATE_ON
    system_state[system_i, schema.SYSTEM_LIGHTING_POWER_W] = system_static[
        system_i,
        schema.SYSTEM_STATIC_MAX_LIGHTING_POWER_W,
    ]

    return system_state


def set_lights_off(system_state, system_i):
    system_state[system_i, schema.SYSTEM_LIGHT_STATE] = schema.LIGHT_STATE_OFF
    system_state[system_i, schema.SYSTEM_LIGHTING_POWER_W] = 0.0
    return system_state


def set_blinds_closed(system_state, system_static, system_i, fraction=1.0):
    if system_static[system_i, schema.SYSTEM_STATIC_HAS_BLINDS] <= 0.0:
        system_state[system_i, schema.SYSTEM_BLIND_STATE] = schema.BLIND_STATE_OPEN
        system_state[system_i, schema.SYSTEM_BLIND_CLOSED_FRACTION] = 0.0
        return system_state

    fraction = clip01(fraction)

    if fraction <= 0.0:
        state = schema.BLIND_STATE_OPEN
    elif fraction >= 1.0:
        state = schema.BLIND_STATE_CLOSED
    else:
        state = schema.BLIND_STATE_PARTIAL

    system_state[system_i, schema.SYSTEM_BLIND_STATE] = state
    system_state[system_i, schema.SYSTEM_BLIND_CLOSED_FRACTION] = fraction

    return system_state


def set_blinds_open(system_state, system_i):
    system_state[system_i, schema.SYSTEM_BLIND_STATE] = schema.BLIND_STATE_OPEN
    system_state[system_i, schema.SYSTEM_BLIND_CLOSED_FRACTION] = 0.0
    return system_state


def set_mechanical_ventilation_on(system_state, system_static, system_i):
    if system_static[system_i, schema.SYSTEM_STATIC_HAS_MECH_VENTILATION] <= 0.0:
        system_state[system_i, schema.SYSTEM_VENTILATION_MODE] = schema.VENTILATION_MODE_OFF
        system_state[
            system_i,
            schema.SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S,
        ] = 0.0
        return system_state

    system_state[system_i, schema.SYSTEM_VENTILATION_MODE] = schema.VENTILATION_MODE_MECHANICAL
    system_state[
        system_i,
        schema.SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S,
    ] = system_static[
        system_i,
        schema.SYSTEM_STATIC_MAX_MECH_VENT_FLOW_M3_S,
    ]

    return system_state


def set_mechanical_ventilation_off(system_state, system_i):
    system_state[system_i, schema.SYSTEM_VENTILATION_MODE] = schema.VENTILATION_MODE_OFF
    system_state[
        system_i,
        schema.SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S,
    ] = 0.0
    return system_state


# =============================================================================
# Apply action to system state
# =============================================================================

def apply_control_action_to_system(
    person_state,
    zone_state,
    system_state,
    system_static,
    action_static,
    person_i,
    action_i,
):
    """
    Apply one selected action's system/control effect.

    This is the central Phase 10 replacement for scattered control effects.

    It mutates system_state in place.
    """
    action_type = int(action_static[action_i, schema.ACTION_TYPE])

    target_system_id = get_action_target_system_id(
        action_static=action_static,
        person_state=person_state,
        system_state=system_state,
        person_i=person_i,
        action_i=action_i,
    )

    if target_system_id == schema.MISSING_ID:
        return False

    if action_type == schema.ACTION_TYPE_OPEN_WINDOW:
        set_window_open(
            system_state=system_state,
            system_static=system_static,
            system_i=target_system_id,
            fraction=1.0,
        )

    elif action_type == schema.ACTION_TYPE_CLOSE_WINDOW:
        set_window_closed(
            system_state=system_state,
            system_i=target_system_id,
        )

    elif action_type == schema.ACTION_TYPE_TURN_LIGHT_ON:
        set_lights_on(
            system_state=system_state,
            system_static=system_static,
            system_i=target_system_id,
        )

    elif action_type == schema.ACTION_TYPE_TURN_LIGHT_OFF:
        set_lights_off(
            system_state=system_state,
            system_i=target_system_id,
        )

    elif action_type == schema.ACTION_TYPE_TURN_HEATING_ON:
        set_heating_on(
            system_state=system_state,
            system_static=system_static,
            system_i=target_system_id,
        )

    elif action_type == schema.ACTION_TYPE_TURN_HEATING_OFF:
        if int(system_state[target_system_id, schema.SYSTEM_HVAC_MODE]) == schema.HVAC_MODE_HEATING:
            set_hvac_off(
                system_state=system_state,
                system_i=target_system_id,
            )
        else:
            system_state[target_system_id, schema.SYSTEM_HEATING_POWER_W] = 0.0

    elif action_type == schema.ACTION_TYPE_TURN_COOLING_ON:
        set_cooling_on(
            system_state=system_state,
            system_static=system_static,
            system_i=target_system_id,
        )

    elif action_type == schema.ACTION_TYPE_TURN_COOLING_OFF:
        if int(system_state[target_system_id, schema.SYSTEM_HVAC_MODE]) == schema.HVAC_MODE_COOLING:
            set_hvac_off(
                system_state=system_state,
                system_i=target_system_id,
            )
        else:
            system_state[target_system_id, schema.SYSTEM_COOLING_POWER_W] = 0.0

    elif action_type == schema.ACTION_TYPE_ADJUST_THERMOSTAT:
        adjust_thermostat_from_zone_conditions(
            zone_state=zone_state,
            system_state=system_state,
            system_i=target_system_id,
        )

    elif action_type == schema.ACTION_TYPE_OPEN_BLINDS:
        set_blinds_open(
            system_state=system_state,
            system_i=target_system_id,
        )

    elif action_type == schema.ACTION_TYPE_CLOSE_BLINDS:
        set_blinds_closed(
            system_state=system_state,
            system_static=system_static,
            system_i=target_system_id,
            fraction=1.0,
        )

    elif action_type == schema.ACTION_TYPE_TURN_VENTILATION_ON:
        set_mechanical_ventilation_on(
            system_state=system_state,
            system_static=system_static,
            system_i=target_system_id,
        )

    elif action_type == schema.ACTION_TYPE_TURN_VENTILATION_OFF:
        set_mechanical_ventilation_off(
            system_state=system_state,
            system_i=target_system_id,
        )

    else:
        return False

    enforce_system_constraints(
        system_state=system_state,
        system_static=system_static,
        zone_state=zone_state,
    )

    return True


def apply_control_actions_from_chosen_actions(
    person_state,
    zone_state,
    system_state,
    system_static,
    action_static,
    chosen_action_indices,
):
    """
    Apply system/control effects for one chosen action per person.

    This does not start timers. It only mutates system_state.
    Execution timing remains Phase 9 territory.
    """
    n_persons = person_state.shape[0]
    applied = np.zeros((n_persons,), dtype=np.float64)

    for person_i in range(n_persons):
        action_i = int(chosen_action_indices[person_i])

        if action_i < 0 or action_i >= action_static.shape[0]:
            applied[person_i] = 0.0
            continue

        ok = apply_control_action_to_system(
            person_state=person_state,
            zone_state=zone_state,
            system_state=system_state,
            system_static=system_static,
            action_static=action_static,
            person_i=person_i,
            action_i=action_i,
        )

        applied[person_i] = 1.0 if ok else 0.0

    return applied


# =============================================================================
# Thermostat adjustment
# =============================================================================

def adjust_thermostat_from_zone_conditions(
    zone_state,
    system_state,
    system_i,
    heating_delta_c=1.0,
    cooling_delta_c=1.0,
):
    """
    Numeric thermostat adjustment.

    Since ACTION_TYPE_ADJUST_THERMOSTAT has no direction column yet:
        - if zone is cold relative to heating setpoint, raise heating setpoint
        - if zone is hot relative to cooling setpoint, lower cooling setpoint
        - otherwise no change
    """
    zone_id = int(system_state[system_i, schema.SYSTEM_ZONE_ID])

    if zone_id == schema.MISSING_ID:
        return system_state

    temp = zone_state[zone_id, schema.ZONE_AIR_TEMPERATURE_C]

    heating_setpoint = system_state[
        system_i,
        schema.SYSTEM_HEATING_SETPOINT_C,
    ]
    cooling_setpoint = system_state[
        system_i,
        schema.SYSTEM_COOLING_SETPOINT_C,
    ]

    if temp < heating_setpoint:
        system_state[
            system_i,
            schema.SYSTEM_HEATING_SETPOINT_C,
        ] = heating_setpoint + heating_delta_c

    elif temp > cooling_setpoint:
        system_state[
            system_i,
            schema.SYSTEM_COOLING_SETPOINT_C,
        ] = cooling_setpoint - cooling_delta_c

    enforce_setpoint_constraints_for_system(
        system_state=system_state,
        system_i=system_i,
    )

    return system_state


# =============================================================================
# System power/gain contribution helpers
# =============================================================================

def add_system_power_to_dwelling_building(
    system_state,
    zone_state,
    dwelling_state,
    building_state,
):
    """
    Add current system power demand into dwelling/building totals.

    This includes:
        heating power
        cooling power
        lighting power

    Ventilation fan power is not explicit in current schema, so mechanical
    ventilation flow is not converted to fan power here yet.
    """
    for system_i in range(system_state.shape[0]):
        zone_id = int(system_state[system_i, schema.SYSTEM_ZONE_ID])

        if zone_id == schema.MISSING_ID:
            continue

        dwelling_id = int(zone_state[zone_id, schema.ZONE_DWELLING_ID])
        building_id = int(zone_state[zone_id, schema.ZONE_BUILDING_ID])

        power_w = 0.0
        power_w += system_state[system_i, schema.SYSTEM_HEATING_POWER_W]
        power_w += system_state[system_i, schema.SYSTEM_COOLING_POWER_W]
        power_w += system_state[system_i, schema.SYSTEM_LIGHTING_POWER_W]

        if dwelling_id != schema.MISSING_ID:
            dwelling_state[
                dwelling_id,
                schema.DWELLING_TOTAL_POWER_W,
            ] += power_w
            dwelling_state[
                dwelling_id,
                schema.DWELLING_TOTAL_ELECTRICITY_DEMAND_W,
            ] += power_w

        if building_id != schema.MISSING_ID:
            building_state[
                building_id,
                schema.BUILDING_TOTAL_POWER_W,
            ] += power_w
            building_state[
                building_id,
                schema.BUILDING_TOTAL_ELECTRICITY_DEMAND_W,
            ] += power_w

    return True


def add_lighting_gains_to_zones(
    system_state,
    zone_state,
    internal_gains=None,
):
    """
    Add lighting power as lighting heat gain.

    This is useful after system controls are normalized.
    """
    for system_i in range(system_state.shape[0]):
        zone_id = int(system_state[system_i, schema.SYSTEM_ZONE_ID])

        if zone_id == schema.MISSING_ID:
            continue

        lighting_power = system_state[system_i, schema.SYSTEM_LIGHTING_POWER_W]

        zone_state[zone_id, schema.ZONE_LIGHTING_GAIN_W] += lighting_power
        zone_state[zone_id, schema.ZONE_INTERNAL_HEAT_GAIN_W] += lighting_power

        if internal_gains is not None:
            internal_gains[zone_id, schema.GAIN_ZONE_ID] = zone_id
            internal_gains[zone_id, schema.GAIN_LIGHTING_HEAT_W] += lighting_power
            internal_gains[zone_id, schema.GAIN_TOTAL_HEAT_W] += lighting_power
            internal_gains[zone_id, schema.GAIN_ELECTRIC_POWER_W] += lighting_power

    return True


# =============================================================================
# Full system update
# =============================================================================

def update_system_control_state(
    system_state,
    system_static,
    zone_state,
    dwelling_state=None,
    building_state=None,
    internal_gains=None,
    thermostat_deadband_c=0.5,
    add_power_totals=False,
    add_lighting_gains=False,
):
    """
    Full Phase 10 system/control update.

    This:
        1. enforces availability constraints
        2. updates HVAC power from mode/setpoints
        3. optionally adds system power to dwelling/building totals
        4. optionally adds lighting heat gains to zones

    Most timestep orchestration should call this after action execution.
    """
    enforce_system_constraints(
        system_state=system_state,
        system_static=system_static,
        zone_state=zone_state,
        thermostat_deadband_c=thermostat_deadband_c,
    )

    if add_lighting_gains:
        add_lighting_gains_to_zones(
            system_state=system_state,
            zone_state=zone_state,
            internal_gains=internal_gains,
        )

    if add_power_totals:
        if dwelling_state is None or building_state is None:
            raise ValueError(
                "dwelling_state and building_state are required when add_power_totals=True."
            )

        add_system_power_to_dwelling_building(
            system_state=system_state,
            zone_state=zone_state,
            dwelling_state=dwelling_state,
            building_state=building_state,
        )

    return system_state