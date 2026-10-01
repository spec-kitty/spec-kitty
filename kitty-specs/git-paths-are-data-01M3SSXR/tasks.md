# Work Packages: Git paths are data, not text

**Inputs**: `kitty-specs/git-paths-are-data-01M3SSXR/` — spec.md, plan.md, research.md, data-model.md, contracts/kernel-git-api.md, quickstart.md
**Tests**: required (red-first P0 repros, unit tests for the kernel owner, an empty-allowlist gate).

Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | `kernel/git/runner.py`: run_git, GitResult, GitCommandError, decode_path | WP01 | |
| T002 | `kernel/git/paths.py`: GitPath value type | WP01 | [P] |
| T003 | `kernel/git/listing.py`: status_entries + StatusEntry (NUL-safe, renames) | WP01 | |
| T004 | `kernel/git/listing.py`: tree/changed/commit/log/tracked/index queries | WP01 | |
| T005 | Unit tests from real git output (quoted, non-ASCII, ` -> `, renames, failures, literal pathspecs) | WP01 | |
| T006 | kernel README + no-destructive-literal test | WP01 | [P] |
| T007 | Red-first `@pytest.mark.regression` repros for #5392 and #5400 through `advance_branch_ref` | WP02 | |
| T008 | Carry PR #5437 commit (`cherry-pick -x`) | WP02 | |
| T009 | Campsite: route `_target_tree_paths` / `_dirty_entries` listing through kernel queries | WP02 | |
| T010 | Obstruction rule on `GitPath.overlaps`; typed obstruction verdict; message rendering | WP02 | |
| T011 | Entry-point coverage: reset-obstruction probe + guarded worktree removal; half-by-half proof; convert repros | WP02 | |
| T012 | Re-base `core/vcs/git.py` helpers + GitVCS listing methods on kernel queries; FR-013 classification | WP03 | |
| T013 | Migrate `consolidation/git_probes.py`, `bookkeeping_projection.py` | WP03 | |
| T014 | Migrate `coordination/commit_router.py`, `surface_resolver.py`, `transaction.py` | WP03 | |
| T015 | Tests for migrated merge-seam sites (quoted path fixtures) | WP03 | |
| T016 | Migrate `git/commit_helpers.py`, `git/report_transaction.py`, `git/sparse_checkout_remediation.py` | WP04 | |
| T017 | Migrate `lanes/auto_rebase.py`, `lanes/consolidation.py`, `lanes/for_review_gate.py` | WP04 | |
| T018 | Migrate `lanes/worktree_allocator.py` + `lanes/checkout_occupancy.py` parser | WP04 | |
| T019 | Migrate `live_work/watcher.py`, `gitignore_manager.py` | WP04 | |
| T020 | Tests for WP04 sites | WP04 | |
| T021 | Migrate `agent/tasks_move_task.py` (incl. `.strip('"')` half-decoder) | WP05 | |
| T022 | Migrate `agent/tasks_parsing_validation.py`, `agent/tasks_mark_status.py` | WP05 | |
| T023 | Migrate `agent/mission_finalize.py`, `mission_setup_plan.py`, `mission_record_analysis.py`, `mission_repair.py` | WP05 | |
| T024 | Migrate `agent/workflow.py`, `agent/workflow_executor.py` | WP05 | |
| T025 | Tests for WP05 sites | WP05 | |
| T026 | Migrate `safe_commit_cmd.py`, `implement_cores.py` | WP06 | |
| T027 | Migrate `accept.py`, `acceptance/__init__.py`, `mission_type.py`, `charter_bundle.py` | WP06 | |
| T028 | Migrate `_coordination_doctor.py`, `review/_dead_code.py`, `agent_tasks_ports.py`, `task_utils/support.py` | WP06 | |
| T029 | Tests for WP06 sites | WP06 | |
| T030 | Migrate `policy/commit_guard_hook.py`, `bulk_edit/gate.py` (fail-open classification checks) | WP07 | |
| T031 | Migrate `post_merge/stale_assertions.py`, `post_merge/retrospective_terminus.py`, `charter_runtime/preflight/runner.py` | WP07 | |
| T032 | Migrate `core/mission_creation.py`, `missions/_substantive.py`, `migration/runner.py`, `upgrade/autocommit.py` | WP07 | |
| T033 | Migrate the three upgrade migrations (behaviour-identical) | WP07 | |
| T034 | Tests for WP07 sites | WP07 | |
| T035 | `tests/architectural/test_git_path_listing_owner.py`: rule, floor, planted hit, worktree negative control, empty allowlist | WP08 | |
| T036 | Fold T019's porcelain scan into the new gate; shrink T019's registry | WP08 | |
| T037 | Run named gates + record base census N and close count 0 | WP08 | |
| T038 | ADR `docs/adr/4.x/2026-09-30-1-allowlist-ratchets-are-priced-debt.md` | WP09 | [P] |
| T039 | Charter: standing order 5 + Burn-down Policy amendment | WP09 | |
| T040 | Packs: built-in ratchet tactic caveat, internal CI-cost rationale, regenerate graph | WP09 | |
| T041 | Docs index/freshness + terminology guard; file the plain-runner follow-up issue | WP09 | |

---

## Work Package WP01: Kernel git owner (Priority: P0)

**Goal**: one runner, NUL-safe listing, `GitPath`, typed entries and queries in `src/kernel/git/`.
**Independent Test**: `pytest tests/kernel/test_git_*.py` green against real git repos with spaced, non-ASCII and ` -> ` names.
**Prompt**: `tasks/WP01-kernel-git-owner.md`
**Requirement Refs**: FR-003, FR-004, FR-005, FR-006, FR-014, NFR-002, NFR-003, NFR-004, C-001, C-007, C-008

### Included Subtasks

T001 runner (WP01)
T002 GitPath (WP01)
T003 status_entries (WP01)
T004 other listing queries (WP01)
T005 unit tests (WP01)
T006 README + no-destructive-literal test (WP01)

### Dependencies

- None. Estimated prompt ~350 lines.

---

## Work Package WP02: Branch advance on the owner — P0 fix for #5392/#5400 (Priority: P0)

**Goal**: consolidate refuses on quoted-path and ancestor collisions; separately landable.
**Independent Test**: regression tests red on base, green after; `tests/git/` + T018/T019/NFR-004/AC-B3 gates green.
**Prompt**: `tasks/WP02-ref-advance-p0.md`
**Requirement Refs**: FR-001, FR-002, FR-007, C-002, C-003, C-009

### Included Subtasks

T007 red-first repros (WP02)
T008 carry PR #5437 (WP02)
T009 campsite listing through kernel (WP02)
T010 GitPath obstruction rule (WP02)
T011 entry-point coverage + half-by-half (WP02)

### Dependencies

- Depends on WP01. Estimated prompt ~330 lines.

---

## Work Package WP03: Merge-seam call sites (Priority: P1)

**Goal**: `core/vcs/git.py`, `consolidation/`, `coordination/` listing sites on kernel queries.
**Prompt**: `tasks/WP03-merge-seam-sites.md`
**Requirement Refs**: FR-008, FR-013, NFR-001, NFR-005

T012 core/vcs helpers (WP03)
T013 consolidation (WP03)
T014 coordination (WP03)
T015 tests (WP03)

### Dependencies

- Depends on WP01. Parallel with WP04–WP07.

---

## Work Package WP04: git/, lanes/ and watcher call sites (Priority: P1)

**Prompt**: `tasks/WP04-git-lanes-sites.md`
**Requirement Refs**: FR-008, FR-013, NFR-001

T016 git/ modules (WP04)
T017 lanes merge helpers (WP04)
T018 worktree allocator + occupancy (WP04)
T019 watcher + gitignore manager (WP04)
T020 tests (WP04)

### Dependencies

- Depends on WP01.

---

## Work Package WP05: agent command call sites (Priority: P1)

**Prompt**: `tasks/WP05-agent-command-sites.md`
**Requirement Refs**: FR-008, NFR-001

T021 tasks_move_task (WP05)
T022 tasks parsing/mark-status (WP05)
T023 mission_* commands (WP05)
T024 workflow commands (WP05)
T025 tests (WP05)

### Dependencies

- Depends on WP01.

---

## Work Package WP06: other CLI command call sites (Priority: P1)

**Prompt**: `tasks/WP06-cli-command-sites.md`
**Requirement Refs**: FR-008, NFR-001

T026 safe_commit + implement (WP06)
T027 accept/acceptance/mission_type/charter_bundle (WP06)
T028 doctors, dead-code, ports, support (WP06)
T029 tests (WP06)

### Dependencies

- Depends on WP01.

---

## Work Package WP07: policy, post-merge, migration and upgrade call sites (Priority: P1)

**Prompt**: `tasks/WP07-policy-upgrade-sites.md`
**Requirement Refs**: FR-008, FR-013, NFR-001

T030 commit guard + bulk edit gate (WP07)
T031 post_merge + charter preflight (WP07)
T032 mission creation, substantive, migration runner, autocommit (WP07)
T033 upgrade migrations (WP07)
T034 tests (WP07)

### Dependencies

- Depends on WP01.

---

## Work Package WP08: Empty-allowlist class gate (Priority: P1)

**Prompt**: `tasks/WP08-class-gate.md`
**Requirement Refs**: FR-009, SC-002, SC-003

T035 gate (WP08)
T036 fold T019 porcelain scan (WP08)
T037 run named gates, record counts (WP08)

### Dependencies

- Depends on WP02, WP03, WP04, WP05, WP06, WP07.

---

## Work Package WP09: Ratchets are priced debt (Priority: P2)

**Prompt**: `tasks/WP09-ratchet-governance.md`
**Requirement Refs**: FR-010, FR-011, FR-012, SC-004, C-005

T038 ADR (WP09)
T039 charter amendment (WP09)
T040 packs + regenerate graph (WP09)
T041 docs checks + follow-up issue (WP09)

### Dependencies

- None. Parallel with everything.
