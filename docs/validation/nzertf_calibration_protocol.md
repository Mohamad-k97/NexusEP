# NIST NZERTF calibration and blind-validation protocol

Validation category: **calibration and blind-validation planning; no result
claimed**.

Model claims: **THERMAL-1, MOIST-1, HVAC-1**.

Phase covered: **4.19**.

## Frozen split

- **Calibration:** Year 1, 2013-07-01 through 2014-06-30, DOI
  `10.18434/T4/1503134`.
- **Blind validation:** Year 2, 2015-02-01 through 2016-01-31, DOI
  `10.18434/T46W2X`. Year 2 must remain sealed until the model form,
  parameters, bounds, preprocessing, exclusions, objective, and acceptance
  criteria are frozen from Year 1.

The periods are deliberately not interchangeable. The NIST publication
documents equipment and operation changes that must be represented as known
inputs rather than absorbed into calibrated envelope parameters: Year 1 used
heat-pump dehumidification, continuous heat-recovery ventilation at about
170 m3/h, and a generic thermostat; Year 2 used a whole-house dehumidifier,
intermittent ventilation for 43 minutes per hour at about 140 m3/h, and a more
configurable thermostat. Both years used fixed 21 degC heating and 24 degC
cooling setpoints.

## Intended observations and comparisons

The hourly Metadata, HVAC, IndEnv, OutEnv, Load, Vent, and Elec channel groups
are required for each year. The eventual analysis will compare room-air
temperature, indoor relative humidity, heat-pump operation and electricity,
ventilation state, appliance/internal gains, and daily and annual energy.
Channel choice must be frozen by stable NIST identifiers, units, and declared
hourly aggregation method before values are loaded.

## Pre-calibration gate

No optimization may start until the following are committed:

1. A canonical NZERTF geometry, envelope, zoning, HVAC/ventilation mapping,
   weather forcing, schedules, and configuration-change record.
2. Calibrated parameter names, physical bounds, priors or initial values, and
   an identifiability review. Year-specific known inputs cannot be fitted.
3. Timestamp/timezone and interval-label interpretation, warm-up length,
   missing-data mask, anomaly exclusions, and resampling rules.
4. Channel-level uncertainty or a documented unweighted fallback, metric
   definitions, objective weights, and Year 1 acceptance thresholds.
5. A locked Year 2 evaluation script and thresholds covering bias, MAE/RMSE,
   peak/timing error, daily and annual energy, and uncertainty coverage where
   uncertainty is available.

## Known evidence gaps

The source publication, official checksum inventory, and two hourly metadata
files are registered, but the measurement tables have not been downloaded and
no calibration has been run. NIST reports 98.5% and 98.8% annual minute-data
coverage in Years 1 and 2, respectively, and notes both `NA` gaps and erroneous
zero readings. These must be masked explicitly rather than interpolated into a
better fit.

There is also an unresolved provenance discrepancy: the current Year 2
`Metadata-hour.csv` download is 65,632 bytes with SHA-256
`d960162aa5120397da4f33180066815406ffa8808fbef40bcac3bdd74f89b631`,
while NIST's current `hashes.csv` inventory lists 69,048 bytes and SHA-256
`ac271b8c0267e00147c7c11e962c1be4a845be598d7b8a4c44ab62103dafadd4`.
The mismatch must be resolved with NIST or frozen as a versioned source change
before any Year 2 channel mapping is trusted.

## Gate status

Phase 4.19 is **not complete**. The source split and reproducibility gates are
now explicit; empirical calibration and blind validation remain blocked by
the missing canonical building model, frozen parameter protocol, measurement
files, uncertainty treatment, and the Year 2 metadata mismatch. No fitted
parameter or credibility claim has been fabricated from metadata alone.
