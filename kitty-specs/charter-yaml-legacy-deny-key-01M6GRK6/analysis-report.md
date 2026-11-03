---
schema: analysis-findings/v1
findings:
  - id: A1
    severity: low
    category: consistency
    summary: "spec.md NFR-004/SC-004 named a timing budget and a '#6556 all-keys fixture' that no task verified verbatim; both are restated structurally (prefix scan; the #6556 test's assembled document) and WP01 T005 now checks the dump explicitly."
counts: {critical: 0, high: 0, medium: 0, low: 1, info: 0}
verdict_hint: ready
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Consistency | LOW | spec.md NFR-004, SC-004; tasks/WP01-named-deny-key-refusal.md T005 | NFR-004 asked for a timing budget no task measured, and SC-004 named a fixture that is actually a test-built document. Both are restated in verifiable terms and T005 now asserts the dump. | Applied before recording; keep the structural wording. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 (named refusal message) | yes | T001, T002 | red-first then validator |
| FR-002 (no deny field declared) | yes | T006 | model_fields assertion |
| FR-003 (docstrings state the posture) | yes | T003, T004 | both docstrings |
| FR-004 (pinned beside the allow gate) | yes | T006, T007 | derived `DENY_KEYS` |
| NFR-001 (no import cycle) | yes | T002, T009 | literal prefix; import-graph gate re-run |
| NFR-002 (strictness unchanged) | yes | T005 | pre-existing tests unmodified |
| NFR-003 (no on-disk/writer change) | yes | T002, T005 | no field, no emit-list change |
| NFR-004 (bounded refusal cost) | yes | T002, T005 | prefix scan, unit tier |
| C-001 (ADR C-003 binding; no fields) | yes | T002, T007 | refusal, not declaration |
| C-002 (one deny vocabulary) | yes | T006 | `DENY_KEYS` is the comparand |
| C-003 (do not silently loosen) | yes | T001, T002 | the refusal is the delta |
| SC-001 (every deny key refused) | yes | T007 | parametrized over `DENY_KEYS` |
| SC-002 (message names ledger + never applied) | yes | T001, T007 | two stable facts |
| SC-003 (deny ∩ allow = ∅) | yes | T006 | both directions |
| SC-004 (strictness tests unmodified; 0 new keys) | yes | T005 | all-keys dump check |

**Charter Alignment Issues:** none. `DIRECTIVE_034` (test-first) is honored by T001-before-T002 and
by T006/T007 pinning before the PR; `NO_FULL_HEAVY_SUITES_IN_MISSION` is honored by the targeted
runs in T005/T009; `DIRECTIVE_024` bounds the change to two source files (one of them docstring
only) and two test files.

**Unmapped Tasks:** none — every `Txxx` belongs to exactly one WP, and every WP has a prompt.

**Metrics:**

- Total Requirements: 4 FR + 4 NFR + 3 C = 11
- Total Success Criteria: 4 (all referenced)
- Total Tasks: 9 (T001–T009)
- Coverage: 100% (11/11 requirements have at least one task; 4/4 success criteria referenced)
- Ambiguity Count: 0
- Duplication Count: 0
- Critical Issues Count: 0

**Design-consistency notes (not findings):**

- The mission's decision (`spec.md` "Which side the evidence supports") is repeated coherently in
  `research.md` R5, `plan.md` D1 and WP01's objective; the rejected alternative is recorded in all
  three rather than restated with different reasons.
- The allow-side parity gate (#6556) and the new deny-side pin land in the same file, which is what
  FR-004 asks for; neither test restates a key by hand.
