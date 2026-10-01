---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: test-suite-remediation-01M3SSDW
mission_id: 01M3SSDWED2X2HYRKNPYQM9EN1
generated_at: '2026-09-30T20:51:03.462603+00:00'
analyzer_agent: claude
input_artifacts:
  spec.md:
    path: kitty-specs/test-suite-remediation-01M3SSDW/spec.md
    sha256: 28541b02abc19e84e1f3d1042e4a9883aac7cb949cfa1b215965a073edd93fc5
  plan.md:
    path: kitty-specs/test-suite-remediation-01M3SSDW/plan.md
    sha256: 65ce17734ced400dd1f4eef85d3e82183480d0e600b7f81d8bdcd110c6dadd33
  tasks.md:
    path: kitty-specs/test-suite-remediation-01M3SSDW/tasks.md
    sha256: cc92ceb40739d6ec0d4b4e63b417bace04834852f7e9ae16761adcd455190a1e
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 69c63e91ae27a02b0c07b48939f72198b0d2654ed5bee42e3d6bc1d5d4e71a6e
verdict: ready
issue_counts:
  high: 0
  medium: 2
  critical: 0
  low: 5
  info: 0
findings:
- id: N1
  severity: medium
  category: inconsistency
  summary: "The WP11 failing-first fold contradicts the WP11 sequencing that was left in place. The T052 'Commit order' box and the DoD commit the loader test file first, before T050 and T051. But WP11 T052 still says 'Parallel?: After T050 and T051', and tasks.md WP11 Parallel Opportunities still says 'T052 needs both'."
- id: N2
  severity: medium
  category: inconsistency
  summary: "The D1 red standard is applied inconsistently in the dead-symbol chain. WP10 states that 'a module-scope import that errors at collection is not an acceptable red' and imports the seam inside each test body. WP11's failing-first commit prescribes exactly that kind of red: a collection-time 'ModuleNotFoundError: tests.architectural._dead_symbol_allowlist' for the whole file, not per-test failures."
- id: N3
  severity: low
  category: inconsistency
  summary: The tasks.md T052 summary ('M12 schema battery plus data-level parity against the old gate constants') and the Subtask Index ('Loader tests (M12) + data parity') contradict WP11 T052 step 4 ('Real-file invariants (not parity ...) Do not assert 293 or 91'). The parity check is a scratch step in T053, not committed test content.
- id: N4
  severity: low
  category: inconsistency
  summary: The C6 fold changed only tasks.md closeout (per-WP reviewers re-run picks; the orchestrator tallies and sets reviewer_rerun). quickstart.md:24 still says 'the independent reviewer' re-runs at least 6 FIX and at least 2 RETIRE personally and sets reviewer_rerun.
- id: N5
  severity: low
  category: inconsistency
  summary: "The data-model.md:184 pin-record example still shows the pair-level F11 form 'partition: emitting == set(_CASES) ...'. The plan (IC-07) and WP08 now prescribe the per-site partition."
- id: N6
  severity: low
  category: inconsistency
  summary: "The coord-branch issue-matrix.json, which closeout step 5 relies on, carries stale evidence_ref text: #3213 says the 'retired-sync gate module FR-002 retires', but the disposition is KEEP + re-cite; #5346 cites 'FR-006..FR-010', although FR-010 is withdrawn. Closeout step 5 checks only that the verdicts are terminal."
- id: N7
  severity: low
  category: underspecification
  summary: Rule A allows a sanctioned out-of-map src/ fix in any WP, but its fix branch requires only a WP-notes rationale and no orchestrator notification or ownership claim. Two parallel lanes could edit the same product file, or a lane fix could shift dead-symbol parity. Closeout step 3's consolidated-branch gate run catches the latter only after approval.
---

# Cross-artifact re-analysis: test-suite-remediation-01M3SSDW (round 2)

**Analyst:** reviewer-renata, running `/spec-kitty.analyze` again in read-only mode. Nothing was edited apart from the recorder's `analysis-report.md`, and no tests were run.

**Inputs:**
- the current `spec.md`, `plan.md`, `tasks.md`, the frontmatter and fold sections of all 15 WPs, and `.kittify/charter/charter.md`;
- the fold commits `aabcd96`, `3c9ba86` and `e2e0e48`;
- `data-model.md`, `quickstart.md` and `traces/design-decisions.md`, where the folds point to them;
- the coord-branch `issue-matrix.json` (read-only), because closeout step 5 now relies on it.

The D1 C-011 reading itself is not re-litigated. It was checked only for being recorded and applied consistently.

## Prior findings: resolution check

| Prior ID | Status | Evidence |
|---|---|---|
| D1 (C-011) | **Resolved** as recorded: in the plan's Charter Check ATDD row, the plan's Risk rulings "D1 (analysis)", the `traces/design-decisions.md` 2026-09-30 rulings entry, tasks.md mission-wide rules, and a `## Definition of Done (C-011)` section in all 15 WPs (product-code, test-only, chain and docs variants). Applied consistently, with one exception on the red form (N2). | `plan.md:104`, `:697`; `design-decisions.md` (the final entry); `grep -c "Definition of Done (C-011)"` = 1 per WP |
| F1 (plan stale) | **Resolved.** The supersession banner is present, and IC-04 (both HOME redirects), IC-05 (32), IC-07 (per-site F11), IC-08 (`agent_utils.directories`, non-tautological F10), IC-09 (strict xfail, `--runxfail`), IC-10/IC-11 (p1 stays green), IC-11 (usage grep) and IC-12 (`>= 16`) are all updated. The evidence location is reconciled in the plan and data-model §1/§2/§3/§4. One stale example remains (N5). | `plan.md:261-265`, `:398`, `:430`, `:481-483`, `:513`, `:522`, `:544-545`, `:576`, `:600-603`, `:627-629` |
| F2 (C-004 vs WP09) | **Resolved.** C-004 was amended: slice-level passes are out, and inventoried FR-006/FR-007 pins stay in scope. The tasks.md coverage note names WP09's F10 edit. | `spec.md:141`; `tasks.md` coverage note |
| B1 (NFR-001) | **Resolved.** The wording is now an aggregate "+9" with a per-file non-decrease rule. | `spec.md:128` |
| C1 (FR-005 path) | **Resolved.** Rule A is in tasks.md and every WP, `tasks.md:33` is relaxed, and the "`src/` must be empty" rule is explicitly lifted for the rule-A fix commit. | `tasks.md:33-34`, `:47-49`; WP02 "Additional mission-wide rules" |
| C2 (evidence access) | **Resolved.** Rule B requires full records, with a fallback to the review-ref or commit body. | tasks.md rule B; WP rule 4/B |
| C3 (types) | **Resolved.** Rule C runs mypy on the touched `src/` files plus the typed test modules of WP05, WP10, WP11 and WP12. | WP05:155, WP10:174, WP11:157, WP12:177 |
| D2 (xfail vs C-003) | **Resolved.** The ruling is recorded in the plan's Risk rulings and the tracer. | `plan.md:698`; tracer |
| E1 (refs) | **Resolved.** tasks.md and the WP frontmatter now carry NFR-004 for WP06–WP10, C-002/SC-005 for WP12 and SC-005 for WP10, and the coverage table was updated. | tasks.md coverage table; WP frontmatter |
| F3 (WP05 count) | **Resolved.** "32 passed (29 + 3 self-tests)" appears in tasks.md, the plan and quickstart. | — |
| C4 (SO 8) | **Resolved.** Closeout step 5 now verifies that the verdicts are terminal. The coord-branch `issue-matrix.json` has rows for #3113, #3213, #5346 and #5353. Evidence-text drift remains (N6). | `tasks.md` closeout step 5 |
| A1, B2, B3, B4, F4, F5, D3, C5, C6 | **Resolved**: the tally note; the C-001 named-file reading; the FR-007 count wording; the L9 decision; the WP15 `create_intent` note; `ALLOWLIST` added to the WP10 and T050 lists; the CLAUDE.md follow-up in closeout; the IC merge mapping; the SC-005 owner (quickstart drift remains, N4). | — |

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| N1 | Inconsistency | MEDIUM | WP11 T052 box (`:226`) vs WP11 T052 `Parallel?` (`:261`); `tasks.md:447` vs `:452` | The new commit order (tests first) contradicts the old "T052 after T050+T051" sequencing, which was left in place. | Change `Parallel?` to "First: committed red before T050/T051; finalized after them". Change `tasks.md:452` to "T052 is drafted and committed first (red); T050 and T051 then turn it green". |
| N2 | Inconsistency | MEDIUM | WP11 T052 box and DoD (red = collection `ModuleNotFoundError`) vs WP10 Objectives ("a module-scope import that errors at collection is **not** an acceptable red") | Within the one D1 chain, two opposite rules govern what counts as a red failing-first commit. A collection error reds the whole file for one reason and cannot show that each M12 plant fails for its own rule. | Either import the loader inside each test body (a WP10-style `_loader()` helper), so each test is red individually at the red commit, or state in the D1 tracer entry that a collection-level red is acceptable for WP11. Keep WP10 and WP11 on one standard. |
| N3 | Inconsistency | LOW | `tasks.md:442`, the Subtask Index T052 row; WP11 T052 step 4 | The summary says "data parity" is committed test content; the WP says explicitly "not parity". | Reword the T052 summary as "M12 schema battery plus real-file invariants (the parity check is scratch-only, T053)". |
| N4 | Inconsistency | LOW | `quickstart.md:24`; `tasks.md` closeout step 1 | The SC-005 owner wording differs between quickstart and tasks.md. | Align quickstart with "per-WP reviewers re-run their picks; the orchestrator tallies and sets `reviewer_rerun` at closeout". |
| N5 | Inconsistency | LOW | `data-model.md:184` | The F11 example uses the pair-level partition form. | Replace the example with "per-site partition: has_remediation or state in _PASS_STATES or (f, s) in _EXEMPT_STATES". |
| N6 | Inconsistency | LOW | coord `kitty/mission-test-suite-remediation-01M3SSDW:…/issue-matrix.json`; `tasks.md` closeout step 5 | The row evidence text contradicts the dispositions (#3213 is KEEP, not retired) and cites the withdrawn FR-010. | Extend closeout step 5: "also correct evidence_ref text (#3213 → KEEP + re-cite; #5346 → FR-006..FR-009, FR-011)". |
| N7 | Underspecification | LOW | tasks.md rule A; WP "Additional mission-wide rules" A | A sanctioned `src/` fix has no orchestrator-notify or ownership step. That risks a cross-lane collision and late dead-symbol parity drift. | Add "notify the orchestrator before the `fix(...)` commit (the file path), and run `tests/architectural/test_no_dead_symbols.py` by name if the fix touches a module with `__all__`" to the fix branch of rule A. |

## Coverage Summary Table

| Requirement Key | Has Task? | Task IDs | Notes |
|---|---|---|---|
| FR-001 | Yes | T001, T002, T005 | WP01 |
| FR-002 | Yes | T006–T014 | WP02, WP03 |
| FR-003 | Yes | T011–T014 | WP03 |
| FR-004 | Yes | T015–T023 | WP04, WP05 |
| FR-005 | Yes | T003, T004, T006; rule A in every WP | Resolved (C1) |
| FR-006 | Yes | T024–T032, T065 | WP06, WP07, WP14 |
| FR-007 | Yes | T033–T044, T065 | WP08, WP09, WP14; C-004 amended (F2) |
| FR-008 | Yes | T069 plus the conversion WPs | — |
| FR-009 | Yes | T045–T073 | WP10–WP15 |
| FR-010 | n/a (withdrawn) | T069 (disposition line) | Accepted residual |
| FR-011 | Yes | the plant subtask of every WP; rule B | — |
| NFR-001 | Yes | T005, T007, T014, T020, T023 | Aggregate wording (B1 resolved) |
| NFR-002 | n/a (withdrawn) | — | — |
| NFR-003 | Yes | T027, T032, T039, T044, T046, T060, T065 | — |
| NFR-004 | Yes | rule 5, WP01–WP10 | E1 resolved |
| NFR-005 | Yes | rule C in every WP | C3 resolved |
| C-001 | Yes | rule 1 in every WP | — |
| C-002 | Yes | WP02, WP06–WP09, WP12, WP13 | — |
| C-003 | Yes | WP08, WP11, WP12, WP14 | D2 recorded |
| C-004 | By exclusion (amended) | — | Consistent with WP09 |
| C-005 | Yes | T004; rule A | — |
| C-006 | Yes | T022, T040, T070 | — |
| C-007 | Yes | rule 2 in every WP | — |
| C-008 | Yes | T069, T070 | — |
| SC-001 | Yes | T001, T002, T005 | — |
| SC-002 | Yes | T006–T014 | — |
| SC-003 | Yes | T046, T049, T060 | — |
| SC-004 | Yes | T027, T032, T039, T044, T069 | — |
| SC-005 | Yes | WP01–WP10, WP12–WP14 plant subtasks | Owner is stated in tasks.md (N4: quickstart drift) |
| SC-006 | n/a (withdrawn) | — | — |

## Charter Alignment Issues

None at HIGH or CRITICAL.

- **C-011:** the D1 reading is recorded in three places (the Charter Check, the Risk rulings and the tracer) and in every WP's DoD. The one application inconsistency is N2 (the red form in WP11 vs WP10).
- **C-003:** the strict xfail ruling is recorded (D2).
- **Standing Order 8:** the matrix rows exist on the coord branch; the text drift is N6.
- **DIRECTIVE_041, 043, 044 and 046, NO_FULL_HEAVY_SUITES_IN_MISSION, Burn-down (a), the `__all__` convention, pack tiers and the terminology canon:** unchanged from round 1 and clean. No fold introduced a `feature` term, a directory sweep or a new allowlist without a cap.

## Unmapped Tasks

None. All 73 subtasks map to exactly one WP.

## Metrics

| Metric | Value |
|---|---|
| Total requirements | 30 (27 active; FR-010, NFR-002 and SC-006 withdrawn) |
| Total tasks | 73 subtasks in 15 WPs |
| Coverage % | 100% of active requirements (C-004 by exclusion, now consistent) |
| Ambiguity count | 0 |
| Duplication count | 0 |
| Critical issues count | 0 |
| Prior findings resolved | 20 / 20 |

## Next Actions

**Ready to implement.** There is no CRITICAL or HIGH finding.

1. Fold N1 and N2 before WP11 starts. They are a two-line sequencing fix and a one-rule decision on the red form.
2. N3–N7 are text-level and can ride along with any later planning commit or the closeout.
