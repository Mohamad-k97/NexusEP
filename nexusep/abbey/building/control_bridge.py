"""
Bridge ABBEY human control actions to building ZoneControlState.

This module updates control intent after behavior/action execution and before
the building performance model runs.

It does not directly switch physical systems.
Physical commands are still produced later by controllers:

    ZoneControlState -> ZoneControlCommand
"""

from typing import Any, Dict, List, Optional

from nexusep.abbey.agents.location import make_dwelling_space_id
from nexusep.abbey.building.model import BuildingModel
from nexusep.abbey.building.systems import ZoneControlState


CONTROL_ACTION_ALIASES = {
    "turn_heating_on": "turn_heating_on",
    "turn_on_heating": "turn_heating_on",
    "heating_on": "turn_heating_on",

    "turn_heating_off": "turn_heating_off",
    "turn_off_heating": "turn_heating_off",
    "heating_off": "turn_heating_off",

    "turn_cooling_on": "turn_cooling_on",
    "turn_on_cooling": "turn_cooling_on",
    "cooling_on": "turn_cooling_on",

    "turn_cooling_off": "turn_cooling_off",
    "turn_off_cooling": "turn_cooling_off",
    "cooling_off": "turn_cooling_off",

    "raise_heating_setpoint": "raise_heating_setpoint",
    "increase_heating_setpoint": "raise_heating_setpoint",
    "heating_setpoint_up": "raise_heating_setpoint",
    "warmer": "raise_heating_setpoint",

    "lower_heating_setpoint": "lower_heating_setpoint",
    "decrease_heating_setpoint": "lower_heating_setpoint",
    "heating_setpoint_down": "lower_heating_setpoint",

    "set_heating_setpoint": "set_heating_setpoint",
    "change_heating_setpoint": "set_heating_setpoint",

    "raise_cooling_setpoint": "raise_cooling_setpoint",
    "increase_cooling_setpoint": "raise_cooling_setpoint",
    "cooling_setpoint_up": "raise_cooling_setpoint",

    "lower_cooling_setpoint": "lower_cooling_setpoint",
    "decrease_cooling_setpoint": "lower_cooling_setpoint",
    "cooling_setpoint_down": "lower_cooling_setpoint",
    "cooler": "lower_cooling_setpoint",

    "set_cooling_setpoint": "set_cooling_setpoint",
    "change_cooling_setpoint": "set_cooling_setpoint",
    
    "turn_ventilation_on": "turn_ventilation_on",
    "turn_on_ventilation": "turn_ventilation_on",
    "ventilation_on": "turn_ventilation_on",
    "turn_fan_on": "turn_ventilation_on",
    "fan_on": "turn_ventilation_on",

    "turn_ventilation_off": "turn_ventilation_off",
    "turn_off_ventilation": "turn_ventilation_off",
    "ventilation_off": "turn_ventilation_off",
    "turn_fan_off": "turn_ventilation_off",
    "fan_off": "turn_ventilation_off",

    "turn_lights_on": "turn_lights_on",
    "turn_light_on": "turn_lights_on",
    "switch_lights_on": "turn_lights_on",
    "lights_on": "turn_lights_on",

    "turn_lights_off": "turn_lights_off",
    "turn_light_off": "turn_lights_off",
    "switch_lights_off": "turn_lights_off",
    "lights_off": "turn_lights_off",

    "open_window": "open_window",
    "close_window": "close_window",

    "open_curtain": "open_curtain",
    "open_curtains": "open_curtain",
    "open_shading": "open_curtain",

    "close_curtain": "close_curtain",
    "close_curtains": "close_curtain",
    "close_shading": "close_curtain",
}


def apply_control_action_bridge(
    building_model: BuildingModel,
    locations: Dict[str, Any],
    action_records: Optional[Any] = None,
    action_name_by_occupant: Optional[Dict[str, str]] = None,
    heating_on_setpoint_c: float = 21.0,
    heating_off_setpoint_c: float = 16.0,
    cooling_on_setpoint_c: float = 24.0,
    cooling_off_setpoint_c: float = 30.0,
    setpoint_step_c: float = 0.5,
    minimum_heat_cool_gap_c: float = 1.0,
) -> List[Dict[str, Any]]:
    """
    Apply human control actions to the ZoneControlState of the occupied zone.

    Parameters
    ----------
    building_model:
        Current BuildingModel.

    locations:
        Dict occupant_id -> OccupantLocation.

    action_records:
        Flexible action records from the simulation/execution layer.

    action_name_by_occupant:
        Optional direct mapping:
            {"person_1": "open_window"}

    Returns
    -------
    List of bridge records for debugging/logging.
    """

    events = _extract_action_events(
        action_records=action_records,
        action_name_by_occupant=action_name_by_occupant,
    )

    bridge_records = []

    for event in events:
        occupant_id = event.get("occupant_id")
        raw_action_name = event.get("action_name")
        action_name = normalize_control_action_name(raw_action_name)

        if action_name is None:
            continue

        if occupant_id not in locations:
            bridge_records.append(
                _make_bridge_record(
                    occupant_id=occupant_id,
                    raw_action_name=raw_action_name,
                    action_name=action_name,
                    changed=False,
                    reason="occupant_location_not_found",
                )
            )
            continue

        location = locations[occupant_id]

        zone_id = _zone_id_for_location(
            building_model=building_model,
            location=location,
        )

        if zone_id is None:
            bridge_records.append(
                _make_bridge_record(
                    occupant_id=occupant_id,
                    raw_action_name=raw_action_name,
                    action_name=action_name,
                    changed=False,
                    reason="zone_not_found_or_occupant_not_home",
                )
            )
            continue

        control_state = _get_or_create_control_state(
            building_model=building_model,
            zone_id=zone_id,
        )

        before = control_state.to_dict()

        changed, reason = _apply_action_to_control_state(
            control_state=control_state,
            action_name=action_name,
            heating_on_setpoint_c=heating_on_setpoint_c,
            heating_off_setpoint_c=heating_off_setpoint_c,
            cooling_on_setpoint_c=cooling_on_setpoint_c,
            cooling_off_setpoint_c=cooling_off_setpoint_c,
            action_value=event.get("action_value"),
            setpoint_step_c=setpoint_step_c,
            minimum_heat_cool_gap_c=minimum_heat_cool_gap_c,
        )

        after = control_state.to_dict()

        zone_model = building_model.get_zone_model(zone_id)

        bridge_records.append(
            _make_bridge_record(
                occupant_id=occupant_id,
                raw_action_name=raw_action_name,
                action_name=action_name,
                changed=changed,
                reason=reason,
                building_id=zone_model.building_id,
                dwelling_id=zone_model.dwelling_id,
                zone_id=zone_id,
                before=before,
                after=after,
            )
        )

    return bridge_records


def normalize_control_action_name(action_name: Any) -> Optional[str]:
    if action_name is None:
        return None

    value = str(action_name).strip().lower().replace(" ", "_").replace("-", "_")

    return CONTROL_ACTION_ALIASES.get(value)


def _apply_action_to_control_state(
    control_state: ZoneControlState,
    action_name: str,
    heating_on_setpoint_c: float,
    heating_off_setpoint_c: float,
    cooling_on_setpoint_c: float,
    cooling_off_setpoint_c: float,
    action_value: Optional[Any] = None,
    setpoint_step_c: float = 0.5,
    minimum_heat_cool_gap_c: float = 1.0,
) -> tuple:
    
    if action_name == "raise_heating_setpoint":
        if _is_auto_or_bms_mode(control_state.heating_mode):
            return False, "auto_placeholder_no_override"

        delta_c = _delta_or_default(action_value, setpoint_step_c)

        return _set_heating_setpoint(
            control_state=control_state,
            new_setpoint_c=control_state.heating_setpoint_c + delta_c,
            minimum_heat_cool_gap_c=minimum_heat_cool_gap_c,
            reason="heating_setpoint_raised",
        )

    if action_name == "lower_heating_setpoint":
        if _is_auto_or_bms_mode(control_state.heating_mode):
            return False, "auto_placeholder_no_override"

        delta_c = _delta_or_default(action_value, setpoint_step_c)

        return _set_heating_setpoint(
            control_state=control_state,
            new_setpoint_c=control_state.heating_setpoint_c - delta_c,
            minimum_heat_cool_gap_c=minimum_heat_cool_gap_c,
            reason="heating_setpoint_lowered",
        )

    if action_name == "set_heating_setpoint":
        if _is_auto_or_bms_mode(control_state.heating_mode):
            return False, "auto_placeholder_no_override"

        value = _float_or_none(action_value)

        if value is None:
            return False, "missing_heating_setpoint_value"

        return _set_heating_setpoint(
            control_state=control_state,
            new_setpoint_c=value,
            minimum_heat_cool_gap_c=minimum_heat_cool_gap_c,
            reason="heating_setpoint_set",
        )

    if action_name == "raise_cooling_setpoint":
        if _is_auto_or_bms_mode(control_state.cooling_mode):
            return False, "auto_placeholder_no_override"

        delta_c = _delta_or_default(action_value, setpoint_step_c)

        return _set_cooling_setpoint(
            control_state=control_state,
            new_setpoint_c=control_state.cooling_setpoint_c + delta_c,
            minimum_heat_cool_gap_c=minimum_heat_cool_gap_c,
            reason="cooling_setpoint_raised",
        )

    if action_name == "lower_cooling_setpoint":
        if _is_auto_or_bms_mode(control_state.cooling_mode):
            return False, "auto_placeholder_no_override"

        delta_c = _delta_or_default(action_value, setpoint_step_c)

        return _set_cooling_setpoint(
            control_state=control_state,
            new_setpoint_c=control_state.cooling_setpoint_c - delta_c,
            minimum_heat_cool_gap_c=minimum_heat_cool_gap_c,
            reason="cooling_setpoint_lowered",
        )

    if action_name == "set_cooling_setpoint":
        if _is_auto_or_bms_mode(control_state.cooling_mode):
            return False, "auto_placeholder_no_override"

        value = _float_or_none(action_value)

        if value is None:
            return False, "missing_cooling_setpoint_value"

        return _set_cooling_setpoint(
            control_state=control_state,
            new_setpoint_c=value,
            minimum_heat_cool_gap_c=minimum_heat_cool_gap_c,
            reason="cooling_setpoint_set",
        )
    
    if action_name == "turn_heating_on":
        if _is_auto_or_bms_mode(control_state.heating_mode):
            return False, "auto_placeholder_no_override"

        if _is_semi_auto_mode(control_state.heating_mode):
            return _set_heating_setpoint(
                control_state=control_state,
                new_setpoint_c=heating_on_setpoint_c,
                minimum_heat_cool_gap_c=minimum_heat_cool_gap_c,
                reason="semi_auto_heating_setpoint_on",
            )

        control_state.heating_mode = "manual"
        control_state.manual_heating_on = True
        return True, "manual_heating_on"

    if action_name == "turn_heating_off":
        if _is_auto_or_bms_mode(control_state.heating_mode):
            return False, "auto_placeholder_no_override"

        if _is_semi_auto_mode(control_state.heating_mode):
            return _set_heating_setpoint(
                control_state=control_state,
                new_setpoint_c=heating_off_setpoint_c,
                minimum_heat_cool_gap_c=minimum_heat_cool_gap_c,
                reason="semi_auto_heating_setpoint_off",
            )

        control_state.heating_mode = "manual"
        control_state.manual_heating_on = False
        return True, "manual_heating_off"

    if action_name == "turn_cooling_on":
        if _is_auto_or_bms_mode(control_state.cooling_mode):
            return False, "auto_placeholder_no_override"

        control_state.cooling_mode = "manual"
        control_state.manual_cooling_on = True
        return True, "manual_cooling_on"

    if action_name == "turn_cooling_off":
        if _is_auto_or_bms_mode(control_state.cooling_mode):
            return False, "auto_placeholder_no_override"

        control_state.cooling_mode = "manual"
        control_state.manual_cooling_on = False
        return True, "manual_cooling_off"

    if action_name == "turn_ventilation_on":
        if _is_auto_or_bms_mode(control_state.ventilation_mode):
            return False, "auto_placeholder_no_override"

        control_state.ventilation_mode = "manual"
        control_state.manual_ventilation_on = True
        return True, "manual_ventilation_on"

    if action_name == "turn_ventilation_off":
        if _is_auto_or_bms_mode(control_state.ventilation_mode):
            return False, "auto_placeholder_no_override"

        control_state.ventilation_mode = "manual"
        control_state.manual_ventilation_on = False
        return True, "manual_ventilation_off"

    if action_name == "turn_lights_on":
        if _is_auto_or_bms_mode(control_state.lighting_mode):
            return False, "auto_placeholder_no_override"

        control_state.lighting_mode = "manual"
        control_state.manual_lights_on = True
        return True, "manual_lights_on"

    if action_name == "turn_lights_off":
        if _is_auto_or_bms_mode(control_state.lighting_mode):
            return False, "auto_placeholder_no_override"

        control_state.lighting_mode = "manual"
        control_state.manual_lights_on = False
        return True, "manual_lights_off"

    if action_name == "open_window":
        if _is_auto_or_bms_mode(control_state.window_mode):
            return False, "auto_placeholder_no_override"

        control_state.window_mode = "manual"
        control_state.manual_window_open = True
        return True, "manual_window_open"

    if action_name == "close_window":
        if _is_auto_or_bms_mode(control_state.window_mode):
            return False, "auto_placeholder_no_override"

        control_state.window_mode = "manual"
        control_state.manual_window_open = False
        return True, "manual_window_closed"

    if action_name == "open_curtain":
        if _is_auto_or_bms_mode(control_state.shading_mode):
            return False, "auto_placeholder_no_override"

        control_state.shading_mode = "manual"
        control_state.manual_curtain_open = True
        return True, "manual_curtain_open"

    if action_name == "close_curtain":
        if _is_auto_or_bms_mode(control_state.shading_mode):
            return False, "auto_placeholder_no_override"

        control_state.shading_mode = "manual"
        control_state.manual_curtain_open = False
        return True, "manual_curtain_closed"

    return False, "not_a_control_action"


def _zone_id_for_location(
    building_model: BuildingModel,
    location: Any,
) -> Optional[str]:
    is_home = bool(_get_attr_or_key(location, "is_home", False))

    if not is_home:
        return None

    current_space_id = _get_attr_or_key(location, "current_space_id", None)
    dwelling_id = _get_attr_or_key(location, "dwelling_id", None)

    if current_space_id is None:
        return None

    all_zone_ids = set(building_model.all_zone_ids())

    if current_space_id in all_zone_ids:
        return current_space_id

    if not dwelling_id:
        dwelling_ids = list(building_model.dwellings)
        if len(dwelling_ids) != 1:
            return None
        dwelling_id = dwelling_ids[0]

    dwelling_aware_id = make_dwelling_space_id(
        space_id=current_space_id,
        dwelling_id=dwelling_id,
    )

    if dwelling_aware_id in all_zone_ids:
        return dwelling_aware_id

    return None


def _get_or_create_control_state(
    building_model: BuildingModel,
    zone_id: str,
) -> ZoneControlState:
    zone_model = building_model.get_zone_model(zone_id)
    dwelling = building_model.dwellings.get(zone_model.dwelling_id)

    if dwelling is not None:
        if zone_id not in dwelling.control_states:
            dwelling.control_states[zone_id] = ZoneControlState(
                zone_id=zone_id,
                dwelling_id=zone_model.dwelling_id,
                building_id=zone_model.building_id,
            )

        return dwelling.control_states[zone_id]

    if zone_id not in building_model.building_control_states:
        building_model.building_control_states[zone_id] = ZoneControlState(
            zone_id=zone_id,
            dwelling_id=zone_model.dwelling_id,
            building_id=zone_model.building_id,
        )

    return building_model.building_control_states[zone_id]


def _extract_action_events(
    action_records: Optional[Any],
    action_name_by_occupant: Optional[Dict[str, str]],
) -> List[Dict[str, Any]]:
    events = []

    if action_name_by_occupant is not None:
        for occupant_id, action_name in action_name_by_occupant.items():
            events.append(
                {
                    "occupant_id": occupant_id,
                    "action_name": action_name,
                    "action_value": None,
                    "source": "action_name_by_occupant",
                }
            )

    if action_records is None:
        return events

    if isinstance(action_records, dict):
        for key, value in action_records.items():
            if isinstance(value, str):
                events.append(
                    {
                        "occupant_id": key,
                        "action_name": value,
                        "action_value": None,
                        "source": "action_records_mapping",
                    }
                )
            else:
                occupant_id = _extract_occupant_id(value)

                if occupant_id is None:
                    occupant_id = key

                action_name = _extract_action_name(value)

                events.append(
                    {
                        "occupant_id": occupant_id,
                        "action_name": action_name,
                        "action_value": _extract_action_value(value),
                        "source": "action_records_dict",
                    }
                )

        return events

    for record in _safe_list(action_records):
        occupant_id = _extract_occupant_id(record)
        action_name = _extract_action_name(record)

        if occupant_id is None or action_name is None:
            continue

        events.append(
            {
                "occupant_id": occupant_id,
                "action_name": action_name,
                "action_value": _extract_action_value(record),
                "source": "action_records_list",
            }
        )

    return events


def _extract_occupant_id(record: Any) -> Optional[str]:
    keys = [
        "occupant_id",
        "actor_id",
        "person_id",
        "agent_id",
    ]

    for key in keys:
        value = _get_attr_or_key(record, key, None)

        if value is not None:
            return str(value)

    return None


def _extract_action_name(record: Any) -> Optional[str]:
    if record is None:
        return None

    if isinstance(record, str):
        return record

    keys = [
        "action_name",
        "action",
        "name",
        "selected_action_name",
        "active_action_name",
        "current_action",
    ]

    for key in keys:
        value = _get_attr_or_key(record, key, None)

        if value is None:
            continue

        if isinstance(value, str):
            return value

        nested_name = _get_attr_or_key(value, "name", None)

        if nested_name is not None:
            return str(nested_name)

    return None

def _extract_action_value(record: Any) -> Optional[Any]:
    if record is None:
        return None

    if isinstance(record, str):
        return None

    keys = [
        "action_value",
        "value",
        "setpoint_c",
        "temperature_c",
        "target_c",
        "delta_c",
        "amount_c",
    ]

    for key in keys:
        value = _get_attr_or_key(record, key, None)

        if value is not None:
            return value

    return None


def _delta_or_default(value: Any, default_delta_c: float) -> float:
    parsed = _float_or_none(value)

    if parsed is None:
        parsed = default_delta_c

    parsed = abs(float(parsed))

    if parsed <= 0.0:
        parsed = abs(float(default_delta_c))

    return parsed


def _float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bounded_setpoint_c(value: float) -> float:
    value = float(value)

    if value < 5.0:
        return 5.0

    if value > 35.0:
        return 35.0

    return value


def _set_heating_setpoint(
    control_state: ZoneControlState,
    new_setpoint_c: float,
    minimum_heat_cool_gap_c: float,
    reason: str,
) -> tuple:
    old_mode = control_state.heating_mode
    old_setpoint = float(control_state.heating_setpoint_c)

    minimum_heat_cool_gap_c = max(0.0, float(minimum_heat_cool_gap_c))

    new_setpoint_c = _bounded_setpoint_c(new_setpoint_c)

    max_allowed = (
        float(control_state.cooling_setpoint_c)
        - minimum_heat_cool_gap_c
    )

    clipped = False

    if new_setpoint_c > max_allowed:
        new_setpoint_c = max_allowed
        clipped = True

    control_state.heating_mode = "semi_auto"
    control_state.heating_setpoint_c = float(new_setpoint_c)

    changed = (
        old_mode != control_state.heating_mode
        or abs(old_setpoint - control_state.heating_setpoint_c) > 1e-9
    )

    if not changed:
        return False, "heating_setpoint_unchanged"

    if clipped:
        return True, reason + "_clipped_by_cooling_setpoint"

    return True, reason


def _set_cooling_setpoint(
    control_state: ZoneControlState,
    new_setpoint_c: float,
    minimum_heat_cool_gap_c: float,
    reason: str,
) -> tuple:
    old_mode = control_state.cooling_mode
    old_setpoint = float(control_state.cooling_setpoint_c)

    minimum_heat_cool_gap_c = max(0.0, float(minimum_heat_cool_gap_c))

    new_setpoint_c = _bounded_setpoint_c(new_setpoint_c)

    min_allowed = (
        float(control_state.heating_setpoint_c)
        + minimum_heat_cool_gap_c
    )

    clipped = False

    if new_setpoint_c < min_allowed:
        new_setpoint_c = min_allowed
        clipped = True

    control_state.cooling_mode = "semi_auto"
    control_state.cooling_setpoint_c = float(new_setpoint_c)

    changed = (
        old_mode != control_state.cooling_mode
        or abs(old_setpoint - control_state.cooling_setpoint_c) > 1e-9
    )

    if not changed:
        return False, "cooling_setpoint_unchanged"

    if clipped:
        return True, reason + "_clipped_by_heating_setpoint"

    return True, reason

def _make_bridge_record(
    occupant_id: Optional[str],
    raw_action_name: Any,
    action_name: Optional[str],
    changed: bool,
    reason: str,
    building_id: Optional[str] = None,
    dwelling_id: Optional[str] = None,
    zone_id: Optional[str] = None,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "occupant_id": occupant_id,
        "raw_action_name": raw_action_name,
        "action_name": action_name,
        "changed": changed,
        "reason": reason,
        "building_id": building_id,
        "dwelling_id": dwelling_id,
        "zone_id": zone_id,
        "before": before,
        "after": after,
    }

def _is_semi_auto_mode(value: Any) -> bool:
    return str(value).strip().lower() == "semi_auto"

def _is_auto_or_bms_mode(value: Any) -> bool:
    return str(value).strip().lower() in {"auto", "bms"}

def _get_attr_or_key(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(name, default)

    return getattr(obj, name, default)


def _safe_list(value: Any) -> List[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    return [value]
