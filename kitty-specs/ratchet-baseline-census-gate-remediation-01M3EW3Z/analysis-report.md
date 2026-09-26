---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: ratchet-baseline-census-gate-remediation-01M3EW3Z
mission_id: 01M3EW3Z4M4VVXAZMHPDFKPSE5
generated_at: '2026-09-26T14:49:22.336186+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/spec.md
    sha256: 890d6727c43018b44b9842f3d9f2f6a79a594aa8d83cbb764b8641ea668cee7e
  plan.md:
    path: kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/plan.md
    sha256: dd345f201d572f3b077e7fc40b0aac1dd295b9c261b5d2f908900598aa855927
  tasks.md:
    path: kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/tasks.md
    sha256: c86ecbc7ad68b8f88416cf2e8e2a76b3e19e27a161a937bc913b4874e24d1d24
  charter:
    path: .kittify/charter/charter.yaml
    sha256: a2b2f62cf1c0fa8987b67f6759d18bcc18b2fb47a8d3ad2783f8fac68b192c77
verdict: blocked
issue_counts:
  critical: 1
  high: 0
  low: 8
  medium: 3
  info: 0
findings:
- id: D1
  severity: critical
  category: charter
  summary: D-OP-4 lets deletion-only WP05/WP07/WP09 prove red-first by tracer evidence with no failing-first test, conflicting with the binding charter ATDD-First Discipline (C-011) and spec C-001's own carve-out; the plan's Charter Check records PASS with no exception.
- id: I1
  severity: medium
  category: inconsistency
  summary: Rev-1 WP numbering survives in plan.md, data-model.md and quickstart.md, contradicting the rev-2 WP table and the WP prompts.
- id: I2
  severity: medium
  category: terminology
  summary: Census discriminator called 'occurrence' in spec.md and plan.md summary step 3 but 'op_ordinal' in plan D-OP-1, data-model, tasks and WP04.
- id: I3
  severity: medium
  category: inconsistency
  summary: data-model.md ContentDescriptor fields and matcher name do not match the substrate (rel_path, token_substring, occurrence, rationale) or WP02's partition_findings.
- id: I4
  severity: low
  category: inconsistency
  summary: Plan WP02 row gives the join drift test '15 files'; WP02 and WP13 derive 3.
- id: I5
  severity: low
  category: inconsistency
  summary: plan.md follow-ups still list test_next_no_unknown_state.py, which FR-013 and WP08 T046 now fold in.
- id: I6
  severity: low
  category: inconsistency
  summary: SC-006 says 'three FR-019 follow-up issues' but FR-019 enumerates four (a-d).
- id: I7
  severity: low
  category: inconsistency
  summary: Spec US2-AS3 names only 2 of the 4 non-enforcing leaves that are RED on the planning base.
- id: I8
  severity: low
  category: inconsistency
  summary: Parity-verdict churn window is 'since 2026-03-20' in data-model.md but 'since 2026-03-26' in WP12.
- id: A1
  severity: low
  category: ambiguity
  summary: tasks.md has orphan 'Subtask Index rows' stub blocks and WP13 T073 numbers two steps '3.'.
- id: C1
  severity: low
  category: coverage
  summary: requirement_refs cite C-001 only on WP01/WP02 and C-006 only on WP13 although both bind every implementation WP.
- id: D2
  severity: low
  category: charter
  summary: Charter prefers an issue-<n>-<slug> branch; C-006 fixes claude/spec-kitty-remediation-wfje22 without a recorded rationale.
---

## Specification Analysis Report

Mission `ratchet-baseline-census-gate-remediation-01M3EW3Z` @ HEAD `28b4bb1d`. Analyst lens: analyst-annie; `charter context --action analyze`.

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| D1 | Charter | CRITICAL | charter.md:622-631; spec.md:136; plan.md:27,54,63; WP05, WP07, WP09 | D-OP-4 substitutes tracer evidence + green survivor for a failing-first test | Name honest REDs for WP05 (`test_load_baseline_rejects_retired_keys`) and WP07 (import of `_surface_resolution_scan`); record an operator-signed charter exception for WP09 in Complexity Tracking; align C-001 |
| I1 | Inconsistency | MEDIUM | plan.md; data-model.md; quickstart.md | Rev-1 WP numbering | Renumber to rev 2 |
| I2 | Terminology | MEDIUM | spec.md; plan.md summary | `occurrence` vs `op_ordinal` | Use `op_ordinal` for census |
| I3 | Inconsistency | MEDIUM | data-model.md | ContentDescriptor fields/matcher name wrong | Rewrite from `_ratchet_keys.py`; name `partition_findings` |
| I4 | Inconsistency | LOW | plan.md WP02 row | 15 vs 3 join drift files | 3 |
| I5 | Inconsistency | LOW | plan.md follow-ups | stale entry | delete |
| I6 | Inconsistency | LOW | spec.md SC-006 | three vs four | four (a-d) |
| I7 | Inconsistency | LOW | spec.md US2-AS3 | 2 of 4 leaves named | name all 4 |
| I8 | Inconsistency | LOW | data-model.md vs WP12 | churn date | unify |
| A1 | Ambiguity | LOW | tasks.md; WP13 | stub blocks, duplicated step number | clean up |
| C1 | Coverage | LOW | WP frontmatter | C-001/C-006 under-cited | declare mission-global |
| D2 | Charter | LOW | charter.md:174; spec.md C-006 | branch-naming deviation | record rationale |

**Coverage**: FR-001..FR-020 and NFR-001..NFR-006 all have tasks (100%); C-001 partial (D1); SC-001..SC-006 verified in WP13 T075.

**Unmapped tasks**: none (T001-T075).

**Metrics**: 32 requirements (20 FR, 6 NFR, 6 C) + 6 SC; 75 subtasks / 13 WPs; coverage 100% FR/NFR; ambiguity 1; duplication 0; critical 1.

**Next actions**: resolve D1 (operator sign-off needed for WP09's exception), fix I1-I3 and LOW items in one editorial pass, re-run analysis and record.
