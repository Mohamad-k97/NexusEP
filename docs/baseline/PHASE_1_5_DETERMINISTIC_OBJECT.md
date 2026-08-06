# Phase 1.5 — deterministic object-runner reference

The trusted reference is `AbbeySimulation` using a byte-for-byte snapshot of
the current local ABBEY config:

- snapshot: `artifacts/baseline/inputs/abbey_config_phase_1_5.jsonc`
- SHA-256: `c1c9d88f2578a1c8ae6cff4a1e9cf90c10905c7f4bde5e1c0be314ff9337aebf`
- application seed: 20260806
- NumPy seed: 20260806
- Python hash seed: 0
- timezone: Europe/Rome
- start: `2026-01-01T00:00:00+01:00`
- weather: deterministic hourly synthetic provider with no random inputs

Both scenarios use a 60-minute timestep, one building, one dwelling, eight
zones, one person, nine physical system specifications, and 21 configured
behavior actions. The smoke case is 24 hours; the short-year case is 720 hours
(30 days). Each ran twice from a new simulation instance into separate ignored
output directories. The public `SystemState` starts with zero zone entries;
physical systems are owned by the building model and counted there.

| Scenario | Timesteps | Loop samples (s) | Normalized output/run | Repeat result |
|---|---:|---|---:|---|
| smoke | 24 | 0.506, 0.887 | 1.33 MiB | exact |
| short-year | 720 | 10.510, 13.669 | 40.25 MiB | exact |

Fourteen output tables were compared: main/person/zone logger records; zone,
dwelling, and building physics; interzone thermal/airflow; window airflow;
control bridge; action events; and source, source-zone, and source-building
records. For every table:

- column order and dtype strings match exactly;
- row-key order and all categorical/status values match exactly;
- numeric matrices match with `rtol=1e-12`, `atol=1e-12`, and equal NaNs;
- canonical full hashes and normalized CSV hashes match exactly.

Zone energy sums equal dwelling and building zone-energy sums with a maximum
absolute residual of 0 Wh. All recorded energy is non-negative and all
zone/dwelling/building balance flags are true. Every step reports the active
physics-engine path and zero legacy-fallback steps.

Wall-clock timings, profiler measurements, and filesystem timestamps are
explicitly excluded from deterministic comparison. The compact golden,
per-table hashes, tolerances, schema, path indicators, and energy summaries are
in `artifacts/baseline/deterministic_object_manifest.json`. Raw normalized CSVs
remain ignored under `artifacts/benchmarks/phase1_5/object/`.
