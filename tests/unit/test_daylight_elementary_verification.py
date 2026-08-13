"""Phase 4.20 analytical verification for simplified daylight and lighting."""

from types import SimpleNamespace

import pytest

from nexusep.abbey.building.controllers import ThermostatController
from nexusep.abbey.building.model import ZoneState
from nexusep.abbey.building.physics.daylight import (
    OutdoorDaylightBoundary,
    WindowDaylightParameters,
    ZoneLightingControlInput,
    ZoneLightingParameters,
    ZoneWindowDaylightParameters,
    calculate_zone_indoor_daylight_result,
    calculate_zone_lighting_power_result,
)
from nexusep.abbey.building.physics.windows import (
    WindowOperationState,
    WindowStaticParameters,
    calculate_window_covering_effect,
    calculate_window_solar_exposure_result,
)
from nexusep.abbey.building.systems import (
    ZoneControlCommand,
    ZoneControlState,
    ZoneSystemSpec,
)

pytestmark = pytest.mark.unit
VALIDATION_CATEGORY = "verification"


def _daylight(window: WindowDaylightParameters | None) -> float:
    parameters = ZoneWindowDaylightParameters(
        zone_id="zone-a",
        windows=[] if window is None else [window],
    )
    return calculate_zone_indoor_daylight_result(
        zone_window_parameters=parameters,
        outdoor_daylight_boundary=OutdoorDaylightBoundary(
            outdoor_illuminance_lux=10_000.0,
            sky_condition="overcast",
        ),
        floor_area_m2=20.0,
    ).daylight_illuminance_lux


def _window(**updates: float) -> WindowDaylightParameters:
    values = {
        "boundary_connection_id": "window-a",
        "zone_id": "zone-a",
        "area_m2": 2.0,
        "visible_transmittance": 0.5,
        "frame_fraction": 0.0,
        "shading_factor": 1.0,
        "daylight_utilization_factor": 0.5,
    }
    values.update(updates)
    return WindowDaylightParameters(**values)


def _static_window(orientation_deg: float, *, shading_factor: float = 1.0):
    return WindowStaticParameters(
        boundary_connection_id=f"window-{orientation_deg:g}",
        zone_id="zone-a",
        orientation_deg=orientation_deg,
        area_m2=2.0,
        frame_fraction=0.0,
        window_visible_transmittance=0.6,
        shading_factor=shading_factor,
    )


def test_no_window_produces_zero_indoor_daylight() -> None:
    assert _daylight(None) == 0.0


def test_single_unshaded_window_matches_declared_linear_equation() -> None:
    # 10,000 lux * (2 m2 * 0.5 VT * 0.5 utilization) / 20 m2.
    assert _daylight(_window()) == pytest.approx(250.0)


def test_visible_transmittance_and_shading_are_monotonic() -> None:
    zero_transmittance = _daylight(_window(visible_transmittance=0.0))
    half_transmittance = _daylight(_window(visible_transmittance=0.5))
    full_transmittance = _daylight(_window(visible_transmittance=1.0))
    fully_shaded = _daylight(_window(shading_factor=0.0))

    assert zero_transmittance == fully_shaded == 0.0
    assert zero_transmittance < half_transmittance < full_transmittance


def test_overcast_fallback_is_symmetric_across_cardinal_orientations() -> None:
    weather = SimpleNamespace(
        sky_condition="overcast",
        outdoor_illuminance_lux=10_000.0,
        direct_normal_radiation_w_m2=0.0,
        diffuse_horizontal_radiation_w_m2=100.0,
        global_horizontal_radiation_w_m2=100.0,
        solar_azimuth_deg=None,
        solar_altitude_deg=None,
    )
    factors = {
        calculate_window_solar_exposure_result(
            _static_window(orientation), weather
        ).daylight_exposure_factor
        for orientation in (0.0, 90.0, 180.0, 270.0)
    }
    assert factors == {0.25}


def test_direct_sunlight_responds_to_orientation_and_full_shading() -> None:
    weather = SimpleNamespace(
        sky_condition="clear",
        outdoor_illuminance_lux=0.0,
        direct_normal_radiation_w_m2=800.0,
        diffuse_horizontal_radiation_w_m2=0.0,
        global_horizontal_radiation_w_m2=400.0,
        solar_azimuth_deg=90.0,
        solar_altitude_deg=30.0,
    )
    east = _static_window(90.0)
    west = _static_window(270.0)
    east_exposure = calculate_window_solar_exposure_result(east, weather)
    west_exposure = calculate_window_solar_exposure_result(west, weather)
    shaded = _static_window(90.0, shading_factor=0.0)
    shaded_effect = calculate_window_covering_effect(
        shaded,
        WindowOperationState(
            boundary_connection_id=shaded.boundary_connection_id,
            zone_id=shaded.zone_id,
        ),
    )

    assert east_exposure.daylight_exposure_factor > 0.0
    assert west_exposure.daylight_exposure_factor == 0.0
    assert shaded_effect.effective_visible_transmittance == 0.0
    assert (
        east_exposure.daylight_exposure_factor
        * shaded_effect.effective_visible_transmittance
        == 0.0
    )


def test_lighting_power_and_energy_increase_monotonically_with_request() -> None:
    parameters = ZoneLightingParameters(
        zone_id="zone-a",
        floor_area_m2=20.0,
        installed_lighting_lux=500.0,
        lighting_power_density_w_m2=8.0,
    )

    def result(requested_lux: float):
        return calculate_zone_lighting_power_result(
            zone_lighting_parameters=parameters,
            lighting_control_input=ZoneLightingControlInput(
                zone_id="zone-a",
                lights_on=True,
                dimming_fraction=1.0,
                requested_artificial_lighting_lux=requested_lux,
                control_mode="auto",
            ),
            dt_minutes=30.0,
        )

    off, dimmed, full = (result(value) for value in (0.0, 250.0, 500.0))
    assert off.lighting_power_w < dimmed.lighting_power_w < full.lighting_power_w
    assert dimmed.lighting_power_w == pytest.approx(80.0)
    assert dimmed.lighting_energy_wh == pytest.approx(40.0)


def test_auto_lighting_threshold_hysteresis_prevents_chatter() -> None:
    controller = ThermostatController(
        lighting_on_threshold=0.35,
        lighting_off_threshold=0.45,
    )
    system = ZoneSystemSpec(
        zone_id="zone-a",
        dwelling_id="dwelling-a",
        building_id="building-a",
        lighting_power_w=100.0,
    )
    control = ZoneControlState(
        zone_id="zone-a",
        dwelling_id="dwelling-a",
        building_id="building-a",
        lighting_mode="auto",
    )

    def step(daylight: float, previous: ZoneControlCommand | None = None):
        return controller.step(
            zone_state=ZoneState(
                zone_id="zone-a",
                dwelling_id="dwelling-a",
                building_id="building-a",
                indoor_daylight=daylight,
                number_of_people=1,
            ),
            control_state=control,
            system_spec=system,
            previous_command=previous,
        )

    low = step(0.30)
    rising_inside_band = step(0.40, low)
    high = step(0.50, rising_inside_band)
    falling_inside_band = step(0.40, high)

    assert low.lights_on is True
    assert rising_inside_band.lights_on is True
    assert high.lights_on is False
    assert falling_inside_band.lights_on is False


def test_auto_lighting_is_off_when_zone_is_unoccupied() -> None:
    controller = ThermostatController()
    command = controller.step(
        zone_state=ZoneState(
            zone_id="zone-a",
            dwelling_id="dwelling-a",
            building_id="building-a",
            indoor_daylight=0.0,
            number_of_people=0,
        ),
        control_state=ZoneControlState(
            zone_id="zone-a",
            dwelling_id="dwelling-a",
            building_id="building-a",
            lighting_mode="auto",
        ),
        system_spec=ZoneSystemSpec(
            zone_id="zone-a",
            dwelling_id="dwelling-a",
            building_id="building-a",
            lighting_power_w=100.0,
        ),
    )
    assert command.lights_on is False
    assert command.lighting_power_w == 0.0
