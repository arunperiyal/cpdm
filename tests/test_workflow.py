"""End-to-end checks over the HTTP API, driven with the bundled samples.

    python -m pytest tests            (or: python tests/test_workflow.py)
"""

import io
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cpdm import create_app  # noqa: E402
from cpdm.core import state  # noqa: E402
from cpdm.core.markdown_lite import _fallback_render  # noqa: E402
from cpdm.paths import PROJECT_ROOT  # noqa: E402

SAMPLES = os.path.join(PROJECT_ROOT, "samples")


def fresh_client():
    state.reset()
    app = create_app(TESTING=True)
    return app.test_client()


def upload(client, filename):
    with open(os.path.join(SAMPLES, filename), "rb") as handle:
        data = {"file": (io.BytesIO(handle.read()), filename)}
    return client.post("/api/upload", data=data, content_type="multipart/form-data")


def apply_recipe(client):
    with open(os.path.join(SAMPLES, "sample_cleaning_rules.json"), "rb") as handle:
        data = {"file": (io.BytesIO(handle.read()), "sample_cleaning_rules.json")}
    return client.post(
        "/api/apply_cleaning_rules_file", data=data, content_type="multipart/form-data"
    )


def test_full_survey_workflow():
    client = fresh_client()

    loaded = upload(client, "sample_survey.xlsx").get_json()
    assert loaded["rows"] == 30
    assert len(loaded["cols"]) == 17

    # the saved recipe renames headers and turns Likert text into numbers
    result = apply_recipe(client).get_json()["result"]
    assert "WB1" in result["cols"]
    assert "Comments" in result["cols"]

    scored = state.session.df["WB1"].astype(str).unique()
    assert set(scored) <= {"1", "2", "3", "4", "5", ""}, scored
    # ignored columns keep their original free text
    assert state.session.df["Comments"].astype(str).str.contains("survey").any()

    # scales -> categorise -> score -> compute
    assert client.post("/api/create_scale", json={"scale_name": "Wellbeing"}).status_code == 200
    categories = {col: "Uncategorised" for col in state.session.df.columns}
    for col in ["WB1", "WB2", "WB3", "WB4", "WB5"]:
        categories[col] = "Scale: Wellbeing"
    categories["Age"] = "Demographics"
    client.post("/api/categorise", json={"categories": categories})

    client.post(
        "/api/scoring",
        json={"configs": {"WB3": {"type": "Reverse", "scale_max": 5},
                          "WB5": {"type": "Reverse", "scale_max": 5}}},
    )
    assert pd.api.types.is_numeric_dtype(state.session.df["WB3"])

    computed = client.post(
        "/api/compute",
        json={
            "new_col_name": "Wellbeing_Mean",
            "function_name": "mean",
            "selected_cols": ["WB1", "WB2", "WB3", "WB4", "WB5"],
        },
    ).get_json()
    assert computed["new_col"] == "Wellbeing_Mean"
    means = state.session.df["Wellbeing_Mean"].dropna()
    assert means.between(1, 5).all()

    # export round-trip
    export = client.get("/api/export")
    assert export.status_code == 200
    round_trip = pd.read_excel(io.BytesIO(export.data))
    assert "Wellbeing_Mean" in round_trip.columns

    csv_export = client.get("/api/export?format=csv")
    assert csv_export.status_code == 200
    assert "Wellbeing_Mean" in csv_export.data.decode("utf-8-sig").splitlines()[0]


def test_csv_upload_and_recipe_replay():
    client = fresh_client()
    loaded = upload(client, "sample_survey_wave2.csv").get_json()
    assert loaded["rows"] == 12

    apply_recipe(client)
    assert "DS4" in state.session.df.columns
    assert set(state.session.df["Gender"].unique()) <= {"Male", "Female"}


def test_longest_replacement_wins():
    client = fresh_client()
    upload(client, "sample_survey.csv")
    client.post(
        "/api/clean_values",
        json={"replacements": {"Agree / യോജിക്കുന്നു": "4",
                               "Strongly Agree / പൂർണ്ണമായും യോജിക്കുന്നു": "5"}},
    )
    values = set(state.session.df.iloc[:, 7].astype(str))
    assert "Strongly 4" not in values


def test_text_trimming_and_exemptions():
    client = fresh_client()
    upload(client, "sample_survey.csv")

    response = client.post(
        "/api/remove_non_english_advanced",
        json={
            "header_cfg": {"mode": "delimiter_to_end", "delimiter": "/"},
            "value_cfg": {"mode": "delimiter_to_end", "delimiter": "/"},
            "exempt_cols": ["Any other comments? / മറ്റ് അഭിപ്രായങ്ങൾ"],
        },
    ).get_json()

    assert response["result"]["headers_changed"] > 0
    assert "Name" in state.session.df.columns
    assert "Any other comments? / മറ്റ് അഭിപ്രായങ്ങൾ" in state.session.df.columns


def test_ignored_column_survives_rename():
    client = fresh_client()
    upload(client, "sample_survey.csv")

    raw_name = "Name / പേര്"
    client.post(
        "/api/clean_headers",
        json={"header_map": {raw_name: "Name"}, "ignored_cols": [raw_name]},
    )
    assert state.session.state()["ignored_columns"] == ["Name"]

    client.post("/api/clean_values", json={"replacements": {"Anitha Raj": "REDACTED"}})
    assert "REDACTED" not in set(state.session.df["Name"])


def test_console_commands():
    client = fresh_client()
    assert "Available Commands" in client.post("/api/command", json={"command": "help"}).get_json()["output"]
    assert client.post("/api/command", json={"command": "show"}).get_json()["error"]

    upload(client, "sample_survey.csv")
    assert "<table" in client.post("/api/command", json={"command": "show"}).get_json()["html"]
    assert "Dimensions" in client.post("/api/command", json={"command": "info"}).get_json()["output"]
    assert client.post("/api/command", json={"command": "clear"}).get_json()["clear"] is True
    assert "docs" in client.post("/api/command", json={"command": "docs"}).get_json()["html"].lower()


def test_docs_and_samples_are_served():
    client = fresh_client()

    listing = client.get("/api/docs").get_json()
    slugs = {(s["key"], d["slug"]) for s in listing["sections"] for d in s["docs"]}
    assert ("help", "getting-started") in slugs
    assert any(item["name"] == "sample_survey.xlsx" for item in listing["samples"])

    page = client.get("/docs/help/getting-started")
    assert page.status_code == 200
    assert b"CPDM Documentation" in page.data

    assert client.get("/docs/help/does-not-exist").status_code == 404
    assert client.get("/samples/sample_survey.csv").status_code == 200
    assert client.get("/samples/../app.py").status_code in (301, 308, 404)

    workspace = client.get("/")
    assert workspace.status_code == 200
    assert b"Documentation Browser" in workspace.data


def test_markdown_fallback_renderer():
    html = _fallback_render(
        "# Title\n\nSome **bold** and `code`.\n\n"
        "| A | B |\n| - | - |\n| 1 | 2 |\n\n"
        "- one\n- two\n\n```python\nprint('hi')\n```\n"
    )
    assert '<h1 id="title">Title</h1>' in html
    assert "<strong>bold</strong>" in html and "<code>code</code>" in html
    assert "<th>A</th>" in html and "<td>2</td>" in html
    assert "<ul>" in html and "<li>one</li>" in html
    assert "<pre><code" in html and "print(&#x27;hi&#x27;)" in html
    assert "<script>" not in _fallback_render("<script>alert(1)</script>")


if __name__ == "__main__":
    failures = 0
    for name, func in sorted(list(globals().items())):
        if name.startswith("test_") and callable(func):
            try:
                func()
                print(f"PASS {name}")
            except Exception as exc:
                failures += 1
                print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    raise SystemExit(1 if failures else 0)
