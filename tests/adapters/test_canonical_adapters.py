"""Executable gates for Phases 2.11 through 2.14.

Provenance: new regression coverage for the canonical timestep/output and
backend-adapter contracts introduced in Phase 2.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from nexusep.abbey.building.physics.solar import (
    calculate_solar_position,
    calculate_surface_solar_irradiance,
)
from nexusep.adapters import ArrayEngineAdapter, ObjectEngineAdapter
from nexusep.adapters.common import BackendAdapterError
from nexusep.scenarios import load_scenario
from nexusep.schema.outputs import (
    REQUIRED_ZONE_OUTPUT_FIELDS,
    CanonicalRunMetadata,
    aggregate_run_results,
)
from nexusep.schema.scenario import CanonicalScenario
from nexusep.schema.timestep import (
    CanonicalGraphReference,
    CanonicalStepContractError,
    DeterministicRunContext,
    InternalGain,
    OccupantStepState,
    PriorZonePhysicalState,
    SimulationStepInput,
    SystemAvailability,
    ZoneControlCommand,
    validate_step_input_for_scenario,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_PATH = (
    REPOSITORY_ROOT / "contracts" / "examples" / "multizone_dwelling_v1_minimal.json"
)


def make_step_input(
    timestep_index: int = 0,
) -> tuple[CanonicalScenario, dict[str, object], SimulationStepInput]:
    bundle = load_scenario(EXAMPLE_PATH)
    scenario = bundle.scenario
    graph = bundle.compiled_graph
    weather = scenario.weather_series[timestep_index]
    occupant_states = []
    for occupant in scenario.occupants:
        schedule = next(
            item
            for item in occupant.location_schedule
            if item.start_timestep_index <= timestep_index < item.end_timestep_index
        )
        occupant_states.append(
            OccupantStepState(
                occupant_id=occupant.occupant_id,
                dwelling_id=occupant.dwelling_id,
                zone_id=schedule.zone_id,
                activity=schedule.activity,
                is_present=schedule.activity != "away",
            )
        )
    step = SimulationStepInput(
        scenario_id=scenario.scenario_id,
        timestep_index=timestep_index,
        timestamp=weather.timestamp,
        dt_minutes=scenario.simulation_period.dt_minutes,
        weather=weather,
        prior_zone_states=tuple(
            PriorZonePhysicalState(
                zone_id=zone.zone_id,
                air_temperature_c=zone.initial_air_temperature_c,
                mean_radiant_temperature_c=zone.initial_mean_radiant_temperature_c,
                relative_humidity_fraction=zone.initial_relative_humidity_fraction,
                co2_ppm=zone.initial_co2_ppm,
            )
            for zone in scenario.building.dwelling.zones
        ),
        occupant_states=tuple(occupant_states),
        action_events=(),
        internal_gains=(),
        control_commands=tuple(
            ZoneControlCommand(
                zone_id=zone.zone_id,
                heating_on=False,
                heating_power_fraction=0.0,
                cooling_on=False,
                cooling_power_fraction=0.0,
                ventilation_volume_flow_m3_s=0.0,
                lights_on=False,
                lighting_power_w=0.0,
                window_opening_fraction=0.0,
                shading_open_fraction=1.0,
            )
            for zone in scenario.building.dwelling.zones
        ),
        system_availability=tuple(
            SystemAvailability(
                system_id=system.system_id,
                available=True,
                capacity_fraction=1.0,
            )
            for zone in scenario.building.dwelling.zones
            for system in zone.systems
        ),
        graph=CanonicalGraphReference(
            scenario_id=scenario.scenario_id,
            compiled_graph_version=graph["compiled_graph_version"],
            graph_sha256=graph["graph_sha256"],
        ),
        run_context=DeterministicRunContext(
            run_id="adapter_contract_run",
            deterministic_seed=scenario.deterministic_seed,
            random_stream_position=timestep_index,
            timezone=scenario.simulation_period.timezone,
        ),
    )
    return scenario, graph, step


def test_step_input_is_frozen_and_all_top_level_fields_are_required() -> None:
    scenario, graph, step = make_step_input()
    validate_step_input_for_scenario(step, scenario, graph)
    assert step.time_index == step.timestep_index

    with pytest.raises(ValidationError, match="Field required"):
        SimulationStepInput.model_validate(
            {
                key: value
                for key, value in step.model_dump().items()
                if key != "system_availability"
            }
        )
    with pytest.raises(ValidationError, match="Instance is frozen"):
        step.dt_minutes = 15.0  # type: ignore[misc]


def test_scenario_validation_rejects_missing_and_invented_entity_coverage() -> None:
    scenario, graph, step = make_step_input()
    incomplete = step.model_copy(
        update={"control_commands": step.control_commands[:-1]}
    )
    with pytest.raises(CanonicalStepContractError, match="coverage mismatch"):
        validate_step_input_for_scenario(incomplete, scenario, graph)

    invented = step.model_copy(
        update={
            "internal_gains": (
                InternalGain(
                    source_id="invented_gain",
                    source_kind="other",
                    zone_id="invented_zone",
                    sensible_heat_w=1.0,
                    latent_heat_w=0.0,
                    electrical_power_w=0.0,
                    co2_generation_kg_s=0.0,
                    moisture_generation_kg_s=0.0,
                ),
            )
        }
    )
    with pytest.raises(CanonicalStepContractError, match="unknown zone"):
        validate_step_input_for_scenario(invented, scenario, graph)

    unavailable_heating_id = next(
        system.system_id
        for zone in scenario.building.dwelling.zones
        if zone.zone_id == "living_zone"
        for system in zone.systems
        if system.system_type == "heating"
    )
    unavailable = tuple(
        item.model_copy(update={"available": False, "capacity_fraction": 0.0})
        if item.system_id == unavailable_heating_id
        else item
        for item in step.system_availability
    )
    requested = tuple(
        item.model_copy(update={"heating_on": True, "heating_power_fraction": 1.0})
        if item.zone_id == "living_zone"
        else item
        for item in step.control_commands
    )
    with pytest.raises(CanonicalStepContractError, match="unavailable heating"):
        validate_step_input_for_scenario(
            step.model_copy(
                update={
                    "system_availability": unavailable,
                    "control_commands": requested,
                }
            ),
            scenario,
            graph,
        )


def assert_required_output_contract(result, engine_name: str) -> None:
    assert [item.zone_id for item in result.zones] == [
        "bedroom_zone",
        "living_zone",
    ]
    assert all(item.engine_name == engine_name for item in result.zones)
    assert all(item.fallback_used is False for item in result.zones)
    assert all(
        set(item.model_dump()) == set(REQUIRED_ZONE_OUTPUT_FIELDS)
        for item in result.zones
    )
    assert sum(
        item.electrical_energy_wh for item in result.zone_energy
    ) == pytest.approx(result.dwelling_energy[0].electrical_energy_wh)
    assert result.dwelling_energy[0].electrical_energy_wh == pytest.approx(
        result.building_energy[0].electrical_energy_wh
    )
    assert "dwelling_1" not in str(result.model_dump(mode="json"))


def test_object_adapter_runs_real_engine_and_normalizes_native_records() -> None:
    scenario, graph, step = make_step_input()
    adapter = ObjectEngineAdapter(scenario, graph)
    result = adapter.run_step(step, include_debug=True)

    assert_required_output_contract(result, "object")
    assert result.debug is not None
    native_ids = {
        item["zone_id"] for item in result.debug.engine_fields["native_zone_records"]
    }
    assert native_ids == {item.zone_id for item in result.zones}
    native_by_id = {
        item["zone_id"]: item
        for item in result.debug.engine_fields["native_zone_records"]
    }
    for row in result.zones:
        assert row.air_temperature_c == pytest.approx(
            native_by_id[row.zone_id]["new_indoor_temp_c"]
        )
        assert row.co2_ppm == pytest.approx(native_by_id[row.zone_id]["new_co2_ppm"])
        assert row.heating_power_w == pytest.approx(
            native_by_id[row.zone_id]["command_heating_power_w"]
        )
    assert any(
        item.target_path.endswith("ventilation_fan_power_w")
        for item in result.defaults_applied
    )

    run_result = aggregate_run_results(
        CanonicalRunMetadata(
            scenario_id=scenario.scenario_id,
            run_id=step.run_context.run_id,
            engine_name="object",
            engine_version=adapter.engine_version,
            schema_version=scenario.schema_version,
            graph_sha256=graph["graph_sha256"],
            deterministic_seed=scenario.deterministic_seed,
            started_at=step.timestamp,
            timestep_count=1,
            dt_minutes=step.dt_minutes,
        ),
        (result,),
    )
    assert sum(item.electrical_energy_wh for item in run_result.zone_energy) == (
        pytest.approx(run_result.building_energy[0].electrical_energy_wh)
    )
    assert [item.zone_id for item in run_result.zone_energy] == [
        "bedroom_zone",
        "living_zone",
    ]


def test_array_adapter_runs_real_kernel_and_restores_canonical_ids() -> None:
    scenario, graph, step = make_step_input()
    adapter = ArrayEngineAdapter(scenario, graph)
    result = adapter.run_step(step, include_debug=True)

    assert_required_output_contract(result, "array")
    assert result.debug is not None
    assert adapter.id_registry == graph["id_registry"]
    assert all(isinstance(item.zone_id, str) for item in result.zones)
    assert not any(
        key.endswith("_index")
        for row in result.zones
        for key in row.model_dump()
        if key != "timestep_index"
    )


def test_array_hvac_commands_do_not_mutate_equipment_capacities() -> None:
    """Runtime control and availability scale delivered power, not static design data."""

    scenario, graph, step = make_step_input()
    living_zone = next(
        zone
        for zone in scenario.building.dwelling.zones
        if zone.zone_id == "living_zone"
    )
    heating_system = next(
        system for system in living_zone.systems if system.system_type == "heating"
    )
    design_capacity_w = heating_system.max_heating_power_w
    assert design_capacity_w is not None
    command_fraction = 0.4
    availability_fraction = 0.5
    controls = tuple(
        item.model_copy(
            update={"heating_on": True, "heating_power_fraction": command_fraction}
        )
        if item.zone_id == "living_zone"
        else item
        for item in step.control_commands
    )
    availability = tuple(
        item.model_copy(update={"capacity_fraction": availability_fraction})
        if item.system_id == heating_system.system_id
        else item
        for item in step.system_availability
    )

    result = ArrayEngineAdapter(scenario, graph).run_step(
        step.model_copy(
            update={
                "control_commands": controls,
                "system_availability": availability,
            }
        ),
        include_debug=True,
    )

    living = next(row for row in result.zones if row.zone_id == "living_zone")
    assert living.heating_power_w == pytest.approx(
        design_capacity_w * command_fraction * availability_fraction
    )
    assert result.debug is not None
    trace = result.debug.engine_fields["step_trace"]["controls"]["living_zone"]
    assert trace["max_heating_power_W"] == pytest.approx(design_capacity_w)
    assert trace["command_heating_power_fraction"] == pytest.approx(command_fraction)
    assert trace["heating_capacity_fraction"] == pytest.approx(
        availability_fraction
    )


@pytest.mark.parametrize("adapter_type", [ObjectEngineAdapter, ArrayEngineAdapter])
def test_lighting_watt_command_is_the_delivered_power_contract(adapter_type) -> None:
    """A watt command has one meaning for heat, electric power, and energy."""

    scenario, graph, step = make_step_input()
    commanded_power_w = 80.0
    commands = tuple(
        command.model_copy(
            update={"lights_on": True, "lighting_power_w": commanded_power_w}
        )
        if command.zone_id == "living_zone"
        else command
        for command in step.control_commands
    )
    result = adapter_type(scenario, graph).run_step(
        step.model_copy(update={"control_commands": commands}),
        include_debug=True,
    )

    living = next(row for row in result.zones if row.zone_id == "living_zone")
    assert living.lighting_power_w == pytest.approx(commanded_power_w)
    assert living.total_electrical_power_w == pytest.approx(commanded_power_w)
    living_energy = next(
        row for row in result.zone_energy if row.zone_id == "living_zone"
    )
    assert living_energy.electrical_energy_wh == pytest.approx(
        commanded_power_w * step.dt_minutes / 60.0
    )


@pytest.mark.parametrize("adapter_type", [ObjectEngineAdapter, ArrayEngineAdapter])
def test_canonical_window_solar_gain_uses_site_and_surface_orientation(
    adapter_type,
) -> None:
    scenario, graph, step = make_step_input()
    timestamp = datetime(2026, 6, 21, 12, 0, tzinfo=ZoneInfo("Europe/Rome"))
    weather = step.weather.model_copy(
        update={
            "timestamp": timestamp,
            "direct_normal_radiation_w_m2": 800.0,
            "diffuse_horizontal_radiation_w_m2": 100.0,
            "global_horizontal_radiation_w_m2": 700.0,
        }
    )
    scenario = scenario.model_copy(
        update={
            "simulation_period": scenario.simulation_period.model_copy(
                update={"start_datetime": timestamp}
            ),
            "weather_series": (weather,) + scenario.weather_series[1:],
        }
    )
    step = step.model_copy(update={"timestamp": timestamp, "weather": weather})

    position = calculate_solar_position(
        timestamp,
        latitude_deg=scenario.site.latitude_deg,
        longitude_deg=scenario.site.longitude_deg,
        elevation_m=scenario.site.elevation_m,
        atmospheric_pressure_pa=weather.atmospheric_pressure_pa,
        outdoor_temperature_c=weather.outdoor_temperature_c,
    )
    expected_by_zone = {"bedroom_zone": 0.0, "living_zone": 0.0}
    controls = {item.zone_id: item for item in step.control_commands}
    for connection in graph["connections"]:
        if connection["connection_type"] != "opening":
            continue
        zone_id = connection["source_node_id"]
        irradiance = calculate_surface_solar_irradiance(
            solar_zenith_deg=position.zenith_deg,
            solar_azimuth_deg=position.azimuth_deg,
            surface_tilt_deg=connection["tilt_deg"],
            surface_azimuth_deg=connection["azimuth_deg"],
            direct_normal_radiation_w_m2=weather.direct_normal_radiation_w_m2,
            diffuse_horizontal_radiation_w_m2=(
                weather.diffuse_horizontal_radiation_w_m2
            ),
            global_horizontal_radiation_w_m2=(
                weather.global_horizontal_radiation_w_m2
            ),
            ground_albedo_fraction=scenario.site.ground_albedo_fraction,
        )
        expected_by_zone[zone_id] += irradiance.transmitted_gain_w(
            area_m2=connection["gross_area_m2"],
            solar_transmittance_fraction=connection[
                "solar_transmittance_fraction"
            ],
            unshaded_fraction=controls[zone_id].shading_open_fraction,
        )

    result = adapter_type(scenario, graph).run_step(step, include_debug=True)
    assert result.debug is not None
    records_key = (
        "native_zone_records"
        if adapter_type is ObjectEngineAdapter
        else "zone_records"
    )
    gain_key = (
        "solar_gain_w" if adapter_type is ObjectEngineAdapter else "solar_gain_W"
    )
    actual_by_zone = {
        item["zone_id"]: item[gain_key]
        for item in result.debug.engine_fields[records_key]
    }
    assert actual_by_zone == pytest.approx(expected_by_zone)
    assert actual_by_zone["living_zone"] > actual_by_zone["bedroom_zone"]


def test_array_psychrometrics_consume_canonical_atmospheric_pressure() -> None:
    scenario, graph, step = make_step_input()

    def run_at_pressure(pressure_pa: float):
        weather = step.weather.model_copy(
            update={"atmospheric_pressure_pa": pressure_pa}
        )
        run_scenario = scenario.model_copy(
            update={"weather_series": (weather,) + scenario.weather_series[1:]}
        )
        run_step = step.model_copy(update={"weather": weather})
        return ArrayEngineAdapter(run_scenario, graph).run_step(run_step)

    sea_level = run_at_pressure(101_325.0)
    high_altitude = run_at_pressure(80_000.0)
    assert any(
        abs(left.relative_humidity_fraction - right.relative_humidity_fraction)
        > 1.0e-9
        for left, right in zip(sea_level.zones, high_altitude.zones, strict=True)
    )


def test_adapters_reject_untyped_mapping_and_array_unsupported_inputs() -> None:
    scenario, graph, step = make_step_input()
    object_adapter = ObjectEngineAdapter(scenario, graph)
    with pytest.raises(TypeError, match="SimulationStepInput"):
        object_adapter.run_step(step.model_dump())  # type: ignore[arg-type]

    array_adapter = ArrayEngineAdapter(scenario, graph)
    gain = InternalGain(
        source_id="appliance_gain",
        source_kind="appliance",
        zone_id="living_zone",
        sensible_heat_w=50.0,
        latent_heat_w=0.0,
        electrical_power_w=50.0,
        co2_generation_kg_s=0.0,
        moisture_generation_kg_s=0.0,
    )
    with pytest.raises(BackendAdapterError, match="cannot yet inject"):
        array_adapter.run_step(step.model_copy(update={"internal_gains": (gain,)}))


@pytest.mark.parametrize(
    "command_update",
    [
        {"heating_convective_fraction": 0.7},
        {"ventilation_supply_temperature_c": 18.0},
    ],
)
def test_array_adapter_rejects_unrepresentable_energy_paths(
    command_update: dict[str, float],
) -> None:
    scenario, graph, step = make_step_input()
    commands = tuple(
        item.model_copy(update=command_update)
        if item.zone_id == "living_zone"
        else item
        for item in step.control_commands
    )

    with pytest.raises(BackendAdapterError, match="cannot yet represent"):
        ArrayEngineAdapter(scenario, graph).run_step(
            step.model_copy(update={"control_commands": commands})
        )
