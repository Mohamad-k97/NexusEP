"""Canonical adapter for the object/reference-candidate physics engine."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal, cast

from nexusep.abbey.building.model import BuildingModel, DwellingModel, ZoneModel
from nexusep.abbey.building.physics.engine import (
    BuildingPhysicsStepInput,
    run_building_physics_step,
)
from nexusep.abbey.building.physics.graph import (
    BoundaryConnection,
    BuildingPhysicsGraph,
    ZoneConnection,
)
from nexusep.abbey.building.physics.internal_sources import (
    BuildingInternalSourceResult,
    InternalSourceRecord,
)
from nexusep.abbey.building.physics.solar import calculate_solar_position
from nexusep.abbey.building.physics.weather import WeatherState as ObjectWeatherState
from nexusep.abbey.building.systems import (
    ZoneControlCommand as ObjectZoneControlCommand,
)
from nexusep.abbey.building.systems import (
    ZoneSystemSpec,
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
    InternalGain,
    SimulationStepInput,
    validate_step_input_for_scenario,
)

CO2_DENSITY_KG_M3 = 1.842


def _required_float(value: float | None, label: str) -> float:
    if value is None:
        raise BackendAdapterError(f"validated canonical system is missing {label}")
    return float(value)


class ObjectEngineAdapter:
    """Compile canonical v1 data into existing ABBEY object models."""

    engine_name: Literal["object"] = "object"
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
        self.scenario = scenario
        self.compiled_graph = compiled_graph
        self.defaults_applied: tuple[AppliedDefault, ...] = ()
        self.building_model, defaults = self._compile_building_model()
        self.physics_graph = self._compile_physics_graph()
        self.defaults_applied = tuple(defaults)

    def conformance_snapshot(self) -> dict[str, object]:
        """Return a backend-decoded, side-effect-free contract snapshot."""

        zone_states = []
        for zone_id in sorted(self.building_model.all_zone_ids()):
            state = self.building_model.get_zone_state(zone_id)
            zone_states.append(
                {
                    "zone_id": zone_id,
                    "air_temperature_c": state.indoor_temp_c,
                    "mean_radiant_temperature_c": state.indoor_mass_temp_c,
                    "relative_humidity_fraction": (
                        (state.indoor_relative_humidity_percent or 0.0) / 100.0
                    ),
                    "co2_ppm": state.co2_ppm,
                }
            )
        return {
            "engine_name": self.engine_name,
            "engine_version": self.engine_version,
            "scenario_id": self.scenario.scenario_id,
            "schema_version": self.scenario.schema_version,
            "graph_sha256": self.compiled_graph["graph_sha256"],
            "decoded_ids": {
                "building": [self.building_model.building_id],
                "dwelling": sorted(self.building_model.dwellings),
                "zone": sorted(self.building_model.all_zone_ids()),
                "occupant": sorted(item.occupant_id for item in self.scenario.occupants),
            },
            "initial_zone_states": zone_states,
            "native_topology": {
                "compiled_connection_ids": sorted(
                    item["connection_id"]
                    for item in cast(
                        list[dict[str, Any]], self.compiled_graph["connections"]
                    )
                ),
                "zone_connection_ids": sorted(self.physics_graph.zone_connections),
                "boundary_connection_ids": sorted(
                    self.physics_graph.boundary_connections
                ),
            },
        }

    def _compile_building_model(self) -> tuple[BuildingModel, list[AppliedDefault]]:
        canonical_building = self.scenario.building
        canonical_dwelling = canonical_building.dwelling
        zone_models: dict[str, ZoneModel] = {}
        defaults: list[AppliedDefault] = []

        for zone in sorted(canonical_dwelling.zones, key=lambda item: item.zone_id):
            exterior = [
                item for item in zone.surfaces if item.boundary_type == "exterior"
            ]
            interzone = [
                item for item in zone.surfaces if item.boundary_type == "interzone"
            ]
            opaque_areas: list[tuple[float, float]] = []
            window_areas: list[tuple[float, float]] = []
            for surface in exterior:
                opening_area = sum(item.area_m2 for item in surface.openings)
                opaque_areas.append(
                    (
                        surface.area_m2 - opening_area,
                        surface.thermal_transmittance_w_m2_k,
                    )
                )
                window_areas.extend(
                    (item.area_m2, item.thermal_transmittance_w_m2_k)
                    for item in surface.openings
                )
            external_area = sum(area for area, _ in opaque_areas)
            ua_w_k = sum(
                area * u_value for area, u_value in opaque_areas + window_areas
            )
            weighted_external_u = (
                sum(area * u_value for area, u_value in opaque_areas) / external_area
                if external_area > 0.0
                else 0.0
            )
            systems = {item.system_type: item for item in zone.systems}
            ventilation = systems.get("ventilation")
            zone_path = f"/building/dwelling/zones/{zone.zone_id}"
            defaults.extend(
                (
                    AppliedDefault(
                        target_path=f"{zone_path}/object_engine/default_infiltration_ach",
                        value=0.0,
                        reason="canonical v1 has no infiltration input; zero prevents hidden airflow",
                    ),
                    AppliedDefault(
                        target_path=f"{zone_path}/object_engine/ventilation_fan_power_w",
                        value=0.0,
                        reason="canonical v1 has no fan-power field; electrical fan power is explicitly zero",
                    ),
                    AppliedDefault(
                        target_path=f"{zone_path}/object_engine/thermal_mass_class",
                        value="medium",
                        reason="object-engine compatibility field; surface heat capacities remain authoritative",
                    ),
                )
            )
            zone_models[zone.zone_id] = ZoneModel(
                zone_id=zone.zone_id,
                zone_name=zone.zone_id,
                dwelling_id=canonical_dwelling.dwelling_id,
                building_id=canonical_building.building_id,
                zone_scope="private",
                zone_use={"living": "living_room"}.get(zone.zone_type, zone.zone_type),
                floor_area_m2=zone.floor_area_m2,
                height_m=zone.height_m,
                volume_m3=zone.volume_m3,
                floor_level=0,
                is_conditioned=True,
                is_occupied_space=True,
                centroid_x=None,
                centroid_y=None,
                geometry_source="canonical_scenario_v1",
                ua_w_per_k=ua_w_k,
                thermal_envelope_model="graph_boundaries",
                envelope_provenance="pending_canonical_graph_compilation",
                thermal_capacity_j_per_k=sum(
                    item.heat_capacity_j_k for item in zone.surfaces
                ),
                initial_temp_c=zone.initial_air_temperature_c,
                initial_co2_ppm=zone.initial_co2_ppm,
                thermal_mass_class="medium",
                internal_heat_capacity_j_k=sum(
                    item.heat_capacity_j_k for item in zone.surfaces
                ),
                air_heat_capacity_j_k=zone.volume_m3 * 1.2 * 1005.0,
                external_wall_area_m2=external_area,
                internal_wall_area_m2=sum(item.area_m2 for item in interzone),
                floor_area_to_other_zone_m2=0.0,
                ceiling_area_to_other_zone_m2=0.0,
                u_value_external_wall_w_m2k=weighted_external_u,
                u_value_internal_wall_w_m2k=(
                    sum(
                        item.area_m2 * item.thermal_transmittance_w_m2_k
                        for item in interzone
                    )
                    / sum(item.area_m2 for item in interzone)
                    if interzone
                    else 0.0
                ),
                u_value_floor_w_m2k=0.0,
                u_value_ceiling_w_m2k=0.0,
                thermal_bridge_factor=1.0,
                initial_air_temperature_c=zone.initial_air_temperature_c,
                initial_mass_temperature_c=zone.initial_mean_radiant_temperature_c,
                air_volume_m3=zone.volume_m3,
                default_infiltration_ach=0.0,
                mechanical_ventilation_available=ventilation is not None,
                mechanical_ventilation_flow_m3_h=(
                    _required_float(
                        ventilation.max_ventilation_volume_flow_m3_s,
                        "max_ventilation_volume_flow_m3_s",
                    )
                    * 3600.0
                    if ventilation is not None
                    else 0.0
                ),
                interzone_airflow_base_m3_h=0.0,
                co2_initial_ppm=zone.initial_co2_ppm,
                co2_generation_per_person_m3_h=0.0,
                daylight_utilization_factor=0.5,
                room_depth_m=zone.floor_area_m2**0.5,
                visual_comfort_target_lux=300.0,
                indoor_noise_initial_db=35.0,
                background_noise_db=30.0,
                room_absorption_factor=0.3,
            )
            state = zone_models[zone.zone_id].initial_state()
            state.indoor_relative_humidity_percent = (
                zone.initial_relative_humidity_fraction * 100.0
            )

        dwelling = DwellingModel(
            dwelling_id=canonical_dwelling.dwelling_id,
            building_id=canonical_building.building_id,
            household_id=f"household:{canonical_dwelling.dwelling_id}",
            private_zone_ids=sorted(zone_models),
            zone_models=zone_models,
            zone_states={
                zone_id: model.initial_state() for zone_id, model in zone_models.items()
            },
            system_specs={},
            control_states={},
            controller_specs={},
        )
        for zone in canonical_dwelling.zones:
            dwelling.zone_states[zone.zone_id].indoor_relative_humidity_percent = (
                zone.initial_relative_humidity_fraction * 100.0
            )
        building = BuildingModel(
            building_id=canonical_building.building_id,
            dwelling_ids=[canonical_dwelling.dwelling_id],
            dwellings={canonical_dwelling.dwelling_id: dwelling},
            shared_zone_ids=[],
            shared_zone_models={},
            shared_zone_states={},
            shared_system_specs={},
            building_system_specs={},
            building_control_states={},
            building_controller_specs={},
        )
        return building, defaults

    def _compile_physics_graph(self) -> BuildingPhysicsGraph:
        zone_connections: dict[str, ZoneConnection] = {}
        boundary_connections: dict[str, BoundaryConnection] = {}
        connections = cast(list[dict[str, Any]], self.compiled_graph["connections"])
        for raw in connections:
            connection = dict(raw)
            if connection["boundary_type"] == "interzone":
                zone_connections[connection["connection_id"]] = ZoneConnection(
                    connection_id=connection["connection_id"],
                    from_zone_id=connection["source_node_id"],
                    to_zone_id=connection["target_node_id"],
                    connection_type="internal_wall",
                    area_m2=connection["gross_area_m2"],
                    is_openable=False,
                    open_fraction=0.0,
                    allow_duplicate=False,
                    max_opening_area_m2=None,
                    discharge_coefficient=0.6,
                    base_airflow_m3_h=0.0,
                    partition_sound_reduction_db=35.0,
                    door_sound_reduction_db=20.0,
                    u_value_w_m2k=connection["thermal_transmittance_w_m2_k"],
                )
            elif connection["connection_type"] == "surface":
                boundary_connections[connection["connection_id"]] = BoundaryConnection(
                    connection_id=connection["connection_id"],
                    zone_id=connection["source_node_id"],
                    connection_type="external_wall",
                    area_m2=connection["net_opaque_area_m2"],
                    orientation_deg=connection["azimuth_deg"],
                    tilt_deg=connection["tilt_deg"],
                    is_window=False,
                    is_openable=False,
                    open_fraction=0.0,
                    allow_duplicate=False,
                    u_value_w_m2k=connection["thermal_transmittance_w_m2_k"],
                )
            else:
                boundary_connections[connection["connection_id"]] = BoundaryConnection(
                    connection_id=connection["connection_id"],
                    zone_id=connection["source_node_id"],
                    connection_type="window",
                    area_m2=connection["gross_area_m2"],
                    orientation_deg=connection["azimuth_deg"],
                    tilt_deg=connection["tilt_deg"],
                    is_window=True,
                    is_openable=bool(connection["openable_area_m2"]),
                    open_fraction=0.0,
                    allow_duplicate=False,
                    window_u_value_w_m2k=connection["thermal_transmittance_w_m2_k"],
                    glazing_transmittance=connection["solar_transmittance_fraction"],
                    window_visible_transmittance=connection[
                        "visible_transmittance_fraction"
                    ],
                    solar_heat_gain_coefficient=connection[
                        "solar_transmittance_fraction"
                    ],
                    frame_fraction=0.0,
                    shading_factor=1.0,
                    curtain_open=True,
                    curtain_solar_reduction_factor=0.0,
                    curtain_daylight_reduction_factor=0.0,
                    outside_noise_transmission_factor=0.1,
                    window_sound_reduction_db=25.0,
                    max_opening_area_m2=connection["openable_area_m2"],
                    discharge_coefficient=0.6,
                )
        return BuildingPhysicsGraph(
            building_model=self.building_model,
            zone_connections=zone_connections,
            boundary_connections=boundary_connections,
        )

    def _system_specs(
        self, step_input: SimulationStepInput
    ) -> dict[str, ZoneSystemSpec]:
        availability = {item.system_id: item for item in step_input.system_availability}
        result: dict[str, ZoneSystemSpec] = {}
        dwelling = self.scenario.building.dwelling
        for zone in dwelling.zones:
            systems = {item.system_type: item for item in zone.systems}

            def available(system_type: str, zone_systems=systems) -> float:
                system = zone_systems.get(system_type)
                if system is None:
                    return 0.0
                return availability[system.system_id].capacity_fraction

            heating = systems.get("heating")
            cooling = systems.get("cooling")
            ventilation = systems.get("ventilation")
            lighting = systems.get("lighting")
            result[zone.zone_id] = ZoneSystemSpec(
                zone_id=zone.zone_id,
                dwelling_id=dwelling.dwelling_id,
                building_id=self.scenario.building.building_id,
                heating_capacity_w=(
                    _required_float(heating.max_heating_power_w, "max_heating_power_w")
                    * available("heating")
                    if heating
                    else 0.0
                ),
                cooling_capacity_w=(
                    _required_float(cooling.max_cooling_power_w, "max_cooling_power_w")
                    * available("cooling")
                    if cooling
                    else 0.0
                ),
                ventilation_flow_m3_h=(
                    _required_float(
                        ventilation.max_ventilation_volume_flow_m3_s,
                        "max_ventilation_volume_flow_m3_s",
                    )
                    * 3600.0
                    * available("ventilation")
                    if ventilation
                    else 0.0
                ),
                lighting_power_w=(
                    _required_float(
                        lighting.max_lighting_power_w, "max_lighting_power_w"
                    )
                    * available("lighting")
                    if lighting
                    else 0.0
                ),
                ventilation_fan_power_w=0.0,
                heating_efficiency_or_cop=(
                    _required_float(
                        heating.heating_efficiency_fraction,
                        "heating_efficiency_fraction",
                    )
                    if heating
                    else 1.0
                ),
                cooling_efficiency_or_cop=(
                    _required_float(cooling.cooling_cop, "cooling_cop")
                    if cooling
                    else 1.0
                ),
                has_heating=heating is not None and available("heating") > 0.0,
                has_cooling=cooling is not None and available("cooling") > 0.0,
                has_ventilation=ventilation is not None
                and available("ventilation") > 0.0,
                has_lighting=lighting is not None and available("lighting") > 0.0,
                has_operable_window=any(
                    opening.openable_area_m2 > 0.0
                    for surface in zone.surfaces
                    for opening in surface.openings
                ),
                has_shading=True,
                lighting_power_density_w_m2=(
                    _required_float(
                        lighting.max_lighting_power_w, "max_lighting_power_w"
                    )
                    / zone.floor_area_m2
                    if lighting
                    else 0.0
                ),
                installed_lighting_lux=300.0,
                system_scope="zone",
            )
        return result

    def _control_commands(
        self, step_input: SimulationStepInput
    ) -> dict[str, ObjectZoneControlCommand]:
        dwelling_id = self.scenario.building.dwelling.dwelling_id
        building_id = self.scenario.building.building_id
        result: dict[str, ObjectZoneControlCommand] = {}
        for item in step_input.control_commands:
            if item.shading_open_fraction not in {0.0, 1.0}:
                raise BackendAdapterError(
                    "object engine cannot represent fractional shading; use 0.0 or 1.0"
                )
            result[item.zone_id] = ObjectZoneControlCommand(
                zone_id=item.zone_id,
                dwelling_id=dwelling_id,
                building_id=building_id,
                heating_on=item.heating_on,
                heating_power_fraction=item.heating_power_fraction,
                heating_convective_fraction=item.heating_convective_fraction,
                cooling_on=item.cooling_on,
                cooling_power_fraction=item.cooling_power_fraction,
                cooling_convective_fraction=item.cooling_convective_fraction,
                ventilation_flow_m3_h=item.ventilation_volume_flow_m3_s * 3600.0,
                ventilation_supply_temperature_c=(
                    item.ventilation_supply_temperature_c
                ),
                lights_on=item.lights_on,
                lighting_power_w=item.lighting_power_w,
                window_open=item.window_opening_fraction > 0.0,
                window_opening_fraction=item.window_opening_fraction,
                curtain_open=item.shading_open_fraction == 1.0,
            )
        return result

    @staticmethod
    def _source_record(gain: InternalGain, dt_minutes: float) -> InternalSourceRecord:
        source_kind = {
            "occupant": "person",
            "activity": "activity",
            "appliance": "appliance",
            "lighting": "lighting",
            "other": "generic",
        }[gain.source_kind]
        return InternalSourceRecord(
            zone_id=gain.zone_id,
            source_kind=source_kind,
            source_type=gain.source_kind,
            source_id=gain.source_id,
            duration_minutes=dt_minutes,
            power_w=gain.electrical_power_w,
            electricity_wh=gain.electrical_power_w * dt_minutes / 60.0,
            sensible_heat_w=gain.sensible_heat_w,
            sensible_heat_wh=gain.sensible_heat_w * dt_minutes / 60.0,
            latent_heat_w=gain.latent_heat_w,
            latent_heat_wh=gain.latent_heat_w * dt_minutes / 60.0,
            co2_generation_m3_h=gain.co2_generation_kg_s * 3600.0 / CO2_DENSITY_KG_M3,
            moisture_generation_kg_h=gain.moisture_generation_kg_s * 3600.0,
            source="canonical_step_input",
        )

    def _internal_sources(
        self, step_input: SimulationStepInput
    ) -> BuildingInternalSourceResult:
        occupant_by_id = {item.occupant_id: item for item in self.scenario.occupants}
        records = [
            self._source_record(item, step_input.dt_minutes)
            for item in step_input.internal_gains
        ]
        for state in step_input.occupant_states:
            if not state.is_present:
                continue
            occupant = occupant_by_id[state.occupant_id]
            records.append(
                InternalSourceRecord(
                    zone_id=state.zone_id,
                    source_kind="person",
                    source_type="occupant",
                    source_id=f"occupant:{state.occupant_id}",
                    actor_id=state.occupant_id,
                    action_name=state.activity,
                    duration_minutes=step_input.dt_minutes,
                    sensible_heat_w=occupant.sensible_heat_gain_w,
                    sensible_heat_wh=occupant.sensible_heat_gain_w
                    * step_input.dt_minutes
                    / 60.0,
                    co2_generation_m3_h=(
                        occupant.co2_generation_kg_s * 3600.0 / CO2_DENSITY_KG_M3
                    ),
                    moisture_generation_kg_h=occupant.moisture_generation_kg_s * 3600.0,
                    source="canonical_occupant_state",
                )
            )
        for command in step_input.control_commands:
            if not command.lights_on or command.lighting_power_w == 0.0:
                continue
            records.append(
                InternalSourceRecord(
                    zone_id=command.zone_id,
                    source_kind="lighting",
                    source_type="lighting",
                    source_id=f"lighting:{command.zone_id}",
                    duration_minutes=step_input.dt_minutes,
                    power_w=command.lighting_power_w,
                    electricity_wh=(
                        command.lighting_power_w * step_input.dt_minutes / 60.0
                    ),
                    sensible_heat_w=command.lighting_power_w,
                    sensible_heat_wh=(
                        command.lighting_power_w * step_input.dt_minutes / 60.0
                    ),
                    source="canonical_control_command",
                )
            )
        return BuildingInternalSourceResult(
            records=records,
            expected_zone_ids=sorted(self.building_model.all_zone_ids()),
            dt_minutes=step_input.dt_minutes,
            source="canonical_object_adapter",
        )

    def _apply_prior_state(self, step_input: SimulationStepInput) -> None:
        occupants_by_zone: dict[str, list[str]] = defaultdict(list)
        for occupant in step_input.occupant_states:
            if occupant.is_present:
                occupants_by_zone[occupant.zone_id].append(occupant.occupant_id)
        for prior in step_input.prior_zone_states:
            state = self.building_model.get_zone_state(prior.zone_id).copy(
                indoor_temp_c=prior.air_temperature_c,
                indoor_mass_temp_c=prior.mean_radiant_temperature_c,
                co2_ppm=prior.co2_ppm,
                indoor_relative_humidity_percent=prior.relative_humidity_fraction
                * 100.0,
                occupied_person_ids=sorted(occupants_by_zone[prior.zone_id]),
                number_of_people=len(occupants_by_zone[prior.zone_id]),
            )
            self.building_model.set_zone_state(prior.zone_id, state)

    def run_step(self, step_input: SimulationStepInput, *, include_debug: bool = False):
        validate_step_input_for_scenario(step_input, self.scenario, self.compiled_graph)
        self._apply_prior_state(step_input)
        commands = self._control_commands(step_input)
        specs = self._system_specs(step_input)
        weather = step_input.weather
        solar_position = calculate_solar_position(
            weather.timestamp,
            latitude_deg=self.scenario.site.latitude_deg,
            longitude_deg=self.scenario.site.longitude_deg,
            elevation_m=self.scenario.site.elevation_m,
            atmospheric_pressure_pa=weather.atmospheric_pressure_pa,
            outdoor_temperature_c=weather.outdoor_temperature_c,
        )
        object_weather = ObjectWeatherState(
            datetime=weather.timestamp,
            outdoor_temperature_c=weather.outdoor_temperature_c,
            wind_speed_m_s=weather.wind_speed_m_s,
            wind_direction_deg=weather.wind_direction_deg,
            direct_normal_radiation_w_m2=weather.direct_normal_radiation_w_m2,
            diffuse_horizontal_radiation_w_m2=weather.diffuse_horizontal_radiation_w_m2,
            global_horizontal_radiation_w_m2=weather.global_horizontal_radiation_w_m2,
            outdoor_illuminance_lux=weather.outdoor_illuminance_lux or 0.0,
            sky_condition="canonical",
            outdoor_co2_ppm=weather.outdoor_co2_ppm,
            outdoor_noise_db=weather.outdoor_noise_db or 0.0,
            relative_humidity_percent=weather.relative_humidity_fraction * 100.0,
            atmospheric_pressure_pa=weather.atmospheric_pressure_pa,
            solar_zenith_deg=solar_position.zenith_deg,
            solar_azimuth_deg=solar_position.azimuth_deg,
            solar_altitude_deg=solar_position.elevation_deg,
            ground_albedo_fraction=self.scenario.site.ground_albedo_fraction,
        )
        native_input = BuildingPhysicsStepInput(
            building_model=self.building_model,
            dt_minutes=step_input.dt_minutes,
            physics_graph=self.physics_graph,
            weather_state=object_weather,
            zone_control_commands=commands,
            zone_system_specs=specs,
            people={},
            locations={},
            role_to_zone_id={
                zone_id: zone_id for zone_id in self.building_model.all_zone_ids()
            },
            chunk_records=[],
            internal_source_result=self._internal_sources(step_input),
            previous_air_state=None,
            previous_moisture_state=None,
            previous_thermal_state=None,
            previous_light_state=None,
            previous_acoustic_state=None,
            source="canonical_object_adapter",
        )
        encoded_trace = {
            "timestamp": object_weather.datetime.isoformat(),
            "time_index": step_input.timestep_index,
            "dt_minutes": step_input.dt_minutes,
            "weather": object_weather.to_dict(),
            "controls": {
                zone_id: command.to_dict()
                for zone_id, command in sorted(commands.items())
            },
            "occupants": [
                item.model_dump(mode="json")
                for item in sorted(
                    step_input.occupant_states, key=lambda value: value.occupant_id
                )
            ],
            "graph_sha256": self.compiled_graph["graph_sha256"],
        }
        native_result = run_building_physics_step(
            native_input,
            require_physics_graph=True,
            write_back_to_building_model=True,
        )
        record_by_zone = {item["zone_id"]: item for item in native_result.zone_records}
        controls = {item.zone_id: item for item in step_input.control_commands}
        occupancy: defaultdict[str, int] = defaultdict(int)
        for occupant in step_input.occupant_states:
            if occupant.is_present:
                occupancy[occupant.zone_id] += 1
        extra_electricity: defaultdict[str, float] = defaultdict(float)
        for gain in step_input.internal_gains:
            extra_electricity[gain.zone_id] += gain.electrical_power_w

        rows = []
        for zone_id in sorted(self.building_model.all_zone_ids()):
            state = self.building_model.get_zone_state(zone_id)
            native = record_by_zone[zone_id]
            command = controls[zone_id]
            heating = float(native.get("command_heating_power_w", 0.0))
            cooling = float(native.get("command_cooling_power_w", 0.0))
            lighting = float(
                native.get("lighting_result_power_w", command.lighting_power_w)
            )
            heating_input = float(native.get("heating_input_power_w", heating))
            cooling_input = float(native.get("cooling_input_power_w", cooling))
            total_electrical = (
                heating_input + cooling_input + lighting + extra_electricity[zone_id]
            )
            rows.append(
                CanonicalZoneStepResult(
                    scenario_id=self.scenario.scenario_id,
                    run_id=step_input.run_context.run_id,
                    building_id=self.scenario.building.building_id,
                    dwelling_id=self.scenario.building.dwelling.dwelling_id,
                    zone_id=zone_id,
                    timestamp=step_input.timestamp,
                    timestep_index=step_input.timestep_index,
                    air_temperature_c=state.indoor_temp_c,
                    relative_humidity_fraction=(
                        (state.indoor_relative_humidity_percent or 0.0) / 100.0
                    ),
                    co2_ppm=state.co2_ppm,
                    occupancy_count=occupancy[zone_id],
                    heating_power_w=heating,
                    cooling_power_w=cooling,
                    ventilation_power_w=0.0,
                    lighting_power_w=lighting,
                    total_electrical_power_w=total_electrical,
                    engine_name=self.engine_name,
                    engine_version=self.engine_version,
                    engine_status="completed_with_warnings"
                    if self.defaults_applied
                    else "completed",
                    fallback_used=False,
                    fallback_reason=None,
                )
            )
        warnings = (
            CanonicalWarning(
                code="object_engine_explicit_zero_fan_power",
                message="ventilation electrical power is zero because canonical v1 has no fan-power field",
                entity_id=None,
            ),
        )
        return assemble_step_result(
            scenario=self.scenario,
            step_input=step_input,
            zones=rows,
            warnings=warnings,
            provenance=(
                ValidationProvenance(
                    check="object_engine_path",
                    status="passed",
                    detail="unified physics engine executed with legacy fallback disabled",
                ),
                ValidationProvenance(
                    check="native_record_translation",
                    status="passed",
                    detail="legacy zone records translated by original canonical string IDs",
                ),
            ),
            defaults=self.defaults_applied,
            debug_fields=(
                {
                    "native_source": native_result.source,
                    "native_zone_records": native_result.zone_records,
                    "conservation_residuals": {
                        "thermal_balance_residual_w": (
                            native_result.thermal_step_result.balance_residual_w()
                        ),
                        "moisture_balance_residual_kg_s": (
                            native_result.moisture_step_result.balance_residual_kg_s()
                        ),
                        "co2_mass_balance_residual_kg_s": (
                            native_result.co2_step_result.balance_residual_m3_s()
                            * CO2_DENSITY_KG_M3
                        ),
                    },
                    "action_events": [
                        item.model_dump(mode="json")
                        for item in step_input.action_events
                    ],
                    "step_trace": encoded_trace,
                    "next_prior_zone_states": [
                        {
                            "zone_id": zone_id,
                            "air_temperature_c": self.building_model.get_zone_state(
                                zone_id
                            ).indoor_temp_c,
                            "mean_radiant_temperature_c": self.building_model.get_zone_state(
                                zone_id
                            ).indoor_mass_temp_c,
                            "relative_humidity_fraction": (
                                (
                                    self.building_model.get_zone_state(zone_id)
                                    .indoor_relative_humidity_percent
                                    or 0.0
                                )
                                / 100.0
                            ),
                            "co2_ppm": self.building_model.get_zone_state(
                                zone_id
                            ).co2_ppm,
                        }
                        for zone_id in sorted(self.building_model.all_zone_ids())
                    ],
                }
                if include_debug
                else None
            ),
        )


__all__ = ["CO2_DENSITY_KG_M3", "ObjectEngineAdapter"]
