"""Scales: declaring them on a group, then numerising and scoring them.

A scale is deliberately separate from the group tree. A group organises
columns; a scale says "these columns, as organised by that group, are one
instrument". Declaring a scale takes the group's name and its columns, and
nothing about the group changes — the same tree can carry no scales at all,
or a scale on every subgroup.

Where a scale is declared on a group *and* on a group nested inside it, the
deeper one wins for the columns they share (see ``Dataset.refresh_categories``).
"""

import pandas as pd

from cpdm.core import groups

DIRECT = "Direct"
REVERSE = "Reverse"


# --- declaring scales -----------------------------------------------------
def list_scales(dataset):
    """Every declared scale, with the group it reads and that group's columns."""
    listing = []
    for scale in dataset.scales:
        group = dataset.find_group(scale["group"])
        columns = list(group["columns"]) if group else []
        listing.append({
            "name": scale["name"],
            "group": scale["group"],
            "columns": columns,
            "column_count": len(columns),
            "missing_group": group is None,
        })
    return listing


def find_scale(dataset, name):
    for scale in dataset.scales:
        if scale["name"] == name:
            return scale
    return None


def create_scale(dataset, group_name, name=None):
    """Declare the columns of a group to be a scale."""
    dataset.require_df()

    group = groups.require(dataset, group_name)
    if not group["columns"]:
        raise ValueError(
            f"Group '{group_name}' has no columns yet. Add columns in Fields -> Groups first."
        )

    existing = groups.scale_on(dataset, group_name)
    if existing:
        raise ValueError(f"Group '{group_name}' is already the scale '{existing}'.")

    name = (name or group_name).strip()
    if not name:
        raise ValueError("Scale name cannot be empty.")
    for scale in dataset.scales:
        if scale["name"].lower() == name.lower():
            raise ValueError(f"A scale named '{scale['name']}' already exists.")

    scale = {"name": name, "group": group_name}
    dataset.scales.append(scale)
    dataset.refresh_categories()
    return scale


def delete_scale(dataset, name):
    """Undeclare a scale. Its group and columns are untouched."""
    if find_scale(dataset, name) is None:
        raise ValueError(f"No scale named '{name}'.")
    dataset.scales = [scale for scale in dataset.scales if scale["name"] != name]
    dataset.refresh_categories()
    return dataset.defined_scales


def scale_summary(dataset):
    """One line per scale, for the console."""
    return [
        f"[{scale['name']}] from group '{scale['group']}', "
        f"{scale['column_count']} column(s): "
        + (", ".join(scale["columns"]) if scale["columns"] else "none")
        for scale in list_scales(dataset)
    ]


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
