# Deferred external thermal validation gates

Validation category: **comparative validation, empirical validation,
calibration, and blind validation planning only; no result claimed**
Model claim(s): `THERMAL-1`
Evidence: source metadata only

The user has deferred validation steps requiring licensed material, dataset
handling decisions, or scientific calibration judgement until the final
human-involvement stage. Deferred work is recorded as pending rather than
skipped or passed.

## Phase 4.8 — ASHRAE Standard 140 thermal cases

Status: **deferred; not run**.

No Standard 140 thermal result, range comparison, or compliance claim exists
in this repository. At the final human-involvement stage, the operator must
provide authorized access to the applicable Standard 140 edition and confirm
how its supplemental inputs and reference ranges may be processed and stored.
Licensed inputs must remain outside Git unless their terms explicitly permit
redistribution.

The execution order will be lightweight/heavyweight fabric, free-floating
temperature, prescribed heating/cooling, window orientation, solar-gain
variation, and infiltration variation. Each unsupported input or equation is
to be classified as a model-scope difference before comparing results; cases
must not be tuned individually.

## Phase 4.9 — IEA Annex 58 Twin Houses

Status: **deferred; not downloaded, calibrated, or run**.

The intended data policy is frozen before access to the holdout values:

- Experiment 1, DOI `10.15129/8a86bbbb-7be8-4a87-be76-0372985ea228`, is the
  only parameter-identification and calibration dataset.
- Experiment 2, DOI `10.15129/94559779-e781-4318-8842-80a2b1201668`, is a
  sealed blind-validation dataset. Its measured outcome series must not guide
  model selection, parameter bounds, fitting, stopping, or preprocessing
  choices.
- The Experiment 1 record identifies the supplementary dataset as CC BY 4.0.
  License and attribution metadata must still be captured in the validation
  registry when the bytes are retrieved.
- Raw archives belong under ignored `data/raw/validation/`; their SHA-256,
  byte size, retrieval date, units, timezone, uncertainties, known gaps, and
  preprocessing lineage must be registered before analysis.

Before Experiment 2 is opened, the calibration code, parameter set, exclusion
rules, warm-up, alignment, metrics, and acceptance thresholds must be frozen
and hashed. Calibration and blind-validation reports will be separate results.

## Remaining exit criteria

Phase 4.8 remains open until every supported case has an authorized,
provenance-tracked comparison and every deviation is classified. Phase 4.9
remains open until Experiment 1 calibration is frozen and the unchanged model
is evaluated on Experiment 2 without retuning.
