"""Canonical version 1 weather source and timestep models."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from nexusep.schema.common import CanonicalModel, ExternalID, Fraction


class WeatherSource(CanonicalModel):
    """Explicit source policy; v1 never interpolates weather."""

    source_type: Literal["inline", "external_json", "synthetic_smoke_test"]
    path: Path | None = None
    interpolation: Literal["none"] = "none"
    allowable_derived_fields: tuple[Literal["timestamp"], ...] = ("timestamp",)
    synthetic_profile: Literal["constant_mild_v1"] | None = None

    @model_validator(mode="after")
    def validate_source_fields(self) -> WeatherSource:
        if len(self.allowable_derived_fields) != len(
            set(self.allowable_derived_fields)
        ):
            raise ValueError("allowable_derived_fields must be unique")
        if self.source_type == "external_json" and self.path is None:
            raise ValueError("external_json weather requires path")
        if self.source_type != "external_json" and self.path is not None:
            raise ValueError("path is allowed only for external_json weather")
        if self.source_type == "synthetic_smoke_test":
            if self.synthetic_profile is None:
                raise ValueError("synthetic weather requires a named profile")
        elif self.synthetic_profile is not None:
            raise ValueError(
                "synthetic_profile is allowed only for synthetic_smoke_test weather"
            )
        return self


class WeatherState(CanonicalModel):
    """Normalized boundary conditions for one half-open timestep interval."""

    scenario_id: ExternalID
    timestep_index: Annotated[int, Field(ge=0)]
    timestamp: datetime
    outdoor_temperature_c: Annotated[
        float, Field(ge=-100.0, le=100.0, allow_inf_nan=False)
    ]
    relative_humidity_fraction: Fraction
    atmospheric_pressure_pa: Annotated[
        float, Field(ge=10_000.0, le=120_000.0, allow_inf_nan=False)
    ]
    wind_speed_m_s: Annotated[float, Field(ge=0.0, le=100.0, allow_inf_nan=False)]
    wind_direction_deg: Annotated[float, Field(ge=0.0, lt=360.0, allow_inf_nan=False)]
    direct_normal_radiation_w_m2: Annotated[
        float, Field(ge=0.0, le=2_000.0, allow_inf_nan=False)
    ]
    diffuse_horizontal_radiation_w_m2: Annotated[
        float, Field(ge=0.0, le=2_000.0, allow_inf_nan=False)
    ]
    global_horizontal_radiation_w_m2: Annotated[
        float, Field(ge=0.0, le=2_000.0, allow_inf_nan=False)
    ]
    outdoor_co2_ppm: Annotated[float, Field(ge=0.0, le=100_000.0, allow_inf_nan=False)]
    sky_temperature_c: (
        Annotated[float, Field(ge=-100.0, le=100.0, allow_inf_nan=False)] | None
    ) = None
    outdoor_illuminance_lux: (
        Annotated[float, Field(ge=0.0, le=250_000.0, allow_inf_nan=False)] | None
    ) = None
    outdoor_noise_db: (
        Annotated[float, Field(ge=0.0, le=200.0, allow_inf_nan=False)] | None
    ) = None
    rain: bool | None = None

    @model_validator(mode="after")
    def validate_aware_timestamp(self) -> WeatherState:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("weather timestamp must include an explicit UTC offset")
        return self
