"""Run the protocol-1.5.1 Annex 71 sky-boundary diagnostic (v7)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
V6_RUNNER = (
    REPOSITORY_ROOT
    / "scripts"
    / "validation_data"
    / "run_annex71_boundary_runtime_error.py"
)
FIXTURE_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "validation"
    / "fixtures"
    / "annex71-twin-houses"
    / "sky-boundary-runtime-error-v7.json"
)
REPORT_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "validation"
    / "results"
    / "annex71_sky_boundary_runtime_error_v7.md"
)
PROTOCOL_PATH = "data/validation/governance/annex71_extended_holdout_v1_5_1.json"


def _load_v6_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("annex71_boundary_v6_runner", V6_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load v6 runner {V6_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run() -> dict:
    v6 = _load_v6_runner()
    v6.FIXTURE_PATH = FIXTURE_PATH
    v6.REPORT_PATH = REPORT_PATH
    document = v6.run()
    document["report_version"] = "7.0.0"
    document["validation_category"]["extended"] = (
        "post_unsealing_holdout_diagnostic_under_protocol_1_5_1"
    )
    document["protocols"].append(PROTOCOL_PATH)
    document["weather_boundary_handoff"] = {
        "source": "CanonicalWeather.sky_temperature_c",
        "target": "object WeatherState.sky_temperature_c",
        "parameter_fitting": "none",
    }
    text = v6._render_report(v6._load_base_runner(), document)
    text = text.replace(
        "# Annex 71 boundary-contract runtime and error report v6",
        "# Annex 71 sky-boundary runtime and error report v7",
    )
    text = text.replace(
        "protocol 1.5 freezes the target-independent topology, ventilation, and radiative-boundary corrections.",
        "protocol 1.5.1 freezes the missing canonical-to-object sky-temperature handoff.",
    )
    text = text.replace(
        "uv run python scripts/validation_data/run_annex71_boundary_runtime_error.py",
        "uv run python scripts/validation_data/run_annex71_sky_boundary_runtime_error.py",
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
