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
            
    return paths


# ============================================================
# SUMMARY TABLES
# ============================================================

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

    out = df.groupby(group_cols, as_index=False).agg(
        indoor_temp_c_mean=("indoor_temp_c", "mean"),
        indoor_temp_c_min=("indoor_temp_c", "min"),
        indoor_temp_c_max=("indoor_temp_c", "max"),
        co2_ppm_mean=("co2_ppm", "mean"),
        co2_ppm_max=("co2_ppm", "max"),
        occupancy_mean=("number_of_people", "mean"),
        occupancy_max=("number_of_people", "max"),
        heating_energy_wh=("heating_energy_wh", "sum"),
        cooling_energy_wh=("cooling_energy_wh", "sum"),
        lighting_energy_wh=("lighting_energy_wh", "sum"),
        appliance_energy_wh=("appliance_energy_wh", "sum"),
        total_energy_wh=("total_energy_wh", "sum"),
    )

    return out


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

    out = df.groupby(group_cols, as_index=False).agg(
        indoor_temp_c_mean=("indoor_temp_c", "mean"),
        indoor_temp_c_min=("indoor_temp_c", "min"),
        indoor_temp_c_max=("indoor_temp_c", "max"),
        co2_ppm_mean=("co2_ppm", "mean"),
        co2_ppm_max=("co2_ppm", "max"),
        occupancy_mean=("number_of_people", "mean"),
        occupancy_max=("number_of_people", "max"),
        heating_energy_wh=("heating_energy_wh", "sum"),
        cooling_energy_wh=("cooling_energy_wh", "sum"),
        lighting_energy_wh=("lighting_energy_wh", "sum"),
        appliance_energy_wh=("appliance_energy_wh", "sum"),
        total_energy_wh=("total_energy_wh", "sum"),
    )

    return out


def make_daily_dwelling_summary(dwelling_df: pd.DataFrame) -> pd.DataFrame:
    df = dwelling_df.copy()
    _add_time_columns(df)

    group_cols = [
        "building_id",
        "dwelling_id",
        "day",
    ]

    out = df.groupby(group_cols, as_index=False).agg(
        total_occupancy_mean=("total_occupancy", "mean"),
        total_occupancy_max=("total_occupancy", "max"),
        heating_energy_wh=("heating_energy_wh", "sum"),
        cooling_energy_wh=("cooling_energy_wh", "sum"),
        lighting_energy_wh=("lighting_energy_wh", "sum"),
        appliance_energy_wh=("appliance_energy_wh", "sum"),
        total_energy_wh=("total_energy_wh", "sum"),
    )

    return out


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
        "total_energy_wh": ("total_energy_wh", "sum"),
    }

    for col in [
        "private_zone_energy_wh",
        "shared_zone_energy_wh",
        "heating_energy_wh",
        "cooling_energy_wh",
        "lighting_energy_wh",
        "appliance_energy_wh",
        "shared_system_energy_wh",
    ]:
        if col in df.columns:
            agg_map[col] = (col, "sum")

    out = df.groupby(group_cols, as_index=False).agg(**agg_map)

    return out


def make_energy_by_zone(zone_df: pd.DataFrame) -> pd.DataFrame:
    group_cols = [
        "building_id",
        "dwelling_id",
        "zone_id",
        "zone_scope",
    ]

    return zone_df.groupby(group_cols, as_index=False).agg(
        heating_energy_wh=("heating_energy_wh", "sum"),
        cooling_energy_wh=("cooling_energy_wh", "sum"),
        lighting_energy_wh=("lighting_energy_wh", "sum"),
        appliance_energy_wh=("appliance_energy_wh", "sum"),
        total_energy_wh=("total_energy_wh", "sum"),
    )


def make_energy_by_dwelling(dwelling_df: pd.DataFrame) -> pd.DataFrame:
    group_cols = [
        "building_id",
        "dwelling_id",
    ]

    return dwelling_df.groupby(group_cols, as_index=False).agg(
        heating_energy_wh=("heating_energy_wh", "sum"),
        cooling_energy_wh=("cooling_energy_wh", "sum"),
        lighting_energy_wh=("lighting_energy_wh", "sum"),
        appliance_energy_wh=("appliance_energy_wh", "sum"),
        total_energy_wh=("total_energy_wh", "sum"),
    )


def make_energy_by_building(building_df: pd.DataFrame) -> pd.DataFrame:
    group_cols = [
        "building_id",
    ]

    agg_map = {
        "total_energy_wh": ("total_energy_wh", "sum"),
    }

    for col in [
        "private_zone_energy_wh",
        "shared_zone_energy_wh",
        "heating_energy_wh",
        "cooling_energy_wh",
        "lighting_energy_wh",
        "appliance_energy_wh",
        "shared_system_energy_wh",
    ]:
        if col in building_df.columns:
            agg_map[col] = (col, "sum")

    return building_df.groupby(group_cols, as_index=False).agg(**agg_map)


def make_control_active_hours_by_zone(zone_df: pd.DataFrame) -> pd.DataFrame:
    df = zone_df.copy()
    dt_hours = _infer_dt_hours(df)

    for col in [
        "heating_on",
        "cooling_on",
        "lights_on",
        "window_open",
    ]:
        if col not in df.columns:
            df[col] = False

        df[col + "_hours"] = df[col].astype(bool).astype(float) * dt_hours

    group_cols = [
        "building_id",
        "dwelling_id",
        "zone_id",
        "zone_scope",
    ]

    return df.groupby(group_cols, as_index=False).agg(
        heating_on_hours=("heating_on_hours", "sum"),
        cooling_on_hours=("cooling_on_hours", "sum"),
        lights_on_hours=("lights_on_hours", "sum"),
        window_open_hours=("window_open_hours", "sum"),
    )


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