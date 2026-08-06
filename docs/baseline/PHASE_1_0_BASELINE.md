# Phase 1.0 — frozen baseline

Captured before recovery work on **2026-08-05T17:01:06.2484253+02:00** in
`C:\Works\NexusEP\NexusEP`. The Windows time zone was `W. Europe Standard
Time` (Europe/Rome; UTC+02:00 at capture time).

This report is the only file created by Phase 1.0. No test, benchmark, profile,
formatter, package installer, or Phase 16–18 script was run. In particular, no
existing output was regenerated. Hashes are lowercase SHA-256 unless a column
explicitly says Git blob (SHA-1).

## Repository anchor

| Field | Frozen value |
|---|---|
| Branch | `main` |
| HEAD | `7d2729173146536771935ffa92eabaa3c4000c53` |
| Subject | `arraywise` |
| Author/commit time | `2026-07-03T18:59:43+02:00` |
| Upstream | `origin/main` |
| Cached ahead/behind | `+0 / -0` |
| Origin | `https://github.com/Mohamad-k97/NexusEP.git` |
| Git | `2.44.0.windows.1` |
| OS | `Microsoft Windows NT 10.0.26200.0` |

The ahead/behind value uses the locally cached `origin/main`; no fetch was
performed. HEAD identifies every unchanged tracked source file. There were no
staged changes, conflicts, or submodule status entries.

## Working-tree snapshot before this report was written

Exact `git status --short --branch`:

```text
## main...origin/main
 M .spyproject/config/backups/workspace.ini.bak
 M .spyproject/config/workspace.ini
 M nexusep/data/abbey/config/abbey_config.jsonc
?? fast_shadow_results.csv
?? polygon_shadow_results.csv
?? shadow_cache_clustered_128_q16.npz
?? shadow_cache_exact_q16.npz
?? ubep.md
```

Tracked local modifications:

| Status | Path | Bytes | Current SHA-256 | HEAD Git blob | Numstat |
|---|---|---:|---|---|---:|
| modified | `.spyproject/config/backups/workspace.ini.bak` | 283 | `e521ccee07de92560c9cdd5d0956397cf596fa1c77dfdffb7dc697d74f12ee48` | `4171283e374dc2317d1ae07f650f15ac38631b82` | `1 + / 1 -` |
| modified | `.spyproject/config/workspace.ini` | 283 | `e521ccee07de92560c9cdd5d0956397cf596fa1c77dfdffb7dc697d74f12ee48` | `4171283e374dc2317d1ae07f650f15ac38631b82` | `1 + / 1 -` |
| modified | `nexusep/data/abbey/config/abbey_config.jsonc` | 28,115 | `c1c9d88f2578a1c8ae6cff4a1e9cf90c10905c7f4bde5e1c0be314ff9337aebf` | `7d162a2c47f11edb04cc40393798620a6756b00a` | `45 + / 4 -` |

Untracked files present at capture:

| Path | Bytes | SHA-256 |
|---|---:|---|
| `fast_shadow_results.csv` | 15,794,694 | `47bdd54f292c388bbb8e9a61ceb155d2493e8de3308ad448896868ab2cbff8ca` |
| `polygon_shadow_results.csv` | 1,701,867 | `6778ed5f5a8ef1689f5952d000fc700daf48a8ce1d296d5d26ba3ebebfd0ca0a` |
| `shadow_cache_clustered_128_q16.npz` | 253,611 | `e77da188553a4eb96cef8468fdee03ee3cdef79fbb56456f639027a8714a0665` |
| `shadow_cache_exact_q16.npz` | 39,416,429 | `1c8ea8afb67c069f23d2bcd49432890badef0bf2d1715ca3bb1fd35d988fb965` |
| `ubep.md` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The protected `.spyproject/` files, Abbey configuration, and root CSV/NPZ
files were read only. Their timestamps and contents were not changed. The
tracked diff summary was 47 insertions and 6 deletions across the three
modified files.

## Python installations

`python` resolved first to `C:\Python314\python.exe`; it reported CPython
3.14.5, 64-bit, with `sys.prefix == sys.base_prefix == C:\Python314`. The
project declares `requires-python = ">=3.10"`.

Interpreters found on PATH, through the Python launcher, through Conda, or at a
registered/directly discovered installation path were probed individually:

| Interpreter | Version | Discovery/condition |
|---|---|---|
| `C:\Python314\python.exe` | CPython 3.14.5, 64-bit | first on PATH; `py` default |
| `C:\ProgramData\Miniconda3\python.exe` | CPython 3.10.16, 64-bit | directly probed base install |
| `C:\ProgramData\Miniconda3\envs\eureca\python.exe` | CPython 3.10.20, 64-bit | on PATH |
| `C:\Users\Mohamad\miniconda3\envs\eureca\python.exe` | CPython 3.9.23, 64-bit | on PATH; Conda prefix-only entry; below project minimum |
| `C:\Users\khajmoh18975\AppData\Local\miniconda3\python.exe` | CPython 3.14.4, 64-bit | on PATH; current Conda `base` |
| `C:\Users\khajmoh18975\AppData\Local\miniconda3\envs\eureca\python.exe` | CPython 3.9.23, 64-bit | Conda `eureca`; below project minimum; startup errors noted below |
| `C:\Users\khajmoh18975\AppData\Local\Programs\Python\Python312\python.exe` | CPython 3.12.2, 64-bit | on PATH; `py -3.12` |
| `C:\Users\khajmoh18975\AppData\Roaming\uv\python\cpython-3.14.6-windows-x86_64-none\python.exe` | CPython 3.14.6, 64-bit | `py` launcher registration (`Astral/CPython3.14.6`) |

PATH order for `python.exe` was: Python 3.14.5; ProgramData `eureca` 3.10.20;
the `C:\Users\Mohamad` `eureca` 3.9.23; local Miniconda base 3.14.4; Python
3.12.2; then the WindowsApps alias. `python3.exe` resolved only to the
WindowsApps alias. No repository-local `.venv`, `venv`, `env`, or `.conda`
directory was present.

The registry also advertised Python 3.11 at
`C:\Users\khajmoh18975\AppData\Local\anaconda3`, but that `python.exe` did not
exist. Treat this as a stale registration, not an installation. The local
Miniconda `eureca` interpreter emitted `.pth` startup errors including missing
`urllib` and `_distutils_hack`, although it still reported version 3.9.23. An
independent `uv python list --only-installed` could not complete because the
UV cache was access-denied, so the launcher-visible UV 3.14.6 interpreter is
known but a complete UV-managed inventory is not guaranteed.

## Phase 16–18 script/module inventory

Inventory boundary: executable-looking files with a Phase 16–18 identity in
their filename or content are included, along with the v0.4/v0.5 object-runner
baselines and the shared array profiler that explain the existing profiles.
All entries below are tracked, unchanged relative to HEAD, and therefore also
anchored by the commit SHA above.

| Physical path | Classification | Declared/effective identity | SHA-256 |
|---|---|---|---|
| `nexusep/abbey/run_test_phase_16_0_validation_harness.py` | validation test | Phase 16.0 harness; also supplies factories/assertions to later tests | `2d1d647bd6e1981f70fb1b48655d876f3f6bf4d29528a0b7c61c57d4bab49bf4` |
| `nexusep/abbey/run_test_phase_16_1_validation_harness.py` | validation test | Phase 16.1 passive thermal sanity | `67c205901135395d96fe87e9ef1d7830b36cad96486c0e487556108b2c71cb76` |
| `nexusep/abbey/run_test_phase_17_1_model_rename.py` | validation test | Phase 17.1 public model rename/compatibility | `e39ff3453c775a1ae1110101d5aa22537a24946f7a014b71f89e2ecaa14e0330` |
| `nexusep/abbey/run_test_phase_17_2_performance_input_contract.py` | validation test | Phase 17.2 performance-input contract | `1350bce3daf8a03151b4025a4a8e5192caba1ced558e1bd3d21a9cfaf11a49d0` |
| `nexusep/abbey/run_test_phase_17_3_engine_to_performance_adapter.py` | validation test | content is Phase 18.23 reference-vs-fast thermal kernel comparison | `70b277c2ea4990eeb8e51c455a8de9b083f9ca8f74313b56afbf4955f22a2dd0` |
| `nexusep/abbey/run_test_phase_17_4_observation_contract.py` | validation test | Phase 17.4 engine-to-observation contract | `a5e2bf004ce6e180774bbd2e828643c22600063c1be95183831ed0f699ed49f5` |
| `nexusep/abbey/run_test_phase_17_5_legacy_fallback_quarantine.py` | validation test | content is Phase 18.24 reference-vs-fast moisture kernel comparison | `1736a1dc2a985b50aaeeac7b57d43d6928d87992f29fd2c43a4c0c2ba613a5e3` |
| `nexusep/abbey/run_test_phase_17_6_runner_integration.py` | validation test | content is Phase 18.22 reference-vs-fast action scoring comparison | `dc2891ccbb5da7d74947525364e7ba0ac33919d6ef89d429baf6e9e36a1426da` |
| `nexusep/abbey/run_test_phase_17_7_debug_outputs.py` | array benchmark | content is Phase 18.26 one-zone 8,760-hour shoebox benchmark | `8fab25e7053460b9e7b73341e974102ee329847d0587865f0ba0990490379af4` |
| `nexusep/abbey/run_test_phase_17_8_yearly_outputs.py` | validation test | Phase 17.8 yearly/minimal output contract; writes only inside temporary directories during tests | `0df82ac6ed2e6b0b2b50cc8d633cdc46e1c11d10ae38198ce387b21e69968414` |
| `nexusep/abbey/test.py` | validation test | content declares Phase 17.10 airflow sanity | `00797722367805639ed6f2d0cee96bae1f7569e77c34e1393aa1430a35d803d7` |
| `nexusep/abbey/run_test_phase_18_validation_helpers.py` | helper | shared small deterministic inputs/assertions for Phase 18 array tests | `46481d272c2d4dad5bac62751cd5611ce6a6413d214d2ab7c210177e8f001403` |
| `nexusep/abbey/arrays/profiler.py` | helper | array and optional old/object-runner profiling plus CSV export; header calls this “Phase 16” | `de10f38a7476d5f976e63142106be03aa4bf01713ff03de8b6c5d23554f39138` |
| `nexusep/abbey/run_test_phase_18_0.py` | array benchmark | content is Phase 18.20 5-zone/4-person 8,760-hour benchmark | `e1baf361da6b44c538d571b61926a9dd76dadde0334210f720661f950fd08405` |
| `nexusep/abbey/run_test_18_21_profiling.py` | array benchmark | Phase 18.21 cProfile run of the Phase 18.20 array benchmark, logs on/off | `ee5382b305fbe46667f4a4a67c76e37c55e0e7f5117e1faec11a046395207587` |
| `nexusep/abbey/run_test_v0_4.py` | object-runner profile | full AbbeySimulation object-runner smoke/debug/yearly/quick profiles; optional Phase 16 suite | `ec2ee4acb66015d74228c649be5de4004a0a98ec0cba188337758fc6803ccde3` |
| `nexusep/abbey/run_test_v0_5_0.py` | object-runner profile | AbbeySimulation object-runner speed benchmark profiles | `1ea9a18f511b0c1f6a7c01098724d2ba998f665bed321e6ef1267582c024131e` |

Files containing Phase notes but excluded from the script list because they are
production implementation modules are:

```text
nexusep/abbey/arrays/action_kernels_numba.py
nexusep/abbey/arrays/execution_kernels_numba.py
nexusep/abbey/arrays/numba_prep.py
nexusep/abbey/arrays/numba_support.py
nexusep/abbey/arrays/physics_kernels_numba.py
nexusep/abbey/arrays/timestep_numba_ready.py
nexusep/abbey/building/performance.py
nexusep/abbey/simulation/runner.py
```

Older `run_test_v0_1.py` through `run_test_v0_3.py` are also excluded because
they do not declare a Phase 16–18 identity. They remain exactly identified by
HEAD like all other unchanged tracked source.

## Existing generated artifacts and hashes

### Tracked Phase profile outputs

| Path | Bytes | Filesystem timestamp | SHA-256 |
|---|---:|---|---|
| `nexusep/abbey/profiling_outputs/abbey_8760_logs_off_profile.csv` | 21,794 | `2026-07-03T18:56:51.7201954+02:00` | `b37adf7f640bff3349ace6958c8fc8a04de96cead1cea8264ec82f2184abff68` |
| `nexusep/abbey/profiling_outputs/abbey_8760_logs_off_profile.txt` | 8,079 | `2026-07-03T18:56:51.7072387+02:00` | `2129085332f4309a3e55771f0f62c3ea7e6a481249fb07511f9c84b9e519c65c` |
| `nexusep/abbey/profiling_outputs/abbey_8760_logs_on_profile.csv` | 23,175 | `2026-07-03T18:56:45.3829373+02:00` | `720bcb7627ee4f55ee4a595b8f4e78bf1e22040f016e9c0d6bdbedf8c7bc072f` |
| `nexusep/abbey/profiling_outputs/abbey_8760_logs_on_profile.txt` | 8,057 | `2026-07-03T18:56:45.3804247+02:00` | `411708c72246a9a92a3e0a9b1546564606f3b0e9df4bb19660796ce9d6ad7bbd` |
| `nexusep/abbey/profiling_outputs_phase_18_16/cprofile_group_summary.csv` | 1,143 | `2026-07-03T17:30:14.0795594+02:00` | `cd53a7acfb4ba9a578d8fdf064ad262f32a5f4ee0a33b3f7bc06c7307e7792e7` |
| `nexusep/abbey/profiling_outputs_phase_18_16/cprofile_top_functions.csv` | 3,640 | `2026-07-03T17:30:14.0815595+02:00` | `741feb7efbad7e19cfc1070dbd68458fcd747c98c83789d32cd00d7a9982e829` |
| `nexusep/abbey/profiling_outputs_phase_18_16/timing_summary.csv` | 541 | `2026-07-03T17:30:14.0775613+02:00` | `7284f1cd44fa529729a29f7e5d4fc4ef43d9d02b2082cc4bc3e8e83e13ab0515` |

Useful content fingerprints, quoted from the existing files rather than a new
run: Phase 18.16 records `array.total = 4.550492800000029 s` and 8,760 calls at
`0.0005087143949777704 s` per `array.timestep_total`. Phase 18.21 cProfile text
records 6.528 s with logs on and 6.261 s with logs off.

### Untracked root benchmark/cache artifacts

These are the same protected root files listed in the working-tree snapshot,
classified here as generated artifacts. No tracked source contains any of
their four literal filenames, so their generator and Phase association are
unknown.

| Path | Observed structure | SHA-256 |
|---|---|---|
| `fast_shadow_results.csv` | columns start `polygon_id,area,receives_front_sun,...` | `47bdd54f292c388bbb8e9a61ceb155d2493e8de3308ad448896868ab2cbff8ca` |
| `polygon_shadow_results.csv` | columns start `receiver_id,receiver_area,shaded_area,...` | `6778ed5f5a8ef1689f5952d000fc700daf48a8ce1d296d5d26ba3ebebfd0ca0a` |
| `shadow_cache_clustered_128_q16.npz` | six members: `codebook`, `polygon_to_code`, `hour_to_bin`, `n_samples`, `n_levels`, `metadata_json` | `e77da188553a4eb96cef8468fdee03ee3cdef79fbb56456f639027a8714a0665` |
| `shadow_cache_exact_q16.npz` | same six member names | `1c8ea8afb67c069f23d2bcd49432890badef0bf2d1715ca3bb1fd35d988fb965` |

`outputs/abbey/` contained zero files. A tracked older visualization artifact,
`nexusep/abbey/visualization/abbey_v01_test_08.csv`, exists but is not identified
as a Phase benchmark/profile output; for completeness its SHA-256 is
`55341cc8209af1e787fd2a3ce0673d68a45ed3b49dc0609da6b17567cf3c3952`
(3,190,350 bytes).

## Known uncertainty and recovery warnings

1. Physical filenames and declared module names conflict in multiple committed
   scripts. Phase 17.3, 17.5, 17.6, and 17.7 filenames contain Phase 18.23,
   18.24, 18.22, and 18.26 content respectively. Phase 18.20 is physically
   `run_test_phase_18_0.py`; Phase 18.21 is physically
   `run_test_18_21_profiling.py`; Phase 17.10 airflow sanity is physically
   `test.py`. These are committed HEAD contents, not current working-tree
   edits.
2. The run commands written inside the mismatched files point to modules that
   do not exist. The v0.5 script similarly documents
   `run_test_v0_5_speed`, which does not exist under that name.
3. The Phase 16.1 docstring names a nonexistent
   `run_test_phase_16_1_passive_thermal_sanity.py`, and its import of the 16.0
   harness is unqualified. Invocation behavior therefore depends on the
   working directory/import path and has not been validated.
4. `run_test_v0_4.py --run-phase16-suite` references Phase 16.2 through 16.7
   modules. None of those six files exists at HEAD.
5. The `profiling_outputs_phase_18_16` files match export names in
   `arrays/profiler.py`, but no dedicated Phase 18.16 runner is present and the
   input/settings that produced them are not encoded in filenames. Provenance
   beyond committed content and timestamps is uncertain.
6. `run_test_18_21_profiling.py` uses a relative `Path("profiling_outputs")`.
   The tracked results live under `nexusep/abbey/profiling_outputs`, so their
   location implies a particular historical working directory; this was not
   reproduced. Filesystem timestamps are evidence, not guaranteed generation
   times.
7. No Phase script was executed during the freeze. Runtime pass/fail state,
   dependency completeness, and which Python installation originally generated
   each profile remain unknown.
8. The remote repository was not contacted. The current local commit and
   cached tracking relation are exact; the live remote state is not asserted.

## Comparison rule for later phases

- Compare tracked source to HEAD `7d2729173146536771935ffa92eabaa3c4000c53`.
- Compare protected/local files and generated artifacts by the SHA-256 values
  above, not timestamps alone.
- Compare Phase scripts by physical path **and** declared/effective identity;
  do not infer identity from a mismatched filename.
- Treat any additional `git status` entry other than this new report as a
  post-freeze change unless its hash matches an entry above.
