# CO2 analytical and multizone verification

Validation category: **verification**.

Model claim: **CO2-1**.

Phases covered: **4.13** and the implemented analytical portion of **4.14**.

## Single-zone QICO2 contract

NIST Technical Note 2213 defines the balanced, well-mixed single-zone model
used by QICO2:

```text
V dC/dt = Q (C_out - C) + G
C(t) = C_ss + (C(0) - C_ss) exp(-Q t / V)
C_ss = C_out + G / Q
```

NexusEP uses m³, m³/s, and ppm rather than litres, litres per second, and
ppmv; the equations are dimensionally identical. The production timestep is
backward Euler, so finite-step output is checked for monotonic convergence to
the NIST analytical solution rather than required to equal it exactly.

[`tests/unit/test_co2_single_zone_analytical.py`](../../tests/unit/test_co2_single_zone_analytical.py)
verifies:

- constant occupancy and ventilation;
- occupancy and ventilation steps using piecewise analytical solutions;
- decay after occupants leave;
- zero generation with and without ventilation;
- the control-volume balance at every timestep.

For each timestep and zone, the emitted diagnostic is:

```text
storage_change_m3_s
  = generation_m3_s + airflow_transport_m3_s + balance_residual_m3_s
```

The ppm state represents an equivalent pure-CO2 volume. The tests also apply
an explicit fixed reference density of 1.842 kg/m³ to both sides to show that
the corresponding mass balance is proportional and closes. This does not
claim a temperature-independent CO2 density for general simulations.

## Multizone control-volume verification

[`tests/unit/test_contaminant_multizone_analytical.py`](../../tests/unit/test_contaminant_multizone_analytical.py)
uses a two-zone pair and a three-zone chain with unequal volumes, multiple
sources, reciprocal exchange, outdoor dilution, and a mechanical-ventilation
record. It checks:

- generation source attribution by zone;
- outdoor and interzone target attribution;
- exact reciprocal cancellation of interzone transport at building level;
- storage = generation + outdoor removal/dilution at every timestep;
- non-negative concentrations and directional mixing response;
- explicit source/destination paths for every airflow record.

The simultaneous building solve implements the same standard implicit
control-volume structure documented by CONTAM. It fixed the mass drift that
occurs when unequal-volume zones are advanced independently using only their
neighbour's old concentration.

## Current limits

- A well-mixed zone responds during the first timestep. Physical transport
  delay, plug flow, and one-dimensional convection-diffusion are not modeled.
- A mechanical-ventilation record is currently a balanced outdoor exchange.
  Independent extraction, replacement-air routing, fan/duct networks, and
  pressure balance are unsupported.
- The two- and three-zone cases are analytical NexusEP configurations. No
  CONTAM `.prj` file or CONTAM output is registered, so Phase 4.14 is not
  reported as comparative validation.
- The next CONTAM result must match volumes, fixed flows, source terms,
  initial concentrations, timestep method, and output units and then enter the
  scientific-result registry with hashes.

Commands and current result:

```powershell
uv run pytest -q tests/unit/test_co2_single_zone_analytical.py `
  tests/unit/test_contaminant_multizone_analytical.py
```

**9 passed.** The supported analytical mass-balance exit criterion is met;
transport-delay, independent-extraction, and executed-CONTAM comparison gates
remain open.
