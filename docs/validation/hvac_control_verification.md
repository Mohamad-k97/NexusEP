# Ideal/full-capacity HVAC control verification

Validation category: **verification**.

Model claim: **HVAC-1**.

Phase covered: **4.17**.

## Frozen controller contract

NexusEP currently implements a zone-level bang-bang sensible-load controller,
not a modulating equipment model:

```text
heating activates when T_zone < T_heat_setpoint - deadband / 2
cooling activates when T_zone > T_cool_setpoint + deadband / 2
active delivered power = declared capacity
delivered energy [Wh] = delivered power [W] * interval [h]
input energy [Wh] = delivered energy [Wh] / efficiency_or_COP
```

Within either hysteresis band the previous same-mode command is retained; with
no command history the mode is off. Heating and cooling are mutually
exclusive. A missing system or zero capacity produces zero command and zero
power.

The interval-start zone state selects the command applied during that same
interval. The resulting physical state is visible at the next timestep. There
is no additional one-timestep command delay. The verification case applies a
3,000 W command for 900 seconds to a 900,000 J/K adiabatic node and obtains
exactly 21 degC from an 18 degC initial state; the controller then switches
off at the next interval boundary.

## Executed cases

[`tests/unit/test_ideal_hvac_control.py`](../../tests/unit/test_ideal_hvac_control.py)
checks:

- heating below the lower activation threshold;
- cooling above the upper activation threshold;
- off and history-dependent behavior inside the deadband;
- unavailable and zero-capacity systems;
- exact declared-capacity limiting;
- current-interval application and next-step state/control transition;
- no simultaneous heating and cooling across extreme and boundary states;
- exact delivered and input energy for heating efficiency 0.8 and cooling COP
  4.0.

Command and result:

```powershell
uv run pytest -q tests/unit/test_ideal_hvac_control.py
```

**14 passed.** The Phase 4.17 exit criterion is met for the declared
bang-bang/full-capacity sensible controller and its energy accounting.

## Excluded claims

This verification does not establish equipment efficiency maps, cycling,
minimum on/off time, fan or pump energy, ducts, hydronics, latent control,
part-load ratios, thermostat sensor dynamics, or equipment degradation. Those
features require separate model claims and tests before their outputs can be
described as verified.
