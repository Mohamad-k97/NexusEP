# Phase 3 test and script inventory

Validation category: **verification**

Pytest is the only correctness-test authority. Compatibility modules do not
contain a second copy of assertions: they delegate to the listed pytest file.
Benchmark/profile entry points delegate to code below `benchmarks/` and are
excluded from correctness lanes.

| Compatibility entry point | Role / pytest owner | Lane |
|---|---|---|
| `run_test_phase_16_0_validation_harness.py` | `tests/phase16/test_16_0_validation_harness.py` | integration |
| `run_test_phase_16_1_validation_harness.py` | `tests/phase16/test_16_1_passive_thermal_sanity.py` | integration |
| `run_test_phase_17_1_model_rename.py` | Phase 17.1 compatibility contract | contract |
| `run_test_phase_17_2_performance_input_contract.py` | Phase 17.2 input contract | contract |
| `run_test_phase_17_3_engine_to_performance_adapter.py` | Phase 17.3 adapter contract | contract |
| `run_test_phase_17_4_observation_contract.py` | Phase 17.4 observation contract | contract |
| `run_test_phase_17_5_legacy_fallback_quarantine.py` | Phase 17.5 fallback contract | contract |
| `run_test_phase_17_6_runner_integration.py` | Phase 17.6 real-runner boundary | integration |
| `run_test_phase_17_7_debug_outputs.py` | Phase 17.7 debug export | integration |
| `run_test_phase_17_8_yearly_outputs.py` | Phase 17.8 output aggregation | integration |
| `run_test_phase_17_10_airflow_sanity.py`, `test.py` | `tests/regression/test_airflow_sanity.py` | unit |
| `run_test_phase_18_22_action_scoring_fast_compare.py` | reference/fast implementation comparison | integration |
| `run_test_phase_18_23_thermal_fast_compare.py` | reference/fast implementation comparison | integration |
| `run_test_phase_18_24_moisture_fast_compare.py` | reference/fast implementation comparison | integration |
| `run_test_phase_18_validation_helpers.py` | fixture/helper compatibility exports; no tests | helper |
| `run_test_phase_18_0.py`, `run_test_phase_18_20_8760_benchmark.py` | array 8,760-step timing | benchmark |
| `run_test_18_21_profiling.py`, `run_test_phase_18_21_profile_8760.py` | array profiler | benchmark |
| `run_test_phase_18_26_shoebox_8760_benchmark.py` | shoebox array timing | benchmark |
| `run_test_v0_1.py` through `run_test_v0_5_speed.py` | object examples, profiles and timing | benchmark |
| `arrays/profiler.py` | compatibility exports for `benchmarks/arrays/profiler.py` | helper |

The historical `tests/phase16`, `tests/phase17`, `tests/phase18`, and
`tests/regression` paths remain import-compatible collections. Collection-time
classification in `tests/conftest.py` assigns each test exactly one execution
lane. New tests must be placed directly in one of `unit`, `contracts`,
`integration`, `annual`, or `benchmarks`.

Print-based success messages and direct `main()` test runners have been
removed. Diagnostic output that is emitted only after a failed numerical
comparison remains useful failure evidence.
