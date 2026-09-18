---
work_package_id: WP05
title: Migrate filelock-family onto kernel primitive + retire filelock
dependencies:
- WP03
requirement_refs:
- FR-009
- NFR-001
planning_base_branch: feat/cross-os-primitive-unification
merge_target_branch: feat/cross-os-primitive-unification
branch_strategy: Planning artifacts for this mission were generated on feat/cross-os-primitive-unification. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/cross-os-primitive-unification unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cross-os-primitive-unification-01M2T1CM
base_commit: c441079109016d0e4479b080113b4fdfcca664ca
created_at: '2026-09-18T14:22:38.100826+00:00'
subtasks:
- T021
- T022
- T023
- T024
- T025
- T026
phase: Phase 1 - Implementation
history:
- at: '2026-09-18T11:05:00Z'
  actor: system
  action: Prompt generated for cross-os-primitive-unification mission
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/checkout_file_lock.py
create_intent:
- tests/specify_cli/core/test_checkout_file_lock_migration.py
- tests/status/test_locking_reentrancy_migration.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/core/checkout_file_lock.py
- src/specify_cli/status/locking.py
- src/specify_cli/review/verdict_commit_queue.py
- src/specify_cli/auth/secure_storage/file_fallback.py
- src/specify_cli/zeitgeist_client/credentials.py
- src/specify_cli/zeitgeist_client/outbox_approval.py
- tests/specify_cli/core/test_checkout_file_lock_migration.py
- tests/status/test_locking_reentrancy_migration.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#4714'
---

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (role: implementer) via the profile-load skill before proceeding.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## Objectives & Success Criteria

Migrate the six `filelock`-library sites onto the canonical `kernel/locks.py`
primitive — preserving re-entrancy, blocking-timeout, and the verdict-queue
test-double contract — then remove `filelock` from `pyproject.toml` and shrink
the lock gate to empty. **This is the highest-risk wave and the deferral seam
(A-01)**: if cross-process/blocking-timeout parity cannot be proven in-mission,
STOP the filelock removal, leave these sites in the gate allowlist, and hand off
a tracked follow-up sub-issue instead — do not ship an unproven cross-process lock.

Read first: `../spec.md` (FR-009, NFR-001, SC-003/005, A-01),
`../contracts/lock-primitive.md`, `../research.md` R-04, `../data-model.md` E-01.

**Success (full scope)**: no `filelock` import remains; it is gone from runtime
deps; re-entrancy + test-double preserved; cross-process contention proven.

## Context

Depends on WP03 (the primitive with sync surface + reentrancy + test-double
seam). Contracts to preserve (else silent regression):
- `status/locking.py` — thread-local re-entrant counts.
- `review/verdict_commit_queue.py` — references the concrete `FileLock` type for a
  test double → migrate onto the primitive's injection seam.
- `auth/secure_storage/file_fallback.py` — fixed `timeout=10` blocking acquire.
- `zeitgeist_client/{credentials,outbox_approval}.py` — local *client* consumer
  code (CLAUDE.md client-repo inversion), safe to migrate here.

## Subtasks

### T021 — Migrate checkout_file_lock.py
Replace `filelock.FileLock` (L26) with the canonical sync primitive; preserve the
`.lock`-beside-common-dir sidecar semantics and `acquire_or_raise` behaviour.

### T022 — Migrate status/locking.py (preserve re-entrancy)
Replace `filelock.FileLock` (L34/L232) with the canonical primitive using its
re-entrant mode; preserve the thread-local re-entrant counts (L83). Add a
regression test proving nested acquire/release keeps the correct count.

### T023 — Migrate verdict_commit_queue.py (preserve test double)
Replace `filelock.FileLock` (L103) via the primitive's supported injection seam
so the existing test double (L123-124) still works. Verify the queue's mutual
exclusion behaviour is unchanged.

### T024 — Migrate auth/secure_storage/file_fallback.py
Replace `FileLock(..., timeout=10)` (L229/267/289) with the canonical primitive,
`blocking=True, timeout_s=10`. Security-sensitive — keep the same failure mode on
timeout.

### T025 — Migrate zeitgeist_client credentials + outbox_approval
Replace `filelock.FileLock` (credentials L104; outbox_approval L102) with the
canonical primitive; preserve the "one lock per module" `_locked()` helper shape.

### T026 — Retire filelock + close the gate + cross-process proof
- **Red-first cross-process parity FIRST** (post-tasks squad N-1): before removing
  `filelock`, author a subprocess-contention + blocking-timeout test that
  exercises the stdlib primitive against the retired `filelock` behaviour on both
  OS semantics (simulate Windows mandatory-lock). This test existing and passing
  is the evidence that licenses removal; if it CANNOT pass, it is the evidence
  that licenses the deferral seam — the deferral must not be taken on a bare
  assertion.
- Remove `filelock>=3.13.0` from `pyproject.toml` (L84) — out-of-map edit on
  WP03's `pyproject.toml`, one-line rationale — and refresh `uv.lock`.
- Shrink WP05's **per-WP exemption file** `tests/architectural/_exemptions/lock-ban-wp05.txt`
  to **empty** (post-tasks squad S-2; do NOT edit WP04's file). With WP04's file
  also empty, the lock gate allowlist is empty overall.
- **Deferral seam (A-01)** — only with the failing-parity test as evidence: revert
  the filelock removal for the affected site(s), keep them in `lock-ban-wp05.txt`,
  and record a tracked follow-up sub-issue that **must exist** (URL into the PR
  body + design-decisions tracer, per SC-005) — the mission still ships the stdlib
  families + gate. **Run WP05 AFTER WP04** (the orchestrator sequences them) so
  the two exemption-file/pyproject edits never race.

## Branch Strategy

Planning base and merge target: `feat/cross-os-primitive-unification`. Lane
worktree per `lanes.json`; sync the lane `.venv` (`uv sync --frozen --all-extras`).

## Definition of Done (full scope)

- No `filelock` import in owned files; removed from `pyproject.toml` + `uv.lock`.
- Re-entrancy (status/locking) + test double (verdict queue) + timeout (auth)
  preserved, each with a focused test.
- Cross-process + blocking-timeout parity proven on simulated Windows semantics.
- Lock gate allowlist empty (or exactly the deferred sites + a tracked sub-issue).
- `ruff`/format clean; complexity ≤15.

## Risks (highest in the mission)

- **Silent lock-semantics divergence** (mandatory-vs-advisory, no-dir-flock,
  blocking-timeout): the reason this is the deferral seam. Prove parity with
  red-first cross-process tests simulating Windows; do not trust Windows CI alone.
- **Re-entrancy / test-double regression**: naive migration drops both — use the
  primitive's re-entrant mode and injection seam.
- **zeitgeist_client**: local client code only; do not touch upstream-authored surface.

## Reviewer guidance (reviewer-renata, opus)

Confirm: every `filelock` usage gone; re-entrancy + test double + timeout each
have a proving test; cross-process parity genuinely simulates mandatory-lock
semantics; if the deferral seam is taken, the follow-up sub-issue exists and the
gate allowlist matches exactly the deferred sites.
