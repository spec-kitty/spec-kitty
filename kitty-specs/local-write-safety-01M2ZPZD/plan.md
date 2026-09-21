# Implementation Plan: Local Write-Safety Hardening

**Branch**: `fix/local-write-safety` | **Date**: 2026-09-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/local-write-safety-01M2ZPZD/spec.md`

## Summary

Close a family of local write-safety defects across seven tickets by hardening **one shared foundation** and reusing it everywhere: (1) make the canonical lock authority (`src/kernel/locks.py`) symlink-safe and factor a canonical no-follow-open helper into `kernel/`; (2) relocate world-shared predictable temp paths (cold-install sentinel, prompt temp dir) under the per-user runtime root `~/.spec-kitty` (`0700`); (3) serialize the decisions index read-modify-write at the service level and add an event-log→index reconciler; (4) make `spec-kitty init` back up operator-authored `.kittify/` content at every destructive site instead of deleting it; (5) close the credential "0600-by-construction" class on both transports; (6) route the last hand-rolled lock through the canonical authority. The technical spine: **one canonical no-follow module hoisted into `kernel/`, consumed by `kernel.locks` and the four in-scope defect write sites** (credentials, mission_state lock, prompt temp, cold-install sentinel). This mission does **not** convert the ~7 pre-existing already-correct hand-rolled `O_NOFOLLOW` sites elsewhere (Non-Goal; a codebase-wide ban-gate is a separate deferred item).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: stdlib `os`/`fcntl` (locking, low-level opens); `typer`+`rich` (CLI surface for the doctor reconciler). **No new third-party dependencies** — supply-chain posture: nothing added/upgraded/removed (see research.md §Supply-Chain).
**Storage**: filesystem only — append-only JSONL event log (`status.events.jsonl`, `decisions/…`), JSON index (`decisions/index.json`), the `.kittify/` tree, and per-user `~/.spec-kitty` locks/sentinels/credentials. No database.
**Testing**: pytest with `pytest-xdist`; **per-worker HOME isolation is mandatory** — all relocated-path and symlink-plant tests use the isolated HOME, never the real `~/.spec-kitty`.
**Target Platform**: POSIX (Linux/macOS) primary; Windows safe-degrade (`O_NOFOLLOW` `getattr`-guarded to `0`).
**Project Type**: single (Python CLI toolkit; enforced module chain `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`).
**Performance Goals**: N/A — correctness/safety mission; added lock/no-follow overhead on the affected paths is negligible and off any hot path.
**Constraints**: C-001 canonical locking authority (no new hand-rolled primitives); C-003 no `O_EXCL` on the shared lock (breaks re-acquisition); C-004 one canonical `kernel` no-follow helper; C-005 reuse `kernel.locks` parent-chmod for `~/.spec-kitty` `0700`; C-006 keep init backup vocabulary distinct from the template-render transactional swap.
**Scale/Scope**: 7 tickets → 6 work packages → ~8 source modules; blast radius of WP01 spans all 13 `kernel.locks` consumers.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Charter present at `.kittify/charter/charter.md` — evaluated:

- **Single canonical authority** ✅ — the mission *reinforces* it: all locking routes through `kernel.locks`; the no-follow primitive becomes one canonical `kernel` helper rather than per-site copies; the last hand-rolled lock (#4811) is retired into the authority. Directly serves DIRECTIVE_044.
- **Architectural alignment** ✅ / ⚠ layering note — the no-follow helper **must live in `kernel/`** (not `specify_cli.core.no_follow`) so `kernel.locks` can consume it without violating the `kernel ↛ specify_cli` import direction (`tests/architectural/test_layer_rules.py`). WP01 hoists the primitive into `kernel/`; `specify_cli.core.no_follow` becomes a thin re-export or is repointed. This is the load-bearing structural decision (see research.md D1).
- **DDD + tiered rigour** ✅ — security/data-integrity surfaces are tier-1; red-first tests required (see below).
- **ATDD-first / red-first** ✅ — every WP ships a red-first regression: symlink-plant proves bytes-intact+refuse; concurrency proof is barrier-synchronized and fails without the fix; init backup proves survival; reconciler heals a seeded corpus.
- **Terminology adherence** ✅ — Mission (not Feature) throughout.
- **Architectural gate discipline** ✅ — WP01 must keep `tests/architectural/test_lock_primitive_ban.py` and `test_layer_rules.py` green; run the full lock-consumer blast radius.

No unjustified violations → **PASS**. Complexity Tracking below is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/local-write-safety-01M2ZPZD/
├── plan.md              # This file
├── research.md          # Phase 0 — design decisions + adversarial evidence
├── data-model.md        # Phase 1 — entities/invariants (lock, index vs log, .kittify, runtime root)
├── quickstart.md        # Phase 1 — how to verify each fix locally
├── contracts/           # Phase 1 — no-follow helper contract + decisions-doctor subcommand contract
└── tasks.md             # Phase 2 (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/kernel/
├── locks.py                 # WP01: O_NOFOLLOW in _LockCore.open_fd + force_release; consume kernel no-follow helper
└── no_follow.py             # WP01: NEW canonical no-follow-open primitive (hoisted; kernel-layer)

src/specify_cli/
├── core/no_follow.py        # WP01: repoint to kernel helper (thin re-export; no behavior fork)
├── runtime/asset_preparation.py   # WP01b: cold-install sentinel → ~/.spec-kitty (0700) via machine_file_lock
├── runtime/next/_tmp_namespace.py # WP06: prompt temp dir → per-user root, no-follow, non-world-readable (#4721)
├── decisions/store.py        # WP02: index RMW under lock (sidecar index.json.lock)
├── decisions/service.py      # WP02: lock spans service-level critical section (open/resolve)
├── cli/commands/_decisions_doctor.py   # WP02: NEW reconciler subcommand (mirrors _mission_state_doctor.py)
├── cli/commands/init.py      # WP03: broaden idempotency gate; back-up-then-proceed at every destructive site
├── template/manager.py       # WP03: non-destructive copy (copy_package_tree + copy_specify_base_from_local)
├── migration/mission_state.py# WP04: hand-rolled lock → kernel.locks (post-#4813 base)
├── zeitgeist_client/credentials.py  # WP05: no-follow + 0600-by-construction
└── tracker/credentials.py    # WP05: 0600-by-construction (drop 0644-then-chmod) (#4760)

tests/
├── unit/ status/ cli/ decisions/ integration/ architectural/   # per-WP red-first coverage
```

**Structure Decision**: single-project Python layout. The only structural change is the **new `src/kernel/no_follow.py`** (canonical helper at the kernel layer) plus a new `_decisions_doctor.py` CLI surface; everything else is in-place hardening of existing modules.

## Complexity Tracking

*No Constitution Check violations — table intentionally empty.*

## Parallel Work Analysis

### Dependency Graph

```
                        ┌────────────────────────────────────────────┐
Foundation (land first) │ WP01  #4756  kernel no-follow helper +      │
                        │       O_NOFOLLOW in open_fd & force_release │
                        │       + Windows-noop. FULL lock-consumer    │
                        │       blast-radius + ban-gate + layer tests │
                        └───────┬───────────────┬───────────┬────────┘
                                │ (hard: needs   │           │
                                │  hardened prim) │           │
        ┌───────────────────────┼────────────────┼───────────┼─────────────┐
        ▼                       ▼                ▼           ▼             ▼
   WP01b #4756           WP02 #4757        WP04 #4811   WP05 #4812     WP06 #4721
   sentinel →            decisions RMW     mission_st.  +#4760 cred    prompt temp
   ~/.spec-kitty         lock + reconciler lock → kernel write-safety  per-user +
   (0700)                + doctor cmd                                  no-follow

WP03 #4759 (init backup-then-proceed) — INDEPENDENT, no lock/kernel dep, fully parallel from day 1.

External gate (PR #4813, not yet merged to main):
  • WP04 — HARD: shares migration/mission_state.py → base on post-#4813 main.
  • WP02 doctor surface — SOFT: mirror _mission_state_doctor.py; the store lock + reconciler CORE
    share no file with #4813 and may proceed now.
```

### Work Distribution

- **Sequential (foundation)**: WP01 lands first and alone — it hoists the whole `core/no_follow.py` module (6 symbols, `NoFollowPathError` identity preserved) into `kernel/no_follow.py`, mutates the shared `kernel.locks` primitive (13 consumers inherit the change), and repoints `core/no_follow.py` as a re-export. A regression here reds the whole lock surface AND the no-follow importers, so its acceptance runs **both** blast radii: the 13 `kernel.locks` consumers **and** the 11 `core.no_follow` importers, plus the ban-gate and layer tests.
- **Parallel after WP01**: WP01b, WP02 (core), WP05, WP06 — disjoint write-scopes, one lane each.
- **Parallel from day 1**: WP03 (init) — touches no locking.
- **Externally gated**: WP04 (hard on #4813); WP02's doctor subcommand (soft-aligns to #4813).

### Agent assignments (write-scope isolation — lanes collapse by write-scope, not dependency)

| WP | Owns (write-scope) | Depends on |
|----|--------------------|------------|
| WP01 | `kernel/locks.py`, `kernel/no_follow.py`, `specify_cli/core/no_follow.py` | — |
| WP01b | `runtime/asset_preparation.py` | WP01 |
| WP02 | `decisions/store.py`, `decisions/service.py`, `cli/commands/_decisions_doctor.py` | WP01 (hard); #4813 (soft, doctor only) |
| WP03 | `cli/commands/init.py`, `template/manager.py` | — |
| WP04 | `migration/mission_state.py` | WP01 (hard); #4813 (hard) |
| WP05 | `zeitgeist_client/credentials.py`, `tracker/credentials.py` | WP01 (helper) — also retires zeitgeist's hand-rolled 3-level 0700 ladder (`:220-224`) into the canonical authority (single owner of `~/.spec-kitty`, FR-011/C-005) |
| WP06 | `runtime/next/_tmp_namespace.py` | WP01 (helper) |

No two WPs write the same file → all viable as separate lanes.

### Coordination Points

- **After WP01 merges to the mission branch**: unblock WP02/WP04/WP05/WP06 rebases so they pick up the hardened primitive + helper.
- **#4813 watch**: before WP04 leaves draft, confirm #4813 merged to `main` and rebase WP04's base; align WP02's `_decisions_doctor.py` to the merged `_mission_state_doctor.py` shape.
- **Integration**: a cross-WP test asserts the whole no-follow surface (SC-001 per path) after all lanes land.
