# NZERTF virtual-occupant schedule verification

Validation category: **verification**.

Model claim: `OCC-1`.

The NIST NZERTF Year 1 minute load file contains flags for a simulated
four-person family, room lighting, plug loads, and appliances. Those flags are
prescribed experimental inputs. They can verify schedule execution and energy
attribution, but they cannot validate natural human stochasticity.

## Registered fixture

The raw registry records the first 2,097,152 HTTP bytes of the official
367,266,298-byte `Load-minute.csv` object and retains NIST's official full-file
checksum separately in the known-gaps record. A deterministic preprocessing
command extracts the first 900 complete records before the first large clock
gap. The compact fixture includes:

- all four stable occupant IDs and `away`/`upstairs`/`downstairs` locations;
- cooktop, dishwasher, and oven flags;
- aggregate first- and second-floor light flags; and
- separate first- and second-floor lighting power channels.

Raw source timestamps have small acquisition jitter. The fixture preserves
them as `source_timestamp` and constructs a separate canonical one-minute
`timestamp` from the contiguous sequence counter. The transformation is
therefore visible and reproducible.

`nexusep.validation_data.nzertf` strictly converts every row to canonical
`OccupantStepState` and `ActionEvent` objects. Contract tests verify fixed
cadence, complete stable ID restoration, named zones, reproducible event runs,
and nonnegative separated lighting power.

## Remaining gate

This verifies ingestion and exact schedule decoding, not full NexusEP engine
energy reproduction. Closing the Phase 4.24 energy-attribution gate still
requires a canonical NZERTF building/system scenario, complete raw load file,
explicit mapping from each status/power channel to NexusEP gains and systems,
missing-record masks, and per-channel energy tolerances. That work is distinct
from the Year 1 calibration/Year 2 blind-validation protocol.
