"""
ABBEY weather and outside boundary states.

Phase 3.1:
- WeatherState

"""

import math
from dataclasses import dataclass, replace
from datetime import datetime as DateTime, timedelta, timezone
from typing import Any, Dict, Optional, List
import copy
import os
import pandas as pd
import numpy as np

from nexusep.abbey.building.physics.graph import normalize_orientation_deg

VALID_WEATHER_SOURCE_TYPES = {
    "epw",
    "manual",
    "synthetic",
}

EPW_COLUMNS = [
    "year",
    "month",
    "day",
    "hour",
    "minute",
    "data_source_uncertainty_flags",
    "dry_bulb_temperature_c",
    "dew_point_temperature_c",
    "relative_humidity_percent",
    "atmospheric_pressure_pa",
    "extraterrestrial_horizontal_radiation_w_m2",
    "extraterrestrial_direct_normal_radiation_w_m2",
    "horizontal_infrared_radiation_intensity_w_m2",
    "global_horizontal_radiation_w_m2",
    "direct_normal_radiation_w_m2",
    "diffuse_horizontal_radiation_w_m2",
    "global_horizontal_illuminance_lux",
    "direct_normal_illuminance_lux",
    "diffuse_horizontal_illuminance_lux",
    "zenith_luminance_cd_m2",
    "wind_direction_deg",
    "wind_speed_m_s",
    "total_sky_cover_tenths",
    "opaque_sky_cover_tenths",
    "visibility_km",
    "ceiling_height_m",
    "present_weather_observation",
    "present_weather_codes",
    "precipitable_water_mm",
    "aerosol_optical_depth",
    "snow_depth_cm",
    "days_since_last_snowfall",
    "albedo",
    "liquid_precipitation_depth_mm",
    "liquid_precipitation_quantity_hr",
]

RADIATION_COLUMNS = [
    "direct_normal_radiation_w_m2",
    "diffuse_horizontal_radiation_w_m2",
    "global_horizontal_radiation_w_m2",
]

ILLUMINANCE_COLUMNS = [
    "global_horizontal_illuminance_lux",
    "direct_normal_illuminance_lux",
    "diffuse_horizontal_illuminance_lux",
]

WEATHER_CORE_COLUMNS = [
    "datetime",
    "outdoor_temperature_c",
    "wind_speed_m_s",
    "wind_direction_deg",
    "direct_normal_radiation_w_m2",
    "diffuse_horizontal_radiation_w_m2",
    "global_horizontal_radiation_w_m2",
    "outdoor_illuminance_lux",
    "outdoor_co2_ppm",
    "outdoor_noise_db",
]

WEATHER_OPTIONAL_COLUMNS = [
    "relative_humidity_percent",
    "atmospheric_pressure_pa",
    "sky_condition",
    "total_sky_cover_tenths",
    "opaque_sky_cover_tenths",
]

EPW_CRITICAL_COLUMNS = [
    "dry_bulb_temperature_c",
    "wind_speed_m_s",
    "wind_direction_deg",
    "direct_normal_radiation_w_m2",
    "diffuse_horizontal_radiation_w_m2",
    "global_horizontal_radiation_w_m2",
]

DEFAULT_LUMINOUS_EFFICACY_LUX_PER_W_M2 = 120.0
DEFAULT_NIGHT_RADIATION_THRESHOLD_W_M2 = 1.0

DEFAULT_CALM_WIND_SPEED_M_S = 0.2
DEFAULT_WIND_DIRECTION_DEG = 0.0
DEFAULT_OUTDOOR_CO2_PPM = 420.0
DEFAULT_OUTDOOR_NOISE_DB = 45.0
DEFAULT_SKY_CONDITION = "unknown"

SUPPORTED_WEATHER_TIMESTEPS_MINUTES = {
    1,
    5,
    10,
    15,
    60,
}

LINEAR_INTERPOLATION_COLUMNS = [
    "outdoor_temperature_c",
    "relative_humidity_percent",
    "atmospheric_pressure_pa",
    "wind_speed_m_s",
    "direct_normal_radiation_w_m2",
    "diffuse_horizontal_radiation_w_m2",
    "global_horizontal_radiation_w_m2",
    "global_horizontal_illuminance_lux",
    "direct_normal_illuminance_lux",
    "diffuse_horizontal_illuminance_lux",
    "outdoor_illuminance_lux",
    "total_sky_cover_tenths",
    "opaque_sky_cover_tenths",
    "outdoor_co2_ppm",
    "outdoor_noise_db",
    "outdoor_pollution_index",
]

NON_NEGATIVE_INTERPOLATED_COLUMNS = [
    "wind_speed_m_s",
    "direct_normal_radiation_w_m2",
    "diffuse_horizontal_radiation_w_m2",
    "global_horizontal_radiation_w_m2",
    "global_horizontal_illuminance_lux",
    "direct_normal_illuminance_lux",
    "diffuse_horizontal_illuminance_lux",
    "outdoor_illuminance_lux",
    "outdoor_co2_ppm",
    "outdoor_noise_db",
    "outdoor_pollution_index",
]

CATEGORICAL_WEATHER_COLUMNS = [
    "sky_condition",
    "outdoor_noise_class",
]


@dataclass
class WeatherState:
    """
    Weather and outside boundary condition at one simulation timestep.
    """

    datetime: Any

    outdoor_temperature_c: float = 20.0
    sky_temperature_c: Optional[float] = None

    wind_speed_m_s: float = 0.0
    wind_direction_deg: float = 0.0

    direct_normal_radiation_w_m2: float = 0.0
    diffuse_horizontal_radiation_w_m2: float = 0.0
    global_horizontal_radiation_w_m2: float = 0.0
    north_vertical_radiation_w_m2: Optional[float] = None
    east_vertical_radiation_w_m2: Optional[float] = None
    south_vertical_radiation_w_m2: Optional[float] = None
    west_vertical_radiation_w_m2: Optional[float] = None

    outdoor_illuminance_lux: float = 0.0
    sky_condition: str = "unknown"

    outdoor_co2_ppm: float = 420.0
    outdoor_noise_db: float = 45.0

    relative_humidity_percent: Optional[float] = None
    atmospheric_pressure_pa: Optional[float] = None

    # Solar geometry is calculated once by the canonical adapter.  Legacy
    # callers may omit it and continue through the explicitly labelled
    # compatibility path.
    solar_zenith_deg: Optional[float] = None
    solar_azimuth_deg: Optional[float] = None
    solar_altitude_deg: Optional[float] = None
    ground_albedo_fraction: float = 0.0

    def __post_init__(self) -> None:
        self.datetime = _normalize_datetime(self.datetime)

        self.outdoor_temperature_c = float(self.outdoor_temperature_c)
        if self.sky_temperature_c is not None:
            self.sky_temperature_c = float(self.sky_temperature_c)
            if not math.isfinite(self.sky_temperature_c):
                raise ValueError("sky_temperature_c must be finite")

        self.wind_speed_m_s = _non_negative_float(
            self.wind_speed_m_s,
            "wind_speed_m_s",
        )

        self.wind_direction_deg = normalize_orientation_deg(
            self.wind_direction_deg
        )

        self.direct_normal_radiation_w_m2 = _non_negative_float(
            self.direct_normal_radiation_w_m2,
            "direct_normal_radiation_w_m2",
        )

        self.diffuse_horizontal_radiation_w_m2 = _non_negative_float(
            self.diffuse_horizontal_radiation_w_m2,
            "diffuse_horizontal_radiation_w_m2",
        )

        self.global_horizontal_radiation_w_m2 = _non_negative_float(
            self.global_horizontal_radiation_w_m2,
            "global_horizontal_radiation_w_m2",
        )

        self.outdoor_illuminance_lux = _non_negative_float(
            self.outdoor_illuminance_lux,
            "outdoor_illuminance_lux",
        )

        if self.sky_condition is None or not str(self.sky_condition).strip():
            self.sky_condition = "unknown"

        self.sky_condition = str(self.sky_condition).strip().lower()

        self.outdoor_co2_ppm = _positive_float(
            self.outdoor_co2_ppm,
            "outdoor_co2_ppm",
        )

        self.outdoor_noise_db = _non_negative_float(
            self.outdoor_noise_db,
            "outdoor_noise_db",
        )

        if self.relative_humidity_percent is not None:
            self.relative_humidity_percent = _clamp(
                self.relative_humidity_percent,
                0.0,
                100.0,
            )

        if self.atmospheric_pressure_pa is not None:
            self.atmospheric_pressure_pa = _positive_float(
                self.atmospheric_pressure_pa,
                "atmospheric_pressure_pa",
            )

        if self.solar_zenith_deg is not None:
            self.solar_zenith_deg = _clamp(self.solar_zenith_deg, 0.0, 180.0)
        if self.solar_azimuth_deg is not None:
            self.solar_azimuth_deg = normalize_orientation_deg(
                self.solar_azimuth_deg
            )
        if self.solar_altitude_deg is not None:
            self.solar_altitude_deg = _clamp(
                self.solar_altitude_deg, -90.0, 90.0
            )
        self.ground_albedo_fraction = _clamp(
            self.ground_albedo_fraction, 0.0, 1.0
        )
        for field_name in (
            "north_vertical_radiation_w_m2",
            "east_vertical_radiation_w_m2",
            "south_vertical_radiation_w_m2",
            "west_vertical_radiation_w_m2",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, _non_negative_float(value, field_name))

    def copy(self, **updates: Any) -> "WeatherState":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "datetime": self.datetime.isoformat(),
            "outdoor_temperature_c": self.outdoor_temperature_c,
            "sky_temperature_c": self.sky_temperature_c,
            "wind_speed_m_s": self.wind_speed_m_s,
            "wind_direction_deg": self.wind_direction_deg,
            "direct_normal_radiation_w_m2": self.direct_normal_radiation_w_m2,
            "diffuse_horizontal_radiation_w_m2": self.diffuse_horizontal_radiation_w_m2,
            "global_horizontal_radiation_w_m2": self.global_horizontal_radiation_w_m2,
            "north_vertical_radiation_w_m2": self.north_vertical_radiation_w_m2,
            "east_vertical_radiation_w_m2": self.east_vertical_radiation_w_m2,
            "south_vertical_radiation_w_m2": self.south_vertical_radiation_w_m2,
            "west_vertical_radiation_w_m2": self.west_vertical_radiation_w_m2,
            "outdoor_illuminance_lux": self.outdoor_illuminance_lux,
            "sky_condition": self.sky_condition,
            "outdoor_co2_ppm": self.outdoor_co2_ppm,
            "outdoor_noise_db": self.outdoor_noise_db,
            "relative_humidity_percent": self.relative_humidity_percent,
            "atmospheric_pressure_pa": self.atmospheric_pressure_pa,
            "solar_zenith_deg": self.solar_zenith_deg,
            "solar_azimuth_deg": self.solar_azimuth_deg,
            "solar_altitude_deg": self.solar_altitude_deg,
            "ground_albedo_fraction": self.ground_albedo_fraction,
        }
    
@dataclass
class OutdoorBoundaryDefaults:
    """
    Default outside boundary values not usually provided by EPW.

    No air-quality, pollution, or acoustic solver here.
    These are only boundary placeholders.
    """

    outdoor_co2_ppm: float = DEFAULT_OUTDOOR_CO2_PPM
    outdoor_noise_db: float = DEFAULT_OUTDOOR_NOISE_DB
    sky_condition: str = DEFAULT_SKY_CONDITION

    # Reserved for later.
    outdoor_noise_class: Optional[str] = None
    outdoor_pollution_index: Optional[float] = None

    def __post_init__(self) -> None:
        self.outdoor_co2_ppm = _positive_float(
            self.outdoor_co2_ppm,
            "outdoor_co2_ppm",
        )

        self.outdoor_noise_db = _non_negative_float(
            self.outdoor_noise_db,
            "outdoor_noise_db",
        )

        if self.sky_condition is None or not str(self.sky_condition).strip():
            self.sky_condition = DEFAULT_SKY_CONDITION

        self.sky_condition = str(self.sky_condition).strip().lower()

        if self.outdoor_noise_class is not None:
            self.outdoor_noise_class = str(self.outdoor_noise_class).strip().lower()

            if not self.outdoor_noise_class:
                self.outdoor_noise_class = None

        if self.outdoor_pollution_index is not None:
            self.outdoor_pollution_index = _non_negative_float(
                self.outdoor_pollution_index,
                "outdoor_pollution_index",
            )

    def copy(self, **updates: Any) -> "OutdoorBoundaryDefaults":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outdoor_co2_ppm": self.outdoor_co2_ppm,
            "outdoor_noise_db": self.outdoor_noise_db,
            "sky_condition": self.sky_condition,
            "outdoor_noise_class": self.outdoor_noise_class,
            "outdoor_pollution_index": self.outdoor_pollution_index,
        }

@dataclass
class WeatherSourceMetadata:
    """
    Metadata for the weather source used by ABBEY.

    This describes where the weather data came from.
    It does not store timestep weather values.
    """

    source_type: str = "manual"
    source_path: Optional[str] = None

    location_name: str = "unknown"

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # EPW uses numeric timezone offset from GMT.
    # Example: Italy winter standard time is usually +1.
    timezone: Optional[float] = None

    elevation_m: Optional[float] = None

    year: Optional[int] = None
    is_tmy: bool = False

    data_timestep_minutes: int = 60

    def __post_init__(self) -> None:
        self.source_type = str(self.source_type).strip().lower()

        if self.source_type not in VALID_WEATHER_SOURCE_TYPES:
            raise ValueError(
                "Invalid weather source_type '{}'. Valid values are {}.".format(
                    self.source_type,
                    sorted(VALID_WEATHER_SOURCE_TYPES),
                )
            )

        if self.source_path is not None:
            self.source_path = str(self.source_path)

        if self.location_name is None or not str(self.location_name).strip():
            self.location_name = "unknown"

        self.location_name = str(self.location_name).strip()

        if self.latitude is not None:
            self.latitude = float(self.latitude)

            if self.latitude < -90.0 or self.latitude > 90.0:
                raise ValueError(
                    "WeatherSourceMetadata.latitude must be in [-90, 90]."
                )

        if self.longitude is not None:
            self.longitude = float(self.longitude)

            if self.longitude < -180.0 or self.longitude > 180.0:
                raise ValueError(
                    "WeatherSourceMetadata.longitude must be in [-180, 180]."
                )

        if self.timezone is not None:
            self.timezone = float(self.timezone)

            if self.timezone < -12.0 or self.timezone > 14.0:
                raise ValueError(
                    "WeatherSourceMetadata.timezone must be a UTC offset in roughly [-12, 14]."
                )

        if self.elevation_m is not None:
            self.elevation_m = float(self.elevation_m)

        if self.year is not None:
            self.year = int(self.year)

        self.data_timestep_minutes = int(self.data_timestep_minutes)

        if self.data_timestep_minutes <= 0:
            raise ValueError(
                "WeatherSourceMetadata.data_timestep_minutes must be positive."
            )

        if self.source_type == "epw" and self.data_timestep_minutes != 60:
            raise ValueError(
                "EPW weather data should have data_timestep_minutes=60."
            )

        if self.source_type == "epw" and not self.source_path:
            raise ValueError(
                "EPW weather source requires source_path."
            )

    def copy(self, **updates: Any) -> "WeatherSourceMetadata":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_path": self.source_path,
            "location_name": self.location_name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timezone": self.timezone,
            "elevation_m": self.elevation_m,
            "year": self.year,
            "is_tmy": self.is_tmy,
            "data_timestep_minutes": self.data_timestep_minutes,
        }
    
    
@dataclass
class WeatherTimeSeries:
    """
    Clean internal weather table.

    Stores:
    - metadata
    - extracted hourly weather dataframe
    - raw EPW dataframe for debugging
    - raw EPW header lines

    No interpolation yet.
    No building physics yet.
    """

    metadata: WeatherSourceMetadata
    hourly_dataframe: Any
    raw_dataframe: Optional[Any] = None
    raw_header_lines: List[str] = None
    timestep_dataframe: Optional[Any] = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            raise ValueError("WeatherTimeSeries.metadata cannot be None.")

        if self.hourly_dataframe is None:
            raise ValueError("WeatherTimeSeries.hourly_dataframe cannot be None.")

        if self.raw_header_lines is None:
            self.raw_header_lines = []

    def copy(self, **updates: Any) -> "WeatherTimeSeries":
        if not updates:
            return copy.deepcopy(self)

        return replace(self, **updates)

    def number_of_records(self) -> int:
        return int(len(self.hourly_dataframe))

    def columns(self) -> List[str]:
        return list(self.hourly_dataframe.columns)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "number_of_hourly_records": int(len(self.hourly_dataframe)),
            "number_of_timestep_records": self.number_of_timestep_records(),
            "hourly_columns": list(self.hourly_dataframe.columns),
            "timestep_columns": list(self.simulation_dataframe().columns),
            "raw_header_line_count": len(self.raw_header_lines),
        }
    
    def simulation_dataframe(self) -> Any:
        if self.timestep_dataframe is not None:
            return self.timestep_dataframe

        return self.hourly_dataframe

    def number_of_timestep_records(self) -> int:
        return int(len(self.simulation_dataframe()))

@dataclass
class WeatherProvider:
    """
    Provides WeatherState objects to the simulation runner.

    Physics modules should not know about EPW files or weather dataframes.
    They should receive only WeatherState.
    """

    weather_series: WeatherTimeSeries
    use_timestep_dataframe: bool = True

    def __post_init__(self) -> None:
        if self.weather_series is None:
            raise ValueError("WeatherProvider.weather_series cannot be None.")

        if self.use_timestep_dataframe:
            self._df = self.weather_series.simulation_dataframe().copy()
        else:
            self._df = self.weather_series.hourly_dataframe.copy()

        if "datetime" not in self._df.columns:
            raise ValueError(
                "WeatherProvider dataframe must contain a 'datetime' column."
            )

        self._df["datetime"] = pd.to_datetime(self._df["datetime"])
        self._df = self._df.sort_values("datetime")
        self._df = self._df.reset_index(drop=True)

        if len(self._df) == 0:
            raise ValueError("WeatherProvider dataframe is empty.")

        self._datetime_to_step = {}

        for index, value in enumerate(self._df["datetime"]):
            self._datetime_to_step[pd.Timestamp(value)] = index

    def number_of_steps(self) -> int:
        return int(len(self._df))

    def start_datetime(self) -> Any:
        return self._df["datetime"].iloc[0].to_pydatetime()

    def end_datetime(self) -> Any:
        return self._df["datetime"].iloc[-1].to_pydatetime()

    def datetimes(self) -> List[Any]:
        return [
            value.to_pydatetime()
            for value in self._df["datetime"]
        ]

    def get_state_by_step(self, step_index: int) -> WeatherState:
        step_index = int(step_index)

        if step_index < 0 or step_index >= len(self._df):
            raise IndexError(
                "Weather step_index {} is outside available range [0, {}].".format(
                    step_index,
                    len(self._df) - 1,
                )
            )

        row = self._df.iloc[step_index]

        return _weather_state_from_row(row)

    def get_state(self, datetime_value: Any) -> WeatherState:
        timestamp = pd.Timestamp(_normalize_datetime(datetime_value))

        if timestamp not in self._datetime_to_step:
            raise KeyError(
                "Weather datetime {} not found. "
                "Use a timestep datetime produced by the WeatherProvider.".format(
                    timestamp
                )
            )

        return self.get_state_by_step(self._datetime_to_step[timestamp])

    def dataframe(self) -> Any:
        return self._df.copy()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "number_of_steps": self.number_of_steps(),
            "start_datetime": self.start_datetime().isoformat(),
            "end_datetime": self.end_datetime().isoformat(),
            "metadata": self.weather_series.metadata.to_dict(),
            "use_timestep_dataframe": self.use_timestep_dataframe,
        }

@dataclass
class WeatherValidationReport:
    errors: List[str] = None
    warnings: List[str] = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []

        if self.warnings is None:
            self.warnings = []

    def add_error(self, message: str) -> None:
        self.errors.append(str(message))

    def add_warning(self, message: str) -> None:
        self.warnings.append(str(message))

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "number_of_errors": len(self.errors),
            "number_of_warnings": len(self.warnings),
        }

    def __repr__(self) -> str:
        return (
            "WeatherValidationReport(errors="
            + str(len(self.errors))
            + ", warnings="
            + str(len(self.warnings))
            + ")"
        )
    
def validate_weather_timeseries(
    weather_series: WeatherTimeSeries,
    require_timestep_dataframe: bool = False,
    expected_dt_minutes: Optional[int] = None,
    realistic_mode: bool = True,
    raise_on_error: bool = False,
) -> WeatherValidationReport:
    """
    Validate weather inputs before physics starts.

    Checks:
    - required columns
    - value ranges
    - timestep coverage
    - EPW raw columns when source_type == epw
    - optional missing fields

    No building physics.
    """

    report = WeatherValidationReport()

    if weather_series is None:
        report.add_error("weather_series cannot be None.")
        return _finish_weather_validation(report, raise_on_error)

    if weather_series.metadata is None:
        report.add_error("weather_series.metadata cannot be None.")

    _validate_weather_metadata(weather_series, report)
    _validate_raw_epw_columns(weather_series, report)

    _validate_weather_dataframe(
        df=weather_series.hourly_dataframe,
        dataframe_name="hourly_dataframe",
        report=report,
        realistic_mode=realistic_mode,
        expected_dt_minutes=60,
    )

    if require_timestep_dataframe and weather_series.timestep_dataframe is None:
        report.add_error(
            "weather_series.timestep_dataframe is required but is None. "
            "Run interpolate_weather_to_timestep(...) first."
        )

    if weather_series.timestep_dataframe is not None:
        _validate_weather_dataframe(
            df=weather_series.timestep_dataframe,
            dataframe_name="timestep_dataframe",
            report=report,
            realistic_mode=realistic_mode,
            expected_dt_minutes=expected_dt_minutes,
        )

    return _finish_weather_validation(report, raise_on_error)

def _validate_weather_metadata(
    weather_series: WeatherTimeSeries,
    report: WeatherValidationReport,
) -> None:
    metadata = weather_series.metadata

    if metadata is None:
        return

    if metadata.source_type not in VALID_WEATHER_SOURCE_TYPES:
        report.add_error(
            "Invalid weather metadata source_type: "
            + str(metadata.source_type)
        )

    if metadata.source_type == "epw" and not metadata.source_path:
        report.add_error("EPW weather metadata requires source_path.")

    if metadata.source_type == "epw" and metadata.data_timestep_minutes != 60:
        report.add_error("EPW data_timestep_minutes must be 60.")

    if metadata.latitude is None:
        report.add_warning("Weather metadata latitude is missing.")

    if metadata.longitude is None:
        report.add_warning("Weather metadata longitude is missing.")

    if metadata.timezone is None:
        report.add_warning("Weather metadata timezone is missing.")

    if metadata.elevation_m is None:
        report.add_warning("Weather metadata elevation_m is missing.")

    if metadata.is_tmy and metadata.year is not None:
        report.add_warning(
            "Weather metadata is marked as TMY but also has a specific year. "
            "This is allowed, but remember it is representative weather."
        )


def _validate_raw_epw_columns(
    weather_series: WeatherTimeSeries,
    report: WeatherValidationReport,
) -> None:
    metadata = weather_series.metadata

    if metadata is None:
        return

    if metadata.source_type != "epw":
        return

    if weather_series.raw_dataframe is None:
        report.add_warning(
            "EPW weather has no raw_dataframe. Raw debugging values are unavailable."
        )
        return

    raw_df = weather_series.raw_dataframe

    for column in EPW_CRITICAL_COLUMNS:
        if column not in raw_df.columns:
            report.add_error("Missing critical EPW column: " + column)
            continue

        values = pd.to_numeric(raw_df[column], errors="coerce")

        if values.isna().all():
            report.add_error(
                "Critical EPW column contains no numeric values: " + column
            )


def _validate_weather_dataframe(
    df: Any,
    dataframe_name: str,
    report: WeatherValidationReport,
    realistic_mode: bool,
    expected_dt_minutes: Optional[int],
) -> None:
    if df is None:
        report.add_error(dataframe_name + " cannot be None.")
        return

    if len(df) == 0:
        report.add_error(dataframe_name + " is empty.")
        return

    _validate_required_weather_columns(df, dataframe_name, report)
    _validate_optional_weather_columns(df, dataframe_name, report)
    _validate_datetime_coverage(df, dataframe_name, report, expected_dt_minutes)

    if "outdoor_temperature_c" in df.columns:
        _validate_numeric_range(
            df=df,
            column="outdoor_temperature_c",
            dataframe_name=dataframe_name,
            report=report,
            min_error=-90.0,
            max_error=80.0,
            min_warning=-50.0,
            max_warning=60.0,
            realistic_mode=realistic_mode,
        )

    if "wind_speed_m_s" in df.columns:
        _validate_non_negative_column(
            df,
            "wind_speed_m_s",
            dataframe_name,
            report,
        )

        if realistic_mode:
            _validate_warning_upper_bound(
                df,
                "wind_speed_m_s",
                dataframe_name,
                report,
                upper_warning=60.0,
            )

    if "wind_direction_deg" in df.columns:
        _validate_wind_direction_column(
            df,
            dataframe_name,
            report,
        )

    for column in RADIATION_COLUMNS:
        if column in df.columns:
            _validate_non_negative_column(
                df,
                column,
                dataframe_name,
                report,
            )

    illuminance_columns = list(ILLUMINANCE_COLUMNS) + [
        "outdoor_illuminance_lux",
    ]

    for column in illuminance_columns:
        if column in df.columns:
            _validate_non_negative_column(
                df,
                column,
                dataframe_name,
                report,
            )

    if "outdoor_co2_ppm" in df.columns:
        _validate_positive_column(
            df,
            "outdoor_co2_ppm",
            dataframe_name,
            report,
        )

    if "outdoor_noise_db" in df.columns:
        _validate_non_negative_column(
            df,
            "outdoor_noise_db",
            dataframe_name,
            report,
        )

    if "relative_humidity_percent" in df.columns:
        _validate_numeric_range(
            df=df,
            column="relative_humidity_percent",
            dataframe_name=dataframe_name,
            report=report,
            min_error=0.0,
            max_error=100.0,
            min_warning=0.0,
            max_warning=100.0,
            realistic_mode=False,
        )

    if "atmospheric_pressure_pa" in df.columns:
        _validate_positive_column(
            df,
            "atmospheric_pressure_pa",
            dataframe_name,
            report,
        )
   
def _validate_required_weather_columns(
    df: Any,
    dataframe_name: str,
    report: WeatherValidationReport,
) -> None:
    for column in WEATHER_CORE_COLUMNS:
        if column not in df.columns:
            report.add_error(
                dataframe_name + " is missing required column: " + column
            )


def _validate_optional_weather_columns(
    df: Any,
    dataframe_name: str,
    report: WeatherValidationReport,
) -> None:
    for column in WEATHER_OPTIONAL_COLUMNS:
        if column not in df.columns:
            report.add_warning(
                dataframe_name + " is missing optional column: " + column
            )


def _validate_datetime_coverage(
    df: Any,
    dataframe_name: str,
    report: WeatherValidationReport,
    expected_dt_minutes: Optional[int],
) -> None:
    if "datetime" not in df.columns:
        return

    datetimes = pd.to_datetime(
        df["datetime"],
        errors="coerce",
    )

    if datetimes.isna().any():
        report.add_error(
            dataframe_name + " contains invalid datetime values."
        )
        return

    if not datetimes.is_monotonic_increasing:
        report.add_error(
            dataframe_name + " datetime column must be sorted increasingly."
        )

    if datetimes.duplicated().any():
        report.add_error(
            dataframe_name + " contains duplicate datetime values."
        )

    if expected_dt_minutes is not None and len(datetimes) > 1:
        expected_delta = pd.Timedelta(minutes=int(expected_dt_minutes))
        deltas = datetimes.diff().dropna()

        bad = deltas[deltas != expected_delta]

        if len(bad) > 0:
            report.add_error(
                dataframe_name
                + " timestep coverage is not regular at "
                + str(expected_dt_minutes)
                + " minutes."
            )


def _validate_numeric_range(
    df: Any,
    column: str,
    dataframe_name: str,
    report: WeatherValidationReport,
    min_error: float,
    max_error: float,
    min_warning: float,
    max_warning: float,
    realistic_mode: bool,
) -> None:
    values = pd.to_numeric(df[column], errors="coerce")

    if values.isna().any():
        report.add_error(
            dataframe_name + "." + column + " contains NaN/non-numeric values."
        )
        return

    if (values < min_error).any() or (values > max_error).any():
        report.add_error(
            dataframe_name
            + "."
            + column
            + " has values outside hard range ["
            + str(min_error)
            + ", "
            + str(max_error)
            + "]."
        )

    if realistic_mode:
        if (values < min_warning).any() or (values > max_warning).any():
            report.add_warning(
                dataframe_name
                + "."
                + column
                + " has values outside realistic warning range ["
                + str(min_warning)
                + ", "
                + str(max_warning)
                + "]."
            )


def _validate_non_negative_column(
    df: Any,
    column: str,
    dataframe_name: str,
    report: WeatherValidationReport,
) -> None:
    values = pd.to_numeric(df[column], errors="coerce")

    if values.isna().any():
        report.add_error(
            dataframe_name + "." + column + " contains NaN/non-numeric values."
        )
        return

    if (values < 0.0).any():
        report.add_error(
            dataframe_name + "." + column + " contains negative values."
        )


def _validate_positive_column(
    df: Any,
    column: str,
    dataframe_name: str,
    report: WeatherValidationReport,
) -> None:
    values = pd.to_numeric(df[column], errors="coerce")

    if values.isna().any():
        report.add_error(
            dataframe_name + "." + column + " contains NaN/non-numeric values."
        )
        return

    if (values <= 0.0).any():
        report.add_error(
            dataframe_name + "." + column + " must be positive."
        )


def _validate_wind_direction_column(
    df: Any,
    dataframe_name: str,
    report: WeatherValidationReport,
) -> None:
    values = pd.to_numeric(
        df["wind_direction_deg"],
        errors="coerce",
    )

    if values.isna().any():
        report.add_error(
            dataframe_name + ".wind_direction_deg contains NaN/non-numeric values."
        )
        return

    if (values < 0.0).any() or (values >= 360.0).any():
        report.add_error(
            dataframe_name
            + ".wind_direction_deg must be in [0, 360)."
        )


def _validate_warning_upper_bound(
    df: Any,
    column: str,
    dataframe_name: str,
    report: WeatherValidationReport,
    upper_warning: float,
) -> None:
    values = pd.to_numeric(df[column], errors="coerce")

    if values.isna().any():
        return

    if (values > upper_warning).any():
        report.add_warning(
            dataframe_name
            + "."
            + column
            + " has unusually high values above "
            + str(upper_warning)
            + "."
        )


def _finish_weather_validation(
    report: WeatherValidationReport,
    raise_on_error: bool,
) -> WeatherValidationReport:
    if raise_on_error and report.has_errors():
        raise ValueError(
            "Weather validation failed with errors: "
            + str(report.errors)
        )

    return report

def _weather_state_from_row(row: Any) -> WeatherState:
    return WeatherState(
        datetime=_row_value(row, "datetime"),
        outdoor_temperature_c=_row_value(
            row,
            "outdoor_temperature_c",
            20.0,
        ),
        wind_speed_m_s=_row_value(
            row,
            "wind_speed_m_s",
            0.0,
        ),
        wind_direction_deg=_row_value(
            row,
            "wind_direction_deg",
            0.0,
        ),
        direct_normal_radiation_w_m2=_row_value(
            row,
            "direct_normal_radiation_w_m2",
            0.0,
        ),
        diffuse_horizontal_radiation_w_m2=_row_value(
            row,
            "diffuse_horizontal_radiation_w_m2",
            0.0,
        ),
        global_horizontal_radiation_w_m2=_row_value(
            row,
            "global_horizontal_radiation_w_m2",
            0.0,
        ),
        outdoor_illuminance_lux=_row_value(
            row,
            "outdoor_illuminance_lux",
            0.0,
        ),
        sky_condition=_row_value(
            row,
            "sky_condition",
            DEFAULT_SKY_CONDITION,
        ),
        outdoor_co2_ppm=_row_value(
            row,
            "outdoor_co2_ppm",
            DEFAULT_OUTDOOR_CO2_PPM,
        ),
        outdoor_noise_db=_row_value(
            row,
            "outdoor_noise_db",
            DEFAULT_OUTDOOR_NOISE_DB,
        ),
        relative_humidity_percent=_optional_row_value(
            row,
            "relative_humidity_percent",
        ),
        atmospheric_pressure_pa=_optional_row_value(
            row,
            "atmospheric_pressure_pa",
        ),
    )


def _row_value(row: Any, key: str, default: Any = None) -> Any:
    if key not in row:
        return default

    value = row[key]

    if pd.isna(value):
        return default

    return value


def _optional_row_value(row: Any, key: str) -> Any:
    if key not in row:
        return None

    value = row[key]

    if pd.isna(value):
        return None

    return value


def load_epw_weather_timeseries(
    epw_path: str,
    is_tmy: bool = True,
    year: Optional[int] = None,
) -> WeatherTimeSeries:
    """
    Load an EPW file into ABBEY's internal weather table.

    EPW data are hourly.
    Timestamp convention:
        EPW hour 1 becomes 00:00
        EPW hour 24 becomes 23:00

    This creates hourly boundary-condition records.
    No interpolation is performed here.
    """

    if epw_path is None or not str(epw_path).strip():
        raise ValueError("epw_path cannot be empty.")

    epw_path = str(epw_path)

    if not os.path.exists(epw_path):
        raise FileNotFoundError("EPW file not found: " + epw_path)

    with open(epw_path, "r", encoding="utf-8", errors="ignore") as handle:
        header_lines = [handle.readline().strip() for _ in range(8)]

    metadata = _parse_epw_metadata(
        epw_path=epw_path,
        header_lines=header_lines,
        is_tmy=is_tmy,
        year=year,
    )

    raw_df = pd.read_csv(
        epw_path,
        skiprows=8,
        header=None,
        names=EPW_COLUMNS,
    )

    hourly_df = _extract_clean_epw_hourly_dataframe(
        raw_df=raw_df,
        metadata=metadata,
    )

    weather_series = WeatherTimeSeries(
        metadata=metadata,
        hourly_dataframe=hourly_df,
        raw_dataframe=raw_df,
        raw_header_lines=header_lines,
    )

    weather_series = preprocess_radiation_and_daylight(weather_series)
    weather_series = preprocess_wind(weather_series)
    weather_series = apply_outdoor_boundary_defaults(weather_series)

    return weather_series

def _parse_epw_metadata(
    epw_path: str,
    header_lines: List[str],
    is_tmy: bool,
    year: Optional[int],
) -> WeatherSourceMetadata:
    if not header_lines:
        raise ValueError("EPW header is empty.")

    location_line = header_lines[0]

    parts = location_line.split(",")

    if len(parts) < 10 or parts[0].strip().upper() != "LOCATION":
        raise ValueError(
            "Invalid EPW LOCATION header. First line was: " + location_line
        )

    location_name = parts[1].strip()

    latitude = _optional_float(parts[6])
    longitude = _optional_float(parts[7])
    timezone = _optional_float(parts[8])
    elevation_m = _optional_float(parts[9])

    # TMY EPW files may contain non-continuous historical years.
    # For ABBEY, force them into one representative non-leap year.
    if is_tmy and year is None:
        year = 2021

    return WeatherSourceMetadata(
        source_type="epw",
        source_path=epw_path,
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        elevation_m=elevation_m,
        year=year,
        is_tmy=is_tmy,
        data_timestep_minutes=60,
    )
def _extract_clean_epw_hourly_dataframe(
    raw_df: Any,
    metadata: WeatherSourceMetadata,
) -> Any:
    df = pd.DataFrame()

    df["datetime"] = _make_epw_datetimes(
        raw_df=raw_df,
        metadata=metadata,
    )

    df["outdoor_temperature_c"] = _numeric_column(
        raw_df,
        "dry_bulb_temperature_c",
    )

    df["relative_humidity_percent"] = _numeric_column(
        raw_df,
        "relative_humidity_percent",
    )

    df["atmospheric_pressure_pa"] = _numeric_column(
        raw_df,
        "atmospheric_pressure_pa",
    )

    df["wind_speed_m_s"] = _numeric_column(
        raw_df,
        "wind_speed_m_s",
    )

    df["wind_direction_deg"] = _numeric_column(
        raw_df,
        "wind_direction_deg",
    ).apply(normalize_orientation_deg)

    df["direct_normal_radiation_w_m2"] = _numeric_column(
        raw_df,
        "direct_normal_radiation_w_m2",
    )

    df["diffuse_horizontal_radiation_w_m2"] = _numeric_column(
        raw_df,
        "diffuse_horizontal_radiation_w_m2",
    )

    df["global_horizontal_radiation_w_m2"] = _numeric_column(
        raw_df,
        "global_horizontal_radiation_w_m2",
    )

    df["global_horizontal_illuminance_lux"] = _numeric_column(
        raw_df,
        "global_horizontal_illuminance_lux",
    )

    df["direct_normal_illuminance_lux"] = _numeric_column(
        raw_df,
        "direct_normal_illuminance_lux",
    )

    df["diffuse_horizontal_illuminance_lux"] = _numeric_column(
        raw_df,
        "diffuse_horizontal_illuminance_lux",
    )

    df["total_sky_cover_tenths"] = _numeric_column(
        raw_df,
        "total_sky_cover_tenths",
    )

    df["opaque_sky_cover_tenths"] = _numeric_column(
        raw_df,
        "opaque_sky_cover_tenths",
    )

    return df

def preprocess_radiation_and_daylight(
    weather_series: WeatherTimeSeries,
    night_radiation_threshold_w_m2: float = DEFAULT_NIGHT_RADIATION_THRESHOLD_W_M2,
    estimate_illuminance_if_missing: bool = True,
    luminous_efficacy_lux_per_w_m2: float = DEFAULT_LUMINOUS_EFFICACY_LUX_PER_W_M2,
) -> WeatherTimeSeries:
    """
    Clean radiation and daylight fields.

    This does not calculate zone solar gains.
    This does not calculate indoor daylight.
    It only prepares outside boundary inputs.
    """

    df = weather_series.hourly_dataframe.copy()

    for column in RADIATION_COLUMNS:
        df[column] = _clean_non_negative_series(df[column])

    for column in ILLUMINANCE_COLUMNS:
        if column in df.columns:
            df[column] = _clean_non_negative_series(df[column])

    df["is_night"] = _detect_night_hours(
        df=df,
        night_radiation_threshold_w_m2=night_radiation_threshold_w_m2,
    )

    for column in RADIATION_COLUMNS:
        df.loc[df["is_night"], column] = 0.0

    for column in ILLUMINANCE_COLUMNS:
        if column in df.columns:
            df.loc[df["is_night"], column] = 0.0

    df["outdoor_illuminance_lux"] = _make_outdoor_illuminance_lux(
        df=df,
        estimate_if_missing=estimate_illuminance_if_missing,
        luminous_efficacy_lux_per_w_m2=luminous_efficacy_lux_per_w_m2,
    )

    df["outdoor_illuminance_lux"] = _clean_non_negative_series(
        df["outdoor_illuminance_lux"]
    )

    df.loc[df["is_night"], "outdoor_illuminance_lux"] = 0.0

    if "sky_condition" not in df.columns:
        df["sky_condition"] = _make_sky_condition(df)

    return weather_series.copy(hourly_dataframe=df)

def preprocess_wind(
    weather_series: WeatherTimeSeries,
    calm_wind_speed_m_s: float = DEFAULT_CALM_WIND_SPEED_M_S,
    default_wind_direction_deg: float = DEFAULT_WIND_DIRECTION_DEG,
) -> WeatherTimeSeries:
    """
    Clean wind speed and wind direction.

    Direction convention:
        0°   = North
        90°  = East
        180° = South
        270° = West

    This does not calculate airflow.
    It only prepares wind boundary inputs for later airflow modules.
    """

    df = weather_series.hourly_dataframe.copy()

    df["wind_speed_m_s"] = _clean_wind_speed_series(
        df["wind_speed_m_s"]
    )

    raw_direction = _clean_wind_direction_series(
        df["wind_direction_deg"]
    )

    df["wind_is_calm"] = df["wind_speed_m_s"] <= float(calm_wind_speed_m_s)

    df["wind_direction_available"] = raw_direction.notna()

    # For non-calm missing wind directions, use nearest available direction.
    direction = raw_direction.copy()
    direction = direction.ffill()
    direction = direction.bfill()
    direction = direction.fillna(default_wind_direction_deg)

    direction = direction.apply(normalize_orientation_deg)

    # For calm periods, direction is physically weak/irrelevant.
    # Still assign a valid angle so downstream code never sees NaN.
    direction.loc[df["wind_is_calm"]] = normalize_orientation_deg(
        default_wind_direction_deg
    )

    df["wind_direction_deg"] = direction

    (
        df["wind_direction_sin"],
        df["wind_direction_cos"],
    ) = _wind_direction_unit_components(df["wind_direction_deg"])

    (
        df["wind_vector_east_m_s"],
        df["wind_vector_north_m_s"],
    ) = _wind_velocity_components(
        wind_speed_m_s=df["wind_speed_m_s"],
        wind_direction_deg=df["wind_direction_deg"],
    )

    return weather_series.copy(hourly_dataframe=df)

def apply_outdoor_boundary_defaults(
    weather_series: WeatherTimeSeries,
    defaults: Optional[OutdoorBoundaryDefaults] = None,
) -> WeatherTimeSeries:
    """
    Add outside boundary defaults to the weather dataframe.

    Adds:
    - outdoor_co2_ppm
    - outdoor_noise_db
    - sky_condition if missing
    - optional outdoor_noise_class
    - optional outdoor_pollution_index

    No CO2 solver.
    No acoustic solver.
    No pollution solver.
    """

    if defaults is None:
        defaults = OutdoorBoundaryDefaults()

    df = weather_series.hourly_dataframe.copy()

    if "outdoor_co2_ppm" not in df.columns:
        df["outdoor_co2_ppm"] = defaults.outdoor_co2_ppm
    else:
        df["outdoor_co2_ppm"] = pd.to_numeric(
            df["outdoor_co2_ppm"],
            errors="coerce",
        ).fillna(defaults.outdoor_co2_ppm)

        df.loc[df["outdoor_co2_ppm"] <= 0.0, "outdoor_co2_ppm"] = (
            defaults.outdoor_co2_ppm
        )

    if "outdoor_noise_db" not in df.columns:
        df["outdoor_noise_db"] = defaults.outdoor_noise_db
    else:
        df["outdoor_noise_db"] = pd.to_numeric(
            df["outdoor_noise_db"],
            errors="coerce",
        ).fillna(defaults.outdoor_noise_db)

        df.loc[df["outdoor_noise_db"] < 0.0, "outdoor_noise_db"] = (
            defaults.outdoor_noise_db
        )

    if "sky_condition" not in df.columns:
        df["sky_condition"] = defaults.sky_condition
    else:
        df["sky_condition"] = df["sky_condition"].fillna(defaults.sky_condition)
        df["sky_condition"] = df["sky_condition"].apply(
            lambda value: str(value).strip().lower()
            if str(value).strip()
            else defaults.sky_condition
        )

    if defaults.outdoor_noise_class is not None:
        df["outdoor_noise_class"] = defaults.outdoor_noise_class

    if defaults.outdoor_pollution_index is not None:
        df["outdoor_pollution_index"] = defaults.outdoor_pollution_index

    return weather_series.copy(hourly_dataframe=df)

def interpolate_weather_to_timestep(
    weather_series: WeatherTimeSeries,
    dt_minutes: int,
    allow_extrapolation: bool = False,
) -> WeatherTimeSeries:
    """
    Interpolate hourly weather data to ABBEY simulation timestep.

    Handles:
    - normal linear interpolation for scalar fields
    - circular interpolation for wind direction
    - non-negative clamping for radiation, illuminance, wind speed, CO2, noise
    - timestep dataframe generation

    No building physics.
    No solar gain calculation.
    No indoor daylight calculation.
    """

    dt_minutes = int(dt_minutes)

    if dt_minutes not in SUPPORTED_WEATHER_TIMESTEPS_MINUTES:
        raise ValueError(
            "Unsupported weather timestep {} minutes. Supported values are {}.".format(
                dt_minutes,
                sorted(SUPPORTED_WEATHER_TIMESTEPS_MINUTES),
            )
        )

    hourly_df = weather_series.hourly_dataframe.copy()

    if "datetime" not in hourly_df.columns:
        raise ValueError(
            "Weather hourly dataframe must contain a 'datetime' column."
        )

    hourly_df["datetime"] = pd.to_datetime(hourly_df["datetime"])
    hourly_df = hourly_df.sort_values("datetime")
    hourly_df = hourly_df.drop_duplicates(subset=["datetime"], keep="first")

    if dt_minutes == int(weather_series.metadata.data_timestep_minutes):
        timestep_df = hourly_df.copy()
        timestep_df = _finalize_interpolated_weather_dataframe(timestep_df)

        return weather_series.copy(
            timestep_dataframe=timestep_df,
        )

    start_time = hourly_df["datetime"].iloc[0]
    end_time = hourly_df["datetime"].iloc[-1]

    timestep_index = pd.date_range(
        start=start_time,
        end=end_time,
        freq=str(dt_minutes) + "min",
    )

    source_df = hourly_df.set_index("datetime")
    source_df = _prepare_wind_direction_components_for_interpolation(source_df)

    combined_index = source_df.index.union(timestep_index)
    work_df = source_df.reindex(combined_index).sort_index()

    for column in LINEAR_INTERPOLATION_COLUMNS:
        if column not in work_df.columns:
            continue

        work_df[column] = pd.to_numeric(
            work_df[column],
            errors="coerce",
        )

        work_df[column] = work_df[column].interpolate(
            method="time",
            limit_area="inside",
        )

        if allow_extrapolation:
            work_df[column] = work_df[column].ffill()
            work_df[column] = work_df[column].bfill()

    work_df = _interpolate_wind_direction_circularly(
        work_df=work_df,
        allow_extrapolation=allow_extrapolation,
    )

    for column in CATEGORICAL_WEATHER_COLUMNS:
        if column not in work_df.columns:
            continue

        work_df[column] = work_df[column].ffill()
        work_df[column] = work_df[column].bfill()

    timestep_df = work_df.loc[timestep_index].reset_index()
    timestep_df = timestep_df.rename(columns={"index": "datetime"})

    if not allow_extrapolation:
        _raise_if_interpolation_has_missing_core_values(timestep_df)

    timestep_df = _finalize_interpolated_weather_dataframe(timestep_df)

    return weather_series.copy(
        timestep_dataframe=timestep_df,
    )

def _prepare_wind_direction_components_for_interpolation(source_df: Any) -> Any:
    df = source_df.copy()

    if "wind_direction_sin" in df.columns and "wind_direction_cos" in df.columns:
        return df

    if "wind_direction_deg" not in df.columns:
        raise ValueError(
            "Weather dataframe must contain wind_direction_deg."
        )

    direction = pd.to_numeric(
        df["wind_direction_deg"],
        errors="coerce",
    )

    direction = direction.apply(
        lambda value: normalize_orientation_deg(value)
        if pd.notna(value)
        else np.nan
    )

    radians = np.deg2rad(direction.astype(float))

    df["wind_direction_sin"] = np.sin(radians)
    df["wind_direction_cos"] = np.cos(radians)

    return df


def _interpolate_wind_direction_circularly(
    work_df: Any,
    allow_extrapolation: bool,
) -> Any:
    if "wind_direction_sin" not in work_df.columns:
        raise ValueError(
            "Missing wind_direction_sin for circular interpolation."
        )

    if "wind_direction_cos" not in work_df.columns:
        raise ValueError(
            "Missing wind_direction_cos for circular interpolation."
        )

    work_df["wind_direction_sin"] = pd.to_numeric(
        work_df["wind_direction_sin"],
        errors="coerce",
    ).interpolate(
        method="time",
        limit_area="inside",
    )

    work_df["wind_direction_cos"] = pd.to_numeric(
        work_df["wind_direction_cos"],
        errors="coerce",
    ).interpolate(
        method="time",
        limit_area="inside",
    )

    if allow_extrapolation:
        work_df["wind_direction_sin"] = work_df["wind_direction_sin"].ffill()
        work_df["wind_direction_sin"] = work_df["wind_direction_sin"].bfill()

        work_df["wind_direction_cos"] = work_df["wind_direction_cos"].ffill()
        work_df["wind_direction_cos"] = work_df["wind_direction_cos"].bfill()

    radians = np.arctan2(
        work_df["wind_direction_sin"].astype(float),
        work_df["wind_direction_cos"].astype(float),
    )

    direction_deg = np.rad2deg(radians)

    work_df["wind_direction_deg"] = pd.Series(
        direction_deg,
        index=work_df.index,
    ).apply(normalize_orientation_deg)

    return work_df


def _raise_if_interpolation_has_missing_core_values(timestep_df: Any) -> None:
    core_columns = [
        "outdoor_temperature_c",
        "wind_speed_m_s",
        "wind_direction_deg",
        "direct_normal_radiation_w_m2",
        "diffuse_horizontal_radiation_w_m2",
        "global_horizontal_radiation_w_m2",
        "outdoor_illuminance_lux",
        "outdoor_co2_ppm",
        "outdoor_noise_db",
    ]

    missing = []

    for column in core_columns:
        if column not in timestep_df.columns:
            missing.append(column)
            continue

        if timestep_df[column].isna().any():
            missing.append(column)

    if missing:
        raise ValueError(
            "Interpolated weather contains missing core values. "
            "Missing/NaN columns: "
            + str(missing)
            + ". Use allow_extrapolation=True only if this is intentional."
        )


def _finalize_interpolated_weather_dataframe(df: Any) -> Any:
    df = df.copy()

    for column in NON_NEGATIVE_INTERPOLATED_COLUMNS:
        if column not in df.columns:
            continue

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        ).fillna(0.0)

        df[column] = df[column].clip(lower=0.0)

    if "wind_direction_deg" in df.columns:
        df["wind_direction_deg"] = df["wind_direction_deg"].apply(
            normalize_orientation_deg
        )

    if "wind_speed_m_s" in df.columns:
        df["wind_is_calm"] = (
            df["wind_speed_m_s"] <= DEFAULT_CALM_WIND_SPEED_M_S
        )

    if (
        "wind_direction_deg" in df.columns
        and "wind_speed_m_s" in df.columns
    ):
        (
            df["wind_direction_sin"],
            df["wind_direction_cos"],
        ) = _wind_direction_unit_components(df["wind_direction_deg"])

        (
            df["wind_vector_east_m_s"],
            df["wind_vector_north_m_s"],
        ) = _wind_velocity_components(
            wind_speed_m_s=df["wind_speed_m_s"],
            wind_direction_deg=df["wind_direction_deg"],
        )

    if all(column in df.columns for column in RADIATION_COLUMNS):
        df["is_night"] = _detect_night_hours(
            df=df,
            night_radiation_threshold_w_m2=DEFAULT_NIGHT_RADIATION_THRESHOLD_W_M2,
        )

        for column in RADIATION_COLUMNS:
            df.loc[df["is_night"], column] = 0.0

        for column in ILLUMINANCE_COLUMNS:
            if column in df.columns:
                df.loc[df["is_night"], column] = 0.0

        if "outdoor_illuminance_lux" in df.columns:
            df.loc[df["is_night"], "outdoor_illuminance_lux"] = 0.0

    if "sky_condition" not in df.columns:
        df["sky_condition"] = DEFAULT_SKY_CONDITION
    else:
        df["sky_condition"] = df["sky_condition"].fillna(DEFAULT_SKY_CONDITION)
        df["sky_condition"] = df["sky_condition"].apply(
            lambda value: str(value).strip().lower()
            if str(value).strip()
            else DEFAULT_SKY_CONDITION
        )

    return df

def _clean_wind_speed_series(series: Any) -> Any:
    cleaned = pd.to_numeric(series, errors="coerce")

    # EPW missing values can appear as very large placeholders.
    cleaned = cleaned.where(cleaned < 900000.0)

    cleaned = cleaned.fillna(0.0)
    cleaned = cleaned.clip(lower=0.0)

    return cleaned


def _clean_wind_direction_series(series: Any) -> Any:
    cleaned = pd.to_numeric(series, errors="coerce")

    # EPW missing values can appear as very large placeholders.
    cleaned = cleaned.where(cleaned < 900000.0)

    cleaned = cleaned.where(cleaned.notna())

    return cleaned.apply(
        lambda value: normalize_orientation_deg(value)
        if pd.notna(value)
        else np.nan
    )


def _wind_direction_unit_components(direction_deg: Any):
    """
    Convert wind direction angle to circular interpolation components.

    With ABBEY convention:
        0°   = North
        90°  = East

    east component  = sin(theta)
    north component = cos(theta)
    """

    radians = np.deg2rad(direction_deg.astype(float))

    direction_sin = np.sin(radians)
    direction_cos = np.cos(radians)

    return direction_sin, direction_cos


def _wind_velocity_components(
    wind_speed_m_s: Any,
    wind_direction_deg: Any,
):
    """
    Create wind vector components.

    These are useful later for wind-facing façade/opening logic.
    """

    radians = np.deg2rad(wind_direction_deg.astype(float))

    east = wind_speed_m_s.astype(float) * np.sin(radians)
    north = wind_speed_m_s.astype(float) * np.cos(radians)

    return east, north

def _clean_non_negative_series(series: Any) -> Any:
    cleaned = pd.to_numeric(series, errors="coerce")

    # EPW missing values can appear as very large placeholders.
    cleaned = cleaned.where(cleaned < 900000.0)

    cleaned = cleaned.fillna(0.0)
    cleaned = cleaned.clip(lower=0.0)

    return cleaned


def _detect_night_hours(
    df: Any,
    night_radiation_threshold_w_m2: float,
) -> Any:
    total_radiation = (
        df["direct_normal_radiation_w_m2"]
        + df["diffuse_horizontal_radiation_w_m2"]
        + df["global_horizontal_radiation_w_m2"]
    )

    return total_radiation <= float(night_radiation_threshold_w_m2)


def _make_outdoor_illuminance_lux(
    df: Any,
    estimate_if_missing: bool,
    luminous_efficacy_lux_per_w_m2: float,
) -> Any:
    if "global_horizontal_illuminance_lux" in df.columns:
        illuminance = pd.to_numeric(
            df["global_horizontal_illuminance_lux"],
            errors="coerce",
        )

        illuminance = illuminance.where(illuminance < 900000.0)

        if illuminance.notna().any() and illuminance.max() > 0.0:
            return illuminance.fillna(0.0)

    if not estimate_if_missing:
        return pd.Series(0.0, index=df.index)

    return (
        df["global_horizontal_radiation_w_m2"]
        * float(luminous_efficacy_lux_per_w_m2)
    )


def _make_sky_condition(df: Any) -> Any:
    if "total_sky_cover_tenths" not in df.columns:
        return pd.Series("unknown", index=df.index)

    cover = pd.to_numeric(
        df["total_sky_cover_tenths"],
        errors="coerce",
    ).fillna(-1)

    def classify(value):
        if value < 0:
            return "unknown"

        if value <= 2:
            return "clear"

        if value <= 6:
            return "partly_cloudy"

        if value <= 9:
            return "cloudy"

        return "overcast"

    return cover.apply(classify)


def _make_epw_datetimes(
    raw_df: Any,
    metadata: WeatherSourceMetadata,
) -> List[DateTime]:
    datetimes = []
    if metadata.timezone is None:
        raise ValueError("EPW LOCATION header must declare a UTC offset.")
    source_timezone = timezone(timedelta(hours=float(metadata.timezone)))

    for _, row in raw_df.iterrows():
        epw_year = int(row["year"])
        month = int(row["month"])
        day = int(row["day"])
        epw_hour = int(row["hour"])

        if metadata.year is not None:
            used_year = int(metadata.year)
        else:
            used_year = epw_year

        # EPW hour convention:
        # 1 means 00:00-01:00, so we store timestamp as 00:00.
        hour = epw_hour - 1

        if hour < 0:
            hour = 0

        if hour > 23:
            hour = 23

        datetimes.append(
            DateTime(
                year=used_year,
                month=month,
                day=day,
                hour=hour,
                minute=0,
                second=0,
                tzinfo=source_timezone,
            )
        )

    return datetimes

def _numeric_column(raw_df: Any, column_name: str) -> Any:
    if column_name not in raw_df.columns:
        raise ValueError(
            "Missing EPW column: " + column_name
        )

    return pd.to_numeric(
        raw_df[column_name],
        errors="coerce",
    )


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    try:
        return float(value)
    except Exception:
        return None
    
    
def _normalize_datetime(value: Any) -> DateTime:
    if isinstance(value, DateTime):
        return value

    if isinstance(value, str):
        return DateTime.fromisoformat(value)

    raise ValueError(
        "WeatherState.datetime must be a datetime object or ISO datetime string."
    )


def _non_negative_float(value: float, field_name: str) -> float:
    value = float(value)

    if value < 0.0:
        raise ValueError(field_name + " cannot be negative. Got: " + str(value))

    return value


def _positive_float(value: float, field_name: str) -> float:
    value = float(value)

    if value <= 0.0:
        raise ValueError(field_name + " must be positive. Got: " + str(value))

    return value


def _clamp(value: float, minimum: float, maximum: float) -> float:
    value = float(value)

    if value < minimum:
        return minimum

    if value > maximum:
        return maximum

    return value
