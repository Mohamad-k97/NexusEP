"""Contract tests for schema version 1 and the canonical scenario loader."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from nexusep.scenarios import ScenarioValidationError, load_scenario
from nexusep.schema.scenario import ScenarioV1

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_PATH = (
    REPOSITORY_ROOT / "contracts" / "examples" / "multizone_dwelling_v1_minimal.json"
)
EXPECTED_GRAPH_HASH = "a3021d4de71b7d32fa3a518520c2db11ee12a927d081c98b0d76d01adfb0f00a"


def _example() -> dict[str, Any]:
    with EXAMPLE_PATH.open(encoding="utf-8") as stream:
        return json.load(stream)


def _write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    return path


def _write_jsonc(path: Path, value: Any) -> Path:
    encoded = json.dumps(value, indent=2)
    body, closing = (
        encoded.rsplit("}", 1) if isinstance(value, dict) else encoded.rsplit("]", 1)
    )
    closer = "}" if isinstance(value, dict) else "]"
    text = f"// canonical JSONC test\n{body},\n{closer}{closing}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _issue_paths(error: ScenarioValidationError) -> set[str]:
    return {issue.path for issue in error.issues}


def test_loading_twice_is_equivalent_frozen_and_graph_controlled() -> None:
    first = load_scenario(EXAMPLE_PATH)
    second = load_scenario(EXAMPLE_PATH)

    assert first == second
    assert first.scenario == second.scenario
    assert first.compiled_graph_json == second.compiled_graph_json
    assert first.graph_sha256 == EXPECTED_GRAPH_HASH
    assert first.audit_log == second.audit_log
    assert first.scenario.output_configuration.directory.is_absolute()

    with pytest.raises(ValidationError, match="Instance is frozen"):
        first.scenario.metadata.name = "mutated"  # type: ignore[misc]

    graph_copy = first.compiled_graph
    graph_copy["nodes"][0]["node_id"] = "mutated"
    assert first.compiled_graph["nodes"][0]["node_id"] == "__exterior__"


def test_loader_audit_records_optional_nulls_and_relative_output_path() -> None:
    bundle = load_scenario(EXAMPLE_PATH)
    targets = {record.target_path for record in bundle.audit_log}

    assert "/output_configuration/directory" in targets
    assert {
        f"/weather_series/{index}/outdoor_noise_db" for index in range(4)
    } <= targets
    assert all(
        state.outdoor_noise_db is None for state in bundle.scenario.weather_series
    )


def test_jsonc_comments_and_trailing_commas_are_supported(tmp_path: Path) -> None:
    scenario_path = _write_jsonc(tmp_path / "scenario.jsonc", _example())

    bundle = load_scenario(scenario_path)

    assert bundle.scenario.scenario_id == "minimal_two_zone_dwelling"
    assert bundle.graph_sha256 == EXPECTED_GRAPH_HASH


def test_external_weather_path_is_relative_to_scenario_file(tmp_path: Path) -> None:
    source = _example()
    weather = source["weather_series"]
    source["weather_series"] = []
    source["weather_source"] = {
        "source_type": "external_json",
        "path": "weather/hourly.jsonc",
        "interpolation": "none",
        "allowable_derived_fields": ["timestamp"],
        "synthetic_profile": None,
    }
    _write_jsonc(tmp_path / "weather" / "hourly.jsonc", weather)
    scenario_path = _write_json(tmp_path / "scenario.json", source)

    bundle = load_scenario(scenario_path)

    assert (
        bundle.scenario.weather_source.path
        == (tmp_path / "weather" / "hourly.jsonc").resolve()
    )
    assert len(bundle.scenario.weather_series) == 4
    assert any(
        record.kind == "path_resolution"
        and record.target_path == "/weather_source/path"
        for record in bundle.audit_log
    )


def test_timestamp_is_the_only_normal_weather_derivation(tmp_path: Path) -> None:
    source = _example()
    del source["weather_series"][2]["timestamp"]
    scenario_path = _write_json(tmp_path / "scenario.json", source)

    bundle = load_scenario(scenario_path)

    assert bundle.scenario.weather_series[2].timestamp.isoformat() == (
        "2026-01-15T02:00:00+01:00"
    )
    assert any(
        record.kind == "derived" and record.target_path == "/weather_series/2/timestamp"
        for record in bundle.audit_log
    )


def test_missing_required_weather_fails_at_field_path(tmp_path: Path) -> None:
    source = _example()
    del source["weather_series"][0]["outdoor_temperature_c"]
    scenario_path = _write_json(tmp_path / "scenario.json", source)

    with pytest.raises(ScenarioValidationError) as captured:
        load_scenario(scenario_path)

    assert "/weather_series/0/outdoor_temperature_c" in _issue_paths(captured.value)


def test_null_required_weather_and_nonfinite_values_are_rejected(
    tmp_path: Path,
) -> None:
    null_source = _example()
    null_source["weather_series"][0]["atmospheric_pressure_pa"] = None
    null_path = _write_json(tmp_path / "null.json", null_source)
    with pytest.raises(ScenarioValidationError) as captured:
        load_scenario(null_path)
    assert "/weather_series/0/atmospheric_pressure_pa" in _issue_paths(captured.value)

    infinite_source = _example()
    infinite_source["weather_series"][0]["wind_speed_m_s"] = float("inf")
    infinite_path = _write_json(tmp_path / "infinite.json", infinite_source)
    with pytest.raises(ScenarioValidationError) as captured:
        load_scenario(infinite_path)
    assert "/weather_series/0/wind_speed_m_s" in _issue_paths(captured.value)


def test_weather_gaps_and_interpolation_are_rejected(tmp_path: Path) -> None:
    gap_source = _example()
    gap_source["weather_series"].pop(1)
    gap_path = _write_json(tmp_path / "gap.json", gap_source)
    with pytest.raises(ScenarioValidationError) as captured:
        load_scenario(gap_path)
    assert "/weather_series" in _issue_paths(captured.value)

    interpolated = _example()
    interpolated["weather_source"]["interpolation"] = "linear"
    interpolation_path = _write_json(tmp_path / "interpolation.json", interpolated)
    with pytest.raises(ScenarioValidationError) as captured:
        load_scenario(interpolation_path)
    assert "/weather_source/interpolation" in _issue_paths(captured.value)


def test_named_synthetic_weather_is_smoke_only(tmp_path: Path) -> None:
    smoke = _example()
    smoke["metadata"]["scenario_kind"] = "smoke_test"
    smoke["metadata"]["name"] = "Loader smoke scenario"
    smoke["weather_source"] = {
        "source_type": "synthetic_smoke_test",
        "path": None,
        "interpolation": "none",
        "allowable_derived_fields": ["timestamp"],
        "synthetic_profile": "constant_mild_v1",
    }
    smoke["weather_series"] = []
    smoke_path = _write_json(tmp_path / "smoke.json", smoke)

    bundle = load_scenario(smoke_path)

    assert len(bundle.scenario.weather_series) == 4
    assert all(
        state.outdoor_temperature_c == 20.0 for state in bundle.scenario.weather_series
    )
    assert any(
        record.kind == "derived" and record.target_path == "/weather_series"
        for record in bundle.audit_log
    )

    normal = deepcopy(smoke)
    normal["metadata"]["scenario_kind"] = "validated"
    normal_path = _write_json(tmp_path / "normal.json", normal)
    with pytest.raises(ScenarioValidationError) as captured:
        load_scenario(normal_path)
    assert "/weather_source/source_type" in _issue_paths(captured.value)


def test_no_automatic_synthetic_fallback_for_empty_inline_weather(
    tmp_path: Path,
) -> None:
    source = _example()
    source["weather_series"] = []
    scenario_path = _write_json(tmp_path / "scenario.json", source)

    with pytest.raises(ScenarioValidationError) as captured:
        load_scenario(scenario_path)

    assert "/weather_series" in _issue_paths(captured.value)


def test_output_defaults_are_materialized_resolved_and_audited(tmp_path: Path) -> None:
    source = _example()
    del source["output_configuration"]
    scenario_path = _write_json(tmp_path / "scenario.json", source)

    bundle = load_scenario(scenario_path)

    assert (
        bundle.scenario.output_configuration.directory
        == (tmp_path / "artifacts" / "scenarios" / source["scenario_id"]).resolve()
    )
    targets = {record.target_path for record in bundle.audit_log}
    assert "/output_configuration" in targets
    assert "/output_configuration/formats" in targets
    assert "/output_configuration/directory" in targets


def test_schema_version_extra_aliases_and_unit_aliases_fail(tmp_path: Path) -> None:
    unsupported = _example()
    unsupported["schema_version"] = "2.0.0"
    unsupported_path = _write_json(tmp_path / "unsupported.json", unsupported)
    with pytest.raises(ScenarioValidationError) as captured:
        load_scenario(unsupported_path)
    assert _issue_paths(captured.value) == {"/schema_version"}

    alias = _example()
    alias["persons"] = alias["occupants"]
    alias_path = _write_json(tmp_path / "alias.json", alias)
    with pytest.raises(ScenarioValidationError) as captured:
        load_scenario(alias_path)
    assert "/persons" in _issue_paths(captured.value)

    unit_alias = _example()
    state = unit_alias["weather_series"][0]
    state["relative_humidity_percent"] = state.pop("relative_humidity_fraction") * 100
    unit_alias_path = _write_json(tmp_path / "unit-alias.json", unit_alias)
    with pytest.raises(ScenarioValidationError) as captured:
        load_scenario(unit_alias_path)
    assert {
        "/weather_series/0/relative_humidity_fraction",
        "/weather_series/0/relative_humidity_percent",
    } <= _issue_paths(captured.value)


def test_semantic_identity_parent_and_topology_errors_have_paths(
    tmp_path: Path,
) -> None:
    duplicate = _example()
    duplicate["occupants"][0]["occupant_id"] = "living_zone"
    duplicate_path = _write_json(tmp_path / "duplicate.json", duplicate)
    with pytest.raises(ScenarioValidationError) as captured:
        load_scenario(duplicate_path)
    assert "/occupants/0/occupant_id" in _issue_paths(captured.value)

    parent = _example()
    parent["building"]["dwelling"]["zones"][0]["dwelling_id"] = "wrong_parent"
    parent_path = _write_json(tmp_path / "parent.json", parent)
    with pytest.raises(ScenarioValidationError) as captured:
        load_scenario(parent_path)
    assert "/building/dwelling/zones/0/dwelling_id" in _issue_paths(captured.value)

    topology = _example()
    topology["building"]["dwelling"]["zones"][0]["surfaces"][1]["paired_surface_id"] = (
        "living_exterior_south"
    )
    topology_path = _write_json(tmp_path / "topology.json", topology)
    with pytest.raises(ScenarioValidationError) as captured:
        load_scenario(topology_path)
    assert "/building/dwelling/zones/0/surfaces/1/paired_surface_id" in _issue_paths(
        captured.value
    )


def test_versioned_model_covers_all_required_sections() -> None:
    assert set(ScenarioV1.model_fields) == {
        "schema_version",
        "use_case",
        "scenario_id",
        "metadata",
        "site",
        "deterministic_seed",
        "simulation_period",
        "geometry_configuration",
        "building",
        "occupants",
        "weather_source",
        "weather_series",
        "output_configuration",
    }
