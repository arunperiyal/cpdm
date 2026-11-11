"""Versioned extension points for transformations, estimators, and reports."""

from dataclasses import dataclass

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
