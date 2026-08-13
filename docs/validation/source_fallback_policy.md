# Validation-source fallback policy

Validation category: **verification and validation governance**.

An inaccessible, licensed, incompatible, or scientifically mismatched source
does not become a failed model result. It is recorded as an evidence-access or
model-scope gate. Alternatives are accepted only when they test the same
declared claim and their provenance, assumptions, and tolerances are explicit.

## Evidence ladder

1. Closed-form or conservation verification for the implemented equations.
2. Official public reference implementations or vectors, such as NREL SPA or
   NIST analytical tools/documentation.
3. Open, independently executable software comparisons using original cases,
   such as the registered EnergyPlus IdealLoadsAirSystem comparison.
4. Public controlled measurements with registered checksums, license,
   uncertainty, and untouched holdout periods, such as Twin Houses or NZERTF.
5. Licensed standards only after an authorized human operator supplies them
   and confirms permitted processing and reporting.

The lower item number is not automatically stronger evidence: analytical
verification and measurement validation answer different questions. An
alternative may close only the claim it actually tests.

## Current ASHRAE replacements and limits

- The ideal HVAC prerequisite uses the executed, BSD-licensed EnergyPlus 25.1
  comparison. It closes a narrow delivered-load and Wh-accounting comparison;
  it is not an ASHRAE Standard 140 pass.
- Thermal equations use closed-form RC verification now. A public original
  cross-solver EnergyPlus or Modelica fabric case may supply comparative
  evidence later, but no such result is fabricated in this phase.
- NREL HVAC BESTEST reports are public candidates for future equipment-map,
  dynamic, and airside models. NexusEP currently lacks those physics, so their
  cases remain classified as missing feature rather than approximated.
- The open Annex 71 Twin Houses main experiment has been acquired. The
  historical single-node run is retained as a rejected mapping diagnostic:
  it bypasses production adapters, crosses experimental regimes, and fails
  the frozen numerical limits. It is not promoted as blind evidence.
- BLS ATUS aggregate sleep statistics have been compared with repaired
  production object-runner output. The old 300-minute episode cliff is gone,
  but the output fails the narrow duration screen and aggregates cannot test
  individual distributions, so respondent microdata evidence remains blocked.
- NZERTF remains the preferred integrated empirical route. Annex 71, BOPTEST,
  and the narrow EnergyPlus result do not jointly replace its mapped measured
  temperature, humidity, ventilation, HVAC, load, and energy evidence.
