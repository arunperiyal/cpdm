# Field Groups and Subgroups

**Fields → Groups** is where you say what your columns *are*. A **group** is a construct — Demographics, Wellbeing, Digital Stress. A **subgroup** is a facet of the group above it, which for a questionnaire usually means a subscale.

The rule that shapes everything here: a subgroup can only hold columns its parent already holds. Nesting can go deeper than two levels, and the rule applies at each one, so every subgroup's columns belong to its root group.

The dialogue has two tabs, and they edit the same thing from opposite ends:

- **Build groups** — make a group, then choose its columns. Best when you think in constructs.
- **Assign columns** — one row per column with a dropdown of every group. Best when you have a wide table and just need everything filed. The counter at the top right says how many columns are still ungrouped.

## Creating a group

**+ New group** opens the editor on the right.

| Field | What it does |
| --- | --- |
| Group name | Must be unique across the whole tree, subgroups included. |
| Kind | *Scale* for items to be scored, *Demographics* for background variables, *Other* for columns you want organised but kept out of scoring (IDs, timestamps, free text). Only root groups have a kind; subgroups inherit their root's. |
| Columns | Tick them in the list, or type them — see below. |

**Create group** saves it. The **+ Sub** button on any group opens the same editor for a child, with the column list already narrowed to that group's columns.

## Typing columns instead of ticking them

The spec box accepts a comma-separated list, and adds whatever it matches to the current selection:

| You type | You get |
| --- | --- |
| `WB1, WB3, DS2` | those three columns by name |
| `WB1:WB5` | every column from `WB1` to `WB5`, in table order |
| `7:15` | columns 7 to 15 by position (1-based) |
| `12` | the twelfth column |
| `WB*` | every column whose name starts with `WB` |

Names are matched case-insensitively, and an exact column name always wins over the other readings — a column genuinely called `5` resolves to itself, not to the fifth column. After you press **Add to selection** the line underneath reports what matched, what matched nothing, and anything that fell outside the parent group.

Ranges use positions in the table, so `WB1:WB5` picks up everything sitting between those two columns even if one of them is named differently. Check the ticked boxes afterwards.

## Assigning columns one by one

The **Assign columns** tab lists every column with a dropdown of the whole tree, subgroups indented under their parents. Search to narrow the list, tick *only ungrouped* to see what is left to do, then **Save assignments** — nothing is written until you do, and the footer counts your unsaved changes.

Picking a subgroup files the column under its parent too, because a subgroup's columns are always part of its parent. Picking *— ungrouped —* takes the column out of every group at once.

Create the groups under **Build groups** first; the dropdown can only offer groups that exist.

## What groups drive

The group tree is the only place column membership is decided. Everything else reads a flat picture derived from it: each column of a scale-kind root — including the ones inside its subgroups — counts as `Scale: <group name>`, which is what Scoring, Numerise and Compute work from.

So subscale membership lives only in the tree. That is deliberate: splitting a scale into subscales should not stop you scoring or averaging the scale as a whole. A subscale score is simply a Compute run over the columns of one subgroup.

Deleting a scale under **Scales → Create Scale** removes its group and any subgroups beneath it. Deleting a group never touches the data — the columns simply become ungrouped.

## Two rules the editor enforces for you

**A column belongs to one group per level.** Putting `WB5` into a new group takes it out of whichever group held it before, and the log says which: *"Moved 1 column(s) out of 'Wellbeing'"*. The same applies to sibling subgroups, so a subscale item cannot sit in two subscales at once.

**Subgroups follow their parent.** Shrink a group and its subgroups lose the columns that left; the log reports how many. Rename columns with Scales → Numerise and every group follows the rename automatically.

## Checking the tree

Type `groups` at the prompt:

```
Field Groups:
[Background] Demographics, 4 column(s): Age, Gender, District, Occupation
[Wellbeing] Scale, 5 column(s): WB1, WB2, WB3, WB4, WB5
  - [Positive affect] Scale, 3 column(s): WB1, WB2, WB4
  - [Negative affect] Scale, 2 column(s): WB3, WB5
[Digital Stress] Scale, 4 column(s): DS1, DS2, DS3, DS4
```

## A worked pass over the sample survey

After cleaning `sample_survey.xlsx` (see [Sample Data](/docs/help/sample-data)):

1. **+ New group** → `Background`, kind *Demographics*, spec `Age, Gender, District, Occupation`.
2. **+ New group** → `Wellbeing`, kind *Scale*, spec `WB1:WB5`.
3. **+ New group** → `Digital Stress`, kind *Scale*, spec `DS*`.
4. **+ Sub** on Wellbeing → `Positive affect`, spec `WB1, WB2, WB4`.
5. **+ Sub** on Wellbeing → `Negative affect`, spec `WB3, WB5` — the two reverse-keyed items.
6. **+ New group** → `Admin`, kind *Other*, spec `Timestamp, Name, Comments`, so those columns are filed away but stay out of scoring.

From here, [Scales and Scoring](/docs/help/scales-and-scoring) and [Computing Scores](/docs/help/compute-and-export) work exactly as before — and a subscale mean is just a Compute run over the columns of one subgroup.
