# Implementation Plan: One answer for a Mission's human slug

**Branch**: `issue-6278-human-slug-handle-parity` | **Date**: 2026-11-01 | **Spec**: `kitty-specs/human-slug-handle-parity-01M6BV06/spec.md`
**Input**: Mission specification from `kitty-specs/human-slug-handle-parity-01M6BV06/spec.md`

## Summary

`implement --mission <human-slug>` refuses a Mission that `agent tasks status --mission
<human-slug>` resolves, because the identity resolver's "human slug" rung strips only a
leading `NNN-` prefix and never the trailing `-<mid8>` a Mission created today carries.
Fix: extend that one rung in `specify_cli/context/mission_resolver.py::_resolve_from_index`
to also fold the trailing mid8 — but only when it equals that Mission's own
`mission_id[:8]` — keeping `_resolve_or_raise`'s loud ambiguity refusal. Then pin the
whole handle matrix against both resolution paths so the two cannot drift again.

## Technical Context

**Language/Version**: Python 3.11 (`requires-python` in `pyproject.toml`), typed, mypy-checked
**Primary Dependencies**: stdlib only for the change; `mission_runtime` (`mid8_from_slug`, `placement_seam`), `specify_cli.lanes.branch_naming` (`strip_numeric_prefix`) already imported by the touched modules
**Storage**: filesystem — `kitty-specs/<composed-slug>/meta.json` per Mission
**Testing**: pytest; `tests/context/test_mission_resolver.py` (unit ladder), `tests/specify_cli/cli/commands/test_selector_resolution.py` (CLI + both paths)
**Target Platform**: CLI, Linux/macOS/Windows
**Project Type**: single Python package (`src/specify_cli/`)
**Performance Goals**: no change — one `kitty-specs/` walk per resolution call (NFR-001)
**Constraints**: fail closed on ambiguity; no precedence change for the other handle forms
**Scale/Scope**: one function body (~4 lines), one module docstring, two test files, one changelog entry

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | This plan |
| --- | --- |
| Single canonical authority | The fold goes into the one ladder (`_resolve_from_index`) shared by both adapters — no second resolution path, no second source of truth for "what is this Mission's human slug". |
| ATDD-First Discipline (C-011) / DIRECTIVE_034 | The defect gets a failing unit test and a failing CLI-level test **before** the fix, both through the pre-existing entry points (`resolve_mission`, `implement`). |
| DIRECTIVE_024 Locality of Change | The production edit is one comparison in one function. Tests are added to the two suites that already own this behaviour. |
| DIRECTIVE_041 (a test only where it guards real behaviour) | Every added test pins a handle form or the two-path parity; no scaffolding tests. |
| Pre-existing Failure Reporting Rule | Any red gate outside this diff is reported in the PR's `## Deferred` section, not masked. |
| `__all__` Declaration Convention (C-007) / dead-symbol gate | The helper stays module-private (`_human_slug_for_index_entry`); no new `__all__` member. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Run the two targeted suites plus the architectural gates the change can touch, not the full suite. |

No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/human-slug-handle-parity-01M6BV06/
├── plan.md              # This file
├── research.md          # Phase 0: discovery + plan-phase findings
├── spec.md              # The specification
├── decisions/           # Decision Moment ledger (DM-01M6BV0F…)
├── tasks.md             # Phase 2 (/spec-kitty.tasks)
└── traces/              # approach.md, design-decisions.md, tooling-friction.md
```

No `data-model.md`, `contracts/` or `quickstart.md`: the mission introduces no new
entity, no externally consumed contract and no runnable demo — the handle grammar it
touches is documented in the module docstring it already has, and that docstring is
updated in place.

### Source Code (repository root)

```
src/specify_cli/
├── context/mission_resolver.py        # the ladder: _resolve_from_index priority 4 (+ docstring)
├── cli/selector_resolution.py         # unchanged; documents the two paths in its docstrings
└── missions/_read_path_resolver.py    # unchanged; the other path's bare-modern fold

tests/
├── context/test_mission_resolver.py                        # ladder unit tests (add human-slug rows)
├── specify_cli/cli/commands/test_selector_resolution.py    # two-path parity matrix
└── specify_cli/cli/commands/agent/test_implement_*.py      # CLI-level: implement accepts the human slug
```

**Structure Decision**: existing single-package layout; no new modules, no package moves.

## Contract / Compatibility Notes

- `resolve_mission` is documented public surface. This widens the input it accepts; it
  removes no handle form and changes no return value shape (`ResolvedMission`).
- The CLI's `MISSION_NOT_FOUND` / `MISSION_AMBIGUOUS_SELECTOR` envelopes are unchanged:
  the new rung raises through `_resolve_or_raise`, which the CLI already renders.
- Ambiguity message text and candidate shape stay exactly as they are.

## Complexity Tracking

*(empty — no Charter Check violations)*

## Implementation Concern Map

### IC-01 — The identity resolver's human-slug rung

- **Purpose**: Make the shared ladder recognize `<human-slug>` for a `<human-slug>-<mid8>`
  Mission, without inventing a handle from a coincidental tail and without weakening the
  ambiguity refusal.
- **Relevant requirements**: FR-001, FR-002, FR-003, NFR-001, NFR-002, C-001, C-002
- **Affected surfaces**: `src/specify_cli/context/mission_resolver.py`
  (`_resolve_from_index`, module docstring priority list, `resolve_mission` docstring)
- **Sequencing/depends-on**: none
- **Risks**: the only real risk is over-stripping a tail that is not this Mission's mid8;
  the guard is `mid8` equality, and the negative fixture in FR-002's row proves it.

### IC-02 — The two-path parity guard

- **Purpose**: Pin the handle matrix (`human slug`, composed slug, mid8, full ULID,
  numeric prefix, unknown) so `resolve_mission_handle` and the read-path bare-modern fold
  answer identically, and so `implement` is covered by a CLI-level test rather than only
  by unit tests of the helper it calls.
- **Relevant requirements**: FR-004, FR-005, SC-002, SC-003, SC-004
- **Affected surfaces**: `tests/context/test_mission_resolver.py`,
  `tests/specify_cli/cli/commands/test_selector_resolution.py`, the existing implement
  command tests
- **Sequencing/depends-on**: IC-01 (the parity test is red for the human-slug row until
  the ladder folds it — that redness IS the red-first proof)
- **Risks**: the read-path fold's `MissionSelectorAmbiguous` and the ladder's
  `AmbiguousHandleError` are different types rendered by different wrappers; the parity
  test asserts on the rendered CLI outcome, not on the exception class.

## Phase 0 — Research

Extends `research.md` (discovery already recorded there). New findings for plan: the
`mid8` on a `ResolvedMission` is exactly `mission_id[:8]`, so the guard needs no new read;
`branch_naming._human_slug_for_mid8_branch` already implements the same rule privately and
stays the single definition for branch composition (the resolver's rung shares the rule,
not the symbol, because `branch_naming` imports upward and would create a cycle).

## Phase 1 — Design

The rung, as designed:

```
priority 4 (handle is not a numeric prefix):
  match m  where  human_slug(m) == handle
  human_slug(m) = strip_numeric_prefix(m.mission_slug), minus a trailing "-<m.mid8>"
                  when present
  > 1 match  -> AmbiguousHandleError (candidates = all matches)
  0 matches  -> fall through to priority 5
```

Worked examples:

| `meta.json` `mission_slug` | `mission_id[:8]` | human slug |
| --- | --- | --- |
| `smoke-test-01M6BTQX` | `01M6BTQX` | `smoke-test` |
| `smoke-test-01M6BTQX` | `01ZZZZZZ` | `smoke-test-01M6BTQX` (coincidental tail kept) |
| `083-foo-bar` | (any) | `foo-bar` (legacy: no mid8 tail) |
| `01M6BTQX-smoke` | `01M6BTQX` | `01M6BTQX-smoke` (tail is not at the end) |

## Gates

- `uv run pytest tests/context/test_mission_resolver.py tests/specify_cli/cli/commands/test_selector_resolution.py -q`
- the implement-command CLI test file(s) touched
- `uv run ruff check` + `uv run mypy` on the changed files
- architectural gates the change can touch: dead-symbols, terminology, docstring/`__all__`
  conventions
- `uv run python -m scripts.docs.check_docs_freshness --ci` only if a docs page changes
