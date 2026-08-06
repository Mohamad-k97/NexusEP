# Canonical backend adapters

The supported backend entry points are:

- `ObjectEngineAdapter(CanonicalScenario, compiled_graph)`
- `ArrayEngineAdapter(CanonicalScenario, compiled_graph)`

Both accept only `SimulationStepInput` in `run_step` and return
`CanonicalStepResult`.

## Object engine

The object adapter compiles canonical building, dwelling, zone, surface,
opening, topology, system, weather, state, occupant-source, control, and
availability data into existing ABBEY object models. It calls
`run_building_physics_step` with `require_physics_graph=True` and legacy
fallback unavailable. Canonical IDs are used directly; no `dwelling_1` or
list-position identity enters the supported path.

Legacy zone records are retained only in optional debug output. Required rows
are translated from the native result and carry the original IDs. Object-only
compatibility values are emitted as `AppliedDefault` records.

Canonical v1 does not yet contain infiltration, ventilation fan power, or
detailed acoustic parameters. The adapter sets infiltration and fan electrical
power to zero so omitted data cannot silently add physics. Surface heat
capacity and U-values remain the canonical inputs. CO2 mass generation is
converted to the legacy volume rate using `1.842 kg/m3` at the adapter boundary.

## Array engine

The array adapter constructs one exact readable payload internally and then
calls the existing encoder. Users cannot supply the encoder dictionary. All
fields consumed by the encoder are materialized; its aliases and fallback
entity creation are outside the supported path.

Building, dwelling, zone, and occupant arrays are checked against the canonical
deterministic registry. The current numeric kernel represents one combined
system row per zone, so the adapter creates deterministic private carrier rows
and maps canonical per-service availability and controls into them. Carrier
IDs and numeric indices never enter required output rows.

Before every kernel call, the adapter writes prior state, occupant location,
system availability, and control values by private array-column constants. It
decodes zone/system rows immediately after execution. Array mutation and
column constants remain internal to `ArrayEngineAdapter`.

Current experimental limitations are explicit errors or warnings:

- externally supplied action events and non-occupant internal gains are
  rejected because the current timestep kernel has no injection boundary;
- canonical pressure is validated but not consumed by the array kernel;
- compiled surface topology is reduced to deterministic envelope/interzone UA
  values because no surface-graph array kernel exists;
- window pressure-flow and ventilation fan electrical power are explicitly
  zero because canonical v1 lacks the required coefficients.

These are experimental-backend gaps under ADR-0001, not permission to infer
backend defaults.
