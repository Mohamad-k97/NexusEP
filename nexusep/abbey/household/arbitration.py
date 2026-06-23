"""
ABBEY household action arbitration.

Receives action proposals from occupants and decides which proposals survive.

For v0.3:
    - remove impossible/very bad proposals
    - choose one proposal per actor
    - resolve shared conflicts by authority-weighted score
    - use random tie-break if scores are close
"""

import random
from collections import defaultdict
from typing import Dict, List, Optional

from nexusep.abbey.actions.proposal import ActionProposal
from nexusep.abbey.household.state import HouseholdState


def _proposal_is_valid(
    proposal: ActionProposal,
    min_score: float,
) -> bool:
    """
    Remove proposals that are intentionally blocked by scoring.

    We often use -999 as a soft impossibility marker.
    """

    if proposal.score <= min_score:
        return False

    return True


def _choose_best_proposal(
    proposals: List[ActionProposal],
    rng: random.Random,
    tie_margin: float,
) -> Optional[ActionProposal]:
    """
    Choose best proposal by authority-weighted score.

    If several proposals are very close, choose randomly among them.
    """

    if not proposals:
        return None

    best_score = max(p.weighted_score() for p in proposals)

    near_best = [
        p for p in proposals
        if abs(p.weighted_score() - best_score) <= tie_margin
    ]

    return rng.choice(near_best)


def _group_by_actor(
    proposals: List[ActionProposal],
) -> Dict[str, List[ActionProposal]]:
    grouped = defaultdict(list)

    for proposal in proposals:
        grouped[proposal.actor_id].append(proposal)

    return dict(grouped)


def _group_by_conflict(
    proposals: List[ActionProposal],
) -> Dict[str, List[ActionProposal]]:
    grouped = defaultdict(list)

    for proposal in proposals:
        if proposal.conflict_group:
            grouped[proposal.conflict_group].append(proposal)

    return dict(grouped)


def _deduplicate_selected(
    proposals: List[ActionProposal],
) -> List[ActionProposal]:
    """
    Keep unique proposals.

    Useful because the same proposal can pass through actor-level and
    conflict-level selection.
    """

    seen = set()
    unique = []

    for proposal in proposals:
        key = (
            proposal.actor_id,
            proposal.action_name,
            proposal.target_space_id,
            proposal.conflict_group,
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(proposal)

    return unique

def _apply_household_priority_adjustments(
    proposals: List[ActionProposal],
    household: HouseholdState,
) -> List[ActionProposal]:
    adjusted = []

    for proposal in proposals:
        if proposal.action_name != "cook":
            adjusted.append(proposal)
            continue

        priority = household.cooking_priority_by_occupant.get(
            proposal.actor_id,
            999,
        )

        bonus = 0.0

        if proposal.actor_id == household.main_cook_id:
            bonus += 1.0

        bonus += max(0.0, (100.0 - float(priority)) / 100.0)

        adjusted.append(
            proposal.copy(
                score=proposal.score + bonus,
                metadata={
                    **proposal.metadata,
                    "cooking_priority": priority,
                    "main_cook_bonus_applied": proposal.actor_id == household.main_cook_id,
                },
            )
        )

    return adjusted

def arbitrate_household_actions(
    proposals: List[ActionProposal],
    household: HouseholdState,
    rng: random.Random,
    min_score: float = -998.0,
    tie_margin: float = 0.05,
) -> List[ActionProposal]:

    proposals = _apply_household_priority_adjustments(
        proposals=proposals,
        household=household,
    )

    valid = [
        proposal for proposal in proposals
        if _proposal_is_valid(proposal, min_score=min_score)
    ]

    if not valid:
        return []

    # ------------------------------------------------------------
    # Step 1: one proposal per actor
    # ------------------------------------------------------------
    proposals = _apply_household_priority_adjustments(
        proposals=proposals,
        household=household,
    )
    actor_selected = []

    for actor_id, actor_proposals in _group_by_actor(valid).items():
        chosen = _choose_best_proposal(
            proposals=actor_proposals,
            rng=rng,
            tie_margin=tie_margin,
        )

        if chosen is not None:
            actor_selected.append(chosen)

    actor_selected = _deduplicate_selected(actor_selected)

    # ------------------------------------------------------------
    # Step 2: resolve shared conflict groups
    # ------------------------------------------------------------

    selected_by_key = {
        (
            proposal.actor_id,
            proposal.action_name,
            proposal.target_space_id,
            proposal.conflict_group,
        ): proposal
        for proposal in actor_selected
    }

    for conflict_group, group in _group_by_conflict(actor_selected).items():
        if len(group) <= 1:
            continue

        winner = _choose_best_proposal(
            proposals=group,
            rng=rng,
            tie_margin=tie_margin,
        )

        for proposal in group:
            key = (
                proposal.actor_id,
                proposal.action_name,
                proposal.target_space_id,
                proposal.conflict_group,
            )

            if proposal is not winner:
                selected_by_key.pop(key, None)

    return list(selected_by_key.values())