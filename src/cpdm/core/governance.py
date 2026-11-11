"""Privacy, scoped authorization, durable audit, and retention contracts."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

from cpdm.core.contracts import ContractError


PRIVACY_CLASSES = ("public", "internal", "confidential", "restricted")
EXPORT_ACTIONS = ("include", "redact", "drop")


@dataclass(frozen=True)
class FieldClassification:
    """Privacy classification and default export action for one field."""

    field: str
    classification: str = "internal"
    export_action: str = "include"

    def __post_init__(self):
        if not str(self.field).strip():
            raise ContractError("Classified field cannot be empty.")
        if self.classification not in PRIVACY_CLASSES:
            raise ContractError(f"Unsupported privacy classification '{self.classification}'.")
        if self.export_action not in EXPORT_ACTIONS:
            raise ContractError(f"Unsupported export action '{self.export_action}'.")


@dataclass(frozen=True)
class ExportPolicy:
    """Apply field-level classifications to tabular exports."""

    fields: tuple[FieldClassification, ...] = ()
    replacement: str = "[REDACTED]"

    def __post_init__(self):
        fields = tuple(self.fields)
        names = [item.field for item in fields]
        if len(names) != len(set(names)):
            raise ContractError("Export policy fields must be unique.")
        object.__setattr__(self, "fields", fields)

    def preview(self, columns):
        columns = list(columns)
        decisions = {item.field: item for item in self.fields}
        return {
            "included": [
                column for column in columns
                if decisions.get(column, FieldClassification(column)).export_action == "include"
            ],
            "redacted": [
                column for column in columns
                if column in decisions and decisions[column].export_action == "redact"
            ],
            "dropped": [
                column for column in columns
                if column in decisions and decisions[column].export_action == "drop"
            ],
        }

    def apply(self, frame):
        if not isinstance(frame, pd.DataFrame):
            raise ContractError("Export policy requires a pandas DataFrame.")
        preview = self.preview(frame.columns)
        result = frame.drop(columns=preview["dropped"], errors="ignore").copy()
        for column in preview["redacted"]:
            result[column] = self.replacement
        return result


@dataclass(frozen=True)
class Actor:
    """An authenticated actor and the scopes granted to that actor."""

    actor_id: str
    scopes: tuple[str, ...] = ()

    def __post_init__(self):
        if not str(self.actor_id).strip():
            raise ContractError("Actor ID cannot be empty.")
        object.__setattr__(self, "scopes", tuple(str(scope) for scope in self.scopes))


class ScopedAuthorizer:
    """Authorize resource actions using exact or wildcard scopes."""

    def authorize(self, actor, resource, action):
        if not isinstance(actor, Actor):
            raise ContractError("Authorization requires an Actor.")
        required = f"{resource}:{action}"
        allowed = {required, f"{resource}:*", "*:*"}
        if not allowed.intersection(actor.scopes):
            raise ContractError(
                f"Actor '{actor.actor_id}' is not authorized for {required}."
            )
        return True


@dataclass(frozen=True)
class AuditEvent:
    """A durable, append-only governance event."""

    actor: str
    action: str
    resource: str
    revision: int
    details: dict = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def as_dict(self):
        return {
            "actor": str(self.actor),
            "action": str(self.action),
            "resource": str(self.resource),
            "revision": int(self.revision),
            "details": dict(self.details),
            "timestamp": self.timestamp,
        }


class DurableAuditStore:
    """Append and read audit events from a local JSONL file."""

    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event):
        if not isinstance(event, AuditEvent):
            raise ContractError("Audit store requires an AuditEvent.")
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.as_dict(), sort_keys=True) + "\n")
        return event

    def read(self):
        if not self.path.exists():
            return []
        events = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(AuditEvent(**json.loads(line)))
        return events


def resolve_revision_conflict(base, current, proposed):
    """Resolve identical edits and reject divergent collaborative edits."""
    if current == proposed:
        return current
    if current == base:
        return proposed
    if proposed == base:
        return current
    raise ContractError("Conflicting collaborative edits require manual resolution.")
