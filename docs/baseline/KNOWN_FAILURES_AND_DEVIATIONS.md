# Known failures, deviations, and uncertainty

Validation category: **verification** (evidence classification and provenance)

There are no observed validation or pytest failures in the Phase 1.4 baseline.
The following limitations remain material.

## D1 — no authoritative statewise object/array comparison

The trusted object and surviving array benchmark scenarios differ in topology,
occupants, actions, and input representation. Both are deterministic and pass
their own invariants, but their state values are not semantically comparable.
Architecture work must not cite the Phase 1.7 invariant check as proof of
per-field equivalence.

Unblock by defining one versioned scenario contract that both runners consume,
including agreed initial states, weather, actions, optional kernels, logging,
and output-field mappings. Add explicit tolerances per comparable field and
record unsupported fields.

## D2 — protected generated files remain at repository root

Four pre-existing user files remain at the root because Phase 1.0 explicitly
prohibited modifying or moving them:

- `fast_shadow_results.csv`
- `polygon_shadow_results.csv`
- `shadow_cache_clustered_128_q16.npz`
- `shadow_cache_exact_q16.npz`

Their hashes are frozen and unchanged, and exact `.gitignore` rules prevent
accidental commits. New outputs no longer target the root. The repository-root
cleanup gate nevertheless remains unsatisfied until the user authorizes their
relocation or removal.

## D3 — unsupported local Python 3.14 installations

Local Python 3.14 executables and caches exist, but recovery supports only
CPython 3.12.x. No baseline result should be generalized to 3.14.

## D4 — performance variability

Object logs-on annual runs ranged from 168.629 to 228.501 seconds. Array loop
ranges were also several seconds. Reports preserve median, min, max, and range;
single-run speedup claims are unsupported. Re-run on an otherwise idle machine
before using the numbers for a performance target.

## D5 — recovered-test provenance

Git contains no earlier committed Phase 17.1–17.8 validation sources before
their first appearance in commit `7d27291`. Phase 17.3, 17.5, 17.6, and 17.7
were reconstructed from surviving contracts rather than restored verbatim.
Detailed provenance is in `PHASE_1_3_RECOVERY_PROVENANCE.md`.
