"""
ABBEY numba execution kernels.

Phase 18:
    Guarded optional numba dispatcher for the in-place execution step.

Execution has many branches, so keep a Python fallback.
"""

from nexusep.abbey.arrays.numba_support import optional_njit, NUMBA_AVAILABLE
from nexusep.abbey.arrays.execution_kernels import (
    run_execution_step_from_chosen_actions_inplace,
)


if NUMBA_AVAILABLE:
    _execution_dispatcher = optional_njit(cache=True)(
        run_execution_step_from_chosen_actions_inplace
    )
else:
    _execution_dispatcher = run_execution_step_from_chosen_actions_inplace


def run_execution_step_from_chosen_actions_optional_numba(
    person_state,
    person_static,
    zone_state,
    dwelling_state,
    building_state,
    system_state,
    system_static,
    process_state,
    action_static,
    chosen_action_indices,
    started_actions,
    dt_minutes,
    internal_gains,
):
    """
    Try numba-compiled execution step.

    If compilation fails, fall back to Python execution.
    """
    try:
        return _execution_dispatcher(
            person_state=person_state,
            person_static=person_static,
            zone_state=zone_state,
            dwelling_state=dwelling_state,
            building_state=building_state,
            system_state=system_state,
            system_static=system_static,
            process_state=process_state,
            action_static=action_static,
            chosen_action_indices=chosen_action_indices,
            started_actions=started_actions,
            dt_minutes=dt_minutes,
            internal_gains=internal_gains,
        )
    except Exception:
        return run_execution_step_from_chosen_actions_inplace(
            person_state=person_state,
            person_static=person_static,
            zone_state=zone_state,
            dwelling_state=dwelling_state,
            building_state=building_state,
            system_state=system_state,
            system_static=system_static,
            process_state=process_state,
            action_static=action_static,
            chosen_action_indices=chosen_action_indices,
            started_actions=started_actions,
            dt_minutes=dt_minutes,
            internal_gains=internal_gains,
        )