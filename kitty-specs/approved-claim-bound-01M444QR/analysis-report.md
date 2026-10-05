---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: approved-claim-bound-01M444QR
mission_id: 01M444QR19BY00CKEDYSTTYBKS
generated_at: '2026-10-04T23:54:09.578018+00:00'
analyzer_agent: orchestrator
input_artifacts:
  spec.md:
    path: kitty-specs/approved-claim-bound-01M444QR/spec.md
    sha256: f7696030627c852cf72ab242309508fbc7f4d20e0dbea0eeecb21a15d1c38483
  plan.md:
    path: kitty-specs/approved-claim-bound-01M444QR/plan.md
    sha256: 307fc0fa05127a7f79ffa6aa73fd7a8809e2a5d44a42a878fb4b66fd77fbb1cc
  tasks.md:
    path: kitty-specs/approved-claim-bound-01M444QR/tasks.md
    sha256: 9083584b578c4447616633037224732c8084a81cb71f915b92eb92a4fd5327bf
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 69c63e91ae27a02b0c07b48939f72198b0d2654ed5bee42e3d6bc1d5d4e71a6e
verdict: ready
issue_counts:
  medium: 4
  low: 3
  critical: 0
  high: 0
  info: 0
findings:
- id: I1
  severity: medium
  category: inconsistency
  summary: FR-003 says the gate applies 'the same check'; plan D-3 and WP03 use a different predicate (content since the claim-time validated tips).
- id: I2
  severity: medium
  category: inconsistency
  summary: plan D-6 lists three tests as retired and the oracle as replaced; tasks keep the lane-tips test and only reword the oracle docstring.
- id: I3
  severity: low
  category: inconsistency
  summary: The contract says the orchestrator reports the code 'in the envelope data'; WP05 names the key preflight_error_code.
- id: C1
  severity: medium
  category: coverage
  summary: C-004, C-006 and SC-001..SC-006 are in no work package's requirement_refs; they are process or outcome checks covered by review and the PR.
- id: C2
  severity: low
  category: coverage
  summary: FR-012 is referenced by WP07 only, while the work that preserves existing refusals is WP02 T011.
- id: U1
  severity: low
  category: underspecification
  summary: data-model.md describes the claim-time result but not the gate function's inputs (validated tips, anchor SHAs).
- id: U2
  severity: medium
  category: underspecification
  summary: 'Two implementation checks stay open: the in-process transition shell on a LANES mission, and whether attestation evidence overwrites review evidence.'
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | MEDIUM | spec.md FR-003; plan.md D-3; tasks/WP03 T013 | The spec says the gate applies "the same check"; the plan and WP03 ask whether content arrived on a lane since the claim-time check, with pre-mutation SHAs as references. | The plan wording is the correct one (the same check would pass vacuously). Treat FR-003 as "the gate refuses lane content that arrived after the up-front check"; align the spec sentence at closeout. |
| I2 | Inconsistency | MEDIUM | plan.md D-6; tasks/WP01 T003, T005; tasks/WP02 T011 | The plan lists three tests as retired or rewritten and the test oracle as replaced. The tasks delete one, rewrite one, keep one (it stays true) and reword the oracle's docstring. | The tasks are the narrower, justified reading. Align plan D-6 at closeout. |
| I3 | Inconsistency | LOW | contracts/consolidate-refusals.md; tasks/WP05 T022 | The contract does not name the envelope key. | Name `data["preflight_error_code"]` in the contract. |
| C1 | Coverage | MEDIUM | spec.md C-004, C-006, SC-001 to SC-006 | No work package lists them in `requirement_refs`. | They are checked at review and in the PR (no new gate, no priority change, outcome criteria). SC-005 is T027, SC-006 is T021. No task change needed. |
| C2 | Coverage | LOW | tasks.md WP02, WP07 | FR-012 is referenced by WP07; WP02 T011 does the preserving work. | Acceptable: WP07 verifies it on the integrated base. |
| U1 | Underspecification | LOW | data-model.md | The gate function's inputs are not in the data model. | Add two lines at closeout. |
| U2 | Underspecification | MEDIUM | tasks/WP02 T006; tasks/WP04 Risks | Two facts could not be verified at planning time. | Both prompts tell the implementer what to do in either case and to report it. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 approval stamp is the authority | yes | T001, T002, T007 | one reader |
| FR-002 post-approval commit refused up front | yes | T006, T008, T009 | red-first, 4 cells |
| FR-003 gate re-check | yes | T012, T013, T014, T032 | see I1; T032 pins the case the older checks miss |
| FR-004 verified is honest | yes | T006, T012, T013 | folded into FR-002 and FR-003 |
| FR-005 unstamped approval fails closed | yes | T008, T009, T018 | |
| FR-006 attestation | yes | T016, T017, T018 | |
| FR-007 attestation never lifts a post-approval commit | yes | T016, T018 | |
| FR-008 rewritten lane refused | yes | T008, T010 | through the claim builder |
| FR-009 tool-made movement not refused | yes | T008, T010 | each with a refusing control |
| FR-010 latest approval wins | yes | T007, T010, T006 (rework) | |
| FR-011 every landing entry point | yes | T021, T022, T023, T030, T031 | contract version; resume after a mid-run interruption |
| FR-012 existing refusals unchanged | yes | T011, T029 | see C2 |
| FR-013 red-first reproduction | yes | T006 | |
| FR-014 truthful fixtures | yes | T003, T004, T005 | |
| FR-015 documentation | yes | T020, T024, T025, T026 | |
| NFR-001 bounded extra cost | yes | T011 | read-count test |
| NFR-002 code quality | yes | every WP, T029 | |
| NFR-003 coverage | yes | every WP | CI diff-cover gate |
| NFR-004 non-destructive refusals | yes | T006, T012, T021 | tips asserted |
| C-001 one rollback authority | yes | T014 | |
| C-002 status stays git-free | yes | T007 to T009 | module boundary gates |
| C-003 no fail-open | yes | T003, T007 | |
| C-005 scope of the bound | yes | T009, T010 | |
| C-007 red before fix | yes | T006, T012, T018, T021 | |
| C-004, C-006 | review | n/a | see C1 |

**Charter Alignment Issues:** none. ATDD-first, tidy-first, single authority, role separation and the no-heavy-suites rule are each reflected in the prompts.

**Unmapped Tasks:** none. T027 and T029 are verification tasks tied to SC-005, FR-012 and NFR-002.

**Metrics:**

- Total requirements: 15 FR, 4 NFR, 7 C, 6 SC
- Total tasks: 32 subtasks in 7 work packages (T030 to T032 were added to WP07 from the WP03, WP04 and WP05 reviews: orchestrator contract version, a resume case, review tidy-ups)
- Coverage: 100% of FR and NFR have at least one task
- Ambiguity count: 0
- Duplication count: 0
- Critical issues count: 0

## Next Actions

No critical or high finding. Implementation may start. I1, I2, I3 and U1 are wording alignments in planning artifacts, to be made at closeout.
