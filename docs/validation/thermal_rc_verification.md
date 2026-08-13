# Elementary RC response verification

Validation category: **verification**
Model claim(s): `THERMAL-1`
Evidence: `tests/unit/test_thermal_rc_analytical.py`

## Scope

The Phase 4.7 suite verifies the object engine's reduced-order RC equations
against analytical or closed-form reference responses. It covers exponential
decay, the `C/H` time constant, constant-gain equilibrium, an outdoor
temperature step, an adiabatic heating step, two-zone exchange, an adiabatic
two-node zone, invalid zero capacity, and timestep convergence.

The scalar reference equation is

```text
C dT/dt = sum(H_i (T_i - T)) + Q
```

and its backward-Euler update is

```text
T[n+1] = ((C/dt) T[n] + sum(H_i T_i) + Q)
         / ((C/dt) + sum(H_i)).
```

For the object engine's two-node zones, air and mass temperatures are solved
as one coupled linear system. All zones connected by interzone conductances
are included in the same system. This makes air/mass and interzone exchanges
equal and opposite in a closed model.

## Acceptance rules

- scalar discrete equations: absolute tolerance `1e-12 degC`;
- constant-gain equilibrium: absolute temperature tolerance `1e-9 degC`;
- closed-system stored-energy residual: absolute tolerance `1e-6 J`;
- interzone flow symmetry: absolute tolerance `1e-12 W`;
- adiabatic equilibrium after the declared settling period: `1e-3 degC`;
- one-hour continuous-solution error at a 60-second step: below `0.07 degC`;
- convergence errors must decrease monotonically as the timestep decreases.

These tolerances test the specified reduced-order equations and numerical
scheme. They are not evidence that the parameters represent a real building.

## Defect corrected during verification

The former object update solved the air node first against the old mass
temperature and then solved the mass node against the new air temperature.
That asymmetric exchange lost approximately `21.2 kJ` in a closed illustrative
zone over one 10-minute step. The solver now uses a coupled backward-Euler
linear solve. The analytical suite guards this conservation property.

## Current boundary

This report verifies the object thermal kernel only. The array thermal kernel
retains its separately documented implementation and is not promoted by these
results. Object/array numerical parity must be measured after the array solver
adopts or explicitly justifies an equivalent conservative discretization.
