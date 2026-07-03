"""
ABBEY array CO2 kernels.

Phase 11.3:
    Move CO2 balance into numeric arrays.

This module consumes airflow outputs from Phase 11.2:
    zone_state[:, ZONE_OUTDOOR_AIRFLOW_M3_S]
    zone_state[:, ZONE_INFILTRATION_AIRFLOW_M3_S]
    zone_state[:, ZONE_INTERZONE_AIRFLOW_M3_S]

It updates:
    zone_state[:, ZONE_CO2_PPM]
    physics_result[:, PHYSICS_CO2_PPM]

Sources:
    zone_state[:, ZONE_CO2_GAIN_KG_S]
    internal_gains[:, GAIN_CO2_KG_S], if provided

Outdoor sink/source:
    weather_state[WEATHER_OUTDOOR_CO2_PPM]

Interzone mixing:
    optional airflow_link_array from airflow_kernels.py

Important:
    - No zone objects.
    - No observation objects.
    - No dicts in timestep-facing functions.
    - No strings.
    - Numeric arrays only.
"""

import numpy as np

from nexusep.abbey.arrays import schema
from nexusep.abbey.arrays.airflow_kernels import (
    AIRFLOW_LINK_ZONE_A_ID,
    AIRFLOW_LINK_ZONE_B_ID,
    AIRFLOW_LINK_CURRENT_FLOW_M3_S,
    calculate_interzone_link_flow_m3_s,
)


# =============================================================================
# Constants
# =============================================================================

AIR_DENSITY_KG_M3 = 1.2

# CO2 molar mass / dry air average molar mass.
# Used to convert CO2 mass fraction into approximate ppmv.
CO2_TO_AIR_MOLAR_MASS_RATIO = 44.01 / 28.97

DEFAULT_OUTDOOR_CO2_PPM = 420.0
DEFAULT_MIN_CO2_PPM = 350.0
DEFAULT_MAX_CO2_PPM = 10000.0


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


def co2_gain_kg_s_to_ppm_s(
    co2_gain_kg_s,
    zone_volume_m3,
    air_density_kg_m3=AIR_DENSITY_KG_M3,
):
    """
    Convert CO2 generation kg/s into approximate ppm/s.

    ppm/s =
        kg_CO2/s
        / (rho_air * volume * CO2_to_air_molar_mass_ratio)
        * 1e6
    """
    co2_gain_kg_s = float(co2_gain_kg_s)
    zone_volume_m3 = float(zone_volume_m3)

    if zone_volume_m3 <= 0.0:
        return 0.0

    air_mass_kg = air_density_kg_m3 * zone_volume_m3

    if air_mass_kg <= 0.0:
        return 0.0

    return (
        co2_gain_kg_s
        / (air_mass_kg * CO2_TO_AIR_MOLAR_MASS_RATIO)
        * 1.0e6
    )


def co2_ppm_to_mass_kg(
    co2_ppm,
    zone_volume_m3,
    air_density_kg_m3=AIR_DENSITY_KG_M3,
):
    """
    Approximate CO2 mass contained in a zone from ppm.
    """
    air_mass_kg = air_density_kg_m3 * zone_volume_m3

    return (
        float(co2_ppm)
        * 1.0e-6
        * CO2_TO_AIR_MOLAR_MASS_RATIO
        * air_mass_kg
    )


def co2_mass_kg_to_ppm(
    co2_mass_kg,
    zone_volume_m3,
    air_density_kg_m3=AIR_DENSITY_KG_M3,
):
    """
    Approximate ppm from CO2 mass in zone.
    """
    air_mass_kg = air_density_kg_m3 * zone_volume_m3

    if air_mass_kg <= 0.0:
        return DEFAULT_OUTDOOR_CO2_PPM

    return (
        float(co2_mass_kg)
        / (CO2_TO_AIR_MOLAR_MASS_RATIO * air_mass_kg)
        * 1.0e6
    )


# =============================================================================
# CO2 source handling
# =============================================================================

def copy_zone_co2_gains_to_internal_gains(
    zone_state,
    internal_gains,
):
    """
    Copy zone CO2 gain column into internal_gains.

    Useful because earlier execution/person kernels may write directly to
    zone_state.
    """
    if internal_gains is None:
        return True

    for zone_i in range(zone_state.shape[0]):
        internal_gains[zone_i, schema.GAIN_ZONE_ID] = zone_i
        internal_gains[zone_i, schema.GAIN_CO2_KG_S] = zone_state[
            zone_i,
            schema.ZONE_CO2_GAIN_KG_S,
        ]

    return True


def get_zone_co2_gain_kg_s(
    zone_state,
    internal_gains,
    zone_i,
):
    """
    Read CO2 source for a zone.

    Preference:
        internal_gains if provided

    Fallback:
        zone_state
    """
    if internal_gains is not None:
        return internal_gains[zone_i, schema.GAIN_CO2_KG_S]

    return zone_state[zone_i, schema.ZONE_CO2_GAIN_KG_S]


# =============================================================================
# Airflow terms
# =============================================================================

def calculate_outdoor_exchange_flow_for_zone_m3_s(
    zone_state,
    zone_i,
):
    """
    Outdoor exchange used in CO2 balance.

    Includes:
        - outdoor airflow
        - infiltration airflow

    Both are treated as exchange with outdoor CO2 concentration.
    """
    outdoor_flow = _non_negative(
        zone_state[zone_i, schema.ZONE_OUTDOOR_AIRFLOW_M3_S]
    )
    infiltration_flow = _non_negative(
        zone_state[zone_i, schema.ZONE_INFILTRATION_AIRFLOW_M3_S]
    )

    return outdoor_flow + infiltration_flow


def calculate_interzone_flow_terms_for_zone(
    zone_state,
    airflow_link_array,
    zone_i,
):
    """
    Calculate interzone source terms for one zone.

    Returns:
        total_interzone_flow_m3_s
        sum_flow_times_source_co2

    The balance uses:
        sum(q_j * C_j)
    """
    if airflow_link_array is None:
        return 0.0, 0.0

    total_flow = 0.0
    weighted_source = 0.0

    n_zones = zone_state.shape[0]

    for link_i in range(airflow_link_array.shape[0]):
        zone_a = int(airflow_link_array[link_i, AIRFLOW_LINK_ZONE_A_ID])
        zone_b = int(airflow_link_array[link_i, AIRFLOW_LINK_ZONE_B_ID])

        if zone_a == schema.MISSING_ID or zone_b == schema.MISSING_ID:
            continue

        if zone_a < 0 or zone_a >= n_zones:
            continue

        if zone_b < 0 or zone_b >= n_zones:
            continue

        if zone_a != int(zone_i) and zone_b != int(zone_i):
            continue

        current_flow = airflow_link_array[
            link_i,
            AIRFLOW_LINK_CURRENT_FLOW_M3_S,
        ]

        if current_flow <= 0.0:
            current_flow = calculate_interzone_link_flow_m3_s(
                airflow_link_array=airflow_link_array,
                link_i=link_i,
            )

        current_flow = _non_negative(current_flow)

        if current_flow <= 0.0:
            continue

        if zone_a == int(zone_i):
            source_zone = zone_b
        else:
            source_zone = zone_a

        source_co2 = zone_state[source_zone, schema.ZONE_CO2_PPM]

        total_flow += current_flow
        weighted_source += current_flow * source_co2

    return total_flow, weighted_source


# =============================================================================
# Core CO2 balance
# =============================================================================

def semi_implicit_co2_update_scalar(
    old_co2_ppm,
    zone_volume_m3,
    outdoor_co2_ppm,
    outdoor_flow_m3_s,
    interzone_flow_m3_s,
    interzone_flow_times_source_co2,
    co2_gain_kg_s,
    dt_seconds,
    min_co2_ppm=DEFAULT_MIN_CO2_PPM,
    max_co2_ppm=DEFAULT_MAX_CO2_PPM,
):
    """
    Semi-implicit CO2 balance.

    Equation:

        dC/dt =
            q_out/V * (C_out - C)
            + sum(q_j/V * (C_j - C))
            + G_ppm_s

    Semi-implicit form:

        C_next =
            (C_old/dt + q_out/V*C_out + sum(q_j/V*C_j) + G_ppm_s)
            /
            (1/dt + q_out/V + sum(q_j/V))
    """
    zone_volume_m3 = float(zone_volume_m3)
    dt_seconds = float(dt_seconds)

    if zone_volume_m3 <= 0.0:
        return float(old_co2_ppm)

    if dt_seconds <= 0.0:
        raise ValueError("dt_seconds must be positive.")

    old_co2_ppm = float(old_co2_ppm)
    outdoor_co2_ppm = float(outdoor_co2_ppm)

    outdoor_flow_m3_s = _non_negative(outdoor_flow_m3_s)
    interzone_flow_m3_s = _non_negative(interzone_flow_m3_s)

    outdoor_rate_s = outdoor_flow_m3_s / zone_volume_m3
    interzone_rate_s = interzone_flow_m3_s / zone_volume_m3

    source_ppm_s = co2_gain_kg_s_to_ppm_s(
        co2_gain_kg_s=co2_gain_kg_s,
        zone_volume_m3=zone_volume_m3,
    )

    c_over_dt = old_co2_ppm / dt_seconds

    numerator = c_over_dt
    numerator += outdoor_rate_s * outdoor_co2_ppm

    if interzone_flow_m3_s > 0.0:
        numerator += interzone_flow_times_source_co2 / zone_volume_m3

    numerator += source_ppm_s

    denominator = 1.0 / dt_seconds
    denominator += outdoor_rate_s
    denominator += interzone_rate_s

    if denominator <= 0.0:
        return _clip(old_co2_ppm, min_co2_ppm, max_co2_ppm)

    new_co2_ppm = numerator / denominator

    return _clip(new_co2_ppm, min_co2_ppm, max_co2_ppm)


def step_zone_co2_balance(
    zone_state,
    zone_static,
    weather_state,
    internal_gains,
    physics_result,
    zone_i,
    dt_minutes,
    airflow_link_array=None,
    min_co2_ppm=DEFAULT_MIN_CO2_PPM,
    max_co2_ppm=DEFAULT_MAX_CO2_PPM,
):
    """
    Update CO2 for one zone.
    """
    if _zone_is_outside(zone_state, zone_i):
        if physics_result is not None:
            physics_result[zone_i, schema.PHYSICS_ZONE_ID] = zone_state[
                zone_i,
                schema.ZONE_ID,
            ]
            physics_result[zone_i, schema.PHYSICS_CO2_PPM] = weather_state[
                schema.WEATHER_OUTDOOR_CO2_PPM
            ]
        return True

    dt_seconds = float(dt_minutes) * 60.0

    if dt_seconds <= 0.0:
        raise ValueError("dt_minutes must be positive.")

    volume_m3 = _zone_volume_m3(
        zone_static=zone_static,
        zone_i=zone_i,
    )

    old_co2_ppm = zone_state[zone_i, schema.ZONE_CO2_PPM]

    outdoor_co2_ppm = weather_state[schema.WEATHER_OUTDOOR_CO2_PPM]

    if outdoor_co2_ppm <= 0.0:
        outdoor_co2_ppm = DEFAULT_OUTDOOR_CO2_PPM

    outdoor_flow = calculate_outdoor_exchange_flow_for_zone_m3_s(
        zone_state=zone_state,
        zone_i=zone_i,
    )

    interzone_flow, interzone_weighted_source = calculate_interzone_flow_terms_for_zone(
        zone_state=zone_state,
        airflow_link_array=airflow_link_array,
        zone_i=zone_i,
    )

    co2_gain_kg_s = get_zone_co2_gain_kg_s(
        zone_state=zone_state,
        internal_gains=internal_gains,
        zone_i=zone_i,
    )

    new_co2_ppm = semi_implicit_co2_update_scalar(
        old_co2_ppm=old_co2_ppm,
        zone_volume_m3=volume_m3,
        outdoor_co2_ppm=outdoor_co2_ppm,
        outdoor_flow_m3_s=outdoor_flow,
        interzone_flow_m3_s=interzone_flow,
        interzone_flow_times_source_co2=interzone_weighted_source,
        co2_gain_kg_s=co2_gain_kg_s,
        dt_seconds=dt_seconds,
        min_co2_ppm=min_co2_ppm,
        max_co2_ppm=max_co2_ppm,
    )

    zone_state[zone_i, schema.ZONE_CO2_PPM] = new_co2_ppm

    if physics_result is not None:
        physics_result[zone_i, schema.PHYSICS_ZONE_ID] = zone_state[
            zone_i,
            schema.ZONE_ID,
        ]
        physics_result[zone_i, schema.PHYSICS_CO2_PPM] = new_co2_ppm

    return True


# =============================================================================
# Building CO2 step
# =============================================================================

def step_building_co2_balance(
    zone_state,
    zone_static,
    weather_state,
    internal_gains,
    physics_result,
    dt_minutes,
    airflow_link_array=None,
    copy_zone_gains=True,
    min_co2_ppm=DEFAULT_MIN_CO2_PPM,
    max_co2_ppm=DEFAULT_MAX_CO2_PPM,
):
    """
    Update all zone CO2 states for one timestep.

    Mutates:
        zone_state
        physics_result
        internal_gains, only if copy_zone_gains=True and internal_gains is not None

    Returns:
        zone_state, physics_result
    """
    if copy_zone_gains:
        copy_zone_co2_gains_to_internal_gains(
            zone_state=zone_state,
            internal_gains=internal_gains,
        )

    for zone_i in range(zone_state.shape[0]):
        step_zone_co2_balance(
            zone_state=zone_state,
            zone_static=zone_static,
            weather_state=weather_state,
            internal_gains=internal_gains,
            physics_result=physics_result,
            zone_i=zone_i,
            dt_minutes=dt_minutes,
            airflow_link_array=airflow_link_array,
            min_co2_ppm=min_co2_ppm,
            max_co2_ppm=max_co2_ppm,
        )

    return zone_state, physics_result


def run_co2_step(
    zone_state,
    zone_static,
    weather_state,
    internal_gains,
    physics_result,
    dt_minutes,
    airflow_link_array=None,
):
    """
    Public alias for future physics orchestration.
    """
    return step_building_co2_balance(
        zone_state=zone_state,
        zone_static=zone_static,
        weather_state=weather_state,
        internal_gains=internal_gains,
        physics_result=physics_result,
        dt_minutes=dt_minutes,
        airflow_link_array=airflow_link_array,
    )