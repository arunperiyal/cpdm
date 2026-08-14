"""Reusable text-trimming rules shared by every cleaning tool."""

import re

import pandas as pd

MODE_NONE = "none"
MODE_TO_END = "non_english_to_end"
MODE_DELIMITER = "delimiter_to_end"
MODE_STRIP = "strip_non_english"

MODES = (MODE_NONE, MODE_TO_END, MODE_DELIMITER, MODE_STRIP)

MODE_LABELS = {
    MODE_NONE: "Leave unchanged",
    MODE_TO_END: "Remove from the first non-English character to the end",
    MODE_DELIMITER: "Remove from a chosen delimiter to the end",
    MODE_STRIP: "Strip all non-English characters",
}

_NON_ASCII = re.compile(r"[^\x00-\x7F]")
_NON_PRINTABLE_ASCII = re.compile(r"[^\x20-\x7E]")
_WHITESPACE = re.compile(r"\s+")


def apply_mode(value, mode, delimiter=""):
    """Apply one trimming rule to a single value.

    Non-strings (numbers, NaN, dates) are returned untouched.
    """
    if value is None or not isinstance(value, str):
        return value

    if mode == MODE_TO_END:
        match = _NON_ASCII.search(value)
        return value[: match.start()].strip() if match else value

    if mode == MODE_DELIMITER and delimiter:
        if delimiter in value:
            return value.split(delimiter)[0].strip()
        return value

    if mode == MODE_STRIP:
        cleaned = _NON_PRINTABLE_ASCII.sub("", value)
        return _WHITESPACE.sub(" ", cleaned).strip()

    return value


def apply_mode_to_cell(value, mode, delimiter=""):
    """Cell-level wrapper that preserves missing values."""
    if pd.isna(value):
        return value
    return apply_mode(str(value), mode, delimiter)


def validate(mode, delimiter=""):
    if mode not in MODES:
        raise ValueError(f"Unknown text rule '{mode}'. Expected one of: {', '.join(MODES)}")
    if mode == MODE_DELIMITER and not delimiter:
        raise ValueError("A delimiter is required for the 'delimiter to end' rule.")
    return mode
