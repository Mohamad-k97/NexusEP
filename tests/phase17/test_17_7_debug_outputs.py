"""Phase 17.7 debug-output contract.

Provenance: reconstructed from ``save_building_debug_outputs``, output-schema
APIs, and v0.4 debug-output assertions. The original June 29 script was not
recovered; its filename later held the Phase 18.26 annual shoebox benchmark.
"""

from pathlib import Path

import pandas as pd

from nexusep.abbey.building.outputs import (
    OUTPUT_MODE_DEBUG,
    OUTPUT_MODE_MINIMAL,
    output_columns_for_record_type,
)
from nexusep.abbey.simulation.runner import AbbeySimulation


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "nexusep" / "data" / "abbey" / "config" / "abbey_config.jsonc"


def make_completed_short_simulation():
    sim = AbbeySimulation.initialize(
        config_path=CONFIG_PATH,
        duration_hours=0.1,
        dt_minutes=1.0,
        use_building_performance=True,
        use_household_execution=False,
        random_seed=42,
    )
    sim.step()
    return sim


def test_debug_schema_keeps_diagnostics_beyond_minimal_schema():
    debug_columns = set(output_columns_for_record_type("zone", OUTPUT_MODE_DEBUG))
    minimal_columns = set(output_columns_for_record_type("zone", OUTPUT_MODE_MINIMAL))

    assert minimal_columns < debug_columns
    assert {
        "old_indoor_temp_c",
        "thermal_old_air_temperature_c",
        "airflow_total_exchange_m3_h",
        "solar_gain_w",
        "indoor_noise_db",
    }.issubset(debug_columns)


def test_debug_export_writes_core_timestep_csvs_only_to_requested_folder(tmp_path):
    sim = make_completed_short_simulation()
    output_folder = tmp_path / "building_debug"
    paths = sim.save_building_debug_outputs(
        output_folder,
        output_mode=OUTPUT_MODE_DEBUG,
        include_diagnostics=False,
        include_long_records=False,
        include_plots=False,
        include_interzone_timestep_records=False,
        include_window_detail_timestep_records=False,
    )

    required = {
        "zone_timestep_csv",
        "dwelling_timestep_csv",
        "building_timestep_csv",
    }
    assert required.issubset(paths)

    for key in required:
        path = Path(paths[key]).resolve()
        assert path.is_file()
        assert path.is_relative_to(output_folder.resolve())
        assert not pd.read_csv(path).empty

    zone_df = pd.read_csv(paths["zone_timestep_csv"])
    assert {
        "physics_engine_active",
        "performance_path",
        "legacy_fallback_used",
        "old_indoor_temp_c",
    }.issubset(zone_df.columns)
