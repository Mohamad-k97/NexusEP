# Canonical contracts

`contracts/` contains backend-neutral public semantics.

- `multizone_dwelling_v1.schema.json` defines canonical scenario inputs.
- `multizone_dwelling_v1.units.json` registers every public numeric input and
  required output, including bounds and aggregation meaning.
- `compiled_physics_graph.schema.json` defines the inspectable deterministic
  compiler output consumed by backend adapters.
- `canonical_terms.json` records canonical terms and adapter-only aliases.
- `examples/multizone_dwelling_v1_minimal.json` is the minimal semantic
  conformance fixture.

`tests/contracts/test_multizone_dwelling_v1_contract.py` prevents drift among
the documents, schema, registry, and example without importing either engine.
`tests/contracts/test_ids_time_geometry_graph.py` verifies deterministic ID and
time mapping, geometry requirements, graph compilation, and canonical hashing.

The backend-independent reference implementation is
`nexusep.schema.compile_physics_graph`. Users never author the compiled graph.

The executable version 1 model is `nexusep.schema.scenario.ScenarioV1`; strict
JSON/JSONC loading is provided by `nexusep.scenarios.load_scenario`.

These files do not certify either engine. Engine status and promotion evidence
are governed by `docs/architecture/decisions/0001-dual-engine-policy.md`.

Breaking public changes create a new contract version. Existing versions are
immutable except for clarifications that do not change accepted data or output
meaning.
