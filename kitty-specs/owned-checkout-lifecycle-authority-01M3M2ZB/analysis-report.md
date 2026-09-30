---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
mission_id: 01M3M2ZB5D4A33B8070F97DKW7
generated_at: '2026-09-30T04:28:21.698171+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/spec.md
    sha256: 81f088193e4eefcf832ec549d952031252bd47d622e322f5dda3fe1a17c6f88c
  plan.md:
    path: kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/plan.md
    sha256: ce4663bf193ac75724fa76970f47e03930ddcb81dbad8413c741cca1df311325
  tasks.md:
    path: kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/tasks.md
    sha256: 78b51a6dfa6c50f566ea85590f5f5bf7e1c7aaa8838f8127d793349636f8280c
  charter:
    path: .kittify/charter/charter.yaml
    sha256: cae74c9f8d1895556c96391ed8d733a628ffd85fe6b57c9b5a1f05ab6c873539
verdict: ready
issue_counts:
  critical: 0
  high: 0
  low: 2
  medium: 0
  info: 0
findings:
- id: I4
  severity: low
  category: inconsistency
  summary: Census still disagrees. Spec FR-001 and research R-03 now defer to plan Scale/Scope (94), but plan Summary L13/L18 still says 92, and WP03 L106/L133, WP04 L337 and WP15 L101 still cite '92' and R-03's '92-parameter census', which R-03 no longer contains.
- id: C3
  severity: low
  category: coverage
  summary: Spec US1-AS3 now lists 'a directory outside any repository (OWNERSHIP_BROKEN_POINTER)', but WP09 T049's matrix has no such row and WP02 does not pin it. T049 step 2 still says 'three rows' cite WP02 pins, although four rows do now.
---

## Re-run 2026-09-30 (spec edit: NFR-001 amendment)

- **NFR-001 amended (operator ruling 2026-09-30):** `SPEC_KITTY_HOME` stays in the R snapshot with exactly one named tolerance, the P-keyed prompt cache that owned `next` writes (`SPEC_KITTY_HOME/spec-kitty-prompts/<key of P>`), defined once in `tests/_owned_fixtures.py`. WP18's e2e snapshot is re-pointed to it (WP18 review cycle 1). No other requirement changed.
- **Resolved since the last run, dropped from the findings:** C2 (flagless `next` adoption restored red-first in WP19, FR-021 row added), U3 (AS6 hook asserts the flip happened, WP19), I5 (AS6 snapshot baseline taken after the flip, WP19). All three were verified by the WP19 reviews.
- **Still open, carried to closeout:** the remaining findings below (documentation drift; no code impact).


## Specification Analysis Report

Mission `owned-checkout-lifecycle-authority-01M3M2ZB` was re-analysed after planning commits `df192b7b9` and `c831607d5` ("apply analysis findings"). I read spec.md, plan.md, tasks.md, tasks/WP01..WP19, data-model.md, contracts/architectural-gate.md, research.md, quickstart.md and `.kittify/charter/charter.md`, and checked the previous report's diff against HEAD. I also verified the claim primitive's codes against `src/specify_cli/core/checkout_ownership.py` and `src/specify_cli/git/commit_helpers.py::_is_worktree_of`. Governance applied: the reviewer-renata profile and the review-action charter context.

The following are intentional design choices and are not flagged: the temporary dual keywords and `TRANSITIONAL(WP18)` markers that WP18 deletes, the retired subtask ids T056/T059, WP03 as a `planning_artifact`, and C-004/C-006/C-007 being enforced through prose.

### Prior findings: resolution status

| Prior ID | Status | Evidence |
|----------|--------|----------|
| C1 | **Resolved** (coverage) | tasks.md WP19 Independent Test, the WP19 outcome row "US3-AS6", and T102 step 10 plus a checklist item now cover US3-AS6. The test design has a new defect, raised as U3, and the edit removed a step, raised as C2. |
| I1 | **Resolved** | NFR-004 now names data-model.md's registry as the single authority and lists `OWNED_CHECKOUT_IS_MISSION_WORKTREE` and the `OWNERSHIP_*` / `WORKTREE_INVOCATION_REFUSED` codes. US1-AS3 gives the lane/coordination code. WP09 T049 step 2 no longer contains the stale sentence. |
| I2 | **Resolved** | NFR-004 has a carve-out for commands with no `--json` option: `Error: [<CODE>]` on stderr with a non-zero exit. |
| U1 | **Resolved** | `NEXT_OWNED_TOPOLOGIES` includes `LANES` in data-model, research R-02 (with a rationale that preserves today's behaviour), spec, WP02 (`test_next_topologies_accept_lanes` paired with `test_lifecycle_default_refuses_lanes`) and the WP19 FR-023 row and step 3. |
| U2 | **Resolved** | US1-AS3 lists the codes. WP02 adds `test_missing_path_is_refused` (`OWNERSHIP_BROKEN_POINTER`) and `test_non_worktree_directory_is_refused` (`OWNERSHIP_NESTED`). WP09 T049 cites both. Both codes match the source: for `R/docs`, `_is_worktree_of` returns False because toplevel ≠ path, and the comparator then returns NESTED; a missing path makes the toplevel probe fail, which gives BROKEN_POINTER. The new outside-repo row is raised as C3. |
| I3 | **Resolved** | The spec's Common-fixture paragraph and quickstart now defer to NFR-001's definition. WP02 T011 already implements that definition. |
| I4 | **Unresolved (carried forward)** | Only spec and research were aligned. The plan Summary and three WP prompts still say 92 (see the table below). |
| A1 | **Resolved** | FR-001 now names the rule-based exemptions and points to contracts/architectural-gate.md. It also states there is no site-level allowlist. |

### Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C2 | Coverage | MEDIUM | tasks/WP19:L167-173 (T102 step 10, formerly "Flagless adoption pins (T103 step 4)"); WP19:L190 (T103 step 4); WP19 outcome table L82-91; tasks.md WP19 Requirement Refs | The C1 remediation **overwrote** T102 step 10 instead of appending a step. The only test step for `next`'s flagless adoption was lost: adoption from a valid P runs owned, and a flagless run from a lane worktree gets the unchanged legacy refusal. T103 step 4 still reworks `_require_main_repo_unless_owned`, so that behaviour change now has no red-first test. The outcome table has no FR-021 / US7 row, and WP19's refs omit FR-021. WP08 covers adoption only for `context resolve`. | Restore the flagless-adoption pins as their own T102 step, renumbering so that US3-AS6 is step 11 and the commit is step 12. Add an FR-021 (next) row to the outcome table and FR-021 to WP19's requirement refs. |
| U3 | Underspecification | MEDIUM | tasks/WP19:L167-172 (T102 step 10); spec.md:L125 (US3-AS6) | The hook is installed on `get_main_repo_root` "or the equivalent site … whichever the merged code actually reads". A correct implementation reads nothing after validation, so the hook never fires, R's branch never changes, and all three assertions (count 1, paths under P, exit 0) pass vacuously. If the site is called *before* validation, the flip happens pre-validation and tests the wrong window. No assertion checks that the flip occurred. This conflicts with WP19's non-vacuity discipline. | Hook a point that is guaranteed to run after validation and before the prompt build, for example wrap `resolve_owned_or_adopt` so the flip runs after it returns, or wrap the prompt-builder entry. Add assertions that the hook ran exactly once and that `git -C R branch --show-current` equals `<other>` afterwards. Add a mutation check: re-deriving via `get_main_repo_root` after the hook must go red. |
| I4 | Inconsistency | LOW | plan.md:L13, L18 (Summary: "92") vs L46-47 (Scale/Scope: "94 … in 30 files"); tasks/WP03:L106, L133; tasks/WP04:L337 ("14 of the 92"); tasks/WP15:L101 ("research.md R-03 (the 92-parameter census …)") | Spec FR-001 and research R-03 now defer to plan Scale/Scope (94). The plan's own Summary still says 92, and three WP prompts cite 92. WP15 also points readers to a "92-parameter census" in R-03 that no longer exists. Execution is unaffected, because G4/G5 have an empty allowlist and floor ≥ 1. | Change the plan Summary to "all (census in Scale/Scope)" and align the WP03, WP04 and WP15 wording. |
| I5 | Inconsistency | LOW | tasks/WP19:L163 (T102 step 8: every owned scenario wrapped in `r_snapshot`, 0 differences); WP19:L167 (step 10 flips R's branch); spec.md NFR-001 | NFR-001 requires 0 R-snapshot differences in *every* owned acceptance scenario, including R's `HEAD`. The US3-AS6 test changes R's `HEAD` on purpose, so under step 8 as written it either fails or needs an unstated exemption. | Scope step 8 to exclude the AS6 scenario, or take the AS6 snapshot baseline after the flip, and state which in step 10. Optionally, add a sentence to NFR-001 that test-induced R mutations are excluded. |
| C3 | Coverage | LOW | spec.md:L74 (US1-AS3 "a directory outside any repository (`OWNERSHIP_BROKEN_POINTER`)"); tasks/WP09 T049 matrix (L383-395), step 2 (L396); WP02 T007 pins | The spec adds a new invalid value that has no matrix row in WP09 T049 (still "5 commands × 11 cases") and no WP02 pin. The code is right per the source: a failed toplevel probe gives BROKEN_POINTER. T049 step 2 still refers to "the three rows marked 'WP02's minter test pins'", but four rows cite WP02 pins (missing path, `R/docs`, lane, coordination). | Add an "outside any repository" row (for example `tmp_path / "plain-dir"`, created, with no `git init`) and update the case count to 12. Fix the "three rows" wording in step 2. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs / WPs | Notes |
|-----------------|-----------|----------------|-------|
| FR-001 one-ownership-validator | Yes | WP01 T004-T005; WP18 T095-T097 (+WP15, WP17 sweep) | A1 resolved |
| FR-002 next-uses-validator | Yes | WP02 T006; WP19 T102-T103 | O9 |
| FR-003 validated-once | Yes | WP07 T037; WP16 T089; WP14; WP19 T102 | US3-AS6 now mapped (see U3) |
| FR-004 owned-status-listing | Yes | WP09 T044-T045 | |
| FR-005 owned-plan-setup | Yes | WP09 T046 | |
| FR-006 owned-wp-context | Yes | WP04 T016-T018; WP05; WP08 T038-T040 | |
| FR-007 stale-copy-never-wins | Yes | WP04, WP08 T041, WP09 T045, WP11, WP13 T074, WP19 T104 | |
| FR-008 next-crosses-tasks-implement | Yes | WP11 T061; WP19 T102; WP12 | |
| FR-009 owned-runtime-reads | Yes | WP11 T057, T060; WP12 T068 | |
| FR-010 owned-review-base | Yes | WP12 T064, T065, T068 | |
| FR-011 owned-workspace-kind | Yes | WP05 T022-T025; WP04 | |
| FR-012 coordination-probe-hardening | Yes | WP11 T057, T062; WP19 (CLI envelope) | |
| FR-013 owned-status-under-worktrees | Yes | WP06 T028-T031; WP13 | |
| FR-014 coordination-protections-unchanged | Yes | WP06 T027, T031 | |
| FR-015 atomic-finalize | Yes | WP13 T070-T073 | |
| FR-016 governance-reads-at-owned-create | Yes | WP10 T052-T054 | |
| FR-017 charter-authoring-stays-at-root | Yes | WP10 T054 | |
| FR-018 typed-refusal-unsupported-actions | Yes | WP09 T047 | I2 resolved |
| FR-019 per-checkout-lookup-isolation | Yes | WP05 T022, T024 | |
| FR-020 invalid-owned-path-refused | Yes | WP02 T007, T009; WP08; WP09 T049 | See C3 |
| FR-021 validated-flagless-adoption | Partial | WP02 T009; WP08 T038, T040; WP19 T103 step 4 (no test) | See C2 |
| FR-022 existing-owned-commands-unchanged | Yes | WP14 T079; WP15 T083; WP16 T088; WP17; WP19 T102 | |
| FR-023 topology-per-command | Yes | WP02 T006; WP04 T019; WP11; WP19 T102 | U1 resolved (LANES pinned) |
| FR-024 glossary-and-adrs | Yes | WP03 T012-T015 | |
| FR-025 unified-review-base | Yes | WP12 T064, T065, T069 | |
| FR-026 complexity-ceiling-restored | Yes | WP10 T050-T051; WP14 T075-T076 | |
| NFR-001 repository-root-untouched | Yes | WP02 T011; WP18 T098; WP19 T102 step 8 | See I5 |
| NFR-002 validation-count | Yes | WP07 T037; WP16 T089; WP18 T099 | |
| NFR-003 command-latency | Yes | WP18 T099 | nightly `performance` |
| NFR-004 typed-errors | Yes | WP01; WP08 T039; WP09 T049 | I1 and I2 resolved |
| NFR-005 quality-gates | Yes | every WP DoD; WP18 T100 | |
| NFR-006 cross-platform-identity | Yes | WP01 T003 | |
| US3-AS6 fact-not-re-derived (scenario) | Yes | WP19 T102 step 10 | See U3 and I5 |

**Charter Alignment Issues:** none. ATDD-first (C-011) red-first ordering, the terminology canon (no `--feature`), single canonical authority (G1-G3), the layer rules and `NO_FULL_HEAVY_SUITES_IN_MISSION` all remain intact after the edits. C2 matters under ATDD-first: T103 step 4 now has a behaviour change with no red-first test. It is graded MEDIUM rather than CRITICAL because the WP's own Done-when rule ("every row has a red-first test") would catch it once a row is restored.

**Unmapped Tasks:** none. T056 and T059 are retired ids, by design.

**Structural checks (pass):** `check-prerequisites` returns `valid: true`. `lanes.json` was recomputed at planning commit `c831607d5`. The remediation edits touch no owned_files, dependencies or wave assignments.

**Issue-matrix heads-up (non-gating, #3469):** unchanged from the prior report. Record the out-of-scope and dependency citations (#4250, #5100, #5099, #3443, #3474, #4959, #4980, #5259, #4785) as context-only or `not-applicable` rows at approval time.

**Metrics:**

- Total Requirements: 32 (26 FR + 6 NFR)
- Total Tasks: 103 active subtasks across 19 WPs
- Coverage: 100% of requirements have ≥1 task. FR-021's `next` arm has a task with no test step (C2). All acceptance scenarios, including US3-AS6, are mapped.
- Ambiguity Count: 0
- Duplication Count: 0
- Critical Issues Count: 0
- Prior findings: 7 of 8 resolved; 1 carried forward (I4). New findings: 4 (C2, U3, I5, C3).

### Next Actions

- No CRITICAL or HIGH findings: the verdict is ready and implementation may proceed.
- Fix C2 before WP19 is implemented. It is a one-step restore in T102, plus an FR-021 row and ref.
- Tighten U3 and I5 together in WP19 T102 steps 8 and 10: use a guaranteed hook point, assert that the flip happened, and add a snapshot carve-out.
- C3 and I4 are wording and matrix alignment: WP09 T049 (add the outside-repo row), plus the plan Summary and the WP03, WP04 and WP15 census wording.

### Re-analysis delta (NFR-001 clarification, WP06 review cycle 1)

The only input change since the previous report is a clarification of NFR-001 in spec.md. The shared lock root now names exactly one tolerated delta: the pre-existing per-mission status mutex (`status/locking.py::feature_status_lock_path`), which may appear as a single empty `<mission>.status.lock`. The git common dir is shared by P and R by construction, so no owned transactional write can avoid it.

The tolerance is defined once in `tests/_owned_fixtures.py`, and every other lock-root delta still fails. No requirement, task or coverage mapping changed, and no new finding arises. WP19 T102 step 8 and all NFR-001 oracles pick up the named tolerance from the shared fixture.

### Re-analysis delta (NFR-004 registry alignment)

The only input change is in spec.md. NFR-004's list of registered codes now names five pre-existing wire codes that owned commands already emit: `WORKTREE_REGISTRY_UNAVAILABLE`, `FEATURE_CONTEXT_UNRESOLVED`, `MISSION_CONTEXT_CONFLICT`, `OWNED_OPTION_UNSUPPORTED` and `OWNED_INPUT_INVALID`. data-model.md's Error code registry, the single authority, lists the same codes, so spec and registry now agree. No requirement, task or coverage mapping changed, and no new finding arises.
