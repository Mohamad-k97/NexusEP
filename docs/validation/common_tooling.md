# Common validation tooling

Validation category: **verification** (method governance)

All comparative, empirical, calibration, and blind-validation work must use the
shared functions in `nexusep.validation_data.tooling`, or document and register
an analysis-code deviation. Each transformation returns a `ProvenanceRecord`
containing tooling version `1.0.0`, the operation, canonical parameters, and
deterministic input/output SHA-256 values.

## Mandatory operation order

1. Normalize timestamps and timezones.
2. Convert units to the canonical public-unit registry.
3. Build missing-data masks; do not silently impute.
4. Resample using declared interval semantics and inspect coverage.
5. Exclude the declared model/measurement warm-up.
6. Create disjoint calibration and validation periods.
7. Align simulation to measurement timestamps with an explicit tolerance.
8. Propagate uncertainty and calculate metrics on pairwise-valid samples.
9. Generate standard tables and plots from the aligned artifact.
10. Register code, result hashes, tolerances, deviations, and source IDs in the
    Phase 4.2 result manifest.

## Time and interval rules

- Naive timestamps require an explicit source timezone.
- DST ambiguity and nonexistent local times raise unless the caller supplies an
  explicit resolution.
- Internal alignment uses UTC, while source timezone remains in provenance.
- Duplicate or non-monotonic timestamps are rejected.
- Timestamps denote interval starts, consistent with canonical scenario v1.
- Alignment never interpolates silently. Unmatched measurements remain visible
  with `matched=False` and missing simulation values.
- The alignment tolerance and direction are required provenance parameters.

## Conservative resampling

`conservative_resample` requires a fixed source interval, fixed target
interval, and one semantic for every numeric column:

| Semantic | Meaning | Resampling rule |
|---|---|---|
| `state` | interval-representative state such as temperature | overlap-time-weighted mean |
| `rate` | power, mass flow, or another rate | overlap-time-weighted mean; integral preserved when coverage is complete |
| `interval_total` | energy, mass, or another interval accumulation | apportioned by overlap, then summed |

Every output column receives a separate `coverage_fraction`. Missing source
values reduce coverage; they are never replaced by zero. Input intervals may
have gaps but cannot overlap. A result with incomplete coverage must either be
masked or explicitly justified before metrics are reported.

## Unit conversion

The common converter supports affine temperature conversion and explicit
dimensions for power, energy, mass flow, volume flow, pressure, ratios,
duration, and angles. Cross-dimension conversions fail. Current canonical
spellings include `degC`, `K`, `degF`, `W`, `kW`, `J`, `Wh`, `kWh`, `kg/s`,
`kg/h`, `m3/s`, `m3/h`, `Pa`, `kPa`, `fraction`, `%`, `ppm`, `s`, `min`, `h`,
`rad`, and `deg`.

## Missing data and warm-up

`build_missing_data_mask` marks nulls, numeric infinity, and declared source
sentinels. It returns cell masks, a pairwise-valid row mask, and per-column
counts. Imputation, gap filling, and outlier removal are separate registered
preprocessing decisions.

Warm-up is excluded by a declared leading duration or row count. The retained
and excluded rows are hashed. A warm-up choice must be made before calibration,
alignment metrics, or scientific plots.

## Calibration and validation splits

Splits are chronological and disjoint. Explicit boundary splitting supports a
gap between calibration and validation. The blocked-fraction helper provides a
deterministic chronological split with an optional leakage-prevention gap.
Random row splitting is not part of the common time-series contract.

Blind validation data must not influence parameter selection, preprocessing
choices, stopping rules, model selection, or tolerances.

## Uncertainty

Independent standard uncertainties are propagated in quadrature. Covariant
propagation uses the first-order rule

```text
u_y = sqrt(cᵀ Σ c)
```

where `c` contains sensitivities and `Σ` is a symmetric positive-semidefinite
covariance matrix whose diagonal equals the squared declared standard
uncertainties. Measurement-uncertainty coverage is the fraction of aligned
errors whose absolute magnitude is within the supplied measurement uncertainty
bound.

## Metric definitions

Let the signed error be `simulation - measurement` after pairwise missing-data
exclusion.

| Metric | Definition |
|---|---|
| bias | mean signed error |
| normalized bias | bias divided by measured mean absolute value by default; measured range or absolute peak may be selected |
| MAE | mean absolute error |
| RMSE | square root of mean squared error |
| peak error | simulated maximum minus measured maximum |
| peak timing error | simulated-peak timestamp minus measured-peak timestamp, minutes |
| cumulative residual | sum of interval totals, or integrated rate using the explicitly selected seconds/hour convention |
| correlation | Pearson correlation on valid pairs; undefined for constant or single-point series |
| uncertainty coverage | fraction of absolute errors within the supplied measurement uncertainty |
| event frequency error | simulated contiguous-event count minus measured count |
| event duration error | simulated threshold-exceedance minutes minus measured minutes |

Missing samples break event runs rather than joining events across an unknown
period. Metric results always report included and excluded sample counts and
the physical quantity unit. An integrated residual also requires its explicit
result unit, such as `Wh` for `W × h` or `kg` for `kg/s × s`.

## Tables and plots

`generate_metric_table` produces one stable row per named domain/quantity
without rounding away stored precision. `generate_alignment_plot` uses the
same aligned data to show measured and simulated traces plus the measurement
uncertainty band when present. Saving a plot records its file SHA-256 in the
operation parameters; scientific result manifests remain responsible for the
final registered artifact hash.

## Minimal example

```python
from nexusep.validation_data.tooling import (
    align_measurement_simulation,
    calculate_validation_metrics,
)

aligned = align_measurement_simulation(
    measured,
    simulated,
    quantities={"air_temperature_c": ("temperature_c", "air_temperature_c")},
    uncertainty_columns={"air_temperature_c": "temperature_uncertainty_c"},
    tolerance="5min",
)

metrics = calculate_validation_metrics(
    aligned.data["air_temperature_c_measured"],
    aligned.data["air_temperature_c_simulated"],
    timestamps=aligned.data.index,
    interval="10min",
    quantity_unit="degC",
    residual_semantic="none",
    measured_uncertainty=aligned.data["air_temperature_c_uncertainty"],
)
```
