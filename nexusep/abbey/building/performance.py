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

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import copy

from nexusep.abbey.agents.states import DwellingObservation, ZoneObservation
from nexusep.abbey.building.model import BuildingModel, ZoneState, ZoneModel
from nexusep.abbey.building.systems import (
    ZoneSystemSpec,
    ZoneControlState,
    ZoneControlCommand,
    ZoneEnergyResult,
    DwellingEnergyResult,
    BuildingEnergyResult,
)
from nexusep.abbey.building.controllers import controller_for_control_state


@dataclass
class BuildingPerformanceStepResult:
    observation: DwellingObservation

    zone_records: List[Dict[str, Any]] = field(default_factory=list)
    dwelling_records: List[Dict[str, Any]] = field(default_factory=list)
    building_record: Dict[str, Any] = field(default_factory=dict)

    zone_energy_results: Dict[str, ZoneEnergyResult] = field(default_factory=dict)
    dwelling_energy_results: Dict[str, DwellingEnergyResult] = field(default_factory=dict)
    building_energy_result: Optional[BuildingEnergyResult] = None

    zone_control_commands: Dict[str, ZoneControlCommand] = field(default_factory=dict)


class SimpleBuildingPerformanceModel:
    """
    Dummy-simple building performance model.

    MVP scope:
        one building
        one dwelling
        one household

    Future-ready:
        multiple dwellings
        shared zones
        building-level systems
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

    def step(
        self,
        performance_input: Any,
        dt_minutes: float,
    ) -> BuildingPerformanceStepResult:
        dt_minutes = float(dt_minutes)
        dt_hours = dt_minutes / 60.0
        dt_seconds = dt_minutes * 60.0

        if dt_minutes <= 0:
            raise ValueError("dt_minutes must be positive.")

        observation = _get_attr_or_key(performance_input, "observation", None)
        locations = _get_attr_or_key(performance_input, "locations", {})
        people = _get_attr_or_key(performance_input, "people", {})
        chunk_records = _get_attr_or_key(performance_input, "chunk_records", [])
        action_energy_wh = _get_attr_or_key(performance_input, "action_energy_wh", {})

        day = _get_attr_or_key(performance_input, "day", None)
        hour = _get_attr_or_key(performance_input, "hour", None)
        step = _get_attr_or_key(performance_input, "step", None)

        outdoor_temp_c = self._get_outdoor_temp_c(
            performance_input=performance_input,
            observation=observation,
        )

        occupancy_by_zone = self._map_occupancy_by_zone(locations=locations)
        appliance_energy_by_zone = self._map_appliance_energy_by_zone(
            locations=locations,
            chunk_records=chunk_records,
            action_energy_wh=action_energy_wh,
            dt_hours=dt_hours,
        )

        zone_records = []
        zone_energy_results = {}
        zone_control_commands = {}

        all_zone_models = self.building_model.all_zone_models()

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

            appliance_energy_wh = appliance_energy_by_zone.get(zone_id, 0.0)

            new_temp_c = self._update_temperature(
                zone_model=zone_model,
                zone_state=occupied_state,
                system_spec=system_spec,
                command=command,
                outdoor_temp_c=outdoor_temp_c,
                appliance_energy_wh=appliance_energy_wh,
                dt_hours=dt_hours,
                dt_seconds=dt_seconds,
            )

            new_co2_ppm = self._update_co2(
                zone_model=zone_model,
                zone_state=occupied_state,
                command=command,
                dt_hours=dt_hours,
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
                dt_hours=dt_hours,
            )

            zone_energy_results[zone_id] = energy_result

            zone_records.append(
                self._make_zone_record(
                    step=step,
                    day=day,
                    hour=hour,
                    zone_model=zone_model,
                    zone_state=new_state,
                    command=command,
                    energy_result=energy_result,
                )
            )

        dwelling_energy_results = self._aggregate_dwelling_energy(zone_energy_results)
        building_energy_result = self._aggregate_building_energy(dwelling_energy_results)

        dwelling_records = self._make_dwelling_records(
            step=step,
            day=day,
            hour=hour,
            dwelling_energy_results=dwelling_energy_results,
        )

        building_record = self._make_building_record(
            step=step,
            day=day,
            hour=hour,
            building_energy_result=building_energy_result,
            zone_records=zone_records,
        )

        updated_observation = self._make_updated_observation(
            previous_observation=observation,
            outdoor_temp_c=outdoor_temp_c,
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
        energy_by_zone = {
            zone_id: 0.0
            for zone_id in self.building_model.all_zone_ids()
        }

        # Case 1: direct mapping {zone_id: energy_wh}
        if isinstance(action_energy_wh, dict):
            for key, value in action_energy_wh.items():
                if key in energy_by_zone:
                    energy_by_zone[key] += float(value)

        # Case 2: scalar action energy -> put into first occupied/default zone
        if isinstance(action_energy_wh, (int, float)):
            target_zone_id = self._default_energy_zone_id(locations)
            if target_zone_id in energy_by_zone:
                energy_by_zone[target_zone_id] += float(action_energy_wh)

        # Case 3: chunk records with actor_id + energy_wh
        chunk_records = _safe_list(chunk_records)

        for chunk in chunk_records:
            if not isinstance(chunk, dict):
                continue

            breakdown = chunk.get("power_breakdown", [])

            for item in _safe_list(breakdown):
                if not isinstance(item, dict):
                    continue

                actor_id = item.get("actor_id", "")
                energy_wh = float(item.get("energy_wh", 0.0))

                if energy_wh <= 0:
                    continue

                zone_id = item.get("target_space_id", "")

                if not zone_id:
                    zone_id = self._zone_for_actor(actor_id, locations)
                    
                    
                if zone_id in energy_by_zone:
                    energy_by_zone[zone_id] += energy_wh

        return energy_by_zone

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
    ) -> float:
        temp_c = float(zone_state.indoor_temp_c)

        effective_ua_w_per_k = float(zone_model.ua_w_per_k)

        if command.window_open:
            effective_ua_w_per_k *= 3.0

        outdoor_exchange_w = effective_ua_w_per_k * (outdoor_temp_c - temp_c)

        people_gain_w = (
            float(zone_state.number_of_people)
            * self.sensible_gain_per_person_w
        )

        appliance_gain_w = 0.0

        if dt_hours > 0:
            appliance_gain_w = float(appliance_energy_wh) / dt_hours

        heating_power_w = (
            float(command.heating_power_fraction)
            * float(system_spec.heating_capacity_w)
        )

        cooling_power_w = (
            float(command.cooling_power_fraction)
            * float(system_spec.cooling_capacity_w)
        )

        net_heat_flow_w = (
            outdoor_exchange_w
            + people_gain_w
            + appliance_gain_w
            + heating_power_w
            - cooling_power_w
        )

        delta_t_c = (
            net_heat_flow_w
            * dt_seconds
            / float(zone_model.thermal_capacity_j_per_k)
        )

        next_temp_c = temp_c + delta_t_c

        return _clip(next_temp_c, self.min_temp_c, self.max_temp_c)

    def _update_co2(
        self,
        zone_model: ZoneModel,
        zone_state: ZoneState,
        command: ZoneControlCommand,
        dt_hours: float,
    ) -> float:
        co2 = float(zone_state.co2_ppm)
        volume_m3 = float(zone_model.volume_m3)

        people_generation_m3_h = (
            float(zone_state.number_of_people)
            * self.co2_generation_per_person_m3_h
        )

        generation_ppm = (
            people_generation_m3_h
            / volume_m3
            * 1_000_000.0
            * dt_hours
        )

        ventilation_flow_m3_h = float(command.ventilation_flow_m3_h)

        if command.window_open:
            window_flow_m3_h = max(
                50.0,
                2.0 * volume_m3 * float(command.window_opening_fraction),
            )
            ventilation_flow_m3_h += window_flow_m3_h

        air_changes_per_h = ventilation_flow_m3_h / volume_m3

        removal_ppm = (
            max(0.0, co2 - self.outdoor_co2_ppm)
            * air_changes_per_h
            * dt_hours
        )

        next_co2 = co2 + generation_ppm - removal_ppm

        return _clip(next_co2, self.min_co2_ppm, self.max_co2_ppm)

    def _calculate_zone_energy(
        self,
        zone_model: ZoneModel,
        system_spec: ZoneSystemSpec,
        command: ZoneControlCommand,
        appliance_energy_wh: float,
        dt_hours: float,
    ) -> ZoneEnergyResult:
        heating_energy_wh = (
            float(command.heating_power_fraction)
            * float(system_spec.heating_capacity_w)
            * dt_hours
        )

        cooling_energy_wh = (
            float(command.cooling_power_fraction)
            * float(system_spec.cooling_capacity_w)
            * dt_hours
        )

        lighting_energy_wh = (
            float(command.lighting_power_w)
            * dt_hours
        )

        return ZoneEnergyResult(
            zone_id=zone_model.zone_id,
            dwelling_id=zone_model.dwelling_id,
            building_id=zone_model.building_id,
            heating_energy_wh=heating_energy_wh,
            cooling_energy_wh=cooling_energy_wh,
            lighting_energy_wh=lighting_energy_wh,
            appliance_energy_wh=float(appliance_energy_wh),
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

    def _make_zone_record(
        self,
        step: Any,
        day: Any,
        hour: Any,
        zone_model: ZoneModel,
        zone_state: ZoneState,
        command: ZoneControlCommand,
        energy_result: ZoneEnergyResult,
    ) -> Dict[str, Any]:
        return {
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
            "co2_ppm": zone_state.co2_ppm,
            "indoor_daylight": zone_state.indoor_daylight,
            "indoor_noise": zone_state.indoor_noise,
            "heating_on": command.heating_on,
            "cooling_on": command.cooling_on,
            "lights_on": command.lights_on,
            "window_open": command.window_open,
            "curtain_open": command.curtain_open,
            "heating_power_w": (
                command.heating_power_fraction
                * self._get_or_create_zone_system_spec(zone_model).heating_capacity_w
            ),
            "cooling_power_w": (
                command.cooling_power_fraction
                * self._get_or_create_zone_system_spec(zone_model).cooling_capacity_w
            ),
            "lighting_power_w": command.lighting_power_w,
            "ventilation_flow_m3_h": command.ventilation_flow_m3_h,
            "heating_energy_wh": energy_result.heating_energy_wh,
            "cooling_energy_wh": energy_result.cooling_energy_wh,
            "lighting_energy_wh": energy_result.lighting_energy_wh,
            "appliance_energy_wh": energy_result.appliance_energy_wh,
            "total_energy_wh": energy_result.total_energy_wh,
        }

    def _make_dwelling_records(
        self,
        step: Any,
        day: Any,
        hour: Any,
        dwelling_energy_results: Dict[str, DwellingEnergyResult],
    ) -> List[Dict[str, Any]]:
        records = []

        for dwelling_id, result in dwelling_energy_results.items():
            dwelling = self.building_model.dwellings[dwelling_id]

            total_occupancy = 0

            for zone_id in dwelling.zone_states:
                total_occupancy += dwelling.zone_states[zone_id].number_of_people

            records.append(
                {
                    "step": step,
                    "day": day,
                    "hour": hour,
                    "building_id": result.building_id,
                    "dwelling_id": result.dwelling_id,
                    "total_occupancy": total_occupancy,
                    "heating_energy_wh": result.heating_energy_wh,
                    "cooling_energy_wh": result.cooling_energy_wh,
                    "lighting_energy_wh": result.lighting_energy_wh,
                    "appliance_energy_wh": result.appliance_energy_wh,
                    "total_energy_wh": result.total_energy_wh,
                }
            )

        return records

    def _make_building_record(
        self,
        step: Any,
        day: Any,
        hour: Any,
        building_energy_result: BuildingEnergyResult,
        zone_records: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        total_occupancy = sum(
            int(record["number_of_people"])
            for record in zone_records
        )

        private_zone_energy_wh = sum(
            float(record.get("total_energy_wh", 0.0))
            for record in zone_records
            if record.get("zone_scope") == "private"
        )

        shared_zone_energy_wh = sum(
            float(record.get("total_energy_wh", 0.0))
            for record in zone_records
            if record.get("zone_scope") == "shared"
        )

        return {
            "step": step,
            "day": day,
            "hour": hour,
            "building_id": building_energy_result.building_id,
            "number_of_dwellings": len(self.building_model.dwellings),
            "total_occupancy": total_occupancy,
            "private_zone_energy_wh": private_zone_energy_wh,
            "shared_zone_energy_wh": shared_zone_energy_wh,
            "heating_energy_wh": building_energy_result.heating_energy_wh,
            "cooling_energy_wh": building_energy_result.cooling_energy_wh,
            "lighting_energy_wh": building_energy_result.lighting_energy_wh,
            "appliance_energy_wh": building_energy_result.appliance_energy_wh,
            "shared_system_energy_wh": building_energy_result.shared_system_energy_wh,
            "total_energy_wh": building_energy_result.total_energy_wh,
        }
    # ============================================================
    # OBSERVATION OUTPUT
    # ============================================================

    def _make_updated_observation(
        self,
        previous_observation: Any,
        outdoor_temp_c: float,
    ) -> DwellingObservation:
        zone_observations = {}

        all_zone_models = self.building_model.all_zone_models()
        all_zone_states = self.building_model.all_zone_states()

        for zone_id, zone_state in all_zone_states.items():
            zone_model = all_zone_models[zone_id]

            zone_observations[zone_id] = ZoneObservation(
                zone_id=zone_id,
                zone_name=zone_model.zone_name,
                indoor_temp=zone_state.indoor_temp_c,
                co2_ppm=zone_state.co2_ppm,
                indoor_daylight=zone_state.indoor_daylight,
                indoor_noise=zone_state.indoor_noise,
                occupied_person_ids=list(zone_state.occupied_person_ids),
                number_of_people=zone_state.number_of_people,
            )

        default_zone_id = self._default_observation_zone_id(zone_observations)

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
            electricity_tariff=electricity_tariff,
            default_zone_id=default_zone_id,
            zone_observations=zone_observations,
        )

    def _default_observation_zone_id(
        self,
        zone_observations: Dict[str, ZoneObservation],
    ) -> str:
        preferred = [
            "living_room",
            "dwelling_1_living_room",
        ]

        for zone_id in preferred:
            if zone_id in zone_observations:
                return zone_id

        for zone_id in zone_observations:
            return zone_id

        raise ValueError("No zone observations available.")

    # ============================================================
    # OUTDOOR CONDITIONS
    # ============================================================

    def _get_outdoor_temp_c(
        self,
        performance_input: Any,
        observation: Any,
    ) -> float:
        direct = _get_attr_or_key(performance_input, "outdoor_temp_c", None)

        if direct is not None:
            return float(direct)

        if observation is not None:
            value = _get_attr_or_key(observation, "outdoor_temp", None)

            if value is not None:
                return float(value)

        return 10.0


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