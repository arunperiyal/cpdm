# Reverse Scoring

Questionnaires usually mix positively and negatively worded items. Before those items can be combined into one score, the negatively worded ones must be flipped so that a high number means the same thing everywhere.

## Why the mixture exists

Asking every question in the same direction invites **acquiescence bias** — the habit of agreeing with whatever is put in front of you — and lets a respondent tick straight down the page without reading. Mixing the wording breaks that rhythm and forces engagement.

The cost is that raw responses are no longer comparable across items.

## What "reverse-keyed" means

Consider a wellbeing scale where higher should mean better:

- `WB1` *"I feel calm and relaxed most days"* — agreeing means **more** wellbeing.
- `WB3` *"I often feel tense for no clear reason"* — agreeing means **less** wellbeing.

A respondent who is doing well answers 5 to the first and 1 to the third. Averaging those raw numbers gives 3, which describes nobody. `WB3` has to be flipped first.

## The formula

For a scale running from `min` to `max`:

```
reversed = (min + max) − original
```

On the usual 1–5 scale that is `6 − x`:

| Original | Reversed |
| --- | --- |
| 1 | 5 |
| 2 | 4 |
| 3 | 3 |
| 4 | 2 |
| 5 | 1 |

On a 1–7 scale it is `8 − x`. CPDM takes both ends from the scale's own option scores, so there is no maximum to supply.

## The two ways to get it wrong

**The wrong maximum.** Entering 5 for a 1–7 item turns a response of 6 into 0 and a 7 into −1. Nothing errors; the score column just quietly stops meaning anything. CPDM avoids this by deriving the range from the options you scored — but that only helps if the option list is complete, so add the answers nobody happened to choose. After scoring, run `summary` at the prompt and check that every item's minimum and maximum still sit inside the response range.

**Scoring twice.** The transformation is its own inverse: apply it again and you are back where you started. If you are unsure whether scoring has been applied, look at the data rather than guessing — a reverse item's relationship with the rest of the scale should be positive once it is flipped.

## Checking that the keying is right

Once every item points the same way, a respondent's answers across the items of one scale should be broadly consistent. If one item still runs against the others — high where the rest are low, across many respondents — one of three things is true: it needed reversing and was not, it was reversed when it should not have been, or it does not belong in the scale.

CPDM does not compute item-total correlations, so this check belongs in whatever you use after exporting.

## Which items to reverse

Decide from the wording, before you see the data, and write it down. If the questionnaire is a published instrument, its manual states which items are reverse-keyed — follow the manual rather than your own reading. Reversing an item because it "correlates the wrong way" is fitting the scoring to the sample.
