# Supported use case: `multizone_dwelling_v1`

## Purpose

`multizone_dwelling_v1` is the smallest scenario that exercises the coupled
occupancy/building path without becoming a district or city-scale benchmark.
It is a conformance target, not a promise that either current engine already
implements the canonical adapter.

## Required scope

One scenario contains exactly:

- one building;
- one dwelling in that building;
- multiple thermal zones (at least two);
- at least two occupants assigned to the dwelling;
- at least one exterior surface and a paired interzone boundary;
- at least one exterior window;
- basic heating, cooling, mechanical ventilation, and lighting systems;
- occupant home/sleep zones and deterministic location schedules;
- one weather record per timestep;
- one fixed timestep duration, expressed as constant `dt_minutes` for the
  complete period; and
- one explicit deterministic seed.

Every identity value is stable and globally unique within the scenario. Every referenced zone,
surface, opening, system, dwelling, and building must exist. Interzone
boundaries must identify the adjacent zone and be paired in the opposite
direction. Exterior boundaries must not identify an adjacent zone.

## Required coupled behavior

The scenario must produce enough observable output to verify:

| Concern | Minimum evidence |
|---|---|
| occupancy | both occupants have a location for every timestep and at least one scheduled location transition occurs |
| controls | heating/cooling setpoints and at least one ventilation, window, or lighting command are represented distinctly from resulting system state |
| airflow | exterior and interzone volume-flow outputs are finite and topology-consistent |
| thermal | zone air and mean-radiant temperatures are finite and react to weather, gains, and system delivery |
| moisture | humidity ratio and relative-humidity fraction remain in accepted ranges and respond to occupant moisture gains/airflow |
| CO₂ (`co2`) | concentration is finite, positive, and responds to occupancy and ventilation |
| energy | delivered and input power are distinguished; interval Wh values aggregate zone → dwelling → building |

The versioned minimal example is
`contracts/examples/multizone_dwelling_v1_minimal.json`. It is intentionally
short and is a contract fixture, not a performance benchmark or golden output.

## Explicit exclusions

The following are outside version 1 and must be rejected or exposed as
non-canonical backend extensions:

- multiple dwellings in one building;
- multiple buildings or district simulation;
- adaptive timesteps or event-driven timesteps;
- shared-space arbitration or shared-space ownership;
- detailed shading, including geometric ray tracing or dynamic facade shading;
- unsupported HVAC networks beyond basic zone heating/cooling, ventilation,
  and lighting represented by the contract;
- plant loops, distribution networks, storage dispatch, or district energy;
- calibration, parameter estimation, uncertainty, ensemble, and probabilistic
  workflows; and
- city-scale GIS generation or urban morphology preprocessing.

Detailed acoustics is not required for conformance. It may be a namespaced
backend extension provided it cannot change required canonical outputs when
disabled.

## Conformance boundary

The JSON Schema validates structure, local ranges, fixed-timestep metadata, and
canonical names. Semantic conformance additionally validates reference
integrity, ID uniqueness, weather length, boundary pairing, required system
types, and schedule coverage. Numerical conformance is evaluated after both
engine adapters emit canonical results under ADR-0001 tolerances.
