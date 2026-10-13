# Analyze phase: operator decisions (2026-10-10)

The analysis was recorded with verdict `ready` in commit 073426bde: 0 high, 3 medium and 12 low findings. Every finding gets one fix session.

- **ANL-002, tamper test.** A standing CI test. WP03 commits an automated tamper test that runs in the service's `check` on CI. AC-14a stays as written.
- **ANL-005, E-7 container rows.** Amend the specification. AC-9b's closed 400 list (set 2) gains the three values Tomcat decides itself:
  - a duplicate `Host` header;
  - HTTP/1.1 without `Host`;
  - an HTTP/1.1 absolute-form foreign target with an accepted `Host`.

  These three rows stop being provisional. The other E-7 rows (the filter-decided 403s) keep their interim status.
- **ANL-013, PR shape.** Five stacked slices:
  1. WP01-WP04
  2. WP05, WP17, WP06, WP18
  3. WP07, WP08, WP19, WP09
  4. WP10, WP20, WP11
  5. WP12-WP16
- **ANL-014, toolchain.** Installed locally, with no system packages: GraalVM CE 25.0.2, from the sha256-verified release tarball, and Gradle 9.7.1, from the sha256-verified distribution. The service build still uses its committed wrapper.

Other dispositions:

- **ANL-011:** the legacy noun is reworded when history is compacted before the PR.
- **ANL-012:** the matrices are populated through the CLI at accept.

## 2026-10-11: JaCoCo floors apply per class (DD-70)

Operator ruling: keep WP03's `element = "CLASS"` rules. Every class matched by `org.speckitty.missionstatus.domain.*` must reach LINE >= 0.90 and BRANCH >= 0.80, and every class matched by `org.speckitty.missionstatus.application.*` must reach LINE >= 0.90. This is stricter than the package wording of NFR-006 and plan section 5. It is a plan deviation alongside E-6, and no minimum is lowered. WP05, WP06, WP17 and WP18 must test every class in those packages to the floor.

## 2026-10-11: register the workflow in the fleet verdict (supersedes E-3)

Found by WP04: `scripts/ci/fleet_verdict.py` keeps a closed `PR_WORKFLOWS` set and raises "PR workflow inventory changed" for any unregistered workflow with a `pull_request` trigger. The new workflow turned 26 tests in `tests/ci/test_fleet_verdict.py` and `tests/ci/test_fleet_main.py` red, and after merge it would fail the verdict job on every PR. Dropping the `pull_request` trigger would break AC-15a.

Operator ruling: register it. WP04 adds `mission-status-api.yml` to `PR_WORKFLOWS`, adds the workflow name to `ci-fleet-verdict.yml`'s `workflow_run.workflows`, and updates the two tests. Plan E-3 is superseded. Spec AC-15d gains the exception. WP04's owned_files gain the four paths, and WP16's docs text changes to match. State it in the slice-1 PR for the maintainer.

## 2026-10-11: gradlew line endings on Windows (WP04 review F1)

Operator ruling: option (b). Add `services/mission-status-api/.gitattributes` with `/gradlew text eol=lf` (and `*.bat text eol=crlf`, Gradle's own convention). This fixes the file in the repository for every checkout, not just CI. It is folded in at the slice-1 wrap-up together with F2 (stale fleet-verdict header comment in the workflow) and F3 (label the provisional timeouts). The file sits under `services/mission-status-api/**`, inside WP03's owned tree.

## 2026-10-11: three domain rulings from the WP05 review

1. **Annotation rows reach the reducer as their own line kind.** `LedgerLine.kind` gains `Annotation(wpId)`, and data-model.md is amended. An annotation-only WP counts in `wpTotal` and in the progress denominator, but in no lane count, as in the oracle. WP05 adds the kind and the reducer path in its fix round. WP17's codec produces it.
2. **An unparseable stream cursor text is refused as `400 misaligned`,** with a detail text saying the cursor did not parse. The contract is not changed. This applies to WP06 and WP10.
3. **Page size is clamped at both ends.** A value above 200 becomes 200, which the contract allows ("may apply a smaller maximum"). A value below 1 becomes 1. No 400 is added. This applies to WP06 and WP10.

Also corrected in data-model.md, with no ruling needed because the oracle is the reference: the fold dedups by `event_id` in file order and then sorts (`diary.reduce_parsed`), while the cancellation-provenance and implementer projections sort first and then dedup (`reducer.py` `_project_*`). WP05's projections had used the fold's order, which diverged from the oracle for a duplicate id with a different `at` (WP05 review F2). An earlier wording of this note said the whole reduction sorts first; WP05's fix round ran the oracle and showed that only the projections do (DD-81).

## 2026-10-11: rulings from the WP06 review

1. **Unknown Mission id next to an unusable Mission stays fail-loud** (operator). While any Mission's `meta.json` is unusable, or its path is refused, a Mission-scoped request for an id that matches no readable Mission answers by the first such fault. A path refusal (L9) gives 404 with `path_refused`. An unusable `meta.json` (L7) gives 500 `meta_unparseable`. An unreadable directory gives 500 `mission_dir_unreadable`. A plain 404 is given only when no such Mission exists. Added to spec FR-004.
2. **A correction to my own WP07 ruling on the stream cursor invariant** (orchestrator, the oracle decides). I ruled that the invariant is the digest of the last consumed non-blank terminated line. The WP06 reviewer ran `tail_reader` on `{"a":1}\n\n`: `validate_resume_cursor` and `poll_once` accept the digest of the last terminated line of any kind, the blank line included, and reject the non-blank digest with `content_mismatch`. The correct rule is therefore the last terminated line, blank included. WP06's code is right. WP06 adds a test for a ledger ending in a blank line and corrects the `FixtureMissions` comment. The manifest's blank-line text (WP07) is reworded at wrap-up.
3. **Unusable rows are a separate malformed reason** (orchestrator, single remedy from AC-3b(iii) and L3a). A well-formed JSON object that is not a usable row is a new `MalformedReason.UNUSABLE_ROW`: a missing required key, an unknown lane or an unknown `kind`. The request routes are unchanged, because every reason still gives `ledger_unparseable` (L3a). On a stream, the row is skipped and the connection stays open, as Python's `poll_once` does (AC-3b(iii)). Non-JSON, non-object and blank lines still close the stream (L10/S4).
4. **`StatusEvent` carries an `Actor`** (orchestrator, single remedy from the contract's required `StatusTransitionEvent.actor`). The actor is decoded with `decode_actor` semantics in the codec. It is needed by WP20.

WP06's owned_files are widened to `domain/model/**`, `domain/oracle/**` (tests) and `adapter/out/filesystem/codec/**`, so that one fix round makes items 3 and 4 across the WP05 and WP17 code. The plan now records that `MissionStatusService` takes the leak-class value and builds its own `ProjectionCache`.

## 2026-10-12: coordination routing needs a `coordination_branch` (WP08 review F1)

Operator ruling: match the oracle. The resolver routes to the coordination folder only when `meta.json` holds a non-empty string `coordination_branch`. This applies even when the stored topology is `coord` or `lanes_with_coord` and the coordination Mission folder exists. Without a `coordination_branch`, the Mission's own folder is read, as `resolve_read_dir` does. Three real Missions in this repo have that shape; no coordination folders exist for them, so there is no live effect today. WP08 fixes this in its next round. WP09 adds the case to the golden resolver table (`resolver-cases.json`).

## 2026-10-12: WP19 review rulings (operator)

1. **Diagnostic code for unusable meta contents and for a missing project slug: keep the Java codes and record them.** A `meta.json` that parses but cannot populate the Mission logs `meta_unparseable`. A missing or unusable `project.slug` logs `mission_dir_unreadable`. The oracle logs `projection_refused` for both, but the status and the Problem body are the same. This is recorded in FR-004, with no code change.
2. **Large integers: document the 32-bit limit.** A `mission_number` beyond 31 bits is L7 (500), where the oracle serves it with 200. A `schema_version` beyond 31 bits is served as null, where the oracle serves the integer. The contract is not changed. This is recorded in FR-004, and WP19 corrects the javadoc, which wrongly says the contract carries a 32-bit integer.
3. **A missing `created_at` is refused (L7).** The oracle would serve `createdAt: null`, which is not valid against the contract. This is recorded in FR-004.

## 2026-10-12: coordination routing, corrected to the full oracle rule

The earlier ruling today ("route to COORD only when `coordination_branch` is a non-blank string") rested on a probe whose coordination folder held no `meta.json`. The operator's choice was to match Python. An investigation found that the full oracle rule has one more condition. It ran a real `git init` repo, with a registered worktree and a husk, on the current `src`, which is identical across main, lane-a and lane-b. The routing code is `src/specify_cli/coordination/surface_resolver.py:1352-1369` (husk authority) and `:1436-1439` (the `coordination_branch` check), and `src/specify_cli/missions/_read_path_resolver.py:396-417`.

The oracle rule, for a stored coord-routing topology (`coord` or `lanes_with_coord`) with the coordination Mission folder present, registered or husk:
- If the coordination folder holds a `meta.json`, the read directory is COORD, whatever `coordination_branch` holds.
- If the coordination folder has no `meta.json`, the read directory is COORD only when `coordination_branch` is a non-blank string. Otherwise it is OWN.

This applies the operator's "match Python" choice exactly, so no new ruling is needed. The resolver needs only to STAT the coordination folder's `meta.json`, never read it. A stat reads no file content, so the allowlist gains a stat-only class. WP07 adds oracle-generated resolver cases for both shapes. WP08 is reopened to make the resolver follow this rule.

## 2026-10-12: a non-integer `pageSize` is treated as absent (operator, WP10 review)

`/missions?pageSize=abc`, `1.5` or any other non-integer value is treated as if `pageSize` were absent, so the default page of 50 is served. This matches the earlier ruling that page size gets no new 400, and the contract's only 400 on `/missions` is the page-cursor refusal. Integers beyond 32 bits saturate and then clamp: values above 200 become 200, and values below 1 become 1.

## 2026-10-12: `lastEventId` is projected strictly on every route (operator, WP20 review F2)

`lastEventId` on `GET /missions` and `/project` goes through the same strict projection as `eventId` on the stream. A path-, email- or token-shaped value is handled like any other strict field: it is nulled where the contract allows null, and refused with `projection_refused` otherwise. This closes an AC-9g leak path and makes the JSON routes agree with the stream. It is a recorded divergence from the oracle, which never projects `lastEventId`; real ledgers carry ULID event ids, so no real data triggers it.

The fix is an out-of-map edit of WP06's `MissionStatusService.projected`, made in WP20's fix round. WP20's canary scan gains an `event_id` canary on the JSON routes.

The orchestrator also ruled on WP20 review F1: the three skeleton native tests are deleted with the skeleton package in WP12. The native-tag count is then 3 (WP20's real tests), and the workflow `--floor 3` stands.

## 2026-10-12: NFR-001 ratio limits tightened (operator, WP13 review F1)

The warm p95 ratio limit is about 40 and the cold-call limit about 90, so an injected 50 ms delay turns the check red, as the WP13 revert row requires. There is only about 1.5x headroom over the local worst. Under ADR 2026-10-05-2 a CI miss is classified as runner noise and the limit is amended from the measurement; it is never retried. The first CI run re-measures.

## 2026-10-13: pre-merge squad rulings (operator)

1. **`acceptedAt`, `mergedAt` and `discardedAt` are projected strictly and are nullable.** A value that is not an instant, or that is shaped like a leak, is served as null. A junk value then cannot flip `lifecycleStatus`. This diverges from the oracle on purpose, the same way `lastEventId` does (DD-110).
2. **Actor handles are projected strictly and are nullable.** A `tool`, `role` or `profile` shaped like a token, path or email is served as null on the stream.
3. **`.kittify` must resolve inside the project root.** A symlink pointing outside is refused and handled the same as an unusable project config. This diverges from the oracle on purpose.
4. **Supply chain.** The release job gets GitHub build-provenance attestation: one pinned action, with job-level `id-token: write` and `attestations: write`. Dependency verification stays checksum-only, trusted on first use. That choice is recorded as deliberate, with no PGP key management for now.

The orchestrator also ruled these single-remedy squad findings:
- `EventData` must parse `at` and `timestamp` as instants. An unparseable value drops the event and writes one `projection_refused` diagnostic.
- Spring config is pinned to the classpath only, and `spring.web.resources.add-mappings` is false.
- Every `readRegular` call takes a required size cap: 1 MiB for `meta.json` and `lanes.json`, and a documented cap for the ledger, which maps to L2.
- Concurrent SSE connections are capped by `mission-status.stream.max-connections` and refused with a Problem.
- The Tomcat HTTP/1.1 parser log level is raised to WARN.
- The NFR-004 heap measurement uses the median of several GC-settled samples.
- `perfTest` stays in `check`; the limits are recalibrated from the first CI run.
