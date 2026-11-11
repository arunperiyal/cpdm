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


def test_weighted_clustered_longitudinal_and_bootstrap_adapters():
    frame = pd.DataFrame({
        "subject": ["a", "a", "b", "b", "c", "c"],
        "time": [1, 2, 1, 2, 1, 2],
        "cluster": ["x", "x", "y", "y", "z", "z"],
        "weight": [1, 2, 1, 2, 1, 2],
        "x": [1, 2, 2, 4, 3, 6],
        "m": [2, 3, 4, 6, 6, 9],
        "y": [3, 4, 6, 9, 9, 13],
    })
    runner = analysis.AnalysisRunner()
    weighted = runner.run(
        frame,
        analysis.AnalysisSpec(
            "weighted", predictors=("x",), outcomes=("y",),
            estimator="weighted_regression", weights="weight",
        ),
    )
    clustered = runner.run(
        frame,
        analysis.AnalysisSpec(
            "clustered", predictors=("x",), outcomes=("y",),
            estimator="clustered_regression", cluster="cluster",
        ),
    )
    longitudinal = runner.run(
        frame,
        analysis.AnalysisSpec(
            "longitudinal", predictors=("x",), outcomes=("y",),
            estimator="longitudinal_regression", subject="subject", time="time",
        ),
    )
    repeated = runner.run(
        frame,
        analysis.AnalysisSpec(
            "repeated", predictors=("x",), outcomes=("y",),
            estimator="repeated_measures_regression", subject="subject", time="time",
        ),
    )
    indirect = runner.run(
        frame,
        analysis.AnalysisSpec(
            "indirect", predictors=("x",), mediators=("m",), outcomes=("y",),
            estimator="bootstrap_indirect", exploratory=True, roles=("bootstrap",),
            seed=42,
        ),
    )
    assert weighted.estimates[0].role == "weighted_regression"
    assert clustered.estimates[0].diagnostics["cluster_count"] == 3
    assert longitudinal.estimates[0].diagnostics["subject"] == "subject"
    assert repeated.estimates[0].role == "repeated_measures_regression"
    assert indirect.estimates[0].confidence_interval is not None
    assert indirect.as_dict()["spec"]["seed"] == 42
    assert indirect.input_fingerprint
    assert indirect.warnings


def test_backend_capabilities_are_discoverable():
    names = {item["name"] for item in analysis.AnalysisRunner().capability_metadata()}
    assert {
        "weighted_regression",
        "clustered_regression",
        "longitudinal_regression",
        "repeated_measures_regression",
    } <= names


def test_backend_contracts_report_actionable_errors():
    frame = pd.DataFrame({"x": [1, 2], "y": [2, 4]})
    runner = analysis.AnalysisRunner()
    with pytest.raises(contracts.ContractError, match="weights"):
        runner.run(
            frame,
            analysis.AnalysisSpec(
                "weighted", predictors=("x",), outcomes=("y",),
                estimator="weighted_regression",
            ),
        )
    with pytest.raises(contracts.ContractError, match="subject, time"):
        runner.run(
            frame,
            analysis.AnalysisSpec(
                "longitudinal", predictors=("x",), outcomes=("y",),
                estimator="longitudinal_regression",
            ),
        )
    with pytest.raises(contracts.ContractError, match="missing-data"):
        runner.run(
            frame,
            analysis.AnalysisSpec(
                "indirect", predictors=("x",), mediators=("x",), outcomes=("y",),
                estimator="bootstrap_indirect", missing_data="pairwise",
            ),
        )


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
