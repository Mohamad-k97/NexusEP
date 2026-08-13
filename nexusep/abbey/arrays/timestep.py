"""
ABBEY array timestep orchestration.

Phase 12:
    One clean timestep function that runs the array core.

Main public function:
    run_array_timestep(...)

Lower-level raw-array function:
    run_array_timestep_arrays(...)

Order:
    1. read current time/weather
    2. enforce/normalize current system state
    3. update person perception/needs
    4. score candidate actions
    5. choose actions
    6. start/advance/finish foreground/background execution
    7. update system state and system gains
    8. build occupant/internal gains
    9. run daylight
    10. run airflow
    11. run thermal
    12. run CO2
    13. run moisture
    14. run acoustics, if available
    15. update person perception again from new zone state
    16. write logs, if provided

Important:
    - Timestep-facing kernel receives numeric arrays.
    - The state wrapper is only a convenience wrapper.
    - No human-readable objects are used inside run_array_timestep_arrays.
"""

import numpy as np

from nexusep.abbey.arrays import schema

from nexusep.abbey.arrays.person_kernels import (
    make_schedule_array_from_person_static,
    update_person_dynamics,
    update_person_perception,
    reset_zone_occupancy_from_person_state,
)

from nexusep.abbey.arrays.action_kernels import (
    score_all_person_actions,
    choose_best_action_indices_from_scores,
    choose_best_actions_from_scores,
)

from nexusep.abbey.arrays.execution_kernels import (
    run_execution_step_from_chosen_actions,
    recompute_occupancy_after_execution,
)

from nexusep.abbey.arrays.daylight_kernels import (
    run_daylight_step,
)

from nexusep.abbey.arrays.airflow_kernels import (
    run_airflow_step,
)

from nexusep.abbey.arrays.thermal_kernels import (
    run_thermal_step,
)

from nexusep.abbey.arrays.co2_kernels import (
    run_co2_step,
)

from nexusep.abbey.arrays.moisture_kernels import (
    run_moisture_step,
)

from nexusep.abbey.arrays.logger import (
    write_current_state_to_logs,
)


# =============================================================================
# Optional Phase 10 / 11.6 imports
# =============================================================================

try:
    from nexusep.abbey.arrays.system_kernels import (
        add_system_power_to_dwelling_building,
        enforce_system_constraints,
        update_system_control_state,
    )
except ImportError:
    update_system_control_state = None
    enforce_system_constraints = None
    add_system_power_to_dwelling_building = None


try:
    from nexusep.abbey.arrays.acoustic_kernels import (
        run_acoustic_step,
    )
except ImportError:
    run_acoustic_step = None


# =============================================================================
# Small helpers
# =============================================================================

def _series_row_index(series, time_index):
    """
    Return a safe row index for a time series.

    If the series has one row and the simulation has many timesteps, repeat
    the last available row.
    """
    if series is None:
        return schema.MISSING_ID

    if series.shape[0] <= 0:
        return schema.MISSING_ID

    if time_index < 0:
        raise IndexError("time_index cannot be negative.")

    if time_index >= series.shape[0]:
        return series.shape[0] - 1

    return int(time_index)


def copy_current_external_inputs(
    weather_state,
    time_state,
    weather_series,
    time_series,
    time_index,
):
    """
    Copy current weather/time rows into dynamic current-state arrays.

    This lets kernels only read:
        weather_state[col]
        time_state[col]

    instead of reading full series.
    """
    weather_row = _series_row_index(
        series=weather_series,
        time_index=time_index,
    )

    if weather_row != schema.MISSING_ID:
        weather_state[:] = weather_series[weather_row, :]

    time_row = _series_row_index(
        series=time_series,
        time_index=time_index,
    )

    if time_row != schema.MISSING_ID:
        time_state[:] = time_series[time_row, :]

    return True


def clear_current_gain_arrays(
    zone_state,
    dwelling_state,
    building_state,
    internal_gains,
):
    """
    Clear per-timestep gain accumulators.

    execution_kernels.advance_execution_state_arrays also does this, but this
    helper is useful when a timestep has no executable action or when this file
    is later refactored into a chunked timestep.
    """
    zone_state[:, schema.ZONE_INTERNAL_HEAT_GAIN_W] = 0.0
    zone_state[:, schema.ZONE_SOLAR_GAIN_W] = 0.0
    zone_state[:, schema.ZONE_LIGHTING_GAIN_W] = 0.0
    zone_state[:, schema.ZONE_APPLIANCE_GAIN_W] = 0.0
    zone_state[:, schema.ZONE_PEOPLE_GAIN_W] = 0.0
    zone_state[:, schema.ZONE_CO2_GAIN_KG_S] = 0.0
    zone_state[:, schema.ZONE_MOISTURE_GAIN_KG_S] = 0.0

    dwelling_state[:, schema.DWELLING_TOTAL_POWER_W] = 0.0
    dwelling_state[:, schema.DWELLING_TOTAL_HEAT_GAIN_W] = 0.0
    dwelling_state[:, schema.DWELLING_TOTAL_CO2_GAIN_KG_S] = 0.0
    dwelling_state[:, schema.DWELLING_TOTAL_MOISTURE_GAIN_KG_S] = 0.0
    dwelling_state[:, schema.DWELLING_TOTAL_HEATING_DEMAND_W] = 0.0
    dwelling_state[:, schema.DWELLING_TOTAL_COOLING_DEMAND_W] = 0.0
    dwelling_state[:, schema.DWELLING_TOTAL_ELECTRICITY_DEMAND_W] = 0.0

    building_state[:, schema.BUILDING_TOTAL_POWER_W] = 0.0
    building_state[:, schema.BUILDING_TOTAL_HEATING_DEMAND_W] = 0.0
    building_state[:, schema.BUILDING_TOTAL_COOLING_DEMAND_W] = 0.0
    building_state[:, schema.BUILDING_TOTAL_ELECTRICITY_DEMAND_W] = 0.0

    if internal_gains is not None:
        internal_gains[:, :] = 0.0

        for zone_i in range(internal_gains.shape[0]):
            internal_gains[zone_i, schema.GAIN_ZONE_ID] = zone_i

    return True


# =============================================================================
# Internal gains
# =============================================================================

def add_gain_to_zone_dwelling_building(
    zone_state,
    dwelling_state,
    building_state,
    internal_gains,
    zone_id,
    heat_gain_w,
    co2_gain_kg_s,
    moisture_gain_kg_s,
    electric_power_w,
    gain_kind,
):
    """
    Add one source to zone/dwelling/building/internal-gains arrays.

    gain_kind:
        0 = people
        1 = lighting
        2 = appliance
        3 = solar
    """
    zone_id = int(zone_id)

    if zone_id == schema.MISSING_ID:
        return False

    if zone_id < 0 or zone_id >= zone_state.shape[0]:
        return False

    dwelling_id = int(zone_state[zone_id, schema.ZONE_DWELLING_ID])
    building_id = int(zone_state[zone_id, schema.ZONE_BUILDING_ID])

    heat_gain_w = float(heat_gain_w)
    co2_gain_kg_s = float(co2_gain_kg_s)
    moisture_gain_kg_s = float(moisture_gain_kg_s)
    electric_power_w = float(electric_power_w)

    if gain_kind == 0:
        zone_state[zone_id, schema.ZONE_PEOPLE_GAIN_W] += heat_gain_w
        if internal_gains is not None:
            internal_gains[zone_id, schema.GAIN_PEOPLE_HEAT_W] += heat_gain_w

    elif gain_kind == 1:
        zone_state[zone_id, schema.ZONE_LIGHTING_GAIN_W] += heat_gain_w
        if internal_gains is not None:
            internal_gains[zone_id, schema.GAIN_LIGHTING_HEAT_W] += heat_gain_w

    elif gain_kind == 2:
        zone_state[zone_id, schema.ZONE_APPLIANCE_GAIN_W] += heat_gain_w
        if internal_gains is not None:
            internal_gains[zone_id, schema.GAIN_APPLIANCE_HEAT_W] += heat_gain_w

    elif gain_kind == 3:
        zone_state[zone_id, schema.ZONE_SOLAR_GAIN_W] += heat_gain_w
        if internal_gains is not None:
            internal_gains[zone_id, schema.GAIN_SOLAR_HEAT_W] += heat_gain_w

    zone_state[zone_id, schema.ZONE_INTERNAL_HEAT_GAIN_W] += heat_gain_w
    zone_state[zone_id, schema.ZONE_CO2_GAIN_KG_S] += co2_gain_kg_s
    zone_state[zone_id, schema.ZONE_MOISTURE_GAIN_KG_S] += moisture_gain_kg_s

    if internal_gains is not None:
        internal_gains[zone_id, schema.GAIN_ZONE_ID] = zone_id
        internal_gains[zone_id, schema.GAIN_TOTAL_HEAT_W] += heat_gain_w
        internal_gains[zone_id, schema.GAIN_CO2_KG_S] += co2_gain_kg_s
        internal_gains[zone_id, schema.GAIN_MOISTURE_KG_S] += moisture_gain_kg_s
        internal_gains[zone_id, schema.GAIN_ELECTRIC_POWER_W] += electric_power_w

    if dwelling_id != schema.MISSING_ID:
        dwelling_state[dwelling_id, schema.DWELLING_TOTAL_HEAT_GAIN_W] += heat_gain_w
        dwelling_state[dwelling_id, schema.DWELLING_TOTAL_CO2_GAIN_KG_S] += co2_gain_kg_s
        dwelling_state[dwelling_id, schema.DWELLING_TOTAL_MOISTURE_GAIN_KG_S] += moisture_gain_kg_s
        dwelling_state[dwelling_id, schema.DWELLING_TOTAL_POWER_W] += electric_power_w
        dwelling_state[dwelling_id, schema.DWELLING_TOTAL_ELECTRICITY_DEMAND_W] += electric_power_w

    if building_id != schema.MISSING_ID:
        building_state[building_id, schema.BUILDING_TOTAL_POWER_W] += electric_power_w
        building_state[building_id, schema.BUILDING_TOTAL_ELECTRICITY_DEMAND_W] += electric_power_w

    return True


def add_occupant_internal_gains(
    person_state,
    person_static,
    zone_state,
    dwelling_state,
    building_state,
    internal_gains,
):
    """
    Add metabolic heat, CO2, and moisture from people currently at home.

    This is separate from action gains. Even an idle person still produces heat,
    CO2, and moisture.
    """
    for person_i in range(person_state.shape[0]):
        if person_state[person_i, schema.PERSON_IS_HOME] <= 0.0:
            continue

        zone_id = int(person_state[person_i, schema.PERSON_CURRENT_ZONE_ID])

        if zone_id == schema.MISSING_ID:
            continue

        heat_gain_w = person_static[
            person_i,
            schema.PERSON_STATIC_METABOLIC_HEAT_W,
        ]
        co2_gain_kg_s = person_static[
            person_i,
            schema.PERSON_STATIC_CO2_GAIN_KG_S,
        ]
        moisture_gain_kg_s = person_static[
            person_i,
            schema.PERSON_STATIC_MOISTURE_GAIN_KG_S,
        ]

        add_gain_to_zone_dwelling_building(
            zone_state=zone_state,
            dwelling_state=dwelling_state,
            building_state=building_state,
            internal_gains=internal_gains,
            zone_id=zone_id,
            heat_gain_w=heat_gain_w,
            co2_gain_kg_s=co2_gain_kg_s,
            moisture_gain_kg_s=moisture_gain_kg_s,
            electric_power_w=0.0,
            gain_kind=0,
        )

    return True


def sync_internal_gains_from_zone_state(
    zone_state,
    internal_gains,
):
    """
    Make internal_gains consistent with zone_state.

    Use this before physics. It avoids problems when one kernel writes directly
    to zone_state while another reads internal_gains.
    """
    if internal_gains is None:
        return True

    for zone_i in range(zone_state.shape[0]):
        internal_gains[zone_i, schema.GAIN_ZONE_ID] = zone_state[
            zone_i,
            schema.ZONE_ID,
        ]
        internal_gains[zone_i, schema.GAIN_PEOPLE_HEAT_W] = zone_state[
            zone_i,
            schema.ZONE_PEOPLE_GAIN_W,
        ]
        internal_gains[zone_i, schema.GAIN_LIGHTING_HEAT_W] = zone_state[
            zone_i,
            schema.ZONE_LIGHTING_GAIN_W,
        ]
        internal_gains[zone_i, schema.GAIN_APPLIANCE_HEAT_W] = zone_state[
            zone_i,
            schema.ZONE_APPLIANCE_GAIN_W,
        ]
        internal_gains[zone_i, schema.GAIN_SOLAR_HEAT_W] = zone_state[
            zone_i,
            schema.ZONE_SOLAR_GAIN_W,
        ]
        internal_gains[zone_i, schema.GAIN_TOTAL_HEAT_W] = zone_state[
            zone_i,
            schema.ZONE_INTERNAL_HEAT_GAIN_W,
        ]
        internal_gains[zone_i, schema.GAIN_CO2_KG_S] = zone_state[
            zone_i,
            schema.ZONE_CO2_GAIN_KG_S,
        ]
        internal_gains[zone_i, schema.GAIN_MOISTURE_KG_S] = zone_state[
            zone_i,
            schema.ZONE_MOISTURE_GAIN_KG_S,
        ]

    return True


# =============================================================================
# Demand aggregation
# =============================================================================

def aggregate_physics_demands_to_dwelling_building(
    zone_state,
    dwelling_state,
    building_state,
    physics_result,
):
    """
    Aggregate heating/cooling demand from per-zone physics_result to dwelling
    and building state.
    """
    dwelling_state[:, schema.DWELLING_TOTAL_HEATING_DEMAND_W] = 0.0
    dwelling_state[:, schema.DWELLING_TOTAL_COOLING_DEMAND_W] = 0.0

    building_state[:, schema.BUILDING_TOTAL_HEATING_DEMAND_W] = 0.0
    building_state[:, schema.BUILDING_TOTAL_COOLING_DEMAND_W] = 0.0

    for zone_i in range(zone_state.shape[0]):
        dwelling_id = int(zone_state[zone_i, schema.ZONE_DWELLING_ID])
        building_id = int(zone_state[zone_i, schema.ZONE_BUILDING_ID])

        heating = physics_result[zone_i, schema.PHYSICS_HEATING_DEMAND_W]
        cooling = physics_result[zone_i, schema.PHYSICS_COOLING_DEMAND_W]

        if dwelling_id != schema.MISSING_ID:
            dwelling_state[
                dwelling_id,
                schema.DWELLING_TOTAL_HEATING_DEMAND_W,
            ] += heating
            dwelling_state[
                dwelling_id,
                schema.DWELLING_TOTAL_COOLING_DEMAND_W,
            ] += cooling

        if building_id != schema.MISSING_ID:
            building_state[
                building_id,
                schema.BUILDING_TOTAL_HEATING_DEMAND_W,
            ] += heating
            building_state[
                building_id,
                schema.BUILDING_TOTAL_COOLING_DEMAND_W,
            ] += cooling

    return True


# =============================================================================
# Optional system update wrapper
# =============================================================================

def run_system_update_if_available(
    system_state,
    system_static,
    zone_state,
    dwelling_state,
    building_state,
    internal_gains,
    add_power_totals=True,
    add_lighting_gains=True,
    prescribed_heating_power_by_system_w=None,
    prescribed_cooling_power_by_system_w=None,
):
    """
    Use Phase 10 system_kernels if available.

    If system_kernels.py is not present yet, this becomes a no-op. Phase 9
    execution_kernels still applies basic immediate control effects.
    """
    if update_system_control_state is None:
        return False

    update_system_control_state(
        system_state=system_state,
        system_static=system_static,
        zone_state=zone_state,
        dwelling_state=dwelling_state,
        building_state=building_state,
        internal_gains=internal_gains,
        add_power_totals=False,
        add_lighting_gains=add_lighting_gains,
    )

    prescribed_pairs = (
        (
            prescribed_heating_power_by_system_w,
            schema.SYSTEM_HEATING_POWER_W,
            "prescribed_heating_power_by_system_w",
        ),
        (
            prescribed_cooling_power_by_system_w,
            schema.SYSTEM_COOLING_POWER_W,
            "prescribed_cooling_power_by_system_w",
        ),
    )
    for values, column, label in prescribed_pairs:
        if values is None:
            continue
        if len(values) != system_state.shape[0]:
            raise ValueError(label + " must have one value per system")
        for system_i, value in enumerate(values):
            power_w = float(value)
            if not np.isfinite(power_w) or power_w < 0.0:
                raise ValueError(label + " must be finite and non-negative")
            system_state[system_i, column] = power_w

    if add_power_totals:
        if add_system_power_to_dwelling_building is None:
            raise RuntimeError("system power aggregation is unavailable")
        add_system_power_to_dwelling_building(
            system_state=system_state,
            zone_state=zone_state,
            dwelling_state=dwelling_state,
            building_state=building_state,
        )

    return True


def enforce_system_constraints_if_available(
    system_state,
    system_static,
    zone_state,
):
    """
    Normalize system states before decisions/physics if Phase 10 exists.
    """
    if enforce_system_constraints is None:
        return False

    enforce_system_constraints(
        system_state=system_state,
        system_static=system_static,
        zone_state=zone_state,
    )

    return True


# =============================================================================
# Raw array timestep
# =============================================================================

def run_array_timestep_arrays(
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
    weather_series=None,
    time_series=None,
    airflow_link_array=None,
    acoustic_link_array=None,
    zone_noise_source_array=None,
    outdoor_noise_db=None,
    electricity_tariff=0.25,
    enforce_work_schedule=True,
    run_acoustics=True,
    refresh_perception_after_physics=False,
    prescribed_solar_gain_by_zone_w=None,
    prescribed_heating_power_by_system_w=None,
    prescribed_cooling_power_by_system_w=None,
):
    """
    Run one complete ABBEY array timestep.

    This is the numeric-array core.

    Arrays are mutated in place.

    Returns:
        chosen_action_indices
        chosen_action_ids
        started_actions
    """
    # -------------------------------------------------------------------------
    # 1. Read current external inputs.
    # -------------------------------------------------------------------------

    copy_current_external_inputs(
        weather_state=weather_state,
        time_state=time_state,
        weather_series=weather_series,
        time_series=time_series,
        time_index=time_index,
    )
    clear_timestep_accumulators(
        person_state=person_state,
        zone_state=zone_state,
        internal_gains=internal_gains,
        physics_result=physics_result,
    )
    # -------------------------------------------------------------------------
    # 2. Normalize current system states before perception/action scoring.
    # -------------------------------------------------------------------------

    enforce_system_constraints_if_available(
        system_state=system_state,
        system_static=system_static,
        zone_state=zone_state,
    )

    # -------------------------------------------------------------------------
    # 3. Update person perception, health, needs, home/away, occupancy.
    # -------------------------------------------------------------------------

    person_state, zone_state, sleep_pressure_scores = update_person_dynamics(
        person_state=person_state,
        person_static=person_static,
        zone_state=zone_state,
        system_state=system_state,
        schedule_array=schedule_array,
        time_state=time_state,
        dt_minutes=dt_minutes,
        sleep_pressure_scores=None,
        enforce_work_schedule=enforce_work_schedule,
    )
    sanitize_person_state_values(person_state)
    # -------------------------------------------------------------------------
    # 4. Score candidate actions.
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # 5. Select deterministic best action.
    # -------------------------------------------------------------------------

    chosen_action_indices = choose_best_action_indices_from_scores(
        action_scores=action_scores,
    )

    chosen_action_ids = choose_best_actions_from_scores(
        action_scores=action_scores,
        action_static=action_static,
    )

    # -------------------------------------------------------------------------
    # 6. Start/advance/finish foreground and background actions.
    #
    # This clears current gain accumulators internally, then writes action and
    # process power/gains.
    # -------------------------------------------------------------------------

    started_actions = run_execution_step_from_chosen_actions(
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
        dt_minutes=dt_minutes,
        internal_gains=internal_gains,
    )

    # -------------------------------------------------------------------------
    # 7. Normalize/apply system state and system gains.
    #
    # This should happen after execution because execution may change window,
    # HVAC, light, blind, and ventilation states.
    # -------------------------------------------------------------------------

    run_system_update_if_available(
        system_state=system_state,
        system_static=system_static,
        zone_state=zone_state,
        dwelling_state=dwelling_state,
        building_state=building_state,
        internal_gains=internal_gains,
        add_power_totals=True,
        add_lighting_gains=True,
        prescribed_heating_power_by_system_w=(
            prescribed_heating_power_by_system_w
        ),
        prescribed_cooling_power_by_system_w=(
            prescribed_cooling_power_by_system_w
        ),
    )

    # -------------------------------------------------------------------------
    # 8. Add occupant metabolic gains.
    # -------------------------------------------------------------------------

    add_occupant_internal_gains(
        person_state=person_state,
        person_static=person_static,
        zone_state=zone_state,
        dwelling_state=dwelling_state,
        building_state=building_state,
        internal_gains=internal_gains,
    )

    # -------------------------------------------------------------------------
    # 9. Daylight and solar gains.
    # -------------------------------------------------------------------------

    run_daylight_step(
        zone_state=zone_state,
        zone_static=zone_static,
        system_state=system_state,
        system_static=system_static,
        weather_state=weather_state,
        physics_result=physics_result,
        internal_gains=internal_gains,
    )

    if prescribed_solar_gain_by_zone_w is not None:
        if len(prescribed_solar_gain_by_zone_w) != zone_state.shape[0]:
            raise ValueError(
                "prescribed_solar_gain_by_zone_w must have one value per zone"
            )
        for zone_i in range(zone_state.shape[0]):
            solar_gain_w = float(prescribed_solar_gain_by_zone_w[zone_i])
            if not np.isfinite(solar_gain_w) or solar_gain_w < 0.0:
                raise ValueError(
                    "prescribed_solar_gain_by_zone_w must be finite and non-negative"
                )
            zone_state[zone_i, schema.ZONE_SOLAR_GAIN_W] = solar_gain_w
            zone_state[zone_i, schema.ZONE_INTERNAL_HEAT_GAIN_W] = (
                zone_state[zone_i, schema.ZONE_PEOPLE_GAIN_W]
                + zone_state[zone_i, schema.ZONE_LIGHTING_GAIN_W]
                + zone_state[zone_i, schema.ZONE_APPLIANCE_GAIN_W]
                + solar_gain_w
            )

    sync_internal_gains_from_zone_state(
        zone_state=zone_state,
        internal_gains=internal_gains,
    )

    # -------------------------------------------------------------------------
    # 10. Airflow.
    # -------------------------------------------------------------------------

    run_airflow_step(
        zone_state=zone_state,
        zone_static=zone_static,
        system_state=system_state,
        system_static=system_static,
        weather_state=weather_state,
        physics_result=physics_result,
        airflow_link_array=airflow_link_array,
    )

    # -------------------------------------------------------------------------
    # 11. Thermal physics.
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # 12. CO2 physics.
    # -------------------------------------------------------------------------

    run_co2_step(
        zone_state=zone_state,
        zone_static=zone_static,
        weather_state=weather_state,
        internal_gains=internal_gains,
        physics_result=physics_result,
        dt_minutes=dt_minutes,
        airflow_link_array=airflow_link_array,
    )

    # -------------------------------------------------------------------------
    # 13. Moisture physics.
    # -------------------------------------------------------------------------

    run_moisture_step(
        zone_state=zone_state,
        zone_static=zone_static,
        weather_state=weather_state,
        internal_gains=internal_gains,
        physics_result=physics_result,
        dt_minutes=dt_minutes,
        airflow_link_array=airflow_link_array,
    )

    # -------------------------------------------------------------------------
    # 14. Acoustic physics, if Phase 11.6 exists.
    # -------------------------------------------------------------------------

    if run_acoustics and run_acoustic_step is not None:
        run_acoustic_step(
            zone_state=zone_state,
            zone_static=zone_static,
            system_state=system_state,
            system_static=system_static,
            weather_state=weather_state,
            person_state=person_state,
            process_state=process_state,
            action_static=action_static,
            physics_result=physics_result,
            zone_noise_source_array=zone_noise_source_array,
            acoustic_link_array=acoustic_link_array,
            outdoor_noise_db=outdoor_noise_db,
        )

    # -------------------------------------------------------------------------
    # 15. Aggregate physics demand to dwelling/building.
    # -------------------------------------------------------------------------

    aggregate_physics_demands_to_dwelling_building(
        zone_state=zone_state,
        dwelling_state=dwelling_state,
        building_state=building_state,
        physics_result=physics_result,
    )

    # -------------------------------------------------------------------------
    # 16. Refresh occupancy and perception from the newly updated zone states.
    #
    # Needs are not updated again here. Only perception is refreshed so logs at
    # the end of the timestep correspond to current zone conditions.
    # -------------------------------------------------------------------------

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
    if refresh_perception_after_physics:
        update_person_perception(
            person_state=person_state,
            person_static=person_static,
            zone_state=zone_state,
            system_state=system_state,
            dt_minutes=dt_minutes,
        )
        sanitize_person_state_values(person_state)
    return chosen_action_indices, chosen_action_ids, started_actions


# =============================================================================
# State-wrapper timestep
# =============================================================================

def get_schedule_array_for_state(state, schedule_array=None):
    """
    Resolve person schedule array.

    Preference:
        explicit schedule_array argument
        state.metadata["person_schedule_array"]
        generated from person_static
    """
    if schedule_array is not None:
        return schedule_array

    if state.metadata is not None:
        if "person_schedule_array" in state.metadata:
            return state.metadata["person_schedule_array"]

    return make_schedule_array_from_person_static(
        state.static.person_static
    )


def get_dt_minutes_for_state(state, dt_minutes=None):
    """
    Resolve dt_minutes.
    """
    if dt_minutes is not None:
        return float(dt_minutes)

    if state.metadata is not None:
        if "dt_minutes" in state.metadata:
            return float(state.metadata["dt_minutes"])

    return 15.0


def run_array_timestep(
    state,
    time_index,
    dt_minutes=None,
    logs=None,
    schedule_array=None,
    airflow_link_array=None,
    acoustic_link_array=None,
    zone_noise_source_array=None,
    outdoor_noise_db=None,
    electricity_tariff=0.25,
    enforce_work_schedule=True,
    run_acoustics=True,
    refresh_perception_after_physics = False,
    prescribed_solar_gain_by_zone_w=None,
    prescribed_heating_power_by_system_w=None,
    prescribed_cooling_power_by_system_w=None,
):
    """
    Run one complete timestep using a SimulationArrayState.

    This wrapper exists for usability. The numerical work is delegated to
    run_array_timestep_arrays(...).

    Mutates:
        state.dynamic.*
        logs, if provided

    Returns:
        state,
        chosen_action_indices,
        chosen_action_ids,
        started_actions
    """
    dt_minutes = get_dt_minutes_for_state(
        state=state,
        dt_minutes=dt_minutes,
    )

    schedule_array = get_schedule_array_for_state(
        state=state,
        schedule_array=schedule_array,
    )

    weather_series = None
    time_series = None

    if state.series is not None:
        weather_series = state.series.weather_series
        time_series = state.series.time_series

    chosen_action_indices, chosen_action_ids, started_actions = run_array_timestep_arrays(
        person_state=state.dynamic.person_state,
        person_static=state.static.person_static,
        zone_state=state.dynamic.zone_state,
        zone_static=state.static.zone_static,
        dwelling_state=state.dynamic.dwelling_state,
        dwelling_static=state.static.dwelling_static,
        building_state=state.dynamic.building_state,
        building_static=state.static.building_static,
        system_state=state.dynamic.system_state,
        system_static=state.static.system_static,
        process_state=state.dynamic.process_state,
        action_static=state.static.action_static,
        action_scores=state.dynamic.action_scores,
        weather_state=state.dynamic.weather_state,
        time_state=state.dynamic.time_state,
        internal_gains=state.dynamic.internal_gains,
        physics_result=state.dynamic.physics_result,
        schedule_array=schedule_array,
        time_index=time_index,
        dt_minutes=dt_minutes,
        weather_series=weather_series,
        time_series=time_series,
        airflow_link_array=airflow_link_array,
        acoustic_link_array=acoustic_link_array,
        zone_noise_source_array=zone_noise_source_array,
        outdoor_noise_db=outdoor_noise_db,
        electricity_tariff=electricity_tariff,
        enforce_work_schedule=enforce_work_schedule,
        run_acoustics=run_acoustics,
        refresh_perception_after_physics=refresh_perception_after_physics,
        prescribed_solar_gain_by_zone_w=prescribed_solar_gain_by_zone_w,
        prescribed_heating_power_by_system_w=(
            prescribed_heating_power_by_system_w
        ),
        prescribed_cooling_power_by_system_w=(
            prescribed_cooling_power_by_system_w
        ),
        
    )

    if logs is not None:
        write_current_state_to_logs(
            state=state,
            logs=logs,
            time_index=time_index,
        )

    return state, chosen_action_indices, chosen_action_ids, started_actions


# =============================================================================
# Simple multi-timestep helper
# =============================================================================

def run_array_timesteps(
    state,
    n_timesteps=None,
    dt_minutes=None,
    logs=None,
    schedule_array=None,
    airflow_link_array=None,
    acoustic_link_array=None,
    zone_noise_source_array=None,
    outdoor_noise_db=None,
    electricity_tariff=0.25,
    enforce_work_schedule=True,
    run_acoustics=True,
):
    """
    Convenience loop around run_array_timestep(...).

    This is not a full runner class. It is just useful for tests and scratch runs.
    """
    if n_timesteps is None:
        if state.series is not None and state.series.time_series is not None:
            n_timesteps = state.series.time_series.shape[0]
        elif state.series is not None and state.series.weather_series is not None:
            n_timesteps = state.series.weather_series.shape[0]
        elif state.metadata is not None and "n_timesteps" in state.metadata:
            n_timesteps = int(state.metadata["n_timesteps"])
        else:
            n_timesteps = 1

    last_chosen_action_indices = None
    last_chosen_action_ids = None
    last_started_actions = None

    for time_index in range(int(n_timesteps)):
        (
            state,
            last_chosen_action_indices,
            last_chosen_action_ids,
            last_started_actions,
        ) = run_array_timestep(
            state=state,
            time_index=time_index,
            dt_minutes=dt_minutes,
            logs=logs,
            schedule_array=schedule_array,
            airflow_link_array=airflow_link_array,
            acoustic_link_array=acoustic_link_array,
            zone_noise_source_array=zone_noise_source_array,
            outdoor_noise_db=outdoor_noise_db,
            electricity_tariff=electricity_tariff,
            enforce_work_schedule=enforce_work_schedule,
            run_acoustics=run_acoustics,
        )

    return state, last_chosen_action_indices, last_chosen_action_ids, last_started_actions


def _finite_or_zero(value):
    if value != value:
        return 0.0

    if value == float("inf"):
        return 0.0

    if value == -float("inf"):
        return 0.0

    return value


def _clip01_safe(value):
    value = _finite_or_zero(value)

    if value < 0.0:
        return 0.0

    if value > 1.0:
        return 1.0

    return value


def clear_timestep_accumulators(
    person_state,
    zone_state,
    internal_gains,
    physics_result,
):
    """
    Clear transient timestep accumulators.

    These values are not physical state memories. They must be rebuilt every
    timestep from occupants, actions, systems, daylight, airflow, and physics.

    If they are not cleared, heat/CO2/moisture/power can accumulate forever,
    causing temperature blow-up and eventually NaNs.
    """

    # -------------------------------------------------------------------------
    # Person instantaneous outputs.
    # Do not clear current action/type/time-left here.
    # Only clear current per-timestep emission/power terms.
    # -------------------------------------------------------------------------

    for person_i in range(person_state.shape[0]):
        person_state[person_i, schema.PERSON_CURRENT_POWER_W] = 0.0
        person_state[person_i, schema.PERSON_CURRENT_HEAT_GAIN_W] = 0.0
        person_state[person_i, schema.PERSON_CURRENT_CO2_GAIN_KG_S] = 0.0
        person_state[person_i, schema.PERSON_CURRENT_MOISTURE_GAIN_KG_S] = 0.0

    # -------------------------------------------------------------------------
    # Zone transient gains and flows.
    # -------------------------------------------------------------------------

    for zone_i in range(zone_state.shape[0]):
        zone_state[zone_i, schema.ZONE_INTERNAL_HEAT_GAIN_W] = 0.0
        zone_state[zone_i, schema.ZONE_SOLAR_GAIN_W] = 0.0
        zone_state[zone_i, schema.ZONE_LIGHTING_GAIN_W] = 0.0
        zone_state[zone_i, schema.ZONE_APPLIANCE_GAIN_W] = 0.0
        zone_state[zone_i, schema.ZONE_PEOPLE_GAIN_W] = 0.0

        zone_state[zone_i, schema.ZONE_CO2_GAIN_KG_S] = 0.0
        zone_state[zone_i, schema.ZONE_MOISTURE_GAIN_KG_S] = 0.0

        zone_state[zone_i, schema.ZONE_OUTDOOR_AIRFLOW_M3_S] = 0.0
        zone_state[zone_i, schema.ZONE_INTERZONE_AIRFLOW_M3_S] = 0.0
        zone_state[zone_i, schema.ZONE_INFILTRATION_AIRFLOW_M3_S] = 0.0

    # -------------------------------------------------------------------------
    # Internal gain table.
    # -------------------------------------------------------------------------

    for zone_i in range(internal_gains.shape[0]):
        for col_i in range(internal_gains.shape[1]):
            internal_gains[zone_i, col_i] = 0.0

        internal_gains[zone_i, schema.GAIN_ZONE_ID] = zone_i

    # -------------------------------------------------------------------------
    # Physics result table.
    # Keep zone ID, clear outputs.
    # -------------------------------------------------------------------------

    for zone_i in range(physics_result.shape[0]):
        for col_i in range(physics_result.shape[1]):
            physics_result[zone_i, col_i] = 0.0

        physics_result[zone_i, schema.PHYSICS_ZONE_ID] = zone_state[
            zone_i,
            schema.ZONE_ID,
        ]

    return True


def sanitize_person_state_values(person_state):
    """
    Keep bounded person state variables finite.

    Inlined version: avoids many tiny helper calls.
    """

    cols = (
        schema.PERSON_HUNGER,
        schema.PERSON_FATIGUE,
        schema.PERSON_DIRTY_CLOTHES,
        schema.PERSON_SICKNESS,
        schema.PERSON_LAZINESS,
        schema.PERSON_THERMAL_STRESS,
        schema.PERSON_AIR_QUALITY_STRESS,
        schema.PERSON_VISUAL_STRESS,
        schema.PERSON_ACOUSTIC_STRESS,
        schema.PERSON_TOTAL_DISCOMFORT,
    )

    for person_i in range(person_state.shape[0]):
        for col in cols:
            value = person_state[person_i, col]

            if value != value:
                value = 0.0
            elif value == float("inf"):
                value = 1.0
            elif value == -float("inf"):
                value = 0.0

            if value < 0.0:
                value = 0.0
            elif value > 1.0:
                value = 1.0

            person_state[person_i, col] = value

    return True
