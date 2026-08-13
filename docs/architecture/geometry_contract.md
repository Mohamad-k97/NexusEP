# Geometry tiers and provenance

## Tier 1: required thermal topology

`multizone_dwelling_v1` compiles from thermal topology without GIS or a full
solid model. The required tier contains:

- stable zone identity and explicit building/dwelling membership;
- zone volume;
- explicit exterior and paired interzone boundary topology;
- surface identity, owner zone, area, and boundary classification;
- thermal transmittance and heat capacity required by the selected model;
- opening identity, owner surface/zone, area, openable area, and connected
  boundary/zone;
- explicit exterior boundary identity, surface/opening thermal-bridge
  conductance, static solar-shading factor, infiltration rate, and interzone
  airflow-opening area/fraction where those paths are enabled;
- azimuth and tilt when solar gains or daylight are enabled; and
- explicit enabled features, orientation convention, applied defaults, and
  derived-value provenance in the loaded scenario.

The current minimal scenario enables airflow, solar gains, and daylight, so its
surface orientation and opening optical properties are required. A later
contract may conditionally relax fields only when the associated feature is
explicitly disabled.

## Tier 2: optional geometric detail

The following may be attached by future versioned extensions or sidecars but is
not required to compile version 1 physics:

- vertices and complete 3D polygons;
- geographic coordinates and coordinate reference systems;
- detailed shading objects;
- material-layer geometry;
- visualization metadata; and
- GIS source references.

Optional detail has no version 1 physical meaning. Adding or removing it must
leave the canonical ID registry, required graph nodes/connections, numeric graph
properties, and graph hash unchanged. An enabled feature that needs such detail
must promote it to required geometry in a new contract version rather than
silently alter calculations when the detail happens to be present.

## Defaults and derived values

Required physical fields are never inferred by a backend. A loader may derive
or default a value only before compilation, must materialize the resulting value
in the loaded scenario, and must add a provenance record containing:

- the target JSON path;
- `provided`, `derived`, or `defaulted` method;
- source paths, if any; and
- the deterministic rule or source description.

An explicit empty `defaults_applied` list means no defaults were used. The
compiler also records provenance for graph-derived values such as net opaque
area and orientation inherited by an opening. Missing optional geometry means
“not supplied”; it is never a signal to select different physics.
