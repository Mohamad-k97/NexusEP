"""
ABBEY Phase 18.26 shoebox 8760-hour benchmark.

Single-zone shoebox dwelling benchmark.

Run:

    python -m nexusep.abbey.run_test_phase_18_26_shoebox_8760_benchmark

Purpose:
    - Fast smoke benchmark after kernel patches.
    - One building, one dwelling, one zone, one system, one person.
    - Annual hourly run.
    - Logs on/off comparison.
"""

import math
import time

from nexusep.abbey.arrays import schema
from nexusep.abbey.arrays.encoder import compile_simulation_to_arrays
from nexusep.abbey.arrays.logger import allocate_logs_for_state
from nexusep.abbey.arrays.timestep import run_array_timestep


N_TIMESTEPS = 8760
DT_MINUTES = 60
RUN_ACOUSTICS = False


def make_shoebox_weather_series(n_timesteps):
    weather = []

    for t in range(n_timesteps):
        hour_of_year = float(t)
        hour_of_day = t % 24
        day_of_year = t // 24

        annual_angle = 2.0 * math.pi * (float(day_of_year) - 15.0) / 365.0
        daily_angle = 2.0 * math.pi * (float(hour_of_day) - 15.0) / 24.0

        outdoor_temp = 12.0
        outdoor_temp += 9.0 * math.sin(annual_angle)
        outdoor_temp += 4.0 * math.sin(daily_angle)

        daylight_shape = math.sin(math.pi * max(0.0, min(1.0, (hour_of_day - 6.0) / 12.0)))

        if 6 <= hour_of_day <= 18:
            seasonal_solar = 0.65 + 0.35 * math.sin(annual_angle)
            ghi = 650.0 * daylight_shape * max(0.15, seasonal_solar)
        else:
            ghi = 0.0

        dni = 0.70 * ghi
        dhi = 0.30 * ghi

        rh = 0.65 - 0.15 * daylight_shape
        if rh < 0.35:
            rh = 0.35
        if rh > 0.90:
            rh = 0.90

        weather.append(
            {
                "outdoor_temperature_C": outdoor_temp,
                "relative_humidity": rh,
                "outdoor_co2_ppm": 420.0,
                "ghi_W_m2": ghi,
                "dni_W_m2": dni,
                "dhi_W_m2": dhi,
                "wind_speed_m_s": 2.0,
                "wind_direction_deg": 180.0,
                "sky_temperature_C": outdoor_temp - 5.0,
                "rain": False,
            }
        )

    return weather


def make_shoebox_input():
    return {
        "n_timesteps": N_TIMESTEPS,
        "dt_minutes": DT_MINUTES,
        "start_minute_of_day": 0.0,
        "start_day_of_week": 0,
        "start_month": 1,
        "n_processes": 2,

        "buildings": [
            {
                "id": "shoebox_building",
                "floor_area_m2": 40.0,
                "volume_m3": 108.0,
                "height_m": 2.7,
                "n_floors": 1,
            }
        ],

        "dwellings": [
            {
                "id": "shoebox_dwelling",
                "building_id": "shoebox_building",
                "floor_area_m2": 40.0,
                "volume_m3": 108.0,
            }
        ],

        "zones": [
            {
                "id": "shoebox_zone",
                "type": "main_room",
                "dwelling_id": "shoebox_dwelling",
                "building_id": "shoebox_building",

                "floor_area_m2": 40.0,
                "height_m": 2.7,
                "volume_m3": 108.0,

                # Shoebox thermal parameters.
                "heat_capacity_J_K": 4.0e6,
                "ua_envelope_W_K": 95.0,
                "ua_internal_W_K": 0.0,

                # Initial state.
                "air_temperature_C": 20.0,
                "mean_radiant_temperature_C": 20.0,
                "relative_humidity": 0.50,
                "co2_ppm": 600.0,
                "illuminance_lux": 150.0,
                "noise_db": 35.0,

                # Comfort/reference limits.
                "min_comfort_temp_C": 20.0,
                "max_comfort_temp_C": 26.0,
                "min_illuminance_lux": 150.0,
                "max_co2_ppm": 1200.0,
                "max_noise_db": 55.0,

                # Baseline leakage.
                "outdoor_airflow_m3_s": 0.0,
                "interzone_airflow_m3_s": 0.0,
                "infiltration_airflow_m3_s": 0.008,
            }
        ],

        "systems": [
            {
                "id": "shoebox_system",
                "dwelling_id": "shoebox_dwelling",
                "zone_id": "shoebox_zone",

                "has_heating": True,
                "has_cooling": True,
                "has_window": True,
                "has_lights": True,
                "has_blinds": True,
                "has_mech_ventilation": True,

                "hvac_mode": "auto",
                "ventilation_mode": "mechanical",

                "heating_setpoint_C": 20.0,
                "cooling_setpoint_C": 26.0,
                "default_heating_setpoint_C": 20.0,
                "default_cooling_setpoint_C": 26.0,

                "window_open_fraction": 0.0,
                "light_on": False,
                "lighting_power_W": 0.0,
                "blind_closed_fraction": 0.0,
                "mechanical_ventilation_flow_m3_s": 0.015,

                "max_heating_power_W": 2500.0,
                "max_cooling_power_W": 1800.0,
                "max_lighting_power_W": 120.0,
                "max_window_flow_m3_s": 0.12,
                "max_mech_vent_flow_m3_s": 0.025,
            }
        ],

        "persons": [
            {
                "id": "shoebox_person",
                "dwelling_id": "shoebox_dwelling",
                "home_zone_id": "shoebox_zone",
                "sleep_zone_id": "shoebox_zone",
                "current_zone_id": "shoebox_zone",
                "is_home": True,
                "occupancy_state": "home_awake",

                "hunger": 0.30,
                "fatigue": 0.25,
                "dirty_clothes": 0.10,
                "sickness": 0.0,
                "laziness": 0.20,

                "cold_sensitivity": 1.0,
                "heat_sensitivity": 1.0,
                "co2_sensitivity": 1.0,
                "light_sensitivity": 1.0,
                "noise_sensitivity": 1.0,
                "action_friction": 1.0,

                "metabolic_heat_W": 80.0,
                "co2_gain_kg_s": 0.000005,
                "moisture_gain_kg_s": 0.00003,

                "has_job": True,
                "usual_wake_minute": 7.0 * 60.0,
                "usual_sleep_minute": 23.0 * 60.0,
                "work_start_minute": 8.0 * 60.0,
                "work_end_minute": 17.0 * 60.0,
            }
        ],

        "actions": [
            {
                "id": "idle",
                "type": "idle",
                "target_zone_id": "shoebox_zone",
                "target_system_id": "shoebox_system",
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
                "target_zone_id": "shoebox_zone",
                "target_system_id": "shoebox_system",
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
                "target_zone_id": "shoebox_zone",
                "target_system_id": "shoebox_system",
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
                "target_zone_id": "shoebox_zone",
                "target_system_id": "shoebox_system",
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
                "target_zone_id": "shoebox_zone",
                "target_system_id": "shoebox_system",
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
                "target_zone_id": "shoebox_zone",
                "target_system_id": "shoebox_system",
                "duration_min": 1.0,
                "requires_home": True,
                "requires_awake": True,
                "is_background": False,
                "can_run_while_away": False,
                "appliance_type": "lights",
                "power_W": 120.0,
                "heat_gain_W": 120.0,
                "friction": 0.05,
            },
            {
                "id": "turn_light_off",
                "type": "turn_light_off",
                "target_zone_id": "shoebox_zone",
                "target_system_id": "shoebox_system",
                "duration_min": 1.0,
                "requires_home": True,
                "requires_awake": True,
                "is_background": False,
                "can_run_while_away": False,
                "appliance_type": "lights",
                "friction": 0.05,
            },
        ],

        "weather_series": make_shoebox_weather_series(N_TIMESTEPS),
    }


def allocate_logs_safe(state, n_timesteps, write_logs):
    if not write_logs:
        return None

    try:
        return allocate_logs_for_state(
            state=state,
            n_timesteps=n_timesteps,
            log_persons=True,
            log_zones=True,
            log_systems=True,
            log_dwellings=True,
            log_buildings=True,
        )
    except TypeError:
        return allocate_logs_for_state(
            state=state,
            n_timesteps=n_timesteps,
        )


def validate_shoebox_state(state):
    zone_state = state.dynamic.zone_state
    person_state = state.dynamic.person_state

    temp = zone_state[0, schema.ZONE_AIR_TEMPERATURE_C]
    co2 = zone_state[0, schema.ZONE_CO2_PPM]
    rh = zone_state[0, schema.ZONE_RELATIVE_HUMIDITY]

    hunger = person_state[0, schema.PERSON_HUNGER]
    fatigue = person_state[0, schema.PERSON_FATIGUE]

    if temp < -50.0 or temp > 80.0:
        raise AssertionError("Shoebox temperature out of diagnostic bounds.")

    if co2 <= 0.0 or co2 > 10000.0:
        raise AssertionError("Shoebox CO2 out of diagnostic bounds.")

    if rh < 0.0 or rh > 1.0:
        raise AssertionError("Shoebox RH out of bounds.")

    if hunger != hunger:
        raise AssertionError("Shoebox person hunger is NaN.")

    if fatigue != fatigue:
        raise AssertionError("Shoebox person fatigue is NaN.")


def run_case(write_logs):
    readable_input = make_shoebox_input()

    t0 = time.perf_counter()
    state = compile_simulation_to_arrays(readable_input)
    t1 = time.perf_counter()

    logs = allocate_logs_safe(
        state=state,
        n_timesteps=N_TIMESTEPS,
        write_logs=write_logs,
    )
    t2 = time.perf_counter()

    loop_t0 = time.perf_counter()

    chosen_indices = None
    chosen_ids = None
    started = None

    for time_index in range(N_TIMESTEPS):
        state, chosen_indices, chosen_ids, started = run_array_timestep(
            state=state,
            time_index=time_index,
            dt_minutes=DT_MINUTES,
            logs=logs,
            run_acoustics=RUN_ACOUSTICS,
        )

    loop_t1 = time.perf_counter()

    validate_shoebox_state(state)

    compile_s = t1 - t0
    log_alloc_s = t2 - t1
    simulation_loop_s = loop_t1 - loop_t0
    total_s = loop_t1 - t0

    simulated_hours = float(N_TIMESTEPS) * float(DT_MINUTES) / 60.0

    return {
        "state": state,
        "logs": logs,
        "write_logs": write_logs,
        "compile_s": compile_s,
        "log_alloc_s": log_alloc_s,
        "simulation_loop_s": simulation_loop_s,
        "total_s": total_s,
        "seconds_per_timestep": simulation_loop_s / float(N_TIMESTEPS),
        "simulated_hours_per_second": simulated_hours / simulation_loop_s,
        "chosen_indices": chosen_indices,
        "chosen_ids": chosen_ids,
        "started": started,
    }


def print_case_result(result):
    state = result["state"]
    logs = result["logs"]

    zone_state = state.dynamic.zone_state
    person_state = state.dynamic.person_state
    system_state = state.dynamic.system_state

    action_id = int(person_state[0, schema.PERSON_CURRENT_ACTION_ID])
    action_name = state.mappings.action_id_to_name.get(action_id, str(action_id))

    zone_id = int(person_state[0, schema.PERSON_CURRENT_ZONE_ID])
    zone_name = state.mappings.zone_id_to_name.get(zone_id, str(zone_id))

    print()
    print("Shoebox 8760-hour benchmark")
    print("---------------------------")
    print("timesteps:", N_TIMESTEPS)
    print("dt_minutes:", DT_MINUTES)
    print("simulated_hours:", float(N_TIMESTEPS) * float(DT_MINUTES) / 60.0)
    print("zones:", state.dynamic.zone_state.shape[0])
    print("people:", state.dynamic.person_state.shape[0])
    print("systems:", state.dynamic.system_state.shape[0])
    print("actions:", state.static.action_static.shape[0])
    print("write_logs:", result["write_logs"])
    print("run_acoustics:", RUN_ACOUSTICS)
    print()
    print("compile_s:", result["compile_s"])
    print("log_alloc_s:", result["log_alloc_s"])
    print("simulation_loop_s:", result["simulation_loop_s"])
    print("total_s:", result["total_s"])
    print("seconds_per_timestep:", result["seconds_per_timestep"])
    print("simulated_hours_per_second:", result["simulated_hours_per_second"])

    print()
    print("Final zone state:")
    print(
        "shoebox_zone",
        "T=", zone_state[0, schema.ZONE_AIR_TEMPERATURE_C],
        "CO2=", zone_state[0, schema.ZONE_CO2_PPM],
        "RH=", zone_state[0, schema.ZONE_RELATIVE_HUMIDITY],
        "lux=", zone_state[0, schema.ZONE_ILLUMINANCE_LUX],
    )

    print()
    print("Final system state:")
    print(
        "shoebox_system",
        "hvac_mode=", system_state[0, schema.SYSTEM_HVAC_MODE],
        "heating_W=", system_state[0, schema.SYSTEM_HEATING_POWER_W],
        "cooling_W=", system_state[0, schema.SYSTEM_COOLING_POWER_W],
        "window_frac=", system_state[0, schema.SYSTEM_WINDOW_OPEN_FRACTION],
        "light_state=", system_state[0, schema.SYSTEM_LIGHT_STATE],
        "vent_mode=", system_state[0, schema.SYSTEM_VENTILATION_MODE],
        "mech_flow=", system_state[0, schema.SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S],
    )

    print()
    print("Final person state:")
    print(
        "shoebox_person",
        "zone=", zone_name,
        "hunger=", person_state[0, schema.PERSON_HUNGER],
        "fatigue=", person_state[0, schema.PERSON_FATIGUE],
        "thermal=", person_state[0, schema.PERSON_THERMAL_STRESS],
        "air=", person_state[0, schema.PERSON_AIR_QUALITY_STRESS],
        "visual=", person_state[0, schema.PERSON_VISUAL_STRESS],
        "action=", action_name,
    )

    if logs is not None:
        print()
        print("Log shapes:")
        if getattr(logs, "person_log", None) is not None:
            print("person_log:", logs.person_log.shape)
        if getattr(logs, "zone_log", None) is not None:
            print("zone_log:", logs.zone_log.shape)
        if getattr(logs, "system_log", None) is not None:
            print("system_log:", logs.system_log.shape)
        if getattr(logs, "dwelling_log", None) is not None:
            print("dwelling_log:", logs.dwelling_log.shape)
        if getattr(logs, "building_log", None) is not None:
            print("building_log:", logs.building_log.shape)


def main():
    result_logs_on = run_case(write_logs=True)
    print_case_result(result_logs_on)

    result_logs_off = run_case(write_logs=False)
    print_case_result(result_logs_off)

    print()
    print("Logs overhead")
    print("-------------")
    print("logs_on_loop_s:", result_logs_on["simulation_loop_s"])
    print("logs_off_loop_s:", result_logs_off["simulation_loop_s"])
    print(
        "difference_s:",
        result_logs_on["simulation_loop_s"] - result_logs_off["simulation_loop_s"],
    )

    if result_logs_on["simulation_loop_s"] > 0.0:
        print(
            "logging_share_of_logs_on:",
            (
                result_logs_on["simulation_loop_s"]
                - result_logs_off["simulation_loop_s"]
            )
            / result_logs_on["simulation_loop_s"],
        )


if __name__ == "__main__":
    main()