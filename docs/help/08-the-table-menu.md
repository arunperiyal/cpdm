# The Table Menu

Everything else in CPDM works on the data indirectly — rules, groups, scales. The Table menu is the direct route: look at the rows, change the shape of the table, and throw away what you do not want.

Nothing here can be undone, and none of it is recorded in the cleaning recipe. Export first if you are unsure.

## Header

Every column with its position, what it holds (`text`, `number`, `date`, `yes/no`), how many cells are filled and blank, how many distinct values it has, and which group and scale it belongs to. It is the quickest way to see whether a column arrived as numbers or as text.

Type into the right-hand box to rename a column outright. Groups, scale keying and the answers remembered for scoring all follow the new name. A rename that would give two columns the same name is refused rather than quietly applied.

## Rows

A paged view of the data, 25 rows at a time. The number on the left of each row is its **label** — it does not change when the table is sorted or filtered, so a row you tick stays the row you meant even after the view moves.

- Tick rows and **Delete ticked rows**.
- **Drop blank rows** removes rows where every cell is empty — the trailing junk a spreadsheet export often carries.
- **Drop duplicate rows** removes rows that repeat an earlier row exactly, keeping the first.

## Columns

Reorder with the arrows — useful before an export, since the order here is the order in the file. **Save order** applies it.

Tick a column and **Delete ticked** to remove it and its data. The column leaves any group that held it, and its scale loses that item. Deleting every column is refused.

## Sort

Sort by one column, or several: the first decides, the ones below break ties. Text sorts without regard to case; numbers sort as numbers, not as text, so `10` follows `9` rather than `1`.

Sorting reorders the table itself, so an export afterwards comes out in that order — and the scores already computed travel with their rows.

## Filter

Build one or more tests, each a column, a comparison and a value:

| Test | Applies to |
| --- | --- |
| is / is not | text or numbers, matched whole and case-insensitively |
| contains / does not contain | text |
| starts with / ends with | text |
| is greater than / at least / less than / at most | numbers; text that is not a number counts as blank |
| is blank / is not blank | anything — an empty cell or one holding only spaces |

Then say whether a row must match **every** test or **any** of them, and whether the matching rows are the ones to **keep** or the ones to **drop**.

**Count matches** reports how many rows the tests pick out, and how many would remain either way, without changing anything. Use it before applying — the difference between *keep* and *drop* is the whole dataset.

## Where this sits in the workflow

Filtering and row deletion change who is in your data, which is a decision about the study rather than about tidiness — see [Principles of Survey Data Cleaning](/docs/theory/data-cleaning-principles) on deciding exclusions before you look at the results. Do it deliberately, and write down what you removed and why: CPDM does not record it for you.
