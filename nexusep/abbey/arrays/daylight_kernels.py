"""
ABBEY array daylight kernels.

Phase 11.5:
    Move simplified daylight and solar-gain calculation into numeric arrays.

This module calculates:
    - outdoor horizontal illuminance from GHI
    - indoor natural daylight illuminance
    - transmitted solar gain through windows/blinds

It updates:
    zone_state[:, ZONE_ILLUMINANCE_LUX]
    zone_state[:, ZONE_SOLAR_GAIN_W]
    physics_result[:, PHYSICS_ILLUMINANCE_LUX]

It may also update:
    internal_gains[:, GAIN_SOLAR_HEAT_W]
    internal_gains[:, GAIN_TOTAL_HEAT_W]

Important:
    - No zone objects.
    - No window objects.
    - No daylight dataclasses.
    - No dicts in timestep-facing functions.
    - No strings.
    - Numeric arrays only.

Schema limitation:
    The current array schema does not yet have explicit window/surface geometry.

Therefore this first array daylight model estimates aperture area from:
    zone floor area
    default window-to-floor ratio
    system_static[:, SYSTEM_STATIC_HAS_WINDOW]

Later:
    replace this with explicit surface/window arrays.
"""

import numpy as np

from nexusep.abbey.arrays import schema


# =============================================================================
# Constants
# =============================================================================

DEFAULT_LUMINOUS_EFFICACY_LM_W = 120.0

DEFAULT_WINDOW_TO_FLOOR_RATIO = 0.18
DEFAULT_VISIBLE_TRANSMITTANCE = 0.60
DEFAULT_SOLAR_HEAT_GAIN_COEFFICIENT = 0.55

DEFAULT_DAYLIGHT_FACTOR = 0.025
DEFAULT_MAX_INDOOR_DAYLIGHT_LUX = 20000.0

DEFAULT_BLIND_CLOSED_DAYLIGHT_MULTIPLIER = 0.10
DEFAULT_BLIND_CLOSED_SOLAR_MULTIPLIER = 0.15

DEFAULT_NO_WINDOW_DAYLIGHT_LUX = 0.0
DEFAULT_NO_SUN_SOLAR_GAIN_W = 0.0


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


def _zone_floor_area_m2(zone_static, zone_i):
    area = zone_static[zone_i, schema.ZONE_STATIC_FLOOR_AREA_M2]

    if area <= 0.0:
        return 10.0

    return area


def _weather_ghi_w_m2(weather_state):
    """
    Read GHI from weather_state.

    Expected schema constant:
        WEATHER_GHI_W_M2

    Fallback:
        if the schema name changes later, update this function only.
    """
    return _non_negative(weather_state[schema.WEATHER_GLOBAL_HORIZONTAL_IRRADIANCE_W_M2])


def _count_window_systems_for_zone(system_state, system_static, zone_i):
    count = 0

    for system_i in range(system_state.shape[0]):
        system_zone_id = int(system_state[system_i, schema.SYSTEM_ZONE_ID])

        if system_zone_id != int(zone_i):
            continue

        if system_static[system_i, schema.SYSTEM_STATIC_HAS_WINDOW] > 0.0:
            count += 1

    return count


# =============================================================================
# Outdoor illuminance
# =============================================================================

def calculate_outdoor_horizontal_illuminance_lux(
    weather_state,
    luminous_efficacy_lm_w=DEFAULT_LUMINOUS_EFFICACY_LM_W,
):
    """
    Convert GHI W/m2 to approximate outdoor horizontal illuminance lux.

        lux = GHI * luminous efficacy

    Typical daylight luminous efficacy is often around 100-130 lm/W.
    """
    ghi = _weather_ghi_w_m2(weather_state)

    return ghi * _non_negative(luminous_efficacy_lm_w)


# =============================================================================
# Window/blind modifiers
# =============================================================================

def calculate_zone_effective_window_area_m2(
    zone_state,
    zone_static,
    system_state,
    system_static,
    zone_i,
    window_to_floor_ratio=DEFAULT_WINDOW_TO_FLOOR_RATIO,
):
    """
    Estimate effective window area for one zone.

    Current schema does not store window geometry, so:
        window_area = floor_area * window_to_floor_ratio

    Only zones with at least one window-capable system receive window area.
    """
    if _zone_is_outside(zone_state, zone_i):
        return 0.0

    n_window_systems = _count_window_systems_for_zone(
        system_state=system_state,
        system_static=system_static,
        zone_i=zone_i,
    )

    if n_window_systems <= 0:
        return 0.0

    floor_area = _zone_floor_area_m2(
        zone_static=zone_static,
        zone_i=zone_i,
    )

    return floor_area * _non_negative(window_to_floor_ratio)


def calculate_zone_blind_closed_fraction(
    system_state,
    system_static,
    zone_i,
):
    """
    Average blind-closed fraction for systems serving one zone.

    If no blinds are available, return 0.
    """
    total = 0.0
    count = 0

    for system_i in range(system_state.shape[0]):
        system_zone_id = int(system_state[system_i, schema.SYSTEM_ZONE_ID])

        if system_zone_id != int(zone_i):
            continue

        if system_static[system_i, schema.SYSTEM_STATIC_HAS_BLINDS] <= 0.0:
            continue

        total += _clip01(
            system_state[
                system_i,
                schema.SYSTEM_BLIND_CLOSED_FRACTION,
            ]
        )
        count += 1

    if count <= 0:
        return 0.0

    return _clip01(total / float(count))


def blind_fraction_to_daylight_multiplier(
    blind_closed_fraction,
    closed_multiplier=DEFAULT_BLIND_CLOSED_DAYLIGHT_MULTIPLIER,
):
    """
    Convert blind closed fraction to daylight multiplier.

    0 closed:
        multiplier = 1

    1 closed:
        multiplier = closed_multiplier
    """
    f = _clip01(blind_closed_fraction)
    closed_multiplier = _clip01(closed_multiplier)

    return (1.0 - f) + f * closed_multiplier


def blind_fraction_to_solar_multiplier(
    blind_closed_fraction,
    closed_multiplier=DEFAULT_BLIND_CLOSED_SOLAR_MULTIPLIER,
):
    """
    Convert blind closed fraction to solar-gain multiplier.
    """
    f = _clip01(blind_closed_fraction)
    closed_multiplier = _clip01(closed_multiplier)

    return (1.0 - f) + f * closed_multiplier


# =============================================================================
# Core daylight and solar calculations
# =============================================================================

def calculate_zone_daylight_lux(
    zone_state,
    zone_static,
    system_state,
    system_static,
    weather_state,
    zone_i,
    luminous_efficacy_lm_w=DEFAULT_LUMINOUS_EFFICACY_LM_W,
    window_to_floor_ratio=DEFAULT_WINDOW_TO_FLOOR_RATIO,
    visible_transmittance=DEFAULT_VISIBLE_TRANSMITTANCE,
    daylight_factor=DEFAULT_DAYLIGHT_FACTOR,
    max_indoor_daylight_lux=DEFAULT_MAX_INDOOR_DAYLIGHT_LUX,
):
    """
    Calculate indoor natural daylight for one zone.
    """
    if _zone_is_outside(zone_state, zone_i):
        return DEFAULT_NO_WINDOW_DAYLIGHT_LUX

    window_area = calculate_zone_effective_window_area_m2(
        zone_state=zone_state,
        zone_static=zone_static,
        system_state=system_state,
        system_static=system_static,
        zone_i=zone_i,
        window_to_floor_ratio=window_to_floor_ratio,
    )

    if window_area <= 0.0:
        return DEFAULT_NO_WINDOW_DAYLIGHT_LUX

    floor_area = _zone_floor_area_m2(
        zone_static=zone_static,
        zone_i=zone_i,
    )

    outdoor_lux = calculate_outdoor_horizontal_illuminance_lux(
        weather_state=weather_state,
        luminous_efficacy_lm_w=luminous_efficacy_lm_w,
    )

    if outdoor_lux <= 0.0:
        return 0.0

    blind_fraction = calculate_zone_blind_closed_fraction(
        system_state=system_state,
        system_static=system_static,
        zone_i=zone_i,
    )

    blind_multiplier = blind_fraction_to_daylight_multiplier(
        blind_closed_fraction=blind_fraction,
    )

    aperture_ratio = window_area / floor_area

    indoor_lux = (
        outdoor_lux
        * daylight_factor
        * visible_transmittance
        * blind_multiplier
        * (aperture_ratio / max(window_to_floor_ratio, 1.0e-9))
    )

    return _clip(
        indoor_lux,
        0.0,
        max_indoor_daylight_lux,
    )


def calculate_zone_solar_gain_w(
    zone_state,
    zone_static,
    system_state,
    system_static,
    weather_state,
    zone_i,
    window_to_floor_ratio=DEFAULT_WINDOW_TO_FLOOR_RATIO,
    solar_heat_gain_coefficient=DEFAULT_SOLAR_HEAT_GAIN_COEFFICIENT,
):
    """
    Calculate transmitted solar heat gain for one zone.

    Current approximation:
        solar_gain = GHI * window_area * SHGC * blind_multiplier
    """
    if _zone_is_outside(zone_state, zone_i):
        return DEFAULT_NO_SUN_SOLAR_GAIN_W

    ghi = _weather_ghi_w_m2(weather_state)

    if ghi <= 0.0:
        return DEFAULT_NO_SUN_SOLAR_GAIN_W

    window_area = calculate_zone_effective_window_area_m2(
        zone_state=zone_state,
        zone_static=zone_static,
        system_state=system_state,
        system_static=system_static,
        zone_i=zone_i,
        window_to_floor_ratio=window_to_floor_ratio,
    )

    if window_area <= 0.0:
        return DEFAULT_NO_SUN_SOLAR_GAIN_W

    blind_fraction = calculate_zone_blind_closed_fraction(
        system_state=system_state,
        system_static=system_static,
        zone_i=zone_i,
    )

    blind_multiplier = blind_fraction_to_solar_multiplier(
        blind_closed_fraction=blind_fraction,
    )

    solar_gain = (
        ghi
        * window_area
        * _non_negative(solar_heat_gain_coefficient)
        * blind_multiplier
    )

    return _non_negative(solar_gain)


# =============================================================================
# Write helpers
# =============================================================================

def write_daylight_result_to_zone_state(
    zone_state,
    physics_result,
    zone_i,
    indoor_daylight_lux,
    solar_gain_w,
):
    """
    Write daylight result to zone_state and physics_result.
    """
    zone_state[zone_i, schema.ZONE_ILLUMINANCE_LUX] = indoor_daylight_lux
    zone_state[zone_i, schema.ZONE_SOLAR_GAIN_W] = solar_gain_w

    if physics_result is not None:
        physics_result[zone_i, schema.PHYSICS_ZONE_ID] = zone_state[
            zone_i,
            schema.ZONE_ID,
        ]
        physics_result[zone_i, schema.PHYSICS_ILLUMINANCE_LUX] = indoor_daylight_lux

    return True


def write_solar_gain_to_internal_gains(
    zone_state,
    internal_gains,
    zone_i,
    solar_gain_w,
):
    """
    Write solar gain to internal_gains.

    Also refreshes total heat gain as:
        people + lighting + appliance + solar
    """
    if internal_gains is None:
        return True

    internal_gains[zone_i, schema.GAIN_ZONE_ID] = zone_i
    internal_gains[zone_i, schema.GAIN_SOLAR_HEAT_W] = solar_gain_w

    people = internal_gains[zone_i, schema.GAIN_PEOPLE_HEAT_W]
    lighting = internal_gains[zone_i, schema.GAIN_LIGHTING_HEAT_W]
    appliance = internal_gains[zone_i, schema.GAIN_APPLIANCE_HEAT_W]

    internal_gains[zone_i, schema.GAIN_TOTAL_HEAT_W] = (
        people
        + lighting
        + appliance
        + solar_gain_w
    )

    return True


# =============================================================================
# Zone daylight step
# =============================================================================

def step_zone_daylight(
    zone_state,
    zone_static,
    system_state,
    system_static,
    weather_state,
    physics_result,
    zone_i,
    internal_gains=None,
    luminous_efficacy_lm_w=DEFAULT_LUMINOUS_EFFICACY_LM_W,
    window_to_floor_ratio=DEFAULT_WINDOW_TO_FLOOR_RATIO,
    visible_transmittance=DEFAULT_VISIBLE_TRANSMITTANCE,
    daylight_factor=DEFAULT_DAYLIGHT_FACTOR,
    solar_heat_gain_coefficient=DEFAULT_SOLAR_HEAT_GAIN_COEFFICIENT,
):
    """
    Calculate daylight and solar gain for one zone.
    """
    indoor_daylight_lux = calculate_zone_daylight_lux(
        zone_state=zone_state,
        zone_static=zone_static,
        system_state=system_state,
        system_static=system_static,
        weather_state=weather_state,
        zone_i=zone_i,
        luminous_efficacy_lm_w=luminous_efficacy_lm_w,
        window_to_floor_ratio=window_to_floor_ratio,
        visible_transmittance=visible_transmittance,
        daylight_factor=daylight_factor,
    )

    solar_gain_w = calculate_zone_solar_gain_w(
        zone_state=zone_state,
        zone_static=zone_static,
        system_state=system_state,
        system_static=system_static,
        weather_state=weather_state,
        zone_i=zone_i,
        window_to_floor_ratio=window_to_floor_ratio,
        solar_heat_gain_coefficient=solar_heat_gain_coefficient,
    )

    write_daylight_result_to_zone_state(
        zone_state=zone_state,
        physics_result=physics_result,
        zone_i=zone_i,
        indoor_daylight_lux=indoor_daylight_lux,
        solar_gain_w=solar_gain_w,
    )

    write_solar_gain_to_internal_gains(
        zone_state=zone_state,
        internal_gains=internal_gains,
        zone_i=zone_i,
        solar_gain_w=solar_gain_w,
    )

    return True


# =============================================================================
# Building daylight step
# =============================================================================

def step_building_daylight(
    zone_state,
    zone_static,
    system_state,
    system_static,
    weather_state,
    physics_result,
    internal_gains=None,
    luminous_efficacy_lm_w=DEFAULT_LUMINOUS_EFFICACY_LM_W,
    window_to_floor_ratio=DEFAULT_WINDOW_TO_FLOOR_RATIO,
    visible_transmittance=DEFAULT_VISIBLE_TRANSMITTANCE,
    daylight_factor=DEFAULT_DAYLIGHT_FACTOR,
    solar_heat_gain_coefficient=DEFAULT_SOLAR_HEAT_GAIN_COEFFICIENT,
):
    """
    Phase 11.5 daylight timestep.

    Mutates:
        zone_state
        physics_result
        internal_gains, if provided

    Returns:
        zone_state, physics_result
    """
    for zone_i in range(zone_state.shape[0]):
        step_zone_daylight(
            zone_state=zone_state,
            zone_static=zone_static,
            system_state=system_state,
            system_static=system_static,
            weather_state=weather_state,
            physics_result=physics_result,
            zone_i=zone_i,
            internal_gains=internal_gains,
            luminous_efficacy_lm_w=luminous_efficacy_lm_w,
            window_to_floor_ratio=window_to_floor_ratio,
            visible_transmittance=visible_transmittance,
            daylight_factor=daylight_factor,
            solar_heat_gain_coefficient=solar_heat_gain_coefficient,
        )

    return zone_state, physics_result


def run_daylight_step(
    zone_state,
    zone_static,
    system_state,
    system_static,
    weather_state,
    physics_result,
    internal_gains=None,
):
    """
    Public alias for future physics orchestration.
    """
    return step_building_daylight(
        zone_state=zone_state,
        zone_static=zone_static,
        system_state=system_state,
        system_static=system_static,
        weather_state=weather_state,
        physics_result=physics_result,
        internal_gains=internal_gains,
    )