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

Environment overrides: `CPDM_HOST`, `CPDM_PORT`, `CPDM_DEBUG`, `CPDM_DOCS_DIR`,
`CPDM_SAMPLES_DIR`.

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

**Remove Non-English / Trim Text** — a two-stage wizard: stage 1 cleans the header row,
stage 2 cleans the cell values. Each stage takes an **ordered chain of rules** plus the
columns to apply them to, and previews the result before anything is written.

- *Cut from the first non-English character to the end* — `WhatsApp (വാട്സാപ്പ്)` → `WhatsApp (`
- *Cut at a delimiter* — several delimiters at once (`/ ( -`), cutting at whichever comes first, keeping the text **before** or **after** it
- *Strip non-English characters* — removes them wherever they appear
- *Tidy up leftovers* — drops dangling brackets and separators, removes empty `()`, collapses spaces: `WhatsApp (` → `WhatsApp`

"Non-English" means outside the Latin script and ordinary punctuation, so `café`, `₹500`,
dashes and curly quotes survive; a per-rule **strict ASCII** toggle restores the older
behaviour that removed those too.

The column picker has search, all/none and shift-click range selection; numeric columns
are excluded from the values stage automatically. **Preview** lists every header as
before → after — warning about collisions (`Name` → `Name_1`) and about rules that would
empty a header — or, for values, the changed-cell count per column with up to five
examples. The ⚡ button inside the header-mapping wizard opens the same wizard at its
values stage.

**Save Cleaning File (.json)** — exports the recorded recipe as `cleaning_rules.json`:
an ordered `steps` log (text rules, header maps, value replacements) plus the flat
`header_map` / `value_replacements` / `ignored_columns` keys for readability.

**Apply Cleaning File (.json)** — replays a saved recipe against the loaded dataset, step
by step in the order they were performed, so trimming, renaming and coding all reproduce.
This is how a second wave of the same survey gets cleaned identically to the first.
Version 1 recipes — the older flat format, including `samples/sample_cleaning_rules.json`
— still replay through the original code path.

### Fields

**Groups** — one dialogue, two tabs, for saying what every column *is*, and the only
place scales are defined. A **group** names a set of columns; a **subgroup** holds a
subset of its parent's columns, at any depth of nesting.

Groups and scales are separate ideas. Each group carries a *kind* — `Scale`,
`Demographics`, or `Container` (organise only, claims nothing for scoring) — and any
group at any depth can be a scale, so a container called `Scales` can hold `PHQ` and
`GAD` as two independent scales. Where marks nest, the deepest one wins: mark a scale's
subgroups as containers and it scores as one scale; mark them as scales and each becomes
its own. A scale takes both its name and its items from the group.

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

The tree is the single source of truth; the flat categorisation the rest of the app reads
is derived from it. A column belongs to one group per level (reassigning moves it and
says so), shrinking a group trims its subgroups, and renames from Numerise are followed
automatically. `groups` at the prompt prints the tree.

### Scales

Scales are created in Fields → Groups; this menu holds what you then do with them.

**Numerise** — bulk-renames the columns of one scale group (or of all of them) to
`Scale_1`, `Scale_2`, … with a configurable prefix, following column order.

**Scoring** — per scale column, choose *Direct* or *Reverse* and a maximum score. The
column is coerced to numeric (unparseable cells become blank) and reverse items become
`(1 + max) − value`.

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

### Command console

| Command | Result |
| --- | --- |
| `help` | Lists the available commands |
| `show` / `head` | First 5 rows as a table |
| `info` | Filename, dimensions, demographics, ignored-column count, scales and their members |
| `summary` | `describe()` descriptive statistics |
| `columns` | Column count and full list of names |
| `groups` | The field group / subgroup tree |
| `docs` | Links to every documentation page |
| `replace "old" "new"` | Global literal replacement across active text columns (quoted, Unicode-safe) |
| `clear` | Clears the output pane |

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
- **Cleaning recipes record text rules, renames and replacements** — scoring, numerise and
  computed columns are still not part of the exported `.json`.
- **Text replacement is substring-based**, not whole-cell: mapping `Yes` → `1` also
  rewrites `Yes, always`. Use the ignore and exempt lists to protect free text.
- Not yet implemented from the original project outline: **form creation**, **data
  analysis**, **plotting**, and **macros**.

---

## Project layout

```
app.py                       Launcher: puts src/ on the path, runs create_app()
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
        groups.py            The field group tree and the categories it derives
        column_spec.py       Typed column selections: names, ranges, globs
        scales.py            Scale definitions, categories, numerise, scoring
        compute.py           Row-wise statistics
        console.py           Command prompt handlers
        docs_library.py      Discovery of docs/*.md
        markdown_lite.py     Dependency-free Markdown renderer (fallback)
        samples.py           Sample-file listing and download resolution
    web/
        views.py             HTML pages: workspace, /docs, sample downloads
        api/                 JSON endpoints: files, cleaning, scales, compute,
                             console, docs (+ support.py for error handling)
    templates/               index.html (workspace), docs.html (reader)
    static/css/              style.css, docs.css
    static/js/               core, files, cleaning, text_rules (the trimming
                             wizard), groups, scales, compute, console, docs
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
| `POST` | `/api/clean_text_pattern` | Adapter: one value rule (pre-wizard API) |
| `POST` | `/api/remove_non_english_advanced` | Adapter: one header + one value rule |
| `GET` | `/api/export_cleaning_rules` | Download `cleaning_rules.json` |
| `POST` | `/api/apply_cleaning_rules_file` | Replay a saved recipe |
| `GET` | `/api/groups` | The group tree, per-column assignments, ungrouped list |
| `POST` | `/api/groups/create`, `/api/groups/update`, `/api/groups/delete` | Edit the tree |
| `POST` | `/api/groups/assign` | Set each column's group directly |
| `POST` | `/api/groups/eligible` | Columns a group or subgroup may take |
| `POST` | `/api/groups/resolve_spec` | Resolve a typed column spec |
| `POST` | `/api/numerise` | Rename scale columns with a prefix |
| `POST` | `/api/scoring` | Direct/reverse scoring |
| `POST` | `/api/compute` | Row-wise statistic into a new column |
| `POST` | `/api/command` | Console commands |
| `GET` | `/api/docs`, `/api/docs/<section>/<slug>` | Doc listing and rendered page |

### Tests

```bash
python -m pytest tests        # or: python tests/test_workflow.py
```

Twenty-six end-to-end tests drive the HTTP API with the bundled samples: the full clean →
group → score → compute → export path, CSV upload, recipe replay (both v1 and v2),
replacement ordering, exemptions, console commands, docs/sample serving, the Markdown
fallback renderer, the trimming wizard (rule chains, delimiter sides, script awareness,
tidying, collision warnings, and the guarantee that a preview leaves the dataset
untouched), and field groups (the containment rule, column moves, subgroup trimming,
per-column assignment including the parent implication, parent-relative positions in a
spec, a subgroup acting as its own scale, survival through renames and deletion, and the
spec parser).

---

## Contribution

- Juby Merin Sam (jubymerinsam@gmail.com)
- Arun Periyal (periyal.arun@gmail.com)
