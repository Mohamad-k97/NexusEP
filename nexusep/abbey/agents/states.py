from dataclasses import dataclass, asdict, replace, field
from typing import Any, Dict


@dataclass
class PersonState:
    """
    Dynamic and semi-stable state of one ABBEY occupant.

    Most continuous states are intended to evolve smoothly in [0, 1],
    Bounded evolution is handled by the dynamics module.
    """
    
    # Identity / behavior profile
    occupant_id: str = "person_1"
    idle_movement_profile: str = "normal"
    mobility_tendency: float = 1.0

    # Internal physiological states
    hunger: float = 0.30
    fatigue: float = 0.20
    sleep_pressure: float = 0.20
    sickness_severity: float = 0.00
    dirty_clothes: float = 0.20

    # Perceptual discomfort states
    thermal_discomfort: float = 0.00
    air_quality_discomfort: float = 0.00
    visual_discomfort: float = 0.00
    acoustic_discomfort: float = 0.00
    
    # Thermal perception outputs
    thermal_sensation: float = 0.0          # personal PMV-like value
    thermal_satisfaction: float = 0.95      # 1 - PPD/100
    thermal_dissatisfaction: float = 0.05   # PPD/100
    
    # Thermal perception traits
    cold_sensitivity: float = 1.0
    heat_sensitivity: float = 1.0
    thermal_neutral_shift: float = 0.0

    # Derived behavioral state
    action_friction: float = 0.30

    # Location/activity state
    is_home: bool = True
    away_reason: str = "none" 
    is_sleeping: bool = False

    # Stable/semi-stable behavioral traits
    has_job: bool = True
    base_laziness: float = 0.40
    money_sensitivity: float = 0.60
    comfort_sensitivity: float = 0.70
    future_awareness: float = 0.60
    
    # Spatial state
    current_zone_id: str = "main_room"
    default_zone_id: str = "main_room"
    
    # Sleep episode memory
    minutes_asleep: float = 0.0
    minutes_awake_since_sleep: float = 1200.0
    
    # Assigned personal spaces
    assigned_sleep_zone_id: str = ""   # empty = use fallback/default
    assigned_work_zone_id: str = ""    # empty = use fallback/default
    assigned_idle_zone_id: str = ""    # empty = use fallback/default
    
    # Household  role
    household_id: str = "household_1"
    can_cook: bool = True
    is_main_cook: bool = True
    cooking_priority: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def copy(self, **updates: Any) -> "PersonState":
        return replace(self, **updates)
    
@dataclass
class HouseholdState:
    """
    Household-level state.

    This is multiagent-ready, even if v0.2 still runs one occupant.
    """

    household_id: str = "household_1"
    occupant_ids: list = field(default_factory=lambda: ["person_1"])

    main_cook_id: str = "person_1"

    # Lower number = higher priority.
    cooking_priority_by_occupant: Dict[str, int] = field(
        default_factory=lambda: {"person_1": 1}
    )

    cooked_meal_events: int = 0
    fallback_meal_events: int = 0
    last_cook_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def copy(self, **updates: Any) -> "HouseholdState":
        return replace(self, **updates)


@dataclass
class ZoneObservation:
    """
    Observation for one space/room/thermal zone.

    For now, 'zone' and 'space' mean the same thing.
    Later this can feed a multizone RC model.
    """

    zone_id: str = "main_room"
    zone_name: str = "Main room"

    indoor_temp: float = 20.0
    co2_ppm: float = 600.0
    indoor_daylight: float = 0.5
    indoor_noise: float = 0.2

    heating_on: bool = False
    cooling_on: bool = False
    lights_on: bool = False
    window_open: bool = False

    occupied_person_ids: list = field(default_factory=list)
    number_of_people: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def copy(self, **updates: Any) -> "ZoneObservation":
        return replace(self, **updates)  
    
@dataclass
class DwellingObservation:
    """
    What ABBEY receives from the building-performance module.

    Scalar fields are kept for single-zone/dummy compatibility.
    zone_observations is used for multi-space dwellings.
    """

    indoor_temp: float = 20.0
    outdoor_temp: float = 10.0
    co2_ppm: float = 600.0
    indoor_daylight: float = 0.5
    indoor_noise: float = 0.2
    electricity_tariff: float = 0.25

    default_zone_id: str = "main_room"
    zone_observations: Dict[str, ZoneObservation] = field(default_factory=dict)

    def has_zone(self, zone_id: str) -> bool:
        return zone_id in self.zone_observations

    def available_space_ids(self) -> list:
        return list(self.zone_observations.keys())

    def get_zone(self, zone_id: str) -> ZoneObservation:
        if zone_id in self.zone_observations:
            return self.zone_observations[zone_id]

        if self.default_zone_id in self.zone_observations:
            return self.zone_observations[self.default_zone_id]

        return ZoneObservation(
            zone_id=zone_id or self.default_zone_id,
            zone_name=zone_id or self.default_zone_id,
            indoor_temp=self.indoor_temp,
            co2_ppm=self.co2_ppm,
            indoor_daylight=self.indoor_daylight,
            indoor_noise=self.indoor_noise,
        )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["zone_observations"] = {
            zone_id: zone.to_dict()
            for zone_id, zone in self.zone_observations.items()
        }
        return data

    def copy(self, **updates: Any) -> "DwellingObservation":
        return replace(self, **updates)

    
@dataclass
class ZoneSystemState:
    """
    Controllable system state for one space/zone.
    """

    space_id: str = "main_room"

    window_open: bool = False
    mechanical_ventilation_on: bool = True

    heating_on: bool = False
    cooling_on: bool = False

    lights_on: bool = False

    curtain_closed: bool = False
    blind_closed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def copy(self, **updates: Any) -> "ZoneSystemState":
        return replace(self, **updates)    
    
@dataclass
class SystemState:
    """
    System/control state.

    v0.2 supports per-space controls through zone_systems.
    Legacy scalar fields are kept as fallback/default-zone values.
    """

    default_space_id: str = "main_room"

    zone_systems: Dict[str, ZoneSystemState] = field(default_factory=dict)

    # Legacy/default controls
    window_open: bool = False
    mechanical_ventilation_on: bool = True
    heating_on: bool = False
    cooling_on: bool = False
    lights_on: bool = False
    curtain_closed: bool = False
    blind_closed: bool = False

    def get_space_controls(self, space_id: str) -> ZoneSystemState:
        if space_id in self.zone_systems:
            return self.zone_systems[space_id]

        return ZoneSystemState(
            space_id=space_id,
            window_open=self.window_open,
            mechanical_ventilation_on=self.mechanical_ventilation_on,
            heating_on=self.heating_on,
            cooling_on=self.cooling_on,
            lights_on=self.lights_on,
            curtain_closed=self.curtain_closed,
            blind_closed=self.blind_closed,
        )

    def set_space_controls(
        self,
        space_id: str,
        **updates: Any,
    ) -> "SystemState":
        controls = self.get_space_controls(space_id)

        for field_name in updates:
            if not hasattr(controls, field_name):
                raise AttributeError(
                    f"ZoneSystemState has no field '{field_name}'."
                )

        new_controls = controls.copy(**updates)

        new_zone_systems = dict(self.zone_systems)
        new_zone_systems[space_id] = new_controls

        new_state = replace(
            self,
            zone_systems=new_zone_systems,
        )

        # Keep legacy/default fields synchronized for the default space.
        if space_id == self.default_space_id:
            legacy_updates = {
                key: value
                for key, value in updates.items()
                if hasattr(new_state, key)
            }
            if legacy_updates:
                new_state = replace(new_state, **legacy_updates)

        return new_state

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["zone_systems"] = {
            space_id: controls.to_dict()
            for space_id, controls in self.zone_systems.items()
        }
        return data

    def copy(self, **updates: Any) -> "SystemState":
        return replace(self, **updates)
    
    
    
@dataclass 
class ActionState:
    """
    One running action/process instance.

    Can represent:
        - control action
        - foreground action
        - background process
        - passive filler action
    """

    name: str = "do_nothing"
    category: str = "passive"
    execution_type: str = "passive"

    actor_id: str = "person_1"

    remaining_minutes: float = 0.0
    elapsed_minutes: float = 0.0

    power_w: float = 0.0
    activity_intensity: float = 0.0
    effort: float = 0.0

    requires_home: bool = False
    requires_awake: bool = False

    blocks_actor: bool = False
    background_process: bool = False
    can_continue_without_actor: bool = True
    can_be_interrupted: bool = True
    can_fill_remaining_time: bool = False
    can_repeat: bool = False

    system_effects: Dict[str, Any] = field(default_factory=dict)
    person_effects: Dict[str, Any] = field(default_factory=dict)
    post_action_zone_role: str = "current"
    action_cooldowns_on_start: Dict[str, float] = field(default_factory=dict)
    target_zone_role: str = "current"
    
    def is_active(self) -> bool:
        return self.remaining_minutes > 0.0

    def is_finished(self) -> bool:
        return self.remaining_minutes <= 0.0

    def advance(self, minutes: float) -> "ActionState":
        if minutes < 0:
            raise ValueError("minutes must be non-negative.")

        used_minutes = min(minutes, self.remaining_minutes)

        return replace(
            self,
            elapsed_minutes=self.elapsed_minutes + used_minutes,
            remaining_minutes=max(0.0, self.remaining_minutes - used_minutes),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def copy(self, **updates: Any) -> "ActionState":
        return replace(self, **updates)
    
    
@dataclass 
class SimulationClock:
    """
    Current simulation time.
    """

    step: int = 0
    hour: float = 0.0
    day: int = 0
    dt_hours: float = 0.25

    def advance(self) -> "SimulationClock":
        next_step = self.step + 1
        next_hour = self.hour + self.dt_hours
        next_day = self.day

        if next_hour >= 24.0:
            next_hour -= 24.0
            next_day += 1

        return replace(
            self,
            step=next_step,
            hour=next_hour,
            day=next_day,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def copy(self, **updates: Any) -> "SimulationClock":
        return replace(self, **updates)
    
@dataclass 
class ExecutionState:
    """
    Active foreground actions and background processes.

    Foreground actions may block an actor.
    Background processes can run in parallel, e.g. washing machine.
    """

    foreground_actions: list[ActionState] = field(default_factory=list)
    background_processes: list[ActionState] = field(default_factory=list)
    action_cooldowns: Dict[str, float] = field(default_factory=dict)

    def actor_is_blocked(self, actor_id: str = "person_1") -> bool:
        return any(
            action.actor_id == actor_id
            and action.blocks_actor
            and action.is_active()
            for action in self.foreground_actions
        )

    def active_foreground_for_actor(
        self,
        actor_id: str = "person_1",
    ) -> list[ActionState]:
        return [
            action
            for action in self.foreground_actions
            if action.actor_id == actor_id and action.is_active()
        ]

    def background_process_running(self, name: str) -> bool:
        return any(
            process.name == name and process.is_active()
            for process in self.background_processes
        )

    def active_power_w(self) -> float:
        foreground_power = sum(
            action.power_w
            for action in self.foreground_actions
            if action.is_active()
        )

        background_power = sum(
            process.power_w
            for process in self.background_processes
            if process.is_active()
        )

        return foreground_power + background_power

    def advance(self, minutes: float) -> "ExecutionState":
        if minutes < 0:
            raise ValueError("minutes must be non-negative.")
    
        new_foreground = []
    
        for action in self.foreground_actions:
            advanced = action.advance(minutes)
            if advanced.is_active():
                new_foreground.append(advanced)
    
        new_background = []
    
        for process in self.background_processes:
            advanced = process.advance(minutes)
            if advanced.is_active():
                new_background.append(advanced)
    
        new_cooldowns = {
            name: max(0.0, remaining - minutes)
            for name, remaining in self.action_cooldowns.items()
            if max(0.0, remaining - minutes) > 0.0
        }
    
        return replace(
            self,
            foreground_actions=new_foreground,
            background_processes=new_background,
            action_cooldowns=new_cooldowns,
        )

    def add_foreground_action(self, action: ActionState) -> "ExecutionState":
        return replace(
            self,
            foreground_actions=[*self.foreground_actions, action],
        )

    def add_background_process(self, process: ActionState) -> "ExecutionState":
        return replace(
            self,
            background_processes=[*self.background_processes, process],
        )

    def action_on_cooldown(self, action_name: str) -> bool:
        return self.action_cooldowns.get(action_name, 0.0) > 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "foreground_actions": [
                action.to_dict() for action in self.foreground_actions
            ],
            "background_processes": [
                process.to_dict() for process in self.background_processes
            ],
            "active_power_w": self.active_power_w(),
        }

    def copy(self, **updates: Any) -> "ExecutionState":
        return replace(self, **updates)
