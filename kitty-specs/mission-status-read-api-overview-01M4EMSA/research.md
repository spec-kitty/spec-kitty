# Research: Mission Status Read API, overview (Java service)

Decisions are binding where the spec says so; everything else is a plan decision with the alternatives named. Dates: 2026-10-10.

Numbering note: in this Mission's work-package numbering the spike discussed here is WP02 and the scaffold is WP03 (the plan and this file say "WP01" for the whole of phase 1 in places); see `tasks-overview.md` section 1, "Numbering note".

## R-1 Reduction ordering (Q-7)

- Decision: Java sorts by `(at, event_id)` as text (Unicode code point), deduplicates by `event_id` keeping the first, exactly as `materialize_snapshot` -> `spec_kitty_events.status.reduce` -> `reduce_parsed` does at 10.4.0 (`uv.lock`).
- Rationale: operator answer Q-7; pinned by goldens and the manifest field `specKittyEventsVersion`.
- Alternatives: causal (Lamport) ordering (rejected: not what Python runs; Python-side change first, #4941).

## R-2 Generated models versus hand-written DTOs (C-007)

- Decision: WP02 spikes openapi-generator 7.25.0 `spring` generator (interfaceOnly, models, OpenAPI 3.1 input from the split root, `apiPackage` and `modelPackage` pinned under `adapter.in.http`) for `/project` and `/missions`; the spike record at the end of this file states which mode the build is in.
- **Spike criteria (all recorded in the spike record; pass/fail each).** (1) The Jackson major actually on `runtimeClasspath`: the Boot 4.1.1 BOM (`spring-boot-dependencies-4.1.1.pom`) pins Jackson 3 (`jackson-bom` 3.1.5, `tools.jackson`) and also a Jackson 2 BOM (2.21.5); record which one the generated models' annotations and `JsonNullable` need and whether both coexist. (2) A required-nullable member (`type: [string, 'null']`) serialises as an explicit `null`, not omitted. (3) Member order of a generated response equals the canonical golden order. (4) Number formatting (`progress`) and non-ASCII output equal the Python-written golden bytes (plan section 13 canonical form). (5) `openApiGenerate` is green with plugin 7.25.0 on Gradle 9.7.1. (6) The generated interfaces compile against Spring MVC under Boot 4.1.1.
- **Go/no-go rule.** Generated models are accepted only if criteria 1-6 all pass without a hand patch of generated output. Any failure selects hand-written DTOs in `adapter.in.http.dto` plus the AC-11c replacement (drift test) recorded in the decision record; no partial or patched-generation mode exists.
- **Contract document (operator decision E-11, contract-first).** The service serves the committed `contracts/mission-status` document as it stands, bundled at build time, at `/api/v1/openapi.yaml`; springdoc generates and serves nothing, at runtime or in test scope, because a second document generated from the controllers can drift from the contract that the generated interfaces and the validator follow. WP02 spike criterion 7: the bundling mechanism (candidate: `contracts/tools/bundle.py --bundle-only`, the bundler the contract tooling already uses) writes a single file whose bytes equal what the service serves for the same commit, and it runs on all four legs; recorded in the spike record.
- **Spike outcome (WP02, 2026-10-11): GENERATED mode.** Criteria 1-6 and 8 pass without a hand patch; criteria 3 and 4 need the mapper configuration recorded in the spike record. Criterion 7: bundling mechanism B (pre-job artifact), digest and reason in the record.
- Rationale: operator decision D-Q2. Fallback: hand DTOs in `adapter.in.http.dto` plus the drift test of AC-11c.
- Alternatives: generate SSE too (rejected, spec), generate from the bundle instead of the split root (considered; the split root is the contract authority).

## R-3 Response validator

- Decision: networknt json-schema-validator (JSON Schema 2020-12 dialect, honours `unevaluatedProperties` and `type: [string, 'null']`), schemas extracted from the contract bundle.
- Alternatives: swagger-request-validator (OpenAPI 3.0 era; rejected), the generator's Java parser (drops 3.1 constructs, `contracts/build.gradle` comment).

## R-4 Supply chain and versions (DIRECTIVE_051 / `supply-chain-install-safety` checklist)

| Control | Result |
|---|---|
| Pinned versions | catalog only; Gradle 9.7.1, Spring Boot 4.1.1 (BOM: Tomcat 11.0.24, Jackson 3.1.5 and 2.21.5), no springdoc (operator decision E-11, plan.md section 13), openapi-generator plugin 7.25.0, JaCoCo 0.8.15, networknt 3.0.8, ArchUnit 1.4.2 (re-verified at WP01) |
| Provenance / age | Gradle 9.7.1 built 2026-08-19 (date and wrapper checksum from a web read, re-fetched at WP01: plan.md Unverified 18); Boot 4.1.1 latest stable of 4.x in Central metadata; openapi-generator plugin pin equals `contracts/tools/pins.json` (sha256 `34bf234e...`) |
| Checksums | strict `gradle/verification-metadata.xml` (`verify-metadata` true, `verify-signatures` false, the same stated limit as `contracts/`); wrapper `distributionSha256Sum`. Generated once on Linux x64 by a run that resolves every configuration (`check nativeCompile nativeTest nativeSmoke jacocoTestReport openApiGenerate`, plan section 2), not by `help`; the other three legs verify only. WP02 recorded (2026-10-11, Linux x64): no resolved artifact has an OS or arch classifier; re-running the write step merges additively; the scratch project's file is 359 components and about 156 KiB (the real service will be larger); behaviour on another OS is owed to the first non-Linux leg |
| Toolchain | no JDK auto-download (`org.gradle.java.installations.auto-download=false`), no foojay resolver plugin, `java.toolchain` 25 with the vendor unconstrained, `JAVA_HOME` from the SHA-pinned `graalvm/setup-graalvm` on every leg including the JVM leg; pinned by a build test (plan section 12) |
| Advisory feeds | checked at WP01 per dependency (Gradle, Spring Boot, Tomcat, Jackson, GraalVM); not run at planning time (no network tooling beyond registry metadata) |
| Install-time execution | none outside Gradle; no postinstall hooks (JVM) |
| CI hardening | actions pinned by SHA, `persist-credentials: false`, read-only token, wrapper-validation first |

## R-5 Native toolchain

GraalVM Community JDK 25.0.2 (graalvm-ce-builds), via `graalvm/setup-graalvm`; Native Build Tools version is Boot-managed. Windows needs MSVC (preinstalled on the Windows runner image; confirmed by the first run). Fallback if a target fails: `jlink`/`jpackage` (named in #5528).

## R-6 Workflow topology

One file, `mission-status-api.yml`, jobs: `jvm` (ubuntu-24.04), `native` (4-leg matrix), `mission-status-api-gate` (terminal; FR-015's aggregate job; `if:` canonical fork guard, then `github.event_name != 'schedule'`, then `always()`; it also compares the four leg digests; plan section 5), `nightly-corpus` (schedule/dispatch only), and `release` (a tag push of `mission-status-api-v*.*.*` only; operator decision E-4, 2026-10-10; plan section 12). The `jvm` job carries the canonical fork guard and then `!= 'schedule'`, is one of the gate's `needs` and is separate from the Linux x64 native leg. Reason for one file: `reusable_workflow_ceiling: 20` and 19 existing files. Not added to the router `needs` (a path-filtered workflow posts no check when skipped, so the router gate would wait forever or misread).

## R-7 Host/Origin refusal (Q-5)

See plan.md section 8. Decision 403 / `request_refused`, constant `HostOriginRefusal.STATUS`. The expected status per AC-9b row is FIXED in plan.md section 8 from the Tomcat source (`Http11Processor.prepareRequest`, `AbstractProcessor.parseHost`, `Host.parse`, `HttpParser.readHostDomainName`, `apache/tomcat` `11.0.x`, read 2026-10-10): rows 1-7 and 9 reach the filter and answer 403; row 8 (`evil.example@127.0.0.1:<port>`) is rejected by the container with 400, as are the three container-decided rows added to AC-9b set 2 after analyze (duplicate Host, HTTP/1.1 without Host, HTTP/1.1 absolute-form foreign target with an accepted Host): set 2 is four 400 rows, `reachesFilter` false for all four. The WP02 spike (a throwaway, uncommitted harness outside the repository tree; plan section 8) runs the table against the pinned 11.0.24 jar and records, per row, the observed status and whether the filter was entered (a test-profile counter). **Outcome (2026-10-11): all rows CONFIRMED against Tomcat 11.0.24; see the spike record.** It CONFIRMS the plan table; a divergence is a finding against the plan or the spec, never an automatic rewrite of the expected value. Also recorded by the spike: the body of a container-generated 400. Operator decision E-1 (2026-10-10): the spec lists the closed set of 400 values and no custom container valve re-renders them.

## R-8 Python oracle location

Generator and golden test live in `tests/contract/` (their imports stay inside src files the `contract_tools` router group already names) rather than `scripts/` so that `tests (contract tools)` owns them and the router glob suffices. Alternative: `scripts/ci/` (rejected: scripts/ is not run by the contract tool job and the oracle helpers are in `tests/contract`).

## R-9 Q-3 classification

Empty at planning time. This section is documentation only: no script reads it and it never turns a Python/Java difference green (the nightly fails on any difference, plan.md section 7; no exemption, operator decision E-10). It records, for each Mission class found by the first nightly full-corpus run and the resolver-cases review, where Python's answer needs a git verdict: the Python verdict used, what the service reads, and the class `same`, `differs` or `unknown`.

## Squad dispositions

Plan review round 1 (2026-10-10): a read-only reviewer squad (governance, architecture, JVM architecture, verification lenses) raised findings; independent refuters confirmed 30 (`reviews/plan.confirmed.yaml`). All 30 are dispositioned ACCEPTED and addressed in this commit by the fixer (a different seat from the author and the reviewers); none was rejected or dropped. Findings whose remedy needs a decision outside the plan are accepted as an escalation row rather than applied: plan.md section 14, items E-1 (PLAN-GOV-002, PLAN-ARCH-006, PLAN-ARCH-007), E-3, E-4 (PLAN-ARCH-JVM-008), E-5, E-6 (PLAN-GOV-005), E-7, E-8, and E-10 as numbered then (PLAN-ARCH-002, PLAN-ARCH-005; withdrawn in round 2, see below, the number now names the nightly-exemption row). The review trail is committed under `reviews/` (`plan-*.yaml`, `plan.merged.yaml`, `plan.confirmed.yaml`).

Plan review round 2 (2026-10-10): a fresh-eyes sweep (`reviews/plan-fresh.yaml`, 14 findings PLAN-FRESH-001 to 014) and the round-1 verification (`reviews/plan-verify-r1.yaml`) are committed as the trail. All 14 are addressed by a fixer seat: the two-seam design restored (PLAN-FRESH-001), the nightly made strict with no exemption (002), the owner of each port-package dependency, write scope, phase gate and cross-reference made consistent (003, 004, 006, 009, 013), E-1 and E-7 given one statement (005), springdoc returned to a runtime dependency with endpoints disabled (007; superseded by the 2026-10-10 contract-first decision E-11, which drops springdoc), the bind guard extended to an unset address (008), the release job stated as absent (010), connect-time failures, the JDK allowance and the overflow policy declared (011, 012), and the branch gate and Gradle facts recorded (014).

Plan review round 4 (2026-10-10): the findings PLAN-FRESH3-001 to 011 (`reviews/plan-fresh-r3.yaml`) and PLAN-NEW3-001 to 005 (`reviews/plan-verify-r3.yaml`) are addressed by a fixer seat: the projection component and its pattern source of truth (FRESH3-001), the coordination worktree path and the project-header HEAD materialisation (002, 003), the phase 3 dependency of 4a and 5 and the wiring class (004), the executable homes of the JaCoCo scope, digest and tag-floor guards (005, NEW3-001, NEW3-003), the project-root check and the README stub (006, NEW3-002), the nightly refusal contract and the husk wording (007, 008), the skeleton test deletion and the 404 assertions (009, NEW3-004), the nightly script imports (010), the jvm job (011) and the interim-id guard (NEW3-005). The operator decisions E-1, E-4, E-10 and E-11 of `reviews/plan.ruling.md` are applied.

## WP01 spike record (to be appended)

Generated-vs-hand mode with the R-2 criteria 1-6 and the go/no-go outcome; contract-document bundling mechanism (R-2 criterion 7); Tomcat Host table (observed status and filter-entered flag per row, container 400 body); `jdk.ProcessStart` JFR event; `SseEmitter(0L)` native result; Jackson major and null/ordering/number results; JaCoCo on Java 25; networknt `unevaluatedProperties` negative case; plugin 7.25.0 on Gradle 9.7.1; OS classifiers in the resolved set; four-target native build timings (including the doubled native compile); verification-metadata churn size; `stampLedger` cost over the corpus.

### Spike record, 2026-10-11 (WP02, researcher-robbie)

Method: a throwaway Gradle project in `<scratch>` (outside `<repo>`, nothing from it committed), one Spring Boot 4.1.1 app that grew the pieces under test (generated interfaces and models for `getProject` and `listMissions`, the Jackson mapper, a counting Host filter, a contract-document controller, an `SseEmitter(0L)` endpoint, a SnakeYAML probe), built with the pinned versions and run in JVM mode and as a native binary. Timings carry the machine load at the moment they were taken (24 cores, 30 GB; other sessions were running test suites, so the load averages are not quiet). A result that contradicts the plan is a FINDING, listed as such; no expected value in the plan was rewritten.

#### Environment

| Item | Observed |
|---|---|
| JDK | `openjdk 25.0.2 2026-01-20`, GraalVM CE `25.0.2+10.1` (build `25.0.2+10-jvmci-b01`) |
| `native-image` | `25.0.2 2026-01-20` |
| C toolchain | gcc `16.1.1 20260515`; `zlib-ng-compat-devel 2.3.3`, `glibc-devel 2.43` present; Fedora Linux 44 |
| Gradle | `9.7.1`, build time 2026-08-19 14:16 UTC, revision `92f0512e7f06d84621afba191f75e265363890cf` |
| Provenance | the JDK and Gradle were installed by the orchestrator once, with the operator's approval, checksum-verified; this WP installed nothing |
| Gradle zip checksum | the vendor `.sha256` fetched again from `services.gradle.org` equals the recorded `acd53f1edaf02f1a8ff99879f8a34b302661a057d9b063ae9e35b552f804d20a` (MATCH); the zip's `Last-Modified` is 2026-08-19 (Unverified 18 closed) |
| GraalVM tarball checksum | the vendor `.sha256` of `graalvm-community-jdk-25.0.2_linux-x64_bin.tar.gz` (release `jdk-25.0.2`) fetched again is `e0be791c8fda4d03b6b0a0cb824fef3149736170057b3a515252b44419606af0` and equals the digest GitHub lists for the release asset (MATCH between the two vendor-side sources; the tarball itself was verified by the orchestrator at install and is not on this machine) |
| Wrapper | generated by the provisioned Gradle: `./gradlew wrapper --gradle-version 9.7.1 --gradle-distribution-sha256-sum acd53f1e...d20a` ran green in the scratch project; the properties file carries `distributionSha256Sum` and the services.gradle.org URL |
| Native Build Tools | `1.1.8` (`native-build-tools-plugin.version` in `spring-boot-dependencies-4.1.1.pom`; the plugin DSL still needs the version written out: `id("org.graalvm.buildtools.native") version "1.1.8"`); GraalVM reachability metadata repository `1.0.9` is downloaded at build time (`graalvm-reachability-metadata-1.1.8-repository.zip`, a checksum entry in the verification file) |
| Other BOM facts read from the pom | Tomcat `11.0.24`, Jackson `jackson-bom 3.1.5` and `jackson-2-bom 2.21.5`, SnakeYAML `2.6`; `io.spring.dependency-management` `1.1.7` was used with the Boot plugin |

Action pins (read with `gh api` on 2026-10-11, annotated tags dereferenced; the table WP04 copies; every SHA except `gradle/actions` and `graalvm/setup-graalvm` is the one `contracts.yml` / the other workflows already use):

| Action | Tag | Commit |
|---|---|---|
| `gradle/actions/wrapper-validation` | v6.4.0 (published 2026-09-28) | `3f5f9adaf7d9fecd50b5935e54106014257a94e6` |
| `graalvm/setup-graalvm` | v1.6.7 (published 2026-10-01) | `27b360dbb857524eaf0b4c4cef364d38e5b4f173` |
| `actions/checkout` | v5.0.0 | `08c6903cd8c0fde910a37f88322edcfb5dd907a8` |
| `actions/upload-artifact` | v7.0.1 | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` |
| `actions/download-artifact` | v4.1.8 | `fa0a91b85d4f404e444e00e005971372dc801d16` |
| `astral-sh/setup-uv` | v10.0.1 | `20cfd1bf945f4377ade1205e4dbc17946fc9a30d` |
| `actions/setup-python` (only if bundling mechanism A) | v6.1.0 | `83679a892e2d95755f2dac6acb0bfd1e9ac5d548` |
| `actions/setup-java` (used by `contracts.yml`, not needed once `setup-graalvm` provides `JAVA_HOME`) | v6.0.1 | `de7274f081f381c8f8158605e0321c36c376e2e6` |

#### T004 toolchain and library compatibility

| # | Item | Result | Evidence and fallback |
|---|---|---|---|
| 1 | Boot 4.1.1 plugin on Gradle 9.7.1, Java 25 toolchain; `help` and a hello `@RestController` `bootJar` | PASS | `help bootJar` green in 38 s. FINDING: `processTestAot` fails with `'groupId' must not be empty` unless `project.group` is set; WP03 sets `group = "org.speckitty.missionstatus"`. `org.gradle.java.installations.auto-download=false` honoured (the pinned JDK was found as the Java 25 toolchain) |
| 2 | Native Build Tools plugin version | PASS | 1.1.8 (see Environment); no Gradle deprecation warning in any run |
| 3 | Empty tag filter under Gradle 9.7.1 (`useJUnitPlatform { includeTags("perf") }`, no test carries the tag, test sources present, `check` depends on the task) | PASS (no failure) | Gradle 9.7.1 PASSES it. `Test.failOnNoDiscoveredTests` exists and defaults to `true` (read from the property), but it does not fire here: tests are discovered and then excluded by the tag. Also passing: a `Test` task whose test classes directory holds no test class (task runs, passes) and one with no class directory at all (`NO-SOURCE`). The only failing form found is a class filter with no match: `filter { includeTestsMatching("nomatch.*") }` fails with `No tests found for given includes: [nomatch.*](filter.includeTestsMatching)`. Decision for WP03 T012 step 8: no switch is needed for tag filters; do not set `failOnNoDiscoveredTests = false` (it would only matter for the class-filter form). The zero-test case is therefore caught only by the floor guards (`native-tag-floor`, class floor), as planned. The finder's recollection (Gradle 9 fails an empty tag filter) is refuted |
| 4 | `org.openapi.generator` plugin 7.25.0 on Gradle 9.7.1, `openApiGenerate` against the split root read in place | PASS | Green; no patch to the plugin, pin unchanged. FINDING (Kotlin DSL): the task properties are `Property<>` types, set with `.set(...)` (`inputSpec`, `outputDir`, `apiPackage`, `modelPackage`, `generatorName`, `openapiNormalizer`, `globalProperties`, `configOptions`); plain `=` fails to compile. The generator prints two "is not set" warnings for `generateJsonIncludeAnnotations` and `generateJsonSetterNullsAnnotations`; WP03 sets both to `false` explicitly to pin the 7.23-equivalent output and silence them |
| 5 | ArchUnit 1.4.2 on Java 25 class files | PASS | 32 main classes imported (generated ones included); a rule forbidding Spring in `..domain..` reported the deliberately violating `Violator` class and a clean sub-rule reported none. No catalog change (1.5.1 not needed) |
| 6 | JaCoCo 0.8.15 on a Java 25 test run | PASS | `jacocoTestReport` XML produced (the three `domain` classes listed). Pattern syntax: `includes = ["org.speckitty.missionstatus.domain.*"]` matches the sub-package class `domain.model.Thing` as well as `domain.Calc` (`*` crosses `.`), and a rule on `...domain.model.*` matches only the sub-package. A pattern matching zero classes (`...nothere.*`, minimum 1.0) PASSES vacuously, which is why `jacocoScopeCheck` exists. Spring AOT classes are built into separate source-set output directories, not the `main` class directories, so they are outside a `main`-directory scope by construction |
| 7 | networknt 3.0.8 | PASS | Needs no catalog extras (it uses Jackson 3 `tools.jackson` nodes). Built against the schemas of the Python bundle (see T006 note: the bundle has every `$ref` inlined, so the response schema is read from `paths./missions.get.responses.200...schema` and `paths./project...`, not from `components`). `MissionOverview`: valid example 0 errors; one extra property -> `unevaluatedProperties: property 'bogus' is not evaluated and the schema does not allow unevaluated properties`. `Project`: valid 0 errors; extra property -> `additionalProperties` error; `specKittyVersion: null` -> 0 errors; `specKittyVersion: 5` -> `type: integer found, [string, null] expected`; a missing required member -> 1 error. Dialect used: 2020-12 |
| 8 | `--write-verification-metadata sha256` over `check nativeCompile nativeNtTest nativeTestCompile jacocoTestReport openApiGenerate --refresh-dependencies` | PASS | One run, 125.9 s wall at load 16.5 -> 25.8: 359 components, 614 `sha256` entries, 160,221 bytes (about 156 KiB) for the scratch project (the real service will be larger). Artifact kinds: 183 jar, 96 module, 334 pom, 1 zip. OS or arch classifier: NONE (a grep for linux/osx/windows/aarch/x86/amd64/arm64 hits only plugin names such as `native-gradle-plugin`). Re-running the write step is ADDITIVE on Linux: adding one dependency (guava) and re-running over `compileJava` left every existing line (0 removed) and inserted 7 components (56 lines) in sorted position. Merging when the step is re-run on another OS cannot be observed on this machine: owed to the first non-Linux leg (WP04 appends). A build whose plugin set differs resolves different plugin-classpath versions (commons-io 2.16.1, commons-lang3 3.16.0, slf4j-api 1.7.36 appeared as missing entries when the generator plugin was removed): the metadata file is specific to the plugin set, so WP03 generates it after the mode is fixed and regenerates it if the mode ever changes. `verify-signatures` stays false (the same stated limit as `contracts/`) |
| 9 | YAML library for `.kittify/config.yaml` and `.kittify/metadata.yaml` | PASS | SnakeYAML `2.6` (the BOM version) resolves under strict verification (it is in the 359 entries). With `new Yaml(new SafeConstructor(loaderOptions))` and `allowDuplicateKeys=false`: a real `metadata.yaml` parses (`spec_kitty.version` is the String `4.0.0rc7`, `spec_kitty.schema_version` is the Integer `3`; ignoring the other keys), a real `config.yaml` parses (`project.slug` is `spec-kitty`; unlisted keys `vcs`, `agents`, `charter`, `merge`, `review`, ... ignored); a broken file throws `ParserException`, an empty file loads as `null`, a duplicate key throws `DuplicateKeyException` (all three must map to the "absent or unreadable" answer the contract gives). A version written unquoted as `4.0` would load as a Double, not a String: the reader must treat any non-String as "not a string" (null). (b) ArchUnit consequence: plan section 13 rule 8 lists "JSON libraries and Spring" only; SnakeYAML is neither, so add `org.yaml.snakeyaml..` to the library set of rules 1(a) and 2(a) (forbidden in `domain` and `application`) and to rule 8, and allow it ONLY in `adapter.out.filesystem..` excluding its `codec` sub-package (rule 12 keeps `codec` to `domain..`); forbidden in `adapter.in.http` and `config`. The reader is one class of the filesystem adapter that parses text it is handed. (c) Native hint: none (a `SafeConstructor` load into `Map`/`List`/scalars ran in the native binary with no hint beyond the resource hint for the file itself) |
| 10 | Nested builds (AC-11c drift, AC-14a tamper) with Gradle TestKit under strict verification, offline | PASS in both modes | Run through `GradleRunner` pinned with `withTestKitDir(<GRADLE_USER_HOME>)`, arguments `--offline` and `-PcontractRoot=<copy>`. Generated mode: an unmutated copy of the project plus contract compiles (6.0 s); the same copy with `blockedCount` renamed in `schemas/MissionHead.yaml` fails (2.4 s) with `error: cannot find symbol` at the hand-written `new MissionOverview().blockedCount(1)`; a copy with one hex digit of one `sha256` in `verification-metadata.xml` altered fails (6.4 s) with `Dependency verification failed for configuration ':compileClasspath'` / `One artifact failed verification: jackson-annotations-2.21.jar (com.fasterxml.jackson.core:jackson-annotations:2.21) from repository MavenRepo` (WP03's test matches the stable prefix `Dependency verification failed for configuration`). Hand mode (no generator plugin, no generated source): metadata written once, the unmutated copy resolves offline, an altered checksum fails with `Dependency verification failed for configuration 'classpath'` / `One artifact failed verification: jackson-annotations-2.21.jar ...` (the failing configuration differs, `classpath` of the buildscript versus `:compileClasspath`, so the test matches only the common prefix). FINDING: `gradleTestKit()` on the same classpath as Spring tests breaks `processTestAot` (`LoggerFactory is not a Logback LoggerContext but Logback is on the classpath`, Gradle's slf4j binding collides with Logback), so the TestKit tests live in their own source set with their own `Test` task (here `kit`), never in `test`. Another TestKit rule: `--no-daemon` is an unsupported build argument (the runner rejects it). Whole `kitTest` run: 22.6 s wall including the outer build (machine load average between 6 and 13 in that period); the nested daemon is warm after the first build |

Fallbacks: see the FALLBACK table at the end of this record.

#### T005 R-2: generated models versus hand DTOs (C-007)

Setup: plugin 7.25.0, generator `spring`, input the split root in place, `apiPackage` `org.speckitty.missionstatus.adapter.in.http.api`, `modelPackage` `org.speckitty.missionstatus.adapter.in.http.model`. `configOptions`: `interfaceOnly=true`, `useSpringBoot3=true` (the jakarta namespace), `useTags=true`, `documentationProvider=none`, `openApiNullable=false`, `defaultInterfaces=false`, `skipDefaultInterface=true`, `useBeanValidation=true`, `performBeanValidation=false`, `hideGenerationTimestamp=true`. No generated file was patched.

| # | Criterion | Result | Observation |
|---|---|---|---|
| 1 | Jackson major on `runtimeClasspath` and what the generated code needs | PASS | `runtimeClasspath` carries Jackson 3 `tools.jackson.core:jackson-databind` / `jackson-core` 3.1.5 and `com.fasterxml.jackson.core:jackson-annotations:2.21` only (the annotations artifact is shared by both majors); NO `com.fasterxml.jackson.core:jackson-databind` (Jackson 2 databind). The generated models import only `com.fasterxml.jackson.annotation.*` (`@JsonProperty`, `@JsonCreator`, `@JsonValue`, `@JsonTypeName`), which Jackson 3 honours. With `openApiNullable=false` no `JsonNullable` (the Jackson 2 `jackson-databind-nullable`) appears; `openApiNullable=true` was not exercised and must not be turned on |
| 2 | Required-nullable member serialises as explicit `null` | PASS | `acceptedAt`, `nextAction`, `specKittyVersion`, `schemaVersion`, `currentBranch`, `lastActivityAt` and `nextPageCursor` come out as `null` (Jackson 3 writes nulls by default), on the JVM and in the native binary |
| 3 | Member order equals the canonical golden order | PASS with a configuration FINDING | Out of the box the order is the declaration order of the contract, not sorted: Boot's plugin compiles with `-parameters`, Jackson 3 then detects the generated all-required-arguments constructor as a creator and `MapperFeature.SORT_CREATOR_PROPERTIES_FIRST` (default on) puts those parameters first. The mapper must `enable(MapperFeature.SORT_PROPERTIES_ALPHABETICALLY)`, `disable(MapperFeature.SORT_CREATOR_PROPERTIES_FIRST)` and `enable(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS)`; with those, nested objects (`progress`, `statusLaneCounts`, `streamCursor`, `pageInfo`) and the list items all match the sorted golden |
| 4 | Number formatting and non-ASCII equal the Python canonical form | PASS with a pinned function | The generated `progress` members are `BigDecimal`. With the default serializer `65.0000` (scale 4) would print `65.0000` and `0` would print `0`, neither equal to Python's `65.0` and `0.0`. A `BigDecimal` serializer registered on the mapper that writes `stripTrailingZeros().toPlainString()` plus `.0` when no fraction (zero as `0.0`) reproduces Python's `repr` for every value tried: `65.0`, `12.3456`, `0.0001`, `0.0005`, `0.001`, `33.3333`, `99.9999`, `7.0`, `100.0`, `0.0`. Strings with `é ☕ ï 日本語`, an emoji, a quote, a backslash, a tab and a DEL character are byte-equal to `json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"))` (Jackson does not escape non-ASCII; it escapes control characters below 0x20 the way Python does). Dates: the mapper must keep `WRITE_DATES_AS_TIMESTAMPS` off; `…Z` round-trips as `…Z`, `+00:00` is written as `Z`, `+02:00` is converted to the UTC instant, fractions are kept as given (`.5Z`, `.123456Z`): the domain must hand the adapter UTC instants whose rendering matches the golden, which is the Python writer's rule to pin in phase 2/3. Four golden files (a page with ten edge-case items, `Project` populated, `Project` all-null, the contract's own `MissionOverviewPage.first`) built by the Python canonical dump round-tripped byte-identical through generated models and the configured mapper, and the same bytes came back over real HTTP |
| 5 | `openApiGenerate` green on Gradle 9.7.1 | PASS | see T004 item 4 |
| 6 | Generated interfaces compile against Spring MVC under Boot 4.1.1 | PASS | `compileJava` green with `ProjectApi` and `MissionsApi` implemented by two `@RestController` classes. Needs `jakarta.validation:jakarta.validation-api` for the annotations; `spring-boot-starter-validation` is NOT needed and should not be added: with Hibernate Validator on the classpath the Native Build Tools TEST binary of a non-Spring source set fails to build (`Type not found during analysis: ...PastValidatorForReadablePartial`); consequence: with `performBeanValidation=false` and no validator, the framework enforces none of the generated `@Min`, `@Max`, `@Size` parameter constraints, so the application owns the `pageSize` clamp and the cursor refusal |
| 8 | Out-of-scope operations | PASS | Mechanism: the generator's `openapiNormalizer = {"FILTER": "operationId:getProject\|listMissions"}` (5 other `Missions` operations, `streamEvents`, `Drift` and `Ops` produce no interface at all) plus an explicit model list `globalProperties.models = "MissionOverview,MissionOverviewPage,MissionProgress,PageCursorRefusal,PageInfo,Problem,Problem_1,Project,StatusLaneCounts,StreamCursor,Workspace"`. The FILTER alone is not enough: it removes the operations but the other schemas are still generated (58 model classes against 11 needed), so the explicit list is what keeps the model package, ArchUnit rule 9's scan, the JaCoCo exclusions and the AC-11c mutation target small. `Problem_1` is the schema name of the generator's inline duplicate (class `Problem1`); `Problem1` as a list entry generates nothing. A missing name is a compile error in `ProjectApi`/`MissionsApi`, so the list cannot silently under-generate; an extra name is harmless. Result: 2 interfaces plus 11 models, and each of the five other `Missions` paths (`/missions/{id}`, both work-package paths, both artifact paths) plus `/drift`, `/ops/invocations` and `/events` answered 404 with an accepted Host, not 501. For contrast, generating all operations with `defaultInterfaces=true` produces `default` methods returning `HttpStatus.NOT_IMPLEMENTED`: that is the failing form |
| E-8 | Production mapper emits the canonical bytes | PASS | The configured `JsonMapper` bean (Jackson 3 `tools.jackson.databind.json.JsonMapper`, the properties of criteria 3 and 4) is what Spring MVC used: `GET /project` and `GET /missions` returned bytes `cmp`-identical to the Python canonical golden. E-8 is not triggered; AC-15b stays raw-byte equality |

Extra FINDINGS for WP03/WP10 from the same harness:

- The contract says `servers: /api/v1`, but the generated mappings are server-relative (`"/project"`, `"/missions"`). The prefix must be added by an MVC path prefix: `WebMvcConfigurer.configurePathMatch(c -> c.addPathPrefix("/api/v1", HandlerTypePredicate.forBasePackage(<controller package>)))`. `spring.mvc.servlet.path=/api/v1` (and a context path) must NOT be used: with it, a request outside the prefix, such as `/nope`, is answered 404 by the container WITHOUT entering any filter, so the Host/Origin filter would not cover unknown paths, contradicting FR-009 ("every path including unknown paths"). (The container-404-without-filter claim was first stated without a recorded observation; it is observed in Review cycle 2 F2.) With the MVC prefix the filter was entered for all five targets of every row (table below).
- Boot's default 404 body is JSON with `error`, `path`, `status` and `timestamp` (it echoes the request path). That is outside this spike, but AC-9g/AC-4c authors should know the unknown-route body is not a contract Problem unless an error handler is added.
- The generated documentation for the `default` response says "(status code 200)" and the `default` response yields a second class `Problem1` besides `Problem`; cosmetic, listed so nobody tries to remove it by hand.

**Go/no-go: GO, generated mode** (criteria 1 to 6 and 8 pass without a hand patch of generated output; criteria 3 and 4 need the mapper configuration above, which is configuration, not patching). Hand DTOs in `adapter.in.http.dto` and the YAML-parsing drift test are NOT selected; the AC-11c nested-build mechanism (T004 item 10) is.

#### T006 R-2 criterion 7: contract-document bundling

Facts: `bundle.py --root contracts --out <outside-repo> --module mission-status --bundle-only` wrote `bundle/mission-status/openapi.yaml`, printed `bundle sha256 mission-status fadf8a869e9402306be3fc0a9fb8f3470b507a21ebfa645f0400d53fc2d0effd` and `counts: modules=1 bundles=1 path_items=10`; the tool writes the module twice into two directories and reports `BUILDS_DIFFER` if they differ (it did not). The bundle is 475,687 bytes, with no `$ref` left (every reference inlined, so the document the service serves has no `components` section for the schemas). Served versus written: the classpath copy served at `GET /api/v1/openapi.yaml` hashed to the same digest on Linux, in JVM mode and as a native binary (with the resource hint). `OUT_INSIDE_REPOSITORY` finding: `--out services/mission-status-api/build/contract` is REFUSED (`inside the repository working tree`): a Gradle build directory under `services/` is inside the working tree even though it is ignored, so a `bundleContract` task cannot point the tool at its own `build/` output. Mechanism A would have to run the tool into a temporary directory outside the repository and copy the file in.

Requirements per leg (mechanism A): Python 3 with PyYAML 6.0.3 (the `uv.lock` pin; here the repository venv runs the tool) and the sibling `contract_resolver`; the Linux runners and macOS/Windows images need `setup-uv` plus `uv sync --frozen` on every native leg and the `jvm` job (the repo's contracts workflow already does this on ubuntu). Not provable here: byte equality on Linux arm64, macOS arm64 and Windows x64 (PyYAML dump formatting and newline handling are the risk; the tool writes `newline="\n"` and UTF-8 explicitly). Those three legs are "confirmed by the first workflow run" and the acceptance rule of plan section 13 cannot be met locally.

**Decision: mechanism B** (a pre-job `contract-bundle` on ubuntu-24.04 runs the tool once into a directory outside the checkout, uploads the single file and its SHA-256 as a workflow artifact; every leg downloads it into the build's resource input; `bundleContract` verifies the SHA-256 the job passes in and fails on a mismatch). Reason: A's acceptance condition cannot be shown for three of the four legs now, and A needs an outside-repo temp directory plus Python tooling on four OS images; B makes the bytes equal on all legs by construction, costs one more job and one workflow artifact, and writes no second bundler (no SnakeYAML dereferencer, which could drift from the contract authority). For a local run the same task takes `-PcontractBundle=<file>` and `-PcontractBundleSha256=<digest>`, produced by the one tool invocation in `quickstart.md`. Digest at this commit: `fadf8a869e9402306be3fc0a9fb8f3470b507a21ebfa645f0400d53fc2d0effd`. Byte-equality procedure for WP10's AC-11d test: run the tool at the same commit into a directory outside the repository, take the file's SHA-256, request `GET /api/v1/openapi.yaml` with an accepted Host, require the response body bytes to equal the file's bytes (and the digest to equal the value the build verified), on every leg that has the artifact.

#### T007 R-7: Tomcat 11.0.24 Host table, observed

Harness: the Boot 4.1.1 BOM's Tomcat (log line `Apache Tomcat/11.0.24`), `server.address=127.0.0.1`, port 0, a counting filter registered at `HIGHEST_PRECEDENCE` that logs "filter entered" and refuses with 403 when the raw `Host` header is not `127.0.0.1:<port>` or `localhost:<port>` or when `Forwarded` / `X-Forwarded-Host` is present. Raw sockets (Python `socket`, literal bytes). Each row ran on five targets (`/api/v1/project`, `/api/v1/missions`, `/api/v1/missions/<ulid>`, `/api/v1/events`, `/nope`); the result below was identical on all five.

| # | Host value | Expected | Observed status | Filter entered | |
|---|---|---|---|---|---|
| 1 | `evil.example` | 403 | 403 | yes | CONFIRMED |
| 2 | `evil.example:<port>` | 403 | 403 | yes | CONFIRMED |
| 3 | `127.0.0.1` | 403 | 403 | yes | CONFIRMED |
| 4 | `127.0.0.1:<port+1>` | 403 | 403 | yes | CONFIRMED |
| 5 | no Host (HTTP/1.0) | 403 | 403 | yes | CONFIRMED |
| 6 | `127.0.0.1.evil.example:<port>` | 403 | 403 | yes | CONFIRMED |
| 7 | `localhost.evil.example:<port>` | 403 | 403 | yes | CONFIRMED |
| 8 | `evil.example@127.0.0.1:<port>` | 400 | 400 | no | CONFIRMED |
| 9 | `[::1]:<port>` (over IPv4) | 403 | 403 | yes | CONFIRMED |
| E1 | duplicate `Host` | 400 | 400 | no | CONFIRMED |
| E2 | HTTP/1.1 without `Host` | 400 | 400 | no | CONFIRMED |
| E3 | HTTP/1.1 absolute-form foreign target, accepted `Host` | 400 | 400 | no | CONFIRMED |
| E4 | HTTP/1.0 absolute-form foreign target | 403 | 403 | yes | CONFIRMED |
| E5 | empty `Host:` | 403 | 403 | yes | CONFIRMED |
| E6 | accepted `Host` + `X-Forwarded-Host: evil.example` | 403 | 403 | yes | CONFIRMED |
| E7 | accepted `Host` + `Forwarded: host=evil.example` | 403 | 403 | yes | CONFIRMED |
| E8 | `LOCALHOST:<port>` | 403 | 403 | yes | CONFIRMED |
| E9 | `localhost.:<port>` | 403 | 403 | yes | CONFIRMED |
| C1 | `127.0.0.1:<port>`, configured port 0 | 200 | 200 on `/project` and `/missions` (404 on routes not implemented) | yes | CONFIRMED |
| C2 | `localhost:<port>`, configured port 0 | 200 | same as C1 | yes | CONFIRMED |

No row DIVERGES; the AC-9b sets (eight 403, four 400) stand as written. Body of a container-generated 400 (identical for rows 8, E1, E2, E3): status line `HTTP/1.1 400`, headers `Content-Type: text/html;charset=utf-8`, `Content-Language: en`, `Content-Length: 435`, `Date`, `Connection: close` (no `Server` header, no version string); the body is one HTML page: `<!doctype html><html lang="en"><head><title>HTTP Status 400 – Bad Request</title><style type="text/css">…inline CSS…</style></head><body><h1>HTTP Status 400 – Bad Request</h1></body></html>`. It echoes no path, Host value, canary or environment value, so the AC-9g scan has nothing to find in it.

Unverified 19 (the accessor for the bound address): no public Tomcat accessor reports the address the socket actually bound. `Connector.getProperty("address")` and `AbstractProtocol.getAddress()` return the CONFIGURED address (`/127.0.0.1`; `null` when unset); `AbstractEndpoint.getLocalAddress()` and `NioEndpoint.getServerSocket()` are `protected`. `ss` showed the loopback listener as `[::ffff:127.0.0.1]:<port>`. So the post-start check in `BindGuard` can compare only what the connector was configured with (`getAddress()` must be the loopback InetAddress, and never `null`) unless it reads `getLocalAddress()` by reflection (which would need a native reflection hint); the plan's pre-start check on the effective `server.address` is the real guard. Default bind with `server.address` blank: `getAddress()` is `null` and the OS showed the socket as `*:<port>` (all interfaces), which justifies the "unset exits non-zero" rule.

#### T008 JFR, SSE, native resources, Jackson under native, native test wiring, native toolchain gate

| # | Item | Result | Evidence and hints |
|---|---|---|---|
| 1 | `jdk.ProcessStart` JFR event | PASS | On the pinned GraalVM CE 25.0.2 JDK in JVM mode a `Recording` with `jdk.ProcessStart` enabled, a child `ProcessBuilder("true")` and a dump read back one event named exactly `jdk.ProcessStart` with fields `startTime, eventThread, stackTrace, pid, directory, command` (`command` = `true`, `pid` set). Modules `jdk.jfr` and `jdk.management.jfr` are present. E-2 is not triggered |
| 2 | `SseEmitter(0L)` with `spring.mvc.async.request-timeout=-1` as a native binary | PASS | A curl client held the stream open for 42 s (past the 35 s bar) and received `: heartbeat` at 10 s, 20 s, 31 s and 41 s from a virtual thread; response headers `Content-Type: text/event-stream`, `Transfer-Encoding: chunked`. No native hint was needed. (The negative control without the property was not run; see Review cycle 2 F5a.) |
| 3 | Classpath resource under native | PASS with a hint | Without a hint `getResourceAsStream` returned null in the native binary (observed: HTTP 500 from a `NullPointerException` and `FileNotFoundException: class path resource [contract/openapi.yaml] cannot be opened because it does not exist`). The Spring way works: a `RuntimeHintsRegistrar` (`config.NativeHints`, imported with `@ImportRuntimeHints` on the application class) calling `hints.resources().registerPattern("contract/openapi.yaml")` (and likewise any other resource the code reads by name, here `golden/*.json`, `kittify/*.yaml`; for the real service `leak-patterns.json` too). The served bytes then hashed to the bundle digest |
| 4 | Jackson null members, ordering and numbers under native | PASS, no hint | Using the generated models, the configured mapper and Spring AOT only, `GET /project` and `GET /missions` from the native binary were `cmp`-identical to the Python canonical golden (explicit `null`s, sorted keys, pinned `progress`, UTF-8 text). Spring AOT registered the reflection for the generated return types; no `reflect-config` was written. SnakeYAML (T004 item 9) and networknt (it ships its own `META-INF/native-image` metadata, shown as experimental-option warnings at build) built into the image without a hint of ours |
| 5 | Native Build Tools test wiring | PASS, two forms | (a) Dedicated source set: `graalvmNative.registerTestBinary("<name>Test") { usingSourceSet(<set>); forTestTask(<JVM twin>) }` with a JVM `Test` task over the same set that carries `useJUnitPlatform { includeTags("native") }`. RULE FOUND IN THE PLUGIN SOURCE (tag 1.1.8): the binary name MUST end in `test` (case-insensitive); otherwise registration fails at configuration with `Task with name 'native<Name>' not found` (the run task is then named `native<Name>Run`). The binary `ntTest` produced `nativeNtTestCompile` and `nativeNtTest`; the JVM twin ran first (the tag filter applied: the 2 `native`-tagged tests ran, the class tagged `other` was excluded), then the native binary executed those two. Executed count: `build/test-results/ntTest-native/TEST-junit-jupiter.xml` -> `<testsuite name="JUnit Jupiter" tests="2" ...>` (the `native-tag-floor` input; the console also prints `2 tests found`/`2 tests successful`). Limits: the test binary's classpath includes the main runtime classpath and Spring AOT test processing exists only for the `test` source set, so tests in such a set are plain JUnit (no Spring context) and Hibernate Validator breaks its image build (see T005 criterion 6). (b) Tag filter on `test`: `tasks.test { useJUnitPlatform { includeTags("native") } }`, then `./gradlew nativeTest` compiled a Spring-AOT test binary and executed the tagged `@SpringBootTest(webEnvironment = RANDOM_PORT)` class natively (1 test found, 1 successful; `build/test-results/test-native/TEST-junit-jupiter.xml` has `tests="1"`; a second file `TEST-archunit.xml` with `tests="0"` sits beside it, so the floor must read the "JUnit Jupiter" suite or sum all files). Choice for WP03: (b) for tests that need the Spring context (the native route and byte tests), (a) only for context-free tests; both are proven. **SUPERSEDED in part by Review cycle 2 F1 (below): the literal filter on `test` in (b) makes `check` run only native-tagged tests; WP03 uses the unfiltered `test` plus the `nativeTagged` twin of the Review cycle 2 amendment** |
| 6 | Native toolchain gate | PASS | `native-image`, gcc 16.1.1 and the zlib headers are present; `nativeCompile` of the hello app succeeded and the binary answered its routes (`/api/v1/project`, `/api/v1/missions`, `/api/v1/openapi.yaml`, byte-equal as above). WP03 T014/T015 may be claimed. Wall-clock and load (1-minute load average at the start and at the end of each run; the builds themselves are part of the end value; each run alone on the build side, other sessions sharing the machine): `nativeCompile` first run 38.7 s, load 3.2 -> 10.3, 448 s CPU, peak RSS 5.5 GB; `nativeCompile` again after the resource hint 66.0 s, load 6.9 -> 24.9; `nativeNtTest` (JVM tag run + test binary compile + run) 43.5 s, load 25.3 -> 24.0; `nativeTest` with tag filter (Spring AOT test binary) 52.6 s, load 5.1 -> 11.9; the metadata-writing run (check, nativeCompile, nativeNtTest, nativeTestCompile, jacocoTestReport, openApiGenerate, refresh) 125.9 s, load 16.5 -> 25.8. The binary is about 98 MB. These are 24-core figures for a small app; CI runners with fewer cores and the real service will be slower, so the leg timeout budget cannot be taken from them directly (the main compile and the test-binary compile are two native-image runs of the same order, i.e. the doubled native compile) |

#### T009 `stampLedger` cost over this checkout's corpus

Method: Java harness in `<scratch>` over `kitty-specs/*/` (596 Mission directories now; 596 `meta.json` and 594 `status.events.jsonl` tracked by `git ls-files`, against 588 at planning). Per Mission: `Files.readAttributes` (size, mtime, file key), open the ledger, read at most the last 16 KiB, locate the last terminated line, SHA-256 it. Plus the listing of `kitty-specs/` sorted by Unicode code point. 300 passes per JVM run, 3 JVM runs, the first pass of each run reported separately (JVM cold, OS page cache as the machine had it; the page cache cannot be dropped without privilege, so a true cold-disk figure is NOT measured). Load average during the runs: 6.5 (1-minute). Filesystem btrfs.

| Quantity | Result |
|---|---|
| First pass in a fresh JVM, list + stamp of 596 directories | 191 ms (run 1), 47 ms (run 2), 46.5 ms (run 3) |
| Warm passes (299 per run), list + stamp | p50 4.7 to 4.9 ms, p95 8.7 to 9.8 ms; one outlier max 532 ms in run 1 (a single scheduling or page-cache event; 13 to 14 ms in runs 2 and 3) |
| Listing and code-point sort alone | p50 0.58 to 0.61 ms |
| Stat without the tail read | p50 0.56 to 0.60 ms |
| Per Mission, stat + bounded tail read + SHA-256 | about 7 microseconds |

Against NFR-001 (provisional: warm p95 under 200 ms, cold first call under 5 s, as a ratio to a same-run no-op floor): the probe alone is about 5 percent of the 200 ms ceiling warm and about 1 to 4 percent of the 5 s cold ceiling. The probe does not threaten NFR-001 at 596 Missions; no design finding and no escalation. The remaining budget is for the cache-miss reads, JSON, and HTTP; those are not measured here.

#### Decisions consumed by WP03, WP04 and WP10

1. Mode: generated models and interfaces (T005). The `openApiGenerate` task: generator `spring`, the options and the explicit `models` list of T005 (including `Problem_1`), `openapiNormalizer FILTER operationId:getProject|listMissions`, `generateJsonIncludeAnnotations=false` and `generateJsonSetterNullsAnnotations=false` stated explicitly; generated sources under `build/`, added as a `main` source directory, `compileJava` depends on the task. The plugin version stays 7.25.0.
2. Build: `group` set (needed by `processTestAot`); Boot plugin 4.1.1, `io.spring.dependency-management` 1.1.7, NBT plugin 1.1.8 written with its version; `org.gradle.java.installations.auto-download=false`; `jakarta.validation:jakarta.validation-api` and NOT `spring-boot-starter-validation`; no springdoc (E-11 unchanged); Jackson 3 only, `openApiNullable=false`.
3. Mapper: the mapper bean of T005 criteria 3 and 4 (sorted properties, creator-first sorting off, map entries by key, dates not as timestamps, one pinned `BigDecimal` function), exactly one `CanonicalJson`/golden comparison class on raw bytes. The pinned function is a unit-test target for 0, 7, 0.0001, 100, 65.0000.
4. Routing: `/api/v1` by `PathMatchConfigurer.addPathPrefix`, never by servlet path or context path (T005 finding, observed in Review cycle 2 F2); the Host filter then covers unknown paths.
5. Container 400: Tomcat's own HTML page, body above; AC-9g scans it; no valve.
6. Bundling: mechanism B (T006). WP04 adds the `contract-bundle` pre-job and the three-leg digest equality is then true by construction; `bundleContract` verifies the digest it is given. WP04 still appends whether the downloaded artifact is byte-identical on the other three legs after one real run.
7. Native: resource hints through `config.NativeHints`; no Jackson, SnakeYAML, SSE or networknt hints needed; native tests with a Spring context: `test` stays UNFILTERED (the JVM leg runs ArchUnit, goldens, networknt and the JaCoCo rule), a `nativeTagged` Test task over the same source set with `includeTags("native")` writes the test list, and the default `nativeTest` binary takes its list from it (exact wiring in Review cycle 2 F1; both counts shown from one build); the literal `tasks.test { includeTags("native") }` of the first record is withdrawn. Context-free ones may use a dedicated source set whose binary name ends in `Test`; the floor reads the "JUnit Jupiter" suite of `test-native`.
8. Verification: `verification-metadata.xml` is generated once per plugin set in one Linux run over every configuration (T004 item 8); `verify-signatures` false; any OS-classifier question for the other legs is owed to the first non-Linux run.
9. Nested builds: `gradleTestKit()` only in a separate source set with its own `Test` task; `withTestKitDir(<GRADLE_USER_HOME>)`; `--offline`; no `--no-daemon`; the tamper test matches `Dependency verification failed for configuration`.
10. `BindGuard`: pre-start check on the effective `server.address` is the guard; the post-start check compares the connector's configured address (public accessors only), `null` means all interfaces.
11. YAML: SnakeYAML 2.6 in `adapter.out.filesystem` outside `codec`; add it to ArchUnit rules 1(a), 2(a) and 8 and add the "only in the filesystem adapter" rule.
12. `stampLedger`: the plan's probe design stands (T009).
13. FINDINGS against the plan text (none rewrites an expected value): (a) plan section 13 says bundling "runs on every leg"; mechanism B is chosen instead of the candidate; (b) the Unverified-3 fallback ("tag filter on `test`") is not a fallback, it is the working form for Spring-context native tests; (c) the finder's recollection about Gradle 9 failing an empty tag filter is refuted (T004 item 3); (d) the post-start bound-address accessor does not report the bound address (Unverified 19); (e) the generated mappings carry no `/api/v1` prefix.

#### FALLBACK table

| Item | Pass condition | Result | Fallback if it fails | Owner |
|---|---|---|---|---|
| Generated models (T005 1-6) | all of criteria 1-6 without a hand patch | PASS | hand DTOs in `adapter.in.http.dto` plus the YAML-parsing drift test replacing AC-11c | WP03 / WP10 |
| Out-of-scope operation restriction (criterion 8) | five other `Missions` operations answer 404, model package holds only the closure | PASS in a harness with no controllers (Review cycle 2 F5c; the real-application proof is still owed) (FILTER normalizer + `models` list) | hand DTOs (no partial or patched generation) | WP03 T012 / WP10 T053 |
| Mapper emits canonical bytes (E-8) | raw-byte equality with the Python golden | PASS | E-8 escalation to the operator; never weaken AC-15b | WP03 / WP10 |
| Bundling (criterion 7) | served bytes equal the tool's output on all four legs | B chosen (A not provable locally) | B is the fallback already taken | WP03 / WP04 |
| `jdk.ProcessStart` JFR event | event exists and fires | PASS | E-2 escalation: operator-approved amendment may drop the runtime half | WP10 |
| `SseEmitter(0L)` under native | open past 35 s with heartbeat | PASS (no negative control run, Review cycle 2 F5a) | escalate (a platform-thread heartbeat is NOT allowed) | WP20 |
| Native resource | resource readable in the binary | PASS with a `RuntimeHintsRegistrar` hint | a `resource-config.json` under `META-INF/native-image` | WP03 |
| Native test wiring | tagged tests executed natively, count visible, AND the JVM `test` task still runs every non-native test, both counts from one build | PASS (Review cycle 2 F1: unfiltered `test` + `nativeTagged` twin feeding the default `nativeTest`: JVM 6 tests in 5 classes, native 1) | form (a), a dedicated source set (context-free tests only), or (not run) an inversion with `test` tagged and an unfiltered `jvmTest` wired into `check` | WP03 / WP04 |
| Native toolchain gate | `nativeCompile` of the hello app, binary answers | PASS | BLOCKED, owner orchestrator (repairs the toolchain per `tasks-overview.md` section 10); no CI-only fallback | WP03 T014/T015 |
| networknt 3.0.8 | negative cases fail, 3.1 constructs honoured | PASS | a different 3.1-capable validator, or schema pre-processing, named before WP03 | WP03 |
| YAML library | parses both shapes, strict verification, ArchUnit placement | PASS (SnakeYAML 2.6) | another YAML reader declared in the catalog, same placement rule | WP03 |
| AC-11c / AC-14a nested build | TestKit nested build fails on drift (both mutations: rename `MissionOverview.blockedCount`, remove required `Project.currentBranch`) and on a tampered checksum, passes unmutated, offline | PASS in generated and hand mode (second mutation observed in Review cycle 2 F3) | invoke the generator as a library from the test with its artifact declared as a test dependency | WP03 / WP10 T056 |
| ArchUnit / JaCoCo on Java 25 | read Java 25 classes, report, pattern behaviour | PASS | catalog bump (ArchUnit 1.5.1, a later JaCoCo) | WP03 |
| Runner labels (`macos-15`, `windows-2025`, `ubuntu-24.04-arm`) | the first workflow run schedules on them | NOT OBSERVABLE here | name the labels the runners accept in the first run | WP04 first run |
| Verification metadata on other OS | no OS-classified artifact; additive merge | Linux part PASS; other OS NOT OBSERVABLE here | `workflow_dispatch` job that uploads the generated diff; CI never commits | WP04 first run |
| `stampLedger` cost | probe well under the NFR-001 ceiling | PASS (about 5 ms warm over 596 Missions) | design finding (cache of the listing, coarser stamp), escalate; NFR is not weakened | WP03 / phase 2 |
| Empty tag filter | no failure | PASS (Gradle 9.7.1 passes it) | `failOnNoDiscoveredTests = false` if a future Gradle starts failing it | WP03 T012 step 8 |
| Bundle byte-identity | the downloaded `contract-bundle` artifact is byte-identical on the other three legs (macOS, Windows, arm64) | NOT OBSERVABLE here (only the Linux x86_64 result was seen) | mechanism B already makes the digest equal by construction; a divergent leg is a defect to fix before the leg is required | WP04 first run |
| Native build on macOS, Windows, arm64 | `nativeCompile` and the native test binary build and run on each leg, including the MSVC claim of R-5 | NOT OBSERVABLE here (Linux x86_64 only; the MSVC claim is source-reasoned, never run) | name the failing leg and its toolchain gap before the leg is required; no CI-only workaround | WP04 first run |
| Leg timeout budget | each leg's timeout is set from real runner timings | NOT OBSERVABLE here: the Linux 24-core figures (T008 item 6) cannot be used for 4-core runners | take the budget from the first run's per-step times plus a margin, then record it | WP04 first run |

#### Review cycle 2 amendment, 2026-10-11 (WP02, researcher-robbie)

Answers the cycle 1 review (F1 to F5). Same throwaway harness (`<scratch>`, nothing committed), same pinned toolchain (GraalVM CE 25.0.2+10.1, Gradle 9.7.1, Boot 4.1.1, Native Build Tools 1.1.8). No expected value in the Tomcat table or elsewhere is rewritten, and nothing the review accepted is reopened. Where a claim is not observed, it says so.

**F1: native test wiring that keeps the JVM `test` task whole (observed).** The first record's form (b), `tasks.test { useJUnitPlatform { includeTags("native") } }`, is withdrawn: taken literally it makes `./gradlew check` run only native-tagged tests. Tried and failed before the form that works, all observed:

1. A second test binary over the `test` source set (`registerTestBinary("nativeTaggedTest") { usingSourceSet(test); forTestTask(<tagged task>) }`) builds, but the run fails with `ClassNotFoundException: org.springframework.test.context.web.WebAppConfiguration`: the Spring AOT test wiring is attached only to the default `test` binary.
2. Re-registering the default binary (`registerTestBinary("test")`) fails at configuration (`Cannot add a configuration with name 'nativeImageTestCompileOnly' as a configuration with that name already exists`); the default binary's `forTestTask` is not reachable from the DSL (the container hands back a `BaseNativeImageOptions`, not a `TestBinaryConfig`).
3. Pointing only `nativeTestCompile.testListDirectory` at the tagged twin's list builds the image from the tagged list, but `nativeTest` still reads `test/testlist` (unfiltered, 6 ids) and fails with `5 critical issues ... UniqueIdSelector ... could not be resolved`.

The working form, in the build script: `test` stays unfiltered. A `nativeTagged` task of type `Test` over the same `test` classes and runtime classpath carries `useJUnitPlatform { includeTags("native") }` and the system properties `junit.platform.listeners.uid.tracking.enabled=true` and `junit.platform.listeners.uid.tracking.output.dir=<build>/test-results/nativeTagged/testlist` (JUnit's own unique-id tracking listener; without them the twin writes no list, because the plugin only injects them into `test`). Then `nativeTestCompile` gets `dependsOn(nativeTagged)` and `testListDirectory` set to that directory, and the `nativeTest` run task gets the environment variable `JUNIT_PLATFORM_LISTENERS_UID_TRACKING_OUTPUT_DIR` and the runtime arguments `-Djunit.platform.listeners.uid.tracking.output.dir=<same directory>` followed by `--xml-output-dir <build>/test-results/test-native` (the `-D` argument must come first; set after the plugin's default argument it displaced the XML output, and no native XML was written).

Evidence, one build (`./gradlew --offline test nativeTest`, exit 0, 53 s wall, 1-minute load average 10.7 at the start and 18.4 at the end; the test image compile took 46.9 s in an earlier identical-shape run at load about 17). Harness tests: `PlainTest` (untagged), `CanonTest` (untagged, raw-byte golden), `ValidatorTest` (untagged, networknt), `ToolchainTest` (untagged, two ArchUnit rules through `ArchRuleDefinition`, one JaCoCo-covered class), `NativeProbeTest` (`@Tag("native")`, `@SpringBootTest(RANDOM_PORT)`).

| Run | Where | Count |
|---|---|---|
| JVM `test` (unfiltered) | `build/test-results/test/TEST-*.xml` | 6 tests in 5 classes: `PlainTest` 1, `CanonTest` 1, `ValidatorTest` 1, `ToolchainTest` 2, `NativeProbeTest` 1; 0 failures |
| JVM `nativeTagged` (the list writer) | `build/test-results/nativeTagged/TEST-*.xml` and its `testlist` | 1 test (`NativeProbeTest`) |
| Native binary (`nativeTest`) | `build/test-results/test-native/TEST-junit-jupiter.xml` | `<testsuite name="JUnit Jupiter" tests="1">`; the console prints `1 tests found`, `1 tests successful`. A second file `TEST-archunit.xml` with `tests="0"` sits beside it |

So the native count (1) is the tagged subset of the JVM count (6), from one build, and the non-native tests ran on the JVM. The `native-tag-floor` input is the "JUnit Jupiter" suite of `test-native`, as before.

Consequences for WP03: JaCoCo's execution data and the `check` rule stay on `test`, so they cover the whole JVM leg. `nativeTagged` is reached through `nativeTest` (which depends on `nativeTestCompile`), not wired into `check` directly, so the tagged tests are not run a second time on the JVM leg beyond their run inside `test`. The exact build-script lines are the `nativeTagged` task, the `nativeTestCompile` block and the `nativeTest` block described above. NOT shown: the same wiring on macOS and Windows (owed to WP04's first run, FALLBACK table).

**F2: addPathPrefix versus servlet path (observed).** The same bootJar was started twice on a free port and probed with `curl`, reading the counting Host filter's own `FILTER-ENTER` log lines (filter registered on `/*`, highest precedence):

| Configuration | `/nope` | `/api/v1/nope` | `/api/v1/project` |
|---|---|---|---|
| `addPathPrefix("/api/v1", ...)` (no servlet path) | 404, filter entered = 1 | 404, filter entered = 1 | 200, filter entered = 1 |
| `--spring.mvc.servlet.path=/api/v1` | 404, filter entered = 0 | 404, filter entered = 1 | 404, filter entered = 1 |

The servlet-path row confirms the claim: a request outside the servlet path is answered 404 by the container without entering any filter. (Under the servlet path the harness controller still carries its own `addPathPrefix`, so `/api/v1/project` is 404 there from a doubled prefix; that cell is not part of the claim.) DD-57 stands.

**F3: AC-11c's second mutation (observed).** The nested-build test (TestKit, offline, strict verification) now runs both mutations against a copy of the contract. Each relies on a hand-written compile-time reference that WP03 must create, one per mutation:

| Mutation | Hand-written reference that breaks | Result |
|---|---|---|
| (1) rename `blockedCount` in `schemas/MissionHead.yaml` | `new MissionOverview().blockedCount(1)` in a hand-written class (harness: `web/Drift.java`) | fails in 2.5 s, `error: cannot find symbol` |
| (2) remove the required property `currentBranch` from `schemas/Project.yaml` (from `required` and from `properties`) | `new Project().currentBranch("main")` in a second class (harness: `web/ProjectDrift.java`) | fails in 2.1 s, `error: cannot find symbol ... symbol:` |

The unmutated copy still compiles (9.4 s). Finding: the harness had no hand-written reference to `Project` before this run, so mutation 2 would have passed silently; WP03 must add the `Project` reference (a use of at least one required property) next to the `MissionOverview` one, and a reference per required property is cheap insurance. In the real service the references are the mapper and fixture code that build both records; WP03 should not rely on that and keep an explicit drift-probe class for each.

**F4:** the three deferrals owed to WP04's first run are now rows in the FALLBACK table (bundle byte-identity on the other three legs; native build on macOS, Windows and arm64 including the MSVC claim of R-5; the leg timeout budget from real runner timings).

**F5: evidence gaps, disclosed (no decision changes).**
- (a) The SSE negative control without `spring.mvc.async.request-timeout=-1` was not run; the 42 s result in T008 item 2 is a positive observation only. The FALLBACK row now says so.
- (b) The Tomcat table (T007) records status and filter-entered flag per row, not raw request excerpts. Accepted by the review as it stands.
- (c) The 404 for the out-of-scope routes (criterion 8) was observed in a harness with no controllers beyond `Project` and `Missions` stubs. It shows the generator restriction, not the application's routing. WP10 T053 still owns the real proof against the real application; the FALLBACK row keeps that owner.

## WP03 scaffold record (2026-10-11, java-jenny)

Facts recorded while building `services/mission-status-api/` (Linux x86_64, GraalVM CE 25.0.2+10.1, Gradle 9.7.1 through the committed wrapper). Where the WP02 spike record and the WP03 prompt disagreed, the approved spike record was applied; the reconciliations are DD-65 to DD-75 in `traces/design-decisions.md`.

#### Versions and supply chain (R-4)

| Item | Observed |
|---|---|
| Wrapper | `./gradlew wrapper --gradle-version 9.7.1 --gradle-distribution-sha256-sum acd53f1e...d20a` run once with the provisioned Gradle; the first `./gradlew --version` downloaded the distribution and verified the checksum; `gradle-wrapper.jar` SHA-256 `7a9ce74cff467ca1bf60a4fcd9f05185acceda4d0f382434d393e17864262c5d` (pinned by `tests/ci/test_mission_status_api_build.py`) |
| Plugins (catalog) | Spring Boot 4.1.1, `io.spring.dependency-management` 1.1.7, openapi-generator 7.25.0 (equal to `contracts/tools/pins.json`), Native Build Tools 1.1.8 |
| Libraries (catalog) | JaCoCo 0.8.15 (tool version), networknt json-schema-validator 3.0.8, ArchUnit 1.4.2; BOM-managed: Boot starters, `jakarta.validation-api`, SnakeYAML 2.6, JUnit 5, AssertJ. No `spring-boot-starter-validation`, no springdoc |
| Verification metadata | one Linux x64 write run over `check nativeCompile nativeTest nativeSmoke jacocoTestReport openApiGenerate bootJar --refresh-dependencies`: 359 components, 614 `sha256` entries, 160,221 bytes (`verify-metadata` true, `verify-signatures` false). Artifact kinds: 183 jar entries, 98 module, 334 pom, 1 zip. A second from-scratch write run (file deleted first) produced a byte-identical file, so the generation is deterministic on this machine |
| OS or arch classifier | NONE (a grep for linux, osx, windows, aarch, amd64, x86 and arm64 hits nothing). The other three legs run verify-only; a classifier surfacing there is WP04's first-run finding (spike FALLBACK table) |
| Strict check from the committed tree | `git archive HEAD services/mission-status-api` extracted outside the repository and built `--offline` with `-PcontractRoot=<contracts>`: `check` green (17 tasks, 29 s), so nothing the build needs is untracked or ignored |

#### Quickstart run on the skeleton jar (T013 step 5)

Command, exactly the documented one (project root = the lane worktree): `java -jar build/libs/mission-status-api.jar --mission-status.project-root=<project root> --mission-status.port=8787`, then `curl -si http://127.0.0.1:8787/api/v1/hello`:

```text
HTTP/1.1 200
Content-Type: text/plain;charset=UTF-8
Content-Length: 24

mission-status-api hello
```

`curl http://127.0.0.1:8787/api/v1/openapi.yaml | sha256sum` printed `fadf8a869e9402306be3fc0a9fb8f3470b507a21ebfa645f0400d53fc2d0effd` (the bundle digest). `ss -ltn` showed the listener as `[::ffff:127.0.0.1]:8787`. Refusals, same jar: no argument and a blank value print `mission-status.project-root: project root unset (pass --mission-status.project-root=<directory>)`, a missing directory prints `mission-status.project-root: not a directory`; all three exit 1 and print no operating-system message.

#### Native and test counts from ONE build

`./gradlew --offline --rerun-tasks check nativeCompile nativeTest nativeSmoke nativePerf -PnativeBinary=<binary>` (exit 0, 94 s, 29 tasks executed, machine load average about 5 at the start):

| Run | Result |
|---|---|
| JVM `test` (unfiltered except the `native-binary` and `perf` exclusions) | 16 tests in 8 classes: `ArchUnitToolchainSkeletonTest` 2, `HelloRouteTest` 3, `MissionStatusApplicationJsonTest` 2, `ProjectRootCheckTest` 5, `SkeletonContractDocumentTest` 1 and the three `@Tag("native")` classes 1 each; 0 failures |
| JVM `nativeTagJvmTest` (the list writer) | 3 tests; its `testlist` holds the three unique ids |
| Native binary `nativeTest`, `build/test-results/test-native/TEST-junit-jupiter.xml` | `<testsuite name="JUnit Jupiter" tests="3">` (`nativeTagFloor` 3); `TEST-archunit.xml` beside it has 0 tests |
| `kitTest` | `build.VerificationTamperTest` 1 test, about 6 s with the control and the tampered nested build |
| `nativeSmoke`, `nativePerf` with `-PnativeBinary` | 1 test each; without the property the task fails before any test with `nativeSmoke needs the built binary: pass -PnativeBinary=<path to the native executable>` |

The native count (3) is the tagged subset of the JVM count (16); the non-native tests (ArchUnit and the others) ran on the JVM in the same build. `nativeCompile` of the skeleton: the main image is 90,573,896 bytes; `nativeCompile nativeTest` together took 87 s on a lightly loaded 24-core machine.

#### Findings for later work packages

- `@SpringBootTest` needs `classes = MissionStatusApplication.class`: the application class lives in `config`, which is not an ancestor of the test packages, so the upward search for a `@SpringBootConfiguration` fails in `processTestAot`.
- `bootJar`/`processAot` runs `main()` at build time with no project root; the project-root guard therefore does nothing while `spring.aot.processing` is set.
- The repository `.gitignore` ignores every directory named `build` and `out`; source packages `...missionstatus.build` and `...adapter.out` were silently left out of the first commit. The service `.gitignore` anchors its patterns and re-includes both packages; a pin keeps it so.
- `jacocoTestCoverageVerification` rules use `element = "CLASS"` (the pattern syntax WP02 verified), so the 0.90 line and 0.80 branch minimums apply to each class matching the pattern, not to the package aggregate.
- The default gradle `jacocoTestReport` is SKIPPED when no test ran; both JaCoCo tasks now depend on `test` explicitly.

## WP04 workflow record (2026-10-11)

- **Bundling is mechanism B.** A `contract-bundle` pre-job runs `contracts/tools/bundle.py --root contracts --out "$RUNNER_TEMP/bundle-out" --module mission-status --bundle-only` and uploads `bundle/mission-status/openapi.yaml` with a one-line `.sha256` as an artifact. The `jvm` job and the `native` legs download it and export `CONTRACT_BUNDLE` and `CONTRACT_BUNDLE_SHA256`. The gate needs exactly `[jvm, native]`; a bundle failure skips both, so the gate goes red.
- **Action SHAs** were re-verified with `gh api` on 2026-10-11 and all six match the WP02 table: `gradle/actions` v6.4.0 `3f5f9adaf7d9fecd50b5935e54106014257a94e6`, `graalvm/setup-graalvm` v1.6.7 `27b360dbb857524eaf0b4c4cef364d38e5b4f173`, `actions/checkout` v5.0.0 `08c6903cd8c0fde910a37f88322edcfb5dd907a8`, `actions/upload-artifact` v7.0.1 `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`, `actions/download-artifact` v4.1.8 `fa0a91b85d4f404e444e00e005971372dc801d16`, `astral-sh/setup-uv` v10.0.1 `20cfd1bf945f4377ade1205e4dbc17946fc9a30d`.
- **Python on the legs** is the runner's own, standard library only, with no setup-uv. The step is written out literally twice, `python3` for non-Windows and `python` for Windows, because `test_no_duplicate_suite_execution` cannot see a `${{ matrix.python }}` command word.
- **Provisional timeouts:** `contract-bundle` 10, `jvm` 45, `native` 90, gate 10 minutes. These are unmeasured until the first CI run.
- **Strict verification** runs verify-only on all four legs, Linux x64 included, so AC-14c has an exit status for every leg.
- **Fleet verdict:** `scripts/ci/fleet_verdict.py::PR_WORKFLOWS` rejects any unregistered `pull_request` workflow, so plan E-3 could not hold. The operator ruled to register the workflow (reviews/analyze.ruling.md, 2026-10-11).
- **Owed to the first CI run** (slice-1 PR):
  - the runner labels exist;
  - setup-graalvm works on every leg, including MSVC on Windows;
  - per-leg wall-clock for the native compile, which sets the final timeouts;
  - the bundle artifact on the other legs;
  - `./gradlew` and `-PnativeBinary` under Git Bash on Windows;
  - strict-verification outcomes per leg (AC-14c);
  - the AC-14b negative wrapper run;
  - a tag push skips the path filter (WP15);
  - a schedule run with all jobs skipped shows as skipped.
