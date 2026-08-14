# Scales and Scoring

Once the text is clean, CPDM needs to know which columns belong together. That is [Fields → Groups](/docs/help/field-groups); this page covers what the Scales menu then does with them.

## Define your scales

**Scales → Create Scale** declares that a group's columns are one instrument. Pick the group; the scale takes its columns, and its name unless you type a different one — `PHQ` the group can back `PHQ-9` the scale.

Groups and scales stay separate on purpose:

- A group with no scale on it is just organisation — the demographics, an admin block, a container holding the whole item set.
- A group at any depth can carry a scale, so a container holding `PHQ` and `GAD` gives you two scales rather than one big one.
- Where scales sit on nested groups, the deepest one wins the columns they share. A scale on the container above still covers whatever the inner scales do not.
- Deleting a scale leaves its group and columns untouched. Deleting the *group* removes the scale with it.

Build the groups first in [Fields → Groups](/docs/help/field-groups); a group needs columns before a scale can read it. The same dialogue lists the scales you have declared, with the group and column count behind each, and deletes them.

Type `scales` at the prompt to see the same list from the console.

## Numerise (optional)

**Scales → Numerise** renames the items of one scale — or of every scale — to `Scale_1`, `Scale_2`, … using the prefix you choose. Numbering follows the current column order.

Give each scale its own prefix (`WB_`, `DS_`) if you numerise more than one, otherwise the second run will produce names that collide with the first. Renaming here is permanent for the session, so do it after you are happy with your groups — they follow the rename automatically.

## Items and Options

A scale describes itself in two parts, and the Create Scale dialogue shows both as soon as you pick a group:

- **Items** are its columns — the questions.
- **Options** are its response set — the answers, read from the data.

Both come from the group. Options are seeded from the values actually present in the columns; if those values are already numbers, they arrive in numeric order scored as themselves, and there is nothing left to do.

## Assign Scoring — a number for each option

**Scales → Assign Scoring** lists the options in order, each with a score.

| Control | What it is for |
| --- | --- |
| ↑ ↓ | Put the options in response order — *Strongly Disagree* first, *Strongly Agree* last. |
| Score | The number that answer becomes. |
| **Number 1…n** / **n…1** | Fill the scores from the current order, which is the usual Likert case. |
| Add | An option nobody happened to choose. A five-point scale where nobody picked the bottom still needs that option, or its score will be missing from the range. |
| **Find new answers in the data** | Re-scan the columns and append anything not on the list — useful after further cleaning. |
| × | Remove an option. Answers matching a removed option become blank when you apply. |

**Leave a score blank** for an answer that should count as missing rather than as a number — *Not applicable*, *Prefer not to say*. Those cells become blank, and, importantly, the option stays out of the scale's range: a blank-scored sixth option does not turn a 1–5 scale into a 1–6 one.

The line at the bottom shows the range you have built and the reversal it implies.

## Assign Scoring Type — direct or reverse per item

**Scales → Assign Scoring Type** lists the scale's items with a *Direct* / *Reverse* choice each, plus *all direct* / *all reverse* buttons.

There is no maximum to type in. Reverse items are flipped with `min + max − value` taken from the scale's own option scores, so a 1–7 scale reverses as `8 − value` without being told. That removes the commonest way to corrupt a dataset silently. The background is in [Reverse Scoring](/docs/theory/reverse-scoring).

## Apply Scoring to Data

**Scales → Apply Scoring to Data** shows what would happen before it happens: per item, how many cells will be scored, how many are blank, and — in yellow — any answer the option list does not cover. Those would become blank, so an unexpected entry there usually means an option is missing or spelled differently.

Applying replaces each answer with its option's score **within that scale's columns only**, then flips the reverse items. Columns outside the scale are untouched, which is the main advantage over coding Likert answers with a global find-and-replace in the cleaning wizard.

Apply **once**. A second pass would find numbers where it expects labels, and reverse the reversal.

## Order of operations

```
Groups  →  Create Scale  →  Assign Scoring  →  Assign Scoring Type
        →  Apply Scoring  →  (Numerise)  →  Compute
```

You no longer need to convert Likert text to numbers in the cleaning wizard — the scale does it, per scale, on exact whole-cell matches. Clean the text so the answers are consistent, then let the scale score them.
