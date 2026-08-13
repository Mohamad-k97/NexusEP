# Occupant validation dossier

Validation category: **verification and empirical validation**.

## Model version and commit

Model claim `OCC-1`; source baseline `63936cc50fe83850d5c9bd1d1b49026f47d91c9f` plus dirty Phase 4 changes.

## Dataset and license

Registered NZERTF virtual-occupant schedule fixture, the retained BLS aggregate diagnostic, and official BLS ATUS 2023 respondent/activity microdata. The two raw ZIPs are ignored and checksum-registered; only compact results are tracked.

## Scenario mapping

Prescribed four-person schedules and load attribution plus complete survey-weighted ATUS diaries. The production population model samples whole diaries so sleep, location, timing, and duration remain correlated.

## Preprocessing

ATUS activities are joined to respondent weights by `TUCASEID`. The official 04:00-to-04:00 diary is rotated to the canonical 00:00-to-24:00 clock. Sleep code `010101` is explicitly inferred at home because BLS does not collect its location; other unknown-location minutes stay masked.

## Calibrated parameters

The empirical whole-diary probability mass is fitted from the development respondents using `TUFINLWGT`; no holdout statistic is fitted.

## Untouched validation period

Respondents are split before fitting by a stable SHA-256 `TUCASEID` bucket: 6,823 development diaries and 1,725 untouched holdout diaries. All episodes from one respondent remain in one partition.

## Metrics and plots

The retained aggregate diagnostic still fails. The respondent-level replacement samples 20,000 schedules and passes all frozen gates: sleep-fraction quantile MAE 0.002890, observed-location home-fraction quantile MAE 0.006815, sleep-episode-duration quantile MAE 1.0 minute, and exact deterministic repeat.

## Residual analysis

The passing metrics are distributional residuals against isolated respondents, not a fit to a single mean. The largest remaining scientific gaps are demographic/household conditioning and condition-dependent window, light, HVAC, and appliance action probabilities.

## Limitations

ATUS describes the U.S. civilian noninstitutionalized population and cannot establish deterministic or Italian-household truth. Whole-diary empirical sampling can reproduce observed schedule distributions but does not itself explain causal behavior or validate environmental response models.

## Pass/fail decision

**Pass for prescribed schedule execution and for the declared U.S. population schedule-prior holdout. The old aggregate alternative remains rejected; probabilistic action validation remains open.**

## Reproducible command

`uv run python scripts/validation_data/run_atus_population_validation.py` followed by `uv run pytest -q tests/unit/test_atus_population_model.py tests/contracts/test_nzertf_virtual_occupant_schedule.py tests/integration/test_phase4_blocked_alternatives.py`
