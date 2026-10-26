---
work_package_id: WP02
title: Done judges every issue-matrix row; the gate reports what it judged
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-005
- FR-006
- FR-007
- C-001
- C-002
- C-003
- C-005
- NFR-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6653-terminality-all-rows
merge_target_branch: issue-6653-terminality-all-rows
branch_strategy: Planning artifacts for this mission were generated on issue-6653-terminality-all-rows. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6653-terminality-all-rows unless the human explicitly redirects the landing branch.
subtasks:
- T004
- T005
- T006
- T007
- T008
- T009
history:
- at: '2026-10-26T22:30:00Z'
  action: created
  actor: claude
agent_profile: python-pedro
authoritative_surface: src/specify_cli/tasks/
create_intent:
- tests/specify_cli/cli/commands/agent/test_move_task_done_issue_matrix.py
- docs/adr/4.x/2026-10-26-1-done-judges-every-issue-matrix-row.md
execution_mode: code_change
owned_files:
- src/specify_cli/tasks/issue_matrix_approval.py
- src/specify_cli/policy/merge_gates.py
- tests/policy/test_merge_gates_issue_matrix.py
- tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py
- tests/specify_cli/cli/commands/agent/test_move_task_done_issue_matrix.py
- docs/adr/4.x/2026-10-26-1-done-judges-every-issue-matrix-row.md
- docs/adr/4.x/index.md
- docs/development/reference/issue-matrix-verdicts.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
tracker_refs: []
---

# WP02 — `done` judges every issue-matrix row; the gate reports what it judged

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile with the `/spk-charter-profile-load` skill:
`spec-kitty agent profile show python-pedro`, then `spec-kitty charter context --action implement --json`.
Apply its initialization, boundaries, directives and tactics, and say which ones you applied.

## Objective

Close #6653. At `done`:
- every `in-mission` issue-matrix row blocks, whether or not its issue is a discovered gating
  reference;
- with zero gating references, a present matrix is judged whole, diagnostics included;
- a missing matrix is still nothing to enforce.

The terminality gate's PASS says what it judged. `approved` and the completeness gate are
unchanged. Docs record the rule.

Requirements:
- FR-001, FR-002, FR-003, FR-005, FR-006, FR-007
- C-001, C-002, C-003, C-005
- NFR-003
- Decisions `01M5X206M989YE99MA0KHRFTNP` (judge the whole matrix) and
  `01M5X498X3ATTAB12KQWMDPZRV` (NOT_AUTHORED code, delivered by WP01).

## Context

Root cause (research F-1..F-4, `kitty-specs/issue-matrix-terminality-research-01M5X1X0/research.md`):

- `src/specify_cli/tasks/issue_matrix_approval.py::_issue_matrix_in_mission_rows` filters rows
  with `row.issue in referenced_issues`.
- `_issue_matrix_approval_blocker` returns `None` when `gating_refs` is empty, before reading
  the matrix. It serves BOTH `approved` and `done`:
  - `tasks_move_task.py::_mt_issue_matrix_facts` calls it for approved and done;
  - the terminality gate calls it with `target_lane=Lane.DONE`.
- `src/specify_cli/policy/merge_gates.py::_evaluate_issue_matrix_verdict_terminality_gate`
  returns PASS "No gating issue references discovered — nothing to enforce" before resolving
  the partition (#5222 leg 1). Its PASS detail "No unresolved (in-mission/unknown)
  issue-matrix rows" overclaims.
- WP01 delivers `IssueMatrixRefReadError(code="ISSUE_MATRIX_NOT_AUTHORED")` from the
  post-consolidation coordination ref read when the ref is valid and no matrix file exists.

Compat (C-003): `_issue_matrix_approval_blocker`, `_issue_matrix_evaluation` and
`_issue_matrix_in_mission_rows` are re-exported from
`cli/commands/agent/tasks_parsing_validation.py` and `cli/commands/agent/tasks.py`.
Keep the names and the call signatures backward compatible, so add only keyword arguments.

## Subtask T004 — Red-first blocker tests

In `tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py`, beside the
existing `target_lane=Lane.DONE` cases (~line 320). Build `feature_dir` with `spec.md` and
`issue-matrix.json` as those tests do.
1. `spec.md` cites `#1234` (fixed); the matrix also has `#5678: in-mission`. At DONE the
   blocker returns a message naming `#5678`. RED today.
2. Zero gating refs (spec cites nothing); the matrix is `{#5678: in-mission}`. At DONE: a
   blocker naming `#5678`. RED today.
3. Zero gating refs, plus a row with an unknown verdict: at DONE, a blocker that carries the
   row's diagnostic. RED today.
4. Controls, GREEN before and after (C-001):
   - the same matrices at `Lane.APPROVED` → `None`;
   - zero gating refs and no matrix file → `None` for both APPROVED and DONE;
   - zero refs, all terminal → `None` at DONE.

Commit the tests first.

## Subtask T005 — The blocker judges every row at done

1. `_issue_matrix_in_mission_rows`: drop the `referenced_issues` filter, so it collects every
   row whose verdict is `in-mission`. Keep the parameter so the signature is compatible;
   document it as unused, or keep using it only to order the output. The only consumer is the
   DONE leg, because the caller zeroes the list for non-DONE targets.
2. `_issue_matrix_approval_blocker`: when `not gating_refs`:
   - `target_lane != Lane.DONE` → `return None`, unchanged (C-001);
   - DONE → if `not issue_matrix_artifact_present(feature_dir, content=matrix_content)` →
     `return None` (no matrix is nothing to enforce); otherwise fall through to the shared
     evaluation, so diagnostics and in-mission rows are judged.
3. Keep the `missing_issues` logic tied to gating refs (C-002: completeness unchanged). With
   zero refs, `missing_issues` is empty by construction.
4. Keep the function at complexity ≤ 15. Extract a helper such as
   `_zero_gating_refs_outcome(...)` if needed.
5. Optionally add a pure helper `issue_matrix_judged_row_count(...)` for T007's PASS text.
   Do not change any existing return type.

## Subtask T006 — Red-first gate tests

In `tests/policy/test_merge_gates_issue_matrix.py`, reusing `_build_lanes_mission`,
`_build_coord_mission`, `_run_gates`, `_gate` and the `_GATING_SPEC_TEXT` monkeypatch
pattern. The probe in `kitty-specs/issue-matrix-terminality-research-01M5X1X0/research/probe_6653.py`
shows the three #6653 variants passing today.

1. Lanes Mission, `{#1234: fixed, #5678: in-mission}`, only `#1234` cited:
   - block mode → FAIL, blocking, details name `#5678`;
   - warn mode → FAIL, non-blocking, with a warning;
   - same fixture with `#5678: fixed` → PASS (positive control).
2. Zero refs, `{#5678: in-mission}` → FAIL naming `#5678`.
3. Spec cites `#8`, `{#8: in-mission}` → FAIL naming `#8`.
4. Zero refs, all-terminal matrix → PASS. The detail names the judged row count, e.g.
   `"No unresolved (in-mission/unknown) rows among 1 issue-matrix row(s)"`.
5. Coord Mission, zero refs:
   - (a) coordination worktree materialized with an in-mission row → FAIL;
   - (b) post-consolidation, a matrix with an in-mission row at the coordination ref → FAIL;
   - (c) post-consolidation, no matrix at the ref → PASS with a detail saying no
     issue-matrix was authored;
   - (d) the existing `TestZeroGatingReferencesNeverProbesCoordination` stays green,
     unchanged.
6. Coord, zero refs, simulated probe failure: monkeypatch `resolve_issue_matrix_partition`
   (as imported inside the gate) to raise `IssueMatrixRefReadError(PROBE_ERROR)` → FAIL,
   never PASS (NFR-002).
7. PASS-text pin: no PASS detail equals the old overclaiming
   `"No unresolved (in-mission/unknown) issue-matrix rows"`.

## Subtask T007 — The gate reads with zero refs; the PASS detail

In `_evaluate_issue_matrix_verdict_terminality_gate`:
1. Replace the zero-refs early PASS with this:
   - resolve the partition;
   - on `IssueMatrixRefReadError` with code `ISSUE_MATRIX_NOT_AUTHORED` AND zero gating refs →
     PASS, `"No issue-matrix authored and no gating issue references — nothing to enforce"`;
   - any other exception keeps the existing FAIL path (`Could not evaluate ...`).
   - A coord-less Mission and a materialized coordination dir resolve to a dir. Pass it to
     the blocker, which handles absent-matrix itself (T005).
   - #5222 F1 is preserved because a Mission with no matrix ends in PASS on every path,
     without a FAIL from the probe.
2. With gating refs present, NOT_AUTHORED keeps FAILing, as it does today: the existing
   generic `except Exception` path.
3. The PASS detail must name the judged row count (use T005's helper, or read the evaluation
   result's `rows`). The completeness gate is unchanged (C-002).
4. Keep complexity ≤ 15; extract helpers.

## Subtask T008 — `move-task --to done` tests

New file `tests/specify_cli/cli/commands/agent/test_move_task_done_issue_matrix.py`. Drive
`tasks_move_task._mt_issue_matrix_facts` on a minimal `_MoveTaskState` (see `_make_state` in
`test_tasks_move_task_seam.py` for the shape), with a real `feature_dir`:
- an uncited `in-mission` row, `target_lane=DONE` → a blocker naming the row and the
  `agent issue-verdict` remedy;
- `target_lane=APPROVED` → `None`;
- zero refs, no matrix → `None` for both.

If constructing the state turns out to be heavier than ~40 lines, test
`_issue_matrix_approval_blocker` with the arguments `_mt_issue_matrix_facts` passes, and
say so in the handoff.

## Subtask T009 — ADR, reference doc, changelog

1. `docs/adr/4.x/2026-10-26-1-done-judges-every-issue-matrix-row.md`: a short ADR in the
   repository's ADR shape (copy the frontmatter keys of a neighbouring 4.x ADR). Cover:
   - context: #6653, #4943 / PR #5222;
   - the decision: verdict decides resolution for every existing row at `done`;
     classification decides requirement;
   - zero-ref matrices are judged whole;
   - NOT_AUTHORED is "nothing to enforce" only without gating references;
   - consequences: the accepted behaviour change (C-005);
   - alternatives: the narrower PASS text.
   Add it to `docs/adr/4.x/index.md`.
2. `docs/development/reference/issue-matrix-verdicts.md`: add a section "What `done`
   enforces". Bump `updated:`.
3. `docs/changelog/CHANGELOG.md` `[Unreleased]`: an entry naming the behaviour change and what
   to do (record a terminal verdict with `spec-kitty agent issue-verdict`). Bump `updated:`.

## Test strategy

Record commands and counts:
- `uv run --frozen pytest -q tests/policy/`
- `uv run --frozen pytest -q tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py tests/specify_cli/cli/commands/agent/test_move_task_done_issue_matrix.py tests/agent/cli/commands/test_tasks_helpers.py tests/specify_cli/cli/commands/test_issue_matrix_not_applicable.py`
- `uv run --frozen pytest -q $(git grep -l "_issue_matrix_approval_blocker\|issue_matrix_verdict_terminality" -- 'tests/*.py')`
- `uv run --frozen pytest -q tests/architectural/test_issue_matrix_partition_guard.py tests/architectural/test_no_legacy_terminology.py`
- `make test-fast`
- ruff check, `ruff format --check --force-exclude` and mypy on the touched files.

Existing tests that pin the OLD behaviour (zero refs plus an in-mission row passing at done)
are stale: re-pin them to the new rule and name each one in the handoff (DIRECTIVE_041: judge
the test, not git-blame).

## Branch strategy

Planning/base branch `issue-6653-terminality-all-rows`, final merge target
`issue-6653-terminality-all-rows`. The worktree is allocated per computed lane from
`lanes.json`. Run `spec-kitty agent action implement WP02 --agent <name> --mission issue-matrix-terminality-all-rows-01M5X1ZJ`.
It is gated on WP01 being approved.

## Definition of Done

- [ ] T004/T006/T008 tests committed before the fix; red on the base for the right reason.
- [ ] All three #6653 variants FAIL in block mode; the zero-ref no-matrix cases PASS.
- [ ] The `approved` behaviour is byte-identical (controls green).
- [ ] No PASS detail claims rows that were not judged.
- [ ] ADR, reference doc and changelog written.
- [ ] ruff, format and mypy clean; complexity ≤ 15; no new suppressions.

## Reviewer guidance

- Verify C-001: diff the APPROVED behaviour.
- Verify that NOT_AUTHORED maps to PASS only on the zero-gating-refs path.
- Verify every FAIL message names the row and the remedy.
- Verify that a coordination Mission with no matrix never reaches FAIL.
