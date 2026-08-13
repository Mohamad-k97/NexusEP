"""Frozen calibration-split, acceptance, and uncertainty governance models."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from nexusep.jsonc import loads_strict_json

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    ),
]


class GovernanceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CalibrationSegment(GovernanceModel):
    dataset_id: Identifier
    segment_id: Identifier
    role: Literal["calibration", "validation", "blind_validation", "holdout"]
    start_date: date | None
    end_date_exclusive: date | None
    sealed: bool
    configuration_changes: tuple[NonEmptyText, ...]
    permitted_uses: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    prohibited_uses: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_interval_and_seal(self) -> CalibrationSegment:
        if (self.start_date is None) != (self.end_date_exclusive is None):
            raise ValueError("segment dates must both be supplied or both be null")
        if (
            self.start_date is not None
            and self.end_date_exclusive is not None
            and self.end_date_exclusive <= self.start_date
        ):
            raise ValueError("end_date_exclusive must be after start_date")
        if self.role != "calibration" and not self.sealed:
            raise ValueError("validation and holdout segments must remain sealed")
        return self


class CalibrationSplitDocument(GovernanceModel):
    governance_version: Literal["1.0.0"]
    validation_category: Literal["calibration_and_blind_validation_planning"]
    frozen_on: date
    global_prohibition: NonEmptyText
    segments: Annotated[tuple[CalibrationSegment, ...], Field(min_length=2)]

    @model_validator(mode="after")
    def validate_unique_nonoverlapping_segments(self) -> CalibrationSplitDocument:
        keys = [(item.dataset_id, item.segment_id) for item in self.segments]
        if len(keys) != len(set(keys)):
            raise ValueError("dataset/segment pairs must be unique")
        if not any(item.role == "calibration" for item in self.segments):
            raise ValueError("at least one calibration segment is required")
        if not any(item.role != "calibration" for item in self.segments):
            raise ValueError("at least one untouched holdout segment is required")
        for first_index, first in enumerate(self.segments):
            for second in self.segments[first_index + 1 :]:
                if (
                    first.dataset_id != second.dataset_id
                    or first.start_date is None
                    or second.start_date is None
                ):
                    continue
                assert first.end_date_exclusive is not None
                assert second.end_date_exclusive is not None
                overlaps = (
                    first.start_date < second.end_date_exclusive
                    and second.start_date < first.end_date_exclusive
                )
                if overlaps:
                    raise ValueError(
                        f"segments overlap for dataset {first.dataset_id!r}"
                    )
        return self


class AcceptanceCriterion(GovernanceModel):
    criterion_id: Identifier
    target_study: Identifier
    variable: NonEmptyText
    metric: NonEmptyText
    time_resolution: NonEmptyText
    warm_up: NonEmptyText
    uncertainty_treatment: NonEmptyText
    operator: Literal["less_than_or_equal"]
    acceptable_error: Annotated[float, Field(ge=0.0)]
    error_unit: NonEmptyText
    failure_severity: Literal["blocker", "major", "minor"]
    decision_priority: Literal["bias", "dynamics", "balanced", "distribution"]


class AcceptanceCriteriaDocument(GovernanceModel):
    governance_version: Literal["1.0.0"]
    validation_category: Literal["calibration_and_blind_validation_planning"]
    frozen_on: date
    freeze_status: Literal["frozen_before_fitting"]
    optimization_started: Literal[False]
    amendment_rule: NonEmptyText
    criteria: Annotated[tuple[AcceptanceCriterion, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_unique_criteria(self) -> AcceptanceCriteriaDocument:
        ids = [item.criterion_id for item in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("criterion_id values must be unique")
        return self


UncertaintyName = Literal[
    "measurement",
    "weather_input",
    "parameter",
    "structural_model",
    "numerical",
    "stochastic_occupant",
]


class UncertaintyComponent(GovernanceModel):
    name: UncertaintyName
    status: Literal["quantified", "pending", "not_applicable"]
    method: NonEmptyText
    evidence: NonEmptyText
    calibration_gate: NonEmptyText


class UncertaintyBudgetDocument(GovernanceModel):
    governance_version: Literal["1.0.0"]
    validation_category: Literal["verification_and_validation_planning"]
    frozen_on: date
    interval_policy: NonEmptyText
    components: Annotated[tuple[UncertaintyComponent, ...], Field(min_length=6)]

    @model_validator(mode="after")
    def validate_complete_budget(self) -> UncertaintyBudgetDocument:
        expected = {
            "measurement",
            "weather_input",
            "parameter",
            "structural_model",
            "numerical",
            "stochastic_occupant",
        }
        actual = [item.name for item in self.components]
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise ValueError("uncertainty budget must contain each required component once")
        return self


AlternativeClassification = Literal[
    "blocked but passed with alternative",
    "blocked and rejected with alternative",
    "blocked and no alternative",
]


class BlockedAlternativeEvaluation(GovernanceModel):
    gate_id: Identifier
    original_requirement: NonEmptyText
    original_status: Literal["blocked"]
    alternative_name: NonEmptyText
    alternative_scope: NonEmptyText
    equivalent_claim: bool
    execution_status: Literal["passed", "rejected", "not_available"]
    test_command: NonEmptyText | None
    evidence_paths: tuple[NonEmptyText, ...]
    rejection_or_limit: NonEmptyText
    alternative_classification: AlternativeClassification

    @model_validator(mode="after")
    def validate_classification(self) -> BlockedAlternativeEvaluation:
        expected = {
            "passed": "blocked but passed with alternative",
            "rejected": "blocked and rejected with alternative",
            "not_available": "blocked and no alternative",
        }[self.execution_status]
        if self.alternative_classification != expected:
            raise ValueError(
                "alternative_classification is inconsistent with execution_status"
            )
        if self.execution_status == "not_available":
            if self.test_command is not None or self.evidence_paths:
                raise ValueError(
                    "a no-alternative row cannot claim a test command or evidence"
                )
        elif self.test_command is None or not self.evidence_paths:
            raise ValueError("an executed alternative requires command and evidence")
        return self


class BlockedAlternativesDocument(GovernanceModel):
    governance_version: Literal["1.0.0"]
    validation_category: Literal["verification_and_validation_status_reporting"]
    assessed_on: date
    policy: NonEmptyText
    evaluations: Annotated[
        tuple[BlockedAlternativeEvaluation, ...], Field(min_length=1)
    ]

    @model_validator(mode="after")
    def validate_unique_gates(self) -> BlockedAlternativesDocument:
        gate_ids = [item.gate_id for item in self.evaluations]
        if len(gate_ids) != len(set(gate_ids)):
            raise ValueError("gate_id values must be unique")
        return self


def load_governance_document(
    path: Path,
    model_type: type[GovernanceModel],
) -> GovernanceModel:
    """Load a strict JSON governance document and reject unknown fields."""

    payload = loads_strict_json(
        path.read_text(encoding="utf-8"), source=path, jsonc=False
    )
    return model_type.model_validate(payload)
