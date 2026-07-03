"""
Compare old reference action scoring with fast inlined action scoring.

Run:

    python -m nexusep.abbey.run_test_phase_18_22_action_scoring_fast_compare
"""

import numpy as np

from nexusep.abbey.arrays.encoder import compile_simulation_to_arrays
from nexusep.abbey.arrays.action_kernels import (
    score_all_person_actions,
    score_all_person_actions_reference,
)
from nexusep.abbey.run_test_phase_18_0 import (
    make_8760_multizone_dwelling_input,
)


def main():
    state = compile_simulation_to_arrays(
        make_8760_multizone_dwelling_input()
    )

    scores_ref = state.dynamic.action_scores.copy()
    scores_fast = state.dynamic.action_scores.copy()

    score_all_person_actions_reference(
        person_state=state.dynamic.person_state,
        person_static=state.static.person_static,
        zone_state=state.dynamic.zone_state,
        zone_static=state.static.zone_static,
        system_state=state.dynamic.system_state,
        system_static=state.static.system_static,
        process_state=state.dynamic.process_state,
        action_static=state.static.action_static,
        action_scores=scores_ref,
        schedule_array=state.metadata["person_schedule_array"],
        time_state=state.dynamic.time_state,
        sleep_pressure_scores=None,
        electricity_tariff=0.25,
    )

    score_all_person_actions(
        person_state=state.dynamic.person_state,
        person_static=state.static.person_static,
        zone_state=state.dynamic.zone_state,
        zone_static=state.static.zone_static,
        system_state=state.dynamic.system_state,
        system_static=state.static.system_static,
        process_state=state.dynamic.process_state,
        action_static=state.static.action_static,
        action_scores=scores_fast,
        schedule_array=state.metadata["person_schedule_array"],
        time_state=state.dynamic.time_state,
        sleep_pressure_scores=None,
        electricity_tariff=0.25,
    )

    if not np.allclose(scores_ref, scores_fast, rtol=1.0e-9, atol=1.0e-9):
        diff = scores_fast - scores_ref
        max_abs = np.max(np.abs(diff))

        print("Action scoring mismatch.")
        print("max_abs_diff:", max_abs)
        print("reference scores:")
        print(scores_ref)
        print("fast scores:")
        print(scores_fast)
        print("diff:")
        print(diff)

        raise AssertionError("Fast action scoring does not match reference.")

    print("Fast action scoring matches reference.")


if __name__ == "__main__":
    main()