---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: lane-worktree-model-hardening-01M6QY1M
mission_id: 01M6QY1MKKW6AA3EBKSJ0VVAMP
generated_at: '2026-11-06T09:31:29.812511+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/lane-worktree-model-hardening-01M6QY1M/spec.md
    sha256: 78fc02f43dae1313ba126d8d42d2779f4288cb9783e832de388ffa42b89a4e83
  plan.md:
    path: kitty-specs/lane-worktree-model-hardening-01M6QY1M/plan.md
    sha256: 51f73ae841f9888a95b0f35194ccda0e3dd2902550b9d0c86b7b3f83e773cc7e
  tasks.md:
    path: kitty-specs/lane-worktree-model-hardening-01M6QY1M/tasks.md
    sha256: 59577af97c278c8554fa6180dbd437dcc8c83bbf5d971aeafc2be8c788ca38cb
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  medium: 5
  critical: 0
  high: 0
  low: 3
  info: 0
findings:
- id: G1
  severity: medium
  category: inconsistency
  summary: "WP20/FR-062/IC-18 premise mis-aimed: a coord Mission's lanes.json mission_branch IS the coordination (topic) branch and _phase_mission_to_target already squashes it onto the target via integrate_mission_into_target, so post-last-cut PRIMARY edits already land; the unlanded window is post-checkpoint PRIMARY commits that _post_checkpoint_mission_paths excludes. FR-062 names the wrong seam (single_branch_landing.py) and WP20's 'red on the planning base' is vacuous."
- id: G2
  severity: medium
  category: underspecification
  summary: "WP20 T121's option to widen project_post_checkpoint_commits_to_target to PRIMARY kinds reintroduces the regression its guard documents: stale coordination-ref copies of meta.json clobber the target-authored mission_number bake and baseline_merge_commit stamp. No test pins those values survive."
- id: G3
  severity: medium
  category: inconsistency
  summary: Plan IC-18 says lands_mission_branch 'gains the default-settled lanes_with_coord arm'; that predicate has six callers with single_branch semantics, incl. executor.py:456/953 (WP15-owned, not recorded as out-of-map) and phase_advance.py:328 done_marked_before_target. WP20 leaves 'beside or one predicate' open.
- id: G4
  severity: medium
  category: coverage
  summary: 'Consolidate-time PRIMARY anchor handover for a default Mission is unowned: consolidate reads meta/lanes through run.target_feature_dir and detects coord topology from coordination_branch in target meta (run_state._is_coord_topology_mission); for a default Mission those files live on the topic branch until landed, and post-teardown phases need them on the target.'
- id: G6
  severity: medium
  category: inconsistency
  summary: "Spec FR-092, SC-011 (pack half) and Dependencies still require a patch file in this Mission and a core pin bump, while plan IC-17 and tasks cancel WP19 (open-packs PR #128) and bump no pin; SC-011's 'patch applies cleanly' is untestable as written."
- id: G5
  severity: low
  category: inconsistency
  summary: WP20's out-of-map hunks are recorded in tasks.md and WP20 only; owner prompts WP07 (phase_advance.py), WP11 (single_branch_landing.py) and WP15 (phase_teardown.py) do not mention them.
- id: G7
  severity: low
  category: inconsistency
  summary: "C-004's interim exception names 'the S5 guard binding (FR-036, after #7275)'; the binding is FR-037 (FR-036 is pr-mode cleanup)."
- id: G8
  severity: low
  category: underspecification
  summary: WP20's test_primary_landing_through_orchestrator_api may need a hunk in orchestrator_api/consolidation.py (WP15-owned), which is not listed as a recorded out-of-map edit.
---

## Specification Analysis Report (re-run 2)

Mission `lane-worktree-model-hardening-01M6QY1M`. Reviewer profile: reviewer-renata. Inputs: spec.md, plan.md, tasks.md, tasks/WP01-WP20, data-model.md, contracts/, research.md, lanes.json, the 19 resolved Decision Moments, `.kittify/charter/charter.md`, and the consolidation sources WP20 extends (`lanes/single_branch_landing.py`, `lanes/consolidation.py`, `consolidation/phase_advance.py`, `phase_teardown.py`, `bookkeeping_projection.py`, `run_state.py`). Non-remediating.

### Prior findings: verification

| ID | Prior severity | Status | Evidence |
|----|---------------|--------|----------|
| D1 | critical | Resolved | WP04 T017: commit 1 = `942ff4aed9` alone (path-limited `-x`), then fix and style commits separately; "never `cherry-pick -n` across both". |
| E1 | high | Resolved as coverage (FR-062, IC-18, WP20); soundness concerns remain, see G1-G4 | WP20 owns `bookkeeping_projection.py`, depends on WP07, WP14, WP15. |
| F1 | medium | Resolved | WP04 depends on WP01; WP09 on WP01, WP03, WP08. |
| E2 | medium | Resolved | NFR-008 sections in WP10 and WP15. |
| C1 | medium | Resolved | WP06, WP13, WP16 run the matching `tests/specify_cli/cli/commands/test_*` selections. |
| F2 | medium | Resolved | WP15 is the single 1.24.0 owner; WP13 and WP14 depend on WP15 and do not edit `envelope.py` or the doc page. |
| C2 | medium | Resolved | WP16 exit rule in tasks.md and spec Dependencies. |
| F3 | low | Resolved | spec, plan and tasks say 19; the decision list has 19 resolved. |
| F4 | low | Resolved | Spec Dependencies reworded; WP04 adds `test_registry_unreadable_repository_root_caller`. |
| F5 | low | Resolved | WP07 and WP10 both record the `transaction.py` hunk. |
| E3 | low | Resolved | WP16 `test_prune_second_run_changes_nothing`, `--durations=5`. |
| B1 | low | Resolved | WP19 cites `upstream/doctrine-and-write-service-adr-map.md` Part 1; "destructive-op routing pins". |
| F6 | low | Resolved (wording slip, G7) | C-004 records the s5-seam interim exception. |

### Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| G1 | Inconsistency | MEDIUM | spec FR-062; plan IC-18 "Why"; tasks/WP20 Context, T119; `consolidation/phase_advance.py::_phase_mission_to_target`; `lanes/consolidation.py:340`; `bookkeeping_projection.py:664` | For coordination topologies the Mission branch and the coordination branch are the same ref (`kitty/mission-<slug>-<mid8>`; `single_branch_landing.authorship_window` docstring). `_phase_mission_to_target` squashes that whole branch onto the target through `integrate_mission_into_target` before teardown. A PRIMARY edit committed on the topic branch after the last lane cut, but before `consolidate`, therefore already lands, and WP20's scenario (a) is likely green once WP14 exists. The window that is really dropped is PRIMARY commits on the coordination ref after the transaction checkpoint, which `_post_checkpoint_mission_paths` excludes on purpose. FR-062 also names `lanes/single_branch_landing.py` as "the existing mission-branch landing seam", but the seam that lands a coordination Mission is `integrate_mission_into_target`. "Red on the planning base" is vacuous for a WP that needs WP14's settlement to build its fixture. | Make T118's characterization decide the design before any implementation subtask. Point the red-first tests at the post-checkpoint window and at meta.json (`meta_two_way`), and require them to be red on WP20's own lane base (after WP14). Name `integrate_mission_into_target` / `_phase_mission_to_target` in FR-062 and IC-18. If T118 shows nothing is lost, WP20 reduces to pins. |
| G2 | Underspecification | MEDIUM | tasks/WP20 T121; `bookkeeping_projection.py:664-690` (docstring "WP10 integration fix") | T121 offers "a widened `project_post_checkpoint_commits_to_target` limited to `_PRIMARY_ARTIFACT_KINDS`". The function excludes PRIMARY kinds because the coordination ref carries stale pre-merge copies, and projecting them would overwrite the `mission_number` bake and `baseline_merge_commit` stamp that the run commits on the target. Following that option breaks NFR-002 / "lose nothing" on the target side. | Drop that option, or allow it only for paths that the run did not author on the target, with a 3-way check against the checkpoint. Add a test that `mission_number` and `baseline_merge_commit` survive a default-Mission consolidate. |
| G3 | Inconsistency | MEDIUM | plan IC-18 Approach; tasks/WP20 T120; callers `executor.py:437-456, 942-953`, `phase_advance.py:328, 582`, `phase_teardown.py:789-792, 846-850` | Widening `lands_mission_branch` also changes `planning_artifact_only` (executor, WP15-owned, not a recorded out-of-map edit), `done_marked_before_target`, and the switch, clear and delete paths of `mission_branch`, all of which have `single_branch` semantics. WP20 leaves the choice open ("beside ... or one predicate"). | Require a separate predicate (for example `lands_topic_branch_primary`) and leave `lands_mission_branch` unchanged. Otherwise list each caller's intended behaviour for default `lanes_with_coord` and record `executor.py` as an out-of-map edit. |
| G4 | Coverage | MEDIUM | spec FR-061/FR-062; tasks/WP05 T026, WP14 T088, WP20; `run_state.py:488` `_is_coord_topology_mission`; `phase_advance.py:319-321` (`run.target_feature_dir`) | Consolidate reads `meta.json` and `lanes.json` through `run.target_feature_dir`, and it detects coordination topology from `coordination_branch` in that meta. For a default Mission those PRIMARY files live on the topic branch until they land. The post-teardown phases (`mission_number` bake, baseline stamp, retrospective, `_clear_landed...`) need them on the target. WP05 places status reads (`CONSOLIDATED_TARGET`) and WP14 places PRIMARY before and after settlement, but no WP owns the handover of the PRIMARY anchor during the consolidate run. | Give it to WP20, with `run_state.py` and the bookkeeping-phase hunks as recorded out-of-map edits, or to WP05. Add an integration test that a default `lanes_with_coord` consolidate detects coordination topology, tears down the coordination triple, and bakes `mission_number` on the target. |
| G6 | Inconsistency | MEDIUM | spec FR-092, SC-011, C-002, Dependencies "pack pin bump in core follows"; plan IC-17; tasks WP19 | The plan and tasks say FR-092 is delivered by open-packs PR #128, WP19 is canceled, and no pin bump happens. The spec still requires a patch file in this Mission and a later pin bump, and SC-011 measures "the pack patch applies cleanly". | Amend FR-092, SC-011 and the Dependencies bullet to "delivered by spec-kitty-open-packs PR #128; no core pin bump in this Mission". Record the issue-matrix row when WP19 is canceled. |
| G5 | Inconsistency | LOW | tasks/WP07, WP11, WP15 prompts | WP20's out-of-map hunks are recorded in tasks.md and WP20 only. The owners precede WP20, so the risk is low. | Add one line to each owner WP naming WP20's later hunk. |
| G7 | Inconsistency | LOW | spec C-004 | "S5 guard binding (FR-036, after #7275)": the binding is FR-037. | Say "FR-037 (and FR-036/FR-039), after #7275". |
| G8 | Underspecification | LOW | tasks/WP20 T119 (`test_primary_landing_through_orchestrator_api`) | Parity, or a pinned `PREFLIGHT_FAILED`, may need code in `orchestrator_api/consolidation.py` (WP15-owned), which is not listed. | List it as a possible recorded out-of-map edit, or state that the test only pins current behaviour. |

### WP20 checks requested

- **Carries every PRIMARY change before teardown, no loss on resume or rollback?** Not as written: see G1 (the wrong window), G2 (clobber hazard) and G4 (anchor handover). Rollback stays on `rollback_to_snapshot`, `advance_branch_ref` is used inside the recorded span, and no new error code is added: sound.
- **Sequenced after WP07, WP14, WP15?** Yes. Frontmatter `dependencies: [WP07, WP14, WP15]`; lanes.json lane-p depends on lane-d (WP07), lane-k (WP14) and lane-l (WP15). WP11 is reached transitively through WP14 -> WP12 -> WP11. WP17 depends on WP20.
- **Out-of-map edits recorded in the owner WPs?** Recorded in the tasks.md shared-file table and in WP20; not in WP07, WP11 or WP15 (G5). `executor.py` (WP15) is affected through the predicate but not recorded (G3).
- **owned_files**: no duplicates across WP01-WP20.

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 to FR-007 (S1) | Yes | WP01, WP04-WP07 | |
| FR-010 to FR-014 (S2) | Yes | WP08 | |
| FR-020 to FR-022 (S3) | Yes | WP03, WP09 | |
| FR-030 to FR-039a (S5) | Yes | WP03, WP15, WP16 | WP16 has an exit rule |
| FR-040 to FR-046 (S6) | Yes | WP01, WP04, WP06, WP09, WP10 | |
| FR-050 to FR-061 (S7) | Yes | WP02, WP05, WP13, WP14, WP20 | |
| FR-062 | Yes | WP20 | soundness concerns G1-G4 |
| FR-070 to FR-078 (S8) | Yes | WP02, WP11, WP12 | |
| FR-080 to FR-084 (S9) | Yes | WP03 | |
| FR-090, FR-091, FR-093 | Yes | WP17, WP18 | |
| FR-092 | Yes, external | WP19 (to be canceled), open-packs PR #128 | spec not updated (G6) |
| NFR-001 to NFR-010 | Yes | WP05, WP07, WP09, WP10, WP12, WP14-WP16, all code WPs | |
| SC-001 to SC-012 | Yes | various | the SC-011 pack half is untestable as written (G6) |

**Charter Alignment Issues:** none. D1 is resolved. G1's vacuous red-first evidence weakens ATDD-first for WP20 but does not violate a MUST, because T118 characterization and "never retry-to-green" stay binding.

**Unmapped Tasks:** none.

**Metrics:**

- Total Requirements: 64 FR + 10 NFR + 17 C + 12 SC
- Total Tasks: 20 WPs (WP19 to be canceled) / 123 subtasks
- Coverage % (requirements with >=1 task): 100%
- Ambiguity Count: 0
- Duplication Count: 0
- Critical Issues Count: 0

### Next Actions

- No critical or high finding: implementation may start with WP01-WP03 and WP08.
- Before WP20 is claimed, fix G1-G4 in the WP20 prompt and plan IC-18 (and the FR-062 seam name) through `/spec-kitty.tasks` refinement, then re-run `finalize-tasks` and `/spec-kitty.analyze`. WP20 is the last code lane before WP17, so there is time.
- G6: amend spec FR-092, SC-011 and Dependencies through `/spec-kitty.specify` refinement.
- The low findings are optional.
