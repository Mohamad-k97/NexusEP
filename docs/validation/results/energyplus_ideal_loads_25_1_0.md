# EnergyPlus 25.1 ideal-load comparison

Validation category: comparative validation
Model claim(s): HVAC-1
Data source IDs: energyplus-25.1.0

## Result

EnergyPlus 25.1.0-68a4a7c774 completed an original three-zone, 24-hour
adiabatic fixture with zero warnings and zero severe errors. The fixture is
not derived from an ASHRAE publication. Constant sensible loss/gain creates a
1,000 W heating case, a 1,500 W cooling case, and an unloaded 23 degC
deadband case with 20/24 degC thermostat setpoints.

| Quantity | EnergyPlus | NexusEP | Absolute difference | Tolerance | Result |
|---|---:|---:|---:|---:|---|
| Heating delivered power | 999.999999407 W | 1,000 W | 5.93e-7 W | 0.001 W | pass |
| Cooling delivered power | 1499.999999708 W | 1,500 W | 2.92e-7 W | 0.001 W | pass |
| Heating energy per hour | 999.999999407 Wh | 1,000 Wh | 5.93e-7 Wh | 0.001 Wh | pass |
| Cooling energy per hour | 1499.999999708 Wh | 1,500 Wh | 2.92e-7 Wh | 0.001 Wh | pass |
| Opposite-mode power in heating/cooling zones | 0 W | 0 W | 0 W | 0.001 W | pass |
| Heating and cooling power in deadband zone | 0 W | 0 W | 0 W | 0.001 W | pass |
| EnergyPlus controlled temperatures | 20, 24, 23 degC | not compared | at targets within 1.76e-9 degC | 1e-6 degC | pass for reference fixture |

All registered comparison quantities passed. The compact JSON records the
EnergyPlus executable, input, and weather SHA-256 values as well as every
comparison value and tolerance.

## Interpretation

This result supports only ideal sensible delivered-load accounting, mutually
exclusive heating/cooling modes, deadband operation, and one-hour
power-to-energy integration. EnergyPlus modulates an unlimited ideal load to
hold a setpoint. NexusEP currently applies a declared full capacity when its
bang-bang controller is outside the activation band. For the comparison,
NexusEP capacities are deliberately set to the independently imposed
EnergyPlus steady loads. Zone temperature trajectories are therefore not
claimed to be numerically equivalent.

The result is not an HVAC equipment-performance validation and is not an
ASHRAE Standard 140 pass. It does not test COP curves, furnace efficiency,
fans, ducts, ventilation, humidity control, cycling, overload recovery, or
part-load behavior.

## Reproduction

```powershell
uv run python scripts/validation_data/compare_energyplus_ideal_loads.py `
  --energyplus-exe C:\EnergyPlusV25-1-0\energyplus.exe `
  --input data/validation/fixtures/energyplus-ideal-loads-25.1.0/energyplus_ideal_loads.idf `
  --weather C:\EnergyPlusV25-1-0\WeatherData\USA_CO_Golden-NREL.724666_TMY3.epw `
  --output-directory artifacts/benchmarks/hvac/energyplus-comparison `
  --result-json data/validation/fixtures/energyplus-ideal-loads-25.1.0/comparison.json
```

The executable integration test repeats the comparison when EnergyPlus 25.1
is installed at `C:\EnergyPlusV25-1-0`; otherwise it is collected and skipped
with an explicit dependency reason.
