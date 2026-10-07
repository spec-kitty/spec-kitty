# Research: composition-advance-alignment

## R-1 Grounding

- Decision: close the gap by routing the composition advance through `engine.plan_advance` / `commit_advance` (operator ruling: a specified behaviour change).
- Rationale: `GROUNDING.md` §"#2562 design-spike finding" shows that the adapter's planner runs only `apply_result` + `plan_next`. A composition-backed advance therefore records no `SignificanceEvaluated` event and no `raci:` record.
- Alternatives considered:
  - Keep the parallel planner and add the two calls to it. Rejected: that keeps two planning authorities, which goes against the charter's single-canonical-authority principle.
  - Behaviour-preserving dedup only. Rejected by the operator ruling.

## R-2 Post-spec adversarial squad (2026-10-06, advisory)

Two lenses ran: consumer impact (reviewer-renata profile) and design invariants (architect-alphonso profile). Each finding's disposition:

| # | Lens | Severity | Finding | Disposition |
|---|------|----------|---------|-------------|
| 1 | both | BLOCKER/MAJOR | The adapter unit tests (`test_bridge_engine.py:341-640`, `test_bridge_decision_log_flush.py:359-400`) stub `_planner.plan_next` with an `object()` template. `plan_advance` reads neither, so these tests crash. | **Folded.** Spec US3 now allows re-seaming them onto a real minimal frozen template with every assertion kept. Each re-seam is listed in the PR. |
| 2 | design | MAJOR | A `complete_run(emit)` hook could drop or duplicate `MissionRunCompleted`. | **Folded.** The hook becomes `before_run_completed: Callable[[], None] \| None`, an abort-only guard. The engine always emits. The non-blocking capture runs after `commit_advance` returns (FR-008 wording). |
| 3 | design | MAJOR | A malformed significance block now blocks a composition advance (EDGE-003). | **Folded.** It is an edge case in the spec and is named in the FR-012 changelog entry. This matches the engine path. |
| 4 | design | MINOR | `plan_composition_advance` would forward to `plan_advance` (C-003). | **Folded.** It is deleted together with `CompositionAdvancePlan`, and the bridge calls `_engine_adapter.plan_advance(..., "success")`. |
| 5 | design | MINOR | Symbols become dead: the `apply_result` wrapper, `_mark_step_completed`, `_live_template_path` and the payload imports. | **Folded.** They are deleted in IC-03. The `_append_event` / `_write_snapshot` wrappers are kept (pinned by the six-wrapper test). |
| 6 | design | MINOR | The legacy path catches `StaleAdvancePlan` and falls back to `runtime_next_step`; that must not be copied here. | **Folded.** The FR-010 test asserts that `runtime_next_step` is never called. |
| 7 | consumer | MINOR | A run paused at a MEDIUM gate from before this change can mismatch: it holds approve/reject options and no significance record. | **Recorded residual** (spec edge cases). The composition path never re-polls a pending decision, so this mission does not reach that state. |
| 8 | consumer | MINOR | `DecisionGitLog` committed content changes for MEDIUM/LOW gates. | **Folded.** It is an edge case in the spec and is named in the changelog. |
| 9 | consumer | NOTE | Answered records gain `raci_source`, which nothing outside the engine reads. No contract changes (events, Decision, orchestrator-api `CONTRACT_VERSION` 1.10.0). | No action. C-005 holds, so no escalation to the orchestrator. |
| 10 | design | NOTE | Q1: `StaleAdvancePlan` cannot fire spuriously, because nothing writes `state.json` between plan and commit. | No action; the analysis is recorded. |
| 11 | design | NOTE | The legacy and composition strict gates differ on refusal: the composition path leaves `NextStepAutoCompleted` in the log, while the legacy path rolls back. | Out of scope (preserved deliberately); named under the PR's Deferred section. |
| 12 | design | NOTE | Emitter seeding could reuse `plan.source`. | Kept as `_read_snapshot` to preserve today's behaviour exactly; this is a NOTE only. |
| 13 | design | Q7 | Proposed split of `provide_decision_answer`. | **Adopted** as the IC-01 helper map. |

No finding needs an operator decision beyond the ruling. Both lenses confirm that C-005 holds.

## R-3: Post-tasks squad (planner-priti lens, 2026-10-06, advisory)

There were 4 MAJOR findings, all folded:

| Finding | Disposition |
|---|---|
| (1) Silently dead `planner.plan_next` patches | Repatch onto `engine.plan_next`, with a fake-ran assertion |
| (2) Retrospective order not pinned on the composition path | Order and strict-abort tests added to WP02 |
| (3) The FR-010 red case was missing (C-004) | Committed red in the gate file |
| (4) The untracked gate file would block `implement` | The gate was committed before WP01 |

Minor findings 5-11 and 13-14 are folded into the WP02 prompt ("Post-tasks squad folds") and the WP01 DoD. Note 12 (non-blocking capture now runs after the snapshot write) is recorded for the PR. Note 15 needs no action: the gates are confirmed safe. Note 16 also needs no action: the historical ADR is left as is.

## R-4: Pre-PR squad (2026-10-06, advisory)

Two lenses ran: correctness (debugger-debbie) and boundary/overlap (architect-alphonso). Neither found a BLOCKER or a MAJOR.

| # | Lens | Severity | Finding | Disposition |
|---|------|----------|---------|-------------|
| 1 | correctness | MINOR | A failure while building the best-effort retrospective capture, after the commit, turned a terminal advance into a false `blocked` Decision. | **Fixed at the root** (`runtime_bridge_retrospective`). The callback is now built inside the policy's `try`. Red-first test in `tests/runtime/test_bridge_retrospective.py`. |
| 2 | correctness | MINOR | A strict-gate refusal leaves `NextStepAutoCompleted` (and now `SignificanceEvaluated`) in the run journal. The legacy path rolls back; the composition path does not. | **Fixed at landing** (operator ruling 2026-10-07). The guard runs before anything is appended or emitted, so a refusal writes nothing and a retry does not stack events. |
| 3 | correctness | NOTE | The strict-refusal operator message differs between the paths, and a stale plan re-dispatches the composed action on the next call. | **Deferred / by design** (FR-010). Named in the PR. |
| 4 | boundary | MINOR | The adapter's `_append_event` / `_write_snapshot` wrappers are dead, kept alive only by a pin test. | **Fixed.** Wrappers deleted. The pin covers reads and planner names, and a new check asserts the adapter wraps no writer. |
| 5 | boundary | MINOR | The shape gate missed `SignificanceEvaluatedPayload` and direct writer calls. | **Fixed**, with planted rows. |
| 6 | boundary | MINOR | The terminal predicate is restated in the adapter. | **Deferred.** It is low risk. An `after_run_completed` engine hook is named in the PR. |
| 7 | boundary | MINOR | The adapter docstring cited stale call-site lines. | **Fixed.** |
| 8 | boundary | MINOR | The no-bridge positive-presence check has no planted row. | Accepted: it is a positive check. |
| 9 | boundary | NOTE | Upgrade note for readers of `decisions.events.jsonl`. | **Added** to the CHANGELOG. |
| 10 | boundary | NOTE | `engine.apply_result` / `existing_template_path` could become private again. | Out of scope (#5834 surface). |

## R-5: Landing residuals (2026-10-07)

| Ref | Residual | Disposition |
|---|---|---|
| #5853 | `spec-kitty next` in query mode previews a MEDIUM audit gate as approve/reject, but the persisted request and the answer validator use `decide_solo` / `open_stand_up` / `defer`: query mode plans through `plan_next` on the live template and never evaluates significance. The engine path had this gap before this change and the composition path now shares it. Only operator-authored templates that declare `significance:` reach it. | Open follow-up; `plan_advance` applies a result, so it cannot be dropped into query mode as is. |
| #5854 | The stale-plan check in `commit_advance` detects a run that moved between plan and commit but does not serialise concurrent writers. On a stale plan the engine path (`_dn_advance_engine`) re-plans through `next_step` and can complete a step this caller never ran; the composition path refuses with a `blocked` Decision. | Open follow-up (a run-dir lock, and a refusing engine path). The limits are stated in the `commit_advance` docstring and the changelog. |
| #5855 | Re-polling a pending audit gate evaluates its significance again. A run paused at a MEDIUM gate before this change keeps its approve/reject request, so a re-poll records the MEDIUM band and a later `approve` is refused. Engine re-poll behaviour that predates this change. | Open follow-up. Stated in the changelog Upgrade Notes: answer such a gate before polling again. |
