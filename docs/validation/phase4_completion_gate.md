# Phase 4 completion gate

Validation category: **verification and validation status reporting**.

Assessment date: **2026-08-14**. Latest scored implementation:
`3d15372457fe25b30a68db6ca5ef890abef79adc`.

## Gate assessment

| Required evidence | Status | Alternative classification | Evidence or blocker |
|---|---|---|---|
| Solar position passes an analytical reference | **pass** | not applicable | NREL SPA reference and edge-case contract suite |
| Weather ingestion is source- and timezone-correct | **pass for registered fixtures** | not applicable | PVGIS/NASA POWER ingestion and common alignment contracts; source accuracy is not claimed |
| Thermal RC passes analytical and comparative tests | **partial/open** | not applicable | Closed-form/conservation verification passes; no fabric cross-solver or Standard 140 result is registered |
| A controlled thermal dataset is validated blindly | **blocked** | **blocked and rejected with alternative** | Annex 71 now includes source-plan ceiling topology, separate measured supply/exhaust, measured IR sky forcing, and measured cardinal façade radiation. Protocol-1.6 v8 is deterministic and conservative but still fails pooled RMSE (2.489 degC), bias (+2.128 degC), ground/kitchen/sleeping RMSE, and four-row input completeness. Post-unsealing corrections mean it is neither blind nor a pass. |
| Airflow, CO2, and moisture balances close | **pass for declared reduced-order scope** | not applicable | Analytical suites reconcile storage, source, transfer, and removal |
| HVAC control and energy accounting pass supported BESTEST cases | **partial/open** | not applicable | Ideal controller verification and open EnergyPlus ideal-load comparison pass; equipment BESTEST physics are not implemented |
| Integrated performance is tested against NZERTF | **blocked** | **blocked and rejected with alternative** | Annex 71, DOE BOPTEST, and the registered EnergyPlus case were assessed. None replaces mapped measured temperature, humidity, HVAC, ventilation, occupant-load, and energy evidence; Annex 71 v4 is a rejected thermal diagnostic. |
| Daylight passes analytical cases before empirical comparison | **pass for analytical prerequisite** | not applicable | Elementary response suite; CIE/BRE empirical evidence remains open |
| Occupant models reproduce distributions | **blocked** | **blocked but passed with alternative** | The former aggregate comparison remains rejected. Its replacement fits complete survey-weighted ATUS 2023 development diaries and passes an isolated respondent holdout for daily sleep, observed home presence, sleep-episode duration, and deterministic sampling. The pass is limited to U.S. schedule priors. |
| Acoustics remains explicitly non-validated until upgraded | **pass** | not applicable | `ACOUST-0` dossier limits evidence to placeholder arithmetic |
| Calibrated parameters succeed on unseen data | **blocked** | **blocked and rejected with alternative** | The legacy fitted capacity still approaches its upper bound, while source-complete v8 remains outside frozen thresholds. No new residual-fitted parameter or unseen-period claim is made; the next valid step is a verified surface/layer RC formulation followed by development-period calibration and a genuinely sealed dataset. |
| Unsupported physics is visible in every report | **pass** | not applicable | Domain dossiers declare exclusions and scope-specific decisions |

## Decision

**Phase 4 is not complete.** The original blocked rows remain visible. The
alternative classification distinguishes an unavailable original route from
the outcome of a substitute: a substitute passes only if it tests the same
claim and satisfies the criteria. The respondent-level ATUS schedule
alternative passes within its declared U.S. population-prior scope. The
thermal and integrated alternatives remain rejected.

The repository now has enforceable pre-calibration governance, an executed
local sensitivity/identifiability study, frozen split and acceptance
manifests, an uncertainty budget, domain dossiers, and an open-source fallback
policy. The remaining blockers are scientific evidence tasks, not hidden test
failures:

- a thermal comparative fabric case;
- an independent controlled thermal dataset or a genuinely sealed Annex 58/71 period;
- a matched CONTAM executable comparison where model assumptions overlap;
- NZERTF Year 1 calibration followed by Year 2 evaluation with known
  configuration changes represented;
- CIE/measured daylight evidence when licensed reusable inputs are available;
- condition-dependent occupant action validation beyond schedule distributions.

No unavailable source is counted as a pass. The
[source fallback policy](source_fallback_policy.md) permits open alternatives
only when they test the same claim.

## Alternative rerun results

| Alternative | Category | Outcome | Compact evidence |
|---|---|---|---|
| Annex 71 N2 living-room mapping diagnostic | Empirical-validation diagnostic | rejected | [report](results/annex71_thermal_transfer_v1.md) |
| Object-runner/BLS ATUS aggregate sleep screen | Empirical validation alternative | rejected | [report](results/atus_aggregate_sleep_alternative_v1.md) |
| Annex 71 N2 four-air-body production diagnostic | Post-hoc empirical diagnostic | rejected | [report](results/annex71_production_transfer_v1.md) fixes the mapper but fails the numerical and sealed-target gates |
| Annex 71 thermal energy-path audit | Diagnostic verification and empirical residual analysis | rejection unchanged | [report](results/annex71_energy_path_audit_v1.md) verifies repaired paths and rejects a single fitted conductance as the remaining explanation |
| Annex 71 structural diagnostics | Post-hoc empirical residual diagnosis | historical rejection retained | [report](results/annex71_structural_diagnostics_v1.md) rejected timing, heater-split, initial-mass, and floor-area-capacity quick fixes; its identified boundary/fabric contracts were subsequently implemented and re-evaluated in v4 |
| Annex 71 component-resolved runtime/error diagnostic v4 | Post-unsealing empirical diagnostic | rejected | [report](results/annex71_physical_runtime_error_v4.md) records 98.088 s for 4,896 steps, pooled RMSE 2.663 degC, bias +2.316 degC, deterministic output, energy closure, and the remaining one-node/large-opening limitations |
| Annex 71 typed large-opening runtime/error diagnostic v5 | Post-unsealing empirical diagnostic | rejected | [report](results/annex71_large_opening_runtime_error_v5.md) records 70.014 s for 4,896 steps, pooled RMSE 2.626 degC, bias +2.295 degC, deterministic output, 1.537e-9 W energy closure, and the remaining one-node/horizontal-opening limitations |
| Annex 71 boundary-contract diagnostic v6 | Post-unsealing empirical diagnostic | rejected | [report](results/annex71_boundary_runtime_error_v6.md) preserves the corrected topology and ventilation contract and the discovered missing native sky-temperature handoff |
| Annex 71 sky-boundary diagnostic v7 | Post-unsealing empirical diagnostic | rejected | [report](results/annex71_sky_boundary_runtime_error_v7.md) improves pooled RMSE to 2.483 degC and bias to +2.131 degC; attic passes, while three airbodies and input completeness fail |
| Annex 71 measured-plane diagnostic v8 | Post-unsealing empirical diagnostic | rejected | [report](results/annex71_measured_plane_runtime_error_v8.md) records 160.939 s for 4,896 steps, pooled RMSE 2.489 degC, bias +2.128 degC, 1.969e-9 W closure, deterministic repeat, and the remaining reduced-RC limitation |
| BLS ATUS 2023 respondent-diary population model | Behavioral holdout validation | passed within U.S. schedule-prior scope | [report](results/atus_population_holdout_v1.md) |
| BOPTEST for NZERTF replacement | Evidence-coverage assessment | rejected | Simulated controls benchmark; not an empirical integrated replacement |
| EnergyPlus ideal-load case for NZERTF replacement | Comparative validation | rejected as integrated substitute | [narrow passing result](results/energyplus_ideal_loads_25_1_0.md) covers only ideal sensible load accounting |

The exact row classifications and their evidence paths are frozen in
`data/validation/governance/blocked_alternatives_v1.json`.

## Verification outcome

The full default suite passes **449 tests** with **4 intentional annual-lane skips**. Those four
are opt-in 8,760-interval and repeated-determinism runs controlled by
`NEXUSEP_RUN_ANNUAL` and `NEXUSEP_RUN_ANNUAL_REPEAT`; they are not unavailable
scientific-source tests and are not classified as blocked alternatives.

The production-code root-cause repairs and the distinction between repaired
defects and still-rejected scientific alternatives are recorded in the
[core issue resolution audit](core_issue_resolution_2026-08-12.md).

The checksum-backed registry also passes with raw-file verification enabled.

## Reproducible governance gate

```powershell
uv run python scripts/calibration/run_rc_sensitivity.py
uv run python scripts/validation_data/run_annex71_production_transfer.py
uv run python scripts/validation_data/run_annex71_energy_path_audit.py
uv run python scripts/validation_data/run_annex71_structural_diagnostics.py
uv run python scripts/validation_data/run_atus_population_validation.py
uv run pytest -q tests/contracts/test_sensitivity_identifiability.py `
  tests/contracts/test_calibration_governance.py `
  tests/integration/test_phase4_blocked_alternatives.py `
  tests/unit/test_sleep_work_arbitration.py
```
