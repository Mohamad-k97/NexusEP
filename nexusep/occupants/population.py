"""Seeded population-level occupant schedule generation.

The model samples complete weighted diary templates.  Keeping a whole diary
intact preserves correlations among sleep, home presence, travel, and activity
durations that independent marginal draws would destroy.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

ActivityState = Literal["away", "awake", "sleeping"]
LocationBasis = Literal["reported", "sleep_inferred_home", "not_collected"]


@dataclass(frozen=True)
class OccupantEpisode:
    start_minute: int
    end_minute_exclusive: int
    activity_code: str
    activity_state: ActivityState
    is_home: bool | None
    location_basis: LocationBasis

    def __post_init__(self) -> None:
        if not 0 <= self.start_minute < self.end_minute_exclusive <= 1440:
            raise ValueError("occupant episode must lie within a 1440-minute diary")
        if not self.activity_code:
            raise ValueError("activity_code cannot be empty")
        if self.activity_state == "sleeping" and self.is_home is not True:
            raise ValueError(
                "sleeping episodes use the declared home-location inference"
            )
        if self.location_basis == "not_collected" and self.is_home is not None:
            raise ValueError("uncollected locations cannot have an observed home state")

    @property
    def duration_minutes(self) -> int:
        return self.end_minute_exclusive - self.start_minute


@dataclass(frozen=True)
class OccupantDiaryTemplate:
    template_id: str
    survey_weight: float
    diary_day: int
    episodes: tuple[OccupantEpisode, ...]

    def __post_init__(self) -> None:
        if not self.template_id:
            raise ValueError("template_id cannot be empty")
        if not math.isfinite(self.survey_weight) or self.survey_weight <= 0.0:
            raise ValueError("survey_weight must be finite and positive")
        if self.diary_day not in range(1, 8):
            raise ValueError("diary_day must use the ATUS 1..7 coding")
        if not self.episodes:
            raise ValueError("a diary template requires episodes")
        cursor = 0
        for episode in self.episodes:
            if episode.start_minute != cursor:
                raise ValueError("diary episodes must be contiguous and ordered")
            cursor = episode.end_minute_exclusive
        if cursor != 1440:
            raise ValueError("diary episodes must cover exactly 1440 minutes")

    @property
    def sleep_minutes(self) -> int:
        return sum(
            episode.duration_minutes
            for episode in self.episodes
            if episode.activity_state == "sleeping"
        )

    @property
    def observed_location_minutes(self) -> int:
        return sum(
            episode.duration_minutes
            for episode in self.episodes
            if episode.is_home is not None
        )

    @property
    def observed_home_minutes(self) -> int:
        return sum(
            episode.duration_minutes
            for episode in self.episodes
            if episode.is_home is True
        )

    @property
    def observed_location_home_fraction(self) -> float:
        denominator = self.observed_location_minutes
        if denominator == 0:
            raise ValueError(
                "diary has no observed or explicitly inferred location minutes"
            )
        return self.observed_home_minutes / denominator

    @property
    def sleep_episode_durations_minutes(self) -> tuple[int, ...]:
        return tuple(
            episode.duration_minutes
            for episode in self.episodes
            if episode.activity_state == "sleeping"
        )


@dataclass(frozen=True)
class SampledOccupantSchedule:
    occupant_id: str
    template_id: str
    diary_day: int
    episodes: tuple[OccupantEpisode, ...]

    @property
    def sleep_minutes(self) -> int:
        return sum(
            item.duration_minutes
            for item in self.episodes
            if item.activity_state == "sleeping"
        )

    @property
    def observed_location_home_fraction(self) -> float:
        observed = [item for item in self.episodes if item.is_home is not None]
        denominator = sum(item.duration_minutes for item in observed)
        if denominator == 0:
            raise ValueError("sampled schedule has no known location minutes")
        return (
            sum(item.duration_minutes for item in observed if item.is_home is True)
            / denominator
        )

    @property
    def sleep_episode_durations_minutes(self) -> tuple[int, ...]:
        return tuple(
            item.duration_minutes
            for item in self.episodes
            if item.activity_state == "sleeping"
        )


def _stable_seed_words(base_seed: int, occupant_id: str, day_index: int) -> list[int]:
    if not 0 <= base_seed <= 4_294_967_295:
        raise ValueError("base_seed must be an unsigned 32-bit integer")
    if not occupant_id:
        raise ValueError("occupant_id cannot be empty")
    if day_index < 0:
        raise ValueError("day_index must be nonnegative")
    digest = hashlib.sha256(occupant_id.encode("utf-8")).digest()
    return [
        base_seed,
        day_index & 0xFFFFFFFF,
        *[
            int.from_bytes(digest[index : index + 4], "big")
            for index in range(0, 16, 4)
        ],
    ]


class PopulationScheduleModel:
    """Immutable weighted empirical model fitted only from development diaries."""

    def __init__(
        self,
        templates: Sequence[OccupantDiaryTemplate],
        *,
        base_seed: int,
    ) -> None:
        ordered = tuple(sorted(templates, key=lambda item: item.template_id))
        if not ordered:
            raise ValueError("at least one development diary is required")
        identifiers = [item.template_id for item in ordered]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("development template IDs must be unique")
        weights = np.asarray([item.survey_weight for item in ordered], dtype=float)
        if not np.isfinite(weights).all() or np.any(weights <= 0.0):
            raise ValueError("development weights must be finite and positive")
        self._templates = ordered
        self._probabilities = weights / weights.sum()
        self._base_seed = int(base_seed)
        _stable_seed_words(self._base_seed, "seed_validation", 0)

    @property
    def development_template_count(self) -> int:
        return len(self._templates)

    @property
    def base_seed(self) -> int:
        return self._base_seed

    def sample(
        self,
        occupant_id: str,
        *,
        day_index: int = 0,
        diary_day: int | None = None,
    ) -> SampledOccupantSchedule:
        """Sample one whole diary, optionally conditioning on weekday.

        ATUS codes Sunday as 1 through Saturday as 7.  Conditioning is
        explicit because silently mixing weekday and weekend diaries would
        erase one of the population differences the model is meant to retain.
        """

        if diary_day is not None and diary_day not in range(1, 8):
            raise ValueError("diary_day must use the ATUS 1..7 coding")
        seed = np.random.SeedSequence(
            _stable_seed_words(self._base_seed, occupant_id, day_index)
        )
        generator = np.random.default_rng(seed)
        eligible = np.asarray(
            [
                index
                for index, template in enumerate(self._templates)
                if diary_day is None or template.diary_day == diary_day
            ],
            dtype=int,
        )
        if eligible.size == 0:
            raise ValueError(f"development diaries do not cover diary_day={diary_day}")
        probabilities = self._probabilities[eligible]
        probabilities = probabilities / probabilities.sum()
        index = int(generator.choice(eligible, p=probabilities))
        template = self._templates[index]
        return SampledOccupantSchedule(
            occupant_id=occupant_id,
            template_id=template.template_id,
            diary_day=template.diary_day,
            episodes=template.episodes,
        )

    def sample_population(
        self,
        size: int,
        *,
        population_prefix: str = "synthetic_occupant",
        day_index: int = 0,
        diary_day: int | None = None,
    ) -> tuple[SampledOccupantSchedule, ...]:
        if size <= 0:
            raise ValueError("population size must be positive")
        return tuple(
            self.sample(
                f"{population_prefix}_{index:06d}",
                day_index=day_index,
                diary_day=diary_day,
            )
            for index in range(size)
        )


__all__ = [
    "OccupantDiaryTemplate",
    "OccupantEpisode",
    "PopulationScheduleModel",
    "SampledOccupantSchedule",
]
