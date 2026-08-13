# Official weather-ingestion verification

Validation category: **verification**
Model claim: `WEATHER-1` (with forcing inputs used by `SOLAR-1`)
Evidence sources: `pvgis-5.3-hourly`, `nasa-power-hourly-v2.9.8`, and
`nsrdb-api-contract-2026`

## Executed official fixtures

The PVGIS fixture is a checksum-backed PVGIS 5.3 `seriescalc` response for
45 N, 8 E and calendar year 2020. The adapter verifies the response's own unit
metadata, reads UTC timestamps, maps temperature and wind speed, derives GHI
from the three horizontal-plane components, and derives DNI from horizontal
beam irradiance only when sun height makes that conversion stable. Relative
humidity, pressure, and wind direction remain explicitly missing.

PVGIS-SARAH irradiance is classified as an `instantaneous_sample`: the
satellite observation for this location is stamped at minute 10. It is not
silently treated as an hourly energy average. The companion ERA5 variables
are hourly values, so the response deliberately carries a mixed-semantics
warning.

The NASA POWER fixture is a checksum-backed Hourly API v2.9.8 response for the
same location, 2020-01-01 through 2020-01-02. The request explicitly sets
`time-standard=UTC`. The adapter verifies all source unit labels, converts
percent RH to a fraction and kPa to Pa, preserves the `-999` missing-value mask,
and rejects Local Solar Time on the UTC ingestion path because LST is not a
civil timezone.

Radiation-component consistency is evaluated using solar position at the
midpoint of each hourly mean. For the fixed POWER fixture, the maximum absolute
`GHI - (DHI + DNI*cos(zenith))` residual is below `20 W/m2`. This is a
source-specific forcing-plausibility bound, not an equation-verification
tolerance or a claim that independently averaged components must close exactly.

## NSRDB status

The current NSRDB API contract and its GHI/DNI/DHI fields are recorded. An
end-to-end NSRDB data query is not claimed: the download endpoint requires an
API key plus identifying request metadata. The checked-in test verifies the
PSM CSV schema and fixed-offset conversion using an authored schema sample,
not external scientific values. A future authenticated retrieval must add its
own raw checksum, version, query, license, uncertainty, and derived fixture.

## EPW boundary convention

The legacy EPW reader now attaches the fixed UTC offset from the EPW LOCATION
header. EPW hour 1 becomes interval start 00:00 and hour 24 becomes 23:00;
the original EPW convention denotes the end of the reported hour. EPW uses
standard local time and does not apply daylight-saving transitions.

## Claim limit

These tests verify fields, units, masks, UTC handling, and source time
semantics. PVGIS, POWER, and NSRDB are satellite/reanalysis forcing products;
agreement with them is not empirical validation against ground measurements.
