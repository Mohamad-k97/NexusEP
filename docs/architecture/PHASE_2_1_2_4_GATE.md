# Phase 2.1–2.4 architecture gate

- Recorded: 2026-08-06
- Contract version: `multizone_dwelling_v1` / `1.0.0`
- Scope: policy and canonical contract definition
- Engine certification: none

## Exit status

| Phase | Status | Evidence |
|---|---|---|
| 2.1 dual-engine policy | complete | ADR-0001 records `reference_candidate` for the object engine, `experimental` for the array engine, neither as canonical, evidence-based promotion/retirement criteria, and change routing for canonical, shared, and backend-only work. |
| 2.2 first supported use case | complete | The versioned use-case document and minimal scenario constrain the problem to one building, one dwelling, multiple zones, two occupants, fixed weather/clock/seed, and basic zone services; exclusions are explicit. |
| 2.3 canonical terminology | complete | The glossary and machine-readable terms registry define the hierarchy, distinguish ambiguous concepts, and restrict aliases to adapters and migrations. |
| 2.4 unit conventions | complete | The unit document and machine-readable registry cover every public numeric input and required output, select relative humidity as a fraction, and define ranges, conversion boundaries, aggregation, energy, precision, and comparison rules. |

## Executable evidence

Run from the repository root in the locked Phase 1 environment:

```powershell
.venv\Scripts\python.exe -m pytest tests\contracts\test_multizone_dwelling_v1_contract.py -q
```

Expected result at this gate: `13 passed`.

The gates assert:

- a one-to-one mapping between all 52 numeric scenario inputs and unit-registry
  entries;
- a unit and accepted range for every registered public numeric field;
- canonical suffixes and fraction-valued relative humidity;
- absence of forbidden legacy aliases in canonical schema properties;
- the required engine statuses, promotion evidence, retirement policy, and
  single-engine feature policy;
- the supported-use-case scope and exclusions; and
- coherent geometry, IDs, boundaries, openings, services, occupant schedules,
  weather length, and fixed simulation clock in the minimal scenario.

All JSON contract files are also parsed with Python's standard JSON parser.
Draft 2020-12 meta-schema validation is not part of this gate because the
locked development environment does not include a JSON Schema validator; this
does not affect the engine-independent semantic gates above.

## Boundary and next evidence

This phase freezes the canonical vocabulary and public shape. It does not
rename existing engine-native internals or claim that either engine currently
consumes the canonical JSON directly. Legacy names remain internal until named
inbound/outbound adapters are implemented.

Promotion still requires the evidence in ADR-0001: executable adapter
conformance, repeated deterministic runs, conservation/invariant checks,
scenario-level object/array parity, and field-group numerical tolerances. Until
that evidence exists, neither backend is the canonical truth.
