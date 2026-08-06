# Canonical timestep weather contract

## Normalized required values

Every normalized timestep contains exactly one interval-start timestamp and the
following required boundary conditions in canonical units:

| Field | Meaning | Unit/range |
|---|---|---|
| `timestamp` | start of the half-open timestep interval | timezone-aware ISO 8601 |
| `outdoor_temperature_c` | outdoor dry-bulb temperature | °C, `[-100, 100]` |
| `relative_humidity_fraction` | outdoor relative humidity | fraction, `[0, 1]` |
| `atmospheric_pressure_pa` | atmospheric pressure | Pa, `[10000, 120000]` |
| `wind_speed_m_s` | wind speed | m/s, `[0, 100]` |
| `wind_direction_deg` | direction clockwise from true north | degrees, `[0, 360)` |
| `direct_normal_radiation_w_m2` | direct-normal solar irradiance | W/m², `[0, 2000]` |
| `diffuse_horizontal_radiation_w_m2` | diffuse-horizontal solar irradiance | W/m², `[0, 2000]` |
| `global_horizontal_radiation_w_m2` | global-horizontal solar irradiance | W/m², `[0, 2000]` |
| `outdoor_co2_ppm` | outdoor CO₂ concentration | ppm, `[0, 100000]` |

All three solar components are required in version 1. This avoids making solar
position algorithms or decomposition models an implicit weather dependency.

Optional normalized fields are `sky_temperature_c`,
`outdoor_illuminance_lux`, `outdoor_noise_db`, and `rain`. Omission is
materialized as JSON `null` and recorded by the loader. Backends must treat null
as unavailable, not as zero and not as permission to select a hidden default.

## Missing values and interpolation

Required values may not be absent, null, NaN, or infinite. A missing or invalid
required value is a field-level validation error before graph compilation.
Version 1 interpolation is always `none`: the loader neither fills gaps nor
resamples weather. Source records must already match the fixed simulation grid.

Weather indices must be unique and cover `[0, n_timesteps)`. Input list order is
not semantic. Each timestamp must equal the canonical start of its indexed
interval after timezone normalization. The final weather state applies through
the derived exclusive end; there is no endpoint record or extrapolation.

## Allowable derived fields

Only `timestamp` may be derived in a normal version 1 load, and only from a
valid `timestep_index` plus the canonical simulation clock. Its derivation is
recorded in the audit log. Dry-bulb temperature, humidity, pressure, wind,
solar radiation, and outdoor CO₂ are never derived by the canonical loader.

In particular, global radiation is not reconstructed from direct/diffuse
components, and illuminance is not estimated from irradiance. Such processing
must be an explicit, versioned weather-preparation step that writes complete
canonical weather and provenance before scenario loading.

## Weather sources and synthetic smoke data

`weather_source.source_type` is one of:

- `inline` — records are present in the scenario;
- `external_json` — a JSON/JSONC array or object containing `weather_series`,
  resolved relative to the scenario file; or
- `synthetic_smoke_test` — the explicitly named `constant_mild_v1` profile.

Synthetic weather is never an automatic fallback. It is accepted only when
metadata declares `scenario_kind: smoke_test`, the scenario has a non-empty
name, and the named synthetic profile is explicitly selected. It is rejected
for validated, benchmark, and profile scenarios. Synthetic results are useful
only for loader/initialization smoke tests and are not validation evidence.

The canonical `WeatherState` tuple is the only weather adapter input. Both
engines must receive values decoded from that same normalized tuple for each
`timestep_index`.

