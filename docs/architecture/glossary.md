# Canonical terminology and hierarchy

## Domain hierarchy

```text
Scenario
└── Building
    └── Dwelling
        └── Zone
            ├── Surface
            │   └── Opening
            └── System

Occupant
Weather series
Simulation period
```

An occupant belongs to a dwelling and references zones; it is not a child of a
zone because location changes over time. The weather series and simulation
period belong to the scenario.

## Canonical terms

| Canonical term | Definition | Legacy/ambiguous aliases | Adapter rule |
|---|---|---|---|
| scenario | Complete immutable simulation input plus contract version. | config, case | Adapters may read aliases; canonical serialization writes `scenario`. |
| building | Physical building container. | property | `building` only. |
| dwelling | One residential unit inside the building. | household, apartment | A household describes occupants, not geometry; map geometry to `dwelling`. |
| zone | Thermally well-mixed volume with physical state. | space, room | Engine `space_id`/`room_id` maps to `zone_id`; canonical fields never use `space`. |
| surface | Opaque exterior or interzone boundary owned by a zone. | wall, boundary | Type belongs in `boundary_type`; entity remains `surface`. |
| opening | Aperture in a surface; version 1 supports exterior windows. | window entity | Use `opening_type: window`; IDs use `opening_id`. |
| system | Equipment that can receive commands and produce physical delivery/state. | device | System type is explicit. |
| occupant | Human actor assigned to a dwelling. | person, agent | `person*` is accepted only by inbound/outbound engine adapters. |
| action | Intent or defined operation that may cause state changes. | event | An action is not proof that execution occurred. |
| event | Immutable occurrence emitted when an action starts, changes, or finishes. | action record | Events include timestep/time and action identity; do not use event as an instruction. |
| control command | Requested target or mode sent to a system for one timestep. | system state | Commands are inputs/decisions and may be constrained or rejected. |
| system state | Actual system mode, flow, power, or actuator position after constraints. | control command | Never infer that a command was delivered without state/output evidence. |
| physical state | Conserved or physically evolved zone/building quantities. | observation | Examples: temperature, humidity ratio, CO2 concentration. |
| observation | A selected, possibly transformed view presented to behavior/control logic. | physical state | Observations may lag, normalize, omit, or combine physical state; label them separately. |
| timestep index | Zero-based integer position in the simulation period. | time index, step, tick | Canonical key is `timestep_index`; `time_index` is adapter-only. |
| simulation clock | Timestamp derived from start time plus fixed timestep duration. | timestep index, hour/day | Canonical timestamp and index must agree; neither substitutes for the other. |
| weather series | Ordered boundary-condition records, one per timestep. | weather state | `weather_state` is one record; `weather_series` is the complete sequence. |
| simulation period | Start timestamp, timezone, fixed duration, and number of timesteps. | calendar | Calendar metadata may be derived but does not replace the period. |

## Alias policy

Canonical schema and result fields use only canonical terms. Aliases are listed
in `contracts/canonical_terms.json` and may occur only inside named adapters,
migration tools, or compatibility shims. Core kernels may retain internal names
until migrated, but those names are not public contract fields. New aliases are
not accepted without a contract decision and an unambiguous conversion rule.

Entity IDs are canonical external strings. Array indices are deterministic
compiled transport values and are never synonyms for IDs.
