"""
Simple building performance model for ABBEY.

This model is intentionally simple.

It:
- maps people to zones
- updates zone occupancy
- applies controllers
- updates temperature
- updates CO2
- computes zone/dwelling/building energy
- returns updated observations and records

It is not a real RC network yet.
"""
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from contextlib import contextmanager
from nexusep.abbey.agents.states import DwellingObservation, ZoneObservation
from nexusep.abbey.building.model import BuildingModel, ZoneState, ZoneModel
from nexusep.abbey.building.systems import (
    ZoneSystemSpec,
    ZoneControlState,
    ZoneControlCommand,
    ZoneEnergyResult,
    DwellingEnergyResult,
    BuildingEnergyResult,
    heating_power_w_from_zone_control_command,
    cooling_power_w_from_zone_control_command,
)
from nexusep.abbey.building.controllers import controller_for_control_state
from nexusep.abbey.building.physics.internal_sources import (
    make_building_internal_source_result,
    make_physics_inputs_from_internal_sources,
)
from nexusep.abbey.building.physics.engine import (
    BuildingPhysicsStepInput,
    run_building_physics_step,
)
from nexusep.abbey.building.physics.weather import WeatherState

BUILDING_PERFORMANCE_PATH_ENGINE = "engine"
BUILDING_PERFORMANCE_PATH_LEGACY_FALLBACK_EXPLICIT = "legacy_fallback_explicit"
BUILDING_PERFORMANCE_PATH_LEGACY_FALLBACK_AFTER_ENGINE_ERROR = (
    "legacy_fallback_after_engine_error"
)

WEATHER_SOURCE_EXPLICIT = "weather_state_explicit"
WEATHER_SOURCE_FROM_OBSERVATION = "weather_from_observation"
WEATHER_SOURCE_DEFAULT_SYNTHETIC = "weather_default_synthetic"
# ============================================================
# ENGINE DIAGNOSTIC COPY GROUPS
# ============================================================
#
# These lists describe physical meaning, not implementation phase.
#
# engine.py is the canonical producer of these diagnostics.
# performance.py only copies selected engine diagnostics into the
# public zone/building timestep records.
#
# Keep PHASE_* aliases below for old tests/imports, but do not use
# them in the copy logic.

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
        
def _unique_record_keys(keys):
    out = []

    for key in keys:
        if key not in out:
            out.append(key)

    return out


ENGINE_THERMAL_ZONE_KEYS = [
    "old_indoor_temp_c",
    "new_indoor_temp_c",
    "old_indoor_mass_temp_c",
    "new_indoor_mass_temp_c",
    "thermal_old_air_temperature_c",
    "thermal_new_air_temperature_c",
    "thermal_old_mass_temperature_c",
    "thermal_new_mass_temperature_c",
    "thermal_convective_gain_w",
    "thermal_radiative_gain_w",
    "thermal_ventilation_h_w_k",
]


ENGINE_AIRFLOW_ZONE_KEYS = [
    "airflow_infiltration_flow_m3_h",
    "airflow_mechanical_ventilation_flow_m3_h",
    "airflow_window_flow_m3_h",
    "airflow_outdoor_exchange_m3_h",
    "airflow_interzone_exchange_m3_h",
    "airflow_total_exchange_m3_h",
]


ENGINE_AIR_QUALITY_ZONE_KEYS = [
    "old_co2_ppm",
    "new_co2_ppm",
    "co2_generation_m3_h",
]


ENGINE_MOISTURE_ZONE_KEYS = [
    "old_humidity_ratio_kg_kg",
    "new_humidity_ratio_kg_kg",
    "old_relative_humidity_percent",
    "new_relative_humidity_percent",
    "moisture_generation_kg_h",
    "moisture_transport_airflow_m3_h",
    "old_indoor_relative_humidity_percent",
    "new_indoor_relative_humidity_percent",
    "old_indoor_humidity_ratio_kg_kg",
    "new_indoor_humidity_ratio_kg_kg",
]


ENGINE_INTERZONE_THERMAL_ZONE_KEYS = [
    "interzone_thermal_link_count",
    "interzone_thermal_total_h_w_k",
    "interzone_heat_gain_w",
    "interzone_heat_loss_w",
    "interzone_net_heat_gain_w",
]


ENGINE_WINDOW_ZONE_KEYS = [
    "window_count",
    "window_orientation_deg_list",
    "window_curtain_open_count",
    "window_curtain_closed_count",
    "window_solar_alignment_factor_max",
    "window_daylight_alignment_factor_max",
    "window_effective_solar_factor_sum",
    "window_effective_solar_factor_max",
    "window_effective_visible_transmittance_sum",
    "window_effective_visible_transmittance_max",
]


ENGINE_SOLAR_ZONE_KEYS = [
    "solar_gain_w",
    "solar_gain_wh",
]


ENGINE_DAYLIGHT_LIGHTING_ZONE_KEYS = [
    "old_indoor_daylight",
    "new_indoor_daylight",
    "proposed_indoor_daylight",
    "daylight_illuminance_lux",
    "indoor_illuminance_lux",
    "artificial_lighting_illuminance_lux",
    "visual_comfort_status",
    "lighting_result_lights_on",
    "lighting_result_power_w",
    "lighting_result_energy_wh",
    "lighting_result_requested_lux",
    "lighting_result_dimming_fraction",
]


ENGINE_HVAC_CONTROL_ZONE_KEYS = [
    "heating_power_fraction",
    "cooling_power_fraction",
    "heating_capacity_w",
    "cooling_capacity_w",
    "heating_efficiency_or_cop",
    "cooling_efficiency_or_cop",
    "heating_input_power_w",
    "cooling_input_power_w",

    "command_heating_on",
    "command_heating_power_fraction",
    "command_heating_power_w",
    "command_heating_delivered_power_w",
    "command_cooling_on",
    "command_cooling_power_fraction",
    "command_cooling_power_w",
    "command_cooling_delivered_power_w",
    "command_hvac_thermal_gain_w",
    "command_heating_delivered_energy_wh",
    "command_cooling_delivered_energy_wh",
    "command_ventilation_flow_m3_h",

    "command_lights_on",
    "command_lighting_power_w",
    "command_window_open",
    "command_window_opening_fraction",
    "command_curtain_open",
]


ENGINE_INTERNAL_SOURCE_ZONE_KEYS = [
    "internal_source_record_count",
    "internal_average_sensible_heat_w",
    "internal_average_latent_heat_w",
    "internal_average_electricity_power_w",
    "internal_electricity_wh",
    "internal_average_co2_generation_m3_h",
    "internal_average_moisture_generation_kg_h",
    "internal_average_sensible_heat_w_by_source_kind",
    "internal_average_electricity_power_w_by_source_kind",
    "internal_average_co2_generation_m3_h_by_source_kind",
    "internal_average_moisture_generation_kg_h_by_source_kind",
    "internal_record_count_by_source_kind",
    "total_internal_gain_w",
    "total_internal_gain_wh",
    "internal_electricity_wh_by_source_kind",
"internal_average_latent_heat_w_by_source_kind",

"appliance_electricity_wh_from_internal_sources",
"lighting_electricity_wh_from_internal_sources",
"hvac_electricity_wh_from_internal_sources",

"appliance_total_heat_w",
"appliance_total_heat_wh",
"lighting_sensible_heat_w",

"hvac_sensible_gain_w",
"hvac_heating_gain_w",
"hvac_cooling_gain_w",
"hvac_cooling_removal_w",

"zone_energy_balance_residual_wh",
"zone_energy_balance_ok",
]


ENGINE_ACOUSTIC_ZONE_KEYS = [
    "old_indoor_noise",
    "new_indoor_noise",
    "proposed_indoor_noise",
    "indoor_noise",
    "indoor_noise_db",
    "background_noise_db",
    "outdoor_noise_db",
    "local_noise_source_db",
    "local_noise_source_count",
    "outdoor_noise_contribution_db",
    "interzone_noise_contribution_db",
    "max_neighbor_noise_contribution_db",
    "acoustic_discomfort_input",
]


ENGINE_AIRFLOW_AIR_QUALITY_ZONE_KEYS = _unique_record_keys(
    ENGINE_AIRFLOW_ZONE_KEYS
    + ENGINE_AIR_QUALITY_ZONE_KEYS
)


ENGINE_SOLAR_DAYLIGHT_LIGHTING_ZONE_KEYS = _unique_record_keys(
    ENGINE_WINDOW_ZONE_KEYS
    + ENGINE_SOLAR_ZONE_KEYS
    + ENGINE_DAYLIGHT_LIGHTING_ZONE_KEYS
)


ENGINE_ZONE_DIAGNOSTIC_KEYS = _unique_record_keys(
    ENGINE_THERMAL_ZONE_KEYS
    + ENGINE_AIRFLOW_ZONE_KEYS
    + ENGINE_AIR_QUALITY_ZONE_KEYS
    + ENGINE_MOISTURE_ZONE_KEYS
    + ENGINE_INTERZONE_THERMAL_ZONE_KEYS
    + ENGINE_WINDOW_ZONE_KEYS
    + ENGINE_SOLAR_ZONE_KEYS
    + ENGINE_DAYLIGHT_LIGHTING_ZONE_KEYS
    + ENGINE_HVAC_CONTROL_ZONE_KEYS
    + ENGINE_INTERNAL_SOURCE_ZONE_KEYS
    + ENGINE_ACOUSTIC_ZONE_KEYS
)


ENGINE_SOLAR_DAYLIGHT_LIGHTING_BUILDING_KEYS = [
    "window_count",
    "window_curtain_closed_count",
    "total_solar_gain_w",
    "total_solar_gain_w_from_zone_records",
    "max_zone_solar_gain_w",
    "average_zone_daylight_illuminance_lux",
    "max_zone_daylight_illuminance_lux",
    "average_zone_indoor_illuminance_lux",
    "max_zone_indoor_illuminance_lux",
    "total_lighting_power_result_w",
    "total_lighting_result_energy_wh",
]


ENGINE_ACOUSTIC_BUILDING_KEYS = [
    "has_acoustic_step_result",
    "average_zone_indoor_noise",
    "max_zone_indoor_noise",
    "average_zone_indoor_noise_db",
    "max_zone_indoor_noise_db",
    "total_local_noise_source_count",
]


ENGINE_BUILDING_DIAGNOSTIC_KEYS = _unique_record_keys(
    ENGINE_SOLAR_DAYLIGHT_LIGHTING_BUILDING_KEYS
    + ENGINE_ACOUSTIC_BUILDING_KEYS
)


# ------------------------------------------------------------
# Backward-compatible aliases.
# Do not use these in new copy logic.
# ------------------------------------------------------------

PHASE_12_ENGINE_ZONE_DIAGNOSTIC_KEYS = _unique_record_keys(
    ENGINE_AIRFLOW_ZONE_KEYS
    + ENGINE_AIR_QUALITY_ZONE_KEYS
    + ENGINE_MOISTURE_ZONE_KEYS
)

PHASE_13_ENGINE_ZONE_DIAGNOSTIC_KEYS = _unique_record_keys(
    ENGINE_WINDOW_ZONE_KEYS
    + ENGINE_SOLAR_ZONE_KEYS
    + ENGINE_DAYLIGHT_LIGHTING_ZONE_KEYS
)

PHASE_13_ENGINE_BUILDING_DIAGNOSTIC_KEYS = list(
    ENGINE_SOLAR_DAYLIGHT_LIGHTING_BUILDING_KEYS
)

PHASE_14_ENGINE_ZONE_DIAGNOSTIC_KEYS = list(
    ENGINE_ACOUSTIC_ZONE_KEYS
)

PHASE_14_ENGINE_BUILDING_DIAGNOSTIC_KEYS = list(
    ENGINE_ACOUSTIC_BUILDING_KEYS
)

PHASE_15_ENGINE_ZONE_DIAGNOSTIC_KEYS = _unique_record_keys(
    ENGINE_THERMAL_ZONE_KEYS
    + ENGINE_INTERZONE_THERMAL_ZONE_KEYS
    + ENGINE_HVAC_CONTROL_ZONE_KEYS
    + ENGINE_INTERNAL_SOURCE_ZONE_KEYS
)
@dataclass
class BuildingPerformanceStepResult:
    observation: DwellingObservation

    zone_records: List[Dict[str, Any]] = field(default_factory=list)
    dwelling_records: List[Dict[str, Any]] = field(default_factory=list)
    building_record: Dict[str, Any] = field(default_factory=dict)
    interzone_airflow_records: List[Dict[str, Any]] = field(default_factory=list)
    window_airflow_records: List[Dict[str, Any]] = field(default_factory=list)
    
    zone_energy_results: Dict[str, ZoneEnergyResult] = field(default_factory=dict)
    dwelling_energy_results: Dict[str, DwellingEnergyResult] = field(default_factory=dict)
    building_energy_result: Optional[BuildingEnergyResult] = None

    zone_control_commands: Dict[str, ZoneControlCommand] = field(default_factory=dict)

    internal_source_result: Any = None
    physics_inputs: Dict[str, Any] = field(default_factory=dict)
    physics_engine_result: Any = None
    interzone_thermal_flow_records: List[Dict[str, Any]] = field(default_factory=list)
    physics_engine_active: bool = False
    physics_engine_error: Optional[str] = None
   
    weather_state: Any = None
    weather_source: str = WEATHER_SOURCE_DEFAULT_SYNTHETIC
    
    performance_path: str = BUILDING_PERFORMANCE_PATH_ENGINE
    legacy_fallback_used: bool = False
    legacy_fallback_reason: Optional[str] = None


class BuildingPhysicsPerformanceModel:
    """
    Engine-backed ABBEY building performance model.

    Public v0.4 building-performance adapter.

    It keeps the external performance-model interface stable while routing
    the normal path through the unified building physics engine:

        controller/control bridge
            -> BuildingPhysicsStepInput
            -> run_building_physics_step(...)
            -> BuildingPerformanceStepResult

    The old toy/simple calculation remains available only through the
    explicit legacy fallback branch.
    """

    def __init__(
        self,
        building_model: BuildingModel,
        outdoor_co2_ppm: float = 420.0,
        sensible_gain_per_person_w: float = 75.0,
        co2_generation_per_person_m3_h: float = 0.018,
        thermostat_deadband_c: float = 0.5,
        min_temp_c: float = -20.0,
        max_temp_c: float = 45.0,
        min_co2_ppm: float = 420.0,
        max_co2_ppm: float = 5000.0,
        use_physics_engine: bool = True,
        allow_legacy_physics_fallback: bool = False,
        physics_graph: Any = None,
    ):
        self.building_model = building_model

        self.outdoor_co2_ppm = float(outdoor_co2_ppm)
        self.sensible_gain_per_person_w = float(sensible_gain_per_person_w)
        self.co2_generation_per_person_m3_h = float(co2_generation_per_person_m3_h)
        self.thermostat_deadband_c = float(thermostat_deadband_c)

        self.min_temp_c = float(min_temp_c)
        self.max_temp_c = float(max_temp_c)
        self.min_co2_ppm = float(min_co2_ppm)
        self.max_co2_ppm = float(max_co2_ppm)

        self.previous_commands = {}
        self.use_physics_engine = bool(use_physics_engine)
        self.allow_legacy_physics_fallback = bool(allow_legacy_physics_fallback)
        self.physics_graph = physics_graph
        self.last_physics_engine_result = None
        self.last_physics_engine_error = None

        
    def step(
        self,
        performance_input,
        dt_minutes,
    ) -> BuildingPerformanceStepResult:
        timer = _get_attr_or_key(
            performance_input,
            "timer",
            None,
        )

        with _measure_if_available(
            timer,
            "building_performance.step_total",
        ):
            return self._step_inner(
                performance_input=performance_input,
                dt_minutes=dt_minutes,
                timer=timer,
            )

    def _step_inner(
        self,
        performance_input,
        dt_minutes,
        timer=None,
    ) -> BuildingPerformanceStepResult:
        with _measure_if_available(
            timer,
            "building_performance.read_inputs",
        ):
            dt_minutes = float(dt_minutes)
            dt_hours = dt_minutes / 60.0
            dt_seconds = dt_minutes * 60.0

            if dt_minutes <= 0:
                raise ValueError("dt_minutes must be positive.")

            observation = _get_attr_or_key(performance_input, "observation", None)
            locations = _get_attr_or_key(performance_input, "locations", {})
            people = _get_attr_or_key(performance_input, "people", {})
            chunk_records = _get_attr_or_key(
                performance_input,
                "chunk_records",
                [],
            )
            role_to_zone_id = _get_attr_or_key(
                performance_input,
                "role_to_zone_id",
                {},
            )

            day = _get_attr_or_key(performance_input, "day", None)
            hour = _get_attr_or_key(performance_input, "hour", None)
            step = _get_attr_or_key(performance_input, "step", None)

            outdoor_temp_c = self._get_outdoor_temp_c(
                performance_input=performance_input,
                observation=observation,
            )

            occupancy_by_zone = self._map_occupancy_by_zone(
                locations=locations,
            )

            zone_records = []
            zone_energy_results = {}
            zone_control_commands = {}
            zone_system_specs = {}
            zone_occupied_states = {}

            all_zone_models = self.building_model.all_zone_models()

        # ------------------------------------------------------------
        # PASS 1:
        # Create occupied states, system specs, and physical commands.
        # ------------------------------------------------------------
        with _measure_if_available(
            timer,
            "building_performance.prepare_zone_commands",
        ):
            for zone_id, zone_model in all_zone_models.items():
                old_state = self.building_model.get_zone_state(zone_id)

                occupied_person_ids = occupancy_by_zone.get(zone_id, [])
                occupied_state = old_state.with_occupants(occupied_person_ids)

                system_spec = self._get_or_create_zone_system_spec(zone_model)
                control_state = self._get_or_create_zone_control_state(zone_model)

                previous_command = self.previous_commands.get(zone_id)

                controller = controller_for_control_state(
                    control_state=control_state,
                    deadband_c=self.thermostat_deadband_c,
                )

                command = controller.step(
                    zone_state=occupied_state,
                    control_state=control_state,
                    system_spec=system_spec,
                    previous_command=previous_command,
                    context={
                        "outdoor_temp_c": outdoor_temp_c,
                        "outdoor_co2_ppm": self.outdoor_co2_ppm,
                        "dt_minutes": dt_minutes,
                        "people": people,
                    },
                )

                self.previous_commands[zone_id] = command
                zone_control_commands[zone_id] = command
                zone_system_specs[zone_id] = system_spec
                zone_occupied_states[zone_id] = occupied_state

            # Make occupancy visible to the physics engine.
            # The engine reads current ZoneState from BuildingModel.
            for zone_id, occupied_state in zone_occupied_states.items():
                self.building_model.set_zone_state(zone_id, occupied_state)

        # ------------------------------------------------------------
        # PASS 2:
        # Preferred path: execute physical effects through physics engine.
        # Legacy path remains fallback only.
        # ------------------------------------------------------------
        physics_engine_result = None
        physics_engine_active = False
        physics_engine_error = None
        performance_path = BUILDING_PERFORMANCE_PATH_ENGINE
        legacy_fallback_used = False
        legacy_fallback_reason = None
        internal_source_result = None
        physics_inputs = {}
        interzone_thermal_flow_records = []
        interzone_airflow_records = []
        window_airflow_records = []

        with _measure_if_available(
            timer,
            "building_performance.resolve_weather",
        ):
            weather_state, weather_source = self._resolve_weather_for_step(
                performance_input=performance_input,
                observation=observation,
                outdoor_temp_c=outdoor_temp_c,
            )

        if self.use_physics_engine:
            try:
                with _measure_if_available(
                    timer,
                    "building_performance.build_engine_input",
                ):
                    step_input = self._build_physics_step_input(
                        performance_input=performance_input,
                        dt_minutes=dt_minutes,
                        weather_state=weather_state,
                        zone_control_commands=zone_control_commands,
                        zone_system_specs=zone_system_specs,
                        people=people,
                        locations=locations,
                        role_to_zone_id=role_to_zone_id,
                        chunk_records=chunk_records,
                    )

                with _measure_if_available(
                    timer,
                    "building_performance.engine_total",
                ):
                    physics_engine_result = self._run_physics_engine(
                        step_input=step_input,
                    )

                physics_engine_active = True
                self.last_physics_engine_result = physics_engine_result
                self.last_physics_engine_error = None

            except Exception as exc:
                physics_engine_error = repr(exc)
                self.last_physics_engine_error = physics_engine_error

                if not self.allow_legacy_physics_fallback:
                    raise

        if physics_engine_active:
            with _measure_if_available(
                timer,
                "building_performance.adapter_payload",
            ):
                adapter_payload = self._make_engine_adapter_payload(
                    step=step,
                    day=day,
                    hour=hour,
                    dt_hours=dt_hours,
                    all_zone_models=all_zone_models,
                    zone_control_commands=zone_control_commands,
                    zone_system_specs=zone_system_specs,
                    physics_engine_result=physics_engine_result,
                    performance_path=performance_path,
                )

                internal_source_result = adapter_payload["internal_source_result"]
                physics_inputs = adapter_payload["physics_inputs"]
                interzone_thermal_flow_records = adapter_payload[
                    "interzone_thermal_flow_records"
                ]
                interzone_airflow_records = adapter_payload[
                    "interzone_airflow_records"
                ]
                window_airflow_records = adapter_payload[
                    "window_airflow_records"
                ]
                zone_records = adapter_payload["zone_records"]
                zone_energy_results = adapter_payload["zone_energy_results"]

        else:
            with _measure_if_available(
                timer,
                "building_performance.legacy_fallback",
            ):
                # --------------------------------------------------------
                # LEGACY FALLBACK PATH.
                #
                # Quarantined in Phase 10.13.
                # This branch is not the normal ABBEY HVAC/control path.
                # It exists only for explicit debugging or temporary backward
                # compatibility when the real physics engine is disabled or
                # allowed to fail over.
                #
                # Normal path:
                #     controller -> ZoneControlCommand -> physics.engine
                #
                # Legacy path:
                #     simplified _update_temperature / _update_co2 helpers
                # --------------------------------------------------------

                legacy_fallback_used = True

                if self.use_physics_engine:
                    performance_path = (
                        BUILDING_PERFORMANCE_PATH_LEGACY_FALLBACK_AFTER_ENGINE_ERROR
                    )
                    legacy_fallback_reason = physics_engine_error
                else:
                    performance_path = BUILDING_PERFORMANCE_PATH_LEGACY_FALLBACK_EXPLICIT
                    legacy_fallback_reason = "use_physics_engine_false"

                internal_source_result = make_building_internal_source_result(
                    chunk_records=chunk_records,
                    people=people,
                    locations=locations,
                    role_to_zone_id=role_to_zone_id,
                    building_model=self.building_model,
                    dt_minutes=dt_minutes,
                    include_people=True,
                    include_lighting=True,
                    lighting_power_result=None,
                    include_hvac=False,
                    zone_control_commands=zone_control_commands,
                    zone_system_specs=zone_system_specs,
                )

                physics_inputs = make_physics_inputs_from_internal_sources(
                    internal_source_result=internal_source_result,
                    zone_ids=list(all_zone_models.keys()),
                )

                bridge_inputs_by_zone = (
                    internal_source_result.physics_bridge_inputs_by_zone()
                )

                appliance_energy_by_zone = (
                    internal_source_result.appliance_electricity_wh_by_zone()
                )

                lighting_energy_by_zone = (
                    internal_source_result.lighting_electricity_wh_by_zone()
                )

                for zone_id, zone_model in all_zone_models.items():
                    occupied_state = zone_occupied_states[zone_id]
                    command = zone_control_commands[zone_id]
                    system_spec = zone_system_specs[zone_id]

                    bridge_row = bridge_inputs_by_zone.get(zone_id, {})

                    internal_sensible_heat_w = float(
                        bridge_row.get("average_sensible_heat_w", 0.0)
                    )

                    co2_generation_m3_h = float(
                        bridge_row.get("average_co2_generation_m3_h", 0.0)
                    )

                    appliance_energy_wh = appliance_energy_by_zone.get(
                        zone_id,
                        0.0,
                    )
                    lighting_energy_wh = lighting_energy_by_zone.get(
                        zone_id,
                        0.0,
                    )

                    new_temp_c = self._update_temperature(
                        zone_model=zone_model,
                        zone_state=occupied_state,
                        system_spec=system_spec,
                        command=command,
                        outdoor_temp_c=outdoor_temp_c,
                        appliance_energy_wh=appliance_energy_wh,
                        dt_hours=dt_hours,
                        dt_seconds=dt_seconds,
                        internal_sensible_heat_w=internal_sensible_heat_w,
                    )

                    new_co2_ppm = self._update_co2(
                        zone_model=zone_model,
                        zone_state=occupied_state,
                        command=command,
                        dt_hours=dt_hours,
                        co2_generation_m3_h=co2_generation_m3_h,
                    )

                    new_state = occupied_state.copy(
                        indoor_temp_c=new_temp_c,
                        co2_ppm=new_co2_ppm,
                    )

                    self.building_model.set_zone_state(zone_id, new_state)

                    energy_result = self._calculate_zone_energy(
                        zone_model=zone_model,
                        system_spec=system_spec,
                        command=command,
                        appliance_energy_wh=appliance_energy_wh,
                        lighting_energy_wh=lighting_energy_wh,
                        dt_hours=dt_hours,
                    )

                    zone_energy_results[zone_id] = energy_result

                    record = self._make_zone_record(
                        step=step,
                        day=day,
                        hour=hour,
                        zone_model=zone_model,
                        zone_state=new_state,
                        command=command,
                        energy_result=energy_result,
                        internal_source_row=bridge_row,
                        dt_hours=dt_hours,
                    )

                    record["physics_engine_active"] = False
                    record["physics_engine_error"] = physics_engine_error
                    record["physics_path"] = performance_path
                    record["performance_path"] = performance_path
                    record["legacy_fallback_used"] = legacy_fallback_used
                    record["legacy_fallback_reason"] = legacy_fallback_reason

                    self._add_weather_diagnostics_to_record(
                        record=record,
                        weather_state=weather_state,
                        weather_source=weather_source,
                    )

                    zone_records.append(record)

        with _measure_if_available(
            timer,
            "building_performance.aggregate_records",
        ):
            dwelling_energy_results = self._aggregate_dwelling_energy(
                zone_energy_results
            )

            building_energy_result = self._aggregate_building_energy(
                dwelling_energy_results
            )

            dwelling_records = self._make_dwelling_records(
                step=step,
                day=day,
                hour=hour,
                dwelling_energy_results=dwelling_energy_results,
                zone_records=zone_records,
                dt_hours=dt_hours,
            )

            building_record = self._make_building_record(
                step=step,
                day=day,
                hour=hour,
                building_energy_result=building_energy_result,
                zone_records=zone_records,
            )

            building_record["internal_source_record_count"] = len(
                internal_source_result.records
            )

            building_record["internal_total_electricity_wh"] = (
                internal_source_result.total_electricity_wh()
            )

            building_record["internal_total_average_sensible_heat_w"] = (
                internal_source_result.total_average_sensible_heat_w()
            )

            building_record["internal_total_co2_generation_m3_h"] = (
                internal_source_result.total_co2_generation_m3_h()
            )

            building_record["internal_total_moisture_generation_kg_h"] = (
                internal_source_result.total_moisture_generation_kg_h()
            )

            self._add_engine_status_to_building_record(
                building_record=building_record,
                physics_engine_result=physics_engine_result,
                physics_engine_active=physics_engine_active,
                physics_engine_error=physics_engine_error,
                performance_path=performance_path,
                legacy_fallback_used=legacy_fallback_used,
                legacy_fallback_reason=legacy_fallback_reason,
                interzone_thermal_flow_records=interzone_thermal_flow_records,
                interzone_airflow_records=interzone_airflow_records,
                window_airflow_records=window_airflow_records,
            )

            self._add_weather_diagnostics_to_record(
                record=building_record,
                weather_state=weather_state,
                weather_source=weather_source,
            )

        with _measure_if_available(
            timer,
            "building_performance.make_result",
        ):
            return self._make_performance_result_from_adapter_payload(
                observation=observation,
                outdoor_temp_c=outdoor_temp_c,
                zone_control_commands=zone_control_commands,
                zone_records=zone_records,
                dwelling_records=dwelling_records,
                building_record=building_record,
                zone_energy_results=zone_energy_results,
                dwelling_energy_results=dwelling_energy_results,
                building_energy_result=building_energy_result,
                internal_source_result=internal_source_result,
                physics_inputs=physics_inputs,
                physics_engine_result=physics_engine_result,
                interzone_thermal_flow_records=interzone_thermal_flow_records,
                interzone_airflow_records=interzone_airflow_records,
                window_airflow_records=window_airflow_records,
                physics_engine_active=physics_engine_active,
                physics_engine_error=physics_engine_error,
                performance_path=performance_path,
                legacy_fallback_used=legacy_fallback_used,
                legacy_fallback_reason=legacy_fallback_reason,
                weather_state=weather_state,
                weather_source=weather_source,
            )

    # ============================================================
    # OCCUPANCY
    # ============================================================

    def _map_occupancy_by_zone(self, locations: Dict[str, Any]) -> Dict[str, List[str]]:
        occupancy_by_zone = {
            zone_id: []
            for zone_id in self.building_model.all_zone_ids()
        }

        for occupant_id, location in locations.items():
            is_home = bool(_get_attr_or_key(location, "is_home", False))

            if not is_home:
                continue

            zone_id = _get_attr_or_key(location, "current_space_id", None)

            if zone_id in occupancy_by_zone:
                occupancy_by_zone[zone_id].append(occupant_id)

        return occupancy_by_zone

    # ============================================================
    # APPLIANCE / ACTION ENERGY
    # ============================================================

    def _map_appliance_energy_by_zone(
        self,
        locations: Dict[str, Any],
        chunk_records: Any,
        action_energy_wh: Any,
        dt_hours: float,
    ) -> Dict[str, float]:
        return {}

    def _zone_for_actor(self, actor_id: str, locations: Dict[str, Any]) -> Optional[str]:
        if actor_id not in locations:
            return None

        location = locations[actor_id]

        if not bool(_get_attr_or_key(location, "is_home", False)):
            return None

        return _get_attr_or_key(location, "current_space_id", None)

    def _default_energy_zone_id(self, locations: Dict[str, Any]) -> Optional[str]:
        for _, location in locations.items():
            if bool(_get_attr_or_key(location, "is_home", False)):
                return _get_attr_or_key(location, "current_space_id", None)

        zone_ids = self.building_model.all_zone_ids()

        if not zone_ids:
            return None

        return zone_ids[0]

    # ============================================================
    # PHYSICS
    # ============================================================

    def _update_temperature(
        self,
        zone_model: ZoneModel,
        zone_state: ZoneState,
        system_spec: ZoneSystemSpec,
        command: ZoneControlCommand,
        outdoor_temp_c: float,
        appliance_energy_wh: float,
        dt_hours: float,
        dt_seconds: float,
        internal_sensible_heat_w: float,
    ) -> float:
        
        # LEGACY FALLBACK ONLY.
        # Do not call this from the normal Phase 10 engine path.
        # Real HVAC thermal effects belong in physics.engine + thermal.py.
        temp_c = float(zone_state.indoor_temp_c)
    
        effective_ua_w_per_k = float(zone_model.ua_w_per_k)
    
        ventilation_flow_m3_h = float(command.ventilation_flow_m3_h)
    
        ventilation_heat_transfer_w_per_k = (
            0.33 * ventilation_flow_m3_h
        )
    
        effective_ua_w_per_k += ventilation_heat_transfer_w_per_k
    
        outdoor_exchange_w = effective_ua_w_per_k * (
            outdoor_temp_c - temp_c
        )
    
        net_heat_flow_w = (
            outdoor_exchange_w
            + float(internal_sensible_heat_w)
        )
    
        delta_t_k = (
            net_heat_flow_w
            * dt_seconds
            / float(zone_model.thermal_capacity_j_per_k)
        )
    
        new_temp_c = temp_c + delta_t_k
    
        return new_temp_c

    def _update_co2(
        self,
        zone_model: ZoneModel,
        zone_state: ZoneState,
        command: ZoneControlCommand,
        dt_hours: float,
        co2_generation_m3_h: float,
    ) -> float:
        
    # LEGACY FALLBACK ONLY.
    # Do not call this from the normal Phase 10 engine path.
    # Real CO2 updates belong in physics.engine + airflow.py.
        volume_m3 = float(zone_model.volume_m3)
    
        if volume_m3 <= 0.0:
            return float(zone_state.co2_ppm)
    
        current_co2_ppm = float(zone_state.co2_ppm)
    
        ventilation_flow_m3_h = float(command.ventilation_flow_m3_h)
    
        generation_m3_h = float(co2_generation_m3_h)
    
        generation_ppm_h = (
            generation_m3_h
            / volume_m3
            * 1000000.0
        )
    
        ventilation_rate_h = 0.0
    
        if volume_m3 > 0.0:
            ventilation_rate_h = ventilation_flow_m3_h / volume_m3
    
        ventilation_ppm_h = ventilation_rate_h * (
            self.outdoor_co2_ppm - current_co2_ppm
        )
    
        new_co2_ppm = current_co2_ppm + (
            generation_ppm_h + ventilation_ppm_h
        ) * dt_hours
    
        return max(
            self.outdoor_co2_ppm,
            new_co2_ppm,
        )

    def _calculate_zone_energy(
        self,
        zone_model: ZoneModel,
        system_spec: ZoneSystemSpec,
        command: ZoneControlCommand,
        appliance_energy_wh: float,
        lighting_energy_wh: float,
        dt_hours: float,
    ) -> ZoneEnergyResult:
        heating_power_w = heating_power_w_from_zone_control_command(
            command=command,
            system_spec=system_spec,
        )

        cooling_power_w = cooling_power_w_from_zone_control_command(
            command=command,
            system_spec=system_spec,
        )

        heating_delivered_energy_wh = heating_power_w * dt_hours
        cooling_delivered_energy_wh = cooling_power_w * dt_hours

        heating_efficiency_or_cop = float(system_spec.heating_efficiency_or_cop)
        cooling_efficiency_or_cop = float(system_spec.cooling_efficiency_or_cop)

        if heating_efficiency_or_cop <= 0.0:
            heating_efficiency_or_cop = 1.0

        if cooling_efficiency_or_cop <= 0.0:
            cooling_efficiency_or_cop = 1.0

        heating_input_energy_wh = (
            heating_delivered_energy_wh / heating_efficiency_or_cop
        )

        cooling_input_energy_wh = (
            cooling_delivered_energy_wh / cooling_efficiency_or_cop
        )

        ventilation_fan_power_w = float(
            _get_attr_or_key(
                system_spec,
                "ventilation_fan_power_w",
                0.0,
            )
        )

        ventilation_flow_m3_h = float(
            _get_attr_or_key(
                command,
                "ventilation_flow_m3_h",
                0.0,
            )
        )

        ventilation_fan_energy_wh = 0.0

        if ventilation_flow_m3_h > 0.0 and ventilation_fan_power_w > 0.0:
            ventilation_fan_energy_wh = ventilation_fan_power_w * dt_hours

        appliance_energy_wh = float(appliance_energy_wh)
        lighting_energy_wh = float(lighting_energy_wh)

        hvac_delivered_energy_wh = (
            heating_delivered_energy_wh
            + cooling_delivered_energy_wh
        )

        hvac_input_energy_wh = (
            heating_input_energy_wh
            + cooling_input_energy_wh
            + ventilation_fan_energy_wh
        )

        total_energy_wh = (
            hvac_input_energy_wh
            + lighting_energy_wh
            + appliance_energy_wh
        )

        return ZoneEnergyResult(
            zone_id=zone_model.zone_id,
            dwelling_id=zone_model.dwelling_id,
            building_id=zone_model.building_id,
            heating_delivered_energy_wh=heating_delivered_energy_wh,
            cooling_delivered_energy_wh=cooling_delivered_energy_wh,
            heating_energy_wh=heating_input_energy_wh,
            cooling_energy_wh=cooling_input_energy_wh,
            ventilation_fan_energy_wh=ventilation_fan_energy_wh,
            lighting_energy_wh=lighting_energy_wh,
            appliance_energy_wh=appliance_energy_wh,
            hvac_delivered_energy_wh=hvac_delivered_energy_wh,
            hvac_input_energy_wh=hvac_input_energy_wh,
            total_energy_wh=total_energy_wh,
        )

    # ============================================================
    # SYSTEM / CONTROL LOOKUP
    # ============================================================

    def _get_or_create_zone_system_spec(self, zone_model: ZoneModel) -> ZoneSystemSpec:
        dwelling = self.building_model.dwellings.get(zone_model.dwelling_id)

        if dwelling is not None:
            if zone_model.zone_id in dwelling.system_specs:
                return dwelling.system_specs[zone_model.zone_id]

            default_spec = self._default_zone_system_spec(zone_model)
            dwelling.system_specs[zone_model.zone_id] = default_spec
            return default_spec

        if zone_model.zone_id in self.building_model.shared_system_specs:
            return self.building_model.shared_system_specs[zone_model.zone_id]

        default_spec = self._default_zone_system_spec(zone_model)
        self.building_model.shared_system_specs[zone_model.zone_id] = default_spec
        return default_spec

    def _get_or_create_zone_control_state(self, zone_model: ZoneModel) -> ZoneControlState:
        dwelling = self.building_model.dwellings.get(zone_model.dwelling_id)

        if dwelling is not None:
            if zone_model.zone_id in dwelling.control_states:
                return dwelling.control_states[zone_model.zone_id]

            default_state = self._default_zone_control_state(zone_model)
            dwelling.control_states[zone_model.zone_id] = default_state
            return default_state

        if zone_model.zone_id in self.building_model.building_control_states:
            return self.building_model.building_control_states[zone_model.zone_id]

        default_state = self._default_zone_control_state(zone_model)
        self.building_model.building_control_states[zone_model.zone_id] = default_state
        return default_state

    def _default_zone_system_spec(self, zone_model: ZoneModel) -> ZoneSystemSpec:
        return ZoneSystemSpec(
            zone_id=zone_model.zone_id,
            dwelling_id=zone_model.dwelling_id,
            building_id=zone_model.building_id,
            heating_capacity_w=80.0 * zone_model.floor_area_m2,
            cooling_capacity_w=60.0 * zone_model.floor_area_m2,
            ventilation_flow_m3_h=0.5 * zone_model.volume_m3,
            lighting_power_w=6.0 * zone_model.floor_area_m2,
            has_heating=True,
            has_cooling=False,
            has_ventilation=True,
            has_lighting=True,
            has_operable_window=True,
            has_shading=True,
        )

    def _default_zone_control_state(self, zone_model: ZoneModel) -> ZoneControlState:
        return ZoneControlState(
            zone_id=zone_model.zone_id,
            dwelling_id=zone_model.dwelling_id,
            building_id=zone_model.building_id,
            heating_mode="semi_auto",
            heating_setpoint_c=20.0,
            cooling_mode="off",
            cooling_setpoint_c=26.0,
            ventilation_mode="manual",
            manual_ventilation_on=True,
            lighting_mode="manual",
            manual_lights_on=False,
            window_mode="manual",
            manual_window_open=False,
            shading_mode="manual",
            manual_curtain_open=True,
        )

    # ============================================================
    # AGGREGATION
    # ============================================================

    def _aggregate_dwelling_energy(
        self,
        zone_energy_results: Dict[str, ZoneEnergyResult],
    ) -> Dict[str, DwellingEnergyResult]:
        results = {}

        for dwelling_id, dwelling in self.building_model.dwellings.items():
            zone_results = {
                zone_id: zone_energy_results[zone_id]
                for zone_id in dwelling.zone_models.keys()
                if zone_id in zone_energy_results
            }

            results[dwelling_id] = DwellingEnergyResult.from_zone_results(
                dwelling_id=dwelling_id,
                building_id=dwelling.building_id,
                zone_results=zone_results,
            )

        return results

    def _aggregate_building_energy(
        self,
        dwelling_energy_results: Dict[str, DwellingEnergyResult],
    ) -> BuildingEnergyResult:
        return BuildingEnergyResult.from_dwelling_results(
            building_id=self.building_model.building_id,
            dwelling_results=dwelling_energy_results,
            shared_system_energy_wh=0.0,
        )

    # ============================================================
    # RECORDS
    # ============================================================
    
    def _make_interzone_airflow_records(
        self,
        step: Any,
        day: Any,
        hour: Any,
        physics_engine_result: Any,
    ) -> List[Dict[str, Any]]:
        if physics_engine_result is None:
            return []

        airflow_network = getattr(
            physics_engine_result,
            "airflow_network",
            None,
        )

        if airflow_network is None:
            return []

        raw_records = getattr(
            airflow_network,
            "interzone_airflow_records",
            {},
        )

        raw_links = getattr(
            airflow_network,
            "interzone_airflow_links",
            {},
        )

        rows = []

        time_hour = None

        if day is not None and hour is not None:
            time_hour = float(day) * 24.0 + float(hour)

        if isinstance(raw_records, dict):
            records_iter = raw_records.values()
        else:
            records_iter = raw_records

        for record in records_iter:
            if hasattr(record, "to_dict"):
                row = record.to_dict()
            else:
                row = dict(record)

            link_id = row.get("link_id")
            link = raw_links.get(link_id) if isinstance(raw_links, dict) else None

            if link is not None:
                row["opening_fraction"] = getattr(link, "opening_fraction", None)
                row["mixing_flow_m3_h"] = getattr(link, "mixing_flow_m3_h", None)
                row["connection_type"] = getattr(link, "connection_type", None)
                row["base_airflow_m3_h"] = getattr(link, "base_airflow_m3_h", None)
                row["max_flow_m3_h"] = getattr(link, "max_flow_m3_h", None)

            row["step"] = step
            row["day"] = day
            row["hour"] = hour
            row["time_hour"] = time_hour
            row["building_id"] = self.building_model.building_id
            row["source"] = "physics_engine_interzone_airflow"

            rows.append(row)

        return rows

    def _make_window_airflow_records(
        self,
        step: Any,
        day: Any,
        hour: Any,
        physics_engine_result: Any,
    ) -> List[Dict[str, Any]]:
        if physics_engine_result is None:
            return []

        window_boundary_result = getattr(
            physics_engine_result,
            "window_boundary_result",
            None,
        )

        if window_boundary_result is None:
            return []

        raw_results = getattr(
            window_boundary_result,
            "window_results_by_id",
            {},
        )

        step_input = getattr(
            physics_engine_result,
            "step_input",
            None,
        )

        weather_state = getattr(
            step_input,
            "weather_state",
            None,
        )

        wind_direction_deg = getattr(
            weather_state,
            "wind_direction_deg",
            None,
        )

        wind_speed_m_s = getattr(
            weather_state,
            "wind_speed_m_s",
            None,
        )

        rows = []

        time_hour = None

        if day is not None and hour is not None:
            time_hour = float(day) * 24.0 + float(hour)

        if isinstance(raw_results, dict):
            results_iter = raw_results.values()
        else:
            results_iter = raw_results

        for result in results_iter:
            if hasattr(result, "to_dict"):
                row = result.to_dict()
            else:
                row = dict(result)

            row["step"] = step
            row["day"] = day
            row["hour"] = hour
            row["time_hour"] = time_hour
            row["building_id"] = self.building_model.building_id
            row["wind_direction_deg"] = wind_direction_deg
            row["wind_speed_m_s"] = wind_speed_m_s
            row["source"] = "physics_engine_window_airflow"

            rows.append(row)

        return rows
    
    def _make_interzone_thermal_flow_records(
        self,
        step: Any,
        day: Any,
        hour: Any,
        physics_engine_result: Any,
    ) -> List[Dict[str, Any]]:
        if physics_engine_result is None:
            return []

        raw_records = getattr(
            physics_engine_result,
            "interzone_thermal_flow_records",
            [],
        )

        rows = []

        time_hour = None

        if day is not None and hour is not None:
            time_hour = float(day) * 24.0 + float(hour)

        for record in raw_records:
            if hasattr(record, "to_dict"):
                row = record.to_dict()
            else:
                row = dict(record)

            row["step"] = step
            row["day"] = day
            row["hour"] = hour
            row["time_hour"] = time_hour
            row["building_id"] = self.building_model.building_id
            row["source"] = "physics_engine_interzone_thermal"

            rows.append(row)

        return rows

    def _resolve_weather_for_step(
        self,
        performance_input: Any,
        observation: Any,
        outdoor_temp_c: float,
    ) -> Tuple[Any, Optional[str]]:
        """
        Phase 17.3 adapter helper.

        Supports both:
            - Phase 17.2 weather helper returning (weather_state, weather_source)
            - older helper returning only weather_state
        """

        weather_result = self._make_weather_state_for_engine(
            performance_input=performance_input,
            observation=observation,
            outdoor_temp_c=outdoor_temp_c,
        )

        if isinstance(weather_result, tuple) and len(weather_result) == 2:
            return weather_result

        explicit_weather = _get_attr_or_key(
            performance_input,
            "weather_state",
            None,
        )

        if explicit_weather is not None and weather_result is explicit_weather:
            return weather_result, "weather_state_explicit"

        return weather_result, "weather_default_synthetic"

    def _build_physics_step_input(
        self,
        performance_input: Any,
        dt_minutes: float,
        weather_state: Any,
        zone_control_commands: Dict[str, ZoneControlCommand],
        zone_system_specs: Dict[str, ZoneSystemSpec],
        people: Dict[str, Any],
        locations: Dict[str, Any],
        role_to_zone_id: Dict[str, str],
        chunk_records: List[Any],
    ) -> BuildingPhysicsStepInput:
        physics_graph = _get_attr_or_key(
            performance_input,
            "physics_graph",
            self.physics_graph,
        )

        return BuildingPhysicsStepInput(
            building_model=self.building_model,
            dt_minutes=dt_minutes,
            physics_graph=physics_graph,
            weather_state=weather_state,
            zone_control_commands=zone_control_commands,
            zone_system_specs=zone_system_specs,
            people=people,
            locations=locations,
            role_to_zone_id=role_to_zone_id,
            chunk_records=chunk_records,
        )

    def _run_physics_engine(
        self,
        step_input: BuildingPhysicsStepInput,
    ) -> Any:
        physics_engine_result = run_building_physics_step(
            step_input=step_input,
            require_physics_graph=False,
            write_back_to_building_model=True,
        )

        self.last_physics_engine_result = physics_engine_result
        self.last_physics_engine_error = None

        return physics_engine_result

    def _copy_engine_zone_diagnostics(
        self,
        record: Dict[str, Any],
        engine_zone_record: Dict[str, Any],
    ) -> None:
        """
        Copy engine-produced diagnostics into the public zone timestep row.

        engine.py is the canonical producer of these fields.
        performance.py only adapts them into the public output schema.
        """

        if engine_zone_record is None:
            return

        for key in ENGINE_ZONE_DIAGNOSTIC_KEYS:
            if key in engine_zone_record:
                record[key] = engine_zone_record.get(key)

    def _normalize_internal_source_record_count(
        self,
        record: Dict[str, Any],
    ) -> None:
        """
        Keep scalar internal_source_record_count robust.

        Some bridge rows expose the per-kind count correctly even when
        internal_source_record_count is absent or zero.
        """

        try:
            current_count = int(record.get("internal_source_record_count", 0))
        except Exception:
            current_count = 0

        if current_count > 0:
            return

        by_kind = record.get("internal_record_count_by_source_kind", {})

        if not isinstance(by_kind, dict):
            return

        fixed_count = 0

        for item in by_kind.values():
            try:
                fixed_count += int(item)
            except Exception:
                pass

        record["internal_source_record_count"] = fixed_count

    def _add_engine_status_to_zone_record(
        self,
        record: Dict[str, Any],
        physics_engine_result: Any,
        performance_path: str,
    ) -> None:
        record["physics_engine_active"] = True
        record["physics_path"] = performance_path
        record["performance_path"] = performance_path
        record["legacy_fallback_used"] = False
        record["legacy_fallback_reason"] = None
        record["physics_engine_source"] = getattr(
            physics_engine_result,
            "source",
            None,
        )

    def _make_engine_adapter_payload(
        self,
        step: Any,
        day: Any,
        hour: Any,
        dt_hours: float,
        all_zone_models: Dict[str, ZoneModel],
        zone_control_commands: Dict[str, ZoneControlCommand],
        zone_system_specs: Dict[str, ZoneSystemSpec],
        physics_engine_result: Any,
        performance_path: str,
    ) -> Dict[str, Any]:
        """
        Convert BuildingPhysicsStepResult into the public performance payload.

        This is the official Phase 17.3 adapter:
            BuildingPhysicsStepResult
                -> zone energy
                -> public zone records
                -> long physics records
        """

        internal_source_result = physics_engine_result.internal_source_result
        physics_inputs = physics_engine_result.physics_inputs or {}

        interzone_thermal_flow_records = self._make_interzone_thermal_flow_records(
            step=step,
            day=day,
            hour=hour,
            physics_engine_result=physics_engine_result,
        )

        interzone_airflow_records = self._make_interzone_airflow_records(
            step=step,
            day=day,
            hour=hour,
            physics_engine_result=physics_engine_result,
        )

        window_airflow_records = self._make_window_airflow_records(
            step=step,
            day=day,
            hour=hour,
            physics_engine_result=physics_engine_result,
        )

        bridge_inputs_by_zone = {}

        if internal_source_result is not None and hasattr(
            internal_source_result,
            "physics_bridge_inputs_by_zone",
        ):
            bridge_inputs_by_zone = (
                internal_source_result.physics_bridge_inputs_by_zone()
            )

        appliance_energy_by_zone = {}
        lighting_energy_by_zone = {}

        if internal_source_result is not None:
            if hasattr(internal_source_result, "appliance_electricity_wh_by_zone"):
                appliance_energy_by_zone = (
                    internal_source_result.appliance_electricity_wh_by_zone()
                )

            if hasattr(internal_source_result, "lighting_electricity_wh_by_zone"):
                lighting_energy_by_zone = (
                    internal_source_result.lighting_electricity_wh_by_zone()
                )

        engine_zone_records_by_zone = {
            row.get("zone_id"): row
            for row in getattr(physics_engine_result, "zone_records", [])
        }

        zone_records = []
        zone_energy_results = {}

        for zone_id, zone_model in all_zone_models.items():
            new_state = self.building_model.get_zone_state(zone_id)
            command = zone_control_commands[zone_id]
            system_spec = zone_system_specs[zone_id]

            bridge_row = bridge_inputs_by_zone.get(zone_id, {})

            appliance_energy_wh = appliance_energy_by_zone.get(zone_id, 0.0)
            lighting_energy_wh = lighting_energy_by_zone.get(zone_id, 0.0)

            energy_result = self._calculate_zone_energy(
                zone_model=zone_model,
                system_spec=system_spec,
                command=command,
                appliance_energy_wh=appliance_energy_wh,
                lighting_energy_wh=lighting_energy_wh,
                dt_hours=dt_hours,
            )

            zone_energy_results[zone_id] = energy_result

            record = self._make_zone_record(
                step=step,
                day=day,
                hour=hour,
                zone_model=zone_model,
                zone_state=new_state,
                command=command,
                energy_result=energy_result,
                internal_source_row=bridge_row,
                dt_hours=dt_hours,
            )

            self._add_engine_status_to_zone_record(
                record=record,
                physics_engine_result=physics_engine_result,
                performance_path=performance_path,
            )

            engine_zone_record = engine_zone_records_by_zone.get(zone_id, {})

            self._copy_engine_zone_diagnostics(
                record=record,
                engine_zone_record=engine_zone_record,
            )

            self._normalize_internal_source_record_count(record)

            zone_records.append(record)

        return {
            "internal_source_result": internal_source_result,
            "physics_inputs": physics_inputs,
            "interzone_thermal_flow_records": interzone_thermal_flow_records,
            "interzone_airflow_records": interzone_airflow_records,
            "window_airflow_records": window_airflow_records,
            "zone_records": zone_records,
            "zone_energy_results": zone_energy_results,
        }

    def _add_engine_status_to_building_record(
        self,
        building_record: Dict[str, Any],
        physics_engine_result: Any,
        physics_engine_active: bool,
        physics_engine_error: Optional[str],
        performance_path: str,
        legacy_fallback_used: bool,
        legacy_fallback_reason: Optional[str],
        interzone_thermal_flow_records: List[Dict[str, Any]],
        interzone_airflow_records: List[Dict[str, Any]],
        window_airflow_records: List[Dict[str, Any]],
    ) -> None:
        building_record["physics_engine_active"] = physics_engine_active
        building_record["physics_engine_error"] = physics_engine_error
        building_record["physics_path"] = performance_path
        building_record["performance_path"] = performance_path
        building_record["legacy_fallback_used"] = legacy_fallback_used
        building_record["legacy_fallback_reason"] = legacy_fallback_reason

        building_record["interzone_thermal_flow_record_count"] = len(
            interzone_thermal_flow_records
        )

        building_record["interzone_airflow_record_count"] = len(
            interzone_airflow_records
        )

        building_record["window_airflow_record_count"] = len(
            window_airflow_records
        )

        if physics_engine_result is None:
            return

        building_record["physics_engine_source"] = getattr(
            physics_engine_result,
            "source",
            None,
        )

        building_record["physics_engine_has_thermal_step_result"] = (
            physics_engine_result.thermal_step_result is not None
        )

        building_record["physics_engine_has_interzone_thermal_network"] = (
            getattr(physics_engine_result, "interzone_thermal_network", None)
            is not None
        )

        building_record["physics_engine_interzone_thermal_link_count"] = (
            len(
                getattr(
                    getattr(
                        physics_engine_result,
                        "interzone_thermal_network",
                        None,
                    ),
                    "links",
                    {},
                )
            )
        )

        building_record["physics_engine_interzone_thermal_flow_record_count"] = (
            len(
                getattr(
                    physics_engine_result,
                    "interzone_thermal_flow_records",
                    [],
                )
            )
        )

        building_record["physics_engine_has_airflow_network"] = (
            physics_engine_result.airflow_network is not None
        )

        building_record["physics_engine_has_co2_step_result"] = (
            physics_engine_result.co2_step_result is not None
        )

        building_record["physics_engine_has_moisture_step_result"] = (
            physics_engine_result.moisture_step_result is not None
        )

        building_record["physics_engine_has_acoustic_step_result"] = (
            getattr(physics_engine_result, "acoustic_step_result", None)
            is not None
        )

        engine_building_record = getattr(
            physics_engine_result,
            "building_record",
            {},
        ) or {}

        for key in ENGINE_BUILDING_DIAGNOSTIC_KEYS:
            if key in engine_building_record:
                building_record[key] = engine_building_record.get(key)

    def _make_performance_result_from_adapter_payload(
        self,
        observation: Any,
        outdoor_temp_c: float,
        zone_control_commands: Dict[str, ZoneControlCommand],
        zone_records: List[Dict[str, Any]],
        dwelling_records: List[Dict[str, Any]],
        building_record: Dict[str, Any],
        zone_energy_results: Dict[str, ZoneEnergyResult],
        dwelling_energy_results: Dict[str, DwellingEnergyResult],
        building_energy_result: BuildingEnergyResult,
        internal_source_result: Any,
        physics_inputs: Dict[str, Any],
        physics_engine_result: Any,
        interzone_thermal_flow_records: List[Dict[str, Any]],
        interzone_airflow_records: List[Dict[str, Any]],
        window_airflow_records: List[Dict[str, Any]],
        physics_engine_active: bool,
        physics_engine_error: Optional[str],
        performance_path: str,
        legacy_fallback_used: bool,
        legacy_fallback_reason: Optional[str],
        weather_state: Any = None,
        weather_source: Optional[str] = None,
    ) -> BuildingPerformanceStepResult:
        updated_observation = self._make_updated_observation(
            previous_observation=observation,
            outdoor_temp_c=outdoor_temp_c,
            zone_control_commands=zone_control_commands,
        )

        return BuildingPerformanceStepResult(
            observation=updated_observation,
            zone_records=zone_records,
            dwelling_records=dwelling_records,
            building_record=building_record,
            zone_energy_results=zone_energy_results,
            dwelling_energy_results=dwelling_energy_results,
            building_energy_result=building_energy_result,
            zone_control_commands=zone_control_commands,
            internal_source_result=internal_source_result,
            physics_inputs=physics_inputs,
            physics_engine_result=physics_engine_result,
            interzone_thermal_flow_records=interzone_thermal_flow_records,
            interzone_airflow_records=interzone_airflow_records,
            window_airflow_records=window_airflow_records,
            physics_engine_active=physics_engine_active,
            physics_engine_error=physics_engine_error,
            weather_state=weather_state,
            weather_source=weather_source,
            performance_path=performance_path,
            legacy_fallback_used=legacy_fallback_used,
            legacy_fallback_reason=legacy_fallback_reason,
        )
    
    def _make_zone_record(
        self,
        step: Any,
        day: Any,
        hour: Any,
        zone_model: ZoneModel,
        zone_state: ZoneState,
        command: ZoneControlCommand,
        energy_result: ZoneEnergyResult,
        internal_source_row: Optional[Dict[str, Any]] = None,
        dt_hours: float = 0.0,
    ) -> Dict[str, Any]:
        system_spec = self._get_or_create_zone_system_spec(zone_model)

        heating_delivered_power_w = heating_power_w_from_zone_control_command(
            command=command,
            system_spec=system_spec,
        )

        cooling_delivered_power_w = cooling_power_w_from_zone_control_command(
            command=command,
            system_spec=system_spec,
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

        heating_power_fraction = float(
            _get_attr_or_key(command, "heating_power_fraction", 0.0)
        )

        cooling_power_fraction = float(
            _get_attr_or_key(command, "cooling_power_fraction", 0.0)
        )

        if heating_efficiency_or_cop <= 0.0:
            heating_efficiency_or_cop = 1.0

        if cooling_efficiency_or_cop <= 0.0:
            cooling_efficiency_or_cop = 1.0

        heating_input_power_w = heating_delivered_power_w / heating_efficiency_or_cop
        cooling_input_power_w = cooling_delivered_power_w / cooling_efficiency_or_cop

        internal_source_row = internal_source_row or {}

        internal_average_sensible_heat_w = float(
            internal_source_row.get("average_sensible_heat_w", 0.0)
        )

        internal_average_latent_heat_w = float(
            internal_source_row.get("average_latent_heat_w", 0.0)
        )

        total_internal_gain_w = (
            internal_average_sensible_heat_w
            + internal_average_latent_heat_w
        )
        indoor_relative_humidity_percent = _get_attr_or_key(
            zone_state,
            "indoor_relative_humidity_percent",
            None,
        )

        if indoor_relative_humidity_percent is None:
            indoor_relative_humidity_percent = 50.0

        indoor_humidity_ratio_kg_kg = _get_attr_or_key(
            zone_state,
            "indoor_humidity_ratio_kg_kg",
            None,
        )

        if indoor_humidity_ratio_kg_kg is None:
            indoor_humidity_ratio_kg_kg = 0.008
        record = {
            "step": step,
            "day": day,
            "hour": hour,
            "building_id": zone_model.building_id,
            "dwelling_id": zone_model.dwelling_id,
            "zone_id": zone_model.zone_id,
            "zone_name": zone_model.zone_name,
            "zone_scope": zone_model.zone_scope,
            "number_of_people": zone_state.number_of_people,
            "occupied_person_ids": list(zone_state.occupied_person_ids),
            "indoor_temp_c": zone_state.indoor_temp_c,
            "indoor_mass_temp_c": _get_attr_or_key(
                zone_state,
                "indoor_mass_temp_c",
                None,
            ),
            "co2_ppm": zone_state.co2_ppm,
            "indoor_daylight": zone_state.indoor_daylight,
            "indoor_noise": zone_state.indoor_noise,
            "indoor_relative_humidity_percent": indoor_relative_humidity_percent,
            "indoor_humidity_ratio_kg_kg": indoor_humidity_ratio_kg_kg,
            "heating_on": command.heating_on,
            "cooling_on": command.cooling_on,
            "lights_on": command.lights_on,
            "window_open": command.window_open,
            "curtain_open": command.curtain_open,
            "heating_delivered_power_w": heating_delivered_power_w,
            "cooling_delivered_power_w": cooling_delivered_power_w,
            "lighting_power_w": command.lighting_power_w,
            "ventilation_flow_m3_h": command.ventilation_flow_m3_h,
            "ventilation_fan_power_w": (
                system_spec.ventilation_fan_power_w
                if command.ventilation_flow_m3_h > 0.0
                else 0.0
            ),
            "heating_delivered_energy_wh": energy_result.heating_delivered_energy_wh,
            "cooling_delivered_energy_wh": energy_result.cooling_delivered_energy_wh,
            "heating_energy_wh": energy_result.heating_energy_wh,
            "cooling_energy_wh": energy_result.cooling_energy_wh,
            "ventilation_fan_energy_wh": energy_result.ventilation_fan_energy_wh,
            "lighting_energy_wh": energy_result.lighting_energy_wh,
            "appliance_energy_wh": energy_result.appliance_energy_wh,
            "hvac_delivered_energy_wh": energy_result.hvac_delivered_energy_wh,
            "hvac_input_energy_wh": energy_result.hvac_input_energy_wh,
            "total_energy_wh": energy_result.total_energy_wh,
            "heating_power_fraction": heating_power_fraction,
            "cooling_power_fraction": cooling_power_fraction,
            "heating_capacity_w": heating_capacity_w,
            "cooling_capacity_w": cooling_capacity_w,
            "heating_efficiency_or_cop": heating_efficiency_or_cop,
            "cooling_efficiency_or_cop": cooling_efficiency_or_cop,
            "heating_input_power_w": heating_input_power_w,
            "cooling_input_power_w": cooling_input_power_w,

            # ------------------------------------------------------------
            # Stable command diagnostics.
            #
            # These are written here, not only copied from engine.py, so
            # standard output validation also works for legacy/fallback
            # paths and simple harness tests.
            # ------------------------------------------------------------
            "command_heating_on": bool(command.heating_on),
            "command_heating_power_fraction": heating_power_fraction,
            "command_heating_power_w": heating_delivered_power_w,
            "command_heating_delivered_power_w": heating_delivered_power_w,

            "command_cooling_on": bool(command.cooling_on),
            "command_cooling_power_fraction": cooling_power_fraction,
            "command_cooling_power_w": cooling_delivered_power_w,
            "command_cooling_delivered_power_w": cooling_delivered_power_w,

            "command_hvac_thermal_gain_w": (
                heating_delivered_power_w
                - cooling_delivered_power_w
            ),

            "command_ventilation_flow_m3_h": command.ventilation_flow_m3_h,

            "command_lights_on": bool(command.lights_on),
            "command_lighting_power_w": command.lighting_power_w,

            "command_window_open": bool(command.window_open),
            "command_window_opening_fraction": _get_attr_or_key(
                command,
                "window_opening_fraction",
                0.0,
            ),
            "command_curtain_open": bool(command.curtain_open),
        }

        if internal_source_row is not None:
            zone_energy_balance_residual_wh = (
                float(energy_result.total_energy_wh)
                - (
                    float(energy_result.appliance_energy_wh)
                    + float(energy_result.lighting_energy_wh)
                    + float(energy_result.hvac_input_energy_wh)
                )
            )
    
            record["internal_source_record_count"] = internal_source_row.get(
                "record_count",
                0,
            )
    
            record["internal_average_sensible_heat_w"] = internal_source_row.get(
                "average_sensible_heat_w",
                0.0,
            )
    
            record["internal_average_latent_heat_w"] = internal_source_row.get(
                "average_latent_heat_w",
                0.0,
            )
    
            record["internal_average_electricity_power_w"] = internal_source_row.get(
                "average_electricity_power_w",
                0.0,
            )
    
            record["internal_electricity_wh"] = internal_source_row.get(
                "electricity_wh",
                0.0,
            )
    
            record["internal_average_co2_generation_m3_h"] = internal_source_row.get(
                "average_co2_generation_m3_h",
                0.0,
            )
    
            record["internal_average_moisture_generation_kg_h"] = internal_source_row.get(
                "average_moisture_generation_kg_h",
                0.0,
            )
    
            record["internal_average_sensible_heat_w_by_source_kind"] = internal_source_row.get(
                "internal_average_sensible_heat_w_by_source_kind",
                internal_source_row.get("average_sensible_heat_w_by_source_kind", {}),
            )
    
            record["internal_average_latent_heat_w_by_source_kind"] = internal_source_row.get(
                "internal_average_latent_heat_w_by_source_kind",
                internal_source_row.get("average_latent_heat_w_by_source_kind", {}),
            )
    
            record["internal_average_electricity_power_w_by_source_kind"] = internal_source_row.get(
                "internal_average_electricity_power_w_by_source_kind",
                internal_source_row.get("average_electricity_power_w_by_source_kind", {}),
            )
    
            record["internal_average_co2_generation_m3_h_by_source_kind"] = internal_source_row.get(
                "internal_average_co2_generation_m3_h_by_source_kind",
                internal_source_row.get("average_co2_generation_m3_h_by_source_kind", {}),
            )
    
            record["internal_average_moisture_generation_kg_h_by_source_kind"] = internal_source_row.get(
                "internal_average_moisture_generation_kg_h_by_source_kind",
                internal_source_row.get("average_moisture_generation_kg_h_by_source_kind", {}),
            )
    
            record["internal_record_count_by_source_kind"] = internal_source_row.get(
                "record_count_by_source_kind",
                {},
            )
    
            record["internal_electricity_wh_by_source_kind"] = internal_source_row.get(
                "internal_electricity_wh_by_source_kind",
                internal_source_row.get("electricity_wh_by_source_kind", {}),
            )
    
            record["appliance_electricity_wh_from_internal_sources"] = float(
                internal_source_row.get("appliance_electricity_wh", 0.0)
            )
    
            record["lighting_electricity_wh_from_internal_sources"] = float(
                internal_source_row.get("lighting_electricity_wh", 0.0)
            )
    
            record["hvac_electricity_wh_from_internal_sources"] = float(
                internal_source_row.get("hvac_electricity_wh", 0.0)
            )
    
            record["appliance_total_heat_w"] = float(
                internal_source_row.get("appliance_total_heat_w", 0.0)
            )
    
            record["appliance_total_heat_wh"] = float(
                internal_source_row.get("appliance_total_heat_wh", 0.0)
            )
    
            record["lighting_sensible_heat_w"] = float(
                internal_source_row.get("lighting_sensible_heat_w", 0.0)
            )
    
            record["hvac_sensible_gain_w"] = float(
                internal_source_row.get("hvac_sensible_gain_w", 0.0)
            )
    
            record["hvac_heating_gain_w"] = float(
                internal_source_row.get("hvac_heating_gain_w", 0.0)
            )
    
            record["hvac_cooling_gain_w"] = float(
                internal_source_row.get("hvac_cooling_gain_w", 0.0)
            )
    
            record["hvac_cooling_removal_w"] = float(
                internal_source_row.get("hvac_cooling_removal_w", 0.0)
            )
    
            record["total_internal_gain_w"] = total_internal_gain_w
            record["total_internal_gain_wh"] = total_internal_gain_w * float(dt_hours)
    
            record["zone_energy_balance_residual_wh"] = zone_energy_balance_residual_wh
            record["zone_energy_balance_ok"] = abs(zone_energy_balance_residual_wh) <= 1e-6

        return record

    @staticmethod
    def _summary_float(value: Any, default: float = 0.0) -> float:
        if value is None:
            return float(default)

        try:
            return float(value)
        except Exception:
            return float(default)

    @classmethod
    def _summary_values(
        cls,
        records: List[Dict[str, Any]],
        key: str,
    ) -> List[float]:
        values = []

        for record in records:
            if key not in record:
                continue

            value = record.get(key)

            if value is None:
                continue

            try:
                values.append(float(value))
            except Exception:
                continue

        return values

    @classmethod
    def _summary_sum(
        cls,
        records: List[Dict[str, Any]],
        key: str,
    ) -> float:
        return sum(cls._summary_values(records, key))

    @classmethod
    def _summary_mean(
        cls,
        records: List[Dict[str, Any]],
        key: str,
        default: float = 0.0,
    ) -> float:
        values = cls._summary_values(records, key)

        if not values:
            return float(default)

        return sum(values) / float(len(values))

    @classmethod
    def _summary_min(
        cls,
        records: List[Dict[str, Any]],
        key: str,
        default: float = 0.0,
    ) -> float:
        values = cls._summary_values(records, key)

        if not values:
            return float(default)

        return min(values)

    @classmethod
    def _summary_max(
        cls,
        records: List[Dict[str, Any]],
        key: str,
        default: float = 0.0,
    ) -> float:
        values = cls._summary_values(records, key)

        if not values:
            return float(default)

        return max(values)

    @staticmethod
    def _summary_zone_records_for_dwelling(
        zone_records: List[Dict[str, Any]],
        dwelling: Any,
        dwelling_id: str,
    ) -> List[Dict[str, Any]]:
        private_zone_ids = set(
            getattr(
                dwelling,
                "private_zone_ids",
                list(getattr(dwelling, "zone_models", {}).keys()),
            )
        )

        out = []

        for record in zone_records:
            zone_id = record.get("zone_id")
            record_dwelling_id = record.get("dwelling_id")
            zone_scope = record.get("zone_scope")

            if zone_id not in private_zone_ids:
                continue

            if record_dwelling_id not in (None, dwelling_id):
                continue

            if zone_scope not in (None, "private"):
                continue

            out.append(record)

        return out

    @classmethod
    def _add_zone_physics_summary_to_record(
        cls,
        target: Dict[str, Any],
        records: List[Dict[str, Any]],
        dt_hours: float,
        prefix: str = "",
    ) -> None:
        target[prefix + "zone_count"] = len(records)

        target[prefix + "mean_indoor_temp_c"] = cls._summary_mean(
            records,
            "indoor_temp_c",
        )
        target[prefix + "min_indoor_temp_c"] = cls._summary_min(
            records,
            "indoor_temp_c",
        )
        target[prefix + "max_indoor_temp_c"] = cls._summary_max(
            records,
            "indoor_temp_c",
        )

        target[prefix + "mean_indoor_mass_temp_c"] = cls._summary_mean(
            records,
            "indoor_mass_temp_c",
        )
        target[prefix + "mean_co2_ppm"] = cls._summary_mean(
            records,
            "co2_ppm",
        )
        target[prefix + "max_co2_ppm"] = cls._summary_max(
            records,
            "co2_ppm",
        )

        target[prefix + "mean_indoor_daylight"] = cls._summary_mean(
            records,
            "indoor_daylight",
        )
        target[prefix + "mean_indoor_noise"] = cls._summary_mean(
            records,
            "indoor_noise",
        )

        target[prefix + "total_solar_gain_wh"] = cls._summary_sum(
            records,
            "solar_gain_wh",
        )

        target[prefix + "total_internal_electricity_wh"] = cls._summary_sum(
            records,
            "internal_electricity_wh",
        )

        target[prefix + "total_internal_average_sensible_heat_w"] = cls._summary_sum(
            records,
            "internal_average_sensible_heat_w",
        )

        target[prefix + "mean_internal_average_sensible_heat_w"] = cls._summary_mean(
            records,
            "internal_average_sensible_heat_w",
        )

        target[prefix + "total_internal_sensible_heat_wh"] = (
            cls._summary_sum(records, "internal_average_sensible_heat_w")
            * float(dt_hours)
        )

        target[prefix + "total_internal_gain_wh"] = cls._summary_sum(
            records,
            "total_internal_gain_wh",
        )

        target[prefix + "total_ventilation_flow_m3_h"] = cls._summary_sum(
            records,
            "ventilation_flow_m3_h",
        )

        target[prefix + "average_ventilation_flow_m3_h"] = cls._summary_mean(
            records,
            "ventilation_flow_m3_h",
        )

        target[prefix + "total_airflow_outdoor_exchange_m3_h"] = cls._summary_sum(
            records,
            "airflow_outdoor_exchange_m3_h",
        )

        target[prefix + "total_airflow_interzone_exchange_m3_h"] = cls._summary_sum(
            records,
            "airflow_interzone_exchange_m3_h",
        )

        target[prefix + "total_local_noise_source_count"] = int(
            cls._summary_sum(records, "local_noise_source_count")
        )
        
    def _make_dwelling_records(
        self,
        step: Any,
        day: Any,
        hour: Any,
        dwelling_energy_results: Dict[str, DwellingEnergyResult],
        zone_records: Optional[List[Dict[str, Any]]] = None,
        dt_hours: float = 0.0,
    ) -> List[Dict[str, Any]]:
        records = []
        zone_records = zone_records or []

        for dwelling_id, result in dwelling_energy_results.items():
            dwelling = self.building_model.dwellings[dwelling_id]

            dwelling_zone_records = self._summary_zone_records_for_dwelling(
                zone_records=zone_records,
                dwelling=dwelling,
                dwelling_id=dwelling_id,
            )

            total_occupancy = sum(
                int(record.get("number_of_people", 0))
                for record in dwelling_zone_records
            )

            zone_total_energy_wh = self._summary_sum(
                dwelling_zone_records,
                "total_energy_wh",
            )

            energy_residual_wh = (
                float(result.total_energy_wh)
                - zone_total_energy_wh
            )

            record = {
                "step": step,
                "day": day,
                "hour": hour,
                "building_id": result.building_id,
                "dwelling_id": result.dwelling_id,

                "total_occupancy": total_occupancy,
                "private_zone_count": len(dwelling_zone_records),

                "heating_energy_wh": result.heating_energy_wh,
                "cooling_energy_wh": result.cooling_energy_wh,
                "lighting_energy_wh": result.lighting_energy_wh,
                "appliance_energy_wh": result.appliance_energy_wh,
                "total_energy_wh": result.total_energy_wh,

                "heating_delivered_energy_wh": result.heating_delivered_energy_wh,
                "cooling_delivered_energy_wh": result.cooling_delivered_energy_wh,
                "ventilation_fan_energy_wh": result.ventilation_fan_energy_wh,
                "hvac_delivered_energy_wh": result.hvac_delivered_energy_wh,
                "hvac_input_energy_wh": result.hvac_input_energy_wh,

                "zone_total_energy_wh": zone_total_energy_wh,
                "energy_balance_residual_wh": energy_residual_wh,
                "energy_balance_ok": abs(energy_residual_wh) <= 1e-6,
            }

            self._add_zone_physics_summary_to_record(
                target=record,
                records=dwelling_zone_records,
                dt_hours=dt_hours,
                prefix="",
            )

            records.append(record)

        return records

    def _make_building_record(
        self,
        step: Any,
        day: Any,
        hour: Any,
        building_energy_result: BuildingEnergyResult,
        zone_records: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        zone_records = zone_records or []

        private_zone_records = [
            record
            for record in zone_records
            if record.get("zone_scope") == "private"
        ]

        shared_zone_records = [
            record
            for record in zone_records
            if record.get("zone_scope") == "shared"
        ]

        total_occupancy = sum(
            int(record.get("number_of_people", 0))
            for record in zone_records
        )

        private_zone_energy_wh = self._summary_sum(
            private_zone_records,
            "total_energy_wh",
        )

        shared_zone_energy_wh = self._summary_sum(
            shared_zone_records,
            "total_energy_wh",
        )

        zone_total_energy_wh = self._summary_sum(
            zone_records,
            "total_energy_wh",
        )

        heating_energy_wh = self._summary_sum(
            zone_records,
            "heating_energy_wh",
        )

        cooling_energy_wh = self._summary_sum(
            zone_records,
            "cooling_energy_wh",
        )

        lighting_energy_wh = self._summary_sum(
            zone_records,
            "lighting_energy_wh",
        )

        appliance_energy_wh = self._summary_sum(
            zone_records,
            "appliance_energy_wh",
        )

        ventilation_fan_energy_wh = self._summary_sum(
            zone_records,
            "ventilation_fan_energy_wh",
        )

        hvac_delivered_energy_wh = self._summary_sum(
            zone_records,
            "hvac_delivered_energy_wh",
        )

        hvac_input_energy_wh = self._summary_sum(
            zone_records,
            "hvac_input_energy_wh",
        )

        heating_delivered_energy_wh = self._summary_sum(
            zone_records,
            "heating_delivered_energy_wh",
        )

        cooling_delivered_energy_wh = self._summary_sum(
            zone_records,
            "cooling_delivered_energy_wh",
        )

        building_energy_result_total_energy_wh = float(
            building_energy_result.total_energy_wh
        )

        zone_energy_balance_residual_wh = (
            building_energy_result_total_energy_wh
            - zone_total_energy_wh
        )

        record = {
            "step": step,
            "day": day,
            "hour": hour,
            "building_id": building_energy_result.building_id,

            "number_of_dwellings": len(self.building_model.dwellings),
            "number_of_zones": len(zone_records),
            "private_zone_count": len(private_zone_records),
            "shared_zone_count": len(shared_zone_records),
            "total_occupancy": total_occupancy,

            "private_zone_energy_wh": private_zone_energy_wh,
            "shared_zone_energy_wh": shared_zone_energy_wh,
            "zone_total_energy_wh": zone_total_energy_wh,

            # Building-row total is the actual sum of zone records.
            # The original BuildingEnergyResult total is preserved below.
            "heating_energy_wh": heating_energy_wh,
            "cooling_energy_wh": cooling_energy_wh,
            "lighting_energy_wh": lighting_energy_wh,
            "appliance_energy_wh": appliance_energy_wh,
            "shared_system_energy_wh": building_energy_result.shared_system_energy_wh,
            "total_energy_wh": zone_total_energy_wh,

            "heating_delivered_energy_wh": heating_delivered_energy_wh,
            "cooling_delivered_energy_wh": cooling_delivered_energy_wh,
            "ventilation_fan_energy_wh": ventilation_fan_energy_wh,
            "hvac_delivered_energy_wh": hvac_delivered_energy_wh,
            "hvac_input_energy_wh": hvac_input_energy_wh,

            "building_energy_result_total_energy_wh": building_energy_result_total_energy_wh,
            "building_zone_energy_balance_residual_wh": zone_energy_balance_residual_wh,
            "building_zone_energy_balance_ok": abs(zone_energy_balance_residual_wh) <= 1e-6,

            "record_level": "building_timestep",
            "diagnostic_output_mode": "standard",
        }

        self._add_zone_physics_summary_to_record(
            target=record,
            records=zone_records,
            dt_hours=0.0,
            prefix="",
        )

        record["private_mean_indoor_temp_c"] = self._summary_mean(
            private_zone_records,
            "indoor_temp_c",
        )
        record["shared_mean_indoor_temp_c"] = self._summary_mean(
            shared_zone_records,
            "indoor_temp_c",
        )

        record["private_total_energy_wh"] = private_zone_energy_wh
        record["shared_total_energy_wh"] = shared_zone_energy_wh

        return record
    # ============================================================
    # OBSERVATION OUTPUT
    # ============================================================

    def _make_updated_observation(
        self,
        previous_observation: Any,
        outdoor_temp_c: float,
        zone_control_commands: Optional[Dict[str, ZoneControlCommand]] = None,
    ) -> DwellingObservation:
        zone_observations = {}

        all_zone_models = self.building_model.all_zone_models()
        all_zone_states = self.building_model.all_zone_states()

        for zone_id, zone_state in all_zone_states.items():
            zone_model = all_zone_models[zone_id]

            command = None

            if zone_control_commands is not None:
                command = zone_control_commands.get(zone_id)

            previous_zone_observation = None

            if previous_observation is not None and hasattr(
                previous_observation,
                "get_zone",
            ):
                previous_zone_observation = previous_observation.get_zone(zone_id)

            heating_on = bool(
                _get_attr_or_key(
                    command,
                    "heating_on",
                    _get_attr_or_key(previous_zone_observation, "heating_on", False),
                )
            )

            cooling_on = bool(
                _get_attr_or_key(
                    command,
                    "cooling_on",
                    _get_attr_or_key(previous_zone_observation, "cooling_on", False),
                )
            )

            ventilation_flow_m3_h = float(
                _get_attr_or_key(command, "ventilation_flow_m3_h", 0.0)
            )

            mechanical_ventilation_on = ventilation_flow_m3_h > 0.0

            lights_on = bool(
                _get_attr_or_key(
                    command,
                    "lights_on",
                    _get_attr_or_key(previous_zone_observation, "lights_on", False),
                )
            )

            window_open = bool(
                _get_attr_or_key(
                    command,
                    "window_open",
                    _get_attr_or_key(previous_zone_observation, "window_open", False),
                )
            )

            curtain_open = bool(
                _get_attr_or_key(
                    command,
                    "curtain_open",
                    _get_attr_or_key(previous_zone_observation, "curtain_open", True),
                )
            )

            zone_observations[zone_id] = ZoneObservation(
                zone_id=zone_id,
                zone_name=zone_model.zone_name,
                indoor_temp=zone_state.indoor_temp_c,
                co2_ppm=zone_state.co2_ppm,
                indoor_daylight=zone_state.indoor_daylight,
                indoor_noise=zone_state.indoor_noise,
                indoor_relative_humidity_percent=_get_attr_or_key(
                    zone_state,
                    "indoor_relative_humidity_percent",
                    _get_attr_or_key(
                        previous_zone_observation,
                        "indoor_relative_humidity_percent",
                        None,
                    ),
                ),
                indoor_humidity_ratio_kg_kg=_get_attr_or_key(
                    zone_state,
                    "indoor_humidity_ratio_kg_kg",
                    _get_attr_or_key(
                        previous_zone_observation,
                        "indoor_humidity_ratio_kg_kg",
                        None,
                    ),
                ),
                heating_on=heating_on,
                cooling_on=cooling_on,
                mechanical_ventilation_on=mechanical_ventilation_on,
                lights_on=lights_on,
                window_open=window_open,
                curtain_open=curtain_open,
                occupied_person_ids=list(zone_state.occupied_person_ids),
                number_of_people=zone_state.number_of_people,
            )

        default_zone_id = self._default_observation_zone_id(
            zone_observations=zone_observations,
            previous_observation=previous_observation,
        )
        default_zone = zone_observations[default_zone_id]

        electricity_tariff = 0.25

        if previous_observation is not None:
            electricity_tariff = _get_attr_or_key(
                previous_observation,
                "electricity_tariff",
                electricity_tariff,
            )

        return DwellingObservation(
            indoor_temp=default_zone.indoor_temp,
            outdoor_temp=outdoor_temp_c,
            co2_ppm=default_zone.co2_ppm,
            indoor_daylight=default_zone.indoor_daylight,
            indoor_noise=default_zone.indoor_noise,
            indoor_relative_humidity_percent=default_zone.indoor_relative_humidity_percent,
            indoor_humidity_ratio_kg_kg=default_zone.indoor_humidity_ratio_kg_kg,
            electricity_tariff=electricity_tariff,
            default_zone_id=default_zone_id,
            zone_observations=zone_observations,
        )

    def _default_observation_zone_id(
        self,
        zone_observations: Dict[str, ZoneObservation],
        previous_observation: Any = None,
    ) -> str:
        previous_default = _get_attr_or_key(
            previous_observation,
            "default_zone_id",
            None,
        )

        for candidate in self._candidate_observation_zone_ids(previous_default):
            if candidate in zone_observations:
                return candidate

        preferred = [
            "dwelling_1_living_room",
            "living_room",
            "main_room",
        ]

        for zone_id in preferred:
            for candidate in self._candidate_observation_zone_ids(zone_id):
                if candidate in zone_observations:
                    return candidate

        for zone_id in zone_observations:
            return zone_id

        raise ValueError("No zone observations available.")

    @staticmethod
    def _candidate_observation_zone_ids(zone_id: Any) -> List[str]:
        if zone_id is None:
            return []

        value = str(zone_id)

        candidates = []

        def add(candidate):
            if candidate is None:
                return

            candidate = str(candidate)

            if candidate and candidate not in candidates:
                candidates.append(candidate)

        add(value)

        if value == "main_room":
            add("living_room")
            add("dwelling_1_living_room")

        if value == "living_room":
            add("dwelling_1_living_room")

        if value and not value.startswith("dwelling_") and value != "outside":
            add("dwelling_1_" + value)

        if value.startswith("dwelling_1_"):
            add(value[len("dwelling_1_"):])

        return candidates
        
    def _add_weather_diagnostics_to_record(
        self,
        record: Dict[str, Any],
        weather_state: Any,
        weather_source: str,
    ) -> None:
        record["weather_source"] = weather_source
        record["weather_outdoor_temperature_c"] = _get_attr_or_key(
            weather_state,
            "outdoor_temperature_c",
            None,
        )
        record["weather_outdoor_co2_ppm"] = _get_attr_or_key(
            weather_state,
            "outdoor_co2_ppm",
            None,
        )
        record["weather_wind_speed_m_s"] = _get_attr_or_key(
            weather_state,
            "wind_speed_m_s",
            None,
        )
        record["weather_wind_direction_deg"] = _get_attr_or_key(
            weather_state,
            "wind_direction_deg",
            None,
        )
        record["weather_direct_normal_radiation_w_m2"] = _get_attr_or_key(
            weather_state,
            "direct_normal_radiation_w_m2",
            None,
        )
        record["weather_diffuse_horizontal_radiation_w_m2"] = _get_attr_or_key(
            weather_state,
            "diffuse_horizontal_radiation_w_m2",
            None,
        )
        record["weather_global_horizontal_radiation_w_m2"] = _get_attr_or_key(
            weather_state,
            "global_horizontal_radiation_w_m2",
            None,
        )
        record["weather_outdoor_illuminance_lux"] = _get_attr_or_key(
            weather_state,
            "outdoor_illuminance_lux",
            None,
        )
        record["weather_relative_humidity_percent"] = _get_attr_or_key(
            weather_state,
            "relative_humidity_percent",
            None,
        )
        record["weather_atmospheric_pressure_pa"] = _get_attr_or_key(
            weather_state,
            "atmospheric_pressure_pa",
            None,
        )
        record["weather_sky_condition"] = _get_attr_or_key(
            weather_state,
            "sky_condition",
            None,
        )
    # ============================================================
    # OUTDOOR CONDITIONS
    # ============================================================

    def _get_outdoor_temp_c(
        self,
        performance_input: Any,
        observation: Any,
    ) -> float:
        weather_state = _get_attr_or_key(
            performance_input,
            "weather_state",
            None,
        )

        if weather_state is not None:
            value = _get_attr_or_key(
                weather_state,
                "outdoor_temperature_c",
                None,
            )

            if value is not None:
                return float(value)

        direct = _get_attr_or_key(performance_input, "outdoor_temp_c", None)

        if direct is not None:
            return float(direct)

        if observation is not None:
            value = _get_attr_or_key(observation, "outdoor_temp", None)

            if value is not None:
                return float(value)

        return 10.0

    def _make_weather_state_for_engine(
        self,
        performance_input: Any,
        observation: Any,
        outdoor_temp_c: float,
    ) -> Tuple[Any, str]:
        existing = _get_attr_or_key(performance_input, "weather_state", None)

        if existing is not None:
            return existing, WEATHER_SOURCE_EXPLICIT

        outdoor_co2_ppm = _get_attr_or_key(
            performance_input,
            "outdoor_co2_ppm",
            self.outdoor_co2_ppm,
        )

        step_datetime = self._make_synthetic_weather_datetime(
            performance_input=performance_input,
        )

        if observation is not None:
            observation_outdoor_temp = _get_attr_or_key(
                observation,
                "outdoor_temp",
                None,
            )

            if observation_outdoor_temp is not None:
                return (
                    WeatherState(
                        datetime=step_datetime,
                        outdoor_temperature_c=float(observation_outdoor_temp),
                        wind_speed_m_s=0.0,
                        wind_direction_deg=0.0,
                        direct_normal_radiation_w_m2=0.0,
                        diffuse_horizontal_radiation_w_m2=0.0,
                        global_horizontal_radiation_w_m2=0.0,
                        outdoor_illuminance_lux=0.0,
                        outdoor_co2_ppm=float(outdoor_co2_ppm),
                        outdoor_noise_db=45.0,
                        relative_humidity_percent=50.0,
                        atmospheric_pressure_pa=101325.0,
                        sky_condition="synthetic_observation",
                    ),
                    WEATHER_SOURCE_FROM_OBSERVATION,
                )

        return (
            WeatherState(
                datetime=step_datetime,
                outdoor_temperature_c=float(outdoor_temp_c),
                wind_speed_m_s=0.0,
                wind_direction_deg=0.0,
                direct_normal_radiation_w_m2=0.0,
                diffuse_horizontal_radiation_w_m2=0.0,
                global_horizontal_radiation_w_m2=0.0,
                outdoor_illuminance_lux=0.0,
                outdoor_co2_ppm=float(outdoor_co2_ppm),
                outdoor_noise_db=45.0,
                relative_humidity_percent=50.0,
                atmospheric_pressure_pa=101325.0,
                sky_condition="synthetic_default",
            ),
            WEATHER_SOURCE_DEFAULT_SYNTHETIC,
        )

    def _make_synthetic_weather_datetime(
        self,
        performance_input: Any,
    ) -> Any:
        existing_datetime = _get_attr_or_key(
            performance_input,
            "datetime",
            None,
        )

        if existing_datetime is not None:
            return existing_datetime

        base = datetime(2026, 1, 1, 0, 0, 0)

        day = _get_attr_or_key(
            performance_input,
            "day",
            0,
        )

        hour = _get_attr_or_key(
            performance_input,
            "hour",
            0.0,
        )

        try:
            day = int(day)
        except Exception:
            day = 0

        try:
            hour = float(hour)
        except Exception:
            hour = 0.0

        return base + timedelta(
            days=day,
            hours=hour,
        )
    
# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================
#
# Phase 17.1:
# BuildingPhysicsPerformanceModel is now the official public class.
# Keep the old name as an alias so old imports and Phase 16 tests do
# not break during the v0.3 -> v0.4 transition.

SimpleBuildingPerformanceModel = BuildingPhysicsPerformanceModel
# ============================================================
# UTILS
# ============================================================

def _get_attr_or_key(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(name, default)

    return getattr(obj, name, default)


def _safe_list(value: Any) -> List[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    return [value]


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))