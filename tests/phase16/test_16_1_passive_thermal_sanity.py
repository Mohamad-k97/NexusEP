"""
ABBEY Phase 16.1 passive thermal sanity tests.

Goal:
    Directional sanity checks before adding more complexity.

Run:
    python -m pytest tests/phase16/test_16_1_passive_thermal_sanity.py

Provenance:
    adapted from the surviving package-level Phase 16.1 script at frozen HEAD.
"""

from tests.phase16.test_16_0_validation_harness import (
    make_phase16_building,
    make_phase16_weather,
    run_phase16_case,
    phase16_zone_ids,
    assert_true,
    assert_direction,
)


# ============================================================
# TEST HELPERS
# ============================================================

def zone_row(case_out, zone_id, step=None):
    df = case_out["zone_df"]

    subset = df[df["zone_id"] == zone_id]

    if step is not None:
        subset = subset[subset["step"] == step]

    assert_true(
        not subset.empty,
        "No zone row found for " + str(zone_id),
    )

    return subset.iloc[-1].to_dict()


def zone_temp_from_building(building, zone_id):
    return float(
        building.get_zone_state(zone_id).indoor_temp_c
    )


def set_uniform_zone_temperatures(
    building,
    air_temp_c=20.0,
    mass_temp_c=None,
    co2_ppm=600.0,
):
    if mass_temp_c is None:
        mass_temp_c = air_temp_c

    for zone_id in phase16_zone_ids(building):
        state = building.get_zone_state(zone_id)

        building.set_zone_state(
            zone_id,
            state.copy(
                indoor_temp_c=float(air_temp_c),
                indoor_mass_temp_c=float(mass_temp_c),
                co2_ppm=float(co2_ppm),
                indoor_relative_humidity_percent=50.0,
                indoor_humidity_ratio_kg_kg=0.008,
            ),
        )


def disable_active_controls(building):
    """
    Make the case passive:
        no heating
        no cooling
        no mechanical ventilation command
        no lights
        closed windows
        open curtains

    We do not delete systems. We only disable commands/control intent.
    """

    for dwelling in building.dwellings.values():
        for zone_id, control_state in dwelling.control_states.items():
            dwelling.control_states[zone_id] = control_state.copy(
                heating_mode="off",
                manual_heating_on=False,
                cooling_mode="off",
                manual_cooling_on=False,
                ventilation_mode="manual",
                manual_ventilation_on=False,
                lighting_mode="manual",
                manual_lights_on=False,
                window_mode="manual",
                manual_window_open=False,
                shading_mode="manual",
                manual_curtain_open=True,
            )

    if hasattr(building, "building_control_states"):
        for zone_id, control_state in building.building_control_states.items():
            building.building_control_states[zone_id] = control_state.copy(
                heating_mode="off",
                manual_heating_on=False,
                cooling_mode="off",
                manual_cooling_on=False,
                ventilation_mode="manual",
                manual_ventilation_on=False,
                lighting_mode="manual",
                manual_lights_on=False,
                window_mode="manual",
                manual_window_open=False,
                shading_mode="manual",
                manual_curtain_open=True,
            )


def make_passive_building(
    uniform_temp_c=20.0,
):
    building = make_phase16_building()

    set_uniform_zone_temperatures(
        building=building,
        air_temp_c=uniform_temp_c,
        mass_temp_c=uniform_temp_c,
        co2_ppm=600.0,
    )

    disable_active_controls(building)

    return building


def make_person_in_zone(
    person_id,
    zone_id,
):
    people = {
        person_id: {
            "person_id": person_id,
        }
    }

    locations = {
        person_id: {
            "is_home": True,
            "current_space_id": zone_id,
            "current_activity": "idle",
        }
    }

    return people, locations


def make_cooking_chunk(
    zone_id,
    actor_id="person_1",
    minutes=10.0,
    power_w=2000.0,
):
    return {
        "chunk_index": 0,
        "minutes": float(minutes),
        "power_breakdown": [
            {
                "name": "cook",
                "actor_id": actor_id,
                "target_space_id": zone_id,
                "target_zone_role": "kitchen",
                "minutes": float(minutes),
                "power_w": float(power_w),
            }
        ],
    }


# ============================================================
# TESTS
# ============================================================

def test_closed_unoccupied_room_drifts_toward_outdoor_temperature():
    building = make_passive_building(
        uniform_temp_c=20.0,
    )

    zone_id = "dwelling_1_living_room"
    initial_temp = zone_temp_from_building(
        building=building,
        zone_id=zone_id,
    )

    weather = make_phase16_weather(
        outdoor_temperature_c=5.0,
        wind_speed_m_s=0.0,
        direct_normal_radiation_w_m2=0.0,
        diffuse_horizontal_radiation_w_m2=0.0,
        global_horizontal_radiation_w_m2=0.0,
        outdoor_illuminance_lux=0.0,
    )

    out = run_phase16_case(
        building=building,
        weather_state=weather,
        dt_minutes=10.0,
        number_of_steps=36,
        use_physics_engine=True,
        allow_legacy_physics_fallback=False,
        people={},
        locations={},
        chunk_records=[],
        validate_outputs=True,
    )

    row = zone_row(out, zone_id)
    final_temp = float(row["indoor_temp_c"])

    assert_direction(
        before=initial_temp,
        after=final_temp,
        direction="decrease",
        message="Closed unoccupied room should drift downward toward cold outdoors.",
        tolerance=1e-6,
    )

    assert_true(
        final_temp > 5.0,
        "Room should drift toward outdoor temperature, not instantly become outdoor temperature.",
    )

    assert_true(
        not bool(row["heating_on"]),
        "Heating should be off in passive drift test.",
    )

    print("PASS: test_closed_unoccupied_room_drifts_toward_outdoor_temperature")


def test_occupied_closed_room_warms_or_cools_more_slowly_than_unoccupied():
    zone_id = "dwelling_1_living_room"

    weather = make_phase16_weather(
        outdoor_temperature_c=20.0,
        wind_speed_m_s=0.0,
        direct_normal_radiation_w_m2=0.0,
        diffuse_horizontal_radiation_w_m2=0.0,
        global_horizontal_radiation_w_m2=0.0,
        outdoor_illuminance_lux=0.0,
    )

    unoccupied_building = make_passive_building(
        uniform_temp_c=20.0,
    )

    unoccupied = run_phase16_case(
        building=unoccupied_building,
        weather_state=weather,
        dt_minutes=10.0,
        number_of_steps=18,
        use_physics_engine=True,
        allow_legacy_physics_fallback=False,
        people={},
        locations={},
        chunk_records=[],
        validate_outputs=True,
    )

    occupied_building = make_passive_building(
        uniform_temp_c=20.0,
    )

    people, locations = make_person_in_zone(
        person_id="person_1",
        zone_id=zone_id,
    )

    occupied = run_phase16_case(
        building=occupied_building,
        weather_state=weather,
        dt_minutes=10.0,
        number_of_steps=18,
        use_physics_engine=True,
        allow_legacy_physics_fallback=False,
        people=people,
        locations=locations,
        chunk_records=[],
        validate_outputs=True,
    )

    unoccupied_row = zone_row(unoccupied, zone_id)
    occupied_row = zone_row(occupied, zone_id)

    unoccupied_temp = float(unoccupied_row["indoor_temp_c"])
    occupied_temp = float(occupied_row["indoor_temp_c"])

    assert_true(
        occupied_temp > unoccupied_temp,
        (
            "Occupied room should be warmer than unoccupied baseline. "
            + "occupied="
            + str(occupied_temp)
            + ", unoccupied="
            + str(unoccupied_temp)
        ),
    )
    
    assert_true(
        float(occupied_row["internal_source_record_count"]) > 0.0,
        "Occupied room should have internal source records.",
    )

    assert_true(
        float(occupied_row["internal_average_sensible_heat_w"]) > 0.0,
        "Occupied room should expose sensible internal heat.",
    )

    print("PASS: test_occupied_closed_room_warms_or_cools_more_slowly_than_unoccupied")


def test_cooking_heats_kitchen_compared_with_no_cooking_baseline():
    zone_id = "dwelling_1_kitchen"

    weather = make_phase16_weather(
        outdoor_temperature_c=20.0,
        wind_speed_m_s=0.0,
        direct_normal_radiation_w_m2=0.0,
        diffuse_horizontal_radiation_w_m2=0.0,
        global_horizontal_radiation_w_m2=0.0,
        outdoor_illuminance_lux=0.0,
    )

    baseline_building = make_passive_building(
        uniform_temp_c=20.0,
    )

    baseline = run_phase16_case(
        building=baseline_building,
        weather_state=weather,
        dt_minutes=10.0,
        number_of_steps=12,
        use_physics_engine=True,
        allow_legacy_physics_fallback=False,
        people={},
        locations={},
        chunk_records=[],
        validate_outputs=True,
    )

    cooking_building = make_passive_building(
        uniform_temp_c=20.0,
    )

    people, locations = make_person_in_zone(
        person_id="person_1",
        zone_id=zone_id,
    )

    cooking_chunk = make_cooking_chunk(
        zone_id=zone_id,
        actor_id="person_1",
        minutes=10.0,
        power_w=2000.0,
    )

    cooking = run_phase16_case(
        building=cooking_building,
        weather_state=weather,
        dt_minutes=10.0,
        number_of_steps=12,
        use_physics_engine=True,
        allow_legacy_physics_fallback=False,
        people=people,
        locations=locations,
        chunk_records=[cooking_chunk],
        validate_outputs=True,
    )

    baseline_row = zone_row(baseline, zone_id)
    cooking_row = zone_row(cooking, zone_id)

    baseline_temp = float(baseline_row["indoor_temp_c"])
    cooking_temp = float(cooking_row["indoor_temp_c"])

    assert_true(
        cooking_temp > baseline_temp,
        (
            "Cooking should heat the kitchen compared with no-cooking baseline. "
            + "cooking="
            + str(cooking_temp)
            + ", baseline="
            + str(baseline_temp)
        ),
    )

    assert_true(
        float(cooking_row["internal_source_record_count"]) > 0.0,
        "Cooking case should have internal source records.",
    )

    assert_true(
        float(cooking_row["internal_average_sensible_heat_w"]) > 0.0,
        "Cooking case should expose sensible heat in zone records.",
    )

    assert_true(
        float(cooking_row["internal_electricity_wh"]) > 0.0,
        "Cooking case should expose internal electricity in zone records.",
    )

    assert_true(
        float(cooking_row["appliance_energy_wh"]) > 0.0,
        "Cooking case should expose appliance energy in zone energy accounting.",
    )

    print("PASS: test_cooking_heats_kitchen_compared_with_no_cooking_baseline")


def test_temperature_changes_are_directional_not_exact():
    """
    Guardrail test:
        Phase 16.1 checks signs/directions, not exact calibrated magnitudes.
    """

    cold_building = make_passive_building(
        uniform_temp_c=20.0,
    )

    warm_building = make_passive_building(
        uniform_temp_c=20.0,
    )

    zone_id = "dwelling_1_living_room"

    cold_weather = make_phase16_weather(
        outdoor_temperature_c=5.0,
        wind_speed_m_s=0.0,
        direct_normal_radiation_w_m2=0.0,
        diffuse_horizontal_radiation_w_m2=0.0,
        global_horizontal_radiation_w_m2=0.0,
        outdoor_illuminance_lux=0.0,
    )

    warm_weather = make_phase16_weather(
        outdoor_temperature_c=30.0,
        wind_speed_m_s=0.0,
        direct_normal_radiation_w_m2=0.0,
        diffuse_horizontal_radiation_w_m2=0.0,
        global_horizontal_radiation_w_m2=0.0,
        outdoor_illuminance_lux=0.0,
    )

    cold_case = run_phase16_case(
        building=cold_building,
        weather_state=cold_weather,
        dt_minutes=10.0,
        number_of_steps=12,
        use_physics_engine=True,
        allow_legacy_physics_fallback=False,
        people={},
        locations={},
        chunk_records=[],
        validate_outputs=True,
    )

    warm_case = run_phase16_case(
        building=warm_building,
        weather_state=warm_weather,
        dt_minutes=10.0,
        number_of_steps=12,
        use_physics_engine=True,
        allow_legacy_physics_fallback=False,
        people={},
        locations={},
        chunk_records=[],
        validate_outputs=True,
    )

    cold_temp = float(zone_row(cold_case, zone_id)["indoor_temp_c"])
    warm_temp = float(zone_row(warm_case, zone_id)["indoor_temp_c"])

    assert_true(
        warm_temp > cold_temp,
        (
            "Warm outdoor case should finish warmer than cold outdoor case. "
            + "warm="
            + str(warm_temp)
            + ", cold="
            + str(cold_temp)
        ),
    )

    print("PASS: test_temperature_changes_are_directional_not_exact")


def main():
    test_closed_unoccupied_room_drifts_toward_outdoor_temperature()
    test_occupied_closed_room_warms_or_cools_more_slowly_than_unoccupied()
    test_cooking_heats_kitchen_compared_with_no_cooking_baseline()
    test_temperature_changes_are_directional_not_exact()

    print("Phase 16.1 passive thermal sanity tests passed.")


if __name__ == "__main__":
    main()
