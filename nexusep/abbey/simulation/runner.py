"""
ABBEY simulation runner.
"""

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Union

from nexusep.abbey.agents.decision import choose_action
from nexusep.abbey.agents.health import update_health
from nexusep.abbey.agents.idle_movement import update_idle_location
from nexusep.abbey.agents.location import OccupantLocation, SpaceAssignment
from nexusep.abbey.agents.needs import update_needs
from nexusep.abbey.agents.perception import update_perception
from nexusep.abbey.agents.states import (
    PersonState,
    DwellingObservation,
    SystemState,
    ActionState,
    ExecutionState,
    SimulationClock,
)
from nexusep.abbey.simulation.execution import execute_timestep
from nexusep.abbey.simulation.logger import SimulationLogger
from nexusep.abbey.utils import load_jsonc
from nexusep.building_performance import (
    DummyBuildingPerformanceModel,
    PerformanceInput,
    BuildingPerformanceModel,
)
from nexusep.abbey.agents.sleep_state import update_sleep_episode_timers

AbbeyConfig = Mapping[str, Any]


@dataclass
class AbbeySimulation:
    config: AbbeyConfig

    person: PersonState
    location: OccupantLocation
    assignment: SpaceAssignment

    observation: DwellingObservation
    systems: SystemState
    execution: ExecutionState
    clock: SimulationClock

    performance_model: BuildingPerformanceModel
    logger: SimulationLogger

    n_steps: int
    rng: random.Random

    @classmethod
    def initialize(
        cls,
        config_path: Union[str, Path],
        duration_hours: float = 24.0,
        dt_minutes: float = 15.0,
        person: Optional[PersonState] = None,
        location: Optional[OccupantLocation] = None,
        assignment: Optional[SpaceAssignment] = None,
        observation: Optional[DwellingObservation] = None,
        systems: Optional[SystemState] = None,
        execution: Optional[ExecutionState] = None,
        performance_model: Optional[BuildingPerformanceModel] = None,
        random_seed: int = 42,
    ) -> "AbbeySimulation":
        config = load_jsonc(config_path)

        person = person or PersonState()
        observation = observation or DwellingObservation()

        default_space_id = observation.default_zone_id

        location = location or OccupantLocation(
            occupant_id=person.occupant_id,
            dwelling_id="dwelling_1",
            is_home=person.is_home,
            current_space_id=default_space_id,
            current_space_role="idle",
            away_reason=getattr(person, "away_reason", "none"),
        )

        assignment = assignment or SpaceAssignment(
            occupant_id=person.occupant_id,
            dwelling_id=location.dwelling_id,
            default_space_id=default_space_id,
            role_to_space_id={
                "idle": default_space_id,
                "sleep": default_space_id,
                "work": default_space_id,
                "kitchen": default_space_id,
                "bathroom": default_space_id,
                "laundry": default_space_id,
                "entrance": default_space_id,
            },
        )

        dt_hours = dt_minutes / 60.0
        n_steps = int(round(duration_hours / dt_hours))

        return cls(
            config=config,
            person=person,
            location=location,
            assignment=assignment,
            observation=observation,
            systems=systems or SystemState(),
            execution=execution or ExecutionState(),
            clock=SimulationClock(dt_hours=dt_hours),
            performance_model=performance_model or DummyBuildingPerformanceModel(),
            logger=SimulationLogger(),
            n_steps=n_steps,
            rng=random.Random(random_seed),
        )

    def step(self) -> None:
        """
        Run one ABBEY timestep.
        """

        # Keep legacy PersonState home/away fields synchronized for v0.1.
        self._sync_person_from_location()
        self.person = update_sleep_episode_timers(
            person=self.person,
            clock=self.clock,
        )
        # 1. Update slow health state
        self.person = update_health(
            person=self.person,
            clock=self.clock,
            config=self.config,
        )

        # 2. Convert current room/building observation into perception
        self.person = update_perception(
            person=self.person,
            observation=self.observation,
            systems=self.systems,
            location=self.location,
            clock=self.clock,
            config=self.config,
        )

        # 3. Execute purposeful decisions/actions within the timestep
        (
            self.person,
            self.location,
            self.systems,
            self.execution,
            chunk_records,
        ) = execute_timestep(
            person=self.person,
            location=self.location,
            assignment=self.assignment,
            observation=self.observation,
            systems=self.systems,
            execution=self.execution,
            clock=self.clock,
            config=self.config,
            choose_action=choose_action,
            actor_id=self.person.occupant_id,
        )

        # Keep person mirrored after purposeful actions.
        self._sync_person_from_location()

        # 4. Ambient/idle Markov movement
        self.location = update_idle_location(
            person=self.person,
            location=self.location,
            assignment=self.assignment,
            execution=self.execution,
            available_space_ids=self.observation.available_space_ids(),
            clock=self.clock,
            config=self.config,
            rng=self.rng,
        )

        self._sync_person_from_location()

        # 5. Update internal needs based on representative executed action
        representative_action = self._representative_action_from_chunks(chunk_records)
        
        if (
            not self.location.is_home
            and self.location.away_reason == "work"
        ):
            representative_action = ActionState(
                name="work",
                category="external_activity",
                execution_type="external",
                remaining_minutes=self.clock.dt_hours * 60.0,
                power_w=0.0,
                activity_intensity=0.35,
                effort=0.35,
                requires_home=False,
                requires_awake=True,
                blocks_actor=False,
                background_process=False,
                can_continue_without_actor=True,
                can_be_interrupted=False,
            )
        self.person = update_needs(
            person=self.person,
            observation=self.observation,
            action=representative_action,
            clock=self.clock,
            config=self.config,
        )

        # 6. Send controls/actions/location to building-performance model
        performance_input = PerformanceInput(
            systems=self.systems,
            execution=self.execution,
            clock=self.clock,
            chunk_records=chunk_records,
            person_is_home=self.location.is_home,
            person_current_zone_id=self.location.current_space_id,
        )

        performance_output = self.performance_model.step(
            previous_observation=self.observation,
            performance_input=performance_input,
        )

        self.observation = performance_output.observation

        # 7. Log timestep
        self.logger.record_step(
            clock=self.clock,
            person=self.person,
            location=self.location,
            assignment=self.assignment,
            observation=self.observation,
            systems=self.systems,
            execution=self.execution,
            chunk_records=chunk_records,
            performance_log=performance_output.performance_log,
        )

        # 8. Advance clock
        self.clock = self.clock.advance()

    def run(self):
        """
        Run the full simulation and return a dataframe.
        """

        for _ in range(self.n_steps):
            self.step()

        return self.logger.to_dataframe()

    def save_csv(self, path: Union[str, Path]) -> None:
        self.logger.save_csv(path)
        
    def save_zone_csvs(self, folder: Union[str, Path]) -> None:
        self.logger.save_zone_csvs(folder)

    def _sync_person_from_location(self) -> None:
        """
        Temporary v0.1 compatibility layer.

        Location is the proper spatial state.
        PersonState still has is_home/away_reason because older modules use them.
        """

        updates = {}

        if hasattr(self.person, "is_home"):
            updates["is_home"] = self.location.is_home

        if hasattr(self.person, "away_reason"):
            updates["away_reason"] = self.location.away_reason

        if updates:
            self.person = self.person.copy(**updates)

    def _representative_action_from_chunks(
        self,
        chunk_records: list[dict[str, Any]],
    ) -> ActionState:
        """
        Temporary v0.1 bridge.

        Needs currently accept one ActionState.
        Since execution can contain several chunks/actions, we select
        the most behaviorally relevant action in the timestep.
        """

        action_minutes: dict[str, float] = {}

        for chunk in chunk_records:
            for row in chunk.get("power_breakdown", []):
                name = str(row["name"])
                minutes = float(row["minutes"])
                action_minutes[name] = action_minutes.get(name, 0.0) + minutes

        if not action_minutes:
            return ActionState(name="do_nothing")

        priority = [
            "sleep",
            "cook",
            "emergency_eat",
            "run_washing_machine",
            "shower",
            "make_hot_drink",
            "use_laptop",
            "do_nothing",
        ]

        for name in priority:
            if name in action_minutes:
                return self._action_state_from_config(name)

        dominant_name = max(action_minutes, key=action_minutes.get)
        return self._action_state_from_config(dominant_name)

    def _action_state_from_config(self, name: str) -> ActionState:
        cfg = self.config["actions"][name]

        return ActionState(
            name=name,
            category=str(cfg["category"]),
            execution_type=str(cfg["execution_type"]),
            remaining_minutes=float(cfg["duration_minutes"]),
            power_w=float(cfg["power_w"]),
            activity_intensity=float(cfg["activity_intensity"]),
            effort=float(cfg["effort"]),
            requires_home=bool(cfg["requires_home"]),
            requires_awake=bool(cfg["requires_awake"]),
            blocks_actor=bool(cfg["blocks_actor"]),
            background_process=bool(cfg["background_process"]),
            can_continue_without_actor=bool(cfg["can_continue_without_actor"]),
            can_be_interrupted=bool(cfg["can_be_interrupted"]),
            can_fill_remaining_time=bool(cfg.get("can_fill_remaining_time", False)),
            can_repeat=bool(cfg.get("can_repeat", False)),
            target_zone_role=str(cfg.get("target_zone_role", "current")),
            system_effects=dict(cfg.get("system_effects", {})),
            person_effects=dict(cfg.get("person_effects", {})),
            action_cooldowns_on_start=dict(cfg.get("action_cooldowns_on_start", {})),
        )