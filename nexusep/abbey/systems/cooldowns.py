"""
ABBEY shared cooldown state.

Cooldowns are separated from ExecutionState because they exist at
different levels:

- person action cooldowns
- household action cooldowns
- space/control cooldowns
"""

from dataclasses import dataclass, field, asdict, replace
from typing import Any, Dict


@dataclass
class CooldownState:
    """
    Shared cooldown state.

    All cooldown values are in minutes.
    """

    # Example:
    # {"working_man": {"make_hot_drink": 180}}
    person_action_cooldowns: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Example:
    # {"cook_family_meal": 240, "run_washing_machine": 360}
    household_action_cooldowns: Dict[str, float] = field(default_factory=dict)

    # Example:
    # {"kitchen": {"window": 20, "lights": 5}}
    space_control_cooldowns: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def person_action_on_cooldown(
        self,
        occupant_id: str,
        action_name: str,
    ) -> bool:
        return (
            self.person_action_cooldowns
            .get(occupant_id, {})
            .get(action_name, 0.0)
            > 0.0
        )

    def household_action_on_cooldown(
        self,
        action_name: str,
    ) -> bool:
        return self.household_action_cooldowns.get(action_name, 0.0) > 0.0

    def space_control_on_cooldown(
        self,
        space_id: str,
        control_name: str,
    ) -> bool:
        return (
            self.space_control_cooldowns
            .get(space_id, {})
            .get(control_name, 0.0)
            > 0.0
        )

    def set_person_action_cooldown(
        self,
        occupant_id: str,
        action_name: str,
        cooldown_minutes: float,
    ) -> "CooldownState":
        if cooldown_minutes < 0:
            raise ValueError("cooldown_minutes must be non-negative.")

        person_cooldowns = {
            pid: dict(values)
            for pid, values in self.person_action_cooldowns.items()
        }

        person_cooldowns.setdefault(occupant_id, {})

        person_cooldowns[occupant_id][action_name] = max(
            person_cooldowns[occupant_id].get(action_name, 0.0),
            float(cooldown_minutes),
        )

        return self.copy(person_action_cooldowns=person_cooldowns)

    def set_household_action_cooldown(
        self,
        action_name: str,
        cooldown_minutes: float,
    ) -> "CooldownState":
        if cooldown_minutes < 0:
            raise ValueError("cooldown_minutes must be non-negative.")

        household_cooldowns = dict(self.household_action_cooldowns)

        household_cooldowns[action_name] = max(
            household_cooldowns.get(action_name, 0.0),
            float(cooldown_minutes),
        )

        return self.copy(household_action_cooldowns=household_cooldowns)

    def set_space_control_cooldown(
        self,
        space_id: str,
        control_name: str,
        cooldown_minutes: float,
    ) -> "CooldownState":
        if cooldown_minutes < 0:
            raise ValueError("cooldown_minutes must be non-negative.")

        space_cooldowns = {
            sid: dict(values)
            for sid, values in self.space_control_cooldowns.items()
        }

        space_cooldowns.setdefault(space_id, {})

        space_cooldowns[space_id][control_name] = max(
            space_cooldowns[space_id].get(control_name, 0.0),
            float(cooldown_minutes),
        )

        return self.copy(space_control_cooldowns=space_cooldowns)

    def advance_cooldowns(
        self,
        minutes: float,
    ) -> "CooldownState":
        if minutes < 0:
            raise ValueError("minutes must be non-negative.")

        person_cooldowns = {}

        for occupant_id, cooldowns in self.person_action_cooldowns.items():
            updated = {
                name: max(0.0, remaining - minutes)
                for name, remaining in cooldowns.items()
                if max(0.0, remaining - minutes) > 0.0
            }

            if updated:
                person_cooldowns[occupant_id] = updated

        household_cooldowns = {
            name: max(0.0, remaining - minutes)
            for name, remaining in self.household_action_cooldowns.items()
            if max(0.0, remaining - minutes) > 0.0
        }

        space_cooldowns = {}

        for space_id, cooldowns in self.space_control_cooldowns.items():
            updated = {
                name: max(0.0, remaining - minutes)
                for name, remaining in cooldowns.items()
                if max(0.0, remaining - minutes) > 0.0
            }

            if updated:
                space_cooldowns[space_id] = updated

        return self.copy(
            person_action_cooldowns=person_cooldowns,
            household_action_cooldowns=household_cooldowns,
            space_control_cooldowns=space_cooldowns,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def copy(self, **updates: Any) -> "CooldownState":
        return replace(self, **updates)