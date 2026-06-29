"""
ABBEY Phase 16.7 timestep stability sanity tests.

Goal:
    Compare short 1-minute and 10-minute runs for numerical sanity.

Run:
    python run_test_phase_16_7_timestep_stability_sanity.py
"""

import math
import pandas as pd

from run_test_phase_16_0_validation_harness import (
    make_phase16_building,
    make_phase16_weather,
    run_phase16_case,
    phase16_zone_ids,
    assert_true,
)

from nexusep.abbey.building.outputs import (
    OUTPUT_MODE_STANDARD,
    validate_building_output_dataframes,
)


TARGET_ZONE_ID = "dwelling_1_living_room"
CO2_ZONE_ID = "dwelling_1_bedroom_1"

INITIAL_TEMP_C = 20.0
COLD_OUTDOOR_TEMP_C = 5.0
INITIAL_CO2_PPM = 600.0

ENERGY_TOLERANCE_WH = 1e-6


# ============================================================
# BASIC HELPERS
# ============================================================

def assert_close_enough_sign(
    value,
    expected_sign,
    message,
    tolerance=1e-9,
):
    value = float(value)

    if expected_sign == "negative":
        assert_true(
            value < -float(tolerance),
            message + " value=" + str(value),
        )
        return

    if expected_sign == "positive":
        assert_true(
            value > float(tolerance),
            message + " value=" + str(value),
        )
        return

    raise ValueError("expected_sign must be positive or negative.")


def final_zone_row(case_out, zone_id):
    df = case_out["zone_df"]
    subset = df[df["zone_id"] == zone_id]

    assert_true(
        not subset.empty,
        "No zone rows found for " + str(zone_id),
    )

    return subset.iloc[-1].to_dict()


def numeric_columns(df):
    return [
        column
        for column in df.columns
        if pd.api.types.is_numeric_dtype(df[column])
    ]


def assert_dataframe_has_no_nan_or_infinite(df, name):
    assert_true(
        df is not None,
        name + " dataframe should not be None.",
    )

    assert_true(
        not df.empty,
        name + " dataframe should not be empty.",
    )

    for column in numeric_columns(df):
        for value in df[column].tolist():
            assert_true(
                pd.notna(value),
                name + "." + column + " contains NaN.",
            )

            assert_true(
                math.isfinite(float(value)),
                name + "." + column + " contains infinite value.",
            )


def assert_case_has_no_nan_or_infinite(case_out, label):
    assert_dataframe_has_no_nan_or_infinite(
        case_out["zone_df"],
        label + ".zone_df",
    )

    assert_dataframe_has_no_nan_or_infinite(
        case_out["dwelling_df"],
        label + ".dwelling_df",
    )

    assert_dataframe_has_no_nan_or_infinite(
        case_out["building_df"],
        label + ".building_df",
    )


def assert_temperatures_plausible(case_out, label):
    zone_df = case_out["zone_df"]

    for column in [
        "indoor_temp_c",
        "indoor_mass_temp_c",
    ]:
        assert_true(
            column in zone_df.columns,
            label + " missing " + column,
        )

        for value in zone_df[column].tolist():
            value = float(value)

            assert_true(
                -20.0 <= value <= 60.0,
                label + "." + column + " outside plausible range: " + str(value),
            )


def assert_co2_plausible(case_out, label):
    zone_df = case_out["zone_df"]

    assert_true(
        "co2_ppm" in zone_df.columns,
        label + " missing co2_ppm.",
    )

    for value in zone_df["co2_ppm"].tolist():
        value = float(value)

        assert_true(
            300.0 <= value <= 10000.0,
            label + ".co2_ppm outside plausible range: " + str(value),
        )


def assert_energy_non_negative(case_out, label):
    for df_name in [
        "zone_df",
        "dwelling_df",
        "building_df",
    ]:
        df = case_out[df_name]

        energy_columns = [
            column
            for column in df.columns
            if column.endswith("_energy_wh")
            or column in [
                "total_energy_wh",
                "zone_total_energy_wh",
                "private_zone_energy_wh",
                "shared_zone_energy_wh",
                "private_total_energy_wh",
                "shared_total_energy_wh",
                "building_energy_result_total_energy_wh",
            ]
        ]

        for column in energy_columns:
            values = pd.to_numeric(
                df[column],
                errors="coerce",
            )

            for value in values.tolist():
                assert_true(
                    pd.notna(value),
                    label + "." + df_name + "." + column + " contains NaN.",
                )

                assert_true(
                    float(value) >= -ENERGY_TOLERANCE_WH,
                    label + "." + df_name + "." + column
                    + " is negative: "
                    + str(value),
                )


def assert_output_validation_passes(case_out, label):
    validation = validate_building_output_dataframes(
        zone_df=case_out["zone_df"],
        dwelling_df=case_out["dwelling_df"],
        building_df=case_out["building_df"],
        mode=OUTPUT_MODE_STANDARD,
        tolerance_wh=ENERGY_TOLERANCE_WH,
    )

    assert_true(
        validation["ok"],
        label
        + " validate_building_output_dataframes failed. errors="
        + str(validation.get("errors", []))
        + ", missing_columns="
        + str(validation.get("missing_columns", []))
        + ", energy_checks="
        + str(validation.get("energy_checks", {})),
    )


# ============================================================
# BUILDING SETUP
# ============================================================

def set_uniform_zone_state(
    building,
    indoor_temp_c=20.0,
    mass_temp_c=None,
    co2_ppm=600.0,
):
    if mass_temp_c is None:
        mass_temp_c = indoor_temp_c

    for zone_id in phase16_zone_ids(building):
        state = building.get_zone_state(zone_id)

        building.set_zone_state(
            zone_id,
            state.copy(
                indoor_temp_c=float(indoor_temp_c),
                indoor_mass_temp_c=float(mass_temp_c),
                co2_ppm=float(co2_ppm),
                indoor_relative_humidity_percent=50.0,
                indoor_humidity_ratio_kg_kg=0.008,
            ),
        )


def set_zone_co2(
    building,
    zone_id,
    co2_ppm,
):
    state = building.get_zone_state(zone_id)

    building.set_zone_state(
        zone_id,
        state.copy(
            co2_ppm=float(co2_ppm),
            indoor_relative_humidity_percent=50.0,
            indoor_humidity_ratio_kg_kg=0.008,
        ),
    )


def set_passive_closed_controls(building):
    """
    Disable active systems so thermal direction is driven by envelope/airflow,
    not thermostat control.
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


def make_person_in_zone(
    person_id,
    zone_id,
    activity="sleeping",
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
            "current_activity": activity,
        }
    }

    return people, locations


def make_cold_weather():
    return make_phase16_weather(
        outdoor_temperature_c=COLD_OUTDOOR_TEMP_C,
        outdoor_co2_ppm=420.0,
        wind_speed_m_s=0.0,
        wind_direction_deg=0.0,
        direct_normal_radiation_w_m2=0.0,
        diffuse_horizontal_radiation_w_m2=0.0,
        global_horizontal_radiation_w_m2=0.0,
        outdoor_illuminance_lux=0.0,
        relative_humidity_percent=50.0,
    )


def make_neutral_weather():
    return make_phase16_weather(
        outdoor_temperature_c=20.0,
        outdoor_co2_ppm=420.0,
        wind_speed_m_s=0.0,
        wind_direction_deg=0.0,
        direct_normal_radiation_w_m2=0.0,
        diffuse_horizontal_radiation_w_m2=0.0,
        global_horizontal_radiation_w_m2=0.0,
        outdoor_illuminance_lux=0.0,
        relative_humidity_percent=50.0,
    )


# ============================================================
# CASES
# ============================================================

def make_passive_cooling_case(
    dt_minutes,
    duration_minutes=120.0,
):
    building = make_phase16_building()

    set_uniform_zone_state(
        building=building,
        indoor_temp_c=INITIAL_TEMP_C,
        mass_temp_c=INITIAL_TEMP_C,
        co2_ppm=INITIAL_CO2_PPM,
    )

    set_passive_closed_controls(building)

    number_of_steps = int(round(float(duration_minutes) / float(dt_minutes)))

    return run_phase16_case(
        building=building,
        weather_state=make_cold_weather(),
        dt_minutes=float(dt_minutes),
        number_of_steps=number_of_steps,
        use_physics_engine=True,
        allow_legacy_physics_fallback=False,
        people={},
        locations={},
        chunk_records=[],
        validate_outputs=True,
        validation_mode=OUTPUT_MODE_STANDARD,
    )


def make_closed_occupied_co2_case(
    dt_minutes,
    duration_minutes=120.0,
):
    building = make_phase16_building()

    set_uniform_zone_state(
        building=building,
        indoor_temp_c=20.0,
        mass_temp_c=20.0,
        co2_ppm=INITIAL_CO2_PPM,
    )

    set_zone_co2(
        building=building,
        zone_id=CO2_ZONE_ID,
        co2_ppm=INITIAL_CO2_PPM,
    )

    set_passive_closed_controls(building)

    people, locations = make_person_in_zone(
        person_id="person_1",
        zone_id=CO2_ZONE_ID,
        activity="sleeping",
    )

    number_of_steps = int(round(float(duration_minutes) / float(dt_minutes)))

    return run_phase16_case(
        building=building,
        weather_state=make_neutral_weather(),
        dt_minutes=float(dt_minutes),
        number_of_steps=number_of_steps,
        use_physics_engine=True,
        allow_legacy_physics_fallback=False,
        people=people,
        locations=locations,
        chunk_records=[],
        validate_outputs=True,
        validation_mode=OUTPUT_MODE_STANDARD,
    )


# ============================================================
# TESTS
# ============================================================

def test_1_minute_timestep_run_completes():
    case = make_passive_cooling_case(
        dt_minutes=1.0,
        duration_minutes=120.0,
    )

    assert_true(
        len(case["zone_df"]) > 0,
        "1-minute timestep run should produce zone rows.",
    )

    assert_output_validation_passes(case, "1-minute passive cooling")

    print("PASS: test_1_minute_timestep_run_completes")


def test_10_minute_timestep_run_completes():
    case = make_passive_cooling_case(
        dt_minutes=10.0,
        duration_minutes=120.0,
    )

    assert_true(
        len(case["zone_df"]) > 0,
        "10-minute timestep run should produce zone rows.",
    )

    assert_output_validation_passes(case, "10-minute passive cooling")

    print("PASS: test_10_minute_timestep_run_completes")


def test_no_nan_or_infinite_values():
    case_1m = make_passive_cooling_case(
        dt_minutes=1.0,
        duration_minutes=120.0,
    )

    case_10m = make_passive_cooling_case(
        dt_minutes=10.0,
        duration_minutes=120.0,
    )

    assert_case_has_no_nan_or_infinite(case_1m, "1-minute")
    assert_case_has_no_nan_or_infinite(case_10m, "10-minute")

    print("PASS: test_no_nan_or_infinite_values")


def test_temperatures_remain_plausible():
    case_1m = make_passive_cooling_case(
        dt_minutes=1.0,
        duration_minutes=120.0,
    )

    case_10m = make_passive_cooling_case(
        dt_minutes=10.0,
        duration_minutes=120.0,
    )

    assert_temperatures_plausible(case_1m, "1-minute")
    assert_temperatures_plausible(case_10m, "10-minute")

    print("PASS: test_temperatures_remain_plausible")


def test_co2_remains_plausible():
    case_1m = make_closed_occupied_co2_case(
        dt_minutes=1.0,
        duration_minutes=120.0,
    )

    case_10m = make_closed_occupied_co2_case(
        dt_minutes=10.0,
        duration_minutes=120.0,
    )

    assert_co2_plausible(case_1m, "1-minute")
    assert_co2_plausible(case_10m, "10-minute")

    print("PASS: test_co2_remains_plausible")


def test_energy_remains_non_negative():
    case_1m = make_closed_occupied_co2_case(
        dt_minutes=1.0,
        duration_minutes=120.0,
    )

    case_10m = make_closed_occupied_co2_case(
        dt_minutes=10.0,
        duration_minutes=120.0,
    )

    assert_energy_non_negative(case_1m, "1-minute")
    assert_energy_non_negative(case_10m, "10-minute")

    print("PASS: test_energy_remains_non_negative")


def test_thermal_direction_consistent_between_1_and_10_minute_runs():
    case_1m = make_passive_cooling_case(
        dt_minutes=1.0,
        duration_minutes=120.0,
    )

    case_10m = make_passive_cooling_case(
        dt_minutes=10.0,
        duration_minutes=120.0,
    )

    row_1m = final_zone_row(case_1m, TARGET_ZONE_ID)
    row_10m = final_zone_row(case_10m, TARGET_ZONE_ID)

    delta_1m = float(row_1m["indoor_temp_c"]) - INITIAL_TEMP_C
    delta_10m = float(row_10m["indoor_temp_c"]) - INITIAL_TEMP_C

    assert_close_enough_sign(
        delta_1m,
        expected_sign="negative",
        message="1-minute cold passive case should cool.",
    )

    assert_close_enough_sign(
        delta_10m,
        expected_sign="negative",
        message="10-minute cold passive case should cool.",
    )

    assert_true(
        float(row_1m["indoor_temp_c"]) > COLD_OUTDOOR_TEMP_C,
        "1-minute case should move toward outdoor temperature, not jump to it.",
    )

    assert_true(
        float(row_10m["indoor_temp_c"]) > COLD_OUTDOOR_TEMP_C,
        "10-minute case should move toward outdoor temperature, not jump to it.",
    )

    print("PASS: test_thermal_direction_consistent_between_1_and_10_minute_runs")


def test_co2_direction_consistent_between_1_and_10_minute_runs():
    case_1m = make_closed_occupied_co2_case(
        dt_minutes=1.0,
        duration_minutes=120.0,
    )

    case_10m = make_closed_occupied_co2_case(
        dt_minutes=10.0,
        duration_minutes=120.0,
    )

    row_1m = final_zone_row(case_1m, CO2_ZONE_ID)
    row_10m = final_zone_row(case_10m, CO2_ZONE_ID)

    delta_1m = float(row_1m["co2_ppm"]) - INITIAL_CO2_PPM
    delta_10m = float(row_10m["co2_ppm"]) - INITIAL_CO2_PPM

    assert_close_enough_sign(
        delta_1m,
        expected_sign="positive",
        message="1-minute closed occupied case should increase CO2.",
    )

    assert_close_enough_sign(
        delta_10m,
        expected_sign="positive",
        message="10-minute closed occupied case should increase CO2.",
    )

    print("PASS: test_co2_direction_consistent_between_1_and_10_minute_runs")


def test_validators_pass_for_both_timesteps():
    case_1m = make_closed_occupied_co2_case(
        dt_minutes=1.0,
        duration_minutes=120.0,
    )

    case_10m = make_closed_occupied_co2_case(
        dt_minutes=10.0,
        duration_minutes=120.0,
    )

    assert_output_validation_passes(case_1m, "1-minute occupied CO2")
    assert_output_validation_passes(case_10m, "10-minute occupied CO2")

    print("PASS: test_validators_pass_for_both_timesteps")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    test_1_minute_timestep_run_completes()
    test_10_minute_timestep_run_completes()
    test_no_nan_or_infinite_values()
    test_temperatures_remain_plausible()
    test_co2_remains_plausible()
    test_energy_remains_non_negative()
    test_thermal_direction_consistent_between_1_and_10_minute_runs()
    test_co2_direction_consistent_between_1_and_10_minute_runs()
    test_validators_pass_for_both_timesteps()

    print("Phase 16.7 timestep stability sanity tests passed.")