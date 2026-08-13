# Future acoustic validation gates

Validation category: **empirical validation** (protocol only; no result).

Model claim: `ACOUST-0`, which must be replaced or versioned before these data
can test a physical acoustic claim.

## Registered candidates

The PTB Room Acoustics Absorption Coefficient Database overview describes more
than 2,000 material records with octave-band absorption and, where available,
scattering coefficients. Only the official overview is checksum-pinned; the
linked Excel/ZIP database has not been acquired.

Motus version 1.0, DOI `10.5281/zenodo.4923187`, is CC BY 4.0 and describes
3,320 higher-order Ambisonic room impulse responses: 830 furniture
configurations with four source-receiver configurations in one room. Its seven
archives total 63,649,043,963 bytes. Only the Zenodo metadata JSON is
checksum-pinned; no archive was downloaded.

Neither source has a scientific-result manifest because both are mismatched to
the present broadband attenuation placeholder.

## Capability gates

PTB material data become relevant only after NexusEP has:

- frequency/octave-band acoustic state and outputs;
- explicit surface/material ownership and frequency-dependent absorption;
- a declared reflection/reverberation equation and room geometry contract;
- scattering semantics if scattering data are used; and
- analytical verification plus sensitivity to area and absorption changes.

Motus becomes relevant only after NexusEP has:

- an impulse-response or defensible energy-decay/reverberation model;
- source and receiver position/orientation contracts;
- frequency, sampling, Ambisonic-channel, geometry, and furniture mappings;
- declared comparison targets such as decay curves, EDT/T20/T30, or spatial
  response metrics; and
- a resource-approved acquisition plan, local SHA-256 inventory,
  preprocessing, calibration/holdout split, and uncertainty treatment.

Façade or interzone transmission-loss validation requires a different matched
dataset; Motus must not be repurposed for that claim.

## Promotion rule

When one of these gates closes, define a new acoustic claim ID rather than
silently expanding `ACOUST-0`. The source manifest must then reference the new
claim, and any numerical comparison must have a separate scientific-result
manifest and report.
