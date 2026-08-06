r"""Run surviving Phase 16--18 entry points one at a time.

Each command receives its own ignored artifact directory.  The harness records
wall time, captured output, generated files, repository path changes, and Git
status before and after the command.  It intentionally does not interpret a
benchmark as an assertion suite; the ``role`` field preserves that distinction.

Run from the repository root with the supported environment::

    .venv\Scripts\python.exe -m benchmarks.validation_matrix
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = PROJECT_ROOT / "artifacts" / "benchmarks" / "phase1_4"

PROTECTED_PATHS = (
    ".spyproject/config/backups/workspace.ini.bak",
    ".spyproject/config/workspace.ini",
    "nexusep/data/abbey/config/abbey_config.jsonc",
    "fast_shadow_results.csv",
    "polygon_shadow_results.csv",
    "shadow_cache_clustered_128_q16.npz",
    "shadow_cache_exact_q16.npz",
)


def _module(slug: str, module: str, role: str, requirements: str) -> dict:
    return {
        "slug": slug,
        "argv": [sys.executable, "-m", module],
        "role": role,
        "requirements": requirements,
    }


COMMANDS = [
    _module(
        "phase16_0",
        "nexusep.abbey.run_test_phase_16_0_validation_harness",
        "validation test",
        "installed nexusep; NumPy; deterministic in-memory fixtures",
    ),
    _module(
        "phase16_1",
        "nexusep.abbey.run_test_phase_16_1_validation_harness",
        "validation test",
        "installed nexusep; NumPy; deterministic in-memory fixtures",
    ),
    *[
        _module(
            f"phase17_{number}",
            f"nexusep.abbey.run_test_phase_17_{number}_{suffix}",
            "validation test",
            "installed nexusep; NumPy; pandas; pytest-compatible assertions",
        )
        for number, suffix in (
            (1, "model_rename"),
            (2, "performance_input_contract"),
            (3, "engine_to_performance_adapter"),
            (4, "observation_contract"),
            (5, "legacy_fallback_quarantine"),
            (6, "runner_integration"),
            (7, "debug_outputs"),
            (8, "yearly_outputs"),
        )
    ],
    _module(
        "phase17_10",
        "nexusep.abbey.run_test_phase_17_10_airflow_sanity",
        "validation test",
        "installed nexusep; NumPy; deterministic airflow fixtures",
    ),
    {
        "slug": "phase18_helpers",
        "argv": [
            sys.executable,
            "-c",
            (
                "from nexusep.abbey import run_test_phase_18_validation_helpers "
                "as h; assert callable(h.make_one_person_one_zone_input)"
            ),
        ],
        "role": "helper",
        "requirements": "installed nexusep; Phase 18 helper compatibility import",
    },
    _module(
        "phase18_0_legacy",
        "nexusep.abbey.run_test_phase_18_0",
        "array benchmark",
        "installed nexusep; NumPy; 8760-step synthetic array input",
    ),
    _module(
        "phase18_20",
        "nexusep.abbey.run_test_phase_18_20_8760_benchmark",
        "array benchmark",
        "installed nexusep; NumPy; 8760-step synthetic array input",
    ),
    _module(
        "phase18_21",
        "nexusep.abbey.run_test_phase_18_21_profile_8760",
        "array benchmark",
        "installed nexusep; NumPy; cProfile; isolated profile output directory",
    ),
    _module(
        "phase18_21_legacy",
        "nexusep.abbey.run_test_18_21_profiling",
        "array benchmark",
        "installed nexusep; NumPy; cProfile; legacy compatibility alias",
    ),
    _module(
        "phase18_22",
        "nexusep.abbey.run_test_phase_18_22_action_scoring_fast_compare",
        "validation test",
        "installed nexusep; NumPy; optional Numba comparison when available",
    ),
    _module(
        "phase18_23",
        "nexusep.abbey.run_test_phase_18_23_thermal_fast_compare",
        "validation test",
        "installed nexusep; NumPy; optional Numba comparison when available",
    ),
    _module(
        "phase18_24",
        "nexusep.abbey.run_test_phase_18_24_moisture_fast_compare",
        "validation test",
        "installed nexusep; NumPy; optional Numba comparison when available",
    ),
    _module(
        "phase18_26",
        "nexusep.abbey.run_test_phase_18_26_shoebox_8760_benchmark",
        "array benchmark",
        "installed nexusep; NumPy; 8760-step shoebox array input",
    ),
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _protected_hashes() -> dict[str, str | None]:
    values: dict[str, str | None] = {}
    for relative in PROTECTED_PATHS:
        path = PROJECT_ROOT / relative
        values[relative] = _sha256(path) if path.is_file() else None
    return values


def _git_status() -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.splitlines()


def _workspace_state() -> dict[str, tuple[int, int]]:
    excluded_parts = {".git", ".venv", "__pycache__", ".pytest_cache"}
    values: dict[str, tuple[int, int]] = {}
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(PROJECT_ROOT)
        if any(part in excluded_parts for part in relative.parts):
            continue
        if path.is_relative_to(RUN_ROOT):
            continue
        stat = path.stat()
        values[relative.as_posix()] = (stat.st_size, stat.st_mtime_ns)
    return values


def _relative_files(root: Path) -> list[dict[str, object]]:
    if not root.exists():
        return []
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def _command_text(argv: list[str]) -> str:
    return subprocess.list2cmdline(argv)


def run_one(specification: dict) -> dict:
    slug = specification["slug"]
    command_root = RUN_ROOT / slug
    generated_root = command_root / "generated"
    generated_root.mkdir(parents=True, exist_ok=True)

    stdout_path = command_root / "stdout.txt"
    stderr_path = command_root / "stderr.txt"

    before_status = _git_status()
    before_workspace = _workspace_state()
    before_protected = _protected_hashes()

    environment = os.environ.copy()
    environment.update(
        {
            "MPLBACKEND": "Agg",
            "NEXUSEP_PROFILE_OUTPUT_DIR": str(generated_root),
            "PYTHONHASHSEED": "0",
            "TZ": "Europe/Rome",
        }
    )

    started = time.perf_counter()
    completed = subprocess.run(
        specification["argv"],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    runtime_s = time.perf_counter() - started

    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")

    after_status = _git_status()
    after_workspace = _workspace_state()
    after_protected = _protected_hashes()

    created_outside_artifacts = sorted(
        set(after_workspace).difference(before_workspace)
    )
    removed_outside_artifacts = sorted(
        set(before_workspace).difference(after_workspace)
    )
    modified_outside_artifacts = sorted(
        path
        for path in set(before_workspace).intersection(after_workspace)
        if before_workspace[path] != after_workspace[path]
    )

    diagnostic_lines = (completed.stderr or completed.stdout).splitlines()
    result = {
        "slug": slug,
        "role": specification["role"],
        "exact_command": _command_text(specification["argv"]),
        "working_directory": str(PROJECT_ROOT),
        "environment_overrides": {
            "MPLBACKEND": "Agg",
            "NEXUSEP_PROFILE_OUTPUT_DIR": str(generated_root),
            "PYTHONHASHSEED": "0",
            "TZ": "Europe/Rome",
        },
        "requirements": specification["requirements"],
        "runtime_s": runtime_s,
        "return_code": completed.returncode,
        "outcome": "pass" if completed.returncode == 0 else "error",
        "failure_category": None if completed.returncode == 0 else "unclassified",
        "exception_or_failed_assertion_tail": (
            diagnostic_lines[-20:] if completed.returncode != 0 else []
        ),
        "generated_files": _relative_files(generated_root),
        "stdout_path": str(stdout_path.relative_to(PROJECT_ROOT)),
        "stderr_path": str(stderr_path.relative_to(PROJECT_ROOT)),
        "git_status_changed": before_status != after_status,
        "git_status_before": before_status,
        "git_status_after": after_status,
        "created_outside_isolated_artifacts": created_outside_artifacts,
        "modified_outside_isolated_artifacts": modified_outside_artifacts,
        "removed_outside_isolated_artifacts": removed_outside_artifacts,
        "protected_hashes_unchanged": before_protected == after_protected,
    }
    (command_root / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> int:
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    results = []
    try:
        for specification in COMMANDS:
            saved_result_path = RUN_ROOT / specification["slug"] / "result.json"
            if saved_result_path.is_file():
                result = json.loads(saved_result_path.read_text(encoding="utf-8"))
                results.append(result)
                print(
                    f"SKIP {specification['slug']}: existing complete result "
                    f"({result['outcome']}, {result['runtime_s']:.6f}s)",
                    flush=True,
                )
                continue
            print(f"RUN {specification['slug']}: {_command_text(specification['argv'])}")
            result = run_one(specification)
            results.append(result)
            print(
                f"  {result['outcome'].upper()} rc={result['return_code']} "
                f"runtime={result['runtime_s']:.6f}s "
                f"generated={len(result['generated_files'])} "
                f"repo_state_changed={result['git_status_changed']}",
                flush=True,
            )
    except Exception:
        traceback.print_exc()
        return 2

    summary = {
        "schema_version": 1,
        "python": sys.version,
        "python_executable": sys.executable,
        "run_root": str(RUN_ROOT),
        "results": results,
    }
    (RUN_ROOT / "validation_matrix_raw.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    failures = [result for result in results if result["return_code"] != 0]
    print(f"SUMMARY {len(results) - len(failures)} passed, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
