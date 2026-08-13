# Moisture analytical and Annex 41 scope verification

Validation category: **verification**.

Model claim: **MOIST-1**.

Phases covered: **4.15** and the supported portion of **4.16**.

## Fixed-temperature analytical contract

NexusEP transports humidity ratio `w` in kg water per kg dry air. Relative
humidity is derived from `w`, fixed air temperature, and atmospheric pressure;
it is not a conserved state. The coupled backward-Euler equation is:

```text
(M_i/dt + sum(m_dot_ij)) w_i,next
    - sum(m_dot_ij w_j,next)
  = (M_i/dt) w_i,old + G_i + fixed-boundary terms
```

`M` is dry-air mass in kg, `m_dot` is dry-air mass flow in kg/s, and `G` is
water-vapour generation in kg/s. Every zone result now reports storage,
generation, transport, and their residual in kg/s. Interzone targets use the
simultaneously solved neighbour humidity ratio, which preserves total water
vapour for reciprocal closed exchange between unequal dry-air masses.

[`tests/unit/test_moisture_analytical.py`](../../tests/unit/test_moisture_analytical.py)
verifies:

- constant moisture generation and constant ventilation;
- source removal and exponential decay;
- multiple occupants and additive cooking/shower pulses;
- outdoor humidity steps;
- reciprocal interzone exchange and whole-building water conservation;
- humidity-ratio/relative-humidity round trips at 5, 20, and 30 °C;
- zone and whole-building residuals at every timestep.

## Annex 41 isothermal exercise

The registered IEA EBC Annex 41 project summary distinguishes isothermal
Exercises 1, 2, and 6 from non-isothermal Exercises 3 and 4. Its reported
Common Exercise 2 case 2-6 uses a 4.60 m³ chamber, 0.64 h⁻¹ ventilation,
20.5 °C ambient temperature, 51% ambient RH, and non-buffering walls.

The Phase 4.16 test implements that published non-buffering chamber structure
at fixed temperature and compares an explicitly authored six-hour moisture
pulse plus eighteen-hour decay against the analytical air-only solution. The
authored pulse is 0.016 kg/h and is not presented as an Annex measurement or
official exercise input. The summary report does not provide complete
machine-readable source schedules, reference series, or measurement
uncertainties.

This test is therefore equation verification of the supported, vapor-tight
non-buffering limit, not Annex 41 comparative or empirical validation.

## Gates

- Material sorption, moisture buffering, capillary transport, condensation,
  and envelope moisture storage are absent.
- Latent heat does not feed back to the thermal balance.
- Annex 41 gypsum-board and other buffering cases remain blocked.
- Non-isothermal Exercises 3 and 4 and coupled HAM claims remain blocked.
- Exercise 6's coupled-room measurements cannot test transport delay with the
  current ideal-mixing zone model.
- Underlying exercise-file availability and reuse rights must be verified
  before any files or digitized curves are incorporated.

Command and current result:

```powershell
uv run pytest -q tests/unit/test_moisture_analytical.py
```

**16 passed.** The fixed-temperature dry-air/water-vapour balance exit
criterion is met; buffering, non-isothermal HAM, and empirical Annex 41 gates
remain open.
