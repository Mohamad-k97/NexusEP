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
) -> tuple:
    if action_name == "turn_heating_on":
        if control_state.heating_mode == "auto":
            return False, "auto_placeholder_no_override"

        if control_state.heating_mode == "semi_auto":
            control_state.heating_setpoint_c = max(
                control_state.heating_setpoint_c,
                heating_on_setpoint_c,
            )
            return True, "semi_auto_heating_setpoint_raised"

        if control_state.heating_mode == "off":
            control_state.heating_mode = "manual"

        control_state.manual_heating_on = True
        return True, "manual_heating_on"

    if action_name == "turn_heating_off":
        if control_state.heating_mode == "auto":
            return False, "auto_placeholder_no_override"

        if control_state.heating_mode == "semi_auto":
            control_state.heating_setpoint_c = min(
                control_state.heating_setpoint_c,
                heating_off_setpoint_c,
            )
            return True, "semi_auto_heating_setback"

        control_state.manual_heating_on = False
        return True, "manual_heating_off"

    if action_name == "turn_cooling_on":
        if control_state.cooling_mode == "auto":
            return False, "auto_placeholder_no_override"

        if control_state.cooling_mode == "semi_auto":
            control_state.cooling_setpoint_c = min(
                control_state.cooling_setpoint_c,
                cooling_on_setpoint_c,
            )
            return True, "semi_auto_cooling_setpoint_lowered"

        if control_state.cooling_mode == "off":
            control_state.cooling_mode = "manual"

        control_state.manual_cooling_on = True
        return True, "manual_cooling_on"

    if action_name == "turn_cooling_off":
        if control_state.cooling_mode == "auto":
            return False, "auto_placeholder_no_override"

        if control_state.cooling_mode == "semi_auto":
            control_state.cooling_setpoint_c = max(
                control_state.cooling_setpoint_c,
                cooling_off_setpoint_c,
            )
            return True, "semi_auto_cooling_setback"

        control_state.manual_cooling_on = False
        return True, "manual_cooling_off"

    if action_name == "turn_lights_on":
        if control_state.lighting_mode == "auto":
            return False, "auto_placeholder_no_override"

        control_state.lighting_mode = "manual"
        control_state.manual_lights_on = True
        return True, "manual_lights_on"

    if action_name == "turn_lights_off":
        if control_state.lighting_mode == "auto":
            return False, "auto_placeholder_no_override"

        control_state.lighting_mode = "manual"
        control_state.manual_lights_on = False
        return True, "manual_lights_off"

    if action_name == "open_window":
        if control_state.window_mode == "auto":
            return False, "auto_placeholder_no_override"

        control_state.window_mode = "manual"
        control_state.manual_window_open = True
        return True, "manual_window_open"

    if action_name == "close_window":
        if control_state.window_mode == "auto":
            return False, "auto_placeholder_no_override"

        control_state.window_mode = "manual"
        control_state.manual_window_open = False
        return True, "manual_window_closed"

    if action_name == "open_curtain":
        if control_state.shading_mode == "auto":
            return False, "auto_placeholder_no_override"

        control_state.shading_mode = "manual"
        control_state.manual_curtain_open = True
        return True, "manual_curtain_open"

    if action_name == "close_curtain":
        if control_state.shading_mode == "auto":
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
    dwelling_id = _get_attr_or_key(location, "dwelling_id", "dwelling_1")

    if current_space_id is None:
        return None

    all_zone_ids = set(building_model.all_zone_ids())

    if current_space_id in all_zone_ids:
        return current_space_id

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