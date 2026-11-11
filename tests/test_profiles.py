import os
import sys

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
