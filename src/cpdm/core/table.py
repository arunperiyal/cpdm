"""Direct operations on the table: its header, rows, columns, order and filters.

Everything here changes the working dataframe in place and then puts the rest
of the session back in step — groups lose columns that no longer exist, and the
answers remembered for scored items follow their rows through a sort or a
filter, so scoring can still be redone afterwards.

Rows are addressed by their index label, not by their position on screen, so a
deletion cannot drift when the view is sorted or paged.
"""

import pandas as pd

from cpdm.core import groups

PAGE_SIZE = 25
MAX_PAGE_SIZE = 200

KEEP = "keep"
DROP = "drop"

MATCH_ALL = "all"
MATCH_ANY = "any"

#: operator -> label, shown in the Filter dialogue
OPERATORS = {
    "equals": "is",
    "not_equals": "is not",
    "contains": "contains",
    "not_contains": "does not contain",
    "starts_with": "starts with",
    "ends_with": "ends with",
    "greater_than": "is greater than",
    "greater_or_equal": "is at least",
    "less_than": "is less than",
    "less_or_equal": "is at most",
    "is_blank": "is blank",
    "not_blank": "is not blank",
}
NO_VALUE_OPERATORS = ("is_blank", "not_blank")


def _friendly_dtype(series):
    if pd.api.types.is_numeric_dtype(series):
        return "number"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"
    if pd.api.types.is_bool_dtype(series):
        return "yes/no"
    return "text"


def _cell(value):
    """A JSON-safe rendering of one cell."""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float, str, bool)):
        return value
    return str(value)


# --- looking at it --------------------------------------------------------
def page(dataset, offset=0, limit=PAGE_SIZE, columns=None):
    """One screenful of rows, with the index labels that identify them."""
    df = dataset.require_df()

    limit = max(1, min(int(limit or PAGE_SIZE), MAX_PAGE_SIZE))
    offset = max(0, min(int(offset or 0), max(0, len(df) - 1)))

    shown = [col for col in (columns or df.columns) if col in df.columns]
    window = df.iloc[offset:offset + limit]

    return {
        "columns": [str(col) for col in shown],
        "index": [str(label) for label in window.index],
        "rows": [[_cell(value) for value in row] for row in window[shown].to_numpy()],
        "offset": offset,
        "limit": limit,
        "total": int(len(df)),
    }


def column_report(dataset):
    """Per column: where it sits, what it holds, and what it belongs to."""
    df = dataset.require_df()
    report = []

    for position, col in enumerate(df.columns, start=1):
        series = df[col]
        filled = int(series.notna().sum())
        group = groups.group_of(dataset, col)
        report.append({
            "position": position,
            "name": str(col),
            "dtype": _friendly_dtype(series),
            "filled": filled,
            "blank": int(len(series) - filled),
            "distinct": int(series.nunique(dropna=True)),
            "group": group,
            "scale": dataset.categories.get(col, "").replace("Scale: ", "") or None,
        })
    return report


MAX_UNIQUE = 200


def unique_values(dataset, columns, limit=MAX_UNIQUE):
    """The distinct values of each column, numbered.

    The numbering is a property of the column, not of the last thing printed:
    it is recomputed the same way every time, so ``unique 10`` and a later
    ``map values 10 unique 2`` agree even if other commands ran in between, or
    the listing was printed in another browser.

    Numbers sort numerically, anything else alphabetically without regard to
    case, which is the order that is easiest to find a value in.
    """
    dataset.require_df()

    report = []
    for name in columns:
        if name not in dataset.df.columns:
            raise ValueError(f"No column named '{name}'.")

        series = dataset.df[name]
        counts = series.dropna().astype(str).str.strip()
        counts = counts[counts != ""].value_counts()

        numbers = {label: _as_number(label) for label in counts.index}
        if counts.index.size and all(value is not None for value in numbers.values()):
            order = sorted(counts.index, key=lambda label: numbers[label])
        else:
            order = sorted(counts.index, key=lambda label: label.lower())

        values = [
            {"n": position, "value": label, "count": int(counts[label])}
            for position, label in enumerate(order[:limit], start=1)
        ]
        report.append({
            "column": str(name),
            "values": values,
            "distinct": int(counts.index.size),
            "blank": int(len(series) - counts.sum()),
            "truncated": counts.index.size > limit,
        })

    return report


def unique_value_at(dataset, column, number):
    """The nth value of a column's numbered list, as ``unique`` printed it."""
    listing = unique_values(dataset, [column])[0]
    for entry in listing["values"]:
        if entry["n"] == number:
            return entry["value"]

    raise ValueError(
        f"'{column}' has {listing['distinct']} distinct value(s); there is no number "
        f"{number}. Run 'unique' on that column to see the list."
    )


def _as_number(label):
    try:
        value = float(label)
    except (TypeError, ValueError):
        return None
    return value


# --- the header row -------------------------------------------------------
def rename_columns(dataset, mapping):
    """Rename columns outright, refusing anything that would collide."""
    df = dataset.require_df()

    wanted = {}
    for old, new in (mapping or {}).items():
        new = str(new).strip()
        if not new or old == new:
            continue
        if old not in df.columns:
            raise ValueError(f"No column named '{old}'.")
        wanted[old] = new

    if not wanted:
        return {"renamed": 0, "columns": [str(c) for c in df.columns]}

    resulting = [wanted.get(col, col) for col in df.columns]
    duplicates = sorted({name for name in resulting if resulting.count(name) > 1})
    if duplicates:
        raise ValueError("These names would be used twice: " + ", ".join(duplicates))

    dataset.rename(wanted)
    for old, new in wanted.items():
        dataset.cleaning_rules["header_map"][old] = new
    dataset.record_step("header_map", map=wanted)

    return {"renamed": len(wanted), "columns": [str(c) for c in dataset.df.columns]}


# --- columns --------------------------------------------------------------
def reorder_columns(dataset, order):
    """Put the columns in the order given; anything unnamed keeps its place."""
    df = dataset.require_df()

    wanted = [col for col in (order or []) if col in df.columns]
    if not wanted:
        raise ValueError("No known columns in that order.")

    rest = [col for col in df.columns if col not in set(wanted)]
    dataset.df = df[wanted + rest]
    return [str(col) for col in dataset.df.columns]


def drop_columns(dataset, names):
    """Delete columns and their data, tidying the groups they belonged to."""
    df = dataset.require_df()

    doomed = [col for col in (names or []) if col in df.columns]
    if not doomed:
        raise ValueError("None of those columns exist.")
    if len(doomed) == len(df.columns):
        raise ValueError("That would delete every column.")

    dataset.df = df.drop(columns=doomed)
    dataset.remap_groups()          # groups and scale keying lose them
    dataset.forget_answers(doomed)
    for col in doomed:
        dataset.categories.pop(col, None)

    return {"dropped": [str(col) for col in doomed],
            "columns": [str(col) for col in dataset.df.columns]}


# --- rows -----------------------------------------------------------------
def _after_row_change(dataset):
    """Keep the remembered answers lined up with the rows that remain."""
    dataset.sync_answers()


def drop_rows(dataset, labels):
    """Delete rows by index label, which is what the table view sends back."""
    df = dataset.require_df()

    wanted = {str(label) for label in (labels or [])}
    keep = [label for label in df.index if str(label) not in wanted]
    removed = len(df) - len(keep)
    if not removed:
        raise ValueError("No rows matched.")

    dataset.df = df.loc[keep]
    _after_row_change(dataset)
    return {"removed": removed, "rows": int(len(dataset.df))}


def drop_blank_rows(dataset):
    """Remove rows that hold nothing at all."""
    df = dataset.require_df()
    before = len(df)
    dataset.df = df.dropna(how="all")
    _after_row_change(dataset)
    return {"removed": before - len(dataset.df), "rows": int(len(dataset.df))}


def drop_duplicate_rows(dataset, columns=None, keep="first"):
    """Remove repeat rows, judged on every column or just the ones given."""
    df = dataset.require_df()

    subset = [col for col in (columns or []) if col in df.columns] or None
    before = len(df)
    dataset.df = df.drop_duplicates(subset=subset, keep=keep)
    _after_row_change(dataset)
    return {
        "removed": before - len(dataset.df),
        "rows": int(len(dataset.df)),
        # only worth echoing when it was narrowed; otherwise it is every column
        "judged_on": [str(col) for col in subset] if subset else "every column",
    }


# --- sorting --------------------------------------------------------------
def sort_rows(dataset, keys):
    """Sort by one or more columns; text sorts case-insensitively."""
    df = dataset.require_df()

    columns = []
    ascending = []
    for key in keys or []:
        name = key.get("column") if isinstance(key, dict) else key
        if name not in df.columns:
            raise ValueError(f"No column named '{name}'.")
        columns.append(name)
        ascending.append(not (isinstance(key, dict) and key.get("descending")))

    if not columns:
        raise ValueError("Choose at least one column to sort by.")

    def sort_key(series):
        if pd.api.types.is_numeric_dtype(series):
            return series
        return series.astype(str).str.lower()

    dataset.df = df.sort_values(
        by=columns, ascending=ascending, key=sort_key, kind="stable"
    )
    _after_row_change(dataset)
    return {"sorted_by": [
        {"column": str(col), "descending": not asc}
        for col, asc in zip(columns, ascending)
    ]}


# --- filtering ------------------------------------------------------------
def _condition_mask(dataset, condition):
    df = dataset.df
    column = condition.get("column")
    operator = condition.get("operator", "equals")
    value = condition.get("value", "")

    if column not in df.columns:
        raise ValueError(f"No column named '{column}'.")
    if operator not in OPERATORS:
        raise ValueError(f"Unknown test '{operator}'.")

    series = df[column]

    if operator == "is_blank":
        return series.isna() | series.astype(str).str.strip().eq("")
    if operator == "not_blank":
        return ~(series.isna() | series.astype(str).str.strip().eq(""))

    if operator in ("greater_than", "greater_or_equal", "less_than", "less_or_equal"):
        numbers = pd.to_numeric(series, errors="coerce")
        try:
            threshold = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"'{value}' is not a number.") from None
        if operator == "greater_than":
            return numbers > threshold
        if operator == "greater_or_equal":
            return numbers >= threshold
        if operator == "less_than":
            return numbers < threshold
        return numbers <= threshold

    text = series.astype(str).str.strip().str.lower()
    needle = str(value).strip().lower()

    if operator == "equals":
        return text.eq(needle)
    if operator == "not_equals":
        return ~text.eq(needle)
    if operator == "contains":
        return text.str.contains(needle, regex=False, na=False)
    if operator == "not_contains":
        return ~text.str.contains(needle, regex=False, na=False)
    if operator == "starts_with":
        return text.str.startswith(needle, na=False)
    return text.str.endswith(needle, na=False)


def _combined_mask(dataset, conditions, match=MATCH_ALL):
    dataset.require_df()
    if not conditions:
        raise ValueError("Add at least one test.")

    masks = [_condition_mask(dataset, condition) for condition in conditions]
    combined = masks[0]
    for mask in masks[1:]:
        combined = (combined & mask) if match == MATCH_ALL else (combined | mask)
    return combined


def count_matches(dataset, conditions, match=MATCH_ALL):
    """How many rows the tests pick out — shown before anything is deleted."""
    mask = _combined_mask(dataset, conditions, match)
    matched = int(mask.sum())
    return {"matched": matched, "total": int(len(dataset.df)),
            "remaining_if_kept": matched,
            "remaining_if_dropped": int(len(dataset.df)) - matched}


def filter_rows(dataset, conditions, match=MATCH_ALL, action=KEEP):
    """Keep or drop the rows the tests pick out."""
    mask = _combined_mask(dataset, conditions, match)
    if action not in (KEEP, DROP):
        raise ValueError("Choose whether to keep or drop the matching rows.")

    before = int(len(dataset.df))
    dataset.df = dataset.df[mask] if action == KEEP else dataset.df[~mask]
    _after_row_change(dataset)

    return {
        "action": action,
        "matched": int(mask.sum()),
        "removed": before - int(len(dataset.df)),
        "rows": int(len(dataset.df)),
    }
