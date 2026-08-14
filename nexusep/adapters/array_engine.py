"""Canonical adapter for the experimental ABBEY array engine."""

from __future__ import annotations

import copy
from collections import defaultdict
from typing import Any, Literal, cast

from nexusep.abbey.arrays import schema as array_schema
from nexusep.abbey.arrays.decoder import (
    decode_person_state_records,
    decode_system_state_records,
    decode_time_state_record,
    decode_weather_state_record,
    decode_zone_state_records,
)
from nexusep.abbey.arrays.encoder import compile_simulation_to_arrays
from nexusep.abbey.arrays.timestep import run_array_timestep
from nexusep.abbey.building.physics.solar import (
    calculate_solar_position,
    calculate_surface_solar_irradiance,
)
from nexusep.adapters.common import (
    ADAPTER_CONTRACT_VERSION,
    BackendAdapterError,
    assemble_step_result,
)
from nexusep.schema.compiler import validate_compiled_graph
from nexusep.schema.outputs import (
    AppliedDefault,
    CanonicalWarning,
    CanonicalZoneStepResult,
    ValidationProvenance,
)
from nexusep.schema.scenario import CanonicalScenario
from nexusep.schema.timestep import (
    SimulationStepInput,
    validate_step_input_for_scenario,
)


def _required_float(value: float | None, label: str) -> float:
    if value is None:
        raise BackendAdapterError(f"validated canonical system is missing {label}")
    return float(value)


class ArrayEngineAdapter:
    """Own all array IDs, columns, aliases, and mutations behind one boundary."""

    engine_name: Literal["array"] = "array"
    engine_version = ADAPTER_CONTRACT_VERSION

    def __init__(
        self,
        scenario: CanonicalScenario,
        compiled_graph: dict[str, object],
    ) -> None:
        if not isinstance(scenario, CanonicalScenario):
            raise TypeError("scenario must be a validated CanonicalScenario")
        validate_compiled_graph(compiled_graph)
        if compiled_graph["scenario_id"] != scenario.scenario_id:
            raise ValueError("compiled graph belongs to a different scenario")
        if any(
            any(
                getattr(weather, field_name) is not None
                for field_name in (
                    "north_vertical_radiation_w_m2",
                    "east_vertical_radiation_w_m2",
                    "south_vertical_radiation_w_m2",
                    "west_vertical_radiation_w_m2",
                )
            )
            for weather in scenario.weather_series
        ):
            raise BackendAdapterError(
                "array engine does not yet support measured vertical-plane radiation"
            )
        if any(
            connection.get("exterior_solar_absorptance_fraction") is not None
            for connection in cast(
                list[dict[str, Any]], compiled_graph["connections"]
            )
        ):
            raise BackendAdapterError(
                "array engine does not yet support opaque sol-air boundary terms"
            )
        self.scenario = scenario
        self.compiled_graph = compiled_graph
        self.id_registry = copy.deepcopy(compiled_graph["id_registry"])
        self._carrier_by_zone = {
            zone.zone_id: f"array_adapter_system_{zone.zone_id}"
            for zone in sorted(
                scenario.building.dwelling.zones, key=lambda item: item.zone_id
            )
        }
        readable, defaults = self._compile_exact_readable_input()
        self.defaults_applied = tuple(defaults)
        self._base_state = compile_simulation_to_arrays(readable)
        self._verify_backend_registry()

    def conformance_snapshot(self) -> dict[str, object]:
        """Return a backend-decoded, side-effect-free contract snapshot."""

        state = copy.deepcopy(self._base_state)
        zones = decode_zone_state_records(state)
        people = decode_person_state_records(state)
        return {
            "engine_name": self.engine_name,
            "engine_version": self.engine_version,
            "scenario_id": self.scenario.scenario_id,
            "schema_version": self.scenario.schema_version,
            "graph_sha256": self.compiled_graph["graph_sha256"],
            "decoded_ids": {
                "building": [self.scenario.building.building_id],
                "dwelling": [self.scenario.building.dwelling.dwelling_id],
                "zone": sorted(item["zone_id"] for item in zones),
                "occupant": sorted(item["person_id"] for item in people),
            },
            "initial_zone_states": [
                {
                    "zone_id": item["zone_id"],
                    "air_temperature_c": item["air_temperature_C"],
                    "mean_radiant_temperature_c": item[
                        "mean_radiant_temperature_C"
                    ],
                    "relative_humidity_fraction": item["relative_humidity"],
                    "co2_ppm": item["co2_ppm"],
                }
                for item in sorted(zones, key=lambda value: value["zone_id"])
            ],
            "native_topology": {
                "representation": "compiled_surface_graph_to_array_coefficients",
                "compiled_connection_ids": sorted(
                    item["connection_id"]
                    for item in cast(
                        list[dict[str, Any]], self.compiled_graph["connections"]
                    )
                ),
                "zone_ids": sorted(item["zone_id"] for item in zones),
            },
        }

    def _compile_exact_readable_input(
        self,
    ) -> tuple[dict[str, object], list[AppliedDefault]]:
        building = self.scenario.building
        dwelling = building.dwelling
        defaults: list[AppliedDefault] = []
        zones = []
        systems = []
        graph_connections = cast(
            list[dict[str, Any]], self.compiled_graph["connections"]
        )
        for zone in sorted(dwelling.zones, key=lambda item: item.zone_id):
            owned_connections = [
                item
                for item in graph_connections
                if zone.zone_id in item["owner_zone_ids"]
            ]
            exterior_ua = sum(
                (
                    float(
                        item["gross_area_m2"]
                        if item["connection_type"] == "opening"
                        else item["net_opaque_area_m2"]
                    )
                    * float(item["thermal_transmittance_w_m2_k"])
                    + float(item.get("thermal_bridge_conductance_w_k", 0.0))
                )
                for item in owned_connections
                if item["boundary_type"] == "exterior"
            )
            internal_ua = sum(
                float(item["gross_area_m2"])
                * float(item["thermal_transmittance_w_m2_k"])
                + float(item.get("thermal_bridge_conductance_w_k", 0.0))
                for item in owned_connections
                if item["boundary_type"] == "interzone"
            )
            zone_heat_capacity_j_k = sum(
                float(item["heat_capacity_j_k"] or 0.0)
                for item in owned_connections
                if item["connection_type"] == "surface"
            )
            heating = next(
                item for item in zone.systems if item.system_type == "heating"
            )
            cooling = next(
                item for item in zone.systems if item.system_type == "cooling"
            )
            ventilation = next(
                item for item in zone.systems if item.system_type == "ventilation"
            )
            lighting = next(
                item for item in zone.systems if item.system_type == "lighting"
            )
            zones.append(
                {
                    "id": zone.zone_id,
                    "type": {"living": "living_room", "other": "main_room"}.get(
                        zone.zone_type, zone.zone_type
                    ),
                    "dwelling_id": dwelling.dwelling_id,
                    "building_id": building.building_id,
                    "floor_area_m2": zone.floor_area_m2,
                    "volume_m3": zone.volume_m3,
                    "height_m": zone.height_m,
                    "air_temperature_C": zone.initial_air_temperature_c,
                    "mean_radiant_temperature_C": zone.initial_mean_radiant_temperature_c,
                    "relative_humidity": zone.initial_relative_humidity_fraction,
                    "co2_ppm": zone.initial_co2_ppm,
                    "illuminance_lux": 0.0,
                    "noise_db": 35.0,
                    "solar_gain_W": 0.0,
                    "outdoor_airflow_m3_s": 0.0,
                    "interzone_airflow_m3_s": 0.0,
                    "infiltration_airflow_m3_s": (
                        zone.volume_m3
                        * zone.infiltration_air_changes_per_hour
                        / 3600.0
                    ),
                    "heat_capacity_J_K": zone_heat_capacity_j_k,
                    "ua_envelope_W_K": exterior_ua,
                    "ua_internal_W_K": internal_ua,
                    "min_comfort_temp_C": heating.heating_setpoint_c,
                    "max_comfort_temp_C": cooling.cooling_setpoint_c,
                    "min_illuminance_lux": 150.0,
                    "max_co2_ppm": 1200.0,
                    "max_noise_db": 55.0,
                }
            )
            systems.append(
                {
                    "id": self._carrier_by_zone[zone.zone_id],
                    "dwelling_id": dwelling.dwelling_id,
                    "zone_id": zone.zone_id,
                    "has_heating": True,
                    "has_cooling": True,
                    "has_window": any(
                        item["connection_type"] == "opening"
                        and float(item["openable_area_m2"] or 0.0) > 0.0
                        for item in owned_connections
                    ),
                    "has_lights": True,
                    "has_blinds": True,
                    "has_mech_ventilation": True,
                    "hvac_mode": "off",
                    "ventilation_mode": "off",
                    "heating_setpoint_C": heating.heating_setpoint_c,
                    "cooling_setpoint_C": cooling.cooling_setpoint_c,
                    "window_open_fraction": 0.0,
                    "light_on": False,
                    "lighting_power_W": 0.0,
                    "blind_closed_fraction": 0.0,
                    "mechanical_ventilation_flow_m3_s": 0.0,
                    "max_heating_power_W": _required_float(
                        heating.max_heating_power_w, "max_heating_power_w"
                    ),
                    "max_cooling_power_W": _required_float(
                        cooling.max_cooling_power_w, "max_cooling_power_w"
                    ),
                    "max_lighting_power_W": _required_float(
                        lighting.max_lighting_power_w, "max_lighting_power_w"
                    ),
                    "max_window_flow_m3_s": 0.0,
                    "max_mech_vent_flow_m3_s": _required_float(
                        ventilation.max_ventilation_volume_flow_m3_s,
                        "max_ventilation_volume_flow_m3_s",
                    ),
                    "default_heating_setpoint_C": heating.heating_setpoint_c,
                    "default_cooling_setpoint_C": cooling.cooling_setpoint_c,
                }
            )
            zone_path = f"/building/dwelling/zones/{zone.zone_id}"
            defaults.extend(
                (
                    AppliedDefault(
                        target_path=f"{zone_path}/array_engine/max_window_flow_m3_s",
                        value=0.0,
                        reason="canonical v1 does not define the array kernel pressure-flow coefficient",
                    ),
                    AppliedDefault(
                        target_path=f"{zone_path}/array_engine/ventilation_fan_power_w",
                        value=0.0,
                        reason="canonical v1 has no fan-power field; electrical fan power is explicitly zero",
                    ),
                )
            )

        occupants = []
        for occupant in sorted(
            self.scenario.occupants, key=lambda item: item.occupant_id
        ):
            first = next(
                item
                for item in occupant.location_schedule
                if item.start_timestep_index == 0
            )
            occupants.append(
                {
                    "id": occupant.occupant_id,
                    "dwelling_id": occupant.dwelling_id,
                    "home_zone_id": occupant.home_zone_id,
                    "sleep_zone_id": occupant.sleep_zone_id,
                    "work_zone_id": None,
                    "current_zone_id": first.zone_id,
                    "is_home": first.activity != "away",
                    "occupancy_state": (
                        "away"
                        if first.activity == "away"
                        else "home_sleeping"
                        if first.activity == "sleeping"
                        else "home_awake"
                    ),
                    "current_action_type": "none",
                    "current_action_id": None,
                    "action_time_left_min": 0.0,
                    "hunger": 0.0,
                    "fatigue": 0.0,
                    "dirty_clothes": 0.0,
                    "sickness": 0.0,
                    "laziness": 0.0,
                    "cold_sensitivity": 1.0,
                    "heat_sensitivity": 1.0,
                    "co2_sensitivity": 1.0,
                    "light_sensitivity": 1.0,
                    "noise_sensitivity": 1.0,
                    "action_friction": 1.0,
                    "metabolic_heat_W": occupant.sensible_heat_gain_w,
                    "co2_gain_kg_s": occupant.co2_generation_kg_s,
                    "moisture_gain_kg_s": occupant.moisture_generation_kg_s,
                    "has_job": False,
                    "usual_wake_minute": 420.0,
                    "usual_sleep_minute": 1380.0,
                    "work_start_minute": 540.0,
                    "work_end_minute": 1020.0,
                }
            )

        weather_series = []
        time_series = []
        for weather in self.scenario.weather_series:
            timestamp = weather.timestamp
            sky_temperature = (
                weather.sky_temperature_c
                if weather.sky_temperature_c is not None
                else weather.outdoor_temperature_c
            )
            if weather.sky_temperature_c is None:
                defaults.append(
                    AppliedDefault(
                        target_path=f"/weather_series/{weather.timestep_index}/sky_temperature_c",
                        value=sky_temperature,
                        reason="array kernel requires sky temperature; outdoor temperature is the documented neutral fallback",
                    )
                )
            weather_series.append(
                {
                    "outdoor_temperature_C": weather.outdoor_temperature_c,
                    "outdoor_relative_humidity": weather.relative_humidity_fraction,
                    "outdoor_co2_ppm": weather.outdoor_co2_ppm,
                    "ghi_W_m2": weather.global_horizontal_radiation_w_m2,
                    "dni_W_m2": weather.direct_normal_radiation_w_m2,
                    "dhi_W_m2": weather.diffuse_horizontal_radiation_w_m2,
                    "wind_speed_m_s": weather.wind_speed_m_s,
                    "wind_direction_deg": weather.wind_direction_deg,
                    "sky_temperature_C": sky_temperature,
                    "rain": bool(weather.rain),
                    "atmospheric_pressure_pa": weather.atmospheric_pressure_pa,
                }
            )
            local = timestamp
            time_series.append(
                {
                    "time_step_index": weather.timestep_index,
                    "elapsed_min": weather.timestep_index
                    * self.scenario.simulation_period.dt_minutes,
                    "minute_of_day": local.hour * 60 + local.minute,
                    "hour_of_day": local.hour + local.minute / 60.0,
                    "day_index": (
                        local.date()
                        - self.scenario.simulation_period.start_datetime.date()
                    ).days,
                    "day_of_week": local.weekday(),
                    "month": local.month,
                    "is_weekend": local.weekday() >= 5,
                }
            )

        first_zone = min(item.zone_id for item in dwelling.zones)
        readable: dict[str, object] = {
            "dt_minutes": self.scenario.simulation_period.dt_minutes,
            "n_timesteps": self.scenario.simulation_period.n_timesteps,
            "n_processes": max(1, len(occupants) * 2),
            "buildings": [
                {
                    "id": building.building_id,
                    "floor_area_m2": building.floor_area_m2,
                    "volume_m3": building.volume_m3,
                    "height_m": building.height_m,
                    "n_floors": building.n_floors,
                }
            ],
            "dwellings": [
                {
                    "id": dwelling.dwelling_id,
                    "building_id": building.building_id,
                    "floor_area_m2": dwelling.floor_area_m2,
                    "volume_m3": dwelling.volume_m3,
                }
            ],
            "zones": zones,
            "persons": occupants,
            "systems": systems,
            "actions": [
                {
                    "id": "array_adapter_idle",
                    "type": "idle",
                    "target_zone_id": first_zone,
                    "target_system_id": self._carrier_by_zone[first_zone],
                    "appliance_type": "none",
                    "duration_min": self.scenario.simulation_period.dt_minutes,
                    "requires_home": False,
                    "requires_awake": False,
                    "can_run_while_away": True,
                    "friction": 0.0,
                    "hunger_effect": 0.0,
                    "fatigue_effect": 0.0,
                    "dirty_clothes_effect": 0.0,
                    "sickness_effect": 0.0,
                    "power_W": 0.0,
                    "heat_gain_W": 0.0,
                    "co2_gain_kg_s": 0.0,
                    "moisture_gain_kg_s": 0.0,
                    "noise_gain_db": 0.0,
                    "process_type": "none",
                    "process_duration_min": 0.0,
                    "process_power_W": 0.0,
                    "process_heat_gain_W": 0.0,
                    "process_moisture_gain_kg_s": 0.0,
                    "base_score": 0.0,
                    "cooldown_min": 0.0,
                }
            ],
            "weather_series": weather_series,
            "time_series": time_series,
        }
        return readable, defaults

    def _verify_backend_registry(self) -> None:
        registry = self._base_state.metadata["registry"]
        id_registry = cast(dict[str, Any], self.compiled_graph["id_registry"])
        expected = cast(dict[str, Any], id_registry["entity_types"])
        comparisons = {
            "building": registry.building_name_to_id,
            "dwelling": registry.dwelling_name_to_id,
            "zone": registry.zone_name_to_id,
            "occupant": registry.person_name_to_id,
        }
        for entity_type, actual in comparisons.items():
            canonical = dict(
                zip(
                    expected[entity_type]["external_ids"],
                    expected[entity_type]["indices"],
                    strict=True,
                )
            )
            if actual != canonical:
                raise BackendAdapterError(
                    f"array {entity_type} registry differs from canonical deterministic registry"
                )

    def _apply_step(self, state, step_input: SimulationStepInput) -> None:
        if state.series is None:
            raise BackendAdapterError("array state has no canonical weather/time series")
        state.dynamic.weather_state[:] = state.series.weather_series[
            step_input.timestep_index, :
        ]
        state.dynamic.time_state[:] = state.series.time_series[
            step_input.timestep_index, :
        ]
        registry = state.metadata["registry"]
        occupants_by_zone: defaultdict[str, int] = defaultdict(int)
        for prior in step_input.prior_zone_states:
            zone_i = registry.zone_id(prior.zone_id)
            row = state.dynamic.zone_state[zone_i]
            row[array_schema.ZONE_AIR_TEMPERATURE_C] = prior.air_temperature_c
            row[array_schema.ZONE_MEAN_RADIANT_TEMPERATURE_C] = (
                prior.mean_radiant_temperature_c
            )
            row[array_schema.ZONE_RELATIVE_HUMIDITY] = prior.relative_humidity_fraction
            row[array_schema.ZONE_CO2_PPM] = prior.co2_ppm
        for occupant in step_input.occupant_states:
            person_i = registry.person_id(occupant.occupant_id)
            zone_i = registry.zone_id(occupant.zone_id)
            row = state.dynamic.person_state[person_i]
            row[array_schema.PERSON_CURRENT_ZONE_ID] = zone_i
            row[array_schema.PERSON_IS_HOME] = 1.0 if occupant.is_present else 0.0
            row[array_schema.PERSON_OCCUPANCY_STATE] = registry.occupancy_state_id(
                "away"
                if occupant.activity == "away"
                else "home_sleeping"
                if occupant.activity == "sleeping"
                else "home_awake"
            )
            if occupant.is_present:
                occupants_by_zone[occupant.zone_id] += 1
        for zone_id in self._carrier_by_zone:
            zone_i = registry.zone_id(zone_id)
            state.dynamic.zone_state[zone_i, array_schema.ZONE_OCCUPANT_COUNT] = (
                occupants_by_zone[zone_id]
            )
            state.dynamic.zone_state[zone_i, array_schema.ZONE_IS_OCCUPIED] = (
                1.0 if occupants_by_zone[zone_id] else 0.0
            )

        controls = {item.zone_id: item for item in step_input.control_commands}
        for zone_id, carrier in self._carrier_by_zone.items():
            system_i = registry.system_id(carrier)
            dynamic = state.dynamic.system_state[system_i]
            control = controls[zone_id]
            if (
                control.ventilation_exhaust_volume_flow_m3_s is not None
                and abs(
                    control.ventilation_exhaust_volume_flow_m3_s
                    - control.ventilation_volume_flow_m3_s
                )
                > 1.0e-12
            ):
                raise BackendAdapterError(
                    "array engine does not yet support distinct mechanical "
                    "supply and exhaust flows"
                )
            dynamic[array_schema.SYSTEM_HVAC_MODE] = registry.hvac_mode_id(
                "heating"
                if control.heating_on
                else "cooling"
                if control.cooling_on
                else "off"
            )
            dynamic[array_schema.SYSTEM_WINDOW_OPEN_FRACTION] = (
                control.window_opening_fraction
            )
            dynamic[array_schema.SYSTEM_WINDOW_STATE] = (
                array_schema.WINDOW_STATE_OPEN
                if control.window_opening_fraction > 0.0
                else array_schema.WINDOW_STATE_CLOSED
            )
            dynamic[array_schema.SYSTEM_LIGHT_STATE] = (
                array_schema.LIGHT_STATE_ON
                if control.lights_on
                else array_schema.LIGHT_STATE_OFF
            )
            dynamic[array_schema.SYSTEM_LIGHTING_POWER_W] = (
                control.lighting_power_w if control.lights_on else 0.0
            )
            dynamic[array_schema.SYSTEM_BLIND_CLOSED_FRACTION] = (
                1.0 - control.shading_open_fraction
            )
            dynamic[array_schema.SYSTEM_VENTILATION_MODE] = (
                registry.ventilation_mode_id(
                    "mechanical"
                    if control.ventilation_volume_flow_m3_s > 0.0
                    else "off"
                )
            )
            dynamic[array_schema.SYSTEM_MECHANICAL_VENTILATION_FLOW_M3_S] = (
                control.ventilation_volume_flow_m3_s
            )

    def _prescribed_hvac_power_by_system_w(
        self, state: Any, step_input: SimulationStepInput
    ) -> tuple[list[float], list[float]]:
        """Apply availability and command fractions without mutating static arrays."""

        heating_w = [0.0] * state.dynamic.system_state.shape[0]
        cooling_w = [0.0] * state.dynamic.system_state.shape[0]
        registry = state.metadata["registry"]
        availability = {item.system_id: item for item in step_input.system_availability}
        controls = {item.zone_id: item for item in step_input.control_commands}
        for zone in self.scenario.building.dwelling.zones:
            systems = {item.system_type: item for item in zone.systems}
            control = controls[zone.zone_id]
            carrier_i = registry.system_id(self._carrier_by_zone[zone.zone_id])
            heating = systems["heating"]
            cooling = systems["cooling"]
            heating_w[carrier_i] = (
                _required_float(heating.max_heating_power_w, "max_heating_power_w")
                * availability[heating.system_id].capacity_fraction
                * control.heating_power_fraction
                if control.heating_on
                else 0.0
            )
            cooling_w[carrier_i] = (
                _required_float(cooling.max_cooling_power_w, "max_cooling_power_w")
                * availability[cooling.system_id].capacity_fraction
                * control.cooling_power_fraction
                if control.cooling_on
                else 0.0
            )
        return heating_w, cooling_w

    def _control_trace_records(
        self, state: Any, step_input: SimulationStepInput
    ) -> dict[str, dict[str, Any]]:
        """Expose commands separately from immutable equipment capabilities."""

        records = {
            item["zone_id"]: item for item in decode_system_state_records(state)
        }
        controls = {item.zone_id: item for item in step_input.control_commands}
        availability = {item.system_id: item for item in step_input.system_availability}
        for zone in self.scenario.building.dwelling.zones:
            systems = {item.system_type: item for item in zone.systems}
            command = controls[zone.zone_id]
            record = records[zone.zone_id]
            record["command_heating_power_fraction"] = (
                command.heating_power_fraction
            )
            record["command_cooling_power_fraction"] = (
                command.cooling_power_fraction
            )
            record["heating_capacity_fraction"] = availability[
                systems["heating"].system_id
            ].capacity_fraction
            record["cooling_capacity_fraction"] = availability[
                systems["cooling"].system_id
            ].capacity_fraction
        return records

    def _solar_gain_by_array_zone_w(
        self, state: Any, step_input: SimulationStepInput
    ) -> list[float]:
        """Resolve canonical window irradiance before entering array kernels."""

        solar_position = calculate_solar_position(
            step_input.timestamp,
            latitude_deg=self.scenario.site.latitude_deg,
            longitude_deg=self.scenario.site.longitude_deg,
            elevation_m=self.scenario.site.elevation_m,
            atmospheric_pressure_pa=step_input.weather.atmospheric_pressure_pa,
            outdoor_temperature_c=step_input.weather.outdoor_temperature_c,
        )
        controls = {item.zone_id: item for item in step_input.control_commands}
        registry = state.metadata["registry"]
        gains = [0.0] * state.dynamic.zone_state.shape[0]
        connections = cast(list[dict[str, Any]], self.compiled_graph["connections"])
        for connection in connections:
            if connection["connection_type"] != "opening":
                continue
            zone_id = str(connection["source_node_id"])
            irradiance = calculate_surface_solar_irradiance(
                solar_zenith_deg=solar_position.zenith_deg,
                solar_azimuth_deg=solar_position.azimuth_deg,
                surface_tilt_deg=float(connection["tilt_deg"]),
                surface_azimuth_deg=float(connection["azimuth_deg"]),
                direct_normal_radiation_w_m2=(
                    step_input.weather.direct_normal_radiation_w_m2
                ),
                diffuse_horizontal_radiation_w_m2=(
                    step_input.weather.diffuse_horizontal_radiation_w_m2
                ),
                global_horizontal_radiation_w_m2=(
                    step_input.weather.global_horizontal_radiation_w_m2
                ),
                ground_albedo_fraction=(
                    self.scenario.site.ground_albedo_fraction
                ),
            )
            gains[registry.zone_id(zone_id)] += irradiance.transmitted_gain_w(
                area_m2=float(connection["gross_area_m2"]),
                solar_transmittance_fraction=float(
                    connection["solar_transmittance_fraction"]
                ),
                unshaded_fraction=(
                    controls[zone_id].shading_open_fraction
                    * float(connection.get("solar_shading_factor", 1.0))
                ),
            )
        return gains

    def run_step(self, step_input: SimulationStepInput, *, include_debug: bool = False):
        validate_step_input_for_scenario(step_input, self.scenario, self.compiled_graph)
        if step_input.external_boundary_states:
            raise BackendAdapterError(
                "array adapter cannot yet represent named non-weather thermal boundaries"
            )
        if step_input.opening_control_commands:
            raise BackendAdapterError(
                "array adapter cannot yet represent per-opening controls"
            )
        if step_input.interzone_opening_controls:
            raise BackendAdapterError(
                "array adapter cannot yet represent dynamic interzone openings"
            )
        if any(
            item.heating_convective_fraction != 1.0
            or item.cooling_convective_fraction != 1.0
            or item.ventilation_supply_temperature_c is not None
            for item in step_input.control_commands
        ):
            raise BackendAdapterError(
                "array adapter cannot yet represent non-convective HVAC or "
                "non-outdoor ventilation supply temperature"
            )
        if step_input.internal_gains:
            raise BackendAdapterError(
                "array adapter cannot yet inject canonical non-occupant internal gains"
            )
        if step_input.action_events:
            raise BackendAdapterError(
                "array adapter cannot yet apply externally supplied action events"
            )
        state = copy.deepcopy(self._base_state)
        self._apply_step(state, step_input)
        prescribed_heating_power_by_system_w, prescribed_cooling_power_by_system_w = (
            self._prescribed_hvac_power_by_system_w(state, step_input)
        )
        for system_i, (heating_w, cooling_w) in enumerate(
            zip(
                prescribed_heating_power_by_system_w,
                prescribed_cooling_power_by_system_w,
                strict=True,
            )
        ):
            state.dynamic.system_state[
                system_i, array_schema.SYSTEM_HEATING_POWER_W
            ] = heating_w
            state.dynamic.system_state[
                system_i, array_schema.SYSTEM_COOLING_POWER_W
            ] = cooling_w
        encoded_trace = {
            "timestamp": step_input.timestamp.isoformat(),
            "time_index": decode_time_state_record(state)["time_step_index"],
            "dt_minutes": step_input.dt_minutes,
            "weather": decode_weather_state_record(state),
            "controls": self._control_trace_records(state, step_input),
            "occupants": sorted(
                decode_person_state_records(state), key=lambda item: item["person_id"]
            ),
            "graph_sha256": self.compiled_graph["graph_sha256"],
        }
        prescribed_solar_gain_by_zone_w = self._solar_gain_by_array_zone_w(
            state, step_input
        )
        state, _, _, _ = run_array_timestep(
            state=state,
            time_index=step_input.timestep_index,
            dt_minutes=step_input.dt_minutes,
            logs=None,
            airflow_link_array=None,
            acoustic_link_array=None,
            zone_noise_source_array=None,
            outdoor_noise_db=step_input.weather.outdoor_noise_db,
            enforce_work_schedule=False,
            run_acoustics=False,
            prescribed_solar_gain_by_zone_w=prescribed_solar_gain_by_zone_w,
            prescribed_heating_power_by_system_w=(
                prescribed_heating_power_by_system_w
            ),
            prescribed_cooling_power_by_system_w=(
                prescribed_cooling_power_by_system_w
            ),
        )
        zone_records = decode_zone_state_records(state)
        system_records = decode_system_state_records(state)
        zone_by_id = {item["zone_id"]: item for item in zone_records}
        system_by_zone = {item["zone_id"]: item for item in system_records}
        controls = {item.zone_id: item for item in step_input.control_commands}
        canonical_zones = {
            item.zone_id: item for item in self.scenario.building.dwelling.zones
        }
        occupancy: defaultdict[str, int] = defaultdict(int)
        for occupant in step_input.occupant_states:
            if occupant.is_present:
                occupancy[occupant.zone_id] += 1
        rows = []
        for zone_id in sorted(zone_by_id):
            zone = zone_by_id[zone_id]
            system = system_by_zone[zone_id]
            canonical_systems = {
                item.system_type: item for item in canonical_zones[zone_id].systems
            }
            heating = float(system["heating_power_W"])
            cooling = float(system["cooling_power_W"])
            lighting = float(system["lighting_power_W"])
            heating_efficiency = _required_float(
                canonical_systems["heating"].heating_efficiency_fraction,
                "heating_efficiency_fraction",
            )
            cooling_cop = _required_float(
                canonical_systems["cooling"].cooling_cop, "cooling_cop"
            )
            total = heating / heating_efficiency + cooling / cooling_cop + lighting
            rows.append(
                CanonicalZoneStepResult(
                    scenario_id=self.scenario.scenario_id,
                    run_id=step_input.run_context.run_id,
                    building_id=self.scenario.building.building_id,
                    dwelling_id=self.scenario.building.dwelling.dwelling_id,
                    zone_id=zone_id,
                    timestamp=step_input.timestamp,
                    timestep_index=step_input.timestep_index,
                    air_temperature_c=zone["air_temperature_C"],
                    relative_humidity_fraction=zone["relative_humidity"],
                    co2_ppm=zone["co2_ppm"],
                    occupancy_count=occupancy[zone_id],
                    heating_power_w=heating,
                    cooling_power_w=cooling,
                    ventilation_power_w=0.0,
                    lighting_power_w=lighting,
                    total_electrical_power_w=total,
                    engine_name=self.engine_name,
                    engine_version=self.engine_version,
                    engine_status="completed_with_warnings",
                    fallback_used=False,
                    fallback_reason=None,
                )
            )
        return assemble_step_result(
            scenario=self.scenario,
            step_input=step_input,
            zones=rows,
            warnings=(
                CanonicalWarning(
                    code="array_engine_experimental_topology",
                    message="array v1 uses compiled UA values but has no canonical surface-graph kernel",
                    entity_id=None,
                ),
                CanonicalWarning(
                    code="array_engine_explicit_zero_fan_power",
                    message="ventilation electrical power is zero because canonical v1 has no fan-power field",
                    entity_id=None,
                ),
            ),
            provenance=(
                ValidationProvenance(
                    check="canonical_array_id_registry",
                    status="passed",
                    detail="building, dwelling, zone, and occupant array indices equal the canonical registry",
                ),
                ValidationProvenance(
                    check="decoded_external_ids",
                    status="passed",
                    detail="all required output entity IDs were decoded to original strings",
                ),
                ValidationProvenance(
                    check="array_mutation_boundary",
                    status="passed",
                    detail="array columns and mutations remained inside ArrayEngineAdapter",
                ),
            ),
            defaults=self.defaults_applied,
            debug_fields=(
                {
                    "backend_system_carriers": dict(self._carrier_by_zone),
                    "zone_records": zone_records,
                    "system_records": system_records,
                    "conservation_residuals": {
                        "thermal_balance_residual_w": float(
                            state.dynamic.physics_result[
                                :,
                                array_schema.PHYSICS_THERMAL_BALANCE_RESIDUAL_W,
                            ].sum()
                        ),
                        "moisture_balance_residual_kg_s": float(
                            state.dynamic.physics_result[
                                :,
                                array_schema.PHYSICS_MOISTURE_BALANCE_RESIDUAL_KG_S,
                            ].sum()
                        ),
                        "co2_mass_balance_residual_kg_s": float(
                            state.dynamic.physics_result[
                                :,
                                array_schema.PHYSICS_CO2_BALANCE_RESIDUAL_KG_S,
                            ].sum()
                        ),
                    },
                    "control_commands": {
                        key: value.model_dump(mode="json")
                        for key, value in controls.items()
                    },
                    "step_trace": encoded_trace,
                    "next_prior_zone_states": [
                        {
                            "zone_id": item["zone_id"],
                            "air_temperature_c": item["air_temperature_C"],
                            "mean_radiant_temperature_c": item[
                                "mean_radiant_temperature_C"
                            ],
                            "relative_humidity_fraction": item[
                                "relative_humidity"
                            ],
                            "co2_ppm": item["co2_ppm"],
                        }
                        for item in sorted(
                            zone_records, key=lambda value: value["zone_id"]
                        )
                    ],
                }
                if include_debug
                else None
            ),
        )


__all__ = ["ArrayEngineAdapter"]
