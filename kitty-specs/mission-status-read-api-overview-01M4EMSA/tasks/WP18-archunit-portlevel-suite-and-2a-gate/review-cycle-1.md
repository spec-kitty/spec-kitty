---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-11T17:22:11Z'
reviewer_agent: reviewer-renata
wp_id: WP18
---

# WP18 review cycle 1: REJECT (reviewer-renata)

The full evidence is in wp18-review-verdict.md (orchestrator scratchpad). The build, the rule set, the controls, non-vacuity, the AC-4a rows and the interim machinery are sound. Every finding has a single remedy inside WP18's owned tree.

| id | severity | where | problem | remedy |
|---|---|---|---|---|
| F1 | medium | conformance/port/Ac2bPagingTest.java (`pageSizeOneYieldsEveryMissionOnceInContractOrder` fixtures) | AC-2b cannot tell an instant sort from a text sort: every `createdAt` in the fixture sorts the same both ways. With `MissionOrder` mutated to compare text, both AC-2b port tests stayed green. | Add a Mission whose offset `createdAt` reverses the text order, for example `2026-09-05T10:00:00+02:00` next to `2026-09-05T09:00:00+00:00`. Show that the text-sort mutation now turns AC-2b red. |
| F2 | medium | conformance/port/Ac3ResumeAndBatchTest.java (`cursorAfterRow`, class Javadoc); testsupport/PortFixtures.java (`cursorAfter`) | The expected cursors of AC-3g and AC-3i are read back from the code under test, although the Javadoc says they are not. With the digest made consistently wrong in `LedgerLineDecoder.sha256Hex` and `StreamCursor.digestOf`, AC-3g and AC-3i stayed green. | Compute each expected cursor in the test from the raw fixture text. The offset is the UTF-8 byte length of the prefix. The invariant is the SHA-256 of the last terminated line, blank included (DD-92), computed with `java.security.MessageDigest` directly in the test, not through production code. Delete `cursorAfter` and fix the Javadoc. Show that the digest mutation now turns AC-3g and AC-3i red. |
| F3 | medium | architecture/ArchitectureRules.java, `NO_GENERATED_AOT_TEST_CLASSES` (`location.contains("/aotTest/")`) | The substring can match anywhere, so a production class in a package named `aotTest` drops out of every main rule. A planted `domain/aotTest/PlantB` using `ConcurrentHashMap` passed all 12 rules. | Anchor the match to the Gradle output directory, `/classes/java/aotTest/`, and handle Windows separators if the location can contain them. Add a control: a class in a package named `aotTest` is still scanned and caught. |
| F4 | low | architecture/PortLevelClassSetTest.java (`topLevelPortClasses`) | The AC-13b equality looks at the exact package `conformance.port` only, so a stray class in a sub-package is not reported. | Compare every class whose package equals `PORT` or starts with `PORT + "."`. Add a revert row. |
| F5 | low | conformance/port (AC-5a beta progress) | The reviewer's oracle run gives beta's weighted progress as 44.99999999999999, and the test expects 45.0. | Confirm the test asserts the value as the oracle SERVES it, after the payload's rounding or rendering. Cite the Python line that rounds, and assert the rendered text if that is the served form. If the served Python value differs from Java, report it; do not change production code. |

Notes for WP09, with no action here: WP09's reflection test must assert that the class `PortLevelInterim` is absent. When the phase 3 launcher lands, rule 11b should be tightened to forbid any `adapter..` dependency.
