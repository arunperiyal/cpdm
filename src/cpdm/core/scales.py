"""Numerisation and scoring.

Scales themselves are not defined here: a scale is a group marked as one in
Fields -> Groups (see :mod:`cpdm.core.groups`), which is where it takes both
its name and its columns from. This module only acts on them.
"""

import pandas as pd

DIRECT = "Direct"
REVERSE = "Reverse"


# --- numerisation --------------------------------------------------------
def numerise(dataset, prefix="Scale_", target_scale=None):
    """Rename a scale's columns to <prefix>1, <prefix>2, ... in column order."""
    dataset.require_df()

    scale_cols = set(dataset.scale_columns(target_scale))
    if not scale_cols:
        raise ValueError("No columns categorized under the selected scale(s).")

    rename_map = {}
    counter = 1
    for col in dataset.df.columns:
        if col in scale_cols:
            rename_map[col] = f"{prefix}{counter}"
            counter += 1

    return dataset.rename(rename_map)


# --- scoring -------------------------------------------------------------
def apply_scoring(dataset, configs):
    """Coerce scored columns to numeric and flip any marked as reverse-keyed."""
    dataset.require_df()

    applied = []
    for col, cfg in (configs or {}).items():
        if col not in dataset.df.columns:
            continue

        dataset.df[col] = pd.to_numeric(dataset.df[col], errors="coerce")
        if cfg.get("type") == REVERSE:
            scale_max = cfg.get("scale_max", 5)
            scale_min = cfg.get("scale_min", 1)
            dataset.df[col] = (scale_min + scale_max) - dataset.df[col]

        dataset.scoring_config[col] = cfg
        applied.append(col)

    return applied
