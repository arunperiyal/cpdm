"""Durable session contracts and local persistence primitives."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from threading import RLock
from uuid import uuid4

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
