# Phase 3 correctness gate

Validation category: **verification**

This gate establishes implementation correctness and engineering invariants.
It does not establish comparative or empirical credibility; those claims are
bounded by the model-claim matrix in `../validation/model_claim_matrix.md`.

| Phase | Automated evidence | Gate |
|---|---|---|
| 3.1 | markers plus `tests/conftest.py` enforce exactly one lane per test | enforced at collection |
| 3.2 | AST duplicate-dataclass scan and `PersonState` round trip | PR |
| 3.3 | strict JSON/JSONC duplicate paths and unknown-key tests | PR |
| 3.4–3.6 | graph-owned envelope, directional heat/solar/interzone tests, mandatory graph and feature checks | PR |
| 3.7 | arbitrary building/dwelling/zone/occupant IDs through loader, both adapters, runner, logging and decode | PR |
| 3.8–3.9 | isolated execution-state and actor-attribution tests | PR |
| 3.10 | multi-person occupancy cardinality and reconciliation tests | PR |
| 3.11 | shared adapter conformance plus arbitrary-ID coverage | PR/nightly |
| 3.12 | exception propagation, explicit fallback and status/category propagation | PR |
| 3.13 | real short runner integration and deterministic contract coverage | PR |
| 3.14 | script inventory, pytest delegates, and no manual test `main()` blocks | PR |
| 3.15 | 8,760-step engineering invariants for both supported adapters | nightly |
| 3.16 | benchmark code/location separation; timing only in manual lane | PR/manual |
| 3.17 | `.github/workflows/quality.yml` defines PR, nightly and manual lanes | automated |

## Non-negotiable success rule

A graph-dependent run must fail before physics execution if the graph is
missing, belongs to a different building, contains a different zone set, has
an incomplete conditioned-zone envelope, or enables an operable-window
feature without an openable-window definition. Legacy UA is permitted only
through the explicitly named `legacy_ua_compatibility` model.

## Annual correctness scope

`tests/annual/test_annual_correctness.py` checks 8,760 exact intervals,
timestamps, zone coverage, finite/bounded states, nonnegative energy,
power-to-energy integration, aggregation reconciliation, fallback visibility,
and optional deterministic repetition. It is environment-gated to keep PRs
short:

```powershell
$env:NEXUSEP_RUN_ANNUAL = "1"
$env:NEXUSEP_RUN_ANNUAL_REPEAT = "1"
.venv\Scripts\python.exe -m pytest tests\annual -m annual
```

An annual pass means only that the supported scenario satisfies these
engineering invariants. It does not mean annual consumption represents a real
building.

## Release decision

Architecture work may proceed only when the full non-annual suite passes, the
nightly annual lane passes or has a documented unsupported result, no fallback
is unreported, and all failures are classified. Scientific credibility remains
separately gated by comparative and empirical evidence.

## Execution record — 2026-08-10

| Command | Result |
|---|---|
| `.venv\Scripts\python.exe -m pytest --collect-only -q` | 181 tests collected |
| `.venv\Scripts\python.exe -m pytest -m "unit or contract or (integration and not slow)" -q` | 175 passed, 6 deselected |
| `.venv\Scripts\python.exe -m pytest -q` | 177 passed, 4 intentionally gated annual tests skipped |
| annual engineering-invariant lane with `NEXUSEP_RUN_ANNUAL=1` | object and array passed (2 passed) |
| annual repeat lane with `NEXUSEP_RUN_ANNUAL_REPEAT=1` | object and array passed two-run digest equality (2 passed) |
| focused Ruff check over new Phase 3 sources/tests | passed |

The first annual attempt found an invalid fixture activity (`home` instead of
schema-v1 `awake`); this was **test corruption** and was corrected before any
engine ran. The next attempt correctly exposed unbounded CO₂ in a deliberately
sealed, continuously occupied fixture because the short parity control policy
turns ventilation off after timestep 1. The annual fixture now explicitly
commands `0.02 m³/s` basic ventilation per zone. With that supported boundary
condition, both 8,760-step runs satisfy the bounded-state and aggregation
invariants. This correction changes only test scenario inputs, not an engine
equation.
