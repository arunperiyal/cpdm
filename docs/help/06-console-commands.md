# Console Commands

The prompt at the bottom of the workspace takes short commands. Press Enter to run one; the arrow keys walk back through what you have already typed.

Anything after a `#` is a comment, so you can annotate a line, or park a command without deleting it:

```
clean cut 8:16 /        # strip the Malayalam from the item columns
# map values 4 "Male / പുരുഷൻ" "Male"   -- not yet, check the wave 2 file first
```

A `#` inside quotes belongs to the data, not to a comment, so `map values 1 "day #1" "day one"` works as written.

## Naming columns

Everywhere a command takes columns, it takes the same spec as the group editor:

| You type | You get |
| --- | --- |
| `7` | the seventh column |
| `7:15` | columns 7 to 15 |
| `Age` | the column of that name, case-insensitively |
| `WB*` | every column whose name starts with `WB` |

`headers` prints the positions, so it is the natural first command of any session.

## Looking

| Command | What it does |
| --- | --- |
| `head [n]` | The first n rows, 5 by default. `show` is the old name and still works. |
| `tail [n]` | The last n rows. |
| `headers [spec]` | The header row as a table: position, name, type, filled and blank counts, distinct values, group and scale. With a spec, just those columns. `columns` is the old name. |
| `info` | File name, dimensions, ignored columns, group count and the scales. |
| `summary` | Descriptive statistics for the numeric columns. |
| `groups` | The group and subgroup tree, and the scale each group backs. |
| `scales` | Each scale with its items and its scored options. |
| `docs` | Links to every documentation page. |
| `clear` | Empties the output pane. |

## Cleaning

`clean rules` lists what is available and what each rule still needs:

| Rule | What it does | Extra argument |
| --- | --- | --- |
| `cut` | Cut at the first delimiter, keeping what comes before it | the delimiter |
| `cut-after` | Cut at the first delimiter, keeping what comes after it | the delimiter |
| `cut-non-english` | Cut from the first non-English character to the end | — |
| `strip` | Remove non-English characters wherever they appear | — |
| `tidy` | Drop stray brackets and separators, collapse spaces | — |

```
clean cut 8:16 /              # the item columns, cut at the first slash
clean tidy 8:16               # then clear the debris that leaves
clean headers cut 1:17 /      # the same to the header text
```

Put `headers` first to clean the header row instead of the values. Several delimiters can follow the rule: `clean cut 8:16 / ( -` cuts at whichever comes first. These are the same rules as [Clean → Remove Non-English](/docs/help/cleaning-workflow), without the preview — so check with `head` afterwards.

## Changing one thing

| Command | What it does |
| --- | --- |
| `map headers <n> <new name>` | Renames the column at position n. Groups, scales and remembered answers follow it. |
| `map values <n> "old" "new"` | Replaces an answer in that column only, matched **whole**. |
| `replace "old" "new"` | Substring replacement across every active text column. |

`map values` matches the whole cell, so `map values 4 "Male" "M"` does nothing if the cell actually reads `Male / പുരുഷൻ` — and it tells you what the column does hold, which is usually a tail nobody has trimmed yet. `replace` is the blunt instrument: it matches anywhere inside a cell, in every column at once.

Both are recorded in the cleaning recipe, so they replay on the next wave.

## Reading the log

| Colour | Meaning |
| --- | --- |
| Blue | Something started, or a hint. |
| Green | `[SUCCESS]` — it completed, usually with a count. |
| Red | It failed and nothing changed. |

Counts are worth reading: *"147 cell(s) changed across 5 column(s)"* tells you whether your column range was the one you meant. The pane trims itself to the number of lines set in [Preferences](/docs/help/preferences).
