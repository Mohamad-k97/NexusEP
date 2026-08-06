# Phase 1.7 — array-runner benchmark

The surviving Phase 18.20 scenario has 8,760 hourly timesteps, one building,
one dwelling, five zones, four people, five systems, and seven actions.
Thermal, airflow, CO2, moisture, and daylight kernels are enabled; acoustics is
disabled. The hardware, OS, interpreter, repository commit/dirty marker,
package versions, and thread environment are embedded in
`artifacts/baseline/array_benchmark.json`.

One 24-step warm-up was excluded. Three full repetitions were then measured for
each logging mode. The reference timestep path is NumPy/Python and does not call
Numba dispatchers, so the separately reported first-timestep number is not
labeled as JIT compilation cost even though Numba 0.66.0 is installed.

| Metric (median) | Logs off | Logs on |
|---|---:|---:|
| input construction | 0.0154 s | 0.0172 s |
| encoding/compilation | 0.0779 s | 0.0417 s |
| log allocation | ~0 s | 0.0006 s |
| first timestep | 1.225 ms | 2.049 ms |
| steady-state loop | 10.261 s | 10.228 s |
| total loop | 10.262 s | 10.230 s |
| loop range | 3.649 s | 4.058 s |
| simulated hours/s | 853.6 | 856.3 |
| decode/output | 0.0205 s | 2.3466 s |
| peak RSS | 145.3 MiB | 232.6 MiB |
| raw state arrays | 1.212 MiB | 1.212 MiB |
| raw log arrays | 0 | 19.916 MiB |
| decoded DataFrames | 0.008 MiB | 24.797 MiB |

The large loop ranges show contemporaneous machine load; medians are therefore
the comparison statistic. Logging does not materially change the loop because
logs are dense preallocated arrays, but it adds allocation, memory, and
post-loop decoding cost.

All final arrays and logs have identical hashes across the three repetitions.
Zone/person states are finite, temperature/CO2/RH bounds pass, building demands
are non-negative, and final state exactly matches the final log slice. The
object golden also repeats exactly, has balanced non-negative energy, remains on
the engine path, and completed both annual profiles.

Statewise object-to-array equivalence is not claimed. The authoritative object
baseline is a one-person/eight-zone config, while the surviving array benchmark
is a synthetic four-person/five-zone readable input. Frozen source contains no
authoritative adapter that maps one scenario into both runners. This is a known
deviation, not a numerical pass: shared structural, physical, logging,
repeatability, and energy/path invariants are checked, but per-field values are
not comparable until a shared scenario contract is introduced.

The existing Phase 18.21 cProfile artifacts are linked and hashed in the JSON
report. Their top cumulative paths include `run_array_timestep`,
`run_array_timestep_arrays`, action scoring, person dynamics, execution, and
daylight.

