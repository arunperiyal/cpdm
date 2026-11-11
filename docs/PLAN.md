# CPDM improvement plan

This is a staged roadmap for turning CPDM from a useful single-session data
cleaning workspace into a reproducible survey-data preparation and analysis
platform. The first stages strengthen the current application without
discarding its simple Flask/pandas workflow. Later stages add reusable
measurement and dyadic-analysis primitives informed by
`tmp/APIM_Analysis`.

## Guiding principles

- Keep the core layer independent of Flask, as it is today.
- Make every transformation inspectable, reversible where practical, and
  exportable as metadata.
- Prefer declarative metadata over instrument-specific code.
- Keep statistical analysis separate from file cleaning and presentation.
- Treat the existing R project as a source of domain requirements and
  validation examples, not as code to port wholesale.
- Preserve the current one-process behavior until durable session storage and
  concurrency semantics are designed explicitly.

## Stage 1 — Stabilise the current foundation

**Goal:** make the existing cleaning, grouping, scoring, and export workflow
safe to extend.

- [x] Define and document the data contracts for `Dataset`, groups, scales,
      cleaning recipes, API responses, and exported definition files.
- [x] Add focused unit tests around missing values, column contracts, rename
      propagation, scoring state, saved definitions, and row changes.
- [x] Add a validation layer for uploaded tables and recipes, with actionable
      warnings before mutation.
- [x] Introduce structured operation results containing change status, warnings,
      and provenance rather than returning only counts.
- [x] Add a small service boundary around file I/O and session state so future
      background jobs or persistence do not require route-by-route rewrites.

- [x] **Exit criteria:** current end-to-end tests still pass, transformations
      have deterministic error behavior, and a saved cleaning/scoring
      definition can be validated before it is applied.

## Stage 2 — Build a metadata-driven measurement core

**Goal:** represent instruments, dimensions, items, response ranges, and
keying as reusable first-class objects.

Add a core package (names are provisional):

- [x] `InstrumentDefinition`: instrument name, version, dimensions, item
  membership, response scale, and scoring policy.
- [x] `ItemDefinition`: source column, item number, label, minimum/maximum,
  missing-value rules, and direct/reverse keying.
- [x] `DimensionDefinition`: ordered items, display label, total/subscale flag,
  and aggregation policy.
- [x] `ScaleMap`: import/export the R-style metadata table and validate that every
  declared item exists exactly once.
- [x] `ScoringEngine`: apply reverse coding, map responses, calculate composites,
  and emit a scoring report without embedding instrument names in code.
- [x] `ReliabilityReport`: hold alpha/omega (where supported), item counts,
  missingness, and warnings about unsuitable inputs.

The design should directly cover the patterns in
`tmp/APIM_Analysis/R/scoring.R`,
`tmp/APIM_Analysis/R/reliability.R`, and
`tmp/APIM_Analysis/metadata/scale_map.csv`:

- reverse coding uses item-specific bounds;
- dimensions and totals are declared by metadata;
- composites have explicit aggregation and missing-data policies;
- positive and negative constructs may be separate composites rather than an
  automatically reversed total.

Use JSON/CSV import and export so a scale map can be reviewed or edited
outside the application. Keep the current interactive Groups and Scales UI as
one way to create these definitions.

- [x] **Exit criteria:** the bundled sample workflow can be represented by
      metadata, scored deterministically, and compared against a checked-in
      fixture/report.

## Stage 3 — Add reproducible preparation pipelines

**Goal:** make a complete preparation run repeatable, inspectable, and
portable across waves of a study.

- [x] Introduce a `PreparationPipeline` with explicit steps such as load,
   validate, clean headers, clean values, apply scale definitions, score,
   compute derived columns, and export.
- [x] Give every step an input/output schema, configuration, timestamp, and
   summary of changes. Extend the existing ordered cleaning recipe rather than
   creating a second incompatible history format.
- [x] Add pipeline manifests containing source-file fingerprints, definition
   versions, software version, warnings, and output artifacts.
- [x] Support dry-run/preview mode and fail before mutation when required
   columns, instruments, or response values are missing.
- [x] Add a command-line entry point for running a saved pipeline without opening
   the browser.

This stage should mirror the numbered R preparation flow in
`tmp/APIM_Analysis/run_00_data_prep.R` and
`tmp/APIM_Analysis/R/pipeline_step0.R`, while retaining Python-native
dataframes and reports.

- [x] **Exit criteria:** a second survey wave can be processed using the same
      definitions, with a clear report of applied, skipped, and changed
      operations.

## Stage 4 — Support participant and dyad data models

**Goal:** make couple/partner data a supported data shape rather than an
analysis-specific convention.

Add reusable abstractions:

- [ ] `ParticipantKey` and `DyadKey` for stable participant/couple identifiers.
- [ ] `RoleDefinition` for partner roles such as husband/wife or actor/partner.
- [ ] `DyadTable` for validating one-row-per-participant and one-row-per-dyad
  assumptions.
- [ ] `ReshapePlan` for long-to-wide and wide-to-long transformations with
  explicit name templates and collision checks.
- [ ] `DerivedVariable` for actor, partner, difference, mean, and interaction
  variables.

These should capture the intent of
`tmp/APIM_Analysis/R/id_utils.R` and
`tmp/APIM_Analysis/R/reshape.R`:

- reject duplicate role records;
- report incomplete dyads;
- preserve identifiers and metadata;
- make generated names predictable;
- never silently pair participants by row order.

Provide diagnostics for missing partners, duplicate couple IDs, inconsistent
role labels, and accidental leakage of identifiers into analysis columns.

- [ ] **Exit criteria:** a validated dyad table can be produced from a scored
      participant table and round-tripped without losing identifiers or
      measures.

## Stage 5 — Create an analysis and result abstraction

**Goal:** provide a stable base for future APIM, mediation, moderation, and
other statistical workflows without coupling them to the web UI.

Define generic interfaces:

- [ ] `AnalysisSpec`: named predictors, mediators, outcomes, moderators,
  covariates, roles, estimator, and missing-data policy.
- [ ] `AnalysisRunner`: validates inputs, builds a model design, executes one
  analysis, and returns typed results.
- [ ] `EffectEstimate`: estimate, standard error, confidence interval, p-value
  (when applicable), path label, role, and diagnostics.
- [ ] `AnalysisResult`: model metadata, estimates, warnings, convergence status,
  and reproducible input fingerprint.
- [ ] `ResultTable`/`ReportWriter`: stable CSV/XLSX/JSON output with human-readable
  labels and machine-readable identifiers.

Use the conventions in the R analysis code as domain requirements:

- actor versus partner paths must be explicit;
- indirect effects need bootstrap confidence intervals rather than being
  reduced to a bare p-value;
- moderation results should include the interaction and conditional indirect
  effect/index together;
- exploratory analyses must be labelled as such;
- convergence and suspicious estimates must be surfaced, not hidden.

Relevant references include
`tmp/APIM_Analysis/R/apim_models.R`,
`tmp/APIM_Analysis/R/apimem_models.R`,
`tmp/APIM_Analysis/R/moderated_mediation_models.R`,
`tmp/APIM_Analysis/R/multigroup_models.R`, and
`tmp/APIM_Analysis/R/model_utils.R`.

Do not implement every APIMeM model in the first pass. Start with a
well-tested design-matrix/result contract and one small analysis adapter.

- [ ] **Exit criteria:** an analysis can be run from a saved specification,
      produces stable machine-readable results and diagnostics, and is
      testable without HTTP.

## Stage 6 — Reporting, visualization, and research reproducibility

**Goal:** make outputs suitable for review and repeated research use.

- [ ] Add report bundles containing definitions, preparation manifests, model
   specifications, result tables, warnings, and figures.
- [ ] Add reusable table formatting and figure-data exports instead of embedding
   formatting in individual analyses.
- [ ] Add a figure specification layer for forest plots, path diagrams, and
   descriptive summaries.
- [ ] Add comparison tools for two waves, two groups, or two pipeline runs.
- [ ] Add provenance links from every reported result back to source columns,
   scale items, transformation steps, and model specification.

The reporting design should reflect
`tmp/APIM_Analysis/R/excel_export.R`,
`tmp/APIM_Analysis/R/figures_common.R`, and the numbered figure scripts, but
should keep raw results separate from presentation formatting.

- [ ] **Exit criteria:** a complete run produces a self-contained report bundle
      that another person can inspect and regenerate from the recorded inputs.

## Stage 7 — Product hardening and operational improvements

**Goal:** make the application dependable for larger datasets and shared
workflows.

- [ ] Replace process-global state with explicit session storage when multi-user
  access is required; retain the single-worker safeguard until then.
- [ ] Add upload size limits, timeout/error boundaries, and safe temporary-file
  handling.
- [ ] Add background execution and progress reporting for expensive scoring,
  reliability, bootstrap, and report jobs.
- [ ] Add schema/version migrations for saved recipes, scale maps, pipelines, and
  results.
- [ ] Add CI for tests, formatting/type checks, browser/API smoke tests, and
  documentation consistency.
- [ ] Add authentication and authorization before recommending non-loopback
  deployment.

## Suggested implementation order

Prioritise **Stages 1-3** before statistical features. They reduce the risk of
building analysis functionality on ambiguous or non-reproducible data
transformations. Implement **Stage 4** before APIM work, then implement
**Stage 5** incrementally with one analysis adapter and fixture-based
validation. Finish with **Stages 6-7** as the reporting and deployment needs
become clear.

## Decisions to make before implementation

- Should instrument metadata be stored as JSON, CSV, or both?
- Which missing-data and minimum-response rules should composites use?
- Which participant roles and dyad identifiers are canonical?
- Is statistical computation expected to remain Python-only, or should CPDM
  optionally call R for methods not yet available in Python?
- Which outputs are exploratory versus confirmatory, and how should that label
  be carried into reports?
- Is multi-user hosting in scope, or should CPDM remain a local single-user
  workspace?
