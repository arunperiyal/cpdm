"""Scales: declaring them on a group, describing them, and scoring the data.

A scale is deliberately separate from the group tree. A group organises
columns; a scale says "these columns, as organised by that group, are one
instrument". Declaring a scale takes the group's name and its columns, and
nothing about the group changes.

A scale then describes itself in two parts:

**Items** are its columns — the questions — each carrying a scoring *type*,
Direct or Reverse.

**Options** are its response set — the answers — an *ordered* list of labels,
each carrying a numeric score. Options are seeded from the values actually
present in the data, but the list is editable: an option nobody happened to
choose can be added by hand, and the order is yours to set.

Scoring the data then means: replace each answer with its option's score,
within this scale's columns only, and flip the reverse-keyed items. The
reversal uses the scale's own smallest and largest option scores, so there is
no maximum to type in and get wrong.

Where a scale is declared on a group *and* on a group nested inside it, the
deeper one wins for the columns they share (see ``Dataset.refresh_categories``).
"""

import pandas as pd

from cpdm.core import groups

DIRECT = "Direct"
REVERSE = "Reverse"
TYPES = (DIRECT, REVERSE)

#: a group with more distinct answers than this is free text, not a scale
MAX_SEEDED_OPTIONS = 60


# --- declaring scales -----------------------------------------------------
def list_scales(dataset):
    """Every declared scale: the group it reads, its items and its options."""
    listing = []
    for scale in dataset.scales:
        group = dataset.find_group(scale["group"])
        columns = list(group["columns"]) if group else []
        options = scale.get("options", [])
        types = scale.get("items", {})

        listing.append({
            "name": scale["name"],
            "group": scale["group"],
            "columns": columns,
            "column_count": len(columns),
            "missing_group": group is None,
            "option_count": len(options),
            "scored_options": sum(1 for o in options if o.get("score") is not None),
            "reverse_items": sum(
                1 for col in columns if types.get(col, {}).get("type") == REVERSE
            ),
        })
    return listing


def find_scale(dataset, name):
    for scale in dataset.scales:
        if scale["name"] == name:
            return scale
    return None


def require_scale(dataset, name):
    scale = find_scale(dataset, name)
    if scale is None:
        raise ValueError(f"No scale named '{name}'.")
    return scale


def scale_columns(dataset, scale):
    """The items of a scale: the columns of the group it reads."""
    group = dataset.find_group(scale["group"])
    return list(group["columns"]) if group else []


#: text that means "no answer" rather than an answer
MISSING_LABELS = {"nan", "none", "null", "na", "n/a"}


def _as_number(label):
    try:
        value = float(label)
    except (TypeError, ValueError):
        return None
    return int(value) if value.is_integer() else value


def observed_options(dataset, columns):
    """Distinct answers across some columns.

    Answers that are all numbers come back in numeric order — data that has
    already been coded needs no reordering. Anything else keeps the order it
    first appears in, which is as good a starting point as any before you set
    the real response order.
    """
    dataset.require_df()

    seen = []
    known = set()
    truncated = False

    for col in columns:
        if col not in dataset.df.columns:
            continue
        for value in dataset.df[col]:
            if pd.isna(value):
                continue
            label = str(value).strip()
            if not label or label.lower() in MISSING_LABELS or label in known:
                continue
            if len(seen) >= MAX_SEEDED_OPTIONS:
                truncated = True
                break
            known.add(label)
            seen.append(label)
        if truncated:
            break

    numbers = [_as_number(label) for label in seen]
    if seen and all(number is not None for number in numbers):
        seen = [label for _, label in sorted(zip(numbers, seen))]

    return seen, truncated


def inspect_group(dataset, group_name):
    """What a scale built on this group would contain — used before creating one."""
    group = groups.require(dataset, group_name)
    labels, truncated = observed_options(dataset, group["columns"])
    return {
        "group": group_name,
        "items": list(group["columns"]),
        "options": labels,
        "truncated": truncated,
    }


def create_scale(dataset, group_name, name=None):
    """Declare the columns of a group to be a scale, seeded from the data."""
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

    labels, truncated = observed_options(dataset, group["columns"])
    scale = {
        "name": name,
        "group": group_name,
        # answers that are already numbers score as themselves
        "options": [{"label": label, "score": _as_number(label)} for label in labels],
        "items": {col: {"type": DIRECT} for col in group["columns"]},
        "options_truncated": truncated,
    }
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
    lines = []
    for scale in dataset.scales:
        detail = describe(dataset, scale["name"])
        scored = sum(1 for option in detail["options"] if option["score"] is not None)
        reversed_items = sum(1 for item in detail["items"] if item["type"] == REVERSE)
        lines.append(
            f"[{scale['name']}] from group '{scale['group']}': "
            f"{len(detail['items'])} item(s) ({reversed_items} reverse), "
            f"{len(detail['options'])} option(s) ({scored} scored)"
        )
        if detail["options"]:
            lines.append(
                "    options: "
                + ", ".join(
                    f"{option['label']}"
                    + (f"={option['score']:g}" if option["score"] is not None else "=?")
                    for option in detail["options"]
                )
            )
    return lines


# --- items and options ----------------------------------------------------
def describe(dataset, name):
    """Everything the scale dialogues need: its items and its ordered options."""
    scale = require_scale(dataset, name)
    columns = scale_columns(dataset, scale)
    types = scale.setdefault("items", {})

    items = [
        {"column": col, "type": types.get(col, {}).get("type", DIRECT)}
        for col in columns
    ]
    options = [dict(option) for option in scale.get("options", [])]
    scores = [option["score"] for option in options if option["score"] is not None]

    return {
        "name": scale["name"],
        "group": scale["group"],
        "items": items,
        "options": options,
        "score_min": min(scores) if scores else None,
        "score_max": max(scores) if scores else None,
        "unscored": [o["label"] for o in options if o["score"] is None],
        "options_truncated": scale.get("options_truncated", False),
    }


def _clean_score(raw):
    if raw is None or raw == "":
        return None
    try:
        score = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"'{raw}' is not a number.") from None
    return int(score) if score.is_integer() else score


def set_options(dataset, name, options):
    """Replace the ordered option list. Order is the caller's; labels are unique."""
    scale = require_scale(dataset, name)

    cleaned = []
    seen = set()
    for entry in options or []:
        label = str(entry.get("label", "")).strip()
        if not label:
            continue
        if label.lower() in seen:
            raise ValueError(f"Duplicate option '{label}'.")
        seen.add(label.lower())
        cleaned.append({"label": label, "score": _clean_score(entry.get("score"))})

    scale["options"] = cleaned
    return describe(dataset, name)


def refresh_options(dataset, name):
    """Add any answers now in the data that the option list does not have yet."""
    scale = require_scale(dataset, name)
    labels, truncated = observed_options(dataset, scale_columns(dataset, scale))

    known = {option["label"] for option in scale.get("options", [])}
    added = [label for label in labels if label not in known]
    scale.setdefault("options", []).extend(
        {"label": label, "score": _as_number(label)} for label in added
    )
    scale["options_truncated"] = truncated

    return {"added": added, "detail": describe(dataset, name)}


def autoscore_options(dataset, name, start=1, step=1):
    """Number the options in their current order — the usual Likert case."""
    scale = require_scale(dataset, name)
    for index, option in enumerate(scale.get("options", [])):
        option["score"] = _clean_score(start + index * step)
    return describe(dataset, name)


def set_item_types(dataset, name, types):
    """Set Direct/Reverse per item. Unlisted items keep what they had."""
    scale = require_scale(dataset, name)
    columns = set(scale_columns(dataset, scale))
    stored = scale.setdefault("items", {})

    for column, value in (types or {}).items():
        if column not in columns:
            raise ValueError(f"'{column}' is not an item of scale '{name}'.")
        item_type = (value or {}).get("type") if isinstance(value, dict) else value
        if item_type not in TYPES:
            raise ValueError(f"Scoring type must be one of: {', '.join(TYPES)}")
        stored[column] = {"type": item_type}

    return describe(dataset, name)


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


# --- scoring the data -----------------------------------------------------
def _scored_series(dataset, column, score_by_label, known_labels, flip):
    """Map one item's answers to scores, then flip it if it is reverse-keyed.

    An answer whose option is on the list but deliberately left unscored — "not
    applicable" and the like — becomes blank without complaint. Only answers
    with no option at all are reported back as unmapped.
    """
    original = dataset.df[column]
    labels = original.apply(lambda v: None if pd.isna(v) else str(v).strip())

    scored = labels.map(lambda label: score_by_label.get(label) if label else None)
    scored = pd.to_numeric(scored, errors="coerce")
    if flip is not None:
        scored = flip - scored

    unmapped = sorted({
        label for label in labels if label and label not in known_labels
    })
    return scored, unmapped


def _scoring_plan(dataset, names=None):
    """Work out, per scale, what scoring would do. No writes."""
    dataset.require_df()

    chosen = names or dataset.defined_scales
    plans = []

    for name in chosen:
        scale = require_scale(dataset, name)
        detail = describe(dataset, name)

        score_by_label = {
            option["label"]: option["score"]
            for option in detail["options"] if option["score"] is not None
        }
        if not score_by_label:
            raise ValueError(
                f"Scale '{name}' has no scored options yet. "
                "Set them in Scales -> Assign Scoring."
            )

        known_labels = {option["label"] for option in detail["options"]}
        span = detail["score_min"] + detail["score_max"]
        items = []
        for item in detail["items"]:
            if item["column"] not in dataset.df.columns:
                continue
            flip = span if item["type"] == REVERSE else None
            scored, unmapped = _scored_series(
                dataset, item["column"], score_by_label, known_labels, flip
            )
            filled = int(scored.notna().sum())
            items.append({
                "column": item["column"],
                "type": item["type"],
                "values": scored,
                "scored_cells": filled,
                "blank_cells": int(len(scored) - filled),
                "unmapped": unmapped,
            })

        plans.append({
            "scale": name,
            "score_min": detail["score_min"],
            "score_max": detail["score_max"],
            "reversal_note": f"reverse = {span:g} - value",
            "items": items,
            "unscored_options": detail["unscored"],
        })

    return plans


def preview_scoring(dataset, names=None):
    """What Apply Scoring would do, without touching the dataframe."""
    return [
        {
            "scale": plan["scale"],
            "score_min": plan["score_min"],
            "score_max": plan["score_max"],
            "reversal_note": plan["reversal_note"],
            "unscored_options": plan["unscored_options"],
            "items": [
                {key: item[key] for key in
                 ("column", "type", "scored_cells", "blank_cells", "unmapped")}
                for item in plan["items"]
            ],
        }
        for plan in _scoring_plan(dataset, names)
    ]


def apply_scoring(dataset, names=None):
    """Write the scores into the data: map answers, then flip reverse items."""
    plans = _scoring_plan(dataset, names)

    applied = []
    for plan in plans:
        for item in plan["items"]:
            dataset.df[item["column"]] = item["values"]
        applied.append({
            "scale": plan["scale"],
            "items_scored": len(plan["items"]),
            "cells_scored": sum(item["scored_cells"] for item in plan["items"]),
            "unmapped": sorted({
                label for item in plan["items"] for label in item["unmapped"]
            }),
        })

    return applied
