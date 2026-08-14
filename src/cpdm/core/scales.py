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

import io
import json

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

    Reads the remembered answers for columns that have been scored, so the
    option list keeps showing the labels people chose rather than the numbers
    scoring has since written.

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
        for value in dataset.answers_for(col):
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


def item_prefix(label):
    """A column-name-safe prefix from a scale name: 'Digital Stress' -> 'Digital_Stress'."""
    return "_".join(str(label).split()) or "Scale"


def rename_items(dataset, name, prefix=None):
    """Rename a scale's columns to <prefix>_1, <prefix>_2, … in column order.

    The prefix defaults to the scale's own name, so the headers say which
    instrument they belong to and in what order.
    """
    scale = require_scale(dataset, name)
    columns = set(scale_columns(dataset, scale))
    if not columns:
        raise ValueError(f"Scale '{name}' has no items to rename.")

    stem = item_prefix(prefix or scale["name"])
    rename_map = {}
    counter = 1
    for col in dataset.df.columns:
        if col in columns:
            new_name = f"{stem}_{counter}"
            if new_name != col:
                rename_map[col] = new_name
            counter += 1

    taken = set(dataset.df.columns) - columns
    clashes = sorted(set(rename_map.values()) & taken)
    if clashes:
        raise ValueError(
            "These names are already used by other columns: " + ", ".join(clashes)
        )

    dataset.rename(rename_map)
    return {"renamed": rename_map, "columns": scale_columns(dataset, scale)}


def create_scale(dataset, group_name, name=None, rename=False):
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

    if rename:
        rename_items(dataset, name)
    # numeric answers score themselves, so such a scale is ready at once
    rescore(dataset, name)
    return scale


def delete_scale(dataset, name):
    """Undeclare a scale, putting back the answers its scoring overwrote.

    The group and its columns stay; the columns simply hold what they held
    before the scale scored them. That makes scoring reversible in a tool that
    has no undo.
    """
    scale = require_scale(dataset, name)

    restored = []
    for column in scale_columns(dataset, scale):
        if column in dataset.answers and column in dataset.df.columns:
            dataset.df[column] = dataset.answers[column]
            restored.append(column)
    dataset.forget_answers(restored)

    dataset.scales = [entry for entry in dataset.scales if entry["name"] != name]
    dataset.refresh_categories()
    return {"defined_scales": dataset.defined_scales, "restored": restored}


# --- saving and loading definitions ---------------------------------------
SCALE_FILE_KIND = "cpdm-scales"
SCALE_FILE_VERSION = 1
SCALE_FILENAME = "scales.json"


def export_definitions(dataset, names=None):
    """The scales as a portable definition: options, keying and item names."""
    chosen = names or dataset.defined_scales
    definitions = []

    for name in chosen:
        scale = require_scale(dataset, name)
        detail = describe(dataset, name)
        definitions.append({
            "name": scale["name"],
            "group": scale["group"],
            "columns": scale_columns(dataset, scale),
            "options": [dict(option) for option in detail["options"]],
            "items": [dict(item) for item in detail["items"]],
        })

    payload = {
        "kind": SCALE_FILE_KIND,
        "version": SCALE_FILE_VERSION,
        "source_file": dataset.filename,
        "scales": definitions,
    }
    stream = io.BytesIO(json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"))
    return stream, SCALE_FILENAME


def _target_group(dataset, definition, create=True):
    """Find, or build, the group a saved scale should read.

    A definition travels between datasets, so match on the group name first,
    then on the exact set of columns, and failing both build the group from
    the saved column names if this dataset has them.
    """
    group = dataset.find_group(definition.get("group", ""))
    if group is not None:
        return group, "by group name"

    saved_columns = [col for col in definition.get("columns", [])]
    if saved_columns:
        for candidate in dataset.groups:
            if candidate["columns"] == saved_columns:
                return candidate, "by matching columns"

        live = set(dataset.df.columns)
        if create and all(col in live for col in saved_columns):
            created = groups.create_group(
                dataset, definition.get("group") or definition["name"],
                columns=saved_columns,
            )
            return created["group"], "new group from the file"
        if not create and all(col in live for col in saved_columns):
            return None, "new group from the file"

    return None, None


def _require_file(payload):
    if not isinstance(payload, dict) or payload.get("kind") != SCALE_FILE_KIND:
        raise ValueError("That is not a CPDM scale file.")
    return payload


def inspect_file(dataset, payload):
    """What a scale file holds, and where each scale could go in this dataset.

    A definition saved after its items were renamed will not match a fresh
    dataset by column name, so the loader offers the groups it could be put on
    instead of quietly skipping it.
    """
    dataset.require_df()
    _require_file(payload)

    free_groups = [
        {"name": group["name"], "column_count": len(group["columns"])}
        for group in dataset.groups if not groups.scale_on(dataset, group["name"])
    ]

    entries = []
    for definition in payload.get("scales", []):
        name = str(definition.get("name", "")).strip()
        if not name:
            continue
        group, matched = _target_group(dataset, definition, create=False)
        saved_columns = definition.get("columns", [])
        entries.append({
            "name": name,
            "saved_group": definition.get("group"),
            "saved_columns": saved_columns,
            "items": len(definition.get("items", [])),
            "options": len(definition.get("options", [])),
            "suggested_group": group["name"] if group else None,
            "suggested_reason": matched,
            "can_create_group": bool(saved_columns) and all(
                col in set(dataset.df.columns) for col in saved_columns
            ),
            "already_here": find_scale(dataset, name) is not None,
        })

    return {"scales": entries, "groups": free_groups}


def import_definitions(dataset, payload, mapping=None):
    """Load saved scales onto this dataset, matching groups and items.

    ``mapping`` names the group each scale should read, for the cases the
    automatic match cannot work out; an empty value there means "skip".
    """
    dataset.require_df()
    _require_file(payload)

    mapping = mapping or {}
    results = []

    for definition in payload.get("scales", []):
        name = str(definition.get("name", "")).strip()
        if not name:
            continue

        if find_scale(dataset, name):
            results.append({"scale": name, "loaded": False,
                            "reason": "a scale of that name already exists"})
            continue

        if name in mapping:
            chosen = mapping[name]
            if not chosen:
                results.append({"scale": name, "loaded": False,
                                "reason": "skipped"})
                continue
            group, matched = groups.require(dataset, chosen), "chosen"
        else:
            group, matched = _target_group(dataset, definition)

        if group is None:
            results.append({"scale": name, "loaded": False,
                            "reason": "no group here holds its columns"})
            continue
        if groups.scale_on(dataset, group["name"]):
            results.append({"scale": name, "loaded": False,
                            "reason": f"group '{group['name']}' already has a scale"})
            continue

        scale = create_scale(dataset, group["name"], name)
        set_options(dataset, name, definition.get("options", []))

        # keying travels by column name, falling back to position so the same
        # instrument keeps its pattern under different headers
        columns = scale_columns(dataset, scale)
        saved_items = definition.get("items", [])
        by_name = {item.get("column"): item.get("type") for item in saved_items}

        types = {}
        matched_by_position = 0
        for index, column in enumerate(columns):
            if column in by_name:
                types[column] = by_name[column]
            elif index < len(saved_items):
                types[column] = saved_items[index].get("type", DIRECT)
                matched_by_position += 1
        set_item_types(dataset, name, {c: t for c, t in types.items() if t in TYPES})

        results.append({
            "scale": name,
            "loaded": True,
            "group": group["name"],
            "group_matched": matched,
            "items": len(columns),
            "items_by_position": matched_by_position,
            "options": len(definition.get("options", [])),
        })

    return results


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
    rescore(dataset, name)
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

    rescore(dataset, name)
    return {"added": added, "detail": describe(dataset, name)}


def autoscore_options(dataset, name, start=1, step=1):
    """Number the options in their current order — the usual Likert case."""
    scale = require_scale(dataset, name)
    for index, option in enumerate(scale.get("options", [])):
        option["score"] = _clean_score(start + index * step)
    rescore(dataset, name)
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

    rescore(dataset, name)
    return describe(dataset, name)


# --- scoring the data -----------------------------------------------------
def _scored_series(dataset, column, score_by_label, known_labels, flip):
    """Map one item's answers to scores, then flip it if it is reverse-keyed.

    An answer whose option is on the list but deliberately left unscored — "not
    applicable" and the like — becomes blank without complaint. Only answers
    with no option at all are reported back as unmapped.
    """
    original = dataset.answers_for(column)
    labels = original.apply(lambda v: None if pd.isna(v) else str(v).strip())

    scored = labels.map(lambda label: score_by_label.get(label) if label else None)
    scored = pd.to_numeric(scored, errors="coerce")
    if flip is not None:
        scored = flip - scored

    unmapped = sorted({
        label for label in labels if label and label not in known_labels
    })
    return scored, unmapped


def is_scorable(dataset, name):
    """Whether the scale has enough of a definition to score anything."""
    detail = describe(dataset, name)
    return any(option["score"] is not None for option in detail["options"])


def _scoring_plan(dataset, names=None, strict=True):
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
            if not strict:
                continue
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


def scoring_status(dataset, names=None):
    """What the scoring currently does to each item — for Scales -> View Scoring."""
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
        for plan in _scoring_plan(dataset, names, strict=False)
    ]


def apply_scoring(dataset, names=None, strict=True):
    """Score the data: map the remembered answers, then flip reverse items.

    Safe to run as often as you like. Each item is computed from the answers
    the column held before it was ever scored, never from the numbers a
    previous pass wrote, so re-running cannot double-reverse or blank a scale
    whose answers are text.
    """
    plans = _scoring_plan(dataset, names, strict=strict)

    applied = []
    for plan in plans:
        for item in plan["items"]:
            dataset.keep_answers(item["column"])
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


def rescore(dataset, name):
    """Re-apply one scale after its definition changed. Quiet if not ready."""
    if not is_scorable(dataset, name):
        return None
    applied = apply_scoring(dataset, [name], strict=False)
    return applied[0] if applied else None
