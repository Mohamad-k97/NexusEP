"""
ABBEY action proposal layer.

A proposal is not yet an executed action.
It is one occupant's candidate action before household arbitration.
"""

from dataclasses import dataclass, field, asdict, replace
from typing import Any, Dict, Optional


@dataclass
class ActionProposal:
    """
    Candidate action proposed by one occupant.

    Later, household arbitration will compare proposals and decide
    which actions are actually executed.
    """

    actor_id: str
    action_name: str

    score: float = 0.0

    target_space_id: str = ""
    target_space_role: str = "current"

    is_household_action: bool = False

    # Examples:
    #   same_person_foreground
    #   household_cooking
    #   laundry_machine
    #   same_space_light_control
    #   same_space_window_control
    conflict_group: str = ""

    # Copied from PersonState.authority_weight during proposal creation.
    authority_weight: float = 1.0

    # Optional explanation/debug info.
    reason: str = ""

    metadata: Dict[str, Any] = field(default_factory=dict)

    def weighted_score(self) -> float:
        return self.score * self.authority_weight

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def copy(self, **updates: Any) -> "ActionProposal":
        return replace(self, **updates)