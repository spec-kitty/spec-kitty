---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: persistent-deactivation-ledger-01M59YAA
mission_id: 01M59YAAGWG6HWFVYSZD4GGN9Y
generated_at: '2026-10-20T12:25:27.454571+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/persistent-deactivation-ledger-01M59YAA/spec.md
    sha256: 57b98b663ac56f2db76f7e0eda091297cf799f17afd4867feef6bcb37566ac92
  plan.md:
    path: kitty-specs/persistent-deactivation-ledger-01M59YAA/plan.md
    sha256: fa1393b1ebb21c036cf3065b2153d1a9869470d650a3d2f13a6a5adee2da4984
  tasks.md:
    path: kitty-specs/persistent-deactivation-ledger-01M59YAA/tasks.md
    sha256: 19612d2d74c00c4b09a3e5c75d50882f7ac0292e9fd9974ae5bee0ed58843006
  charter:
    path: .kittify/charter/charter.yaml
    sha256: c6db31e8689d3ae3e4c7ed4da12514b42fbb881c02350da955372b08326c8d71
verdict: ready
issue_counts:
  medium: 1
  high: 0
  low: 2
  critical: 0
  info: 0
findings:
- id: M1
  severity: medium
  category: underspecification
  summary: The 'init re-run on an unmigrated project' path never reaches the seed. init.py:912-941 exits 0 ('Already initialized') whenever config.yaml exists, before provisioning (:1456) and the seed (:1515). On the fresh path config.yaml did not exist at entry, so pre_existing_legacy_keys is always empty and the new rc8 skip branch is dead on every init path. The WP08 T049 red-first test (re-run init → rc8 pending) and the WP14 T078.3 assertion pass because of the idempotency exit, not the seed rule, and spec.md:313's edge case describes behaviour that cannot happen.
- id: L1
  severity: low
  category: inconsistency
  summary: plan.md:399 and spec.md:313 still state the pre-fold rule ('skips rc8 while legacy activation keys exist and no ledger exists'). WP08 T049 now says 'keys that existed before this init run started'.
- id: L2
  severity: low
  category: coverage
  summary: 'Carried (pass-8 L2 / pass-9 L3): acceptance-matrix.json has no FR-021..FR-024 or SC-004 row; deferred to accept time.'
---

## Specification Analysis Report (pass 10, independent, reviewer-renata)


## Specification Analysis Report (pass 11, independent, reviewer-renata)

**Why this pass.** The pass-10 report went stale only through its charter input. spec.md, plan.md and tasks.md hash identically to the pass-10 record (57b98b66…, fa1393b1…, 19612d2d…). Since the pass-10 record commit 686f8098, the mission directory changed only in status.events.jsonl/status.json, WP08 baseline-tests and review-cycle-1 artifacts, and traces/. No WP prompt, wps.yaml, lanes.json or data-model.md changed. charter.md is unchanged.

**Charter input change (WP08 dogfood, 9a52f13d).** `.kittify/charter/charter.yaml` sha256 2efd56dd… → c6db31e8…. The change is a pure tail deletion of the 8 activation keys (activated_agent_profiles, activated_directives, activated_paradigms, activated_procedures, activated_styleguides, activated_tactics, activated_toolguides, mission_type_activations). They were parsed and compared: every moved key's value equals `.kittify/charter/activation.yaml` exactly, activation.yaml holds exactly those 8 keys, and every other charter.yaml key is semantically equal. synthesis-manifest.yaml changes only bundle_content_hash and manifest_hash. This is consistent with the mission (the ledger owns the activation keys, and charter.yaml keeps governance content). No governance principle changed, so no new charter finding arises.

### Findings (unchanged from pass 10)

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| M1 | Underspecification | MEDIUM | init.py:912-941 vs :1456/:1515; spec.md:313 | The re-run never seeds (idempotency exit), so the skip branch is unreachable through init | **Handled in WP08 via carry-forward.** No `pre_existing_legacy_keys` parameter is in src/. The regression test test_init_reseed_keeps_rc8_pending.py pins the early exit, and the case is recorded in traces/design-decisions.md:98. The spec.md:313 wording is still open for WP15, so the finding stays open until then |
| L1 | Inconsistency | LOW | plan.md:399; spec.md:313 | Pre-fold wording of the seed rule | WP15 aligns the wording |
| L2 | Coverage | LOW | acceptance-matrix.json | Missing FR-021..FR-024 and SC-004 rows | Fill them at accept |

**Coverage summary.** 42 requirement keys (FR-001..024, NFR-001..004, C-001..010, SC-001..004), each mapped to at least one active WP. FR-017's read half is moved to epic child #6535. Coverage is 100 %.

**Charter alignment.** No MUST violation. **Unmapped tasks.** None.

**Metrics.** Requirements: 42. Coverage: 100 %. Ambiguity: 0. Duplication: 0. Critical: 0. High: 0. Medium: 1. Low: 2.

**Next actions.** Ready. Implementation may continue (WP08 review cycle 2, then WP09…WP15). WP15 closes M1 and L1, and L2 is filled at accept.
