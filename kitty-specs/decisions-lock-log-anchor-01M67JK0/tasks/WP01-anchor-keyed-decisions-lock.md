---
work_package_id: WP01
title: Anchor-keyed decisions lock on the write path
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-002
- C-003
- C-004
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6765-decisions-lock-log-anchor
merge_target_branch: issue-6765-decisions-lock-log-anchor
branch_strategy: Planning artifacts for this mission were generated on issue-6765-decisions-lock-log-anchor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6765-decisions-lock-log-anchor unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-decisions-lock-log-anchor-01M67JK0
base_commit: 5890573ef480e4dd75157e699d8bb18f1fe4d4c4
created_at: '2026-10-30T23:39:08.012163+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Lock keying
history:
- at: '2026-10-30T23:38:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/decisions/
create_intent:
- tests/specify_cli/decisions/test_decisions_lock_log_anchor.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/decisions/service.py
- tests/specify_cli/decisions/test_decisions_lock_log_anchor.py
# Extended in implementation: this pre-existing ratchet pins the LOCK_TIMEOUT
# error's ``lock_path`` to the ledger sidecar. With a lock taken ahead of the
# sidecar, the lock a blocked waiter contends for first is the anchor, so that
# single assertion had to name the anchor (every behavioural assertion kept).
- tests/specify_cli/decisions/test_service_terminal_concurrency.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Anchor-keyed decisions lock on the write path

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: record what you changed with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

Make every Decision Moment **write** hold a lock keyed on the event log it appends to, in
addition to the ledger-dir sidecar it holds today, so that two checkouts that write one
`status.events.jsonl` serialize even when their `decisions/` ledger directories differ.

Done when:

- `open_decision` and `_terminal_command` hold, in this order, the **log anchor lock** and
  then the existing **ledger-dir sidecar lock** (`C-004`).
- The anchor lock path comes from `kernel.event_log_append.event_log_lock_path` — no second
  digest/placement scheme (`C-003`).
- Both takes go through the existing `_decisions_lock` helper, so the timeout/refusal shape
  is unchanged (`C-001`, `NFR-003`).
- The new test module proves, through `open_decision`, that two checkouts sharing a log do
  not enter the critical section concurrently, and that distinct logs get distinct locks
  (`FR-001`, `FR-003`, `SC-001`, `SC-002`).
- `git status --porcelain` is clean after a decision write (`NFR-004`, `SC-003`), and every
  pre-existing decision suite passes unchanged (`FR-004`, `SC-004`).

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6765. Read `kitty-specs/decisions-lock-log-anchor-01M67JK0/research.md`
  first — D-2/D-3 record the actual resolution behaviour and why a naive test is vacuous.
- `src/specify_cli/decisions/service.py` is the only production file. The lock today is
  `_decisions_lock_path(mission_dir)` → `<ledger>/decisions/index.json.lock`; the row it
  protects is appended to `_write_events_path(...)`, a different path on a different
  partition for a coordination-routed Mission.
- `src/kernel/event_log_append.py` already owns anchor keying:
  `event_log_lock_path(anchor)` → `<git-common-dir>/spec-kitty-locks/event-logs/<digest>.lock`;
  non-git → `<anchor>.event-log.lock`; git unavailable → `EventLogLockUnavailableError`.
- **Do not** touch lock-timeout reporting/retryability (`C-001`, PR #6841 owns it), the
  sidecar's existence, its `.gitignore` provisioning, `repair-runtime-lock`, the
  `is_decisions_runtime_lock` coherence screen, or `_decisions_doctor` (`C-002`).
- Do not change `decisions/emit.py`. The Mission status lock it takes inside the critical
  section stays where it is (order: anchor → sidecar → status).

## Branch Strategy

- **Strategy**: feature branch per mission, merged to `main` by the operator.
- **Planning base branch**: `issue-6765-decisions-lock-log-anchor`
- **Merge target branch**: `main`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

## Subtasks & Detailed Guidance

### Subtask T001 – Survey the touched surfaces (campsite check)

- **Purpose**: confirm there is no enabler to fix first, and record the conclusion.
- **Steps**: read `service.py` around `_decisions_lock_path`, `_decisions_lock`,
  `open_decision`, `_terminal_command`; grep every caller of `_decisions_lock_path`
  (`cli/commands/_decisions_doctor.py`, `cli/commands/decision.py`,
  `cli/commands/next_cmd.py`); confirm no other module takes an event-log lock on
  `status.events.jsonl` (`grep -rn event_log_lock_path src/` — `state/retention.py` takes
  it non-blockingly for pruning).
- **Files**: `src/specify_cli/decisions/service.py`, `src/kernel/event_log_append.py`.
- **Record**: one line in the WP history (`spec-kitty agent tasks add-history WP01 --note`).

### Subtask T002 – Failing-first test through `open_decision`

- **Purpose**: prove the defect before any production edit (DIRECTIVE_034).
- **Steps**: create `tests/specify_cli/decisions/test_decisions_lock_log_anchor.py`.
  The overlap reproduction must:
  1. build two repo roots (a real git repo and a linked worktree, or two worktrees, from
     the existing fixtures under `tests/`) whose decision writes must share one event log
     while their ledger dirs differ. Because no *supported* topology produces that split
     today (research D-3), inject the split at the two resolution helpers
     (`service._ledger_dir`, `service._write_events_path`) on the module under test — never
     by reaching into `placement_seam` — and document why in the test docstring;
  2. instrument the critical section (a wrapper around `service._open_locked` recording
     enter/exit times with a small sleep) and run two `open_decision` calls concurrently
     from two threads, each with its own `repo_root`/`owned`;
  3. assert the recorded `(enter, exit)` intervals do not overlap — and add the same-fixture
     positive control that the recorder *does* observe an overlap when the anchor lock is
     disabled (e.g. monkeypatch the anchor path helper to a per-root path), so the probe
     cannot pass vacuously.
- **Files**: `tests/specify_cli/decisions/test_decisions_lock_log_anchor.py`.
- **Run**: `uv run pytest tests/specify_cli/decisions/test_decisions_lock_log_anchor.py -q`
  → RED. Commit the RED test on its own
  (`test(decisions): two checkouts sharing one log must not interleave an open (#6765)`).

### Subtask T003 – The anchor lock path and the two-lock context manager

- **Purpose**: give the write path the two identities it must hold.
- **Steps**: in `service.py`:
  - add `_decisions_anchor_lock_path(events_path: Path) -> Path` delegating to
    `kernel.event_log_append.event_log_lock_path`, with a docstring stating what it guards
    and why the anchor (not the ledger dir) is the shared identity;
  - add a context manager (e.g. `_decisions_write_locks(...)`) that enters the anchor lock
    and then the existing sidecar lock via `_decisions_lock`, taking both a
    `timeout_s: float | None` so `open_decision` passes `_OPEN_LOCK_WAIT_S` and the terminal
    verbs pass `_LOCK_ACQUIRE_TIMEOUT_S`;
  - document the global order in both docstrings.
- **Files**: `src/specify_cli/decisions/service.py`.
- **Notes**: import `event_log_lock_path` at module scope only if it does not pull heavy
  imports into the decisions command's cold path; otherwise import it function-locally
  (check `tests/architectural/test_cold_import_status_boundary.py` and any cold-import gate).

### Subtask T004 – Wire both forward write paths

- **Purpose**: make the guarantee hold on every write, not just on `open`.
- **Steps**: replace the single `with _decisions_lock(lock_path, ...)` block in
  `open_decision` and in `_terminal_command` with the two-lock context manager, passing the
  already pre-resolved `events_path` and the path-specific `mission_slug`/`decision_id`
  details. Keep every existing behaviour inside the critical section unchanged: the open's
  unbounded wait, the terminal verbs' bounded wait, the artifact/index/log write order, the
  repair calls, and the `on_minted` callback outside the lock.
- **Files**: `src/specify_cli/decisions/service.py`.
- **Verify**: `uv run pytest tests/specify_cli/decisions/test_decisions_lock_log_anchor.py -q` → GREEN.

### Subtask T005 – Pin the remaining invariants

- **Purpose**: FR-003/NFR-004 and the non-git fallback need their own pinned assertions.
- **Steps**: extend the new module with:
  - a keying test on one fixture: same events path from two checkouts with different ledger
    dirs → one anchor lock path; two different events paths → two different lock paths
    (both assertions in one parametrized test — the positive control for FR-003);
  - a residue test: after an `open_decision`, `git status --porcelain` on the checkout is
    empty and the anchor lock file exists under `<git-common-dir>/spec-kitty-locks/event-logs/`;
  - a non-git fallback test: `event_log_lock_path` on a path outside any repository returns
    the sibling `<log>.event-log.lock` (no lock is created merely by computing the path).
- **Files**: `tests/specify_cli/decisions/test_decisions_lock_log_anchor.py`.

### Subtask T006 – Targeted evidence

- **Purpose**: prove no regression in the surfaces this change sits inside.
- **Steps**: run and record results for
  `uv run pytest tests/specify_cli/decisions/ -q`,
  `tests/decisions/test_decisions_reconciler.py`,
  `tests/integration/test_owned_decision_runtime_lock.py`,
  `tests/specify_cli/orchestrator_api/test_decision_verbs.py`,
  `tests/specify_cli/cli/commands/test_decision.py`, plus
  `uv run ruff check` / `uv run ruff format --check` on the two touched files and
  `uv run mypy src/specify_cli/decisions/service.py` if that is how the repo runs mypy.
  No full heavy suite (NO_FULL_HEAVY_SUITES_IN_MISSION).

### Subtask T007 – Self-review against spec and plan

- **Purpose**: catch your own drift before the reviewer does.
- **Steps**: re-read `spec.md` FR-001..FR-004 and C-001..C-004 against the diff; confirm no
  timeout wording changed, no sidecar caller touched, no new error type; record the outcome
  with `spec-kitty agent tasks add-history WP01 --note`.

## Test Strategy

- Red-first through `open_decision` (the production entry point), not a helper.
- Each absence/overlap assertion carries a same-fixture positive control
  (`tactic:acceptance-criteria-non-vacuity`).
- The pre-existing decision suites are the ratchet; do not edit them.

## Definition of Done

- New module green; RED commit precedes the production commit in history.
- Every command from T006 run, with results recorded in the WP history and the PR body.
- Diff limited to `src/specify_cli/decisions/service.py` and the new test module.
- No change to timeout/refusal behaviour, the sidecar contract, or `emit.py`.

## Risks & Mitigations

- **Overlap test flakiness**: use an explicit `threading.Barrier` inside the instrumented
  critical section so the overlap is deterministic pre-fix, and a modest sleep so a
  post-fix queue is observable. Assert on recorded intervals, not on wall-clock.
- **Cold-import gate**: `service.py` already imports `kernel.*`; if a module-scope
  `event_log_append` import trips a cold-import or boundary gate, import it locally.
- **Deadlock**: never take the sidecar before the anchor.

## Reviewer Guidance

- Verify the order (anchor → sidecar → status) in both write paths and that no other path
  takes the sidecar first.
- Verify `open_decision` still waits unbounded on both locks and that the terminal verbs keep
  their bound.
- Verify the reproduction fails when the anchor lock is removed (run the same-fixture
  positive control) and that it is not just asserting equal strings.
- Verify nothing in `_ensure_runtime_lock_ignore` / `repair-runtime-lock` /
  `_decisions_doctor` / `next_cmd` changed.
