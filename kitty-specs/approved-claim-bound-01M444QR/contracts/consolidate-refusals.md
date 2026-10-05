# Contract: consolidate refusals added by this mission

All three are REFUSE verdicts. At claim time they exit 1 before any branch moves, under the existing header `Reconciliation refused (fail-closed) at claim time, before any change:`. At the gate they exit 1 and the run is rolled back through the existing rollback authority. "Reconciliation verified" is not printed.

| Code | When | Names | Remedy stated | Attestation lifts it |
|---|---|---|---|---|
| `LANE_MOVED_AFTER_APPROVAL` | a code lane holds a non-merge commit, not reachable from an approval stamp or an anchor, that touches a non-bookkeeping path; a commit of a canceled work package of the lane counts like any other | lane, branch, approved work packages, up to three short SHAs, one path | move the work package back for review, then re-run | no |
| `APPROVAL_STAMP_MISSING` | a work package in the approved claim has no approval stamp | work package, lane | re-review, or `--attest-approved-reviewed <WP> --attest-reason "..."` | yes, for that work package |
| `APPROVAL_STAMP_NOT_ON_LANE` | an approval stamp is neither the lane tip nor an ancestor of it | work package, lane, branch, short stamp | move the work package back for review, then re-run | no |

## Compound messages

When a mixed-lane or canceled-dependency refusal stops the claim, the first message also carries the refusals of this contract that apply. The first refusal is printed unchanged, then a blank line, `This Mission also has:`, the refusal block(s) of this contract, a blank line and one sentence saying both parts need their own fix, in either order. Every canceled work package that refuses is named in the first part, one per line. A missing approved lane branch, an unreadable canceled dependency lane, an unmaterializable status surface and an unreadable event log stand alone: later checks cannot be computed without them. A canceled-dependency refusal is shown with the approval-stamp refusals; a mixed-lane refusal on the same Mission is shown on the next run. The gate stops at its first refusal and rolls back, so it never prints two. Refusals of different phases are still shown one per run: before the claim, flag validation, review-artifact consistency, merge-state and resume checks, terminal readiness, the merge gates, the hollow-review prompt and the dirty-checkout and protected-branch preflights; after it, one gate verdict per run. Only the claim-time refusals are compounded.

## CLI

```
spec-kitty consolidate --mission <handle> --attest-approved-reviewed <WP> [--attest-approved-reviewed <WP> ...] --attest-reason "<why>"
```

- Requires `--attest-reason`.
- Refused, with nothing recorded, when the work package is not in the approved claim, when its newest approval is a stamped review approval, or when it was attested before and its lane has since moved past that attestation.
- With `--dry-run` nothing is recorded and a notice says so.

## orchestrator-api consolidate-mission

Returns the existing `PREFLIGHT_FAILED` envelope; the first code of the text is reported as `data.preflight_error_code` and every distinct code it names as `data.preflight_error_codes` (orchestrator-api contract 1.10.0). This path only raises the codes of this contract, so the list can hold several of them when lanes refuse for different reasons; it never receives a compound message. No lane is consolidated. The command has no attestation flag. For `APPROVAL_STAMP_MISSING` only, its message says so and points to `spec-kitty consolidate`.

## Unchanged

Every existing refusal code and text, the mixed-lane closed-world verdicts, the rollback authority's caller set and the "Reconciliation verified" texts.
