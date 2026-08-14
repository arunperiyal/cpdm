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
from cpdm.core import column_spec, groups, state, text_rules  # noqa: E402
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

    # group -> score -> compute
    assert client.post("/api/groups/create",
                       json={"name": "Wellbeing", "kind": "scale"}).status_code == 200
    client.post("/api/groups/create",
                json={"name": "Background", "kind": "demographics", "columns": ["Age"]})
    client.post("/api/groups/assign", json={"assignments": {
        col: "Wellbeing" for col in ["WB1", "WB2", "WB3", "WB4", "WB5"]
    }})
    assert state.session.categories["WB1"] == "Scale: Wellbeing"
    assert state.session.categories["Age"] == "Demographics"

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


def prepared_survey(client):
    """The sample survey with short column names, ready for grouping."""
    upload(client, "sample_survey.xlsx")
    apply_recipe(client)
    return client


def test_groups_build_a_tree_and_drive_categories():
    client = fresh_client()
    prepared_survey(client)

    client.post("/api/groups/create",
                json={"name": "Background", "kind": "demographics", "spec": "Age, Gender, District"})
    client.post("/api/groups/create",
                json={"name": "Wellbeing", "kind": "scale", "spec": "WB1:WB5"})
    created = client.post("/api/groups/create",
                          json={"name": "Positive affect", "parent": "Wellbeing",
                                "spec": "WB1, WB2, WB4"}).get_json()

    assert created["group"]["parent"] == "Wellbeing"

    tree = client.get("/api/groups").get_json()["groups"]
    names = {node["name"]: node for node in tree}
    assert set(names) == {"Background", "Wellbeing"}
    assert [child["name"] for child in names["Wellbeing"]["children"]] == ["Positive affect"]
    # a new subgroup is a plain container, so its parent stays the scale
    assert names["Wellbeing"]["children"][0]["kind"] == "other"

    # the flat category map the rest of the app reads follows the tree,
    # with subscale items still counted as part of their scale
    categories = state.session.state()["categories"]
    assert categories["Age"] == "Demographics"
    assert {categories[c] for c in ["WB1", "WB2", "WB3", "WB4", "WB5"]} == {"Scale: Wellbeing"}
    assert "Wellbeing" in state.session.defined_scales

    # ...so scoring and compute still see the whole scale
    computed = client.post("/api/compute", json={
        "new_col_name": "Wellbeing_Mean", "function_name": "mean",
        "selected_cols": ["WB1", "WB2", "WB3", "WB4", "WB5"]}).get_json()
    assert computed["new_col"] == "Wellbeing_Mean"


def test_subgroup_cannot_reach_outside_its_parent():
    client = fresh_client()
    prepared_survey(client)

    client.post("/api/groups/create", json={"name": "Wellbeing", "spec": "WB1:WB5"})
    response = client.post("/api/groups/create",
                           json={"name": "Bad", "parent": "Wellbeing", "spec": "DS1"})

    assert response.status_code == 400
    assert "not in the parent group" in response.get_json()["error"]

    eligible = client.post("/api/groups/eligible", json={"parent": "Wellbeing"}).get_json()
    assert eligible["columns"] == ["WB1", "WB2", "WB3", "WB4", "WB5"]


def test_shrinking_a_group_trims_its_subgroups():
    client = fresh_client()
    prepared_survey(client)

    client.post("/api/groups/create", json={"name": "Wellbeing", "spec": "WB1:WB5"})
    client.post("/api/groups/create",
                json={"name": "Positive affect", "parent": "Wellbeing", "spec": "WB1, WB2"})

    result = client.post("/api/groups/update",
                         json={"name": "Wellbeing", "columns": ["WB2", "WB3"]}).get_json()

    assert result["columns_dropped_from_subgroups"] == 1
    subgroup = groups.find(state.session, "Positive affect")
    assert subgroup["columns"] == ["WB2"]


def test_a_column_belongs_to_one_group_per_level():
    client = fresh_client()
    prepared_survey(client)

    client.post("/api/groups/create", json={"name": "Wellbeing", "spec": "WB1:WB5"})
    moved = client.post("/api/groups/create",
                        json={"name": "Stress", "spec": "WB5, DS1, DS2"}).get_json()["moved"]

    assert moved == {"Wellbeing": ["WB5"]}
    assert groups.find(state.session, "Wellbeing")["columns"] == ["WB1", "WB2", "WB3", "WB4"]
    assert state.session.state()["categories"]["WB5"] == "Scale: Stress"


def test_groups_survive_renames_and_scale_deletion():
    client = fresh_client()
    prepared_survey(client)

    client.post("/api/groups/create", json={"name": "Wellbeing", "spec": "WB1:WB5"})
    client.post("/api/groups/create",
                json={"name": "Positive affect", "parent": "Wellbeing", "spec": "WB1, WB2"})

    # numerise renames the scale's columns; the tree must follow
    client.post("/api/numerise", json={"prefix": "W", "target_scale": "Wellbeing"})
    assert groups.find(state.session, "Wellbeing")["columns"] == ["W1", "W2", "W3", "W4", "W5"]
    assert groups.find(state.session, "Positive affect")["columns"] == ["W1", "W2"]

    # deleting the group takes its subgroups with it
    client.post("/api/groups/delete", json={"name": "Wellbeing"})
    assert groups.find(state.session, "Wellbeing") is None
    assert groups.find(state.session, "Positive affect") is None
    assert state.session.categories["W1"] == "Uncategorised"
    assert state.session.defined_scales == []


def test_assigning_columns_one_by_one():
    client = fresh_client()
    prepared_survey(client)

    client.post("/api/groups/create", json={"name": "Wellbeing", "kind": "scale"})
    client.post("/api/groups/create",
                json={"name": "Background", "kind": "demographics", "columns": []})

    # a scale is just a group marked as one, and starts out empty
    assert state.session.defined_scales == ["Wellbeing"]
    assert groups.find(state.session, "Wellbeing")["columns"] == []

    client.post("/api/groups/assign", json={"assignments": {
        "WB1": "Wellbeing", "WB2": "Wellbeing", "WB3": "Wellbeing",
        "Age": "Background", "Gender": "Background",
    }})

    listing = client.get("/api/groups").get_json()
    assert listing["assignments"]["WB1"] == "Wellbeing"
    assert listing["assignments"]["Comments"] is None
    assert "Comments" in listing["ungrouped"]
    assert state.session.categories["Gender"] == "Demographics"

    # naming a subgroup files the column under its parent as well
    client.post("/api/groups/create",
                json={"name": "Positive affect", "parent": "Wellbeing", "columns": ["WB1"]})
    client.post("/api/groups/assign", json={"assignments": {"WB2": "Positive affect"}})

    assert groups.find(state.session, "Positive affect")["columns"] == ["WB1", "WB2"]
    assert "WB2" in groups.find(state.session, "Wellbeing")["columns"]
    assert client.get("/api/groups").get_json()["assignments"]["WB2"] == "Positive affect"

    # clearing a column takes it out of every group, parents included
    client.post("/api/groups/assign", json={"assignments": {"WB2": ""}})
    assert "WB2" not in groups.find(state.session, "Wellbeing")["columns"]
    assert "WB2" not in groups.find(state.session, "Positive affect")["columns"]
    assert state.session.categories["WB2"] == "Uncategorised"


def test_categorise_endpoint_is_gone():
    client = fresh_client()
    prepared_survey(client)
    assert client.post("/api/categorise", json={"categories": {}}).status_code == 404


def test_subgroup_positions_are_relative_to_the_parent():
    """1:4 inside a group means that group's first four columns."""
    client = fresh_client()
    prepared_survey(client)

    table = list(state.session.df.columns)
    assert table[7:16] == ["WB1", "WB2", "WB3", "WB4", "WB5",
                           "DS1", "DS2", "DS3", "DS4"]

    # a container over table columns 8:16
    client.post("/api/groups/create",
                json={"name": "Scales", "kind": "other", "spec": "8:16"})

    resolved = client.post("/api/groups/resolve_spec",
                           json={"spec": "1:4", "parent": "Scales"}).get_json()
    assert resolved["columns"] == ["WB1", "WB2", "WB3", "WB4"]

    client.post("/api/groups/create",
                json={"name": "PHQ", "parent": "Scales", "kind": "scale", "spec": "1:4"})
    client.post("/api/groups/create",
                json={"name": "GAD", "parent": "Scales", "kind": "scale", "spec": "6:9"})

    assert groups.find(state.session, "PHQ")["columns"] == ["WB1", "WB2", "WB3", "WB4"]
    assert groups.find(state.session, "GAD")["columns"] == ["DS1", "DS2", "DS3", "DS4"]

    # the same digits at the root count against the whole table instead
    root_level = client.post("/api/groups/resolve_spec",
                             json={"spec": "1:4", "parent": None}).get_json()
    assert root_level["columns"] == table[:4]

    # a position outside the parent is reported, not silently taken
    outside = client.post("/api/groups/resolve_spec",
                          json={"spec": "1, 99, Timestamp", "parent": "Scales"}).get_json()
    assert outside["columns"] == ["WB1"]
    assert outside["rejected"] == ["Timestamp"]
    assert outside["unknown"] == ["99"]


def test_a_subgroup_can_be_the_scale():
    """The deepest group marked as a scale wins, so containers can hold scales."""
    client = fresh_client()
    prepared_survey(client)

    client.post("/api/groups/create",
                json={"name": "Scales", "kind": "other", "spec": "WB1:DS4"})
    client.post("/api/groups/create",
                json={"name": "PHQ", "parent": "Scales", "kind": "scale", "spec": "1:5"})
    client.post("/api/groups/create",
                json={"name": "GAD", "parent": "Scales", "kind": "scale", "spec": "6:9"})

    # the container claims nothing; each subgroup is its own scale
    assert state.session.defined_scales == ["PHQ", "GAD"]
    categories = state.session.categories
    assert categories["WB1"] == "Scale: PHQ"
    assert categories["DS1"] == "Scale: GAD"

    # so Numerise and Scoring address them separately
    client.post("/api/numerise", json={"prefix": "PHQ_", "target_scale": "PHQ"})
    assert "PHQ_1" in state.session.df.columns
    assert groups.find(state.session, "PHQ")["columns"][0] == "PHQ_1"
    assert "DS1" in state.session.df.columns

    # marking the container as the scale instead puts everything back under it
    client.post("/api/groups/update", json={"name": "Scales", "kind": "scale"})
    client.post("/api/groups/update", json={"name": "PHQ", "kind": "other"})
    client.post("/api/groups/update", json={"name": "GAD", "kind": "other"})
    assert state.session.defined_scales == ["Scales"]
    assert state.session.categories["PHQ_1"] == "Scale: Scales"


def test_column_spec_forms():
    columns = ["Timestamp", "Age", "WB1", "WB2", "WB3", "DS1", "5"]

    assert column_spec.parse("WB1:WB3", columns)["columns"] == ["WB1", "WB2", "WB3"]
    assert column_spec.parse("2:4", columns)["columns"] == ["Age", "WB1", "WB2"]
    assert column_spec.parse("DS*", columns)["columns"] == ["DS1"]
    assert column_spec.parse("age", columns)["columns"] == ["Age"]        # case-insensitive
    assert column_spec.parse("5", columns)["columns"] == ["5"]            # a real column wins
    assert column_spec.parse("WB1, nope", columns)["unknown"] == ["nope"]

    scoped = column_spec.parse("WB1, DS1", columns, allowed=["WB1", "WB2"])
    assert scoped["columns"] == ["WB1"] and scoped["rejected"] == ["DS1"]

    # positions count within the allowed list, not the table
    relative = column_spec.parse("1:2", columns, allowed=["WB2", "WB3", "DS1"])
    assert relative["columns"] == ["WB2", "WB3"]


def test_groups_console_command():
    client = fresh_client()
    prepared_survey(client)
    client.post("/api/groups/create", json={"name": "Wellbeing", "spec": "WB1:WB5"})
    client.post("/api/groups/create",
                json={"name": "Positive affect", "parent": "Wellbeing", "spec": "WB1"})

    output = client.post("/api/command", json={"command": "groups"}).get_json()["output"]
    assert "[Wellbeing] Scale, 5 column(s)" in output
    assert "  - [Positive affect]" in output


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
