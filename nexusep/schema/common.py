"""Common immutable types for canonical scenario schema version 1."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ExternalID = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$",
    ),
]
FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
Fraction = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
PositiveFloat = Annotated[float, Field(gt=0.0, allow_inf_nan=False)]
NonnegativeFloat = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]


class CanonicalModel(BaseModel):
    """Strict-key, frozen base for canonical models."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=False,
        validate_default=True,
    )


class ScenarioMetadata(CanonicalModel):
    """Human-facing scenario identity and validation purpose."""

    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    description: str = ""
    scenario_kind: Literal["validated", "smoke_test", "benchmark", "profile"]
    tags: tuple[str, ...] = ()


class SimulationPeriod(CanonicalModel):
    """Fixed timezone-aware simulation period."""

    start_datetime: datetime
    timezone: Annotated[str, StringConstraints(min_length=1)]
    n_timesteps: Annotated[int, Field(ge=1, le=525_600)]
    dt_minutes: Annotated[float, Field(gt=0.0, le=60.0, allow_inf_nan=False)]

    @model_validator(mode="after")
    def validate_timezone_alignment(self) -> SimulationPeriod:
        if (
            self.start_datetime.tzinfo is None
            or self.start_datetime.utcoffset() is None
        ):
            raise ValueError("start_datetime must include an explicit UTC offset")
        try:
            timezone_info = ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as error:
            raise ValueError(
                "timezone must be an available IANA timezone name"
            ) from error
        normalized = self.start_datetime.astimezone(timezone_info)
        if (
            normalized.replace(tzinfo=None) != self.start_datetime.replace(tzinfo=None)
            or normalized.utcoffset() != self.start_datetime.utcoffset()
        ):
            raise ValueError(
                "start_datetime wall time and offset must agree with timezone"
            )
        return self


class ProvenanceRecord(CanonicalModel):
    """Audit record for a materialized canonical value."""

    target_path: Annotated[str, StringConstraints(pattern=r"^/")]
    method: Literal["provided", "derived", "defaulted"]
    source_paths: tuple[str, ...] = ()
    rule: Annotated[str, StringConstraints(min_length=1)]


class TransformationRecord(CanonicalModel):
    """Loader audit entry for defaults, migrations, derivations, and paths."""

    kind: Literal["default", "migration", "derived", "path_resolution"]
    target_path: Annotated[str, StringConstraints(pattern=r"^/")]
    source_paths: tuple[str, ...] = ()
    rule: Annotated[str, StringConstraints(min_length=1)]
