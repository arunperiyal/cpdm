"""Session state: the working dataframe and everything derived from it.

A single :class:`Dataset` instance is shared by every request (see
:mod:`cpdm.core.state`). All transformation modules take that instance as their
first argument instead of holding state of their own.
"""

import pandas as pd

UNCATEGORISED = "Uncategorised"
SCALE_PREFIX = "Scale: "


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
    """The in-memory workbook plus its groups, scales and cleaning recipe.

    Groups and scales are separate things. ``groups`` is a tree of named column
    sets and says nothing about analysis; ``scales`` names the groups whose
    columns are to be scored together. ``categories`` is derived from the two
    and is what Scoring, Numerise and Compute read.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """Return to the just-started state, keeping the object identity."""
        self.df = None
        self.filename = "dataset.xlsx"
        self.categories = {}
        self.groups = []
        self.scales = []
        self.answers = {}
        self.cleaning_rules = empty_cleaning_rules()

    # --- loading -------------------------------------------------------
    def load(self, df, filename):
        """Adopt a freshly read dataframe, discarding any previous session."""
        self.df = df
        self.filename = filename or "dataset.xlsx"
        self.categories = {col: UNCATEGORISED for col in df.columns}
        self.groups = []
        self.scales = []
        self.answers = {}
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
        return [scale["name"] for scale in self.scales]

    # --- the group tree ---------------------------------------------------
    def find_group(self, name):
        for group in self.groups:
            if group["name"] == name:
                return group
        return None

    def group_depth(self, group):
        """How far below a root a group sits (0 for a root)."""
        steps = 0
        seen = {group["name"]}
        while group["parent"]:
            group = self.find_group(group["parent"])
            if group is None or group["name"] in seen:
                break
            seen.add(group["name"])
            steps += 1
        return steps

    def refresh_categories(self):
        """Recompute ``categories`` from the groups and the scales on them.

        A column takes the scale of the **deepest** group holding it that has
        one, so a scale defined on a subgroup wins over one on the group above.
        """
        if self.df is None:
            return self.categories

        categories = {col: UNCATEGORISED for col in self.df.columns}

        def depth(scale):
            group = self.find_group(scale["group"])
            return self.group_depth(group) if group else -1

        for scale in sorted(self.scales, key=depth):  # shallow first
            group = self.find_group(scale["group"])
            if group is None:
                continue
            for col in group["columns"]:
                if col in categories:
                    categories[col] = SCALE_PREFIX + scale["name"]

        self.categories = categories
        return categories

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
        """Follow renames into the groups and scales; drop columns that are gone."""
        live = set(self.df.columns) if self.df is not None else set()
        rename_map = rename_map or {}

        for group in self.groups:
            renamed = [rename_map.get(col, col) for col in group["columns"]]
            group["columns"] = [col for col in renamed if col in live]

        self.answers = {
            rename_map.get(col, col): values
            for col, values in self.answers.items()
            if rename_map.get(col, col) in live
        }

        # a scale's per-item scoring types are keyed by column name
        for scale in self.scales:
            items = scale.get("items", {})
            scale["items"] = {
                rename_map.get(col, col): cfg
                for col, cfg in items.items()
                if rename_map.get(col, col) in live
            }

        self.refresh_categories()
        return self.groups

    # --- the answers behind a scored column -------------------------------
    def keep_answers(self, column):
        """Remember a column's answers the first time it is scored.

        Scoring then always works from these rather than from whatever is in
        the column now, so it can be redone as often as you like: change a
        score, change a keying, and the column is recomputed from the answers
        instead of from the numbers the last pass left behind.
        """
        if column not in self.answers:
            self.answers[column] = self.df[column].copy()
        return self.answers[column]

    def answers_for(self, column):
        """The original answers if the column has been scored, else the column."""
        if column in self.answers:
            return self.answers[column]
        return self.df[column] if column in self.df.columns else None

    def forget_answers(self, columns=None):
        """Drop remembered answers so the current values are read afresh."""
        if columns is None:
            self.answers = {}
            return
        for column in columns:
            self.answers.pop(column, None)

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
            "scales": self.scales,
            "defined_scales": self.defined_scales,
            "ignored_columns": list(self.cleaning_rules.get("ignored_columns", [])),
            "has_cleaning_rules": self.has_cleaning_rules(),
        }
