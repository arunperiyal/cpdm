# Next session handoff

## Current state

- Phase 1, Phase 2, Phase 3, and Phase 4 are implemented on dependent branches.
- Phase 4 is on `phase-4-dyads`; its PR and stack registration should be
  completed before starting new implementation work.
- The full test suite passes with 81 tests.
- Existing unrelated worktree edits remain intentionally uncommitted:
  `.gitignore` and `src/cpdm/core/groups.py`.

## Pull-request stack

The native stack is `#3`:

1. `#1` — `phase-1-foundation` → `main`
2. `#2` — `phase-2-measurement` → `phase-1-foundation`
3. `#4` — `phase-3-pipelines` → `phase-2-measurement`
4. Phase 4 — `phase-4-dyads` → `phase-3-pipelines` (create and append)

Do not merge or enable auto-merge unless explicitly requested.

## Next implementation target

Begin Phase 5 from the Phase 4 branch after its PR is pushed:

- Add `AnalysisSpec` for predictors, mediators, outcomes, moderators,
  covariates, roles, estimators, and missing-data policy.
- Add typed `EffectEstimate` and `AnalysisResult` objects with diagnostics,
  warnings, convergence status, and input fingerprints.
- Add an `AnalysisRunner` boundary and one small APIM-compatible adapter.
- Add stable JSON/CSV/XLSX result serialization and focused tests.

Follow the repository rules in `CLAUDE.md`: use a phase branch, make one
focused five-line minimum commit per task, push the branch, and open a
dependent pull request after the phase is complete.
