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
from typing import Any, Literal
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
    ExternalBoundaryState,
    InternalGain,
    InterzoneOpeningControl,
    OccupantStepState,
    OpeningControlCommand,
    PriorZonePhysicalState,
    SimulationStepInput,
    SystemAvailability,
    ZoneControlCommand,
)

SCENARIO_ID = "annex71_n2_four_airbody"
BUILDING_ID = "annex71_n2"
DWELLING_ID = "annex71_n2_dwelling"
# The source Excel serials include 02:00--02:50 on the 2019 spring DST
# transition.  They therefore use fixed Central European Time, not local civil
# Europe/Berlin time.  Etc/GMT-1 is the IANA fixed-offset UTC+1 zone (the POSIX
# sign is intentionally reversed).
TIMEZONE = "Etc/GMT-1"
DT_MINUTES = 60.0
AIR_DENSITY_KG_M3 = 1.204
AIR_HEAT_CAPACITY_J_KG_K = 1005.0
HEATER_CONVECTIVE_FRACTION = 0.70
STEFAN_BOLTZMANN_W_M2_K4 = 5.670374419e-8
EXTERIOR_SOLAR_ABSORPTANCE_FRACTION = 0.23
EXTERIOR_LONGWAVE_EMISSIVITY_FRACTION = 0.90
EXTERIOR_SURFACE_HEAT_TRANSFER_COEFFICIENT_W_M2_K = 25.0

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
OPENING_TILT_DEG = {"south_child1_roof_type4": 30.0}

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
    ventilation_exhaust_flow_m3_s: float


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
    downwelling_longwave_radiation_w_m2: float | None
    north_vertical_radiation_w_m2: float | None
    east_vertical_radiation_w_m2: float | None
    south_vertical_radiation_w_m2: float | None
    west_vertical_radiation_w_m2: float | None
    rain: bool
    zones: tuple[Annex71ZoneObservation, ...]
    cellar_temperature_c: float = 10.0
    child1_window_opening_fraction: float = 0.0
    kitchen_door_opening_fraction: float = 1.0
    attic_door_opening_fraction: float = 1.0
    missing_source_fields: tuple[str, ...] = ()
    source_quality_flags: tuple[str, ...] = ()
    shading_open_fraction_by_opening: tuple[tuple[str, float], ...] = (
        ("window_west_living_type1", 0.0),
        ("window_west_kitchen_type1", 0.0),
    )

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
        value = _date_value(row)
        if value is not None and value != "NA":
            result[round(float(value), 9)] = row
    return result


def _date_value(
    row: Mapping[str, str | float | None],
) -> str | float | None:
    """Read the documented timestamp column used by either source archive."""

    for field in ("DATE", "as.character(index(datn2))"):
        if field in row:
            return row.get(field)
    raise ValueError("Annex 71 workbook has no recognized timestamp column")


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
            exhaust_flow_m3_h = sum(
                _optional_finite(full1.get(f"n2_Vent_{room}_EHA_VFR"))
                for room in ("bath", "dining")
            )
            supply_temperature = _optional_finite(
                full1.get("n2_Vent_living_SUA_AT"), temperature
            )
        elif zone_id == "attic_airbody":
            child_flows = [
                _optional_finite(full1.get(f"n2_Vent_{room}_SUA_VFR"))
                for room in ("child1", "child2")
            ]
            flow_m3_h = sum(child_flows)
            exhaust_flow_m3_h = sum(
                _optional_finite(full1.get(f"n2_Vent_{room}_EHA_VFR"))
                for room in ("child1", "child2")
            )
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
            exhaust_flow_m3_h = 0.0
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
                ventilation_exhaust_flow_m3_s=(
                    max(0.0, exhaust_flow_m3_h) / 3600.0
                ),
            )
        )
    return tuple(sorted(observations, key=lambda item: item.zone_id))


def load_annex71_intervals(
    raw_directory: Path,
    *,
    resolution_minutes: int = 60,
    experiment: Literal["main", "extended"] = "main",
    missing_outdoor_co2_policy: Literal[
        "error", "carry_forward_for_thermal_diagnostic"
    ] = "error",
    drop_duplicate_timestamps_before: datetime | None = None,
) -> tuple[Annex71Interval, ...]:
    """Join official N2 and weather workbooks by their source timestamps."""

    if resolution_minutes not in {10, 60}:
        raise ValueError("resolution_minutes must be 10 or 60")
    resolution = f"{resolution_minutes}min"
    if experiment == "main":
        open_directory = raw_directory / "Experiment1 - open"
        prefix = "exp1"
        weather_suffix = "xlsx"
    else:
        open_directory = raw_directory / "Experiment2 - open"
        prefix = "exp2"
        weather_suffix = "xlsm"
    full1_path = open_directory / f"Twin_house_N2_{prefix}_full1_{resolution}.xlsx"
    full2_path = open_directory / f"Twin_house_N2_{prefix}_full2_{resolution}.xlsx"
    weather_path = (
        raw_directory
        / "Weather Data"
        / f"Twin_house_weather_{prefix}_{resolution}_compensated.{weather_suffix}"
    )
    for path in (full1_path, full2_path, weather_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    full1 = read_first_worksheet(full1_path)
    full2 = _indexed(read_first_worksheet(full2_path))
    weather = _indexed(read_first_worksheet(weather_path))
    result = []
    last_outdoor_co2_ppm: float | None = None
    for row in full1:
        serial = _finite(_date_value(row), "DATE")
        timestamp = _timestamp(serial)
        source_quality_flags: tuple[str, ...] = ()
        if result and result[-1].timestamp == timestamp:
            if (
                drop_duplicate_timestamps_before is None
                or timestamp >= drop_duplicate_timestamps_before
            ):
                raise ValueError(
                    f"Annex 71 source contains duplicate timestamp {timestamp.isoformat()}"
                )
            result.pop()
            source_quality_flags = (
                "earlier conflicting duplicate source row dropped before scored period",
            )
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
        missing_source_fields: tuple[str, ...] = ()
        try:
            outdoor_co2_ppm = max(
                0.0, _finite(weather_row.get("CO2"), "CO2")
            )
        except (TypeError, ValueError):
            if (
                missing_outdoor_co2_policy != "carry_forward_for_thermal_diagnostic"
                or last_outdoor_co2_ppm is None
            ):
                raise
            outdoor_co2_ppm = last_outdoor_co2_ppm
            missing_source_fields = ("weather.CO2",)
        last_outdoor_co2_ppm = outdoor_co2_ppm
        result.append(
            Annex71Interval(
                timestamp=timestamp,
                outdoor_temperature_c=_finite(
                    weather_row.get("AmbientAirTemperature"), "AmbientAirTemperature"
                ),
                relative_humidity_fraction=outdoor_rh_fraction,
                atmospheric_pressure_pa=pressure_hpa * 100.0,
                outdoor_co2_ppm=outdoor_co2_ppm,
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
                downwelling_longwave_radiation_w_m2=max(
                    0.0,
                    _finite(
                        weather_row.get("RadiationIR_global"),
                        "RadiationIR_global",
                    ),
                ),
                north_vertical_radiation_w_m2=max(
                    0.0,
                    _finite(weather_row.get("Radiation_North"), "Radiation_North"),
                ),
                east_vertical_radiation_w_m2=max(
                    0.0,
                    _finite(weather_row.get("Radiation_East"), "Radiation_East"),
                ),
                south_vertical_radiation_w_m2=max(
                    0.0,
                    _finite(weather_row.get("Radiation_South"), "Radiation_South"),
                ),
                west_vertical_radiation_w_m2=max(
                    0.0,
                    _finite(weather_row.get("Radiation_West"), "Radiation_West"),
                ),
                rain=_optional_finite(weather_row.get("Rain_Normal")) > 0.0,
                zones=_zone_observations(
                    row,
                    full2[key],
                    outdoor_relative_humidity_fraction=outdoor_rh_fraction,
                ),
                cellar_temperature_c=(
                    _finite(row.get("n2_cellar_285_AT"), "n2_cellar_285_AT")
                    + _finite(row.get("n2_cellar_285_AT2"), "n2_cellar_285_AT2")
                )
                / 2.0,
                child1_window_opening_fraction=min(
                    max(
                        _optional_finite(row.get("n2_aroom_child1_win_pos")),
                        0.0,
                    ),
                    1.0,
                ),
                kitchen_door_opening_fraction=min(
                    max(
                        _optional_finite(
                            row.get("n2_aroom_kitchen_door_pos"), 1.0
                        ),
                        0.0,
                    ),
                    1.0,
                ),
                attic_door_opening_fraction=min(
                    max(
                        _optional_finite(row.get("n2_attic_door_pos"), 1.0),
                        0.0,
                    ),
                    1.0,
                ),
                missing_source_fields=missing_source_fields,
                source_quality_flags=source_quality_flags,
                shading_open_fraction_by_opening=(
                    ("window_west_living_type1", 0.0),
                    ("window_west_kitchen_type1", 0.0),
                ),
            )
        )
    for previous, current in pairwise(result):
        if current.timestamp - previous.timestamp != timedelta(
            minutes=resolution_minutes
        ):
            raise ValueError("Annex 71 series is not contiguous")
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
        or (
            len(selected) > 1
            and selected[-1].timestamp
            + (selected[1].timestamp - selected[0].timestamp)
            != end_exclusive
        )
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
    tilt_deg: float = 90.0,
    adjacent_zone_id: str | None = None,
    paired_surface_id: str | None = None,
    external_boundary_id: str | None = "outdoor_air",
    airflow_opening_area_m2: float = 0.0,
    airflow_open_fraction: float = 0.0,
    airflow_model: str = "none",
    airflow_opening_height_m: float = 0.0,
    airflow_discharge_coefficient: float = 0.0,
    airflow_assumed_velocity_m_s: float = 0.0,
    thermal_bridge_conductance_w_k: float = 0.0,
    exterior_solar_absorptance_fraction: float | None = None,
    exterior_longwave_emissivity_fraction: float | None = None,
    exterior_surface_heat_transfer_coefficient_w_m2_k: float | None = None,
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
        "external_boundary_id": (
            None if adjacent_zone_id is not None else external_boundary_id
        ),
        "area_m2": area_m2,
        "thermal_transmittance_w_m2_k": u_value,
        "thermal_bridge_conductance_w_k": thermal_bridge_conductance_w_k,
        "exterior_solar_absorptance_fraction": exterior_solar_absorptance_fraction,
        "exterior_longwave_emissivity_fraction": exterior_longwave_emissivity_fraction,
        "exterior_surface_heat_transfer_coefficient_w_m2_k": (
            exterior_surface_heat_transfer_coefficient_w_m2_k
        ),
        "heat_capacity_j_k": capacity_j_k,
        "azimuth_deg": azimuth_deg,
        "tilt_deg": tilt_deg,
        "airflow_opening_area_m2": airflow_opening_area_m2,
        "airflow_open_fraction": airflow_open_fraction,
        "airflow_model": airflow_model,
        "airflow_opening_height_m": airflow_opening_height_m,
        "airflow_discharge_coefficient": airflow_discharge_coefficient,
        "airflow_assumed_velocity_m_s": airflow_assumed_velocity_m_s,
        "openings": list(openings),
    }


def _opening(
    zone_id: str,
    surface_id: str,
    name: str,
    area: float,
    *,
    solar_shading_factor: float = 1.0,
    openable_area_m2: float = 0.0,
) -> dict[str, Any]:
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
        "openable_area_m2": openable_area_m2,
        "thermal_transmittance_w_m2_k": 1.20,
        "solar_transmittance_fraction": 0.543,
        "visible_transmittance_fraction": 0.803,
        "solar_shading_factor": solar_shading_factor,
    }


def _legacy_zone_surfaces(
    zone_id: str,
    parameters: Annex71ModelParameters,
    *,
    capacity_allocation_basis: str = "air_volume",
) -> list[dict[str, Any]]:
    zone_fraction = zone_capacity_fractions(capacity_allocation_basis)[zone_id]
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
        oriented_tilts = {
            OPENING_TILT_DEG.get(name, 90.0)
            for name, _area, _direction in oriented_windows
        }
        if len(oriented_tilts) != 1:
            raise ValueError(
                f"openings with different tilts cannot share a surface for {zone_id}"
            )
        surface_tilt = oriented_tilts.pop()
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
                tilt_deg=surface_tilt,
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


# Published construction properties from 01_Constructions_TwinHouses.xlsx.
# Heat capacities are the layer sums d * density * specific heat. They are not
# inferred from the measured temperature residuals.
PUBLISHED_CONSTRUCTIONS: dict[str, tuple[float, float]] = {
    "west_wall": (0.21815746238272007, 308_864.0),
    "east_wall": (0.22219695605625317, 303_712.0),
    "north_south_wall": (0.21450076607416457, 328_920.0),
    "knee_wall": (0.2897535502770171, 820_920.0),
    "floor_to_cellar": (0.2944664091863765, 663_846.4),
    "roof": (0.216, 50_186.0),
    "ceiling": (0.4101385952367645, 577_700.0),
    "internal_partition": (1.20, 200_000.0),
    "front_door": (0.94, 0.0),
}

GROUND_HEIGHT_M = 2.60
GROUND_CEILING_AREA_M2 = 81.69
TRAP_DOOR_AREA_M2 = 0.57 * 1.39
INTERNAL_DOOR_AREA_M2 = 0.935 * 1.95
INTERNAL_DOOR_HEIGHT_M = 1.95
CONTAM_LARGE_OPENING_DISCHARGE_COEFFICIENT = 0.78
ROOF_PLANE_AREA_M2 = 10.24 * (10.296 / 2.0) / math.cos(math.radians(30.0))
ATTIC_GABLE_AREA_M2 = 10.296 * 0.35 + 0.5 * 10.296 * (2.91 - 0.35)
ATTIC_KNEE_AREA_M2 = 10.24 * 0.35
GROUND_EDGE_PSI_W_M_K = {0.0: 0.210, 90.0: 0.214, 180.0: 0.210, 270.0: 0.210}
ROOF_THERMAL_BRIDGE_CONDUCTANCE_W_K = (
    0.006 * 10.24
    + 0.188 * 2.0 * (10.296 / 2.0) / math.cos(math.radians(30.0))
    + 0.186 * 2.0 * (10.296 / 2.0) / math.cos(math.radians(30.0))
    + 0.165 * 2.0 * 10.24
)
CELLAR_THERMAL_BRIDGE_CONDUCTANCE_W_K = (
    0.177 * 10.296 + 0.176 * (10.296 + 2.0 * 10.24) + 4.0 * 0.656
)
GROUND_ATTIC_THERMAL_BRIDGE_CONDUCTANCE_W_K = (
    0.696 * 10.296 + 0.699 * (10.296 + 2.0 * 10.24) + 4.0 * 0.643
)

WINDOW_INSTALLATION_BRIDGE_W_K = {
    "north_sleeping_type1": 2.0 * 1.23 * 0.037 + 1.54 * (0.039 + 0.034),
    "south_dining_type1": 2.0 * 1.23 * 0.037 + 1.54 * (0.039 + 0.034),
    "south_living_type2": 2.0 * 1.11 * 0.037 + 2.37 * (0.039 + 0.034),
    "south_living_type3": 2.0 * 1.54 * 0.037 + 3.34 * (0.039 + 0.034),
    "west_living_type1": 2.0 * 1.23 * 0.038 + 1.54 * (0.040 + 0.035),
    "west_kitchen_type1": 2.0 * 1.23 * 0.038 + 1.54 * (0.040 + 0.035),
    "west_child1_type1": 2.0 * 1.23 * 0.038 + 1.54 * (0.040 + 0.035),
    "east_bath_type1": 2.0 * 1.23 * 0.029 + 1.54 * (0.032 + 0.027),
    "east_child2_type5": 2.0 * 1.23 * 0.029 + 2.44 * (0.032 + 0.027),
    "south_child1_roof_type4": 0.0,
}


def _published_exterior_surface(
    zone_id: str,
    surface_id: str,
    *,
    gross_area_m2: float,
    construction: str,
    azimuth_deg: float,
    tilt_deg: float = 90.0,
    openings: Sequence[dict[str, Any]] = (),
    external_boundary_id: str = "outdoor_air",
    thermal_bridge_conductance_w_k: float = 0.0,
) -> dict[str, Any]:
    u_value, areal_capacity_j_m2_k = PUBLISHED_CONSTRUCTIONS[construction]
    opaque_area_m2 = gross_area_m2 - sum(float(item["area_m2"]) for item in openings)
    if opaque_area_m2 <= 0.0:
        raise ValueError(f"published surface {surface_id} has no opaque area")
    return _surface(
        zone_id,
        surface_id,
        area_m2=gross_area_m2,
        u_value=u_value,
        capacity_j_k=opaque_area_m2 * areal_capacity_j_m2_k,
        azimuth_deg=azimuth_deg,
        tilt_deg=tilt_deg,
        openings=openings,
        external_boundary_id=external_boundary_id,
        thermal_bridge_conductance_w_k=thermal_bridge_conductance_w_k,
        exterior_solar_absorptance_fraction=(
            EXTERIOR_SOLAR_ABSORPTANCE_FRACTION
            if external_boundary_id == "outdoor_air"
            else None
        ),
        exterior_longwave_emissivity_fraction=(
            EXTERIOR_LONGWAVE_EMISSIVITY_FRACTION
            if external_boundary_id == "outdoor_air"
            else None
        ),
        exterior_surface_heat_transfer_coefficient_w_m2_k=(
            EXTERIOR_SURFACE_HEAT_TRANSFER_COEFFICIENT_W_M2_K
            if external_boundary_id == "outdoor_air"
            else None
        ),
    )


def _published_interzone_surface(
    zone_id: str,
    other_zone_id: str,
    *,
    solid_area_m2: float,
    construction: str,
    azimuth_deg: float,
    airflow_opening_area_m2: float = 0.0,
    airflow_open_fraction: float = 0.0,
    airflow_model: str = "none",
    airflow_opening_height_m: float = 0.0,
    airflow_discharge_coefficient: float = 0.0,
    airflow_assumed_velocity_m_s: float = 0.0,
    tilt_deg: float = 90.0,
    thermal_bridge_conductance_w_k: float = 0.0,
) -> dict[str, Any]:
    u_value, areal_capacity_j_m2_k = PUBLISHED_CONSTRUCTIONS[construction]
    return _surface(
        zone_id,
        f"{zone_id}_to_{other_zone_id}",
        area_m2=solid_area_m2,
        u_value=u_value,
        capacity_j_k=0.5 * solid_area_m2 * areal_capacity_j_m2_k,
        azimuth_deg=azimuth_deg,
        adjacent_zone_id=other_zone_id,
        paired_surface_id=f"{other_zone_id}_to_{zone_id}",
        airflow_opening_area_m2=airflow_opening_area_m2,
        airflow_open_fraction=airflow_open_fraction,
        airflow_model=airflow_model,
        airflow_opening_height_m=airflow_opening_height_m,
        airflow_discharge_coefficient=airflow_discharge_coefficient,
        airflow_assumed_velocity_m_s=airflow_assumed_velocity_m_s,
        tilt_deg=tilt_deg,
        thermal_bridge_conductance_w_k=thermal_bridge_conductance_w_k,
    )


def _published_component_surfaces(zone_id: str) -> list[dict[str, Any]]:
    """Return plan-derived fabric without residual-derived conductances."""

    result: list[dict[str, Any]] = []

    def add_wall(
        surface_id: str,
        gross_area_m2: float,
        construction: str,
        azimuth_deg: float,
        windows: Sequence[tuple[str, float, float]] = (),
        tilt_deg: float = 90.0,
        edge_length_m: float = 0.0,
        extra_thermal_bridge_w_k: float = 0.0,
    ) -> None:
        openings = [
            _opening(
                zone_id,
                surface_id,
                name,
                area,
                openable_area_m2=(
                    1.54 * 0.143 + 2.0 * 0.5 * 1.23 * 0.143
                    if name == "west_child1_type1"
                    else 0.0
                ),
            )
            for name, area, _orientation in windows
        ]
        result.append(
            _published_exterior_surface(
                zone_id,
                surface_id,
                gross_area_m2=gross_area_m2,
                construction=construction,
                azimuth_deg=azimuth_deg,
                tilt_deg=tilt_deg,
                openings=openings,
                thermal_bridge_conductance_w_k=(
                    edge_length_m * GROUND_EDGE_PSI_W_M_K.get(azimuth_deg, 0.0)
                    + sum(
                        WINDOW_INSTALLATION_BRIDGE_W_K[name]
                        for name, _area, _orientation in windows
                    )
                    + extra_thermal_bridge_w_k
                ),
            )
        )

    windows_by_orientation = {
        orientation: tuple(item for item in WINDOWS[zone_id] if item[2] == orientation)
        for orientation in {item[2] for item in WINDOWS[zone_id]}
    }
    if zone_id == "ground_airbody":
        add_wall(
            "ground_north_wall",
            2.4325 * GROUND_HEIGHT_M - 2.0,
            "north_south_wall",
            0.0,
            edge_length_m=2.4325,
        )
        add_wall(
            "ground_south_wall",
            10.24 * GROUND_HEIGHT_M,
            "north_south_wall",
            180.0,
            windows_by_orientation[180.0],
            edge_length_m=10.24,
        )
        add_wall(
            "ground_west_wall",
            7.068 * GROUND_HEIGHT_M,
            "west_wall",
            270.0,
            windows_by_orientation[270.0],
            edge_length_m=7.068,
        )
        add_wall(
            "ground_east_wall",
            6.8755 * GROUND_HEIGHT_M,
            "east_wall",
            90.0,
            windows_by_orientation[90.0],
            edge_length_m=6.8755,
        )
        result.append(
            _published_exterior_surface(
                zone_id,
                "ground_front_door",
                gross_area_m2=2.0,
                construction="front_door",
                azimuth_deg=0.0,
            )
        )
    elif zone_id == "kitchen_airbody":
        add_wall(
            "kitchen_north_wall",
            3.3755 * GROUND_HEIGHT_M,
            "north_south_wall",
            0.0,
            edge_length_m=3.3755,
        )
        add_wall(
            "kitchen_west_wall",
            3.228 * GROUND_HEIGHT_M,
            "west_wall",
            270.0,
            windows_by_orientation[270.0],
            edge_length_m=3.228,
        )
    elif zone_id == "sleeping_airbody":
        add_wall(
            "sleeping_north_wall",
            4.432 * GROUND_HEIGHT_M,
            "north_south_wall",
            0.0,
            windows_by_orientation[0.0],
            edge_length_m=4.432,
        )
        add_wall(
            "sleeping_east_wall",
            3.4205 * GROUND_HEIGHT_M,
            "east_wall",
            90.0,
            edge_length_m=3.4205,
        )
    else:
        add_wall(
            "attic_west_gable",
            ATTIC_GABLE_AREA_M2,
            "west_wall",
            270.0,
            windows_by_orientation[270.0],
        )
        add_wall(
            "attic_east_gable",
            ATTIC_GABLE_AREA_M2,
            "east_wall",
            90.0,
            windows_by_orientation[90.0],
        )
        add_wall(
            "attic_north_knee",
            ATTIC_KNEE_AREA_M2,
            "knee_wall",
            0.0,
        )
        add_wall(
            "attic_south_knee",
            ATTIC_KNEE_AREA_M2,
            "knee_wall",
            180.0,
        )
        add_wall(
            "attic_north_roof",
            ROOF_PLANE_AREA_M2,
            "roof",
            0.0,
            tilt_deg=30.0,
            extra_thermal_bridge_w_k=0.5
            * ROOF_THERMAL_BRIDGE_CONDUCTANCE_W_K,
        )
        roof_windows = windows_by_orientation[180.0]
        roof_openings = [
            _opening(zone_id, "attic_south_roof", name, area)
            for name, area, _orientation in roof_windows
        ]
        result.append(
            _published_exterior_surface(
                zone_id,
                "attic_south_roof",
                gross_area_m2=ROOF_PLANE_AREA_M2,
                construction="roof",
                azimuth_deg=180.0,
                tilt_deg=30.0,
                openings=roof_openings,
                thermal_bridge_conductance_w_k=(
                    0.5 * ROOF_THERMAL_BRIDGE_CONDUCTANCE_W_K
                ),
            )
        )

    if zone_id != "attic_airbody":
        floor_area_m2 = sum(ZONE_ROOM_AREAS_M2[zone_id].values())
        result.append(
            _published_exterior_surface(
                zone_id,
                f"{zone_id}_floor_to_cellar",
                gross_area_m2=floor_area_m2,
                construction="floor_to_cellar",
                azimuth_deg=0.0,
                tilt_deg=180.0,
                external_boundary_id="cellar_air",
                thermal_bridge_conductance_w_k=(
                    CELLAR_THERMAL_BRIDGE_CONDUCTANCE_W_K
                    * floor_area_m2
                    / GROUND_CEILING_AREA_M2
                ),
            )
        )

    partition_specs = {
        "kitchen_airbody": (
            (2.835 + 2.625) * GROUND_HEIGHT_M - INTERNAL_DOOR_AREA_M2,
            INTERNAL_DOOR_AREA_M2,
            1.0,
            INTERNAL_DOOR_HEIGHT_M,
            90.0,
            "two_opening_buoyancy",
            CONTAM_LARGE_OPENING_DISCHARGE_COEFFICIENT,
            0.0,
        ),
        "sleeping_airbody": (
            (3.885 + 2.88) * GROUND_HEIGHT_M - INTERNAL_DOOR_AREA_M2,
            INTERNAL_DOOR_AREA_M2,
            0.0,
            INTERNAL_DOOR_HEIGHT_M,
            90.0,
            "two_opening_buoyancy",
            CONTAM_LARGE_OPENING_DISCHARGE_COEFFICIENT,
            0.0,
        ),
    }

    # The published 81.69 m2 ceiling is the sum of the three lower-airbody
    # footprints, not the footprint of the aggregated ground airbody alone.
    # Preserve that topology explicitly so every lower airbody exchanges heat
    # with the attic through the ceiling physically above it.
    lower_zone_ids = ("ground_airbody", "kitchen_airbody", "sleeping_airbody")

    def add_ceiling_pair(lower_zone_id: str, upper_zone_id: str) -> None:
        floor_area_m2 = sum(ZONE_ROOM_AREAS_M2[lower_zone_id].values())
        opening_area_m2 = TRAP_DOOR_AREA_M2 if lower_zone_id == "ground_airbody" else 0.0
        result.append(
            _published_interzone_surface(
                zone_id,
                upper_zone_id if zone_id == lower_zone_id else lower_zone_id,
                solid_area_m2=floor_area_m2 - opening_area_m2,
                construction="ceiling",
                azimuth_deg=180.0 if zone_id == lower_zone_id else 0.0,
                airflow_opening_area_m2=opening_area_m2,
                airflow_open_fraction=1.0 if opening_area_m2 else 0.0,
                airflow_model="prescribed_velocity" if opening_area_m2 else "none",
                airflow_discharge_coefficient=0.60 if opening_area_m2 else 0.0,
                airflow_assumed_velocity_m_s=0.10 if opening_area_m2 else 0.0,
                tilt_deg=0.0,
                thermal_bridge_conductance_w_k=(
                    GROUND_ATTIC_THERMAL_BRIDGE_CONDUCTANCE_W_K
                    * floor_area_m2
                    / GROUND_CEILING_AREA_M2
                ),
            )
        )

    if zone_id == "ground_airbody":
        add_ceiling_pair("ground_airbody", "attic_airbody")
        for other_zone_id in ("kitchen_airbody", "sleeping_airbody"):
            (
                solid_area,
                opening_area,
                opening_fraction,
                opening_height,
                tilt_deg,
                airflow_model,
                discharge_coefficient,
                assumed_velocity,
            ) = partition_specs[other_zone_id]
            result.append(
                _published_interzone_surface(
                    zone_id,
                    other_zone_id,
                    solid_area_m2=solid_area,
                    construction="internal_partition",
                    azimuth_deg=180.0,
                    airflow_opening_area_m2=opening_area,
                    airflow_open_fraction=opening_fraction,
                    airflow_model=airflow_model,
                    airflow_opening_height_m=opening_height,
                    airflow_discharge_coefficient=discharge_coefficient,
                    airflow_assumed_velocity_m_s=assumed_velocity,
                    tilt_deg=tilt_deg,
                    thermal_bridge_conductance_w_k=0.0,
                )
            )
    elif zone_id in ("kitchen_airbody", "sleeping_airbody"):
        (
            solid_area,
            opening_area,
            opening_fraction,
            opening_height,
            tilt_deg,
            airflow_model,
            discharge_coefficient,
            assumed_velocity,
        ) = partition_specs[zone_id]
        result.append(
            _published_interzone_surface(
                zone_id,
                "ground_airbody",
                solid_area_m2=solid_area,
                construction="internal_partition",
                azimuth_deg=0.0,
                airflow_opening_area_m2=opening_area,
                airflow_open_fraction=opening_fraction,
                airflow_model=airflow_model,
                airflow_opening_height_m=opening_height,
                airflow_discharge_coefficient=discharge_coefficient,
                airflow_assumed_velocity_m_s=assumed_velocity,
                tilt_deg=tilt_deg,
                thermal_bridge_conductance_w_k=0.0,
            )
        )
        add_ceiling_pair(zone_id, "attic_airbody")
    else:
        for lower_zone_id in lower_zone_ids:
            add_ceiling_pair(lower_zone_id, "attic_airbody")
    return result


def zone_capacity_fractions(basis: str = "air_volume") -> dict[str, float]:
    """Return deterministic zone weights for structural capacity diagnostics."""

    if basis == "air_volume":
        weights = ZONE_VOLUMES_M3
    elif basis == "floor_area":
        weights = {
            zone_id: sum(room_areas.values())
            for zone_id, room_areas in ZONE_ROOM_AREAS_M2.items()
        }
    else:
        raise ValueError(
            "capacity_allocation_basis must be 'air_volume' or 'floor_area'"
        )
    total = sum(weights.values())
    return {zone_id: value / total for zone_id, value in weights.items()}


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
    dt_minutes: float = DT_MINUTES,
) -> dict[str, Any]:
    # The selected alignment maps row T to (T - dt, T]. This matches the
    # published experiment start and the observed forcing/state lag, while the
    # canonical contract timestamps the start. Treat this as a documented
    # preprocessing decision, not an independently proven workbook convention.
    timestamp = canonical_interval_start or record.timestamp - timedelta(
        minutes=dt_minutes
    )
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
        "sky_temperature_c": (
            (
                record.downwelling_longwave_radiation_w_m2
                / STEFAN_BOLTZMANN_W_M2_K4
            )
            ** 0.25
            - 273.15
            if record.downwelling_longwave_radiation_w_m2 is not None
            and record.downwelling_longwave_radiation_w_m2 > 0.0
            else record.outdoor_temperature_c
        ),
        "relative_humidity_fraction": record.relative_humidity_fraction,
        "atmospheric_pressure_pa": record.atmospheric_pressure_pa,
        "outdoor_co2_ppm": record.outdoor_co2_ppm,
        "wind_speed_m_s": record.wind_speed_m_s,
        "wind_direction_deg": record.wind_direction_deg,
        "direct_normal_radiation_w_m2": direct_normal,
        "diffuse_horizontal_radiation_w_m2": record.diffuse_horizontal_radiation_w_m2,
        "global_horizontal_radiation_w_m2": record.global_horizontal_radiation_w_m2,
        "north_vertical_radiation_w_m2": record.north_vertical_radiation_w_m2,
        "east_vertical_radiation_w_m2": record.east_vertical_radiation_w_m2,
        "south_vertical_radiation_w_m2": record.south_vertical_radiation_w_m2,
        "west_vertical_radiation_w_m2": record.west_vertical_radiation_w_m2,
        "outdoor_illuminance_lux": 0.0,
        "rain": record.rain,
    }


def build_canonical_scenario(
    records: Sequence[Annex71Interval],
    parameters: Annex71ModelParameters | None = None,
    *,
    initial_record: Annex71Interval | None = None,
    capacity_allocation_basis: str = "air_volume",
    fabric_model: str = "published_components",
    dt_minutes: float = DT_MINUTES,
) -> tuple[CanonicalScenario, dict[str, object]]:
    """Build and compile the traceable four-air-body canonical scenario."""

    if not records:
        raise ValueError("records cannot be empty")
    parameters = parameters or Annex71ModelParameters()
    if fabric_model not in {"published_components", "legacy_effective"}:
        raise ValueError(
            "fabric_model must be 'published_components' or 'legacy_effective'"
        )
    if not 0.0 < dt_minutes <= 60.0:
        raise ValueError("dt_minutes must be in (0, 60]")
    maximum_heating = {
        zone_id: max(item.zone(zone_id).heating_power_w for item in records) + 1.0
        for zone_id in ZONE_VOLUMES_M3
    }
    maximum_ventilation = {
        zone_id: max(
            max(
                item.zone(zone_id).ventilation_supply_flow_m3_s,
                item.zone(zone_id).ventilation_exhaust_flow_m3_s,
            )
            for item in records
        )
        + 1.0e-6
        for zone_id in ZONE_VOLUMES_M3
    }
    first = initial_record or records[0]
    canonical_start = records[0].timestamp - timedelta(minutes=dt_minutes)
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
                "infiltration_air_changes_per_hour": (
                    0.061 if fabric_model == "published_components" else 0.0
                ),
                "surfaces": (
                    _published_component_surfaces(zone_id)
                    if fabric_model == "published_components"
                    else _legacy_zone_surfaces(
                        zone_id,
                        parameters,
                        capacity_allocation_basis=capacity_allocation_basis,
                    )
                ),
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
            "dt_minutes": dt_minutes,
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
                    "rule": (
                        "published component dimensions, U-values, and layer heat capacities"
                        if fabric_model == "published_components"
                        else "legacy measured whole-house HTC allocation retained for forensic replay"
                    ),
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
                canonical_interval_start=canonical_start
                + timedelta(minutes=dt_minutes * index),
                dt_minutes=dt_minutes,
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


def build_annex71_step_input(
    scenario: CanonicalScenario,
    graph: Mapping[str, object],
    record: Annex71Interval,
    index: int,
    prior: tuple[PriorZonePhysicalState, ...],
    *,
    heating_convective_fraction: float = HEATER_CONVECTIVE_FRACTION,
) -> SimulationStepInput:
    if not 0.0 <= heating_convective_fraction <= 1.0:
        raise ValueError("heating_convective_fraction must be between zero and one")
    connections = tuple(dict(item) for item in graph["connections"])
    available_opening_ids = {
        str(connection["opening_ids"][0])
        for connection in connections
        if connection.get("connection_type") == "opening"
    }
    interzone_opening_fractions_by_surface = {
        "ground_airbody_to_attic_airbody": record.attic_door_opening_fraction,
        "ground_airbody_to_kitchen_airbody": record.kitchen_door_opening_fraction,
    }
    available_interzone_opening_surface_ids = {
        str(surface_id)
        for connection in connections
        if connection.get("boundary_type") == "interzone"
        and float(connection.get("airflow_opening_area_m2", 0.0)) > 0.0
        for surface_id in connection.get("surface_ids", ())
    }
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
                heating_convective_fraction=heating_convective_fraction,
                cooling_on=False,
                cooling_power_fraction=0.0,
                ventilation_volume_flow_m3_s=observation.ventilation_supply_flow_m3_s,
                ventilation_supply_temperature_c=(
                    observation.ventilation_supply_temperature_c
                    if observation.ventilation_supply_flow_m3_s > 0.0
                    else None
                ),
                ventilation_exhaust_volume_flow_m3_s=(
                    observation.ventilation_exhaust_flow_m3_s
                ),
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
    return SimulationStepInput(
        scenario_id=scenario.scenario_id,
        timestep_index=index,
        timestamp=scenario.weather_series[index].timestamp,
        dt_minutes=scenario.simulation_period.dt_minutes,
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
        external_boundary_states=(
            ExternalBoundaryState(
                boundary_id="cellar_air",
                temperature_c=record.cellar_temperature_c,
            ),
        )
        if any(
            surface.external_boundary_id == "cellar_air"
            for zone in scenario.building.dwelling.zones
            for surface in zone.surfaces
        )
        else (),
        opening_control_commands=tuple(
            OpeningControlCommand(
                opening_id=opening_id,
                opening_fraction=(
                    record.child1_window_opening_fraction
                    if opening_id == "window_west_child1_type1"
                    else 0.0
                ),
                shading_open_fraction=shading_open_fraction,
            )
            for opening_id, shading_open_fraction in sorted(
                {
                    "window_west_child1_type1": 1.0,
                    **dict(record.shading_open_fraction_by_opening),
                }.items()
            )
            if opening_id in available_opening_ids
        ),
        interzone_opening_controls=tuple(
            InterzoneOpeningControl(
                surface_id=surface_id,
                opening_fraction=opening_fraction,
            )
            for surface_id, opening_fraction in sorted(
                interzone_opening_fractions_by_surface.items()
            )
            if surface_id in available_interzone_opening_surface_ids
        ),
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
    *,
    fabric_model: str = "published_components",
) -> Annex71RunResult:
    """Execute all intervals through the canonical object-engine adapter."""

    if len(records) < 2:
        raise ValueError("at least two observations are required for interval scoring")
    dt = records[1].timestamp - records[0].timestamp
    if any(
        current.timestamp - previous.timestamp != dt
        for previous, current in pairwise(records)
    ):
        raise ValueError("Annex 71 run records must have a fixed timestep")
    dt_minutes = dt.total_seconds() / 60.0
    if not 0.0 < dt_minutes <= 60.0:
        raise ValueError("Annex 71 run timestep must be in (0, 60] minutes")
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
        fabric_model=fabric_model,
        dt_minutes=dt_minutes,
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
        step = build_annex71_step_input(scenario, graph, record, index, prior)
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
    "build_annex71_step_input",
    "build_canonical_scenario",
    "load_annex71_intervals",
    "parameters_as_dict",
    "run_object_scenario",
    "select_interval",
    "temperature_metrics",
    "zone_capacity_fractions",
]
