import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cpdm.core import contracts, plugins, project  # noqa: E402


def test_plugin_registry_validates_and_discovers_extensions():
    registry = plugins.PluginRegistry()
    registry.register(plugins.Plugin(
        plugins.PluginMetadata("double", "transformation", version="1"),
        lambda value: value * 2,
    ))
    assert registry.get("transformation", "double").implementation(3) == 6
    assert registry.metadata()[0].api_version == 1


def test_trusted_plugin_manifests_validate_api_and_dependencies():
    registry = plugins.PluginRegistry()
    manifest = plugins.PluginManifest(
        plugins.PluginMetadata("triple", "transformation", version="2"),
        dependencies={"cpdm": ">=1.0"},
        trusted=True,
    )
    registry.register_manifest(manifest, lambda value: value * 3, {"cpdm": "1.2"})
    assert registry.get("transformation", "triple").implementation(2) == 6
    with pytest.raises(contracts.ContractError, match="not explicitly trusted"):
        registry.register_manifest(
            plugins.PluginManifest(
                plugins.PluginMetadata("untrusted", "report"), trusted=False
            ),
            lambda value: value,
        )
    with pytest.raises(contracts.ContractError, match="not satisfied"):
        registry.register_manifest(
            plugins.PluginManifest(
                plugins.PluginMetadata("bad", "report"),
                dependencies={"pandas": ">=3.0"},
                trusted=True,
            ),
            lambda value: value,
            {"pandas": "2.0"},
        )


def test_portable_bundle_and_revision_guard(tmp_path):
    path = tmp_path / "project.cpdm.zip"
    config = project.ProjectConfig(
        "demo",
        documents=("pipeline.json",),
        analysis_capabilities=({"name": "linear_regression"},),
    )
    project.PortableBundle.write(path, config, {"pipeline.json": b"{}"})
    restored, files = project.PortableBundle.read(path)
    assert restored == config
    assert files["pipeline.json"] == b"{}"

    document = project.RevisionedDocument({"value": 1})
    document.update({"value": 2}, expected_revision=0, actor="analyst", resource="project")
    assert document.audit_log.events[0]["revision"] == 1
    with pytest.raises(contracts.ContractError, match="Revision conflict"):
        document.update({}, expected_revision=0, actor="other", resource="project")
