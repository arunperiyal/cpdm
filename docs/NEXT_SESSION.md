# Project handoff

## Current state

- Phases 1–7 are merged into `main` through native stack `#3`.
- The full local test suite passes with 89 tests.
- Phase 7 contains operational foundations, but deployment-specific work remains
  intentionally open in `docs/PLAN.md`.
- Existing unrelated worktree edits remain intentionally uncommitted:
  `.gitignore` and `src/cpdm/core/groups.py`.

## Landed pull-request stack

Native stack `#3` landed in order:

1. `#1` — `phase-1-foundation` → `main`
2. `#2` — `phase-2-measurement` → `phase-1-foundation`
3. `#4` — `phase-3-pipelines` → `phase-2-measurement`
4. `#5` — `phase-4-dyads` → `phase-3-pipelines`
5. `#6` — `phase-5-analysis` → `phase-4-dyads`
6. `#7` — `phase-6-reporting` → `phase-5-analysis`
7. `#8` — `phase-7-hardening` → `phase-6-reporting`

## Next implementation direction

Continue from `main` with the general-purpose items in Stages 8–9:

- add adapter capability metadata and non-dyadic descriptive/regression methods;
- support time points, clustered observations, and explicit analysis roles;
- improve privacy-aware bundles and portable project configuration;
- design collaboration only after session, authorization, and audit semantics
  are explicit.

APIM remains a supported compatibility target, not the scope of the core
architecture.
