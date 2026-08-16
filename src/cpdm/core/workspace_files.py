"""Files the console may read and write, and the folder they live in.

``load`` and ``save`` act on the machine running CPDM, not on the machine whose
browser is open — and CPDM has no login, so on a workspace reachable from a
network anyone who can open the page could otherwise read any file the service
can read. Both commands are therefore confined to a data directory:

* ``CPDM_DATA_DIR`` if it is set, otherwise ``<project>/data``, created on first
  use, and
* the bundled ``samples/``, which is read-only from here.

Names are taken as plain file names within those folders; a path that tries to
climb out is refused rather than resolved.
"""

import os

from cpdm.paths import PROJECT_ROOT, SAMPLES_DIR

DATA_DIR = os.environ.get("CPDM_DATA_DIR", os.path.join(PROJECT_ROOT, "data"))

READABLE_SUFFIXES = (".xlsx", ".xlsm", ".csv", ".tsv")
WRITABLE_SUFFIXES = (".xlsx", ".csv")


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    return DATA_DIR


def _entries(directory, label):
    if not os.path.isdir(directory):
        return []
    found = []
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        if not name.lower().endswith(READABLE_SUFFIXES):
            continue
        found.append({
            "name": name,
            "where": label,
            "size_kb": round(os.path.getsize(path) / 1024, 1),
            "path": path,
        })
    return found


def listing():
    """Everything ``load`` could open, from the data folder and the samples."""
    return _entries(DATA_DIR, "data") + _entries(SAMPLES_DIR, "samples")


def _plain_name(name):
    name = (name or "").strip().strip('"').strip("'")
    if not name:
        raise ValueError("Give a file name.")
    if os.path.isabs(name) or os.path.basename(name) != name:
        raise ValueError(
            f"Use a plain file name — '{name}' points outside the data folder. "
            f"Files are read from and written to {DATA_DIR} (and samples/)."
        )
    return name


def resolve_readable(name):
    """The path a ``load`` name refers to, refusing anything outside the folders."""
    name = _plain_name(name)

    for directory in (DATA_DIR, SAMPLES_DIR):
        path = os.path.join(directory, name)
        if os.path.isfile(path):
            return path

    known = ", ".join(entry["name"] for entry in listing()) or "nothing yet"
    raise ValueError(f"No file called '{name}'. Available: {known}")


def resolve_writable(name):
    """Where a ``save`` name should be written, creating the folder if needed."""
    name = _plain_name(name)
    if not name.lower().endswith(WRITABLE_SUFFIXES):
        raise ValueError("Save as .xlsx or .csv.")
    return os.path.join(ensure_data_dir(), name)
