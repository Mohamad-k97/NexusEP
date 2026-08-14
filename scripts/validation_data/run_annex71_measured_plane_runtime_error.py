"""Run the protocol-1.6 Annex 71 measured-plane diagnostic (v8)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
V7_RUNNER = (
    REPOSITORY_ROOT
    / "scripts"
    / "validation_data"
    / "run_annex71_sky_boundary_runtime_error.py"
)
FIXTURE_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "validation"
    / "fixtures"
    / "annex71-twin-houses"
    / "measured-plane-runtime-error-v8.json"
)
REPORT_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "validation"
    / "results"
    / "annex71_measured_plane_runtime_error_v8.md"
)
PROTOCOL_PATH = "data/validation/governance/annex71_extended_holdout_v1_6.json"


def _load_v7_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("annex71_sky_v7_runner", V7_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load v7 runner {V7_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run() -> dict:
    v7 = _load_v7_runner()
    v7.FIXTURE_PATH = FIXTURE_PATH
    v7.REPORT_PATH = REPORT_PATH
    document = v7.run()
    document["report_version"] = "8.0.0"
    document["validation_category"]["extended"] = (
        "post_unsealing_holdout_diagnostic_under_protocol_1_6"
    )
    document["protocols"].append(PROTOCOL_PATH)
    document["measured_plane_forcing"] = {
        "vertical_cardinal_surfaces": "source Radiation_North/East/South/West",
        "nonvertical_surfaces": "NREL-SPA isotropic plane-of-array",
        "parameter_fitting": "none",
    }
    text = v7._load_v6_runner()._render_report(
        v7._load_v6_runner()._load_base_runner(), document
    )
    text = text.replace(
        "# Annex 71 boundary-contract runtime and error report v6",
        "# Annex 71 measured-plane runtime and error report v8",
    )
    text = text.replace(
        "Protocols 1.1 through 1.5 preserve every post-unsealing correction; protocol 1.5 freezes the target-independent topology, ventilation, and radiative-boundary corrections.",
        "Protocols 1.1 through 1.6 preserve every post-unsealing correction; protocol 1.6 freezes measured cardinal vertical-plane forcing.",
    )
    text = text.replace(
        "uv run python scripts/validation_data/run_annex71_boundary_runtime_error.py",
        "uv run python scripts/validation_data/run_annex71_measured_plane_runtime_error.py",
    )
    FIXTURE_PATH.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(text, encoding="utf-8")
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
