# Likert Items and Likert Scales

A **Likert item** is a single statement with ordered response options — *Strongly Disagree* through *Strongly Agree*. A **Likert scale** is a set of such items that together measure one construct. The distinction matters: almost everything CPDM does assumes you are building the second from the first.

## Why several items instead of one

Any single question is a noisy measurement. It picks up the respondent's mood, their reading of one particular word, and whatever they did that morning. Averaging several items aimed at the same construct lets the shared signal accumulate while the item-specific noise partly cancels.

That only works if the items really do measure the same thing. Five questions about sleep, mood, energy, outlook and calm can form a wellbeing scale; five questions about five unrelated topics cannot, however neatly they are averaged.

## Coding the responses

Responses arrive as text and have to become numbers before anything can be computed. The conventional coding for a five-point agreement scale:

| Response | Code |
| --- | --- |
| Strongly Disagree | 1 |
| Disagree | 2 |
| Neutral | 3 |
| Agree | 4 |
| Strongly Agree | 5 |

Keep the direction consistent — higher always meaning "more of the construct" — and keep the same coding across every item. In CPDM this is the value-replacement step; do it for the whole dataset at once so no item ends up coded backwards.

Starting at 1 rather than 0 is a convention, not a rule, but the reverse-scoring formula CPDM uses assumes a minimum of 1. See [Reverse Scoring](/docs/theory/reverse-scoring).

## Ordinal data treated as interval

Strictly, Likert responses are **ordinal**: we know *Agree* is more agreement than *Neutral*, but not that the gap is the same size as the one between *Neutral* and *Disagree*. Means and standard deviations assume equal gaps — interval data.

The usual compromise in practice:

- For a **single item**, report the median or the distribution of responses. A mean of 3.4 on one item is hard to interpret.
- For a **scale score** built from several items, the mean is broadly accepted and behaves well in practice, especially with five or more response options and four or more items.

This is a live methodological argument, not settled fact. If you plan to publish, say what you did and why.

## How many response options

Five and seven are the common choices. More options give finer discrimination up to a point, then stop helping because respondents cannot reliably distinguish them. An even number removes the midpoint and forces a direction — a design decision, not a technical one.

Whatever you choose, record the maximum: CPDM needs it for reverse scoring, and using the wrong one silently corrupts the data.

## Neutral answers and non-response

A *Neutral* response is data: the respondent answered, choosing the midpoint. A blank is not: the respondent did not answer. They should never be coded the same way. In CPDM, a mapped `Neutral` becomes 3, while a blank cell stays blank and is skipped by row calculations — see [Scale Scores](/docs/theory/scale-scores).
