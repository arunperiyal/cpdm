# CPDM next-level roadmap

Stages 1-10 are implemented and documented in
[`docs/architecture/`](architecture/). This roadmap starts with the work that
must follow those foundations. Each stage should use a dedicated branch,
focused commits, regression tests, and an updated architecture document.

## Stage 11 — Durable sessions and persistence

**Goal:** move beyond one process-global dataset without breaking local-first
usage.

- [x] Define a session/document storage contract with explicit ownership,
      lifecycle, locking, and cleanup rules.
- [x] Add a durable local session store with migration-safe metadata and
      configurable storage roots.
- [x] Refactor web routes and services to receive a session context rather than
      importing process-global state.
- [x] Preserve a single-worker local mode as the default and add isolation tests
      for two simultaneous sessions.
- [x] Document backup, recovery, retention, and stale-session behavior.

- [x] **Exit criteria:** two sessions can be created, loaded, modified, and
      exported without sharing data or definitions.

## Stage 12 — Complete operational execution and migrations

**Goal:** make expensive and persisted operations reliable under failure.

- [x] Define cancellation and cooperative timeout contracts for core jobs.
- [x] Connect scoring, reliability, bootstrap, and report jobs to
      `JobExecutor` with serializable inputs and progress callbacks.
- [x] Define canonical schemas for recipes, scale maps, pipelines, analysis
      results, and profile results.
- [x] Register migrations for every persisted document type and test old
      fixtures against current loaders.
- [x] Add supported syntax, serialization, and documentation-consistency
      tooling to CI.

- [x] **Exit criteria:** interrupted jobs fail visibly, resume/retry rules are
      documented, and every saved document has a tested migration path.

## Stage 13 — Expand the analysis backend ecosystem

**Goal:** add useful methods without weakening the stable adapter contract.

- [x] Add weighted and clustered regression adapters with explicit observation
      and weight requirements.
- [x] Add repeated-measures and longitudinal model adapters with time and
      subject validation.
- [x] Add bootstrap and indirect-effect adapters with reproducible seeds and
      confidence intervals.
- [x] Add adapter capability discovery to the API and portable project bundles.
- [x] Add backend conformance tests covering errors, warnings, provenance, and
      result serialization.

**Exit criteria:** at least two non-dyadic and one dyadic analysis families
run through the same registry and result writer. **Complete:** the registry
now covers dyadic APIM, regression families, repeated measures/longitudinal
models, and bootstrap indirect effects through one result contract.

## Stage 14 — Production latent-profile backends

**Goal:** turn the profile foundation into reproducible statistical workflows.

- [x] Add a documented Python mixture-model adapter.
- [x] Add an optional R/backend adapter boundary with dependency diagnostics.
- [x] Implement class-count comparison helpers combining fit, stability, and
      recorded substantive review.
- [x] Add diagnostics for singular covariance, boundary estimates, local
      optima, excessive missingness, and non-convergence from real backends.
- [x] Add reproducibility fixtures for repeated starts, label alignment, and
      profile result bundles.

**Exit criteria:** a profile analysis can be run end to end from a saved
specification with a declared backend and reproducible diagnostics.
**Complete:** the Python Gaussian-mixture backend, explicit R boundary,
class-count review helper, backend diagnostics, and reproducibility tests are
implemented through the existing profile runner and result writer.

## Stage 15 — Privacy, collaboration, and governance

**Goal:** support controlled sharing without weakening local safety.

- [x] Add field-level privacy classifications and configurable export policies
      for identifiers, free text, weights, and intermediate artifacts.
- [x] Add scoped authentication and authorization for sessions, projects,
      bundles, and audit events.
- [x] Add durable audit storage and conflict resolution for collaborative edits.
- [x] Add redaction previews and retention/deletion operations for portable
      bundles.
- [x] Threat-model non-loopback deployment and document secure defaults.

**Exit criteria:** a reviewed collaboration workflow has authenticated actors,
auditable changes, conflict behavior, and tested privacy-preserving exports.
**Complete:** field-level export controls, scoped authorization, durable audit
events, explicit conflict resolution, bundle redaction/retention operations,
and secure-default boundaries are implemented and covered by tests.

## Stage 16 — Extension quality and user-facing products

**Goal:** make extensions discoverable, maintainable, and useful to teams.

- [ ] Add plugin discovery from signed or explicitly trusted project manifests.
- [ ] Add compatibility checks for plugin API versions and dependency ranges.
- [ ] Add project templates and examples for surveys, experiments, repeated
      measures, operational data, and dyadic studies.
- [ ] Add generated API/core architecture documentation from supported schemas.
- [ ] Add release checklists for migrations, fixtures, privacy, and reproducible
      report bundles.

**Exit criteria:** a new trusted adapter can be installed, validated, documented,
and used in a portable project without route-specific code changes.

## Guiding decisions

- Keep core contracts independent of Flask and preserve method-agnostic
  analysis interfaces.
- Treat APIM and latent profiles as supported examples, not organizing
  assumptions.
- Do not enable multi-user or non-loopback deployment without durable sessions,
  scoped authorization, auditability, and concurrency semantics.
- Prefer explicit provenance and compatibility fixtures over implicit defaults.
