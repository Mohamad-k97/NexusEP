"""Field-addressable semantic validation for canonical scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from nexusep.schema.compiler import CanonicalClock, CanonicalContractError
from nexusep.schema.scenario import ScenarioV1


@dataclass(frozen=True, order=True)
class FieldIssue:
    """One deterministic validation issue addressed by canonical JSON path."""

    path: str
    message: str
    error_type: str


class ScenarioValidationError(ValueError):
    """Aggregated structural or semantic scenario errors."""

    def __init__(self, issues: list[FieldIssue] | tuple[FieldIssue, ...]) -> None:
        self.issues = tuple(sorted(issues))
        rendered = "; ".join(f"{issue.path}: {issue.message}" for issue in self.issues)
        super().__init__(rendered or "Scenario validation failed.")


def _json_path(location: tuple[Any, ...]) -> str:
    if not location:
        return "/"
    return "/" + "/".join(
        str(part).replace("~", "~0").replace("/", "~1") for part in location
    )


def issues_from_pydantic(error: ValidationError) -> list[FieldIssue]:
    """Convert Pydantic diagnostics to stable field-level issues."""

    return [
        FieldIssue(
            path=_json_path(tuple(item["loc"])),
            message=item["msg"],
            error_type=item["type"],
        )
        for item in error.errors(include_url=False, include_context=False)
    ]


def _issue(issues: list[FieldIssue], path: str, message: str, error_type: str) -> None:
    issues.append(FieldIssue(path, message, error_type))


def validate_scenario(scenario: ScenarioV1) -> None:
    """Validate references, global identity, topology, time, and source policy."""

    issues: list[FieldIssue] = []
    building = scenario.building
    dwelling = building.dwelling
    zones = dwelling.zones

    identities: list[tuple[str, str, str]] = [
        ("/scenario_id", scenario.scenario_id, "scenario"),
        ("/building/building_id", building.building_id, "building"),
        ("/building/dwelling/dwelling_id", dwelling.dwelling_id, "dwelling"),
    ]
    for zone_index, zone in enumerate(zones):
        zone_path = f"/building/dwelling/zones/{zone_index}"
        identities.append((f"{zone_path}/zone_id", zone.zone_id, "zone"))
        for surface_index, surface in enumerate(zone.surfaces):
            surface_path = f"{zone_path}/surfaces/{surface_index}"
            identities.append(
                (f"{surface_path}/surface_id", surface.surface_id, "surface")
            )
            for opening_index, opening in enumerate(surface.openings):
                identities.append(
                    (
                        f"{surface_path}/openings/{opening_index}/opening_id",
                        opening.opening_id,
                        "opening",
                    )
                )
        for system_index, system in enumerate(zone.systems):
            identities.append(
                (
                    f"{zone_path}/systems/{system_index}/system_id",
                    system.system_id,
                    "system",
                )
            )
    for occupant_index, occupant in enumerate(scenario.occupants):
        identities.append(
            (
                f"/occupants/{occupant_index}/occupant_id",
                occupant.occupant_id,
                "occupant",
            )
        )

    owner_by_id: dict[str, tuple[str, str]] = {}
    for path, external_id, entity_type in identities:
        if external_id in owner_by_id:
            prior_path, prior_type = owner_by_id[external_id]
            _issue(
                issues,
                path,
                f"ID {external_id!r} duplicates {prior_type} at {prior_path}",
                "duplicate_external_id",
            )
        else:
            owner_by_id[external_id] = (path, entity_type)

    expected_scenario_id = scenario.scenario_id
    expected_building_id = building.building_id
    expected_dwelling_id = dwelling.dwelling_id

    def check_reference(path: str, actual: str, expected: str) -> None:
        if actual != expected:
            _issue(
                issues,
                path,
                f"reference {actual!r} does not match expected {expected!r}",
                "reference_mismatch",
            )

    check_reference("/building/scenario_id", building.scenario_id, expected_scenario_id)
    check_reference(
        "/building/dwelling/scenario_id",
        dwelling.scenario_id,
        expected_scenario_id,
    )
    check_reference(
        "/building/dwelling/building_id", dwelling.building_id, expected_building_id
    )

    zone_ids = {zone.zone_id for zone in zones}
    surfaces_by_id = {
        surface.surface_id: surface for zone in zones for surface in zone.surfaces
    }
    for zone_index, zone in enumerate(zones):
        zone_path = f"/building/dwelling/zones/{zone_index}"
        for field, actual, expected in (
            ("scenario_id", zone.scenario_id, expected_scenario_id),
            ("building_id", zone.building_id, expected_building_id),
            ("dwelling_id", zone.dwelling_id, expected_dwelling_id),
        ):
            check_reference(f"{zone_path}/{field}", actual, expected)

        for surface_index, surface in enumerate(zone.surfaces):
            surface_path = f"{zone_path}/surfaces/{surface_index}"
            for field, actual, expected in (
                ("scenario_id", surface.scenario_id, expected_scenario_id),
                ("building_id", surface.building_id, expected_building_id),
                ("dwelling_id", surface.dwelling_id, expected_dwelling_id),
                ("zone_id", surface.zone_id, zone.zone_id),
            ):
                check_reference(f"{surface_path}/{field}", actual, expected)
            if (
                surface.adjacent_zone_id is not None
                and surface.adjacent_zone_id not in zone_ids
            ):
                _issue(
                    issues,
                    f"{surface_path}/adjacent_zone_id",
                    f"unknown zone {surface.adjacent_zone_id!r}",
                    "unknown_reference",
                )
            if surface.paired_surface_id is not None:
                pair = surfaces_by_id.get(surface.paired_surface_id)
                if pair is None:
                    _issue(
                        issues,
                        f"{surface_path}/paired_surface_id",
                        f"unknown surface {surface.paired_surface_id!r}",
                        "unknown_reference",
                    )
                elif (
                    pair.paired_surface_id != surface.surface_id
                    or pair.zone_id != surface.adjacent_zone_id
                    or pair.adjacent_zone_id != surface.zone_id
                ):
                    _issue(
                        issues,
                        f"{surface_path}/paired_surface_id",
                        "interzone surface pairing is not reciprocal",
                        "topology_mismatch",
                    )
            for opening_index, opening in enumerate(surface.openings):
                opening_path = f"{surface_path}/openings/{opening_index}"
                for field, actual, expected in (
                    ("scenario_id", opening.scenario_id, expected_scenario_id),
                    ("building_id", opening.building_id, expected_building_id),
                    ("dwelling_id", opening.dwelling_id, expected_dwelling_id),
                    ("zone_id", opening.zone_id, zone.zone_id),
                    ("surface_id", opening.surface_id, surface.surface_id),
                ):
                    check_reference(f"{opening_path}/{field}", actual, expected)
        for system_index, system in enumerate(zone.systems):
            system_path = f"{zone_path}/systems/{system_index}"
            for field, actual, expected in (
                ("scenario_id", system.scenario_id, expected_scenario_id),
                ("building_id", system.building_id, expected_building_id),
                ("dwelling_id", system.dwelling_id, expected_dwelling_id),
                ("zone_id", system.zone_id, zone.zone_id),
            ):
                check_reference(f"{system_path}/{field}", actual, expected)

    for occupant_index, occupant in enumerate(scenario.occupants):
        occupant_path = f"/occupants/{occupant_index}"
        for field, actual, expected in (
            ("scenario_id", occupant.scenario_id, expected_scenario_id),
            ("building_id", occupant.building_id, expected_building_id),
            ("dwelling_id", occupant.dwelling_id, expected_dwelling_id),
        ):
            check_reference(f"{occupant_path}/{field}", actual, expected)
        for field in ("home_zone_id", "sleep_zone_id"):
            if getattr(occupant, field) not in zone_ids:
                _issue(
                    issues,
                    f"{occupant_path}/{field}",
                    f"unknown zone {getattr(occupant, field)!r}",
                    "unknown_reference",
                )
        schedule = sorted(
            occupant.location_schedule,
            key=lambda entry: entry.start_timestep_index,
        )
        previous_end = 0
        for entry_index, entry in enumerate(schedule):
            entry_path = f"{occupant_path}/location_schedule/{entry_index}"
            if entry.start_timestep_index != previous_end:
                _issue(
                    issues,
                    f"{entry_path}/start_timestep_index",
                    "schedule has a gap or overlap",
                    "schedule_coverage",
                )
            if entry.end_timestep_index <= entry.start_timestep_index:
                _issue(
                    issues,
                    f"{entry_path}/end_timestep_index",
                    "end must be after start",
                    "schedule_range",
                )
            if entry.zone_id not in zone_ids:
                _issue(
                    issues,
                    f"{entry_path}/zone_id",
                    f"unknown zone {entry.zone_id!r}",
                    "unknown_reference",
                )
            previous_end = entry.end_timestep_index
        if previous_end != scenario.simulation_period.n_timesteps:
            _issue(
                issues,
                f"{occupant_path}/location_schedule",
                "schedule must cover the complete simulation period",
                "schedule_coverage",
            )

    if (
        scenario.weather_source.source_type == "synthetic_smoke_test"
        and scenario.metadata.scenario_kind != "smoke_test"
    ):
        _issue(
            issues,
            "/weather_source/source_type",
            "synthetic weather is allowed only for smoke_test scenarios",
            "synthetic_weather_forbidden",
        )

    try:
        clock = CanonicalClock.from_period(
            scenario.simulation_period.model_dump(mode="json")
        )
        clock.validate_weather_series(
            [
                state.model_dump(mode="json", exclude_none=True)
                for state in scenario.weather_series
            ]
        )
    except CanonicalContractError as error:
        _issue(issues, "/weather_series", str(error), "weather_alignment")

    for weather_index, state in enumerate(scenario.weather_series):
        check_reference(
            f"/weather_series/{weather_index}/scenario_id",
            state.scenario_id,
            expected_scenario_id,
        )

    if not Path(scenario.output_configuration.directory).is_absolute():
        _issue(
            issues,
            "/output_configuration/directory",
            "loader must resolve output directory to an absolute path",
            "unresolved_path",
        )
    if (
        scenario.weather_source.path is not None
        and not scenario.weather_source.path.is_absolute()
    ):
        _issue(
            issues,
            "/weather_source/path",
            "loader must resolve weather path to an absolute path",
            "unresolved_path",
        )

    if issues:
        raise ScenarioValidationError(issues)


__all__ = [
    "FieldIssue",
    "ScenarioValidationError",
    "issues_from_pydantic",
    "validate_scenario",
]
