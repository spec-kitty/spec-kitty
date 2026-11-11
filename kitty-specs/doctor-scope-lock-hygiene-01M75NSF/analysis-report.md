---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: doctor-scope-lock-hygiene-01M75NSF
mission_id: 01M75NSFANQ8DNQKXZV8EDKFB1
generated_at: '2026-11-11T17:21:18.654954+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/doctor-scope-lock-hygiene-01M75NSF/spec.md
    sha256: e5047791013635af8dd3e77888ac12dd1386350bb17c323b1e621b52759a4f55
  plan.md:
    path: kitty-specs/doctor-scope-lock-hygiene-01M75NSF/plan.md
    sha256: bc88f1cc1a1b59d0a0c25250fb6c71c4f091d291e76f21f314f4eeb2cea5fda7
  tasks.md:
    path: kitty-specs/doctor-scope-lock-hygiene-01M75NSF/tasks.md
    sha256: a1bd3701956ba98610a298acda5cf9122c4227aa2abea818673a46e532e25413
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  critical: 0
  medium: 2
  high: 0
  low: 2
  info: 0
findings:
- id: C1
  severity: medium
  category: coverage
  summary: Remedy strings in src/specify_cli/consolidation/ that say `doctor coordination --fix` are left unchanged (C-002); they now meet the scope refusal, which itself names --mission and --all-missions.
- id: I1
  severity: medium
  category: inconsistency
  summary: Brief asks that a stale lock be reclaimed or tolerated by the landing reset; plan D-10 chooses prevention only, so a branch that already tracks the lock can still block a landing.
- id: U1
  severity: low
  category: underspecification
  summary: NFR-002 (one exclude write per clone) has no dedicated test task.
- id: U2
  severity: low
  category: underspecification
  summary: FR-010 ratchet names no concrete existing test file; WP02 tells the implementer to find it.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Coverage | MEDIUM | plan.md IC-01 Risks; WP01 Context | Consolidation remedy strings stay unscoped (C-002). | Record as a residual in the PR; follow-up with #7544. |
| I1 | Inconsistency | MEDIUM | plan.md D-10; spec Edge Cases | Prevention-only; an already-tracked lock is repaired only by the owned `repair-runtime-lock` route. | Keep D-10 (kernel G3); call it out for operator ruling in the PR. |
| U1 | Underspecification | LOW | spec NFR-002; WP02 T007 | Memoization has no test. | Add a small unit assertion in WP02 if cheap. |
| U2 | Underspecification | LOW | WP02 T006 case 5 | Ratchet test not named. | Implementer locates and runs it; name it in the PR. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001..FR-004 | yes | T001, T002, T003 | WP01 |
| FR-005..FR-007 | yes | T001, T004 | WP01 |
| FR-008 | yes | T006, T007, T010 | WP02 |
| FR-009 | yes | T006, T008 | WP02 |
| FR-010 | yes | T006, T008 | WP02 (ratchet) |
| FR-011 | yes | T006, T009 | WP02 |
| NFR-001..NFR-003 | yes | T004, T007, all | |
| C-001..C-005 | yes | WP01, WP02 | constraints carried into both prompts |

**Charter Alignment Issues:** none. Red-first commits are planned in both WPs (Standing Order 4); no new gate (C-005); the walker allowlist change is a drain.

**Unmapped Tasks:** none.

**Metrics:** Total requirements 19 (11 FR, 3 NFR, 5 C) + 3 SC · Total tasks 10 · Coverage 100% · Ambiguity 0 · Duplication 0 · Critical 0.

**Next Actions:** proceed to implementation; carry C1 and I1 into the PR as residuals for the operator.
