"""Run frozen, non-calibrating Annex 71 structural diagnostics."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nexusep.validation_data.annex71 import (
    HEATER_CONVECTIVE_FRACTION,
    WINDOWS,
    Annex71ModelParameters,
    build_canonical_scenario,
    load_annex71_intervals,
    parameters_as_dict,
    select_interval,
    zone_capacity_fractions,
)
from nexusep.validation_data.annex71_audit import (
    Annex71EnergyPathAudit,
    audit_annex71_energy_paths,
    shift_annex71_source_rows,
)

DEFAULT_RAW_DIRECTORY = Path(
    "data/raw/validation/annex71-twin-houses/03_Data_Main_Experiment"
)
DEFAULT_PRODUCTION_RESULT = Path(
    "data/validation/fixtures/annex71-twin-houses/production-transfer-result-v1.json"
)
DEFAULT_PROTOCOL = Path(
    "data/validation/governance/annex71_structural_diagnostics_v1.json"
)
DEFAULT_RESULT = Path(
    "data/validation/fixtures/annex71-twin-houses/structural-diagnostics-v1.json"
)
DEFAULT_REPORT = Path(
    "docs/validation/results/annex71_structural_diagnostics_v1.md"
)
ZONE_IDS = (
    "attic_airbody",
    "ground_airbody",
    "kitchen_airbody",
    "sleeping_airbody",
)


def _period(records, start: str, end_exclusive: str):
    return select_interval(
        records,
        start=datetime.fromisoformat(start),
        end_exclusive=datetime.fromisoformat(end_exclusive),
    )


def _parameters(path: Path) -> Annex71ModelParameters:
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = payload["study"]["fixed_and_fitted_parameters"]
    return Annex71ModelParameters(
        **{
            field: float(value)
            for field, value in values.items()
            if field in Annex71ModelParameters.__dataclass_fields__
        }
    )


def _metrics(audit: Annex71EnergyPathAudit) -> dict[str, Any]:
    summary = audit.summary
    whole = summary["whole_building"]
    return {
        "graph_sha256": audit.graph_sha256,
        "whole_building": {
            "one_step_temperature_rmse_c": whole["one_step_temperature_rmse_c"],
            "unexplained_gain_bias_w": whole["unexplained_gain_bias_w"],
            "unexplained_gain_mae_w": whole["unexplained_gain_mae_w"],
        },
        "by_zone": {
            zone_id: {
                "one_step_temperature_rmse_c": summary["by_zone"][zone_id][
                    "one_step_temperature"
                ]["rmse_c"],
                "unexplained_gain_bias_w": summary["by_zone"][zone_id][
                    "unexplained_air_node_gain"
                ]["bias_w"],
                "unexplained_gain_mae_w": summary["by_zone"][zone_id][
                    "unexplained_air_node_gain"
                ]["mae_w"],
            }
            for zone_id in ZONE_IDS
        },
    }


def _run_pair(
    label: str,
    calibration_records,
    later_records,
    parameters: Annex71ModelParameters,
    **audit_options: Any,
) -> dict[str, Any]:
    print(f"running {label}", flush=True)
    return {
        "calibration": _metrics(
            audit_annex71_energy_paths(
                calibration_records,
                parameters,
                **audit_options,
            )
        ),
        "later_period": _metrics(
            audit_annex71_energy_paths(
                later_records,
                parameters,
                **audit_options,
            )
        ),
    }


def _improvement(
    baseline: dict[str, Any], candidate: dict[str, Any], zone_id: str | None = None
) -> float:
    key = "whole_building" if zone_id is None else "by_zone"
    if zone_id is None:
        baseline_mae = baseline[key]["unexplained_gain_mae_w"]
        candidate_mae = candidate[key]["unexplained_gain_mae_w"]
    else:
        baseline_mae = baseline[key][zone_id]["unexplained_gain_mae_w"]
        candidate_mae = candidate[key][zone_id]["unexplained_gain_mae_w"]
    return (baseline_mae - candidate_mae) / baseline_mae


def _pair_improvements(
    baseline: dict[str, Any], candidate: dict[str, Any], zone_id: str | None = None
) -> dict[str, float]:
    return {
        period: _improvement(baseline[period], candidate[period], zone_id)
        for period in ("calibration", "later_period")
    }


def _representation_audit(
    records, parameters: Annex71ModelParameters
) -> dict[str, Any]:
    scenario, graph = build_canonical_scenario(records, parameters)
    exterior_surfaces = [
        surface
        for zone in scenario.building.dwelling.zones
        for surface in zone.surfaces
        if surface.boundary_type == "exterior"
    ]
    openings = [opening for surface in exterior_surfaces for opening in surface.openings]
    attic_south = next(
        surface
        for surface in exterior_surfaces
        if surface.zone_id == "attic_airbody" and surface.azimuth_deg == 180.0
    )
    return {
        "graph_sha256": graph["graph_sha256"],
        "published_specification": {
            "source_documents": [
                "01_Experimental_specification_BESmodVAL_annex71_final_v1_0.pdf",
                "02_Additional Documents/Geometry/Plans_TwinHouses.pdf",
                "02_Additional Documents/Materials and Constructions/01_Constructions_TwinHouses.xlsx",
                "02_Additional Documents/Instrumentation/Measurement Channel List.xlsx",
            ],
            "supplementary_archive_sha256": (
                "08e7d39cd5e3eb06821f60cc0f809926d3d8badd48798ce66dbb33f08bce5da9"
            ),
            "component_u_values_w_m2_k": {
                "west_wall": 0.218157,
                "east_wall": 0.222197,
                "south_wall_range": [0.214501, 0.289754],
                "north_wall_range": [0.214501, 0.289754],
                "ceiling": 0.410139,
                "floor": 0.294466,
                "roof": 0.216,
                "window": 1.20,
            },
            "roof_tilt_deg": 30.0,
            "heater_convective_fraction": 0.70,
            "internal_load_delivery": "same electric convectors as room heating",
            "sensitivity_topics": [
                "heater radiative-convective split",
                "cellar temperature",
                "infiltration",
                "operable window",
                "internal heat-gain measurement uncertainty",
                "stratification and exhaust-air temperature",
            ],
        },
        "canonical_mapping": {
            "exterior_surface_count": len(exterior_surfaces),
            "opening_count": len(openings),
            "unique_opaque_u_values_w_m2_k": sorted(
                {surface.thermal_transmittance_w_m2_k for surface in exterior_surfaces}
            ),
            "unique_exterior_tilts_deg": sorted(
                {surface.tilt_deg for surface in exterior_surfaces}
            ),
            "attic_south_opening_tilt_deg": attic_south.tilt_deg,
            "attic_south_source_name": next(
                name
                for name, _area, azimuth in WINDOWS["attic_airbody"]
                if azimuth == 180.0
            ),
            "cellar_boundary_present": any(
                "cellar" in (surface.adjacent_zone_id or "").lower()
                for surface in exterior_surfaces
            ),
            "per_opening_blind_state_present": False,
            "capacity_allocation_basis": "air_volume",
            "capacity_fractions": zone_capacity_fractions("air_volume"),
        },
        "classified_gaps": {
            "component_fabric_topology": "missing",
            "roof_window_tilt": "corrected_from_official_dimensioned_plan",
            "cellar_boundary": "missing",
            "ground_west_blind": "unsupported_by_zone_level_shading_command",
            "internal_gain_split": "supported_70_30_same_convector_delivery",
        },
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    decision = payload["decision"]
    mass = payload["diagnostics"]["initial_mass_state"]
    timing = payload["diagnostics"]["source_timing"]
    capacity = payload["diagnostics"]["capacity_allocation"]
    split = payload["diagnostics"]["heater_distribution"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# Annex 71 structural diagnostics",
                "",
                "Validation category: empirical validation",
                "Model claim(s): THERMAL-1",
                "Data source IDs: iea-ebc-annex71-twin-houses-2020",
                "",
                "Result role: post-hoc structural diagnosis without fitting",
                "",
                "## Outcome",
                "",
                f"- Source timing shift supported: **{decision['source_timing_shift_supported']}**.",
                f"- Alternative heater split materially supported: **{decision['alternative_heater_split_material']}**.",
                f"- Initial mass-state uncertainty material: **{decision['initial_mass_state_material']}**.",
                f"- Floor-area capacity allocation supported: **{decision['floor_area_capacity_allocation_supported']}**.",
                "- Counterfactual production mutation authorized: **false**.",
                "- Source-determined 30-degree roof tilt applied: **true**.",
                "- Validation status changed: **false**.",
                "",
                "## Structural evidence",
                "",
                (
                "The official specification distinguishes walls, roof, floor, ceiling, "
                "windows, thermal bridges, cellar coupling, blinds, and a roof window. "
                "The current mapping preserves an allocated whole-building conductance but "
                "collapses opaque exterior components to one U-value. The dimensioned-plan "
                "30-degree roof tilt is now mapped explicitly."
                ),
                "",
                (
                    "The internal heat sources use the same electric convectors as heating; the "
                    "baseline 70/30 convective/radiative split is therefore source-supported."
                ),
                "",
                "## Diagnostic classifications",
                "",
                f"Source-timing supported candidates: `{timing['supported_candidates']}`.",
                f"Heater-split material candidates: `{split['material_candidates']}`.",
                f"Mass-state maximum relative span: `{mass['maximum_relative_span']:.3f}`.",
                (
                    "Floor-area allocation minimum required improvement: "
                    f"`{capacity['minimum_required_improvement']:.3f}`; observed minimum: "
                    f"`{capacity['minimum_observed_improvement']:.3f}`."
                ),
                "",
                "## Interpretation",
                "",
                (
                    "Only findings that satisfy the predeclared cross-period 10% rule are called "
                    "material. Negative candidates remain in the artifact. No candidate is a "
                    "calibrated correction or validation pass."
                ),
                "",
                "## Reproduce",
                "",
                "```text",
                "uv run python scripts/validation_data/run_annex71_structural_diagnostics.py",
                "```",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-directory", type=Path, default=DEFAULT_RAW_DIRECTORY)
    parser.add_argument(
        "--production-result", type=Path, default=DEFAULT_PRODUCTION_RESULT
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    records = load_annex71_intervals(args.raw_directory)
    calibration_records = _period(records, **protocol["periods"]["calibration"])
    later_records = _period(records, **protocol["periods"]["later_period"])
    parameters = _parameters(args.production_result)
    threshold = protocol["common_settings"]["material_relative_change_fraction"]

    baseline = _run_pair(
        "baseline", calibration_records, later_records, parameters
    )
    source_protocol = protocol["diagnostics"]["source_timing"]
    edge_trim_steps = int(source_protocol["common_edge_trim_hours"])
    trimmed_calibration = shift_annex71_source_rows(
        calibration_records, "heating", 0, edge_trim_steps=edge_trim_steps
    )
    trimmed_later = shift_annex71_source_rows(
        later_records, "heating", 0, edge_trim_steps=edge_trim_steps
    )
    timing_baseline = _run_pair(
        "source timing baseline", trimmed_calibration, trimmed_later, parameters
    )
    timing_candidates = []
    for source_kind in source_protocol["source_kinds"]:
        for offset in source_protocol["source_row_offsets_hours"]:
            if offset == 0:
                continue
            candidate = _run_pair(
                f"source timing {source_kind} {offset:+d}h",
                shift_annex71_source_rows(
                    calibration_records,
                    source_kind,
                    offset,
                    edge_trim_steps=edge_trim_steps,
                ),
                shift_annex71_source_rows(
                    later_records,
                    source_kind,
                    offset,
                    edge_trim_steps=edge_trim_steps,
                ),
                parameters,
            )
            improvements = _pair_improvements(timing_baseline, candidate)
            timing_candidates.append(
                {
                    "source_kind": source_kind,
                    "row_offset_hours": offset,
                    "metrics": candidate,
                    "whole_building_mae_improvement_fraction": improvements,
                    "material": all(value >= threshold for value in improvements.values()),
                }
            )

    split_candidates = []
    for fraction in protocol["diagnostics"]["heater_distribution"][
        "convective_fractions"
    ]:
        if fraction == HEATER_CONVECTIVE_FRACTION:
            candidate = baseline
        else:
            candidate = _run_pair(
                f"heater convective fraction {fraction:.1f}",
                calibration_records,
                later_records,
                parameters,
                heating_convective_fraction=fraction,
            )
        improvements = _pair_improvements(baseline, candidate)
        split_candidates.append(
            {
                "convective_fraction": fraction,
                "metrics": candidate,
                "whole_building_mae_improvement_fraction": improvements,
                "material": fraction != HEATER_CONVECTIVE_FRACTION
                and all(value >= threshold for value in improvements.values()),
            }
        )

    mass_candidates = []
    for scope in protocol["diagnostics"]["initial_mass_state"]["scopes"]:
        for offset in protocol["diagnostics"]["initial_mass_state"]["offsets_c"]:
            if offset == 0.0:
                candidate = baseline
            else:
                zones = ZONE_IDS if scope == "all_zones" else ("attic_airbody",)
                candidate = _run_pair(
                    f"initial mass {scope} {offset:+.1f}C",
                    calibration_records,
                    later_records,
                    parameters,
                    initial_mass_temperature_offset_by_zone_c={
                        zone_id: offset for zone_id in zones
                    },
                )
            mass_candidates.append(
                {"scope": scope, "offset_c": offset, "metrics": candidate}
            )
    mass_spans = []
    for scope in protocol["diagnostics"]["initial_mass_state"]["scopes"]:
        selected = [item for item in mass_candidates if item["scope"] == scope]
        for period in ("calibration", "later_period"):
            for zone_id in (None, "attic_airbody"):
                baseline_section = (
                    baseline[period]["whole_building"]
                    if zone_id is None
                    else baseline[period]["by_zone"][zone_id]
                )
                values = [
                    (
                        item["metrics"][period]["whole_building"]
                        if zone_id is None
                        else item["metrics"][period]["by_zone"][zone_id]
                    )["unexplained_gain_mae_w"]
                    for item in selected
                ]
                mass_spans.append(
                    {
                        "scope": scope,
                        "period": period,
                        "target": zone_id or "whole_building",
                        "relative_span": (max(values) - min(values))
                        / baseline_section["unexplained_gain_mae_w"],
                    }
                )

    floor_capacity = _run_pair(
        "floor-area capacity allocation",
        calibration_records,
        later_records,
        parameters,
        capacity_allocation_basis="floor_area",
    )
    floor_whole = _pair_improvements(baseline, floor_capacity)
    floor_attic = _pair_improvements(baseline, floor_capacity, "attic_airbody")
    floor_observed_minimum = min(*floor_whole.values(), *floor_attic.values())

    supported_timing = [
        {
            "source_kind": item["source_kind"],
            "row_offset_hours": item["row_offset_hours"],
        }
        for item in timing_candidates
        if item["material"]
    ]
    material_splits = [
        item["convective_fraction"] for item in split_candidates if item["material"]
    ]
    maximum_mass_span = max(item["relative_span"] for item in mass_spans)
    floor_supported = floor_observed_minimum >= threshold
    payload = {
        "artifact_version": "1.0.0",
        "created_on": datetime.now(UTC).date().isoformat(),
        "validation_category": "diagnostic_verification_and_empirical_residual_analysis",
        "claim_limit": protocol["claim_limit"],
        "protocol": str(args.protocol).replace("\\", "/"),
        "parameters": parameters_as_dict(parameters),
        "representation_audit": _representation_audit(
            later_records[:2], parameters
        ),
        "diagnostics": {
            "source_timing": {
                "baseline": timing_baseline,
                "candidates": timing_candidates,
                "supported_candidates": supported_timing,
            },
            "heater_distribution": {
                "published_baseline_convective_fraction": HEATER_CONVECTIVE_FRACTION,
                "candidates": split_candidates,
                "material_candidates": material_splits,
            },
            "initial_mass_state": {
                "candidates": mass_candidates,
                "relative_spans": mass_spans,
                "maximum_relative_span": maximum_mass_span,
            },
            "capacity_allocation": {
                "baseline_basis": "air_volume",
                "alternative_basis": "floor_area",
                "baseline_capacity_fractions": zone_capacity_fractions("air_volume"),
                "alternative_capacity_fractions": zone_capacity_fractions("floor_area"),
                "alternative_metrics": floor_capacity,
                "whole_building_mae_improvement_fraction": floor_whole,
                "attic_mae_improvement_fraction": floor_attic,
                "minimum_required_improvement": threshold,
                "minimum_observed_improvement": floor_observed_minimum,
            },
        },
        "decision": {
            "source_timing_shift_supported": bool(supported_timing),
            "alternative_heater_split_material": bool(material_splits),
            "initial_mass_state_material": maximum_mass_span >= threshold,
            "floor_area_capacity_allocation_supported": floor_supported,
            "source_determined_roof_tilt_applied": True,
            "component_fabric_mapping_required": True,
            "cellar_boundary_contract_required": True,
            "production_mutation_authorized": False,
            "additional_calibration_authorized": False,
            "validation_status_changed": False,
        },
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_report(payload, args.report)
    print(json.dumps(payload["decision"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
