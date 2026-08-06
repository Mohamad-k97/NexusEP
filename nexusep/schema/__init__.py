"""Canonical scenario contracts and backend-independent compilation."""

from nexusep.schema.compiler import (
    EXTERIOR_NODE_ID,
    CanonicalClock,
    CanonicalContractError,
    CanonicalIDRegistry,
    compile_physics_graph,
    serialize_compiled_graph,
    validate_compiled_graph,
)
from nexusep.schema.scenario import CanonicalScenario, ScenarioV1
from nexusep.schema.timestep import (
    ActionEvent,
    CanonicalGraphReference,
    CanonicalStepContractError,
    DerivedStepValues,
    DeterministicRunContext,
    InternalGain,
    OccupantStepState,
    PriorZonePhysicalState,
    SimulationStepInput,
    SystemAvailability,
    ZoneControlCommand,
    validate_step_input_for_scenario,
)

__all__ = [
    "EXTERIOR_NODE_ID",
    "ActionEvent",
    "CanonicalClock",
    "CanonicalContractError",
    "CanonicalGraphReference",
    "CanonicalIDRegistry",
    "CanonicalScenario",
    "CanonicalStepContractError",
    "DerivedStepValues",
    "DeterministicRunContext",
    "InternalGain",
    "OccupantStepState",
    "PriorZonePhysicalState",
    "ScenarioV1",
    "SimulationStepInput",
    "SystemAvailability",
    "ZoneControlCommand",
    "compile_physics_graph",
    "serialize_compiled_graph",
    "validate_compiled_graph",
    "validate_step_input_for_scenario",
]
