import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cpdm.core import analysis, contracts  # noqa: E402


COMPATIBLE_ANALYSIS_SPEC = {
    "version": 1,
    "name": "legacy regression",
    "predictors": ["x"],
    "outcomes": ["y"],
    "estimator": "linear_regression",
}


def test_saved_analysis_spec_fixture_remains_compatible():
    spec = analysis.AnalysisSpec.from_dict(COMPATIBLE_ANALYSIS_SPEC)
    assert spec.as_dict()["version"] == 1
    assert spec.estimator == "linear_regression"


def test_incompatible_saved_analysis_spec_is_rejected():
    with pytest.raises(contracts.ContractError, match="predictor"):
        analysis.AnalysisSpec.from_dict({
            "version": 1, "name": "broken", "outcomes": ["y"],
        })
