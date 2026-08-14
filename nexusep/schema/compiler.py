"""Backend-independent compiler for canonical NexusEP scenarios.

This module defines the Phase 2 contract boundary.  It intentionally does not
import either the object or array simulation backend.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

EXTERIOR_NODE_ID = "__exterior__"
EXTERNAL_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
ENTITY_TYPES = (
    "scenario",
    "building",
    "dwelling",
    "zone",
    "surface",
    "opening",
    "system",
    "occupant",
)


class CanonicalContractError(ValueError):
    """Raised when a canonical scenario cannot be compiled unambiguously."""


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CanonicalContractError(f"{label} must be an object.")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise CanonicalContractError(f"{label} must be an array.")
    return value


def _validate_external_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not EXTERNAL_ID_PATTERN.fullmatch(value):
        raise CanonicalContractError(
            f"{label} must be a non-empty canonical external ID; got {value!r}."
        )
    return value


def _identity_values(scenario: dict[str, Any]) -> dict[str, list[str]]:
    building = _require_mapping(scenario.get("building"), "building")
    dwelling = _require_mapping(building.get("dwelling"), "building.dwelling")
    zones = _require_list(dwelling.get("zones"), "building.dwelling.zones")
    occupants = _require_list(scenario.get("occupants"), "occupants")

    surfaces: list[dict[str, Any]] = []
    openings: list[dict[str, Any]] = []
    systems: list[dict[str, Any]] = []
    for zone in zones:
        zone = _require_mapping(zone, "zone")
        zone_surfaces = _require_list(zone.get("surfaces"), "zone.surfaces")
        zone_systems = _require_list(zone.get("systems"), "zone.systems")
        surfaces.extend(_require_mapping(item, "surface") for item in zone_surfaces)
        systems.extend(_require_mapping(item, "system") for item in zone_systems)
        for surface in zone_surfaces:
            surface = _require_mapping(surface, "surface")
            openings.extend(
                _require_mapping(item, "opening")
                for item in _require_list(surface.get("openings"), "surface.openings")
            )

    return {
        "scenario": [scenario.get("scenario_id")],
        "building": [building.get("building_id")],
        "dwelling": [dwelling.get("dwelling_id")],
        "zone": [zone.get("zone_id") for zone in zones],
        "surface": [surface.get("surface_id") for surface in surfaces],
        "opening": [opening.get("opening_id") for opening in openings],
        "system": [system.get("system_id") for system in systems],
        "occupant": [occupant.get("occupant_id") for occupant in occupants],
    }


class CanonicalIDRegistry:
    """Deterministic external-string-to-array-index registry."""

    def __init__(self, ids_by_entity_type: dict[str, tuple[str, ...]]) -> None:
        self._ids_by_entity_type = ids_by_entity_type
        self._indices_by_entity_type = {
            entity_type: {external_id: index for index, external_id in enumerate(ids)}
            for entity_type, ids in ids_by_entity_type.items()
        }

    @classmethod
    def from_scenario(cls, scenario: dict[str, Any]) -> CanonicalIDRegistry:
        values = _identity_values(scenario)
        owner_by_id: dict[str, str] = {}
        normalized: dict[str, tuple[str, ...]] = {}

        for entity_type in ENTITY_TYPES:
            ids: list[str] = []
            for position, raw_id in enumerate(values[entity_type]):
                external_id = _validate_external_id(
                    raw_id, f"{entity_type} identity at position {position}"
                )
                if external_id in owner_by_id:
                    raise CanonicalContractError(
                        f"External ID {external_id!r} is used by both "
                        f"{owner_by_id[external_id]} and {entity_type}; IDs must be "
                        "globally unique within a scenario."
                    )
                owner_by_id[external_id] = entity_type
                ids.append(external_id)
            normalized[entity_type] = tuple(sorted(ids))

        return cls(normalized)

    def ids(self, entity_type: str) -> tuple[str, ...]:
        try:
            return self._ids_by_entity_type[entity_type]
        except KeyError as error:
            raise CanonicalContractError(
                f"Unknown entity type {entity_type!r}; expected one of {ENTITY_TYPES}."
            ) from error

    def index_for(self, entity_type: str, external_id: str) -> int:
        try:
            return self._indices_by_entity_type[entity_type][external_id]
        except KeyError as error:
            raise CanonicalContractError(
                f"Unknown {entity_type} external ID {external_id!r}."
            ) from error

    def external_id_for(self, entity_type: str, index: int) -> str:
        if isinstance(index, bool) or not isinstance(index, int):
            raise CanonicalContractError("Array index must be an integer.")
        ids = self.ids(entity_type)
        if not 0 <= index < len(ids):
            raise CanonicalContractError(
                f"Unknown {entity_type} array index {index}; valid range is "
                f"[0, {len(ids)})."
            )
        return ids[index]

    def decode_indices(self, entity_type: str, indices: list[int]) -> list[str]:
        return [self.external_id_for(entity_type, index) for index in indices]

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_version": "1.0.0",
            "ordering": "ascending_ascii_codepoint_by_external_id",
            "entity_types": {
                entity_type: {
                    "external_ids": list(self.ids(entity_type)),
                    "indices": list(range(len(self.ids(entity_type)))),
                }
                for entity_type in ENTITY_TYPES
            },
        }


def _parse_aware_datetime(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise CanonicalContractError(f"{label} must be an ISO 8601 string.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise CanonicalContractError(
            f"{label} is not a valid ISO 8601 timestamp."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CanonicalContractError(f"{label} must include an explicit UTC offset.")
    return parsed


@dataclass(frozen=True)
class CanonicalClock:
    """Fixed elapsed-time clock with timezone-aware interval boundaries."""

    start_datetime: datetime
    timezone_name: str
    n_timesteps: int
    dt_minutes: float

    @classmethod
    def from_period(cls, period: dict[str, Any]) -> CanonicalClock:
        period = _require_mapping(period, "simulation_period")
        if "end_datetime" in period or "end_datetime_exclusive" in period:
            raise CanonicalContractError(
                "End time is derived and must not be supplied in simulation_period."
            )

        start = _parse_aware_datetime(period.get("start_datetime"), "start_datetime")
        timezone_name = period.get("timezone")
        if not isinstance(timezone_name, str) or not timezone_name:
            raise CanonicalContractError("timezone must be a non-empty IANA name.")
        try:
            timezone_info = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as error:
            raise CanonicalContractError(
                f"timezone {timezone_name!r} is not available as an IANA timezone."
            ) from error

        normalized_start = start.astimezone(timezone_info)
        if (
            normalized_start.replace(tzinfo=None) != start.replace(tzinfo=None)
            or normalized_start.utcoffset() != start.utcoffset()
        ):
            raise CanonicalContractError(
                "start_datetime wall time and offset do not agree with timezone."
            )

        n_timesteps = period.get("n_timesteps")
        if (
            isinstance(n_timesteps, bool)
            or not isinstance(n_timesteps, int)
            or n_timesteps < 1
        ):
            raise CanonicalContractError("n_timesteps must be a positive integer.")

        dt_minutes = period.get("dt_minutes")
        if isinstance(dt_minutes, bool) or not isinstance(dt_minutes, (int, float)):
            raise CanonicalContractError("dt_minutes must be a positive finite number.")
        dt_minutes = float(dt_minutes)
        if not math.isfinite(dt_minutes) or dt_minutes <= 0.0:
            raise CanonicalContractError("dt_minutes must be a positive finite number.")
        if timedelta(minutes=dt_minutes).total_seconds() <= 0.0:
            raise CanonicalContractError("dt_minutes is below datetime resolution.")

        return cls(normalized_start, timezone_name, n_timesteps, dt_minutes)

    @property
    def dt(self) -> timedelta:
        return timedelta(minutes=self.dt_minutes)

    @property
    def end_datetime_exclusive(self) -> datetime:
        return self._boundary_datetime(self.n_timesteps)

    def _boundary_datetime(self, boundary_index: int) -> datetime:
        utc_start = self.start_datetime.astimezone(UTC)
        instant = utc_start + boundary_index * self.dt
        return instant.astimezone(ZoneInfo(self.timezone_name))

    def timestamp_for_index(self, timestep_index: int) -> datetime:
        if (
            isinstance(timestep_index, bool)
            or not isinstance(timestep_index, int)
            or not 0 <= timestep_index < self.n_timesteps
        ):
            raise CanonicalContractError(
                f"timestep_index must be an integer in [0, {self.n_timesteps})."
            )
        return self._boundary_datetime(timestep_index)

    def interval_for_index(self, timestep_index: int) -> tuple[datetime, datetime]:
        start = self.timestamp_for_index(timestep_index)
        return start, self._boundary_datetime(timestep_index + 1)

    def timestep_index_for_timestamp(self, timestamp: str | datetime) -> int:
        parsed = (
            _parse_aware_datetime(timestamp, "timestamp")
            if isinstance(timestamp, str)
            else timestamp
        )
        if not isinstance(parsed, datetime) or parsed.tzinfo is None:
            raise CanonicalContractError("timestamp must be timezone-aware.")

        delta = parsed.astimezone(UTC) - self.start_datetime.astimezone(UTC)
        delta_us = (
            delta.days * 86_400_000_000 + delta.seconds * 1_000_000 + delta.microseconds
        )
        dt_us = round(self.dt.total_seconds() * 1_000_000)
        if delta_us < 0 or delta_us >= self.n_timesteps * dt_us:
            raise CanonicalContractError(
                "timestamp is outside the half-open simulation period."
            )
        timestep_index, remainder = divmod(delta_us, dt_us)
        if remainder:
            raise CanonicalContractError("timestamp is not a timestep interval start.")
        return timestep_index

    def validate_weather_series(self, weather_series: list[Any]) -> None:
        weather_series = _require_list(weather_series, "weather_series")
        if len(weather_series) != self.n_timesteps:
            raise CanonicalContractError(
                "weather_series must contain exactly one state per timestep."
            )

        by_index: dict[int, dict[str, Any]] = {}
        for item in weather_series:
            state = _require_mapping(item, "weather state")
            index = state.get("timestep_index")
            if isinstance(index, bool) or not isinstance(index, int):
                raise CanonicalContractError(
                    "Weather timestep_index must be an integer."
                )
            if index in by_index:
                raise CanonicalContractError(
                    f"Duplicate weather timestep_index {index}."
                )
            by_index[index] = state

        if set(by_index) != set(range(self.n_timesteps)):
            raise CanonicalContractError(
                "Weather indices must cover [0, n_timesteps) without gaps."
            )

        for index, state in by_index.items():
            actual = _parse_aware_datetime(
                state.get("timestamp"), f"weather timestamp at index {index}"
            )
            expected = self.timestamp_for_index(index)
            if (
                actual.astimezone(UTC) != expected.astimezone(UTC)
                or actual.utcoffset() != expected.utcoffset()
            ):
                raise CanonicalContractError(
                    f"Weather timestamp at index {index} is not its interval start."
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_datetime": self.start_datetime.isoformat(),
            "timezone": self.timezone_name,
            "n_timesteps": self.n_timesteps,
            "dt_minutes": self.dt_minutes,
            "end_datetime_exclusive": self.end_datetime_exclusive.isoformat(),
            "timestamp_semantics": "start_of_half_open_interval",
            "weather_final_interval": "last_state_applies_to_exclusive_end",
            "elapsed_time_policy": "fixed_duration_on_utc_timeline",
        }


def _require_reference(entity: dict[str, Any], field: str, expected: str) -> None:
    actual = entity.get(field)
    if actual != expected:
        identity = next(
            (value for key, value in entity.items() if key.endswith("_id")), "entity"
        )
        raise CanonicalContractError(
            f"{identity!r} has {field}={actual!r}; expected {expected!r}."
        )


def _normalized_provenance(records: Any, label: str) -> list[dict[str, Any]]:
    records = _require_list(records, label)
    normalized: list[dict[str, Any]] = []
    for raw in records:
        record = _require_mapping(raw, f"{label} record")
        required = {"target_path", "method", "source_paths", "rule"}
        if set(record) != required:
            raise CanonicalContractError(
                f"{label} records require exactly {sorted(required)}."
            )
        if record["method"] not in {"provided", "derived", "defaulted"}:
            raise CanonicalContractError(f"Invalid provenance method in {label}.")
        sources = _require_list(record["source_paths"], f"{label}.source_paths")
        normalized.append(
            {
                "target_path": str(record["target_path"]),
                "method": record["method"],
                "source_paths": sorted(str(source) for source in sources),
                "rule": str(record["rule"]),
            }
        )
    return sorted(
        normalized,
        key=lambda item: (item["target_path"], item["method"], item["rule"]),
    )


def _validate_geometry_configuration(value: Any) -> dict[str, Any]:
    config = _require_mapping(value, "geometry_configuration")
    if config.get("geometry_tier") != "thermal_topology_v1":
        raise CanonicalContractError("geometry_tier must be thermal_topology_v1.")
    features = _require_list(config.get("enabled_features"), "enabled_features")
    allowed_features = {"airflow", "solar_gains", "daylight"}
    if len(features) != len(set(features)) or not set(features) <= allowed_features:
        raise CanonicalContractError(
            "enabled_features contains duplicates or unknown values."
        )
    if (
        config.get("orientation_convention")
        != "azimuth_clockwise_from_true_north_tilt_from_horizontal"
    ):
        raise CanonicalContractError("Unsupported orientation convention.")
    if config.get("optional_geometry_affects_physics") is not False:
        raise CanonicalContractError(
            "optional_geometry_affects_physics must be explicitly false."
        )
    return {
        "geometry_tier": "thermal_topology_v1",
        "enabled_features": sorted(features),
        "orientation_convention": config["orientation_convention"],
        "optional_geometry_affects_physics": False,
        "defaults_applied": _normalized_provenance(
            config.get("defaults_applied"), "defaults_applied"
        ),
        "derived_values": _normalized_provenance(
            config.get("derived_values"), "derived_values"
        ),
    }


def _close(left: Any, right: Any) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-12)


def _source_path(entity_type: str, external_id: str, field: str) -> str:
    return f"/{entity_type}s/{external_id}/{field}"


def _graph_provenance(
    method: str, source_paths: list[str], rule: str
) -> dict[str, Any]:
    return {"method": method, "source_paths": sorted(source_paths), "rule": rule}


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _graph_digest(graph_without_digest: dict[str, Any]) -> str:
    return hashlib.sha256(
        _canonical_json(graph_without_digest).encode("utf-8")
    ).hexdigest()


def compile_physics_graph(scenario: dict[str, Any]) -> dict[str, Any]:
    """Validate and deterministically compile a canonical scenario."""

    scenario = _require_mapping(scenario, "scenario")
    registry = CanonicalIDRegistry.from_scenario(scenario)
    scenario_id = registry.ids("scenario")[0]
    period = _require_mapping(scenario.get("simulation_period"), "simulation_period")
    weather_series = _require_list(scenario.get("weather_series"), "weather_series")
    clock = CanonicalClock.from_period(period)
    clock.validate_weather_series(weather_series)
    geometry = _validate_geometry_configuration(scenario.get("geometry_configuration"))

    building = _require_mapping(scenario.get("building"), "building")
    building_id = building["building_id"]
    _require_reference(building, "scenario_id", scenario_id)
    dwelling = _require_mapping(building.get("dwelling"), "building.dwelling")
    dwelling_id = dwelling["dwelling_id"]
    _require_reference(dwelling, "scenario_id", scenario_id)
    _require_reference(dwelling, "building_id", building_id)

    zones = [_require_mapping(item, "zone") for item in dwelling["zones"]]
    zone_by_id = {zone["zone_id"]: zone for zone in zones}
    for zone in zones:
        _require_reference(zone, "scenario_id", scenario_id)
        _require_reference(zone, "building_id", building_id)
        _require_reference(zone, "dwelling_id", dwelling_id)

    surfaces: list[dict[str, Any]] = []
    systems: list[dict[str, Any]] = []
    openings: list[dict[str, Any]] = []
    for zone in zones:
        zone_id = zone["zone_id"]
        for surface in zone["surfaces"]:
            surface = _require_mapping(surface, "surface")
            for field, expected in (
                ("scenario_id", scenario_id),
                ("building_id", building_id),
                ("dwelling_id", dwelling_id),
                ("zone_id", zone_id),
            ):
                _require_reference(surface, field, expected)
            surfaces.append(surface)

            surface_openings = [
                _require_mapping(item, "opening") for item in surface["openings"]
            ]
            if (
                sum(float(item["area_m2"]) for item in surface_openings)
                > float(surface["area_m2"]) + 1e-12
            ):
                raise CanonicalContractError(
                    f"Openings exceed area of surface {surface['surface_id']!r}."
                )
            for opening in surface_openings:
                for field, expected in (
                    ("scenario_id", scenario_id),
                    ("building_id", building_id),
                    ("dwelling_id", dwelling_id),
                    ("zone_id", zone_id),
                    ("surface_id", surface["surface_id"]),
                    ("boundary_type", surface["boundary_type"]),
                    ("adjacent_zone_id", surface["adjacent_zone_id"]),
                ):
                    _require_reference(opening, field, expected)
                if opening["boundary_type"] != "exterior":
                    raise CanonicalContractError(
                        "Version 1 openings must connect a zone to exterior."
                    )
                if float(opening["openable_area_m2"]) > float(opening["area_m2"]):
                    raise CanonicalContractError(
                        f"Opening {opening['opening_id']!r} openable area exceeds area."
                    )
                openings.append(opening)

        for system in zone["systems"]:
            system = _require_mapping(system, "system")
            for field, expected in (
                ("scenario_id", scenario_id),
                ("building_id", building_id),
                ("dwelling_id", dwelling_id),
                ("zone_id", zone_id),
            ):
                _require_reference(system, field, expected)
            systems.append(system)

    surface_by_id = {surface["surface_id"]: surface for surface in surfaces}
    for surface in surfaces:
        boundary_type = surface["boundary_type"]
        adjacent_zone_id = surface["adjacent_zone_id"]
        paired_surface_id = surface["paired_surface_id"]
        if boundary_type == "exterior":
            if adjacent_zone_id is not None or paired_surface_id is not None:
                raise CanonicalContractError(
                    f"Exterior surface {surface['surface_id']!r} cannot have a zone pair."
                )
        elif boundary_type == "interzone":
            if (
                adjacent_zone_id not in zone_by_id
                or adjacent_zone_id == surface["zone_id"]
            ):
                raise CanonicalContractError(
                    f"Interzone surface {surface['surface_id']!r} has invalid adjacent zone."
                )
            if paired_surface_id not in surface_by_id:
                raise CanonicalContractError(
                    f"Interzone surface {surface['surface_id']!r} has no paired surface."
                )
            if surface["openings"]:
                raise CanonicalContractError(
                    "Version 1 interzone surfaces cannot contain openings."
                )
        else:
            raise CanonicalContractError(f"Unknown boundary_type {boundary_type!r}.")

    occupants = [_require_mapping(item, "occupant") for item in scenario["occupants"]]
    for occupant in occupants:
        for field, expected in (
            ("scenario_id", scenario_id),
            ("building_id", building_id),
            ("dwelling_id", dwelling_id),
        ):
            _require_reference(occupant, field, expected)
        for field in ("home_zone_id", "sleep_zone_id"):
            if occupant[field] not in zone_by_id:
                raise CanonicalContractError(
                    f"Occupant {occupant['occupant_id']!r} references unknown {field}."
                )
        entries = sorted(
            occupant["location_schedule"], key=lambda item: item["start_timestep_index"]
        )
        if (
            not entries
            or entries[0]["start_timestep_index"] != 0
            or entries[-1]["end_timestep_index"] != clock.n_timesteps
        ):
            raise CanonicalContractError(
                "Occupant schedule must cover the full period."
            )
        previous_end = 0
        for entry in entries:
            if entry["start_timestep_index"] != previous_end:
                raise CanonicalContractError("Occupant schedule has a gap or overlap.")
            if entry["zone_id"] not in zone_by_id:
                raise CanonicalContractError(
                    "Occupant schedule references an unknown zone."
                )
            previous_end = entry["end_timestep_index"]

    for weather_state in weather_series:
        _require_reference(weather_state, "scenario_id", scenario_id)

    nodes: list[dict[str, Any]] = [
        {
            "node_id": EXTERIOR_NODE_ID,
            "node_type": "exterior",
            "scenario_id": scenario_id,
            "building_id": None,
            "dwelling_id": None,
            "zone_id": None,
            "volume_m3": None,
            "provenance": {
                "node_id": _graph_provenance(
                    "derived", [], "reserved canonical exterior node"
                )
            },
        }
    ]
    for zone_id in registry.ids("zone"):
        zone = zone_by_id[zone_id]
        nodes.append(
            {
                "node_id": zone_id,
                "node_type": "zone",
                "scenario_id": scenario_id,
                "building_id": building_id,
                "dwelling_id": dwelling_id,
                "zone_id": zone_id,
                "volume_m3": float(zone["volume_m3"]),
                "provenance": {
                    "volume_m3": _graph_provenance(
                        "provided",
                        [_source_path("zone", zone_id, "volume_m3")],
                        "copied without conversion",
                    )
                },
            }
        )
    nodes = [dict(node, node_index=index) for index, node in enumerate(nodes)]

    connections: list[dict[str, Any]] = []
    processed_interzone: set[str] = set()
    for surface in sorted(surfaces, key=lambda item: item["surface_id"]):
        surface_id = surface["surface_id"]
        zone_id = surface["zone_id"]
        if surface["boundary_type"] == "interzone":
            if surface_id in processed_interzone:
                continue
            pair_id = surface["paired_surface_id"]
            pair = surface_by_id[pair_id]
            if (
                pair["boundary_type"] != "interzone"
                or pair["paired_surface_id"] != surface_id
                or pair["zone_id"] != surface["adjacent_zone_id"]
                or pair["adjacent_zone_id"] != zone_id
            ):
                raise CanonicalContractError(
                    f"Interzone surface pair {surface_id!r}/{pair_id!r} is not reciprocal."
                )
            for field in (
                "area_m2",
                "thermal_transmittance_w_m2_k",
                "thermal_bridge_conductance_w_k",
                "heat_capacity_j_k",
                "tilt_deg",
                "airflow_opening_area_m2",
                "airflow_open_fraction",
                "airflow_opening_height_m",
                "airflow_discharge_coefficient",
                "airflow_assumed_velocity_m_s",
            ):
                if not _close(surface.get(field, 0.0), pair.get(field, 0.0)):
                    raise CanonicalContractError(
                        f"Interzone pair {surface_id!r}/{pair_id!r} disagrees on {field}."
                    )
            if surface.get("airflow_model", "none") != pair.get(
                "airflow_model", "none"
            ):
                raise CanonicalContractError(
                    f"Interzone pair {surface_id!r}/{pair_id!r} disagrees on airflow_model."
                )
            expected_pair_azimuth = (float(surface["azimuth_deg"]) + 180.0) % 360.0
            if not _close(expected_pair_azimuth, pair["azimuth_deg"]):
                raise CanonicalContractError(
                    f"Interzone pair {surface_id!r}/{pair_id!r} has invalid orientation."
                )

            surface_ids = sorted((surface_id, pair_id))
            owner_zone_ids = sorted((zone_id, pair["zone_id"]))
            connections.append(
                {
                    "connection_id": f"surface_pair:{surface_ids[0]}|{surface_ids[1]}",
                    "connection_type": "surface",
                    "boundary_type": "interzone",
                    "directionality": "bidirectional",
                    "source_node_id": owner_zone_ids[0],
                    "target_node_id": owner_zone_ids[1],
                    "owner_zone_ids": owner_zone_ids,
                    "surface_ids": surface_ids,
                    "opening_ids": [],
                    "gross_area_m2": float(surface["area_m2"]),
                    "net_opaque_area_m2": float(surface["area_m2"]),
                    "thermal_transmittance_w_m2_k": float(
                        surface["thermal_transmittance_w_m2_k"]
                    ),
                    "heat_capacity_j_k": float(surface["heat_capacity_j_k"]),
                    "thermal_bridge_conductance_w_k": float(
                        surface.get("thermal_bridge_conductance_w_k", 0.0)
                    ),
                    "azimuth_deg": None,
                    "tilt_deg": None,
                    "openable_area_m2": None,
                    "solar_transmittance_fraction": None,
                    "visible_transmittance_fraction": None,
                    "external_boundary_id": None,
                    "airflow_opening_area_m2": float(
                        surface.get("airflow_opening_area_m2", 0.0)
                    ),
                    "airflow_open_fraction": float(
                        surface.get("airflow_open_fraction", 0.0)
                    ),
                    "airflow_model": surface.get("airflow_model", "none"),
                    "airflow_opening_height_m": float(
                        surface.get("airflow_opening_height_m", 0.0)
                    ),
                    "airflow_discharge_coefficient": float(
                        surface.get("airflow_discharge_coefficient", 0.0)
                    ),
                    "airflow_assumed_velocity_m_s": float(
                        surface.get("airflow_assumed_velocity_m_s", 0.0)
                    ),
                    "provenance": {
                        "connection_id": _graph_provenance(
                            "derived",
                            [
                                _source_path("surface", item, "paired_surface_id")
                                for item in surface_ids
                            ],
                            "sorted reciprocal surface IDs",
                        ),
                        "net_opaque_area_m2": _graph_provenance(
                            "provided",
                            [
                                _source_path("surface", item, "area_m2")
                                for item in surface_ids
                            ],
                            "paired areas validated equal; no interzone openings",
                        ),
                    },
                }
            )
            processed_interzone.update(surface_ids)
            continue

        opening_items = sorted(surface["openings"], key=lambda item: item["opening_id"])
        if opening_items and (surface.get("external_boundary_id") or "outdoor_air") != "outdoor_air":
            raise CanonicalContractError(
                "Version 1 openings can only connect to the outdoor_air boundary."
            )
        opening_area = sum(float(item["area_m2"]) for item in opening_items)
        connections.append(
            {
                "connection_id": f"surface:{surface_id}",
                "connection_type": "surface",
                "boundary_type": "exterior",
                "directionality": "bidirectional",
                "source_node_id": zone_id,
                "target_node_id": EXTERIOR_NODE_ID,
                "owner_zone_ids": [zone_id],
                "surface_ids": [surface_id],
                "opening_ids": [item["opening_id"] for item in opening_items],
                "gross_area_m2": float(surface["area_m2"]),
                "net_opaque_area_m2": float(surface["area_m2"]) - opening_area,
                "thermal_transmittance_w_m2_k": float(
                    surface["thermal_transmittance_w_m2_k"]
                ),
                "heat_capacity_j_k": float(surface["heat_capacity_j_k"]),
                "thermal_bridge_conductance_w_k": float(
                    surface.get("thermal_bridge_conductance_w_k", 0.0)
                ),
                "azimuth_deg": float(surface["azimuth_deg"]),
                "tilt_deg": float(surface["tilt_deg"]),
                "openable_area_m2": None,
                "solar_transmittance_fraction": None,
                "visible_transmittance_fraction": None,
                "external_boundary_id": surface.get("external_boundary_id")
                or "outdoor_air",
                "airflow_opening_area_m2": 0.0,
                "airflow_open_fraction": 0.0,
                "airflow_model": "none",
                "airflow_opening_height_m": 0.0,
                "airflow_discharge_coefficient": 0.0,
                "airflow_assumed_velocity_m_s": 0.0,
                "provenance": {
                    "net_opaque_area_m2": _graph_provenance(
                        "derived",
                        [_source_path("surface", surface_id, "area_m2")]
                        + [
                            _source_path("opening", item["opening_id"], "area_m2")
                            for item in opening_items
                        ],
                        "surface area minus sum of opening areas",
                    )
                },
            }
        )

        for opening in opening_items:
            opening_id = opening["opening_id"]
            connections.append(
                {
                    "connection_id": f"opening:{opening_id}",
                    "connection_type": "opening",
                    "boundary_type": "exterior",
                    "directionality": "bidirectional",
                    "source_node_id": zone_id,
                    "target_node_id": EXTERIOR_NODE_ID,
                    "owner_zone_ids": [zone_id],
                    "surface_ids": [surface_id],
                    "opening_ids": [opening_id],
                    "gross_area_m2": float(opening["area_m2"]),
                    "net_opaque_area_m2": None,
                    "thermal_transmittance_w_m2_k": float(
                        opening["thermal_transmittance_w_m2_k"]
                    ),
                    "heat_capacity_j_k": None,
                    "thermal_bridge_conductance_w_k": float(
                        opening.get("thermal_bridge_conductance_w_k", 0.0)
                    ),
                    "azimuth_deg": float(surface["azimuth_deg"]),
                    "tilt_deg": float(surface["tilt_deg"]),
                    "openable_area_m2": float(opening["openable_area_m2"]),
                    "solar_transmittance_fraction": float(
                        opening["solar_transmittance_fraction"]
                    ),
                    "visible_transmittance_fraction": float(
                        opening["visible_transmittance_fraction"]
                    ),
                    "solar_shading_factor": float(
                        opening.get("solar_shading_factor", 1.0)
                    ),
                    "external_boundary_id": surface.get("external_boundary_id")
                    or "outdoor_air",
                    "airflow_opening_area_m2": 0.0,
                    "airflow_open_fraction": 0.0,
                    "airflow_model": "none",
                    "airflow_opening_height_m": 0.0,
                    "airflow_discharge_coefficient": 0.0,
                    "airflow_assumed_velocity_m_s": 0.0,
                    "provenance": {
                        "azimuth_deg": _graph_provenance(
                            "derived",
                            [_source_path("surface", surface_id, "azimuth_deg")],
                            "inherited from owner surface",
                        ),
                        "tilt_deg": _graph_provenance(
                            "derived",
                            [_source_path("surface", surface_id, "tilt_deg")],
                            "inherited from owner surface",
                        ),
                    },
                }
            )

    connections = sorted(connections, key=lambda item: item["connection_id"])
    connections = [
        dict(connection, connection_index=index)
        for index, connection in enumerate(connections)
    ]

    compiled_systems = [
        {
            "system_index": registry.index_for("system", system_id),
            "system_id": system_id,
            "scenario_id": scenario_id,
            "building_id": building_id,
            "dwelling_id": dwelling_id,
            "zone_id": next(
                item["zone_id"] for item in systems if item["system_id"] == system_id
            ),
            "system_type": next(
                item["system_type"]
                for item in systems
                if item["system_id"] == system_id
            ),
        }
        for system_id in registry.ids("system")
    ]

    graph: dict[str, Any] = {
        "compiled_graph_version": "1.0.0",
        "scenario_schema_version": scenario.get("schema_version"),
        "scenario_id": scenario_id,
        "id_registry": registry.to_dict(),
        "time_axis": clock.to_dict(),
        "geometry_configuration": geometry,
        "nodes": nodes,
        "connections": connections,
        "systems": compiled_systems,
    }
    graph["graph_sha256"] = _graph_digest(graph)
    validate_compiled_graph(graph)
    return graph


def validate_compiled_graph(graph: dict[str, Any]) -> bool:
    """Validate structural invariants and digest of a compiled graph."""

    graph = _require_mapping(graph, "compiled graph")
    nodes = _require_list(graph.get("nodes"), "compiled graph nodes")
    connections = _require_list(graph.get("connections"), "compiled graph connections")
    systems = _require_list(graph.get("systems"), "compiled graph systems")

    node_ids = [node["node_id"] for node in nodes]
    if not node_ids or node_ids[0] != EXTERIOR_NODE_ID:
        raise CanonicalContractError("Compiled graph must start with exterior node.")
    if len(node_ids) != len(set(node_ids)):
        raise CanonicalContractError("Compiled graph contains duplicate node IDs.")
    if [node["node_index"] for node in nodes] != list(range(len(nodes))):
        raise CanonicalContractError("Compiled graph node indices are not contiguous.")
    if node_ids[1:] != sorted(node_ids[1:]):
        raise CanonicalContractError(
            "Compiled zone nodes are not deterministically ordered."
        )

    connection_ids = [item["connection_id"] for item in connections]
    if connection_ids != sorted(connection_ids) or len(connection_ids) != len(
        set(connection_ids)
    ):
        raise CanonicalContractError(
            "Compiled connection IDs must be unique and deterministically ordered."
        )
    if [item["connection_index"] for item in connections] != list(
        range(len(connections))
    ):
        raise CanonicalContractError("Connection indices are not contiguous.")

    node_id_set = set(node_ids)
    for connection in connections:
        source = connection["source_node_id"]
        target = connection["target_node_id"]
        if source not in node_id_set or target not in node_id_set:
            raise CanonicalContractError(
                f"Connection {connection['connection_id']!r} is orphaned."
            )
        if source == target:
            raise CanonicalContractError(
                f"Connection {connection['connection_id']!r} is self-connected."
            )
        if connection["directionality"] != "bidirectional":
            raise CanonicalContractError("Version 1 connections must be bidirectional.")
        if connection["boundary_type"] == "exterior" and target != EXTERIOR_NODE_ID:
            raise CanonicalContractError(
                "Exterior connection must target exterior node."
            )
        if connection["boundary_type"] == "interzone" and EXTERIOR_NODE_ID in {
            source,
            target,
        }:
            raise CanonicalContractError("Interzone connection cannot target exterior.")
        if not set(connection["owner_zone_ids"]) <= node_id_set - {EXTERIOR_NODE_ID}:
            raise CanonicalContractError("Connection has an unknown owner zone.")

    system_ids = [item["system_id"] for item in systems]
    if system_ids != sorted(system_ids):
        raise CanonicalContractError(
            "Compiled systems are not deterministically ordered."
        )
    if any(item["zone_id"] not in node_id_set for item in systems):
        raise CanonicalContractError("Compiled system has an unknown owner zone.")

    supplied_digest = graph.get("graph_sha256")
    payload = {key: value for key, value in graph.items() if key != "graph_sha256"}
    if supplied_digest != _graph_digest(payload):
        raise CanonicalContractError(
            "Compiled graph SHA-256 digest does not match payload."
        )
    return True


def serialize_compiled_graph(graph: dict[str, Any]) -> str:
    """Return canonical JSON after validating the compiled graph."""

    validate_compiled_graph(graph)
    return _canonical_json(graph)
