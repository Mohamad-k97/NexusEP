# Architecture contracts

This directory defines the contributor-facing policy and the first canonical
scenario contract. These documents describe semantics; neither simulation
engine is currently the canonical source of behavioral truth.

- `decisions/0001-dual-engine-policy.md` — engine status, change routing,
  promotion, and retirement policy.
- `multizone_dwelling_v1.md` — the first narrowly supported use case.
- `glossary.md` — canonical hierarchy and terminology.
- `unit_conventions.md` — public units, ranges, conversion boundaries,
  aggregation, and precision.
- `id_and_time_semantics.md` — stable IDs, deterministic indices, interval
  timestamps, weather alignment, leap years, and daylight saving.
- `geometry_contract.md` — required thermal topology, optional geometry, and
  provenance/default rules.
- `physics_graph_contract.md` — deterministic graph compilation and validation.
- `weather_contract.md` — normalized timestep weather, missing/interpolation
  policy, external sources, and restricted synthetic smoke data.
- `scenario_schema_v1.md` — executable versioned model layout and validation.
- `canonical_loader.md` — strict JSON/JSONC loading, defaults, paths, and audit.
- `decisions/0002-canonical-compilation-boundary.md` — why users author the
  scenario rather than a backend graph.
- `PHASE_2_1_2_4_GATE.md` — completion evidence and remaining conformance work.
- `PHASE_2_5_2_7_GATE.md` — ID/time/geometry/graph compilation evidence.
- `PHASE_2_8_2_10_GATE.md` — weather, executable schema, and loader evidence.
- `canonical_timestep_and_outputs.md` — strict per-step inputs and normalized
  required/debug outputs.
- `backend_adapters.md` — canonical object/array encoding, decoding, defaults,
  and experimental limitations.
- `PHASE_2_11_2_14_GATE.md` — executable adapter evidence and known deviation.
- `../../contracts/` — machine-readable schema, unit registry, terminology,
  and the minimal conformance scenario.

The architecture gate remains governed by the Phase 1 baseline until the
promotion evidence in ADR-0001 is complete.
