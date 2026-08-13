"""Strict canonical JSON/JSONC scenario loader."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from nexusep.jsonc import DuplicateJSONKeyError, loads_strict_json, strip_jsonc

from nexusep.scenarios.validation import (
    FieldIssue,
    ScenarioValidationError,
    issues_from_pydantic,
    validate_scenario,
)
from nexusep.schema import compile_physics_graph, serialize_compiled_graph
from nexusep.schema.common import TransformationRecord
from nexusep.schema.compiler import CanonicalClock, CanonicalContractError
from nexusep.schema.scenario import ScenarioV1

SUPPORTED_SCHEMA_VERSIONS = {"1.0.0": ScenarioV1}


@dataclass(frozen=True)
class CanonicalScenarioBundle:
    """Controlled immutable loader result with canonical graph serialization."""

    source_path: Path
    scenario: ScenarioV1
    compiled_graph_json: str
    audit_log: tuple[TransformationRecord, ...]

    @property
    def compiled_graph(self) -> dict[str, Any]:
        """Return a fresh graph object so callers cannot mutate shared state."""

        return json.loads(self.compiled_graph_json)

    @property
    def graph_sha256(self) -> str:
        return self.compiled_graph["graph_sha256"]

    def normalized_dict(self) -> dict[str, Any]:
        return self.scenario.model_dump(mode="json")


def _strip_jsonc(text: str) -> str:
    """Remove JSONC comments and trailing commas without touching strings."""

    return strip_jsonc(text)


def _read_document(path: Path) -> Any:
    if path.suffix.casefold() not in {".json", ".jsonc"}:
        raise ScenarioValidationError(
            [
                FieldIssue(
                    "/",
                    "scenario and external weather files must use .json or .jsonc",
                    "unsupported_file_type",
                )
            ]
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ScenarioValidationError(
            [FieldIssue("/", str(error), "file_read_error")]
        ) from error
    try:
        return loads_strict_json(
            text,
            source=path,
            jsonc=path.suffix.casefold() == ".jsonc",
        )
    except DuplicateJSONKeyError as error:
        raise ScenarioValidationError(
            [
                FieldIssue(
                    error.json_pointer,
                    str(error),
                    "duplicate_json_key",
                )
            ]
        ) from error
    except (json.JSONDecodeError, ValueError) as error:
        line = getattr(error, "lineno", None)
        column = getattr(error, "colno", None)
        location = f" at line {line}, column {column}" if line and column else ""
        raise ScenarioValidationError(
            [FieldIssue("/", f"invalid JSON{location}: {error}", "json_syntax")]
        ) from error


def _record_default(
    audit: list[TransformationRecord], target_path: str, rule: str
) -> None:
    audit.append(
        TransformationRecord(kind="default", target_path=target_path, rule=rule)
    )


def _set_default(
    mapping: dict[str, Any],
    key: str,
    value: Any,
    path: str,
    audit: list[TransformationRecord],
    rule: str,
) -> None:
    if key not in mapping:
        mapping[key] = value
        _record_default(audit, f"{path}/{key}", rule)


def _resolve_path(
    raw_path: Any,
    base_directory: Path,
    target_path: str,
    audit: list[TransformationRecord],
) -> Path:
    if not isinstance(raw_path, (str, Path)):
        raise ScenarioValidationError(
            [FieldIssue(target_path, "path must be a string", "path_type")]
        )
    path = Path(raw_path)
    resolved = (
        (base_directory / path).resolve() if not path.is_absolute() else path.resolve()
    )
    if resolved != path:
        audit.append(
            TransformationRecord(
                kind="path_resolution",
                target_path=target_path,
                source_paths=(str(path),),
                rule="resolve relative to the scenario file directory",
            )
        )
    return resolved


def _clock_from_raw(raw: dict[str, Any]) -> CanonicalClock:
    period = raw.get("simulation_period")
    if not isinstance(period, dict):
        raise ScenarioValidationError(
            [
                FieldIssue(
                    "/simulation_period",
                    "simulation_period must be an object",
                    "time_contract",
                )
            ]
        )
    try:
        return CanonicalClock.from_period(period)
    except CanonicalContractError as error:
        raise ScenarioValidationError(
            [FieldIssue("/simulation_period", str(error), "time_contract")]
        ) from error


def _synthetic_weather(
    raw: dict[str, Any], clock: CanonicalClock, audit: list[TransformationRecord]
) -> list[dict[str, Any]]:
    metadata = raw.get("metadata")
    source = raw.get("weather_source")
    if not isinstance(source, dict):
        raise ScenarioValidationError(
            [
                FieldIssue(
                    "/weather_source",
                    "weather_source must be an object",
                    "weather_source_type",
                )
            ]
        )
    if not isinstance(metadata, dict) or metadata.get("scenario_kind") != "smoke_test":
        raise ScenarioValidationError(
            [
                FieldIssue(
                    "/weather_source/source_type",
                    "synthetic weather is allowed only for named smoke_test scenarios",
                    "synthetic_weather_forbidden",
                )
            ]
        )
    if (
        not metadata.get("name")
        or source.get("synthetic_profile") != "constant_mild_v1"
    ):
        raise ScenarioValidationError(
            [
                FieldIssue(
                    "/weather_source/synthetic_profile",
                    "synthetic smoke weather requires named profile constant_mild_v1",
                    "synthetic_profile_required",
                )
            ]
        )
    if raw.get("weather_series") not in (None, []):
        raise ScenarioValidationError(
            [
                FieldIssue(
                    "/weather_series",
                    "synthetic source cannot be combined with authored weather",
                    "weather_source_conflict",
                )
            ]
        )
    scenario_id = raw.get("scenario_id")
    series = [
        {
            "scenario_id": scenario_id,
            "timestep_index": index,
            "timestamp": clock.timestamp_for_index(index).isoformat(),
            "outdoor_temperature_c": 20.0,
            "relative_humidity_fraction": 0.5,
            "atmospheric_pressure_pa": 101_325.0,
            "wind_speed_m_s": 0.0,
            "wind_direction_deg": 0.0,
            "direct_normal_radiation_w_m2": 0.0,
            "diffuse_horizontal_radiation_w_m2": 0.0,
            "global_horizontal_radiation_w_m2": 0.0,
            "outdoor_co2_ppm": 420.0,
            "sky_temperature_c": 20.0,
            "outdoor_illuminance_lux": 0.0,
            "outdoor_noise_db": 35.0,
            "rain": False,
        }
        for index in range(clock.n_timesteps)
    ]
    audit.append(
        TransformationRecord(
            kind="derived",
            target_path="/weather_series",
            source_paths=("/weather_source/synthetic_profile", "/simulation_period"),
            rule="generate complete constant_mild_v1 smoke-test boundary conditions",
        )
    )
    return series


def _prepare_weather(
    raw: dict[str, Any],
    base_directory: Path,
    audit: list[TransformationRecord],
) -> None:
    source = raw.get("weather_source")
    if not isinstance(source, dict):
        return
    _set_default(
        source,
        "interpolation",
        "none",
        "/weather_source",
        audit,
        "version 1 does not interpolate weather",
    )
    _set_default(
        source,
        "allowable_derived_fields",
        ["timestamp"],
        "/weather_source",
        audit,
        "only interval-start timestamp may be derived in version 1",
    )
    if source.get("source_type") != "external_json":
        _set_default(
            source,
            "path",
            None,
            "/weather_source",
            audit,
            "non-file weather sources have no path",
        )
    if source.get("source_type") != "synthetic_smoke_test":
        _set_default(
            source,
            "synthetic_profile",
            None,
            "/weather_source",
            audit,
            "non-synthetic weather sources have no synthetic profile",
        )
    clock = _clock_from_raw(raw)
    source_type = source.get("source_type")
    if source_type == "external_json" and "path" in source:
        resolved = _resolve_path(
            source["path"], base_directory, "/weather_source/path", audit
        )
        source["path"] = str(resolved)
        weather_document = _read_document(resolved)
        if isinstance(weather_document, dict):
            weather_document = weather_document.get("weather_series")
        if not isinstance(weather_document, list):
            raise ScenarioValidationError(
                [
                    FieldIssue(
                        "/weather_source/path",
                        "external weather document must be an array or contain weather_series",
                        "weather_document_shape",
                    )
                ]
            )
        if raw.get("weather_series") not in (None, []):
            raise ScenarioValidationError(
                [
                    FieldIssue(
                        "/weather_series",
                        "external source cannot be combined with inline weather",
                        "weather_source_conflict",
                    )
                ]
            )
        raw["weather_series"] = weather_document
    elif source_type == "synthetic_smoke_test":
        raw["weather_series"] = _synthetic_weather(raw, clock, audit)

    series = raw.get("weather_series")
    if not isinstance(series, list):
        return
    allowable = set(source.get("allowable_derived_fields", []))
    for item_index, item in enumerate(series):
        if not isinstance(item, dict):
            continue
        timestep_index = item.get("timestep_index")
        if (
            "timestamp" not in item
            and "timestamp" in allowable
            and isinstance(timestep_index, int)
        ):
            try:
                item["timestamp"] = clock.timestamp_for_index(
                    timestep_index
                ).isoformat()
            except CanonicalContractError:
                continue
            audit.append(
                TransformationRecord(
                    kind="derived",
                    target_path=f"/weather_series/{item_index}/timestamp",
                    source_paths=(
                        f"/weather_series/{item_index}/timestep_index",
                        "/simulation_period",
                    ),
                    rule="derive canonical start-of-interval timestamp",
                )
            )
        for key in (
            "sky_temperature_c",
            "outdoor_illuminance_lux",
            "outdoor_noise_db",
            "rain",
        ):
            _set_default(
                item,
                key,
                None,
                f"/weather_series/{item_index}",
                audit,
                "optional weather field omitted; preserve as explicit null",
            )


def _apply_defaults_and_paths(
    raw_input: dict[str, Any], source_path: Path
) -> tuple[dict[str, Any], tuple[TransformationRecord, ...]]:
    raw = deepcopy(raw_input)
    audit: list[TransformationRecord] = []
    base_directory = source_path.parent

    metadata = raw.get("metadata")
    if isinstance(metadata, dict):
        _set_default(
            metadata,
            "description",
            "",
            "/metadata",
            audit,
            "empty description",
        )
        _set_default(metadata, "tags", [], "/metadata", audit, "no metadata tags")

    _prepare_weather(raw, base_directory, audit)

    output = raw.get("output_configuration")
    if output is None:
        output = {}
        raw["output_configuration"] = output
        _record_default(
            audit,
            "/output_configuration",
            "create explicit version 1 output configuration",
        )
    if isinstance(output, dict):
        scenario_id = raw.get("scenario_id", "scenario")
        defaults = {
            "enabled": True,
            "directory": f"artifacts/scenarios/{scenario_id}",
            "formats": ["json"],
            "include_interval_timestamps": True,
            "include_debug_graph": False,
            "fields": [],
        }
        for key, value in defaults.items():
            _set_default(
                output,
                key,
                value,
                "/output_configuration",
                audit,
                f"version 1 output default for {key}",
            )
        if "directory" in output:
            output["directory"] = str(
                _resolve_path(
                    output["directory"],
                    base_directory,
                    "/output_configuration/directory",
                    audit,
                )
            )

    return raw, tuple(audit)


def load_scenario(path: str | Path) -> CanonicalScenarioBundle:
    """Load, normalize, validate, compile, and freeze a JSON/JSONC scenario."""

    source_path = Path(path).resolve()
    document = _read_document(source_path)
    if not isinstance(document, dict):
        raise ScenarioValidationError(
            [FieldIssue("/", "scenario root must be an object", "scenario_shape")]
        )
    version = document.get("schema_version")
    model_type = (
        SUPPORTED_SCHEMA_VERSIONS.get(version) if isinstance(version, str) else None
    )
    if model_type is None:
        raise ScenarioValidationError(
            [
                FieldIssue(
                    "/schema_version",
                    f"unsupported schema version {version!r}; supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}",
                    "unsupported_schema_version",
                )
            ]
        )

    normalized, audit_log = _apply_defaults_and_paths(document, source_path)
    try:
        scenario = model_type.model_validate(normalized)
    except ValidationError as error:
        raise ScenarioValidationError(issues_from_pydantic(error)) from error
    validate_scenario(scenario)

    compiler_input = scenario.model_dump(mode="json")
    try:
        graph = compile_physics_graph(compiler_input)
    except CanonicalContractError as error:
        raise ScenarioValidationError(
            [FieldIssue("/", str(error), "graph_compilation")]
        ) from error
    return CanonicalScenarioBundle(
        source_path=source_path,
        scenario=scenario,
        compiled_graph_json=serialize_compiled_graph(graph),
        audit_log=audit_log,
    )


__all__ = [
    "SUPPORTED_SCHEMA_VERSIONS",
    "CanonicalScenarioBundle",
    "load_scenario",
]
