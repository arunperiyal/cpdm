"""Session state: the working dataframe and everything derived from it.

A single :class:`Dataset` instance is shared by every request (see
:mod:`cpdm.core.state`). All transformation modules take that instance as their
first argument instead of holding state of their own.
"""

import pandas as pd

UNCATEGORISED = "Uncategorised"
DEMOGRAPHICS = "Demographics"
SCALE_PREFIX = "Scale: "

#: what a group represents. Any group at any depth can be a scale: a container
#: group can hold several scales, and a scale can hold sub-scales. Plain
#: containers organise columns without claiming them for scoring.
KIND_SCALE = "scale"
KIND_DEMOGRAPHICS = "demographics"
KIND_OTHER = "other"
KINDS = (KIND_SCALE, KIND_DEMOGRAPHICS, KIND_OTHER)

KIND_LABELS = {
    KIND_SCALE: "Scale",
    KIND_DEMOGRAPHICS: "Demographics",
    KIND_OTHER: "Container",
}


#: recipe schema version. v1 was the flat header_map / value_replacements /
#: ignored_columns object; v2 adds an ordered ``steps`` log, which is what makes
#: a replay reproduce trim-then-rename in the order it actually happened.
RECIPE_VERSION = 2


def empty_cleaning_rules():
    return {
        "version": RECIPE_VERSION,
        "steps": [],
        "header_map": {},
        "value_replacements": {},
        "ignored_columns": [],
    }


class Dataset:
    """The in-memory workbook plus its categorisation and cleaning recipe."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Return to the just-started state, keeping the object identity."""
        self.df = None
        self.filename = "dataset.xlsx"
        self.categories = {}
        self.groups = []
        self.scoring_config = {}
        self.cleaning_rules = empty_cleaning_rules()

    # --- loading -------------------------------------------------------
    def load(self, df, filename):
        """Adopt a freshly read dataframe, discarding any previous session."""
        self.df = df
        self.filename = filename or "dataset.xlsx"
        self.categories = {col: UNCATEGORISED for col in df.columns}
        self.groups = []
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

    @property
    def defined_scales(self):
        """Every group marked as a scale, at any depth in the tree."""
        return [group["name"] for group in self.groups if group["kind"] == KIND_SCALE]

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
        self.remap_groups(rename_map)
        return list(self.df.columns)

    def remap_groups(self, rename_map=None):
        """Follow renames into the group tree and drop columns that are gone."""
        live = set(self.df.columns) if self.df is not None else set()
        for group in self.groups:
            renamed = [(rename_map or {}).get(col, col) for col in group["columns"]]
            group["columns"] = [col for col in renamed if col in live]
        return self.groups

    # --- recipe ----------------------------------------------------------
    def record_step(self, op, **fields):
        """Append one operation to the ordered recipe log."""
        step = {"op": op}
        step.update({key: value for key, value in fields.items() if value is not None})
        self.cleaning_rules.setdefault("steps", []).append(step)
        return step

    # --- reporting ------------------------------------------------------
    def has_cleaning_rules(self):
        rules = self.cleaning_rules
        return bool(
            rules.get("steps")
            or rules["header_map"]
            or rules["value_replacements"]
            or rules["ignored_columns"]
        )

    def state(self):
        """The snapshot the browser polls before opening any dialogue."""
        return {
            "has_file": self.df is not None,
            "filename": self.filename if self.df is not None else None,
            "rows": int(len(self.df)) if self.df is not None else 0,
            "cols": list(self.df.columns) if self.df is not None else [],
            "numeric_columns": (
                [c for c in self.df.columns if self.is_numeric(c)]
                if self.df is not None else []
            ),
            "categories": self.categories,
            "groups": self.groups,
            "defined_scales": self.defined_scales,
            "ignored_columns": list(self.cleaning_rules.get("ignored_columns", [])),
            "has_cleaning_rules": self.has_cleaning_rules(),
        }
