# Initial parity report for `multizone_dwelling_v1`

Validation category: **verification**. This is cross-backend consistency
evidence; neither experimental backend is an accepted reference, so it is not
yet comparative validation.

## Scope and method

The canonical four-hour, two-zone, two-occupant example was run through fresh
object and array adapters twice. Both runs used the same compiled graph, seed,
timezone-aware interval clock, weather rows, occupant schedules, availability,
and deterministic control policy. The policy exercises heating, cooling,
ventilation, lighting, windows, and shading.

Both canonical adapters report engine/adapter version `2.17.0`; the scenario
schema and compiled graph report contract version `1.0.0`.

Comparisons use per-quantity tolerances. Cumulative electrical energy drift is
checked separately from instantaneous power. No global tolerance is used.

## Measured classification

| Classification | Count | Interpretation |
|---|---:|---|
| exact match | 181 | identical categorical or numerical values |
| tolerance match | 5 | two state values and three conservation residuals within declared quantity-specific tolerances |
| expected model difference | 22 | physical solver results differ beyond tolerance; neither backend is canonical |
| missing feature | 0 | all quantities in the first harness are available |
| contract violation | 0 | no canonical command or output-contract violation remains in this scenario |
| defect | 0 | no invariant or repeat-run defect detected |

Both fresh repeat runs were exact for each engine. Canonical graph hashes,
decoded IDs, timestamps, every required weather field, controls, occupancy,
and occupant locations matched exactly.

## Quantity results

The eight zone/timestep comparisons for each physical-state quantity produced
these absolute-difference ranges:

| Quantity | Declared `atol` | Observed absolute range | Classification policy |
|---|---:|---:|---|
| air temperature | 0.10 C | 0.0470 to 1.9776 C | tolerance or expected model difference |
| relative humidity | 0.005 fraction | 0.00792 to 0.14519 | expected model difference |
| CO2 | 5 ppm | 0.0587 to 154.4226 ppm | tolerance or expected model difference |
| power | 0.000001 W | 0 W | exact/tolerance or contract violation |
| cumulative energy | 0.01 Wh | 0 Wh | checked independently from instantaneous power |

The former lighting discrepancy was traced to the object bridge passing a watt
command as both a binary on-state and an unconstrained daylight request. The
bridge now converts requested watts to a fraction of installed capacity; both
engines deliver the requested wattage and produce identical electrical energy.
A separate sunny-midday adapter regression also checks that both engines
receive identical SPA/plane-of-array window solar gains derived from explicit
site and surface geometry.

## Invariants and conservation

Both engines passed finite-output, bounded-humidity/nonnegative-power, and
zone-to-building electrical energy aggregation checks at every timestep.
Both adapters expose independently calculated thermal, moisture, and CO2
balance residuals. Maximum absolute residuals over the run are 1.19e-12 W and
4.27e-12 W for object/array heat balances, 1.32e-19 kg/s and 6.78e-20 kg/s for
moisture, and 1.25e-20 kg/s and 1.95e-20 kg/s for CO2. These pass the frozen
near-numerical-precision tolerances.

## Promotion impact

The report does not promote either engine. Physical-state model differences
require reviewed expectations or solver convergence before ADR-0001 promotion
criteria can be satisfied.

Every individual value, tolerance, difference, rationale, and classification
is retained in `artifacts/baseline/phase_2_16_initial_parity.json`.
