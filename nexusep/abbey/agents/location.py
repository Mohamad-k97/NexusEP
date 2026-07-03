"""
Location and space-assignment containers for ABBEY.

Phase 12:
- keep old simple space IDs working
- add building_id
- support dwelling-aware space IDs such as dwelling_1_living_room
- prepare for future multifamily buildings
"""

from dataclasses import dataclass, field, replace
from typing import Any, Dict, Iterable, List, Optional
import copy


DEFAULT_BUILDING_ID = "dummy_building_1"
DEFAULT_DWELLING_ID = "dwelling_1"


SPACE_ROLE_ALIASES = {
    "idle": "living_room",
    "living_room": "living_room",
    "kitchen": "kitchen",
    "bathroom": "bathroom",
    "laundry": "laundry",
    "entrance": "entrance",
    "main_room": "living_room",
    "door": "entrance",
    "office": "office",
    "work": "office",
    "schoolwork": "office",
    "sleep": "bedroom_1",
    "bedroom": "bedroom_1",
    "bedroom_1": "bedroom_1",
    "parents_bedroom": "bedroom_1",
    "child_sleep": "bedroom_2",
    "bedroom_2": "bedroom_2",
    "child_bedroom": "bedroom_2",
    "care": "living_room",
    "current": "current",
    "outside": "outside",
}


def make_dwelling_space_id(
    space_id: str,
    dwelling_id: str = DEFAULT_DWELLING_ID,
) -> str:
    """
    Convert simple space IDs to dwelling-aware IDs.

    Examples:
        living_room -> dwelling_1_living_room
        kitchen -> dwelling_1_kitchen
        dwelling_1_kitchen -> dwelling_1_kitchen
        shared_corridor -> shared_corridor
        outside -> outside
    """

    if space_id is None:
        return dwelling_id + "_living_room"

    value = str(space_id)

    if value == "":
        return dwelling_id + "_living_room"

    if value == "outside":
        return "outside"

    if value.startswith("shared_"):
        return value

    if value.startswith("dwelling_"):
        return value

    role = SPACE_ROLE_ALIASES.get(value, value)

    if role == "current":
        return "current"

    if role == "outside":
        return "outside"

    if role.startswith("shared_"):
        return role

    if role.startswith("dwelling_"):
        return role

    return dwelling_id + "_" + role


def make_simple_space_id(
    space_id: str,
    dwelling_id: str = DEFAULT_DWELLING_ID,
) -> str:
    """
    Convert dwelling-aware IDs back to simple IDs when needed.

    Examples:
        dwelling_1_living_room -> living_room
        dwelling_2_kitchen -> kitchen
        shared_corridor -> shared_corridor
        outside -> outside
    """

    if space_id is None:
        return ""

    value = str(space_id)

    if value == "outside":
        return "outside"

    if value.startswith("shared_"):
        return value

    prefix = dwelling_id + "_"

    if value.startswith(prefix):
        return value[len(prefix):]

    parts = value.split("_")

    if len(parts) >= 3 and parts[0] == "dwelling" and parts[1].isdigit():
        return "_".join(parts[2:])

    return value


def is_dwelling_aware_space_id(space_id: str) -> bool:
    if space_id is None:
        return False

    value = str(space_id)

    return (
        value == "outside"
        or value.startswith("shared_")
        or value.startswith("dwelling_")
    )


@dataclass
class OccupantLocation:
    """
    Dynamic location state of one occupant.

    Backward-compatible:
        current_space_id can still be "living_room", "kitchen", etc.

    Dwelling-aware:
        current_space_id can also be "dwelling_1_living_room", etc.
    """

    occupant_id: str

    # Keep dwelling_id before building_id for compatibility with old code that
    # may have used positional arguments after occupant_id.
    dwelling_id: str = DEFAULT_DWELLING_ID
    building_id: str = DEFAULT_BUILDING_ID

    is_home: bool = True
    current_space_id: str = "dwelling_1_living_room"
    current_space_role: str = "idle"
    current_activity: str = "idle"
    away_reason: str = "none"
    minutes_since_last_space_change: float = 999.0

    def copy(self, **updates: Any) -> "OccupantLocation":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "occupant_id": self.occupant_id,
            "building_id": self.building_id,
            "dwelling_id": self.dwelling_id,
            "is_home": self.is_home,
            "current_space_id": self.current_space_id,
            "current_space_role": self.current_space_role,
            "current_activity": self.current_activity,
            "away_reason": self.away_reason,
            "minutes_since_last_space_change": self.minutes_since_last_space_change,
        }

    def dwelling_aware_space_id(self) -> str:
        if not self.is_home:
            return "outside"

        return make_dwelling_space_id(
            space_id=self.current_space_id,
            dwelling_id=self.dwelling_id,
        )

    def simple_space_id(self) -> str:
        return make_simple_space_id(
            space_id=self.current_space_id,
            dwelling_id=self.dwelling_id,
        )

    def to_dwelling_aware(
        self,
        building_id: Optional[str] = None,
        dwelling_id: Optional[str] = None,
    ) -> "OccupantLocation":
        new_building_id = building_id if building_id is not None else self.building_id
        new_dwelling_id = dwelling_id if dwelling_id is not None else self.dwelling_id

        if not self.is_home:
            return self.copy(
                building_id=new_building_id,
                dwelling_id=new_dwelling_id,
                current_space_id="outside",
            )

        return self.copy(
            building_id=new_building_id,
            dwelling_id=new_dwelling_id,
            current_space_id=make_dwelling_space_id(
                self.current_space_id,
                new_dwelling_id,
            ),
        )

    def move_to_space(
        self,
        space_id: str,
        space_role: Optional[str] = None,
        activity: Optional[str] = None,
        dwelling_aware: bool = False,
    ) -> "OccupantLocation":
        if dwelling_aware:
            target_space_id = make_dwelling_space_id(
                space_id=space_id,
                dwelling_id=self.dwelling_id,
            )
        else:
            target_space_id = space_id

        if space_role is None:
            space_role = self.current_space_role

        if activity is None:
            activity = self.current_activity

        return self.copy(
            is_home=target_space_id != "outside",
            current_space_id=target_space_id,
            current_space_role=space_role,
            current_activity=activity,
            away_reason="none" if target_space_id != "outside" else self.away_reason,
            minutes_since_last_space_change=0.0,
        )

    def leave_home(
        self,
        away_reason: str = "outside",
        activity: Optional[str] = None,
    ) -> "OccupantLocation":
        if activity is None:
            activity = away_reason

        return self.copy(
            is_home=False,
            current_space_id="outside",
            current_space_role="outside",
            current_activity=activity,
            away_reason=away_reason,
            minutes_since_last_space_change=0.0,
        )

    def return_home(
        self,
        target_space_id: Optional[str] = None,
        target_space_role: str = "idle",
        activity: str = "idle",
        dwelling_aware: bool = False,
    ) -> "OccupantLocation":
        if target_space_id is None:
            target_space_id = "living_room"

        if dwelling_aware:
            target_space_id = make_dwelling_space_id(
                target_space_id,
                self.dwelling_id,
            )

        return self.copy(
            is_home=True,
            current_space_id=target_space_id,
            current_space_role=target_space_role,
            current_activity=activity,
            away_reason="none",
            minutes_since_last_space_change=0.0,
        )

    def advance_time(self, dt_minutes: float) -> "OccupantLocation":
        return self.copy(
            minutes_since_last_space_change=(
                self.minutes_since_last_space_change + float(dt_minutes)
            )
        )


@dataclass
class SpaceAssignment:
    """
    Static/default space assignment for one occupant.

    role_to_space_id can contain either:
        "kitchen"
        or
        "dwelling_1_kitchen"

    The resolve() method supports both.
    """

    occupant_id: str

    # Keep dwelling_id before building_id for compatibility.
    dwelling_id: str = DEFAULT_DWELLING_ID
    building_id: str = DEFAULT_BUILDING_ID

    default_space_id: str = "dwelling_1_living_room"
    role_to_space_id: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.role_to_space_id:
            self.role_to_space_id = default_role_to_space_id(
                dwelling_id=self.dwelling_id,
                dwelling_aware=True,
            )

    def copy(self, **updates: Any) -> "SpaceAssignment":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "occupant_id": self.occupant_id,
            "building_id": self.building_id,
            "dwelling_id": self.dwelling_id,
            "default_space_id": self.default_space_id,
            "role_to_space_id": dict(self.role_to_space_id),
        }

    def resolve(
        self,
        role: str,
        available_space_ids: Optional[Iterable[str]] = None,
    ) -> str:
        """
        Resolve a semantic role to a concrete space ID.

        Works with both old simple zones and new dwelling-aware zones.
        """

        if role is None:
            role = "idle"

        role = str(role)

        if role == "outside":
            return "outside"

        if role == "current":
            return "current"

        if role == "door":
            role = "entrance"

        resolved_role = SPACE_ROLE_ALIASES.get(role, role)

        if resolved_role == "outside":
            return "outside"

        if resolved_role == "current":
            return "current"

        target = self.role_to_space_id.get(resolved_role)

        if target is None:
            target = self.role_to_space_id.get(role)

        if target is None:
            target = resolved_role

        candidates = self._candidate_space_ids(target)

        available = _to_set(available_space_ids)

        if available is not None:
            for candidate in candidates:
                if candidate in available:
                    return candidate

            default_candidates = self._candidate_space_ids(self.default_space_id)

            for candidate in default_candidates:
                if candidate in available:
                    return candidate

        return candidates[0]

    def to_dwelling_aware(
        self,
        building_id: Optional[str] = None,
        dwelling_id: Optional[str] = None,
    ) -> "SpaceAssignment":
        new_building_id = building_id if building_id is not None else self.building_id
        new_dwelling_id = dwelling_id if dwelling_id is not None else self.dwelling_id

        new_role_map = {}

        for role, space_id in self.role_to_space_id.items():
            new_role_map[role] = make_dwelling_space_id(
                space_id=space_id,
                dwelling_id=new_dwelling_id,
            )

        return self.copy(
            building_id=new_building_id,
            dwelling_id=new_dwelling_id,
            default_space_id=make_dwelling_space_id(
                self.default_space_id,
                new_dwelling_id,
            ),
            role_to_space_id=new_role_map,
        )

    def _candidate_space_ids(self, space_id: str) -> List[str]:
        dwelling_aware = make_dwelling_space_id(
            space_id=space_id,
            dwelling_id=self.dwelling_id,
        )

        simple = make_simple_space_id(
            space_id=space_id,
            dwelling_id=self.dwelling_id,
        )

        candidates = []

        for item in [space_id, dwelling_aware, simple]:
            if item not in candidates:
                candidates.append(item)

        return candidates


def default_role_to_space_id(
    dwelling_id: str = DEFAULT_DWELLING_ID,
    dwelling_aware: bool = True,
) -> Dict[str, str]:
    """
    Default role mapping for one dwelling.
    """

    simple_map = {
        "idle": "living_room",
        "living_room": "living_room",
        "sleep": "bedroom_1",
        "bedroom": "bedroom_1",
        "bedroom_1": "bedroom_1",
        "child_sleep": "bedroom_2",
        "bedroom_2": "bedroom_2",
        "work": "office",
        "schoolwork": "office",
        "office": "office",
        "kitchen": "kitchen",
        "bathroom": "bathroom",
        "laundry": "laundry",
        "entrance": "entrance",
        "door": "entrance",
        "care": "living_room",
        "outside": "outside",
    }

    if not dwelling_aware:
        return simple_map

    out = {}

    for role, space_id in simple_map.items():
        out[role] = make_dwelling_space_id(
            space_id=space_id,
            dwelling_id=dwelling_id,
        )

    return out


def make_dwelling_aware_locations(
    locations: Dict[str, OccupantLocation],
    building_id: str = DEFAULT_BUILDING_ID,
    dwelling_id: str = DEFAULT_DWELLING_ID,
) -> Dict[str, OccupantLocation]:
    """
    Convert a dictionary of locations to dwelling-aware locations.
    """

    out = {}

    for occupant_id, location in locations.items():
        out[occupant_id] = location.to_dwelling_aware(
            building_id=building_id,
            dwelling_id=dwelling_id,
        )

    return out


def make_dwelling_aware_assignments(
    assignments: Dict[str, SpaceAssignment],
    building_id: str = DEFAULT_BUILDING_ID,
    dwelling_id: str = DEFAULT_DWELLING_ID,
) -> Dict[str, SpaceAssignment]:
    """
    Convert a dictionary of assignments to dwelling-aware assignments.
    """

    out = {}

    for occupant_id, assignment in assignments.items():
        out[occupant_id] = assignment.to_dwelling_aware(
            building_id=building_id,
            dwelling_id=dwelling_id,
        )

    return out


def _to_set(value: Optional[Iterable[str]]) -> Optional[set]:
    if value is None:
        return None

    return set(value)