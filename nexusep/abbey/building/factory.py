"""
Factory helpers for creating default ABBEY buildings.

Phase 10:
- one dummy building
- one dummy dwelling
- one family household
- private dwelling zones only
"""

from typing import Dict, Tuple

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