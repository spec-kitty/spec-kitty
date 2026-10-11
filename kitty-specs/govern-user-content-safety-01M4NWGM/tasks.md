# Tasks: Governed ops never destroy or mis-report user content

**Mission**: `govern-user-content-safety-01M4NWGM` · **Branch**: `fix/5964-5434-4796-govern-user-content` · **Issues**: #5964, #5434, #4796

Three independent seams, one red-first baseline lane plus one fix lane per issue. No file overlap across work packages.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | #5964 red repro: team `.agents/skills` survives migration + upgrade commit | WP01 | [P] |
| T002 | #5434 red repro: lane worktree with leftover `.spec-kitty/review-lock.json` reuse/recovery | WP01 | [P] |
| T003 | #4796 red repro: orchestrator merge timing — no mutation/push on dirty-worktree refusal | WP01 | [P] |
| T004 | Prove all three red for the right reason; mark + commit | WP01 | |
| T005 | Scope `_untrack_tracked_paths` to spec-kitty-projected paths (manifest + `spec-kitty.*`) | WP02 | |
| T006 | Defense-in-depth: `autocommit.migration_index_untracks` drops non-projected `.agents/skills` deletions | WP02 | |
| T007 | Unit test: ownership selection recognizes pack + command skills, excludes team content | WP02 | |
| T008 | Green the #5964 repro; blast-radius tests | WP02 | |
| T009 | Call `exclude_from_git_index(repo_root, [".spec-kitty/"])` at the allocator choke point | WP03 | |
| T010 | New migration `m_4_0_0rc8_exclude_spec_kitty` modeled on `m_0_13_1_exclude_worktrees` | WP03 | |
| T011 | Delete dead `core/worktree.py::_ensure_spec_kitty_exclude` + 2 call sites; drop allowlist rows | WP03 | |
| T012 | Migration test + remove the wrong-location integration test; green the #5434 repro | WP03 | |
| T013 | Hoist pre-mutation preflight into `_execute_lane_merge` before first mutation | WP04 | |
| T014 | Gate on resolved retention; keep `PREFLIGHT_FAILED` envelope truthful; green the #4796 repro | WP04 | |

## Phase 1 — Red-first baseline

### WP01 — Red-first reproductions for #5964, #5434, #4796 (`tasks/WP01-red-first-reproductions.md`)
- **Goal**: three issue-pinned reproductions, each red for the reported reason through the real code path, asserting on observable state (`git ls-files`, `git status --porcelain`, pre/post refs). **Priority**: P1. **Independent test**: the three new files fail on the mission base for the right reason.
- **Dependencies**: none.
T001 #5964 red repro (WP01)
T002 #5434 red repro (WP01)
T003 #4796 red repro (WP01)
T004 Prove red + commit (WP01)
- **Risks**: planting fixtures where the real flow never writes; the dogfood `.gitignore` masking #5434 (build a consumer-like repo).

## Phase 2 — Fixes (each depends on WP01)

### WP02 — #5964 upgrade untrack scoped to projected paths (`tasks/WP02-5964-upgrade-untrack-ownership.md`)
- **Goal**: `spec-kitty upgrade` untracks only spec-kitty-projected `.agents/skills/` paths; team content stays tracked and absent from the upgrade commit's deletions. **Priority**: P1. **Independent test**: WP01's #5964 repro turns green; a pack skill and a command skill are both still untracked.
- **Dependencies**: WP01.
T005 Scope `_untrack_tracked_paths` (WP02)
T006 Defense-in-depth autocommit filter (WP02)
T007 Ownership-selection unit test (WP02)
T008 Green repro + blast radius (WP02)
- **Risks**: conflating `skills-manifest.json` (pack) and `command-skills-manifest.json` (command); migration-determinism departure (reads live manifest state for the untrack decision only).

### WP03 — #5434 lane worktree `.spec-kitty/` exclude + migration + dead-writer removal (`tasks/WP03-5434-worktree-exclude.md`)
- **Goal**: lane worktrees honour a common-dir `.spec-kitty/` exclude on all allocation routes; backfill migration for existing projects; delete the dead per-worktree writer. **Priority**: P1. **Independent test**: WP01's #5434 repro turns green (clean `git status --porcelain`, no `DirtyWorktreeError`); migration idempotent.
- **Dependencies**: WP01.
T009 Allocator choke-point exclude (WP03)
T010 New backfill migration (WP03)
T011 Delete dead writer + allowlist rows (WP03)
T012 Migration test + remove wrong-location test; green repro (WP03)
- **Risks**: `exclude_from_git_index` no-op on a worktree path / absent exclude file (assert main-repo root; `can_apply` guards).

### WP04 — #4796 orchestrator-api pre-mutation preflight parity (`tasks/WP04-4796-orchestrator-preflight.md`)
- **Goal**: `orchestrator_api/consolidation.py::_execute_lane_merge` runs the shared pre-mutation safety preflight before any lane consolidation/integration/push; a dirty lane worktree refuses `PREFLIGHT_FAILED` with nothing mutated/pushed. **Priority**: P1. **Independent test**: WP01's #4796 timing repro turns green (target ref unchanged, WPs unstamped, no push on refusal); a clean worktree merges unchanged.
- **Dependencies**: WP01.
T013 Hoist preflight before first mutation (WP04)
T014 Gate on retention; truthful envelope; green repro (WP04)
- **Risks**: standing up a real-repo orchestrator merge (model fixture on `test_mission_branch_moved_error_code.py`).
