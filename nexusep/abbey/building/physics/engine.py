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

    thermal_state: Any = None
    thermal_parameters: Any = None
    thermal_ventilation_exchange: Any = None
    thermal_step_result: Any = None

    proposed_zone_states: Dict[str, Any] = field(default_factory=dict)

    zone_records: List[Dict[str, Any]] = field(default_factory=list)
    building_record: Dict[str, Any] = field(default_factory=dict)

    source: str = "physics.engine.Phase10.2"

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
            "has_thermal_state": self.thermal_state is not None,
            "has_thermal_parameters": self.thermal_parameters is not None,
            "has_thermal_ventilation_exchange": self.thermal_ventilation_exchange is not None,
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

    This is the new central function.

    It does not yet remove SimpleBuildingPerformanceModel.
    That happens in Phase 10.3.

    Current behavior:
    - reads BuildingModel / ZoneState
    - reads WeatherState
    - reads ZoneControlCommand / ZoneSystemSpec
    - resolves shared window boundary result if graph exists
    - calculates daylight and lighting if graph exists
    - builds internal sources
    - builds airflow network if graph exists
    - updates CO2 if airflow exists
    - updates moisture if airflow exists
    - updates thermal state
    - proposes updated ZoneState objects
    - optionally writes proposed ZoneState objects back to BuildingModel
    """

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

            zone_system_specs[zone_id] = make_default_zone_system_spec_from_zone_model(
                zone_model
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
    window_operation_inputs = None
    window_boundary_result = step_input.window_boundary_result

    if physics_graph is not None:
        window_operation_inputs = _make_window_operation_inputs_from_zone_commands(
            physics_graph=physics_graph,
            zone_control_commands=zone_control_commands,
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
    daylight_result = None
    lighting_control_inputs = _make_lighting_control_inputs_from_zone_commands(
        building_model=building_model,
        zone_control_commands=zone_control_commands,
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

    from nexusep.abbey.building.physics.internal_sources import (
        make_physics_inputs_from_internal_sources,
    )

    physics_inputs = make_physics_inputs_from_internal_sources(
        internal_source_result=internal_source_result,
        zone_ids=zone_ids,
        solar_gains_by_zone_w=solar_gains_by_zone_w,
    )

    airflow_control_inputs = physics_inputs.get("airflow_control_inputs", None)
    co2_generation_result = physics_inputs.get("co2_generation_result", None)
    moisture_source_inputs = physics_inputs.get("moisture_source_inputs", None)
    thermal_gains = physics_inputs.get("thermal_gains", None)
    airflow_control_inputs = _add_ventilation_commands_to_airflow_control_inputs(
        airflow_control_inputs=airflow_control_inputs,
        zone_ids=zone_ids,
        zone_control_commands=zone_control_commands,
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

        outdoor_moisture_boundary = make_outdoor_moisture_boundary_from_weather_state(
            weather_state=weather_state,
        )

        moisture_transport_result = make_building_moisture_transport_result(
            moisture_state=moisture_state,
            airflow_network=airflow_network,
            outdoor_moisture_boundary=outdoor_moisture_boundary,
        )

        pressure_pa = _get_attr_or_key(
            weather_state,
            "atmospheric_pressure_pa",
            101325.0,
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
    # Thermal.
    # ------------------------------------------------------------
    from nexusep.abbey.building.physics.thermal import (
        make_building_thermal_parameters,
        make_ventilation_heat_exchange_for_thermal,
        step_building_thermal_state_semi_implicit,
    )

    thermal_parameters = make_building_thermal_parameters(
        building_model=building_model,
    )

    thermal_ventilation_exchange = make_ventilation_heat_exchange_for_thermal(
        building_model=building_model,
        airflow_network=airflow_network,
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
        interzone_network=None,
        ventilation_exchange=thermal_ventilation_exchange,
        additional_outside_conductance_by_zone_w_k=additional_outside_conductance_by_zone_w_k,
        dt_minutes=dt_minutes,
    )

    # ------------------------------------------------------------
    # Proposed ZoneState write-back.
    # ------------------------------------------------------------
    proposed_zone_states = _make_proposed_zone_states(
        building_model=building_model,
        thermal_step_result=thermal_step_result,
        co2_step_result=co2_step_result,
        light_state=light_state,
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
        zone_control_commands=zone_control_commands,
        zone_system_specs=zone_system_specs,
    )
    building_record = _make_engine_building_record(
        zone_records=zone_records,
        internal_source_result=internal_source_result,
        solar_gain_result=solar_gain_result,
        airflow_network=airflow_network,
        co2_step_result=co2_step_result,
        moisture_step_result=moisture_step_result,
        thermal_step_result=thermal_step_result,
        command_constraint_records=command_constraint_records,
    )

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
        thermal_step_result=thermal_step_result,
        proposed_zone_states=proposed_zone_states,
        zone_records=zone_records,
        building_record=building_record,
    )


# ============================================================
# PHASE 10.2 HELPERS
# ============================================================

def _get_attr_or_key(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(key, default)

    return getattr(obj, key, default)


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

    pressure_pa = _get_attr_or_key(
        weather_state,
        "atmospheric_pressure_pa",
        101325.0,
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
    light_state: Any = None,
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

        proposed[zone_id] = old_zone_state.copy(
            indoor_temp_c=new_temp_c,
            indoor_mass_temp_c=new_mass_temp_c,
            co2_ppm=new_co2_ppm,
            indoor_daylight=new_indoor_daylight,
        )

    return proposed


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
    zone_control_commands: Optional[Dict[str, Any]] = None,
    zone_system_specs: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    
    records = []
    zone_control_commands = zone_control_commands or {}
    zone_system_specs = zone_system_specs or {}
    internal_bridge_by_zone = {}

    if internal_source_result is not None and hasattr(
        internal_source_result,
        "physics_bridge_inputs_by_zone",
    ):
        internal_bridge_by_zone = internal_source_result.physics_bridge_inputs_by_zone()

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
            "new_indoor_daylight": _get_attr_or_key(zone_state, "indoor_daylight", None),
            "command_heating_on": bool(_get_attr_or_key(command, "heating_on", False)),
            "command_heating_power_fraction": float(
                _get_attr_or_key(command, "heating_power_fraction", 0.0)
            ),
            "command_heating_power_w": heating_power_w,
            "command_heating_delivered_power_w": heating_power_w,
            
            "command_cooling_on": bool(_get_attr_or_key(command, "cooling_on", False)),
            "command_cooling_power_fraction": float(
                _get_attr_or_key(command, "cooling_power_fraction", 0.0)
            ),
            "command_cooling_power_w": cooling_power_w,
            "command_cooling_delivered_power_w": cooling_power_w,
            "command_hvac_thermal_gain_w": heating_power_w - cooling_power_w,
            "command_heating_delivered_energy_wh": heating_power_w * dt_hours,
            "command_cooling_delivered_energy_wh": cooling_power_w * dt_hours,
            "command_ventilation_flow_m3_h": float(
                _get_attr_or_key(command, "ventilation_flow_m3_h", 0.0)
            ),
            "airflow_infiltration_flow_m3_h": infiltration_flow_m3_h,
            "airflow_mechanical_ventilation_flow_m3_h": mechanical_ventilation_flow_m3_h,
            "airflow_window_flow_m3_h": window_airflow_m3_h,
            "airflow_outdoor_exchange_m3_h": outdoor_exchange_m3_h,
            "airflow_interzone_exchange_m3_h": interzone_exchange_m3_h,
            "airflow_total_exchange_m3_h": total_air_exchange_m3_h,
            "thermal_ventilation_h_w_k": thermal_ventilation_h_w_k,
            "command_lights_on": bool(_get_attr_or_key(command, "lights_on", False)),
            "command_lighting_power_w": float(
                _get_attr_or_key(command, "lighting_power_w", 0.0)
            ),
            "command_window_open": bool(_get_attr_or_key(command, "window_open", False)),
            "command_window_opening_fraction": float(
                _get_attr_or_key(command, "window_opening_fraction", 0.0)
            ),
            "command_curtain_open": bool(_get_attr_or_key(command, "curtain_open", True)),
            "internal_average_sensible_heat_w": bridge_row.get(
                "average_sensible_heat_w",
                0.0,
            ),
            "internal_average_co2_generation_m3_h": bridge_row.get(
                "average_co2_generation_m3_h",
                0.0,
            ),
            "internal_average_moisture_generation_kg_h": bridge_row.get(
                "average_moisture_generation_kg_h",
                0.0,
            ),
            "internal_electricity_wh": bridge_row.get(
                "electricity_wh",
                0.0,
            ),
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
    command_constraint_records: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if command_constraint_records is None:
        command_constraint_records = []

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