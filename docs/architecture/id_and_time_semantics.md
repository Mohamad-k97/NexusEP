# Canonical ID and time semantics

## External IDs

Every entity ID supplied by a user is a stable, non-empty string. The version 1
schema additionally restricts IDs to 1–128 ASCII characters matching
`^[A-Za-z][A-Za-z0-9_.-]*$`.

Identity values are globally unique within one scenario, including the
scenario, building, dwelling, zone, surface, opening, system, and occupant IDs.
A reference repeats an identity value and is not a second identity. The
compiler rejects cross-type collisions as well as duplicates of one type.

Every nested entity carries explicit `scenario_id`, `building_id`,
`dwelling_id`, `zone_id`, and/or `surface_id` parent references as applicable.
Nesting is for readability and does not replace those references. No canonical
relationship or output may rely on list position.

## Array indices and decoding

The compiler creates one registry per entity type by sorting external IDs in
ascending ASCII/Unicode code-point order and assigning contiguous zero-based
integer indices. Input list order, dictionary order, process hash randomization,
and backend traversal order cannot affect this mapping.

Indices are internal transport values. They are never public identities.
Outbound adapters must decode every entity index to the exact original string;
unknown indices and unknown strings are errors. Generated graph IDs use a
reserved punctuation-bearing namespace that canonical user IDs cannot occupy.

## Canonical time axis

- `start_datetime` is an ISO 8601 timestamp with an explicit UTC offset.
- `timezone` is an IANA timezone name, and its offset at `start_datetime` must
  agree with the supplied offset.
- `dt_minutes` is one positive, finite elapsed duration, fixed for the entire
  simulation.
- The canonical public integer is zero-based `timestep_index`. Legacy
  `time_index`, `step`, and `tick` names are adapter-only aliases.
- A timestep timestamp is the start of its half-open interval.
- Interval `i` is `[timestamp(i), timestamp(i + 1))`.
- `end_datetime_exclusive` is derived as `start + n_timesteps * dt_minutes` and
  cannot be supplied as an independent scenario field.

Timestamps advance by elapsed time on the UTC timeline and are displayed in the
declared IANA timezone. Spring daylight-saving transitions therefore skip local
wall times; autumn transitions may repeat a wall time with different offsets.
The offset and `timestep_index` disambiguate repeated times. Leap days are
included naturally when crossed. No civil-time padding, removal, or timestep
length change is permitted.

## Weather alignment and final interval

Weather contains exactly one record for every `timestep_index`. Ordering in the
input list is not semantic; indices must be unique and cover
`[0, n_timesteps)`. Each weather `timestamp` must equal the canonical interval
start for its index after timezone normalization.

For version 1, a weather record is the boundary condition for its complete
half-open interval. The last record applies through
`end_datetime_exclusive`; no extra endpoint record, implicit extrapolation, or
unlabeled partial final interval exists.

