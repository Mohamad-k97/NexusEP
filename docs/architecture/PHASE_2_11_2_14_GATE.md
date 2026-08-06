# Phase 2.11–2.14 gate

## Evidence

| Requirement | Evidence | Status |
|---|---|---|
| typed, immutable timestep input | `nexusep/schema/timestep.py` | pass |
| exact entity/time/weather/graph coverage | `validate_step_input_for_scenario` tests | pass |
| derived values excluded from input | separate `DerivedStepValues` model | pass |
| backend-neutral required output | `CanonicalZoneStepResult` and exact-field test | pass |
| step and run zone/dwelling/building energy aggregation | model invariants and adapter tests | pass |
| optional backend debug fields | `CanonicalDebugResult` | pass |
| object canonical adapter | real unified physics step, native-record translation test | pass |
| no canonical hard-coded dwelling ID | canonical IDs asserted; `dwelling_1` absent | pass |
| object fallback quarantine | direct engine call; no legacy fallback branch | pass |
| array canonical adapter | real array timestep kernel and decoded-ID test | pass |
| deterministic array ID registry | canonical-vs-array registry assertion | pass |
| free-form array input removed from supported path | adapter accepts only typed step; internal compiler payload | pass |
| array mutations/columns hidden | adapter boundary provenance test | pass |

Run the gate with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/adapters -q
```

## Compatibility evidence and deviation

For the supported canonical scenario, the object adapter exposes native engine
zone records only in debug output, and tests verify that the normalized rows
cover the same original zone IDs. The existing object engine remains unchanged;
the adapter calls it directly.

The Phase 1 deterministic object fixture itself has eight zones and one
occupant, while `multizone_dwelling_v1` requires at least two occupants. It
therefore cannot be relabeled as a valid v1 canonical scenario without a
separate, reviewed migration. Its frozen Phase 1 hashes remain authoritative
for the legacy runner. Exact legacy-fixture-through-canonical-adapter parity is
recorded as pending migration rather than claimed from mismatched scenarios.

## Experimental-array gaps

The adapter rejects action events and non-occupant internal gains until the
array kernel has explicit injection arrays. Surface topology, pressure, fan
power, and window-flow limitations are returned as warnings/default provenance.
These gaps block array-engine promotion under ADR-0001 but do not re-open the
validated free-form dictionary path.
