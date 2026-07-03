"""
ABBEY array moisture kernels.

Phase 11.4:
    Move moisture / humidity balance into numeric arrays.

This module consumes airflow outputs from Phase 11.2:
    zone_state[:, ZONE_OUTDOOR_AIRFLOW_M3_S]
    zone_state[:, ZONE_INFILTRATION_AIRFLOW_M3_S]
    zone_state[:, ZONE_INTERZONE_AIRFLOW_M3_S]

It updates:
    zone_state[:, ZONE_RELATIVE_HUMIDITY]
    physics_result[:, PHYSICS_RELATIVE_HUMIDITY]

Sources:
    zone_state[:, ZONE_MOISTURE_GAIN_KG_S]
    internal_gains[:, GAIN_MOISTURE_KG_S], if provided

Outdoor boundary:
    weather_state[WEATHER_OUTDOOR_RELATIVE_HUMIDITY]
    weather_state[WEATHER_OUTDOOR_TEMPERATURE_C]

Interzone mixing:
    optional airflow_link_array from airflow_kernels.py

Important:
    - No zone objects.
    - No observation objects.
    - No dicts in timestep-facing functions.
    - No strings.
    - Numeric arrays only.

Schema limitation:
    The current zone_state stores relative humidity, not humidity ratio.
    So this kernel:
        1. converts RH + temperature to humidity ratio
        2. runs the moisture mass balance in humidity-ratio space
        3. converts back to RH
"""

import math

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
ATMOSPHERIC_PRESSURE_PA = 101325.0
WATER_VAPOR_MOLECULAR_RATIO = 0.62198

DEFAULT_OUTDOOR_RELATIVE_HUMIDITY = 0.50
DEFAULT_MIN_RELATIVE_HUMIDITY = 0.05
DEFAULT_MAX_RELATIVE_HUMIDITY = 1.00

DEFAULT_MIN_HUMIDITY_RATIO_KG_KG = 0.0001
DEFAULT_MAX_HUMIDITY_RATIO_KG_KG = 0.035


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


def _normalize_rh_fraction(relative_humidity):
    """
    Accept either:
        0.50
        50.0

    Return:
        0.50
    """
    rh = float(relative_humidity)

    if rh > 1.5:
        rh = rh / 100.0

    return _clip(rh, 0.0, 1.0)


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


# =============================================================================
# Psychrometric helpers
# =============================================================================

def saturation_vapor_pressure_pa(temperature_c):
    """
    Saturation vapor pressure over water, Pa.

    Tetens-style approximation.
    Good enough for building-simulation control ranges.
    """
    temperature_c = float(temperature_c)

    return 610.94 * math.exp(
        17.625 * temperature_c / (temperature_c + 243.04)
    )


def relative_humidity_to_humidity_ratio_kg_kg(
    relative_humidity,
    temperature_c,
    atmospheric_pressure_pa=ATMOSPHERIC_PRESSURE_PA,
):
    """
    Convert RH fraction and dry-bulb temperature to humidity ratio kg/kg dry air.
    """
    rh = _normalize_rh_fraction(relative_humidity)

    p_ws = saturation_vapor_pressure_pa(temperature_c)
    p_v = rh * p_ws

    # Safety against saturation pressure weirdness at high temperature.
    p_v = _clip(p_v, 0.0, 0.99 * atmospheric_pressure_pa)

    denominator = atmospheric_pressure_pa - p_v

    if denominator <= 0.0:
        return DEFAULT_MAX_HUMIDITY_RATIO_KG_KG

    w = WATER_VAPOR_MOLECULAR_RATIO * p_v / denominator

    return _clip(
        w,
        DEFAULT_MIN_HUMIDITY_RATIO_KG_KG,
        DEFAULT_MAX_HUMIDITY_RATIO_KG_KG,
    )


def humidity_ratio_to_relative_humidity(
    humidity_ratio_kg_kg,
    temperature_c,
    atmospheric_pressure_pa=ATMOSPHERIC_PRESSURE_PA,
):
    """
    Convert humidity ratio kg/kg dry air to RH fraction.
    """
    w = _non_negative(humidity_ratio_kg_kg)

    p_ws = saturation_vapor_pressure_pa(temperature_c)

    if p_ws <= 0.0:
        return DEFAULT_OUTDOOR_RELATIVE_HUMIDITY

    p_v = atmospheric_pressure_pa * w / (
        WATER_VAPOR_MOLECULAR_RATIO + w
    )

    rh = p_v / p_ws

    return _clip(rh, 0.0, 1.5)


def moisture_gain_kg_s_to_humidity_ratio_s(
    moisture_gain_kg_s,
    zone_volume_m3,
    air_density_kg_m3=AIR_DENSITY_KG_M3,
):
    """
    Convert water-vapor generation kg/s into humidity-ratio increase per second.

        dW/dt = G / m_air
    """
    moisture_gain_kg_s = float(moisture_gain_kg_s)
    zone_volume_m3 = float(zone_volume_m3)

    if zone_volume_m3 <= 0.0:
        return 0.0

    air_mass_kg = air_density_kg_m3 * zone_volume_m3

    if air_mass_kg <= 0.0:
        return 0.0

    return moisture_gain_kg_s / air_mass_kg


def humidity_ratio_mass_kg(
    humidity_ratio_kg_kg,
    zone_volume_m3,
    air_density_kg_m3=AIR_DENSITY_KG_M3,
):
    """
    Approximate vapor mass represented by humidity ratio in a zone.

    This is mostly for tests/sanity checks.
    """
    air_mass_kg = air_density_kg_m3 * zone_volume_m3

    return float(humidity_ratio_kg_kg) * air_mass_kg


def vapor_mass_kg_to_humidity_ratio(
    vapor_mass_kg,
    zone_volume_m3,
    air_density_kg_m3=AIR_DENSITY_KG_M3,
):
    """
    Approximate humidity ratio from vapor mass in a zone.

    This is mostly for tests/sanity checks.
    """
    air_mass_kg = air_density_kg_m3 * zone_volume_m3

    if air_mass_kg <= 0.0:
        return DEFAULT_MIN_HUMIDITY_RATIO_KG_KG

    return float(vapor_mass_kg) / air_mass_kg


# =============================================================================
# Moisture source handling
# =============================================================================

def copy_zone_moisture_gains_to_internal_gains(
    zone_state,
    internal_gains,
):
    """
    Copy zone moisture gain column into internal_gains.

    Useful because earlier execution/person kernels may write directly to
    zone_state.
    """
    if internal_gains is None:
        return True

    for zone_i in range(zone_state.shape[0]):
        internal_gains[zone_i, schema.GAIN_ZONE_ID] = zone_i
        internal_gains[zone_i, schema.GAIN_MOISTURE_KG_S] = zone_state[
            zone_i,
            schema.ZONE_MOISTURE_GAIN_KG_S,
        ]

    return True


def get_zone_moisture_gain_kg_s(
    zone_state,
    internal_gains,
    zone_i,
):
    """
    Read moisture source for a zone.

    Preference:
        internal_gains if provided

    Fallback:
        zone_state
    """
    if internal_gains is not None:
        return internal_gains[zone_i, schema.GAIN_MOISTURE_KG_S]

    return zone_state[zone_i, schema.ZONE_MOISTURE_GAIN_KG_S]


# =============================================================================
# Airflow terms
# =============================================================================

def calculate_outdoor_exchange_flow_for_zone_m3_s(
    zone_state,
    zone_i,
):
    """
    Outdoor exchange used in moisture balance.

    Includes:
        - outdoor airflow
        - infiltration airflow

    Both are treated as exchange with outdoor humidity ratio.
    """
    outdoor_flow = _non_negative(
        zone_state[zone_i, schema.ZONE_OUTDOOR_AIRFLOW_M3_S]
    )
    infiltration_flow = _non_negative(
        zone_state[zone_i, schema.ZONE_INFILTRATION_AIRFLOW_M3_S]
    )

    return outdoor_flow + infiltration_flow


def zone_humidity_ratio_from_state(
    zone_state,
    zone_i,
):
    """
    Convert one zone's current RH and temperature to humidity ratio.
    """
    rh = zone_state[zone_i, schema.ZONE_RELATIVE_HUMIDITY]
    temp = zone_state[zone_i, schema.ZONE_AIR_TEMPERATURE_C]

    return relative_humidity_to_humidity_ratio_kg_kg(
        relative_humidity=rh,
        temperature_c=temp,
    )


# =============================================================================
# Numba-prep snapshot helpers
# =============================================================================

def fill_zone_humidity_ratio_snapshot(
    zone_state,
    humidity_ratio_snapshot,
):
    """
    Fill preallocated previous-timestep humidity-ratio snapshot.

    Avoids allocating a new snapshot array inside the timestep.
    """
    for zone_i in range(zone_state.shape[0]):
        humidity_ratio_snapshot[zone_i] = zone_humidity_ratio_from_state(
            zone_state=zone_state,
            zone_i=zone_i,
        )

    return True


def step_building_moisture_balance_numba_ready(
    zone_state,
    zone_static,
    weather_state,
    internal_gains,
    physics_result,
    dt_minutes,
    airflow_link_array,
    humidity_ratio_snapshot,
    copy_zone_gains_flag=1,
    min_relative_humidity=DEFAULT_MIN_RELATIVE_HUMIDITY,
    max_relative_humidity=DEFAULT_MAX_RELATIVE_HUMIDITY,
):
    """
    Numba-prep moisture balance.

    Difference from step_building_moisture_balance(...):
        - airflow_link_array is required
        - humidity_ratio_snapshot is required
        - no optional None
        - no internally allocated snapshot
    """
    if copy_zone_gains_flag > 0:
        copy_zone_moisture_gains_to_internal_gains(
            zone_state=zone_state,
            internal_gains=internal_gains,
        )

    fill_zone_humidity_ratio_snapshot(
        zone_state=zone_state,
        humidity_ratio_snapshot=humidity_ratio_snapshot,
    )

    for zone_i in range(zone_state.shape[0]):
        step_zone_moisture_balance(
            zone_state=zone_state,
            zone_static=zone_static,
            weather_state=weather_state,
            internal_gains=internal_gains,
            physics_result=physics_result,
            zone_i=zone_i,
            dt_minutes=dt_minutes,
            airflow_link_array=airflow_link_array,
            old_humidity_ratio_by_zone=humidity_ratio_snapshot,
            min_relative_humidity=min_relative_humidity,
            max_relative_humidity=max_relative_humidity,
        )

    return True


def run_moisture_step_numba_ready(
    zone_state,
    zone_static,
    weather_state,
    internal_gains,
    physics_result,
    dt_minutes,
    airflow_link_array,
    humidity_ratio_snapshot,
):
    return step_building_moisture_balance_numba_ready(
        zone_state=zone_state,
        zone_static=zone_static,
        weather_state=weather_state,
        internal_gains=internal_gains,
        physics_result=physics_result,
        dt_minutes=dt_minutes,
        airflow_link_array=airflow_link_array,
        humidity_ratio_snapshot=humidity_ratio_snapshot,
    )


def make_zone_humidity_ratio_snapshot(zone_state):
    """
    Create previous-timestep humidity-ratio snapshot for all zones.

    This prevents interzone moisture mixing from becoming order-dependent.
    """
    n_zones = zone_state.shape[0]
    snapshot = np.zeros((n_zones,), dtype=np.float64)

    for zone_i in range(n_zones):
        snapshot[zone_i] = zone_humidity_ratio_from_state(
            zone_state=zone_state,
            zone_i=zone_i,
        )

    return snapshot

def weather_humidity_ratio_from_state(
    weather_state,
):
    """
    Convert weather outdoor RH and temperature to humidity ratio.
    """
    outdoor_rh = weather_state[
        schema.WEATHER_OUTDOOR_RELATIVE_HUMIDITY
    ]
    outdoor_temp = weather_state[
        schema.WEATHER_OUTDOOR_TEMPERATURE_C
    ]

    if outdoor_rh <= 0.0:
        outdoor_rh = DEFAULT_OUTDOOR_RELATIVE_HUMIDITY

    return relative_humidity_to_humidity_ratio_kg_kg(
        relative_humidity=outdoor_rh,
        temperature_c=outdoor_temp,
    )


def calculate_interzone_humidity_terms_for_zone(
    zone_state,
    airflow_link_array,
    zone_i,
    old_humidity_ratio_by_zone=None,
):
    """
    Calculate interzone source terms for one zone.

    Returns:
        total_interzone_flow_m3_s
        sum_flow_times_source_humidity_ratio

    The balance uses:
        sum(q_j * W_j)

    If old_humidity_ratio_by_zone is provided, interzone mixing uses the
    previous timestep source humidity ratios. This avoids order-dependent
    updates when stepping zones one by one.
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

        if old_humidity_ratio_by_zone is not None:
            source_w = old_humidity_ratio_by_zone[source_zone]
        else:
            source_w = zone_humidity_ratio_from_state(
                zone_state=zone_state,
                zone_i=source_zone,
            )

        total_flow += current_flow
        weighted_source += current_flow * source_w

    return total_flow, weighted_source


# =============================================================================
# Core moisture balance
# =============================================================================

def semi_implicit_humidity_ratio_update_scalar(
    old_humidity_ratio_kg_kg,
    zone_volume_m3,
    outdoor_humidity_ratio_kg_kg,
    outdoor_flow_m3_s,
    interzone_flow_m3_s,
    interzone_flow_times_source_humidity_ratio,
    moisture_gain_kg_s,
    dt_seconds,
    min_humidity_ratio_kg_kg=DEFAULT_MIN_HUMIDITY_RATIO_KG_KG,
    max_humidity_ratio_kg_kg=DEFAULT_MAX_HUMIDITY_RATIO_KG_KG,
):
    """
    Semi-implicit humidity-ratio balance.

    Equation:

        dW/dt =
            q_out/V * (W_out - W)
            + sum(q_j/V * (W_j - W))
            + G / (rho_air * V)

    Semi-implicit form:

        W_next =
            (W_old/dt + q_out/V*W_out + sum(q_j/V*W_j) + G/(rho*V))
            /
            (1/dt + q_out/V + sum(q_j/V))
    """
    zone_volume_m3 = float(zone_volume_m3)
    dt_seconds = float(dt_seconds)

    if zone_volume_m3 <= 0.0:
        return float(old_humidity_ratio_kg_kg)

    if dt_seconds <= 0.0:
        raise ValueError("dt_seconds must be positive.")

    old_w = float(old_humidity_ratio_kg_kg)
    outdoor_w = float(outdoor_humidity_ratio_kg_kg)

    outdoor_flow_m3_s = _non_negative(outdoor_flow_m3_s)
    interzone_flow_m3_s = _non_negative(interzone_flow_m3_s)

    outdoor_rate_s = outdoor_flow_m3_s / zone_volume_m3
    interzone_rate_s = interzone_flow_m3_s / zone_volume_m3

    source_w_s = moisture_gain_kg_s_to_humidity_ratio_s(
        moisture_gain_kg_s=moisture_gain_kg_s,
        zone_volume_m3=zone_volume_m3,
    )

    numerator = old_w / dt_seconds
    numerator += outdoor_rate_s * outdoor_w

    if interzone_flow_m3_s > 0.0:
        numerator += interzone_flow_times_source_humidity_ratio / zone_volume_m3

    numerator += source_w_s

    denominator = 1.0 / dt_seconds
    denominator += outdoor_rate_s
    denominator += interzone_rate_s

    if denominator <= 0.0:
        return _clip(
            old_w,
            min_humidity_ratio_kg_kg,
            max_humidity_ratio_kg_kg,
        )

    new_w = numerator / denominator

    return _clip(
        new_w,
        min_humidity_ratio_kg_kg,
        max_humidity_ratio_kg_kg,
    )


def step_zone_moisture_balance(
    zone_state,
    zone_static,
    weather_state,
    internal_gains,
    physics_result,
    zone_i,
    dt_minutes,
    airflow_link_array=None,
    old_humidity_ratio_by_zone=None,
    min_relative_humidity=DEFAULT_MIN_RELATIVE_HUMIDITY,
    max_relative_humidity=DEFAULT_MAX_RELATIVE_HUMIDITY,
):
    """
    Update moisture/RH for one zone.
    """
    if _zone_is_outside(zone_state, zone_i):
        if physics_result is not None:
            physics_result[zone_i, schema.PHYSICS_ZONE_ID] = zone_state[
                zone_i,
                schema.ZONE_ID,
            ]
            physics_result[
                zone_i,
                schema.PHYSICS_RELATIVE_HUMIDITY,
            ] = weather_state[schema.WEATHER_OUTDOOR_RELATIVE_HUMIDITY]
        return True

    dt_seconds = float(dt_minutes) * 60.0

    if dt_seconds <= 0.0:
        raise ValueError("dt_minutes must be positive.")

    volume_m3 = _zone_volume_m3(
        zone_static=zone_static,
        zone_i=zone_i,
    )

    old_rh = zone_state[zone_i, schema.ZONE_RELATIVE_HUMIDITY]
    zone_temp = zone_state[zone_i, schema.ZONE_AIR_TEMPERATURE_C]

    old_w = relative_humidity_to_humidity_ratio_kg_kg(
        relative_humidity=old_rh,
        temperature_c=zone_temp,
    )

    outdoor_w = weather_humidity_ratio_from_state(
        weather_state=weather_state,
    )

    outdoor_flow = calculate_outdoor_exchange_flow_for_zone_m3_s(
        zone_state=zone_state,
        zone_i=zone_i,
    )

    interzone_flow, interzone_weighted_source = calculate_interzone_humidity_terms_for_zone(
        zone_state=zone_state,
        airflow_link_array=airflow_link_array,
        zone_i=zone_i,
        old_humidity_ratio_by_zone=old_humidity_ratio_by_zone,
    )

    moisture_gain_kg_s = get_zone_moisture_gain_kg_s(
        zone_state=zone_state,
        internal_gains=internal_gains,
        zone_i=zone_i,
    )

    new_w = semi_implicit_humidity_ratio_update_scalar(
        old_humidity_ratio_kg_kg=old_w,
        zone_volume_m3=volume_m3,
        outdoor_humidity_ratio_kg_kg=outdoor_w,
        outdoor_flow_m3_s=outdoor_flow,
        interzone_flow_m3_s=interzone_flow,
        interzone_flow_times_source_humidity_ratio=interzone_weighted_source,
        moisture_gain_kg_s=moisture_gain_kg_s,
        dt_seconds=dt_seconds,
    )

    new_rh = humidity_ratio_to_relative_humidity(
        humidity_ratio_kg_kg=new_w,
        temperature_c=zone_temp,
    )

    new_rh = _clip(
        new_rh,
        min_relative_humidity,
        max_relative_humidity,
    )

    zone_state[zone_i, schema.ZONE_RELATIVE_HUMIDITY] = new_rh

    if physics_result is not None:
        physics_result[zone_i, schema.PHYSICS_ZONE_ID] = zone_state[
            zone_i,
            schema.ZONE_ID,
        ]
        physics_result[zone_i, schema.PHYSICS_RELATIVE_HUMIDITY] = new_rh

    return True


# =============================================================================
# Building moisture step
# =============================================================================

def step_building_moisture_balance(
    zone_state,
    zone_static,
    weather_state,
    internal_gains,
    physics_result,
    dt_minutes,
    airflow_link_array=None,
    copy_zone_gains=True,
    min_relative_humidity=DEFAULT_MIN_RELATIVE_HUMIDITY,
    max_relative_humidity=DEFAULT_MAX_RELATIVE_HUMIDITY,
):
    """
    Update all zone moisture/RH states for one timestep.

    Mutates:
        zone_state
        physics_result
        internal_gains, only if copy_zone_gains=True and internal_gains is not None

    Returns:
        zone_state, physics_result
    """
    if copy_zone_gains:
        copy_zone_moisture_gains_to_internal_gains(
            zone_state=zone_state,
            internal_gains=internal_gains,
        )
        
    old_humidity_ratio_by_zone = make_zone_humidity_ratio_snapshot(
        zone_state=zone_state,
    )
    
    for zone_i in range(zone_state.shape[0]):
        step_zone_moisture_balance(
            zone_state=zone_state,
            zone_static=zone_static,
            weather_state=weather_state,
            internal_gains=internal_gains,
            physics_result=physics_result,
            zone_i=zone_i,
            dt_minutes=dt_minutes,
            airflow_link_array=airflow_link_array,
            old_humidity_ratio_by_zone=old_humidity_ratio_by_zone,
            min_relative_humidity=min_relative_humidity,
            max_relative_humidity=max_relative_humidity,
        )

    return zone_state, physics_result

def step_building_moisture_balance_fast(
    zone_state,
    zone_static,
    weather_state,
    internal_gains,
    physics_result,
    dt_minutes,
    airflow_link_array=None,
    copy_zone_gains=True,
    min_relative_humidity=DEFAULT_MIN_RELATIVE_HUMIDITY,
    max_relative_humidity=DEFAULT_MAX_RELATIVE_HUMIDITY,
):
    """
    Fast moisture/RH timestep.

    Same model as step_building_moisture_balance, but avoids:
        - per-timestep np.zeros snapshot allocation through make_zone_humidity_ratio_snapshot
        - calling step_zone_moisture_balance for every zone
        - repeated weather humidity conversion
        - repeated small helper calls in the zone loop

    Still uses a previous-timestep humidity-ratio snapshot so interzone mixing
    does not become order-dependent.
    """
    dt_seconds = float(dt_minutes) * 60.0

    if dt_seconds <= 0.0:
        raise ValueError("dt_minutes must be positive.")

    n_zones = zone_state.shape[0]

    # -------------------------------------------------------------------------
    # Copy zone moisture gains to internal_gains.
    # -------------------------------------------------------------------------

    if copy_zone_gains and internal_gains is not None:
        for zone_i in range(n_zones):
            internal_gains[zone_i, schema.GAIN_ZONE_ID] = zone_i
            internal_gains[zone_i, schema.GAIN_MOISTURE_KG_S] = zone_state[
                zone_i,
                schema.ZONE_MOISTURE_GAIN_KG_S,
            ]

    # -------------------------------------------------------------------------
    # Outdoor humidity ratio once per timestep.
    # -------------------------------------------------------------------------

    outdoor_rh = weather_state[schema.WEATHER_OUTDOOR_RELATIVE_HUMIDITY]
    outdoor_temp = weather_state[schema.WEATHER_OUTDOOR_TEMPERATURE_C]

    if outdoor_rh <= 0.0:
        outdoor_rh = DEFAULT_OUTDOOR_RELATIVE_HUMIDITY

    if outdoor_rh > 1.5:
        outdoor_rh = outdoor_rh / 100.0

    if outdoor_rh < 0.0:
        outdoor_rh = 0.0
    elif outdoor_rh > 1.0:
        outdoor_rh = 1.0

    p_ws_outdoor = 610.94 * math.exp(
        17.625 * outdoor_temp / (outdoor_temp + 243.04)
    )
    p_v_outdoor = outdoor_rh * p_ws_outdoor

    if p_v_outdoor < 0.0:
        p_v_outdoor = 0.0
    elif p_v_outdoor > 0.99 * ATMOSPHERIC_PRESSURE_PA:
        p_v_outdoor = 0.99 * ATMOSPHERIC_PRESSURE_PA

    denominator_outdoor = ATMOSPHERIC_PRESSURE_PA - p_v_outdoor

    if denominator_outdoor <= 0.0:
        outdoor_w = DEFAULT_MAX_HUMIDITY_RATIO_KG_KG
    else:
        outdoor_w = (
            WATER_VAPOR_MOLECULAR_RATIO
            * p_v_outdoor
            / denominator_outdoor
        )

    if outdoor_w < DEFAULT_MIN_HUMIDITY_RATIO_KG_KG:
        outdoor_w = DEFAULT_MIN_HUMIDITY_RATIO_KG_KG
    elif outdoor_w > DEFAULT_MAX_HUMIDITY_RATIO_KG_KG:
        outdoor_w = DEFAULT_MAX_HUMIDITY_RATIO_KG_KG

    # -------------------------------------------------------------------------
    # Previous-timestep humidity-ratio snapshot.
    #
    # We still need this to avoid order-dependent interzone moisture mixing.
    # This uses np.empty instead of np.zeros because every value is overwritten.
    # -------------------------------------------------------------------------

    old_humidity_ratio_by_zone = np.empty((n_zones,), dtype=np.float64)

    for zone_i in range(n_zones):
        rh = zone_state[zone_i, schema.ZONE_RELATIVE_HUMIDITY]
        temp = zone_state[zone_i, schema.ZONE_AIR_TEMPERATURE_C]

        if rh > 1.5:
            rh = rh / 100.0

        if rh < 0.0:
            rh = 0.0
        elif rh > 1.0:
            rh = 1.0

        p_ws = 610.94 * math.exp(
            17.625 * temp / (temp + 243.04)
        )
        p_v = rh * p_ws

        if p_v < 0.0:
            p_v = 0.0
        elif p_v > 0.99 * ATMOSPHERIC_PRESSURE_PA:
            p_v = 0.99 * ATMOSPHERIC_PRESSURE_PA

        denominator = ATMOSPHERIC_PRESSURE_PA - p_v

        if denominator <= 0.0:
            old_w = DEFAULT_MAX_HUMIDITY_RATIO_KG_KG
        else:
            old_w = (
                WATER_VAPOR_MOLECULAR_RATIO
                * p_v
                / denominator
            )

        if old_w < DEFAULT_MIN_HUMIDITY_RATIO_KG_KG:
            old_w = DEFAULT_MIN_HUMIDITY_RATIO_KG_KG
        elif old_w > DEFAULT_MAX_HUMIDITY_RATIO_KG_KG:
            old_w = DEFAULT_MAX_HUMIDITY_RATIO_KG_KG

        old_humidity_ratio_by_zone[zone_i] = old_w

    # -------------------------------------------------------------------------
    # Zone loop.
    # -------------------------------------------------------------------------

    for zone_i in range(n_zones):
        zone_id = zone_state[zone_i, schema.ZONE_ID]

        if int(zone_state[zone_i, schema.ZONE_TYPE]) == schema.ZONE_TYPE_OUTSIDE:
            if physics_result is not None:
                physics_result[zone_i, schema.PHYSICS_ZONE_ID] = zone_id
                physics_result[
                    zone_i,
                    schema.PHYSICS_RELATIVE_HUMIDITY,
                ] = weather_state[schema.WEATHER_OUTDOOR_RELATIVE_HUMIDITY]
            continue

        # ---------------------------------------------------------------------
        # Zone volume.
        # ---------------------------------------------------------------------

        volume_m3 = zone_static[zone_i, schema.ZONE_STATIC_VOLUME_M3]

        if volume_m3 <= 0.0:
            area = zone_static[zone_i, schema.ZONE_STATIC_FLOOR_AREA_M2]
            height = zone_static[zone_i, schema.ZONE_STATIC_HEIGHT_M]

            if height <= 0.0:
                height = 2.7

            volume_m3 = area * height

            if volume_m3 <= 0.0:
                volume_m3 = 50.0

        # ---------------------------------------------------------------------
        # Old humidity ratio from snapshot.
        # ---------------------------------------------------------------------

        old_w = old_humidity_ratio_by_zone[zone_i]
        zone_temp = zone_state[zone_i, schema.ZONE_AIR_TEMPERATURE_C]

        # ---------------------------------------------------------------------
        # Outdoor exchange.
        # ---------------------------------------------------------------------

        outdoor_flow = zone_state[
            zone_i,
            schema.ZONE_OUTDOOR_AIRFLOW_M3_S,
        ]

        if outdoor_flow < 0.0:
            outdoor_flow = 0.0

        infiltration_flow = zone_state[
            zone_i,
            schema.ZONE_INFILTRATION_AIRFLOW_M3_S,
        ]

        if infiltration_flow < 0.0:
            infiltration_flow = 0.0

        outdoor_exchange_flow = outdoor_flow + infiltration_flow

        # ---------------------------------------------------------------------
        # Interzone exchange.
        # ---------------------------------------------------------------------

        interzone_flow = 0.0
        interzone_weighted_source = 0.0

        if airflow_link_array is not None:
            for link_i in range(airflow_link_array.shape[0]):
                zone_a = int(airflow_link_array[link_i, AIRFLOW_LINK_ZONE_A_ID])
                zone_b = int(airflow_link_array[link_i, AIRFLOW_LINK_ZONE_B_ID])

                if zone_a == schema.MISSING_ID or zone_b == schema.MISSING_ID:
                    continue

                if zone_a < 0 or zone_a >= n_zones:
                    continue

                if zone_b < 0 or zone_b >= n_zones:
                    continue

                if zone_a != zone_i and zone_b != zone_i:
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

                if current_flow <= 0.0:
                    continue

                if zone_a == zone_i:
                    source_zone = zone_b
                else:
                    source_zone = zone_a

                source_w = old_humidity_ratio_by_zone[source_zone]

                interzone_flow += current_flow
                interzone_weighted_source += current_flow * source_w

        # ---------------------------------------------------------------------
        # Moisture gain.
        # ---------------------------------------------------------------------

        if internal_gains is not None:
            moisture_gain_kg_s = internal_gains[
                zone_i,
                schema.GAIN_MOISTURE_KG_S,
            ]
        else:
            moisture_gain_kg_s = zone_state[
                zone_i,
                schema.ZONE_MOISTURE_GAIN_KG_S,
            ]

        # ---------------------------------------------------------------------
        # Semi-implicit humidity-ratio update.
        #
        # Same equation as semi_implicit_humidity_ratio_update_scalar.
        # ---------------------------------------------------------------------

        outdoor_rate_s = outdoor_exchange_flow / volume_m3
        interzone_rate_s = interzone_flow / volume_m3

        air_mass_kg = AIR_DENSITY_KG_M3 * volume_m3

        if air_mass_kg <= 0.0:
            source_w_s = 0.0
        else:
            source_w_s = moisture_gain_kg_s / air_mass_kg

        numerator = old_w / dt_seconds
        numerator += outdoor_rate_s * outdoor_w

        if interzone_flow > 0.0:
            numerator += interzone_weighted_source / volume_m3

        numerator += source_w_s

        denominator = 1.0 / dt_seconds
        denominator += outdoor_rate_s
        denominator += interzone_rate_s

        if denominator <= 0.0:
            new_w = old_w
        else:
            new_w = numerator / denominator

        if new_w < DEFAULT_MIN_HUMIDITY_RATIO_KG_KG:
            new_w = DEFAULT_MIN_HUMIDITY_RATIO_KG_KG
        elif new_w > DEFAULT_MAX_HUMIDITY_RATIO_KG_KG:
            new_w = DEFAULT_MAX_HUMIDITY_RATIO_KG_KG

        # ---------------------------------------------------------------------
        # Convert humidity ratio back to RH.
        #
        # Same as humidity_ratio_to_relative_humidity + final RH clipping.
        # ---------------------------------------------------------------------

        if new_w < 0.0:
            new_w_for_rh = 0.0
        else:
            new_w_for_rh = new_w

        p_ws_zone = 610.94 * math.exp(
            17.625 * zone_temp / (zone_temp + 243.04)
        )

        if p_ws_zone <= 0.0:
            new_rh = DEFAULT_OUTDOOR_RELATIVE_HUMIDITY
        else:
            p_v_zone = (
                ATMOSPHERIC_PRESSURE_PA
                * new_w_for_rh
                / (WATER_VAPOR_MOLECULAR_RATIO + new_w_for_rh)
            )

            new_rh = p_v_zone / p_ws_zone

        if new_rh < 0.0:
            new_rh = 0.0
        elif new_rh > 1.5:
            new_rh = 1.5

        if new_rh < min_relative_humidity:
            new_rh = min_relative_humidity
        elif new_rh > max_relative_humidity:
            new_rh = max_relative_humidity

        zone_state[zone_i, schema.ZONE_RELATIVE_HUMIDITY] = new_rh

        if physics_result is not None:
            physics_result[zone_i, schema.PHYSICS_ZONE_ID] = zone_id
            physics_result[
                zone_i,
                schema.PHYSICS_RELATIVE_HUMIDITY,
            ] = new_rh

    return zone_state, physics_result

def run_moisture_step(
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

    Uses the fast moisture path by default.
    """
    return step_building_moisture_balance_fast(
        zone_state=zone_state,
        zone_static=zone_static,
        weather_state=weather_state,
        internal_gains=internal_gains,
        physics_result=physics_result,
        dt_minutes=dt_minutes,
        airflow_link_array=airflow_link_array,
    )