# ATUS 2023 population holdout validation

Validation category: empirical validation
Model claim(s): OCC-1
Data source IDs: bls-atus-2023-microdata

The production model samples complete survey-weighted development diaries. This preserves within-day dependence among sleep, location, and activity duration. A stable respondent hash keeps every episode for one person in one partition.

## Evidence and limits

- Development respondents: 6823
- Untouched holdout respondents: 1725
- Generated schedules: 20000
- Sleeping is activity code 010101. BLS does not collect location for sleep, so sleep-at-home is an explicit inference. Other uncollected locations are excluded from the primary home-fraction denominator.
- The official 04:00-to-04:00 diary is rotated to a canonical 00:00-to-24:00 local-day schedule before use.
- ATUS supports U.S. population priors; it is not deterministic household truth and is not direct empirical validation for an Italian population.

## Frozen holdout results

- Daily sleep-fraction quantile MAE: 0.002890 (limit 0.05; pass)
- Observed-location home-fraction quantile MAE: 0.006815 (limit 0.05; pass)
- Sleep-episode duration quantile MAE: 1.000 min (limit 30 min; pass)
- Deterministic repeat: pass

Decision: **passed**.

## Reproduce

```text
uv run python scripts/validation_data/run_atus_population_validation.py
```
