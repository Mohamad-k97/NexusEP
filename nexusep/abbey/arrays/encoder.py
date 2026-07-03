"""
ABBEY readable-input encoder.

Purpose:
    Convert human-readable ABBEY inputs into SimulationArrayState.

This is the messy boundary layer.

Allowed here:
    - strings
    - dicts
    - simple objects/dataclasses
    - defaults
    - validation
    - readable names

Forbidden in the timestep core:
    - strings
    - nested dicts
    - dataclass logic
    - object methods
    - pandas/dataframes

The output arrays should be numeric and ready for array-core simulation.
"""


import numpy as np

from nexusep.abbey.arrays import schema
from nexusep.abbey.arrays.state import (
    SimulationArraySeries,
    SimulationArrayMappings,
    make_empty_simulation_array_state,
)
from nexusep.abbey.arrays.registry import (
    SimulationIDRegistry,
    validate_state_references,
)


# =============================================================================
# Generic readable-object helpers
# =============================================================================

def _is_dict_like(obj):
    return isinstance(obj, dict)


def _read(obj, key, default=None):
    """
    Read one value from either a dict or a simple object.

    This lets the encoder accept:
        item["name"]
    and:
        item.name
    """
    if obj is None:
        return default

    if _is_dict_like(obj):
        return obj.get(key, default)

    return getattr(obj, key, default)


def _read_any(obj, keys, default=None):
    """
    Read the first available key/attribute from a dict or object.
    """
    for key in keys:
        value = _read(obj, key, None)
        if value is not None:
            return value

    return default


def _as_list(value, name):
    """
    Convert optional readable collections into a list.
    """
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    raise TypeError("%s must be a list or tuple." % name)


def _entity_name(item, prefix, index):
    """
    Get a readable entity name/id.

    Accepted keys:
        id
        name
        uid

    If none exists, generate:
        prefix_index
    """
    value = _read_any(item, ["id", "name", "uid"], None)

    if value is None:
        return "%s_%s" % (prefix, index)

    return str(value)


def _to_float(value, default=0.0):
    if value is None:
        return float(default)

    return float(value)


def _to_int(value, default=0):
    if value is None:
        return int(default)

    return int(value)


def _to_flag(value, default=False):
    """
    Convert a readable boolean-ish value to 0.0 or 1.0.
    """
    if value is None:
        value = default

    if isinstance(value, str):
        value_lower = value.strip().lower()
        if value_lower in ("true", "yes", "y", "1", "on", "open"):
            return 1.0
        if value_lower in ("false", "no", "n", "0", "off", "closed"):
            return 0.0

    if bool(value):
        return 1.0

    return 0.0


def _name_or_missing(value):
    if value is None:
        return None

    if value == "":
        return None

    if value == schema.MISSING_ID:
        return None

    return str(value)


def _encode_optional_name(value, encode_function):
    """
    Encode a readable name, or return MISSING_ID.

    If value is already an integer, it is returned as integer.
    """
    if value is None:
        return schema.MISSING_ID

    if isinstance(value, int):
        return int(value)

    if isinstance(value, float):
        if value == schema.MISSING_ID:
            return schema.MISSING_ID
        if float(value).is_integer():
            return int(value)

    value = _name_or_missing(value)
    if value is None:
        return schema.MISSING_ID

    return int(encode_function(value))


def _first_name(names):
    if names:
        return names[0]

    return None


def _count_by_value(values, target):
    count = 0
    for value in values:
        if value == target:
            count += 1
    return count


def _first_index_by_value(values, target):
    for i, value in enumerate(values):
        if value == target:
            return i

    return schema.MISSING_ID


def _is_numeric_array(array):
    return isinstance(array, np.ndarray) and array.dtype.kind in ("i", "u", "f", "b")


# =============================================================================
# Default readable action library
# =============================================================================

def make_default_readable_actions():
    """
    Minimal default action library.

    These are readable action rows. They become action_static rows.
    """
    return [
        {
            "id": "idle",
            "type": "idle",
            "duration_min": 15.0,
            "requires_home": False,
            "requires_awake": False,
            "is_background": False,
            "can_run_while_away": True,
            "friction": 0.0,
        },
        {
            "id": "sleep",
            "type": "sleep",
            "duration_min": 480.0,
            "requires_home": True,
            "requires_awake": False,
            "is_background": False,
            "can_run_while_away": False,
            "fatigue_effect": -1.0,
            "friction": 0.1,
        },
        {
            "id": "eat",
            "type": "eat",
            "duration_min": 30.0,
            "requires_home": True,
            "requires_awake": True,
            "is_background": False,
            "can_run_while_away": False,
            "hunger_effect": -1.0,
            "power_W": 50.0,
            "heat_gain_W": 50.0,
            "friction": 0.2,
        },
        {
            "id": "open_window",
            "type": "open_window",
            "duration_min": 1.0,
            "requires_home": True,
            "requires_awake": True,
            "is_background": False,
            "can_run_while_away": False,
            "friction": 0.1,
        },
        {
            "id": "close_window",
            "type": "close_window",
            "duration_min": 1.0,
            "requires_home": True,
            "requires_awake": True,
            "is_background": False,
            "can_run_while_away": False,
            "friction": 0.1,
        },
        {
            "id": "turn_light_on",
            "type": "turn_light_on",
            "duration_min": 1.0,
            "requires_home": True,
            "requires_awake": True,
            "is_background": False,
            "can_run_while_away": False,
            "appliance_type": "lights",
            "power_W": 80.0,
            "heat_gain_W": 80.0,
            "friction": 0.05,
        },
        {
            "id": "turn_light_off",
            "type": "turn_light_off",
            "duration_min": 1.0,
            "requires_home": True,
            "requires_awake": True,
            "is_background": False,
            "can_run_while_away": False,
            "appliance_type": "lights",
            "friction": 0.05,
        },
    ]


# =============================================================================
# Input extraction
# =============================================================================

def _extract_readable_sections(readable_input):
    """
    Extract top-level readable sections.

    Expected dict-like keys:
        buildings
        dwellings
        zones
        persons
        systems
        actions
        weather
        weather_series
        time_series

    But the function also accepts object attributes with the same names.
    """
    buildings = _as_list(
        _read(readable_input, "buildings", []),
        "buildings",
    )
    dwellings = _as_list(
        _read(readable_input, "dwellings", []),
        "dwellings",
    )
    zones = _as_list(
        _read(readable_input, "zones", []),
        "zones",
    )
    persons = _as_list(
        _read(readable_input, "persons", []),
        "persons",
    )
    systems = _as_list(
        _read(readable_input, "systems", []),
        "systems",
    )

    actions = _read(readable_input, "actions", None)
    if actions is None:
        actions = _read(readable_input, "action_library", None)
    if actions is None:
        actions = make_default_readable_actions()
    actions = _as_list(actions, "actions")

    return buildings, dwellings, zones, persons, systems, actions


def _ensure_minimum_entities(buildings, dwellings, zones, persons):
    """
    Add minimum entities when a tiny input omits them.

    This makes quick tests and one-dwelling cases easier.
    """
    if not buildings:
        buildings = [
            {
                "id": "building_0",
                "floor_area_m2": 0.0,
                "volume_m3": 0.0,
                "height_m": 0.0,
                "n_floors": 1,
            }
        ]

    if not dwellings:
        dwellings = [
            {
                "id": "dwelling_0",
                "building_id": _entity_name(buildings[0], "building", 0),
                "floor_area_m2": 0.0,
                "volume_m3": 0.0,
            }
        ]

    if not zones:
        zones = [
            {
                "id": "main_room",
                "type": "main_room",
                "dwelling_id": _entity_name(dwellings[0], "dwelling", 0),
                "building_id": _entity_name(buildings[0], "building", 0),
                "floor_area_m2": 30.0,
                "volume_m3": 75.0,
            }
        ]

    if not persons:
        persons = [
            {
                "id": "person_0",
                "dwelling_id": _entity_name(dwellings[0], "dwelling", 0),
                "home_zone_id": _entity_name(zones[0], "zone", 0),
                "sleep_zone_id": _entity_name(zones[0], "zone", 0),
                "current_zone_id": _entity_name(zones[0], "zone", 0),
                "is_home": True,
            }
        ]

    return buildings, dwellings, zones, persons


def build_registry_from_readable_input(readable_input):
    """
    Build a SimulationIDRegistry from readable input.
    """
    buildings, dwellings, zones, persons, systems, actions = _extract_readable_sections(
        readable_input
    )

    buildings, dwellings, zones, persons = _ensure_minimum_entities(
        buildings,
        dwellings,
        zones,
        persons,
    )

    person_names = []
    for i, item in enumerate(persons):
        person_names.append(_entity_name(item, "person", i))

    dwelling_names = []
    for i, item in enumerate(dwellings):
        dwelling_names.append(_entity_name(item, "dwelling", i))

    zone_names = []
    for i, item in enumerate(zones):
        zone_names.append(_entity_name(item, "zone", i))

    building_names = []
    for i, item in enumerate(buildings):
        building_names.append(_entity_name(item, "building", i))

    system_names = []
    for i, item in enumerate(systems):
        system_names.append(_entity_name(item, "system", i))

    action_names = []
    for i, item in enumerate(actions):
        action_names.append(_entity_name(item, "action", i))

    registry = SimulationIDRegistry.from_names(
        person_names=person_names,
        dwelling_names=dwelling_names,
        zone_names=zone_names,
        building_names=building_names,
        system_names=system_names,
        action_names=action_names,
    )
    registry.validate()

    return registry


def make_state_mappings_from_registry(registry):
    """
    Convert a full registry into the lighter mappings object stored on state.
    """
    return SimulationArrayMappings(
        person_name_to_id=registry.person_name_to_id,
        person_id_to_name=registry.person_id_to_name,

        zone_name_to_id=registry.zone_name_to_id,
        zone_id_to_name=registry.zone_id_to_name,

        dwelling_name_to_id=registry.dwelling_name_to_id,
        dwelling_id_to_name=registry.dwelling_id_to_name,

        building_name_to_id=registry.building_name_to_id,
        building_id_to_name=registry.building_id_to_name,

        system_name_to_id=registry.system_name_to_id,
        system_id_to_name=registry.system_id_to_name,

        action_name_to_id=registry.action_name_to_id,
        action_id_to_name=registry.action_id_to_name,
    )


# =============================================================================
# Weather and time compilation
# =============================================================================

def _weather_dict_to_row(weather):
    row = np.zeros((schema.N_WEATHER_STATE_COLS,), dtype=np.float64)

    row[schema.WEATHER_OUTDOOR_TEMPERATURE_C] = _to_float(
        _read_any(weather, ["outdoor_temperature_C", "outdoor_temp_C", "temperature_C"], 20.0),
        20.0,
    )
    row[schema.WEATHER_OUTDOOR_RELATIVE_HUMIDITY] = _to_float(
        _read_any(weather, ["outdoor_relative_humidity", "relative_humidity", "rh"], 0.50),
        0.50,
    )
    row[schema.WEATHER_OUTDOOR_CO2_PPM] = _to_float(
        _read_any(weather, ["outdoor_co2_ppm", "co2_ppm"], 420.0),
        420.0,
    )
    row[schema.WEATHER_GLOBAL_HORIZONTAL_IRRADIANCE_W_M2] = _to_float(
        _read_any(weather, ["ghi_W_m2", "global_horizontal_irradiance_W_m2", "ghi"], 0.0),
        0.0,
    )
    row[schema.WEATHER_DIRECT_NORMAL_IRRADIANCE_W_M2] = _to_float(
        _read_any(weather, ["dni_W_m2", "direct_normal_irradiance_W_m2", "dni"], 0.0),
        0.0,
    )
    row[schema.WEATHER_DIFFUSE_HORIZONTAL_IRRADIANCE_W_M2] = _to_float(
        _read_any(weather, ["dhi_W_m2", "diffuse_horizontal_irradiance_W_m2", "dhi"], 0.0),
        0.0,
    )
    row[schema.WEATHER_WIND_SPEED_M_S] = _to_float(
        _read_any(weather, ["wind_speed_m_s", "wind_speed"], 0.0),
        0.0,
    )
    row[schema.WEATHER_WIND_DIRECTION_DEG] = _to_float(
        _read_any(weather, ["wind_direction_deg", "wind_direction"], 0.0),
        0.0,
    )
    row[schema.WEATHER_SKY_TEMPERATURE_C] = _to_float(
        _read_any(weather, ["sky_temperature_C", "sky_temp_C"], 20.0),
        20.0,
    )
    row[schema.WEATHER_RAIN_FLAG] = _to_flag(
        _read_any(weather, ["rain", "rain_flag", "is_raining"], False),
        False,
    )

    return row


def compile_weather_series(readable_input):
    """
    Compile weather input into a 2D weather series array.

    Accepted:
        weather_series as ndarray with correct columns
        weather_series as list of dicts/objects
        weather as one dict/object
        missing weather -> default one-row weather
    """
    weather_series = _read(readable_input, "weather_series", None)

    if weather_series is not None:
        if isinstance(weather_series, np.ndarray):
            if weather_series.ndim != 2:
                raise ValueError("weather_series ndarray must be 2D.")
            if weather_series.shape[1] != schema.N_WEATHER_STATE_COLS:
                raise ValueError(
                    "weather_series has wrong number of columns. Expected %s, got %s."
                    % (schema.N_WEATHER_STATE_COLS, weather_series.shape[1])
                )
            return weather_series.astype(np.float64)

        weather_series = _as_list(weather_series, "weather_series")
        result = np.zeros(
            (len(weather_series), schema.N_WEATHER_STATE_COLS),
            dtype=np.float64,
        )

        for t, weather_item in enumerate(weather_series):
            result[t, :] = _weather_dict_to_row(weather_item)

        return result

    weather = _read(readable_input, "weather", None)
    row = _weather_dict_to_row(weather)

    return row.reshape((1, schema.N_WEATHER_STATE_COLS))


def compile_time_series(readable_input, n_timesteps):
    """
    Compile or generate a time series.

    For now this stores simple numeric calendar information.
    """
    time_series = _read(readable_input, "time_series", None)

    if time_series is not None:
        if isinstance(time_series, np.ndarray):
            if time_series.ndim != 2:
                raise ValueError("time_series ndarray must be 2D.")
            if time_series.shape[1] != schema.N_TIME_STATE_COLS:
                raise ValueError(
                    "time_series has wrong number of columns. Expected %s, got %s."
                    % (schema.N_TIME_STATE_COLS, time_series.shape[1])
                )
            return time_series.astype(np.float64)

        time_series = _as_list(time_series, "time_series")
        result = np.zeros(
            (len(time_series), schema.N_TIME_STATE_COLS),
            dtype=np.float64,
        )

        for t, item in enumerate(time_series):
            result[t, schema.TIME_STEP_INDEX] = _to_float(
                _read_any(item, ["time_step_index", "step", "t"], t),
                t,
            )
            result[t, schema.TIME_ELAPSED_MIN] = _to_float(
                _read_any(item, ["elapsed_min", "time_elapsed_min"], 0.0),
                0.0,
            )
            result[t, schema.TIME_MINUTE_OF_DAY] = _to_float(
                _read_any(item, ["minute_of_day"], 0.0),
                0.0,
            )
            result[t, schema.TIME_HOUR_OF_DAY] = _to_float(
                _read_any(item, ["hour_of_day"], 0.0),
                0.0,
            )
            result[t, schema.TIME_DAY_INDEX] = _to_float(
                _read_any(item, ["day_index"], 0),
                0,
            )
            result[t, schema.TIME_DAY_OF_WEEK] = _to_float(
                _read_any(item, ["day_of_week"], 0),
                0,
            )
            result[t, schema.TIME_MONTH] = _to_float(
                _read_any(item, ["month"], 1),
                1,
            )
            result[t, schema.TIME_IS_WEEKEND] = _to_flag(
                _read_any(item, ["is_weekend"], False),
                False,
            )

        return result

    dt_minutes = _to_float(_read(readable_input, "dt_minutes", 15.0), 15.0)
    start_minute_of_day = _to_float(
        _read(readable_input, "start_minute_of_day", 0.0),
        0.0,
    )
    start_day_of_week = _to_int(
        _read(readable_input, "start_day_of_week", 0),
        0,
    )
    start_month = _to_int(
        _read(readable_input, "start_month", 1),
        1,
    )

    result = np.zeros(
        (n_timesteps, schema.N_TIME_STATE_COLS),
        dtype=np.float64,
    )

    for t in range(n_timesteps):
        elapsed_min = t * dt_minutes
        absolute_minute = start_minute_of_day + elapsed_min

        day_index = int(absolute_minute // 1440.0)
        minute_of_day = absolute_minute % 1440.0
        hour_of_day = int(minute_of_day // 60.0)
        day_of_week = (start_day_of_week + day_index) % 7
        is_weekend = day_of_week in (5, 6)

        result[t, schema.TIME_STEP_INDEX] = t
        result[t, schema.TIME_ELAPSED_MIN] = elapsed_min
        result[t, schema.TIME_MINUTE_OF_DAY] = minute_of_day
        result[t, schema.TIME_HOUR_OF_DAY] = hour_of_day
        result[t, schema.TIME_DAY_INDEX] = day_index
        result[t, schema.TIME_DAY_OF_WEEK] = day_of_week
        result[t, schema.TIME_MONTH] = start_month
        result[t, schema.TIME_IS_WEEKEND] = _to_flag(is_weekend)

    return result


# =============================================================================
# Main compiler
# =============================================================================

def compile_simulation_to_arrays(
    readable_input,
    registry=None,
    dtype=np.float64,
    include_metadata=True,
):
    """
    Compile readable ABBEY input into SimulationArrayState.

    Parameters
    ----------
    readable_input:
        Dict-like or object-like simulation input.

    registry:
        Optional SimulationIDRegistry. If not provided, one is built from
        readable_input.

    dtype:
        Numeric dtype for arrays. Default float64.

    include_metadata:
        If True, stores registry and basic compile metadata outside the core.

    Returns
    -------
    SimulationArrayState
    """
    buildings, dwellings, zones, persons, systems, actions = _extract_readable_sections(
        readable_input
    )

    buildings, dwellings, zones, persons = _ensure_minimum_entities(
        buildings,
        dwellings,
        zones,
        persons,
    )

    if registry is None:
        registry = build_registry_from_readable_input(
            {
                "buildings": buildings,
                "dwellings": dwellings,
                "zones": zones,
                "persons": persons,
                "systems": systems,
                "actions": actions,
            }
        )

    registry.validate()

    weather_series = compile_weather_series(readable_input)
    requested_n_timesteps = _read(readable_input, "n_timesteps", None)

    if requested_n_timesteps is None:
        n_timesteps = weather_series.shape[0]
    else:
        n_timesteps = _to_int(requested_n_timesteps, weather_series.shape[0])

    time_series = compile_time_series(readable_input, n_timesteps)

    n_persons = len(persons)
    n_zones = len(zones)
    n_dwellings = len(dwellings)
    n_buildings = len(buildings)
    n_systems = len(systems)
    n_actions = len(actions)

    n_processes = _to_int(
        _read_any(readable_input, ["n_processes", "max_processes"], max(1, n_persons * 2)),
        max(1, n_persons * 2),
    )

    state = make_empty_simulation_array_state(
        n_persons=n_persons,
        n_zones=n_zones,
        n_dwellings=n_dwellings,
        n_buildings=n_buildings,
        n_systems=n_systems,
        n_actions=n_actions,
        n_processes=n_processes,
        dtype=dtype,
        metadata=None,
    )

    _fill_building_arrays(state, buildings, registry)
    _fill_dwelling_arrays(state, dwellings, zones, persons, registry)
    _fill_zone_arrays(state, zones, registry)
    _fill_person_arrays(state, persons, registry)
    _fill_system_arrays(state, systems, registry)
    _fill_action_arrays(state, actions, registry)
    _fill_process_arrays(state, registry)

    state.dynamic.weather_state[:] = weather_series[0, :]
    state.dynamic.time_state[:] = time_series[0, :]

    state.series = SimulationArraySeries(
        weather_series=weather_series,
        time_series=time_series,
    )
    state.mappings = make_state_mappings_from_registry(registry)

    if include_metadata:
        person_schedule_array = _make_person_schedule_array(state)
        state.metadata = {
            "registry": registry,
            "dt_minutes": _to_float(_read(readable_input, "dt_minutes", 15.0), 15.0),
            "n_timesteps": n_timesteps,
            "person_schedule_array": person_schedule_array,
        }
    else:
        state.metadata = None

    state.validate()
    validate_state_references(state)

    return state


# =============================================================================
# Fill building arrays
# =============================================================================

def _fill_building_arrays(state, buildings, registry):
    building_state = state.dynamic.building_state
    building_static = state.static.building_static

    for i, building in enumerate(buildings):
        name = _entity_name(building, "building", i)
        building_id = registry.building_id(name)

        building_state[i, schema.BUILDING_ID] = building_id
        building_state[i, schema.BUILDING_OCCUPANT_COUNT] = 0.0
        building_state[i, schema.BUILDING_IS_OCCUPIED] = 0.0
        building_state[i, schema.BUILDING_TOTAL_POWER_W] = 0.0
        building_state[i, schema.BUILDING_TOTAL_HEATING_DEMAND_W] = 0.0
        building_state[i, schema.BUILDING_TOTAL_COOLING_DEMAND_W] = 0.0
        building_state[i, schema.BUILDING_TOTAL_ELECTRICITY_DEMAND_W] = 0.0

        building_static[i, schema.BUILDING_STATIC_ID] = building_id
        building_static[i, schema.BUILDING_STATIC_FIRST_DWELLING_ID] = schema.MISSING_ID
        building_static[i, schema.BUILDING_STATIC_N_DWELLINGS] = 0
        building_static[i, schema.BUILDING_STATIC_FIRST_ZONE_ID] = schema.MISSING_ID
        building_static[i, schema.BUILDING_STATIC_N_ZONES] = 0

        building_static[i, schema.BUILDING_STATIC_FLOOR_AREA_M2] = _to_float(
            _read_any(building, ["floor_area_m2", "area_m2"], 0.0),
            0.0,
        )
        building_static[i, schema.BUILDING_STATIC_VOLUME_M3] = _to_float(
            _read_any(building, ["volume_m3"], 0.0),
            0.0,
        )
        building_static[i, schema.BUILDING_STATIC_HEIGHT_M] = _to_float(
            _read_any(building, ["height_m"], 0.0),
            0.0,
        )
        building_static[i, schema.BUILDING_STATIC_N_FLOORS] = _to_float(
            _read_any(building, ["n_floors", "floors"], 1.0),
            1.0,
        )

    return True


# =============================================================================
# Fill dwelling arrays
# =============================================================================

def _fill_dwelling_arrays(state, dwellings, zones, persons, registry):
    dwelling_state = state.dynamic.dwelling_state
    dwelling_static = state.static.dwelling_static

    zone_dwelling_ids = []
    for i, zone in enumerate(zones):
        dwelling_name = _read_any(zone, ["dwelling_id", "dwelling", "dwelling_name"], None)
        if dwelling_name is None:
            zone_dwelling_ids.append(schema.MISSING_ID)
        else:
            zone_dwelling_ids.append(registry.dwelling_id(str(dwelling_name)))

    person_dwelling_ids = []
    for i, person in enumerate(persons):
        dwelling_name = _read_any(person, ["dwelling_id", "dwelling", "dwelling_name"], None)
        if dwelling_name is None:
            dwelling_name = _first_name(list(registry.dwelling_name_to_id.keys()))
        person_dwelling_ids.append(registry.dwelling_id(str(dwelling_name)))

    for i, dwelling in enumerate(dwellings):
        name = _entity_name(dwelling, "dwelling", i)
        dwelling_id = registry.dwelling_id(name)

        building_name = _read_any(
            dwelling,
            ["building_id", "building", "building_name"],
            _first_name(list(registry.building_name_to_id.keys())),
        )
        building_id = registry.building_id(str(building_name))

        first_zone_id = _first_index_by_value(zone_dwelling_ids, dwelling_id)
        n_zones = _count_by_value(zone_dwelling_ids, dwelling_id)

        first_person_id = _first_index_by_value(person_dwelling_ids, dwelling_id)
        n_persons = _count_by_value(person_dwelling_ids, dwelling_id)

        dwelling_state[i, schema.DWELLING_ID] = dwelling_id
        dwelling_state[i, schema.DWELLING_BUILDING_ID] = building_id
        dwelling_state[i, schema.DWELLING_OCCUPANT_COUNT] = 0.0
        dwelling_state[i, schema.DWELLING_IS_OCCUPIED] = 0.0
        dwelling_state[i, schema.DWELLING_TOTAL_POWER_W] = 0.0
        dwelling_state[i, schema.DWELLING_TOTAL_HEAT_GAIN_W] = 0.0
        dwelling_state[i, schema.DWELLING_TOTAL_CO2_GAIN_KG_S] = 0.0
        dwelling_state[i, schema.DWELLING_TOTAL_MOISTURE_GAIN_KG_S] = 0.0
        dwelling_state[i, schema.DWELLING_TOTAL_HEATING_DEMAND_W] = 0.0
        dwelling_state[i, schema.DWELLING_TOTAL_COOLING_DEMAND_W] = 0.0
        dwelling_state[i, schema.DWELLING_TOTAL_ELECTRICITY_DEMAND_W] = 0.0

        dwelling_static[i, schema.DWELLING_STATIC_ID] = dwelling_id
        dwelling_static[i, schema.DWELLING_STATIC_BUILDING_ID] = building_id
        dwelling_static[i, schema.DWELLING_STATIC_FIRST_ZONE_ID] = first_zone_id
        dwelling_static[i, schema.DWELLING_STATIC_N_ZONES] = n_zones
        dwelling_static[i, schema.DWELLING_STATIC_FIRST_PERSON_ID] = first_person_id
        dwelling_static[i, schema.DWELLING_STATIC_N_PERSONS] = n_persons
        dwelling_static[i, schema.DWELLING_STATIC_FLOOR_AREA_M2] = _to_float(
            _read_any(dwelling, ["floor_area_m2", "area_m2"], 0.0),
            0.0,
        )
        dwelling_static[i, schema.DWELLING_STATIC_VOLUME_M3] = _to_float(
            _read_any(dwelling, ["volume_m3"], 0.0),
            0.0,
        )

    # Update building first/count references.
    building_ids_for_dwellings = []
    for i in range(dwelling_static.shape[0]):
        building_ids_for_dwellings.append(
            int(dwelling_static[i, schema.DWELLING_STATIC_BUILDING_ID])
        )

    zone_building_ids = []
    for zone in zones:
        building_name = _read_any(zone, ["building_id", "building", "building_name"], None)
        if building_name is None:
            zone_building_ids.append(schema.MISSING_ID)
        else:
            zone_building_ids.append(registry.building_id(str(building_name)))

    for building_name, building_id in registry.building_name_to_id.items():
        first_dwelling_id = _first_index_by_value(building_ids_for_dwellings, building_id)
        n_dwellings = _count_by_value(building_ids_for_dwellings, building_id)

        first_zone_id = _first_index_by_value(zone_building_ids, building_id)
        n_zones = _count_by_value(zone_building_ids, building_id)

        state.static.building_static[
            building_id,
            schema.BUILDING_STATIC_FIRST_DWELLING_ID,
        ] = first_dwelling_id
        state.static.building_static[
            building_id,
            schema.BUILDING_STATIC_N_DWELLINGS,
        ] = n_dwellings
        state.static.building_static[
            building_id,
            schema.BUILDING_STATIC_FIRST_ZONE_ID,
        ] = first_zone_id
        state.static.building_static[
            building_id,
            schema.BUILDING_STATIC_N_ZONES,
        ] = n_zones

    return True


# =============================================================================
# Fill zone arrays
# =============================================================================

def _fill_zone_arrays(state, zones, registry):
    zone_state = state.dynamic.zone_state
    zone_static = state.static.zone_static

    default_dwelling_name = _first_name(list(registry.dwelling_name_to_id.keys()))
    default_building_name = _first_name(list(registry.building_name_to_id.keys()))

    for i, zone in enumerate(zones):
        name = _entity_name(zone, "zone", i)
        zone_id = registry.zone_id(name)

        zone_type_name = _read_any(zone, ["type", "zone_type", "space_type"], "main_room")
        zone_type_id = registry.zone_type_id(str(zone_type_name))

        dwelling_name = _read_any(
            zone,
            ["dwelling_id", "dwelling", "dwelling_name"],
            default_dwelling_name,
        )
        building_name = _read_any(
            zone,
            ["building_id", "building", "building_name"],
            default_building_name,
        )

        if zone_type_id == schema.ZONE_TYPE_OUTSIDE:
            dwelling_id = schema.MISSING_ID
            building_id = schema.MISSING_ID
        else:
            dwelling_id = _encode_optional_name(dwelling_name, registry.dwelling_id)
            building_id = _encode_optional_name(building_name, registry.building_id)

        zone_state[i, schema.ZONE_ID] = zone_id
        zone_state[i, schema.ZONE_DWELLING_ID] = dwelling_id
        zone_state[i, schema.ZONE_BUILDING_ID] = building_id
        zone_state[i, schema.ZONE_TYPE] = zone_type_id

        zone_state[i, schema.ZONE_AIR_TEMPERATURE_C] = _to_float(
            _read_any(zone, ["air_temperature_C", "temperature_C", "initial_temperature_C"], 20.0),
            20.0,
        )
        zone_state[i, schema.ZONE_MEAN_RADIANT_TEMPERATURE_C] = _to_float(
            _read_any(zone, ["mean_radiant_temperature_C", "mrt_C"], 20.0),
            20.0,
        )
        zone_state[i, schema.ZONE_RELATIVE_HUMIDITY] = _to_float(
            _read_any(zone, ["relative_humidity", "rh"], 0.50),
            0.50,
        )
        zone_state[i, schema.ZONE_CO2_PPM] = _to_float(
            _read_any(zone, ["co2_ppm", "initial_co2_ppm"], 600.0),
            600.0,
        )
        zone_state[i, schema.ZONE_ILLUMINANCE_LUX] = _to_float(
            _read_any(zone, ["illuminance_lux", "lux"], 300.0),
            300.0,
        )
        zone_state[i, schema.ZONE_NOISE_DB] = _to_float(
            _read_any(zone, ["noise_db", "noise_dB"], 35.0),
            35.0,
        )

        zone_state[i, schema.ZONE_OCCUPANT_COUNT] = 0.0
        zone_state[i, schema.ZONE_IS_OCCUPIED] = 0.0

        zone_state[i, schema.ZONE_INTERNAL_HEAT_GAIN_W] = 0.0
        zone_state[i, schema.ZONE_SOLAR_GAIN_W] = _to_float(
            _read_any(zone, ["solar_gain_W"], 0.0),
            0.0,
        )
        zone_state[i, schema.ZONE_LIGHTING_GAIN_W] = 0.0
        zone_state[i, schema.ZONE_APPLIANCE_GAIN_W] = 0.0
        zone_state[i, schema.ZONE_PEOPLE_GAIN_W] = 0.0
        zone_state[i, schema.ZONE_CO2_GAIN_KG_S] = 0.0
        zone_state[i, schema.ZONE_MOISTURE_GAIN_KG_S] = 0.0

        zone_state[i, schema.ZONE_OUTDOOR_AIRFLOW_M3_S] = _to_float(
            _read_any(zone, ["outdoor_airflow_m3_s"], 0.0),
            0.0,
        )
        zone_state[i, schema.ZONE_INTERZONE_AIRFLOW_M3_S] = _to_float(
            _read_any(zone, ["interzone_airflow_m3_s"], 0.0),
            0.0,
        )
        zone_state[i, schema.ZONE_INFILTRATION_AIRFLOW_M3_S] = _to_float(
            _read_any(zone, ["infiltration_airflow_m3_s"], 0.0),
            0.0,
        )

        zone_static[i, schema.ZONE_STATIC_ID] = zone_id
        zone_static[i, schema.ZONE_STATIC_DWELLING_ID] = dwelling_id
        zone_static[i, schema.ZONE_STATIC_BUILDING_ID] = building_id
        zone_static[i, schema.ZONE_STATIC_TYPE] = zone_type_id

        zone_static[i, schema.ZONE_STATIC_FLOOR_AREA_M2] = _to_float(
            _read_any(zone, ["floor_area_m2", "area_m2"], 0.0),
            0.0,
        )
        zone_static[i, schema.ZONE_STATIC_VOLUME_M3] = _to_float(
            _read_any(zone, ["volume_m3"], 0.0),
            0.0,
        )
        zone_static[i, schema.ZONE_STATIC_HEIGHT_M] = _to_float(
            _read_any(zone, ["height_m"], 2.7),
            2.7,
        )
        zone_static[i, schema.ZONE_STATIC_HEAT_CAPACITY_J_K] = _to_float(
            _read_any(zone, ["heat_capacity_J_K"], 1.0e6),
            1.0e6,
        )
        zone_static[i, schema.ZONE_STATIC_UA_ENVELOPE_W_K] = _to_float(
            _read_any(zone, ["ua_envelope_W_K", "UA_envelope_W_K"], 100.0),
            100.0,
        )
        zone_static[i, schema.ZONE_STATIC_UA_INTERNAL_W_K] = _to_float(
            _read_any(zone, ["ua_internal_W_K", "UA_internal_W_K"], 20.0),
            20.0,
        )

        zone_static[i, schema.ZONE_STATIC_MIN_COMFORT_TEMP_C] = _to_float(
            _read_any(zone, ["min_comfort_temp_C"], 20.0),
            20.0,
        )
        zone_static[i, schema.ZONE_STATIC_MAX_COMFORT_TEMP_C] = _to_float(
            _read_any(zone, ["max_comfort_temp_C"], 26.0),
            26.0,
        )
        zone_static[i, schema.ZONE_STATIC_MIN_ILLUMINANCE_LUX] = _to_float(
            _read_any(zone, ["min_illuminance_lux"], 150.0),
            150.0,
        )
        zone_static[i, schema.ZONE_STATIC_MAX_CO2_PPM] = _to_float(
            _read_any(zone, ["max_co2_ppm"], 1200.0),
            1200.0,
        )
        zone_static[i, schema.ZONE_STATIC_MAX_NOISE_DB] = _to_float(
            _read_any(zone, ["max_noise_db", "max_noise_dB"], 55.0),
            55.0,
        )

    return True


# =============================================================================
# Fill person arrays
# =============================================================================

def _fill_person_arrays(state, persons, registry):
    person_state = state.dynamic.person_state
    person_static = state.static.person_static

    default_dwelling_name = _first_name(list(registry.dwelling_name_to_id.keys()))
    default_zone_name = _first_name(list(registry.zone_name_to_id.keys()))

    for i, person in enumerate(persons):
        name = _entity_name(person, "person", i)
        person_id = registry.person_id(name)

        dwelling_name = _read_any(
            person,
            ["dwelling_id", "dwelling", "dwelling_name"],
            default_dwelling_name,
        )
        dwelling_id = registry.dwelling_id(str(dwelling_name))

        home_zone_name = _read_any(
            person,
            ["home_zone_id", "home_zone", "default_zone_id", "default_zone"],
            default_zone_name,
        )
        sleep_zone_name = _read_any(
            person,
            ["sleep_zone_id", "sleep_zone", "bedroom_id", "bedroom"],
            home_zone_name,
        )
        work_zone_name = _read_any(
            person,
            ["work_zone_id", "work_zone"],
            None,
        )
        current_zone_name = _read_any(
            person,
            ["current_zone_id", "current_zone", "zone_id", "zone"],
            home_zone_name,
        )

        home_zone_id = _encode_optional_name(home_zone_name, registry.zone_id)
        sleep_zone_id = _encode_optional_name(sleep_zone_name, registry.zone_id)
        work_zone_id = _encode_optional_name(work_zone_name, registry.zone_id)
        current_zone_id = _encode_optional_name(current_zone_name, registry.zone_id)

        is_home = _to_flag(_read(person, "is_home", True), True)

        occupancy_name = _read(person, "occupancy_state", None)
        if occupancy_name is None:
            if is_home:
                occupancy_name = "home_awake"
            else:
                occupancy_name = "away"

        occupancy_id = registry.occupancy_state_id(str(occupancy_name))

        current_action_type_name = _read_any(
            person,
            ["current_action_type", "action_type"],
            "none",
        )
        current_action_name = _read_any(
            person,
            ["current_action_id", "current_action", "action"],
            None,
        )

        person_state[i, schema.PERSON_ID] = person_id
        person_state[i, schema.PERSON_DWELLING_ID] = dwelling_id
        person_state[i, schema.PERSON_CURRENT_ZONE_ID] = current_zone_id
        person_state[i, schema.PERSON_PREVIOUS_ZONE_ID] = schema.MISSING_ID
        person_state[i, schema.PERSON_IS_HOME] = is_home
        person_state[i, schema.PERSON_OCCUPANCY_STATE] = occupancy_id

        person_state[i, schema.PERSON_HUNGER] = _to_float(
            _read(person, "hunger", 0.3),
            0.3,
        )
        person_state[i, schema.PERSON_FATIGUE] = _to_float(
            _read(person, "fatigue", 0.3),
            0.3,
        )
        person_state[i, schema.PERSON_DIRTY_CLOTHES] = _to_float(
            _read(person, "dirty_clothes", 0.0),
            0.0,
        )
        person_state[i, schema.PERSON_SICKNESS] = _to_float(
            _read(person, "sickness", 0.0),
            0.0,
        )
        person_state[i, schema.PERSON_LAZINESS] = _to_float(
            _read(person, "laziness", 0.2),
            0.2,
        )

        person_state[i, schema.PERSON_THERMAL_STRESS] = 0.0
        person_state[i, schema.PERSON_AIR_QUALITY_STRESS] = 0.0
        person_state[i, schema.PERSON_VISUAL_STRESS] = 0.0
        person_state[i, schema.PERSON_ACOUSTIC_STRESS] = 0.0
        person_state[i, schema.PERSON_TOTAL_DISCOMFORT] = 0.0

        person_state[i, schema.PERSON_CURRENT_ACTION_TYPE] = registry.action_type_id(
            str(current_action_type_name)
        )
        person_state[i, schema.PERSON_CURRENT_ACTION_ID] = _encode_optional_name(
            current_action_name,
            registry.action_id,
        )
        person_state[i, schema.PERSON_ACTION_TARGET_ZONE_ID] = schema.MISSING_ID
        person_state[i, schema.PERSON_ACTION_TARGET_SYSTEM_ID] = schema.MISSING_ID
        person_state[i, schema.PERSON_ACTION_TIME_LEFT_MIN] = _to_float(
            _read(person, "action_time_left_min", 0.0),
            0.0,
        )

        person_state[i, schema.PERSON_CURRENT_POWER_W] = 0.0
        person_state[i, schema.PERSON_CURRENT_HEAT_GAIN_W] = 0.0
        person_state[i, schema.PERSON_CURRENT_CO2_GAIN_KG_S] = 0.0
        person_state[i, schema.PERSON_CURRENT_MOISTURE_GAIN_KG_S] = 0.0

        person_static[i, schema.PERSON_STATIC_ID] = person_id
        person_static[i, schema.PERSON_STATIC_DWELLING_ID] = dwelling_id
        person_static[i, schema.PERSON_STATIC_HOME_ZONE_ID] = home_zone_id
        person_static[i, schema.PERSON_STATIC_SLEEP_ZONE_ID] = sleep_zone_id
        person_static[i, schema.PERSON_STATIC_WORK_ZONE_ID] = work_zone_id

        person_static[i, schema.PERSON_STATIC_COLD_SENSITIVITY] = _to_float(
            _read(person, "cold_sensitivity", 1.0),
            1.0,
        )
        person_static[i, schema.PERSON_STATIC_HEAT_SENSITIVITY] = _to_float(
            _read(person, "heat_sensitivity", 1.0),
            1.0,
        )
        person_static[i, schema.PERSON_STATIC_CO2_SENSITIVITY] = _to_float(
            _read(person, "co2_sensitivity", 1.0),
            1.0,
        )
        person_static[i, schema.PERSON_STATIC_LIGHT_SENSITIVITY] = _to_float(
            _read(person, "light_sensitivity", 1.0),
            1.0,
        )
        person_static[i, schema.PERSON_STATIC_NOISE_SENSITIVITY] = _to_float(
            _read(person, "noise_sensitivity", 1.0),
            1.0,
        )
        person_static[i, schema.PERSON_STATIC_ACTION_FRICTION] = _to_float(
            _read(person, "action_friction", 1.0),
            1.0,
        )

        person_static[i, schema.PERSON_STATIC_METABOLIC_HEAT_W] = _to_float(
            _read(person, "metabolic_heat_W", 80.0),
            80.0,
        )
        person_static[i, schema.PERSON_STATIC_CO2_GAIN_KG_S] = _to_float(
            _read(person, "co2_gain_kg_s", 0.000005),
            0.000005,
        )
        person_static[i, schema.PERSON_STATIC_MOISTURE_GAIN_KG_S] = _to_float(
            _read(person, "moisture_gain_kg_s", 0.00003),
            0.00003,
        )

        has_job = _to_flag(_read(person, "has_job", False), False)
        person_static[i, schema.PERSON_STATIC_HAS_JOB] = has_job
        person_static[i, schema.PERSON_STATIC_USUAL_WAKE_MINUTE] = _to_float(
            _read(person, "usual_wake_minute", 7.0 * 60.0),
            7.0 * 60.0,
        )
        person_static[i, schema.PERSON_STATIC_USUAL_SLEEP_MINUTE] = _to_float(
            _read(person, "usual_sleep_minute", 23.0 * 60.0),
            23.0 * 60.0,
        )
        person_static[i, schema.PERSON_STATIC_WORK_START_MINUTE] = _to_float(
            _read(person, "work_start_minute", 9.0 * 60.0),
            9.0 * 60.0,
        )
        person_static[i, schema.PERSON_STATIC_WORK_END_MINUTE] = _to_float(
            _read(person, "work_end_minute", 17.0 * 60.0),
            17.0 * 60.0,
        )

    _update_occupancy_counts(state)

    return True


# =============================================================================
# Fill system arrays
# =============================================================================

def _fill_system_arrays(state, systems, registry):
    system_state = state.dynamic.system_state
    system_static = state.static.system_static

    default_dwelling_name = _first_name(list(registry.dwelling_name_to_id.keys()))
    default_zone_name = _first_name(list(registry.zone_name_to_id.keys()))

    for i, system in enumerate(systems):
        name = _entity_name(system, "system", i)
        system_id = registry.system_id(name)

        dwelling_name = _read_any(
            system,
            ["dwelling_id", "dwelling", "dwelling_name"],
            default_dwelling_name,
        )
        zone_name = _read_any(
            system,
            ["zone_id", "zone", "zone_name"],
            default_zone_name,
        )

        dwelling_id = registry.dwelling_id(str(dwelling_name))
        zone_id = registry.zone_id(str(zone_name))

        hvac_mode_name = _read_any(system, ["hvac_mode", "mode"], "off")
        ventilation_mode_name = _read_any(
            system,
            ["ventilation_mode", "vent_mode"],
            "off",
        )

        system_state[i, schema.SYSTEM_ID] = system_id
        system_state[i, schema.SYSTEM_DWELLING_ID] = dwelling_id
        system_state[i, schema.SYSTEM_ZONE_ID] = zone_id

        system_state[i, schema.SYSTEM_HVAC_MODE] = registry.hvac_mode_id(
            str(hvac_mode_name)
        )
        system_state[i, schema.SYSTEM_HEATING_SETPOINT_C] = _to_float(
            _read(system, "heating_setpoint_C", 20.0),
            20.0,
        )
        system_state[i, schema.SYSTEM_COOLING_SETPOINT_C] = _to_float(
            _read(system, "cooling_setpoint_C", 26.0),
            26.0,
        )
        system_state[i, schema.SYSTEM_HEATING_POWER_W] = 0.0
        system_state[i, schema.SYSTEM_COOLING_POWER_W] = 0.0

        window_open_fraction = _to_float(
            _read(system, "window_open_fraction", 0.0),
            0.0,
        )
        system_state[i, schema.SYSTEM_WINDOW_OPEN_FRACTION] = window_open_fraction
        system_state[i, schema.SYSTEM_WINDOW_STATE] = (
            schema.WINDOW_STATE_OPEN if window_open_fraction > 0.0 else schema.WINDOW_STATE_CLOSED
        )

        light_on = _to_flag(_read(system, "light_on", False), False)
        system_state[i, schema.SYSTEM_LIGHT_STATE] = (
            schema.LIGHT_STATE_ON if light_on else schema.LIGHT_STATE_OFF
        )
        system_state[i, schema.SYSTEM_LIGHTING_POWER_W] = _to_float(
            _read(system, "lighting_power_W", 0.0),
            0.0,
        )

        blind_closed_fraction = _to_float(
            _read(system, "blind_closed_fraction", 0.0),
            0.0,
        )
        system_state[i, schema.SYSTEM_BLIND_CLOSED_FRACTION] = blind_closed_fraction
        if blind_closed_fraction <= 0.0:
            blind_state = schema.BLIND_STATE_OPEN
        elif blind_closed_fraction >= 1.0:
            blind_state = schema.BLIND_STATE_CLOSED
        else:
            blind_state = schema.BLIND_STATE_PARTIAL
        system_state[i, schema.SYSTEM_BLIND_STATE] = blind_state

        system_state[i, schema.SYSTEM_VENTILATION_MODE] = registry.ventilation_mode_id(
            str(ventilation_mode_name)
        )
        system_state[i, schema.SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S] = _to_float(
            _read(system, "mechanical_ventilation_flow_m3_s", 0.0),
            0.0,
        )

        system_static[i, schema.SYSTEM_STATIC_ID] = system_id
        system_static[i, schema.SYSTEM_STATIC_DWELLING_ID] = dwelling_id
        system_static[i, schema.SYSTEM_STATIC_ZONE_ID] = zone_id

        system_static[i, schema.SYSTEM_STATIC_HAS_HEATING] = _to_flag(
            _read(system, "has_heating", True),
            True,
        )
        system_static[i, schema.SYSTEM_STATIC_HAS_COOLING] = _to_flag(
            _read(system, "has_cooling", False),
            False,
        )
        system_static[i, schema.SYSTEM_STATIC_HAS_WINDOW] = _to_flag(
            _read(system, "has_window", True),
            True,
        )
        system_static[i, schema.SYSTEM_STATIC_HAS_LIGHTS] = _to_flag(
            _read(system, "has_lights", True),
            True,
        )
        system_static[i, schema.SYSTEM_STATIC_HAS_BLINDS] = _to_flag(
            _read(system, "has_blinds", False),
            False,
        )
        system_static[i, schema.SYSTEM_STATIC_HAS_MECH_VENTILATION] = _to_flag(
            _read(system, "has_mech_ventilation", False),
            False,
        )

        system_static[i, schema.SYSTEM_STATIC_MAX_HEATING_POWER_W] = _to_float(
            _read(system, "max_heating_power_W", 3000.0),
            3000.0,
        )
        system_static[i, schema.SYSTEM_STATIC_MAX_COOLING_POWER_W] = _to_float(
            _read(system, "max_cooling_power_W", 3000.0),
            3000.0,
        )
        system_static[i, schema.SYSTEM_STATIC_MAX_LIGHTING_POWER_W] = _to_float(
            _read(system, "max_lighting_power_W", 200.0),
            200.0,
        )
        system_static[i, schema.SYSTEM_STATIC_MAX_WINDOW_FLOW_M3_S] = _to_float(
            _read(system, "max_window_flow_m3_s", 0.2),
            0.2,
        )
        system_static[i, schema.SYSTEM_STATIC_MAX_MECH_VENT_FLOW_M3_S] = _to_float(
            _read(system, "max_mech_vent_flow_m3_s", 0.05),
            0.05,
        )

        system_static[i, schema.SYSTEM_STATIC_DEFAULT_HEATING_SETPOINT_C] = _to_float(
            _read(system, "default_heating_setpoint_C", 20.0),
            20.0,
        )
        system_static[i, schema.SYSTEM_STATIC_DEFAULT_COOLING_SETPOINT_C] = _to_float(
            _read(system, "default_cooling_setpoint_C", 26.0),
            26.0,
        )

    return True


# =============================================================================
# Fill action arrays
# =============================================================================

def _fill_action_arrays(state, actions, registry):
    action_static = state.static.action_static

    default_zone_name = _first_name(list(registry.zone_name_to_id.keys()))
    default_system_name = _first_name(list(registry.system_name_to_id.keys()))

    for i, action in enumerate(actions):
        name = _entity_name(action, "action", i)
        action_id = registry.action_id(name)

        action_type_name = _read(action, "type", None)
        if action_type_name is None:
            if name in registry.action_type_name_to_id:
                action_type_name = name
            else:
                action_type_name = "none"

        target_zone_name = _read_any(
            action,
            ["target_zone_id", "target_zone", "zone_id", "zone"],
            None,
        )
        target_system_name = _read_any(
            action,
            ["target_system_id", "target_system", "system_id", "system"],
            None,
        )

        # For simple one-zone/one-system tests, fill a reasonable default.
        if target_zone_name is None and default_zone_name is not None:
            target_zone_name = default_zone_name

        if target_system_name is None and default_system_name is not None:
            target_system_name = default_system_name

        appliance_type_name = _read_any(
            action,
            ["appliance_type", "appliance"],
            "none",
        )

        action_static[i, schema.ACTION_ID] = action_id
        action_static[i, schema.ACTION_TYPE] = registry.action_type_id(
            str(action_type_name)
        )
        action_static[i, schema.ACTION_DEFAULT_TARGET_ZONE_ID] = _encode_optional_name(
            target_zone_name,
            registry.zone_id,
        )
        action_static[i, schema.ACTION_DEFAULT_TARGET_SYSTEM_ID] = _encode_optional_name(
            target_system_name,
            registry.system_id,
        )
        action_static[i, schema.ACTION_DEFAULT_APPLIANCE_TYPE] = registry.appliance_type_id(
            str(appliance_type_name)
        )

        action_static[i, schema.ACTION_DURATION_MIN] = _to_float(
            _read_any(action, ["duration_min", "duration_minutes"], 15.0),
            15.0,
        )
        action_static[i, schema.ACTION_CAN_RUN_WHILE_AWAY] = _to_flag(
            _read(action, "can_run_while_away", False),
            False,
        )
        action_static[i, schema.ACTION_IS_BACKGROUND] = _to_flag(
            _read(action, "is_background", False),
            False,
        )
        action_static[i, schema.ACTION_REQUIRES_HOME] = _to_flag(
            _read(action, "requires_home", True),
            True,
        )
        action_static[i, schema.ACTION_REQUIRES_AWAKE] = _to_flag(
            _read(action, "requires_awake", True),
            True,
        )

        action_static[i, schema.ACTION_POWER_W] = _to_float(
            _read_any(action, ["power_W", "electric_power_W"], 0.0),
            0.0,
        )
        action_static[i, schema.ACTION_HEAT_GAIN_W] = _to_float(
            _read_any(action, ["heat_gain_W"], 0.0),
            0.0,
        )
        action_static[i, schema.ACTION_CO2_GAIN_KG_S] = _to_float(
            _read_any(action, ["co2_gain_kg_s"], 0.0),
            0.0,
        )
        action_static[i, schema.ACTION_MOISTURE_GAIN_KG_S] = _to_float(
            _read_any(action, ["moisture_gain_kg_s"], 0.0),
            0.0,
        )

        action_static[i, schema.ACTION_HUNGER_EFFECT] = _to_float(
            _read(action, "hunger_effect", 0.0),
            0.0,
        )
        action_static[i, schema.ACTION_FATIGUE_EFFECT] = _to_float(
            _read(action, "fatigue_effect", 0.0),
            0.0,
        )
        action_static[i, schema.ACTION_DIRTY_CLOTHES_EFFECT] = _to_float(
            _read(action, "dirty_clothes_effect", 0.0),
            0.0,
        )
        action_static[i, schema.ACTION_COMFORT_EFFECT] = _to_float(
            _read(action, "comfort_effect", 0.0),
            0.0,
        )
        action_static[i, schema.ACTION_FRICTION] = _to_float(
            _read(action, "friction", 0.0),
            0.0,
        )

    return True


# =============================================================================
# Fill process arrays
# =============================================================================

def _fill_process_arrays(state, registry):
    process_state = state.dynamic.process_state

    for i in range(process_state.shape[0]):
        process_state[i, schema.PROCESS_ID] = i
        process_state[i, schema.PROCESS_TYPE] = schema.PROCESS_TYPE_NONE
        process_state[i, schema.PROCESS_STATE] = schema.PROCESS_STATE_INACTIVE

        process_state[i, schema.PROCESS_PERSON_ID] = schema.MISSING_ID
        process_state[i, schema.PROCESS_DWELLING_ID] = schema.MISSING_ID
        process_state[i, schema.PROCESS_ZONE_ID] = schema.MISSING_ID
        process_state[i, schema.PROCESS_SYSTEM_ID] = schema.MISSING_ID

        process_state[i, schema.PROCESS_TIME_LEFT_MIN] = 0.0
        process_state[i, schema.PROCESS_TOTAL_DURATION_MIN] = 0.0

        process_state[i, schema.PROCESS_POWER_W] = 0.0
        process_state[i, schema.PROCESS_HEAT_GAIN_W] = 0.0
        process_state[i, schema.PROCESS_CO2_GAIN_KG_S] = 0.0
        process_state[i, schema.PROCESS_MOISTURE_GAIN_KG_S] = 0.0

    return True


# =============================================================================
# Derived dynamic initialization
# =============================================================================

def _update_occupancy_counts(state):
    """
    Initialize zone/dwelling/building occupancy counts from person_state.
    """
    state.dynamic.zone_state[:, schema.ZONE_OCCUPANT_COUNT] = 0.0
    state.dynamic.zone_state[:, schema.ZONE_IS_OCCUPIED] = 0.0

    state.dynamic.dwelling_state[:, schema.DWELLING_OCCUPANT_COUNT] = 0.0
    state.dynamic.dwelling_state[:, schema.DWELLING_IS_OCCUPIED] = 0.0

    state.dynamic.building_state[:, schema.BUILDING_OCCUPANT_COUNT] = 0.0
    state.dynamic.building_state[:, schema.BUILDING_IS_OCCUPIED] = 0.0

    for i in range(state.dynamic.person_state.shape[0]):
        is_home = state.dynamic.person_state[i, schema.PERSON_IS_HOME]
        if is_home <= 0.0:
            continue

        zone_id = int(state.dynamic.person_state[i, schema.PERSON_CURRENT_ZONE_ID])
        dwelling_id = int(state.dynamic.person_state[i, schema.PERSON_DWELLING_ID])

        if zone_id != schema.MISSING_ID:
            state.dynamic.zone_state[zone_id, schema.ZONE_OCCUPANT_COUNT] += 1.0
            state.dynamic.zone_state[zone_id, schema.ZONE_IS_OCCUPIED] = 1.0

        if dwelling_id != schema.MISSING_ID:
            state.dynamic.dwelling_state[dwelling_id, schema.DWELLING_OCCUPANT_COUNT] += 1.0
            state.dynamic.dwelling_state[dwelling_id, schema.DWELLING_IS_OCCUPIED] = 1.0

            building_id = int(
                state.dynamic.dwelling_state[dwelling_id, schema.DWELLING_BUILDING_ID]
            )
            if building_id != schema.MISSING_ID:
                state.dynamic.building_state[building_id, schema.BUILDING_OCCUPANT_COUNT] += 1.0
                state.dynamic.building_state[building_id, schema.BUILDING_IS_OCCUPIED] = 1.0

    return True


def _make_person_schedule_array(state):
    """
    Create a compact numeric person schedule array.

    Shape:
        [n_persons, 5]

    Columns:
        0 has_job
        1 usual_wake_minute
        2 usual_sleep_minute
        3 work_start_minute
        4 work_end_minute

    This is metadata for now. Later you can formalize it in schema.py if needed.
    """
    n_persons = state.static.person_static.shape[0]
    result = np.zeros((n_persons, 5), dtype=np.float64)

    result[:, 0] = state.static.person_static[:, schema.PERSON_STATIC_HAS_JOB]
    result[:, 1] = state.static.person_static[:, schema.PERSON_STATIC_USUAL_WAKE_MINUTE]
    result[:, 2] = state.static.person_static[:, schema.PERSON_STATIC_USUAL_SLEEP_MINUTE]
    result[:, 3] = state.static.person_static[:, schema.PERSON_STATIC_WORK_START_MINUTE]
    result[:, 4] = state.static.person_static[:, schema.PERSON_STATIC_WORK_END_MINUTE]

    return result