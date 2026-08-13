"""
ABBEY simulation runner.
"""

import copy
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union
from types import SimpleNamespace
from nexusep.abbey.household import HouseholdState, update_household_dirty_clothes
from nexusep.abbey.agents.decision import choose_action
from nexusep.abbey.agents.health import update_health
from nexusep.abbey.agents.idle_movement import update_idle_location
from nexusep.abbey.agents.location import (
    OccupantLocation,
    SpaceAssignment,
    make_simple_space_id,
)
from nexusep.abbey.agents.needs import update_needs
from nexusep.abbey.agents.perception import update_perception
from nexusep.abbey.agents.sleep_state import update_sleep_episode_timers
from nexusep.abbey.agents.states import (
    PersonState,
    DwellingObservation,
    SystemState,
    ActionState,
    ExecutionState,
    SimulationClock,
)
from nexusep.abbey.systems import CooldownState
from nexusep.abbey.simulation.execution import execute_timestep, execute_household_timestep
from nexusep.abbey.simulation.logger import SimulationLogger
from nexusep.abbey.utils import load_jsonc

from nexusep.building_performance import (
    DummyBuildingPerformanceModel,
    PerformanceInput,
    BuildingPerformanceModel,
)

from nexusep.abbey.building import (
    BuildingModel,
    BuildingPhysicsPerformanceModel,
    make_default_family_building,
    make_default_family_physics_graph,
    apply_control_action_bridge,
)

from nexusep.abbey.profiling.timers import AbbeyTimer

AbbeyConfig = Mapping[str, Any]


@dataclass
class AbbeySimulation:
    config: AbbeyConfig

    people: Dict[str, PersonState]
    locations: Dict[str, OccupantLocation]
    assignments: Dict[str, SpaceAssignment]
    household: HouseholdState

    observation: DwellingObservation
    systems: SystemState
    execution: ExecutionState
    cooldowns: CooldownState
    clock: SimulationClock

    performance_model: BuildingPerformanceModel
    logger: SimulationLogger

    n_steps: int
    rng: random.Random

    dt_minutes: float = 15.0
    use_household_execution: bool = False

    building_model: Optional[BuildingModel] = None
    building_physics_graph: Optional[Any] = None
    building_performance_model: Optional[BuildingPhysicsPerformanceModel] = None
    use_building_performance: bool = True

    weather_provider: Optional[Any] = None
    weather_state: Optional[Any] = None
    
    building_zone_records: Optional[List[Dict[str, Any]]] = None
    building_dwelling_records: Optional[List[Dict[str, Any]]] = None
    building_records: Optional[List[Dict[str, Any]]] = None
    building_interzone_thermal_records: Optional[List[Dict[str, Any]]] = None
    building_interzone_airflow_records: Optional[List[Dict[str, Any]]] = None
    building_window_airflow_records: Optional[List[Dict[str, Any]]] = None
    building_control_bridge_records: Optional[List[Dict[str, Any]]] = None
    building_action_event_records: Optional[List[Dict[str, Any]]] = None
    
    building_internal_source_records: Optional[List[Dict[str, Any]]] = None
    building_internal_source_zone_records: Optional[List[Dict[str, Any]]] = None
    building_internal_source_building_records: Optional[List[Dict[str, Any]]] = None
    last_internal_source_result: Any = None
    timer: Any = None
    def __post_init__(self) -> None:
        if self.building_zone_records is None:
            self.building_zone_records = []

        if self.building_dwelling_records is None:
            self.building_dwelling_records = []

        if self.building_records is None:
            self.building_records = []

        if self.building_interzone_thermal_records is None:
            self.building_interzone_thermal_records = []
            
        if self.building_control_bridge_records is None:
            self.building_control_bridge_records = []

        if self.building_action_event_records is None:
            self.building_action_event_records = []
            
        if self.building_internal_source_records is None:
            self.building_internal_source_records = []
            
        if self.building_internal_source_records is None:
            self.building_internal_source_records = []

        if self.building_internal_source_zone_records is None:
            self.building_internal_source_zone_records = []

        if self.building_internal_source_building_records is None:
            self.building_internal_source_building_records = []
        if self.building_interzone_airflow_records is None:
            self.building_interzone_airflow_records = []

        if self.building_window_airflow_records is None:
            self.building_window_airflow_records = []
    # ============================================================
    # LEGACY SINGLE-OCCUPANT COMPATIBILITY
    # ============================================================

    @property
    def primary_occupant_id(self) -> str:
        if self.household.occupant_ids:
            return self.household.occupant_ids[0]

        return next(iter(self.people.keys()))

    @property
    def person(self) -> PersonState:
        return self.people[self.primary_occupant_id]

    @person.setter
    def person(self, value: PersonState) -> None:
        self.people[value.occupant_id] = value

    @property
    def location(self) -> OccupantLocation:
        return self.locations[self.primary_occupant_id]

    @location.setter
    def location(self, value: OccupantLocation) -> None:
        self.locations[value.occupant_id] = value

    @property
    def assignment(self) -> SpaceAssignment:
        return self.assignments[self.primary_occupant_id]

    @assignment.setter
    def assignment(self, value: SpaceAssignment) -> None:
        self.assignments[value.occupant_id] = value

    # ============================================================
    # INITIALIZATION
    # ============================================================

    @classmethod
    def initialize(
        cls,
        config_path: Union[str, Path],
        duration_hours: float = 24.0,
        dt_minutes: float = 15.0,

        # New multi-occupant inputs.
        people: Optional[Dict[str, PersonState]] = None,
        locations: Optional[Dict[str, OccupantLocation]] = None,
        assignments: Optional[Dict[str, SpaceAssignment]] = None,
        household: Optional[HouseholdState] = None,

        # Legacy single-occupant inputs.
        person: Optional[PersonState] = None,
        location: Optional[OccupantLocation] = None,
        assignment: Optional[SpaceAssignment] = None,

        observation: Optional[DwellingObservation] = None,
        systems: Optional[SystemState] = None,
        execution: Optional[ExecutionState] = None,
        cooldowns: Optional[CooldownState] = None,
        performance_model: Optional[BuildingPerformanceModel] = None,
        use_household_execution: bool = False,

        building_model: Optional[BuildingModel] = None,
        building_physics_graph: Optional[Any] = None,
        building_performance_model: Optional[BuildingPhysicsPerformanceModel] = None,
        use_building_performance: bool = True,
        weather_provider: Optional[Any] = None,
        weather_state: Optional[Any] = None,
        random_seed: int = 42,
    ) -> "AbbeySimulation":
        config = load_jsonc(config_path)

        default_building_created = False
        if use_building_performance and building_model is None:
            building_model = make_default_family_building()
            default_building_created = True
        if use_building_performance and building_physics_graph is None:
            if not default_building_created:
                raise ValueError(
                    "building_physics_graph is required for a supplied building_model"
                )
            building_physics_graph = make_default_family_physics_graph(
                building_model=building_model,
            )

        observation = observation or DwellingObservation()
        default_space_id = observation.default_zone_id
        default_building_id = ""
        default_dwelling_id = ""
        if building_model is not None:
            default_building_id = building_model.building_id
            dwelling_ids = list(building_model.dwellings)
            if len(dwelling_ids) != 1 and locations is None:
                raise ValueError(
                    "locations with explicit dwelling_id are required for "
                    "multi-dwelling buildings"
                )
            if dwelling_ids:
                default_dwelling_id = dwelling_ids[0]
            zone_ids = list(building_model.all_zone_ids())
            if default_space_id not in zone_ids and zone_ids:
                living_ids = [
                    zone.zone_id
                    for zone in building_model.all_zone_models().values()
                    if zone.zone_use in {"living", "living_room"}
                ]
                default_space_id = sorted(living_ids or zone_ids)[0]

        # ------------------------------------------------------------
        # People
        # ------------------------------------------------------------

        if people is None:
            person = person or PersonState()
            people = {
                person.occupant_id: person,
            }

        # ------------------------------------------------------------
        # Household
        # ------------------------------------------------------------

        if household is None:
            occupant_ids = list(people.keys())
            first_occupant = occupant_ids[0]

            household = HouseholdState(
                household_id=people[first_occupant].household_id,
                occupant_ids=occupant_ids,
                main_cook_id=first_occupant,
                cooking_priority_by_occupant={
                    occupant_id: i + 1
                    for i, occupant_id in enumerate(occupant_ids)
                },
                laundry_priority_by_occupant={
                    occupant_id: i + 1
                    for i, occupant_id in enumerate(occupant_ids)
                },
            )

        # ------------------------------------------------------------
        # Locations
        # ------------------------------------------------------------

        if locations is None:
            locations = {}

            if location is not None:
                locations[location.occupant_id] = location

            for occupant_id, person_i in people.items():
                if occupant_id in locations:
                    continue

                locations[occupant_id] = OccupantLocation(
                    occupant_id=occupant_id,
                    dwelling_id=default_dwelling_id,
                    building_id=default_building_id,
                    is_home=getattr(person_i, "is_home", True),
                    current_space_id=default_space_id,
                    current_space_role="idle",
                    current_activity="idle",
                    away_reason=getattr(person_i, "away_reason", "none"),
                )

        # ------------------------------------------------------------
        # Assignments
        # ------------------------------------------------------------

        if assignments is None:
            assignments = {}

            if assignment is not None:
                assignments[assignment.occupant_id] = assignment

            for occupant_id in people:
                if occupant_id in assignments:
                    continue

                dwelling_id = locations[occupant_id].dwelling_id
                building_id = locations[occupant_id].building_id

                assignments[occupant_id] = SpaceAssignment(
                    occupant_id=occupant_id,
                    dwelling_id=dwelling_id,
                    building_id=building_id,
                    default_space_id=default_space_id,
                    role_to_space_id={
                        "idle": default_space_id,
                        "sleep": default_space_id,
                        "work": default_space_id,
                        "schoolwork": default_space_id,
                        "kitchen": default_space_id,
                        "bathroom": default_space_id,
                        "laundry": default_space_id,
                        "entrance": default_space_id,
                        "care": default_space_id,
                    },
                )

        # ------------------------------------------------------------
        # Time
        # ------------------------------------------------------------

        dt_hours = float(dt_minutes) / 60.0

        if dt_hours <= 0:
            raise ValueError("dt_minutes must be positive.")

        n_steps = int(round(float(duration_hours) / dt_hours))

        # ------------------------------------------------------------
        # Building performance path
        # ------------------------------------------------------------

        if use_building_performance and building_performance_model is None:
            building_performance_model = BuildingPhysicsPerformanceModel(
                building_model=building_model,
                physics_graph=building_physics_graph,
                use_physics_engine=True,
                allow_legacy_physics_fallback=False,
            )

        elif (
            use_building_performance
            and building_performance_model is not None
            and getattr(building_performance_model, "physics_graph", None) is None
        ):
            building_performance_model.physics_graph = building_physics_graph
            
        return cls(
            config=config,
            people=people,
            locations=locations,
            assignments=assignments,
            household=household,
            observation=observation,
            systems=systems or SystemState(),
            execution=execution or ExecutionState(),
            cooldowns=cooldowns or CooldownState(),
            clock=SimulationClock(dt_hours=dt_hours),
            timer=AbbeyTimer(enabled=True),
            performance_model=performance_model or DummyBuildingPerformanceModel(),
            logger=SimulationLogger(),
            use_household_execution=use_household_execution,
            n_steps=n_steps,
            rng=random.Random(random_seed),
            dt_minutes=float(dt_minutes),
            building_model=building_model,
            building_physics_graph=building_physics_graph,
            building_performance_model=building_performance_model,
            use_building_performance=use_building_performance,
            weather_provider=weather_provider,
            weather_state=weather_state,
            building_zone_records=[],
            building_dwelling_records=[],
            building_records=[],
            building_interzone_thermal_records=[],
            building_interzone_airflow_records=[],
            building_window_airflow_records=[],
            building_control_bridge_records=[],
            building_action_event_records=[],
            building_internal_source_records=[],
            building_internal_source_zone_records=[],
            building_internal_source_building_records=[],
            last_internal_source_result=None,
        )

    # ============================================================
    # PEOPLE UPDATES
    # ============================================================

    def _sync_people_from_locations(self) -> None:
        """
        Location is the source of truth for home/away.
        PersonState still keeps is_home/away_reason because older modules use them.
        """

        for occupant_id, person in list(self.people.items()):
            if occupant_id not in self.locations:
                continue

            location = self.locations[occupant_id]

            updates = {}

            if hasattr(person, "is_home"):
                updates["is_home"] = location.is_home

            if hasattr(person, "away_reason"):
                updates["away_reason"] = location.away_reason

            if updates:
                self.people[occupant_id] = person.copy(**updates)

    def _sync_person_from_location(self) -> None:
        """
        Legacy primary-person compatibility.
        """

        updates = {}

        if hasattr(self.person, "is_home"):
            updates["is_home"] = self.location.is_home

        if hasattr(self.person, "away_reason"):
            updates["away_reason"] = self.location.away_reason

        if updates:
            self.person = self.person.copy(**updates)

    def _update_all_people_before_execution(self) -> None:
        """
        Update all people before decision/execution:
        sleep episode memory, health, and perception.
        """

        self._sync_people_from_locations()

        for occupant_id, person in list(self.people.items()):
            location = self.locations[occupant_id]

            person = update_sleep_episode_timers(
                person=person,
                clock=self.clock,
            )

            person = update_health(
                person=person,
                clock=self.clock,
                config=self.config,
            )

            person = update_perception(
                person=person,
                observation=self.observation,
                systems=self.systems,
                location=location,
                clock=self.clock,
                config=self.config,
            )

            self.people[occupant_id] = person

        self._sync_people_from_locations()

    def _update_all_people_after_execution(
        self,
        primary_chunk_records: List[Dict[str, Any]],
    ) -> None:
        """
        Update needs for all occupants.

        For v0.3 skeleton:
          - primary occupant uses actual executed action
          - other occupants use external/idle placeholder action
        """

        self._sync_people_from_locations()

        primary_id = self.primary_occupant_id

        for occupant_id, person in list(self.people.items()):
            location = self.locations[occupant_id]

            if occupant_id == primary_id:
                representative_action = self._representative_action_from_chunks(
                    primary_chunk_records
                )

                if not location.is_home and location.away_reason in ("work", "school"):
                    representative_action = self._external_activity_action_for_person(
                        person=person,
                        location=location,
                    )
            else:
                representative_action = self._external_activity_action_for_person(
                    person=person,
                    location=location,
                )

            person = update_needs(
                person=person,
                observation=self.observation,
                action=representative_action,
                clock=self.clock,
                config=self.config,
            )

            self.people[occupant_id] = person

        self._sync_people_from_locations()

    # ============================================================
    # EXTERNAL ACTIVITY
    # ============================================================

    def _external_activity_action_for_person(
        self,
        person: PersonState,
        location: OccupantLocation,
    ) -> ActionState:
        """
        Convert outside semantic activity into an ActionState for needs dynamics.
        """

        if not location.is_home and location.away_reason == "work":
            return ActionState(
                name="work",
                category="external_activity",
                execution_type="external",
                actor_id=person.occupant_id,
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

        if not location.is_home and location.away_reason == "school":
            return ActionState(
                name="school",
                category="external_activity",
                execution_type="external",
                actor_id=person.occupant_id,
                remaining_minutes=self.clock.dt_hours * 60.0,
                power_w=0.0,
                activity_intensity=0.30,
                effort=0.30,
                requires_home=False,
                requires_awake=True,
                blocks_actor=False,
                background_process=False,
                can_continue_without_actor=True,
                can_be_interrupted=False,
            )

        if not location.is_home:
            return ActionState(
                name="away",
                category="external_activity",
                execution_type="external",
                actor_id=person.occupant_id,
                remaining_minutes=self.clock.dt_hours * 60.0,
                power_w=0.0,
                activity_intensity=0.15,
                effort=0.10,
                requires_home=False,
                requires_awake=True,
                blocks_actor=False,
                background_process=False,
                can_continue_without_actor=True,
                can_be_interrupted=False,
            )

        return ActionState(
            name="do_nothing",
            category="passive",
            execution_type="passive",
            actor_id=person.occupant_id,
            remaining_minutes=self.clock.dt_hours * 60.0,
            power_w=0.0,
            activity_intensity=0.0,
            effort=0.0,
            requires_home=False,
            requires_awake=False,
            blocks_actor=False,
            background_process=False,
            can_continue_without_actor=True,
            can_be_interrupted=True,
        )

    # ============================================================
    # BUILDING PERFORMANCE INTEGRATION
    # ============================================================

    def _locations_for_building_performance(self) -> Dict[str, OccupantLocation]:
        """
        Convert old simple space IDs to dwelling-aware zone IDs for the building model.
        """

        if self.building_model is None:
            return self.locations

        all_zone_ids = set(self.building_model.all_zone_ids())

        out = {}

        for occupant_id, location in self.locations.items():
            new_location = copy.deepcopy(location)
            current_space_id = getattr(new_location, "current_space_id", None)

            if current_space_id not in all_zone_ids:
                assignment = self.assignments.get(occupant_id)
                mapped_space_id = current_space_id
                if assignment is not None:
                    mapped_space_id = assignment.resolve(
                        role=getattr(new_location, "current_space_role", "idle"),
                        available_space_ids=all_zone_ids,
                    )

                if mapped_space_id in all_zone_ids:
                    new_location = new_location.copy(
                        current_space_id=mapped_space_id,
                    )

            out[occupant_id] = new_location

        return out
    def _current_weather_state_for_building_performance(self) -> Any:
        """
        Return the current WeatherState if an explicit weather source exists.

        Priority:
            1. weather_provider.get_state_by_step(clock.step)
            2. static self.weather_state
            3. None, letting BuildingPhysicsPerformanceModel create its
               labelled fallback weather from observation/defaults.
        """

        if self.weather_provider is not None:
            step = getattr(self.clock, "step", 0)

            if hasattr(self.weather_provider, "get_state_by_step"):
                return self.weather_provider.get_state_by_step(step)

            if hasattr(self.weather_provider, "get_state"):
                return self.weather_provider.get_state(step)

            raise TypeError(
                "weather_provider must expose get_state_by_step(step) "
                "or get_state(step)."
            )

        if self.weather_state is not None:
            return self.weather_state

        return None
    def _run_building_performance_if_enabled(
        self,
        chunk_records: Optional[List[Dict[str, Any]]] = None,
        action_energy_wh: Optional[Any] = None,
    ) -> None:
        """
        Run the new dwelling/building performance model if enabled.

        This keeps the old dummy performance as fallback.
        """

        if not self.use_building_performance:
            return

        if self.building_model is None:
            self.building_model = make_default_family_building()

        if self.building_physics_graph is None:
            self.building_physics_graph = make_default_family_physics_graph(
                building_model=self.building_model,
            )

        if self.building_performance_model is None:
            self.building_performance_model = BuildingPhysicsPerformanceModel(
                building_model=self.building_model,
                physics_graph=self.building_physics_graph,
                use_physics_engine=True,
                allow_legacy_physics_fallback=False,
            )

        elif getattr(self.building_performance_model, "physics_graph", None) is None:
            self.building_performance_model.physics_graph = self.building_physics_graph

        building_locations = self._locations_for_building_performance()
        role_to_zone_id = {
            zone_id: zone_id for zone_id in self.building_model.all_zone_ids()
        }
        for assignment in self.assignments.values():
            role_to_zone_id.update(
                {
                    role: zone_id
                    for role, zone_id in assignment.role_to_space_id.items()
                    if zone_id in role_to_zone_id
                }
            )
        action_events = self._get_current_action_events_for_building_bridge(
            chunk_records=chunk_records,
        )

        self._store_building_action_events(action_events)

        bridge_records = apply_control_action_bridge(
            building_model=self.building_model,
            locations=building_locations,
            action_records=action_events,
        )

        self._store_building_bridge_records(bridge_records)
        weather_state = self._current_weather_state_for_building_performance()
        performance_input = {
            "step": getattr(self.clock, "step", None),
            "day": getattr(self.clock, "day", None),
            "hour": getattr(self.clock, "hour", None),
            "observation": self.observation,
            "weather_state": weather_state,
            "locations": building_locations,
            "people": self.people,
            "chunk_records": chunk_records or [],
            "action_energy_wh": action_energy_wh or {},
            "role_to_zone_id": role_to_zone_id,
            "physics_graph": self.building_physics_graph,
            "timer": getattr(self, "timer", None),
        }

        result = self.building_performance_model.step(
            performance_input=performance_input,
            dt_minutes=self.dt_minutes,
        )

        self.observation = result.observation
        self._sync_systems_from_observation()
        self.building_zone_records.extend(result.zone_records)
        self.building_dwelling_records.extend(result.dwelling_records)
        self._store_building_interzone_thermal_records(
            getattr(
                result,
                "interzone_thermal_flow_records",
                [],
            )
        )
        self._store_building_interzone_airflow_records(
            getattr(
                result,
                "interzone_airflow_records",
                [],
            )
        )

        self._store_building_window_airflow_records(
            getattr(
                result,
                "window_airflow_records",
                [],
            )
        )
        self.last_internal_source_result = getattr(
            result,
            "internal_source_result",
            None,
        )

        self._store_building_internal_source_outputs(
            internal_source_result=self.last_internal_source_result,
        )
        if result.building_record:
            self.building_records.append(result.building_record)

    def _store_building_interzone_thermal_records(
        self,
        records: Optional[List[Dict[str, Any]]],
    ) -> None:
        if records is None:
            return

        for record in records:
            if hasattr(record, "to_dict"):
                row = record.to_dict()
            else:
                row = dict(record)

            self.building_interzone_thermal_records.append(
                self._standardize_interzone_thermal_row(row)
            )

    def _store_building_interzone_airflow_records(
        self,
        records: Optional[List[Dict[str, Any]]],
    ) -> None:
        if records is None:
            return

        for record in records:
            if hasattr(record, "to_dict"):
                row = record.to_dict()
            else:
                row = dict(record)

            self.building_interzone_airflow_records.append(
                self._standardize_interzone_airflow_row(row)
            )

    def _store_building_window_airflow_records(
        self,
        records: Optional[List[Dict[str, Any]]],
    ) -> None:
        if records is None:
            return

        for record in records:
            if hasattr(record, "to_dict"):
                row = record.to_dict()
            else:
                row = dict(record)

            self.building_window_airflow_records.append(
                self._csv_safe_internal_source_row(row)
            )
            
    def _store_building_action_events(
        self,
        action_events: List[Dict[str, Any]],
    ) -> None:
        for event in action_events:
            row = dict(event)
            row["step"] = getattr(self.clock, "step", None)
            row["day"] = getattr(self.clock, "day", None)
            row["hour"] = getattr(self.clock, "hour", None)
            self.building_action_event_records.append(row)

    def _store_building_internal_source_records(
        self,
        internal_source_result: Any,
    ) -> None:
        if internal_source_result is None:
            return

        if not hasattr(internal_source_result, "records"):
            return

        for record in internal_source_result.records:
            if hasattr(record, "to_dict"):
                row = record.to_dict()
            else:
                row = dict(record)

            row["step"] = getattr(self.clock, "step", None)
            row["day"] = getattr(self.clock, "day", None)
            row["hour"] = getattr(self.clock, "hour", None)

            self.building_internal_source_records.append(row)
    def _store_building_bridge_records(
        self,
        bridge_records: List[Dict[str, Any]],
    ) -> None:
        for record in bridge_records:
            row = dict(record)
            row["step"] = getattr(self.clock, "step", None)
            row["day"] = getattr(self.clock, "day", None)
            row["hour"] = getattr(self.clock, "hour", None)
            self.building_control_bridge_records.append(row)

    def _internal_source_time_record(self) -> Dict[str, Any]:
        day = getattr(self.clock, "day", None)
        hour = getattr(self.clock, "hour", None)

        time_hour = None

        if day is not None and hour is not None:
            time_hour = float(day) * 24.0 + float(hour)

        return {
            "step": getattr(self.clock, "step", None),
            "day": day,
            "hour": hour,
            "time_hour": time_hour,
            "dt_hours": getattr(self.clock, "dt_hours", None),
            "dt_minutes": float(getattr(self.clock, "dt_hours", 0.0)) * 60.0,
        }

    @staticmethod
    def _csv_safe_internal_source_row(row: Dict[str, Any]) -> Dict[str, Any]:
        return AbbeySimulation._csv_safe_row(row)

    @staticmethod
    def _standardize_interzone_thermal_row(row: Dict[str, Any]) -> Dict[str, Any]:
        row = dict(row)

        if "connection_id" not in row and "zone_connection_id" in row:
            row["connection_id"] = row.get("zone_connection_id")

        if "zone_connection_id" not in row and "connection_id" in row:
            row["zone_connection_id"] = row.get("connection_id")

        if "open_fraction" not in row and "opening_fraction" in row:
            row["open_fraction"] = row.get("opening_fraction")

        if "opening_fraction" not in row and "open_fraction" in row:
            row["opening_fraction"] = row.get("open_fraction")

        return row

    @staticmethod
    def _standardize_interzone_airflow_row(row: Dict[str, Any]) -> Dict[str, Any]:
        row = dict(row)

        if "connection_id" not in row and "zone_connection_id" in row:
            row["connection_id"] = row.get("zone_connection_id")

        if "zone_connection_id" not in row and "connection_id" in row:
            row["zone_connection_id"] = row.get("connection_id")

        if "airflow_a_to_b_m3_h" not in row and "flow_a_to_b_m3_h" in row:
            row["airflow_a_to_b_m3_h"] = row.get("flow_a_to_b_m3_h")

        if "airflow_b_to_a_m3_h" not in row and "flow_b_to_a_m3_h" in row:
            row["airflow_b_to_a_m3_h"] = row.get("flow_b_to_a_m3_h")

        if "flow_a_to_b_m3_h" not in row and "airflow_a_to_b_m3_h" in row:
            row["flow_a_to_b_m3_h"] = row.get("airflow_a_to_b_m3_h")

        if "flow_b_to_a_m3_h" not in row and "airflow_b_to_a_m3_h" in row:
            row["flow_b_to_a_m3_h"] = row.get("airflow_b_to_a_m3_h")

        if "airflow_a_to_b_m3_s" not in row and "flow_a_to_b_m3_s" in row:
            row["airflow_a_to_b_m3_s"] = row.get("flow_a_to_b_m3_s")

        if "airflow_b_to_a_m3_s" not in row and "flow_b_to_a_m3_s" in row:
            row["airflow_b_to_a_m3_s"] = row.get("flow_b_to_a_m3_s")

        if "mixing_exchange_m3_h" not in row:
            if "mixing_flow_m3_h" in row:
                row["mixing_exchange_m3_h"] = row.get("mixing_flow_m3_h")
            elif "airflow_a_to_b_m3_h" in row and "airflow_b_to_a_m3_h" in row:
                row["mixing_exchange_m3_h"] = max(
                    float(row.get("airflow_a_to_b_m3_h") or 0.0),
                    float(row.get("airflow_b_to_a_m3_h") or 0.0),
                )

        if "mixing_flow_m3_h" not in row and "mixing_exchange_m3_h" in row:
            row["mixing_flow_m3_h"] = row.get("mixing_exchange_m3_h")

        if "open_fraction" not in row and "opening_fraction" in row:
            row["open_fraction"] = row.get("opening_fraction")

        if "opening_fraction" not in row and "open_fraction" in row:
            row["opening_fraction"] = row.get("open_fraction")

        return row
    
    @staticmethod
    def _call_float_method(obj: Any, method_name: str, default: float = 0.0) -> float:
        if obj is None:
            return default

        method = getattr(obj, method_name, None)

        if method is None:
            return default

        try:
            return float(method())
        except Exception:
            return default
    @staticmethod
    def _csv_safe_row(row: Dict[str, Any]) -> Dict[str, Any]:
        clean = {}

        for key, value in dict(row).items():
            if isinstance(value, (dict, list, tuple)):
                clean[key] = json.dumps(
                    value,
                    ensure_ascii=False,
                    default=str,
                )
            else:
                clean[key] = value

        return clean
    def _sync_systems_from_observation(self) -> None:
        """
        Keep agent-facing SystemState consistent with the final
        building-performance observation.

        The building/control path is now the source of truth for actual
        control states after the physics timestep.

        Phase 17.4:
        - sync dwelling-aware zone IDs
        - sync simple aliases such as living_room/kitchen
        - keep legacy scalar controls aligned with observation.default_zone_id
        """

        if self.observation is None:
            return

        zone_observations = getattr(
            self.observation,
            "zone_observations",
            {},
        )

        if not zone_observations:
            return

        default_zone_id = getattr(
            self.observation,
            "default_zone_id",
            None,
        )

        systems = self.systems

        if default_zone_id is not None:
            systems = systems.copy(
                default_space_id=default_zone_id,
            )

        for zone_id, zone in zone_observations.items():
            updates = {
                "heating_on": bool(getattr(zone, "heating_on", False)),
                "cooling_on": bool(getattr(zone, "cooling_on", False)),
                "mechanical_ventilation_on": bool(
                    getattr(zone, "mechanical_ventilation_on", False)
                ),
                "lights_on": bool(getattr(zone, "lights_on", False)),
                "window_open": bool(getattr(zone, "window_open", False)),
            }

            curtain_open = getattr(zone, "curtain_open", None)

            if curtain_open is not None:
                updates["curtain_closed"] = not bool(curtain_open)

            for space_id in self._system_space_aliases_for_observation_zone(
                zone_id=zone_id,
                default_zone_id=default_zone_id,
            ):
                systems = systems.set_space_controls(
                    space_id,
                    **updates,
                )

        self.systems = systems

    def _system_space_aliases_for_observation_zone(
        self,
        zone_id: str,
        default_zone_id: Optional[str] = None,
    ) -> List[str]:
        aliases = []

        def add(value):
            if value is None:
                return

            value = str(value)

            if value and value not in aliases:
                aliases.append(value)

        add(zone_id)

        try:
            simple_id = make_simple_space_id(zone_id)
        except Exception:
            simple_id = None

        add(simple_id)

        if simple_id == "living_room":
            add("main_room")

        if zone_id == default_zone_id:
            add(default_zone_id)

        return aliases
        
    def _store_building_internal_source_outputs(
        self,
        internal_source_result: Any,
    ) -> None:
        if internal_source_result is None:
            return

        if not hasattr(internal_source_result, "records"):
            return

        time_record = self._internal_source_time_record()

        # ------------------------------------------------------------
        # 1. Long source records: one row per physical source.
        # ------------------------------------------------------------
        for source_record in internal_source_result.records:
            if hasattr(source_record, "to_dict"):
                row = source_record.to_dict()
            else:
                row = dict(source_record)

            row.update(time_record)

            self.building_internal_source_records.append(
                self._csv_safe_internal_source_row(row)
            )

        # ------------------------------------------------------------
        # 2. Zone aggregate rows: one row per zone per timestep.
        # ------------------------------------------------------------
        if hasattr(internal_source_result, "aggregate_dict_by_zone"):
            zone_rows = internal_source_result.aggregate_dict_by_zone()

            for zone_id, row in zone_rows.items():
                row = dict(row)
                row["zone_id"] = zone_id
                row.update(time_record)

                self.building_internal_source_zone_records.append(
                    self._csv_safe_internal_source_row(row)
                )

        # ------------------------------------------------------------
        # 3. Building aggregate row: one row per timestep.
        # ------------------------------------------------------------
        building_row = dict(time_record)

        building_row.update(
            {
                "record_count": len(internal_source_result.records),
                "total_electricity_wh": self._call_float_method(
                    internal_source_result,
                    "total_electricity_wh",
                ),
                "total_average_electricity_power_w": self._call_float_method(
                    internal_source_result,
                    "total_average_electricity_power_w",
                ),
                "total_average_sensible_heat_w": self._call_float_method(
                    internal_source_result,
                    "total_average_sensible_heat_w",
                ),
                "total_average_latent_heat_w": self._call_float_method(
                    internal_source_result,
                    "total_average_latent_heat_w",
                ),
                "total_co2_generation_m3_h": self._call_float_method(
                    internal_source_result,
                    "total_co2_generation_m3_h",
                ),
                "total_moisture_generation_kg": self._call_float_method(
                    internal_source_result,
                    "total_moisture_generation_kg",
                ),
                "average_total_moisture_generation_kg_h": self._call_float_method(
                    internal_source_result,
                    "average_total_moisture_generation_kg_h",
                ),
                "total_appliance_electricity_wh": self._call_float_method(
                    internal_source_result,
                    "total_appliance_electricity_wh",
                ),
                "total_lighting_electricity_wh": self._call_float_method(
                    internal_source_result,
                    "total_lighting_electricity_wh",
                ),
                "total_hvac_electricity_wh": self._call_float_method(
                    internal_source_result,
                    "total_hvac_electricity_wh",
                ),
                "total_appliance_sensible_heat_w": self._call_float_method(
                    internal_source_result,
                    "total_appliance_sensible_heat_w",
                ),
                "total_lighting_sensible_heat_w": self._call_float_method(
                    internal_source_result,
                    "total_lighting_sensible_heat_w",
                ),
                "total_hvac_heating_gain_w": self._call_float_method(
                    internal_source_result,
                    "total_hvac_heating_gain_w",
                ),
                "total_hvac_cooling_removal_w": self._call_float_method(
                    internal_source_result,
                    "total_hvac_cooling_removal_w",
                ),
            }
        )

        self.building_internal_source_building_records.append(
            self._csv_safe_internal_source_row(building_row)
        )
        
    def _get_current_action_events_for_building_bridge(
        self,
        chunk_records: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract current-step action events for the building control bridge.

        Expected final event format:
            {"occupant_id": ..., "action_name": ...}
        """

        events = []

        # Main source: execution chunk records returned by execute_timestep /
        # execute_household_timestep.
        for chunk in self._safe_list(chunk_records):
            events.extend(self._extract_action_events_from_any_record(chunk))

        # Fallback: execution object, if active actions are stored there.
        for attr in [
            "foreground_actions",
            "background_actions",
            "active_actions",
            "active_foreground_actions",
            "active_background_actions",
        ]:
            if hasattr(self.execution, attr):
                value = getattr(self.execution, attr)

                for record in self._safe_list(value):
                    events.extend(self._extract_action_events_from_any_record(record))

        return self._deduplicate_action_events(events)

    def _extract_action_events_from_any_record(
        self,
        record: Any,
    ) -> List[Dict[str, Any]]:
        if record is None:
            return []

        if isinstance(record, str):
            out = []

            for parsed in self._parse_action_list(record):
                out.extend(self._extract_action_events_from_any_record(parsed))

            return out

        if isinstance(record, dict):
            events = []

            direct_event = self._extract_single_action_event(record)

            if direct_event is not None:
                events.append(direct_event)

            for key in [
                "power_breakdown",
                "foreground_actions",
                "background_actions",
                "active_actions",
            ]:
                if key in record:
                    for child in self._parse_action_list(record.get(key)):
                        events.extend(self._extract_action_events_from_any_record(child))

            return events

        direct_event = self._extract_single_action_event(record)

        if direct_event is not None:
            return [direct_event]

        return []

    def _extract_single_action_event(
        self,
        record: Any,
    ) -> Optional[Dict[str, str]]:
        action_name = self._get_attr_or_key(record, "action_name", None)

        if action_name is None:
            action_name = self._get_attr_or_key(record, "name", None)

        if action_name is None:
            action_name = self._get_attr_or_key(record, "action", None)

        if action_name is not None and not isinstance(action_name, str):
            nested_name = self._get_attr_or_key(action_name, "name", None)

            if nested_name is not None:
                action_name = nested_name

        occupant_id = self._get_attr_or_key(record, "occupant_id", None)

        if occupant_id is None:
            occupant_id = self._get_attr_or_key(record, "actor_id", None)

        if occupant_id is None:
            occupant_id = self._get_attr_or_key(record, "person_id", None)

        if occupant_id is None:
            occupant_id = self._get_attr_or_key(record, "agent_id", None)

        if action_name is None or occupant_id is None:
            return None

        event = {
            "occupant_id": str(occupant_id),
            "action_name": str(action_name),
        }

        for key in [
            "action_value",
            "value",
            "setpoint_c",
            "temperature_c",
            "target_c",
            "delta_c",
            "amount_c",
        ]:
            value = self._get_attr_or_key(record, key, None)

            if value is not None:
                event[key] = value

        return event

    def _parse_action_list(self, value: Any) -> List[Any]:
        if value is None:
            return []

        if isinstance(value, list):
            return value

        if isinstance(value, tuple):
            return list(value)

        if isinstance(value, dict):
            return [value]

        if isinstance(value, str):
            text = value.strip()

            if not text:
                return []

            try:
                parsed = json.loads(text)
            except Exception:
                return []

            if isinstance(parsed, list):
                return parsed

            if isinstance(parsed, dict):
                return [parsed]

            return []

        return [value]

    def _deduplicate_action_events(
        self,
        events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        out = []
        seen = set()

        for event in events:
            occupant_id = event.get("occupant_id")
            action_name = event.get("action_name")

            key = (occupant_id, action_name)

            if key in seen:
                continue

            seen.add(key)
            clean_event = dict(event)
            clean_event["occupant_id"] = str(occupant_id)
            clean_event["action_name"] = str(action_name)

            out.append(clean_event)

        return out

    # ============================================================
    # HOUSEHOLD INSPECTION / IDLE MOVEMENT
    # ============================================================

    def _household_inspection_config(self) -> Dict[str, Any]:
        return dict(
            self.config.get(
                "household_inspection",
                {},
            )
        )

    def _zone_number_of_people(self, zone: Any) -> float:
        value = getattr(zone, "number_of_people", None)

        if value is not None:
            try:
                return float(value)
            except Exception:
                return 0.0

        people = getattr(zone, "occupied_person_ids", [])

        try:
            return float(len(people))
        except Exception:
            return 0.0

    def _zone_control_risk_score(
        self,
        zone_id: str,
        zone: Any,
    ) -> float:
        """
        Score how much a room deserves a casual household inspection.

        This is not a controller. It only makes unattended problematic rooms
        more likely to be visited by an idle occupant.
        """

        cfg = self._household_inspection_config()

        cold_temp_c = float(cfg.get("cold_temp_c", 18.5))
        hot_temp_c = float(cfg.get("hot_temp_c", 24.5))
        high_co2_ppm = float(cfg.get("high_co2_ppm", 1200.0))
        high_daylight = float(cfg.get("high_daylight", 0.75))

        unoccupied_multiplier = float(
            cfg.get("unoccupied_room_multiplier", 1.25)
        )

        zone_temp_c = getattr(zone, "indoor_temp", None)

        if zone_temp_c is None:
            zone_temp_c = getattr(zone, "indoor_temp_c", None)

        if zone_temp_c is None:
            zone_temp_c = 20.0

        zone_temp_c = float(zone_temp_c)

        co2_ppm = float(getattr(zone, "co2_ppm", 420.0))
        daylight = float(getattr(zone, "indoor_daylight", 0.0))

        controls = self.systems.get_space_controls(zone_id)

        window_open = bool(
            getattr(zone, "window_open", False)
            or getattr(controls, "window_open", False)
        )

        heating_on = bool(
            getattr(zone, "heating_on", False)
            or getattr(controls, "heating_on", False)
        )

        lights_on = bool(
            getattr(zone, "lights_on", False)
            or getattr(controls, "lights_on", False)
        )

        score = 0.0

        # Worst case: heating against an open window.
        if heating_on and window_open:
            score += float(cfg.get("heating_with_open_window_score", 8.0))

        # Window open while the room is cold.
        if window_open and zone_temp_c < cold_temp_c:
            score += float(cfg.get("cold_open_window_score", 6.0))

        # Heating still on in a hot room.
        if heating_on and zone_temp_c > hot_temp_c:
            score += float(cfg.get("hot_heating_on_score", 6.0))

        # Lights on when daylight is already enough.
        if lights_on and daylight > high_daylight:
            score += float(cfg.get("lights_on_bright_room_score", 2.0))

        # Bad air can justify a visit too.
        if co2_ppm > high_co2_ppm:
            score += float(cfg.get("high_co2_score", 2.0))

        if self._zone_number_of_people(zone) <= 0.0:
            score *= unoccupied_multiplier

        return score

    def _maybe_move_person_for_household_inspection(
        self,
        person: PersonState,
        location: OccupantLocation,
        assignment: SpaceAssignment,
    ) -> OccupantLocation:
        """
        Low-probability inspection movement.

        An idle person at home may casually enter a problematic room.
        After this movement, perception is updated in that room and the normal
        decision engine can choose close_window / turn_heating_off / etc.
        """

        cfg = self._household_inspection_config()

        if not bool(cfg.get("enabled", True)):
            return location

        if not bool(getattr(person, "can_act", True)):
            return location

        if not location.is_home:
            return location

        if person.is_sleeping:
            return location

        if self.execution.actor_is_blocked(person.occupant_id):
            return location

        current_activity = str(
            getattr(location, "current_activity", "idle")
        ).strip().lower()

        if current_activity not in {
            "",
            "idle",
            "do_nothing",
            "household_inspection",
        }:
            return location

        minimum_dwell_minutes = float(
            cfg.get("minimum_dwell_minutes", 10.0)
        )

        if location.minutes_since_last_space_change < minimum_dwell_minutes:
            return location

        probability_per_hour = float(
            cfg.get("probability_per_hour", 0.20)
        )

        probability_this_step = probability_per_hour * self.clock.dt_hours

        if self.rng.random() > probability_this_step:
            return location

        threshold = float(
            cfg.get("minimum_room_risk_score", 2.0)
        )

        available_space_ids = set(self.observation.available_space_ids())
        candidates = []

        for zone_id, zone in self.observation.zone_observations.items():
            if zone_id == location.current_space_id:
                continue

            if zone_id not in available_space_ids:
                continue

            score = self._zone_control_risk_score(
                zone_id=zone_id,
                zone=zone,
            )

            if score < threshold:
                continue

            candidates.append(
                (
                    score,
                    zone_id,
                )
            )

        if not candidates:
            return location

        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        target_zone_id = candidates[0][1]

        return location.copy(
            current_space_id=target_zone_id,
            current_space_role="inspection",
            current_activity="household_inspection",
            minutes_since_last_space_change=0.0,
        )

    def _update_all_idle_locations_before_execution(self) -> None:
        """
        Update idle/ambient movement for all occupants before perception.

        Important ordering:
            movement first
            perception second
            decision third

        This lets an occupant enter a room, perceive that it is cold/hot/stale,
        and then act on that room in the same timestep.
        """

        self._sync_people_from_locations()

        available_space_ids = self.observation.available_space_ids()

        for occupant_id, person in list(self.people.items()):
            if occupant_id not in self.locations:
                continue

            if occupant_id not in self.assignments:
                continue

            old_location = self.locations[occupant_id]
            assignment = self.assignments[occupant_id]

            inspected_location = self._maybe_move_person_for_household_inspection(
                person=person,
                location=old_location,
                assignment=assignment,
            )

            if inspected_location.current_space_id != old_location.current_space_id:
                self.locations[occupant_id] = inspected_location
                continue

            self.locations[occupant_id] = update_idle_location(
                person=person,
                location=old_location,
                assignment=assignment,
                execution=self.execution,
                available_space_ids=available_space_ids,
                clock=self.clock,
                config=self.config,
                rng=self.rng,
            )

        self._sync_people_from_locations()
        
    # ============================================================
    # MAIN STEP
    # ============================================================

    def step(self):
        timer = getattr(self, "timer", None)
    
        if timer is None:
            return self._step_inner()
    
        with timer.measure("simulation.step_total"):
            return self._step_inner()
    
    def _step_inner(self) -> None:
        """
        Run one ABBEY timestep.
        """

        # 0. Ambient/inspection movement before perception.
        #
        # This is important:
        #     move first -> perceive current room -> decide action
        #
        # Otherwise unattended rooms can stay hot/cold/open forever.
        with self.timer.measure("simulation.idle_movement_before_execution"):
            self._update_all_idle_locations_before_execution()
        with self.timer.measure("simulation.people_update_before_execution"):
            self._update_all_people_before_execution()

        # 1. Execute purposeful decisions/actions within the timestep.

        # 1. Execute purposeful decisions/actions within the timestep.
        with self.timer.measure("simulation.household_execution"):
            if self.use_household_execution:
                (
                    self.people,
                    self.locations,
                    self.household,
                    self.systems,
                    self.execution,
                    self.cooldowns,
                    chunk_records,
                ) = execute_household_timestep(
                    people=self.people,
                    locations=self.locations,
                    assignments=self.assignments,
                    household=self.household,
                    observation=self.observation,
                    systems=self.systems,
                    execution=self.execution,
                    cooldowns=self.cooldowns,
                    clock=self.clock,
                    config=self.config,
                    rng=self.rng,
                )
            else:
                (
                    self.person,
                    self.location,
                    self.systems,
                    self.execution,
                    self.cooldowns,
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
                    cooldowns=self.cooldowns,
                )

            if self.cooldowns is None:
                self.cooldowns = CooldownState()
        with self.timer.measure("simulation.dirty_clothes"):
            self.household = update_household_dirty_clothes(
                household=self.household,
                people=self.people,
                locations=self.locations,
                clock=self.clock,
                config=self.config,
                chunk_records=chunk_records,
            )


        with self.timer.measure("simulation.sync_person_location"):
            self._sync_person_from_location()

        # 3. Update internal needs based on representative executed action.
        with self.timer.measure("simulation.update_people"):
            self._update_all_people_after_execution(
                primary_chunk_records=chunk_records,
            )

        # 4. Old dummy/fallback performance model.
        action_energy_wh = sum(
            float(chunk.get("total_energy_wh", 0.0))
            for chunk in chunk_records
        )

        performance_input = PerformanceInput(
            systems=self.systems,
            execution=self.execution,
            clock=self.clock,
            chunk_records=chunk_records,
            action_energy_wh=action_energy_wh,

            # Legacy fallback.
            person_is_home=self.person.is_home,
            person_current_zone_id=self.location.current_space_id,

            # v0.3 multi-occupant.
            people=self.people,
            locations=self.locations,
            household=self.household,
        )

        if self.use_building_performance:
            performance_output = SimpleNamespace(
                performance_log={
                    "legacy_performance_skipped": True,
                    "reason": "use_building_performance_active",
                    "active_performance_path": "building_physics_engine",
                }
            )
        else:
            performance_output = self.performance_model.step(
                previous_observation=self.observation,
                performance_input=performance_input,
            )

            self.observation = performance_output.observation

        # Do not pass scalar action_energy_wh here, because the new model can
        # already map appliance energy from chunk_records by actor/location.
        with self.timer.measure("simulation.building_performance"):
            self._run_building_performance_if_enabled(
                chunk_records=chunk_records,
                action_energy_wh={},
            )

        # 6. Log timestep after final observation has been updated.
        self.logger.record_step(
            clock=self.clock,
            person=self.person,
            location=self.location,
            assignment=self.assignment,
            household=self.household,
            cooldowns=self.cooldowns,
            observation=self.observation,
            systems=self.systems,
            execution=self.execution,
            chunk_records=chunk_records,
            performance_log=performance_output.performance_log,
            people=self.people,
            locations=self.locations,
            internal_source_result=self.last_internal_source_result,
        )

        # 7. Advance clock.
        self.cooldowns = self.cooldowns.advance_cooldowns(
            minutes=self.clock.dt_hours * 60.0
        )
        self.clock = self.clock.advance()

    # ============================================================
    # RUN / EXPORT
    # ============================================================

    def run(
        self,
        progress_every_steps: int = 100,
        progress_every_sim_hours: float = None,
    ):
        """
        Run the simulation.
    
        Progress printing is intentionally handled at runner level, not inside
        low-level physics modules.
        """
    
        for _ in range(self.n_steps):
            current_step = int(getattr(self.clock, "step", 0))
            current_day = int(getattr(self.clock, "day", 0))
            current_hour = float(getattr(self.clock, "hour", 0.0))
    
            should_print = False
    
            if progress_every_steps is not None:
                if int(progress_every_steps) > 0:
                    if current_step % int(progress_every_steps) == 0:
                        should_print = True
    
            if progress_every_sim_hours is not None:
                interval_steps = int(
                    round(
                        float(progress_every_sim_hours)
                        / float(getattr(self.clock, "dt_hours", 1.0))
                    )
                )
    
                if interval_steps > 0 and current_step % interval_steps == 0:
                    should_print = True
    
            if current_step == 0 or current_step == self.n_steps - 1:
                should_print = True
    
            if should_print:
                percent = 100.0 * float(current_step) / max(float(self.n_steps), 1.0)
    
                print(
                    "[ABBEY] step "
                    + str(current_step)
                    + "/"
                    + str(self.n_steps)
                    + " | day "
                    + str(current_day)
                    + " | hour "
                    + "{:.2f}".format(current_hour)
                    + " | "
                    + "{:.1f}".format(percent)
                    + "%"
                )
    
            self.step()
    
        return self.logger.to_dataframe()

    def people_to_dataframe(self):
        return self.logger.people_to_dataframe()

    def save_people_csv(self, path) -> None:
        self.logger.save_people_csv(path)

    def save_csv(self, path: Union[str, Path]) -> None:
        self.logger.save_csv(path)

    def save_zone_csvs(self, folder: Union[str, Path]) -> None:
        self.logger.save_zone_csvs(folder)

    def building_zone_records_to_dataframe(self):
        import pandas as pd
        return pd.DataFrame(self.building_zone_records)

    def building_dwelling_records_to_dataframe(self):
        import pandas as pd
        return pd.DataFrame(self.building_dwelling_records)

    def building_records_to_dataframe(self):
        import pandas as pd
        return pd.DataFrame(self.building_records)

    def building_interzone_thermal_records_to_dataframe(self):
        import pandas as pd
        return pd.DataFrame(self.building_interzone_thermal_records)
    
    def building_control_bridge_records_to_dataframe(self):
        import pandas as pd
        return pd.DataFrame(self.building_control_bridge_records)

    def building_action_event_records_to_dataframe(self):
        import pandas as pd
        return pd.DataFrame(self.building_action_event_records)
    
    def building_internal_source_records_to_dataframe(self):
        import pandas as pd
        return pd.DataFrame(self.building_internal_source_records)

    def building_internal_source_zone_records_to_dataframe(self):
        import pandas as pd
        return pd.DataFrame(self.building_internal_source_zone_records)

    def building_internal_source_building_records_to_dataframe(self):
        import pandas as pd
        return pd.DataFrame(self.building_internal_source_building_records)
    
    def building_interzone_airflow_records_to_dataframe(self):
        import pandas as pd
        return pd.DataFrame(self.building_interzone_airflow_records)

    def building_window_airflow_records_to_dataframe(self):
        import pandas as pd
        return pd.DataFrame(self.building_window_airflow_records)
    
    def save_building_debug_outputs(
        self,
        folder: Union[str, Path],
        prefix: str = "building",
        output_mode: str = "debug",
        include_diagnostics: bool = True,
        include_long_records: bool = True,
        include_plots: bool = True,
        include_interzone_timestep_records: bool = True,
        include_window_detail_timestep_records: bool = True,
    ):
        from nexusep.abbey.building import save_debug_building_outputs
    
        return save_debug_building_outputs(
            sim=self,
            output_folder=str(folder),
            prefix=prefix,
            output_mode=output_mode,
            include_diagnostics=include_diagnostics,
            include_long_records=include_long_records,
            include_plots=include_plots,
            include_interzone_timestep_records=include_interzone_timestep_records,
            include_window_detail_timestep_records=include_window_detail_timestep_records,
        )
    
    def save_building_yearly_outputs(
        self,
        folder: Union[str, Path],
        prefix: str = "building",
        output_mode: str = "minimal",
        include_timestep_diagnostics: bool = False,
        include_long_records: bool = False,
        include_interzone_summaries: bool = True,
        include_interzone_timestep_records: bool = False,
        include_window_detail_summaries: bool = True,
        include_window_detail_timestep_records: bool = False,
    ):
        from nexusep.abbey.building import save_yearly_building_outputs
    
        return save_yearly_building_outputs(
            sim=self,
            output_folder=str(folder),
            prefix=prefix,
            output_mode=output_mode,
            include_timestep_diagnostics=include_timestep_diagnostics,
            include_long_records=include_long_records,
            include_interzone_summaries=include_interzone_summaries,
            include_interzone_timestep_records=include_interzone_timestep_records,
            include_window_detail_summaries=include_window_detail_summaries,
            include_window_detail_timestep_records=include_window_detail_timestep_records,
        )
    
    def save_building_playback_html(
        self,
        path: Union[str, Path],
        max_hours: float = 24.0,
        frame_stride_minutes: int = 1,
    ):
        from nexusep.abbey.building import save_building_playback_html

        return save_building_playback_html(
            sim=self,
            output_path=path,
            max_hours=max_hours,
            frame_stride_minutes=frame_stride_minutes,
        )

    # ============================================================
    # ACTION REPRESENTATION FOR NEEDS
    # ============================================================

    def _representative_action_from_chunks(
        self,
        chunk_records: List[Dict[str, Any]],
    ) -> ActionState:
        """
        Temporary bridge.

        Needs currently accept one ActionState.
        Since execution can contain several chunks/actions, select the most
        behaviorally relevant action in the timestep.
        """

        action_minutes = {}

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

    # ============================================================
    # SMALL UTILS
    # ============================================================

    def _safe_list(self, value: Any) -> List[Any]:
        if value is None:
            return []

        if isinstance(value, list):
            return value

        if isinstance(value, tuple):
            return list(value)

        return [value]

    def _get_attr_or_key(
        self,
        obj: Any,
        name: str,
        default: Any = None,
    ) -> Any:
        if obj is None:
            return default

        if isinstance(obj, dict):
            return obj.get(name, default)

        return getattr(obj, name, default)
