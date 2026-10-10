# Tasks: Destructive ops never delete the only copy

**Mission**: `destructive-residue-context-01M4KBPS` · **Branch**: `fix/5965-5966-destructive-residue-context` · **Issues**: #5965, #5966

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | #5965 reproduction through move-task and consolidate | WP01 | |
| T002 | #5966 reproduction through consolidate --abort | WP01 | [P] |
| T003 | Prove red for the right reason | WP01 | |
| T004 | Mark and commit | WP01 | |
| T005 | CheckoutRole and ResidueContext | WP02 | |
| T006 | is_disposable_residue | WP02 | |
| T007 | Guard and ref-advance accept context | WP02 | |
| T008 | New guard entry points | WP02 | |
| T009 | kernel.tree_removal.remove_tool_owned_tree | WP02 | [P] |
| T010 | Guard unit tests | WP02 | |
| T011 | Exactly-one-of contract tests | WP02 | |
| T012 | Design notes | WP02 | |
| T013 | Rollback resync/restore with context | WP03 | |
| T014 | Coordination teardown with coordination-role context | WP03 | |
| T015 | Stop swallowing the refusal; skip branch delete | WP03 | |
| T016 | Exit without rollback; record state | WP03 | |
| T017 | --resume completes a refused teardown | WP03 | |
| T018 | orchestrator-api, --abort, entry preflight | WP03 | |
| T019 | Tests | WP03 | |
| T020 | resume_recovery and git_probes | WP04 | |
| T021 | Scratch worktrees | WP04 | |
| T022 | merge --abort sites | WP04 | |
| T023 | Residual is_residue callers | WP04 | |
| T024 | Tests | WP04 | |
| T025 | Blast radius | WP04 | |
| T026 | worktree_allocator | WP05 | |
| T027 | Mission-creation rollback and branch deletes | WP05 | |
| T028 | mission_type.py | WP09 | |
| T029 | core/vcs/git.py | WP09 | |
| T030 | doctor_husks, core/worktree, coord_seed | WP09 | |
| T031 | charter_packs git_source | WP09 | |
| T032 | Tests and blast radius | WP05 | |
| T033 | charter_packs snapshot and template_render | WP06 | |
| T034 | skills/catalog | WP06 | |
| T035 | template | WP06 | |
| T036 | runtime bridge and charter pack assembler | WP06 | |
| T037 | Tests and blast radius | WP06 | |
| T038 | Upgrade migrations | WP07 | |
| T039 | migration/runner.py | WP07 | |
| T040 | init.py and runtime/merge.py | WP07 | |
| T041 | core/utils.safe_remove | WP07 | |
| T042 | Tests and blast radius | WP07 | |
| T043 | Widen the patterns | WP08 | |
| T044 | rmtree AST check | WP08 | |
| T045 | Empty the allowlist | WP08 | |
| T046 | Retire is_residue | WP08 | |
| T047 | Transitional repros and changelog | WP08 | |
| T048 | WP09 tests and blast radius | WP09 | |

## Phase 1 — Red-first

### WP01 — Red-first reproductions for #5965 and #5966 (`tasks/WP01-red-first-reproductions.md`)
- **Goal**: two issue-pinned reproductions, red for the reported reason through real entry points. **Priority**: P1. **Independent test**: the two files fail on the base with the file-survival assertion.
- **Dependencies**: none.
T001 #5965 reproduction through move-task and consolidate (WP01)
T002 #5966 reproduction through consolidate --abort (WP01)
T003 Prove red for the right reason (WP01)
T004 Mark and commit (WP01)
- **Risks**: fixture planting files where the real flow never writes them.

## Phase 2 — Foundation

### WP02 — Context-aware disposability and the guard API (`tasks/WP02-disposability-and-guard-api.md`)
- **Goal**: `ResidueContext`, `is_disposable_residue`, guard entry points for every destructive op, kernel tool-owned tree removal. **Priority**: P1.
- **Dependencies**: WP01.
T005 CheckoutRole and ResidueContext (WP02)
T006 is_disposable_residue (WP02)
T007 Guard and ref-advance accept context (WP02)
T008 New guard entry points (WP02)
T009 kernel.tree_removal.remove_tool_owned_tree (WP02)
T010 Guard unit tests (WP02)
T011 Exactly-one-of contract tests (WP02)
T012 Design notes (WP02)
- **Risks**: duplicating the partition rule (C-001); a destructive default on missing context (C-002).

## Phase 3 — Wiring

### WP03 — Consolidate, abort and teardown wiring (`tasks/WP03-consolidate-abort-teardown-wiring.md`)
- **Goal**: both reproductions pass; refused teardown fails safely and resumes. **Priority**: P1.
- **Dependencies**: WP02.
T013 Rollback resync/restore with context (WP03)
T014 Coordination teardown with coordination-role context (WP03)
T015 Stop swallowing the refusal; skip branch delete (WP03)
T016 Exit without rollback; record state (WP03)
T017 --resume completes a refused teardown (WP03)
T018 orchestrator-api, --abort, entry preflight (WP03)
T019 Tests (WP03)
- **Risks**: rolling back a verified landing; half-torn coordination triple; projection re-entrancy on resume.

## Phase 4 — Routing (WP04–WP07 and WP09 run in parallel after WP02)

### WP04 — Consolidation-family sites (`tasks/WP04-route-consolidation-family-sites.md`)
- **Dependencies**: WP02.
T020 resume_recovery and git_probes (WP04)
T021 Scratch worktrees (WP04)
T022 merge --abort sites (WP04)
T023 Residual is_residue callers (WP04)
T024 Tests (WP04)
T025 Blast radius (WP04)

### WP05 — Lane allocation and Mission-creation sites (`tasks/WP05-route-lanes-and-creation-sites.md`)
- **Dependencies**: WP02.
T026 worktree_allocator (WP05)
T027 Mission-creation rollback and branch deletes (WP05)
T032 Tests and blast radius (WP05)

### WP09 — Mission-type, VCS adapter, husk, worktree-memory, coordination-seed, charter-pack-source sites (`tasks/WP09-route-mission-type-vcs-husk-pack-sites.md`)
- **Dependencies**: WP02.
T028 mission_type.py (WP09)
T029 core/vcs/git.py (WP09)
T030 doctor_husks, core/worktree, coord_seed (WP09)
T031 charter_packs git_source (WP09)
T048 Tests and blast radius (WP09)

### WP06 — Tool-owned trees: charter packs, skills, templates, runtime, charter (`tasks/WP06-route-tool-owned-trees-runtime-charter.md`)
- **Dependencies**: WP02.
T033 charter_packs snapshot and template_render (WP06)
T034 skills/catalog (WP06)
T035 template (WP06)
T036 runtime bridge and charter pack assembler (WP06)
T037 Tests and blast radius (WP06)

### WP07 — Tool-owned trees: migrations, runner, init, runtime merge, utils (`tasks/WP07-route-tool-owned-trees-migrations-init.md`)
- **Dependencies**: WP02.
T038 Upgrade migrations (WP07)
T039 migration/runner.py (WP07)
T040 init.py and runtime/merge.py (WP07)
T041 core/utils.safe_remove (WP07)
T042 Tests and blast radius (WP07)

## Phase 5 — Gate

### WP08 — Widen and drain the routing gate (`tasks/WP08-widen-and-drain-routing-gate.md`)
- **Dependencies**: WP03, WP04, WP05, WP06, WP07, WP09.
T043 Widen the patterns (WP08)
T044 rmtree AST check (WP08)
T045 Empty the allowlist (WP08)
T046 Retire is_residue (WP08)
T047 Transitional repros and changelog (WP08)

## MVP
WP01 → WP02 → WP03 closes both reported bugs; WP04–WP08 close the defect class.
