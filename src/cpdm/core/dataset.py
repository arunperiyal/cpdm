"""Session state: the working dataframe and everything derived from it.

A single :class:`Dataset` instance is shared by every request (see
:mod:`cpdm.core.state`). All transformation modules take that instance as their
first argument instead of holding state of their own.
"""

import pandas as pd

UNCATEGORISED = "Uncategorised"
DEMOGRAPHICS = "Demographics"
SCALE_PREFIX = "Scale: "
DEFAULT_SCALE = "General Scale"


def empty_cleaning_rules():
    return {"header_map": {}, "value_replacements": {}, "ignored_columns": []}


class Dataset:
    """The in-memory workbook plus its categorisation and cleaning recipe."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Return to the just-started state, keeping the object identity."""
        self.df = None
        self.filename = "dataset.xlsx"
        self.defined_scales = [DEFAULT_SCALE]
        self.categories = {}
        self.scoring_config = {}
        self.cleaning_rules = empty_cleaning_rules()

    # --- loading -------------------------------------------------------
    def load(self, df, filename):
        """Adopt a freshly read dataframe, discarding any previous session."""
        self.df = df
        self.filename = filename or "dataset.xlsx"
        self.categories = {col: UNCATEGORISED for col in df.columns}
        self.scoring_config = {}
        self.cleaning_rules = empty_cleaning_rules()
        return {"filename": self.filename, "rows": len(df), "cols": list(df.columns)}

    # --- guards & lookups ----------------------------------------------
    def require_df(self):
        if self.df is None:
            raise ValueError("No dataset loaded. Open a data file first.")
        return self.df

    @property
    def ignored_columns(self):
        return set(self.cleaning_rules.get("ignored_columns", []))

    def active_columns(self, extra_ignored=None):
        """Columns that bulk cleaning is allowed to touch."""
        skip = self.ignored_columns | set(extra_ignored or [])
        return [c for c in self.require_df().columns if c not in skip]

    def is_numeric(self, col):
        return pd.api.types.is_numeric_dtype(self.df[col])

    def scale_columns(self, scale_name=None):
        """Columns categorised under one scale, or under any scale."""
        if scale_name:
            target = SCALE_PREFIX + scale_name
            return [c for c, cat in self.categories.items() if cat == target]
        return [c for c, cat in self.categories.items() if cat.startswith(SCALE_PREFIX.strip())]

    def columns_by_category(self, category):
        return [c for c, cat in self.categories.items() if cat == category]

    def rename(self, rename_map):
        """Rename columns, carrying categories across to the new names.

        Categories are rebuilt from the live column list, so stale entries for
        dropped columns disappear and new columns default to Uncategorised.
        """
        new_categories = {}
        for col in self.df.columns:
            new_col = rename_map.get(col, col)
            new_categories[new_col] = self.categories.get(col, UNCATEGORISED)
        self.df = self.df.rename(columns=rename_map)
        self.categories = new_categories
        return list(self.df.columns)

    # --- reporting ------------------------------------------------------
    def has_cleaning_rules(self):
        rules = self.cleaning_rules
        return bool(
            rules["header_map"] or rules["value_replacements"] or rules["ignored_columns"]
        )

    def state(self):
        """The snapshot the browser polls before opening any dialogue."""
        return {
            "has_file": self.df is not None,
            "filename": self.filename if self.df is not None else None,
            "rows": int(len(self.df)) if self.df is not None else 0,
            "cols": list(self.df.columns) if self.df is not None else [],
            "categories": self.categories,
            "defined_scales": self.defined_scales,
            "ignored_columns": list(self.cleaning_rules.get("ignored_columns", [])),
            "has_cleaning_rules": self.has_cleaning_rules(),
        }
