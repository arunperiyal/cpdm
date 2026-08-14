"""Discovery and rendering of the Markdown documentation shipped in ``docs/``.

Files live in ``docs/<section>/<name>.md``. A leading number in the filename
(``01-getting-started.md``) only controls ordering and is stripped from the
slug, so the page URL stays ``/docs/help/getting-started``.
"""

import os
import re

from cpdm.core import markdown_lite
from cpdm.paths import DOCS_DIR

SECTIONS = (
    ("help", "Help", "How to drive CPDM, step by step."),
    ("theory", "Theory", "The measurement ideas behind the tools."),
)
SECTION_LABELS = {key: label for key, label, _ in SECTIONS}

_ORDER_PREFIX = re.compile(r"^(\d+)[-_.]")
_cache = {}


def _slug_and_order(filename):
    stem = os.path.splitext(filename)[0]
    match = _ORDER_PREFIX.match(stem)
    if match:
        return stem[match.end():], int(match.group(1))
    return stem, 999


def _section_dir(section):
    return os.path.join(DOCS_DIR, section)


def _read(path):
    """Read and render a document, caching on (path, mtime)."""
    mtime = os.path.getmtime(path)
    cached = _cache.get(path)
    if cached and cached["mtime"] == mtime:
        return cached

    with open(path, encoding="utf-8") as handle:
        source = handle.read()

    entry = {
        "mtime": mtime,
        "source": source,
        "title": markdown_lite.first_heading(source) or os.path.basename(path),
        "summary": markdown_lite.first_paragraph(source),
        "html": markdown_lite.render(source),
    }
    _cache[path] = entry
    return entry


def list_section(section):
    """Every document in one section, ordered by filename prefix then title."""
    directory = _section_dir(section)
    if not os.path.isdir(directory):
        return []

    entries = []
    for filename in os.listdir(directory):
        if not filename.lower().endswith(".md"):
            continue
        slug, order = _slug_and_order(filename)
        doc = _read(os.path.join(directory, filename))
        entries.append(
            {
                "section": section,
                "section_label": SECTION_LABELS.get(section, section.title()),
                "slug": slug,
                "order": order,
                "filename": filename,
                "title": doc["title"],
                "summary": doc["summary"],
                "url": f"/docs/{section}/{slug}",
            }
        )

    return sorted(entries, key=lambda item: (item["order"], item["title"].lower()))


def index():
    """The full navigation tree: one entry per section, with its documents."""
    return [
        {
            "key": key,
            "label": label,
            "blurb": blurb,
            "docs": list_section(key),
        }
        for key, label, blurb in SECTIONS
    ]


def get(section, slug):
    """Render one document, or return None if it does not exist."""
    if section not in SECTION_LABELS:
        return None

    directory = _section_dir(section)
    if not os.path.isdir(directory):
        return None

    for filename in os.listdir(directory):
        if not filename.lower().endswith(".md"):
            continue
        file_slug, _ = _slug_and_order(filename)
        if file_slug != slug:
            continue

        doc = _read(os.path.join(directory, filename))
        return {
            "section": section,
            "section_label": SECTION_LABELS[section],
            "slug": slug,
            "title": doc["title"],
            "summary": doc["summary"],
            "html": doc["html"],
            "source": doc["source"],
        }

    return None


def default_doc():
    """The document shown when /docs is opened with no page selected."""
    for section in index():
        if section["docs"]:
            return section["docs"][0]
    return None
