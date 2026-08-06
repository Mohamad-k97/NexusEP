"""
Compare reference and fast moisture kernels.

Run:
    python -m pytest tests/phase18/test_18_24_moisture_fast_compare.py

Provenance:
    adapted from Phase 18.24 content found under the overwritten Phase 17.5
    filename at frozen HEAD.
"""

import numpy as np

from nexusep.abbey.arrays import schema
from nexusep.abbey.arrays.encoder import compile_simulation_to_arrays
from nexusep.abbey.arrays.moisture_kernels import (
    step_building_moisture_balance,
    step_building_moisture_balance_fast,
)
from benchmarks.arrays.phase_18_20_8760 import (
    make_8760_multizone_dwelling_input,
)


def test_fast_moisture_kernel_matches_reference():
    state_ref = compile_simulation_to_arrays(
        make_8760_multizone_dwelling_input()
    )
    state_fast = compile_simulation_to_arrays(
        make_8760_multizone_dwelling_input()
    )

    # Give the moisture step non-trivial but stable inputs.
    for zone_i in range(state_ref.dynamic.zone_state.shape[0]):
        state_ref.dynamic.zone_state[
            zone_i,
            schema.ZONE_RELATIVE_HUMIDITY,
        ] = 0.35 + 0.07 * zone_i

        state_ref.dynamic.zone_state[
            zone_i,
            schema.ZONE_AIR_TEMPERATURE_C,
        ] = 18.0 + 1.5 * zone_i

        state_ref.dynamic.zone_state[
            zone_i,
            schema.ZONE_MOISTURE_GAIN_KG_S,
        ] = 0.000002 * (zone_i + 1)

        state_ref.dynamic.zone_state[
            zone_i,
            schema.ZONE_OUTDOOR_AIRFLOW_M3_S,
        ] = 0.01 * zone_i

        state_ref.dynamic.zone_state[
            zone_i,
            schema.ZONE_INFILTRATION_AIRFLOW_M3_S,
        ] = 0.005

    state_ref.dynamic.weather_state[
        schema.WEATHER_OUTDOOR_RELATIVE_HUMIDITY
    ] = 0.65
    state_ref.dynamic.weather_state[
        schema.WEATHER_OUTDOOR_TEMPERATURE_C
    ] = 8.0

    state_fast.dynamic.zone_state[:, :] = state_ref.dynamic.zone_state[:, :]
    state_fast.dynamic.weather_state[:] = state_ref.dynamic.weather_state[:]
    state_fast.dynamic.internal_gains[:, :] = state_ref.dynamic.internal_gains[:, :]

    step_building_moisture_balance(
        zone_state=state_ref.dynamic.zone_state,
        zone_static=state_ref.static.zone_static,
        weather_state=state_ref.dynamic.weather_state,
        internal_gains=state_ref.dynamic.internal_gains,
        physics_result=state_ref.dynamic.physics_result,
        dt_minutes=60,
        airflow_link_array=None,
        copy_zone_gains=True,
    )

    step_building_moisture_balance_fast(
        zone_state=state_fast.dynamic.zone_state,
        zone_static=state_fast.static.zone_static,
        weather_state=state_fast.dynamic.weather_state,
        internal_gains=state_fast.dynamic.internal_gains,
        physics_result=state_fast.dynamic.physics_result,
        dt_minutes=60,
        airflow_link_array=None,
        copy_zone_gains=True,
    )

    rh_ref = state_ref.dynamic.zone_state[
        :,
        schema.ZONE_RELATIVE_HUMIDITY,
    ]
    rh_fast = state_fast.dynamic.zone_state[
        :,
        schema.ZONE_RELATIVE_HUMIDITY,
    ]

    physics_ref = state_ref.dynamic.physics_result
    physics_fast = state_fast.dynamic.physics_result

    if not np.allclose(rh_ref, rh_fast, rtol=1.0e-10, atol=1.0e-10):
        print("RH mismatch")
        print("ref:", rh_ref)
        print("fast:", rh_fast)
        print("diff:", rh_fast - rh_ref)
        raise AssertionError("Fast moisture RH mismatch.")

    if not np.allclose(physics_ref, physics_fast, rtol=1.0e-10, atol=1.0e-10):
        print("Physics result mismatch")
        print("max abs diff:", np.max(np.abs(physics_fast - physics_ref)))
        print("ref:")
        print(physics_ref)
        print("fast:")
        print(physics_fast)
        print("diff:")
        print(physics_fast - physics_ref)
        raise AssertionError("Fast moisture physics_result mismatch.")

    print("Fast moisture kernel matches reference.")


def main():
    test_fast_moisture_kernel_matches_reference()


if __name__ == "__main__":
    main()
