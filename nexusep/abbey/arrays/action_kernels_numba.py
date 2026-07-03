"""
ABBEY numba action kernels.

Phase 18:
    Start with stable action-score postprocessing:
        - reset action_scores
        - deterministic argmax
        - chosen action IDs

Full action scoring is attempted through a guarded optional dispatcher.
"""

from nexusep.abbey.arrays import schema
from nexusep.abbey.arrays.numba_support import optional_njit, NUMBA_AVAILABLE
from nexusep.abbey.arrays.action_kernels import score_all_person_actions


ACTION_SCORE_TOTAL = schema.ACTION_SCORE_TOTAL
ACTION_ID = schema.ACTION_ID


@optional_njit(cache=True)
def reset_action_scores_numba(action_scores):
    for person_i in range(action_scores.shape[0]):
        for action_i in range(action_scores.shape[1]):
            for score_i in range(action_scores.shape[2]):
                action_scores[person_i, action_i, score_i] = 0.0

    return True


@optional_njit(cache=True)
def choose_best_action_indices_from_scores_numba(
    action_scores,
    chosen_action_indices,
):
    for person_i in range(action_scores.shape[0]):
        best_action_i = 0
        best_score = action_scores[person_i, 0, ACTION_SCORE_TOTAL]

        for action_i in range(1, action_scores.shape[1]):
            score = action_scores[person_i, action_i, ACTION_SCORE_TOTAL]

            if score > best_score:
                best_score = score
                best_action_i = action_i

        chosen_action_indices[person_i] = best_action_i

    return True


@optional_njit(cache=True)
def choose_best_actions_from_scores_numba(
    action_scores,
    action_static,
    chosen_action_ids,
):
    for person_i in range(action_scores.shape[0]):
        best_action_i = 0
        best_score = action_scores[person_i, 0, ACTION_SCORE_TOTAL]

        for action_i in range(1, action_scores.shape[1]):
            score = action_scores[person_i, action_i, ACTION_SCORE_TOTAL]

            if score > best_score:
                best_score = score
                best_action_i = action_i

        chosen_action_ids[person_i] = int(action_static[best_action_i, ACTION_ID])

    return True


# Full action scoring: guarded optional dispatcher.
# This is intentionally not required for Phase 18 to pass, because your current
# action scoring tree is much larger than the argmax kernels.
if NUMBA_AVAILABLE:
    _score_all_person_actions_dispatcher = optional_njit(cache=True)(
        score_all_person_actions
    )
else:
    _score_all_person_actions_dispatcher = score_all_person_actions


def score_all_person_actions_optional_numba(
    person_state,
    person_static,
    zone_state,
    zone_static,
    system_state,
    system_static,
    process_state,
    action_static,
    action_scores,
    schedule_array,
    time_state,
    sleep_pressure_scores,
    electricity_tariff=0.25,
):
    """
    Try numba-compiled full action scoring.

    If compilation fails on the current codebase, fall back to Python scoring.
    This keeps the public behavior stable while you clean the scoring tree.
    """
    try:
        return _score_all_person_actions_dispatcher(
            person_state=person_state,
            person_static=person_static,
            zone_state=zone_state,
            zone_static=zone_static,
            system_state=system_state,
            system_static=system_static,
            process_state=process_state,
            action_static=action_static,
            action_scores=action_scores,
            schedule_array=schedule_array,
            time_state=time_state,
            sleep_pressure_scores=sleep_pressure_scores,
            electricity_tariff=electricity_tariff,
        )
    except Exception:
        return score_all_person_actions(
            person_state=person_state,
            person_static=person_static,
            zone_state=zone_state,
            zone_static=zone_static,
            system_state=system_state,
            system_static=system_static,
            process_state=process_state,
            action_static=action_static,
            action_scores=action_scores,
            schedule_array=schedule_array,
            time_state=time_state,
            sleep_pressure_scores=sleep_pressure_scores,
            electricity_tariff=electricity_tariff,
        )