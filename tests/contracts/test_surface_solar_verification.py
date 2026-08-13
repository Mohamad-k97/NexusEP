"""Verification: analytical surface irradiance and transmitted-gain cases."""

from __future__ import annotations

import math

import pytest

from nexusep.abbey.building.physics.solar import (
    calculate_surface_solar_irradiance,
)


def _surface(tilt: float, azimuth: float, *, dni=800.0, dhi=100.0, ghi=500.0):
    return calculate_surface_solar_irradiance(
        solar_zenith_deg=60.0,
        solar_azimuth_deg=180.0,
        surface_tilt_deg=tilt,
        surface_azimuth_deg=azimuth,
        direct_normal_radiation_w_m2=dni,
        diffuse_horizontal_radiation_w_m2=dhi,
        global_horizontal_radiation_w_m2=ghi,
        ground_albedo_fraction=0.0,
    )


def test_cardinal_vertical_facades_have_expected_direction() -> None:
    south = _surface(90.0, 180.0)
    east = _surface(90.0, 90.0)
    west = _surface(90.0, 270.0)
    north = _surface(90.0, 0.0)
    assert south.direct_w_m2 == pytest.approx(800.0 * math.sin(math.radians(60)))
    assert east.direct_w_m2 == pytest.approx(0.0, abs=1e-12)
    assert west.direct_w_m2 == pytest.approx(0.0, abs=1e-12)
    assert north.direct_w_m2 == 0.0
    assert south.total_w_m2 > east.total_w_m2 == pytest.approx(west.total_w_m2)
    assert east.total_w_m2 == pytest.approx(north.total_w_m2)


def test_horizontal_surface_recovers_direct_horizontal_plus_dhi() -> None:
    horizontal = _surface(0.0, 0.0)
    assert horizontal.direct_w_m2 == pytest.approx(800.0 * 0.5)
    assert horizontal.sky_diffuse_w_m2 == pytest.approx(100.0)
    assert horizontal.total_w_m2 == pytest.approx(500.0)


def test_direct_only_and_diffuse_only_components() -> None:
    direct = _surface(90.0, 180.0, dhi=0.0, ghi=400.0)
    diffuse = _surface(90.0, 180.0, dni=0.0, dhi=100.0, ghi=100.0)
    assert direct.sky_diffuse_w_m2 == 0.0
    assert direct.direct_w_m2 > 0.0
    assert diffuse.direct_w_m2 == 0.0
    assert diffuse.sky_diffuse_w_m2 == pytest.approx(50.0)


def test_zero_full_transmittance_and_full_shading() -> None:
    incident = _surface(90.0, 180.0)
    assert incident.transmitted_gain_w(
        area_m2=2.0, solar_transmittance_fraction=0.0
    ) == 0.0
    assert incident.transmitted_gain_w(
        area_m2=2.0, solar_transmittance_fraction=1.0
    ) == pytest.approx(incident.total_w_m2 * 2.0)
    assert incident.transmitted_gain_w(
        area_m2=2.0,
        solar_transmittance_fraction=1.0,
        unshaded_fraction=0.0,
    ) == 0.0


def test_energy_integration_uses_interval_hours() -> None:
    incident = _surface(0.0, 0.0)
    three_half_hour_steps_wh_m2 = sum(incident.total_w_m2 * 0.5 for _ in range(3))
    assert three_half_hour_steps_wh_m2 == pytest.approx(750.0)


def test_night_removes_direct_but_preserves_declared_diffuse() -> None:
    result = calculate_surface_solar_irradiance(
        solar_zenith_deg=110.0,
        solar_azimuth_deg=0.0,
        surface_tilt_deg=90.0,
        surface_azimuth_deg=0.0,
        direct_normal_radiation_w_m2=800.0,
        diffuse_horizontal_radiation_w_m2=10.0,
        global_horizontal_radiation_w_m2=10.0,
    )
    assert result.direct_w_m2 == 0.0
    assert result.sky_diffuse_w_m2 == pytest.approx(5.0)
