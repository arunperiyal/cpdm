# CPDM Core Architecture

CPDM keeps domain logic independent of Flask. Core modules operate on pandas
dataframes and typed metadata so the same contracts can be used by the web
application, command-line pipelines, tests, and future batch runners.

## Data preparation

- `Dataset` owns the current dataframe and recorded cleaning state.
- `contracts.py` validates dataframes, recipes, and user-facing definitions.
- `services.py` coordinates dataset I/O without putting orchestration in routes.
- `pipeline.py` provides declarative preparation steps, manifests, fingerprints,
  dry runs, and reproducible replay.
- `operations.py` provides upload policies, safe temporary paths, versioned
  documents, job state, bounded execution, and timeout boundaries.

Preparation preserves column order and records transformations rather than
silently mutating data. Saved definitions must remain inspectable JSON/CSV
artifacts with explicit versions.

## Measurement

`measurement.py` models instruments, dimensions, items, scale maps, scoring,
composites, and reliability reports. Metadata drives reverse coding and
aggregation; instrument names are not embedded in scoring code.

## Observation and variable contracts

- `dyads.py` contains participant/dyad compatibility models plus the
  method-agnostic `ObservationKey` and `ObservationKeySpec`.
- `variables.py` records variable roles, source columns, derived-from links,
  and sensitivity classification.
- Identifiers, grouping fields, weights, time points, and analysis variables
  remain explicit and are never inferred from row position.

Dyadic workflows are supported examples. The core contracts also support
longitudinal, clustered, experimental, and operational data.

## Results and reporting

`results.py` provides stable operation results. `reporting.py` writes portable
bundles, figure data, comparison tables, and privacy-filtered exports.
Raw results remain separate from presentation formatting.

## State and deployment boundary

The current application intentionally remains single-worker and
single-dataset. `state.py` is therefore process-global. Durable session
storage, concurrent edits, and multi-user authorization require a coordinated
architecture change and must not be introduced through isolated route patches.
