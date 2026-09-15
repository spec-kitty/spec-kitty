---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: sonar-per-pr-coverage-reuse-01M2FR32
mission_id: 01M2FR32NPWKD0HT1YN360FV1N
generated_at: '2026-09-14T14:38:26.378561+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/sonar-per-pr-coverage-reuse-01M2FR32/spec.md
    sha256: 272a2583443bf5eec1c4fc4ff01d060709a3b60342e7b7d0d802a7c1f9dbc6ce
  plan.md:
    path: kitty-specs/sonar-per-pr-coverage-reuse-01M2FR32/plan.md
    sha256: 459c4fbf2156ac4c1eee46a9492d59a10cc8b3d51fcf4c54b82be940296c1c17
  tasks.md:
    path: kitty-specs/sonar-per-pr-coverage-reuse-01M2FR32/tasks.md
    sha256: 43cde93a3a26144800946064829bb154403f222e28d7f3d6fe88de3b9559dcf9
  charter:
    path: .kittify/charter/charter.yaml
    sha256: cded0cf700d030b6f13d6c6f58d237e371ec41e0b874ca2630dcf234dd695fdf
verdict: ready
issue_counts:
  low: 2
  critical: 0
  high: 0
  medium: 3
  info: 0
findings:
- id: H1
  severity: medium
  category: charter
  summary: "Standing Order #5's gate triad names a shrink-only ratchet; NFR-007 specifies a floor and a mutation battery but no ratchet, and no work package owns one."
- id: D1
  severity: medium
  category: dependency
  summary: 'SC-010 cannot be satisfied inside the mission: it depends on #4350, an external vendor setting only the operator can change.'
- id: C1
  severity: medium
  category: coordination
  summary: WP04 and WP06 co-own the battery file across a characterise-then-flip seam; if the flip is missed the battery silently asserts a stale property.
- id: A1
  severity: low
  category: ambiguity
  summary: WP02's roots modelling decision is deferred into implementation rather than resolved in planning.
- id: T1
  severity: low
  category: terminology
  summary: spec.md deliberately uses outcome language while WP prompts name concrete surfaces; the mapping is implicit.
---

## Specification Analysis Report

**Mission**: `sonar-per-pr-coverage-reuse-01M2FR32` · **Issue**: #4334 · **Date**: 2026-09-14
**Artifacts**: `spec.md` (35 requirements, 10 success criteria), `plan.md`, `tasks.md` (6 WPs, 32 subtasks, 2 lanes)
**Prior scrutiny**: two adversarial squads (7 lenses total) already ran at the post-spec and post-plan
point-cuts; their findings were folded at `d934734` and `3936e95`. This analysis deliberately does
**not** re-litigate those — it looks for what survived both.

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| H1 | Charter | MEDIUM | charter SO#5; spec.md NFR-007; contracts/reporting-job-contract.md C5 | The charter's gate triad is *concrete floor + self-mutation test + shrink-only allowlist*. NFR-007 and contract C5 deliver the floor and a six-mutation battery; no ratchet is specified and no WP owns one. `plan.md` already marks SO#5 **PARTIAL** and records it as owed — declared, not resolved. | Either add a ratchet to WP04, or record why the third element is inapplicable (this gate is a relation over workflows, not a mutable allowlist — that is a defensible reading, but it should be written down, not assumed). |
| D1 | Dependency | MEDIUM | spec.md SC-010, FR-015, A-000; #4350 | SC-010 requires a non-zero published coverage measurement. Verified live: the project holds **no coverage metric at all** and every analysis reports `projectVersion: "not provided"` (server-side Automatic Analysis). Only the operator can clear this. | Accept as declared — A-000 and FR-015 already scope it honestly. Do **not** let a green pipeline be read as a satisfied SC-010. |
| C1 | Coordination | MEDIUM | tasks/WP04 T022; tasks/WP06 T029 | WP04 deliberately asserts the rule *detects the still-present duplicate* (non-vacuity against reality); WP06 must flip that seam to a clean-tree assertion after retirement. Both WPs co-own the file. If the flip is missed, the battery keeps asserting a property that is no longer true and nothing fails. | Keep — the sequencing is the point. WP06's DoD already carries the flip; the reviewer must verify it explicitly rather than trusting a green run. |
| A1 | Ambiguity | LOW | tasks/WP02 T009 step 3 | The `roots` modelling decision for two test-directory rows with no distinct source ownership is deferred into implementation with an instruction to record the rationale. | Acceptable — it needs the implementer's view of the router's unmatched-union behaviour. The instruction to record it is the mitigation. |
| T1 | Terminology | LOW | spec.md vs tasks/WP*.md | `spec.md` uses deliberate outcome language ("the reporting surface", "the measurement"); WP prompts name concrete workflows and files. | Intentional — the spec stays implementation-neutral and the prompts are the binding. No action. |

**Coverage Summary Table:**

| Requirement key | Has task? | Task IDs / WP | Notes |
|---|---|---|---|
| FR-001 single measurement per change | yes | WP06 | realised by the retirement |
| FR-002 report reads existing measurement | yes | WP05 | |
| FR-003 retire duplicate step | yes | WP06 | |
| FR-004 report waits for measurement | yes | WP05 | structural via `needs:` |
| FR-005 identity from validated record | yes | WP05 T024 | |
| FR-006 orphaned directories declared | yes | WP02 | |
| FR-007 incomplete measurement refused | yes | WP05 T023 | |
| FR-008 absent service degrades | yes | WP05 T023 | |
| FR-009 blockers declared | yes | WP06 T032 | #4350/#4351 both filed |
| FR-010 pinning rules inventoried | yes | WP03 T016, WP06 T028/T030 | |
| FR-011 same-origin guard | yes | WP05 T023 | mission's principal security change |
| FR-012 trusted analysis configuration | yes | WP05 T025 | |
| FR-013 measurement breadth corrected | yes | WP01 T002 | |
| FR-014 restricted to change events | yes | WP05 T023 | |
| FR-015 publication path proven | yes | WP06 T032 | blocked on #4350 — see D1 |
| FR-016 marker-mismatch set derived | yes | WP01 T005 | |
| NFR-001 surface executes no tests | yes | WP04, WP06 | mapped during this pass |
| NFR-002 aggregate cost bounded | yes | WP01 T003, WP02 T012 | |
| NFR-003 never merge-blocking | yes | WP05 T026 | |
| NFR-004 untrusted exposure not grown | yes | WP05 T023 | |
| NFR-005 settings not contributor-controllable | yes | WP05 T025 | |
| NFR-006 measurement attributed | yes | WP05 T023 | |
| NFR-007 regression closed by construction | yes | WP03, WP04 | ratchet element owed — **H1** |
| NFR-008 analysed tree matches measured tree | yes | WP05 T024 | |
| NFR-009 no per-file regression | yes | WP01 T006 | |

**Charter Alignment Issues:**

- **SO#5 (architectural gate discipline)** — PARTIAL, self-declared in `plan.md`. See H1.
- **SO#2 (campsite/tidy-first)** — PARTIAL, self-declared. The plan corrected an earlier false claim
  that WP01 was behaviour-preserving; it is not (it changes merge-blocking coverage behaviour). The
  honest downgrade is recorded rather than papered over. No further action needed at analysis time.
- All other standing orders: satisfied, with external evidence rather than self-citation.
- **Terminology Canon**: clean — Mission vocabulary throughout, no `feature*` aliases introduced.

**Unmapped Tasks:** none. All 32 subtasks appear in exactly one WP; the index and WP frontmatter
agree exactly; dependencies form two acyclic chains matching the computed lanes.

**Metrics:**

- Total requirements: **35** (16 FR, 9 NFR, 10 C) + 10 success criteria
- Total tasks: **32** subtasks across **6** work packages, **2** lanes
- Requirement coverage: **25/25 FR+NFR = 100%**
- Ambiguity count: **1** (A1, mitigated by a record-the-rationale instruction)
- Findings remediated during this pass: **2** (NFR-001 mapping; stale prompt-size annotations)
- Duplication count: **0**
- Critical issues: **0**

## Next Actions

No CRITICAL or HIGH findings — the mission is **ready for implementation**. Two squads have already
removed the serious defects, including a self-contradicting security assumption, a self-defeating
source-delivery mechanism, and a coverage-loss the original issue did not mention.

Two findings from the first pass were **remediated before this recording**: NFR-001 is now mapped to
WP04 and WP06, and the stale prompt-size annotations in `tasks.md` now carry actual line counts.
This re-record reflects the corrected artifacts.

Remaining, in order of value:

1. **H1** — decide the ratchet question and write the decision down, in WP04 or as a recorded rationale.

D1, C1, A1 and T1 need no pre-implementation action; they are risks to carry visibly, and each already
has its mitigation named in the artifacts.

**The one thing a reviewer must not concede**: this mission cannot restore a published quality report,
because #4350 blocks it independently. The honest claim on completion is "the suite runs once per
change and the report is correctly wired" — anything stronger is overclaiming.
