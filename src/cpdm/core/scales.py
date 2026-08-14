"""Scales, numerisation and scoring.

A scale *is* a root group of kind ``scale`` (see :mod:`cpdm.core.groups`), so
the two entries in the Scales menu are thin wrappers over the group tree.
"""

import pandas as pd

from cpdm.core import groups
from cpdm.core.dataset import KIND_SCALE

DIRECT = "Direct"
REVERSE = "Reverse"


# --- scale definitions ---------------------------------------------------
def add_scale(dataset, scale_name):
    """Create an empty scale, ready for columns in Fields -> Groups."""
    groups.create_group(dataset, scale_name, kind=KIND_SCALE, columns=[])
    return dataset.defined_scales


def delete_scale(dataset, scale_name):
    """Remove a scale, its subscales, and their hold on any columns."""
    if groups.find(dataset, scale_name):
        groups.delete_group(dataset, scale_name)
    return dataset.defined_scales


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
