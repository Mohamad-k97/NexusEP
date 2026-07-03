"""
ABBEY array logger.

Purpose:
    Preallocate dense numeric log arrays and write timestep snapshots into them.

This replaces object-style logging like:

    records.append({"time": ..., "zone_temp": ...})

with array writes like:

    person_log[t, person_i, PERSON_LOG_HUNGER] = ...

Important:
    - This module writes numeric arrays only.
    - Decoding to readable DataFrames happens after the run.
    - No dicts are built inside the timestep loop.
    - No pandas is used inside the timestep loop.
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np

from nexusep.abbey.arrays import schema
from nexusep.abbey.arrays.decoder import decode_logs_to_dataframes, export_logs_to_csv


# =============================================================================
# Log container
# =============================================================================

@dataclass
class SimulationArrayLogs:
    """
    Preallocated numeric simulation logs.

    Shapes:
        person_log[t, person_i, variable_j]
        zone_log[t, zone_i, variable_j]
        system_log[t, system_i, variable_j]
        dwelling_log[t, dwelling_i, variable_j]
        building_log[t, building_i, variable_j]

    These are raw numeric logs. Decode after simulation.
    """

    person_log: Optional[np.ndarray] = None
    zone_log: Optional[np.ndarray] = None
    system_log: Optional[np.ndarray] = None
    dwelling_log: Optional[np.ndarray] = None
    building_log: Optional[np.ndarray] = None

    def validate(self):
        validate_simulation_array_logs(self)
        return True

    def to_dataframes(self, state):
        """
        Decode logs to readable pandas DataFrames.

        This is outside the timestep loop.
        """
        return decode_logs_to_dataframes(
            state=state,
            person_log=self.person_log,
            zone_log=self.zone_log,
            system_log=self.system_log,
            dwelling_log=self.dwelling_log,
            building_log=self.building_log,
        )

    def export_csv(self, state, output_dir):
        """
        Decode logs and export readable CSV files.

        This is outside the timestep loop.
        """
        return export_logs_to_csv(
            state=state,
            output_dir=output_dir,
            person_log=self.person_log,
            zone_log=self.zone_log,
            system_log=self.system_log,
            dwelling_log=self.dwelling_log,
            building_log=self.building_log,
        )


# =============================================================================
# Allocation
# =============================================================================

def allocate_simulation_array_logs(
    n_timesteps,
    n_persons,
    n_zones,
    n_systems,
    n_dwellings,
    n_buildings,
    log_persons=True,
    log_zones=True,
    log_systems=True,
    log_dwellings=True,
    log_buildings=True,
    dtype=np.float64,
):
    """
    Allocate all requested simulation log arrays.
    """
    person_log = None
    zone_log = None
    system_log = None
    dwelling_log = None
    building_log = None

    if log_persons:
        person_log = np.zeros(
            (n_timesteps, n_persons, schema.N_PERSON_LOG_COLS),
            dtype=dtype,
        )

    if log_zones:
        zone_log = np.zeros(
            (n_timesteps, n_zones, schema.N_ZONE_LOG_COLS),
            dtype=dtype,
        )

    if log_systems:
        system_log = np.zeros(
            (n_timesteps, n_systems, schema.N_SYSTEM_LOG_COLS),
            dtype=dtype,
        )

    if log_dwellings:
        dwelling_log = np.zeros(
            (n_timesteps, n_dwellings, schema.N_DWELLING_LOG_COLS),
            dtype=dtype,
        )

    if log_buildings:
        building_log = np.zeros(
            (n_timesteps, n_buildings, schema.N_BUILDING_LOG_COLS),
            dtype=dtype,
        )

    logs = SimulationArrayLogs(
        person_log=person_log,
        zone_log=zone_log,
        system_log=system_log,
        dwelling_log=dwelling_log,
        building_log=building_log,
    )

    logs.validate()
    return logs


def allocate_logs_for_state(
    state,
    n_timesteps=None,
    log_persons=True,
    log_zones=True,
    log_systems=True,
    log_dwellings=True,
    log_buildings=True,
    dtype=np.float64,
):
    """
    Allocate logs using the dimensions of a SimulationArrayState.
    """
    if n_timesteps is None:
        if state.series is not None and state.series.time_series is not None:
            n_timesteps = state.series.time_series.shape[0]
        elif state.series is not None and state.series.weather_series is not None:
            n_timesteps = state.series.weather_series.shape[0]
        elif state.metadata is not None and "n_timesteps" in state.metadata:
            n_timesteps = int(state.metadata["n_timesteps"])
        else:
            raise ValueError(
                "n_timesteps was not provided and could not be inferred from state."
            )

    return allocate_simulation_array_logs(
        n_timesteps=n_timesteps,
        n_persons=state.dynamic.person_state.shape[0],
        n_zones=state.dynamic.zone_state.shape[0],
        n_systems=state.dynamic.system_state.shape[0],
        n_dwellings=state.dynamic.dwelling_state.shape[0],
        n_buildings=state.dynamic.building_state.shape[0],
        log_persons=log_persons,
        log_zones=log_zones,
        log_systems=log_systems,
        log_dwellings=log_dwellings,
        log_buildings=log_buildings,
        dtype=dtype,
    )


# =============================================================================
# Validation
# =============================================================================

def _validate_optional_3d_log(log_array, expected_cols, name):
    if log_array is None:
        return True

    if not isinstance(log_array, np.ndarray):
        raise TypeError("%s must be a numpy array or None." % name)

    if log_array.ndim != 3:
        raise ValueError(
            "%s must be a 3D array. Got shape %s."
            % (name, str(log_array.shape))
        )

    if log_array.shape[2] != expected_cols:
        raise ValueError(
            "%s has wrong number of columns. Expected %s, got %s."
            % (name, expected_cols, log_array.shape[2])
        )

    return True


def validate_simulation_array_logs(logs):
    """
    Validate log array shapes.
    """
    _validate_optional_3d_log(
        logs.person_log,
        schema.N_PERSON_LOG_COLS,
        "person_log",
    )
    _validate_optional_3d_log(
        logs.zone_log,
        schema.N_ZONE_LOG_COLS,
        "zone_log",
    )
    _validate_optional_3d_log(
        logs.system_log,
        schema.N_SYSTEM_LOG_COLS,
        "system_log",
    )
    _validate_optional_3d_log(
        logs.dwelling_log,
        schema.N_DWELLING_LOG_COLS,
        "dwelling_log",
    )
    _validate_optional_3d_log(
        logs.building_log,
        schema.N_BUILDING_LOG_COLS,
        "building_log",
    )

    return True


def _validate_time_index(log_array, time_index, name):
    if log_array is None:
        return True

    if time_index < 0 or time_index >= log_array.shape[0]:
        raise IndexError(
            "%s time_index out of range. Got %s, valid range is [0, %s)."
            % (name, time_index, log_array.shape[0])
        )

    return True


# =============================================================================
# Resetting
# =============================================================================

def reset_logs(logs, value=0.0):
    """
    Reset all allocated logs to a numeric value.
    """
    if logs.person_log is not None:
        logs.person_log[:, :, :] = value

    if logs.zone_log is not None:
        logs.zone_log[:, :, :] = value

    if logs.system_log is not None:
        logs.system_log[:, :, :] = value

    if logs.dwelling_log is not None:
        logs.dwelling_log[:, :, :] = value

    if logs.building_log is not None:
        logs.building_log[:, :, :] = value

    return True


# =============================================================================
# Current-state log writers
# =============================================================================

def write_current_state_to_logs(state, logs, time_index):
    """
    Write all allocated logs for the current timestep.

    This is the function the future array runner should call once per timestep.
    """
    validate_simulation_array_logs(logs)

    if logs.person_log is not None:
        write_person_log(state, logs.person_log, time_index)

    if logs.zone_log is not None:
        write_zone_log(state, logs.zone_log, time_index)

    if logs.system_log is not None:
        write_system_log(state, logs.system_log, time_index)

    if logs.dwelling_log is not None:
        write_dwelling_log(state, logs.dwelling_log, time_index)

    if logs.building_log is not None:
        write_building_log(state, logs.building_log, time_index)

    return True


def write_person_log(state, person_log, time_index):
    """
    Write person_state snapshot into person_log[time_index, :, :].
    """
    _validate_time_index(person_log, time_index, "person_log")

    person_state = state.dynamic.person_state

    n_persons = person_state.shape[0]

    for i in range(n_persons):
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


def write_zone_log(state, zone_log, time_index):
    """
    Write zone_state snapshot into zone_log[time_index, :, :].
    """
    _validate_time_index(zone_log, time_index, "zone_log")

    zone_state = state.dynamic.zone_state
    physics_result = state.dynamic.physics_result

    n_zones = zone_state.shape[0]

    for i in range(n_zones):
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
        zone_log[
            time_index,
            i,
            schema.ZONE_LOG_MEAN_RADIANT_TEMPERATURE_C,
        ] = zone_state[i, schema.ZONE_MEAN_RADIANT_TEMPERATURE_C]
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


def write_system_log(state, system_log, time_index):
    """
    Write system_state snapshot into system_log[time_index, :, :].
    """
    _validate_time_index(system_log, time_index, "system_log")

    system_state = state.dynamic.system_state

    n_systems = system_state.shape[0]

    for i in range(n_systems):
        system_log[time_index, i, schema.SYSTEM_LOG_TIME_INDEX] = time_index
        system_log[time_index, i, schema.SYSTEM_LOG_SYSTEM_ID] = system_state[
            i,
            schema.SYSTEM_ID,
        ]
        system_log[time_index, i, schema.SYSTEM_LOG_DWELLING_ID] = system_state[
            i,
            schema.SYSTEM_DWELLING_ID,
        ]
        system_log[time_index, i, schema.SYSTEM_LOG_ZONE_ID] = system_state[
            i,
            schema.SYSTEM_ZONE_ID,
        ]

        system_log[time_index, i, schema.SYSTEM_LOG_HVAC_MODE] = system_state[
            i,
            schema.SYSTEM_HVAC_MODE,
        ]
        system_log[time_index, i, schema.SYSTEM_LOG_HEATING_SETPOINT_C] = system_state[
            i,
            schema.SYSTEM_HEATING_SETPOINT_C,
        ]
        system_log[time_index, i, schema.SYSTEM_LOG_COOLING_SETPOINT_C] = system_state[
            i,
            schema.SYSTEM_COOLING_SETPOINT_C,
        ]
        system_log[time_index, i, schema.SYSTEM_LOG_HEATING_POWER_W] = system_state[
            i,
            schema.SYSTEM_HEATING_POWER_W,
        ]
        system_log[time_index, i, schema.SYSTEM_LOG_COOLING_POWER_W] = system_state[
            i,
            schema.SYSTEM_COOLING_POWER_W,
        ]

        system_log[time_index, i, schema.SYSTEM_LOG_WINDOW_STATE] = system_state[
            i,
            schema.SYSTEM_WINDOW_STATE,
        ]
        system_log[
            time_index,
            i,
            schema.SYSTEM_LOG_WINDOW_OPEN_FRACTION,
        ] = system_state[i, schema.SYSTEM_WINDOW_OPEN_FRACTION]

        system_log[time_index, i, schema.SYSTEM_LOG_LIGHT_STATE] = system_state[
            i,
            schema.SYSTEM_LIGHT_STATE,
        ]
        system_log[time_index, i, schema.SYSTEM_LOG_LIGHTING_POWER_W] = system_state[
            i,
            schema.SYSTEM_LIGHTING_POWER_W,
        ]

        system_log[time_index, i, schema.SYSTEM_LOG_BLIND_STATE] = system_state[
            i,
            schema.SYSTEM_BLIND_STATE,
        ]
        system_log[
            time_index,
            i,
            schema.SYSTEM_LOG_BLIND_CLOSED_FRACTION,
        ] = system_state[i, schema.SYSTEM_BLIND_CLOSED_FRACTION]

        system_log[time_index, i, schema.SYSTEM_LOG_VENTILATION_MODE] = system_state[
            i,
            schema.SYSTEM_VENTILATION_MODE,
        ]
        system_log[
            time_index,
            i,
            schema.SYSTEM_LOG_MECH_VENT_FLOW_M3_S,
        ] = system_state[i, schema.SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S]

    return True


def write_dwelling_log(state, dwelling_log, time_index):
    """
    Write dwelling_state snapshot into dwelling_log[time_index, :, :].
    """
    _validate_time_index(dwelling_log, time_index, "dwelling_log")

    dwelling_state = state.dynamic.dwelling_state

    n_dwellings = dwelling_state.shape[0]

    for i in range(n_dwellings):
        dwelling_log[time_index, i, schema.DWELLING_LOG_TIME_INDEX] = time_index
        dwelling_log[time_index, i, schema.DWELLING_LOG_DWELLING_ID] = dwelling_state[
            i,
            schema.DWELLING_ID,
        ]
        dwelling_log[time_index, i, schema.DWELLING_LOG_BUILDING_ID] = dwelling_state[
            i,
            schema.DWELLING_BUILDING_ID,
        ]

        dwelling_log[time_index, i, schema.DWELLING_LOG_OCCUPANT_COUNT] = dwelling_state[
            i,
            schema.DWELLING_OCCUPANT_COUNT,
        ]
        dwelling_log[time_index, i, schema.DWELLING_LOG_IS_OCCUPIED] = dwelling_state[
            i,
            schema.DWELLING_IS_OCCUPIED,
        ]

        dwelling_log[time_index, i, schema.DWELLING_LOG_TOTAL_POWER_W] = dwelling_state[
            i,
            schema.DWELLING_TOTAL_POWER_W,
        ]
        dwelling_log[time_index, i, schema.DWELLING_LOG_TOTAL_HEAT_GAIN_W] = dwelling_state[
            i,
            schema.DWELLING_TOTAL_HEAT_GAIN_W,
        ]
        dwelling_log[
            time_index,
            i,
            schema.DWELLING_LOG_TOTAL_CO2_GAIN_KG_S,
        ] = dwelling_state[i, schema.DWELLING_TOTAL_CO2_GAIN_KG_S]
        dwelling_log[
            time_index,
            i,
            schema.DWELLING_LOG_TOTAL_MOISTURE_GAIN_KG_S,
        ] = dwelling_state[i, schema.DWELLING_TOTAL_MOISTURE_GAIN_KG_S]

        dwelling_log[time_index, i, schema.DWELLING_LOG_HEATING_DEMAND_W] = dwelling_state[
            i,
            schema.DWELLING_TOTAL_HEATING_DEMAND_W,
        ]
        dwelling_log[time_index, i, schema.DWELLING_LOG_COOLING_DEMAND_W] = dwelling_state[
            i,
            schema.DWELLING_TOTAL_COOLING_DEMAND_W,
        ]
        dwelling_log[
            time_index,
            i,
            schema.DWELLING_LOG_ELECTRICITY_DEMAND_W,
        ] = dwelling_state[i, schema.DWELLING_TOTAL_ELECTRICITY_DEMAND_W]

    return True


def write_building_log(state, building_log, time_index):
    """
    Write building_state snapshot into building_log[time_index, :, :].
    """
    _validate_time_index(building_log, time_index, "building_log")

    building_state = state.dynamic.building_state

    n_buildings = building_state.shape[0]

    for i in range(n_buildings):
        building_log[time_index, i, schema.BUILDING_LOG_TIME_INDEX] = time_index
        building_log[time_index, i, schema.BUILDING_LOG_BUILDING_ID] = building_state[
            i,
            schema.BUILDING_ID,
        ]

        building_log[time_index, i, schema.BUILDING_LOG_OCCUPANT_COUNT] = building_state[
            i,
            schema.BUILDING_OCCUPANT_COUNT,
        ]
        building_log[time_index, i, schema.BUILDING_LOG_IS_OCCUPIED] = building_state[
            i,
            schema.BUILDING_IS_OCCUPIED,
        ]

        building_log[time_index, i, schema.BUILDING_LOG_TOTAL_POWER_W] = building_state[
            i,
            schema.BUILDING_TOTAL_POWER_W,
        ]
        building_log[time_index, i, schema.BUILDING_LOG_HEATING_DEMAND_W] = building_state[
            i,
            schema.BUILDING_TOTAL_HEATING_DEMAND_W,
        ]
        building_log[time_index, i, schema.BUILDING_LOG_COOLING_DEMAND_W] = building_state[
            i,
            schema.BUILDING_TOTAL_COOLING_DEMAND_W,
        ]
        building_log[
            time_index,
            i,
            schema.BUILDING_LOG_ELECTRICITY_DEMAND_W,
        ] = building_state[i, schema.BUILDING_TOTAL_ELECTRICITY_DEMAND_W]

    return True


# =============================================================================
# Small convenience helpers
# =============================================================================

def update_state_time_from_series(state, time_index):
    """
    Copy weather/time series row into current dynamic state.

    This is useful for tests and the future array runner.
    """
    if state.series is not None:
        if state.series.time_series is not None:
            if time_index >= state.series.time_series.shape[0]:
                raise IndexError("time_index exceeds time_series length.")
            state.dynamic.time_state[:] = state.series.time_series[time_index, :]

        if state.series.weather_series is not None:
            weather_index = min(time_index, state.series.weather_series.shape[0] - 1)
            state.dynamic.weather_state[:] = state.series.weather_series[weather_index, :]

    return True