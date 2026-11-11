import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cpdm.core import contracts, dyads  # noqa: E402


ROLE_DEFINITION = dyads.RoleDefinition(
    {"H": "Husband", "W": "Wife"},
    required=("H", "W"),
)


def long_table():
    return pd.DataFrame([
        {"couple_id": "1", "participant_id": "1H", "role": "H",
         "couple_type": "together", "Q1": 2, "Q2": 4},
        {"couple_id": "1", "participant_id": "1W", "role": "W",
         "couple_type": "together", "Q1": 3, "Q2": 5},
        {"couple_id": "2", "participant_id": "2H", "role": "H",
         "couple_type": "separated", "Q1": 1, "Q2": 2},
        {"couple_id": "2", "participant_id": "2W", "role": "W",
         "couple_type": "separated", "Q1": 4, "Q2": 1},
    ])


def test_participant_key_and_dyad_diagnostics():
    key = dyads.ParticipantKey.parse("42A")
    assert key.dyad_id == "42"
    assert key.role_code == "A"

    table = dyads.DyadTable(
        long_table(), "couple_id", "role", "participant_id", ROLE_DEFINITION
    )
    diagnostics = table.diagnostics()
    assert diagnostics["valid"] is True
    assert diagnostics["dyads"] == 2
    assert diagnostics["roles"] == ["H", "W"]
    assert diagnostics["analysis_columns"] == ["couple_type", "Q1", "Q2"]


def test_dyad_validation_rejects_duplicate_and_incomplete_roles():
    duplicate = long_table().iloc[[0, 0, 1, 2]].copy()
    with pytest.raises(contracts.ContractError, match="Duplicate participant"):
        dyads.DyadTable(
            duplicate, "couple_id", "role", "participant_id", ROLE_DEFINITION
        ).validate()

    incomplete = long_table().iloc[[0, 1, 2]].copy()
    with pytest.raises(contracts.ContractError, match="Incomplete dyad"):
        dyads.DyadTable(
            incomplete, "couple_id", "role", "participant_id", ROLE_DEFINITION
        ).validate()


def test_reshape_round_trip_preserves_ids_and_roles():
    plan = dyads.ReshapePlan(
        "couple_id",
        "role",
        value_columns=("Q1", "Q2"),
        id_columns=("couple_type",),
        role_definition=ROLE_DEFINITION,
    )
    wide = plan.to_wide(long_table())

    assert wide.columns.tolist() == [
        "couple_id", "couple_type", "Q1_h", "Q1_w", "Q2_h", "Q2_w"
    ]
    assert wide.loc[wide["couple_id"] == "1", "Q1_w"].item() == 3

    restored = plan.to_long(wide).sort_values(["couple_id", "role"]).reset_index(drop=True)
    expected = long_table().drop(columns="participant_id").sort_values(
        ["couple_id", "role"]
    )[["couple_id", "couple_type", "role", "Q1", "Q2"]].reset_index(drop=True)
    pd.testing.assert_frame_equal(restored, expected)


def test_derived_variables_cover_actor_partner_and_cross_partner_operations():
    plan = dyads.ReshapePlan(
        "couple_id",
        "role",
        value_columns=("Q1", "Q2"),
        role_definition=ROLE_DEFINITION,
    )
    wide = plan.to_wide(long_table())
    wide = dyads.DerivedVariable("actor_q1_h", "actor", "Q1", role="H").apply(wide)
    wide = dyads.DerivedVariable("partner_q1_h", "partner", "Q1", partner_role="W").apply(wide)
    wide = dyads.DerivedVariable(
        "q1_difference", "difference", "Q1", role="H", partner_role="W"
    ).apply(wide)
    wide = dyads.DerivedVariable(
        "q1_interaction", "interaction", "Q1", role="H", partner_role="W"
    ).apply(wide)

    row = wide.loc[wide["couple_id"] == "1"].iloc[0]
    assert row["actor_q1_h"] == 2
    assert row["partner_q1_h"] == 3
    assert row["q1_difference"] == -1
    assert row["q1_interaction"] == 6
