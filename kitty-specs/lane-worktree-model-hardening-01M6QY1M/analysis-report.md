---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: lane-worktree-model-hardening-01M6QY1M
mission_id: 01M6QY1MKKW6AA3EBKSJ0VVAMP
generated_at: '2026-11-06T09:17:39.432759+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/lane-worktree-model-hardening-01M6QY1M/spec.md
    sha256: b9ea55943ff57fa1c00e2dcfb3bbe89a3743fc74de06f0e21bbf4fe5616a43a7
  plan.md:
    path: kitty-specs/lane-worktree-model-hardening-01M6QY1M/plan.md
    sha256: 4eebb4192c5e2145e2d636265e18cb914dbc4a685a8a7140bd01f79ec01fe198
  tasks.md:
    path: kitty-specs/lane-worktree-model-hardening-01M6QY1M/tasks.md
    sha256: fa526c3bb031a57533518adc632106cf7810d165b7bb84099f9f75b8345a15a1
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: blocked
issue_counts:
  high: 1
  low: 6
  critical: 1
  medium: 5
  info: 0
findings:
- id: D1
  severity: critical
  category: charter
  summary: "WP04 T017 squashes #6884's red-first test and its fix into one first commit (cherry-pick -n), an implementation commit ahead of WP04's own red-first tests; breaks charter ATDD-first C-011 (test committed separately BEFORE any implementation commit)."
- id: E1
  severity: high
  category: coverage
  summary: FR-055/FR-061 'consolidate lands the topic branch's PRIMARY artifacts on the target' for a default lanes_with_coord Mission has no owning WP; today's projection carries only status bookkeeping and post-checkpoint coordination commits, and coordination teardown deletes the branch. WP14 T082 asserts it with no implementing file.
- id: F1
  severity: medium
  category: inconsistency
  summary: 'ADR-before-code ordering: WP04 (S1 behaviour changes: fail-closed registry, typed ref errors) does not depend on WP01; WP09 (S3 helper) does not depend on WP03 although plan IC-03 says it governs IC-09.'
- id: E2
  severity: medium
  category: coverage
  summary: NFR-008 (Linux and Windows lanes) is not reflected in WP10 (S6 migration) or WP15 (S5 kept-report) validation.
- id: C1
  severity: medium
  category: underspecification
  summary: 'Out-of-matrix blast radius incomplete: WP06 edits cli/commands/accept.py, events.py, retrospect.py and implement_*.py, and WP13 edits cli/commands/lifecycle.py, but both run only tests/specify_cli/cli/commands/agent; WP16 edits acceptance/__init__.py without the test_accept_* files.'
- id: F2
  severity: medium
  category: inconsistency
  summary: 'Contract 1.24.0 ownership contradicts itself (WP13: WP15 owns the bump; WP15: whichever of WP13/14/15 lands first sets it), and WP13/WP14 edit WP15-owned envelope.py and orchestrator-api.md from independent lanes.'
- id: C2
  severity: medium
  category: underspecification
  summary: WP16 is BLOCKED and excluded from the first PR cut, but it is still a lane in lanes.json, and nothing says how the Mission is accepted or consolidated while it is planned; FR-036/037/039 and SC-006 are then unmet.
- id: F3
  severity: low
  category: inconsistency
  summary: 'Decision Moment count drifts: spec says twelve, plan says 17, tasks.md says 19; the decision list has 19 resolved.'
- id: F4
  severity: low
  category: inconsistency
  summary: "Spec Dependencies says land #6884 'keeping its tests'; WP04 flips one (justified by the spec edge case, research R-1 and the WP01 ADR), and the fail-closed scope has no control for a repository-root caller with an unreadable registry."
- id: F5
  severity: low
  category: inconsistency
  summary: WP07's out-of-map hunk in WP10-owned coordination/transaction.py sits on a parallel lane (lane-d vs lane-g) with no dependency between them.
- id: E3
  severity: low
  category: coverage
  summary: NFR-006 (gate <= 5 s) is not checked for WP16's amended test_destructive_op_routing.py, and NFR-005 (idempotence) is not tested for WP16's prune fix.
- id: B1
  severity: low
  category: ambiguity
  summary: WP19 T114 says 'the edits listed in the ADR map' without naming the map; WP16 and tasks.md use bare 'routing pins' (C-001 asks for the sense to be named).
- id: F6
  severity: low
  category: inconsistency
  summary: C-004 says every removal the Mission moves goes through destructive_guard, yet WP15's interim 'main-today remover' moves lane removal before the binding (sanctioned by DM s5-seam); C-004 does not record the exception.
---

## Specification Analysis Report

Mission `lane-worktree-model-hardening-01M6QY1M`. Reviewer profile: reviewer-renata. Inputs: spec.md, plan.md, tasks.md, tasks/WP01-WP19, data-model.md, contracts/, research.md, the 19 resolved Decision Moments, and `.kittify/charter/charter.md`. This analysis does not remediate anything.

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| D1 | Charter | CRITICAL | tasks/WP04 T017, T020 | `git cherry-pick -x -n 942ff4aed9 59bd93d6bd f404a0b240` folds #6884's red-first test and its fix into one first commit. That commit is an implementation commit, and it lands before WP04's own red-first tests (T020). The charter's ATDD-First Discipline (C-011) requires the failing test as a separate commit before any implementation commit. | Cherry-pick `942ff4aed9` (the red-first test) alone as commit 1, then the fix commits. Or commit the T020 red-first tests before T017. Keep the attribution trailers. |
| E1 | Coverage | HIGH | spec FR-055, FR-061; plan IC-14; tasks/WP14 T082; `consolidation/bookkeeping_projection.py` | For a default Mission settled to `lanes_with_coord`, PRIMARY artifacts live on the topic branch, which is also the coordination branch. Nothing is assigned to land them on the target. `_project_status_bookkeeping_to_target` and `project_post_checkpoint_commits_to_target` carry only status bookkeeping and coordination commits made after the checkpoint, and coordination teardown deletes the branch. Edits to tasks, WP files or meta made after the last lane cut can therefore be lost. WP14's pin test asserts the landing, but no WP owns a consolidation file that would make it true. | Before implementation, either (a) give the consolidation-side landing to an owner (WP15 or a new WP) with red-first tests and the projection or teardown files in its `owned_files`, or (b) prove with a research note and a WP14 test that the existing path already carries every PRIMARY change. Add the matching dependency. |
| F1 | Inconsistency | MEDIUM | lanes.json; tasks/WP04 and WP09 frontmatter; plan IC-03 and IC-04 | ADRs should land before the code they govern. WP04 changes S1 behaviour (fail-closed registry, typed ref errors), and the WP01 ADR records both, yet WP04 has `dependencies: []`. WP09 builds the S3 helper governed by the WP03 amendment to ADR `2026-04-03-1`, yet depends only on WP01 and WP08. | Add `WP01` to WP04's dependencies and `WP03` to WP09's, or record why ruling 8 alone governs WP04. |
| E2 | Coverage | MEDIUM | spec NFR-008; tasks/WP10, WP15 | NFR-008 names the S6 migration and the S5 kept-report path for Linux and Windows. Only WP08, WP09 and WP16 mention it. | Add Windows-safety criteria and review guidance to WP10 and WP15. |
| C1 | Underspecification | MEDIUM | tasks/WP06, WP13, WP16 Validation | `tests/specify_cli/cli/commands` is out of the CI matrix. WP06 edits `accept.py`, `events.py`, `retrospect.py`, `agent_retrospect.py`, `implement_claim.py` and `implement_phases.py`, but runs only `.../commands/agent`. WP13 edits `lifecycle.py` (specify) without `test_specify_*` or `test_lifecycle_read_seam_migration.py`. WP16 edits `acceptance/__init__.py` without `test_accept_*`. | Add the matching `tests/specify_cli/cli/commands/test_*.py` selections to each WP's Validation. |
| F2 | Inconsistency | MEDIUM | tasks/WP13:92,102; WP15:193; tasks.md shared-file table | WP13 says WP15 owns the 1.24.0 bump, while WP15 and tasks.md say whichever of the three lands first sets it. WP13 and WP14 (lanes j and k) also edit WP15-owned `envelope.py` and `docs/api/orchestrator-api.md` with no dependency on WP15 (lane l), so the same line can conflict. | Make WP15 the single owner of the bump: have WP13 and WP14 hand their field rows to WP15 or WP18, or depend on WP15 for those hunks. |
| C2 | Underspecification | MEDIUM | tasks.md WP16, "First PR cut"; lanes.json lane-m | WP16 is BLOCKED on #7275, yet it is still a WP in this Mission. Nothing says what happens at accept or consolidate if #7275 has not merged: cancel WP16, defer it to a follow-up Mission, or wait. FR-036, FR-037, FR-039 and SC-006 would then be unmet. | State the exit path. For example: if #7275 has not merged by accept, cancel WP16 with a reason, open a follow-up issue, and mark FR-036/037/039 deferred in the issue matrix. |
| F3 | Inconsistency | LOW | spec.md:8; plan.md:3, project tree; tasks.md:8 | The spec says twelve Decision Moments, the plan 17 and tasks.md 19. The decision list returns 19 resolved. | Align the counts (or say "the resolved Decision Moments"). |
| F4 | Inconsistency | LOW | spec Dependencies (#6884); tasks/WP04 T020, T021 | The flip of #6884's `test_an_unreadable_worktree_registry_keeps_the_callers_root` is justified: spec edge case "Registry unreadable … fails closed", Rule 1, research R-1, and the WP01 ADR item 4. But the spec still says "keeping its tests", and no control covers a repository-root caller when the registry cannot be read. | Reword the Dependencies bullet. Add a control test, or record that fail-closed deliberately covers repository-root callers. |
| F5 | Inconsistency | LOW | tasks.md shared-file table (`transaction.py`) | WP07 (lane-d) edits WP10-owned `transaction.py` from a parallel lane (lane-g). | Acceptable as "different functions". Record it in both WPs' completion summaries; consider making WP07 depend on WP10. |
| E3 | Coverage | LOW | tasks/WP16 Validation | No `--durations` or 5 s check (NFR-006) for the amended `test_destructive_op_routing.py`, and no second-run idempotence test (NFR-005) for the prune fix. | Add both to WP16. |
| B1 | Ambiguity | LOW | tasks/WP19 T114; tasks.md T105; WP16 | WP19 T114 says "the edits listed in the ADR map" without saying which map (research? plan's "31 edits, 17 files"?). WP16 and tasks.md say bare "routing pins". | Cite the map's file and section. Say "destructive-op routing pins". |
| F6 | Inconsistency | LOW | spec C-004 vs DM `01M6QY4B7P4T68TE7JE30FRJV6`; tasks/WP15 T093 | Until WP16 binds the remover port, WP15's interim remover moves lane removal into `lane_cleanup.py` through today's primitives. C-004 states no exception for that interim. | Add the interim exception to C-004, citing the s5-seam ruling. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 to FR-007 (S1) | Yes | WP01, WP04-WP07 | FR-043 is folded into WP04 and WP06 |
| FR-010 to FR-014 (S2) | Yes | WP08 | |
| FR-020 to FR-022 (S3) | Yes | WP03, WP09 | see F1 (WP09 does not depend on WP03) |
| FR-030 to FR-039a (S5) | Yes | WP03, WP15, WP16 | WP16 blocked (C2) |
| FR-040 to FR-046 (S6) | Yes | WP01, WP09, WP10 | |
| FR-050 to FR-061 (S7) | Partial | WP02, WP13, WP14, WP05 | FR-055/061 consolidate landing has no owner (E1) |
| FR-070 to FR-078 (S8) | Yes | WP02, WP11, WP12 | |
| FR-080 to FR-084 (S9) | Yes | WP03 | |
| FR-090 to FR-093 (S11) | Yes | WP17, WP18, WP19 | |
| NFR-001 | Yes | WP05 | |
| NFR-002 | Yes | WP10, WP14, WP15 | |
| NFR-003 | Yes | WP14 | |
| NFR-004 | Yes | WP15 | |
| NFR-005 | Partial | WP10 | WP16 prune fix not covered (E3) |
| NFR-006 | Partial | WP07, WP09 | WP16 not covered (E3) |
| NFR-007 | Yes | WP12 | |
| NFR-008 | Partial | WP08, WP09, WP16 | WP10 and WP15 missing (E2) |
| NFR-009, NFR-010 | Yes | all code WPs (quality gates) | |
| SC-001 to SC-012 | Yes | WP03, WP06-WP10, WP12-WP17, WP19 | SC-006 depends on blocked WP16 |

**Specific checks:**
- **ADR file names.** `2026-11-06-2` (WP01), `-3` (WP02), `-4`/`-5`/`-6` (WP03) are consistent across spec, plan and tasks. `-1` stays on #7275.
- **S2 before the S3 helper.** Holds: WP09 depends on WP08.
- **S8 before or with S7 (C-010).** Holds: WP14 depends on WP12. WP13 is coupled only at release, which is acceptable because the first PR cut contains both.
- **WP16 blocked on #7275.** Holds: the block is stated, and T100 checks the precondition.
- **Red-first.** Every code WP has a red-first subtask. Tidy-first steps before it (WP04 T018, WP09 T047, WP13 T075-T078) are behaviour-preserving campsite cleaning, which Standing Order 2 sanctions. The one exception is D1.
- **No full sweeps.** No WP runs a full `tests/architectural/` sweep or `make test-full`; each names its gate files.
- **owned_files.** No overlaps. Out-of-map hunks are recorded in the tasks.md table.
- **Decision Moments.** All 19 resolved Decision Moments are honoured somewhere. OQ-1 is explicitly superseded by `primary_partition_default`, and the "lanes on an unprotected target" clause of `01M6QZ02HDACM7A0VNYSAQ8MQB` by `01M6R0B954ZPQN5NV4R1ZRE7NY`. No contradiction found; see F6 for the C-004 wording.
- **Terminology.** No "feature" usage. Bare "merge" appears only in the generated `branch_strategy` boilerplate (outside this Mission's text).

**Charter Alignment Issues:** D1 (ATDD-First Discipline C-011, commit ordering in WP04).

**Unmapped Tasks:** none. Every WP carries `requirement_refs`.

**Metrics:**

- Total Requirements: 63 FR + 10 NFR + 17 C + 12 SC
- Total Tasks: 19 WPs / 117 subtasks
- Coverage % (requirements with >=1 task): 100% nominal. The FR-055/FR-061 consolidate leg has no owner (E1).
- Ambiguity Count: 1
- Duplication Count: 0
- Critical Issues Count: 1

### Next Actions

- Resolve D1 and E1 before `/spec-kitty.implement`. D1 is a one-line change to WP04 T017. E1 needs a plan/tasks decision on who owns the consolidate landing of the topic branch's PRIMARY artifacts.
- The medium findings (F1, E2, C1, F2, C2) are edits to WP prompts and frontmatter. Make them through `/spec-kitty.tasks` refinement (then re-run `finalize-tasks`) and re-run `/spec-kitty.analyze`.
- The low findings are optional.
