"""
ABBEY array-core schema.

This module defines the numeric language of the ABBEY array simulation core.

Rules:
    - No strings in the timestep core.
    - No dataclasses in the timestep core.
    - No dicts in the timestep core.
    - All categories are integer IDs.
    - All state values live in numeric arrays.
    - Human-readable names are handled only by encoders/decoders outside the core.

Keep this file boring, explicit, and stable.
"""


# =============================================================================
# Generic constants
# =============================================================================

MISSING_ID = -1

FALSE = 0
TRUE = 1

OFF = 0
ON = 1


# =============================================================================
# Occupancy / presence state IDs
# =============================================================================

OCCUPANCY_UNKNOWN = -1
OCCUPANCY_AWAY = 0
OCCUPANCY_HOME_AWAKE = 1
OCCUPANCY_HOME_SLEEPING = 2
OCCUPANCY_TRANSITION = 3

N_OCCUPANCY_STATES = 4


# =============================================================================
# Zone / space type IDs
# =============================================================================

ZONE_TYPE_UNKNOWN = -1
ZONE_TYPE_OUTSIDE = 0
ZONE_TYPE_MAIN_ROOM = 1
ZONE_TYPE_BEDROOM = 2
ZONE_TYPE_KITCHEN = 3
ZONE_TYPE_BATHROOM = 4
ZONE_TYPE_LIVING_ROOM = 5
ZONE_TYPE_CORRIDOR = 6
ZONE_TYPE_STORAGE = 7
ZONE_TYPE_SHARED_SPACE = 8

N_ZONE_TYPES = 9


# =============================================================================
# System mode IDs
# =============================================================================

HVAC_MODE_OFF = 0
HVAC_MODE_HEATING = 1
HVAC_MODE_COOLING = 2
HVAC_MODE_AUTO = 3
HVAC_MODE_VENTILATION_ONLY = 4

N_HVAC_MODES = 5


VENTILATION_MODE_OFF = 0
VENTILATION_MODE_NATURAL = 1
VENTILATION_MODE_MECHANICAL = 2
VENTILATION_MODE_HYBRID = 3

N_VENTILATION_MODES = 4


WINDOW_STATE_CLOSED = 0
WINDOW_STATE_OPEN = 1

N_WINDOW_STATES = 2


LIGHT_STATE_OFF = 0
LIGHT_STATE_ON = 1

N_LIGHT_STATES = 2


BLIND_STATE_OPEN = 0
BLIND_STATE_CLOSED = 1
BLIND_STATE_PARTIAL = 2

N_BLIND_STATES = 3


# =============================================================================
# Action type IDs
# =============================================================================

ACTION_TYPE_NONE = 0

# Person/location actions
ACTION_TYPE_IDLE = 1
ACTION_TYPE_SLEEP = 2
ACTION_TYPE_WAKE_UP = 3
ACTION_TYPE_LEAVE_HOME = 4
ACTION_TYPE_RETURN_HOME = 5
ACTION_TYPE_MOVE_ZONE = 6

# Food / appliance / domestic actions
ACTION_TYPE_EAT = 10
ACTION_TYPE_COOK = 11
ACTION_TYPE_DRINK = 12
ACTION_TYPE_MAKE_COFFEE = 13
ACTION_TYPE_DO_LAUNDRY = 14
ACTION_TYPE_SHOWER = 15

# System/control actions
ACTION_TYPE_OPEN_WINDOW = 30
ACTION_TYPE_CLOSE_WINDOW = 31
ACTION_TYPE_TURN_LIGHT_ON = 32
ACTION_TYPE_TURN_LIGHT_OFF = 33
ACTION_TYPE_TURN_HEATING_ON = 34
ACTION_TYPE_TURN_HEATING_OFF = 35
ACTION_TYPE_TURN_COOLING_ON = 36
ACTION_TYPE_TURN_COOLING_OFF = 37
ACTION_TYPE_ADJUST_THERMOSTAT = 38
ACTION_TYPE_OPEN_BLINDS = 39
ACTION_TYPE_CLOSE_BLINDS = 40
ACTION_TYPE_TURN_VENTILATION_ON = 41
ACTION_TYPE_TURN_VENTILATION_OFF = 42

N_ACTION_TYPES = 43


# =============================================================================
# Background process type IDs
# =============================================================================

PROCESS_TYPE_NONE = 0
PROCESS_TYPE_WASHING_MACHINE = 1
PROCESS_TYPE_DISHWASHER = 2
PROCESS_TYPE_OVEN = 3
PROCESS_TYPE_STOVE = 4
PROCESS_TYPE_SHOWER = 5
PROCESS_TYPE_COOKING = 6
PROCESS_TYPE_COFFEE_MACHINE = 7

N_PROCESS_TYPES = 8


PROCESS_STATE_INACTIVE = 0
PROCESS_STATE_ACTIVE = 1
PROCESS_STATE_PAUSED = 2
PROCESS_STATE_FINISHED = 3

N_PROCESS_STATES = 4


# =============================================================================
# Appliance type IDs
# =============================================================================

APPLIANCE_TYPE_NONE = 0
APPLIANCE_TYPE_LIGHTS = 1
APPLIANCE_TYPE_WASHING_MACHINE = 2
APPLIANCE_TYPE_DISHWASHER = 3
APPLIANCE_TYPE_OVEN = 4
APPLIANCE_TYPE_STOVE = 5
APPLIANCE_TYPE_FRIDGE = 6
APPLIANCE_TYPE_COFFEE_MACHINE = 7
APPLIANCE_TYPE_COMPUTER = 8
APPLIANCE_TYPE_TV = 9
APPLIANCE_TYPE_SHOWER = 10

N_APPLIANCE_TYPES = 11


# =============================================================================
# Person dynamic state columns
# Shape:
#     person_state[n_persons, N_PERSON_STATE_COLS]
# =============================================================================

PERSON_ID = 0
PERSON_DWELLING_ID = 1
PERSON_CURRENT_ZONE_ID = 2
PERSON_PREVIOUS_ZONE_ID = 3
PERSON_IS_HOME = 4
PERSON_OCCUPANCY_STATE = 5

# Needs / internal state
PERSON_HUNGER = 6
PERSON_FATIGUE = 7
PERSON_DIRTY_CLOTHES = 8
PERSON_SICKNESS = 9
PERSON_LAZINESS = 10

# Perception / discomfort
PERSON_THERMAL_STRESS = 11
PERSON_AIR_QUALITY_STRESS = 12
PERSON_VISUAL_STRESS = 13
PERSON_ACOUSTIC_STRESS = 14
PERSON_TOTAL_DISCOMFORT = 15

# Action execution
PERSON_CURRENT_ACTION_TYPE = 16
PERSON_CURRENT_ACTION_ID = 17
PERSON_ACTION_TARGET_ZONE_ID = 18
PERSON_ACTION_TARGET_SYSTEM_ID = 19
PERSON_ACTION_TIME_LEFT_MIN = 20

# Energy / domestic behavior accumulation
PERSON_CURRENT_POWER_W = 21
PERSON_CURRENT_HEAT_GAIN_W = 22
PERSON_CURRENT_CO2_GAIN_KG_S = 23
PERSON_CURRENT_MOISTURE_GAIN_KG_S = 24

N_PERSON_STATE_COLS = 25


# =============================================================================
# Person static columns
# Shape:
#     person_static[n_persons, N_PERSON_STATIC_COLS]
# =============================================================================

PERSON_STATIC_ID = 0
PERSON_STATIC_DWELLING_ID = 1
PERSON_STATIC_HOME_ZONE_ID = 2
PERSON_STATIC_SLEEP_ZONE_ID = 3
PERSON_STATIC_WORK_ZONE_ID = 4

# Traits
PERSON_STATIC_COLD_SENSITIVITY = 5
PERSON_STATIC_HEAT_SENSITIVITY = 6
PERSON_STATIC_CO2_SENSITIVITY = 7
PERSON_STATIC_LIGHT_SENSITIVITY = 8
PERSON_STATIC_NOISE_SENSITIVITY = 9
PERSON_STATIC_ACTION_FRICTION = 10

# Metabolic / gains
PERSON_STATIC_METABOLIC_HEAT_W = 11
PERSON_STATIC_CO2_GAIN_KG_S = 12
PERSON_STATIC_MOISTURE_GAIN_KG_S = 13

# Schedule / behavior flags
PERSON_STATIC_HAS_JOB = 14
PERSON_STATIC_USUAL_WAKE_MINUTE = 15
PERSON_STATIC_USUAL_SLEEP_MINUTE = 16
PERSON_STATIC_WORK_START_MINUTE = 17
PERSON_STATIC_WORK_END_MINUTE = 18

N_PERSON_STATIC_COLS = 19


# =============================================================================
# Zone dynamic state columns
# Shape:
#     zone_state[n_zones, N_ZONE_STATE_COLS]
# =============================================================================

ZONE_ID = 0
ZONE_DWELLING_ID = 1
ZONE_BUILDING_ID = 2
ZONE_TYPE = 3

# Main environmental states
ZONE_AIR_TEMPERATURE_C = 4
ZONE_MEAN_RADIANT_TEMPERATURE_C = 5
ZONE_RELATIVE_HUMIDITY = 6
ZONE_CO2_PPM = 7
ZONE_ILLUMINANCE_LUX = 8
ZONE_NOISE_DB = 9

# Occupancy
ZONE_OCCUPANT_COUNT = 10
ZONE_IS_OCCUPIED = 11

# Current gains
ZONE_INTERNAL_HEAT_GAIN_W = 12
ZONE_SOLAR_GAIN_W = 13
ZONE_LIGHTING_GAIN_W = 14
ZONE_APPLIANCE_GAIN_W = 15
ZONE_PEOPLE_GAIN_W = 16
ZONE_CO2_GAIN_KG_S = 17
ZONE_MOISTURE_GAIN_KG_S = 18

# Airflow / ventilation
ZONE_OUTDOOR_AIRFLOW_M3_S = 19
ZONE_INTERZONE_AIRFLOW_M3_S = 20
ZONE_INFILTRATION_AIRFLOW_M3_S = 21

N_ZONE_STATE_COLS = 22


# =============================================================================
# Zone static columns
# Shape:
#     zone_static[n_zones, N_ZONE_STATIC_COLS]
# =============================================================================

ZONE_STATIC_ID = 0
ZONE_STATIC_DWELLING_ID = 1
ZONE_STATIC_BUILDING_ID = 2
ZONE_STATIC_TYPE = 3

# Geometry
ZONE_STATIC_FLOOR_AREA_M2 = 4
ZONE_STATIC_VOLUME_M3 = 5
ZONE_STATIC_HEIGHT_M = 6

# Thermal properties
ZONE_STATIC_HEAT_CAPACITY_J_K = 7
ZONE_STATIC_UA_ENVELOPE_W_K = 8
ZONE_STATIC_UA_INTERNAL_W_K = 9

# Environmental defaults / limits
ZONE_STATIC_MIN_COMFORT_TEMP_C = 10
ZONE_STATIC_MAX_COMFORT_TEMP_C = 11
ZONE_STATIC_MIN_ILLUMINANCE_LUX = 12
ZONE_STATIC_MAX_CO2_PPM = 13
ZONE_STATIC_MAX_NOISE_DB = 14

N_ZONE_STATIC_COLS = 15


# =============================================================================
# Dwelling dynamic state columns
# Shape:
#     dwelling_state[n_dwellings, N_DWELLING_STATE_COLS]
# =============================================================================

DWELLING_ID = 0
DWELLING_BUILDING_ID = 1

DWELLING_OCCUPANT_COUNT = 2
DWELLING_IS_OCCUPIED = 3

DWELLING_TOTAL_POWER_W = 4
DWELLING_TOTAL_HEAT_GAIN_W = 5
DWELLING_TOTAL_CO2_GAIN_KG_S = 6
DWELLING_TOTAL_MOISTURE_GAIN_KG_S = 7

DWELLING_TOTAL_HEATING_DEMAND_W = 8
DWELLING_TOTAL_COOLING_DEMAND_W = 9
DWELLING_TOTAL_ELECTRICITY_DEMAND_W = 10

N_DWELLING_STATE_COLS = 11


# =============================================================================
# Dwelling static columns
# Shape:
#     dwelling_static[n_dwellings, N_DWELLING_STATIC_COLS]
# =============================================================================

DWELLING_STATIC_ID = 0
DWELLING_STATIC_BUILDING_ID = 1
DWELLING_STATIC_FIRST_ZONE_ID = 2
DWELLING_STATIC_N_ZONES = 3
DWELLING_STATIC_FIRST_PERSON_ID = 4
DWELLING_STATIC_N_PERSONS = 5

DWELLING_STATIC_FLOOR_AREA_M2 = 6
DWELLING_STATIC_VOLUME_M3 = 7

N_DWELLING_STATIC_COLS = 8


# =============================================================================
# Building dynamic state columns
# Shape:
#     building_state[n_buildings, N_BUILDING_STATE_COLS]
# =============================================================================

BUILDING_ID = 0

BUILDING_OCCUPANT_COUNT = 1
BUILDING_IS_OCCUPIED = 2

BUILDING_TOTAL_POWER_W = 3
BUILDING_TOTAL_HEATING_DEMAND_W = 4
BUILDING_TOTAL_COOLING_DEMAND_W = 5
BUILDING_TOTAL_ELECTRICITY_DEMAND_W = 6

N_BUILDING_STATE_COLS = 7


# =============================================================================
# Building static columns
# Shape:
#     building_static[n_buildings, N_BUILDING_STATIC_COLS]
# =============================================================================

BUILDING_STATIC_ID = 0
BUILDING_STATIC_FIRST_DWELLING_ID = 1
BUILDING_STATIC_N_DWELLINGS = 2
BUILDING_STATIC_FIRST_ZONE_ID = 3
BUILDING_STATIC_N_ZONES = 4

BUILDING_STATIC_FLOOR_AREA_M2 = 5
BUILDING_STATIC_VOLUME_M3 = 6
BUILDING_STATIC_HEIGHT_M = 7
BUILDING_STATIC_N_FLOORS = 8

N_BUILDING_STATIC_COLS = 9


# =============================================================================
# System dynamic state columns
# Shape:
#     system_state[n_systems, N_SYSTEM_STATE_COLS]
# =============================================================================

SYSTEM_ID = 0
SYSTEM_DWELLING_ID = 1
SYSTEM_ZONE_ID = 2

SYSTEM_HVAC_MODE = 3
SYSTEM_HEATING_SETPOINT_C = 4
SYSTEM_COOLING_SETPOINT_C = 5
SYSTEM_HEATING_POWER_W = 6
SYSTEM_COOLING_POWER_W = 7

SYSTEM_WINDOW_STATE = 8
SYSTEM_WINDOW_OPEN_FRACTION = 9

SYSTEM_LIGHT_STATE = 10
SYSTEM_LIGHTING_POWER_W = 11

SYSTEM_BLIND_STATE = 12
SYSTEM_BLIND_CLOSED_FRACTION = 13

SYSTEM_VENTILATION_MODE = 14
SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S = 15

N_SYSTEM_STATE_COLS = 16


# =============================================================================
# System static columns
# Shape:
#     system_static[n_systems, N_SYSTEM_STATIC_COLS]
# =============================================================================

SYSTEM_STATIC_ID = 0
SYSTEM_STATIC_DWELLING_ID = 1
SYSTEM_STATIC_ZONE_ID = 2

SYSTEM_STATIC_HAS_HEATING = 3
SYSTEM_STATIC_HAS_COOLING = 4
SYSTEM_STATIC_HAS_WINDOW = 5
SYSTEM_STATIC_HAS_LIGHTS = 6
SYSTEM_STATIC_HAS_BLINDS = 7
SYSTEM_STATIC_HAS_MECH_VENTILATION = 8

SYSTEM_STATIC_MAX_HEATING_POWER_W = 9
SYSTEM_STATIC_MAX_COOLING_POWER_W = 10
SYSTEM_STATIC_MAX_LIGHTING_POWER_W = 11
SYSTEM_STATIC_MAX_WINDOW_FLOW_M3_S = 12
SYSTEM_STATIC_MAX_MECH_VENT_FLOW_M3_S = 13

SYSTEM_STATIC_DEFAULT_HEATING_SETPOINT_C = 14
SYSTEM_STATIC_DEFAULT_COOLING_SETPOINT_C = 15

N_SYSTEM_STATIC_COLS = 16


# =============================================================================
# Action static columns
# Shape:
#     action_static[n_actions, N_ACTION_STATIC_COLS]
# =============================================================================

ACTION_ID = 0
ACTION_TYPE = 1

ACTION_DEFAULT_TARGET_ZONE_ID = 2
ACTION_DEFAULT_TARGET_SYSTEM_ID = 3
ACTION_DEFAULT_APPLIANCE_TYPE = 4

ACTION_DURATION_MIN = 5
ACTION_CAN_RUN_WHILE_AWAY = 6
ACTION_IS_BACKGROUND = 7
ACTION_REQUIRES_HOME = 8
ACTION_REQUIRES_AWAKE = 9

ACTION_POWER_W = 10
ACTION_HEAT_GAIN_W = 11
ACTION_CO2_GAIN_KG_S = 12
ACTION_MOISTURE_GAIN_KG_S = 13

ACTION_HUNGER_EFFECT = 14
ACTION_FATIGUE_EFFECT = 15
ACTION_DIRTY_CLOTHES_EFFECT = 16
ACTION_COMFORT_EFFECT = 17

ACTION_FRICTION = 18

N_ACTION_STATIC_COLS = 19


# =============================================================================
# Action score columns
# Shape:
#     action_scores[n_persons, n_actions, N_ACTION_SCORE_COLS]
# =============================================================================

ACTION_SCORE_TOTAL = 0
ACTION_SCORE_HUNGER = 1
ACTION_SCORE_FATIGUE = 2
ACTION_SCORE_THERMAL = 3
ACTION_SCORE_AIR_QUALITY = 4
ACTION_SCORE_VISUAL = 5
ACTION_SCORE_ACOUSTIC = 6
ACTION_SCORE_LAUNDRY = 7
ACTION_SCORE_TARIFF = 8
ACTION_SCORE_FRICTION = 9
ACTION_SCORE_IMPOSSIBLE_MASK = 10

N_ACTION_SCORE_COLS = 11


# =============================================================================
# Background process state columns
# Shape:
#     process_state[n_processes, N_PROCESS_STATE_COLS]
# =============================================================================

PROCESS_ID = 0
PROCESS_TYPE = 1
PROCESS_STATE = 2

PROCESS_PERSON_ID = 3
PROCESS_DWELLING_ID = 4
PROCESS_ZONE_ID = 5
PROCESS_SYSTEM_ID = 6

PROCESS_TIME_LEFT_MIN = 7
PROCESS_TOTAL_DURATION_MIN = 8

PROCESS_POWER_W = 9
PROCESS_HEAT_GAIN_W = 10
PROCESS_CO2_GAIN_KG_S = 11
PROCESS_MOISTURE_GAIN_KG_S = 12

N_PROCESS_STATE_COLS = 13


# =============================================================================
# Weather state columns
# Shape:
#     weather_state[N_WEATHER_STATE_COLS]
# or:
#     weather_series[n_timesteps, N_WEATHER_STATE_COLS]
# =============================================================================

WEATHER_OUTDOOR_TEMPERATURE_C = 0
WEATHER_OUTDOOR_RELATIVE_HUMIDITY = 1
WEATHER_OUTDOOR_CO2_PPM = 2
WEATHER_GLOBAL_HORIZONTAL_IRRADIANCE_W_M2 = 3
WEATHER_DIRECT_NORMAL_IRRADIANCE_W_M2 = 4
WEATHER_DIFFUSE_HORIZONTAL_IRRADIANCE_W_M2 = 5
WEATHER_WIND_SPEED_M_S = 6
WEATHER_WIND_DIRECTION_DEG = 7
WEATHER_SKY_TEMPERATURE_C = 8
WEATHER_RAIN_FLAG = 9
WEATHER_ATMOSPHERIC_PRESSURE_PA = 10

N_WEATHER_STATE_COLS = 11


# =============================================================================
# Time state columns
# Shape:
#     time_state[N_TIME_STATE_COLS]
# or:
#     time_series[n_timesteps, N_TIME_STATE_COLS]
# =============================================================================

TIME_STEP_INDEX = 0
TIME_ELAPSED_MIN = 1
TIME_MINUTE_OF_DAY = 2
TIME_HOUR_OF_DAY = 3
TIME_DAY_INDEX = 4
TIME_DAY_OF_WEEK = 5
TIME_MONTH = 6
TIME_IS_WEEKEND = 7

N_TIME_STATE_COLS = 8


# =============================================================================
# Internal gains columns
# Shape:
#     internal_gains[n_zones, N_INTERNAL_GAIN_COLS]
# =============================================================================

GAIN_ZONE_ID = 0
GAIN_PEOPLE_HEAT_W = 1
GAIN_LIGHTING_HEAT_W = 2
GAIN_APPLIANCE_HEAT_W = 3
GAIN_SOLAR_HEAT_W = 4
GAIN_TOTAL_HEAT_W = 5
GAIN_CO2_KG_S = 6
GAIN_MOISTURE_KG_S = 7
GAIN_ELECTRIC_POWER_W = 8

N_INTERNAL_GAIN_COLS = 9


# =============================================================================
# Physics result columns
# Shape:
#     physics_result[n_zones, N_PHYSICS_RESULT_COLS]
# =============================================================================

PHYSICS_ZONE_ID = 0
PHYSICS_AIR_TEMPERATURE_C = 1
PHYSICS_MEAN_RADIANT_TEMPERATURE_C = 2
PHYSICS_RELATIVE_HUMIDITY = 3
PHYSICS_CO2_PPM = 4
PHYSICS_ILLUMINANCE_LUX = 5
PHYSICS_NOISE_DB = 6

PHYSICS_HEATING_DEMAND_W = 7
PHYSICS_COOLING_DEMAND_W = 8
PHYSICS_VENTILATION_FLOW_M3_S = 9
PHYSICS_THERMAL_BALANCE_RESIDUAL_W = 10
PHYSICS_MOISTURE_BALANCE_RESIDUAL_KG_S = 11
PHYSICS_CO2_BALANCE_RESIDUAL_KG_S = 12

N_PHYSICS_RESULT_COLS = 13


# =============================================================================
# Person log columns
# Shape:
#     person_log[n_timesteps, n_persons, N_PERSON_LOG_COLS]
# =============================================================================

PERSON_LOG_TIME_INDEX = 0
PERSON_LOG_PERSON_ID = 1
PERSON_LOG_DWELLING_ID = 2
PERSON_LOG_ZONE_ID = 3
PERSON_LOG_IS_HOME = 4
PERSON_LOG_OCCUPANCY_STATE = 5

PERSON_LOG_HUNGER = 6
PERSON_LOG_FATIGUE = 7
PERSON_LOG_DIRTY_CLOTHES = 8
PERSON_LOG_SICKNESS = 9

PERSON_LOG_THERMAL_STRESS = 10
PERSON_LOG_AIR_QUALITY_STRESS = 11
PERSON_LOG_VISUAL_STRESS = 12
PERSON_LOG_ACOUSTIC_STRESS = 13
PERSON_LOG_TOTAL_DISCOMFORT = 14

PERSON_LOG_ACTION_TYPE = 15
PERSON_LOG_ACTION_ID = 16
PERSON_LOG_ACTION_TIME_LEFT_MIN = 17

PERSON_LOG_POWER_W = 18
PERSON_LOG_HEAT_GAIN_W = 19
PERSON_LOG_CO2_GAIN_KG_S = 20
PERSON_LOG_MOISTURE_GAIN_KG_S = 21

N_PERSON_LOG_COLS = 22


# =============================================================================
# Zone log columns
# Shape:
#     zone_log[n_timesteps, n_zones, N_ZONE_LOG_COLS]
# =============================================================================

ZONE_LOG_TIME_INDEX = 0
ZONE_LOG_ZONE_ID = 1
ZONE_LOG_DWELLING_ID = 2
ZONE_LOG_BUILDING_ID = 3

ZONE_LOG_AIR_TEMPERATURE_C = 4
ZONE_LOG_MEAN_RADIANT_TEMPERATURE_C = 5
ZONE_LOG_RELATIVE_HUMIDITY = 6
ZONE_LOG_CO2_PPM = 7
ZONE_LOG_ILLUMINANCE_LUX = 8
ZONE_LOG_NOISE_DB = 9

ZONE_LOG_OCCUPANT_COUNT = 10
ZONE_LOG_IS_OCCUPIED = 11

ZONE_LOG_INTERNAL_HEAT_GAIN_W = 12
ZONE_LOG_SOLAR_GAIN_W = 13
ZONE_LOG_LIGHTING_GAIN_W = 14
ZONE_LOG_APPLIANCE_GAIN_W = 15
ZONE_LOG_PEOPLE_GAIN_W = 16
ZONE_LOG_CO2_GAIN_KG_S = 17
ZONE_LOG_MOISTURE_GAIN_KG_S = 18

ZONE_LOG_HEATING_DEMAND_W = 19
ZONE_LOG_COOLING_DEMAND_W = 20

N_ZONE_LOG_COLS = 21


# =============================================================================
# System log columns
# Shape:
#     system_log[n_timesteps, n_systems, N_SYSTEM_LOG_COLS]
# =============================================================================

SYSTEM_LOG_TIME_INDEX = 0
SYSTEM_LOG_SYSTEM_ID = 1
SYSTEM_LOG_DWELLING_ID = 2
SYSTEM_LOG_ZONE_ID = 3

SYSTEM_LOG_HVAC_MODE = 4
SYSTEM_LOG_HEATING_SETPOINT_C = 5
SYSTEM_LOG_COOLING_SETPOINT_C = 6
SYSTEM_LOG_HEATING_POWER_W = 7
SYSTEM_LOG_COOLING_POWER_W = 8

SYSTEM_LOG_WINDOW_STATE = 9
SYSTEM_LOG_WINDOW_OPEN_FRACTION = 10

SYSTEM_LOG_LIGHT_STATE = 11
SYSTEM_LOG_LIGHTING_POWER_W = 12

SYSTEM_LOG_BLIND_STATE = 13
SYSTEM_LOG_BLIND_CLOSED_FRACTION = 14

SYSTEM_LOG_VENTILATION_MODE = 15
SYSTEM_LOG_MECH_VENT_FLOW_M3_S = 16

N_SYSTEM_LOG_COLS = 17


# =============================================================================
# Dwelling log columns
# Shape:
#     dwelling_log[n_timesteps, n_dwellings, N_DWELLING_LOG_COLS]
# =============================================================================

DWELLING_LOG_TIME_INDEX = 0
DWELLING_LOG_DWELLING_ID = 1
DWELLING_LOG_BUILDING_ID = 2

DWELLING_LOG_OCCUPANT_COUNT = 3
DWELLING_LOG_IS_OCCUPIED = 4

DWELLING_LOG_TOTAL_POWER_W = 5
DWELLING_LOG_TOTAL_HEAT_GAIN_W = 6
DWELLING_LOG_TOTAL_CO2_GAIN_KG_S = 7
DWELLING_LOG_TOTAL_MOISTURE_GAIN_KG_S = 8

DWELLING_LOG_HEATING_DEMAND_W = 9
DWELLING_LOG_COOLING_DEMAND_W = 10
DWELLING_LOG_ELECTRICITY_DEMAND_W = 11

N_DWELLING_LOG_COLS = 12


# =============================================================================
# Building log columns
# Shape:
#     building_log[n_timesteps, n_buildings, N_BUILDING_LOG_COLS]
# =============================================================================

BUILDING_LOG_TIME_INDEX = 0
BUILDING_LOG_BUILDING_ID = 1

BUILDING_LOG_OCCUPANT_COUNT = 2
BUILDING_LOG_IS_OCCUPIED = 3

BUILDING_LOG_TOTAL_POWER_W = 4
BUILDING_LOG_HEATING_DEMAND_W = 5
BUILDING_LOG_COOLING_DEMAND_W = 6
BUILDING_LOG_ELECTRICITY_DEMAND_W = 7

N_BUILDING_LOG_COLS = 8


# =============================================================================
# Lightweight schema validation
# =============================================================================

def _assert_count(last_index, count, name):
    """
    Internal helper.

    Checks that the declared number of columns is consistent with the final
    column index.

    This is intentionally simple and does not depend on numpy.
    """
    expected = last_index + 1
    if expected != count:
        raise ValueError(
            "%s has inconsistent column count: last index %s implies %s columns, "
            "but declared count is %s"
            % (name, last_index, expected, count)
        )


def validate_schema():
    """
    Validate column counts.

    This should be called by tests, not inside the timestep loop.
    """
    _assert_count(PERSON_CURRENT_MOISTURE_GAIN_KG_S, N_PERSON_STATE_COLS, "person_state")
    _assert_count(PERSON_STATIC_WORK_END_MINUTE, N_PERSON_STATIC_COLS, "person_static")

    _assert_count(ZONE_INFILTRATION_AIRFLOW_M3_S, N_ZONE_STATE_COLS, "zone_state")
    _assert_count(ZONE_STATIC_MAX_NOISE_DB, N_ZONE_STATIC_COLS, "zone_static")

    _assert_count(DWELLING_TOTAL_ELECTRICITY_DEMAND_W, N_DWELLING_STATE_COLS, "dwelling_state")
    _assert_count(DWELLING_STATIC_VOLUME_M3, N_DWELLING_STATIC_COLS, "dwelling_static")

    _assert_count(BUILDING_TOTAL_ELECTRICITY_DEMAND_W, N_BUILDING_STATE_COLS, "building_state")
    _assert_count(BUILDING_STATIC_N_FLOORS, N_BUILDING_STATIC_COLS, "building_static")

    _assert_count(SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S, N_SYSTEM_STATE_COLS, "system_state")
    _assert_count(SYSTEM_STATIC_DEFAULT_COOLING_SETPOINT_C, N_SYSTEM_STATIC_COLS, "system_static")

    _assert_count(ACTION_FRICTION, N_ACTION_STATIC_COLS, "action_static")
    _assert_count(ACTION_SCORE_IMPOSSIBLE_MASK, N_ACTION_SCORE_COLS, "action_scores")

    _assert_count(PROCESS_MOISTURE_GAIN_KG_S, N_PROCESS_STATE_COLS, "process_state")

    _assert_count(
        WEATHER_ATMOSPHERIC_PRESSURE_PA,
        N_WEATHER_STATE_COLS,
        "weather_state",
    )
    _assert_count(TIME_IS_WEEKEND, N_TIME_STATE_COLS, "time_state")

    _assert_count(GAIN_ELECTRIC_POWER_W, N_INTERNAL_GAIN_COLS, "internal_gains")
    _assert_count(
        PHYSICS_CO2_BALANCE_RESIDUAL_KG_S,
        N_PHYSICS_RESULT_COLS,
        "physics_result",
    )

    _assert_count(PERSON_LOG_MOISTURE_GAIN_KG_S, N_PERSON_LOG_COLS, "person_log")
    _assert_count(ZONE_LOG_COOLING_DEMAND_W, N_ZONE_LOG_COLS, "zone_log")
    _assert_count(SYSTEM_LOG_MECH_VENT_FLOW_M3_S, N_SYSTEM_LOG_COLS, "system_log")
    _assert_count(DWELLING_LOG_ELECTRICITY_DEMAND_W, N_DWELLING_LOG_COLS, "dwelling_log")
    _assert_count(BUILDING_LOG_ELECTRICITY_DEMAND_W, N_BUILDING_LOG_COLS, "building_log")

    return True
