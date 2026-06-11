"""
Dummy building-performance model for ABBEY v0.1.

This is temporary.
Later replace with real thermal/daylight/CO2/acoustic/HVAC simulation.
"""

import math
from dataclasses import dataclass
from typing import Any, Dict

from nexusep.abbey.agents.states import DwellingObservation
from nexusep.building_performance.interface import (
    PerformanceInput,
    PerformanceOutput,
)


@dataclass 
class DummyBuildingPerformanceModel:
    """
    Minimal building-performance model.

    Calculates:
        indoor temperature
        CO2
        daylight proxy
        noise proxy
        electricity tariff

    This is only for testing ABBEY logic.
    """

    outdoor_co2_ppm: float = 420.0
    occupied_co2_gain_ppm_per_h: float = 180.0
    natural_ventilation_rate_per_h: float = 1.20
    mechanical_ventilation_rate_per_h: float = 0.35

    heat_loss_rate_per_h: float = 0.12
    window_extra_loss_rate_per_h: float = 0.35
    heating_gain_c_per_h: float = 2.50
    internal_gain_c_per_kwh: float = 0.15

    night_noise: float = 0.15
    day_noise: float = 0.35
    open_window_noise_addition: float = 0.25
    
    def _make_zone_observations(
        self,
        previous_observation,
        indoor_temp,
        co2_ppm,
        daylight,
        noise,
        occupied_zone_id,
        person_is_home,
        systems,
    ):
        from nexusep.abbey.agents.states import ZoneObservation
    
        if previous_observation.zone_observations:
            zone_ids = list(previous_observation.zone_observations.keys())
        else:
            zone_ids = ["main_room"]
    
        zone_observations = {}
    
        for zone_id in zone_ids:
            zone_controls = systems.get_space_controls(zone_id)
            temp_offset = 0.0
            daylight_factor = 1.0
            noise_offset = 0.0
    
            if "bedroom" in zone_id:
                temp_offset = -0.3
                daylight_factor = 0.75
    
            if zone_id == "office":
                temp_offset = 0.2
                daylight_factor = 0.9
    
            if zone_id == "kitchen":
                temp_offset = 0.4
                daylight_factor = 0.8
    
            if zone_id == "bathroom":
                temp_offset = 0.6
                daylight_factor = 0.35
    
            if zone_id == "laundry":
                temp_offset = 0.2
                daylight_factor = 0.25
                noise_offset = 0.15
    
            if zone_id == "entrance":
                temp_offset = -0.5
                daylight_factor = 0.4
    
            occupied = person_is_home and zone_id == occupied_zone_id
    
            zone_co2 = co2_ppm
            if not occupied:
                zone_co2 = max(420.0, co2_ppm - 150.0)
    
            occupied_person_ids = ["person_1"] if occupied else []
            
            zone_observations[zone_id] = ZoneObservation(
                zone_id=zone_id,
                zone_name=zone_id,
                indoor_temp=indoor_temp + temp_offset,
                co2_ppm=zone_co2,
                indoor_daylight=max(0.0, min(1.0, daylight * daylight_factor)),
                indoor_noise=max(0.0, min(1.0, noise + noise_offset)),
            
                heating_on=zone_controls.heating_on,
                cooling_on=zone_controls.cooling_on,
                lights_on=zone_controls.lights_on,
                window_open=zone_controls.window_open,
            
                occupied_person_ids=occupied_person_ids,
                number_of_people=len(occupied_person_ids),
            )
    
        return zone_observations

    def step(
        self,
        previous_observation: DwellingObservation,
        performance_input: PerformanceInput,
    ) -> PerformanceOutput:
        systems = performance_input.systems
        clock = performance_input.clock
        dt = clock.dt_hours

        action_energy_wh = self._total_action_energy_wh(
            performance_input.chunk_records
        )

        outdoor_temp = self._outdoor_temperature(clock.hour)
        tariff = self._tariff(clock.hour)
        daylight = self._daylight(clock.hour, systems.curtain_closed, systems.blind_closed)
        noise = self._indoor_noise(clock.hour, systems.window_open)

        indoor_temp = self._update_temperature(
            previous_temp=previous_observation.indoor_temp,
            outdoor_temp=outdoor_temp,
            systems=systems,
            action_energy_wh=action_energy_wh,
            dt_hours=dt,
        )

        co2_ppm = self._update_co2(
            previous_co2=previous_observation.co2_ppm,
            systems=systems,
            person_home=performance_input.person_is_home,
            dt_hours=dt,
        )

        zone_observations = self._make_zone_observations(
            previous_observation=previous_observation,
            indoor_temp=indoor_temp,
            co2_ppm=co2_ppm,
            daylight=daylight,
            noise=noise,
            occupied_zone_id=performance_input.person_current_zone_id,
            person_is_home=performance_input.person_is_home,
            systems=systems,
        )
        
        observation = DwellingObservation(
            indoor_temp=indoor_temp,
            outdoor_temp=outdoor_temp,
            co2_ppm=co2_ppm,
            indoor_daylight=daylight,
            indoor_noise=noise,
            electricity_tariff=tariff,
            default_zone_id=previous_observation.default_zone_id,
            zone_observations=zone_observations,
        )

        log: Dict[str, Any] = {
            "action_energy_wh": action_energy_wh,
            "outdoor_temp": outdoor_temp,
            "tariff": tariff,
            "dummy_model": True,
        }


        return PerformanceOutput(
            observation=observation,
            performance_log=log,
        )

    def _total_action_energy_wh(
        self,
        chunk_records: list[dict[str, Any]],
    ) -> float:
        return sum(float(row["total_energy_wh"]) for row in chunk_records)

    def _outdoor_temperature(self, hour: float) -> float:
        return 10.0 + 5.0 * math.sin(2.0 * math.pi * (hour - 8.0) / 24.0)

    def _tariff(self, hour: float) -> float:
        if 18.0 <= hour <= 22.0:
            return 0.38
        if 0.0 <= hour <= 6.0:
            return 0.16
        return 0.25

    def _daylight(
        self,
        hour: float,
        curtain_closed: bool,
        blind_closed: bool,
    ) -> float:
        if hour < 7.0 or hour > 19.0:
            daylight = 0.0
        else:
            daylight = max(
                0.0,
                math.sin(math.pi * (hour - 7.0) / 12.0),
            )

        if curtain_closed:
            daylight *= 0.25

        if blind_closed:
            daylight *= 0.40

        return max(0.0, min(1.0, daylight))

    def _indoor_noise(
        self,
        hour: float,
        window_open: bool,
    ) -> float:
        if 23.0 <= hour or hour <= 6.0:
            noise = self.night_noise
        else:
            noise = self.day_noise

        if window_open:
            noise += self.open_window_noise_addition

        return max(0.0, min(1.0, noise))

    def _update_temperature(
        self,
        previous_temp: float,
        outdoor_temp: float,
        systems,
        action_energy_wh: float,
        dt_hours: float,
    ) -> float:
        loss_rate = self.heat_loss_rate_per_h

        if systems.window_open:
            loss_rate += self.window_extra_loss_rate_per_h

        drift = loss_rate * (outdoor_temp - previous_temp)
        heating = self.heating_gain_c_per_h if systems.heating_on else 0.0
        internal_gain = (action_energy_wh / 1000.0) * self.internal_gain_c_per_kwh

        return previous_temp + dt_hours * (drift + heating) + internal_gain

    def _update_co2(
        self,
        previous_co2: float,
        systems,
        person_home: bool,
        dt_hours: float,
    ) -> float:
        generation = self.occupied_co2_gain_ppm_per_h if person_home else 0.0

        ventilation_rate = 0.0

        if systems.window_open:
            ventilation_rate += self.natural_ventilation_rate_per_h

        if systems.mechanical_ventilation_on:
            ventilation_rate += self.mechanical_ventilation_rate_per_h

        removal = ventilation_rate * (previous_co2 - self.outdoor_co2_ppm)

        return previous_co2 + dt_hours * (generation - removal)