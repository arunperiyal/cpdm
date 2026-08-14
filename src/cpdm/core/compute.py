"""Row-wise statistics across selected scale items."""

import pandas as pd

from cpdm.core.dataset import UNCATEGORISED

FUNCTIONS = {
    "mean": lambda frame: frame.mean(axis=1),
    "sum": lambda frame: frame.sum(axis=1),
    "min": lambda frame: frame.min(axis=1),
    "max": lambda frame: frame.max(axis=1),
    "std": lambda frame: frame.std(axis=1),
}


def row_statistic(dataset, new_col_name, function_name, selected_cols):
    """Add a new column holding a row-wise statistic over the chosen columns."""
    dataset.require_df()

    new_col_name = (new_col_name or "").strip()
    if not new_col_name:
        raise ValueError("New column name is required.")
    if not selected_cols:
        raise ValueError("Please select at least one scale column.")

    missing = [c for c in selected_cols if c not in dataset.df.columns]
    if missing:
        raise ValueError(f"Unknown column(s): {', '.join(missing)}")

    func = FUNCTIONS.get(function_name)
    if func is None:
        raise ValueError(f"Unsupported calculation function: {function_name}")

    numeric = dataset.df[selected_cols].apply(pd.to_numeric, errors="coerce")
    dataset.df[new_col_name] = func(numeric)
    dataset.categories.setdefault(new_col_name, UNCATEGORISED)

    return new_col_name
