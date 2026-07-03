"""
ABBEY numba physics kernels.

Phase 18:
    Start with stable scalar physics and CO2 building balance.

Keep thermal full-zone update Python for now unless profiling proves it is worth
cleaning next.
"""

import math

from nexusep.abbey.arrays import schema
from nexusep.abbey.arrays.numba_support import optional_njit


# =============================================================================
# Constants
# =============================================================================

AIR_DENSITY_KG_M3 = 1.2
AIR_SPECIFIC_HEAT_J_KG_K = 1005.0

CO2_TO_AIR_MOLAR_MASS_RATIO = 44.01 / 28.97
DEFAULT_OUTDOOR_CO2_PPM = 420.0
DEFAULT_MIN_CO2_PPM = 350.0
DEFAULT_MAX_CO2_PPM = 10000.0

ATMOSPHERIC_PRESSURE_PA = 101325.0
WATER_VAPOR_MOLECULAR_RATIO = 0.62198
DEFAULT_MIN_HUMIDITY_RATIO_KG_KG = 0.0001
DEFAULT_MAX_HUMIDITY_RATIO_KG_KG = 0.035
DEFAULT_MIN_RELATIVE_HUMIDITY = 0.05
DEFAULT_MAX_RELATIVE_HUMIDITY = 1.0


ZONE_TYPE = schema.ZONE_TYPE
ZONE_TYPE_OUTSIDE = schema.ZONE_TYPE_OUTSIDE
ZONE_ID = schema.ZONE_ID
ZONE_STATIC_VOLUME_M3 = schema.ZONE_STATIC_VOLUME_M3

ZONE_CO2_PPM = schema.ZONE_CO2_PPM
ZONE_CO2_GAIN_KG_S = schema.ZONE_CO2_GAIN_KG_S
ZONE_OUTDOOR_AIRFLOW_M3_S = schema.ZONE_OUTDOOR_AIRFLOW_M3_S
ZONE_INFILTRATION_AIRFLOW_M3_S = schema.ZONE_INFILTRATION_AIRFLOW_M3_S

WEATHER_OUTDOOR_CO2_PPM = schema.WEATHER_OUTDOOR_CO2_PPM

GAIN_ZONE_ID = schema.GAIN_ZONE_ID
GAIN_CO2_KG_S = schema.GAIN_CO2_KG_S

PHYSICS_ZONE_ID = schema.PHYSICS_ZONE_ID
PHYSICS_CO2_PPM = schema.PHYSICS_CO2_PPM


@optional_njit(cache=True)
def non_negative_numba(value):
    if value < 0.0:
        return 0.0
    return value


@optional_njit(cache=True)
def clip_numba(value, minimum, maximum):
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


@optional_njit(cache=True)
def semi_implicit_temperature_update_scalar_numba(
    old_temperature_c,
    capacity_j_k,
    conductances_w_k,
    target_temperatures_c,
    gains_w,
    dt_seconds,
):
    """
    Numba version of thermal semi-implicit scalar update.

    Uses preallocated 1D conductance/target arrays.
    """
    if capacity_j_k <= 0.0:
        return old_temperature_c

    if dt_seconds <= 0.0:
        return old_temperature_c

    numerator = capacity_j_k / dt_seconds * old_temperature_c
    denominator = capacity_j_k / dt_seconds

    for i in range(conductances_w_k.shape[0]):
        h = conductances_w_k[i]

        if h <= 0.0:
            continue

        numerator += h * target_temperatures_c[i]
        denominator += h

    numerator += gains_w

    if denominator <= 0.0:
        return old_temperature_c

    return numerator / denominator


@optional_njit(cache=True)
def co2_gain_kg_s_to_ppm_s_numba(
    co2_gain_kg_s,
    zone_volume_m3,
    air_density_kg_m3=AIR_DENSITY_KG_M3,
):
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


@optional_njit(cache=True)
def semi_implicit_co2_update_scalar_numba(
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
    if zone_volume_m3 <= 0.0:
        return old_co2_ppm

    if dt_seconds <= 0.0:
        return old_co2_ppm

    outdoor_flow_m3_s = non_negative_numba(outdoor_flow_m3_s)
    interzone_flow_m3_s = non_negative_numba(interzone_flow_m3_s)

    outdoor_rate_s = outdoor_flow_m3_s / zone_volume_m3
    interzone_rate_s = interzone_flow_m3_s / zone_volume_m3

    source_ppm_s = co2_gain_kg_s_to_ppm_s_numba(
        co2_gain_kg_s,
        zone_volume_m3,
    )

    numerator = old_co2_ppm / dt_seconds
    numerator += outdoor_rate_s * outdoor_co2_ppm

    if interzone_flow_m3_s > 0.0:
        numerator += interzone_flow_times_source_co2 / zone_volume_m3

    numerator += source_ppm_s

    denominator = 1.0 / dt_seconds
    denominator += outdoor_rate_s
    denominator += interzone_rate_s

    if denominator <= 0.0:
        return clip_numba(old_co2_ppm, min_co2_ppm, max_co2_ppm)

    return clip_numba(numerator / denominator, min_co2_ppm, max_co2_ppm)


@optional_njit(cache=True)
def copy_zone_co2_gains_to_internal_gains_numba(
    zone_state,
    internal_gains,
):
    for zone_i in range(zone_state.shape[0]):
        internal_gains[zone_i, GAIN_ZONE_ID] = zone_i
        internal_gains[zone_i, GAIN_CO2_KG_S] = zone_state[
            zone_i,
            ZONE_CO2_GAIN_KG_S,
        ]

    return True


@optional_njit(cache=True)
def calculate_outdoor_exchange_flow_for_zone_m3_s_numba(
    zone_state,
    zone_i,
):
    outdoor_flow = zone_state[zone_i, ZONE_OUTDOOR_AIRFLOW_M3_S]
    infiltration_flow = zone_state[zone_i, ZONE_INFILTRATION_AIRFLOW_M3_S]

    return non_negative_numba(outdoor_flow) + non_negative_numba(infiltration_flow)


@optional_njit(cache=True)
def calculate_interzone_flow_terms_for_zone_numba(
    zone_state,
    airflow_link_array,
    zone_i,
    link_zone_a_col,
    link_zone_b_col,
    link_current_flow_col,
):
    """
    Generic interzone CO2 term.

    Columns are passed in from airflow_kernels constants to avoid importing
    that module into this numba kernel.
    """
    total_flow = 0.0
    weighted_source = 0.0
    n_zones = zone_state.shape[0]

    for link_i in range(airflow_link_array.shape[0]):
        zone_a = int(airflow_link_array[link_i, link_zone_a_col])
        zone_b = int(airflow_link_array[link_i, link_zone_b_col])

        if zone_a < 0 or zone_a >= n_zones:
            continue

        if zone_b < 0 or zone_b >= n_zones:
            continue

        if zone_a != int(zone_i) and zone_b != int(zone_i):
            continue

        current_flow = non_negative_numba(
            airflow_link_array[link_i, link_current_flow_col]
        )

        if current_flow <= 0.0:
            continue

        if zone_a == int(zone_i):
            source_zone = zone_b
        else:
            source_zone = zone_a

        source_co2 = zone_state[source_zone, ZONE_CO2_PPM]

        total_flow += current_flow
        weighted_source += current_flow * source_co2

    return total_flow, weighted_source


@optional_njit(cache=True)
def step_building_co2_balance_numba(
    zone_state,
    zone_static,
    weather_state,
    internal_gains,
    physics_result,
    dt_minutes,
    airflow_link_array,
    link_zone_a_col,
    link_zone_b_col,
    link_current_flow_col,
    copy_zone_gains_flag=1,
    min_co2_ppm=DEFAULT_MIN_CO2_PPM,
    max_co2_ppm=DEFAULT_MAX_CO2_PPM,
):
    """
    Numba CO2 building balance.

    airflow_link_array can be empty with shape (0, N_LINK_COLS).
    """
    if copy_zone_gains_flag > 0:
        copy_zone_co2_gains_to_internal_gains_numba(
            zone_state,
            internal_gains,
        )

    dt_seconds = dt_minutes * 60.0

    if dt_seconds <= 0.0:
        return False

    outdoor_co2_ppm = weather_state[WEATHER_OUTDOOR_CO2_PPM]

    if outdoor_co2_ppm <= 0.0:
        outdoor_co2_ppm = DEFAULT_OUTDOOR_CO2_PPM

    for zone_i in range(zone_state.shape[0]):
        if int(zone_state[zone_i, ZONE_TYPE]) == ZONE_TYPE_OUTSIDE:
            physics_result[zone_i, PHYSICS_ZONE_ID] = zone_state[zone_i, ZONE_ID]
            physics_result[zone_i, PHYSICS_CO2_PPM] = outdoor_co2_ppm
            continue

        volume_m3 = zone_static[zone_i, ZONE_STATIC_VOLUME_M3]

        if volume_m3 <= 0.0:
            volume_m3 = 1.0

        old_co2_ppm = zone_state[zone_i, ZONE_CO2_PPM]

        outdoor_flow = calculate_outdoor_exchange_flow_for_zone_m3_s_numba(
            zone_state,
            zone_i,
        )

        interzone_flow, interzone_weighted_source = calculate_interzone_flow_terms_for_zone_numba(
            zone_state,
            airflow_link_array,
            zone_i,
            link_zone_a_col,
            link_zone_b_col,
            link_current_flow_col,
        )

        co2_gain_kg_s = internal_gains[zone_i, GAIN_CO2_KG_S]

        new_co2_ppm = semi_implicit_co2_update_scalar_numba(
            old_co2_ppm,
            volume_m3,
            outdoor_co2_ppm,
            outdoor_flow,
            interzone_flow,
            interzone_weighted_source,
            co2_gain_kg_s,
            dt_seconds,
            min_co2_ppm,
            max_co2_ppm,
        )

        zone_state[zone_i, ZONE_CO2_PPM] = new_co2_ppm
        physics_result[zone_i, PHYSICS_ZONE_ID] = zone_state[zone_i, ZONE_ID]
        physics_result[zone_i, PHYSICS_CO2_PPM] = new_co2_ppm

    return True


@optional_njit(cache=True)
def saturation_vapor_pressure_pa_numba(temperature_c):
    return 610.94 * math.exp(
        17.625 * temperature_c / (temperature_c + 243.04)
    )


@optional_njit(cache=True)
def relative_humidity_to_humidity_ratio_kg_kg_numba(
    relative_humidity,
    temperature_c,
    pressure_pa=ATMOSPHERIC_PRESSURE_PA,
):
    rh = clip_numba(relative_humidity, 0.0, 1.0)

    p_ws = saturation_vapor_pressure_pa_numba(temperature_c)
    p_w = rh * p_ws

    if p_w <= 0.0:
        return DEFAULT_MIN_HUMIDITY_RATIO_KG_KG

    if p_w >= pressure_pa:
        p_w = pressure_pa * 0.99

    w = WATER_VAPOR_MOLECULAR_RATIO * p_w / (pressure_pa - p_w)

    return clip_numba(
        w,
        DEFAULT_MIN_HUMIDITY_RATIO_KG_KG,
        DEFAULT_MAX_HUMIDITY_RATIO_KG_KG,
    )


@optional_njit(cache=True)
def humidity_ratio_to_relative_humidity_numba(
    humidity_ratio_kg_kg,
    temperature_c,
    pressure_pa=ATMOSPHERIC_PRESSURE_PA,
):
    w = clip_numba(
        humidity_ratio_kg_kg,
        DEFAULT_MIN_HUMIDITY_RATIO_KG_KG,
        DEFAULT_MAX_HUMIDITY_RATIO_KG_KG,
    )

    p_ws = saturation_vapor_pressure_pa_numba(temperature_c)

    if p_ws <= 0.0:
        return DEFAULT_MIN_RELATIVE_HUMIDITY

    p_w = pressure_pa * w / (WATER_VAPOR_MOLECULAR_RATIO + w)

    return clip_numba(
        p_w / p_ws,
        DEFAULT_MIN_RELATIVE_HUMIDITY,
        DEFAULT_MAX_RELATIVE_HUMIDITY,
    )


@optional_njit(cache=True)
def moisture_gain_kg_s_to_humidity_ratio_s_numba(
    moisture_gain_kg_s,
    zone_volume_m3,
    air_density_kg_m3=AIR_DENSITY_KG_M3,
):
    if zone_volume_m3 <= 0.0:
        return 0.0

    dry_air_mass_kg = air_density_kg_m3 * zone_volume_m3

    if dry_air_mass_kg <= 0.0:
        return 0.0

    return moisture_gain_kg_s / dry_air_mass_kg


@optional_njit(cache=True)
def semi_implicit_humidity_ratio_update_scalar_numba(
    old_humidity_ratio,
    zone_volume_m3,
    outdoor_humidity_ratio,
    outdoor_flow_m3_s,
    interzone_flow_m3_s,
    interzone_flow_times_source_humidity_ratio,
    moisture_gain_kg_s,
    dt_seconds,
):
    if zone_volume_m3 <= 0.0:
        return old_humidity_ratio

    if dt_seconds <= 0.0:
        return old_humidity_ratio

    outdoor_flow_m3_s = non_negative_numba(outdoor_flow_m3_s)
    interzone_flow_m3_s = non_negative_numba(interzone_flow_m3_s)

    outdoor_rate_s = outdoor_flow_m3_s / zone_volume_m3
    interzone_rate_s = interzone_flow_m3_s / zone_volume_m3

    source_w_s = moisture_gain_kg_s_to_humidity_ratio_s_numba(
        moisture_gain_kg_s,
        zone_volume_m3,
    )

    numerator = old_humidity_ratio / dt_seconds
    numerator += outdoor_rate_s * outdoor_humidity_ratio

    if interzone_flow_m3_s > 0.0:
        numerator += interzone_flow_times_source_humidity_ratio / zone_volume_m3

    numerator += source_w_s

    denominator = 1.0 / dt_seconds
    denominator += outdoor_rate_s
    denominator += interzone_rate_s

    if denominator <= 0.0:
        return old_humidity_ratio

    return clip_numba(
        numerator / denominator,
        DEFAULT_MIN_HUMIDITY_RATIO_KG_KG,
        DEFAULT_MAX_HUMIDITY_RATIO_KG_KG,
    )