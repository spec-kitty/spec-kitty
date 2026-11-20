# Research: API-claimed and canceled WPs reach acceptance

All line references are to `origin/main` `996f5d6a`.

## R-01 Reproductions (witnessed)

Rebuilt from the issue bodies of #5781 and #5818. Each was run against the editable install at `996f5d6a`, with a throwaway `HOME`.

- `repro_5781.sh lanes`, API arm: `accept-mission` returns `MISSION_NOT_READY`, `outstanding.metadata = ["WP01: missing agent in canonical runtime state (never claimed; run ... --to approved --agent <name> ...)"]`. The named repair exits 1. The `--force` repair succeeds, but `accept-mission` then refuses with `evidence_error_codes = ["REVIEW_NOT_INDEPENDENT"]`. The host-claimed twin accepts.
- `repro_cancel_variants.sh`:
  - **X** (host cancel with `--agent` and `--note`): host accept passes; API `incomplete_wps=["WP02"]`.
  - **P** (host cancel with `--note` only): host accept reports "missing agent ... --to canceled"; API `incomplete_wps`.
  - **V** (API `transition --to canceled --note`): host accept reports "missing agent"; API `incomplete_wps`. `canceled_wps` lists WP02, so an API cancel with a note already carries operator provenance.
  - **C** (control, both approved): both accept.

## R-02 Root causes (verified)

- **RC1**: `acceptance/summary_core.py:111-131` reads the snapshot `agent` slot, with `implementer_of_record` as the fallback. Both are filled only from the `planned -> claimed` event's `policy_metadata["agent"]`. Host claims build that key with `status/emit.py:257` `claim_policy_metadata`. The API passes the raw `--policy` dict (`orchestrator_api/wp_lifecycle.py` `_start_implementation` -> `start_implementation_status(policy_metadata=policy_dict)`). API `transition --to claimed` passes the same raw dict, and `agent status emit` (`cli/commands/agent/status.py:503`) passes no `policy_metadata` at all.
- **RC2**: the gate demands an agent in every lane. Only assignee and shell_pid are scoped to active lanes.
- **RC3**: the hint formats `--to {bucket_lane}`. No lane's `allowed_targets()` contains itself (`status/wp_state.py`), so the printed command can never run.
- **#5818**: `orchestrator_api/consolidation.py:943-958` hard-codes `{APPROVED, DONE}`.
- **#7644**: API `transition --to planned` emits no `release_runtime_claim` annotation; only `move-task` emits one (`tasks_move_task_hops.py:555`).

## R-03 Decisions

- **D-01, the gate authority.** `review_roles.latest_implementer_identity(transitions, wp_id)` (operator ruling 1). `_collect_snapshot_wps` already holds `event_stream.transitions`, so no extra read is needed (NFR-001). Rejected: filling the slot through a migration. That would be a second authority and would need a data rewrite.
- **D-02, display.** `metadata["agent"]` keeps the slot value and falls back to the implementer identity. The gate never reads it. Rejected: switching the display to the full identity, which would change existing `accept --json` values for host-claimed WPs.
- **D-03, the hint.** `review_roles.implementer_claim_target(lane)` returns a lane in `{claimed, in_progress}` that is in `wp_state_for(lane).allowed_targets()`, provided the source is not a reviewer source lane (`for_review`/`in_review`/`approved`). Exits from those lanes need a `review_ref`, and the projection reads them as rework verdicts, never as claims. The command is chosen per target:
  - `claimed` -> `spec-kitty agent action implement WP --agent <name>`
  - `in_progress` from `claimed` -> `agent action implement`
  - `in_progress` from `blocked` -> `spec-kitty agent tasks move-task WP --to in_progress --agent <name>`

  With no target, no command is printed.
- **D-04, the claim sidecar.** `claim_policy_metadata(shell_pid: int | None, agent, *, extra=None)`. With `shell_pid=None` the pid keys are omitted; the API has no live shell. `extra` merges first, so the claim keys win. The host callers are unchanged. This is the one shape #7407/#5735 inherit.
- **D-05, the release.** The new `status/claim_release.py::planned_claim_release_delta()` returns `WPInnerStateDelta(release_runtime_claim=True, review=<empty ReviewOverride>)`. `move-task` keeps its dict additions, built from the helper's fields; the API passes the delta as `annotation_delta` on the `planned` TransitionRequest, which the pipeline emits atomically (`transition_pipeline._annotation_for_request`).
- **D-06, #5818.** `mission_terminal_acceptability(snapshot.work_packages, expected_wp_ids=all_wp_ids)`: the existing provenance-aware aggregate, failing closed on an absent WP.
- **D-07, #7752.** Not folded. It needs a "done or acceptably canceled" predicate; `approved` must fail post-merge. That is not the helper this Mission produces.
- **D-08, the done-bookkeeping reviewer fallback** (`consolidation/done_bookkeeping.py:399`). Today it records the agent slot as the reviewer. With FR-004, API WPs fill that slot with the implementer. The fold reads the actor of the WP's latest `approved` transition, falling back to `unknown`.
- **D-09, the contract.** `CONTRACT_VERSION` goes from 1.29.0 to 1.30.0, a minor bump. Nothing is removed or renamed.

## R-04 Supply chain

No dependency is added or changed (DIRECTIVE_051: not applicable).
