"""Canonical version 1 geometry and topology models."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from nexusep.schema.common import (
    CanonicalModel,
    ExternalID,
    Fraction,
    NonnegativeFloat,
    PositiveFloat,
    ProvenanceRecord,
)


class GeometryConfiguration(CanonicalModel):
    geometry_tier: Literal["thermal_topology_v1"]
    enabled_features: tuple[Literal["airflow", "solar_gains", "daylight"], ...]
    orientation_convention: Literal[
        "azimuth_clockwise_from_true_north_tilt_from_horizontal"
    ]
    optional_geometry_affects_physics: Literal[False]
    defaults_applied: tuple[ProvenanceRecord, ...]
    derived_values: tuple[ProvenanceRecord, ...]

    @model_validator(mode="after")
    def validate_unique_features(self) -> GeometryConfiguration:
        if len(self.enabled_features) != len(set(self.enabled_features)):
            raise ValueError("enabled_features must be unique")
        return self


class Opening(CanonicalModel):
    scenario_id: ExternalID
    building_id: ExternalID
    dwelling_id: ExternalID
    zone_id: ExternalID
    surface_id: ExternalID
    opening_id: ExternalID
    opening_type: Literal["window"]
    boundary_type: Literal["exterior"]
    adjacent_zone_id: None
    area_m2: Annotated[float, Field(gt=0.0, le=1_000.0, allow_inf_nan=False)]
    openable_area_m2: Annotated[float, Field(ge=0.0, le=1_000.0, allow_inf_nan=False)]
    thermal_transmittance_w_m2_k: Annotated[
        float, Field(ge=0.0, le=20.0, allow_inf_nan=False)
    ]
    thermal_bridge_conductance_w_k: Annotated[
        float, Field(ge=0.0, le=100_000.0, allow_inf_nan=False)
    ] = 0.0
    solar_transmittance_fraction: Fraction
    visible_transmittance_fraction: Fraction
    solar_shading_factor: Fraction = 1.0

    @model_validator(mode="after")
    def validate_openable_area(self) -> Opening:
        if self.openable_area_m2 > self.area_m2:
            raise ValueError("openable_area_m2 cannot exceed area_m2")
        return self


class Surface(CanonicalModel):
    scenario_id: ExternalID
    building_id: ExternalID
    dwelling_id: ExternalID
    zone_id: ExternalID
    surface_id: ExternalID
    boundary_type: Literal["exterior", "interzone"]
    adjacent_zone_id: ExternalID | None
    paired_surface_id: ExternalID | None
    external_boundary_id: ExternalID | None = None
    area_m2: Annotated[float, Field(gt=0.0, le=10_000.0, allow_inf_nan=False)]
    thermal_transmittance_w_m2_k: Annotated[
        float, Field(ge=0.0, le=20.0, allow_inf_nan=False)
    ]
    thermal_bridge_conductance_w_k: Annotated[
        float, Field(ge=0.0, le=100_000.0, allow_inf_nan=False)
    ] = 0.0
    heat_capacity_j_k: Annotated[
        float, Field(ge=0.0, le=1_000_000_000_000.0, allow_inf_nan=False)
    ]
    azimuth_deg: Annotated[float, Field(ge=0.0, lt=360.0, allow_inf_nan=False)]
    tilt_deg: Annotated[float, Field(ge=0.0, le=180.0, allow_inf_nan=False)]
    airflow_opening_area_m2: Annotated[
        float, Field(ge=0.0, le=1_000.0, allow_inf_nan=False)
    ] = 0.0
    airflow_open_fraction: Fraction = 0.0
    openings: tuple[Opening, ...]

    @model_validator(mode="after")
    def validate_boundary(self) -> Surface:
        if self.boundary_type == "exterior":
            if self.adjacent_zone_id is not None or self.paired_surface_id is not None:
                raise ValueError(
                    "exterior surfaces cannot reference adjacent zones or pairs"
                )
            if self.airflow_opening_area_m2 != 0.0 or self.airflow_open_fraction != 0.0:
                raise ValueError(
                    "exterior surface airflow openings belong to Opening records"
                )
        else:
            if self.adjacent_zone_id is None or self.paired_surface_id is None:
                raise ValueError(
                    "interzone surfaces require adjacent_zone_id and paired_surface_id"
                )
            if self.external_boundary_id is not None:
                raise ValueError("interzone surfaces cannot name an external boundary")
            if self.airflow_opening_area_m2 > self.area_m2:
                raise ValueError("airflow_opening_area_m2 cannot exceed surface area")
            if self.airflow_opening_area_m2 == 0.0 and self.airflow_open_fraction != 0.0:
                raise ValueError(
                    "airflow_open_fraction requires a positive airflow opening area"
                )
        if self.boundary_type == "interzone" and self.openings:
            raise ValueError("version 1 interzone surfaces cannot contain openings")
        if sum(opening.area_m2 for opening in self.openings) > self.area_m2:
            raise ValueError("total opening area cannot exceed surface area")
        return self


class System(CanonicalModel):
    scenario_id: ExternalID
    building_id: ExternalID
    dwelling_id: ExternalID
    zone_id: ExternalID
    system_id: ExternalID
    system_type: Literal["heating", "cooling", "ventilation", "lighting"]
    max_heating_power_w: NonnegativeFloat | None = None
    heating_efficiency_fraction: Fraction | None = None
    heating_setpoint_c: (
        Annotated[float, Field(ge=-50.0, le=80.0, allow_inf_nan=False)] | None
    ) = None
    max_cooling_power_w: NonnegativeFloat | None = None
    cooling_cop: (
        Annotated[float, Field(gt=0.0, le=20.0, allow_inf_nan=False)] | None
    ) = None
    cooling_setpoint_c: (
        Annotated[float, Field(ge=-50.0, le=80.0, allow_inf_nan=False)] | None
    ) = None
    max_ventilation_volume_flow_m3_s: NonnegativeFloat | None = None
    max_lighting_power_w: NonnegativeFloat | None = None

    @model_validator(mode="after")
    def validate_type_fields(self) -> System:
        required_by_type = {
            "heating": (
                "max_heating_power_w",
                "heating_efficiency_fraction",
                "heating_setpoint_c",
            ),
            "cooling": (
                "max_cooling_power_w",
                "cooling_cop",
                "cooling_setpoint_c",
            ),
            "ventilation": ("max_ventilation_volume_flow_m3_s",),
            "lighting": ("max_lighting_power_w",),
        }
        missing = [
            field
            for field in required_by_type[self.system_type]
            if getattr(self, field) is None
        ]
        if missing:
            raise ValueError(
                f"{self.system_type} system is missing required fields: {missing}"
            )
        return self


class Zone(CanonicalModel):
    scenario_id: ExternalID
    building_id: ExternalID
    dwelling_id: ExternalID
    zone_id: ExternalID
    zone_type: Literal["living", "bedroom", "kitchen", "bathroom", "corridor", "other"]
    floor_area_m2: PositiveFloat
    volume_m3: PositiveFloat
    height_m: PositiveFloat
    initial_air_temperature_c: Annotated[
        float, Field(ge=-50.0, le=80.0, allow_inf_nan=False)
    ]
    initial_mean_radiant_temperature_c: Annotated[
        float, Field(ge=-50.0, le=80.0, allow_inf_nan=False)
    ]
    initial_relative_humidity_fraction: Fraction
    initial_co2_ppm: Annotated[float, Field(ge=0.0, le=100_000.0, allow_inf_nan=False)]
    infiltration_air_changes_per_hour: Annotated[
        float, Field(ge=0.0, le=20.0, allow_inf_nan=False)
    ] = 0.0
    surfaces: tuple[Surface, ...]
    systems: tuple[System, ...]


class Dwelling(CanonicalModel):
    scenario_id: ExternalID
    building_id: ExternalID
    dwelling_id: ExternalID
    floor_area_m2: PositiveFloat
    volume_m3: PositiveFloat
    zones: Annotated[tuple[Zone, ...], Field(min_length=2)]


class Building(CanonicalModel):
    scenario_id: ExternalID
    building_id: ExternalID
    floor_area_m2: PositiveFloat
    volume_m3: PositiveFloat
    height_m: PositiveFloat
    n_floors: Annotated[int, Field(ge=1, le=20)]
    dwelling: Dwelling
