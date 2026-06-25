import math
import os
import tempfile
from pathlib import Path

import pandas as pd

from nexusep.abbey.simulation.runner import AbbeySimulation
from nexusep.abbey.building.outputs import save_debug_building_outputs


REQUIRED_ZONE_COLUMNS = [
    "step",
    "day",
    "hour",
    "zone_id",
    "indoor_temp_c",
    "co2_ppm",
    "indoor_daylight",
    "number_of_people",
    "physics_engine_active",

    # Phase 13 diagnostics from 13.10
    "window_count",
    "solar_gain_w",
    "daylight_illuminance_lux",
    "indoor_illuminance_lux",
    "artificial_lighting_illuminance_lux",
    "visual_comfort_status",
    "lighting_result_power_w",
    "lighting_result_energy_wh",
]


REQUIRED_BUILDING_COLUMNS = [
    "step",
    "day",
    "hour",
    "physics_engine_active",
    "physics_engine_error",
    "physics_engine_has_thermal_step_result",
    "physics_engine_has_airflow_network",
    "physics_engine_has_co2_step_result",
    "physics_engine_has_moisture_step_result",
]


REQUIRED_OUTPUT_KEYS = [
    "zone_timestep_csv",
    "dwelling_timestep_csv",
    "building_timestep_csv",
]


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def assert_equal(a, b, message):
    if a != b:
        raise AssertionError(message + " Got " + str(a) + " != " + str(b))


def assert_greater(a, b, message):
    if not float(a) > float(b):
        raise AssertionError(message + " Got " + str(a) + " <= " + str(b))


def assert_greater_or_equal(a, b, message):
    if not float(a) >= float(b):
        raise AssertionError(message + " Got " + str(a) + " < " + str(b))


def assert_finite(value, message):
    value = float(value)

    if not math.isfinite(value):
        raise AssertionError(message + " Got " + str(value))


def assert_column_exists(df, column, label):
    assert_true(
        column in df.columns,
        label + " missing column: " + column,
    )


def assert_all_finite(df, columns, label):
    for column in columns:
        if column not in df.columns:
            continue

        values = pd.to_numeric(df[column], errors="coerce")

        assert_true(
            values.notna().all(),
            label + " column has NaN after numeric conversion: " + column,
        )

        assert_true(
            values.map(math.isfinite).all(),
            label + " column has non-finite values: " + column,
        )


def find_abbey_config_path():
    candidates = [
        Path("nexusep/abbey/abbey_config.jsonc"),
        Path("abbey_config.jsonc"),
        Path("nexusep/abbey/config/abbey_config.jsonc"),
        Path(__file__).resolve().parent / "data" / "abbey" / "config" /  "abbey_config.jsonc",
        Path(__file__).resolve().parent.parent /"data" / "abbey" / "config" /  "abbey_config.jsonc",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Could not find abbey_config.jsonc. "
        "Run this from the NexusEP project root or update find_abbey_config_path()."
    )


def make_short_normal_simulation():
    config_path = find_abbey_config_path()

    sim = AbbeySimulation.initialize(
        config_path=config_path,
        duration_hours=2.0,
        dt_minutes=15.0,
        use_building_performance=True,
        use_household_execution=True,
        random_seed=42,
    )

    return sim


def run_short_normal_simulation():
    sim = make_short_normal_simulation()

    legacy_df = sim.run()

    return {
        "sim": sim,
        "legacy_df": legacy_df,
        "zone_df": sim.building_zone_records_to_dataframe(),
        "dwelling_df": sim.building_dwelling_records_to_dataframe(),
        "building_df": sim.building_records_to_dataframe(),
        "internal_source_df": sim.building_internal_source_records_to_dataframe(),
        "internal_source_zone_df": sim.building_internal_source_zone_records_to_dataframe(),
        "internal_source_building_df": sim.building_internal_source_building_records_to_dataframe(),
        "interzone_thermal_df": (
            sim.building_interzone_thermal_records_to_dataframe()
            if hasattr(sim, "building_interzone_thermal_records_to_dataframe")
            else pd.DataFrame()
        ),
    }


def test_normal_abbey_loop_runs_and_collects_records():
    case = run_short_normal_simulation()

    sim = case["sim"]
    legacy_df = case["legacy_df"]
    zone_df = case["zone_df"]
    dwelling_df = case["dwelling_df"]
    building_df = case["building_df"]

    assert_true(
        legacy_df is not None,
        "Normal ABBEY loop should return a logger dataframe.",
    )

    assert_true(
        not zone_df.empty,
        "Normal ABBEY loop should collect building zone records.",
    )

    assert_true(
        not dwelling_df.empty,
        "Normal ABBEY loop should collect building dwelling records.",
    )

    assert_true(
        not building_df.empty,
        "Normal ABBEY loop should collect building records.",
    )

    expected_zone_rows = (
        int(sim.n_steps)
        * len(sim.building_model.all_zone_ids())
    )

    assert_equal(
        len(zone_df),
        expected_zone_rows,
        "Zone record count should equal n_steps * number_of_zones.",
    )

    assert_equal(
        len(building_df),
        int(sim.n_steps),
        "Building record count should equal n_steps.",
    )

    print("PASS: test_normal_abbey_loop_runs_and_collects_records")


def test_physics_engine_path_is_active_without_legacy_fallback():
    case = run_short_normal_simulation()

    zone_df = case["zone_df"]
    building_df = case["building_df"]

    assert_column_exists(
        zone_df,
        "physics_engine_active",
        "zone_df",
    )

    assert_column_exists(
        building_df,
        "physics_engine_active",
        "building_df",
    )

    assert_true(
        zone_df["physics_engine_active"].astype(bool).all(),
        "All zone rows should use the physics engine.",
    )

    assert_true(
        building_df["physics_engine_active"].astype(bool).all(),
        "All building rows should use the physics engine.",
    )

    if "legacy_fallback_used" in zone_df.columns:
        assert_true(
            not zone_df["legacy_fallback_used"].astype(bool).any(),
            "No zone row should use legacy fallback.",
        )

    if "legacy_fallback_used" in building_df.columns:
        assert_true(
            not building_df["legacy_fallback_used"].astype(bool).any(),
            "No building row should use legacy fallback.",
        )

    error_values = (
        building_df["physics_engine_error"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    assert_true(
        (error_values == "").all() or (error_values == "None").all(),
        "Physics engine errors should be empty/None.",
    )

    print("PASS: test_physics_engine_path_is_active_without_legacy_fallback")


def test_phase_13_columns_survive_normal_loop():
    case = run_short_normal_simulation()

    zone_df = case["zone_df"]

    for column in REQUIRED_ZONE_COLUMNS:
        assert_column_exists(
            zone_df,
            column,
            "zone_df",
        )

    assert_all_finite(
        zone_df,
        [
            "indoor_temp_c",
            "co2_ppm",
            "indoor_daylight",
            "window_count",
            "solar_gain_w",
            "daylight_illuminance_lux",
            "indoor_illuminance_lux",
            "artificial_lighting_illuminance_lux",
            "lighting_result_power_w",
            "lighting_result_energy_wh",
        ],
        "zone_df",
    )

    assert_true(
        ((zone_df["indoor_daylight"] >= 0.0) & (zone_df["indoor_daylight"] <= 1.0)).all(),
        "indoor_daylight should stay normalized in [0, 1].",
    )

    assert_true(
        (zone_df["window_count"] >= 0).all(),
        "window_count should be non-negative.",
    )

    assert_true(
        (zone_df["solar_gain_w"] >= 0.0).all(),
        "solar_gain_w should be non-negative.",
    )

    assert_true(
        (zone_df["daylight_illuminance_lux"] >= 0.0).all(),
        "daylight_illuminance_lux should be non-negative.",
    )

    assert_true(
        (zone_df["lighting_result_power_w"] >= 0.0).all(),
        "lighting_result_power_w should be non-negative.",
    )

    print("PASS: test_phase_13_columns_survive_normal_loop")


def test_building_records_keep_engine_status_columns():
    case = run_short_normal_simulation()

    building_df = case["building_df"]

    for column in REQUIRED_BUILDING_COLUMNS:
        assert_column_exists(
            building_df,
            column,
            "building_df",
        )

    assert_true(
        building_df["physics_engine_has_thermal_step_result"].astype(bool).all(),
        "Building records should report thermal step result.",
    )

    assert_true(
        building_df["physics_engine_has_airflow_network"].astype(bool).all(),
        "Building records should report airflow network.",
    )

    assert_true(
        building_df["physics_engine_has_co2_step_result"].astype(bool).all(),
        "Building records should report CO2 step result.",
    )

    assert_true(
        building_df["physics_engine_has_moisture_step_result"].astype(bool).all(),
        "Building records should report moisture step result.",
    )

    print("PASS: test_building_records_keep_engine_status_columns")


def test_observation_updates_from_building_zone_state():
    case = run_short_normal_simulation()

    sim = case["sim"]
    zone_df = case["zone_df"]

    default_zone_id = sim.observation.default_zone_id

    assert_true(
        default_zone_id in sim.building_model.all_zone_ids(),
        "Final observation default zone should be a building zone.",
    )

    final_zone_state = sim.building_model.get_zone_state(default_zone_id)
    final_observation_zone = sim.observation.get_zone(default_zone_id)

    assert_finite(
        final_zone_state.indoor_temp_c,
        "Final ZoneState indoor temperature should be finite.",
    )

    assert_finite(
        final_observation_zone.indoor_temp,
        "Final ZoneObservation indoor temperature should be finite.",
    )

    assert_finite(
        final_zone_state.indoor_daylight,
        "Final ZoneState indoor daylight should be finite.",
    )

    assert_finite(
        final_observation_zone.indoor_daylight,
        "Final ZoneObservation indoor daylight should be finite.",
    )

    assert_greater_or_equal(
        final_zone_state.co2_ppm,
        0.0,
        "Final ZoneState CO2 should be non-negative.",
    )

    assert_greater_or_equal(
        final_observation_zone.co2_ppm,
        0.0,
        "Final ZoneObservation CO2 should be non-negative.",
    )

    assert_true(
        default_zone_id in set(zone_df["zone_id"].astype(str)),
        "Default observation zone should appear in zone records.",
    )

    print("PASS: test_observation_updates_from_building_zone_state")


def test_internal_source_outputs_are_available():
    case = run_short_normal_simulation()

    internal_source_zone_df = case["internal_source_zone_df"]
    internal_source_building_df = case["internal_source_building_df"]

    assert_true(
        not internal_source_zone_df.empty,
        "Internal-source zone records should be collected.",
    )

    assert_true(
        not internal_source_building_df.empty,
        "Internal-source building records should be collected.",
    )

    for column in [
        "average_sensible_heat_w",
        "average_electricity_power_w",
        "average_co2_generation_m3_h",
    ]:
        assert_column_exists(
            internal_source_zone_df,
            column,
            "internal_source_zone_df",
        )

    for column in [
        "total_electricity_wh",
        "total_average_sensible_heat_w",
    ]:
        assert_column_exists(
            internal_source_building_df,
            column,
            "internal_source_building_df",
        )

    zone_moisture_candidates = [
        "average_moisture_generation_kg_h",
        "moisture_generation_kg_h",
        "moisture_generation_kg",
    ]

    building_moisture_candidates = [
        "total_moisture_generation_kg_h",
        "average_total_moisture_generation_kg_h",
        "total_moisture_generation_kg",
    ]

    assert_true(
        any(column in internal_source_zone_df.columns for column in zone_moisture_candidates),
        "Internal-source zone records should expose at least one moisture diagnostic column. Columns: "
        + str(list(internal_source_zone_df.columns)),
    )

    assert_true(
        any(column in internal_source_building_df.columns for column in building_moisture_candidates),
        "Internal-source building records should expose at least one moisture diagnostic column. Columns: "
        + str(list(internal_source_building_df.columns)),
    )

    print("PASS: test_internal_source_outputs_are_available")


def test_debug_outputs_are_written_and_readable():
    case = run_short_normal_simulation()

    sim = case["sim"]

    with tempfile.TemporaryDirectory() as tmp:
        paths = save_debug_building_outputs(
            sim=sim,
            output_folder=tmp,
            prefix="phase_13_12",
        )

        for key in REQUIRED_OUTPUT_KEYS:
            assert_true(
                key in paths,
                "Missing output path key: " + key,
            )

            assert_true(
                os.path.exists(paths[key]),
                "Missing output file for key " + key + ": " + str(paths[key]),
            )

            assert_greater(
                os.path.getsize(paths[key]),
                0,
                "Output file should not be empty: " + str(paths[key]),
            )

        zone_csv_df = pd.read_csv(paths["zone_timestep_csv"])
        building_csv_df = pd.read_csv(paths["building_timestep_csv"])

        assert_true(
            not zone_csv_df.empty,
            "Zone timestep CSV should be readable and non-empty.",
        )

        assert_true(
            not building_csv_df.empty,
            "Building timestep CSV should be readable and non-empty.",
        )

        for column in REQUIRED_ZONE_COLUMNS:
            assert_column_exists(
                zone_csv_df,
                column,
                "zone_timestep_csv",
            )

        for column in REQUIRED_BUILDING_COLUMNS:
            assert_column_exists(
                building_csv_df,
                column,
                "building_timestep_csv",
            )

        optional_keys = [
            "internal_source_zone_csv",
            "internal_source_building_csv",
            "energy_by_zone_plot",
            "energy_by_building_plot",
        ]

        for key in optional_keys:
            if key not in paths:
                continue

            assert_true(
                os.path.exists(paths[key]),
                "Optional output key exists but file is missing: " + key,
            )

    print("PASS: test_debug_outputs_are_written_and_readable")


def test_no_obvious_energy_double_counting_between_zone_and_building_records():
    case = run_short_normal_simulation()

    zone_df = case["zone_df"]
    building_df = case["building_df"]

    if "total_energy_wh" not in zone_df.columns:
        print("SKIP: total_energy_wh not in zone_df")
        return

    if "total_energy_wh" not in building_df.columns:
        print("SKIP: total_energy_wh not in building_df")
        return

    zone_sum_by_step = (
        zone_df
        .groupby("step")["total_energy_wh"]
        .sum()
        .reset_index()
        .rename(columns={"total_energy_wh": "zone_sum_total_energy_wh"})
    )

    merged = building_df[["step", "total_energy_wh"]].merge(
        zone_sum_by_step,
        on="step",
        how="inner",
    )

    assert_true(
        not merged.empty,
        "Energy consistency merge should not be empty.",
    )

    for _, row in merged.iterrows():
        assert_true(
            abs(
                float(row["total_energy_wh"])
                - float(row["zone_sum_total_energy_wh"])
            ) < 1e-6,
            "Building total_energy_wh should equal sum of zone total_energy_wh for each step.",
        )

    print("PASS: test_no_obvious_energy_double_counting_between_zone_and_building_records")


if __name__ == "__main__":
    test_normal_abbey_loop_runs_and_collects_records()
    test_physics_engine_path_is_active_without_legacy_fallback()
    test_phase_13_columns_survive_normal_loop()
    test_building_records_keep_engine_status_columns()
    test_observation_updates_from_building_zone_state()
    test_internal_source_outputs_are_available()
    test_debug_outputs_are_written_and_readable()
    test_no_obvious_energy_double_counting_between_zone_and_building_records()

    print("Phase 13.12 full Phase 13 integration tests passed.")