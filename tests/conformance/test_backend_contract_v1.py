"""Shared Phase 2.15 conformance gates for both canonical adapters.

These checks are structural and semantic.  They deliberately do not compare
the numerical physics results produced by one backend with the other.

Provenance: newly added contract-conformance coverage for frozen contract v1.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from nexusep.adapters import ArrayEngineAdapter, ObjectEngineAdapter
from nexusep.parity.harness import build_step_input
from nexusep.scenarios import ScenarioValidationError, load_scenario
from nexusep.schema.compiler import validate_compiled_graph
from nexusep.schema.outputs import REQUIRED_ZONE_OUTPUT_FIELDS
from nexusep.schema.timestep import CanonicalStepContractError

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_PATH = (
    REPOSITORY_ROOT / "contracts" / "examples" / "multizone_dwelling_v1_minimal.json"
)
ADAPTER_TYPES = (ObjectEngineAdapter, ArrayEngineAdapter)


@pytest.fixture(params=ADAPTER_TYPES, ids=("object", "array"))
def adapter_case(request):
    bundle = load_scenario(EXAMPLE_PATH)
    adapter_type = request.param
    return bundle, adapter_type(bundle.scenario, bundle.compiled_graph)


def _trace(result) -> dict[str, Any]:
    assert result.debug is not None
    return result.debug.engine_fields["step_trace"]


def test_schema_validation_precedes_adapter_initialization(
    adapter_case, tmp_path: Path
) -> None:
    bundle, adapter = adapter_case
    assert adapter.scenario is bundle.scenario
    malformed = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    del malformed["building"]["dwelling"]["zones"][0]["zone_id"]
    path = tmp_path / "missing_zone_id.json"
    path.write_text(json.dumps(malformed), encoding="utf-8")

    with pytest.raises(ScenarioValidationError) as captured:
        load_scenario(path)
    assert any(
        issue.path == "/building/dwelling/zones/0/zone_id"
        for issue in captured.value.issues
    )


def test_required_geometry_is_rejected_and_optional_geometry_is_not_required(
    adapter_case, tmp_path: Path
) -> None:
    bundle, adapter = adapter_case
    raw = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    assert raw["geometry_configuration"]["optional_geometry_affects_physics"] is False
    assert all("vertices" not in zone for zone in raw["building"]["dwelling"]["zones"])
    assert adapter.conformance_snapshot()["graph_sha256"] == bundle.graph_sha256

    del raw["building"]["dwelling"]["zones"][0]["volume_m3"]
    path = tmp_path / "missing_required_geometry.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ScenarioValidationError) as captured:
        load_scenario(path)
    assert any(issue.path.endswith("/volume_m3") for issue in captured.value.issues)


def test_original_ids_round_trip_through_backend_decode(adapter_case) -> None:
    bundle, adapter = adapter_case
    expected = bundle.compiled_graph["id_registry"]["entity_types"]
    snapshot = adapter.conformance_snapshot()
    assert snapshot["decoded_ids"] == {
        entity_type: expected[entity_type]["external_ids"]
        for entity_type in ("building", "dwelling", "zone", "occupant")
    }
    result = adapter.run_step(
        build_step_input(bundle.scenario, bundle.compiled_graph, 0),
        include_debug=True,
    )
    assert [item.zone_id for item in result.zones] == expected["zone"]["external_ids"]
    assert all(isinstance(item.zone_id, str) for item in result.zones)


def test_timestamp_alignment_is_enforced_at_adapter_boundary(adapter_case) -> None:
    bundle, adapter = adapter_case
    step = build_step_input(bundle.scenario, bundle.compiled_graph, 1)
    misaligned = step.model_copy(update={"timestamp": bundle.scenario.weather_series[0].timestamp})
    with pytest.raises(CanonicalStepContractError, match="canonical interval start"):
        adapter.run_step(misaligned)


def test_weather_is_mapped_to_backend_native_units(adapter_case) -> None:
    bundle, adapter = adapter_case
    weather = bundle.scenario.weather_series[1]
    result = adapter.run_step(
        build_step_input(bundle.scenario, bundle.compiled_graph, 1),
        include_debug=True,
    )
    trace = _trace(result)
    assert trace["time_index"] == 1
    assert trace["timestamp"] == weather.timestamp.isoformat()
    if adapter.engine_name == "object":
        assert trace["weather"]["outdoor_temperature_c"] == weather.outdoor_temperature_c
        assert trace["weather"]["relative_humidity_percent"] == (
            weather.relative_humidity_fraction * 100.0
        )
        assert trace["weather"]["atmospheric_pressure_pa"] == weather.atmospheric_pressure_pa
    else:
        assert trace["weather"]["outdoor_temperature_C"] == weather.outdoor_temperature_c
        assert trace["weather"]["outdoor_relative_humidity"] == weather.relative_humidity_fraction
        assert trace["weather"]["atmospheric_pressure_pa"] == (
            weather.atmospheric_pressure_pa
        )
        assert not any(
            item.code == "array_engine_unsupported_weather_fields"
            for item in result.warnings
        )


def test_graph_construction_and_digest_are_preserved(adapter_case) -> None:
    bundle, adapter = adapter_case
    graph = bundle.compiled_graph
    assert validate_compiled_graph(graph) is True
    snapshot = adapter.conformance_snapshot()
    assert snapshot["graph_sha256"] == graph["graph_sha256"]
    assert len(graph["nodes"]) == 3
    assert graph["nodes"][0]["node_id"] == "__exterior__"
    assert all(
        connection["source_node_id"] in {item["node_id"] for item in graph["nodes"]}
        and connection["target_node_id"]
        in {item["node_id"] for item in graph["nodes"]}
        for connection in graph["connections"]
    )


def test_missing_and_dangling_references_are_rejected(adapter_case) -> None:
    bundle, adapter = adapter_case
    step = build_step_input(bundle.scenario, bundle.compiled_graph, 0)
    invented = step.occupant_states[0].model_copy(update={"zone_id": "invented_zone"})
    invalid = step.model_copy(
        update={"occupant_states": (invented,) + step.occupant_states[1:]}
    )
    with pytest.raises(CanonicalStepContractError, match="unknown zone"):
        adapter.run_step(invalid)


def test_control_unit_conversions_are_explicit(adapter_case) -> None:
    bundle, adapter = adapter_case
    step = build_step_input(bundle.scenario, bundle.compiled_graph, 0)
    result = adapter.run_step(step, include_debug=True)
    trace = _trace(result)
    requested = {item.zone_id: item for item in step.control_commands}
    for zone_id, command in requested.items():
        native = trace["controls"][zone_id]
        if adapter.engine_name == "object":
            assert native["ventilation_flow_m3_h"] == pytest.approx(
                command.ventilation_volume_flow_m3_s * 3600.0
            )
            assert native["heating_power_fraction"] == command.heating_power_fraction
        else:
            zone = next(
                item
                for item in bundle.scenario.building.dwelling.zones
                if item.zone_id == zone_id
            )
            heating = next(item for item in zone.systems if item.system_type == "heating")
            assert native["mechanical_ventilation_flow_m3_s"] == pytest.approx(
                command.ventilation_volume_flow_m3_s
            )
            assert native["max_heating_power_W"] == pytest.approx(
                heating.max_heating_power_w
            )
            assert native["command_heating_power_fraction"] == pytest.approx(
                command.heating_power_fraction
            )
            availability = next(
                item
                for item in step.system_availability
                if item.system_id == heating.system_id
            )
            assert native["heating_power_W"] == pytest.approx(
                heating.max_heating_power_w
                * availability.capacity_fraction
                * command.heating_power_fraction
                if command.heating_on
                else 0.0
            )


def test_required_output_schema_and_energy_hierarchy(adapter_case) -> None:
    bundle, adapter = adapter_case
    result = adapter.run_step(
        build_step_input(bundle.scenario, bundle.compiled_graph, 0)
    )
    assert all(
        tuple(type(item).model_fields) == REQUIRED_ZONE_OUTPUT_FIELDS
        for item in result.zones
    )
    zone_total = sum(item.electrical_energy_wh for item in result.zone_energy)
    assert zone_total == pytest.approx(result.dwelling_energy[0].electrical_energy_wh)
    assert zone_total == pytest.approx(result.building_energy[0].electrical_energy_wh)
    assert all(item.fallback_used is False for item in result.zones)


def test_fresh_repeat_runs_are_deterministic(adapter_case) -> None:
    bundle, adapter = adapter_case
    step = build_step_input(bundle.scenario, bundle.compiled_graph, 0)
    first = adapter.run_step(step, include_debug=True)
    repeated_adapter = type(adapter)(bundle.scenario, bundle.compiled_graph)
    second = repeated_adapter.run_step(step, include_debug=True)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
