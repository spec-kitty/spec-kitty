# Contract notes: how the service consumes the in-repo contract

No file under `contracts/` is edited (C-001). This note records which operations this mission serves and the clarifications it leaves for the next contract touch. It contains no YAML fence on purpose (every fenced yaml block of `kitty-specs/*/contracts/*.md` is collected by the contract-example round trip test).

## Consumed operations

Added by this mission, generated from the split root `contracts/mission-status/openapi.yaml` and bundled unchanged at build time (the build checks the bundle digest):

- `getMission`
- `getWorkPackage` (with and without `includePrompt=true`)
- `getWorkPackageDetail`
- `listArtifacts`
- `getArtifactContent`

The overview operations of #5529 are unchanged.

## Error statuses

Every non-2xx body is the shared Problem (`contracts/_shared/responses/Problem.yaml`). The per-route detail texts are fixed by the oracle goldens (D-P8-4 and the named `ProblemMapper` edits of WP13 to WP16). A problem body carries no path, no value and no enum name.

## Generated model deviation

`sizeBytes` of the artifact listing is widened to `Long` by a scoped post-generation step in `build.gradle.kts` (WP16, cycle 2). The contract text is unchanged.

## Clarifications for the next contract touch (recorded, not edited; C-001)

- `ArtifactPath`: the pattern accepts U+FFFD, but the service refuses a path holding it (the path cannot be told apart from an undecodable name).
- Known divergences V1 to V26 between the Python oracle and the service are listed in `services/mission-status-api/README.md` and in the conformance manifest. They are behaviour differences, not contract changes.
