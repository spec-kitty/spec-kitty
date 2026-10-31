# Discovery: consolidate run-gap truthfulness (#6450)

**Mission**: `consolidate-run-gap-truthfulness-01M68ZR2`
**Grounded on**: `spec-kitty/spec-kitty` `main` at `dfe9efb0e8` (the reporter's run was 4.0.0rc8 at
`d881f7b4ad`, 2026-10-19).
**Input brief**: issue #6450 body plus its two comments (2026-10-27 maintainer remediation slicing).

## What the issue is

#6450 bundles seven observations from one 2026-10-19 mission run. The 2026-10-27 maintainer
comment splits them by disposition and groups items (4), (6) and (7) into one slice "after #6715
merges (same files)". #6715 is closed, so that slice is actionable now. Items (1), (2), (3) and (5)
each carry their own disposition and stay out of this Mission (C-001 in the spec).

## Decisions

### D-01 — Take items (4), (6), (7) only

The maintainer comment is the authority for the bundle's decomposition, and it names these three as
one slice over the same files. All three are message/persistence truthfulness defects in the
end-of-mission surfaces (`consolidation/phase_teardown.py`,
`acceptance/__init__.py::_build_acceptance_instructions`,
`tasks/issue_matrix_approval.py::issue_matrix_done_outcome`). Touching the other four would either
duplicate a closed ticket (item 3 = #6386) or need evidence that does not exist in the issue
(items 1, 2, 5).

### D-02 — Item (4) is grounded in the phase order, not in the reporter's tree

`consolidation/executor.py` runs `_phase_commit_and_assert` (the one bookkeeping commit) before
`_phase_cleanup_worktrees_and_branches`. The cleanup phase calls
`workspace.delete_context(...)`, a plain `unlink`, for every lane whose worktree it removes. In a
project that tracks `.kittify/workspaces/*.json` the unlink is a tracked-file deletion made after
the only commit of the run, so the target ends dirty. This repository's own `.gitignore` line 68
ignores that directory, which is why the defect does not show up when consolidating spec-kitty
itself — the reproduction has to plant a *tracked* context, which is what the acceptance test does.

### D-03 — Item (6) is the `is_integration_branch` arm of the `pr` mode

`perform_acceptance` computes `is_integration_branch = branch == _target_branch` and
`_build_acceptance_instructions` prints "Acceptance recorded on integration branch `<branch>`. Push
and open a pull request if needed." for it. On coordination topology the Mission is landed by
`spec-kitty consolidate`; a pull request is not part of the topology at all. The truthful fix is to
branch on the Mission's topology inside that arm and name the consolidation instead, leaving every
other topology's wording untouched (FR-004 is the positive control).

### D-04 — Item (7) is the message, not the decision

`issue_matrix_done_outcome` fails for two different families: rows that are missing or still
`in-mission`/`unknown`, and a fully-verdicted matrix that carries validation diagnostics (for
example `deferred-with-followup` with `evidence_ref` "PR #1", which has no follow-up handle). Both
families get the same header ("has unresolved entries. Fill in verdicts before done.") and the same
`spec-kitty agent issue-verdict` remedy line. An operator whose every row has a verdict is therefore
sent to re-record verdicts. The gate decision stays FAIL in both families — only the header and the
remedy line become cause-dependent (FR-006).

## Evidence

- `src/specify_cli/consolidation/executor.py:600-636` — phase order: `_phase_commit_and_assert` at
  line 609, `_phase_cleanup_worktrees_and_branches` at line 635.
- `src/specify_cli/consolidation/phase_teardown.py:684-719` — the tombstone loop calling
  `delete_context`, with no commit.
- `src/specify_cli/git/bookkeeping_commit.py:52` — the sanctioned `commit_merge_bookkeeping` seam
  already used by this module, so no new guarded commit call site is needed (NFR-001).
- `src/specify_cli/acceptance/__init__.py:1943-1982` — `_build_acceptance_instructions`;
  line 1951 is the pull-request sentence; `perform_acceptance` line 2024 computes the flag.
- `src/specify_cli/tasks/issue_matrix_approval.py:219` and `:392` — the only two places the
  issue-verdict remedy text is produced; both live in the `done`/approval blocker family.
- `src/specify_cli/policy/merge_gates.py:583-640` — the `issue_matrix_verdict_terminality` gate
  calls `issue_matrix_done_outcome` and renders whatever blocker it returns.
- `tests/specify_cli/test_workspace_context_tombstone.py:249-345` — the existing merge-completion
  tombstone tests, and the `_run_cleanup_phase` harness this Mission's red test reuses.
- `tests/policy/test_merge_gates_issue_matrix.py` — the gate's real-git fixtures and its terminal
  positive control; the new red test reuses `_build_coord_mission`.
- `tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py:226,369` — the existing
  pins on "has unresolved entries" and "Fill in verdicts before done.", which the missing-verdict
  arm must keep.

## Open questions (resolved before tasks)

- **Q-01** Does `safe_commit` (behind `commit_merge_bookkeeping`) stage a *deletion* of a tracked
  path? *(Resolved: yes — the existing `#5651` `_fold_alias_directory` path appends deleted files
  after the existence filter for exactly this reason,
  `consolidation/phase_bookkeeping.py:720-728`.)*
- **Q-02** Does the cleanup phase already have access to the resolved merge target for a
  destination override? *(Resolved: `run.lanes_manifest.target_branch`, used the same way by
  `_phase_commit_and_assert`.)*
- **Q-03** Can the accept-side fix stay inside the `pr` arm without changing `local`/`checklist`
  output? *(Resolved: yes — the misleading sentence exists only in the `pr`/integration-branch
  arm; `local` and `checklist` arms are untouched and are covered by existing pins.)*

## Deferred (not this Mission)

- Item (1) commit trailers/signing — the maintainer comment defers it to its own issue after the
  Java write-core commit design.
- Item (2) `spec-commit` sweeping `decisions/index.json.lock` — the comment asks for the exact
  reproducing invocation; the current command rejects directories and stages explicit files, so a
  reproduction needs the shell-glob invocation and a lock present at expansion time.
- Item (3) review-lock release deleting the tracked lock — duplicate of #6386 (closed with the
  `ReviewLock` claim-path fix).
- Item (5) stale-assertion `min_version` false positive — needs the concrete fixture that tripped
  it; the analyzer is advisory-only in `consolidate`.
