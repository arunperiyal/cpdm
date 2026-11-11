import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cpdm.core import measurement, reliability, scoring
from cpdm.core import contracts


def test_scale_map_scores_reverse_items_and_composites():
    scale_map = measurement.ScaleMap.from_dataframe(pd.DataFrame([
        {
            "scale": "Example",
            "dimension_code": "EX_SUB",
            "dimension_label": "Example subscale",
            "item_number": 1,
            "column_name": "Q1",
            "reverse": False,
            "item_min": 1,
            "item_max": 5,
            "is_total": False,
        },
        {
            "scale": "Example",
            "dimension_code": "EX_SUB",
            "dimension_label": "Example subscale",
            "item_number": 2,
            "column_name": "Q2",
            "reverse": True,
            "item_min": 1,
            "item_max": 5,
            "is_total": False,
        },
        {
            "scale": "Example",
            "dimension_code": "EX_TOTAL",
            "dimension_label": "Example total",
            "item_number": 1,
            "column_name": "Q1",
            "reverse": False,
            "item_min": 1,
            "item_max": 5,
            "is_total": True,
        },
        {
            "scale": "Example",
            "dimension_code": "EX_TOTAL",
            "dimension_label": "Example total",
            "item_number": 2,
            "column_name": "Q2",
            "reverse": True,
            "item_min": 1,
            "item_max": 5,
            "is_total": True,
        },
    ]))
    frame = pd.DataFrame({"Q1": [1, 2, None], "Q2": [1, 2, 3]})

    scored, report = scoring.ScoringEngine().score(frame, scale_map, "Example")

    assert list(scored["Q2"]) == [5, 4, 3]
    assert list(scored["EX_SUB"]) == [6, 6, 3]
    assert list(scored["EX_TOTAL"]) == [6, 6, 3]
    assert report.reversed_items == ["Q2"]
    assert report.composites == ["EX_SUB", "EX_TOTAL"]
    assert list(frame["Q2"]) == [1, 2, 3]


def test_scale_map_round_trips_json_and_reports_reliability():
    frame = pd.DataFrame([
        {
            "scale": "Example",
            "dimension_code": "EX",
            "dimension_label": "Example",
            "item_number": 1,
            "column_name": "Q1",
            "reverse": False,
            "item_min": 1,
            "item_max": 5,
            "is_total": False,
        },
        {
            "scale": "Example",
            "dimension_code": "EX",
            "dimension_label": "Example",
            "item_number": 2,
            "column_name": "Q2",
            "reverse": False,
            "item_min": 1,
            "item_max": 5,
            "is_total": False,
        },
    ])
    scale_map = measurement.ScaleMap.from_dataframe(frame)
    restored = measurement.ScaleMap.from_json(scale_map.to_json())
    reports = reliability.reliability_report(
        pd.DataFrame({"Q1": [1, 2, 3], "Q2": [1, 2, 3]}),
        restored,
    )

    assert restored.to_dataframe().equals(scale_map.to_dataframe())
    assert reports[0].alpha == pytest.approx(1.0)
    assert reports[0].omega is None
    assert "omega is not implemented" in reports[0].warnings[0]


def test_scale_map_rejects_missing_source_columns():
    scale_map = measurement.ScaleMap.from_dataframe(pd.DataFrame([{
        "scale": "Example",
        "dimension_code": "EX",
        "dimension_label": "Example",
        "item_number": 1,
        "column_name": "Missing",
        "reverse": False,
        "item_min": 1,
        "item_max": 5,
        "is_total": False,
    }]))

    with pytest.raises(contracts.ContractError, match="not found"):
        scoring.ScoringEngine().score(pd.DataFrame({"Other": [1]}), scale_map)
