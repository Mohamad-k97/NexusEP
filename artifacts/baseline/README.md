# Approved baseline manifests

Files in this directory are small, reviewable manifests used to compare later
recovery phases with the frozen Phase 1.0 state. Large/generated data belongs
in the ignored sibling directories.

- `phase_1_4_validation_matrix.json`: exact commands and outcomes.
- `deterministic_object_manifest.json`: object golden hashes and invariants.
- `object_profile.json`: object timing, memory, and profiler summary.
- `array_benchmark.json`: array timing, memory, determinism, and correctness.
- `artifact_manifest.json`: hashes for reports, inputs, raw artifacts, and
  protected legacy outputs; it intentionally excludes its own self-hash.
- `inputs/abbey_config_phase_1_5.jsonc`: frozen deterministic input snapshot.
- `phase_2_15_conformance.json`: shared structural/semantic backend suite.
- `phase_2_16_initial_parity.json`: quantity-specific measured differences,
  tolerances, classifications, and rationales for the first parity scenario.
