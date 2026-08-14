"""Filesystem locations, resolved once so every module agrees on them.

Layout::

    <project root>/
        app.py
        docs/      theory/ and help/ Markdown
        samples/   example datasets
        src/cpdm/  this package (templates/ and static/ live inside it)

``CPDM_DOCS_DIR`` and ``CPDM_SAMPLES_DIR`` override the defaults, which is how
the tests point the app at fixture directories.
"""

import os

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(PACKAGE_DIR)
PROJECT_ROOT = os.path.dirname(SRC_DIR)

TEMPLATES_DIR = os.path.join(PACKAGE_DIR, "templates")
STATIC_DIR = os.path.join(PACKAGE_DIR, "static")

DOCS_DIR = os.environ.get("CPDM_DOCS_DIR", os.path.join(PROJECT_ROOT, "docs"))
SAMPLES_DIR = os.environ.get("CPDM_SAMPLES_DIR", os.path.join(PROJECT_ROOT, "samples"))
