"""Canonical production-engine mapping for the IEA EBC Annex 71 Twin Houses.

The original repository diagnostic reduced the experiment to one room and a
stand-alone RC helper.  This module instead maps the published N2 air-body
definition to a strict :class:`ScenarioV1` and executes the object adapter.
It deliberately calls the User 1 evaluation a temporal transfer, not a blind
validation: the official Annex 71 open files expose its measured targets.
"""

from __future__ import annotations

import math
import re
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

import numpy as np

from nexusep.abbey.building.physics.solar import calculate_solar_position
from nexusep.adapters.object_engine import ObjectEngineAdapter
from nexusep.schema.compiler import compile_physics_graph
from nexusep.schema.scenario import CanonicalScenario, ScenarioV1
from nexusep.schema.timestep import (
    CanonicalGraphReference,
    DeterministicRunContext,
    InternalGain,
    OccupantStepState,
    PriorZonePhysicalState,
    SimulationStepInput,
    SystemAvailability,
    ZoneControlCommand,
)

SCENARIO_ID = "annex71_n2_four_airbody"
BUILDING_ID = "annex71_n2"
DWELLING_ID = "annex71_n2_dwelling"
TIMEZONE = "Europe/Berlin"
DT_MINUTES = 60.0
AIR_DENSITY_KG_M3 = 1.204
AIR_HEAT_CAPACITY_J_KG_K = 1005.0

# Official air-body aggregation from the Annex 71 experimental specification.
ZONE_ROOM_AREAS_M2: dict[str, dict[str, float]] = {
    "ground_airbody": {
        "living": 33.65,
        "corridor": 5.46,
        "bath": 6.92,
        "dining": 11.19,
        "doorway": 5.84,
    },
    "kitchen_airbody": {"kitchen": 7.44},
    "sleeping_airbody": {"bed": 11.19},
    "attic_airbody": {"child1": 34.60, "child2": 36.50, "stairs": 12.90},
}
ZONE_VOLUMES_M3 = {
    "ground_airbody": 164.00,
    "kitchen_airbody": 19.34,
    "sleeping_airbody": 29.09,
    "attic_airbody": 151.72,
}
ZONE_TYPES = {
    "ground_airbody": "living",
    "kitchen_airbody": "kitchen",
    "sleeping_airbody": "bedroom",
    "attic_airbody": "bedroom",
}

# Overall opening areas and orientations from the official plans.  The thermal
# study uses the published U-value and EN 410 normal-incidence transmittance.
WINDOWS: dict[str, tuple[tuple[str, float, float], ...]] = {
    "ground_airbody": (
        ("south_living_type2", 2.63, 180.0),
        ("south_living_type3", 5.14, 180.0),
        ("west_living_type1", 1.89, 270.0),
        ("south_dining_type1", 1.89, 180.0),
        ("east_bath_type1", 1.89, 90.0),
    ),
    "kitchen_airbody": (("west_kitchen_type1", 1.89, 270.0),),
    "sleeping_airbody": (("north_sleeping_type1", 1.89, 0.0),),
    "attic_airbody": (
        ("west_child1_type1", 1.89, 270.0),
        ("south_child1_roof_type4", 1.49, 180.0),
        ("east_child2_type5", 3.00, 90.0),
    ),
}

# Physical interior-face areas used by the two-node air/mass coupling.  The
# ground/attic value is their published separating floor; the two sealed-room
# values are conservative wall areas reconstructed from the dimensioned plan.
# Conductance is specified independently, so these areas do not inflate heat
# transfer between air bodies.
INTERZONE_AREAS_M2 = {
    "attic_airbody": 84.06,
    "kitchen_airbody": 20.0,
    "sleeping_airbody": 25.0,
}

ROOM_TEMPERATURE_FIELD = {
    room: f"n2_aroom_{room}_110_AT"
    for room in {
        room for zone_rooms in ZONE_ROOM_AREAS_M2.values() for room in zone_rooms
    }
}
ROOM_HEATING_FIELD = {
    room: f"n2_aroom_{room}_heat_elP" for room in ROOM_TEMPERATURE_FIELD
}
ROOM_INTERNAL_GAIN_FIELD = {
    room: f"n2_aroom_{room}_IHS_elP" for room in ROOM_TEMPERATURE_FIELD
}

CELL_REFERENCE = re.compile(r"([A-Z]+)([0-9]+)")


@dataclass(frozen=True)
class Annex71ZoneObservation:
    zone_id: str
    air_temperature_c: float
    relative_humidity_fraction: float
    heating_power_w: float
    internal_gain_w: float
    ventilation_supply_temperature_c: float
    ventilation_supply_flow_m3_s: float


@dataclass(frozen=True)
class Annex71Interval:
    timestamp: datetime
    outdoor_temperature_c: float
    relative_humidity_fraction: float
    atmospheric_pressure_pa: float
    outdoor_co2_ppm: float
    wind_speed_m_s: float
    wind_direction_deg: float
    diffuse_horizontal_radiation_w_m2: float
    global_horizontal_radiation_w_m2: float
    rain: bool
    zones: tuple[Annex71ZoneObservation, ...]

    def zone(self, zone_id: str) -> Annex71ZoneObservation:
        return next(item for item in self.zones if item.zone_id == zone_id)


@dataclass(frozen=True)
class Annex71ModelParameters:
    """Frozen reduced-order parameters used by the production engine."""

    total_effective_capacity_j_k: float = 42_000_000.0
    ground_envelope_conductance_w_k: float = 46.2
    kitchen_envelope_conductance_w_k: float = 8.6
    sleeping_envelope_conductance_w_k: float = 7.0
    attic_envelope_conductance_w_k: float = 45.2
    # User-1 has an open kitchen/living door, closed unsealed sleeping-room
    # doors, and a closed trap door.  These are phase-specific effective heat
    # exchange values, not pressure-network airflow claims.
    ground_kitchen_exchange_w_k: float = 200.0
    ground_sleeping_exchange_w_k: float = 45.0
    ground_attic_exchange_w_k: float = 42.8706

    def __post_init__(self) -> None:
        if not 5.0e6 <= self.total_effective_capacity_j_k <= 1.5e8:
            raise ValueError("total_effective_capacity_j_k is outside frozen bounds")
        zone_conductances = self.zone_envelope_conductance_w_k()
        if any(not 1.0 <= value <= 100.0 for value in zone_conductances.values()):
            raise ValueError("a zone envelope conductance is outside frozen bounds")
        if not 60.0 <= sum(zone_conductances.values()) <= 180.0:
            raise ValueError("total envelope conductance is outside frozen bounds")
        for name, value in self.zone_exchange_conductance_w_k().items():
            if not 0.0 <= value <= 2_000.0:
                raise ValueError(
                    f"{name} exchange conductance is outside frozen bounds"
                )

    def zone_envelope_conductance_w_k(self) -> dict[str, float]:
        return {
            "ground_airbody": self.ground_envelope_conductance_w_k,
            "kitchen_airbody": self.kitchen_envelope_conductance_w_k,
            "sleeping_airbody": self.sleeping_envelope_conductance_w_k,
            "attic_airbody": self.attic_envelope_conductance_w_k,
        }

    def zone_exchange_conductance_w_k(self) -> dict[str, float]:
        return {
            "kitchen_airbody": self.ground_kitchen_exchange_w_k,
            "sleeping_airbody": self.ground_sleeping_exchange_w_k,
            "attic_airbody": self.ground_attic_exchange_w_k,
        }


@dataclass(frozen=True)
class Annex71RunResult:
    engine_name: str
    graph_sha256: str
    timestamps: tuple[str, ...]
    measured_temperature_c: dict[str, tuple[float, ...]]
    simulated_temperature_c: dict[str, tuple[float, ...]]
    maximum_abs_thermal_balance_residual_w: float
    fallback_used: bool


def _column_index(reference: str) -> int:
    match = CELL_REFERENCE.fullmatch(reference)
    if match is None:
        raise ValueError(f"invalid Excel cell reference: {reference!r}")
    result = 0
    for character in match.group(1):
        result = result * 26 + ord(character) - ord("A") + 1
    return result - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        payload = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ElementTree.fromstring(payload)
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    return [
        "".join(node.text or "" for node in item.iter(namespace + "t"))
        for item in root.findall(namespace + "si")
    ]


def read_first_worksheet(path: Path) -> list[dict[str, str | float | None]]:
    """Read the first worksheet without making Excel a runtime dependency."""

    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(path) as archive:
        shared_strings = _shared_strings(archive)
        rows: list[list[str | float | None]] = []
        with archive.open("xl/worksheets/sheet1.xml") as worksheet:
            for _event, element in ElementTree.iterparse(worksheet, events=("end",)):
                if element.tag != namespace + "row":
                    continue
                values: dict[int, str | float | None] = {}
                for cell in element.findall(namespace + "c"):
                    reference = cell.attrib.get("r")
                    if reference is None:
                        continue
                    raw_node = cell.find(namespace + "v")
                    raw = None if raw_node is None else raw_node.text
                    if raw is None:
                        value: str | float | None = None
                    elif cell.attrib.get("t") == "s":
                        value = shared_strings[int(raw)]
                    else:
                        try:
                            value = float(raw)
                        except ValueError:
                            value = raw
                    values[_column_index(reference)] = value
                if values:
                    row = [None] * (max(values) + 1)
                    for index, value in values.items():
                        row[index] = value
                    rows.append(row)
                element.clear()
    if len(rows) < 2:
        raise ValueError(f"workbook has no data rows: {path}")
    headers = [None if value is None else str(value) for value in rows[0]]
    return [
        {
            header: row[index] if index < len(row) else None
            for index, header in enumerate(headers)
            if header is not None
        }
        for row in rows[1:]
    ]


def _finite(value: str | float | None, field: str) -> float:
    if value is None or value == "NA":
        raise ValueError(f"missing Annex 71 field {field!r}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"non-finite Annex 71 field {field!r}")
    return result


def _optional_finite(value: str | float | None, default: float = 0.0) -> float:
    if value is None or value == "NA":
        return default
    result = float(value)
    return result if math.isfinite(result) else default


def _timestamp(serial: float) -> datetime:
    return (
        datetime(1899, 12, 30, tzinfo=ZoneInfo(TIMEZONE)) + timedelta(days=serial)
    ).replace(microsecond=0)


def _indexed(
    rows: Iterable[Mapping[str, str | float | None]],
) -> dict[float, Mapping[str, str | float | None]]:
    result = {}
    for row in rows:
        value = row.get("DATE")
        if value is not None and value != "NA":
            result[round(float(value), 9)] = row
    return result


def _weighted_room_value(
    rows: Mapping[str, str | float | None],
    rooms: Mapping[str, float],
    fields: Mapping[str, str],
    *,
    allow_missing: bool = False,
    default: float | None = None,
) -> float:
    values: list[tuple[float, float]] = []
    for room, area in rooms.items():
        field = fields[room]
        raw = rows.get(field)
        if raw is None or raw == "NA":
            if allow_missing:
                continue
            raise ValueError(f"missing required Annex 71 field {field!r}")
        values.append((float(raw), area))
    if not values:
        if default is not None:
            return default
        raise ValueError("weighted room aggregation has no values")
    return sum(value * weight for value, weight in values) / sum(
        weight for _value, weight in values
    )


def _sum_room_values(
    rows: Mapping[str, str | float | None],
    rooms: Mapping[str, float],
    fields: Mapping[str, str],
) -> float:
    return sum(_optional_finite(rows.get(fields[room])) for room in rooms)


def _zone_observations(
    full1: Mapping[str, str | float | None],
    full2: Mapping[str, str | float | None],
    *,
    outdoor_relative_humidity_fraction: float,
) -> tuple[Annex71ZoneObservation, ...]:
    observations = []
    for zone_id, rooms in ZONE_ROOM_AREAS_M2.items():
        temperature = _weighted_room_value(full1, rooms, ROOM_TEMPERATURE_FIELD)
        humidity_fields = {room: f"n2_aroom_{room}_110_rH" for room in rooms}
        humidity_percent = _weighted_room_value(
            full2,
            rooms,
            humidity_fields,
            allow_missing=True,
            default=outdoor_relative_humidity_fraction * 100.0,
        )
        heating = _sum_room_values(full1, rooms, ROOM_HEATING_FIELD)
        internal = _sum_room_values(full1, rooms, ROOM_INTERNAL_GAIN_FIELD)
        if zone_id == "ground_airbody":
            flow_m3_h = _optional_finite(full1.get("n2_Vent_living_SUA_VFR"))
            supply_temperature = _optional_finite(
                full1.get("n2_Vent_living_SUA_AT"), temperature
            )
        elif zone_id == "attic_airbody":
            child_flows = [
                _optional_finite(full1.get(f"n2_Vent_{room}_SUA_VFR"))
                for room in ("child1", "child2")
            ]
            flow_m3_h = sum(child_flows)
            if flow_m3_h > 0.0:
                supply_temperature = (
                    sum(
                        flow
                        * _optional_finite(
                            full1.get(f"n2_Vent_{room}_SUA_AT"), temperature
                        )
                        for room, flow in zip(
                            ("child1", "child2"), child_flows, strict=True
                        )
                    )
                    / flow_m3_h
                )
            else:
                supply_temperature = temperature
        else:
            flow_m3_h = 0.0
            supply_temperature = temperature
        observations.append(
            Annex71ZoneObservation(
                zone_id=zone_id,
                air_temperature_c=temperature,
                relative_humidity_fraction=min(max(humidity_percent / 100.0, 0.0), 1.0),
                heating_power_w=max(0.0, heating),
                internal_gain_w=max(0.0, internal),
                ventilation_supply_temperature_c=supply_temperature,
                ventilation_supply_flow_m3_s=max(0.0, flow_m3_h) / 3600.0,
            )
        )
    return tuple(sorted(observations, key=lambda item: item.zone_id))


def load_annex71_intervals(raw_directory: Path) -> tuple[Annex71Interval, ...]:
    """Join the official N2 and weather workbooks by their Excel timestamps."""

    full1_path = (
        raw_directory / "Experiment1 - open" / "Twin_house_N2_exp1_full1_60min.xlsx"
    )
    full2_path = (
        raw_directory / "Experiment1 - open" / "Twin_house_N2_exp1_full2_60min.xlsx"
    )
    weather_path = (
        raw_directory
        / "Weather Data"
        / "Twin_house_weather_exp1_60min_compensated.xlsx"
    )
    for path in (full1_path, full2_path, weather_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    full1 = read_first_worksheet(full1_path)
    full2 = _indexed(read_first_worksheet(full2_path))
    weather = _indexed(read_first_worksheet(weather_path))
    result = []
    for row in full1:
        serial = _finite(row.get("DATE"), "DATE")
        key = round(serial, 9)
        if key not in full2 or key not in weather:
            raise ValueError(
                f"Annex 71 timestamp {serial} is not present in every source"
            )
        weather_row = weather[key]
        pressure_hpa = _finite(
            weather_row.get("Pressure_Atmosphere"), "Pressure_Atmosphere"
        )
        outdoor_rh_fraction = min(
            max(
                _finite(weather_row.get("RelativeHumidity"), "RelativeHumidity")
                / 100.0,
                0.0,
            ),
            1.0,
        )
        result.append(
            Annex71Interval(
                timestamp=_timestamp(serial),
                outdoor_temperature_c=_finite(
                    weather_row.get("AmbientAirTemperature"), "AmbientAirTemperature"
                ),
                relative_humidity_fraction=outdoor_rh_fraction,
                atmospheric_pressure_pa=pressure_hpa * 100.0,
                outdoor_co2_ppm=max(0.0, _finite(weather_row.get("CO2"), "CO2")),
                wind_speed_m_s=max(
                    0.0, _finite(weather_row.get("WindSpeed"), "WindSpeed")
                ),
                wind_direction_deg=_finite(
                    weather_row.get("WindDirection"), "WindDirection"
                )
                % 360.0,
                diffuse_horizontal_radiation_w_m2=max(
                    0.0,
                    _finite(weather_row.get("Radiation_Diffuse"), "Radiation_Diffuse"),
                ),
                global_horizontal_radiation_w_m2=max(
                    0.0,
                    _finite(weather_row.get("Radiation_Global"), "Radiation_Global"),
                ),
                rain=_optional_finite(weather_row.get("Rain_Normal")) > 0.0,
                zones=_zone_observations(
                    row,
                    full2[key],
                    outdoor_relative_humidity_fraction=outdoor_rh_fraction,
                ),
            )
        )
    for previous, current in pairwise(result):
        if current.timestamp - previous.timestamp != timedelta(hours=1):
            raise ValueError("Annex 71 hourly series is not contiguous")
    return tuple(result)


def select_interval(
    records: Sequence[Annex71Interval],
    *,
    start: datetime,
    end_exclusive: datetime,
) -> tuple[Annex71Interval, ...]:
    selected = tuple(
        item for item in records if start <= item.timestamp < end_exclusive
    )
    if not selected:
        raise ValueError("selected Annex 71 interval is empty")
    if (
        selected[0].timestamp != start
        or selected[-1].timestamp + timedelta(hours=1) != end_exclusive
    ):
        raise ValueError(
            "selected Annex 71 interval does not exactly cover requested bounds"
        )
    return selected


def allocate_envelope_conductance_from_coheat(
    records: Sequence[Annex71Interval],
    *,
    whole_house_conductance_w_k: float = 107.0,
    maximum_radiation_w_m2: float = 5.0,
    maximum_temperature_change_c: float = 0.1,
) -> dict[str, float]:
    """Allocate the published whole-house HTC using stable coheat intervals.

    The coheating result identifies only a whole-building coefficient.  This
    deterministic allocation uses low-solar, near-steady observations solely
    to distribute that independently published total across the four official
    air bodies.  It does not infer a new whole-building HTC.
    """

    if len(records) < 2:
        raise ValueError("coheat allocation requires at least two observations")
    if whole_house_conductance_w_k <= 0.0:
        raise ValueError("whole_house_conductance_w_k must be positive")
    candidates: dict[str, list[float]] = {zone_id: [] for zone_id in ZONE_VOLUMES_M3}
    for previous, current in pairwise(records):
        if current.global_horizontal_radiation_w_m2 > maximum_radiation_w_m2:
            continue
        for zone_id, values in candidates.items():
            observation = current.zone(zone_id)
            previous_observation = previous.zone(zone_id)
            temperature_difference = (
                observation.air_temperature_c - current.outdoor_temperature_c
            )
            if (
                temperature_difference <= 10.0
                or abs(
                    observation.air_temperature_c
                    - previous_observation.air_temperature_c
                )
                > maximum_temperature_change_c
            ):
                continue
            heat_input_w = observation.heating_power_w + observation.internal_gain_w
            values.append(heat_input_w / temperature_difference)
    medians = {}
    for zone_id, values in candidates.items():
        if len(values) < 12:
            raise ValueError(
                f"insufficient stable coheat observations for {zone_id}: {len(values)}"
            )
        medians[zone_id] = float(np.median(values))
    raw_total = sum(medians.values())
    if raw_total <= 0.0:
        raise ValueError("coheat allocation produced no positive conductance")
    return {
        zone_id: whole_house_conductance_w_k * value / raw_total
        for zone_id, value in medians.items()
    }


def _surface(
    zone_id: str,
    surface_id: str,
    *,
    area_m2: float,
    u_value: float,
    capacity_j_k: float,
    azimuth_deg: float,
    adjacent_zone_id: str | None = None,
    paired_surface_id: str | None = None,
    openings: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "scenario_id": SCENARIO_ID,
        "building_id": BUILDING_ID,
        "dwelling_id": DWELLING_ID,
        "zone_id": zone_id,
        "surface_id": surface_id,
        "boundary_type": "interzone" if adjacent_zone_id else "exterior",
        "adjacent_zone_id": adjacent_zone_id,
        "paired_surface_id": paired_surface_id,
        "area_m2": area_m2,
        "thermal_transmittance_w_m2_k": u_value,
        "heat_capacity_j_k": capacity_j_k,
        "azimuth_deg": azimuth_deg,
        "tilt_deg": 90.0,
        "openings": list(openings),
    }


def _opening(zone_id: str, surface_id: str, name: str, area: float) -> dict[str, Any]:
    return {
        "scenario_id": SCENARIO_ID,
        "building_id": BUILDING_ID,
        "dwelling_id": DWELLING_ID,
        "zone_id": zone_id,
        "surface_id": surface_id,
        "opening_id": f"window_{name}",
        "opening_type": "window",
        "boundary_type": "exterior",
        "adjacent_zone_id": None,
        "area_m2": area,
        "openable_area_m2": 0.0,
        "thermal_transmittance_w_m2_k": 1.20,
        "solar_transmittance_fraction": 0.543,
        "visible_transmittance_fraction": 0.803,
    }


def _zone_surfaces(
    zone_id: str,
    parameters: Annex71ModelParameters,
) -> list[dict[str, Any]]:
    total_volume = sum(ZONE_VOLUMES_M3.values())
    zone_fraction = ZONE_VOLUMES_M3[zone_id] / total_volume
    target_envelope_ua = parameters.zone_envelope_conductance_w_k()[zone_id]
    windows = WINDOWS[zone_id]
    window_ua = sum(area * 1.20 for _name, area, _azimuth in windows)
    opaque_ua = target_envelope_ua - window_ua
    if opaque_ua <= 0.0:
        raise ValueError(
            f"envelope conductance cannot accommodate published windows for {zone_id}"
        )
    orientations = sorted({azimuth for _name, _area, azimuth in windows})
    capacity_share = parameters.total_effective_capacity_j_k * zone_fraction
    result = []
    for azimuth in orientations:
        oriented_windows = [item for item in windows if item[2] == azimuth]
        surface_id = f"{zone_id}_exterior_{int(azimuth)}"
        opaque_area = opaque_ua / len(orientations) / 0.24
        opening_area = sum(area for _name, area, _direction in oriented_windows)
        opening_name = f"{zone_id}_{int(azimuth)}_aggregate"
        openings = [_opening(zone_id, surface_id, opening_name, opening_area)]
        result.append(
            _surface(
                zone_id,
                surface_id,
                area_m2=opaque_area + sum(item["area_m2"] for item in openings),
                u_value=0.24,
                capacity_j_k=capacity_share / len(orientations),
                azimuth_deg=azimuth,
                openings=openings,
            )
        )
    if zone_id != "ground_airbody":
        pair_area = INTERZONE_AREAS_M2[zone_id]
        pair_u = parameters.zone_exchange_conductance_w_k()[zone_id] / pair_area
        result.append(
            _surface(
                zone_id,
                f"{zone_id}_to_ground",
                area_m2=pair_area,
                u_value=pair_u,
                capacity_j_k=0.0,
                azimuth_deg=0.0,
                adjacent_zone_id="ground_airbody",
                paired_surface_id=f"ground_to_{zone_id}",
            )
        )
    else:
        for other in ("attic_airbody", "kitchen_airbody", "sleeping_airbody"):
            pair_area = INTERZONE_AREAS_M2[other]
            pair_u = parameters.zone_exchange_conductance_w_k()[other] / pair_area
            result.append(
                _surface(
                    zone_id,
                    f"ground_to_{other}",
                    area_m2=pair_area,
                    u_value=pair_u,
                    capacity_j_k=0.0,
                    azimuth_deg=180.0,
                    adjacent_zone_id=other,
                    paired_surface_id=f"{other}_to_ground",
                )
            )
    return result


def _zone_systems(
    zone_id: str, maximum_heating_w: float, maximum_ventilation_m3_s: float
) -> list[dict[str, Any]]:
    identity = {
        "scenario_id": SCENARIO_ID,
        "building_id": BUILDING_ID,
        "dwelling_id": DWELLING_ID,
        "zone_id": zone_id,
    }
    return [
        {
            **identity,
            "system_id": f"{zone_id}_heating",
            "system_type": "heating",
            "max_heating_power_w": maximum_heating_w,
            "heating_efficiency_fraction": 1.0,
            "heating_setpoint_c": 21.0,
        },
        {
            **identity,
            "system_id": f"{zone_id}_cooling",
            "system_type": "cooling",
            "max_cooling_power_w": 0.0,
            "cooling_cop": 1.0,
            "cooling_setpoint_c": 30.0,
        },
        {
            **identity,
            "system_id": f"{zone_id}_ventilation",
            "system_type": "ventilation",
            "max_ventilation_volume_flow_m3_s": maximum_ventilation_m3_s,
        },
        {
            **identity,
            "system_id": f"{zone_id}_lighting",
            "system_type": "lighting",
            "max_lighting_power_w": 0.0,
        },
    ]


def _weather_state(
    record: Annex71Interval,
    timestep_index: int,
    *,
    canonical_interval_start: datetime | None = None,
) -> dict[str, Any]:
    # The selected alignment maps row T to (T - 1 hour, T]. This matches the
    # published experiment start and the observed forcing/state lag, while the
    # canonical contract timestamps the start. Treat this as a documented
    # preprocessing decision, not an independently proven workbook convention.
    timestamp = canonical_interval_start or record.timestamp - timedelta(hours=1)
    position = calculate_solar_position(
        timestamp,
        latitude_deg=47.874,
        longitude_deg=11.728,
        elevation_m=680.0,
        atmospheric_pressure_pa=record.atmospheric_pressure_pa,
        outdoor_temperature_c=record.outdoor_temperature_c,
    )
    cosine = max(0.0, math.cos(math.radians(position.zenith_deg)))
    direct_horizontal = max(
        0.0,
        record.global_horizontal_radiation_w_m2
        - record.diffuse_horizontal_radiation_w_m2,
    )
    direct_normal = min(2000.0, direct_horizontal / cosine) if cosine > 0.01 else 0.0
    return {
        "scenario_id": SCENARIO_ID,
        "timestep_index": timestep_index,
        "timestamp": timestamp,
        "outdoor_temperature_c": record.outdoor_temperature_c,
        "sky_temperature_c": record.outdoor_temperature_c,
        "relative_humidity_fraction": record.relative_humidity_fraction,
        "atmospheric_pressure_pa": record.atmospheric_pressure_pa,
        "outdoor_co2_ppm": record.outdoor_co2_ppm,
        "wind_speed_m_s": record.wind_speed_m_s,
        "wind_direction_deg": record.wind_direction_deg,
        "direct_normal_radiation_w_m2": direct_normal,
        "diffuse_horizontal_radiation_w_m2": record.diffuse_horizontal_radiation_w_m2,
        "global_horizontal_radiation_w_m2": record.global_horizontal_radiation_w_m2,
        "outdoor_illuminance_lux": 0.0,
        "rain": record.rain,
    }


def build_canonical_scenario(
    records: Sequence[Annex71Interval],
    parameters: Annex71ModelParameters | None = None,
    *,
    initial_record: Annex71Interval | None = None,
) -> tuple[CanonicalScenario, dict[str, object]]:
    """Build and compile the traceable four-air-body canonical scenario."""

    if not records:
        raise ValueError("records cannot be empty")
    parameters = parameters or Annex71ModelParameters()
    maximum_heating = {
        zone_id: max(item.zone(zone_id).heating_power_w for item in records) + 1.0
        for zone_id in ZONE_VOLUMES_M3
    }
    maximum_ventilation = {
        zone_id: max(
            item.zone(zone_id).ventilation_supply_flow_m3_s for item in records
        )
        + 1.0e-6
        for zone_id in ZONE_VOLUMES_M3
    }
    first = initial_record or records[0]
    canonical_start = records[0].timestamp - timedelta(hours=1)
    zones = []
    for zone_id, volume_m3 in ZONE_VOLUMES_M3.items():
        observation = first.zone(zone_id)
        zones.append(
            {
                "scenario_id": SCENARIO_ID,
                "building_id": BUILDING_ID,
                "dwelling_id": DWELLING_ID,
                "zone_id": zone_id,
                "zone_type": ZONE_TYPES[zone_id],
                "floor_area_m2": sum(ZONE_ROOM_AREAS_M2[zone_id].values()),
                "volume_m3": volume_m3,
                "height_m": volume_m3 / sum(ZONE_ROOM_AREAS_M2[zone_id].values()),
                "initial_air_temperature_c": observation.air_temperature_c,
                "initial_mean_radiant_temperature_c": observation.air_temperature_c,
                "initial_relative_humidity_fraction": observation.relative_humidity_fraction,
                "initial_co2_ppm": first.outdoor_co2_ppm,
                "surfaces": _zone_surfaces(zone_id, parameters),
                "systems": _zone_systems(
                    zone_id, maximum_heating[zone_id], maximum_ventilation[zone_id]
                ),
            }
        )
    end = len(records)
    occupant_identity = {
        "scenario_id": SCENARIO_ID,
        "building_id": BUILDING_ID,
        "dwelling_id": DWELLING_ID,
        "home_zone_id": "ground_airbody",
        "sleep_zone_id": "sleeping_airbody",
        "sensible_heat_gain_w": 0.0,
        "co2_generation_kg_s": 0.0,
        "moisture_generation_kg_s": 0.0,
        "location_schedule": [
            {
                "start_timestep_index": 0,
                "end_timestep_index": end,
                "zone_id": "ground_airbody",
                "activity": "away",
            }
        ],
    }
    payload = {
        "schema_version": "1.0.0",
        "use_case": "multizone_dwelling_v1",
        "scenario_id": SCENARIO_ID,
        "metadata": {
            "name": "IEA EBC Annex 71 N2 four-air-body production study",
            "description": "Official geometry aggregation and measured forcing mapped to the canonical object engine.",
            "scenario_kind": "validated",
            "tags": [
                "annex71",
                "empirical-validation-alternative",
                "production-adapter",
            ],
        },
        "site": {
            "latitude_deg": 47.874,
            "longitude_deg": 11.728,
            "elevation_m": 680.0,
            "ground_albedo_fraction": 0.2,
        },
        "deterministic_seed": 710002,
        "simulation_period": {
            "start_datetime": canonical_start,
            "timezone": TIMEZONE,
            "n_timesteps": end,
            "dt_minutes": DT_MINUTES,
        },
        "geometry_configuration": {
            "geometry_tier": "thermal_topology_v1",
            "enabled_features": ["airflow", "solar_gains"],
            "orientation_convention": "azimuth_clockwise_from_true_north_tilt_from_horizontal",
            "optional_geometry_affects_physics": False,
            "defaults_applied": [],
            "derived_values": [
                {
                    "target_path": "/building/dwelling/zones",
                    "method": "derived",
                    "source_paths": ["/annex71/air_body_definition"],
                    "rule": "room measurements aggregated by published floor area into four official air bodies",
                },
                {
                    "target_path": "/building/dwelling/zones/*/surfaces",
                    "method": "derived",
                    "source_paths": [
                        "/annex71/coheating_htc",
                        "/annex71/window_schedule",
                    ],
                    "rule": "measured whole-house HTC allocated by air-body volume after explicit window UA",
                },
            ],
        },
        "building": {
            "scenario_id": SCENARIO_ID,
            "building_id": BUILDING_ID,
            "floor_area_m2": 165.75,
            "volume_m3": 364.15,
            "height_m": 5.2,
            "n_floors": 2,
            "dwelling": {
                "scenario_id": SCENARIO_ID,
                "building_id": BUILDING_ID,
                "dwelling_id": DWELLING_ID,
                "floor_area_m2": 165.75,
                "volume_m3": 364.15,
                "zones": zones,
            },
        },
        "occupants": [
            {**occupant_identity, "occupant_id": "measurement_placeholder_1"},
            {**occupant_identity, "occupant_id": "measurement_placeholder_2"},
        ],
        "weather_source": {
            "source_type": "inline",
            "path": None,
            "interpolation": "none",
            "allowable_derived_fields": ["timestamp"],
            "synthetic_profile": None,
        },
        "weather_series": [
            _weather_state(
                record,
                index,
                canonical_interval_start=canonical_start + timedelta(hours=index),
            )
            for index, record in enumerate(records)
        ],
        "output_configuration": {
            "enabled": False,
            "directory": "artifacts/validation/annex71",
            "formats": ["json"],
            "include_interval_timestamps": True,
            "include_debug_graph": False,
            "fields": [],
        },
    }
    scenario = ScenarioV1.model_validate(payload)
    graph = compile_physics_graph(scenario.model_dump(mode="json"))
    return scenario, graph


def _step_input(
    scenario: CanonicalScenario,
    graph: Mapping[str, object],
    record: Annex71Interval,
    index: int,
    prior: tuple[PriorZonePhysicalState, ...],
) -> SimulationStepInput:
    commands = []
    gains = []
    for zone in scenario.building.dwelling.zones:
        observation = record.zone(zone.zone_id)
        heating_system = next(
            item for item in zone.systems if item.system_type == "heating"
        )
        maximum_heating = float(heating_system.max_heating_power_w or 0.0)
        heating_fraction = (
            observation.heating_power_w / maximum_heating if maximum_heating else 0.0
        )
        commands.append(
            ZoneControlCommand(
                zone_id=zone.zone_id,
                heating_on=observation.heating_power_w > 0.0,
                heating_power_fraction=heating_fraction,
                cooling_on=False,
                cooling_power_fraction=0.0,
                ventilation_volume_flow_m3_s=observation.ventilation_supply_flow_m3_s,
                lights_on=False,
                lighting_power_w=0.0,
                window_opening_fraction=0.0,
                shading_open_fraction=1.0,
            )
        )
        gains.append(
            InternalGain(
                source_id=f"measured_internal_{zone.zone_id}",
                source_kind="other",
                zone_id=zone.zone_id,
                sensible_heat_w=observation.internal_gain_w,
                latent_heat_w=0.0,
                electrical_power_w=observation.internal_gain_w,
                co2_generation_kg_s=0.0,
                moisture_generation_kg_s=0.0,
            )
        )
        # The production ventilation kernel uses outdoor temperature.  This
        # explicit correction makes H*(Tout-Tzone)+H*(Tsupply-Tout) equal the
        # measured-supply expression H*(Tsupply-Tzone).
        ventilation_correction_w = (
            AIR_DENSITY_KG_M3
            * AIR_HEAT_CAPACITY_J_KG_K
            * observation.ventilation_supply_flow_m3_s
            * (
                observation.ventilation_supply_temperature_c
                - record.outdoor_temperature_c
            )
        )
        gains.append(
            InternalGain(
                source_id=f"ventilation_supply_correction_{zone.zone_id}",
                source_kind="other",
                zone_id=zone.zone_id,
                sensible_heat_w=ventilation_correction_w,
                latent_heat_w=0.0,
                electrical_power_w=0.0,
                co2_generation_kg_s=0.0,
                moisture_generation_kg_s=0.0,
            )
        )
    return SimulationStepInput(
        scenario_id=scenario.scenario_id,
        timestep_index=index,
        timestamp=scenario.weather_series[index].timestamp,
        dt_minutes=DT_MINUTES,
        weather=scenario.weather_series[index],
        prior_zone_states=prior,
        occupant_states=tuple(
            OccupantStepState(
                occupant_id=occupant.occupant_id,
                dwelling_id=occupant.dwelling_id,
                zone_id="ground_airbody",
                activity="away",
                is_present=False,
            )
            for occupant in scenario.occupants
        ),
        action_events=(),
        internal_gains=tuple(gains),
        control_commands=tuple(commands),
        system_availability=tuple(
            SystemAvailability(
                system_id=system.system_id, available=True, capacity_fraction=1.0
            )
            for zone in scenario.building.dwelling.zones
            for system in zone.systems
        ),
        graph=CanonicalGraphReference(
            scenario_id=scenario.scenario_id,
            compiled_graph_version=str(graph["compiled_graph_version"]),
            graph_sha256=str(graph["graph_sha256"]),
        ),
        run_context=DeterministicRunContext(
            run_id="annex71_production_transfer",
            deterministic_seed=scenario.deterministic_seed,
            random_stream_position=index,
            timezone=TIMEZONE,
        ),
    )


def run_object_scenario(
    records: Sequence[Annex71Interval],
    parameters: Annex71ModelParameters | None = None,
) -> Annex71RunResult:
    """Execute all intervals through the canonical object-engine adapter."""

    if len(records) < 2:
        raise ValueError("at least two observations are required for interval scoring")
    parameters = parameters or Annex71ModelParameters()
    # Row T contains the mean forcing over (T-1h, T] and the measured state at
    # T.  Seed the model from the preceding observation, then use rows 1..N as
    # both forcing records and end-of-interval targets.
    initial_record = records[0]
    forcing_records = records[1:]
    target_records = records[1:]
    scenario, graph = build_canonical_scenario(
        forcing_records,
        parameters,
        initial_record=initial_record,
    )
    adapter = ObjectEngineAdapter(scenario, graph)
    prior = tuple(
        PriorZonePhysicalState(
            zone_id=zone.zone_id,
            air_temperature_c=zone.initial_air_temperature_c,
            mean_radiant_temperature_c=zone.initial_mean_radiant_temperature_c,
            relative_humidity_fraction=zone.initial_relative_humidity_fraction,
            co2_ppm=zone.initial_co2_ppm,
        )
        for zone in scenario.building.dwelling.zones
    )
    measured = {zone_id: [] for zone_id in ZONE_VOLUMES_M3}
    simulated = {zone_id: [] for zone_id in ZONE_VOLUMES_M3}
    residuals = []
    fallback_used = False
    for index, (record, target) in enumerate(
        zip(forcing_records, target_records, strict=True)
    ):
        step = _step_input(scenario, graph, record, index, prior)
        result = adapter.run_step(step, include_debug=True)
        for zone_result in result.zones:
            measured[zone_result.zone_id].append(
                target.zone(zone_result.zone_id).air_temperature_c
            )
            simulated[zone_result.zone_id].append(zone_result.air_temperature_c)
            fallback_used = fallback_used or zone_result.fallback_used
        assert result.debug is not None
        fields = result.debug.engine_fields
        residuals.append(
            abs(float(fields["conservation_residuals"]["thermal_balance_residual_w"]))
        )
        prior = tuple(
            PriorZonePhysicalState.model_validate(item)
            for item in fields["next_prior_zone_states"]
        )
    return Annex71RunResult(
        engine_name="object",
        graph_sha256=str(graph["graph_sha256"]),
        timestamps=tuple(item.timestamp.isoformat() for item in target_records),
        measured_temperature_c={key: tuple(value) for key, value in measured.items()},
        simulated_temperature_c={key: tuple(value) for key, value in simulated.items()},
        maximum_abs_thermal_balance_residual_w=max(residuals, default=0.0),
        fallback_used=fallback_used,
    )


def temperature_metrics(
    result: Annex71RunResult,
    *,
    warmup_timesteps: int = 24,
) -> dict[str, Any]:
    """Report zone and pooled temperature errors after a frozen warm-up."""

    if warmup_timesteps < 0 or warmup_timesteps >= len(result.timestamps):
        raise ValueError("warmup_timesteps must leave at least one scored interval")
    by_zone: dict[str, dict[str, float | int]] = {}
    pooled_residuals = []
    for zone_id in sorted(result.measured_temperature_c):
        measured = np.asarray(result.measured_temperature_c[zone_id][warmup_timesteps:])
        simulated = np.asarray(
            result.simulated_temperature_c[zone_id][warmup_timesteps:]
        )
        residual = simulated - measured
        pooled_residuals.append(residual)
        by_zone[zone_id] = {
            "count": int(residual.size),
            "bias_c": float(np.mean(residual)),
            "mae_c": float(np.mean(np.abs(residual))),
            "rmse_c": float(np.sqrt(np.mean(np.square(residual)))),
            "maximum_abs_error_c": float(np.max(np.abs(residual))),
            "correlation": float(np.corrcoef(measured, simulated)[0, 1]),
        }
    pooled = np.concatenate(pooled_residuals)
    return {
        "warmup_timesteps": warmup_timesteps,
        "by_zone": by_zone,
        "pooled": {
            "count": int(pooled.size),
            "bias_c": float(np.mean(pooled)),
            "mae_c": float(np.mean(np.abs(pooled))),
            "rmse_c": float(np.sqrt(np.mean(np.square(pooled)))),
            "maximum_abs_error_c": float(np.max(np.abs(pooled))),
        },
    }


def parameters_as_dict(parameters: Annex71ModelParameters) -> dict[str, float]:
    return {key: float(value) for key, value in asdict(parameters).items()}


__all__ = [
    "Annex71Interval",
    "Annex71ModelParameters",
    "Annex71RunResult",
    "Annex71ZoneObservation",
    "allocate_envelope_conductance_from_coheat",
    "build_canonical_scenario",
    "load_annex71_intervals",
    "parameters_as_dict",
    "run_object_scenario",
    "select_interval",
    "temperature_metrics",
]
