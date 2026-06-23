"""
ABBEY household proposal collection.

Collect action proposals from all capable household occupants.
This happens before household arbitration.
"""

from typing import Any, Dict, Mapping, List, Optional

from nexusep.abbey.actions.library import get_available_actions
from nexusep.abbey.actions.proposal import ActionProposal
from nexusep.abbey.agents.decision import propose_actions_for_person
from nexusep.abbey.agents.location import OccupantLocation, SpaceAssignment
from nexusep.abbey.agents.states import (
    PersonState,
    DwellingObservation,
    SystemState,
    ExecutionState,
    SimulationClock,
)
from nexusep.abbey.household.state import HouseholdState
from nexusep.abbey.systems import CooldownState
from nexusep.abbey.household.care import most_needy_dependent_at_home
from nexusep.abbey.household.external_schedule import make_external_schedule_proposals

AbbeyConfig = Mapping[str, Any]

def _make_dependent_care_proposals(
    people,
    locations,
    assignments,
    household,
    config,
    cooldowns=None,
):
    action_config = config.get("actions", {}).get("care_for_infant")
    if cooldowns is not None:
        if cooldowns.household_action_on_cooldown("care_for_infant"):
            return []
    if action_config is None:
        return []

    care_config = config.get("household_care", {})
    threshold = float(care_config.get("care_need_threshold", 0.65))

    target_id, need = most_needy_dependent_at_home(
        people=people,
        locations=locations,
    )

    if target_id is None or need < threshold:
        return []

    proposals = []

    for caregiver_id, person in people.items():
        if caregiver_id == target_id:
            continue

        if not getattr(person, "can_act", True):
            continue

        if getattr(person, "age_group", "") in ["infant", "toddler"]:
            continue

        location = locations.get(caregiver_id)

        if location is None or not location.is_home:
            continue

        if getattr(person, "is_sleeping", False):
            continue

        assignment = assignments.get(caregiver_id)

        if assignment is not None:
            target_space_id = assignment.role_to_space_id.get(
                "care",
                assignment.default_space_id,
            )
        else:
            target_space_id = "living_room"

        score = 1.25 * need
        score -= 0.25 * float(getattr(person, "fatigue", 0.0))

        proposals.append(
            ActionProposal(
                actor_id=caregiver_id,
                action_name="care_for_infant",
                score=score,
                target_space_id=target_space_id,
                target_space_role="care",
                is_household_action=True,
                conflict_group="dependent_care:" + target_id,
                authority_weight=float(
                    getattr(person, "authority_weight", 1.0)
                ),
                reason="dependent_care_need",
                metadata={
                    "category": "care",
                    "execution_type": "foreground",
                    "requires_home": True,
                    "requires_awake": True,
                    "blocks_actor": True,
                    "background_process": False,
                    "care_target_id": target_id,
                    "care_need": need,
                },
            )
        )

    return proposals

def collect_household_action_proposals(
    people: Dict[str, PersonState],
    locations: Dict[str, OccupantLocation],
    assignments: Dict[str, SpaceAssignment],
    household: HouseholdState,
    observation: DwellingObservation,
    systems: SystemState,
    execution: ExecutionState,
    clock: SimulationClock,
    config: AbbeyConfig,
    cooldowns: Optional[CooldownState] = None,
) -> List[ActionProposal]:
    """
    Collect action proposals from all capable occupants.

    For v0.3:
        - can_act=False occupants do not propose actions.
        - missing location/assignment skips the occupant.
        - household arbitration happens later.
    """

    proposals: List[ActionProposal] = []

    for occupant_id in household.occupant_ids:
        person = people.get(occupant_id)
        location = locations.get(occupant_id)
        assignment = assignments.get(occupant_id)

        if person is None or location is None or assignment is None:
            continue

        if not person.can_act:
            continue

        available_actions = get_available_actions(
            person=person,
            systems=systems,
            execution=execution,
            location=location,
            clock=clock,
            config=config,
            cooldowns=cooldowns,
        )

        person_proposals = propose_actions_for_person(
            available_actions=available_actions,
            person=person,
            observation=observation,
            systems=systems,
            execution=execution,
            location=location,
            assignment=assignment,
            clock=clock,
            config=config,
        )

        proposals.extend(person_proposals)
        
    proposals.extend(
        _make_dependent_care_proposals(
            people=people,
            locations=locations,
            assignments=assignments,
            household=household,
            config=config,
            cooldowns=cooldowns,
        )
    )
    proposals.extend(
        make_external_schedule_proposals(
            people=people,
            locations=locations,
            assignments=assignments,
            clock=clock,
            config=config,
        )
    )
    return proposals