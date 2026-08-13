"""Evaluate the blocked occupant-duration gate with open aggregate ATUS data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from nexusep.abbey.building.physics.weather import WeatherState
from nexusep.abbey.simulation.runner import AbbeySimulation
from nexusep.jsonc import loads_strict_json

DEFAULT_RAW_FILES = (
    Path(
        "data/raw/validation/atus-alternative/"
        "dbnomics-sleeping-series-0.json"
    ),
    Path(
        "data/raw/validation/atus-alternative/"
        "dbnomics-sleeping-series-1000.json"
    ),
)
DEFAULT_CONFIG = Path("nexusep/data/abbey/config/abbey_config.jsonc")
DEFAULT_FIXTURE = Path(
    "data/validation/fixtures/atus-aggregate/sleeping-series.csv"
)
DEFAULT_RESULT = Path(
    "data/validation/fixtures/atus-aggregate/sleep-alternative-result-v1.json"
)
ALL_PERSONS_SERIES = "TUU10101AA01000247"
HOLDOUT_YEAR = "2023"
MAXIMUM_DURATION_ERROR_MINUTES = 30.0
SIMULATION_DAYS = 30
WARMUP_DAYS = 1
DT_MINUTES = 15
RANDOM_SEED = 101
START_TIMESTAMP = datetime(2023, 1, 1, tzinfo=ZoneInfo("Europe/Rome"))


class DeterministicValidationWeather:
    """Small deterministic forcing used only for occupant plausibility runs."""

    def get_state_by_step(self, step: int) -> WeatherState:
        timestamp = START_TIMESTAMP + timedelta(
            minutes=int(step) * DT_MINUTES
        )
        hour = timestamp.hour + timestamp.minute / 60.0
        daily = math.sin(2.0 * math.pi * (hour - 8.0) / 24.0)
        daylight = max(0.0, math.sin(math.pi * (hour - 7.0) / 11.0))
        ghi = 500.0 * daylight
        return WeatherState(
            datetime=timestamp,
            outdoor_temperature_c=8.0 + 3.5 * daily,
            wind_speed_m_s=2.0,
            wind_direction_deg=180.0,
            direct_normal_radiation_w_m2=0.7 * ghi,
            diffuse_horizontal_radiation_w_m2=0.3 * ghi,
            global_horizontal_radiation_w_m2=ghi,
            outdoor_illuminance_lux=120.0 * ghi,
            sky_condition="clear" if ghi > 0.0 else "night",
            outdoor_co2_ppm=420.0,
            outdoor_noise_db=42.0,
            relative_humidity_percent=65.0,
            atmospheric_pressure_pa=101325.0,
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_documents(paths: tuple[Path, ...]) -> tuple[list[dict], dict]:
    documents: list[dict] = []
    dataset: dict | None = None
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        current_dataset = payload["dataset"]
        if dataset is None:
            dataset = current_dataset
        elif current_dataset["dir_hash"] != dataset["dir_hash"]:
            raise ValueError("DBnomics query pages do not share a dataset snapshot")
        documents.extend(payload["series"]["docs"])
    if dataset is None:
        raise ValueError("no ATUS query documents were supplied")
    by_code = {document["series_code"]: document for document in documents}
    if len(by_code) != len(documents):
        raise ValueError("duplicate ATUS series across query pages")
    return documents, dataset


def _is_number(value: object) -> bool:
    return isinstance(value, (float, int)) and math.isfinite(float(value))


def _latest_value(document: dict) -> float:
    observations = dict(zip(document["period"], document["value"], strict=True))
    value = observations.get(HOLDOUT_YEAR)
    if not _is_number(value):
        raise ValueError(
            f"series {document['series_code']} lacks a finite {HOLDOUT_YEAR} value"
        )
    return float(value)


def select_strata(documents: list[dict], baseline: dict) -> list[dict]:
    varying_dimensions = {"age", "sex"}
    selected = []
    for document in documents:
        if document["series_code"] == baseline["series_code"]:
            continue
        dimensions = document["dimensions"]
        same_context = all(
            dimensions.get(name) == value
            for name, value in baseline["dimensions"].items()
            if name not in varying_dimensions
        )
        differs = any(
            dimensions.get(name) != baseline["dimensions"][name]
            for name in varying_dimensions
        )
        if same_context and differs and _is_number(document["value"][-1]):
            selected.append(document)
    return sorted(selected, key=lambda item: item["series_code"])


def write_fixture(
    baseline: dict,
    strata: list[dict],
    labels: dict,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for year, value in zip(baseline["period"], baseline["value"], strict=True):
        if _is_number(value):
            rows.append(
                {
                    "series_code": baseline["series_code"],
                    "year": year,
                    "age": labels["age"][baseline["dimensions"]["age"]],
                    "sex": labels["sex"][baseline["dimensions"]["sex"]],
                    "average_sleep_hours_per_day": float(value),
                    "split_role": (
                        "untouched_holdout" if year == HOLDOUT_YEAR else "development"
                    ),
                }
            )
    for document in strata:
        rows.append(
            {
                "series_code": document["series_code"],
                "year": HOLDOUT_YEAR,
                "age": labels["age"][document["dimensions"]["age"]],
                "sex": labels["sex"][document["dimensions"]["sex"]],
                "average_sleep_hours_per_day": _latest_value(document),
                "split_role": "descriptive_stratum_not_fitted",
            }
        )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_target_sleep_minutes(path: Path) -> float:
    config = loads_strict_json(
        path.read_text(encoding="utf-8"), source=path, jsonc=True
    )
    return float(config["decision"]["target_sleep_minutes"])


def run_object_sleep_diagnostic(config_path: Path) -> dict[str, object]:
    """Measure sleep outputs from the production object runner.

    The ATUS screen must compare survey duration with simulated behavior, not
    with an internal decision threshold.  Day zero is excluded from the daily
    mean and an episode clipped by the final simulation boundary is excluded
    from episode statistics.
    """

    np.random.seed(RANDOM_SEED)
    simulation = AbbeySimulation.initialize(
        config_path=config_path,
        duration_hours=24.0 * SIMULATION_DAYS,
        dt_minutes=DT_MINUTES,
        weather_provider=DeterministicValidationWeather(),
        random_seed=RANDOM_SEED,
    )
    simulation.run(progress_every_steps=None)
    frame = simulation.people_to_dataframe()
    occupant_ids = sorted(frame["occupant_id"].astype(str).unique())
    if len(occupant_ids) != 1:
        raise ValueError(
            "aggregate sleep diagnostic requires exactly one default occupant"
        )

    sleeping = frame["person_is_sleeping"].astype(bool)
    scored = frame[frame["day"] >= WARMUP_DAYS]
    scored_sleeping = scored["person_is_sleeping"].astype(bool)
    scored_days = SIMULATION_DAYS - WARMUP_DAYS
    mean_minutes_per_day = (
        float(scored_sleeping.sum()) * DT_MINUTES / scored_days
    )

    transition = sleeping.ne(sleeping.shift(fill_value=False)).cumsum()
    episode_durations = [
        len(group) * DT_MINUTES
        for _group_id, group in frame.loc[sleeping].groupby(transition[sleeping])
        if int(group.index[-1]) != int(frame.index[-1])
    ]
    if not episode_durations:
        raise ValueError("object-runner diagnostic produced no complete sleep episodes")

    return {
        "engine": "object",
        "random_seed": RANDOM_SEED,
        "simulation_days": SIMULATION_DAYS,
        "warmup_days_excluded": WARMUP_DAYS,
        "dt_minutes": DT_MINUTES,
        "occupant_count": len(occupant_ids),
        "occupant_has_job": bool(frame["person_has_job"].iloc[0]),
        "mean_sleep_minutes_per_scored_day": mean_minutes_per_day,
        "complete_episode_count": len(episode_durations),
        "median_complete_episode_minutes": float(np.median(episode_durations)),
        "minimum_complete_episode_minutes": int(min(episode_durations)),
        "maximum_complete_episode_minutes": int(max(episode_durations)),
        "episodes_ending_at_old_300_minute_discontinuity": int(
            sum(duration == 300 for duration in episode_durations)
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, nargs=2, default=DEFAULT_RAW_FILES)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    args = parser.parse_args()

    raw_files = tuple(args.raw)
    documents, dataset = load_documents(raw_files)
    baseline = next(
        document
        for document in documents
        if document["series_code"] == ALL_PERSONS_SERIES
    )
    strata = select_strata(documents, baseline)
    labels = dataset["dimensions_values_labels"]
    write_fixture(baseline, strata, labels, args.fixture)

    target_minutes = load_target_sleep_minutes(args.config)
    model_output = run_object_sleep_diagnostic(args.config)
    reference_minutes = _latest_value(baseline) * 60.0
    simulated_minutes = float(model_output["mean_sleep_minutes_per_scored_day"])
    absolute_error_minutes = abs(simulated_minutes - reference_minutes)
    duration_passed = absolute_error_minutes <= MAXIMUM_DURATION_ERROR_MINUTES
    distribution_supported = False
    payload = {
        "artifact_version": "1.0.0",
        "validation_category": "empirical_validation_alternative",
        "phase": "4.22-alternative",
        "study_id": "atus-aggregate-sleep-alternative-v1",
        "source": {
            "provider": "U.S. Bureau of Labor Statistics",
            "access_path": "DBnomics BLS/tu mirror",
            "dataset_snapshot_hash": dataset["dir_hash"],
            "indexed_at": dataset["indexed_at"],
            "raw_files": [
                {
                    "path": path.as_posix(),
                    "sha256": sha256_file(path),
                    "byte_size": path.stat().st_size,
                }
                for path in raw_files
            ],
        },
        "series": {
            "code": ALL_PERSONS_SERIES,
            "description": baseline["series_name"],
            "development_years": [
                year
                for year, value in zip(
                    baseline["period"], baseline["value"], strict=True
                )
                if year != HOLDOUT_YEAR and _is_number(value)
            ],
            "untouched_holdout_year": int(HOLDOUT_YEAR),
            "holdout_average_sleep_hours_per_day": _latest_value(baseline),
            "descriptive_age_sex_strata_count": len(strata),
        },
        "nexusep": {
            "config_path": args.config.as_posix(),
            "config_sha256": sha256_file(args.config),
            "decision_target_sleep_minutes": target_minutes,
            "model_output": model_output,
        },
        "comparison": {
            "reference_minutes_per_day": reference_minutes,
            "simulated_minutes_per_day": simulated_minutes,
            "absolute_duration_error_minutes": absolute_error_minutes,
            "predeclared_maximum_error_minutes": MAXIMUM_DURATION_ERROR_MINUTES,
            "duration_gate_passed": duration_passed,
            "individual_distribution_available": distribution_supported,
            "distribution_gate_passed": False,
            "passed": bool(duration_passed and distribution_supported),
        },
        "limitations": [
            "The mirror contains BLS LABSTAT aggregate estimates, not ATUS respondent diaries.",
            "Aggregate age/sex means cannot test within-person timing, duration, event-frequency, or transition distributions.",
            "The mirror snapshot ends in 2023; 2024 BLS microdata downloads returned an automated-access denial in this environment.",
            "The duration comparison now uses object-runner output; target_sleep_minutes is retained only as decision-parameter provenance.",
            "One default occupant and one seed cannot represent an ATUS population distribution.",
            "The array engine uses a different fixed-duration sleep contract and is excluded until backend conformance is restored.",
        ],
        "fixture": {
            "path": args.fixture.as_posix(),
            "sha256": sha256_file(args.fixture),
            "byte_size": args.fixture.stat().st_size,
        },
        "blocked_gate_classification": (
            "blocked but passed with alternative"
            if duration_passed and distribution_supported
            else "blocked and rejected with alternative"
        ),
        "reproduce": (
            "uv run python "
            "scripts/validation_data/run_atus_aggregate_alternative.py"
        ),
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["comparison"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
