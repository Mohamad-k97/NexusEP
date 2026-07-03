"""
ABBEY building physics engine order.

Phase 10.1:
- defines the unified timestep order
- defines engine input/result containers
- creates one orchestration-order function
- does not yet solve full physics

Important:
    This file is the spine.
    Later Phase 10 subphases fill each step with real module calls.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import copy
from contextlib import contextmanager

@contextmanager
def _measure_if_available(timer, name):
    if timer is None:
        yield
        return
    if not hasattr(timer, "measure"):
        yield
        return
    with timer.measure(name):
        yield
        

PHYSICS_ENGINE_MODEL_FAMILY = "abbey_unified_building_physics_engine"
PHYSICS_ENGINE_PHASE = "10.1"
PHYSICS_ENGINE_SOURCE = "physics.engine.Phase10.1"


PHYSICS_STEP_READ_CURRENT_STATE = "read_current_building_zone_state"
PHYSICS_STEP_READ_WEATHER = "read_weather_state"
PHYSICS_STEP_READ_CONTROL_COMMANDS = "read_zone_control_commands"
PHYSICS_STEP_RESOLVE_WINDOWS = "resolve_window_boundary_results"
PHYSICS_STEP_CALCULATE_DAYLIGHT_LIGHTING = "calculate_daylight_and_lighting"
PHYSICS_STEP_BUILD_INTERNAL_SOURCES = "build_internal_sources"
PHYSICS_STEP_BUILD_AIRFLOW = "build_airflow_network"
PHYSICS_STEP_CALCULATE_CO2 = "calculate_co2"
PHYSICS_STEP_CALCULATE_MOISTURE = "calculate_moisture"
PHYSICS_STEP_CALCULATE_THERMAL = "calculate_thermal"
PHYSICS_STEP_WRITE_ZONE_STATE = "write_updated_zone_state"
PHYSICS_STEP_LOG_OUTPUTS = "log_physics_outputs"
PHYSICS_STEP_CALCULATE_ACOUSTICS = "calculate_acoustics"

PHYSICS_TIMESTEP_ORDER = [
    PHYSICS_STEP_READ_CURRENT_STATE,
    PHYSICS_STEP_READ_WEATHER,
    PHYSICS_STEP_READ_CONTROL_COMMANDS,
    PHYSICS_STEP_RESOLVE_WINDOWS,
    PHYSICS_STEP_CALCULATE_DAYLIGHT_LIGHTING,
    PHYSICS_STEP_BUILD_INTERNAL_SOURCES,
    PHYSICS_STEP_BUILD_AIRFLOW,
    PHYSICS_STEP_CALCULATE_CO2,
    PHYSICS_STEP_CALCULATE_MOISTURE,
    PHYSICS_STEP_CALCULATE_ACOUSTICS,
    PHYSICS_STEP_CALCULATE_THERMAL,
    PHYSICS_STEP_WRITE_ZONE_STATE,
    PHYSICS_STEP_LOG_OUTPUTS,
]


PHYSICS_TIMESTEP_ORDER_INDEX = {
    step_name: index + 1
    for index, step_name in enumerate(PHYSICS_TIMESTEP_ORDER)
}


@dataclass
class PhysicsTimestepStepRecord:
    step_index: int
    step_name: str
    status: str = "declared"
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_index": self.step_index,
            "step_name": self.step_name,
            "status": self.status,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "notes": self.notes,
        }


@dataclass
class BuildingPhysicsStepInput:
    """
    Unified input container for the future real physics engine.

    This is intentionally broad in Phase 10.1.

    Later phases will make this stricter.
    """

    building_model: Any
    dt_minutes: float

    physics_graph: Any = None
    weather_state: Any = None

    zone_control_commands: Dict[str, Any] = field(default_factory=dict)
    zone_system_specs: Dict[str, Any] = field(default_factory=dict)

    people: Dict[str, Any] = field(default_factory=dict)
    locations: Dict[str, Any] = field(default_factory=dict)
    role_to_zone_id: Dict[str, str] = field(default_factory=dict)
    chunk_records: List[Any] = field(default_factory=list)

    window_boundary_result: Any = None
    lighting_power_result: Any = None
    internal_source_result: Any = None
    airflow_network: Any = None
    co2_generation_result: Any = None
    moisture_source_inputs: Any = None
    thermal_gains: Any = None

    previous_air_state: Any = None
    previous_moisture_state: Any = None
    previous_thermal_state: Any = None
    previous_light_state: Any = None
    previous_acoustic_state: Any = None
    source: str = PHYSICS_ENGINE_SOURCE

    def __post_init__(self) -> None:
        if self.building_model is None:
            raise ValueError("BuildingPhysicsStepInput.building_model cannot be None.")

        self.dt_minutes = float(self.dt_minutes)

        if self.dt_minutes <= 0.0:
            raise ValueError("BuildingPhysicsStepInput.dt_minutes must be positive.")

        if self.zone_control_commands is None:
            self.zone_control_commands = {}

        if self.zone_system_specs is None:
            self.zone_system_specs = {}

        if self.people is None:
            self.people = {}

        if self.locations is None:
            self.locations = {}

        if self.role_to_zone_id is None:
            self.role_to_zone_id = {}

        if self.chunk_records is None:
            self.chunk_records = []

    def zone_ids(self) -> List[str]:
        if hasattr(self.building_model, "all_zone_ids"):
            return list(self.building_model.all_zone_ids())

        if hasattr(self.building_model, "all_zone_models"):
            return list(self.building_model.all_zone_models().keys())

        return []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dt_minutes": self.dt_minutes,
            "zone_count": len(self.zone_ids()),
            "has_physics_graph": self.physics_graph is not None,
            "has_weather_state": self.weather_state is not None,
            "zone_control_command_count": len(self.zone_control_commands),
            "zone_system_spec_count": len(self.zone_system_specs),
            "people_count": len(self.people),
            "location_count": len(self.locations),
            "chunk_record_count": len(self.chunk_records),
            "has_window_boundary_result": self.window_boundary_result is not None,
            "has_lighting_power_result": self.lighting_power_result is not None,
            "has_internal_source_result": self.internal_source_result is not None,
            "has_airflow_network": self.airflow_network is not None,
            "has_co2_generation_result": self.co2_generation_result is not None,
            "has_moisture_source_inputs": self.moisture_source_inputs is not None,
            "has_previous_acoustic_state": self.previous_acoustic_state is not None,
            "has_thermal_gains": self.thermal_gains is not None,
            "source": self.source,
        }


@dataclass
class BuildingPhysicsStepOrderResult:
    """
    Phase 10.1 result.

    This is not yet the final physics result.
    It records the decided timestep order and the current availability of inputs.
    """

    step_input: BuildingPhysicsStepInput
    step_records: List[PhysicsTimestepStepRecord] = field(default_factory=list)
    objects: Dict[str, Any] = field(default_factory=dict)
    source: str = PHYSICS_ENGINE_SOURCE

    def step_names(self) -> List[str]:
        return [
            step.step_name
            for step in self.step_records
        ]

    def available_step_names(self) -> List[str]:
        return [
            step.step_name
            for step in self.step_records
            if step.status in {"ready", "available", "declared"}
        ]

    def missing_optional_step_names(self) -> List[str]:
        return [
            step.step_name
            for step in self.step_records
            if step.status == "missing_optional_for_now"
        ]

    def order_is_valid(self) -> bool:
        return self.step_names() == PHYSICS_TIMESTEP_ORDER

    def all_required_runtime_inputs_available(self) -> bool:
        return len(self.missing_optional_step_names()) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_family": PHYSICS_ENGINE_MODEL_FAMILY,
            "phase": PHYSICS_ENGINE_PHASE,
            "order_is_valid": self.order_is_valid(),
            "all_required_runtime_inputs_available": self.all_required_runtime_inputs_available(),
            "missing_optional_step_names": self.missing_optional_step_names(),
            "step_input": self.step_input.to_dict(),
            "step_records": [
                step.to_dict()
                for step in self.step_records
            ],
            "source": self.source,
        }

    def copy(self, **updates: Any) -> "BuildingPhysicsStepOrderResult":
        if not updates:
            return copy.deepcopy(self)

        data = {
            "step_input": self.step_input,
            "step_records": self.step_records,
            "objects": self.objects,
            "source": self.source,
        }

        data.update(updates)

        return BuildingPhysicsStepOrderResult(**data)
    
# ============================================================
# PHASE 10.2 REAL PHYSICS STEP SKELETON
# ============================================================

@dataclass
class BuildingPhysicsStepResult:
    """
    Unified building physics timestep result.

    Phase 10.2:
    - centralizes orchestration
    - calls existing physics modules where already available
    - does not yet replace performance.py
    - does not yet force write-back into BuildingModel
    """

    step_input: BuildingPhysicsStepInput
    order_result: BuildingPhysicsStepOrderResult
    command_constraint_records: List[Dict[str, Any]] = field(default_factory=list)
    
    window_operation_inputs: Any = None
    window_boundary_result: Any = None

    daylight_result: Any = None
    lighting_control_inputs: Any = None
    lighting_power_result: Any = None
    light_state: Any = None

    solar_gain_result: Any = None

    internal_source_result: Any = None
    physics_inputs: Dict[str, Any] = field(default_factory=dict)

    airflow_control_inputs: Any = None
    airflow_network: Any = None

    air_state: Any = None
    co2_step_result: Any = None

    moisture_state: Any = None
    moisture_transport_result: Any = None
    moisture_step_result: Any = None

    acoustic_state: Any = None
    acoustic_step_result: Any = None
    
    thermal_state: Any = None
    thermal_parameters: Any = None
    thermal_ventilation_exchange: Any = None

    interzone_thermal_network: Any = None
    interzone_thermal_flow_records: List[Any] = field(default_factory=list)
    interzone_heat_gains_by_zone_w: Dict[str, float] = field(default_factory=dict)

    thermal_step_result: Any = None

    proposed_zone_states: Dict[str, Any] = field(default_factory=dict)

    zone_records: List[Dict[str, Any]] = field(default_factory=list)
    building_record: Dict[str, Any] = field(default_factory=dict)

    source: str = "physics.engine.Phase10.2"
    
    def interzone_thermal_flow_records_as_dicts(self) -> List[Dict[str, Any]]:
        rows = []

        for record in self.interzone_thermal_flow_records:
            if hasattr(record, "to_dict"):
                rows.append(record.to_dict())
            else:
                rows.append(dict(record))

        return rows
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "order_is_valid": self.order_result.order_is_valid(),
            "command_constraint_record_count": len(self.command_constraint_records),
            "zone_count": len(self.step_input.zone_ids()),
            "has_window_operation_inputs": self.window_operation_inputs is not None,
            "has_window_boundary_result": self.window_boundary_result is not None,
            "has_daylight_result": self.daylight_result is not None,
            "has_lighting_control_inputs": self.lighting_control_inputs is not None,
            "has_lighting_power_result": self.lighting_power_result is not None,
            "has_light_state": self.light_state is not None,
            "has_solar_gain_result": self.solar_gain_result is not None,
            "has_internal_source_result": self.internal_source_result is not None,
            "has_airflow_control_inputs": self.airflow_control_inputs is not None,
            "has_airflow_network": self.airflow_network is not None,
            "has_air_state": self.air_state is not None,
            "has_co2_step_result": self.co2_step_result is not None,
            "has_moisture_state": self.moisture_state is not None,
            "has_moisture_transport_result": self.moisture_transport_result is not None,
            "has_moisture_step_result": self.moisture_step_result is not None,
            "has_acoustic_state": self.acoustic_state is not None,
            "has_acoustic_step_result": self.acoustic_step_result is not None,
            "has_thermal_state": self.thermal_state is not None,
            "has_thermal_parameters": self.thermal_parameters is not None,
            "has_thermal_ventilation_exchange": self.thermal_ventilation_exchange is not None,
            "has_interzone_thermal_network": self.interzone_thermal_network is not None,
            "interzone_thermal_link_count": (
                len(getattr(self.interzone_thermal_network, "links", {}))
                if self.interzone_thermal_network is not None
                else 0
            ),
            "interzone_thermal_flow_record_count": len(
                self.interzone_thermal_flow_records
            ),
            "has_thermal_step_result": self.thermal_step_result is not None,
            "proposed_zone_state_count": len(self.proposed_zone_states),
            "zone_record_count": len(self.zone_records),
            "building_record": dict(self.building_record),
        }


def run_building_physics_step(
    step_input: BuildingPhysicsStepInput,
    require_physics_graph: bool = False,
    write_back_to_building_model: bool = False,
) -> BuildingPhysicsStepResult:
    """
    Run the Phase 10.2 unified physics orchestration.

    Timed v0.5 version:
    - preserves existing physics logic
    - adds coarse timers around major engine phases
    - does not change module behavior
    """

    timer = getattr(step_input, "timer", None)

    with _measure_if_available(timer, "engine.step_total"):

        with _measure_if_available(timer, "engine.validate_inputs"):
            if not isinstance(step_input, BuildingPhysicsStepInput):
                raise TypeError("step_input must be BuildingPhysicsStepInput.")

            if step_input.weather_state is None:
                raise ValueError(
                    "BuildingPhysicsStepInput.weather_state is required in Phase 10.2."
                )

            if require_physics_graph and step_input.physics_graph is None:
                raise ValueError(
                    "physics_graph is required because require_physics_graph=True."
                )

            order_result = run_building_physics_timestep_order(step_input)

            building_model = step_input.building_model
            weather_state = step_input.weather_state
            physics_graph = step_input.physics_graph
            dt_minutes = step_input.dt_minutes

            zone_ids = step_input.zone_ids()

        with _measure_if_available(timer, "engine.command_constraints"):
            from nexusep.abbey.building.systems import (
                constrain_zone_control_command_to_system_spec,
                make_default_zone_system_spec_from_zone_model,
            )

            zone_control_commands = dict(step_input.zone_control_commands or {})
            zone_system_specs = dict(step_input.zone_system_specs or {})

            command_constraint_records = []

            for zone_id in zone_ids:
                if zone_id not in zone_system_specs:
                    zone_model = building_model.get_zone_model(zone_id)

                    zone_system_specs[zone_id] = (
                        make_default_zone_system_spec_from_zone_model(
                            zone_model
                        )
                    )

                    command_constraint_records.append(
                        {
                            "building_id": getattr(zone_model, "building_id", None),
                            "dwelling_id": getattr(zone_model, "dwelling_id", None),
                            "zone_id": zone_id,
                            "field": "zone_system_spec",
                            "old_value": None,
                            "new_value": "default_created",
                            "reason": "missing_zone_system_spec_default_created",
                        }
                    )

                command = zone_control_commands.get(zone_id)

                if command is None:
                    continue

                constraint_result = constrain_zone_control_command_to_system_spec(
                    command=command,
                    system_spec=zone_system_specs[zone_id],
                )

                zone_control_commands[zone_id] = constraint_result.command
                command_constraint_records.extend(constraint_result.records)

        # ------------------------------------------------------------
        # Current dynamic states from BuildingModel / ZoneState.
        # ------------------------------------------------------------
        with _measure_if_available(timer, "engine.make_current_states"):
            thermal_state = (
                step_input.previous_thermal_state
                or _make_current_thermal_state_from_building_model(building_model)
            )

            air_state = (
                step_input.previous_air_state
                or _make_current_air_state_from_building_model(building_model)
            )

        # ------------------------------------------------------------
        # Windows.
        # ------------------------------------------------------------
        with _measure_if_available(timer, "engine.windows"):
            window_operation_inputs = None
            window_boundary_result = step_input.window_boundary_result

            if physics_graph is not None:
                window_operation_inputs = (
                    _make_window_operation_inputs_from_zone_commands(
                        physics_graph=physics_graph,
                        zone_control_commands=zone_control_commands,
                    )
                )

                if window_boundary_result is None:
                    from nexusep.abbey.building.physics.windows import (
                        calculate_building_window_boundary_result,
                    )

                    window_boundary_result = calculate_building_window_boundary_result(
                        physics_graph=physics_graph,
                        building_model=building_model,
                        building_window_operation_inputs=window_operation_inputs,
                        weather_state=weather_state,
                    )

        # ------------------------------------------------------------
        # Daylight + lighting.
        # ------------------------------------------------------------
        with _measure_if_available(timer, "engine.daylight_lighting"):
            daylight_result = None

            lighting_control_inputs = (
                _make_lighting_control_inputs_from_zone_commands(
                    building_model=building_model,
                    zone_control_commands=zone_control_commands,
                )
            )

            lighting_power_result = step_input.lighting_power_result

            if physics_graph is not None:
                from nexusep.abbey.building.physics.daylight import (
                    estimate_building_indoor_daylight,
                    calculate_building_lighting_from_controls,
                    make_building_light_state_from_daylight_and_lighting,
                )

                daylight_result = estimate_building_indoor_daylight(
                    building_model=building_model,
                    physics_graph=physics_graph,
                    weather_state=weather_state,
                    window_boundary_result=window_boundary_result,
                )

                if lighting_power_result is None:
                    lighting_power_result = calculate_building_lighting_from_controls(
                        building_model=building_model,
                        lighting_control_inputs=lighting_control_inputs,
                        zone_system_specs=zone_system_specs,
                        dt_minutes=dt_minutes,
                    )

                light_state = make_building_light_state_from_daylight_and_lighting(
                    building_model=building_model,
                    daylight_result=daylight_result,
                    lighting_power_result=lighting_power_result,
                )

            else:
                light_state = step_input.previous_light_state

        # ------------------------------------------------------------
        # Solar gains.
        # ------------------------------------------------------------
        with _measure_if_available(timer, "engine.solar_gains"):
            solar_gain_result = None
            solar_gains_by_zone_w = {}

            if physics_graph is not None:
                from nexusep.abbey.building.physics.thermal import (
                    calculate_solar_gains_for_thermal,
                )

                solar_gain_result = calculate_solar_gains_for_thermal(
                    physics_graph=physics_graph,
                    weather_state=weather_state,
                    window_boundary_result=window_boundary_result,
                )

                solar_gains_by_zone_w = solar_gain_result.solar_gains_by_zone_w()

        # ------------------------------------------------------------
        # Internal source bridge.
        # ------------------------------------------------------------
        with _measure_if_available(timer, "engine.internal_sources"):
            internal_source_result = step_input.internal_source_result

            if internal_source_result is None:
                from nexusep.abbey.building.physics.internal_sources import (
                    make_building_internal_source_result,
                )

                internal_source_result = make_building_internal_source_result(
                    chunk_records=step_input.chunk_records,
                    people=step_input.people,
                    locations=step_input.locations,
                    role_to_zone_id=step_input.role_to_zone_id,
                    building_model=building_model,
                    dt_minutes=dt_minutes,
                    include_people=True,
                    include_lighting=True,
                    lighting_power_result=lighting_power_result,
                    include_hvac=False,
                    zone_control_commands=zone_control_commands,
                    zone_system_specs=zone_system_specs,
                )

        with _measure_if_available(timer, "engine.physics_inputs"):
            from nexusep.abbey.building.physics.internal_sources import (
                make_physics_inputs_from_internal_sources,
            )

            physics_inputs = make_physics_inputs_from_internal_sources(
                internal_source_result=internal_source_result,
                zone_ids=zone_ids,
                solar_gains_by_zone_w=solar_gains_by_zone_w,
            )

            airflow_control_inputs = physics_inputs.get(
                "airflow_control_inputs",
                None,
            )

            co2_generation_result = physics_inputs.get(
                "co2_generation_result",
                None,
            )

            moisture_source_inputs = physics_inputs.get(
                "moisture_source_inputs",
                None,
            )

            thermal_gains = physics_inputs.get(
                "thermal_gains",
                None,
            )

            airflow_control_inputs = (
                _add_ventilation_commands_to_airflow_control_inputs(
                    airflow_control_inputs=airflow_control_inputs,
                    zone_ids=zone_ids,
                    zone_control_commands=zone_control_commands,
                )
            )

            physics_inputs["airflow_control_inputs"] = airflow_control_inputs

            thermal_gains = _add_hvac_command_gains_to_thermal_gains(
                zone_ids=zone_ids,
                base_thermal_gains=thermal_gains,
                zone_control_commands=zone_control_commands,
                zone_system_specs=zone_system_specs,
            )

            physics_inputs["thermal_gains"] = thermal_gains

        # ------------------------------------------------------------
        # Airflow.
        # ------------------------------------------------------------
        with _measure_if_available(timer, "engine.airflow"):
            airflow_network = step_input.airflow_network

            if airflow_network is None:
                if physics_graph is not None:
                    from nexusep.abbey.building.physics.airflow import (
                        calculate_building_airflow_network,
                    )

                    airflow_network = calculate_building_airflow_network(
                        building_model=building_model,
                        physics_graph=physics_graph,
                        weather_state=weather_state,
                        airflow_control_inputs=airflow_control_inputs,
                        window_boundary_result=window_boundary_result,
                    )

                else:
                    from nexusep.abbey.building.physics.airflow import (
                        calculate_building_mechanical_only_airflow_network,
                    )

                    airflow_network = calculate_building_mechanical_only_airflow_network(
                        building_model=building_model,
                        airflow_control_inputs=airflow_control_inputs,
                    )

        # ------------------------------------------------------------
        # CO2.
        # ------------------------------------------------------------
        with _measure_if_available(timer, "engine.co2"):
            co2_step_result = None

            if airflow_network is not None and co2_generation_result is not None:
                from nexusep.abbey.building.physics.airflow import (
                    step_building_co2_state,
                )

                co2_step_result = step_building_co2_state(
                    air_state=air_state,
                    airflow_network=airflow_network,
                    co2_generation_result=co2_generation_result,
                    weather_state=weather_state,
                    dt_minutes=dt_minutes,
                )

        # ------------------------------------------------------------
        # Moisture.
        # ------------------------------------------------------------
        with _measure_if_available(timer, "engine.moisture"):
            moisture_state = (
                step_input.previous_moisture_state
                or _make_current_moisture_state_from_building_model(
                    building_model=building_model,
                    thermal_state=thermal_state,
                    weather_state=weather_state,
                )
            )

            moisture_transport_result = None
            moisture_step_result = None

            if airflow_network is not None and moisture_source_inputs is not None:
                from nexusep.abbey.building.physics.moisture import (
                    make_building_moisture_parameters,
                    make_outdoor_moisture_boundary_from_weather_state,
                    make_building_moisture_transport_result,
                    step_building_moisture_state,
                )

                building_moisture_parameters = make_building_moisture_parameters(
                    building_model=building_model,
                )

                outdoor_moisture_boundary = (
                    make_outdoor_moisture_boundary_from_weather_state(
                        weather_state=weather_state,
                    )
                )

                moisture_transport_result = make_building_moisture_transport_result(
                    moisture_state=moisture_state,
                    airflow_network=airflow_network,
                    outdoor_moisture_boundary=outdoor_moisture_boundary,
                )

                pressure_pa = _safe_atmospheric_pressure_pa(
                    weather_state=weather_state,
                )

                moisture_step_result = step_building_moisture_state(
                    moisture_state=moisture_state,
                    building_moisture_parameters=building_moisture_parameters,
                    moisture_transport_result=moisture_transport_result,
                    moisture_source_inputs=moisture_source_inputs,
                    thermal_state=thermal_state,
                    atmospheric_pressure_pa=pressure_pa,
                    dt_minutes=dt_minutes,
                )

        # ------------------------------------------------------------
        # Acoustics.
        # ------------------------------------------------------------
        with _measure_if_available(timer, "engine.acoustic"):
            acoustic_step_result = None
            acoustic_state = step_input.previous_acoustic_state

            from nexusep.abbey.building.physics.acoustics import (
                step_building_acoustic_state,
            )

            acoustic_step_result = step_building_acoustic_state(
                building_model=building_model,
                physics_graph=physics_graph,
                weather_state=weather_state,
                internal_source_result=internal_source_result,
                previous_acoustic_state=acoustic_state,
                dt_minutes=dt_minutes,
            )

            acoustic_state = acoustic_step_result.updated_state

        # ------------------------------------------------------------
        # Thermal.
        # ------------------------------------------------------------
        with _measure_if_available(timer, "engine.thermal"):
            from nexusep.abbey.building.physics.thermal import (
                make_building_thermal_parameters,
                make_ventilation_heat_exchange_for_thermal,
                make_interzone_thermal_network_from_physics_graph,
                calculate_interzone_heat_flow_records,
                aggregate_interzone_heat_gains_by_zone_w,
                step_building_thermal_state_semi_implicit,
            )

            thermal_parameters = make_building_thermal_parameters(
                building_model=building_model,
            )

            thermal_ventilation_exchange = make_ventilation_heat_exchange_for_thermal(
                building_model=building_model,
                airflow_network=airflow_network,
            )

            interzone_thermal_network = None
            interzone_thermal_flow_records = []
            interzone_heat_gains_by_zone_w = {}

            if physics_graph is not None:
                interzone_thermal_network = (
                    make_interzone_thermal_network_from_physics_graph(
                        physics_graph=physics_graph,
                    )
                )

                interzone_thermal_flow_records = calculate_interzone_heat_flow_records(
                    interzone_network=interzone_thermal_network,
                    thermal_state=thermal_state,
                )

                interzone_heat_gains_by_zone_w = (
                    aggregate_interzone_heat_gains_by_zone_w(
                        interzone_thermal_flow_records
                    )
                )

            additional_outside_conductance_by_zone_w_k = {}

            if window_boundary_result is not None and hasattr(
                window_boundary_result,
                "closed_window_conductance_by_zone_w_k",
            ):
                additional_outside_conductance_by_zone_w_k = (
                    window_boundary_result.closed_window_conductance_by_zone_w_k()
                )

            thermal_step_result = step_building_thermal_state_semi_implicit(
                thermal_state=thermal_state,
                building_parameters=thermal_parameters,
                weather_state=weather_state,
                building_gains=thermal_gains,
                interzone_network=interzone_thermal_network,
                ventilation_exchange=thermal_ventilation_exchange,
                additional_outside_conductance_by_zone_w_k=additional_outside_conductance_by_zone_w_k,
                dt_minutes=dt_minutes,
            )

        # ------------------------------------------------------------
        # Proposed ZoneState write-back + records.
        # ------------------------------------------------------------
        with _measure_if_available(timer, "engine.write_state_records"):
            proposed_zone_states = _make_proposed_zone_states(
                building_model=building_model,
                thermal_step_result=thermal_step_result,
                co2_step_result=co2_step_result,
                moisture_step_result=moisture_step_result,
                light_state=light_state,
                acoustic_step_result=acoustic_step_result,
            )

            if write_back_to_building_model:
                for zone_id, zone_state in proposed_zone_states.items():
                    building_model.set_zone_state(zone_id, zone_state)

            zone_records = _make_engine_zone_records(
                building_model=building_model,
                proposed_zone_states=proposed_zone_states,
                internal_source_result=internal_source_result,
                thermal_step_result=thermal_step_result,
                co2_step_result=co2_step_result,
                moisture_step_result=moisture_step_result,
                light_state=light_state,
                airflow_network=airflow_network,
                thermal_ventilation_exchange=thermal_ventilation_exchange,
                interzone_thermal_network=interzone_thermal_network,
                interzone_heat_gains_by_zone_w=interzone_heat_gains_by_zone_w,
                zone_control_commands=zone_control_commands,
                zone_system_specs=zone_system_specs,
                window_boundary_result=window_boundary_result,
                acoustic_step_result=acoustic_step_result,
                daylight_result=daylight_result,
                lighting_power_result=lighting_power_result,
                solar_gain_result=solar_gain_result,
            )

            building_record = _make_engine_building_record(
                zone_records=zone_records,
                internal_source_result=internal_source_result,
                solar_gain_result=solar_gain_result,
                airflow_network=airflow_network,
                co2_step_result=co2_step_result,
                moisture_step_result=moisture_step_result,
                thermal_step_result=thermal_step_result,
                interzone_thermal_network=interzone_thermal_network,
                interzone_thermal_flow_records=interzone_thermal_flow_records,
                command_constraint_records=command_constraint_records,
                window_boundary_result=window_boundary_result,
                acoustic_step_result=acoustic_step_result,
                daylight_result=daylight_result,
                lighting_power_result=lighting_power_result,
                light_state=light_state,
            )

        with _measure_if_available(timer, "engine.make_result"):
            return BuildingPhysicsStepResult(
                step_input=step_input,
                order_result=order_result,
                command_constraint_records=command_constraint_records,
                window_operation_inputs=window_operation_inputs,
                window_boundary_result=window_boundary_result,
                daylight_result=daylight_result,
                lighting_control_inputs=lighting_control_inputs,
                lighting_power_result=lighting_power_result,
                light_state=light_state,
                solar_gain_result=solar_gain_result,
                internal_source_result=internal_source_result,
                physics_inputs=physics_inputs,
                airflow_control_inputs=airflow_control_inputs,
                airflow_network=airflow_network,
                air_state=air_state,
                co2_step_result=co2_step_result,
                moisture_state=moisture_state,
                moisture_transport_result=moisture_transport_result,
                moisture_step_result=moisture_step_result,
                thermal_state=thermal_state,
                thermal_parameters=thermal_parameters,
                thermal_ventilation_exchange=thermal_ventilation_exchange,
                interzone_thermal_network=interzone_thermal_network,
                interzone_thermal_flow_records=interzone_thermal_flow_records,
                interzone_heat_gains_by_zone_w=interzone_heat_gains_by_zone_w,
                thermal_step_result=thermal_step_result,
                acoustic_state=acoustic_state,
                acoustic_step_result=acoustic_step_result,
                proposed_zone_states=proposed_zone_states,
                zone_records=zone_records,
                building_record=building_record,
            )


# ============================================================
# PHASE 10.2 HELPERS
# ============================================================

def _safe_atmospheric_pressure_pa(
    weather_state: Any,
    default_pa: float = 101325.0,
) -> float:
    value = _get_attr_or_key(
        weather_state,
        "atmospheric_pressure_pa",
        None,
    )

    if value is None:
        return float(default_pa)

    try:
        value = float(value)
    except Exception:
        return float(default_pa)

    if value <= 0.0:
        return float(default_pa)

    return value


def _get_attr_or_key(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(key, default)

    return getattr(obj, key, default)

def _internal_source_record_count_from_bridge_row(
    bridge_row: Dict[str, Any],
) -> int:
    if bridge_row is None:
        return 0

    value = bridge_row.get(
        "record_count",
        bridge_row.get("internal_source_record_count", 0),
    )

    try:
        value = int(value)
    except Exception:
        value = 0

    if value > 0:
        return value

    by_kind = bridge_row.get(
        "internal_record_count_by_source_kind",
        bridge_row.get("record_count_by_source_kind", {}),
    )

    if isinstance(by_kind, dict):
        total = 0

        for item in by_kind.values():
            try:
                total += int(item)
            except Exception:
                pass

        return total

    return 0

def _clamp(value: float, lower: float, upper: float) -> float:
    value = float(value)

    if value < lower:
        return lower

    if value > upper:
        return upper

    return value


def _make_current_thermal_state_from_building_model(building_model: Any) -> Any:
    from nexusep.abbey.building.physics.thermal import (
        BuildingThermalState,
        ZoneThermalState,
    )

    zone_states = {}

    for zone_id, zone_model in building_model.all_zone_models().items():
        zone_state = building_model.get_zone_state(zone_id)

        air_temp_c = float(
            _get_attr_or_key(zone_state, "indoor_temp_c", 20.0)
        )

        mass_temp_c = _get_attr_or_key(
            zone_state,
            "indoor_mass_temp_c",
            None,
        )

        if mass_temp_c is None:
            mass_temp_c = _get_attr_or_key(
                zone_model,
                "initial_mass_temperature_c",
                air_temp_c,
            )

        if mass_temp_c is None:
            mass_temp_c = air_temp_c

        zone_states[zone_id] = ZoneThermalState(
            zone_id=zone_id,
            air_temperature_c=air_temp_c,
            mass_temperature_c=float(mass_temp_c),
        )

    return BuildingThermalState(
        zone_states=zone_states,
    )

def _make_current_air_state_from_building_model(building_model: Any) -> Any:
    from nexusep.abbey.building.physics.airflow import (
        BuildingAirState,
        ZoneAirState,
    )

    zone_states = {}

    for zone_id, zone_model in building_model.all_zone_models().items():
        zone_state = building_model.get_zone_state(zone_id)

        zone_states[zone_id] = ZoneAirState(
            zone_id=zone_id,
            co2_ppm=float(_get_attr_or_key(zone_state, "co2_ppm", 600.0)),
            air_volume_m3=float(
                _get_attr_or_key(
                    zone_model,
                    "air_volume_m3",
                    _get_attr_or_key(zone_model, "volume_m3", 50.0),
                )
            ),
        )

    return BuildingAirState(
        zone_states=zone_states,
    )


def _make_current_moisture_state_from_building_model(
    building_model: Any,
    thermal_state: Any,
    weather_state: Any,
) -> Any:
    from nexusep.abbey.building.physics.moisture import (
        make_initial_building_moisture_state,
    )

    pressure_pa = _safe_atmospheric_pressure_pa(
        weather_state=weather_state,
    )

    return make_initial_building_moisture_state(
        building_model=building_model,
        thermal_state=thermal_state,
        atmospheric_pressure_pa=pressure_pa,
    )


def _make_window_operation_inputs_from_zone_commands(
    physics_graph: Any,
    zone_control_commands: Dict[str, Any],
) -> Any:
    from nexusep.abbey.building.physics.windows import (
        make_window_operation_inputs,
    )

    if physics_graph is None:
        return None

    is_open_by_window = {}
    opening_fraction_by_window = {}
    curtain_open_by_window = {}
    zone_id_by_window = {}

    for window_id, boundary in getattr(physics_graph, "boundary_connections", {}).items():
        is_window = bool(_get_attr_or_key(boundary, "is_window", False))

        if not is_window:
            continue

        zone_id = _get_attr_or_key(boundary, "zone_id", "")

        if not zone_id:
            continue

        command = zone_control_commands.get(zone_id)

        zone_id_by_window[window_id] = zone_id

        if command is None:
            is_open_by_window[window_id] = False
            opening_fraction_by_window[window_id] = 0.0
            curtain_open_by_window[window_id] = True
            continue

        is_open_by_window[window_id] = bool(
            _get_attr_or_key(command, "window_open", False)
        )

        opening_fraction_by_window[window_id] = float(
            _get_attr_or_key(command, "window_opening_fraction", 0.0)
        )

        curtain_open_by_window[window_id] = bool(
            _get_attr_or_key(command, "curtain_open", True)
        )

    return make_window_operation_inputs(
        is_open_by_window=is_open_by_window,
        opening_fraction_by_window=opening_fraction_by_window,
        curtain_open_by_window=curtain_open_by_window,
        zone_id_by_window=zone_id_by_window,
    )


def _make_lighting_control_inputs_from_zone_commands(
    building_model: Any,
    zone_control_commands: Dict[str, Any],
) -> Any:
    from nexusep.abbey.building.physics.daylight import (
        make_lighting_control_inputs,
    )

    lights_on_by_zone = {}
    dimming_fraction_by_zone = {}
    requested_lux_by_zone = {}

    for zone_id, zone_model in building_model.all_zone_models().items():
        command = zone_control_commands.get(zone_id)

        lights_on = False

        if command is not None:
            lights_on = bool(_get_attr_or_key(command, "lights_on", False))

        lights_on_by_zone[zone_id] = lights_on
        dimming_fraction_by_zone[zone_id] = 1.0 if lights_on else 0.0
        requested_lux_by_zone[zone_id] = float(
            _get_attr_or_key(zone_model, "visual_comfort_target_lux", 300.0)
        ) if lights_on else 0.0

    return make_lighting_control_inputs(
        lights_on_by_zone=lights_on_by_zone,
        dimming_fraction_by_zone=dimming_fraction_by_zone,
        requested_artificial_lighting_by_zone_lux=requested_lux_by_zone,
    )


def _make_proposed_zone_states(
    building_model: Any,
    thermal_step_result: Any,
    co2_step_result: Any = None,
    moisture_step_result: Any = None,
    light_state: Any = None,
    acoustic_step_result: Any = None,
) -> Dict[str, Any]:
    proposed = {}

    thermal_updated_state = None

    if thermal_step_result is not None:
        thermal_updated_state = _get_attr_or_key(
            thermal_step_result,
            "updated_state",
            None,
        )

    co2_updated_state = None

    if co2_step_result is not None:
        co2_updated_state = _get_attr_or_key(
            co2_step_result,
            "updated_air_state",
            None,
        )
    moisture_updated_state = None
    
    if moisture_step_result is not None:
        moisture_updated_state = _get_attr_or_key(
            moisture_step_result,
            "updated_moisture_state",
            None,
        )
        
    acoustic_results = {}

    if acoustic_step_result is not None and hasattr(
        acoustic_step_result,
        "zone_results",
    ):
        acoustic_results = acoustic_step_result.zone_results
        
    for zone_id, old_zone_state in building_model.all_zone_states().items():
        new_temp_c = float(_get_attr_or_key(old_zone_state, "indoor_temp_c", 20.0))

        new_mass_temp_c = _get_attr_or_key(
            old_zone_state,
            "indoor_mass_temp_c",
            None,
        )

        if new_mass_temp_c is None:
            new_mass_temp_c = new_temp_c

        new_mass_temp_c = float(new_mass_temp_c)

        new_co2_ppm = float(_get_attr_or_key(old_zone_state, "co2_ppm", 600.0))
        new_indoor_daylight = float(
            _get_attr_or_key(old_zone_state, "indoor_daylight", 0.5)
        )
        new_indoor_noise = float(
            _get_attr_or_key(old_zone_state, "indoor_noise", 0.2)
        )
        new_indoor_relative_humidity_percent = _get_attr_or_key(
            old_zone_state,
            "indoor_relative_humidity_percent",
            None,
        )
        
        new_indoor_humidity_ratio_kg_kg = _get_attr_or_key(
            old_zone_state,
            "indoor_humidity_ratio_kg_kg",
            None,
        )
        if (
            thermal_updated_state is not None
            and hasattr(thermal_updated_state, "has_zone")
            and thermal_updated_state.has_zone(zone_id)
        ):
            thermal_zone_state = thermal_updated_state.get_zone_state(zone_id)

            new_temp_c = float(
                thermal_zone_state.air_temperature_c
            )

            new_mass_temp_c = float(
                thermal_zone_state.mass_temperature_c
            )

        if (
            co2_updated_state is not None
            and hasattr(co2_updated_state, "has_zone")
            and co2_updated_state.has_zone(zone_id)
        ):
            new_co2_ppm = float(
                co2_updated_state.get_zone_state(zone_id).co2_ppm
            )
        if (
            moisture_updated_state is not None
            and hasattr(moisture_updated_state, "has_zone")
            and moisture_updated_state.has_zone(zone_id)
        ):
            moisture_zone_state = moisture_updated_state.get_zone_state(zone_id)
        
            new_indoor_humidity_ratio_kg_kg = float(
                _get_attr_or_key(
                    moisture_zone_state,
                    "humidity_ratio_kg_kg",
                    new_indoor_humidity_ratio_kg_kg,
                )
            )
        
            new_indoor_relative_humidity_percent = float(
                _get_attr_or_key(
                    moisture_zone_state,
                    "relative_humidity_percent",
                    new_indoor_relative_humidity_percent
                    if new_indoor_relative_humidity_percent is not None
                    else 50.0,
                )
            )
        if (
            light_state is not None
            and hasattr(light_state, "has_zone")
            and light_state.has_zone(zone_id)
        ):
            zone_model = building_model.get_zone_model(zone_id)
            target_lux = float(
                _get_attr_or_key(zone_model, "visual_comfort_target_lux", 300.0)
            )

            if target_lux <= 0.0:
                target_lux = 300.0

            lux = float(
                light_state.get_zone_state(zone_id).indoor_illuminance_lux
            )

            new_indoor_daylight = _clamp(
                lux / target_lux,
                0.0,
                1.0,
            )
        acoustic_zone_result = acoustic_results.get(zone_id)

        if acoustic_zone_result is not None:
            if hasattr(acoustic_zone_result, "to_zone_state_indoor_noise"):
                new_indoor_noise = float(
                    acoustic_zone_result.to_zone_state_indoor_noise()
                )
            else:
                new_indoor_noise = float(
                    _get_attr_or_key(
                        acoustic_zone_result,
                        "acoustic_discomfort_input",
                        new_indoor_noise,
                    )
                )

            new_indoor_noise = _clamp(
                new_indoor_noise,
                0.0,
                1.0,
            )
        proposed[zone_id] = old_zone_state.copy(
            indoor_temp_c=new_temp_c,
            indoor_mass_temp_c=new_mass_temp_c,
            co2_ppm=new_co2_ppm,
            indoor_daylight=new_indoor_daylight,
            indoor_noise=new_indoor_noise,
            indoor_relative_humidity_percent=new_indoor_relative_humidity_percent,
            indoor_humidity_ratio_kg_kg=new_indoor_humidity_ratio_kg_kg,
        )

    return proposed

def _iter_container_values(value: Any) -> List[Any]:
    if value is None:
        return []

    if isinstance(value, dict):
        return list(value.values())

    if isinstance(value, list):
        return list(value)

    if isinstance(value, tuple):
        return list(value)

    return []


def _safe_max(values: List[float], default: float = 0.0) -> float:
    cleaned = [
        float(value)
        for value in values
        if value is not None
    ]

    if not cleaned:
        return float(default)

    return max(cleaned)


def _safe_sum(values: List[float]) -> float:
    return sum(
        float(value)
        for value in values
        if value is not None
    )


def _semicolon_join(values: List[Any]) -> str:
    return ";".join(
        str(value)
        for value in values
        if value is not None
    )


def _window_results_by_zone_from_boundary_result(
    window_boundary_result: Any,
) -> Dict[str, List[Any]]:
    out = {}

    if window_boundary_result is None:
        return out

    raw_results = getattr(
        window_boundary_result,
        "window_results_by_id",
        {},
    )

    for result in _iter_container_values(raw_results):
        zone_id = str(_get_attr_or_key(result, "zone_id", "")).strip()

        if not zone_id:
            continue

        if zone_id not in out:
            out[zone_id] = []

        out[zone_id].append(result)

    return out
def _make_engine_zone_records(
    building_model: Any,
    proposed_zone_states: Dict[str, Any],
    internal_source_result: Any,
    thermal_step_result: Any = None,
    co2_step_result: Any = None,
    moisture_step_result: Any = None,
    light_state: Any = None,
    airflow_network: Any = None,
    thermal_ventilation_exchange: Any = None,
    interzone_thermal_network: Any = None,
    interzone_heat_gains_by_zone_w: Optional[Dict[str, float]] = None,
    zone_control_commands: Optional[Dict[str, Any]] = None,
    zone_system_specs: Optional[Dict[str, Any]] = None,
    acoustic_step_result: Any = None,
    window_boundary_result: Any = None,
    daylight_result: Any = None,
    lighting_power_result: Any = None,
    solar_gain_result: Any = None,
) -> List[Dict[str, Any]]:
    
    records = []
    zone_control_commands = zone_control_commands or {}
    zone_system_specs = zone_system_specs or {}
    interzone_heat_gains_by_zone_w = interzone_heat_gains_by_zone_w or {}
    internal_bridge_by_zone = {}
    solar_gains_by_zone_w = {}

    if solar_gain_result is not None and hasattr(
        solar_gain_result,
        "solar_gains_by_zone_w",
    ):
        solar_gains_by_zone_w = solar_gain_result.solar_gains_by_zone_w()

    window_results_by_zone = _window_results_by_zone_from_boundary_result(
        window_boundary_result
    )
    if internal_source_result is not None and hasattr(
        internal_source_result,
        "physics_bridge_inputs_by_zone",
    ):
        internal_bridge_by_zone = internal_source_result.physics_bridge_inputs_by_zone()
    acoustic_results_by_zone = {}

    if acoustic_step_result is not None and hasattr(
        acoustic_step_result,
        "zone_results",
    ):
        acoustic_results_by_zone = acoustic_step_result.zone_results
    for zone_id, zone_state in proposed_zone_states.items():
        old_state = building_model.get_zone_state(zone_id)
        bridge_row = internal_bridge_by_zone.get(zone_id, {})
        command = zone_control_commands.get(zone_id)
        system_spec = zone_system_specs.get(zone_id)
        thermal_zone_result = None
        airflow_record = None

        if (
            thermal_step_result is not None
            and hasattr(thermal_step_result, "zone_results")
        ):
            thermal_zone_result = thermal_step_result.zone_results.get(zone_id)
        else:
            thermal_zone_result = None
            
        heating_power_w = 0.0
        cooling_power_w = 0.0

        if command is not None and system_spec is not None:
            heating_power_w = (
                float(_get_attr_or_key(command, "heating_power_fraction", 0.0))
                * float(_get_attr_or_key(system_spec, "heating_capacity_w", 0.0))
            )

            cooling_power_w = (
                float(_get_attr_or_key(command, "cooling_power_fraction", 0.0))
                * float(_get_attr_or_key(system_spec, "cooling_capacity_w", 0.0))
            )
            
        heating_power_fraction = float(
            _get_attr_or_key(command, "heating_power_fraction", 0.0)
        )

        cooling_power_fraction = float(
            _get_attr_or_key(command, "cooling_power_fraction", 0.0)
        )

        heating_capacity_w = float(
            _get_attr_or_key(system_spec, "heating_capacity_w", 0.0)
        )

        cooling_capacity_w = float(
            _get_attr_or_key(system_spec, "cooling_capacity_w", 0.0)
        )

        heating_efficiency_or_cop = float(
            _get_attr_or_key(system_spec, "heating_efficiency_or_cop", 1.0)
        )

        cooling_efficiency_or_cop = float(
            _get_attr_or_key(system_spec, "cooling_efficiency_or_cop", 1.0)
        )

        if heating_efficiency_or_cop <= 0.0:
            heating_efficiency_or_cop = 1.0

        if cooling_efficiency_or_cop <= 0.0:
            cooling_efficiency_or_cop = 1.0

        heating_input_power_w = heating_power_w / heating_efficiency_or_cop
        cooling_input_power_w = cooling_power_w / cooling_efficiency_or_cop
        
        outdoor_airflow_record = None

        if airflow_network is not None and hasattr(
            airflow_network,
            "get_outdoor_airflow_for_zone",
        ):
            outdoor_airflow_record = airflow_network.get_outdoor_airflow_for_zone(
                zone_id
            )

        outdoor_exchange_m3_h = 0.0
        mechanical_ventilation_flow_m3_h = 0.0
        infiltration_flow_m3_h = 0.0
        window_airflow_m3_h = 0.0

        if outdoor_airflow_record is not None:
            outdoor_exchange_m3_h = float(
                _get_attr_or_key(
                    outdoor_airflow_record,
                    "mixing_exchange_m3_h",
                    0.0,
                )
            )
            mechanical_ventilation_flow_m3_h = float(
                _get_attr_or_key(
                    outdoor_airflow_record,
                    "mechanical_ventilation_flow_m3_h",
                    0.0,
                )
            )
            infiltration_flow_m3_h = float(
                _get_attr_or_key(
                    outdoor_airflow_record,
                    "infiltration_flow_m3_h",
                    0.0,
                )
            )
            window_airflow_m3_h = float(
                _get_attr_or_key(
                    outdoor_airflow_record,
                    "window_airflow_m3_h",
                    0.0,
                )
            )

        interzone_exchange_m3_h = 0.0

        if airflow_network is not None and hasattr(
            airflow_network,
            "interzone_mixing_by_zone_m3_h",
        ):
            interzone_exchange_m3_h = float(
                airflow_network
                .interzone_mixing_by_zone_m3_h()
                .get(zone_id, 0.0)
            )

        total_air_exchange_m3_h = outdoor_exchange_m3_h + interzone_exchange_m3_h

        thermal_ventilation_h_w_k = 0.0

        if (
            thermal_ventilation_exchange is not None
            and hasattr(thermal_ventilation_exchange, "zone_ventilation")
            and zone_id in thermal_ventilation_exchange.zone_ventilation
        ):
            thermal_ventilation_h_w_k = float(
                _get_attr_or_key(
                    thermal_ventilation_exchange.zone_ventilation[zone_id],
                    "h_ventilation_w_k",
                    0.0,
                )
            )
            
        dt_hours = 0.0

        if hasattr(thermal_step_result, "dt_minutes"):
            dt_hours = float(thermal_step_result.dt_minutes) / 60.0
        interzone_thermal_link_count = 0
        interzone_thermal_total_h_w_k = 0.0

        if interzone_thermal_network is not None:
            links_for_zone = interzone_thermal_network.links_for_zone(zone_id)
            interzone_thermal_link_count = len(links_for_zone)
            interzone_thermal_total_h_w_k = sum(
                float(_get_attr_or_key(link, "h_w_k", 0.0))
                for link in links_for_zone
            )

        interzone_net_heat_gain_w = float(
            interzone_heat_gains_by_zone_w.get(zone_id, 0.0)
        )

        interzone_heat_gain_w = max(interzone_net_heat_gain_w, 0.0)
        interzone_heat_loss_w = max(-interzone_net_heat_gain_w, 0.0)       
        
        co2_generation_m3_h = float(
            bridge_row.get("average_co2_generation_m3_h", 0.0)
        )

        moisture_generation_kg_h = float(
            bridge_row.get("average_moisture_generation_kg_h", 0.0)
        )

        moisture_zone_result = None

        if (
            moisture_step_result is not None
            and hasattr(moisture_step_result, "zone_results")
        ):
            moisture_zone_result = moisture_step_result.zone_results.get(zone_id)

        old_humidity_ratio_kg_kg = _get_attr_or_key(
            old_state,
            "indoor_humidity_ratio_kg_kg",
            None,
        )

        new_humidity_ratio_kg_kg = _get_attr_or_key(
            zone_state,
            "indoor_humidity_ratio_kg_kg",
            None,
        )

        old_relative_humidity_percent = _get_attr_or_key(
            old_state,
            "indoor_relative_humidity_percent",
            None,
        )

        new_relative_humidity_percent = _get_attr_or_key(
            zone_state,
            "indoor_relative_humidity_percent",
            None,
        )

        moisture_transport_airflow_m3_h = 0.0

        if moisture_zone_result is not None:
            old_humidity_ratio_kg_kg = _get_attr_or_key(
                moisture_zone_result,
                "old_humidity_ratio_kg_kg",
                old_humidity_ratio_kg_kg,
            )

            new_humidity_ratio_kg_kg = _get_attr_or_key(
                moisture_zone_result,
                "new_humidity_ratio_kg_kg",
                new_humidity_ratio_kg_kg,
            )

            old_relative_humidity_percent = _get_attr_or_key(
                moisture_zone_result,
                "old_relative_humidity_percent",
                old_relative_humidity_percent,
            )

            new_relative_humidity_percent = _get_attr_or_key(
                moisture_zone_result,
                "new_relative_humidity_percent",
                new_relative_humidity_percent,
            )

            moisture_generation_kg_h = (
                float(
                    _get_attr_or_key(
                        moisture_zone_result,
                        "moisture_generation_kg_s",
                        0.0,
                    )
                )
                * 3600.0
            )

            moisture_transport_airflow_m3_h = sum(
                float(_get_attr_or_key(target, "airflow_m3_s", 0.0))
                * 3600.0
                for target in _get_attr_or_key(
                    moisture_zone_result,
                    "targets",
                    [],
                )
            )
        zone_window_results = window_results_by_zone.get(zone_id, [])

        window_count = len(zone_window_results)

        window_orientation_values = [
            _get_attr_or_key(result, "orientation_deg", None)
            for result in zone_window_results
        ]

        window_solar_alignment_values = [
            _get_attr_or_key(result, "solar_alignment_factor", 0.0)
            for result in zone_window_results
        ]

        window_daylight_alignment_values = [
            _get_attr_or_key(result, "daylight_alignment_factor", 0.0)
            for result in zone_window_results
        ]

        window_effective_solar_factor_values = [
            _get_attr_or_key(result, "effective_solar_factor", 0.0)
            for result in zone_window_results
        ]

        window_effective_visible_transmittance_values = [
            _get_attr_or_key(result, "effective_visible_transmittance", 0.0)
            for result in zone_window_results
        ]

        window_curtain_open_count = sum(
            1
            for result in zone_window_results
            if bool(_get_attr_or_key(result, "curtain_open", True))
        )

        window_curtain_closed_count = window_count - window_curtain_open_count

        solar_gain_w = float(
            solar_gains_by_zone_w.get(zone_id, 0.0)
        )

        daylight_illuminance_lux = 0.0

        if daylight_result is not None and hasattr(daylight_result, "get_zone_result"):
            daylight_zone_result = daylight_result.get_zone_result(zone_id)
            daylight_illuminance_lux = float(
                _get_attr_or_key(
                    daylight_zone_result,
                    "daylight_illuminance_lux",
                    0.0,
                )
            )

        indoor_illuminance_lux = 0.0
        artificial_lighting_illuminance_lux = 0.0
        visual_comfort_status = ""

        if (
            light_state is not None
            and hasattr(light_state, "has_zone")
            and light_state.has_zone(zone_id)
        ):
            zone_light_state = light_state.get_zone_state(zone_id)

            indoor_illuminance_lux = float(
                _get_attr_or_key(
                    zone_light_state,
                    "indoor_illuminance_lux",
                    0.0,
                )
            )

            artificial_lighting_illuminance_lux = float(
                _get_attr_or_key(
                    zone_light_state,
                    "artificial_lighting_illuminance_lux",
                    0.0,
                )
            )

            visual_comfort_status = str(
                _get_attr_or_key(
                    zone_light_state,
                    "visual_comfort_status",
                    "",
                )
            )

        lighting_result_lights_on = False
        lighting_result_power_w = 0.0
        lighting_result_energy_wh = 0.0
        lighting_result_requested_lux = 0.0
        lighting_result_dimming_fraction = 0.0

        if (
            lighting_power_result is not None
            and hasattr(lighting_power_result, "get_zone_result")
        ):
            lighting_zone_result = lighting_power_result.get_zone_result(zone_id)

            lighting_result_lights_on = bool(
                _get_attr_or_key(lighting_zone_result, "lights_on", False)
            )

            lighting_result_power_w = float(
                _get_attr_or_key(lighting_zone_result, "lighting_power_w", 0.0)
            )

            lighting_result_energy_wh = float(
                _get_attr_or_key(lighting_zone_result, "lighting_energy_wh", 0.0)
            )

            lighting_result_requested_lux = float(
                _get_attr_or_key(
                    lighting_zone_result,
                    "requested_artificial_lighting_lux",
                    0.0,
                )
            )

            lighting_result_dimming_fraction = float(
                _get_attr_or_key(
                    lighting_zone_result,
                    "dimming_fraction",
                    0.0,
                )
            )   
            
        acoustic_zone_result = acoustic_results_by_zone.get(zone_id)

        indoor_noise_db = 0.0
        background_noise_db = 0.0
        outdoor_noise_db = 0.0
        local_noise_source_db = 0.0
        local_noise_source_count = 0
        outdoor_noise_contribution_db = 0.0
        interzone_noise_contribution_db = 0.0
        max_neighbor_noise_contribution_db = 0.0
        acoustic_discomfort_input = float(
            _get_attr_or_key(zone_state, "indoor_noise", 0.0)
        )

        if acoustic_zone_result is not None:
            indoor_noise_db = float(
                _get_attr_or_key(acoustic_zone_result, "indoor_noise_db", 0.0)
            )

            background_noise_db = float(
                _get_attr_or_key(acoustic_zone_result, "background_noise_db", 0.0)
            )

            local_noise_source_db = float(
                _get_attr_or_key(acoustic_zone_result, "local_noise_source_db", 0.0)
            )

            local_noise_source_count = int(
                _get_attr_or_key(acoustic_zone_result, "local_noise_source_count", 0)
            )

            outdoor_noise_contribution_db = float(
                _get_attr_or_key(
                    acoustic_zone_result,
                    "outdoor_noise_contribution_db",
                    0.0,
                )
            )

            interzone_noise_contribution_db = float(
                _get_attr_or_key(
                    acoustic_zone_result,
                    "interzone_noise_contribution_db",
                    0.0,
                )
            )

            max_neighbor_noise_contribution_db = float(
                _get_attr_or_key(
                    acoustic_zone_result,
                    "max_neighbor_noise_contribution_db",
                    0.0,
                )
            )

            acoustic_discomfort_input = float(
                _get_attr_or_key(
                    acoustic_zone_result,
                    "acoustic_discomfort_input",
                    acoustic_discomfort_input,
                )
            )

        if acoustic_step_result is not None:
            outdoor_boundary = _get_attr_or_key(
                acoustic_step_result,
                "outdoor_boundary",
                None,
            )

            outdoor_noise_db = float(
                _get_attr_or_key(
                    outdoor_boundary,
                    "outdoor_noise_db",
                    0.0,
                )
            )
        old_indoor_daylight = _get_attr_or_key(
            old_state,
            "indoor_daylight",
            None,
        )

        new_indoor_daylight = _get_attr_or_key(
            zone_state,
            "indoor_daylight",
            None,
        )

        old_indoor_noise = _get_attr_or_key(
            old_state,
            "indoor_noise",
            None,
        )

        new_indoor_noise = _get_attr_or_key(
            zone_state,
            "indoor_noise",
            None,
        )
        internal_source_record_count = int(
            bridge_row.get("record_count", 0)
        )

        internal_average_sensible_heat_w = float(
            bridge_row.get("average_sensible_heat_w", 0.0)
        )

        internal_average_latent_heat_w = float(
            bridge_row.get("average_latent_heat_w", 0.0)
        )

        internal_average_electricity_power_w = float(
            bridge_row.get("average_electricity_power_w", 0.0)
        )

        internal_electricity_wh = float(
            bridge_row.get("electricity_wh", 0.0)
        )

        total_internal_gain_w = (
            internal_average_sensible_heat_w
            + internal_average_latent_heat_w
        )
        internal_electricity_wh_by_source_kind = bridge_row.get(
            "internal_electricity_wh_by_source_kind",
            bridge_row.get("electricity_wh_by_source_kind", {}),
        )

        internal_average_latent_heat_w_by_source_kind = bridge_row.get(
            "internal_average_latent_heat_w_by_source_kind",
            bridge_row.get("average_latent_heat_w_by_source_kind", {}),
        )

        appliance_electricity_wh_from_sources = float(
            bridge_row.get("appliance_electricity_wh", 0.0)
        )

        lighting_electricity_wh_from_sources = float(
            bridge_row.get("lighting_electricity_wh", 0.0)
        )

        hvac_electricity_wh_from_sources = float(
            bridge_row.get("hvac_electricity_wh", 0.0)
        )

        hvac_heating_gain_w = float(
            bridge_row.get("hvac_heating_gain_w", 0.0)
        )

        hvac_cooling_gain_w = float(
            bridge_row.get("hvac_cooling_gain_w", 0.0)
        )

        hvac_cooling_removal_w = float(
            bridge_row.get("hvac_cooling_removal_w", 0.0)
        )

        hvac_sensible_gain_w = float(
            bridge_row.get("hvac_sensible_gain_w", 0.0)
        )

        appliance_total_heat_w = float(
            bridge_row.get("appliance_total_heat_w", 0.0)
        )

        appliance_total_heat_wh = float(
            bridge_row.get("appliance_total_heat_wh", 0.0)
        )

        lighting_sensible_heat_w = float(
            bridge_row.get("lighting_sensible_heat_w", 0.0)
        )


        total_internal_gain_wh = total_internal_gain_w * dt_hours

        record = {
            "physics_path": "engine",
            "legacy_fallback_used": False,
            "zone_id": zone_id,
            "old_indoor_temp_c": _get_attr_or_key(old_state, "indoor_temp_c", None),
            "new_indoor_temp_c": _get_attr_or_key(zone_state, "indoor_temp_c", None),
            "old_indoor_mass_temp_c": _get_attr_or_key(
                old_state,
                "indoor_mass_temp_c",
                None,
            ),
            "new_indoor_mass_temp_c": _get_attr_or_key(
                zone_state,
                "indoor_mass_temp_c",
                None,
            ),
            "thermal_old_air_temperature_c": _get_attr_or_key(
                thermal_zone_result,
                "old_air_temperature_c",
                None,
            ),
            "thermal_new_air_temperature_c": _get_attr_or_key(
                thermal_zone_result,
                "new_air_temperature_c",
                None,
            ),
            "thermal_old_mass_temperature_c": _get_attr_or_key(
                thermal_zone_result,
                "old_mass_temperature_c",
                None,
            ),
            "thermal_new_mass_temperature_c": _get_attr_or_key(
                thermal_zone_result,
                "new_mass_temperature_c",
                None,
            ),
            "thermal_convective_gain_w": _get_attr_or_key(
                thermal_zone_result,
                "convective_gain_w",
                0.0,
            ),
            "thermal_radiative_gain_w": _get_attr_or_key(
                thermal_zone_result,
                "radiative_gain_w",
                0.0,
            ),
            "old_co2_ppm": _get_attr_or_key(old_state, "co2_ppm", None),
            "new_co2_ppm": _get_attr_or_key(zone_state, "co2_ppm", None),
            "co2_generation_m3_h": co2_generation_m3_h,

            "old_humidity_ratio_kg_kg": old_humidity_ratio_kg_kg,
            "new_humidity_ratio_kg_kg": new_humidity_ratio_kg_kg,
            "old_relative_humidity_percent": old_relative_humidity_percent,
            "new_relative_humidity_percent": new_relative_humidity_percent,
            "moisture_generation_kg_h": moisture_generation_kg_h,
            "moisture_transport_airflow_m3_h": moisture_transport_airflow_m3_h,
            "old_indoor_relative_humidity_percent": _get_attr_or_key(
                old_state,
                "indoor_relative_humidity_percent",
                None,
            ),
            "new_indoor_relative_humidity_percent": _get_attr_or_key(
                zone_state,
                "indoor_relative_humidity_percent",
                None,
            ),
            "old_indoor_humidity_ratio_kg_kg": _get_attr_or_key(
                old_state,
                "indoor_humidity_ratio_kg_kg",
                None,
            ),
            "new_indoor_humidity_ratio_kg_kg": _get_attr_or_key(
                zone_state,
                "indoor_humidity_ratio_kg_kg",
                None,
            ),
            "old_indoor_daylight": old_indoor_daylight,
            "new_indoor_daylight": new_indoor_daylight,
            "old_indoor_noise": old_indoor_noise,
            "new_indoor_noise": new_indoor_noise,
            "proposed_indoor_noise": new_indoor_noise,
            "proposed_indoor_daylight": _get_attr_or_key(
                zone_state,
                "indoor_daylight",
                None,
            ),

            "window_count": window_count,
            "window_orientation_deg_list": _semicolon_join(
                window_orientation_values
            ),
            "window_curtain_open_count": window_curtain_open_count,
            "window_curtain_closed_count": window_curtain_closed_count,
            "window_solar_alignment_factor_max": _safe_max(
                window_solar_alignment_values,
                default=0.0,
            ),
            "window_daylight_alignment_factor_max": _safe_max(
                window_daylight_alignment_values,
                default=0.0,
            ),
            "window_effective_solar_factor_sum": _safe_sum(
                window_effective_solar_factor_values
            ),
            "window_effective_solar_factor_max": _safe_max(
                window_effective_solar_factor_values,
                default=0.0,
            ),
            "window_effective_visible_transmittance_sum": _safe_sum(
                window_effective_visible_transmittance_values
            ),
            "window_effective_visible_transmittance_max": _safe_max(
                window_effective_visible_transmittance_values,
                default=0.0,
            ),
            "indoor_noise": _get_attr_or_key(zone_state, "indoor_noise", None),
            "indoor_noise_db": indoor_noise_db,
            "background_noise_db": background_noise_db,
            "outdoor_noise_db": outdoor_noise_db,
            "local_noise_source_db": local_noise_source_db,
            "local_noise_source_count": local_noise_source_count,
            "outdoor_noise_contribution_db": outdoor_noise_contribution_db,
            "interzone_noise_contribution_db": interzone_noise_contribution_db,
            "max_neighbor_noise_contribution_db": max_neighbor_noise_contribution_db,
            "acoustic_discomfort_input": acoustic_discomfort_input,
            "solar_gain_w": solar_gain_w,
            "solar_gain_wh": solar_gain_w * dt_hours,

            "daylight_illuminance_lux": daylight_illuminance_lux,
            "indoor_illuminance_lux": indoor_illuminance_lux,
            "artificial_lighting_illuminance_lux": artificial_lighting_illuminance_lux,
            "visual_comfort_status": visual_comfort_status,

            "lighting_result_lights_on": lighting_result_lights_on,
            "lighting_result_power_w": lighting_result_power_w,
            "lighting_result_energy_wh": lighting_result_energy_wh,
            "lighting_result_requested_lux": lighting_result_requested_lux,
            "lighting_result_dimming_fraction": lighting_result_dimming_fraction,
            "command_heating_on": bool(_get_attr_or_key(command, "heating_on", False)),
            "command_heating_power_fraction": heating_power_fraction,
            "command_heating_power_w": heating_power_w,
            "command_heating_delivered_power_w": heating_power_w,
            
            "command_cooling_on": bool(_get_attr_or_key(command, "cooling_on", False)),
            "command_cooling_power_fraction": cooling_power_fraction,
            "command_cooling_power_w": cooling_power_w,
            "command_cooling_delivered_power_w": cooling_power_w,
            "command_hvac_thermal_gain_w": heating_power_w - cooling_power_w,
            "command_heating_delivered_energy_wh": heating_power_w * dt_hours,
            "command_cooling_delivered_energy_wh": cooling_power_w * dt_hours,
            "command_ventilation_flow_m3_h": float(
                _get_attr_or_key(command, "ventilation_flow_m3_h", 0.0)
            ),
            "heating_power_fraction": heating_power_fraction,
            "cooling_power_fraction": cooling_power_fraction,
            "heating_capacity_w": heating_capacity_w,
            "cooling_capacity_w": cooling_capacity_w,
            "heating_efficiency_or_cop": heating_efficiency_or_cop,
            "cooling_efficiency_or_cop": cooling_efficiency_or_cop,
            "heating_input_power_w": heating_input_power_w,
            "cooling_input_power_w": cooling_input_power_w,
            "airflow_infiltration_flow_m3_h": infiltration_flow_m3_h,
            "airflow_mechanical_ventilation_flow_m3_h": mechanical_ventilation_flow_m3_h,
            "airflow_window_flow_m3_h": window_airflow_m3_h,
            "airflow_outdoor_exchange_m3_h": outdoor_exchange_m3_h,
            "airflow_interzone_exchange_m3_h": interzone_exchange_m3_h,
            "airflow_total_exchange_m3_h": total_air_exchange_m3_h,
            "thermal_ventilation_h_w_k": thermal_ventilation_h_w_k,
            "interzone_thermal_link_count": interzone_thermal_link_count,
            "interzone_thermal_total_h_w_k": interzone_thermal_total_h_w_k,
            "interzone_heat_gain_w": interzone_heat_gain_w,
            "interzone_heat_loss_w": interzone_heat_loss_w,
            "interzone_net_heat_gain_w": interzone_net_heat_gain_w,
            "command_lights_on": bool(_get_attr_or_key(command, "lights_on", False)),
            "command_lighting_power_w": float(
                _get_attr_or_key(command, "lighting_power_w", 0.0)
            ),
            "command_window_open": bool(_get_attr_or_key(command, "window_open", False)),
            "command_window_opening_fraction": float(
                _get_attr_or_key(command, "window_opening_fraction", 0.0)
            ),
            "command_curtain_open": bool(_get_attr_or_key(command, "curtain_open", True)),

            # ------------------------------------------------------------
            # Internal-source diagnostics from BuildingInternalSourceResult.
            # These are output/audit fields. They do not create physics;
            # the actual thermal/CO2/moisture coupling already happened
            # through physics_inputs.
            # ------------------------------------------------------------
            "internal_source_record_count": _internal_source_record_count_from_bridge_row(
                bridge_row
            ),

            "internal_average_sensible_heat_w": bridge_row.get(
                "average_sensible_heat_w",
                bridge_row.get("internal_average_sensible_heat_w", 0.0),
            ),

                        # ------------------------------------------------------------
            # Phase 15.6 internal-source / energy audit fields.
            # ------------------------------------------------------------
            "internal_electricity_wh_by_source_kind": internal_electricity_wh_by_source_kind,
            "internal_average_latent_heat_w_by_source_kind": internal_average_latent_heat_w_by_source_kind,
            
            "appliance_electricity_wh_from_internal_sources": appliance_electricity_wh_from_sources,
            "lighting_electricity_wh_from_internal_sources": lighting_electricity_wh_from_sources,
            "hvac_electricity_wh_from_internal_sources": hvac_electricity_wh_from_sources,
            
            "appliance_total_heat_w": appliance_total_heat_w,
            "appliance_total_heat_wh": appliance_total_heat_wh,
            "lighting_sensible_heat_w": lighting_sensible_heat_w,
            
            "hvac_sensible_gain_w": hvac_sensible_gain_w,
            "hvac_heating_gain_w": hvac_heating_gain_w,
            "hvac_cooling_gain_w": hvac_cooling_gain_w,
            "hvac_cooling_removal_w": hvac_cooling_removal_w,
            

            "internal_average_moisture_generation_kg_h": bridge_row.get(
                "average_moisture_generation_kg_h",
                0.0,
            ),
            "internal_average_sensible_heat_w_by_source_kind": bridge_row.get(
                "average_sensible_heat_w_by_source_kind",
                {},
            ),
            "internal_average_electricity_power_w_by_source_kind": bridge_row.get(
                "average_electricity_power_w_by_source_kind",
                {},
            ),
            "internal_average_co2_generation_m3_h_by_source_kind": bridge_row.get(
                "average_co2_generation_m3_h_by_source_kind",
                {},
            ),
            "internal_average_moisture_generation_kg_h_by_source_kind": bridge_row.get(
                "average_moisture_generation_kg_h_by_source_kind",
                {},
            ),
            "internal_record_count_by_source_kind": bridge_row.get(
                "record_count_by_source_kind",
                {},
            ),
            "total_internal_gain_w": total_internal_gain_w,
            "total_internal_gain_wh": total_internal_gain_wh,
        }

        records.append(record)

    return records


def _make_engine_building_record(
    zone_records: List[Dict[str, Any]],
    internal_source_result: Any = None,
    solar_gain_result: Any = None,
    airflow_network: Any = None,
    co2_step_result: Any = None,
    moisture_step_result: Any = None,
    thermal_step_result: Any = None,
    interzone_thermal_network: Any = None,
    interzone_thermal_flow_records: Optional[List[Any]] = None,
    command_constraint_records: Optional[List[Dict[str, Any]]] = None,
    window_boundary_result: Any = None,
    daylight_result: Any = None,
    acoustic_step_result: Any = None,
    lighting_power_result: Any = None,
    light_state: Any = None,
) -> Dict[str, Any]:
    if command_constraint_records is None:
        command_constraint_records = []
    if interzone_thermal_flow_records is None:
        interzone_thermal_flow_records = []
    record = {
        "physics_path": "engine",
        "legacy_fallback_used": False,
        "zone_count": len(zone_records),
        "has_internal_source_result": internal_source_result is not None,
        "has_solar_gain_result": solar_gain_result is not None,
        "has_airflow_network": airflow_network is not None,
        "has_co2_step_result": co2_step_result is not None,
        "has_moisture_step_result": moisture_step_result is not None,
        "has_thermal_step_result": thermal_step_result is not None,
        "has_interzone_thermal_network": interzone_thermal_network is not None,
        "has_acoustic_step_result": acoustic_step_result is not None,
        "interzone_thermal_link_count": (
            len(getattr(interzone_thermal_network, "links", {}))
            if interzone_thermal_network is not None
            else 0
        ),
        "interzone_thermal_flow_record_count": len(interzone_thermal_flow_records),
        "command_constraint_record_count": len(command_constraint_records),
        "command_constraints_applied": len(command_constraint_records) > 0,
    }

    if internal_source_result is not None:
        record["internal_source_record_count"] = len(
            getattr(internal_source_result, "records", [])
        )

        if hasattr(internal_source_result, "total_electricity_wh"):
            record["internal_total_electricity_wh"] = (
                internal_source_result.total_electricity_wh()
            )

        if hasattr(internal_source_result, "total_average_sensible_heat_w"):
            record["internal_total_average_sensible_heat_w"] = (
                internal_source_result.total_average_sensible_heat_w()
            )

        if hasattr(internal_source_result, "total_co2_generation_m3_h"):
            record["internal_total_co2_generation_m3_h"] = (
                internal_source_result.total_co2_generation_m3_h()
            )

        if hasattr(internal_source_result, "total_moisture_generation_kg_h"):
            record["internal_total_moisture_generation_kg_h"] = (
                internal_source_result.total_moisture_generation_kg_h()
            )

    if solar_gain_result is not None and hasattr(solar_gain_result, "total_solar_gain_w"):
        record["total_solar_gain_w"] = solar_gain_result.total_solar_gain_w()
    daylight_values = [
        float(row.get("daylight_illuminance_lux", 0.0))
        for row in zone_records
    ]

    indoor_lux_values = [
        float(row.get("indoor_illuminance_lux", 0.0))
        for row in zone_records
    ]

    solar_gain_values = [
        float(row.get("solar_gain_w", 0.0))
        for row in zone_records
    ]

    lighting_power_values = [
        float(row.get("lighting_result_power_w", 0.0))
        for row in zone_records
    ]

    lighting_energy_values = [
        float(row.get("lighting_result_energy_wh", 0.0))
        for row in zone_records
    ]

    record["window_count"] = sum(
        int(row.get("window_count", 0))
        for row in zone_records
    )

    record["window_curtain_closed_count"] = sum(
        int(row.get("window_curtain_closed_count", 0))
        for row in zone_records
    )

    record["total_solar_gain_w_from_zone_records"] = sum(solar_gain_values)
    record["max_zone_solar_gain_w"] = _safe_max(solar_gain_values, default=0.0)

    record["average_zone_daylight_illuminance_lux"] = (
        sum(daylight_values) / len(daylight_values)
        if daylight_values
        else 0.0
    )

    record["max_zone_daylight_illuminance_lux"] = _safe_max(
        daylight_values,
        default=0.0,
    )

    record["average_zone_indoor_illuminance_lux"] = (
        sum(indoor_lux_values) / len(indoor_lux_values)
        if indoor_lux_values
        else 0.0
    )

    record["max_zone_indoor_illuminance_lux"] = _safe_max(
        indoor_lux_values,
        default=0.0,
    )

    record["total_lighting_power_result_w"] = sum(lighting_power_values)
    record["total_lighting_result_energy_wh"] = sum(lighting_energy_values)
    
    indoor_noise_values = [
        float(row.get("indoor_noise", 0.0))
        for row in zone_records
        if row.get("indoor_noise", None) is not None
    ]

    indoor_noise_db_values = [
        float(row.get("indoor_noise_db", 0.0))
        for row in zone_records
        if row.get("indoor_noise_db", None) is not None
    ]

    local_noise_source_counts = [
        int(row.get("local_noise_source_count", 0))
        for row in zone_records
    ]

    record["average_zone_indoor_noise"] = (
        sum(indoor_noise_values) / len(indoor_noise_values)
        if indoor_noise_values
        else 0.0
    )

    record["max_zone_indoor_noise"] = _safe_max(
        indoor_noise_values,
        default=0.0,
    )

    record["average_zone_indoor_noise_db"] = (
        sum(indoor_noise_db_values) / len(indoor_noise_db_values)
        if indoor_noise_db_values
        else 0.0
    )

    record["max_zone_indoor_noise_db"] = _safe_max(
        indoor_noise_db_values,
        default=0.0,
    )

    record["total_local_noise_source_count"] = sum(local_noise_source_counts)
    
    return record


def physics_timestep_order_names() -> List[str]:
    return list(PHYSICS_TIMESTEP_ORDER)


def assert_valid_physics_timestep_order(order: Optional[List[str]] = None) -> None:
    if order is None:
        order = PHYSICS_TIMESTEP_ORDER

    if list(order) != PHYSICS_TIMESTEP_ORDER:
        raise ValueError(
            "Invalid physics timestep order.\nExpected:\n"
            + "\n".join(PHYSICS_TIMESTEP_ORDER)
            + "\nGot:\n"
            + "\n".join(list(order))
        )


def make_physics_timestep_step_record(
    step_name: str,
    status: str = "declared",
    inputs: Optional[List[str]] = None,
    outputs: Optional[List[str]] = None,
    notes: str = "",
) -> PhysicsTimestepStepRecord:
    if step_name not in PHYSICS_TIMESTEP_ORDER_INDEX:
        raise ValueError("Unknown physics timestep step: " + str(step_name))

    return PhysicsTimestepStepRecord(
        step_index=PHYSICS_TIMESTEP_ORDER_INDEX[step_name],
        step_name=step_name,
        status=status,
        inputs=inputs or [],
        outputs=outputs or [],
        notes=notes,
    )


def run_building_physics_timestep_order(
    step_input: BuildingPhysicsStepInput,
) -> BuildingPhysicsStepOrderResult:
    """
    Phase 10.1 orchestration function.

    This function defines the order and records the input/output contract.
    It deliberately does not yet run all solvers.

    Later:
        10.2+ will replace each "ready" contract step with actual calls.
    """

    if not isinstance(step_input, BuildingPhysicsStepInput):
        raise TypeError("step_input must be BuildingPhysicsStepInput.")

    zone_ids = step_input.zone_ids()

    step_records = []

    step_records.append(
        make_physics_timestep_step_record(
            step_name=PHYSICS_STEP_READ_CURRENT_STATE,
            status="ready",
            inputs=["BuildingModel", "ZoneState"],
            outputs=["current_zone_state_by_zone"],
            notes="BuildingModel remains source of truth for zones.",
        )
    )

    step_records.append(
        make_physics_timestep_step_record(
            step_name=PHYSICS_STEP_READ_WEATHER,
            status="ready" if step_input.weather_state is not None else "missing_optional_for_now",
            inputs=["WeatherState"],
            outputs=["outdoor boundary conditions"],
            notes="WeatherState is required for real window, airflow, daylight, moisture, and thermal execution.",
        )
    )

    step_records.append(
        make_physics_timestep_step_record(
            step_name=PHYSICS_STEP_READ_CONTROL_COMMANDS,
            status="ready",
            inputs=["ZoneControlCommand", "ZoneSystemSpec"],
            outputs=["zone_control_commands", "zone_system_specs"],
            notes="Commands are produced before physics engine, currently by performance/controller path.",
        )
    )

    step_records.append(
        make_physics_timestep_step_record(
            step_name=PHYSICS_STEP_RESOLVE_WINDOWS,
            status="ready" if step_input.physics_graph is not None else "missing_optional_for_now",
            inputs=["BuildingPhysicsGraph", "BuildingModel", "WeatherState", "window operation inputs"],
            outputs=["BuildingWindowBoundaryResult"],
            notes="Shared window result feeds daylight, airflow, and thermal.",
        )
    )

    step_records.append(
        make_physics_timestep_step_record(
            step_name=PHYSICS_STEP_CALCULATE_DAYLIGHT_LIGHTING,
            status="ready",
            inputs=["WeatherState", "BuildingWindowBoundaryResult", "ZoneControlCommand", "ZoneSystemSpec"],
            outputs=["BuildingIndoorDaylightResult", "BuildingLightingPowerResult"],
            notes="Lighting result should feed internal_sources before thermal.",
        )
    )

    step_records.append(
        make_physics_timestep_step_record(
            step_name=PHYSICS_STEP_BUILD_INTERNAL_SOURCES,
            status="ready",
            inputs=["people", "locations", "chunk_records", "lighting_power_result", "zone_control_commands"],
            outputs=["BuildingInternalSourceResult", "thermal/CO2/moisture source adapters"],
            notes="This is the Phase 9 bridge.",
        )
    )

    step_records.append(
        make_physics_timestep_step_record(
            step_name=PHYSICS_STEP_BUILD_AIRFLOW,
            status="ready" if step_input.physics_graph is not None else "missing_optional_for_now",
            inputs=["BuildingAirflowControlInputs", "BuildingWindowBoundaryResult", "WeatherState", "BuildingPhysicsGraph"],
            outputs=["BuildingAirflowNetwork"],
            notes="Airflow must be built before CO2, moisture transport, and thermal ventilation exchange.",
        )
    )

    step_records.append(
        make_physics_timestep_step_record(
            step_name=PHYSICS_STEP_CALCULATE_CO2,
            status="ready",
            inputs=["BuildingAirState", "BuildingAirflowNetwork", "BuildingCO2GenerationResult", "WeatherState"],
            outputs=["BuildingCO2StepResult"],
            notes="CO2 uses source rates from internal_sources, not direct action parsing.",
        )
    )

    step_records.append(
        make_physics_timestep_step_record(
            step_name=PHYSICS_STEP_CALCULATE_MOISTURE,
            status="ready",
            inputs=["BuildingMoistureState", "BuildingAirflowNetwork", "BuildingMoistureSourceInputs", "WeatherState", "current thermal state"],
            outputs=["BuildingMoistureStepResult"],
            notes="For now moisture uses current/pre-update thermal temperature. No moisture-to-thermal feedback yet.",
        )
    )
    step_records.append(
        make_physics_timestep_step_record(
            step_name=PHYSICS_STEP_CALCULATE_ACOUSTICS,
            status="ready",
            inputs=[
                "BuildingModel",
                "BuildingPhysicsGraph",
                "WeatherState",
                "BuildingInternalSourceResult",
            ],
            outputs=[
                "BuildingAcousticState",
                "BuildingAcousticStepResult",
            ],
            notes="Phase 14 placeholder acoustic step.",
        ),
    )
    step_records.append(
        make_physics_timestep_step_record(
            step_name=PHYSICS_STEP_CALCULATE_THERMAL,
            status="ready",
            inputs=["BuildingThermalState", "BuildingThermalGains", "BuildingAirflowNetwork", "BuildingWindowBoundaryResult", "WeatherState"],
            outputs=["BuildingSemiImplicitThermalStepResult"],
            notes="Thermal uses internal gains, solar/window effects, and airflow ventilation exchange.",
        )
    )
    


    step_records.append(
        make_physics_timestep_step_record(
            step_name=PHYSICS_STEP_WRITE_ZONE_STATE,
            status="declared",
            inputs=["thermal result", "CO2 result", "moisture result", "daylight result"],
            outputs=["updated BuildingModel ZoneState", "updated DwellingObservation"],
            notes="Phase 10 engine writes proposed ZoneState objects when requested.",
        )
    )

    step_records.append(
        make_physics_timestep_step_record(
            step_name=PHYSICS_STEP_LOG_OUTPUTS,
            status="declared",
            inputs=["all physics step results"],
            outputs=["physics timestep records"],
            notes="Phase 10 engine records command, airflow, CO2, moisture, and thermal diagnostics.",
        )
    )

    assert_valid_physics_timestep_order(
        [
            step.step_name
            for step in step_records
        ]
    )

    objects = {
        "zone_ids": zone_ids,
        "weather_state": step_input.weather_state,
        "zone_control_commands": step_input.zone_control_commands,
        "zone_system_specs": step_input.zone_system_specs,
        "window_boundary_result": step_input.window_boundary_result,
        "lighting_power_result": step_input.lighting_power_result,
        "internal_source_result": step_input.internal_source_result,
        "airflow_network": step_input.airflow_network,
        "co2_generation_result": step_input.co2_generation_result,
        "moisture_source_inputs": step_input.moisture_source_inputs,
        "thermal_gains": step_input.thermal_gains,
    }

    return BuildingPhysicsStepOrderResult(
        step_input=step_input,
        step_records=step_records,
        objects=objects,
        source=PHYSICS_ENGINE_SOURCE,
    )

def _add_ventilation_commands_to_airflow_control_inputs(
    airflow_control_inputs: Any,
    zone_ids: List[str],
    zone_control_commands: Dict[str, Any],
) -> Any:
    """
    Convert final ZoneControlCommand ventilation flow into airflow inputs.

    This is the key 10.9 bridge:
        ZoneControlCommand.ventilation_flow_m3_h
            -> MechanicalVentilationInput
            -> BuildingAirflowNetwork
            -> CO2 / moisture / thermal
    """

    from nexusep.abbey.building.physics.airflow import (
        BuildingAirflowControlInputs,
        MechanicalVentilationInput,
        make_empty_airflow_control_inputs,
    )

    if airflow_control_inputs is None:
        airflow_control_inputs = make_empty_airflow_control_inputs()

    if not isinstance(airflow_control_inputs, BuildingAirflowControlInputs):
        raise TypeError(
            "airflow_control_inputs must be BuildingAirflowControlInputs."
        )

    mechanical_ventilation_by_zone = dict(
        getattr(
            airflow_control_inputs,
            "mechanical_ventilation_by_zone",
            {},
        )
    )

    for zone_id in zone_ids:
        command = zone_control_commands.get(zone_id)

        flow_m3_h = 0.0

        if command is not None:
            flow_m3_h = float(
                _get_attr_or_key(
                    command,
                    "ventilation_flow_m3_h",
                    0.0,
                )
            )

        mechanical_ventilation_by_zone[zone_id] = MechanicalVentilationInput(
            zone_id=zone_id,
            ventilation_flow_m3_h=flow_m3_h,
            source="ZoneControlCommand.ventilation_flow_m3_h",
        )

    return airflow_control_inputs.copy(
        mechanical_ventilation_by_zone=mechanical_ventilation_by_zone,
    )

def _add_hvac_command_gains_to_thermal_gains(
    zone_ids: List[str],
    base_thermal_gains: Any,
    zone_control_commands: Dict[str, Any],
    zone_system_specs: Dict[str, Any],
) -> Any:
    """
    Add HVAC gains from final sanitized ZoneControlCommand objects.

    This keeps HVAC separate from appliance/internal gains.

    Sign convention:
        heating = positive sensible gain
        cooling = negative sensible gain
    """

    from nexusep.abbey.building.systems import (
        hvac_thermal_gain_w_from_zone_control_command,
    )

    from nexusep.abbey.building.physics.thermal import (
        make_building_thermal_gains,
    )

    hvac_gains_by_zone_w = {}

    for zone_id in zone_ids:
        command = zone_control_commands.get(zone_id)
        system_spec = zone_system_specs.get(zone_id)

        hvac_gains_by_zone_w[zone_id] = (
            hvac_thermal_gain_w_from_zone_control_command(
                command=command,
                system_spec=system_spec,
            )
        )

    hvac_only_gains = make_building_thermal_gains(
        zone_ids=zone_ids,
        hvac_gains_by_zone_w=hvac_gains_by_zone_w,
    )

    if base_thermal_gains is None:
        return hvac_only_gains

    combined_gains = copy.deepcopy(base_thermal_gains)

    for zone_id in zone_ids:
        hvac_zone_gains = hvac_only_gains.get_zone_gains(zone_id)

        if not hvac_zone_gains.sources:
            continue

        combined_zone_gains = combined_gains.get_zone_gains(zone_id)

        for source in hvac_zone_gains.sources:
            combined_zone_gains.add_source(source)

        combined_gains.set_zone_gains(zone_id, combined_zone_gains)

    return combined_gains