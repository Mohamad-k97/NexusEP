"""
Building and dwelling data containers for ABBEY.

Hierarchy:
    BuildingModel
        -> DwellingModel(s)
            -> ZoneModel(s)
            -> ZoneState(s)

The MVP uses one building with one dwelling, but the structure is ready for
future multifamily buildings with multiple dwellings and shared zones.
"""

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional
import copy


VALID_ZONE_SCOPES = {
    "private",
    "shared",
    "outside",
}

VALID_ZONE_USES = {
    "living_room",
    "bedroom",
    "kitchen",
    "bathroom",
    "office",
    "laundry",
    "corridor",
    "entrance",
    "shared_corridor",
    "technical_room",
    "generic",
}

DEFAULT_ZONE_HEIGHT_M = 2.7

AIR_DENSITY_KG_M3 = 1.2
AIR_SPECIFIC_HEAT_J_KG_K = 1005.0

VALID_THERMAL_MASS_CLASSES = {
    "light",
    "medium",
    "heavy",
}

THERMAL_MASS_CAPACITY_J_M2K = {
    "light": 110000.0,
    "medium": 165000.0,
    "heavy": 260000.0,
}


def normalize_zone_use(value: str) -> str:
    if value is None:
        return "generic"

    value = str(value).strip().lower()
    value = value.replace(" ", "_")
    value = value.replace("-", "_")

    if not value:
        return "generic"

    return value


def normalize_thermal_mass_class(value: str) -> str:
    if value is None:
        return "medium"

    value = str(value).strip().lower()

    if not value:
        return "medium"

    return value


@dataclass
class ZoneModel:
    """
    Static physical description of a zone/space.
    """

    zone_id: str
    zone_name: str
    dwelling_id: str
    building_id: str

    zone_scope: str = "private"
    zone_use: str = "generic"

    floor_area_m2: Optional[float] = 20.0
    height_m: Optional[float] = None
    volume_m3: Optional[float] = None
    floor_level: int = 0

    is_conditioned: bool = True
    is_occupied_space: bool = True

    centroid_x: Optional[float] = None
    centroid_y: Optional[float] = None
    geometry_source: Optional[str] = None

    ua_w_per_k: float = 60.0
    thermal_capacity_j_per_k: float = 3_000_000.0

    initial_temp_c: float = 20.0
    initial_co2_ppm: float = 600.0
    
    thermal_mass_class: str = "medium"

    internal_heat_capacity_j_k: Optional[float] = None
    air_heat_capacity_j_k: Optional[float] = None

    external_wall_area_m2: float = 0.0
    internal_wall_area_m2: float = 0.0
    floor_area_to_other_zone_m2: float = 0.0
    ceiling_area_to_other_zone_m2: float = 0.0

    u_value_external_wall_w_m2k: float = 1.2
    u_value_internal_wall_w_m2k: float = 1.8
    u_value_floor_w_m2k: float = 1.5
    u_value_ceiling_w_m2k: float = 1.5

    thermal_bridge_factor: float = 1.0

    initial_air_temperature_c: Optional[float] = None
    initial_mass_temperature_c: Optional[float] = None

    air_volume_m3: Optional[float] = None

    default_infiltration_ach: float = 0.3

    mechanical_ventilation_available: bool = False
    mechanical_ventilation_flow_m3_h: float = 0.0

    interzone_airflow_base_m3_h: float = 0.0

    co2_initial_ppm: Optional[float] = None
    co2_generation_per_person_m3_h: float = 0.018
    
    # Daylight and visual inputs
    daylight_utilization_factor: float = 0.5
    room_depth_m: Optional[float] = None
    visual_comfort_target_lux: float = 300.0
    
    # Acoustic placeholder inputs
    indoor_noise_initial_db: float = 35.0
    background_noise_db: float = 30.0
    room_absorption_factor: float = 0.3
    
    def __post_init__(self) -> None:
        if not self.zone_id:
            raise ValueError("ZoneModel.zone_id cannot be empty.")

        if not self.building_id:
            raise ValueError("ZoneModel.building_id cannot be empty.")

        if not self.zone_name:
            self.zone_name = self.zone_id

        if self.zone_scope not in VALID_ZONE_SCOPES:
            raise ValueError(
                "Invalid zone_scope for zone "
                + self.zone_id
                + ": "
                + str(self.zone_scope)
                + ". Valid values: "
                + str(sorted(VALID_ZONE_SCOPES))
            )

        self.zone_use = normalize_zone_use(self.zone_use)

        if self.zone_use not in VALID_ZONE_USES:
            raise ValueError(
                "Invalid zone_use for zone "
                + self.zone_id
                + ": "
                + str(self.zone_use)
                + ". Valid values: "
                + str(sorted(VALID_ZONE_USES))
            )

        if self.floor_area_m2 is None:
            raise ValueError(
                "floor_area_m2 is required for zone " + self.zone_id
            )

        self.floor_area_m2 = float(self.floor_area_m2)

        if self.floor_area_m2 <= 0:
            raise ValueError("floor_area_m2 must be positive for zone " + self.zone_id)

        if self.height_m is None:
            self.height_m = DEFAULT_ZONE_HEIGHT_M

        self.height_m = float(self.height_m)

        if self.height_m <= 0:
            raise ValueError("height_m must be positive for zone " + self.zone_id)

        if self.volume_m3 is None:
            self.volume_m3 = self.floor_area_m2 * self.height_m

        self.volume_m3 = float(self.volume_m3)

        if self.volume_m3 <= 0:
            raise ValueError("volume_m3 must be positive for zone " + self.zone_id)

        self.floor_level = int(self.floor_level)

        if self.centroid_x is not None:
            self.centroid_x = float(self.centroid_x)

        if self.centroid_y is not None:
            self.centroid_y = float(self.centroid_y)

        if self.thermal_capacity_j_per_k <= 0:
            raise ValueError(
                "thermal_capacity_j_per_k must be positive for zone "
                + self.zone_id
            )
        self.thermal_mass_class = normalize_thermal_mass_class(
            self.thermal_mass_class
        )

        if self.thermal_mass_class not in VALID_THERMAL_MASS_CLASSES:
            raise ValueError(
                "Invalid thermal_mass_class for zone "
                + self.zone_id
                + ": "
                + str(self.thermal_mass_class)
                + ". Valid values: "
                + str(sorted(VALID_THERMAL_MASS_CLASSES))
            )

        if self.air_heat_capacity_j_k is None:
            self.air_heat_capacity_j_k = (
                float(self.volume_m3)
                * AIR_DENSITY_KG_M3
                * AIR_SPECIFIC_HEAT_J_KG_K
            )

        self.air_heat_capacity_j_k = float(self.air_heat_capacity_j_k)

        if self.air_heat_capacity_j_k <= 0:
            raise ValueError(
                "air_heat_capacity_j_k must be positive for zone "
                + self.zone_id
            )

        if self.internal_heat_capacity_j_k is None:
            self.internal_heat_capacity_j_k = (
                THERMAL_MASS_CAPACITY_J_M2K[self.thermal_mass_class]
                * float(self.floor_area_m2)
            )

        self.internal_heat_capacity_j_k = float(self.internal_heat_capacity_j_k)

        if self.internal_heat_capacity_j_k <= 0:
            raise ValueError(
                "internal_heat_capacity_j_k must be positive for zone "
                + self.zone_id
            )

        # Backward compatibility with the existing simple model.
        if self.thermal_capacity_j_per_k is None:
            self.thermal_capacity_j_per_k = self.internal_heat_capacity_j_k

        self.thermal_capacity_j_per_k = float(self.thermal_capacity_j_per_k)

        if self.initial_air_temperature_c is None:
            self.initial_air_temperature_c = float(self.initial_temp_c)

        if self.initial_mass_temperature_c is None:
            self.initial_mass_temperature_c = float(self.initial_air_temperature_c)

        self.initial_air_temperature_c = float(self.initial_air_temperature_c)
        self.initial_mass_temperature_c = float(self.initial_mass_temperature_c)

        # Keep old field aligned with the new air-temperature field.
        self.initial_temp_c = self.initial_air_temperature_c

        self.external_wall_area_m2 = _non_negative_float(
            self.external_wall_area_m2,
            "external_wall_area_m2",
            self.zone_id,
        )
        self.internal_wall_area_m2 = _non_negative_float(
            self.internal_wall_area_m2,
            "internal_wall_area_m2",
            self.zone_id,
        )
        self.floor_area_to_other_zone_m2 = _non_negative_float(
            self.floor_area_to_other_zone_m2,
            "floor_area_to_other_zone_m2",
            self.zone_id,
        )
        self.ceiling_area_to_other_zone_m2 = _non_negative_float(
            self.ceiling_area_to_other_zone_m2,
            "ceiling_area_to_other_zone_m2",
            self.zone_id,
        )

        self.u_value_external_wall_w_m2k = _non_negative_float(
            self.u_value_external_wall_w_m2k,
            "u_value_external_wall_w_m2k",
            self.zone_id,
        )
        self.u_value_internal_wall_w_m2k = _non_negative_float(
            self.u_value_internal_wall_w_m2k,
            "u_value_internal_wall_w_m2k",
            self.zone_id,
        )
        self.u_value_floor_w_m2k = _non_negative_float(
            self.u_value_floor_w_m2k,
            "u_value_floor_w_m2k",
            self.zone_id,
        )
        self.u_value_ceiling_w_m2k = _non_negative_float(
            self.u_value_ceiling_w_m2k,
            "u_value_ceiling_w_m2k",
            self.zone_id,
        )

        self.thermal_bridge_factor = float(self.thermal_bridge_factor)

        if self.thermal_bridge_factor < 0:
            raise ValueError(
                "thermal_bridge_factor cannot be negative for zone "
                + self.zone_id
            )
            
        if self.air_volume_m3 is None:
            self.air_volume_m3 = self.volume_m3

        self.air_volume_m3 = float(self.air_volume_m3)

        if self.air_volume_m3 <= 0:
            raise ValueError(
                "air_volume_m3 must be positive for zone " + self.zone_id
            )

        self.default_infiltration_ach = _non_negative_float(
            self.default_infiltration_ach,
            "default_infiltration_ach",
            self.zone_id,
        )

        self.mechanical_ventilation_flow_m3_h = _non_negative_float(
            self.mechanical_ventilation_flow_m3_h,
            "mechanical_ventilation_flow_m3_h",
            self.zone_id,
        )

        self.interzone_airflow_base_m3_h = _non_negative_float(
            self.interzone_airflow_base_m3_h,
            "interzone_airflow_base_m3_h",
            self.zone_id,
        )

        if self.co2_initial_ppm is None:
            self.co2_initial_ppm = float(self.initial_co2_ppm)

        self.co2_initial_ppm = float(self.co2_initial_ppm)

        if self.co2_initial_ppm <= 0:
            raise ValueError(
                "co2_initial_ppm must be positive for zone " + self.zone_id
            )

        # Backward compatibility.
        self.initial_co2_ppm = self.co2_initial_ppm

        self.co2_generation_per_person_m3_h = _non_negative_float(
            self.co2_generation_per_person_m3_h,
            "co2_generation_per_person_m3_h",
            self.zone_id,
        )

        self.daylight_utilization_factor = _clamp_fraction_model(
            self.daylight_utilization_factor
        )

        if self.room_depth_m is None:
            self.room_depth_m = self.floor_area_m2 ** 0.5

        self.room_depth_m = float(self.room_depth_m)

        if self.room_depth_m <= 0:
            raise ValueError(
                "room_depth_m must be positive for zone " + self.zone_id
            )

        self.visual_comfort_target_lux = _non_negative_float(
            self.visual_comfort_target_lux,
            "visual_comfort_target_lux",
            self.zone_id,
        )
        
        self.indoor_noise_initial_db = _non_negative_float(
            self.indoor_noise_initial_db,
            "indoor_noise_initial_db",
            self.zone_id,
        )

        self.background_noise_db = _non_negative_float(
            self.background_noise_db,
            "background_noise_db",
            self.zone_id,
        )

        self.room_absorption_factor = _clamp_fraction_model(
            self.room_absorption_factor
        )
        
    def initial_state(self) -> "ZoneState":
        return ZoneState(
            zone_id=self.zone_id,
            dwelling_id=self.dwelling_id,
            building_id=self.building_id,
            indoor_temp_c=self.initial_air_temperature_c,
            co2_ppm=self.co2_initial_ppm,
            indoor_daylight=0.5,
            indoor_noise=0.2,
        )

    def copy(self, **updates: Any) -> "ZoneModel":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "dwelling_id": self.dwelling_id,
            "building_id": self.building_id,
            "zone_scope": self.zone_scope,
            "zone_use": self.zone_use,
            "floor_area_m2": self.floor_area_m2,
            "height_m": self.height_m,
            "volume_m3": self.volume_m3,
            "floor_level": self.floor_level,
            "is_conditioned": self.is_conditioned,
            "is_occupied_space": self.is_occupied_space,
            "centroid_x": self.centroid_x,
            "centroid_y": self.centroid_y,
            "geometry_source": self.geometry_source,
            "thermal_mass_class": self.thermal_mass_class,
            "internal_heat_capacity_j_k": self.internal_heat_capacity_j_k,
            "air_heat_capacity_j_k": self.air_heat_capacity_j_k,
            "external_wall_area_m2": self.external_wall_area_m2,
            "internal_wall_area_m2": self.internal_wall_area_m2,
            "floor_area_to_other_zone_m2": self.floor_area_to_other_zone_m2,
            "ceiling_area_to_other_zone_m2": self.ceiling_area_to_other_zone_m2,
            "u_value_external_wall_w_m2k": self.u_value_external_wall_w_m2k,
            "u_value_internal_wall_w_m2k": self.u_value_internal_wall_w_m2k,
            "u_value_floor_w_m2k": self.u_value_floor_w_m2k,
            "u_value_ceiling_w_m2k": self.u_value_ceiling_w_m2k,
            "thermal_bridge_factor": self.thermal_bridge_factor,
            "initial_air_temperature_c": self.initial_air_temperature_c,
            "initial_mass_temperature_c": self.initial_mass_temperature_c,
            "air_volume_m3": self.air_volume_m3,
            "default_infiltration_ach": self.default_infiltration_ach,
            "mechanical_ventilation_available": self.mechanical_ventilation_available,
            "mechanical_ventilation_flow_m3_h": self.mechanical_ventilation_flow_m3_h,
            "interzone_airflow_base_m3_h": self.interzone_airflow_base_m3_h,
            "co2_initial_ppm": self.co2_initial_ppm,
            "co2_generation_per_person_m3_h": self.co2_generation_per_person_m3_h,
            "ua_w_per_k": self.ua_w_per_k,
            "thermal_capacity_j_per_k": self.thermal_capacity_j_per_k,
            "initial_temp_c": self.initial_temp_c,
            "initial_co2_ppm": self.initial_co2_ppm,
            "daylight_utilization_factor": self.daylight_utilization_factor,
            "room_depth_m": self.room_depth_m,
            "visual_comfort_target_lux": self.visual_comfort_target_lux,
            "indoor_noise_initial_db": self.indoor_noise_initial_db,
            "background_noise_db": self.background_noise_db,
            "room_absorption_factor": self.room_absorption_factor,
        }
        
@dataclass
class ZoneState:
    """
    Dynamic state of a zone/space.
    """

    zone_id: str
    dwelling_id: str
    building_id: str

    indoor_temp_c: float = 20.0
    co2_ppm: float = 600.0
    indoor_daylight: float = 0.5
    indoor_noise: float = 0.2

    occupied_person_ids: List[str] = field(default_factory=list)
    number_of_people: int = 0

    def copy(self, **updates: Any) -> "ZoneState":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def with_occupants(self, occupied_person_ids: List[str]) -> "ZoneState":
        occupants = list(occupied_person_ids)

        return self.copy(
            occupied_person_ids=occupants,
            number_of_people=len(occupants),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "dwelling_id": self.dwelling_id,
            "building_id": self.building_id,
            "indoor_temp_c": self.indoor_temp_c,
            "co2_ppm": self.co2_ppm,
            "indoor_daylight": self.indoor_daylight,
            "indoor_noise": self.indoor_noise,
            "occupied_person_ids": list(self.occupied_person_ids),
            "number_of_people": self.number_of_people,
        }

@dataclass
class DwellingModel:
    """
    A dwelling/apartment/unit inside a building.

    MVP:
        one dwelling, one household.

    Future:
        many dwellings inside one BuildingModel.
    """

    dwelling_id: str
    building_id: str
    household_id: str

    private_zone_ids: List[str] = field(default_factory=list)

    zone_models: Dict[str, ZoneModel] = field(default_factory=dict)
    zone_states: Dict[str, ZoneState] = field(default_factory=dict)

    # These will be filled by Phase 4.
    # Use Any for now to avoid importing not-yet-created classes.
    system_specs: Dict[str, Any] = field(default_factory=dict)
    control_states: Dict[str, Any] = field(default_factory=dict)
    controller_specs: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.private_zone_ids:
            self.private_zone_ids = list(self.zone_models.keys())

        missing_models = [
            zone_id
            for zone_id in self.private_zone_ids
            if zone_id not in self.zone_models
        ]

        if missing_models:
            raise ValueError(
                "Dwelling "
                + self.dwelling_id
                + " has private_zone_ids missing from zone_models: "
                + str(missing_models)
            )

        for zone_id, zone_model in self.zone_models.items():
            if zone_model.dwelling_id != self.dwelling_id:
                raise ValueError(
                    "Zone "
                    + zone_id
                    + " has dwelling_id="
                    + zone_model.dwelling_id
                    + " but belongs to dwelling "
                    + self.dwelling_id
                )

            if zone_model.building_id != self.building_id:
                raise ValueError(
                    "Zone "
                    + zone_id
                    + " has building_id="
                    + zone_model.building_id
                    + " but dwelling belongs to building "
                    + self.building_id
                )

        for zone_id in self.zone_models:
            if zone_id not in self.zone_states:
                self.zone_states[zone_id] = self.zone_models[zone_id].initial_state()

    def get_zone_model(self, zone_id: str) -> ZoneModel:
        if zone_id not in self.zone_models:
            raise KeyError(
                "Zone "
                + zone_id
                + " not found in dwelling "
                + self.dwelling_id
            )

        return self.zone_models[zone_id]

    def get_zone_state(self, zone_id: str) -> ZoneState:
        if zone_id not in self.zone_states:
            raise KeyError(
                "Zone state "
                + zone_id
                + " not found in dwelling "
                + self.dwelling_id
            )

        return self.zone_states[zone_id]

    def set_zone_state(self, zone_id: str, zone_state: ZoneState) -> None:
        if zone_id not in self.zone_models:
            raise KeyError(
                "Cannot set state for unknown zone "
                + zone_id
                + " in dwelling "
                + self.dwelling_id
            )

        self.zone_states[zone_id] = zone_state

    def copy(self) -> "DwellingModel":
        return copy.deepcopy(self)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dwelling_id": self.dwelling_id,
            "building_id": self.building_id,
            "household_id": self.household_id,
            "private_zone_ids": list(self.private_zone_ids),
            "zone_models": {
                zone_id: zone_model.to_dict()
                for zone_id, zone_model in self.zone_models.items()
            },
            "zone_states": {
                zone_id: zone_state.to_dict()
                for zone_id, zone_state in self.zone_states.items()
            },
            "system_specs": {
                zone_id: _safe_to_dict(value)
                for zone_id, value in self.system_specs.items()
            },
            "control_states": {
                zone_id: _safe_to_dict(value)
                for zone_id, value in self.control_states.items()
            },
            "controller_specs": {
                zone_id: _safe_to_dict(value)
                for zone_id, value in self.controller_specs.items()
            },
        }


@dataclass
class BuildingModel:
    """
    Building container.

    MVP:
        one building with one dwelling.

    Future:
        one building with many dwellings, shared spaces, shared systems,
        and building-level controllers.
    """

    building_id: str

    dwelling_ids: List[str] = field(default_factory=list)
    dwellings: Dict[str, DwellingModel] = field(default_factory=dict)

    shared_zone_ids: List[str] = field(default_factory=list)
    shared_zone_models: Dict[str, ZoneModel] = field(default_factory=dict)
    shared_zone_states: Dict[str, ZoneState] = field(default_factory=dict)

    # These will be filled by later phases.
    shared_system_specs: Dict[str, Any] = field(default_factory=dict)
    building_system_specs: Dict[str, Any] = field(default_factory=dict)
    building_control_states: Dict[str, Any] = field(default_factory=dict)
    building_controller_specs: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.dwelling_ids:
            self.dwelling_ids = list(self.dwellings.keys())

        missing_dwellings = [
            dwelling_id
            for dwelling_id in self.dwelling_ids
            if dwelling_id not in self.dwellings
        ]

        if missing_dwellings:
            raise ValueError(
                "Building "
                + self.building_id
                + " has dwelling_ids missing from dwellings: "
                + str(missing_dwellings)
            )

        for dwelling_id, dwelling in self.dwellings.items():
            if dwelling.building_id != self.building_id:
                raise ValueError(
                    "Dwelling "
                    + dwelling_id
                    + " has building_id="
                    + dwelling.building_id
                    + " but belongs to building "
                    + self.building_id
                )

        if not self.shared_zone_ids:
            self.shared_zone_ids = list(self.shared_zone_models.keys())

        for zone_id in self.shared_zone_models:
            if zone_id not in self.shared_zone_states:
                self.shared_zone_states[zone_id] = (
                    self.shared_zone_models[zone_id].initial_state()
                )

    def get_dwelling(self, dwelling_id: str) -> DwellingModel:
        if dwelling_id not in self.dwellings:
            raise KeyError(
                "Dwelling "
                + dwelling_id
                + " not found in building "
                + self.building_id
            )

        return self.dwellings[dwelling_id]

    def get_zone_model(self, zone_id: str) -> ZoneModel:
        for dwelling in self.dwellings.values():
            if zone_id in dwelling.zone_models:
                return dwelling.zone_models[zone_id]

        if zone_id in self.shared_zone_models:
            return self.shared_zone_models[zone_id]

        raise KeyError(
            "Zone "
            + zone_id
            + " not found in building "
            + self.building_id
        )

    def get_zone_state(self, zone_id: str) -> ZoneState:
        for dwelling in self.dwellings.values():
            if zone_id in dwelling.zone_states:
                return dwelling.zone_states[zone_id]

        if zone_id in self.shared_zone_states:
            return self.shared_zone_states[zone_id]

        raise KeyError(
            "Zone state "
            + zone_id
            + " not found in building "
            + self.building_id
        )

    def set_zone_state(self, zone_id: str, zone_state: ZoneState) -> None:
        for dwelling in self.dwellings.values():
            if zone_id in dwelling.zone_states:
                dwelling.zone_states[zone_id] = zone_state
                return

        if zone_id in self.shared_zone_states:
            self.shared_zone_states[zone_id] = zone_state
            return

        raise KeyError(
            "Cannot set state for unknown zone "
            + zone_id
            + " in building "
            + self.building_id
        )

    def all_zone_ids(self) -> List[str]:
        zone_ids = []

        for dwelling in self.dwellings.values():
            zone_ids.extend(list(dwelling.zone_models.keys()))

        zone_ids.extend(list(self.shared_zone_models.keys()))

        return zone_ids

    def all_zone_models(self) -> Dict[str, ZoneModel]:
        out = {}

        for dwelling in self.dwellings.values():
            out.update(dwelling.zone_models)

        out.update(self.shared_zone_models)

        return out

    def all_zone_states(self) -> Dict[str, ZoneState]:
        out = {}

        for dwelling in self.dwellings.values():
            out.update(dwelling.zone_states)

        out.update(self.shared_zone_states)

        return out

    def copy(self) -> "BuildingModel":
        return copy.deepcopy(self)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "building_id": self.building_id,
            "dwelling_ids": list(self.dwelling_ids),
            "dwellings": {
                dwelling_id: dwelling.to_dict()
                for dwelling_id, dwelling in self.dwellings.items()
            },
            "shared_zone_ids": list(self.shared_zone_ids),
            "shared_zone_models": {
                zone_id: zone_model.to_dict()
                for zone_id, zone_model in self.shared_zone_models.items()
            },
            "shared_zone_states": {
                zone_id: zone_state.to_dict()
                for zone_id, zone_state in self.shared_zone_states.items()
            },
            "shared_system_specs": {
                key: _safe_to_dict(value)
                for key, value in self.shared_system_specs.items()
            },
            "building_system_specs": {
                key: _safe_to_dict(value)
                for key, value in self.building_system_specs.items()
            },
            "building_control_states": {
                key: _safe_to_dict(value)
                for key, value in self.building_control_states.items()
            },
            "building_controller_specs": {
                key: _safe_to_dict(value)
                for key, value in self.building_controller_specs.items()
            },
        }
    
def _clamp_fraction_model(value) -> float:
    value = float(value)

    if value < 0.0:
        return 0.0

    if value > 1.0:
        return 1.0

    return value

def _non_negative_float(value, field_name: str, zone_id: str) -> float:
    value = float(value)

    if value < 0:
        raise ValueError(
            field_name + " cannot be negative for zone " + zone_id
        )

    return value

def _safe_to_dict(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()

    if isinstance(value, dict):
        return {
            key: _safe_to_dict(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _safe_to_dict(item)
            for item in value
        ]

    return value