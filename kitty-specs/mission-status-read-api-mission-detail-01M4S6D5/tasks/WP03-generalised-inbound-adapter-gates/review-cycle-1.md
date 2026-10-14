---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-mission-detail-01M4S6D5
reproduction_command:
reviewed_at: '2026-10-13T22:08:46Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review feedback (cycle 1) - REJECT

Reviewed at lane tip 2a81929e0. Mutation method: scratch worktree at that sha, one mutation of ArchitectureRules.java at a time, then run ArchitectureControlsTest + ArchitectureRulesTest + PortExposesNoLedgerRowTest. 13 of 17 mutations were caught. Four survived (F1 to F4).

## F1 (severity 4) Rules 1b and 2b: the java.lang.reflect / java.lang.invoke exclusion is untested
- Where: ArchitectureRules.java rule1 (r1b) and rule2 (r2b), the exact "java.lang" entry; controls in ArchitectureControlsTest.
- Scenario: revert "java.lang" to "java.lang.." in either rule. Result: 60 tests, 0 failures (mutations m4 and m5). The 2b exclusion has no control at all. For 1b, D1cReflect sits in rule 1 together with its Class.forName call, so rule 1 is red from 1c alone.
- Remedy: one fixture per part. D1cReflect keeps only the java.lang.reflect.Method field (1b). Add a domain fixture holding only the Class.forName call (1c), and an application fixture with a reflect-typed field (2b). Each is red for its own part only; confirm by running the mutation again. The new fixtures are not in owned_files: the orchestrator must add them to the WP scope (this is the amendment).

## F2 (severity 4) Rule 1c has no control of its own
- Where: ArchitectureRules.java rule1 (r1c).
- Scenario: replace the 1c predicate by alwaysFalse. Result: all green (m6), because D1cReflect's Method field already turns rule 1 red through 1b. Same remedy as F1: a domain fixture with only the Class.forName call. Note A2dForName does catch the 2d mutation (m7).

## F3 (severity 3) Rule 3: the sibling-adapter clause has no control
- Where: onlyReachPortDomainAndOwnAdapter; UsesService.
- Scenario: set own = "adapter.in" (any adapter.in.<y> allowed). Result: all green (m14). UsesService reaches application.query.Service, which is forbidden whatever the sibling clause says. The WP prompt T020 step 1 names "a dependency on a sibling adapter.in.<y>.. is a violation" as the rule's text.
- Remedy: a planted class in adapter.in.other that depends on a class of the fixture adapter.in.http (the skeleton's Controller). Pin its red set (expected {3}, reason about co-reds). Needs a new fixture file, same scope amendment.

## F4 (severity 2) PortExposesNoLedgerRowTest: three of four banned types are unpinned
- Where: PortExposesNoLedgerRowTest, LeakyQuery.
- Scenario: shrink belongToAnyOf(LineKind, StatusEvent, LifecycleEvent, LedgerLine) to LineKind. Result: green. LeakyQuery uses LineKind only.
- Remedy: make LeakyQuery (or a sibling fixture) return or take one of each banned type, or assert one violation per banned type.

## Notes, not blocking
- N1 (severity 1) Refusal.Kind never reaches the controls: ClassFileImporter.importClasses(Refusal.class) does not import the nested enum, so the outermost-class judgement is exercised only by production (StreamRefused.Kind). Removing outermost() fails only the production run (m12). Import Refusal$Kind in SKELETON too if you want the control to prove it.
- N2 (severity 1) P13aInClass, P13bOutClass, P14UsesCommand and Cmd are redundant with DtoInRoot, ExceptionInRoot, ReadsCommand and Writer (same rule, same shape; every rule-13 and rule-14 mutation was caught by both). Judged harmless; delete them in the same fix commit if the scope amendment allows, else keep.
- N3 The prompt says DEFINED_RULE_COUNT 12 to 14; the base already held 14 (rules 13 and 14 pre-existed from the re-cut), so the WP leaves it at 14 and says so in the commit. Spec (AC-13.1, AC-13.2, SC-006: rules 15 and 16 are WP12's) and code agree. No finding.

## Verified fine
- Test-only: no diff over src/main, no jacoco-class-floor change, no application.command file in src/main.
- Rule 3b stale-entry guard works (allow-list renamed: ruleThreeBSeesTheFiveAnnotatedControllersAndTheAllowListedOneStillExists and rule 3 both red). Rule 3b controls (m3), rule 3 subject (m1), 2d (m7), 13a/b/c/d (m8 to m11), 14 (m13) all bite.
- Production scan counts, all non-zero: rule 1 56, 2 69, 3 34, 13 32, 14 69. Every rule scans more than zero classes.
- Gates (unchanged tree): clean check green, 2478 tests, 0 failures; nativeCompile, nativeTest and nativeSmoke green, digest 15b1eb6ae389c4752ff3577e32e226730f31f610b61fdee4a9d169073bf2e979; pytest 311 passed; ruff check and format green.
