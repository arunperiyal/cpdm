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
                       json={"name": "Wellbeing"}).status_code == 200
    client.post("/api/groups/create", json={"name": "Background", "columns": ["Age"]})
    client.post("/api/groups/assign", json={"assignments": {
        col: "Wellbeing" for col in ["WB1", "WB2", "WB3", "WB4", "WB5"]
    }})

    # a group on its own is not a scale
    assert state.session.categories["WB1"] == "Uncategorised"
    client.post("/api/create_scale", json={"group": "Wellbeing"})
    assert state.session.categories["WB1"] == "Scale: Wellbeing"
    assert state.session.categories["Age"] == "Uncategorised"

    # the scale seeded its options from the data, already coded 1-5
    detail = client.get("/api/scales/Wellbeing").get_json()
    assert [option["score"] for option in detail["options"]] == [1, 2, 3, 4, 5]

    client.post("/api/scales/items",
                json={"name": "Wellbeing", "items": {"WB3": "Reverse", "WB5": "Reverse"}})
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


def test_leftovers_stage_lists_and_fixes_what_rules_miss():
    client = fresh_client()
    upload(client, "sample_survey.xlsx")

    trim = {"rules": [{"mode": "delimiter", "delimiters": ["/"], "keep": "before"},
                      {"mode": "tidy"}]}
    client.post("/api/text_rules/apply", json={"stage": "headers", **trim})
    client.post("/api/text_rules/apply", json={"stage": "values", **trim})

    left = client.post("/api/text_rules/leftovers", json={}).get_json()
    assert left["headers"] == []          # the delimiter rule got them all
    assert len(left["values"]) == 1       # one Malayalam free-text comment
    entry = left["values"][0]
    assert entry["columns"] == ["Any other comments?"] and entry["marks"]

    fixed = client.post("/api/text_rules/fix_leftovers", json={
        "values": {entry["value"]: "Wants more questions"}}).get_json()["result"]
    assert fixed["cells_changed"] == entry["count"]
    assert client.post("/api/text_rules/leftovers", json={}).get_json()["values"] == []

    # a whole-cell replacement cannot bleed into a longer answer containing it
    assert "Wants more questions" in set(state.session.df["Any other comments?"])
    assert state.session.df["Any other comments?"].astype(str).str.contains(
        "Some questions felt repetitive").any()


def test_leftover_fixes_are_recorded_and_replay():
    client = fresh_client()
    upload(client, "sample_survey.xlsx")

    client.post("/api/text_rules/apply", json={
        "stage": "values",
        "rules": [{"mode": "delimiter", "delimiters": ["/"], "keep": "before"},
                  {"mode": "tidy"}]})
    left = client.post("/api/text_rules/leftovers", json={}).get_json()["values"][0]
    client.post("/api/text_rules/fix_leftovers",
                json={"values": {left["value"]: "Wants more questions"}})

    recipe = json.loads(client.get("/api/export_cleaning_rules").data.decode("utf-8"))
    assert [step["op"] for step in recipe["steps"]] == ["text_rules", "exact_values"]

    # the same hand fix replays onto the next wave
    client = fresh_client()
    upload(client, "sample_survey.xlsx")
    replayed = client.post(
        "/api/apply_cleaning_rules_file",
        data={"file": (io.BytesIO(json.dumps(recipe).encode("utf-8")), "rules.json")},
        content_type="multipart/form-data",
    ).get_json()["result"]

    assert replayed["steps_applied"] == 2
    comments = [col for col in state.session.df.columns if "comments" in col.lower()][0]
    assert "Wants more questions" in set(state.session.df[comments])


def test_whole_cell_replacement_is_exact():
    client = fresh_client()
    upload(client, "sample_survey.csv")

    # "Agree" as a whole cell exists nowhere yet: every answer carries its tail
    before = list(state.session.df.iloc[:, 7])
    client.post("/api/text_rules/fix_leftovers", json={"values": {"Agree": "4"}})
    assert list(state.session.df.iloc[:, 7]) == before

    client.post("/api/text_rules/apply", json={
        "stage": "values",
        "rules": [{"mode": "delimiter", "delimiters": ["/"], "keep": "before"},
                  {"mode": "tidy"}]})
    client.post("/api/text_rules/fix_leftovers", json={"values": {"Agree": "4"}})

    values = set(state.session.df.iloc[:, 7].dropna())
    assert "4" in values                       # exact cells replaced
    assert "Strongly Agree" in values          # the longer answer untouched


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
                json={"name": "Background", "spec": "Age, Gender, District"})
    client.post("/api/groups/create", json={"name": "Wellbeing", "spec": "WB1:WB5"})
    client.post("/api/create_scale", json={"group": "Wellbeing"})
    created = client.post("/api/groups/create",
                          json={"name": "Positive affect", "parent": "Wellbeing",
                                "spec": "WB1, WB2, WB4"}).get_json()

    assert created["group"]["parent"] == "Wellbeing"

    tree = client.get("/api/groups").get_json()["groups"]
    names = {node["name"]: node for node in tree}
    assert set(names) == {"Background", "Wellbeing"}
    assert [child["name"] for child in names["Wellbeing"]["children"]] == ["Positive affect"]
    # the tree shows which group carries a scale, and a new subgroup carries none
    assert names["Wellbeing"]["scale"] == "Wellbeing"
    assert names["Wellbeing"]["children"][0]["scale"] is None
    assert names["Background"]["scale"] is None

    # the flat category map the rest of the app reads follows the tree,
    # with subscale items still counted as part of their scale
    categories = state.session.state()["categories"]
    assert categories["Age"] == "Uncategorised"      # grouped, but not a scale
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
    client.post("/api/create_scale", json={"group": "Stress"})
    assert state.session.state()["categories"]["WB5"] == "Scale: Stress"


def test_groups_survive_renames_and_scale_deletion():
    client = fresh_client()
    prepared_survey(client)

    client.post("/api/groups/create", json={"name": "Wellbeing", "spec": "WB1:WB5"})
    client.post("/api/groups/create",
                json={"name": "Positive affect", "parent": "Wellbeing", "spec": "WB1, WB2"})

    client.post("/api/create_scale", json={"group": "Wellbeing"})

    # renaming a scale's items renames the columns; the tree must follow
    client.post("/api/scales/rename_items", json={"name": "Wellbeing", "prefix": "W"})
    assert groups.find(state.session, "Wellbeing")["columns"] == ["W_1", "W_2", "W_3", "W_4", "W_5"]
    assert groups.find(state.session, "Positive affect")["columns"] == ["W_1", "W_2"]

    # renaming a group carries its scale along
    client.post("/api/groups/update", json={"name": "Wellbeing", "new_name": "WB"})
    assert groups.scale_on(state.session, "WB") == "Wellbeing"
    assert state.session.categories["W_1"] == "Scale: Wellbeing"

    # deleting the group takes its subgroups and its scale with it
    removed = client.post("/api/groups/delete", json={"name": "WB"}).get_json()
    assert removed["scales_removed"] == ["Wellbeing"]
    assert groups.find(state.session, "WB") is None
    assert groups.find(state.session, "Positive affect") is None
    assert state.session.categories["W_1"] == "Uncategorised"
    assert state.session.defined_scales == []


def test_assigning_columns_one_by_one():
    client = fresh_client()
    prepared_survey(client)

    client.post("/api/groups/create", json={"name": "Wellbeing"})
    client.post("/api/groups/create", json={"name": "Background", "columns": []})

    # an empty group cannot be a scale yet: a scale reads a group's columns
    refused = client.post("/api/create_scale", json={"group": "Wellbeing"})
    assert refused.status_code == 400 and "no columns" in refused.get_json()["error"]
    assert groups.find(state.session, "Wellbeing")["columns"] == []

    client.post("/api/groups/assign", json={"assignments": {
        "WB1": "Wellbeing", "WB2": "Wellbeing", "WB3": "Wellbeing",
        "Age": "Background", "Gender": "Background",
    }})

    listing = client.get("/api/groups").get_json()
    assert listing["assignments"]["WB1"] == "Wellbeing"
    assert listing["assignments"]["Comments"] is None
    assert "Comments" in listing["ungrouped"]
    assert state.session.categories["Gender"] == "Uncategorised"

    # naming a subgroup files the column under its parent as well
    client.post("/api/groups/create",
                json={"name": "Positive affect", "parent": "Wellbeing", "columns": ["WB1"]})
    client.post("/api/groups/assign", json={"assignments": {"WB2": "Positive affect"}})

    assert groups.find(state.session, "Positive affect")["columns"] == ["WB1", "WB2"]
    assert "WB2" in groups.find(state.session, "Wellbeing")["columns"]
    assert client.get("/api/groups").get_json()["assignments"]["WB2"] == "Positive affect"

    # clearing a column takes it out of every group, parents included
    client.post("/api/create_scale", json={"group": "Wellbeing"})
    assert state.session.categories["WB2"] == "Scale: Wellbeing"
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
    client.post("/api/groups/create", json={"name": "Scales", "spec": "8:16"})

    resolved = client.post("/api/groups/resolve_spec",
                           json={"spec": "1:4", "parent": "Scales"}).get_json()
    assert resolved["columns"] == ["WB1", "WB2", "WB3", "WB4"]

    client.post("/api/groups/create",
                json={"name": "PHQ", "parent": "Scales", "spec": "1:4"})
    client.post("/api/groups/create",
                json={"name": "GAD", "parent": "Scales", "spec": "6:9"})

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


def test_scales_are_declared_on_groups_and_can_be_nested():
    """A container group holding two scales, each declared on a subgroup."""
    client = fresh_client()
    prepared_survey(client)

    client.post("/api/groups/create", json={"name": "Scales", "spec": "WB1:DS4"})
    client.post("/api/groups/create",
                json={"name": "PHQ", "parent": "Scales", "spec": "1:5"})
    client.post("/api/groups/create",
                json={"name": "GAD", "parent": "Scales", "spec": "6:9"})

    # groups alone claim nothing
    assert state.session.defined_scales == []
    assert set(state.session.categories.values()) == {"Uncategorised"}

    # the scale may be named differently from the group it reads
    client.post("/api/create_scale", json={"group": "PHQ", "name": "PHQ-9"})
    client.post("/api/create_scale", json={"group": "GAD"})

    assert state.session.defined_scales == ["PHQ-9", "GAD"]
    assert state.session.categories["WB1"] == "Scale: PHQ-9"
    assert state.session.categories["DS1"] == "Scale: GAD"

    listing = client.get("/api/scales").get_json()
    phq = next(s for s in listing["scales"] if s["name"] == "PHQ-9")
    assert phq["group"] == "PHQ" and phq["column_count"] == 5
    assert {g["name"]: g["taken_by"] for g in listing["groups"]} == {
        "Scales": None, "PHQ": "PHQ-9", "GAD": "GAD"}

    # each scale renames its own items, leaving the other scale alone
    client.post("/api/scales/rename_items", json={"name": "PHQ-9"})
    assert "PHQ-9_1" in state.session.df.columns
    assert groups.find(state.session, "PHQ")["columns"][0] == "PHQ-9_1"
    assert "DS1" in state.session.df.columns

    # a scale on the container as well: the deeper declaration wins its columns
    client.post("/api/create_scale", json={"group": "Scales", "name": "Whole battery"})
    assert state.session.categories["PHQ-9_1"] == "Scale: PHQ-9"
    assert state.session.categories["Comments"] == "Uncategorised"

    # dropping the deeper scale hands those columns to the one above
    client.post("/api/delete_scale", json={"scale_name": "PHQ-9"})
    assert state.session.categories["PHQ-9_1"] == "Scale: Whole battery"
    # ...and the group itself is untouched
    assert len(groups.find(state.session, "PHQ")["columns"]) == 5


def test_scale_items_options_and_scoring():
    """The full describe -> order -> score -> type -> apply path, on text answers."""
    client = fresh_client()
    upload(client, "sample_survey.xlsx")

    # trim the bilingual tails but leave the Likert answers as text
    client.post("/api/text_rules/apply", json={
        "stage": "headers",
        "rules": [{"mode": "delimiter", "delimiters": ["/"], "keep": "before"},
                  {"mode": "tidy"}]})
    client.post("/api/text_rules/apply", json={
        "stage": "values",
        "rules": [{"mode": "delimiter", "delimiters": ["/"], "keep": "before"},
                  {"mode": "tidy"}]})
    client.post("/api/clean_headers", json={"header_map": {
        "1. I feel calm and relaxed most days": "WB1",
        "2. I sleep well at night": "WB2",
        "3. I often feel tense for no clear reason": "WB3",
    }})
    client.post("/api/groups/create", json={"name": "WB", "columns": ["WB1", "WB2", "WB3"]})

    # what the group would give a scale, before creating it
    inspected = client.post("/api/scales/inspect_group", json={"group": "WB"}).get_json()
    assert inspected["items"] == ["WB1", "WB2", "WB3"]
    assert set(inspected["options"]) == {
        "Strongly Agree", "Agree", "Neutral", "Disagree", "Strongly Disagree"}

    client.post("/api/create_scale", json={"group": "WB", "name": "Wellbeing"})
    detail = client.get("/api/scales/Wellbeing").get_json()
    assert [item["type"] for item in detail["items"]] == ["Direct"] * 3
    # text answers cannot be scored automatically
    assert all(option["score"] is None for option in detail["options"])

    # put the options in response order, adding one nobody chose
    ordered = ["Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree"]
    client.post("/api/scales/options", json={
        "name": "Wellbeing",
        "options": [{"label": label} for label in ordered] + [{"label": "Not applicable"}]})
    client.post("/api/scales/options/autoscore", json={"name": "Wellbeing"})

    # the added option must not stretch the scale's range
    client.post("/api/scales/options", json={
        "name": "Wellbeing",
        "options": [{"label": label, "score": index + 1} for index, label in enumerate(ordered)]
                   + [{"label": "Not applicable", "score": None}]})
    detail = client.get("/api/scales/Wellbeing").get_json()
    assert (detail["score_min"], detail["score_max"]) == (1, 5)
    assert detail["unscored"] == ["Not applicable"]

    client.post("/api/scales/items", json={"name": "Wellbeing", "items": {"WB3": "Reverse"}})

    # setting the scores was enough: the data is already scored
    plan = client.post("/api/scales/status", json={}).get_json()["plans"][0]
    assert plan["reversal_note"] == "reverse = 6 - value"
    assert {item["column"]: item["type"] for item in plan["items"]} == {
        "WB1": "Direct", "WB2": "Direct", "WB3": "Reverse"}
    assert all(item["unmapped"] == [] for item in plan["items"])

    for column in ["WB1", "WB2", "WB3"]:
        assert pd.api.types.is_numeric_dtype(state.session.df[column])
        assert state.session.df[column].dropna().between(1, 5).all()

    # columns outside the scale keep their text
    assert state.session.df["Gender"].astype(str).str.contains("Male|Female").any()


def test_unrecognised_answers_are_reported_not_silently_dropped():
    client = fresh_client()
    prepared_survey(client)

    client.post("/api/groups/create", json={"name": "WB", "spec": "WB1:WB5"})
    client.post("/api/create_scale", json={"group": "WB", "name": "Wellbeing"})

    # drop an option the data actually uses
    detail = client.get("/api/scales/Wellbeing").get_json()
    kept = [o for o in detail["options"] if o["label"] != "5"]
    client.post("/api/scales/options", json={"name": "Wellbeing", "options": kept})

    plan = client.post("/api/scales/status", json={}).get_json()["plans"][0]
    assert any("5" in item["unmapped"] for item in plan["items"])

    # an option left on the list without a score is missing by design, not an error
    blanked = [{"label": o["label"], "score": (None if o["label"] == "4" else o["score"])}
               for o in kept]
    client.post("/api/scales/options", json={"name": "Wellbeing", "options": blanked})
    plan = client.post("/api/scales/status", json={}).get_json()["plans"][0]
    assert all("4" not in item["unmapped"] for item in plan["items"])

    refreshed = client.post("/api/scales/options/refresh", json={"name": "Wellbeing"}).get_json()
    assert refreshed["added"] == ["5"]


def test_scoring_is_idempotent_and_reversible():
    """Re-scoring must never double-flip or blank a text-answer scale."""
    client = fresh_client()
    upload(client, "sample_survey.xlsx")

    client.post("/api/text_rules/apply", json={
        "stage": "values",
        "rules": [{"mode": "delimiter", "delimiters": ["/"], "keep": "before"},
                  {"mode": "tidy"}]})
    likert = list(state.session.df.columns)[7:9]
    client.post("/api/groups/create", json={"name": "WB", "columns": likert})
    client.post("/api/create_scale", json={"group": "WB", "name": "Wellbeing"})
    client.post("/api/scales/options", json={
        "name": "Wellbeing",
        "options": [{"label": label, "score": index + 1} for index, label in enumerate(
            ["Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree"])]})

    first = list(state.session.df[likert[0]])
    assert pd.api.types.is_numeric_dtype(state.session.df[likert[0]])

    # saving the same definition again — the old bug blanked the whole scale
    for _ in range(3):
        client.post("/api/scales/options/refresh", json={"name": "Wellbeing"})
        client.post("/api/scales/items", json={"name": "Wellbeing", "items": {}})
    assert list(state.session.df[likert[0]]) == first

    # a keying change re-derives from the answers, so it can be undone
    client.post("/api/scales/items", json={"name": "Wellbeing", "items": {likert[0]: "Reverse"}})
    reversed_values = list(state.session.df[likert[0]])
    assert reversed_values != first
    assert all(6 - a == b for a, b in zip(first, reversed_values) if pd.notna(a))

    client.post("/api/scales/items", json={"name": "Wellbeing", "items": {likert[0]: "Direct"}})
    assert list(state.session.df[likert[0]]) == first

    # the options still show the answers, not the numbers now in the column
    detail = client.get("/api/scales/Wellbeing").get_json()
    assert [option["label"] for option in detail["options"]][0] == "Strongly Disagree"

    # rescoring on a different scale of numbers also works from the answers
    client.post("/api/scales/options", json={
        "name": "Wellbeing",
        "options": [{"label": label, "score": (index + 1) * 10} for index, label in enumerate(
            ["Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree"])]})
    assert [value * 10 for value in first if pd.notna(value)] == [
        value for value in state.session.df[likert[0]] if pd.notna(value)]


def test_scale_renames_its_own_items():
    client = fresh_client()
    prepared_survey(client)

    client.post("/api/groups/create", json={"name": "Items", "spec": "WB1:WB5"})
    client.post("/api/create_scale",
                json={"group": "Items", "name": "Digital Stress", "rename": True})

    # the scale name becomes the prefix, whitespace and all
    assert [col for col in state.session.df.columns if col.startswith("Digital")] == [
        "Digital_Stress_1", "Digital_Stress_2", "Digital_Stress_3",
        "Digital_Stress_4", "Digital_Stress_5"]
    assert groups.find(state.session, "Items")["columns"][0] == "Digital_Stress_1"

    # renaming again with an explicit prefix, after the fact
    client.post("/api/scales/rename_items", json={"name": "Digital Stress", "prefix": "DS"})
    assert "DS_3" in state.session.df.columns

    # a clash with a column outside the scale is refused, not silently taken
    client.post("/api/groups/create", json={"name": "Other", "columns": ["Age"]})
    client.post("/api/create_scale", json={"group": "Other", "name": "Age scale"})
    clash = client.post("/api/scales/rename_items", json={"name": "Age scale", "prefix": "DS"})
    assert clash.status_code == 400 and "already used" in clash.get_json()["error"]


def test_deleting_a_scale_puts_the_answers_back():
    client = fresh_client()
    upload(client, "sample_survey.xlsx")

    likert = list(state.session.df.columns)[7:9]
    answers = list(state.session.df[likert[0]])

    client.post("/api/groups/create", json={"name": "WB", "columns": likert})
    client.post("/api/create_scale", json={"group": "WB", "name": "Wellbeing"})
    detail = client.get("/api/scales/Wellbeing").get_json()
    client.post("/api/scales/options", json={
        "name": "Wellbeing",
        "options": [{"label": option["label"], "score": index + 1}
                    for index, option in enumerate(detail["options"])]})
    assert pd.api.types.is_numeric_dtype(state.session.df[likert[0]])

    deleted = client.post("/api/delete_scale", json={"scale_name": "Wellbeing"}).get_json()
    assert set(deleted["restored"]) == set(likert)
    assert list(state.session.df[likert[0]]) == answers
    # the group survives; only the scale went
    assert groups.find(state.session, "WB")["columns"] == likert


def test_scoring_needs_scored_options():
    client = fresh_client()
    prepared_survey(client)

    client.post("/api/groups/create", json={"name": "WB", "spec": "WB1:WB5"})
    client.post("/api/create_scale", json={"group": "WB", "name": "Wellbeing"})
    client.post("/api/scales/options", json={
        "name": "Wellbeing",
        "options": [{"label": str(n), "score": None} for n in range(1, 6)]})

    # with nothing scored, the data is left exactly as it was
    before = list(state.session.df["WB1"])
    client.post("/api/scales/items", json={"name": "Wellbeing", "items": {"WB1": "Reverse"}})
    assert list(state.session.df["WB1"]) == before
    assert client.post("/api/scales/status", json={}).get_json()["plans"] == []

    duplicate = client.post("/api/scales/options", json={
        "name": "Wellbeing", "options": [{"label": "Yes"}, {"label": "yes"}]})
    assert duplicate.status_code == 400 and "Duplicate" in duplicate.get_json()["error"]

    bad_type = client.post("/api/scales/items",
                           json={"name": "Wellbeing", "items": {"WB1": "Sideways"}})
    assert bad_type.status_code == 400

    not_an_item = client.post("/api/scales/items",
                              json={"name": "Wellbeing", "items": {"Age": "Reverse"}})
    assert not_an_item.status_code == 400 and "not an item" in not_an_item.get_json()["error"]


def test_item_types_follow_a_rename():
    client = fresh_client()
    prepared_survey(client)

    client.post("/api/groups/create", json={"name": "WB", "spec": "WB1:WB5"})
    client.post("/api/create_scale", json={"group": "WB", "name": "Wellbeing"})
    client.post("/api/scales/items", json={"name": "Wellbeing", "items": {"WB3": "Reverse"}})

    client.post("/api/scales/rename_items", json={"name": "Wellbeing", "prefix": "W"})
    detail = client.get("/api/scales/Wellbeing").get_json()
    assert [item["column"] for item in detail["items"]] == ["W_1", "W_2", "W_3", "W_4", "W_5"]
    assert [item["type"] for item in detail["items"]] == [
        "Direct", "Direct", "Reverse", "Direct", "Direct"]


def test_value_replacement_keeps_blanks_blank():
    client = fresh_client()
    upload(client, "sample_survey.csv")

    blanks_before = int(state.session.df.iloc[:, 9].isna().sum())
    assert blanks_before > 0

    client.post("/api/clean_values", json={"replacements": {"Agree": "4"}})
    column = state.session.df.iloc[:, 9]

    # blanks stay blank rather than becoming the literal text "nan"
    assert int(column.isna().sum()) == blanks_before
    assert "nan" not in {value for value in column if isinstance(value, str)}

    # and a scale built on that column does not offer "nan" as an answer
    client.post("/api/groups/create", json={"name": "G", "columns": [column.name]})
    created = client.post("/api/create_scale", json={"group": "G"}).get_json()["scale"]
    assert all(option["label"] != "nan" for option in created["options"])


def test_scale_definitions_travel_between_datasets():
    """Save a scale, load it onto the next wave, keying and all."""
    client = fresh_client()
    prepared_survey(client)

    client.post("/api/groups/create", json={"name": "Wellbeing", "spec": "WB1:WB5"})
    client.post("/api/create_scale", json={"group": "Wellbeing", "name": "WEMWBS"})
    client.post("/api/scales/items",
                json={"name": "WEMWBS", "items": {"WB3": "Reverse", "WB5": "Reverse"}})

    exported = client.get("/api/scales/export")
    assert exported.status_code == 200
    payload = json.loads(exported.data.decode("utf-8"))
    assert payload["kind"] == "cpdm-scales"
    definition = payload["scales"][0]
    assert definition["name"] == "WEMWBS" and definition["group"] == "Wellbeing"
    assert [item["type"] for item in definition["items"]] == [
        "Direct", "Direct", "Reverse", "Direct", "Reverse"]

    # a fresh session, same questionnaire
    client = fresh_client()
    upload(client, "sample_survey_wave2.csv")
    apply_recipe(client)
    client.post("/api/groups/create", json={"name": "Wellbeing", "spec": "WB1:WB5"})

    result = client.post(
        "/api/scales/import",
        data={"file": (io.BytesIO(exported.data), "scales.json")},
        content_type="multipart/form-data",
    ).get_json()["results"][0]

    assert result["loaded"] and result["group"] == "Wellbeing"
    detail = client.get("/api/scales/WEMWBS").get_json()
    assert [item["type"] for item in detail["items"]] == [
        "Direct", "Direct", "Reverse", "Direct", "Reverse"]
    assert [option["score"] for option in detail["options"]] == [1, 2, 3, 4, 5]
    # loading scored the data on the way in
    assert pd.api.types.is_numeric_dtype(state.session.df["WB3"])


def test_loading_scales_reports_what_it_could_not_do():
    client = fresh_client()
    prepared_survey(client)
    client.post("/api/groups/create", json={"name": "Wellbeing", "spec": "WB1:WB5"})
    client.post("/api/create_scale", json={"group": "Wellbeing", "name": "WEMWBS"})
    exported = client.get("/api/scales/export").data

    # loading the same file again: the scale is already here
    again = client.post(
        "/api/scales/import",
        data={"file": (io.BytesIO(exported), "scales.json")},
        content_type="multipart/form-data",
    ).get_json()["results"][0]
    assert not again["loaded"] and "already exists" in again["reason"]

    # a dataset without those columns cannot take it
    client = fresh_client()
    upload(client, "sample_survey.csv")          # untrimmed headers
    missing = client.post(
        "/api/scales/import",
        data={"file": (io.BytesIO(exported), "scales.json")},
        content_type="multipart/form-data",
    ).get_json()["results"][0]
    assert not missing["loaded"] and "no group here holds its columns" in missing["reason"]

    # and a file that is not a scale file is refused outright
    junk = client.post(
        "/api/scales/import",
        data={"file": (io.BytesIO(b'{"kind": "something-else"}'), "x.json")},
        content_type="multipart/form-data",
    )
    assert junk.status_code == 400 and "not a CPDM scale file" in junk.get_json()["error"]


def test_loading_can_be_pointed_at_a_group_by_hand():
    """A scale saved after renaming its items still loads, onto a chosen group."""
    client = fresh_client()
    prepared_survey(client)
    client.post("/api/groups/create", json={"name": "Wellbeing", "spec": "WB1:WB5"})
    client.post("/api/create_scale",
                json={"group": "Wellbeing", "name": "WEMWBS", "rename": True})
    client.post("/api/scales/items",
                json={"name": "WEMWBS", "items": {"WEMWBS_3": "Reverse"}})
    saved = json.loads(client.get("/api/scales/export").data.decode("utf-8"))

    # wave 2 has the untouched WB1..WB5 headers, so nothing matches by name
    client = fresh_client()
    upload(client, "sample_survey_wave2.csv")
    apply_recipe(client)
    client.post("/api/groups/create", json={"name": "Items", "spec": "WB1:WB5"})

    inspected = client.post("/api/scales/inspect_file", json={"payload": saved}).get_json()
    entry = inspected["scales"][0]
    assert entry["suggested_group"] is None and not entry["can_create_group"]
    assert [group["name"] for group in inspected["groups"]] == ["Items"]

    result = client.post("/api/scales/import", json={
        "payload": saved, "mapping": {"WEMWBS": "Items"}}).get_json()["results"][0]

    assert result["loaded"] and result["group"] == "Items"
    assert result["items_by_position"] == 5      # headers differ, keying by position
    detail = client.get("/api/scales/WEMWBS").get_json()
    assert [item["type"] for item in detail["items"]] == [
        "Direct", "Direct", "Reverse", "Direct", "Direct"]

    # and skipping is honoured
    client.post("/api/delete_scale", json={"scale_name": "WEMWBS"})
    skipped = client.post("/api/scales/import", json={
        "payload": saved, "mapping": {"WEMWBS": ""}}).get_json()["results"][0]
    assert not skipped["loaded"] and skipped["reason"] == "skipped"


def test_loading_builds_the_group_when_the_columns_are_there():
    client = fresh_client()
    prepared_survey(client)
    client.post("/api/groups/create", json={"name": "Wellbeing", "spec": "WB1:WB5"})
    client.post("/api/create_scale", json={"group": "Wellbeing", "name": "WEMWBS"})
    exported = client.get("/api/scales/export").data

    # same columns, but no groups at all this time
    client = fresh_client()
    prepared_survey(client)
    result = client.post(
        "/api/scales/import",
        data={"file": (io.BytesIO(exported), "scales.json")},
        content_type="multipart/form-data",
    ).get_json()["results"][0]

    assert result["loaded"] and result["group_matched"] == "new group from the file"
    assert groups.find(state.session, "Wellbeing")["columns"] == [
        "WB1", "WB2", "WB3", "WB4", "WB5"]


def test_scale_declaration_rules():
    client = fresh_client()
    prepared_survey(client)

    client.post("/api/groups/create", json={"name": "Wellbeing", "spec": "WB1:WB5"})
    client.post("/api/create_scale", json={"group": "Wellbeing"})

    twice = client.post("/api/create_scale", json={"group": "Wellbeing", "name": "Other"})
    assert twice.status_code == 400 and "already the scale" in twice.get_json()["error"]

    client.post("/api/groups/create", json={"name": "Stress", "spec": "DS*"})
    clash = client.post("/api/create_scale", json={"group": "Stress", "name": "wellbeing"})
    assert clash.status_code == 400 and "already exists" in clash.get_json()["error"]

    missing = client.post("/api/create_scale", json={"group": "Nope"})
    assert missing.status_code == 400 and "No group named" in missing.get_json()["error"]


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
    assert "[Wellbeing] group, 5 column(s)" in output
    assert "  - [Positive affect]" in output

    assert "No scales yet" in client.post(
        "/api/command", json={"command": "scales"}).get_json()["output"]

    client.post("/api/create_scale", json={"group": "Wellbeing", "name": "WEMWBS"})
    assert "[Wellbeing] scale 'WEMWBS'" in client.post(
        "/api/command", json={"command": "groups"}).get_json()["output"]
    scales_output = client.post("/api/command", json={"command": "scales"}).get_json()["output"]
    assert "[WEMWBS] from group 'Wellbeing': 5 item(s) (0 reverse)" in scales_output
    assert "options: 1=1, 2=2, 3=3, 4=4, 5=5" in scales_output


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
