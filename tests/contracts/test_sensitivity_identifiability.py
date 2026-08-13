"""Contract tests for pre-calibration sensitivity and identifiability gates."""

import pytest

from nexusep.validation_data.sensitivity import (
    CandidateParameter,
    TargetOutput,
    require_identifiable,
    run_local_sensitivity_analysis,
)

pytestmark = pytest.mark.contract
VALIDATION_CATEGORY = "verification"


def _parameter(name: str) -> CandidateParameter:
    return CandidateParameter(name, nominal=1.0, lower_bound=0.0, upper_bound=2.0)


def test_physical_bounds_must_be_finite_ordered_and_contain_nominal() -> None:
    with pytest.raises(ValueError, match="strictly inside bounds"):
        CandidateParameter("bad", nominal=0.0, lower_bound=0.0, upper_bound=1.0)
    with pytest.raises(ValueError, match="finite"):
        CandidateParameter("bad", nominal=float("inf"), lower_bound=0.0, upper_bound=1.0)


def test_influence_is_measured_for_every_parameter_output_pair() -> None:
    result = run_local_sensitivity_analysis(
        lambda values: {
            "first": [values["a"], 2.0 * values["a"]],
            "second": [values["b"], -values["b"]],
        },
        parameters=[_parameter("a"), _parameter("b")],
        targets=[TargetOutput("first", 1.0, "x"), TargetOutput("second", 1.0, "x")],
    )
    assert {(item.parameter, item.output) for item in result.influences} == {
        ("a", "first"),
        ("a", "second"),
        ("b", "first"),
        ("b", "second"),
    }
    assert result.identifiable is True
    require_identifiable(result)


def test_insensitive_parameter_is_frozen_and_problem_is_rejected() -> None:
    result = run_local_sensitivity_analysis(
        lambda values: {"signal": [values["active"], 2.0 * values["active"]]},
        parameters=[_parameter("active"), _parameter("unused")],
        targets=[TargetOutput("signal", 1.0, "x")],
    )
    assert result.frozen_parameters == ("unused",)
    assert result.identifiable is False
    with pytest.raises(ValueError, match="not identifiable"):
        require_identifiable(result)


def test_collinear_parameter_fingerprints_are_rejected() -> None:
    result = run_local_sensitivity_analysis(
        lambda values: {
            "signal": [
                values["first"] + values["second"],
                2.0 * (values["first"] + values["second"]),
            ]
        },
        parameters=[_parameter("first"), _parameter("second")],
        targets=[TargetOutput("signal", 1.0, "x")],
    )
    assert result.effective_rank == 1
    assert len(result.correlated_pairs) == 1
    assert result.identifiable is False


def test_analysis_is_deterministic() -> None:
    kwargs = {
        "simulator": lambda values: {"signal": [values["a"], values["b"]]},
        "parameters": [_parameter("a"), _parameter("b")],
        "targets": [TargetOutput("signal", 1.0, "x")],
    }
    first = run_local_sensitivity_analysis(**kwargs)
    second = run_local_sensitivity_analysis(**kwargs)
    assert first.to_dict() == second.to_dict()
