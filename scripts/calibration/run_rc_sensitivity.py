"""Run the frozen Phase 4.27 local sensitivity study for the one-node RC model."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

import numpy as np

from nexusep.abbey.building.physics.thermal import (
    ThermalTemperatureTarget,
    semi_implicit_temperature_update,
)
from nexusep.validation_data.sensitivity import (
    CandidateParameter,
    TargetOutput,
    run_local_sensitivity_analysis,
)

DEFAULT_OUTPUT = Path("artifacts/baseline/validation/thermal-rc-sensitivity-v1.json")
PARAMETERS = (
    CandidateParameter(
        "capacity_j_k", 3_000_000.0, 1_500_000.0, 6_000_000.0, unit="J/K"
    ),
    CandidateParameter(
        "conductance_w_k", 150.0, 60.0, 300.0, unit="W/K"
    ),
    CandidateParameter(
        "internal_gain_scale", 1.0, 0.5, 1.5, unit="dimensionless"
    ),
)
TARGETS = (
    TargetOutput("air_temperature_c", 1.0, "degC"),
    TargetOutput("envelope_heat_flow_w", 100.0, "W"),
)


def _forcing(step_count: int) -> tuple[np.ndarray, np.ndarray]:
    hours = np.arange(step_count, dtype=float) * 24.0 / step_count
    outdoor_c = 8.0 + 6.0 * np.sin(2.0 * np.pi * (hours - 8.0) / 24.0)
    gain_w = np.where(
        (hours >= 6.0) & (hours < 9.0),
        250.0,
        np.where((hours >= 17.0) & (hours < 23.0), 500.0, 40.0),
    )
    return outdoor_c, gain_w


def simulate(
    values: dict[str, float] | object, *, dt_minutes: float = 15.0
) -> dict[str, list[float]]:
    parameters = dict(values)  # type: ignore[arg-type]
    step_count = round(24.0 * 60.0 / dt_minutes)
    outdoor_c, base_gain_w = _forcing(step_count)
    temperature_c = 20.0
    temperatures: list[float] = []
    heat_flows: list[float] = []
    conductance_w_k = parameters["conductance_w_k"]
    for outside_c, unscaled_gain_w in zip(outdoor_c, base_gain_w, strict=True):
        temperature_c = semi_implicit_temperature_update(
            capacity_j_k=parameters["capacity_j_k"],
            old_temperature_c=temperature_c,
            targets=[
                ThermalTemperatureTarget(
                    target_id="outdoor",
                    target_type="outside",
                    temperature_c=float(outside_c),
                    h_w_k=conductance_w_k,
                )
            ],
            gain_w=unscaled_gain_w * parameters["internal_gain_scale"],
            dt_seconds=dt_minutes * 60.0,
        )
        temperatures.append(float(temperature_c))
        heat_flows.append(float(conductance_w_k * (outside_c - temperature_c)))
    return {
        "air_temperature_c": temperatures,
        "envelope_heat_flow_w": heat_flows,
    }


def _parameter_uncertainty(seed: int = 20260811) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    sample_count = 512
    nominal = {item.name: item.nominal for item in PARAMETERS}
    relative_std = {
        "capacity_j_k": 0.05,
        "conductance_w_k": 0.05,
        "internal_gain_scale": 0.10,
    }
    trajectories = []
    for _ in range(sample_count):
        sample = {
            item.name: float(
                np.clip(
                    rng.normal(item.nominal, item.nominal * relative_std[item.name]),
                    item.lower_bound,
                    item.upper_bound,
                )
            )
            for item in PARAMETERS
        }
        trajectories.append(simulate(sample)["air_temperature_c"])
    array = np.asarray(trajectories)
    percentiles = np.percentile(array, [2.5, 50.0, 97.5], axis=0)
    final_index = array.shape[1] - 1
    return {
        "status": "quantified_parameter_only",
        "seed": seed,
        "sample_count": sample_count,
        "sampling": "independent clipped normal distributions",
        "assumed_relative_standard_deviation": relative_std,
        "nominal_parameters": nominal,
        "air_temperature_c_95_percent_parameter_interval": {
            "final_timestep": {
                "p2_5": float(percentiles[0, final_index]),
                "p50": float(percentiles[1, final_index]),
                "p97_5": float(percentiles[2, final_index]),
            },
            "maximum_width_c": float(np.max(percentiles[2] - percentiles[0])),
        },
        "limitation": (
            "This is a parameter-only interval, not a total prediction interval; "
            "assumed distributions are illustrative and must be replaced before calibration."
        ),
    }


def _numerical_uncertainty() -> dict[str, object]:
    nominal = {item.name: item.nominal for item in PARAMETERS}
    baseline = np.asarray(simulate(nominal, dt_minutes=15.0)["air_temperature_c"])
    reference = np.asarray(simulate(nominal, dt_minutes=1.0)["air_temperature_c"])
    sampled_reference = reference[14::15]
    difference = baseline - sampled_reference
    return {
        "status": "quantified_timestep_comparison",
        "baseline_dt_minutes": 15.0,
        "reference_dt_minutes": 1.0,
        "air_temperature_rmse_c": float(np.sqrt(np.mean(np.square(difference)))),
        "air_temperature_max_abs_error_c": float(np.max(np.abs(difference))),
    }


def build_payload() -> dict[str, object]:
    result = run_local_sensitivity_analysis(
        simulate,
        parameters=PARAMETERS,
        targets=TARGETS,
        observable_threshold=0.01,
        correlation_threshold=0.995,
        maximum_condition_number=100.0,
    )
    calibrated_parameters = list(result.observable_parameters) if result.identifiable else []
    return {
        "artifact_version": "1.0.0",
        "validation_category": "verification",
        "phase": "4.27",
        "study_id": "thermal-rc-local-sensitivity-v1",
        "model_scope": "one-node backward-Euler reduced-order RC response",
        "production_function": (
            "nexusep.abbey.building.physics.thermal."
            "semi_implicit_temperature_update"
        ),
        "experiment": {
            "duration_hours": 24.0,
            "dt_minutes": 15.0,
            "initial_air_temperature_c": 20.0,
            "forcing": "sinusoidal outdoor temperature and scheduled internal-gain pulses",
        },
        "analysis": result.to_dict(),
        "decision": {
            "calibration_problem_accepted": result.identifiable,
            "calibrated_parameters": calibrated_parameters,
            "frozen_parameters": list(result.frozen_parameters),
            "rejection_reasons": list(result.rejection_reasons),
            "rule": (
                "A parameter may be calibrated only when observable, in a full-rank "
                "well-conditioned set, and within its declared physical bounds."
            ),
        },
        "uncertainty": {
            "measurement": {
                "status": "not_available_in_analytical_fixture",
                "action": "required from each empirical source before fitting",
            },
            "weather_input": {
                "status": "not_quantified_for_prescribed_forcing",
                "action": "propagate source uncertainty in empirical studies",
            },
            "parameter": _parameter_uncertainty(),
            "structural_model": {
                "status": "not_quantified",
                "action": "compare accepted model structures before empirical claims",
            },
            "numerical": _numerical_uncertainty(),
            "stochastic_occupant": {
                "status": "not_applicable_to_deterministic_fixture",
                "action": "use repeated seeded ensembles for occupant studies",
            },
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "reproduce": "uv run python scripts/calibration/run_rc_sensitivity.py",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = build_payload()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    decision = payload["decision"]
    assert isinstance(decision, dict)
    print(json.dumps(decision, indent=2))
    return 0 if decision["calibration_problem_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
