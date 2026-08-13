# Phase 1.8 — published baseline and architecture gate

Validation category: **verification**

## Deliverables

| Deliverable | Location |
|---|---|
| environment constraints | `requirements/constraints-py312.txt` |
| bootstrap and verification | `docs/baseline/PHASE_1_2_ENVIRONMENT.md` |
| Phase 16–18 validation matrix | `artifacts/baseline/phase_1_4_validation_matrix.json` and `docs/baseline/PHASE_1_4_VALIDATION_MATRIX.md` |
| reconstructed Phase 17 pytest suite | `tests/phase17/` with provenance in `docs/baseline/PHASE_1_3_RECOVERY_PROVENANCE.md` |
| deterministic object manifest | `artifacts/baseline/deterministic_object_manifest.json` |
| object profile | `artifacts/baseline/object_profile.json` |
| array benchmark | `artifacts/baseline/array_benchmark.json` |
| artifact hashes | `artifacts/baseline/artifact_manifest.json` |
| known deviations | `docs/baseline/KNOWN_FAILURES_AND_DEVIATIONS.md` |

The artifact manifest hashes approved compact manifests, reports, environment
definitions, ignored raw profile/benchmark outputs, deterministic normalized
outputs, and the protected root files. It intentionally excludes itself to
avoid a recursive self-hash.

## Gate verdict: NOT FROZEN

| Condition | Result | Evidence |
|---|---|---|
| supported clean environment installs and imports | pass | CPython 3.12.2, clean `pip check`, all required imports |
| all intended tests collect | pass | 53 collected |
| every failure understood | pass | 20/20 individual commands and 53/53 pytest tests pass; no failures |
| object results repeat | pass | both scenarios exact across all normalized tables |
| array results checked against object | partial | shared invariants pass; statewise comparison unsupported (D1) |
| benchmark conditions documented | pass | hardware, software, dimensions, warm-up, timing boundaries, memory, ranges recorded |
| generated artifacts absent from production source | pass | new generated files are confined to ignored artifact directories |
| generated artifacts absent from repository root | blocked | four protected pre-existing files remain by explicit instruction (D2) |

Architecture changes should therefore not begin under a “fully frozen” claim.
The baseline is sufficient to reproduce current tests, object behavior, and
runner performance, but D1 and D2 require resolution or an explicit user waiver
before the final gate can be marked passed.

Protected `.spyproject` files, the local ABBEY config, and all four root
CSV/NPZ hashes remained unchanged throughout Phase 1.4–1.8.
