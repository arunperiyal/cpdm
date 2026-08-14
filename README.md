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

**Remove Non-English** — independent rules for headers and for cell values, plus a
per-column exemption list. Each rule can be:

- *Do not modify*
- *Remove from the first non-English (non-ASCII) character to the end* — `WhatsApp (വാട്സാപ്പ്)` → `WhatsApp (`
- *Strip all non-English characters entirely* — keeps printable ASCII, collapses leftover whitespace
- *Remove after a chosen delimiter to the end* — cut at `/`, `-`, `(`, `,` or any character you type

Exempt columns are untouched by both rules; numeric columns are never value-cleaned;
header renames are de-duplicated (`Name`, `Name_1`, …) if trimming would collide. The
same three modes are reachable as a quick value-only trimmer from inside step 1 of the
wizard.

**Save Cleaning File (.json)** — exports the recorded recipe (`header_map`,
`value_replacements`, `ignored_columns`) as `cleaning_rules.json`.

**Apply Cleaning File (.json)** — replays a saved recipe against the loaded dataset:
renames headers, restores the ignored-column list, re-applies value replacements. This is
how a second wave of the same survey gets cleaned identically to the first.

### Fields

**Categorise** — assign every column to `Uncategorised`, `Demographics`, or
`Scale: <name>`. Categories drive the Scales and Compute tools.

### Scales

**Create Scale** — define, list and delete named scale groups (`General Scale` exists by
default). Deleting a scale returns its columns to `Uncategorised`.

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
| [Scales, Categories and Scoring](docs/help/03-scales-and-scoring.md) | [Scale Scores: Mean, Sum and Missing Data](docs/theory/03-scale-scores.md) |
| [Computing Scores and Exporting](docs/help/04-compute-and-export.md) | [Principles of Survey Data Cleaning](docs/theory/04-data-cleaning-principles.md) |
| [Console Commands](docs/help/05-console-commands.md) | [Tidy Data and Why Column Names Matter](docs/theory/05-tidy-data.md) |
| [Sample Data](docs/help/06-sample-data.md) | |

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
- **Cleaning recipes record renames and replacements only** — Remove Non-English value
  rules, scoring, numerise and computed columns are not part of the exported `.json`.
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
        text_rules.py        The four shared text-trimming modes
        cleaning.py          Header mapping, value replacement, trimming
        recipes.py           Saving and replaying cleaning recipes
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
    static/js/               core, files, cleaning, scales, compute, console, docs
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
| `POST` | `/api/clean_text_pattern` | Trim/strip text across active columns |
| `POST` | `/api/remove_non_english_advanced` | Header + value rules with exemptions |
| `GET` | `/api/export_cleaning_rules` | Download `cleaning_rules.json` |
| `POST` | `/api/apply_cleaning_rules_file` | Replay a saved recipe |
| `POST` | `/api/create_scale`, `/api/delete_scale` | Manage scale definitions |
| `POST` | `/api/categorise` | Save column categories |
| `POST` | `/api/numerise` | Rename scale columns with a prefix |
| `POST` | `/api/scoring` | Direct/reverse scoring |
| `POST` | `/api/compute` | Row-wise statistic into a new column |
| `POST` | `/api/command` | Console commands |
| `GET` | `/api/docs`, `/api/docs/<section>/<slug>` | Doc listing and rendered page |

### Tests

```bash
python -m pytest tests        # or: python tests/test_workflow.py
```

Eight end-to-end tests drive the HTTP API with the bundled samples: the full clean →
categorise → score → compute → export path, CSV upload, recipe replay, replacement
ordering, exemptions, console commands, docs/sample serving, and the Markdown fallback
renderer.

---

## Contribution

- Juby Merin Sam (jubymerinsam@gmail.com)
- Arun Periyal (periyal.arun@gmail.com)
