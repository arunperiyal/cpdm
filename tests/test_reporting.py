import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cpdm.core import analysis, reporting  # noqa: E402


def test_report_bundle_contains_inputs_results_and_figure_data(tmp_path):
    frame = pd.DataFrame({
        "x_h": [1, 2, 3, 4], "x_w": [2, 1, 4, 3],
        "y_h": [3, 4, 7, 8], "y_w": [5, 4, 9, 8],
    })
    spec = analysis.AnalysisSpec(
        "bundle", predictors=("x",), outcomes=("y",), roles=("h", "w")
    )
    result = analysis.AnalysisRunner().run(frame, spec)
    figure = reporting.FigureSpec(
        "effects", "forest", ("path", "estimate"), title="Effects"
    )
    bundle = reporting.ReportBundle(tmp_path / "bundle").write(
        definitions={"analysis": spec.as_dict()},
        preparation_manifest={"source_fingerprint": result.input_fingerprint},
        analysis_result=result,
        figures=(figure,),
        figure_data={"effects": analysis.ReportWriter.table(result)},
    )

    assert (bundle / "bundle.json").exists()
    assert (bundle / "analysis.json").exists()
    assert (bundle / "effects.csv").exists()


def test_compare_result_tables_joins_by_path_and_role():
    left = pd.DataFrame([
        {"path": "actor:x->y", "role": "h", "estimate": 1.0},
    ])
    right = pd.DataFrame([
        {"path": "actor:x->y", "role": "h", "estimate": 1.5},
    ])
    compared = reporting.compare_result_tables(left, right)
    assert compared.loc[0, "estimate_difference"] == 0.5


def test_privacy_policy_filters_report_figure_data(tmp_path):
    frame = pd.DataFrame({"participant_id": ["1"], "comment": ["secret"], "value": [2]})
    policy = reporting.PrivacyPolicy(
        drop_columns=("participant_id",), redact_columns=("comment",)
    )
    bundle = reporting.ReportBundle(tmp_path / "private").write(
        figure_data={"rows": frame}, privacy_policy=policy
    )
    exported = pd.read_csv(bundle / "rows.csv")
    assert "participant_id" not in exported
    assert exported.loc[0, "comment"] == "[REDACTED]"
