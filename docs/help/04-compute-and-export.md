# Computing Scores and Exporting

## Row Calculations

**Compute → Row Calculations** creates one new column holding a per-respondent statistic across the scale items you tick.

| Field | Meaning |
| --- | --- |
| Target Column Name | The new column. Name it after the construct: `Wellbeing_Mean`. |
| Calculation Function | Mean, Sum, Minimum, Maximum or Standard Deviation. |
| Scale Items | Every column categorised under a scale, all ticked by default. |

The selected columns are converted to numbers first, so a stray text answer becomes blank rather than an error. Blanks are skipped: a mean over five items where one is missing is the mean of the four that are present. [Scale Scores](/docs/theory/scale-scores) explains when that is the right choice and when it is not.

The new column arrives as *Uncategorised*, so it will not be swept into a later scoring or compute run by accident. You can run Compute as many times as you like — one column per scale, or a mean and a sum side by side.

### Worked example

With `WB1`–`WB5` categorised under `Scale: Wellbeing` and reverse items already scored:

- Target Column Name: `Wellbeing_Mean`
- Function: Mean (Average)
- Items: `WB1`, `WB2`, `WB3`, `WB4`, `WB5`

Then repeat with `DS1`–`DS4` into `Digital_Stress_Mean`.

## Checking the result

At the prompt:

- `summary` — count, mean, standard deviation, min/max and quartiles for every numeric column. Your new score column should sit inside the response range (1–5 for a mean of 1–5 items); if it does not, a reverse-scoring maximum is probably wrong.
- `show` — the first five rows, to eyeball the new column against its inputs.
- `info` — which columns belong to which scale.

## Export

**File → Export (.xlsx)** writes the whole working table to `processed_<original name>.xlsx`, in a sheet named `Processed_Data`. **File → Export (.csv)** writes the same table as UTF-8 CSV, which is the safer choice if the data still contains non-Latin scripts and your next tool is R or SPSS.

The export is a snapshot of the dataset as it currently stands — cleaned text, renamed headers, scored items and computed columns.

Nothing is written to disk until you export, and the session ends when the server stops.
