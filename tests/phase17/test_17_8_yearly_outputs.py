"""
ABBEY Phase 17.8 test.

Goal:
    Verify that yearly/minimal building outputs still work after the
    engine-backed v0.4 performance replacement.

Run:
    python -m pytest tests/phase17/test_17_8_yearly_outputs.py

Provenance:
    adapted from surviving script `run_test_phase_17_8_yearly_outputs.py` at
    frozen HEAD 7d2729173146536771935ffa92eabaa3c4000c53.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from nexusep.abbey.simulation.runner import AbbeySimulation

from nexusep.abbey.building.outputs import (
    OUTPUT_MODE_MINIMAL,
    output_columns_for_record_type,
    validate_building_output_dataframes,
)

from tests.phase16.test_16_0_validation_harness import (
    assert_true,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_PATH = (
    PROJECT_ROOT
    / "nexusep"
    / "data"
    / "abbey"
    / "config"
    / "abbey_config.jsonc"
)

ENERGY_TOLERANCE_WH = 1e-6


def make_short_yearly_sim():
    sim = AbbeySimulation.initialize(
        config_path=CONFIG_PATH,
        duration_hours=0.25,
        dt_minutes=5.0,
        use_building_performance=True,
        use_household_execution=False,
        random_seed=42,
    )

    sim.run()

    return sim


def assert_path_exists(paths, key):
    assert_true(
        key in paths,
        "Missing expected yearly output key: "
        + str(key)
        + ". Returned keys: "
        + str(sorted(paths.keys())),
    )

    path = Path(paths[key])

    assert_true(
        path.exists(),
        "Expected yearly output path does not exist for key "
        + str(key)
        + ": "
        + str(path),
    )

    return path


def read_non_empty_csv(path):
    df = pd.read_csv(path)

    assert_true(
        not df.empty,
        "Expected yearly CSV should be non-empty: " + str(path),
    )

    return df


def test_short_simulation_produces_source_records_for_yearly_export():
    sim = make_short_yearly_sim()

    assert_true(
        len(sim.building_zone_records) > 0,
        "Short run should produce building_zone_records.",
    )

    assert_true(
        len(sim.building_dwelling_records) > 0,
        "Short run should produce building_dwelling_records.",
    )

    assert_true(
        len(sim.building_records) > 0,
        "Short run should produce building_records.",
    )

    assert_true(
        sim.building_zone_records[0].get("physics_path") == "engine",
        "Normal yearly source records should use physics_path='engine'.",
    )

    assert_true(
        sim.building_records[0].get("performance_path") == "engine",
        "Normal yearly source building records should use performance_path='engine'.",
    )

    print("PASS: test_short_simulation_produces_source_records_for_yearly_export")


def test_raw_records_validate_with_minimal_schema():
    sim = make_short_yearly_sim()

    zone_df = sim.building_zone_records_to_dataframe()
    dwelling_df = sim.building_dwelling_records_to_dataframe()
    building_df = sim.building_records_to_dataframe()

    validation = validate_building_output_dataframes(
        zone_df=zone_df,
        dwelling_df=dwelling_df,
        building_df=building_df,
        mode=OUTPUT_MODE_MINIMAL,
        tolerance_wh=ENERGY_TOLERANCE_WH,
    )

    assert_true(
        validation["ok"],
        "Raw source records should validate with minimal/yearly-safe schema. "
        + "errors="
        + str(validation.get("errors", []))
        + ", missing_columns="
        + str(validation.get("missing_columns", []))
        + ", energy_checks="
        + str(validation.get("energy_checks", {})),
    )

    print("PASS: test_raw_records_validate_with_minimal_schema")


def test_save_building_yearly_outputs_creates_core_csvs():
    sim = make_short_yearly_sim()

    with TemporaryDirectory() as tmp:
        output_folder = Path(tmp) / "building_yearly"

        paths = sim.save_building_yearly_outputs(
            output_folder,
            output_mode=OUTPUT_MODE_MINIMAL,
            include_interzone_summaries=False,
            include_window_detail_summaries=False,
        )

        expected_csv_keys = [
            "hourly_zone_summary_csv",
            "daily_zone_summary_csv",
            "energy_by_zone_csv",
            "control_active_hours_by_zone_csv",
            "daily_dwelling_summary_csv",
            "energy_by_dwelling_csv",
            "daily_building_summary_csv",
            "energy_by_building_csv",
        ]

        for key in expected_csv_keys:
            path = assert_path_exists(paths, key)
            read_non_empty_csv(path)

    print("PASS: test_save_building_yearly_outputs_creates_core_csvs")


def test_energy_by_zone_dwelling_building_outputs_have_expected_columns():
    sim = make_short_yearly_sim()

    with TemporaryDirectory() as tmp:
        output_folder = Path(tmp) / "building_yearly"

        paths = sim.save_building_yearly_outputs(
            output_folder,
            output_mode=OUTPUT_MODE_MINIMAL,
            include_interzone_summaries=False,
            include_window_detail_summaries=False,
        )

        zone_energy = read_non_empty_csv(
            assert_path_exists(paths, "energy_by_zone_csv")
        )

        dwelling_energy = read_non_empty_csv(
            assert_path_exists(paths, "energy_by_dwelling_csv")
        )

        building_energy = read_non_empty_csv(
            assert_path_exists(paths, "energy_by_building_csv")
        )

        for column in [
            "building_id",
            "dwelling_id",
            "zone_id",
            "total_energy_wh",
        ]:
            assert_true(
                column in zone_energy.columns,
                "energy_by_zone missing column: " + str(column),
            )

        for column in [
            "building_id",
            "dwelling_id",
            "total_energy_wh",
        ]:
            assert_true(
                column in dwelling_energy.columns,
                "energy_by_dwelling missing column: " + str(column),
            )

        for column in [
            "building_id",
            "total_energy_wh",
        ]:
            assert_true(
                column in building_energy.columns,
                "energy_by_building missing column: " + str(column),
            )

        assert_true(
            float(zone_energy["total_energy_wh"].sum()) >= 0.0,
            "energy_by_zone total energy should be non-negative.",
        )

        assert_true(
            float(dwelling_energy["total_energy_wh"].sum()) >= 0.0,
            "energy_by_dwelling total energy should be non-negative.",
        )

        assert_true(
            float(building_energy["total_energy_wh"].sum()) >= 0.0,
            "energy_by_building total energy should be non-negative.",
        )

    print("PASS: test_energy_by_zone_dwelling_building_outputs_have_expected_columns")


def test_minimal_yearly_output_does_not_write_heavy_timestep_debug_csvs():
    sim = make_short_yearly_sim()

    with TemporaryDirectory() as tmp:
        output_folder = Path(tmp) / "building_yearly"

        paths = sim.save_building_yearly_outputs(
            output_folder,
            output_mode=OUTPUT_MODE_MINIMAL,
            include_interzone_summaries=False,
            include_window_detail_summaries=False,
            include_interzone_timestep_records=False,
            include_window_detail_timestep_records=False,
        )

        forbidden_keys = [
            "zone_timestep_csv",
            "dwelling_timestep_csv",
            "building_timestep_csv",
            "internal_source_records_csv",
            "control_bridge_csv",
            "action_events_csv",
            "interzone_thermal_timestep_csv",
            "interzone_airflow_timestep_csv",
            "window_detail_timestep_csv",
            "window_airflow_timestep_csv",
        ]

        for key in forbidden_keys:
            assert_true(
                key not in paths,
                "Minimal yearly output should not return heavy/debug key: "
                + str(key),
            )

        csv_folder = output_folder / "csv"

        forbidden_patterns = [
            "*_zone_timestep.csv",
            "*_dwelling_timestep.csv",
            "*_building_timestep.csv",
            "*_internal_source_records_timestep.csv",
            "*_control_bridge_timestep.csv",
            "*_action_events_timestep.csv",
            "*_interzone_thermal_timestep.csv",
            "*_interzone_airflow_timestep.csv",
            "*_window_detail_timestep.csv",
            "*_window_airflow_timestep.csv",
        ]

        for pattern in forbidden_patterns:
            matches = list(csv_folder.glob(pattern))

            assert_true(
                len(matches) == 0,
                "Minimal yearly output should not write heavy/debug files for pattern "
                + str(pattern)
                + ": "
                + str(matches),
            )

    print("PASS: test_minimal_yearly_output_does_not_write_heavy_timestep_debug_csvs")


def test_interzone_and_window_summaries_are_optional_and_safe():
    sim = make_short_yearly_sim()

    with TemporaryDirectory() as tmp:
        output_folder = Path(tmp) / "building_yearly"

        paths = sim.save_building_yearly_outputs(
            output_folder,
            output_mode=OUTPUT_MODE_MINIMAL,
            include_interzone_summaries=True,
            include_window_detail_summaries=True,
            include_interzone_timestep_records=False,
            include_window_detail_timestep_records=False,
        )

        optional_keys = [
            "daily_interzone_airflow_summary_csv",
            "daily_interzone_thermal_summary_csv",
            "daily_window_airflow_summary_csv",
        ]

        for key in optional_keys:
            if key not in paths:
                continue

            path = Path(paths[key])

            assert_true(
                path.exists(),
                "Optional summary key exists but file is missing: " + str(key),
            )

            df = pd.read_csv(path)

            assert_true(
                not df.empty,
                "Optional summary file should be non-empty when returned: "
                + str(key),
            )

    print("PASS: test_interzone_and_window_summaries_are_optional_and_safe")


def test_minimal_schema_keeps_fallback_visibility_but_not_debug_requirement():
    zone_columns = output_columns_for_record_type(
        record_type="zone",
        mode=OUTPUT_MODE_MINIMAL,
    )

    building_columns = output_columns_for_record_type(
        record_type="building",
        mode=OUTPUT_MODE_MINIMAL,
    )

    required_status_columns = [
        "physics_engine_active",
        "physics_path",
        "performance_path",
        "legacy_fallback_used",
        "legacy_fallback_reason",
    ]

    for column in required_status_columns:
        assert_true(
            column in zone_columns,
            "Minimal zone schema should keep fallback/status column: "
            + str(column),
        )

        assert_true(
            column in building_columns,
            "Minimal building schema should keep fallback/status column: "
            + str(column),
        )

    debug_only_zone_columns = [
        "old_indoor_temp_c",
        "thermal_old_air_temperature_c",
        "airflow_total_exchange_m3_h",
        "solar_gain_w",
        "indoor_noise_db",
    ]

    for column in debug_only_zone_columns:
        assert_true(
            column not in zone_columns,
            "Minimal zone schema should not require debug-only column: "
            + str(column),
        )

    print("PASS: test_minimal_schema_keeps_fallback_visibility_but_not_debug_requirement")


def main():
    test_short_simulation_produces_source_records_for_yearly_export()
    test_raw_records_validate_with_minimal_schema()
    test_save_building_yearly_outputs_creates_core_csvs()
    test_energy_by_zone_dwelling_building_outputs_have_expected_columns()
    test_minimal_yearly_output_does_not_write_heavy_timestep_debug_csvs()
    test_interzone_and_window_summaries_are_optional_and_safe()
    test_minimal_schema_keeps_fallback_visibility_but_not_debug_requirement()

    print("Phase 17.8 yearly/minimal output tests passed.")


if __name__ == "__main__":
    main()
