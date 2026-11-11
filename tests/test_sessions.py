import os
import sys

import pytest
import pandas as pd

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


def test_local_session_store_isolates_two_owned_datasets(tmp_path):
    store = sessions.LocalSessionStore(tmp_path)
    first = store.create("alice")
    second = store.create("bob")

    one = sessions.Dataset()
    one.load(pd.DataFrame({"value": [1]}), "one.csv")
    two = sessions.Dataset()
    two.load(pd.DataFrame({"value": [2]}), "two.csv")
    store.save(first.session_id, one)
    store.save(second.session_id, two)

    _, restored_one = store.load(first.session_id, "alice")
    _, restored_two = store.load(second.session_id, "bob")
    assert restored_one.df["value"].tolist() == [1]
    assert restored_two.df["value"].tolist() == [2]
    with pytest.raises(contracts.ContractError, match="ownership"):
        store.load(first.session_id, "bob")


def test_local_session_store_closes_and_rejects_missing_dataset(tmp_path):
    store = sessions.LocalSessionStore(tmp_path)
    metadata = store.create("alice")
    with pytest.raises(contracts.ContractError, match="no saved dataset"):
        store.load(metadata.session_id, "alice")
    closed = store.close(metadata.session_id, "alice")
    assert closed.state == "closed"


def test_local_session_store_can_backup_and_restore(tmp_path):
    store = sessions.LocalSessionStore(tmp_path / "sessions")
    metadata = store.create("alice")
    dataset = sessions.Dataset()
    dataset.load(pd.DataFrame({"value": [9]}), "backup.csv")
    store.save(metadata.session_id, dataset)
    backup = store.backup(metadata.session_id, tmp_path / "backup")
    (store.root / metadata.session_id / "metadata.json").unlink()
    restored = store.restore(metadata.session_id, backup)
    assert restored.session_id == metadata.session_id
    _, loaded = store.load(metadata.session_id, "alice")
    assert loaded.df["value"].tolist() == [9]
