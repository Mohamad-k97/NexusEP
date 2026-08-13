"""
ABBEY building physics graph.

Phase 1, revised:
- do not duplicate BuildingModel, DwellingModel, or ZoneModel
- use the existing BuildingModel as the source of truth
- add only topology/adapters needed by physics

No thermal, airflow, daylight, or acoustic equations here.
"""

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional

from nexusep.abbey.building.model import BuildingModel, ZoneModel


OUTSIDE_NODE_ID = "outside"

VALID_ZONE_CONNECTION_TYPES = {
    "internal_wall",
    "door",
    "floor_ceiling",
    "generic_interzone",
}

VALID_BOUNDARY_CONNECTION_TYPES = {
    "external_wall",
    "window",
    "ventilation_opening",
    "outside_boundary",
}


@dataclass
class OutsideBoundaryNode:
    boundary_id: str = OUTSIDE_NODE_ID
    boundary_name: str = "Outside"

    def __post_init__(self) -> None:
        if self.boundary_id != OUTSIDE_NODE_ID:
            raise ValueError("OutsideBoundaryNode.boundary_id must be 'outside'.")


@dataclass
class ZoneConnection:
    """
    Physical/topological connection between two real zones.

    Examples:
        internal wall between living room and bedroom
        door between corridor and kitchen
        floor/ceiling connection between stacked zones later
    """

    connection_id: str
    from_zone_id: str
    to_zone_id: str
    connection_type: str = "generic_interzone"

    area_m2: Optional[float] = None
    is_openable: bool = False
    open_fraction: float = 0.0
    allow_duplicate: bool = False
    
    # Airflow opening properties for doors / interzone openings
    max_opening_area_m2: Optional[float] = None
    discharge_coefficient: float = 0.6
    base_airflow_m3_h: float = 0.0
    

    # Acoustic placeholder properties
    partition_sound_reduction_db: float = 35.0
    door_sound_reduction_db: float = 20.0
    
    # Thermal property for interzone heat transfer
    u_value_w_m2k: Optional[float] = None
    
    def __post_init__(self) -> None:
        if not self.connection_id:
            raise ValueError("ZoneConnection.connection_id cannot be empty.")

        if not self.from_zone_id:
            raise ValueError("ZoneConnection.from_zone_id cannot be empty.")

        if not self.to_zone_id:
            raise ValueError("ZoneConnection.to_zone_id cannot be empty.")

        if self.from_zone_id == OUTSIDE_NODE_ID or self.to_zone_id == OUTSIDE_NODE_ID:
            raise ValueError(
                "ZoneConnection must connect two real zones. "
                "Use BoundaryConnection for outside links."
            )

        if self.from_zone_id == self.to_zone_id:
            raise ValueError(
                "ZoneConnection cannot connect a zone to itself: '{}'.".format(
                    self.from_zone_id
                )
            )

        if self.connection_type not in VALID_ZONE_CONNECTION_TYPES:
            raise ValueError(
                "Invalid zone connection type '{}'. Valid types are {}.".format(
                    self.connection_type,
                    sorted(VALID_ZONE_CONNECTION_TYPES),
                )
            )

        if self.area_m2 is not None and self.area_m2 < 0.0:
            raise ValueError(
                "ZoneConnection '{}' has negative area_m2.".format(
                    self.connection_id
                )
            )

        self.open_fraction = clamp_fraction(self.open_fraction)
        
        self.discharge_coefficient = clamp_fraction(self.discharge_coefficient)

        self.base_airflow_m3_h = float(self.base_airflow_m3_h)

        if self.base_airflow_m3_h < 0.0:
            raise ValueError(
                "ZoneConnection '{}' has negative base_airflow_m3_h.".format(
                    self.connection_id
                )
            )

        if self.max_opening_area_m2 is not None:
            self.max_opening_area_m2 = float(self.max_opening_area_m2)

            if self.max_opening_area_m2 < 0.0:
                raise ValueError(
                    "ZoneConnection '{}' has negative max_opening_area_m2.".format(
                        self.connection_id
                    )
                )

        if self.is_openable and self.max_opening_area_m2 is None:
            if self.area_m2 is not None:
                self.max_opening_area_m2 = self.area_m2
                
        self.partition_sound_reduction_db = float(
            self.partition_sound_reduction_db
        )

        if self.partition_sound_reduction_db < 0.0:
            raise ValueError(
                "ZoneConnection '{}' has negative partition_sound_reduction_db.".format(
                    self.connection_id
                )
            )

        self.door_sound_reduction_db = float(self.door_sound_reduction_db)

        if self.door_sound_reduction_db < 0.0:
            raise ValueError(
                "ZoneConnection '{}' has negative door_sound_reduction_db.".format(
                    self.connection_id
                )
            )
        if self.u_value_w_m2k is not None:
            self.u_value_w_m2k = float(self.u_value_w_m2k)

            if self.u_value_w_m2k < 0.0:
                raise ValueError(
                    "ZoneConnection '{}' has negative u_value_w_m2k.".format(
                        self.connection_id
                    )
                )

    def effective_sound_reduction_db(self) -> float:
        """
        Placeholder for future interzone noise transmission.

        No acoustic propagation is solved here.
        """

        if self.connection_type == "door":
            return self.door_sound_reduction_db

        return self.partition_sound_reduction_db


@dataclass
class BoundaryConnection:
    """
    Physical/topological connection between one real zone and outside.

    Examples:
        external wall
        window
        ventilation opening
        generic outside boundary

    Window, facade, and solar-related properties are stored here because
    one zone can have multiple boundary connections with different orientations.
    """

    connection_id: str
    zone_id: str
    boundary_id: str = OUTSIDE_NODE_ID
    external_boundary_id: str = "outdoor_air"
    connection_type: str = "outside_boundary"

    area_m2: Optional[float] = None
    orientation_deg: Optional[float] = None
    tilt_deg: Optional[float] = None

    is_window: bool = False
    is_openable: bool = False
    open_fraction: float = 0.0
    allow_duplicate: bool = False

    # Window / facade / solar properties
    u_value_w_m2k: Optional[float] = None
    thermal_bridge_conductance_w_k: float = 0.0
    window_u_value_w_m2k: Optional[float] = None
    glazing_transmittance: Optional[float] = None
    window_visible_transmittance: Optional[float] = None
    solar_heat_gain_coefficient: Optional[float] = None
    frame_fraction: float = 0.2
    shading_factor: float = 1.0

    # Curtain / blind state and properties
    curtain_open: bool = True
    curtain_solar_reduction_factor: float = 0.35
    curtain_daylight_reduction_factor: float = 0.25
    
    # Acoustic placeholder properties
    outside_noise_transmission_factor: float = 0.1
    window_sound_reduction_db: float = 25.0
    
    # Airflow opening properties
    max_opening_area_m2: Optional[float] = None
    discharge_coefficient: float = 0.6

    def __post_init__(self) -> None:
        if not self.connection_id:
            raise ValueError("BoundaryConnection.connection_id cannot be empty.")

        if not self.zone_id:
            raise ValueError("BoundaryConnection.zone_id cannot be empty.")

        if self.zone_id == OUTSIDE_NODE_ID:
            raise ValueError(
                "BoundaryConnection.zone_id must be a real zone, not 'outside'."
            )

        if self.boundary_id != OUTSIDE_NODE_ID:
            raise ValueError(
                "For now, BoundaryConnection.boundary_id must be 'outside'."
            )
        if not str(self.external_boundary_id).strip():
            raise ValueError("BoundaryConnection.external_boundary_id cannot be empty.")
        self.external_boundary_id = str(self.external_boundary_id).strip()

        if self.connection_type not in VALID_BOUNDARY_CONNECTION_TYPES:
            raise ValueError(
                "Invalid boundary connection type '{}'. Valid types are {}.".format(
                    self.connection_type,
                    sorted(VALID_BOUNDARY_CONNECTION_TYPES),
                )
            )

        if self.area_m2 is not None:
            self.area_m2 = float(self.area_m2)

            if self.area_m2 < 0.0:
                raise ValueError(
                    "BoundaryConnection '{}' has negative area_m2.".format(
                        self.connection_id
                    )
                )

        if self.orientation_deg is not None:
            self.orientation_deg = normalize_orientation_deg(self.orientation_deg)

        if self.tilt_deg is not None:
            self.tilt_deg = float(self.tilt_deg)
            if not 0.0 <= self.tilt_deg <= 180.0:
                raise ValueError(
                    "BoundaryConnection '{}' has tilt_deg outside [0, 180].".format(
                        self.connection_id
                    )
                )

        if self.connection_type == "window":
            self.is_window = True

        if self.connection_type == "external_wall":
            if self.area_m2 is None or self.area_m2 <= 0.0:
                raise ValueError(
                    "External-wall boundary connection '{}' must have positive "
                    "area_m2.".format(self.connection_id)
                )
            if self.u_value_w_m2k is None:
                raise ValueError(
                    "External-wall boundary connection '{}' must have "
                    "u_value_w_m2k.".format(self.connection_id)
                )

        if self.u_value_w_m2k is not None:
            self.u_value_w_m2k = float(self.u_value_w_m2k)
            if self.u_value_w_m2k < 0.0:
                raise ValueError(
                    "Boundary connection '{}' has negative u_value_w_m2k.".format(
                        self.connection_id
                    )
                )
        self.thermal_bridge_conductance_w_k = float(
            self.thermal_bridge_conductance_w_k
        )
        if self.thermal_bridge_conductance_w_k < 0.0:
            raise ValueError(
                "BoundaryConnection.thermal_bridge_conductance_w_k cannot be negative."
            )

        if self.is_window:
            self._validate_window_inputs()
            
        self.discharge_coefficient = clamp_fraction(self.discharge_coefficient)

        if self.max_opening_area_m2 is not None:
            self.max_opening_area_m2 = float(self.max_opening_area_m2)

            if self.max_opening_area_m2 < 0.0:
                raise ValueError(
                    "BoundaryConnection '{}' has negative max_opening_area_m2.".format(
                        self.connection_id
                    )
                )

        if self.is_openable and self.max_opening_area_m2 is None:
            if self.area_m2 is not None:
                self.max_opening_area_m2 = self.area_m2

        self.open_fraction = clamp_fraction(self.open_fraction)
        self.frame_fraction = clamp_fraction(self.frame_fraction)
        self.shading_factor = clamp_fraction(self.shading_factor)
        self.curtain_solar_reduction_factor = clamp_fraction(
            self.curtain_solar_reduction_factor
        )
        self.curtain_daylight_reduction_factor = clamp_fraction(
            self.curtain_daylight_reduction_factor
        )
        
        self.outside_noise_transmission_factor = clamp_fraction(
            self.outside_noise_transmission_factor
        )

        self.window_sound_reduction_db = float(self.window_sound_reduction_db)

        if self.window_sound_reduction_db < 0.0:
            raise ValueError(
                "BoundaryConnection '{}' has negative window_sound_reduction_db.".format(
                    self.connection_id
                )
            )
            
        self.discharge_coefficient = clamp_fraction(self.discharge_coefficient)

        if self.max_opening_area_m2 is not None:
            self.max_opening_area_m2 = float(self.max_opening_area_m2)

            if self.max_opening_area_m2 < 0.0:
                raise ValueError(
                    "BoundaryConnection '{}' has negative max_opening_area_m2.".format(
                        self.connection_id
                    )
                )

        if self.is_openable and self.max_opening_area_m2 is None:
            if self.area_m2 is not None:
                self.max_opening_area_m2 = self.area_m2

        self.outside_noise_transmission_factor = clamp_fraction(
            self.outside_noise_transmission_factor
        )


            
    def effective_outdoor_sound_reduction_db(self) -> float:
        """
        Placeholder for future outdoor-to-zone noise transmission.

        No acoustic propagation is solved here.
        """

        if self.is_window or self.connection_type == "window":
            open_fraction = self.open_fraction if self.is_openable else 0.0
            return self.window_sound_reduction_db * (1.0 - open_fraction)

        return 0.0

    def effective_outdoor_noise_transmission_factor(self) -> float:
        """Interpolate the placeholder transmission factor toward one when open."""

        base = self.outside_noise_transmission_factor

        if not (self.is_window or self.connection_type == "window"):
            return base

        open_fraction = self.open_fraction if self.is_openable else 0.0
        return base + open_fraction * (1.0 - base)

    def _validate_window_inputs(self) -> None:
        if self.orientation_deg is None:
            raise ValueError(
                "Window boundary connection '{}' must have orientation_deg.".format(
                    self.connection_id
                )
            )

        if self.area_m2 is None:
            raise ValueError(
                "Window boundary connection '{}' must have area_m2.".format(
                    self.connection_id
                )
            )

        if self.area_m2 <= 0.0:
            raise ValueError(
                "Window boundary connection '{}' must have positive area_m2.".format(
                    self.connection_id
                )
            )

        if self.window_u_value_w_m2k is None:
            self.window_u_value_w_m2k = 2.7

        if self.glazing_transmittance is None:
            self.glazing_transmittance = 0.65

        if self.solar_heat_gain_coefficient is None:
            self.solar_heat_gain_coefficient = 0.55
            
        if self.window_visible_transmittance is None:
            self.window_visible_transmittance = self.glazing_transmittance

        self.window_visible_transmittance = clamp_fraction(
            self.window_visible_transmittance
        )

        self.window_u_value_w_m2k = float(self.window_u_value_w_m2k)
        self.glazing_transmittance = clamp_fraction(self.glazing_transmittance)
        self.solar_heat_gain_coefficient = clamp_fraction(
            self.solar_heat_gain_coefficient
        )

        if self.window_u_value_w_m2k < 0.0:
            raise ValueError(
                "Window boundary connection '{}' has negative window_u_value_w_m2k.".format(
                    self.connection_id
                )
            )

    def effective_solar_factor(self) -> float:
        """
        Effective solar factor for later solar-gain calculation.

        No solar equation is solved here.
        This only combines static window/curtain/shading properties.
        """

        if not self.is_window:
            return 0.0

        curtain_factor = 1.0

        if not self.curtain_open:
            curtain_factor = self.curtain_solar_reduction_factor

        return (
            self.solar_heat_gain_coefficient
            * (1.0 - self.frame_fraction)
            * self.shading_factor
            * curtain_factor
        )

    def effective_daylight_factor(self) -> float:
        """
        Effective daylight factor for later daylight calculation.

        No daylight equation is solved here.
        """

        if not self.is_window:
            return 0.0

        curtain_factor = 1.0

        if not self.curtain_open:
            curtain_factor = self.curtain_daylight_reduction_factor

        return (
            self.window_visible_transmittance
            * (1.0 - self.frame_fraction)
            * self.shading_factor
            * curtain_factor
        )


@dataclass
class BuildingPhysicsGraph:
    """
    Topology adapter for ABBEY building physics.

    Source of truth:
        BuildingModel / DwellingModel / ZoneModel

    This graph stores only physical relationships that are not already present
    in BuildingModel:
        - interzone connections
        - boundary connections to outside
        - orientation/topology queries
    """

    building_model: BuildingModel
    zone_connections: Dict[str, ZoneConnection] = field(default_factory=dict)
    boundary_connections: Dict[str, BoundaryConnection] = field(default_factory=dict)
    outside: OutsideBoundaryNode = field(default_factory=OutsideBoundaryNode)
    validate_on_init: bool = True

    def __post_init__(self) -> None:
        if self.building_model is None:
            raise ValueError("BuildingPhysicsGraph.building_model cannot be None.")

        if self.validate_on_init:
            self._derive_zone_envelopes_from_graph()
            self.validate()

    @property
    def building_id(self) -> str:
        return self.building_model.building_id

    def validate(self) -> None:
        self._validate_building_model()
        self._validate_zone_connections()
        self._validate_boundary_connections()
        self._validate_duplicate_zone_connections()
        self._validate_duplicate_boundary_connections()
        self._validate_envelope_models()

    def _derive_zone_envelopes_from_graph(self) -> None:
        """Materialize aggregate thermal fields from graph boundary conductances."""

        for zone_id, zone in self._zone_models().items():
            if zone.thermal_envelope_model != "graph_boundaries":
                continue
            boundaries = [
                connection
                for connection in self.boundary_connections.values()
                if connection.zone_id == zone_id
                and connection.connection_type == "external_wall"
            ]
            opaque_area_m2 = sum(
                float(connection.area_m2 or 0.0) for connection in boundaries
            )
            opaque_ua_w_per_k = sum(
                float(connection.area_m2 or 0.0)
                * float(connection.u_value_w_m2k or 0.0)
                for connection in boundaries
            )
            zone.external_wall_area_m2 = opaque_area_m2
            zone.u_value_external_wall_w_m2k = (
                opaque_ua_w_per_k / opaque_area_m2 if opaque_area_m2 else 0.0
            )
            zone.derived_envelope_ua_w_per_k = opaque_ua_w_per_k
            zone.envelope_provenance = (
                "derived_from_BuildingPhysicsGraph.external_wall_boundaries"
            )

    def _validate_envelope_models(self) -> None:
        for zone_id, zone in self._zone_models().items():
            if not zone.is_conditioned:
                continue
            if zone.thermal_envelope_model == "legacy_ua_compatibility":
                if float(zone.ua_w_per_k) <= 0.0:
                    raise ValueError(
                        "Conditioned zone '{}' selected legacy_ua_compatibility "
                        "but ua_w_per_k is not positive.".format(zone_id)
                    )
                continue
            boundaries = [
                connection
                for connection in self.boundary_connections.values()
                if connection.zone_id == zone_id
                and connection.connection_type == "external_wall"
            ]
            if not boundaries:
                raise ValueError(
                    "Conditioned zone '{}' selected graph_boundaries but has no "
                    "explicit exterior-wall boundary.".format(zone_id)
                )
            derived_ua = sum(
                float(connection.area_m2 or 0.0)
                * float(connection.u_value_w_m2k or 0.0)
                for connection in boundaries
            )
            if derived_ua <= 0.0:
                raise ValueError(
                    "Conditioned zone '{}' has no usable exterior-wall "
                    "conductance in the physics graph.".format(zone_id)
                )
            if abs(derived_ua - float(zone.derived_envelope_ua_w_per_k or 0.0)) > 1e-9:
                raise ValueError(
                    "Conditioned zone '{}' derived envelope UA does not match "
                    "the graph boundary conductance sum.".format(zone_id)
                )

    def _zone_models(self) -> Dict[str, ZoneModel]:
        return self.building_model.all_zone_models()

    def _validate_building_model(self) -> None:
        if not self.building_model.building_id:
            raise ValueError("BuildingModel.building_id cannot be empty.")

        seen_zone_ids = set()

        for dwelling_id, dwelling in self.building_model.dwellings.items():
            if dwelling.building_id != self.building_id:
                raise ValueError(
                    "Dwelling '{}' belongs to building '{}', not '{}'.".format(
                        dwelling_id,
                        dwelling.building_id,
                        self.building_id,
                    )
                )

            for zone_id, zone_model in dwelling.zone_models.items():
                if zone_id in seen_zone_ids:
                    raise ValueError(
                        "Duplicate zone_id '{}' found in BuildingModel.".format(
                            zone_id
                        )
                    )

                seen_zone_ids.add(zone_id)
                self._validate_zone_model_identity(zone_id, zone_model)

                if zone_model.zone_scope != "private":
                    raise ValueError(
                        "Zone '{}' is inside dwelling '{}', but zone_scope is '{}'. "
                        "Dwelling zones must be private.".format(
                            zone_id,
                            dwelling_id,
                            zone_model.zone_scope,
                        )
                    )

                if zone_model.dwelling_id != dwelling_id:
                    raise ValueError(
                        "Zone '{}' has dwelling_id '{}', but is stored in dwelling '{}'.".format(
                            zone_id,
                            zone_model.dwelling_id,
                            dwelling_id,
                        )
                    )

                if zone_id not in dwelling.private_zone_ids:
                    raise ValueError(
                        "Private zone '{}' is in dwelling '{}', but missing from private_zone_ids.".format(
                            zone_id,
                            dwelling_id,
                        )
                    )

        for zone_id, zone_model in self.building_model.shared_zone_models.items():
            if zone_id in seen_zone_ids:
                raise ValueError(
                    "Duplicate zone_id '{}' found in shared_zone_models.".format(
                        zone_id
                    )
                )

            seen_zone_ids.add(zone_id)
            self._validate_zone_model_identity(zone_id, zone_model)

            if zone_model.zone_scope != "shared":
                raise ValueError(
                    "Shared zone '{}' has zone_scope '{}', expected 'shared'.".format(
                        zone_id,
                        zone_model.zone_scope,
                    )
                )

    def get_zone_connection(
        self,
        connection_id: str,
    ) -> ZoneConnection:
        if connection_id not in self.zone_connections:
            raise KeyError(
                "ZoneConnection '" + str(connection_id) + "' not found."
            )

        return self.zone_connections[connection_id]

    def set_zone_connection_open_fraction(
        self,
        connection_id: str,
        open_fraction: float,
        require_openable: bool = True,
        validate_after_update: bool = True,
    ) -> ZoneConnection:
        """
        Update the static graph state of an openable interzone connection.

        Phase 11.4:
            This is still graph-level state, not an agent action bridge.

        Later:
            agent action -> door operation bridge -> this graph update
        """

        connection = self.get_zone_connection(connection_id)

        if require_openable and not bool(connection.is_openable):
            raise ValueError(
                "ZoneConnection '"
                + str(connection_id)
                + "' is not openable."
            )

        new_open_fraction = clamp_fraction(open_fraction)

        updated = replace(
            connection,
            open_fraction=new_open_fraction,
        )

        self.zone_connections[connection_id] = updated

        if validate_after_update:
            self.validate()

        return updated

    def set_door_open_fraction_between_zones(
        self,
        zone_a_id: str,
        zone_b_id: str,
        open_fraction: float,
        validate_after_update: bool = True,
    ) -> ZoneConnection:
        """
        Convenience helper for static door-state tests.

        Finds the unique door connection between two zones and updates
        its open_fraction.
        """

        matches = []

        wanted_pair = set([zone_a_id, zone_b_id])

        for connection in self.zone_connections.values():
            if connection.connection_type != "door":
                continue

            pair = set([connection.from_zone_id, connection.to_zone_id])

            if pair == wanted_pair:
                matches.append(connection)

        if len(matches) == 0:
            raise KeyError(
                "No door ZoneConnection found between "
                + str(zone_a_id)
                + " and "
                + str(zone_b_id)
                + "."
            )

        if len(matches) > 1:
            raise ValueError(
                "Multiple door ZoneConnections found between "
                + str(zone_a_id)
                + " and "
                + str(zone_b_id)
                + ". Use connection_id explicitly."
            )

        return self.set_zone_connection_open_fraction(
            connection_id=matches[0].connection_id,
            open_fraction=open_fraction,
            require_openable=True,
            validate_after_update=validate_after_update,
        )
    
    def openable_boundary_connections_for_zone(
        self,
        zone_id: str,
    ) -> List[BoundaryConnection]:
        return [
            connection
            for connection in self.boundary_connections_for_zone(zone_id)
            if connection.is_openable
        ]

    def openable_window_connections_for_zone(
        self,
        zone_id: str,
    ) -> List[BoundaryConnection]:
        return [
            connection
            for connection in self.window_connections_for_zone(zone_id)
            if connection.is_openable
        ]

    def openable_zone_connections_for_zone(
        self,
        zone_id: str,
    ) -> List[ZoneConnection]:
        return [
            connection
            for connection in self.zone_connections_for_zone(zone_id)
            if connection.is_openable
        ]

    def total_window_opening_area_m2_for_zone(
        self,
        zone_id: str,
    ) -> float:
        total = 0.0

        for connection in self.openable_window_connections_for_zone(zone_id):
            if connection.max_opening_area_m2 is None:
                continue

            total += connection.max_opening_area_m2 * connection.open_fraction

        return total

    def total_interzone_opening_area_m2_for_zone(
        self,
        zone_id: str,
    ) -> float:
        total = 0.0

        for connection in self.openable_zone_connections_for_zone(zone_id):
            if connection.max_opening_area_m2 is None:
                continue

            total += connection.max_opening_area_m2 * connection.open_fraction

        return total

    def mechanically_ventilated_zone_ids(self) -> List[str]:
        out = []

        for zone in self.all_zones():
            if zone.mechanical_ventilation_available:
                out.append(zone.zone_id)

        return out

    def zones_with_infiltration(self) -> List[str]:
        out = []

        for zone in self.all_zones():
            if zone.default_infiltration_ach > 0.0:
                out.append(zone.zone_id)

        return out

    def window_area_m2_for_zone(self, zone_id: str) -> float:
        return sum(
            connection.area_m2
            for connection in self.window_connections_for_zone(zone_id)
            if connection.area_m2 is not None
        )

    def has_window(self, zone_id: str) -> bool:
        return self.window_area_m2_for_zone(zone_id) > 0.0

    def window_connections_by_orientation_label(
        self,
        orientation_label_value: str,
    ) -> List[BoundaryConnection]:
        orientation_label_value = str(orientation_label_value).strip().upper()

        return [
            connection
            for connection in self.boundary_connections.values()
            if (
                connection.is_window
                and connection.orientation_deg is not None
                and orientation_label(connection.orientation_deg) == orientation_label_value
            )
        ]
    
    def has_daylight(self, zone_id: str) -> bool:
        return self.window_area_m2_for_zone(zone_id) > 0.0

    def daylight_zone_ids(self) -> List[str]:
        return [
            zone_id
            for zone_id in self.all_zone_ids()
            if self.has_daylight(zone_id)
        ]

    def effective_daylight_area_m2_for_zone(self, zone_id: str) -> float:
        total = 0.0

        for connection in self.window_connections_for_zone(zone_id):
            if connection.area_m2 is None:
                continue

            total += connection.area_m2 * connection.effective_daylight_factor()

        return total

    def south_facing_window_connections(self) -> List[BoundaryConnection]:
        return self.window_connections_facing(
            orientation_deg=180.0,
            tolerance_deg=45.0,
        )

    def total_window_area_m2(self) -> float:
        return sum(
            connection.area_m2
            for connection in self.boundary_connections.values()
            if connection.is_window and connection.area_m2 is not None
        )

    def window_u_values_for_zone(self, zone_id: str) -> List[float]:
        return [
            connection.window_u_value_w_m2k
            for connection in self.window_connections_for_zone(zone_id)
            if connection.window_u_value_w_m2k is not None
        ]

    def effective_solar_factors_for_zone(self, zone_id: str) -> List[float]:
        return [
            connection.effective_solar_factor()
            for connection in self.window_connections_for_zone(zone_id)
        ]

    def effective_daylight_factors_for_zone(self, zone_id: str) -> List[float]:
        return [
            connection.effective_daylight_factor()
            for connection in self.window_connections_for_zone(zone_id)
        ]
    
    def acoustic_zone_connections_for_zone(
        self,
        zone_id: str,
    ) -> List[ZoneConnection]:
        return self.zone_connections_for_zone(zone_id)

    def acoustic_boundary_connections_for_zone(
        self,
        zone_id: str,
    ) -> List[BoundaryConnection]:
        return self.boundary_connections_for_zone(zone_id)

    def window_sound_reductions_for_zone(
        self,
        zone_id: str,
    ) -> List[float]:
        return [
            connection.window_sound_reduction_db
            for connection in self.window_connections_for_zone(zone_id)
        ]

    def interzone_sound_reductions_for_zone(
        self,
        zone_id: str,
    ) -> List[float]:
        return [
            connection.effective_sound_reduction_db()
            for connection in self.zone_connections_for_zone(zone_id)
        ]

    def _validate_zone_model_identity(
        self,
        zone_id: str,
        zone_model: ZoneModel,
    ) -> None:
        if not zone_id:
            raise ValueError("Zone id cannot be empty.")

        if zone_id == OUTSIDE_NODE_ID:
            raise ValueError(
                "'outside' must be represented by OutsideBoundaryNode, not ZoneModel."
            )

        if zone_model.zone_id != zone_id:
            raise ValueError(
                "Zone dict key '{}' does not match zone_model.zone_id '{}'.".format(
                    zone_id,
                    zone_model.zone_id,
                )
            )

        if zone_model.building_id != self.building_id:
            raise ValueError(
                "Zone '{}' belongs to building '{}', not '{}'.".format(
                    zone_id,
                    zone_model.building_id,
                    self.building_id,
                )
            )

        if zone_model.zone_scope == "outside":
            raise ValueError(
                "Zone '{}' has zone_scope='outside'. Use OutsideBoundaryNode instead.".format(
                    zone_id
                )
            )

    def _validate_zone_connections(self) -> None:
        zone_models = self._zone_models()

        for connection_id, connection in self.zone_connections.items():
            if connection.connection_id != connection_id:
                raise ValueError(
                    "ZoneConnection dict key '{}' does not match connection_id '{}'.".format(
                        connection_id,
                        connection.connection_id,
                    )
                )

            if connection.from_zone_id not in zone_models:
                raise ValueError(
                    "ZoneConnection '{}' references missing from_zone_id '{}'.".format(
                        connection_id,
                        connection.from_zone_id,
                    )
                )

            if connection.to_zone_id not in zone_models:
                raise ValueError(
                    "ZoneConnection '{}' references missing to_zone_id '{}'.".format(
                        connection_id,
                        connection.to_zone_id,
                    )
                )

    def _validate_boundary_connections(self) -> None:
        zone_models = self._zone_models()

        for connection_id, connection in self.boundary_connections.items():
            if connection.connection_id != connection_id:
                raise ValueError(
                    "BoundaryConnection dict key '{}' does not match connection_id '{}'.".format(
                        connection_id,
                        connection.connection_id,
                    )
                )

            if connection.zone_id not in zone_models:
                raise ValueError(
                    "BoundaryConnection '{}' references missing zone_id '{}'.".format(
                        connection_id,
                        connection.zone_id,
                    )
                )

            if connection.boundary_id != OUTSIDE_NODE_ID:
                raise ValueError(
                    "BoundaryConnection '{}' must connect to outside.".format(
                        connection_id
                    )
                )

            if connection.connection_type == "window" and connection.orientation_deg is None:
                raise ValueError(
                    "Window boundary connection '{}' must have orientation_deg.".format(
                        connection_id
                    )
                )

    def _validate_duplicate_zone_connections(self) -> None:
        seen = set()

        for connection in self.zone_connections.values():
            if connection.allow_duplicate:
                continue

            zone_pair = tuple(sorted([connection.from_zone_id, connection.to_zone_id]))
            key = (zone_pair[0], zone_pair[1], connection.connection_type)

            if key in seen:
                raise ValueError(
                    "Duplicate zone connection between '{}' and '{}' of type '{}'.".format(
                        zone_pair[0],
                        zone_pair[1],
                        connection.connection_type,
                    )
                )

            seen.add(key)

    def _validate_duplicate_boundary_connections(self) -> None:
        seen = set()

        for connection in self.boundary_connections.values():
            if connection.allow_duplicate:
                continue

            key = (
                connection.zone_id,
                connection.boundary_id,
                connection.connection_type,
                connection.orientation_deg,
            )

            if key in seen:
                raise ValueError(
                    "Duplicate boundary connection for zone '{}' of type '{}' "
                    "with orientation '{}'.".format(
                        connection.zone_id,
                        connection.connection_type,
                        connection.orientation_deg,
                    )
                )

            seen.add(key)

    def dwelling_ids(self) -> List[str]:
        return list(self.building_model.dwelling_ids)

    def number_of_dwellings(self) -> int:
        return len(self.building_model.dwellings)

    def supports_multiple_dwellings(self) -> bool:
        return True

    def all_zone_ids(self) -> List[str]:
        return self.building_model.all_zone_ids()

    def all_zones(self) -> List[ZoneModel]:
        return list(self._zone_models().values())

    def zone_ids_for_building(self) -> List[str]:
        return self.all_zone_ids()

    def zone_exists(self, zone_id: str) -> bool:
        return zone_id in self._zone_models()

    def get_zone_model(self, zone_id: str) -> Optional[ZoneModel]:
        zone_models = self._zone_models()
        return zone_models.get(zone_id)

    def zone_ids_for_dwelling(self, dwelling_id: str) -> List[str]:
        if dwelling_id not in self.building_model.dwellings:
            return []

        dwelling = self.building_model.dwellings[dwelling_id]
        return list(dwelling.private_zone_ids)

    def zones_for_dwelling(self, dwelling_id: str) -> List[ZoneModel]:
        return [
            self.building_model.get_zone_model(zone_id)
            for zone_id in self.zone_ids_for_dwelling(dwelling_id)
        ]

    def private_zone_ids(self) -> List[str]:
        out = []

        for dwelling in self.building_model.dwellings.values():
            out.extend(list(dwelling.private_zone_ids))

        return out

    def private_zones(self) -> List[ZoneModel]:
        return [
            self.building_model.get_zone_model(zone_id)
            for zone_id in self.private_zone_ids()
        ]

    def private_zone_ids_for_dwelling(self, dwelling_id: str) -> List[str]:
        return self.zone_ids_for_dwelling(dwelling_id)

    def private_zone_nodes_for_dwelling(self, dwelling_id: str) -> List[ZoneModel]:
        return self.zones_for_dwelling(dwelling_id)

    def shared_zone_ids(self) -> List[str]:
        return list(self.building_model.shared_zone_ids)

    def shared_zones(self) -> List[ZoneModel]:
        return [
            self.building_model.shared_zone_models[zone_id]
            for zone_id in self.building_model.shared_zone_ids
            if zone_id in self.building_model.shared_zone_models
        ]

    def shared_zone_nodes(self) -> List[ZoneModel]:
        return self.shared_zones()

    def zone_belongs_to_dwelling(
        self,
        zone_id: str,
        dwelling_id: str,
    ) -> bool:
        if dwelling_id not in self.building_model.dwellings:
            return False

        return zone_id in self.building_model.dwellings[dwelling_id].private_zone_ids

    def zone_is_shared(self, zone_id: str) -> bool:
        return zone_id in self.building_model.shared_zone_models

    def zone_connections_for_zone(self, zone_id: str) -> List[ZoneConnection]:
        return [
            connection
            for connection in self.zone_connections.values()
            if connection.from_zone_id == zone_id or connection.to_zone_id == zone_id
        ]

    def zone_connections_by_type(
        self,
        zone_id: str,
        connection_type: str,
    ) -> List[ZoneConnection]:
        return [
            connection
            for connection in self.zone_connections_for_zone(zone_id)
            if connection.connection_type == connection_type
        ]

    def adjacent_zone_ids(self, zone_id: str) -> List[str]:
        adjacent = []

        for connection in self.zone_connections_for_zone(zone_id):
            if connection.from_zone_id == zone_id:
                adjacent.append(connection.to_zone_id)
            elif connection.to_zone_id == zone_id:
                adjacent.append(connection.from_zone_id)

        return adjacent

    def adjacent_zone_ids_by_connection_type(
        self,
        zone_id: str,
        connection_type: str,
    ) -> List[str]:
        adjacent = []

        for connection in self.zone_connections_by_type(zone_id, connection_type):
            if connection.from_zone_id == zone_id:
                adjacent.append(connection.to_zone_id)
            elif connection.to_zone_id == zone_id:
                adjacent.append(connection.from_zone_id)

        return adjacent

    def internal_wall_connections_for_zone(self, zone_id: str) -> List[ZoneConnection]:
        return self.zone_connections_by_type(zone_id, "internal_wall")

    def door_connections_for_zone(self, zone_id: str) -> List[ZoneConnection]:
        return self.zone_connections_by_type(zone_id, "door")

    def vertical_connections_for_zone(self, zone_id: str) -> List[ZoneConnection]:
        return self.zone_connections_by_type(zone_id, "floor_ceiling")

    def boundary_connections_for_zone(self, zone_id: str) -> List[BoundaryConnection]:
        return [
            connection
            for connection in self.boundary_connections.values()
            if connection.zone_id == zone_id
        ]

    def boundary_connections_by_type(
        self,
        zone_id: str,
        connection_type: str,
    ) -> List[BoundaryConnection]:
        return [
            connection
            for connection in self.boundary_connections_for_zone(zone_id)
            if connection.connection_type == connection_type
        ]

    def outside_boundary_connections_for_zone(
        self,
        zone_id: str,
    ) -> List[BoundaryConnection]:
        return [
            connection
            for connection in self.boundary_connections_for_zone(zone_id)
            if connection.boundary_id == OUTSIDE_NODE_ID
        ]

    def external_wall_connections_for_zone(
        self,
        zone_id: str,
    ) -> List[BoundaryConnection]:
        return self.boundary_connections_by_type(zone_id, "external_wall")

    def window_connections_for_zone(
        self,
        zone_id: str,
    ) -> List[BoundaryConnection]:
        return [
            connection
            for connection in self.boundary_connections_for_zone(zone_id)
            if connection.connection_type == "window" or connection.is_window
        ]

    def ventilation_opening_connections_for_zone(
        self,
        zone_id: str,
    ) -> List[BoundaryConnection]:
        return self.boundary_connections_by_type(zone_id, "ventilation_opening")

    def outside_connected_zone_ids(self) -> List[str]:
        return sorted(
            set(
                connection.zone_id
                for connection in self.boundary_connections.values()
                if connection.boundary_id == OUTSIDE_NODE_ID
            )
        )

    def window_connected_zone_ids(self) -> List[str]:
        return sorted(
            set(
                connection.zone_id
                for connection in self.boundary_connections.values()
                if connection.connection_type == "window" or connection.is_window
            )
        )

    def has_outside_connection(self, zone_id: str) -> bool:
        return len(self.outside_boundary_connections_for_zone(zone_id)) > 0

    def has_window(self, zone_id: str) -> bool:
        return len(self.window_connections_for_zone(zone_id)) > 0

    def oriented_boundary_connections_for_zone(
        self,
        zone_id: str,
    ) -> List[BoundaryConnection]:
        return [
            connection
            for connection in self.boundary_connections_for_zone(zone_id)
            if connection.orientation_deg is not None
        ]

    def orientations_for_zone(self, zone_id: str) -> List[float]:
        return [
            connection.orientation_deg
            for connection in self.oriented_boundary_connections_for_zone(zone_id)
        ]

    def orientation_labels_for_zone(self, zone_id: str) -> List[str]:
        return [
            orientation_label(connection.orientation_deg)
            for connection in self.oriented_boundary_connections_for_zone(zone_id)
        ]

    def window_orientations_for_zone(self, zone_id: str) -> List[float]:
        return [
            connection.orientation_deg
            for connection in self.window_connections_for_zone(zone_id)
            if connection.orientation_deg is not None
        ]

    def boundary_connections_facing(
        self,
        orientation_deg: float,
        tolerance_deg: float = 45.0,
    ) -> List[BoundaryConnection]:
        out = []

        for connection in self.boundary_connections.values():
            if connection.orientation_deg is None:
                continue

            diff = angular_difference_deg(connection.orientation_deg, orientation_deg)

            if diff <= tolerance_deg:
                out.append(connection)

        return out

    def window_connections_facing(
        self,
        orientation_deg: float,
        tolerance_deg: float = 45.0,
    ) -> List[BoundaryConnection]:
        return [
            connection
            for connection in self.boundary_connections_facing(
                orientation_deg=orientation_deg,
                tolerance_deg=tolerance_deg,
            )
            if connection.connection_type == "window" or connection.is_window
        ]


def clamp_fraction(value: float) -> float:
    value = float(value)

    if value < 0.0:
        return 0.0

    if value > 1.0:
        return 1.0

    return value


def normalize_orientation_deg(value: float) -> float:
    return float(value) % 360.0


def angular_difference_deg(a: float, b: float) -> float:
    a = normalize_orientation_deg(a)
    b = normalize_orientation_deg(b)

    diff = abs(a - b) % 360.0

    if diff > 180.0:
        diff = 360.0 - diff

    return diff


def orientation_label(orientation_deg: float) -> str:
    orientation_deg = normalize_orientation_deg(orientation_deg)

    if orientation_deg >= 337.5 or orientation_deg < 22.5:
        return "N"

    if orientation_deg < 67.5:
        return "NE"

    if orientation_deg < 112.5:
        return "E"

    if orientation_deg < 157.5:
        return "SE"

    if orientation_deg < 202.5:
        return "S"

    if orientation_deg < 247.5:
        return "SW"

    if orientation_deg < 292.5:
        return "W"

    return "NW"
