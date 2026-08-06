"""Canonical scenario model shared by version dispatch and loaders."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from nexusep.schema.common import (
    CanonicalModel,
    ExternalID,
    ScenarioMetadata,
    SimulationPeriod,
)
from nexusep.schema.geometry import Building, GeometryConfiguration
from nexusep.schema.outputs import OutputConfiguration
from nexusep.schema.weather import WeatherSource, WeatherState


class ScheduleEntry(CanonicalModel):
    start_timestep_index: Annotated[int, Field(ge=0)]
    end_timestep_index: Annotated[int, Field(ge=1)]
    zone_id: ExternalID
    activity: Literal["away", "awake", "sleeping"]


class Occupant(CanonicalModel):
    scenario_id: ExternalID
    building_id: ExternalID
    occupant_id: ExternalID
    dwelling_id: ExternalID
    home_zone_id: ExternalID
    sleep_zone_id: ExternalID
    sensible_heat_gain_w: Annotated[
        float, Field(ge=0.0, le=1_000.0, allow_inf_nan=False)
    ]
    co2_generation_kg_s: Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
    moisture_generation_kg_s: Annotated[
        float, Field(ge=0.0, le=1.0, allow_inf_nan=False)
    ]
    location_schedule: Annotated[tuple[ScheduleEntry, ...], Field(min_length=1)]


class ScenarioV1(CanonicalModel):
    """Complete strict canonical scenario schema version 1."""

    schema_version: Literal["1.0.0"]
    use_case: Literal["multizone_dwelling_v1"]
    scenario_id: ExternalID
    metadata: ScenarioMetadata
    deterministic_seed: Annotated[int, Field(ge=0, le=4_294_967_295)]
    simulation_period: SimulationPeriod
    geometry_configuration: GeometryConfiguration
    building: Building
    occupants: Annotated[tuple[Occupant, ...], Field(min_length=2)]
    weather_source: WeatherSource
    weather_series: tuple[WeatherState, ...]
    output_configuration: OutputConfiguration


CanonicalScenario = ScenarioV1
