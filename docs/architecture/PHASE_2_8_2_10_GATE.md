# Phase 2.8–2.10 scenario-loading gate

- Recorded: 2026-08-06
- Canonical scenario schema: `1.0.0`
- Loader entry point: `nexusep.scenarios.load_scenario`
- Backend certification: none

## Exit status

| Phase | Status | Evidence |
|---|---|---|
| 2.8 weather contract | complete | Required and optional timestep fields, units, null/NaN policy, no-interpolation rule, fixed-clock alignment, final interval, permitted timestamp derivation, external sources, and smoke-only synthetic weather are documented and enforced by `WeatherSource`, `WeatherState`, semantic validation, and loader tests. |
| 2.9 scenario schema v1 | complete | The empty schema package now contains frozen strict models for common fields, scenario hierarchy, geometry/topology, weather, systems/controls, outputs, and version dispatch. Extra aliases and malformed fields produce stable JSON-path errors before compilation. |
| 2.10 canonical loader | complete | The loader reads JSON/JSONC, dispatches schema version, resolves paths, materializes and audits defaults, derives permitted timestamps, loads external or named smoke weather, validates references/uniqueness, compiles the graph, and returns a controlled immutable bundle. Repeated loads are equal. |

## Reference load

Loading `contracts/examples/multizone_dwelling_v1_minimal.json` produces:

- frozen `ScenarioV1` models and tuple collections;
- four aligned normalized weather states;
- an absolute output path resolved relative to the scenario file;
- five deterministic audit entries: four optional-noise null defaults and one
  output-path resolution;
- the same 3-node / 5-connection / 8-system compiled graph; and
- graph SHA-256
  `a3021d4de71b7d32fa3a518520c2db11ee12a927d081c98b0d76d01adfb0f00a`.

Loading the file twice yields equal scenario objects, audit logs, canonical
graph JSON, and graph hashes. Callers receive a fresh decoded graph dictionary,
so mutation cannot alter the bundle's stored graph.

## Executable evidence

```powershell
.venv\Scripts\python.exe -m pytest tests\contracts tests\scenarios -q
.venv\Scripts\python.exe -m ruff check nexusep\schema nexusep\scenarios tests\contracts tests\scenarios
.venv\Scripts\python.exe -m mypy nexusep\schema nexusep\scenarios
```

Expected focused result at this gate: `42 passed`.

Tests cover JSONC comments/trailing commas, external relative weather paths,
derived timestamps, required-null/nonfinite weather failures, missing weather
records, interpolation rejection, named smoke synthesis, rejection of
synthetic weather in validated runs, absence of automatic fallback, output
defaults, unsupported schema versions, extra aliases, legacy unit aliases,
duplicate IDs, parent mismatches, topology errors, immutability, and repeatable
graph compilation.

## Backend boundary

The normalized `ScenarioV1.weather_series` tuple is the only canonical weather
input. Both backend adapters must consume values from this same tuple; they may
not reread source weather, interpolate, derive components, or synthesize a
fallback independently.

The canonical loader and compiler boundary is complete, but the existing object
and array runner entry points are not yet rewired to require a
`CanonicalScenarioBundle`. Runtime backend conformance remains unclaimed until
that adapter work and ADR-0001 parity evidence are complete.
