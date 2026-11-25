---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: planning-lane-write-branch-01M8A725
mission_id: 01M8A725BGBKAK98Y7F392ZFZ5
generated_at: '2026-11-25T21:28:20.695839+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: .worktrees/planning-lane-write-branch-01M8A725-coord/kitty-specs/planning-lane-write-branch-01M8A725/spec.md
    sha256: 67cbd213eb3c10fb370b38ba3692102abcab8dc1482ad9c2ac7bd4f4d2453c7e
  plan.md:
    path: .worktrees/planning-lane-write-branch-01M8A725-coord/kitty-specs/planning-lane-write-branch-01M8A725/plan.md
    sha256: 79410e69f2529d7ae4c75ec8f2ecffa744dd1af4f5ebcdb495b6ff74b7060cac
  tasks.md:
    path: .worktrees/planning-lane-write-branch-01M8A725-coord/kitty-specs/planning-lane-write-branch-01M8A725/tasks.md
    sha256: 697605baa6c4833d7495d6633e701997c91e2c399ebffb7db6745afdb409e3a8
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  critical: 0
  low: 5
  medium: 2
  high: 0
  info: 0
findings:
- id: I1
  severity: medium
  category: inconsistency
  summary: spec FR-011 says the for_review gate counts the work package's own commits, but WP03 records that the gate counts any non-status commit in the shared coordination worktree (sibling-commit residual) and that the evidence axis is the real check.
- id: I2
  severity: medium
  category: inconsistency
  summary: data-model PlanningWriteRef invariant says an absent or unreadable meta.json never reads as not default; WP01 now decides a missing meta.json with no copy on the Mission branch (legacy Mission) returns the target, proven by a probe.
- id: I3
  severity: low
  category: inconsistency
  summary: plan IC-04 lists WP04 as depending on IC-01 only; tasks.md now makes WP04 depend on WP02 (move-task auto-commit guard, T025).
- id: I4
  severity: low
  category: inconsistency
  summary: plan IC-02 and the source tree list ownership/{kind_normalisation,workspace_strategy}.py docstrings under the workspace concern; tasks moved them to WP05.
- id: I5
  severity: low
  category: inconsistency
  summary: plan IC-04 names the recovery map _REMEDIES; the code and WP04 use _RECOVERY.
- id: I6
  severity: low
  category: inconsistency
  summary: data-model PlanningWriteRef describes a branch string; WP01 returns a facts object PlanningWriteRef(branch, on_mission_branch, landed).
- id: C1
  severity: low
  category: coverage
  summary: NFR-003 and NFR-004 (quality gates, diff coverage) apply to every WP but are mapped to WP01 and WP03 only; every WP prompt carries the standing rules, so coverage is real but under-mapped.
---

## Specification Analysis Report

Mission `planning-lane-write-branch-01M8A725` (#7860, operator rulings A', guidance only, window start = claim commit). The artifacts were analysed after two squad folding passes (post-spec, post-tasks).

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | MEDIUM | spec.md FR-011; tasks/WP03 T010 case 5 | FR-011 overclaims what the coarse gate does, given the sibling-commit residual | When WP03 lands, reword FR-011's "so that" clause to "does not count the Mission's planning history"; the evidence axis (FR-003/FR-010) stays the real check |
| I2 | Inconsistency | MEDIUM | data-model.md PlanningWriteRef invariant; tasks/WP01 T001 | A missing meta.json with no copy on the Mission branch is a proven legacy shape, not a silent fallback | Align data-model.md with WP01's rule (unreadable/malformed → raise; missing → probe the Mission branch, raise if it carries meta.json, else legacy target) |
| I3 | Inconsistency | LOW | plan.md IC-04 sequencing | WP04 → WP02 dependency added by post-tasks squad | Note it in plan IC-04 |
| I4 | Inconsistency | LOW | plan.md IC-02, source tree | Docstring ownership moved to WP05 | Note it in plan |
| I5 | Inconsistency | LOW | plan.md IC-04 | `_REMEDIES` vs `_RECOVERY` | Use `_RECOVERY` |
| I6 | Inconsistency | LOW | data-model.md | Branch string vs facts object | Update data-model.md |
| C1 | Coverage | LOW | WP frontmatter requirement_refs | NFR-003/NFR-004 under-mapped | Optional: map to all WPs |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 planning workspace is the Mission-branch checkout | Yes | T005–T007 | WP02 |
| FR-002 implement message names the Mission branch | Yes | T008 | WP02 |
| FR-003 evidence window ends at the Mission branch | Yes | T015–T017, T019 | WP04, WP05 |
| FR-004 hollow refused, names the Mission branch | Yes | T015, T017 | WP04 |
| FR-005 one write-branch rule | Yes | T001–T003, T023 | WP01, WP05 pin |
| FR-006 unchanged shapes | Yes | T005, T015, T021 | WP02, WP04, WP05 |
| FR-007 in-flight refusal names the remedy | Yes | T018, T021 | WP04, WP05 |
| FR-008 Proposed ADR amendments | Yes | T004, T020 | WP01, WP04 |
| FR-009 release note and migrations note | Yes | T024 | WP05 |
| FR-010 window starts after the claim | Yes | T015, T016 | WP04 |
| FR-011 claim base and gate read the workspace | Yes | T010–T013 | WP03 (see I1) |
| FR-012 consolidate lands planning work | Yes | T022 | WP05 (shape B expected red, fix in scope) |
| FR-013 shared coordination worktree | Yes | T014, T025 | WP03 ratchet, WP04 guard |
| FR-014 glossary and docs | Yes | T009, T024 | WP02, WP05 |
| NFR-001 diff budget | Yes | T016 | WP04 |
| NFR-002 fail closed | Yes | T001–T003, T005, T015 | |
| NFR-003 code quality | Yes | all | standing rules (see C1) |
| NFR-004 coverage | Yes | all | standing rules (see C1) |
| C-001..C-006 | Yes | various | C-001 read-only modules respected; C-003 restricted hunks stated in WP02 |
| SC-001..SC-006 | Yes | T021, T015, T005, T018, T022 | |

**Charter Alignment Issues:** none. Single canonical authority (one reader and one checkout locator, pinned by T023), layering (mission_runtime below specify_cli, lazy imports), ATDD red-first (red reproduction exists; each WP starts with failing tests), test policy (no test-full), ADR amendments Proposed, terminology (Mission branch, no bare primary/merge, no Feature; CLAUDE.md is a symlink to AGENTS.md).

**Unmapped Tasks:** none.

**Metrics:**

- Total Requirements: 14 FR, 4 NFR, 6 C, 6 SC
- Total Tasks: 25 subtasks in 5 work packages
- Coverage: 100 % of requirements have at least one task
- Ambiguity Count: 0
- Duplication Count: 0
- Critical Issues Count: 0

**Next Actions:** No critical or high findings, so implementation may start. The two medium findings (I1, I2) are wording drift between the spec or data model and the decided WP rules. The WP prompts carry the decided behaviour, so they do not block. Editing spec.md or data-model.md now would make this report stale, so fold them at the end, through the WP that owns the behaviour, or in the closeout.
