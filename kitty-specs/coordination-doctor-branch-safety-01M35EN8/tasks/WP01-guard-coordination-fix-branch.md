---
work_package_id: WP01
title: Guard coordination fix branch identity
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
planning_base_branch: issue-4920-coordination-doctor-branch-safety
merge_target_branch: issue-4920-coordination-doctor-branch-safety
branch_strategy: Planning artifacts for this mission were generated on issue-4920-coordination-doctor-branch-safety. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4920-coordination-doctor-branch-safety unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/_coordination_doctor.py
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/_coordination_doctor.py
- tests/coordination/test_coord_staleness.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 – Guard Coordination Fix Branch Identity

## Objective

Make `spec-kitty doctor coordination --fix` fail closed when the recorded
coordination worktree is not checked out on the declared coordination branch. Prove
the refusal mutates no refs and preserve the valid correct-branch fast-forward. Tie the
success message to a verified declared-ref postcondition.

Implement with:

`spec-kitty agent action implement WP01 --agent codex --mission coordination-doctor-branch-safety-01M35EN8`

## Context

GitHub issue #4920 demonstrates that `_fix_one_mission_coord_staleness` computes the
declared coordination and target SHAs correctly, then runs `git merge --ff-only` inside
the recorded worktree without confirming which branch is checked out there. Git
advances the checked-out branch, not the branch named in mission metadata. The command
then prints success using precomputed SHAs although the declared coordination ref is
still stale.

The same module already contains `_coord_worktree_head_finding`, the canonical
read-only branch identity check used by coordination health reporting. Reuse it. Do not
create a second symbolic-ref parser, switch the worktree branch, reset any ref, or
discard any user state.

Relevant artifacts:

- `.kittify/charter/charter.md`
- `kitty-specs/coordination-doctor-branch-safety-01M35EN8/spec.md`
- `kitty-specs/coordination-doctor-branch-safety-01M35EN8/plan.md`
- `kitty-specs/coordination-doctor-branch-safety-01M35EN8/research.md`
- `kitty-specs/coordination-doctor-branch-safety-01M35EN8/data-model.md`
- `kitty-specs/coordination-doctor-branch-safety-01M35EN8/quickstart.md`

## Branch Strategy

- **Strategy**: single branch on the issue topic branch
- **Planning base branch**: `issue-4920-coordination-doctor-branch-safety`
- **Merge target branch**: `issue-4920-coordination-doctor-branch-safety`
- **Publication target**: PR to `main`; the implementer does not merge

## Subtasks & Detailed Guidance

### Subtask T001 – Add the real-Git wrong-branch acceptance test

- **Purpose**: Pin issue #4920 through the existing command entry point with real Git
  behavior rather than subprocess mocks.
- **Steps**:
  1. Extend `tests/coordination/test_coord_staleness.py` with a fixture or local setup
     that creates a stale declared coordination branch and a different branch checked
     out at the path returned by `CoordinationWorkspace.worktree_path`.
  2. Ensure both the declared coordination ref and the wrong checked-out ref begin as
     strict ancestors of the target so the pre-fix command attempts and succeeds at
     `merge --ff-only` on the wrong ref.
  3. Invoke `run_coordination_health(json_output=True, fix=True)` exactly as the
     existing correct-branch test does.
  4. Assert exit code 1, the stable blocked-fix error code, branch-mismatch detail, and
     absence of `Fast-forwarded`.
  5. Snapshot and compare the declared coordination ref, wrong ref, worktree `HEAD`,
     and target ref before/after.
- **Files**: Modify only `tests/coordination/test_coord_staleness.py`.
- **Validation**: The new test must fail on the untouched source for the issue's exact
  reason: the wrong branch advances and/or the command falsely exits 0 and prints
  success.
- **Parallel?**: No. This is the required first commit and defines the product contract.

### Subtask T002 – Commit the failing acceptance contract

- **Purpose**: Preserve auditable red-first evidence required by the charter.
- **Steps**:
  1. Run only the new test and capture the failure summary.
  2. Confirm the failure is on the pre-existing product behavior, not fixture setup.
  3. Commit the test without production changes using a conventional `test(...)`
     message that references #4920.
  4. Record the red command and observed assertion in the work-package activity log or
     mission tracer after the code-owned commit is safely made.
- **Files**: The committed code change is only
  `tests/coordination/test_coord_staleness.py`; workflow metadata may be written by
  canonical Spec Kitty commands.
- **Validation**: `git show --stat HEAD` contains the test file and no production file.
- **Parallel?**: No. T003 cannot begin until this commit exists.

### Subtask T003 – Add the fail-closed precondition and truthful postcondition

- **Purpose**: Prevent unauthorized ref mutation and eliminate false successful output.
- **Steps**:
  1. In `_fix_one_mission_coord_staleness`, after resolving the worktree and proving it
     exists, call `_coord_worktree_head_finding(worktree, coord_branch)`.
  2. If it returns a finding, translate the mismatch into
     `_coord_staleness_fix_blocked_finding` with a reason that includes the existing
     mismatch message. Return the finding before dirty-state inspection or mutation.
  3. Preserve the current dirty and diverged refusal paths and their stable code.
  4. Keep `git merge --ff-only` as the mutation for the valid path.
  5. After the subprocess returns, re-read `refs/heads/<coord_branch>` with the existing
     `_rev_parse` authority.
  6. Print `Fast-forwarded` only when the observed SHA equals `target_sha`; otherwise
     return a structured blocked-fix error explaining that the declared ref did not
     reach the target. Do not print success first.
  7. Keep the function within the complexity ceiling; extract only if needed.
- **Files**: Modify only
  `src/specify_cli/cli/commands/_coordination_doctor.py`.
- **Validation**: The new wrong-branch test turns green and the existing strict-ancestor
  correct-branch test remains green.
- **Parallel?**: No. Depends on the committed red contract.

### Subtask T004 – Run focused and owning-subsystem verification

- **Purpose**: Establish that the safety guard composes with existing coordination
  repair behavior.
- **Steps**:
  1. Run the new test alone.
  2. Run all of `tests/coordination/test_coord_staleness.py`.
  3. Run all of `tests/coordination` because it owns the changed behavior.
  4. Run `make test-fast` as the shared repository baseline.
  5. Run targeted Ruff check and format check for both changed files.
  6. Run strict MyPy for the changed source module or the repository's calibrated
     owning package command.
  7. Classify any failure against `origin/main`; do not retry-to-green. A confirmed
     pre-existing failure must be filed before continuing.
- **Files**: No additional product files.
- **Validation**: Every required command has exact pass/fail counts recorded for PR
  handoff.
- **Parallel?**: The independent lint and typecheck commands may run after T003, but
  test commands should remain ordered from narrow to broad for clear attribution.

### Subtask T005 – Self-review the aggregate diff

- **Purpose**: Catch safety, wording, scope, and contract regressions before independent
  review.
- **Steps**:
  1. Review `git diff origin/main...HEAD` for changes outside the two owned files and
     expected mission/runtime artifacts.
  2. Verify there is no second symbolic-HEAD parser, no branch switching, no reset,
     no exception suppression, and no new public error code.
  3. Verify the wrong-branch test would fail if the new guard call were deleted.
  4. Verify the correct-branch test would fail if valid repairs were accidentally
     blocked.
  5. Confirm success output follows, rather than precedes, the declared-ref
     postcondition check.
- **Files**: No additional product files.
- **Validation**: Clean diff review and green required commands.
- **Parallel?**: No. Final work-package step.

## Test Strategy

- Red-first command: targeted node for the new #4920 acceptance test.
- Focused contract: `uv run --extra test pytest -q tests/coordination/test_coord_staleness.py`.
- Owning subsystem: `uv run --extra test pytest -q tests/coordination`.
- Shared baseline: `make test-fast`.
- Lint: `uv run --frozen ruff check src/specify_cli/cli/commands/_coordination_doctor.py tests/coordination/test_coord_staleness.py`.
- Format: `uv run --frozen ruff format --check src/specify_cli/cli/commands/_coordination_doctor.py tests/coordination/test_coord_staleness.py`.
- Typecheck: run strict MyPy on the changed source within the repository configuration.

## Definition of Done

- [ ] The real-Git wrong-branch test was committed red before source changes.
- [ ] Wrong-branch and detached worktrees are refused before mutation.
- [ ] The refused command returns a structured error, exits 1, and prints no success.
- [ ] All involved refs remain unchanged in the regression.
- [ ] The correct-branch strict-ancestor repair still advances the declared ref.
- [ ] Success is printed only after the declared ref is observed at the target SHA.
- [ ] Focused, owning-subsystem, fast baseline, Ruff, format, and MyPy gates pass.
- [ ] The aggregate diff contains no unrelated product changes or suppressions.

## Risks

- **Fixture accidentally cannot reproduce**: Make the wrong branch a strict ancestor of
  target and confirm the pre-fix command exits 0/advances it.
- **Duplicate authority**: Reuse `_coord_worktree_head_finding` and `_rev_parse`.
- **Cross-mission abort**: Return a finding; do not raise for the mismatch.
- **False success after a race**: Verify the declared ref after the merge before
  printing.
- **Scope growth**: Do not attempt path registration repair, branch switching, or
  generalized coordination healing.

## Reviewer Guidance

Use the `reviewer-renata` profile and focus on mutation authorization, byte-identical
ref evidence, and whether the acceptance test genuinely passes through
`run_coordination_health`. Confirm the correct-branch control still exercises the
positive mutation path. Reject any solution that merely changes the message after the
wrong branch has already advanced.

## Activity Log

- 2026-09-22T21:11:00Z – codex – Work package prompt created from the governed plan.
