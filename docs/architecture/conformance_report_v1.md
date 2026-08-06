# Contract v1 conformance report

## Result

Both canonical adapters pass the same Phase 2.15 structural and semantic test
suite. The suite contains ten parameterized contracts, producing 20 backend
cases: ten object cases and ten array cases.

| Contract area | Object | Array |
|---|---:|---:|
| schema validation before initialization | pass | pass |
| required and optional geometry | pass | pass |
| original ID round trips | pass | pass |
| timestamp alignment | pass | pass |
| weather mapping | pass | pass |
| deterministic graph construction/digest | pass | pass |
| missing and dangling references | pass | pass |
| explicit unit conversions | pass | pass |
| required output schema/energy hierarchy | pass | pass |
| deterministic fresh repeat | pass | pass |

This is conformance evidence, not numerical parity evidence. Each backend is
tested against the frozen contract; a passing result never depends on matching
the other backend's physical values.

## Reproduction

```powershell
.\.venv\Scripts\python.exe -m pytest tests/conformance/test_backend_contract_v1.py -q
```

The combined adapter regression command is:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/conformance tests/adapters -q
```

The machine-readable result is
`artifacts/baseline/phase_2_15_conformance.json`.

## Interpretation of explicit gaps

The array adapter passes pressure-field validation and preserves the canonical
weather row, but its current kernel does not consume atmospheric pressure; it
emits a warning. Both adapters publish zero ventilation fan power because v1
has no fan-power input. These explicit capability statements satisfy the
structural contract but remain promotion blockers where physical completeness
is required by ADR-0001.
