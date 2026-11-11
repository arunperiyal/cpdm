import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cpdm.core import contracts, sessions  # noqa: E402


def test_session_metadata_tracks_owner_lifecycle_and_version():
    metadata = sessions.SessionMetadata.create("analyst", "session-1")
    assert metadata.state == "active"
    assert metadata.as_dict()["schema_version"] == 1
    closed = metadata.touch("closed")
    assert closed.owner_id == "analyst"
    assert closed.state == "closed"


def test_session_metadata_rejects_invalid_contracts():
    with pytest.raises(contracts.ContractError, match="owner"):
        sessions.SessionMetadata.create("")
    with pytest.raises(contracts.ContractError, match="state"):
        sessions.SessionMetadata("s", "o", "now", "now", state="broken")


def test_session_lock_is_reentrant_for_one_session():
    with sessions.SessionLock("one"):
        with sessions.SessionLock("one"):
            assert True
