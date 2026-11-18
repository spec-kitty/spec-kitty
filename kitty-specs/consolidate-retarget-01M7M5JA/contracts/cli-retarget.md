# Contract: `spec-kitty consolidate` retarget

## Flags
| Flag | Requires | Meaning |
|---|---|---|
| `--retarget` | `--target <b>` | Adopt `<b>` as the Mission's recorded target for this run and record it. |
| `--retarget-reason "<why>"` | `--retarget` | Reason recorded in the provenance. Default: `operator retarget via spec-kitty consolidate --target <b> --retarget`. |

Misuse (`--retarget` without `--target`, or `--retarget-reason` without `--retarget`) is a usage error: exit 2, nothing moves.

## Error codes (CLI and `--dry-run --json` `error_code`)
| Code | When | Moves anything? |
|---|---|---|
| `TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE` (existing) | plain `--target` differing from the record (unchanged; its next step now also names `--retarget`) | no |
| `PROTECTED_BRANCH_REFUSED` (existing) | `<b>` is protected (#6464), or the re-pointed #5385 probe refuses | no |
| `RETARGET_RECORD_UNWRITABLE` (new) | neither the Mission branch nor `<b>` carries the Mission's `meta.json`; or `<b>` carries it but the root checkout is not on `<b>`, or `meta.json` there is untracked, dirty or skip-worktree | no |
| `RETARGET_WRITE_BRANCH_IS_RECORDED_TARGET` (new) | a `single_branch` commit-to-target Mission: its write branch is the recorded target, so the work is already there and a retarget would make consolidate delete that branch | no |
| `RETARGET_RESUME_MISMATCH` (new) | the run record persisted a retarget `from -> to`, and this run's target is not `to`, with or without `--retarget` (`--target <from>` included; mission review RISK-1). `orchestrator-api consolidate-mission` refuses every persisted retarget with this code (`PREFLIGHT_FAILED`, `data.preflight_error_code`) | no |

## Dry-run JSON
A retarget forecast adds `"retarget": {"from": "<old>", "to": "<b>"}`.

## orchestrator-api
`consolidate-mission` has no retarget. A differing target keeps `PREFLIGHT_FAILED` with `data.preflight_error_code = TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE`. `CONTRACT_VERSION` is unchanged.

## Attestations
`--attest-*` under a retarget follow it (operator ruling, option A). On a Mission without a coordination branch, the attestation status events land on `<b>`, not on the old target, and they are undone with the run: a failure inside the rollback door, or `--abort`, leaves `<b>` at its pre-run tip (mission review RISK-2). A coordination branch is unaffected.
