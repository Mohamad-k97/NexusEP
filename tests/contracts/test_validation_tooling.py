"""Cross-domain contracts for Phase 4.3 validation tooling."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nexusep.validation_data.tooling import (
    align_measurement_simulation,
    blocked_calibration_validation_split,
    build_missing_data_mask,
    calculate_validation_metrics,
    calibration_validation_split,
    combine_independent_uncertainties,
    conservative_resample,
    content_sha256,
    convert_units,
    exclude_warmup,
    generate_alignment_plot,
    generate_metric_table,
    normalize_timestamps,
    propagate_uncertainty,
)

pytestmark = pytest.mark.contract
VALIDATION_CATEGORY = "verification"


def _utc_index(periods: int, frequency: str = "1h") -> pd.DatetimeIndex:
    return pd.date_range("2025-01-01", periods=periods, freq=frequency, tz="UTC")


def _alignment() -> object:
    measured = pd.DataFrame(
        {"temperature": [20.0, 21.0], "uncertainty": [0.2, 0.2]},
        index=pd.date_range(
            "2025-01-01 01:00", periods=2, freq="1h", tz="Europe/Rome"
        ),
    )
    simulated = pd.DataFrame(
        {"zone_temperature": [20.1, 20.8]},
        index=pd.date_range(
            "2025-01-01 00:02", periods=2, freq="1h", tz="UTC"
        ),
    )
    return align_measurement_simulation(
        measured,
        simulated,
        quantities={"air_temperature_c": ("temperature", "zone_temperature")},
        uncertainty_columns={"air_temperature_c": "uncertainty"},
        tolerance="5min",
    )


def test_timestamp_normalization_requires_timezone_and_resolves_to_utc() -> None:
    result = normalize_timestamps(
        ["2025-01-01 01:00", "2025-01-01 02:00"],
        source_timezone="Europe/Rome",
    )
    assert str(result.timestamps.tz) == "UTC"
    assert result.timestamps[0] == pd.Timestamp("2025-01-01 00:00", tz="UTC")
    assert result.provenance.tooling_version == "1.0.0"
    assert result.provenance.operation == "normalize_timestamps"
    with pytest.raises(ValueError, match="source_timezone is required"):
        normalize_timestamps(["2025-01-01"], source_timezone=None)


def test_timestamp_normalization_rejects_dst_ambiguity_and_duplicates() -> None:
    with pytest.raises(ValueError):
        normalize_timestamps(
            ["2025-10-26 02:30"], source_timezone="Europe/Rome"
        )
    with pytest.raises(ValueError, match="duplicate normalized timestamps"):
        normalize_timestamps(
            ["2025-01-01 00:00", "2025-01-01 00:00"],
            source_timezone="UTC",
        )


def test_conservative_downsampling_preserves_rate_and_interval_totals() -> None:
    frame = pd.DataFrame(
        {
            "power_w": [100.0] * 4,
            "energy_wh": [25.0] * 4,
            "temperature_c": [10.0, 20.0, 30.0, 40.0],
        },
        index=_utc_index(4, "15min"),
    )
    result = conservative_resample(
        frame,
        source_interval="15min",
        target_interval="1h",
        semantics={
            "power_w": "rate",
            "energy_wh": "interval_total",
            "temperature_c": "state",
        },
    )
    assert result.data.iloc[0].to_dict() == pytest.approx(
        {"power_w": 100.0, "energy_wh": 100.0, "temperature_c": 25.0}
    )
    assert (result.coverage_fraction.iloc[0] == 1.0).all()
    assert result.data.iloc[0]["power_w"] * 1.0 == pytest.approx(100.0)


def test_conservative_upsampling_apportions_totals_without_duplication() -> None:
    frame = pd.DataFrame(
        {"power_w": [120.0], "energy_wh": [60.0]}, index=_utc_index(1)
    )
    result = conservative_resample(
        frame,
        source_interval="1h",
        target_interval="15min",
        semantics={"power_w": "rate", "energy_wh": "interval_total"},
    )
    assert result.data["power_w"].tolist() == pytest.approx([120.0] * 4)
    assert result.data["energy_wh"].tolist() == pytest.approx([15.0] * 4)
    assert result.data["energy_wh"].sum() == pytest.approx(60.0)


def test_resampling_reports_missing_coverage_without_zero_filling() -> None:
    frame = pd.DataFrame(
        {"power_w": [100.0, np.nan, 100.0, 100.0]},
        index=_utc_index(4, "15min"),
    )
    result = conservative_resample(
        frame,
        source_interval="15min",
        target_interval="1h",
        semantics={"power_w": "rate"},
    )
    assert result.data.iloc[0, 0] == pytest.approx(100.0)
    assert result.coverage_fraction.iloc[0, 0] == pytest.approx(0.75)


def test_unit_conversion_handles_affine_and_scaled_units() -> None:
    assert convert_units(0.0, from_unit="degC", to_unit="K").values == pytest.approx(
        273.15
    )
    assert convert_units(1.0, from_unit="kWh", to_unit="J").values == pytest.approx(
        3_600_000.0
    )
    assert convert_units(
        3600.0, from_unit="kg/h", to_unit="kg/s"
    ).values == pytest.approx(1.0)
    with pytest.raises(ValueError, match="incompatible units"):
        convert_units(1.0, from_unit="W", to_unit="degC")


def test_missing_data_masks_cover_nan_infinity_and_declared_sentinels() -> None:
    frame = pd.DataFrame(
        {"a": [1.0, np.nan, np.inf, -999.0], "b": [1.0, 2.0, 3.0, 4.0]}
    )
    result = build_missing_data_mask(
        frame, required_columns=("a", "b"), sentinels={"a": (-999.0,)}
    )
    assert result.valid_rows.tolist() == [True, False, False, False]
    assert result.missing_counts.to_dict() == {"a": 3, "b": 0}


def test_warmup_exclusion_supports_duration_and_rows() -> None:
    frame = pd.DataFrame({"value": range(6)}, index=_utc_index(6))
    duration_result = exclude_warmup(frame, duration="2h")
    row_result = exclude_warmup(frame, rows=2)
    pd.testing.assert_frame_equal(duration_result.data, row_result.data)
    assert duration_result.excluded_rows.sum() == 2


def test_alignment_normalizes_timezones_and_records_offsets_and_uncertainty() -> None:
    result = _alignment()
    assert result.data["matched"].all()
    assert result.data["time_offset_seconds"].tolist() == [120.0, 120.0]
    assert result.data["air_temperature_c_simulated"].tolist() == [20.1, 20.8]
    assert "air_temperature_c_uncertainty" in result.data
    assert str(result.data.index.tz) == "UTC"


def test_alignment_does_not_hide_out_of_tolerance_measurements() -> None:
    measured = pd.DataFrame({"value": [1.0]}, index=_utc_index(1))
    simulated = pd.DataFrame(
        {"value": [1.0]}, index=_utc_index(1) + pd.Timedelta("2min")
    )
    result = align_measurement_simulation(
        measured,
        simulated,
        quantities={"value": ("value", "value")},
        tolerance="1min",
    )
    assert not result.data.iloc[0]["matched"]
    assert math.isnan(result.data.iloc[0]["value_simulated"])


def test_calibration_validation_splits_are_disjoint_and_chronological() -> None:
    timestamps = _utc_index(6)
    split = calibration_validation_split(
        timestamps,
        calibration_end="2025-01-01T02:00:00Z",
        validation_start="2025-01-01T04:00:00Z",
    )
    assert split.calibration_mask.sum() == 2
    assert split.excluded_mask.sum() == 2
    assert split.validation_mask.sum() == 2
    assert not (split.calibration_mask & split.validation_mask).any()

    blocked = blocked_calibration_validation_split(
        timestamps, calibration_fraction=0.5, gap="1h"
    )
    assert not (blocked.calibration_mask & blocked.validation_mask).any()
    assert blocked.excluded_mask.any()


def test_uncertainty_propagation_supports_independent_and_covariant_inputs() -> None:
    independent = propagate_uncertainty([3.0, 4.0])
    assert independent.standard_uncertainty == pytest.approx(5.0)
    covariance = np.array([[9.0, 2.0], [2.0, 16.0]])
    covariant = propagate_uncertainty(
        [3.0, 4.0], sensitivities=[1.0, 1.0], covariance=covariance
    )
    assert covariant.standard_uncertainty == pytest.approx(math.sqrt(29.0))
    combined = combine_independent_uncertainties([3.0, 0.0], [4.0, 2.0])
    assert np.asarray(combined.standard_uncertainty).tolist() == pytest.approx(
        [5.0, 2.0]
    )


def test_common_metrics_use_declared_sign_timing_residual_and_uncertainty_rules() -> None:
    result = calculate_validation_metrics(
        [1.0, 3.0, 2.0, 0.0],
        [2.0, 2.0, 4.0, 0.0],
        timestamps=_utc_index(4),
        interval="1h",
        quantity_unit="W",
        residual_semantic="rate_per_hour",
        cumulative_residual_unit="Wh",
        measured_uncertainty=[1.0, 1.0, 1.0, 0.0],
        event_threshold=2.5,
    )
    metrics = result.metrics
    assert metrics.bias == pytest.approx(0.5)
    assert metrics.normalized_bias == pytest.approx(1.0 / 3.0)
    assert metrics.mae == pytest.approx(1.0)
    assert metrics.rmse == pytest.approx(math.sqrt(1.5))
    assert metrics.peak_error == pytest.approx(1.0)
    assert metrics.peak_timing_error_minutes == pytest.approx(60.0)
    assert metrics.cumulative_residual == pytest.approx(2.0)
    assert metrics.measured_uncertainty_coverage == pytest.approx(0.75)
    assert metrics.measured_event_count == 1
    assert metrics.simulated_event_count == 1
    assert metrics.event_frequency_error == 0


def test_metric_missing_pairs_are_excluded_and_break_event_runs() -> None:
    result = calculate_validation_metrics(
        [3.0, np.nan, 3.0],
        [3.0, 3.0, 3.0],
        timestamps=_utc_index(3),
        interval="1h",
        quantity_unit="degC",
        event_threshold=2.5,
    )
    assert result.metrics.count == 2
    assert result.metrics.excluded_count == 1
    assert result.metrics.measured_event_count == 2


def test_metric_table_and_plot_share_provenance_and_generate_artifacts(
    tmp_path: Path,
) -> None:
    metric = calculate_validation_metrics(
        [20.0, 21.0],
        [20.1, 20.8],
        timestamps=_utc_index(2),
        interval="1h",
        quantity_unit="degC",
    )
    table = generate_metric_table({"thermal": metric})
    assert list(table.table.index) == ["thermal"]
    assert table.table.loc["thermal", "count"] == 2
    plot_path = tmp_path / "alignment.png"
    plot = generate_alignment_plot(
        _alignment(), quantity="air_temperature_c", output_path=plot_path
    )
    assert plot_path.is_file() and plot_path.stat().st_size > 0
    assert plot.provenance.operation == "generate_alignment_plot"


def test_provenance_hashes_are_deterministic_and_sensitive_to_values() -> None:
    frame = pd.DataFrame({"value": [1.0, 2.0]}, index=_utc_index(2))
    assert content_sha256(frame) == content_sha256(frame.copy())
    changed = frame.copy()
    changed.iloc[1, 0] = 3.0
    assert content_sha256(frame) != content_sha256(changed)
