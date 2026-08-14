# Getting Started

CPDM is a local workspace for turning a raw questionnaire export into a scored, analysis-ready table. This page walks the whole path once, using the bundled sample survey.

## Start the workspace

```bash
pip install -r requirements.txt
python app.py
```

Your browser opens at `http://127.0.0.1:5000/`. Everything runs on your machine; no data leaves it.

## The three panes

| Pane | What it is |
| --- | --- |
| Menu bar | File, Clean, Fields, Scales, Compute and Help. The right-hand corner shows the loaded file and its size. |
| Output log | A running record of every action, plus tables printed by console commands. |
| Command prompt | Short text commands — type `help` to list them. |

## A first pass, end to end

1. **Get the sample data.** Help → Sample Data Files → download `sample_survey.xlsx`. It is a bilingual wellbeing survey with 30 responses, deliberately messy.
2. **Open it.** File → Open (.xlsx / .csv).
3. **Look at it.** Type `show` at the prompt for the first five rows, then `columns` for the full header list. The headers carry a Malayalam translation after a `/`, and the answers are text like `Agree / യോജിക്കുന്നു`.
4. **Trim the second language.** Clean → Remove Non-English / Trim Text. In stage 1, build the chain *Cut at delimiter `/` (keep before)* → *Tidy up leftovers*, press **Preview** to check the before → after list, then **Apply & continue →**. Stage 2 repeats it for the cell values; untick the comments column there so the free text survives. See [Cleaning a Dataset](/docs/help/cleaning-workflow).
5. **Map the headers.** Clean → Header Mapping & Value Replacement. Rename the long item texts to short codes (`WB1`, `WB2`, …) and untick columns that should never be touched (name, comments). You can leave the Likert answers as text — the scale will score them in step 8.
6. **Group your columns.** Fields → Groups: make a `Wellbeing` group holding `WB1:WB5`, a `Digital Stress` group holding `DS*`, and a `Background` group for the demographic columns. Nest subgroups with **+ Sub**, or switch to the **Assign columns** tab to file every column from one list. See [Field Groups and Subgroups](/docs/help/field-groups).
7. **Say which groups are scales.** Scales → Create Scale, once for `Wellbeing` and once for `Digital Stress`. The dialogue shows the items and the answer options it found. Grouping and scoring are deliberately separate steps.
8. **Score the answers.** Scales → Assign Scoring: put the options in response order and press *Number 1…n*. Then Scales → Assign Scoring Type to mark the reverse-keyed items, and Scales → Apply Scoring to Data — check its preview, then apply. See [Scales and Scoring](/docs/help/scales-and-scoring).
9. **Compute a score per respondent.** Compute → Row Calculations, e.g. the mean of `WB1`–`WB5` into `Wellbeing_Mean`.
10. **Export.** File → Export (.xlsx) or (.csv).

## Save the recipe

Clean → Save Cleaning File (.json) writes down the header renames, value replacements and ignored columns you just made. When a second wave of the same questionnaire arrives, open it and use Clean → Apply Cleaning File (.json) to repeat that work exactly. Try it with `sample_survey_wave2.csv`.

## Things worth knowing early

- **One dataset at a time, held in memory.** Closing the browser tab is harmless; stopping the server discards everything. Export before you quit.
- **There is no undo.** Work from a copy of your raw file, and save a cleaning recipe as you go.
- **Blank cells stay blank.** They are ignored by row calculations rather than counted as zero — see [Scale Scores](/docs/theory/scale-scores).
