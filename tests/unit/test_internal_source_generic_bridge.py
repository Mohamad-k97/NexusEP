"""Regression coverage for canonical ``other`` sensible gains.

Validation category: verification.
"""

from __future__ import annotations

import pytest

from nexusep.abbey.building.physics.internal_sources import (
    BuildingInternalSourceResult,
    InternalSourceRecord,
    make_thermal_gains_from_internal_sources,
)


def test_generic_internal_source_reaches_the_thermal_solver() -> None:
    sources = BuildingInternalSourceResult(
        records=[
            InternalSourceRecord(
                zone_id="zone_a",
                source_kind="generic",
                source_type="other",
                duration_minutes=60.0,
                sensible_heat_w=100.0,
            )
        ],
        expected_zone_ids=["zone_a"],
        dt_minutes=60.0,
    )

    gains = make_thermal_gains_from_internal_sources(sources)
    zone_gains = gains.get_zone_gains("zone_a")

    assert zone_gains.total_gain_w() == pytest.approx(100.0)
    assert zone_gains.convective_gain_w() + zone_gains.radiative_gain_w() == (
        pytest.approx(100.0)
    )
    assert zone_gains.gains_by_source_type_w() == {"appliances": 100.0}
