"""Run the protocol-1.5 Annex 71 boundary-contract runtime/error diagnostic.

Validation category: post-unsealing empirical diagnostic. Acceptance thresholds
are inherited unchanged from the frozen v4 runner. Outputs are versioned so
prior rejected evidence remains immutable.
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
    / "boundary-runtime-error-v6.json"
)
REPORT_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "validation"
    / "results"
    / "annex71_boundary_runtime_error_v6.md"
)
PROTOCOL_PATH = "data/validation/governance/annex71_extended_holdout_v1_5.json"


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
    document["report_version"] = "6.0.0"
    document["validation_category"]["extended"] = (
        "post_unsealing_holdout_diagnostic_under_protocol_1_5"
    )
    if PROTOCOL_PATH not in document["protocols"]:
        document["protocols"].append(PROTOCOL_PATH)
    document["boundary_contract_change"] = {
        "ceiling_topology": "three source-plan footprint links to attic",
        "mechanical_ventilation": "distinct measured SUA supply and EHA exhaust enthalpy terms",
        "sky_forcing": "RadiationIR_global converted to effective sky temperature",
        "opaque_boundary": "explicit opt-in sol-air term; no residual-derived parameter",
        "parameter_fitting": "none",
    }
    document["known_limitations"] = list(document["known_limitations"]) + [
        "Exterior longwave emissivity 0.90 is a declared physical assumption, not a measured or fitted parameter.",
        "The array backend rejects the new boundary terms until equivalent kernels exist.",
    ]
    return document


def _render_report(base: ModuleType, document: dict) -> str:
    text = base._render_report(document)
    decision = document["extended_primary_holdout"]["gate"]
    failed = [name for name, passed in decision["checks"].items() if not passed]
    text = text.replace(
        "# Annex 71 physical-model runtime and error report v4",
        "# Annex 71 boundary-contract runtime and error report v6",
    )
    text = text.replace(
        "documented post-unsealing source-schedule, time, and RC-mapping corrections",
        "documented post-unsealing source-schedule, time, RC-mapping, airflow, topology, and radiative-boundary corrections",
    )
    old_decision = (
        "The original Phase 4.9 row remains **blocked and rejected with "
        "alternative**. The temperature criteria fail and four missing "
        "outdoor-CO2 input rows independently violate the predeclared "
        "no-missing-input rule."
    )
    classification = document["blocked_gate_classification"]
    text = text.replace(
        old_decision,
        f"The original Phase 4.9 row remains **{classification}**. "
        f"Failed frozen checks: {', '.join(failed) if failed else 'none'}.",
    )
    text = text.replace(
        "Protocol 1.1 preserves the original protocol and documents this target-independent correction.",
        "Protocols 1.1 through 1.5 preserve every post-unsealing correction; protocol 1.5 freezes the target-independent topology, ventilation, and radiative-boundary corrections.",
    )
    text = text.replace(
        "uv run python scripts/validation_data/run_annex71_physical_runtime_error.py",
        "uv run python scripts/validation_data/run_annex71_boundary_runtime_error.py",
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
