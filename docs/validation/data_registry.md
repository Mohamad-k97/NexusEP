# Validation-data registry policy

Validation category: **verification** (provenance governance)

Registry version 1.0.0 establishes the immutable chain from an external raw
file to a scientific report:

```text
publisher URL + retrieval date
  -> raw file SHA-256 + byte size
  -> checked preprocessing code + exact command
  -> licensed compact fixture
  -> checked analysis code + compact result artifact
  -> result manifest
  -> categorized scientific report + model-claim IDs
```

The tracked index is [`data/validation/registry.json`](../../data/validation/registry.json),
and operational instructions are in
[`data/validation/README.md`](../../data/validation/README.md).

Source records are rejected unless they explicitly describe title and version,
publisher and DOI status, license and terms URL, download URL, retrieval date,
raw-file SHA-256 and byte size, units, timezone, measurement uncertainty, known
gaps, checked preprocessing, permitted use, and targeted model-claim IDs.
Unknown fields and duplicate JSON keys are rejected.

Raw data belongs below ignored `data/raw/validation/<source_id>/`. Only source
and result manifests, checked scripts, and small licensed derived fixtures are
versioned. `--verify-raw` upgrades the normal provenance check to require local
raw files and verify their bytes.

Scientific reports must live below `docs/validation/results/`, be indexed by a
result manifest, and declare the same category, model claims, and source IDs as
that manifest. The checker rejects dangling sources, unregistered reports,
changed scripts/fixtures/results, and claims not targeted by the cited data.

The registry now contains checksum-backed NREL SPA contract material, PVGIS
5.3 and NASA POWER hourly responses, and the current NSRDB API contract. The
PVGIS and POWER sources have small licensed fixtures; NREL is metadata-only
because its source license prohibits redistribution, and NSRDB is metadata-only
because no authenticated data query has been performed. No comparative,
empirical, calibration, or blind-validation scientific result is registered.
