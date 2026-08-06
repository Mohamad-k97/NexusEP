# Phase 2.5–2.7 compilation gate

- Recorded: 2026-08-06
- Scenario contract: `multizone_dwelling_v1` / `1.0.0`
- Compiled graph contract: `1.0.0`
- Backend certification: none

## Exit status

| Phase | Status | Evidence |
|---|---|---|
| 2.5 IDs and time | complete | Canonical IDs are globally unique external strings with explicit ancestry. Per-type array indices are lexicographically compiled and losslessly decoded. The fixed elapsed-time clock defines timezone agreement, integer `timestep_index`, half-open intervals, weather alignment, exclusive derived end, DST, and leap-day behavior. |
| 2.6 geometry tiers | complete | The input schema requires only thermal topology plus enabled-feature data, explicit orientation convention, defaults, and provenance. The minimal scenario compiles without vertices, polygons, geographic coordinates, shading objects, GIS references, or hidden defaults. |
| 2.7 physics graph | complete | ADR-0002 makes compilation mandatory before backend execution. The reference compiler emits and validates an explicit exterior node, reciprocal interzone topology, deterministic ordering, inspectable canonical JSON, provenance, and a SHA-256 digest. |

## Reference compilation

Compiling `contracts/examples/multizone_dwelling_v1_minimal.json` produces:

- 3 nodes: one exterior and two zones;
- 5 connections: two exterior surfaces, one reciprocal interzone surface pair,
  and two openings;
- 8 zone-attached systems; and
- graph SHA-256
  `885168497f39af100709e59c32516adac8dcb4f5cc87d5a5a379015f453f2b32`.

The hash covers canonical JSON containing the scenario version, ID registry,
time axis, geometry configuration, nodes, connections, systems, and provenance.
Reordering zones, surfaces, openings, systems, occupants, schedules, weather,
or enabled features produces the same structure, indices, serialization, and
hash.

## Executable evidence

```powershell
.venv\Scripts\python.exe -m pytest tests\contracts -q
.venv\Scripts\python.exe -m ruff check nexusep\schema tests\contracts
```

Expected focused result at this gate: `28 passed`.

The tests also reject cross-type ID collisions, unknown indices, incorrect
parent references, timezone/offset disagreement, authored end times,
non-boundary timestamps, weather gaps/misalignment, broken interzone pairs,
oversized openings, missing geometry declarations, orphan graph structures,
and digest tampering. Spring/fall DST transitions and a leap day are covered.

## Boundary and remaining promotion evidence

`nexusep.schema.compile_physics_graph` is the canonical reference compiler. It
does not import either backend. Existing object graph construction and array
registries remain backend-native adapters and are not yet certified as
consumers of this graph.

The rule that compilation is mandatory is frozen here; wiring both runners to
the compiled boundary is subsequent adapter work. Neither backend becomes
canonical until ADR-0001 promotion evidence, including scenario-level parity,
is complete.

