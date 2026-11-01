# Tasks: One answer for a Mission's human slug

**Mission**: `human-slug-handle-parity-01M6BV06` · **Branch**: `issue-6278-human-slug-handle-parity` (planning base and merge target)
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Failing human-slug rows in `tests/context/test_mission_resolver.py` (resolves, coincidental tail does not, ambiguity refuses) | WP01 | |
| T002 | Fold the Mission's own trailing `-<mid8>` in `_resolve_from_index` priority 4; update the ladder docstrings | WP01 | |
| T003 | Prove the existing precedence rows (full ULID, mid8, exact directory, `NNN-` slug, numeric prefix, unknown) are unchanged | WP01 | |
| T004 | Failing CLI-level test: `implement` resolves `--mission <human-slug>` through `detect_mission_context` | WP02 | |
| T005 | Two-path parity matrix in `tests/specify_cli/cli/commands/test_selector_resolution.py` | WP02 | |
| T006 | `implement --mission` help text names the accepted handle forms | WP02 | [P] |
| T007 | `docs/changelog/CHANGELOG.md` `[Unreleased]` entry for (#6278) | WP02 | [P] |

## Phase 1 — The resolver

### WP01 — The identity resolver's human-slug rung

**Goal**: `resolve_mission("<human-slug>")` resolves a `<human-slug>-<mid8>` Mission, refuses two Missions sharing a human slug, and answers every other handle form exactly as before. **Priority**: P1. **Prompt**: [tasks/WP01-human-slug-ladder-rung.md](tasks/WP01-human-slug-ladder-rung.md)
**Independent test**: `uv run pytest tests/context/test_mission_resolver.py -q` — the new human-slug row is red before T002 and green after it.

T001 Failing human-slug rows in `tests/context/test_mission_resolver.py` (resolves, coincidental tail does not, ambiguity refuses) (WP01)
T002 Fold the Mission's own trailing `-<mid8>` in `_resolve_from_index` priority 4; update the ladder docstrings (WP01)
T003 Prove the existing precedence rows (full ULID, mid8, exact directory, `NNN-` slug, numeric prefix, unknown) are unchanged (WP01)

Dependencies: none. Risk: over-stripping a coincidental tail — T001's negative row is the control.

## Phase 2 — Parity and record

### WP02 — The two paths answer the same, and the operator can see why

**Goal**: `implement` resolves the human slug end to end, one test pins the handle matrix for both resolution paths, and the user-facing surfaces (help text, changelog) say what handles are accepted. **Priority**: P1. **Prompt**: [tasks/WP02-parity-guard-and-record.md](tasks/WP02-parity-guard-and-record.md)
**Independent test**: the parity matrix in `tests/specify_cli/cli/commands/test_selector_resolution.py` and the CLI-level implement test both pass, and the human-slug cell of the matrix is red without WP01.

T004 Failing CLI-level test: `implement` resolves `--mission <human-slug>` through `detect_mission_context` (WP02)
T005 Two-path parity matrix in `tests/specify_cli/cli/commands/test_selector_resolution.py` (WP02)
T006 `implement --mission` help text names the accepted handle forms (WP02)
T007 `docs/changelog/CHANGELOG.md` `[Unreleased]` entry for (#6278) (WP02)

Dependencies: WP01 (the human-slug rows are red until the ladder folds the mid8). Risk: the read-path fold raises `MissionSelectorAmbiguous` where the ladder raises `AmbiguousHandleError`; T005 asserts the rendered CLI outcome, not the exception class.

## Issue matrix

| Issue | Scope | Work packages | Verdict |
|-------|-------|---------------|---------|
| #6278 | The whole issue: `implement` and every other `resolve_mission` caller accept a Mission's human slug, with loud ambiguity. | WP01, WP02 | pending |
