# Sample Data

Four files ship in the `samples/` folder. Download them from Help → Sample Data Files, or from the sidebar of this documentation browser.

| File | What it is |
| --- | --- |
| `sample_survey.xlsx` | 30 responses to a bilingual wellbeing survey. The main worked example. |
| `sample_survey.csv` | The same 30 responses as CSV. |
| `sample_survey_wave2.csv` | A second wave, 12 responses, identical questionnaire. |
| `sample_cleaning_rules.json` | A finished cleaning recipe for that questionnaire. |

## What is in the survey

Seven background columns (`Timestamp`, name, age, gender, district, occupation, daily social media use), nine Likert items, and one free-text comment column.

The mess is deliberate:

- Every header is `English / മലയാളം`.
- Every answer option is too: `Agree / യോജിക്കുന്നു`.
- A few item cells are blank, as in a real export.
- The comment column mixes English and Malayalam free text, and must survive cleaning intact.

### The nine items

| Column | Scale | Keying |
| --- | --- | --- |
| `WB1` I feel calm and relaxed most days | Wellbeing | Direct |
| `WB2` I sleep well at night | Wellbeing | Direct |
| `WB3` I often feel tense for no clear reason | Wellbeing | **Reverse** |
| `WB4` I enjoy my daily activities | Wellbeing | Direct |
| `WB5` I feel hopeless about the future | Wellbeing | **Reverse** |
| `DS1` I check my phone within minutes of waking up | Digital Stress | Direct |
| `DS2` Notifications interrupt my work | Digital Stress | Direct |
| `DS3` I can put my phone away whenever I choose to | Digital Stress | **Reverse** |
| `DS4` I feel anxious when my phone battery is low | Digital Stress | Direct |

Responses run `Strongly Disagree` = 1 to `Strongly Agree` = 5.

## The shortcut path

1. File → Open → `sample_survey.xlsx`
2. Clean → Apply Cleaning File (.json) → `sample_cleaning_rules.json`

That single recipe renames all seventeen headers to short codes, converts every Likert label to a number, converts the gender and yes/no answers, and marks `Timestamp`, `Name` and `Comments` as ignored so the free text is untouched. You land at the point where scales and scoring begin.

Apply the recipe to a **raw** file: it is keyed on the original bilingual headers, so it will not match a file whose headers you have already trimmed.

## The long path

Skip the recipe and do it by hand, following [Cleaning a Dataset](/docs/help/cleaning-workflow). It takes a few minutes and teaches the trimmer, the ignore list and the value-mapping step, which is the point of the exercise.

## Replaying on wave 2

Open `sample_survey_wave2.csv`, apply the same recipe, and you get identically named and coded columns — the reason for saving recipes at all. Opening a new file resets the session, so export wave 1 before you load wave 2.

## Regenerating

```bash
python samples/generate_samples.py
```

The data is synthetic and generated from fixed seeds, so the files are reproducible. Edit `samples/generate_samples.py` to change the questionnaire.
