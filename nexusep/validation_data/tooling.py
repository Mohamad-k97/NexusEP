"""Domain-neutral tooling for aligned, provenance-backed model validation."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

ResampleSemantic = Literal["state", "rate", "interval_total"]
ResidualSemantic = Literal[
    "none", "rate_per_second", "rate_per_hour", "interval_total"
]
TOOLING_VERSION = "1.0.0"


@dataclass(frozen=True)
class ProvenanceRecord:
    tooling_version: str
    operation: str
    input_sha256: str
    output_sha256: str
    parameters_json: str


@dataclass(frozen=True)
class TimestampNormalizationResult:
    timestamps: pd.DatetimeIndex
    provenance: ProvenanceRecord


@dataclass(frozen=True)
class ResampleResult:
    data: pd.DataFrame
    coverage_fraction: pd.DataFrame
    provenance: ProvenanceRecord


@dataclass(frozen=True)
class UnitConversionResult:
    values: float | np.ndarray | pd.Series
    from_unit: str
    to_unit: str
    provenance: ProvenanceRecord


@dataclass(frozen=True)
class MissingDataResult:
    mask: pd.DataFrame
    valid_rows: pd.Series
    missing_counts: pd.Series
    provenance: ProvenanceRecord


@dataclass(frozen=True)
class WarmupExclusionResult:
    data: pd.DataFrame
    excluded_rows: pd.Series
    provenance: ProvenanceRecord


@dataclass(frozen=True)
class AlignmentResult:
    data: pd.DataFrame
    quantities: tuple[str, ...]
    provenance: ProvenanceRecord


@dataclass(frozen=True)
class CalibrationValidationSplit:
    calibration_mask: pd.Series
    validation_mask: pd.Series
    excluded_mask: pd.Series
    provenance: ProvenanceRecord


@dataclass(frozen=True)
class UncertaintyPropagationResult:
    standard_uncertainty: float | np.ndarray
    provenance: ProvenanceRecord


@dataclass(frozen=True)
class ValidationMetrics:
    quantity_unit: str
    count: int
    excluded_count: int
    bias: float
    normalized_bias: float
    mae: float
    rmse: float
    measured_peak: float
    simulated_peak: float
    peak_error: float
    peak_timing_error_minutes: float
    cumulative_residual: float
    cumulative_residual_unit: str | None
    correlation: float
    measured_uncertainty_coverage: float
    measured_event_count: int | None
    simulated_event_count: int | None
    event_frequency_error: int | None
    measured_event_duration_minutes: float | None
    simulated_event_duration_minutes: float | None
    event_duration_error_minutes: float | None

    def to_dict(self) -> dict[str, int | float | str | None]:
        return asdict(self)


@dataclass(frozen=True)
class MetricResult:
    metrics: ValidationMetrics
    provenance: ProvenanceRecord


@dataclass(frozen=True)
class MetricTableResult:
    table: pd.DataFrame
    provenance: ProvenanceRecord


@dataclass(frozen=True)
class PlotResult:
    figure: Figure
    provenance: ProvenanceRecord


def _json_default(value: object) -> object:
    if isinstance(value, (pd.Timestamp, pd.Timedelta)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"cannot serialize provenance value {type(value).__name__}")


def _canonical_json(value: object) -> str:
    def make_safe(item: object) -> object:
        if isinstance(item, Mapping):
            return {str(key): make_safe(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [make_safe(child) for child in item]
        if isinstance(item, (float, np.floating)) and not math.isfinite(float(item)):
            if math.isnan(float(item)):
                return {"nonfinite_float": "nan"}
            return {"nonfinite_float": "inf" if float(item) > 0 else "-inf"}
        return item

    return json.dumps(
        make_safe(value),
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
        allow_nan=False,
    )


def content_sha256(value: object) -> str:
    """Hash values with indexes, column order, dtypes, and missingness preserved."""

    digest = hashlib.sha256()
    if isinstance(value, pd.DataFrame):
        metadata = {
            "kind": "dataframe",
            "columns": [str(item) for item in value.columns],
            "dtypes": [str(item) for item in value.dtypes],
            "index_name": str(value.index.name),
            "index_dtype": str(value.index.dtype),
        }
        digest.update(_canonical_json(metadata).encode())
        digest.update(pd.util.hash_pandas_object(value, index=True).values.tobytes())
        return digest.hexdigest()
    if isinstance(value, pd.Series):
        metadata = {
            "kind": "series",
            "name": str(value.name),
            "dtype": str(value.dtype),
            "index_name": str(value.index.name),
            "index_dtype": str(value.index.dtype),
        }
        digest.update(_canonical_json(metadata).encode())
        digest.update(pd.util.hash_pandas_object(value, index=True).values.tobytes())
        return digest.hexdigest()
    if isinstance(value, pd.DatetimeIndex):
        metadata = {
            "kind": "datetime_index",
            "name": str(value.name),
            "timezone": str(value.tz),
        }
        digest.update(_canonical_json(metadata).encode())
        digest.update(value.asi8.tobytes())
        return digest.hexdigest()
    if isinstance(value, np.ndarray):
        array = np.asarray(value)
        digest.update(
            _canonical_json(
                {"kind": "ndarray", "dtype": str(array.dtype), "shape": array.shape}
            ).encode()
        )
        digest.update(array.tobytes())
        return digest.hexdigest()
    digest.update(_canonical_json(value).encode())
    return digest.hexdigest()


def _provenance(
    operation: str,
    input_value: object,
    output_value: object,
    parameters: Mapping[str, object],
) -> ProvenanceRecord:
    return ProvenanceRecord(
        tooling_version=TOOLING_VERSION,
        operation=operation,
        input_sha256=content_sha256(input_value),
        output_sha256=content_sha256(output_value),
        parameters_json=_canonical_json(dict(parameters)),
    )


def normalize_timestamps(
    values: Sequence[object] | pd.Series | pd.Index,
    *,
    source_timezone: str | None,
    target_timezone: str = "UTC",
    ambiguous: str | bool | np.ndarray = "raise",
    nonexistent: str = "raise",
    require_unique: bool = True,
    require_monotonic: bool = True,
) -> TimestampNormalizationResult:
    """Normalize timestamps without silently guessing the timezone or DST fold."""

    original = pd.DatetimeIndex(pd.to_datetime(values, errors="raise"))
    timestamps = original
    if timestamps.tz is None:
        if not source_timezone:
            raise ValueError("source_timezone is required for naive timestamps")
        timestamps = timestamps.tz_localize(
            source_timezone, ambiguous=ambiguous, nonexistent=nonexistent
        )
    elif source_timezone and str(timestamps.tz) != source_timezone:
        raise ValueError(
            f"aware timestamps use {timestamps.tz}, not source_timezone "
            f"{source_timezone}"
        )
    timestamps = timestamps.tz_convert(target_timezone)
    if require_unique and timestamps.has_duplicates:
        duplicates = timestamps[timestamps.duplicated()].astype(str).tolist()
        raise ValueError(f"duplicate normalized timestamps: {duplicates}")
    if require_monotonic and not timestamps.is_monotonic_increasing:
        raise ValueError("timestamps must be monotonic increasing")
    provenance = _provenance(
        "normalize_timestamps",
        original,
        timestamps,
        {
            "source_timezone": source_timezone,
            "target_timezone": target_timezone,
            "ambiguous": str(ambiguous),
            "nonexistent": nonexistent,
            "require_unique": require_unique,
            "require_monotonic": require_monotonic,
        },
    )
    return TimestampNormalizationResult(timestamps=timestamps, provenance=provenance)


def _positive_fixed_interval(value: str | pd.Timedelta, name: str) -> pd.Timedelta:
    interval = pd.Timedelta(value)
    if interval <= pd.Timedelta(0):
        raise ValueError(f"{name} must be positive")
    return interval


def conservative_resample(
    frame: pd.DataFrame,
    *,
    source_interval: str | pd.Timedelta,
    target_interval: str | pd.Timedelta,
    semantics: Mapping[str, ResampleSemantic],
) -> ResampleResult:
    """Resample interval-start data by exact overlap while preserving integrals."""

    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
        raise TypeError("frame must use a timezone-aware DatetimeIndex")
    if frame.empty:
        raise ValueError("frame cannot be empty")
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError("frame index must be unique and monotonic increasing")
    if set(semantics) != set(frame.columns):
        raise ValueError("semantics must declare exactly every frame column")
    unsupported = sorted(set(semantics.values()) - {"state", "rate", "interval_total"})
    if unsupported:
        raise ValueError(f"unsupported resampling semantics: {unsupported}")
    if any(not pd.api.types.is_numeric_dtype(frame[column]) for column in frame):
        raise TypeError("conservative resampling supports numeric columns only")

    source_dt = _positive_fixed_interval(source_interval, "source_interval")
    target_dt = _positive_fixed_interval(target_interval, "target_interval")
    differences = frame.index.to_series().diff().dropna()
    if not differences.empty and (differences < source_dt).any():
        raise ValueError("source intervals overlap")

    target_start = frame.index[0].floor(target_dt)
    source_end = frame.index[-1] + source_dt
    target_end = source_end.ceil(target_dt)
    if target_end == target_start:
        target_end += target_dt
    target_index = pd.date_range(
        target_start,
        target_end,
        freq=target_dt,
        inclusive="left",
        name=frame.index.name,
    )
    numerators = {
        column: np.zeros(len(target_index), dtype=float) for column in frame.columns
    }
    coverage_seconds = {
        column: np.zeros(len(target_index), dtype=float) for column in frame.columns
    }
    target_origin_ns = target_index[0].value
    source_seconds = source_dt.total_seconds()
    target_seconds = target_dt.total_seconds()
    target_ns = target_dt.value

    for timestamp, row in frame.iterrows():
        source_start_ns = timestamp.value
        source_end_ns = source_start_ns + source_dt.value
        first_bin = max(0, int((source_start_ns - target_origin_ns) // target_ns))
        last_bin = min(
            len(target_index) - 1,
            int((source_end_ns - 1 - target_origin_ns) // target_ns),
        )
        for bin_index in range(first_bin, last_bin + 1):
            bin_start_ns = target_origin_ns + bin_index * target_ns
            bin_end_ns = bin_start_ns + target_ns
            overlap_seconds = (
                min(source_end_ns, bin_end_ns) - max(source_start_ns, bin_start_ns)
            ) / 1_000_000_000.0
            if overlap_seconds <= 0.0:
                continue
            for column in frame.columns:
                raw_value = row[column]
                if pd.isna(raw_value):
                    continue
                value = float(raw_value)
                if not math.isfinite(value):
                    continue
                coverage_seconds[column][bin_index] += overlap_seconds
                if semantics[column] == "interval_total":
                    numerators[column][bin_index] += (
                        value * overlap_seconds / source_seconds
                    )
                else:
                    numerators[column][bin_index] += value * overlap_seconds

    output = pd.DataFrame(index=target_index)
    coverage = pd.DataFrame(index=target_index)
    for column in frame.columns:
        covered = coverage_seconds[column]
        coverage[column] = np.clip(covered / target_seconds, 0.0, 1.0)
        if semantics[column] == "interval_total":
            output[column] = numerators[column]
            output.loc[covered == 0.0, column] = np.nan
        else:
            output[column] = np.divide(
                numerators[column],
                covered,
                out=np.full(len(target_index), np.nan),
                where=covered > 0.0,
            )

    provenance = _provenance(
        "conservative_resample",
        frame,
        output,
        {
            "source_interval": source_dt,
            "target_interval": target_dt,
            "semantics": dict(semantics),
            "coverage_sha256": content_sha256(coverage),
        },
    )
    return ResampleResult(
        data=output, coverage_fraction=coverage, provenance=provenance
    )


_UNIT_DEFINITIONS: dict[str, tuple[str, float, float]] = {
    "K": ("temperature", 1.0, 0.0),
    "degC": ("temperature", 1.0, 273.15),
    "degF": ("temperature", 5.0 / 9.0, 255.3722222222222),
    "W": ("power", 1.0, 0.0),
    "kW": ("power", 1000.0, 0.0),
    "J": ("energy", 1.0, 0.0),
    "Wh": ("energy", 3600.0, 0.0),
    "kWh": ("energy", 3_600_000.0, 0.0),
    "kg/s": ("mass_flow", 1.0, 0.0),
    "kg/h": ("mass_flow", 1.0 / 3600.0, 0.0),
    "m3/s": ("volume_flow", 1.0, 0.0),
    "m3/h": ("volume_flow", 1.0 / 3600.0, 0.0),
    "Pa": ("pressure", 1.0, 0.0),
    "kPa": ("pressure", 1000.0, 0.0),
    "fraction": ("ratio", 1.0, 0.0),
    "%": ("ratio", 0.01, 0.0),
    "ppm": ("ratio", 1.0e-6, 0.0),
    "s": ("duration", 1.0, 0.0),
    "min": ("duration", 60.0, 0.0),
    "h": ("duration", 3600.0, 0.0),
    "rad": ("angle", 1.0, 0.0),
    "deg": ("angle", math.pi / 180.0, 0.0),
}


def convert_units(
    values: float | Sequence[float] | np.ndarray | pd.Series,
    *,
    from_unit: str,
    to_unit: str,
) -> UnitConversionResult:
    """Convert supported public units and reject cross-quantity conversions."""

    if from_unit not in _UNIT_DEFINITIONS or to_unit not in _UNIT_DEFINITIONS:
        raise ValueError(f"unsupported unit conversion: {from_unit} -> {to_unit}")
    from_dimension, from_scale, from_offset = _UNIT_DEFINITIONS[from_unit]
    to_dimension, to_scale, to_offset = _UNIT_DEFINITIONS[to_unit]
    if from_dimension != to_dimension:
        raise ValueError(
            f"incompatible units: {from_unit} ({from_dimension}) and "
            f"{to_unit} ({to_dimension})"
        )
    array = np.asarray(values, dtype=float)
    converted_array = (array * from_scale + from_offset - to_offset) / to_scale
    if isinstance(values, pd.Series):
        converted: float | np.ndarray | pd.Series = pd.Series(
            converted_array, index=values.index, name=values.name
        )
    elif np.isscalar(values):
        converted = float(converted_array)
    else:
        converted = converted_array
    provenance = _provenance(
        "convert_units",
        array,
        np.asarray(converted_array),
        {"from_unit": from_unit, "to_unit": to_unit, "dimension": from_dimension},
    )
    return UnitConversionResult(
        values=converted,
        from_unit=from_unit,
        to_unit=to_unit,
        provenance=provenance,
    )


def build_missing_data_mask(
    frame: pd.DataFrame,
    *,
    required_columns: Sequence[str],
    sentinels: Mapping[str, Sequence[object]] | None = None,
) -> MissingDataResult:
    """Create per-value and per-row masks without imputing measurements."""

    missing_columns = sorted(set(required_columns) - set(frame.columns))
    if missing_columns:
        raise KeyError(f"required columns are absent: {missing_columns}")
    selected = frame.loc[:, list(required_columns)]
    mask = selected.isna().copy()
    for column in selected.columns:
        if pd.api.types.is_numeric_dtype(selected[column]):
            mask[column] |= ~np.isfinite(selected[column].astype(float))
        for sentinel in (sentinels or {}).get(column, ()):
            mask[column] |= selected[column].eq(sentinel)
    valid_rows = ~mask.any(axis=1)
    missing_counts = mask.sum(axis=0).astype(int)
    provenance = _provenance(
        "build_missing_data_mask",
        selected,
        mask,
        {
            "required_columns": list(required_columns),
            "sentinels": {key: list(value) for key, value in (sentinels or {}).items()},
        },
    )
    return MissingDataResult(
        mask=mask,
        valid_rows=valid_rows,
        missing_counts=missing_counts,
        provenance=provenance,
    )


def exclude_warmup(
    frame: pd.DataFrame,
    *,
    duration: str | pd.Timedelta | None = None,
    rows: int | None = None,
) -> WarmupExclusionResult:
    """Exclude a declared leading duration or row count and record the choice."""

    if (duration is None) == (rows is None):
        raise ValueError("provide exactly one of duration or rows")
    if frame.empty:
        raise ValueError("frame cannot be empty")
    excluded = pd.Series(False, index=frame.index, name="warmup_excluded")
    if rows is not None:
        if rows < 0 or rows >= len(frame):
            raise ValueError("rows must be nonnegative and leave validation data")
        excluded.iloc[:rows] = True
        parameters: dict[str, object] = {"rows": rows}
    else:
        if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
            raise TypeError("duration-based warm-up requires a timezone-aware index")
        warmup = _positive_fixed_interval(duration, "duration")
        cutoff = frame.index[0] + warmup
        excluded.loc[frame.index < cutoff] = True
        if excluded.all():
            raise ValueError("duration excludes all validation data")
        parameters = {"duration": warmup, "cutoff": cutoff}
    output = frame.loc[~excluded].copy()
    provenance = _provenance(
        "exclude_warmup", frame, output, parameters
    )
    return WarmupExclusionResult(
        data=output, excluded_rows=excluded, provenance=provenance
    )


def _utc_frame(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
        raise TypeError(f"{label} must use a timezone-aware DatetimeIndex")
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError(f"{label} index must be unique and monotonic increasing")
    output = frame.copy()
    output.index = output.index.tz_convert("UTC")
    return output


def align_measurement_simulation(
    measured: pd.DataFrame,
    simulated: pd.DataFrame,
    *,
    quantities: Mapping[str, tuple[str, str]],
    uncertainty_columns: Mapping[str, str] | None = None,
    tolerance: str | pd.Timedelta = "0s",
    direction: Literal["nearest", "backward", "forward"] = "nearest",
) -> AlignmentResult:
    """Align simulation to measurement timestamps without hidden interpolation."""

    if not quantities:
        raise ValueError("at least one aligned quantity is required")
    measured_utc = _utc_frame(measured, "measured")
    simulated_utc = _utc_frame(simulated, "simulated")
    measured_columns = [item[0] for item in quantities.values()]
    simulated_columns = [item[1] for item in quantities.values()]
    if len(measured_columns) != len(set(measured_columns)) or len(
        simulated_columns
    ) != len(set(simulated_columns)):
        raise ValueError("each aligned quantity must use distinct source columns")
    uncertainty_columns = dict(uncertainty_columns or {})
    missing_measured = sorted(
        set(measured_columns + list(uncertainty_columns.values()))
        - set(measured_utc.columns)
    )
    missing_simulated = sorted(set(simulated_columns) - set(simulated_utc.columns))
    if missing_measured or missing_simulated:
        raise KeyError(
            f"alignment columns missing: measured={missing_measured}, "
            f"simulated={missing_simulated}"
        )
    tolerance_value = pd.Timedelta(tolerance)
    if tolerance_value < pd.Timedelta(0):
        raise ValueError("tolerance cannot be negative")

    left = measured_utc.loc[
        :, list(dict.fromkeys(measured_columns + list(uncertainty_columns.values())))
    ].copy()
    left.insert(0, "measurement_timestamp", measured_utc.index)
    right = simulated_utc.loc[:, simulated_columns].copy()
    right.insert(0, "simulation_timestamp", simulated_utc.index)
    right = right.rename(
        columns={column: f"_sim_{position}" for position, column in enumerate(simulated_columns)}
    )
    merged = pd.merge_asof(
        left.sort_values("measurement_timestamp"),
        right.sort_values("simulation_timestamp"),
        left_on="measurement_timestamp",
        right_on="simulation_timestamp",
        tolerance=tolerance_value,
        direction=direction,
        allow_exact_matches=True,
    )
    output = pd.DataFrame(index=pd.DatetimeIndex(merged["measurement_timestamp"]))
    output.index.name = measured.index.name or "timestamp"
    for position, (quantity, (measured_column, _)) in enumerate(quantities.items()):
        output[f"{quantity}_measured"] = merged[measured_column].to_numpy()
        output[f"{quantity}_simulated"] = merged[f"_sim_{position}"].to_numpy()
        if quantity in uncertainty_columns:
            output[f"{quantity}_uncertainty"] = merged[
                uncertainty_columns[quantity]
            ].to_numpy()
    output["simulation_timestamp"] = pd.DatetimeIndex(merged["simulation_timestamp"])
    output["time_offset_seconds"] = (
        output["simulation_timestamp"] - output.index
    ).dt.total_seconds()
    output["matched"] = output["simulation_timestamp"].notna()
    provenance = _provenance(
        "align_measurement_simulation",
        pd.concat(
            {"measured": measured_utc, "simulated": simulated_utc},
            axis=1,
            sort=False,
        ),
        output,
        {
            "quantities": {key: list(value) for key, value in quantities.items()},
            "uncertainty_columns": uncertainty_columns,
            "tolerance": tolerance_value,
            "direction": direction,
        },
    )
    return AlignmentResult(
        data=output,
        quantities=tuple(quantities),
        provenance=provenance,
    )


def calibration_validation_split(
    timestamps: pd.DatetimeIndex,
    *,
    calibration_end: str | pd.Timestamp,
    validation_start: str | pd.Timestamp | None = None,
) -> CalibrationValidationSplit:
    """Create deterministic, non-overlapping chronological fit/holdout masks."""

    if timestamps.tz is None or timestamps.has_duplicates:
        raise ValueError("timestamps must be timezone-aware and unique")
    if not timestamps.is_monotonic_increasing:
        raise ValueError("timestamps must be monotonic increasing")
    calibration_boundary = pd.Timestamp(calibration_end)
    if calibration_boundary.tzinfo is None:
        raise ValueError("calibration_end must be timezone-aware")
    calibration_boundary = calibration_boundary.tz_convert(timestamps.tz)
    validation_boundary = (
        calibration_boundary
        if validation_start is None
        else pd.Timestamp(validation_start)
    )
    if validation_boundary.tzinfo is None:
        raise ValueError("validation_start must be timezone-aware")
    validation_boundary = validation_boundary.tz_convert(timestamps.tz)
    if validation_boundary < calibration_boundary:
        raise ValueError("validation_start cannot precede calibration_end")
    calibration = pd.Series(
        timestamps < calibration_boundary,
        index=timestamps,
        name="calibration",
    )
    validation = pd.Series(
        timestamps >= validation_boundary,
        index=timestamps,
        name="validation",
    )
    excluded = ~(calibration | validation)
    excluded.name = "split_excluded"
    if not calibration.any() or not validation.any():
        raise ValueError("split must contain both calibration and validation samples")
    combined = pd.DataFrame(
        {"calibration": calibration, "validation": validation, "excluded": excluded}
    )
    provenance = _provenance(
        "calibration_validation_split",
        timestamps,
        combined,
        {
            "calibration_end": calibration_boundary,
            "validation_start": validation_boundary,
        },
    )
    return CalibrationValidationSplit(
        calibration_mask=calibration,
        validation_mask=validation,
        excluded_mask=excluded,
        provenance=provenance,
    )


def blocked_calibration_validation_split(
    timestamps: pd.DatetimeIndex,
    *,
    calibration_fraction: float,
    gap: str | pd.Timedelta = "0s",
) -> CalibrationValidationSplit:
    """Create a chronological split with an optional leakage-prevention gap."""

    if not 0.0 < calibration_fraction < 1.0:
        raise ValueError("calibration_fraction must be between zero and one")
    if len(timestamps) < 2:
        raise ValueError("at least two timestamps are required")
    boundary_index = min(
        len(timestamps) - 1,
        max(1, math.floor(len(timestamps) * calibration_fraction)),
    )
    gap_value = pd.Timedelta(gap)
    if gap_value < pd.Timedelta(0):
        raise ValueError("gap cannot be negative")
    validation_start = timestamps[boundary_index] + gap_value
    return calibration_validation_split(
        timestamps,
        calibration_end=timestamps[boundary_index],
        validation_start=validation_start,
    )


def propagate_uncertainty(
    standard_uncertainties: Sequence[float] | np.ndarray,
    *,
    sensitivities: Sequence[float] | np.ndarray | None = None,
    covariance: np.ndarray | None = None,
) -> UncertaintyPropagationResult:
    """Propagate standard uncertainties by the GUM first-order rule."""

    uncertainties = np.asarray(standard_uncertainties, dtype=float)
    if uncertainties.ndim != 1 or uncertainties.size == 0:
        raise ValueError("standard_uncertainties must be a nonempty vector")
    if not np.isfinite(uncertainties).all() or (uncertainties < 0.0).any():
        raise ValueError("standard_uncertainties must be finite and nonnegative")
    sensitivity = (
        np.ones_like(uncertainties)
        if sensitivities is None
        else np.asarray(sensitivities, dtype=float)
    )
    if sensitivity.shape != uncertainties.shape or not np.isfinite(sensitivity).all():
        raise ValueError("sensitivities must be finite and match uncertainties")
    if covariance is None:
        variance = float(np.sum(np.square(sensitivity * uncertainties)))
    else:
        covariance_array = np.asarray(covariance, dtype=float)
        expected_shape = (uncertainties.size, uncertainties.size)
        if covariance_array.shape != expected_shape:
            raise ValueError(f"covariance must have shape {expected_shape}")
        if not np.allclose(covariance_array, covariance_array.T):
            raise ValueError("covariance must be symmetric")
        if not np.allclose(np.diag(covariance_array), np.square(uncertainties)):
            raise ValueError(
                "covariance diagonal must equal squared standard_uncertainties"
            )
        if float(np.min(np.linalg.eigvalsh(covariance_array))) < -1e-12:
            raise ValueError("covariance must be positive semidefinite")
        variance = float(sensitivity @ covariance_array @ sensitivity)
    if variance < -1e-12:
        raise ValueError("propagated variance is negative")
    result = math.sqrt(max(0.0, variance))
    provenance = _provenance(
        "propagate_uncertainty",
        uncertainties,
        result,
        {
            "sensitivities": sensitivity.tolist(),
            "covariance": None if covariance is None else np.asarray(covariance).tolist(),
        },
    )
    return UncertaintyPropagationResult(
        standard_uncertainty=result, provenance=provenance
    )


def combine_independent_uncertainties(
    *standard_uncertainties: Sequence[float] | np.ndarray,
) -> UncertaintyPropagationResult:
    """Combine independent per-sample uncertainty arrays in quadrature."""

    if not standard_uncertainties:
        raise ValueError("at least one uncertainty array is required")
    arrays = [np.asarray(item, dtype=float) for item in standard_uncertainties]
    shape = arrays[0].shape
    if any(item.shape != shape for item in arrays):
        raise ValueError("all uncertainty arrays must have the same shape")
    stacked = np.stack(arrays)
    if not np.isfinite(stacked).all() or (stacked < 0.0).any():
        raise ValueError("uncertainties must be finite and nonnegative")
    combined = np.sqrt(np.sum(np.square(stacked), axis=0))
    provenance = _provenance(
        "combine_independent_uncertainties",
        stacked,
        combined,
        {"component_count": len(arrays)},
    )
    return UncertaintyPropagationResult(
        standard_uncertainty=combined, provenance=provenance
    )


def _event_summary(mask: np.ndarray, interval_minutes: float) -> tuple[int, float]:
    if mask.size == 0:
        return 0, 0.0
    starts = mask & np.concatenate(([True], ~mask[:-1]))
    return int(starts.sum()), float(mask.sum() * interval_minutes)


def calculate_validation_metrics(
    measured: Sequence[float] | np.ndarray | pd.Series,
    simulated: Sequence[float] | np.ndarray | pd.Series,
    *,
    timestamps: Sequence[object] | pd.DatetimeIndex,
    interval: str | pd.Timedelta,
    quantity_unit: str,
    normalization: Literal["mean_abs", "range", "peak_abs"] = "mean_abs",
    residual_semantic: ResidualSemantic = "none",
    cumulative_residual_unit: str | None = None,
    measured_uncertainty: Sequence[float] | np.ndarray | pd.Series | None = None,
    event_threshold: float | None = None,
) -> MetricResult:
    """Calculate one consistent metric set after pairwise missing-data exclusion."""

    measured_values = np.asarray(measured, dtype=float)
    simulated_values = np.asarray(simulated, dtype=float)
    timestamp_index = pd.DatetimeIndex(pd.to_datetime(timestamps, errors="raise"))
    if measured_values.ndim != 1 or simulated_values.shape != measured_values.shape:
        raise ValueError("measured and simulated must be equal-length vectors")
    if not quantity_unit.strip():
        raise ValueError("quantity_unit cannot be empty")
    if len(timestamp_index) != measured_values.size:
        raise ValueError("timestamps must match the value-vector length")
    if timestamp_index.tz is None:
        raise ValueError("metric timestamps must be timezone-aware")
    if timestamp_index.has_duplicates or not timestamp_index.is_monotonic_increasing:
        raise ValueError("metric timestamps must be unique and monotonic increasing")
    interval_value = _positive_fixed_interval(interval, "interval")
    valid = np.isfinite(measured_values) & np.isfinite(simulated_values)
    uncertainty_values: np.ndarray | None = None
    if measured_uncertainty is not None:
        uncertainty_values = np.asarray(measured_uncertainty, dtype=float)
        if uncertainty_values.shape != measured_values.shape:
            raise ValueError("measured_uncertainty must match measured values")
        valid &= np.isfinite(uncertainty_values) & (uncertainty_values >= 0.0)
    if not valid.any():
        raise ValueError("no finite aligned measurement/simulation pairs")
    observed = measured_values[valid]
    predicted = simulated_values[valid]
    aligned_timestamps = timestamp_index[valid]
    error = predicted - observed
    bias = float(np.mean(error))
    if normalization == "mean_abs":
        denominator = float(np.mean(np.abs(observed)))
    elif normalization == "range":
        denominator = float(np.max(observed) - np.min(observed))
    else:
        denominator = float(np.max(np.abs(observed)))
    normalized_bias = bias / denominator if denominator > 0.0 else math.nan
    measured_peak_position = int(np.argmax(observed))
    simulated_peak_position = int(np.argmax(predicted))
    measured_peak = float(observed[measured_peak_position])
    simulated_peak = float(predicted[simulated_peak_position])
    peak_timing_error_minutes = float(
        (
            aligned_timestamps[simulated_peak_position]
            - aligned_timestamps[measured_peak_position]
        ).total_seconds()
        / 60.0
    )
    if residual_semantic == "rate_per_second":
        cumulative_residual = float(np.sum(error) * interval_value.total_seconds())
    elif residual_semantic == "rate_per_hour":
        cumulative_residual = float(
            np.sum(error) * interval_value.total_seconds() / 3600.0
        )
    elif residual_semantic == "interval_total":
        cumulative_residual = float(np.sum(error))
    elif residual_semantic == "none":
        cumulative_residual = math.nan
    else:
        raise ValueError(f"unsupported residual_semantic: {residual_semantic}")
    if residual_semantic == "none" and cumulative_residual_unit is not None:
        raise ValueError(
            "cumulative_residual_unit must be null when residual_semantic is none"
        )
    if residual_semantic != "none" and not (cumulative_residual_unit or "").strip():
        raise ValueError(
            "cumulative_residual_unit is required for an integrated residual"
        )
    correlation = (
        float(np.corrcoef(observed, predicted)[0, 1])
        if observed.size >= 2
        and float(np.std(observed)) > 0.0
        and float(np.std(predicted)) > 0.0
        else math.nan
    )
    coverage = (
        float(np.mean(np.abs(error) <= uncertainty_values[valid]))
        if uncertainty_values is not None
        else math.nan
    )
    measured_event_count: int | None = None
    simulated_event_count: int | None = None
    event_frequency_error: int | None = None
    measured_event_duration: float | None = None
    simulated_event_duration: float | None = None
    event_duration_error: float | None = None
    if event_threshold is not None:
        interval_minutes = interval_value.total_seconds() / 60.0
        measured_event_mask = np.zeros(measured_values.shape, dtype=bool)
        simulated_event_mask = np.zeros(simulated_values.shape, dtype=bool)
        measured_event_mask[valid] = measured_values[valid] >= event_threshold
        simulated_event_mask[valid] = simulated_values[valid] >= event_threshold
        measured_event_count, measured_event_duration = _event_summary(
            measured_event_mask, interval_minutes
        )
        simulated_event_count, simulated_event_duration = _event_summary(
            simulated_event_mask, interval_minutes
        )
        event_frequency_error = simulated_event_count - measured_event_count
        event_duration_error = simulated_event_duration - measured_event_duration

    metrics = ValidationMetrics(
        quantity_unit=quantity_unit,
        count=int(valid.sum()),
        excluded_count=int((~valid).sum()),
        bias=bias,
        normalized_bias=float(normalized_bias),
        mae=float(np.mean(np.abs(error))),
        rmse=float(np.sqrt(np.mean(np.square(error)))),
        measured_peak=measured_peak,
        simulated_peak=simulated_peak,
        peak_error=simulated_peak - measured_peak,
        peak_timing_error_minutes=peak_timing_error_minutes,
        cumulative_residual=cumulative_residual,
        cumulative_residual_unit=cumulative_residual_unit,
        correlation=correlation,
        measured_uncertainty_coverage=coverage,
        measured_event_count=measured_event_count,
        simulated_event_count=simulated_event_count,
        event_frequency_error=event_frequency_error,
        measured_event_duration_minutes=measured_event_duration,
        simulated_event_duration_minutes=simulated_event_duration,
        event_duration_error_minutes=event_duration_error,
    )
    metric_frame = pd.DataFrame([metrics.to_dict()])
    provenance = _provenance(
        "calculate_validation_metrics",
        pd.DataFrame(
            {
                "measured": measured_values,
                "simulated": simulated_values,
                "uncertainty": (
                    np.full_like(measured_values, np.nan)
                    if uncertainty_values is None
                    else uncertainty_values
                ),
            },
            index=timestamp_index,
        ),
        metric_frame,
        {
            "interval": interval_value,
            "normalization": normalization,
            "residual_semantic": residual_semantic,
            "quantity_unit": quantity_unit,
            "cumulative_residual_unit": cumulative_residual_unit,
            "event_threshold": event_threshold,
            "bias_sign": "simulation_minus_measurement",
        },
    )
    return MetricResult(metrics=metrics, provenance=provenance)


def generate_metric_table(
    results: Mapping[str, MetricResult],
) -> MetricTableResult:
    """Generate a stable domain-by-metric table without formatting away precision."""

    if not results:
        raise ValueError("results cannot be empty")
    table = pd.DataFrame(
        {label: result.metrics.to_dict() for label, result in results.items()}
    ).T
    table.index.name = "series"
    input_value = {
        label: result.provenance.output_sha256 for label, result in results.items()
    }
    provenance = _provenance(
        "generate_metric_table",
        input_value,
        table,
        {"series_order": list(results)},
    )
    return MetricTableResult(table=table, provenance=provenance)


def generate_alignment_plot(
    alignment: AlignmentResult,
    *,
    quantity: str,
    title: str | None = None,
    output_path: str | Path | None = None,
) -> PlotResult:
    """Generate the standard measured/simulated trace and uncertainty band."""

    if quantity not in alignment.quantities:
        raise KeyError(f"quantity is not present in alignment: {quantity}")
    measured_column = f"{quantity}_measured"
    simulated_column = f"{quantity}_simulated"
    uncertainty_column = f"{quantity}_uncertainty"
    figure = Figure(figsize=(9.0, 4.5), constrained_layout=True)
    axis = figure.subplots()
    data = alignment.data
    axis.plot(data.index, data[measured_column], label="measurement", linewidth=1.5)
    axis.plot(data.index, data[simulated_column], label="simulation", linewidth=1.3)
    if uncertainty_column in data:
        uncertainty = data[uncertainty_column].astype(float)
        measured_values = data[measured_column].astype(float)
        axis.fill_between(
            data.index,
            measured_values - uncertainty,
            measured_values + uncertainty,
            alpha=0.2,
            label="measurement uncertainty",
        )
    axis.set_title(title or f"Measured and simulated {quantity}")
    axis.set_xlabel("timestamp")
    axis.set_ylabel(quantity)
    axis.grid(True, alpha=0.25)
    axis.legend()
    parameters: dict[str, object] = {"quantity": quantity, "title": title}
    if output_path is not None:
        path = Path(output_path)
        if not path.parent.exists():
            raise FileNotFoundError(f"plot output directory does not exist: {path.parent}")
        figure.savefig(path, dpi=150)
        parameters["output_path"] = path
        parameters["output_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    provenance = _provenance(
        "generate_alignment_plot",
        data,
        {
            "measurement": data[measured_column].tolist(),
            "simulation": data[simulated_column].tolist(),
        },
        parameters,
    )
    return PlotResult(figure=figure, provenance=provenance)


__all__ = [
    "TOOLING_VERSION",
    "AlignmentResult",
    "CalibrationValidationSplit",
    "MetricResult",
    "MetricTableResult",
    "MissingDataResult",
    "PlotResult",
    "ProvenanceRecord",
    "ResampleResult",
    "TimestampNormalizationResult",
    "UncertaintyPropagationResult",
    "UnitConversionResult",
    "ValidationMetrics",
    "WarmupExclusionResult",
    "align_measurement_simulation",
    "blocked_calibration_validation_split",
    "build_missing_data_mask",
    "calculate_validation_metrics",
    "calibration_validation_split",
    "combine_independent_uncertainties",
    "conservative_resample",
    "content_sha256",
    "convert_units",
    "exclude_warmup",
    "generate_alignment_plot",
    "generate_metric_table",
    "normalize_timestamps",
    "propagate_uncertainty",
]
