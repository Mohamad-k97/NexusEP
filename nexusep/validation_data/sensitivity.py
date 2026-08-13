"""Pre-calibration sensitivity and local practical-identifiability analysis."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass

import numpy as np

Simulator = Callable[[Mapping[str, float]], Mapping[str, Sequence[float]]]


@dataclass(frozen=True)
class CandidateParameter:
    name: str
    nominal: float
    lower_bound: float
    upper_bound: float
    perturbation_fraction_of_range: float = 0.05
    unit: str = "dimensionless"

    def __post_init__(self) -> None:
        values = (
            self.nominal,
            self.lower_bound,
            self.upper_bound,
            self.perturbation_fraction_of_range,
        )
        if not self.name.strip():
            raise ValueError("parameter name cannot be empty")
        if any(not math.isfinite(float(value)) for value in values):
            raise ValueError(f"parameter {self.name!r} values must be finite")
        if not self.lower_bound < self.nominal < self.upper_bound:
            raise ValueError(
                f"parameter {self.name!r} nominal must lie strictly inside bounds"
            )
        if not 0.0 < self.perturbation_fraction_of_range <= 0.5:
            raise ValueError("perturbation fraction must be in (0, 0.5]")

    @property
    def range_width(self) -> float:
        return self.upper_bound - self.lower_bound

    def perturbation_points(self) -> tuple[float, float]:
        step = self.range_width * self.perturbation_fraction_of_range
        lower = max(self.lower_bound, self.nominal - step)
        upper = min(self.upper_bound, self.nominal + step)
        if lower == upper:
            raise ValueError(f"parameter {self.name!r} has no perturbation interval")
        return lower, upper


@dataclass(frozen=True)
class TargetOutput:
    name: str
    normalization_scale: float
    unit: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("target output name cannot be empty")
        if (
            not math.isfinite(float(self.normalization_scale))
            or self.normalization_scale <= 0.0
        ):
            raise ValueError("target normalization scale must be finite and positive")


@dataclass(frozen=True)
class OutputInfluence:
    parameter: str
    output: str
    lower_value: float
    upper_value: float
    normalized_rms_sensitivity: float
    normalized_max_abs_sensitivity: float


@dataclass(frozen=True)
class CorrelatedParameterPair:
    first_parameter: str
    second_parameter: str
    absolute_cosine_similarity: float


@dataclass(frozen=True)
class SensitivityAnalysisResult:
    parameter_order: tuple[str, ...]
    output_order: tuple[str, ...]
    baseline_outputs: dict[str, tuple[float, ...]]
    influences: tuple[OutputInfluence, ...]
    normalized_sensitivity_matrix: tuple[tuple[float, ...], ...]
    singular_values: tuple[float, ...]
    effective_rank: int
    condition_number: float
    observable_parameters: tuple[str, ...]
    frozen_parameters: tuple[str, ...]
    correlated_pairs: tuple[CorrelatedParameterPair, ...]
    identifiable: bool
    rejection_reasons: tuple[str, ...]
    observable_threshold: float
    correlation_threshold: float
    maximum_condition_number: float

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["condition_number"] = (
            self.condition_number if math.isfinite(self.condition_number) else "infinite"
        )
        return payload


def _validated_output(
    values: Sequence[float], *, output_name: str, expected_length: int | None = None
) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.size == 0:
        raise ValueError(f"output {output_name!r} must be a nonempty one-dimensional series")
    if expected_length is not None and array.size != expected_length:
        raise ValueError(f"output {output_name!r} changed length across evaluations")
    if not np.isfinite(array).all():
        raise ValueError(f"output {output_name!r} contains non-finite values")
    return array


def run_local_sensitivity_analysis(
    simulator: Simulator,
    *,
    parameters: Sequence[CandidateParameter],
    targets: Sequence[TargetOutput],
    observable_threshold: float = 1e-3,
    correlation_threshold: float = 0.995,
    maximum_condition_number: float = 1e4,
    rank_relative_tolerance: float = 1e-10,
) -> SensitivityAnalysisResult:
    """Build a scaled central-difference Jacobian and screen identifiability."""

    parameter_specs = tuple(parameters)
    target_specs = tuple(targets)
    if not parameter_specs or not target_specs:
        raise ValueError("at least one parameter and one target are required")
    parameter_names = tuple(item.name for item in parameter_specs)
    target_names = tuple(item.name for item in target_specs)
    if len(parameter_names) != len(set(parameter_names)):
        raise ValueError("parameter names must be unique")
    if len(target_names) != len(set(target_names)):
        raise ValueError("target output names must be unique")
    if not 0.0 <= observable_threshold:
        raise ValueError("observable_threshold must be nonnegative")
    if not 0.0 < correlation_threshold <= 1.0:
        raise ValueError("correlation_threshold must be in (0, 1]")
    if maximum_condition_number <= 1.0:
        raise ValueError("maximum_condition_number must exceed one")

    nominal = {item.name: item.nominal for item in parameter_specs}
    raw_baseline = simulator(nominal)
    missing = sorted(set(target_names) - set(raw_baseline))
    if missing:
        raise ValueError(f"simulator omitted target outputs: {missing}")
    baseline = {
        target.name: _validated_output(
            raw_baseline[target.name], output_name=target.name
        )
        for target in target_specs
    }

    columns: list[np.ndarray] = []
    influences: list[OutputInfluence] = []
    for parameter in parameter_specs:
        lower_value, upper_value = parameter.perturbation_points()
        lower_parameters = {**nominal, parameter.name: lower_value}
        upper_parameters = {**nominal, parameter.name: upper_value}
        lower_outputs = simulator(lower_parameters)
        upper_outputs = simulator(upper_parameters)
        column_parts: list[np.ndarray] = []
        for target in target_specs:
            expected_length = baseline[target.name].size
            lower_output = _validated_output(
                lower_outputs[target.name],
                output_name=target.name,
                expected_length=expected_length,
            )
            upper_output = _validated_output(
                upper_outputs[target.name],
                output_name=target.name,
                expected_length=expected_length,
            )
            derivative = (upper_output - lower_output) / (
                upper_value - lower_value
            )
            scaled = (
                derivative
                * (0.5 * parameter.range_width)
                / target.normalization_scale
            )
            column_parts.append(scaled)
            influences.append(
                OutputInfluence(
                    parameter=parameter.name,
                    output=target.name,
                    lower_value=lower_value,
                    upper_value=upper_value,
                    normalized_rms_sensitivity=float(
                        np.sqrt(np.mean(np.square(scaled)))
                    ),
                    normalized_max_abs_sensitivity=float(np.max(np.abs(scaled))),
                )
            )
        columns.append(np.concatenate(column_parts))

    matrix = np.column_stack(columns)
    global_rms = np.sqrt(np.mean(np.square(matrix), axis=0))
    observable = tuple(
        name
        for name, influence in zip(parameter_names, global_rms, strict=True)
        if influence >= observable_threshold
    )
    frozen = tuple(name for name in parameter_names if name not in observable)

    singular_values_array = np.linalg.svd(matrix, compute_uv=False)
    largest = float(singular_values_array[0]) if singular_values_array.size else 0.0
    rank_tolerance = largest * rank_relative_tolerance
    effective_rank = int(np.sum(singular_values_array > rank_tolerance))
    if effective_rank == len(parameter_specs):
        smallest = float(singular_values_array[-1])
        condition_number = largest / smallest if smallest > 0.0 else math.inf
    else:
        condition_number = math.inf

    correlated_pairs = []
    for first_index, first_name in enumerate(parameter_names):
        first_column = matrix[:, first_index]
        first_norm = float(np.linalg.norm(first_column))
        for second_index in range(first_index + 1, len(parameter_names)):
            second_column = matrix[:, second_index]
            second_norm = float(np.linalg.norm(second_column))
            if first_norm == 0.0 or second_norm == 0.0:
                similarity = 0.0
            else:
                similarity = abs(
                    float(np.dot(first_column, second_column))
                    / (first_norm * second_norm)
                )
                similarity = min(1.0, similarity)
            if similarity >= correlation_threshold:
                correlated_pairs.append(
                    CorrelatedParameterPair(first_name, parameter_names[second_index], similarity)
                )

    reasons = []
    if frozen:
        reasons.append(f"insensitive parameters must be frozen: {list(frozen)}")
    if effective_rank < len(parameter_specs):
        reasons.append(
            f"scaled sensitivity matrix rank {effective_rank} is below "
            f"parameter count {len(parameter_specs)}"
        )
    if condition_number > maximum_condition_number:
        reasons.append(
            f"condition number {condition_number:g} exceeds {maximum_condition_number:g}"
        )
    if correlated_pairs:
        reasons.append(
            "correlated parameter fingerprints exceed the declared threshold: "
            + str(
                [
                    (item.first_parameter, item.second_parameter)
                    for item in correlated_pairs
                ]
            )
        )

    return SensitivityAnalysisResult(
        parameter_order=parameter_names,
        output_order=target_names,
        baseline_outputs={
            name: tuple(float(value) for value in values)
            for name, values in baseline.items()
        },
        influences=tuple(influences),
        normalized_sensitivity_matrix=tuple(
            tuple(float(value) for value in row) for row in matrix
        ),
        singular_values=tuple(float(value) for value in singular_values_array),
        effective_rank=effective_rank,
        condition_number=condition_number,
        observable_parameters=observable,
        frozen_parameters=frozen,
        correlated_pairs=tuple(correlated_pairs),
        identifiable=not reasons,
        rejection_reasons=tuple(reasons),
        observable_threshold=observable_threshold,
        correlation_threshold=correlation_threshold,
        maximum_condition_number=maximum_condition_number,
    )


def require_identifiable(result: SensitivityAnalysisResult) -> None:
    """Reject a proposed calibration parameter set that failed the frozen gate."""

    if not result.identifiable:
        raise ValueError("calibration problem is not identifiable: " + "; ".join(result.rejection_reasons))
