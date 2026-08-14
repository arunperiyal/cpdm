"""The process-wide session.

CPDM is a single-user desktop-style tool, so one module-level dataset is shared
by every request. Import ``session`` rather than constructing a Dataset; it is
reset in place so existing references stay valid.
"""

from cpdm.core.dataset import Dataset

session = Dataset()


def reset():
    """Drop all working state (used by tests)."""
    session.reset()
    return session
