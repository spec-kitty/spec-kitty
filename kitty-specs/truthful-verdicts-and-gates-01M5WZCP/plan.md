# Implementation Plan: Truthful verdicts and gates

**Branch**: `issue-6652-verdict-gate-truthfulness` | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/truthful-verdicts-and-gates-01M5WZCP/spec.md`

## Summary

Three independent defect fixes, each red-first through its pre-existing entry point:

1. **Approval review-cycle record** (#6652, #6654): `_persist_approved_review_cycle` (`src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py`) writes the reviewer's feedback file after the approval line, writes a new cycle when a file is supplied on an already-approved WP, refuses a supplied file it cannot record (damaged verdict slot), and builds `reproduction_command` with `shlex.join`.
2. **Issue-matrix terminality** (#6653): at `done`, `_issue_matrix_in_mission_rows` (`src/specify_cli/tasks/issue_matrix_approval.py`) counts every `in-mission` row; with zero gating references the blocker and the consolidation gate (`src/specify_cli/policy/merge_gates.py`) evaluate an existing matrix and pass, with a message that says so, only when no matrix exists.
3. **safe-commit pre-check** (#6649, #5393): `_has_candidate_changes` (`src/specify_cli/cli/commands/safe_commit_cmd.py`) counts an explicitly named untracked-ignored file, as the commit helper already force-stages it; a CLI regression test pins non-ASCII directory expansion.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml; git via `kernel.git`
**Storage**: files in git (review-cycle Markdown, issue-matrix JSON/Markdown, status event log)
**Testing**: pytest, red-first; `make test-fast` plus the touched modules' test files and owning subsystem directories
**Target Platform**: Linux, macOS, Windows (CLI)
**Project Type**: single
**Performance Goals**: no added git process per command beyond what is already run (the safe-commit probe keeps one `git status`)
**Constraints**: mypy/ruff clean, no new suppressions, complexity ≤ 15; the provenance guard and rejection path unchanged
**Scale/Scope**: 4 source modules, 3 PRs

## Charter Check

- Single canonical authority: the approval keeps using the one review-cycle writer (`create_rejected_review_cycle`) and the one provenance guard; no second writer. ✅
- ATDD / red-first (C-011, Standing Order #4): each WP commits its failing test before its fix. ✅
- Architectural alignment: no layer crossing; `policy -> tasks` import direction unchanged (#5222 F4). ✅
- Test policy: targeted files + owning directories; no full architectural sweep. ✅
- Terminology canon: Mission, never feature, in new text. ✅

No violations.

## Project Structure

### Documentation (this mission)

```
kitty-specs/truthful-verdicts-and-gates-01M5WZCP/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks/
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py   # IC-01
src/specify_cli/review/cycle.py                                   # IC-01 (body preamble)
src/specify_cli/tasks/issue_matrix_approval.py                    # IC-02
src/specify_cli/policy/merge_gates.py                             # IC-02
src/specify_cli/cli/commands/safe_commit_cmd.py                   # IC-03
tests/specify_cli/cli/commands/agent/                             # IC-01 tests
tests/policy/test_merge_gates_issue_matrix.py, tests/tasks/       # IC-02 tests
tests/specify_cli/cli/commands/test_safe_commit_cli.py            # IC-03 tests
```

**Structure Decision**: single project; changes stay in the modules that own each defect.

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — Approval record carries the review and a replayable command

- **Purpose**: an approval never reports durable persistence of feedback it discarded, and its replay command replays.
- **Relevant requirements**: FR-001..FR-006
- **Affected surfaces**: `tasks_verdict_persistence._persist_approved_review_cycle`; `review/cycle.create_rejected_review_cycle` / `_resolve_review_body` (optional `body_preamble` used only with `feedback_source`, so the provenance guard still runs on the file)
- **Sequencing/depends-on**: none
- **Risks**: the M1 content-identity concern (#3156) applies only to the synthesized body, which stays on `body=`; a reviewer file goes through the guard by design. The arbiter-override edge keeps ignoring the file (out of scope; residual recorded).

### IC-02 — Terminality gate evaluates every row it reports on

- **Purpose**: the done-gate and consolidation gate fail for any `in-mission`/unknown row and never claim a check they skipped.
- **Relevant requirements**: FR-007..FR-010
- **Affected surfaces**: `tasks/issue_matrix_approval._issue_matrix_in_mission_rows`, `_issue_matrix_approval_blocker`; `policy/merge_gates` terminality gate zero-reference arm
- **Sequencing/depends-on**: none
- **Risks**: #5222 F1 — a coordination Mission with no matrix must not fail on the coordination ref probe; zero-reference arm treats an unreadable/absent matrix as "no matrix" with an explicit PASS message.

### IC-03 — safe-commit pre-check sees what the helper stages

- **Purpose**: a lone named ignored file is committed like the same file named beside another.
- **Relevant requirements**: FR-011, FR-012
- **Affected surfaces**: `cli/commands/safe_commit_cmd._has_candidate_changes`
- **Sequencing/depends-on**: none
- **Risks**: directory arguments are already expanded to non-ignored changed files before the probe, so `--ignored` affects only explicit file arguments.
