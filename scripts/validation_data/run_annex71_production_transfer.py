"""Run the frozen Annex 71 four-air-body production-adapter transfer study."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from scipy.optimize import minimize_scalar

from nexusep.validation_data.annex71 import (
    Annex71ModelParameters,
    allocate_envelope_conductance_from_coheat,
    load_annex71_intervals,
    parameters_as_dict,
    run_object_scenario,
    select_interval,
    temperature_metrics,
)
from nexusep.validation_data.sensitivity import (
    CandidateParameter,
    TargetOutput,
    run_local_sensitivity_analysis,
)

DEFAULT_RAW_DIRECTORY = Path(
    "data/raw/validation/annex71-twin-houses/03_Data_Main_Experiment"
)
DEFAULT_RESULT = Path(
    "data/validation/fixtures/annex71-twin-houses/production-transfer-result-v1.json"
)
DEFAULT_REPORT = Path("docs/validation/results/annex71_production_transfer_v1.md")
ZONE_ORDER = (
    "attic_airbody",
    "ground_airbody",
    "kitchen_airbody",
    "sleeping_airbody",
)


def _period(records, start: str, end: str):
    zone = ZoneInfo("Europe/Berlin")
    return select_interval(
        records,
        start=datetime.fromisoformat(start).astimezone(zone),
        end_exclusive=datetime.fromisoformat(end).astimezone(zone),
    )


def _write_report(payload: dict[str, object], path: Path) -> None:
    study = payload["study"]
    calibration = study["calibration"]
    transfer = study["later_period_diagnostic"]
    decision = study["predeclared_acceptance"]
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for zone_id, metrics in transfer["metrics"]["by_zone"].items():
        rows.append(
            f"| {zone_id} | {metrics['bias_c']:.3f} | {metrics['mae_c']:.3f} | "
            f"{metrics['rmse_c']:.3f} | {metrics['correlation']:.3f} |"
        )
    path.write_text(
        "\n".join(
            [
                "# Annex 71 four-air-body production diagnostic",
                "",
                "Validation category: empirical validation",
                "Model claim(s): THERMAL-1",
                "Data source IDs: iea-ebc-annex71-twin-houses-2020",
                "",
                (
                    "This study replaces the old one-room helper calculation with a strict canonical "
                    "scenario and the production object-engine adapter. It uses the four air bodies, "
                    "measured heat/internal-gain inputs, measured ventilation flow and supply "
                    "temperature, official weather, published windows, and deterministic graph IDs."
                ),
                "",
                (
                    "> This is a post-hoc production diagnostic, not a blind or untouched "
                    "validation. The open Annex 71 targets have been inspected while correcting "
                    "the mapper, and the original Annex 58 Experiment 2 archive remains unavailable."
                ),
                "",
                "## Frozen protocol",
                "",
                (
                    "The protocol and thresholds were frozen in "
                    "`data/validation/governance/annex71_production_transfer_v1.json` before "
                    "production-adapter fitting. The independently published 107 W/K HTC is "
                    "distributed with the coheat phase; only effective capacity is fitted in the "
                    "first User-1 period. Thresholds are diagnostic and cannot create a validation "
                    "pass because the later target period is no longer sealed."
                ),
                "",
                f"Sensitivity gate: **{'pass' if study['sensitivity']['identifiable'] else 'fail'}**.",
                "",
                "## Results",
                "",
                (
                    f"Calibration pooled RMSE: {calibration['metrics']['pooled']['rmse_c']:.3f} degC; "
                    f"bias: {calibration['metrics']['pooled']['bias_c']:.3f} degC."
                ),
                "",
                (
                    f"Later-period diagnostic pooled RMSE: {transfer['metrics']['pooled']['rmse_c']:.3f} degC; "
                    f"bias: {transfer['metrics']['pooled']['bias_c']:.3f} degC."
                ),
                "",
                "| Air body | Bias (degC) | MAE (degC) | RMSE (degC) | Correlation |",
                "|---|---:|---:|---:|---:|",
                *rows,
                "",
                (
                    "Thermal conservation residual: "
                    f"{transfer['maximum_abs_thermal_balance_residual_w']:.3e} W."
                ),
                "",
                f"Numerical diagnostic decision: **{'passed' if decision['numerical_criteria_passed'] else 'failed'}**.",
                (
                    "Scientific gate decision: **rejected as validation evidence** because the "
                    "later target period is not sealed."
                ),
                "",
                "## Scientific limits",
                "",
                (
                    "- The measured electric heater's documented 70/30 convective/radiative "
                    "split is represented explicitly by the typed control contract."
                ),
                "- The source-determined 30-degree attic roof-window tilt is represented explicitly.",
                (
                    "- The ground-floor west blind is not represented because canonical v1 has "
                    "no per-opening blind state; this is a structural solar-gain limitation."
                ),
                (
                    "- The ground floor still uses the common outdoor boundary because canonical "
                    "v1 cannot yet carry the measured time-varying cellar temperature; "
                    "substituting outdoor temperature for the cellar is not treated as valid."
                ),
                (
                    "- Opaque fabric remains a conductance-preserving reduction rather than "
                    "component-resolved wall, roof, ceiling, floor, and thermal-bridge topology."
                ),
                (
                    "- Measured supply-air temperature enters the air node through the typed "
                    "mechanical-ventilation heat path; it is not approximated as an internal gain."
                ),
                "- The result does not close the temporal-transfer or blind-validation gates.",
                "",
                "## Reproduce",
                "",
                "```text",
                "uv run python scripts/validation_data/run_annex71_production_transfer.py",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-directory", type=Path, default=DEFAULT_RAW_DIRECTORY)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--max-fit-evaluations", type=int, default=12)
    parser.add_argument(
        "--replay-capacity-j-k",
        type=float,
        default=None,
        help="Replay a previously recorded fitted capacity without re-optimizing.",
    )
    args = parser.parse_args()
    records = load_annex71_intervals(args.raw_directory)
    coheat_records = _period(
        records,
        "2018-12-10T19:00:00+01:00",
        "2018-12-19T10:00:00+01:00",
    )
    calibration_records = _period(
        records,
        "2018-12-19T10:00:00+01:00",
        "2019-01-10T00:00:00+01:00",
    )
    transfer_records = _period(
        records,
        "2019-01-10T00:00:00+01:00",
        "2019-02-01T10:00:00+01:00",
    )
    allocation = allocate_envelope_conductance_from_coheat(coheat_records)
    base = Annex71ModelParameters(
        ground_envelope_conductance_w_k=allocation["ground_airbody"],
        kitchen_envelope_conductance_w_k=allocation["kitchen_airbody"],
        sleeping_envelope_conductance_w_k=allocation["sleeping_airbody"],
        attic_envelope_conductance_w_k=allocation["attic_airbody"],
    )

    def simulate_for_sensitivity(values):
        parameters = replace(
            base,
            total_effective_capacity_j_k=float(values["total_effective_capacity_j_k"]),
        )
        run = run_object_scenario(calibration_records, parameters)
        return {
            zone_id: run.simulated_temperature_c[zone_id][24:] for zone_id in ZONE_ORDER
        }

    sensitivity = run_local_sensitivity_analysis(
        simulate_for_sensitivity,
        parameters=(
            CandidateParameter(
                "total_effective_capacity_j_k",
                nominal=42_000_000.0,
                lower_bound=5_000_000.0,
                upper_bound=150_000_000.0,
                perturbation_fraction_of_range=0.05,
                unit="J/K",
            ),
        ),
        targets=tuple(
            TargetOutput(zone_id, normalization_scale=1.0, unit="degC")
            for zone_id in ZONE_ORDER
        ),
    )
    if not sensitivity.identifiable:
        raise RuntimeError(
            "frozen capacity calibration is not identifiable: "
            + "; ".join(sensitivity.rejection_reasons)
        )

    evaluations = []

    def objective(capacity: float) -> float:
        parameters = replace(base, total_effective_capacity_j_k=float(capacity))
        run = run_object_scenario(calibration_records, parameters)
        rmse = float(temperature_metrics(run, warmup_timesteps=24)["pooled"]["rmse_c"])
        evaluations.append({"capacity_j_k": float(capacity), "pooled_rmse_c": rmse})
        print(f"capacity={capacity:.3f} J/K calibration_rmse={rmse:.6f} C", flush=True)
        return rmse

    if args.replay_capacity_j_k is None:
        fit = minimize_scalar(
            objective,
            method="bounded",
            bounds=(5_000_000.0, 150_000_000.0),
            options={"maxiter": args.max_fit_evaluations, "xatol": 100_000.0},
        )
        fit_mode = "bounded_optimization"
    else:
        replay_capacity = float(args.replay_capacity_j_k)
        if not 5_000_000.0 <= replay_capacity <= 150_000_000.0:
            raise ValueError("replay capacity is outside the frozen parameter bounds")
        fit = SimpleNamespace(
            x=replay_capacity,
            success=False,
            message="Replay of a previously recorded bound-seeking failed fit.",
        )
        objective(replay_capacity)
        fit_mode = "replay_of_recorded_failed_fit"
    fitted = replace(base, total_effective_capacity_j_k=float(fit.x))
    calibration_run = run_object_scenario(calibration_records, fitted)
    transfer_run = run_object_scenario(transfer_records, fitted)
    calibration_metrics = temperature_metrics(calibration_run, warmup_timesteps=24)
    transfer_metrics = temperature_metrics(transfer_run, warmup_timesteps=24)
    pooled = transfer_metrics["pooled"]
    rmse_passed = bool(pooled["rmse_c"] <= 1.0)
    bias_passed = bool(abs(pooled["bias_c"]) <= 0.5)
    conservation_passed = bool(
        transfer_run.maximum_abs_thermal_balance_residual_w <= 1.0e-7
    )
    no_fallback = bool(not transfer_run.fallback_used)
    distance_from_bound = min(
        (fit.x - 5_000_000.0) / 145_000_000.0,
        (150_000_000.0 - fit.x) / 145_000_000.0,
    )
    numerical_criteria_passed = bool(
        rmse_passed
        and bias_passed
        and conservation_passed
        and no_fallback
        and fit.success
        and distance_from_bound >= 0.01
    )
    decision = {
        "temperature_rmse_passed": rmse_passed,
        "temperature_bias_passed": bias_passed,
        "thermal_conservation_passed": conservation_passed,
        "no_fallback_passed": no_fallback,
        "optimizer_succeeded": bool(fit.success),
        "parameter_not_on_bound": bool(distance_from_bound >= 0.01),
        "numerical_criteria_passed": numerical_criteria_passed,
        "later_period_remained_sealed": False,
        "passed": False,
    }
    payload = {
        "artifact_version": "1.0.0",
        "created_on": datetime.now(UTC).date().isoformat(),
        "validation_category": "empirical_validation_diagnostic",
        "study": {
            "study_id": "annex71-four-airbody-production-transfer-v1",
            "protocol": "data/validation/governance/annex71_production_transfer_v1.json",
            "engine": "object production adapter",
            "graph_sha256": transfer_run.graph_sha256,
            "coheat_envelope_allocation_w_k": allocation,
            "sensitivity": {
                key: value
                for key, value in sensitivity.to_dict().items()
                if key not in {"baseline_outputs", "jacobian"}
            },
            "fixed_and_fitted_parameters": parameters_as_dict(fitted),
            "fit": {
                "mode": fit_mode,
                "success": bool(fit.success),
                "message": str(fit.message),
                "evaluations": evaluations,
                "minimum_fractional_distance_from_bound": float(distance_from_bound),
            },
            "calibration": {
                "start": calibration_records[0].timestamp.isoformat(),
                "end_exclusive": (
                    calibration_records[-1].timestamp + timedelta(hours=1)
                ).isoformat(),
                "metrics": calibration_metrics,
                "maximum_abs_thermal_balance_residual_w": calibration_run.maximum_abs_thermal_balance_residual_w,
            },
            "later_period_diagnostic": {
                "start": transfer_records[0].timestamp.isoformat(),
                "end_exclusive": (
                    transfer_records[-1].timestamp + timedelta(hours=1)
                ).isoformat(),
                "metrics": transfer_metrics,
                "maximum_abs_thermal_balance_residual_w": transfer_run.maximum_abs_thermal_balance_residual_w,
                "fallback_used": transfer_run.fallback_used,
            },
            "predeclared_acceptance": decision,
            "claim_limit": "Post-hoc same-experiment production diagnostic; neither blind nor untouched validation.",
        },
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_report(payload, args.report)
    print(json.dumps(decision, sort_keys=True))
    return 0 if decision["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
