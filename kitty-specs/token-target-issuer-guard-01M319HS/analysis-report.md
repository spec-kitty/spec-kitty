---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: token-target-issuer-guard-01M319HS
mission_id: 01M319HSN3ZVHE3QPGZDH3J8ST
generated_at: '2026-09-21T06:45:37.110479+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/token-target-issuer-guard-01M319HS/spec.md
    sha256: c3a09468e637aee653ab5784b3e57b8485c75429ba1d9bbb06168357d7eb8923
  plan.md:
    path: kitty-specs/token-target-issuer-guard-01M319HS/plan.md
    sha256: fe4667c6fb3c112fd4d2d7a0d1ca71614c383de0f62ee38e6f5806d41bf8dc58
  tasks.md:
    path: kitty-specs/token-target-issuer-guard-01M319HS/tasks.md
    sha256: 5956a2df9ef460b883d40b9a15dbbffc54e9f1f6cba3c82ce88fa7f52d86b567
  charter:
    path: .kittify/charter/charter.yaml
    sha256: a2b2f62cf1c0fa8987b67f6759d18bcc18b2fb47a8d3ad2783f8fac68b192c77
verdict: ready
issue_counts:
  critical: 0
  low: 2
  high: 0
  medium: 0
  info: 0
findings:
- id: C1
  severity: low
  category: coverage
  summary: NFR-007 (ruff/mypy/complexity) and C-005 (tiered rigour) are cross-cutting gates enforced via each WP's Definition of Done rather than a per-WP requirement_ref; intentional but not visible in FR-coverage tooling.
- id: N1
  severity: low
  category: consistency
  summary: FR-004 (ws provisioning) is a dormant path verified by direct invocation, not an integration reproduction (NFR-004 carve-out); reviewers must not expect a pre-existing-entry-point red for WP04.
---

## Specification Analysis Report

Mission: token-target-issuer-guard-01M319HS (#4755). Artifacts: spec.md, plan.md, tasks.md (5 WPs),
research.md, data-model.md, contracts/issuer-target-helper.md, quickstart.md. This mission passed a
3-lens grounding squad, a post-spec adversarial lens (12 findings folded), and a post-tasks
anti-laziness lens (4 findings folded) before analysis.

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Coverage | LOW | spec.md NFR-007, C-005; all WP DoD | Cross-cutting static/rigour gates enforced per-WP via Definition of Done, not a requirement_ref | Keep as-is; each WP DoD asserts ruff/mypy/complexity. No FR-coverage impact. |
| N1 | Consistency | LOW | spec.md FR-004/NFR-004; tasks WP04 | ws path is dormant → verified by direct invocation, not an integration red-first repro | Already reconciled in NFR-004 + WP04; reviewers should expect a direct-invocation test, not an entry-point red. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 refresh targets issuer | yes | T004, T008 | WP02 |
| FR-002 revoke targets issuer | yes | T011, T013 | WP03 |
| FR-003 rehydrate targets issuer | yes | T006, T010 | WP02 |
| FR-004 ws targets issuer | yes | T015, T016 | WP04 (dormant → direct-invocation) |
| FR-005 refuse on mismatch | yes | T002, T004, T011, T015 | all flows |
| FR-006 legacy null → resolved | yes | T003, T010, T014, T016 | helper + flow-level confirmations |
| FR-007 single authority | yes | T002, T005, T020, T023 | helper + consumers + membership test |
| FR-008 gate the send / non-demotion | yes | T004, T005, T009 | held-token trap |
| FR-009 diagnosable refusal | yes | T006, T012, T014 | token-free warnings |
| FR-010 fold #4053 | yes | T021 | WP05 |
| FR-011 fold #4265 | yes | T022 | WP05 |
| FR-012 null-session contract | yes | T002, T003 | helper |
| NFR-001 no cred to non-issuer | yes | T008, T009, T013, T014, T016 | red-first + units |
| NFR-002 identical normalization | yes | T002, T007 | canonical normalizer |
| NFR-003 non-vacuous fence (both dirs) | yes | T018, T019, T023 | WP05 |
| NFR-004 red-first | yes | T008, T009, T013 | + ws direct-invocation |
| NFR-005 no regression | yes | T010, T014, T016 | happy-path unchanged |
| NFR-006 token-free diagnostics | yes | T003, T009, T010, T014, T016 | asserted |
| NFR-007 static gates | yes (DoD) | all WPs | cross-cutting (C1) |

**Charter Alignment Issues:** none. Single canonical authority (unification, not a parallel guard),
architectural-gate discipline (non-vacuous both directions), red-first per ADR 2026-07-17-1, campsite
folds bounded, model discipline (implement=sonnet/review=opus) all honored.

**Unmapped Tasks:** none. Every subtask T001–T023 maps to an FR/NFR.

**Metrics:**
- Total Requirements: 12 FR + 7 NFR + 5 C = 24
- Total Tasks (subtasks): 23 across 5 WPs
- Coverage %: 100% of FRs have ≥1 task
- Ambiguity Count: 0 (resolved via prior adversarial passes)
- Duplication Count: 0
- Critical Issues Count: 0

## Next Actions
No CRITICAL/HIGH findings → READY for `/spec-kitty.implement`. The two LOW findings are informational
and already reconciled in the artifacts; no remediation required before implementation.
