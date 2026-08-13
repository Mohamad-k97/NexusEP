"""Annex 71 canonical mapping and production-adapter regressions.

Validation category: verification of preprocessing and execution semantics.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from nexusep.validation_data.annex71 import (
    Annex71Interval,
    Annex71ZoneObservation,
    build_canonical_scenario,
    run_object_scenario,
    zone_capacity_fractions,
)
from nexusep.validation_data.annex71_audit import (
    audit_annex71_energy_paths,
    shift_annex71_source_rows,
)

ZONE_IDS = (
    "ground_airbody",
    "kitchen_airbody",
    "sleeping_airbody",
    "attic_airbody",
)


def _record(
    timestamp: datetime,
    temperature_c: float,
    *,
    heating_power_w: float = 0.0,
    internal_gain_w: float = 0.0,
    solar_w_m2: float = 0.0,
) -> Annex71Interval:
    return Annex71Interval(
        timestamp=timestamp,
        outdoor_temperature_c=10.0,
        relative_humidity_fraction=0.5,
        atmospheric_pressure_pa=95_000.0,
        outdoor_co2_ppm=420.0,
        wind_speed_m_s=0.0,
        wind_direction_deg=0.0,
        diffuse_horizontal_radiation_w_m2=solar_w_m2 * 0.25,
        global_horizontal_radiation_w_m2=solar_w_m2,
        rain=False,
        zones=tuple(
            Annex71ZoneObservation(
                zone_id=zone_id,
                air_temperature_c=temperature_c,
                relative_humidity_fraction=0.5,
                heating_power_w=heating_power_w,
                internal_gain_w=internal_gain_w,
                ventilation_supply_temperature_c=10.0,
                ventilation_supply_flow_m3_s=0.0,
            )
            for zone_id in ZONE_IDS
        ),
    )


def test_selected_hourly_alignment_maps_row_timestamp_to_interval_end() -> None:
    end = datetime(2018, 12, 20, 1, tzinfo=ZoneInfo("Europe/Berlin"))
    record = _record(end, 20.0)

    scenario, _graph = build_canonical_scenario((record,))

    assert scenario.simulation_period.start_datetime == end - timedelta(hours=1)
    assert scenario.weather_series[0].timestamp == end - timedelta(hours=1)


def test_four_air_bodies_execute_without_fallback_and_conserve_energy() -> None:
    start = datetime(2018, 12, 20, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    records = tuple(_record(start + timedelta(hours=index), 20.0) for index in range(3))

    result = run_object_scenario(records)

    assert result.engine_name == "object"
    assert set(result.simulated_temperature_c) == set(ZONE_IDS)
    assert result.timestamps == tuple(
        item.timestamp.isoformat() for item in records[1:]
    )
    assert result.fallback_used is False
    assert result.maximum_abs_thermal_balance_residual_w <= 1.0e-7


def test_observation_constrained_energy_audit_closes_steady_no_gain_case() -> None:
    start = datetime(2018, 12, 20, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    records = tuple(_record(start + timedelta(hours=index), 10.0) for index in range(3))

    audit = audit_annex71_energy_paths(records, warmup_timesteps=0)

    assert len(audit.records) == 8
    assert audit.summary["whole_building"]["unexplained_gain_rmse_w"] <= 1.0e-9
    assert all(abs(item.unexplained_air_node_gain_w) <= 1.0e-9 for item in audit.records)


def test_source_row_counterfactual_preserves_targets_and_common_period() -> None:
    start = datetime(2018, 12, 20, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    records = tuple(
        _record(
            start + timedelta(hours=index),
            20.0 + index,
            heating_power_w=100.0 * index,
            internal_gain_w=10.0 * index,
            solar_w_m2=50.0 * index,
        )
        for index in range(5)
    )

    shifted = shift_annex71_source_rows(records, "heating", 1)

    assert [item.timestamp for item in shifted] == [
        records[1].timestamp,
        records[2].timestamp,
        records[3].timestamp,
    ]
    assert shifted[0].zone("attic_airbody").air_temperature_c == 21.0
    assert shifted[0].zone("attic_airbody").heating_power_w == 200.0
    assert shifted[0].zone("attic_airbody").internal_gain_w == 10.0
    assert shifted[0].global_horizontal_radiation_w_m2 == 50.0


def test_capacity_allocation_bases_are_explicit_and_conservative() -> None:
    volume = zone_capacity_fractions("air_volume")
    floor = zone_capacity_fractions("floor_area")

    assert sum(volume.values()) == pytest.approx(1.0)
    assert sum(floor.values()) == pytest.approx(1.0)
    assert floor["attic_airbody"] > volume["attic_airbody"]


def test_roof_window_uses_published_thirty_degree_tilt() -> None:
    timestamp = datetime(2018, 12, 20, 1, tzinfo=ZoneInfo("Europe/Berlin"))

    scenario, graph = build_canonical_scenario((_record(timestamp, 20.0),))
    attic = next(
        zone
        for zone in scenario.building.dwelling.zones
        if zone.zone_id == "attic_airbody"
    )
    roof_surface = next(
        surface
        for surface in attic.surfaces
        if surface.boundary_type == "exterior" and surface.azimuth_deg == 180.0
    )
    roof_connection = next(
        connection
        for connection in graph["connections"]
        if connection["connection_type"] == "opening"
        and connection["source_node_id"] == "attic_airbody"
        and connection["azimuth_deg"] == 180.0
    )

    assert roof_surface.tilt_deg == pytest.approx(30.0)
    assert roof_connection["tilt_deg"] == pytest.approx(30.0)
    assert all(
        surface.tilt_deg == pytest.approx(90.0)
        for surface in attic.surfaces
        if surface is not roof_surface
    )
