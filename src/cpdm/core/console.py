"""The text console: small commands typed into the workspace prompt.

Each handler returns a dict the browser understands: ``output`` for plain text,
``html`` for markup, ``error`` for a red line, ``clear`` to wipe the log.

Anything after a ``#`` is a comment, so a line can be annotated or a command
parked without deleting it. Quotes protect a ``#`` that belongs to the data.

Where a command takes columns it takes the same spec the group editor does:
a position (``7``), a range (``7:15``), a name, or a glob (``WB*``).
"""

import os
import shlex

from cpdm.core import (cleaning, column_spec, docs_library, groups, scales, table,
                       tabular_io, text_rules, workspace_files)
from cpdm.core.dataset import SCALE_PREFIX

def _escape(text):
    """Console output is injected as HTML, so anything from the data is escaped."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _cmd_help(_dataset, args):
    """help          : every command, grouped
       help <name>   : what one command does, in full"""
    if args:
        return _help_for(args[0].lower())

    sections = []
    for section in HELP_SECTIONS:
        rows = "".join(
            f"<div class='help-usage'><code>{_escape(spec['usage'])}</code></div>"
            f"<div>{spec['summary']}</div>"
            for name, spec in COMMAND_ORDER if spec["section"] == section
        )
        sections.append(f"<div class='help-section'>{section}</div>"
                        f"<div class='help-grid'>{rows}</div>")

    return {"html":
            "<div class='help'>"
            f"<div class='help-head'>{len(COMMAND_ORDER)} commands — "
            "<code>help &lt;name&gt;</code> for one of them in full</div>"
            + "".join(sections) +
            "<div class='help-foot'>"
            "<strong>#</strong> starts a comment, unless it is inside quotes. "
            "<strong>Tab</strong> completes commands, rules, column names and files. "
            "<strong>↑ ↓</strong> walk back through what you have typed.<br>"
            "Columns are given as a position <code>7</code>, a range <code>7:15</code>, "
            "a name, or a pattern <code>WB*</code> — <code>headers</code> prints the positions."
            "</div></div>"}


def _help_for(name):
    spec = COMMANDS.get(name)
    if spec is None:
        close = [known for known in sorted(COMMANDS) if known.startswith(name[:2])]
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        return {"error": f"No command called '{name}'. Type 'help' for the list.{hint}"}

    aliases = [other for other, target in ALIASES.items() if target == spec["name"]]
    detail = spec.get("detail") or ""

    return {"html":
            "<div class='help'>"
            f"<div class='help-head'><code>{_escape(spec['usage'])}</code></div>"
            f"<p>{spec['summary']}.</p>"
            + (f"<p>{detail}</p>" if detail else "")
            + (f"<div class='help-foot'>Also answers to: <code>"
               + "</code>, <code>".join(sorted(aliases)) + "</code></div>" if aliases else "")
            + "</div>"}


def _cmd_clear(_dataset, _args):
    return {"clear": True}


def _cmd_docs(_dataset, _args):
    rows = []
    for section in docs_library.index():
        if not section["docs"]:
            continue
        rows.append(f"<strong style='color:#89b4fa;'>{section['label']}</strong>")
        for doc in section["docs"]:
            rows.append(
                f"&nbsp;&nbsp;- <a href='{doc['url']}' target='_blank'>{doc['title']}</a>"
            )
    if not rows:
        return {"error": "No documentation found in the docs/ directory."}
    rows.append("<br>Open the full documentation browser: "
                "<a href='/docs' target='_blank'>/docs</a>")
    return {"html": "<br>".join(rows)}


def _rows_wanted(args, default=5):
    if not args:
        return default
    try:
        count = int(args[0])
    except ValueError:
        raise ValueError(f"'{args[0]}' is not a number of rows.") from None
    if count < 1:
        raise ValueError("Ask for at least one row.")
    return count


def _cmd_head(dataset, args):
    count = _rows_wanted(args)
    frame = dataset.df.head(count)
    return {"html": f"<strong>First {len(frame)} of {len(dataset.df)} rows:</strong><br>"
                    + frame.to_html(classes="data-table")}


def _cmd_tail(dataset, args):
    count = _rows_wanted(args)
    frame = dataset.df.tail(count)
    return {"html": f"<strong>Last {len(frame)} of {len(dataset.df)} rows:</strong><br>"
                    + frame.to_html(classes="data-table")}


def _resolve_columns(dataset, spec):
    """Turn a console column spec into real column names, or explain why not.

    Separate arguments count as separate items, so `unique 4 5` and
    `unique 4,5` mean the same. A name holding a space needs quoting, which is
    what Tab completion does for you.
    """
    if isinstance(spec, (list, tuple)):
        spec = ",".join(spec)
    parsed = column_spec.parse(spec, dataset.df.columns)
    if parsed["unknown"]:
        raise ValueError("No column matches: " + ", ".join(parsed["unknown"]))
    if not parsed["columns"]:
        raise ValueError(f"'{spec}' matched no columns.")
    return parsed["columns"]


def _cmd_headers(dataset, args):
    """The header row: all of it, or the position or range asked for."""
    report = table.column_report(dataset)

    if args:
        wanted = set(_resolve_columns(dataset, args))
        report = [entry for entry in report if entry["name"] in wanted]

    rows = "".join(
        f"<tr><td class='muted'>{entry['position']}</td>"
        f"<td>{_escape(entry['name'])}</td>"
        f"<td class='muted'>{entry['dtype']}</td>"
        f"<td class='muted'>{entry['filled']}</td>"
        f"<td class='muted'>{entry['blank']}</td>"
        f"<td class='muted'>{entry['distinct']}</td>"
        f"<td class='muted'>{_escape(entry['group'] or '')}</td>"
        f"<td class='muted'>{_escape(entry['scale'] or '')}</td></tr>"
        for entry in report
    )

    return {"html":
            f"<strong>{len(report)} of {len(dataset.df.columns)} column(s):</strong>"
            "<table class='data-table'><thead><tr>"
            "<th>#</th><th>Header</th><th>Type</th><th>Filled</th><th>Blank</th>"
            "<th>Distinct</th><th>Group</th><th>Scale</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"}


def _cmd_info(dataset, _args):
    grouped = {}
    for col, category in dataset.categories.items():
        if category.startswith(SCALE_PREFIX.strip()):
            grouped.setdefault(category.replace(SCALE_PREFIX, ""), []).append(col)

    ungrouped = groups.ungrouped_columns(dataset)
    lines = [
        f"Dataset File: {dataset.filename}",
        f"Dimensions  : {dataset.df.shape[0]} rows x {dataset.df.shape[1]} columns",
        f"Ignored Cols: {len(dataset.ignored_columns)}",
        f"Groups      : {len(dataset.groups)} ({len(ungrouped)} column(s) ungrouped)",
        f"Scales ({len(dataset.defined_scales)}): "
        + (", ".join(dataset.defined_scales) if dataset.defined_scales else "none"),
    ]
    for scale_name, cols in grouped.items():
        lines.append(f"  - [{scale_name}]: {', '.join(cols)}")
    return {"output": "\n".join(lines) + "\n"}


def _cmd_groups(dataset, _args):
    lines = groups.summary(dataset)
    if not lines:
        return {"output": "No field groups yet. Build them in Fields -> Groups.\n"}
    return {"output": "Field Groups:\n" + "\n".join(lines) + "\n"}


def _cmd_scales(dataset, _args):
    lines = scales.scale_summary(dataset)
    if not lines:
        return {"output": "No scales yet. Declare one in Scales -> Create Scale.\n"}
    return {"output": "Scales:\n" + "\n".join(lines) + "\n"}


def _cmd_summary(dataset, _args):
    table = dataset.df.describe().to_html(classes="data-table")
    return {"html": f"<strong>Descriptive Statistics:</strong><br>{table}"}


# --- clean ----------------------------------------------------------------
#: console name -> the rule it builds, and what it still needs from you
CLEAN_RULES = {
    "cut": {
        "rule": {"mode": "delimiter", "keep": "before"},
        "needs": "delimiter",
        "what": "Cut at the first delimiter, keeping what comes before it",
    },
    "cut-after": {
        "rule": {"mode": "delimiter", "keep": "after"},
        "needs": "delimiter",
        "what": "Cut at the first delimiter, keeping what comes after it",
    },
    "cut-non-english": {
        "rule": {"mode": "non_english_to_end"},
        "needs": None,
        "what": "Cut from the first non-English character to the end",
    },
    "strip": {
        "rule": {"mode": "strip_non_english"},
        "needs": None,
        "what": "Remove non-English characters wherever they appear",
    },
    "tidy": {
        "rule": {"mode": "tidy"},
        "needs": None,
        "what": "Drop stray brackets and separators, collapse spaces",
    },
}


def _clean_rules_table():
    rows = "".join(
        f"<tr><td><strong>{name}</strong></td>"
        f"<td>{spec['what']}</td>"
        f"<td class='muted'>{spec['needs'] or '—'}</td></tr>"
        for name, spec in CLEAN_RULES.items()
    )
    return {"html":
            "<strong>clean values &lt;rule&gt; &lt;columns&gt; [extra]</strong><br>"
            "<table class='data-table'><thead><tr>"
            "<th>Rule</th><th>What it does</th><th>Extra argument</th>"
            "</tr></thead><tbody>" + rows + "</tbody></table>"
            "<strong>clean headers &lt;rule&gt; &lt;columns&gt;</strong> cleans the header "
            "text instead. <em>values</em> may be left out: <em>clean cut 8:16 /</em> is "
            "the same as <em>clean values cut 8:16 /</em>."}


CLEAN_TARGETS = ("rules", "headers", "values")


def _cmd_clean(dataset, args):
    """clean rules | clean headers <rule> … | clean values <rule> …"""
    if not args:
        raise ValueError("Usage: clean rules | clean headers <rule> <cols> [extra] "
                         "| clean values <rule> <cols> [extra]")
    if args[0] == "rules":
        return _clean_rules_table()

    stage = cleaning.STAGE_VALUES
    if args[0] in ("headers", "values"):
        stage = cleaning.STAGE_HEADERS if args[0] == "headers" else cleaning.STAGE_VALUES
        args = args[1:]           # named outright
    elif args[0] not in CLEAN_RULES:
        raise ValueError(f"'{args[0]}' is neither a rule nor one of: "
                         + ", ".join(CLEAN_TARGETS) + ". Try 'clean rules'.")
    # else: a bare rule name is shorthand for `clean values <rule> …`

    if len(args) < 2:
        raise ValueError("Usage: clean values <rule> <columns> [extra]  —  see 'clean rules'.")

    name, spec, extra = args[0], args[1], args[2:]
    known = CLEAN_RULES.get(name)
    if known is None:
        raise ValueError(f"No rule called '{name}'. Try 'clean rules'.")

    rule = dict(known["rule"])
    if known["needs"]:
        if not extra:
            raise ValueError(f"'{name}' needs a {known['needs']}: clean {name} {spec} <{known['needs']}>")
        rule["delimiters"] = list(extra)
    elif extra:
        raise ValueError(f"'{name}' takes no extra argument.")

    columns = _resolve_columns(dataset, spec)
    result = cleaning.apply_text_rules(dataset, stage, [rule], columns)

    if stage == cleaning.STAGE_HEADERS:
        return {"output": f"[SUCCESS] {result['description']}: "
                          f"{result['headers_changed']} header(s) changed."}
    return {"output": f"[SUCCESS] {result['description']}: {result['cells_changed']} cell(s) "
                      f"changed across {result['columns_cleaned']} column(s)."}


def _cmd_unique(dataset, args):
    """unique <columns> : the distinct values of each, numbered"""
    if not args:
        raise ValueError("Which column? e.g. unique 10, or unique 8:12")

    columns = _resolve_columns(dataset, args)
    blocks = []

    for listing in table.unique_values(dataset, columns):
        rows = "".join(
            f"<tr><td class='muted'>{entry['n']}</td>"
            f"<td>{_escape(entry['value'])}</td>"
            f"<td class='muted'>{entry['count']}</td></tr>"
            for entry in listing["values"]
        )
        note = []
        if listing["blank"]:
            note.append(f"{listing['blank']} blank")
        if listing["truncated"]:
            note.append(f"showing the first {len(listing['values'])}")

        blocks.append(
            f"<strong>{_escape(listing['column'])}</strong> — "
            f"{listing['distinct']} distinct value(s)"
            + (f" <span class='muted'>({', '.join(note)})</span>" if note else "")
            + "<table class='data-table'><thead><tr><th>#</th><th>Value</th><th>Rows</th>"
            f"</tr></thead><tbody>{rows}</tbody></table>"
        )

    return {"html": "<br>".join(blocks)
                    + "<span class='muted'>Use the number with: "
                      "map values &lt;column&gt; unique &lt;#&gt; \"new value\"</span>"}


# --- files on the machine running CPDM ------------------------------------
def _cmd_load(dataset, args):
    """load            : what is there to open
       load <file>     : open it"""
    if not args:
        files = workspace_files.listing()
        if not files:
            return {"output": f"Nothing to load yet. Put .xlsx or .csv files in "
                              f"{workspace_files.ensure_data_dir()} and try again."}
        rows = "".join(
            f"<tr><td>{_escape(entry['name'])}</td>"
            f"<td class='muted'>{entry['where']}</td>"
            f"<td class='muted'>{entry['size_kb']} KB</td></tr>"
            for entry in files
        )
        return {"html": f"<strong>{len(files)} file(s) you can load:</strong>"
                        "<table class='data-table'><thead><tr><th>File</th><th>Where</th>"
                        f"<th>Size</th></tr></thead><tbody>{rows}</tbody></table>"
                        f"<span class='muted'>Data folder: {_escape(workspace_files.DATA_DIR)}</span>"}

    path = workspace_files.resolve_readable(" ".join(args))
    with open(path, "rb") as handle:
        loaded = tabular_io.load_into(dataset, _Upload(handle, os.path.basename(path)))

    return {"output": f"[SUCCESS] Loaded '{loaded['filename']}' — {loaded['rows']} row(s), "
                      f"{len(loaded['cols'])} column(s). Anything previously open is closed."}


class _Upload:
    """Enough of a file upload for the reader that expects one."""

    def __init__(self, handle, filename):
        self._handle = handle
        self.filename = filename

    def read(self, *args):
        return self._handle.read(*args)

    def seek(self, *args):
        return self._handle.seek(*args)


def _cmd_save(dataset, args):
    """save            : write processed_<name> beside the data
       save <file>     : write that name (.xlsx or .csv)"""
    default = f"processed_{os.path.splitext(dataset.filename)[0]}.xlsx"
    name = " ".join(args) if args else default
    path = workspace_files.resolve_writable(name)

    fmt = "csv" if path.lower().endswith(".csv") else "xlsx"
    stream, _, _ = tabular_io.export(dataset, fmt)
    with open(path, "wb") as handle:
        handle.write(stream.getvalue())

    size = round(os.path.getsize(path) / 1024, 1)
    return {"output": f"[SUCCESS] Saved {len(dataset.df)} row(s) x "
                      f"{len(dataset.df.columns)} column(s) to {path} ({size} KB)."}


# --- map ------------------------------------------------------------------
def _one_column(dataset, spec):
    columns = _resolve_columns(dataset, spec)
    if len(columns) != 1:
        raise ValueError(f"'{spec}' matches {len(columns)} columns; name just one.")
    return columns[0]


def _cmd_map(dataset, args):
    if not args or args[0] not in ("headers", "values"):
        raise ValueError('Usage: map headers <n> <new name>   |   map values <n> "old" "new"')

    what, rest = args[0], args[1:]

    if what == "headers":
        if len(rest) < 2:
            raise ValueError("Usage: map headers <n> <new name>")
        column = _one_column(dataset, rest[0])
        new_name = " ".join(rest[1:]).strip()
        result = table.rename_columns(dataset, {column: new_name})
        return {"output": f"[SUCCESS] Column {rest[0]} renamed to '{new_name}'."
                if result["renamed"] else "[INFO] That is already its name."}

    if len(rest) < 3:
        raise ValueError('Usage: map values <column> "old" "new"   |   '
                         'map values <column> unique <#> "new"')

    column = _one_column(dataset, rest[0])
    how, rest = (rest[1].lower(), rest[2:]) if rest[1].lower() in ("unique", "string") \
        else ("string", rest[1:])

    if how == "unique":
        if len(rest) != 2:
            raise ValueError('Usage: map values <column> unique <#> "new value"')
        try:
            number = int(rest[0])
        except ValueError:
            raise ValueError(f"'{rest[0]}' is not a number from the unique list.") from None
        old, new = table.unique_value_at(dataset, column, number), rest[1]
    else:
        if len(rest) != 2:
            raise ValueError('Usage: map values <column> string "old" "new"')
        old, new = rest[0], rest[1]

    result = cleaning.replace_whole_cells(dataset, {old: new}, [column])
    if not result["cells_changed"]:
        # the usual cause is a tail nobody trimmed; show what is really there
        present = [str(value) for value in dataset.df[column].dropna().unique()[:4]]
        more = "; ..." if dataset.df[column].nunique() > 4 else ""
        return {"output": f"[INFO] No cell in '{column}' holds exactly '{old}'. "
                          f"It holds: {'; '.join(present)}{more}  —  "
                          f"'unique {rest[0] if how == 'unique' else column}' numbers them for you."}

    return {"output": f"[SUCCESS] Replaced '{old}' with '{new}' in "
                      f"{result['cells_changed']} cell(s) of '{column}'."}


# --- files on the machine running CPDM ------------------------------------
def _cmd_load(dataset, args):
    """load            : what is there to open
       load <file>     : open it"""
    if not args:
        files = workspace_files.listing()
        if not files:
            return {"output": f"Nothing to load yet. Put .xlsx or .csv files in "
                              f"{workspace_files.ensure_data_dir()} and try again."}
        rows = "".join(
            f"<tr><td>{_escape(entry['name'])}</td>"
            f"<td class='muted'>{entry['where']}</td>"
            f"<td class='muted'>{entry['size_kb']} KB</td></tr>"
            for entry in files
        )
        return {"html": f"<strong>{len(files)} file(s) you can load:</strong>"
                        "<table class='data-table'><thead><tr><th>File</th><th>Where</th>"
                        f"<th>Size</th></tr></thead><tbody>{rows}</tbody></table>"
                        f"<span class='muted'>Data folder: {_escape(workspace_files.DATA_DIR)}</span>"}

    path = workspace_files.resolve_readable(" ".join(args))
    with open(path, "rb") as handle:
        loaded = tabular_io.load_into(dataset, _Upload(handle, os.path.basename(path)))

    return {"output": f"[SUCCESS] Loaded '{loaded['filename']}' — {loaded['rows']} row(s), "
                      f"{len(loaded['cols'])} column(s). Anything previously open is closed."}


class _Upload:
    """Enough of a file upload for the reader that expects one."""

    def __init__(self, handle, filename):
        self._handle = handle
        self.filename = filename

    def read(self, *args):
        return self._handle.read(*args)

    def seek(self, *args):
        return self._handle.seek(*args)


def _cmd_save(dataset, args):
    """save            : write processed_<name> beside the data
       save <file>     : write that name (.xlsx or .csv)"""
    default = f"processed_{os.path.splitext(dataset.filename)[0]}.xlsx"
    name = " ".join(args) if args else default
    path = workspace_files.resolve_writable(name)

    fmt = "csv" if path.lower().endswith(".csv") else "xlsx"
    stream, _, _ = tabular_io.export(dataset, fmt)
    with open(path, "wb") as handle:
        handle.write(stream.getvalue())

    size = round(os.path.getsize(path) / 1024, 1)
    return {"output": f"[SUCCESS] Saved {len(dataset.df)} row(s) x "
                      f"{len(dataset.df.columns)} column(s) to {path} ({size} KB)."}


# --- map ------------------------------------------------------------------
def _one_column(dataset, spec):
    columns = _resolve_columns(dataset, spec)
    if len(columns) != 1:
        raise ValueError(f"'{spec}' matches {len(columns)} columns; name just one.")
    return columns[0]


def _cmd_map(dataset, args):
    if not args or args[0] not in ("headers", "values"):
        raise ValueError('Usage: map headers <n> <new name>   |   map values <n> "old" "new"')

    what, rest = args[0], args[1:]

    if what == "headers":
        if len(rest) < 2:
            raise ValueError("Usage: map headers <n> <new name>")
        column = _one_column(dataset, rest[0])
        new_name = " ".join(rest[1:]).strip()
        result = table.rename_columns(dataset, {column: new_name})
        return {"output": f"[SUCCESS] Column {rest[0]} renamed to '{new_name}'."
                if result["renamed"] else "[INFO] That is already its name."}

    if len(rest) < 3:
        raise ValueError('Usage: map values <column> "old" "new"   |   '
                         'map values <column> unique <#> "new"')

    column = _one_column(dataset, rest[0])
    how, rest = (rest[1].lower(), rest[2:]) if rest[1].lower() in ("unique", "string") \
        else ("string", rest[1:])

    if how == "unique":
        if len(rest) != 2:
            raise ValueError('Usage: map values <column> unique <#> "new value"')
        try:
            number = int(rest[0])
        except ValueError:
            raise ValueError(f"'{rest[0]}' is not a number from the unique list.") from None
        old, new = table.unique_value_at(dataset, column, number), rest[1]
    else:
        if len(rest) != 2:
            raise ValueError('Usage: map values <column> string "old" "new"')
        old, new = rest[0], rest[1]

    result = cleaning.replace_whole_cells(dataset, {old: new}, [column])
    if not result["cells_changed"]:
        # say what is actually there: the usual cause is a tail nobody trimmed
        present = [str(value) for value in dataset.df[column].dropna().unique()[:4]]
        return {"output": f"[INFO] No cell in '{column}' holds exactly '{old}'. "
                          f"It holds: " + "; ".join(present)
                          + ("; ..." if dataset.df[column].nunique() > 4 else "")
                          + f"  —  'unique {rest[0]}' numbers them for you."
                          if how == "string" else
                          f"[INFO] No cell in '{column}' holds exactly '{old}'."}
    return {"output": f"[SUCCESS] Replaced '{old}' with '{new}' in "
                      f"{result['cells_changed']} cell(s) of '{column}'."}


def _cmd_replace(dataset, args):
    """replace all "old" "new"       : everywhere
       replace <columns> "old" "new" : only there
       replace "old" "new"           : the same as all"""
    if len(args) == 2:
        scope, (old_value, new_value) = "all", args
    elif len(args) == 3:
        scope, old_value, new_value = args
    else:
        raise ValueError('Usage: replace all "old" "new"   |   '
                         'replace <columns> "old" "new"')

    columns = None if scope.lower() == "all" else _resolve_columns(dataset, scope)
    changed = cleaning.apply_value_replacements(
        dataset, {old_value: new_value}, columns
    )

    where = "every active text column" if columns is None else (
        f"'{columns[0]}'" if len(columns) == 1 else f"{len(columns)} columns")
    return {"output": f"[SUCCESS] Replaced '{old_value}' -> '{new_value}' "
                      f"as a substring in {changed} of {where}."}


HELP_SECTIONS = ("Looking", "Files", "Cleaning", "Editing", "The session")


def _spec(name, handler, section, usage, summary, needs_data=True, detail=None):
    return {"name": name, "handler": handler, "needs_data": needs_data,
            "section": section, "usage": usage, "summary": summary, "detail": detail}


#: the commands, in the order help prints them
COMMAND_ORDER = [(spec["name"], spec) for spec in [
    _spec("head", _cmd_head, "Looking", "head [n]",
          "The first n rows, five by default",
          detail="<code>head 20</code> shows twenty. The heading says how many of how "
                 "many, so a mistyped count is obvious."),
    _spec("tail", _cmd_tail, "Looking", "tail [n]",
          "The last n rows, five by default"),
    _spec("headers", _cmd_headers, "Looking", "headers [columns]",
          "The header row: position, type, how full, group and scale",
          detail="With no argument it lists every column. Give it a position, a range or "
                 "a pattern to narrow it: <code>headers 8:12</code>, <code>headers WB*</code>. "
                 "The positions it prints are what the other commands take."),
    _spec("info", _cmd_info, "Looking", "info",
          "File name, size, ignored columns, groups and scales"),
    _spec("unique", _cmd_unique, "Looking", "unique <columns>",
          "The distinct values of a column, numbered, with how often each occurs",
          detail="<code>unique 10</code> numbers the answers in that column; "
                 "<code>unique 8:12</code> does several at once.<br>"
                 "The numbers are a property of the column, not of the listing, so "
                 "<code>map values 10 unique 2 \"Agree\"</code> means the same thing "
                 "however long ago you printed it. Numbers sort numerically, text "
                 "alphabetically."),
    _spec("summary", _cmd_summary, "Looking", "summary",
          "Count, mean, spread and quartiles for the numeric columns"),
    _spec("groups", _cmd_groups, "Looking", "groups",
          "The group and subgroup tree, and the scale each group backs"),
    _spec("scales", _cmd_scales, "Looking", "scales",
          "Each scale with its items and its scored options"),

    _spec("load", _cmd_load, "Files", "load [file]",
          "List the files on this machine, or open one", needs_data=False,
          detail="These are files where CPDM is running, not on the computer whose browser "
                 "is open — File → Open is the one that uploads from there. Reading and "
                 "writing stay inside the data folder and the read-only samples; a name "
                 "that points outside them is refused."),
    _spec("save", _cmd_save, "Files", "save [file]",
          "Write the table back out beside the data",
          detail="Without a name it writes <code>processed_&lt;file&gt;.xlsx</code>. The "
                 "extension chooses the format: <code>.xlsx</code> or <code>.csv</code>."),

    _spec("clean", _cmd_clean, "Cleaning", "clean rules | values | headers …",
          "Apply a trimming rule to the values or the header text",
          detail="<code>clean rules</code> lists the rules and what each one needs.<br>"
                 "<code>clean values cut 8:16 /</code> cuts those columns at the first "
                 "slash; <code>clean headers cut 1:17 /</code> does the same to the header "
                 "text. The word <em>values</em> may be left out.<br>"
                 "Several delimiters may follow a rule — <code>clean values cut 8:16 / ( -</code> "
                 "cuts at whichever comes first. These are the rules from Clean → Remove "
                 "Non-English, without its preview, so check with <code>head</code> after."),

    _spec("map", _cmd_map, "Editing", 'map headers|values …',
          "Change one header, or one answer in one column",
          detail="<code>map headers 3 Age</code> renames the third column.<br>"
                 "<code>map values 4 \"old\" \"new\"</code> replaces an answer in that "
                 "column only, matched <strong>whole</strong>; if nothing matches it says "
                 "what the column does hold, which is usually a tail nobody has trimmed."),
    _spec("replace", _cmd_replace, "Editing", 'replace all|<columns> "old" "new"',
          "Substring replacement, everywhere or in the columns named",
          detail="<code>replace all \"old\" \"new\"</code> touches every active text "
                 "column; <code>replace 8:12 \"old\" \"new\"</code> only those. Saying "
                 "neither is the same as <em>all</em>.<br>"
                 "It matches anywhere <em>inside</em> a cell, which is what makes it useful "
                 "for a stray fragment and dangerous for a whole answer — for one answer "
                 "use <code>map values</code>, and for coding a scale use "
                 "Scales → Assign Scoring."),

    _spec("docs", _cmd_docs, "The session", "docs",
          "Links to every Theory and Help page", needs_data=False),
    _spec("help", _cmd_help, "The session", "help [command]",
          "This list, or one command in full", needs_data=False),
    _spec("clear", _cmd_clear, "The session", "clear",
          "Empty the output pane", needs_data=False),
]]

#: older names kept working, and listed under the command they point at
ALIASES = {"show": "head", "columns": "headers"}

COMMANDS = {name: spec for name, spec in COMMAND_ORDER}
COMMANDS.update({alias: COMMANDS[target] for alias, target in ALIASES.items()})


def _split_for_completion(line):
    """Tokens so far, and the partial token being typed (empty after a space)."""
    try:
        tokens = shlex.split(line, comments=True)
    except ValueError:                      # an unbalanced quote while typing
        tokens = line.split()

    if line.endswith((" ", "\t")):
        return tokens, ""
    return tokens[:-1], (tokens[-1] if tokens else "")


def _column_names(dataset):
    return [str(col) for col in dataset.df.columns] if dataset.df is not None else []


def _candidates_for(dataset, tokens):
    """What could come next, given the tokens already typed."""
    if not tokens:
        return sorted(COMMANDS)

    command, rest = tokens[0].lower(), tokens[1:]

    if command == "clean":
        if not rest:
            return list(CLEAN_TARGETS) + sorted(CLEAN_RULES)
        if rest[0] in ("headers", "values"):
            return sorted(CLEAN_RULES) if len(rest) == 1 else (
                _column_names(dataset) if len(rest) == 2 else [])
        if rest[0] in CLEAN_RULES:
            return _column_names(dataset) if len(rest) == 1 else []
        return []

    if command == "map":
        if not rest:
            return ["headers", "values"]
        if len(rest) == 1:
            return _column_names(dataset)
        if len(rest) == 2 and rest[0] == "values":
            return ["unique", "string"]
        return []

    if command == "unique":
        return _column_names(dataset) if not rest else []

    if command == "replace":
        return (["all"] + _column_names(dataset)) if not rest else []

    if command in ("headers", "columns"):
        return _column_names(dataset) if not rest else []

    if command == "help":
        return sorted(COMMANDS) if not rest else []

    if command == "load":
        return [entry["name"] for entry in workspace_files.listing()] if not rest else []

    if command == "save":
        if rest or dataset.df is None:
            return []
        stem = os.path.splitext(dataset.filename)[0]
        return [f"processed_{stem}.xlsx", f"processed_{stem}.csv"]

    return []


def complete(dataset, line):
    """Candidates for the token being typed — what the Tab key offers."""
    tokens, partial = _split_for_completion(line or "")
    lowered = partial.lower()

    candidates = [
        candidate for candidate in _candidates_for(dataset, tokens)
        if candidate.lower().startswith(lowered)
    ]

    # the common prefix is what Tab can safely fill in without choosing for you
    shared = os.path.commonprefix(candidates) if candidates else ""
    return {"prefix": partial, "candidates": candidates[:60],
            "total": len(candidates), "common": shared}


def execute(dataset, command):
    """Parse and run one console command.

    ``#`` starts a comment, so a line can be annotated or a command parked
    without deleting it; shlex keeps a ``#`` that sits inside quotes, where it
    belongs to the data rather than to the comment.
    """
    command = (command or "").strip()
    if not command:
        return {"output": ""}

    try:
        parts = shlex.split(command, comments=True)
    except ValueError as exc:
        return {"error": f"Parsing error: {exc}"}

    if not parts:                        # the whole line was a comment
        return {"output": ""}

    name, args = parts[0].lower(), parts[1:]
    spec = COMMANDS.get(name)
    if spec is None:
        close = [known for known in sorted(COMMANDS) if known.startswith(name[:2])]
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        return {"error": f"Unknown command '{name}'. Type 'help' for the list.{hint}"}

    handler = spec["handler"]
    if spec["needs_data"] and dataset.df is None:
        return {"error": "No dataset loaded. Use 'load' to open one, "
                         "or File -> Open to upload it."}

    try:
        return handler(dataset, args)
    except Exception as exc:  # surfaced in the log pane rather than a 500
        return {"error": str(exc)}
