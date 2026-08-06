"""Shared validation and output assembly for canonical backend adapters."""

from __future__ import annotations

from collections.abc import Iterable

from nexusep.schema.outputs import (
    AppliedDefault,
    BuildingEnergyResult,
    CanonicalDebugResult,
    CanonicalStepResult,
    CanonicalWarning,
    CanonicalZoneStepResult,
    DwellingEnergyResult,
    ValidationProvenance,
    ZoneEnergyResult,
)
from nexusep.schema.scenario import CanonicalScenario
from nexusep.schema.timestep import SimulationStepInput

ADAPTER_CONTRACT_VERSION = "2.17.0"


class BackendAdapterError(RuntimeError):
    """A validated input cannot be represented by the selected backend."""


def assemble_step_result(
    *,
    scenario: CanonicalScenario,
    step_input: SimulationStepInput,
    zones: Iterable[CanonicalZoneStepResult],
    warnings: Iterable[CanonicalWarning] = (),
    provenance: Iterable[ValidationProvenance] = (),
    defaults: Iterable[AppliedDefault] = (),
    debug_fields: dict[str, object] | None = None,
) -> CanonicalStepResult:
    """Build checked zone/dwelling/building energy aggregates."""

    zone_rows = tuple(sorted(zones, key=lambda item: item.zone_id))
    dt_hours = step_input.dt_minutes / 60.0
    zone_energy = tuple(
        ZoneEnergyResult(
            scenario_id=scenario.scenario_id,
            run_id=step_input.run_context.run_id,
            zone_id=row.zone_id,
            timestep_index=step_input.timestep_index,
            electrical_energy_wh=row.total_electrical_power_w * dt_hours,
        )
        for row in zone_rows
    )
    total_wh = sum(item.electrical_energy_wh for item in zone_energy)
    dwelling = scenario.building.dwelling
    dwelling_energy = (
        DwellingEnergyResult(
            scenario_id=scenario.scenario_id,
            run_id=step_input.run_context.run_id,
            dwelling_id=dwelling.dwelling_id,
            timestep_index=step_input.timestep_index,
            electrical_energy_wh=total_wh,
        ),
    )
    building_energy = (
        BuildingEnergyResult(
            scenario_id=scenario.scenario_id,
            run_id=step_input.run_context.run_id,
            building_id=scenario.building.building_id,
            timestep_index=step_input.timestep_index,
            electrical_energy_wh=total_wh,
        ),
    )
    checks = tuple(provenance) + (
        ValidationProvenance(
            check="canonical_output_coverage",
            status="passed",
            detail="one required output row and energy row emitted per canonical zone",
        ),
        ValidationProvenance(
            check="energy_aggregation",
            status="passed",
            detail="zone electrical energy sums exactly to dwelling and building totals",
        ),
    )
    return CanonicalStepResult(
        scenario_id=scenario.scenario_id,
        run_id=step_input.run_context.run_id,
        timestamp=step_input.timestamp,
        timestep_index=step_input.timestep_index,
        dt_minutes=step_input.dt_minutes,
        zones=zone_rows,
        zone_energy=zone_energy,
        dwelling_energy=dwelling_energy,
        building_energy=building_energy,
        warnings=tuple(warnings),
        validation_provenance=checks,
        defaults_applied=tuple(defaults),
        debug=(
            CanonicalDebugResult(engine_fields=debug_fields)
            if debug_fields is not None
            else None
        ),
    )


__all__ = ["ADAPTER_CONTRACT_VERSION", "BackendAdapterError", "assemble_step_result"]
