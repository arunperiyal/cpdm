import json
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cpdm.core import analysis, contracts  # noqa: E402


def apim_frame():
    return pd.DataFrame({
        "x_h": [1, 2, 3, 4, 5, 6],
        "x_w": [2, 1, 4, 3, 6, 5],
        "y_h": [3, 4, 7, 8, 11, 12],
        "y_w": [5, 4, 9, 8, 13, 12],
    })


def test_analysis_spec_round_trips_and_validates():
    spec = analysis.AnalysisSpec.from_dict({
        "name": "basic apim",
        "predictors": ["x"],
        "outcomes": ["y"],
        "roles": ["h", "w"],
        "exploratory": True,
    })
    assert analysis.AnalysisSpec.from_dict(spec.as_dict()) == spec
    with pytest.raises(contracts.ContractError, match="missing-data"):
        analysis.AnalysisSpec("bad", predictors=("x",), outcomes=("y",),
                              missing_data="drop_silently")


def test_apim_runner_returns_explicit_actor_and_partner_effects():
    spec = analysis.AnalysisSpec(
        "basic apim", predictors=("x",), outcomes=("y",), roles=("h", "w")
    )
    result = analysis.AnalysisRunner().run(apim_frame(), spec)

    assert result.convergence_status == "converged"
    assert [item.path for item in result.estimates] == [
        "actor:x->y", "partner:x->y", "actor:x->y", "partner:x->y"
    ]
    assert {item.role for item in result.estimates} == {"h", "w"}
    assert result.input_fingerprint


def test_analysis_registry_exposes_capabilities():
    runner = analysis.AnalysisRunner()
    capability = runner.registry.capabilities()[0]
    assert capability.name == "apim_ols"
    assert "predictors" in capability.required_roles
    capability.validate(
        analysis.AnalysisSpec(
            "basic apim", predictors=("x",), outcomes=("y",)
        )
    )


def test_summary_comparison_repeated_measures_and_regression_adapters():
    frame = pd.DataFrame({
        "subject": ["a", "a", "b", "b"],
        "time": [1, 2, 1, 2],
        "group": ["x", "x", "y", "y"],
        "predictor": [1, 2, 2, 4],
        "outcome": [2, 4, 4, 8],
    })
    summary = analysis.descriptive_summary(frame, ["outcome"], group_by="group")
    assert summary["n"].tolist() == [2, 2]
    comparison = analysis.compare_groups(frame, "outcome", "group")
    assert comparison["mean_difference"] == -3.0
    repeated = analysis.repeated_measures_summary(frame, "subject", "time", "outcome")
    assert repeated["time"].tolist() == [1, 2]
    result = analysis.AnalysisRunner().run(
        frame,
        analysis.AnalysisSpec(
            "regression", predictors=("predictor",), outcomes=("outcome",),
            estimator="linear_regression",
        ),
    )
    assert result.estimates[0].estimate == pytest.approx(2.0)


def test_report_writers_have_stable_table_and_json(tmp_path):
    spec = analysis.AnalysisSpec(
        "basic apim", predictors=("x",), outcomes=("y",), roles=("h", "w")
    )
    result = analysis.AnalysisRunner().run(apim_frame(), spec)
    json_path = tmp_path / "result.json"
    csv_path = tmp_path / "result.csv"
    xlsx_path = tmp_path / "result.xlsx"

    analysis.ReportWriter.write_json(result, json_path)
    analysis.ReportWriter.write_csv(result, csv_path)
    analysis.ReportWriter.write_xlsx(result, xlsx_path)

    payload = json.loads(json_path.read_text())
    assert payload["kind"] == "cpdm-analysis-result"
    assert list(pd.read_csv(csv_path).columns) == list(analysis.ReportWriter.COLUMNS)
    assert xlsx_path.exists()
