---
work_package_id: WP18
title: 'Phase 2a-4: ArchUnit rule set, port-level conformance suite, interim id check and 2a exit gate'
dependencies:
- WP06
requirement_refs:
- FR-012
- FR-013
- C-003
- NFR-006
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
subtasks:
- T033
- T034
- T035
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/test/
create_intent:
- services/mission-status-api/src/test/resources/portlevel-tests.txt
- services/mission-status-api/src/test/resources/jacoco-class-floor.properties
execution_mode: code_change
model: ''
owned_files:
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/port/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/**
- services/mission-status-api/src/test/resources/portlevel-tests.txt
- services/mission-status-api/src/test/resources/jacoco-class-floor.properties
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP18 - Phase 2a-4: ArchUnit rule set, port-level suite and 2a exit gate

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Write the ArchUnit rule set with one positive control per rule, the committed `portlevel-tests.txt` id list with its interim-ids machinery, and the port-level conformance suite running against the in-memory source over hand-built fixtures through the single `PortSourceSelector`; verify the JaCoCo floor against the real report and close phase 2a.

## Context

- Plan phase 2a, last part (plan.md section 11 row 2a and "Parallelism and the honest dependency of 2a on 2b", section 13 ArchUnit rule table and rules 11 and 13). Spec FR-012 (AC-12a/b), FR-013 (AC-13a/b), C-003, NFR-006.
- Depends on WP06 (the application layer, in-memory source, `FixtureSpec`, `FixtureFactory`, `PortSourceSelector`). Concurrent with WP07 (Python oracle): this WP cannot use WP07's goldens; the AC-2a members of the port-level subset (five fixture classes against goldens) are NOT run at this WP's gate. FR-013's id floor and the full AC-13a equality are first met at WP09's gate, not here.
- The adapter side (filesystem) is WP08/WP19 and the HTTP side WP10/WP20; the ArchUnit rules written here guard those packages from their first commit, which is why WP08 depends on this WP.
- Cross-WP appends: the tracer files are appended (append-only, own commit; they are in no WP's `owned_files`); public repo hygiene.
- **Toolchain precondition (first step, before any other work).** Run `java -version` and `./gradlew --version` (from `services/mission-status-api/`) and compare them with the versions the orchestrator recorded in `research.md` (GraalVM Community 25.0.2, Gradle 9.7.1). `JAVA_HOME` and `PATH` for the persistent, orchestrator-provisioned install come from this brief (`tasks-overview.md` section 10). If either command is missing or reports another version: STOP and report BLOCKED (owner: orchestrator/operator, who install or repair the toolchain). Do not substitute another JDK, do not install one yourself, and do not skip a gate this WP lists as local: "CI is the proof" is not an alternative for a local Gradle gate.

## Subtask T033: ArchUnit rule set (12 rules, positive controls, non-vacuity)

**Purpose**: FR-012 / AC-12a/b / AC-13b / C-003.

**Steps**:
1. `architecture/ArchitectureRulesTest` implementing plan.md section 13 rules 1-12 as written, with the one rule 11 reading recorded in `tasks-overview.md` section 9 item 15 (production rules import main classes only: `ImportOption.DoNotIncludeTests`, generated classes included; rule 11 imports test classes; rule 11 treats test classes that live in the `adapter.out.filesystem` package itself, such as `RecordingAllowlistAccess` (WP08 T044 step 2, `src/test`), as in-package, not as importers). Pay attention to the scoping text: rules 3 and 4 constrain only dependencies among project packages; rule 1 allows `java.security`, `java.time`, `java.nio.charset`, `java.util` except `java.util.concurrent`; rule 2 forbids thread creation (`Executors.*`, `Thread.ofVirtual/ofPlatform`, `new Thread`, `ThreadPoolExecutor`, `ForkJoinPool`); rule 7 excludes the `codec` sub-package; rule 12 binds the codec and is satisfied because the codec returns `domain.model` types (`LedgerLine`, its kind, reason and tail classification, declared by WP05) and declares none of its own.
2. Positive controls: ONE mutation per rule that turns exactly that rule red, implemented as scratch compilation units under `src/test` that are excluded from the production import, or as an ArchUnit evaluation over a deliberately violating class set built in the test. The mutation list is the right-hand column of the plan's table (second controls for rules 1, 2, 3, 12).
3. Non-vacuity in three parts: each rule scans more than zero classes (AC-12b), each rule has its control, and a rule-count guard fails when the number of rules run differs from the number defined (revert: delete one rule and the guard is red).
4. Rule 9's package list is pinned as LITERALS in the ArchUnit test, not read from `build.gradle.kts` (hand mode has no `apiPackage`/`modelPackage` there): `org.speckitty.missionstatus.adapter.in.http.api`, `org.speckitty.missionstatus.adapter.in.http.model` AND `org.speckitty.missionstatus.adapter.in.http.dto` (generated mode fills the first two, hand mode the third; the rule covers all three whichever is populated). Rule 9 is therefore checkable before the generated-versus-hand decision is applied; it must pass vacuously-but-guarded until WP10 adds classes (the sanity count for rule 9 uses the fixed package list, not a class count > 0, and says so). A separate WP10 build pin ties these literals to the mode recorded by WP03.
5. The rule 13b scan (`..conformance.port..` classes equal the classes named by the id list) is part of T034.

**Files**: `architecture/*` (~500 lines).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.architecture.*'`.

## Subtask T034: `portlevel-tests.txt`, the port-level suite and the interim id check

**Purpose**: FR-013 / AC-13a/13b.

**Steps**:
0. Interim machinery (moved here from WP06 because it needs `portlevel-tests.txt`; all of it lives under `testsupport/**`, which WP09 owns, so WP09 never edits `conformance/port/**`): `testsupport.INTERIM_GOLDEN_DEPENDENT_IDS`, the constant listing exactly the AC-2a members that need WP07's data; the interim id check ("executed ids = file ids minus that constant", plus "no listed test is skipped" except those); and the guard test asserting every member of the constant is an AC-2a id of `portlevel-tests.txt` (revert: add a non-AC-2a id to the constant and the guard is red). WP09 deletes the constant, the check and the guard and adds a reflection test asserting the constant is gone.
1. Write the COMPLETE `portlevel-tests.txt` now (one test id per line, floor recorded in FR-013): AC-2a restricted to classes `interleaved`, `lifecycle-only`, `no-ledger`, `log-truncated`, `crlf-and-listing`; AC-2b; AC-5a; AC-5c; the port legs of AC-3g and AC-3i; the port legs of AC-4a for L1, L3a, L3b, L4, L4b. The id grammar is yours to fix and document in a header comment line; the Java launcher in WP09 parses it.
2. Implement the non-golden members as classes in `..conformance.port..` written against `MissionStatusQuery` only. EVERY port-level class obtains its `MissionStatusQuery` from `testsupport.PortSourceSelector` (WP06 T032 step 3) over a source-neutral `FixtureSpec` built by hand; none constructs a factory or names a source. The selector defaults to the in-memory source; WP09 flips it to `FilesystemFixtureFactory` for the second leg by editing `testsupport/**` only. AC-2b: paging with page size 1 through N Missions yields each once in contract order, including two Missions with equal `createdAt`.
3. The AC-2a members get their class shells here (so ids exist and the file is complete) and are skipped-by-constant now (step 0). A shell contains NO assertion logic of its own: it calls a `testsupport` hook (`testsupport.Ac2aGoldenHook`, a stub declared here that reports "not yet backed by goldens") with its fixture-class name and the selector's `MissionStatusQuery`; WP09 implements the hook over the committed fixture trees and goldens, inside `testsupport/**`, so the shells never need completion in `conformance/port/**`. Document that WP09 runs them on both sources.
4. ArchUnit rule 13b control: add an adapter import to a subset class in a test branch => red; sanity: the scanned class set is non-empty and equals the classes named by the id list.
5. Record the id count; the file must hold at least the ids FR-013 names (a recorded floor).

**Files**: `conformance/port/*` (~700 lines), `testsupport` additions (interim constant, hook stub, ~80 lines), `portlevel-tests.txt` (~40 lines).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.conformance.port.*' --tests 'org.speckitty.missionstatus.testsupport.*'`.

## Subtask T035: JaCoCo floor verification and the 2a exit gate

**Purpose**: Close phase 2a: the floor file (created by WP05, raised by WP17, completed by WP06) matches the real report and everything is green together.

**Steps**:
1. Re-derive the class counts from the real `jacocoTestReport` XML for `org.speckitty.missionstatus.domain.*` and `application.*` and require `jacoco-class-floor.properties` to hold exactly those lines (a count above the file means an earlier WP forgot to raise it: raise it here as a one-line amendment in its own commit; the file is created by WP05, raised by WP17 and WP06, and this WP owns it for this one-line raise; it is never lowered). Prove the guard once more in a scratch copy: empty one include pattern and `./gradlew check` goes red; restore.
2. `cd services/mission-status-api && ./gradlew check` green with the JaCoCo rule (line >= 90% on domain and application, branch >= 80% on domain), ArchUnit, the port-level subset (minus the interim constant).
3. A red JaCoCo rule is fixed with tests; no threshold is ever lowered and "check green" has no shortfall alternative.
4. Append tracer entries (design decisions: any seam detail not in data-model.md, e.g. the id grammar and the selector; friction).

**Validation**: all green; the PR "Tests run" note lists the Gradle tasks and the revert-fails observations.

## Definition of Done

- The ArchUnit rule set (12 rules, one control each, non-vacuity, literal rule-9 packages), `portlevel-tests.txt` (complete), the port-level classes, the interim machinery under `testsupport/**` and its guard exist, each test-first with its revert-fails mutation observed red.
- `cd services/mission-status-api && ./gradlew check` is GREEN at this tip; the floor file equals the real report.
- The FR-013 floor and the AC-13a equality are explicitly NOT claimed yet (WP09).
- Native legs stay green at this tip (nothing here touches the hello route).

## Risks

- Size: ArchUnit (about 500 lines) plus the port-level suite (about 700); if it overruns, the seam is T033 versus T034, both inside this WP's owned trees.
- A shell with assertion logic of its own would force WP09 into `conformance/port/**`: reviewers reject it.

## Reviewer Guidance

- Check every ArchUnit rule has a control and the guard counts; check the interim constant guard.
- Check every `conformance.port` class asks the selector for its query and every AC-2a shell delegates to the hook.
- Check the rule-9 package literals include `adapter.in.http.dto`.

## Implementation command

`spec-kitty agent action implement WP18 --agent claude`
