---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: issue-matrix-source-issue-gating-01M6EJTT
mission_id: 01M6EJTT36CSYFRJRWNB4HJGGN
generated_at: '2026-11-02T16:57:07.156161+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/issue-matrix-source-issue-gating-01M6EJTT/spec.md
    sha256: defb2591cb5f69d334a10943a6aa491823332aa3271f6a9170569d0eac63e74f
  plan.md:
    path: kitty-specs/issue-matrix-source-issue-gating-01M6EJTT/plan.md
    sha256: 1975edbdfbb5e90810cbac9e150aced511bf3a622a686a84b0d3f45275a04733
  tasks.md:
    path: kitty-specs/issue-matrix-source-issue-gating-01M6EJTT/tasks.md
    sha256: 50479455d22de9b69c31e135d051093b5a2acb186c1ed13c1998f5e986eb66ed
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  high: 0
  low: 2
  medium: 1
  critical: 0
  info: 0
findings:
- id: A1
  severity: medium
  category: inconsistency
  summary: WP02 T006 leaves the spec.md read count ambiguous (reuse the already-scanned text vs a second read), while NFR-003 bounds it.
- id: A2
  severity: low
  category: ambiguity
  summary: "The spec's illustrative `follow-up: patched in #7004` example cites a real issue number, so this Mission's own matrix carries a non-gating #7004 row."
- id: A3
  severity: low
  category: underspecification
  summary: FR-005's ratchet is proven only by untouched pre-existing suites; no new assertion names the four preserved outcomes explicitly.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Inconsistency | MEDIUM | spec.md:NFR-003; tasks/WP02-source-issue-promotion.md:T006 | NFR-003 allows "at most one `meta.json` + one `spec.md` read per call"; T006 says "prefer reading the already-scanned `spec.md` text once" but the discovery path scans `spec.md` through `detect_issue_references`, so the simpler implementation adds one read. | Implement the derivation with a single `spec.md` read and state it in the WP history; the requirement as written is satisfied, the wording is what drifts. |
| A2 | Ambiguity | LOW | spec.md:US2 scenario 2 | The illustrative `**Input**: Issue #6926, follow-up: patched in #7004` uses a real issue number, so `#7004` becomes a non-gating `not-applicable` row in this Mission's own matrix. | Accepted: the row is non-gating by construction and demonstrates the intended `follow-up:` semantics. Record the verdict explicitly rather than rewording. |
| A3 | Underspecification | LOW | spec.md:FR-005 / SC-004 | FR-005 is a `[ratchet]` row proven by the pre-existing suites running unchanged; no new assertion names the preserved outcomes. | Accept: SC-004 names the untouched suites as the paired control, which the non-vacuity tactic allows for a ratchet row. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 positional-label-scope | yes | T001, T002, T003 | Scaffold-path repro + classifier twin |
| FR-002 source-issue-derivation | yes | T005, T006 | Three derivation sources, each its own fixture |
| FR-003 never-non-gating | yes | T005, T007 | Promotion on the existing reference |
| FR-004 shared-classification | yes | T007, T009 | Both call sites share one helper; four views asserted |
| FR-005 existing-outcomes-preserved | yes | T004, T008, T012 | Pre-existing suites as the control |
| NFR-001 classifier-purity | yes | T003, T004 | Pattern stays pure; determinism test already exists |
| NFR-002 metadata-fail-open | yes | T005, T006 | Three-way malformed-metadata control |
| NFR-003 bounded-reads | yes | T006 | Guarded single reads |
| C-001 occurrence-compat | yes | T002, T004 | Optional field with default |
| C-002 one-pattern | yes | T006 | `issue_numbers_in_text` reuses `_GH_ISSUE_PATTERN` |
| C-003 verdict-vocabulary | yes | T005 | `not-applicable` asserted still reachable for context refs |
| SC-001..SC-004 | yes | T001, T005, T009, T012 | One asserting package each |

**Charter Alignment Issues:** none. The plan's charter table covers the single-authority,
ATDD-first, smallest-viable-diff, locality and fail-safe rules; no MUST is diluted.

**Unmapped Tasks:** none.

**Metrics:**

- Total Requirements: 11 (5 FR, 3 NFR, 3 C) plus 4 success criteria
- Total Tasks: 3 work packages, 12 subtasks
- Coverage %: 100 (every requirement maps to at least one subtask)
- Ambiguity Count: 1
- Duplication Count: 0
- Critical Issues Count: 0

## Next Actions

- No CRITICAL issues: proceed to `/spec-kitty.implement` with WP01.
- Resolve A1 while implementing T006 (single `spec.md` read), and record the A2 verdict
  explicitly at wrap-up.

## Remediation

No remediation is required before implementation. A1 is an implementation note, A2 is an
accepted demonstration, and A3 is allowed for a ratchet row.
