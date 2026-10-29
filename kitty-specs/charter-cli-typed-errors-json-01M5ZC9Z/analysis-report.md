---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: charter-cli-typed-errors-json-01M5ZC9Z
mission_id: 01M5ZC9ZQVQ4MT57GJWE56ZASP
generated_at: '2026-10-29T05:40:11.163324+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/charter-cli-typed-errors-json-01M5ZC9Z/spec.md
    sha256: 3c1f72d17916d6b30e091ea89a9a0bd43636c94aebeb1f717ad5bc267ab1a640
  plan.md:
    path: kitty-specs/charter-cli-typed-errors-json-01M5ZC9Z/plan.md
    sha256: 664c688b19aee7bdd34d3c66d29fea0090b19644b0c78e77d2d942144c400869
  tasks.md:
    path: kitty-specs/charter-cli-typed-errors-json-01M5ZC9Z/tasks.md
    sha256: cf4346cbc5f280b312914a54bd1221fd1405d4973a6eb814ea0d6cbae0acb3cd
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  critical: 0
  low: 2
  high: 0
  medium: 2
  info: 0
findings:
- id: I1
  severity: low
  category: inconsistency
  summary: plan.md Project Structure still describes _coded_errors.py as a codes table; codes live in activate.py/status.py (implemented and reviewed that way).
- id: U1
  severity: medium
  category: underspecification
  summary: The activation.error fallback (status succeeds when the activation read fails) is defined in plan/data-model and implemented, but not stated as a spec edge case; WP03 docs must describe it.
- id: D1
  severity: medium
  category: documentation
  summary: 'WP03 must document review-surfaced details: skipped_out_of_scope[].deactivated, preflight warnings first in warnings, referenced_not_cascaded excludes kind-filtered nodes, required[] covers activatable org-requirable kinds only, ACTIVATION_FAILED vs ACTIVE_CHARTER_CONFIG_INVALID asymmetry for malformed charter_packs.'
- id: C1
  severity: low
  category: coverage
  summary: NFR-002 verified by manual timing (status --json median 1094 ms vs 1091 ms, collector ~5 ms).
---

## Specification Analysis Report (re-run after spec correction)

Re-run because spec.md's config-shape edge case and the contract code table were corrected after the WP02 review
(a non-mapping `.kittify/config.yaml` is refused by the soundness gate as ACTIVE_CHARTER_CONFIG_INVALID; RESYNTHESIS_FAILED added to the table).
WP01 and WP02 are approved; WP03 (docs) remains.

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | LOW | plan.md Project Structure | Stale codes-table note | No action; implementation reviewed |
| U1 | Underspecification | MEDIUM | data-model.md ActivationBlock | activation.error fallback not in spec | Document in WP03 |
| D1 | Documentation | MEDIUM | WP01/WP02 review notes | Review-surfaced behaviour details | Document in WP03 |
| C1 | Coverage | LOW | NFR-002 | Manual timing | Recorded in WP02 history |

**Coverage Summary:** all FR-001..FR-012, NFR-001..NFR-004, C-001..C-006 mapped (WP01/WP02 approved; FR-012/C-006 via WP03). 100% coverage.

**Charter Alignment Issues:** none.

**Metrics:** 22 requirements + 5 SC; 15 tasks; coverage 100%; ambiguity 0; duplication 0; critical 0.

## Next Actions

Proceed with WP03, folding D1/U1 into the docs.
