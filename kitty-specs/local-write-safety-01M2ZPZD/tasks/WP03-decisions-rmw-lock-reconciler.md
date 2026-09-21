---
work_package_id: WP03
title: Decisions RMW lock + reconciler
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
planning_base_branch: fix/local-write-safety
merge_target_branch: fix/local-write-safety
branch_strategy: Planning artifacts for this mission were generated on fix/local-write-safety. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/local-write-safety unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-local-write-safety-01M2ZPZD
base_commit: 1c4140e9d98cc7a7b247fb9db6fb4185a00c0620
created_at: '2026-09-20T17:29:42.732529+00:00'
subtasks:
- T008
- T009
- T010
- T011
- T012
history:
- at: '2026-09-20T16:18:00Z'
  by: claude
  note: Authored by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/decisions/
create_intent:
- src/specify_cli/decisions/index_fold.py
- src/specify_cli/cli/commands/_decisions_doctor.py
- tests/decisions/test_decisions_concurrency.py
- tests/decisions/test_decisions_reconciler.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/decisions/store.py
- src/specify_cli/decisions/service.py
- src/specify_cli/decisions/index_fold.py
- src/specify_cli/cli/commands/_decisions_doctor.py
- src/specify_cli/cli/commands/doctor.py
- tests/decisions/test_decisions_concurrency.py
- tests/decisions/test_decisions_reconciler.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile
Load `python-pedro` via `/ad-hoc-profile-load` (+ `charter context --action implement`); apply and state.

## Objective
Stop concurrent decision opens/resolves from dropping index entries, and give operators a way to
repair an already-diverged index from the authoritative event log — behind **one** canonical fold
so the forward writer and the rebuild cannot drift.

## Context
- `decisions/store.py` `append_entry`/`update_entry` do lock-free `load_index → mutate → save_index`; `save_index` is atomic per write but nothing serializes the RMW → last-writer-wins drops entries (8 concurrent → 1).
- The check-then-act window is at the **service level** (`decisions/service.py` `open_decision`/`_terminal_command` load the index for dedup *then* append) — the lock must span that, not just `store.save_index`.
- The forward writer builds `IndexEntry` from params and derives the event from it; the reconciler needs the **inverse** `event → IndexEntry` fold, which does not exist yet. Do **not** mirror `status.reducer` (different schema).
- See `../contracts/decisions-doctor.md`, `../research.md` D4/D5. Depends on **WP01** (uses `machine_file_lock` on a sidecar lock).
- **#4813 soft-gate**: the `_decisions_doctor.py` surface should mirror the merged `_mission_state_doctor.py` shape; the store-lock + fold + concurrency core do NOT depend on #4813 and proceed now.

## Subtasks

### T008 — Canonical `event → IndexEntry` fold
- Create `decisions/index_fold.py` with a single `event → IndexEntry` fold. Refactor the forward path to derive its IndexEntry through the same mapping so there is one source of truth.

### T009 — Red-first I9 round-trip proof
- Assert `reconstructed_IndexEntry == original_IndexEntry` for the **full** object, driving the comparison off the dataclass field set so a missing/renamed field fails (not a cherry-picked subset). If any field does not round-trip today, fix the event payload first (prerequisite). This proves I9.

### T010 — Serialize the service-level RMW
- Wrap the service-level critical section (`service.py` open/resolve: load → mutate → save) under `machine_file_lock` on a dedicated sidecar `decisions/index.json.lock` (never the JSON payload). The lock must cover the load→save span, not just `store.save_index`.

### T011 — Red-first barrier-synchronized concurrency proof
- N=8 workers with **distinct keys** released simultaneously (a barrier), repeated across iterations; assert **set-equality of the 8 distinct decision keys** between the index and the `DecisionPointOpened` events (per-key 1:1 — NOT a bare `len==8` count, which a drop+duplicate would pass). Confirm it **fails without** the lock (red-first) and capture the failing run. A non-contending test that passes without the fix is unacceptable. Isolated HOME for the sidecar-lock test.

### T012 — `_decisions_doctor.py` reconciler  (implement LAST — #4813 soft-gated surface)
- Register the command in the doctor **group**: add the thin `@app.command` shell + `from ._decisions_doctor import …` in `cli/commands/doctor.py` (mirroring the `mission-state` shell); put the logic in `_decisions_doctor.py`.
- `spec-kitty doctor decisions --mission <h> [--json] [--repair]`: diagnose (read-only) reports log/index divergence; `--repair` rebuilds via the T008 fold under the sidecar lock; **no-op** when they already agree. Test (isolated HOME): heal a seeded log=8/index=5 corpus so index keys == the 8 log keys; no-op on an agreeing corpus.

## Branch Strategy
Base/merge `fix/local-write-safety`. Depends on WP01. `spec-kitty agent action implement WP03 --agent claude`.

## Definition of Done (non-fakeable)
- Concurrency proof is red-first + barrier-synchronized with distinct keys: index keys == the 8 event keys (set-equality, per-key 1:1 — **not** a bare count); fails without the lock (SC-002).
- I9 round-trip test asserts full `reconstructed_IndexEntry == original_IndexEntry` (all fields).
- Reconciler heals log=8/index=5 so index keys == the 8 log keys, and is a no-op on agreement.
- `doctor decisions` is wired into the doctor group (`doctor.py`), not left unregistered.
- One fold shared by forward + rebuild (no second reducer); reject a hand-rolled parallel interpretation.
- **Red-first evidence**: the PR "Tests run" section includes the failing-on-unlocked-code output for the concurrency + I9 tests, so red-first is verifiable after the fix lands.
- Tests use the isolated per-worker HOME. ruff + mypy clean; complexity ≤15.

## Risks & Reviewer Guidance
- **Risk**: locking only `store.save_index` leaves the service TOCTOU open. Reviewer: confirm the lock spans `service.py` load→save.
- **Risk**: reconciler invents/drops entries. Reviewer: confirm it only reconstructs log-backed entries via the shared fold.
- **Risk**: concurrency test never actually races (false green). Reviewer: confirm the barrier + red-first evidence.
