"""Strict, checksum-backed provenance registry for scientific validation data."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)

from nexusep.jsonc import loads_strict_json

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    ),
]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
TimezoneText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^(UTC|not_applicable|[A-Za-z_]+/[A-Za-z0-9_+./-]+|[+-][0-9]{2}:[0-9]{2})$",
    ),
]
ClaimId = Literal[
    "SOLAR-1",
    "WEATHER-1",
    "THERMAL-1",
    "AIRFLOW-1",
    "CO2-1",
    "MOIST-1",
    "HVAC-1",
    "DAYLIGHT-1",
    "OCC-1",
    "ACOUST-0",
]
MAX_TRACKED_FIXTURE_BYTES = 1_048_576


class RegistryValidationError(ValueError):
    """Raised when registry lineage or a referenced checksum is invalid."""


class RegistryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FileChecksum(RegistryModel):
    file_id: Identifier
    path: NonEmptyText
    sha256: Sha256
    byte_size: Annotated[int, Field(ge=0)]

    @field_validator("sha256")
    @classmethod
    def reject_placeholder_checksum(cls, value: str) -> str:
        if value == "0" * 64:
            raise ValueError("placeholder SHA-256 values are not permitted")
        return value


class DoiRecord(RegistryModel):
    status: Literal["assigned", "not_assigned", "unknown"]
    value: NonEmptyText | None
    absence_reason: NonEmptyText | None

    @model_validator(mode="after")
    def validate_status(self) -> DoiRecord:
        if self.status == "assigned":
            if self.value is None or not self.value.lower().startswith("10."):
                raise ValueError("assigned DOI must provide a value beginning with '10.'")
            if self.absence_reason is not None:
                raise ValueError("assigned DOI cannot have an absence_reason")
        elif self.value is not None:
            raise ValueError("DOI value must be null unless status is assigned")
        elif self.absence_reason is None:
            raise ValueError("missing DOI must have an explicit absence_reason")
        return self


class LicenseRecord(RegistryModel):
    name: NonEmptyText
    spdx_id: NonEmptyText | None
    terms_url: HttpUrl


class MeasurementUncertainty(RegistryModel):
    status: Literal["reported", "estimated", "not_reported", "not_applicable"]
    description: NonEmptyText
    by_variable: dict[NonEmptyText, NonEmptyText]


class PermittedUse(RegistryModel):
    purpose: NonEmptyText
    redistribution: Literal[
        "prohibited", "metadata_only", "derived_only", "permitted"
    ]
    commercial_use: bool | None
    citation_required: bool
    notes: NonEmptyText


class PreprocessingStep(RegistryModel):
    step_id: Identifier
    description: NonEmptyText
    script_path: NonEmptyText
    script_sha256: Sha256
    command: NonEmptyText
    input_raw_file_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    output_fixtures: tuple[FileChecksum, ...]


class DataSourceRecord(RegistryModel):
    manifest_version: Literal["1.0.0"]
    source_id: Identifier
    title: NonEmptyText
    version: NonEmptyText
    publisher: NonEmptyText
    doi: DoiRecord
    license: LicenseRecord
    download_url: HttpUrl
    retrieval_date: date
    raw_files: Annotated[tuple[FileChecksum, ...], Field(min_length=1)]
    units: Annotated[dict[NonEmptyText, NonEmptyText], Field(min_length=1)]
    timezone: TimezoneText
    measurement_uncertainty: MeasurementUncertainty
    known_gaps: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    preprocessing: Annotated[tuple[PreprocessingStep, ...], Field(min_length=1)]
    permitted_use: PermittedUse
    targeted_models: Annotated[tuple[ClaimId, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_internal_references(self) -> DataSourceRecord:
        raw_ids = [item.file_id for item in self.raw_files]
        if len(raw_ids) != len(set(raw_ids)):
            raise ValueError("raw file_id values must be unique within a source")
        step_ids = [item.step_id for item in self.preprocessing]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("preprocessing step_id values must be unique")
        for step in self.preprocessing:
            unknown = sorted(set(step.input_raw_file_ids) - set(raw_ids))
            if unknown:
                raise ValueError(
                    f"preprocessing step {step.step_id!r} references unknown raw files: "
                    f"{unknown}"
                )
        if len(self.targeted_models) != len(set(self.targeted_models)):
            raise ValueError("targeted_models cannot contain duplicates")
        if self.permitted_use.redistribution in {"prohibited", "metadata_only"}:
            redistributed = [
                fixture.path
                for step in self.preprocessing
                for fixture in step.output_fixtures
            ]
            if redistributed:
                raise ValueError(
                    "derived fixtures cannot be registered when redistribution "
                    f"is {self.permitted_use.redistribution}: {redistributed}"
                )
        return self


class CodeReference(RegistryModel):
    path: NonEmptyText
    sha256: Sha256
    command: NonEmptyText


class ScientificResultRecord(RegistryModel):
    manifest_version: Literal["1.0.0"]
    result_id: Identifier
    title: NonEmptyText
    validation_category: Literal[
        "comparative_validation",
        "empirical_validation",
        "calibration",
        "blind_validation",
    ]
    created_on: date
    targeted_models: Annotated[tuple[ClaimId, ...], Field(min_length=1)]
    source_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    analysis_code: Annotated[tuple[CodeReference, ...], Field(min_length=1)]
    report_path: NonEmptyText
    result_artifacts: Annotated[tuple[FileChecksum, ...], Field(min_length=1)]
    numerical_tolerances: Annotated[
        dict[NonEmptyText, NonEmptyText], Field(min_length=1)
    ]
    known_deviations: tuple[NonEmptyText, ...]

    @model_validator(mode="after")
    def validate_unique_references(self) -> ScientificResultRecord:
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("source_ids cannot contain duplicates")
        if len(self.targeted_models) != len(set(self.targeted_models)):
            raise ValueError("targeted_models cannot contain duplicates")
        return self


class RegistryIndex(RegistryModel):
    registry_version: Literal["1.0.0"]
    validation_category: Literal["verification"]
    source_manifests: tuple[NonEmptyText, ...]
    scientific_result_manifests: tuple[NonEmptyText, ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_model(path: Path, model_type: type[RegistryModel]) -> RegistryModel:
    try:
        payload = loads_strict_json(
            path.read_text(encoding="utf-8"), source=path, jsonc=False
        )
        return model_type.model_validate(payload)
    except Exception as exc:
        raise RegistryValidationError(f"invalid registry document {path}: {exc}") from exc


def _repository_path(repository_root: Path, relative_path: str) -> Path:
    pure_path = PurePosixPath(relative_path)
    if pure_path.is_absolute() or ".." in pure_path.parts or "\\" in relative_path:
        raise RegistryValidationError(
            f"registry paths must be repository-relative POSIX paths: {relative_path!r}"
        )
    root = repository_root.resolve()
    resolved = root.joinpath(*pure_path.parts).resolve()
    if resolved != root and root not in resolved.parents:
        raise RegistryValidationError(f"registry path escapes repository: {relative_path}")
    return resolved


def _require_file(repository_root: Path, relative_path: str, purpose: str) -> Path:
    path = _repository_path(repository_root, relative_path)
    if not path.is_file():
        raise RegistryValidationError(f"missing {purpose}: {relative_path}")
    return path


def _verify_checksum(path: Path, expected_sha256: str, purpose: str) -> None:
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise RegistryValidationError(
            f"{purpose} checksum mismatch for {path}: expected {expected_sha256}, "
            f"got {actual}"
        )


def _validate_source_files(
    source: DataSourceRecord,
    repository_root: Path,
    *,
    verify_raw_files: bool,
) -> tuple[set[str], set[str]]:
    registered_fixtures: set[str] = set()
    registered_code: set[str] = set()
    for raw_file in source.raw_files:
        raw_path = _repository_path(repository_root, raw_file.path)
        if not raw_file.path.startswith("data/raw/validation/"):
            raise RegistryValidationError(
                f"raw file {raw_file.file_id!r} must live below data/raw/validation/"
            )
        if verify_raw_files:
            if not raw_path.is_file():
                raise RegistryValidationError(f"missing raw file: {raw_file.path}")
            if raw_path.stat().st_size != raw_file.byte_size:
                raise RegistryValidationError(
                    f"raw file size mismatch for {raw_file.path}: expected "
                    f"{raw_file.byte_size}, got {raw_path.stat().st_size}"
                )
            _verify_checksum(raw_path, raw_file.sha256, "raw file")

    for step in source.preprocessing:
        script = _require_file(
            repository_root, step.script_path, "preprocessing script"
        )
        if not step.script_path.startswith("scripts/validation_data/"):
            raise RegistryValidationError(
                "preprocessing scripts must live below scripts/validation_data/"
            )
        _verify_checksum(script, step.script_sha256, "preprocessing script")
        registered_code.add(step.script_path)
        for fixture in step.output_fixtures:
            if not fixture.path.startswith("data/validation/fixtures/"):
                raise RegistryValidationError(
                    "derived fixtures must live below data/validation/fixtures/"
                )
            if fixture.byte_size > MAX_TRACKED_FIXTURE_BYTES:
                raise RegistryValidationError(
                    f"derived fixture exceeds {MAX_TRACKED_FIXTURE_BYTES} bytes: "
                    f"{fixture.path}"
                )
            fixture_path = _require_file(
                repository_root, fixture.path, "derived fixture"
            )
            if fixture_path.stat().st_size != fixture.byte_size:
                raise RegistryValidationError(
                    f"derived fixture size mismatch for {fixture.path}"
                )
            _verify_checksum(fixture_path, fixture.sha256, "derived fixture")
            registered_fixtures.add(fixture.path)
    return registered_fixtures, registered_code


def _tracked_files_below(repository_root: Path, relative_directory: str) -> set[str]:
    directory = _repository_path(repository_root, relative_directory)
    if not directory.exists():
        return set()
    return {
        path.relative_to(repository_root).as_posix()
        for path in directory.rglob("*")
        if path.is_file()
        and path.name.lower() != "readme.md"
        and path.name != ".gitkeep"
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    }


def validate_registry(
    registry_path: str | Path,
    *,
    repository_root: str | Path | None = None,
    verify_raw_files: bool = False,
) -> RegistryIndex:
    """Validate source lineage, cross-references, and committed-file checksums."""

    registry_path = Path(registry_path).resolve()
    root = (
        Path(repository_root).resolve()
        if repository_root is not None
        else registry_path.parents[2]
    )
    index = _read_model(registry_path, RegistryIndex)
    assert isinstance(index, RegistryIndex)

    if len(index.source_manifests) != len(set(index.source_manifests)):
        raise RegistryValidationError("source_manifests contains duplicate paths")
    if len(index.scientific_result_manifests) != len(
        set(index.scientific_result_manifests)
    ):
        raise RegistryValidationError(
            "scientific_result_manifests contains duplicate paths"
        )

    sources: dict[str, DataSourceRecord] = {}
    registered_fixtures: set[str] = set()
    registered_code: set[str] = set()
    for relative_path in index.source_manifests:
        if not relative_path.startswith("data/validation/sources/"):
            raise RegistryValidationError(
                "source manifests must live below data/validation/sources/"
            )
        manifest_path = _require_file(root, relative_path, "source manifest")
        source = _read_model(manifest_path, DataSourceRecord)
        assert isinstance(source, DataSourceRecord)
        if source.source_id in sources:
            raise RegistryValidationError(f"duplicate source_id: {source.source_id}")
        if source.retrieval_date > datetime.now(UTC).date():
            raise RegistryValidationError(
                f"source {source.source_id} has a future retrieval_date"
            )
        source_fixtures, source_code = _validate_source_files(
            source, root, verify_raw_files=verify_raw_files
        )
        registered_fixtures.update(source_fixtures)
        registered_code.update(source_code)
        sources[source.source_id] = source

    registered_reports: set[str] = set()
    result_ids: set[str] = set()
    for relative_path in index.scientific_result_manifests:
        if not relative_path.startswith("data/validation/results/"):
            raise RegistryValidationError(
                "scientific result manifests must live below data/validation/results/"
            )
        manifest_path = _require_file(root, relative_path, "result manifest")
        result = _read_model(manifest_path, ScientificResultRecord)
        assert isinstance(result, ScientificResultRecord)
        if result.result_id in result_ids:
            raise RegistryValidationError(f"duplicate result_id: {result.result_id}")
        result_ids.add(result.result_id)
        missing_sources = sorted(set(result.source_ids) - set(sources))
        if missing_sources:
            raise RegistryValidationError(
                f"result {result.result_id} references unregistered sources: "
                f"{missing_sources}"
            )
        source_claims = {
            claim
            for source_id in result.source_ids
            for claim in sources[source_id].targeted_models
        }
        unsupported_claims = sorted(set(result.targeted_models) - source_claims)
        if unsupported_claims:
            raise RegistryValidationError(
                f"result {result.result_id} targets models not covered by its "
                f"sources: {unsupported_claims}"
            )
        report = _require_file(root, result.report_path, "scientific report")
        if not result.report_path.startswith("docs/validation/results/"):
            raise RegistryValidationError(
                "scientific result reports must live below docs/validation/results/"
            )
        registered_reports.add(result.report_path)
        for code in result.analysis_code:
            if not code.path.startswith("scripts/validation_data/"):
                raise RegistryValidationError(
                    "scientific analysis code must live below "
                    "scripts/validation_data/"
                )
            code_path = _require_file(root, code.path, "analysis code")
            _verify_checksum(code_path, code.sha256, "analysis code")
            registered_code.add(code.path)
        for artifact in result.result_artifacts:
            if not artifact.path.startswith("data/validation/fixtures/"):
                raise RegistryValidationError(
                    "compact result artifacts must live below "
                    "data/validation/fixtures/"
                )
            if artifact.byte_size > MAX_TRACKED_FIXTURE_BYTES:
                raise RegistryValidationError(
                    f"result artifact exceeds {MAX_TRACKED_FIXTURE_BYTES} bytes: "
                    f"{artifact.path}"
                )
            artifact_path = _require_file(root, artifact.path, "result artifact")
            if artifact_path.stat().st_size != artifact.byte_size:
                raise RegistryValidationError(
                    f"result artifact size mismatch for {artifact.path}"
                )
            _verify_checksum(artifact_path, artifact.sha256, "result artifact")
            registered_fixtures.add(artifact.path)
        opening = "\n".join(report.read_text(encoding="utf-8").splitlines()[:12])
        required_report_lines = (
            "Validation category: "
            + result.validation_category.replace("_", " "),
            "Model claim(s): " + ", ".join(result.targeted_models),
            "Data source IDs: " + ", ".join(result.source_ids),
        )
        missing_report_lines = [
            line for line in required_report_lines if line not in opening
        ]
        if missing_report_lines:
            raise RegistryValidationError(
                f"report {result.report_path} has incomplete provenance header: "
                f"{missing_report_lines}"
            )

    result_docs = {
        path.relative_to(root).as_posix()
        for path in (root / "docs/validation/results").rglob("*.md")
        if path.name.lower() != "readme.md"
    }
    unregistered_reports = sorted(result_docs - registered_reports)
    if unregistered_reports:
        raise RegistryValidationError(
            f"scientific reports lack result manifests: {unregistered_reports}"
        )

    indexed_source_manifests = set(index.source_manifests)
    unindexed_source_manifests = sorted(
        _tracked_files_below(root, "data/validation/sources")
        - indexed_source_manifests
    )
    if unindexed_source_manifests:
        raise RegistryValidationError(
            f"source manifests are not indexed: {unindexed_source_manifests}"
        )
    indexed_result_manifests = set(index.scientific_result_manifests)
    unindexed_result_manifests = sorted(
        _tracked_files_below(root, "data/validation/results")
        - indexed_result_manifests
    )
    if unindexed_result_manifests:
        raise RegistryValidationError(
            f"result manifests are not indexed: {unindexed_result_manifests}"
        )
    unregistered_fixtures = sorted(
        _tracked_files_below(root, "data/validation/fixtures")
        - registered_fixtures
    )
    if unregistered_fixtures:
        raise RegistryValidationError(
            f"derived fixtures lack manifest lineage: {unregistered_fixtures}"
        )
    unregistered_code = sorted(
        _tracked_files_below(root, "scripts/validation_data") - registered_code
    )
    if unregistered_code:
        raise RegistryValidationError(
            f"validation-data code lacks manifest lineage: {unregistered_code}"
        )
    return index


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check", help="validate registry lineage")
    check.add_argument(
        "registry", nargs="?", default="data/validation/registry.json"
    )
    check.add_argument("--repository-root", default=None)
    check.add_argument("--verify-raw", action="store_true")
    subparsers.add_parser("schema", help="print JSON Schema for source manifests")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "schema":
        print(json.dumps(DataSourceRecord.model_json_schema(), indent=2))
        return 0
    validate_registry(
        args.registry,
        repository_root=args.repository_root,
        verify_raw_files=args.verify_raw,
    )
    print(f"validation-data registry OK: {Path(args.registry)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
