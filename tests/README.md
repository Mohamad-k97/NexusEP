# Test taxonomy

Every collected test has exactly one execution lane. `tests/conftest.py`
enforces the lane marker and records `validation_category=verification` in test
reports. Passing these tests verifies implementation; it is not empirical
validation or calibration.

| Directory/marker | Purpose | Lane |
|---|---|---|
| `tests/unit/`, `unit` | Isolated functions and state transitions | PR |
| `tests/contracts/`, `contract` | Schemas, units, IDs, graph, adapters | PR |
| `tests/integration/`, `integration` | Complete timesteps and short runs | PR/extended |
| `tests/annual/`, `annual`, `slow` | 8,760-interval correctness | Nightly |
| `tests/benchmarks/`, `benchmark` | Benchmark protocol checks, not timing assertions | Manual/release |

Historical `phase16`, `phase17`, and `phase18` directories are compatibility
collections while their public launcher modules survive. They are assigned to
the integration lane automatically; timing loops themselves live under
`benchmarks/`.

Commands:

```powershell
# Pull request lane
uv run pytest -m "unit or contract or (integration and not slow)"

# Nightly correctness lane
$env:NEXUSEP_RUN_ANNUAL = "1"
uv run pytest -m "annual or (integration and slow)"

# Manual benchmark protocol lane
uv run pytest -m benchmark
```

Every adapted or reconstructed Phase 17 module records its provenance in its
module docstring and in `docs/baseline/PHASE_1_3_RECOVERY_PROVENANCE.md`.

Engine-independent public contract gates under `tests/contracts/` check
terminology, units, topology, arbitrary ID round trips, strict configuration,
and graph-owned envelopes. Adapter and conformance compatibility collections
remain assigned to the contract lane.

The annual suite checks engineering invariants. It does not assert that annual
consumption matches a measured building; that requires a separately labeled
empirical-validation study.
