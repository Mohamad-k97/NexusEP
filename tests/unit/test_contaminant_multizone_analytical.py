"""Control-volume verification for two- and three-zone CO2 transport."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nexusep.abbey.building.physics.airflow import (
    OUTDOOR_AIRFLOW_SOURCE_MECHANICAL,
    BuildingAirflowNetwork,
    BuildingAirState,
    BuildingCO2GenerationResult,
    InterzoneAirflowLink,
    InterzoneAirflowRecord,
    ZoneAirState,
    ZoneCO2GenerationRecord,
    ZoneOutdoorAirflowRecord,
    step_building_co2_state,
)
from nexusep.abbey.building.physics.weather import WeatherState

pytestmark = [pytest.mark.unit]
VALIDATION_CATEGORY = "verification"
OUTDOOR_CO2_PPM = 420.0


def _weather() -> WeatherState:
    return WeatherState(
        datetime=datetime(2025, 1, 1, tzinfo=UTC),
        outdoor_co2_ppm=OUTDOOR_CO2_PPM,
    )


def _link(
    link_id: str,
    zone_a_id: str,
    zone_b_id: str,
    flow_m3_h: float,
) -> tuple[InterzoneAirflowLink, InterzoneAirflowRecord]:
    link = InterzoneAirflowLink(
        link_id=link_id,
        zone_connection_id=link_id,
        zone_a_id=zone_a_id,
        zone_b_id=zone_b_id,
        mixing_flow_m3_h=flow_m3_h,
    )
    record = InterzoneAirflowRecord(
        link_id=link_id,
        zone_connection_id=link_id,
        zone_a_id=zone_a_id,
        zone_b_id=zone_b_id,
        flow_a_to_b_m3_h=flow_m3_h,
        flow_b_to_a_m3_h=flow_m3_h,
    )
    return link, record


def _generation(**generation_m3_h_by_zone: float) -> BuildingCO2GenerationResult:
    return BuildingCO2GenerationResult(
        zone_records={
            zone_id: ZoneCO2GenerationRecord(
                zone_id=zone_id,
                co2_generation_m3_h=generation_m3_h,
                source="phase_4_14__" + zone_id,
            )
            for zone_id, generation_m3_h in generation_m3_h_by_zone.items()
        }
    )


def _interzone_transport_rate_m3_s(result) -> float:
    return sum(
        target.airflow_m3_s
        * (target.co2_ppm - zone_result.new_co2_ppm)
        / 1e6
        for zone_result in result.zone_results.values()
        for target in zone_result.targets
        if target.target_type == "interzone_air"
    )


def _assert_every_control_volume_balances(result) -> None:
    for zone_result in result.zone_results.values():
        assert zone_result.balance_residual_m3_s() == pytest.approx(
            0.0,
            abs=3e-18,
        )
    assert result.balance_residual_m3_s() == pytest.approx(0.0, abs=5e-18)
    assert _interzone_transport_rate_m3_s(result) == pytest.approx(
        0.0,
        abs=3e-18,
    )


def test_two_zone_source_attribution_exchange_and_outdoor_dilution() -> None:
    link, record = _link("west-east", "west", "east", 60.0)
    network = BuildingAirflowNetwork(
        outdoor_airflows_by_zone={
            "west": ZoneOutdoorAirflowRecord(
                zone_id="west",
                infiltration_flow_m3_h=20.0,
            ),
            "east": ZoneOutdoorAirflowRecord(
                zone_id="east",
                mechanical_ventilation_flow_m3_h=30.0,
            ),
        },
        interzone_airflow_links={link.link_id: link},
        interzone_airflow_records={record.link_id: record},
    )
    state = BuildingAirState(
        zone_states={
            "west": ZoneAirState("west", 900.0, 60.0),
            "east": ZoneAirState("east", 420.0, 120.0),
        }
    )
    result = step_building_co2_state(
        air_state=state,
        airflow_network=network,
        co2_generation_result=_generation(west=0.018, east=0.0),
        weather_state=_weather(),
        dt_minutes=15.0,
    )

    _assert_every_control_volume_balances(result)
    assert result.zone_results["west"].co2_generation_m3_s > 0.0
    assert result.zone_results["west"].generation_source == "phase_4_14__west"
    assert result.zone_results["east"].co2_generation_m3_s == 0.0
    assert {target.target_type for target in result.zone_results["west"].targets} == {
        "outdoor_air",
        "interzone_air",
    }
    assert OUTDOOR_AIRFLOW_SOURCE_MECHANICAL in (
        network.outdoor_airflows_by_zone["east"].active_sources()
    )
    assert network.all_flow_paths_traceable()


def test_well_mixed_two_zone_model_has_immediate_response_not_transport_delay() -> None:
    link, record = _link("source-receiver", "source", "receiver", 30.0)
    network = BuildingAirflowNetwork(
        interzone_airflow_links={link.link_id: link},
        interzone_airflow_records={record.link_id: record},
    )
    state = BuildingAirState(
        zone_states={
            "source": ZoneAirState("source", 1400.0, 50.0),
            "receiver": ZoneAirState("receiver", 420.0, 50.0),
        }
    )
    result = step_building_co2_state(
        air_state=state,
        airflow_network=network,
        co2_generation_result=_generation(source=0.0, receiver=0.0),
        weather_state=_weather(),
        dt_minutes=1.0,
    )

    _assert_every_control_volume_balances(result)
    assert result.co2_by_zone_ppm()["receiver"] > 420.0
    assert result.co2_by_zone_ppm()["source"] < 1400.0


def test_three_zone_chain_reconciles_storage_generation_and_removal_each_step() -> None:
    link_ab, record_ab = _link("a-b", "a", "b", 36.0)
    link_bc, record_bc = _link("b-c", "b", "c", 54.0)
    network = BuildingAirflowNetwork(
        outdoor_airflows_by_zone={
            "a": ZoneOutdoorAirflowRecord(
                zone_id="a",
                infiltration_flow_m3_h=12.0,
            ),
            "b": ZoneOutdoorAirflowRecord(zone_id="b"),
            "c": ZoneOutdoorAirflowRecord(
                zone_id="c",
                mechanical_ventilation_flow_m3_h=72.0,
            ),
        },
        interzone_airflow_links={
            link_ab.link_id: link_ab,
            link_bc.link_id: link_bc,
        },
        interzone_airflow_records={
            record_ab.link_id: record_ab,
            record_bc.link_id: record_bc,
        },
    )
    state = BuildingAirState(
        zone_states={
            "a": ZoneAirState("a", 420.0, 40.0),
            "b": ZoneAirState("b", 500.0, 80.0),
            "c": ZoneAirState("c", 700.0, 120.0),
        }
    )
    generation = _generation(a=0.018, b=0.009, c=0.0)

    for _ in range(24):
        result = step_building_co2_state(
            air_state=state,
            airflow_network=network,
            co2_generation_result=generation,
            weather_state=_weather(),
            dt_minutes=5.0,
        )
        _assert_every_control_volume_balances(result)
        assert result.total_storage_change_m3_s() == pytest.approx(
            result.total_generation_m3_s() + result.total_transport_rate_m3_s(),
            abs=5e-18,
        )
        assert all(
            value >= OUTDOOR_CO2_PPM
            for value in result.co2_by_zone_ppm().values()
        )
        state = result.updated_air_state

    assert result.co2_by_zone_ppm()["c"] < 700.0
    assert result.co2_by_zone_ppm()["a"] > OUTDOOR_CO2_PPM
