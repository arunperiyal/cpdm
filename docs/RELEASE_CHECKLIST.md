# CPDM Release Checklist

- Run the full test suite, bytecode compilation, and documentation checks.
- Verify every persisted document kind has a current schema and migration
  fixture.
- Review plugin manifests, API versions, dependency ranges, and explicit trust
  decisions.
- Review privacy classifications, export previews, retention rules, and audit
  storage paths.
- Confirm portable bundles contain definitions only and no credentials or user
  data.
- Record the release version, validation commands, and supported backend
  diagnostics.
