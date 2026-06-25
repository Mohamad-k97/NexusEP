import math
import os
import tempfile
from pathlib import Path

import pandas as pd

from nexusep.abbey.simulation.runner import AbbeySimulation
from nexusep.abbey.building.outputs import save_debug_building_outputs


REQUIRED_ACOUSTIC_ZONE_COLUMNS = [
    "indoor_noise",
    "indoor_noise_db",
    "background_noise_db",
    "outdoor_noise_db",
    "local_noise_source_db",
    "local_noise_source_count",
    "outdoor_noise_contribution_db",
    "interzone_noise_contribution_db",
    "max_neighbor_noise_contribution_db",
    "acoustic_discomfort_input",
]


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def assert_between(value, lower, upper, message):
    value = float(value)

    if not math.isfinite(value):
        raise AssertionError(message + " Got non-finite value " + str(value))

    if value < float(lower) or value > float(upper):
        raise AssertionError(
            message
            + " Got "
            + str(value)
            + ", expected between "
            + str(lower)
            + " and "
            + str(upper)
        )


def assert_column_exists(df, column, label):
    assert_true(
        column in df.columns,
        label + " missing column: " + column,
    )


def find_abbey_config_path():
    candidates = [
        Path("nexusep/abbey/abbey_config.jsonc"),
        Path("abbey_config.jsonc"),
        Path("nexusep/abbey/config/abbey_config.jsonc"),
        Path(__file__).resolve().parent / "nexusep" / "abbey" / "abbey_config.jsonc",
        Path(__file__).resolve().parent.parent /  "data" / "abbey" / "config" / "abbey_config.jsonc",
    ]

    for candidate in candidates:
        print(candidate)
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Could not find abbey_config.jsonc. Run this from the NexusEP project root."
    )


def run_normal_loop():
    sim = AbbeySimulation.initialize(
        config_path=find_abbey_config_path(),
        duration_hours=2.0,
        dt_minutes=15.0,
        use_building_performance=True,
        use_household_execution=True,
        random_seed=42,
    )

    legacy_df = sim.run()

    return {
        "sim": sim,
        "legacy_df": legacy_df,
        "zone_df": sim.building_zone_records_to_dataframe(),
        "building_df": sim.building_records_to_dataframe(),
    }


def test_normal_loop_runs_with_acoustics_active():
    case = run_normal_loop()

    zone_df = case["zone_df"]
    building_df = case["building_df"]

    assert_true(
        not zone_df.empty,
        "Normal loop should produce zone records.",
    )

    assert_true(
        not building_df.empty,
        "Normal loop should produce building records.",
    )

    for column in REQUIRED_ACOUSTIC_ZONE_COLUMNS:
        assert_column_exists(
            zone_df,
            column,
            "zone_df",
        )

    assert_column_exists(
        building_df,
        "physics_engine_has_acoustic_step_result",
        "building_df",
    )

    assert_true(
        building_df["physics_engine_has_acoustic_step_result"].astype(bool).all(),
        "Every building timestep should have acoustic step result.",
    )

    for _, row in zone_df.iterrows():
        assert_between(
            row["indoor_noise"],
            0.0,
            1.0,
            "Zone record indoor_noise should be normalized.",
        )

        assert_between(
            row["acoustic_discomfort_input"],
            0.0,
            1.0,
            "Zone record acoustic_discomfort_input should be normalized.",
        )

        assert_between(
            row["indoor_noise_db"],
            0.0,
            160.0,
            "Zone record indoor_noise_db should be finite and bounded.",
        )

    print("PASS: test_normal_loop_runs_with_acoustics_active")


def test_final_observation_noise_is_normalized():
    case = run_normal_loop()
    sim = case["sim"]

    default_zone_id = sim.observation.default_zone_id
    zone_observation = sim.observation.get_zone(default_zone_id)

    assert_between(
        zone_observation.indoor_noise,
        0.0,
        1.0,
        "Final ZoneObservation.indoor_noise should be normalized.",
    )

    for person in sim.people.values():
        assert_between(
            person.acoustic_discomfort,
            0.0,
            1.0,
            "Person acoustic_discomfort should remain bounded.",
        )

    print("PASS: test_final_observation_noise_is_normalized")


def test_debug_csv_contains_acoustic_columns_after_full_loop():
    case = run_normal_loop()
    sim = case["sim"]

    with tempfile.TemporaryDirectory() as tmp:
        paths = save_debug_building_outputs(
            sim=sim,
            output_folder=tmp,
            prefix="phase_14_12",
        )

        zone_csv = paths["zone_timestep_csv"]

        assert_true(
            os.path.exists(zone_csv),
            "Zone timestep CSV should exist.",
        )

        df = pd.read_csv(zone_csv)

        for column in REQUIRED_ACOUSTIC_ZONE_COLUMNS:
            assert_column_exists(
                df,
                column,
                "zone_timestep_csv",
            )

    print("PASS: test_debug_csv_contains_acoustic_columns_after_full_loop")


if __name__ == "__main__":
    test_normal_loop_runs_with_acoustics_active()
    test_final_observation_noise_is_normalized()
    test_debug_csv_contains_acoustic_columns_after_full_loop()

    print("Phase 14.12 full acoustic loop tests passed.")