---
work_package_id: WP03
title: '[PR A] P1b Generalised inbound-adapter gates (ArchUnit rules 3, 3b, 1c, 2d, 13, 14)'
dependencies:
- WP02
requirement_refs:
- FR-013
- NFR-005
- C-002
- SC-006
planning_base_branch: issue-957-mission-status-read-api-mission-detail
merge_target_branch: issue-957-mission-status-read-api-mission-detail
branch_strategy: Planning artifacts for this mission were generated on issue-957-mission-status-read-api-mission-detail. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-mission-status-read-api-mission-detail unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-status-read-api-mission-detail-01M4S6D5
base_commit: ed4acdd90df4f2dc14cf053b69abf0538f0a4e8f
created_at: '2026-10-13T20:54:14.822305+00:00'
subtasks:
- T019
- T020
- T021
- T022
- T023
- T024
- T025
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/
create_intent:
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/PortExposesNoLedgerRowTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/adapter/in/other/UsesService.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/config/RogueController.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/config/ProblemErrorController.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/domain/D1cReflect.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/A2dForName.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/ReadsCommand.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/LeakyQuery.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/DtoInRoot.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/out/ExceptionInRoot.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/dto/Value.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/dto/ExceptionInDto.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/exceptions/Refusal.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/exceptions/RecordInExceptions.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/helpers/Stray.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/command/Writer.java
execution_mode: code_change
model: sonnet
owned_files:
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/ArchitectureControlsTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/ArchitectureRulesTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/PortExposesNoLedgerRowTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/adapter/in/other/UsesService.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/config/RogueController.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/config/ProblemErrorController.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/domain/D1cReflect.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/A2dForName.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/ReadsCommand.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/LeakyQuery.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/DtoInRoot.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/out/ExceptionInRoot.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/dto/Value.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/dto/ExceptionInDto.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/exceptions/Refusal.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/exceptions/RecordInExceptions.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/helpers/Stray.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/command/Writer.java
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP03 – [PR A] P1b Generalised inbound-adapter gates (ArchUnit rules 3, 3b, 1c, 2d, 13, 14)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Pull request and dependencies

- **Pull request**: **PR A** (draft; phase tag **P1b**). PR A stacks on the branch carrying #5529's last slice; the operator retargets it to `main` after #5529 lands. No agent pushes, opens or retargets a PR.
- **Depends on**: WP02 (P1a), through the manifest chain WP01 -> WP02 -> WP03. **External dependency (not a `dependencies` entry)**: the #5529 re-cut tip merged into the branch by the orchestrator (paths below are re-cut paths and **exist after the re-cut**; plan section 1.1). If the flat layout is present, stop and report BLOCKED.
- **Dependents**: WP04 (P3a) and, through it, everything functional; WP12 (P8) extends this WP's files with rules 15 and 16 as named edits and takes `DEFINED_RULE_COUNT` from 14 to 16; WP09 (P5) adds one control (`A2cByteBuffer`) to `ArchitectureControlsTest` as a named edit.
- **Write scope**: `owned_files` only, **test-only: no production line and no JaCoCo count**. `application.command` is reserved and is **not created in production**; `Writer` exists in the fixture tree only.
- **Named edits (out-of-map; not in `owned_files`)**. Each: rebase first, state the edit in the commit message, touch nothing else of the file.
  - `T/architecture/ArchitectureRules.java`: rule 3 generalised, rule 3b, rules 1c and 2d, the 1b and 2b exclusion, rules 13 and 14 added, `DEFINED_RULE_COUNT` 12 to 14. **Owned by WP01** (split into one builder per rule in P1; rules 1 to 12 keep their ids).
  - `M/traces/tooling-friction.md`: one append-only entry, **only if** the recorded `java.lang.invoke` fallback of T021 triggers (see the gap noted under "Plan defects found"). Tracer files are never in `owned_files`.

**Path aliases** (repo-relative): `S` = `services/mission-status-api`; `J` = `S/src/main/java/org/speckitty/missionstatus`; `T` = `S/src/test/java/org/speckitty/missionstatus`; `R` = `S/src/test/resources`; `M` = `kitty-specs/mission-status-read-api-mission-detail-01M4S6D5`. Package root `org.speckitty.missionstatus`. Fixture root `FIXTURE_ROOT` = `org.speckitty.missionstatus.architecture.fixture`.

## Objective

Land the architecture gates of operator ruling A3 item 5 and the operator's two layout rules, each shown to bite by a planted violation committed **first**: rule 3 generalised to every `adapter.in.<x>`, rule 3b (controller annotations only in `adapter.in..`), rules 1c and 2d (no reflective class loading in `domain` and `application`), rule 13 (ports are interfaces only; data in `dto/`, exceptions in `exceptions/`), rule 14 (`application.query` never depends on `application.command`), and `PortExposesNoLedgerRowTest`. `DEFINED_RULE_COUNT` goes 12 to 14.

## Context

- Why: after WP02 the inbound port projects, but nothing stops a second adapter from reaching `application.query.MissionStatusQueryService`, a `@RestController` from living outside `adapter.in..`, or a raw ledger row from being re-exposed. These gates are the structural guard that the MCP mission (#6116) will rely on.
- **Rule numbering (plan S-25, D-124, D-130, D-131)**: rules **13 and 14 are the operator's two layout rules** (ports are interfaces only; the query side never depends on the command side). FR-013's controller rule and port-purity rule are rules **15 and 16** and are WP12's; the spec was folded in commit 462bb3c63, so AC-13.1, AC-13.2 and SC-006 now say 15 and 16. This WP covers SC-006 only in its layout half; the controller/port-purity half and the plain-Java caller `PlainCaller` (AC-13.3) land in WP12.
- Arithmetic: 12 existing + 2 (this WP) = 14; 14 + 2 (WP12) = 16. Rule ids 1 to 12 do **not** change: rule 3b is a part of rule 3 (as 1a and 1b are parts of rule 1), rules 1c and 2d are parts of rules 1 and 2, so only the two new numbered rules raise `DEFINED_RULE_COUNT`.
- A nested class is judged by its outermost class (ArchUnit `JavaClass#getTopLevelClass`), so the nested `Kind` enums of `StreamRefused`, `SourceFault` and (later) `TextFault` are judged as the exceptions they sit in (PLAN-FRESH3-005).
- The existing machinery (read it before you edit; **exists in the checkout**): `T/architecture/ArchitectureRules.java` (record `Rule(int id, String name, Scope scope, ArchRule rule, DescribedPredicate<JavaClass> subject)`, `all(root, rule9Packages)`, `production()`, `mainClasses()`, `testClasses()`), `ArchitectureRulesTest` (a `@TestFactory` over `production()`, each rule's `scanned(...) > 0`, the rule-9 literals test, the rule-count guard and `@AfterAll`), `ArchitectureControlsTest` (`SKELETON` list, `CONTROLS` list of `Control(target, planted, redSet)`, `theConformingSkeletonKeepsAll...GreenAndEveryRuleScansAClass`, `everyRuleHasAControl...`). The fixture tree is `T/architecture/fixture/**`; at the re-cut the conforming skeleton (`Service`, `Query`, `Source`) and planted `A2*`, `A6`, `A8`, `A9` classes are re-pathed under `fixture/application/query/**` (mapping row 13).
- Red-first form (plan 11 / 15.6): each planted fixture is committed first and shown **red** against the rule it targets, then the rule is added; against the **old** rule 3, `UsesService` is not reached, which is the defect. Revert rows: 15.6 (reproduced in T025).

### Gate vocabulary

- **Gate G**: `export LC_ALL=C.UTF-8` then `cd services/mission-status-api && ./gradlew --no-daemon test jacocoTestCoverageVerification jacocoScopeCheck`. Never `check` as a phase gate.
- **Gate P**: from the repository root `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q` (stage new files first: the pin's tracked-path scan reads `git ls-files`). Required here because `ArchitectureRulesTest` is rewritten and the pin requires its **three rule-9 literals** (`contract_package_violations`): `...adapter.in.http.api`, `...adapter.in.http.model`, `...adapter.in.http.dto`, in that order, as asserted by `ruleNineCoversTheThreeDtoPackagesAsLiterals`. Do not touch them.
- Targeted loop: `./gradlew --no-daemon test --tests 'org.speckitty.missionstatus.architecture.<Class>'`.
- **E-7 (operator word given)**: local `check`, `nativeCompile nativeTest`, `nativeSmoke` are allowed before review; none is needed for a test-only WP. CI is the authority.

---

### Subtask T019: Commit each planted fixture first and show it red against its rule

**Purpose**: red-first discipline (C-011, charter test-remediation). A control that was never red proves nothing.

**Steps**:
1. Create the planted fixtures (all under `T/architecture/fixture/**`, package names mirror the path under `FIXTURE_ROOT`; each is a few lines, compiles, and does nothing at run time). One concern per fixture, exact paths from `owned_files`:
   - `adapter/in/other/UsesService` (`FIXTURE_ROOT.adapter.in.other`): a class that depends on the skeleton's `application.query.Service` (a sibling adapter reaching the service). Target: rule 3.
   - `config/RogueController`: annotated `@RestController`, residing in `config`. Target: rule 3b (part of rule 3).
   - `config/ProblemErrorController`: the **conforming** allow-listed member (a `@RestController` in `config`, mirroring `config.ProblemErrorController`); must stay green.
   - `domain/D1cReflect`: calls `Class.forName("java.nio.file.Files")` **and** holds a field of type `java.lang.reflect.Method`. Targets: rule 1 (1b and 1c).
   - `application/query/A2dForName`: calls `Class.forName(...)`. Target: rule 2 (2d).
   - `application/query/ReadsCommand`: depends on `FIXTURE_ROOT.application.command.Writer`. Target: rule 14.
   - `application/command/Writer`: the fixture-only target class (**never** a production package of that name).
   - `application/query/port/in/LeakyQuery`: an interface with a method returning the real `org.speckitty.missionstatus.domain.model.LineKind`. Target: `PortExposesNoLedgerRowTest`.
   - `application/query/port/in/DtoInRoot`: a **record** directly in a `port.in` root. Target: rule 13(a).
   - `application/query/port/out/ExceptionInRoot`: an exception class directly in a `port.out` root. Target: rule 13(a).
   - `application/query/port/in/dto/ExceptionInDto`: a `Throwable` in a `dto/` package. Target: rule 13(b).
   - `application/query/port/in/exceptions/RecordInExceptions`: a record in an `exceptions/` package. Target: rule 13(c).
   - `application/query/port/in/helpers/Stray`: a class in an unlisted `port..` subpackage. Target: rule 13(d).
   - Conforming members (must stay green): `application/query/port/in/dto/Value` (a record) and `application/query/port/in/exceptions/Refusal` (an exception holding a **nested enum `Kind`**, which exercises the outermost-class judgement that the production `StreamRefused.Kind` and `SourceFault.Kind` rely on).
2. Show each red **before** the rule exists. Procedure (scratch copy, never by editing the tree under review): for each planted class run the old `ArchitectureRules.all(...)` over `SKELETON + planted` and record the red set. Expected on the old rules: `UsesService` is **not reached** by rule 3 (this is the defect; record it), `RogueController` is not reached, `D1cReflect`/`A2dForName` are green under the old 1b/2b (`java.lang..` allows reflect), rules 13 and 14 do not exist. Put the observed table in the commit message of the fixtures commit: `test(campsite): plant the generalised-gate fixtures, red against the old rules`.
3. The fixtures commit is allowed to leave `ArchitectureControlsTest` unchanged and green (the fixtures are not yet in `CONTROLS`).

**Files**: the 15 fixture files above (~10 to 25 lines each), new.

**Validation**: the red table in the commit message names, for each planted fixture, the old-rule behaviour; the whole existing `ArchitectureRulesTest`/`ArchitectureControlsTest` still pass unchanged at this commit.

---

### Subtask T020: Rule 3 generalised to every adapter.in.<x>; rule 3b controllers confined to adapter.in..

**Purpose**: item 5 of the ruling. A second inbound adapter (`adapter.in.mcp`) must be bound by the same dependency law as `adapter.in.http`, and no controller annotation may escape `adapter.in..`.

**Steps** (named edit of `ArchitectureRules.java`, WP01's file; rebase first):
1. **Rule 3 text**: "every `adapter.in.<x>` depends, among project packages, only on `application.query.port.in`, `domain` and itself". Implement as a custom `ArchCondition<JavaClass>` over `adapter.in..`: for each class compute its adapter segment (the first package segment below `adapter.in`); every dependency on a project class (package starts with the root) must be in `application.query.port.in..`, `domain..`, or the **same** `adapter.in.<x>..`; a dependency on a sibling `adapter.in.<y>..` is a violation. Keep the existing `H3aInternal` and `H3bConfig` controls working (they remain in `CONTROLS`: H3a red on {3}, H3b red on {3, 6}).
2. **Pin the discovered set** of `adapter.in.<x>` packages in `ArchitectureRulesTest` (production run only, not in the rule, because the fixture root legitimately holds `adapter.in.other`): compute the set of segments over the production import and assert it equals `{http}` with a non-zero scanned count per entry, so the first MCP adapter forces its own entry and its own count.
3. **Rule 3b** (a part of rule 3, same id): a class annotated `@RestController`, `@Controller`, `@RestControllerAdvice` or `@ControllerAdvice` resides in `adapter.in..`, **except `config.ProblemErrorController`**, allow-listed by fully qualified name (`p(root, "config.ProblemErrorController")`, so the fixture root evaluates the same predicate). Floor in production: **5** annotated classes (`ProjectController`, `MissionsController`, `EventsController`, `ContractDocumentController`, `ProblemAdvice`) plus the allow-listed one.
4. **Stale-entry guard**: the allow-listed class must exist in the import, or the test is red (an entry that no longer matches anything is a rotting exception). The allow-list entry is a **permanent structural exception, not transient debt** (Standing Order 5): the container dispatches an error to `/error`, outside the `/api/v1` prefix that applies to `adapter.in.http`, so the error controller cannot live there without changing the path. No expiry; say so in the Javadoc.
5. Controls added to `ArchitectureControlsTest`: `new Control(3, UsesService.class, Set.of(3))` and `new Control(3, RogueController.class, Set.of(3))`; skeleton adds `ProblemErrorController` (conforming, green). Determine each exact red set empirically on the run and **reason about every co-red** before pinning it; the plan's expectation is "red on rule 3 only" for both.

**Files**: `ArchitectureRules.java` (named edit, ~+70 lines), `ArchitectureRulesTest.java` (discovered-set pin, ~+30), `ArchitectureControlsTest.java` (controls).

**Validation**: `--tests '*ArchitectureRulesTest' --tests '*ArchitectureControlsTest'`: the production run scans >= 5 annotated classes plus the allow-listed one; `UsesService` and `RogueController` turn exactly rule 3 red; `H3a`/`H3b` unchanged.

---

### Subtask T021: Rules 1c and 2d (no reflective class loading); 1b and 2b lose java.lang.reflect.. and java.lang.invoke..

**Purpose**: the finding's example, `Class.forName("java.nio.file.Files")`, is a hole that a package exclusion alone leaves open because `java.lang.Class` stays allowed (D-124). Close it in two parts.

**Steps** (named edit of `ArchitectureRules.java`):
1. **Rules 1c and 2d** (parts of rules 1 and 2): `domain..` and `application..` do not call `Class.forName`, `ClassLoader.loadClass`, or `Class.getMethod`/`getMethods`/`getConstructor`/`getConstructors`/`getField`/`getFields`/`getDeclared*` (a `callMethodWhere` predicate on the target owner and name). Subject: `domain..` and `application..` respectively (non-zero scanned counts already asserted by rules 1 and 2).
2. **Rules 1b and 2b**: remove `java.lang.reflect..` and `java.lang.invoke..` from what `java.lang..` allows: replace the subpackage-inclusive `"java.lang.."` by the exact package `"java.lang"` in the allow lists of 1b and 2b. The main sources import neither today (verified by grep: `grep -rn "java.lang.reflect\|java.lang.invoke\|Class.forName" services/mission-status-api/src/main` is empty at the checkout).
3. **Recorded fallback (Unverified 16; there is no JDK on the planning host)**: if ArchUnit reports the `invokedynamic` bootstrap references of records, lambdas or string concatenation (`java.lang.invoke.MethodHandles$Lookup`, `StringConcatFactory`) as dependencies of conforming domain or application classes, rules 1b and 2b go red on the **production tree**. Then narrow the exclusion to `java.lang.reflect..` only and ban calls to `MethodHandles` factory methods instead, and record the observation in `M/traces/tooling-friction.md` as one append-only dated entry (`- **[YYYY-MM-DD][P1b] Short symptom.** 1-3 sentences; disposition.`) naming which classes triggered it. State the outcome (kept, or fell back) in the commit message either way.
4. Controls: `D1cReflect` (rule 1 red: the `Class.forName` call is 1c, the `java.lang.reflect.Method` field is 1b) and `A2dForName` (rule 2 red). Pin the exact red sets after reasoning about co-reds (for example `D1cReflect` may also turn another rule red if it imports a file API; keep the fixture minimal so the plan's "red on rule 1" / "red on rule 2" holds).

**Files**: `ArchitectureRules.java` (named edit, ~+45), `ArchitectureControlsTest.java` (controls), `M/traces/tooling-friction.md` (append only on fallback).

**Validation**: production run green under 1b/2b/1c/2d; `D1cReflect` and `A2dForName` red as pinned; the skeleton stays green.

---

### Subtask T022: Rule 13 (ports are interfaces only)

**Purpose**: the operator's layout rule (2026-10-13, D-130, D-131): the port packages hold only interfaces; every data type a port defines lives in `dto/`, every contract exception in `exceptions/`.

**Steps** (named edit of `ArchitectureRules.java`; id **13**; name "ports are interfaces only"):
1. Over `application.query.port..`, each class judged by its **outermost class** (`JavaClass#getTopLevelClass`):
   - (a) a class residing **directly** in `port.in` or `port.out` has an interface as its outermost class;
   - (b) a class in `port.in.dto` or `port.out.dto` has an outermost class that is **not** a `Throwable`;
   - (c) a class in `port.in.exceptions` or `port.out.exceptions` has an outermost class that **is** a `Throwable`;
   - (d) every class of `port..` resides in one of `port.in`, `port.out` and the four `dto`/`exceptions` subpackages (no other subpackage).
2. Subject for the non-zero scanned count: `application.query.port..`. The production run asserts a non-zero count for **each of the two roots and the four subpackages** (a test in `ArchitectureRulesTest` over the production import; the roots hold `MissionStatusQuery`, `Subscription`, `MissionEventSource`; the subpackages hold `StreamEvent`/`MissionRef`, `StreamRefused`/`SourceFault` and the rest; if one is empty at this tip, report it, do not invent a class).
3. Controls (each red on rule 13 **only**; pin that): `DtoInRoot` (a), `ExceptionInRoot` (a), `ExceptionInDto` (b), `RecordInExceptions` (c), `Stray` (d). Skeleton gains `Value` (`port.in.dto`) and `Refusal` with nested `Kind` (`port.in.exceptions`); the existing skeleton `Query` and `Source` are re-pathed under `fixture/application/query/port/{in,out}` by the re-cut (mapping row 13) and are the conforming interface members.

**Files**: `ArchitectureRules.java` (named edit, ~+60), `ArchitectureControlsTest.java` (5 controls, skeleton), `ArchitectureRulesTest.java` (six non-zero counts).

**Validation**: production green; each planted class red on 13 only; `Refusal` (nested enum) green, which proves the outermost-class judgement.

---

### Subtask T023: Rule 14 (query side never depends on the command side)

**Purpose**: keep the read side clean before a write module exists (D-131).

**Steps**:
1. Rule 14 (id **14**): no class of `application.query..` depends on a class of `application.command..`. Subject: `application.query..`; non-zero in production. The target package does **not** exist in production by design; the rule keeps it from being reached, and the planted control is what shows it bites.
2. Control: `ReadsCommand` (fixture `application.query`) depends on `FIXTURE_ROOT.application.command.Writer` (the fixture tree only): red on rule 14 only. The skeleton's `fixture.application.query.Service` is the conforming scanned member.
3. Do **not** create any `application.command` directory, package, class or placeholder in `S/src/main` (plan 1.1: "NOT created by this mission: no class, no package, no directory, no empty placeholder"). `Writer` lives under `T/architecture/fixture/application/command/` only.

**Files**: `ArchitectureRules.java` (named edit, ~+20), `ArchitectureControlsTest.java` (control).

**Validation**: `ReadsCommand` turns rule 14 red only; `git ls-files S/src/main | grep -c 'application/command'` prints `0`.

---

### Subtask T024: PortExposesNoLedgerRowTest; DEFINED_RULE_COUNT 12 to 14; exact red sets; skeleton stays green

**Purpose**: prove the port exposes no raw ledger row (ruling item 1, enforced for types), and close the count/controls bookkeeping.

**Steps**:
1. `T/architecture/PortExposesNoLedgerRowTest.java`: over `application.query.port.in..` (the production import), no class depends on `domain.model.LineKind`, `StatusEvent`, `LifecycleEvent` or `LedgerLine`. Floor: the scanned count is at least the class count of `application.query.port.in..` that you read off the tip (assert `isGreaterThanOrEqualTo(<n>)` with the number you measured, and state it in the commit; never an equality, so later phases can add port classes). A planted control: import `LeakyQuery` (method returning `LineKind`) on its own and require the predicate to report a violation, so the test is not vacuous.
2. `ArchitectureRules.DEFINED_RULE_COUNT` 12 to **14** (named edit). Re-title the tests that say "twelve" (`theRuleSetDefinesTheTwelveRulesOfThePlanTableWithContiguousIds`, `theConformingSkeletonKeepsAllTwelveRulesGreen...`, `everyRuleHasAControlAndRulesOneTwoThreeAndTwelveHaveASecond`) to count-neutral names; they compare with `DEFINED_RULE_COUNT`, so only the names change. The test that checks each rule has a control requires one for every id 1 to 14.
3. `ArchitectureControlsTest` pins the **exact red set of every control, including the new ones**: `Control(13, DtoInRoot.class, Set.of(13))`, `ExceptionInRoot`, `ExceptionInDto`, `RecordInExceptions`, `Stray` each `Set.of(13)`; `Control(14, ReadsCommand.class, Set.of(14))`; `Control(3, UsesService.class, Set.of(3))`; `Control(3, RogueController.class, Set.of(3))`; `D1cReflect` `Set.of(1)`; `A2dForName` `Set.of(2)`. Each set is what the run prints, reasoned about (a co-red that the plan did not predict is investigated, not copied).
4. Skeleton: add `Value`, `Refusal`, `ProblemErrorController`; keep `theConformingSkeleton...` green (every rule scans at least one skeleton class and none is red). Rule 13 and 14 each scan a skeleton class (`Query`/`Source`/`Value`/`Refusal` and `Service`).
5. The existing Windows-filename concern: all fixture file names are plain ASCII Java names.

**Files**: `PortExposesNoLedgerRowTest.java` (new, ~90), `ArchitectureRules.java` (count), `ArchitectureControlsTest.java`, `ArchitectureRulesTest.java`.

**Validation**: `--tests '*ArchitectureControlsTest' --tests '*ArchitectureRulesTest' --tests '*PortExposesNoLedgerRowTest'` green; `ArchitectureRulesTest` reports 14 rules each non-vacuous.

---

### Subtask T025: Gate

**Purpose**: exit evidence.

**Steps**:
1. **Gate G** (`LC_ALL=C.UTF-8`), whole.
2. `ArchitectureControlsTest` (every control pins its exact red set), `ArchitectureRulesTest` (14 rules, each scans a non-zero class count; the discovered adapter set equals `{http}`), `PortExposesNoLedgerRowTest`.
3. **Gate P** (stage new files first), because `ArchitectureRulesTest` is rewritten and the pin requires its three rule-9 literals.
4. **Revert rows to run once in a scratch copy of the tree** (record the commands and results in the hand-off; never by editing the working tree under review): restore the old subject of rule 3 (`adapter.in.http..` only) and `UsesService` stops turning red, so the controls test fails the build; delete the allow-list entry and the production run is red on `ProblemErrorController`; add a `@RestController` to `config` and rule 3b is red; put a record in a port root, an exception in a `dto/` package, a record in an `exceptions/` package or a class in another `port..` subpackage and rule 13 is red; make `application.query` reach `application.command` and rule 14 is red.
5. Confirm test-only: `git diff <WP base>..HEAD --stat -- services/mission-status-api/src/main` is empty and `R/jacoco-class-floor.properties` is unchanged.
6. Hygiene: Windows-filename guard after staging; no home path or username in any file.

**Validation**: all of the above recorded with commands and counts.

---

## Self-contained green

- **Fixtures live with their tests (plan 11)**: all 15 fixtures are read only by `ArchitectureControlsTest`/`PortExposesNoLedgerRowTest` and sit under `T/architecture/fixture/**`. Nothing outside the `architecture` test package reads them. `Writer` exists only in the fixture tree.
- **Floors and counts satisfiable now**: `DEFINED_RULE_COUNT` = 14 here (16 at WP12); rule 3b production floor 5 + the allow-listed `config.ProblemErrorController` (all six exist: plan 15.4); the discovered adapter set `{http}`; rule 13 non-zero for the two roots and four subpackages (satisfied by the #5529 re-cut tree plus WP02's `StreamEvent`/`StreamCapacityReached`); `PortExposesNoLedgerRowTest` floor = the count measured at this tip. **No JaCoCo count** changes (test-only, no production line).
- **No test or gate names a type of a later WP**: nothing names `MissionDetailQuery`, `DetailController`, `R15Controller`, `R16*`, `StreamSpring`, `TextSource`, `A2cByteBuffer` or any `domain.readmodel.detail` record. Those are WP12/WP09 additions to these same files (named edits there).
- **Pin clauses kept green**: the three rule-9 literals of `ArchitectureRulesTest` (Gate P); the tracked-path scan (stage new files first); the `out`-probe list was fixed in WP01; the `EventsController` needles are untouched (WP02).
- **Mission record**: no `meta.json`, `status.events.jsonl` or `status.json` edit; `status.json` is only produced by `spec-kitty agent status materialize --mission <slug>`, never by hand, so cutover-guard, the mission-state audit and corpus-blocking see a complete record. Any tracer append is append-only; no untracked CLI state is committed blind.
- **Production tree is green under the new rules at the tip**: rule 3 generalised must not newly redden the real `adapter.in.http` classes; at the checkout their project imports are only `application.port.in` (re-cut: `application.query.port.in`), `domain.*` and `adapter.in.http.*`, so they conform. If any production class turns a new rule red, that is a finding for the orchestrator (a production fix would break this WP's test-only contract), not something to fix here.

## Plan defects found

- **Resolved**: the 1b/2b `java.lang.invoke` fallback of T021 requires an append to `M/traces/tooling-friction.md` (plan 15.4: "records the observation in `traces/tooling-friction.md`"), and the wps.yaml header now lists that append among WP03's named edits (TASKS-COVER-010 c; tracer files are append-only and "every phase appends", plan 11 table).
- **Spec numbering**: folded in commit 462bb3c63 (AC-13.1, AC-13.2 and SC-006 say rules 15 and 16; the layout rules 13 and 14 are this WP's). WP03 satisfies SC-006 only in part; the rest is WP12.
- **`ArchitectureRulesTest` literal**: the existing test asserts `MAIN.contain("...application.MissionStatusService")`; after the re-cut #5529 re-points it. If the re-cut left a stale name, `theMainImportHoldsNoTestClass...` passes vacuously on its `isFalse` leg; verify the strings with the C-005 grep (`grep -rnE '"org\.speckitty\.missionstatus\.(application|domain)' services/mission-status-api/src/test`) and report a stale one to the orchestrator.
- No forward reference or unsatisfiable floor found for this WP.

## Definition of Done

- [ ] Each of T019 to T025 has a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- [ ] Fixtures committed first, each shown red (or not reached, for `UsesService`) against the old rules; the red table is in the commit message.
- [ ] Rules 3 (generalised), 3b (allow-list by FQN with stale-entry guard), 1c, 2d, 13, 14 exist; 1b/2b lose `java.lang.reflect..` and `java.lang.invoke..` (or the recorded fallback is applied and recorded).
- [ ] `DEFINED_RULE_COUNT` = 14; `ArchitectureControlsTest` pins the exact red set of every control, new ones included; the skeleton stays green; every rule scans a skeleton class.
- [ ] The discovered adapter set is pinned to `{http}` with non-zero counts; rule 3b production floor 5 + the allow-listed class.
- [ ] `PortExposesNoLedgerRowTest` green on production, red on `LeakyQuery`.
- [ ] No production line changed, no `application.command` in `S/src/main`, no JaCoCo count change.
- [ ] Gate G and Gate P green; revert rows run once in a scratch copy with results recorded.

## Risks

- **A production class turns a new rule red** (for example a controller outside `adapter.in..`, or a reflective call): report it; do not "fix" production in a test-only WP.
- **`java.lang.invoke` bootstrap references** make 1b/2b red on the production tree: apply the recorded fallback and record it.
- **Over-pinned red sets**: a co-red copied without reasoning hides a real defect; reason about each.
- **Vacuous guard**: the Windows-filename guard and the pin read `git ls-files`; stage first. A control that was never red proves nothing: show every planted fixture red before the rule change.
- **Concurrent edits**: WP09 (control) and WP12 (rules 15/16) edit these files later; keep the `SKELETON`/`CONTROLS` lists and `DEFINED_RULE_COUNT` handling simple to rebase (one entry per line, no reflowing of existing entries).

## Reviewer Guidance

- Check the red-first evidence: the fixtures commit precedes the rule commits; `UsesService` is shown **not reached** by the old rule 3.
- Verify each control's pinned red set by running it; any co-red must be explained in a comment.
- Verify rule 3b is by fully qualified name, has the stale-entry guard and no expiry, and that the production floor is 5 plus the allow-listed class.
- Verify rule 13's outermost-class judgement via `Refusal.Kind`, rule 14's production non-zero count, and that no `application.command` exists in `S/src/main`.
- Verify rule ids 1 to 12 are unchanged and `DEFINED_RULE_COUNT` is 14 (not 16).
- Run the revert rows of T025 in a scratch copy and compare.
- Verify Gate P was run and the three rule-9 literals are intact.

## Implementation command

```bash
spec-kitty agent action implement WP03 --agent claude --mission mission-status-read-api-mission-detail-01M4S6D5
```
