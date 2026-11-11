"""Variable roles, provenance links, and export classification."""

from dataclasses import dataclass, field

from cpdm.core.contracts import ContractError


VALID_ROLES = {
    "identifier",
    "grouping",
    "weight",
    "time",
    "predictor",
    "outcome",
    "covariate",
    "analysis",
}


@dataclass(frozen=True)
class VariableDefinition:
    """Metadata for one source or derived variable."""

    name: str
    role: str = "analysis"
    source: str | None = None
    derived_from: tuple[str, ...] = ()
    sensitive: bool = False
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not str(self.name).strip():
            raise ContractError("Variable name cannot be empty.")
        if self.role not in VALID_ROLES:
            raise ContractError(f"Unknown variable role '{self.role}'.")
        object.__setattr__(self, "derived_from", tuple(self.derived_from))

    def as_dict(self):
        return {
            "name": self.name,
            "role": self.role,
            "source": self.source,
            "derived_from": list(self.derived_from),
            "sensitive": self.sensitive,
            "metadata": dict(self.metadata),
        }


class VariableCatalog:
    """Validate variable metadata and provenance references."""

    def __init__(self, definitions=()):
        self._definitions = {}
        for definition in definitions:
            self.add(definition)

    def add(self, definition):
        if not isinstance(definition, VariableDefinition):
            raise ContractError("Variable catalog entries must be VariableDefinition objects.")
        if definition.name in self._definitions:
            raise ContractError(f"Variable '{definition.name}' is already defined.")
        self._definitions[definition.name] = definition

    def validate(self, columns=None):
        known = set(self._definitions)
        for definition in self._definitions.values():
            unknown = set(definition.derived_from) - known
            if unknown:
                raise ContractError(
                    f"Variable '{definition.name}' references unknown provenance: "
                    + ", ".join(sorted(unknown))
                )
        if columns is not None:
            missing = sorted(set(columns) - known)
            if missing:
                raise ContractError("Variables missing from catalog: " + ", ".join(missing))
        return self

    def get(self, name):
        try:
            return self._definitions[name]
        except KeyError:
            raise ContractError(f"Unknown variable '{name}'.") from None

    def as_dict(self):
        return {name: definition.as_dict() for name, definition in self._definitions.items()}
