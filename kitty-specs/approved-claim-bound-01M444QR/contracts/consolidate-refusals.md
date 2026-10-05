# Contract: consolidate refusals added by this mission

All three are REFUSE verdicts. At claim time they exit 1 before any branch moves, under the existing header `Reconciliation refused (fail-closed) at claim time, before any change:`. At the gate they exit 1 and the run is rolled back through the existing rollback authority. "Reconciliation verified" is not printed.

| Code | When | Names | Remedy stated | Attestation lifts it |
|---|---|---|---|---|
| `LANE_MOVED_AFTER_APPROVAL` | a code lane holds a non-merge commit, not reachable from a covered point or an anchor, that touches a non-bookkeeping path | lane, branch, approved work packages, up to three short SHAs, one path | move the work package back for review, then re-run | no attestation of an approved work package; a canceled-superseded attestation on a mixed lane exempts lane commits up to its own stamp (ADR 2026-09-29-1), see the residual in the ADR |
| `APPROVAL_STAMP_MISSING` | a work package in the approved claim has no approval stamp | work package, lane | re-review, or `--attest-approved-reviewed <WP> --attest-reason "..."` | yes, for that work package |
| `APPROVAL_STAMP_NOT_ON_LANE` | an approval stamp is neither the lane tip nor an ancestor of it | work package, lane, branch, short stamp | move the work package back for review, then re-run | no |

## CLI

```
spec-kitty consolidate --mission <handle> --attest-approved-reviewed <WP> [--attest-approved-reviewed <WP> ...] --attest-reason "<why>"
```

- Requires `--attest-reason`.
- Refused, with nothing recorded, when the work package is not in the approved claim, when its newest approval is a stamped review approval, or when it was attested before and its lane has since moved past that attestation.
- With `--dry-run` nothing is recorded and a notice says so.

## orchestrator-api consolidate-mission

Returns the existing `PREFLIGHT_FAILED` envelope; the code is reported as `data.preflight_error_code` (orchestrator-api contract 1.10.0). No lane is consolidated. The command has no attestation flag. For `APPROVAL_STAMP_MISSING` only, its message says so and points to `spec-kitty consolidate`.

## Unchanged

Every existing refusal code and text, the mixed-lane closed-world verdicts, the rollback authority's caller set and the "Reconciliation verified" texts.
