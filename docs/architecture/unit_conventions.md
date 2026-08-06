# Canonical unit conventions

## Scope

These rules cover every public numeric input and required output for
`multizone_dwelling_v1`. Engine-native fields are converted at adapters and are
not evidence that the engine already conforms.

## Naming and units

| Quantity | Canonical suffix | Unit |
|---|---|---|
| temperature | `_c` | degrees Celsius |
| power / heat flow | `_w` | watt |
| interval or accumulated energy | `_wh` | watt-hour |
| mass flow | `_kg_s` | kilogram per second |
| volume flow | `_m3_s` | cubic metre per second |
| pressure | `_pa` | pascal |
| concentration | `_ppm`, `_kg_kg` | parts per million, kilogram per kilogram |
| area | `_m2` | square metre |
| volume | `_m3` | cubic metre |
| length | `_m` | metre |
| angle | `_deg` | degree |
| duration | `_minutes` | minute; the period field remains `dt_minutes` for compatibility |
| speed | `_m_s` | metre per second |
| irradiance/transmittance coefficient | `_w_m2`, `_fraction` | watt per square metre, dimensionless fraction |
| thermal transmittance | `_w_m2_k` | watt per square metre-kelvin |
| heat capacity | `_j_k` | joule per kelvin |
| illuminance | `_lux` | lux |

Counts, indices, seeds, and coefficients such as COP use unit `1` and must be
identified explicitly in the registry.

Canonical relative humidity is always `relative_humidity_fraction` in `[0, 1]`.
Percent-valued legacy fields are divided by 100 only in adapters. A bare
`relative_humidity` public key and a canonical percent field are forbidden.

## Accepted ranges

The machine-readable registry is authoritative for field-specific bounds.
General safety envelopes are:

- zone temperature: `[-50, 80] °C`;
- weather/sky temperature: `[-100, 100] °C`;
- relative-humidity fraction: `[0, 1]`;
- humidity ratio: `[0, 0.1] kg/kg`;
- CO2 concentration: `[0, 100000] ppm`, with normal scenarios expected above
  zero;
- pressure: `[10000, 120000] Pa`;
- areas, volumes, capacities, power, energy, flows, gains, and irradiance:
  non-negative, with tighter schema bounds where appropriate;
- fractions: `[0, 1]`;
- azimuth: `[0, 360)` degrees; tilt: `[0, 180]` degrees; and
- timestep index and counts: non-negative integers, with `n_timesteps >= 1`.

Bounds are validation envelopes, not clipping instructions. Adapters must reject
invalid public input. Engines must report out-of-range output as a failed
invariant; they may not silently clamp unless the physical model explicitly
defines the limit and exposes that event.

## Conversion locations

1. Inbound adapters translate legacy aliases and units into the canonical
   contract before engine encoding.
2. Engine encoders translate canonical values into backend-native arrays or
   objects.
3. Kernels and aggregators operate in one documented internal unit and do not
   perform presentation conversions.
4. Outbound adapters translate backend state into canonical result units.
5. Display/export layers may format values but must not change stored precision
   or aggregation meaning.

Conversions must not occur in more than one layer. Adapter tests include round
trips for every non-identity conversion.

## Energy and aggregation

For a fixed timestep, canonical interval energy is:

```text
interval_energy_wh = average_power_w * dt_minutes / 60
```

Power is the timestep-average unless a field explicitly says instantaneous.
An `_energy_wh` field is interval energy unless prefixed with `cumulative_`.
Scenario energy is the sum of interval energy. Zone energies sum to dwelling
energy; dwelling energies sum to building energy. Aggregators must preserve the
distinction among delivered heating/cooling, equipment input electricity,
lighting, ventilation fans, and appliances.

Consumption and delivered heating/cooling magnitudes are non-negative. Signed
heat balance uses explicit `heat_gain_w` (positive into the zone) and
`heat_loss_w` (positive out of the zone), rather than overloading one ambiguous
energy field.

## Precision and comparison

- Canonical numeric computation and serialization use IEEE-754 binary64
  (`float64`); IDs, counts, and indices use signed 64-bit integers where stored
  numerically.
- No rounding occurs before conservation checks or aggregation.
- Serialization preserves enough decimal digits for a binary64 round trip.
- Categorical values, IDs, schema, row order, commands, events, and indices are
  compared exactly.
- Numeric tolerance is field-group-specific and versioned with parity evidence.
  The Phase 1 deterministic-object default (`rtol=1e-12`, `atol=1e-12`) is a
  baseline measurement, not automatically the cross-engine tolerance.
- NaN and infinity are invalid in required canonical fields. Optional missing
  values use JSON `null`, never NaN.

`contracts/multizone_dwelling_v1.units.json` is the authoritative public field
registry. Each numeric schema property carries an `x-unit` and
`x-registry-path`, and contract tests require complete agreement.

