"""
ABBEY occupant location and space-assignment layer.

PersonState describes the person.
OccupantLocation describes where that person is in a specific dwelling.
SpaceAssignment maps semantic roles to actual spaces in that dwelling.
"""

from dataclasses import dataclass, field, asdict, replace
from typing import Any, Dict, List


@dataclass
class OccupantLocation:
    """
    Spatial state of one occupant inside one dwelling simulation.

    This is separate from PersonState because space IDs depend on
    the specific dwelling layout.
    """

    occupant_id: str = "person_1"
    dwelling_id: str = "dwelling_1"

    is_home: bool = True
    current_space_id: str = "main_room"
    current_space_role: str = "idle"

    away_reason: str = "none"  # none, work, leisure

    minutes_since_last_space_change: float = 999.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def copy(self, **updates: Any) -> "OccupantLocation":
        return replace(self, **updates)


@dataclass
class SpaceAssignment:
    """
    Maps semantic roles to dwelling-specific spaces.

    Example:
        sleep -> bedroom_1
        work  -> office
        idle  -> living_room

    In a studio, most roles may map to main_room.
    """

    occupant_id: str = "person_1"
    dwelling_id: str = "dwelling_1"

    default_space_id: str = "main_room"

    role_to_space_id: Dict[str, str] = field(
        default_factory=lambda: {
            "idle": "main_room",
            "sleep": "main_room",
            "work": "main_room",
            "kitchen": "main_room",
            "bathroom": "main_room",
            "laundry": "main_room",
            "entrance": "main_room",
        }
    )

    def resolve(
        self,
        role: str,
        available_space_ids: List[str],
    ) -> str:
        """
        Resolve a semantic role to an actual dwelling space.

        If the target does not exist, fallback safely.
        """

        candidate = self.role_to_space_id.get(role, self.default_space_id)

        if candidate in available_space_ids:
            return candidate

        if self.default_space_id in available_space_ids:
            return self.default_space_id

        if available_space_ids:
            return available_space_ids[0]

        return self.default_space_id

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def copy(self, **updates: Any) -> "SpaceAssignment":
        return replace(self, **updates)