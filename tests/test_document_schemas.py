import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cpdm.core import contracts, document_schemas  # noqa: E402


def test_legacy_recipe_migrates_to_canonical_schema():
    migrated = document_schemas.load_document(
        "recipe",
        {"header_map": {"old": "new"}, "value_replacements": {}, "ignored_columns": []},
    )
    assert migrated["kind"] == "recipe"
    assert migrated["version"] == 2
    assert migrated["steps"] == []


def test_all_persisted_document_kinds_have_current_schema():
    for kind in document_schemas.SCHEMAS:
        assert document_schemas.load_document(kind, {})["kind"] == kind
    with pytest.raises(contracts.ContractError, match="Unknown document"):
        document_schemas.load_document("unknown", {})
