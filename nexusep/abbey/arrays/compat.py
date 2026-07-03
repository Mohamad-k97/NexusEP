"""
ABBEY array backward-compatibility layer.

Phase 14:
    Keep the old public/readable ABBEY surface alive while routing new runs
    through the array core.

This module is intentionally outside the numeric timestep core.

Allowed here:
    - dictionaries
    - strings
    - dataclasses
    - pandas DataFrames
    - old logger-style records
    - old config compatibility

Forbidden here:
    - new timestep physics logic
    - duplicate object-heavy timestep simulation

Main purposes:
    1. readable/legacy person -> array rows
    2. array rows -> readable/legacy person
    3. readable/legacy action -> action_static row
    4. array logs -> old logger-like DataFrames
    5. old public runner entrypoint -> array runner
"""

from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import json
import warnings

import numpy as np

from nexusep.abbey.arrays import schema
from nexusep.abbey.arrays.encoder import compile_simulation_to_arrays
from nexusep.abbey.arrays.runner import run_simulation_array_core


# =============================================================================
# Optional old imports
# =============================================================================

try:
    from nexusep.abbey.agents.states import PersonState as LegacyPersonState
except Exception:
    LegacyPersonState = None


try:
    from nexusep.abbey.actions.action import Action as LegacyAction
except Exception:
    LegacyAction = None


try:
    from nexusep.abbey.utils.config_loader import load_jsonc as legacy_load_jsonc
except Exception:
    legacy_load_jsonc = None


# =============================================================================
# Compatibility result containers
# =============================================================================

@dataclass
class PersonArrayRows:
    """
    Result of converting one readable/legacy person to array rows.
    """

    person_state_row: np.ndarray
    person_static_row: np.ndarray
    state: Any


@dataclass
class ActionArrayRow:
    """
    Result of converting one readable/legacy action to an action_static row.
    """

    action_static_row: np.ndarray
    state: Any


@dataclass
class LegacyLoggerDataFrames:
    """
    Old logger-style DataFrames reconstructed from array logs.

    main:
        close to old SimulationLogger.to_dataframe()

    people:
        close to old SimulationLogger.people_to_dataframe()

    zones:
        close to old SimulationLogger.zones_to_dataframe()
    """

    main: Any
    people: Any
    zones: Any


# =============================================================================
# Generic helpers
# =============================================================================

def _read(obj, key, default=None):
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(key, default)

    return getattr(obj, key, default)


def _read_any(obj, keys, default=None):
    for key in keys:
        value = _read(obj, key, None)
        if value is not None:
            return value

    return default


def _to_float(value, default=0.0):
    if value is None:
        return float(default)

    return float(value)


def _to_bool(value, default=False):
    if value is None:
        value = default

    if isinstance(value, str):
        lower = value.strip().lower()
        if lower in ("true", "yes", "y", "1", "on", "open"):
            return True
        if lower in ("false", "no", "n", "0", "off", "closed"):
            return False

    return bool(value)


def _safe_int(value, default=schema.MISSING_ID):
    if value is None:
        return int(default)

    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _schema_col(name, default=None):
    return getattr(schema, name, default)


def _safe_log_value(log_array, t, i, col_name, default=0.0):
    if log_array is None:
        return default

    col = _schema_col(col_name, None)

    if col is None:
        return default

    if t < 0 or t >= log_array.shape[0]:
        return default

    if i < 0 or i >= log_array.shape[1]:
        return default

    if int(col) < 0 or int(col) >= log_array.shape[2]:
        return default

    return log_array[t, i, int(col)]


def _require_pandas():
    try:
        import pandas as pd
    except ImportError:
        raise ImportError(
            "pandas is required for legacy logger DataFrame compatibility."
        )

    return pd


def _dataclass_kwargs(cls, values):
    """
    Keep only constructor fields accepted by a dataclass.
    """
    if cls is None:
        return values

    if not is_dataclass(cls):
        return values

    allowed = set()
    for item in fields(cls):
        allowed.add(item.name)

    clean = {}

    for key, value in values.items():
        if key in allowed:
            clean[key] = value

    return clean


def _id_to_name(state, entity, integer_id, fallback_prefix):
    integer_id = _safe_int(integer_id)

    if integer_id == schema.MISSING_ID:
        return None

    mappings = getattr(state, "mappings", None)

    if mappings is not None:
        attr = "%s_id_to_name" % entity
        mapping = getattr(mappings, attr, None)

        if mapping is not None and integer_id in mapping:
            return mapping[integer_id]

    return "%s_%s" % (fallback_prefix, integer_id)


def _action_type_name_from_id(state, action_type_id):
    action_type_id = _safe_int(action_type_id)

    registry = None
    if getattr(state, "metadata", None) is not None:
        registry = state.metadata.get("registry", None)

    if registry is not None:
        mapping = getattr(registry, "action_type_id_to_name", None)
        if mapping is not None and action_type_id in mapping:
            return mapping[action_type_id]

    fallback = {
        schema.ACTION_TYPE_NONE: "none",
        schema.ACTION_TYPE_IDLE: "idle",
        schema.ACTION_TYPE_SLEEP: "sleep",
        schema.ACTION_TYPE_WAKE_UP: "wake_up",
        schema.ACTION_TYPE_LEAVE_HOME: "leave_home",
        schema.ACTION_TYPE_RETURN_HOME: "return_home",
        schema.ACTION_TYPE_MOVE_ZONE: "move_zone",
        schema.ACTION_TYPE_EAT: "eat",
        schema.ACTION_TYPE_COOK: "cook",
        schema.ACTION_TYPE_DRINK: "drink",
        schema.ACTION_TYPE_MAKE_COFFEE: "make_coffee",
        schema.ACTION_TYPE_DO_LAUNDRY: "do_laundry",
        schema.ACTION_TYPE_SHOWER: "shower",
        schema.ACTION_TYPE_OPEN_WINDOW: "open_window",
        schema.ACTION_TYPE_CLOSE_WINDOW: "close_window",
        schema.ACTION_TYPE_TURN_LIGHT_ON: "turn_light_on",
        schema.ACTION_TYPE_TURN_LIGHT_OFF: "turn_light_off",
        schema.ACTION_TYPE_TURN_HEATING_ON: "turn_heating_on",
        schema.ACTION_TYPE_TURN_HEATING_OFF: "turn_heating_off",
        schema.ACTION_TYPE_TURN_COOLING_ON: "turn_cooling_on",
        schema.ACTION_TYPE_TURN_COOLING_OFF: "turn_cooling_off",
        schema.ACTION_TYPE_ADJUST_THERMOSTAT: "adjust_thermostat",
        schema.ACTION_TYPE_OPEN_BLINDS: "open_blinds",
        schema.ACTION_TYPE_CLOSE_BLINDS: "close_blinds",
        schema.ACTION_TYPE_TURN_VENTILATION_ON: "turn_ventilation_on",
        schema.ACTION_TYPE_TURN_VENTILATION_OFF: "turn_ventilation_off",
    }

    return fallback.get(action_type_id, "action_type_%s" % action_type_id)


def _occupancy_state_from_person_row(row):
    occupancy = _safe_int(row[schema.PERSON_OCCUPANCY_STATE])

    if occupancy == schema.OCCUPANCY_HOME_SLEEPING:
        return "home_sleeping"
    if occupancy == schema.OCCUPANCY_HOME_AWAKE:
        return "home_awake"
    if occupancy == schema.OCCUPANCY_AWAY:
        return "away"
    if occupancy == schema.OCCUPANCY_TRANSITION:
        return "transition"

    return "unknown"


# =============================================================================
# Legacy/readable person compatibility
# =============================================================================

def legacy_person_to_readable_dict(person):
    """
    Convert an old PersonState-like object/dict to the readable person dict
    accepted by the array encoder.
    """
    occupant_id = _read_any(
        person,
        ["id", "name", "uid", "occupant_id", "person_id"],
        "person_001",
    )

    household_id = _read_any(
        person,
        ["dwelling_id", "household_id"],
        "dwelling_001",
    )

    default_zone_id = _read_any(
        person,
        ["home_zone_id", "default_zone_id", "current_zone_id"],
        "main_room",
    )

    current_zone_id = _read_any(
        person,
        ["current_zone_id", "zone_id"],
        default_zone_id,
    )

    assigned_sleep_zone_id = _read_any(
        person,
        ["sleep_zone_id", "assigned_sleep_zone_id"],
        "",
    )

    if assigned_sleep_zone_id in (None, ""):
        assigned_sleep_zone_id = default_zone_id

    assigned_work_zone_id = _read_any(
        person,
        ["work_zone_id", "assigned_work_zone_id"],
        None,
    )

    sickness = _read_any(
        person,
        ["sickness", "sickness_severity"],
        0.0,
    )

    laziness = _read_any(
        person,
        ["laziness", "base_laziness", "action_friction"],
        0.2,
    )

    readable = {
        "id": str(occupant_id),
        "dwelling_id": str(household_id),

        "home_zone_id": str(default_zone_id),
        "sleep_zone_id": str(assigned_sleep_zone_id),
        "work_zone_id": assigned_work_zone_id,
        "current_zone_id": str(current_zone_id),

        "is_home": _to_bool(_read(person, "is_home", True), True),
        "occupancy_state": "home_sleeping"
        if _to_bool(_read(person, "is_sleeping", False), False)
        else "home_awake",

        "hunger": _to_float(_read(person, "hunger", 0.3), 0.3),
        "fatigue": _to_float(_read(person, "fatigue", 0.3), 0.3),
        "dirty_clothes": _to_float(_read(person, "dirty_clothes", 0.0), 0.0),
        "sickness": _to_float(sickness, 0.0),
        "laziness": _to_float(laziness, 0.2),

        "cold_sensitivity": _to_float(_read(person, "cold_sensitivity", 1.0), 1.0),
        "heat_sensitivity": _to_float(_read(person, "heat_sensitivity", 1.0), 1.0),
        "co2_sensitivity": _to_float(_read(person, "co2_sensitivity", 1.0), 1.0),
        "light_sensitivity": _to_float(_read(person, "light_sensitivity", 1.0), 1.0),
        "noise_sensitivity": _to_float(_read(person, "noise_sensitivity", 1.0), 1.0),
        "action_friction": _to_float(_read(person, "action_friction", 0.3), 0.3),

        "metabolic_heat_W": _to_float(_read(person, "metabolic_heat_W", 80.0), 80.0),
        "co2_gain_kg_s": _to_float(_read(person, "co2_gain_kg_s", 0.000005), 0.000005),
        "moisture_gain_kg_s": _to_float(_read(person, "moisture_gain_kg_s", 0.00003), 0.00003),

        "has_job": _to_bool(_read(person, "has_job", False), False),
        "usual_wake_minute": _to_float(
            _read(person, "usual_wake_minute", 7.0 * 60.0),
            7.0 * 60.0,
        ),
        "usual_sleep_minute": _to_float(
            _read(person, "usual_sleep_minute", 23.0 * 60.0),
            23.0 * 60.0,
        ),
        "work_start_minute": _to_float(
            _read(person, "work_start_minute", 9.0 * 60.0),
            9.0 * 60.0,
        ),
        "work_end_minute": _to_float(
            _read(person, "work_end_minute", 17.0 * 60.0),
            17.0 * 60.0,
        ),
    }

    if not readable["is_home"]:
        readable["occupancy_state"] = "away"

    return readable


def _minimal_input_for_person(readable_person):
    dwelling_id = _read(readable_person, "dwelling_id", "dwelling_001")
    building_id = "building_001"

    home_zone_id = _read(readable_person, "home_zone_id", "main_room")
    sleep_zone_id = _read(readable_person, "sleep_zone_id", home_zone_id)
    current_zone_id = _read(readable_person, "current_zone_id", home_zone_id)

    zone_ids = []
    for value in [home_zone_id, sleep_zone_id, current_zone_id]:
        if value is not None and value not in zone_ids:
            zone_ids.append(value)

    zones = []
    for zone_id in zone_ids:
        zones.append(
            {
                "id": zone_id,
                "type": "main_room" if zone_id == home_zone_id else "bedroom",
                "dwelling_id": dwelling_id,
                "building_id": building_id,
                "floor_area_m2": 30.0,
                "volume_m3": 75.0,
                "height_m": 2.5,
                "air_temperature_C": 21.0,
                "relative_humidity": 0.50,
                "co2_ppm": 700.0,
            }
        )

    return {
        "dt_minutes": 15,
        "n_timesteps": 1,
        "buildings": [
            {
                "id": building_id,
                "floor_area_m2": 30.0,
                "volume_m3": 75.0,
                "height_m": 3.0,
                "n_floors": 1,
            }
        ],
        "dwellings": [
            {
                "id": dwelling_id,
                "building_id": building_id,
                "floor_area_m2": 30.0,
                "volume_m3": 75.0,
            }
        ],
        "zones": zones,
        "persons": [readable_person],
        "systems": [
            {
                "id": "system_001",
                "dwelling_id": dwelling_id,
                "zone_id": home_zone_id,
                "has_heating": True,
                "has_cooling": True,
                "has_window": True,
                "has_lights": True,
                "has_blinds": True,
                "has_mech_ventilation": True,
            }
        ],
        "actions": [
            {
                "id": "idle",
                "type": "idle",
                "target_zone_id": home_zone_id,
                "duration_min": 15.0,
                "requires_home": False,
                "requires_awake": False,
                "can_run_while_away": True,
            }
        ],
        "weather": {
            "outdoor_temperature_C": 10.0,
            "relative_humidity": 0.50,
            "outdoor_co2_ppm": 420.0,
            "wind_speed_m_s": 2.0,
            "ghi_W_m2": 0.0,
        },
    }


def readable_person_to_array_rows(person, registry=None, dtype=np.float64):
    """
    Convert one old/readable person object to person_state/person_static rows.

    Returns:
        PersonArrayRows
    """
    readable_person = legacy_person_to_readable_dict(person)

    state = compile_simulation_to_arrays(
        readable_input=_minimal_input_for_person(readable_person),
        registry=registry,
        dtype=dtype,
        include_metadata=True,
    )

    return PersonArrayRows(
        person_state_row=state.dynamic.person_state[0, :].copy(),
        person_static_row=state.static.person_static[0, :].copy(),
        state=state,
    )


def array_person_rows_to_readable_person(
    person_state_row,
    person_static_row,
    state=None,
    as_legacy_dataclass=False,
):
    """
    Convert person_state/person_static rows back to a readable person dict.

    If as_legacy_dataclass=True and the old PersonState is importable, return
    an old PersonState instance.
    """
    person_id = person_state_row[schema.PERSON_ID]
    dwelling_id = person_state_row[schema.PERSON_DWELLING_ID]
    current_zone_id = person_state_row[schema.PERSON_CURRENT_ZONE_ID]
    home_zone_id = person_static_row[schema.PERSON_STATIC_HOME_ZONE_ID]
    sleep_zone_id = person_static_row[schema.PERSON_STATIC_SLEEP_ZONE_ID]
    work_zone_id = person_static_row[schema.PERSON_STATIC_WORK_ZONE_ID]

    if state is not None:
        person_name = _id_to_name(state, "person", person_id, "person")
        dwelling_name = _id_to_name(state, "dwelling", dwelling_id, "dwelling")
        current_zone_name = _id_to_name(state, "zone", current_zone_id, "zone")
        home_zone_name = _id_to_name(state, "zone", home_zone_id, "zone")
        sleep_zone_name = _id_to_name(state, "zone", sleep_zone_id, "zone")
        work_zone_name = _id_to_name(state, "zone", work_zone_id, "zone")
    else:
        person_name = "person_%s" % _safe_int(person_id)
        dwelling_name = "dwelling_%s" % _safe_int(dwelling_id)
        current_zone_name = "zone_%s" % _safe_int(current_zone_id)
        home_zone_name = "zone_%s" % _safe_int(home_zone_id)
        sleep_zone_name = "zone_%s" % _safe_int(sleep_zone_id)
        work_zone_name = None if _safe_int(work_zone_id) == schema.MISSING_ID else "zone_%s" % _safe_int(work_zone_id)

    occupancy_name = _occupancy_state_from_person_row(person_state_row)

    readable = {
        "id": person_name,
        "occupant_id": person_name,
        "dwelling_id": dwelling_name,
        "household_id": dwelling_name,

        "current_zone_id": current_zone_name,
        "default_zone_id": home_zone_name,
        "home_zone_id": home_zone_name,
        "sleep_zone_id": sleep_zone_name,
        "work_zone_id": work_zone_name,

        "is_home": bool(person_state_row[schema.PERSON_IS_HOME] > 0.0),
        "is_sleeping": occupancy_name == "home_sleeping",
        "occupancy_state": occupancy_name,

        "hunger": float(person_state_row[schema.PERSON_HUNGER]),
        "fatigue": float(person_state_row[schema.PERSON_FATIGUE]),
        "dirty_clothes": float(person_state_row[schema.PERSON_DIRTY_CLOTHES]),
        "sickness": float(person_state_row[schema.PERSON_SICKNESS]),
        "sickness_severity": float(person_state_row[schema.PERSON_SICKNESS]),
        "laziness": float(person_state_row[schema.PERSON_LAZINESS]),
        "base_laziness": float(person_state_row[schema.PERSON_LAZINESS]),

        "thermal_discomfort": float(person_state_row[schema.PERSON_THERMAL_STRESS]),
        "air_quality_discomfort": float(person_state_row[schema.PERSON_AIR_QUALITY_STRESS]),
        "visual_discomfort": float(person_state_row[schema.PERSON_VISUAL_STRESS]),
        "acoustic_discomfort": float(person_state_row[schema.PERSON_ACOUSTIC_STRESS]),

        "cold_sensitivity": float(person_static_row[schema.PERSON_STATIC_COLD_SENSITIVITY]),
        "heat_sensitivity": float(person_static_row[schema.PERSON_STATIC_HEAT_SENSITIVITY]),
        "action_friction": float(person_static_row[schema.PERSON_STATIC_ACTION_FRICTION]),

        "has_job": bool(person_static_row[schema.PERSON_STATIC_HAS_JOB] > 0.0),
        "usual_wake_minute": float(person_static_row[schema.PERSON_STATIC_USUAL_WAKE_MINUTE]),
        "usual_sleep_minute": float(person_static_row[schema.PERSON_STATIC_USUAL_SLEEP_MINUTE]),
        "work_start_minute": float(person_static_row[schema.PERSON_STATIC_WORK_START_MINUTE]),
        "work_end_minute": float(person_static_row[schema.PERSON_STATIC_WORK_END_MINUTE]),
    }

    if as_legacy_dataclass and LegacyPersonState is not None:
        kwargs = _dataclass_kwargs(LegacyPersonState, readable)
        return LegacyPersonState(**kwargs)

    return readable


# =============================================================================
# Legacy/readable action compatibility
# =============================================================================

def infer_action_type_name(action_name, action=None):
    """
    Infer array action type from an old action name/config.

    This intentionally handles common old names without requiring the old
    config structure to perfectly match the array schema.
    """
    name = str(action_name).lower()

    category = str(_read(action, "category", "")).lower()
    system_effects = _read(action, "system_effects", {}) or {}

    if "sleep" in name:
        return "sleep"
    if "wake" in name:
        return "wake_up"
    if "eat" in name or "meal" in name:
        return "eat"
    if "cook" in name:
        return "cook"
    if "coffee" in name:
        return "make_coffee"
    if "laundry" in name or "washing" in name:
        return "do_laundry"
    if "shower" in name:
        return "shower"

    if "open_window" in name or "window_open" in name:
        return "open_window"
    if "close_window" in name or "window_close" in name:
        return "close_window"

    if "light_on" in name or "turn_light_on" in name:
        return "turn_light_on"
    if "light_off" in name or "turn_light_off" in name:
        return "turn_light_off"

    if "heating_on" in name or "turn_heating_on" in name:
        return "turn_heating_on"
    if "heating_off" in name or "turn_heating_off" in name:
        return "turn_heating_off"

    if "cooling_on" in name or "turn_cooling_on" in name:
        return "turn_cooling_on"
    if "cooling_off" in name or "turn_cooling_off" in name:
        return "turn_cooling_off"

    if "ventilation_on" in name:
        return "turn_ventilation_on"
    if "ventilation_off" in name:
        return "turn_ventilation_off"

    if "blind" in name and "open" in name:
        return "open_blinds"
    if "blind" in name and "close" in name:
        return "close_blinds"

    if isinstance(system_effects, dict):
        if system_effects.get("window_open") is True:
            return "open_window"
        if system_effects.get("window_open") is False:
            return "close_window"
        if system_effects.get("lights_on") is True:
            return "turn_light_on"
        if system_effects.get("lights_on") is False:
            return "turn_light_off"
        if system_effects.get("heating_on") is True:
            return "turn_heating_on"
        if system_effects.get("heating_on") is False:
            return "turn_heating_off"

    if category in ("sleep", "food", "cooking", "laundry", "comfort"):
        return category

    return "idle"


def legacy_action_to_readable_dict(action):
    """
    Convert an old Action-like object/dict/config row to the readable action
    dict accepted by the array encoder.
    """
    name = _read_any(action, ["id", "name"], "idle")
    action_type = _read(action, "type", None)

    if action_type is None:
        action_type = infer_action_type_name(name, action)

    person_effects = _read(action, "person_effects", {}) or {}

    readable = {
        "id": str(name),
        "type": str(action_type),

        "target_zone_id": _read_any(
            action,
            ["target_zone_id", "target_space_id", "zone_id"],
            "main_room",
        ),
        "target_system_id": _read_any(
            action,
            ["target_system_id", "system_id"],
            "system_001",
        ),

        "duration_min": _to_float(
            _read_any(action, ["duration_min", "duration_minutes"], 15.0),
            15.0,
        ),

        "requires_home": _to_bool(_read(action, "requires_home", True), True),
        "requires_awake": _to_bool(_read(action, "requires_awake", True), True),
        "is_background": _to_bool(_read(action, "background_process", False), False),
        "can_run_while_away": _to_bool(
            _read(action, "can_continue_without_actor", False),
            False,
        ),

        "power_W": _to_float(_read_any(action, ["power_W", "power_w"], 0.0), 0.0),
        "heat_gain_W": _to_float(_read_any(action, ["heat_gain_W", "heat_gain_w"], 0.0), 0.0),
        "co2_gain_kg_s": _to_float(_read(action, "co2_gain_kg_s", 0.0), 0.0),
        "moisture_gain_kg_s": _to_float(_read(action, "moisture_gain_kg_s", 0.0), 0.0),

        "hunger_effect": _to_float(
            _read_any(action, ["hunger_effect"], person_effects.get("hunger", 0.0)),
            0.0,
        ),
        "fatigue_effect": _to_float(
            _read_any(action, ["fatigue_effect"], person_effects.get("fatigue", 0.0)),
            0.0,
        ),
        "dirty_clothes_effect": _to_float(
            _read_any(
                action,
                ["dirty_clothes_effect"],
                person_effects.get("dirty_clothes", 0.0),
            ),
            0.0,
        ),
        "comfort_effect": _to_float(
            _read_any(action, ["comfort_effect"], person_effects.get("comfort", 0.0)),
            0.0,
        ),
        "friction": _to_float(_read_any(action, ["friction", "effort"], 0.0), 0.0),
    }

    return readable


def _minimal_input_for_action(readable_action):
    target_zone_id = _read(readable_action, "target_zone_id", "main_room")
    target_system_id = _read(readable_action, "target_system_id", "system_001")

    return {
        "dt_minutes": 15,
        "n_timesteps": 1,
        "buildings": [
            {
                "id": "building_001",
                "floor_area_m2": 30.0,
                "volume_m3": 75.0,
                "height_m": 3.0,
                "n_floors": 1,
            }
        ],
        "dwellings": [
            {
                "id": "dwelling_001",
                "building_id": "building_001",
                "floor_area_m2": 30.0,
                "volume_m3": 75.0,
            }
        ],
        "zones": [
            {
                "id": target_zone_id,
                "type": "main_room",
                "dwelling_id": "dwelling_001",
                "building_id": "building_001",
                "floor_area_m2": 30.0,
                "volume_m3": 75.0,
            }
        ],
        "persons": [
            {
                "id": "person_001",
                "dwelling_id": "dwelling_001",
                "home_zone_id": target_zone_id,
                "sleep_zone_id": target_zone_id,
                "current_zone_id": target_zone_id,
                "is_home": True,
            }
        ],
        "systems": [
            {
                "id": target_system_id,
                "dwelling_id": "dwelling_001",
                "zone_id": target_zone_id,
                "has_heating": True,
                "has_cooling": True,
                "has_window": True,
                "has_lights": True,
                "has_blinds": True,
                "has_mech_ventilation": True,
            }
        ],
        "actions": [readable_action],
        "weather": {
            "outdoor_temperature_C": 10.0,
            "relative_humidity": 0.50,
            "outdoor_co2_ppm": 420.0,
            "wind_speed_m_s": 2.0,
            "ghi_W_m2": 0.0,
        },
    }


def readable_action_to_action_static_row(action, registry=None, dtype=np.float64):
    """
    Convert one old/readable action to one action_static row.

    Returns:
        ActionArrayRow
    """
    readable_action = legacy_action_to_readable_dict(action)

    state = compile_simulation_to_arrays(
        readable_input=_minimal_input_for_action(readable_action),
        registry=registry,
        dtype=dtype,
        include_metadata=True,
    )

    return ActionArrayRow(
        action_static_row=state.static.action_static[0, :].copy(),
        state=state,
    )


def array_action_row_to_readable_action(action_static_row, state=None):
    """
    Convert one action_static row back to a readable action dict.
    """
    action_id = action_static_row[schema.ACTION_ID]
    target_zone_id = action_static_row[schema.ACTION_DEFAULT_TARGET_ZONE_ID]
    target_system_id = action_static_row[schema.ACTION_DEFAULT_TARGET_SYSTEM_ID]

    if state is not None:
        action_name = _id_to_name(state, "action", action_id, "action")
        target_zone_name = _id_to_name(state, "zone", target_zone_id, "zone")
        target_system_name = _id_to_name(state, "system", target_system_id, "system")
    else:
        action_name = "action_%s" % _safe_int(action_id)
        target_zone_name = None if _safe_int(target_zone_id) == schema.MISSING_ID else "zone_%s" % _safe_int(target_zone_id)
        target_system_name = None if _safe_int(target_system_id) == schema.MISSING_ID else "system_%s" % _safe_int(target_system_id)

    return {
        "id": action_name,
        "name": action_name,
        "type": _action_type_name_from_id(state, action_static_row[schema.ACTION_TYPE])
        if state is not None
        else "action_type_%s" % _safe_int(action_static_row[schema.ACTION_TYPE]),

        "target_zone_id": target_zone_name,
        "target_system_id": target_system_name,

        "duration_min": float(action_static_row[schema.ACTION_DURATION_MIN]),
        "requires_home": bool(action_static_row[schema.ACTION_REQUIRES_HOME] > 0.0),
        "requires_awake": bool(action_static_row[schema.ACTION_REQUIRES_AWAKE] > 0.0),
        "is_background": bool(action_static_row[schema.ACTION_IS_BACKGROUND] > 0.0),
        "can_run_while_away": bool(action_static_row[schema.ACTION_CAN_RUN_WHILE_AWAY] > 0.0),

        "power_W": float(action_static_row[schema.ACTION_POWER_W]),
        "heat_gain_W": float(action_static_row[schema.ACTION_HEAT_GAIN_W]),
        "co2_gain_kg_s": float(action_static_row[schema.ACTION_CO2_GAIN_KG_S]),
        "moisture_gain_kg_s": float(action_static_row[schema.ACTION_MOISTURE_GAIN_KG_S]),

        "hunger_effect": float(action_static_row[schema.ACTION_HUNGER_EFFECT]),
        "fatigue_effect": float(action_static_row[schema.ACTION_FATIGUE_EFFECT]),
        "dirty_clothes_effect": float(action_static_row[schema.ACTION_DIRTY_CLOTHES_EFFECT]),
        "comfort_effect": float(action_static_row[schema.ACTION_COMFORT_EFFECT]),
        "friction": float(action_static_row[schema.ACTION_FRICTION]),
    }


# =============================================================================
# Old config compatibility
# =============================================================================

def load_config_compatible(config):
    """
    Accept:
        dict/object config
        JSON/JSONC path

    The old config loader is kept and reused if available.
    """
    if isinstance(config, (str, Path)):
        path = Path(config)

        if legacy_load_jsonc is not None:
            return legacy_load_jsonc(path)

        import json
        text = path.read_text(encoding="utf-8")
        return json.loads(text)

    return config


def legacy_actions_config_to_readable_actions(actions_config):
    """
    Convert old config['actions'] dict into encoder-friendly action list.
    """
    if actions_config is None:
        return None

    if isinstance(actions_config, list):
        return actions_config

    if not isinstance(actions_config, dict):
        return actions_config

    actions = []

    for name, cfg in actions_config.items():
        if str(name).startswith("_"):
            continue

        if cfg is None:
            cfg = {}

        if isinstance(cfg, dict):
            item = dict(cfg)
            item["id"] = name
            item["name"] = name
        else:
            item = {
                "id": name,
                "name": name,
            }

        actions.append(legacy_action_to_readable_dict(item))

    return actions


def legacy_config_to_readable_input(config):
    """
    Convert old ABBEY config-ish input into readable input for the array runner.

    If config already has buildings/dwellings/zones/persons/systems, preserve
    them. If it only has old action config, create a minimum one-zone case.
    """
    config = load_config_compatible(config)

    if not isinstance(config, dict):
        return config

    has_array_sections = (
        "buildings" in config
        or "dwellings" in config
        or "zones" in config
        or "persons" in config
        or "systems" in config
    )

    readable = dict(config)

    if isinstance(readable.get("actions", None), dict):
        readable["actions"] = legacy_actions_config_to_readable_actions(
            readable.get("actions")
        )

    if has_array_sections:
        return readable

    # Minimum compatibility case for old config-only runs.
    readable.setdefault("dt_minutes", 15)
    readable.setdefault("n_timesteps", 1)
    readable.setdefault("start_minute_of_day", 8 * 60)

    readable.setdefault(
        "buildings",
        [
            {
                "id": "building_001",
                "floor_area_m2": 40.0,
                "volume_m3": 100.0,
                "height_m": 3.0,
                "n_floors": 1,
            }
        ],
    )

    readable.setdefault(
        "dwellings",
        [
            {
                "id": "dwelling_001",
                "building_id": "building_001",
                "floor_area_m2": 40.0,
                "volume_m3": 100.0,
            }
        ],
    )

    readable.setdefault(
        "zones",
        [
            {
                "id": "main_room",
                "type": "main_room",
                "dwelling_id": "dwelling_001",
                "building_id": "building_001",
                "floor_area_m2": 40.0,
                "volume_m3": 100.0,
                "height_m": 2.5,
                "air_temperature_C": 21.0,
                "mean_radiant_temperature_C": 21.0,
                "relative_humidity": 0.50,
                "co2_ppm": 700.0,
                "illuminance_lux": 200.0,
                "noise_db": 35.0,
            }
        ],
    )

    readable.setdefault(
        "persons",
        [
            {
                "id": "person_001",
                "dwelling_id": "dwelling_001",
                "home_zone_id": "main_room",
                "sleep_zone_id": "main_room",
                "current_zone_id": "main_room",
                "is_home": True,
            }
        ],
    )

    readable.setdefault(
        "systems",
        [
            {
                "id": "system_001",
                "dwelling_id": "dwelling_001",
                "zone_id": "main_room",
                "has_heating": True,
                "has_cooling": True,
                "has_window": True,
                "has_lights": True,
                "has_blinds": True,
                "has_mech_ventilation": True,
                "hvac_mode": "off",
                "ventilation_mode": "off",
            }
        ],
    )

    readable.setdefault(
        "weather",
        {
            "outdoor_temperature_C": 10.0,
            "relative_humidity": 0.50,
            "outdoor_co2_ppm": 420.0,
            "wind_speed_m_s": 2.0,
            "ghi_W_m2": 0.0,
        },
    )

    if not readable.get("actions"):
        readable["actions"] = [
            {
                "id": "idle",
                "type": "idle",
                "target_zone_id": "main_room",
                "duration_min": 15.0,
                "requires_home": False,
                "requires_awake": False,
                "can_run_while_away": True,
            }
        ]

    return readable


# =============================================================================
# Array logs -> old logger-like DataFrames
# =============================================================================

def _time_info_for_index(state, time_index):
    dt_minutes = 15.0

    if getattr(state, "metadata", None) is not None:
        dt_minutes = float(state.metadata.get("dt_minutes", dt_minutes))

    day = 0
    hour = 0.0

    if getattr(state, "series", None) is not None:
        time_series = getattr(state.series, "time_series", None)

        if time_series is not None and time_index < time_series.shape[0]:
            minute_of_day = time_series[time_index, schema.TIME_MINUTE_OF_DAY]
            day = int(time_series[time_index, schema.TIME_DAY_INDEX])
            hour = float(minute_of_day) / 60.0

    return {
        "step": int(time_index),
        "day": int(day),
        "hour": float(hour),
        "dt_hours": float(dt_minutes) / 60.0,
    }


def _system_controls_for_zone_from_logs(state, logs, time_index, zone_id):
    result = {
        "heating_on": False,
        "cooling_on": False,
        "lights_on": False,
        "window_open": False,
        "curtain_closed": False,
        "blind_closed": False,
    }

    system_log = logs.system_log

    if system_log is None:
        return result

    for system_i in range(system_log.shape[1]):
        system_zone_id = _safe_int(
            _safe_log_value(
                system_log,
                time_index,
                system_i,
                "SYSTEM_LOG_ZONE_ID",
                schema.MISSING_ID,
            )
        )

        if system_zone_id != int(zone_id):
            continue

        heating_power = _safe_log_value(
            system_log,
            time_index,
            system_i,
            "SYSTEM_LOG_HEATING_POWER_W",
            0.0,
        )
        cooling_power = _safe_log_value(
            system_log,
            time_index,
            system_i,
            "SYSTEM_LOG_COOLING_POWER_W",
            0.0,
        )
        light_state = _safe_log_value(
            system_log,
            time_index,
            system_i,
            "SYSTEM_LOG_LIGHT_STATE",
            schema.LIGHT_STATE_OFF,
        )
        window_fraction = _safe_log_value(
            system_log,
            time_index,
            system_i,
            "SYSTEM_LOG_WINDOW_OPEN_FRACTION",
            0.0,
        )
        blind_fraction = _safe_log_value(
            system_log,
            time_index,
            system_i,
            "SYSTEM_LOG_BLIND_CLOSED_FRACTION",
            0.0,
        )

        result["heating_on"] = result["heating_on"] or heating_power > 0.0
        result["cooling_on"] = result["cooling_on"] or cooling_power > 0.0
        result["lights_on"] = result["lights_on"] or _safe_int(light_state) == schema.LIGHT_STATE_ON
        result["window_open"] = result["window_open"] or window_fraction > 0.0
        result["blind_closed"] = result["blind_closed"] or blind_fraction > 0.0
        result["curtain_closed"] = result["blind_closed"]

    return result


def _occupied_person_ids_for_zone_from_logs(state, logs, time_index, zone_id):
    result = []

    person_log = logs.person_log

    if person_log is None:
        return result

    for person_i in range(person_log.shape[1]):
        person_zone_id = _safe_int(
            _safe_log_value(
                person_log,
                time_index,
                person_i,
                "PERSON_LOG_ZONE_ID",
                schema.MISSING_ID,
            )
        )
        is_home = _safe_log_value(
            person_log,
            time_index,
            person_i,
            "PERSON_LOG_IS_HOME",
            0.0,
        )

        if person_zone_id == int(zone_id) and is_home > 0.0:
            person_id = _safe_log_value(
                person_log,
                time_index,
                person_i,
                "PERSON_LOG_PERSON_ID",
                person_i,
            )
            result.append(_id_to_name(state, "person", person_id, "person"))

    return result


def array_logs_to_old_zone_records(state, logs):
    """
    Create old SimulationLogger.zone_records-like rows from array zone logs.
    """
    records = []

    zone_log = logs.zone_log

    if zone_log is None:
        return records

    for t in range(zone_log.shape[0]):
        time_info = _time_info_for_index(state, t)

        for zone_i in range(zone_log.shape[1]):
            zone_id_value = _safe_log_value(
                zone_log,
                t,
                zone_i,
                "ZONE_LOG_ZONE_ID",
                zone_i,
            )
            zone_id = _safe_int(zone_id_value)
            zone_name = _id_to_name(state, "zone", zone_id, "zone")

            occupied_person_ids = _occupied_person_ids_for_zone_from_logs(
                state=state,
                logs=logs,
                time_index=t,
                zone_id=zone_id,
            )

            controls = _system_controls_for_zone_from_logs(
                state=state,
                logs=logs,
                time_index=t,
                zone_id=zone_id,
            )

            record = dict(time_info)
            record.update(
                {
                    "zone_id": zone_name,
                    "zone_name": zone_name,

                    "indoor_temp": float(
                        _safe_log_value(
                            zone_log,
                            t,
                            zone_i,
                            "ZONE_LOG_AIR_TEMPERATURE_C",
                            0.0,
                        )
                    ),
                    "co2_ppm": float(
                        _safe_log_value(
                            zone_log,
                            t,
                            zone_i,
                            "ZONE_LOG_CO2_PPM",
                            0.0,
                        )
                    ),
                    "indoor_daylight": float(
                        _safe_log_value(
                            zone_log,
                            t,
                            zone_i,
                            "ZONE_LOG_ILLUMINANCE_LUX",
                            0.0,
                        )
                    ),
                    "illuminance_lux": float(
                        _safe_log_value(
                            zone_log,
                            t,
                            zone_i,
                            "ZONE_LOG_ILLUMINANCE_LUX",
                            0.0,
                        )
                    ),
                    "indoor_noise": float(
                        _safe_log_value(
                            zone_log,
                            t,
                            zone_i,
                            "ZONE_LOG_NOISE_DB",
                            0.0,
                        )
                    ),
                    "noise_db": float(
                        _safe_log_value(
                            zone_log,
                            t,
                            zone_i,
                            "ZONE_LOG_NOISE_DB",
                            0.0,
                        )
                    ),
                    "relative_humidity": float(
                        _safe_log_value(
                            zone_log,
                            t,
                            zone_i,
                            "ZONE_LOG_RELATIVE_HUMIDITY",
                            0.0,
                        )
                    ),

                    "heating_on": controls["heating_on"],
                    "cooling_on": controls["cooling_on"],
                    "lights_on": controls["lights_on"],
                    "window_open": controls["window_open"],
                    "curtain_closed": controls["curtain_closed"],
                    "blind_closed": controls["blind_closed"],

                    "occupied_person_ids": json.dumps(
                        occupied_person_ids,
                        ensure_ascii=False,
                    ),
                    "number_of_people": int(
                        _safe_log_value(
                            zone_log,
                            t,
                            zone_i,
                            "ZONE_LOG_OCCUPANT_COUNT",
                            len(occupied_person_ids),
                        )
                    ),
                }
            )

            records.append(record)

    return records


def array_logs_to_old_people_records(state, logs):
    """
    Create old SimulationLogger.person_records-like rows from array person logs.
    """
    records = []

    person_log = logs.person_log

    if person_log is None:
        return records

    for t in range(person_log.shape[0]):
        time_info = _time_info_for_index(state, t)

        for person_i in range(person_log.shape[1]):
            person_id_value = _safe_log_value(
                person_log,
                t,
                person_i,
                "PERSON_LOG_PERSON_ID",
                person_i,
            )
            person_id = _safe_int(person_id_value)
            occupant_id = _id_to_name(state, "person", person_id, "person")

            zone_id_value = _safe_log_value(
                person_log,
                t,
                person_i,
                "PERSON_LOG_ZONE_ID",
                schema.MISSING_ID,
            )
            zone_name = _id_to_name(state, "zone", zone_id_value, "zone")

            record = dict(time_info)
            record.update(
                {
                    "occupant_id": occupant_id,

                    "person_occupant_id": occupant_id,
                    "person_hunger": float(
                        _safe_log_value(person_log, t, person_i, "PERSON_LOG_HUNGER", 0.0)
                    ),
                    "person_fatigue": float(
                        _safe_log_value(person_log, t, person_i, "PERSON_LOG_FATIGUE", 0.0)
                    ),
                    "person_dirty_clothes": float(
                        _safe_log_value(person_log, t, person_i, "PERSON_LOG_DIRTY_CLOTHES", 0.0)
                    ),
                    "person_sickness_severity": float(
                        _safe_log_value(person_log, t, person_i, "PERSON_LOG_SICKNESS", 0.0)
                    ),
                    "person_thermal_discomfort": float(
                        _safe_log_value(person_log, t, person_i, "PERSON_LOG_THERMAL_STRESS", 0.0)
                    ),
                    "person_air_quality_discomfort": float(
                        _safe_log_value(person_log, t, person_i, "PERSON_LOG_AIR_QUALITY_STRESS", 0.0)
                    ),
                    "person_visual_discomfort": float(
                        _safe_log_value(person_log, t, person_i, "PERSON_LOG_VISUAL_STRESS", 0.0)
                    ),
                    "person_acoustic_discomfort": float(
                        _safe_log_value(person_log, t, person_i, "PERSON_LOG_ACOUSTIC_STRESS", 0.0)
                    ),

                    "location_occupant_id": occupant_id,
                    "location_current_space_id": zone_name,
                    "location_is_home": bool(
                        _safe_log_value(person_log, t, person_i, "PERSON_LOG_IS_HOME", 0.0) > 0.0
                    ),

                    "action_id": _safe_int(
                        _safe_log_value(
                            person_log,
                            t,
                            person_i,
                            "PERSON_LOG_ACTION_ID",
                            schema.MISSING_ID,
                        )
                    ),
                    "action_time_left_min": float(
                        _safe_log_value(
                            person_log,
                            t,
                            person_i,
                            "PERSON_LOG_ACTION_TIME_LEFT_MIN",
                            0.0,
                        )
                    ),
                    "power_w": float(
                        _safe_log_value(
                            person_log,
                            t,
                            person_i,
                            "PERSON_LOG_POWER_W",
                            0.0,
                        )
                    ),
                }
            )

            records.append(record)

    return records


def array_logs_to_old_main_records(state, logs):
    """
    Create old SimulationLogger.records-like rows from array logs.

    This is a compatibility approximation: enough for old plotting/scripts that
    expect the old high-level logger columns.
    """
    records = []

    if logs.person_log is None and logs.zone_log is None:
        return records

    n_timesteps = 0

    if logs.person_log is not None:
        n_timesteps = logs.person_log.shape[0]
    elif logs.zone_log is not None:
        n_timesteps = logs.zone_log.shape[0]

    for t in range(n_timesteps):
        time_info = _time_info_for_index(state, t)

        person_i = 0
        zone_i = 0

        occupant_id = None
        current_space_id = None
        location_is_home = False

        if logs.person_log is not None and logs.person_log.shape[1] > 0:
            person_id_value = _safe_log_value(
                logs.person_log,
                t,
                person_i,
                "PERSON_LOG_PERSON_ID",
                person_i,
            )
            occupant_id = _id_to_name(state, "person", person_id_value, "person")

            zone_id_value = _safe_log_value(
                logs.person_log,
                t,
                person_i,
                "PERSON_LOG_ZONE_ID",
                schema.MISSING_ID,
            )
            current_space_id = _id_to_name(state, "zone", zone_id_value, "zone")

            location_is_home = bool(
                _safe_log_value(
                    logs.person_log,
                    t,
                    person_i,
                    "PERSON_LOG_IS_HOME",
                    0.0,
                )
                > 0.0
            )

        if current_space_id is None and logs.zone_log is not None and logs.zone_log.shape[1] > 0:
            zone_id_value = _safe_log_value(
                logs.zone_log,
                t,
                zone_i,
                "ZONE_LOG_ZONE_ID",
                zone_i,
            )
            current_space_id = _id_to_name(state, "zone", zone_id_value, "zone")

        action_id_value = schema.MISSING_ID
        action_time_left_min = 0.0
        total_action_power_w = 0.0

        if logs.person_log is not None and logs.person_log.shape[1] > 0:
            action_id_value = _safe_log_value(
                logs.person_log,
                t,
                person_i,
                "PERSON_LOG_ACTION_ID",
                schema.MISSING_ID,
            )
            action_time_left_min = _safe_log_value(
                logs.person_log,
                t,
                person_i,
                "PERSON_LOG_ACTION_TIME_LEFT_MIN",
                0.0,
            )
            total_action_power_w = _safe_log_value(
                logs.person_log,
                t,
                person_i,
                "PERSON_LOG_POWER_W",
                0.0,
            )

        foreground_actions = []
        if _safe_int(action_id_value) != schema.MISSING_ID:
            foreground_actions.append(
                {
                    "action_id": _safe_int(action_id_value),
                    "remaining_minutes": float(action_time_left_min),
                }
            )

        record = dict(time_info)
        record.update(
            {
                "occupant_id": occupant_id,
                "dwelling_id": "dwelling_0",
                "current_space_id": current_space_id,
                "current_space_role": "current",
                "location_is_home": location_is_home,
                "away_reason": "none" if location_is_home else "away",
                "minutes_since_last_space_change": 0.0,

                "total_action_energy_wh": 0.0,
                "total_action_power_w": float(total_action_power_w),
                "active_power_w": float(total_action_power_w),

                "foreground_actions": json.dumps(
                    foreground_actions,
                    ensure_ascii=False,
                ),
                "background_processes": "[]",
                "action_cooldowns": "{}",
                "chunk_records": "[]",
                "space_assignment": "{}",
                "household": "{}",
                "cooldowns": "{}",
                "performance_log": "{}",
            }
        )

        if logs.person_log is not None and logs.person_log.shape[1] > 0:
            record.update(
                {
                    "person_occupant_id": occupant_id,
                    "person_hunger": float(
                        _safe_log_value(logs.person_log, t, person_i, "PERSON_LOG_HUNGER", 0.0)
                    ),
                    "person_fatigue": float(
                        _safe_log_value(logs.person_log, t, person_i, "PERSON_LOG_FATIGUE", 0.0)
                    ),
                    "person_dirty_clothes": float(
                        _safe_log_value(logs.person_log, t, person_i, "PERSON_LOG_DIRTY_CLOTHES", 0.0)
                    ),
                    "person_sickness_severity": float(
                        _safe_log_value(logs.person_log, t, person_i, "PERSON_LOG_SICKNESS", 0.0)
                    ),
                    "person_thermal_discomfort": float(
                        _safe_log_value(logs.person_log, t, person_i, "PERSON_LOG_THERMAL_STRESS", 0.0)
                    ),
                    "person_air_quality_discomfort": float(
                        _safe_log_value(logs.person_log, t, person_i, "PERSON_LOG_AIR_QUALITY_STRESS", 0.0)
                    ),
                    "person_visual_discomfort": float(
                        _safe_log_value(logs.person_log, t, person_i, "PERSON_LOG_VISUAL_STRESS", 0.0)
                    ),
                    "person_acoustic_discomfort": float(
                        _safe_log_value(logs.person_log, t, person_i, "PERSON_LOG_ACOUSTIC_STRESS", 0.0)
                    ),
                }
            )

        if logs.zone_log is not None and logs.zone_log.shape[1] > 0:
            record.update(
                {
                    "observation_indoor_temp": float(
                        _safe_log_value(logs.zone_log, t, zone_i, "ZONE_LOG_AIR_TEMPERATURE_C", 0.0)
                    ),
                    "observation_co2_ppm": float(
                        _safe_log_value(logs.zone_log, t, zone_i, "ZONE_LOG_CO2_PPM", 0.0)
                    ),
                    "observation_indoor_daylight": float(
                        _safe_log_value(logs.zone_log, t, zone_i, "ZONE_LOG_ILLUMINANCE_LUX", 0.0)
                    ),
                    "observation_indoor_noise": float(
                        _safe_log_value(logs.zone_log, t, zone_i, "ZONE_LOG_NOISE_DB", 0.0)
                    ),
                    "observation_indoor_relative_humidity_percent": 100.0
                    * float(
                        _safe_log_value(
                            logs.zone_log,
                            t,
                            zone_i,
                            "ZONE_LOG_RELATIVE_HUMIDITY",
                            0.0,
                        )
                    ),
                }
            )

        records.append(record)

    return records


def array_logs_to_old_logger_dataframes(state, logs):
    """
    Convert array logs into old SimulationLogger-style DataFrames.
    """
    pd = _require_pandas()

    main_records = array_logs_to_old_main_records(state, logs)
    people_records = array_logs_to_old_people_records(state, logs)
    zone_records = array_logs_to_old_zone_records(state, logs)

    return LegacyLoggerDataFrames(
        main=pd.DataFrame(main_records),
        people=pd.DataFrame(people_records),
        zones=pd.DataFrame(zone_records),
    )


def array_logs_to_old_logger_dataframe(state, logs):
    """
    Singular helper matching old SimulationLogger.to_dataframe().
    """
    return array_logs_to_old_logger_dataframes(
        state=state,
        logs=logs,
    ).main


# =============================================================================
# Old logger adapter object
# =============================================================================

class LegacyArraySimulationLoggerAdapter:
    """
    Adapter exposing old SimulationLogger-like methods while backed by array logs.

    Useful for old scripts that call:
        sim.logger.to_dataframe()
        sim.logger.people_to_dataframe()
        sim.logger.zones_to_dataframe()
        sim.logger.save_csv(...)
        sim.logger.save_people_csv(...)
        sim.logger.save_zone_csvs(...)
    """

    def __init__(self, state, logs):
        self.state = state
        self.logs = logs
        self._dataframes = None

    def _ensure_dataframes(self):
        if self._dataframes is None:
            self._dataframes = array_logs_to_old_logger_dataframes(
                state=self.state,
                logs=self.logs,
            )
        return self._dataframes

    def to_dataframe(self):
        return self._ensure_dataframes().main

    def people_to_dataframe(self):
        return self._ensure_dataframes().people

    def zones_to_dataframe(self):
        return self._ensure_dataframes().zones

    def save_csv(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.to_dataframe().to_csv(path, index=False)

    def save_people_csv(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.people_to_dataframe().to_csv(path, index=False)

    def save_zone_csvs(self, folder):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)

        df = self.zones_to_dataframe()

        if df.empty:
            return

        for zone_id, group in df.groupby("zone_id"):
            safe_zone_id = str(zone_id).replace("/", "_").replace("\\", "_")
            group.to_csv(folder / ("%s.csv" % safe_zone_id), index=False)


# =============================================================================
# Runner compatibility
# =============================================================================

def run_simulation_compatible(
    config,
    runner="array",
    old_runner=None,
    legacy_logger_format=True,
    **kwargs
):
    """
    Backward-compatible public runner.

    Default:
        route to array core.

    If runner='old':
        call old_runner(config).

    This lets old code switch gradually instead of rewriting all call sites.
    """
    runner_name = str(runner).lower().strip()

    if runner_name in ("old", "object", "legacy"):
        if old_runner is None:
            raise ValueError(
                "runner='old' was requested but old_runner was not provided."
            )
        return old_runner(config)

    if runner_name not in ("array", "arrays", "new", "array_core", "compat"):
        raise ValueError(
            "Unknown runner '%s'. Use 'array' or 'old'." % runner
        )

    readable_input = legacy_config_to_readable_input(config)

    result = run_simulation_array_core(
        readable_input=readable_input,
        **kwargs
    )

    if legacy_logger_format:
        adapter = LegacyArraySimulationLoggerAdapter(
            state=result.state,
            logs=result.logs,
        )
        result.metadata["legacy_logger_adapter"] = adapter
        result.metadata["old_logger_dataframes"] = adapter._ensure_dataframes()

    return result


def run_abbey_simulation(config, **kwargs):
    """
    Old-public-name-style alias.

    Point old examples/scripts here first. Later, once the array runner is
    trusted, this can become the official public runner.
    """
    return run_simulation_compatible(
        config=config,
        **kwargs
    )


def mark_legacy_object_timestep(name="old object timestep"):
    """
    Small helper to mark old object timestep code as legacy without deleting it.
    """
    warnings.warn(
        "%s is legacy. New runs should use nexusep.abbey.arrays.runner "
        "or nexusep.abbey.arrays.compat.run_simulation_compatible."
        % name,
        DeprecationWarning,
        stacklevel=2,
    )


def legacy_timestep_wrapper(function):
    """
    Decorator for old object timestep functions.

    Use this later on the old step function if you want a visible warning
    without deleting the old implementation.
    """
    def wrapped(*args, **kwargs):
        mark_legacy_object_timestep(function.__name__)
        return function(*args, **kwargs)

    wrapped.__name__ = getattr(function, "__name__", "legacy_timestep")
    wrapped.__doc__ = getattr(function, "__doc__", None)

    return wrapped