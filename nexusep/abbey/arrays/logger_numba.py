"""
ABBEY numba logger kernels.

Only raw array writers live here.

Readable DataFrame decoding remains in logger.py / decoder.py.
"""

from nexusep.abbey.arrays import schema
from nexusep.abbey.arrays.numba_support import optional_njit


@optional_njit(cache=True)
def write_person_log_arrays_numba(
    person_state,
    person_log,
    time_index,
):
    for i in range(person_state.shape[0]):
        person_log[time_index, i, schema.PERSON_LOG_TIME_INDEX] = time_index
        person_log[time_index, i, schema.PERSON_LOG_PERSON_ID] = person_state[
            i,
            schema.PERSON_ID,
        ]
        person_log[time_index, i, schema.PERSON_LOG_DWELLING_ID] = person_state[
            i,
            schema.PERSON_DWELLING_ID,
        ]
        person_log[time_index, i, schema.PERSON_LOG_ZONE_ID] = person_state[
            i,
            schema.PERSON_CURRENT_ZONE_ID,
        ]
        person_log[time_index, i, schema.PERSON_LOG_IS_HOME] = person_state[
            i,
            schema.PERSON_IS_HOME,
        ]
        person_log[time_index, i, schema.PERSON_LOG_OCCUPANCY_STATE] = person_state[
            i,
            schema.PERSON_OCCUPANCY_STATE,
        ]

        person_log[time_index, i, schema.PERSON_LOG_HUNGER] = person_state[
            i,
            schema.PERSON_HUNGER,
        ]
        person_log[time_index, i, schema.PERSON_LOG_FATIGUE] = person_state[
            i,
            schema.PERSON_FATIGUE,
        ]
        person_log[time_index, i, schema.PERSON_LOG_DIRTY_CLOTHES] = person_state[
            i,
            schema.PERSON_DIRTY_CLOTHES,
        ]
        person_log[time_index, i, schema.PERSON_LOG_SICKNESS] = person_state[
            i,
            schema.PERSON_SICKNESS,
        ]

        person_log[time_index, i, schema.PERSON_LOG_THERMAL_STRESS] = person_state[
            i,
            schema.PERSON_THERMAL_STRESS,
        ]
        person_log[time_index, i, schema.PERSON_LOG_AIR_QUALITY_STRESS] = person_state[
            i,
            schema.PERSON_AIR_QUALITY_STRESS,
        ]
        person_log[time_index, i, schema.PERSON_LOG_VISUAL_STRESS] = person_state[
            i,
            schema.PERSON_VISUAL_STRESS,
        ]
        person_log[time_index, i, schema.PERSON_LOG_ACOUSTIC_STRESS] = person_state[
            i,
            schema.PERSON_ACOUSTIC_STRESS,
        ]
        person_log[time_index, i, schema.PERSON_LOG_TOTAL_DISCOMFORT] = person_state[
            i,
            schema.PERSON_TOTAL_DISCOMFORT,
        ]

        person_log[time_index, i, schema.PERSON_LOG_ACTION_TYPE] = person_state[
            i,
            schema.PERSON_CURRENT_ACTION_TYPE,
        ]
        person_log[time_index, i, schema.PERSON_LOG_ACTION_ID] = person_state[
            i,
            schema.PERSON_CURRENT_ACTION_ID,
        ]
        person_log[time_index, i, schema.PERSON_LOG_ACTION_TIME_LEFT_MIN] = person_state[
            i,
            schema.PERSON_ACTION_TIME_LEFT_MIN,
        ]

        person_log[time_index, i, schema.PERSON_LOG_POWER_W] = person_state[
            i,
            schema.PERSON_CURRENT_POWER_W,
        ]
        person_log[time_index, i, schema.PERSON_LOG_HEAT_GAIN_W] = person_state[
            i,
            schema.PERSON_CURRENT_HEAT_GAIN_W,
        ]
        person_log[time_index, i, schema.PERSON_LOG_CO2_GAIN_KG_S] = person_state[
            i,
            schema.PERSON_CURRENT_CO2_GAIN_KG_S,
        ]
        person_log[time_index, i, schema.PERSON_LOG_MOISTURE_GAIN_KG_S] = person_state[
            i,
            schema.PERSON_CURRENT_MOISTURE_GAIN_KG_S,
        ]

    return True


@optional_njit(cache=True)
def write_zone_log_arrays_numba(
    zone_state,
    physics_result,
    zone_log,
    time_index,
):
    for i in range(zone_state.shape[0]):
        zone_log[time_index, i, schema.ZONE_LOG_TIME_INDEX] = time_index
        zone_log[time_index, i, schema.ZONE_LOG_ZONE_ID] = zone_state[
            i,
            schema.ZONE_ID,
        ]
        zone_log[time_index, i, schema.ZONE_LOG_DWELLING_ID] = zone_state[
            i,
            schema.ZONE_DWELLING_ID,
        ]
        zone_log[time_index, i, schema.ZONE_LOG_BUILDING_ID] = zone_state[
            i,
            schema.ZONE_BUILDING_ID,
        ]

        zone_log[time_index, i, schema.ZONE_LOG_AIR_TEMPERATURE_C] = zone_state[
            i,
            schema.ZONE_AIR_TEMPERATURE_C,
        ]
        zone_log[time_index, i, schema.ZONE_LOG_MEAN_RADIANT_TEMPERATURE_C] = zone_state[
            i,
            schema.ZONE_MEAN_RADIANT_TEMPERATURE_C,
        ]
        zone_log[time_index, i, schema.ZONE_LOG_RELATIVE_HUMIDITY] = zone_state[
            i,
            schema.ZONE_RELATIVE_HUMIDITY,
        ]
        zone_log[time_index, i, schema.ZONE_LOG_CO2_PPM] = zone_state[
            i,
            schema.ZONE_CO2_PPM,
        ]
        zone_log[time_index, i, schema.ZONE_LOG_ILLUMINANCE_LUX] = zone_state[
            i,
            schema.ZONE_ILLUMINANCE_LUX,
        ]
        zone_log[time_index, i, schema.ZONE_LOG_NOISE_DB] = zone_state[
            i,
            schema.ZONE_NOISE_DB,
        ]

        zone_log[time_index, i, schema.ZONE_LOG_OCCUPANT_COUNT] = zone_state[
            i,
            schema.ZONE_OCCUPANT_COUNT,
        ]
        zone_log[time_index, i, schema.ZONE_LOG_IS_OCCUPIED] = zone_state[
            i,
            schema.ZONE_IS_OCCUPIED,
        ]

        zone_log[time_index, i, schema.ZONE_LOG_INTERNAL_HEAT_GAIN_W] = zone_state[
            i,
            schema.ZONE_INTERNAL_HEAT_GAIN_W,
        ]
        zone_log[time_index, i, schema.ZONE_LOG_SOLAR_GAIN_W] = zone_state[
            i,
            schema.ZONE_SOLAR_GAIN_W,
        ]
        zone_log[time_index, i, schema.ZONE_LOG_LIGHTING_GAIN_W] = zone_state[
            i,
            schema.ZONE_LIGHTING_GAIN_W,
        ]
        zone_log[time_index, i, schema.ZONE_LOG_APPLIANCE_GAIN_W] = zone_state[
            i,
            schema.ZONE_APPLIANCE_GAIN_W,
        ]
        zone_log[time_index, i, schema.ZONE_LOG_PEOPLE_GAIN_W] = zone_state[
            i,
            schema.ZONE_PEOPLE_GAIN_W,
        ]
        zone_log[time_index, i, schema.ZONE_LOG_CO2_GAIN_KG_S] = zone_state[
            i,
            schema.ZONE_CO2_GAIN_KG_S,
        ]
        zone_log[time_index, i, schema.ZONE_LOG_MOISTURE_GAIN_KG_S] = zone_state[
            i,
            schema.ZONE_MOISTURE_GAIN_KG_S,
        ]

        zone_log[time_index, i, schema.ZONE_LOG_HEATING_DEMAND_W] = physics_result[
            i,
            schema.PHYSICS_HEATING_DEMAND_W,
        ]
        zone_log[time_index, i, schema.ZONE_LOG_COOLING_DEMAND_W] = physics_result[
            i,
            schema.PHYSICS_COOLING_DEMAND_W,
        ]

    return True