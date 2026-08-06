# Tests

Phase validation is ordinary pytest coverage grouped by recovery phase.
Long-running timing loops belong under `benchmarks/`, not here. Every adapted
or reconstructed Phase 17 module records its provenance in its module
docstring and in `docs/baseline/PHASE_1_3_RECOVERY_PROVENANCE.md`.

Engine-independent public contract gates live under `tests/contracts/`. They
check terminology, units, supported-use-case topology, and reference fixtures;
they do not establish either simulation engine as canonical.

The Phase 2.5–2.7 gates additionally compile the canonical scenario and test
stable ID/index round trips, timezone-aware interval semantics, geometry tiers,
and deterministic physics-graph structure and hashing.

`tests/scenarios/` verifies Phase 2.8–2.10 weather policy, strict versioned
models, JSON/JSONC loading, external paths, defaults/audit, semantic errors,
immutability, and repeatable compilation.

`tests/adapters/` verifies Phase 2.11–2.14 typed timestep coverage, canonical
required outputs and energy aggregates, real object/array timestep execution,
fallback quarantine, deterministic array registries, restored string IDs, and
explicit rejection of unsupported array inputs.
