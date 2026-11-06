---
description: "Work packages for Mission lane-worktree-model-hardening-01M6QY1M (epic #7276)"
---

# Work Packages: Lane and worktree model hardening

**Inputs**: design documents in `kitty-specs/lane-worktree-model-hardening-01M6QY1M/` (spec.md, plan.md, research.md, data-model.md, contracts/, quickstart.md, decisions/)
**Prerequisites**: plan.md (Implementation Concern Map IC-01 to IC-18), spec.md (FR/NFR/C/SC), the 19 resolved Decision Moments (`spec-kitty agent decision list --mission lane-worktree-model-hardening-01M6QY1M`).

**Tests**: required. Charter C-011 (ATDD-first): every code work package commits its red-first acceptance tests BEFORE the implementation commit, through the pre-existing entry point (the real CLI or `orchestrator-api` verb) on real git fixtures. ADR work packages name confirmation tests instead.

**Organization**: one work package per implementation concern (WP01 = IC-01 ... WP16 = IC-16). IC-17 is split in three: WP17 code (command skills, stale-lane CLI message, skill-text guard, CLAUDE.md), WP18 docs pages and changelog fragments (`code_change`, owns only `docs/`), WP19 the open-packs patch (planning artifact; the kitty-specs ownership ban keeps it out of code WPs, and the planning lane may not depend on code lanes). IC-18 (added after `/spec-kitty.analyze` finding E1) is WP20.

**Branch contract**: planning base = merge target = `issue-7276-lane-worktree-hardening`. Execution lanes come from `lanes.json` after `finalize-tasks`; agents never pick a base branch.

**Prompt files**: each work package has a prompt in `tasks/`. This file is the high-level index; detail lives in the prompts.

## Subtask Format: `Txxx [P?] Description (WPxx)`

- **[P]** marks a subtask that is safe to run in parallel with its neighbours (different files).
- Subtasks are **reference rows**, not checkboxes. Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`; the reduced event-log snapshot is the only completion authority.

## External PR gates (owned outside this Mission)

| PR | What it is | Effect on this Mission |
|----|------------|------------------------|
| #6884 (`issue-6466-lane-status-shadow`, author Ivan-Melck) | lane root is never a status surface | NOT merged, conflicts, labelled taken-by-human. WP04 carries `_canonical_status_read_root` and its 9 tests forward as its FIRST commits with attribution: #6884's red-first test commit `942ff4aed9` alone first, then its fix `59bd93d6bd` and style `f404a0b240` (and optional `43f48eee8f`) as separate path-limited `-x` cherry-picks (charter C-011), then builds on it. |
| #7255 (`issue-7210-finalize-derived-pin`) | finalize derived pin, ADR `2026-10-04-5` Amendment 2026-11-05 | NOT merged. WP02 appends its ADR `2026-10-04-5` amendment as a NEW dated section at the end of the file (a rebase conflicts only there). WP14 rebases its finalize phases after it. |
| #7248 (`issue-7224-flat-fixture-single-branch`) | flat-fixture `single_branch` | NOT merged. WP11 rebases onto it once it lands and deliberately reverses its "single_branch is never stamped" fixture comment. |
| #7274 (`issue-7198-late-window-one-pass`, S10) | late-window one pass | NOT merged. WP15 shares `phase_teardown.py` / `run_state.py`; rebase onto it when it lands. WP07 rebases if consolidation neighbours conflict. |
| #7275 (`issue-7211-safe-landed-prune`, S4) | destructive guard + ADR `2026-11-06-1` | NOT merged. **WP16 is BLOCKED until #7275 merges into `main` and the topic branch is rebased.** WP16 is out of the first PR cut. WP15 does not wait (port only). See the WP16 exit rule below. |
| open-packs PR #128 | the S11 pack doctrine | Made ready and ungated by the operator, with the S11 doctrine already applied. **WP19 is canceled at implement time** with that rationale; this Mission does not bump the core pack pin; no WP depends on WP19. |

---

## Phase 1 - Governing ADRs (planning artifacts)

## Work Package WP01: ADR - one status read contract and restated ruling 3 (Priority: P1)

**Goal**: record the S1 read contract, reverse `coord-artifact-single-home-01M3V4BE#FR-017` / `#C-002`, record the FR-061 PRIMARY placement of default Missions, and amend ADR `2026-07-29-1` with the restated ruling 3 (Assert A' kept).
**Independent Test**: a reviewer maps each topology to exactly one declared read source in the ADR, and the ADR names the WP05 matrix test, the WP07 single-door gate and the WP09 every-route exclusion test as confirmation.
**Prompt**: `tasks/WP01-adr-status-read-contract.md`
**Requirement Refs**: FR-007, FR-046, FR-061, C-016

### Included Subtasks

T001 Draft `docs/adr/4.x/2026-11-06-2-one-status-read-contract.md` (Proposed): per-topology sources, normalization, typed ref errors (WP01)
T002 Record the explicit reversal of FR-017/C-002 and append an amendment section to `docs/adr/3.x/2026-06-19-1-coord-empty-surface-fallback.md` (WP01)
T003 Record the FR-061 PRIMARY placement change for `topology_source: default` (DM 01M6R0QJVPVZG2QT8MWQD4NXJR) (WP01)
T004 [P] Append the restated ruling 3 amendment to `docs/adr/3.x/2026-07-29-1-lane-base-recorded-planning-commit.md` keeping Assert A' (WP01)
T005 Confirmation-test section, cross-links, terminology guard and frontmatter validation (WP01)

### Dependencies

- None.

### Risks & Mitigations

- ADR number collision with other in-flight PRs: re-list `docs/adr/4.x/` before writing; #7275 already holds `2026-11-06-1`.

---

## Work Package WP02: ADR - topology settled once at first finalize, and S8 approval windows (Priority: P1)

**Goal**: record the #5100 item 2 reversal, the size rule, deferred materialization, the provisional representation, the PRIMARY placement rule, decide-once, compensation and C-010; amend ADR `2026-06-22-1` D2; append the per-WP window amendment to ADR `2026-10-04-5`.
**Independent Test**: the ADR states every FR-050 element and every FR-077 residual; the ADR `2026-10-04-5` amendment is the LAST section of the file.
**Prompt**: `tasks/WP02-adr-topology-settlement-and-s8-windows.md`
**Requirement Refs**: FR-050, FR-061, FR-077, C-010, C-011, C-016

### Included Subtasks

T006 Draft `docs/adr/4.x/2026-11-06-3-topology-is-settled-once-at-first-finalize.md` (Proposed): size rule, A-3 mapping, deferred materialization (WP02)
T007 Provisional representation, `topology_source`, `create_return_branch`, PRIMARY placement, decide-once, compensation, C-010 (WP02)
T008 [P] Append a D2 amendment section to `docs/adr/3.x/2026-06-22-1-mission-topology-ssot.md` (WP02)
T009 [P] Append a new dated amendment section at the END of `docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md` (per-WP windows, residuals) (WP02)
T010 Confirmation tests, cross-links, terminology guard, frontmatter validation (WP02)

### Dependencies

- None inside the Mission. External: #7255 touches the same ADR file; the amendment is appended as a new dated section so a rebase conflicts only at the end.

---

## Work Package WP03: ADR set - short-lived checkouts, cleanup amendment draft, worktree-free coordination write (Priority: P2)

**Goal**: amend ADR `2026-04-03-1` Core Decision 3 (FR-020), draft the ADR `2026-11-06-1` amendment for #7275 (FR-038), write the three Proposed core ADRs C-1/C-2/C-3 (FR-080 to FR-082), amend ADR `2026-10-22-1` D-6 with step 4a (FR-083), and link the spec-kitty-events ADR 0007/0008 drafts (FR-084).
**Independent Test**: SC-010: every ADR `2026-10-22-1` D-6 bullet maps to exactly one of the 5 records plus the amendment, each naming its confirmation tests.
**Prompt**: `tasks/WP03-adr-set-checkouts-cleanup-coordination-write.md`
**Requirement Refs**: FR-020, FR-038, FR-080, FR-081, FR-082, FR-083, FR-084, SC-010, C-003, C-005, C-007, C-016

### Included Subtasks

T011 Append the Core Decision 3 amendment to `docs/adr/3.x/2026-04-03-1-execution-lanes-own-worktrees-and-mission-branches.md` (WP03)
T012 [P] Write `upstream/adr-2026-11-06-1-amendment-draft.md` for the #7275 owner (WP03)
T013 [P] Write core ADR C-1 `docs/adr/4.x/2026-11-06-4-coordination-branch-written-by-commit.md` (WP03)
T014 [P] Write core ADR C-2 `docs/adr/4.x/2026-11-06-5-gates-over-worktree-less-coordination.md` (WP03)
T015 [P] Write core ADR C-3 `docs/adr/4.x/2026-11-06-6-committed-ledger-is-the-coordination-blob.md` (WP03)
T016 Append the D-6 / step 4a amendment to `docs/adr/4.x/2026-10-22-1-...md`, the D-6 mapping table, and the events-draft links (WP03)

### Dependencies

- None. C-2 cites #7274's #7265 pass by reference.

---

## Phase 2 - S1 one status read contract (code)

## Work Package WP04: S1 tidy-first, lane-root normalization (carrying #6884) and the typed ref reader (Priority: P1) MVP

**Goal**: every root-taking status entry re-anchors a lane root to the repository root (finishing #6884); the ref reader tells "absent file" from "bad ref".
**Independent Test**: lane copy says `planned`, write checkout says `in_progress`; three entry points called from the lane root all return the write checkout. A bad ref raises `StatusSurfaceRefUnreadable`; an absent file on a good ref reads empty.
**Prompt**: `tasks/WP04-s1-root-normalization-and-ref-reader.md`
**Requirement Refs**: FR-002, FR-004, FR-043

### Included Subtasks

T017 Carry #6884 forward: commit 1 = its red-first test `942ff4aed984` ALONE (path-limited `-x` cherry-pick), then the fix `59bd93d6bd68` and style `f404a0b24030` (optional `43f48eee8f63`) as separate path-limited `-x` commits; drop other-Mission kitty-specs, CHANGELOG.md and body6466.md; `Co-authored-by: Ivan Melck` on each (WP04)
T018 Tidy: rename the `_resolve_status_surface` alias in `implement_phases.py`, fix stale docstrings (WP04)
T019 Characterization matrix `tests/status/test_status_read_matrix.py` pinned at today's values (WP04)
T020 Red-first tests: lane-root, ref-reader typed error, absent-file empty, positive control, registry-unreadable fails closed (WP04)
T021 Lift `_canonical_status_read_root` into one helper called by the five entry points; registry unreadable fails closed (WP04)
T022 Typed `RefRead` / `StatusSurfaceRefUnreadable` in `read_event_log` / `read_event_stream_log` (WP04)
T023 Quality gates and blast radius (WP04)

### Dependencies

- Depends on WP01 (the ADR records the fail-closed registry and typed ref errors before the code; analysis F1). Carries #6884 itself.

---

## Work Package WP05: S1 read door and declared sources (Priority: P1)

**Goal**: one entry point `resolve_status_read(...) -> StatusReadSurface` with a declared source per topology; the resolver body delegates; the loud empty-coordination fallback is removed.
**Independent Test**: a `lanes_with_coord` Mission with 3 committed coordination events and the coordination worktree removed reads 3 events through the door, with exactly one git subprocess.
**Prompt**: `tasks/WP05-s1-read-door-declared-sources.md`
**Requirement Refs**: FR-001, FR-003, FR-061, NFR-001

### Included Subtasks

T024 Red-first acceptance tests for the door (unmaterialized, empty, pre-seed, owned, one-subprocess, never-nonexistent) (WP05)
T025 Value objects `StatusReadSource`, `StatusReadSurface` in `status/read_surface.py` (WP05)
T026 `resolve_status_read` per-topology source selection incl. the declared pre-seed fallback and FR-061 PRIMARY placement read (WP05)
T027 Batched `git cat-file --batch` ref reader and `read_status_events` / `read_status_stream` / `materialize_status` (WP05)
T028 `coordination/surface_resolver.py` delegates to the door; remove `_empty_coord_surface` loud fallback (WP05)
T029 Quality gates and blast radius (WP05)

### Dependencies

- Depends on WP01, WP04.

---

## Work Package WP06: S1 migrate status, CLI and mission_runtime readers onto the door (Priority: P1)

**Goal**: every status reader in `status/`, the CLI and `mission_runtime` reads through the door; the retired names are removed.
**Independent Test**: SC-001 cross-cwd parity matrix: 0 divergent cells.
**Prompt**: `tasks/WP06-s1-migrate-cli-and-runtime-readers.md`
**Requirement Refs**: FR-005, FR-043, SC-001

### Included Subtasks

T030 Red-first: `test_status_readers_agree_across_cwd_and_coord_state` and `test_agent_status_materialize_never_writes_read_only_path` (WP06)
T031 `status/aggregate.py`: `MissionStatus` holds a surface; `materialize` moves to the write dir (WP06)
T032 [P] Migrate `agent/status.py`, `events.py`, `retrospect.py`, `agent_retrospect.py`, `retrospective/gate.py` (WP06)
T033 [P] Migrate `tasks_shared.py`, `tasks_mark_status.py`, `implement_claim.py`, `implement_phases.py`, `mission_finalize_planning_pin.py:70`, `accept.py`, `issue_verdict.py` (WP06)
T034 Migrate `task_utils/support.py`, `migration/{wp_status_backfill,backfill_runtime_state}.py`, `mission_runtime/resolution.py` status-dir arms (WP06)
T035 Quality gates and blast radius (WP06)

### Dependencies

- Depends on WP05. Rebase point: #7255 (`mission_finalize_planning_pin.py`).

---

## Work Package WP07: S1 migrate consolidation readers and add the single-door gate (Priority: P1)

**Goal**: consolidation readers use the door; an empty-allowlist AST gate forbids any status read outside it and amends (not bypasses) the four standing gates.
**Independent Test**: SC-002: the gate reports 0 violations and detects 100% of its planted violations.
**Prompt**: `tasks/WP07-s1-consolidation-readers-and-single-door-gate.md`
**Requirement Refs**: FR-005, FR-006, SC-002, C-013, NFR-006

### Included Subtasks

T036 Red-first: `test_unmaterialized_preflight_reports_real_lanes` (WP07)
T037 Migrate `consolidation/{done_bookkeeping,forecast,phase_advance,preflight,entry_preflight,coord_strand}.py` (incl. `done_bookkeeping:610` raw `git show`) and the `transaction.py` `preflight_refusal` read (WP07)
T038 Gate `tests/architectural/test_status_read_single_door.py`: planted arms first (red), then the live scan (WP07)
T039 Amend `test_single_mission_surface_resolver.py`, `_surface_resolution_scan.py`, `test_no_read_side_bypass.py`, `test_read_surface_placement_guard.py` (WP07)
T040 Gate speed check (NFR-006 <= 5 s) and floors frozen at measured counts (WP07)
T041 Quality gates and blast radius (WP07)

### Dependencies

- Depends on WP06. Rebase point: #7274.

---

## Phase 3 - S2/S3/S6 lanes carry no live status (code)

## Work Package WP08: S2 - the for_review gate reads the lane branch ref (Priority: P1)

**Goal**: the shared gate counts `base..refs/heads/<lane>` from the repository root, passes with the checkout absent, refuses distinctly when the branch is missing.
**Independent Test**: SC-003 on all three surfaces.
**Prompt**: `tasks/WP08-s2-for-review-gate-on-lane-branch.md`
**Requirement Refs**: FR-010, FR-011, FR-012, FR-013, FR-014, SC-003, C-006, NFR-008

### Included Subtasks

T042 Red-first: extend `tests/specify_cli/lanes/test_for_review_gate_parity.py` with the seven named tests (WP08)
T043 Tidy: `lane_branch_has_commit_beyond_base(repo_root, base_ref, branch)` with `--end-of-options` in `lanes/_git.py`; extract `_code_lane_identity` (WP08)
T044 Gate on the ref: branch from `lane_created_branch`, drop `worktree.exists()`, `GateDecision.reason_code` (WP08)
T045 Reworded refusal text (names branch and base, no worktree advice) per `contracts/for-review-gate-refusal.md` (WP08)
T046 Quality gates and blast radius (Linux + Windows-safe) (WP08)

### Dependencies

- None.

---

## Work Package WP09: S3/S6 - one lane-checkout helper; status exclusion on every lane checkout (Priority: P1)

**Goal**: `open_lane_checkout(...)` is the only lane `git worktree add`; it installs the lane-tip hook, the `.spec-kitty/` exclude and the status sparse exclusion on every topology with code lanes; a single-seam gate holds it.
**Independent Test**: SC-004: a lane checkout from any route contains 0 Mission status files; the gate finds 0 raw lane `worktree add` and 100% of planted ones.
**Prompt**: `tasks/WP09-s3-s6-lane-checkout-helper.md`
**Requirement Refs**: FR-021, FR-022, FR-040, SC-004, C-013

### Included Subtasks

T047 Tidy: `lane_sparse_checkout_patterns` takes the resolved Mission dir name; rename `_register_sparse_checkout_if_coord` (WP09)
T048 Red-first: every-route no-status-files tests, lane-tip hook fires, lifecycle-sync flip (WP09)
T049 New `lanes/lane_checkout.py::open_lane_checkout` + `LaneCheckoutRequest` (WP09)
T050 Route allocation FRESH / FRESH_LEGACY / CRASH_RECOVERY through the helper (WP09)
T051 [P] Route `lifecycle_sync` recreate, `_create_review_worktree` and the printed recreate command through the helper (WP09)
T052 Gate `tests/architectural/test_lane_checkout_single_seam.py` (planted violations, scan floor) (WP09)
T053 Quality gates and blast radius (WP09)

### Dependencies

- Depends on WP01, WP03 (the S3 amendment to ADR `2026-04-03-1` governs the helper; analysis F1), WP08.

---

## Work Package WP10: S6 - lanes never change status; migrate existing lane worktrees; doctor probe (Priority: P1)

**Goal**: status writes refuse a registry-classified lane target; Spec Kitty lane commits leave status unstaged; a clone-local migration brings existing lane worktrees in line without losing an event; a doctor probe lists lane-authored status changes.
**Independent Test**: SC-009: migration loses 0 events and a second run changes nothing.
**Prompt**: `tasks/WP10-s6-lane-write-refusal-migration-doctor.md`
**Requirement Refs**: FR-041, FR-042, FR-044, FR-045, SC-009, NFR-002, NFR-005, C-008, C-009, C-014

### Included Subtasks

T054 Red-first: write refusal + positive control; deliverable auto-commit never stages status (WP10)
T055 Red-first: migration tests (clean, redundant-dirty, lane-only ids, mid-rebase, second run) and doctor probe test (WP10)
T056 `coordination_transaction_append` / `_validate_write_contract` classify the target through the worktree registry; `STATUS_WRITE_TARGETS_LANE_CHECKOUT` (WP10)
T057 `tasks_move_task.py`: `_drop_lane_coord_residue` and deliverable auto-commit leave status unstaged on every topology (WP10)
T058 Clone-local migration `m_4_0_0rc9_lane_checkout_status_exclusion.py` + `order_manifest.txt` entry (WP10)
T059 Doctor probe `LANE_STATUS_AUTHORED` vs merge-base in `_sparse_checkout_doctor.py` (WP10)
T060 Quality gates and blast radius (WP10)

### Dependencies

- Depends on WP05, WP09.

---

## Phase 4 - S8 approval windows for `single_branch` (code)

## Work Package WP11: S8 - stamp the write-branch head; approval-time warnings (Priority: P1)

**Goal**: every lifecycle transition of a stored-`single_branch` Mission carries the Mission write branch head as `lane_head`; the existing warnings print for `single_branch`.
**Independent Test**: a `single_branch` approval records `lane_head` = Mission branch head; a `lanes` planning-lane WP stays unstamped.
**Prompt**: `tasks/WP11-s8-stamp-write-branch-head.md`
**Requirement Refs**: FR-070, FR-075

### Included Subtasks

T061 Red-first: stamp, positive control, move-task approved stamp, unstamped warning (WP11)
T062 Tidy: `write_branch_for(manifest, meta)` collapsing the overlapping predicates; owned-aware stored-topology helper (WP11)
T063 Tidy: rename `_maps_to_code_lane` -> `_approval_is_bounded`; split `check_lane` stamp resolution into public `stamp_refusal(...)` (WP11)
T064 `status/lane_head.py` `single_branch` arm keyed on the stored topology (function-local imports) (WP11)
T065 Warnings for `single_branch` in `approved_bound` (unstamped, forced approval) (WP11)
T066 Quality gates and blast radius (WP11)

### Dependencies

- Depends on WP02. External: rebase onto #7248 once merged; reverse its fixture comment deliberately.

---

## Work Package WP12: S8 - per-WP approval windows at claim and gate (Priority: P1)

**Goal**: tier 1 (after newest approval) and tier 2 (every content commit in some `(O_k, S_k]`) at claim; the gate re-check reads the Mission branch through the claim's `lane_id -> branch` map; refuse-plus-attest; commit-to-target residual pinned.
**Independent Test**: SC-008 scenario set through `spec-kitty consolidate`.
**Prompt**: `tasks/WP12-s8-approval-windows-claim-and-gate.md`
**Requirement Refs**: FR-071, FR-072, FR-073, FR-074, FR-076, FR-078, SC-008, SC-012, NFR-007, C-012

### Included Subtasks

T067 Red-first claim scenarios (late commit, between approvals, overlapping review, rework, re-approval) (WP12)
T068 Red-first legacy and gate scenarios (unstamped + attest, rebased, gate mid-run, own bookkeeping, target merge-in, orchestrator code, residual xfail, cost) (WP12)
T069 New `consolidation/write_branch_bound.py::check_write_branch` (tier 1 + tier 2, missing-`O_k` degrade logged) (WP12)
T070 `reconciliation._approved_bound_verdict` `single_branch` arm when `lands_mission_branch` (WP12)
T071 `lane_tips_moved_refusal` takes a `lane_id -> branch` map; `phase_gate` passes it (WP12)
T072 Refusal text and recovery advice (tool commits after approval) (WP12)
T073 Quality gates and blast radius (WP12)

### Dependencies

- Depends on WP11.

---

## Phase 5 - S7 topology settled at finalize (code)

## Work Package WP13: S7 tidy-first, provenance and topic-branch-only create (Priority: P1)

**Goal**: `create` without `--topology` mints exactly one topic branch, records `topology_source: default`, `topology_settled: false`, `create_return_branch`; explicit topology unchanged; one `TOPOLOGY_HELP` constant.
**Independent Test**: SC-007 create half: 1 new branch, 0 worktrees, no coordination branch, on protected and unprotected targets.
**Prompt**: `tasks/WP13-s7-provenance-and-topic-branch-create.md`
**Requirement Refs**: FR-051, FR-052, FR-058, FR-059, FR-060, C-012

### Included Subtasks

T074 Red-first create tests (topic-branch-only both targets, explicit coord control, owned unchanged, commit-to-target, create --json, return branch, other-Mission topic target, occupied refusal) (WP13)
T075 Tidy: one `TOPOLOGY_HELP` constant for `mission_create.py`, `lifecycle.py`, `design_phase.py` (WP13)
T076 Tidy + bug fix: extract the protected-mint "switch the write checkout" core with #5676 occupancy/dirty refusals (WP13)
T077 [P] Tidy: pure `count_code_lanes(...)` in `lanes/compute_and_persist.py` (WP13)
T078 [P] Tidy: `restamp_*` sibling of `flatten_coordination_metadata` in `mission_metadata.py`, ratchet-registered (WP13)
T079 `meta_keys.py` keys; `_resolve_default_topology_phase` returns `(topology, source)`; default arm provisional (WP13)
T080 `create --json` / `specify` / `orchestrator-api specify` provisional fields (emitted under WP15's 1.24.0 bump; doc rows are WP15's) (WP13)
T081 Quality gates and blast radius (WP13)

### Dependencies

- Depends on WP02, WP15 (WP15 is the single owner of the 1.24.0 bump and documents these fields; WP13 only emits them, analysis F2). C-010: must not reach a release before WP12 and WP14.

---

## Work Package WP14: S7 settlement at the first finalize, with compensation (Priority: P1)

**Goal**: the first `finalize-tasks` settles a provisional Mission by size, once and atomically, to `single_branch` or `lanes_with_coord` (topic branch = coordination branch, root checkout back on `create_return_branch`).
**Independent Test**: SC-007 finalize half plus NFR-003 fault injection.
**Prompt**: `tasks/WP14-s7-settlement-at-first-finalize.md`
**Requirement Refs**: FR-053, FR-054, FR-055, FR-056, FR-057, FR-058, FR-061, SC-007, NFR-002, NFR-003, C-010, C-011

### Included Subtasks

T082 First commit: `test_default_mission_primary_placement_topic_branch_pinned` + explicit-topology positive control (placement only; the consolidate landing leg is WP20) (WP14)
T083 Red-first settlement scenario tests (2-WP, 3-lane protected/unprotected, root-checkout move, return-branch refusal, explicit wins, 5-WP-1-lane, re-finalize, legacy, canceled/planning counting) (WP14)
T084 Red-first preview/report/refusal/fault-injection tests (validate-only, --json, orchestrator tasks, occupied/dirty, byte-identical restore) (WP14)
T085 `_decide_topology_by_size` phase before the frozen preflight in `mission_finalize.py` (WP14)
T086 New `lanes/topology_settlement.py`: transition plan, git steps, undo stack, `TOPOLOGY_SETTLEMENT_REFUSED` (WP14)
T087 Wire `_apply_topology_settlement` before `_emit_tasks_started`; `mission_finalize_lanes.py` takes the decided topology; `mission_finalize_commit.py` attributes the re-stamp (WP14)
T088 `mission_runtime/resolution.py` provisional / default-PRIMARY arm of `single_branch_write_ref` (sequenced after WP06) (WP14)
T089 No-redecide pins in `tasks_finalize.py` and `migration/mission_state.py` (WP14)
T090 Quality gates and blast radius (WP14)

### Dependencies

- Depends on WP06, WP12, WP13, WP15 (1.24.0 owner; `topology_decision` doc row is WP15's, analysis F2). External rebase point: #7255.

---

## Phase 6 - S5 cleanup as the last consolidation step (code)

## Work Package WP15: S5 - one lane-cleanup module behind a remover port; keep and report (Priority: P2)

**Goal**: one `consolidation/lane_cleanup.py` used by the executor, `orchestrator-api consolidate-mission` and `mission close --discard`; order coordination -> lanes -> record clear; kept lanes are reported with exit 0; contract 1.24.0.
**Independent Test**: SC-005: a dirtied lane after a verified landing -> exit 0, one Kept entry, 0 consolidation records.
**Prompt**: `tasks/WP15-s5-lane-cleanup-module.md`
**Requirement Refs**: FR-030, FR-031, FR-032, FR-033, FR-034, FR-035, FR-039a, SC-005, SC-012, NFR-002, NFR-004, NFR-008, C-012, C-017

### Included Subtasks

T091 Red-first: drift pin (`_created_lane_branch` vs `code_lane_branch_name`) and FR-035 resume-after-kill test written first (WP15)
T092 Red-first: kept exit 0, orchestrator parity, retained vs kept, missing branch keeps tip ref, abort after partial cleanup, coord refusal exit codes (WP15)
T093 Extract `consolidation/lane_cleanup.py` (pure `plan_lane_cleanup`, `apply`, `LaneRemover` Protocol, main-today remover) (WP15)
T094 `phase_teardown.py` order: coordination triple, lane legs, record clear; `clear_tip` only after a confirmed delete (WP15)
T095 `run_state.py` / `state.py` `cleanup_started` marker and PASS anchor over cleanup's own commits (only if T091 is red) (WP15)
T096 `cli/commands/consolidate.py` Kept / Retained rendering; `executor.py` wiring (WP15)
T097 `orchestrator_api/consolidation.py` on the module with per-lane outcomes; `envelope.py` CONTRACT_VERSION 1.24.0 (single owner); `docs/api/orchestrator-api.md` rows for `lane_cleanup` and WP13/WP14's topology fields (WP15)
T098 `cli/commands/mission_type.py` `--discard` on the module (WP15)
T099 Quality gates and blast radius (WP15)

### Dependencies

- Depends on WP03. External rebase point: #7274.

---

## Work Package WP16: S5 binding after #7275 - guard entry, pr-mode cleanup, prune backstop (Priority: P2) BLOCKED

**BLOCKED until #7275 merges into `main` and `issue-7276-lane-worktree-hardening` is rebased onto it. Out of the first PR cut.**

**Exit rule (analysis C2)**: WP16 stays `planned`. If #7275 has not merged into `main` by the time every other WP is approved, WP16 is canceled with a recorded rationale, a new follow-up issue is opened for the S5 guard binding, and FR-036, FR-037, FR-039 and SC-006 are recorded deferred-with-followup (naming that issue) in `issue-matrix.json`. `accept` and `consolidate` proceed without it.

**Goal**: bind `LaneRemover` to `guarded_landed_removal` with the O3-local landing proof; `accept --mode pr` removes absorbed lanes before the PR merges; `doctor workspaces --prune` treats consolidated Mission lanes as candidates.
**Independent Test**: SC-006.
**Prompt**: `tasks/WP16-s5-guard-binding-pr-mode-prune.md`
**Requirement Refs**: FR-036, FR-037, FR-039, SC-006, C-004, NFR-005, NFR-006, NFR-008

### Included Subtasks

T100 Precondition check: #7275 merged, topic branch rebased, ADR `2026-11-06-1` present; else stop (WP16)
T101 Red-first pr-mode, prune, guard tests (incl. probe unavailable keeps and reports, never-force pin) (WP16)
T102 O3-local landing proof variant in `git/destructive_guard.py` (coordinated with the #7275 owner) (WP16)
T103 Bind `LaneRemover` to `guarded_landed_removal` (binding hunk in `lane_cleanup.py`) (WP16)
T104 `acceptance/__init__.py` pr-mode cleanup step; remove raw `git worktree remove` / `git branch -d` advice (WP16)
T105 `workspace/landed_worktrees.py` + `_landed_worktree_doctor.py` Mission-lane prune candidates (second run changes nothing, NFR-005); destructive-op routing pins in `test_destructive_op_routing.py` (<= 5 s, NFR-006) (WP16)
T106 Quality gates, blast radius, changelog fragment (WP16)

### Dependencies

- Depends on WP06, WP09, WP15. External BLOCK: #7275.

---

## Work Package WP20: S7 - consolidate lands a default Mission's PRIMARY artifacts from the topic branch (Priority: P1)

**Goal**: for a `topology_source: default` Mission settled to `lanes_with_coord`, `consolidate` carries every PRIMARY-partition change on the topic branch (= coordination branch) to the target before the coordination teardown, through the extended mission-branch landing seam (one landing authority; rollback authority unchanged). Added after `/spec-kitty.analyze` finding E1 (plan IC-18).
**Independent Test**: (a) a PRIMARY edit made on the topic branch after the last lane cut reaches the target; (b) nothing is lost on `--resume` or rollback; (c) control: explicit `--topology lanes_with_coord` consolidates as today.
**Prompt**: `tasks/WP20-s7-consolidate-lands-topic-branch-primary.md`
**Requirement Refs**: FR-055, FR-061, FR-062, SC-007, NFR-002

### Included Subtasks

T118 Characterize today's consolidate of a default `lanes_with_coord` Mission (which PRIMARY paths are lost, where) (WP20)
T119 Red-first: post-last-cut PRIMARY edit reaches target; resume/rollback lose nothing; explicit-topology control; orchestrator parity; predicate unit tests (WP20)
T120 Extend the landing predicate in `lanes/single_branch_landing.py` with the default-settled `lanes_with_coord` arm (recorded out-of-map, WP11-owned) (WP20)
T121 PRIMARY projection leg in `bookkeeping_projection.py`; call in `phase_advance.py` (out-of-map, WP07-owned); land-before-teardown in `phase_teardown.py` (out-of-map, WP15-owned) (WP20)
T122 Green the red tests; projection, late-teardown and rollback-authority pins stay green (WP20)
T123 Quality gates and blast radius (WP20)

### Dependencies

- Depends on WP07 (`phase_advance.py` owner), WP14 (settlement; WP11 transitively, `single_branch_landing.py` owner), WP15 (`phase_teardown.py` owner, cleanup order). C-010: ships with WP13/WP14.

---

## Phase 7 - S11 text that follows behaviour

## Work Package WP17: S11 core command skills, stale-lane CLI remedy, skill-text guard, CLAUDE.md (Priority: P3)

**Goal**: the six core command skills and the stale-lane CLI message teach the shipped model; a guard test with planted strings keeps them honest; CLAUDE.md describes the size default and the topic branch.
**Independent Test**: SC-011 (core half).
**Prompt**: `tasks/WP17-s11-skills-stale-remedy-guard.md`
**Requirement Refs**: FR-090, FR-091, FR-093, FR-059, SC-011, C-001

### Included Subtasks

T107 Red-first: `test_stale_remediation_has_no_git_merge_or_worktrees_cd`, A-10 re-entry verification, skill guard with planted strings (WP17)
T108 `lanes/stale_check.py::_stale_remediation` prints a `spec-kitty` command (WP17)
T109 Edit the six SKILL.md files (K1-K9) (WP17)
T110 CLAUDE.md "Execution Workspace Strategy" and "Consolidation" paragraphs (WP17)
T111 Quality gates and blast radius (WP17)

### Dependencies

- Depends on WP07, WP08, WP10, WP12, WP14, WP15, WP20.

---

## Work Package WP18: S11 docs pages and changelog fragments (Priority: P3)

**Goal**: `docs/architecture/execution-lanes.md`, `docs/architecture/git-worktrees.md`, `docs/context/topology.md` describe the shipped model; one changelog fragment set per issue.
**Independent Test**: changelog style/spelling checks and the terminology guard pass; docs say "settled at first finalize", never "explicit-only" for the default.
**Prompt**: `tasks/WP18-s11-docs-and-changelog.md`
**Requirement Refs**: FR-059, FR-093, C-001

Runs as `code_change` (owns only `docs/` files) so it can follow WP17 in a code lane; a planning-artifact WP after code WPs forms a lane cycle.

### Included Subtasks

T112 Docs pages: size default, topic branch, coordination branch shares the Mission branch name, status surface, cleanup last (WP18)
T113 [P] Changelog fragments for #7277-#7285 (WP18)
T116 Validation: changelog style/spelling, terminology guard, docs frontmatter (WP18)

### Dependencies

- Depends on WP17.

---

## Work Package WP19: S11 open-packs doctrine patch and hand-off (Priority: P3) TO BE CANCELED

**To be canceled at implement time**: the operator made open-packs PR #128 ready and ungated, and the S11 doctrine is already applied there. This Mission does not bump the core pack pin. The orchestrator cancels WP19 with that rationale when the implement loop reaches it; FR-092 and the pack half of SC-011 are recorded as delivered by open-packs PR #128 in the issue matrix. No WP depends on WP19.

**Goal**: a patch against the pinned `spec-kitty-open-packs` tree plus hand-off steps (FR-092).
**Independent Test**: SC-011 (pack half): `git apply --check` succeeds on the pinned tree.
**Prompt**: `tasks/WP19-s11-open-packs-doctrine-patch.md`
**Requirement Refs**: FR-092, FR-093, SC-011, C-002

Planning artifact (planning lane), so it carries no code dependency. **Hand-off gate**: the orchestrator hands the patch over only after WP07, WP08, WP10, WP12, WP14 and WP15 are approved (rows for WP16 behaviour withheld unless it landed); re-run `git apply --check` then.

### Included Subtasks

T114 Open-packs patch against the pinned tree, each row tagged with its delivering FR (WP19)
T115 Hand-off note (pin bump, `make sync-packs`, `charter pack regenerate-graph`, withheld rows) (WP19)
T117 Validation: `git apply --check`, terminology guard (WP19)

### Dependencies

- None (hand-off gate above instead).

---

## Dependency & Execution Summary

```
WP01 ─► WP04 ─► WP05 ─► WP06 ─► WP07 ─────────────┬─► WP20 ─┐
WP01 ───────────► WP05            │                  │         │
WP08 ─► WP09 ◄─ WP01, WP03        └──► WP14 ─────────┤         ├─► WP17 ─► WP18
          └──► WP10 ◄─ WP05             ▲            │         │
WP02 ─► WP11 ─► WP12 ───────────────────┤            │         │
WP02 ─► WP13 ───────────────────────────┤            │         │
WP03 ─► WP15 ─► WP13, WP14 (1.24.0 owner) ───────────┘         │
WP15 ─► WP16 (BLOCKED on #7275; also WP06, WP09; exit rule)    │
WP07, WP08, WP10, WP12, WP14, WP15, WP20 ──────────────────────┘
WP19 (planning lane, no deps; TO BE CANCELED: open-packs PR #128)
```

- **Start immediately (no deps)**: WP01, WP02, WP03, WP08 (WP19 has no deps but is canceled). WP04 starts once WP01 is approved.
- **Lane hints** (finalize-tasks computes the real lanes): S1 chain WP04 -> WP05 -> WP06 -> WP07; S2/S3/S6 chain WP08 -> WP09 -> WP10; S8/S7 chain WP11 -> WP12 -> WP14 with WP13 beside it (both after WP15) -> WP20; S5 chain WP15 (-> WP16 later); ADR WPs and WP19 are planning artifacts (planning lane).
- **Release coupling (C-010)**: WP13 and WP14 never reach a release without WP11 and WP12.
- **First PR cut**: every WP except WP16 (blocked; see its exit rule) and WP19 (canceled: open-packs PR #128). WP16 lands after #7275 after a rebase, or is canceled and deferred to a follow-up issue.
- **Release coupling (C-010)** also holds for WP20: it ships with WP13 and WP14.
- **MVP**: WP04 + WP05 (one read contract) carry the most value; every other slice relies on them.

### Shared-file sequencing (out-of-map hunks)

`owned_files` never overlap. Where the plan gives two concerns hunks in one file, one WP owns the file and the other makes a small, recorded out-of-map edit (one-line rationale in its completion summary):

| File | Owner | Out-of-map hunk by | Sequence |
|------|-------|--------------------|----------|
| `src/specify_cli/coordination/status_service.py` | WP04 | WP10 (`_validate_write_contract`) | WP04 -> WP10 |
| `src/mission_runtime/resolution.py` | WP06 | WP04 (docstrings), WP14 (provisional arm) | WP04 -> WP06 -> WP14 |
| `src/specify_cli/cli/commands/implement_phases.py` | WP06 | WP04 (alias rename) | WP04 -> WP06 |
| `src/specify_cli/coordination/surface_resolver.py` | WP05 | WP04 (normalization call) | WP04 -> WP05 |
| `src/specify_cli/status/aggregate.py` | WP06 | WP04 (normalization call in `MissionStatus.load`) | WP04 -> WP06 |
| `src/specify_cli/coordination/transaction.py` | WP10 | WP07 (`preflight_refusal` read) | different functions on parallel lanes; both WPs record the hunk in their completion summaries (analysis F5) |
| `src/specify_cli/workspace/landed_worktrees.py` | WP16 | WP09 (printed recreate command) | WP09 -> WP16 |
| `src/specify_cli/consolidation/lane_cleanup.py` | WP15 | WP16 (binding) | WP15 -> WP16 |
| `docs/api/orchestrator-api.md`, `orchestrator_api/envelope.py` | WP15 (single owner of the 1.24.0 bump and of every 1.24.0 field row) | none planned; a correction by WP13/WP14 is a recorded out-of-map edit | WP15 -> WP13 -> WP14 (dependencies; lanes stay acyclic, analysis F2) |
| `src/specify_cli/lanes/single_branch_landing.py` | WP11 | WP20 (default `lanes_with_coord` landing arm) | WP11 -> WP12 -> WP14 -> WP20 |
| `src/specify_cli/consolidation/phase_advance.py` | WP07 | WP20 (PRIMARY landing call) | WP07 -> WP20 |
| `src/specify_cli/consolidation/phase_teardown.py` | WP15 | WP20 (land before coordination teardown) | WP15 -> WP20 |

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP05 |
| FR-002 | WP04 |
| FR-003 | WP05 |
| FR-004 | WP04 |
| FR-005 | WP06, WP07 |
| FR-006 | WP07 |
| FR-007 | WP01 |
| FR-010 to FR-014 | WP08 |
| FR-020 | WP03 |
| FR-021, FR-022 | WP09 |
| FR-030 to FR-035, FR-039a | WP15 |
| FR-036, FR-037, FR-039 | WP16 (deferred-with-followup if #7275 is unmerged when all other WPs are approved) |
| FR-038 | WP03 |
| FR-040 | WP09 |
| FR-041, FR-042, FR-044, FR-045 | WP10 |
| FR-043 | WP04, WP06 |
| FR-046 | WP01 |
| FR-050 | WP02 |
| FR-051, FR-052, FR-060 | WP13 |
| FR-053 to FR-057 | WP14 (FR-055 consolidate leg: WP20) |
| FR-058 | WP13, WP14 |
| FR-059 | WP13, WP17, WP18 |
| FR-061 | WP01, WP02, WP05, WP14, WP20 |
| FR-062 | WP20 |
| FR-070, FR-075 | WP11 |
| FR-071 to FR-074, FR-076, FR-078 | WP12 |
| FR-077 | WP02 |
| FR-080 to FR-084 | WP03 |
| FR-090, FR-091 | WP17 |
| FR-092 | WP19 (to be canceled: delivered by open-packs PR #128) |
| FR-093 | WP17, WP18, WP19 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | S1 read-contract ADR draft | WP01 | P1 | No |
| T002 | FR-017/C-002 reversal + 2026-06-19-1 amendment | WP01 | P1 | No |
| T003 | FR-061 PRIMARY placement record | WP01 | P1 | No |
| T004 | 2026-07-29-1 restated ruling 3 amendment | WP01 | P1 | Yes |
| T005 | Confirmation tests, links, validation | WP01 | P1 | No |
| T006 | Topology ADR: size rule, mapping, deferral | WP02 | P1 | No |
| T007 | Provisional record, placement, decide-once, compensation | WP02 | P1 | No |
| T008 | 2026-06-22-1 D2 amendment | WP02 | P1 | Yes |
| T009 | 2026-10-04-5 per-WP window amendment (end of file) | WP02 | P1 | Yes |
| T010 | Confirmation tests, links, validation | WP02 | P1 | No |
| T011 | 2026-04-03-1 Core Decision 3 amendment | WP03 | P2 | No |
| T012 | ADR 2026-11-06-1 amendment draft | WP03 | P2 | Yes |
| T013 | Core ADR C-1 | WP03 | P2 | Yes |
| T014 | Core ADR C-2 | WP03 | P2 | Yes |
| T015 | Core ADR C-3 | WP03 | P2 | Yes |
| T016 | D-6 / step 4a amendment + mapping | WP03 | P2 | No |
| T017 | Carry #6884 forward with attribution | WP04 | P1 | No |
| T018 | Tidy rename + docstrings | WP04 | P1 | No |
| T019 | Characterization matrix | WP04 | P1 | No |
| T020 | Red-first root + ref-reader tests | WP04 | P1 | No |
| T021 | One normalization helper, fail closed | WP04 | P1 | No |
| T022 | Typed ref reader | WP04 | P1 | No |
| T023 | Quality gates (WP04) | WP04 | P1 | No |
| T024 | Red-first door tests | WP05 | P1 | No |
| T025 | Door value objects | WP05 | P1 | No |
| T026 | Per-topology source selection | WP05 | P1 | No |
| T027 | Batched ref reader + read functions | WP05 | P1 | No |
| T028 | Resolver delegates; drop loud fallback | WP05 | P1 | No |
| T029 | Quality gates (WP05) | WP05 | P1 | No |
| T030 | Red-first parity matrix | WP06 | P1 | No |
| T031 | MissionStatus holds a surface | WP06 | P1 | No |
| T032 | Migrate status/events/retrospect readers | WP06 | P1 | Yes |
| T033 | Migrate tasks/implement/accept readers | WP06 | P1 | Yes |
| T034 | Migrate support/migration/runtime readers | WP06 | P1 | No |
| T035 | Quality gates (WP06) | WP06 | P1 | No |
| T036 | Red-first unmaterialized preflight | WP07 | P1 | No |
| T037 | Migrate consolidation readers | WP07 | P1 | No |
| T038 | Single-door gate | WP07 | P1 | No |
| T039 | Amend four standing gates | WP07 | P1 | No |
| T040 | Gate speed + floors | WP07 | P1 | No |
| T041 | Quality gates (WP07) | WP07 | P1 | No |
| T042 | Red-first gate parity tests | WP08 | P1 | No |
| T043 | Ref probe helper + identity extraction | WP08 | P1 | No |
| T044 | Gate reads the ref; reason_code | WP08 | P1 | No |
| T045 | Refusal text | WP08 | P1 | No |
| T046 | Quality gates (WP08) | WP08 | P1 | No |
| T047 | Tidy sparse patterns + rename | WP09 | P1 | No |
| T048 | Red-first every-route tests | WP09 | P1 | No |
| T049 | `open_lane_checkout` helper | WP09 | P1 | No |
| T050 | Allocation routes through helper | WP09 | P1 | No |
| T051 | Sync/review/recreate routes through helper | WP09 | P1 | Yes |
| T052 | Single-seam gate | WP09 | P1 | No |
| T053 | Quality gates (WP09) | WP09 | P1 | No |
| T054 | Red-first write refusal + auto-commit | WP10 | P1 | No |
| T055 | Red-first migration + doctor tests | WP10 | P1 | No |
| T056 | Registry-classified write refusal | WP10 | P1 | No |
| T057 | Lane commits leave status unstaged | WP10 | P1 | No |
| T058 | Clone-local migration | WP10 | P1 | No |
| T059 | Doctor probe LANE_STATUS_AUTHORED | WP10 | P1 | Yes |
| T060 | Quality gates (WP10) | WP10 | P1 | No |
| T061 | Red-first stamp tests | WP11 | P1 | No |
| T062 | `write_branch_for` tidy | WP11 | P1 | No |
| T063 | `_approval_is_bounded`, `stamp_refusal` tidy | WP11 | P1 | No |
| T064 | lane_head single_branch arm | WP11 | P1 | No |
| T065 | single_branch warnings | WP11 | P1 | No |
| T066 | Quality gates (WP11) | WP11 | P1 | No |
| T067 | Red-first claim window scenarios | WP12 | P1 | No |
| T068 | Red-first legacy/gate scenarios | WP12 | P1 | No |
| T069 | `check_write_branch` tier 1 + 2 | WP12 | P1 | No |
| T070 | `_approved_bound_verdict` single_branch arm | WP12 | P1 | No |
| T071 | Gate re-check lane->branch map | WP12 | P1 | No |
| T072 | Refusal text + recovery advice | WP12 | P1 | No |
| T073 | Quality gates (WP12) | WP12 | P1 | No |
| T074 | Red-first create tests | WP13 | P1 | No |
| T075 | `TOPOLOGY_HELP` constant | WP13 | P1 | No |
| T076 | Protected-mint switch core + #5676 | WP13 | P1 | No |
| T077 | `count_code_lanes` | WP13 | P1 | Yes |
| T078 | `restamp_*` metadata helper | WP13 | P1 | Yes |
| T079 | Meta keys + default arm provisional | WP13 | P1 | No |
| T080 | Create/specify JSON fields | WP13 | P1 | No |
| T081 | Quality gates (WP13) | WP13 | P1 | No |
| T082 | PRIMARY placement pin (first commit) | WP14 | P1 | No |
| T083 | Red-first settlement scenarios | WP14 | P1 | No |
| T084 | Red-first preview/report/fault tests | WP14 | P1 | No |
| T085 | Size decision phase | WP14 | P1 | No |
| T086 | `topology_settlement.py` with compensation | WP14 | P1 | No |
| T087 | Finalize wiring | WP14 | P1 | No |
| T088 | resolution.py provisional arm | WP14 | P1 | No |
| T089 | No-redecide pins | WP14 | P1 | Yes |
| T090 | Quality gates (WP14) | WP14 | P1 | No |
| T091 | Red-first drift pin + resume crash test | WP15 | P2 | No |
| T092 | Red-first kept/retained/abort tests | WP15 | P2 | No |
| T093 | Extract lane_cleanup module | WP15 | P2 | No |
| T094 | Teardown order + clear_tip | WP15 | P2 | No |
| T095 | cleanup_started marker | WP15 | P2 | No |
| T096 | Kept/Retained rendering | WP15 | P2 | No |
| T097 | Orchestrator per-lane + 1.24.0 | WP15 | P2 | No |
| T098 | mission close --discard | WP15 | P2 | Yes |
| T099 | Quality gates (WP15) | WP15 | P2 | No |
| T100 | #7275 precondition check | WP16 | P2 | No |
| T101 | Red-first pr-mode/prune/guard tests | WP16 | P2 | No |
| T102 | O3-local proof variant | WP16 | P2 | No |
| T103 | Bind LaneRemover | WP16 | P2 | No |
| T104 | pr-mode cleanup step | WP16 | P2 | No |
| T105 | Prune candidates + routing pins | WP16 | P2 | No |
| T106 | Quality gates (WP16) | WP16 | P2 | No |
| T107 | Red-first stale remedy + skill guard | WP17 | P3 | No |
| T108 | Stale remedy prints spec-kitty command | WP17 | P3 | No |
| T109 | Six SKILL.md edits | WP17 | P3 | Yes |
| T110 | CLAUDE.md paragraphs | WP17 | P3 | Yes |
| T111 | Quality gates (WP17) | WP17 | P3 | No |
| T112 | Docs pages | WP18 | P3 | No |
| T113 | Changelog fragments | WP18 | P3 | Yes |
| T114 | Open-packs patch | WP19 | P3 | No |
| T115 | Hand-off note | WP19 | P3 | No |
| T116 | Validation (docs/changelog) | WP18 | P3 | No |
| T117 | Validation (patch) | WP19 | P3 | No |
| T118 | Characterize default lanes_with_coord consolidate | WP20 | P1 | No |
| T119 | Red-first PRIMARY landing tests | WP20 | P1 | No |
| T120 | Landing predicate default arm | WP20 | P1 | No |
| T121 | PRIMARY projection before teardown | WP20 | P1 | No |
| T122 | Green tests, pins stay green | WP20 | P1 | No |
| T123 | Quality gates (WP20) | WP20 | P1 | No |
