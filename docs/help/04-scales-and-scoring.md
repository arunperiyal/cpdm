# Scales and Scoring

Once the text is clean, CPDM needs to know which columns belong together. That is [Fields → Groups](/docs/help/field-groups); this page covers what the Scales menu then does with them.

## Define your scales

Scales are made in **Fields → Groups**, and nowhere else: create a group, set its kind to *Scale*, and give it columns. The scale takes its name and its items from that group. A group at any depth can be a scale, so a container holding `PHQ` and `GAD` gives you two scales, and where marks nest the deepest one wins. See [Field Groups and Subgroups](/docs/help/field-groups).

Deleting the group removes the scale — along with anything beneath it. The columns and their data stay; they simply become ungrouped.

The Scales menu therefore has no "create": it holds the two things you *do* to a scale once it exists.

## Numerise (optional)

**Scales → Numerise** renames the items of one scale — or of every scale — to `Scale_1`, `Scale_2`, … using the prefix you choose. Numbering follows the current column order.

Give each scale its own prefix (`WB_`, `DS_`) if you numerise more than one, otherwise the second run will produce names that collide with the first. Renaming here is permanent for the session, so do it after you are happy with your groups — they follow the rename automatically.

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
Groups  →  (Numerise)  →  Scoring  →  Compute
```

Scoring before value replacement will not work: the items must already hold numbers, or text that converts cleanly to numbers.
