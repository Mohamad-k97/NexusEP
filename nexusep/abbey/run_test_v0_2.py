from pathlib import Path

from nexusep.abbey.simulation.runner import AbbeySimulation
from nexusep.abbey.agents.states import (
    PersonState,
    DwellingObservation,
    ZoneObservation,
    SystemState,
    ExecutionState,
)
from nexusep.abbey.agents.location import OccupantLocation, SpaceAssignment


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

config_path = (
    PROJECT_ROOT
    / "nexusep"
    / "data"
    / "abbey"
    / "config"
    / "abbey_config.jsonc"
)



zone_output_folder = (
    PROJECT_ROOT
    / "outputs"
    / "abbey"
    / "runs"
    / "zones_dummy_apartment_v02_05"
)
output_path = (
    zone_output_folder
    / "abbey_dummy_apartment.csv"
)

# ============================================================
# DUMMY APARTMENT ZONES
# ============================================================

zone_observations = {
    "living_room": ZoneObservation(
        zone_id="living_room",
        zone_name="Living room",
        indoor_temp=20.5,
        co2_ppm=600.0,
        indoor_daylight=0.60,
        indoor_noise=0.25,
        heating_on=False,
        cooling_on=False,
        lights_on=False,
        window_open=False,
        occupied_person_ids=["person_1"],
        number_of_people=1,
    ),
    "bedroom_1": ZoneObservation(
        zone_id="bedroom_1",
        zone_name="Bedroom 1",
        indoor_temp=20.0,
        co2_ppm=580.0,
        indoor_daylight=0.35,
        indoor_noise=0.18,
        heating_on=False,
        cooling_on=False,
        lights_on=False,
        window_open=False,
        occupied_person_ids=[],
        number_of_people=0,
    ),
    "office": ZoneObservation(
        zone_id="office",
        zone_name="Office",
        indoor_temp=20.3,
        co2_ppm=590.0,
        indoor_daylight=0.50,
        indoor_noise=0.22,
        heating_on=False,
        cooling_on=False,
        lights_on=False,
        window_open=False,
        occupied_person_ids=[],
        number_of_people=0,
    ),
    "kitchen": ZoneObservation(
        zone_id="kitchen",
        zone_name="Kitchen",
        indoor_temp=20.7,
        co2_ppm=610.0,
        indoor_daylight=0.45,
        indoor_noise=0.25,
        heating_on=False,
        cooling_on=False,
        lights_on=False,
        window_open=False,
        occupied_person_ids=[],
        number_of_people=0,
    ),
    "bathroom": ZoneObservation(
        zone_id="bathroom",
        zone_name="Bathroom",
        indoor_temp=21.0,
        co2_ppm=560.0,
        indoor_daylight=0.15,
        indoor_noise=0.20,
        heating_on=False,
        cooling_on=False,
        lights_on=False,
        window_open=False,
        occupied_person_ids=[],
        number_of_people=0,
    ),
    "laundry": ZoneObservation(
        zone_id="laundry",
        zone_name="Laundry",
        indoor_temp=20.3,
        co2_ppm=570.0,
        indoor_daylight=0.10,
        indoor_noise=0.35,
        heating_on=False,
        cooling_on=False,
        lights_on=False,
        window_open=False,
        occupied_person_ids=[],
        number_of_people=0,
    ),
    "entrance": ZoneObservation(
        zone_id="entrance",
        zone_name="Entrance",
        indoor_temp=19.5,
        co2_ppm=550.0,
        indoor_daylight=0.20,
        indoor_noise=0.30,
        heating_on=False,
        cooling_on=False,
        lights_on=False,
        window_open=False,
        occupied_person_ids=[],
        number_of_people=0,
    ),
}


# ============================================================
# PERSON
# ============================================================

person = PersonState(
    occupant_id="person_1",
    idle_movement_profile="normal",
    mobility_tendency=1.0,

    hunger=0.30,
    fatigue=0.20,
    sleep_pressure=0.20,
    sickness_severity=0.00,
    dirty_clothes=0.20,

    is_home=True,
    is_sleeping=False,
    away_reason="none",

    has_job=True,
    base_laziness=0.40,
    money_sensitivity=0.60,
    comfort_sensitivity=0.70,
    future_awareness=0.60,
)


# ============================================================
# LOCATION + SPACE ASSIGNMENT
# ============================================================

location = OccupantLocation(
    occupant_id="person_1",
    dwelling_id="dummy_apartment_1",
    is_home=True,
    current_space_id="living_room",
    current_space_role="idle",
    away_reason="none",
    minutes_since_last_space_change=999.0,
)

assignment = SpaceAssignment(
    occupant_id="person_1",
    dwelling_id="dummy_apartment_1",
    default_space_id="living_room",
    role_to_space_id={
        "idle": "living_room",
        "sleep": "bedroom_1",
        "work": "office",
        "kitchen": "kitchen",
        "bathroom": "bathroom",
        "laundry": "laundry",
        "entrance": "entrance",
    },
)


# ============================================================
# DWELLING OBSERVATION
# ============================================================

observation = DwellingObservation(
    indoor_temp=20.5,
    outdoor_temp=10.0,
    co2_ppm=600.0,
    indoor_daylight=0.60,
    indoor_noise=0.25,
    electricity_tariff=0.25,
    default_zone_id="living_room",
    zone_observations=zone_observations,
)


# ============================================================
# SYSTEM + EXECUTION STATE
# ============================================================

systems = SystemState(
    default_space_id="living_room",
)

execution = ExecutionState()


# ============================================================
# RUN SIMULATION
# ============================================================

sim = AbbeySimulation.initialize(
    config_path=config_path,
    duration_hours=48,
    dt_minutes=1,
    person=person,
    location=location,
    assignment=assignment,
    observation=observation,
    systems=systems,
    execution=execution,
    random_seed=42,
)

df = sim.run()

sim.save_csv(output_path)
sim.save_zone_csvs(zone_output_folder)


# ============================================================
# QUICK CHECKS
# ============================================================

print("\nSaved main CSV to:")
print(output_path)

print("\nSaved zone CSVs to:")
print(zone_output_folder)

print("\nSpace counts:")
print(df["current_space_id"].value_counts())

print("\nSpace-role counts:")
print(df["current_space_role"].value_counts())

print("\nLocation sample:")
print(
    df[
        [
            "day",
            "hour",
            "current_space_id",
            "current_space_role",
            "location_is_home",
            "away_reason",
            "person_is_sleeping",
            "person_hunger",
            "person_fatigue",
            "person_sleep_pressure",
        ]
    ].head(80)
)

print("\nLast rows:")
print(
    df[
        [
            "day",
            "hour",
            "current_space_id",
            "current_space_role",
            "location_is_home",
            "away_reason",
            "person_is_sleeping",
        ]
    ].tail(80)
)

import json
from collections import Counter

action_counter = Counter()

for value in df["chunk_records"]:
    chunks = json.loads(value)
    for chunk in chunks:
        label = chunk.get("chunk_label", "")
        action_counter[label] += 1

print("\nAction counts:")
print(action_counter)

print(
    df[
        [
            "day",
            "hour",
            "person_is_sleeping",
            "person_minutes_asleep",
            "person_minutes_awake_since_sleep",
            "current_space_id",
            "current_space_role",
        ]
    ].tail(200)
)

print(
    df[
        [
            "day",
            "hour",
            "location_is_home",
            "away_reason",
            "current_space_id",
            "current_space_role",
        ]
    ][df["away_reason"] == "work"].tail(200)
)

# ============================================================
# QUICK BEHAVIOR PLOTS
# ============================================================

import json
import numpy as np
import matplotlib.pyplot as plt


plot_folder = (
    PROJECT_ROOT
    / "outputs"
    / "abbey"
    / "plots"
    / "dummy_apartment_v02"
)

plot_folder.mkdir(parents=True, exist_ok=True)


def extract_primary_action(chunk_records_value):
    """
    Extract the dominant visible action from chunk_records.
    """

    if isinstance(chunk_records_value, str):
        try:
            chunks = json.loads(chunk_records_value)
        except json.JSONDecodeError:
            return "unknown"
    else:
        chunks = chunk_records_value

    if not chunks:
        return "do_nothing"

    action_minutes = {}

    for chunk in chunks:
        label = chunk.get("chunk_label", "do_nothing")
        minutes = float(chunk.get("chunk_minutes", 0.0))

        if label != "continue_blocking_action":
            action_minutes[label] = action_minutes.get(label, 0.0) + minutes
            continue

        for item in chunk.get("power_breakdown", []):
            if item.get("execution_type") != "background":
                name = item.get("name", "do_nothing")
                item_minutes = float(item.get("minutes", minutes))
                action_minutes[name] = action_minutes.get(name, 0.0) + item_minutes

    if not action_minutes:
        return "do_nothing"

    return max(action_minutes, key=action_minutes.get)


df_plot = df.copy()

df_plot["time_h"] = np.arange(len(df_plot)) * df_plot["dt_hours"].iloc[0]
df_plot["primary_action"] = df_plot["chunk_records"].apply(extract_primary_action)


# ------------------------------------------------------------
# Plot 1: where he is over time
# ------------------------------------------------------------

space_categories = sorted(df_plot["current_space_id"].dropna().unique())
space_to_y = {space: i for i, space in enumerate(space_categories)}

df_plot["space_y"] = df_plot["current_space_id"].map(space_to_y)

plt.figure(figsize=(14, 5))
plt.scatter(
    df_plot["time_h"],
    df_plot["space_y"],
    s=6,
)
plt.yticks(
    list(space_to_y.values()),
    list(space_to_y.keys()),
)
plt.xlabel("Time [h]")
plt.ylabel("Space")
plt.title("Occupant location over time")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(plot_folder / "01_location_over_time.png", dpi=200)
plt.close()


# ------------------------------------------------------------
# Plot 2: what he is doing over time
# ------------------------------------------------------------

action_categories = sorted(df_plot["primary_action"].dropna().unique())
action_to_y = {action: i for i, action in enumerate(action_categories)}

df_plot["action_y"] = df_plot["primary_action"].map(action_to_y)

plt.figure(figsize=(14, 6))
plt.scatter(
    df_plot["time_h"],
    df_plot["action_y"],
    s=6,
)
plt.yticks(
    list(action_to_y.values()),
    list(action_to_y.keys()),
)
plt.xlabel("Time [h]")
plt.ylabel("Action")
plt.title("Primary action over time")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(plot_folder / "02_action_over_time.png", dpi=200)
plt.close()


# ------------------------------------------------------------
# Plot 3: home / work / sleep overview
# ------------------------------------------------------------

plt.figure(figsize=(14, 5))

plt.plot(
    df_plot["time_h"],
    df_plot["location_is_home"].astype(int),
    label="At home",
)

plt.plot(
    df_plot["time_h"],
    df_plot["person_is_sleeping"].astype(int),
    label="Sleeping",
)

plt.xlabel("Time [h]")
plt.ylabel("State flag")
plt.title("Home and sleep state over time")
plt.yticks([0, 1], ["False", "True"])
plt.grid(True, alpha=0.3)
plt.legend()
plt.tight_layout()
plt.savefig(plot_folder / "03_home_sleep_over_time.png", dpi=200)
plt.close()


# ------------------------------------------------------------
# Plot 4: time spent in each space
# ------------------------------------------------------------

space_minutes = (
    df_plot.groupby("current_space_id")["dt_hours"]
    .sum()
    .sort_values(ascending=True)
    * 60.0
)

plt.figure(figsize=(9, 5))
plt.barh(space_minutes.index, space_minutes.values)
plt.xlabel("Minutes")
plt.ylabel("Space")
plt.title("Total time spent in each space")
plt.grid(True, axis="x", alpha=0.3)
plt.tight_layout()
plt.savefig(plot_folder / "04_time_by_space.png", dpi=200)
plt.close()


# ------------------------------------------------------------
# Plot 5: time spent doing each action
# ------------------------------------------------------------

action_minutes = (
    df_plot.groupby("primary_action")["dt_hours"]
    .sum()
    .sort_values(ascending=True)
    * 60.0
)

plt.figure(figsize=(9, 6))
plt.barh(action_minutes.index, action_minutes.values)
plt.xlabel("Minutes")
plt.ylabel("Action")
plt.title("Total time spent by action")
plt.grid(True, axis="x", alpha=0.3)
plt.tight_layout()
plt.savefig(plot_folder / "05_time_by_action.png", dpi=200)
plt.close()


print("\nSaved behavior plots to:")
print(plot_folder)

print("\nTime spent in spaces [min]:")
print(space_minutes.sort_values(ascending=False))

print("\nTime spent by action [min]:")
print(action_minutes.sort_values(ascending=False))

print("\nSleep pressure diagnostic every hour:")
cols = [
    "time_h",
    "hour",
    "current_activity",
    "location_is_home",
    "away_reason",
    "person_is_sleeping",
    "person_minutes_awake_since_sleep",
    "person_minutes_asleep",
    "person_fatigue",
    "person_sleep_pressure",
]

print(df_plot[[c for c in cols if c in df_plot.columns]].iloc[::60].head(60))