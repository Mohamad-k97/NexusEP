"""Audit Annex 71 heat paths without fitting additional parameters."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from nexusep.validation_data.annex71 import (
    Annex71ModelParameters,
    load_annex71_intervals,
    parameters_as_dict,
    select_interval,
)
from nexusep.validation_data.annex71_audit import audit_annex71_energy_paths

DEFAULT_RAW_DIRECTORY = Path(
    "data/raw/validation/annex71-twin-houses/03_Data_Main_Experiment"
)
DEFAULT_PRODUCTION_RESULT = Path(
    "data/validation/fixtures/annex71-twin-houses/production-transfer-result-v1.json"
)
DEFAULT_RESULT = Path(
    "data/validation/fixtures/annex71-twin-houses/energy-path-audit-v1.json"
)
DEFAULT_REPORT = Path("docs/validation/results/annex71_energy_path_audit_v1.md")


def _period(records, start: str, end_exclusive: str):
    return select_interval(
        records,
        start=datetime.fromisoformat(start),
        end_exclusive=datetime.fromisoformat(end_exclusive),
    )


def _parameters_from_production_result(path: Path) -> Annex71ModelParameters:
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = payload["study"]["fixed_and_fitted_parameters"]
    return Annex71ModelParameters(
        **{
            field: float(value)
            for field, value in values.items()
            if field in Annex71ModelParameters.__dataclass_fields__
        }
    )


def _write_report(payload: dict, path: Path) -> None:
    calibration = payload["audit"]["calibration"]["summary"]
    later = payload["audit"]["later_period"]["summary"]
    rows = []
    for zone_id, zone in later["by_zone"].items():
        one_step = zone["one_step_temperature"]
        residual = zone["unexplained_air_node_gain"]
        rows.append(
            f"| {zone_id} | {one_step['rmse_c']:.3f} | {residual['bias_w']:.1f} | "
            f"{residual['mae_w']:.1f} | {residual['p05_w']:.1f} | "
            f"{residual['p95_w']:.1f} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# Annex 71 thermal energy-path audit",
                "",
                "Validation category: empirical validation",
                "Model claim(s): THERMAL-1",
                "Data source IDs: iea-ebc-annex71-twin-houses-2020",
                "",
                "Result role: diagnostic verification and empirical residual analysis",
                "",
                (
                    "This audit runs the production object adapter but constrains each interval "
                    "with the measured air temperature. The unmeasured mass node is advanced "
                    "conditionally. The reported residual is therefore a diagnostic net heat "
                    "flow, not a fitted correction or a validation score."
                ),
                "",
                (
                    "Positive unexplained gain means the model is missing heat; negative means "
                    "the represented paths supply too much heat for the measured response."
                ),
                "",
                "## Results",
                "",
                (
                    "Calibration one-step RMSE: "
                    f"{calibration['whole_building']['one_step_temperature_rmse_c']:.3f} degC; "
                    "unexplained-gain bias: "
                    f"{calibration['whole_building']['unexplained_gain_bias_w']:.1f} W."
                ),
                "",
                (
                    "Later-period one-step RMSE: "
                    f"{later['whole_building']['one_step_temperature_rmse_c']:.3f} degC; "
                    "unexplained-gain bias: "
                    f"{later['whole_building']['unexplained_gain_bias_w']:.1f} W; "
                    "MAE: "
                    f"{later['whole_building']['unexplained_gain_mae_w']:.1f} W."
                ),
                "",
                "| Air body | One-step RMSE (degC) | Residual bias (W) | Residual MAE (W) | P05 (W) | P95 (W) |",
                "|---|---:|---:|---:|---:|---:|",
                *rows,
                "",
                "## Diagnosis",
                "",
                (
                    "- Explicit ventilation supply temperature and heater radiant split improve "
                    "the free-running later-period RMSE, but do not remove the rejection."
                ),
                (
                    "- The source-determined 30-degree roof tilt is now mapped. It changes the "
                    "residual only slightly and does not remove the rejection."
                ),
                (
                    "- Frozen cross-period tests reject one-hour heating, internal-gain, and "
                    "solar shifts; alternate heater splits; +/-2 degC initial mass states; and "
                    "floor-area capacity allocation as material explanations."
                ),
                (
                    "- The remaining structural gaps are component-resolved fabric topology, "
                    "the ground-floor cellar boundary, and per-opening blind state. A single "
                    "fitted conductance or another aggregate correction is not justified."
                ),
                "",
                "No empirical correction factor is applied to production physics.",
                "",
                "## Reproduce",
                "",
                "```text",
                "uv run python scripts/validation_data/run_annex71_energy_path_audit.py",
                "```",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-directory", type=Path, default=DEFAULT_RAW_DIRECTORY)
    parser.add_argument(
        "--production-result", type=Path, default=DEFAULT_PRODUCTION_RESULT
    )
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    source_records = load_annex71_intervals(args.raw_directory)
    calibration_records = _period(
        source_records,
        "2018-12-19T10:00:00+01:00",
        "2019-01-10T00:00:00+01:00",
    )
    later_records = _period(
        source_records,
        "2019-01-10T00:00:00+01:00",
        "2019-02-01T10:00:00+01:00",
    )
    parameters = _parameters_from_production_result(args.production_result)
    calibration = audit_annex71_energy_paths(calibration_records, parameters)
    later = audit_annex71_energy_paths(later_records, parameters)
    payload = {
        "artifact_version": "1.0.0",
        "created_on": datetime.now(UTC).date().isoformat(),
        "validation_category": "diagnostic_verification_and_empirical_residual_analysis",
        "claim_limit": (
            "Post-hoc energy-path diagnosis; not calibration, blind validation, "
            "or evidence that acceptance thresholds pass."
        ),
        "parameters": parameters_as_dict(parameters),
        "audit": {
            "calibration": calibration.to_dict(include_records=False),
            "later_period": later.to_dict(include_records=False),
        },
        "decision": {
            "explicit_supply_air_path_verified": True,
            "explicit_heater_split_verified": True,
            "single_constant_missing_conductance_supported": False,
            "additional_calibration_authorized": False,
            "validation_status_changed": False,
        },
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_report(payload, args.report)
    print(json.dumps(payload["decision"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
