"""Annex 71 canonical mapping and production-adapter regressions.

Validation category: verification of preprocessing and execution semantics.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from nexusep.validation_data.annex71 import (
    Annex71Interval,
    Annex71ZoneObservation,
    build_canonical_scenario,
    run_object_scenario,
)

ZONE_IDS = (
    "ground_airbody",
    "kitchen_airbody",
    "sleeping_airbody",
    "attic_airbody",
)


def _record(timestamp: datetime, temperature_c: float) -> Annex71Interval:
    return Annex71Interval(
        timestamp=timestamp,
        outdoor_temperature_c=10.0,
        relative_humidity_fraction=0.5,
        atmospheric_pressure_pa=95_000.0,
        outdoor_co2_ppm=420.0,
        wind_speed_m_s=0.0,
        wind_direction_deg=0.0,
        diffuse_horizontal_radiation_w_m2=0.0,
        global_horizontal_radiation_w_m2=0.0,
        rain=False,
        zones=tuple(
            Annex71ZoneObservation(
                zone_id=zone_id,
                air_temperature_c=temperature_c,
                relative_humidity_fraction=0.5,
                heating_power_w=0.0,
                internal_gain_w=0.0,
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
