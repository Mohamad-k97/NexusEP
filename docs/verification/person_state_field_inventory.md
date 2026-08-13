# Person state field inventory

Validation category: **verification**

`PersonState` is the per-occupant state owner. Duplicate annotations are
rejected by `tests/unit/test_state_structure.py` before Python can silently
shadow an earlier declaration.

| Category | Fields / field families | Ownership rule |
|---|---|---|
| Identity and static profile | `occupant_id`, `household_id`, age/sex/role, employment and school profile, capabilities such as `can_cook` | Assigned to one occupant and not inferred from list position. `has_job` defaults to `False`. |
| Dynamic person state | location/availability, needs, comfort and perception values, current behavior, work/school/sleep flags | Mutated only for the addressed occupant, except for an explicitly declared household-wide effect. |
| Derived state | discomfort scores, schedule availability, action eligibility and other computed indicators | Recomputed from canonical inputs; not an independent source of truth. |
| Compatibility concepts | historical role-based space aliases and default-family IDs | Resolved only by legacy adapters/example factories. They are not canonical IDs and must not escape decoded output. |

The authoritative serialized form is `PersonState.to_dict()`. Its round-trip
test protects the selected defaults for `has_job`, `household_id`, and
`can_cook`.
