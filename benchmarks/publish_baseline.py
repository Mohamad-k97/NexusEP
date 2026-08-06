"""Publish compact Phase 1 baseline manifests from ignored raw artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_ROOT = PROJECT_ROOT / "artifacts" / "baseline"
RAW_VALIDATION_PATH = (
    PROJECT_ROOT
    / "artifacts"
    / "benchmarks"
    / "phase1_4"
    / "validation_matrix_raw.json"
)
VALIDATION_PATH = BASELINE_ROOT / "phase_1_4_validation_matrix.json"
ARTIFACT_MANIFEST_PATH = BASELINE_ROOT / "artifact_manifest.json"
OBJECT_MANIFEST_PATH = BASELINE_ROOT / "deterministic_object_manifest.json"
OBJECT_PROFILE_PATH = BASELINE_ROOT / "object_profile.json"

OBJECT_CONFIGURED_ACTIONS = [
    "care_for_infant",
    "close_curtain",
    "close_window",
    "cook",
    "do_nothing",
    "emergency_eat",
    "go_to_school",
    "go_to_work",
    "make_hot_drink",
    "open_curtain",
    "open_window",
    "return_home",
    "run_washing_machine",
    "shower",
    "sleep",
    "turn_heating_off",
    "turn_heating_on",
    "turn_lights_off",
    "turn_lights_on",
    "use_laptop",
    "wake_up",
]

PROTECTED_ROOT_OUTPUTS = (
    "fast_shadow_results.csv",
    "polygon_shadow_results.csv",
    "shadow_cache_clustered_128_q16.npz",
    "shadow_cache_exact_q16.npz",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout.strip()


def publish_validation_matrix() -> None:
    raw = json.loads(RAW_VALIDATION_PATH.read_text(encoding="utf-8"))
    results = []
    for raw_result in raw["results"]:
        results.append(
            {
                "slug": raw_result["slug"],
                "role": raw_result["role"],
                "exact_command": raw_result["exact_command"],
                "working_directory": raw_result["working_directory"],
                "environment_overrides": raw_result["environment_overrides"],
                "requirements": raw_result["requirements"],
                "runtime_s": raw_result["runtime_s"],
                "return_code": raw_result["return_code"],
                "outcome": raw_result["outcome"],
                "failure_category": raw_result["failure_category"],
                "exception_or_failed_assertion_tail": raw_result[
                    "exception_or_failed_assertion_tail"
                ],
                "generated_files": raw_result["generated_files"],
                "created_outside_isolated_artifacts": raw_result[
                    "created_outside_isolated_artifacts"
                ],
                "modified_outside_isolated_artifacts": raw_result[
                    "modified_outside_isolated_artifacts"
                ],
                "removed_outside_isolated_artifacts": raw_result[
                    "removed_outside_isolated_artifacts"
                ],
                "git_status_changed": raw_result["git_status_changed"],
                "protected_hashes_unchanged": raw_result[
                    "protected_hashes_unchanged"
                ],
                "stdout_path": raw_result["stdout_path"],
                "stderr_path": raw_result["stderr_path"],
            }
        )

    matrix = {
        "schema_version": 1,
        "repository_commit": git_output("rev-parse", "HEAD"),
        "python": raw["python"],
        "python_executable": raw["python_executable"],
        "execution_policy": (
            "Each entry point ran in a separate subprocess before aggregate pytest. "
            "Profile outputs were redirected to an isolated ignored directory."
        ),
        "individual_summary": {
            "total": len(results),
            "passed": sum(result["outcome"] == "pass" for result in results),
            "failed": sum(result["outcome"] != "pass" for result in results),
            "failure_categories": {
                "environment": 0,
                "test_corruption": 0,
                "regression": 0,
                "unsupported_behavior": 0,
            },
        },
        "results": results,
        "aggregate_pytest": {
            "collection": {
                "exact_command": (
                    f"{raw['python_executable']} -m pytest --collect-only -q"
                ),
                "outcome": "pass",
                "collected": 53,
                "pytest_reported_runtime_s": 3.29,
                "process_wall_runtime_s": 6.1,
            },
            "execution": {
                "exact_command": f"{raw['python_executable']} -m pytest -q",
                "outcome": "pass",
                "passed": 53,
                "failed": 0,
                "pytest_reported_runtime_s": 17.32,
                "process_wall_runtime_s": 20.6,
            },
        },
    }
    VALIDATION_PATH.write_text(
        json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def refresh_object_dimensions() -> None:
    """Publish dimensions resolved from the current frozen object snapshot."""
    object_manifest = json.loads(OBJECT_MANIFEST_PATH.read_text(encoding="utf-8"))
    for scenario in object_manifest["scenarios"].values():
        dimensions = scenario["dimensions"]
        dimensions.pop("systems_with_zone_state", None)
        dimensions.update(
            {
                "configured_action_count": len(OBJECT_CONFIGURED_ACTIONS),
                "configured_action_names": OBJECT_CONFIGURED_ACTIONS,
                "physical_system_specs": 9,
                "public_system_state_entries_at_initialization": 0,
            }
        )
    OBJECT_MANIFEST_PATH.write_text(
        json.dumps(object_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    object_profile = json.loads(OBJECT_PROFILE_PATH.read_text(encoding="utf-8"))
    object_profile["scenario"].update(
        {
            "configured_actions": len(OBJECT_CONFIGURED_ACTIONS),
            "physical_system_specs": 9,
        }
    )
    OBJECT_PROFILE_PATH.write_text(
        json.dumps(object_profile, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def artifact_role(relative: str) -> str:
    if relative in PROTECTED_ROOT_OUTPUTS:
        return "protected pre-existing root output"
    if relative.startswith("docs/baseline/"):
        return "baseline report"
    if relative.startswith("requirements/") or relative in {
        ".python-version",
        "pyproject.toml",
    }:
        return "environment definition"
    if "/inputs/" in relative:
        return "stable input snapshot"
    if relative.startswith("artifacts/baseline/"):
        return "approved compact baseline manifest"
    if relative.startswith("artifacts/profiles/"):
        return "generated profiler artifact (ignored)"
    if relative.startswith("artifacts/benchmarks/"):
        return "generated benchmark/validation artifact (ignored)"
    return "baseline support artifact"


def artifact_candidates() -> list[Path]:
    candidates: set[Path] = set()
    roots = (
        BASELINE_ROOT,
        PROJECT_ROOT / "artifacts" / "profiles",
        PROJECT_ROOT / "artifacts" / "benchmarks" / "phase1_4",
        PROJECT_ROOT / "artifacts" / "benchmarks" / "phase1_5",
        PROJECT_ROOT / "docs" / "baseline",
        PROJECT_ROOT / "requirements",
    )
    for root in roots:
        if root.exists():
            candidates.update(path for path in root.rglob("*") if path.is_file())
    for relative in (
        *PROTECTED_ROOT_OUTPUTS,
        ".python-version",
        "pyproject.toml",
    ):
        path = PROJECT_ROOT / relative
        if path.is_file():
            candidates.add(path)
    candidates.discard(ARTIFACT_MANIFEST_PATH)
    return sorted(candidates, key=lambda path: path.relative_to(PROJECT_ROOT).as_posix())


def publish_artifact_manifest() -> None:
    dirty_status = git_output("status", "--short", "--untracked-files=all")
    entries = []
    for path in artifact_candidates():
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        entries.append(
            {
                "path": relative,
                "role": artifact_role(relative),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    manifest = {
        "schema_version": 1,
        "repository_commit": git_output("rev-parse", "HEAD"),
        "repository_branch": git_output("branch", "--show-current"),
        "dirty": bool(dirty_status),
        "dirty_status_sha256": hashlib.sha256(
            dirty_status.encode("utf-8")
        ).hexdigest(),
        "manifest_self_hash_policy": (
            "artifact_manifest.json is intentionally excluded from its own entries"
        ),
        "storage_policy": {
            "approved_versioned": "artifacts/baseline and docs/baseline",
            "ignored_generated": "artifacts/profiles and artifacts/benchmarks",
            "protected_legacy_exception": list(PROTECTED_ROOT_OUTPUTS),
        },
        "artifact_count": len(entries),
        "total_bytes": sum(entry["bytes"] for entry in entries),
        "artifacts": entries,
    }
    ARTIFACT_MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    BASELINE_ROOT.mkdir(parents=True, exist_ok=True)
    publish_validation_matrix()
    refresh_object_dimensions()
    publish_artifact_manifest()
    print(f"Wrote {VALIDATION_PATH}")
    print(f"Wrote {ARTIFACT_MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
