"""
ABBEY array-output decoder.

Purpose:
    Convert numeric ABBEY array state/logs back into human-readable outputs.

This is outside the timestep core.

Allowed here:
    - strings
    - dicts
    - pandas
    - CSV export
    - readable names
    - decoded records

Forbidden in timestep kernels:
    - this module
    - pandas
    - string decoding
    - dict record construction
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import os

import numpy as np

from nexusep.abbey.arrays import schema
from nexusep.abbey.arrays.registry import (
    invert_mapping,
    make_default_action_type_name_to_id,
    make_default_appliance_type_name_to_id,
    make_default_zone_type_name_to_id,
    make_default_hvac_mode_name_to_id,
    make_default_ventilation_mode_name_to_id,
    make_default_process_type_name_to_id,
    make_default_process_state_name_to_id,
    make_default_occupancy_state_name_to_id,
)


# =============================================================================
# Decoded output container
# =============================================================================

@dataclass
class DecodedSimulationState:
    """
    Human-readable decoded snapshot of SimulationArrayState.
    """

    persons: List[Dict[str, Any]]
    zones: List[Dict[str, Any]]
    dwellings: List[Dict[str, Any]]
    buildings: List[Dict[str, Any]]
    systems: List[Dict[str, Any]]
    actions: List[Dict[str, Any]]
    processes: List[Dict[str, Any]]
    weather: Dict[str, Any]
    time: Dict[str, Any]


# =============================================================================
# Generic helpers
# =============================================================================

def _to_int(value):
    return int(round(float(value)))


def _to_float(value):
    return float(value)


def _to_bool(value):
    return bool(float(value) > 0.0)


def _none_if_missing(integer_id):
    integer_id = _to_int(integer_id)
    if integer_id == schema.MISSING_ID:
        return None
    return integer_id


def _get_registry(state):
    """
    Get full registry from state.metadata, if available.
    """
    if getattr(state, "metadata", None) is None:
        return None

    if not isinstance(state.metadata, dict):
        return None

    return state.metadata.get("registry", None)


def _get_mapping(state, attr_name):
    """
    Get an entity id->name mapping from state.mappings.
    """
    mappings = getattr(state, "mappings", None)
    if mappings is None:
        return None

    return getattr(mappings, attr_name, None)


def _decode_from_mapping(integer_id, id_to_name, fallback_prefix):
    """
    Decode an integer entity ID using a mapping.

    If no mapping is available, return fallback_prefix_id.
    """
    integer_id = _none_if_missing(integer_id)
    if integer_id is None:
        return None

    if id_to_name is not None and integer_id in id_to_name:
        return id_to_name[integer_id]

    return "%s_%s" % (fallback_prefix, integer_id)


def _decode_type(integer_id, type_id_to_name, fallback_prefix):
    """
    Decode an integer type ID.
    """
    integer_id = _none_if_missing(integer_id)
    if integer_id is None:
        return None

    if integer_id in type_id_to_name:
        return type_id_to_name[integer_id]

    return "%s_%s" % (fallback_prefix, integer_id)


def _default_type_inverse_mappings():
    """
    Build default ID -> name mappings for enum-like schema values.
    """
    return {
        "action_type": invert_mapping(
            make_default_action_type_name_to_id(),
            "action_type",
        ),
        "appliance_type": invert_mapping(
            make_default_appliance_type_name_to_id(),
            "appliance_type",
        ),
        "zone_type": invert_mapping(
            make_default_zone_type_name_to_id(),
            "zone_type",
        ),
        "hvac_mode": invert_mapping(
            make_default_hvac_mode_name_to_id(),
            "hvac_mode",
        ),
        "ventilation_mode": invert_mapping(
            make_default_ventilation_mode_name_to_id(),
            "ventilation_mode",
        ),
        "process_type": invert_mapping(
            make_default_process_type_name_to_id(),
            "process_type",
        ),
        "process_state": invert_mapping(
            make_default_process_state_name_to_id(),
            "process_state",
        ),
        "occupancy_state": invert_mapping(
            make_default_occupancy_state_name_to_id(),
            "occupancy_state",
        ),
    }


def _get_type_maps(state):
    """
    Get type reverse mappings.

    Prefer the full registry if state.metadata contains it.
    Otherwise use defaults from schema registry helpers.
    """
    registry = _get_registry(state)

    if registry is not None:
        return {
            "action_type": registry.action_type_id_to_name,
            "appliance_type": registry.appliance_type_id_to_name,
            "zone_type": registry.zone_type_id_to_name,
            "hvac_mode": registry.hvac_mode_id_to_name,
            "ventilation_mode": registry.ventilation_mode_id_to_name,
            "process_type": registry.process_type_id_to_name,
            "process_state": registry.process_state_id_to_name,
            "occupancy_state": registry.occupancy_state_id_to_name,
        }

    return _default_type_inverse_mappings()


def _entity_maps(state):
    return {
        "person": _get_mapping(state, "person_id_to_name"),
        "zone": _get_mapping(state, "zone_id_to_name"),
        "dwelling": _get_mapping(state, "dwelling_id_to_name"),
        "building": _get_mapping(state, "building_id_to_name"),
        "system": _get_mapping(state, "system_id_to_name"),
        "action": _get_mapping(state, "action_id_to_name"),
    }


# =============================================================================
# Decode current state arrays
# =============================================================================

def decode_person_state_records(state):
    """
    Decode person_state/person_static into readable person records.
    """
    person_state = state.dynamic.person_state
    person_static = state.static.person_static

    maps = _entity_maps(state)
    type_maps = _get_type_maps(state)

    records = []

    for i in range(person_state.shape[0]):
        row = person_state[i, :]
        static_row = person_static[i, :]

        person_index = _to_int(row[schema.PERSON_ID])

        record = {
            "person_id": _decode_from_mapping(person_index, maps["person"], "person"),
            "person_index": person_index,

            "dwelling_id": _decode_from_mapping(
                row[schema.PERSON_DWELLING_ID],
                maps["dwelling"],
                "dwelling",
            ),
            "current_zone_id": _decode_from_mapping(
                row[schema.PERSON_CURRENT_ZONE_ID],
                maps["zone"],
                "zone",
            ),
            "previous_zone_id": _decode_from_mapping(
                row[schema.PERSON_PREVIOUS_ZONE_ID],
                maps["zone"],
                "zone",
            ),

            "is_home": _to_bool(row[schema.PERSON_IS_HOME]),
            "occupancy_state": _decode_type(
                row[schema.PERSON_OCCUPANCY_STATE],
                type_maps["occupancy_state"],
                "occupancy_state",
            ),

            "hunger": _to_float(row[schema.PERSON_HUNGER]),
            "fatigue": _to_float(row[schema.PERSON_FATIGUE]),
            "dirty_clothes": _to_float(row[schema.PERSON_DIRTY_CLOTHES]),
            "sickness": _to_float(row[schema.PERSON_SICKNESS]),
            "laziness": _to_float(row[schema.PERSON_LAZINESS]),

            "thermal_stress": _to_float(row[schema.PERSON_THERMAL_STRESS]),
            "air_quality_stress": _to_float(row[schema.PERSON_AIR_QUALITY_STRESS]),
            "visual_stress": _to_float(row[schema.PERSON_VISUAL_STRESS]),
            "acoustic_stress": _to_float(row[schema.PERSON_ACOUSTIC_STRESS]),
            "total_discomfort": _to_float(row[schema.PERSON_TOTAL_DISCOMFORT]),

            "current_action_type": _decode_type(
                row[schema.PERSON_CURRENT_ACTION_TYPE],
                type_maps["action_type"],
                "action_type",
            ),
            "current_action_id": _decode_from_mapping(
                row[schema.PERSON_CURRENT_ACTION_ID],
                maps["action"],
                "action",
            ),
            "action_target_zone_id": _decode_from_mapping(
                row[schema.PERSON_ACTION_TARGET_ZONE_ID],
                maps["zone"],
                "zone",
            ),
            "action_target_system_id": _decode_from_mapping(
                row[schema.PERSON_ACTION_TARGET_SYSTEM_ID],
                maps["system"],
                "system",
            ),
            "action_time_left_min": _to_float(row[schema.PERSON_ACTION_TIME_LEFT_MIN]),

            "current_power_W": _to_float(row[schema.PERSON_CURRENT_POWER_W]),
            "current_heat_gain_W": _to_float(row[schema.PERSON_CURRENT_HEAT_GAIN_W]),
            "current_co2_gain_kg_s": _to_float(row[schema.PERSON_CURRENT_CO2_GAIN_KG_S]),
            "current_moisture_gain_kg_s": _to_float(row[schema.PERSON_CURRENT_MOISTURE_GAIN_KG_S]),

            "home_zone_id": _decode_from_mapping(
                static_row[schema.PERSON_STATIC_HOME_ZONE_ID],
                maps["zone"],
                "zone",
            ),
            "sleep_zone_id": _decode_from_mapping(
                static_row[schema.PERSON_STATIC_SLEEP_ZONE_ID],
                maps["zone"],
                "zone",
            ),
            "work_zone_id": _decode_from_mapping(
                static_row[schema.PERSON_STATIC_WORK_ZONE_ID],
                maps["zone"],
                "zone",
            ),

            "cold_sensitivity": _to_float(static_row[schema.PERSON_STATIC_COLD_SENSITIVITY]),
            "heat_sensitivity": _to_float(static_row[schema.PERSON_STATIC_HEAT_SENSITIVITY]),
            "co2_sensitivity": _to_float(static_row[schema.PERSON_STATIC_CO2_SENSITIVITY]),
            "light_sensitivity": _to_float(static_row[schema.PERSON_STATIC_LIGHT_SENSITIVITY]),
            "noise_sensitivity": _to_float(static_row[schema.PERSON_STATIC_NOISE_SENSITIVITY]),
            "action_friction": _to_float(static_row[schema.PERSON_STATIC_ACTION_FRICTION]),

            "metabolic_heat_W": _to_float(static_row[schema.PERSON_STATIC_METABOLIC_HEAT_W]),
            "has_job": _to_bool(static_row[schema.PERSON_STATIC_HAS_JOB]),
            "usual_wake_minute": _to_float(static_row[schema.PERSON_STATIC_USUAL_WAKE_MINUTE]),
            "usual_sleep_minute": _to_float(static_row[schema.PERSON_STATIC_USUAL_SLEEP_MINUTE]),
            "work_start_minute": _to_float(static_row[schema.PERSON_STATIC_WORK_START_MINUTE]),
            "work_end_minute": _to_float(static_row[schema.PERSON_STATIC_WORK_END_MINUTE]),
        }

        records.append(record)

    return records


def decode_zone_state_records(state):
    """
    Decode zone_state/zone_static into readable zone records.
    """
    zone_state = state.dynamic.zone_state
    zone_static = state.static.zone_static

    maps = _entity_maps(state)
    type_maps = _get_type_maps(state)

    records = []

    for i in range(zone_state.shape[0]):
        row = zone_state[i, :]
        static_row = zone_static[i, :]

        zone_index = _to_int(row[schema.ZONE_ID])

        record = {
            "zone_id": _decode_from_mapping(zone_index, maps["zone"], "zone"),
            "zone_index": zone_index,

            "dwelling_id": _decode_from_mapping(
                row[schema.ZONE_DWELLING_ID],
                maps["dwelling"],
                "dwelling",
            ),
            "building_id": _decode_from_mapping(
                row[schema.ZONE_BUILDING_ID],
                maps["building"],
                "building",
            ),
            "zone_type": _decode_type(
                row[schema.ZONE_TYPE],
                type_maps["zone_type"],
                "zone_type",
            ),

            "air_temperature_C": _to_float(row[schema.ZONE_AIR_TEMPERATURE_C]),
            "mean_radiant_temperature_C": _to_float(row[schema.ZONE_MEAN_RADIANT_TEMPERATURE_C]),
            "relative_humidity": _to_float(row[schema.ZONE_RELATIVE_HUMIDITY]),
            "co2_ppm": _to_float(row[schema.ZONE_CO2_PPM]),
            "illuminance_lux": _to_float(row[schema.ZONE_ILLUMINANCE_LUX]),
            "noise_db": _to_float(row[schema.ZONE_NOISE_DB]),

            "occupant_count": _to_float(row[schema.ZONE_OCCUPANT_COUNT]),
            "is_occupied": _to_bool(row[schema.ZONE_IS_OCCUPIED]),

            "internal_heat_gain_W": _to_float(row[schema.ZONE_INTERNAL_HEAT_GAIN_W]),
            "solar_gain_W": _to_float(row[schema.ZONE_SOLAR_GAIN_W]),
            "lighting_gain_W": _to_float(row[schema.ZONE_LIGHTING_GAIN_W]),
            "appliance_gain_W": _to_float(row[schema.ZONE_APPLIANCE_GAIN_W]),
            "people_gain_W": _to_float(row[schema.ZONE_PEOPLE_GAIN_W]),
            "co2_gain_kg_s": _to_float(row[schema.ZONE_CO2_GAIN_KG_S]),
            "moisture_gain_kg_s": _to_float(row[schema.ZONE_MOISTURE_GAIN_KG_S]),

            "outdoor_airflow_m3_s": _to_float(row[schema.ZONE_OUTDOOR_AIRFLOW_M3_S]),
            "interzone_airflow_m3_s": _to_float(row[schema.ZONE_INTERZONE_AIRFLOW_M3_S]),
            "infiltration_airflow_m3_s": _to_float(row[schema.ZONE_INFILTRATION_AIRFLOW_M3_S]),

            "floor_area_m2": _to_float(static_row[schema.ZONE_STATIC_FLOOR_AREA_M2]),
            "volume_m3": _to_float(static_row[schema.ZONE_STATIC_VOLUME_M3]),
            "height_m": _to_float(static_row[schema.ZONE_STATIC_HEIGHT_M]),
            "heat_capacity_J_K": _to_float(static_row[schema.ZONE_STATIC_HEAT_CAPACITY_J_K]),
            "ua_envelope_W_K": _to_float(static_row[schema.ZONE_STATIC_UA_ENVELOPE_W_K]),
            "ua_internal_W_K": _to_float(static_row[schema.ZONE_STATIC_UA_INTERNAL_W_K]),
            "min_comfort_temp_C": _to_float(static_row[schema.ZONE_STATIC_MIN_COMFORT_TEMP_C]),
            "max_comfort_temp_C": _to_float(static_row[schema.ZONE_STATIC_MAX_COMFORT_TEMP_C]),
            "min_illuminance_lux": _to_float(static_row[schema.ZONE_STATIC_MIN_ILLUMINANCE_LUX]),
            "max_co2_ppm": _to_float(static_row[schema.ZONE_STATIC_MAX_CO2_PPM]),
            "max_noise_db": _to_float(static_row[schema.ZONE_STATIC_MAX_NOISE_DB]),
        }

        records.append(record)

    return records


def decode_dwelling_state_records(state):
    """
    Decode dwelling state/static arrays.
    """
    dwelling_state = state.dynamic.dwelling_state
    dwelling_static = state.static.dwelling_static

    maps = _entity_maps(state)

    records = []

    for i in range(dwelling_state.shape[0]):
        row = dwelling_state[i, :]
        static_row = dwelling_static[i, :]

        dwelling_index = _to_int(row[schema.DWELLING_ID])

        record = {
            "dwelling_id": _decode_from_mapping(
                dwelling_index,
                maps["dwelling"],
                "dwelling",
            ),
            "dwelling_index": dwelling_index,
            "building_id": _decode_from_mapping(
                row[schema.DWELLING_BUILDING_ID],
                maps["building"],
                "building",
            ),

            "occupant_count": _to_float(row[schema.DWELLING_OCCUPANT_COUNT]),
            "is_occupied": _to_bool(row[schema.DWELLING_IS_OCCUPIED]),

            "total_power_W": _to_float(row[schema.DWELLING_TOTAL_POWER_W]),
            "total_heat_gain_W": _to_float(row[schema.DWELLING_TOTAL_HEAT_GAIN_W]),
            "total_co2_gain_kg_s": _to_float(row[schema.DWELLING_TOTAL_CO2_GAIN_KG_S]),
            "total_moisture_gain_kg_s": _to_float(row[schema.DWELLING_TOTAL_MOISTURE_GAIN_KG_S]),

            "total_heating_demand_W": _to_float(row[schema.DWELLING_TOTAL_HEATING_DEMAND_W]),
            "total_cooling_demand_W": _to_float(row[schema.DWELLING_TOTAL_COOLING_DEMAND_W]),
            "total_electricity_demand_W": _to_float(row[schema.DWELLING_TOTAL_ELECTRICITY_DEMAND_W]),

            "first_zone_id": _decode_from_mapping(
                static_row[schema.DWELLING_STATIC_FIRST_ZONE_ID],
                maps["zone"],
                "zone",
            ),
            "n_zones": _to_int(static_row[schema.DWELLING_STATIC_N_ZONES]),
            "first_person_id": _decode_from_mapping(
                static_row[schema.DWELLING_STATIC_FIRST_PERSON_ID],
                maps["person"],
                "person",
            ),
            "n_persons": _to_int(static_row[schema.DWELLING_STATIC_N_PERSONS]),
            "floor_area_m2": _to_float(static_row[schema.DWELLING_STATIC_FLOOR_AREA_M2]),
            "volume_m3": _to_float(static_row[schema.DWELLING_STATIC_VOLUME_M3]),
        }

        records.append(record)

    return records


def decode_building_state_records(state):
    """
    Decode building state/static arrays.
    """
    building_state = state.dynamic.building_state
    building_static = state.static.building_static

    maps = _entity_maps(state)

    records = []

    for i in range(building_state.shape[0]):
        row = building_state[i, :]
        static_row = building_static[i, :]

        building_index = _to_int(row[schema.BUILDING_ID])

        record = {
            "building_id": _decode_from_mapping(
                building_index,
                maps["building"],
                "building",
            ),
            "building_index": building_index,

            "occupant_count": _to_float(row[schema.BUILDING_OCCUPANT_COUNT]),
            "is_occupied": _to_bool(row[schema.BUILDING_IS_OCCUPIED]),

            "total_power_W": _to_float(row[schema.BUILDING_TOTAL_POWER_W]),
            "total_heating_demand_W": _to_float(row[schema.BUILDING_TOTAL_HEATING_DEMAND_W]),
            "total_cooling_demand_W": _to_float(row[schema.BUILDING_TOTAL_COOLING_DEMAND_W]),
            "total_electricity_demand_W": _to_float(row[schema.BUILDING_TOTAL_ELECTRICITY_DEMAND_W]),

            "first_dwelling_id": _decode_from_mapping(
                static_row[schema.BUILDING_STATIC_FIRST_DWELLING_ID],
                maps["dwelling"],
                "dwelling",
            ),
            "n_dwellings": _to_int(static_row[schema.BUILDING_STATIC_N_DWELLINGS]),
            "first_zone_id": _decode_from_mapping(
                static_row[schema.BUILDING_STATIC_FIRST_ZONE_ID],
                maps["zone"],
                "zone",
            ),
            "n_zones": _to_int(static_row[schema.BUILDING_STATIC_N_ZONES]),
            "floor_area_m2": _to_float(static_row[schema.BUILDING_STATIC_FLOOR_AREA_M2]),
            "volume_m3": _to_float(static_row[schema.BUILDING_STATIC_VOLUME_M3]),
            "height_m": _to_float(static_row[schema.BUILDING_STATIC_HEIGHT_M]),
            "n_floors": _to_float(static_row[schema.BUILDING_STATIC_N_FLOORS]),
        }

        records.append(record)

    return records


def decode_system_state_records(state):
    """
    Decode system_state/system_static into readable system records.
    """
    system_state = state.dynamic.system_state
    system_static = state.static.system_static

    maps = _entity_maps(state)
    type_maps = _get_type_maps(state)

    records = []

    for i in range(system_state.shape[0]):
        row = system_state[i, :]
        static_row = system_static[i, :]

        system_index = _to_int(row[schema.SYSTEM_ID])

        record = {
            "system_id": _decode_from_mapping(system_index, maps["system"], "system"),
            "system_index": system_index,

            "dwelling_id": _decode_from_mapping(
                row[schema.SYSTEM_DWELLING_ID],
                maps["dwelling"],
                "dwelling",
            ),
            "zone_id": _decode_from_mapping(
                row[schema.SYSTEM_ZONE_ID],
                maps["zone"],
                "zone",
            ),

            "hvac_mode": _decode_type(
                row[schema.SYSTEM_HVAC_MODE],
                type_maps["hvac_mode"],
                "hvac_mode",
            ),
            "heating_setpoint_C": _to_float(row[schema.SYSTEM_HEATING_SETPOINT_C]),
            "cooling_setpoint_C": _to_float(row[schema.SYSTEM_COOLING_SETPOINT_C]),
            "heating_power_W": _to_float(row[schema.SYSTEM_HEATING_POWER_W]),
            "cooling_power_W": _to_float(row[schema.SYSTEM_COOLING_POWER_W]),

            "window_state": "open"
            if _to_int(row[schema.SYSTEM_WINDOW_STATE]) == schema.WINDOW_STATE_OPEN
            else "closed",
            "window_open_fraction": _to_float(row[schema.SYSTEM_WINDOW_OPEN_FRACTION]),

            "light_state": "on"
            if _to_int(row[schema.SYSTEM_LIGHT_STATE]) == schema.LIGHT_STATE_ON
            else "off",
            "lighting_power_W": _to_float(row[schema.SYSTEM_LIGHTING_POWER_W]),

            "blind_state": _decode_blind_state(row[schema.SYSTEM_BLIND_STATE]),
            "blind_closed_fraction": _to_float(row[schema.SYSTEM_BLIND_CLOSED_FRACTION]),

            "ventilation_mode": _decode_type(
                row[schema.SYSTEM_VENTILATION_MODE],
                type_maps["ventilation_mode"],
                "ventilation_mode",
            ),
            "mechanical_ventilation_flow_m3_s": _to_float(
                row[schema.SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S]
            ),

            "has_heating": _to_bool(static_row[schema.SYSTEM_STATIC_HAS_HEATING]),
            "has_cooling": _to_bool(static_row[schema.SYSTEM_STATIC_HAS_COOLING]),
            "has_window": _to_bool(static_row[schema.SYSTEM_STATIC_HAS_WINDOW]),
            "has_lights": _to_bool(static_row[schema.SYSTEM_STATIC_HAS_LIGHTS]),
            "has_blinds": _to_bool(static_row[schema.SYSTEM_STATIC_HAS_BLINDS]),
            "has_mech_ventilation": _to_bool(static_row[schema.SYSTEM_STATIC_HAS_MECH_VENTILATION]),

            "max_heating_power_W": _to_float(static_row[schema.SYSTEM_STATIC_MAX_HEATING_POWER_W]),
            "max_cooling_power_W": _to_float(static_row[schema.SYSTEM_STATIC_MAX_COOLING_POWER_W]),
            "max_lighting_power_W": _to_float(static_row[schema.SYSTEM_STATIC_MAX_LIGHTING_POWER_W]),
            "max_window_flow_m3_s": _to_float(static_row[schema.SYSTEM_STATIC_MAX_WINDOW_FLOW_M3_S]),
            "max_mech_vent_flow_m3_s": _to_float(static_row[schema.SYSTEM_STATIC_MAX_MECH_VENT_FLOW_M3_S]),
            "default_heating_setpoint_C": _to_float(
                static_row[schema.SYSTEM_STATIC_DEFAULT_HEATING_SETPOINT_C]
            ),
            "default_cooling_setpoint_C": _to_float(
                static_row[schema.SYSTEM_STATIC_DEFAULT_COOLING_SETPOINT_C]
            ),
        }

        records.append(record)

    return records


def _decode_blind_state(value):
    integer_id = _to_int(value)

    if integer_id == schema.BLIND_STATE_OPEN:
        return "open"
    if integer_id == schema.BLIND_STATE_CLOSED:
        return "closed"
    if integer_id == schema.BLIND_STATE_PARTIAL:
        return "partial"

    return "blind_state_%s" % integer_id


def decode_action_static_records(state):
    """
    Decode action_static into readable action records.
    """
    action_static = state.static.action_static

    maps = _entity_maps(state)
    type_maps = _get_type_maps(state)

    records = []

    for i in range(action_static.shape[0]):
        row = action_static[i, :]

        action_index = _to_int(row[schema.ACTION_ID])

        record = {
            "action_id": _decode_from_mapping(action_index, maps["action"], "action"),
            "action_index": action_index,
            "action_type": _decode_type(
                row[schema.ACTION_TYPE],
                type_maps["action_type"],
                "action_type",
            ),

            "default_target_zone_id": _decode_from_mapping(
                row[schema.ACTION_DEFAULT_TARGET_ZONE_ID],
                maps["zone"],
                "zone",
            ),
            "default_target_system_id": _decode_from_mapping(
                row[schema.ACTION_DEFAULT_TARGET_SYSTEM_ID],
                maps["system"],
                "system",
            ),
            "default_appliance_type": _decode_type(
                row[schema.ACTION_DEFAULT_APPLIANCE_TYPE],
                type_maps["appliance_type"],
                "appliance_type",
            ),

            "duration_min": _to_float(row[schema.ACTION_DURATION_MIN]),
            "can_run_while_away": _to_bool(row[schema.ACTION_CAN_RUN_WHILE_AWAY]),
            "is_background": _to_bool(row[schema.ACTION_IS_BACKGROUND]),
            "requires_home": _to_bool(row[schema.ACTION_REQUIRES_HOME]),
            "requires_awake": _to_bool(row[schema.ACTION_REQUIRES_AWAKE]),

            "power_W": _to_float(row[schema.ACTION_POWER_W]),
            "heat_gain_W": _to_float(row[schema.ACTION_HEAT_GAIN_W]),
            "co2_gain_kg_s": _to_float(row[schema.ACTION_CO2_GAIN_KG_S]),
            "moisture_gain_kg_s": _to_float(row[schema.ACTION_MOISTURE_GAIN_KG_S]),

            "hunger_effect": _to_float(row[schema.ACTION_HUNGER_EFFECT]),
            "fatigue_effect": _to_float(row[schema.ACTION_FATIGUE_EFFECT]),
            "dirty_clothes_effect": _to_float(row[schema.ACTION_DIRTY_CLOTHES_EFFECT]),
            "comfort_effect": _to_float(row[schema.ACTION_COMFORT_EFFECT]),
            "friction": _to_float(row[schema.ACTION_FRICTION]),
        }

        records.append(record)

    return records


def decode_process_state_records(state, include_inactive=True):
    """
    Decode background process state.
    """
    process_state = state.dynamic.process_state

    maps = _entity_maps(state)
    type_maps = _get_type_maps(state)

    records = []

    for i in range(process_state.shape[0]):
        row = process_state[i, :]

        process_status = _to_int(row[schema.PROCESS_STATE])
        if not include_inactive and process_status == schema.PROCESS_STATE_INACTIVE:
            continue

        record = {
            "process_id": _to_int(row[schema.PROCESS_ID]),
            "process_type": _decode_type(
                row[schema.PROCESS_TYPE],
                type_maps["process_type"],
                "process_type",
            ),
            "process_state": _decode_type(
                row[schema.PROCESS_STATE],
                type_maps["process_state"],
                "process_state",
            ),
            "person_id": _decode_from_mapping(
                row[schema.PROCESS_PERSON_ID],
                maps["person"],
                "person",
            ),
            "dwelling_id": _decode_from_mapping(
                row[schema.PROCESS_DWELLING_ID],
                maps["dwelling"],
                "dwelling",
            ),
            "zone_id": _decode_from_mapping(
                row[schema.PROCESS_ZONE_ID],
                maps["zone"],
                "zone",
            ),
            "system_id": _decode_from_mapping(
                row[schema.PROCESS_SYSTEM_ID],
                maps["system"],
                "system",
            ),
            "time_left_min": _to_float(row[schema.PROCESS_TIME_LEFT_MIN]),
            "total_duration_min": _to_float(row[schema.PROCESS_TOTAL_DURATION_MIN]),
            "power_W": _to_float(row[schema.PROCESS_POWER_W]),
            "heat_gain_W": _to_float(row[schema.PROCESS_HEAT_GAIN_W]),
            "co2_gain_kg_s": _to_float(row[schema.PROCESS_CO2_GAIN_KG_S]),
            "moisture_gain_kg_s": _to_float(row[schema.PROCESS_MOISTURE_GAIN_KG_S]),
        }

        records.append(record)

    return records


def decode_weather_state_record(state):
    row = state.dynamic.weather_state

    return {
        "outdoor_temperature_C": _to_float(row[schema.WEATHER_OUTDOOR_TEMPERATURE_C]),
        "outdoor_relative_humidity": _to_float(row[schema.WEATHER_OUTDOOR_RELATIVE_HUMIDITY]),
        "outdoor_co2_ppm": _to_float(row[schema.WEATHER_OUTDOOR_CO2_PPM]),
        "ghi_W_m2": _to_float(row[schema.WEATHER_GLOBAL_HORIZONTAL_IRRADIANCE_W_M2]),
        "dni_W_m2": _to_float(row[schema.WEATHER_DIRECT_NORMAL_IRRADIANCE_W_M2]),
        "dhi_W_m2": _to_float(row[schema.WEATHER_DIFFUSE_HORIZONTAL_IRRADIANCE_W_M2]),
        "wind_speed_m_s": _to_float(row[schema.WEATHER_WIND_SPEED_M_S]),
        "wind_direction_deg": _to_float(row[schema.WEATHER_WIND_DIRECTION_DEG]),
        "sky_temperature_C": _to_float(row[schema.WEATHER_SKY_TEMPERATURE_C]),
        "rain": _to_bool(row[schema.WEATHER_RAIN_FLAG]),
    }


def decode_time_state_record(state):
    row = state.dynamic.time_state

    return {
        "time_step_index": _to_int(row[schema.TIME_STEP_INDEX]),
        "elapsed_min": _to_float(row[schema.TIME_ELAPSED_MIN]),
        "minute_of_day": _to_float(row[schema.TIME_MINUTE_OF_DAY]),
        "hour_of_day": _to_int(row[schema.TIME_HOUR_OF_DAY]),
        "day_index": _to_int(row[schema.TIME_DAY_INDEX]),
        "day_of_week": _to_int(row[schema.TIME_DAY_OF_WEEK]),
        "month": _to_int(row[schema.TIME_MONTH]),
        "is_weekend": _to_bool(row[schema.TIME_IS_WEEKEND]),
    }


def decode_simulation_state(state, include_inactive_processes=True):
    """
    Decode a full current SimulationArrayState into human-readable records.
    """
    state.validate()

    return DecodedSimulationState(
        persons=decode_person_state_records(state),
        zones=decode_zone_state_records(state),
        dwellings=decode_dwelling_state_records(state),
        buildings=decode_building_state_records(state),
        systems=decode_system_state_records(state),
        actions=decode_action_static_records(state),
        processes=decode_process_state_records(
            state,
            include_inactive=include_inactive_processes,
        ),
        weather=decode_weather_state_record(state),
        time=decode_time_state_record(state),
    )


# =============================================================================
# DataFrame helpers
# =============================================================================

def _require_pandas():
    try:
        import pandas as pd
    except ImportError:
        raise ImportError(
            "pandas is required for DataFrame/CSV decoding. "
            "Install pandas or use the record-decoding functions instead."
        )

    return pd


def decoded_state_to_dataframes(decoded_state):
    """
    Convert DecodedSimulationState into a dict of pandas DataFrames.
    """
    pd = _require_pandas()

    return {
        "persons": pd.DataFrame(decoded_state.persons),
        "zones": pd.DataFrame(decoded_state.zones),
        "dwellings": pd.DataFrame(decoded_state.dwellings),
        "buildings": pd.DataFrame(decoded_state.buildings),
        "systems": pd.DataFrame(decoded_state.systems),
        "actions": pd.DataFrame(decoded_state.actions),
        "processes": pd.DataFrame(decoded_state.processes),
        "weather": pd.DataFrame([decoded_state.weather]),
        "time": pd.DataFrame([decoded_state.time]),
    }


def simulation_state_to_dataframes(state):
    """
    Decode state and return DataFrames.
    """
    decoded = decode_simulation_state(state)
    return decoded_state_to_dataframes(decoded)


def export_decoded_state_to_csv(decoded_state, output_dir):
    """
    Export decoded current state to CSV files.

    This exports human-readable decoded tables, not raw core arrays.
    """
    os.makedirs(output_dir, exist_ok=True)

    dataframes = decoded_state_to_dataframes(decoded_state)

    for name, dataframe in dataframes.items():
        path = os.path.join(output_dir, "%s.csv" % name)
        dataframe.to_csv(path, index=False)

    return True


def export_state_to_csv(state, output_dir):
    """
    Decode a SimulationArrayState and export readable CSV files.
    """
    decoded = decode_simulation_state(state)
    return export_decoded_state_to_csv(decoded, output_dir)


# =============================================================================
# Log decoding helpers
# =============================================================================

def _require_3d_log(log_array, expected_cols, name):
    if log_array is None:
        return

    if not isinstance(log_array, np.ndarray):
        raise TypeError("%s must be a numpy array." % name)

    if log_array.ndim != 3:
        raise ValueError("%s must be 3D. Got shape %s." % (name, str(log_array.shape)))

    if log_array.shape[2] != expected_cols:
        raise ValueError(
            "%s has wrong number of columns. Expected %s, got %s."
            % (name, expected_cols, log_array.shape[2])
        )


def decode_person_log_records(state, person_log):
    """
    Decode person_log[t, person_i, variable_j] to readable records.
    """
    _require_3d_log(person_log, schema.N_PERSON_LOG_COLS, "person_log")

    maps = _entity_maps(state)
    type_maps = _get_type_maps(state)

    records = []

    for t in range(person_log.shape[0]):
        for i in range(person_log.shape[1]):
            row = person_log[t, i, :]

            record = {
                "time_index": _to_int(row[schema.PERSON_LOG_TIME_INDEX]),
                "person_id": _decode_from_mapping(
                    row[schema.PERSON_LOG_PERSON_ID],
                    maps["person"],
                    "person",
                ),
                "dwelling_id": _decode_from_mapping(
                    row[schema.PERSON_LOG_DWELLING_ID],
                    maps["dwelling"],
                    "dwelling",
                ),
                "zone_id": _decode_from_mapping(
                    row[schema.PERSON_LOG_ZONE_ID],
                    maps["zone"],
                    "zone",
                ),
                "is_home": _to_bool(row[schema.PERSON_LOG_IS_HOME]),
                "occupancy_state": _decode_type(
                    row[schema.PERSON_LOG_OCCUPANCY_STATE],
                    type_maps["occupancy_state"],
                    "occupancy_state",
                ),
                "hunger": _to_float(row[schema.PERSON_LOG_HUNGER]),
                "fatigue": _to_float(row[schema.PERSON_LOG_FATIGUE]),
                "dirty_clothes": _to_float(row[schema.PERSON_LOG_DIRTY_CLOTHES]),
                "sickness": _to_float(row[schema.PERSON_LOG_SICKNESS]),
                "thermal_stress": _to_float(row[schema.PERSON_LOG_THERMAL_STRESS]),
                "air_quality_stress": _to_float(row[schema.PERSON_LOG_AIR_QUALITY_STRESS]),
                "visual_stress": _to_float(row[schema.PERSON_LOG_VISUAL_STRESS]),
                "acoustic_stress": _to_float(row[schema.PERSON_LOG_ACOUSTIC_STRESS]),
                "total_discomfort": _to_float(row[schema.PERSON_LOG_TOTAL_DISCOMFORT]),
                "action_type": _decode_type(
                    row[schema.PERSON_LOG_ACTION_TYPE],
                    type_maps["action_type"],
                    "action_type",
                ),
                "action_id": _decode_from_mapping(
                    row[schema.PERSON_LOG_ACTION_ID],
                    maps["action"],
                    "action",
                ),
                "action_time_left_min": _to_float(row[schema.PERSON_LOG_ACTION_TIME_LEFT_MIN]),
                "power_W": _to_float(row[schema.PERSON_LOG_POWER_W]),
                "heat_gain_W": _to_float(row[schema.PERSON_LOG_HEAT_GAIN_W]),
                "co2_gain_kg_s": _to_float(row[schema.PERSON_LOG_CO2_GAIN_KG_S]),
                "moisture_gain_kg_s": _to_float(row[schema.PERSON_LOG_MOISTURE_GAIN_KG_S]),
            }

            records.append(record)

    return records


def decode_zone_log_records(state, zone_log):
    """
    Decode zone_log[t, zone_i, variable_j].
    """
    _require_3d_log(zone_log, schema.N_ZONE_LOG_COLS, "zone_log")

    maps = _entity_maps(state)

    records = []

    for t in range(zone_log.shape[0]):
        for i in range(zone_log.shape[1]):
            row = zone_log[t, i, :]

            record = {
                "time_index": _to_int(row[schema.ZONE_LOG_TIME_INDEX]),
                "zone_id": _decode_from_mapping(row[schema.ZONE_LOG_ZONE_ID], maps["zone"], "zone"),
                "dwelling_id": _decode_from_mapping(
                    row[schema.ZONE_LOG_DWELLING_ID],
                    maps["dwelling"],
                    "dwelling",
                ),
                "building_id": _decode_from_mapping(
                    row[schema.ZONE_LOG_BUILDING_ID],
                    maps["building"],
                    "building",
                ),
                "air_temperature_C": _to_float(row[schema.ZONE_LOG_AIR_TEMPERATURE_C]),
                "mean_radiant_temperature_C": _to_float(
                    row[schema.ZONE_LOG_MEAN_RADIANT_TEMPERATURE_C]
                ),
                "relative_humidity": _to_float(row[schema.ZONE_LOG_RELATIVE_HUMIDITY]),
                "co2_ppm": _to_float(row[schema.ZONE_LOG_CO2_PPM]),
                "illuminance_lux": _to_float(row[schema.ZONE_LOG_ILLUMINANCE_LUX]),
                "noise_db": _to_float(row[schema.ZONE_LOG_NOISE_DB]),
                "occupant_count": _to_float(row[schema.ZONE_LOG_OCCUPANT_COUNT]),
                "is_occupied": _to_bool(row[schema.ZONE_LOG_IS_OCCUPIED]),
                "internal_heat_gain_W": _to_float(row[schema.ZONE_LOG_INTERNAL_HEAT_GAIN_W]),
                "solar_gain_W": _to_float(row[schema.ZONE_LOG_SOLAR_GAIN_W]),
                "lighting_gain_W": _to_float(row[schema.ZONE_LOG_LIGHTING_GAIN_W]),
                "appliance_gain_W": _to_float(row[schema.ZONE_LOG_APPLIANCE_GAIN_W]),
                "people_gain_W": _to_float(row[schema.ZONE_LOG_PEOPLE_GAIN_W]),
                "co2_gain_kg_s": _to_float(row[schema.ZONE_LOG_CO2_GAIN_KG_S]),
                "moisture_gain_kg_s": _to_float(row[schema.ZONE_LOG_MOISTURE_GAIN_KG_S]),
                "heating_demand_W": _to_float(row[schema.ZONE_LOG_HEATING_DEMAND_W]),
                "cooling_demand_W": _to_float(row[schema.ZONE_LOG_COOLING_DEMAND_W]),
            }

            records.append(record)

    return records


def decode_system_log_records(state, system_log):
    """
    Decode system_log[t, system_i, variable_j].
    """
    _require_3d_log(system_log, schema.N_SYSTEM_LOG_COLS, "system_log")

    maps = _entity_maps(state)
    type_maps = _get_type_maps(state)

    records = []

    for t in range(system_log.shape[0]):
        for i in range(system_log.shape[1]):
            row = system_log[t, i, :]

            record = {
                "time_index": _to_int(row[schema.SYSTEM_LOG_TIME_INDEX]),
                "system_id": _decode_from_mapping(
                    row[schema.SYSTEM_LOG_SYSTEM_ID],
                    maps["system"],
                    "system",
                ),
                "dwelling_id": _decode_from_mapping(
                    row[schema.SYSTEM_LOG_DWELLING_ID],
                    maps["dwelling"],
                    "dwelling",
                ),
                "zone_id": _decode_from_mapping(
                    row[schema.SYSTEM_LOG_ZONE_ID],
                    maps["zone"],
                    "zone",
                ),
                "hvac_mode": _decode_type(
                    row[schema.SYSTEM_LOG_HVAC_MODE],
                    type_maps["hvac_mode"],
                    "hvac_mode",
                ),
                "heating_setpoint_C": _to_float(row[schema.SYSTEM_LOG_HEATING_SETPOINT_C]),
                "cooling_setpoint_C": _to_float(row[schema.SYSTEM_LOG_COOLING_SETPOINT_C]),
                "heating_power_W": _to_float(row[schema.SYSTEM_LOG_HEATING_POWER_W]),
                "cooling_power_W": _to_float(row[schema.SYSTEM_LOG_COOLING_POWER_W]),
                "window_state": "open"
                if _to_int(row[schema.SYSTEM_LOG_WINDOW_STATE]) == schema.WINDOW_STATE_OPEN
                else "closed",
                "window_open_fraction": _to_float(row[schema.SYSTEM_LOG_WINDOW_OPEN_FRACTION]),
                "light_state": "on"
                if _to_int(row[schema.SYSTEM_LOG_LIGHT_STATE]) == schema.LIGHT_STATE_ON
                else "off",
                "lighting_power_W": _to_float(row[schema.SYSTEM_LOG_LIGHTING_POWER_W]),
                "blind_state": _decode_blind_state(row[schema.SYSTEM_LOG_BLIND_STATE]),
                "blind_closed_fraction": _to_float(row[schema.SYSTEM_LOG_BLIND_CLOSED_FRACTION]),
                "ventilation_mode": _decode_type(
                    row[schema.SYSTEM_LOG_VENTILATION_MODE],
                    type_maps["ventilation_mode"],
                    "ventilation_mode",
                ),
                "mechanical_ventilation_flow_m3_s": _to_float(
                    row[schema.SYSTEM_LOG_MECH_VENT_FLOW_M3_S]
                ),
            }

            records.append(record)

    return records


def decode_dwelling_log_records(state, dwelling_log):
    """
    Decode dwelling_log[t, dwelling_i, variable_j].
    """
    _require_3d_log(dwelling_log, schema.N_DWELLING_LOG_COLS, "dwelling_log")

    maps = _entity_maps(state)

    records = []

    for t in range(dwelling_log.shape[0]):
        for i in range(dwelling_log.shape[1]):
            row = dwelling_log[t, i, :]

            record = {
                "time_index": _to_int(row[schema.DWELLING_LOG_TIME_INDEX]),
                "dwelling_id": _decode_from_mapping(
                    row[schema.DWELLING_LOG_DWELLING_ID],
                    maps["dwelling"],
                    "dwelling",
                ),
                "building_id": _decode_from_mapping(
                    row[schema.DWELLING_LOG_BUILDING_ID],
                    maps["building"],
                    "building",
                ),
                "occupant_count": _to_float(row[schema.DWELLING_LOG_OCCUPANT_COUNT]),
                "is_occupied": _to_bool(row[schema.DWELLING_LOG_IS_OCCUPIED]),
                "total_power_W": _to_float(row[schema.DWELLING_LOG_TOTAL_POWER_W]),
                "total_heat_gain_W": _to_float(row[schema.DWELLING_LOG_TOTAL_HEAT_GAIN_W]),
                "total_co2_gain_kg_s": _to_float(row[schema.DWELLING_LOG_TOTAL_CO2_GAIN_KG_S]),
                "total_moisture_gain_kg_s": _to_float(
                    row[schema.DWELLING_LOG_TOTAL_MOISTURE_GAIN_KG_S]
                ),
                "heating_demand_W": _to_float(row[schema.DWELLING_LOG_HEATING_DEMAND_W]),
                "cooling_demand_W": _to_float(row[schema.DWELLING_LOG_COOLING_DEMAND_W]),
                "electricity_demand_W": _to_float(
                    row[schema.DWELLING_LOG_ELECTRICITY_DEMAND_W]
                ),
            }

            records.append(record)

    return records


def decode_building_log_records(state, building_log):
    """
    Decode building_log[t, building_i, variable_j].
    """
    _require_3d_log(building_log, schema.N_BUILDING_LOG_COLS, "building_log")

    maps = _entity_maps(state)

    records = []

    for t in range(building_log.shape[0]):
        for i in range(building_log.shape[1]):
            row = building_log[t, i, :]

            record = {
                "time_index": _to_int(row[schema.BUILDING_LOG_TIME_INDEX]),
                "building_id": _decode_from_mapping(
                    row[schema.BUILDING_LOG_BUILDING_ID],
                    maps["building"],
                    "building",
                ),
                "occupant_count": _to_float(row[schema.BUILDING_LOG_OCCUPANT_COUNT]),
                "is_occupied": _to_bool(row[schema.BUILDING_LOG_IS_OCCUPIED]),
                "total_power_W": _to_float(row[schema.BUILDING_LOG_TOTAL_POWER_W]),
                "heating_demand_W": _to_float(row[schema.BUILDING_LOG_HEATING_DEMAND_W]),
                "cooling_demand_W": _to_float(row[schema.BUILDING_LOG_COOLING_DEMAND_W]),
                "electricity_demand_W": _to_float(
                    row[schema.BUILDING_LOG_ELECTRICITY_DEMAND_W]
                ),
            }

            records.append(record)

    return records


def decode_logs_to_dataframes(
    state,
    person_log=None,
    zone_log=None,
    system_log=None,
    dwelling_log=None,
    building_log=None,
):
    """
    Decode available log arrays to pandas DataFrames.

    All decoding is outside the timestep loop.
    """
    pd = _require_pandas()

    result = {}

    if person_log is not None:
        result["person_log"] = pd.DataFrame(
            decode_person_log_records(state, person_log)
        )

    if zone_log is not None:
        result["zone_log"] = pd.DataFrame(
            decode_zone_log_records(state, zone_log)
        )

    if system_log is not None:
        result["system_log"] = pd.DataFrame(
            decode_system_log_records(state, system_log)
        )

    if dwelling_log is not None:
        result["dwelling_log"] = pd.DataFrame(
            decode_dwelling_log_records(state, dwelling_log)
        )

    if building_log is not None:
        result["building_log"] = pd.DataFrame(
            decode_building_log_records(state, building_log)
        )

    return result


def export_logs_to_csv(
    state,
    output_dir,
    person_log=None,
    zone_log=None,
    system_log=None,
    dwelling_log=None,
    building_log=None,
):
    """
    Decode log arrays and export readable CSV files.
    """
    os.makedirs(output_dir, exist_ok=True)

    dataframes = decode_logs_to_dataframes(
        state=state,
        person_log=person_log,
        zone_log=zone_log,
        system_log=system_log,
        dwelling_log=dwelling_log,
        building_log=building_log,
    )

    for name, dataframe in dataframes.items():
        path = os.path.join(output_dir, "%s.csv" % name)
        dataframe.to_csv(path, index=False)

    return True