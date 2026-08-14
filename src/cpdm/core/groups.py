"""Field groups: a tree of named column sets.

A **group** names a set of columns; a **subgroup** is a subset of its parent's
columns. Nesting can go as deep as you like, and the containment rule holds at
every level.

Groups say nothing about analysis: they organise columns, and that is all. What
makes a group's columns a scale is a scale declared on it in
:mod:`cpdm.core.scales`, which is a separate, explicit step.
"""

from cpdm.core import column_spec


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


def tree(dataset):
    """The group forest, ready for the browser."""

    def node(group):
        return {
            "name": group["name"],
            "parent": group["parent"],
            "scale": scale_on(dataset, group["name"]),
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
def create_group(dataset, name, parent=None, columns=None, spec=None):
    """Create a group. Whether it is a scale is declared separately."""
    dataset.require_df()

    if parent:
        require(dataset, parent)
    name = _clean_name(dataset, name)
    resolved = _clean_columns(dataset, columns, parent, spec)

    group = {"name": name, "parent": parent or None, "columns": resolved}
    dataset.groups.append(group)

    moved = _detach_from_siblings(dataset, name, group["parent"], resolved)
    dataset.refresh_categories()
    return {"group": group, "moved": moved}


def update_group(dataset, name, new_name=None, columns=None, spec=None):
    dataset.require_df()
    group = require(dataset, name)

    if new_name is not None and new_name != name:
        renamed = _clean_name(dataset, new_name, current=name)
        for child in dataset.groups:
            if child["parent"] == name:
                child["parent"] = renamed
        for scale in dataset.scales:   # a scale points at its group by name
            if scale["group"] == name:
                scale["group"] = renamed
        group["name"] = renamed
        name = renamed

    moved = {}
    dropped = 0
    if columns is not None or spec:
        group["columns"] = _clean_columns(dataset, columns, group["parent"], spec)
        moved = _detach_from_siblings(dataset, name, group["parent"], group["columns"])
        dropped = _prune_children(dataset, name)

    dataset.refresh_categories()
    return {"group": group, "moved": moved, "columns_dropped_from_subgroups": dropped}


def delete_group(dataset, name):
    """Remove a group, everything under it, and any scales built on them.

    Columns keep their data; they just stop belonging anywhere.
    """
    require(dataset, name)
    doomed = {name} | {child["name"] for child in descendants(dataset, name)}

    dataset.groups = [group for group in dataset.groups if group["name"] not in doomed]
    dropped_scales = [scale["name"] for scale in dataset.scales if scale["group"] in doomed]
    dataset.scales = [scale for scale in dataset.scales if scale["group"] not in doomed]

    dataset.refresh_categories()
    return {"groups": sorted(doomed), "scales": dropped_scales}


def scale_on(dataset, group_name):
    """The name of the scale declared on this group, if there is one."""
    for scale in dataset.scales:
        if scale["group"] == group_name:
            return scale["name"]
    return None


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

    dataset.refresh_categories()
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
    return max(holders, key=lambda group: dataset.group_depth(group))["name"]


def summary(dataset):
    """One line per group, indented by depth — used by the console."""
    lines = []

    def walk(group, depth):
        marker = "  " * depth + ("- " if depth else "")
        scale = scale_on(dataset, group["name"])
        badge = f"scale '{scale}'" if scale else "group"
        lines.append(
            f"{marker}[{group['name']}] {badge}, {len(group['columns'])} column(s): "
            + (", ".join(group["columns"]) if group["columns"] else "none")
        )
        for child in children(dataset, group["name"]):
            walk(child, depth + 1)

    for group in dataset.groups:
        if not group["parent"]:
            walk(group, 0)
    return lines
