---
affected_files: []
cycle_number: 2
mission_slug: live-fresh-claim-01M6BV7X
reproduction_command: spec-kitty agent tasks move-task WP01 --to approved --mission live-fresh-claim-01M6BV7X --agent claude:opus-5.5:reviewer-renata
reviewed_at: '2026-11-01T17:38:02Z'
reviewer_agent: claude:opus-5.5:reviewer-renata
wp_id: WP01
---

Approved by claude:opus-5.5:reviewer-renata: approval:WP01

# Review cycle 1 — WP01 (live fresh-claim guard)

Reviewer: `claude:opus-5.5:reviewer-renata:reviewer` (profile `reviewer-renata`)
Scope: `kitty/mission-live-fresh-claim-01M6BV7X..kitty/mission-live-fresh-claim-01M6BV7X-lane-a`
Verdict: **pass with one required change** (applied in `46f33afa39`).

## What the diff is

One new module, `tests/specify_cli/cli/commands/agent/test_implement_live_fresh_claim_6311.py`
(three scenarios), plus the mission's planning artifacts on the mission branch.
No production file is touched: `git diff --stat origin/main..HEAD -- src/` is empty.

## Findings

### F1 (required, fixed) — a resume asserted only the exit code

`test_same_identity_reinvoke_resumes_without_conflict` proved the second
invocation exited 0. That is weaker than "idempotent resume": a command could
exit 0 while re-transitioning the WP (for example `in_progress -> in_progress`
re-emitted as a claim). Now the test snapshots the WP's lane sequence before the
second invocation and asserts it is unchanged afterwards. The resume refresh may
still add an off-axis annotation — that is the documented behaviour — but it must
never re-transition the lane. Fixed in `46f33afa39`.

### F2 (nit, applied before first hand-off) — the module wrote to the real HOME

The claim writes its rendered prompt under the per-user runtime root
(`~/.spec-kitty/spec-kitty-prompts/...`). On the shared mission host that is
another agent's directory tree; on any host it makes the test leave state behind.
The fixture now pins `SPEC_KITTY_HOME` inside `tmp_path`.

### F3 (nit, applied before first hand-off) — marker

The module is an issue-pinned guard for an already-fixed defect, which is exactly
the documented `regression` marker ("issue-pinned end-to-end regression tests for
bugs that are already FIXED … run per PR"). Added alongside `integration` and
`git_repo`; it stays selected by the router gates and out of the `fast` tier.

## Checks the reviewer ran

1. **Is the fixture live?** The fixture creates a real git repository, commits a
   baseline, and asserts `not worktree.exists()` before the run; nothing stubs
   `git`, `safe_commit`, `_ensure_target_branch_checked_out` or workspace
   creation. `test_fresh_compact_claim_completes_in_one_invocation` then asserts
   `git -C <lane worktree> rev-parse --is-inside-work-tree` returns `true`, which
   a hand-written `.git` marker cannot answer. Compared against the neighbouring
   #4665 module, whose header documents that it pre-fakes the worktree and
   monkeypatches git — the new module is a genuine step up in coverage, and the
   only reason it exists (DIRECTIVE_041 satisfied: it does not re-test the
   projection that `tests/status/test_actor_identity_reconciliation_4665.py`
   already pins).
2. **Is the positive scenario vacuous?** No: `test_different_tool_is_still_refused`
   is the positive control, and the fixture seeds no claim, so the claim under
   test is the log's first ownership record.
3. **Does the guard discriminate?** Run with the pre-`e455ce26c1` `_actor_key`
   restored in both binding modules, the module fails on scenario 1 with the
   issue's exact error (`WP WP01 is already claimed for implementation by
   'claude:opus-5.5:python-pedro:implementer'`, exit 1) and passes on head.
   Recorded in the module docstring and the mission's `design-decisions` tracer.
4. **Style and typing.** `ruff check` clean, `ruff format --check` clean,
   `mypy` clean for the new module (the one remaining mypy message is a
   pre-existing error in `tests/lane_test_utils.py:96`, untouched here).
5. **Determinism.** No network (upgrade probe disabled), explicit git identity,
   no absolute host paths, one `tmp_path` repo per test.

## Not in this review

The pre-review regression gate could not produce a verdict on this host (three
`timed_out` outcomes at its 300 s budget; `make test-fast` exceeds 9 minutes under
load average 105–357 on 40 cores). Recorded in the mission's `tooling-friction`
tracer and cited in the PR's `## Deferred`; upstream issues #3046 and #6865 cover
the gate's structural inability to run in this repo. This diff changes no
production code, so the gate has no signal to add for it.
