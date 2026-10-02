# Post-spec adversarial squad: findings and dispositions

- **Procedure:** `adversarial-squad-deployment`, point-cut **post-spec**.
- **Squad:** two profile-loaded lenses on opus, read-only, against spec revision 1 (`82cfc1ce0c`) and `ecb5dd914a`.
- **reviewer-renata** (acceptance criteria and non-vacuity): verdict **READY-WITH-FOLDS**.
- **paula-patterns** (boundary leaks, ownership, whack-a-field): verdict **READY-WITH-FOLDS**.
- **Operator rulings:** four findings needed an operator decision, recorded as decisions `specify.design.seed-mechanism`, `specify.design.fork-check`, `specify.scope.legacy-ledger` and `specify.scope.planning-commit-refresh`.
- **Outcome:** spec revision 2 applies every disposition below. No finding was dropped.

## reviewer-renata

| # | Severity | Finding (short) | Disposition | Where |
|---|----------|-----------------|-------------|-------|
| R1 | MAJOR | The fork-refusal trigger and the operator's exit are undefined; "diverge" is not defined | accepted, after an operator ruling: the check runs at seed time only, an already-forked materialized Mission is not locked out, and "diverged" means neither event-id sequence is a prefix of the other | US2.4–2.6, FR-004b, Domain Language "Fork" |
| R2 | MAJOR | FR-004 bundles three behaviours; the logical-clock restart is not named; the root copy's fate is unspecified | accepted: the row is split into FR-004 / 004a / 004b; the clock continuation and the root copy's restoration are asserted | FR-004, FR-004a, FR-004b, US2.4–2.5 |
| R3 | MAJOR | FR-005 is a compound fix over two accept legs | accepted: two fixtures, with each leg's fix reverted in turn | FR-005, US3.5–3.6 |
| R4 | MAJOR | "Committed or refused" lets a router that always refuses pass; "skipped" contradicts FR-006 | accepted: commit is the required outcome, refusal is allowed only for named conditions, and "skipped" is forbidden for dirty owning-surface copies | FR-006, US3.1, SC-003, FR-007a |
| R5 | MAJOR | FR-007 is partly passable at base; finalize and retrospect have no scenarios; the finalize porcelain gate is uncovered | accepted: the fixture has one group committed and one skipped, CLI scenarios are added, and FR-007b is new | FR-007, FR-007b, US3.3, US3.8–3.9 |
| R6 | MAJOR | FR-009 has five halves and two of them already hold at base; accept's change is unstated | accepted: split into FR-009 [build] and FR-009a [ratchet]; accept commits the uncommitted ledger, with a committed-ledger positive control | FR-009, FR-009a, US4.7 |
| R7 | MAJOR | There is no commit point for the PRIMARY ledger; the legacy fresh-clone case is unhandled | accepted, after an operator ruling: the existing PRIMARY committers commit it, with no auto-commit; pre-fix Missions are fixed forward via doctor (no read fallback) | FR-009b, FR-009c, US4.5–4.6 |
| R8 | MAJOR | A tip-tree probe is vacuous for #5440 | accepted: a history probe over creation base..target tip; the coordination branch is asserted to carry the creation events | FR-001, US1.1, SC-001 |
| R9 | MAJOR | #5440's headline consolidate conflict is not exercised | accepted: a moved-merge-base variant of the end-to-end test | FR-015, SC-001 |
| R10 | MAJOR | Fixtures miss the production create path; `lanes_with_coord` is absent | accepted: the CLI `--pr-bound --start-branch` path, parametrized over both coordination topologies | US1 (Independent Test), FR-001, FR-015 |
| R11 | MAJOR | FR-003 is compound over writer families × surface states; the COORD kinds are not enumerated | accepted: the writer families are enumerated, with one test per family; each state's behaviour is pinned | FR-003, FR-003a, US2.3, US2.7–2.8 |
| R12 | MAJOR | Seed option (direct ref commit) breaks reads; US1.2 is ambiguous | changed: the operator ruled for eager materialization; US1.2 asserts the classifier state | Assumptions, decision `seed-mechanism`, FR-002, US1.2 |
| R13 | MAJOR | FR-008 is unbounded and contradicts consolidation | accepted: scoped to the router's target-advance seam, with consolidation's projection explicitly excluded | FR-008 |
| R14 | MAJOR | #5023 and #2533 traceability overclaims (the planning_commit_sha facet; #2533's warning symptom; the implement-claim leg) | changed: the operator ruled the planning_commit_sha refresh in scope (FR-012); the #2533 warning repro is added to FR-016; the implement-claim leg is recorded as an assumption to verify in plan | FR-012, US5, FR-016, Assumptions |
| R15 | MAJOR | #5519 (P0) and #5501 have no named red-first reproduction | accepted | FR-016, SC-005 |
| R16 | MAJOR | FR-013 (now FR-014) "concrete floor" has no red-at-base proof | accepted: red at base on real offenders, plus a self-mutation test | FR-014, SC-005 |
| R17 | MINOR | The FR-002 control proves C-008, not FR-002 | accepted: assert through the coordination branch tree and the production read classifier on the same fixture | FR-002 |
| R18 | MINOR | FR-010 covers two commands; refs vs working trees is unstated | accepted: split into FR-010 / FR-010a; detection works from refs and working trees | FR-010, FR-010a, US4.1–4.2 |
| R19 | MINOR | The FR-012 (now FR-013) receipt check is subjective; no positive control | accepted: a commit id per receipt line, plus a target-branch positive control | FR-013, US6 |
| R20 | MINOR | SC-003, SC-004 and NFR-002 cover unbounded sets; "duplicated" is undefined | accepted: commands and fork fixtures are enumerated; duplicates mean the same event id within one log | SC-003, SC-004, NFR-002 |
| R21 | MINOR | The NFR-001 baseline is unmeasurable | accepted: fixture, statistic (median of 5 warm runs), baseline revision, and manual measurement | NFR-001 |
| R22 | MINOR | Label hygiene (FR-015/SC-005 ratchet mixing; FR-016's review-only control) | accepted: FR-016 (red-first) is labelled [build]; FR-017 names the cited ADR sections as its checkable anchor | FR-016, FR-017, SC-005 |
| R23 | MINOR | "Focused homes" for transitional repros is vague | accepted: they move into the owning modules' test files | FR-016 |

## paula-patterns

| # | Severity | Finding (short) | Disposition | Where |
|---|----------|-----------------|-------------|-------|
| P1 | MAJOR | C-001 plus FR-013 force ~10 per-caller patches; no write-dir accessor exists | accepted: C-001 now sanctions one write-location accessor on the existing seam, which owns materialize-and-seed; FR-003 names it; the census sites form the FR-014 floor | C-001, FR-003, FR-014, Domain Language |
| P2 | MAJOR | Accept's raw primary commit is a fifth commit mechanism; its gate and committer disagree | accepted: both legs route through the commit router; the raw commit is removed; gate and committer must agree | FR-005, US3.7, C-001 |
| P3 | MAJOR | Masking lives in the shared result contract; FR-007 names only 4 of about 14 consumers | accepted: per-surface outcomes in the result contract, one shared renderer, all consumers named | FR-007 |
| P4 | MAJOR | Seeding changes the coordination-vs-target relation; the doctor and create would false-flag divergence | accepted | FR-002b, US1.6, Key Entities |
| P5 | MAJOR | A direct ref-commit seed collides with `assert_coord_write_materialized` | changed: the operator ruled for eager materialization, which avoids the collision | Assumptions, decision `seed-mechanism` |
| P6 | MAJOR | Protected-target create is unexercised; create rollback now spans two refs | accepted | FR-002a, US1.4–1.5 |
| P7 | MAJOR | Ledger reclassification flips several readers (residue churn, consolidation dirty gate, bookkeeping projection, write-placement guard) | accepted: the dirty gates treat the ledger as real work; the pre-fix ledger is fixed forward via doctor, and teardown refuses to destroy a coordination-only ledger; the plan enumerates every reader | FR-009, FR-009c, US4.6–4.7 |
| P8 | MAJOR | Seed ordering and atomicity (reduce-before-append, partial seed, leftover root copy, quiet empty state for coord) | accepted | FR-004, FR-004a, FR-003a, Edge Cases, US2.7 |
| P9 | MAJOR | INV-COORD-HOME is silent on the stage-and-copy writers | accepted: direct-to-coordination via the accessor, with transient staging cleaned up in the same command | Edge Cases ("Transient staging"), FR-003 |
| P10 | MAJOR | A new gate would parallel the existing gate family | accepted: extend the existing write-side rederivation gate family | FR-014 |
| P11 | MINOR | `decisions.events.jsonl` (DecisionGitLog) is a second decision-event stream and a home-switch trigger | accepted | Domain Language, FR-003, FR-010 |
| P12 | MINOR | FR-008 wording also catches consolidation advances | accepted: scoped to the router's target-advance seam | FR-008 |
| P13 | MINOR | The seeded directory's contents are unspecified | accepted: COORD-partition records only | FR-002, US1.3 |
| P14 | MINOR | Owned checkouts are not mentioned | accepted | Domain Language, Edge Cases |
