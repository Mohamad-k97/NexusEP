"""Verify exact decoding of the prescribed NZERTF virtual family schedule."""

from pathlib import Path

import pytest

from nexusep.validation_data.behavior import extract_binary_events
from nexusep.validation_data.nzertf import load_virtual_schedule_fixture

pytestmark = pytest.mark.contract
VALIDATION_CATEGORY = "verification"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    REPOSITORY_ROOT
    / "data/validation/fixtures/nist-nzertf/virtual-schedule-first-900-records.csv"
)


def test_fixture_is_a_complete_fixed_cadence_pre_gap_block() -> None:
    rows = load_virtual_schedule_fixture(FIXTURE)
    assert len(rows) == 900
    assert rows[0].time_index == 0
    assert rows[-1].time_index == 899
    assert (rows[-1].timestamp - rows[0].timestamp).total_seconds() == 899 * 60


def test_every_row_restores_all_four_stable_occupant_ids() -> None:
    rows = load_virtual_schedule_fixture(FIXTURE)
    expected = {
        "nzertf-parent-a",
        "nzertf-parent-b",
        "nzertf-child-a",
        "nzertf-child-b",
    }
    assert all({occupant.occupant_id for occupant in row.occupants} == expected for row in rows)
    assert all(
        occupant.is_present == (occupant.activity != "away")
        for row in rows
        for occupant in row.occupants
    )


def test_prescribed_actions_decode_to_named_zones_without_numeric_ids() -> None:
    rows = load_virtual_schedule_fixture(FIXTURE)
    actions = [action for row in rows for action in row.active_actions]
    assert actions
    assert {action.zone_id for action in actions} <= {
        "nzertf-downstairs",
        "nzertf-upstairs",
    }
    assert all(action.status == "active" for action in actions)


def test_virtual_load_frequency_and_duration_are_reproducible() -> None:
    rows = load_virtual_schedule_fixture(FIXTURE)
    cooktop = [
        any(action.action == "cooktop" for action in row.active_actions)
        for row in rows
    ]
    first = extract_binary_events(cooktop, interval_minutes=1.0)
    second = extract_binary_events(cooktop, interval_minutes=1.0)
    assert first == second
    assert all(event.duration_minutes >= 1.0 for event in first)


def test_lighting_power_channels_remain_nonnegative_and_separate() -> None:
    rows = load_virtual_schedule_fixture(FIXTURE)
    assert all(row.first_floor_lighting_power_w >= 0.0 for row in rows)
    assert all(row.second_floor_lighting_power_w >= 0.0 for row in rows)
