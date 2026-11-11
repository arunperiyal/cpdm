import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cpdm.core import contracts, pipeline  # noqa: E402


def test_pipeline_runs_steps_without_mutating_source():
    source = pd.DataFrame({
        "Name / പേര്": ["A", "B"],
        "Answer": ["Strongly Agree", "Agree"],
        "Q1": [1, 2],
        "Q2": [2, 3],
    })
    definition = {
        "version": 1,
        "steps": [
            {"op": "validate"},
            {"op": "rename_headers", "map": {"Name / പേര്": "Name"}},
            {"op": "replace_values", "map": {"Strongly Agree": "5", "Agree": "4"}},
            {
                "op": "compute",
                "new_col_name": "Mean",
                "function": "mean",
                "columns": ["Q1", "Q2"],
            },
        ],
    }

    result = pipeline.PreparationPipeline(definition).run(
        source, source_filename="wave1.csv"
    )

    assert list(result.frame["Name"]) == ["A", "B"]
    assert list(result.frame["Answer"]) == ["5", "4"]
    assert list(result.frame["Mean"]) == [1.5, 2.5]
    assert result.manifest["source_filename"] == "wave1.csv"
    assert result.manifest["source_fingerprint"] != result.manifest["output_fingerprint"]
    assert result.manifest["steps"][1]["details"]["columns_changed"] == 1
    assert source.columns.tolist() == ["Name / പേര്", "Answer", "Q1", "Q2"]


def test_pipeline_dry_run_returns_manifest_without_external_mutation():
    source = pd.DataFrame({"Answer": ["Agree"]})
    definition = {
        "steps": [{"op": "replace_values", "map": {"Agree": "4"}}]
    }

    result = pipeline.PreparationPipeline(definition).run(source, dry_run=True)

    assert result.dry_run is True
    assert result.manifest["dry_run"] is True
    assert result.frame["Answer"].tolist() == ["4"]
    assert source["Answer"].tolist() == ["Agree"]


def test_pipeline_rejects_unknown_columns_before_running():
    with pytest.raises(contracts.ContractError, match="unknown columns"):
        pipeline.PreparationPipeline({
            "steps": [{"op": "rename_headers", "map": {"Missing": "New"}}]
        }).run(pd.DataFrame({"Answer": ["Agree"]}))


def test_pipeline_score_requires_explicit_scale_map_context():
    with pytest.raises(contracts.ContractError, match="ScaleMap"):
        pipeline.PreparationPipeline({"steps": [{"op": "score"}]}).run(
            pd.DataFrame({"Q1": [1]})
        )
