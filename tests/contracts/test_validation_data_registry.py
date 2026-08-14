"""Contract tests for immutable scientific-data and result provenance."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from nexusep.validation_data.registry import (
    ClaimId,
    DataSourceRecord,
    RegistryValidationError,
    validate_registry,
)

pytestmark = pytest.mark.contract
VALIDATION_CATEGORY = "verification"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _source_payload(root: Path) -> dict[str, object]:
    raw = b"timestamp,value\n2000-01-01T00:00:00Z,1.0\n"
    script = b"from pathlib import Path\n\ndef preprocess(source: Path) -> bytes:\n    return source.read_bytes()\n"
    fixture = b"timestamp,value\n2000-01-01T00:00:00Z,1.0\n"
    _write(root / "data/raw/validation/demo-source-v1/raw.csv", raw)
    _write(root / "scripts/validation_data/demo-source-v1/preprocess.py", script)
    _write(root / "data/validation/fixtures/demo-source-v1/tiny.csv", fixture)
    return {
        "manifest_version": "1.0.0",
        "source_id": "demo-source-v1",
        "title": "Demonstration measurement series",
        "version": "1.0",
        "publisher": "Example Measurement Institute",
        "doi": {
            "status": "not_assigned",
            "value": None,
            "absence_reason": "Publisher did not assign a DOI.",
        },
        "license": {
            "name": "Creative Commons Attribution 4.0 International",
            "spdx_id": "CC-BY-4.0",
            "terms_url": "https://creativecommons.org/licenses/by/4.0/",
        },
        "download_url": "https://example.invalid/demo-source-v1/raw.csv",
        "retrieval_date": "2000-01-02",
        "raw_files": [
            {
                "file_id": "raw-csv",
                "path": "data/raw/validation/demo-source-v1/raw.csv",
                "sha256": _sha256(raw),
                "byte_size": len(raw),
            }
        ],
        "units": {"timestamp": "ISO 8601", "value": "degC"},
        "timezone": "UTC",
        "measurement_uncertainty": {
            "status": "reported",
            "description": "Expanded uncertainty reported at 95% coverage.",
            "by_variable": {"value": "±0.2 degC"},
        },
        "known_gaps": ["No gaps in the redistributed one-row fixture."],
        "preprocessing": [
            {
                "step_id": "extract-tiny-fixture",
                "description": "Select the licensed one-row contract fixture.",
                "script_path": "scripts/validation_data/demo-source-v1/preprocess.py",
                "script_sha256": _sha256(script),
                "command": "python scripts/validation_data/demo-source-v1/preprocess.py",
                "input_raw_file_ids": ["raw-csv"],
                "output_fixtures": [
                    {
                        "file_id": "tiny-fixture",
                        "path": "data/validation/fixtures/demo-source-v1/tiny.csv",
                        "sha256": _sha256(fixture),
                        "byte_size": len(fixture),
                    }
                ],
            }
        ],
        "permitted_use": {
            "purpose": "Verification and empirical-validation research.",
            "redistribution": "permitted",
            "commercial_use": True,
            "citation_required": True,
            "notes": "Retain publisher attribution with derived fixtures.",
        },
        "targeted_models": ["WEATHER-1", "THERMAL-1"],
    }


def _write_source_registry(root: Path) -> tuple[Path, dict[str, object]]:
    source = _source_payload(root)
    source_path = root / "data/validation/sources/demo-source-v1.json"
    _write(source_path, json.dumps(source).encode())
    registry = {
        "registry_version": "1.0.0",
        "validation_category": "verification",
        "source_manifests": ["data/validation/sources/demo-source-v1.json"],
        "scientific_result_manifests": [],
    }
    registry_path = root / "data/validation/registry.json"
    _write(registry_path, json.dumps(registry).encode())
    (root / "docs/validation/results").mkdir(parents=True, exist_ok=True)
    return registry_path, source


def test_repository_registry_indexes_only_retrieved_or_explicitly_gated_sources() -> (
    None
):
    registry_path = REPOSITORY_ROOT / "data/validation/registry.json"
    registry = validate_registry(registry_path, repository_root=REPOSITORY_ROOT)
    assert set(registry.source_manifests) == {
        "data/validation/sources/nasa_power_hourly.json",
        "data/validation/sources/nrel_spa_2008.json",
        "data/validation/sources/nist_airnet_1989.json",
        "data/validation/sources/nist_contam_3_4_r1.json",
        "data/validation/sources/nist_qico2_tn_2213.json",
        "data/validation/sources/iea_ebc_annex_41_psr_2013.json",
        "data/validation/sources/nsrdb_api_contract.json",
        "data/validation/sources/pvgis_5_3_hourly.json",
        "data/validation/sources/energyplus_25_1_0.json",
        "data/validation/sources/nist_nzertf_reference_2017.json",
        "data/validation/sources/cie_171_2006.json",
        "data/validation/sources/bre_idmp_2001.json",
        "data/validation/sources/atus_2025_catalog.json",
        "data/validation/sources/eia_recs_2020.json",
        "data/validation/sources/iea_annex_66_2018.json",
        "data/validation/sources/iea_annex_79_2024.json",
        "data/validation/sources/ptb_absorption_database.json",
        "data/validation/sources/aalto_motus_2021.json",
        "data/validation/sources/iea_ebc_annex71_twin_houses_2020.json",
        "data/validation/sources/dbnomics_bls_atus_sleeping_2025.json",
        "data/validation/sources/bls_atus_2023_microdata.json",
    }
    assert set(registry.scientific_result_manifests) == {
        "data/validation/results/energyplus_ideal_loads_25_1_0.json",
        "data/validation/results/annex71_thermal_transfer_v1.json",
        "data/validation/results/atus_aggregate_sleep_alternative_v1.json",
        "data/validation/results/annex71_production_transfer_v1.json",
        "data/validation/results/annex71_energy_path_audit_v1.json",
        "data/validation/results/annex71_structural_diagnostics_v1.json",
        "data/validation/results/annex71_physical_runtime_error_v4.json",
        "data/validation/results/annex71_large_opening_runtime_error_v5.json",
        "data/validation/results/annex71_boundary_runtime_error_v6.json",
        "data/validation/results/annex71_sky_boundary_runtime_error_v7.json",
        "data/validation/results/atus_population_holdout_v1.json",
    }


def test_registry_model_claim_ids_match_the_published_claim_matrix() -> None:
    matrix = (REPOSITORY_ROOT / "docs/validation/model_claim_matrix.md").read_text(
        encoding="utf-8"
    )
    documented = set(re.findall(r"\| ([A-Z0-9]+-[0-9]+) ", matrix))
    assert documented == set(get_args(ClaimId))


def test_source_manifest_requires_every_phase_4_2_field() -> None:
    required = set(DataSourceRecord.model_json_schema()["required"])
    assert {
        "title",
        "version",
        "publisher",
        "doi",
        "license",
        "download_url",
        "retrieval_date",
        "raw_files",
        "units",
        "timezone",
        "measurement_uncertainty",
        "known_gaps",
        "preprocessing",
        "permitted_use",
        "targeted_models",
    } <= required


@pytest.mark.parametrize(
    "field_name",
    (
        "title",
        "version",
        "publisher",
        "doi",
        "license",
        "download_url",
        "retrieval_date",
        "raw_files",
        "units",
        "timezone",
        "measurement_uncertainty",
        "known_gaps",
        "preprocessing",
        "permitted_use",
        "targeted_models",
    ),
)
def test_incomplete_source_records_are_rejected(
    field_name: str, tmp_path: Path
) -> None:
    payload = _source_payload(tmp_path)
    del payload[field_name]
    with pytest.raises(ValidationError):
        DataSourceRecord.model_validate(payload)


def test_registry_checks_scripts_fixtures_and_optional_raw_files(
    tmp_path: Path,
) -> None:
    registry_path, source = _write_source_registry(tmp_path)
    validate_registry(registry_path, repository_root=tmp_path)
    validate_registry(registry_path, repository_root=tmp_path, verify_raw_files=True)

    raw_path = tmp_path / str(source["raw_files"][0]["path"])
    raw_path.write_bytes(b"corrupted")
    with pytest.raises(RegistryValidationError, match="raw file size mismatch"):
        validate_registry(
            registry_path, repository_root=tmp_path, verify_raw_files=True
        )


def test_duplicate_json_keys_are_never_accepted_in_manifests(tmp_path: Path) -> None:
    registry_path = tmp_path / "data/validation/registry.json"
    _write(
        registry_path,
        b'{"registry_version":"1.0.0","registry_version":"1.0.0",'
        b'"validation_category":"verification","source_manifests":[],'
        b'"scientific_result_manifests":[]}',
    )
    with pytest.raises(RegistryValidationError, match="Duplicate JSON key"):
        validate_registry(registry_path, repository_root=tmp_path)


def test_placeholder_checksums_are_rejected(tmp_path: Path) -> None:
    payload = _source_payload(tmp_path)
    payload["raw_files"][0]["sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="placeholder SHA-256"):
        DataSourceRecord.model_validate(payload)


def test_license_permissions_control_fixture_redistribution(tmp_path: Path) -> None:
    payload = _source_payload(tmp_path)
    payload["permitted_use"]["redistribution"] = "metadata_only"
    with pytest.raises(ValidationError, match="derived fixtures cannot be registered"):
        DataSourceRecord.model_validate(payload)


def test_unindexed_manifests_and_orphan_fixtures_are_rejected(tmp_path: Path) -> None:
    registry_path, source = _write_source_registry(tmp_path)
    _write(
        tmp_path / "data/validation/sources/unindexed.json",
        json.dumps(source).encode(),
    )
    with pytest.raises(RegistryValidationError, match="not indexed"):
        validate_registry(registry_path, repository_root=tmp_path)

    (tmp_path / "data/validation/sources/unindexed.json").unlink()
    _write(tmp_path / "data/validation/fixtures/orphan.csv", b"orphan\n")
    with pytest.raises(RegistryValidationError, match="lack manifest lineage"):
        validate_registry(registry_path, repository_root=tmp_path)


def test_scientific_results_trace_to_sources_code_artifacts_and_report(
    tmp_path: Path,
) -> None:
    registry_path, _ = _write_source_registry(tmp_path)
    analysis = b"def score(observed, predicted):\n    return observed - predicted\n"
    artifact = b'{"rmse_c":0.1}\n'
    _write(tmp_path / "scripts/validation_data/demo-source-v1/analyse.py", analysis)
    _write(tmp_path / "data/validation/fixtures/demo-source-v1/result.json", artifact)
    report = (
        b"# Demonstration empirical result\n\n"
        b"Validation category: empirical validation\n"
        b"Model claim(s): THERMAL-1\n"
        b"Data source IDs: demo-source-v1\n"
    )
    _write(tmp_path / "docs/validation/results/demo-result.md", report)
    result_manifest = {
        "manifest_version": "1.0.0",
        "result_id": "demo-result-v1",
        "title": "Demonstration result",
        "validation_category": "empirical_validation",
        "created_on": "2000-01-03",
        "targeted_models": ["THERMAL-1"],
        "source_ids": ["demo-source-v1"],
        "analysis_code": [
            {
                "path": "scripts/validation_data/demo-source-v1/analyse.py",
                "sha256": _sha256(analysis),
                "command": "python scripts/validation_data/demo-source-v1/analyse.py",
            }
        ],
        "report_path": "docs/validation/results/demo-result.md",
        "result_artifacts": [
            {
                "file_id": "demo-result-summary",
                "path": "data/validation/fixtures/demo-source-v1/result.json",
                "sha256": _sha256(artifact),
                "byte_size": len(artifact),
            }
        ],
        "numerical_tolerances": {"air_temperature_c": "absolute ±0.2 degC"},
        "known_deviations": [],
    }
    _write(
        tmp_path / "data/validation/results/demo-result-v1.json",
        json.dumps(result_manifest).encode(),
    )
    index = json.loads(registry_path.read_text())
    index["scientific_result_manifests"] = [
        "data/validation/results/demo-result-v1.json"
    ]
    registry_path.write_text(json.dumps(index))

    validate_registry(registry_path, repository_root=tmp_path)


def test_unregistered_scientific_report_is_rejected(tmp_path: Path) -> None:
    registry_path, _ = _write_source_registry(tmp_path)
    _write(
        tmp_path / "docs/validation/results/unregistered.md",
        b"# Unregistered scientific claim\n",
    )
    with pytest.raises(RegistryValidationError, match="lack result manifests"):
        validate_registry(registry_path, repository_root=tmp_path)
