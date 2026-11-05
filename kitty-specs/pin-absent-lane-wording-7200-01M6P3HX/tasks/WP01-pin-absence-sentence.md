---
work_package_id: WP01
title: Pin the absence sentence and prove the guard
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
- C-004
- SC-001
- SC-002
- SC-003
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Test pin
history:
- at: '2026-11-05T15:01:22Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: tests/git_ops/
create_intent:
- docs/changelog/unreleased/7200-pin-absent-lane-wording.internal.md
execution_mode: code_change
pre_review_test_scope: tests/git_ops/test_move_task_evidence_refusals.py
owned_files:
- tests/git_ops/test_move_task_evidence_refusals.py
- docs/changelog/unreleased/7200-pin-absent-lane-wording.internal.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Pin the absence sentence and prove the guard

## ⚡ Do This First: Load Agent Profile

Load profile `implementer-ivan` (role implementer) with the `/spk-charter-profile-load` skill before reading anything else, then follow its guidance. Read `.kittify/charter/charter.md`, the mission `spec.md`, `plan.md`, and `research.md`.

## Objective

Issue [#7200](https://github.com/spec-kitty/spec-kitty/issues/7200) closes a test gap from Mission 250. In `tests/git_ops/test_move_task_evidence_refusals.py::test_a_missing_lane_with_a_sibling_names_conditional_restore`, the refusal wording for an absent lane branch that has a sibling is not pinned. Replacing the shipped production sentence

```text
the lane branch kitty/mission-fx-lane-b does not exist in this checkout
```

with `the lane branch kitty/mission-fx-lane-b is unavailable` leaves the test green, so FR-001's absence-versus-unreadability distinction can regress silently.

Add the missing assertion in that same test, prove it fails under that temporary production mutation, restore the source, and add the internal changelog fragment. The committed diff must contain **no** `src/` change.

## Context

- Shipped classifier: `src/specify_cli/consolidation/wp_evidence.py::absent_lane_window_cause` (introduced by #7120 / PR #7146, merged `582b5697`).
- Sibling shape: the target lane ref is absent but not every code-lane ref is absent. The classifier builds `local_fact = f"the lane branch {branch} does not exist in this checkout"`, then appends "Local refs do not establish whether this lane previously existed. If it did exist and was pruned or never fetched here, restore its recorded tip from `refs/spec-kitty/lane-tip/<branch>` …".
- Never-created shape: every code-lane ref is absent, so the message additionally contains "and no lane of this Mission has a branch here".
- Unreadable shape: the ref exists but cannot be read, or the probe raises; the message says "could not be diffed".
- The target test already builds a real Git repo, creates sibling branch `kitty/mission-fx-lane-a`, makes the diff probe raise `GitProbeError("bad revision")`, and calls the real move-task gate `move_task_module._mt_require_implementation_evidence`.
- Existing assertions in that test: `IMPLEMENTATION_UNREADABLE`, the lane-tip ref, "If it did exist", and the absence of "no lane of this Mission has a branch here". The local-fact sentence is not asserted.

## Subtasks

### T001 — Pin the absence sentence

**File**: `tests/git_ops/test_move_task_evidence_refusals.py`

In `test_a_missing_lane_with_a_sibling_names_conditional_restore`, after the existing message assertions, add an assertion that pins the full local-fact sentence:

```python
assert "the lane branch kitty/mission-fx-lane-b does not exist in this checkout" in message
```

Keep every existing assertion. Do **not** remove the lane-tip, "If it did exist", or never-created-negative assertions: together they keep the test discriminating the sibling shape from the all-lanes-absent and unreadable shapes. Do not add a new test function, a snapshot of the whole message, or a second wording owner.

### T002 — Prove the guard is non-vacuous (red first)

1. Run the target test on unmodified source and confirm it passes:
   ```bash
   uv run --frozen pytest 'tests/git_ops/test_move_task_evidence_refusals.py::test_a_missing_lane_with_a_sibling_names_conditional_restore' -q -p no:randomly
   ```
2. Apply the issue's production mutation **temporarily**:
   ```python
   # src/specify_cli/consolidation/wp_evidence.py
   # before
   local_fact = f"the lane branch {branch} does not exist in this checkout"
   # mutated
   local_fact = f"the lane branch {branch} is unavailable"
   ```
3. Re-run the same test and confirm it **fails** on the new absence assertion. This is the red receipt for the PR body.
4. Restore `wp_evidence.py` exactly (for example `cp` back from a saved copy, or `git checkout -- src/specify_cli/consolidation/wp_evidence.py`). Confirm `git diff -- src/specify_cli/consolidation/wp_evidence.py` is empty before staging. Never commit the mutation.

### T003 — Internal changelog fragment

Create `docs/changelog/unreleased/7200-pin-absent-lane-wording.internal.md` with no heading, following `docs/changelog/unreleased/README.md`:

```markdown
- **Pin move-task's absent-lane sentence for a missing lane with a sibling** (#7200). A test-only guard now fails if "the lane branch … does not exist in this checkout" is softened to "is unavailable" on the sibling-lane path, preserving #7120's absence-versus-unreadability distinction.
```

Once the PR exists and its number is known, `git mv` the fragment to `<pr>.internal.md` and update nothing else. Do not edit `docs/changelog/CHANGELOG.md`.

### T004 — Focused verification

Run and record exact results:

```bash
uv run --frozen pytest tests/git_ops/test_move_task_evidence_refusals.py -q -p no:randomly
uv run --frozen ruff check tests/git_ops/test_move_task_evidence_refusals.py
uv run --frozen ruff format --check --force-exclude tests/git_ops/test_move_task_evidence_refusals.py
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
```

Expected: `3 passed`; Ruff and format exit 0; changelog style and spelling report no finding caused by this fragment. Do not run a full heavy suite.

## Branch Strategy

Planning artifacts were generated on `main` in the primary checkout. During implementation, use the workspace/lane path the runtime resolves for the WP (from `lanes.json`); completed changes merge back into `main` through the mission branch. Never push to `main`, force-push an owned lane in a way that discards reviewed work, or merge any pull request.

## Definition of Done

- [ ] The target test asserts the exact `the lane branch kitty/mission-fx-lane-b does not exist in this checkout` sentence.
- [ ] The mutation proof is recorded (test fails under `is unavailable`, passes after restore).
- [ ] `git diff --stat` shows only `tests/git_ops/test_move_task_evidence_refusals.py` and the internal changelog fragment; no `src/` file changes.
- [ ] Focused real-Git module: 3 passed.
- [ ] Ruff check and format check: exit 0.
- [ ] No assertion removed, no skip/xfail added, no gate weakened.

## Reviewer Guidance

- Verify the assertion pins absence wording, not merely a substring that also appears in the never-created shape.
- Verify the test still exercises the real move-task entry point and the real Git fixture.
- Verify the production file is byte-identical to `main`.
- Confirm the fragment is internal (test-only change) and follows the fragment style.
