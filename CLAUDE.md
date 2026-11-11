# CPDM contributor guidance

## Project overview

CPDM (Comprehensive Package for Data Management) is a local Flask workspace for
cleaning survey data, grouping columns into scales, scoring items, computing
row-level statistics, and exporting CSV/XLSX files.

- Application code lives in `src/cpdm/`.
- `app.py` is the development launcher and adds `src/` to `PYTHONPATH`.
- HTTP/API behavior is implemented in `src/cpdm/web/`.
- Data and domain logic is in `src/cpdm/core/`.
- Browser assets and templates are in `src/cpdm/static/` and `src/cpdm/templates/`.
- User-facing documentation is in `docs/`.
- Bundled fixtures and sample files are in `samples/`.
- End-to-end tests are in `tests/`.

The active dataset and session state live in one process. Do not introduce
multiple workers or designs that assume a shared persistent store unless the
architecture is deliberately changed throughout the application.

## Setup and common commands

```bash
python -m pip install -r requirements.txt
python app.py
python -m pytest tests
```

The service wrapper is `cpdmctl.sh`; use `./cpdmctl.sh start`, `status`, `stop`,
or `logs` for local service operation. The default development URL is
`http://127.0.0.1:5000/`.

Useful environment variables include `CPDM_HOST`, `CPDM_PORT`, `CPDM_DEBUG`,
`CPDM_NO_BROWSER`, `CPDM_DOCS_DIR`, and `CPDM_SAMPLES_DIR`.

## Development conventions

- Keep changes focused and preserve existing API response shapes and UI behavior.
- Reuse helpers and state-management patterns in `src/cpdm/core/` rather than
  duplicating data transformations in route handlers.
- Validate user input at API boundaries and return the repository's established
  JSON error format; do not silently swallow failures.
- Keep dataset operations compatible with pandas and preserve column order and
  recorded cleaning-recipe behavior.
- Keep analysis contracts method-agnostic: APIM and dyadic workflows are
  supported examples, not assumptions that every dataset has partners, roles,
  or a single cross-sectional wave.
- Add focused regression coverage in `tests/test_workflow.py` for new or fixed
  behavior.
- Use the existing CSS theme variables for UI colors; do not hard-code palette
  colors in stylesheets.
- Keep the single-worker deployment requirement documented and intact.

## Repository hygiene

Do not commit generated caches, local settings, user data, or exported files.
The repository ignores `__pycache__`, `.pytest_cache`, `.claude/settings.local.json`,
`data/`, `tmp/`, and generated `processed_*`/`cleaning_rules.json` files.

## Phase and pull-request workflow

Work from `docs/PLAN.md` one phase at a time.

- Do not create or use Git worktrees; perform phase work in the current checkout
  and switch branches directly.
- Create a dedicated branch for every phase, using a descriptive name such as
  `phase-1-foundation` or `phase-2-measurement`.
- Create one focused commit for every task checkbox completed in that phase.
- Do not add co-author trailers to commit messages.
- Write commit messages with at least five lines: a concise subject followed by
  the purpose, important implementation details, validation, and scope notes.
- Keep each phase branch based on the completed branch immediately below it.
- Push the phase branch and open a pull request after all of its task commits
  pass the relevant tests.
- Do not merge a phase pull request unless explicitly requested.
- Update the corresponding checkboxes in `docs/PLAN.md` only when the task and
  its validation are complete.
