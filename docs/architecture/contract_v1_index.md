# Canonical contract v1 index

This is the publication index for frozen `multizone_dwelling_v1` contract
version `1.0.0`.

## Normative machine-readable definitions

| Subject | Definition |
|---|---|
| scenario schema | `contracts/multizone_dwelling_v1.schema.json` |
| executable scenario models | `nexusep/schema/scenario.py`, `common.py`, `geometry.py`, `weather.py`, `versions/v1.py` |
| field names and units | `contracts/multizone_dwelling_v1.units.json` |
| canonical terms and aliases | `contracts/canonical_terms.json` |
| compiled graph schema | `contracts/compiled_physics_graph.schema.json` |
| canonical example | `contracts/examples/multizone_dwelling_v1_minimal.json` |
| strict loader and validation | `nexusep/scenarios/loader.py`, `validation.py` |
| deterministic compiler | `nexusep/schema/compiler.py` |
| timestep input | `nexusep/schema/timestep.py` |
| required/debug outputs | `nexusep/schema/outputs.py` |
| backend adapters | `nexusep/adapters/object_engine.py`, `array_engine.py` |

## Normative semantic specifications

- `multizone_dwelling_v1.md`: supported and excluded use cases.
- `glossary.md`: hierarchy and canonical terms.
- `unit_conventions.md`: units, ranges, precision, and aggregation.
- `id_and_time_semantics.md`: stable IDs, deterministic indices, and clock.
- `geometry_contract.md`: required/optional geometry and provenance.
- `physics_graph_contract.md`: graph ownership, construction, and validation.
- `weather_contract.md`: weather values, alignment, and missing-value policy.
- `scenario_schema_v1.md` and `canonical_loader.md`: validation boundary.
- `canonical_timestep_and_outputs.md`: input/output specifications.
- `backend_adapters.md`: lowering, decoding, defaults, and limitations.
- ADR-0001, ADR-0002, and ADR-0003: engine policy, compilation boundary,
  and version freeze.

When prose and executable validation disagree, contract v1 is not silently
reinterpreted. The mismatch is a contract defect to be resolved through the
versioning rules in ADR-0003.

## Evidence

- `tests/contracts/`: backend-independent contract, ID/time, graph, loader,
  and weather gates.
- `tests/adapters/`: typed boundary and adapter regression gates.
- `tests/conformance/test_backend_contract_v1.py`: the same black-box
  conformance suite for object and array adapters.
- `artifacts/baseline/phase_2_15_conformance.json`: executable conformance
  result.
- `artifacts/baseline/phase_2_16_initial_parity.json`: all measured and
  classified first-parity comparisons.
