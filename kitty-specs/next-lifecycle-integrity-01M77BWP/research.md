# Research: next lifecycle integrity (#7548)

updated: 2026-11-12. The detailed grounding is in `research/code-grounding.md`; issue triage is in `research/foldable-issues.md`.

## R-1: Root cause of the replay (#7553, #5929, #7565)
- **Decision:** gate advancing `next` on a finished board before any run start or advance.
- **Rationale:**
  - The front-phase override (`_dn_finalized_board_override`) never moves the run and declines an `accept`/`done` board.
  - Every fall-through (board decline, `--result failed|blocked`, a mid-implementation decline) issues `discovery`.
  - `engine.apply_result` then completes each issued step on `success`. A run already walked onto the DAG is never overridden afterwards.
- **Alternatives considered:**
  - Gate only on acceptance. Rejected: misses #5929/#7565, which happen before accept.
  - Fast-forward the run's `completed_steps`. Rejected: fabricates the very rows #7553 complains about.
  - Issue the `accept` step from the board. Rejected by operator ruling in favour of `blocked`.

## R-2: Envelope on a finished board (operator rulings 2026-11-12)
> **Superseded in part:** the Squad dispositions below and the operator rulings in `decisions/` supersede this entry where they differ.
- **Decision:**
  - unaccepted: `kind=blocked`, `error_code=MISSION_AWAITING_ACCEPTANCE`, `next_command` = `spec-kitty accept --mission <handle>`;
  - accepted (board still finished) or landed: `kind=terminal`.
- **Rationale:** recorded in `decisions/` (`finished_board_envelope`, `finished_board_state_map`).
- **Where the command goes:** `Decision.remediation` already means "what next changed in the workspace" (#7310 WP06), so the command goes in the additive `next_command`, not `remediation`.
- **Alternatives considered:** terminal as soon as the board is finished; one shared code for both states. Both rejected by the operator.

## R-3: Which runs the gate must not pre-empt
> **Superseded in part:** the Squad dispositions below and the operator rulings in `decisions/` supersede this entry where they differ.
- **Decision:** the gate fires only when there is no persisted run, or the run's `issued_step_id` is not a WP-iteration step (`implement`, `review`) or `accept`.
- **Rationale:** a Mission driven through `next` reaches `accept` through the engine. Its final advance appends `MissionRunCompleted` and runs the retrospective gate (`_primary_mission_is_completed` docstring, `runtime_bridge.py:343-347`). Pre-empting it would make both unreachable.
- **Residual:** a Mission whose WPs finished outside the DAG never reaches `MissionRunCompleted` through `next`. A follow-up issue will be filed.

## R-4: Where acceptance is read
> **Superseded in part:** the Squad dispositions below and the operator rulings in `decisions/` supersede this entry where they differ.
- **Decision:** `meta.json` `accepted_at` on the PRIMARY metadata dir, through `load_meta_or_empty`, and only while the board is finished.
- **Rationale:** the status read door has no acceptance fact, and `accepted_at` is sticky (never cleared on reopen). An unreadable `meta.json` reads as not accepted, which fails toward `blocked` and never toward a wrong `terminal`.
- **Gates:** `mission_metadata` is already allowed for the runtime layer. `test_inline_meta_read_gate.py` forbids raw JSON reads.

## R-5: Query `question` contract
- **Decision:**
  - keep `question` nullable;
  - pin `question != null` iff `decision_id` and `options` are present;
  - fix the dropped first `decision_required`;
  - add `next_command` to non-decision query envelopes.
- **Rationale:** a two-lens squad (consumer, history) disproved "query always carries a question". `kind=query` is a read-only mode (`decision.py:73`, runtime-loop.md:77-80, SKILL.md, the `next-query-response` schema). Field friction asks for the next action (tracers `upgrade-dry-run-sequenced-verdict-01M68J9V`, `dispatch-router-docs-coverage-01M6BTTX`).
- **Alternatives considered:**
  - a synthesized question (rejected: no `decision_id`, so `--answer` fails);
  - a new kind or `read_only` flag (rejected: breaking change).

## R-6: Rollback reset record (#7582)
- **Decision:** `policy_metadata.rollback_reset = {scope, reset, previously_completed, reason}` on the PLANNED transition.
- **Rationale:** `policy_metadata` is a free dict in `spec_kitty_events`, so no library release is needed. A field on the `InnerStateChanged` delta would need one (typed `WPInnerStateDelta`, unknown keys dropped).
  - The transition already carries `reason` and `review_ref`. The new record adds only the facts missing today: scope, previously completed and the narrowing reason.
  - The annotation keeps the per-id lanes (single authority for subtask state).
- **Narrowing:** `--reset-subtasks T001,T002`, which requires `--note`/`--reason` (the existing alias pair).
  - The full reset stays the default, so the #2513 protection is kept: no gate checks rework since the rejection.
- **Risk:** `cutover_eligibility._policy_metadata_carries_runtime_evidence` treats any non-`lane_head`/`wp_window` key as runtime evidence. A WP being rolled back already carries a claim with policy metadata, so this is harmless. It is pinned by a test.

## Adversarial challenge (Standing Order 1)
- A fresh-context second opinion challenged R-1 to R-6 before specify. Its findings were folded in:
  - query returns `accept`, not `done`, after accept;
  - #5929's mechanism;
  - `MissionRunCompleted` reachability;
  - `accepted_at` stickiness;
  - artifact-only Missions;
  - duplication with the existing `reason`/`review_ref`.
- No dependency is added, removed or upgraded, so the supply-chain checks (DIRECTIVE_051) do not apply.

## Squad dispositions (post-tasks, 2026-11-12)

Two lenses ran: architecture (`architect-alphonso`) and test/fakeability (`reviewer-renata`). Every finding is listed below with its disposition.

| Finding | Disposition |
|---|---|
| Mid-implementation replay (`in_progress`/`claimed` → discovery); the FR-006 control was false | **Escalated.** Ruling: widen, never rewind (FR-016). Controls fixed: a `planned` WP dispatches. |
| Gate ignored mission family; documentation/research tails starved | **Folded.** The gate applies to software-dev only (decision `plan.next.gate_scope_family`). |
| The FR-010 invariant cannot hold for input decisions (`options=None`) | **Escalated.** Ruling: question ⇔ decision_id, plus options or input_key, enforced by construction (`PendingDecisionPrompt`). |
| Sticky `accepted_at` after reopen and re-approval | **Escalated.** Ruling: acceptance must be newer than the board's latest WP transition. |
| Lifecycle pairing writes `completed` for a stale issued step on a gated call | **Folded.** `suppress_step_pairing`; `next_cmd.py` moves to WP02. |
| No-row probes blind (no `mission_id` in the fixture; Op and glossary records not covered) | **Folded.** Mint a ULID `mission_id`; snapshot the tree before and after; the blocked/terminal row is required as the positive control. |
| Replayed run at `implement`/`analyze` slips through the exemption | **Residual.** Indistinguishable from a legitimate run; stale cells are pinned and documented. |
| Cell-4 seeding unbuildable at the WP head | **Folded.** Seed engine-direct (`_advance_runtime_to_step` / `advance_to_step`) and through the CLI for the lifecycle cell. |
| Canceled WPs count as finished | **Folded.** Definition aligned; cells added. |
| T008 option A breaks `test_runtime_bridge_read_path_branches.py:209` and costs a dispatch resolution | **Folded.** A separate accessor sharing the selector prefix; those tests are added to WP02's runs. |
| WP04 validation placed after the review-cycle commit; two authorities for the reset map | **Folded.** Validate after `_mt_resolve_targets`; compute once onto the state. |
| WP04 refusal cells green on the base; lane_head and subtask-gate cells blind | **Folded.** Each refusal asserts its own message, passes `--review-feedback-file`, and is paired with the positive cell. The lane branch is created; the gate message must name T002. |
| First `decision_required` preview unanswerable | **Folded.** It also carries the advance `next_command`. |
| Query premises (no metadata dir; override not returned; task_error early return) | **Folded** into WP03. |
| `RunStateMissing` must surface | **Folded.** The gate falls through. |
| Second door read on the blocked/terminal row | **Accepted.** Pinned by a count test; NFR-001 is still met. |
| Ruling said "remediation" | **Folded.** Amendment decision `plan.next.command_field_amendment`. |
| orchestrator-api maps blocked to `RUNTIME_NEXT_FAILED` | **Accepted.** Existing mapping; documented in spec Assumptions. |
| SC-001 5 vs 10 calls; SC-005 had no control | **Folded.** |
