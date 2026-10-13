---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-11T10:58:49Z'
reviewer_agent: reviewer-renata
wp_id: WP02
---

# WP02 review: rejected (cycle 1), reviewer-renata

This is a narrow rejection. Every fact that could be re-derived checked out: the 8 action SHAs, the Gradle and GraalVM checksums, and the bundle digest fadf8a86…0effd. The spike is largely sound. Fix F1 to F4 and note F5. All of the fixes are edits to research.md, or a re-run in the scratch harness.

## F1 (severity 4): the "tag filter on `test`" native wiring does not say how the JVM leg keeps its other tests
Location: T008 item 5(b), "Decisions consumed" item 7, DD-58, and the FALLBACK row "Native test wiring".

`tasks.test { useJUnitPlatform { includeTags("native") } }` taken literally makes `./gradlew check` run only native-tagged tests. ArchUnit, the goldens, networknt and the JaCoCo rule must all run in `check` on the JVM leg (plan line 21, and section 11 "Native test partition"). The record itself shows TEST-archunit.xml with tests="0".

Remedy: run the build (or state a mechanism that is proven by a run) so that the JVM `test` count and the native count show side by side from the same build. Either keep `test` unfiltered and give the native binary a separate Test task or an NBT-only filter, or fall back to the proven dedicated source set, form (a). Then rewrite decision 7, DD-58 and the table row to match.

## F2 (severity 3): the addPathPrefix-over-servlet-path rationale is stated as observed without evidence
Location: T005 "Extra FINDINGS", first bullet, and DD-57.

Remedy: either record the observation in the Tomcat-table style (the filter-entered flag for `/nope` under servlet-path versus under addPathPrefix), or mark the claim explicitly as source-reasoned rather than observed. The decision stands either way.

## F3 (severity 3): AC-11c's second mutation was not exercised
Location: T004 item 10 and T005.

AC-11c requires two mutations: (1) renaming a MissionOverview property, and (2) removing a required property of Project. Only the rename was shown.

Remedy: run, or state, the removal mutation. Name the hand-written compile-time reference in WP03 that each mutation relies on.

## F4 (severity 2): the deferrals owed to WP04's first run are not all in the FALLBACK table
Remedy: add three rows, each owned by "WP04 first run":
1. bundle byte-identity on the other three legs;
2. native build on macOS, Windows and arm64, including the MSVC claim from R-5;
3. the leg timeout budget, taken from real runner timings, because the Linux 24-core figures cannot be used directly.

## F5 (severity 2): smaller evidence gaps (disclose them; no decision change)
- (a) The SSE negative control without the property was not run. Say so where the 35 s result is cited.
- (b) The Tomcat table has no raw-request excerpts. This is acceptable as it is.
- (c) The 404 for out-of-scope routes was observed in a harness with no controllers. WP10 T053 still owns the real proof; keep that statement.
