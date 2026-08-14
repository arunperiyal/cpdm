"""The example datasets shipped in ``samples/``, offered as downloads."""

import os

from cpdm.paths import SAMPLES_DIR

DESCRIPTIONS = {
    "sample_survey.xlsx": "Messy wellbeing survey (30 responses) — the main worked example.",
    "sample_survey.csv": "The same survey as CSV, for testing the CSV reader.",
    "sample_survey_wave2.csv": "A second wave of the same questionnaire, for replaying a saved recipe.",
    "sample_cleaning_rules.json": "A finished cleaning recipe for the survey above.",
}

DOWNLOADABLE = (".xlsx", ".xlsm", ".csv", ".tsv", ".json")


def listing():
    """Sample files with size and description, ready for the docs page."""
    if not os.path.isdir(SAMPLES_DIR):
        return []

    files = []
    for filename in sorted(os.listdir(SAMPLES_DIR)):
        path = os.path.join(SAMPLES_DIR, filename)
        if not os.path.isfile(path):
            continue
        if os.path.splitext(filename)[1].lower() not in DOWNLOADABLE:
            continue
        files.append(
            {
                "name": filename,
                "size_kb": round(os.path.getsize(path) / 1024, 1),
                "description": DESCRIPTIONS.get(filename, ""),
                "url": f"/samples/{filename}",
            }
        )
    return files


def resolve(filename):
    """Guard against path traversal, then return the absolute sample path."""
    safe = os.path.basename(filename)
    path = os.path.join(SAMPLES_DIR, safe)
    if not os.path.isfile(path):
        raise ValueError(f"No sample file named '{safe}'.")
    return SAMPLES_DIR, safe
