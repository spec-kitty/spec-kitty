# Tasks: Local Write-Safety Hardening

**Mission**: local-write-safety-01M2ZPZD | **Branch**: `fix/local-write-safety` | **Date**: 2026-09-20
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

7 work packages, 24 subtasks. WP01 is the foundation (kernel no-follow primitive); WP02/WP03/WP05/WP06/WP07 depend on it; WP04 is independent. WP05 additionally hard-gates on PR #4813 (shared `mission_state.py` — base on post-#4813 `main`); WP03's doctor surface soft-aligns to #4813.

## Subtask Index (reference table — not a tracking surface)

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Hoist whole `core/no_follow.py` (6 symbols) → `kernel/no_follow.py`; repoint core as re-export | WP01 | |
| T002 | Add `O_NOFOLLOW` to `kernel.locks` `open_fd` + `force_release` (no `O_EXCL`; Windows getattr-guard) | WP01 | |
| T003 | Red-first symlink-plant regression on the lock path (bytes intact + raises) | WP01 | |
| T004 | Run 11 `core.no_follow` importers + 13 `kernel.locks` consumers + ban-gate + layer tests green | WP01 | |
| T005 | Relocate cold-install sentinel → `~/.spec-kitty` (0700) via `machine_file_lock` parent-chmod | WP02 | |
| T006 | Red-first symlink-plant on the sentinel path (bytes intact + refuse) | WP02 | [P] |
| T007 | Assert sentinel resolves under `~/.spec-kitty` (isolated HOME), not `$TMPDIR`; dir 0700 | WP02 | [P] |
| T008 | Factor canonical `event → IndexEntry` fold (`decisions/index_fold.py`); share with forward path | WP03 | |
| T009 | Red-first I9 round-trip test: opened+resolved events serialize every IndexEntry field | WP03 | |
| T010 | Serialize service-level RMW under sidecar `index.json.lock` via `machine_file_lock` | WP03 | |
| T011 | Red-first barrier-synchronized 8-concurrent-open proof → index 8 == 8 events | WP03 | |
| T012 | `_decisions_doctor.py` reconciler (diagnose + `--repair`, no-op when agree); heal log=8/index=5 | WP03 | |
| T013 | Shared backup helper: move operator content → timestamped `.kittify/.backup-<ts>/`, collision-safe | WP04 | |
| T014 | Route every destructive site (manager.py ×N + init.py) through the backup helper | WP04 | |
| T015 | Broaden init "already initialized" gate beyond `config.yaml` (detect operator content) | WP04 | |
| T016 | Red-first per-site content-survival tests (missions/memory survive, backup reported) | WP04 | |
| T017 | Replace hand-rolled `_git_lock` in `mission_state.py` with `machine_file_lock` | WP05 | |
| T018 | Red-first: lock routes through canonical authority (ban-gate) + symlink-safe | WP05 | |
| T019 | tracker/credentials.py: `os.open(O_CREAT|O_EXCL,0600)` via helper (0600-by-construction) | WP06 | |
| T020 | zeitgeist credentials: add `O_NOFOLLOW`; retire hand-rolled 3-level 0700 ladder into authority | WP06 | |
| T021 | Red-first: both transports mode ≤0600 at all times + symlink-plant refused | WP06 | |
| T022 | Relocate prompt temp dir → `~/.spec-kitty`; no-follow open; non-world-readable | WP07 | |
| T023 | Red-first symlink-plant on prompt path refused + relocation asserted + not world-readable | WP07 | |
| T024 | Close #4721 DoS + info-disclosure facets (per-user isolation + 0600) | WP07 | |

Completion is event-sourced via `spec-kitty agent tasks mark-status <Txxx> --status done` — there are no checkboxes.

---

## WP01 — Kernel no-follow foundation (#4756a)  [FOUNDATION]
- **Goal**: One canonical no-follow module at the kernel layer; the shared lock primitive no longer follows symlinks. Everything else depends on this.
- **Priority**: P1 (highest) | **Prompt**: [tasks/WP01-kernel-no-follow-foundation.md](tasks/WP01-kernel-no-follow-foundation.md)
- **Independent test**: symlink-plant on a lock leaves victim bytes intact and raises; the 11 core.no_follow importers + 13 lock consumers + ban/layer gates stay green.
- **Subtasks**: T001, T002, T003, T004 | **Dependencies**: none | **Est.**: ~220 lines

## WP02 — Cold-install sentinel relocation (#4756b)
- **Goal**: Move the cold-install sentinel out of world-shared `$TMPDIR` into the per-user runtime root (0700).
- **Priority**: P1 | **Prompt**: [tasks/WP02-cold-install-sentinel-relocation.md](tasks/WP02-cold-install-sentinel-relocation.md)
- **Independent test**: sentinel resolves under `~/.spec-kitty` (isolated HOME); symlink-plant refused.
- **Subtasks**: T005, T006, T007 | **Dependencies**: WP01 | **Est.**: ~170 lines

## WP03 — Decisions RMW lock + reconciler (#4757)
- **Goal**: Serialize the decisions index read-modify-write at the service level; add an event-log→index reconciler behind one canonical fold.
- **Priority**: P1 | **Prompt**: [tasks/WP03-decisions-rmw-lock-reconciler.md](tasks/WP03-decisions-rmw-lock-reconciler.md)
- **Independent test**: barrier-synchronized 8 concurrent opens → index 8 == 8 events; seeded log=8/index=5 heals to 8.
- **Subtasks**: T008, T009, T010, T011, T012 | **Dependencies**: WP01 (hard); PR #4813 (soft — doctor surface only) | **Est.**: ~320 lines

## WP04 — Init backup-then-proceed (#4759)
- **Goal**: `spec-kitty init` backs up operator-authored `.kittify/` content at every destructive site instead of deleting it; broaden the idempotency gate.
- **Priority**: P2 | **Prompt**: [tasks/WP04-init-backup-then-proceed.md](tasks/WP04-init-backup-then-proceed.md)
- **Independent test**: at every destructive site, operator missions/memory survive (backed up, reported) with `config.yaml` absent.
- **Subtasks**: T013, T014, T015, T016 | **Dependencies**: none (fully parallel) | **Est.**: ~250 lines

## WP05 — mission_state lock canonical (#4811)
- **Goal**: Retire the last hand-rolled lock into the canonical authority; symlink-safe.
- **Priority**: P3 | **Prompt**: [tasks/WP05-mission-state-lock-canonical.md](tasks/WP05-mission-state-lock-canonical.md)
- **Independent test**: lock routes through `machine_file_lock` (ban-gate) and does not follow a symlink.
- **Subtasks**: T017, T018 | **Dependencies**: WP01 (hard); PR #4813 (hard — base on post-#4813 `main`) | **Est.**: ~150 lines

## WP06 — Credential write-safety (#4812 + #4760)
- **Goal**: Close the credential 0600-by-construction class on both transports; retire zeitgeist's competing 0700 ladder.
- **Priority**: P2 | **Prompt**: [tasks/WP06-credential-write-safety.md](tasks/WP06-credential-write-safety.md)
- **Independent test**: both transports create credentials at mode ≤0600 with no world-readable window; symlink-plant refused.
- **Subtasks**: T019, T020, T021 | **Dependencies**: WP01 | **Est.**: ~200 lines

## WP07 — Prompt temp per-user (#4721)
- **Goal**: Prompt temp dir under the per-user runtime root; no-follow; never world-readable (closes DoS + info-disclosure).
- **Priority**: P1 | **Prompt**: [tasks/WP07-prompt-temp-per-user.md](tasks/WP07-prompt-temp-per-user.md)
- **Independent test**: prompt dir resolves under `~/.spec-kitty`; symlink-plant refused; files not world-readable.
- **Subtasks**: T022, T023, T024 | **Dependencies**: WP01 | **Est.**: ~190 lines

---

## Execution notes
- **MVP / land-first**: WP01 (foundation). Merge it before rebasing WP02/WP03/WP05/WP06/WP07 so they inherit the hardened primitive + helper.
- **Parallel after WP01**: WP02, WP03 (core), WP06, WP07 — disjoint write-scopes, one lane each. WP04 runs from day 1.
- **External gate**: WP05 stays draft until PR #4813 merges to `main`; rebase its base then. WP03's `_decisions_doctor.py` aligns to the merged `_mission_state_doctor.py` shape.
- **Tests**: every relocated-path / symlink test uses the isolated per-worker HOME, never the real `~/.spec-kitty`.
