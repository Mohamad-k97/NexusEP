# Canonical scenario loader

`nexusep.scenarios.load_scenario(path)` is the only canonical file-loading
entry point for schema version 1.

## Pipeline

The loader:

1. reads UTF-8 `.json` or `.jsonc` while preserving comment line locations;
2. validates the declared schema version before dispatch;
3. resolves external-weather and output paths relative to the scenario file;
4. applies documented defaults and materializes optional nulls;
5. obtains inline, external, or explicitly synthetic smoke weather;
6. derives only permitted timestamps and normalizes datetimes/numeric values to
   canonical typed fields;
7. creates the frozen `ScenarioV1` object;
8. performs semantic uniqueness/reference/time/weather validation;
9. compiles and validates the deterministic physics graph; and
10. returns a frozen `CanonicalScenarioBundle` with scenario, canonical graph
    JSON, source path, graph hash, and transformation audit.

JSONC support includes line and block comments and trailing commas. It does not
add unquoted keys, single-quoted strings, environment substitution, includes,
or arbitrary code execution.

## Defaults and audit

Version 1 defaults are limited to metadata description/tags, explicit weather
source policy fields, optional weather nulls, and output configuration. A
missing output directory becomes
`artifacts/scenarios/<scenario_id>` relative to the scenario file. Every
applied default, timestamp derivation, synthetic series generation, and path
resolution produces a deterministic `TransformationRecord`.

There are no schema migrations in version 1. Unsupported versions fail instead
of being guessed or silently migrated. Unit-bearing canonical field names are
already in registry units; Pydantic normalizes their JSON numeric representation
without accepting alternate-unit aliases.

The bundle is controlled and repeatable: nested schema models are frozen,
collections are tuples, and `compiled_graph` returns a fresh dictionary decoded
from stored canonical JSON. Loading the same file twice yields equal scenario,
audit, graph serialization, and graph hash.

