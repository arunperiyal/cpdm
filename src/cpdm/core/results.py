"""Structured results shared by core services and API adapters."""

from dataclasses import dataclass, field


@dataclass
class OperationResult:
    """A stable summary of a core operation.

    ``details`` keeps operation-specific fields while the top-level shape
    remains consistent for the web API and future batch runners.
    """

    operation: str
    changed: bool = False
    warnings: list[str] = field(default_factory=list)
    provenance: dict = field(default_factory=dict)
    details: dict = field(default_factory=dict)

    def as_dict(self):
        result = {
            "operation": self.operation,
            "changed": self.changed,
            "warnings": list(self.warnings),
            "provenance": dict(self.provenance),
        }
        result.update(self.details)
        return result
