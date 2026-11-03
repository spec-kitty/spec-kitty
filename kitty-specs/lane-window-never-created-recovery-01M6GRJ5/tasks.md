# Tasks: A lane window that was never created names the shape it is in

**Mission**: `lane-window-never-created-recovery-01M6GRJ5`
**Branch**: `issue-7120-lane-window-never-created`
**Spec**: `spec.md` | **Plan**: `plan.md`

Issue: [#7120](https://github.com/spec-kitty/spec-kitty/issues/7120). Scope note: this Mission
implements the issue's option 1 (name the shape, name a real next step, stop the loop). Option 2 —
widening the evidence window for a `lanes` Mission that ran on its target branch — is a policy
change and stays with the operator on #7120. #7121 is untouched.

## Work Package WP01: The shared absence probe and the never-created cause

**Dependencies**: None

Requirement refs: FR-001, FR-002, FR-007, FR-008, NFR-001, NFR-002, SC-002, SC-003

Put the absent-branch knowledge in the one module that owns the evidence axis:
`consolidation/wp_evidence.py`. A public, fail-closed `branch_ref_absent` (today's private
`_branch_ref_absent`, which the #6780 landed-window path already uses); a read-only classifier for
the shape the issue recorded (a `lanes`/`coord` Mission in which no code lane has a branch); and the
cause sentence that names that shape, says creating the branch would fabricate the evidence the gate
checks, and points at the open ruling. `evaluate_evidence` then refuses the #7120 shape with a cause
line an operator can act on, while a pruned branch keeps its restore remedy and a present-but-
unreadable ref keeps "could not be diffed". No verdict, code or passing-path git call changes.

Files: `src/specify_cli/consolidation/wp_evidence.py`,
`tests/consolidation/test_wp_evidence.py`.

## Work Package WP02: move-task names the shape and stops the loop

**Dependencies**: WP01

Requirement refs: FR-003, FR-004, FR-005, FR-006, FR-009, NFR-003, SC-001, SC-002

`_mt_require_lane_evidence` sends every diff failure to "Make the lane branch and the recorded
planning commit readable, then retry", which cannot be carried out for a branch that never existed.
On the failure path only, ask WP01's `branch_ref_absent` whether the window tip is truly absent and
use the shared cause when it is; leave the present-but-unreadable sentence exactly as it is. The
gate keeps refusing on every path, keeps `IMPLEMENTATION_UNREADABLE` as its code, and adds no flag.
The tests drive a real temporary git repository (the module's monkeypatched `evidence_paths` cannot
express an absent ref).

Files: `src/specify_cli/cli/commands/agent/tasks_move_task.py`,
`tests/specify_cli/cli/commands/agent/test_move_task_evidence_gate.py`.

## Work Package WP03: End-to-end proof through the real CLI

**Dependencies**: WP01, WP02

Requirement refs: FR-009, SC-001, SC-003

Prove the shape the issue recorded through the command an operator runs: a real `lanes` Mission, the
work package's implementation committed on the target branch, no lane worktree and no lane branch,
and an unforced `move-task --to for_review`. The command exits non-zero, the work package stays
where it was, no lane branch is fabricated, and the refusal carries the shape, the fabrication
warning and the ruling. Reuses the #6715 real-CLI harness read-only.

Files: `tests/integration/test_7120_lane_window_never_created.py`.

## Out of plan artefacts

The changelog fragment and the docs row are written during wrap-up, after the pull request number
exists (`docs/changelog/unreleased/<pr>.fixed.md`), and are therefore not work packages here.

## Definition of done for the Mission

- Every test in the three work packages fails against the pre-fix source and passes with the fix.
- `move-task` still refuses; no work package changes lane on any of these paths.
- `IMPLEMENTATION_UNREADABLE`, `EVIDENCE_WINDOW_UNCOMPUTABLE` and the `SINGLE_BRANCH_*` aliases keep
  their codes and machine contract.
- The recorded #7120 refusal no longer contains an instruction the operator cannot carry out, and
  names both things a human needs: that the work is on the target branch, and that the evidence
  policy for that shape is unruled.
