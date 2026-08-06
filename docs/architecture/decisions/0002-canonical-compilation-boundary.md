# ADR-0002: Canonical compilation boundary

- Status: accepted
- Date: 2026-08-06
- Scope: `multizone_dwelling_v1`

## Context

The object backend currently owns a rich graph and the array backend owns
integer registries. Neither representation is canonical under ADR-0001. Letting
users author either backend representation would make IDs, ordering, topology,
and defaults backend-dependent.

## Decision

Users do not author the low-level physics graph. They author the canonical
scenario: buildings, dwellings, zones, surfaces, openings, systems, occupants,
weather, and their explicit references.

A backend-independent loader/compiler must complete successfully before either
physics backend starts. It performs semantic validation and deterministically
constructs:

1. the canonical time axis;
2. string-ID-to-array-index registries; and
3. an inspectable, serializable physics graph.

The compiler output, not input list position and not a backend-native graph, is
the adapter boundary. Backends may lower that output into objects or arrays but
must restore original external IDs and canonical timestamps when decoding.

## Consequences

- Canonical inputs remain readable and backend-neutral.
- Reordering entity lists cannot change indices, graph ordering, or graph hash.
- Explicit external and interzone topology replaces inference from geometry.
- Required physical values cannot be supplied by hidden backend defaults.
- Rich optional geometry is not needed to compile the version 1 graph and
  cannot alter version 1 physics merely by being present.
- Existing backend graph builders and list-order registries remain adapters and
  are not conformance evidence until they consume this boundary.

## Validation and serialization

The compiled graph must reject missing references, orphan links, duplicate IDs,
invalid directionality, inconsistent surface/opening ownership, unmatched
interzone pairs, and nondeterministic ordering. Its canonical JSON form sorts
keys and uses deterministic node/connection order; a SHA-256 digest covers that
form for debugging and parity evidence.

The graph is a required precondition for backend execution. A backend must not
silently rebuild a different topology or invent its own external node.

