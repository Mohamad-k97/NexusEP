# Canonical timestep and output contracts

## Timestep boundary

`nexusep.schema.timestep.SimulationStepInput` is the only supported timestep
boundary for canonical runners. It is strict, immutable, and rejects unknown
keys. Every top-level field is required; empty tuples are allowed only where
absence is meaningful, such as action events and additional internal gains.

The canonical spelling is `timestep_index`. A read-only `time_index` property
exists for transition code, but canonical serialization never emits the
alias.

The boundary separates four kinds of data:

| Kind | Owner | Representation |
|---|---|---|
| Immutable scenario data | loader/compiler | `CanonicalScenario` held by the adapter |
| Mutable physical state | caller/run coordinator | `prior_zone_states` |
| External timestep inputs | caller/run coordinator | weather, named boundary temperatures, occupants, events, gains, opening/zone controls, availability |
| Derived intermediate values | backend | `DerivedStepValues`, never accepted by `SimulationStepInput` |

Each adapter calls `validate_step_input_for_scenario` before encoding. The
validator requires exact zone, occupant, and system coverage, confirms the
scenario/graph digest, and aligns the timestamp, timestep duration, timezone,
weather row, seed, and graph version. Missing and invented entity IDs are both
errors. Dict-like timestep aliases are not accepted.

Named non-weather thermal boundaries, such as a measured cellar air node, are
explicit `ExternalBoundaryState` rows. Coverage is exact: every boundary named
by the graph must be supplied once and no boundary may be invented. Exterior
weather surfaces continue to use the normalized weather state.

Action events describe externally known semantic events. Their physical
effects must be represented explicitly in `internal_gains`; an adapter must
not infer gains from an action name.

`ZoneControlCommand` carries delivered heating/cooling fractions, their
convective fractions, and an optional mechanical-ventilation supply
temperature. Convective fractions default to `1.0` for backward compatibility;
the complementary share is radiant and must enter the thermal mass path.
Supply temperature applies only to mechanical outdoor air. Infiltration and
window exchange remain coupled to outdoor dry-bulb temperature.

`OpeningControlCommand` overrides the zone default for one exterior opening's
opening fraction and shading state. `InterzoneOpeningControl` overrides the
static opening fraction of one reciprocal interzone surface pair. Both use
canonical IDs and are validated against the compiled graph; controlling both
faces of the same pair is an error. Omission means the explicit static scenario
or zone command applies, not an inferred backend default.

## Required output tables

`CanonicalZoneStepResult` is the required per-zone row. Its columns are
backend neutral:

- scenario, run, building, dwelling, and zone string IDs;
- interval-start timestamp and timestep index;
- air temperature, relative humidity fraction, CO2, and occupancy count;
- heating, cooling, ventilation, lighting, and total electrical power;
- engine name/version, execution status, and fallback status.

`CanonicalStepResult` also contains zone, dwelling, and building electrical
energy in Wh, warnings, validation provenance, applied defaults, and an
optional `CanonicalDebugResult`. `CanonicalRunResult` sums those rows by the
original IDs and carries `CanonicalRunMetadata`, warnings, and validation
provenance. Debug fields may be backend-specific; required zone and aggregate
rows may not be.

Energy uses interval power times `dt_minutes / 60`. Zone energy must sum to
both the dwelling and building totals within `1e-9 Wh`; construction fails if
coverage or aggregation differs.

Heating and cooling fields are delivered thermal power. Lighting and
ventilation fields are electrical power. `total_electrical_power_w` converts
heating/cooling through the declared efficiency/COP and adds electrical end
uses; fan power is currently the explicit zero default described by each
adapter.

## Relative humidity

The public contract uses a fraction in `[0, 1]`. The object adapter converts to
and from the legacy percent representation only at its boundary. The array
engine already stores a fraction.

## Status and fallback

`fallback_used` and `fallback_reason` are coupled: a reason is required exactly
when fallback is true. The supported object adapter invokes the unified physics
engine directly and does not enable legacy fallback. The array adapter has no
fallback branch. Explicit compatibility defaults produce warnings and
`completed_with_warnings`, not a fallback status.
