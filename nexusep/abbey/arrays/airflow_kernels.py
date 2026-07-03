"""
ABBEY array airflow kernels.

Phase 11.2:
    Move simplified airflow calculation into numeric arrays.

This module calculates:
    - infiltration airflow
    - mechanical ventilation airflow
    - window-driven outdoor airflow
    - simple interzone mixing airflow
    - total ventilation/exchange flow per zone

It writes to:
    zone_state[:, ZONE_OUTDOOR_AIRFLOW_M3_S]
    zone_state[:, ZONE_INFILTRATION_AIRFLOW_M3_S]
    zone_state[:, ZONE_INTERZONE_AIRFLOW_M3_S]
    physics_result[:, PHYSICS_VENTILATION_FLOW_M3_S]

Important:
    - No zone objects.
    - No airflow dataclasses.
    - No graph objects.
    - No dicts in timestep-facing functions.
    - No strings.
    - Numeric arrays only.

Notes:
    The old object airflow model had richer record objects and graph links.
    This Phase 11.2 version gives the array core a clean first airflow layer.
"""

import math

import numpy as np

from nexusep.abbey.arrays import schema


# =============================================================================
# Constants
# =============================================================================

SECONDS_PER_HOUR = 3600.0

DEFAULT_INFILTRATION_ACH = 0.20
DEFAULT_MAX_WINDOW_AIRFLOW_M3_S = 0.20
DEFAULT_WINDOW_WIND_REFERENCE_SPEED_M_S = 4.0
DEFAULT_WINDOW_MIN_WIND_FACTOR = 0.20
DEFAULT_WINDOW_MAX_WIND_FACTOR = 1.50

DEFAULT_INTERZONE_BASE_FLOW_M3_S = 0.0
DEFAULT_INTERZONE_MAX_FLOW_M3_S = 0.05

# Optional interzone link array columns.
#
# airflow_link_array[link_i, AIRFLOW_LINK_*]
#
# The link is treated as symmetric mixing:
#     zone_a receives flow from zone_b
#     zone_b receives flow from zone_a
#
AIRFLOW_LINK_ZONE_A_ID = 0
AIRFLOW_LINK_ZONE_B_ID = 1
AIRFLOW_LINK_BASE_FLOW_M3_S = 2
AIRFLOW_LINK_OPEN_FRACTION = 3
AIRFLOW_LINK_MAX_FLOW_M3_S = 4
AIRFLOW_LINK_CURRENT_FLOW_M3_S = 5
N_AIRFLOW_LINK_COLS = 6


# =============================================================================
# Small helpers
# =============================================================================

def _non_negative(value):
    value = float(value)

    if value < 0.0:
        return 0.0

    return value


def _clip(value, minimum, maximum):
    value = float(value)

    if value < minimum:
        return float(minimum)

    if value > maximum:
        return float(maximum)

    return value


def _clip01(value):
    return _clip(value, 0.0, 1.0)


def _zone_is_outside(zone_state, zone_i):
    return int(zone_state[zone_i, schema.ZONE_TYPE]) == schema.ZONE_TYPE_OUTSIDE


def _zone_volume_m3(zone_static, zone_i):
    volume = zone_static[zone_i, schema.ZONE_STATIC_VOLUME_M3]

    if volume > 0.0:
        return volume

    area = zone_static[zone_i, schema.ZONE_STATIC_FLOOR_AREA_M2]
    height = zone_static[zone_i, schema.ZONE_STATIC_HEIGHT_M]

    if height <= 0.0:
        height = 2.7

    volume = area * height

    if volume <= 0.0:
        volume = 50.0

    return volume


def airflow_ach_to_m3_s(ach, volume_m3):
    """
    Convert air changes per hour to m3/s.

        flow = ACH * volume / 3600
    """
    return _non_negative(ach) * _non_negative(volume_m3) / SECONDS_PER_HOUR


def airflow_m3_s_to_ach(flow_m3_s, volume_m3):
    """
    Convert m3/s to ACH.
    """
    volume_m3 = _non_negative(volume_m3)

    if volume_m3 <= 0.0:
        return 0.0

    return _non_negative(flow_m3_s) * SECONDS_PER_HOUR / volume_m3


# =============================================================================
# Infiltration
# =============================================================================

def calculate_infiltration_flow_for_zone_m3_s(
    zone_static,
    zone_i,
    infiltration_ach=DEFAULT_INFILTRATION_ACH,
):
    """
    Calculate simple infiltration flow from ACH.

    In this first array version, infiltration is not pressure-driven.
    """
    volume_m3 = _zone_volume_m3(
        zone_static=zone_static,
        zone_i=zone_i,
    )

    return airflow_ach_to_m3_s(
        ach=infiltration_ach,
        volume_m3=volume_m3,
    )


def calculate_all_infiltration_flows_m3_s(
    zone_state,
    zone_static,
    out_infiltration_flows=None,
    infiltration_ach=DEFAULT_INFILTRATION_ACH,
):
    """
    Calculate infiltration flow for every zone.
    """
    n_zones = zone_state.shape[0]

    if out_infiltration_flows is None:
        out_infiltration_flows = np.zeros((n_zones,), dtype=np.float64)

    for zone_i in range(n_zones):
        if _zone_is_outside(zone_state, zone_i):
            out_infiltration_flows[zone_i] = 0.0
            continue

        out_infiltration_flows[zone_i] = calculate_infiltration_flow_for_zone_m3_s(
            zone_static=zone_static,
            zone_i=zone_i,
            infiltration_ach=infiltration_ach,
        )

    return out_infiltration_flows


# =============================================================================
# Mechanical ventilation
# =============================================================================

def calculate_mechanical_ventilation_flow_for_zone_m3_s(
    system_state,
    zone_i,
):
    """
    Sum mechanical ventilation flow serving one zone.
    """
    total = 0.0

    for system_i in range(system_state.shape[0]):
        system_zone_id = int(system_state[system_i, schema.SYSTEM_ZONE_ID])

        if system_zone_id != int(zone_i):
            continue

        mode = int(system_state[system_i, schema.SYSTEM_VENTILATION_MODE])

        if (
            mode == schema.VENTILATION_MODE_MECHANICAL
            or mode == schema.VENTILATION_MODE_HYBRID
        ):
            total += _non_negative(
                system_state[
                    system_i,
                    schema.SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S,
                ]
            )

    return total


def calculate_all_mechanical_ventilation_flows_m3_s(
    zone_state,
    system_state,
    out_mechanical_flows=None,
):
    """
    Calculate mechanical ventilation flow for every zone.
    """
    n_zones = zone_state.shape[0]

    if out_mechanical_flows is None:
        out_mechanical_flows = np.zeros((n_zones,), dtype=np.float64)

    for zone_i in range(n_zones):
        if _zone_is_outside(zone_state, zone_i):
            out_mechanical_flows[zone_i] = 0.0
            continue

        out_mechanical_flows[zone_i] = calculate_mechanical_ventilation_flow_for_zone_m3_s(
            system_state=system_state,
            zone_i=zone_i,
        )

    return out_mechanical_flows


# =============================================================================
# Window airflow
# =============================================================================

def calculate_window_wind_factor(
    weather_state,
    wind_reference_speed_m_s=DEFAULT_WINDOW_WIND_REFERENCE_SPEED_M_S,
    min_factor=DEFAULT_WINDOW_MIN_WIND_FACTOR,
    max_factor=DEFAULT_WINDOW_MAX_WIND_FACTOR,
):
    """
    Convert wind speed to a simple multiplier.

    factor = wind_speed / reference_speed

    Clipped to avoid zero flow in calm weather and silly flow in high wind.
    """
    wind_speed = weather_state[schema.WEATHER_WIND_SPEED_M_S]

    if wind_reference_speed_m_s <= 0.0:
        return 1.0

    factor = wind_speed / wind_reference_speed_m_s

    return _clip(
        factor,
        min_factor,
        max_factor,
    )


def calculate_window_airflow_for_system_m3_s(
    system_state,
    system_static,
    weather_state,
    system_i,
):
    """
    Calculate simple outdoor airflow through one system's window.
    """
    has_window = system_static[system_i, schema.SYSTEM_STATIC_HAS_WINDOW] > 0.0

    if not has_window:
        return 0.0

    open_fraction = system_state[
        system_i,
        schema.SYSTEM_WINDOW_OPEN_FRACTION,
    ]

    open_fraction = _clip01(open_fraction)

    if open_fraction <= 0.0:
        return 0.0

    max_flow = system_static[
        system_i,
        schema.SYSTEM_STATIC_MAX_WINDOW_FLOW_M3_S,
    ]

    if max_flow <= 0.0:
        max_flow = DEFAULT_MAX_WINDOW_AIRFLOW_M3_S

    wind_factor = calculate_window_wind_factor(
        weather_state=weather_state,
    )

    return open_fraction * max_flow * wind_factor


def calculate_window_airflow_for_zone_m3_s(
    system_state,
    system_static,
    weather_state,
    zone_i,
):
    """
    Sum simple window airflow for all systems serving one zone.
    """
    total = 0.0

    for system_i in range(system_state.shape[0]):
        system_zone_id = int(system_state[system_i, schema.SYSTEM_ZONE_ID])

        if system_zone_id != int(zone_i):
            continue

        total += calculate_window_airflow_for_system_m3_s(
            system_state=system_state,
            system_static=system_static,
            weather_state=weather_state,
            system_i=system_i,
        )

    return total


def calculate_all_window_airflows_m3_s(
    zone_state,
    system_state,
    system_static,
    weather_state,
    out_window_flows=None,
):
    """
    Calculate window airflow for every zone.
    """
    n_zones = zone_state.shape[0]

    if out_window_flows is None:
        out_window_flows = np.zeros((n_zones,), dtype=np.float64)

    for zone_i in range(n_zones):
        if _zone_is_outside(zone_state, zone_i):
            out_window_flows[zone_i] = 0.0
            continue

        out_window_flows[zone_i] = calculate_window_airflow_for_zone_m3_s(
            system_state=system_state,
            system_static=system_static,
            weather_state=weather_state,
            zone_i=zone_i,
        )

    return out_window_flows


# =============================================================================
# Interzone airflow links
# =============================================================================

def make_empty_airflow_link_array(n_links):
    """
    Allocate an optional interzone airflow-link array.
    """
    return np.zeros((n_links, N_AIRFLOW_LINK_COLS), dtype=np.float64)


def make_single_airflow_link(
    zone_a_id,
    zone_b_id,
    base_flow_m3_s=DEFAULT_INTERZONE_BASE_FLOW_M3_S,
    open_fraction=1.0,
    max_flow_m3_s=DEFAULT_INTERZONE_MAX_FLOW_M3_S,
):
    """
    Create one interzone airflow link row.

    Returns:
        shape [N_AIRFLOW_LINK_COLS]
    """
    row = np.zeros((N_AIRFLOW_LINK_COLS,), dtype=np.float64)

    row[AIRFLOW_LINK_ZONE_A_ID] = int(zone_a_id)
    row[AIRFLOW_LINK_ZONE_B_ID] = int(zone_b_id)
    row[AIRFLOW_LINK_BASE_FLOW_M3_S] = _non_negative(base_flow_m3_s)
    row[AIRFLOW_LINK_OPEN_FRACTION] = _clip01(open_fraction)
    row[AIRFLOW_LINK_MAX_FLOW_M3_S] = _non_negative(max_flow_m3_s)
    row[AIRFLOW_LINK_CURRENT_FLOW_M3_S] = 0.0

    return row


def calculate_interzone_link_flow_m3_s(airflow_link_array, link_i):
    """
    Calculate symmetric interzone mixing flow for one link.
    """
    base_flow = _non_negative(
        airflow_link_array[link_i, AIRFLOW_LINK_BASE_FLOW_M3_S]
    )
    open_fraction = _clip01(
        airflow_link_array[link_i, AIRFLOW_LINK_OPEN_FRACTION]
    )
    max_flow = _non_negative(
        airflow_link_array[link_i, AIRFLOW_LINK_MAX_FLOW_M3_S]
    )

    return base_flow + open_fraction * max_flow


def calculate_all_interzone_flows_m3_s(
    zone_state,
    airflow_link_array=None,
    out_interzone_flows=None,
):
    """
    Calculate total interzone mixing airflow per zone.

    The flow is symmetric:
        flow from A to B counts in A's total interzone exchange
        and in B's total interzone exchange.
    """
    n_zones = zone_state.shape[0]

    if out_interzone_flows is None:
        out_interzone_flows = np.zeros((n_zones,), dtype=np.float64)

    out_interzone_flows[:] = 0.0

    if airflow_link_array is None:
        return out_interzone_flows

    for link_i in range(airflow_link_array.shape[0]):
        zone_a = int(airflow_link_array[link_i, AIRFLOW_LINK_ZONE_A_ID])
        zone_b = int(airflow_link_array[link_i, AIRFLOW_LINK_ZONE_B_ID])

        if zone_a == schema.MISSING_ID or zone_b == schema.MISSING_ID:
            airflow_link_array[link_i, AIRFLOW_LINK_CURRENT_FLOW_M3_S] = 0.0
            continue

        if zone_a < 0 or zone_a >= n_zones:
            airflow_link_array[link_i, AIRFLOW_LINK_CURRENT_FLOW_M3_S] = 0.0
            continue

        if zone_b < 0 or zone_b >= n_zones:
            airflow_link_array[link_i, AIRFLOW_LINK_CURRENT_FLOW_M3_S] = 0.0
            continue

        if _zone_is_outside(zone_state, zone_a) or _zone_is_outside(zone_state, zone_b):
            airflow_link_array[link_i, AIRFLOW_LINK_CURRENT_FLOW_M3_S] = 0.0
            continue

        flow = calculate_interzone_link_flow_m3_s(
            airflow_link_array=airflow_link_array,
            link_i=link_i,
        )

        airflow_link_array[link_i, AIRFLOW_LINK_CURRENT_FLOW_M3_S] = flow

        out_interzone_flows[zone_a] += flow
        out_interzone_flows[zone_b] += flow

    return out_interzone_flows


# =============================================================================
# Main airflow calculation
# =============================================================================

def calculate_zone_airflow_components_m3_s(
    zone_state,
    zone_static,
    system_state,
    system_static,
    weather_state,
    zone_i,
    infiltration_ach=DEFAULT_INFILTRATION_ACH,
):
    """
    Calculate airflow components for one zone.

    Returns:
        infiltration_flow_m3_s,
        mechanical_flow_m3_s,
        window_flow_m3_s,
        outdoor_flow_m3_s
    """
    if _zone_is_outside(zone_state, zone_i):
        return 0.0, 0.0, 0.0, 0.0

    infiltration_flow = calculate_infiltration_flow_for_zone_m3_s(
        zone_static=zone_static,
        zone_i=zone_i,
        infiltration_ach=infiltration_ach,
    )

    mechanical_flow = calculate_mechanical_ventilation_flow_for_zone_m3_s(
        system_state=system_state,
        zone_i=zone_i,
    )

    window_flow = calculate_window_airflow_for_zone_m3_s(
        system_state=system_state,
        system_static=system_static,
        weather_state=weather_state,
        zone_i=zone_i,
    )

    # Outdoor airflow is the controllable/direct outdoor exchange excluding
    # infiltration, because infiltration has its own column.
    outdoor_flow = mechanical_flow + window_flow

    return infiltration_flow, mechanical_flow, window_flow, outdoor_flow


def calculate_all_zone_airflow_components_m3_s(
    zone_state,
    zone_static,
    system_state,
    system_static,
    weather_state,
    airflow_link_array=None,
    infiltration_ach=DEFAULT_INFILTRATION_ACH,
    out_infiltration_flows=None,
    out_mechanical_flows=None,
    out_window_flows=None,
    out_outdoor_flows=None,
    out_interzone_flows=None,
    out_total_flows=None,
):
    """
    Calculate all airflow components for all zones.

    Returns:
        infiltration_flows
        mechanical_flows
        window_flows
        outdoor_flows
        interzone_flows
        total_flows
    """
    n_zones = zone_state.shape[0]

    if out_infiltration_flows is None:
        out_infiltration_flows = np.zeros((n_zones,), dtype=np.float64)
    if out_mechanical_flows is None:
        out_mechanical_flows = np.zeros((n_zones,), dtype=np.float64)
    if out_window_flows is None:
        out_window_flows = np.zeros((n_zones,), dtype=np.float64)
    if out_outdoor_flows is None:
        out_outdoor_flows = np.zeros((n_zones,), dtype=np.float64)
    if out_interzone_flows is None:
        out_interzone_flows = np.zeros((n_zones,), dtype=np.float64)
    if out_total_flows is None:
        out_total_flows = np.zeros((n_zones,), dtype=np.float64)

    for zone_i in range(n_zones):
        infiltration, mechanical, window, outdoor = calculate_zone_airflow_components_m3_s(
            zone_state=zone_state,
            zone_static=zone_static,
            system_state=system_state,
            system_static=system_static,
            weather_state=weather_state,
            zone_i=zone_i,
            infiltration_ach=infiltration_ach,
        )

        out_infiltration_flows[zone_i] = infiltration
        out_mechanical_flows[zone_i] = mechanical
        out_window_flows[zone_i] = window
        out_outdoor_flows[zone_i] = outdoor

    calculate_all_interzone_flows_m3_s(
        zone_state=zone_state,
        airflow_link_array=airflow_link_array,
        out_interzone_flows=out_interzone_flows,
    )

    for zone_i in range(n_zones):
        out_total_flows[zone_i] = (
            out_infiltration_flows[zone_i]
            + out_outdoor_flows[zone_i]
            + out_interzone_flows[zone_i]
        )

    return (
        out_infiltration_flows,
        out_mechanical_flows,
        out_window_flows,
        out_outdoor_flows,
        out_interzone_flows,
        out_total_flows,
    )


# =============================================================================
# Write airflow results
# =============================================================================

def write_airflow_results_to_zone_state(
    zone_state,
    physics_result,
    infiltration_flows,
    outdoor_flows,
    interzone_flows,
    total_flows,
):
    """
    Write airflow results into zone_state and physics_result.
    """
    for zone_i in range(zone_state.shape[0]):
        if _zone_is_outside(zone_state, zone_i):
            zone_state[zone_i, schema.ZONE_INFILTRATION_AIRFLOW_M3_S] = 0.0
            zone_state[zone_i, schema.ZONE_OUTDOOR_AIRFLOW_M3_S] = 0.0
            zone_state[zone_i, schema.ZONE_INTERZONE_AIRFLOW_M3_S] = 0.0

            if physics_result is not None:
                physics_result[zone_i, schema.PHYSICS_ZONE_ID] = zone_state[
                    zone_i,
                    schema.ZONE_ID,
                ]
                physics_result[zone_i, schema.PHYSICS_VENTILATION_FLOW_M3_S] = 0.0

            continue

        zone_state[zone_i, schema.ZONE_INFILTRATION_AIRFLOW_M3_S] = infiltration_flows[
            zone_i
        ]
        zone_state[zone_i, schema.ZONE_OUTDOOR_AIRFLOW_M3_S] = outdoor_flows[
            zone_i
        ]
        zone_state[zone_i, schema.ZONE_INTERZONE_AIRFLOW_M3_S] = interzone_flows[
            zone_i
        ]

        if physics_result is not None:
            physics_result[zone_i, schema.PHYSICS_ZONE_ID] = zone_state[
                zone_i,
                schema.ZONE_ID,
            ]
            physics_result[zone_i, schema.PHYSICS_VENTILATION_FLOW_M3_S] = total_flows[
                zone_i
            ]

    return True


def step_building_airflow(
    zone_state,
    zone_static,
    system_state,
    system_static,
    weather_state,
    physics_result=None,
    airflow_link_array=None,
    infiltration_ach=DEFAULT_INFILTRATION_ACH,
):
    """
    Phase 11.2 airflow timestep.

    Mutates:
        zone_state
        physics_result
        airflow_link_array, if provided, by writing current link flow

    Returns:
        zone_state, physics_result
    """
    (
        infiltration_flows,
        mechanical_flows,
        window_flows,
        outdoor_flows,
        interzone_flows,
        total_flows,
    ) = calculate_all_zone_airflow_components_m3_s(
        zone_state=zone_state,
        zone_static=zone_static,
        system_state=system_state,
        system_static=system_static,
        weather_state=weather_state,
        airflow_link_array=airflow_link_array,
        infiltration_ach=infiltration_ach,
    )

    write_airflow_results_to_zone_state(
        zone_state=zone_state,
        physics_result=physics_result,
        infiltration_flows=infiltration_flows,
        outdoor_flows=outdoor_flows,
        interzone_flows=interzone_flows,
        total_flows=total_flows,
    )

    return zone_state, physics_result


def run_airflow_step(
    zone_state,
    zone_static,
    system_state,
    system_static,
    weather_state,
    physics_result=None,
    airflow_link_array=None,
    infiltration_ach=DEFAULT_INFILTRATION_ACH,
):
    """
    Public alias for future physics orchestration.
    """
    return step_building_airflow(
        zone_state=zone_state,
        zone_static=zone_static,
        system_state=system_state,
        system_static=system_static,
        weather_state=weather_state,
        physics_result=physics_result,
        airflow_link_array=airflow_link_array,
        infiltration_ach=infiltration_ach,
    )