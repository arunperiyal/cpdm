"""Cleaning operations: header mapping, value replacement, text trimming.

Every rename and replacement is also recorded in ``dataset.cleaning_rules`` so
the session can be exported as a reusable recipe (see :mod:`cpdm.core.recipes`).
"""

import pandas as pd

from cpdm.core import text_rules

MISSING_TOKENS = {"nan", "none", "null", "na", "n/a"}


# --- headers ------------------------------------------------------------
def update_headers(dataset, header_map, ignored_cols=None):
    """Rename columns from a {old: new} map and store the ignored-column list.

    Ignored columns are stored under their *new* names: the browser sends the
    names it displayed, which are the pre-rename ones, and a column that is
    renamed and deselected in the same step must still count as ignored.
    """
    dataset.require_df()

    rename_map = {}
    for old_col in dataset.df.columns:
        new_col = str(header_map.get(old_col, old_col)).strip() or old_col
        if new_col != old_col:
            rename_map[old_col] = new_col
            dataset.cleaning_rules["header_map"][old_col] = new_col

    if ignored_cols is not None:
        dataset.cleaning_rules["ignored_columns"] = [
            rename_map.get(col, col) for col in ignored_cols
        ]

    return dataset.rename(rename_map)


# --- unique text values -------------------------------------------------
def _is_missing(text):
    return not text or text.lower() in MISSING_TOKENS


def _looks_numeric(text):
    try:
        float(text)
    except ValueError:
        return False
    return True


def _already_mapped(dataset):
    """Every source value and target value recorded so far, in any column."""
    mapped = set()
    for col_map in dataset.cleaning_rules.get("value_replacements", {}).values():
        if isinstance(col_map, dict):
            mapped.update(col_map.keys())
            mapped.update(col_map.values())
    return mapped


def unique_text_values(dataset, ignored_cols=None):
    """Distinct unmapped text values across the active columns, with locations."""
    dataset.require_df()

    columns = dataset.active_columns(extra_ignored=ignored_cols)
    mapped = _already_mapped(dataset)
    found = {}

    for col in columns:
        series = dataset.df[col].dropna()
        if pd.api.types.is_numeric_dtype(series):
            continue

        for value in series:
            text = str(value).strip()
            if _is_missing(text) or _looks_numeric(text) or text in mapped:
                continue
            found.setdefault(text, set()).add(col)

    return {
        "uniques": [
            {"value": value, "columns": sorted(cols)}
            for value, cols in sorted(found.items())
        ]
    }


# --- value replacement --------------------------------------------------
def _flatten_replacements(dataset, replacements):
    """Accept both {'old': 'new'} and {'Column': {'old': 'new'}} payloads."""
    flat = {}
    if not isinstance(replacements, dict):
        return flat

    recorded = dataset.cleaning_rules["value_replacements"]
    for key, value in replacements.items():
        if isinstance(value, dict):
            flat.update(value)
            recorded.setdefault(key, {}).update(value)
        elif isinstance(value, str):
            flat[key] = value
            recorded.setdefault("_global", {})[key] = value
    return flat


def apply_value_replacements(dataset, replacements):
    """Replace text literally (not as regex) across every active text column."""
    dataset.require_df()

    value_map = _flatten_replacements(dataset, replacements)
    if not value_map:
        return 0

    # Longest source first: otherwise mapping "Agree" would eat the tail of
    # "Strongly Agree" before its own rule ever runs.
    ordered = sorted(value_map.items(), key=lambda item: len(item[0]), reverse=True)

    changed = 0
    for col in dataset.active_columns():
        if dataset.is_numeric(col):
            continue
        series = dataset.df[col].astype(str)
        for old_value, new_value in ordered:
            series = series.str.replace(old_value, new_value, regex=False)
        dataset.df[col] = series
        changed += 1

    return changed


# --- text trimming ------------------------------------------------------
def trim_values(dataset, mode, delimiter="", exempt_cols=None):
    """Apply one trimming rule to the cell values of every active text column."""
    dataset.require_df()
    text_rules.validate(mode, delimiter)

    processed = 0
    for col in dataset.active_columns(extra_ignored=exempt_cols):
        if dataset.is_numeric(col):
            continue
        dataset.df[col] = dataset.df[col].apply(
            lambda value: text_rules.apply_mode_to_cell(value, mode, delimiter)
        )
        processed += 1

    return processed


def trim_headers(dataset, mode, delimiter="", exempt_cols=None):
    """Apply one trimming rule to the column headers, avoiding name collisions."""
    dataset.require_df()
    text_rules.validate(mode, delimiter)

    exempt = set(exempt_cols or [])
    rename_map = {}
    taken = set()

    for col in dataset.df.columns:
        if col in exempt:
            taken.add(col)
            continue

        new_col = text_rules.apply_mode(str(col), mode, delimiter).strip() or col
        base, counter = new_col, 1
        while new_col in taken and new_col != col:
            new_col = f"{base}_{counter}"
            counter += 1

        if new_col != col:
            rename_map[col] = new_col
            dataset.cleaning_rules["header_map"][col] = new_col
        taken.add(new_col)

    dataset.rename(rename_map)
    return len(rename_map)


def scrub_non_english(dataset, header_cfg=None, value_cfg=None, exempt_cols=None):
    """Run independent header and value trimming rules in one pass."""
    dataset.require_df()

    header_cfg = header_cfg or {}
    value_cfg = value_cfg or {}
    exempt_cols = list(exempt_cols or [])

    header_mode = header_cfg.get("mode", text_rules.MODE_NONE)
    value_mode = value_cfg.get("mode", text_rules.MODE_NONE)

    if header_mode == text_rules.MODE_NONE and value_mode == text_rules.MODE_NONE:
        raise ValueError("Select at least one cleaning rule for headers or values.")

    headers_changed = 0
    if header_mode != text_rules.MODE_NONE:
        headers_changed = trim_headers(
            dataset, header_mode, header_cfg.get("delimiter", ""), exempt_cols
        )

    columns_cleaned = 0
    if value_mode != text_rules.MODE_NONE:
        columns_cleaned = trim_values(
            dataset, value_mode, value_cfg.get("delimiter", ""), exempt_cols
        )

    return {
        "headers_changed": headers_changed,
        "columns_cleaned": columns_cleaned,
        "exempt_columns_count": len(exempt_cols),
    }

