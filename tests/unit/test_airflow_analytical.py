"""Analytical verification cases for prescribed airflow and CO2 exchange."""

from __future__ import annotations

from datetime import UTC, datetime
from math import exp, sqrt

import pytest

from nexusep.abbey.building.physics.airflow import (
    AIRFLOW_NETWORK_PRESSURE_SOLVE,
    AIRFLOW_PRESSURE_NETWORK_MODE,
    AIRFLOW_WINDOW_MODEL,
    CO2_BUILDING_TIMESTEP_METHOD,
    INTERZONE_AIRFLOW_MODEL_TWO_OPENING_BUOYANCY,
    INTERZONE_TWO_OPENING_SOURCE,
    BuildingAirflowNetwork,
    BuildingAirState,
    BuildingCO2GenerationResult,
    DoorOpeningInput,
    InterzoneAirflowLink,
    InterzoneAirflowRecord,
    ZoneAirState,
    ZoneOutdoorAirflowRecord,
    calculate_interzone_airflow_link,
    check_airflow_network_mass_balance,
    dry_air_density_kg_m3,
    step_building_co2_state,
    two_opening_buoyancy_exchange_m3_s,
)
from nexusep.abbey.building.physics.graph import ZoneConnection
from nexusep.abbey.building.physics.thermal import (
    BuildingThermalState,
    ZoneThermalState,
)
from nexusep.abbey.building.physics.weather import WeatherState
from nexusep.abbey.building.physics.windows import (
    WindowOperationState,
    WindowStaticParameters,
    calculate_window_airflow_opening_result,
)

pytestmark = [pytest.mark.unit]
VALIDATION_CATEGORY = "verification"


def _weather(
    *,
    outdoor_temperature_c: float = 20.0,
    wind_speed_m_s: float = 0.0,
    wind_direction_deg: float = 180.0,
) -> WeatherState:
    return WeatherState(
        datetime=datetime(2025, 1, 1, tzinfo=UTC),
        outdoor_temperature_c=outdoor_temperature_c,
        wind_speed_m_s=wind_speed_m_s,
        wind_direction_deg=wind_direction_deg,
        outdoor_co2_ppm=420.0,
    )


def _two_zone_network(flow_m3_h: float = 60.0) -> BuildingAirflowNetwork:
    link = InterzoneAirflowLink(
        link_id="west-east",
        zone_connection_id="west-east",
        zone_a_id="west",
        zone_b_id="east",
        mixing_flow_m3_h=flow_m3_h,
    )
    record = InterzoneAirflowRecord(
        link_id=link.link_id,
        zone_connection_id=link.zone_connection_id,
        zone_a_id=link.zone_a_id,
        zone_b_id=link.zone_b_id,
        flow_a_to_b_m3_h=flow_m3_h,
        flow_b_to_a_m3_h=flow_m3_h,
    )
    return BuildingAirflowNetwork(
        interzone_airflow_links={link.link_id: link},
        interzone_airflow_records={record.link_id: record},
    )


def _step_closed_two_zone_exchange(
    state: BuildingAirState,
    *,
    flow_m3_h: float,
    dt_minutes: float,
) -> BuildingAirState:
    result = step_building_co2_state(
        air_state=state,
        airflow_network=_two_zone_network(flow_m3_h),
        co2_generation_result=BuildingCO2GenerationResult(),
        weather_state=_weather(),
        dt_minutes=dt_minutes,
    )
    assert result.method == CO2_BUILDING_TIMESTEP_METHOD
    return result.updated_air_state


def _window() -> WindowStaticParameters:
    return WindowStaticParameters(
        boundary_connection_id="south-window",
        zone_id="west",
        orientation_deg=180.0,
        area_m2=1.0,
        max_opening_area_m2=0.2,
        discharge_coefficient=0.6,
    )


def _window_state(
    opening_fraction: float,
    *,
    is_open: bool = True,
) -> WindowOperationState:
    return WindowOperationState(
        boundary_connection_id="south-window",
        zone_id="west",
        is_open=is_open,
        opening_fraction=opening_fraction,
    )


def test_one_zone_outdoor_exchange_balances_supply_and_exhaust() -> None:
    record = ZoneOutdoorAirflowRecord(
        zone_id="west",
        infiltration_flow_m3_h=18.0,
        mechanical_ventilation_flow_m3_h=42.0,
    )
    network = BuildingAirflowNetwork(outdoor_airflows_by_zone={"west": record})

    assert record.mixing_exchange_m3_h == pytest.approx(60.0)
    assert record.outdoor_supply_m3_h == pytest.approx(60.0)
    assert record.outdoor_exhaust_m3_h == pytest.approx(60.0)
    assert network.approximate_net_air_balance_by_zone_m3_h() == {"west": 0.0}
    assert network.approximate_air_mass_residual_by_zone_kg_s() == {"west": 0.0}
    assert check_airflow_network_mass_balance(network)

    paths = record.flow_paths()
    assert {(path["from_node_id"], path["to_node_id"]) for path in paths} == {
        ("outdoor", "west"),
        ("west", "outdoor"),
    }
    assert all(path["source_components"] for path in paths)


def test_one_zone_supply_exhaust_imbalance_is_detected_and_quantified() -> None:
    network = BuildingAirflowNetwork(
        outdoor_airflows_by_zone={
            "west": ZoneOutdoorAirflowRecord(
                zone_id="west",
                mixing_exchange_m3_h=100.0,
                outdoor_supply_m3_h=100.0,
                outdoor_exhaust_m3_h=90.0,
            )
        }
    )

    assert network.approximate_net_air_balance_by_zone_m3_h()["west"] == 10.0
    assert network.approximate_air_mass_residual_by_zone_kg_s()["west"] == (
        pytest.approx(10.0 * 1.2 / 3600.0)
    )
    assert not check_airflow_network_mass_balance(network)


def test_airnet_constant_flow_case_maps_only_the_prescribed_flow() -> None:
    # NISTIR 89-4072, Appendix B.7.1 prescribes 1.0 kg/s. With the
    # NexusEP diagnostic density convention, that is 3000 m3/h.
    prescribed_mass_flow_kg_s = 1.0
    air_density_kg_m3 = 1.2
    prescribed_flow_m3_h = (
        prescribed_mass_flow_kg_s / air_density_kg_m3 * 3600.0
    )
    record = ZoneOutdoorAirflowRecord(
        zone_id="reference-zone",
        mixing_exchange_m3_h=prescribed_flow_m3_h,
    )
    network = BuildingAirflowNetwork(
        outdoor_airflows_by_zone={"reference-zone": record}
    )

    for path in record.flow_paths():
        assert path["flow_m3_s"] * air_density_kg_m3 == pytest.approx(1.0)
    assert check_airflow_network_mass_balance(network)
    assert network.pressure_solution == AIRFLOW_NETWORK_PRESSURE_SOLVE
    assert network.pressure_solution == "not_solved"


def test_two_zone_exchange_is_reciprocal_and_every_flow_is_traceable() -> None:
    network = _two_zone_network(72.0)
    record = network.interzone_airflow_records["west-east"]

    assert record.flow_a_to_b_m3_h == pytest.approx(72.0)
    assert record.flow_b_to_a_m3_h == pytest.approx(72.0)
    assert record.net_a_to_b_m3_h == pytest.approx(0.0)
    assert network.interzone_mixing_by_zone_m3_h() == {
        "west": 72.0,
        "east": 72.0,
    }
    assert check_airflow_network_mass_balance(network)
    assert network.all_flow_paths_traceable()
    directed_endpoints = {
        (path["from_node_id"], path["to_node_id"])
        for path in record.flow_paths()
    }
    assert directed_endpoints == {
        ("west", "east"),
        ("east", "west"),
    }


def test_nist_two_opening_buoyancy_equation_69_is_implemented_directly() -> None:
    pressure_pa = 101_325.0
    density_20 = dry_air_density_kg_m3(20.0, pressure_pa)
    density_30 = dry_air_density_kg_m3(30.0, pressure_pa)
    height_m = 1.95
    width_m = 0.935
    area_m2 = height_m * width_m
    coefficient = 0.78
    reference_density = 0.5 * (density_20 + density_30)
    expected_mass_flow_kg_s = (
        coefficient
        / 3.0
        * width_m
        * sqrt(
            reference_density
            * 9.80665
            * abs(density_20 - density_30)
            * height_m**3
        )
    )

    actual_m3_s = two_opening_buoyancy_exchange_m3_s(
        opening_area_m2=area_m2,
        opening_height_m=height_m,
        discharge_coefficient=coefficient,
        zone_a_air_density_kg_m3=density_20,
        zone_b_air_density_kg_m3=density_30,
    )

    assert actual_m3_s * reference_density == pytest.approx(
        expected_mass_flow_kg_s, rel=1e-12
    )


def test_airnet_appendix_b6_buoyancy_doorway_matches_reported_streams() -> None:
    # NISTIR 89-4072 Appendix B.6: two zones at 18/22 degC connected by a
    # 0.8 m x 2.0 m opening with Cd=0.78. AIRNET reports approximately
    # 0.259 kg/s in each direction.
    pressure_pa = 101_325.0
    density_18 = dry_air_density_kg_m3(18.0, pressure_pa)
    density_22 = dry_air_density_kg_m3(22.0, pressure_pa)
    reference_density = 0.5 * (density_18 + density_22)
    volume_flow_m3_s = two_opening_buoyancy_exchange_m3_s(
        opening_area_m2=0.8 * 2.0,
        opening_height_m=2.0,
        discharge_coefficient=0.78,
        zone_a_air_density_kg_m3=density_18,
        zone_b_air_density_kg_m3=density_22,
    )

    assert volume_flow_m3_s * reference_density == pytest.approx(
        0.259, abs=0.001
    )


def test_two_opening_buoyancy_is_zero_at_equal_temperature_and_reciprocal() -> None:
    connection = ZoneConnection(
        connection_id="west-east-door",
        from_zone_id="west",
        to_zone_id="east",
        connection_type="door",
        area_m2=8.0,
        is_openable=True,
        max_opening_area_m2=1.5,
        airflow_model=INTERZONE_AIRFLOW_MODEL_TWO_OPENING_BUOYANCY,
        opening_height_m=2.0,
        discharge_coefficient=0.78,
    )
    opening = DoorOpeningInput(
        zone_connection_id=connection.connection_id,
        zone_a_id="west",
        zone_b_id="east",
        opening_fraction=1.0,
    )
    equal_state = BuildingThermalState(
        {
            "west": ZoneThermalState("west", 20.0, 20.0),
            "east": ZoneThermalState("east", 20.0, 20.0),
        }
    )
    unequal_state = BuildingThermalState(
        {
            "west": ZoneThermalState("west", 20.0, 20.0),
            "east": ZoneThermalState("east", 30.0, 30.0),
        }
    )

    equal = calculate_interzone_airflow_link(
        connection, opening, equal_state, 101_325.0
    )
    unequal = calculate_interzone_airflow_link(
        connection, opening, unequal_state, 101_325.0
    )
    swapped = calculate_interzone_airflow_link(
        connection,
        opening,
        BuildingThermalState(
            {
                "west": ZoneThermalState("west", 30.0, 30.0),
                "east": ZoneThermalState("east", 20.0, 20.0),
            }
        ),
        101_325.0,
    )

    assert equal.mixing_flow_m3_h == 0.0
    assert unequal.mixing_flow_m3_h > 0.0
    assert swapped.mixing_mass_flow_kg_s == pytest.approx(
        unequal.mixing_mass_flow_kg_s, rel=1e-12
    )
    assert unequal.source == INTERZONE_TWO_OPENING_SOURCE


def test_closed_two_zone_contaminant_exchange_conserves_total_amount() -> None:
    state = BuildingAirState(
        zone_states={
            "west": ZoneAirState("west", co2_ppm=900.0, air_volume_m3=60.0),
            "east": ZoneAirState("east", co2_ppm=400.0, air_volume_m3=120.0),
        }
    )
    amount_before_ppm_m3 = 900.0 * 60.0 + 400.0 * 120.0
    updated = _step_closed_two_zone_exchange(
        state,
        flow_m3_h=60.0,
        dt_minutes=60.0,
    )
    west_co2 = updated.get_zone_state("west").co2_ppm
    east_co2 = updated.get_zone_state("east").co2_ppm
    amount_after_ppm_m3 = west_co2 * 60.0 + east_co2 * 120.0

    assert amount_after_ppm_m3 == pytest.approx(amount_before_ppm_m3, abs=1e-9)
    assert 400.0 < east_co2 < west_co2 < 900.0
    assert min(west_co2, east_co2) >= 0.0


def test_unrecorded_interzone_flow_fails_the_traceability_gate() -> None:
    link = InterzoneAirflowLink(
        link_id="west-east",
        zone_connection_id="west-east",
        zone_a_id="west",
        zone_b_id="east",
        mixing_flow_m3_h=72.0,
    )
    network = BuildingAirflowNetwork(
        interzone_airflow_links={link.link_id: link},
    )

    assert not network.all_flow_paths_traceable()
    assert not check_airflow_network_mass_balance(network)


def test_coupled_contaminant_exchange_converges_as_timestep_decreases() -> None:
    west_volume_m3 = 60.0
    east_volume_m3 = 120.0
    flow_m3_s = 60.0 / 3600.0
    duration_s = 3600.0
    initial_west_ppm = 900.0
    initial_east_ppm = 400.0
    weighted_mean_ppm = (
        initial_west_ppm * west_volume_m3
        + initial_east_ppm * east_volume_m3
    ) / (west_volume_m3 + east_volume_m3)
    exact_difference_ppm = (
        initial_west_ppm - initial_east_ppm
    ) * exp(
        -flow_m3_s
        * (1.0 / west_volume_m3 + 1.0 / east_volume_m3)
        * duration_s
    )
    exact_west_ppm = weighted_mean_ppm + (
        east_volume_m3 / (west_volume_m3 + east_volume_m3)
    ) * exact_difference_ppm
    errors = []

    for dt_minutes in (30.0, 15.0, 5.0, 1.0, 0.25):
        state = BuildingAirState(
            zone_states={
                "west": ZoneAirState(
                    "west", initial_west_ppm, west_volume_m3
                ),
                "east": ZoneAirState(
                    "east", initial_east_ppm, east_volume_m3
                ),
            }
        )
        for _ in range(round(duration_s / (dt_minutes * 60.0))):
            state = _step_closed_two_zone_exchange(
                state,
                flow_m3_h=60.0,
                dt_minutes=dt_minutes,
            )
        errors.append(
            abs(state.get_zone_state("west").co2_ppm - exact_west_ppm)
        )

    assert errors == sorted(errors, reverse=True)
    assert errors[-1] < 0.4


def test_closed_window_and_zero_wind_produce_no_window_flow() -> None:
    window = _window()
    closed = calculate_window_airflow_opening_result(
        window,
        _window_state(1.0, is_open=False),
        _weather(wind_speed_m_s=2.0),
    )
    zero_wind = calculate_window_airflow_opening_result(
        window,
        _window_state(1.0),
        _weather(wind_speed_m_s=0.0),
    )

    assert closed.outdoor_airflow_m3_h == 0.0
    assert zero_wind.outdoor_airflow_m3_h == 0.0


def test_larger_window_opening_increases_supported_wind_driven_flow() -> None:
    window = _window()
    weather = _weather(wind_speed_m_s=0.5, wind_direction_deg=180.0)
    quarter_open = calculate_window_airflow_opening_result(
        window,
        _window_state(0.25),
        weather,
    )
    fully_open = calculate_window_airflow_opening_result(
        window,
        _window_state(1.0),
        weather,
    )

    assert 0.0 < quarter_open.outdoor_airflow_m3_h
    assert fully_open.outdoor_airflow_m3_h > quarter_open.outdoor_airflow_m3_h


def test_wind_direction_affects_only_the_supported_local_window_formulation() -> None:
    window = _window()
    state = _window_state(0.5)
    aligned = calculate_window_airflow_opening_result(
        window,
        state,
        _weather(wind_speed_m_s=0.5, wind_direction_deg=180.0),
    )
    perpendicular = calculate_window_airflow_opening_result(
        window,
        state,
        _weather(wind_speed_m_s=0.5, wind_direction_deg=90.0),
    )

    assert aligned.outdoor_airflow_m3_h > 0.0
    assert perpendicular.outdoor_airflow_m3_h == pytest.approx(0.0, abs=1e-12)
    assert AIRFLOW_WINDOW_MODEL == "wind_orientation_opening_approximation"
    assert AIRFLOW_PRESSURE_NETWORK_MODE == "not_pressure_network_yet"


def test_temperature_difference_does_not_imply_unsupported_buoyancy_flow() -> None:
    window = _window()
    state = _window_state(0.5)
    cold_outdoor = calculate_window_airflow_opening_result(
        window,
        state,
        _weather(outdoor_temperature_c=-10.0, wind_speed_m_s=0.5),
    )
    warm_outdoor = calculate_window_airflow_opening_result(
        window,
        state,
        _weather(outdoor_temperature_c=30.0, wind_speed_m_s=0.5),
    )

    assert cold_outdoor.outdoor_airflow_m3_h == pytest.approx(
        warm_outdoor.outdoor_airflow_m3_h,
        rel=1e-12,
    )
