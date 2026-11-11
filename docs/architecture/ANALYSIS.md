# CPDM Analysis Architecture

Analysis contracts are method-agnostic. APIM is one adapter, not the product
boundary.

## Generic analysis

`analysis.py` defines:

- `AnalysisSpec` for predictors, outcomes, mediators, moderators, covariates,
  roles, estimators, and missing-data policies;
- `AnalysisCapability`, `AnalysisAdapter`, and `AnalysisRegistry` for discoverable
  adapters with input requirements and method-specific validation;
- `AnalysisRunner` for validation and dispatch;
- `EffectEstimate` and `AnalysisResult` for stable typed outputs;
- `ReportWriter` for JSON, CSV, and XLSX result files.

Reusable summaries cover descriptive statistics, two-group comparisons,
repeated-measures summaries, and a transparent linear-regression adapter.
The registry also includes weighted regression, clustered regression,
longitudinal and repeated-measures regression, and seeded bootstrap indirect
effects. Weighted, clustered, and longitudinal adapters require explicit
weights, cluster, subject, and time columns respectively; bootstrap indirect
effects expose reproducible seeds, confidence intervals, and warnings for
degenerate resamples. Capability metadata is available through the analysis
API and can be preserved in portable project configurations.

All adapters return the same `AnalysisResult` contract with an input
fingerprint, serialized specification, diagnostics, warnings, and stable
effect estimates. Adapter-specific unsupported policies or missing required
columns fail with `ContractError` before model execution.

## Latent profiles

`profiles.py` separates indicator preparation from fitting:

- `IndicatorDefinition` validates measurement level, allowed values,
  transformations, standardisation, and missing-data policy.
- `ProfileAnalysisSpec` keeps indicators separate from identifiers, weights,
  covariates, and distal outcomes.
- `ProfileSolution`, `FitStatistic`, `ClassSelectionReport`, and
  `ProfileStabilityReport` hold backend-neutral results and review evidence.
- `MixtureAnalysisRunner` dispatches registered Python, R, or other backends.
- `ProfileResultWriter` exports assignments, probabilities, fit, parameters, and
  warnings without requiring HTTP state.

Class labels have no substantive meaning until an explicit alignment is
recorded. Tiny classes, missingness, convergence, boundary estimates, and
backend limitations belong in diagnostics and provenance.

## Provenance and compatibility

Results record input fingerprints, seeds, estimator/backend metadata, warnings,
and serialized specifications. Compatibility fixtures protect saved
definitions and result schemas as adapters evolve.

Future adapters must preserve the stable result shape and declare unsupported
roles, measurement levels, missing-data policies, and weighting behavior.
