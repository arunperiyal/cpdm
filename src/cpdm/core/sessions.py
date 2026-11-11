"""Durable session contracts and local persistence primitives."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from threading import RLock
from uuid import uuid4
import time

import pandas as pd

from cpdm.core.dataset import Dataset
from cpdm.core.contracts import ContractError


SESSION_SCHEMA_VERSION = 1
SESSION_STATES = {"active", "closed", "expired"}


def _now():
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SessionMetadata:
    """Ownership and lifecycle metadata for one persisted dataset session."""

    session_id: str
    owner_id: str
    created_at: str
    updated_at: str
    state: str = "active"
    schema_version: int = SESSION_SCHEMA_VERSION

    def __post_init__(self):
        if not self.session_id.strip() or not self.owner_id.strip():
            raise ContractError("Session ID and owner ID cannot be empty.")
        if self.state not in SESSION_STATES:
            raise ContractError(f"Unsupported session state '{self.state}'.")
        if self.schema_version != SESSION_SCHEMA_VERSION:
            raise ContractError(
                f"Unsupported session schema version {self.schema_version}."
            )

    @classmethod
    def create(cls, owner_id, session_id=None):
        now = _now()
        return cls(
            session_id=session_id or uuid4().hex,
            owner_id=str(owner_id),
            created_at=now,
            updated_at=now,
        )

    def touch(self, state=None):
        return SessionMetadata(
            session_id=self.session_id,
            owner_id=self.owner_id,
            created_at=self.created_at,
            updated_at=_now(),
            state=state or self.state,
            schema_version=self.schema_version,
        )

    def as_dict(self):
        return {
            "session_id": self.session_id,
            "owner_id": self.owner_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "state": self.state,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, payload):
        if not isinstance(payload, dict):
            raise ContractError("Session metadata must be a JSON object.")
        return cls(**payload)


class SessionLock:
    """Process-local lock for a session; durable stores may add OS locks later."""

    _locks = {}
    _registry_lock = RLock()

    def __init__(self, session_id):
        self.session_id = session_id
        with self._registry_lock:
            self._lock = self._locks.setdefault(session_id, RLock())

    def __enter__(self):
        self._lock.acquire()
        return self

    def __exit__(self, *_):
        self._lock.release()


class SessionStore:
    """Abstract storage contract implemented by local durable stores."""

    def create(self, owner_id):
        raise NotImplementedError

    def load(self, session_id, owner_id):
        raise NotImplementedError

    def save(self, session_id, dataset):
        raise NotImplementedError

    def close(self, session_id, owner_id):
        raise NotImplementedError

    def cleanup(self, max_age_seconds):
        raise NotImplementedError


class LocalSessionStore(SessionStore):
    """Persist session data under one configurable local storage root."""

    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id):
        if not session_id or Path(session_id).name != session_id:
            raise ContractError("Invalid session ID.")
        return self.root / session_id

    def _metadata_path(self, session_id):
        return self._path(session_id) / "metadata.json"

    def _read_metadata(self, session_id):
        path = self._metadata_path(session_id)
        if not path.exists():
            raise ContractError(f"Unknown session '{session_id}'.")
        return SessionMetadata.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def _assert_owner(self, metadata, owner_id):
        if metadata.owner_id != str(owner_id):
            raise ContractError("Session ownership does not match.")
        if metadata.state != "active":
            raise ContractError(f"Session is {metadata.state}.")

    def create(self, owner_id):
        metadata = SessionMetadata.create(owner_id)
        path = self._path(metadata.session_id)
        path.mkdir()
        (path / "metadata.json").write_text(
            json.dumps(metadata.as_dict(), indent=2), encoding="utf-8"
        )
        return metadata

    def load(self, session_id, owner_id):
        with SessionLock(session_id):
            metadata = self._read_metadata(session_id)
            self._assert_owner(metadata, owner_id)
            data_path = self._path(session_id) / "data.pkl"
            state_path = self._path(session_id) / "state.json"
            if not data_path.exists() or not state_path.exists():
                raise ContractError(f"Session '{session_id}' has no saved dataset.")
            frame = pd.read_pickle(data_path)
            saved = json.loads(state_path.read_text(encoding="utf-8"))
            dataset = Dataset()
            dataset.load(frame, saved["filename"])
            dataset.categories = saved["categories"]
            dataset.groups = saved["groups"]
            dataset.scales = saved["scales"]
            dataset.answers = saved["answers"]
            dataset.cleaning_rules = saved["cleaning_rules"]
            return metadata, dataset

    def save(self, session_id, dataset):
        if not isinstance(dataset, Dataset):
            raise ContractError("Local session storage requires a Dataset.")
        with SessionLock(session_id):
            metadata = self._read_metadata(session_id)
            if metadata.state != "active":
                raise ContractError(f"Session is {metadata.state}.")
            path = self._path(session_id)
            if dataset.df is None:
                raise ContractError("Cannot persist a session without a dataset.")
            dataset.df.to_pickle(path / "data.pkl")
            state = {
                "filename": dataset.filename,
                "categories": dataset.categories,
                "groups": dataset.groups,
                "scales": dataset.scales,
                "answers": dataset.answers,
                "cleaning_rules": dataset.cleaning_rules,
            }
            (path / "state.json").write_text(
                json.dumps(state, indent=2, default=str), encoding="utf-8"
            )
            updated = metadata.touch()
            (path / "metadata.json").write_text(
                json.dumps(updated.as_dict(), indent=2), encoding="utf-8"
            )
            return updated

    def close(self, session_id, owner_id):
        with SessionLock(session_id):
            metadata = self._read_metadata(session_id)
            self._assert_owner(metadata, owner_id)
            closed = metadata.touch("closed")
            self._metadata_path(session_id).write_text(
                json.dumps(closed.as_dict(), indent=2), encoding="utf-8"
            )
            return closed

    def cleanup(self, max_age_seconds):
        if max_age_seconds < 0:
            raise ContractError("Cleanup age cannot be negative.")
        now = time.time()
        removed = []
        for path in self.root.iterdir():
            if not path.is_dir():
                continue
            try:
                metadata = self._read_metadata(path.name)
                updated = datetime.fromisoformat(metadata.updated_at).timestamp()
            except (ContractError, OSError, ValueError):
                continue
            if now - updated > max_age_seconds:
                shutil.rmtree(path)
                removed.append(path.name)
        return removed

    def backup(self, session_id, target):
        """Copy a complete session directory to an explicit backup path."""
        source = self._path(session_id)
        if not source.exists():
            raise ContractError(f"Unknown session '{session_id}'.")
        target = Path(target).expanduser().resolve()
        if target == source or source in target.parents:
            raise ContractError("Backup target cannot be inside the session.")
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        return target

    def restore(self, session_id, backup):
        """Restore a session directory after validating its metadata."""
        source = Path(backup).expanduser().resolve()
        if not (source / "metadata.json").exists():
            raise ContractError("Backup is missing session metadata.")
        metadata = SessionMetadata.from_dict(
            json.loads((source / "metadata.json").read_text(encoding="utf-8"))
        )
        if metadata.session_id != session_id:
            raise ContractError("Backup session ID does not match restore target.")
        target = self._path(session_id)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        return metadata
