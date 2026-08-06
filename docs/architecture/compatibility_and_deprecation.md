# Contract compatibility and deprecation policy

## Canonical compatibility

The supported canonical input is a declared schema version loaded by
`nexusep.scenarios.load_scenario`. The canonical layer does not accept aliases,
arbitrary dict-like objects, implicit units, list-position IDs, naive
timestamps, or engine-native field names.

A compatibility importer may translate a legacy format only when it:

1. is separate from the canonical loader;
2. declares its source format and supported versions;
3. records every alias, default, migration, path resolution, and derived value;
4. produces a strict canonical scenario that passes normal validation; and
5. has regression tests proving deterministic conversion.

Compatibility code never changes the meaning of a frozen v1 field and never
enables silent engine fallback.

## Deprecating a contract field or version

A successor must be published before v1 is deprecated. The release must
include a versioned migration, before/after examples, validation diagnostics,
adapter coverage, and parity evidence. Deprecation warnings identify the exact
replacement and removal release. V1 remains readable and its required outputs
remain decodable for at least one documented release cycle.

Removal requires a major contract version, no supported workflow depending on
the old boundary, archived baseline/parity artifacts, and a maintainer-approved
decision. Stored canonical results keep their original schema and engine
versions; they are never relabeled in place.

## Backend compatibility

Backend capability gaps are rejected before execution when they would silently
change required physics. Explicitly modeled zero values and documented warnings
are allowed only where the canonical contract itself lacks the required input.
Backend-specific debug fields may be added or removed, but required canonical
tables remain stable.

Engine promotion, deprecation, and retirement follow ADR-0001. A faster engine
does not replace a conformant one without the required deterministic,
conservation, parity, migration, and rollback evidence.
