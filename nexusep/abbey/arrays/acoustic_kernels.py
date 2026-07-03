"""
ABBEY array acoustic kernels.

Phase 11.6:
    Move simplified acoustic / indoor-noise calculation into numeric arrays.

This module calculates:
    - background zone noise
    - local foreground-action noise
    - local background-process noise
    - optional explicit zone noise-source array
    - outdoor noise transmitted through windows/envelope
    - optional interzone transmitted noise

It updates:
    zone_state[:, ZONE_NOISE_DB]
    physics_result[:, PHYSICS_NOISE_DB]

Important:
    - No zone objects.
    - No acoustic dataclasses.
    - No graph objects.
    - No dicts in timestep-facing functions.
    - No strings.
    - Numeric arrays only.

Schema limitation:
    The current schema does not yet have explicit acoustic surface/link columns.
    Therefore this file defines optional lightweight acoustic-link arrays.

Weather limitation:
    The schema may or may not contain an outdoor-noise weather column.
    So step_building_acoustics(...) accepts outdoor_noise_db explicitly.
"""

import math

import numpy as np

from nexusep.abbey.arrays import schema


# =============================================================================
# Constants
# =============================================================================

REFERENCE_ENERGY = 1.0

DEFAULT_BACKGROUND_NOISE_DB = 30.0
DEFAULT_OUTDOOR_NOISE_DB = 45.0
DEFAULT_INDOOR_NOISE_INITIAL_DB = 35.0

DEFAULT_NOISE_COMFORT_DB = 35.0
DEFAULT_NOISE_STRESS_DB = 75.0

MIN_NOISE_DB = 0.0
MAX_REASONABLE_NOISE_DB = 140.0

DEFAULT_CLOSED_WINDOW_ATTENUATION_DB = 30.0
DEFAULT_OPEN_WINDOW_ATTENUATION_DB = 10.0
DEFAULT_NO_WINDOW_ATTENUATION_DB = 38.0

DEFAULT_ROOM_ABSORPTION_FACTOR = 0.30
DEFAULT_ROOM_ABSORPTION_MAX_ATTENUATION_DB = 6.0

DEFAULT_INTERZONE_SOUND_REDUCTION_DB = 35.0

# Optional explicit zone noise-source array:
#
# zone_noise_source_array[source_i, ZONE_NOISE_SOURCE_*]
#
ZONE_NOISE_SOURCE_ZONE_ID = 0
ZONE_NOISE_SOURCE_NOISE_DB = 1
ZONE_NOISE_SOURCE_ACTIVE = 2
N_ZONE_NOISE_SOURCE_COLS = 3

# Optional acoustic link array:
#
# acoustic_link_array[link_i, ACOUSTIC_LINK_*]
#
# The link is treated as symmetric unless ACOUSTIC_LINK_IS_DIRECTIONAL = 1.
#
ACOUSTIC_LINK_ZONE_A_ID = 0
ACOUSTIC_LINK_ZONE_B_ID = 1
ACOUSTIC_LINK_SOUND_REDUCTION_DB = 2
ACOUSTIC_LINK_OPEN_FRACTION = 3
ACOUSTIC_LINK_IS_DIRECTIONAL = 4
ACOUSTIC_LINK_CURRENT_A_TO_B_DB = 5
ACOUSTIC_LINK_CURRENT_B_TO_A_DB = 6
N_ACOUSTIC_LINK_COLS = 7


# =============================================================================
# Small helpers
# =============================================================================

def _schema_col(name, default=None):
    return getattr(schema, name, default)


def _non_negative(value):
    value = float(value)

    if value < 0.0:
        return 0.0

    return value


def _clip(value, minimum, maximum):
    value = float(value)

    if value < minimum:
        return float(minimum)

    if value > maximum:
        return float(maximum)

    return value


def _clip01(value):
    return _clip(value, 0.0, 1.0)


def _zone_is_outside(zone_state, zone_i):
    return int(zone_state[zone_i, schema.ZONE_TYPE]) == schema.ZONE_TYPE_OUTSIDE


def _is_active_process(process_state, process_i):
    return int(process_state[process_i, schema.PROCESS_STATE]) == schema.PROCESS_STATE_ACTIVE


# =============================================================================
# dB math
# =============================================================================

def db_to_energy(noise_db):
    """
    Convert dB level to relative acoustic energy.
    """
    noise_db = _non_negative(noise_db)

    if noise_db <= 0.0:
        return 0.0

    return REFERENCE_ENERGY * (10.0 ** (noise_db / 10.0))


def energy_to_db(energy, default_db=0.0):
    """
    Convert relative acoustic energy to dB.
    """
    energy = float(energy)

    if energy <= 0.0:
        return _non_negative(default_db)

    return 10.0 * math.log10(energy / REFERENCE_ENERGY)


def add_two_noise_levels_db(noise_a_db, noise_b_db, default_db=0.0):
    """
    Logarithmically add two dB levels.
    """
    energy = 0.0
    energy += db_to_energy(noise_a_db)
    energy += db_to_energy(noise_b_db)

    return energy_to_db(energy, default_db=default_db)


def add_noise_levels_db_from_array(noise_levels_db, n_levels, background_db=None, default_db=0.0):
    """
    Logarithmically add first n_levels from an array-like object.
    """
    total_energy = 0.0

    if background_db is not None:
        total_energy += db_to_energy(background_db)

    for i in range(n_levels):
        level = float(noise_levels_db[i])

        if level <= 0.0:
            continue

        total_energy += db_to_energy(level)

    if total_energy <= 0.0:
        return _non_negative(default_db)

    return energy_to_db(total_energy, default_db=default_db)


def add_noise_components_db(
    background_db,
    local_db,
    outdoor_db,
    interzone_db,
):
    """
    Combine receiver-side acoustic components.
    """
    components = np.zeros((4,), dtype=np.float64)

    components[0] = _non_negative(background_db)
    components[1] = _non_negative(local_db)
    components[2] = _non_negative(outdoor_db)
    components[3] = _non_negative(interzone_db)

    return add_noise_levels_db_from_array(
        noise_levels_db=components,
        n_levels=4,
        background_db=None,
        default_db=DEFAULT_BACKGROUND_NOISE_DB,
    )


def attenuate_noise_db(source_noise_db, attenuation_db, floor_db=MIN_NOISE_DB):
    """
    Apply simple dB attenuation.
    """
    source_noise_db = _non_negative(source_noise_db)
    attenuation_db = _non_negative(attenuation_db)
    floor_db = _non_negative(floor_db)

    return max(floor_db, source_noise_db - attenuation_db)


def normalize_noise_discomfort_input(
    noise_db,
    comfort_db=DEFAULT_NOISE_COMFORT_DB,
    stress_db=DEFAULT_NOISE_STRESS_DB,
):
    """
    Convert raw dB into normalized acoustic discomfort.

    0:
        at/below comfort_db

    1:
        at/above stress_db
    """
    noise_db = _non_negative(noise_db)
    comfort_db = _non_negative(comfort_db)
    stress_db = _non_negative(stress_db)

    if stress_db <= comfort_db:
        stress_db = comfort_db + 1.0

    return _clip01((noise_db - comfort_db) / (stress_db - comfort_db))


def room_absorption_factor_to_attenuation_db(
    room_absorption_factor,
    max_attenuation_db=DEFAULT_ROOM_ABSORPTION_MAX_ATTENUATION_DB,
):
    """
    Convert simple room absorption factor into attenuation.

    0 absorption:
        0 dB attenuation

    1 absorption:
        max_attenuation_db
    """
    return _clip01(room_absorption_factor) * _non_negative(max_attenuation_db)


# =============================================================================
# Optional source/link arrays
# =============================================================================

def make_empty_zone_noise_source_array(n_sources):
    return np.zeros((n_sources, N_ZONE_NOISE_SOURCE_COLS), dtype=np.float64)


def make_single_zone_noise_source(
    zone_id,
    noise_db,
    active=1.0,
):
    row = np.zeros((N_ZONE_NOISE_SOURCE_COLS,), dtype=np.float64)

    row[ZONE_NOISE_SOURCE_ZONE_ID] = int(zone_id)
    row[ZONE_NOISE_SOURCE_NOISE_DB] = _non_negative(noise_db)
    row[ZONE_NOISE_SOURCE_ACTIVE] = 1.0 if active else 0.0

    return row


def make_empty_acoustic_link_array(n_links):
    return np.zeros((n_links, N_ACOUSTIC_LINK_COLS), dtype=np.float64)


def make_single_acoustic_link(
    zone_a_id,
    zone_b_id,
    sound_reduction_db=DEFAULT_INTERZONE_SOUND_REDUCTION_DB,
    open_fraction=1.0,
    is_directional=0.0,
):
    row = np.zeros((N_ACOUSTIC_LINK_COLS,), dtype=np.float64)

    row[ACOUSTIC_LINK_ZONE_A_ID] = int(zone_a_id)
    row[ACOUSTIC_LINK_ZONE_B_ID] = int(zone_b_id)
    row[ACOUSTIC_LINK_SOUND_REDUCTION_DB] = _non_negative(sound_reduction_db)
    row[ACOUSTIC_LINK_OPEN_FRACTION] = _clip01(open_fraction)
    row[ACOUSTIC_LINK_IS_DIRECTIONAL] = 1.0 if is_directional else 0.0
    row[ACOUSTIC_LINK_CURRENT_A_TO_B_DB] = 0.0
    row[ACOUSTIC_LINK_CURRENT_B_TO_A_DB] = 0.0

    return row


# =============================================================================
# Weather / thresholds / background
# =============================================================================

def get_outdoor_noise_db_from_weather_state(
    weather_state,
    default_outdoor_noise_db=DEFAULT_OUTDOOR_NOISE_DB,
):
    """
    Robustly read outdoor noise from weather_state if the schema has such a column.

    This avoids errors when schema.py does not yet define outdoor-noise weather.
    """
    if weather_state is None:
        return default_outdoor_noise_db

    candidate_names = [
        "WEATHER_OUTDOOR_NOISE_DB",
        "WEATHER_NOISE_DB",
        "WEATHER_OUTDOOR_SOUND_LEVEL_DB",
    ]

    for name in candidate_names:
        col = _schema_col(name, None)

        if col is None:
            continue

        if int(col) < 0 or int(col) >= weather_state.shape[0]:
            continue

        value = weather_state[int(col)]

        if value > 0.0:
            return _non_negative(value)

    return default_outdoor_noise_db


def get_zone_background_noise_db(
    zone_state,
    zone_static,
    zone_i,
    default_background_noise_db=DEFAULT_BACKGROUND_NOISE_DB,
):
    """
    Read zone background noise if a static column exists; otherwise default.

    Current schema likely does not have a dedicated background-noise column.
    """
    col = _schema_col("ZONE_STATIC_BACKGROUND_NOISE_DB", None)

    if col is not None:
        value = zone_static[zone_i, int(col)]

        if value > 0.0:
            return _non_negative(value)

    return default_background_noise_db


def get_zone_room_absorption_factor(
    zone_static,
    zone_i,
    default_room_absorption_factor=DEFAULT_ROOM_ABSORPTION_FACTOR,
):
    """
    Read room absorption factor if schema has it; otherwise default.
    """
    col = _schema_col("ZONE_STATIC_ROOM_ABSORPTION_FACTOR", None)

    if col is not None:
        return _clip01(zone_static[zone_i, int(col)])

    return _clip01(default_room_absorption_factor)


def get_zone_noise_comfort_db(
    zone_static,
    zone_i,
    default_noise_comfort_db=DEFAULT_NOISE_COMFORT_DB,
):
    """
    Use ZONE_STATIC_MAX_NOISE_DB as comfort/stress threshold helper if present.

    In your current perception logic, max_noise_db is used as the point where
    acoustic discomfort starts becoming meaningful.
    """
    col = _schema_col("ZONE_STATIC_MAX_NOISE_DB", None)

    if col is not None:
        value = zone_static[zone_i, int(col)]

        if value > 0.0:
            return _non_negative(value)

    return default_noise_comfort_db


# =============================================================================
# Action/process noise heuristics
# =============================================================================

def default_noise_for_action_type_db(action_type):
    """
    Fallback action noise when action_static has no ACTION_NOISE_DB column.
    """
    action_type = int(action_type)

    if action_type == schema.ACTION_TYPE_IDLE:
        return 0.0
    if action_type == schema.ACTION_TYPE_SLEEP:
        return 0.0
    if action_type == schema.ACTION_TYPE_EAT:
        return 35.0
    if action_type == schema.ACTION_TYPE_COOK:
        return 48.0
    if action_type == schema.ACTION_TYPE_MAKE_COFFEE:
        return 50.0
    if action_type == schema.ACTION_TYPE_DO_LAUNDRY:
        return 55.0
    if action_type == schema.ACTION_TYPE_SHOWER:
        return 50.0

    if action_type == schema.ACTION_TYPE_OPEN_WINDOW:
        return 25.0
    if action_type == schema.ACTION_TYPE_CLOSE_WINDOW:
        return 25.0
    if action_type == schema.ACTION_TYPE_TURN_LIGHT_ON:
        return 15.0
    if action_type == schema.ACTION_TYPE_TURN_LIGHT_OFF:
        return 15.0

    return 0.0


def default_noise_for_process_type_db(process_type):
    """
    Fallback background-process noise.
    """
    process_type = int(process_type)

    if process_type == schema.PROCESS_TYPE_WASHING_MACHINE:
        return 55.0
    if process_type == schema.PROCESS_TYPE_DISHWASHER:
        return 50.0
    if process_type == schema.PROCESS_TYPE_OVEN:
        return 35.0
    if process_type == schema.PROCESS_TYPE_STOVE:
        return 40.0
    if process_type == schema.PROCESS_TYPE_SHOWER:
        return 50.0
    if process_type == schema.PROCESS_TYPE_COFFEE_MACHINE:
        return 50.0
    if process_type == schema.PROCESS_TYPE_COOKING:
        return 48.0

    return 0.0


def get_action_noise_db(action_static, action_i):
    """
    Read action noise column if it exists, otherwise use action-type heuristic.
    """
    noise_col = _schema_col("ACTION_NOISE_DB", None)

    if noise_col is not None:
        value = action_static[action_i, int(noise_col)]

        if value > 0.0:
            return _non_negative(value)

    action_type = int(action_static[action_i, schema.ACTION_TYPE])

    return default_noise_for_action_type_db(action_type)


def get_process_noise_db(process_state, process_i):
    """
    Read process noise column if it exists, otherwise use process-type heuristic.
    """
    noise_col = _schema_col("PROCESS_NOISE_DB", None)

    if noise_col is not None:
        value = process_state[process_i, int(noise_col)]

        if value > 0.0:
            return _non_negative(value)

    process_type = int(process_state[process_i, schema.PROCESS_TYPE])

    return default_noise_for_process_type_db(process_type)


def find_action_row_from_action_id(action_static, action_id):
    action_id = int(action_id)

    if action_id == schema.MISSING_ID:
        return schema.MISSING_ID

    for action_i in range(action_static.shape[0]):
        if int(action_static[action_i, schema.ACTION_ID]) == action_id:
            return action_i

    return schema.MISSING_ID


# =============================================================================
# Local noise source calculation
# =============================================================================

def calculate_explicit_zone_noise_source_db(
    zone_noise_source_array,
    zone_i,
):
    """
    Combine explicit zone noise sources.
    """
    if zone_noise_source_array is None:
        return 0.0

    energy = 0.0

    for source_i in range(zone_noise_source_array.shape[0]):
        if zone_noise_source_array[source_i, ZONE_NOISE_SOURCE_ACTIVE] <= 0.0:
            continue

        source_zone = int(zone_noise_source_array[source_i, ZONE_NOISE_SOURCE_ZONE_ID])

        if source_zone != int(zone_i):
            continue

        noise_db = zone_noise_source_array[source_i, ZONE_NOISE_SOURCE_NOISE_DB]

        energy += db_to_energy(noise_db)

    return energy_to_db(energy, default_db=0.0)


def calculate_foreground_action_noise_for_zone_db(
    person_state,
    action_static,
    zone_i,
):
    """
    Combine noise from current foreground actions in a zone.
    """
    if person_state is None or action_static is None:
        return 0.0

    energy = 0.0

    for person_i in range(person_state.shape[0]):
        if person_state[person_i, schema.PERSON_IS_HOME] <= 0.0:
            continue

        person_zone = int(person_state[person_i, schema.PERSON_CURRENT_ZONE_ID])

        if person_zone != int(zone_i):
            continue

        action_id = int(person_state[person_i, schema.PERSON_CURRENT_ACTION_ID])
        time_left = person_state[person_i, schema.PERSON_ACTION_TIME_LEFT_MIN]

        if action_id == schema.MISSING_ID or time_left <= 0.0:
            continue

        action_i = find_action_row_from_action_id(
            action_static=action_static,
            action_id=action_id,
        )

        if action_i == schema.MISSING_ID:
            continue

        noise_db = get_action_noise_db(
            action_static=action_static,
            action_i=action_i,
        )

        energy += db_to_energy(noise_db)

    return energy_to_db(energy, default_db=0.0)


def calculate_background_process_noise_for_zone_db(
    process_state,
    zone_i,
):
    """
    Combine noise from active background processes in a zone.
    """
    if process_state is None:
        return 0.0

    energy = 0.0

    for process_i in range(process_state.shape[0]):
        if not _is_active_process(process_state, process_i):
            continue

        process_zone = int(process_state[process_i, schema.PROCESS_ZONE_ID])

        if process_zone != int(zone_i):
            continue

        noise_db = get_process_noise_db(
            process_state=process_state,
            process_i=process_i,
        )

        energy += db_to_energy(noise_db)

    return energy_to_db(energy, default_db=0.0)


def calculate_local_noise_source_for_zone_db(
    zone_state,
    person_state,
    process_state,
    action_static,
    zone_noise_source_array,
    zone_i,
):
    """
    Combine all local active noise sources for one zone.
    """
    explicit_db = calculate_explicit_zone_noise_source_db(
        zone_noise_source_array=zone_noise_source_array,
        zone_i=zone_i,
    )

    foreground_db = calculate_foreground_action_noise_for_zone_db(
        person_state=person_state,
        action_static=action_static,
        zone_i=zone_i,
    )

    process_db = calculate_background_process_noise_for_zone_db(
        process_state=process_state,
        zone_i=zone_i,
    )

    components = np.zeros((3,), dtype=np.float64)
    components[0] = explicit_db
    components[1] = foreground_db
    components[2] = process_db

    return add_noise_levels_db_from_array(
        noise_levels_db=components,
        n_levels=3,
        background_db=None,
        default_db=0.0,
    )


# =============================================================================
# Outdoor noise
# =============================================================================

def calculate_average_window_open_fraction_for_zone(
    system_state,
    system_static,
    zone_i,
):
    total = 0.0
    count = 0

    for system_i in range(system_state.shape[0]):
        if int(system_state[system_i, schema.SYSTEM_ZONE_ID]) != int(zone_i):
            continue

        if system_static[system_i, schema.SYSTEM_STATIC_HAS_WINDOW] <= 0.0:
            continue

        total += _clip01(
            system_state[
                system_i,
                schema.SYSTEM_WINDOW_OPEN_FRACTION,
            ]
        )
        count += 1

    if count <= 0:
        return 0.0

    return _clip01(total / float(count))


def zone_has_window(
    system_state,
    system_static,
    zone_i,
):
    for system_i in range(system_state.shape[0]):
        if int(system_state[system_i, schema.SYSTEM_ZONE_ID]) != int(zone_i):
            continue

        if system_static[system_i, schema.SYSTEM_STATIC_HAS_WINDOW] > 0.0:
            return True

    return False


def calculate_outdoor_noise_attenuation_for_zone_db(
    system_state,
    system_static,
    zone_i,
    closed_window_attenuation_db=DEFAULT_CLOSED_WINDOW_ATTENUATION_DB,
    open_window_attenuation_db=DEFAULT_OPEN_WINDOW_ATTENUATION_DB,
    no_window_attenuation_db=DEFAULT_NO_WINDOW_ATTENUATION_DB,
):
    """
    Estimate envelope/window attenuation.

    If no window:
        use no-window attenuation.

    If window:
        interpolate attenuation between closed and open values.
    """
    if not zone_has_window(
        system_state=system_state,
        system_static=system_static,
        zone_i=zone_i,
    ):
        return _non_negative(no_window_attenuation_db)

    open_fraction = calculate_average_window_open_fraction_for_zone(
        system_state=system_state,
        system_static=system_static,
        zone_i=zone_i,
    )

    closed_att = _non_negative(closed_window_attenuation_db)
    open_att = _non_negative(open_window_attenuation_db)

    return (1.0 - open_fraction) * closed_att + open_fraction * open_att


def calculate_outdoor_noise_contribution_for_zone_db(
    zone_state,
    system_state,
    system_static,
    weather_state,
    zone_i,
    outdoor_noise_db=None,
):
    """
    Calculate outdoor noise transmitted into one zone.
    """
    if _zone_is_outside(zone_state, zone_i):
        return 0.0

    if outdoor_noise_db is None:
        outdoor_noise_db = get_outdoor_noise_db_from_weather_state(
            weather_state=weather_state,
        )

    attenuation_db = calculate_outdoor_noise_attenuation_for_zone_db(
        system_state=system_state,
        system_static=system_static,
        zone_i=zone_i,
    )

    return attenuate_noise_db(
        source_noise_db=outdoor_noise_db,
        attenuation_db=attenuation_db,
        floor_db=0.0,
    )


# =============================================================================
# Interzone acoustic links
# =============================================================================

def calculate_link_received_noise_db(
    source_noise_db,
    sound_reduction_db,
    open_fraction,
):
    """
    Calculate received noise through an acoustic link.

    open_fraction weakens the sound reduction.
    """
    source_noise_db = _non_negative(source_noise_db)

    if source_noise_db <= 0.0:
        return 0.0

    reduction = _non_negative(sound_reduction_db)
    open_fraction = _clip01(open_fraction)

    # Open door/connection reduces effective sound reduction.
    effective_reduction = reduction * (1.0 - open_fraction)

    return attenuate_noise_db(
        source_noise_db=source_noise_db,
        attenuation_db=effective_reduction,
        floor_db=0.0,
    )


def calculate_interzone_noise_contribution_for_zone_db(
    zone_state,
    acoustic_link_array,
    active_source_noise_db_by_zone,
    zone_i,
):
    """
    Combine one-hop interzone noise received by zone_i.

    active_source_noise_db_by_zone should not include receiver background.
    """
    if acoustic_link_array is None:
        return 0.0

    if _zone_is_outside(zone_state, zone_i):
        return 0.0

    n_zones = zone_state.shape[0]
    receiver_zone = int(zone_i)

    total_energy = 0.0

    for link_i in range(acoustic_link_array.shape[0]):
        zone_a = int(acoustic_link_array[link_i, ACOUSTIC_LINK_ZONE_A_ID])
        zone_b = int(acoustic_link_array[link_i, ACOUSTIC_LINK_ZONE_B_ID])

        if zone_a == schema.MISSING_ID or zone_b == schema.MISSING_ID:
            acoustic_link_array[link_i, ACOUSTIC_LINK_CURRENT_A_TO_B_DB] = 0.0
            acoustic_link_array[link_i, ACOUSTIC_LINK_CURRENT_B_TO_A_DB] = 0.0
            continue

        if zone_a < 0 or zone_a >= n_zones:
            continue

        if zone_b < 0 or zone_b >= n_zones:
            continue

        sound_reduction = acoustic_link_array[
            link_i,
            ACOUSTIC_LINK_SOUND_REDUCTION_DB,
        ]
        open_fraction = acoustic_link_array[
            link_i,
            ACOUSTIC_LINK_OPEN_FRACTION,
        ]
        is_directional = acoustic_link_array[
            link_i,
            ACOUSTIC_LINK_IS_DIRECTIONAL,
        ] > 0.0

        source_a = active_source_noise_db_by_zone[zone_a]
        source_b = active_source_noise_db_by_zone[zone_b]

        a_to_b = calculate_link_received_noise_db(
            source_noise_db=source_a,
            sound_reduction_db=sound_reduction,
            open_fraction=open_fraction,
        )
        b_to_a = 0.0

        if not is_directional:
            b_to_a = calculate_link_received_noise_db(
                source_noise_db=source_b,
                sound_reduction_db=sound_reduction,
                open_fraction=open_fraction,
            )

        acoustic_link_array[link_i, ACOUSTIC_LINK_CURRENT_A_TO_B_DB] = a_to_b
        acoustic_link_array[link_i, ACOUSTIC_LINK_CURRENT_B_TO_A_DB] = b_to_a

        if receiver_zone == zone_b:
            total_energy += db_to_energy(a_to_b)

        if receiver_zone == zone_a:
            total_energy += db_to_energy(b_to_a)

    return energy_to_db(total_energy, default_db=0.0)


# =============================================================================
# Main zone/building step
# =============================================================================

def calculate_zone_acoustic_components_db(
    zone_state,
    zone_static,
    system_state,
    system_static,
    weather_state,
    person_state,
    process_state,
    action_static,
    zone_noise_source_array,
    acoustic_link_array,
    active_source_noise_db_by_zone,
    zone_i,
    outdoor_noise_db=None,
):
    """
    Calculate background/local/outdoor/interzone/final indoor noise for one zone.

    Returns:
        background_db
        local_db
        outdoor_db
        interzone_db
        indoor_db
        discomfort
    """
    if _zone_is_outside(zone_state, zone_i):
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    background_db = get_zone_background_noise_db(
        zone_state=zone_state,
        zone_static=zone_static,
        zone_i=zone_i,
    )

    local_db = calculate_local_noise_source_for_zone_db(
        zone_state=zone_state,
        person_state=person_state,
        process_state=process_state,
        action_static=action_static,
        zone_noise_source_array=zone_noise_source_array,
        zone_i=zone_i,
    )

    outdoor_db = calculate_outdoor_noise_contribution_for_zone_db(
        zone_state=zone_state,
        system_state=system_state,
        system_static=system_static,
        weather_state=weather_state,
        zone_i=zone_i,
        outdoor_noise_db=outdoor_noise_db,
    )

    interzone_db = calculate_interzone_noise_contribution_for_zone_db(
        zone_state=zone_state,
        acoustic_link_array=acoustic_link_array,
        active_source_noise_db_by_zone=active_source_noise_db_by_zone,
        zone_i=zone_i,
    )

    absorption = get_zone_room_absorption_factor(
        zone_static=zone_static,
        zone_i=zone_i,
    )
    attenuation_db = room_absorption_factor_to_attenuation_db(absorption)

    local_db = attenuate_noise_db(local_db, attenuation_db, floor_db=0.0)
    outdoor_db = attenuate_noise_db(outdoor_db, attenuation_db, floor_db=0.0)
    interzone_db = attenuate_noise_db(interzone_db, attenuation_db, floor_db=0.0)

    indoor_db = add_noise_components_db(
        background_db=background_db,
        local_db=local_db,
        outdoor_db=outdoor_db,
        interzone_db=interzone_db,
    )

    indoor_db = _clip(
        indoor_db,
        MIN_NOISE_DB,
        MAX_REASONABLE_NOISE_DB,
    )

    comfort_db = get_zone_noise_comfort_db(
        zone_static=zone_static,
        zone_i=zone_i,
    )

    discomfort = normalize_noise_discomfort_input(
        noise_db=indoor_db,
        comfort_db=comfort_db,
        stress_db=DEFAULT_NOISE_STRESS_DB,
    )

    return background_db, local_db, outdoor_db, interzone_db, indoor_db, discomfort


def write_zone_acoustic_result(
    zone_state,
    physics_result,
    zone_i,
    indoor_noise_db,
):
    """
    Write acoustic result to zone_state and physics_result.

    zone_state[:, ZONE_NOISE_DB] stores raw dB.
    Person perception can normalize it later using zone_static max_noise_db.
    """
    zone_state[zone_i, schema.ZONE_NOISE_DB] = indoor_noise_db

    if physics_result is not None:
        physics_result[zone_i, schema.PHYSICS_ZONE_ID] = zone_state[
            zone_i,
            schema.ZONE_ID,
        ]
        physics_result[zone_i, schema.PHYSICS_NOISE_DB] = indoor_noise_db

    return True


def calculate_active_source_noise_by_zone(
    zone_state,
    system_state,
    system_static,
    weather_state,
    person_state,
    process_state,
    action_static,
    zone_noise_source_array,
    outdoor_noise_db=None,
):
    """
    Calculate active source noise per zone for interzone propagation.

    Important:
        Background noise is not propagated.
    """
    n_zones = zone_state.shape[0]
    active = np.zeros((n_zones,), dtype=np.float64)

    for zone_i in range(n_zones):
        if _zone_is_outside(zone_state, zone_i):
            active[zone_i] = 0.0
            continue

        local_db = calculate_local_noise_source_for_zone_db(
            zone_state=zone_state,
            person_state=person_state,
            process_state=process_state,
            action_static=action_static,
            zone_noise_source_array=zone_noise_source_array,
            zone_i=zone_i,
        )

        outdoor_db = calculate_outdoor_noise_contribution_for_zone_db(
            zone_state=zone_state,
            system_state=system_state,
            system_static=system_static,
            weather_state=weather_state,
            zone_i=zone_i,
            outdoor_noise_db=outdoor_noise_db,
        )

        components = np.zeros((2,), dtype=np.float64)
        components[0] = local_db
        components[1] = outdoor_db

        active[zone_i] = add_noise_levels_db_from_array(
            noise_levels_db=components,
            n_levels=2,
            background_db=None,
            default_db=0.0,
        )

    return active


def step_zone_acoustics(
    zone_state,
    zone_static,
    system_state,
    system_static,
    weather_state,
    person_state,
    process_state,
    action_static,
    physics_result,
    zone_i,
    zone_noise_source_array=None,
    acoustic_link_array=None,
    active_source_noise_db_by_zone=None,
    outdoor_noise_db=None,
):
    """
    Update acoustic state for one zone.
    """
    if active_source_noise_db_by_zone is None:
        active_source_noise_db_by_zone = calculate_active_source_noise_by_zone(
            zone_state=zone_state,
            system_state=system_state,
            system_static=system_static,
            weather_state=weather_state,
            person_state=person_state,
            process_state=process_state,
            action_static=action_static,
            zone_noise_source_array=zone_noise_source_array,
            outdoor_noise_db=outdoor_noise_db,
        )

    (
        _background_db,
        _local_db,
        _outdoor_db,
        _interzone_db,
        indoor_db,
        _discomfort,
    ) = calculate_zone_acoustic_components_db(
        zone_state=zone_state,
        zone_static=zone_static,
        system_state=system_state,
        system_static=system_static,
        weather_state=weather_state,
        person_state=person_state,
        process_state=process_state,
        action_static=action_static,
        zone_noise_source_array=zone_noise_source_array,
        acoustic_link_array=acoustic_link_array,
        active_source_noise_db_by_zone=active_source_noise_db_by_zone,
        zone_i=zone_i,
        outdoor_noise_db=outdoor_noise_db,
    )

    write_zone_acoustic_result(
        zone_state=zone_state,
        physics_result=physics_result,
        zone_i=zone_i,
        indoor_noise_db=indoor_db,
    )

    return True


def step_building_acoustics(
    zone_state,
    zone_static,
    system_state,
    system_static,
    weather_state,
    person_state=None,
    process_state=None,
    action_static=None,
    physics_result=None,
    zone_noise_source_array=None,
    acoustic_link_array=None,
    outdoor_noise_db=None,
):
    """
    Phase 11.6 acoustic timestep.

    Mutates:
        zone_state
        physics_result
        acoustic_link_array, if provided

    Returns:
        zone_state, physics_result
    """
    if outdoor_noise_db is None:
        outdoor_noise_db = get_outdoor_noise_db_from_weather_state(
            weather_state=weather_state,
            default_outdoor_noise_db=DEFAULT_OUTDOOR_NOISE_DB,
        )

    active_source_noise_db_by_zone = calculate_active_source_noise_by_zone(
        zone_state=zone_state,
        system_state=system_state,
        system_static=system_static,
        weather_state=weather_state,
        person_state=person_state,
        process_state=process_state,
        action_static=action_static,
        zone_noise_source_array=zone_noise_source_array,
        outdoor_noise_db=outdoor_noise_db,
    )

    for zone_i in range(zone_state.shape[0]):
        step_zone_acoustics(
            zone_state=zone_state,
            zone_static=zone_static,
            system_state=system_state,
            system_static=system_static,
            weather_state=weather_state,
            person_state=person_state,
            process_state=process_state,
            action_static=action_static,
            physics_result=physics_result,
            zone_i=zone_i,
            zone_noise_source_array=zone_noise_source_array,
            acoustic_link_array=acoustic_link_array,
            active_source_noise_db_by_zone=active_source_noise_db_by_zone,
            outdoor_noise_db=outdoor_noise_db,
        )

    return zone_state, physics_result


def run_acoustic_step(
    zone_state,
    zone_static,
    system_state,
    system_static,
    weather_state,
    person_state=None,
    process_state=None,
    action_static=None,
    physics_result=None,
    zone_noise_source_array=None,
    acoustic_link_array=None,
    outdoor_noise_db=None,
):
    """
    Public alias for future physics orchestration.
    """
    return step_building_acoustics(
        zone_state=zone_state,
        zone_static=zone_static,
        system_state=system_state,
        system_static=system_static,
        weather_state=weather_state,
        person_state=person_state,
        process_state=process_state,
        action_static=action_static,
        physics_result=physics_result,
        zone_noise_source_array=zone_noise_source_array,
        acoustic_link_array=acoustic_link_array,
        outdoor_noise_db=outdoor_noise_db,
    )