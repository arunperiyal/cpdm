"""Field groups: a tree of named column sets.

A **group** names a set of columns; a **subgroup** is a subset of its parent's
columns. Nesting can go as deep as you like, and the containment rule holds at
every level.

Groups and scales are different things. A group is organisational; a *scale* is
a group whose ``kind`` says so, and that mark can sit at any depth. A container
group can hold several scales (a "Scales" group holding PHQ and GAD), or a
scale can hold plain sub-groups that merely label facets of it.

The tree is the only place column membership is decided. The flat
``dataset.categories`` map that Scoring, Numerise and Compute read is derived
from it by :func:`derive_categories`: for each column, the **deepest** group
holding it that is marked as a scale (or as demographics) decides, so a scale
takes both its name and its items from the group.
"""

from cpdm.core import column_spec
from cpdm.core.dataset import (
    DEMOGRAPHICS,
    KIND_DEMOGRAPHICS,
    KIND_LABELS,
    KIND_OTHER,
    KIND_SCALE,
    KINDS,
    SCALE_PREFIX,
    UNCATEGORISED,
)


# --- lookups --------------------------------------------------------------
def find(dataset, name):
    for group in dataset.groups:
        if group["name"] == name:
            return group
    return None


def require(dataset, name):
    group = find(dataset, name)
    if group is None:
        raise ValueError(f"No group named '{name}'.")
    return group


def children(dataset, name):
    return [group for group in dataset.groups if group["parent"] == name]


def descendants(dataset, name):
    """Every group below this one, depth first."""
    found = []
    for child in children(dataset, name):
        found.append(child)
        found.extend(descendants(dataset, child["name"]))
    return found


def depth_of(dataset, group):
    """How far below a root a group sits (0 for a root)."""
    steps = 0
    seen = {group["name"]}
    while group["parent"]:
        group = find(dataset, group["parent"])
        if group is None or group["name"] in seen:
            break
        seen.add(group["name"])
        steps += 1
    return steps


def tree(dataset):
    """The group forest, ready for the browser."""

    def node(group):
        return {
            "name": group["name"],
            "parent": group["parent"],
            "kind": group["kind"],
            "label": KIND_LABELS[group["kind"]],
            "columns": list(group["columns"]),
            "column_count": len(group["columns"]),
            "children": [node(child) for child in children(dataset, group["name"])],
        }

    return [node(group) for group in dataset.groups if not group["parent"]]


def eligible_columns(dataset, parent=None):
    """Columns a group may take: its parent's, or every column for a root."""
    if not parent:
        return list(dataset.require_df().columns)
    return list(require(dataset, parent)["columns"])


# --- validation -----------------------------------------------------------
def _clean_name(dataset, name, current=None):
    name = (name or "").strip()
    if not name:
        raise ValueError("Group name cannot be empty.")
    for group in dataset.groups:
        if group["name"] == current:
            continue
        if group["name"].lower() == name.lower():
            raise ValueError(f"A group named '{group['name']}' already exists.")
    return name


def _clean_kind(kind):
    kind = (kind or KIND_SCALE).lower()
    if kind not in KINDS:
        raise ValueError(f"Unknown group kind '{kind}'. Expected one of: {', '.join(KINDS)}")
    return kind


def _clean_columns(dataset, columns, parent=None, spec=None):
    """Resolve a column list and/or a typed spec against the allowed set."""
    allowed = eligible_columns(dataset, parent)
    allowed_set = set(allowed)

    chosen = []
    rejected = []
    unknown = []

    for col in columns or []:
        if col in allowed_set:
            chosen.append(col)
        elif col in set(dataset.df.columns):
            rejected.append(col)
        else:
            unknown.append(col)

    if spec:
        parsed = column_spec.parse(spec, dataset.df.columns, allowed=allowed)
        chosen.extend(parsed["columns"])
        rejected.extend(parsed["rejected"])
        unknown.extend(parsed["unknown"])

    if rejected:
        raise ValueError(
            "These columns are not in the parent group: " + ", ".join(sorted(set(rejected)))
        )
    if unknown:
        raise ValueError("Unknown column(s): " + ", ".join(sorted(set(unknown))))

    # keep table order, drop duplicates
    ordered = [col for col in allowed if col in set(chosen)]
    return ordered


def _detach_from_siblings(dataset, name, parent, columns):
    """A column belongs to one group per level; take it off any rival.

    Returns the groups it was pulled out of, so the caller can say so.
    """
    taken = set(columns)
    moved = {}

    for group in dataset.groups:
        if group["name"] == name or group["parent"] != parent:
            continue
        overlap = [col for col in group["columns"] if col in taken]
        if not overlap:
            continue
        group["columns"] = [col for col in group["columns"] if col not in taken]
        moved[group["name"]] = overlap
        # a subgroup cannot keep columns its parent has just lost
        for child in descendants(dataset, group["name"]):
            child["columns"] = [col for col in child["columns"] if col not in taken]

    return moved


def _prune_children(dataset, name):
    """Keep every subgroup within its parent after the parent shrinks."""
    parent_columns = set(require(dataset, name)["columns"])
    dropped = 0
    for child in children(dataset, name):
        kept = [col for col in child["columns"] if col in parent_columns]
        dropped += len(child["columns"]) - len(kept)
        child["columns"] = kept
        dropped += _prune_children(dataset, child["name"])
    return dropped


# --- operations -----------------------------------------------------------
def create_group(dataset, name, parent=None, kind=None, columns=None, spec=None):
    """Create a group. Subgroups default to plain containers, roots to scales."""
    dataset.require_df()

    if parent:
        require(dataset, parent)
    name = _clean_name(dataset, name)
    kind = _clean_kind(kind or (KIND_OTHER if parent else KIND_SCALE))
    resolved = _clean_columns(dataset, columns, parent, spec)

    group = {"name": name, "parent": parent or None, "kind": kind, "columns": resolved}
    dataset.groups.append(group)

    moved = _detach_from_siblings(dataset, name, group["parent"], resolved)
    derive_categories(dataset)
    return {"group": group, "moved": moved}


def update_group(dataset, name, new_name=None, kind=None, columns=None, spec=None):
    dataset.require_df()
    group = require(dataset, name)

    if new_name is not None and new_name != name:
        renamed = _clean_name(dataset, new_name, current=name)
        for child in dataset.groups:
            if child["parent"] == name:
                child["parent"] = renamed
        group["name"] = renamed
        name = renamed

    if kind is not None:
        group["kind"] = _clean_kind(kind)

    moved = {}
    dropped = 0
    if columns is not None or spec:
        group["columns"] = _clean_columns(dataset, columns, group["parent"], spec)
        moved = _detach_from_siblings(dataset, name, group["parent"], group["columns"])
        dropped = _prune_children(dataset, name)

    derive_categories(dataset)
    return {"group": group, "moved": moved, "columns_dropped_from_subgroups": dropped}


def delete_group(dataset, name):
    """Remove a group and everything under it. Columns keep their data."""
    require(dataset, name)
    doomed = {name} | {child["name"] for child in descendants(dataset, name)}
    dataset.groups = [group for group in dataset.groups if group["name"] not in doomed]
    derive_categories(dataset)
    return sorted(doomed)


# --- keeping the flat category map in step --------------------------------
def derive_categories(dataset):
    """Rewrite ``dataset.categories`` from the tree.

    The deepest group holding a column decides, so marking a subgroup as a
    scale makes *it* the column's scale rather than the group above it.
    Container groups say nothing, and the search carries on up the tree.
    """
    if dataset.df is None:
        return dataset.categories

    categories = {col: UNCATEGORISED for col in dataset.df.columns}

    for group in sorted(dataset.groups, key=lambda g: depth_of(dataset, g)):
        if group["kind"] == KIND_OTHER:
            continue
        label = (
            DEMOGRAPHICS if group["kind"] == KIND_DEMOGRAPHICS
            else SCALE_PREFIX + group["name"]
        )
        # shallow first, so a deeper scale overwrites the one above it
        for col in group["columns"]:
            if col in categories:
                categories[col] = label

    dataset.categories = categories
    return categories


def assign_columns(dataset, assignments):
    """Move columns between groups, one column at a time.

    ``assignments`` maps a column to the group it should end up in, or to an
    empty value to leave it ungrouped. Naming a subgroup puts the column in its
    ancestors too, since a subgroup's columns are always part of its parent.
    """
    dataset.require_df()

    live = set(dataset.df.columns)
    moved = 0
    cleared = 0

    for column, target in (assignments or {}).items():
        if column not in live:
            raise ValueError(f"Unknown column '{column}'.")

        wanted = set()
        if target:
            group = require(dataset, target)
            while group:
                wanted.add(group["name"])
                group = find(dataset, group["parent"]) if group["parent"] else None

        for group in dataset.groups:
            holds = column in group["columns"]
            if group["name"] in wanted and not holds:
                # keep the group's columns in table order
                group["columns"] = [
                    col for col in dataset.df.columns
                    if col in set(group["columns"]) | {column}
                ]
            elif holds and group["name"] not in wanted:
                group["columns"] = [col for col in group["columns"] if col != column]

        if wanted:
            moved += 1
        else:
            cleared += 1

    derive_categories(dataset)
    return {"assigned": moved, "cleared": cleared}


def ungrouped_columns(dataset):
    """Columns that belong to no group at all."""
    taken = {col for group in dataset.groups for col in group["columns"]}
    return [col for col in dataset.require_df().columns if col not in taken]


def group_of(dataset, column):
    """The deepest group holding a column, which is what the UI shows."""
    holders = [group for group in dataset.groups if column in group["columns"]]
    if not holders:
        return None
    return max(holders, key=lambda group: depth_of(dataset, group))["name"]


def summary(dataset):
    """One line per group, indented by depth — used by the console."""
    lines = []

    def walk(group, depth):
        marker = "  " * depth + ("- " if depth else "")
        kind = KIND_LABELS[group["kind"]]
        lines.append(
            f"{marker}[{group['name']}] {kind}, {len(group['columns'])} column(s): "
            + (", ".join(group["columns"]) if group["columns"] else "none")
        )
        for child in children(dataset, group["name"]):
            walk(child, depth + 1)

    for group in dataset.groups:
        if not group["parent"]:
            walk(group, 0)
    return lines
