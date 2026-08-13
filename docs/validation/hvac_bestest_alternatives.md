# Open alternatives to ASHRAE HVAC resource ingestion

Validation category: **comparative validation planning and one executed open
comparison; no Standard 140 result claimed**.

Model claim: **HVAC-1**.

Phase covered: **4.18, alternative route**.

## Why the ASHRAE package is not ingested

ASHRAE's current supplemental-files page states that the 140-2023 package is
available only to purchasers and for personal use. The same page displays an
AI policy prohibiting entry of ASHRAE publication content or related
intellectual property into AI tools. NexusEP therefore does not download,
parse, reproduce, or derive fixtures from that package in this workflow.

This is an evidence-access gate, not a failed simulation. No Standard 140
case is marked passed, failed, or approximated.

## Open reference ladder

1. **Executed now - EnergyPlus IdealLoadsAirSystem.** EnergyPlus 25.1 is
   BSD-licensed and already installed. An original, adiabatic three-zone case
   compares the supported ideal sensible-load contract. The registered result
   is in
   [`results/energyplus_ideal_loads_25_1_0.md`](results/energyplus_ideal_loads_25_1_0.md).
2. **Future equipment-map suite - original NREL HVAC BESTEST Volume 1.** The
   public NREL report `NREL/TP-550-30152`, DOI `10.2172/15000340`, provides
   steady-state analytical cases E100-E200 for unitary cooling performance
   maps. These cases are not compatible with NexusEP until it implements
   manufacturer-map cooling capacity and power behavior.
3. **Future dynamic equipment suite - NREL HVAC BESTEST Volume 2.** The public
   NREL report `NREL/TP-550-36754` extends the equipment tests with hourly
   dynamics, mixing, economizer, thermostat setup, and overload behavior.
   NexusEP does not yet implement those components.
4. **Future air-distribution suite - NREL Airside HVAC BESTEST.** Public
   `NREL/TP-5500-66000`, DOI `10.2172/1244668`, provides analytical airside
   mass/energy-balance cases. NexusEP lacks an air-loop, fan, coil, duct, and
   economizer graph, so these remain unsupported.

## Case classification

| Family | Current classification | Reason |
|---|---|---|
| Ideal sensible heating/cooling load | tolerance match | Open EnergyPlus comparison passed for delivered power, Wh integration, deadband, and opposite-mode exclusion |
| Unitary cooling performance maps | missing feature | No temperature/flow performance curves or equipment electrical-power map |
| Fuel-fired furnace performance | missing feature | No furnace fuel/stack/jacket-loss or cycling model |
| Airside HVAC equipment | missing feature | No supply/return air loop, fan, coil, duct, mixing-box, or economizer model |
| Part-load and cycling cases | missing feature | Controller has no minimum runtime, cycling degradation, or part-load map |
| Latent HVAC control | missing feature | Moisture model is not coupled to HVAC latent removal or thermal latent feedback |

## Gate status

The supported ideal-load prerequisite now has an independently executable
comparative result. The original Phase 4.18 equipment-performance exit
criterion remains open: no cooling-equipment, furnace, or airside BESTEST
case may be run until the corresponding production model exists. Adding
nominal COP constants or silently translating a case to an ideal load would
not satisfy that criterion.
