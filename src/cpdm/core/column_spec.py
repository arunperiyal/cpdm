"""Parsing typed column selections.

Users can name columns instead of ticking them, which is far quicker on a wide
questionnaire. A spec is a comma- or newline-separated list of tokens::

    WB1, WB3, DS2        exact column names
    WB1:WB5              inclusive range, by position in the table
    7:15                 the same, given as 1-based column positions
    12                   one column by position
    WB*                  glob against the column name

An exact column name always wins over the other readings, so a column really
called ``5`` or ``A:B`` still resolves to itself.
"""

import fnmatch
import re

_SEPARATORS = re.compile(r"[,\n;]+")
_RANGE = re.compile(r"^(?P<start>.+?)\s*(?::|\.\.)\s*(?P<end>.+)$")


def _position(token, columns):
    """1-based column position, or None if the token is not a bare number."""
    if not token.isdigit():
        return None
    index = int(token)
    if 1 <= index <= len(columns):
        return index - 1
    return None


def _resolve_single(token, columns, lookup):
    """One endpoint or plain token -> column index, or None."""
    if token in lookup:
        return lookup[token]
    position = _position(token, columns)
    if position is not None:
        return position
    lowered = token.lower()
    for index, column in enumerate(columns):
        if str(column).lower() == lowered:
            return index
    return None


def parse(spec, columns, allowed=None):
    """Resolve a spec against ``columns``.

    Returns ``{"columns": [...], "unknown": [...], "rejected": [...]}`` where
    the resolved columns keep table order, ``unknown`` lists tokens that matched
    nothing, and ``rejected`` lists resolved columns that fall outside
    ``allowed`` (used for subgroups, which may only take their parent's
    columns).
    """
    columns = [str(col) for col in columns]
    lookup = {col: index for index, col in enumerate(columns)}
    allowed_set = None if allowed is None else {str(col) for col in allowed}

    chosen = set()
    unknown = []
    rejected = set()

    for raw in _SEPARATORS.split(spec or ""):
        token = raw.strip()
        if not token:
            continue

        # an exact column name beats every other interpretation
        if token in lookup:
            matched = [lookup[token]]
        else:
            matched = _match_token(token, columns, lookup)

        if not matched:
            unknown.append(token)
            continue

        for index in matched:
            name = columns[index]
            if allowed_set is not None and name not in allowed_set:
                rejected.add(name)
                continue
            chosen.add(index)

    return {
        "columns": [columns[i] for i in sorted(chosen)],
        "unknown": unknown,
        "rejected": sorted(rejected),
    }


def _match_token(token, columns, lookup):
    """Indices matched by a range, a position, a glob or a name."""
    range_match = _RANGE.match(token)
    if range_match:
        start = _resolve_single(range_match.group("start").strip(), columns, lookup)
        end = _resolve_single(range_match.group("end").strip(), columns, lookup)
        if start is not None and end is not None:
            low, high = sorted((start, end))
            return list(range(low, high + 1))
        return []

    if any(char in token for char in "*?["):
        return [
            index for index, column in enumerate(columns)
            if fnmatch.fnmatch(column, token) or fnmatch.fnmatch(column.lower(), token.lower())
        ]

    single = _resolve_single(token, columns, lookup)
    return [] if single is None else [single]


def describe(result):
    """A short human summary for the log pane."""
    parts = [f"{len(result['columns'])} column(s) matched"]
    if result["unknown"]:
        parts.append("no match for: " + ", ".join(result["unknown"]))
    if result["rejected"]:
        parts.append("outside the parent group: " + ", ".join(result["rejected"]))
    return "; ".join(parts)
