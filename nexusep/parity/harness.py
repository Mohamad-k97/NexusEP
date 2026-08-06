"""Measured Phase 2.16 parity harness for ``multizone_dwelling_v1``.

The harness compares canonical inputs, decoded outputs, and invariants.  It
does not declare either backend authoritative and never turns an unavailable
physical balance into a passing check.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from nexusep.adapters import ArrayEngineAdapter, ObjectEngineAdapter
from nexusep.scenarios import CanonicalScenarioBundle, load_scenario
from nexusep.schema.outputs import (
    CanonicalRunMetadata,
    CanonicalRunResult,
    CanonicalStepResult,
    aggregate_run_results,
)
from nexusep.schema.scenario import CanonicalScenario
from nexusep.schema.timestep import (
    CanonicalGraphReference,
    DeterministicRunContext,
    OccupantStepState,
    PriorZonePhysicalState,
    SimulationStepInput,
    SystemAvailability,
    ZoneControlCommand,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENARIO_PATH = (
    REPOSITORY_ROOT / "contracts" / "examples" / "multizone_dwelling_v1_minimal.json"
)

type Classification = Literal[
    "exact_match",
    "tolerance_match",
    "expected_model_difference",
    "missing_feature",
    "defect",
    "contract_violation",
]


@dataclass(frozen=True)
class QuantityTolerance:
    absolute: float
    relative: float
    rationale: str

    def to_dict(self) -> dict[str, object]:
        return {
            "absolute": self.absolute,
            "relative": self.relative,
            "rationale": self.rationale,
        }


DEFAULT_TOLERANCES: dict[str, QuantityTolerance] = {
    "air_temperature_c": QuantityTolerance(
        absolute=0.10,
        relative=1.0e-6,
        rationale="sub-tenth-degree numerical variation is immaterial for this first harness",
    ),
    "relative_humidity_fraction": QuantityTolerance(
        absolute=0.005,
        relative=1.0e-6,
        rationale="half a percentage point of relative humidity",
    ),
    "co2_ppm": QuantityTolerance(
        absolute=5.0,
        relative=1.0e-6,
        rationale="small concentration variation while retaining ppm-scale sensitivity",
    ),
    "power_w": QuantityTolerance(
        absolute=1.0e-6,
        relative=1.0e-9,
        rationale="commands and decoded power use the same watt contract",
    ),
    "cumulative_energy_wh": QuantityTolerance(
        absolute=0.01,
        relative=1.0e-6,
        rationale="cumulative drift is checked separately from instantaneous power",
    ),
    "canonical_input": QuantityTolerance(
        absolute=1.0e-12,
        relative=0.0,
        rationale="canonical input mapping is structural conformance, not physical parity",
    ),
}


def _control_policy(
    scenario: CanonicalScenario, timestep_index: int
) -> tuple[ZoneControlCommand, ...]:
    commands: list[ZoneControlCommand] = []
    for zone in sorted(
        scenario.building.dwelling.zones, key=lambda item: item.zone_id
    ):
        is_living = zone.zone_id == "living_zone"
        heating_fraction = (
            (0.40 if is_living else 0.30)
            if timestep_index == 0
            else (0.35 if not is_living else 0.0)
            if timestep_index == 2
            else 0.0
        )
        cooling_fraction = 0.10 if timestep_index == 3 and is_living else 0.0
        lighting_power_w = (
            (80.0 if is_living else 0.0)
            if timestep_index == 0
            else (45.0 if not is_living else 0.0)
            if timestep_index == 1
            else 0.0
        )
        ventilation_flow = (
            (0.02 if is_living else 0.01) if timestep_index in {0, 1} else 0.0
        )
        commands.append(
            ZoneControlCommand(
                zone_id=zone.zone_id,
                heating_on=heating_fraction > 0.0,
                heating_power_fraction=heating_fraction,
                cooling_on=cooling_fraction > 0.0,
                cooling_power_fraction=cooling_fraction,
                ventilation_volume_flow_m3_s=ventilation_flow,
                lights_on=lighting_power_w > 0.0,
                lighting_power_w=lighting_power_w,
                window_opening_fraction=(
                    0.25 if timestep_index == 1 and is_living else 0.0
                ),
                shading_open_fraction=0.0 if timestep_index == 3 else 1.0,
            )
        )
    return tuple(commands)


def _scheduled_occupants(
    scenario: CanonicalScenario, timestep_index: int
) -> tuple[OccupantStepState, ...]:
    result = []
    for occupant in sorted(scenario.occupants, key=lambda item: item.occupant_id):
        schedule = next(
            entry
            for entry in occupant.location_schedule
            if entry.start_timestep_index
            <= timestep_index
            < entry.end_timestep_index
        )
        result.append(
            OccupantStepState(
                occupant_id=occupant.occupant_id,
                dwelling_id=occupant.dwelling_id,
                zone_id=schedule.zone_id,
                activity=schedule.activity,
                is_present=schedule.activity != "away",
            )
        )
    return tuple(result)


def _initial_prior_states(
    scenario: CanonicalScenario,
) -> tuple[PriorZonePhysicalState, ...]:
    return tuple(
        PriorZonePhysicalState(
            zone_id=zone.zone_id,
            air_temperature_c=zone.initial_air_temperature_c,
            mean_radiant_temperature_c=zone.initial_mean_radiant_temperature_c,
            relative_humidity_fraction=zone.initial_relative_humidity_fraction,
            co2_ppm=zone.initial_co2_ppm,
        )
        for zone in sorted(
            scenario.building.dwelling.zones, key=lambda item: item.zone_id
        )
    )


def build_step_input(
    scenario: CanonicalScenario,
    compiled_graph: dict[str, object],
    timestep_index: int,
    *,
    prior_zone_states: tuple[PriorZonePhysicalState, ...] | None = None,
    run_id: str = "phase_2_16_parity",
) -> SimulationStepInput:
    """Build the one deterministic input used for both backend executions."""

    weather = scenario.weather_series[timestep_index]
    return SimulationStepInput(
        scenario_id=scenario.scenario_id,
        timestep_index=timestep_index,
        timestamp=weather.timestamp,
        dt_minutes=scenario.simulation_period.dt_minutes,
        weather=weather,
        prior_zone_states=prior_zone_states or _initial_prior_states(scenario),
        occupant_states=_scheduled_occupants(scenario, timestep_index),
        action_events=(),
        internal_gains=(),
        control_commands=_control_policy(scenario, timestep_index),
        system_availability=tuple(
            SystemAvailability(
                system_id=system.system_id,
                available=True,
                capacity_fraction=1.0,
            )
            for zone in sorted(
                scenario.building.dwelling.zones, key=lambda item: item.zone_id
            )
            for system in sorted(zone.systems, key=lambda item: item.system_id)
        ),
        graph=CanonicalGraphReference(
            scenario_id=scenario.scenario_id,
            compiled_graph_version=cast(
                Literal["1.0.0"], compiled_graph["compiled_graph_version"]
            ),
            graph_sha256=str(compiled_graph["graph_sha256"]),
        ),
        run_context=DeterministicRunContext(
            run_id=run_id,
            deterministic_seed=scenario.deterministic_seed,
            random_stream_position=timestep_index,
            timezone=scenario.simulation_period.timezone,
        ),
    )


@dataclass(frozen=True)
class EngineExecution:
    snapshot: dict[str, object]
    run: CanonicalRunResult


def _next_prior_states(result: CanonicalStepResult) -> tuple[PriorZonePhysicalState, ...]:
    if result.debug is None:
        raise RuntimeError("parity execution requires adapter debug traces")
    records = result.debug.engine_fields["next_prior_zone_states"]
    if not isinstance(records, list):
        raise TypeError("adapter next-state trace is malformed")
    return tuple(PriorZonePhysicalState.model_validate(item) for item in records)


def _execute(
    adapter_type: type[ObjectEngineAdapter | ArrayEngineAdapter],
    bundle: CanonicalScenarioBundle,
) -> EngineExecution:
    adapter = adapter_type(bundle.scenario, bundle.compiled_graph)
    snapshot = adapter.conformance_snapshot()
    prior: tuple[PriorZonePhysicalState, ...] | None = None
    steps = []
    for timestep_index in range(bundle.scenario.simulation_period.n_timesteps):
        step_input = build_step_input(
            bundle.scenario,
            bundle.compiled_graph,
            timestep_index,
            prior_zone_states=prior,
        )
        step_result = adapter.run_step(step_input, include_debug=True)
        steps.append(step_result)
        prior = _next_prior_states(step_result)
    metadata = CanonicalRunMetadata(
        scenario_id=bundle.scenario.scenario_id,
        run_id="phase_2_16_parity",
        engine_name=adapter.engine_name,
        engine_version=adapter.engine_version,
        schema_version=bundle.scenario.schema_version,
        graph_sha256=str(bundle.compiled_graph["graph_sha256"]),
        deterministic_seed=bundle.scenario.deterministic_seed,
        started_at=bundle.scenario.simulation_period.start_datetime,
        timestep_count=len(steps),
        dt_minutes=bundle.scenario.simulation_period.dt_minutes,
    )
    return EngineExecution(
        snapshot=snapshot,
        run=aggregate_run_results(metadata, tuple(steps)),
    )


def _relative_difference(left: float, right: float) -> float:
    denominator = max(abs(left), abs(right))
    return 0.0 if denominator == 0.0 else abs(left - right) / denominator


def _comparison(
    *,
    scope: str,
    quantity: str,
    object_value: object,
    array_value: object,
    tolerance_name: str | None = None,
    outside_tolerance: Classification = "contract_violation",
    rationale: str,
    timestep_index: int | None = None,
    entity_id: str | None = None,
) -> dict[str, object]:
    tolerance = DEFAULT_TOLERANCES.get(tolerance_name or "")
    absolute_difference: float | None = None
    relative_difference: float | None = None

    if object_value is None or array_value is None:
        classification: Classification = "missing_feature"
    elif isinstance(object_value, (int, float)) and isinstance(
        array_value, (int, float)
    ):
        left = float(object_value)
        right = float(array_value)
        absolute_difference = abs(left - right)
        relative_difference = _relative_difference(left, right)
        if not math.isfinite(left) or not math.isfinite(right):
            classification = "defect"
        elif left == right:
            classification = "exact_match"
        elif tolerance is not None and math.isclose(
            left,
            right,
            abs_tol=tolerance.absolute,
            rel_tol=tolerance.relative,
        ):
            classification = "tolerance_match"
        else:
            classification = outside_tolerance
    elif object_value == array_value:
        classification = "exact_match"
    else:
        classification = outside_tolerance

    return {
        "scope": scope,
        "timestep_index": timestep_index,
        "entity_id": entity_id,
        "quantity": quantity,
        "object_value": object_value,
        "array_value": array_value,
        "absolute_difference": absolute_difference,
        "relative_difference": relative_difference,
        "tolerance": tolerance.to_dict() if tolerance is not None else None,
        "classification": classification,
        "rationale": rationale,
    }


def _initial_state_comparisons(
    object_execution: EngineExecution,
    array_execution: EngineExecution,
) -> list[dict[str, object]]:
    rows = [
        _comparison(
            scope="initial_state",
            quantity="graph_sha256",
            object_value=object_execution.snapshot["graph_sha256"],
            array_value=array_execution.snapshot["graph_sha256"],
            rationale="both adapters were constructed from the same compiled graph",
        ),
        _comparison(
            scope="initial_state",
            quantity="decoded_ids",
            object_value=object_execution.snapshot["decoded_ids"],
            array_value=array_execution.snapshot["decoded_ids"],
            rationale="numeric backend IDs must decode to original canonical strings",
        ),
    ]
    object_states: dict[str, dict[str, object]] = {
        str(item["zone_id"]): item
        for item in cast(
            list[dict[str, object]], object_execution.snapshot["initial_zone_states"]
        )
    }
    array_states: dict[str, dict[str, object]] = {
        str(item["zone_id"]): item
        for item in cast(
            list[dict[str, object]], array_execution.snapshot["initial_zone_states"]
        )
    }
    for zone_id in sorted(object_states):
        for quantity, tolerance_name in (
            ("air_temperature_c", "air_temperature_c"),
            ("mean_radiant_temperature_c", "air_temperature_c"),
            ("relative_humidity_fraction", "relative_humidity_fraction"),
            ("co2_ppm", "co2_ppm"),
        ):
            rows.append(
                _comparison(
                    scope="initial_state",
                    entity_id=zone_id,
                    quantity=quantity,
                    object_value=object_states[zone_id][quantity],
                    array_value=array_states[zone_id][quantity],
                    tolerance_name=tolerance_name,
                    outside_tolerance="contract_violation",
                    rationale="canonical initial state must survive backend encoding",
                )
            )
    rows.append(
        _comparison(
            scope="topology",
            quantity="native_surface_graph",
            object_value=object_execution.snapshot["native_topology"],
            array_value=None,
            rationale="the array backend has compiled UA values but no surface-graph kernel",
        )
    )
    return rows


def _normalized_weather(engine_name: str, trace: dict[str, Any]) -> dict[str, object]:
    weather = trace["weather"]
    if engine_name == "object":
        return {
            "timestamp": weather["datetime"],
            "outdoor_temperature_c": weather["outdoor_temperature_c"],
            "relative_humidity_fraction": weather["relative_humidity_percent"]
            / 100.0,
            "atmospheric_pressure_pa": weather["atmospheric_pressure_pa"],
            "outdoor_co2_ppm": weather["outdoor_co2_ppm"],
            "wind_speed_m_s": weather["wind_speed_m_s"],
            "wind_direction_deg": weather["wind_direction_deg"],
            "direct_normal_radiation_w_m2": weather[
                "direct_normal_radiation_w_m2"
            ],
            "diffuse_horizontal_radiation_w_m2": weather[
                "diffuse_horizontal_radiation_w_m2"
            ],
            "global_horizontal_radiation_w_m2": weather[
                "global_horizontal_radiation_w_m2"
            ],
        }
    return {
        "timestamp": trace["timestamp"],
        "outdoor_temperature_c": weather["outdoor_temperature_C"],
        "relative_humidity_fraction": weather["outdoor_relative_humidity"],
        "atmospheric_pressure_pa": None,
        "outdoor_co2_ppm": weather["outdoor_co2_ppm"],
        "wind_speed_m_s": weather["wind_speed_m_s"],
        "wind_direction_deg": weather["wind_direction_deg"],
        "direct_normal_radiation_w_m2": weather["dni_W_m2"],
        "diffuse_horizontal_radiation_w_m2": weather["dhi_W_m2"],
        "global_horizontal_radiation_w_m2": weather["ghi_W_m2"],
    }


def _normalized_occupants(engine_name: str, trace: dict[str, Any]) -> list[dict[str, object]]:
    if engine_name == "object":
        return [
            {
                "occupant_id": item["occupant_id"],
                "zone_id": item["zone_id"],
                "activity": item["activity"],
                "is_present": item["is_present"],
            }
            for item in trace["occupants"]
        ]
    activity = {
        "away": "away",
        "home_awake": "awake",
        "home_sleeping": "sleeping",
    }
    return [
        {
            "occupant_id": item["person_id"],
            "zone_id": item["current_zone_id"],
            "activity": activity[item["occupancy_state"]],
            "is_present": item["is_home"],
        }
        for item in trace["occupants"]
    ]


def _normalized_controls(
    engine_name: str,
    trace: dict[str, Any],
    scenario: CanonicalScenario,
) -> dict[str, dict[str, object]]:
    if engine_name == "object":
        return {
            zone_id: {
                "hvac_mode": "heating"
                if item["heating_on"]
                else "cooling"
                if item["cooling_on"]
                else "off",
                "heating_power_fraction": item["heating_power_fraction"],
                "cooling_power_fraction": item["cooling_power_fraction"],
                "ventilation_volume_flow_m3_s": item["ventilation_flow_m3_h"]
                / 3600.0,
                "lights_on": item["lights_on"],
                "lighting_power_w": item["lighting_power_w"],
                "window_opening_fraction": item["window_opening_fraction"],
                "shading_open_fraction": 1.0 if item["curtain_open"] else 0.0,
            }
            for zone_id, item in trace["controls"].items()
        }
    zones = {item.zone_id: item for item in scenario.building.dwelling.zones}
    result = {}
    for zone_id, item in trace["controls"].items():
        systems = {entry.system_type: entry for entry in zones[zone_id].systems}
        heating_capacity = systems["heating"].max_heating_power_w or 0.0
        cooling_capacity = systems["cooling"].max_cooling_power_w or 0.0
        result[zone_id] = {
            "hvac_mode": item["hvac_mode"],
            "heating_power_fraction": (
                item["max_heating_power_W"] / heating_capacity
                if heating_capacity
                else 0.0
            ),
            "cooling_power_fraction": (
                item["max_cooling_power_W"] / cooling_capacity
                if cooling_capacity
                else 0.0
            ),
            "ventilation_volume_flow_m3_s": item[
                "mechanical_ventilation_flow_m3_s"
            ],
            "lights_on": item["light_state"] == "on",
            "lighting_power_w": item["lighting_power_W"],
            "window_opening_fraction": item["window_open_fraction"],
            "shading_open_fraction": 1.0 - item["blind_closed_fraction"],
        }
    return result


def _step_comparisons(
    bundle: CanonicalScenarioBundle,
    object_execution: EngineExecution,
    array_execution: EngineExecution,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    object_cumulative: dict[str, float] = {}
    array_cumulative: dict[str, float] = {}
    for object_step, array_step in zip(
        object_execution.run.steps, array_execution.run.steps, strict=True
    ):
        if object_step.debug is None or array_step.debug is None:
            raise RuntimeError("parity execution requires step traces")
        timestep_index = object_step.timestep_index
        object_trace = cast(dict[str, Any], object_step.debug.engine_fields["step_trace"])
        array_trace = cast(dict[str, Any], array_step.debug.engine_fields["step_trace"])
        object_weather = _normalized_weather("object", object_trace)
        array_weather = _normalized_weather("array", array_trace)
        for quantity in object_weather:
            rows.append(
                _comparison(
                    scope="weather_mapping",
                    timestep_index=timestep_index,
                    quantity=quantity,
                    object_value=object_weather[quantity],
                    array_value=array_weather[quantity],
                    tolerance_name="canonical_input",
                    outside_tolerance="contract_violation",
                    rationale=(
                        "array pressure consumption is not implemented"
                        if quantity == "atmospheric_pressure_pa"
                        else "both engines must receive the same normalized weather"
                    ),
                )
            )
        rows.append(
            _comparison(
                scope="occupancy_mapping",
                timestep_index=timestep_index,
                quantity="occupant_locations_and_states",
                object_value=_normalized_occupants("object", object_trace),
                array_value=_normalized_occupants("array", array_trace),
                outside_tolerance="contract_violation",
                rationale="occupant identities, locations, and presence are canonical inputs",
            )
        )
        object_controls = _normalized_controls(
            "object", object_trace, bundle.scenario
        )
        array_controls = _normalized_controls("array", array_trace, bundle.scenario)
        for zone_id in sorted(object_controls):
            for quantity in object_controls[zone_id]:
                rows.append(
                    _comparison(
                        scope="control_mapping",
                        timestep_index=timestep_index,
                        entity_id=zone_id,
                        quantity=quantity,
                        object_value=object_controls[zone_id][quantity],
                        array_value=array_controls[zone_id][quantity],
                        tolerance_name="canonical_input",
                        outside_tolerance="contract_violation",
                        rationale="canonical control commands must survive both encoders",
                    )
                )
        object_by_zone = {item.zone_id: item for item in object_step.zones}
        array_by_zone = {item.zone_id: item for item in array_step.zones}
        for zone_id in sorted(object_by_zone):
            object_row = object_by_zone[zone_id]
            array_row = array_by_zone[zone_id]
            for quantity, tolerance_name, outside in (
                (
                    "air_temperature_c",
                    "air_temperature_c",
                    "expected_model_difference",
                ),
                (
                    "relative_humidity_fraction",
                    "relative_humidity_fraction",
                    "expected_model_difference",
                ),
                ("co2_ppm", "co2_ppm", "expected_model_difference"),
                ("heating_power_w", "power_w", "contract_violation"),
                ("cooling_power_w", "power_w", "contract_violation"),
                ("ventilation_power_w", "power_w", "contract_violation"),
                ("lighting_power_w", "power_w", "contract_violation"),
                ("total_electrical_power_w", "power_w", "contract_violation"),
            ):
                rows.append(
                    _comparison(
                        scope="step_output",
                        timestep_index=timestep_index,
                        entity_id=zone_id,
                        quantity=quantity,
                        object_value=getattr(object_row, quantity),
                        array_value=getattr(array_row, quantity),
                        tolerance_name=tolerance_name,
                        outside_tolerance=cast(Classification, outside),
                        rationale=(
                            "backend physical solvers differ and neither is canonical truth"
                            if outside == "expected_model_difference"
                            else "the same physical command and power output contract applies"
                        ),
                    )
                )
            object_energy = next(
                item.electrical_energy_wh
                for item in object_step.zone_energy
                if item.zone_id == zone_id
            )
            array_energy = next(
                item.electrical_energy_wh
                for item in array_step.zone_energy
                if item.zone_id == zone_id
            )
            object_cumulative[zone_id] = object_cumulative.get(zone_id, 0.0) + object_energy
            array_cumulative[zone_id] = array_cumulative.get(zone_id, 0.0) + array_energy
            rows.append(
                _comparison(
                    scope="cumulative_drift",
                    timestep_index=timestep_index,
                    entity_id=zone_id,
                    quantity="electrical_energy_wh",
                    object_value=object_cumulative[zone_id],
                    array_value=array_cumulative[zone_id],
                    tolerance_name="cumulative_energy_wh",
                    outside_tolerance="contract_violation",
                    rationale="cumulative energy drift is evaluated separately from power",
                )
            )
        object_zone_total = sum(
            item.electrical_energy_wh for item in object_step.zone_energy
        )
        array_zone_total = sum(
            item.electrical_energy_wh for item in array_step.zone_energy
        )
        invariant_checks = {
            "electrical_energy_aggregation": (
                math.isclose(
                    object_zone_total,
                    object_step.building_energy[0].electrical_energy_wh,
                    abs_tol=1.0e-12,
                    rel_tol=0.0,
                ),
                math.isclose(
                    array_zone_total,
                    array_step.building_energy[0].electrical_energy_wh,
                    abs_tol=1.0e-12,
                    rel_tol=0.0,
                ),
            ),
            "finite_physical_outputs": (
                all(
                    math.isfinite(value)
                    for item in object_step.zones
                    for value in (
                        item.air_temperature_c,
                        item.relative_humidity_fraction,
                        item.co2_ppm,
                        item.total_electrical_power_w,
                    )
                ),
                all(
                    math.isfinite(value)
                    for item in array_step.zones
                    for value in (
                        item.air_temperature_c,
                        item.relative_humidity_fraction,
                        item.co2_ppm,
                        item.total_electrical_power_w,
                    )
                ),
            ),
            "bounded_humidity_and_nonnegative_power": (
                all(
                    0.0 <= item.relative_humidity_fraction <= 1.0
                    and item.total_electrical_power_w >= 0.0
                    for item in object_step.zones
                ),
                all(
                    0.0 <= item.relative_humidity_fraction <= 1.0
                    and item.total_electrical_power_w >= 0.0
                    for item in array_step.zones
                ),
            ),
        }
        for quantity, (object_passed, array_passed) in invariant_checks.items():
            rows.append(
                _comparison(
                    scope="invariant",
                    timestep_index=timestep_index,
                    quantity=quantity,
                    object_value=object_passed,
                    array_value=array_passed,
                    outside_tolerance="defect",
                    rationale="the invariant is evaluated independently in each backend",
                )
            )
    rows.extend(
        (
            _comparison(
                scope="conservation",
                quantity="thermal_balance_residual",
                object_value=None,
                array_value=None,
                rationale="neither canonical adapter exposes a comparable thermal residual",
            ),
            _comparison(
                scope="conservation",
                quantity="moisture_balance_residual",
                object_value=None,
                array_value=None,
                rationale="neither canonical adapter exposes a comparable moisture residual",
            ),
            _comparison(
                scope="conservation",
                quantity="co2_mass_balance_residual",
                object_value=None,
                array_value=None,
                rationale="neither canonical adapter exposes a comparable CO2 residual",
            ),
        )
    )
    return rows


def _determinism_comparisons(
    first: dict[str, EngineExecution], second: dict[str, EngineExecution]
) -> list[dict[str, object]]:
    rows = []
    for engine_name in ("object", "array"):
        first_dump = first[engine_name].run.model_dump(mode="json")
        second_dump = second[engine_name].run.model_dump(mode="json")
        first_digest = hashlib.sha256(
            json.dumps(first_dump, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        second_digest = hashlib.sha256(
            json.dumps(second_dump, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        rows.append(
            _comparison(
                scope="determinism",
                entity_id=engine_name,
                quantity="repeat_run",
                object_value=first_digest,
                array_value=second_digest,
                outside_tolerance="defect",
                rationale="SHA-256 hashes of fresh structured runs must be identical",
            )
        )
    return rows


def run_initial_parity(
    scenario_path: Path = DEFAULT_SCENARIO_PATH,
) -> dict[str, object]:
    """Run both engines twice and return a JSON-serializable measured report."""

    bundle = load_scenario(scenario_path)
    first = {
        "object": _execute(ObjectEngineAdapter, bundle),
        "array": _execute(ArrayEngineAdapter, bundle),
    }
    second = {
        "object": _execute(ObjectEngineAdapter, bundle),
        "array": _execute(ArrayEngineAdapter, bundle),
    }
    comparisons = _initial_state_comparisons(first["object"], first["array"])
    comparisons.extend(
        _step_comparisons(bundle, first["object"], first["array"])
    )
    comparisons.extend(_determinism_comparisons(first, second))
    counts: dict[str, int] = {}
    for item in comparisons:
        classification = str(item["classification"])
        counts[classification] = counts.get(classification, 0) + 1
    resolved_scenario_path = scenario_path.resolve()
    try:
        published_scenario_path = resolved_scenario_path.relative_to(
            REPOSITORY_ROOT
        ).as_posix()
    except ValueError:
        published_scenario_path = str(resolved_scenario_path)
    return {
        "report_version": "1.0.0",
        "contract_version": "1.0.0",
        "scenario_path": published_scenario_path,
        "scenario_id": bundle.scenario.scenario_id,
        "schema_version": bundle.scenario.schema_version,
        "graph_sha256": bundle.compiled_graph["graph_sha256"],
        "engine_policy": {
            "object": "reference_candidate",
            "array": "experimental",
            "canonical_truth": None,
        },
        "engine_versions": {
            engine_name: execution.run.metadata.engine_version
            for engine_name, execution in first.items()
        },
        "scenario_shape": {
            "timesteps": bundle.scenario.simulation_period.n_timesteps,
            "dt_minutes": bundle.scenario.simulation_period.dt_minutes,
            "zones": len(bundle.scenario.building.dwelling.zones),
            "occupants": len(bundle.scenario.occupants),
            "systems": sum(
                len(zone.systems) for zone in bundle.scenario.building.dwelling.zones
            ),
        },
        "tolerances": {
            key: value.to_dict() for key, value in DEFAULT_TOLERANCES.items()
        },
        "classification_counts": dict(sorted(counts.items())),
        "comparisons": comparisons,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        type=Path,
        default=DEFAULT_SCENARIO_PATH,
        help="canonical scenario JSON/JSONC path",
    )
    parser.add_argument("--output", type=Path, help="optional JSON report path")
    args = parser.parse_args()
    report = run_initial_parity(args.scenario)
    serialized = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
