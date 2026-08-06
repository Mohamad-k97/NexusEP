# Phase 1.1 — repository boundaries

The repository now uses these roles:

| Path | Role |
|---|---|
| `nexusep/` | installable production source and thin legacy command shims only |
| `tests/phase16/` | Phase 16 validation and deterministic test fixtures |
| `tests/phase17/` | recovered Phase 17 contracts |
| `tests/phase18/` | Phase 18 array correctness comparisons and helpers |
| `tests/regression/` | cross-phase regressions not tied to one recovery phase |
| `benchmarks/object/` | object-runner profiles and historical runner workloads |
| `benchmarks/arrays/` | array-runner workloads and profiler helpers |
| `artifacts/baseline/` | small, approved, versioned manifests |
| `artifacts/profiles/` | ignored generated profiler output |
| `artifacts/benchmarks/` | ignored generated benchmark output |
| `docs/baseline/` | versioned recovery and environment reports |

## Compatibility policy

The historical `python -m nexusep.abbey.run_test_*` commands remain as thin
entry points. They import the corresponding test or benchmark module and call
its `main()` function. They contain no validation or benchmark implementation.
New automation should invoke pytest or the modules under `benchmarks/`
directly:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\phase17
.\.venv\Scripts\python.exe -m benchmarks.arrays.phase_18_20_8760
```

Compatibility modules are developer commands for a source checkout. Tests and
benchmarks are deliberately excluded from the installable `nexusep` package.

## Migration map

- Phase 16.0/16.1 validation moved to `tests/phase16/`.
- Genuine surviving Phase 17.1, 17.2, 17.4, and 17.8 validation moved to
  `tests/phase17/`.
- Reconstructed Phase 17.3, 17.5, 17.6, and 17.7 contracts live beside them.
- Phase 18.22/18.23/18.24 comparisons that had occupied Phase 17 filenames
  moved to `tests/phase18/`.
- Phase 18.20, 18.21, and 18.26 annual loops moved to `benchmarks/arrays/`.
- v0.1 through v0.5 object-runner workloads moved to `benchmarks/object/`.
- The shared array profiler moved from production source to
  `benchmarks/arrays/profiler.py`; its former import path is a compatibility
  shim.
- Airflow and graph sanity checks moved to `tests/regression/`.
- The Phase 1.0 report moved to `docs/baseline/` without content changes.

## Generated-file policy

Generated profiles and benchmark results are ignored under `artifacts/`.
Baseline hashes are versioned under `artifacts/baseline/`. Historical profile
files were moved from `nexusep/abbey/` to ignored
`artifacts/profiles/phase18_16/` and `artifacts/profiles/phase18_21/`. The old
visualization CSV was moved to ignored `artifacts/benchmarks/legacy/`.

The four root shadow CSV/NPZ files are a deliberate exception: Phase 1.0
explicitly protected those user files from modification. They remain in place
with exact `.gitignore` rules and frozen hashes, so they cannot be committed by
accident. Future outputs should be written under `artifacts/`.

Pytest temporary files are routed to ignored `artifacts/test-temp/`; `.venv/`
and normal caches remain ignored.
