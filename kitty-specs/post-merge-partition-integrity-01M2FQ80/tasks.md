# Tasks: Post-merge partition integrity (#3942 + #4090 + #4091)

**Mission**: `post-merge-partition-integrity-01M2FQ80` | **Branch**: `issue-3942-merge-surface-authority`
**Spec**: `./spec.md` | **Plan**: `./plan.md` (locked design decisions, post-brownfield-squad)

Two file-disjoint tracks, parallel. Track A = squash **write** authority (#3942). Track B = post-merge **read** authority (#4090, folding #4091). Each track is red-first: the repro WP must be RED on HEAD `ecbf036328` before its fix WP.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first pytest driving real `integrate_mission_into_target(SQUASH)`; assert target-newer primary-artifact-kind file survives (RED on HEAD) | WP01 | [P] |
| T002 | Confirm & document RED on HEAD; mark xfail-strict so suite stays green pending WP02 | WP01 | |
| T003 | Net-new pure three-way recency helper (`merge-base`/target-vs-lane divergence) + standalone unit test | WP02 | |
| T004 | Capture pre-squash target bytes for primary-artifact-kind files (sibling of gate capture) | WP02 | |
| T005 | Extend post-squash restore to write back target-newer primary-artifact-kind files; report divergence (FR-002) | WP02 | |
| T006 | Amend `lanes/merge.py:631-633` authoritative-comment; flip WP01 test green (remove xfail) | WP02 | |
| T007 | Keep #2709/#2804 driver suites green (FR-003); complexity ≤15 census on touched fns | WP02 | |
| T008 | Red-first test: constructed post-merge state (primary 11 done, no `merged_at`; coord husk 11 approved) drives REAL retrospect AND REAL doctor to disagreement (RED on HEAD) | WP03 | [P] |
| T009 | Restore `merged_at` (+`merged_commit`) writer beside `record_baseline_merge_commit` (meta-write authority) | WP04 | |
| T010 | Make `is_mission_merged` reopen-aware via `_last_reopen_at` (merged iff `merged_at` present AND no later `MissionReopened`) | WP04 | |
| T011 | Focused tests: writer unit test; retrospect≡doctor agreement (flip T008 green); reopened-mission NOT merged; `runtime_bridge` :1600 terminal short-circuit for merged mission | WP04 | |
| T012 | #4091 coord-fixture repro: `event_count` vs unioned `status.events.jsonl` after `_project_status_bookkeeping_to_target` (RED-or-verify) | WP05 | |
| T013 | If RED: reconcile the count measure; if GREEN on HEAD: verify-and-close #4091 with citation (no phantom fix) | WP05 | |
| T014 | FR-009 cross-track synthesis doc (`docs/architecture/post-merge-partition-authority.md`): #2709→#3942 lineage, dead-`conflict_resolver.py` disposition for #2907, D-B1 husk-override authority note for #2160 | WP06 | |
| T015 | Combined regression (both red-first tests green + preserved #2709/#2804/#3981 suites); NFR-003 complexity census; CHANGELOG entries | WP06 | |

## Work Packages

### WP01 — Track A red-first: squash clobbers target-newer planning file
**Goal**: Prove #3942 LIVE on HEAD with a real-path repro. **Priority**: P1. **Deps**: none.
**Independent test**: `pytest tests/merge/test_squash_target_newer_planning_3942.py` is RED on HEAD (target-newer `spec.md`/`WP01.md` clobbered), green only after WP02.
Subtasks: T001, T002. Prompt: `tasks/WP01-track-a-red-first-clobber.md`

### WP02 — Track A fix: kind-aware target-newer restore on squash
**Goal**: Preserve target-newer primary-artifact-kind files on squash; report divergence; preserve driver/gate behavior. **Priority**: P1. **Deps**: WP01.
**Independent test**: WP01 test green; #2709/#2804 suites green; recency-helper unit test green.
Subtasks: T003, T004, T005, T006, T007. Prompt: `tasks/WP02-track-a-kind-aware-restore.md`

### WP03 — Track B red-first: retrospect vs doctor disagreement
**Goal**: Prove #4090 LIVE on HEAD with the REAL retrospect + doctor readers disagreeing on a constructed post-merge state. **Priority**: P1. **Deps**: none.
**Independent test**: `pytest tests/specify_cli/cli/commands/test_retrospect_doctor_surface_4090.py` is RED on HEAD.
Subtasks: T008. Prompt: `tasks/WP03-track-b-red-first-disagreement.md`

### WP04 — Track B fix: restore merged_at writer + reopen-aware guard
**Goal**: Write `merged_at` at merge completion AND make `is_mission_merged` reopen-aware so retrospect≡doctor for merged (and reopened) missions. **Priority**: P1. **Deps**: WP03.
**Independent test**: WP03 test green; reopened-mission-not-merged test green; runtime-bridge short-circuit test green; `test_lifecycle` green.
Subtasks: T009, T010, T011. Prompt: `tasks/WP04-track-b-merged-at-writer-reopen-aware.md`

### WP05 — #4091 contingent: event_count union consistency
**Goal**: Repro #4091 on a coord fixture; reconcile if RED, verify-and-close if GREEN on HEAD. **Priority**: P2. **Deps**: WP04.
**Independent test**: `pytest tests/merge/test_event_count_union_4091.py` — outcome documented (fix or verify-close).
Subtasks: T012, T013. Prompt: `tasks/WP05-issue-4091-event-count-union.md`

### WP06 — Cross-track synthesis + green consolidation
**Goal**: FR-009 synthesis + NFR-003 census + combined regression + CHANGELOG. **Priority**: P2. **Deps**: WP02, WP04, WP05.
**Independent test**: synthesis doc present + cites both seams; combined regression green.
Subtasks: T014, T015. Prompt: `tasks/WP06-synthesis-and-consolidation.md`

## Dependencies

```
WP01 → WP02 ┐
WP03 → WP04 → WP05 ┤→ WP06
```
Tracks A (WP01→WP02) and B (WP03→WP04→WP05) are file-disjoint and parallel.
