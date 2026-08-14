"""Saving and replaying a cleaning recipe (header map + value replacements)."""

import io
import json

from cpdm.core import cleaning

RECIPE_FILENAME = "cleaning_rules.json"


def export_rules(dataset):
    """Serialise the recorded rules as a downloadable JSON stream."""
    payload = json.dumps(dataset.cleaning_rules, indent=2, ensure_ascii=False)
    return io.BytesIO(payload.encode("utf-8")), RECIPE_FILENAME


def apply_rules(dataset, rules_data):
    """Replay a saved recipe against the currently loaded dataset."""
    dataset.require_df()

    if not isinstance(rules_data, dict):
        raise ValueError("Cleaning file must contain a JSON object.")

    header_map = rules_data.get("header_map", {})
    value_replacements = rules_data.get("value_replacements", {})
    ignored_cols = rules_data.get("ignored_columns", [])

    if header_map or ignored_cols:
        cleaning.update_headers(dataset, header_map, ignored_cols)

    if value_replacements:
        cleaning.apply_value_replacements(dataset, value_replacements)

    return {
        "cols": list(dataset.df.columns),
        "headers_changed": len(header_map),
        "columns_replaced": len(value_replacements),
        "ignored_columns_count": len(ignored_cols),
    }
