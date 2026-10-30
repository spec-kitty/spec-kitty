# Research — accept-path-conventions-name-overrides-01M66F7N

## Decisions

1. **The single seam is `PathValidationResult.format_errors()`** (`src/specify_cli/validators/paths.py`). Every strict-failure rendering path flows through it: `PathValidationError.__init__` (strict mode) and `summary_core.evaluate_path_conventions` (line 278, the `path_violations` entry `accept --diagnose` prints, wrapped with `_with_notice`). No second copy of remediation text is needed or wanted (C-003).
2. **Reproduction confirmed on `main` @ `512567ee`.** A Go-style repo (only `internal/`, mission declares `workspace: src/`, `tests: tests/`, `documentation: docs/`) fails strict validation and the rendered text names neither `project.path_conventions` nor the mission-override route. Not superseded: `git log -S` shows no change to `format_errors` since #3730's wording; the #3016 changelog entry and ADR `docs/adr/3.x/2026-08-28-1-project-path-convention-override-precedes-doctrine.md` deliberately kept the two-lever text ("Deliberate non-reversal of #3783"), with the discoverability cost named in its Negative consequences — this mission pays down exactly that cost, additively.
3. **Which keys are remappable is knowable at validation time.** `config/path_conventions.py` exports `ARTIFACT_ROUTED_KEYS = {"deliverables"}`; a missing key NOT in that set can be remapped by `project.path_conventions` and belongs in the copy-pasteable example. `deliverables` must not be suggested (C-002; the #5298 `contracts: none` waiver governs it and already prints its own guidance).
4. **The mission-type slug for the override route comes from the resolved mission path.** `Mission.path` is `<...>/missions/<type>` (e.g. `.kittify/missions/software-dev`); `mission.path.name` is already used as the mission-type key elsewhere in `mission.py` (line 381). For hand-built stubs or neutral org missions without a meaningful path, render a generic `<mission-type>` placeholder rather than guessing.
5. **Guidance blocks render only when their inputs are non-empty** (graceful degradation for hand-built results in existing unit tests, which construct `PathValidationResult` directly).
6. **#3783 contract preserved**: `--lenient` stays named and before `mkdir -p`; the "are required by the active mission" phrase stays absent. The existing test `test_format_errors_names_lenient_before_mkdir_and_drops_unconditional_claim` must pass unmodified.
7. **Docs + changelog are in scope** (user-facing text change): `docs/guides/how-to/missions/accept-and-merge.md` names both routes where the `contracts: none` bullet says other conventions "stay in force"; `[Unreleased]` entry in `docs/changelog/CHANGELOG.md`.

## Evidence

- Issue #6633 body: reproduction, root-cause reading of `validators/paths.py:81-107` on `1a0c8b467`, and the verified workaround matrix (remap-only leaves `docs/` missing; remap + mission override leaves nothing missing).
- #3016 (closed): added `project.path_conventions` (remap-only, fail-closed section shape, `deliverables` excluded).
- #4088 (closed): the `.kittify/overrides/missions/<type>/` project override tier.
- #5298 (closed): the `contracts: none` meta.json waiver — governs `contracts/` only; its how-to bullet is the "stay in force" sentence to extend.
- #3730/#3783 (closed): the two-lever remediation text and its ordering contract.
- #2744 (open): layout auto-detection — explicitly out of scope here (C-004).

## Open questions

- None blocking. The issue's heavier suggestion (a per-key opt-out like the `contracts: none` waiver) is explicitly left to the maintainers as an ADR-revising decision; this mission implements only the named-text fix.
