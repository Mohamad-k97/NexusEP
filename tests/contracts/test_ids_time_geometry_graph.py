"""Executable gates for canonical IDs, time, geometry, and graph compilation."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from nexusep.schema import (
    EXTERIOR_NODE_ID,
    CanonicalClock,
    CanonicalContractError,
    CanonicalIDRegistry,
    compile_physics_graph,
    serialize_compiled_graph,
    validate_compiled_graph,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_PATH = (
    REPOSITORY_ROOT / "contracts" / "examples" / "multizone_dwelling_v1_minimal.json"
)
SCENARIO_SCHEMA_PATH = (
    REPOSITORY_ROOT / "contracts" / "multizone_dwelling_v1.schema.json"
)
GRAPH_SCHEMA_PATH = REPOSITORY_ROOT / "contracts" / "compiled_physics_graph.schema.json"
ID_TIME_DOC = REPOSITORY_ROOT / "docs" / "architecture" / "id_and_time_semantics.md"
GEOMETRY_DOC = REPOSITORY_ROOT / "docs" / "architecture" / "geometry_contract.md"
GRAPH_DOC = REPOSITORY_ROOT / "docs" / "architecture" / "physics_graph_contract.md"
COMPILER_ADR = (
    REPOSITORY_ROOT
    / "docs"
    / "architecture"
    / "decisions"
    / "0002-canonical-compilation-boundary.md"
)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


@pytest.fixture
def scenario() -> dict[str, Any]:
    return _load_json(EXAMPLE_PATH)


def _reorder_every_nonsemantic_list(scenario: dict[str, Any]) -> dict[str, Any]:
    reordered = deepcopy(scenario)
    dwelling = reordered["building"]["dwelling"]
    dwelling["zones"].reverse()
    for zone in dwelling["zones"]:
        zone["surfaces"].reverse()
        zone["systems"].reverse()
        for surface in zone["surfaces"]:
            surface["openings"].reverse()
    reordered["occupants"].reverse()
    for occupant in reordered["occupants"]:
        occupant["location_schedule"].reverse()
    reordered["weather_series"].reverse()
    reordered["geometry_configuration"]["enabled_features"].reverse()
    return reordered


def test_registry_is_sorted_and_decodes_original_external_ids(
    scenario: dict[str, Any],
) -> None:
    registry = CanonicalIDRegistry.from_scenario(scenario)

    assert registry.ids("zone") == ("bedroom_zone", "living_zone")
    assert registry.index_for("zone", "bedroom_zone") == 0
    assert registry.index_for("zone", "living_zone") == 1
    assert registry.external_id_for("zone", 0) == "bedroom_zone"
    assert registry.decode_indices("zone", [1, 0]) == [
        "living_zone",
        "bedroom_zone",
    ]


def test_registry_rejects_cross_type_collisions_and_unknown_indices(
    scenario: dict[str, Any],
) -> None:
    scenario["occupants"][0]["occupant_id"] = "living_zone"
    with pytest.raises(CanonicalContractError, match="globally unique"):
        CanonicalIDRegistry.from_scenario(scenario)

    valid = _load_json(EXAMPLE_PATH)
    registry = CanonicalIDRegistry.from_scenario(valid)
    with pytest.raises(CanonicalContractError, match="Unknown zone array index"):
        registry.external_id_for("zone", 2)


def test_compilation_is_independent_of_all_source_list_positions(
    scenario: dict[str, Any],
) -> None:
    original_graph = compile_physics_graph(scenario)
    reordered_graph = compile_physics_graph(_reorder_every_nonsemantic_list(scenario))

    assert reordered_graph == original_graph
    assert serialize_compiled_graph(reordered_graph) == serialize_compiled_graph(
        original_graph
    )
    assert reordered_graph["graph_sha256"] == original_graph["graph_sha256"]


def test_explicit_parent_reference_mismatch_is_rejected(
    scenario: dict[str, Any],
) -> None:
    scenario["building"]["dwelling"]["zones"][0]["dwelling_id"] = "wrong_parent"

    with pytest.raises(CanonicalContractError, match="expected 'dwelling_001'"):
        compile_physics_graph(scenario)


def test_clock_uses_half_open_start_of_interval_semantics() -> None:
    clock = CanonicalClock.from_period(
        {
            "start_datetime": "2026-01-15T00:00:00+01:00",
            "timezone": "Europe/Rome",
            "n_timesteps": 4,
            "dt_minutes": 60.0,
        }
    )

    assert clock.timestamp_for_index(0).isoformat() == "2026-01-15T00:00:00+01:00"
    assert clock.timestamp_for_index(3).isoformat() == "2026-01-15T03:00:00+01:00"
    assert clock.end_datetime_exclusive.isoformat() == "2026-01-15T04:00:00+01:00"
    assert clock.interval_for_index(3)[1] == clock.end_datetime_exclusive
    assert clock.timestep_index_for_timestamp("2026-01-15T02:00:00+01:00") == 2
    with pytest.raises(CanonicalContractError, match="outside the half-open"):
        clock.timestep_index_for_timestamp(clock.end_datetime_exclusive)
    with pytest.raises(CanonicalContractError, match="not a timestep interval start"):
        clock.timestep_index_for_timestamp("2026-01-15T02:30:00+01:00")


def test_clock_has_explicit_dst_and_leap_year_behavior() -> None:
    spring = CanonicalClock.from_period(
        {
            "start_datetime": "2026-03-29T01:30:00+01:00",
            "timezone": "Europe/Rome",
            "n_timesteps": 2,
            "dt_minutes": 60,
        }
    )
    assert spring.timestamp_for_index(1).isoformat() == "2026-03-29T03:30:00+02:00"

    autumn = CanonicalClock.from_period(
        {
            "start_datetime": "2026-10-25T02:30:00+02:00",
            "timezone": "Europe/Rome",
            "n_timesteps": 2,
            "dt_minutes": 60,
        }
    )
    assert autumn.timestamp_for_index(1).isoformat() == "2026-10-25T02:30:00+01:00"
    assert autumn.timestep_index_for_timestamp("2026-10-25T02:30:00+01:00") == 1

    leap = CanonicalClock.from_period(
        {
            "start_datetime": "2028-02-28T23:00:00+01:00",
            "timezone": "Europe/Rome",
            "n_timesteps": 25,
            "dt_minutes": 60,
        }
    )
    assert leap.timestamp_for_index(1).date().isoformat() == "2028-02-29"
    assert leap.end_datetime_exclusive.date().isoformat() == "2028-03-01"


def test_clock_rejects_timezone_mismatch_and_authored_end_time() -> None:
    mismatch = {
        "start_datetime": "2026-01-15T00:00:00+00:00",
        "timezone": "Europe/Rome",
        "n_timesteps": 1,
        "dt_minutes": 60,
    }
    with pytest.raises(CanonicalContractError, match="do not agree"):
        CanonicalClock.from_period(mismatch)

    authored_end = dict(mismatch)
    authored_end["start_datetime"] = "2026-01-15T00:00:00+01:00"
    authored_end["end_datetime_exclusive"] = "2026-01-15T01:00:00+01:00"
    with pytest.raises(CanonicalContractError, match="must not be supplied"):
        CanonicalClock.from_period(authored_end)


def test_weather_alignment_uses_index_not_list_position(
    scenario: dict[str, Any],
) -> None:
    reversed_weather = deepcopy(scenario)
    reversed_weather["weather_series"].reverse()
    assert (
        compile_physics_graph(reversed_weather)["time_axis"]
        == compile_physics_graph(scenario)["time_axis"]
    )

    scenario["weather_series"][2]["timestamp"] = "2026-01-15T02:30:00+01:00"
    with pytest.raises(CanonicalContractError, match="not its interval start"):
        compile_physics_graph(scenario)


def test_graph_has_explicit_exterior_and_valid_deterministic_connections(
    scenario: dict[str, Any],
) -> None:
    graph = compile_physics_graph(scenario)

    assert graph["nodes"][0]["node_id"] == EXTERIOR_NODE_ID
    assert [node["node_id"] for node in graph["nodes"][1:]] == [
        "bedroom_zone",
        "living_zone",
    ]
    assert len(graph["connections"]) == 5
    assert [item["connection_id"] for item in graph["connections"]] == sorted(
        item["connection_id"] for item in graph["connections"]
    )
    assert (
        sum(item["boundary_type"] == "interzone" for item in graph["connections"]) == 1
    )
    assert all(
        item["target_node_id"] == EXTERIOR_NODE_ID
        for item in graph["connections"]
        if item["boundary_type"] == "exterior"
    )
    assert validate_compiled_graph(graph)


def test_graph_derived_geometry_has_provenance(scenario: dict[str, Any]) -> None:
    graph = compile_physics_graph(scenario)
    surface = next(
        item
        for item in graph["connections"]
        if item["connection_id"] == "surface:living_exterior_south"
    )
    opening = next(
        item
        for item in graph["connections"]
        if item["connection_id"] == "opening:living_window_south"
    )

    assert surface["gross_area_m2"] == 24.0
    assert surface["net_opaque_area_m2"] == 20.0
    assert surface["provenance"]["net_opaque_area_m2"]["method"] == "derived"
    assert opening["provenance"]["azimuth_deg"]["rule"] == (
        "inherited from owner surface"
    )


def test_graph_rejects_invalid_pairs_opening_area_and_digest(
    scenario: dict[str, Any],
) -> None:
    zones = scenario["building"]["dwelling"]["zones"]
    living_interzone = next(
        item for item in zones[0]["surfaces"] if item["boundary_type"] == "interzone"
    )
    living_interzone["paired_surface_id"] = "living_exterior_south"
    with pytest.raises(CanonicalContractError, match="not reciprocal"):
        compile_physics_graph(scenario)

    oversized = _load_json(EXAMPLE_PATH)
    oversized["building"]["dwelling"]["zones"][0]["surfaces"][0]["openings"][0][
        "area_m2"
    ] = 25.0
    with pytest.raises(CanonicalContractError, match="exceed area"):
        compile_physics_graph(oversized)

    graph = compile_physics_graph(_load_json(EXAMPLE_PATH))
    graph["nodes"][1]["volume_m3"] = 999.0
    with pytest.raises(CanonicalContractError, match="digest does not match"):
        validate_compiled_graph(graph)


def test_minimal_geometry_has_no_hidden_defaults_or_gis_dependency(
    scenario: dict[str, Any],
) -> None:
    configuration = scenario["geometry_configuration"]
    assert configuration["geometry_tier"] == "thermal_topology_v1"
    assert configuration["defaults_applied"] == []
    assert configuration["derived_values"] == []
    assert configuration["optional_geometry_affects_physics"] is False
    assert "vertices" not in json.dumps(scenario).casefold()
    assert "geographic" not in json.dumps(scenario).casefold()
    assert compile_physics_graph(scenario)["geometry_configuration"] == {
        **configuration,
        "enabled_features": sorted(configuration["enabled_features"]),
    }

    del scenario["geometry_configuration"]
    with pytest.raises(CanonicalContractError, match="geometry_configuration"):
        compile_physics_graph(scenario)


def test_schema_freezes_parent_references_and_pair_topology() -> None:
    schema = _load_json(SCENARIO_SCHEMA_PATH)
    required_by_definition = {
        name: set(schema["$defs"][name]["required"])
        for name in (
            "building",
            "dwelling",
            "zone",
            "surface",
            "opening",
            "system",
            "occupant",
        )
    }

    assert {"scenario_id", "building_id"} <= required_by_definition["dwelling"]
    assert {"scenario_id", "building_id", "dwelling_id"} <= required_by_definition[
        "zone"
    ]
    assert {"zone_id", "paired_surface_id"} <= required_by_definition["surface"]
    assert {"zone_id", "surface_id", "boundary_type", "adjacent_zone_id"} <= (
        required_by_definition["opening"]
    )
    assert "zone_id" in required_by_definition["system"]
    assert {"building_id", "dwelling_id"} <= required_by_definition["occupant"]


def test_compiled_graph_schema_gives_every_numeric_property_a_unit() -> None:
    schema = _load_json(GRAPH_SCHEMA_PATH)
    numeric_definitions: list[tuple[str, dict[str, Any]]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            properties = value.get("properties")
            if isinstance(properties, dict):
                for name, definition in properties.items():
                    field_type = definition.get("type")
                    if (
                        field_type == "integer"
                        or field_type == "number"
                        or (
                            isinstance(field_type, list)
                            and ({"integer", "number"} & set(field_type))
                        )
                    ):
                        numeric_definitions.append((name, definition))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    assert numeric_definitions
    assert all("x-unit" in definition for _, definition in numeric_definitions)


def test_documents_freeze_the_requested_policy() -> None:
    id_time = " ".join(ID_TIME_DOC.read_text(encoding="utf-8").split()).casefold()
    geometry = " ".join(GEOMETRY_DOC.read_text(encoding="utf-8").split()).casefold()
    graph = " ".join(GRAPH_DOC.read_text(encoding="utf-8").split()).casefold()
    decision = " ".join(COMPILER_ADR.read_text(encoding="utf-8").split()).casefold()

    for phrase in (
        "globally unique within one scenario",
        "no canonical relationship or output may rely on list position",
        "original string",
        "start of its half-open interval",
        "daylight-saving",
        "leap days",
        "end_datetime_exclusive",
    ):
        assert phrase in id_time
    for phrase in (
        "zone volume",
        "boundary topology",
        "optional geometric detail",
        "vertices",
        "geographic coordinates",
        "detailed shading objects",
        "material-layer geometry",
        "visualization metadata",
        "gis source references",
        "no defaults were used",
    ):
        assert phrase in geometry
    for phrase in (
        "users describe physical entities and topology",
        "explicit reserved exterior node",
        "no connection is orphaned",
        "deterministically ordered",
    ):
        assert phrase in graph
    assert "users do not author the low-level physics graph" in decision
    assert "before either physics backend starts" in decision
