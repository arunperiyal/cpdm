# Cleaning a Dataset

The Clean menu holds four tools. They are meant to be used in this order: trim the noise out of the text, then map headers and values by hand, then save the result as a recipe you can replay.

## 1. Remove Non-English / Trim Text

A two-stage wizard: **Step 1 cleans the header row, Step 2 cleans the cell values.** Each stage takes an ordered list of rules and a set of target columns, and neither writes anything until you have had the chance to preview it.

### The rules

Add as many as you need with **+ Add rule**; they run top to bottom, and the arrows reorder them.

| Rule | Effect on `WhatsApp (വാട്സാപ്പ്)` |
| --- | --- |
| Cut from the first non-English character to the end | `WhatsApp (` |
| Cut at a delimiter | with `(` → `WhatsApp` |
| Strip non-English characters | `WhatsApp ()` |
| Tidy up leftovers | cleans the debris above → `WhatsApp` |

**Cut at a delimiter** takes several delimiters at once — type them separated by spaces, e.g. `/ ( -` — and cuts at whichever comes first. *keep before* / *keep after* chooses which side survives, so an export written `മലയാളം / English` is handled by keeping the part after the cut.

**Tidy up leftovers** is what makes the cutting rules produce clean text: it drops stray brackets and separators left dangling at either end, removes empty `()` pairs, and collapses runs of spaces. Put it last in the chain.

**Non-English** means "outside the Latin script and ordinary punctuation". Accented Latin (`café`, `naïve`), currency symbols (`₹`), dashes and curly quotes are *kept*. Tick **strict ASCII** on a rule if you want the older, blunter behaviour that removes those too.

### Target columns

The right-hand list picks which columns the stage touches. Search to filter, use **All** / **None**, and shift-click to select a contiguous range — handy for "just the nine item columns". Columns already marked ignored in the header-mapping wizard start unticked; in the values stage, numeric columns are greyed out because they hold no text to trim.

### Preview

**Preview** shows exactly what will happen, without changing anything:

- Stage 1 lists every header as before → after, and warns when two headers would collapse onto the same name (the later one becomes `Name_1`) or when a rule would empty a header (the original is kept).
- Stage 2 reports how many cells change per column, with up to five before → after examples each.

Then **Apply & continue →** commits stage 1 and moves to stage 2; **Apply & finish** commits stage 2. **Skip headers →** jumps straight to the values stage.

> Pick the delimiter rule when your export is consistently `English / translation`. Pick *strip* only when the other script is scattered inside the text rather than appended at the end. Always finish with *tidy*.

## 2. Header Mapping & Value Replacement

A two-step wizard.

**Step 1 — headers and column selection.** Every column gets a text box holding its new name, and a checkbox. Unticking a column marks it **ignored**: it keeps its data through every later value replacement. Untick names, free text, IDs, and anything else where a global find-and-replace would do damage. The ⚡ button in the corner opens the wizard from part 1 at its values stage.

**Step 2 — value replacement.** CPDM gathers every distinct text value across the columns that are still ticked, and shows how many columns each appears in. Type the replacement next to it and apply.

Two rules govern this step:

- Replacement is **global across all active columns**, not per column. Mapping `Yes` → `1` changes it everywhere at once.
- Replacement is **literal substring**, not whole-cell. Mapping `Yes` → `1` also turns `Yes, always` into `1, always`. Longer values are always applied before shorter ones, so `Strongly Agree` is safe from the rule for `Agree`, but overlapping fragments are still worth checking.

Values already mapped are hidden the next time you open the step, so a second pass only shows what is left.

> For Likert answers, prefer [Scales → Assign Scoring](/docs/help/scales-and-scoring) over this step. It matches whole cells rather than substrings, applies only inside one scale's columns, and keeps the response order and scores together where you can see them. Use value replacement for tidying answers up — spelling, casing, stray wording — rather than for coding them.

## 3. Save Cleaning File (.json)

Writes the recorded recipe. The `steps` list is the important part: it is an ordered log of what you did, because trimming and then renaming produces a different dataset from renaming and then trimming.

```json
{
  "version": 2,
  "steps": [
    {"op": "text_rules", "stage": "headers",
     "rules": [{"mode": "delimiter", "delimiters": ["/"], "keep": "before"},
               {"mode": "tidy"}]},
    {"op": "header_map", "map": {"Age": "age"}, "ignored_columns": ["Comments"]},
    {"op": "value_replacements", "map": {"Agree": "4"}}
  ],

  "header_map": { "Age / വയസ്സ്": "Age" },
  "value_replacements": { "_global": { "Agree / യോജിക്കുന്നു": "4" } },
  "ignored_columns": ["Timestamp", "Name", "Comments"]
}
```

It records trimming rules, header renames, value replacements and the ignored list — *not* the scoring or the computed columns. The flat keys below `steps` are kept so the file stays readable at a glance.

## 4. Apply Cleaning File (.json)

Load a fresh dataset, then apply the recipe to repeat every recorded step, in order. This is how wave 2 of a survey ends up with the same column names, the same trimmed text and the same codes as wave 1.

Because the recipe starts from the original header names, apply it to an untouched export rather than to a file you have already half-cleaned. `samples/sample_cleaning_rules.json` is a complete worked example for the sample survey; it is a version 1 file — the older flat format, still replayed exactly as before.

## Order of operations

```
Open file
  └─ Remove Non-English      (bulk, mechanical)
       └─ Header Mapping      (rename + choose ignored columns)
            └─ Value Replacement  (tidy up inconsistent answers)
                 └─ Save Cleaning File
```

Doing header mapping before trimming means you retype text the trimmer would have fixed for free. Doing value replacement before choosing your ignored columns risks rewriting free text.
