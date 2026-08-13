"""
Factory helpers for creating default ABBEY buildings.

Phase 10:
- one dummy building
- one dummy dwelling
- one family household
- private dwelling zones only
"""

from typing import Dict, Tuple, Optional

from nexusep.abbey.building.model import (
    ZoneModel,
    DwellingModel,
    BuildingModel,
)

from nexusep.abbey.building.systems import (
    ZoneSystemSpec,
    DwellingSystemSpec,
    BuildingSystemSpec,
    ZoneControlState,
)

from nexusep.abbey.building.physics.graph import (
    BuildingPhysicsGraph,
    ZoneConnection,
    BoundaryConnection,
)

def make_default_family_building() -> BuildingModel:
    """
    Create the default one-family dwelling inside one building.

    MVP:
        building_1
            dwelling_1
                family_1
                private zones

    Future-ready:
        the BuildingModel can later contain multiple dwellings and shared zones.
    """

    building_id = "dummy_building_1"
    dwelling_id = "dwelling_1"
    household_id = "family_1"

    zone_models = {}
    system_specs = {}
    control_states = {}

    zone_inputs = [
        {
            "role": "living_room",
            "name": "Living room",
            "area": 28.0,
            "height": 2.7,
            "ua": 75.0,
            "thermal_capacity": 4_500_000.0,
            "initial_temp": 20.0,
            "initial_co2": 600.0,
            "heating_mode": "semi_auto",
            "heating_setpoint": 20.5,
            "has_heating": True,
            "heating_w_m2": 80.0,
            "has_cooling": False,
            "cooling_w_m2": 0.0,
            "has_ventilation": True,
            "ventilation_ach": 0.5,
            "has_lighting": True,
            "lighting_w_m2": 6.0,
            "has_window": True,
            "has_shading": True,
        },
        {
            "role": "bedroom_1",
            "name": "Parents bedroom",
            "area": 16.0,
            "height": 2.7,
            "ua": 45.0,
            "thermal_capacity": 3_000_000.0,
            "initial_temp": 19.5,
            "initial_co2": 580.0,
            "heating_mode": "semi_auto",
            "heating_setpoint": 19.5,
            "has_heating": True,
            "heating_w_m2": 75.0,
            "has_cooling": False,
            "cooling_w_m2": 0.0,
            "has_ventilation": True,
            "ventilation_ach": 0.5,
            "has_lighting": True,
            "lighting_w_m2": 5.0,
            "has_window": True,
            "has_shading": True,
        },
        {
            "role": "bedroom_2",
            "name": "Child bedroom",
            "area": 13.0,
            "height": 2.7,
            "ua": 40.0,
            "thermal_capacity": 2_500_000.0,
            "initial_temp": 19.5,
            "initial_co2": 575.0,
            "heating_mode": "semi_auto",
            "heating_setpoint": 19.5,
            "has_heating": True,
            "heating_w_m2": 75.0,
            "has_cooling": False,
            "cooling_w_m2": 0.0,
            "has_ventilation": True,
            "ventilation_ach": 0.5,
            "has_lighting": True,
            "lighting_w_m2": 5.0,
            "has_window": True,
            "has_shading": True,
        },
        {
            "role": "kitchen",
            "name": "Kitchen",
            "area": 12.0,
            "height": 2.7,
            "ua": 45.0,
            "thermal_capacity": 2_300_000.0,
            "initial_temp": 20.0,
            "initial_co2": 610.0,
            "heating_mode": "semi_auto",
            "heating_setpoint": 20.0,
            "has_heating": True,
            "heating_w_m2": 70.0,
            "has_cooling": False,
            "cooling_w_m2": 0.0,
            "has_ventilation": True,
            "ventilation_ach": 0.8,
            "has_lighting": True,
            "lighting_w_m2": 7.0,
            "has_window": True,
            "has_shading": True,
        },
        {
            "role": "bathroom",
            "name": "Bathroom",
            "area": 6.0,
            "height": 2.7,
            "ua": 35.0,
            "thermal_capacity": 1_200_000.0,
            "initial_temp": 21.0,
            "initial_co2": 560.0,
            "heating_mode": "manual",
            "heating_setpoint": 21.0,
            "has_heating": True,
            "heating_w_m2": 100.0,
            "has_cooling": False,
            "cooling_w_m2": 0.0,
            "has_ventilation": True,
            "ventilation_ach": 1.2,
            "has_lighting": True,
            "lighting_w_m2": 8.0,
            "has_window": True,
            "has_shading": False,
        },
        {
            "role": "laundry",
            "name": "Laundry",
            "area": 5.0,
            "height": 2.7,
            "ua": 25.0,
            "thermal_capacity": 900_000.0,
            "initial_temp": 19.0,
            "initial_co2": 570.0,
            "heating_mode": "off",
            "heating_setpoint": 18.0,
            "has_heating": False,
            "heating_w_m2": 0.0,
            "has_cooling": False,
            "cooling_w_m2": 0.0,
            "has_ventilation": True,
            "ventilation_ach": 0.8,
            "has_lighting": True,
            "lighting_w_m2": 6.0,
            "has_window": False,
            "has_shading": False,
        },
        {
            "role": "office",
            "name": "Office",
            "area": 10.0,
            "height": 2.7,
            "ua": 35.0,
            "thermal_capacity": 1_800_000.0,
            "initial_temp": 20.0,
            "initial_co2": 590.0,
            "heating_mode": "semi_auto",
            "heating_setpoint": 20.0,
            "has_heating": True,
            "heating_w_m2": 75.0,
            "has_cooling": False,
            "cooling_w_m2": 0.0,
            "has_ventilation": True,
            "ventilation_ach": 0.5,
            "has_lighting": True,
            "lighting_w_m2": 7.0,
            "has_window": True,
            "has_shading": True,
        },
        {
            "role": "entrance",
            "name": "Entrance",
            "area": 5.0,
            "height": 2.7,
            "ua": 30.0,
            "thermal_capacity": 900_000.0,
            "initial_temp": 18.5,
            "initial_co2": 550.0,
            "heating_mode": "off",
            "heating_setpoint": 18.0,
            "has_heating": False,
            "heating_w_m2": 0.0,
            "has_cooling": False,
            "cooling_w_m2": 0.0,
            "has_ventilation": False,
            "ventilation_ach": 0.4,
            "has_lighting": True,
            "lighting_w_m2": 5.0,
            "has_window": False,
            "has_shading": False,
        },
    ]

    private_zone_ids = []

    for item in zone_inputs:
        zone_id = dwelling_id + "_" + item["role"]
        volume_m3 = float(item["area"]) * float(item["height"])
        role = item["role"]

        if role.startswith("bedroom"):
            zone_use = "bedroom"
        else:
            zone_use = role

        has_heating = bool(item.get("has_heating", True))
        has_cooling = bool(item.get("has_cooling", False))
        has_ventilation = bool(item.get("has_ventilation", True))
        has_lighting = bool(item.get("has_lighting", True))
        has_window = bool(item.get("has_window", False))
        has_shading = bool(item.get("has_shading", False))

        heating_capacity_w = (
            float(item["heating_w_m2"]) * float(item["area"])
            if has_heating
            else 0.0
        )

        cooling_capacity_w = (
            float(item["cooling_w_m2"]) * float(item["area"])
            if has_cooling
            else 0.0
        )

        ventilation_flow_m3_h = (
            float(item["ventilation_ach"]) * volume_m3
            if has_ventilation
            else 0.0
        )

        lighting_power_w = (
            float(item["lighting_w_m2"]) * float(item["area"])
            if has_lighting
            else 0.0
        )

        zone_model = ZoneModel(
            zone_id=zone_id,
            zone_name=item["name"],
            dwelling_id=dwelling_id,
            building_id=building_id,
            zone_scope="private",
            zone_use=zone_use,
            floor_area_m2=float(item["area"]),
            height_m=float(item["height"]),
            volume_m3=volume_m3,
            ua_w_per_k=float(item["ua"]),
            thermal_envelope_model="graph_boundaries",
            envelope_provenance="pending_default_family_graph_compilation",
            thermal_capacity_j_per_k=float(item["thermal_capacity"]),
            initial_temp_c=float(item["initial_temp"]),
            initial_co2_ppm=float(item["initial_co2"]),
            mechanical_ventilation_available=has_ventilation,
            mechanical_ventilation_flow_m3_h=ventilation_flow_m3_h,
        )

        system_spec = ZoneSystemSpec(
            zone_id=zone_id,
            dwelling_id=dwelling_id,
            building_id=building_id,
            heating_capacity_w=heating_capacity_w,
            cooling_capacity_w=cooling_capacity_w,
            ventilation_flow_m3_h=ventilation_flow_m3_h,
            lighting_power_w=lighting_power_w,
            has_heating=has_heating,
            has_cooling=has_cooling,
            has_ventilation=has_ventilation,
            has_lighting=has_lighting,
            has_operable_window=has_window,
            has_shading=has_shading,
        )

        control_state = ZoneControlState(
            zone_id=zone_id,
            dwelling_id=dwelling_id,
            building_id=building_id,
            heating_mode=item["heating_mode"],
            heating_setpoint_c=float(item["heating_setpoint"]),
            manual_heating_on=False,
            cooling_mode="off",
            cooling_setpoint_c=26.0,
            manual_cooling_on=False,
            ventilation_mode="manual",
            manual_ventilation_on=has_ventilation,
            lighting_mode="manual",
            manual_lights_on=False,
            window_mode="manual",
            manual_window_open=False,
            shading_mode="manual",
            manual_curtain_open=True,
        )

        private_zone_ids.append(zone_id)
        zone_models[zone_id] = zone_model
        system_specs[zone_id] = system_spec
        control_states[zone_id] = control_state

    dwelling = DwellingModel(
        dwelling_id=dwelling_id,
        building_id=building_id,
        household_id=household_id,
        private_zone_ids=private_zone_ids,
        zone_models=zone_models,
        system_specs=system_specs,
        control_states=control_states,
    )

    building = BuildingModel(
        building_id=building_id,
        dwelling_ids=[dwelling_id],
        dwellings={dwelling_id: dwelling},
        shared_zone_ids=[],
        shared_zone_models={},
        shared_zone_states={},
        building_system_specs={
            "default": BuildingSystemSpec(
                building_id=building_id,
                has_central_heating=False,
                has_central_cooling=False,
                has_central_ventilation=False,
                has_central_dhw=False,
                central_system_type="none",
            )
        },
    )

    return building

def make_default_family_physics_graph(
    building_model: Optional[BuildingModel] = None,
    dwelling_id: str = "dwelling_1",
) -> BuildingPhysicsGraph:
    """
    Create the default physical topology for the default family dwelling.

    Phase 11.1:
        - Adds explicit room-to-room adjacency.
        - Does not yet solve interzone heat transfer.
        - Does not yet connect this graph to the default runner.

    The topology is deliberately simple and inspectable.
    Later phases can replace this with imported geometry/topology.
    """

    if building_model is None:
        building_model = make_default_family_building()

    if dwelling_id not in building_model.dwellings:
        if len(building_model.dwellings) == 1:
            dwelling_id = next(iter(building_model.dwellings.keys()))
        else:
            raise ValueError(
                "dwelling_id "
                + str(dwelling_id)
                + " not found in building_model."
            )

    zone_ids = set(building_model.all_zone_ids())

    def zid(role: str) -> str:
        return dwelling_id + "_" + role

    def require_zone(role: str) -> str:
        zone_id = zid(role)

        if zone_id not in zone_ids:
            raise ValueError(
                "Default family physics graph expected zone "
                + zone_id
                + " but it was not found in building_model."
            )

        return zone_id

    living = require_zone("living_room")
    kitchen = require_zone("kitchen")
    bedroom_1 = require_zone("bedroom_1")
    bedroom_2 = require_zone("bedroom_2")
    bathroom = require_zone("bathroom")
    laundry = require_zone("laundry")
    office = require_zone("office")
    entrance = require_zone("entrance")

    zone_connections = {}
    boundary_connections = {}
    def add_internal_wall(
        connection_id: str,
        from_zone_id: str,
        to_zone_id: str,
        area_m2: float,
        u_value_w_m2k: float = 1.8,
    ) -> None:
        zone_connections[connection_id] = ZoneConnection(
            connection_id=connection_id,
            from_zone_id=from_zone_id,
            to_zone_id=to_zone_id,
            connection_type="internal_wall",
            area_m2=area_m2,
            is_openable=False,
            open_fraction=0.0,
            max_opening_area_m2=None,
            base_airflow_m3_h=0.0,
            u_value_w_m2k=u_value_w_m2k,
        )

    def add_door(
        connection_id: str,
        from_zone_id: str,
        to_zone_id: str,
        open_fraction: float = 0.0,
        door_area_m2: float = 1.7,
        max_opening_area_m2: float = 1.5,
        u_value_w_m2k: float = 2.5,
        base_airflow_m3_h: float = 5.0,
    ) -> None:
        zone_connections[connection_id] = ZoneConnection(
            connection_id=connection_id,
            from_zone_id=from_zone_id,
            to_zone_id=to_zone_id,
            connection_type="door",
            area_m2=door_area_m2,
            is_openable=True,
            open_fraction=open_fraction,
            max_opening_area_m2=max_opening_area_m2,
            base_airflow_m3_h=base_airflow_m3_h,
            u_value_w_m2k=u_value_w_m2k,
        )
    def add_window(
        connection_id: str,
        zone_id: str,
        area_m2: float,
        orientation_deg: float,
        max_opening_area_m2: float,
        window_u_value_w_m2k: float = 1.6,
        glazing_transmittance: float = 0.60,
        window_visible_transmittance: float = 0.60,
        solar_heat_gain_coefficient: float = 0.50,
        frame_fraction: float = 0.20,
        shading_factor: float = 1.00,
        discharge_coefficient: float = 0.60,
    ) -> None:
        boundary_connections[connection_id] = BoundaryConnection(
            connection_id=connection_id,
            zone_id=zone_id,
            connection_type="window",
            area_m2=area_m2,
            orientation_deg=orientation_deg,
            is_window=True,
            is_openable=True,
            open_fraction=0.0,
            max_opening_area_m2=max_opening_area_m2,
            discharge_coefficient=discharge_coefficient,
            window_u_value_w_m2k=window_u_value_w_m2k,
            glazing_transmittance=glazing_transmittance,
            window_visible_transmittance=window_visible_transmittance,
            solar_heat_gain_coefficient=solar_heat_gain_coefficient,
            frame_fraction=frame_fraction,
            shading_factor=shading_factor,
            curtain_open=True,
        )
    def add_external_wall(
        connection_id: str,
        zone_id: str,
        ua_w_per_k: float,
        orientation_deg: float,
        u_value_w_m2k: float = 1.2,
    ) -> None:
        boundary_connections[connection_id] = BoundaryConnection(
            connection_id=connection_id,
            zone_id=zone_id,
            connection_type="external_wall",
            area_m2=float(ua_w_per_k) / float(u_value_w_m2k),
            orientation_deg=orientation_deg,
            u_value_w_m2k=u_value_w_m2k,
        )
    # ------------------------------------------------------------
    # Main circulation / access topology.
    # ------------------------------------------------------------
    add_door(
        connection_id="door_entrance_living_room",
        from_zone_id=entrance,
        to_zone_id=living,
        open_fraction=0.0,
    )

    add_door(
        connection_id="door_living_room_kitchen",
        from_zone_id=living,
        to_zone_id=kitchen,
        open_fraction=0.5,
        door_area_m2=2.5,
        max_opening_area_m2=2.2,
        base_airflow_m3_h=15.0,
    )

    add_door(
        connection_id="door_living_room_bedroom_1",
        from_zone_id=living,
        to_zone_id=bedroom_1,
        open_fraction=0.0,
    )

    add_door(
        connection_id="door_living_room_bedroom_2",
        from_zone_id=living,
        to_zone_id=bedroom_2,
        open_fraction=0.0,
    )

    add_door(
        connection_id="door_living_room_office",
        from_zone_id=living,
        to_zone_id=office,
        open_fraction=0.0,
    )

    add_door(
        connection_id="door_living_room_bathroom",
        from_zone_id=living,
        to_zone_id=bathroom,
        open_fraction=0.0,
    )

    add_door(
        connection_id="door_kitchen_laundry",
        from_zone_id=kitchen,
        to_zone_id=laundry,
        open_fraction=0.0,
    )

    # ------------------------------------------------------------
    # Internal partitions.
    # These are separate from doors so the thermal adapter can later
    # treat wall conduction and door/opening coupling separately.
    # ------------------------------------------------------------
    add_internal_wall(
        connection_id="wall_living_room_bedroom_1",
        from_zone_id=living,
        to_zone_id=bedroom_1,
        area_m2=9.0,
        u_value_w_m2k=1.8,
    )

    add_internal_wall(
        connection_id="wall_living_room_bedroom_2",
        from_zone_id=living,
        to_zone_id=bedroom_2,
        area_m2=8.0,
        u_value_w_m2k=1.8,
    )

    add_internal_wall(
        connection_id="wall_living_room_office",
        from_zone_id=living,
        to_zone_id=office,
        area_m2=7.0,
        u_value_w_m2k=1.8,
    )

    add_internal_wall(
        connection_id="wall_living_room_bathroom",
        from_zone_id=living,
        to_zone_id=bathroom,
        area_m2=6.0,
        u_value_w_m2k=1.8,
    )

    add_internal_wall(
        connection_id="wall_living_room_kitchen",
        from_zone_id=living,
        to_zone_id=kitchen,
        area_m2=5.0,
        u_value_w_m2k=1.8,
    )

    add_internal_wall(
        connection_id="wall_kitchen_laundry",
        from_zone_id=kitchen,
        to_zone_id=laundry,
        area_m2=5.0,
        u_value_w_m2k=1.8,
    )

    add_internal_wall(
        connection_id="wall_bathroom_laundry",
        from_zone_id=bathroom,
        to_zone_id=laundry,
        area_m2=4.0,
        u_value_w_m2k=1.8,
    )
    # ------------------------------------------------------------
    # Outside/window boundary topology.
    #
    # Phase 12.1:
    #     Static window geometry belongs to BoundaryConnection.
    #     Dynamic opening state still belongs to window operation inputs.
    #
    # Orientation convention:
    #     0   = north
    #     90  = east
    #     180 = south
    #     270 = west
    # ------------------------------------------------------------
    add_window(
        connection_id="window_living_room_south",
        zone_id=living,
        area_m2=4.0,
        orientation_deg=180.0,
        max_opening_area_m2=1.8,
    )

    add_window(
        connection_id="window_bedroom_1_east",
        zone_id=bedroom_1,
        area_m2=2.2,
        orientation_deg=90.0,
        max_opening_area_m2=1.0,
    )

    add_window(
        connection_id="window_bedroom_2_west",
        zone_id=bedroom_2,
        area_m2=1.8,
        orientation_deg=270.0,
        max_opening_area_m2=0.8,
    )

    add_window(
        connection_id="window_kitchen_south_east",
        zone_id=kitchen,
        area_m2=1.6,
        orientation_deg=135.0,
        max_opening_area_m2=0.7,
    )

    add_window(
        connection_id="window_bathroom_north",
        zone_id=bathroom,
        area_m2=0.6,
        orientation_deg=0.0,
        max_opening_area_m2=0.3,
        glazing_transmittance=0.35,
        window_visible_transmittance=0.35,
        solar_heat_gain_coefficient=0.35,
    )

    add_window(
        connection_id="window_office_west",
        zone_id=office,
        area_m2=1.5,
        orientation_deg=270.0,
        max_opening_area_m2=0.7,
    )

    # The graph is the active envelope source. The areas below are a declared
    # one-time migration from the example factory's legacy aggregate UA inputs;
    # ZoneModel aggregate area and UA are then derived back from these edges.
    orientation_by_role = {
        "living_room": 180.0,
        "bedroom_1": 90.0,
        "bedroom_2": 270.0,
        "kitchen": 135.0,
        "bathroom": 0.0,
        "laundry": 0.0,
        "office": 270.0,
        "entrance": 0.0,
    }
    for role, orientation_deg in orientation_by_role.items():
        zone_id = require_zone(role)
        add_external_wall(
            connection_id="external_wall_" + role,
            zone_id=zone_id,
            ua_w_per_k=building_model.get_zone_model(zone_id).ua_w_per_k,
            orientation_deg=orientation_deg,
        )
    return BuildingPhysicsGraph(
        building_model=building_model,
        zone_connections=zone_connections,
        boundary_connections=boundary_connections,
        validate_on_init=True,
    )


def default_family_space_role_map(
    dwelling_id: str = "dwelling_1",
) -> Dict[str, str]:
    """
    Map ABBEY semantic roles to globally unique dwelling zone IDs.

    This helps connect old ABBEY role names to the new dwelling-aware zones.
    """

    return {
        "idle": dwelling_id + "_living_room",
        "living_room": dwelling_id + "_living_room",
        "sleep": dwelling_id + "_bedroom_1",
        "child_sleep": dwelling_id + "_bedroom_2",
        "work": dwelling_id + "_office",
        "schoolwork": dwelling_id + "_office",
        "kitchen": dwelling_id + "_kitchen",
        "bathroom": dwelling_id + "_bathroom",
        "laundry": dwelling_id + "_laundry",
        "entrance": dwelling_id + "_entrance",
        "care": dwelling_id + "_living_room",
        "outside": "outside",
    }


def default_family_ids() -> Tuple[str, str, str]:
    """
    Return:
        building_id, dwelling_id, household_id
    """

    return "dummy_building_1", "dwelling_1", "family_1"
