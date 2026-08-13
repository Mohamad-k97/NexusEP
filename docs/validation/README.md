# Validation governance

Validation category: **verification** (scope governance only).

- [Terminology](terminology.md) defines what NexusEP means by verification,
  comparative validation, empirical validation, calibration, and blind
  validation.
- [Model claim matrix](model_claim_matrix.md) limits claims and maps each model
  to suitable evidence.
- [Validation-data registry policy](data_registry.md) defines immutable source,
  preprocessing, result, and report provenance.
- [Common validation tooling](common_tooling.md) freezes alignment, resampling,
  uncertainty, metric, plot, table, and provenance rules across domains.
- [Elementary RC response verification](thermal_rc_verification.md) records
  the Phase 4.7 analytical equations, tolerances, conservation fix, and scope.
- [Prescribed airflow and contaminant verification](airflow_verification.md)
  records the Phase 4.10/4.12 analytical balances, coupled CO₂ conservation,
  traceable flow paths, window scope, and pressure-network gate.
- [NIST CONTAM comparative scope](contam_comparative_scope.md) registers the
  usable public NIST references and separates comparable prescribed-flow
  behavior from unsupported pressure-network cases.
- [CO2 analytical and multizone verification](co2_verification.md) records the
  QICO2 single-zone equations, two-/three-zone conservation, attribution, and
  the remaining CONTAM/transport-delay gates.
- [Moisture analytical and Annex 41 scope verification](moisture_verification.md)
  records fixed-temperature dry-air and water-vapour balances, psychrometric
  conversions, the non-buffering isothermal exercise, and HAM deferrals.
- [Deferred external thermal validation gates](deferred_thermal_validation.md)
  preserves the Phase 4.8/4.9 human-involvement boundary without claiming an
  unexecuted result.
- [Ideal/full-capacity HVAC control verification](hvac_control_verification.md)
  freezes the Phase 4.17 controller and energy-accounting contract.
- [Open HVAC comparative alternatives](hvac_bestest_alternatives.md) explains
  why no ASHRAE material was ingested, records the executed open EnergyPlus
  ideal-load comparison, and classifies unsupported NREL HVAC BESTEST suites.
- [EnergyPlus ideal-load result](results/energyplus_ideal_loads_25_1_0.md)
  reports the checksum-backed Phase 4.18 alternative comparison.
- [Annex 71 thermal-mapping diagnostic](results/annex71_thermal_transfer_v1.md)
  records why the historical helper-model transfer is not production or blind
  validation and preserves its rejected numerical result.
- [Annex 71 production diagnostic](results/annex71_production_transfer_v1.md),
  [energy-path audit](results/annex71_energy_path_audit_v1.md), and
  [structural diagnostics](results/annex71_structural_diagnostics_v1.md)
  preserve the repaired production mapping, rejected empirical result, and
  frozen evidence against timing, split, mass-state, and capacity quick fixes.
- [Annex 71 component-resolved runtime/error diagnostic](results/annex71_physical_runtime_error_v4.md)
  records the fixed-CET Extended run, deterministic timing, temperature error,
  conservation result, and remaining model-form rejection under protocol 1.3.
- [ATUS aggregate sleep alternative](results/atus_aggregate_sleep_alternative_v1.md)
  compares repaired object-runner output with the survey aggregate and records
  the remaining duration and distribution gaps.
- [NIST NZERTF protocol](nzertf_calibration_protocol.md) freezes the Year 1
  calibration/Year 2 blind-validation split and all remaining Phase 4.19
  evidence gates without claiming an unexecuted fit.
- [Elementary daylight and lighting verification](daylight_verification.md)
  records the Phase 4.20 algebraic, monotonic, directional, shading, power,
  energy, threshold, and hysteresis checks.
- [Published lighting benchmark scope](lighting_benchmark_scope.md) keeps CIE
  171 and BRE-IDMP comparisons blocked until their actual reference data and
  reuse terms are available.
- [Occupant behavior validation protocol](occupant_behavior_validation_protocol.md)
  freezes the Phase 4.22/4.23 population, split, distribution, probability,
  variability, and transferability rules.
- [NZERTF virtual-occupant verification](nzertf_virtual_occupant_verification.md)
  registers and decodes a compact prescribed-family schedule fixture while
  keeping natural-human and full-engine energy claims out of scope.
- [Acoustic placeholder verification](acoustics_placeholder_verification.md)
  freezes Phase 4.25 at dB arithmetic, direction/order, symmetry, and bounded
  response without making room-acoustic or transmission-loss claims.
- [Future acoustic validation gates](future_acoustic_validation.md) registers
  PTB absorption metadata and Motus impulse-response metadata while keeping
  both scientifically blocked until matching acoustic physics exist.
- [Thermal RC sensitivity and identifiability](thermal_rc_sensitivity.md)
  executes the Phase 4.27 pre-calibration observability, rank, correlation,
  conditioning, bounds, and partial-uncertainty gate.
- [Calibration governance](calibration_governance.md) freezes the Phase
  4.28--4.30 splits, pre-fit acceptance criteria, and six-part uncertainty
  budget in strict machine-readable manifests.
- [Validation dossiers](dossiers/README.md) publish one status report per
  scientific domain using a common Phase 4.31 structure.
- [Validation-source fallback policy](source_fallback_policy.md) allows open
  alternatives only for scientifically matching claims and records the limits
  of the current EnergyPlus replacement for unavailable ASHRAE material.
- [Phase 4 completion gate](phase4_completion_gate.md) retains every original
  blocked row and adds the exact passed/rejected/no-alternative outcome for
  each substitute without treating availability as scientific success.

All pytest correctness results are currently categorized as **verification**.
Comparative and empirical reports must name their benchmark or measurement
dataset, while calibration and blind validation must identify their disjoint
fit and holdout periods.

External validation evidence is governed by the checksum-backed
[`data/validation/registry.json`](../../data/validation/registry.json). A
candidate dataset named in the model-claim matrix is not evidence until an
indexed source manifest records its immutable raw-file hashes, license,
uncertainty, preprocessing, and permitted use. Scientific reports are indexed
under [`results/`](results/) and may not cite an unregistered source.
