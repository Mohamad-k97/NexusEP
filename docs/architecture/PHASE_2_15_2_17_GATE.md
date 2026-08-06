# Phase 2.15-2.17 gate

## Deliverables

| Deliverable | Evidence | Status |
|---|---|---|
| same conformance suite for both adapters | `tests/conformance/test_backend_contract_v1.py` | pass |
| schema, geometry, IDs, time, weather, graph, references, units, outputs, repeats | ten parameterized contracts | pass |
| deterministic first parity harness | `nexusep/parity/harness.py` | pass |
| initial state, inputs, occupants, outputs, energy, graph, invariants | machine report comparisons | measured |
| quantity-specific tolerances | `DEFAULT_TOLERANCES` and machine report | pass |
| cumulative drift separate from power | `cumulative_drift` comparison scope | pass |
| every difference classified | six exhaustive classification values | pass |
| contract v1 freeze | ADR-0003 and `contract_v1_index.md` | pass |
| compatibility/deprecation policy | `compatibility_and_deprecation.md` | pass |

## Gate result

Contract v1 is frozen and both adapters structurally conform. Numerical parity
is measured, not achieved. ADR-0001 promotion remains closed because contract
violations and missing conservation/array capabilities are explicitly present
in the initial parity report.

Reproduce the evidence with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/conformance tests/adapters tests/contracts tests/scenarios -q
.\.venv\Scripts\python.exe -m nexusep.parity.harness --output artifacts/baseline/phase_2_16_initial_parity.json
```
