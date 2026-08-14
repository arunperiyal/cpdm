"""Field groups: a tree of named column sets.

A **root group** is a construct — Demographics, Wellbeing, Digital Stress. A
**subgroup** is a facet of its parent, i.e. a subscale, and may only contain
columns its parent already holds. Nesting can go deeper; the same rule applies
at every level, so every subgroup's columns belong to its root.

Groups are the structured view of the flat ``dataset.categories`` map that
Scoring, Numerise and Compute read: after any change here,
:func:`derive_categories` rewrites that map, giving every column of a
scale-kind root the category ``Scale: <root name>``. Subscale membership lives
only in the tree, so a scale keeps working as one scale.
"""

from cpdm.core import column_spec
from cpdm.core.dataset import DEMOGRAPHICS, SCALE_PREFIX, UNCATEGORISED

KIND_SCALE = "scale"
KIND_DEMOGRAPHICS = "demographics"
KIND_OTHER = "other"
KINDS = (KIND_SCALE, KIND_DEMOGRAPHICS, KIND_OTHER)

KIND_LABELS = {
    KIND_SCALE: "Scale",
    KIND_DEMOGRAPHICS: "Demographics",
    KIND_OTHER: "Other",
}


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


def root_of(dataset, group):
    """Walk up to the top-level group (a group with no parent)."""
    seen = {group["name"]}
    while group["parent"]:
        parent = find(dataset, group["parent"])
        if parent is None or parent["name"] in seen:
            break
        seen.add(parent["name"])
        group = parent
    return group


def tree(dataset):
    """The group forest, ready for the browser."""

    def node(group):
        return {
            "name": group["name"],
            "parent": group["parent"],
            "kind": root_of(dataset, group)["kind"],
            "own_kind": group["kind"],
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
def create_group(dataset, name, parent=None, kind=KIND_SCALE, columns=None, spec=None):
    dataset.require_df()

    if parent:
        require(dataset, parent)
    name = _clean_name(dataset, name)
    kind = _clean_kind(kind)
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

    if kind is not None and not group["parent"]:
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
    """Rewrite ``dataset.categories`` and ``defined_scales`` from the tree."""
    if dataset.df is None:
        return dataset.categories

    categories = {col: UNCATEGORISED for col in dataset.df.columns}

    for group in dataset.groups:
        root = root_of(dataset, group)
        if root["kind"] == KIND_OTHER:
            continue
        label = (
            DEMOGRAPHICS if root["kind"] == KIND_DEMOGRAPHICS
            else SCALE_PREFIX + root["name"]
        )
        for col in group["columns"]:
            if col in categories:
                categories[col] = label

    dataset.categories = categories

    for group in dataset.groups:
        if not group["parent"] and group["kind"] == KIND_SCALE:
            if group["name"] not in dataset.defined_scales:
                dataset.defined_scales.append(group["name"])

    return categories


def rebuild_from_categories(dataset):
    """Rebuild root groups from the flat categories, keeping subgroups.

    Fields -> Categorise edits the flat map directly, so the tree has to follow.
    Subgroups survive wherever their columns are still inside the same root.
    """
    if dataset.df is None:
        return dataset.groups

    subgroups = [group for group in dataset.groups if group["parent"]]
    roots = {}

    for col in dataset.df.columns:
        category = dataset.categories.get(col, UNCATEGORISED)
        if category == DEMOGRAPHICS:
            key, kind = DEMOGRAPHICS, KIND_DEMOGRAPHICS
        elif category.startswith(SCALE_PREFIX):
            key, kind = category[len(SCALE_PREFIX):], KIND_SCALE
        else:
            continue
        roots.setdefault(key, {"name": key, "parent": None, "kind": kind, "columns": []})
        roots[key]["columns"].append(col)

    dataset.groups = list(roots.values())

    # re-attach the subgroups whose parent still exists, trimmed to it
    for subgroup in subgroups:
        parent = find(dataset, subgroup["parent"])
        if parent is None:
            continue
        allowed = set(parent["columns"])
        kept = [col for col in subgroup["columns"] if col in allowed]
        if kept:
            subgroup["columns"] = kept
            dataset.groups.append(subgroup)

    derive_categories(dataset)
    return dataset.groups


def summary(dataset):
    """One line per group, indented by depth — used by the console."""
    lines = []

    def walk(group, depth):
        marker = "  " * depth + ("- " if depth else "")
        kind = KIND_LABELS[root_of(dataset, group)["kind"]]
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
