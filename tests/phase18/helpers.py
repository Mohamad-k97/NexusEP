"""
Shared validation helpers for ABBEY Phase 18 array-refactor tests.
"""

from nexusep.abbey.arrays import schema


def make_one_person_one_zone_input(n_timesteps=4):
    return {
        "dt_minutes": 15,
        "n_timesteps": n_timesteps,
        "start_minute_of_day": 8 * 60,

        "weather_series": [
            {
                "outdoor_temperature_C": 5.0 + i,
                "relative_humidity": 0.60,
                "outdoor_co2_ppm": 420.0,
                "wind_speed_m_s": 2.0 + i,
                "ghi_W_m2": 100.0 + 100.0 * i,
            }
            for i in range(n_timesteps)
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

        "actions": make_default_validation_actions(sleep_zone_id="main_room"),
    }


def make_one_person_two_zone_input(n_timesteps=4):
    data = make_one_person_one_zone_input(n_timesteps=n_timesteps)

    data["zones"] = [
        data["zones"][0],
        {
            "id": "bedroom",
            "type": "bedroom",
            "dwelling_id": "dwelling_001",
            "building_id": "building_001",

            "floor_area_m2": 20.0,
            "volume_m3": 50.0,
            "height_m": 2.5,

            "air_temperature_C": 19.0,
            "mean_radiant_temperature_C": 19.0,
            "relative_humidity": 0.45,
            "co2_ppm": 700.0,
            "illuminance_lux": 20.0,
            "noise_db": 30.0,

            "heat_capacity_J_K": 1500000.0,
            "ua_envelope_W_K": 80.0,
            "ua_internal_W_K": 20.0,

            "min_comfort_temp_C": 19.0,
            "max_comfort_temp_C": 25.0,
            "min_illuminance_lux": 100.0,
            "max_co2_ppm": 1000.0,
            "max_noise_db": 40.0,
        },
    ]

    data["persons"][0]["sleep_zone_id"] = "bedroom"

    data["systems"].append(
        {
            "id": "system_bedroom",
            "dwelling_id": "dwelling_001",
            "zone_id": "bedroom",

            "has_heating": True,
            "has_cooling": False,
            "has_window": True,
            "has_lights": True,
            "has_blinds": True,
            "has_mech_ventilation": False,

            "hvac_mode": "off",
            "ventilation_mode": "off",

            "heating_setpoint_C": 19.0,
            "cooling_setpoint_C": 26.0,

            "window_open_fraction": 0.0,
            "light_on": False,
            "blind_closed_fraction": 0.0,

            "max_heating_power_W": 1500.0,
            "max_cooling_power_W": 0.0,
            "max_lighting_power_W": 80.0,
            "max_window_flow_m3_s": 0.10,
            "max_mech_vent_flow_m3_s": 0.0,
        }
    )
    data["actions"] = make_default_validation_actions(sleep_zone_id="bedroom")
    return data


def make_default_validation_actions(sleep_zone_id="main_room"):
    return [
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
            "id": "sleep",
            "type": "sleep",
            "target_zone_id": sleep_zone_id,
            "duration_min": 480.0,
            "requires_home": True,
            "requires_awake": False,
            "can_run_while_away": False,
            "fatigue_effect": -1.0,
            "friction": 0.1,
        },
        {
            "id": "leave_home",
            "type": "leave_home",
            "target_zone_id": "main_room",
            "duration_min": 1.0,
            "requires_home": True,
            "requires_awake": True,
            "friction": 0.1,
        },
        {
            "id": "return_home",
            "type": "return_home",
            "target_zone_id": "main_room",
            "duration_min": 1.0,
            "requires_home": False,
            "requires_awake": True,
            "can_run_while_away": True,
            "friction": 0.1,
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
            "id": "do_laundry",
            "type": "do_laundry",
            "target_zone_id": "main_room",
            "target_system_id": "system_main_room",
            "appliance_type": "washing_machine",
            "duration_min": 60.0,
            "requires_home": True,
            "requires_awake": True,
            "is_background": True,
            "can_run_while_away": True,
            "power_W": 500.0,
            "heat_gain_W": 100.0,
            "dirty_clothes_effect": -0.8,
            "friction": 0.3,
        },
    ]


def get_id_from_state_mapping(state, mapping_name, name):
    mappings = state.mappings
    mapping = getattr(mappings, mapping_name)
    return mapping[name]


def assert_close(a, b, tol=1.0e-9):
    assert abs(float(a) - float(b)) <= tol, "%s != %s" % (a, b)


def print_passed(name):
    print("%s passed." % name)