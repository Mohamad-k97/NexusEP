# NIST CONTAM comparative-validation scope

Validation category: **verification and narrowly scoped comparative
validation**. No general pressure-network comparison is claimed.

Model claims in scope: **AIRFLOW-1**, **CO2-1**.

Phase covered: **4.11**.

## Registered verification sources

Two public NIST reports are held locally under the ignored raw-data directory
and registered by exact byte size and SHA-256:

- AIRNET, NISTIR 89-4072, DOI
  [10.6028/NIST.IR.89-4072](https://doi.org/10.6028/NIST.IR.89-4072),
  source ID `nist-airnet-1989`.
- CONTAM 3.4 User Guide, NIST TN 1887r1, DOI
  [10.6028/NIST.TN.1887r1](https://doi.org/10.6028/NIST.TN.1887r1),
  source ID `nist-contam-3.4-r1`.

The [NIST CONTAM product page](https://www.nist.gov/services-resources/software/contam)
describes CONTAM as public-domain software covering mechanically driven,
wind-driven, and buoyancy-driven multizone airflow and contaminant transport.
The manifests are indexed in
[`data/validation/registry.json`](../../data/validation/registry.json); the
large PDFs remain uncommitted.

## What can be compared now

The common reduced-order subset is deliberately small:

- fixed outdoor or mechanical volumetric flows;
- fixed reciprocal interzone mixing rates;
- the centered-neutral-plane vertical two-opening buoyancy equation;
- zone volumes and initial well-mixed trace-contaminant concentrations;
- prescribed outdoor concentration and zone generation;
- transient concentration response using a matched implicit integration
  method and timestep.

CONTAM TN 1887r1, section 8.2, derives contaminant conservation in a control
volume. Section 8.2.2 states that the standard implicit method solves the full
set of next-step concentrations simultaneously and describes its all-timestep
stability. This is corroborating numerical-method evidence for the coupled
NexusEP CO₂ solve; the analytical conservation and closed-form tests remain
the verification oracle.

AIRNET Appendix B.7.1 prescribes a constant flow of 1.0 kg/s in series with a
power-law element. NexusEP can represent only the imposed-flow part of that
case. The reported 115.342 Pa pressure drop is outside the current model and
must not be presented as a NexusEP comparison target.

## Comparative result and remaining blocks

| NIST capability / case | NexusEP status | Decision |
|---|---|---|
| Power-law crack pressure drop | No pressure unknowns or path pressure law | blocked |
| AIRNET Appendix B.6 buoyancy doorway: 18/22 °C, 0.8 × 2.0 m, `Cd=0.78` | Typed two-opening model returns 0.259145 kg/s | passed against the rounded approximately 0.259 kg/s opposing streams (`0.001 kg/s` absolute tolerance) |
| Wind and stack pressure | Local capped wind-opening approximation only | blocked |
| Fans, ducts, recirculation, filters, reactions, sorption | Not in the supported airflow/CO₂ contract | excluded |
| One-dimensional contaminant convection/diffusion | One well-mixed value per zone | excluded |

Successful execution of either program would not remove these model-scope
differences.

## Reproducible next comparison

The first executable CONTAM comparison should use two well-mixed zones with
fixed volumes, fixed prescribed reciprocal exchange, no pressure-dependent
paths, no reactions/removal, one trace contaminant, and the same initial and
outdoor concentrations. Before running it, record the CONTAM project file,
CONTAM version, flow-unit conversion, timestep method, timestep, input hashes,
and decoded output checksum. Compare per-zone concentration and total
contaminant residual separately.

Calibration is prohibited at this stage. It becomes meaningful only after the
two programs are configured to represent the same reduced-order assumptions
and the untouched comparison exposes a parameter that belongs to both models.
