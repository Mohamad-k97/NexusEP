"""Current physics-graph structure regression.

Provenance: reconstructed from the current graph/factory contract after the
surviving typo-named Phase 1 script proved to target removed ``ZoneNode`` and
``DwellingNode`` APIs. This is newly added regression coverage, not a verbatim
restoration.
"""

from nexusep.abbey.building.factory import (
    default_family_ids,
    make_default_family_building,
    make_default_family_physics_graph,
)


def test_physics_graph_uses_building_model_as_source_of_truth():
    building = make_default_family_building()
    graph = make_default_family_physics_graph(building)
    _, dwelling_id, _ = default_family_ids()

    assert graph.building_model is building
    assert set(graph.zone_ids_for_building()) == set(
        building.all_zone_models()
    )
    assert set(graph.zone_ids_for_dwelling(dwelling_id)) == set(
        building.dwellings[dwelling_id].zone_models
    )
    graph.validate()


def test_physics_graph_exposes_outside_and_window_connections():
    building = make_default_family_building()
    graph = make_default_family_physics_graph(building)

    outside_zone_ids = set(graph.outside_connected_zone_ids())
    window_zone_ids = set(graph.window_connected_zone_ids())

    assert window_zone_ids
    assert window_zone_ids <= outside_zone_ids
    assert all(graph.has_window(zone_id) for zone_id in window_zone_ids)
    assert all(graph.window_connections_for_zone(zone_id) for zone_id in window_zone_ids)
    assert graph.window_connections_facing(orientation_deg=180.0, tolerance_deg=180.0)
