# Research: Reject invalid forced status rewinds before append (#6514)

Grounding for the mission. Everything below was measured on `main` @ `35318ef51c`
(the mission's base commit) in this clone, not recalled from documentation.

## 1. The defect, measured

Driven through the real CLI (`agent status emit` → `agent status validate`), on a
fixture mission seeded `planned` and advanced `claimed → in_progress → for_review`:

```
$ spec-kitty agent status emit WP01 --to in_progress --actor codex \
    --force --reason "source boundary changed"
exit 0
stdout: {"event_id": "01M68J63NCYKK6X90EG8HYNE6K", "wp_id": "WP01",
         "from_lane": "for_review", "to_lane": "in_progress", "actor": "codex"}
log rows: 4 -> 5
appended row: {"wp_id":"WP01","from_lane":"for_review","to_lane":"in_progress",
               "force":true,"reason":"source boundary changed","review_ref":null}

$ spec-kitty agent status validate --mission 017-test-feature
exit 1
{"passed": false,
 "errors": ["Event 01M68J63NCYKK6X90EG8HYNE6K: for_review->in_progress without review_ref"]}
```

Two facts matter for the fix: the append *happened* (the log is append-only, so the row
is permanent), and the row carries `review_ref: null` — the writer never asked for it.

## 2. Why the two authorities disagree

| Authority | File | What it says about `for_review → in_progress` |
|---|---|---|
| Auditor | `status/validate.py::validate_event_schema` (line ~147) | `review_ref` must be present, unconditionally |
| Writer | `status/wp_state.py::ForReviewState.allowed_targets` | `{in_review, blocked, canceled}` — the backward edge does not exist |
| Writer | `status/wp_state.py::WPState.check_transition` | no structural edge ⇒ only `ctx.force` can admit it ⇒ `_check_force` = actor + reason, nothing else |

So the edge is **force-only**, and the force gate checks nothing but audit fields. The
auditor's rule has no counterpart on the write path: the writer and the auditor are
allowed to disagree by construction. That is the whole defect.

## 3. What `move-task` already does — and the second hole found while pinning it

`move-task` recognised this edge earlier, by a different route: a forced
`for_review → in_progress` rewind supplies a `review_ref` sentinel.

```python
# src/specify_cli/cli/commands/agent/tasks_transition_core.py:330
elif old_lane == Lane.FOR_REVIEW and resolve_lane_alias(target_lane) in (Lane.IN_PROGRESS, Lane.PLANNED) and force:
    emit_review_ref = "force-override"
```

`force-override` is a recognised operational sentinel
(`review/cycle.py::REVIEW_FEEDBACK_SENTINELS`), so it is an auditable pointer, not a hole.

**But that branch reads the operator's `--force` flag, not the plan's final force decision.**
`move-task WP01 --to in_progress` **without** `--force` is auto-promoted to a forced
re-*wind* further down (`emit_force = not (legal_force_free and wire_allows_force_free)`),
*before* the reason is rewritten to `backward rewind: …`. Measured on the pre-fix tree:

```
$ spec-kitty agent tasks move-task WP01 --to in_progress --mission <slug>
exit 0
last row: {"from_lane":"for_review","to_lane":"in_progress",
           "force":true,"reason":"backward rewind: for_review -> in_progress",
           "review_ref":null}
```

So the second generic write path produced the identical invalid row — the issue names only
`agent status emit`, and the ratchet test
`test_unforced_non_done_backward_move_is_unchanged` asserts the lane move and the force
bit but never the pointer, which is how it stayed invisible. This mission therefore fixes
both: the shared rule refuses the row, and `build_transition_plan` now supplies its own
already-established sentinel whenever it *emits* force on this edge, so the surface that is
supposed to conform actually does. Code change:
`src/specify_cli/cli/commands/agent/tasks_transition_core.py` (WP01).

The two generic doors (`agent status emit`, `orchestrator-api wp transition`) pass the
caller's `--review-ref` straight through, including `None`. They are the doors the rule
closes.

Every other producer of a lane event was surveyed for this edge and none emits it:

- `status/work_package_lifecycle.start_review_status` moves `for_review → in_review` only.
- `lanes/recovery._get_recovery_transitions` never emits from `for_review` (its
  progression ceiling is `in_progress` and `for_review` is not in `_PROGRESSION`).
- `consolidation/*` attestation and bookkeeping requests never target `in_progress` from
  `for_review`.
- `status/bootstrap.py` seeds `genesis → planned`.
- `review/arbiter.py` supplies its own `review_ref`.

## 4. Where the fix belongs

Three candidate seams were considered.

**(a) `ForReviewState.guard_for`.** Rejected: force bypasses the guard entirely.
`wp_state.py` states the rule explicitly — *"guards must NOT consult `ctx.force`"* — and a
guard-only refusal would be dead on the forced path, which is the only path this edge has.

**(b) `status/transition_pipeline.prepare_transition`, next to `_refuse_unnoted_review_exit`.** Workable: it is
the tree's only per-emit `validate_transition` call, and it is pure, so no partial state.
But it would leave the FSM able to admit the edge for any caller that reaches
`validate_transition` directly (the batch door, recovery, the orchestrator). It fixes one
door's furniture, not the aggregate.

**(c) `WPState.check_transition`, with the fact shared with the auditor.** Chosen. The FSM
is already the sole authority for edge legality and force override (`transitions.py` is an
explicit thin delegator; `validate.py::_edge_is_legal` already routes to
`wp_state_for(...).may_transition_to`). Putting the requirement there means every writer
inherits it, and putting the *predicate* in one place means the auditor reads the same
fact rather than restating it. Precedent: `genesis` is already a force-insurmountable
target refusal evaluated inside `check_transition`.

## 5. Decisions taken (and what was deliberately not decided)

| # | Decision | Rationale |
|---|---|---|
| D-1 | Refuse; do not auto-fill a sentinel. | The issue's expected behaviour is "reject the transition unless `--review-ref` is non-empty, even when `--force` is used", and the operator brief is "reject invalid forced status rewinds before append". Manufacturing a pointer the operator did not give would record a review reference that does not exist. `move-task`'s `force-override` sentinel is a deliberate, named, auditable choice of *that* command; it is not a licence for a generic door to invent one. |
| D-2 | The requirement is force-insurmountable. | Force's contract is "override guards and missing edges with actor + reason for audit". It is not "produce an event the tool's own validator rejects". |
| D-3 | Keep the historical non-force refusal text. | A force-free attempt on this edge is refused by the structural check today with `Illegal transition: for_review -> in_progress`. Changing that text would be an unrelated behaviour change; the new message only appears on the force path, where nothing was refused before. |
| D-4 | No new CLI flag, no new command. | `--review-ref` already exists on both doors and is already the documented pointer. |
| D-5 | No byte-rewriting repair, and no new repair command in this mission. | Event-sourced consumers must be able to trust history (C-002). The issue asks for the *documented* position on rows already written; shipping an unreviewed history mutator would be a far larger blast radius than a P2 ledger hole. Recorded as the honest limit in `docs/architecture/status-model.md` and in the PR's `## Deferred`. |
| D-6 | `in_review → in_progress` is out of scope. | It is a *different* edge: structurally allowed, guarded by `_check_review_result`, with its own #5446 force-note rule. Widening the requirement to it would change a legal transition — a force-policy change the issue did not ask for and the operator's ruling did not authorise. |
| D-7 | When `move-task`'s own plan emits force on this edge, fill its existing `force-override` sentinel. | Discovered while pinning the ratchet: the auto-promoted backward move wrote `force=True, review_ref=null`. Refusing it outright would break a documented operator move; supplying the sentinel the command already uses for the explicit-`--force` form of the same move keeps one vocabulary and makes the event valid. This is not the D-1 anti-pattern — `force-override` is `move-task`'s declared semantic for "the operator rewound over a review", not an invented pointer. |

## 6. Supersession check

Not superseded, and not previously filed as fixed:

- `git log -S "for_review->in_progress without review_ref"` → only the three commits that
  introduced and delegated the auditor rule (`1bce5f07e0`, `b0d2e147de`, `321e42ca56`).
- #5446 (`a83d5db354`) gated forced exits from `in_review`/`approved` on a note. It
  explicitly does not touch the `for_review` edge, and its own tests seed the
  `in_review → in_progress` shape directly.
- #3307 (wire-contract `review_ref` on review-rollback edges) fixed the *wire*, on the
  `move-task` path, by supplying the pointer — the same conclusion this mission reaches
  for the generic door, by refusing instead of inventing.
- No ADR under `docs/adr/` addresses this edge.

## 7. Blast radius

The predicate is consulted by `check_transition` (all admission) and by
`validate_event_schema` (all audit). Callers of `check_transition`/`transition_to`:
`transitions.validate_transition` (every emit door), `move_task._plan_transition` (asks
force-free legality), `transition_pipeline.prepare_transition` (the emit door), and the
FSM tests. Because the new requirement applies only to edges listed in
`REVIEW_REF_REQUIRED_EDGES`, and only one edge is listed, the observable change is
confined to a forced `for_review → in_progress` with a blank `review_ref`.

## 8. Pre-existing reds cited (not caused by this mission)

`#6798`, `#6801`, `#6816`, `#5927` are open reds on `main` that can appear in CI on any
head. They are cited in the PR's `## Deferred` and were not touched or worked around.