"""The text console: small commands typed into the workspace prompt.

Each handler returns a dict the browser understands: ``output`` for plain text,
``html`` for markup, ``error`` for a red line, ``clear`` to wipe the log.
"""

import shlex

from cpdm.core import cleaning, docs_library, groups
from cpdm.core.dataset import DEMOGRAPHICS, SCALE_PREFIX

HELP_TEXT = """Available Commands:
 - show/head                   : Displays the first 5 rows
 - info                        : Shows dataset shape, scales & categories
 - groups                      : Shows the field group / subgroup tree
 - summary                     : Descriptive statistics
 - columns                     : Lists all columns
 - docs                        : Lists the Theory & Help documentation pages
 - replace "old" "new"         : Globally replaces 'old' text with 'new' text
 - clear                       : Clears output terminal
 - help                        : Shows this list"""


def _cmd_help(_dataset, _args):
    return {"output": HELP_TEXT}


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


def _cmd_show(dataset, _args):
    table = dataset.df.head().to_html(classes="data-table", index=False)
    return {"html": f"<strong>Dataset Preview (First 5 Rows):</strong><br>{table}"}


def _cmd_columns(dataset, _args):
    cols = list(dataset.df.columns)
    return {"output": f"Columns ({len(cols)}): " + ", ".join(str(c) for c in cols)}


def _cmd_info(dataset, _args):
    demographics = dataset.columns_by_category(DEMOGRAPHICS)

    grouped = {}
    for col, category in dataset.categories.items():
        if category.startswith(SCALE_PREFIX.strip()):
            grouped.setdefault(category.replace(SCALE_PREFIX, ""), []).append(col)

    lines = [
        f"Dataset File: {dataset.filename}",
        f"Dimensions  : {dataset.df.shape[0]} rows x {dataset.df.shape[1]} columns",
        f"Demographics: {', '.join(demographics) if demographics else 'None'}",
        f"Ignored Cols: {len(dataset.ignored_columns)}",
        f"Defined Scales ({len(dataset.defined_scales)}): {', '.join(dataset.defined_scales)}",
    ]
    for scale_name, cols in grouped.items():
        lines.append(f"  - [{scale_name}]: {', '.join(cols)}")
    return {"output": "\n".join(lines) + "\n"}


def _cmd_groups(dataset, _args):
    lines = groups.summary(dataset)
    if not lines:
        return {"output": "No field groups yet. Build them in Fields -> Groups.\n"}
    return {"output": "Field Groups:\n" + "\n".join(lines) + "\n"}


def _cmd_summary(dataset, _args):
    table = dataset.df.describe().to_html(classes="data-table")
    return {"html": f"<strong>Descriptive Statistics:</strong><br>{table}"}


def _cmd_replace(dataset, args):
    if len(args) != 2:
        return {"error": 'Invalid syntax. Usage: replace "old text" "new text"'}
    old_value, new_value = args
    cleaning.apply_value_replacements(dataset, {old_value: new_value})
    return {
        "output": f"[SUCCESS] Replaced '{old_value}' -> '{new_value}' "
                  "globally across all active text columns."
    }


# name -> (handler, needs a loaded dataset)
COMMANDS = {
    "help": (_cmd_help, False),
    "docs": (_cmd_docs, False),
    "show": (_cmd_show, True),
    "head": (_cmd_show, True),
    "columns": (_cmd_columns, True),
    "info": (_cmd_info, True),
    "groups": (_cmd_groups, True),
    "summary": (_cmd_summary, True),
    "replace": (_cmd_replace, True),
}


def execute(dataset, command):
    """Parse and run one console command."""
    command = (command or "").strip()
    if not command:
        return {"output": ""}
    if command == "clear":
        return {"clear": True}

    try:
        parts = shlex.split(command)
    except ValueError as exc:
        return {"error": f"Parsing error: {exc}"}

    name, args = parts[0].lower(), parts[1:]
    entry = COMMANDS.get(name)
    if entry is None:
        return {"error": f"Unknown command '{command}'. Type 'help' for options."}

    handler, needs_data = entry
    if needs_data and dataset.df is None:
        return {"error": "No dataset loaded. Open a data file first."}

    try:
        return handler(dataset, args)
    except Exception as exc:  # surfaced in the log pane rather than a 500
        return {"error": str(exc)}
