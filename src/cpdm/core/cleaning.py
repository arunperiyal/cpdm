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

    resolved_ignored = None
    if ignored_cols is not None:
        resolved_ignored = [rename_map.get(col, col) for col in ignored_cols]
        dataset.cleaning_rules["ignored_columns"] = resolved_ignored

    if rename_map or resolved_ignored is not None:
        dataset.record_step("header_map", map=rename_map, ignored_columns=resolved_ignored)

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

    dataset.record_step("value_replacements", map=dict(value_map))

    # Longest source first: otherwise mapping "Agree" would eat the tail of
    # "Strongly Agree" before its own rule ever runs.
    ordered = sorted(value_map.items(), key=lambda item: len(item[0]), reverse=True)

    changed = 0
    for col in dataset.active_columns():
        if dataset.is_numeric(col):
            continue

        series = dataset.df[col]
        present = series.notna()          # keep blanks blank: astype(str) would
        text = series[present].astype(str)  # otherwise write the literal "nan"
        for old_value, new_value in ordered:
            text = text.str.replace(old_value, new_value, regex=False)

        updated = series.astype(object).copy()
        updated[present] = text
        dataset.df[col] = updated
        changed += 1

    return changed


# --- text trimming ------------------------------------------------------
STAGE_HEADERS = "headers"
STAGE_VALUES = "values"
STAGES = (STAGE_HEADERS, STAGE_VALUES)

PREVIEW_ROW_CAP = 5000
PREVIEW_EXAMPLES = 5


def _validate_stage(stage):
    if stage not in STAGES:
        raise ValueError(f"Unknown stage '{stage}'. Expected one of: {', '.join(STAGES)}")
    return stage


def target_columns(dataset, stage, columns=None):
    """Which columns a stage may touch.

    ``columns=None`` keeps the pre-wizard defaults: every column for headers,
    the active (non-ignored) ones for values. An explicit selection is honoured
    as given, minus columns that no longer exist and — for values — numeric
    ones, which have no text to trim.
    """
    df = dataset.require_df()
    _validate_stage(stage)

    if columns is None:
        candidates = list(df.columns) if stage == STAGE_HEADERS else dataset.active_columns()
    else:
        selected = set(columns)
        candidates = [col for col in df.columns if col in selected]

    if stage == STAGE_VALUES:
        candidates = [col for col in candidates if not dataset.is_numeric(col)]
    return candidates


def _planned_renames(dataset, rules, columns=None):
    """Work out the header renames without touching the dataframe.

    Shared by preview and apply so that what you see is what you get, including
    the de-duplication suffixes.
    """
    targets = set(target_columns(dataset, STAGE_HEADERS, columns))
    rename_map = {}
    rows = []
    taken = set()

    for col in dataset.df.columns:
        name = str(col)
        if col not in targets:
            taken.add(col)
            rows.append({"column": name, "before": name, "after": name,
                         "changed": False, "warning": ""})
            continue

        warning = ""
        new_col = text_rules.apply_chain(name, rules).strip()
        if not new_col:
            new_col = col
            warning = "the rules empty this header, so the original is kept"

        base, counter = new_col, 1
        while new_col in taken and new_col != col:
            new_col = f"{base}_{counter}"
            counter += 1
        if new_col != base:
            warning = f"'{base}' is already taken, so this becomes '{new_col}'"

        if new_col != col:
            rename_map[col] = new_col
        taken.add(new_col)
        rows.append({"column": name, "before": name, "after": str(new_col),
                     "changed": new_col != col, "warning": warning})

    return rename_map, rows


def _changed_mask(original, cleaned):
    """Elementwise inequality that does not count NaN != NaN as a change."""
    return (original != cleaned) & ~(original.isna() & cleaned.isna())


def apply_text_rules(dataset, stage, rules, columns=None):
    """Run a chain of trimming rules over the headers or the cell values."""
    dataset.require_df()
    _validate_stage(stage)
    chain = text_rules.normalise_chain(rules)

    if stage == STAGE_HEADERS:
        rename_map, _ = _planned_renames(dataset, chain, columns)
        for old_col, new_col in rename_map.items():
            dataset.cleaning_rules["header_map"][old_col] = new_col
        dataset.rename(rename_map)
        result = {"headers_changed": len(rename_map), "renames": rename_map}
    else:
        columns_cleaned = 0
        cells_changed = 0
        for col in target_columns(dataset, STAGE_VALUES, columns):
            original = dataset.df[col]
            cleaned = original.apply(
                lambda value: text_rules.apply_chain_to_cell(value, chain)
            )
            changed = int(_changed_mask(original, cleaned).sum())
            if changed:
                dataset.df[col] = cleaned
                cells_changed += changed
            columns_cleaned += 1
        result = {"columns_cleaned": columns_cleaned, "cells_changed": cells_changed}

    dataset.record_step("text_rules", stage=stage, rules=chain,
                        columns=list(columns) if columns is not None else None)
    result["description"] = text_rules.describe_chain(chain)
    return result


def preview_text_rules(dataset, stage, rules, columns=None):
    """Show what :func:`apply_text_rules` would do. Never mutates the dataset."""
    dataset.require_df()
    _validate_stage(stage)
    chain = text_rules.normalise_chain(rules)

    if stage == STAGE_HEADERS:
        _, rows = _planned_renames(dataset, chain, columns)
        return {
            "stage": stage,
            "description": text_rules.describe_chain(chain),
            "rows": rows,
            "columns_scanned": len(rows),
            "columns_affected": sum(1 for row in rows if row["changed"]),
            "warnings": [row["warning"] for row in rows if row["warning"]],
            "truncated": False,
        }

    rows = []
    cells_changed = 0
    truncated = False

    for col in target_columns(dataset, STAGE_VALUES, columns):
        original = dataset.df[col]
        if len(original) > PREVIEW_ROW_CAP:
            original = original.head(PREVIEW_ROW_CAP)
            truncated = True

        cleaned = original.apply(lambda value: text_rules.apply_chain_to_cell(value, chain))
        mask = _changed_mask(original, cleaned)
        changed = int(mask.sum())
        cells_changed += changed

        examples = []
        seen = set()
        for before, after in zip(original[mask], cleaned[mask]):
            if before in seen:
                continue
            seen.add(before)
            examples.append({"before": str(before), "after": str(after)})
            if len(examples) >= PREVIEW_EXAMPLES:
                break

        rows.append({
            "column": str(col),
            "cells_changed": changed,
            "cells_total": int(len(original)),
            "changed": changed > 0,
            "examples": examples,
        })

    return {
        "stage": stage,
        "description": text_rules.describe_chain(chain),
        "rows": rows,
        "columns_scanned": len(rows),
        "columns_affected": sum(1 for row in rows if row["changed"]),
        "cells_changed": cells_changed,
        "warnings": [],
        "truncated": truncated,
    }


# --- leftovers: what the rules could not catch -----------------------------
MAX_LEFTOVER_VALUES = 300


def find_leftovers(dataset, columns=None, strict_ascii=False):
    """Headers and cell values that still hold non-English characters.

    A rule chain handles the regular cases; whatever is left is usually a
    handful of oddities worth fixing by hand, which is what stage 3 is for.
    """
    dataset.require_df()
    targets = target_columns(dataset, STAGE_VALUES, columns)

    headers = []
    for col in dataset.df.columns:
        marks = text_rules.non_english_chars(str(col), strict_ascii)
        if marks:
            headers.append({"column": str(col), "marks": marks})

    found = {}
    truncated = False
    for col in targets:
        for value in dataset.df[col].dropna():
            text = str(value).strip()
            if not text or text in found:
                if text in found:
                    found[text]["count"] += 1
                    found[text]["columns"].add(col)
                continue
            if not text_rules.non_english_chars(text, strict_ascii):
                continue
            if len(found) >= MAX_LEFTOVER_VALUES:
                truncated = True
                break
            found[text] = {
                "count": 1,
                "columns": {col},
                "marks": text_rules.non_english_chars(text, strict_ascii),
            }
        if truncated:
            break

    values = [
        {
            "value": text,
            "count": entry["count"],
            "columns": sorted(entry["columns"]),
            "marks": entry["marks"],
        }
        for text, entry in sorted(found.items())
    ]

    return {
        "headers": headers,
        "values": values,
        "columns_scanned": len(targets),
        "truncated": truncated,
    }


def replace_whole_cells(dataset, replacements, columns=None):
    """Replace cells that match a value exactly, not as a substring.

    This is the manual counterpart to the value-replacement wizard: it touches
    only cells that hold precisely the value given, so a fix for one stray
    answer cannot bleed into a longer one that contains it.
    """
    dataset.require_df()

    mapping = {
        str(old).strip(): str(new)
        for old, new in (replacements or {}).items()
        if str(old).strip() and str(old).strip() != str(new)
    }
    if not mapping:
        return {"cells_changed": 0, "columns_changed": 0}

    targets = target_columns(dataset, STAGE_VALUES, columns)
    cells = 0
    touched = 0

    for col in targets:
        series = dataset.df[col]
        stripped = series.apply(lambda v: None if pd.isna(v) else str(v).strip())
        mask = stripped.isin(mapping.keys())
        hits = int(mask.sum())
        if not hits:
            continue
        updated = series.astype(object).copy()
        updated[mask] = stripped[mask].map(mapping)
        dataset.df[col] = updated
        cells += hits
        touched += 1

    dataset.record_step("exact_values", map=mapping,
                        columns=list(columns) if columns is not None else None)
    return {"cells_changed": cells, "columns_changed": touched}


def fix_leftovers(dataset, headers=None, values=None, columns=None):
    """Apply hand-written fixes to the headers and values stage 3 listed."""
    dataset.require_df()

    renamed = 0
    if headers:
        wanted = {old: new for old, new in headers.items() if new and new != old}
        if wanted:
            before = list(dataset.df.columns)
            update_headers(dataset, wanted)
            renamed = sum(1 for old, new in zip(before, dataset.df.columns) if old != new)

    replaced = replace_whole_cells(dataset, values, columns) if values else {
        "cells_changed": 0, "columns_changed": 0}

    return {
        "headers_renamed": renamed,
        "cells_changed": replaced["cells_changed"],
        "columns_changed": replaced["columns_changed"],
    }


# --- adapters for the pre-chain API ---------------------------------------
def trim_values(dataset, mode, delimiter="", exempt_cols=None):
    """Apply a single trimming rule to the active text columns."""
    columns = None
    if exempt_cols:
        exempt = set(exempt_cols)
        columns = [c for c in dataset.active_columns() if c not in exempt]

    result = apply_text_rules(
        dataset, STAGE_VALUES, [text_rules.rule_from_mode(mode, delimiter)], columns
    )
    return result["columns_cleaned"]


def trim_headers(dataset, mode, delimiter="", exempt_cols=None):
    """Apply a single trimming rule to the column headers."""
    columns = None
    if exempt_cols:
        exempt = set(exempt_cols)
        columns = [c for c in dataset.df.columns if c not in exempt]

    result = apply_text_rules(
        dataset, STAGE_HEADERS, [text_rules.rule_from_mode(mode, delimiter)], columns
    )
    return result["headers_changed"]


def scrub_non_english(dataset, header_cfg=None, value_cfg=None, exempt_cols=None):
    """Run independent header and value rules in one pass (pre-wizard API)."""
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

