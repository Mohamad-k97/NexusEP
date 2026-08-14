"""Run the protocol-1.4 Annex 71 large-opening runtime/error diagnostic.

Validation category: post-unsealing empirical diagnostic. This runner reuses
the frozen v4 timing and scoring implementation while versioning all new
outputs separately. It does not alter acceptance thresholds or model inputs.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BASE_RUNNER = (
    REPOSITORY_ROOT
    / "scripts"
    / "validation_data"
    / "run_annex71_physical_runtime_error.py"
)
FIXTURE_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "validation"
    / "fixtures"
    / "annex71-twin-houses"
    / "large-opening-runtime-error-v5.json"
)
REPORT_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "validation"
    / "results"
    / "annex71_large_opening_runtime_error_v5.md"
)
PROTOCOL_PATH = (
    "data/validation/governance/annex71_extended_holdout_v1_4.json"
)


def _load_base_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "annex71_physical_runtime_error_v4_runner", BASE_RUNNER
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load base runner {BASE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _amend_document(document: dict) -> dict:
    document["report_version"] = "5.0.0"
    document["validation_category"]["extended"] = (
        "post_unsealing_holdout_diagnostic_under_protocol_1_4"
    )
    if PROTOCOL_PATH not in document["protocols"]:
        document["protocols"].append(PROTOCOL_PATH)
    document["airflow_model_change"] = {
        "vertical_internal_doors": (
            "NIST TN 1887r1 equation 69 centered-neutral-plane two-opening "
            "buoyancy exchange"
        ),
        "inputs": [
            "opening area and height",
            "discharge coefficient 0.78",
            "current zone temperatures",
            "timestep atmospheric pressure",
            "measured opening fraction",
        ],
        "attic_trap_door_state": "mapped from n2_attic_door_pos",
        "horizontal_trap_door_model": (
            "explicit prescribed_velocity compatibility path at 0.10 m/s"
        ),
        "whole_building_pressure_network": "not implemented or claimed",
        "parameter_fitting": "none",
    }
    document["known_limitations"] = [
        item
        for item in document["known_limitations"]
        if item
        != "Open-door exchange is prescribed symmetric mixing rather than a pressure-network solution."
    ] + [
        "Vertical-door exchange uses the verified centered-neutral-plane two-opening equation, not a whole-building pressure solve.",
        "The horizontal attic hatch remains an explicit 0.10 m/s prescribed-velocity compatibility path; no horizontal-opening validation claim is made.",
    ]
    return document


def _render_report(base: ModuleType, document: dict) -> str:
    text = base._render_report(document)
    decision = document["extended_primary_holdout"]["gate"]
    failed = [name for name, passed in decision["checks"].items() if not passed]
    text = text.replace(
        "# Annex 71 physical-model runtime and error report v4",
        "# Annex 71 large-opening runtime and error report v5",
    )
    text = text.replace(
        "documented post-unsealing source-schedule, time, and RC-mapping corrections",
        "documented post-unsealing source-schedule, time, RC-mapping, and large-opening corrections",
    )
    old_decision = (
        "The original Phase 4.9 row remains **blocked and rejected with "
        "alternative**. The temperature criteria fail and four missing "
        "outdoor-CO2 input rows independently violate the predeclared "
        "no-missing-input rule."
    )
    classification = document["blocked_gate_classification"]
    new_decision = (
        f"The original Phase 4.9 row remains **{classification}**. "
        f"Failed frozen checks: {', '.join(failed) if failed else 'none'}."
    )
    text = text.replace(old_decision, new_decision)
    text = text.replace(
        "(3) open-door exchange uses a prescribed symmetric 0.10 m/s mixing speed rather than a pressure/buoyancy large-opening network;",
        "(3) vertical-door exchange now uses the NIST two-opening buoyancy equation, while the horizontal attic hatch still uses an explicit prescribed 0.10 m/s compatibility path and no whole-building pressure solve exists;",
    )
    text = text.replace(
        "Protocol 1.1 preserves the original protocol and documents this target-independent correction.",
        "Protocols 1.1 through 1.4 preserve every post-unsealing correction; protocol 1.4 freezes the target-independent large-opening and attic-state mapping change.",
    )
    text = text.replace(
        "uv run python scripts/validation_data/run_annex71_physical_runtime_error.py",
        "uv run python scripts/validation_data/run_annex71_large_opening_runtime_error.py",
    )
    return text


def run() -> dict:
    base = _load_base_runner()
    base.FIXTURE_PATH = FIXTURE_PATH
    base.REPORT_PATH = REPORT_PATH
    document = _amend_document(base.run())
    FIXTURE_PATH.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(_render_report(base, document), encoding="utf-8")
    return document


def main() -> int:
    document = run()
    result = document["extended_primary_holdout"]
    print(
        json.dumps(
            {
                "report": str(REPORT_PATH.relative_to(REPOSITORY_ROOT)),
                "fixture": str(FIXTURE_PATH.relative_to(REPOSITORY_ROOT)),
                "runtime_seconds": result["runtime"]["runtime_seconds"],
                "pooled_rmse_c": result["metrics"]["pooled"]["rmse_c"],
                "pooled_bias_c": result["metrics"]["pooled"]["bias_c"],
                "failed_checks": [
                    name
                    for name, passed in result["gate"]["checks"].items()
                    if not passed
                ],
                "gate_passed": result["gate"]["passed"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
