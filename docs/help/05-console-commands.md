# Console Commands

The prompt at the bottom of the workspace takes short commands. Press Enter to run one; the arrow keys walk back through what you have already typed.

| Command | What it does |
| --- | --- |
| `help` | Lists these commands. |
| `show` / `head` | Prints the first five rows as a table. |
| `info` | File name, dimensions, demographic columns, ignored-column count, and every scale with its items. |
| `summary` | Descriptive statistics for the numeric columns (count, mean, sd, min, quartiles, max). |
| `columns` | Column count, then every column name. |
| `docs` | Links to the Theory and Help pages. |
| `replace "old" "new"` | Replaces text globally across all active text columns. |
| `clear` | Empties the output log. |

## `replace` in detail

```
replace "Strongly Agree / പൂർണ്ണമായും യോജിക്കുന്നു" "5"
```

Both arguments must be quoted if they contain spaces, and non-Latin text is fine inside the quotes. The rules are the same as in the cleaning wizard: the replacement is literal (not a regular expression), applies as a substring anywhere in the cell, skips numeric columns, and skips any column you unticked in Clean → Header Mapping.

Unlike the wizard, `replace` does not show you what it is about to change. It is quickest for a fix you have already spotted — a stray spelling, one leftover label.

Everything you do with `replace` is recorded in the cleaning recipe under `_global`, so it is included when you save a cleaning file.

## Reading the log

| Colour | Meaning |
| --- | --- |
| Blue | Something started, or a hint. |
| Green | `[SUCCESS]` — the action completed, usually with a count. |
| Red | The action failed and nothing was changed. |

Counts in the success lines are worth reading: *"cleaned cell values across 12 column(s)"* tells you whether your exemptions did what you expected.
