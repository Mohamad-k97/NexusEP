# Canonical scenario schema version 1

## Python model layout

The executable schema is intentionally split by responsibility:

```text
nexusep/schema/
  scenario.py
  common.py
  geometry.py
  weather.py
  outputs.py
  versions/
    v1.py

nexusep/scenarios/
  loader.py
  validation.py
  examples/
```

`ScenarioV1` is a frozen Pydantic model with `extra="forbid"`. No canonical
field has a validation alias, and arbitrary mapping-like objects are not
accepted as substitutes for declared models. Legacy keys and permissive input
shapes belong in a separate compatibility importer.

## Covered sections

The root model covers schema version and use case, metadata, deterministic
random seed, fixed simulation period, enabled geometry features, the building /
dwelling / zone hierarchy, surfaces and openings, occupants and schedules,
systems and their control setpoints/capacities, weather source and timestep
weather, and output configuration.

Models are frozen and collection fields normalize to tuples. Numeric fields
reject NaN and infinity and carry field-specific bounds. Datetimes remain
timezone-aware. Paths become resolved `Path` values before the model is handed
to callers.

## Validation layers

1. Pydantic validates required fields, types, literals, ranges, extra keys, and
   local model invariants.
2. Semantic validation checks global ID uniqueness, ancestry, references,
   schedule coverage, reciprocal topology, weather/source policy, timestamp
   alignment, and path resolution.
3. The canonical compiler validates graph-level ownership, directionality,
   connection ordering, and digest invariants.

All failures occur before engine initialization. Structural and semantic errors
are aggregated as stable JSON paths with error types and messages.

