"""
ABBEY Phase 18.20 benchmark.

8760-hour simulation:
    - one dwelling
    - 5 zones
    - 4 people
    - hourly timestep
    - array runner/timestep path
    - optional logs
    - no DataFrame decoding during benchmark

Run:
    python -m benchmarks.arrays.phase_18_20_8760
"""

import math
import time

from nexusep.abbey.arrays import schema
from nexusep.abbey.arrays.encoder import compile_simulation_to_arrays
from nexusep.abbey.arrays.logger import allocate_logs_for_state
from nexusep.abbey.arrays.timestep import run_array_timestep


N_TIMESTEPS = 8760
DT_MINUTES = 60
WRITE_LOGS = True
RUN_ACOUSTICS = False


def make_hourly_weather_series(n_timesteps):
    weather = []

    for t in range(n_timesteps):
        hour = t % 24
        day = t // 24

        annual = math.sin(2.0 * math.pi * day / 365.0)
        daily = math.sin(2.0 * math.pi * (hour - 8.0) / 24.0)

        outdoor_temp = 12.0 + 10.0 * annual + 4.0 * daily

        if 7 <= hour <= 18:
            solar_shape = math.sin(math.pi * (hour - 7.0) / 11.0)
            ghi = max(0.0, 650.0 * solar_shape * (0.65 + 0.35 * annual))
        else:
            ghi = 0.0

        rh = 0.60 - 0.10 * daily
        rh = max(0.30, min(0.90, rh))

        weather.append(
            {
                "outdoor_temperature_C": outdoor_temp,
                "relative_humidity": rh,
                "outdoor_co2_ppm": 420.0,
                "wind_speed_m_s": 2.0 + 1.0 * abs(daily),
                "wind_direction_deg": 0.0,
                "ghi_W_m2": ghi,
                "dni_W_m2": 0.7 * ghi,
                "dhi_W_m2": 0.3 * ghi,
                "sky_temperature_C": outdoor_temp - 5.0,
                "rain": False,
            }
        )

    return weather


def zone(
    zone_id,
    zone_type,
    floor_area_m2,
    volume_m3,
    air_temperature_C,
    relative_humidity,
    co2_ppm,
    illuminance_lux,
    ua_envelope_W_K,
    heat_capacity_J_K,
):
    return {
        "id": zone_id,
        "type": zone_type,
        "dwelling_id": "dwelling_001",
        "building_id": "building_001",

        "floor_area_m2": floor_area_m2,
        "volume_m3": volume_m3,
        "height_m": 2.6,

        "air_temperature_C": air_temperature_C,
        "mean_radiant_temperature_C": air_temperature_C,
        "relative_humidity": relative_humidity,
        "co2_ppm": co2_ppm,
        "illuminance_lux": illuminance_lux,
        "noise_db": 35.0,

        "heat_capacity_J_K": heat_capacity_J_K,
        "ua_envelope_W_K": ua_envelope_W_K,
        "ua_internal_W_K": 25.0,

        "min_comfort_temp_C": 20.0,
        "max_comfort_temp_C": 26.0,
        "min_illuminance_lux": 150.0,
        "max_co2_ppm": 1000.0,
        "max_noise_db": 45.0,
    }


def person(
    person_id,
    current_zone_id,
    sleep_zone_id,
    hunger,
    fatigue,
    dirty_clothes,
    has_job,
    work_start_minute,
    work_end_minute,
):
    return {
        "id": person_id,
        "dwelling_id": "dwelling_001",

        "home_zone_id": "living_room",
        "sleep_zone_id": sleep_zone_id,
        "current_zone_id": current_zone_id,
        "is_home": True,

        "hunger": hunger,
        "fatigue": fatigue,
        "dirty_clothes": dirty_clothes,
        "sickness": 0.0,
        "laziness": 0.20,

        "cold_sensitivity": 1.0,
        "heat_sensitivity": 1.0,
        "co2_sensitivity": 1.0,
        "light_sensitivity": 1.0,
        "noise_sensitivity": 1.0,
        "action_friction": 0.30,

        "metabolic_heat_W": 80.0,
        "co2_gain_kg_s": 0.000005,
        "moisture_gain_kg_s": 0.000012,

        "has_job": has_job,
        "usual_wake_minute": 7 * 60,
        "usual_sleep_minute": 23 * 60,
        "work_start_minute": work_start_minute,
        "work_end_minute": work_end_minute,
    }


def system(
    system_id,
    zone_id,
    has_cooling,
    has_window,
    has_mech_ventilation,
    max_heating_power_W,
    max_cooling_power_W,
    max_lighting_power_W,
    max_window_flow_m3_s,
    max_mech_vent_flow_m3_s,
):
    return {
        "id": system_id,
        "dwelling_id": "dwelling_001",
        "zone_id": zone_id,

        "has_heating": True,
        "has_cooling": has_cooling,
        "has_window": has_window,
        "has_lights": True,
        "has_blinds": has_window,
        "has_mech_ventilation": has_mech_ventilation,

        "hvac_mode": "auto",
        "ventilation_mode": "off",

        "heating_setpoint_C": 20.0,
        "cooling_setpoint_C": 26.0,

        "window_open_fraction": 0.0,
        "light_on": False,
        "blind_closed_fraction": 0.0,

        "max_heating_power_W": max_heating_power_W,
        "max_cooling_power_W": max_cooling_power_W,
        "max_lighting_power_W": max_lighting_power_W,
        "max_window_flow_m3_s": max_window_flow_m3_s,
        "max_mech_vent_flow_m3_s": max_mech_vent_flow_m3_s,
    }


def make_8760_multizone_dwelling_input():
    return {
        "dt_minutes": DT_MINUTES,
        "n_timesteps": N_TIMESTEPS,
        "start_minute_of_day": 0,
        "start_day_of_week": 0,
        "start_month": 1,

        "weather_series": make_hourly_weather_series(N_TIMESTEPS),

        "buildings": [
            {
                "id": "building_001",
                "floor_area_m2": 105.0,
                "volume_m3": 265.0,
                "height_m": 3.0,
                "n_floors": 1,
            }
        ],

        "dwellings": [
            {
                "id": "dwelling_001",
                "building_id": "building_001",
                "floor_area_m2": 105.0,
                "volume_m3": 265.0,
            }
        ],

        "zones": [
            zone("living_room", "living_room", 35.0, 90.0, 21.0, 0.50, 850.0, 100.0, 120.0, 3200000.0),
            zone("kitchen", "kitchen", 18.0, 45.0, 21.0, 0.52, 850.0, 120.0, 80.0, 1600000.0),
            zone("bedroom_1", "bedroom", 20.0, 50.0, 20.0, 0.48, 750.0, 50.0, 90.0, 1800000.0),
            zone("bedroom_2", "bedroom", 18.0, 45.0, 20.0, 0.48, 750.0, 50.0, 85.0, 1600000.0),
            zone("bathroom", "bathroom", 8.0, 20.0, 21.0, 0.55, 700.0, 80.0, 55.0, 700000.0),
        ],

        "persons": [
            person("person_1", "living_room", "bedroom_1", 0.70, 0.20, 0.20, True, 8 * 60, 17 * 60),
            person("person_2", "kitchen", "bedroom_1", 0.45, 0.30, 0.30, True, 9 * 60, 18 * 60),
            person("person_3", "bedroom_2", "bedroom_2", 0.35, 0.55, 0.10, False, 9 * 60, 17 * 60),
            person("person_4", "living_room", "bedroom_2", 0.80, 0.25, 0.45, False, 9 * 60, 17 * 60),
        ],

        "systems": [
            system("system_living", "living_room", True, True, True, 3500.0, 2500.0, 180.0, 0.20, 0.05),
            system("system_kitchen", "kitchen", False, True, True, 1800.0, 0.0, 120.0, 0.15, 0.05),
            system("system_bedroom_1", "bedroom_1", False, True, False, 1800.0, 0.0, 90.0, 0.12, 0.0),
            system("system_bedroom_2", "bedroom_2", False, True, False, 1800.0, 0.0, 90.0, 0.12, 0.0),
            system("system_bathroom", "bathroom", False, False, True, 1200.0, 0.0, 80.0, 0.0, 0.04),
        ],

        "actions": [
            {
                "id": "idle",
                "type": "idle",
                "target_zone_id": "living_room",
                "duration_min": 60.0,
                "requires_home": False,
                "requires_awake": False,
                "can_run_while_away": True,
                "friction": 0.0,
            },
            {
                "id": "sleep",
                "type": "sleep",
                "target_zone_id": "bedroom_1",
                "duration_min": 480.0,
                "requires_home": True,
                "requires_awake": False,
                "can_run_while_away": False,
                "fatigue_effect": -1.0,
                "friction": 0.1,
            },
            {
                "id": "eat",
                "type": "eat",
                "target_zone_id": "kitchen",
                "duration_min": 30.0,
                "requires_home": True,
                "requires_awake": True,
                "hunger_effect": -0.7,
                "power_W": 80.0,
                "heat_gain_W": 80.0,
                "friction": 0.2,
            },
            {
                "id": "cook",
                "type": "cook",
                "target_zone_id": "kitchen",
                "target_system_id": "system_kitchen",
                "appliance_type": "stove",
                "duration_min": 45.0,
                "requires_home": True,
                "requires_awake": True,
                "hunger_effect": -0.3,
                "power_W": 1200.0,
                "heat_gain_W": 900.0,
                "moisture_gain_kg_s": 0.00004,
                "friction": 0.4,
            },
            {
                "id": "open_living_window",
                "type": "open_window",
                "target_zone_id": "living_room",
                "target_system_id": "system_living",
                "duration_min": 1.0,
                "requires_home": True,
                "requires_awake": True,
                "friction": 0.1,
            },
            {
                "id": "turn_living_light_on",
                "type": "turn_light_on",
                "target_zone_id": "living_room",
                "target_system_id": "system_living",
                "appliance_type": "lights",
                "duration_min": 1.0,
                "requires_home": True,
                "requires_awake": True,
                "power_W": 100.0,
                "heat_gain_W": 100.0,
                "friction": 0.05,
            },
            {
                "id": "do_laundry",
                "type": "do_laundry",
                "target_zone_id": "bathroom",
                "target_system_id": "system_bathroom",
                "appliance_type": "washing_machine",
                "duration_min": 90.0,
                "requires_home": True,
                "requires_awake": True,
                "is_background": True,
                "can_run_while_away": True,
                "power_W": 500.0,
                "heat_gain_W": 120.0,
                "moisture_gain_kg_s": 0.00002,
                "dirty_clothes_effect": -0.8,
                "friction": 0.3,
            },
        ],
    }


def run_benchmark():
    readable_input = make_8760_multizone_dwelling_input()

    t0 = time.perf_counter()
    state = compile_simulation_to_arrays(readable_input)
    t1 = time.perf_counter()

    logs = None
    if WRITE_LOGS:
        logs = allocate_logs_for_state(
            state=state,
            n_timesteps=N_TIMESTEPS,
            log_persons=True,
            log_zones=True,
            log_systems=True,
            log_dwellings=True,
            log_buildings=True,
        )
    t2 = time.perf_counter()

    for time_index in range(N_TIMESTEPS):
        state, chosen_indices, chosen_ids, started = run_array_timestep(
            state=state,
            time_index=time_index,
            dt_minutes=DT_MINUTES,
            logs=logs,
            run_acoustics=RUN_ACOUSTICS,
        )
    
        zone_temp = state.dynamic.zone_state[:, schema.ZONE_AIR_TEMPERATURE_C]
        zone_co2 = state.dynamic.zone_state[:, schema.ZONE_CO2_PPM]
        zone_rh = state.dynamic.zone_state[:, schema.ZONE_RELATIVE_HUMIDITY]
    
        person_hunger = state.dynamic.person_state[:, schema.PERSON_HUNGER]
        person_fatigue = state.dynamic.person_state[:, schema.PERSON_FATIGUE]
    
        if zone_temp.min() < -50.0 or zone_temp.max() > 80.0:
            print("Temperature instability at timestep:", time_index)
            print("zone_temp:", zone_temp)
            print("zone internal heat:", state.dynamic.zone_state[:, schema.ZONE_INTERNAL_HEAT_GAIN_W])
            print("zone people gain:", state.dynamic.zone_state[:, schema.ZONE_PEOPLE_GAIN_W])
            print("zone appliance gain:", state.dynamic.zone_state[:, schema.ZONE_APPLIANCE_GAIN_W])
            print("zone lighting gain:", state.dynamic.zone_state[:, schema.ZONE_LIGHTING_GAIN_W])
            raise AssertionError("Zone temperature out of realistic diagnostic bounds.")
    
        if zone_co2.min() <= 0.0 or zone_co2.max() > 10000.0:
            print("CO2 instability at timestep:", time_index)
            print("zone_co2:", zone_co2)
            raise AssertionError("Zone CO2 out of diagnostic bounds.")
    
        if zone_rh.min() < 0.0 or zone_rh.max() > 1.0:
            print("RH instability at timestep:", time_index)
            print("zone_rh:", zone_rh)
            raise AssertionError("Zone relative humidity out of bounds.")
    
        if person_hunger.min() != person_hunger.min() or person_fatigue.min() != person_fatigue.min():
            print("Person NaN at timestep:", time_index)
            print("hunger:", person_hunger)
            print("fatigue:", person_fatigue)
            print("person_state:", state.dynamic.person_state)
            raise AssertionError("Person state became NaN.")

    t3 = time.perf_counter()

    compile_s = t1 - t0
    log_alloc_s = t2 - t1
    sim_s = t3 - t2
    total_s = t3 - t0

    simulated_hours = float(N_TIMESTEPS) * float(DT_MINUTES) / 60.0
    sim_hours_per_second = simulated_hours / sim_s
    seconds_per_timestep = sim_s / float(N_TIMESTEPS)

    print()
    print("ABBEY 8760-hour multizone dwelling benchmark")
    print("------------------------------------------------")
    print("timesteps:", N_TIMESTEPS)
    print("dt_minutes:", DT_MINUTES)
    print("simulated_hours:", simulated_hours)
    print("zones:", state.dynamic.zone_state.shape[0])
    print("people:", state.dynamic.person_state.shape[0])
    print("systems:", state.dynamic.system_state.shape[0])
    print("actions:", state.static.action_static.shape[0])
    print("write_logs:", WRITE_LOGS)
    print("run_acoustics:", RUN_ACOUSTICS)
    print()
    print("compile_s:", compile_s)
    print("log_alloc_s:", log_alloc_s)
    print("simulation_loop_s:", sim_s)
    print("total_s:", total_s)
    print("seconds_per_timestep:", seconds_per_timestep)
    print("simulated_hours_per_second:", sim_hours_per_second)
    print()

    print("Final zone temperatures:")
    for i in range(state.dynamic.zone_state.shape[0]):
        zone_id_num = int(state.dynamic.zone_state[i, schema.ZONE_ID])
        zone_name = state.mappings.zone_id_to_name.get(zone_id_num, str(zone_id_num))
        temp = state.dynamic.zone_state[i, schema.ZONE_AIR_TEMPERATURE_C]
        co2 = state.dynamic.zone_state[i, schema.ZONE_CO2_PPM]
        rh = state.dynamic.zone_state[i, schema.ZONE_RELATIVE_HUMIDITY]
        print(zone_name, "T=", temp, "CO2=", co2, "RH=", rh)

    print()
    print("Final people:")
    for i in range(state.dynamic.person_state.shape[0]):
        person_id_num = int(state.dynamic.person_state[i, schema.PERSON_ID])
        person_name = state.mappings.person_id_to_name.get(person_id_num, str(person_id_num))
        zone_id = int(state.dynamic.person_state[i, schema.PERSON_CURRENT_ZONE_ID])
        zone_name = state.mappings.zone_id_to_name.get(zone_id, str(zone_id))
        hunger = state.dynamic.person_state[i, schema.PERSON_HUNGER]
        fatigue = state.dynamic.person_state[i, schema.PERSON_FATIGUE]
        action_id = int(state.dynamic.person_state[i, schema.PERSON_CURRENT_ACTION_ID])
        action_name = state.mappings.action_id_to_name.get(action_id, str(action_id))
        print(person_name, "zone=", zone_name, "hunger=", hunger, "fatigue=", fatigue, "action=", action_name)

    if logs is not None:
        print()
        print("Log shapes:")
        print("person_log:", logs.person_log.shape)
        print("zone_log:", logs.zone_log.shape)
        print("system_log:", logs.system_log.shape)
        print("dwelling_log:", logs.dwelling_log.shape)
        print("building_log:", logs.building_log.shape)


def main():
    run_benchmark()


if __name__ == "__main__":
    main()
