# Acoustics validation dossier

Validation category: **verification only; physical acoustic validation is not claimed**.

## Model version and commit

Model claim `ACOUST-0`; source baseline `63936cc50fe83850d5c9bd1d1b49026f47d91c9f` plus dirty Phase 4 changes.

## Dataset and license

Hand-calculated fixtures only. PTB absorption and Motus impulse-response metadata are registered for a future, scientifically matching model.

## Scenario mapping

dB addition, attenuation direction, open/closed-window ordering, interzone symmetry, and bounded comfort response.

## Preprocessing

No external acoustic data are processed.

## Calibrated parameters

None.

## Untouched validation period

Not applicable to placeholder arithmetic.

## Metrics and plots

Exact arithmetic/directional assertions and bounds; no physical residual or plot exists.

## Residual analysis

Not scientifically applicable until frequency, reverberation, or impulse-response physics is implemented.

## Limitations

No spectrum, weighting, distance, absorption, reflection, diffraction, reverberation, room acoustics, or transmission loss.

## Pass/fail decision

**Pass only for placeholder arithmetic. Physical acoustic validation remains explicitly blocked.**

## Reproducible command

`uv run pytest -q tests/unit/test_acoustics_placeholder_verification.py`
