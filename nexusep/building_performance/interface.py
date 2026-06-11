"""
Building-performance interface for NexusEP / ABBEY coupling.

ABBEY sends controls/actions.
Building-performance module returns DwellingObservation.
"""

from dataclasses import dataclass
from typing import Any, Dict, Protocol

from nexusep.abbey.agents.states import (
    SystemState,
    ExecutionState,
    DwellingObservation,
    SimulationClock,
)


@dataclass 
class PerformanceInput:
    """
    Data sent from ABBEY to the building-performance module.
    """

    systems: SystemState
    execution: ExecutionState
    clock: SimulationClock
    chunk_records: list[dict[str, Any]]
    person_is_home: bool = True
    person_current_zone_id: str = "main_room"
    def to_dict(self) -> Dict[str, Any]:
        return {
            "systems": self.systems.to_dict(),
            "execution": self.execution.to_dict(),
            "clock": self.clock.to_dict(),
            "chunk_records": self.chunk_records,
            "person_is_home": self.person_is_home,
        }

@dataclass 
class PerformanceOutput:
    """
    Data returned from building-performance module to ABBEY.
    """

    observation: DwellingObservation
    performance_log: Dict[str, Any]


class BuildingPerformanceModel(Protocol):
    def step(
        self,
        previous_observation: DwellingObservation,
        performance_input: PerformanceInput,
    ) -> PerformanceOutput:
        ...