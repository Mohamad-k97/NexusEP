# Validation-data registry

Validation category: **verification** (data provenance)

`registry.json` is the tracked index for every external source and every
comparative, empirical, calibration, or blind-validation result. It currently
indexes four Phase 4 weather/solar sources. PVGIS and NASA POWER have licensed
compact fixtures; NREL SPA and NSRDB are metadata-only for the reasons recorded
in their manifests. NexusEP has not yet published a comparative, empirical,
calibration, or blind-validation result backed by these sources.

## Layout

```text
data/validation/
  registry.json          tracked index
  sources/               one tracked download/source manifest per dataset
  results/               one tracked provenance manifest per scientific result
  fixtures/              small licensed, checksum-backed derived fixtures
scripts/validation_data/ tracked preprocessing and analysis code
data/raw/validation/     ignored raw downloads
docs/validation/results/ tracked scientific reports
```

Raw datasets, extracted archives, caches, and working files must not be
committed. A raw file is identified immutably by its SHA-256 and byte size even
when it is absent locally.

## Source manifest workflow

1. Review the license and permitted use before download.
2. Save raw files below `data/raw/validation/<source_id>/`.
3. Compute SHA-256 and byte size without changing the downloaded bytes.
4. Add preprocessing code below `scripts/validation_data/<source_id>/`.
5. If licensing permits, write only compact derived fixtures below
   `data/validation/fixtures/<source_id>/`.
6. Create `data/validation/sources/<source_id>.json` with every field required
   by `DataSourceRecord`.
7. Add the manifest path to `registry.json` and run the checks below.

Required source metadata includes title/version, publisher/DOI status,
license, download URL, retrieval date, every raw-file checksum, units,
timezone, measurement uncertainty, known gaps, preprocessing code and command,
permitted use, and model-claim IDs from `model_claim_matrix.md`.

```powershell
# Verify tracked manifests, scripts, fixtures, reports, and cross-references.
.venv\Scripts\python.exe -m nexusep.validation_data.registry check data/validation/registry.json

# Additionally require every raw file locally and verify its size/checksum.
.venv\Scripts\python.exe -m nexusep.validation_data.registry check data/validation/registry.json --verify-raw

# Inspect the authoritative source-manifest JSON Schema.
.venv\Scripts\python.exe -m nexusep.validation_data.registry schema
```

## Scientific-result workflow

Scientific reports belong below `docs/validation/results/`. Every such report
must have a result manifest indexed by `scientific_result_manifests`. The
manifest must reference registered source IDs, checked analysis code, checked
compact result artifacts, quantity-specific tolerances, and known deviations.
The report header must reproduce the source IDs in manifest order:

```text
Validation category: empirical validation
Model claim(s): THERMAL-1
Data source IDs: example-source-v1
```

The registry rejects unregistered reports and dangling source references.
