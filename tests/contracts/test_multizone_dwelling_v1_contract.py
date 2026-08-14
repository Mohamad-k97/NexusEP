"""Executable gates for the ``multizone_dwelling_v1`` canonical contract."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = REPOSITORY_ROOT / "contracts"
SCHEMA_PATH = CONTRACTS / "multizone_dwelling_v1.schema.json"
REGISTRY_PATH = CONTRACTS / "multizone_dwelling_v1.units.json"
TERMS_PATH = CONTRACTS / "canonical_terms.json"
EXAMPLE_PATH = CONTRACTS / "examples" / "multizone_dwelling_v1_minimal.json"
ADR_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "architecture"
    / "decisions"
    / "0001-dual-engine-policy.md"
)
USE_CASE_PATH = REPOSITORY_ROOT / "docs" / "architecture" / "multizone_dwelling_v1.md"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _walk_dicts(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _public_field_names(value: Any) -> set[str]:
    names: set[str] = set()
    for node in _walk_dicts(value):
        properties = node.get("properties")
        if isinstance(properties, dict):
            names.update(properties)
    return names


def _field_name(path: str) -> str:
    return path.rsplit(".", 1)[-1].replace("[]", "")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return _load_json(SCHEMA_PATH)


@pytest.fixture(scope="module")
def registry() -> dict[str, Any]:
    return _load_json(REGISTRY_PATH)


@pytest.fixture(scope="module")
def terms() -> dict[str, Any]:
    return _load_json(TERMS_PATH)


@pytest.fixture(scope="module")
def example() -> dict[str, Any]:
    return _load_json(EXAMPLE_PATH)


def test_schema_numeric_inputs_and_unit_registry_are_bijective(
    schema: dict[str, Any], registry: dict[str, Any]
) -> None:
    schema_fields = {
        node["x-registry-path"]: node
        for node in _walk_dicts(schema)
        if "x-registry-path" in node
    }
    registered_inputs = {
        field["path"]: field
        for field in registry["fields"]
        if field["direction"] == "input"
    }

    assert len(schema_fields) == 65
    assert schema_fields.keys() == registered_inputs.keys()
    for path, definition in schema_fields.items():
        registered = registered_inputs[path]
        field_type = definition["type"]
        assert (
            field_type == "integer"
            or field_type == "number"
            or (
                isinstance(field_type, list)
                and ({"integer", "number"} & set(field_type))
            )
        )
        assert definition["x-unit"] == registered["unit"]
        assert registered["type"] in {"integer", "float64"}
        assert registered["accepted_range"]
        assert registered["aggregation"]


def test_no_numeric_schema_property_has_an_implicit_unit(
    schema: dict[str, Any],
) -> None:
    numeric_properties: list[tuple[str, dict[str, Any]]] = []
    for node in _walk_dicts(schema):
        properties = node.get("properties")
        if not isinstance(properties, dict):
            continue
        numeric_properties.extend(
            (name, definition)
            for name, definition in properties.items()
            if definition.get("type") == "integer"
            or definition.get("type") == "number"
            or (
                isinstance(definition.get("type"), list)
                and ({"integer", "number"} & set(definition["type"]))
            )
        )

    assert numeric_properties
    for name, definition in numeric_properties:
        assert "x-unit" in definition, name
        assert "x-registry-path" in definition, name


def test_every_registry_path_is_unique_and_fully_specified(
    registry: dict[str, Any],
) -> None:
    fields = registry["fields"]
    paths = [field["path"] for field in fields]

    assert len(paths) == len(set(paths))
    assert {field["direction"] for field in fields} == {"input", "output"}
    for field in fields:
        assert set(field) == {
            "path",
            "direction",
            "type",
            "unit",
            "accepted_range",
            "aggregation",
        }
        assert field["unit"]
        assert field["accepted_range"]
        assert field["aggregation"]


def test_unit_suffixes_are_explicit(registry: dict[str, Any]) -> None:
    required_suffix = {
        "degC": "_c",
        "W": "_w",
        "Wh": "_wh",
        "kg/s": "_kg_s",
        "m3/s": "_m3_s",
        "Pa": "_pa",
        "ppm": "_ppm",
        "kg/kg": "_kg_kg",
        "m2": "_m2",
        "m3": "_m3",
        "m": "_m",
        "deg": "_deg",
        "m/s": "_m_s",
        "W/m2": "_w_m2",
        "W/(m2*K)": "_w_m2_k",
        "J/K": "_j_k",
        "lux": "_lux",
    }
    for field in registry["fields"]:
        suffix = required_suffix.get(field["unit"])
        if suffix is not None:
            assert _field_name(field["path"]).endswith(suffix), field["path"]

    minute_fields = [field for field in registry["fields"] if field["unit"] == "min"]
    assert [_field_name(field["path"]) for field in minute_fields] == ["dt_minutes"]


def test_relative_humidity_is_a_fraction_everywhere(
    schema: dict[str, Any], registry: dict[str, Any]
) -> None:
    humidity_fields = [
        field for field in registry["fields"] if "relative_humidity" in field["path"]
    ]

    assert humidity_fields
    assert registry["relative_humidity_convention"] == "fraction"
    assert all(
        field["path"].endswith("relative_humidity_fraction")
        for field in humidity_fields
    )
    assert all(field["unit"] == "1" for field in humidity_fields)
    assert all(field["accepted_range"] == "[0, 1]" for field in humidity_fields)
    assert "relative_humidity_percent" not in _public_field_names(schema)


def test_aliases_do_not_leak_into_canonical_schema(
    schema: dict[str, Any], terms: dict[str, Any]
) -> None:
    public_names = _public_field_names(schema)
    forbidden = set(terms["forbidden_canonical_field_tokens"])

    for name in public_names:
        assert name not in forbidden
        assert not any(name.startswith(f"{token}_") for token in forbidden)


def test_dual_engine_policy_records_required_status_and_evidence() -> None:
    decision = ADR_PATH.read_text(encoding="utf-8").casefold()

    assert "object engine" in decision and "reference_candidate" in decision
    assert "array engine" in decision and "experimental" in decision
    assert "neither engine" in decision and "canonical" in decision
    for evidence in (
        "contract conformance",
        "deterministic behavior",
        "conservation and invariant checks",
        "scenario-level parity",
        "documented numerical tolerances",
    ):
        assert evidence in decision
    assert "retirement" in decision
    assert "feature implemented in only one engine" in decision


def test_supported_use_case_records_required_scope_and_exclusions() -> None:
    use_case = USE_CASE_PATH.read_text(encoding="utf-8").casefold()

    for required in (
        "one building",
        "one dwelling",
        "multiple thermal zones",
        "at least two occupants",
        "fixed timestep",
        "deterministic seed",
        "occupancy",
        "controls",
        "airflow",
        "thermal",
        "moisture",
        "co₂",
        "energy",
    ):
        assert required in use_case
    for excluded in (
        "multiple dwellings",
        "district simulation",
        "adaptive timesteps",
        "shared-space arbitration",
        "detailed shading",
        "unsupported hvac networks",
        "calibration",
        "uncertainty",
    ):
        assert excluded in use_case


def test_example_has_one_building_one_dwelling_and_required_entities(
    example: dict[str, Any],
) -> None:
    assert example["use_case"] == "multizone_dwelling_v1"
    assert isinstance(example["building"], dict)
    assert isinstance(example["building"]["dwelling"], dict)

    dwelling = example["building"]["dwelling"]
    zones = dwelling["zones"]
    occupants = example["occupants"]
    assert len(zones) >= 2
    assert len(occupants) >= 2
    assert sum(zone["floor_area_m2"] for zone in zones) == pytest.approx(
        dwelling["floor_area_m2"]
    )
    assert sum(zone["volume_m3"] for zone in zones) == pytest.approx(
        dwelling["volume_m3"]
    )
    assert dwelling["floor_area_m2"] == pytest.approx(
        example["building"]["floor_area_m2"]
    )
    assert dwelling["volume_m3"] == pytest.approx(example["building"]["volume_m3"])


def test_example_topology_and_references_are_consistent(
    example: dict[str, Any],
) -> None:
    dwelling = example["building"]["dwelling"]
    zones = dwelling["zones"]
    zone_ids = {zone["zone_id"] for zone in zones}
    assert len(zone_ids) == len(zones)

    boundaries: set[tuple[str, str]] = set()
    boundary_types: set[str] = set()
    opening_types: set[str] = set()
    for zone in zones:
        for surface in zone["surfaces"]:
            boundary_type = surface["boundary_type"]
            adjacent_zone_id = surface["adjacent_zone_id"]
            boundary_types.add(boundary_type)
            if boundary_type == "exterior":
                assert adjacent_zone_id is None
            else:
                assert boundary_type == "interzone"
                assert adjacent_zone_id in zone_ids - {zone["zone_id"]}
                boundaries.add((zone["zone_id"], adjacent_zone_id))
            for opening in surface["openings"]:
                opening_types.add(opening["opening_type"])
                assert opening["openable_area_m2"] <= opening["area_m2"]

    assert boundary_types == {"exterior", "interzone"}
    assert "window" in opening_types
    assert all((target, source) in boundaries for source, target in boundaries)


def test_example_systems_cover_basic_services(example: dict[str, Any]) -> None:
    systems = [
        system
        for zone in example["building"]["dwelling"]["zones"]
        for system in zone["systems"]
    ]
    assert {system["system_type"] for system in systems} == {
        "heating",
        "cooling",
        "ventilation",
        "lighting",
    }


def test_example_occupant_schedules_cover_the_period(example: dict[str, Any]) -> None:
    period = example["simulation_period"]
    n_timesteps = period["n_timesteps"]
    dwelling = example["building"]["dwelling"]
    zone_ids = {zone["zone_id"] for zone in dwelling["zones"]}
    has_location_change = False

    for occupant in example["occupants"]:
        assert occupant["dwelling_id"] == dwelling["dwelling_id"]
        schedule = occupant["location_schedule"]
        assert schedule[0]["start_timestep_index"] == 0
        assert schedule[-1]["end_timestep_index"] == n_timesteps
        assert all(item["zone_id"] in zone_ids for item in schedule)
        assert all(
            current["end_timestep_index"] == following["start_timestep_index"]
            for current, following in pairwise(schedule)
        )
        has_location_change |= len({item["zone_id"] for item in schedule}) > 1

    assert has_location_change


def test_example_weather_matches_fixed_simulation_clock(
    example: dict[str, Any],
) -> None:
    period = example["simulation_period"]
    weather = example["weather_series"]
    n_timesteps = period["n_timesteps"]
    step = timedelta(minutes=period["dt_minutes"])
    start = _parse_timestamp(period["start_datetime"])

    assert isinstance(example["deterministic_seed"], int)
    assert period["dt_minutes"] > 0
    assert len(weather) == n_timesteps
    assert [state["timestep_index"] for state in weather] == list(range(n_timesteps))
    assert [_parse_timestamp(state["timestamp"]) for state in weather] == [
        start + index * step for index in range(n_timesteps)
    ]
    assert all(0 <= state["relative_humidity_fraction"] <= 1 for state in weather)
