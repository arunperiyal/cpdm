import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cpdm.core import contracts, governance, project  # noqa: E402


def test_field_level_export_policy_previews_and_applies():
    policy = governance.ExportPolicy(fields=(
        governance.FieldClassification("participant_id", "restricted", "drop"),
        governance.FieldClassification("comment", "confidential", "redact"),
        governance.FieldClassification("weight", "confidential", "redact"),
    ))
    frame = pd.DataFrame({
        "participant_id": ["1"], "comment": ["secret"], "weight": [2], "score": [4]
    })

    assert policy.preview(frame.columns) == {
        "included": ["score"],
        "redacted": ["comment", "weight"],
        "dropped": ["participant_id"],
    }
    exported = policy.apply(frame)
    assert list(exported.columns) == ["comment", "weight", "score"]
    assert exported.loc[0, "comment"] == "[REDACTED]"


def test_scoped_authorization_and_revision_conflicts():
    actor = governance.Actor("alice", ("sessions:read", "bundles:*"))
    authorizer = governance.ScopedAuthorizer()
    assert authorizer.authorize(actor, "sessions", "read")
    with pytest.raises(contracts.ContractError, match="not authorized"):
        authorizer.authorize(actor, "audit", "read")
    assert governance.resolve_revision_conflict(1, 1, 2) == 2
    with pytest.raises(contracts.ContractError, match="Conflicting"):
        governance.resolve_revision_conflict({"v": 1}, {"v": 2}, {"v": 3})


def test_durable_audit_store_round_trips_events(tmp_path):
    store = governance.DurableAuditStore(tmp_path / "audit.jsonl")
    store.append(governance.AuditEvent(
        actor="alice", action="export", resource="bundle/demo", revision=2,
        details={"policy": "restricted"},
    ))
    events = store.read()
    assert len(events) == 1
    assert events[0].details["policy"] == "restricted"


def test_bundle_preview_redaction_and_retention(tmp_path):
    source = tmp_path / "source.zip"
    redacted = tmp_path / "redacted.zip"
    config = project.ProjectConfig("demo")
    project.PortableBundle.write(
        source, config, {"public.json": b"{}", "intermediate.csv": b"secret"}
    )
    preview = project.PortableBundle.preview(source, exclude=("intermediate.csv",))
    assert preview["excluded"] == ["intermediate.csv"]
    project.PortableBundle.redact(source, redacted, exclude=("intermediate.csv",))
    _, files = project.PortableBundle.read(redacted)
    assert list(files) == ["public.json"]
    assert project.PortableBundle.delete_if_older(redacted, 0) is True
    assert not redacted.exists()
