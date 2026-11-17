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
| `RETARGET_WITH_ATTESTATION_UNSUPPORTED` (new) | `--retarget` with `--attest-*` on a coordination-less Mission (its status surface is the old target) | no |
| `RETARGET_RESUME_MISMATCH` (new) | `--resume --target X --retarget` names an X other than the persisted retarget | no |

## Dry-run JSON
A retarget forecast adds `"retarget": {"from": "<old>", "to": "<b>"}`.

## orchestrator-api
`consolidate-mission` has no retarget. A differing target keeps `PREFLIGHT_FAILED` with `data.preflight_error_code = TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE`. `CONTRACT_VERSION` is unchanged.
