# Research: plan-phase decisions

Pre-spec findings are in [research/code-grounding.md](research/code-grounding.md).
This file records the decisions taken while planning.

## R-1 Refuse, or land the approved tip and drop the later commit

- **Decision**: refuse.
- **Rationale**: fail-closed and consistent with every other gate verdict; dropping a commit silently would hide work from its author.
- **Alternatives considered**: merge the approval stamp instead of the branch name. Rejected: it changes the physical merge for every mission and discards tool-made merges the lane needs.

## R-2 Where the reader lives

- **Decision**: a new `consolidation/approved_bound.py` that imports the public stamp readers from `wp_attribution.py`.
- **Rationale**: `wp_attribution.py` is scoped by its docstring to one canceled work package of one mixed lane; the status package must stay git-free.
- **Alternatives considered**: a reader in `status/` (needs git for the ancestry check); extending `resolve_canceled_wp` (wrong subject, and it would push that function past its complexity).

## R-3 Lane-level bound, not per-WP windows on every lane

- **Decision**: lane-level, with "commits reachable from no covered point".
- **Rationale**: per-WP windows on every lane bring every closed-world anchor hazard to missions that have no canceled work package, with unknown real-world refusals.
- **Alternatives considered**: closed world on all lanes. Deferred as a named residual.

## R-4 Mixed lanes

- **Decision**: the check runs after the existing mixed-lane resolution and treats a canceled work package's latest stamp as a covered point.
- **Rationale**: the closed world already refuses a stray commit on a mixed lane with its own text; counting the canceled work package's commits as "after approval" would change existing verdicts.
- **Alternatives considered**: skip mixed lanes entirely. Rejected: an unstamped approval on a mixed lane would pass.

## R-5 Gate re-check source

- **Decision**: at the gate, compare each live lane tip with the tip validated at claim time, using only SHAs captured before the run mutated anything as references.
- **Rationale**: lane branches still exist at the gate (teardown is later); a commit added during the run is on the live tip whether or not it was merged, and refusing either case is correct. Re-running the claim-time check with live branch names would pass vacuously, because the mission branch then contains the merged lanes (post-tasks review, finding 1).
- **Alternatives considered**: compare the `done` event's landed-tip stamp to the bound. Rejected: it adds a second reader of a different stamp. Re-run the claim-time check unchanged. Rejected: vacuous, as above.

## R-6 Attestation shape

- **Decision**: a forced operator self-transition carrying `attestation = "approved_reviewed"`, read by the same `approval_stamp` function.
- **Rationale**: no voiding rule is needed; ordering in the append-only log decides, and the pipeline's own stamp bounds the attestation in time.
- **Alternatives considered**: reuse `--attest-canceled-superseded` (requires a canceled work package); store the attestation outside the status log (second authority).

## R-7 Orchestrator path

- **Decision**: call the lane check before the first lane merge and report the code in the `PREFLIGHT_FAILED` envelope.
- **Rationale**: confirmed from source that the code-lane path (`orchestrator_api/consolidation.py:447-460`) merges without a claim; the planning-only path already goes through `_run_lane_based_consolidation`.
- **Alternatives considered**: route the code-lane path through the executor. Out of scope: a larger behaviour change with its own rollback questions.

## R-8 Dependencies

No dependency is added, upgraded or removed; the supply-chain checks do not apply.
