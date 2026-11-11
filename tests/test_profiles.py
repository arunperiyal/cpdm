import os
import sys
import json

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cpdm.core import contracts, profiles  # noqa: E402


def test_profile_spec_round_trips_and_validates_metadata():
    spec = profiles.ProfileAnalysisSpec(
        name="wellbeing_profiles",
        indicators=(
            profiles.IndicatorDefinition("stress", "stress_score", standardize=True),
            profiles.IndicatorDefinition(
                "employment", "employment", measurement_level="categorical",
                allowed_values=("employed", "unemployed"),
            ),
        ),
        class_counts=(2, 3),
        identifier_columns=("participant_id",),
        covariates=("age",),
        weights="survey_weight",
    )
    restored = profiles.ProfileAnalysisSpec.from_dict(spec.as_dict())

    assert restored == spec
    frame = pd.DataFrame({
        "participant_id": ["1", "2"],
        "stress_score": [1.0, 2.0],
        "employment": ["employed", "unemployed"],
        "age": [30, 40],
        "survey_weight": [1.0, 1.2],
    })
    assert spec.validate_frame(frame) is spec


def test_profile_spec_rejects_identifier_leakage_and_unknown_values():
    with pytest.raises(contracts.ContractError, match="cannot also be indicators"):
        profiles.ProfileAnalysisSpec(
            "bad",
            indicators=(profiles.IndicatorDefinition("id", "participant_id"),),
            identifier_columns=("participant_id",),
        )

    definition = profiles.IndicatorDefinition(
        "group", "group", measurement_level="categorical",
        allowed_values=("a", "b"),
    )
    with pytest.raises(contracts.ContractError, match="outside its allowed set"):
        definition.validate_frame(pd.DataFrame({"group": ["a", "c"]}))


def test_continuous_indicator_rejects_non_numeric_values():
    definition = profiles.IndicatorDefinition("score", "score")
    with pytest.raises(contracts.ContractError, match="non-numeric"):
        definition.validate_frame(pd.DataFrame({"score": ["1", "not-a-number"]}))


def test_profile_solution_and_fit_reports_validate_and_serialize():
    solution = profiles.ProfileSolution(
        class_count=2,
        class_labels=("class_1", "class_2"),
        parameters={"means": {"class_1": [1.0], "class_2": [3.0]}},
        assignments=("class_1", "class_2", "class_1"),
        posterior_probabilities=(
            (0.9, 0.1), (0.2, 0.8), (0.7, 0.3)
        ),
        class_sizes={"class_1": 2, "class_2": 1},
        profile_labels={"class_1": "Lower", "class_2": "Higher"},
    )
    statistic = profiles.FitStatistic(
        class_count=2, log_likelihood=-10, parameter_count=4,
        aic=28, bic=35, entropy=0.82,
    )
    report = profiles.ClassSelectionReport(
        "wellbeing_profiles", (statistic,), selected_class_count=2,
        decision="retain two profiles", review_notes="Stable and interpretable.",
    )

    assert solution.as_dict()["class_sizes"] == {"class_1": 2, "class_2": 1}
    assert report.as_dict()["fit_statistics"][0]["bic"] == 35


def test_profile_solution_rejects_invalid_posteriors_and_selection():
    with pytest.raises(contracts.ContractError, match="sum to 1"):
        profiles.ProfileSolution(
            2, ("a", "b"), {}, ("a",), ((0.8, 0.8),), {"a": 1, "b": 0}
        )
    statistic = profiles.FitStatistic(2, -1, 2, 6, 8)
    with pytest.raises(contracts.ContractError, match="not in"):
        profiles.ClassSelectionReport("analysis", (statistic,), selected_class_count=3)


def test_profile_stability_report_records_repeated_starts_and_resampling():
    report = profiles.ProfileStabilityReport(
        class_count=3,
        repeated_start_count=20,
        agreement_rate=0.95,
        resample_count=100,
        resample_agreement_rate=0.88,
        label_alignment={"run_2": {"1": "2", "2": "1"}},
        sensitivity={"standardized": {"selected_class_count": 3}},
        warnings=("One small class needs review.",),
    )

    payload = report.as_dict()
    assert payload["repeated_start_count"] == 20
    assert payload["label_alignment"]["run_2"]["1"] == "2"
    assert payload["warnings"] == ["One small class needs review."]


def test_profile_stability_report_rejects_invalid_agreement():
    with pytest.raises(contracts.ContractError, match="between 0 and 1"):
        profiles.ProfileStabilityReport(2, 10, 1.2)


def test_mixture_runner_validates_adapter_contract_and_writes_results(tmp_path):
    spec = profiles.ProfileAnalysisSpec(
        "profiles",
        indicators=(profiles.IndicatorDefinition("score", "score"),),
        estimator="fake",
        identifier_columns=("participant_id",),
    )
    solution = profiles.ProfileSolution(
        2, ("low", "high"), {"means": {}}, ("low", "high"),
        ((0.8, 0.2), (0.1, 0.9)), {"low": 1, "high": 1},
    )
    fit = profiles.FitStatistic(2, -2, 3, 10, 12)
    expected = profiles.ProfileAnalysisResult(spec, solution, fit)
    runner = profiles.MixtureAnalysisRunner({
        "fake": lambda frame, received: expected,
    })
    frame = pd.DataFrame({"participant_id": ["a", "b"], "score": [1.0, 3.0]})

    result = runner.run(frame, spec)
    json_path = tmp_path / "profile.json"
    csv_path = tmp_path / "assignments.csv"
    xlsx_path = tmp_path / "profile.xlsx"
    profiles.ProfileResultWriter.write_json(result, json_path)
    profiles.ProfileResultWriter.write_csv(result, csv_path)
    profiles.ProfileResultWriter.write_xlsx(result, xlsx_path)

    assert result.metadata["input_fingerprint"]
    assert result.metadata["seed"] == 0
    assert json.loads(json_path.read_text())["kind"] == "cpdm-profile-analysis-result"
    assert list(pd.read_csv(csv_path)["assigned_class"]) == ["low", "high"]
    assert xlsx_path.exists()


def test_profile_diagnostics_alignment_and_distal_outcome_boundary():
    spec = profiles.ProfileAnalysisSpec(
        "profiles",
        indicators=(profiles.IndicatorDefinition("score", "score"),),
        covariates=("age",),
        distal_outcomes=("later_score",),
    )
    spec.validate_frame(pd.DataFrame({
        "score": [1.0, 2.0], "age": [20, 21], "later_score": [2.0, 3.0],
    }))
    solution = profiles.ProfileSolution(
        2, ("low", "high"), {}, ("low", "high", "low", "high"),
        ((1, 0), (0, 1), (1, 0), (0, 1)), {"low": 2, "high": 2},
    )
    assert solution.diagnostics()["warnings"] == ["Tiny classes below 5: {'low': 2, 'high': 2}"]
    reversed_solution = profiles.ProfileSolution(
        2, ("a", "b"), {}, ("a", "b", "a", "b"),
        ((1, 0), (0, 1), (1, 0), (0, 1)), {"a": 2, "b": 2},
    )
    alignment = profiles.align_profile_labels(solution, reversed_solution)
    assert alignment["agreement_rate"] == 1


def test_mixture_runner_rejects_unknown_backend():
    spec = profiles.ProfileAnalysisSpec(
        "profiles",
        indicators=(profiles.IndicatorDefinition("score", "score"),),
        estimator="missing_backend",
    )
    with pytest.raises(contracts.ContractError, match="No mixture-analysis adapter"):
        profiles.MixtureAnalysisRunner().run(pd.DataFrame({"score": [1.0]}), spec)


def test_python_mixture_backend_is_reproducible_and_selects_class_count():
    pytest.importorskip("sklearn")
    frame = pd.DataFrame({
        "score_1": [0.0, 0.1, -0.1, 5.0, 5.1, 4.9],
        "score_2": [0.1, 0.0, -0.2, 5.1, 4.9, 5.0],
    })
    spec = profiles.ProfileAnalysisSpec(
        "profiles",
        indicators=(
            profiles.IndicatorDefinition("score_1", "score_1"),
            profiles.IndicatorDefinition("score_2", "score_2"),
        ),
        class_counts=(2, 3),
        starts=3,
        seed=17,
    )
    runner = profiles.MixtureAnalysisRunner()
    first = runner.run(frame, spec)
    second = runner.run(frame, spec)

    assert first.solution.as_dict() == second.solution.as_dict()
    assert first.fit_statistic.class_count in {2, 3}
    assert first.metadata["seed"] == 17
    assert first.stability.repeated_start_count == 3


def test_profile_class_count_comparison_keeps_substantive_review():
    indicator = profiles.IndicatorDefinition("score", "score")
    spec = profiles.ProfileAnalysisSpec("profiles", indicators=(indicator,))
    solution = profiles.ProfileSolution(
        2, ("a", "b"), {}, ("a", "b"), ((1, 0), (0, 1)), {"a": 1, "b": 1}
    )
    results = (
        profiles.ProfileAnalysisResult(
            spec, solution, profiles.FitStatistic(2, -1, 2, 6, 8),
            warnings=("Review tiny classes.",),
        ),
        profiles.ProfileAnalysisResult(
            spec,
            profiles.ProfileSolution(
                3, ("a", "b", "c"), {},
                ("a", "b", "c"), ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                {"a": 1, "b": 1, "c": 1},
            ),
            profiles.FitStatistic(3, -1, 3, 7, 7),
        ),
    )
    report = profiles.compare_class_counts(
        results,
        substantive_review={
            "selected_class_count": 2,
            "decision": "retain two",
            "notes": "Theory wins.",
        },
    )
    assert report.selected_class_count == 2
    assert report.decision == "retain two"
    assert report.review_notes == "Theory wins."
    assert "Review tiny classes." in report.warnings


def test_profile_dependency_diagnostics_explain_optional_boundaries():
    diagnostics = profiles.dependency_diagnostics()
    assert "python_gaussian_mixture" in diagnostics
    assert diagnostics["r_backend"]["available"] is False
    assert diagnostics["r_backend"]["message"]
    with pytest.raises(contracts.ContractError, match="R mixture backend"):
        profiles.r_mixture_adapter(pd.DataFrame(), None)


def test_indicator_preparation_applies_imputation_transformation_and_standardization():
    spec = profiles.ProfileAnalysisSpec(
        "prepared",
        indicators=(
            profiles.IndicatorDefinition(
                "score", "raw_score", transform="zscore",
                standardize=True, missing_policy="impute",
            ),
            profiles.IndicatorDefinition(
                "group", "raw_group", measurement_level="categorical",
                allowed_values=("a", "b"), missing_policy="impute",
            ),
        ),
    )
    prepared = spec.prepare_indicators(pd.DataFrame({
        "raw_score": [1.0, None, 3.0],
        "raw_group": ["a", None, "b"],
    }))

    assert list(prepared.columns) == ["score", "group"]
    assert prepared["score"].isna().sum() == 0
    assert prepared["group"].tolist() == ["a", "a", "b"]
    assert round(prepared["score"].mean(), 8) == 0


def test_indicator_preparation_rejects_missing_values_under_error_policy():
    definition = profiles.IndicatorDefinition("score", "score", missing_policy="error")
    with pytest.raises(contracts.ContractError, match="missing values"):
        definition.prepare(pd.Series([1.0, None]))
