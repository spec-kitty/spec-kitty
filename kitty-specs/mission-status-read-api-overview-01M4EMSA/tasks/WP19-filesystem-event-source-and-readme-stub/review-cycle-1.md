---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-12T07:43:08Z'
reviewer_agent: reviewer-renata
wp_id: WP19
---

# WP19 review cycle 1: returned for folds (reviewer-renata, operator rulings)

The full evidence is in wp19-review-verdict.md (orchestrator scratchpad). The reviewer approved with no blocker:
- tail/stamp parity on 484 new byte patterns (18,980 offsets);
- `PyText.isBlank` matches `str.strip` on every code point;
- the torn-tail test is deterministic;
- the allowlist flow, README parity and HEAD reads all pass.

The operator ruled on F1 to F3 (no code change except a javadoc fix; see the end of reviews/analyze.ruling.md, spec FR-004 and DD-102). The folds below are single-remedy and are made now, before WP09 builds goldens on this adapter.

| id | severity | where | problem | remedy |
|---|---|---|---|---|
| F2-doc | low | FilesystemMissionEventSourceMeta.java:114-121; FilesystemMissionEventSourceProject.java:152-154 (javadoc) | The javadoc says the contract carries a 32-bit integer, but the contract fields are plain `integer`. | Reword it: the service carries these fields as 32-bit integers by decision (FR-004, 2026-10-12). A `mission_number` beyond 31 bits is L7, and a `schema_version` beyond 31 bits is null. No behaviour change. |
| F4 | low | FilesystemMissionEventSourceProject.java:112-136 (`loadSucceeds`) | It misses the `parse_iso` TypeError cases: a non-string `initialized_at`, `last_upgraded_at` or migration `applied_at`. The oracle serves `specKittyVersion` null; Java serves the recorded version. | Fail the load when one of those three values is truthy and not a `String`. Add cases with expected values from running the oracle, and a revert row. |
| F5 | low | FilesystemMissionEventSourceProject.java:247-256 (`utf8()`, used at :180 and :217) | A BOM is stripped for HEAD and the `.git` pointer, which the oracle does not do, so a BOM-prefixed HEAD gives null in the oracle. | Strip the BOM only for the YAML reads. Add oracle-backed cases for a BOM-prefixed HEAD and pointer, and a revert row. |
| F6 | low | rule 7 coverage | The recorder only sees reads through the seam, so a direct `java.nio.file.Files` read in the adapter passes the flow test and `check` (the reviewer's M21 survived). | Add a new ArchUnit test class in YOUR owned test tree (`adapter/out/filesystem` tests), not in `architecture/` (WP18's file). In `..adapter.out.filesystem..` main code, only `AllowlistPassThrough` may depend on `java.nio.file.Files`, `java.nio.channels.FileChannel` and the `java.io` file classes; also allow `ProjectRootCheck` if it sits there. Exclude the codec sub-package if needed. Add a positive control (a planted class is caught) and show M21 now red. |
| F7 | info | FilesystemMissionEventSource.java:60-64 (`readMeta`) | No size cap on `meta.json`. | Cap the read, like the 1 MiB YAML cap, and map an oversize file to L7. Add a test. Document in the javadoc that the stamp scan cost is bounded by the length of the last line. |
| F8 | info | FilesystemMissionEventSourceTornTailTest.java:130-165 (`awaitReads`) | Unbounded spin on a non-daemon thread. | Use a daemon thread and a bounded spin that fails with a clear message. |
| F9 | info | FilesystemMissionEventSourceProject.java:197-216 | Pointer containment is lexical, so a pointer through an out-of-root symlink to an in-root directory reads that in-root HEAD. | Contain by real path: resolve the gitdir with `realPath` through the seam, and refuse when the real path is inside the root. Add a test and a revert row. Also add one sentence to the README threat note. |
