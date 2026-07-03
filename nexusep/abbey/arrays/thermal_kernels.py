"""
ABBEY array thermal kernels.

Phase 11.1:
    Move the thermal timestep calculation into numeric arrays.

Model:
    Semi-implicit reduced RC model.

Current array-schema limitation:
    The old object thermal model has:
        - air temperature
        - mass temperature

    The current array schema has:
        - ZONE_AIR_TEMPERATURE_C
        - ZONE_MEAN_RADIANT_TEMPERATURE_C

    For now:
        ZONE_MEAN_RADIANT_TEMPERATURE_C is used as the mass-node proxy.

Later:
    Add an explicit ZONE_MASS_TEMPERATURE_C column if needed.

Important:
    - No zone objects.
    - No building objects.
    - No dicts in timestep-facing kernels.
    - No strings.
    - Numeric arrays only.
"""

import numpy as np

from nexusep.abbey.arrays import schema


# =============================================================================
# Thermal constants
# =============================================================================

AIR_DENSITY_KG_M3 = 1.2
AIR_SPECIFIC_HEAT_J_KG_K = 1005.0

DEFAULT_AIR_MASS_COUPLING_W_M2K = 3.45
DEFAULT_EFFECTIVE_MASS_AREA_FACTOR = 2.5
DEFAULT_MIN_AIR_MASS_CONDUCTANCE_W_K = 0.1

DEFAULT_PEOPLE_CONVECTIVE_FRACTION = 0.50
DEFAULT_APPLIANCE_CONVECTIVE_FRACTION = 0.70
DEFAULT_LIGHTING_CONVECTIVE_FRACTION = 0.60
DEFAULT_SOLAR_CONVECTIVE_FRACTION = 0.10
DEFAULT_HVAC_CONVECTIVE_FRACTION = 1.00

DEFAULT_AIR_CAPACITY_MIN_J_K = 1000.0
DEFAULT_MASS_CAPACITY_MIN_J_K = 10000.0


# =============================================================================
# Small helpers
# =============================================================================

def _max_float(value, minimum):
    value = float(value)

    if value < minimum:
        return float(minimum)

    return value


def _non_negative(value):
    value = float(value)

    if value < 0.0:
        return 0.0

    return value


def _zone_is_outside(zone_state, zone_i):
    return int(zone_state[zone_i, schema.ZONE_TYPE]) == schema.ZONE_TYPE_OUTSIDE


def _zone_id_valid(zone_i):
    return int(zone_i) != schema.MISSING_ID


# =============================================================================
# Core semi-implicit update
# =============================================================================

def semi_implicit_temperature_update_scalar(
    capacity_j_k,
    old_temperature_c,
    target_temperatures_c,
    target_conductances_w_k,
    n_targets,
    gain_w,
    dt_seconds,
):
    """
    Stable backward-Euler-style scalar temperature update.

        T_next =
            (C/dt * T_old + sum(H_i * T_i) + gain)
            /
            (C/dt + sum(H_i))

    gain_w:
        positive = heat added
        negative = heat removed
    """
    capacity_j_k = float(capacity_j_k)
    old_temperature_c = float(old_temperature_c)
    gain_w = float(gain_w)
    dt_seconds = float(dt_seconds)

    if capacity_j_k <= 0.0:
        raise ValueError("capacity_j_k must be positive.")

    if dt_seconds <= 0.0:
        raise ValueError("dt_seconds must be positive.")

    c_over_dt = capacity_j_k / dt_seconds

    numerator = c_over_dt * old_temperature_c + gain_w
    denominator = c_over_dt

    for i in range(n_targets):
        h_w_k = float(target_conductances_w_k[i])
        target_t = float(target_temperatures_c[i])

        if h_w_k < 0.0:
            raise ValueError("thermal conductance cannot be negative.")

        numerator += h_w_k * target_t
        denominator += h_w_k

    if denominator <= 0.0:
        raise ValueError("thermal update denominator became non-positive.")

    return numerator / denominator


# =============================================================================
# Derived thermal properties from arrays
# =============================================================================

def zone_air_capacity_j_k(zone_static, zone_i):
    """
    Calculate air-node heat capacity from zone volume.
    """
    volume_m3 = zone_static[zone_i, schema.ZONE_STATIC_VOLUME_M3]

    if volume_m3 <= 0.0:
        floor_area = zone_static[zone_i, schema.ZONE_STATIC_FLOOR_AREA_M2]
        height = zone_static[zone_i, schema.ZONE_STATIC_HEIGHT_M]

        if height <= 0.0:
            height = 2.7

        volume_m3 = floor_area * height

    c_air = volume_m3 * AIR_DENSITY_KG_M3 * AIR_SPECIFIC_HEAT_J_KG_K

    return _max_float(c_air, DEFAULT_AIR_CAPACITY_MIN_J_K)


def zone_mass_capacity_j_k(zone_static, zone_i):
    """
    Get mass-node heat capacity.

    Current schema stores one heat-capacity column. Treat it as mass capacity.
    """
    c_mass = zone_static[zone_i, schema.ZONE_STATIC_HEAT_CAPACITY_J_K]

    return _max_float(c_mass, DEFAULT_MASS_CAPACITY_MIN_J_K)


def zone_air_mass_conductance_w_k(zone_static, zone_i):
    """
    Estimate air-mass coupling.

    Old object model used an effective mass area. Here we estimate it from
    floor area because the current array schema does not store wall areas.
    """
    floor_area = zone_static[zone_i, schema.ZONE_STATIC_FLOOR_AREA_M2]

    if floor_area <= 0.0:
        floor_area = 10.0

    effective_mass_area = floor_area * DEFAULT_EFFECTIVE_MASS_AREA_FACTOR

    h_air_mass = DEFAULT_AIR_MASS_COUPLING_W_M2K * effective_mass_area

    return _max_float(h_air_mass, DEFAULT_MIN_AIR_MASS_CONDUCTANCE_W_K)


def zone_envelope_conductance_w_k(zone_static, zone_i):
    """
    Envelope UA to outdoor.
    """
    return _non_negative(zone_static[zone_i, schema.ZONE_STATIC_UA_ENVELOPE_W_K])


def zone_internal_conductance_w_k(zone_static, zone_i):
    """
    Internal UA is kept available for later interzone links.

    In Phase 11.1 there is no explicit interzone-link array, so this is not
    used directly by the one-zone update.
    """
    return _non_negative(zone_static[zone_i, schema.ZONE_STATIC_UA_INTERNAL_W_K])


# =============================================================================
# Ventilation conductance
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


def calculate_window_airflow_for_zone_m3_s(
    system_state,
    system_static,
    zone_i,
):
    """
    Approximate window airflow from window open fraction.

    This uses:
        SYSTEM_STATIC_MAX_WINDOW_FLOW_M3_S
        *
        SYSTEM_WINDOW_OPEN_FRACTION

    Proper airflow network comes later.
    """
    total = 0.0

    for system_i in range(system_state.shape[0]):
        system_zone_id = int(system_state[system_i, schema.SYSTEM_ZONE_ID])

        if system_zone_id != int(zone_i):
            continue

        has_window = (
            system_static[system_i, schema.SYSTEM_STATIC_HAS_WINDOW]
            > 0.0
        )

        if not has_window:
            continue

        fraction = system_state[
            system_i,
            schema.SYSTEM_WINDOW_OPEN_FRACTION,
        ]
        max_flow = system_static[
            system_i,
            schema.SYSTEM_STATIC_MAX_WINDOW_FLOW_M3_S,
        ]

        total += _non_negative(fraction) * _non_negative(max_flow)

    return total


def calculate_total_outdoor_airflow_for_zone_m3_s(
    zone_state,
    system_state,
    system_static,
    zone_i,
):
    """
    Outdoor exchange flow used by the thermal kernel.

    Includes:
        - zone outdoor airflow
        - infiltration airflow
        - mechanical ventilation
        - simple window flow approximation
    """
    outdoor_flow = _non_negative(
        zone_state[zone_i, schema.ZONE_OUTDOOR_AIRFLOW_M3_S]
    )
    infiltration_flow = _non_negative(
        zone_state[zone_i, schema.ZONE_INFILTRATION_AIRFLOW_M3_S]
    )
    mechanical_flow = calculate_mechanical_ventilation_flow_for_zone_m3_s(
        system_state=system_state,
        zone_i=zone_i,
    )
    window_flow = calculate_window_airflow_for_zone_m3_s(
        system_state=system_state,
        system_static=system_static,
        zone_i=zone_i,
    )

    return outdoor_flow + infiltration_flow + mechanical_flow + window_flow


def airflow_m3_s_to_thermal_conductance_w_k(flow_m3_s):
    """
    H_vent = rho * cp * Vdot
    """
    return _non_negative(flow_m3_s) * AIR_DENSITY_KG_M3 * AIR_SPECIFIC_HEAT_J_KG_K


# =============================================================================
# HVAC and gain collection
# =============================================================================

def calculate_hvac_gain_for_zone_w(system_state, zone_i):
    """
    Positive = heating into zone.
    Negative = cooling removal from zone.
    """
    total = 0.0

    for system_i in range(system_state.shape[0]):
        system_zone_id = int(system_state[system_i, schema.SYSTEM_ZONE_ID])

        if system_zone_id != int(zone_i):
            continue

        heating_power = _non_negative(
            system_state[system_i, schema.SYSTEM_HEATING_POWER_W]
        )
        cooling_power = _non_negative(
            system_state[system_i, schema.SYSTEM_COOLING_POWER_W]
        )

        total += heating_power
        total -= cooling_power

    return total


def calculate_hvac_heating_power_for_zone_w(system_state, zone_i):
    total = 0.0

    for system_i in range(system_state.shape[0]):
        if int(system_state[system_i, schema.SYSTEM_ZONE_ID]) == int(zone_i):
            total += _non_negative(
                system_state[system_i, schema.SYSTEM_HEATING_POWER_W]
            )

    return total


def calculate_hvac_cooling_power_for_zone_w(system_state, zone_i):
    total = 0.0

    for system_i in range(system_state.shape[0]):
        if int(system_state[system_i, schema.SYSTEM_ZONE_ID]) == int(zone_i):
            total += _non_negative(
                system_state[system_i, schema.SYSTEM_COOLING_POWER_W]
            )

    return total


def copy_zone_gains_to_internal_gains(
    zone_state,
    internal_gains,
):
    """
    Make internal_gains consistent with current zone_state gain columns.

    This is useful because previous phases write some gains into zone_state
    and some into internal_gains.
    """
    if internal_gains is None:
        return True

    for zone_i in range(zone_state.shape[0]):
        internal_gains[zone_i, schema.GAIN_ZONE_ID] = zone_i

        people = zone_state[zone_i, schema.ZONE_PEOPLE_GAIN_W]
        lighting = zone_state[zone_i, schema.ZONE_LIGHTING_GAIN_W]
        appliance = zone_state[zone_i, schema.ZONE_APPLIANCE_GAIN_W]
        solar = zone_state[zone_i, schema.ZONE_SOLAR_GAIN_W]

        internal_gains[zone_i, schema.GAIN_PEOPLE_HEAT_W] = people
        internal_gains[zone_i, schema.GAIN_LIGHTING_HEAT_W] = lighting
        internal_gains[zone_i, schema.GAIN_APPLIANCE_HEAT_W] = appliance
        internal_gains[zone_i, schema.GAIN_SOLAR_HEAT_W] = solar
        internal_gains[zone_i, schema.GAIN_TOTAL_HEAT_W] = (
            people + lighting + appliance + solar
        )

    return True


def get_zone_gain_components_w(
    zone_state,
    internal_gains,
    zone_i,
):
    """
    Read thermal gains for one zone.

    Preference:
        internal_gains if provided

    Fallback:
        zone_state gain columns
    """
    if internal_gains is not None:
        people = internal_gains[zone_i, schema.GAIN_PEOPLE_HEAT_W]
        lighting = internal_gains[zone_i, schema.GAIN_LIGHTING_HEAT_W]
        appliance = internal_gains[zone_i, schema.GAIN_APPLIANCE_HEAT_W]
        solar = internal_gains[zone_i, schema.GAIN_SOLAR_HEAT_W]
    else:
        people = zone_state[zone_i, schema.ZONE_PEOPLE_GAIN_W]
        lighting = zone_state[zone_i, schema.ZONE_LIGHTING_GAIN_W]
        appliance = zone_state[zone_i, schema.ZONE_APPLIANCE_GAIN_W]
        solar = zone_state[zone_i, schema.ZONE_SOLAR_GAIN_W]

    return people, lighting, appliance, solar


def split_zone_gains_for_thermal(
    zone_state,
    system_state,
    internal_gains,
    zone_i,
):
    """
    Split zone gains into convective and radiative/mass-node gains.

    Returns:
        convective_gain_w, radiative_gain_w, hvac_gain_w
    """
    people, lighting, appliance, solar = get_zone_gain_components_w(
        zone_state=zone_state,
        internal_gains=internal_gains,
        zone_i=zone_i,
    )

    hvac_gain = calculate_hvac_gain_for_zone_w(
        system_state=system_state,
        zone_i=zone_i,
    )

    people_conv = DEFAULT_PEOPLE_CONVECTIVE_FRACTION * people
    people_rad = people - people_conv

    appliance_conv = DEFAULT_APPLIANCE_CONVECTIVE_FRACTION * appliance
    appliance_rad = appliance - appliance_conv

    lighting_conv = DEFAULT_LIGHTING_CONVECTIVE_FRACTION * lighting
    lighting_rad = lighting - lighting_conv

    solar_conv = DEFAULT_SOLAR_CONVECTIVE_FRACTION * solar
    solar_rad = solar - solar_conv

    hvac_conv = DEFAULT_HVAC_CONVECTIVE_FRACTION * hvac_gain
    hvac_rad = hvac_gain - hvac_conv

    convective_gain = (
        people_conv
        + appliance_conv
        + lighting_conv
        + solar_conv
        + hvac_conv
    )

    radiative_gain = (
        people_rad
        + appliance_rad
        + lighting_rad
        + solar_rad
        + hvac_rad
    )

    return convective_gain, radiative_gain, hvac_gain


# =============================================================================
# Physics result helpers
# =============================================================================

def initialize_physics_result_from_zone_state(
    zone_state,
    physics_result,
):
    """
    Copy current zone environmental states into physics_result.
    """
    for zone_i in range(zone_state.shape[0]):
        physics_result[zone_i, schema.PHYSICS_ZONE_ID] = zone_state[
            zone_i,
            schema.ZONE_ID,
        ]
        physics_result[zone_i, schema.PHYSICS_AIR_TEMPERATURE_C] = zone_state[
            zone_i,
            schema.ZONE_AIR_TEMPERATURE_C,
        ]
        physics_result[
            zone_i,
            schema.PHYSICS_MEAN_RADIANT_TEMPERATURE_C,
        ] = zone_state[
            zone_i,
            schema.ZONE_MEAN_RADIANT_TEMPERATURE_C,
        ]
        physics_result[zone_i, schema.PHYSICS_RELATIVE_HUMIDITY] = zone_state[
            zone_i,
            schema.ZONE_RELATIVE_HUMIDITY,
        ]
        physics_result[zone_i, schema.PHYSICS_CO2_PPM] = zone_state[
            zone_i,
            schema.ZONE_CO2_PPM,
        ]
        physics_result[zone_i, schema.PHYSICS_ILLUMINANCE_LUX] = zone_state[
            zone_i,
            schema.ZONE_ILLUMINANCE_LUX,
        ]
        physics_result[zone_i, schema.PHYSICS_NOISE_DB] = zone_state[
            zone_i,
            schema.ZONE_NOISE_DB,
        ]

        physics_result[zone_i, schema.PHYSICS_HEATING_DEMAND_W] = 0.0
        physics_result[zone_i, schema.PHYSICS_COOLING_DEMAND_W] = 0.0
        physics_result[zone_i, schema.PHYSICS_VENTILATION_FLOW_M3_S] = 0.0

    return physics_result


def write_zone_thermal_result(
    zone_state,
    physics_result,
    system_state,
    zone_i,
    new_air_temperature_c,
    new_mass_temperature_c,
    ventilation_flow_m3_s,
):
    """
    Write thermal result back to zone_state and physics_result.
    """
    zone_state[zone_i, schema.ZONE_AIR_TEMPERATURE_C] = new_air_temperature_c
    zone_state[
        zone_i,
        schema.ZONE_MEAN_RADIANT_TEMPERATURE_C,
    ] = new_mass_temperature_c

    physics_result[zone_i, schema.PHYSICS_ZONE_ID] = zone_state[
        zone_i,
        schema.ZONE_ID,
    ]
    physics_result[
        zone_i,
        schema.PHYSICS_AIR_TEMPERATURE_C,
    ] = new_air_temperature_c
    physics_result[
        zone_i,
        schema.PHYSICS_MEAN_RADIANT_TEMPERATURE_C,
    ] = new_mass_temperature_c

    physics_result[zone_i, schema.PHYSICS_RELATIVE_HUMIDITY] = zone_state[
        zone_i,
        schema.ZONE_RELATIVE_HUMIDITY,
    ]
    physics_result[zone_i, schema.PHYSICS_CO2_PPM] = zone_state[
        zone_i,
        schema.ZONE_CO2_PPM,
    ]
    physics_result[zone_i, schema.PHYSICS_ILLUMINANCE_LUX] = zone_state[
        zone_i,
        schema.ZONE_ILLUMINANCE_LUX,
    ]
    physics_result[zone_i, schema.PHYSICS_NOISE_DB] = zone_state[
        zone_i,
        schema.ZONE_NOISE_DB,
    ]

    physics_result[
        zone_i,
        schema.PHYSICS_HEATING_DEMAND_W,
    ] = calculate_hvac_heating_power_for_zone_w(
        system_state=system_state,
        zone_i=zone_i,
    )

    physics_result[
        zone_i,
        schema.PHYSICS_COOLING_DEMAND_W,
    ] = calculate_hvac_cooling_power_for_zone_w(
        system_state=system_state,
        zone_i=zone_i,
    )

    physics_result[
        zone_i,
        schema.PHYSICS_VENTILATION_FLOW_M3_S,
    ] = ventilation_flow_m3_s

    return True


# =============================================================================
# Main zone thermal step
# =============================================================================

def step_zone_thermal_semi_implicit(
    zone_state,
    zone_static,
    system_state,
    system_static,
    weather_state,
    internal_gains,
    physics_result,
    zone_i,
    dt_minutes,
):
    """
    Update one zone thermal state.

    Air node receives:
        - coupling to mass/MRT proxy
        - envelope exchange with outside
        - ventilation exchange with outside
        - convective gains

    Mass/MRT node receives:
        - coupling to new air temperature
        - radiative gains
    """
    if _zone_is_outside(zone_state, zone_i):
        return True

    dt_seconds = float(dt_minutes) * 60.0

    if dt_seconds <= 0.0:
        raise ValueError("dt_minutes must be positive.")

    outdoor_temperature_c = weather_state[
        schema.WEATHER_OUTDOOR_TEMPERATURE_C
    ]

    old_air_temperature_c = zone_state[
        zone_i,
        schema.ZONE_AIR_TEMPERATURE_C,
    ]
    old_mass_temperature_c = zone_state[
        zone_i,
        schema.ZONE_MEAN_RADIANT_TEMPERATURE_C,
    ]

    # Safety fallback.
    if old_mass_temperature_c == 0.0:
        old_mass_temperature_c = old_air_temperature_c

    c_air = zone_air_capacity_j_k(
        zone_static=zone_static,
        zone_i=zone_i,
    )
    c_mass = zone_mass_capacity_j_k(
        zone_static=zone_static,
        zone_i=zone_i,
    )

    h_air_mass = zone_air_mass_conductance_w_k(
        zone_static=zone_static,
        zone_i=zone_i,
    )
    h_envelope = zone_envelope_conductance_w_k(
        zone_static=zone_static,
        zone_i=zone_i,
    )

    ventilation_flow_m3_s = calculate_total_outdoor_airflow_for_zone_m3_s(
        zone_state=zone_state,
        system_state=system_state,
        system_static=system_static,
        zone_i=zone_i,
    )

    h_ventilation = airflow_m3_s_to_thermal_conductance_w_k(
        flow_m3_s=ventilation_flow_m3_s,
    )

    convective_gain_w, radiative_gain_w, _hvac_gain_w = split_zone_gains_for_thermal(
        zone_state=zone_state,
        system_state=system_state,
        internal_gains=internal_gains,
        zone_i=zone_i,
    )

    # Air node targets:
    #   0. old mass/MRT node
    #   1. outdoor envelope
    #   2. outdoor ventilation
    target_temperatures = np.zeros((3,), dtype=np.float64)
    target_conductances = np.zeros((3,), dtype=np.float64)

    target_temperatures[0] = old_mass_temperature_c
    target_conductances[0] = h_air_mass

    target_temperatures[1] = outdoor_temperature_c
    target_conductances[1] = h_envelope

    target_temperatures[2] = outdoor_temperature_c
    target_conductances[2] = h_ventilation

    new_air_temperature_c = semi_implicit_temperature_update_scalar(
        capacity_j_k=c_air,
        old_temperature_c=old_air_temperature_c,
        target_temperatures_c=target_temperatures,
        target_conductances_w_k=target_conductances,
        n_targets=3,
        gain_w=convective_gain_w,
        dt_seconds=dt_seconds,
    )

    # Mass/MRT proxy node target:
    #   0. new air node
    mass_target_temperatures = np.zeros((1,), dtype=np.float64)
    mass_target_conductances = np.zeros((1,), dtype=np.float64)

    mass_target_temperatures[0] = new_air_temperature_c
    mass_target_conductances[0] = h_air_mass

    new_mass_temperature_c = semi_implicit_temperature_update_scalar(
        capacity_j_k=c_mass,
        old_temperature_c=old_mass_temperature_c,
        target_temperatures_c=mass_target_temperatures,
        target_conductances_w_k=mass_target_conductances,
        n_targets=1,
        gain_w=radiative_gain_w,
        dt_seconds=dt_seconds,
    )

    write_zone_thermal_result(
        zone_state=zone_state,
        physics_result=physics_result,
        system_state=system_state,
        zone_i=zone_i,
        new_air_temperature_c=new_air_temperature_c,
        new_mass_temperature_c=new_mass_temperature_c,
        ventilation_flow_m3_s=ventilation_flow_m3_s,
    )

    return True


# =============================================================================
# Building thermal step
# =============================================================================

def step_building_thermal_semi_implicit(
    zone_state,
    zone_static,
    system_state,
    system_static,
    weather_state,
    internal_gains,
    physics_result,
    dt_minutes,
    copy_zone_gains=True,
):
    """
    Update all zone thermal states for one timestep.

    This is the Phase 11.1 array thermal timestep.

    Mutates:
        zone_state
        physics_result
        internal_gains, only if copy_zone_gains=True and internal_gains is not None

    Returns:
        zone_state, physics_result
    """
    if copy_zone_gains:
        copy_zone_gains_to_internal_gains(
            zone_state=zone_state,
            internal_gains=internal_gains,
        )

    initialize_physics_result_from_zone_state(
        zone_state=zone_state,
        physics_result=physics_result,
    )

    for zone_i in range(zone_state.shape[0]):
        step_zone_thermal_semi_implicit(
            zone_state=zone_state,
            zone_static=zone_static,
            system_state=system_state,
            system_static=system_static,
            weather_state=weather_state,
            internal_gains=internal_gains,
            physics_result=physics_result,
            zone_i=zone_i,
            dt_minutes=dt_minutes,
        )

    return zone_state, physics_result

def step_building_thermal_semi_implicit_fast(
    zone_state,
    zone_static,
    system_state,
    system_static,
    weather_state,
    internal_gains,
    physics_result,
    dt_minutes,
    copy_zone_gains=True,
):
    """
    Fast thermal timestep.

    Same reduced RC model as step_building_thermal_semi_implicit, but avoids:
        - per-zone np.zeros allocations
        - repeated helper calls
        - repeated loops over systems for heating/cooling/window/ventilation

    Mutates:
        zone_state
        physics_result
        internal_gains, only if copy_zone_gains=True
    """
    dt_seconds = float(dt_minutes) * 60.0

    if dt_seconds <= 0.0:
        raise ValueError("dt_minutes must be positive.")

    n_zones = zone_state.shape[0]
    n_systems = system_state.shape[0]

    outdoor_temperature_c = weather_state[
        schema.WEATHER_OUTDOOR_TEMPERATURE_C
    ]

    # -------------------------------------------------------------------------
    # Copy zone gains to internal_gains.
    # Inline version of copy_zone_gains_to_internal_gains.
    # -------------------------------------------------------------------------

    if copy_zone_gains and internal_gains is not None:
        for zone_i in range(n_zones):
            people = zone_state[zone_i, schema.ZONE_PEOPLE_GAIN_W]
            lighting = zone_state[zone_i, schema.ZONE_LIGHTING_GAIN_W]
            appliance = zone_state[zone_i, schema.ZONE_APPLIANCE_GAIN_W]
            solar = zone_state[zone_i, schema.ZONE_SOLAR_GAIN_W]

            internal_gains[zone_i, schema.GAIN_ZONE_ID] = zone_i
            internal_gains[zone_i, schema.GAIN_PEOPLE_HEAT_W] = people
            internal_gains[zone_i, schema.GAIN_LIGHTING_HEAT_W] = lighting
            internal_gains[zone_i, schema.GAIN_APPLIANCE_HEAT_W] = appliance
            internal_gains[zone_i, schema.GAIN_SOLAR_HEAT_W] = solar
            internal_gains[zone_i, schema.GAIN_TOTAL_HEAT_W] = (
                people + lighting + appliance + solar
            )

    # -------------------------------------------------------------------------
    # Zone loop.
    # -------------------------------------------------------------------------

    for zone_i in range(n_zones):
        # ---------------------------------------------------------------------
        # Initialize physics result from current zone state.
        # This preserves the behavior of initialize_physics_result_from_zone_state.
        # ---------------------------------------------------------------------

        physics_result[zone_i, schema.PHYSICS_ZONE_ID] = zone_state[
            zone_i,
            schema.ZONE_ID,
        ]
        physics_result[zone_i, schema.PHYSICS_AIR_TEMPERATURE_C] = zone_state[
            zone_i,
            schema.ZONE_AIR_TEMPERATURE_C,
        ]
        physics_result[
            zone_i,
            schema.PHYSICS_MEAN_RADIANT_TEMPERATURE_C,
        ] = zone_state[
            zone_i,
            schema.ZONE_MEAN_RADIANT_TEMPERATURE_C,
        ]
        physics_result[zone_i, schema.PHYSICS_RELATIVE_HUMIDITY] = zone_state[
            zone_i,
            schema.ZONE_RELATIVE_HUMIDITY,
        ]
        physics_result[zone_i, schema.PHYSICS_CO2_PPM] = zone_state[
            zone_i,
            schema.ZONE_CO2_PPM,
        ]
        physics_result[zone_i, schema.PHYSICS_ILLUMINANCE_LUX] = zone_state[
            zone_i,
            schema.ZONE_ILLUMINANCE_LUX,
        ]
        physics_result[zone_i, schema.PHYSICS_NOISE_DB] = zone_state[
            zone_i,
            schema.ZONE_NOISE_DB,
        ]
        physics_result[zone_i, schema.PHYSICS_HEATING_DEMAND_W] = 0.0
        physics_result[zone_i, schema.PHYSICS_COOLING_DEMAND_W] = 0.0
        physics_result[zone_i, schema.PHYSICS_VENTILATION_FLOW_M3_S] = 0.0

        if int(zone_state[zone_i, schema.ZONE_TYPE]) == schema.ZONE_TYPE_OUTSIDE:
            continue

        # ---------------------------------------------------------------------
        # Current state.
        # ---------------------------------------------------------------------

        old_air_temperature_c = zone_state[
            zone_i,
            schema.ZONE_AIR_TEMPERATURE_C,
        ]
        old_mass_temperature_c = zone_state[
            zone_i,
            schema.ZONE_MEAN_RADIANT_TEMPERATURE_C,
        ]

        if old_mass_temperature_c == 0.0:
            old_mass_temperature_c = old_air_temperature_c

        # ---------------------------------------------------------------------
        # Capacities.
        # ---------------------------------------------------------------------

        volume_m3 = zone_static[zone_i, schema.ZONE_STATIC_VOLUME_M3]

        if volume_m3 <= 0.0:
            floor_area = zone_static[zone_i, schema.ZONE_STATIC_FLOOR_AREA_M2]
            height = zone_static[zone_i, schema.ZONE_STATIC_HEIGHT_M]

            if height <= 0.0:
                height = 2.7

            volume_m3 = floor_area * height

        c_air = volume_m3 * AIR_DENSITY_KG_M3 * AIR_SPECIFIC_HEAT_J_KG_K

        if c_air < DEFAULT_AIR_CAPACITY_MIN_J_K:
            c_air = DEFAULT_AIR_CAPACITY_MIN_J_K

        c_mass = zone_static[zone_i, schema.ZONE_STATIC_HEAT_CAPACITY_J_K]

        if c_mass < DEFAULT_MASS_CAPACITY_MIN_J_K:
            c_mass = DEFAULT_MASS_CAPACITY_MIN_J_K

        # ---------------------------------------------------------------------
        # Conductances.
        # ---------------------------------------------------------------------

        floor_area = zone_static[zone_i, schema.ZONE_STATIC_FLOOR_AREA_M2]

        if floor_area <= 0.0:
            floor_area = 10.0

        effective_mass_area = floor_area * DEFAULT_EFFECTIVE_MASS_AREA_FACTOR
        h_air_mass = (
            DEFAULT_AIR_MASS_COUPLING_W_M2K
            * effective_mass_area
        )

        if h_air_mass < DEFAULT_MIN_AIR_MASS_CONDUCTANCE_W_K:
            h_air_mass = DEFAULT_MIN_AIR_MASS_CONDUCTANCE_W_K

        h_envelope = zone_static[
            zone_i,
            schema.ZONE_STATIC_UA_ENVELOPE_W_K,
        ]

        if h_envelope < 0.0:
            h_envelope = 0.0

        # ---------------------------------------------------------------------
        # Outdoor airflow and HVAC.
        # One loop over systems instead of several helper loops.
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

        mechanical_flow = 0.0
        window_flow = 0.0
        heating_power = 0.0
        cooling_power = 0.0

        for system_i in range(n_systems):
            system_zone_id = int(
                system_state[system_i, schema.SYSTEM_ZONE_ID]
            )

            if system_zone_id != zone_i:
                continue

            # HVAC.
            heat = system_state[
                system_i,
                schema.SYSTEM_HEATING_POWER_W,
            ]
            cool = system_state[
                system_i,
                schema.SYSTEM_COOLING_POWER_W,
            ]

            if heat > 0.0:
                heating_power += heat

            if cool > 0.0:
                cooling_power += cool

            # Mechanical ventilation.
            ventilation_mode = int(
                system_state[
                    system_i,
                    schema.SYSTEM_VENTILATION_MODE,
                ]
            )

            if (
                ventilation_mode == schema.VENTILATION_MODE_MECHANICAL
                or ventilation_mode == schema.VENTILATION_MODE_HYBRID
            ):
                mech = system_state[
                    system_i,
                    schema.SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S,
                ]

                if mech > 0.0:
                    mechanical_flow += mech

            # Window ventilation.
            has_window = (
                system_static[
                    system_i,
                    schema.SYSTEM_STATIC_HAS_WINDOW,
                ]
                > 0.0
            )

            if has_window:
                fraction = system_state[
                    system_i,
                    schema.SYSTEM_WINDOW_OPEN_FRACTION,
                ]
                max_flow = system_static[
                    system_i,
                    schema.SYSTEM_STATIC_MAX_WINDOW_FLOW_M3_S,
                ]

                if fraction > 0.0 and max_flow > 0.0:
                    window_flow += fraction * max_flow

        ventilation_flow_m3_s = (
            outdoor_flow
            + infiltration_flow
            + mechanical_flow
            + window_flow
        )

        h_ventilation = (
            ventilation_flow_m3_s
            * AIR_DENSITY_KG_M3
            * AIR_SPECIFIC_HEAT_J_KG_K
        )

        if h_ventilation < 0.0:
            h_ventilation = 0.0

        # ---------------------------------------------------------------------
        # Gains.
        # ---------------------------------------------------------------------

        if internal_gains is not None:
            people = internal_gains[zone_i, schema.GAIN_PEOPLE_HEAT_W]
            lighting = internal_gains[zone_i, schema.GAIN_LIGHTING_HEAT_W]
            appliance = internal_gains[zone_i, schema.GAIN_APPLIANCE_HEAT_W]
            solar = internal_gains[zone_i, schema.GAIN_SOLAR_HEAT_W]
        else:
            people = zone_state[zone_i, schema.ZONE_PEOPLE_GAIN_W]
            lighting = zone_state[zone_i, schema.ZONE_LIGHTING_GAIN_W]
            appliance = zone_state[zone_i, schema.ZONE_APPLIANCE_GAIN_W]
            solar = zone_state[zone_i, schema.ZONE_SOLAR_GAIN_W]

        hvac_gain = heating_power - cooling_power

        people_conv = DEFAULT_PEOPLE_CONVECTIVE_FRACTION * people
        appliance_conv = DEFAULT_APPLIANCE_CONVECTIVE_FRACTION * appliance
        lighting_conv = DEFAULT_LIGHTING_CONVECTIVE_FRACTION * lighting
        solar_conv = DEFAULT_SOLAR_CONVECTIVE_FRACTION * solar
        hvac_conv = DEFAULT_HVAC_CONVECTIVE_FRACTION * hvac_gain

        convective_gain_w = (
            people_conv
            + appliance_conv
            + lighting_conv
            + solar_conv
            + hvac_conv
        )

        radiative_gain_w = (
            (people - people_conv)
            + (appliance - appliance_conv)
            + (lighting - lighting_conv)
            + (solar - solar_conv)
            + (hvac_gain - hvac_conv)
        )

        # ---------------------------------------------------------------------
        # Air node semi-implicit update.
        #
        # Same as:
        #   semi_implicit_temperature_update_scalar(
        #       c_air,
        #       old_air,
        #       [old_mass, outdoor, outdoor],
        #       [h_air_mass, h_envelope, h_vent],
        #       3,
        #       convective_gain,
        #       dt_seconds,
        #   )
        # ---------------------------------------------------------------------

        c_air_over_dt = c_air / dt_seconds

        air_numerator = (
            c_air_over_dt * old_air_temperature_c
            + convective_gain_w
            + h_air_mass * old_mass_temperature_c
            + h_envelope * outdoor_temperature_c
            + h_ventilation * outdoor_temperature_c
        )

        air_denominator = (
            c_air_over_dt
            + h_air_mass
            + h_envelope
            + h_ventilation
        )

        if air_denominator <= 0.0:
            new_air_temperature_c = old_air_temperature_c
        else:
            new_air_temperature_c = air_numerator / air_denominator

        # ---------------------------------------------------------------------
        # Mass/MRT node semi-implicit update.
        #
        # Same as:
        #   semi_implicit_temperature_update_scalar(
        #       c_mass,
        #       old_mass,
        #       [new_air],
        #       [h_air_mass],
        #       1,
        #       radiative_gain,
        #       dt_seconds,
        #   )
        # ---------------------------------------------------------------------

        c_mass_over_dt = c_mass / dt_seconds

        mass_numerator = (
            c_mass_over_dt * old_mass_temperature_c
            + radiative_gain_w
            + h_air_mass * new_air_temperature_c
        )

        mass_denominator = c_mass_over_dt + h_air_mass

        if mass_denominator <= 0.0:
            new_mass_temperature_c = old_mass_temperature_c
        else:
            new_mass_temperature_c = mass_numerator / mass_denominator

        # ---------------------------------------------------------------------
        # Write back.
        # Inline version of write_zone_thermal_result.
        # ---------------------------------------------------------------------

        zone_state[
            zone_i,
            schema.ZONE_AIR_TEMPERATURE_C,
        ] = new_air_temperature_c

        zone_state[
            zone_i,
            schema.ZONE_MEAN_RADIANT_TEMPERATURE_C,
        ] = new_mass_temperature_c

        physics_result[
            zone_i,
            schema.PHYSICS_AIR_TEMPERATURE_C,
        ] = new_air_temperature_c

        physics_result[
            zone_i,
            schema.PHYSICS_MEAN_RADIANT_TEMPERATURE_C,
        ] = new_mass_temperature_c

        physics_result[
            zone_i,
            schema.PHYSICS_HEATING_DEMAND_W,
        ] = heating_power

        physics_result[
            zone_i,
            schema.PHYSICS_COOLING_DEMAND_W,
        ] = cooling_power

        physics_result[
            zone_i,
            schema.PHYSICS_VENTILATION_FLOW_M3_S,
        ] = ventilation_flow_m3_s

    return zone_state, physics_result

def run_thermal_step(
    zone_state,
    zone_static,
    system_state,
    system_static,
    weather_state,
    internal_gains,
    physics_result,
    dt_minutes,
):
    """
    Public alias for the array timestep orchestration.

    Uses the fast thermal path by default.
    """
    return step_building_thermal_semi_implicit_fast(
        zone_state=zone_state,
        zone_static=zone_static,
        system_state=system_state,
        system_static=system_static,
        weather_state=weather_state,
        internal_gains=internal_gains,
        physics_result=physics_result,
        dt_minutes=dt_minutes,
    )