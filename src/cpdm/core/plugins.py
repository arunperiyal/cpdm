"""Versioned extension points for transformations, estimators, and reports."""

from dataclasses import dataclass
import re

from cpdm.core.contracts import ContractError


PLUGIN_KINDS = {"transformation", "instrument", "estimator", "report"}
PLUGIN_API_VERSION = 1


@dataclass(frozen=True)
class PluginMetadata:
    """Portable metadata describing one registered extension."""

    name: str
    kind: str
    version: str = "0"
    api_version: int = PLUGIN_API_VERSION
    description: str = ""

    def __post_init__(self):
        if not str(self.name).strip():
            raise ContractError("Plugin name cannot be empty.")
        if self.kind not in PLUGIN_KINDS:
            raise ContractError(f"Unsupported plugin kind '{self.kind}'.")
        if self.api_version != PLUGIN_API_VERSION:
            raise ContractError(f"Unsupported plugin API version {self.api_version}.")

    def as_dict(self):
        return {
            "name": self.name,
            "kind": self.kind,
            "version": self.version,
            "api_version": self.api_version,
            "description": self.description,
        }


@dataclass(frozen=True)
class PluginManifest:
    """Trusted project-manifest metadata for one explicitly installed plugin."""

    metadata: PluginMetadata
    dependencies: dict[str, str] = None
    trusted: bool = False

    def __post_init__(self):
        object.__setattr__(self, "dependencies", dict(self.dependencies or {}))

    def as_dict(self):
        return {
            "metadata": self.metadata.as_dict(),
            "dependencies": dict(self.dependencies),
            "trusted": self.trusted,
        }


@dataclass(frozen=True)
class Plugin:
    metadata: PluginMetadata
    implementation: object


class PluginRegistry:
    """Discover and invoke explicitly registered local extensions."""

    def __init__(self):
        self._plugins = {}

    def register(self, plugin):
        if not isinstance(plugin, Plugin) or not callable(plugin.implementation):
            raise ContractError("Plugins need metadata and a callable implementation.")
        key = (plugin.metadata.kind, plugin.metadata.name)
        if key in self._plugins:
            raise ContractError(f"Plugin '{plugin.metadata.name}' is already registered.")
        self._plugins[key] = plugin

    def get(self, kind, name):
        try:
            return self._plugins[(kind, name)]
        except KeyError:
            raise ContractError(f"Unknown {kind} plugin '{name}'.") from None

    def metadata(self):
        return tuple(plugin.metadata for plugin in self._plugins.values())

    def register_manifest(self, manifest, implementation, installed_versions=None):
        """Validate a trusted manifest before making its implementation usable."""
        if not isinstance(manifest, PluginManifest):
            raise ContractError("Plugin registration requires a PluginManifest.")
        if not manifest.trusted:
            raise ContractError("Plugin manifest is not explicitly trusted.")
        installed_versions = dict(installed_versions or {})
        for package, requirement in manifest.dependencies.items():
            version = installed_versions.get(package)
            if version is None or not _satisfies(version, requirement):
                raise ContractError(
                    f"Plugin dependency '{package}{requirement}' is not satisfied."
                )
        self.register(Plugin(manifest.metadata, implementation))
        return manifest.metadata


def _satisfies(version, requirement):
    match = re.fullmatch(r"\s*(>=|<=|==|>|<)\s*([0-9]+(?:\.[0-9]+)*)\s*", requirement)
    if not match:
        raise ContractError(f"Unsupported plugin dependency requirement '{requirement}'.")
    actual = tuple(int(part) for part in str(version).split("."))
    expected = tuple(int(part) for part in match.group(2).split("."))
    operator = match.group(1)
    return {
        ">=": actual >= expected,
        "<=": actual <= expected,
        "==": actual == expected,
        ">": actual > expected,
        "<": actual < expected,
    }[operator]
