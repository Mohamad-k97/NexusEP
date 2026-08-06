# ADR-0001: Dual-engine policy

- Status: Accepted
- Date: 2026-08-06
- Decision owners: NexusEP maintainers
- Scope: object and array simulation backends

## Context

NexusEP currently has an object engine and an array engine. Phase 1 established
repeatable baselines for both, but it did not establish statewise parity on one
authoritative scenario. Treating either backend as truth would therefore turn
its accidental behavior, names, and units into an undocumented contract.

The versioned files under `contracts/` define canonical input/output semantics.
They do not declare either engine's numerical results canonical.

## Decision

The engine lifecycle states are:

| Backend | Current status | Meaning |
|---|---|---|
| object engine (`AbbeySimulation`) | `reference_candidate` | Best preserved behavioral reference, but not promoted to canonical truth. |
| array engine | `experimental` | Suitable for experiments and benchmarked validation; not an authoritative result source. |

Neither engine is canonical. At most one backend may later have status
`canonical`, and only through an explicit superseding ADR.

`multizone_dwelling_v1` is the first contract to which both backends will be
compared. Engine-native names and representations are internal. Canonical names,
units, IDs, validation, serialization, and comparison rules belong to the
contract/adaptor layer.

## Required promotion evidence

A backend may be promoted one state only when all evidence is versioned and
reviewable for every supported use case:

1. **Contract conformance** — canonical inputs validate; outputs contain every
   required field with canonical IDs, terms, units, shape, and ordering.
2. **Deterministic behavior** — identical config, seed, weather, clock, and
   platform class produce identical categorical outputs and numeric outputs
   within declared tolerances over repeated isolated runs.
3. **Conservation and invariant checks** — energy aggregation, mass/moisture balance,
   CO2 non-negativity, physical bounds, topology, and engine-path assertions
   pass at timestep and scenario levels.
4. **Scenario-level parity** — both backends consume the same canonical
   scenario and compare on mapped outputs; a backend cannot self-certify against
   its own fixture.
5. **Documented numerical tolerances** — every non-exact comparison identifies
   the field group, `rtol`, `atol`, precision, NaN policy, aggregation level,
   and physical justification. A single global “close enough” threshold is not
   acceptable.

Promotion from `experimental` to `reference_candidate` requires all five items
for `multizone_dwelling_v1`. Promotion from `reference_candidate` to
`canonical` additionally requires:

- successful use on all supported scenarios for a documented stabilization
  period;
- no unexplained parity deviation;
- production-quality error handling and observability;
- performance and memory appropriate to the supported scale;
- a migration and rollback plan;
- a superseding ADR approved by maintainers.

## Contributor change-routing policy

| Change | Canonical layer | Object backend | Array backend | Rule |
|---|---:|---:|---:|---|
| New or changed public field, term, unit, range, ID, or output meaning | required | adapter required | adapter required | Change the versioned contract first. Breaking changes require a new contract version. |
| Physics, occupancy, controls, or aggregation behavior inside a supported use case | contract test required | required | required | The feature is not supported until both implementations and parity evidence exist. |
| Bug fix for a shared contract violation | regression required | fix if failing | fix if failing | Run both backends; document if only one was defective. |
| Canonical validation, unit conversion, ID normalization, serialization, result comparison, or orchestration | required | no engine change unless adapter changes | no engine change unless adapter changes | This logic belongs only in the canonical layer and adapters, never duplicated in kernels. |
| Backend-only optimization with no observable contract change | no | allowed | allowed | One backend is sufficient, but conformance, determinism, and invariant tests must remain green. |
| Backend-specific diagnostics or profiling | optional namespaced extension | allowed | allowed | It must not alter canonical outputs or be required by the supported use case. |
| Feature outside every supported use case | capability registration required | optional | optional | It remains an experimental extension and may not be advertised as canonical support. |

### Policy for a feature implemented in only one engine

An engine-only implementation of a supported feature must be marked
`backend_extension`, exposed through a capability check, and excluded from
canonical conformance claims. Silent fallback to the other engine is forbidden.
If the unsupported feature affects physical results, the adapter must reject the
scenario before execution rather than ignore it.

## Retirement criteria

A backend may enter `deprecated` only when:

- another backend is explicitly `canonical` for every supported use case;
- canonical adapters and migration instructions exist;
- all unique supported features have been ported or explicitly retired;
- saved scenarios and outputs have a tested migration path;
- baseline and parity evidence are archived; and
- the deprecation is announced for at least one documented release cycle.

Removal requires zero canonical call paths, fixtures, or published workflows
depending on the backend, plus a separate removal decision. Performance alone
is not a retirement reason. A backend with stronger contract correctness cannot
be retired in favor of a faster but non-conformant backend.

## Consequences

Contributors must identify the change class before implementation. Supported
physical behavior usually requires both backends. Contract mechanics belong in
the canonical layer. Optimizations and diagnostics may be backend-specific when
they do not change canonical behavior. Engine status is evidence-based and may
not be inferred from directory names, age, or speed.
