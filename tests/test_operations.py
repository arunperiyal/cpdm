import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cpdm.core import contracts, operations  # noqa: E402


def test_upload_policy_and_safe_temp_directory():
    policy = operations.UploadPolicy(max_bytes=10)
    assert policy.validate("wave.csv", 10)
    with pytest.raises(contracts.ContractError, match="size limit"):
        policy.validate("wave.csv", 11)
    with pytest.raises(contracts.ContractError, match="Unsupported"):
        policy.validate("wave.exe", 1)
    with operations.SafeTemporaryDirectory() as temporary:
        assert temporary.child("file.csv").parent == temporary.path
        with pytest.raises(contracts.ContractError, match="escapes"):
            temporary.child("../outside")


def test_upload_policy_validates_file_storage_stream():
    class Storage:
        filename = "sample.csv"

        def __init__(self):
            import io
            self.stream = io.BytesIO(b"12345")

    assert operations.UploadPolicy(max_bytes=5).validate_storage(Storage())
    with pytest.raises(contracts.ContractError, match="size limit"):
        operations.UploadPolicy(max_bytes=4).validate_storage(Storage())


def test_job_registry_tracks_progress_and_errors():
    registry = operations.JobRegistry()
    job_id = registry.create("scoring")
    registry.update(job_id, status="running", progress=50)
    registry.update(job_id, status="failed", error="bad input")
    assert registry.get(job_id)["error"] == "bad input"


def test_versioned_document_applies_explicit_migration():
    document = operations.VersionedDocument(
        "example",
        2,
        migrations={1: lambda value: {**value, "renamed": value.pop("old")}},
    )
    assert document.load({"kind": "example", "version": 1, "old": 3})["renamed"] == 3
