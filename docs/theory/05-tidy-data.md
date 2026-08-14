# Tidy Data and Why Column Names Matter

CPDM's Fields and Scales menus assume a particular shape of table. It is worth knowing which shape, and why the app pushes you towards short column names.

## One row per respondent, one column per variable

The layout CPDM expects — and the one every statistics package wants — is:

- Each **row** is one unit of observation: one respondent, one response.
- Each **column** is one variable: one question, one derived score.
- Each **cell** holds one value.

Form platforms export this shape already. It survives cleaning as long as you resist two temptations: merging cells, and adding summary rows at the bottom. A total row is not an observation, and it will be averaged into your results.

## Why headers get shortened

A raw export header can be the entire question, in two languages, with its numbering:

```
3. I often feel tense for no clear reason / വ്യക്തമായ കാരണമില്ലാതെ പിരിമുറുക്കം തോന്നാറുണ്ട്
```

That is unusable as a variable name. It is too long to read in a dropdown, it will not survive import into most statistics software, and any dataset with fifty such columns is impossible to navigate.

Renaming it to `WB3` costs the question text, which is why the mapping should be written down — in the recipe file, in your codebook, or both. A good short name is:

- **Short** — a handful of characters.
- **Systematic** — `WB1`…`WB5` for one scale, `DS1`…`DS4` for another. The prefix carries the scale membership.
- **Plain** — letters, digits and underscores. No spaces, no punctuation, no accents.
- **Stable** — the same name in wave 2 as in wave 1, which is exactly what a saved cleaning recipe guarantees.

## Keep a codebook

The mapping from `WB3` back to its question is the difference between a reusable dataset and a puzzle. Record, for each variable: its short name, the exact question wording, the response options and their codes, the direction of keying, and which scale it belongs to.

The saved cleaning recipe covers part of this automatically — it is a literal record of old name to new name, and of every value code you assigned. It is not a substitute for the response options and keying, which live in your own notes.

## Derived columns are variables too

A computed `Wellbeing_Mean` is as much a variable as any item, and it needs the same treatment: a clear name, a note of how it was derived, and which items went into it. Names like `Scale_Mean` or `mean1` are cheap to type and expensive later, when a second scale arrives and you cannot tell them apart.

## What the categories buy you

Marking a column as *Demographics* or *Scale: Wellbeing* does not change the data — it records what the column is *for*. That record is what lets CPDM offer the right columns in the Scoring and Compute dialogues instead of the full list, and it is what `info` prints back to you.

Doing the categorisation carefully is the cheapest error prevention available: a column that is not in a scale cannot accidentally be reverse-scored or averaged into someone else's total.
