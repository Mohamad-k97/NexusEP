"""Distribution-aware verification metrics for binary occupant actions."""

from __future__ import annotations

import math
import statistics
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise


@dataclass(frozen=True)
class BinaryEvent:
    start_index: int
    end_index_exclusive: int
    start_time_minutes: float
    duration_minutes: float


@dataclass(frozen=True)
class DistributionSummary:
    count: int
    mean: float | None
    population_stddev: float | None
    minimum: float | None
    median: float | None
    maximum: float | None


@dataclass(frozen=True)
class BinaryProbabilityScores:
    count: int
    brier_score: float
    log_loss: float


@dataclass(frozen=True)
class BinaryTransitionSummary:
    off_to_off: int
    off_to_on: int
    on_to_off: int
    on_to_on: int
    probability_on_given_off: float | None
    probability_off_given_on: float | None


@dataclass(frozen=True)
class ConditionalEventRate:
    condition: str
    count: int
    event_count: int
    event_rate: float


def _binary_values(values: Sequence[int | bool], name: str) -> tuple[int, ...]:
    normalized = tuple(int(value) for value in values)
    if any(value not in (0, 1) for value in normalized):
        raise ValueError(f"{name} must contain only binary values")
    return normalized


def extract_binary_events(
    states: Sequence[int | bool], *, interval_minutes: float
) -> tuple[BinaryEvent, ...]:
    """Return every contiguous active run using start-of-interval semantics."""

    if not math.isfinite(interval_minutes) or interval_minutes <= 0.0:
        raise ValueError("interval_minutes must be finite and positive")
    binary = _binary_values(states, "states")
    events: list[BinaryEvent] = []
    start: int | None = None
    for index, active in enumerate((*binary, 0)):
        if active and start is None:
            start = index
        elif not active and start is not None:
            events.append(
                BinaryEvent(
                    start_index=start,
                    end_index_exclusive=index,
                    start_time_minutes=start * interval_minutes,
                    duration_minutes=(index - start) * interval_minutes,
                )
            )
            start = None
    return tuple(events)


def summarize_distribution(values: Sequence[float]) -> DistributionSummary:
    """Summarize a population or event distribution without hiding its spread."""

    normalized = tuple(float(value) for value in values)
    if any(not math.isfinite(value) for value in normalized):
        raise ValueError("distribution values must be finite")
    if not normalized:
        return DistributionSummary(0, None, None, None, None, None)
    return DistributionSummary(
        count=len(normalized),
        mean=statistics.fmean(normalized),
        population_stddev=statistics.pstdev(normalized),
        minimum=min(normalized),
        median=statistics.median(normalized),
        maximum=max(normalized),
    )


def score_binary_probabilities(
    probabilities: Sequence[float],
    outcomes: Sequence[int | bool],
    *,
    epsilon: float = 1e-15,
) -> BinaryProbabilityScores:
    """Calculate Brier score and Bernoulli log loss from pre-decision probabilities."""

    predicted = tuple(float(value) for value in probabilities)
    observed = _binary_values(outcomes, "outcomes")
    if len(predicted) != len(observed):
        raise ValueError("probabilities and outcomes must have equal length")
    if not predicted:
        raise ValueError("at least one probability/outcome pair is required")
    if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in predicted):
        raise ValueError("probabilities must be finite values in [0, 1]")
    if not math.isfinite(epsilon) or not 0.0 < epsilon < 0.5:
        raise ValueError("epsilon must be finite and between 0 and 0.5")

    brier = statistics.fmean(
        (probability - outcome) ** 2
        for probability, outcome in zip(predicted, observed, strict=True)
    )
    log_loss = -statistics.fmean(
        outcome * math.log(min(max(probability, epsilon), 1.0 - epsilon))
        + (1 - outcome)
        * math.log(1.0 - min(max(probability, epsilon), 1.0 - epsilon))
        for probability, outcome in zip(predicted, observed, strict=True)
    )
    return BinaryProbabilityScores(len(predicted), brier, log_loss)


def summarize_binary_transitions(
    states: Sequence[int | bool],
) -> BinaryTransitionSummary:
    """Count state transitions and report the two action-transition probabilities."""

    binary = _binary_values(states, "states")
    counts = {(0, 0): 0, (0, 1): 0, (1, 0): 0, (1, 1): 0}
    for before, after in pairwise(binary):
        counts[(before, after)] += 1
    off_denominator = counts[(0, 0)] + counts[(0, 1)]
    on_denominator = counts[(1, 0)] + counts[(1, 1)]
    return BinaryTransitionSummary(
        off_to_off=counts[(0, 0)],
        off_to_on=counts[(0, 1)],
        on_to_off=counts[(1, 0)],
        on_to_on=counts[(1, 1)],
        probability_on_given_off=(
            counts[(0, 1)] / off_denominator if off_denominator else None
        ),
        probability_off_given_on=(
            counts[(1, 0)] / on_denominator if on_denominator else None
        ),
    )


def conditional_event_rates(
    outcomes: Sequence[int | bool], conditions: Sequence[Hashable]
) -> tuple[ConditionalEventRate, ...]:
    """Report event rates by a frozen environmental or contextual stratum."""

    binary = _binary_values(outcomes, "outcomes")
    if len(binary) != len(conditions):
        raise ValueError("outcomes and conditions must have equal length")
    grouped: dict[str, list[int]] = {}
    for outcome, condition in zip(binary, conditions, strict=True):
        grouped.setdefault(str(condition), []).append(outcome)
    return tuple(
        ConditionalEventRate(
            condition=condition,
            count=len(values),
            event_count=sum(values),
            event_rate=sum(values) / len(values),
        )
        for condition, values in sorted(grouped.items())
    )


def summarize_between_person_event_rates(
    states_by_person: Mapping[str, Sequence[int | bool]],
) -> DistributionSummary:
    """Summarize person-level rates, preserving people as the unit of variation."""

    rates: list[float] = []
    for person_id, states in sorted(states_by_person.items()):
        binary = _binary_values(states, f"states_by_person[{person_id!r}]")
        if not binary:
            raise ValueError(f"person {person_id!r} has no observations")
        rates.append(sum(binary) / len(binary))
    return summarize_distribution(rates)
