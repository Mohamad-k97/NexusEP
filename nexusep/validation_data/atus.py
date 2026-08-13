"""BLS ATUS microdata preprocessing and distributional holdout metrics."""

from __future__ import annotations

import csv
import hashlib
import io
import math
import zipfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from nexusep.occupants.population import (
    OccupantDiaryTemplate,
    OccupantEpisode,
    PopulationScheduleModel,
    SampledOccupantSchedule,
)

SLEEP_ACTIVITY_CODE = "010101"
ATUS_DIARY_START_MINUTE = 4 * 60


@dataclass(frozen=True)
class ATUSPartition:
    development: tuple[OccupantDiaryTemplate, ...]
    holdout: tuple[OccupantDiaryTemplate, ...]

    def __post_init__(self) -> None:
        development_ids = {item.template_id for item in self.development}
        holdout_ids = {item.template_id for item in self.holdout}
        if not self.development or not self.holdout:
            raise ValueError(
                "ATUS split requires nonempty development and holdout sets"
            )
        if development_ids & holdout_ids:
            raise ValueError("ATUS respondent leakage across partitions")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _data_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".dat")]
        if len(members) != 1:
            raise ValueError(f"expected one .dat member in {path}, found {members}")
        with archive.open(members[0]) as raw:
            return list(
                csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            )


def respondent_bucket(case_id: str) -> int:
    """Frozen group-preserving 80/20 split bucket."""

    if not case_id:
        raise ValueError("TUCASEID cannot be empty")
    value = int.from_bytes(hashlib.sha256(case_id.encode("ascii")).digest()[:8], "big")
    return value % 10


def _float(row: dict[str, str], field: str) -> float:
    try:
        result = float(row[field])
    except (KeyError, ValueError) as error:
        raise ValueError(f"invalid ATUS field {field!r}") from error
    if not math.isfinite(result):
        raise ValueError(f"non-finite ATUS field {field!r}")
    return result


def _int(row: dict[str, str], field: str) -> int:
    return int(_float(row, field))


def _episode(row: dict[str, str], start_minute: int) -> OccupantEpisode:
    duration = _int(row, "TUACTDUR24")
    if duration <= 0:
        raise ValueError("ATUS episode duration must be positive")
    code = row["TRCODE"].strip().zfill(6)
    where = _int(row, "TEWHERE")
    if code == SLEEP_ACTIVITY_CODE:
        state = "sleeping"
        is_home: bool | None = True
        basis = "sleep_inferred_home"
    elif where == 1:
        state = "awake"
        is_home = True
        basis = "reported"
    elif where > 1:
        state = "away"
        is_home = False
        basis = "reported"
    else:
        state = "awake"
        is_home = None
        basis = "not_collected"
    return OccupantEpisode(
        start_minute=start_minute,
        end_minute_exclusive=start_minute + duration,
        activity_code=code,
        activity_state=state,
        is_home=is_home,
        location_basis=basis,
    )


def _rotate_atus_diary_to_midnight(
    episodes: Sequence[OccupantEpisode],
) -> tuple[OccupantEpisode, ...]:
    """Convert the official 04:00--04:00 diary to a 00:00--24:00 schedule."""

    rotated = []
    for episode in episodes:
        start = episode.start_minute + ATUS_DIARY_START_MINUTE
        end = episode.end_minute_exclusive + ATUS_DIARY_START_MINUTE
        if start >= 1440:
            spans = ((start - 1440, end - 1440),)
        elif end <= 1440:
            spans = ((start, end),)
        else:
            spans = ((start, 1440), (0, end - 1440))
        for span_start, span_end in spans:
            if span_start == span_end:
                continue
            rotated.append(
                OccupantEpisode(
                    start_minute=span_start,
                    end_minute_exclusive=span_end,
                    activity_code=episode.activity_code,
                    activity_state=episode.activity_state,
                    is_home=episode.is_home,
                    location_basis=episode.location_basis,
                )
            )
    return tuple(sorted(rotated, key=lambda item: item.start_minute))


def load_atus_2023_diaries(
    respondent_archive: Path,
    activity_archive: Path,
) -> tuple[OccupantDiaryTemplate, ...]:
    """Join respondent weights to complete activity diaries by TUCASEID."""

    respondents = _data_rows(respondent_archive)
    activities = _data_rows(activity_archive)
    metadata = {}
    for row in respondents:
        case_id = row["TUCASEID"].strip()
        if case_id in metadata:
            raise ValueError(f"duplicate ATUS respondent {case_id}")
        metadata[case_id] = (_float(row, "TUFINLWGT"), _int(row, "TUDIARYDAY"))
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in activities:
        grouped.setdefault(row["TUCASEID"].strip(), []).append(row)
    if set(grouped) != set(metadata):
        raise ValueError("ATUS respondent and activity case coverage differs")
    diaries = []
    for case_id in sorted(grouped):
        rows = sorted(grouped[case_id], key=lambda row: _int(row, "TUACTIVITY_N"))
        cursor = 0
        episodes = []
        for row in rows:
            episode = _episode(row, cursor)
            episodes.append(episode)
            cursor = episode.end_minute_exclusive
        if cursor != 1440:
            raise ValueError(
                f"ATUS respondent {case_id} diary totals {cursor}, not 1440 minutes"
            )
        weight, diary_day = metadata[case_id]
        public_hash = hashlib.sha256(case_id.encode("ascii")).hexdigest()[:16]
        diaries.append(
            OccupantDiaryTemplate(
                template_id=f"atus2023_{public_hash}",
                survey_weight=weight,
                diary_day=diary_day,
                episodes=_rotate_atus_diary_to_midnight(episodes),
            )
        )
    return tuple(diaries)


def partition_diaries(
    diaries: Sequence[OccupantDiaryTemplate],
) -> ATUSPartition:
    """Partition public template hashes with the frozen respondent hash rule.

    ``template_id`` embeds the first 16 hex characters of the same SHA-256
    digest, which is sufficient to reproduce the first-eight-byte bucket.
    """

    development = []
    holdout = []
    for diary in diaries:
        digest_prefix = diary.template_id.removeprefix("atus2023_")
        bucket = int(digest_prefix, 16) % 10
        (development if bucket <= 7 else holdout).append(diary)
    return ATUSPartition(tuple(development), tuple(holdout))


def weighted_quantiles(
    values: Sequence[float],
    weights: Sequence[float],
    quantiles: Sequence[float],
) -> tuple[float, ...]:
    value_array = np.asarray(values, dtype=float)
    weight_array = np.asarray(weights, dtype=float)
    requested = np.asarray(quantiles, dtype=float)
    if (
        value_array.ndim != 1
        or value_array.size == 0
        or value_array.size != weight_array.size
    ):
        raise ValueError(
            "weighted quantiles require equal nonempty one-dimensional values and weights"
        )
    if (
        not np.isfinite(value_array).all()
        or not np.isfinite(weight_array).all()
        or np.any(weight_array <= 0.0)
    ):
        raise ValueError("weighted quantile inputs must be finite and weights positive")
    if np.any((requested < 0.0) | (requested > 1.0)):
        raise ValueError("quantiles must be in [0, 1]")
    order = np.argsort(value_array, kind="stable")
    sorted_values = value_array[order]
    sorted_weights = weight_array[order]
    cumulative = (
        np.cumsum(sorted_weights) - 0.5 * sorted_weights
    ) / sorted_weights.sum()
    return tuple(
        float(item) for item in np.interp(requested, cumulative, sorted_values)
    )


def _generated_values(
    schedules: Sequence[SampledOccupantSchedule],
    attribute: str,
) -> list[float]:
    return [float(getattr(schedule, attribute)) for schedule in schedules]


def validate_population_model(
    model: PopulationScheduleModel,
    holdout: Sequence[OccupantDiaryTemplate],
    *,
    generated_population_size: int,
    quantiles: Sequence[float] = (0.1, 0.25, 0.5, 0.75, 0.9),
) -> dict[str, object]:
    """Compare generated population distributions with weighted holdout diaries."""

    if not holdout:
        raise ValueError("holdout cannot be empty")
    generated = model.sample_population(generated_population_size, day_index=0)
    holdout_weights = [item.survey_weight for item in holdout]

    def daily_metric(
        holdout_values: Sequence[float], generated_values: Sequence[float]
    ) -> dict[str, object]:
        observed = weighted_quantiles(holdout_values, holdout_weights, quantiles)
        predicted = tuple(
            float(item) for item in np.quantile(generated_values, quantiles)
        )
        errors = tuple(
            abs(left - right) for left, right in zip(predicted, observed, strict=True)
        )
        return {
            "quantiles": list(quantiles),
            "holdout_weighted": list(observed),
            "generated": list(predicted),
            "absolute_errors": list(errors),
            "quantile_mae": float(np.mean(errors)),
        }

    sleep_fraction = daily_metric(
        [item.sleep_minutes / 1440.0 for item in holdout],
        [item.sleep_minutes / 1440.0 for item in generated],
    )
    home_fraction = daily_metric(
        [item.observed_location_home_fraction for item in holdout],
        _generated_values(generated, "observed_location_home_fraction"),
    )
    observed_sleep_durations = []
    observed_sleep_weights = []
    for diary in holdout:
        for duration in diary.sleep_episode_durations_minutes:
            observed_sleep_durations.append(float(duration))
            observed_sleep_weights.append(diary.survey_weight)
    generated_sleep_durations = [
        float(duration)
        for diary in generated
        for duration in diary.sleep_episode_durations_minutes
    ]
    observed_duration_quantiles = weighted_quantiles(
        observed_sleep_durations, observed_sleep_weights, quantiles
    )
    generated_duration_quantiles = tuple(
        float(item) for item in np.quantile(generated_sleep_durations, quantiles)
    )
    duration_errors = tuple(
        abs(left - right)
        for left, right in zip(
            generated_duration_quantiles, observed_duration_quantiles, strict=True
        )
    )
    duration_metric = {
        "quantiles": list(quantiles),
        "holdout_weighted_minutes": list(observed_duration_quantiles),
        "generated_minutes": list(generated_duration_quantiles),
        "absolute_errors_minutes": list(duration_errors),
        "quantile_mae_minutes": float(np.mean(duration_errors)),
    }
    return {
        "development_template_count": model.development_template_count,
        "holdout_respondent_count": len(holdout),
        "generated_population_size": len(generated),
        "daily_sleep_fraction": sleep_fraction,
        "observed_location_home_fraction": home_fraction,
        "sleep_episode_duration": duration_metric,
        "determinism_check": asdict(model.sample("determinism_probe"))
        == asdict(model.sample("determinism_probe")),
    }


__all__ = [
    "ATUSPartition",
    "load_atus_2023_diaries",
    "partition_diaries",
    "respondent_bucket",
    "sha256_file",
    "validate_population_model",
    "weighted_quantiles",
]
