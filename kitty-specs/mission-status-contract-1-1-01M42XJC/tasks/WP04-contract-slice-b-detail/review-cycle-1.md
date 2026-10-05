---
affected_files: []
cycle_number: 1
mission_slug: mission-status-contract-1-1-01M42XJC
reproduction_command:
reviewed_at: '2026-10-04T14:42:58Z'
reviewer_agent: claude
wp_id: WP04
---

# WP04 review (Renata): VERDICT: changes requested

Commits 9e43b1acc, 9c6708500, 95f02e8bd, 18a72eacc: all `commit` per cat-file; 9758a5cd5 and aef7cc967 too.

## Findings
- F1 (severity 3, blocks): `ReviewCycle.feedbackReference` pattern `^review-cycle://[^/\\\s]+/[^/\\\s]+/review-cycle-[1-9][0-9]*\.md$` is wider than `validate_review_cycle_pointer` (which uses `assert_safe_path_segment`: ASCII only, no leading dot, no `..` substring, must start alphanumeric). Run against both, these all match the schema and all fail the validator: `review-cycle://../x/review-cycle-1.md`, `review-cycle://a/.hid/review-cycle-1.md`, `review-cycle://a..b/x/...`, `review-cycle://é/x/...`. A traversal-shaped pointer is schema-valid. The brief requires agreement with the validator. Remedy: segment class `[A-Za-z0-9][A-Za-z0-9._-]*` plus a negative lookahead for `..` (or equivalent), then re-pin with planted examples.
- F2 (severity 2): `Workspace.planningBranch` is a plain string with no maxLength and no pattern. Matches the spec ("string or null"), and the strict-field leak scan covers it. Unbounded and could carry `-`-leading text. This is safe only if WP06 never passes it to git. Suggest a maxLength.
- F3 (severity 1): the `laneBranch` pattern `^[A-Za-z0-9][A-Za-z0-9._/-]*$` (max 255) has no leading `-` and admits no path leak. It still admits `..`, `//` and a trailing `/`, which git refuses. Harmless, because the value is produced by `lane_branch_name`. `laneId` (max 64, alphanumeric start) is fine for real ids such as `lane-a` and `lane-planning`.
- F4 (severity 1): CHANGELOG Provisional bullets are right. `reviewCycles`, `workspace`, both schemas, `WorkPackageDetailRefusalCode`, `WorkPackageDetailRefusal` and `code` are named, plus `kind` of `ArtifactReference`. `provisional_check` reports 22 elements.

## Verified OK
- Additive only: the only modified files are the 4 `_index` files, `openapi.yaml` (one path key), `CHANGELOG`, `enum_pins.json` and two tests. `breaking_check` against baseline aef7cc967 (oasdiff 1.32.1 installed with the verified checksum, in scratch) gives breaking=0. No `src/` diff. `_shared` is byte-identical. No `/home`, username or email, no NUL byte in added lines.
- Spec conformance: required fields, all arrays required, no embedded `WorkPackage`, `ChangeState` and refusal codes exact, 404/500 `if`/`then` pairing present. Duplicate-id rule is in the path, `WorkPackageDetail`, 404 response and CHANGELOG text. Closed schemas: an extra property in an example is rejected.
- Citations: `citation_check` exit 0, symbols resolve. CITATION_REUSE for `AuthoredGroup` (15) and `ResolvedGroup` (17) is legitimate. `AuthoredGroup` really holds subtasks, dependencies and owned_files, and `ResolvedGroup` holds the resolved states. WP04 adds 6 and 2 uses, none of them wrong. No mis-citation is hidden.

## Gates (all exit 0 unless noted)
- The ten contract checks pass. Counts: examples=74, enums=7 values=43, leak_scan files=1061 artifact_path=35.
- Tool-job selection: 1258 passed, 37 skipped. Reality, payloads, round_trip and leak_scan: 903 passed.
- Router, registry and architectural batch: 562 passed, 1 skipped.
- ruff check, `ruff format --check` (3103 files) and TID251: clean.
- cutover-guard: 0 un-cut-over.
- `run_negative_cases` x3 with fresh `--work` dirs: cases=127 ran=94 skipped=33 passed=94 failed=0 each time.
- Zero reds, so nothing to classify as introduced.

## Revert experiments (mine, each restored with `git checkout -- <literal file>`; tree clean afterwards)
- E1: planted `sneaky` property in the populated example. `example_check` EXAMPLE_INVALID, and the pytest examples test fails.
- E2: `Workspace` additionalProperties set to true. 2 tests fail (closed-schema test and the `workspace-extra-property` planted case); `example_check` stays green, so the tests carry it.
- E3: the 500 pairing changed to 404. `example_check` and pytest both fail on `source-unreadable`.
- E4: `unknown` dropped from `ChangeState`. `example_check` fails and `enum_pin_check` gives ENUM_VALUE_REMOVED.
- E5: `artifactReferences` removed from required. 1 pytest failure.
- All 5 were killed, so no vacuous tests were found.
