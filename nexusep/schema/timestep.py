"""Typed canonical boundary for one simulation timestep.

The models in this module contain only values that are available before a
backend starts.  Backend-derived intermediates deliberately live in
``DerivedStepValues`` and cannot be smuggled into ``SimulationStepInput``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from nexusep.schema.common import (
    CanonicalModel,
    ExternalID,
    FiniteFloat,
    Fraction,
    NonnegativeFloat,
)
from nexusep.schema.compiler import validate_compiled_graph
from nexusep.schema.scenario import CanonicalScenario
from nexusep.schema.weather import WeatherState


class CanonicalStepContractError(ValueError):
    """Raised when a typed step does not cover its canonical scenario exactly."""


class CanonicalGraphReference(CanonicalModel):
    scenario_id: ExternalID
    compiled_graph_version: Literal["1.0.0"]
    graph_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class PriorZonePhysicalState(CanonicalModel):
    zone_id: ExternalID
    air_temperature_c: Annotated[float, Field(ge=-100.0, le=100.0, allow_inf_nan=False)]
    mean_radiant_temperature_c: Annotated[
        float, Field(ge=-100.0, le=100.0, allow_inf_nan=False)
    ]
    relative_humidity_fraction: Fraction
    co2_ppm: Annotated[float, Field(ge=0.0, le=100_000.0, allow_inf_nan=False)]


class OccupantStepState(CanonicalModel):
    occupant_id: ExternalID
    dwelling_id: ExternalID
    zone_id: ExternalID
    activity: Literal["away", "awake", "sleeping"]
    is_present: bool

    @model_validator(mode="after")
    def validate_presence(self) -> OccupantStepState:
        if self.activity == "away" and self.is_present:
            raise ValueError("an away occupant cannot be present in a zone")
        if self.activity != "away" and not self.is_present:
            raise ValueError("a non-away occupant must be present in a zone")
        return self


class ActionEvent(CanonicalModel):
    event_id: ExternalID
    action: Annotated[str, Field(min_length=1, max_length=128)]
    occupant_id: ExternalID | None
    zone_id: ExternalID | None
    status: Literal["started", "active", "completed", "cancelled"]


class InternalGain(CanonicalModel):
    source_id: ExternalID
    source_kind: Literal["occupant", "activity", "appliance", "lighting", "other"]
    zone_id: ExternalID
    sensible_heat_w: FiniteFloat
    latent_heat_w: FiniteFloat
    electrical_power_w: NonnegativeFloat
    co2_generation_kg_s: NonnegativeFloat
    moisture_generation_kg_s: NonnegativeFloat


class ExternalBoundaryState(CanonicalModel):
    """Temperature prescribed for a named non-weather exterior boundary."""

    boundary_id: ExternalID
    temperature_c: Annotated[
        float, Field(ge=-100.0, le=100.0, allow_inf_nan=False)
    ]


class OpeningControlCommand(CanonicalModel):
    """Dynamic state for one canonical exterior opening.

    Zone-level controls remain useful defaults.  This command is the explicit
    override for experiments and controllers that operate individual windows
    or blinds.
    """

    opening_id: ExternalID
    opening_fraction: Fraction
    shading_open_fraction: Fraction = 1.0


class InterzoneOpeningControl(CanonicalModel):
    """Dynamic opening fraction for one canonical interzone surface pair."""

    surface_id: ExternalID
    opening_fraction: Fraction


class ZoneControlCommand(CanonicalModel):
    zone_id: ExternalID
    heating_on: bool
    heating_power_fraction: Fraction
    heating_convective_fraction: Fraction = 1.0
    cooling_on: bool
    cooling_power_fraction: Fraction
    cooling_convective_fraction: Fraction = 1.0
    ventilation_volume_flow_m3_s: NonnegativeFloat
    ventilation_supply_temperature_c: Annotated[
        float, Field(ge=-100.0, le=100.0, allow_inf_nan=False)
    ] | None = None
    ventilation_exhaust_volume_flow_m3_s: NonnegativeFloat | None = None
    lights_on: bool
    lighting_power_w: NonnegativeFloat
    window_opening_fraction: Fraction
    shading_open_fraction: Fraction

    @model_validator(mode="after")
    def validate_switches(self) -> ZoneControlCommand:
        if not self.heating_on and self.heating_power_fraction != 0.0:
            raise ValueError("heating_power_fraction must be zero when heating is off")
        if not self.cooling_on and self.cooling_power_fraction != 0.0:
            raise ValueError("cooling_power_fraction must be zero when cooling is off")
        if not self.lights_on and self.lighting_power_w != 0.0:
            raise ValueError("lighting_power_w must be zero when lights are off")
        if self.heating_on and self.cooling_on:
            raise ValueError("heating and cooling cannot be on simultaneously")
        return self


class SystemAvailability(CanonicalModel):
    system_id: ExternalID
    available: bool
    capacity_fraction: Fraction

    @model_validator(mode="after")
    def validate_capacity(self) -> SystemAvailability:
        if not self.available and self.capacity_fraction != 0.0:
            raise ValueError("capacity_fraction must be zero when unavailable")
        return self


class DeterministicRunContext(CanonicalModel):
    run_id: ExternalID
    deterministic_seed: Annotated[int, Field(ge=0, le=4_294_967_295)]
    random_stream_position: Annotated[int, Field(ge=0)]
    timezone: Annotated[str, Field(min_length=1)]


class SimulationStepInput(CanonicalModel):
    """Complete immutable input at the canonical runner boundary."""

    scenario_id: ExternalID
    timestep_index: Annotated[int, Field(ge=0)]
    timestamp: datetime
    dt_minutes: Annotated[float, Field(gt=0.0, le=60.0, allow_inf_nan=False)]
    weather: WeatherState
    prior_zone_states: Annotated[
        tuple[PriorZonePhysicalState, ...], Field(min_length=1)
    ]
    occupant_states: tuple[OccupantStepState, ...]
    action_events: tuple[ActionEvent, ...]
    internal_gains: tuple[InternalGain, ...]
    external_boundary_states: tuple[ExternalBoundaryState, ...] = ()
    opening_control_commands: tuple[OpeningControlCommand, ...] = ()
    interzone_opening_controls: tuple[InterzoneOpeningControl, ...] = ()
    control_commands: Annotated[tuple[ZoneControlCommand, ...], Field(min_length=1)]
    system_availability: Annotated[tuple[SystemAvailability, ...], Field(min_length=1)]
    graph: CanonicalGraphReference
    run_context: DeterministicRunContext

    @model_validator(mode="after")
    def validate_local_identity(self) -> SimulationStepInput:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must include an explicit UTC offset")
        if self.weather.scenario_id != self.scenario_id:
            raise ValueError("weather scenario_id does not match step scenario_id")
        if self.weather.timestep_index != self.timestep_index:
            raise ValueError("weather timestep_index does not match the step")
        if self.weather.timestamp != self.timestamp:
            raise ValueError("weather timestamp does not match the step")
        if self.graph.scenario_id != self.scenario_id:
            raise ValueError("graph scenario_id does not match the step")
        for label, values, key in (
            ("prior_zone_states", self.prior_zone_states, "zone_id"),
            ("occupant_states", self.occupant_states, "occupant_id"),
            ("action_events", self.action_events, "event_id"),
            ("internal_gains", self.internal_gains, "source_id"),
            ("external_boundary_states", self.external_boundary_states, "boundary_id"),
            ("opening_control_commands", self.opening_control_commands, "opening_id"),
            (
                "interzone_opening_controls",
                self.interzone_opening_controls,
                "surface_id",
            ),
            ("control_commands", self.control_commands, "zone_id"),
            ("system_availability", self.system_availability, "system_id"),
        ):
            identifiers = [getattr(value, key) for value in values]
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"{label} contains duplicate {key} values")
        return self

    @property
    def time_index(self) -> int:
        """Read-only compatibility spelling; canonical serialization uses timestep_index."""

        return self.timestep_index


class DerivedStepValues(BaseModel):
    """Backend-owned scratch values, intentionally absent from step input."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    values_by_zone: dict[str, dict[str, float]] = Field(default_factory=dict)
    diagnostics: dict[str, str] = Field(default_factory=dict)


def validate_step_input_for_scenario(
    step_input: SimulationStepInput,
    scenario: CanonicalScenario,
    compiled_graph: dict[str, object],
) -> None:
    """Reject missing, invented, or misaligned values before adapter encoding."""

    if not isinstance(step_input, SimulationStepInput):
        raise TypeError(
            "step_input must be SimulationStepInput; mappings are not accepted"
        )
    if not isinstance(scenario, CanonicalScenario):
        raise TypeError("scenario must be a validated CanonicalScenario")
    validate_compiled_graph(compiled_graph)

    period = scenario.simulation_period
    if step_input.scenario_id != scenario.scenario_id:
        raise CanonicalStepContractError("step scenario_id does not match scenario")
    if step_input.timestep_index >= period.n_timesteps:
        raise CanonicalStepContractError(
            "timestep_index is outside the simulation period"
        )
    expected_timestamp = period.start_datetime + timedelta(
        minutes=period.dt_minutes * step_input.timestep_index
    )
    if step_input.timestamp != expected_timestamp:
        raise CanonicalStepContractError(
            "timestamp is not the canonical interval start"
        )
    if step_input.dt_minutes != period.dt_minutes:
        raise CanonicalStepContractError("dt_minutes does not match the scenario")
    if step_input.run_context.deterministic_seed != scenario.deterministic_seed:
        raise CanonicalStepContractError("run seed does not match the scenario")
    if step_input.run_context.timezone != period.timezone:
        raise CanonicalStepContractError("run timezone does not match the scenario")
    if step_input.graph.graph_sha256 != compiled_graph["graph_sha256"]:
        raise CanonicalStepContractError("graph digest does not match compiled graph")
    if (
        step_input.graph.compiled_graph_version
        != compiled_graph["compiled_graph_version"]
    ):
        raise CanonicalStepContractError("compiled graph version does not match")

    dwelling = scenario.building.dwelling
    expected_zones = {zone.zone_id for zone in dwelling.zones}
    expected_occupants = {occupant.occupant_id for occupant in scenario.occupants}
    expected_systems = {
        system.system_id for zone in dwelling.zones for system in zone.systems
    }
    expected_external_boundaries = {
        str(connection.get("external_boundary_id"))
        for connection in compiled_graph["connections"]
        if connection.get("boundary_type") == "exterior"
        and connection.get("external_boundary_id") not in {None, "outdoor_air"}
    }
    connections = [dict(item) for item in compiled_graph["connections"]]
    opening_connections = {
        str(connection["opening_ids"][0]): connection
        for connection in connections
        if connection.get("connection_type") == "opening"
    }
    interzone_connections_by_surface = {
        str(surface_id): connection
        for connection in connections
        if connection.get("boundary_type") == "interzone"
        for surface_id in connection.get("surface_ids", [])
    }

    def require_exact(label: str, supplied: set[str], expected: set[str]) -> None:
        if supplied != expected:
            raise CanonicalStepContractError(
                f"{label} coverage mismatch: missing={sorted(expected - supplied)}, "
                f"invented={sorted(supplied - expected)}"
            )

    require_exact(
        "prior zone state",
        {item.zone_id for item in step_input.prior_zone_states},
        expected_zones,
    )
    require_exact(
        "zone control command",
        {item.zone_id for item in step_input.control_commands},
        expected_zones,
    )
    require_exact(
        "occupant state",
        {item.occupant_id for item in step_input.occupant_states},
        expected_occupants,
    )
    require_exact(
        "system availability",
        {item.system_id for item in step_input.system_availability},
        expected_systems,
    )
    require_exact(
        "external boundary state",
        {item.boundary_id for item in step_input.external_boundary_states},
        expected_external_boundaries,
    )

    for occupant_state in step_input.occupant_states:
        if occupant_state.dwelling_id != dwelling.dwelling_id:
            raise CanonicalStepContractError("occupant references the wrong dwelling")
        if occupant_state.zone_id not in expected_zones:
            raise CanonicalStepContractError("occupant references an unknown zone")
    for event in step_input.action_events:
        if (
            event.occupant_id is not None
            and event.occupant_id not in expected_occupants
        ):
            raise CanonicalStepContractError(
                "action event references an unknown occupant"
            )
        if event.zone_id is not None and event.zone_id not in expected_zones:
            raise CanonicalStepContractError("action event references an unknown zone")
    for gain in step_input.internal_gains:
        if gain.zone_id not in expected_zones:
            raise CanonicalStepContractError("internal gain references an unknown zone")
    for command in step_input.opening_control_commands:
        connection = opening_connections.get(command.opening_id)
        if connection is None:
            raise CanonicalStepContractError(
                f"opening control references unknown opening {command.opening_id!r}"
            )
        if (
            command.opening_fraction > 0.0
            and float(connection.get("openable_area_m2", 0.0)) <= 0.0
        ):
            raise CanonicalStepContractError(
                f"opening {command.opening_id!r} is not declared openable"
            )
    controlled_interzone_connections: set[str] = set()
    for command in step_input.interzone_opening_controls:
        connection = interzone_connections_by_surface.get(command.surface_id)
        if connection is None:
            raise CanonicalStepContractError(
                f"interzone control references unknown surface {command.surface_id!r}"
            )
        if float(connection.get("airflow_opening_area_m2", 0.0)) <= 0.0:
            raise CanonicalStepContractError(
                f"interzone surface {command.surface_id!r} has no airflow opening"
            )
        connection_id = str(connection["connection_id"])
        if connection_id in controlled_interzone_connections:
            raise CanonicalStepContractError(
                "both faces of one interzone opening were controlled; provide one "
                "canonical surface ID per connection"
            )
        controlled_interzone_connections.add(connection_id)

    availability = {item.system_id: item for item in step_input.system_availability}
    controls = {item.zone_id: item for item in step_input.control_commands}
    for zone in dwelling.zones:
        systems = {item.system_type: item for item in zone.systems}
        control = controls[zone.zone_id]

        def available_capacity(
            system_type: str, field_name: str, zone_systems=systems
        ) -> float:
            system = zone_systems[system_type]
            installed = getattr(system, field_name)
            if installed is None:
                raise CanonicalStepContractError(
                    f"{system_type} system is missing {field_name}"
                )
            return float(installed) * availability[system.system_id].capacity_fraction

        if (
            control.heating_on
            and available_capacity("heating", "max_heating_power_w") == 0.0
        ):
            raise CanonicalStepContractError(
                f"zone {zone.zone_id} requests unavailable heating"
            )
        if (
            control.cooling_on
            and available_capacity("cooling", "max_cooling_power_w") == 0.0
        ):
            raise CanonicalStepContractError(
                f"zone {zone.zone_id} requests unavailable cooling"
            )
        maximum_ventilation = available_capacity(
            "ventilation", "max_ventilation_volume_flow_m3_s"
        )
        if control.ventilation_volume_flow_m3_s > maximum_ventilation + 1.0e-12:
            raise CanonicalStepContractError(
                f"zone {zone.zone_id} ventilation command exceeds available capacity"
            )
        if (
            control.ventilation_exhaust_volume_flow_m3_s is not None
            and control.ventilation_exhaust_volume_flow_m3_s
            > maximum_ventilation + 1.0e-12
        ):
            raise CanonicalStepContractError(
                f"zone {zone.zone_id} ventilation exhaust command exceeds available capacity"
            )
        maximum_lighting = available_capacity("lighting", "max_lighting_power_w")
        if control.lighting_power_w > maximum_lighting + 1.0e-12:
            raise CanonicalStepContractError(
                f"zone {zone.zone_id} lighting command exceeds available capacity"
            )


__all__ = [
    "ActionEvent",
    "CanonicalGraphReference",
    "CanonicalStepContractError",
    "DerivedStepValues",
    "DeterministicRunContext",
    "ExternalBoundaryState",
    "InternalGain",
    "InterzoneOpeningControl",
    "OccupantStepState",
    "OpeningControlCommand",
    "PriorZonePhysicalState",
    "SimulationStepInput",
    "SystemAvailability",
    "ZoneControlCommand",
    "validate_step_input_for_scenario",
]
