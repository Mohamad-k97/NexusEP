"""
ABBEY household state.

HouseholdState stores shared household-level variables.
These are not individual physiological states and should not live
inside PersonState.
"""

from dataclasses import dataclass, field, asdict, replace
from typing import Any, Dict, List


@dataclass
class HouseholdState:
    """
    Shared state of one household.

    This is multi-occupant ready, even if the current simulation still
    runs only one or a few simple agents.
    """

    household_id: str = "household_1"

    # Occupants belonging to this household
    occupant_ids: List[str] = field(default_factory=lambda: ["person_1"])

    # Cooking coordination
    main_cook_id: str = "person_1"

    # Lower value = higher priority.
    # Example:
    #   {"housewife": 1, "working_man": 2, "schoolboy": 3}
    cooking_priority_by_occupant: Dict[str, int] = field(
        default_factory=lambda: {"person_1": 1}
    )

    # Household laundry stock.
    # Smooth 0-1 value for now:
    #   0 = no dirty clothes
    #   1 = urgent laundry pile
    dirty_clothes: float = 0.20

    # Lower value = higher priority for starting laundry.
    laundry_priority_by_occupant: Dict[str, int] = field(
        default_factory=lambda: {"person_1": 1}
    )

    # Shared cooldowns.
    # Example:
    #   {"cook_family_meal": 240, "run_washing_machine": 360}
    household_action_cooldowns: Dict[str, float] = field(default_factory=dict)

    # Event counters / diagnostics
    cooked_meal_events: int = 0
    laundry_events: int = 0
    fallback_meal_events: int = 0

    last_cook_id: str = ""
    last_laundry_actor_id: str = ""
    
    care_events: int = 0
    last_caregiver_id: str = ""
    last_care_target_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def copy(self, **updates: Any) -> "HouseholdState":
        return replace(self, **updates)

    def action_on_cooldown(self, action_name: str) -> bool:
        return self.household_action_cooldowns.get(action_name, 0.0) > 0.0

    def advance_cooldowns(self, minutes: float) -> "HouseholdState":
        if minutes < 0:
            raise ValueError("minutes must be non-negative.")

        new_cooldowns = {
            name: max(0.0, remaining - minutes)
            for name, remaining in self.household_action_cooldowns.items()
            if max(0.0, remaining - minutes) > 0.0
        }

        return self.copy(household_action_cooldowns=new_cooldowns)

    def set_action_cooldown(
        self,
        action_name: str,
        cooldown_minutes: float,
    ) -> "HouseholdState":
        if cooldown_minutes < 0:
            raise ValueError("cooldown_minutes must be non-negative.")

        new_cooldowns = dict(self.household_action_cooldowns)

        new_cooldowns[action_name] = max(
            new_cooldowns.get(action_name, 0.0),
            float(cooldown_minutes),
        )

        return self.copy(household_action_cooldowns=new_cooldowns)