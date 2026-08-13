# Surface solar-gain verification

Validation category: **verification** for the executed analytical cases
Future category: **comparative validation** for an authorized Standard 140 run
Model claims: `SOLAR-1` and the solar boundary of `THERMAL-1`

The new plane-of-array helper uses explicit north-clockwise surface azimuth,
tilt from horizontal, DNI projected by the incidence cosine, isotropic-sky
diffuse radiation, and optional ground-reflected GHI. Transmitted gain is
incident irradiance times opening area, solar transmittance, and unshaded
fraction.

Executed analytical cases cover north/south/east/west vertical facades,
horizontal surfaces, zero and full transmittance, fully shaded openings,
direct-only and diffuse-only forcing, night-time direct suppression, and
Wh/m2 integration over fixed intervals. The tests verify exact equations and
direction/timing behavior; they are not comparative or empirical validation.

## Standard 140 gate

No ASHRAE Standard 140 comparative result is claimed in this repository.
ASHRAE's current supporting-files page states that the files are limited to
purchasers for personal use, and its page expressly prohibits entering ASHRAE
publication or related IP content into AI tools or creating AI-derived works
without written permission. Consequently no Standard 140 file was downloaded,
processed, or registered by this work.

An authorized human-run comparison can complete this gate by placing the
licensed inputs outside Git, recording checksums and permitted use, executing
the weather-driver/envelope cases without exposing protected content to an AI
tool, and publishing only results permitted by ASHRAE. Until then Phase 4.6's
comparative-validation portion remains blocked by source-use permission.

## Integration limitation

The existing object and array runners still use their documented GHI-only
solar approximation. The verified orientation-aware helper is intentionally
not wired into those runners in this phase because doing so would change the
Phase 1 behavioral baseline. Runner-level orientation credibility therefore
must not be claimed yet.
