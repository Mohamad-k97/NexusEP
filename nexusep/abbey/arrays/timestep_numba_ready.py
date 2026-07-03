"""
ABBEY numba-prep timestep.

This is not @njit yet.

Purpose:
    Provide one no-None, preallocated-work timestep entrypoint.

Future Phase 18:
    Start applying @njit to smaller called kernels first.
"""

from nexusep.abbey.arrays.person_kernels import (
    update_person_dynamics_numba_ready,
    update_person_perception,
    reset_zone_occupancy_from_person_state,
)

from nexusep.abbey.arrays.action_kernels import (
    score_all_person_actions,
    choose_best_action_indices_from_scores_inplace,
    choose_best_actions_from_scores_inplace,
)

from nexusep.abbey.arrays.execution_kernels import (
    run_execution_step_from_chosen_actions_inplace,
    recompute_occupancy_after_execution,
)

from nexusep.abbey.arrays.daylight_kernels import run_daylight_step
from nexusep.abbey.arrays.airflow_kernels import run_airflow_step
from nexusep.abbey.arrays.thermal_kernels import run_thermal_step
from nexusep.abbey.arrays.co2_kernels import run_co2_step
from nexusep.abbey.arrays.moisture_kernels import run_moisture_step_numba_ready

from nexusep.abbey.arrays.timestep import (
    copy_current_external_inputs,
    run_system_update_if_available,
    add_occupant_internal_gains,
    sync_internal_gains_from_zone_state,
    aggregate_physics_demands_to_dwelling_building,
)


def run_array_timestep_arrays_numba_ready(
    person_state,
    person_static,
    zone_state,
    zone_static,
    dwelling_state,
    dwelling_static,
    building_state,
    building_static,
    system_state,
    system_static,
    process_state,
    action_static,
    action_scores,
    weather_state,
    time_state,
    internal_gains,
    physics_result,
    schedule_array,
    time_index,
    dt_minutes,
    weather_series,
    time_series,
    airflow_link_array,
    chosen_action_indices,
    chosen_action_ids,
    started_actions,
    sleep_pressure_scores,
    humidity_ratio_snapshot,
    electricity_tariff=0.25,
    enforce_work_schedule_flag=1,
):
    """
    Numba-prep raw-array timestep.

    Differences from run_array_timestep_arrays(...):
        - no state dataclass
        - no logs
        - no optional None arrays
        - no allocated chosen/started/sleep work arrays
        - no acoustics for first njit target

    Arrays are mutated in place.
    """
    copy_current_external_inputs(
        weather_state=weather_state,
        time_state=time_state,
        weather_series=weather_series,
        time_series=time_series,
        time_index=time_index,
    )

    update_person_dynamics_numba_ready(
        person_state=person_state,
        person_static=person_static,
        zone_state=zone_state,
        system_state=system_state,
        schedule_array=schedule_array,
        time_state=time_state,
        dt_minutes=dt_minutes,
        sleep_pressure_scores=sleep_pressure_scores,
        enforce_work_schedule_flag=enforce_work_schedule_flag,
    )

    score_all_person_actions(
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

    choose_best_action_indices_from_scores_inplace(
        action_scores=action_scores,
        chosen_action_indices=chosen_action_indices,
    )

    choose_best_actions_from_scores_inplace(
        action_scores=action_scores,
        action_static=action_static,
        chosen_action_ids=chosen_action_ids,
    )

    run_execution_step_from_chosen_actions_inplace(
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

    run_system_update_if_available(
        system_state=system_state,
        system_static=system_static,
        zone_state=zone_state,
        dwelling_state=dwelling_state,
        building_state=building_state,
        internal_gains=internal_gains,
        add_power_totals=True,
        add_lighting_gains=True,
    )

    add_occupant_internal_gains(
        person_state=person_state,
        person_static=person_static,
        zone_state=zone_state,
        dwelling_state=dwelling_state,
        building_state=building_state,
        internal_gains=internal_gains,
    )

    run_daylight_step(
        zone_state=zone_state,
        zone_static=zone_static,
        system_state=system_state,
        system_static=system_static,
        weather_state=weather_state,
        physics_result=physics_result,
        internal_gains=internal_gains,
    )

    sync_internal_gains_from_zone_state(
        zone_state=zone_state,
        internal_gains=internal_gains,
    )

    run_airflow_step(
        zone_state=zone_state,
        zone_static=zone_static,
        system_state=system_state,
        system_static=system_static,
        weather_state=weather_state,
        physics_result=physics_result,
        airflow_link_array=airflow_link_array,
    )

    run_thermal_step(
        zone_state=zone_state,
        zone_static=zone_static,
        system_state=system_state,
        system_static=system_static,
        weather_state=weather_state,
        internal_gains=internal_gains,
        physics_result=physics_result,
        dt_minutes=dt_minutes,
    )

    run_co2_step(
        zone_state=zone_state,
        zone_static=zone_static,
        weather_state=weather_state,
        internal_gains=internal_gains,
        physics_result=physics_result,
        dt_minutes=dt_minutes,
        airflow_link_array=airflow_link_array,
    )

    run_moisture_step_numba_ready(
        zone_state=zone_state,
        zone_static=zone_static,
        weather_state=weather_state,
        internal_gains=internal_gains,
        physics_result=physics_result,
        dt_minutes=dt_minutes,
        airflow_link_array=airflow_link_array,
        humidity_ratio_snapshot=humidity_ratio_snapshot,
    )

    aggregate_physics_demands_to_dwelling_building(
        zone_state=zone_state,
        dwelling_state=dwelling_state,
        building_state=building_state,
        physics_result=physics_result,
    )

    recompute_occupancy_after_execution(
        person_state=person_state,
        zone_state=zone_state,
        dwelling_state=dwelling_state,
        building_state=building_state,
    )

    reset_zone_occupancy_from_person_state(
        person_state=person_state,
        zone_state=zone_state,
    )

    update_person_perception(
        person_state=person_state,
        person_static=person_static,
        zone_state=zone_state,
        system_state=system_state,
        dt_minutes=dt_minutes,
    )

    return True