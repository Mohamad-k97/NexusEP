"""Fit the seeded ATUS population model and score the frozen respondent holdout."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from nexusep.occupants import PopulationScheduleModel
from nexusep.validation_data.atus import (
    load_atus_2023_diaries,
    partition_diaries,
    sha256_file,
    validate_population_model,
)

DEFAULT_RAW_DIRECTORY = Path("data/raw/validation/atus-2023-microdata")
DEFAULT_RESULT = Path(
    "data/validation/fixtures/atus-2023-microdata/population-holdout-result-v1.json"
)
DEFAULT_REPORT = Path("docs/validation/results/atus_population_holdout_v1.md")
RESPONDENT_SHA256 = "5b24084ffd4c618c14e096429f99f0efa87e1393d7902c6007f96dd8725ba90c"
ACTIVITY_SHA256 = "c7f497f8ac91254b9ddf771f8de475dded5bc7ea39806a019e8cdee920989b33"


def _write_report(payload: dict[str, object], path: Path) -> None:
    study = payload["study"]
    metrics = study["metrics"]
    decisions = study["predeclared_acceptance"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# ATUS 2023 population holdout validation",
                "",
                "Validation category: empirical validation",
                "Model claim(s): OCC-1",
                "Data source IDs: bls-atus-2023-microdata",
                "",
                (
                    "The production model samples complete survey-weighted development diaries. "
                    "This preserves within-day dependence among sleep, location, and activity duration. "
                    "A stable respondent hash keeps every episode for one person in one partition."
                ),
                "",
                "## Evidence and limits",
                "",
                f"- Development respondents: {metrics['development_template_count']}",
                f"- Untouched holdout respondents: {metrics['holdout_respondent_count']}",
                f"- Generated schedules: {metrics['generated_population_size']}",
                (
                    "- Sleeping is activity code 010101. BLS does not collect location for sleep, "
                    "so sleep-at-home is an explicit inference. Other uncollected locations are "
                    "excluded from the primary home-fraction denominator."
                ),
                (
                    "- The official 04:00-to-04:00 diary is rotated to a canonical "
                    "00:00-to-24:00 local-day schedule before use."
                ),
                (
                    "- ATUS supports U.S. population priors; it is not deterministic household truth "
                    "and is not direct empirical validation for an Italian population."
                ),
                "",
                "## Frozen holdout results",
                "",
                (
                    "- Daily sleep-fraction quantile MAE: "
                    f"{metrics['daily_sleep_fraction']['quantile_mae']:.6f} "
                    f"(limit 0.05; {'pass' if decisions['daily_sleep_fraction_passed'] else 'fail'})"
                ),
                (
                    "- Observed-location home-fraction quantile MAE: "
                    f"{metrics['observed_location_home_fraction']['quantile_mae']:.6f} "
                    f"(limit 0.05; {'pass' if decisions['home_fraction_passed'] else 'fail'})"
                ),
                (
                    "- Sleep-episode duration quantile MAE: "
                    f"{metrics['sleep_episode_duration']['quantile_mae_minutes']:.3f} min "
                    f"(limit 30 min; {'pass' if decisions['sleep_duration_passed'] else 'fail'})"
                ),
                f"- Deterministic repeat: {'pass' if metrics['determinism_check'] else 'fail'}",
                "",
                f"Decision: **{'passed' if decisions['passed'] else 'failed'}**.",
                "",
                "## Reproduce",
                "",
                "```text",
                "uv run python scripts/validation_data/run_atus_population_validation.py",
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
    parser.add_argument("--population-size", type=int, default=20_000)
    args = parser.parse_args()
    respondent = args.raw_directory / "atusresp-2023.zip"
    activity = args.raw_directory / "atusact-2023.zip"
    hashes = {
        "atusresp-2023.zip": sha256_file(respondent),
        "atusact-2023.zip": sha256_file(activity),
    }
    expected = {
        "atusresp-2023.zip": RESPONDENT_SHA256,
        "atusact-2023.zip": ACTIVITY_SHA256,
    }
    if hashes != expected:
        raise ValueError(f"ATUS archive checksum mismatch: {hashes}")
    diaries = load_atus_2023_diaries(respondent, activity)
    partition = partition_diaries(diaries)
    model = PopulationScheduleModel(partition.development, base_seed=20260812)
    metrics = validate_population_model(
        model,
        partition.holdout,
        generated_population_size=args.population_size,
    )
    sleep_passed = metrics["daily_sleep_fraction"]["quantile_mae"] <= 0.05
    home_passed = metrics["observed_location_home_fraction"]["quantile_mae"] <= 0.05
    duration_passed = metrics["sleep_episode_duration"]["quantile_mae_minutes"] <= 30.0
    decision = {
        "daily_sleep_fraction_passed": sleep_passed,
        "home_fraction_passed": home_passed,
        "sleep_duration_passed": duration_passed,
        "determinism_passed": metrics["determinism_check"],
        "passed": bool(
            sleep_passed
            and home_passed
            and duration_passed
            and metrics["determinism_check"]
        ),
    }
    payload = {
        "artifact_version": "1.0.0",
        "created_on": datetime.now(UTC).date().isoformat(),
        "validation_category": "behavioral_holdout_validation",
        "study": {
            "study_id": "atus-2023-weighted-diary-population-holdout-v1",
            "source": {
                "publisher": "U.S. Bureau of Labor Statistics",
                "year": 2023,
                "archive_sha256": hashes,
            },
            "protocol": "data/validation/governance/atus_population_holdout_v1.json",
            "model": "weighted empirical whole-diary population sampler",
            "metrics": metrics,
            "predeclared_acceptance": decision,
            "claim_limit": "U.S. population-prior validation only; no deterministic household or Italian-population claim.",
        },
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_report(payload, args.report)
    print(json.dumps(decision, sort_keys=True))
    return 0 if decision["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
