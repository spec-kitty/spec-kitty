# Tasks: Upgrade writes project-global state once

**Mission**: `upgrade-project-global-state-01M44538` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)
**Branch contract**: planning base, final merge target and consolidation target are all `issue-5457-upgrade-project-global-state`.

## Subtask index

| ID | Subtask | WP | Parallel |
|----|---------|----|----------|
| T001 | Add `StateSurface.primary_owned` (and `to_dict`), and mark `project_metadata` | WP01 | |
| T002 | Add `primary_owned_paths()` / `is_primary_owned_path()` (exact, root-anchored) | WP01 | |
| T003 | Unit tests: predicate exactness, the C-008 negatives, the TRACKED/PROJECT invariant | WP01 | [P] |
| T004 | Shared real-git fixture builders: older-version project with lanes; broken-state branches | WP01 | [P] |
| T005 | Red: real-CLI `upgrade --yes` leaves integrating lane and coordination branches untouched, with a non-integrating control | WP02 | |
| T006 | Implement `_is_integrating_worktree` and the skip seam in `_upgrade_worktrees` | WP02 | |
| T007 | Re-pin the defect-pinning tests in `test_upgrade_worktree_commit.py` and the #4972 tests | WP02 | |
| T008 | Real-CLI fresh-upgrade paths: A (two lanes), B (one lane, squash into `work`) and C (coordination review) | WP02 | |
| T009 | Red: `check_lane_staleness` refuses on primary-owned and content-identical overlaps | WP03 | |
| T010 | Implement the primary-owned exclusion in the stale check | WP03 | |
| T011 | Implement the content-identical (`ls-tree` mode + object) exclusion | WP03 | |
| T012 | Controls: different content and a deletion on one side are still stale; remedy text byte-identical | WP03 | [P] |
| T013 | Red: real-CLI `consolidate` on broken-state fixtures (Story 4 AS-1, AS-2, AS-3, plus a status.json mix) | WP04 | |
| T014 | Implement `resolve_primary_owned_conflicts(worktree, env)`, with unit tests | WP04 | |
| T015 | Wire it into `_run_squash_merge` (ordering) and the MERGE branch of `_merge_branch_into` | WP04 | |
| T016 | Red, then wire: dependency-lane merge in `worktree_allocator` (Story 4 AS-5 via `implement`) | WP04 | |
| T017 | Controls (Story 5 AS-2, dependency source conflict) and the half-by-half revert proof | WP04 | |
| T018 | Tidy-first: parametrise the `_resolve_take_theirs` rule id (behaviour-preserving) | WP05 | |
| T019 | Red: the coordination lane sync refuses on a divergent `metadata.yaml` (Story 4 AS-4) | WP05 | |
| T020 | Implement the `R-PRIMARY-OWNED-BOOKKEEPING` managed-artifact branch, with the audit id in the commit message | WP05 | |
| T021 | Controls: a non-classified conflict still raises `LANE_AUTO_REBASE_FAILED`; a deletion takes stage 3 | WP05 | [P] |
| T022 | New ADR `docs/adr/4.x/2026-10-04-2-…` and inventory refresh | WP06 | |
| T023 | Amend ADRs `2026-07-07-1` (residuals) and `2026-05-14-1` (managed-arm rule) | WP06 | [P] |
| T024 | Recovery how-to, plus an architecture note in branch-target-routing / git-worktrees | WP06 | [P] |
| T025 | CHANGELOG `[Unreleased]` entry, docs freshness and terminology gates | WP06 | |

## Work packages

### WP01 — Primary-owned declaration and shared fixtures (foundation)
- **Goal**: one declared fact plus a derived predicate (FR-004, C-002, C-008), and the real-git fixture builders that every later WP's red tests share.
- **Priority**: P1 (it unblocks WP03, WP04 and WP05). **Independent test**: `tests/specify_cli/test_state_contract.py` plus the new predicate tests, and a self-test of the fixture builders.
- **Subtasks**: T001, T002, T003, T004.
- **Dependencies**: none. **Parallel**: it can run alongside WP02.
- **Prompt**: [tasks/WP01-primary-owned-declaration.md](tasks/WP01-primary-owned-declaration.md) (~175 lines).

### WP02 — Upgrade write placement (source fix)
- **Goal**: `spec-kitty upgrade` writes, stamps and commits nothing in integrating worktrees, while non-integrating worktrees are unchanged (FR-001, FR-002, FR-003, FR-011, NFR-001, C-001). Fresh-upgrade Paths A, B and C go green through the real CLI.
- **Priority**: P1 (MVP: on its own it fixes every *future* upgrade).
- **Subtasks**: T005, T006, T007, T008.
- **Dependencies**: WP01 (it uses the shared fixture builders only).
- **Prompt**: [tasks/WP02-upgrade-write-placement.md](tasks/WP02-upgrade-write-placement.md) (~190 lines).

### WP03 — Stale-lane rules
- **Goal**: the stale check ignores primary-owned and content-identical overlaps; genuine overlaps stay stale, with byte-identical text (FR-005, FR-006, FR-009).
- **Subtasks**: T009, T010, T011, T012.
- **Dependencies**: WP01.
- **Prompt**: [tasks/WP03-stale-lane-rules.md](tasks/WP03-stale-lane-rules.md) (~135 lines).

### WP04 — Merge-site resolver (consolidate and dependency-lane merge)
- **Goal**: lane → mission, mission → target (squash and merge) and the dependency-lane merge resolve primary-owned conflicts to their fixed side, so a broken-state mission consolidates and dependent WPs start (FR-007, FR-012, FR-013, FR-009, FR-010 evidence).
- **Subtasks**: T013, T014, T015, T016, T017.
- **Dependencies**: WP01, WP03 (Story 4 AS-1 and AS-2 need the stale rule to reach the merge site).
- **Prompt**: [tasks/WP04-merge-site-resolver.md](tasks/WP04-merge-site-resolver.md) (~200 lines).

### WP05 — Auto-rebase managed-artifact rule
- **Goal**: the lane sync after a coordination commit, and consolidate's auto-rebase, resolve primary-owned bookkeeping to the coordination or mission side under `R-PRIMARY-OWNED-BOOKKEEPING` (FR-008).
- **Subtasks**: T018, T019, T020, T021.
- **Dependencies**: WP01.
- **Prompt**: [tasks/WP05-auto-rebase-primary-owned-rule.md](tasks/WP05-auto-rebase-primary-owned-rule.md) (~130 lines).

### WP06 — Decision records and operator docs
- **Goal**: a new ADR, two amendments, the recovery how-to, the CHANGELOG entry and an architecture note (FR-010, the Assumptions residuals).
- **Subtasks**: T022, T023, T024, T025.
- **Dependencies**: WP02, WP04, WP05 (the docs describe shipped behaviour).
- **Prompt**: [tasks/WP06-decision-records-and-docs.md](tasks/WP06-decision-records-and-docs.md) (~160 lines).

## Dependency graph

```
WP01 ──┬──> WP02 ─────────────┐
       ├──> WP03 ──> WP04 ────┼──> WP06
       └──> WP05 ─────────────┘
```

**MVP**: WP01 + WP02 fixes every future upgrade. WP03 to WP05 make already-broken missions recover. WP06 documents both.
