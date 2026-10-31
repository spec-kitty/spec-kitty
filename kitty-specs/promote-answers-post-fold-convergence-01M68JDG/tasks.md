# Work Packages: Pin the post-fold convergence of the interview promotion (#6549)

**Inputs**: `kitty-specs/promote-answers-post-fold-convergence-01M68JDG/spec.md`, `plan.md`

## Work Package WP01: Pin the convergence, and prove the pin bites (Priority: P1) 🎯 MVP

**Goal**: One new test module pins the post-fold no-op of the registered interview
promotion, the two-run convergence of a fold-crossing project, and — with the
supersession entry removed on the same fixture — that the #6549 symptom returns. The ADR
amendment that documents the fix names the pin.
**Independent Test**: `uv run pytest tests/upgrade/test_promote_answers_post_fold_convergence_6549.py -q`
is green; dropping `unify_charter_activation_promote_answers` from
`SUPERSEDED_MIGRATIONS` inside the bite test turns the same fixture red.
**Prompt**: `/tasks/WP01-pin-post-fold-convergence.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

T001 Build the fold-crossing fixture (real git repo, pre-ledger metadata stamp, mirrored interview selection in `config.yaml`) and the whole-worktree convergence snapshot helper
T002 Add the two-run convergence test for FR-001 through the production CLI `upgrade` entry point (FR-001, SC-001, C-002)
T003 Add the post-fold seam test for the registered promotion plus the shipped-class positive control (FR-002, FR-004)
T004 Add the bite proof that removes the supersession entry on the same fixture, restores it in `finally`, and asserts the whole-kind `config.yaml` copy returns (FR-003, SC-002)
T005 Name the pin in ADR `2026-10-17-1` Amendment 2026-10-25 (FR-005)
T006 Run the new module plus the neighbouring upgrade suites; record results for the PR body (SC-004)

### Dependencies

- None.

### Constraints restated for the implementer

- No file under `src/` changes (NFR-002). The shipped migration module is byte-frozen
  (C-001).
- No test is skipped/xfailed/deselected and no gate is edited (NFR-003).
- Projects already damaged by the pre-#6629 second pass keep their stale `config.yaml`
  copy; the module documents that boundary and does not strip it (C-003).
