---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: landed-worktree-cleanup-01M6KZNP
mission_id: 01M6KZNPGEVQH9VPKAEZD2T94V
generated_at: '2026-11-04T23:48:22.251460+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/landed-worktree-cleanup-01M6KZNP/spec.md
    sha256: 063a53058af1bb760dade14a08c2445fa009e10307c60ad99f2261b96fba5442
  plan.md:
    path: kitty-specs/landed-worktree-cleanup-01M6KZNP/plan.md
    sha256: 8a593fcd55f9dec0710b4fd9523c3f7b1be617417ecc93df87330b7e54c1e9f8
  tasks.md:
    path: kitty-specs/landed-worktree-cleanup-01M6KZNP/tasks.md
    sha256: 38557149d00f2f15bd3359ebca7a969d822779585bd4da63137cfa5194acc5e5
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  low: 1
  high: 0
  medium: 3
  critical: 0
  info: 0
findings:
- id: I1
  severity: medium
  category: inconsistency
  summary: Reason code BRANCH_IN_OTHER_WORKTREE (data-model.md, spec edge case) is not in WP03's Reason enum or verdict rule.
- id: U1
  severity: medium
  category: underspecification
  summary: WP03 process probe ignores processes of other uids; spec FR-005/NFR-001 state the rule without that residual.
- id: C1
  severity: medium
  category: coverage
  summary: NFR-003 (report < 10 s over 50 worktrees) has no explicit measuring test task.
- id: L1
  severity: low
  category: inconsistency
  summary: Operator closeout wording names CHANGELOG.md [Unreleased]; CLAUDE.md requires a fragment in docs/changelog/unreleased/ (WP06 follows CLAUDE.md).
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | MEDIUM | data-model.md (reason codes); spec.md Edge Cases; tasks/WP03 T008 | `BRANCH_IN_OTHER_WORKTREE` is listed in data-model and the spec edge case but WP03 omits it. Git refuses a second checkout of one branch without `--force`, so the case is near-impossible; the guard's `branch -D` would also fail on a checked-out branch. | Implementer: treat a `branch -D` failure as a recorded refusal (already covered by T011); no new verdict needed. Reviewer checks the refusal path. |
| U1 | Underspecification | MEDIUM | spec.md FR-005; tasks/WP03 T009 | Another user's process inside a worktree is not detected without root. | Document the residual in the runbook (WP06) and the PR body; keep same-uid fail-closed behaviour. |
| C1 | Coverage | MEDIUM | spec.md NFR-003 | No task measures the 50-worktree budget. | WP03 adds a coarse timing assertion (or the closeout records a manual timing) — do not add a flaky hard gate. |
| L1 | Inconsistency | LOW | operator instruction vs CLAUDE.md "Code Style" | Changelog location. | Follow CLAUDE.md (fragment); mention in PR. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 landed-worktree-report | Yes | T001-T004, T010, T015 | |
| FR-002 offline-landed-proof | Yes | T010, T013 | |
| FR-003 prune-proven-landed | Yes | T005, T011, T013 | |
| FR-004 recreate-hint | Yes | T006, T008, T011 | |
| FR-005 running-process-proof | Yes | T009, T013 | U1 residual |
| FR-006 fix-contract-unchanged | Yes | T016, T017 | |
| FR-007 upgrade-skips-non-mission | Yes | T018, T019, T023 | |
| FR-008 upgrade-optin-flags | Yes | T020, T023 | |
| FR-009 upgrade-names-every-worktree | Yes | T021, T023 | |
| FR-010 plan-json-policy | Yes | T022 | |
| FR-011 runbook-step | Yes | T025 | |
| FR-012 machine-readable-report | Yes | T015, T017 | |
| NFR-001 no-unproven-deletion | Yes | T007, T013 | |
| NFR-002 offline | Yes | T013 (remote-contact gate) | |
| NFR-003 report-cost | Partial | T010 | C1 |
| NFR-004 code-quality | Yes | all WPs' test strategy | |

**Charter Alignment Issues:** none. Single-authority reuse (guard, `is_absorbed`, branch-naming), tidy-first WP01, ATDD red-first in WP03/WP05, no hosted surface, packs edited upstream only.

**Unmapped Tasks:** none.

**Metrics:**

- Total Requirements: 21 (12 FR, 4 NFR, 5 C)
- Total Tasks: 26
- Coverage: 100 % of FRs; NFR-003 partial
- Ambiguity Count: 0
- Duplication Count: 0
- Critical Issues Count: 0

## Next Actions

- No CRITICAL/HIGH findings: proceed to implementation. Fold I1/U1/C1 guidance into WP03 and WP06 review.
