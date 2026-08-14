"""Scale definitions, column categorisation, numerisation and scoring."""

import pandas as pd

from cpdm.core import groups
from cpdm.core.dataset import SCALE_PREFIX, UNCATEGORISED

DIRECT = "Direct"
REVERSE = "Reverse"


# --- scale definitions ---------------------------------------------------
def add_scale(dataset, scale_name):
    scale_name = (scale_name or "").strip()
    if not scale_name:
        raise ValueError("Scale name cannot be empty.")
    if scale_name in dataset.defined_scales:
        raise ValueError(f"Scale '{scale_name}' already exists.")
    dataset.defined_scales.append(scale_name)
    return dataset.defined_scales


def delete_scale(dataset, scale_name):
    """Remove a scale; its columns fall back to Uncategorised."""
    if scale_name in dataset.defined_scales:
        dataset.defined_scales.remove(scale_name)
        target = SCALE_PREFIX + scale_name
        for col, category in dataset.categories.items():
            if category == target:
                dataset.categories[col] = UNCATEGORISED

        # the scale's group, and any subscales under it, go with it
        if groups.find(dataset, scale_name):
            groups.delete_group(dataset, scale_name)
    return dataset.defined_scales


def set_categories(dataset, categories):
    """Save the flat categorisation, then rebuild the group tree from it."""
    dataset.categories = dict(categories or {})
    groups.rebuild_from_categories(dataset)
    return dataset.categories


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
