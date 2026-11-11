# CPDM Operations Architecture

## Current safeguards

- Uploads are restricted by extension and byte size before readers run.
- Flask request-size failures and operation timeouts return explicit JSON errors.
- `SafeTemporaryDirectory` prevents path escape.
- `JobExecutor` provides in-process queued/running/completed/failed state and
  progress reporting.
- Non-loopback launcher bindings require a bearer token.
- `VersionedDocument` supplies explicit schema validation and migration hooks.
- `JobSpec` requires JSON-serializable inputs, while `CancellationToken` and
  `JobCancelled` define cooperative cancellation for scoring, reliability,
  bootstrap, and report adapters.
- `governance.py` defines field-level export classifications, scoped actor
  authorization, durable JSONL audit events, and explicit revision-conflict
  resolution.
- Portable bundles support previewing excluded artifacts, writing redacted
  copies, and explicit age-based deletion; these operations never delete
  directories implicitly.
- CI runs the test suite, bytecode compilation, and API smoke coverage.

## Deferred work

The following are intentionally not treated as complete:

1. Long-running operations need a cancellation contract before hard timeouts can
   safely stop workers.
2. Scoring, reliability, bootstrap, and report operations need serializable job
   inputs and progress callbacks before using `JobExecutor`.
3. Recipes, scale maps, pipelines, and results need canonical persisted schemas
   before one migration registry can govern them all.
4. Formatting, type checking, and documentation validation need supported tools
   added to the project dependencies.
5. Session/project/bundle/audit authorization is exposed as a core contract;
   route-level policy wiring remains opt-in until deployment identities and
   persistent actor storage are selected. The local session context remains
   opt-in and the process-global mode remains the default.

These items are the first candidates in the next roadmap rather than hidden
assumptions in the current implementation.
