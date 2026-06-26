import pandas as pd

from nexusep.abbey.building.outputs import (
    OUTPUT_MODE_DEBUG,
    output_columns_for_record_type,
    validate_zone_timestep_record_schema,
    validate_dwelling_timestep_record_schema,
    validate_building_timestep_record_schema,
    validate_energy_consistency,
    validate_building_output_dataframes,
)


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def default_value_for_column(column):
    string_columns = {
        "building_id",
        "dwelling_id",
        "zone_id",
        "zone_name",
        "zone_scope",
        "occupied_person_ids",
        "physics_engine_source",
        "physics_path",
        "performance_path",
        "legacy_fallback_reason",
        "visual_comfort_status",
        "window_orientation_deg_list",
        "record_level",
        "diagnostic_output_mode",
    }

    bool_columns = {
        "heating_on",
        "cooling_on",
        "lights_on",
        "window_open",
        "curtain_open",
        "command_heating_on",
        "command_cooling_on",
        "command_lights_on",
        "command_window_open",
        "command_curtain_open",
        "lighting_result_lights_on",
        "physics_engine_active",
        "legacy_fallback_used",
        "zone_energy_balance_ok",
        "energy_balance_ok",
        "building_zone_energy_balance_ok",
        "physics_engine_has_thermal_step_result",
        "physics_engine_has_interzone_thermal_network",
        "physics_engine_has_airflow_network",
        "physics_engine_has_co2_step_result",
        "physics_engine_has_moisture_step_result",
        "physics_engine_has_acoustic_step_result",
        "has_acoustic_step_result",
    }

    normalized_columns = {
        "indoor_daylight",
        "indoor_noise",
        "old_indoor_daylight",
        "new_indoor_daylight",
        "proposed_indoor_daylight",
        "old_indoor_noise",
        "new_indoor_noise",
        "proposed_indoor_noise",
        "heating_power_fraction",
        "cooling_power_fraction",
        "command_heating_power_fraction",
        "command_cooling_power_fraction",
        "command_window_opening_fraction",
        "window_solar_alignment_factor_max",
        "window_daylight_alignment_factor_max",
        "window_effective_solar_factor_max",
        "window_effective_visible_transmittance_max",
        "lighting_result_dimming_fraction",
        "acoustic_discomfort_input",
        "mean_indoor_daylight",
        "mean_indoor_noise",
    }

    dict_columns = {
        "internal_average_sensible_heat_w_by_source_kind",
        "internal_average_electricity_power_w_by_source_kind",
        "internal_average_co2_generation_m3_h_by_source_kind",
        "internal_average_moisture_generation_kg_h_by_source_kind",
        "internal_record_count_by_source_kind",
        "internal_electricity_wh_by_source_kind",
        "internal_average_latent_heat_w_by_source_kind",
    }

    if column in string_columns:
        if column == "building_id":
            return "b1"
        if column == "dwelling_id":
            return "d1"
        if column == "zone_id":
            return "z1"
        if column == "zone_scope":
            return "private"
        if column == "record_level":
            return "building_timestep"
        if column == "diagnostic_output_mode":
            return "debug"
        return ""

    if column in bool_columns:
        return False

    if column in normalized_columns:
        return 0.5

    if column in dict_columns:
        return {}

    if column in ("step", "day"):
        return 0

    if column == "hour":
        return 0.0

    return 0.0


def make_zone_df():
    row = {
        column: default_value_for_column(column)
        for column in output_columns_for_record_type("zone", OUTPUT_MODE_DEBUG)
    }

    row.update(
        {
            "building_id": "b1",
            "dwelling_id": "d1",
            "zone_id": "z1",
            "zone_scope": "private",
            "number_of_people": 1,

            "heating_energy_wh": 2.0,
            "cooling_energy_wh": 0.0,
            "ventilation_fan_energy_wh": 1.0,
            "hvac_input_energy_wh": 3.0,

            "heating_delivered_energy_wh": 4.0,
            "cooling_delivered_energy_wh": 0.0,
            "hvac_delivered_energy_wh": 4.0,

            "lighting_energy_wh": 5.0,
            "appliance_energy_wh": 7.0,
            "total_energy_wh": 15.0,
        }
    )

    return pd.DataFrame([row])


def make_dwelling_df():
    row = {
        column: default_value_for_column(column)
        for column in output_columns_for_record_type("dwelling", OUTPUT_MODE_DEBUG)
    }

    row.update(
        {
            "building_id": "b1",
            "dwelling_id": "d1",
            "private_zone_count": 1,
            "heating_energy_wh": 2.0,
            "cooling_energy_wh": 0.0,
            "ventilation_fan_energy_wh": 1.0,
            "hvac_input_energy_wh": 3.0,
            "heating_delivered_energy_wh": 4.0,
            "cooling_delivered_energy_wh": 0.0,
            "hvac_delivered_energy_wh": 4.0,
            "lighting_energy_wh": 5.0,
            "appliance_energy_wh": 7.0,
            "total_energy_wh": 15.0,
        }
    )

    return pd.DataFrame([row])


def make_building_df():
    row = {
        column: default_value_for_column(column)
        for column in output_columns_for_record_type("building", OUTPUT_MODE_DEBUG)
    }

    row.update(
        {
            "building_id": "b1",
            "number_of_dwellings": 1,
            "number_of_zones": 1,
            "private_zone_count": 1,
            "shared_zone_count": 0,
            "private_zone_energy_wh": 15.0,
            "shared_zone_energy_wh": 0.0,
            "private_total_energy_wh": 15.0,
            "shared_total_energy_wh": 0.0,
            "zone_total_energy_wh": 15.0,
            "heating_energy_wh": 2.0,
            "cooling_energy_wh": 0.0,
            "ventilation_fan_energy_wh": 1.0,
            "hvac_input_energy_wh": 3.0,
            "heating_delivered_energy_wh": 4.0,
            "cooling_delivered_energy_wh": 0.0,
            "hvac_delivered_energy_wh": 4.0,
            "lighting_energy_wh": 5.0,
            "appliance_energy_wh": 7.0,
            "shared_system_energy_wh": 0.0,
            "total_energy_wh": 15.0,
            "building_energy_result_total_energy_wh": 15.0,
            "building_zone_energy_balance_residual_wh": 0.0,
        }
    )

    return pd.DataFrame([row])


def test_schema_validators_pass_on_complete_debug_rows():
    zone_df = make_zone_df()
    dwelling_df = make_dwelling_df()
    building_df = make_building_df()

    zone_result = validate_zone_timestep_record_schema(
        zone_df,
        mode=OUTPUT_MODE_DEBUG,
    )

    dwelling_result = validate_dwelling_timestep_record_schema(
        dwelling_df,
        mode=OUTPUT_MODE_DEBUG,
    )

    building_result = validate_building_timestep_record_schema(
        building_df,
        mode=OUTPUT_MODE_DEBUG,
    )

    assert_true(zone_result["ok"], "Zone schema validation failed: " + str(zone_result))
    assert_true(dwelling_result["ok"], "Dwelling schema validation failed: " + str(dwelling_result))
    assert_true(building_result["ok"], "Building schema validation failed: " + str(building_result))

    print("PASS: test_schema_validators_pass_on_complete_debug_rows")


def test_energy_consistency_passes():
    result = validate_energy_consistency(
        zone_df=make_zone_df(),
        dwelling_df=make_dwelling_df(),
        building_df=make_building_df(),
    )

    assert_true(
        result["ok"],
        "Energy consistency should pass: " + str(result),
    )

    print("PASS: test_energy_consistency_passes")


def test_validation_catches_missing_required_column():
    zone_df = make_zone_df().drop(columns=["total_energy_wh"])

    result = validate_zone_timestep_record_schema(
        zone_df,
        mode=OUTPUT_MODE_DEBUG,
    )

    assert_true(
        not result["ok"],
        "Validation should fail when total_energy_wh is missing.",
    )

    assert_true(
        "total_energy_wh" in result["missing_columns"],
        "Missing columns should include total_energy_wh.",
    )

    print("PASS: test_validation_catches_missing_required_column")


def test_validation_catches_normalized_range_error():
    zone_df = make_zone_df()
    zone_df.loc[0, "indoor_daylight"] = 1.5

    result = validate_zone_timestep_record_schema(
        zone_df,
        mode=OUTPUT_MODE_DEBUG,
    )

    assert_true(
        not result["ok"],
        "Validation should fail for indoor_daylight > 1.",
    )

    assert_true(
        "indoor_daylight" in result["out_of_range_columns"],
        "Out-of-range columns should include indoor_daylight.",
    )

    print("PASS: test_validation_catches_normalized_range_error")


def test_validation_catches_energy_error():
    zone_df = make_zone_df()
    zone_df.loc[0, "total_energy_wh"] = 999.0

    result = validate_energy_consistency(
        zone_df=zone_df,
        dwelling_df=make_dwelling_df(),
        building_df=make_building_df(),
    )

    assert_true(
        not result["ok"],
        "Energy validation should fail for wrong zone total.",
    )

    print("PASS: test_validation_catches_energy_error")


def test_combined_validation_passes():
    result = validate_building_output_dataframes(
        zone_df=make_zone_df(),
        dwelling_df=make_dwelling_df(),
        building_df=make_building_df(),
        mode=OUTPUT_MODE_DEBUG,
    )

    assert_true(
        result["ok"],
        "Combined validation should pass: " + str(result),
    )

    print("PASS: test_combined_validation_passes")


if __name__ == "__main__":
    test_schema_validators_pass_on_complete_debug_rows()
    test_energy_consistency_passes()
    test_validation_catches_missing_required_column()
    test_validation_catches_normalized_range_error()
    test_validation_catches_energy_error()
    test_combined_validation_passes()

    print("Phase 15.11 output validation helper tests passed.")