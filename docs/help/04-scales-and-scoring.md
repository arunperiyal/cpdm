# Scales, Categories and Scoring

Once the text is clean, CPDM needs to know which columns belong together. That is what the Fields and Scales menus are for.

## Define your scales

**Scales → Create Scale.** Name each construct your questionnaire measures — `Wellbeing`, `Digital Stress`, `Job Satisfaction`. `General Scale` exists by default and can be deleted like any other.

Deleting a scale does not delete data: its columns fall back to *Uncategorised*.

## Categorise the columns

**Fields → Categorise** lists every column with a dropdown:

| Category | Use it for |
| --- | --- |
| Uncategorised | Timestamps, IDs, free text, anything not analysed |
| Demographics | Age, gender, district, occupation |
| Scale: *name* | The individual items of that scale |

Categorisation drives the rest of the app: Scoring, Numerise and Compute only offer columns that sit under a scale.

**Fields → Groups & Subgroups** is the richer version of the same thing: a tree, where a scale can be split into subscales. The two stay in step — a group of kind *Scale* becomes the `Scale: <name>` category for all of its columns, subgroups included. See [Field Groups and Subgroups](/docs/help/field-groups).

## Numerise (optional)

**Scales → Numerise** renames the items of one scale — or of every scale — to `Scale_1`, `Scale_2`, … using the prefix you choose. Numbering follows the current column order.

Give each scale its own prefix (`WB_`, `DS_`) if you numerise more than one, otherwise the second run will produce names that collide with the first. Renaming here is permanent for the session, so do it after you are happy with your categories.

## Scoring

**Scales → Scoring** lists every scale item with two settings:

- **Type** — *Direct* leaves the number as it is; *Reverse* flips it.
- **Max Score** — the top of the response scale (5 for a 1–5 Likert, 7 for 1–7).

Applying scoring does two things to each listed column: it converts the column to numbers (anything unparseable becomes blank), and for reverse items it replaces each value `x` with `(1 + max) − x`.

So on a 1–5 scale: 1↔5, 2↔4, 3 stays 3.

Set *Max Score* to the real maximum of your scale. Using 5 on a 1–7 scale produces silently wrong numbers — negative values for the top two response options. The background is in [Reverse Scoring](/docs/theory/reverse-scoring).

Run scoring **once**. Applying it a second time reverses the reversal.

## Order of operations

```
Create Scale  →  Categorise or Groups  →  (Numerise)  →  Scoring  →  Compute
```

Scoring before value replacement will not work: the items must already hold numbers, or text that converts cleanly to numbers.
