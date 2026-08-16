# Comprehensive Package for Data Management (CPDM)

A local Flask web workspace for preparing survey / questionnaire datasets. CPDM gives you
a menu-driven UI plus a small command console for cleaning messy headers and values,
grouping columns into psychometric scales, reverse-scoring items, and computing row-level
scale statistics — then exporting the result to `.xlsx` or `.csv`.

Everything runs on your own machine. The app opens your browser at
`http://127.0.0.1:5000/` and keeps the working dataset in memory for the life of the
process. Built-in documentation (Theory and Help) is served at `/docs`.

---

## Running it

```bash
pip install -r requirements.txt
python app.py
```

Python 3 with Flask, pandas and openpyxl. The optional `markdown` package improves the
rendering of the documentation pages; without it CPDM uses its own built-in renderer.

Environment overrides: `CPDM_HOST`, `CPDM_PORT`, `CPDM_DEBUG`, `CPDM_NO_BROWSER`,
`CPDM_DOCS_DIR`, `CPDM_SAMPLES_DIR`.

### Running it as a service

`cpdmctl.sh` hosts the workspace so it is there whenever you want it:

```bash
./cpdmctl.sh start                  # run it now, in the background
./cpdmctl.sh status                 # is it up, and on what URL
./cpdmctl.sh stop
./cpdmctl.sh update                 # git pull, then restart onto the new code

./cpdmctl.sh install                # write a systemd unit, enable it, start it
./cpdmctl.sh uninstall              # stop, disable and remove that unit
```

Without a unit installed, `start`/`stop` manage a background process with a pid file in
`~/.local/state/cpdm`; once `install` has run, the same commands drive systemd, and each
one says which it is using. `logs` follows either the journal or the log file.

| Option | |
| --- | --- |
| `--user` / `--system` | Per-user unit in `~/.config/systemd/user` (default, no sudo), or a system-wide one in `/etc/systemd/system` |
| `--host`, `--port` | Where to bind — default `127.0.0.1:5000` |
| `--python PATH` | Which interpreter to run under |
| `--gunicorn` | Serve through gunicorn instead of Flask's development server |
| `--linger` | With `install --user`: keep the service running when you log out |
| `--dry-run` | Print the unit file instead of writing it |

The service always runs **one worker**: CPDM keeps its dataset in the process, so a second
worker would answer from a different in-memory dataset.

#### Leaving it running

```bash
./cpdmctl.sh install --linger                    # this machine only
./cpdmctl.sh install --linger --host 0.0.0.0     # reachable from the LAN
```

`--linger` runs `loginctl enable-linger`, without which a user service stops when you log
out. With it, the unit starts at boot and stays up. `--system` is the alternative — no
linger needed — but a system unit reads the project as your user, so it will not see a
home directory that is only decrypted at login.

The unit declares `RequiresMountsFor` on the project directory, so a project on a second
drive waits for that filesystem instead of failing at boot, and `Restart=always` brings it
back if it ever exits.

When bound past loopback, `start` and `status` list the addresses it is reachable on and
print the `ufw`/`firewalld` command to open the port.

#### Who can reach it

The default `127.0.0.1` is reachable only from this machine. CPDM has no login and no
access control, so anyone who can reach the port can read, change and export the loaded
dataset — bind it wider only on a network you trust. For anything less trusted, keep it on
loopback and put an authenticating reverse proxy in front.

New to the tool? Download `samples/sample_survey.xlsx` (Help → Sample Data Files) and
follow [docs/help/01-getting-started.md](docs/help/01-getting-started.md), which is also
readable in the app at `/docs/help/getting-started`.

---

## Current capabilities

### File

| Action | What it does |
| --- | --- |
| **Open (.xlsx / .csv)** | Loads `.xlsx`, `.xlsm`, `.csv` or `.tsv` with pandas. Reports filename, row count and column count. All columns start as `Uncategorised`, and any previous session state is reset. |
| **Export (.xlsx)** | Downloads the current dataframe as `processed_<name>.xlsx`, sheet `Processed_Data`. |
| **Export (.csv)** | The same table as UTF-8 CSV. |

Only the first sheet of a workbook is read.

**Preferences** — how the workspace looks and behaves, applied as you choose them and kept
in the browser rather than on the server, so several people sharing one hosted workspace
each keep their own:

| | |
| --- | --- |
| Theme | Dark, Light, High contrast, or Match the system |
| Interface font | Default, system UI, serif, monospace, or wide-spaced with plain letterforms |
| Text size | 11–22px, scaling the whole interface and the docs |
| Density | Comfortable or Compact |
| Motion | Full or Reduced (also honoured from the system setting) |
| Rows per page | What Table → Rows shows at a time |
| Keep in the log | Trim the output pane so a long session stays quick |

Every colour in the app comes from a variable in `static/css/theme.css`, so a theme is a
palette swap rather than a stylesheet edit; a test fails if any stylesheet hard-codes a
colour or uses a variable no palette defines.

### Clean

**Header Mapping & Value Replacement** — a two-step wizard:

1. *Header mapping & column selection.* Every column is listed with an editable box for
   its new name and a checkbox. Unchecking a column marks it **ignored**, excluding it
   from all later value replacement. Renames are applied to the dataframe and recorded in
   the cleaning recipe; categories and the ignore list follow their columns through the
   rename.
2. *Text value replacement.* CPDM collects every distinct non-numeric text value across
   the active columns and shows each with the columns it appears in. Applying a mapping
   replaces the value **globally, as a literal substring**, in every active text column;
   longer values are applied first so `Agree` cannot eat the tail of `Strongly Agree`.
   Values already mapped are hidden on later passes. Numeric columns, numbers stored as
   text, blanks and `nan`/`none`/`null` are skipped.

**Remove Non-English / Trim Text** — a three-stage wizard: stage 1 cleans the header row,
stage 2 the cell values, stage 3 the leftovers. The first two take an **ordered chain of
rules** plus the columns to apply them to, and preview the result before anything is
written. **Preview**, **Apply** and **Continue** are separate buttons: applying keeps you
on the stage so one chain can follow another.

- *Cut from the first non-English character to the end* — `WhatsApp (വാട്സാപ്പ്)` → `WhatsApp (`
- *Cut at a delimiter* — several delimiters at once (`/ ( -`), cutting at whichever comes first, keeping the text **before** or **after** it
- *Strip non-English characters* — removes them wherever they appear
- *Tidy up leftovers* — drops dangling brackets and separators, removes empty `()`, collapses spaces: `WhatsApp (` → `WhatsApp`

"Non-English" means outside the Latin script and ordinary punctuation, so `café`, `₹500`,
dashes and curly quotes survive; a per-rule **strict ASCII** toggle restores the older
behaviour that removed those too.

The column picker is keyboard-driven, with the keys listed across the top of the dialogue:
it opens focused on the search box, **Enter** takes every column matching the filter
(**Shift+Enter** drops them), **↓** moves into the list, **Space** ticks, **Shift+Space**
extends, **Ctrl+A** takes everything listed and **Esc** clears the filter. Shift-click
still works, and the same keys drive the Fields → Groups picker. Numeric columns are
excluded from the values stage automatically.

**Stage 2 aims by group**: your field groups appear as chips above the column list — click
to take or drop a group, double-click for only that one — since values usually need
different rules per construct. With no groups yet, the stage says so and points at
Fields → Groups. **Preview** compares **Now** — the data as it stands, not as the file arrived — with
**After these rules**: every header, warning about collisions (`Name` → `Name_1`) and
about rules that would empty a header, or for values the changed-cell count per column
with up to five examples. The count is echoed in a status line beside the buttons.

**Stage 3** lists every header and distinct value that still holds a non-English character
— the free-text answer in another script, the header nobody standardised — with the
offending characters highlighted and, for values, the cell count and columns. Edit them by
hand and apply: headers are renamed, and values are replaced **only where a cell matches
exactly**, so fixing `Agree` cannot touch `Strongly Agree`. Both are recorded in the
cleaning recipe and replay with it.

The ⚡ button inside the header-mapping wizard opens the same wizard at its values stage.

**Save Cleaning File (.json)** — exports the recorded recipe as `cleaning_rules.json`:
an ordered `steps` log (text rules, header maps, value replacements) plus the flat
`header_map` / `value_replacements` / `ignored_columns` keys for readability.

**Apply Cleaning File (.json)** — replays a saved recipe against the loaded dataset, step
by step in the order they were performed, so trimming, renaming and coding all reproduce.
This is how a second wave of the same survey gets cleaned identically to the first.
Version 1 recipes — the older flat format, including `samples/sample_cleaning_rules.json`
— still replay through the original code path.

### Fields

**Groups** — one dialogue, two tabs, for organising columns. A **group** names a set of
columns; a **subgroup** holds a subset of its parent's columns, at any depth of nesting.
Grouping says nothing about analysis: whether a group's columns are a scale is declared
separately under Scales → Create Scale, so the two can be edited independently.

*Build groups* creates and edits groups: pick columns by ticking them, or type a spec —
names (`WB1, DS2`), inclusive ranges by name or position (`WB1:WB5`, `8:16`), single
positions (`12`), globs (`WB*`). **Positions count within the list you are choosing
from**: at the root that is the table, but inside a group holding table columns 8–16 the
spec `1:4` means that group's first four columns — table columns 8–11. The picker
numbers every row and shows the table position alongside when the two differ. An exact
column name always beats the other readings, and the editor reports what matched, what
didn't, and anything outside the parent group.

*Assign columns* is the fast route on a wide table: one row per column with a dropdown of
the whole tree, a search box, an *only ungrouped* filter, and a running count of how many
columns are still unfiled. Choosing a subgroup files the column under its parent too.

A column belongs to one group per level (reassigning moves it and says so), shrinking a
group trims its subgroups, and renames of a scale's items are followed automatically. Deleting
a group removes its subgroups and any scale declared on them. `groups` at the prompt
prints the tree, with the scale each group backs.

### Table

Direct operations on the data, none of them recorded in the cleaning recipe and none
reversible — export first if unsure.

**Header** — every column with its position, type, filled/blank counts, distinct values
and the group and scale it belongs to; rename a column outright from here, with groups,
keying and remembered answers following it. Names that would collide are refused.

**Rows** — a paged view, 25 at a time. Rows carry a stable label that survives sorting and
filtering, so a ticked row stays the row you meant. Delete ticked rows, drop wholly blank
rows, or drop rows that repeat an earlier one exactly.

**Columns** — reorder with the arrows (the order here is the export order) or delete
columns and their data; a deleted column leaves any group that held it.

**Sort** — by one column or several, the later ones breaking ties. Text sorts
case-insensitively, numbers sort as numbers, and the scores already computed travel with
their rows.

**Filter** — tests of the form *column · comparison · value*, combined with **every** or
**any**, then **keep** or **drop** the rows that match. **Count matches** reports how many
rows are involved, and what would remain either way, before anything is deleted.

### Scales

**Create Scale** — declares that a group's columns are one instrument. Pick the group; the
scale takes its columns, and its name unless you give a different one (group `PHQ` can
back scale `PHQ-9`). A group at any depth can carry a scale, so a container holding `PHQ`
and `GAD` yields two scales rather than one; where scales sit on nested groups the deepest
wins the columns they share. Deleting a scale leaves its group and columns untouched. The
same dialogue lists what is declared, and `scales` at the prompt prints it.

Together, groups and scales give every column its category — `Scale: <name>` for the
deepest scale holding it, `Uncategorised` otherwise — which is what the tools below read.

A scale describes itself in two parts, both taken from its group and shown as soon as you
pick one: **Items** are its columns — the questions — and **Options** are its response
set, seeded from the values actually in the data. Answers that are already numbers arrive
in numeric order, scored as themselves.

**Assign Scoring** — the ordered option list, each with a score. Reorder with ↑ ↓ into
response order, then *Number 1…n* (or *n…1*) fills the scores in. Add an option nobody
happened to choose, re-scan for answers that appeared after further cleaning, or remove
one. Leaving a score **blank** marks that answer as missing by design — *Not applicable*
— and keeps it out of the scale's range.

**Assign Scoring Type** — *Direct* or *Reverse* per item, with all-direct / all-reverse
buttons. There is no maximum to type: reverse items use `min + max − value` from the
scale's own option scores, so a 1–7 scale reverses as `8 − value` without being told.

**Scoring is applied as you define it** — there is no apply step. Saving the options or
the item types scores that scale's columns immediately, **within its own columns only**.
It is safe to redo: the answers each item held before it was first scored are kept, and
every pass recomputes from those rather than from the numbers already in the column, so
changing a score or a keying gives the right result and saving twice changes nothing.
Deleting a scale puts the answers back.

**View Scoring** — per item: its keying, how many cells are scored, how many blank, and
any answer no option covers (those cells are blank).

**Rename items** — a scale can rename its own columns to `<scale>_1`, `<scale>_2`, … in
column order, either as a checkbox when the scale is created or later with a prefix of
your choosing. Clashes with columns outside the scale are refused.

**Save Scale / Load Scale (.json)** — a scale definition is portable: its items and their
keying, and its ordered options with their scores. Loading matches each saved scale to a
group here by name, then by columns, then by building the group from the saved column
names; where none of those work the dialogue lists what the file holds and lets you pick
the group. Keying travels by column name and falls back to **position**, so an instrument
keeps its reverse-keyed items in the right places even under different headers. Loading
scores the data as it goes.

### Compute

**Row Calculations** — pick a subset of scale columns, a target column name and a
function: **mean**, **sum**, **min**, **max** or **std**. The result is added as a new
`Uncategorised` column computed row-wise; non-numeric cells become blanks and blanks are
skipped rather than counted as zero.

### Help

**Documentation Browser** (`/docs`) — a two-pane reader for the Markdown in `docs/`, with
a sidebar of Theory and Help pages plus download links for the sample data. Individual
pages also open in a modal inside the workspace from the Help menu, and the console
command `docs` prints links to all of them.

**Sample Data Files** — lists `samples/` with descriptions and download links.

**About CPDM** — a read-only card: what the app is, its version, **the commit it is
actually running**, the licence as the repository actually states it, the contributors,
what it is running on, and what is loaded right now. The commit line answers the question
a hosted copy raises: whether the update you pulled is the code that is serving.

Static files are served with a stamp that changes when the file does, so a browser cannot
keep running yesterday's JavaScript against today's API.

### Command console

| Command | Result |
| --- | --- |
| `head [n]` / `tail [n]` | First or last n rows, 5 by default (`show` is the old name for `head`) |
| `headers [spec]` | The header row as a table — position, name, type, filled/blank, distinct, group, scale — all of it or just the columns named |
| `info` | Filename, dimensions, ignored columns, groups and scales |
| `summary` | `describe()` descriptive statistics |
| `groups` / `scales` | The group tree; the scales and their options |
| `clean rules` | What `clean` can do and what each rule needs |
| `clean values\|headers <rule> <cols> [arg]` | Apply a cleaning rule to the values or the header text of those columns (`values` may be left out) |
| `load [file]` / `save [file]` | List or open a file **on the server**, and write the table back out |
| `map headers <n> <name>` | Rename the column at position n |
| `map values <n> "old" "new"` | Replace a whole answer, in that column only |
| `replace "old" "new"` | Substring replacement across active text columns |
| `docs` | Links to every documentation page |
| `clear` | Clears the output pane |

Anything after `#` is a comment; a `#` inside quotes belongs to the data. Columns are named
the same way as in the group editor — `7`, `7:15`, a name, or `WB*` — and `headers` prints
the positions. **Tab** completes commands, `clean` targets and rules, column names and
loadable files, filling in a unique match and listing an ambiguous one.

`load` and `save` act on the machine running CPDM, confined to a data folder
(`CPDM_DATA_DIR`, or `data/` beside the project) plus the read-only `samples/`; a name that
points outside them is refused. That matters on a hosted copy, where the browser and the
files are on different machines and nothing asks who is asking.

Arrow-up / arrow-down walk through command history. All output — results, successes and
errors — is appended to the scrolling log pane.

---

## Documentation

Markdown in `docs/`, rendered by the app and readable directly on disk. A leading number
in the filename controls ordering only; the URL uses the rest of the name.

| Help | Theory |
| --- | --- |
| [Getting Started](docs/help/01-getting-started.md) | [Likert Items and Likert Scales](docs/theory/01-likert-scales.md) |
| [Cleaning a Dataset](docs/help/02-cleaning-workflow.md) | [Reverse Scoring](docs/theory/02-reverse-scoring.md) |
| [Field Groups and Subgroups](docs/help/03-field-groups.md) | [Scale Scores: Mean, Sum and Missing Data](docs/theory/03-scale-scores.md) |
| [Scales and Scoring](docs/help/04-scales-and-scoring.md) | [Principles of Survey Data Cleaning](docs/theory/04-data-cleaning-principles.md) |
| [Computing Scores and Exporting](docs/help/05-compute-and-export.md) | [Tidy Data and Why Column Names Matter](docs/theory/05-tidy-data.md) |
| [Console Commands](docs/help/06-console-commands.md) | |
| [Sample Data](docs/help/07-sample-data.md) | |
| [The Table Menu](docs/help/08-the-table-menu.md) | |
| [Preferences](docs/help/09-preferences.md) | |

Adding a page is just adding a `.md` file to `docs/help/` or `docs/theory/` — the sidebar,
the Help menu and the `docs` command pick it up on the next page load.

## Sample data

| File | Contents |
| --- | --- |
| `samples/sample_survey.xlsx` | 30 responses to a bilingual wellbeing survey: 7 background columns, 9 Likert items (3 reverse-keyed), 1 free-text column, a few blanks |
| `samples/sample_survey.csv` | The same 30 responses as CSV |
| `samples/sample_survey_wave2.csv` | A second wave, 12 responses, same questionnaire |
| `samples/sample_cleaning_rules.json` | A finished recipe for that questionnaire |

Regenerate them with `python samples/generate_samples.py` (synthetic, fixed seeds).

---

## Notes and limitations

- **Single session, in-memory.** One dataset is held in a module-level object shared by
  all requests; there is no multi-user isolation, no persistence, and no undo. Restarting
  the server discards the working data. Export before you quit.
- **Cleaning recipes record text rules, renames and replacements** — groups, scales,
  scoring and computed columns are not part of the exported `.json`.
- **Text replacement is substring-based**, not whole-cell: mapping `Yes` → `1` also
  rewrites `Yes, always`. Use the ignore and exempt lists to protect free text.
- Not yet implemented from the original project outline: **form creation**, **data
  analysis**, **plotting**, and **macros**.

---

## Project layout

```
app.py                       Launcher: puts src/ on the path, runs create_app()
cpdmctl.sh                   Service control: start/stop, install/remove a systemd unit
requirements.txt
docs/help/, docs/theory/     Markdown served at /docs
samples/                     Example datasets + generate_samples.py
tests/test_workflow.py       End-to-end API tests over the samples
src/cpdm/
    __init__.py              create_app()
    paths.py                 Project directories (docs, samples, templates, static)
    core/                    Dataframe logic — no Flask imports
        dataset.py           Dataset: the working table, categories, scales, recipe
        state.py             The process-wide session object
        tabular_io.py        Reading and writing .xlsx / .csv
        text_rules.py        Trimming rules: the chain model and its modes
        cleaning.py          Header mapping, value replacement, trimming
        recipes.py           Saving and replaying cleaning recipes
        groups.py            The field group tree
        column_spec.py       Typed column selections: names, ranges, globs
        scales.py            Scales: options, item keying, scoring, renaming
        compute.py           Row-wise statistics
        console.py           Command prompt handlers
        table.py             The Table menu: header, rows, columns, sort, filter
        about_info.py        What the About box reports
        docs_library.py      Discovery of docs/*.md
        markdown_lite.py     Dependency-free Markdown renderer (fallback)
        samples.py           Sample-file listing and download resolution
    web/
        views.py             HTML pages: workspace, /docs, sample downloads
        api/                 JSON endpoints: files, cleaning, scales, compute,
                             console, docs (+ support.py for error handling)
    templates/               index.html (workspace), docs.html (reader)
    static/css/              theme.css (palettes and typography), style.css, docs.css
    static/js/               core, files, cleaning, text_rules (the trimming
                             wizard), groups, scales, table, compute, console, docs,
                             prefs
```

Core modules take a `Dataset` as their first argument and never import Flask, so they can
be exercised without a request. The web layer only unpacks JSON, calls core, and formats
the reply; `ValueError` from core becomes a 400 with its message.

### API endpoints

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/` | Workspace page |
| `GET` | `/docs`, `/docs/<section>/<slug>` | Documentation browser |
| `GET` | `/samples/<filename>` | Download a sample file |
| `POST` | `/api/upload` | Load an `.xlsx` / `.csv` file |
| `GET` | `/api/export?format=xlsx\|csv` | Download the processed table |
| `GET` | `/api/get_state` | Columns, categories, scales, ignored columns, flags |
| `POST` | `/api/clean_headers` | Apply header map + ignored-column list |
| `POST` | `/api/get_unique_values` | Unmapped unique text values and where they occur |
| `POST` | `/api/clean_values` | Apply global value replacements |
| `POST` | `/api/text_rules/preview` | What a rule chain would do (never mutates) |
| `POST` | `/api/text_rules/apply` | Run a rule chain over headers or values |
| `POST` | `/api/text_rules/leftovers` | Headers and values the rules did not catch |
| `POST` | `/api/text_rules/fix_leftovers` | Hand fixes: rename headers, replace whole cells |
| `POST` | `/api/clean_text_pattern` | Adapter: one value rule (pre-wizard API) |
| `POST` | `/api/remove_non_english_advanced` | Adapter: one header + one value rule |
| `GET` | `/api/export_cleaning_rules` | Download `cleaning_rules.json` |
| `POST` | `/api/apply_cleaning_rules_file` | Replay a saved recipe |
| `GET` | `/api/groups` | The group tree, per-column assignments, ungrouped list |
| `GET` | `/api/scales` | Declared scales, and the groups one could be built on |
| `POST` | `/api/create_scale`, `/api/delete_scale` | Declare or drop a scale on a group |
| `POST` | `/api/groups/create`, `/api/groups/update`, `/api/groups/delete` | Edit the tree |
| `POST` | `/api/groups/assign` | Set each column's group directly |
| `POST` | `/api/groups/eligible` | Columns a group or subgroup may take |
| `POST` | `/api/groups/resolve_spec` | Resolve a typed column spec |
| `POST` | `/api/scales/rename_items` | Rename a scale's columns after it |
| `GET` | `/api/scales/<name>` | One scale's items and options |
| `POST` | `/api/scales/inspect_group` | Items and options a scale on a group would get |
| `POST` | `/api/scales/options`, `/api/scales/options/refresh`, `/api/scales/options/autoscore` | Edit the option list |
| `POST` | `/api/scales/items` | Direct/reverse per item |
| `GET`/`POST` | `/api/scales/status` | What the scoring currently does |
| `GET` | `/api/scales/export` | Download the scale definitions |
| `POST` | `/api/scales/inspect_file`, `/api/scales/import` | Inspect and load a scale file |
| `POST` | `/api/compute` | Row-wise statistic into a new column |
| `POST` | `/api/command` | Console commands |
| `GET` | `/api/table/page`, `/api/table/columns` | A page of rows; the column report |
| `POST` | `/api/table/rename`, `/api/table/reorder`, `/api/table/drop_columns` | Header and column edits |
| `POST` | `/api/table/drop_rows`, `/api/table/drop_blank_rows`, `/api/table/drop_duplicates` | Row deletion |
| `POST` | `/api/table/sort`, `/api/table/filter`, `/api/table/filter/count` | Sorting and filtering |
| `GET` | `/api/about` | What the About box shows |
| `GET` | `/api/docs`, `/api/docs/<section>/<slug>` | Doc listing and rendered page |

### Tests

```bash
python -m pytest tests        # or: python tests/test_workflow.py
```

Sixty end-to-end tests drive the HTTP API with the bundled samples: the full clean →
group → score → compute → export path, CSV upload, recipe replay (both v1 and v2),
replacement ordering, exemptions, console commands, docs/sample serving, the Markdown
fallback renderer, the trimming wizard (rule chains, delimiter sides, script awareness,
tidying, collision warnings, and the guarantee that a preview leaves the dataset
untouched), and field groups (the containment rule, column moves, subgroup trimming,
per-column assignment including the parent implication, parent-relative positions in a
spec, scales declared on nested groups with the deepest winning, the rules that refuse a
bad declaration, survival through renames and deletion, and the spec parser), and scale
scoring (option seeding and ordering, hand-added and deliberately unscored options,
per-item direct/reverse, the no-mutation preview, unrecognised answers being reported
rather than dropped, blanks surviving value replacement, scoring being idempotent and
reversible, a scale renaming its own items, deleting a scale restoring the answers, and
scale definitions travelling between datasets by name, by columns and by position, and
the leftovers stage listing, fixing and recording what the rules could not catch), the
Table menu (paged rows, the column report, refused rename collisions, reorder and drop,
sorting keeping every respondent's score with their row, filtering counted before it
deletes, and row labels staying stable), and the About box reporting the licence the
repository actually has, and the theming contract — every colour coming from a variable
some palette defines, and both pages applying preferences before the first paint, and the console commands (comments stripped outside quotes, head
and tail counts, the headers table, clean over a column range, and map matching a whole
answer in one column, the load/save sandbox refusing paths outside the data folder, and
Tab completion offering the right candidates at each position).

---

## Contribution

- Juby Merin Sam (jubymerinsam@gmail.com)
- Arun Periyal (periyal.arun@gmail.com)
