"""
Building-output saving utilities for ABBEY.

Phase 14:
- debug timestep outputs
- yearly aggregated outputs
- building/dwelling/zone CSVs
- basic plots
"""

from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import matplotlib.pyplot as plt


def save_debug_building_outputs(
    sim: Any,
    output_folder: str,
    prefix: str = "building",
) -> Dict[str, Path]:
    """
    Save full timestep building outputs for debug runs.
    """

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

    if hasattr(sim, "building_window_airflow_records_to_dataframe"):
        window_airflow_df = sim.building_window_airflow_records_to_dataframe()
    else:
        window_airflow_df = pd.DataFrame()
    bridge_df = sim.building_control_bridge_records_to_dataframe()
    action_df = sim.building_action_event_records_to_dataframe()
    internal_source_df = sim.building_internal_source_records_to_dataframe()
    internal_source_zone_df = sim.building_internal_source_zone_records_to_dataframe()
    internal_source_building_df = sim.building_internal_source_building_records_to_dataframe()
    
    zone_path = csv_folder / (prefix + "_zone_timestep.csv")
    dwelling_path = csv_folder / (prefix + "_dwelling_timestep.csv")
    building_path = csv_folder / (prefix + "_building_timestep.csv")

    zone_df.to_csv(zone_path, index=False)
    dwelling_df.to_csv(dwelling_path, index=False)
    building_df.to_csv(building_path, index=False)

    paths["zone_timestep_csv"] = zone_path
    paths["dwelling_timestep_csv"] = dwelling_path
    paths["building_timestep_csv"] = building_path
    if not interzone_thermal_df.empty:
        interzone_thermal_path = csv_folder / (
            prefix + "_interzone_thermal_timestep.csv"
        )

        interzone_thermal_df.to_csv(
            interzone_thermal_path,
            index=False,
        )

        paths["interzone_thermal_timestep_csv"] = interzone_thermal_path
    if not interzone_airflow_df.empty:
        interzone_airflow_path = csv_folder / (
            prefix + "_interzone_airflow_timestep.csv"
        )

        interzone_airflow_df.to_csv(
            interzone_airflow_path,
            index=False,
        )

        paths["interzone_airflow_timestep_csv"] = interzone_airflow_path

    if not window_airflow_df.empty:
        window_airflow_path = csv_folder / (
            prefix + "_window_airflow_timestep.csv"
        )

        window_airflow_df.to_csv(
            window_airflow_path,
            index=False,
        )

        paths["window_airflow_timestep_csv"] = window_airflow_path
    if not bridge_df.empty:
        bridge_path = csv_folder / (prefix + "_control_bridge_timestep.csv")
        bridge_df.to_csv(bridge_path, index=False)
        paths["control_bridge_csv"] = bridge_path

    if not action_df.empty:
        action_path = csv_folder / (prefix + "_action_events_timestep.csv")
        action_df.to_csv(action_path, index=False)
        paths["action_events_csv"] = action_path

    if not zone_df.empty:
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
        internal_source_df.to_csv(internal_source_path, index=False)
        paths["internal_source_records_csv"] = internal_source_path

    if not internal_source_zone_df.empty:
        internal_source_zone_path = csv_folder / (
            prefix + "_internal_source_zone_timestep.csv"
        )
        internal_source_zone_df.to_csv(internal_source_zone_path, index=False)
        paths["internal_source_zone_csv"] = internal_source_zone_path

    if not internal_source_building_df.empty:
        internal_source_building_path = csv_folder / (
            prefix + "_internal_source_building_timestep.csv"
        )
        internal_source_building_df.to_csv(internal_source_building_path, index=False)
        paths["internal_source_building_csv"] = internal_source_building_path
    return paths


def save_yearly_building_outputs(
    sim: Any,
    output_folder: str,
    prefix: str = "building",
) -> Dict[str, Path]:
    """
    Save aggregated building outputs for yearly runs.

    Avoids heavy people/action timestep CSVs.
    """

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

    if hasattr(sim, "building_window_airflow_records_to_dataframe"):
        window_airflow_df = sim.building_window_airflow_records_to_dataframe()
    else:
        window_airflow_df = pd.DataFrame()
    internal_source_zone_df = sim.building_internal_source_zone_records_to_dataframe()
    internal_source_building_df = sim.building_internal_source_building_records_to_dataframe()
    
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

        hourly_zone.to_csv(hourly_zone_path, index=False)
        daily_zone.to_csv(daily_zone_path, index=False)
        energy_by_zone.to_csv(energy_by_zone_path, index=False)
        control_hours_by_zone.to_csv(control_hours_path, index=False)

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

        daily_dwelling.to_csv(daily_dwelling_path, index=False)
        energy_by_dwelling.to_csv(energy_by_dwelling_path, index=False)

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

        daily_building.to_csv(daily_building_path, index=False)
        energy_by_building.to_csv(energy_by_building_path, index=False)

        paths["daily_building_summary_csv"] = daily_building_path
        paths["energy_by_building_csv"] = energy_by_building_path

        paths["energy_by_building_plot"] = _plot_energy_by_building(
            building_df=building_df,
            path=plot_folder / (prefix + "_energy_by_building.png"),
        )
    if not interzone_airflow_df.empty:
        _add_time_columns(interzone_airflow_df)

        daily_interzone_airflow = make_daily_interzone_airflow_summary(
            interzone_airflow_df
        )

        if not daily_interzone_airflow.empty:
            interzone_airflow_summary_path = csv_folder / (
                prefix + "_daily_interzone_airflow_summary.csv"
            )

            daily_interzone_airflow.to_csv(
                interzone_airflow_summary_path,
                index=False,
            )

            paths["daily_interzone_airflow_summary_csv"] = (
                interzone_airflow_summary_path
            )

    if not window_airflow_df.empty:
        _add_time_columns(window_airflow_df)

        daily_window_airflow = make_daily_window_airflow_summary(
            window_airflow_df
        )

        if not daily_window_airflow.empty:
            window_airflow_summary_path = csv_folder / (
                prefix + "_daily_window_airflow_summary.csv"
            )

            daily_window_airflow.to_csv(
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

            daily_internal_zone.to_csv(
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

            daily_internal_building.to_csv(
                daily_internal_building_path,
                index=False,
            )

            paths["daily_internal_source_building_summary_csv"] = (
                daily_internal_building_path
            )

    if not interzone_thermal_df.empty:
        _add_time_columns(interzone_thermal_df)

        daily_interzone_thermal = make_daily_interzone_thermal_summary(
            interzone_thermal_df
        )

        interzone_thermal_summary_path = csv_folder / (
            prefix + "_daily_interzone_thermal_summary.csv"
        )

        daily_interzone_thermal.to_csv(
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

    if "zone_b_air_temperature_c" in df.columns:
        agg_map["zone_b_air_temperature_c_mean"] = (
            "zone_b_air_temperature_c",
            "mean",
        )

    if not group_cols or not agg_map:
        return pd.DataFrame()

    return df.groupby(group_cols, as_index=False).agg(**agg_map)

def make_hourly_zone_summary(zone_df: pd.DataFrame) -> pd.DataFrame:
    df = zone_df.copy()
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
    df = zone_df.copy()
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
    df = dwelling_df.copy()
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
    df = building_df.copy()
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
            "zone_connection_id",
            "zone_a_id",
            "zone_b_id",
            "connection_type",
        ]
        if col in df.columns
    ]

    agg_map = {}

    for col in [
        "flow_a_to_b_m3_h",
        "flow_b_to_a_m3_h",
        "net_a_to_b_m3_h",
        "opening_fraction",
        "mixing_flow_m3_h",
    ]:
        if col in df.columns:
            agg_map[col + "_mean"] = (col, "mean")
            agg_map[col + "_max"] = (col, "max")

    if not group_cols or not agg_map:
        return pd.DataFrame()

    return df.groupby(group_cols, as_index=False).agg(**agg_map)


def make_daily_window_airflow_summary(
    window_df: pd.DataFrame,
) -> pd.DataFrame:
    df = window_df.copy()
    _add_time_columns(df)

    group_cols = [
        col for col in [
            "building_id",
            "day",
            "boundary_connection_id",
            "zone_id",
            "orientation_deg",
        ]
        if col in df.columns
    ]

    agg_map = {}

    for col in [
        "opening_fraction",
        "wind_speed_m_s",
        "wind_alignment_factor",
        "outdoor_airflow_m3_h",
    ]:
        if col in df.columns:
            agg_map[col + "_mean"] = (col, "mean")
            agg_map[col + "_max"] = (col, "max")

    if not group_cols or not agg_map:
        return pd.DataFrame()

    return df.groupby(group_cols, as_index=False).agg(**agg_map)

def make_energy_by_zone(zone_df: pd.DataFrame) -> pd.DataFrame:
    df = zone_df.copy()

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
    df = dwelling_df.copy()

    group_cols = [
        "building_id",
        "dwelling_id",
    ]

    agg_map = _energy_agg_map(df)
    agg_map.update(_fallback_agg_map(df))
    return df.groupby(group_cols, as_index=False).agg(**agg_map)


def make_energy_by_building(building_df: pd.DataFrame) -> pd.DataFrame:
    df = building_df.copy()

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
    df = zone_df.copy()
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