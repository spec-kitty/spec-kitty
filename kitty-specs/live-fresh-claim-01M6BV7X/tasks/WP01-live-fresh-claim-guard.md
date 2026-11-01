---
work_package_id: WP01
title: Live fresh-claim guard
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- C-001
- C-002
planning_base_branch: issue-6311-live-fresh-claim
merge_target_branch: issue-6311-live-fresh-claim
branch_strategy: Planning artifacts for this mission were generated on issue-6311-live-fresh-claim. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6311-live-fresh-claim unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-live-fresh-claim-01M6BV7X
base_commit: 17c4223883abff0205c89241c733f6500bbfcae4
created_at: '2026-11-01T15:26:47.292766+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1
history: []
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_implement_live_fresh_claim_6311.py
execution_mode: code_change
model: ''
owned_files:
- tests/specify_cli/cli/commands/agent/test_implement_live_fresh_claim_6311.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6311'
---

# Work Package Prompt: WP01 – Live fresh-claim guard

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (implementer) before parsing the rest of this
prompt. If it cannot be loaded, run `spec-kitty agent profile list` and pick the
best match for `task_type: implement` on
`authoritative_surface: tests/specify_cli/cli/commands/agent/`.

## Objective

Pin the **live** fresh compact-actor claim — issue #6311 — with one integration
test module. The production behaviour is already correct (see
`kitty-specs/live-fresh-claim-01M6BV7X/research.md`); what is missing is a guard
that exercises the documented command against a real allocator-created lane
worktree instead of a seeded log and a pre-faked directory.

**Do not change production code.** If the module cannot pass without a
production change, stop and report — that is a finding, not a licence to edit
`src/`.

## Subtasks

### T001 — Real-git mission fixture

Build a throwaway repository in `tmp_path`:

- `git init`, an explicit committer identity (`user.name`/`user.email` via `-c`),
  one baseline commit, and a writable branch;
- a mission directory `kitty-specs/<slug>/` with `meta.json` (ULID `mission_id`
  + `mid8`, `mission_slug`, `mission_type`, `target_branch` = the branch you
  committed to), a single-lane `lanes.json` claiming `WP01`
  (`tests/lane_test_utils.write_single_lane_manifest` is the established
  helper), and a `tasks/WP01-*.md` prompt file with the usual frontmatter;
- the mission status log seeded at **`planned` only** — the state
  `finalize-tasks` leaves. No claim event, no `in_progress` event;
- **no** pre-created lane worktree directory: the allocator must create it.

Reuse `tests/_support/status_seed.py` / `tests/lane_test_utils.py` where they fit
rather than inventing a parallel fixture (single canonical authority).

### T002 — Scenario 1: the documented claim completes in one invocation (FR-001, FR-005)

Invoke the real CLI surface with `CliRunner`:

```python
CliRunner().invoke(
    workflow.app,
    ["implement", "WP01", "--mission", SLUG,
     "--agent", "claude:opus-5.5:python-pedro:implementer"],
)
```

Assert exit code 0, stdout contains no `already claimed`, and the implement
prompt was rendered. Assert the resolved lane worktree exists **and is a real git
worktree** (`git -C <path> rev-parse --is-inside-work-tree` returns `true`) —
that is the FR-005 anchor which stops the module from degrading into another
pre-faked-directory test.

### T003 — Scenario 2: the recorded claim names the compact identity (FR-002)

Read the mission's status events and assert the claim event (`planned ->
claimed` / `claimed -> in_progress`) records the tool of the compact identity —
i.e. both representations of one agent reconcile. Use the production reader
(`specify_cli.status.store.read_events` or the mission's `status.events.jsonl`
through the canonical loader), not a hand-rolled parser.

### T004 — Scenario 3: same-identity resume is idempotent (FR-003)

Invoke the same command again with the same compact identity. Assert exit 0 and
no `already claimed`; a resume must be a no-op, not a conflict.

### T005 — Scenario 4: a different tool is refused (FR-004, positive control)

Invoke with a different tool (`codex:gpt-6:python-pedro:implementer`). Assert a
non-zero exit and `already claimed` in stdout. This is the positive control that
keeps scenarios 1–3 from passing vacuously.

### T006 — Verification run

- `uv run pytest tests/specify_cli/cli/commands/agent/test_implement_live_fresh_claim_6311.py -q`
- `uv run pytest tests/specify_cli/cli/commands/agent/test_implement_compact_identity_4665.py tests/status/test_actor_identity_reconciliation_4665.py -q`
- `uv run ruff check <new file>` and `uv run mypy <new file>`

Record the commands and their outcomes for the work package review.

## Red-first note

The defect this guards is already fixed upstream, so the red baseline is the
pre-fix comparison layer, not this branch:

1. with the pre-`e455ce26c1` `_actor_key` (compact string projected verbatim, in
   `work_package_lifecycle` and `review_roles`) restored in-process, the same
   live command prints `Error: WP WP01 is already claimed for implementation by
   'claude:opus-5.5:python-pedro:implementer'` and exits 1 (verified live by the
   planner on a throwaway lanes mission, `research.md` D2);
2. on the current code the same command exits 0 and renders the prompt.

Record scenario 1's discriminating power in the module docstring, citing the
pre-fix behaviour — do **not** monkeypatch `_actor_key` inside the test module to
manufacture a red run.

## Definition of Done

- Four scenarios green in one new module, marked `integration` and `git_repo`.
- Real git and a real lane worktree; no seeded claim; no monkeypatched `git`,
  `safe_commit` or workspace creation.
- No production file modified; `git diff --stat` shows only the new test module.
- `ruff` / `mypy` clean on the new file; neighbouring suites still green.
- No machine-local absolute paths or personal data in the file or the commit.
