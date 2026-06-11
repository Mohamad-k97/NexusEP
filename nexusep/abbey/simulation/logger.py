"""
ABBEY simulation logger.
"""

import json
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd

from nexusep.abbey.agents.location import OccupantLocation, SpaceAssignment
from nexusep.abbey.agents.states import (
    PersonState,
    DwellingObservation,
    SystemState,
    ExecutionState,
    SimulationClock,
)


class SimulationLogger:
    def __init__(self) -> None:
        self.records = []
        self.zone_records = []

    def record_step(
        self,
        clock: SimulationClock,
        person: PersonState,
        location: OccupantLocation,
        assignment: SpaceAssignment,
        observation: DwellingObservation,
        systems: SystemState,
        execution: ExecutionState,
        chunk_records: list,
        performance_log: Optional[dict] = None,
    ) -> None:
        performance_log = performance_log or {}

        total_action_energy_wh = sum(
            float(chunk.get("total_energy_wh", 0.0))
            for chunk in chunk_records
        )

        total_action_power_w = sum(
            float(chunk.get("total_power_w", 0.0))
            for chunk in chunk_records
        )

        record = {
            "step": clock.step,
            "day": clock.day,
            "hour": clock.hour,
            "dt_hours": clock.dt_hours,

            "occupant_id": location.occupant_id,
            "dwelling_id": location.dwelling_id,
            "current_space_id": location.current_space_id,
            "current_space_role": location.current_space_role,
            "location_is_home": location.is_home,
            "away_reason": location.away_reason,
            "minutes_since_last_space_change": location.minutes_since_last_space_change,

            "total_action_energy_wh": total_action_energy_wh,
            "total_action_power_w": total_action_power_w,
            "active_power_w": execution.active_power_w(),

            "foreground_actions": json.dumps(
                [a.to_dict() for a in execution.foreground_actions],
                ensure_ascii=False,
            ),
            "background_processes": json.dumps(
                [p.to_dict() for p in execution.background_processes],
                ensure_ascii=False,
            ),
            "action_cooldowns": json.dumps(
                execution.action_cooldowns,
                ensure_ascii=False,
            ),
            "chunk_records": json.dumps(chunk_records, ensure_ascii=False),
            "space_assignment": json.dumps(assignment.to_dict(), ensure_ascii=False),
            "performance_log": json.dumps(performance_log, ensure_ascii=False),
        }

        record.update(self._prefix_dict("person", person.to_dict()))
        record.update(self._prefix_dict("observation", observation.to_dict()))
        record.update(self._prefix_dict("systems", systems.to_dict()))

        self.records.append(record)

        self._record_zones(
            clock=clock,
            location=location,
            observation=observation,
            systems=systems,
        )

    def _record_zones(
        self,
        clock: SimulationClock,
        location: OccupantLocation,
        observation: DwellingObservation,
        systems: SystemState,
    ) -> None:
        for zone_id, zone in observation.zone_observations.items():
            occupied_person_ids = []
            zone_controls = systems.get_space_controls(zone_id)
            if location.is_home and location.current_space_id == zone_id:
                occupied_person_ids.append(location.occupant_id)
                
            self.zone_records.append(
                {
                    "step": clock.step,
                    "day": clock.day,
                    "hour": clock.hour,
                    "dt_hours": clock.dt_hours,

                    "zone_id": zone.zone_id,
                    "zone_name": zone.zone_name,

                    "indoor_temp": zone.indoor_temp,
                    "co2_ppm": zone.co2_ppm,
                    "indoor_daylight": zone.indoor_daylight,
                    "indoor_noise": zone.indoor_noise,

                    "heating_on": zone_controls.heating_on,
                    "cooling_on": zone_controls.cooling_on,
                    "lights_on": zone_controls.lights_on,
                    "window_open": zone_controls.window_open,
                    "curtain_closed": zone_controls.curtain_closed,
                    "blind_closed": zone_controls.blind_closed,

                    "occupied_person_ids": json.dumps(occupied_person_ids),
                    "number_of_people": len(occupied_person_ids),
                }
            )

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.records)

    def zones_to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.zone_records)

    def save_csv(self, path: Union[str, Path]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.to_dataframe().to_csv(path, index=False)

    def save_zone_csvs(self, folder: Union[str, Path]) -> None:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)

        df = self.zones_to_dataframe()

        if df.empty:
            return

        for zone_id, group in df.groupby("zone_id"):
            safe_zone_id = str(zone_id).replace("/", "_").replace("\\", "_")
            out = folder / f"{safe_zone_id}.csv"
            group.to_csv(out, index=False)

    @staticmethod
    def _prefix_dict(prefix: str, data: dict) -> dict:
        clean = {}

        for key, value in data.items():
            if isinstance(value, (dict, list)):
                clean[f"{prefix}_{key}"] = json.dumps(value, ensure_ascii=False)
            else:
                clean[f"{prefix}_{key}"] = value

        return clean