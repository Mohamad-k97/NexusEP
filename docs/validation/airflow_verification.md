# Prescribed airflow and contaminant verification

Validation category: **verification**.

Model claims: **AIRFLOW-1**, **CO2-1**.

Phases covered: **4.10** and **4.12**. These tests verify NexusEP's declared
prescribed-flow equations. They do not validate pressure-driven infiltration
or window ventilation against measurements.

## Implemented contract

NexusEP currently represents outdoor infiltration, fixed mechanical
ventilation, and window airflow as balanced outdoor mixing. Each non-zero
outdoor exchange is emitted as two traceable paths: outdoor-to-zone supply and
zone-to-outdoor exhaust. Interzone exchange is a symmetric pair with the same
flow in each direction. Prescribed paths retain the 1.2 kg/m³ diagnostic
convention. The vertical two-opening model derives dry-air density from zone
temperature and timestep atmospheric pressure and reports equal opposing mass
flow; it does not solve zone pressures.

For a closed set of well-mixed zones, the building CO₂ step now solves all
concentrations simultaneously by backward Euler:

```text
(V_i/dt + q_out,i + sum(q_ij)) C_i,next
    - sum(q_ij C_j,next)
  = (V_i/dt) C_i,old + q_out,i C_out + 1e6 G_i
```

Here `V` is m³, `q` is m³/s, concentration is ppm, and `G` is m³/s of pure
CO₂. Simultaneous coupling is required for closed interzone exchange to
conserve `sum(V_i * C_i)` when zone volumes differ. The earlier zone-by-zone
update did not meet that invariant and was replaced.

## Analytical cases

The verification suite is
[`tests/unit/test_airflow_analytical.py`](../../tests/unit/test_airflow_analytical.py).
Each test declares `VALIDATION_CATEGORY = "verification"`.

| Case | Verified result | Tolerance / rule |
|---|---|---|
| One-zone infiltration plus fixed mechanical ventilation | Components add to total exchange; supply equals exhaust | `1e-9 m³/h` balance gate |
| Deliberate supply/exhaust mismatch | Residual is detected and converted to kg/s | `rho = 1.2 kg/m³` diagnostic convention |
| AIRNET Appendix B.7.1 fixed-flow subset | The imposed 1.0 kg/s maps to 3000 m³/h at the diagnostic density; pressure drop remains unsolved | exact unit conversion only |
| Two-zone equal exchange | Reciprocal directed paths and zero net flow | `1e-9 m³/h` |
| NIST two-opening equation 69 | Calculated mass flow equals the published centered-neutral-plane equation | `1e-12` relative |
| AIRNET Appendix B.6 doorway | 18/22 degC, 0.8 x 2.0 m, `Cd=0.78` gives 0.259145 kg/s against the reported approximately 0.259 kg/s opposing streams | `0.001 kg/s` absolute (source is rounded) |
| Equal-temperature and reversed-temperature doorway | Equal temperature gives zero buoyancy flow; swapping zone temperatures preserves exchange magnitude | exact zero / `1e-12` relative |
| Two-zone CO₂, unequal volumes | High zone decreases, low zone increases, `sum(V*C)` is conserved | `1e-9 ppm·m³` absolute |
| CO₂ timestep convergence | Backward-Euler result approaches the closed-form exchange solution monotonically | Finest tested step `0.25 min`, west-zone error `< 0.4 ppm` after one hour |
| Closed window | Exactly zero window flow | exact |
| Zero wind | Exactly zero window flow | exact |
| Opening area | Larger supported opening produces larger flow before the safety cap | strict ordering |
| Wind orientation | Aligned wind produces flow; perpendicular wind produces zero | cosine roundoff below `1e-12` is zeroed |
| Outdoor temperature change | Does not create or reverse window flow | documents absent buoyancy coupling |

Command:

```powershell
uv run pytest -q tests/unit/test_airflow_analytical.py
```

Current result: **14 passed**.

## Scope and gates

- The outdoor records are balanced mixing approximations, not independently
  solved supply and exhaust paths.
- The window model uses opening area, local wind speed, and façade alignment,
  with a per-window safety cap. It receives no indoor temperature or zone
  pressure. Vertical internal openings can additionally use the symmetric
  centered-neutral-plane NIST two-opening buoyancy equation.
- Interzone exchange is symmetric. Vertical openings may be temperature-driven;
  prescribed compatibility paths remain explicit. Neither can represent a
  displaced neutral pressure level or unequal two-way doorway streams.
- CO₂ is one well-mixed concentration per zone. The physical test range stays
  above the model's 300 ppm lower bound; activating that defensive bound can
  break a pure conservation comparison and must be reported.
- General pressure-, stack-, horizontal-opening, and wind-pressure empirical
  claims remain blocked until a defensible pressure-network solver,
  boundary-pressure contract, and matched
  comparison cases exist.
