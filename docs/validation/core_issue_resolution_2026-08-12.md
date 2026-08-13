# Core issue resolution audit

Validation category: **verification and validation-protocol audit**.

Assessment date: **2026-08-13**.

## Outcome

The rejected scientific alternatives exposed two different classes of issue.
Sixteen implementation, preprocessing, and contract defects were repairable.
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
| Annex boundary and fabric reduction | The supported path could not name the measured cellar boundary, carry component properties/thermal bridges, or address individual opening and door states. | Add named boundary, surface bridge, infiltration, per-opening and interzone-opening contracts; construct the plan-derived N2 component graph; map measured cellar and operation schedules through the object adapter. | Contract tests reject missing/invented inputs; the v4 run consumes the explicit graph without fallback and closes energy to 1.471e-9 W. |
| Extended clock treated as civil time | Interpreting source Excel serials as Europe/Berlin creates duplicate UTC instants at the March DST transition, although the workbook contains every 02:00--02:50 row. | Interpret the registered source clock as fixed CET (`Etc/GMT-1`) and preserve the post-unsealing amendment. | The 10-minute primary interval collects 4,896 output steps without duplicate instants. This correction does not restore a blind claim. |
| Incomplete blind schedule | The first component mapper closed only one of the two west-facing ground-floor blinds, contrary to the experiment specification. | Close both specified west ground-floor blinds and keep north/east/south plus attic-west states open. | Mapping tests assert the two ground-west commands exactly; the correction is source-derived and documented under protocol 1.2. |
| RC capacity/coupling mismatch | The adapter assigned every opaque-surface capacity to the zone mass node, but its exchange area included only floor and interzone walls. | Derive coupling area from all opaque graph faces while retaining the old estimator only for geometry-free legacy callers. | The regression proves capacity and area derive from the same canonical surfaces. V4 lowers maximum error but does not pass the empirical gate, so no fitted claim is made. |
| Legacy graph received physical opening IDs | Strict controls emitted a measured child-window and door command even when the historical aggregate graph did not declare those openings. | Generate controls only for exact compiled opening/surface IDs and preserve the unsupported legacy-operation limitation. | The legacy regression collects and runs without an invented reference; the historical diagnostic still rejects numerically. |
| ATUS diary clock shifted four hours | ATUS diaries cover 04:00 to 04:00, while NexusEP schedules use a midnight day. | Rotate complete diaries to 00:00--24:00, splitting the wraparound episode without changing duration, and preserve day-type conditioning. | Synthetic ZIP and full microdata regressions prove contiguous 1,440-minute coverage and deterministic weekday selection. |
| Mechanical supply heat misclassified as a generic gain | The Annex mapper converted supply-air heat to a generic source. The generic bridge split it 70/30 between air and mass, although ventilation heat acts directly on the air node. | Add a typed mechanical supply-temperature command and keep mechanical, infiltration, and window conductances distinct in the solver. | Regressions prove supply temperature applies only to mechanical airflow; infiltration remains at outdoor temperature. |
| Heater radiant share discarded | The documented 70/30 heater split was sent through a control path that treated all delivered heat as convective. | Add typed heating/cooling convective fractions and construct explicit air/mass thermal gains. Preserve `1.0` as the compatibility default. | A 500 W, 70% convective command reaches the solver as exactly 350 W air and 150 W mass gain. |

The regenerated Phase 2.16 parity report contains 181 exact matches, 4
tolerance matches, 23 expected model differences, no missing features, no
contract violations, and no defects. Expected differences in temperature,
humidity, and CO2 remain model differences; they have not been hidden with a
larger tolerance.

## Rejected alternatives rerun

The Annex 71 diagnostic remains **blocked and rejected with alternative**.
The former helper and legacy-effective results remain available for
provenance. The v4 replacement maps four official air bodies, component
properties, thermal bridges, measured cellar/weather forcing, blind/window/
door schedules, and graph-derived RC area through the canonical object
adapter. It is deterministic, uses no fallback, and conserves heat to
1.471e-9 W. The 4,896-step Extended run has pooled RMSE 2.663 degC, bias
+2.316 degC, MAE 2.358 degC, and maximum absolute error 8.565 degC. Those
values fail the frozen thresholds, and four missing outdoor-CO2 rows
independently fail input completeness. Post-unsealing amendments mean the
result is not blind evidence.

The observation-constrained historical audit reports 0.835 degC later-period one-step
RMSE but 302.7 W unexplained-gain MAE. Residuals change sign, vary strongly by
zone, and have the largest tails in the attic. That evidence rejects the idea
of adding one fitted constant conductance and does not authorize more
calibration. A frozen cross-period structural diagnostic rejects one-hour
source shifts, alternate heater splits, +/-2 degC initial mass states, and
floor-area capacity allocation as material explanations. The official
supplement exposed real roof-tilt, component-fabric, cellar, and blind mapping
defects, which are now corrected without residual fitting. V4 shows that those
repairs do not remove the positive free-run bias. The largest errors occur in
the kitchen during roughly 1.8 kW heat pulses with the internal door open,
leaving the one-mass-node fabric representation and prescribed symmetric
large-opening mixing as the strongest model-form limitations.

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
- Replace the single zone-mass representation with a verified layer/surface
  state formulation before claiming transient fabric credibility.
- Implement and verify a pressure/buoyancy large-opening airflow formulation
  before using the Annex door cycle for empirical airflow or thermal claims.
- Propagate source measurement uncertainty and replace the generic closed-blind
  optical factor with registered optical data before another empirical fit.
- Add demographic/household conditioning and condition-dependent stochastic
  action models; the passing ATUS result covers schedules, not causal actions.
- Perform NZERTF integrated calibration/validation only when the measured
  channel mapping and documented year-to-year configuration changes exist.

## Reproduction

```powershell
uv run python -m nexusep.parity.harness --output artifacts/baseline/phase_2_16_initial_parity.json
uv run python scripts/validation_data/run_annex71_production_transfer.py
uv run python scripts/validation_data/run_annex71_energy_path_audit.py
uv run python scripts/validation_data/run_annex71_structural_diagnostics.py
uv run python scripts/validation_data/run_annex71_physical_runtime_error.py
uv run python scripts/validation_data/run_atus_population_validation.py
uv run pytest -q
```
