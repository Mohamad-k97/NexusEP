# Phase 1.3 — Phase 17 recovery provenance

Validation category: **verification** (test provenance only)

## Recovery search

The search did not find verbatim source for the overwritten Phase 17.3, 17.5,
17.6, or 17.7 scripts.

- Git: Phase 17.1–17.8 first appear in commit
  `7d2729173146536771935ffa92eabaa3c4000c53`; the parent has no Phase 17
  files. `git fsck --unreachable --no-reflogs` found no recoverable objects.
- Uncommitted workspace: only the protected files recorded by Phase 1.0 were
  present; no alternate Phase 17 source or backup files were found.
- Spyder: `history.py` proves all Phase 17.1–17.8 physical filenames were run
  on 2026-06-29. They were run again selectively during the July 3 array work.
  Spyder autosave and project backup directories contained no copies.
- VS Code local history: only `.gitignore` and `pyproject.toml` NexusEP entries
  were present.
- External working copies: searches below `C:\Works`, Documents, and Downloads
  found no second NexusEP checkout.
- Archive: `NexusEP_array_refactor_changed_files.zip` contains a Phase 18.0
  array-contract script and array implementation files, but no Phase 17
  scripts. It corroborates the start of the array refactor only.
- Compiled caches: Phase 17.3/17.5/17.6/17.7 CPython 3.14 bytecode headers
  match the July 3 overwritten files and contain the Phase 18.23/18.24/18.22/
  18.26 identities. No older cache for those modules survived.

Compiled caches and IDE command history were treated only as corroborating
evidence, never as authoritative source.

## Contract-by-contract result

| Group | Pytest module | Provenance |
|---|---|---|
| 17.1 model rename and compatibility | `tests/phase17/test_17_1_model_rename.py` | adapted from surviving script |
| 17.2 performance-input contract | `tests/phase17/test_17_2_performance_input_contract.py` | adapted from surviving script |
| 17.3 engine-to-performance adapter | `tests/phase17/test_17_3_engine_to_performance_adapter.py` | reconstructed from production adapter contract |
| 17.4 observation contract | `tests/phase17/test_17_4_observation_contract.py` | adapted from surviving script |
| 17.5 legacy fallback quarantine | `tests/phase17/test_17_5_legacy_fallback_quarantine.py` | reconstructed from model flags, path constants, and runner defaults |
| 17.6 runner integration | `tests/phase17/test_17_6_runner_integration.py` | reconstructed from runner integration points and surviving neighboring tests |
| 17.7 debug outputs | `tests/phase17/test_17_7_debug_outputs.py` | reconstructed from output APIs/schema and v0.4 assertions |
| 17.8 yearly/minimal outputs | `tests/phase17/test_17_8_yearly_outputs.py` | adapted from surviving script |

No Phase 17 test is marked “restored verbatim,” because no trustworthy
verbatim external source was found. “Adapted” means the surviving assertions
were preserved while imports, entry points, and provenance were converted to
ordinary pytest form. “Reconstructed” means the assertion was derived from a
surviving production contract and is explicitly identified as such in the
test module.

## Reclassified Phase 18 content

- The old Phase 17.6 physical file became the Phase 18.22 action-scoring
  comparison under `tests/phase18/`.
- The old Phase 17.3 physical file became the Phase 18.23 thermal comparison.
- The old Phase 17.5 physical file became the Phase 18.24 moisture comparison.
- The old Phase 17.7 physical file became the Phase 18.26 shoebox benchmark
  under `benchmarks/arrays/`.

These comparisons are now independently collected as tests, while the 8,760
hour loop is only a benchmark. The recovered Phase 17 suite collects 36 tests
across all eight expected groups and passes independently.
