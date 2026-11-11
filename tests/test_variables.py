import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cpdm.core import contracts, variables  # noqa: E402


def test_variable_catalog_validates_roles_and_provenance():
    catalog = variables.VariableCatalog([
        variables.VariableDefinition("person_id", role="identifier"),
        variables.VariableDefinition(
            "score", role="outcome", derived_from=("item_a",)
        ),
        variables.VariableDefinition("item_a", role="predictor"),
    ])
    assert catalog.validate().get("score").role == "outcome"

    with pytest.raises(contracts.ContractError, match="unknown provenance"):
        variables.VariableCatalog([
            variables.VariableDefinition("score", derived_from=("missing",)),
        ]).validate()
