"""What the About box reports: the app, its footing, and what is loaded.

Nothing here is invented. The licence line reads the repository rather than
claiming one, so a project without a LICENSE file says so plainly instead of
implying terms nobody has agreed.
"""

import os
import platform
import subprocess
import sys
from importlib import metadata

from cpdm import __version__
from cpdm.paths import PROJECT_ROOT

NAME = "CPDM"
FULL_NAME = "Comprehensive Package for Data Management"
SUMMARY = (
    "A local workspace for preparing survey and questionnaire data: cleaning "
    "messy headers and answers, grouping columns, defining scales and scoring "
    "them, then computing per-respondent scores and exporting the result."
)
REPOSITORY = "https://github.com/arunperiyal/cpdm"

CONTRIBUTORS = [
    {"name": "Juby Merin Sam", "email": "jubymerinsam@gmail.com"},
    {"name": "Arun Periyal", "email": "periyal.arun@gmail.com"},
]

LICENCE_FILES = ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING")


def licence():
    """The licence as the repository states it — or the fact that it does not."""
    for name in LICENCE_FILES:
        path = os.path.join(PROJECT_ROOT, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as handle:
            first = next((line.strip() for line in handle if line.strip()), "")
        return {"declared": True, "file": name, "summary": first}

    return {
        "declared": False,
        "file": None,
        "summary": "No licence file in this repository, so no terms of reuse are "
                   "granted. Add a LICENSE file to say how others may use it.",
    }


def running_commit():
    """Which commit this process is actually running.

    After a `git pull` the service keeps running the code it started with, so
    this is the honest answer to "did my update take effect?".
    """
    if not os.path.isdir(os.path.join(PROJECT_ROOT, ".git")):
        return None
    try:
        result = subprocess.run(
            ["git", "-C", PROJECT_ROOT, "log", "-1", "--format=%h %cs %s"],
            capture_output=True, text=True, timeout=3, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def dependencies():
    """Installed versions, read from package metadata rather than __version__.

    Flask has deprecated its ``__version__`` attribute, and several libraries
    never had one.
    """
    versions = {}
    for name in ("flask", "pandas", "openpyxl", "markdown", "gunicorn"):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def summary(dataset=None):
    loaded = None
    if dataset is not None and dataset.df is not None:
        loaded = {
            "filename": dataset.filename,
            "rows": int(len(dataset.df)),
            "columns": int(len(dataset.df.columns)),
            "groups": len(dataset.groups),
            "scales": len(dataset.scales),
        }

    return {
        "name": NAME,
        "full_name": FULL_NAME,
        "version": __version__,
        "commit": running_commit(),
        "summary": SUMMARY,
        "repository": REPOSITORY,
        "contributors": CONTRIBUTORS,
        "licence": licence(),
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.release()}",
        "interpreter": sys.executable,
        "dependencies": dependencies(),
        "loaded": loaded,
    }
