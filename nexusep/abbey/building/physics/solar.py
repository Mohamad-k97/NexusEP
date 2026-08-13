"""Solar geometry and plane-of-array irradiance with explicit conventions.

Solar position delegates to pvlib's independent Python implementation of the
NREL Solar Position Algorithm (SPA).  Surface irradiance uses the isotropic-sky
model and is intentionally kept separate from the legacy GHI-only runner path.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from pvlib.solarposition import spa_python, sun_rise_set_transit_spa

NREL_SPA_REFERENCE = "NREL/TP-560-34302, revised January 2008"
AZIMUTH_CONVENTION = "degrees clockwise from true north"


@dataclass(frozen=True)
class SolarPosition:
    """Solar position at one aware timestamp.

    ``zenith_deg`` and ``elevation_deg`` are geometric.  The apparent values
    include atmospheric refraction.  Azimuth is clockwise from true north.
    """

    timestamp: datetime
    latitude_deg: float
    longitude_deg: float
    zenith_deg: float
    apparent_zenith_deg: float
    elevation_deg: float
    apparent_elevation_deg: float
    azimuth_deg: float
    equation_of_time_minutes: float

    @property
    def is_sun_up(self) -> bool:
        return self.apparent_elevation_deg > 0.0


@dataclass(frozen=True)
class SurfaceSolarIrradiance:
    """Irradiance incident on a planar surface in W/m2."""

    surface_tilt_deg: float
    surface_azimuth_deg: float
    incidence_angle_deg: float
    incidence_cosine: float
    direct_w_m2: float
    sky_diffuse_w_m2: float
    ground_reflected_w_m2: float
    total_w_m2: float

    def transmitted_gain_w(
        self,
        *,
        area_m2: float,
        solar_transmittance_fraction: float,
        unshaded_fraction: float = 1.0,
    ) -> float:
        area = _non_negative(area_m2, "area_m2")
        transmittance = _fraction(
            solar_transmittance_fraction, "solar_transmittance_fraction"
        )
        unshaded = _fraction(unshaded_fraction, "unshaded_fraction")
        return self.total_w_m2 * area * transmittance * unshaded


@dataclass(frozen=True)
class SolarDayEvents:
    """NREL-SPA sunrise, transit, and sunset for one local civil date."""

    sunrise: datetime
    transit: datetime
    sunset: datetime


def calculate_solar_day_events(
    local_date: datetime,
    *,
    latitude_deg: float,
    longitude_deg: float,
    delta_t_seconds: float | None = None,
) -> SolarDayEvents:
    """Calculate sunrise, solar transit and sunset using NREL SPA.

    ``local_date`` must be an aware datetime at local midnight.  Its timezone
    controls the civil-date representation, including daylight-saving rules.
    """

    if not isinstance(local_date, datetime) or local_date.tzinfo is None:
        raise ValueError("local_date must be a timezone-aware datetime")
    if any((local_date.hour, local_date.minute, local_date.second, local_date.microsecond)):
        raise ValueError("local_date must be local midnight")
    latitude = float(latitude_deg)
    longitude = float(longitude_deg)
    if not -90.0 <= latitude <= 90.0:
        raise ValueError("latitude_deg must be in [-90, 90]")
    if not -180.0 <= longitude <= 180.0:
        raise ValueError("longitude_deg must be in [-180, 180]")
    values = sun_rise_set_transit_spa(
        pd.DatetimeIndex([local_date]),
        latitude,
        longitude,
        how="numpy",
        delta_t=delta_t_seconds,
    ).iloc[0]
    return SolarDayEvents(
        sunrise=values["sunrise"].to_pydatetime(warn=False),
        transit=values["transit"].to_pydatetime(warn=False),
        sunset=values["sunset"].to_pydatetime(warn=False),
    )


def calculate_solar_position(
    timestamp: datetime,
    *,
    latitude_deg: float,
    longitude_deg: float,
    elevation_m: float = 0.0,
    atmospheric_pressure_pa: float = 101_325.0,
    outdoor_temperature_c: float = 12.0,
    delta_t_seconds: float | None = None,
    atmospheric_refraction_deg: float = 0.5667,
) -> SolarPosition:
    """Calculate solar position using NREL SPA through pvlib.

    The timestamp must carry its UTC offset.  ``delta_t_seconds=None`` asks
    pvlib to calculate the monthly approximation; callers doing metrological
    comparisons should supply a measured/declared value.
    """

    if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
        raise ValueError("timestamp must be a timezone-aware datetime")
    latitude = float(latitude_deg)
    longitude = float(longitude_deg)
    if not -90.0 <= latitude <= 90.0:
        raise ValueError("latitude_deg must be in [-90, 90]")
    if not -180.0 <= longitude <= 180.0:
        raise ValueError("longitude_deg must be in [-180, 180]")
    pressure = _non_negative(atmospheric_pressure_pa, "atmospheric_pressure_pa")
    times = pd.DatetimeIndex([timestamp])
    values = spa_python(
        times,
        latitude,
        longitude,
        altitude=float(elevation_m),
        pressure=pressure,
        temperature=float(outdoor_temperature_c),
        delta_t=delta_t_seconds,
        atmos_refract=float(atmospheric_refraction_deg),
        how="numpy",
    ).iloc[0]
    return SolarPosition(
        timestamp=timestamp,
        latitude_deg=latitude,
        longitude_deg=longitude,
        zenith_deg=float(values["zenith"]),
        apparent_zenith_deg=float(values["apparent_zenith"]),
        elevation_deg=float(values["elevation"]),
        apparent_elevation_deg=float(values["apparent_elevation"]),
        azimuth_deg=float(values["azimuth"]) % 360.0,
        equation_of_time_minutes=float(values["equation_of_time"]),
    )


def calculate_surface_solar_irradiance(
    *,
    solar_zenith_deg: float,
    solar_azimuth_deg: float,
    surface_tilt_deg: float,
    surface_azimuth_deg: float,
    direct_normal_radiation_w_m2: float,
    diffuse_horizontal_radiation_w_m2: float,
    global_horizontal_radiation_w_m2: float,
    ground_albedo_fraction: float = 0.0,
) -> SurfaceSolarIrradiance:
    """Resolve DNI, DHI and GHI onto a surface using isotropic sky diffuse.

    Surface tilt is measured from horizontal.  Both azimuths are clockwise
    from north.  Direct irradiance is zero when the sun is behind the plane or
    geometrically below the horizon.
    """

    zenith = float(solar_zenith_deg)
    if not 0.0 <= zenith <= 180.0:
        raise ValueError("solar_zenith_deg must be in [0, 180]")
    tilt = float(surface_tilt_deg)
    if not 0.0 <= tilt <= 180.0:
        raise ValueError("surface_tilt_deg must be in [0, 180]")
    solar_azimuth = float(solar_azimuth_deg) % 360.0
    surface_azimuth = float(surface_azimuth_deg) % 360.0
    dni = _non_negative(
        direct_normal_radiation_w_m2, "direct_normal_radiation_w_m2"
    )
    dhi = _non_negative(
        diffuse_horizontal_radiation_w_m2,
        "diffuse_horizontal_radiation_w_m2",
    )
    ghi = _non_negative(
        global_horizontal_radiation_w_m2,
        "global_horizontal_radiation_w_m2",
    )
    albedo = _fraction(ground_albedo_fraction, "ground_albedo_fraction")

    zenith_rad = math.radians(zenith)
    tilt_rad = math.radians(tilt)
    azimuth_delta_rad = math.radians(solar_azimuth - surface_azimuth)
    raw_cosine = (
        math.cos(zenith_rad) * math.cos(tilt_rad)
        + math.sin(zenith_rad)
        * math.sin(tilt_rad)
        * math.cos(azimuth_delta_rad)
    )
    direct_cosine = max(0.0, raw_cosine) if zenith < 90.0 else 0.0
    incidence_angle = math.degrees(
        math.acos(max(-1.0, min(1.0, raw_cosine)))
    )
    direct = dni * direct_cosine
    sky_diffuse = dhi * (1.0 + math.cos(tilt_rad)) / 2.0
    ground_reflected = ghi * albedo * (1.0 - math.cos(tilt_rad)) / 2.0
    return SurfaceSolarIrradiance(
        surface_tilt_deg=tilt,
        surface_azimuth_deg=surface_azimuth,
        incidence_angle_deg=incidence_angle,
        incidence_cosine=direct_cosine,
        direct_w_m2=direct,
        sky_diffuse_w_m2=sky_diffuse,
        ground_reflected_w_m2=ground_reflected,
        total_w_m2=direct + sky_diffuse + ground_reflected,
    )


def _non_negative(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")
    return result


def _fraction(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be in [0, 1]")
    return result
