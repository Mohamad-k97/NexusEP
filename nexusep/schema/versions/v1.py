"""Schema-version dispatch target for canonical scenario version 1.0.0."""

from nexusep.schema.scenario import ScenarioV1

SCHEMA_VERSION = "1.0.0"
Scenario = ScenarioV1

__all__ = ["SCHEMA_VERSION", "Scenario", "ScenarioV1"]
