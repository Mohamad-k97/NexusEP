"""
ABBEY perception update.

ABBEY does not calculate building performance.
It receives DwellingObservation from the building-performance module
and converts it into occupant perception states.
"""

import math
from typing import Any, Mapping

from nexusep.abbey.agents.states import (
    PersonState,
    DwellingObservation,
    SystemState,
    SimulationClock,
)
from nexusep.abbey.dynamics.smooth_update import smooth_bounded_update
from nexusep.abbey.agents.location import OccupantLocation

AbbeyConfig = Mapping[str, Any]


def fanger_pmv(
    ta_c: float,
    tr_c: float,
    vel_m_s: float,
    rh_percent: float,
    met: float,
    clo: float,
) -> float:
    pa = rh_percent * 10.0 * math.exp(16.6536 - 4030.183 / (ta_c + 235.0))

    icl = 0.155 * clo
    m = met * 58.15
    w = 0.0
    mw = m - w

    fcl = 1.0 + 1.29 * icl if icl <= 0.078 else 1.05 + 0.645 * icl
    hcf = 12.1 * math.sqrt(vel_m_s)

    taa = ta_c + 273.0
    tra = tr_c + 273.0

    tcla = taa + (35.5 - ta_c) / (3.5 * icl + 0.1)

    p1 = icl * fcl
    p2 = p1 * 3.96
    p3 = p1 * 100.0
    p4 = p1 * taa
    p5 = 308.7 - 0.028 * mw + p2 * ((tra / 100.0) ** 4)

    xn = tcla / 100.0
    eps = 0.00015

    for _ in range(150):
        xf = xn
        hcn = 2.38 * abs(100.0 * xf - taa) ** 0.25
        hc = max(hcf, hcn)
        xn = (p5 + p4 * hc - p2 * (xf ** 4)) / (100.0 + p3 * hc)

        if abs(xn - xf) <= eps:
            break

    tcl = 100.0 * xn - 273.0

    hl1 = 3.05 * 0.001 * (5733.0 - 6.99 * mw - pa)
    hl2 = 0.42 * (mw - 58.15) if mw > 58.15 else 0.0
    hl3 = 1.7 * 0.00001 * m * (5867.0 - pa)
    hl4 = 0.0014 * m * (34.0 - ta_c)
    hl5 = 3.96 * fcl * ((xn ** 4) - ((tra / 100.0) ** 4))
    hl6 = fcl * hc * (tcl - ta_c)

    transfer = 0.303 * math.exp(-0.036 * m) + 0.028

    return transfer * (mw - hl1 - hl2 - hl3 - hl4 - hl5 - hl6)


def pmv_to_ppd(pmv: float) -> float:
    return 100.0 - 95.0 * math.exp(
        -0.03353 * (pmv ** 4)
        - 0.2179 * (pmv ** 2)
    )


def personal_pmv(
    pmv: float,
    person: PersonState,
    config: AbbeyConfig,
) -> float:
    cfg = config["perception"]["thermal"]

    adjusted = pmv + person.thermal_neutral_shift
    adjusted -= float(cfg["sickness_pmv_cold_shift"]) * person.sickness_severity

    if adjusted < 0.0:
        adjusted *= person.cold_sensitivity
    else:
        adjusted *= person.heat_sensitivity

    return adjusted


def compute_thermal_perception(
    person: PersonState,
    observation: DwellingObservation,
    location: OccupantLocation,
    config: AbbeyConfig,
) -> tuple[float, float, float]:
    cfg = config["perception"]["thermal"]

    zone = observation.get_zone(location.current_space_id)
    ta = zone.indoor_temp
    tr = ta

    pmv = fanger_pmv(
        ta_c=ta,
        tr_c=tr,
        vel_m_s=float(cfg["air_velocity_m_s"]),
        rh_percent=float(cfg["relative_humidity_percent"]),
        met=float(cfg["met"]),
        clo=float(cfg["clo"]),
    )

    pmv_personal = personal_pmv(pmv, person, config)
    ppd = pmv_to_ppd(pmv_personal)

    dissatisfaction = ppd / 100.0
    satisfaction = 1.0 - dissatisfaction

    return pmv_personal, dissatisfaction, satisfaction


def _stress_from_excess(excess: float, scale: float) -> float:
    if scale <= 0:
        raise ValueError("stress scale must be positive.")

    if excess <= 0.0:
        return 0.0

    return math.tanh(excess / scale)


def air_quality_stressor(
    person: PersonState,
    observation: DwellingObservation,
    location: OccupantLocation,
    config: AbbeyConfig,
) -> float:
    cfg = config["perception"]["air_quality"]

    zone = observation.get_zone(location.current_space_id)

    excess = max(
        0.0,
        zone.co2_ppm - float(cfg["comfortable_co2_ppm"]),
    )

    base_stress = _stress_from_excess(
        excess=excess,
        scale=float(cfg["co2_stress_scale_ppm"]),
    )

    sickness_multiplier = (
        1.0
        + float(cfg["sickness_sensitivity_multiplier"]) * person.sickness_severity
    )

    return min(1.0, base_stress * sickness_multiplier)


def visual_stressor(
    person: PersonState,
    observation: DwellingObservation,
    systems: SystemState,
    location: OccupantLocation,
    config: AbbeyConfig,
) -> float:
    
    zone = observation.get_zone(location.current_space_id)

    cfg = config["perception"]["visual"]

    if person.is_sleeping or not person.is_home:
        return 0.0

    effective_light = zone.indoor_daylight
    zone_controls = systems.get_space_controls(location.current_space_id)
    
    if zone_controls.lights_on:
        effective_light += float(cfg["artificial_light_equivalent"])

    deficit = max(
        0.0,
        float(cfg["required_daylight"]) - effective_light,
    )

    return _stress_from_excess(
        excess=deficit,
        scale=float(cfg["daylight_stress_scale"]),
    )


def acoustic_stressor(
    person: PersonState,
    observation: DwellingObservation,
    location: OccupantLocation,
    config: AbbeyConfig,
) -> float:
    
    zone = observation.get_zone(location.current_space_id)

    cfg = config["perception"]["acoustic"]

    if not person.is_home:
        return 0.0

    excess = max(
        0.0,
        zone.indoor_noise - float(cfg["comfortable_noise"]),
    )

    return _stress_from_excess(
        excess=excess,
        scale=float(cfg["noise_stress_scale"]),
    )


def update_perception(
    person: PersonState,
    observation: DwellingObservation,
    systems: SystemState,
    location: OccupantLocation,
    clock: SimulationClock,
    config: AbbeyConfig,
) -> PersonState:
    
    thermal_cfg = config["perception"]["thermal"]
    air_cfg = config["perception"]["air_quality"]
    visual_cfg = config["perception"]["visual"]
    acoustic_cfg = config["perception"]["acoustic"]

    thermal_sensation, thermal_dissatisfaction, thermal_satisfaction = (
        compute_thermal_perception(person, observation, location, config)
    )
    
    air_stress = air_quality_stressor(person, observation, location, config)
    visual_stress = visual_stressor(person, observation, systems, location, config)
    acoustic_stress = acoustic_stressor(person, observation, location, config)

    thermal_discomfort = smooth_bounded_update(
        x=person.thermal_discomfort,
        up=float(thermal_cfg["response_up"]) * thermal_dissatisfaction,
        down=float(thermal_cfg["response_down"]) * thermal_satisfaction,
        dt_hours=clock.dt_hours,
    )

    air_quality_discomfort = smooth_bounded_update(
        x=person.air_quality_discomfort,
        up=float(air_cfg["response_up"]) * air_stress,
        down=float(air_cfg["response_down"]) * (1.0 - air_stress),
        dt_hours=clock.dt_hours,
    )

    visual_discomfort = smooth_bounded_update(
        x=person.visual_discomfort,
        up=float(visual_cfg["response_up"]) * visual_stress,
        down=float(visual_cfg["response_down"]) * (1.0 - visual_stress),
        dt_hours=clock.dt_hours,
    )

    acoustic_discomfort = smooth_bounded_update(
        x=person.acoustic_discomfort,
        up=float(acoustic_cfg["response_up"]) * acoustic_stress,
        down=float(acoustic_cfg["response_down"]) * (1.0 - acoustic_stress),
        dt_hours=clock.dt_hours,
    )

    return person.copy(
        thermal_sensation=thermal_sensation,
        thermal_satisfaction=thermal_satisfaction,
        thermal_dissatisfaction=thermal_dissatisfaction,
        thermal_discomfort=thermal_discomfort,
        air_quality_discomfort=air_quality_discomfort,
        visual_discomfort=visual_discomfort,
        acoustic_discomfort=acoustic_discomfort,
    )