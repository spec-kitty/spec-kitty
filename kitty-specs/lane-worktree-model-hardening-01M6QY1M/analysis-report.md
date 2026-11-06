---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: lane-worktree-model-hardening-01M6QY1M
mission_id: 01M6QY1MKKW6AA3EBKSJ0VVAMP
generated_at: '2026-11-06T09:38:57.912116+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/lane-worktree-model-hardening-01M6QY1M/spec.md
    sha256: e4c4c78a12e2af4c8edaf2c4a83d1d988d4c297ecc685268d2cea353929476f3
  plan.md:
    path: kitty-specs/lane-worktree-model-hardening-01M6QY1M/plan.md
    sha256: 8667aa883eeb1c8ce21eb757fbd099c21ed1fdd5ea9b1fc6f1714a6a334d5ee6
  tasks.md:
    path: kitty-specs/lane-worktree-model-hardening-01M6QY1M/tasks.md
    sha256: 8efa57e76b0ac4077b9fe8622957c2f6c8600f487605239e12c5baf12a669c2c
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  critical: 0
  high: 0
  low: 2
  medium: 1
  info: 0
findings:
- id: H1
  severity: medium
  category: underspecification
  summary: 'No artifact defines what the PRIMARY placement (WP05 read door, WP14 resolution.py arm, keyed on topology_source: default -> meta.mission_branch) returns after consolidate has landed and torn down the topic branch; WP20 T121 flips run.target_feature_dir to the target after the landing through a consolidate-local executor.py hunk, which risks a second placement decision beside the seam, and later readers (accept, status, doctor) have no post-landing answer.'
- id: H2
  severity: low
  category: underspecification
  summary: FR-062/WP20 describe the dropped window as 'after the landing read the tip, up to the teardown'; the existing ProjectionTeardownGate already CAS-refuses coordination commits after the projection captured its tip, so the unguarded span is landing-read to projection-capture (plus the resumed late window). T118 should localize it.
- id: H3
  severity: low
  category: inconsistency
  summary: Plan IC-18, WP20 and the analyze-2 trace say lands_mission_branch has six callers; a seventh, in-module caller exists (single_branch_landing.expected_consolidate_checkout:129). The unchanged-predicate pin covers it, so the risk is low.
---

## Specification Analysis Report (re-run 3)

Mission `lane-worktree-model-hardening-01M6QY1M`. Reviewer profile: reviewer-renata. Inputs: spec.md (86048ac68a), tasks.md and tasks/WP01-WP20 (5c211877d5, finalize-tasks re-run, lanes.json planning_commit_sha 86048ac68a), plan.md and traces (cb9d01928f), data-model.md, research.md, `.kittify/charter/charter.md`, and the consolidation code WP20 touches (`consolidation/executor.py`, `phase_advance.py`, `phase_teardown.py`, `run_state.py`, `bookkeeping_projection.py`, `lanes/single_branch_landing.py`, `coordination/teardown.py`). Non-remediating.

### Prior findings: verification

| ID | Prior severity | Status | Evidence |
|----|---------------|--------|----------|
| G1 | medium | Resolved | FR-062 now names `_phase_mission_to_target` -> `integrate_mission_into_target` as the landing seam and aims at PRIMARY commits after the landing read the tip. Code confirms the order: `executor.py:613-620` runs `_phase_bake_and_pre_target_done` -> `_phase_mission_to_target` -> `_phase_capture_and_baseline` -> `_phase_record_done_and_project`, and `phase_advance.py:552-563` calls `integrate_mission_into_target`. WP20 T118 is a committed characterization test that decides the design, and red-first runs on WP20's own lane base, not the planning base. Precision note: H2. |
| G2 | medium | Resolved | T121 forbids widening `project_post_checkpoint_commits_to_target`. `bookkeeping_projection.py:664-708` documents the exclusion (the "WP10 integration fix" for `mission_number` and `baseline_merge_commit`). WP20 adds `test_target_authored_mission_number_and_baseline_survive` and `test_post_checkpoint_projection_still_excludes_primary_kinds`. |
| G3 | medium | Resolved | A separate `lands_topic_branch` predicate is required, and `lands_mission_branch` stays byte-unchanged with a pin. The cited callers are confirmed at `executor.py:456, 953`, `phase_advance.py:328, 582` and `phase_teardown.py:792, 850`. A seventh caller inside the module is missed (H3). |
| G4 | medium | Resolved as ownership; edge remains (H1) | WP20 T121 Window C owns `run.target_feature_dir` (`executor.py:446`, `placement_seam(...).read_dir(PRIMARY_METADATA)`) and `_is_coord_topology_mission` (`run_state.py:488-506`, target meta `coordination_branch`). Both are recorded as out-of-map edits in WP15. The integration test `test_default_mission_consolidate_detects_coord_topology_and_bakes_on_target` was added. |
| G5 | low | Resolved | WP07, WP11 and WP15 each carry a "Later recorded out-of-map hunk by WP20" line. |
| G6 | medium | Resolved | FR-092, C-002, the User Story 9 independent test, SC-011 and Dependencies now say "delivered externally by open-packs PR #128 (merged, main 9013b34); the core pin bump is an open operator decision at pre-PR time". Plan IC-17 withdraws `test_pack_patch_applies_to_pinned_tree`. WP18 and WP19 match. The WP19 body is kept for the record under a TO BE CANCELED banner. The issue-matrix row is recorded when WP19 is canceled. |
| G7 | low | Resolved | C-004 reads "FR-037, with FR-036 and FR-039, after #7275". |
| G8 | low | Resolved | `orchestrator_api/consolidation.py` is listed as a conditional out-of-map edit (WP15). Pinning current behaviour is preferred and no new error code is added. |

### Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| H1 | Underspecification | MEDIUM | spec FR-061 ("until `consolidate` lands it"), FR-062; tasks/WP05 (read door, l.91), WP14 T088 (`resolution.py` default-PRIMARY arm), WP20 T121 Window C; `executor.py:446`; `run_state.py:505` | FR-061's placement keys on the stored `topology_source: default` and `meta.mission_branch`. No artifact says what the read door and the `resolution.py` arm return once `consolidate` has landed the topic branch and deleted it. WP20 T121 makes `run.target_feature_dir` "resolve the Mission's PRIMARY anchor before the landing ... and the target after it" through an `executor.py` hunk gated on `lands_topic_branch`. That puts a consolidate-local placement decision beside the seam, which FR-061 says carries the change "as one change" (charter: single canonical authority). Readers after consolidate (accept, status, doctor, `agent context resolve`) get no defined answer. | Before WP14 and WP20 are claimed, define the landed signal once: for example, the stored landed state, or meta flattened by `_flatten_coordination_metadata_after_branch_delete`. The placement seam (WP14's arm) should return the target after landing. WP20's `executor.py` hunk then only re-reads the seam after `_phase_mission_to_target`. Add the seam's answer before and after landing and teardown to T118 Window C. Add a post-consolidate `agent context resolve` assertion to WP14 or WP20. |
| H2 | Underspecification | LOW | spec FR-062; plan IC-18; WP20 Objectives "The real window"; `coordination/teardown.py:105-124` (`ProjectionTeardownGate.expected_coord_sha`) | The teardown already compare-and-swaps the coordination tip against the tip the projection captured, so a commit after that capture refuses with `PROJECTION_TEARDOWN_ABORTED`. The silently dropped span is from the landing's tip read to the projection's capture: a PRIMARY path there falls in `checkpoint..tip`, but `_post_checkpoint_mission_paths` filters it out. The resumed late window is also dropped. "Up to the teardown" overstates the gap. | Have T118 Window B inject at the landing-to-projection boundary and after projection, and pin the existing refusal for the second case. |
| H3 | Inconsistency | LOW | plan IC-18 Approach; tasks/WP20 Context ("six callers"); traces/design-decisions.md G3 entry; `lanes/single_branch_landing.py:129` | `expected_consolidate_checkout` also calls `lands_mission_branch`. The predicate is unchanged, so behaviour holds. Only the inventory is incomplete. | Say "seven callers, including `expected_consolidate_checkout`", or leave the count out. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 to FR-007 (S1) | Yes | WP01, WP04-WP07 | |
| FR-010 to FR-014 (S2) | Yes | WP08 | |
| FR-020 to FR-022 (S3) | Yes | WP03, WP09 | |
| FR-030 to FR-039a (S5) | Yes | WP03, WP15, WP16 | WP16 has an exit rule |
| FR-040 to FR-046 (S6) | Yes | WP01, WP04, WP06, WP09, WP10 | |
| FR-050 to FR-061 (S7) | Yes | WP02, WP05, WP13, WP14, WP20 | FR-061 post-landing answer: H1 |
| FR-062 | Yes | WP20 | re-aimed; H1, H2 |
| FR-070 to FR-078 (S8) | Yes | WP02, WP11, WP12 | |
| FR-080 to FR-084 (S9) | Yes | WP03 | |
| FR-090, FR-091, FR-093 | Yes | WP17, WP18 | |
| FR-092 | Delivered externally | open-packs PR #128; WP19 to be canceled | spec amended |
| NFR-001 to NFR-010 | Yes | WP05, WP07, WP09, WP10, WP12, WP14-WP16, all code WPs | |
| SC-001 to SC-012 | Yes | various | SC-011 measures the core half only |

**Charter Alignment Issues:** none. H1 is a risk to single canonical authority, not a violation, because no WP prescribes a second resolver. It is graded medium for that reason.

**Unmapped Tasks:** none.

**Metrics:**

- Total Requirements: 64 FR + 10 NFR + 17 C + 12 SC
- Total Tasks: 20 WPs (WP19 to be canceled) / 123 subtasks
- Coverage % (requirements with >=1 task): 100% (FR-092 by an external delivery)
- Ambiguity Count: 0
- Duplication Count: 0
- Critical Issues Count: 0

### Next Actions

- No critical or high finding. Implementation may proceed with WP01-WP03 and WP08.
- H1: before WP14 is claimed, settle the post-landing placement answer through `/spec-kitty.tasks` refinement (WP14 T088, WP20 T121/T118) and an FR-061 sentence. Then re-run finalize-tasks and `/spec-kitty.analyze`.
- H2 and H3 are optional wording fixes.
- The core pack pin bump stays an open operator decision at pre-PR time (not a finding).
