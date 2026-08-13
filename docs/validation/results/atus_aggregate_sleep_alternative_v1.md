# ATUS aggregate sleep alternative

Validation category: empirical validation
Model claim(s): OCC-1
Data source IDs: dbnomics-bls-atus-sleeping-2025

## Result

The BLS ATUS all-person sleeping series was acquired through the DBnomics
mirror. Years through 2022 were designated development context; the 2023
aggregate estimate was reserved as the untouched screen. The source reports
9.07 hours/day (544.2 minutes/day) for 2023.

The repaired production object runner was executed for 30 deterministic days
at 15-minute resolution with seed 101 and a one-day warm-up exclusion. It
produced 450.0 simulated sleep minutes per scored day, an absolute difference
of 94.2 minutes against the frozen 30-minute duration screen. The comparison
now uses model output; `target_sleep_minutes` is recorded only as internal
decision provenance.

| Test | Result |
|---|---|
| Aggregate sleep-duration screen | fail: 94.2 min > 30 min |
| Complete sleep episodes | 30 |
| Median complete episode | 450 min |
| Episodes ending at the former 300-min discontinuity | 0 |
| Individual timing/duration/frequency distributions available | no |
| Distribution-reproduction gate | fail |

Classification: **blocked and rejected with alternative**.

## Interpretation

The previous test incorrectly compared an internal decision threshold with a
population output. That defect is resolved. Separately, continuous sleep
protection now tapers from the minimum to the target, removing the artificial
five-hour episode termination. The remaining rejection is empirical: one
default occupant and one seed still fail the aggregate-duration screen and
cannot establish a population distribution.

## Scope and limitations

DBnomics is the access path and BLS is the underlying provider. The mirror
snapshot ends in 2023. Attempts to retrieve official 2024 BLS microdata ZIPs
received an automated-access denial in this environment; denial responses
were not treated as data or registered. The array backend remains excluded
because its fixed-duration sleep execution is not conformant with the object
backend's repeated-decision contract.

## Reproduction

```powershell
uv run python scripts/validation_data/run_atus_aggregate_alternative.py
```
