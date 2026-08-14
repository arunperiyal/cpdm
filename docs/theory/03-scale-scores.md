# Scale Scores: Mean, Sum and Missing Data

Once every item is coded and keyed in the same direction, the items of a scale get collapsed into one number per respondent. CPDM offers mean, sum, minimum, maximum and standard deviation. The choice between the first two is not cosmetic.

## Mean or sum

**The mean** stays on the response scale. A wellbeing mean of 4.2 sits on the same 1–5 ruler as the items themselves, so it is readable without knowing how many items the scale has, and it is comparable across scales of different lengths.

**The sum** — the total score — is what published instruments and their cut-off tables usually expect. A total of 21 means nothing until you know it came from five items on a 1–5 scale.

With complete data the two are interchangeable: `sum = mean × number of items`. They stop being interchangeable the moment a response is missing.

Use the sum when a manual or a norm table demands it. Otherwise prefer the mean.

## What missing data does

CPDM skips blanks rather than treating them as zero. For a respondent who answered four of five items:

- **Mean** — the average of the four answers. Still on the 1–5 scale, still comparable to a complete respondent, on slightly thinner evidence.
- **Sum** — the total of four items, compared against totals built from five. The respondent looks systematically lower for a reason that has nothing to do with the construct.

This is the practical argument for the mean: it degrades gracefully. If you need sums, deal with the missing values first.

## How much missingness is acceptable

A common convention is the **half rule**: compute a scale score if the respondent answered at least half the items; otherwise leave it missing. Some instruments specify their own threshold — follow it when they do.

CPDM does not enforce a threshold. It will happily average a single answered item out of nine, and the result will look as confident as any other. If that matters for your analysis, count the answered items per respondent after exporting and blank out the scores that rest on too little.

Before working around missing data, look at *why* it is missing. Blanks concentrated in one item usually point at a badly worded question; blanks concentrated at the end of the form point at fatigue; blanks concentrated in one subgroup are a finding, not a nuisance.

## The other three functions

**Minimum** and **maximum** describe a respondent's extremes rather than their level — useful for spotting straight-lining (min equals max across every item, so they ticked one column all the way down).

**Standard deviation** across a respondent's items measures how much they varied. A standard deviation of 0 is the same red flag: every answer identical. Neither is a scale score; both are quality checks.

## Interpreting what comes out

A scale score is only as meaningful as the set of items behind it. Averaging items that measure different things produces a number with no referent, however tidy it looks.

Two checks are worth running after exporting, neither of which CPDM performs:

- **Internal consistency** (Cronbach's alpha, or better, omega) — do the items behave as one scale in *this* sample?
- **The distribution of the score** — floor and ceiling effects, or a bimodal shape, change what the mean is telling you.
