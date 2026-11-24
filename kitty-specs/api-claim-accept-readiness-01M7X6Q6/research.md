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

## R-05 Residual found in WP01 review (cycle 1)

`spec_kitty_events.diary.reduce_parsed` folds every annotation after every transition, so a `release_runtime_claim` annotation also clears the `agent`/`shell_pid` slots that a LATER claim's sidecar set (#7794, minimal reproduction in the issue). Since WP01, an `orchestrator-api transition --to planned` emits that release (#7644), so after an API rollback the next claim, API or host, shows no live holder in the reduced snapshot. `move-task --to planned` has had the same consequence since #2512. The claim event still records its agent, and the implementer of record is right, so acceptance is unaffected.

The fix belongs in `spec-kitty-events` (C-001). The intended outcome is pinned as strict `xfail`s in `tests/orchestrator_api/test_api_claim_sidecar_5781.py` (`test_after_an_api_rollback_the_new_claim_holds_the_agent_slot`, `test_after_an_api_rollback_the_host_re_claim_holds_the_live_claim_slots`). Keeping the release (parity with `move-task`, the #7644 contract) was preferred over withholding it until the events fix: withholding would keep a stale holder and pid bound after every API rollback, the defect #7644 reports.

## R-06 Post-consolidation adversarial squad (R24), finding dispositions

Three independent read-only lenses reviewed the aggregate diff: correctness/regression, orchestrator-api contract/single authority, and test quality/non-vacuity. None found a HIGH correctness defect. All findings were folded except those noted.

| Finding | Severity | Disposition |
|---|---|---|
| The host re-claim strict xfail XPASSes on origin/main: the API release is new on this path, so the next host claim's live slots now read empty (#7794) | HIGH (test lens) | Labelled accurately as a regression of this path in the xfail reason and the PR. Whether to keep the release until #7794 ships is with the operator (dispatcher escalation); no unilateral change. |
| No-command repair text read "none can be recorded" | MEDIUM | Folded: "it must go back for rework and be claimed by a named agent". |
| Docs, skill and docstrings still said accept-mission needs every WP approved/done | MEDIUM | Folded: docs/api, SKILL.md, the contract reference, the command docstrings; the CLI reference and completion manifest regenerated. |
| Matrix auto-verification (`populate_criteria_from_review_evidence`) still required every WP approved/done, so a descoped Mission's `code_review` rows stayed pending | MEDIUM | Folded at first, then **reverted** after the PR-level review (#7797) reproduced the folded version marking scope that only the canceled WP owned as `pass`, citing other WPs' reviews: matrix criteria carry no WP mapping, so the two cannot be separated. `main`'s behaviour is restored and pinned by a test (rows stay pending for an explicit `acceptance-verdict`). Follow-up: #7798. |
| The success payload did not name canceled WPs | MEDIUM | Folded: additive `canceled_wps` field (contract 1.30.0), documented and tested. |
| The `tests/utils.py` fixture seeds a claim for every lane past `claimed` | MEDIUM | Folded: `seed_claim=False` escape hatch, documented. |
| The trio stub could not tell the implementer from the slot | MEDIUM | Folded: a discriminating wiring test. |
| A test inspected `co_names` | MEDIUM | Folded: replaced with a behavioural comparison of the move-task and API release deltas. |
| Missing coverage: generic actors, canceled-after-claim, the `doing` alias, the ownership guard on API claims | MEDIUM | Folded: unit and integration tests added. |
| `implementer_claim_target` raised on an unknown lane | LOW | Folded: returns `None`. |
| Builder and release docstrings overstated their reach | LOW | Folded: made accurate (move-task shares the key-shape builder; its rollback also resets subtasks). |
| `status_lanes.mission_terminal_acceptability` docstring consumer list | LOW | Folded. |
| The hand-back `release_runtime_claim` in the executor looks like a second release | LOW | Folded: comment points to the shared release. |
| xfails could pass on any exception; "unforced" never asserted | LOW | Folded: `raises=AssertionError`; `force is False` asserted. |
| `test_acceptance_support` re-pin docstring | LOW | Folded. |
| The printed repair can still meet dependency/workspace gates in real use | LOW | Accepted: those lanes are already not acceptable, and the gate prints the only claim the state machine allows. Recorded here. |
| The raw `--actor` stored as `agent` differs from the parsed event actor for compact actors | LOW | Accepted: same as host claims (`effective_actor`); the ownership guard compares tool keys. Recorded here. |
| `--policy` claim keys are dropped silently | LOW | Accepted: documented in the builder and contract 1.30.0; no envelope warning added. |
