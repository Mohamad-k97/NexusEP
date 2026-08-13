# Correctness verification

Validation category: **verification**

Every artifact in this directory is a **verification** record as defined in
[`../validation/terminology.md`](../validation/terminology.md). Passing these
checks supports claims about implementation and internal engineering
invariants. It is not evidence that simulated results agree with an
established benchmark or a measured building.

- `phase3_correctness_gate.md` maps the Phase 3 exit criteria to automated
  evidence and the remaining release checks.
- `phase3_test_and_script_inventory.md` classifies retained manual entry
  points and documents the authoritative pytest owner for each assertion.
- `person_state_field_inventory.md` assigns each `PersonState` field family a
  single ownership category and identifies compatibility-only concepts.
