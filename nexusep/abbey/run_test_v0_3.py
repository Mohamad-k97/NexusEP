# ============================================================
# ABBEY v0.3 RUNNER
#
# Profiles:
#   debug  -> weekly, full outputs + plots
#   yearly -> yearly, 10-min timestep, light aggregated building outputs
# ============================================================

from pathlib import Path
import argparse
import copy
import json
import re

import pandas as pd
import matplotlib.pyplot as plt

from nexusep.abbey.simulation.runner import AbbeySimulation

from nexusep.abbey.agents.states import (
    PersonState,
    DwellingObservation,
    ZoneObservation,
    SystemState,
    ExecutionState,
)

from nexusep.abbey.agents.location import (
    OccupantLocation,
    SpaceAssignment,
)

from nexusep.abbey.household import HouseholdState
from nexusep.abbey.household.calendar import get_day_type, get_weekday_name
from nexusep.abbey.systems import CooldownState

from nexusep.abbey.building import (
    make_default_family_building,
    default_family_ids,
    default_family_space_role_map,
    SimpleBuildingPerformanceModel,
)


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_PATH = (
    PROJECT_ROOT
    / "nexusep"
    / "data"
    / "abbey"
    / "config"
    / "abbey_config.jsonc"
)

OUTPUT_ROOT = Path(__file__).resolve().parent / "outputs"


# ============================================================
# BUILDING / DWELLING IDS
# ============================================================

BUILDING_ID, DWELLING_ID, HOUSEHOLD_ID = default_family_ids()
ROLE_MAP = default_family_space_role_map(dwelling_id=DWELLING_ID)

LIVING_ROOM = ROLE_MAP["living_room"]
BEDROOM_1 = ROLE_MAP["sleep"]
BEDROOM_2 = ROLE_MAP["child_sleep"]
KITCHEN = ROLE_MAP["kitchen"]
BATHROOM = ROLE_MAP["bathroom"]
LAUNDRY = ROLE_MAP["laundry"]
OFFICE = ROLE_MAP["work"]
ENTRANCE = ROLE_MAP["entrance"]


# ============================================================
# PROFILE SETTINGS
# ============================================================

PROFILES = {
    "debug": {
        "duration_hours": 24 * 1,
        "dt_minutes": 1,
        "start_weekday": 0,
        "holiday_days": [],
        "random_seed": 42,
        "save_building_html_playback": True,

        # Legacy / behavior outputs
        "save_main_timestep": True,
        "save_people_timestep": True,
        "save_actions_long": True,
        "make_behavior_plots": True,

        # New building outputs
        "save_building_debug_outputs": True,
        "save_building_yearly_outputs": False,
    },

    "yearly": {
        "duration_hours": 24 * 365,
        "dt_minutes": 10,
        "start_weekday": 0,
        "holiday_days": [],
        "random_seed": 42,
        "save_building_html_playback": False,

        # Avoid heavy behavior timestep CSVs
        "save_main_timestep": False,
        "save_people_timestep": False,
        "save_actions_long": False,
        "make_behavior_plots": False,

        # New building outputs
        "save_building_debug_outputs": False,
        "save_building_yearly_outputs": True,
    },
    
}


# ============================================================
# OUTPUT FOLDER
# ============================================================

def make_next_output_folder(output_root):
    output_root.mkdir(parents=True, exist_ok=True)

    existing = []

    for path in output_root.iterdir():
        if not path.is_dir():
            continue

        match = re.match(r"abbey_v03_output_run_(\d+)$", path.name)

        if match:
            existing.append(int(match.group(1)))

    next_id = max(existing, default=0) + 1

    run_folder = output_root / "abbey_v03_output_run_{:03d}".format(next_id)
    run_folder.mkdir(parents=True, exist_ok=False)

    (run_folder / "csv").mkdir()
    (run_folder / "plots").mkdir()
    (run_folder / "metadata").mkdir()

    return run_folder


# ============================================================
# FAMILY MODEL
# ============================================================

EXPECTED_OCCUPANTS = [
    "working_man",
    "housewife",
    "schoolboy",
    "infant",
]


def make_zone_observations():
    return {
        LIVING_ROOM: ZoneObservation(
            zone_id=LIVING_ROOM,
            zone_name="Living room",
            indoor_temp=20.5,
            co2_ppm=600.0,
            indoor_daylight=0.60,
            indoor_noise=0.25,
            occupied_person_ids=[
                "working_man",
                "housewife",
                "schoolboy",
                "infant",
            ],
            number_of_people=4,
        ),

        BEDROOM_1: ZoneObservation(
            zone_id=BEDROOM_1,
            zone_name="Parents bedroom",
            indoor_temp=20.0,
            co2_ppm=580.0,
            indoor_daylight=0.35,
            indoor_noise=0.18,
        ),

        BEDROOM_2: ZoneObservation(
            zone_id=BEDROOM_2,
            zone_name="Child bedroom",
            indoor_temp=20.0,
            co2_ppm=575.0,
            indoor_daylight=0.35,
            indoor_noise=0.18,
        ),

        OFFICE: ZoneObservation(
            zone_id=OFFICE,
            zone_name="Office",
            indoor_temp=20.3,
            co2_ppm=590.0,
            indoor_daylight=0.50,
            indoor_noise=0.22,
        ),

        KITCHEN: ZoneObservation(
            zone_id=KITCHEN,
            zone_name="Kitchen",
            indoor_temp=20.7,
            co2_ppm=610.0,
            indoor_daylight=0.45,
            indoor_noise=0.25,
        ),

        BATHROOM: ZoneObservation(
            zone_id=BATHROOM,
            zone_name="Bathroom",
            indoor_temp=21.0,
            co2_ppm=560.0,
            indoor_daylight=0.15,
            indoor_noise=0.20,
        ),

        LAUNDRY: ZoneObservation(
            zone_id=LAUNDRY,
            zone_name="Laundry",
            indoor_temp=20.3,
            co2_ppm=570.0,
            indoor_daylight=0.10,
            indoor_noise=0.35,
        ),

        ENTRANCE: ZoneObservation(
            zone_id=ENTRANCE,
            zone_name="Entrance",
            indoor_temp=19.5,
            co2_ppm=550.0,
            indoor_daylight=0.20,
            indoor_noise=0.30,
        ),
    }


def make_people():
    return {
        "working_man": PersonState(
            occupant_id="working_man",
            household_id=HOUSEHOLD_ID,
            can_act=True,
            can_cook=True,
            authority_weight=1.0,
            has_job=True,
            has_school=False,
            age_group="adult",
            care_dependency=0.0,
            laundry_generation_rate=0.012,
            idle_movement_profile="normal",
            mobility_tendency=1.0,
            hunger=0.30,
            fatigue=0.20,
            sleep_pressure=0.20,
            sickness_severity=0.00,
            is_home=True,
            is_sleeping=False,
            away_reason="none",
            base_laziness=0.40,
            money_sensitivity=0.60,
            comfort_sensitivity=0.70,
            future_awareness=0.60,
        ),

        "housewife": PersonState(
            occupant_id="housewife",
            household_id=HOUSEHOLD_ID,
            can_act=True,
            can_cook=True,
            authority_weight=1.0,
            has_job=False,
            has_school=False,
            age_group="adult",
            care_dependency=0.0,
            laundry_generation_rate=0.011,
            idle_movement_profile="normal",
            mobility_tendency=1.0,
            hunger=0.25,
            fatigue=0.15,
            sleep_pressure=0.15,
            sickness_severity=0.00,
            is_home=True,
            is_sleeping=False,
            away_reason="none",
            base_laziness=0.35,
            money_sensitivity=0.55,
            comfort_sensitivity=0.75,
            future_awareness=0.65,
        ),

        "schoolboy": PersonState(
            occupant_id="schoolboy",
            household_id=HOUSEHOLD_ID,
            can_act=True,
            can_cook=False,
            authority_weight=0.5,
            has_job=False,
            has_school=True,
            age_group="child",
            care_dependency=0.2,
            laundry_generation_rate=0.014,
            idle_movement_profile="normal",
            mobility_tendency=1.2,
            hunger=0.35,
            fatigue=0.15,
            sleep_pressure=0.15,
            sickness_severity=0.00,
            is_home=True,
            is_sleeping=False,
            away_reason="none",
            base_laziness=0.50,
            money_sensitivity=0.30,
            comfort_sensitivity=0.60,
            future_awareness=0.35,
        ),

        "infant": PersonState(
            occupant_id="infant",
            household_id=HOUSEHOLD_ID,
            can_act=False,
            can_cook=False,
            authority_weight=0.0,
            has_job=False,
            has_school=False,
            age_group="infant",
            care_dependency=1.0,
            laundry_generation_rate=0.025,
            idle_movement_profile="none",
            mobility_tendency=0.0,
            hunger=0.40,
            fatigue=0.10,
            sleep_pressure=0.25,
            sickness_severity=0.00,
            is_home=True,
            is_sleeping=False,
            away_reason="none",
            base_laziness=0.0,
            money_sensitivity=0.0,
            comfort_sensitivity=1.0,
            future_awareness=0.0,
        ),
    }


def make_household():
    return HouseholdState(
        household_id=HOUSEHOLD_ID,
        occupant_ids=[
            "working_man",
            "housewife",
            "schoolboy",
            "infant",
        ],
        main_cook_id="housewife",
        cooking_priority_by_occupant={
            "housewife": 1,
            "working_man": 2,
            "schoolboy": 99,
            "infant": 999,
        },
        dirty_clothes=0.20,
        laundry_priority_by_occupant={
            "housewife": 1,
            "working_man": 2,
            "schoolboy": 99,
            "infant": 999,
        },
    )


def make_locations():
    return {
        occupant_id: OccupantLocation(
            occupant_id=occupant_id,
            building_id=BUILDING_ID,
            dwelling_id=DWELLING_ID,
            is_home=True,
            current_space_id=LIVING_ROOM,
            current_space_role="idle",
            current_activity="idle",
            away_reason="none",
            minutes_since_last_space_change=999.0,
        )
        for occupant_id in EXPECTED_OCCUPANTS
    }


def make_assignments():
    return {
        "working_man": SpaceAssignment(
            occupant_id="working_man",
            building_id=BUILDING_ID,
            dwelling_id=DWELLING_ID,
            default_space_id=LIVING_ROOM,
            role_to_space_id={
                "idle": LIVING_ROOM,
                "living_room": LIVING_ROOM,
                "sleep": BEDROOM_1,
                "work": OFFICE,
                "schoolwork": OFFICE,
                "kitchen": KITCHEN,
                "bathroom": BATHROOM,
                "laundry": LAUNDRY,
                "entrance": ENTRANCE,
                "care": LIVING_ROOM,
                "outside": "outside",
            },
        ),

        "housewife": SpaceAssignment(
            occupant_id="housewife",
            building_id=BUILDING_ID,
            dwelling_id=DWELLING_ID,
            default_space_id=LIVING_ROOM,
            role_to_space_id={
                "idle": LIVING_ROOM,
                "living_room": LIVING_ROOM,
                "sleep": BEDROOM_1,
                "work": LIVING_ROOM,
                "schoolwork": LIVING_ROOM,
                "kitchen": KITCHEN,
                "bathroom": BATHROOM,
                "laundry": LAUNDRY,
                "entrance": ENTRANCE,
                "care": LIVING_ROOM,
                "outside": "outside",
            },
        ),

        "schoolboy": SpaceAssignment(
            occupant_id="schoolboy",
            building_id=BUILDING_ID,
            dwelling_id=DWELLING_ID,
            default_space_id=LIVING_ROOM,
            role_to_space_id={
                "idle": LIVING_ROOM,
                "living_room": LIVING_ROOM,
                "sleep": BEDROOM_2,
                "child_sleep": BEDROOM_2,
                "work": BEDROOM_2,
                "schoolwork": BEDROOM_2,
                "kitchen": KITCHEN,
                "bathroom": BATHROOM,
                "laundry": LAUNDRY,
                "entrance": ENTRANCE,
                "care": LIVING_ROOM,
                "outside": "outside",
            },
        ),

        "infant": SpaceAssignment(
            occupant_id="infant",
            building_id=BUILDING_ID,
            dwelling_id=DWELLING_ID,
            default_space_id=LIVING_ROOM,
            role_to_space_id={
                "idle": LIVING_ROOM,
                "living_room": LIVING_ROOM,
                "sleep": BEDROOM_1,
                "work": LIVING_ROOM,
                "schoolwork": LIVING_ROOM,
                "kitchen": KITCHEN,
                "bathroom": BATHROOM,
                "laundry": LAUNDRY,
                "entrance": ENTRANCE,
                "care": LIVING_ROOM,
                "outside": "outside",
            },
        ),
    }


def make_observation():
    return DwellingObservation(
        indoor_temp=20.5,
        outdoor_temp=10.0,
        co2_ppm=600.0,
        indoor_daylight=0.60,
        indoor_noise=0.25,
        electricity_tariff=0.25,
        default_zone_id=LIVING_ROOM,
        zone_observations=make_zone_observations(),
    )


# ============================================================
# SIM FACTORY
# ============================================================

def make_sim(settings):
    building = make_default_family_building()

    sim = AbbeySimulation.initialize(
        config_path=CONFIG_PATH,
        duration_hours=settings["duration_hours"],
        dt_minutes=settings["dt_minutes"],
        people=copy.deepcopy(make_people()),
        locations=copy.deepcopy(make_locations()),
        assignments=copy.deepcopy(make_assignments()),
        household=copy.deepcopy(make_household()),
        observation=copy.deepcopy(make_observation()),
        systems=SystemState(default_space_id=LIVING_ROOM),
        execution=ExecutionState(),
        cooldowns=CooldownState(),
        random_seed=settings["random_seed"],
        use_household_execution=True,
        building_model=building,
        building_performance_model=SimpleBuildingPerformanceModel(
            building_model=building,
        ),
        use_building_performance=True,
    )

    sim.config.setdefault("simulation_calendar", {})
    sim.config["simulation_calendar"]["start_weekday"] = int(
        settings["start_weekday"]
    )
    sim.config["simulation_calendar"]["holiday_days"] = list(
        settings["holiday_days"]
    )

    return sim


# ============================================================
# ACTION SUMMARY
# ============================================================

def parse_json_field(value):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, dict):
        return [value]

    if isinstance(value, str):
        text = value.strip()

        if not text:
            return []

        try:
            parsed = json.loads(text)
        except Exception:
            return []

        if isinstance(parsed, list):
            return parsed

        if isinstance(parsed, dict):
            return [parsed]

    return []


def extract_actions_long(main_df):
    rows = []

    if main_df is None or main_df.empty:
        return pd.DataFrame(rows)

    for _, row in main_df.iterrows():
        step = row.get("step")
        day = row.get("day")
        hour = row.get("hour")
        time_hour = float(day) * 24.0 + float(hour)

        # Newer logger path.
        for field_name in [
            "foreground_actions",
            "background_actions",
        ]:
            actions = parse_json_field(row.get(field_name))

            for action in actions:
                rows.append(
                    {
                        "step": step,
                        "day": day,
                        "hour": hour,
                        "time_hour": time_hour,
                        "source": field_name,
                        "action_name": action.get("name", "unknown"),
                        "actor_id": action.get("actor_id", ""),
                        "category": action.get("category", ""),
                        "execution_type": action.get("execution_type", ""),
                        "minutes": float(action.get("elapsed_minutes", 0.0)),
                        "power_w": float(action.get("power_w", 0.0)),
                        "energy_wh": (
                            float(action.get("power_w", 0.0))
                            * float(action.get("elapsed_minutes", 0.0))
                            / 60.0
                        ),
                    }
                )

        # Older chunk-record path.
        chunks = parse_json_field(row.get("chunk_records"))

        for chunk in chunks:
            breakdown = chunk.get("power_breakdown", [])

            for item in breakdown:
                rows.append(
                    {
                        "step": step,
                        "day": day,
                        "hour": hour,
                        "time_hour": time_hour,
                        "source": "chunk_records",
                        "action_name": item.get("name", "unknown"),
                        "actor_id": item.get("actor_id", ""),
                        "category": item.get("category", ""),
                        "execution_type": item.get("execution_type", ""),
                        "minutes": float(item.get("minutes", 0.0)),
                        "power_w": float(item.get("power_w", 0.0)),
                        "energy_wh": float(item.get("energy_wh", 0.0)),
                    }
                )

    return pd.DataFrame(rows)


def make_action_summary(actions_df):
    if actions_df is None or actions_df.empty:
        return pd.DataFrame()

    return (
        actions_df
        .groupby("action_name", as_index=False)
        .agg(
            total_minutes=("minutes", "sum"),
            total_hours=("minutes", lambda x: x.sum() / 60.0),
            total_energy_wh=("energy_wh", "sum"),
            event_rows=("action_name", "size"),
        )
        .sort_values("total_hours", ascending=False)
    )


# ============================================================
# OUTPUT HELPERS
# ============================================================

def save_json(path, payload):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)


def save_household_daily_summary(main_df, run_folder):
    if main_df is None or main_df.empty:
        return

    household_columns = [
        column for column in main_df.columns
        if column.startswith("household_")
    ]

    if not household_columns:
        return

    keep = ["day"] + household_columns
    keep = [
        col for col in keep
        if col in main_df.columns
    ]

    df = main_df[keep].copy()

    summary = (
        df
        .groupby("day")
        .tail(1)
        .reset_index(drop=True)
    )

    summary.to_csv(
        run_folder / "csv" / "household_daily_summary.csv",
        index=False,
    )


def save_debug_behavior_outputs(sim, main_df, actions_df, action_summary, run_folder):
    csv_folder = run_folder / "csv"

    main_df.to_csv(csv_folder / "main_timestep.csv", index=False)

    people_df = sim.people_to_dataframe()
    people_df.to_csv(csv_folder / "people_timestep.csv", index=False)

    actions_df.to_csv(csv_folder / "actions_long.csv", index=False)
    action_summary.to_csv(csv_folder / "action_summary.csv", index=False)

    action_event_df = sim.building_action_event_records_to_dataframe()
    bridge_df = sim.building_control_bridge_records_to_dataframe()

    action_event_df.to_csv(
        csv_folder / "building_action_events_timestep.csv",
        index=False,
    )

    bridge_df.to_csv(
        csv_folder / "building_control_bridge_timestep.csv",
        index=False,
    )


def save_light_behavior_outputs(action_summary, run_folder):
    action_summary.to_csv(
        run_folder / "csv" / "action_summary.csv",
        index=False,
    )


def save_building_outputs(profile_name, settings, sim, run_folder):
    output_paths = {}

    if settings["save_building_debug_outputs"]:
        output_paths["building_debug"] = sim.save_building_debug_outputs(
            run_folder / "building_debug"
        )

    if settings["save_building_yearly_outputs"]:
        output_paths["building_yearly"] = sim.save_building_yearly_outputs(
            run_folder / "building_yearly"
        )

    return output_paths


def save_metadata(profile_name, settings, sim, run_folder, building_output_paths):
    save_json(
        run_folder / "metadata" / "final_household.json",
        sim.household.to_dict(),
    )

    metadata = {
        "profile": profile_name,
        "duration_hours": settings["duration_hours"],
        "dt_minutes": settings["dt_minutes"],
        "start_weekday": settings["start_weekday"],
        "holiday_days": settings["holiday_days"],
        "random_seed": settings["random_seed"],
        "config_path": str(CONFIG_PATH),
        "output_folder": str(run_folder),
        "weekday_0": get_weekday_name(day=0, config=sim.config),
        "day_type_0": get_day_type(day=0, config=sim.config),
        "building_id": BUILDING_ID,
        "dwelling_id": DWELLING_ID,
        "household_id": HOUSEHOLD_ID,
        "use_building_performance": True,
        "saved_main_timestep": settings["save_main_timestep"],
        "saved_people_timestep": settings["save_people_timestep"],
        "saved_actions_long": settings["save_actions_long"],
        "building_output_paths": _paths_to_strings(building_output_paths),
    }

    save_json(
        run_folder / "metadata" / "run_settings.json",
        metadata,
    )


def _paths_to_strings(value):
    if isinstance(value, dict):
        return {
            key: _paths_to_strings(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _paths_to_strings(item)
            for item in value
        ]

    if isinstance(value, Path):
        return str(value)

    return value


# ============================================================
# PLOTS
# ============================================================

def savefig_both(fig, path_without_suffix):
    fig.tight_layout()
    fig.savefig(str(path_without_suffix) + ".png", dpi=220)
    fig.savefig(str(path_without_suffix) + ".svg")
    plt.close(fig)


def plot_action_duration(action_summary, run_folder):
    if action_summary is None or action_summary.empty:
        return

    df = action_summary.sort_values("total_hours")

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(df["action_name"], df["total_hours"])
    ax.set_xlabel("Hours")
    ax.set_ylabel("Action")
    ax.grid(True, axis="x", alpha=0.3)

    savefig_both(fig, run_folder / "plots" / "action_duration_hours")


def plot_action_energy(action_summary, run_folder):
    if action_summary is None or action_summary.empty:
        return

    df = action_summary.sort_values("total_energy_wh")

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(df["action_name"], df["total_energy_wh"])
    ax.set_xlabel("Energy [Wh]")
    ax.set_ylabel("Action")
    ax.grid(True, axis="x", alpha=0.3)

    savefig_both(fig, run_folder / "plots" / "energy_by_action")


def plot_debug_people_needs(sim, run_folder):
    people_df = sim.people_to_dataframe()

    if people_df is None or people_df.empty:
        return

    df = people_df.copy()
    df["time_hour"] = df["day"] * 24.0 + df["hour"]

    need_columns = [
        ("person_hunger", "Hunger"),
        ("person_fatigue", "Fatigue"),
        ("person_sleep_pressure", "Sleep pressure"),
    ]

    for column, label in need_columns:
        if column not in df.columns:
            continue

        fig, ax = plt.subplots(figsize=(12, 4))

        for occupant_id, part in df.groupby("occupant_id"):
            ax.plot(part["time_hour"], part[column], label=occupant_id)

        ax.set_xlabel("Simulation hour")
        ax.set_ylabel(label)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best")

        safe_label = label.lower().replace(" ", "_")
        savefig_both(fig, run_folder / "plots" / ("debug_people_" + safe_label))

def plot_debug_people_locations(sim, run_folder):
    people_df = sim.people_to_dataframe()

    if people_df is None or people_df.empty:
        return

    df = people_df.copy()

    if "location_current_space_id" not in df.columns:
        return

    df["time_hour"] = df["day"] * 24.0 + df["hour"]

    locations_sorted = sorted(
        df["location_current_space_id"].dropna().unique()
    )

    location_to_int = {
        location: index
        for index, location in enumerate(locations_sorted)
    }

    fig, ax = plt.subplots(figsize=(12, 5))

    for occupant_id, part in df.groupby("occupant_id"):
        y = part["location_current_space_id"].map(location_to_int)
        ax.plot(part["time_hour"], y, label=occupant_id)

    ax.set_xlabel("Simulation hour")
    ax.set_ylabel("Space")
    ax.set_yticks(list(location_to_int.values()))
    ax.set_yticklabels(list(location_to_int.keys()))
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")

    savefig_both(fig, run_folder / "plots" / "debug_people_location_timeline")


def make_behavior_plots(settings, sim, action_summary, run_folder):
    if not settings["make_behavior_plots"]:
        return

    plot_action_duration(action_summary, run_folder)
    plot_action_energy(action_summary, run_folder)
    plot_debug_people_needs(sim, run_folder)
    plot_debug_people_locations(sim, run_folder)


# ============================================================
# MAIN RUN LOGIC
# ============================================================

def run_profile(profile_name, settings, run_folder):
    print("\nABBEY v0.3 run")
    print("profile:", profile_name)
    print("duration_hours:", settings["duration_hours"])
    print("dt_minutes:", settings["dt_minutes"])
    print("output:", run_folder)

    sim = make_sim(settings=settings)

    print("\nRunning simulation...")
    main_df = sim.run()

    print("Simulation done.")

    actions_df = extract_actions_long(main_df)
    action_summary = make_action_summary(actions_df)

    save_household_daily_summary(main_df, run_folder)

    if settings["save_main_timestep"]:
        main_df.to_csv(
            run_folder / "csv" / "main_timestep.csv",
            index=False,
        )

    if settings["save_people_timestep"]:
        people_df = sim.people_to_dataframe()
        people_df.to_csv(
            run_folder / "csv" / "people_timestep.csv",
            index=False,
        )

    if settings["save_actions_long"]:
        actions_df.to_csv(
            run_folder / "csv" / "actions_long.csv",
            index=False,
        )
        

    save_light_behavior_outputs(
        action_summary=action_summary,
        run_folder=run_folder,
    )

    building_output_paths = save_building_outputs(
        profile_name=profile_name,
        settings=settings,
        sim=sim,
        run_folder=run_folder,
    )
    
    if settings.get("save_building_html_playback", False):
        playback_path = sim.save_building_playback_html(
            path=run_folder / "building_playback" / "building_playback.html",
            max_hours=24.0,
            frame_stride_minutes=1,
        )

        building_output_paths["building_playback_html"] = playback_path

    make_behavior_plots(
        settings=settings,
        sim=sim,
        action_summary=action_summary,
        run_folder=run_folder,
    )

    save_metadata(
        profile_name=profile_name,
        settings=settings,
        sim=sim,
        run_folder=run_folder,
        building_output_paths=building_output_paths,
    )

    return sim, main_df, actions_df, action_summary, building_output_paths


def print_run_summary(sim, run_folder, building_output_paths):
    print("\nSaved output folder:")
    print(run_folder)

    print("\nTop-level CSVs:")
    for path in sorted((run_folder / "csv").glob("*.csv")):
        print(path.name)

    print("\nBuilding output folders:")
    for key, value in building_output_paths.items():
        print(key)

        if isinstance(value, dict):
            for item_key, item_path in value.items():
                print("  ", item_key, "->", item_path)

    print("\nPlots folder:")
    print(run_folder / "plots")

    print("\nFinal household:")
    print(sim.household.to_dict())

    action_df = sim.building_action_event_records_to_dataframe()
    bridge_df = sim.building_control_bridge_records_to_dataframe()

    print("\nBuilding action events:")
    if action_df.empty:
        print("empty")
    else:
        print(action_df["action_name"].value_counts(dropna=False).head(20))

    print("\nBuilding control bridge records:")
    if bridge_df.empty:
        print("empty")
    else:
        print(bridge_df["reason"].value_counts(dropna=False).head(20))

    print("\nABBEY v0.3 run done ✅")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--profile",
        choices=["debug", "yearly"],
        default="debug",
    )

    args = parser.parse_args()

    profile_name = args.profile
    settings = copy.deepcopy(PROFILES[profile_name])

    run_folder = make_next_output_folder(OUTPUT_ROOT)

    (
        sim,
        main_df,
        actions_df,
        action_summary,
        building_output_paths,
    ) = run_profile(
        profile_name=profile_name,
        settings=settings,
        run_folder=run_folder,
    )

    print_run_summary(
        sim=sim,
        run_folder=run_folder,
        building_output_paths=building_output_paths,
    )


if __name__ == "__main__":
    main()