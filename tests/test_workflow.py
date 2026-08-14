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
from cpdm.core import state, text_rules  # noqa: E402
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


def test_text_rule_chain_applies_in_order():
    client = fresh_client()
    upload(client, "sample_survey.csv")

    result = client.post(
        "/api/text_rules/apply",
        json={
            "stage": "headers",
            "rules": [
                {"mode": "delimiter", "delimiters": ["/", "("], "keep": "before"},
                {"mode": "tidy"},
            ],
        },
    ).get_json()["result"]

    # every header but Timestamp carries a ' / <translation>' tail
    assert result["headers_changed"] == 16
    assert "Name" in state.session.df.columns
    assert "Do you use social media daily?" in state.session.df.columns
    assert "Timestamp" in state.session.df.columns
    assert "Cut at '/' '('" in result["description"]


def test_delimiter_keep_after_and_script_awareness():
    chain = [{"mode": "delimiter", "delimiters": ["/"], "keep": "after"}]
    rules = text_rules.normalise_chain(chain)
    assert text_rules.apply_chain("പേര് / Name", rules) == "Name"

    keep_accents = text_rules.normalise_chain([{"mode": "strip_non_english"}])
    assert text_rules.apply_chain("café ₹500 — naïve", keep_accents) == "café ₹500 — naïve"
    assert text_rules.apply_chain("café വാട്സ്", keep_accents) == "café"

    strict = text_rules.normalise_chain([{"mode": "strip_non_english", "strict_ascii": True}])
    assert text_rules.apply_chain("café ₹500", strict) == "caf 500"


def test_tidy_clears_the_debris_a_cut_leaves():
    rules = text_rules.normalise_chain(
        [{"mode": "non_english_to_end"}, {"mode": "tidy"}]
    )
    assert text_rules.apply_chain("WhatsApp (വാട്സാപ്പ്)", rules) == "WhatsApp"
    assert text_rules.apply_chain("Age - വയസ്സ്", rules) == "Age"
    assert text_rules.apply_chain("Q1. Are you well?", rules) == "Q1. Are you well?"


def test_preview_matches_apply_and_never_mutates():
    client = fresh_client()
    upload(client, "sample_survey.csv")

    before_state = client.get("/api/get_state").get_json()
    body = {
        "stage": "headers",
        "rules": [{"mode": "delimiter", "delimiters": ["/"], "keep": "before"},
                  {"mode": "tidy"}],
    }

    preview = client.post("/api/text_rules/preview", json=body).get_json()
    assert preview["columns_affected"] == 16
    assert client.get("/api/get_state").get_json() == before_state  # untouched

    client.post("/api/text_rules/apply", json=body)
    after = list(state.session.df.columns)
    assert [row["after"] for row in preview["rows"]] == after


def test_preview_warns_about_collisions_and_emptied_headers():
    client = fresh_client()
    upload(client, "sample_survey.csv")

    # two headers that will collapse onto the same name once cut at '/'
    client.post("/api/clean_headers", json={"header_map": {
        "Age / വയസ്സ്": "Dup / a",
        "District / ജില്ല": "Dup / b",
    }})

    rows = {row["column"]: row for row in client.post(
        "/api/text_rules/preview",
        json={"stage": "headers",
              "rules": [{"mode": "delimiter", "delimiters": ["/"], "keep": "before"}]},
    ).get_json()["rows"]}

    assert rows["Dup / a"]["after"] == "Dup"
    assert rows["Dup / b"]["after"] == "Dup_1"
    assert "already taken" in rows["Dup / b"]["warning"]

    # a rule that would wipe a header out entirely keeps the original instead
    emptied = {row["column"]: row for row in client.post(
        "/api/text_rules/preview",
        json={"stage": "headers",
              "rules": [{"mode": "delimiter", "delimiters": ["T"], "keep": "before"}]},
    ).get_json()["rows"]}

    assert emptied["Timestamp"]["after"] == "Timestamp"
    assert "empty this header" in emptied["Timestamp"]["warning"]


def test_values_preview_counts_and_examples():
    client = fresh_client()
    upload(client, "sample_survey.csv")

    preview = client.post(
        "/api/text_rules/preview",
        json={"stage": "values",
              "rules": [{"mode": "delimiter", "delimiters": ["/"], "keep": "before"},
                        {"mode": "tidy"}],
              "columns": ["Gender / ലിംഗം"]},
    ).get_json()

    assert preview["columns_scanned"] == 1
    row = preview["rows"][0]
    assert row["cells_changed"] == row["cells_total"] == 30
    assert {example["after"] for example in row["examples"]} == {"Male", "Female"}


def test_recipe_v2_records_and_replays_text_rules():
    client = fresh_client()
    upload(client, "sample_survey.xlsx")

    trim = {"stage": "headers",
            "rules": [{"mode": "delimiter", "delimiters": ["/"], "keep": "before"},
                      {"mode": "tidy"}]}
    comments = "Any other comments?"   # what the trimmed header becomes
    client.post("/api/text_rules/apply", json=trim)
    client.post("/api/clean_headers",
                json={"header_map": {"Gender": "sex"}, "ignored_cols": [comments]})
    client.post("/api/text_rules/apply",
                json={"stage": "values",
                      "rules": [{"mode": "delimiter", "delimiters": ["/"], "keep": "before"},
                                {"mode": "tidy"}]})

    exported = client.get("/api/export_cleaning_rules")
    recipe = json.loads(exported.data.decode("utf-8"))
    assert recipe["version"] == 2
    assert [step["op"] for step in recipe["steps"]] == [
        "text_rules", "header_map", "text_rules"
    ]

    # replay onto wave 2 and expect the same names *and* the same trimmed values
    wave1_cols = list(state.session.df.columns)
    wave1_gender = set(state.session.df["sex"])

    upload(client, "sample_survey_wave2.csv")
    replay = client.post(
        "/api/apply_cleaning_rules_file",
        data={"file": (io.BytesIO(exported.data), "cleaning_rules.json")},
        content_type="multipart/form-data",
    ).get_json()["result"]

    assert replay["version"] == 2 and replay["steps_applied"] == 3
    assert list(state.session.df.columns) == wave1_cols
    assert set(state.session.df["sex"]) <= wave1_gender
    # the ignored column keeps its original text through the value stage
    assert state.session.df[comments].astype(str).str.contains("[^\x00-\x7F]").any()


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
