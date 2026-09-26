---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: lane-branch-naming-authority-01M3EVC4
mission_id: 01M3EVC459SNRPXV6B3DX8TKHV
generated_at: '2026-09-26T14:48:22.079481+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/lane-branch-naming-authority-01M3EVC4/spec.md
    sha256: 4f37d6a37ad0629b5f1d661a596795a07a8aed87ffe515d2d3d9e3cc0b0fd688
  plan.md:
    path: kitty-specs/lane-branch-naming-authority-01M3EVC4/plan.md
    sha256: ea0ef8a02b294527140c349a61d29e8bd4c58889e050c4799400282ac2a71e0d
  tasks.md:
    path: kitty-specs/lane-branch-naming-authority-01M3EVC4/tasks.md
    sha256: fee5cd45cfd992ea79cf8305278e8c378ae23c1f92ea54d85d7e33c8693c7fc2
  charter:
    path: .kittify/charter/charter.yaml
    sha256: a2b2f62cf1c0fa8987b67f6759d18bcc18b2fb47a8d3ad2783f8fac68b192c77
verdict: ready
issue_counts:
  high: 0
  medium: 3
  low: 9
  critical: 0
  info: 0
findings:
- id: C1
  severity: medium
  category: coverage
  summary: NFR-004 (diff coverage >= 90%) is named only in WP01/WP02/WP04 prompts; 7 code WPs (WP03, WP05, WP06, WP07, WP09, WP10, WP11) omit it although tasks.md claims NFR-002..005 are in every code WP's gates section.
- id: U1
  severity: medium
  category: underspecification
  summary: 'FR-011 typed refusal is not delivered for finalize: untouched compute_lanes still calls mission_branch_name(slug, mission_id) and raises a raw ValueError for an identity < 8 chars before _preserved_mission_branch runs; PD-14 sidesteps it by hand-writing lanes.json in the fixture.'
- id: K1
  severity: medium
  category: inconsistency
  summary: Spec C-005 requires any other lane-creation site to be folded into FR-006, but research ADJ-7 / plan Risk 6 / tasks follow-ups defer the review-workspace creation path (cli/commands/agent/workflow.py:1691); spec rev 3 folded ADJ-1..6 only and C-005 was not amended.
- id: I1
  severity: low
  category: inconsistency
  summary: plan.md Parallel Work Analysis (graph, Work Distribution, parallel line, Coordination Points) and Scale/Scope still describe the 9-WP layout; tasks.md has 11 WPs with moved ownership. The deviations are recorded in tasks.md (deviations 1-8).
- id: I2
  severity: low
  category: inconsistency
  summary: 'plan.md holds stale WP references that tasks.md does not record: Risk 1 puts the SC-001 end-to-end proof in WP02 (now WP03/T043), Risk 4 names WP07 for concurrent materialization (now WP09/T025), Charter Check says architectural suite runs for WP06 (now WP11), and the header cites spec rev 2 (spec is rev 3).'
- id: I3
  severity: low
  category: inconsistency
  summary: 'research.md Part A section 7/8 use a different WP numbering (WP03 = lane consumers, WP04 = match sites, WP06 = cutover + sibling gate file test_lane_naming_authority_gate.py, WP07 = #5113) that conflicts with tasks.md; only the kwarg-drop claim and the gate file are corrected in tasks.md.'
- id: I4
  severity: low
  category: inconsistency
  summary: 'Test call-site counts disagree: plan Gate Baseline ~72 in 19 files, plan Risk 3 ~61, research 61, WP07 measured 64 calls in 19 test files at HEAD 8900c2cb.'
- id: I5
  severity: low
  category: inconsistency
  summary: tasks.md deviation 3 says the quickstart names a stale gate file, but quickstart.md already names test_no_worktree_name_guess.py; quickstart also omits several new verification modules (test_merge_divergent_end_to_end.py, test_lane_match_sites.py, test_coordination_remedy_5113.py, test_lane_naming_gate_sites.py).
- id: I6
  severity: low
  category: inconsistency
  summary: 'Gate baseline drift: plan targets _NAME_COMPOSE_BASELINE_RAW_MATCHES 5 -> 4, WP11 targets 5 -> 3; and the plan baseline is measured over src/specify_cli only while FR-009/WP11 also scan src/runtime, so NFR-003 has no recorded src/runtime number.'
- id: A1
  severity: low
  category: ambiguity
  summary: SC-003/FR-009 require 0 compose sites outside the authority, while WP11 caps the compose allow-list at 1 (lanes/compute.py::_next_free_lane_id, which mints a lane id, not a name). This is consistent with the Domain Language definition, but the '0' reads ambiguously next to a non-empty allow-list.
- id: U2
  severity: low
  category: underspecification
  summary: WP03 allows open-ended out-of-map fixes to WP01/WP02-owned files (executor.py, reconciliation.py) for residual non-naming failures ('a few lines'). The WP07/WP11 out-of-map edits are bounded by explicit tables; this one is not.
- id: D1
  severity: low
  category: duplication
  summary: tasks.md Requirements Coverage Summary lists NFR-003 twice (inside 'NFR-002..005' and as its own row) and maps only C-006 among constraints C-001..C-008.
---

## Specification Analysis Report

Mission: `lane-branch-naming-authority-01M3EVC4`. Artifacts analysed: spec.md (rev 3), plan.md, tasks.md, tasks/WP01–WP11, data-model.md, research.md (ADJ-1..7, Part A, Part B), quickstart.md, `.kittify/charter/charter.md`. Reviewed as reviewer-renata (quality gate, non-remediating).

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Coverage | MEDIUM | tasks.md:423; WP03/05/06/07/09/10/11 prompts | NFR-004 (diff coverage ≥ 90%) appears only in the WP01, WP02 and WP04 prompts. tasks.md says NFR-002..005 are covered by "every code WP (gates section)", which is not true for NFR-004. The CI diff-cover gate still enforces it. | Add "diff coverage ≥ 90% on changed lines" to the Definition of Done / quality-gate section of the seven code WPs that lack it. |
| U1 | Underspecification | MEDIUM | spec.md:146 (FR-011); plan.md:52 (PD-14), :19; WP06 T021; src/specify_cli/lanes/compute.py:715 | FR-011 says a Mission-branch consumer must refuse "with a typed error rather than crashing when it must recompose from an invalid identity". `compute_lanes` is not edited and calls `mission_branch_name(slug, mission_id=…)` first, so `_mid8` raises a raw `ValueError` for an identity shorter than 8 characters. This happens on first finalize and on re-finalize, before `_preserved_mission_branch` runs. PD-14 works around it by hand-writing `lanes.json` in the < 8 fixture. | Either amend FR-011 to scope the typed refusal to post-manifest consumers and record that finalize with a < 8 identity is out of scope, or have WP06 convert the `ValueError` into `BranchIdentityUnresolved` in `compute_and_write_lanes`, around the `compute_lanes` call, without editing `compute_lanes`. |
| K1 | Inconsistency | MEDIUM | spec.md:169 (C-005); research.md:15 (ADJ-7), :132; plan.md:162; tasks.md:499 | C-005 says "any other creation site is folded into FR-006". The review-workspace path (`cli/commands/agent/workflow.py:1691`) creates lane branches outside the allocator, and research and planning defer it to a follow-up. Its naming is compliant: it gets its name from `lane_branch_name` via `workspace/context.py:911`, which WP07 migrates. Invariant I-1 therefore holds, but the spec constraint and the adjudication disagree and the spec was not amended. | Amend C-005 (or add ADJ-7 to spec's folded adjudications) so it says that a creation site with compliant naming outside the allocator is a recorded follow-up. Otherwise, fold it into a WP. |
| I1 | Inconsistency | LOW | plan.md:20, :114-153 | The plan's dependency graph, work distribution, parallel line and coordination points describe 9 WPs. tasks.md has 11: WP09 split into WP09 + WP10 and WP07 split into WP07 + WP11. Several items also moved: H5 from WP03 to WP02, the recovery fallback from WP03 to WP04, the drift matcher and `detection.py` from WP05 to WP11, the kwarg-drop files from WP04 to WP07, and the ADR from `-1` to `-2`. | Already recorded in tasks.md deviations 1–8. Optionally refresh plan.md so readers are not misled. |
| I2 | Inconsistency | LOW | plan.md:4, :34, :157, :160 | These stale WP references are not listed in tasks.md's deviations: Risk 1 (SC-001 proof in WP02; it is now WP03/T043), Risk 4 (WP07; it is now WP09/T025, where the re-probe mitigation is carried correctly), Charter Check (architectural suite for WP06; it is now WP11), and the header "spec.md (rev 2)". | Refresh plan.md, or add these to the tasks.md deviation list. |
| I3 | Inconsistency | LOW | research.md:255-278 | Research §7/§8 uses different WP numbers and names a sibling gate file (`test_lane_naming_authority_gate.py`). tasks.md corrects only the kwarg-drop claim (deviation 2) and the gate file (deviation 3). | Mark research §7 as superseded by tasks.md. |
| I4 | Inconsistency | LOW | plan.md:20, :67, :159; research.md:264; WP07:128 | The test call-site counts disagree: ~72, ~61, 61 and 64. | Treat the WP07 AST count (64 in 19 files at `8900c2cb`) as authoritative. |
| I5 | Inconsistency | LOW | tasks.md:34; quickstart.md | Deviation 3 calls the quickstart stale, but the quickstart already names the right gate file. The quickstart also omits several new verification modules. | Correct deviation 3's wording and add the missing modules to the quickstart. |
| I6 | Inconsistency | LOW | plan.md:56-65; WP11:142; spec.md:144 | The raw-match baseline target is 5→4 in the plan and 5→3 in WP11, because WP11 also removes the placeholder. The plan's baseline covers only `src/specify_cli`, but the gate also scans `src/runtime`. | Record the `src/runtime` baseline number (NFR-003 requires "recorded in the plan"). WP11's stricter target is fine. |
| A1 | Ambiguity | LOW | spec.md:188 (SC-003); WP11:109 | "0 compose sites" sits next to a compose allow-list of 1, `_next_free_lane_id`, which mints a lane **id**. | Let the WP11 detector exclude lane-id minting, or state in SC-003 that minting a lane id is not a compose site. |
| U2 | Underspecification | LOW | WP03:104 | WP03 may make open-ended out-of-map fixes in files owned by upstream WPs. | Cap it: list the permitted files, set a line budget, and require escalation beyond that. |
| D1 | Duplication | LOW | tasks.md:422-425 | NFR-003 is listed twice, and constraints are mapped only partially. | Tidy the coverage table. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 single-lane-naming-authority | Yes | WP01 T003; WP02 T030; WP07 T049; WP08 T056 | |
| FR-002 no-naming-form-choice | Yes | WP07 T048–T049; WP11 T053 (signature leg) | |
| FR-003 reconciliation-claim-uses-authority | Yes | WP01 T002–T004; WP03 T043 | |
| FR-004 lane-tip-capture-uses-authority | Yes | WP02 T031 | |
| FR-005 resume-refuses-unanchored-tips | Yes | WP02 T032; WP03 T045 | Scoped per ADJ-2/PD-4; spec amended |
| FR-006 remaining-consumers-routed | Yes | WP02 T030/T033–T035; WP04 T009–T010; WP07 T049 | Review-workspace creation site deferred (K1) |
| FR-007 retire-dual-name-probe | Yes | WP04 T007–T008; WP11 T052 (placeholder) | |
| FR-008 match-sites-via-parsers | Yes | WP05 T013–T018; WP11 T052 | All 7 listed sites mapped |
| FR-009 non-vacuous-gate | Yes | WP11 T053–T055 | See I6, A1 |
| FR-010 stable-origin-aware-lane-identity | Yes | WP06 T023 | Re-verify only (already landed) |
| FR-011 refinalize-preserves-mission-branch | Yes | WP06 T020–T022; WP04 T011; WP03 T046 | Gap in finalize typed refusal (U1) |
| FR-012 red-first-divergent-regressions | Yes | WP01 T002; WP02 T031–T035; WP03 T043; WP04 T007/T009; WP06 T020 | |
| FR-013 decision-recording-fresh-coord | Yes | WP09 T024–T027 | |
| FR-014 truthful-unmaterialized-remedy | Yes | WP09 T028; WP10 T037–T042 | |
| NFR-001 name-stability | Yes | WP07 T050 | Golden re-pin per ADJ-1/PD-3 |
| NFR-002 complexity-ceiling | Yes | all code WPs (C901 checks present) | |
| NFR-003 gate-floor | Yes | WP11 T053 | |
| NFR-004 change-coverage | Partial | WP01, WP02, WP04 explicit | Missing in 7 code WPs (C1) |
| NFR-005 static-checks | Yes | all code WPs (ruff/format/mypy present) | |

**Charter Alignment Issues:** None found. The plan's Charter Check holds up against the charter. ATDD-first / red-first: every code WP opens with a red-first subtask through a pre-existing entry point, and `TestPlanningArtifactReachesTarget` must go green with its fixture unedited. Single canonical authority: the existing creation-side authority is extended, not duplicated. Layer direction: all changes stay in `specify_cli`, and the `runtime` / `mission_runtime` edits are remedy text only. No suppressions. The Terminology canon is clean: "feature" appears only inside literal fixture slugs such as `083-my-feature`. The `__all__` convention binds only `src/charter/` and `src/kernel/`, and both touched modules already declare `__all__`.

**Unmapped Tasks:** None. All 60 subtasks (T001–T060) roll up to WPs, and each WP carries requirement refs.

**Issue-matrix heads-up (informational, non-gating):** bare references #5108 and #5113 (spec, intended), and bare #1899, #1890 and #4762 in plan.md (PD-11, PD-10, Risk 5). These will need issue-matrix rows, a context-only marker, or a `not-applicable` verdict before approval of the owning WPs.

**Metrics:**

- Total Requirements: 19 (14 FR + 5 NFR), plus 8 constraints
- Total Tasks: 60 subtasks across 11 work packages
- Coverage: 100% (19/19 requirements with ≥ 1 task; NFR-004 only partially reflected)
- Ambiguity Count: 1
- Duplication Count: 1
- Critical Issues Count: 0

### Next Actions

- No CRITICAL or HIGH findings: verdict **ready**. Implementation may proceed.
- Recommended before or early in implementation:
  - C1: add the NFR-004 diff-coverage gate to the seven WP prompts that lack it.
  - U1: decide whether FR-011's typed refusal covers finalize. If it does, add a guard around `compute_lanes` in WP06; if not, amend FR-011.
  - K1: amend spec C-005 to record ADJ-7 (or run `/spec-kitty.specify` refinement).
- Optional hygiene: refresh the plan.md parallel-work section and risk WP references, mark research.md Part A §7 superseded, and fix the quickstart and the tasks.md coverage table.
