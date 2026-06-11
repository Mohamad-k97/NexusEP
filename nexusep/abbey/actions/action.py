"""
ABBEY action blueprint.

Action = definition from config.
ActionState = running instance of that action.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict

from nexusep.abbey.agents.states import ActionState


@dataclass
class Action:
    name: str
    category: str = "passive"
    execution_type: str = "passive"

    duration_minutes: float = 1.0

    power_w: float = 0.0
    activity_intensity: float = 0.0
    effort: float = 0.0

    requires_home: bool = False
    requires_awake: bool = False

    blocks_actor: bool = False
    background_process: bool = False
    can_continue_without_actor: bool = True
    can_be_interrupted: bool = True
    can_fill_remaining_time: bool = False
    can_repeat: bool = False
    
    system_effects: Dict[str, Any] = field(default_factory=dict)
    person_effects: Dict[str, Any] = field(default_factory=dict)
    
    action_cooldowns_on_start: Dict[str, float] = field(default_factory=dict)
    post_action_zone_role: str = "current"
    target_zone_role: str = "current"
    
    def to_state(self, actor_id: str = "person_1") -> ActionState:
        return ActionState(
            name=self.name,
            category=self.category,
            execution_type=self.execution_type,
            actor_id=actor_id,
            remaining_minutes=self.duration_minutes,
            elapsed_minutes=0.0,
            power_w=self.power_w,
            activity_intensity=self.activity_intensity,
            effort=self.effort,
            requires_home=self.requires_home,
            requires_awake=self.requires_awake,
            blocks_actor=self.blocks_actor,
            background_process=self.background_process,
            can_continue_without_actor=self.can_continue_without_actor,
            can_be_interrupted=self.can_be_interrupted,
            can_fill_remaining_time=self.can_fill_remaining_time,
            can_repeat=self.can_repeat,
            system_effects=dict(self.system_effects),
            person_effects=dict(self.person_effects),
            action_cooldowns_on_start=dict(self.action_cooldowns_on_start),
            target_zone_role=self.target_zone_role,
            post_action_zone_role=self.post_action_zone_role,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)