"""Production population-schedule and ATUS clock-alignment tests.

Validation category: verification.
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import asdict
from pathlib import Path

from nexusep.occupants import (
    OccupantDiaryTemplate,
    OccupantEpisode,
    PopulationScheduleModel,
)
from nexusep.validation_data.atus import load_atus_2023_diaries


def _write_zip(path: Path, member: str, rows: list[dict[str, object]]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(member, buffer.getvalue())


def test_atus_0400_diary_is_rotated_to_a_canonical_midnight_day(
    tmp_path: Path,
) -> None:
    respondent = tmp_path / "respondent.zip"
    activity = tmp_path / "activity.zip"
    _write_zip(
        respondent,
        "atusresp.dat",
        [{"TUCASEID": "202301000001", "TUFINLWGT": 2.0, "TUDIARYDAY": 2}],
    )
    _write_zip(
        activity,
        "atusact.dat",
        [
            {
                "TUCASEID": "202301000001",
                "TUACTIVITY_N": 1,
                "TUACTDUR24": 1200,
                "TRCODE": "020101",
                "TEWHERE": 1,
            },
            {
                "TUCASEID": "202301000001",
                "TUACTIVITY_N": 2,
                "TUACTDUR24": 240,
                "TRCODE": "010101",
                "TEWHERE": -1,
            },
        ],
    )

    diary = load_atus_2023_diaries(respondent, activity)[0]

    assert [
        (item.start_minute, item.end_minute_exclusive) for item in diary.episodes
    ] == [
        (0, 240),
        (240, 1440),
    ]
    assert diary.episodes[0].activity_state == "sleeping"
    assert diary.episodes[0].location_basis == "sleep_inferred_home"


def _template(identifier: str, diary_day: int) -> OccupantDiaryTemplate:
    return OccupantDiaryTemplate(
        template_id=identifier,
        survey_weight=1.0,
        diary_day=diary_day,
        episodes=(
            OccupantEpisode(
                start_minute=0,
                end_minute_exclusive=1440,
                activity_code="020101",
                activity_state="awake",
                is_home=True,
                location_basis="reported",
            ),
        ),
    )


def test_population_sampling_is_stable_and_can_preserve_day_type() -> None:
    model = PopulationScheduleModel(
        (_template("monday", 2), _template("sunday", 1)),
        base_seed=42,
    )

    first = model.sample("occupant_a", day_index=3, diary_day=2)
    repeated = model.sample("occupant_a", day_index=3, diary_day=2)

    assert asdict(first) == asdict(repeated)
    assert first.template_id == "monday"
    assert first.diary_day == 2
