# Elementary daylight and lighting verification

Validation category: **verification**.

Model claim: `DAYLIGHT-1`.

## Implemented scope

The Phase 4.20 suite verifies the equations NexusEP currently implements; it
does not claim full room-lighting accuracy. The zone daylight model is

`indoor_lux = outdoor_lux * effective_daylight_area_m2 / floor_area_m2`

where effective area is window area times frame, visible-transmittance,
shading, covering, directional-exposure, and utilization factors on the path
where each factor is available. Artificial-lighting power is linear in
delivered illuminance and energy is `power_w * dt_minutes / 60`.

The verification cases cover:

- no window and zero visible transmittance;
- one unshaded window with an exact hand-calculated result;
- monotonic transmittance and shading response;
- cardinal-orientation symmetry under the overcast fallback;
- east/west directionality for an eastern sun position;
- complete direct-light rejection when the explicit shading factor is zero;
- monotonic artificial-light output, power, and energy; and
- an occupied auto-light controller that turns on below 0.35 and off above
  0.45. Values on or inside that band preserve the preceding command.

The executable checks are in
`tests/unit/test_daylight_elementary_verification.py` and declare themselves
as verification tests.

## Scope limits

The current model has no sky vault, interreflection, detailed glazing optics,
radiosity, glare calculation, sensor-point geometry, or ray-traced shading.
Its orientation term is a front-facing cosine factor. The legacy controller's
`ZoneState.indoor_daylight` is a normalized scalar, while the physics output
is lux; a documented adapter between these quantities is still required
before the auto-lighting thresholds can be interpreted as physical lux.

Consequently the Phase 4.20 result supports only monotonic and algebraic
correctness for the simplified model. It cannot support a CIE, BRE-IDMP,
Radiance, or real-building accuracy claim.
