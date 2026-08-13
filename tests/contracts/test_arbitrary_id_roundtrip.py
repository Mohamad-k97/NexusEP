"""Verification that canonical execution never infers relationships from IDs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from nexusep.abbey.agents.states import (
    DwellingObservation,
    PersonState,
    ZoneObservation,
)
from nexusep.abbey.simulation.runner import AbbeySimulation
from nexusep.adapters import ArrayEngineAdapter, ObjectEngineAdapter
from nexusep.parity.harness import build_step_input
from nexusep.scenarios import load_scenario

pytestmark = pytest.mark.contract
VALIDATION_CATEGORY = "verification"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_PATH = (
    REPOSITORY_ROOT / "contracts" / "examples" / "multizone_dwelling_v1_minimal.json"
)


def _rename(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _rename(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_rename(item, replacements) for item in value]
    if isinstance(value, str):
        return replacements.get(value, value)
    return value


def _write_unusual_scenario(tmp_path: Path) -> Path:
    replacements = {
        "minimal_two_zone_dwelling": "scenario-with-unusual-identifiers",
        "building_001": "building_alpha",
        "dwelling_001": "home_north",
        "occupant_001": "resident_maria",
        "occupant_002": "resident_zoe",
        "living_zone": "zone-kitchen-west",
        "bedroom_zone": "zone-sleep-east",
    }
    raw = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    scenario_path = tmp_path / "unusual_ids.json"
    scenario_path.write_text(json.dumps(_rename(raw, replacements)), encoding="utf-8")
    return scenario_path


@pytest.mark.parametrize(
    "adapter_type",
    (ObjectEngineAdapter, ArrayEngineAdapter),
    ids=("object", "array"),
)
def test_unusual_ids_survive_loader_adapter_logging_and_decode(
    adapter_type: type[ObjectEngineAdapter | ArrayEngineAdapter],
    tmp_path: Path,
) -> None:
    replacements = {
        "minimal_two_zone_dwelling": "scenario-with-unusual-identifiers",
        "building_001": "building_alpha",
        "dwelling_001": "home_north",
        "occupant_001": "resident_maria",
        "occupant_002": "resident_zoe",
        "living_zone": "zone-kitchen-west",
        "bedroom_zone": "zone-sleep-east",
    }
    bundle = load_scenario(_write_unusual_scenario(tmp_path))
    adapter = adapter_type(bundle.scenario, bundle.compiled_graph)
    step_input = build_step_input(bundle.scenario, bundle.compiled_graph, 0)
    result = adapter.run_step(step_input, include_debug=True)

    assert result.debug is not None
    assert {row.zone_id for row in result.zones} == {
        "zone-kitchen-west",
        "zone-sleep-east",
    }
    assert {row.building_id for row in result.zones} == {"building_alpha"}
    assert {row.dwelling_id for row in result.zones} == {"home_north"}
    assert {state.occupant_id for state in step_input.occupant_states} == {
        "resident_maria",
        "resident_zoe",
    }
    serialized = json.dumps(result.model_dump(mode="json"), sort_keys=True)
    for original in replacements:
        assert original not in serialized


def test_object_runner_uses_explicit_relationships_with_unusual_ids(
    tmp_path: Path,
) -> None:
    bundle = load_scenario(_write_unusual_scenario(tmp_path))
    adapter = ObjectEngineAdapter(bundle.scenario, bundle.compiled_graph)
    zones = {
        zone_id: ZoneObservation(zone_id=zone_id, zone_name=zone_id)
        for zone_id in adapter.building_model.all_zone_ids()
    }
    people = {
        occupant.occupant_id: PersonState(
            occupant_id=occupant.occupant_id,
            household_id="home_north",
        )
        for occupant in bundle.scenario.occupants
    }
    simulation = AbbeySimulation.initialize(
        config_path=REPOSITORY_ROOT
        / "nexusep"
        / "data"
        / "abbey"
        / "config"
        / "abbey_config.jsonc",
        duration_hours=1.0,
        dt_minutes=60.0,
        people=people,
        observation=DwellingObservation(
            default_zone_id="zone-kitchen-west", zone_observations=zones
        ),
        building_model=adapter.building_model,
        building_physics_graph=adapter.physics_graph,
        use_household_execution=True,
    )
    assert {item.building_id for item in simulation.locations.values()} == {
        "building_alpha"
    }
    assert {item.dwelling_id for item in simulation.locations.values()} == {
        "home_north"
    }
    simulation.step()
    assert {row["building_id"] for row in simulation.building_zone_records} == {
        "building_alpha"
    }
    assert {row["dwelling_id"] for row in simulation.building_zone_records} == {
        "home_north"
    }
