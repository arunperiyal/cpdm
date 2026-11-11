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
