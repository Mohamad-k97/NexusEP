# Core issue resolution audit

Validation category: **verification and validation-protocol audit**.

Assessment date: **2026-08-12**.

## Outcome

The rejected scientific alternatives exposed two different classes of issue.
Nine implementation, preprocessing, and contract defects were repairable.
The controlled-thermal rejection remains an evidence/model-scope failure;
changing bounds or tolerances merely to make it green would invalidate the
claim. The aggregate-only occupant rejection is retained, while a new
respondent-level alternative passes in its narrower schedule-prior scope.

| Issue | Root cause | Resolution | Current evidence |
|---|---|---|---|
| Lighting power and energy disagreement | The object bridge interpreted a watt command as an unconstrained daylight request, doubling delivered power in the parity scenario. | Convert requested watts to an installed-capacity fraction once at the bridge. | Both adapters deliver the commanded watts; parity has zero contract violations and zero electrical-energy drift. |
| Orientation-blind solar gain | The canonical path had no site and the thermal path multiplied GHI by a heuristic orientation factor. | Require explicit site coordinates/albedo for the supported scenario, calculate NREL-SPA position, resolve DNI/DHI/GHI on each opening plane, and feed identical gains to both engines. | Sunny-midday adapter tests reproduce independently calculated plane-of-array gains and the south-facing opening exceeds the north-facing opening. |
| Array pressure omission | Atmospheric pressure was validated but discarded; moisture conversion silently used 101325 Pa. | Extend the numeric weather contract and use the supplied pressure in array psychrometric conversions. | Mapping is exact and a pressure-perturbation test demonstrates that pressure changes the result. |
| Array graph bypass | Array coefficients were recomputed from scenario objects rather than from the validated compiled graph. | Derive envelope/interzone UA, capacity, opening availability, and solar geometry from deterministic compiled connections. | Both adapter snapshots prove consumption of the same sorted connection IDs. |
| Mutable HVAC design capacity | Runtime command and availability fractions were applied by rewriting static maximum capacities, coupling controls to equipment identity and making diagnostics misleading. | Preserve compiled design capacities and pass explicitly calculated per-step heating/cooling power through the runtime boundary. Record commands, availability, and capabilities as separate trace fields. | A regression proves 40% command at 50% availability delivers 20% of design power while the decoded maximum capacity remains unchanged; parity retains zero contract violations. |
| Missing conservation evidence | Solvers computed stable updates but the canonical debug boundary exposed no comparable residuals. | Calculate independent heat, moisture, and CO2 residuals in each backend and expose them only in debug evidence. | Maximum four-step residuals are 1.19e-12/4.27e-12 W (object/array heat), 1.32e-19/6.78e-20 kg/s (moisture), and 1.25e-20/1.95e-20 kg/s (CO2). |
| Dropped canonical `other` gains | The object adapter normalized `other` to `generic`, but the thermal aggregation bridge omitted the generic category. | Include generic sensible gains in the internal/appliance thermal channel and add a direct regression. | A 100 W generic source reaches the thermal solver with exactly 100 W total sensible gain. |
| Annex hourly forcing shifted one interval | The former mapper applied row T to the following interval. A lag audit and the published experiment start support mapping row T to the preceding hour, while the canonical contract labels interval starts. | Make the selected source-to-canonical alignment explicit and seed each run from the preceding measured state. | The clock-alignment regression passes; heat-input correlation and short-run error improve without changing solver equations. The source workbook's label convention is not claimed as independently proven. |
| ATUS diary clock shifted four hours | ATUS diaries cover 04:00 to 04:00, while NexusEP schedules use a midnight day. | Rotate complete diaries to 00:00--24:00, splitting the wraparound episode without changing duration, and preserve day-type conditioning. | Synthetic ZIP and full microdata regressions prove contiguous 1,440-minute coverage and deterministic weekday selection. |

The regenerated Phase 2.16 parity report contains 181 exact matches, 5
tolerance matches, 22 expected model differences, no missing features, no
contract violations, and no defects. Expected differences in temperature,
humidity, and CO2 remain model differences; they have not been hidden with a
larger tolerance.

## Rejected alternatives rerun

The Annex 71 diagnostic remains **blocked and rejected with alternative**.
The former one-room helper rejection remains available for provenance. Its
replacement maps four official air bodies and measured forcing through the
canonical object adapter, conserves heat to 1.83e-10 W, and uses no fallback.
Nevertheless calibration RMSE is 2.172 degC and the later diagnostic RMSE is
1.858 degC; capacity reaches 1.4955e8 J/K near the frozen upper bound. The
later targets were inspected while fixing the mapper, so they are no longer
unseen. This is negative evidence for the present reduced-order
parameterization, not a blind-validation pass.

The old ATUS aggregate alternative remains **blocked and rejected with
alternative**. It was not tuned away. A separate official-microdata
replacement is now **blocked but passed with alternative** for the declared
U.S. schedule-prior claim. It fits 6,823 weighted development diaries and
passes 1,725 respondent-isolated holdouts: sleep-fraction quantile MAE
0.002890, observed-home quantile MAE 0.006815, sleep-duration quantile MAE
1.0 minute, and exact deterministic repeat.

## Remaining work that cannot be replaced by test-specific code

- Acquire an independent controlled thermal dataset or a genuinely sealed
  Annex 58/71 outcome before claiming blind validation.
- Extend the canonical thermal contract for heater radiative split, blind
  state, supply-air temperature, cellar/ground boundaries, and detailed fabric
  before attempting another empirical fit.
- Add demographic/household conditioning and condition-dependent stochastic
  action models; the passing ATUS result covers schedules, not causal actions.
- Perform NZERTF integrated calibration/validation only when the measured
  channel mapping and documented year-to-year configuration changes exist.

## Reproduction

```powershell
uv run python -m nexusep.parity.harness --output artifacts/baseline/phase_2_16_initial_parity.json
uv run python scripts/validation_data/run_annex71_production_transfer.py
uv run python scripts/validation_data/run_atus_population_validation.py
uv run pytest -q
```
