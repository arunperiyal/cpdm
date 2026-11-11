"""Canonical persisted-document schemas and migration registry."""

from cpdm.core.contracts import ContractError
from cpdm.core.operations import VersionedDocument


def _recipe_v1_to_v2(value):
    return {
        **value,
        "steps": [],
        "header_map": value.get("header_map", {}),
        "value_replacements": value.get("value_replacements", {}),
        "ignored_columns": value.get("ignored_columns", []),
    }


def _add_version(value):
    return dict(value)


SCHEMAS = {
    "recipe": VersionedDocument("recipe", 2, {1: _recipe_v1_to_v2}),
    "scale-map": VersionedDocument("scale-map", 1),
    "pipeline": VersionedDocument("pipeline", 1),
    "analysis-result": VersionedDocument("analysis-result", 1),
    "profile-result": VersionedDocument("profile-result", 1),
}


def load_document(kind, payload):
    """Normalize legacy payloads and validate the current canonical schema."""
    schema = SCHEMAS.get(kind)
    if schema is None:
        raise ContractError(f"Unknown document schema '{kind}'.")
    if not isinstance(payload, dict):
        raise ContractError(f"{kind} document must be a JSON object.")
    value = dict(payload)
    value.setdefault("kind", kind)
    value.setdefault("version", 1)
    return schema.load(value)
