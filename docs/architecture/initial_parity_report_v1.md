# Initial parity report for `multizone_dwelling_v1`

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
| exact match | 165 | identical categorical or numerical values |
| tolerance match | 2 | within the declared quantity-specific tolerance |
| expected model difference | 22 | physical solver results differ beyond tolerance; neither backend is canonical |
| missing feature | 8 | four array pressure-consumption rows, one array surface-graph gap, and three unavailable balance residuals |
| contract violation | 11 | two lighting-power differences, two resulting total-power differences, and seven cumulative-energy drift rows |
| defect | 0 | no invariant or repeat-run defect detected |

Both fresh repeat runs were exact for each engine. Canonical graph hashes,
decoded IDs, timestamps, mapped weather other than unsupported pressure,
controls, occupancy, and occupant locations matched exactly.

## Quantity results

The eight zone/timestep comparisons for each physical-state quantity produced
these absolute-difference ranges:

| Quantity | Declared `atol` | Observed absolute range | Classification policy |
|---|---:|---:|---|
| air temperature | 0.10 C | 0.0470 to 1.9776 C | tolerance or expected model difference |
| relative humidity | 0.005 fraction | 0.00792 to 0.14519 | expected model difference |
| CO2 | 5 ppm | 0.0587 to 154.4226 ppm | tolerance or expected model difference |
| power | 0.000001 W | 0 or the lighting deviations below | exact/tolerance or contract violation |
| cumulative energy | 0.01 Wh | 0 to 80 Wh | checked independently; deviations classified as contract violations |

The object backend reports 160 W for an 80 W living-zone lighting request and
90 W for a 45 W bedroom request. The array backend reports the requested
wattage. This propagates to total electrical power and cumulative energy. The
harness classifies the discrepancy as a contract violation because the same
canonical physical command is presented to both adapters. It is not hidden by
a larger tolerance.

## Invariants and conservation

Both engines passed finite-output, bounded-humidity/nonnegative-power, and
zone-to-building electrical energy aggregation checks at every timestep.
Comparable thermal, moisture, and CO2 mass-balance residuals are not exposed by
both adapters, so those three checks are `missing_feature`, not pass.

## Promotion impact

The report does not promote either engine. Array pressure consumption and
surface-graph execution remain missing. Comparable physical conservation
residuals remain missing. Lighting command semantics and resulting energy
drift must be resolved. Physical-state model differences require reviewed
expectations or solver convergence before ADR-0001 promotion criteria can be
satisfied.

Every individual value, tolerance, difference, rationale, and classification
is retained in `artifacts/baseline/phase_2_16_initial_parity.json`.
