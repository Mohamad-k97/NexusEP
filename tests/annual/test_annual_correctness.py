"""8,760-interval engineering verification for both canonical backends."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import pytest

from nexusep.adapters import ArrayEngineAdapter, ObjectEngineAdapter
from nexusep.parity.harness import build_step_input
from nexusep.scenarios import load_scenario
from nexusep.schema.compiler import CanonicalClock
from nexusep.schema.outputs import CanonicalRunMetadata, aggregate_run_results
from nexusep.schema.timestep import PriorZonePhysicalState

pytestmark = [pytest.mark.annual, pytest.mark.slow]
VALIDATION_CATEGORY = "verification"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_PATH = (
    REPOSITORY_ROOT / "contracts" / "examples" / "multizone_dwelling_v1_minimal.json"
)
N_INTERVALS = 8_760


def _annual_enabled() -> bool:
    return os.environ.get("NEXUSEP_RUN_ANNUAL") == "1"


def _write_annual_scenario(tmp_path: Path) -> Path:
    raw = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    raw["scenario_id"] = "annual_correctness_v1"

    def replace_scenario_id(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "scenario_id":
                    value[key] = "annual_correctness_v1"
                else:
                    replace_scenario_id(child)
        elif isinstance(value, list):
            for child in value:
                replace_scenario_id(child)

    replace_scenario_id(raw)
    raw["simulation_period"]["n_timesteps"] = N_INTERVALS
    clock = CanonicalClock.from_period(raw["simulation_period"])
    for occupant in raw["occupants"]:
        occupant["location_schedule"] = [
            {
                "start_timestep_index": 0,
                "end_timestep_index": N_INTERVALS,
                "zone_id": occupant["home_zone_id"],
                "activity": "awake",
            }
        ]
    weather_template = dict(raw["weather_series"][0])
    raw["weather_series"] = []
    for timestep_index in range(N_INTERVALS):
        weather = dict(weather_template)
        weather["scenario_id"] = raw["scenario_id"]
        weather["timestep_index"] = timestep_index
        weather["timestamp"] = clock.timestamp_for_index(timestep_index).isoformat()
        raw["weather_series"].append(weather)
    raw["output_configuration"]["directory"] = str(tmp_path / "annual-output")
    path = tmp_path / "annual.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def _run_annual(adapter_type, scenario_path: Path):
    bundle = load_scenario(scenario_path)
    adapter = adapter_type(bundle.scenario, bundle.compiled_graph)
    prior = None
    results = []
    for timestep_index in range(N_INTERVALS):
        step_input = build_step_input(
            bundle.scenario, bundle.compiled_graph, timestep_index
        )
        step_input = step_input.model_copy(
            update={
                "control_commands": tuple(
                    command.model_copy(
                        update={"ventilation_volume_flow_m3_s": 0.02}
                    )
                    for command in step_input.control_commands
                )
            }
        )
        if prior is not None:
            step_input = step_input.model_copy(update={"prior_zone_states": prior})
        result = adapter.run_step(step_input, include_debug=True)
        assert result.debug is not None
        prior = tuple(
            PriorZonePhysicalState.model_validate(item)
            for item in result.debug.engine_fields["next_prior_zone_states"]
        )
        results.append(result)
    metadata = CanonicalRunMetadata(
        scenario_id=bundle.scenario.scenario_id,
        run_id=results[0].run_id,
        engine_name=adapter.engine_name,
        engine_version=adapter.engine_version,
        schema_version=bundle.scenario.schema_version,
        graph_sha256=bundle.graph_sha256,
        deterministic_seed=bundle.scenario.deterministic_seed,
        started_at=bundle.scenario.simulation_period.start_datetime,
        timestep_count=N_INTERVALS,
        dt_minutes=bundle.scenario.simulation_period.dt_minutes,
    )
    return aggregate_run_results(metadata, tuple(results))


def _normalized_digest(run) -> str:
    payload = run.model_dump(mode="json", exclude={"warnings", "validation_provenance"})
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@pytest.mark.parametrize(
    "adapter_type", (ObjectEngineAdapter, ArrayEngineAdapter), ids=("object", "array")
)
def test_annual_engineering_invariants(adapter_type, tmp_path: Path) -> None:
    if not _annual_enabled():
        pytest.skip("set NEXUSEP_RUN_ANNUAL=1 for the nightly annual lane")
    run = _run_annual(adapter_type, _write_annual_scenario(tmp_path))
    assert len(run.steps) == N_INTERVALS
    assert [step.timestep_index for step in run.steps] == list(range(N_INTERVALS))
    timestamps = [step.timestamp for step in run.steps]
    assert timestamps == sorted(timestamps)
    expected_zone_ids = {item.zone_id for item in run.steps[0].zones}
    assert all({item.zone_id for item in step.zones} == expected_zone_ids for step in run.steps)
    for step in run.steps:
        assert all(not zone.fallback_used for zone in step.zones)
        assert all(
            math.isfinite(value)
            for zone in step.zones
            for value in (
                zone.air_temperature_c,
                zone.relative_humidity_fraction,
                zone.co2_ppm,
                zone.total_electrical_power_w,
            )
        )
        assert all(0.0 <= zone.relative_humidity_fraction <= 1.0 for zone in step.zones)
        assert all(zone.co2_ppm >= 0.0 for zone in step.zones)
        energy_by_zone = {item.zone_id: item.electrical_energy_wh for item in step.zone_energy}
        for zone in step.zones:
            assert energy_by_zone[zone.zone_id] == pytest.approx(
                zone.total_electrical_power_w * step.dt_minutes / 60.0
            )
    zone_total = sum(item.electrical_energy_wh for item in run.zone_energy)
    assert zone_total >= 0.0
    assert zone_total == pytest.approx(run.dwelling_energy[0].electrical_energy_wh)
    assert zone_total == pytest.approx(run.building_energy[0].electrical_energy_wh)


@pytest.mark.parametrize(
    "adapter_type", (ObjectEngineAdapter, ArrayEngineAdapter), ids=("object", "array")
)
def test_annual_normalized_results_are_deterministic(adapter_type, tmp_path: Path) -> None:
    if os.environ.get("NEXUSEP_RUN_ANNUAL_REPEAT") != "1":
        pytest.skip("set NEXUSEP_RUN_ANNUAL_REPEAT=1 for repeated annual determinism")
    path = _write_annual_scenario(tmp_path)
    assert _normalized_digest(_run_annual(adapter_type, path)) == _normalized_digest(
        _run_annual(adapter_type, path)
    )
