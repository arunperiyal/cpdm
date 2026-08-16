"""Saving and replaying a cleaning recipe.

Two formats are understood:

**v2** carries an ordered ``steps`` log. Order matters — trimming headers and
then mapping them is a different dataset from mapping and then trimming — so a
v2 recipe replays the session exactly as it happened.

**v1** is the flat ``header_map`` / ``value_replacements`` / ``ignored_columns``
object CPDM used to write. It is still accepted and replayed the old way:
headers first, then values, with no text rules.
"""

import io
import json

from cpdm.core import cleaning

RECIPE_FILENAME = "cleaning_rules.json"

OP_TEXT_RULES = "text_rules"
OP_HEADER_MAP = "header_map"
OP_VALUE_REPLACEMENTS = "value_replacements"
OP_EXACT_VALUES = "exact_values"


def export_rules(dataset):
    """Serialise the recorded rules as a downloadable JSON stream."""
    payload = json.dumps(dataset.cleaning_rules, indent=2, ensure_ascii=False)
    return io.BytesIO(payload.encode("utf-8")), RECIPE_FILENAME


def _replay_steps(dataset, steps):
    counts = {OP_TEXT_RULES: 0, OP_HEADER_MAP: 0,
              OP_VALUE_REPLACEMENTS: 0, OP_EXACT_VALUES: 0}
    headers_changed = 0
    cells_changed = 0

    for position, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise ValueError(f"Step {position} is not an object.")

        op = step.get("op")
        if op == OP_TEXT_RULES:
            result = cleaning.apply_text_rules(
                dataset,
                step.get("stage", cleaning.STAGE_VALUES),
                step.get("rules", []),
                step.get("columns"),
            )
            headers_changed += result.get("headers_changed", 0)
            cells_changed += result.get("cells_changed", 0)
        elif op == OP_HEADER_MAP:
            before = dict(dataset.cleaning_rules["header_map"])
            cleaning.update_headers(
                dataset, step.get("map", {}), step.get("ignored_columns")
            )
            headers_changed += len(dataset.cleaning_rules["header_map"]) - len(before)
        elif op == OP_VALUE_REPLACEMENTS:
            cleaning.apply_value_replacements(
                dataset, step.get("map", {}), step.get("columns")
            )
        elif op == OP_EXACT_VALUES:
            result = cleaning.replace_whole_cells(
                dataset, step.get("map", {}), step.get("columns")
            )
            cells_changed += result["cells_changed"]
        else:
            raise ValueError(f"Step {position} has an unknown operation '{op}'.")

        counts[op] += 1

    return {
        "version": 2,
        "steps_applied": len(steps),
        "text_rule_steps": counts[OP_TEXT_RULES],
        "headers_changed": headers_changed,
        "cells_changed": cells_changed,
    }


def _replay_flat(dataset, rules_data):
    header_map = rules_data.get("header_map", {})
    value_replacements = rules_data.get("value_replacements", {})
    ignored_cols = rules_data.get("ignored_columns", [])

    if header_map or ignored_cols:
        cleaning.update_headers(dataset, header_map, ignored_cols)

    if value_replacements:
        cleaning.apply_value_replacements(dataset, value_replacements)

    return {
        "version": 1,
        "headers_changed": len(header_map),
        "columns_replaced": len(value_replacements),
        "ignored_columns_count": len(ignored_cols),
    }


def apply_rules(dataset, rules_data):
    """Replay a saved recipe against the currently loaded dataset."""
    dataset.require_df()

    if not isinstance(rules_data, dict):
        raise ValueError("Cleaning file must contain a JSON object.")

    steps = rules_data.get("steps")
    if steps:
        if not isinstance(steps, list):
            raise ValueError("'steps' must be a list of operations.")
        result = _replay_steps(dataset, steps)
    else:
        result = _replay_flat(dataset, rules_data)

    result["cols"] = list(dataset.df.columns)
    # kept for the log line the browser prints
    result.setdefault("headers_changed", 0)
    result.setdefault("columns_replaced", len(rules_data.get("value_replacements", {})))
    result.setdefault("ignored_columns_count", len(rules_data.get("ignored_columns", [])))
    return result
