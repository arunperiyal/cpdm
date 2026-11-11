# CPDM Extensions and Portable Projects

`plugins.py` defines a versioned local plugin boundary. A plugin has metadata
for its kind, implementation version, API version, and description. Supported
kinds are transformations, instruments, estimators, and report components.
Registration is explicit and duplicate names are rejected.

`PluginManifest` adds an explicit trust decision and dependency requirements.
`PluginRegistry.register_manifest` validates the manifest, plugin API version,
and installed dependency versions before registering an implementation. This
keeps discovery portable without importing or executing untrusted code.

`project.py` defines:

- `ProjectConfig` for portable project settings and document references;
- `PortableBundle` for safe zip bundles containing project definitions;
- `AuditLog` for append-only collaboration events;
- `RevisionedDocument` for optimistic concurrency checks.

Bundles contain definitions and settings, not implicit process-global dataset
state. Optional collaboration must add authentication scope and durable
storage before it is exposed as a multi-user service.

Project templates live under `docs/templates/`; supported persisted schemas
are recorded in `docs/architecture/SCHEMAS.md` and checked against the
canonical schema registry. Release validation is recorded in
`docs/RELEASE_CHECKLIST.md`.
