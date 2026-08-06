# Phase 1.6 — object-runner performance baseline

Measurements used the deterministic Phase 1.5 config, seeds, weather, timezone,
and hourly clock. One unmeasured 24-step warm-up ran separately. Small cases
have three repetitions; annual cases have two. Results report median and full
range, and peak memory is process RSS sampled every 20 ms.

The scenario has one building, one dwelling, eight zones, one person, nine
physical system specifications, and 21 configured behavior actions.

Hardware was a 13th Gen Intel Core i7-1355U (10 physical/12 logical cores) with
16,849,256,448 bytes RAM on Windows 11 build 26200. No OMP, MKL, OpenBLAS,
Numba, VECLIB, or NumExpr thread-count override was set.

| Case | Reps | Loop median (range), s | ms/step | Simulated h/s | Peak RSS |
|---|---:|---:|---:|---:|---:|
| one step, logs on | 3 | 0.0138 (0.0040) | 13.84 | 72.27 | 118.1 MiB |
| 168-hour integration, logs on | 3 | 2.840 (0.842) | 16.91 | 59.15 | 142.6 MiB |
| 8,760 hours, logs off | 2 | 185.114 (2.742) | 21.13 | 47.32 | 1,149.4 MiB |
| 8,760 hours, logs on | 2 | 198.565 (59.873) | 22.67 | 45.14 | 1,495.3 MiB |

The logs-off annual samples were 183.743 and 186.485 seconds. Logs-on samples
were 228.501 and 168.629 seconds, so the wide range is part of the baseline and
must not be hidden by the median. Initialization itself was about 0.014–0.016
seconds in annual cases after import. Fresh-process module import median was
3.762 seconds and fresh-process total median was 4.214 seconds.

“Logs off” replaces the public `SimulationLogger` with a null implementation;
building-physics output records remain enabled and retained. Logs off retained
505,722 rows, while logs on retained 593,322. The deterministic serialized
24-hour and 720-hour output sizes are reported in Phase 1.5; annual output size
is represented by retained row counts and RSS growth to avoid writing a very
large duplicate raw bundle.

cProfile was collected separately over the 168-step integration case so it
does not distort annual timing. The leading cumulative call paths were
`AbbeySimulation.step`, `_step_inner`, `execute_timestep`,
`_run_building_performance_if_enabled`, `_run_physics_engine`, and
`run_building_physics_step`. Full text/CSV profiles are ignored under
`artifacts/profiles/phase1_6_object/`; the top functions and their hashes are in
`artifacts/baseline/object_profile.json`.
