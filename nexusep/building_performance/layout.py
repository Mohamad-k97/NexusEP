from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class RoomDefinition:
    """
    RC-ready room/zone definition.

    This is not fully used yet by the dummy model,
    but it is structured for future multizone RC simulation.
    """

    zone_id: str
    name: str
    room_type: str

    floor_area_m2: float
    height_m: float = 2.7
    volume_m3: Optional[float] = None

    # Geometry / envelope hooks
    external_wall_area_m2: float = 0.0
    internal_wall_area_m2: float = 0.0
    window_area_m2: float = 0.0
    door_area_m2: float = 0.0

    # Thermal hooks for future RC model
    thermal_capacitance_j_k: float = 1.0e6
    ventilation_flow_m3h: float = 0.0
    infiltration_ach: float = 0.2

    # Connectivity
    adjacent_zone_ids: List[str] = field(default_factory=list)

    # Assignment / semantics
    assigned_to: Optional[str] = None
    normally_occupied: bool = False

    def resolved_volume_m3(self) -> float:
        if self.volume_m3 is not None:
            return self.volume_m3
        return self.floor_area_m2 * self.height_m

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DwellingDefinition:
    dwelling_id: str
    dwelling_type: str
    rooms: Dict[str, RoomDefinition]

    def get_room(self, zone_id: str) -> RoomDefinition:
        return self.rooms[zone_id]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dwelling_id": self.dwelling_id,
            "dwelling_type": self.dwelling_type,
            "rooms": {
                zone_id: room.to_dict()
                for zone_id, room in self.rooms.items()
            },
        }