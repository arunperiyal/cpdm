# Field Groups and Subgroups

**Fields → Groups** is where you organise columns. A **group** names a set of them — the demographics, the item block, one instrument. A **subgroup** takes a subset of the group above it: a subscale, or one instrument inside a block of them.

Grouping says nothing about analysis. Declaring that a group's columns form a scale is a separate step, under [Scales → Create Scale](/docs/help/scales-and-scoring) — so the two stay independent, and you can reorganise columns without disturbing your scales, or drop a scale without disturbing your groups.

The rule that shapes everything here: a subgroup can only hold columns its parent already holds. Nesting can go deeper than two levels, and the rule applies at each one, so every subgroup's columns belong to its root group.

The dialogue has two tabs, and they edit the same thing from opposite ends:

- **Build groups** — make a group, then choose its columns. Best when you think in constructs.
- **Assign columns** — one row per column with a dropdown of every group. Best when you have a wide table and just need everything filed. The counter at the top right says how many columns are still ungrouped.

## Creating a group

**+ New group** opens the editor on the right.

| Field | What it does |
| --- | --- |
| Group name | Must be unique across the whole tree, subgroups included. |
| Columns | Tick them in the list, or type them — see below. |

**Create group** saves it. The **+ Sub** button on any group opens the same editor for a child, with the column list already narrowed to that group's columns.

## Groups are not scales

A group is a container of columns and nothing more. Nothing you do here decides what gets scored — that is what **Scales → Create Scale** is for, and it points at a group. A group with a scale on it wears a green `scale:` badge in the tree.

Because the two are separate, a group called `Scales` holding the whole item block can carry no scale itself while its subgroups `PHQ` and `GAD` each carry one. Where scales are declared on nested groups, the deepest declaration wins for the columns they share.

## Typing columns instead of ticking them

The spec box accepts a comma-separated list, and adds whatever it matches to the current selection:

| You type | You get |
| --- | --- |
| `WB1, WB3, DS2` | those three columns by name |
| `WB1:WB5` | every column from `WB1` to `WB5`, in list order |
| `8:16` | columns 8 to 16 by position (1-based) |
| `12` | the twelfth column |
| `WB*` | every column whose name starts with `WB` |

**Positions count within the list shown underneath, not the whole table.** For a root group that list is the table, so `8:16` means the eighth to sixteenth columns. Inside a subgroup it is the parent's columns: if `Scales` holds table columns 8–16, then its subgroup `PHQ` takes `1:4` to mean that group's first four columns — table columns 8–11. Each row in the picker is numbered, and when the two differ the table position is shown dimmed on the right, so you can always see which is which.

Names are matched case-insensitively, and an exact column name always wins over the other readings — a column genuinely called `5` resolves to itself, not to the fifth column. After you press **Add to selection** the line underneath reports what matched, what matched nothing, and anything that fell outside the parent group.

## Assigning columns one by one

The **Assign columns** tab lists every column with a dropdown of the whole tree, subgroups indented under their parents. Search to narrow the list, tick *only ungrouped* to see what is left to do, then **Save assignments** — nothing is written until you do, and the footer counts your unsaved changes.

Picking a subgroup files the column under its parent too, because a subgroup's columns are always part of its parent. Picking *— ungrouped —* takes the column out of every group at once.

Create the groups under **Build groups** first; the dropdown can only offer groups that exist.

## What groups drive

The tree is the only place column membership is decided. Which of those groups are scales is decided in Scales → Create Scale, and the two together give every column its category: `Scale: <name>` for the deepest scale holding it, `Uncategorised` for everything else. That is what Scoring, Numerise and Compute read.

Deleting a group removes it, everything beneath it, and any scale declared on them — the log says which. It never touches the data: the columns simply become ungrouped.

## Two rules the editor enforces for you

**A column belongs to one group per level.** Putting `WB5` into a new group takes it out of whichever group held it before, and the log says which: *"Moved 1 column(s) out of 'Wellbeing'"*. The same applies to sibling subgroups, so a subscale item cannot sit in two subscales at once.

**Subgroups follow their parent.** Shrink a group and its subgroups lose the columns that left; the log reports how many. Rename columns with Scales → Numerise and every group follows the rename automatically.

## Checking the tree

Type `groups` at the prompt (and `scales` for the other half):

```
Field Groups:
[Background] group, 4 column(s): Age, Gender, District, Occupation
[Scales] group, 9 column(s): WB1, WB2, WB3, WB4, WB5, DS1, DS2, DS3, DS4
  - [PHQ] scale 'PHQ-9', 4 column(s): WB1, WB2, WB3, WB4
  - [GAD] scale 'GAD-7', 4 column(s): DS1, DS2, DS3, DS4
```

## A worked pass over the sample survey

After cleaning `sample_survey.xlsx` (see [Sample Data](/docs/help/sample-data)):

1. **+ New group** → `Background`, spec `3:6` (age, gender, district, occupation).
2. **+ New group** → `Scales`, spec `8:16` — the nine item columns.
3. **+ Sub** on Scales → `Wellbeing`, spec `1:5`. Inside `Scales`, `1:5` is its own first five columns, `WB1`–`WB5`.
4. **+ Sub** on Scales → `Digital Stress`, spec `6:9` — `DS1`–`DS4`.
5. **+ Sub** on Wellbeing → `Negative affect`, spec `3, 5` — the two reverse-keyed items, labelled without splitting anything.
6. **+ New group** → `Admin`, spec `Timestamp, Name, Comments`.

Then, under **Scales → Create Scale**, declare a scale on `Wellbeing` and another on `Digital Stress`. The other groups stay as they are: organised, and out of the scoring tools.

From there, [Scales and Scoring](/docs/help/scales-and-scoring) and [Computing Scores](/docs/help/compute-and-export) take over — and a subscale mean is just a Compute run over the columns of one subgroup, whether or not that subgroup carries a scale of its own.
