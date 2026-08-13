"""Phase 4.25 verification of the explicitly limited acoustic placeholder."""

from types import SimpleNamespace

import numpy as np
import pytest

from nexusep.abbey.arrays import acoustic_kernels as array_acoustics
from nexusep.abbey.building.physics.acoustics import (
    OutdoorAcousticBoundary,
    add_noise_levels_db,
    attenuate_noise_db,
    calculate_interzone_noise_contributions_by_zone,
    calculate_outdoor_noise_contribution_db_by_zone,
    db_to_energy,
    energy_to_db,
    normalize_noise_discomfort_input,
)
from nexusep.abbey.building.physics.graph import BoundaryConnection, ZoneConnection

pytestmark = pytest.mark.unit
VALIDATION_CATEGORY = "verification"


def _building(*zone_ids: str) -> SimpleNamespace:
    return SimpleNamespace(all_zone_ids=lambda: list(zone_ids))


def _window(open_fraction: float) -> BoundaryConnection:
    return BoundaryConnection(
        connection_id=f"window-{open_fraction:g}",
        zone_id="zone-a",
        connection_type="window",
        area_m2=2.0,
        orientation_deg=180.0,
        is_openable=True,
        open_fraction=open_fraction,
        window_sound_reduction_db=25.0,
        outside_noise_transmission_factor=0.1,
    )


def _outdoor_contribution(window: BoundaryConnection) -> float:
    graph = SimpleNamespace(
        boundary_connections={window.connection_id: window},
        zone_connections={},
    )
    return calculate_outdoor_noise_contribution_db_by_zone(
        building_model=_building("zone-a"),
        physics_graph=graph,
        outdoor_boundary=OutdoorAcousticBoundary(outdoor_noise_db=80.0),
    )["zone-a"]


def test_decibel_energy_round_trip_and_equal_source_arithmetic() -> None:
    assert energy_to_db(db_to_energy(47.5)) == pytest.approx(47.5)
    expected = 60.0 + 10.0 * np.log10(2.0)
    assert add_noise_levels_db([60.0, 60.0], default_db=0.0) == pytest.approx(
        expected
    )


def test_source_combination_is_order_independent_and_backend_consistent() -> None:
    levels = [35.0, 50.0, 42.0]
    object_result = add_noise_levels_db(levels, default_db=0.0)
    reversed_result = add_noise_levels_db(list(reversed(levels)), default_db=0.0)
    array_result = array_acoustics.add_noise_levels_db_from_array(
        np.asarray(levels, dtype=np.float64),
        n_levels=len(levels),
        background_db=None,
        default_db=0.0,
    )
    assert object_result == pytest.approx(reversed_result)
    assert array_result == pytest.approx(object_result)


def test_more_attenuation_never_increases_received_level() -> None:
    object_levels = [attenuate_noise_db(80.0, value) for value in (0.0, 10.0, 40.0)]
    array_levels = [
        array_acoustics.attenuate_noise_db(80.0, value)
        for value in (0.0, 10.0, 40.0)
    ]
    assert object_levels == pytest.approx([80.0, 70.0, 40.0])
    assert array_levels == pytest.approx(object_levels)


def test_open_window_ordering_is_closed_below_partial_below_open() -> None:
    closed = _outdoor_contribution(_window(0.0))
    partial = _outdoor_contribution(_window(0.5))
    opened = _outdoor_contribution(_window(1.0))
    assert closed < partial < opened
    assert opened == pytest.approx(80.0)


def test_equal_interzone_sources_propagate_symmetrically() -> None:
    connection = ZoneConnection(
        connection_id="door-a-b",
        from_zone_id="zone-a",
        to_zone_id="zone-b",
        connection_type="door",
        door_sound_reduction_db=20.0,
    )
    graph = SimpleNamespace(
        boundary_connections={},
        zone_connections={connection.connection_id: connection},
    )
    contributions = calculate_interzone_noise_contributions_by_zone(
        building_model=_building("zone-a", "zone-b"),
        physics_graph=graph,
        source_noise_db_by_zone={"zone-a": 60.0, "zone-b": 60.0},
    )
    assert contributions == {"zone-a": [40.0], "zone-b": [40.0]}


@pytest.mark.parametrize("noise_db", (0.0, 35.0, 55.0, 75.0, 140.0))
def test_normalized_comfort_response_is_bounded_and_backend_consistent(
    noise_db: float,
) -> None:
    object_result = normalize_noise_discomfort_input(noise_db)
    array_result = array_acoustics.normalize_noise_discomfort_input(noise_db)
    assert 0.0 <= object_result <= 1.0
    assert array_result == pytest.approx(object_result)


def test_normalized_comfort_response_is_monotonic() -> None:
    values = [normalize_noise_discomfort_input(value) for value in range(141)]
    assert values == sorted(values)
    assert values[35] == 0.0
    assert values[75] == 1.0
