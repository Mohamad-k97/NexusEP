"""
Compare reference and fast thermal kernels.

Run:

    python -m nexusep.abbey.run_test_phase_18_23_thermal_fast_compare
"""

import numpy as np

from nexusep.abbey.arrays import schema
from nexusep.abbey.arrays.encoder import compile_simulation_to_arrays
from nexusep.abbey.arrays.thermal_kernels import (
    step_building_thermal_semi_implicit,
    step_building_thermal_semi_implicit_fast,
)
from nexusep.abbey.run_test_phase_18_0 import (
    make_8760_multizone_dwelling_input,
)


def main():
    state_ref = compile_simulation_to_arrays(
        make_8760_multizone_dwelling_input()
    )
    state_fast = compile_simulation_to_arrays(
        make_8760_multizone_dwelling_input()
    )

    # Give the thermal step some nonzero gains and airflow.
    for zone_i in range(state_ref.dynamic.zone_state.shape[0]):
        state_ref.dynamic.zone_state[
            zone_i,
            schema.ZONE_PEOPLE_GAIN_W,
        ] = 80.0 + 10.0 * zone_i
        state_ref.dynamic.zone_state[
            zone_i,
            schema.ZONE_LIGHTING_GAIN_W,
        ] = 30.0
        state_ref.dynamic.zone_state[
            zone_i,
            schema.ZONE_APPLIANCE_GAIN_W,
        ] = 50.0
        state_ref.dynamic.zone_state[
            zone_i,
            schema.ZONE_SOLAR_GAIN_W,
        ] = 100.0
        state_ref.dynamic.zone_state[
            zone_i,
            schema.ZONE_INFILTRATION_AIRFLOW_M3_S,
        ] = 0.01

    state_fast.dynamic.zone_state[:, :] = state_ref.dynamic.zone_state[:, :]
    state_fast.dynamic.system_state[:, :] = state_ref.dynamic.system_state[:, :]
    state_fast.dynamic.weather_state[:] = state_ref.dynamic.weather_state[:]
    state_fast.dynamic.internal_gains[:, :] = state_ref.dynamic.internal_gains[:, :]

    step_building_thermal_semi_implicit(
        zone_state=state_ref.dynamic.zone_state,
        zone_static=state_ref.static.zone_static,
        system_state=state_ref.dynamic.system_state,
        system_static=state_ref.static.system_static,
        weather_state=state_ref.dynamic.weather_state,
        internal_gains=state_ref.dynamic.internal_gains,
        physics_result=state_ref.dynamic.physics_result,
        dt_minutes=60,
        copy_zone_gains=True,
    )

    step_building_thermal_semi_implicit_fast(
        zone_state=state_fast.dynamic.zone_state,
        zone_static=state_fast.static.zone_static,
        system_state=state_fast.dynamic.system_state,
        system_static=state_fast.static.system_static,
        weather_state=state_fast.dynamic.weather_state,
        internal_gains=state_fast.dynamic.internal_gains,
        physics_result=state_fast.dynamic.physics_result,
        dt_minutes=60,
        copy_zone_gains=True,
    )

    temp_ref = state_ref.dynamic.zone_state[
        :,
        schema.ZONE_AIR_TEMPERATURE_C,
    ]
    temp_fast = state_fast.dynamic.zone_state[
        :,
        schema.ZONE_AIR_TEMPERATURE_C,
    ]

    mrt_ref = state_ref.dynamic.zone_state[
        :,
        schema.ZONE_MEAN_RADIANT_TEMPERATURE_C,
    ]
    mrt_fast = state_fast.dynamic.zone_state[
        :,
        schema.ZONE_MEAN_RADIANT_TEMPERATURE_C,
    ]

    physics_ref = state_ref.dynamic.physics_result
    physics_fast = state_fast.dynamic.physics_result

    if not np.allclose(temp_ref, temp_fast, rtol=1.0e-10, atol=1.0e-10):
        print("Air temperature mismatch")
        print("ref:", temp_ref)
        print("fast:", temp_fast)
        print("diff:", temp_fast - temp_ref)
        raise AssertionError("Fast thermal air temperature mismatch.")

    if not np.allclose(mrt_ref, mrt_fast, rtol=1.0e-10, atol=1.0e-10):
        print("MRT/mass temperature mismatch")
        print("ref:", mrt_ref)
        print("fast:", mrt_fast)
        print("diff:", mrt_fast - mrt_ref)
        raise AssertionError("Fast thermal mass temperature mismatch.")

    if not np.allclose(physics_ref, physics_fast, rtol=1.0e-10, atol=1.0e-10):
        print("Physics result mismatch")
        print("max abs diff:", np.max(np.abs(physics_fast - physics_ref)))
        print("ref:")
        print(physics_ref)
        print("fast:")
        print(physics_fast)
        print("diff:")
        print(physics_fast - physics_ref)
        raise AssertionError("Fast thermal physics_result mismatch.")

    print("Fast thermal kernel matches reference.")


if __name__ == "__main__":
    main()