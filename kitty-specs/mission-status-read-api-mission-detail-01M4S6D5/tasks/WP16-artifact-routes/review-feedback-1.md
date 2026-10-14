# WP16 review, cycle 1: REJECT (one finding)

Reviewer: reviewer-renata. Tip reviewed: ca559c89b. Every read-safety attack, the OO-2 split, the gates and three mutations passed; the single finding is a silent wrong value.

## F1 (severity 3): `sizeBytes` is clamped to 2147483647 silently

- Where: `services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/ArtifactMapper.java:44-50` (`size()`), pinned as correct by `ArtifactMapperTest.java:77`.
- Contract: `contracts/mission-status/schemas/ArtifactEntry.yaml:24-27` and `ArtifactContent.yaml:46-48` say `type: integer`, `minimum: 0`, with NO `format` and NO `maximum`. The contract does not cap the value at 2^31-1; the 32-bit limit is an artifact of the generator's default `Integer` mapping.
- Failure scenario (reproduced): a 3 GiB sparse file `huge.bin` in a Mission directory is listed with `"sizeBytes":2147483647` (true size 3221225472). The listing answers 200, with `readable:false`, and nothing says the number is wrong. The oracle serves the true size.
- Remedy (either, then record a D-entry):
  1. Serve the true value: map `integer` to `Long` for these two members (generator `typeMappings`/schema-level override in `build.gradle.kts`, or write the member through a Long-typed field), and change the mapper test to assert the true size for a > 2^31 entry. This needs no contract change.
  2. If the generated type cannot change in this WP, refuse instead of lying: a listing entry above 2^31-1 bytes answers 500 `artifact_listing_unreadable` with one path-free diagnostic, and declare it a knownDivergence entry (oracle serves the true size) in the same commit.
  Do not keep the silent clamp. Option 1 is preferred.

## Notes (no action required by this WP)

- The lane's `kitty-specs/.../traces/tooling-friction.md` holds seven `# Tracer: tooling friction` headers and 55 duplicate lines from the three dependency-lane merges (d83513a20, 982e4f7c7, 9fad37406). This is orchestrator integration (obligation 10), not WP16 authored content. Dedupe at merge.
- `perfTest` `Nfr001OverviewLatencyTest` failed once (ratio 71.15 vs limit 70) while another Gradle run shared the host (load 9); green when rerun alone. Classified as load, not code.
