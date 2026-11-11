"""Portable project configuration, bundles, and collaboration safeguards."""

from dataclasses import dataclass, field
import io
import json
from pathlib import PurePosixPath
import zipfile

from cpdm.core.contracts import ContractError


@dataclass(frozen=True)
class ProjectConfig:
    """Machine-portable project settings without dataset state."""

    name: str
    schema_version: int = 1
    documents: tuple[str, ...] = ()
    analysis_capabilities: tuple[dict, ...] = ()
    settings: dict = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "documents", tuple(self.documents))
        object.__setattr__(
            self, "analysis_capabilities", tuple(self.analysis_capabilities)
        )

    def as_dict(self):
        return {
            "name": self.name,
            "schema_version": self.schema_version,
            "documents": list(self.documents),
            "analysis_capabilities": list(self.analysis_capabilities),
            "settings": dict(self.settings),
        }


class PortableBundle:
    """Create and inspect a safe zip bundle of project definitions."""

    @staticmethod
    def write(path, config, files):
        if not isinstance(config, ProjectConfig):
            raise ContractError("Portable bundles require a ProjectConfig.")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("project.json", json.dumps(config.as_dict(), indent=2))
            for name, content in files.items():
                target = PurePosixPath(str(name))
                if target.is_absolute() or ".." in target.parts:
                    raise ContractError("Bundle file path escapes the project root.")
                bundle.writestr(str(target), content)
        return path

    @staticmethod
    def read(path):
        with zipfile.ZipFile(path) as bundle:
            names = bundle.namelist()
            if "project.json" not in names:
                raise ContractError("Portable bundle is missing project.json.")
            config = ProjectConfig(**json.loads(bundle.read("project.json")))
            files = {
                name: bundle.read(name)
                for name in names if name != "project.json"
            }
        return config, files


@dataclass
class AuditLog:
    """Append-only local audit events for collaboration-aware workflows."""

    events: list[dict] = field(default_factory=list)

    def record(self, actor, action, resource, revision):
        self.events.append({
            "actor": str(actor),
            "action": str(action),
            "resource": str(resource),
            "revision": int(revision),
        })


class RevisionedDocument:
    """Optimistic-concurrency guard for optional collaborative editing."""

    def __init__(self, value=None, revision=0, audit_log=None):
        self.value = value
        self.revision = revision
        self.audit_log = audit_log or AuditLog()

    def update(self, value, *, expected_revision, actor, resource):
        if expected_revision != self.revision:
            raise ContractError(
                f"Revision conflict: expected {expected_revision}, current {self.revision}."
            )
        self.revision += 1
        self.value = value
        self.audit_log.record(actor, "update", resource, self.revision)
        return self.revision
