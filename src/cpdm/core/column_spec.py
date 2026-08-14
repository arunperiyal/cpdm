"""Parsing typed column selections.

Users can name columns instead of ticking them, which is far quicker on a wide
questionnaire. A spec is a comma- or newline-separated list of tokens::

    WB1, WB3, DS2        exact column names
    WB1:WB5              inclusive range, in the order the columns appear
    7:15                 the same, given as positions (1-based)
    12                   one column by position
    WB*                  glob against the column name

**Positions are relative to the list being selected from.** For a root group
that list is the whole table, so ``7:15`` means the seventh to fifteenth
columns. Inside a subgroup it is the parent's columns, so a subgroup of a group
holding columns 7-16 reads ``1:4`` as that group's first four columns — table
columns 7-10. It matches what the picker shows underneath.

An exact column name always wins over the other readings, so a column really
called ``5`` or ``A:B`` still resolves to itself.
"""

import fnmatch
import re

_SEPARATORS = re.compile(r"[,\n;]+")
_RANGE = re.compile(r"^(?P<start>.+?)\s*(?::|\.\.)\s*(?P<end>.+)$")


def _index_of(token, universe, lookup):
    """One token -> index within ``universe``, or None."""
    if token in lookup:
        return lookup[token]

    if token.isdigit():
        position = int(token)
        if 1 <= position <= len(universe):
            return position - 1
        return None

    lowered = token.lower()
    for index, column in enumerate(universe):
        if column.lower() == lowered:
            return index
    return None


def _match_token(token, universe, lookup):
    """Indices in ``universe`` matched by a range, position, glob or name."""
    range_match = _RANGE.match(token)
    if range_match:
        start = _index_of(range_match.group("start").strip(), universe, lookup)
        end = _index_of(range_match.group("end").strip(), universe, lookup)
        if start is None or end is None:
            return []
        low, high = sorted((start, end))
        return list(range(low, high + 1))

    if any(char in token for char in "*?["):
        return [
            index for index, column in enumerate(universe)
            if fnmatch.fnmatch(column, token)
            or fnmatch.fnmatch(column.lower(), token.lower())
        ]

    index = _index_of(token, universe, lookup)
    return [] if index is None else [index]


def parse(spec, columns, allowed=None):
    """Resolve a spec against ``columns``, or against ``allowed`` if scoped.

    Returns ``{"columns": [...], "unknown": [...], "rejected": [...]}``: the
    resolved columns in list order, tokens that matched nothing, and columns
    that exist in the table but sit outside ``allowed`` (a subgroup reaching
    past its parent).
    """
    columns = [str(col) for col in columns]
    universe = columns if allowed is None else [str(col) for col in allowed]

    lookup = {col: index for index, col in enumerate(universe)}
    table_lookup = {col: index for index, col in enumerate(columns)}

    chosen = set()
    unknown = []
    rejected = set()

    for raw in _SEPARATORS.split(spec or ""):
        token = raw.strip()
        if not token:
            continue

        # an exact column name beats every other interpretation
        matched = [lookup[token]] if token in lookup else _match_token(token, universe, lookup)
        if matched:
            chosen.update(matched)
            continue

        # nothing in scope: is it a real column the scope excludes, or a typo?
        outside = _match_token(token, columns, table_lookup) if allowed is not None else []
        if outside:
            rejected.update(columns[index] for index in outside)
        else:
            unknown.append(token)

    return {
        "columns": [universe[index] for index in sorted(chosen)],
        "unknown": unknown,
        "rejected": sorted(rejected),
    }


def describe(result):
    """A short human summary for the log pane."""
    parts = [f"{len(result['columns'])} column(s) matched"]
    if result["unknown"]:
        parts.append("no match for: " + ", ".join(result["unknown"]))
    if result["rejected"]:
        parts.append("outside the parent group: " + ", ".join(result["rejected"]))
    return "; ".join(parts)
