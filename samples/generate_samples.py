"""Regenerate the example datasets in this folder.

    python samples/generate_samples.py

The data is synthetic but deliberately messy in the ways a real bilingual
Google Forms export is messy: bilingual headers and answer options, Likert
responses stored as text, free-text comments, and a few blank cells.
"""

import json
import os
import random

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))

# --- questionnaire definition -------------------------------------------
# (raw bilingual header, clean short name, scale, keying)
ITEMS = [
    ("1. I feel calm and relaxed most days / എനിക്ക് മിക്ക ദിവസവും ശാന്തത അനുഭവപ്പെടുന്നു", "WB1", "Wellbeing", "Direct"),
    ("2. I sleep well at night / എനിക്ക് രാത്രി നന്നായി ഉറങ്ങാൻ കഴിയുന്നു", "WB2", "Wellbeing", "Direct"),
    ("3. I often feel tense for no clear reason / വ്യക്തമായ കാരണമില്ലാതെ പിരിമുറുക്കം തോന്നാറുണ്ട്", "WB3", "Wellbeing", "Reverse"),
    ("4. I enjoy my daily activities / ദൈനംദിന പ്രവർത്തനങ്ങൾ ഞാൻ ആസ്വദിക്കുന്നു", "WB4", "Wellbeing", "Direct"),
    ("5. I feel hopeless about the future / ഭാവിയെക്കുറിച്ച് പ്രതീക്ഷയില്ലായ്മ തോന്നുന്നു", "WB5", "Wellbeing", "Reverse"),
    ("6. I check my phone within minutes of waking up / ഉണർന്ന ഉടനെ ഫോൺ പരിശോധിക്കുന്നു", "DS1", "Digital Stress", "Direct"),
    ("7. Notifications interrupt my work / അറിയിപ്പുകൾ എന്റെ ജോലിയെ തടസ്സപ്പെടുത്തുന്നു", "DS2", "Digital Stress", "Direct"),
    ("8. I can put my phone away whenever I choose to / വേണമെന്ന് തോന്നുമ്പോൾ ഫോൺ മാറ്റിവയ്ക്കാൻ കഴിയും", "DS3", "Digital Stress", "Reverse"),
    ("9. I feel anxious when my phone battery is low / ബാറ്ററി കുറയുമ്പോൾ ഉത്കണ്ഠ തോന്നുന്നു", "DS4", "Digital Stress", "Direct"),
]

DEMOGRAPHIC_HEADERS = {
    "Timestamp": "Timestamp",
    "Name / പേര്": "Name",
    "Age / വയസ്സ്": "Age",
    "Gender / ലിംഗം": "Gender",
    "District / ജില്ല": "District",
    "Occupation / തൊഴിൽ": "Occupation",
    "Do you use social media daily? / ദിവസവും സമൂഹമാധ്യമം ഉപയോഗിക്കുന്നുണ്ടോ?": "Daily_Social_Media",
}
COMMENT_HEADER = "Any other comments? / മറ്റ് അഭിപ്രായങ്ങൾ"
COMMENT_CLEAN = "Comments"

LIKERT = {
    "Strongly Agree / പൂർണ്ണമായും യോജിക്കുന്നു": "5",
    "Agree / യോജിക്കുന്നു": "4",
    "Neutral / നിഷ്പക്ഷം": "3",
    "Disagree / വിയോജിക്കുന്നു": "2",
    "Strongly Disagree / പൂർണ്ണമായും വിയോജിക്കുന്നു": "1",
}
GENDERS = {"Male / പുരുഷൻ": "Male", "Female / സ്ത്രീ": "Female"}
YES_NO = {"Yes / അതെ": "Yes", "No / അല്ല": "No"}

NAMES = [
    "Anitha Raj", "Bineesh Kumar", "Chandni Menon", "Deepak Nair", "Elizabeth John",
    "Faisal Rahman", "Gayathri Pillai", "Harish Varma", "Irene Thomas", "Jithin Joseph",
    "Kavya Suresh", "Lijo Mathew", "Meera Krishnan", "Nithin Das", "Oommen Cherian",
    "Parvathy Menon", "Rahul Prasad", "Sandra Jacob", "Tony Sebastian", "Uma Shankar",
    "Vishnu Prakash", "Wilson Fernandez", "Xavier Lopez", "Yamuna Devi", "Zainab Ali",
    "Arun Gopal", "Bhavana Rao", "Cyril Antony", "Divya Menon", "Emil Kurian",
    "Farhan Basheer", "Greeshma Nair",
]
DISTRICTS = ["Ernakulam", "Thrissur", "Kozhikode", "Kollam", "Wayanad", "Palakkad"]
OCCUPATIONS = ["Student", "Teacher", "Nurse", "Software Engineer", "Shopkeeper", "Homemaker"]
COMMENTS = [
    "The survey was easy to fill.",
    "",
    "കുറച്ചു ചോദ്യങ്ങൾ കൂടി വേണം",
    "Some questions felt repetitive.",
    "",
    "Please share the results with us.",
    "No comments",
    "",
]


def _responses(rng, count, start_day):
    rows = []
    likert_options = list(LIKERT.keys())

    for index in range(count):
        row = {
            "Timestamp": f"2025-0{start_day}-{(index % 27) + 1:02d} {9 + index % 8}:{(index * 7) % 60:02d}:00",
            "Name / പേര്": NAMES[index % len(NAMES)],
            "Age / വയസ്സ്": rng.randint(18, 58),
            "Gender / ലിംഗം": rng.choice(list(GENDERS.keys())),
            "District / ജില്ല": rng.choice(DISTRICTS),
            "Occupation / തൊഴിൽ": rng.choice(OCCUPATIONS),
            "Do you use social media daily? / ദിവസവും സമൂഹമാധ്യമം ഉപയോഗിക്കുന്നുണ്ടോ?": rng.choice(list(YES_NO.keys())),
        }
        for position, (raw_header, _, _, _) in enumerate(ITEMS):
            # leave a few cells blank so the mean/sum behaviour is worth showing
            blank = (index % 11 == 0 and position == 2) or (index % 13 == 0 and position == 6)
            row[raw_header] = "" if blank else rng.choice(likert_options)
        row[COMMENT_HEADER] = rng.choice(COMMENTS)
        rows.append(row)

    columns = (
        list(DEMOGRAPHIC_HEADERS.keys())
        + [raw for raw, _, _, _ in ITEMS]
        + [COMMENT_HEADER]
    )
    return pd.DataFrame(rows, columns=columns)


def cleaning_recipe():
    """A recipe keyed on the raw headers, so it applies to an untouched export."""
    header_map = dict(DEMOGRAPHIC_HEADERS)
    header_map.update({raw: clean for raw, clean, _, _ in ITEMS})
    header_map[COMMENT_HEADER] = COMMENT_CLEAN

    replacements = {}
    replacements.update(LIKERT)
    replacements.update(GENDERS)
    replacements.update(YES_NO)

    return {
        "header_map": header_map,
        "value_replacements": {"_global": replacements},
        # given as raw names: CPDM translates them through the header map
        "ignored_columns": ["Timestamp", "Name / പേര്", COMMENT_HEADER],
    }


def main():
    wave1 = _responses(random.Random(7), 30, start_day=3)
    wave2 = _responses(random.Random(21), 12, start_day=9)

    wave1.to_excel(os.path.join(HERE, "sample_survey.xlsx"), index=False, sheet_name="Responses")
    wave1.to_csv(os.path.join(HERE, "sample_survey.csv"), index=False)
    wave2.to_csv(os.path.join(HERE, "sample_survey_wave2.csv"), index=False)

    with open(os.path.join(HERE, "sample_cleaning_rules.json"), "w", encoding="utf-8") as handle:
        json.dump(cleaning_recipe(), handle, indent=2, ensure_ascii=False)

    print(f"Wrote 4 sample files to {HERE}")
    print(f"  wave 1: {wave1.shape[0]} rows x {wave1.shape[1]} columns")
    print(f"  wave 2: {wave2.shape[0]} rows x {wave2.shape[1]} columns")


if __name__ == "__main__":
    main()
