"""Verification: solar position against NREL SPA and time/angle contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from nexusep.abbey.building.physics.solar import (
    calculate_solar_day_events,
    calculate_solar_position,
)


def test_official_nrel_spa_tester_vector() -> None:
    # Published by NREL in spa_tester.c.  Only the scalar test result is
    # recorded here; the non-redistributable NREL source remains local-only.
    timestamp = datetime(
        2003, 10, 17, 12, 30, 30, tzinfo=timezone(timedelta(hours=-7))
    )
    result = calculate_solar_position(
        timestamp,
        latitude_deg=39.742476,
        longitude_deg=-105.1786,
        elevation_m=1830.14,
        atmospheric_pressure_pa=82_000.0,
        outdoor_temperature_c=11.0,
        delta_t_seconds=67.0,
        atmospheric_refraction_deg=0.5667,
    )
    assert result.apparent_zenith_deg == pytest.approx(50.111622, abs=0.000_001)
    assert result.azimuth_deg == pytest.approx(194.340241, abs=0.000_001)


def test_official_nrel_spa_sunrise_and_sunset_vector() -> None:
    offset = timezone(timedelta(hours=-7))
    events = calculate_solar_day_events(
        datetime(2003, 10, 17, tzinfo=offset),
        latitude_deg=39.742476,
        longitude_deg=-105.1786,
        delta_t_seconds=67.0,
    )
    expected_sunrise = datetime(2003, 10, 17, 6, 12, 43, tzinfo=offset)
    expected_sunset = datetime(2003, 10, 17, 17, 20, 19, tzinfo=offset)
    assert abs((events.sunrise - expected_sunrise).total_seconds()) < 0.5
    assert abs((events.sunset - expected_sunset).total_seconds()) < 0.5


@pytest.mark.parametrize(
    ("timestamp", "latitude"),
    [
        (datetime(2024, 2, 29, 12, tzinfo=UTC), 45.0),
        (datetime(2024, 3, 20, 12, tzinfo=UTC), 45.0),
        (datetime(2024, 6, 20, 12, tzinfo=UTC), 45.0),
        (datetime(2024, 9, 22, 12, tzinfo=UTC), -33.9),
        (datetime(2024, 12, 21, 12, tzinfo=UTC), -33.9),
    ],
)
def test_spa_handles_leap_day_seasons_and_both_hemispheres(
    timestamp: datetime, latitude: float
) -> None:
    result = calculate_solar_position(
        timestamp, latitude_deg=latitude, longitude_deg=0.0
    )
    assert 0.0 <= result.azimuth_deg < 360.0
    assert 0.0 <= result.zenith_deg <= 180.0


def test_same_instant_is_invariant_to_utc_offset_and_dst_fold() -> None:
    utc_instant = datetime(2025, 10, 26, 1, 30, tzinfo=UTC)
    local = utc_instant.astimezone(timezone(timedelta(hours=1)))
    utc_result = calculate_solar_position(
        utc_instant, latitude_deg=45.0, longitude_deg=8.0
    )
    local_result = calculate_solar_position(
        local, latitude_deg=45.0, longitude_deg=8.0
    )
    assert local_result.zenith_deg == pytest.approx(utc_result.zenith_deg, abs=1e-10)
    assert local_result.azimuth_deg == pytest.approx(utc_result.azimuth_deg, abs=1e-10)


@pytest.mark.parametrize(
    "utc_instant",
    (
        datetime(2025, 3, 30, 0, 30, tzinfo=UTC),
        datetime(2025, 3, 30, 1, 30, tzinfo=UTC),
        datetime(2025, 10, 26, 0, 30, tzinfo=UTC),
        datetime(2025, 10, 26, 1, 30, tzinfo=UTC),
    ),
)
def test_civil_dst_transition_preserves_physical_instant(utc_instant: datetime) -> None:
    local = utc_instant.astimezone(ZoneInfo("Europe/Rome"))
    utc_result = calculate_solar_position(
        utc_instant, latitude_deg=45.0, longitude_deg=8.0
    )
    local_result = calculate_solar_position(
        local, latitude_deg=45.0, longitude_deg=8.0
    )
    assert local_result.zenith_deg == pytest.approx(utc_result.zenith_deg, abs=1e-10)
    assert local_result.azimuth_deg == pytest.approx(utc_result.azimuth_deg, abs=1e-10)


def test_sunrise_sunset_transition_and_night_behavior() -> None:
    before = calculate_solar_position(
        datetime(2024, 6, 20, 2, 30, tzinfo=UTC),
        latitude_deg=45.0,
        longitude_deg=8.0,
    )
    after = calculate_solar_position(
        datetime(2024, 6, 20, 5, 0, tzinfo=UTC),
        latitude_deg=45.0,
        longitude_deg=8.0,
    )
    night = calculate_solar_position(
        datetime(2024, 6, 20, 23, 0, tzinfo=UTC),
        latitude_deg=45.0,
        longitude_deg=8.0,
    )
    assert not before.is_sun_up
    assert after.is_sun_up
    assert not night.is_sun_up
    assert night.zenith_deg > 90.0
    assert 0.0 <= night.azimuth_deg < 360.0


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        calculate_solar_position(
            datetime(2024, 6, 20, 12, tzinfo=UTC).replace(tzinfo=None),
            latitude_deg=45.0,
            longitude_deg=8.0,
        )
