"""Canonical version 1 output configuration and backend-neutral results."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from nexusep.schema.common import (
    CanonicalModel,
    ExternalID,
    FiniteFloat,
    NonnegativeFloat,
)


class OutputConfiguration(CanonicalModel):
    enabled: bool = True
    directory: Path
    formats: tuple[Literal["json", "csv", "npz"], ...] = ("json",)
    include_interval_timestamps: bool = True
    include_debug_graph: bool = False
    fields: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_unique_collections(self) -> OutputConfiguration:
        if len(self.formats) != len(set(self.formats)):
            raise ValueError("formats must be unique")
        if len(self.fields) != len(set(self.fields)):
            raise ValueError("fields must be unique")
        return self


class CanonicalWarning(CanonicalModel):
    code: Annotated[str, Field(min_length=1, max_length=128)]
    message: Annotated[str, Field(min_length=1)]
    entity_id: ExternalID | None


class ValidationProvenance(CanonicalModel):
    check: Annotated[str, Field(min_length=1, max_length=128)]
    status: Literal["passed", "warning"]
    detail: Annotated[str, Field(min_length=1)]


class AppliedDefault(CanonicalModel):
    target_path: Annotated[str, Field(pattern=r"^/")]
    value: Any
    reason: Annotated[str, Field(min_length=1)]


class CanonicalZoneStepResult(CanonicalModel):
    """Small required table shared by every engine."""

    scenario_id: ExternalID
    run_id: ExternalID
    building_id: ExternalID
    dwelling_id: ExternalID
    zone_id: ExternalID
    timestamp: datetime
    timestep_index: Annotated[int, Field(ge=0)]
    air_temperature_c: FiniteFloat
    relative_humidity_fraction: Annotated[
        float, Field(ge=0.0, le=1.0, allow_inf_nan=False)
    ]
    co2_ppm: Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
    occupancy_count: Annotated[int, Field(ge=0)]
    heating_power_w: NonnegativeFloat
    cooling_power_w: NonnegativeFloat
    ventilation_power_w: NonnegativeFloat
    lighting_power_w: NonnegativeFloat
    total_electrical_power_w: NonnegativeFloat
    engine_name: Literal["object", "array"]
    engine_version: Annotated[str, Field(min_length=1)]
    engine_status: Literal["completed", "completed_with_warnings"]
    fallback_used: bool
    fallback_reason: str | None

    @model_validator(mode="after")
    def validate_fallback(self) -> CanonicalZoneStepResult:
        if self.fallback_used != (self.fallback_reason is not None):
            raise ValueError(
                "fallback_reason must be present exactly when fallback_used"
            )
        return self


class ZoneEnergyResult(CanonicalModel):
    scenario_id: ExternalID
    run_id: ExternalID
    zone_id: ExternalID
    timestep_index: Annotated[int, Field(ge=0)]
    electrical_energy_wh: NonnegativeFloat


class DwellingEnergyResult(CanonicalModel):
    scenario_id: ExternalID
    run_id: ExternalID
    dwelling_id: ExternalID
    timestep_index: Annotated[int, Field(ge=0)]
    electrical_energy_wh: NonnegativeFloat


class BuildingEnergyResult(CanonicalModel):
    scenario_id: ExternalID
    run_id: ExternalID
    building_id: ExternalID
    timestep_index: Annotated[int, Field(ge=0)]
    electrical_energy_wh: NonnegativeFloat


class CanonicalDebugResult(CanonicalModel):
    engine_fields: dict[str, Any]


class CanonicalStepResult(CanonicalModel):
    scenario_id: ExternalID
    run_id: ExternalID
    timestamp: datetime
    timestep_index: Annotated[int, Field(ge=0)]
    dt_minutes: Annotated[float, Field(gt=0.0, allow_inf_nan=False)]
    zones: Annotated[tuple[CanonicalZoneStepResult, ...], Field(min_length=1)]
    zone_energy: Annotated[tuple[ZoneEnergyResult, ...], Field(min_length=1)]
    dwelling_energy: Annotated[tuple[DwellingEnergyResult, ...], Field(min_length=1)]
    building_energy: Annotated[tuple[BuildingEnergyResult, ...], Field(min_length=1)]
    warnings: tuple[CanonicalWarning, ...]
    validation_provenance: Annotated[
        tuple[ValidationProvenance, ...], Field(min_length=1)
    ]
    defaults_applied: tuple[AppliedDefault, ...]
    debug: CanonicalDebugResult | None

    @model_validator(mode="after")
    def validate_aggregates(self) -> CanonicalStepResult:
        zone_ids = [item.zone_id for item in self.zones]
        if zone_ids != sorted(zone_ids) or len(zone_ids) != len(set(zone_ids)):
            raise ValueError("zone results must have unique deterministic ordering")
        if {item.zone_id for item in self.zone_energy} != set(zone_ids):
            raise ValueError("zone energy coverage must match zone results")
        zone_total = sum(item.electrical_energy_wh for item in self.zone_energy)
        dwelling_total = sum(item.electrical_energy_wh for item in self.dwelling_energy)
        building_total = sum(item.electrical_energy_wh for item in self.building_energy)
        tolerance = 1.0e-9
        if abs(zone_total - dwelling_total) > tolerance:
            raise ValueError("zone and dwelling energy aggregates disagree")
        if abs(zone_total - building_total) > tolerance:
            raise ValueError("zone and building energy aggregates disagree")
        return self


class CanonicalRunMetadata(CanonicalModel):
    scenario_id: ExternalID
    run_id: ExternalID
    engine_name: Literal["object", "array"]
    engine_version: Annotated[str, Field(min_length=1)]
    schema_version: Literal["1.0.0"]
    graph_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    deterministic_seed: Annotated[int, Field(ge=0, le=4_294_967_295)]
    started_at: datetime
    timestep_count: Annotated[int, Field(ge=1)]
    dt_minutes: Annotated[float, Field(gt=0.0, allow_inf_nan=False)]


class ZoneEnergySummary(CanonicalModel):
    scenario_id: ExternalID
    run_id: ExternalID
    zone_id: ExternalID
    electrical_energy_wh: NonnegativeFloat


class DwellingEnergySummary(CanonicalModel):
    scenario_id: ExternalID
    run_id: ExternalID
    dwelling_id: ExternalID
    electrical_energy_wh: NonnegativeFloat


class BuildingEnergySummary(CanonicalModel):
    scenario_id: ExternalID
    run_id: ExternalID
    building_id: ExternalID
    electrical_energy_wh: NonnegativeFloat


class CanonicalRunResult(CanonicalModel):
    metadata: CanonicalRunMetadata
    steps: Annotated[tuple[CanonicalStepResult, ...], Field(min_length=1)]
    zone_energy: Annotated[tuple[ZoneEnergySummary, ...], Field(min_length=1)]
    dwelling_energy: Annotated[tuple[DwellingEnergySummary, ...], Field(min_length=1)]
    building_energy: Annotated[tuple[BuildingEnergySummary, ...], Field(min_length=1)]
    warnings: tuple[CanonicalWarning, ...]
    validation_provenance: Annotated[
        tuple[ValidationProvenance, ...], Field(min_length=1)
    ]

    @model_validator(mode="after")
    def validate_run(self) -> CanonicalRunResult:
        if len(self.steps) != self.metadata.timestep_count:
            raise ValueError("run step count does not match metadata")
        indices = [item.timestep_index for item in self.steps]
        if indices != sorted(indices) or len(indices) != len(set(indices)):
            raise ValueError("run steps must have unique deterministic ordering")
        if any(
            item.scenario_id != self.metadata.scenario_id
            or item.run_id != self.metadata.run_id
            for item in self.steps
        ):
            raise ValueError("run steps do not match run metadata identity")
        if any(item.dt_minutes != self.metadata.dt_minutes for item in self.steps):
            raise ValueError("run step duration does not match run metadata")
        zone_total = sum(item.electrical_energy_wh for item in self.zone_energy)
        dwelling_total = sum(item.electrical_energy_wh for item in self.dwelling_energy)
        building_total = sum(item.electrical_energy_wh for item in self.building_energy)
        if abs(zone_total - dwelling_total) > 1.0e-9:
            raise ValueError("run zone and dwelling energy summaries disagree")
        if abs(zone_total - building_total) > 1.0e-9:
            raise ValueError("run zone and building energy summaries disagree")
        return self


def aggregate_run_results(
    metadata: CanonicalRunMetadata,
    steps: tuple[CanonicalStepResult, ...],
) -> CanonicalRunResult:
    """Aggregate already validated step rows without backend-specific fields."""

    zone_totals: dict[str, float] = {}
    dwelling_totals: dict[str, float] = {}
    building_totals: dict[str, float] = {}
    warnings: list[CanonicalWarning] = []
    provenance: list[ValidationProvenance] = []
    for step in steps:
        warnings.extend(step.warnings)
        provenance.extend(step.validation_provenance)
        for item in step.zone_energy:
            zone_totals[item.zone_id] = (
                zone_totals.get(item.zone_id, 0.0) + item.electrical_energy_wh
            )
        for item in step.dwelling_energy:
            dwelling_totals[item.dwelling_id] = (
                dwelling_totals.get(item.dwelling_id, 0.0) + item.electrical_energy_wh
            )
        for item in step.building_energy:
            building_totals[item.building_id] = (
                building_totals.get(item.building_id, 0.0) + item.electrical_energy_wh
            )
    provenance.append(
        ValidationProvenance(
            check="run_energy_aggregation",
            status="passed",
            detail="step energy rows summed by original zone, dwelling, and building IDs",
        )
    )
    return CanonicalRunResult(
        metadata=metadata,
        steps=steps,
        zone_energy=tuple(
            ZoneEnergySummary(
                scenario_id=metadata.scenario_id,
                run_id=metadata.run_id,
                zone_id=entity_id,
                electrical_energy_wh=value,
            )
            for entity_id, value in sorted(zone_totals.items())
        ),
        dwelling_energy=tuple(
            DwellingEnergySummary(
                scenario_id=metadata.scenario_id,
                run_id=metadata.run_id,
                dwelling_id=entity_id,
                electrical_energy_wh=value,
            )
            for entity_id, value in sorted(dwelling_totals.items())
        ),
        building_energy=tuple(
            BuildingEnergySummary(
                scenario_id=metadata.scenario_id,
                run_id=metadata.run_id,
                building_id=entity_id,
                electrical_energy_wh=value,
            )
            for entity_id, value in sorted(building_totals.items())
        ),
        warnings=tuple(warnings),
        validation_provenance=tuple(provenance),
    )


REQUIRED_ZONE_OUTPUT_FIELDS = tuple(CanonicalZoneStepResult.model_fields)


__all__ = [
    "REQUIRED_ZONE_OUTPUT_FIELDS",
    "AppliedDefault",
    "BuildingEnergyResult",
    "BuildingEnergySummary",
    "CanonicalDebugResult",
    "CanonicalRunMetadata",
    "CanonicalRunResult",
    "CanonicalStepResult",
    "CanonicalWarning",
    "CanonicalZoneStepResult",
    "DwellingEnergyResult",
    "DwellingEnergySummary",
    "OutputConfiguration",
    "ValidationProvenance",
    "ZoneEnergyResult",
    "ZoneEnergySummary",
    "aggregate_run_results",
]
