# Phase 1.4 — surviving validation baseline

Validation category: **verification**

All surviving Phase 16–18 entry points ran individually in fresh subprocesses
before aggregate pytest. Each process used CPython 3.12.2 from `.venv`, the
repository root as its working directory, `PYTHONHASHSEED=0`, `TZ=Europe/Rome`,
and `MPLBACKEND=Agg`. Phase 18.21 outputs were redirected with
`NEXUSEP_PROFILE_OUTPUT_DIR` to an ignored, per-command artifact directory.

The authoritative matrix, including every exact absolute command, dependency
and configuration requirement, captured exception tail, generated-file hash,
and repository-state comparison, is
`artifacts/baseline/phase_1_4_validation_matrix.json`.

| Entry | Role | Runtime (s) | Outcome | Script-created files |
|---|---|---:|---|---:|
| Phase 16.0 | validation test | 7.161 | pass | 0 |
| Phase 16.1 | validation test | 13.466 | pass | 0 |
| Phase 17.1 | validation test | 9.136 | pass | 0 |
| Phase 17.2 | validation test | 6.178 | pass | 0 |
| Phase 17.3 | validation test | 7.061 | pass | 0 |
| Phase 17.4 | validation test | 5.593 | pass | 0 |
| Phase 17.5 | validation test | 8.818 | pass | 0 |
| Phase 17.6 | validation test | 10.480 | pass | 0 |
| Phase 17.7 | validation test | 8.071 | pass | 0 |
| Phase 17.8 | validation test | 23.209 | pass | 0 |
| Phase 17.10 airflow sanity | validation test | 9.135 | pass | 0 |
| Phase 18 helper import | helper | 0.971 | pass | 0 |
| Phase 18.0 legacy alias | array benchmark | 12.115 | pass | 0 |
| Phase 18.20 | array benchmark | 15.045 | pass | 0 |
| Phase 18.21 | array profiler | 21.276 | pass | 4 |
| Phase 18.21 legacy alias | array profiler | 39.555 | pass | 4 |
| Phase 18.22 | validation test | 1.534 | pass | 0 |
| Phase 18.23 | validation test | 1.410 | pass | 0 |
| Phase 18.24 | validation test | 1.581 | pass | 0 |
| Phase 18.26 | array benchmark | 6.719 | pass | 0 |

Phase 18.0 is a compatibility alias for the Phase 18.20 benchmark. The two
Phase 18.21 commands are also compatibility aliases for the same full-year
profiling implementation. Their zero return codes establish command survival;
they are not counted as additional assertion coverage. Each profiler invocation
created logs-on/off CSV and text reports only within its isolated directory.

Aggregate collection used:

```powershell
.\.venv\Scripts\python.exe -m pytest --collect-only -q
```

It collected 53 tests in 3.29 seconds (6.1 seconds process wall time). Aggregate
execution used `.\.venv\Scripts\python.exe -m pytest -q` and returned 53 passed
in 17.32 seconds (20.6 seconds process wall time).

There were no environment failures, corrupted tests, regressions, or unsupported
behaviors in this run. No command changed Git status, created or modified a file
outside its isolated artifact directory, or changed a protected user-file hash.
