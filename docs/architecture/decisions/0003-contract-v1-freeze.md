# ADR-0003: Canonical contract v1 freeze

- Status: Accepted
- Date: 2026-08-06
- Scope: `multizone_dwelling_v1`, schema version `1.0.0`

## Context

Phases 2.1 through 2.14 established backend-neutral terminology, units, IDs,
time semantics, geometry, weather, graph compilation, strict scenario loading,
timestep inputs, outputs, and adapters. Phase 2.15 runs both adapters through
one conformance suite. Phase 2.16 measures parity without treating either
engine as canonical truth.

The public boundary is now coherent enough to stabilize independently from
the numerical engine results. Freezing the contract does not promote an
engine and does not convert known parity deviations into accepted behavior.

## Decision

Canonical contract v1 is frozen at schema and compiled-graph version `1.0.0`.
Its normative surface is the set listed in `contract_v1_index.md`, including
the machine-readable schemas and unit/term registries, executable frozen
models, strict loader/compiler, typed timestep input, required output tables,
and adapter responsibilities.

The object engine remains `reference_candidate`. The array engine remains
`experimental`. Neither is canonical. The initial parity report is evidence
about the frozen boundary, not a waiver for its contract violations or missing
features.

## Versioning rules

- Files declaring `1.0.0` do not change accepted fields, units, ranges,
  defaults, timestamp meanings, output meanings, or graph ordering.
- Editorial clarifications may be applied only when they do not change
  validation or runtime behavior.
- A backward-compatible optional addition requires a new declared minor
  version, an explicit default/provenance rule, migration coverage, both
  adapter mappings, conformance tests, and refreshed parity evidence.
- A removal, rename, unit change, range narrowing, default change, required
  field addition, ID/time change, or output semantic change requires contract
  version `2.0.0` and a migration path.
- Backend-native debug fields may evolve without a contract version only when
  required canonical outputs and deterministic evidence are unchanged.

## Compatibility and deprecation

Aliases, legacy dict shapes, and implicit units are forbidden in the canonical
loader. A separate compatibility importer may translate them, but it must
emit an audit record and return the same strict canonical object as a native
v1 input. Supported v1 inputs and required outputs remain available for at
least one documented deprecation cycle after a successor is released.

Engine deprecation and promotion continue to follow ADR-0001. Contract freeze
does not relax its conservation, determinism, conformance, or parity gates.

## Consequences

Contributors can rely on one stable semantic boundary while backend physics
continues to converge. New supported behavior is contract-first. Backend-only
features remain explicit capabilities or extensions and cannot silently alter
v1 results.
