# Thermal RC sensitivity and identifiability study

Validation category: **verification and pre-calibration identifiability
screening**. This is not calibration or empirical validation.

Phase covered: **4.27**. Model claim: **THERMAL-1**.

## Experiment and parameter bounds

The executed study calls the production
`semi_implicit_temperature_update` function for a 24-hour, 15-minute,
one-node backward-Euler RC experiment. A sinusoidal outdoor temperature and
separate morning/evening gain pulses excite both transient and equilibrium
behavior. The recorded targets are air temperature and envelope heat flow.

| Candidate | Nominal | Physical screening bounds |
|---|---:|---:|
| Effective capacity | 3,000,000 J/K | 1,500,000--6,000,000 J/K |
| Envelope conductance | 150 W/K | 60--300 W/K |
| Internal-gain scale | 1.0 | 0.5--1.5 |

Central finite differences are scaled by half the permitted parameter range
and by a target-specific scale (1 degC or 100 W). A candidate is observable
only when its global normalized RMS sensitivity is at least 0.01. The set is
rejected if the scaled Jacobian is rank deficient, its condition number
exceeds 100, or any absolute column cosine is at least 0.995.

## Executed result

| Gate | Result | Decision |
|---|---:|---|
| Effective rank | 3 of 3 | pass |
| Condition number | 7.435 | pass |
| Correlated pairs at 0.995 | 0 | pass |
| Observable candidates | 3 of 3 | pass |

Normalized RMS sensitivities by candidate and target were:

| Candidate | Air temperature | Envelope heat flow |
|---|---:|---:|
| Effective capacity | 2.361 | 3.541 |
| Envelope conductance | 2.787 | 5.890 |
| Internal-gain scale | 0.502 | 0.752 |

The proposed three-parameter problem is accepted for this experiment design.
No candidate is frozen. This does not prove global or dataset-specific
identifiability: every future calibration experiment must rerun the gate with
its actual observations, masks, forcing, and candidate set.

## Uncertainty result

A deterministic 512-member ensemble with explicitly illustrative independent
parameter distributions gives a **parameter-only**, not total, 95% final-step
air-temperature interval of 9.502--10.617 degC (median 10.029 degC). Its
maximum interval width over the experiment is 1.622 degC. Comparing the
15-minute solution with a one-minute reference gives 0.0815 degC RMSE and
0.1305 degC maximum absolute numerical error.

Measurement, weather/input, and structural-model uncertainty are not
available in this analytical fixture. Stochastic-occupant uncertainty is not
applicable. Consequently this study must not be presented as a total
prediction interval or a calibrated credibility result.

## Reproduction

```powershell
uv run python scripts/calibration/run_rc_sensitivity.py
uv run pytest -q tests/contracts/test_sensitivity_identifiability.py `
  tests/contracts/test_calibration_governance.py
```

The compact result is
[`artifacts/baseline/validation/thermal-rc-sensitivity-v1.json`](../../artifacts/baseline/validation/thermal-rc-sensitivity-v1.json).
Its initial SHA-256 is
`b1593de4b762ba502843404b56213275d7c4507eded42f02cb58cc4a3dd1bfd9`.
