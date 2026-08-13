# Occupant schedule and action validation protocol

Validation category: **calibration** (protocol only; no fitted result).

Model claim: `OCC-1`.

## Intended evidence roles

- ATUS activity diaries are candidates for weighted population priors for
  time at home, sleep/wake, meal timing, activity duration, weekday/weekend
  differences, and household composition. They are not deterministic
  household schedules.
- RECS is a candidate for weighted distributions of household characteristics,
  appliance presence, lighting/heating context, and energy use. It does not
  provide natural minute-level event timing.
- IEA EBC Annex 66 supplies fit-for-purpose model definitions and warns that
  model choice and evaluation must follow the application.
- IEA EBC Annex 79 supplies documentation/evaluation guidance and emphasizes
  diversity, domain-specific metrics, transparent data provenance, and
  real-building evaluation rather than proof-of-concept alone.

The current registry contains source metadata/guidance only for ATUS and
RECS; it contains no survey microdata and therefore supports no calibration
claim.

## Frozen calibration design before data use

The calibration study must declare its target population, geography,
household strata, diary/activity code mapping, location mapping, survey and
replicate weights, treatment of simultaneous activities, weekday/weekend and
seasonal strata, missing-data rules, random seed, parameter bounds, and a
household-level split that prevents one person's records leaking across fit
and holdout sets.

Reported schedule distributions include sleep/wake time, meals per day,
time-at-home fraction, appliance-event frequency, event start time, event
duration, and between-person/household variation. Means are always accompanied
by spread and relevant quantiles or distributions.

## Probabilistic action contract

For windows, HVAC, lights, and appliances, empirical evaluation requires:

- frequency, start-time, and duration distributions;
- off-to-on and on-to-off transition probabilities;
- conditional rates by frozen indoor/outdoor/context bins;
- Brier score or Bernoulli log loss from the probability recorded *before*
  each decision; and
- person-level and household-level variability.

`nexusep.validation_data.behavior` implements reproducible event extraction,
transition summaries, conditional rates, between-person rate distributions,
Brier score, and log loss. These are verification-tested tools, not empirical
results.

The current ABBEY action selector exposes ranking scores and a selected action,
not calibrated probabilities. Scores must not be normalized after the fact
and reported as probabilities. Phase 4.23 empirical probability claims remain
blocked until the runner logs a named pre-decision probability, model version,
person ID, context, eligible action set, and realized decision on every trial.

## Transferability rule

ATUS and RECS describe U.S. populations. Using them for an Italian or other
European scenario requires a declared transfer assumption or a local dataset;
otherwise only software behavior and sensitivity to those priors may be
reported.
