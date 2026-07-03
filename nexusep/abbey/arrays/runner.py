"""
ABBEY array simulation runner.

Phase 13:
    Friendly simulation runner around the array timestep core.

This file is allowed to use:
    - readable input dictionaries/objects
    - dataclasses
    - decoded records
    - DataFrames outside the timestep loop

This file must not put those things inside the numeric timestep kernels.

Public functions:
    run_simulation_array_core(...)
    run_simulation(...)
    compare_array_runner_outputs(...)
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import numpy as np

from nexusep.abbey.arrays.encoder import compile_simulation_to_arrays
from nexusep.abbey.arrays.decoder import (
    decode_simulation_state,
    decoded_state_to_dataframes,
)
from nexusep.abbey.arrays.logger import allocate_logs_for_state
from nexusep.abbey.arrays.timestep import run_array_timestep


# =============================================================================
# Result containers
# =============================================================================

@dataclass
class ArraySimulationRunResult:
    """
    Result returned by run_simulation_array_core.

    This object is outside the numeric core. It is allowed to contain readable
    records, DataFrames, metadata, and raw arrays for debugging.
    """

    state: Any
    logs: Any
    decoded_state: Any
    dataframes: Optional[Dict[str, Any]]
    log_dataframes: Optional[Dict[str, Any]]
    metadata: Dict[str, Any]

    def export_logs_csv(self, output_dir):
        """
        Export decoded logs to CSV files.
        """
        return self.logs.export_csv(
            state=self.state,
            output_dir=output_dir,
        )

    def export_final_state_csv(self, output_dir):
        """
        Export decoded final state to CSV files.
        """
        from nexusep.abbey.arrays.decoder import export_decoded_state_to_csv

        return export_decoded_state_to_csv(
            decoded_state=self.decoded_state,
            output_dir=output_dir,
        )


@dataclass
class RunnerComparisonResult:
    """
    Result returned by compare_array_runner_outputs.
    """

    array_result: Any
    old_result: Any
    comparison: Dict[str, Any]


# =============================================================================
# Small helpers
# =============================================================================

def _read(obj, key, default=None):
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(key, default)

    return getattr(obj, key, default)


def infer_n_timesteps_from_state(state):
    """
    Infer number of timesteps from array state.
    """
    if state.series is not None:
        if state.series.time_series is not None:
            return int(state.series.time_series.shape[0])
        if state.series.weather_series is not None:
            return int(state.series.weather_series.shape[0])

    if state.metadata is not None:
        if "n_timesteps" in state.metadata:
            return int(state.metadata["n_timesteps"])

    return 1


def infer_dt_minutes_from_state(state, fallback=15.0):
    """
    Infer dt_minutes from array state.
    """
    if state.metadata is not None:
        if "dt_minutes" in state.metadata:
            return float(state.metadata["dt_minutes"])

    return float(fallback)


def make_runner_metadata(
    state,
    n_timesteps,
    dt_minutes,
    chosen_action_history,
    started_action_history,
):
    """
    Build readable run metadata outside the timestep loop.
    """
    return {
        "runner": "array",
        "n_timesteps": int(n_timesteps),
        "dt_minutes": float(dt_minutes),
        "n_persons": int(state.dynamic.person_state.shape[0]),
        "n_zones": int(state.dynamic.zone_state.shape[0]),
        "n_systems": int(state.dynamic.system_state.shape[0]),
        "n_dwellings": int(state.dynamic.dwelling_state.shape[0]),
        "n_buildings": int(state.dynamic.building_state.shape[0]),
        "n_actions": int(state.static.action_static.shape[0]),
        "chosen_action_history": chosen_action_history,
        "started_action_history": started_action_history,
    }


def maybe_decode_dataframes(decoded_state, decode_to_dataframes):
    if not decode_to_dataframes:
        return None

    return decoded_state_to_dataframes(decoded_state)


def maybe_decode_log_dataframes(logs, state, decode_logs_to_dataframes):
    if not decode_logs_to_dataframes:
        return None

    return logs.to_dataframes(state)


# =============================================================================
# Main array runner
# =============================================================================

def run_simulation_array_core(
    readable_input,
    n_timesteps=None,
    dt_minutes=None,
    registry=None,
    dtype=np.float64,
    logs=None,
    decode_final_state=True,
    decode_to_dataframes=True,
    decode_logs_to_dataframes=True,
    log_persons=True,
    log_zones=True,
    log_systems=True,
    log_dwellings=True,
    log_buildings=True,
    airflow_link_array=None,
    acoustic_link_array=None,
    zone_noise_source_array=None,
    outdoor_noise_db=None,
    electricity_tariff=0.25,
    enforce_work_schedule=True,
    run_acoustics=True,
):
    """
    Run ABBEY using the array core.

    Steps:
        1. compile readable input to arrays
        2. preallocate logs
        3. loop over timesteps
        4. call run_array_timestep
        5. decode final state and logs after the loop

    Parameters
    ----------
    readable_input:
        Dict-like or object-like simulation input.

    n_timesteps:
        Optional override. If None, inferred from state series/metadata.

    dt_minutes:
        Optional override. If None, inferred from state metadata.

    registry:
        Optional SimulationIDRegistry. Useful when comparing runs with fixed IDs.

    Returns
    -------
    ArraySimulationRunResult
    """
    state = compile_simulation_to_arrays(
        readable_input=readable_input,
        registry=registry,
        dtype=dtype,
        include_metadata=True,
    )

    if n_timesteps is None:
        n_timesteps = infer_n_timesteps_from_state(state)

    n_timesteps = int(n_timesteps)

    if dt_minutes is None:
        dt_minutes = infer_dt_minutes_from_state(state)

    dt_minutes = float(dt_minutes)

    if logs is None:
        logs = allocate_logs_for_state(
            state=state,
            n_timesteps=n_timesteps,
            log_persons=log_persons,
            log_zones=log_zones,
            log_systems=log_systems,
            log_dwellings=log_dwellings,
            log_buildings=log_buildings,
            dtype=dtype,
        )

    chosen_action_history = np.zeros(
        (n_timesteps, state.dynamic.person_state.shape[0]),
        dtype=np.int64,
    )
    started_action_history = np.zeros(
        (n_timesteps, state.dynamic.person_state.shape[0]),
        dtype=np.float64,
    )

    for time_index in range(n_timesteps):
        (
            state,
            chosen_action_indices,
            chosen_action_ids,
            started_actions,
        ) = run_array_timestep(
            state=state,
            time_index=time_index,
            dt_minutes=dt_minutes,
            logs=logs,
            airflow_link_array=airflow_link_array,
            acoustic_link_array=acoustic_link_array,
            zone_noise_source_array=zone_noise_source_array,
            outdoor_noise_db=outdoor_noise_db,
            electricity_tariff=electricity_tariff,
            enforce_work_schedule=enforce_work_schedule,
            run_acoustics=run_acoustics,
        )

        chosen_action_history[time_index, :] = chosen_action_ids[:]
        started_action_history[time_index, :] = started_actions[:]

    decoded_state = None
    dataframes = None
    log_dataframes = None

    if decode_final_state:
        decoded_state = decode_simulation_state(state)
        dataframes = maybe_decode_dataframes(
            decoded_state=decoded_state,
            decode_to_dataframes=decode_to_dataframes,
        )

    log_dataframes = maybe_decode_log_dataframes(
        logs=logs,
        state=state,
        decode_logs_to_dataframes=decode_logs_to_dataframes,
    )

    metadata = make_runner_metadata(
        state=state,
        n_timesteps=n_timesteps,
        dt_minutes=dt_minutes,
        chosen_action_history=chosen_action_history,
        started_action_history=started_action_history,
    )

    return ArraySimulationRunResult(
        state=state,
        logs=logs,
        decoded_state=decoded_state,
        dataframes=dataframes,
        log_dataframes=log_dataframes,
        metadata=metadata,
    )


# =============================================================================
# Public runner switch
# =============================================================================

def run_simulation(
    config,
    runner="array",
    old_runner=None,
    **kwargs
):
    """
    Public simulation switch.

    runner:
        "array"
            use new array core

        "old", "object", "legacy"
            use old object runner

    old_runner:
        callable for the legacy/object runner.

    This avoids guessing your old import path. In the compatibility phase you
    can wire the old runner here permanently.
    """
    runner_name = str(runner).lower().strip()

    if runner_name in ("array", "arrays", "new", "array_core"):
        return run_simulation_array_core(
            readable_input=config,
            **kwargs
        )

    if runner_name in ("old", "object", "legacy"):
        if old_runner is None:
            raise ValueError(
                "runner='%s' requested, but old_runner was not provided."
                % runner
            )

        return old_runner(config)

    raise ValueError(
        "Unknown runner '%s'. Use 'array' or 'old'." % runner
    )


# =============================================================================
# Comparison helpers
# =============================================================================

def extract_array_key_outputs(result):
    """
    Extract a small set of comparable outputs from an array run.

    This is intentionally conservative. It avoids assuming the old runner has
    the same rich object structure.
    """
    state = result.state
    logs = result.logs

    output = {
        "final_zone_air_temperature_C": None,
        "final_zone_co2_ppm": None,
        "final_zone_relative_humidity": None,
        "final_zone_illuminance_lux": None,
        "final_zone_noise_db": None,
        "final_person_hunger": None,
        "final_person_fatigue": None,
        "final_person_is_home": None,
        "zone_log": None,
        "person_log": None,
    }

    if state.dynamic.zone_state.shape[0] > 0:
        from nexusep.abbey.arrays import schema

        output["final_zone_air_temperature_C"] = float(
            state.dynamic.zone_state[0, schema.ZONE_AIR_TEMPERATURE_C]
        )
        output["final_zone_co2_ppm"] = float(
            state.dynamic.zone_state[0, schema.ZONE_CO2_PPM]
        )
        output["final_zone_relative_humidity"] = float(
            state.dynamic.zone_state[0, schema.ZONE_RELATIVE_HUMIDITY]
        )
        output["final_zone_illuminance_lux"] = float(
            state.dynamic.zone_state[0, schema.ZONE_ILLUMINANCE_LUX]
        )
        output["final_zone_noise_db"] = float(
            state.dynamic.zone_state[0, schema.ZONE_NOISE_DB]
        )

    if state.dynamic.person_state.shape[0] > 0:
        from nexusep.abbey.arrays import schema

        output["final_person_hunger"] = float(
            state.dynamic.person_state[0, schema.PERSON_HUNGER]
        )
        output["final_person_fatigue"] = float(
            state.dynamic.person_state[0, schema.PERSON_FATIGUE]
        )
        output["final_person_is_home"] = float(
            state.dynamic.person_state[0, schema.PERSON_IS_HOME]
        )

    if logs is not None:
        output["zone_log"] = logs.zone_log
        output["person_log"] = logs.person_log

    return output


def default_old_output_extractor(old_result):
    """
    Best-effort old-runner extractor.

    You can replace this with a project-specific extractor once you wire the
    legacy runner.
    """
    return old_result


def compare_numeric_values(a, b, tolerance=1.0e-6):
    """
    Compare two scalar numeric values.
    """
    if a is None or b is None:
        return {
            "comparable": False,
            "match": False,
            "difference": None,
        }

    try:
        af = float(a)
        bf = float(b)
    except Exception:
        return {
            "comparable": False,
            "match": False,
            "difference": None,
        }

    difference = abs(af - bf)

    return {
        "comparable": True,
        "match": difference <= tolerance,
        "difference": difference,
    }


def compare_array_runner_outputs(
    readable_input,
    old_runner,
    old_output_extractor=None,
    tolerance=1.0e-6,
    **array_runner_kwargs
):
    """
    Run array runner and old runner on the same readable input.

    This does not force old-runner structure. Instead, old_output_extractor
    should return a dict with keys comparable to extract_array_key_outputs.

    Example old_output_extractor result:
        {
            "final_zone_air_temperature_C": 20.5,
            "final_zone_co2_ppm": 800.0,
        }
    """
    if old_output_extractor is None:
        old_output_extractor = default_old_output_extractor

    array_result = run_simulation_array_core(
        readable_input=readable_input,
        **array_runner_kwargs
    )

    old_result = old_runner(readable_input)

    array_outputs = extract_array_key_outputs(array_result)
    old_outputs = old_output_extractor(old_result)

    comparison = {}

    for key, array_value in array_outputs.items():
        if key in ("zone_log", "person_log"):
            continue

        old_value = None

        if isinstance(old_outputs, dict) and key in old_outputs:
            old_value = old_outputs[key]

        comparison[key] = compare_numeric_values(
            a=array_value,
            b=old_value,
            tolerance=tolerance,
        )

    return RunnerComparisonResult(
        array_result=array_result,
        old_result=old_result,
        comparison=comparison,
    )


# =============================================================================
# Minimal example input
# =============================================================================

def make_minimal_array_runner_input():
    """
    Minimal readable input for runner tests and scratch runs.
    """
    return {
        "dt_minutes": 15,
        "n_timesteps": 4,
        "start_minute_of_day": 8 * 60,

        "weather_series": [
            {
                "outdoor_temperature_C": 5.0,
                "relative_humidity": 0.60,
                "outdoor_co2_ppm": 420.0,
                "wind_speed_m_s": 2.0,
                "ghi_W_m2": 100.0,
            },
            {
                "outdoor_temperature_C": 6.0,
                "relative_humidity": 0.58,
                "outdoor_co2_ppm": 420.0,
                "wind_speed_m_s": 3.0,
                "ghi_W_m2": 300.0,
            },
            {
                "outdoor_temperature_C": 7.0,
                "relative_humidity": 0.55,
                "outdoor_co2_ppm": 420.0,
                "wind_speed_m_s": 4.0,
                "ghi_W_m2": 500.0,
            },
            {
                "outdoor_temperature_C": 8.0,
                "relative_humidity": 0.50,
                "outdoor_co2_ppm": 420.0,
                "wind_speed_m_s": 4.0,
                "ghi_W_m2": 600.0,
            },
        ],

        "buildings": [
            {
                "id": "building_001",
                "floor_area_m2": 50.0,
                "volume_m3": 125.0,
                "height_m": 3.0,
                "n_floors": 1,
            }
        ],

        "dwellings": [
            {
                "id": "dwelling_001",
                "building_id": "building_001",
                "floor_area_m2": 50.0,
                "volume_m3": 125.0,
            }
        ],

        "zones": [
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
                "co2_ppm": 900.0,
                "illuminance_lux": 50.0,
                "noise_db": 35.0,

                "heat_capacity_J_K": 3000000.0,
                "ua_envelope_W_K": 120.0,
                "ua_internal_W_K": 20.0,

                "min_comfort_temp_C": 20.0,
                "max_comfort_temp_C": 26.0,
                "min_illuminance_lux": 150.0,
                "max_co2_ppm": 1000.0,
                "max_noise_db": 45.0,
            }
        ],

        "persons": [
            {
                "id": "person_001",
                "dwelling_id": "dwelling_001",
                "home_zone_id": "main_room",
                "sleep_zone_id": "main_room",
                "current_zone_id": "main_room",
                "is_home": True,

                "hunger": 0.90,
                "fatigue": 0.20,
                "dirty_clothes": 0.30,
                "sickness": 0.00,
                "laziness": 0.10,

                "metabolic_heat_W": 80.0,
                "co2_gain_kg_s": 0.000005,
                "moisture_gain_kg_s": 0.00001,

                "has_job": False,
            }
        ],

        "systems": [
            {
                "id": "system_main_room",
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

                "heating_setpoint_C": 20.0,
                "cooling_setpoint_C": 26.0,

                "window_open_fraction": 0.0,
                "light_on": False,
                "blind_closed_fraction": 0.0,

                "max_heating_power_W": 3000.0,
                "max_cooling_power_W": 2500.0,
                "max_lighting_power_W": 150.0,
                "max_window_flow_m3_s": 0.20,
                "max_mech_vent_flow_m3_s": 0.05,
            }
        ],

        "actions": [
            {
                "id": "idle",
                "type": "idle",
                "target_zone_id": "main_room",
                "duration_min": 15.0,
                "requires_home": False,
                "requires_awake": False,
                "can_run_while_away": True,
                "friction": 0.0,
            },
            {
                "id": "eat",
                "type": "eat",
                "target_zone_id": "main_room",
                "duration_min": 30.0,
                "requires_home": True,
                "requires_awake": True,
                "hunger_effect": -0.7,
                "power_W": 50.0,
                "heat_gain_W": 50.0,
                "friction": 0.2,
            },
            {
                "id": "open_window",
                "type": "open_window",
                "target_zone_id": "main_room",
                "target_system_id": "system_main_room",
                "duration_min": 1.0,
                "requires_home": True,
                "requires_awake": True,
                "friction": 0.1,
            },
            {
                "id": "turn_light_on",
                "type": "turn_light_on",
                "target_zone_id": "main_room",
                "target_system_id": "system_main_room",
                "appliance_type": "lights",
                "duration_min": 1.0,
                "requires_home": True,
                "requires_awake": True,
                "power_W": 80.0,
                "heat_gain_W": 80.0,
                "friction": 0.05,
            },
            {
                "id": "turn_heating_on",
                "type": "turn_heating_on",
                "target_zone_id": "main_room",
                "target_system_id": "system_main_room",
                "duration_min": 1.0,
                "requires_home": True,
                "requires_awake": True,
                "friction": 0.1,
            },
        ],
    }