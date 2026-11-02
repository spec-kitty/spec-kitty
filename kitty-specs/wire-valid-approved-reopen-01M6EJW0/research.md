# Research: Wire-valid approved reopen (#6955)

Merge base: `main` @ `9aed3a8012cb5eb22c0128b14d525039f95fea7a`. Pinned wire contract:
`spec-kitty-events` 11.3.0 (`spec_kitty_events.status`).

## R1 — Does the issue still reproduce on current main?

Yes, through both authorities the `move-task` decision core calls. Probe (the production
planner `build_transition_plan`, exactly what `move-task --to in_progress` invokes on an
approved WP with no `--review-feedback-file`):

```
plan(approved -> in_progress, force=False, no feedback pointer) =
  TransitionPlan(canonical_lane='in_progress', transition_targets=['in_progress'],
                 emit_force=True,
                 emit_reason='backward rewind: approved -> in_progress',
                 emit_review_ref=None)
wire validate_transition(same payload) -> valid=False
```

Writer probe (`wp_state_for(<lane>).check_transition(IN_PROGRESS, force+actor+reason)`,
the check every door reaches before an append) versus the pinned wire contract on the same
pointerless forced payload:

| edge | local writer | local `requires_review_ref` | wire `validate_transition` |
|---|---|---|---|
| `for_review -> in_progress` | refused (missing `review_ref`) | True | invalid |
| `in_review -> in_progress` | **accepted** | False | **invalid** |
| `approved -> in_progress` | **accepted** | False | **invalid** |

So the reported edge is the live `move-task` repro, and `in_review` is the same divergence
one edge over — the writer accepts a payload the contract rejects.

## R2 — What exactly does the pinned contract require?

`spec_kitty_events/status.py`, "Review-Ref-Gated Rewind Family" (v11.3.0):

> Three backward rewinds to `in_progress` form a second, separate family. They are
> force-exempt and gated on `review_ref`: `for_review -> in_progress`,
> `in_review -> in_progress`, `approved -> in_progress` … `review_ref` MUST be a non-empty
> string, whether the event is forced or not. A missing or blank `review_ref` is invalid
> even when `force=True`.

Measured (payload rebuild + `validate_transition`) on `approved -> in_progress`:

| `force` | `review_ref` | valid |
|---|---|---|
| True | `None` | **False** |
| True | `review-cycle://…` | True |
| True | `force-override` | True |
| False | `None` | **False** |

`force-override` is a member of `specify_cli.review.cycle.REVIEW_FEEDBACK_SENTINELS`
(`{"force-override", "action-review-claim", "workflow-review-claim"}`) and resolves through
`resolve_review_cycle_pointer` to a structured "sentinel" result — never to a fabricated
artifact.

## R3 — Is the conforming shape already emitted anywhere?

Yes, on the same hop, from the other door. `status/work_package_lifecycle.py:417-452`
(`start_implementation_status`, reached by `agent action implement`) covers
`_REVIEW_LANES = {for_review, in_review, approved}` and passes
`review_ref="force-override"` with the comment "keeps the event valid without inventing a
feedback pointer that does not exist". `build_transition_plan`'s #6514 fill already stamps
the same sentinel on the forced `for_review -> in_progress` rewind. `move-task`'s approved
arm is the only writer that leaves it `None`.

## R4 — Is it superseded or already decided elsewhere?

- No merged PR or ADR fixes it: `git log -S"_is_approved_reopen"` shows only #6845's
  landing work (`c18c800d57`, `d3e60abf5e`), which deliberately kept the missing-reference
  arm forced (engineering note `docs/plans/engineering-notes/2026-10-31-approved-reopen-feedback.md`:
  "a missing reference retains its documented forced behavior and is never described as
  force-free").
- #6514 fixed only `for_review -> in_progress` and its spec (`C-003`, § Edge Cases)
  deliberately left `in_review`/`approved` alone because the local auditor did not flag
  them — the gap the shared contract exposes and this mission closes.
- Issue option (b) ("re-pin the wire contract") is a `spec-kitty-events` change; the
  events surface is frozen in core (ADR `2026-10-29-1`, charter 2026-11-01) and the pin is
  consumed, never edited (`C-001`).
- Issue option (a) ("refuse every bare approved reopen") would delete the FR-015 arm #6845
  preserved; it needs a maintainer ruling this issue does not carry, and it is unnecessary
  because the contract admits a forced rewind that cites the sentinel (R2, R3).

## R5 — Blast radius on stored logs

Committed mission logs on the merge base hold 91 rows on the family with
`review_ref: null` (e.g. `mission-status-read-api-overview-01M4EMSA`,
`common-docs-consolidation-01KW3Q6M`, `unified-charter-bundle-chokepoint-01KP5Q2G`).
The auditor will begin reporting them, exactly as #6514 accepted for its edge. No CI step
runs `status validate` over the committed corpus (`grep -rn "status validate" .github/
scripts/ Makefile` → no hits), so this is an operator-facing verdict, not a gate. History
is never rewritten (`C-003`); the reference documents the append-only correction route.

## R6 — Where the one definition is read

`REVIEW_REF_REQUIRED_EDGES` (`src/specify_cli/status/wp_state.py`) is read by:

- `WPState.check_transition` — the force-insurmountable refusal before any append (all
  doors: `move-task`, `agent status emit`, `orchestrator-api wp transition`);
- `status.validate.validate_event_schema` — the auditor;
- `build_transition_plan` — the sentinel fill for an emitted forced rewind.

One frozenset, three consumers, no second copy (`C-004`).

## R7 — A pre-existing regression sits on the same edge (found during grounding)

Running the mission's own target suite on the merge base shows two reds that have nothing to
do with this mission's diff:

```
$ uv run pytest -q tests/integration/test_owned_reopen_feedback.py
FAILED ...test_owned_approved_reopen_feedback_contract[provided]
FAILED ...test_owned_approved_reopen_feedback_contract[empty]
2 failed, 4 passed
```

Both fail with `Cannot move WP01 from 'approved' to 'in_progress' with
--review-feedback-file: this edge writes no review cycle`. Cause: `_feedback_edge_recordable`
(#6699, commit `aa99d50f74`, committed 2026-11-02T09:21Z) admits review-rejection edges and
the approval lanes only, so the approved reopen is classified non-recordable and refused
before `_guard_feedback_file`'s own approved-reopen arm can read the file.

Chronology (verified, not assumed): `aa99d50f74` is an ancestor of the #6845 landing fix
`d3e60abf5e` (13:35Z), so the guard was already in the tree when that landing pass amended
this very test. The pass re-ran the fast gate only, and this contract test is
`@pytest.mark.integration` + `git_repo`, so the arm shipped broken and nothing caught it.
The #6699 test matrix lists `for_review -> in_progress` as non-recordable and never mentions
`approved -> in_progress`, so the regression is unpinned as well.

The approved reopen does record the supplied file — it becomes the event's `review_ref`
(`build_transition_plan`'s `review_feedback_pointer` arm) — so #6699's own premise says it is
recordable. The restore is folded into this mission (`FR-004`) rather than deferred: the
mission's evidence arm cannot be stated honestly while it is broken, and the same test file
carries both halves.
