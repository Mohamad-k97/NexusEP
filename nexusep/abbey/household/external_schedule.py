from typing import Any, Dict, List

from nexusep.abbey.actions.proposal import ActionProposal
from nexusep.abbey.agents.states import PersonState, SimulationClock
from nexusep.abbey.agents.location import OccupantLocation, SpaceAssignment
from nexusep.abbey.household.calendar import get_day_type, get_weekday_name


def _hour_of_day(clock: SimulationClock) -> float:
    return float(clock.hour) % 24.0


def _inside_window(hour: float, start: float, end: float) -> bool:
    if start <= end:
        return start <= hour <= end

    return hour >= start or hour <= end


def _resolve_assignment_space(
    assignment: SpaceAssignment,
    role: str,
    fallback: str,
) -> str:
    return assignment.role_to_space_id.get(role, fallback)


def _get_schedule_for_today(
    schedule_name: str,
    clock: SimulationClock,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    schedules = config.get("external_schedules", {})
    schedule_group = schedules.get(schedule_name, {})

    day_type = get_day_type(day=int(clock.day), config=config)

    today_schedule = schedule_group.get(day_type, {})

    if not today_schedule.get("enabled", False):
        return {}

    return today_schedule


def make_external_schedule_proposals(
    people: Dict[str, PersonState],
    locations: Dict[str, OccupantLocation],
    assignments: Dict[str, SpaceAssignment],
    clock: SimulationClock,
    config: Dict[str, Any],
) -> List[ActionProposal]:
    proposals = []

    actions = config.get("actions", {})
    hour = _hour_of_day(clock)
    day_type = get_day_type(day=int(clock.day), config=config)
    weekday_name = get_weekday_name(day=int(clock.day), config=config)

    work_today = _get_schedule_for_today(
        schedule_name="work",
        clock=clock,
        config=config,
    )

    school_today = _get_schedule_for_today(
        schedule_name="school",
        clock=clock,
        config=config,
    )

    for occupant_id, person in people.items():
        if not getattr(person, "can_act", True):
            continue

        if getattr(person, "age_group", "") == "infant":
            continue

        location = locations.get(occupant_id)
        assignment = assignments.get(occupant_id)

        if location is None or assignment is None:
            continue



        # ----------------------------
        # WORK LEAVE
        # ----------------------------
        if (
            getattr(person, "has_job", False)
            and location.is_home
            and work_today
            and "go_to_work" in actions
            and _inside_window(
                hour,
                float(work_today.get("leave_start_hour", 7.5)),
                float(work_today.get("leave_end_hour", 9.0)),
            )
        ):
            entrance_id = _resolve_assignment_space(
                assignment=assignment,
                role="entrance",
                fallback=assignment.default_space_id,
            )

            proposals.append(
                ActionProposal(
                    actor_id=occupant_id,
                    action_name="go_to_work",
                    score=float(work_today.get("leave_score", 5.0)),
                    target_space_id=entrance_id,
                    target_space_role="entrance",
                    is_household_action=False,
                    conflict_group="same_person_foreground:" + occupant_id,
                    authority_weight=float(
                        getattr(person, "authority_weight", 1.0)
                    ),
                    reason="external_work_schedule",
                    metadata={
                        "category": "external",
                        "schedule_type": "work_leave",
                        "day_type": day_type,
                        "weekday_name": weekday_name,
                        "hour": hour,
                    },
                )
            )

        # ----------------------------
        # SCHOOL LEAVE
        # ----------------------------
        if (
            getattr(person, "has_school", False)
            and location.is_home
            and school_today
            and "go_to_school" in actions
            and _inside_window(
                hour,
                float(school_today.get("leave_start_hour", 7.25)),
                float(school_today.get("leave_end_hour", 8.25)),
            )
        ):
            entrance_id = _resolve_assignment_space(
                assignment=assignment,
                role="entrance",
                fallback=assignment.default_space_id,
            )

            proposals.append(
                ActionProposal(
                    actor_id=occupant_id,
                    action_name="go_to_school",
                    score=float(school_today.get("leave_score", 5.5)),
                    target_space_id=entrance_id,
                    target_space_role="entrance",
                    is_household_action=False,
                    conflict_group="same_person_foreground:" + occupant_id,
                    authority_weight=float(
                        getattr(person, "authority_weight", 1.0)
                    ),
                    reason="external_school_schedule",
                    metadata={
                        "category": "external",
                        "schedule_type": "school_leave",
                        "day_type": day_type,
                        "weekday_name": weekday_name,
                        "hour": hour,
                    },
                )
            )

        # ----------------------------
        # RETURN HOME
        # ----------------------------
        if not location.is_home:
            away_reason = getattr(location, "away_reason", "none")

            if away_reason == "work":
                today_schedule = work_today
                default_start = 17.0
                default_end = 19.5
                default_score = 5.0
                reason = "external_work_return"

            elif away_reason == "school":
                today_schedule = school_today
                default_start = 13.0
                default_end = 15.0
                default_score = 5.5
                reason = "external_school_return"

            else:
                continue

            if not today_schedule:
                continue

            if (
                "return_home" in actions
                and _inside_window(
                    hour,
                    float(today_schedule.get("return_start_hour", default_start)),
                    float(today_schedule.get("return_end_hour", default_end)),
                )
            ):
                idle_id = _resolve_assignment_space(
                    assignment=assignment,
                    role="idle",
                    fallback=assignment.default_space_id,
                )

                proposals.append(
                    ActionProposal(
                        actor_id=occupant_id,
                        action_name="return_home",
                        score=float(today_schedule.get("return_score", default_score)),
                        target_space_id=idle_id,
                        target_space_role="idle",
                        is_household_action=False,
                        conflict_group="same_person_foreground:" + occupant_id,
                        authority_weight=float(
                            getattr(person, "authority_weight", 1.0)
                        ),
                        reason=reason,
                        metadata={
                            "category": "external",
                            "schedule_type": "return_home",
                            "away_reason": away_reason,
                            "day_type": day_type,
                            "weekday_name": weekday_name,
                            "hour": hour,
                        },
                    )
                )

    return proposals