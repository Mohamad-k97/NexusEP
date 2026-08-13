# Acoustic placeholder verification

Validation category: **verification**.

Model claim: `ACOUST-0`.

## Frozen claim

NexusEP currently implements broadband placeholder arithmetic, not an
acoustic simulation model. Phase 4.25 verifies only:

- logarithmic source combination using relative energy
  `10 * log10(sum(10 ** (L_i / 10)))`;
- conversion between positive placeholder dB levels and relative energy;
- attenuation direction using `max(floor_db, source_db - attenuation_db)`;
- closed/partially open/open window ordering by interpolating both the
  placeholder sound reduction and transmission factor toward zero attenuation;
- equal bidirectional transmission across one symmetric interzone link; and
- a monotonic normalized discomfort signal bounded to `[0, 1]` between the
  declared comfort and stress thresholds.

The unit suite also checks that object and array helper arithmetic agrees for
source addition, attenuation, and normalized discomfort. Executable coverage
is in `tests/unit/test_acoustics_placeholder_verification.py`.

## Placeholder conventions and uncertainty

`0 dB` is treated as absence of an active source rather than the physical
reference-pressure level. Levels are broadband and have no declared A/C/Z
weighting, spectrum, octave band, time weighting, source directivity, distance,
room mode, reflection, diffraction, absorption path, reverberation, or impulse
response. The open-window interpolation is an ordering rule, not a measured
façade transmission-loss equation. The interzone rule is one-hop subtraction
and is not a coupled sound-field solution.

The normalized discomfort output is only a bounded simulation input. It is
not a validated comfort, annoyance, health, or exposure metric.

## Prohibited claims

Passing Phase 4.25 must never be described as room-acoustic validation,
façade/partition transmission-loss validation, material validation,
reverberation validation, or agreement with measured sound fields.
