# Published lighting benchmark scope

Validation category: **comparative validation** (protocol only; no result).

Model claim: `DAYLIGHT-1`.

## Evidence order

1. Phase 4.20 analytical verification must pass first.
2. CIE 171 analytical reference cases may be configured only after the actual
   publication/reference values are lawfully acquired and hashed.
3. A measured daylight comparison may follow only after the BRE-IDMP raw
   files, sensor metadata, uncertainty, timezone, and reusable-data license
   are confirmed.
4. Annual weather-driven daylight is last because it compounds weather,
   solar, geometry, material, control, and integration errors.

The official CIE page identifies CIE 171:2006 as a collection of analytical
and experimental lighting-program cases. The registered local evidence is
only that overview page; the 97-page benchmark and numerical values are not
present. The BRE-IDMP registry entry is likewise bibliographic metadata only.
Neither source therefore has a scientific-result manifest.

## Required reporting

Each future comparison must report these quantities independently rather
than collapsing them into a single score:

- illuminance bias and normalized bias;
- illuminance MAE and RMSE;
- daylight onset/offset or peak-timing error;
- lighting-control event frequency and duration errors; and
- lighting-power and lighting-energy error.

Geometry, surface reflectances, glazing optics, sky model, sensor position,
shading, timestep, warm-up, missing-value masks, and numerical tolerances must
be frozen before execution. Unsupported cases are classified as missing
features, not approximated silently.

## Gate status

`CIE 171`: **blocked on human acquisition/licensing of the full reference**.

`BRE-IDMP`: **blocked on raw-file access, reuse license, and measurement
uncertainty**.

Passing the repository's analytical tests does not satisfy either gate.
