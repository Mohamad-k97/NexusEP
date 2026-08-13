"""Observation-constrained energy-path audit for the Annex 71 mapping.

The audit is diagnostic, not calibration or validation. It assimilates each
measured air temperature, advances the unobserved mass node conditionally, and
reports the net air-node heat flow that the reduced-order model cannot explain.
This prevents free-running drift from being mistaken for an individual input-
path error while keeping the production object adapter in the loop.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from typing import Any

import numpy as np

from nexusep.abbey.building.physics.thermal import make_building_thermal_parameters
from nexusep.adapters.object_engine import ObjectEngineAdapter
from nexusep.schema.timestep import PriorZonePhysicalState
from nexusep.validation_data.annex71 import (
    AIR_DENSITY_KG_M3,
    AIR_HEAT_CAPACITY_J_KG_K,
    DT_MINUTES,
    HEATER_CONVECTIVE_FRACTION,
    ZONE_VOLUMES_M3,
    Annex71Interval,
    Annex71ModelParameters,
    build_annex71_step_input,
    build_canonical_scenario,
)

SOURCE_TIMING_KINDS = frozenset({"heating", "internal", "solar"})


@dataclass(frozen=True)
class Annex71EnergyPathRecord:
    timestamp: str
    zone_id: str
    measured_air_temperature_c: float
    predicted_air_temperature_c: float
    prediction_error_c: float
    conditional_mass_temperature_c: float
    air_storage_w: float
    envelope_gain_w: float
    ventilation_gain_w: float
    interzone_gain_w: float
    air_mass_gain_w: float
    convective_source_gain_w: float
    radiative_source_gain_w: float
    heating_gain_w: float
    internal_gain_w: float
    solar_gain_w: float
    unexplained_air_node_gain_w: float

    def to_dict(self) -> dict[str, float | str]:
        return asdict(self)


@dataclass(frozen=True)
class Annex71EnergyPathAudit:
    graph_sha256: str
    warmup_timesteps: int
    records: tuple[Annex71EnergyPathRecord, ...]
    summary: dict[str, Any]

    def to_dict(self, *, include_records: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "graph_sha256": self.graph_sha256,
            "warmup_timesteps": self.warmup_timesteps,
            "summary": self.summary,
        }
        if include_records:
            result["records"] = [item.to_dict() for item in self.records]
        return result


def _interzone_gain_w(
    record: Annex71Interval,
    zone_id: str,
    parameters: Annex71ModelParameters,
) -> float:
    exchange = parameters.zone_exchange_conductance_w_k()
    ground_temperature_c = record.zone("ground_airbody").air_temperature_c
    if zone_id == "ground_airbody":
        return sum(
            h_w_k
            * (record.zone(other_zone_id).air_temperature_c - ground_temperature_c)
            for other_zone_id, h_w_k in exchange.items()
        )
    return exchange[zone_id] * (
        ground_temperature_c - record.zone(zone_id).air_temperature_c
    )


def _correlation(left: np.ndarray, right: np.ndarray) -> float | None:
    if left.size < 2 or np.std(left) <= 1.0e-12 or np.std(right) <= 1.0e-12:
        return None
    return float(np.corrcoef(left, right)[0, 1])


def shift_annex71_source_rows(
    records: tuple[Annex71Interval, ...],
    source_kind: str,
    row_offset: int,
    *,
    edge_trim_steps: int = 1,
) -> tuple[Annex71Interval, ...]:
    """Build a timestamp-preserving source-alignment counterfactual.

    The physical targets, timestamps, and non-selected forcings remain on row
    ``t``. Only the selected source is copied from ``t + row_offset``. A common
    edge trim keeps every offset comparison on the same target observations.
    """

    if source_kind not in SOURCE_TIMING_KINDS:
        raise ValueError(f"unsupported source_kind: {source_kind!r}")
    if not isinstance(row_offset, int):
        raise TypeError("row_offset must be an integer")
    if edge_trim_steps < abs(row_offset):
        raise ValueError("edge_trim_steps must cover the absolute row offset")
    if len(records) - 2 * edge_trim_steps < 2:
        raise ValueError("source timing comparison requires at least two rows")

    shifted = []
    for target_index in range(edge_trim_steps, len(records) - edge_trim_steps):
        target = records[target_index]
        source = records[target_index + row_offset]
        if source_kind == "solar":
            shifted.append(
                replace(
                    target,
                    diffuse_horizontal_radiation_w_m2=(
                        source.diffuse_horizontal_radiation_w_m2
                    ),
                    global_horizontal_radiation_w_m2=(
                        source.global_horizontal_radiation_w_m2
                    ),
                )
            )
            continue
        field_name = (
            "heating_power_w" if source_kind == "heating" else "internal_gain_w"
        )
        shifted.append(
            replace(
                target,
                zones=tuple(
                    replace(
                        target_observation,
                        **{
                            field_name: getattr(
                                source.zone(target_observation.zone_id), field_name
                            )
                        },
                    )
                    for target_observation in target.zones
                ),
            )
        )
    return tuple(shifted)


def _summarize(
    records: tuple[Annex71EnergyPathRecord, ...], warmup_timesteps: int
) -> dict[str, Any]:
    path_fields = (
        "air_storage_w",
        "envelope_gain_w",
        "ventilation_gain_w",
        "interzone_gain_w",
        "air_mass_gain_w",
        "convective_source_gain_w",
        "radiative_source_gain_w",
        "heating_gain_w",
        "internal_gain_w",
        "solar_gain_w",
    )
    by_zone: dict[str, Any] = {}
    scored: list[Annex71EnergyPathRecord] = []
    for zone_id in sorted(ZONE_VOLUMES_M3):
        zone_records = tuple(item for item in records if item.zone_id == zone_id)
        selected = zone_records[warmup_timesteps:]
        if not selected:
            raise ValueError("warmup_timesteps must leave scored energy-path records")
        scored.extend(selected)
        residual = np.asarray(
            [item.unexplained_air_node_gain_w for item in selected], dtype=float
        )
        prediction_error = np.asarray(
            [item.prediction_error_c for item in selected], dtype=float
        )
        components: dict[str, Any] = {}
        for field in path_fields:
            values = np.asarray([getattr(item, field) for item in selected], dtype=float)
            components[field] = {
                "mean_w": float(np.mean(values)),
                "mean_abs_w": float(np.mean(np.abs(values))),
                "net_energy_kwh": float(np.sum(values) * DT_MINUTES / 60_000.0),
                "correlation_with_unexplained_gain": _correlation(values, residual),
            }
        by_zone[zone_id] = {
            "count": len(selected),
            "one_step_temperature": {
                "bias_c": float(np.mean(prediction_error)),
                "mae_c": float(np.mean(np.abs(prediction_error))),
                "rmse_c": float(np.sqrt(np.mean(np.square(prediction_error)))),
            },
            "unexplained_air_node_gain": {
                "bias_w": float(np.mean(residual)),
                "mae_w": float(np.mean(np.abs(residual))),
                "rmse_w": float(np.sqrt(np.mean(np.square(residual)))),
                "p05_w": float(np.quantile(residual, 0.05)),
                "p50_w": float(np.quantile(residual, 0.50)),
                "p95_w": float(np.quantile(residual, 0.95)),
                "net_energy_kwh": float(
                    np.sum(residual) * DT_MINUTES / 60_000.0
                ),
            },
            "components": components,
        }
    whole_residual = np.asarray(
        [item.unexplained_air_node_gain_w for item in scored], dtype=float
    )
    whole_prediction_error = np.asarray(
        [item.prediction_error_c for item in scored], dtype=float
    )
    return {
        "method": (
            "measured air temperatures constrain each interval; the unobserved mass "
            "node advances from its prior state with the measured end-of-interval "
            "air temperature"
        ),
        "sign_convention": (
            "positive unexplained_air_node_gain_w means additional heat is required "
            "to reproduce the measurement"
        ),
        "limitations": [
            "mean radiant/mass temperature is unmeasured and conditionally estimated",
            "path residuals diagnose the reduced-order mapping and are not parameter estimates",
            "the inspected period is not blind or untouched validation evidence",
        ],
        "whole_building": {
            "count": len(scored),
            "one_step_temperature_rmse_c": float(
                np.sqrt(np.mean(np.square(whole_prediction_error)))
            ),
            "unexplained_gain_bias_w": float(np.mean(whole_residual)),
            "unexplained_gain_mae_w": float(np.mean(np.abs(whole_residual))),
            "unexplained_gain_rmse_w": float(
                np.sqrt(np.mean(np.square(whole_residual)))
            ),
            "unexplained_net_energy_kwh": float(
                np.sum(whole_residual) * DT_MINUTES / 60_000.0
            ),
        },
        "by_zone": by_zone,
    }


def audit_annex71_energy_paths(
    source_records: tuple[Annex71Interval, ...],
    parameters: Annex71ModelParameters | None = None,
    *,
    warmup_timesteps: int = 24,
    initial_mass_temperature_offset_by_zone_c: Mapping[str, float] | None = None,
    heating_convective_fraction: float = HEATER_CONVECTIVE_FRACTION,
    capacity_allocation_basis: str = "air_volume",
) -> Annex71EnergyPathAudit:
    """Run an observation-constrained production-adapter heat-path audit."""

    if len(source_records) < 2:
        raise ValueError("at least two Annex 71 observations are required")
    if warmup_timesteps < 0 or warmup_timesteps >= len(source_records) - 1:
        raise ValueError("warmup_timesteps must leave at least one scored interval")
    parameters = parameters or Annex71ModelParameters()
    offsets = dict(initial_mass_temperature_offset_by_zone_c or {})
    unknown_offset_zones = sorted(set(offsets) - set(ZONE_VOLUMES_M3))
    if unknown_offset_zones:
        raise ValueError(f"unknown initial mass offset zones: {unknown_offset_zones}")
    if any(not np.isfinite(float(value)) for value in offsets.values()):
        raise ValueError("initial mass temperature offsets must be finite")
    initial_record = source_records[0]
    forcing_records = source_records[1:]
    scenario, graph = build_canonical_scenario(
        forcing_records,
        parameters,
        initial_record=initial_record,
        capacity_allocation_basis=capacity_allocation_basis,
    )
    adapter = ObjectEngineAdapter(scenario, graph)
    thermal_parameters = make_building_thermal_parameters(adapter.building_model)
    mass_temperature_c = {
        zone_id: initial_record.zone(zone_id).air_temperature_c
        + float(offsets.get(zone_id, 0.0))
        for zone_id in ZONE_VOLUMES_M3
    }
    records: list[Annex71EnergyPathRecord] = []
    previous = initial_record
    dt_seconds = DT_MINUTES * 60.0
    envelope_h_w_k = parameters.zone_envelope_conductance_w_k()
    for index, current in enumerate(forcing_records):
        prior = tuple(
            PriorZonePhysicalState(
                zone_id=zone_id,
                air_temperature_c=previous.zone(zone_id).air_temperature_c,
                mean_radiant_temperature_c=mass_temperature_c[zone_id],
                relative_humidity_fraction=previous.zone(
                    zone_id
                ).relative_humidity_fraction,
                co2_ppm=previous.outdoor_co2_ppm,
            )
            for zone_id in sorted(ZONE_VOLUMES_M3)
        )
        step = build_annex71_step_input(
            scenario,
            graph,
            current,
            index,
            prior,
            heating_convective_fraction=heating_convective_fraction,
        )
        result = adapter.run_step(step, include_debug=True)
        if result.debug is None:
            raise RuntimeError("object adapter did not return requested debug fields")
        native_by_zone = {
            str(item["zone_id"]): item
            for item in result.debug.engine_fields["native_zone_records"]
        }
        predicted_by_zone = {item.zone_id: item for item in result.zones}
        next_mass_temperature_c: dict[str, float] = {}
        for zone_id in sorted(ZONE_VOLUMES_M3):
            zone_parameters = thermal_parameters.get_zone_parameters(zone_id)
            row = native_by_zone[zone_id]
            measured_old_c = previous.zone(zone_id).air_temperature_c
            observation = current.zone(zone_id)
            measured_new_c = observation.air_temperature_c
            radiative_gain_w = float(row["thermal_radiative_gain_w"])
            c_mass_over_dt = zone_parameters.c_mass_j_k / dt_seconds
            conditional_mass_c = (
                c_mass_over_dt * mass_temperature_c[zone_id]
                + zone_parameters.h_air_mass_w_k * measured_new_c
                + radiative_gain_w
            ) / (c_mass_over_dt + zone_parameters.h_air_mass_w_k)
            next_mass_temperature_c[zone_id] = conditional_mass_c
            air_storage_w = (
                zone_parameters.c_air_j_k
                * (measured_new_c - measured_old_c)
                / dt_seconds
            )
            envelope_gain_w = envelope_h_w_k[zone_id] * (
                current.outdoor_temperature_c - measured_new_c
            )
            ventilation_gain_w = (
                AIR_DENSITY_KG_M3
                * AIR_HEAT_CAPACITY_J_KG_K
                * observation.ventilation_supply_flow_m3_s
                * (observation.ventilation_supply_temperature_c - measured_new_c)
            )
            interzone_gain_w = _interzone_gain_w(current, zone_id, parameters)
            air_mass_gain_w = zone_parameters.h_air_mass_w_k * (
                conditional_mass_c - measured_new_c
            )
            convective_gain_w = float(row["thermal_convective_gain_w"])
            explained_gain_w = (
                envelope_gain_w
                + ventilation_gain_w
                + interzone_gain_w
                + air_mass_gain_w
                + convective_gain_w
            )
            predicted_c = predicted_by_zone[zone_id].air_temperature_c
            records.append(
                Annex71EnergyPathRecord(
                    timestamp=current.timestamp.isoformat(),
                    zone_id=zone_id,
                    measured_air_temperature_c=measured_new_c,
                    predicted_air_temperature_c=predicted_c,
                    prediction_error_c=predicted_c - measured_new_c,
                    conditional_mass_temperature_c=conditional_mass_c,
                    air_storage_w=air_storage_w,
                    envelope_gain_w=envelope_gain_w,
                    ventilation_gain_w=ventilation_gain_w,
                    interzone_gain_w=interzone_gain_w,
                    air_mass_gain_w=air_mass_gain_w,
                    convective_source_gain_w=convective_gain_w,
                    radiative_source_gain_w=radiative_gain_w,
                    heating_gain_w=observation.heating_power_w,
                    internal_gain_w=observation.internal_gain_w,
                    solar_gain_w=float(row["solar_gain_w"]),
                    unexplained_air_node_gain_w=air_storage_w - explained_gain_w,
                )
            )
        mass_temperature_c = next_mass_temperature_c
        previous = current
    frozen_records = tuple(records)
    return Annex71EnergyPathAudit(
        graph_sha256=str(graph["graph_sha256"]),
        warmup_timesteps=warmup_timesteps,
        records=frozen_records,
        summary=_summarize(frozen_records, warmup_timesteps),
    )


__all__ = [
    "SOURCE_TIMING_KINDS",
    "Annex71EnergyPathAudit",
    "Annex71EnergyPathRecord",
    "audit_annex71_energy_paths",
    "shift_annex71_source_rows",
]
