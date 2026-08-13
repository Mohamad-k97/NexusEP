# Solar position verification

Validation category: **verification**
Model claim: `SOLAR-1`
Evidence source: `nrel-spa-2008`

NexusEP's solar-position boundary calls pvlib 0.15.2's Python implementation
of the NREL Solar Position Algorithm (SPA). Public angles use degrees,
longitude is positive east, and azimuth is clockwise from true north. Input
timestamps must be timezone-aware. Geometric and refraction-adjusted angles
are kept separate.

## Reference result and tolerance

The official NREL tester case (2003-10-17 12:30:30 UTC-07:00,
39.742476 N, 105.1786 W) reports apparent zenith 50.111622 degrees and
azimuth 194.340241 degrees. The executable comparison tolerance is
`1e-6 degree`; the observed values round to both published results. Sunrise
and sunset agree with the tester's 06:12:43 and 17:20:19 local values to less
than 0.5 seconds.

This numerical test tolerance is not the algorithm uncertainty. NLR states an
approximately `+/-0.0003 degree` uncertainty claim for SPA over years -2000
through 6000.

## Covered semantics

The verification suite includes equinoxes, both solstices, leap day, northern
and southern latitudes, equivalent instants expressed at different UTC
offsets, a daylight-saving transition instant, sunrise/sunset, the north-
clockwise azimuth range, and below-horizon night behavior. Naive timestamps
are rejected.

## Licensing boundary and remaining uncertainty

NLR restricts its SPA source to internal, noncommercial use and prohibits
redistribution. The downloaded header and tester remain below the ignored
`data/raw/validation/` directory. NexusEP does not vendor the NLR C source.
Only the two published scalar reference results are encoded in the test.

The implementation is therefore verified against the official reference
case and exercises the required edge semantics; it is not an independent
metrological reimplementation of every NREL intermediate equation.
