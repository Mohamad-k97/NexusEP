"""
ABBEY physics Phase 1 test.

Checks only graph structure.
No thermal, airflow, CO2, daylight, or noise physics.
"""

from nexusep.abbey.building.physics import (
    BuildingPhysicsGraph,
    DwellingNode,
    ZoneNode,
    ZoneConnection,
    BoundaryConnection,
)


def make_dummy_graph():
    building_id = "dummy_building_1"
    dwelling_id = "dwelling_1"

    zones = {
        "living_room": ZoneNode(
            zone_id="living_room",
            building_id=building_id,
            dwelling_id=dwelling_id,
            zone_name="Living room",
            zone_use="living_room",
            zone_scope="private",
            floor_area_m2=25.0,
            height_m=2.7,
        ),
        "kitchen": ZoneNode(
            zone_id="kitchen",
            building_id=building_id,
            dwelling_id=dwelling_id,
            zone_name="Kitchen",
            zone_use="kitchen",
            zone_scope="private",
            floor_area_m2=12.0,
            height_m=2.7,
        ),
        "bedroom_1": ZoneNode(
            zone_id="bedroom_1",
            building_id=building_id,
            dwelling_id=dwelling_id,
            zone_name="Bedroom 1",
            zone_use="bedroom",
            zone_scope="private",
            floor_area_m2=16.0,
            height_m=2.7,
        ),
        "bathroom": ZoneNode(
            zone_id="bathroom",
            building_id=building_id,
            dwelling_id=dwelling_id,
            zone_name="Bathroom",
            zone_use="bathroom",
            zone_scope="private",
            floor_area_m2=6.0,
            height_m=2.7,
        ),
        "shared_corridor": ZoneNode(
            zone_id="shared_corridor",
            building_id=building_id,
            dwelling_id=None,
            zone_name="Shared corridor",
            zone_use="corridor",
            zone_scope="shared",
            floor_area_m2=20.0,
            height_m=2.7,
        ),
    }

    dwellings = {
        dwelling_id: DwellingNode(
            dwelling_id=dwelling_id,
            building_id=building_id,
            zone_ids=[
                "living_room",
                "kitchen",
                "bedroom_1",
                "bathroom",
            ],
        )
    }

    zone_connections = {
        "living_kitchen_wall": ZoneConnection(
            connection_id="living_kitchen_wall",
            from_zone_id="living_room",
            to_zone_id="kitchen",
            connection_type="internal_wall",
            area_m2=8.0,
        ),
        "living_bedroom_door": ZoneConnection(
            connection_id="living_bedroom_door",
            from_zone_id="living_room",
            to_zone_id="bedroom_1",
            connection_type="door",
            area_m2=1.8,
            is_openable=True,
            open_fraction=0.3,
        ),
        "living_corridor_door": ZoneConnection(
            connection_id="living_corridor_door",
            from_zone_id="living_room",
            to_zone_id="shared_corridor",
            connection_type="door",
            area_m2=2.0,
            is_openable=True,
            open_fraction=0.2,
        ),
    }

    boundary_connections = {
        "living_south_window": BoundaryConnection(
            connection_id="living_south_window",
            zone_id="living_room",
            connection_type="window",
            area_m2=4.0,
            orientation_deg=180.0,
            is_openable=True,
            open_fraction=0.0,
        ),
        "kitchen_east_window": BoundaryConnection(
            connection_id="kitchen_east_window",
            zone_id="kitchen",
            connection_type="window",
            area_m2=2.0,
            orientation_deg=90.0,
            is_openable=True,
            open_fraction=0.0,
        ),
        "bedroom_north_wall": BoundaryConnection(
            connection_id="bedroom_north_wall",
            zone_id="bedroom_1",
            connection_type="external_wall",
            area_m2=10.0,
            orientation_deg=0.0,
        ),
        "bathroom_outside_boundary": BoundaryConnection(
            connection_id="bathroom_outside_boundary",
            zone_id="bathroom",
            connection_type="outside_boundary",
            area_m2=4.0,
        ),
    }

    return BuildingPhysicsGraph(
        building_id=building_id,
        dwellings=dwellings,
        zones=zones,
        zone_connections=zone_connections,
        boundary_connections=boundary_connections,
    )


def run_tests():
    graph = make_dummy_graph()

    print("Created graph:")
    print("building_id:", graph.building_id)
    print("dwelling_ids:", graph.dwelling_ids())
    print("zone_ids:", graph.all_zone_ids())

    assert graph.building_id == "dummy_building_1"

    # All zones exist.
    assert set(graph.all_zone_ids()) == {
        "living_room",
        "kitchen",
        "bedroom_1",
        "bathroom",
        "shared_corridor",
    }

    print("OK: all zones exist")

    # Dwelling ownership.
    assert set(graph.zone_ids_for_dwelling("dwelling_1")) == {
        "living_room",
        "kitchen",
        "bedroom_1",
        "bathroom",
    }

    assert graph.zone_belongs_to_dwelling("kitchen", "dwelling_1")
    assert not graph.zone_belongs_to_dwelling("shared_corridor", "dwelling_1")

    print("OK: dwelling ownership works")

    # Private/shared scopes.
    assert set(graph.private_zone_ids()) == {
        "living_room",
        "kitchen",
        "bedroom_1",
        "bathroom",
    }

    assert set(graph.shared_zone_ids()) == {
        "shared_corridor",
    }

    assert graph.zone_is_shared("shared_corridor")

    print("OK: private/shared scopes work")

    # Adjacency.
    living_adjacent = set(graph.adjacent_zone_ids("living_room"))

    assert living_adjacent == {
        "kitchen",
        "bedroom_1",
        "shared_corridor",
    }

    assert set(graph.adjacent_zone_ids_by_connection_type("living_room", "door")) == {
        "bedroom_1",
        "shared_corridor",
    }

    assert set(graph.adjacent_zone_ids_by_connection_type("living_room", "internal_wall")) == {
        "kitchen",
    }

    print("OK: adjacency works")

    # Outside connections.
    outside_connected = set(graph.outside_connected_zone_ids())

    assert outside_connected == {
        "living_room",
        "kitchen",
        "bedroom_1",
        "bathroom",
    }

    print("OK: outside connections work")

    # Window connections.
    assert set(graph.window_connected_zone_ids()) == {
        "living_room",
        "kitchen",
    }

    assert graph.has_window("living_room")
    assert graph.has_window("kitchen")
    assert not graph.has_window("bathroom")

    print("OK: window connections work")

    # Orientation.
    living_windows = graph.window_connections_for_zone("living_room")
    assert len(living_windows) == 1
    assert living_windows[0].orientation_deg == 180.0

    south_windows = graph.window_connections_facing(
        orientation_deg=180.0,
        tolerance_deg=30.0,
    )

    assert len(south_windows) == 1
    assert south_windows[0].zone_id == "living_room"

    print("OK: orientation works")

    # Validation should run without error.
    graph.validate()

    print("\nPHASE 1 PHYSICS GRAPH OK ✅")


if __name__ == "__main__":
    run_tests()