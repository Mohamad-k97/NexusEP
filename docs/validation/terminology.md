# Validation terminology

Validation category: **verification** (scope governance only).

NexusEP reports use these terms exclusively:

- **Verification:** evidence that equations, data transformations, state
  transitions, units, conservation checks, and software contracts are
  implemented as specified. Unit, contract, integration, and annual
  correctness tests are verification.
- **Comparative validation:** quantified agreement with an established
  simulation benchmark or another accepted implementation under the same
  inputs and boundary conditions. The reference, version, metrics, and
  tolerances must be named.
- **Empirical validation:** quantified agreement with physical measurements.
  The measurement system, uncertainty, time alignment, exclusions, and
  metrics must be documented.
- **Calibration:** estimation of model parameters using measurements. A
  calibration result is not validation evidence for the same samples used to
  fit it.
- **Blind validation:** evaluation of calibrated parameters against measured
  data that was not used for parameter selection, fitting, stopping, or model
  choice.

Required report header:

```text
Validation category: verification | comparative validation |
                     empirical validation | calibration | blind validation
Model claim(s): <IDs from model_claim_matrix.md>
Evidence: <tests, benchmark, or dataset and version>
```

Mixed-category work must report each category separately. “Validated” without
a category is not an acceptable claim.
