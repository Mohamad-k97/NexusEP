# ============================================================
# ABBEY v0.4 RUNNER / FULL SMOKE TEST
#
# Profiles:
#   smoke  -> 24h final v0.4 gate, debug + yearly outputs + HTML
#   debug  -> 24h, 1-min timestep, full outputs + plots + HTML
#   yearly -> yearly, 10-min timestep, light aggregated outputs only
#   quick  -> short developer run, useful while fixing bugs
#
# Examples:
#
#   python -m nexusep.abbey.run_test_v0_4 --profile smoke --epw auto
#   python -m nexusep.abbey.run_test_v0_4 --profile debug --epw C:/path/weather.epw
#   python -m nexusep.abbey.run_test_v0_4 --profile yearly --epw auto
#
# Temporary development only:
#
#   python -m nexusep.abbey.run_test_v0_4 --profile smoke --allow-synthetic-weather
# ============================================================

from pathlib import Path
from typing import Any, Dict, List, Optional
import argparse
import copy
import json
import math
import os
import re
import subprocess
import sys

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
    BuildingPhysicsPerformanceModel,
    make_default_family_building,
    make_default_family_physics_graph,
    default_family_ids,
    default_family_space_role_map,
)

from nexusep.abbey.building.outputs import (
    OUTPUT_MODE_DEBUG,
    OUTPUT_MODE_MINIMAL,
    validate_building_output_dataframes,
)

from nexusep.abbey.building.physics.weather import (
    WeatherProvider,
    load_epw_weather_timeseries,
    interpolate_weather_to_timestep,
    validate_weather_timeseries,
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

ENERGY_TOLERANCE_WH = 1e-6


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

EXPECTED_OCCUPANTS = [
    "working_man",
    "housewife",
    "schoolboy",
    "infant",
]


# ============================================================
# PROFILE SETTINGS
# ============================================================

PROFILES = {
    "quick": {
        "duration_hours": 2.0,
        "dt_minutes": 5,
        "start_weekday": 0,
        "holiday_days": [],
        "random_seed": 42,

        "require_epw": False,
        "save_building_html_playback": True,
        "html_max_hours": 2.0,
        "html_frame_stride_minutes": 5,

        "save_main_timestep": True,
        "save_people_timestep": True,
        "save_actions_long": True,
        "make_behavior_plots": False,

        "save_building_debug_outputs": True,
        "save_building_yearly_outputs": True,
        "save_debug_plots": False,

        "validate_debug": True,
        "validate_minimal": True,
        "strict_v04_gate": False,
        "run_phase16_suite": False,
    },

    "smoke": {
        "duration_hours": 24.0,
        "dt_minutes": 10,
        "start_weekday": 0,
        "holiday_days": [],
        "random_seed": 42,

        "require_epw": True,
        "save_building_html_playback": True,
        "html_max_hours": 24.0,
        "html_frame_stride_minutes": 10,

        "save_main_timestep": True,
        "save_people_timestep": True,
        "save_actions_long": True,
        "make_behavior_plots": True,

        "save_building_debug_outputs": True,
        "save_building_yearly_outputs": True,
        "save_debug_plots": False,

        "validate_debug": True,
        "validate_minimal": True,
        "strict_v04_gate": True,
        "run_phase16_suite": False,
    },

    "debug": {
        "duration_hours": 24.0,
        "dt_minutes": 60,
        "start_weekday": 0,
        "holiday_days": [],
        "random_seed": 42,

        "require_epw": True,
        "save_building_html_playback": True,
        "html_max_hours": 24.0,
        "html_frame_stride_minutes": 1,

        "save_main_timestep": True,
        "save_people_timestep": True,
        "save_actions_long": True,
        "make_behavior_plots": True,

        "save_building_debug_outputs": True,
        "save_building_yearly_outputs": True,
        "save_debug_plots": True,

        "validate_debug": True,
        "validate_minimal": True,
        "strict_v04_gate": True,
        "run_phase16_suite": False,
    },

    "yearly": {
        "duration_hours": 24.0 * 365.0,
        "dt_minutes": 60,
        "start_weekday": 0,
        "holiday_days": [],
        "random_seed": 42,

        "require_epw": True,
        "save_building_html_playback": False,
        "html_max_hours": 24.0,
        "html_frame_stride_minutes": 10,

        "save_main_timestep": False,
        "save_people_timestep": False,
        "save_actions_long": False,
        "make_behavior_plots": False,

        "save_building_debug_outputs": False,
        "save_building_yearly_outputs": True,
        "save_debug_plots": False,

        "validate_debug": False,
        "validate_minimal": True,
        "strict_v04_gate": True,
        "run_phase16_suite": False,
    },
}


# ============================================================
# ASSERTIONS
# ============================================================

def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def truthy_value(value):
    if isinstance(value, bool):
        return value

    if value is None:
        return False

    text = str(value).strip().lower()

    return text in [
        "true",
        "1",
        "yes",
        "y",
        "t",
    ]


def assert_non_empty_dataframe(df, name):
    assert_true(
        df is not None,
        name + " dataframe is None.",
    )

    assert_true(
        not df.empty,
        name + " dataframe is empty.",
    )


def assert_path_exists(path, label):
    path = Path(path)

    assert_true(
        path.exists(),
        label + " missing path: " + str(path),
    )

    return path


def assert_csv_non_empty(path, label):
    path = assert_path_exists(path, label)
    df = pd.read_csv(path)

    assert_non_empty_dataframe(
        df=df,
        name=label,
    )

    return df


def assert_validation_ok(validation, label):
    if not bool(validation.get("ok", False)):
        raise AssertionError(
            label
            + " failed."
            + "\nerrors="
            + str(validation.get("errors", []))
            + "\nmissing_columns="
            + str(validation.get("missing_columns", []))
            + "\nnon_finite_columns="
            + str(validation.get("non_finite_columns", {}))
            + "\nout_of_range_columns="
            + str(validation.get("out_of_range_columns", {}))
            + "\nenergy_checks="
            + str(validation.get("energy_checks", {}))
        )


def assert_no_nan_or_inf(df, columns, label):
    bad = {}
    missing = []

    for column in columns:
        if column not in df.columns:
            missing.append(column)
            continue

        values = pd.to_numeric(df[column], errors="coerce")

        bad_count = int(
            values.map(
                lambda value: (
                    pd.isna(value)
                    or not math.isfinite(float(value))
                )
            ).sum()
        )

        if bad_count > 0:
            bad[column] = bad_count

    assert_true(
        not missing,
        label + " missing finite-check columns: " + str(missing),
    )

    assert_true(
        not bad,
        label + " has non-finite values: " + str(bad),
    )


def assert_range(df, column, lower, upper, label, required=True):
    if column not in df.columns:
        assert_true(
            not required,
            label + " missing column: " + str(column),
        )

        return

    values = pd.to_numeric(df[column], errors="coerce")

    bad_mask = values.map(
        lambda value: (
            pd.isna(value)
            or not math.isfinite(float(value))
            or float(value) < float(lower)
            or float(value) > float(upper)
        )
    )

    bad_count = int(bad_mask.sum())

    assert_true(
        bad_count == 0,
        label
        + " column "
        + str(column)
        + " has "
        + str(bad_count)
        + " values outside ["
        + str(lower)
        + ", "
        + str(upper)
        + "]. min="
        + str(values.min())
        + ", max="
        + str(values.max()),
    )


def assert_some_variation(df, column, label, tolerance=1e-9, required=True):
    if column not in df.columns:
        assert_true(
            not required,
            label + " missing variation column: " + str(column),
        )

        return

    values = pd.to_numeric(df[column], errors="coerce").dropna()

    if len(values) < 2:
        return

    delta = float(values.max()) - float(values.min())

    assert_true(
        delta > float(tolerance),
        label
        + " column "
        + str(column)
        + " did not vary enough. delta="
        + str(delta),
    )


# ============================================================
# OUTPUT FOLDER
# ============================================================

def make_next_output_folder(output_root, profile_name):
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    prefix = "abbey_v04_" + str(profile_name) + "_run_"

    existing = []

    for path in output_root.iterdir():
        if not path.is_dir():
            continue

        match = re.match(r"^" + re.escape(prefix) + r"(\d+)$", path.name)

        if match:
            existing.append(int(match.group(1)))

    next_id = max(existing, default=0) + 1

    run_folder = output_root / (prefix + "{:03d}".format(next_id))
    run_folder.mkdir(parents=True, exist_ok=False)

    (run_folder / "csv").mkdir()
    (run_folder / "plots").mkdir()
    (run_folder / "metadata").mkdir()
    (run_folder / "building_debug").mkdir()
    (run_folder / "building_yearly").mkdir()
    (run_folder / "building_playback").mkdir()

    return run_folder


# ============================================================
# EPW WEATHER
# ============================================================

def candidate_epw_paths():
    env_path = os.environ.get("ABBEY_EPW_PATH")

    if env_path:
        yield Path(env_path)

    search_roots = [
        PROJECT_ROOT / "nexusep" / "data" / "weather",
        PROJECT_ROOT / "nexusep" / "data" / "abbey" / "weather",
        PROJECT_ROOT / "nexusep" / "data",
        PROJECT_ROOT / "data" / "weather",
        Path.cwd(),
    ]

    seen = set()

    for root in search_roots:
        if not root.exists():
            continue

        try:
            matches = sorted(root.rglob("*.epw"))
        except Exception:
            matches = []

        for path in matches:
            resolved = str(path.resolve())

            if resolved in seen:
                continue

            seen.add(resolved)
            yield path


def resolve_epw_path(epw_arg):
    if epw_arg is None:
        epw_arg = "auto"

    epw_arg = str(epw_arg).strip()

    if epw_arg.lower() in ["auto", "", "none"]:
        for path in candidate_epw_paths():
            if path.exists():
                return path.resolve()

        return None

    path = Path(epw_arg)

    if not path.exists():
        raise FileNotFoundError("EPW file not found: " + str(path))

    return path.resolve()
class CyclicWeatherProvider:
    """
    Repeat a TMY/EPW weather provider if the interpolated timestep table is
    a few rows short of the requested simulation length.

    This mainly protects full-year 10-minute runs where interpolation can
    drop the final sub-hourly samples near year end.
    """

    def __init__(self, base_provider, required_steps):
        self.base_provider = base_provider
        self.required_steps = int(required_steps)

        if self.required_steps <= 0:
            raise ValueError("required_steps must be positive.")

        self.base_steps = int(base_provider.number_of_steps())

        if self.base_steps <= 0:
            raise ValueError("base weather provider has no steps.")

    def get_state_by_step(self, step_index):
        return self.base_provider.get_state_by_step(
            int(step_index) % self.base_steps
        )

    def get_state(self, datetime_value):
        if hasattr(self.base_provider, "get_state"):
            return self.base_provider.get_state(datetime_value)

        return self.get_state_by_step(0)

    def number_of_steps(self):
        return self.required_steps

    def start_datetime(self):
        if hasattr(self.base_provider, "start_datetime"):
            return self.base_provider.start_datetime()

        return None

    def end_datetime(self):
        if hasattr(self.base_provider, "end_datetime"):
            return self.base_provider.end_datetime()

        return None

    def to_dict(self):
        return {
            "source": "cyclic_weather_provider",
            "required_steps": self.required_steps,
            "base_steps": self.base_steps,
        }

def make_weather_provider_from_epw(epw_path, dt_minutes, required_steps):
    weather_series = load_epw_weather_timeseries(
        epw_path=str(epw_path),
        is_tmy=True,
    )

    weather_series = interpolate_weather_to_timestep(
        weather_series=weather_series,
        dt_minutes=int(dt_minutes),
        allow_extrapolation=True,
    )

    validate_weather_timeseries(
        weather_series=weather_series,
        require_timestep_dataframe=True,
        expected_dt_minutes=int(dt_minutes),
        raise_on_error=True,
    )

    provider = WeatherProvider(
        weather_series=weather_series,
        use_timestep_dataframe=True,
    )

    if provider.number_of_steps() < int(required_steps):
        provider = CyclicWeatherProvider(
            base_provider=provider,
            required_steps=int(required_steps),
        )

    return provider


def make_weather_provider(settings, epw_arg, allow_synthetic_weather):
    duration_hours = float(settings["duration_hours"])
    dt_minutes = float(settings["dt_minutes"])
    required_steps = int(round(duration_hours / (dt_minutes / 60.0)))

    epw_path = resolve_epw_path(epw_arg)

    if epw_path is None:
        if bool(settings.get("require_epw", False)) and not allow_synthetic_weather:
            raise FileNotFoundError(
                "No EPW found. Pass --epw C:/path/file.epw, set ABBEY_EPW_PATH, "
                "or use --allow-synthetic-weather for temporary development."
            )

        print("\nWARNING: no EPW found.")
        print("Using BuildingPhysicsPerformanceModel synthetic weather fallback.")
        print("This is OK for quick development, not for final acceptance.")

        return None, {
            "using_epw": False,
            "epw_path": None,
            "source": "synthetic_fallback",
            "provider_steps": None,
        }

    print("\nUsing EPW weather:")
    print(epw_path)

    provider = make_weather_provider_from_epw(
        epw_path=epw_path,
        dt_minutes=int(dt_minutes),
        required_steps=required_steps,
    )

    return provider, {
        "using_epw": True,
        "epw_path": str(epw_path),
        "source": "epw",
"provider_steps": provider.number_of_steps(),
"start_datetime": (
    provider.start_datetime().isoformat()
    if provider.start_datetime() is not None
    else None
),
"end_datetime": (
    provider.end_datetime().isoformat()
    if provider.end_datetime() is not None
    else None
),
"weather_provider_type": provider.__class__.__name__,
    }


# ============================================================
# FAMILY MODEL
# ============================================================

def make_zone_observations():
    values = {
        LIVING_ROOM: ("Living room", 20.5, 600.0, 0.60, 0.25),
        BEDROOM_1: ("Parents bedroom", 20.0, 580.0, 0.35, 0.18),
        BEDROOM_2: ("Child bedroom", 20.0, 575.0, 0.35, 0.18),
        OFFICE: ("Office", 20.3, 590.0, 0.50, 0.22),
        KITCHEN: ("Kitchen", 20.7, 610.0, 0.45, 0.25),
        BATHROOM: ("Bathroom", 21.0, 560.0, 0.15, 0.20),
        LAUNDRY: ("Laundry", 20.3, 570.0, 0.10, 0.35),
        ENTRANCE: ("Entrance", 19.5, 550.0, 0.20, 0.30),
    }

    out = {}

    for zone_id, item in values.items():
        zone_name, indoor_temp, co2_ppm, daylight, noise = item

        occupied_person_ids = []

        if zone_id == LIVING_ROOM:
            occupied_person_ids = list(EXPECTED_OCCUPANTS)

        out[zone_id] = ZoneObservation(
            zone_id=zone_id,
            zone_name=zone_name,
            indoor_temp=float(indoor_temp),
            co2_ppm=float(co2_ppm),
            indoor_daylight=float(daylight),
            indoor_noise=float(noise),
            indoor_relative_humidity_percent=50.0,
            indoor_humidity_ratio_kg_kg=0.008,
            heating_on=False,
            cooling_on=False,
            mechanical_ventilation_on=True,
            lights_on=False,
            window_open=False,
            curtain_open=True,
            occupied_person_ids=occupied_person_ids,
            number_of_people=len(occupied_person_ids),
        )

    return out


def make_observation():
    return DwellingObservation(
        indoor_temp=20.5,
        outdoor_temp=10.0,
        co2_ppm=600.0,
        indoor_daylight=0.60,
        indoor_noise=0.25,
        indoor_relative_humidity_percent=50.0,
        indoor_humidity_ratio_kg_kg=0.008,
        electricity_tariff=0.25,
        default_zone_id=LIVING_ROOM,
        zone_observations=make_zone_observations(),
    )


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
        occupant_ids=list(EXPECTED_OCCUPANTS),
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


# ============================================================
# SIM FACTORY
# ============================================================

def make_sim(settings, weather_provider=None):
    building = make_default_family_building()

    graph = make_default_family_physics_graph(
        building_model=building,
    )

    building_performance_model = BuildingPhysicsPerformanceModel(
        building_model=building,
        physics_graph=graph,
        use_physics_engine=True,
        allow_legacy_physics_fallback=False,
    )

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
        building_physics_graph=graph,
        building_performance_model=building_performance_model,
        use_building_performance=True,
        weather_provider=weather_provider,
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

        for field_name in [
            "foreground_actions",
            "background_actions",
        ]:
            actions = parse_json_field(row.get(field_name))

            for action in actions:
                elapsed_minutes = float(action.get("elapsed_minutes", 0.0))
                power_w = float(action.get("power_w", 0.0))

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
                        "minutes": elapsed_minutes,
                        "power_w": power_w,
                        "energy_wh": power_w * elapsed_minutes / 60.0,
                    }
                )

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
# SAVE HELPERS
# ============================================================

def save_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(
            payload,
            file,
            indent=2,
            ensure_ascii=False,
            default=str,
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


def save_household_daily_summary(main_df, run_folder):
    if main_df is None or main_df.empty:
        return None

    household_columns = [
        column for column in main_df.columns
        if column.startswith("household_")
    ]

    if not household_columns:
        return None

    keep = ["day"] + household_columns
    keep = [
        column for column in keep
        if column in main_df.columns
    ]

    df = main_df[keep].copy()

    summary = (
        df
        .groupby("day")
        .tail(1)
        .reset_index(drop=True)
    )

    path = run_folder / "csv" / "household_daily_summary.csv"
    summary.to_csv(path, index=False)

    return path


def save_behavior_outputs(settings, sim, main_df, actions_df, action_summary, run_folder):
    csv_folder = run_folder / "csv"
    paths = {}

    if settings["save_main_timestep"]:
        path = csv_folder / "main_timestep.csv"
        main_df.to_csv(path, index=False)
        paths["main_timestep_csv"] = path

    if settings["save_people_timestep"]:
        path = csv_folder / "people_timestep.csv"
        sim.people_to_dataframe().to_csv(path, index=False)
        paths["people_timestep_csv"] = path

    if settings["save_actions_long"]:
        path = csv_folder / "actions_long.csv"
        actions_df.to_csv(path, index=False)
        paths["actions_long_csv"] = path

    action_summary_path = csv_folder / "action_summary.csv"
    action_summary.to_csv(action_summary_path, index=False)
    paths["action_summary_csv"] = action_summary_path

    action_event_df = sim.building_action_event_records_to_dataframe()
    bridge_df = sim.building_control_bridge_records_to_dataframe()

    action_event_path = csv_folder / "building_action_events_timestep.csv"
    bridge_path = csv_folder / "building_control_bridge_timestep.csv"

    action_event_df.to_csv(action_event_path, index=False)
    bridge_df.to_csv(bridge_path, index=False)

    paths["building_action_events_timestep_csv"] = action_event_path
    paths["building_control_bridge_timestep_csv"] = bridge_path

    household_path = save_household_daily_summary(
        main_df=main_df,
        run_folder=run_folder,
    )

    if household_path is not None:
        paths["household_daily_summary_csv"] = household_path

    return paths


def save_building_outputs(settings, sim, run_folder):
    output_paths = {}

    if settings["save_building_debug_outputs"]:
        output_paths["building_debug"] = sim.save_building_debug_outputs(
            run_folder / "building_debug",
            include_plots=bool(settings.get("save_debug_plots", False)),
            include_long_records=True,
            include_interzone_timestep_records=True,
            include_window_detail_timestep_records=True,
        )

    if settings["save_building_yearly_outputs"]:
        output_paths["building_yearly"] = sim.save_building_yearly_outputs(
            run_folder / "building_yearly",
            output_mode=OUTPUT_MODE_MINIMAL,
            include_timestep_diagnostics=False,
            include_long_records=False,
            include_interzone_summaries=True,
            include_interzone_timestep_records=False,
            include_window_detail_summaries=True,
            include_window_detail_timestep_records=False,
        )

    if settings.get("save_building_html_playback", False):
        playback_path = sim.save_building_playback_html(
            path=run_folder / "building_playback" / "building_playback.html",
            max_hours=float(settings.get("html_max_hours", 24.0)),
            frame_stride_minutes=int(settings.get("html_frame_stride_minutes", 1)),
        )

        output_paths["building_playback_html"] = playback_path

    return output_paths


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
# VALIDATION
# ============================================================

def validate_output_records(settings, sim):
    zone_df = sim.building_zone_records_to_dataframe()
    dwelling_df = sim.building_dwelling_records_to_dataframe()
    building_df = sim.building_records_to_dataframe()

    assert_non_empty_dataframe(zone_df, "zone records")
    assert_non_empty_dataframe(dwelling_df, "dwelling records")
    assert_non_empty_dataframe(building_df, "building records")

    results = {
        "zone_df": zone_df,
        "dwelling_df": dwelling_df,
        "building_df": building_df,
    }

    if settings.get("validate_debug", False):
        debug_validation = validate_building_output_dataframes(
            zone_df=zone_df,
            dwelling_df=dwelling_df,
            building_df=building_df,
            mode=OUTPUT_MODE_DEBUG,
            tolerance_wh=ENERGY_TOLERANCE_WH,
        )

        assert_validation_ok(
            validation=debug_validation,
            label="debug output validation",
        )

        results["debug_validation"] = debug_validation

    if settings.get("validate_minimal", False):
        minimal_validation = validate_building_output_dataframes(
            zone_df=zone_df,
            dwelling_df=dwelling_df,
            building_df=building_df,
            mode=OUTPUT_MODE_MINIMAL,
            tolerance_wh=ENERGY_TOLERANCE_WH,
        )

        assert_validation_ok(
            validation=minimal_validation,
            label="minimal/yearly output validation",
        )

        results["minimal_validation"] = minimal_validation

    return results


def validate_saved_outputs(settings, building_output_paths):
    if settings["save_building_debug_outputs"]:
        debug_paths = building_output_paths.get("building_debug", {})

        required_debug_keys = [
            "zone_timestep_csv",
            "dwelling_timestep_csv",
            "building_timestep_csv",
            "internal_source_records_csv",
            "internal_source_zone_csv",
            "internal_source_building_csv",
            "interzone_thermal_timestep_csv",
            "interzone_airflow_timestep_csv",
            "window_detail_timestep_csv",
            "window_airflow_timestep_csv",
        ]

        for key in required_debug_keys:
            assert_true(
                key in debug_paths,
                "Missing debug output key: " + str(key),
            )

            assert_csv_non_empty(
                path=debug_paths[key],
                label="debug output " + str(key),
            )

    if settings["save_building_yearly_outputs"]:
        yearly_paths = building_output_paths.get("building_yearly", {})

        required_yearly_keys = [
            "hourly_zone_summary_csv",
            "daily_zone_summary_csv",
            "energy_by_zone_csv",
            "control_active_hours_by_zone_csv",
            "daily_dwelling_summary_csv",
            "energy_by_dwelling_csv",
            "daily_building_summary_csv",
            "energy_by_building_csv",
        ]

        for key in required_yearly_keys:
            assert_true(
                key in yearly_paths,
                "Missing yearly output key: " + str(key),
            )

            assert_csv_non_empty(
                path=yearly_paths[key],
                label="yearly output " + str(key),
            )

    if settings.get("save_building_html_playback", False):
        assert_true(
            "building_playback_html" in building_output_paths,
            "Missing building playback HTML path.",
        )

        assert_path_exists(
            building_output_paths["building_playback_html"],
            "building playback HTML",
        )


def validate_no_fallback(zone_df, building_df):
    for df, label in [
        (zone_df, "zone"),
        (building_df, "building"),
    ]:
        for column in [
            "physics_engine_active",
            "legacy_fallback_used",
            "physics_path",
            "performance_path",
        ]:
            assert_true(
                column in df.columns,
                label + " records missing column: " + str(column),
            )

        active_values = [
            truthy_value(value)
            for value in df["physics_engine_active"].tolist()
        ]

        fallback_values = [
            truthy_value(value)
            for value in df["legacy_fallback_used"].tolist()
        ]

        assert_true(
            all(active_values),
            label + " records should all have physics_engine_active=True.",
        )

        assert_true(
            not any(fallback_values),
            label + " records should never use legacy fallback.",
        )

        assert_true(
            set(df["physics_path"].astype(str).dropna().unique()) == {"engine"},
            label + " physics_path should only be engine.",
        )

        assert_true(
            set(df["performance_path"].astype(str).dropna().unique()) == {"engine"},
            label + " performance_path should only be engine.",
        )


def validate_physical_plausibility(zone_df):
    finite_columns = [
        "number_of_people",
        "indoor_temp_c",
        "indoor_mass_temp_c",
        "co2_ppm",
        "indoor_daylight",
        "indoor_noise",
        "indoor_relative_humidity_percent",
        "indoor_humidity_ratio_kg_kg",
        "heating_delivered_energy_wh",
        "cooling_delivered_energy_wh",
        "lighting_energy_wh",
        "appliance_energy_wh",
        "hvac_input_energy_wh",
        "total_energy_wh",
    ]

    assert_no_nan_or_inf(
        df=zone_df,
        columns=finite_columns,
        label="zone physical outputs",
    )

    assert_range(zone_df, "number_of_people", 0.0, 4.0, "occupancy")
    assert_range(zone_df, "indoor_temp_c", -5.0, 45.0, "indoor temperature")
    assert_range(zone_df, "indoor_mass_temp_c", -5.0, 45.0, "indoor mass temperature")
    assert_range(zone_df, "co2_ppm", 350.0, 6000.0, "CO2")
    assert_range(zone_df, "indoor_daylight", 0.0, 1.0, "daylight")
    assert_range(zone_df, "indoor_noise", 0.0, 1.0, "noise")
    assert_range(zone_df, "indoor_relative_humidity_percent", 0.0, 100.0, "RH")
    assert_range(zone_df, "indoor_humidity_ratio_kg_kg", 0.0, 0.05, "humidity ratio")
    assert_range(zone_df, "total_energy_wh", 0.0, 1.0e7, "zone total energy")

    assert_range(zone_df, "indoor_noise_db", 0.0, 120.0, "indoor noise dB", required=False)
    assert_range(zone_df, "outdoor_noise_db", 0.0, 120.0, "outdoor noise dB", required=False)
    assert_range(zone_df, "daylight_illuminance_lux", 0.0, 200000.0, "daylight lux", required=False)
    assert_range(zone_df, "indoor_illuminance_lux", 0.0, 200000.0, "indoor lux", required=False)

    assert_some_variation(zone_df, "indoor_temp_c", "indoor temperature", tolerance=1e-6)
    assert_some_variation(zone_df, "co2_ppm", "CO2", tolerance=1e-6)
    assert_some_variation(zone_df, "indoor_daylight", "daylight", tolerance=1e-9)


def validate_run_length(settings, sim):
    duration_hours = float(settings["duration_hours"])
    dt_minutes = float(settings["dt_minutes"])

    expected_steps = int(round(duration_hours / (dt_minutes / 60.0)))
    zone_count = len(list(sim.building_model.all_zone_ids()))
    expected_zone_rows = expected_steps * zone_count

    assert_true(
        len(sim.building_records) == expected_steps,
        "Expected one building record per timestep. expected="
        + str(expected_steps)
        + ", got="
        + str(len(sim.building_records)),
    )

    assert_true(
        len(sim.building_zone_records) == expected_zone_rows,
        "Expected one zone record per zone per timestep. expected="
        + str(expected_zone_rows)
        + ", got="
        + str(len(sim.building_zone_records)),
    )

    assert_true(
        len(sim.building_dwelling_records) >= expected_steps,
        "Expected at least one dwelling record per timestep.",
    )


def validate_final_observation(sim):
    observation = sim.observation

    assert_true(
        observation is not None,
        "Final observation is None.",
    )

    assert_true(
        observation.default_zone_id in observation.zone_observations,
        "Final observation default_zone_id is not valid.",
    )

    assert_true(
        len(observation.zone_observations) == len(list(sim.building_model.all_zone_ids())),
        "Final observation should contain all building zones.",
    )


# ============================================================
# OPTIONAL PHASE 16 SUITE
# ============================================================

PHASE16_MODULES = [
    "tests.phase16.test_16_0_validation_harness",
    "tests.phase16.test_16_1_passive_thermal_sanity",
]


def run_optional_phase16_suite():
    print("\nRunning optional Phase 16 suite...")

    for module_name in PHASE16_MODULES:
        print("  ", module_name)

        completed = subprocess.run(
            [sys.executable, "-m", module_name],
            cwd=str(PROJECT_ROOT),
        )

        assert_true(
            completed.returncode == 0,
            "Phase 16 module failed: " + str(module_name),
        )

    print("PASS: optional Phase 16 suite")


# ============================================================
# METADATA / SUMMARY
# ============================================================

def save_metadata(
    profile_name,
    settings,
    sim,
    run_folder,
    weather_summary,
    behavior_output_paths,
    building_output_paths,
    validation_payload,
):
    save_json(
        run_folder / "metadata" / "final_household.json",
        sim.household.to_dict(),
    )

    metadata = {
        "profile": profile_name,
        "version": "v0.4",
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
        "occupants": list(EXPECTED_OCCUPANTS),
        "use_household_execution": bool(sim.use_household_execution),
        "use_building_performance": True,
        "building_performance_model": sim.building_performance_model.__class__.__name__,
        "weather": weather_summary,
        "behavior_output_paths": _paths_to_strings(behavior_output_paths),
        "building_output_paths": _paths_to_strings(building_output_paths),
        "debug_validation_ok": bool(
            validation_payload.get("debug_validation", {}).get("ok", False)
        ),
        "minimal_validation_ok": bool(
            validation_payload.get("minimal_validation", {}).get("ok", False)
        ),
        "zone_record_count": len(sim.building_zone_records),
        "dwelling_record_count": len(sim.building_dwelling_records),
        "building_record_count": len(sim.building_records),
        "legacy_fallback_used": False,
        "physics_engine_active": True,
    }

    save_json(
        run_folder / "metadata" / "run_settings.json",
        metadata,
    )

    return metadata


def print_run_summary(sim, run_folder, building_output_paths):
    print("\nSaved output folder:")
    print(run_folder)

    print("\nTop-level CSVs:")
    for path in sorted((run_folder / "csv").glob("*.csv")):
        print(path.name)

    print("\nBuilding output paths:")
    for key, value in building_output_paths.items():
        print(key)

        if isinstance(value, dict):
            for item_key, item_path in value.items():
                print("  ", item_key, "->", item_path)
        else:
            print("  ", value)

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

    print("\nPASS: ABBEY v0.4 run completed")


# ============================================================
# MAIN RUN LOGIC
# ============================================================

def apply_cli_overrides(settings, args):
    out = copy.deepcopy(settings)

    if args.duration_hours is not None:
        out["duration_hours"] = float(args.duration_hours)

    if args.dt_minutes is not None:
        out["dt_minutes"] = float(args.dt_minutes)

    if args.random_seed is not None:
        out["random_seed"] = int(args.random_seed)

    if args.include_plots:
        out["make_behavior_plots"] = True
        out["save_debug_plots"] = True

    if args.no_html:
        out["save_building_html_playback"] = False

    if args.html:
        out["save_building_html_playback"] = True

    if args.run_phase16_suite:
        out["run_phase16_suite"] = True

    return out


def run_profile(profile_name, settings, args, run_folder):
    print("\nABBEY v0.4 run")
    print("profile:", profile_name)
    print("duration_hours:", settings["duration_hours"])
    print("dt_minutes:", settings["dt_minutes"])
    print("output:", run_folder)

    weather_provider, weather_summary = make_weather_provider(
        settings=settings,
        epw_arg=args.epw,
        allow_synthetic_weather=bool(args.allow_synthetic_weather),
    )

    sim = make_sim(
        settings=settings,
        weather_provider=weather_provider,
    )

    assert_true(
        isinstance(sim.building_performance_model, BuildingPhysicsPerformanceModel),
        "v0.4 run must use BuildingPhysicsPerformanceModel.",
    )

    assert_true(
        sim.use_household_execution is True,
        "v0.4 run must use household execution.",
    )

    assert_true(
        sim.building_model is not None,
        "v0.4 run must use default family building.",
    )

    assert_true(
        sim.building_physics_graph is not None,
        "v0.4 run must use default physics graph.",
    )

    print("\nRunning simulation...")
    main_df = sim.run()
    print("Simulation done.")

    actions_df = extract_actions_long(main_df)
    action_summary = make_action_summary(actions_df)

    behavior_output_paths = save_behavior_outputs(
        settings=settings,
        sim=sim,
        main_df=main_df,
        actions_df=actions_df,
        action_summary=action_summary,
        run_folder=run_folder,
    )

    building_output_paths = save_building_outputs(
        settings=settings,
        sim=sim,
        run_folder=run_folder,
    )

    make_behavior_plots(
        settings=settings,
        sim=sim,
        action_summary=action_summary,
        run_folder=run_folder,
    )

    validate_run_length(
        settings=settings,
        sim=sim,
    )

    validation_payload = validate_output_records(
        settings=settings,
        sim=sim,
    )

    validate_saved_outputs(
        settings=settings,
        building_output_paths=building_output_paths,
    )

    zone_df = validation_payload["zone_df"]
    building_df = validation_payload["building_df"]

    validate_no_fallback(
        zone_df=zone_df,
        building_df=building_df,
    )

    validate_physical_plausibility(zone_df)
    validate_final_observation(sim)

    metadata = save_metadata(
        profile_name=profile_name,
        settings=settings,
        sim=sim,
        run_folder=run_folder,
        weather_summary=weather_summary,
        behavior_output_paths=behavior_output_paths,
        building_output_paths=building_output_paths,
        validation_payload=validation_payload,
    )

    if settings.get("run_phase16_suite", False):
        run_optional_phase16_suite()

    return {
        "sim": sim,
        "main_df": main_df,
        "actions_df": actions_df,
        "action_summary": action_summary,
        "behavior_output_paths": behavior_output_paths,
        "building_output_paths": building_output_paths,
        "metadata": metadata,
    }


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES.keys()),
        default="yearly",
    )

    parser.add_argument(
        "--epw",
        default="auto",
        help=(
            "EPW path. Use 'auto' to search ABBEY_EPW_PATH and common data folders."
        ),
    )

    parser.add_argument(
        "--allow-synthetic-weather",
        action="store_true",
        help="Allow run without EPW. Development only.",
    )

    parser.add_argument(
        "--duration-hours",
        type=float,
        default=None,
        help="Override profile duration.",
    )

    parser.add_argument(
        "--dt-minutes",
        type=float,
        default=None,
        help="Override profile timestep.",
    )

    parser.add_argument(
        "--random-seed",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--output-root",
        default=str(OUTPUT_ROOT),
    )

    parser.add_argument(
        "--include-plots",
        action="store_true",
    )

    parser.add_argument(
        "--html",
        action="store_true",
        help="Force HTML playback on.",
    )

    parser.add_argument(
        "--no-html",
        action="store_true",
        help="Force HTML playback off.",
    )

    parser.add_argument(
        "--run-phase16-suite",
        action="store_true",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    profile_name = args.profile
    settings = apply_cli_overrides(
        settings=PROFILES[profile_name],
        args=args,
    )

    run_folder = make_next_output_folder(
        output_root=Path(args.output_root),
        profile_name=profile_name,
    )

    result = run_profile(
        profile_name=profile_name,
        settings=settings,
        args=args,
        run_folder=run_folder,
    )

    print_run_summary(
        sim=result["sim"],
        run_folder=run_folder,
        building_output_paths=result["building_output_paths"],
    )

    print("\nPASS: v0.4 run completed")
    print("PASS: BuildingPhysicsPerformanceModel used")
    print("PASS: household execution used")
    print("PASS: default family building + physics graph used")
    print("PASS: physics engine active")
    print("PASS: no legacy fallback")
    print("PASS: debug/yearly/html outputs according to profile")
    print("PASS: validation and plausibility checks passed")


if __name__ == "__main__":
    main()
