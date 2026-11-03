# Implementation Plan: Subtask completion recipes name their work package

**Branch**: `issue-7108-subtask-recipe-wp-scoping` | **Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/subtask-recipe-wp-scoping-01M6G9TW/spec.md`

## Summary

Subtask ids are mission-scoped, so a mission's WPs routinely share `T001..T00n`.
`mark-status` already handles that: `--wp` selects the owner, and an unscoped id
with several owners is refused (never mis-attributed). But every surface that
*prints a subtask-completion recipe* still prints it **unscoped**, so on the
normal case the printed command is refused by the very command it was printed
for. Concretely, on `main` today:

```
Cannot move WP02 to for_review - unchecked subtasks:
  - [ ] T001
  - [ ] T002

Mark these complete first:
  spec-kitty agent tasks mark-status T001 --status done      <-- refused:
  spec-kitty agent tasks mark-status T002 --status done          "T001 is a
                                                                  subtask of
                                                                  WP01, WP02"
```

The operator's only way past the gate is `--force` — the workaround issue #7108
reports, and the mechanism by which the mis-attribution stays hidden.

The fix is one rendered shape, owned in one new module, used by all four
emitter sites:

```
spec-kitty agent tasks mark-status T001 T002 --wp WP02 --status done --mission <slug>[ --owned-checkout <root>]
```

Two facts make the shape safe: the WP being moved is `MoveTaskRequest.task_id`
itself (so the refusal already knows it), and every workflow/prompt site already
has the `WPxx` id in scope for the surrounding `move-task` line.

## Technical Context

**Language/Version**: Python 3.12 (project floor `>=3.11` per `pyproject.toml`)
**Primary Dependencies**: typer (CLI surface, unchanged); no new dependency
**Storage**: N/A — the change renders text; it reads no file and writes no state
**Testing**: pytest. Fast in-process tests for the rendered recipe
(`tasks_transition_core._guard_subtasks`), the prompt builder
(`runtime.next.prompt_builder._completion_lines`) and the workflow executor
sites; one behavioural test that executes the emitted command string through the
real `mark-status` entry point on a two-WP, shared-id fixture
**Target Platform**: CLI on Linux/macOS developer hosts and CI
**Project Type**: single project (Python package `specify_cli` + internal `runtime` package)
**Performance Goals**: NFR-001 — the refusal path stays pure: zero added I/O, zero added latency beyond string formatting (no file read, no event read, no post-processing hook)
**Constraints**: `runtime` may not import `specify_cli.cli` (`TestRuntimeBoundary` in `tests/architectural/test_layer_rules.py`), so the shared helper lives under `specify_cli.core`, which is already in the `runtime` → `specify_cli` ledger; the byte-frozen `agent tasks --help` fixtures are **not** touched
**Scale/Scope**: one new ~40-line module, four emitter call sites in three modules, three test files plus one new behavioural test; no data-model, event-schema or frontmatter change

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority | The recipe text gets exactly one home (`core/subtask_recipe.py`); the four emitters call it instead of hand-formatting. `mark-status`'s `_resolve_task_owners` stays the sole owner-resolution authority — this mission adds no second resolver and relaxes no refusal. |
| Architectural alignment / module seams | `core/subtask_recipe.py` is a pure, I/O-free module in the shared `core` layer, which both `runtime` and `specify_cli.cli` are permitted to import. No `runtime` → `specify_cli.cli` edge is created (the ledger forbids it). `tasks_transition_core` stays a pure decision core — the helper is pure text, so no I/O enters the core. |
| ATDD-first | Red first: the assertion on the emitted recipe (`--wp WP02`) fails on unmodified `src`, and the behavioural test that runs the emitted string through `mark-status` fails with the current refusal text before the helper exists. |
| Terminology canon | Uses the existing "work package / subtask roster / completion" vocabulary; no new domain term is coined. |
| Standing order 2 (campsite) | The three `workflow_executor` sites currently repeat the same f-string three times; extracting one helper removes that duplication rather than adding a fourth. |
| Standing order 5 (canonical sources / no shrink-only allowlist) | No new exclusion in any gate; no allowlist entry added; no test skipped or xfailed. |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | Validation = the targeted fast suites named below plus the affected architectural gates. CI owns the full matrix. |
| DIRECTIVE_024 locality / DIRECTIVE_025 boy-scout | Edits stay at the four emitter sites and in one new leaf module. No unrelated refactor of `_guard_subtasks`, the mark-status phases or the prompt builder. |
| DIRECTIVE_041 (test only real behaviour) | No test for an unreachable branch: every call site already guards `if subtask_ids`, so the helper does not add an empty-input error path with a synthetic test. |

No violations; `Complexity Tracking` stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/subtask-recipe-wp-scoping-01M6G9TW/
├── plan.md              # This file
├── spec.md              # Mission specification
├── tasks.md             # Work-package index (`/spec-kitty.tasks` output)
└── tasks/               # One file per work package
    ├── WP01-*.md
    └── WP02-*.md
```

### Source Code (repository root)

```
src/
├── specify_cli/
│   ├── core/
│   │   └── subtask_recipe.py            # NEW — the one home for the recipe text
│   └── cli/commands/agent/
│       ├── tasks_transition_core.py     # _guard_subtasks: refusal recipe
│       └── workflow_executor.py         # three implement runbook recipes
└── runtime/next/
    └── prompt_builder.py                # _completion_lines: WHEN DONE recipe

tests/
├── specify_cli/cli/commands/agent/
│   └── test_move_task_unchecked_recipe_scoped.py   # NEW — refusal + behavioural proof
├── specify_cli/core/
│   └── test_subtask_recipe.py                      # NEW — one shape, all arms
├── next/
│   └── test_prompt_builder_review_base.py          # updated completion-line assertion
└── integration/
    └── test_prompt_builder_owned_arms.py           # updated owned-arm assertion
```

**Structure Decision**: single project; the change touches the shared `core`
leaf, the two CLI emitters and the runtime prompt builder, and adds tests next
to each existing surface.

## Complexity Tracking

*No charter violations, so this table stays empty.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Concern Map

### IC-01 — The recipe's single home

- **Purpose**: Render the subtask-completion command once, so the four emitters cannot drift and the `--wp` scoping cannot be forgotten at a new site.
- **Relevant requirements**: FR-001, FR-003, FR-004, FR-005, NFR-002
- **Affected surfaces**: `src/specify_cli/core/subtask_recipe.py` (new); mirrored by `tests/specify_cli/core/test_subtask_recipe.py`
- **Sequencing/depends-on**: none — this is the first piece
- **Risks**: the helper must keep the *existing* option order (`--status`, then `--mission`, then `--owned-checkout`) so the owned-arm assertions and the parsed command both stay stable; `--wp` is inserted before `--status`. It must accept `mission_slug=None` and simply omit `--mission` (a `MoveTaskRequest` built directly in tests carries `None`), never print `--mission None`.

### IC-02 — The refusal that ends in a dead end

- **Purpose**: Make `move-task`'s unchecked-subtasks refusal print the scoped recipe for the WP being moved, so following its advice actually clears the gate.
- **Relevant requirements**: FR-001, FR-002, NFR-001, C-002
- **Affected surfaces**: `src/specify_cli/cli/commands/agent/tasks_transition_core.py::_guard_subtasks`; `tests/specify_cli/cli/commands/agent/test_move_task_unchecked_recipe_scoped.py` (new)
- **Sequencing/depends-on**: IC-01
- **Risks**: `_guard_subtasks` is a *pure* decision function explicitly kept free of I/O; the helper import must be module-scope-safe and side-effect-free. The WP id is `req.task_id` — do not re-resolve it. Do not change the guard's pass/refuse verdict, only its message.

### IC-03 — The recipes the runtime prints

- **Purpose**: Make the implement "WHEN DONE" block and the post-`implement` runbook print the same scoped recipe, so an agent or operator running them verbatim records completion against the WP it is implementing.
- **Relevant requirements**: FR-003, FR-004, FR-005, FR-006, NFR-003
- **Affected surfaces**: `src/runtime/next/prompt_builder.py::_completion_lines`, `src/specify_cli/cli/commands/agent/workflow_executor.py` (three sites); `tests/next/test_prompt_builder_review_base.py`, `tests/integration/test_prompt_builder_owned_arms.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: `runtime` must not import `specify_cli.cli` — the helper must resolve from `specify_cli.core`. The "no subtasks declared" branch must keep its present wording (FR-006). Three call sites in `workflow_executor` are the same string: replace all three, not one.

## Testing Strategy

| Surface | Test | Proof shape |
| --- | --- | --- |
| `core/subtask_recipe.mark_status_recipe` | `tests/specify_cli/core/test_subtask_recipe.py` | Each arm renders the exact expected string: plain, `--mission`, `--owned-checkout`, multi-id, and the omission of `--mission` when the slug is unknown |
| `_guard_subtasks` refusal | `tests/specify_cli/cli/commands/agent/test_move_task_unchecked_recipe_scoped.py` | Assert the recipe names `--wp <the WP being moved>` and, on a two-WP shared-id fixture, execute the emitted line through the real `mark-status` entry point and assert exit 0 with the completion recorded against that WP |
| `_completion_lines` | `tests/next/test_prompt_builder_review_base.py`, `tests/integration/test_prompt_builder_owned_arms.py` | Assert every emitted `mark-status` line carries `--wp`, and the owned arm carries both `--wp` and `--owned-checkout` |
| workflow-executor runbook | `tests/specify_cli/cli/commands/agent/test_move_task_unchecked_recipe_scoped.py` (same file, separate test) | Assert the three rendered runbook recipes carry `--wp` |
| Byte-frozen `--help` | `tests/specify_cli/cli/commands/agent/test_tasks_cli_contract.py` | Unchanged and must stay green: this mission deliberately does not edit the `--help` docstrings |
| Architectural | `tests/architectural/test_layer_rules.py` | Unchanged and must stay green: the new `runtime` → `specify_cli.core` import is already in the ledger |

## Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| A future emitter is added without `--wp` and re-opens the bug | The recipe lives in one helper; each emitter test asserts on the emitted string, not on a hand-typed duplicate |
| The refusal gains I/O through the new import | `core/subtask_recipe.py` imports only `collections.abc`; no `Path`, no `kernel`, no status module |
| The owned-arm flag ordering breaks `mark-status` parsing | The helper renders the same option order as today and the owned integration test asserts both flags in the rendered line |
| Help-text churn from editing docstrings | Out of scope by decision: the byte-frozen `--help` fixtures stay untouched; the docstring already documents `--wp` as the disambiguator |
