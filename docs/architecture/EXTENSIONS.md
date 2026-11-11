# CPDM Extensions and Portable Projects

`plugins.py` defines a versioned local plugin boundary. A plugin has metadata
for its kind, implementation version, API version, and description. Supported
kinds are transformations, instruments, estimators, and report components.
Registration is explicit and duplicate names are rejected.

`project.py` defines:

- `ProjectConfig` for portable project settings and document references;
- `PortableBundle` for safe zip bundles containing project definitions;
- `AuditLog` for append-only collaboration events;
- `RevisionedDocument` for optimistic concurrency checks.

Bundles contain definitions and settings, not implicit process-global dataset
state. Optional collaboration must add authentication scope and durable
storage before it is exposed as a multi-user service.
