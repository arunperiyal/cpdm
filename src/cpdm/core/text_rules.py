"""Text-trimming rules, shared by every cleaning tool.

A *rule* is a plain dict, which is also exactly what gets stored in a cleaning
recipe::

    {"mode": "delimiter", "delimiters": ["/", "("], "keep": "before"}
    {"mode": "non_english_to_end", "strict_ascii": False}
    {"mode": "strip_non_english", "strict_ascii": False}
    {"mode": "tidy"}

A *chain* is an ordered list of rules, applied left to right.
"""

import re

MODE_NONE = "none"
MODE_TO_END = "non_english_to_end"
MODE_DELIMITER = "delimiter"
MODE_STRIP = "strip_non_english"
MODE_TIDY = "tidy"

#: the pre-chain name for the delimiter rule, still accepted in payloads
LEGACY_DELIMITER = "delimiter_to_end"

MODES = (MODE_NONE, MODE_TO_END, MODE_DELIMITER, MODE_STRIP, MODE_TIDY)

KEEP_BEFORE = "before"
KEEP_AFTER = "after"
KEEP_SIDES = (KEEP_BEFORE, KEEP_AFTER)

MODE_LABELS = {
    MODE_NONE: "Leave unchanged",
    MODE_TO_END: "Cut from the first non-English character to the end",
    MODE_DELIMITER: "Cut at a delimiter",
    MODE_STRIP: "Strip non-English characters",
    MODE_TIDY: "Tidy up leftovers",
}

# What counts as "English" when strict_ascii is off: printable ASCII, the Latin
# supplements (café, naïve), Latin Extended Additional, the punctuation people
# actually paste in (curly quotes, dashes, ellipsis) and currency symbols (₹).
_ALLOWED_EXTENDED = (
    "\x20-\x7E"        # printable ASCII
    " -ɏ"    # Latin-1 Supplement, Latin Extended-A and -B
    "Ḁ-ỿ"    # Latin Extended Additional
    "‐-‧"    # dashes, quotation marks, bullets, ellipsis
    "‰-⁞"    # per-mille, primes, misc. punctuation
    "₠-₿"    # currency symbols
)

# "cut at the first non-English character" must not trip over a newline or tab
# inside a header, so whitespace controls stay allowed for detection.
_DISALLOWED_EXTENDED_DETECT = re.compile(f"[^\t\n\r{_ALLOWED_EXTENDED}]")
_DISALLOWED_EXTENDED = re.compile(f"[^{_ALLOWED_EXTENDED}]")
_DISALLOWED_STRICT_DETECT = re.compile(r"[^\x00-\x7F]")
_DISALLOWED_STRICT = re.compile(r"[^\x20-\x7E]")

_WHITESPACE = re.compile(r"\s+")
_EMPTY_BRACKETS = re.compile(r"\(\s*\)|\[\s*\]|\{\s*\}|<\s*>")
# a trailing opener or separator is debris left behind by a cut; '.' is spared
# so that abbreviations survive
_TRAILING_JUNK = re.compile(r"[\s\-‐-―/\\|,;:([{<]+$")
_LEADING_JUNK = re.compile(r"^[\s\-‐-―/\\|,;:)\]}>]+")


# --- rule normalisation --------------------------------------------------
def normalise_rule(rule):
    """Accept the loose shapes the UI and old API send; return a canonical rule."""
    if not isinstance(rule, dict):
        raise ValueError(f"Each text rule must be an object, got {type(rule).__name__}.")

    mode = rule.get("mode", MODE_NONE)
    if mode == LEGACY_DELIMITER:
        mode = MODE_DELIMITER
    if mode not in MODES:
        raise ValueError(
            f"Unknown text rule '{mode}'. Expected one of: {', '.join(MODES)}"
        )

    if mode == MODE_DELIMITER:
        delimiters = rule.get("delimiters")
        if delimiters is None:
            delimiters = rule.get("delimiter", "")
        if isinstance(delimiters, str):
            delimiters = [delimiters]
        delimiters = [str(d) for d in delimiters if str(d) != ""]
        if not delimiters:
            raise ValueError("The delimiter rule needs at least one delimiter.")

        keep = rule.get("keep", KEEP_BEFORE)
        if keep not in KEEP_SIDES:
            raise ValueError(f"'keep' must be one of: {', '.join(KEEP_SIDES)}")
        return {"mode": mode, "delimiters": delimiters, "keep": keep}

    if mode in (MODE_TO_END, MODE_STRIP):
        return {"mode": mode, "strict_ascii": bool(rule.get("strict_ascii", False))}

    return {"mode": mode}


def normalise_chain(rules):
    """Validate a chain and drop its no-op rules."""
    if isinstance(rules, dict):
        rules = [rules]
    if not isinstance(rules, list):
        raise ValueError("Text rules must be a list.")

    chain = [normalise_rule(rule) for rule in rules]
    chain = [rule for rule in chain if rule["mode"] != MODE_NONE]
    if not chain:
        raise ValueError("Add at least one cleaning rule.")
    return chain


def rule_from_mode(mode, delimiter=""):
    """Build a one-rule chain from the pre-chain {mode, delimiter} pair."""
    if mode == LEGACY_DELIMITER or mode == MODE_DELIMITER:
        return normalise_rule({"mode": MODE_DELIMITER, "delimiter": delimiter})
    return normalise_rule({"mode": mode, "strict_ascii": True})


# --- the rules themselves -------------------------------------------------
def _cut_at_non_english(text, strict_ascii):
    pattern = _DISALLOWED_STRICT_DETECT if strict_ascii else _DISALLOWED_EXTENDED_DETECT
    match = pattern.search(text)
    return text[: match.start()].strip() if match else text


def _strip_non_english(text, strict_ascii):
    pattern = _DISALLOWED_STRICT if strict_ascii else _DISALLOWED_EXTENDED
    return _WHITESPACE.sub(" ", pattern.sub("", text)).strip()


def _cut_at_delimiter(text, delimiters, keep):
    """Cut at the earliest occurrence of any delimiter."""
    hit = min(
        ((text.find(d), d) for d in delimiters if d in text),
        default=None,
        key=lambda found: found[0],
    )
    if hit is None:
        return text

    index, delimiter = hit
    if keep == KEEP_AFTER:
        return text[index + len(delimiter):].strip()
    return text[:index].strip()


def tidy(text):
    """Clear the debris a cut leaves behind: `WhatsApp (` -> `WhatsApp`."""
    cleaned = _WHITESPACE.sub(" ", text)

    for _ in range(3):  # nested leftovers such as "name ( [ ] )"
        before = cleaned
        cleaned = _EMPTY_BRACKETS.sub("", cleaned)
        cleaned = _TRAILING_JUNK.sub("", cleaned)
        cleaned = _LEADING_JUNK.sub("", cleaned)
        if cleaned == before:
            break

    return cleaned.strip()


def apply_rule(text, rule):
    """Apply one canonical rule to one string."""
    mode = rule["mode"]

    if mode == MODE_TO_END:
        return _cut_at_non_english(text, rule.get("strict_ascii", False))
    if mode == MODE_STRIP:
        return _strip_non_english(text, rule.get("strict_ascii", False))
    if mode == MODE_DELIMITER:
        return _cut_at_delimiter(text, rule["delimiters"], rule.get("keep", KEEP_BEFORE))
    if mode == MODE_TIDY:
        return tidy(text)
    return text


def apply_chain(text, rules):
    """Apply a canonical chain in order. Non-strings pass through untouched."""
    if not isinstance(text, str):
        return text
    for rule in rules:
        text = apply_rule(text, rule)
    return text


def apply_chain_to_cell(value, rules):
    """Cell-level wrapper: blanks and non-text values are left alone."""
    if value is None or not isinstance(value, str):
        return value
    return apply_chain(value, rules)


# --- descriptions ---------------------------------------------------------
def describe_rule(rule):
    mode = rule["mode"]

    if mode == MODE_DELIMITER:
        shown = " ".join(f"'{d}'" for d in rule["delimiters"])
        side = "keep before" if rule.get("keep", KEEP_BEFORE) == KEEP_BEFORE else "keep after"
        return f"Cut at {shown} ({side})"

    if mode in (MODE_TO_END, MODE_STRIP):
        scope = "ASCII only" if rule.get("strict_ascii") else "keep accents"
        return f"{MODE_LABELS[mode]} ({scope})"

    return MODE_LABELS.get(mode, mode)


def describe_chain(rules):
    return " -> ".join(describe_rule(rule) for rule in rules)
