"""
ABBEY building physics input validation.


- validates graph/model/system/control inputs
- reports missing or inconsistent data
- does not solve thermal, airflow, CO2, daylight, or acoustics
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from nexusep.abbey.building.physics.graph import BuildingPhysicsGraph


VALID_SYSTEM_SCOPES_LOCAL = {
    "zone",
    "dwelling",
    "shared",
    "building",
}

VALID_CONTROL_MODES_LOCAL = {
    "off",
    "manual",
    "semi_auto",
    "auto",
}


@dataclass
class PhysicsInputValidationReport:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def ok(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, message: str) -> None:
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def raise_if_errors(self) -> None:
        if not self.errors:
            return

        message = "Physics input validation failed:\n"

        for error in self.errors:
            message += "- " + error + "\n"

        raise ValueError(message)

    def summary(self) -> str:
        return (
            "PhysicsInputValidationReport("
            + "errors="
            + str(len(self.errors))
            + ", warnings="
            + str(len(self.warnings))
            + ")"
        )


def validate_physics_inputs(
    graph: BuildingPhysicsGraph,
    zone_system_specs: Optional[Dict[str, Any]] = None,
    zone_control_states: Optional[Dict[str, Any]] = None,
    realistic_mode: bool = True,
    raise_on_error: bool = False,
) -> PhysicsInputValidationReport:
    report = PhysicsInputValidationReport()

    zone_system_specs = zone_system_specs or {}
    zone_control_states = zone_control_states or {}

    _validate_graph(graph, report)
    _validate_zones(graph, report, realistic_mode)
    _validate_zone_connections(graph, report)
    _validate_boundary_connections(graph, report)
    _validate_zone_system_specs(graph, zone_system_specs, report)
    _validate_zone_control_states(graph, zone_control_states, report)

    if raise_on_error:
        report.raise_if_errors()

    return report


def _validate_graph(
    graph: BuildingPhysicsGraph,
    report: PhysicsInputValidationReport,
) -> None:
    try:
        graph.validate()
    except Exception as exc:
        report.add_error("BuildingPhysicsGraph.validate() failed: " + str(exc))


def _validate_zones(
    graph: BuildingPhysicsGraph,
    report: PhysicsInputValidationReport,
    realistic_mode: bool,
) -> None:
    for zone in graph.all_zones():
        zone_id = _get(zone, "zone_id", "")

        _require_text(zone, "zone_id", zone_id, report)
        _require_text(zone, "building_id", zone_id, report)
        _require_text(zone, "zone_name", zone_id, report)
        _require_text(zone, "zone_use", zone_id, report)
        _require_text(zone, "zone_scope", zone_id, report)

        if _get(zone, "zone_scope", "") == "private":
            _require_text(zone, "dwelling_id", zone_id, report)

        if _get(zone, "zone_scope", "") not in ("private", "shared"):
            report.add_error(
                "Zone '" + zone_id + "' has invalid zone_scope: "
                + str(_get(zone, "zone_scope", ""))
            )

        _validate_geometry_zone(zone, report, realistic_mode)
        _validate_thermal_zone(zone, report)
        _validate_airflow_zone(zone, report)
        _validate_lighting_zone(zone, report)
        _validate_acoustic_zone(zone, report)


def _validate_geometry_zone(
    zone: Any,
    report: PhysicsInputValidationReport,
    realistic_mode: bool,
) -> None:
    zone_id = _get(zone, "zone_id", "")

    if _missing(zone, "floor_area_m2"):
        if realistic_mode:
            report.add_error(
                "Zone '" + zone_id + "' is missing floor_area_m2."
            )
        return

    _check_positive(zone, "floor_area_m2", zone_id, report)
    _check_positive(zone, "height_m", zone_id, report)
    _check_positive(zone, "volume_m3", zone_id, report)

    if not _missing(zone, "floor_level"):
        try:
            int(_get(zone, "floor_level", 0))
        except Exception:
            report.add_error(
                "Zone '" + zone_id + "' has invalid floor_level."
            )

    if not _missing(zone, "centroid_x"):
        _check_number(zone, "centroid_x", zone_id, report)

    if not _missing(zone, "centroid_y"):
        _check_number(zone, "centroid_y", zone_id, report)


def _validate_thermal_zone(
    zone: Any,
    report: PhysicsInputValidationReport,
) -> None:
    zone_id = _get(zone, "zone_id", "")

    _require_text(zone, "thermal_mass_class", zone_id, report)

    _check_positive(zone, "internal_heat_capacity_j_k", zone_id, report)
    _check_positive(zone, "air_heat_capacity_j_k", zone_id, report)

    _check_nonnegative(zone, "external_wall_area_m2", zone_id, report)
    _check_nonnegative(zone, "internal_wall_area_m2", zone_id, report)
    _check_nonnegative(zone, "floor_area_to_other_zone_m2", zone_id, report)
    _check_nonnegative(zone, "ceiling_area_to_other_zone_m2", zone_id, report)

    _check_nonnegative(zone, "u_value_external_wall_w_m2k", zone_id, report)
    _check_nonnegative(zone, "u_value_internal_wall_w_m2k", zone_id, report)
    _check_nonnegative(zone, "u_value_floor_w_m2k", zone_id, report)
    _check_nonnegative(zone, "u_value_ceiling_w_m2k", zone_id, report)

    _check_nonnegative(zone, "thermal_bridge_factor", zone_id, report)

    _check_number(zone, "initial_air_temperature_c", zone_id, report)
    _check_number(zone, "initial_mass_temperature_c", zone_id, report)


def _validate_airflow_zone(
    zone: Any,
    report: PhysicsInputValidationReport,
) -> None:
    zone_id = _get(zone, "zone_id", "")

    _check_positive(zone, "air_volume_m3", zone_id, report)
    _check_nonnegative(zone, "default_infiltration_ach", zone_id, report)
    _check_nonnegative(zone, "mechanical_ventilation_flow_m3_h", zone_id, report)
    _check_nonnegative(zone, "interzone_airflow_base_m3_h", zone_id, report)
    _check_positive(zone, "co2_initial_ppm", zone_id, report)
    _check_nonnegative(zone, "co2_generation_per_person_m3_h", zone_id, report)

    if (
        bool(_get(zone, "mechanical_ventilation_available", False))
        and float(_get(zone, "mechanical_ventilation_flow_m3_h", 0.0)) <= 0.0
    ):
        report.add_warning(
            "Zone '" + zone_id + "' has mechanical ventilation available "
            "but mechanical_ventilation_flow_m3_h is zero."
        )


def _validate_lighting_zone(
    zone: Any,
    report: PhysicsInputValidationReport,
) -> None:
    zone_id = _get(zone, "zone_id", "")

    _check_fraction(zone, "daylight_utilization_factor", zone_id, report)
    _check_positive(zone, "room_depth_m", zone_id, report)
    _check_nonnegative(zone, "visual_comfort_target_lux", zone_id, report)


def _validate_acoustic_zone(
    zone: Any,
    report: PhysicsInputValidationReport,
) -> None:
    zone_id = _get(zone, "zone_id", "")

    _check_nonnegative(zone, "indoor_noise_initial_db", zone_id, report)
    _check_nonnegative(zone, "background_noise_db", zone_id, report)
    _check_fraction(zone, "room_absorption_factor", zone_id, report)


def _validate_zone_connections(
    graph: BuildingPhysicsGraph,
    report: PhysicsInputValidationReport,
) -> None:
    for connection in graph.zone_connections.values():
        cid = _get(connection, "connection_id", "")

        _require_text(connection, "connection_id", cid, report)
        _require_text(connection, "from_zone_id", cid, report)
        _require_text(connection, "to_zone_id", cid, report)
        _require_text(connection, "connection_type", cid, report)

        _check_optional_nonnegative(connection, "area_m2", cid, report)
        _check_fraction(connection, "open_fraction", cid, report)
        _check_optional_nonnegative(connection, "max_opening_area_m2", cid, report)
        _check_fraction(connection, "discharge_coefficient", cid, report)
        _check_nonnegative(connection, "base_airflow_m3_h", cid, report)

        _check_nonnegative(connection, "partition_sound_reduction_db", cid, report)
        _check_nonnegative(connection, "door_sound_reduction_db", cid, report)

        if bool(_get(connection, "is_openable", False)):
            if _missing(connection, "max_opening_area_m2"):
                report.add_warning(
                    "Openable ZoneConnection '" + cid
                    + "' has no max_opening_area_m2."
                )


def _validate_boundary_connections(
    graph: BuildingPhysicsGraph,
    report: PhysicsInputValidationReport,
) -> None:
    for connection in graph.boundary_connections.values():
        cid = _get(connection, "connection_id", "")

        _require_text(connection, "connection_id", cid, report)
        _require_text(connection, "zone_id", cid, report)
        _require_text(connection, "boundary_id", cid, report)
        _require_text(connection, "connection_type", cid, report)

        _check_optional_nonnegative(connection, "area_m2", cid, report)
        _check_fraction(connection, "open_fraction", cid, report)
        _check_optional_nonnegative(connection, "max_opening_area_m2", cid, report)
        _check_fraction(connection, "discharge_coefficient", cid, report)

        _check_fraction(connection, "frame_fraction", cid, report)
        _check_fraction(connection, "shading_factor", cid, report)
        _check_fraction(connection, "curtain_solar_reduction_factor", cid, report)
        _check_fraction(connection, "curtain_daylight_reduction_factor", cid, report)

        _check_fraction(connection, "outside_noise_transmission_factor", cid, report)
        _check_nonnegative(connection, "window_sound_reduction_db", cid, report)

        if bool(_get(connection, "is_window", False)):
            _check_positive(connection, "area_m2", cid, report)
            _check_number(connection, "orientation_deg", cid, report)
            _check_nonnegative(connection, "window_u_value_w_m2k", cid, report)
            _check_fraction(connection, "glazing_transmittance", cid, report)
            _check_fraction(connection, "window_visible_transmittance", cid, report)
            _check_fraction(connection, "solar_heat_gain_coefficient", cid, report)

        if bool(_get(connection, "is_openable", False)):
            if _missing(connection, "max_opening_area_m2"):
                report.add_warning(
                    "Openable BoundaryConnection '" + cid
                    + "' has no max_opening_area_m2."
                )

            if _missing(connection, "orientation_deg"):
                report.add_warning(
                    "Openable BoundaryConnection '" + cid
                    + "' has no orientation_deg; wind-driven airflow will be limited."
                )


def _validate_zone_system_specs(
    graph: BuildingPhysicsGraph,
    zone_system_specs: Dict[str, Any],
    report: PhysicsInputValidationReport,
) -> None:
    if not zone_system_specs:
        report.add_warning(
            "No zone_system_specs provided to physics input validation."
        )
        return

    for zone_id in graph.all_zone_ids():
        if zone_id not in zone_system_specs:
            report.add_warning(
                "Zone '" + zone_id + "' has no ZoneSystemSpec."
            )
            continue

        spec = zone_system_specs[zone_id]

        _check_nonnegative(spec, "heating_capacity_w", zone_id, report)
        _check_nonnegative(spec, "cooling_capacity_w", zone_id, report)
        _check_nonnegative(spec, "ventilation_flow_m3_h", zone_id, report)
        _check_nonnegative(spec, "lighting_power_w", zone_id, report)

        _check_positive(spec, "heating_efficiency_or_cop", zone_id, report)
        _check_positive(spec, "cooling_efficiency_or_cop", zone_id, report)

        _check_nonnegative(spec, "lighting_power_density_w_m2", zone_id, report)
        _check_nonnegative(spec, "installed_lighting_lux", zone_id, report)

        scope = _get(spec, "system_scope", "zone")

        if scope not in VALID_SYSTEM_SCOPES_LOCAL:
            report.add_error(
                "ZoneSystemSpec for zone '" + zone_id
                + "' has invalid system_scope: " + str(scope)
            )

        if bool(_get(spec, "has_heating", False)):
            if float(_get(spec, "heating_capacity_w", 0.0)) <= 0.0:
                report.add_warning(
                    "Zone '" + zone_id + "' has_heating=True but heating_capacity_w is zero."
                )

        if bool(_get(spec, "has_cooling", False)):
            if float(_get(spec, "cooling_capacity_w", 0.0)) <= 0.0:
                report.add_warning(
                    "Zone '" + zone_id + "' has_cooling=True but cooling_capacity_w is zero."
                )


def _validate_zone_control_states(
    graph: BuildingPhysicsGraph,
    zone_control_states: Dict[str, Any],
    report: PhysicsInputValidationReport,
) -> None:
    if not zone_control_states:
        report.add_warning(
            "No zone_control_states provided to physics input validation."
        )
        return

    for zone_id in graph.all_zone_ids():
        if zone_id not in zone_control_states:
            report.add_warning(
                "Zone '" + zone_id + "' has no ZoneControlState."
            )
            continue

        state = zone_control_states[zone_id]

        _check_number(state, "heating_setpoint_c", zone_id, report)
        _check_number(state, "cooling_setpoint_c", zone_id, report)
        _check_nonnegative(state, "thermostat_deadband_c", zone_id, report)

        for field_name in (
            "heating_mode",
            "cooling_mode",
            "ventilation_mode",
            "lighting_mode",
            "window_mode",
            "shading_mode",
        ):
            if _missing(state, field_name):
                continue

            value = _get(state, field_name, "")

            if value not in VALID_CONTROL_MODES_LOCAL:
                report.add_error(
                    "ZoneControlState for zone '" + zone_id
                    + "' has invalid "
                    + field_name
                    + ": "
                    + str(value)
                )


def _missing(obj: Any, field_name: str) -> bool:
    return _get(obj, field_name, None) is None


def _get(obj: Any, field_name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(field_name, default)

    return getattr(obj, field_name, default)


def _require_text(
    obj: Any,
    field_name: str,
    object_id: str,
    report: PhysicsInputValidationReport,
) -> None:
    value = _get(obj, field_name, None)

    if value is None or not str(value).strip():
        report.add_error(
            "Object '" + object_id + "' is missing required text field "
            + field_name + "."
        )


def _check_number(
    obj: Any,
    field_name: str,
    object_id: str,
    report: PhysicsInputValidationReport,
) -> None:
    value = _get(obj, field_name, None)

    if value is None:
        report.add_error(
            "Object '" + object_id + "' is missing required numeric field "
            + field_name + "."
        )
        return

    try:
        float(value)
    except Exception:
        report.add_error(
            "Object '" + object_id + "' has non-numeric "
            + field_name + ": " + str(value)
        )


def _check_positive(
    obj: Any,
    field_name: str,
    object_id: str,
    report: PhysicsInputValidationReport,
) -> None:
    value = _get(obj, field_name, None)

    if value is None:
        report.add_error(
            "Object '" + object_id + "' is missing required positive field "
            + field_name + "."
        )
        return

    try:
        value = float(value)
    except Exception:
        report.add_error(
            "Object '" + object_id + "' has non-numeric "
            + field_name + ": " + str(value)
        )
        return

    if value <= 0.0:
        report.add_error(
            "Object '" + object_id + "' has non-positive "
            + field_name + ": " + str(value)
        )


def _check_nonnegative(
    obj: Any,
    field_name: str,
    object_id: str,
    report: PhysicsInputValidationReport,
) -> None:
    value = _get(obj, field_name, None)

    if value is None:
        report.add_error(
            "Object '" + object_id + "' is missing required non-negative field "
            + field_name + "."
        )
        return

    try:
        value = float(value)
    except Exception:
        report.add_error(
            "Object '" + object_id + "' has non-numeric "
            + field_name + ": " + str(value)
        )
        return

    if value < 0.0:
        report.add_error(
            "Object '" + object_id + "' has negative "
            + field_name + ": " + str(value)
        )


def _check_optional_nonnegative(
    obj: Any,
    field_name: str,
    object_id: str,
    report: PhysicsInputValidationReport,
) -> None:
    if _missing(obj, field_name):
        return

    _check_nonnegative(obj, field_name, object_id, report)


def _check_fraction(
    obj: Any,
    field_name: str,
    object_id: str,
    report: PhysicsInputValidationReport,
) -> None:
    value = _get(obj, field_name, None)

    if value is None:
        report.add_error(
            "Object '" + object_id + "' is missing required fraction field "
            + field_name + "."
        )
        return

    try:
        value = float(value)
    except Exception:
        report.add_error(
            "Object '" + object_id + "' has non-numeric fraction "
            + field_name + ": " + str(value)
        )
        return

    if value < 0.0 or value > 1.0:
        report.add_error(
            "Object '" + object_id + "' has fraction outside [0, 1] for "
            + field_name + ": " + str(value)
        )