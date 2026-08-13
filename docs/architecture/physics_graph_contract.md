# Deterministic physics-graph contract

## Authored scenario versus compiled graph

Users describe physical entities and topology. They do not author nodes, edges,
array indices, the exterior node, connection order, or backend-native graph
objects. The canonical compiler described by ADR-0002 constructs those values
before a backend is selected.

The compiled graph contains:

- one explicit reserved exterior node and one node per thermal zone;
- one surface connection per exterior surface;
- one surface connection per reciprocal interzone surface pair;
- one opening connection per opening;
- explicit named exterior-boundary IDs plus copied thermal-bridge, shading,
  and airflow-opening properties on their owning connections;
- systems attached to their owner zones;
- the deterministic external-ID registry and canonical time axis; and
- provenance for copied, inherited, and derived graph properties.

## Ordering and directionality

Nodes are ordered by `(node_type_rank, node_id)`, with the exterior node first.
Connections are ordered by generated `connection_id`. Systems use their
canonical registry indices. Indices are contiguous and serialization uses
sorted JSON keys. Nodes, connections, and systems are therefore
deterministically ordered before either backend receives them.

Thermal surface and opening connections are physically bidirectional. Exterior
connections explicitly target `__exterior__`. Interzone connections use one
canonical source/target ordering based on zone ID, while retaining both owner
zone IDs and surface IDs. Direction in serialization is ordering, not a claim
that heat or mass can flow only one way.

## Required graph validation

Compilation fails unless:

- every referenced scenario, building, dwelling, zone, surface, and opening
  exists and has consistent ownership;
- the reserved exterior node is explicit and cannot collide with user IDs;
- no connection is orphaned or self-connected;
- all connection IDs and node IDs are unique;
- every interzone surface names one reciprocal paired surface and both sides
  agree on zones, area, thermal properties, and opposing orientation;
- exterior surfaces and openings target the reserved exterior graph node while
  retaining their explicit physical boundary ID (`outdoor_air` or a named
  prescribed boundary such as `cellar_air`);
- total opening area does not exceed owner-surface area;
- connection directionality is valid for its type; and
- node, connection, system, and registry ordering is deterministic.

`nexusep.schema.compile_physics_graph` is the reference compiler for the
contract. Its output is inspectable as a dictionary, serializable as canonical
JSON, and covered by a SHA-256 graph digest. Both engines must consume an
equivalent compiled graph before either can claim conformance.
