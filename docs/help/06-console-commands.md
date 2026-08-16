# Console Commands

The prompt at the bottom of the workspace takes short commands. Press Enter to run one; the arrow keys walk back through what you have already typed.

`help` lists them grouped by what they are for, and **`help <command>`** explains one in full — its exact usage, the things worth knowing about it, and any older name it still answers to. It is quicker than this page when you only need to check an argument.

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

## Completion

**Tab** completes the word you are typing. It knows the commands, the first level of
`clean`, its rule names, your column names, and the files `load` can open — so `clean v`
Tab `cut` Tab then Tab again lists the columns to choose from. A unique match is filled in
whole; an ambiguous one fills in as far as the candidates agree and lists them in the log.

Column names with spaces are quoted for you.

## Files

`load` and `save` act on **the machine running CPDM**, not on the machine whose browser is
open. They are confined to a data folder — `CPDM_DATA_DIR` if you set it, otherwise
`data/` beside the project, created on first use — plus the bundled `samples/`, which is
read-only. A name that tries to climb out of those folders is refused.

| Command | What it does |
| --- | --- |
| `load` | Lists what is there to open, from the data folder and the samples |
| `load <file>` | Opens it, closing whatever was open before |
| `save` | Writes `processed_<name>.xlsx` into the data folder |
| `save <file>` | Writes that name; `.xlsx` or `.csv` decides the format |

File → Open and File → Export are the other half of this: they move files between your own
machine and the workspace through the browser. `load` and `save` are for the files already
sitting on the server, which is the useful pair when CPDM is hosted rather than run
locally.

## Looking

| Command | What it does |
| --- | --- |
| `head [n]` | The first n rows, 5 by default. `show` is the old name and still works. |
| `tail [n]` | The last n rows. |
| `headers [spec]` | The header row as a table: position, name, type, filled and blank counts, distinct values, group and scale. With a spec, just those columns. `columns` is the old name. |
| `unique <spec>` | The distinct values of each column, **numbered**, with how many rows hold each. |
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

The first word after `clean` says what it works on:

```
clean rules                        # the table above
clean values cut 8:16 /            # the item columns, cut at the first slash
clean values tidy 8:16             # then clear the debris that leaves
clean headers cut 1:17 /           # the same to the header text
```

`values` may be left out — `clean cut 8:16 /` means the same thing. Several delimiters can follow the rule: `clean values cut 8:16 / ( -` cuts at whichever comes first. These are the same rules as [Clean → Remove Non-English](/docs/help/cleaning-workflow), without the preview — so check with `head` afterwards.

## Changing one thing

```
unique 4                              # 1  Female / സ്ത്രീ   12
                                      # 2  Male / പുരുഷൻ     18
map values 4 unique 2 "Male"          # take number 2, call it Male
map values 4 string "Female / സ്ത്രീ" "Female"
map headers 3 Age
```

| Command | What it does |
| --- | --- |
| `map headers <n> <new name>` | Renames the column at position n. Groups, scales and remembered answers follow it. |
| `map values <n> unique <#> "new"` | Replaces the numbered value from `unique <n>`, in that column only. |
| `map values <n> string "old" "new"` | Spells the old value out instead. The word `string` may be left out. |
| `replace all "old" "new"` | Substring replacement across every active text column. |
| `replace <spec> "old" "new"` | The same, but only in the columns named. Saying neither `all` nor a spec means `all`. |

**The numbers `unique` prints belong to the column, not to the listing.** They are worked out afresh each time from the column's own values — sorted numerically if they are numbers, alphabetically otherwise — so `map values 10 unique 2` means the same thing whether you printed the list a second ago or in another browser. They do of course follow the data: once you have renamed value 2, the list is different.

`map values` matches the **whole cell**, so `map values 4 "Male" "M"` does nothing when the cell actually reads `Male / പുരുഷൻ` — and it says what the column does hold, and points at `unique`. `replace` is the blunt instrument: it matches anywhere *inside* a cell, which is what makes it right for a stray fragment and wrong for a whole answer.

All of these are recorded in the cleaning recipe, so they replay on the next wave.

## Reading the log

| Colour | Meaning |
| --- | --- |
| Blue | Something started, or a hint. |
| Green | `[SUCCESS]` — it completed, usually with a count. |
| Red | It failed and nothing changed. |

Counts are worth reading: *"147 cell(s) changed across 5 column(s)"* tells you whether your column range was the one you meant. The pane trims itself to the number of lines set in [Preferences](/docs/help/preferences).
