# Cleaning a Dataset

The Clean menu holds four tools. They are meant to be used in this order: trim the noise out of the text, then map headers and values by hand, then save the result as a recipe you can replay.

## 1. Remove Non-English

One dialogue with three independent parts.

**Column Headers Rule** and **Cell Values Rule** each offer the same four choices:

| Rule | Effect on `WhatsApp (വാട്സാപ്പ്)` |
| --- | --- |
| Do not modify | unchanged |
| Remove from the 1st non-English character to the end | `WhatsApp (` |
| Strip all non-English characters entirely | `WhatsApp ()` |
| Remove after character/delimiter | with `(` → `WhatsApp` |

**Exempt Columns** — anything ticked here is skipped by *both* rules. Use it for free-text answers written in another script, which you want to keep intact.

Numeric columns are never touched. If two headers collapse onto the same name, the later one gets a `_1`, `_2` suffix rather than silently overwriting.

> Pick the delimiter rule when your export is consistently `English / translation`. Pick *strip* only when the other script is scattered inside the text rather than appended at the end.

## 2. Header Mapping & Value Replacement

A two-step wizard.

**Step 1 — headers and column selection.** Every column gets a text box holding its new name, and a checkbox. Unticking a column marks it **ignored**: it keeps its data through every later value replacement. Untick names, free text, IDs, and anything else where a global find-and-replace would do damage. The ⚡ button in the corner opens the trimming tool from part 1 for values only.

**Step 2 — value replacement.** CPDM gathers every distinct text value across the columns that are still ticked, and shows how many columns each appears in. Type the replacement next to it and apply.

Two rules govern this step:

- Replacement is **global across all active columns**, not per column. Mapping `Yes` → `1` changes it everywhere at once.
- Replacement is **literal substring**, not whole-cell. Mapping `Yes` → `1` also turns `Yes, always` into `1, always`. Longer values are always applied before shorter ones, so `Strongly Agree` is safe from the rule for `Agree`, but overlapping fragments are still worth checking.

Values already mapped are hidden the next time you open the step, so a second pass only shows what is left.

## 3. Save Cleaning File (.json)

Writes the recorded recipe:

```json
{
  "header_map": { "Age / വയസ്സ്": "Age" },
  "value_replacements": { "_global": { "Agree / യോജിക്കുന്നു": "4" } },
  "ignored_columns": ["Timestamp", "Name", "Comments"]
}
```

It records header renames, value replacements and the ignored list — *not* the Remove Non-English rules, the scoring, or the computed columns.

## 4. Apply Cleaning File (.json)

Load a fresh dataset, then apply the recipe to repeat those renames and replacements exactly. This is how wave 2 of a survey ends up with the same column names and codes as wave 1.

Because the recipe is keyed on the original header names, apply it to an untouched export rather than to a file you have already half-cleaned. `samples/sample_cleaning_rules.json` is a complete worked example for the sample survey.

## Order of operations

```
Open file
  └─ Remove Non-English      (bulk, mechanical)
       └─ Header Mapping      (rename + choose ignored columns)
            └─ Value Replacement  (Likert text → numbers)
                 └─ Save Cleaning File
```

Doing header mapping before trimming means you retype text the trimmer would have fixed for free. Doing value replacement before choosing your ignored columns risks rewriting free text.
