"""
Building-output saving utilities for ABBEY.

Phase 14:
- debug timestep outputs
- yearly aggregated outputs
- building/dwelling/zone CSVs
- basic plots
"""
from pathlib import Path
from typing import Any, Dict, Optional, List
import json
import math
import pandas as pd
import matplotlib.pyplot as plt


OUTPUT_SCHEMA_PHASE = "15.1"
OUTPUT_SCHEMA_SOURCE = "building.outputs.Phase15.1"

OUTPUT_MODE_MINIMAL = "minimal"
OUTPUT_MODE_STANDARD = "standard"
OUTPUT_MODE_DEBUG = "debug"

VALID_OUTPUT_MODES = {
    OUTPUT_MODE_MINIMAL,
    OUTPUT_MODE_STANDARD,
    OUTPUT_MODE_DEBUG,
}


ZONE_CORE_COLUMNS = [
    "step",
    "day",
    "hour",
    "building_id",
    "dwelling_id",
    "zone_id",
    "zone_name",
    "zone_scope",
    "number_of_people",
    "occupied_person_ids",
]

ZONE_STATE_COLUMNS = [
    "indoor_temp_c",
    "indoor_mass_temp_c",
    "co2_ppm",
    "indoor_daylight",
    "indoor_noise",
    "indoor_relative_humidity_percent",
    "indoor_humidity_ratio_kg_kg",
]

ZONE_CONTROL_COLUMNS = [
    "heating_on",
    "cooling_on",
    "lights_on",
    "window_open",
    "curtain_open",
    "ventilation_flow_m3_h",
    "ventilation_fan_power_w",
]

ZONE_HVAC_POWER_COLUMNS = [
    "heating_delivered_power_w",
    "cooling_delivered_power_w",

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
    "command_ventilation_flow_m3_h",
]

ZONE_ENERGY_COLUMNS = [
    "heating_delivered_energy_wh",
    "cooling_delivered_energy_wh",
    "heating_energy_wh",
    "cooling_energy_wh",
    "ventilation_fan_energy_wh",
    "lighting_energy_wh",
    "appliance_energy_wh",
    "hvac_delivered_energy_wh",
    "hvac_input_energy_wh",
    "total_energy_wh",
]

ZONE_THERMAL_COLUMNS = [
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

ZONE_AIRFLOW_COLUMNS = [
    "airflow_infiltration_flow_m3_h",
    "airflow_mechanical_ventilation_flow_m3_h",
    "airflow_window_flow_m3_h",
    "airflow_outdoor_exchange_m3_h",
    "airflow_interzone_exchange_m3_h",
    "airflow_total_exchange_m3_h",
]

ZONE_AIR_QUALITY_COLUMNS = [
    "old_co2_ppm",
    "new_co2_ppm",
    "co2_generation_m3_h",
]

ZONE_MOISTURE_COLUMNS = [
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

ZONE_WINDOW_COLUMNS = [
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
    "command_window_open",
    "command_window_opening_fraction",
    "command_curtain_open",
]

WINDOW_DETAIL_TIMESTEP_COLUMNS = [
    "step",
    "day",
    "hour",
    "time_hour",
    "building_id",

    "window_id",
    "boundary_connection_id",
    "zone_id",

    "orientation_deg",
    "orientation_label",
    "area_m2",

    "curtain_open",
    "blind_open",
    "blind_fraction",

    "opening_fraction",
    "airflow_opening_area_m2",
    "outdoor_airflow_m3_h",

    "solar_alignment_factor",
    "daylight_alignment_factor",
    "effective_solar_factor",
    "effective_visible_transmittance",
    "effective_solar_area_m2",
    "effective_daylight_area_m2",

    "solar_gain_w",
    "daylight_contribution_lux",

    "effective_u_value_w_m2k",
    "closed_window_conductance_w_k",
    "wind_alignment_factor",
    "has_airflow_opening",
    "source",
]

ZONE_DAYLIGHT_LIGHTING_COLUMNS = [
    "proposed_indoor_daylight",
    "old_indoor_daylight",
    "new_indoor_daylight",
    "daylight_illuminance_lux",
    "indoor_illuminance_lux",
    "artificial_lighting_illuminance_lux",
    "visual_comfort_status",
    "lighting_power_w",
    "lighting_result_lights_on",
    "lighting_result_power_w",
    "lighting_result_energy_wh",
    "lighting_result_requested_lux",
    "lighting_result_dimming_fraction",
    "command_lights_on",
    "command_lighting_power_w",
]

ZONE_SOLAR_COLUMNS = [
    "solar_gain_w",
    "solar_gain_wh",
]

ZONE_INTERNAL_SOURCE_COLUMNS = [
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

ZONE_INTERZONE_THERMAL_COLUMNS = [
    "interzone_thermal_link_count",
    "interzone_thermal_total_h_w_k",
    "interzone_heat_gain_w",
    "interzone_heat_loss_w",
    "interzone_net_heat_gain_w",
]

INTERZONE_THERMAL_TIMESTEP_COLUMNS = [
    "step",
    "day",
    "hour",
    "time_hour",
    "building_id",
    "link_id",
    "connection_id",
    "zone_connection_id",
    "zone_a_id",
    "zone_b_id",
    "connection_type",
    "h_w_k",
    "q_to_zone_a_w",
    "q_to_zone_b_w",
    "zone_a_air_temperature_c",
    "zone_b_air_temperature_c",
    "is_openable",
    "open_fraction",
    "opening_fraction",
    "source",
]


INTERZONE_AIRFLOW_TIMESTEP_COLUMNS = [
    "step",
    "day",
    "hour",
    "time_hour",
    "building_id",
    "link_id",
    "connection_id",
    "zone_connection_id",
    "zone_a_id",
    "zone_b_id",
    "connection_type",

    # Stable Phase 15 names.
    "airflow_a_to_b_m3_h",
    "airflow_b_to_a_m3_h",
    "airflow_a_to_b_m3_s",
    "airflow_b_to_a_m3_s",
    "mixing_exchange_m3_h",
    "mixing_exchange_m3_s",

    # Original/internal names kept for compatibility.
    "flow_a_to_b_m3_h",
    "flow_b_to_a_m3_h",
    "flow_a_to_b_m3_s",
    "flow_b_to_a_m3_s",
    "mixing_flow_m3_h",

    "net_a_to_b_m3_h",
    "is_symmetric",
    "open_fraction",
    "opening_fraction",
    "base_airflow_m3_h",
    "max_flow_m3_h",
    "source",
]

ZONE_ACOUSTIC_COLUMNS = [
    "old_indoor_noise",
    "new_indoor_noise",
    "proposed_indoor_noise",

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

ZONE_ENGINE_STATUS_COLUMNS = [
    "physics_engine_active",
    "physics_engine_source",
    "physics_path",
    "performance_path",
    "legacy_fallback_used",
    "legacy_fallback_reason",
]

ZONE_DEBUG_COLUMNS = (
    ZONE_THERMAL_COLUMNS
    + ZONE_AIRFLOW_COLUMNS
    + ZONE_AIR_QUALITY_COLUMNS
    + ZONE_MOISTURE_COLUMNS
    + ZONE_WINDOW_COLUMNS
    + ZONE_DAYLIGHT_LIGHTING_COLUMNS
    + ZONE_SOLAR_COLUMNS
    + ZONE_INTERNAL_SOURCE_COLUMNS
    + ZONE_INTERZONE_THERMAL_COLUMNS
    + ZONE_ACOUSTIC_COLUMNS
    + ZONE_ENGINE_STATUS_COLUMNS
)

ZONE_TIMESTEP_STANDARD_COLUMNS = (
    ZONE_CORE_COLUMNS
    + ZONE_STATE_COLUMNS
    + ZONE_CONTROL_COLUMNS
    + ZONE_HVAC_POWER_COLUMNS
    + ZONE_ENERGY_COLUMNS
)

ZONE_TIMESTEP_DEBUG_COLUMNS = (
    ZONE_TIMESTEP_STANDARD_COLUMNS
    + ZONE_DEBUG_COLUMNS
)

ZONE_TIMESTEP_YEARLY_SAFE_COLUMNS = (
    ZONE_CORE_COLUMNS
    + ZONE_STATE_COLUMNS
    + ZONE_CONTROL_COLUMNS
    + ZONE_ENERGY_COLUMNS
    + ZONE_ENGINE_STATUS_COLUMNS
)

DWELLING_CORE_COLUMNS = [
    "step",
    "day",
    "hour",
    "building_id",
    "dwelling_id",
    "total_occupancy",
    "private_zone_count",
]
DWELLING_ENERGY_COLUMNS = [
    "heating_energy_wh",
    "cooling_energy_wh",
    "lighting_energy_wh",
    "appliance_energy_wh",
    "total_energy_wh",
    "heating_delivered_energy_wh",
    "cooling_delivered_energy_wh",
    "ventilation_fan_energy_wh",
    "hvac_delivered_energy_wh",
    "hvac_input_energy_wh",
]

DWELLING_DEBUG_COLUMNS = [
    "zone_count",
    "mean_indoor_temp_c",
    "min_indoor_temp_c",
    "max_indoor_temp_c",
    "mean_indoor_mass_temp_c",
    "mean_co2_ppm",
    "max_co2_ppm",
    "mean_indoor_daylight",
    "mean_indoor_noise",
    "total_solar_gain_wh",
    "total_internal_electricity_wh",
    "total_internal_average_sensible_heat_w",
    "mean_internal_average_sensible_heat_w",
    "total_internal_sensible_heat_wh",
    "total_internal_gain_wh",
    "total_ventilation_flow_m3_h",
    "average_ventilation_flow_m3_h",
    "total_airflow_outdoor_exchange_m3_h",
    "total_airflow_interzone_exchange_m3_h",
    "total_local_noise_source_count",
    "zone_total_energy_wh",
    "energy_balance_residual_wh",
    "energy_balance_ok",
]

DWELLING_TIMESTEP_STANDARD_COLUMNS = (
    DWELLING_CORE_COLUMNS
    + DWELLING_ENERGY_COLUMNS
)

DWELLING_TIMESTEP_DEBUG_COLUMNS = (
    DWELLING_TIMESTEP_STANDARD_COLUMNS
    + DWELLING_DEBUG_COLUMNS
)

DWELLING_TIMESTEP_YEARLY_SAFE_COLUMNS = DWELLING_TIMESTEP_STANDARD_COLUMNS


BUILDING_CORE_COLUMNS = [
    "step",
    "day",
    "hour",
    "building_id",
    "number_of_dwellings",
    "number_of_zones",
    "private_zone_count",
    "shared_zone_count",
    "total_occupancy",
    "record_level",
    "diagnostic_output_mode",
]
BUILDING_ENERGY_COLUMNS = [
    "private_zone_energy_wh",
    "shared_zone_energy_wh",
    "private_total_energy_wh",
    "shared_total_energy_wh",
    "zone_total_energy_wh",
    "heating_energy_wh",
    "cooling_energy_wh",
    "lighting_energy_wh",
    "appliance_energy_wh",
    "shared_system_energy_wh",
    "total_energy_wh",
    "heating_delivered_energy_wh",
    "cooling_delivered_energy_wh",
    "ventilation_fan_energy_wh",
    "hvac_delivered_energy_wh",
    "hvac_input_energy_wh",
    "building_energy_result_total_energy_wh",
    "building_zone_energy_balance_residual_wh",
    "building_zone_energy_balance_ok",
]

BUILDING_INTERNAL_SOURCE_COLUMNS = [
    "internal_source_record_count",
    "internal_total_electricity_wh",
    "internal_total_average_sensible_heat_w",
    "internal_total_co2_generation_m3_h",
    "internal_total_moisture_generation_kg_h",
]
BUILDING_PHYSICS_SUMMARY_COLUMNS = [
    "zone_count",
    "mean_indoor_temp_c",
    "min_indoor_temp_c",
    "max_indoor_temp_c",
    "mean_indoor_mass_temp_c",
    "mean_co2_ppm",
    "max_co2_ppm",
    "mean_indoor_daylight",
    "mean_indoor_noise",
    "total_solar_gain_wh",
    "total_internal_electricity_wh",
    "total_internal_average_sensible_heat_w",
    "mean_internal_average_sensible_heat_w",
    "total_internal_sensible_heat_wh",
    "total_internal_gain_wh",
    "total_ventilation_flow_m3_h",
    "average_ventilation_flow_m3_h",
    "total_airflow_outdoor_exchange_m3_h",
    "total_airflow_interzone_exchange_m3_h",
    "total_local_noise_source_count",
    "private_mean_indoor_temp_c",
    "shared_mean_indoor_temp_c",
]
BUILDING_ENGINE_STATUS_COLUMNS = [
    "physics_engine_active",
    "physics_engine_error",
    "physics_engine_source",
    "physics_path",
    "performance_path",
    "legacy_fallback_used",
    "legacy_fallback_reason",
    "physics_engine_has_thermal_step_result",
    "physics_engine_has_interzone_thermal_network",
    "physics_engine_interzone_thermal_link_count",
    "physics_engine_interzone_thermal_flow_record_count",
    "physics_engine_has_airflow_network",
    "physics_engine_has_co2_step_result",
    "physics_engine_has_moisture_step_result",
    "physics_engine_has_acoustic_step_result",
    "interzone_thermal_flow_record_count",
    "interzone_airflow_record_count",
    "window_airflow_record_count",
]

BUILDING_SOLAR_DAYLIGHT_LIGHTING_COLUMNS = [
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

BUILDING_ACOUSTIC_COLUMNS = [
    "has_acoustic_step_result",
    "average_zone_indoor_noise",
    "max_zone_indoor_noise",
    "average_zone_indoor_noise_db",
    "max_zone_indoor_noise_db",
    "total_local_noise_source_count",
]

BUILDING_DEBUG_COLUMNS = (
    BUILDING_INTERNAL_SOURCE_COLUMNS
    + BUILDING_PHYSICS_SUMMARY_COLUMNS
    + BUILDING_ENGINE_STATUS_COLUMNS
    + BUILDING_SOLAR_DAYLIGHT_LIGHTING_COLUMNS
    + BUILDING_ACOUSTIC_COLUMNS
)

BUILDING_TIMESTEP_STANDARD_COLUMNS = (
    BUILDING_CORE_COLUMNS
    + BUILDING_ENERGY_COLUMNS
)

BUILDING_TIMESTEP_DEBUG_COLUMNS = (
    BUILDING_TIMESTEP_STANDARD_COLUMNS
    + BUILDING_DEBUG_COLUMNS
)

BUILDING_TIMESTEP_YEARLY_SAFE_COLUMNS = (
    BUILDING_TIMESTEP_STANDARD_COLUMNS
    + BUILDING_ENGINE_STATUS_COLUMNS
)

OUTPUT_SCHEMA_GROUPS = {
    "zone_core": ZONE_CORE_COLUMNS,
    "zone_state": ZONE_STATE_COLUMNS,
    "zone_control": ZONE_CONTROL_COLUMNS,
    "zone_hvac_power": ZONE_HVAC_POWER_COLUMNS,
    "zone_energy": ZONE_ENERGY_COLUMNS,
    "zone_thermal": ZONE_THERMAL_COLUMNS,
    "zone_airflow": ZONE_AIRFLOW_COLUMNS,
    "zone_air_quality": ZONE_AIR_QUALITY_COLUMNS,
    "zone_moisture": ZONE_MOISTURE_COLUMNS,
    "zone_window": ZONE_WINDOW_COLUMNS,
    "window_detail_timestep": WINDOW_DETAIL_TIMESTEP_COLUMNS,
    "zone_daylight_lighting": ZONE_DAYLIGHT_LIGHTING_COLUMNS,
    "zone_solar": ZONE_SOLAR_COLUMNS,
    "zone_internal_source": ZONE_INTERNAL_SOURCE_COLUMNS,
    "zone_interzone_thermal": ZONE_INTERZONE_THERMAL_COLUMNS,
    "interzone_thermal_timestep": INTERZONE_THERMAL_TIMESTEP_COLUMNS,
    "interzone_airflow_timestep": INTERZONE_AIRFLOW_TIMESTEP_COLUMNS,
    "zone_acoustic": ZONE_ACOUSTIC_COLUMNS,
    "zone_engine_status": ZONE_ENGINE_STATUS_COLUMNS,
    "zone_debug": ZONE_DEBUG_COLUMNS,
    "zone_timestep_standard": ZONE_TIMESTEP_STANDARD_COLUMNS,
    "zone_timestep_debug": ZONE_TIMESTEP_DEBUG_COLUMNS,
    "zone_timestep_yearly_safe": ZONE_TIMESTEP_YEARLY_SAFE_COLUMNS,

    "dwelling_core": DWELLING_CORE_COLUMNS,
    "dwelling_energy": DWELLING_ENERGY_COLUMNS,
    "dwelling_debug": DWELLING_DEBUG_COLUMNS,
    "dwelling_timestep_standard": DWELLING_TIMESTEP_STANDARD_COLUMNS,
    "dwelling_timestep_debug": DWELLING_TIMESTEP_DEBUG_COLUMNS,
    "dwelling_timestep_yearly_safe": DWELLING_TIMESTEP_YEARLY_SAFE_COLUMNS,

    "building_core": BUILDING_CORE_COLUMNS,
    "building_energy": BUILDING_ENERGY_COLUMNS,
    "building_internal_source": BUILDING_INTERNAL_SOURCE_COLUMNS,
    "building_engine_status": BUILDING_ENGINE_STATUS_COLUMNS,
    "building_solar_daylight_lighting": BUILDING_SOLAR_DAYLIGHT_LIGHTING_COLUMNS,
    "building_acoustic": BUILDING_ACOUSTIC_COLUMNS,
    "building_debug": BUILDING_DEBUG_COLUMNS,
    "building_timestep_standard": BUILDING_TIMESTEP_STANDARD_COLUMNS,
    "building_timestep_debug": BUILDING_TIMESTEP_DEBUG_COLUMNS,
    "building_timestep_yearly_safe": BUILDING_TIMESTEP_YEARLY_SAFE_COLUMNS,
    "building_physics_summary": BUILDING_PHYSICS_SUMMARY_COLUMNS,
}


def unique_columns(columns):
    out = []

    for column in columns:
        if column not in out:
            out.append(column)

    return out

def csv_safe_value(value):
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )

    return value


def csv_safe_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    for col in out.columns:
        if out[col].map(lambda value: isinstance(value, (dict, list, tuple))).any():
            out[col] = out[col].map(csv_safe_value)

    return out

def output_columns_for_record_type(
    record_type,
    mode=OUTPUT_MODE_STANDARD,
):
    record_type = str(record_type).strip().lower()
    mode = str(mode).strip().lower()

    if mode not in VALID_OUTPUT_MODES:
        raise ValueError(
            "Invalid output mode: "
            + str(mode)
            + ". Valid modes: "
            + str(sorted(VALID_OUTPUT_MODES))
        )

    if record_type == "zone":
        if mode == OUTPUT_MODE_DEBUG:
            return unique_columns(ZONE_TIMESTEP_DEBUG_COLUMNS)

        if mode == OUTPUT_MODE_MINIMAL:
            return unique_columns(ZONE_TIMESTEP_YEARLY_SAFE_COLUMNS)

        return unique_columns(ZONE_TIMESTEP_STANDARD_COLUMNS)

    if record_type == "dwelling":
        if mode == OUTPUT_MODE_DEBUG:
            return unique_columns(DWELLING_TIMESTEP_DEBUG_COLUMNS)

        if mode == OUTPUT_MODE_MINIMAL:
            return unique_columns(DWELLING_TIMESTEP_YEARLY_SAFE_COLUMNS)

        return unique_columns(DWELLING_TIMESTEP_STANDARD_COLUMNS)

    if record_type == "building":
        if mode == OUTPUT_MODE_DEBUG:
            return unique_columns(BUILDING_TIMESTEP_DEBUG_COLUMNS)

        if mode == OUTPUT_MODE_MINIMAL:
            return unique_columns(BUILDING_TIMESTEP_YEARLY_SAFE_COLUMNS)

        return unique_columns(BUILDING_TIMESTEP_STANDARD_COLUMNS)

    raise ValueError(
        "Invalid record_type: "
        + str(record_type)
        + ". Expected 'zone', 'dwelling', or 'building'."
    )

def standardize_interzone_thermal_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if df.empty:
        return df

    if "connection_id" not in df.columns and "zone_connection_id" in df.columns:
        df["connection_id"] = df["zone_connection_id"]

    if "zone_connection_id" not in df.columns and "connection_id" in df.columns:
        df["zone_connection_id"] = df["connection_id"]

    if "open_fraction" not in df.columns and "opening_fraction" in df.columns:
        df["open_fraction"] = df["opening_fraction"]

    if "opening_fraction" not in df.columns and "open_fraction" in df.columns:
        df["opening_fraction"] = df["open_fraction"]

    return df

def standardize_window_detail_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if df.empty:
        return df

    if "window_id" not in df.columns and "boundary_connection_id" in df.columns:
        df["window_id"] = df["boundary_connection_id"]

    if "boundary_connection_id" not in df.columns and "window_id" in df.columns:
        df["boundary_connection_id"] = df["window_id"]

    if "solar_gain_w" not in df.columns:
        df["solar_gain_w"] = 0.0

    if "daylight_contribution_lux" not in df.columns:
        df["daylight_contribution_lux"] = 0.0

    if "effective_solar_area_m2" not in df.columns:
        if "area_m2" in df.columns and "effective_solar_factor" in df.columns:
            df["effective_solar_area_m2"] = (
                pd.to_numeric(df["area_m2"], errors="coerce").fillna(0.0)
                * pd.to_numeric(df["effective_solar_factor"], errors="coerce").fillna(0.0)
            )
        else:
            df["effective_solar_area_m2"] = 0.0

    if "effective_daylight_area_m2" not in df.columns:
        if "area_m2" in df.columns and "effective_visible_transmittance" in df.columns:
            df["effective_daylight_area_m2"] = (
                pd.to_numeric(df["area_m2"], errors="coerce").fillna(0.0)
                * pd.to_numeric(
                    df["effective_visible_transmittance"],
                    errors="coerce",
                ).fillna(0.0)
            )
        else:
            df["effective_daylight_area_m2"] = 0.0

    if "curtain_open" not in df.columns:
        df["curtain_open"] = True

    if "opening_fraction" not in df.columns:
        df["opening_fraction"] = 0.0

    return df

def standardize_interzone_airflow_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if df.empty:
        return df

    if "connection_id" not in df.columns and "zone_connection_id" in df.columns:
        df["connection_id"] = df["zone_connection_id"]

    if "zone_connection_id" not in df.columns and "connection_id" in df.columns:
        df["zone_connection_id"] = df["connection_id"]

    if "airflow_a_to_b_m3_h" not in df.columns and "flow_a_to_b_m3_h" in df.columns:
        df["airflow_a_to_b_m3_h"] = df["flow_a_to_b_m3_h"]

    if "airflow_b_to_a_m3_h" not in df.columns and "flow_b_to_a_m3_h" in df.columns:
        df["airflow_b_to_a_m3_h"] = df["flow_b_to_a_m3_h"]

    if "flow_a_to_b_m3_h" not in df.columns and "airflow_a_to_b_m3_h" in df.columns:
        df["flow_a_to_b_m3_h"] = df["airflow_a_to_b_m3_h"]

    if "flow_b_to_a_m3_h" not in df.columns and "airflow_b_to_a_m3_h" in df.columns:
        df["flow_b_to_a_m3_h"] = df["airflow_b_to_a_m3_h"]

    if "airflow_a_to_b_m3_s" not in df.columns and "flow_a_to_b_m3_s" in df.columns:
        df["airflow_a_to_b_m3_s"] = df["flow_a_to_b_m3_s"]

    if "airflow_b_to_a_m3_s" not in df.columns and "flow_b_to_a_m3_s" in df.columns:
        df["airflow_b_to_a_m3_s"] = df["flow_b_to_a_m3_s"]

    if "mixing_exchange_m3_h" not in df.columns:
        if "mixing_flow_m3_h" in df.columns:
            df["mixing_exchange_m3_h"] = df["mixing_flow_m3_h"]
        elif (
            "airflow_a_to_b_m3_h" in df.columns
            and "airflow_b_to_a_m3_h" in df.columns
        ):
            df["mixing_exchange_m3_h"] = df[
                [
                    "airflow_a_to_b_m3_h",
                    "airflow_b_to_a_m3_h",
                ]
            ].max(axis=1)

    if "mixing_flow_m3_h" not in df.columns and "mixing_exchange_m3_h" in df.columns:
        df["mixing_flow_m3_h"] = df["mixing_exchange_m3_h"]

    if "mixing_exchange_m3_s" not in df.columns and "mixing_exchange_m3_h" in df.columns:
        df["mixing_exchange_m3_s"] = df["mixing_exchange_m3_h"] / 3600.0

    if "open_fraction" not in df.columns and "opening_fraction" in df.columns:
        df["open_fraction"] = df["opening_fraction"]

    if "opening_fraction" not in df.columns and "open_fraction" in df.columns:
        df["opening_fraction"] = df["open_fraction"]

    return df
def missing_output_columns(
    df,
    record_type,
    mode=OUTPUT_MODE_STANDARD,
):
    expected_columns = output_columns_for_record_type(
        record_type=record_type,
        mode=mode,
    )

    return [
        column
        for column in expected_columns
        if column not in df.columns
    ]

# ============================================================
# OUTPUT VALIDATION HELPERS
# ============================================================

VALIDATION_DEFAULT_TOLERANCE_WH = 1e-6
VALID_PHYSICS_PATH_VALUES = [
    "engine",
    "legacy_fallback_explicit",
    "legacy_fallback_after_engine_error",
]

ZONE_REQUIRED_NUMERIC_COLUMNS = [
    "day",
    "hour",
    "number_of_people",
    "indoor_temp_c",
    "indoor_mass_temp_c",
    "co2_ppm",
    "indoor_daylight",
    "indoor_noise",
    "indoor_relative_humidity_percent",
    "indoor_humidity_ratio_kg_kg",
    "heating_delivered_power_w",
    "cooling_delivered_power_w",
    "lighting_power_w",
    "ventilation_flow_m3_h",
    "ventilation_fan_power_w",
    "heating_delivered_energy_wh",
    "cooling_delivered_energy_wh",
    "heating_energy_wh",
    "cooling_energy_wh",
    "ventilation_fan_energy_wh",
    "lighting_energy_wh",
    "appliance_energy_wh",
    "hvac_delivered_energy_wh",
    "hvac_input_energy_wh",
    "total_energy_wh",
]


ZONE_DEBUG_NUMERIC_COLUMNS = [
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
    "airflow_infiltration_flow_m3_h",
    "airflow_mechanical_ventilation_flow_m3_h",
    "airflow_window_flow_m3_h",
    "airflow_outdoor_exchange_m3_h",
    "airflow_interzone_exchange_m3_h",
    "airflow_total_exchange_m3_h",
    "old_co2_ppm",
    "new_co2_ppm",
    "co2_generation_m3_h",
    "window_count",
    "window_curtain_open_count",
    "window_curtain_closed_count",
    "window_solar_alignment_factor_max",
    "window_daylight_alignment_factor_max",
    "window_effective_solar_factor_sum",
    "window_effective_visible_transmittance_sum",
    "solar_gain_w",
    "solar_gain_wh",
    "daylight_illuminance_lux",
    "indoor_illuminance_lux",
    "artificial_lighting_illuminance_lux",
    "lighting_result_power_w",
    "lighting_result_energy_wh",
    "internal_source_record_count",
    "internal_average_sensible_heat_w",
    "internal_average_latent_heat_w",
    "internal_average_electricity_power_w",
    "internal_electricity_wh",
    "internal_average_co2_generation_m3_h",
    "internal_average_moisture_generation_kg_h",
    "total_internal_gain_w",
    "total_internal_gain_wh",
    "interzone_thermal_link_count",
    "interzone_thermal_total_h_w_k",
    "interzone_heat_gain_w",
    "interzone_heat_loss_w",
    "interzone_net_heat_gain_w",
    "indoor_noise_db",
    "background_noise_db",
    "outdoor_noise_db",
    "local_noise_source_db",
    "local_noise_source_count",
    "acoustic_discomfort_input",
]


ZONE_NORMALIZED_COLUMNS = [
    "indoor_daylight",
    "indoor_noise",
    "heating_power_fraction",
    "cooling_power_fraction",
    "command_heating_power_fraction",
    "command_cooling_power_fraction",
    "command_window_opening_fraction",
    "old_indoor_daylight",
    "new_indoor_daylight",
    "proposed_indoor_daylight",
    "old_indoor_noise",
    "new_indoor_noise",
    "proposed_indoor_noise",
    "window_solar_alignment_factor_max",
    "window_daylight_alignment_factor_max",
    "window_effective_solar_factor_max",
    "window_effective_visible_transmittance_max",
    "lighting_result_dimming_fraction",
    "acoustic_discomfort_input",
]


DWELLING_REQUIRED_NUMERIC_COLUMNS = [
    "day",
    "hour",
    "total_occupancy",
    "private_zone_count",
    "heating_energy_wh",
    "cooling_energy_wh",
    "lighting_energy_wh",
    "appliance_energy_wh",
    "total_energy_wh",
    "heating_delivered_energy_wh",
    "cooling_delivered_energy_wh",
    "ventilation_fan_energy_wh",
    "hvac_delivered_energy_wh",
    "hvac_input_energy_wh",
]


DWELLING_DEBUG_NUMERIC_COLUMNS = [
    "zone_count",
    "mean_indoor_temp_c",
    "min_indoor_temp_c",
    "max_indoor_temp_c",
    "mean_indoor_mass_temp_c",
    "mean_co2_ppm",
    "max_co2_ppm",
    "mean_indoor_daylight",
    "mean_indoor_noise",
    "total_solar_gain_wh",
    "total_internal_electricity_wh",
    "total_internal_average_sensible_heat_w",
    "mean_internal_average_sensible_heat_w",
    "total_internal_sensible_heat_wh",
    "total_internal_gain_wh",
    "total_ventilation_flow_m3_h",
    "average_ventilation_flow_m3_h",
    "total_airflow_outdoor_exchange_m3_h",
    "total_airflow_interzone_exchange_m3_h",
    "total_local_noise_source_count",
    "zone_total_energy_wh",
    "energy_balance_residual_wh",
]


DWELLING_NORMALIZED_COLUMNS = [
    "mean_indoor_daylight",
    "mean_indoor_noise",
]


BUILDING_REQUIRED_NUMERIC_COLUMNS = [
    "day",
    "hour",
    "number_of_dwellings",
    "number_of_zones",
    "private_zone_count",
    "shared_zone_count",
    "total_occupancy",
    "private_zone_energy_wh",
    "shared_zone_energy_wh",
    "private_total_energy_wh",
    "shared_total_energy_wh",
    "zone_total_energy_wh",
    "heating_energy_wh",
    "cooling_energy_wh",
    "lighting_energy_wh",
    "appliance_energy_wh",
    "shared_system_energy_wh",
    "total_energy_wh",
    "heating_delivered_energy_wh",
    "cooling_delivered_energy_wh",
    "ventilation_fan_energy_wh",
    "hvac_delivered_energy_wh",
    "hvac_input_energy_wh",
    "building_energy_result_total_energy_wh",
    "building_zone_energy_balance_residual_wh",
]


BUILDING_DEBUG_NUMERIC_COLUMNS = [
    "zone_count",
    "mean_indoor_temp_c",
    "min_indoor_temp_c",
    "max_indoor_temp_c",
    "mean_indoor_mass_temp_c",
    "mean_co2_ppm",
    "max_co2_ppm",
    "mean_indoor_daylight",
    "mean_indoor_noise",
    "total_solar_gain_wh",
    "total_internal_electricity_wh",
    "total_internal_average_sensible_heat_w",
    "mean_internal_average_sensible_heat_w",
    "total_internal_sensible_heat_wh",
    "total_internal_gain_wh",
    "total_ventilation_flow_m3_h",
    "average_ventilation_flow_m3_h",
    "total_airflow_outdoor_exchange_m3_h",
    "total_airflow_interzone_exchange_m3_h",
    "total_local_noise_source_count",
    "internal_source_record_count",
    "internal_total_electricity_wh",
    "internal_total_average_sensible_heat_w",
    "internal_total_co2_generation_m3_h",
    "internal_total_moisture_generation_kg_h",
    "interzone_thermal_flow_record_count",
    "interzone_airflow_record_count",
    "window_airflow_record_count",
]


BUILDING_NORMALIZED_COLUMNS = [
    "mean_indoor_daylight",
    "mean_indoor_noise",
]


def _make_validation_result(name: str) -> Dict[str, Any]:
    return {
        "name": name,
        "ok": True,
        "row_count": 0,
        "errors": [],
        "warnings": [],
        "missing_columns": [],
        "non_finite_columns": {},
        "out_of_range_columns": {},
        "energy_checks": {},
    }


def _validation_error(result: Dict[str, Any], message: str) -> None:
    result["ok"] = False
    result["errors"].append(message)


def _validation_warning(result: Dict[str, Any], message: str) -> None:
    result["warnings"].append(message)


def _merge_validation_result(
    target: Dict[str, Any],
    child: Dict[str, Any],
    prefix: str,
) -> None:
    if not child.get("ok", False):
        target["ok"] = False

    for message in child.get("errors", []):
        target["errors"].append(prefix + ": " + message)

    for message in child.get("warnings", []):
        target["warnings"].append(prefix + ": " + message)

    if child.get("missing_columns"):
        target["missing_columns"].extend(
            [
                prefix + "." + str(column)
                for column in child.get("missing_columns", [])
            ]
        )

    for key, value in child.get("non_finite_columns", {}).items():
        target["non_finite_columns"][prefix + "." + key] = value

    for key, value in child.get("out_of_range_columns", {}).items():
        target["out_of_range_columns"][prefix + "." + key] = value

    if child.get("energy_checks"):
        target["energy_checks"][prefix] = child.get("energy_checks")


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(
        df[column],
        errors="coerce",
    )


def _non_finite_count(df: pd.DataFrame, column: str) -> int:
    values = _numeric_series(df, column)

    finite = values.map(
        lambda value: (
            pd.notna(value)
            and math.isfinite(float(value))
        )
    )

    return int((~finite).sum())


def _out_of_range_count(
    df: pd.DataFrame,
    column: str,
    lower: float = 0.0,
    upper: float = 1.0,
) -> int:
    values = _numeric_series(df, column)

    valid = values.map(
        lambda value: (
            pd.notna(value)
            and math.isfinite(float(value))
            and float(value) >= float(lower)
            and float(value) <= float(upper)
        )
    )

    return int((~valid).sum())


def _validate_required_columns(
    result: Dict[str, Any],
    df: pd.DataFrame,
    record_type: str,
    mode: str,
) -> None:
    missing = missing_output_columns(
        df=df,
        record_type=record_type,
        mode=mode,
    )

    result["missing_columns"] = missing

    if missing:
        _validation_error(
            result,
            "Missing required "
            + str(record_type)
            + " columns for mode="
            + str(mode)
            + ": "
            + str(missing),
        )


def _validate_numeric_finite_columns(
    result: Dict[str, Any],
    df: pd.DataFrame,
    columns: List[str],
) -> None:
    for column in unique_columns(columns):
        if column not in df.columns:
            continue

        bad_count = _non_finite_count(df, column)

        if bad_count > 0:
            result["non_finite_columns"][column] = bad_count
            _validation_error(
                result,
                "Column "
                + column
                + " has "
                + str(bad_count)
                + " non-finite values.",
            )


def _validate_normalized_columns(
    result: Dict[str, Any],
    df: pd.DataFrame,
    columns: List[str],
) -> None:
    for column in unique_columns(columns):
        if column not in df.columns:
            continue

        bad_count = _out_of_range_count(
            df=df,
            column=column,
            lower=0.0,
            upper=1.0,
        )

        if bad_count > 0:
            result["out_of_range_columns"][column] = {
                "bad_count": bad_count,
                "expected_min": 0.0,
                "expected_max": 1.0,
            }

            _validation_error(
                result,
                "Column "
                + column
                + " has "
                + str(bad_count)
                + " values outside [0, 1].",
            )

def _validate_allowed_values(
    result: Dict[str, Any],
    df: pd.DataFrame,
    column: str,
    allowed_values: List[str],
) -> None:
    if column not in df.columns:
        return

    allowed = set(
        str(value)
        for value in allowed_values
    )

    bad_count = 0
    bad_values = []

    for value in df[column].tolist():
        if pd.isna(value):
            bad_count += 1

            if "None" not in bad_values:
                bad_values.append("None")

            continue

        text = str(value)

        if text not in allowed:
            bad_count += 1

            if text not in bad_values:
                bad_values.append(text)

    if bad_count > 0:
        result["out_of_range_columns"][column] = {
            "bad_count": bad_count,
            "allowed_values": list(allowed_values),
            "bad_values": bad_values,
        }

        _validation_error(
            result,
            "Column "
            + column
            + " has "
            + str(bad_count)
            + " invalid values. Allowed values: "
            + str(allowed_values)
            + ". Bad values: "
            + str(bad_values),
        )

def validate_zone_timestep_record_schema(
    df: pd.DataFrame,
    mode: str = OUTPUT_MODE_DEBUG,
) -> Dict[str, Any]:
    result = _make_validation_result("zone_timestep_schema")
    result["row_count"] = 0 if df is None else int(len(df))

    if df is None:
        _validation_error(result, "Zone dataframe is None.")
        return result

    if df.empty:
        _validation_warning(result, "Zone dataframe is empty.")
        return result

    _validate_required_columns(
        result=result,
        df=df,
        record_type="zone",
        mode=mode,
    )

    numeric_columns = list(ZONE_REQUIRED_NUMERIC_COLUMNS)

    if str(mode).strip().lower() == OUTPUT_MODE_DEBUG:
        numeric_columns = numeric_columns + ZONE_DEBUG_NUMERIC_COLUMNS

    _validate_numeric_finite_columns(
        result=result,
        df=df,
        columns=numeric_columns,
    )

    _validate_normalized_columns(
        result=result,
        df=df,
        columns=ZONE_NORMALIZED_COLUMNS,
    )
    _validate_allowed_values(
        result=result,
        df=df,
        column="physics_path",
        allowed_values=VALID_PHYSICS_PATH_VALUES,
    )
    
    _validate_allowed_values(
        result=result,
        df=df,
        column="performance_path",
        allowed_values=VALID_PHYSICS_PATH_VALUES,
    )
    return result


def validate_dwelling_timestep_record_schema(
    df: pd.DataFrame,
    mode: str = OUTPUT_MODE_DEBUG,
) -> Dict[str, Any]:
    result = _make_validation_result("dwelling_timestep_schema")
    result["row_count"] = 0 if df is None else int(len(df))

    if df is None:
        _validation_error(result, "Dwelling dataframe is None.")
        return result

    if df.empty:
        _validation_warning(result, "Dwelling dataframe is empty.")
        return result

    _validate_required_columns(
        result=result,
        df=df,
        record_type="dwelling",
        mode=mode,
    )

    numeric_columns = list(DWELLING_REQUIRED_NUMERIC_COLUMNS)

    if str(mode).strip().lower() == OUTPUT_MODE_DEBUG:
        numeric_columns = numeric_columns + DWELLING_DEBUG_NUMERIC_COLUMNS

    _validate_numeric_finite_columns(
        result=result,
        df=df,
        columns=numeric_columns,
    )

    _validate_normalized_columns(
        result=result,
        df=df,
        columns=DWELLING_NORMALIZED_COLUMNS,
    )

    return result


def validate_building_timestep_record_schema(
    df: pd.DataFrame,
    mode: str = OUTPUT_MODE_DEBUG,
) -> Dict[str, Any]:
    result = _make_validation_result("building_timestep_schema")
    result["row_count"] = 0 if df is None else int(len(df))

    if df is None:
        _validation_error(result, "Building dataframe is None.")
        return result

    if df.empty:
        _validation_warning(result, "Building dataframe is empty.")
        return result

    _validate_required_columns(
        result=result,
        df=df,
        record_type="building",
        mode=mode,
    )

    numeric_columns = list(BUILDING_REQUIRED_NUMERIC_COLUMNS)

    if str(mode).strip().lower() == OUTPUT_MODE_DEBUG:
        numeric_columns = numeric_columns + BUILDING_DEBUG_NUMERIC_COLUMNS

    _validate_numeric_finite_columns(
        result=result,
        df=df,
        columns=numeric_columns,
    )

    _validate_normalized_columns(
        result=result,
        df=df,
        columns=BUILDING_NORMALIZED_COLUMNS,
    )

    return result


def _energy_identity_check(
    df: pd.DataFrame,
    total_column: str,
    component_columns: List[str],
    tolerance_wh: float,
) -> Dict[str, Any]:
    check = {
        "ok": True,
        "checked_rows": 0,
        "bad_rows": 0,
        "max_abs_residual_wh": 0.0,
        "missing_columns": [],
    }

    required = [total_column] + list(component_columns)

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:
        check["ok"] = False
        check["missing_columns"] = missing
        return check

    total = _numeric_series(df, total_column)
    components = None

    for column in component_columns:
        series = _numeric_series(df, column)

        if components is None:
            components = series
        else:
            components = components + series

    residual = total - components
    abs_residual = residual.abs()

    bad_mask = abs_residual.isna() | (abs_residual > float(tolerance_wh))

    check["checked_rows"] = int(len(df))
    check["bad_rows"] = int(bad_mask.sum())

    if len(abs_residual.dropna()) > 0:
        check["max_abs_residual_wh"] = float(abs_residual.dropna().max())

    if check["bad_rows"] > 0:
        check["ok"] = False

    return check


def _common_group_columns(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    candidate_columns: List[str],
) -> List[str]:
    return [
        column
        for column in candidate_columns
        if column in left_df.columns and column in right_df.columns
    ]


def _compare_grouped_energy(
    source_df: pd.DataFrame,
    target_df: pd.DataFrame,
    source_total_column: str,
    target_total_column: str,
    candidate_group_columns: List[str],
    source_name: str,
    target_name: str,
    tolerance_wh: float,
) -> Dict[str, Any]:
    check = {
        "ok": True,
        "checked_rows": 0,
        "bad_rows": 0,
        "max_abs_residual_wh": 0.0,
        "group_columns": [],
        "missing_columns": [],
        "source_name": source_name,
        "target_name": target_name,
    }

    missing = []

    if source_total_column not in source_df.columns:
        missing.append(source_name + "." + source_total_column)

    if target_total_column not in target_df.columns:
        missing.append(target_name + "." + target_total_column)

    if missing:
        check["ok"] = False
        check["missing_columns"] = missing
        return check

    group_cols = _common_group_columns(
        source_df,
        target_df,
        candidate_group_columns,
    )

    if not group_cols:
        check["ok"] = False
        check["missing_columns"] = ["no_common_group_columns"]
        return check

    check["group_columns"] = group_cols

    source = source_df.copy()
    target = target_df.copy()

    source[source_total_column] = pd.to_numeric(
        source[source_total_column],
        errors="coerce",
    )

    target[target_total_column] = pd.to_numeric(
        target[target_total_column],
        errors="coerce",
    )

    source_grouped = (
        source
        .groupby(group_cols, as_index=False)[source_total_column]
        .sum()
        .rename(columns={source_total_column: "source_total_wh"})
    )

    target_grouped = (
        target
        .groupby(group_cols, as_index=False)[target_total_column]
        .sum()
        .rename(columns={target_total_column: "target_total_wh"})
    )

    merged = target_grouped.merge(
        source_grouped,
        on=group_cols,
        how="left",
    )

    residual = merged["target_total_wh"] - merged["source_total_wh"]
    abs_residual = residual.abs()

    bad_mask = (
        abs_residual.isna()
        | (abs_residual > float(tolerance_wh))
    )

    check["checked_rows"] = int(len(merged))
    check["bad_rows"] = int(bad_mask.sum())

    if len(abs_residual.dropna()) > 0:
        check["max_abs_residual_wh"] = float(abs_residual.dropna().max())

    if check["bad_rows"] > 0:
        check["ok"] = False

    return check


def validate_energy_consistency(
    zone_df: pd.DataFrame,
    dwelling_df: Optional[pd.DataFrame] = None,
    building_df: Optional[pd.DataFrame] = None,
    tolerance_wh: float = VALIDATION_DEFAULT_TOLERANCE_WH,
) -> Dict[str, Any]:
    result = _make_validation_result("energy_consistency")

    if zone_df is None:
        _validation_error(result, "zone_df is None.")
        return result

    if zone_df.empty:
        _validation_warning(result, "zone_df is empty.")
        return result

    # ------------------------------------------------------------
    # 1. Zone identity:
    # total_energy_wh = appliance + lighting + hvac_input
    # ------------------------------------------------------------
    zone_total_check = _energy_identity_check(
        df=zone_df,
        total_column="total_energy_wh",
        component_columns=[
            "appliance_energy_wh",
            "lighting_energy_wh",
            "hvac_input_energy_wh",
        ],
        tolerance_wh=tolerance_wh,
    )

    result["energy_checks"]["zone_total_identity"] = zone_total_check

    if not zone_total_check["ok"]:
        _validation_error(
            result,
            "Zone total energy identity failed.",
        )

    # ------------------------------------------------------------
    # 2. HVAC input identity:
    # hvac_input = heating input + cooling input + ventilation fan
    # ------------------------------------------------------------
    hvac_input_check = _energy_identity_check(
        df=zone_df,
        total_column="hvac_input_energy_wh",
        component_columns=[
            "heating_energy_wh",
            "cooling_energy_wh",
            "ventilation_fan_energy_wh",
        ],
        tolerance_wh=tolerance_wh,
    )

    result["energy_checks"]["zone_hvac_input_identity"] = hvac_input_check

    if not hvac_input_check["ok"]:
        _validation_error(
            result,
            "Zone HVAC input energy identity failed.",
        )

    # ------------------------------------------------------------
    # 3. HVAC delivered identity:
    # hvac_delivered = heating delivered + cooling delivered
    # ------------------------------------------------------------
    hvac_delivered_check = _energy_identity_check(
        df=zone_df,
        total_column="hvac_delivered_energy_wh",
        component_columns=[
            "heating_delivered_energy_wh",
            "cooling_delivered_energy_wh",
        ],
        tolerance_wh=tolerance_wh,
    )

    result["energy_checks"]["zone_hvac_delivered_identity"] = hvac_delivered_check

    if not hvac_delivered_check["ok"]:
        _validation_error(
            result,
            "Zone HVAC delivered energy identity failed.",
        )

    # ------------------------------------------------------------
    # 4. Dwelling rows equal sum of private zone rows.
    # ------------------------------------------------------------
    if dwelling_df is not None and not dwelling_df.empty:
        zone_for_dwelling = zone_df.copy()

        if "zone_scope" in zone_for_dwelling.columns:
            zone_for_dwelling = zone_for_dwelling[
                zone_for_dwelling["zone_scope"].astype(str) == "private"
            ]

        dwelling_check = _compare_grouped_energy(
            source_df=zone_for_dwelling,
            target_df=dwelling_df,
            source_total_column="total_energy_wh",
            target_total_column="total_energy_wh",
            candidate_group_columns=[
                "step",
                "day",
                "hour",
                "building_id",
                "dwelling_id",
            ],
            source_name="zone_df_private",
            target_name="dwelling_df",
            tolerance_wh=tolerance_wh,
        )

        result["energy_checks"]["dwelling_equals_private_zone_sum"] = dwelling_check

        if not dwelling_check["ok"]:
            _validation_error(
                result,
                "Dwelling total energy does not match private-zone sum.",
            )

    # ------------------------------------------------------------
    # 5. Building rows equal sum of all zone rows.
    # ------------------------------------------------------------
    if building_df is not None and not building_df.empty:
        building_check = _compare_grouped_energy(
            source_df=zone_df,
            target_df=building_df,
            source_total_column="total_energy_wh",
            target_total_column="total_energy_wh",
            candidate_group_columns=[
                "step",
                "day",
                "hour",
                "building_id",
            ],
            source_name="zone_df",
            target_name="building_df",
            tolerance_wh=tolerance_wh,
        )

        result["energy_checks"]["building_equals_zone_sum"] = building_check

        if not building_check["ok"]:
            _validation_error(
                result,
                "Building total energy does not match zone sum.",
            )

    return result


def validate_building_output_dataframes(
    zone_df: pd.DataFrame,
    dwelling_df: Optional[pd.DataFrame] = None,
    building_df: Optional[pd.DataFrame] = None,
    mode: str = OUTPUT_MODE_DEBUG,
    tolerance_wh: float = VALIDATION_DEFAULT_TOLERANCE_WH,
) -> Dict[str, Any]:
    result = _make_validation_result("building_output_dataframes")

    zone_result = validate_zone_timestep_record_schema(
        df=zone_df,
        mode=mode,
    )

    _merge_validation_result(
        target=result,
        child=zone_result,
        prefix="zone",
    )

    if dwelling_df is not None:
        dwelling_result = validate_dwelling_timestep_record_schema(
            df=dwelling_df,
            mode=mode,
        )

        _merge_validation_result(
            target=result,
            child=dwelling_result,
            prefix="dwelling",
        )

    if building_df is not None:
        building_result = validate_building_timestep_record_schema(
            df=building_df,
            mode=mode,
        )

        _merge_validation_result(
            target=result,
            child=building_result,
            prefix="building",
        )

    energy_result = validate_energy_consistency(
        zone_df=zone_df,
        dwelling_df=dwelling_df,
        building_df=building_df,
        tolerance_wh=tolerance_wh,
    )

    _merge_validation_result(
        target=result,
        child=energy_result,
        prefix="energy",
    )

    return result

def output_schema_summary():
    return {
        "phase": OUTPUT_SCHEMA_PHASE,
        "source": OUTPUT_SCHEMA_SOURCE,
        "valid_output_modes": sorted(VALID_OUTPUT_MODES),
        "group_count": len(OUTPUT_SCHEMA_GROUPS),
        "groups": {
            group_name: {
                "column_count": len(unique_columns(columns)),
                "columns": unique_columns(columns),
            }
            for group_name, columns in OUTPUT_SCHEMA_GROUPS.items()
        },
    }
def save_debug_building_outputs(
    sim: Any,
    output_folder: str,
    prefix: str = "building",
    output_mode: str = OUTPUT_MODE_DEBUG,
    include_diagnostics: bool = True,
    include_long_records: bool = True,
    include_plots: bool = True,
    include_interzone_timestep_records: bool = True,
    include_window_detail_timestep_records: bool = True,
) -> Dict[str, Path]:
    """
    Save full timestep building outputs for debug runs.
    """
    if output_mode not in VALID_OUTPUT_MODES:
        raise ValueError("Invalid output_mode: " + str(output_mode))

    if not include_diagnostics:
        include_long_records = False
        include_interzone_timestep_records = False
        include_window_detail_timestep_records = False
        include_plots = False

    if output_mode == OUTPUT_MODE_MINIMAL:
        include_diagnostics = False
        include_long_records = False
        include_interzone_timestep_records = False
        include_window_detail_timestep_records = False
        include_plots = False

    if output_mode == OUTPUT_MODE_STANDARD:
        include_long_records = False
        include_interzone_timestep_records = False
        include_window_detail_timestep_records = False
    folder = _ensure_folder(output_folder)
    csv_folder = _ensure_folder(folder / "csv")
    plot_folder = _ensure_folder(folder / "plots")

    paths = {}

    zone_df = sim.building_zone_records_to_dataframe()
    dwelling_df = sim.building_dwelling_records_to_dataframe()
    building_df = sim.building_records_to_dataframe()
    if hasattr(sim, "building_interzone_thermal_records_to_dataframe"):
        interzone_thermal_df = sim.building_interzone_thermal_records_to_dataframe()
    else:
        interzone_thermal_df = pd.DataFrame()
    if hasattr(sim, "building_interzone_thermal_records_to_dataframe"):
        interzone_thermal_df = sim.building_interzone_thermal_records_to_dataframe()
    else:
        interzone_thermal_df = pd.DataFrame()
    if hasattr(sim, "building_interzone_airflow_records_to_dataframe"):
        interzone_airflow_df = sim.building_interzone_airflow_records_to_dataframe()
    else:
        interzone_airflow_df = pd.DataFrame()
    interzone_thermal_df = standardize_interzone_thermal_dataframe(
        interzone_thermal_df
    )

    interzone_airflow_df = standardize_interzone_airflow_dataframe(
        interzone_airflow_df
    )
    if hasattr(sim, "building_window_airflow_records_to_dataframe"):
        window_airflow_df = sim.building_window_airflow_records_to_dataframe()
    else:
        window_airflow_df = pd.DataFrame()
    bridge_df = sim.building_control_bridge_records_to_dataframe()
    action_df = sim.building_action_event_records_to_dataframe()
    internal_source_df = sim.building_internal_source_records_to_dataframe()
    internal_source_zone_df = sim.building_internal_source_zone_records_to_dataframe()
    internal_source_building_df = sim.building_internal_source_building_records_to_dataframe()
    window_detail_df = standardize_window_detail_dataframe(
        window_airflow_df
    )
    zone_path = csv_folder / (prefix + "_zone_timestep.csv")
    dwelling_path = csv_folder / (prefix + "_dwelling_timestep.csv")
    building_path = csv_folder / (prefix + "_building_timestep.csv")

    csv_safe_dataframe(zone_df).to_csv(zone_path, index=False)
    csv_safe_dataframe(dwelling_df).to_csv(dwelling_path, index=False)
    csv_safe_dataframe(building_df).to_csv(building_path, index=False)

    paths["zone_timestep_csv"] = zone_path
    paths["dwelling_timestep_csv"] = dwelling_path
    paths["building_timestep_csv"] = building_path
    if include_interzone_timestep_records and not interzone_thermal_df.empty:
        interzone_thermal_path = csv_folder / (
            prefix + "_interzone_thermal_timestep.csv"
        )

        csv_safe_dataframe(interzone_thermal_df).to_csv(
            interzone_thermal_path,
            index=False,
        )

        paths["interzone_thermal_timestep_csv"] = interzone_thermal_path
    if include_interzone_timestep_records and not interzone_airflow_df.empty:
        interzone_airflow_path = csv_folder / (
            prefix + "_interzone_airflow_timestep.csv"
        )

        csv_safe_dataframe(interzone_airflow_df).to_csv(
            interzone_airflow_path,
            index=False,
        )

        paths["interzone_airflow_timestep_csv"] = interzone_airflow_path

    if include_window_detail_timestep_records and not window_detail_df.empty:
        window_detail_path = csv_folder / (
            prefix + "_window_detail_timestep.csv"
        )

        csv_safe_dataframe(window_detail_df).to_csv(
            window_detail_path,
            index=False,
        )

        paths["window_detail_timestep_csv"] = window_detail_path

    if include_window_detail_timestep_records and not window_airflow_df.empty:
        window_airflow_path = csv_folder / (
            prefix + "_window_airflow_timestep.csv"
        )

        csv_safe_dataframe(window_airflow_df).to_csv(
            window_airflow_path,
            index=False,
        )

        paths["window_airflow_timestep_csv"] = window_airflow_path
    if include_long_records and not bridge_df.empty:
        bridge_path = csv_folder / (prefix + "_control_bridge_timestep.csv")
        csv_safe_dataframe(bridge_df).to_csv(bridge_path, index=False)
        paths["control_bridge_csv"] = bridge_path

    if include_long_records and not action_df.empty:
        action_path = csv_folder / (prefix + "_action_events_timestep.csv")
        csv_safe_dataframe(action_df).to_csv(action_path, index=False)
        paths["action_events_csv"] = action_path

    if include_long_records and not zone_df.empty:
        _add_time_columns(zone_df)

        paths["zone_temperature_plot"] = _plot_zone_lines(
            df=zone_df,
            y_col="indoor_temp_c",
            y_label="Indoor temperature [°C]",
            path=plot_folder / (prefix + "_zone_temperature.png"),
        )

        paths["zone_co2_plot"] = _plot_zone_lines(
            df=zone_df,
            y_col="co2_ppm",
            y_label="CO2 [ppm]",
            path=plot_folder / (prefix + "_zone_co2.png"),
        )

        paths["occupancy_plot"] = _plot_zone_lines(
            df=zone_df,
            y_col="number_of_people",
            y_label="Number of people",
            path=plot_folder / (prefix + "_zone_occupancy.png"),
        )

        for state_col in [
            "heating_on",
            "cooling_on",
            "lights_on",
            "window_open",
        ]:
            if state_col in zone_df.columns:
                paths[state_col + "_plot"] = _plot_zone_state_lines(
                    df=zone_df,
                    state_col=state_col,
                    path=plot_folder / (prefix + "_" + state_col + ".png"),
                )

        paths["energy_by_zone_plot"] = _plot_energy_by_zone(
            zone_df=zone_df,
            path=plot_folder / (prefix + "_energy_by_zone.png"),
        )

    if not dwelling_df.empty:
        paths["energy_by_dwelling_plot"] = _plot_energy_by_dwelling(
            dwelling_df=dwelling_df,
            path=plot_folder / (prefix + "_energy_by_dwelling.png"),
        )

    if not building_df.empty:
        paths["energy_by_building_plot"] = _plot_energy_by_building(
            building_df=building_df,
            path=plot_folder / (prefix + "_energy_by_building.png"),
        )
    if not internal_source_df.empty:
        internal_source_path = csv_folder / (
            prefix + "_internal_source_records_timestep.csv"
        )
        csv_safe_dataframe(internal_source_df).to_csv(internal_source_path, index=False)
        paths["internal_source_records_csv"] = internal_source_path

    if not internal_source_zone_df.empty:
        internal_source_zone_path = csv_folder / (
            prefix + "_internal_source_zone_timestep.csv"
        )
        csv_safe_dataframe(internal_source_zone_df).to_csv(internal_source_zone_path, index=False)
        paths["internal_source_zone_csv"] = internal_source_zone_path

    if not internal_source_building_df.empty:
        internal_source_building_path = csv_folder / (
            prefix + "_internal_source_building_timestep.csv"
        )
        csv_safe_dataframe(internal_source_building_df).to_csv(internal_source_building_path, index=False)
        paths["internal_source_building_csv"] = internal_source_building_path
    return paths


def save_yearly_building_outputs(
    sim: Any,
    output_folder: str,
    prefix: str = "building",
    output_mode: str = OUTPUT_MODE_MINIMAL,
    include_timestep_diagnostics: bool = False,
    include_long_records: bool = False,
    include_interzone_summaries: bool = True,
    include_interzone_timestep_records: bool = False,
    include_window_detail_summaries: bool = True,
    include_window_detail_timestep_records: bool = False,
) -> Dict[str, Path]:
    """
    Save aggregated building outputs for yearly runs.

    Avoids heavy people/action timestep CSVs.
    """
    if output_mode not in VALID_OUTPUT_MODES:
        raise ValueError("Invalid output_mode: " + str(output_mode))

    if output_mode == OUTPUT_MODE_DEBUG:
        include_timestep_diagnostics = True
        include_long_records = True
        include_interzone_timestep_records = True
        include_window_detail_timestep_records = True

    if output_mode == OUTPUT_MODE_STANDARD:
        include_timestep_diagnostics = True
        include_long_records = False
        include_interzone_timestep_records = False
        include_window_detail_timestep_records = False

    if output_mode == OUTPUT_MODE_MINIMAL:
        include_timestep_diagnostics = False
        include_long_records = False
        include_interzone_timestep_records = False
        include_window_detail_timestep_records = False
    folder = _ensure_folder(output_folder)
    csv_folder = _ensure_folder(folder / "csv")
    plot_folder = _ensure_folder(folder / "plots")

    paths = {}

    zone_df = sim.building_zone_records_to_dataframe()
    dwelling_df = sim.building_dwelling_records_to_dataframe()
    building_df = sim.building_records_to_dataframe()
    if hasattr(sim, "building_interzone_thermal_records_to_dataframe"):
        interzone_thermal_df = sim.building_interzone_thermal_records_to_dataframe()
    else:
        interzone_thermal_df = pd.DataFrame()
    if hasattr(sim, "building_interzone_thermal_records_to_dataframe"):
        interzone_thermal_df = sim.building_interzone_thermal_records_to_dataframe()
    else:
        interzone_thermal_df = pd.DataFrame()
    if hasattr(sim, "building_interzone_airflow_records_to_dataframe"):
        interzone_airflow_df = sim.building_interzone_airflow_records_to_dataframe()
    else:
        interzone_airflow_df = pd.DataFrame()
    interzone_thermal_df = standardize_interzone_thermal_dataframe(
        interzone_thermal_df
    )

    interzone_airflow_df = standardize_interzone_airflow_dataframe(
        interzone_airflow_df
    )
    if hasattr(sim, "building_window_airflow_records_to_dataframe"):
        window_airflow_df = sim.building_window_airflow_records_to_dataframe()
    else:
        window_airflow_df = pd.DataFrame()
    window_detail_df = standardize_window_detail_dataframe(
        window_airflow_df
    )
    internal_source_zone_df = sim.building_internal_source_zone_records_to_dataframe()
    internal_source_building_df = sim.building_internal_source_building_records_to_dataframe()
    if include_interzone_timestep_records and not interzone_thermal_df.empty:
        interzone_thermal_path = csv_folder / (
            prefix + "_interzone_thermal_timestep.csv"
        )

        csv_safe_dataframe(interzone_thermal_df).to_csv(
            interzone_thermal_path,
            index=False,
        )

        paths["interzone_thermal_timestep_csv"] = interzone_thermal_path

    if include_interzone_timestep_records and not interzone_airflow_df.empty:
        interzone_airflow_path = csv_folder / (
            prefix + "_interzone_airflow_timestep.csv"
        )

        csv_safe_dataframe(interzone_airflow_df).to_csv(
            interzone_airflow_path,
            index=False,
        )

        paths["interzone_airflow_timestep_csv"] = interzone_airflow_path    
    if not zone_df.empty:
        _add_time_columns(zone_df)

        hourly_zone = make_hourly_zone_summary(zone_df)
        daily_zone = make_daily_zone_summary(zone_df)
        energy_by_zone = make_energy_by_zone(zone_df)
        control_hours_by_zone = make_control_active_hours_by_zone(zone_df)

        hourly_zone_path = csv_folder / (prefix + "_hourly_zone_summary.csv")
        daily_zone_path = csv_folder / (prefix + "_daily_zone_summary.csv")
        energy_by_zone_path = csv_folder / (prefix + "_energy_by_zone.csv")
        control_hours_path = csv_folder / (prefix + "_control_active_hours_by_zone.csv")

        csv_safe_dataframe(hourly_zone).to_csv(hourly_zone_path, index=False)
        csv_safe_dataframe(daily_zone).to_csv(daily_zone_path, index=False)
        csv_safe_dataframe(energy_by_zone).to_csv(energy_by_zone_path, index=False)
        csv_safe_dataframe(control_hours_by_zone).to_csv(control_hours_path, index=False)

        paths["hourly_zone_summary_csv"] = hourly_zone_path
        paths["daily_zone_summary_csv"] = daily_zone_path
        paths["energy_by_zone_csv"] = energy_by_zone_path
        paths["control_active_hours_by_zone_csv"] = control_hours_path

        paths["energy_by_zone_plot"] = _plot_energy_by_zone(
            zone_df=zone_df,
            path=plot_folder / (prefix + "_energy_by_zone.png"),
        )

        paths["control_active_hours_plot"] = _plot_control_active_hours_by_zone(
            control_df=control_hours_by_zone,
            path=plot_folder / (prefix + "_control_active_hours_by_zone.png"),
        )

    if not dwelling_df.empty:
        _add_time_columns(dwelling_df)

        daily_dwelling = make_daily_dwelling_summary(dwelling_df)
        energy_by_dwelling = make_energy_by_dwelling(dwelling_df)

        daily_dwelling_path = csv_folder / (prefix + "_daily_dwelling_summary.csv")
        energy_by_dwelling_path = csv_folder / (prefix + "_energy_by_dwelling.csv")

        csv_safe_dataframe(daily_dwelling).to_csv(daily_dwelling_path, index=False)
        csv_safe_dataframe(energy_by_dwelling).to_csv(energy_by_dwelling_path, index=False)

        paths["daily_dwelling_summary_csv"] = daily_dwelling_path
        paths["energy_by_dwelling_csv"] = energy_by_dwelling_path

        paths["energy_by_dwelling_plot"] = _plot_energy_by_dwelling(
            dwelling_df=dwelling_df,
            path=plot_folder / (prefix + "_energy_by_dwelling.png"),
        )

    if not building_df.empty:
        _add_time_columns(building_df)

        daily_building = make_daily_building_summary(building_df)
        energy_by_building = make_energy_by_building(building_df)

        daily_building_path = csv_folder / (prefix + "_daily_building_summary.csv")
        energy_by_building_path = csv_folder / (prefix + "_energy_by_building.csv")

        csv_safe_dataframe(daily_building).to_csv(daily_building_path, index=False)
        csv_safe_dataframe(energy_by_building).to_csv(energy_by_building_path, index=False)

        paths["daily_building_summary_csv"] = daily_building_path
        paths["energy_by_building_csv"] = energy_by_building_path

        paths["energy_by_building_plot"] = _plot_energy_by_building(
            building_df=building_df,
            path=plot_folder / (prefix + "_energy_by_building.png"),
        )
    if include_interzone_summaries and not interzone_airflow_df.empty:
        _add_time_columns(interzone_airflow_df)

        daily_interzone_airflow = make_daily_interzone_airflow_summary(
            interzone_airflow_df
        )

        if not daily_interzone_airflow.empty:
            interzone_airflow_summary_path = csv_folder / (
                prefix + "_daily_interzone_airflow_summary.csv"
            )

            csv_safe_dataframe(daily_interzone_airflow).to_csv(
                interzone_airflow_summary_path,
                index=False,
            )

            paths["daily_interzone_airflow_summary_csv"] = (
                interzone_airflow_summary_path
            )
    if include_window_detail_timestep_records and not window_detail_df.empty:
        window_detail_path = csv_folder / (
            prefix + "_window_detail_timestep.csv"
        )

        csv_safe_dataframe(window_detail_df).to_csv(
            window_detail_path,
            index=False,
        )

        paths["window_detail_timestep_csv"] = window_detail_path
        
    if include_window_detail_summaries and not window_airflow_df.empty:
        _add_time_columns(window_airflow_df)

        daily_window_airflow = make_daily_window_airflow_summary(
            window_airflow_df
        )

        if not daily_window_airflow.empty:
            window_airflow_summary_path = csv_folder / (
                prefix + "_daily_window_airflow_summary.csv"
            )

            csv_safe_dataframe(daily_window_airflow).to_csv(
                window_airflow_summary_path,
                index=False,
            )

            paths["daily_window_airflow_summary_csv"] = (
                window_airflow_summary_path
            )
            
    if not internal_source_zone_df.empty:
        _add_time_columns(internal_source_zone_df)

        group_cols = ["day", "zone_id"]

        value_cols = [
            col for col in [
                "average_sensible_heat_w",
                "average_electricity_power_w",
                "average_co2_generation_m3_h",
                "average_moisture_generation_kg_h",
                "electricity_wh",
                "moisture_generation_kg",
                "record_count",
            ]
            if col in internal_source_zone_df.columns
        ]

        if value_cols:
            daily_internal_zone = (
                internal_source_zone_df
                .groupby(group_cols)[value_cols]
                .mean()
                .reset_index()
            )

            daily_internal_zone_path = csv_folder / (
                prefix + "_daily_internal_source_zone_summary.csv"
            )

            csv_safe_dataframe(daily_internal_zone).to_csv(
                daily_internal_zone_path,
                index=False,
            )

            paths["daily_internal_source_zone_summary_csv"] = (
                daily_internal_zone_path
            )

    if not internal_source_building_df.empty:
        _add_time_columns(internal_source_building_df)

        value_cols = [
            col for col in [
                "record_count",
                "total_electricity_wh",
                "total_average_electricity_power_w",
                "total_average_sensible_heat_w",
                "total_co2_generation_m3_h",
                "average_total_moisture_generation_kg_h",
                "total_appliance_electricity_wh",
                "total_lighting_electricity_wh",
                "total_hvac_electricity_wh",
            ]
            if col in internal_source_building_df.columns
        ]

        if value_cols:
            daily_internal_building = (
                internal_source_building_df
                .groupby("day")[value_cols]
                .mean()
                .reset_index()
            )

            daily_internal_building_path = csv_folder / (
                prefix + "_daily_internal_source_building_summary.csv"
            )

            csv_safe_dataframe(daily_internal_building).to_csv(
                daily_internal_building_path,
                index=False,
            )

            paths["daily_internal_source_building_summary_csv"] = (
                daily_internal_building_path
            )

    if include_interzone_summaries and not interzone_thermal_df.empty:
        _add_time_columns(interzone_thermal_df)

        daily_interzone_thermal = make_daily_interzone_thermal_summary(
            interzone_thermal_df
        )

        interzone_thermal_summary_path = csv_folder / (
            prefix + "_daily_interzone_thermal_summary.csv"
        )

        csv_safe_dataframe(daily_interzone_thermal).to_csv(
            interzone_thermal_summary_path,
            index=False,
        )

        paths["daily_interzone_thermal_summary_csv"] = (
            interzone_thermal_summary_path
        )        
    return paths


# ============================================================
# SUMMARY TABLES
# ============================================================

def _optional_sum_agg(df: pd.DataFrame, columns: list) -> Dict[str, tuple]:
    return {
        col: (col, "sum")
        for col in columns
        if col in df.columns
    }


def _energy_agg_map(df: pd.DataFrame) -> Dict[str, tuple]:
    """
    Common energy aggregation map.

    Old energy columns are kept.
    New Phase 10.10 HVAC-accounting columns are added only if present.
    """

    agg_map = {}

    for col in [
        "heating_energy_wh",
        "cooling_energy_wh",
        "lighting_energy_wh",
        "appliance_energy_wh",
        "total_energy_wh",
    ]:
        if col in df.columns:
            agg_map[col] = (col, "sum")

    agg_map.update(
        _optional_sum_agg(
            df,
            [
                "heating_delivered_energy_wh",
                "cooling_delivered_energy_wh",
                "ventilation_fan_energy_wh",
                "hvac_delivered_energy_wh",
                "hvac_input_energy_wh",
            ],
        )
    )

    return agg_map

def _fallback_agg_map(df: pd.DataFrame) -> Dict[str, tuple]:
    agg_map = {}

    if "legacy_fallback_used" in df.columns:
        df["legacy_fallback_used"] = df["legacy_fallback_used"].astype(bool)
        agg_map["legacy_fallback_steps"] = ("legacy_fallback_used", "sum")

    return agg_map

def _ensure_zone_group_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    defaults = {
        "building_id": "unknown_building",
        "dwelling_id": "unknown_dwelling",
        "zone_id": "unknown_zone",
        "zone_scope": "unknown",
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    return df

def _ensure_dwelling_group_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    defaults = {
        "building_id": "unknown_building",
        "dwelling_id": "unknown_dwelling",
        "total_occupancy": 0.0,
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    return df


def _ensure_building_group_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    defaults = {
        "building_id": "unknown_building",
        "number_of_dwellings": 0,
        "total_occupancy": 0.0,
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    return df

def make_daily_interzone_thermal_summary(
    interzone_df: pd.DataFrame,
) -> pd.DataFrame:
    df = interzone_df.copy()
    _add_time_columns(df)

    group_cols = [
        col for col in [
            "building_id",
            "day",
            "link_id",
            "connection_id",
            "zone_a_id",
            "zone_b_id",
            "connection_type",
        ]
        if col in df.columns
    ]

    agg_map = {}

    if "h_w_k" in df.columns:
        agg_map["h_w_k_mean"] = ("h_w_k", "mean")
        agg_map["h_w_k_max"] = ("h_w_k", "max")

    if "open_fraction" in df.columns:
        agg_map["open_fraction_mean"] = ("open_fraction", "mean")
        agg_map["open_fraction_max"] = ("open_fraction", "max")

    if "q_to_zone_a_w" in df.columns:
        agg_map["q_to_zone_a_w_mean"] = ("q_to_zone_a_w", "mean")
        agg_map["q_to_zone_a_w_min"] = ("q_to_zone_a_w", "min")
        agg_map["q_to_zone_a_w_max"] = ("q_to_zone_a_w", "max")

    if "q_to_zone_b_w" in df.columns:
        agg_map["q_to_zone_b_w_mean"] = ("q_to_zone_b_w", "mean")
        agg_map["q_to_zone_b_w_min"] = ("q_to_zone_b_w", "min")
        agg_map["q_to_zone_b_w_max"] = ("q_to_zone_b_w", "max")

    if "zone_a_air_temperature_c" in df.columns:
        agg_map["zone_a_air_temperature_c_mean"] = (
            "zone_a_air_temperature_c",
            "mean",
        )
    if "opening_fraction" in df.columns:
        agg_map["opening_fraction_mean"] = ("opening_fraction", "mean")
        agg_map["opening_fraction_max"] = ("opening_fraction", "max")
        
    if "zone_b_air_temperature_c" in df.columns:
        agg_map["zone_b_air_temperature_c_mean"] = (
            "zone_b_air_temperature_c",
            "mean",
        )

    if not group_cols or not agg_map:
        return pd.DataFrame()

    return df.groupby(group_cols, as_index=False).agg(**agg_map)

def make_hourly_zone_summary(zone_df: pd.DataFrame) -> pd.DataFrame:
    df = _ensure_zone_group_columns(zone_df)
    _add_time_columns(df)

    group_cols = [
        "building_id",
        "dwelling_id",
        "zone_id",
        "zone_scope",
        "day",
        "hour_index",
    ]

    agg_map = {
        "indoor_temp_c_mean": ("indoor_temp_c", "mean"),
        "indoor_temp_c_min": ("indoor_temp_c", "min"),
        "indoor_temp_c_max": ("indoor_temp_c", "max"),
        "co2_ppm_mean": ("co2_ppm", "mean"),
        "co2_ppm_max": ("co2_ppm", "max"),
        "occupancy_mean": ("number_of_people", "mean"),
        "occupancy_max": ("number_of_people", "max"),
    }

    agg_map.update(_energy_agg_map(df))
    agg_map.update(_fallback_agg_map(df))
    agg_map.update(_interzone_zone_agg_map(df))
    agg_map.update(_phase12_air_quality_zone_agg_map(df))
    return df.groupby(group_cols, as_index=False).agg(**agg_map)


def make_daily_zone_summary(zone_df: pd.DataFrame) -> pd.DataFrame:
    df = _ensure_zone_group_columns(zone_df)
    _add_time_columns(df)

    group_cols = [
        "building_id",
        "dwelling_id",
        "zone_id",
        "zone_scope",
        "day",
    ]

    agg_map = {
        "indoor_temp_c_mean": ("indoor_temp_c", "mean"),
        "indoor_temp_c_min": ("indoor_temp_c", "min"),
        "indoor_temp_c_max": ("indoor_temp_c", "max"),
        "co2_ppm_mean": ("co2_ppm", "mean"),
        "co2_ppm_max": ("co2_ppm", "max"),
        "occupancy_mean": ("number_of_people", "mean"),
        "occupancy_max": ("number_of_people", "max"),
    }

    agg_map.update(_energy_agg_map(df))
    agg_map.update(_fallback_agg_map(df))
    agg_map.update(_interzone_zone_agg_map(df))
    agg_map.update(_phase12_air_quality_zone_agg_map(df))

    return df.groupby(group_cols, as_index=False).agg(**agg_map)


def make_daily_dwelling_summary(dwelling_df: pd.DataFrame) -> pd.DataFrame:
    df = _ensure_dwelling_group_columns(dwelling_df)
    _add_time_columns(df)

    group_cols = [
        "building_id",
        "dwelling_id",
        "day",
    ]

    agg_map = {
        "total_occupancy_mean": ("total_occupancy", "mean"),
        "total_occupancy_max": ("total_occupancy", "max"),
    }

    agg_map.update(_energy_agg_map(df))
    agg_map.update(_fallback_agg_map(df))
    return df.groupby(group_cols, as_index=False).agg(**agg_map)


def make_daily_building_summary(building_df: pd.DataFrame) -> pd.DataFrame:
    df = _ensure_building_group_columns(building_df)  
    _add_time_columns(df)

    group_cols = [
        "building_id",
        "day",
    ]

    agg_map = {
        "number_of_dwellings": ("number_of_dwellings", "max"),
        "total_occupancy_mean": ("total_occupancy", "mean"),
        "total_occupancy_max": ("total_occupancy", "max"),
    }

    for col in [
        "private_zone_energy_wh",
        "shared_zone_energy_wh",
        "heating_energy_wh",
        "cooling_energy_wh",
        "lighting_energy_wh",
        "appliance_energy_wh",
        "shared_system_energy_wh",
        "total_energy_wh",
        "heating_delivered_energy_wh",
        "cooling_delivered_energy_wh",
        "ventilation_fan_energy_wh",
        "hvac_delivered_energy_wh",
        "hvac_input_energy_wh",
    ]:
        if col in df.columns:
            agg_map[col] = (col, "sum")
    agg_map.update(_fallback_agg_map(df))
    return df.groupby(group_cols, as_index=False).agg(**agg_map)

def make_daily_interzone_airflow_summary(
    interzone_df: pd.DataFrame,
) -> pd.DataFrame:
    df = interzone_df.copy()
    _add_time_columns(df)

    group_cols = [
        col for col in [
            "building_id",
            "day",
            "link_id",
            "connection_id",
            "zone_connection_id",
            "zone_a_id",
            "zone_b_id",
            "connection_type",
        ]
        if col in df.columns
    ]

    agg_map = {}

    for col in [
        "airflow_a_to_b_m3_h",
        "airflow_b_to_a_m3_h",
        "flow_a_to_b_m3_h",
        "flow_b_to_a_m3_h",
        "net_a_to_b_m3_h",
        "open_fraction",
        "opening_fraction",
        "mixing_exchange_m3_h",
        "mixing_flow_m3_h",
    ]:
        if col in df.columns:
            agg_map[col + "_mean"] = (col, "mean")
            agg_map[col + "_max"] = (col, "max")

    if not group_cols or not agg_map:
        return pd.DataFrame()

    return df.groupby(group_cols, as_index=False).agg(**agg_map)


def make_daily_window_airflow_summary(window_airflow_df: pd.DataFrame) -> pd.DataFrame:
    if window_airflow_df.empty:
        return pd.DataFrame()

    df = standardize_window_detail_dataframe(window_airflow_df)
    _add_time_columns(df)

    group_cols = [
        col for col in [
            "day",
            "building_id",
            "zone_id",
            "window_id",
            "boundary_connection_id",
        ]
        if col in df.columns
    ]

    value_cols = [
        col for col in [
            "opening_fraction",
            "airflow_opening_area_m2",
            "outdoor_airflow_m3_h",
            "solar_alignment_factor",
            "daylight_alignment_factor",
            "effective_solar_factor",
            "effective_visible_transmittance",
            "effective_solar_area_m2",
            "effective_daylight_area_m2",
            "solar_gain_w",
            "daylight_contribution_lux",
        ]
        if col in df.columns
    ]

    if not group_cols or not value_cols:
        return pd.DataFrame()

    return (
        df
        .groupby(group_cols)[value_cols]
        .mean()
        .reset_index()
    )

def make_energy_by_zone(zone_df: pd.DataFrame) -> pd.DataFrame:
    df = _ensure_zone_group_columns(zone_df)
    group_cols = [
        "building_id",
        "dwelling_id",
        "zone_id",
        "zone_scope",
    ]

    agg_map = _energy_agg_map(df)
    agg_map.update(_fallback_agg_map(df))
    return df.groupby(group_cols, as_index=False).agg(**agg_map)


def make_energy_by_dwelling(dwelling_df: pd.DataFrame) -> pd.DataFrame:
    df = _ensure_dwelling_group_columns(dwelling_df)
    group_cols = [
        "building_id",
        "dwelling_id",
    ]

    agg_map = _energy_agg_map(df)
    agg_map.update(_fallback_agg_map(df))
    return df.groupby(group_cols, as_index=False).agg(**agg_map)


def make_energy_by_building(building_df: pd.DataFrame) -> pd.DataFrame:
    df = _ensure_building_group_columns(building_df)
    group_cols = [
        "building_id",
    ]

    agg_map = {}

    for col in [
        "private_zone_energy_wh",
        "shared_zone_energy_wh",
        "heating_energy_wh",
        "cooling_energy_wh",
        "lighting_energy_wh",
        "appliance_energy_wh",
        "shared_system_energy_wh",
        "total_energy_wh",
        "heating_delivered_energy_wh",
        "cooling_delivered_energy_wh",
        "ventilation_fan_energy_wh",
        "hvac_delivered_energy_wh",
        "hvac_input_energy_wh",
    ]:
        if col in df.columns:
            agg_map[col] = (col, "sum")
    agg_map.update(_fallback_agg_map(df))
    return df.groupby(group_cols, as_index=False).agg(**agg_map)


def make_control_active_hours_by_zone(zone_df: pd.DataFrame) -> pd.DataFrame:
    df = _ensure_zone_group_columns(zone_df)
    dt_hours = _infer_dt_hours(df)

    control_cols = [
        "heating_on",
        "cooling_on",
        "lights_on",
        "window_open",
        "mechanical_ventilation_on",
    ]

    active_hour_cols = []

    for col in control_cols:
        if col not in df.columns:
            continue

        hour_col = col + "_hours"
        df[hour_col] = df[col].astype(bool).astype(float) * dt_hours
        active_hour_cols.append(hour_col)

    group_cols = [
        "building_id",
        "dwelling_id",
        "zone_id",
        "zone_scope",
    ]

    agg_map = {
        col: (col, "sum")
        for col in active_hour_cols
    }
    agg_map.update(_fallback_agg_map(df))
    return df.groupby(group_cols, as_index=False).agg(**agg_map)

# ============================================================
# PLOTS
# ============================================================

def _plot_zone_lines(
    df: pd.DataFrame,
    y_col: str,
    y_label: str,
    path: Path,
) -> Path:
    fig, ax = plt.subplots(figsize=(12, 6))

    for zone_id, group in df.groupby("zone_id"):
        group = group.sort_values("time_h")
        ax.plot(group["time_h"], group[y_col], label=zone_id)

    ax.set_xlabel("Time [h]")
    ax.set_ylabel(y_label)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)

    return path


def _plot_zone_state_lines(
    df: pd.DataFrame,
    state_col: str,
    path: Path,
) -> Path:
    fig, ax = plt.subplots(figsize=(12, 6))

    for zone_id, group in df.groupby("zone_id"):
        group = group.sort_values("time_h")
        ax.step(
            group["time_h"],
            group[state_col].astype(bool).astype(int),
            where="post",
            label=zone_id,
        )

    ax.set_xlabel("Time [h]")
    ax.set_ylabel(state_col)
    ax.set_yticks([0, 1])
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)

    return path


def _plot_energy_by_zone(
    zone_df: pd.DataFrame,
    path: Path,
) -> Path:
    energy_df = make_energy_by_zone(zone_df)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(energy_df["zone_id"], energy_df["total_energy_wh"])
    ax.set_xlabel("Zone")
    ax.set_ylabel("Total energy [Wh]")
    ax.tick_params(axis="x", rotation=60)
    ax.grid(True, axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)

    return path


def _plot_energy_by_dwelling(
    dwelling_df: pd.DataFrame,
    path: Path,
) -> Path:
    energy_df = make_energy_by_dwelling(dwelling_df)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(energy_df["dwelling_id"], energy_df["total_energy_wh"])
    ax.set_xlabel("Dwelling")
    ax.set_ylabel("Total energy [Wh]")
    ax.grid(True, axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)

    return path

def _optional_sum_agg(df: pd.DataFrame, columns: list) -> Dict[str, tuple]:
    return {
        col: (col, "sum")
        for col in columns
        if col in df.columns
    }

def _plot_energy_by_building(
    building_df: pd.DataFrame,
    path: Path,
) -> Path:
    energy_df = make_energy_by_building(building_df)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(energy_df["building_id"], energy_df["total_energy_wh"])
    ax.set_xlabel("Building")
    ax.set_ylabel("Total energy [Wh]")
    ax.grid(True, axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)

    return path


def _plot_control_active_hours_by_zone(
    control_df: pd.DataFrame,
    path: Path,
) -> Path:
    plot_df = control_df.copy()

    cols = [
        "heating_on_hours",
        "cooling_on_hours",
        "lights_on_hours",
        "window_open_hours",
    ]

    existing_cols = [
        col for col in cols
        if col in plot_df.columns
    ]

    fig, ax = plt.subplots(figsize=(12, 6))

    bottom = None

    for col in existing_cols:
        values = plot_df[col].values

        if bottom is None:
            ax.bar(plot_df["zone_id"], values, label=col)
            bottom = values
        else:
            ax.bar(plot_df["zone_id"], values, bottom=bottom, label=col)
            bottom = bottom + values

    ax.set_xlabel("Zone")
    ax.set_ylabel("Active hours [h]")
    ax.tick_params(axis="x", rotation=60)
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)

    return path


def _interzone_zone_agg_map(df: pd.DataFrame) -> Dict[str, tuple]:
    agg_map = {}

    if "interzone_thermal_link_count" in df.columns:
        agg_map["interzone_link_count"] = (
            "interzone_thermal_link_count",
            "max",
        )

    if "interzone_thermal_total_h_w_k" in df.columns:
        agg_map["interzone_thermal_total_h_w_k_mean"] = (
            "interzone_thermal_total_h_w_k",
            "mean",
        )

    if "interzone_heat_gain_w" in df.columns:
        agg_map["interzone_heat_gain_w_mean"] = (
            "interzone_heat_gain_w",
            "mean",
        )
        agg_map["interzone_heat_gain_w_max"] = (
            "interzone_heat_gain_w",
            "max",
        )

    if "interzone_heat_loss_w" in df.columns:
        agg_map["interzone_heat_loss_w_mean"] = (
            "interzone_heat_loss_w",
            "mean",
        )
        agg_map["interzone_heat_loss_w_max"] = (
            "interzone_heat_loss_w",
            "max",
        )

    if "interzone_net_heat_gain_w" in df.columns:
        agg_map["interzone_net_heat_gain_w_mean"] = (
            "interzone_net_heat_gain_w",
            "mean",
        )
        agg_map["interzone_net_heat_gain_w_min"] = (
            "interzone_net_heat_gain_w",
            "min",
        )
        agg_map["interzone_net_heat_gain_w_max"] = (
            "interzone_net_heat_gain_w",
            "max",
        )

    return agg_map
def _phase12_air_quality_zone_agg_map(df: pd.DataFrame) -> Dict[str, tuple]:
    agg_map = {}

    mean_cols = [
        "airflow_infiltration_flow_m3_h",
        "airflow_mechanical_ventilation_flow_m3_h",
        "airflow_window_flow_m3_h",
        "airflow_outdoor_exchange_m3_h",
        "airflow_interzone_exchange_m3_h",
        "airflow_total_exchange_m3_h",
        "co2_generation_m3_h",
        "moisture_generation_kg_h",
        "moisture_transport_airflow_m3_h",
        "old_humidity_ratio_kg_kg",
        "new_humidity_ratio_kg_kg",
        "old_relative_humidity_percent",
        "new_relative_humidity_percent",
    ]

    for col in mean_cols:
        if col in df.columns:
            agg_map[col + "_mean"] = (col, "mean")

    max_cols = [
        "airflow_total_exchange_m3_h",
        "airflow_window_flow_m3_h",
        "airflow_mechanical_ventilation_flow_m3_h",
        "co2_generation_m3_h",
        "moisture_generation_kg_h",
        "new_humidity_ratio_kg_kg",
        "new_relative_humidity_percent",
    ]

    for col in max_cols:
        if col in df.columns:
            agg_map[col + "_max"] = (col, "max")

    return agg_map
# ============================================================
# INTERNAL UTILS
# ============================================================

def _ensure_folder(path: Any) -> Path:
    folder = Path(path)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _add_time_columns(df: pd.DataFrame) -> None:
    if "day" not in df.columns:
        df["day"] = 0

    if "hour" not in df.columns:
        df["hour"] = 0.0

    df["time_h"] = df["day"].astype(float) * 24.0 + df["hour"].astype(float)
    df["hour_index"] = df["time_h"].astype(int)


def _infer_dt_hours(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0

    temp = df.copy()
    _add_time_columns(temp)

    times = sorted(temp["time_h"].dropna().unique())

    if len(times) < 2:
        return 1.0

    diffs = []

    for i in range(1, len(times)):
        diff = float(times[i] - times[i - 1])

        if diff > 0:
            diffs.append(diff)

    if not diffs:
        return 1.0

    return min(diffs)