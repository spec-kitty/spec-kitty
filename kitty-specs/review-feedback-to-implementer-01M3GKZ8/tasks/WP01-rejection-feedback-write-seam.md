---
work_package_id: WP01
title: Coupled rejection-feedback persistence on the re-implement edge
dependencies: []
requirement_refs:
- C-003
- FR-001
- FR-002
- FR-003
- FR-004
- FR-008
- NFR-002
- NFR-003
planning_base_branch: issue-4899-review-feedback-to-implementer
merge_target_branch: issue-4899-review-feedback-to-implementer
branch_strategy: Planning artifacts for this mission were generated on issue-4899-review-feedback-to-implementer. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4899-review-feedback-to-implementer unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-review-feedback-to-implementer-01M3GKZ8
base_commit: d6f2a64def973e7b43b7cb5e09920bfdfd08ab38
created_at: '2026-09-27T06:34:20.767316+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Write-side seam
history:
- at: '2026-09-27T05:48:09Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: ''
authoritative_surface: src/specify_cli/cli/commands/agent/tasks_transition_core.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/tasks_transition_core.py
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py
- tests/characterization/test_trio_pure_cores.py
role: ''
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Coupled rejection-feedback persistence on the re-implement edge

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any
user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `{{agent_profile}}`
- **Role**: `{{role}}`
- **Agent/tool**: `{{agent}}`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this
work package's `task_type` (`implement`) and `authoritative_surface`
(`src/specify_cli/cli/commands/agent/tasks_transition_core.py`).

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via
  `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code blocks: ```python`, ```bash`.

---

## Objectives & Success Criteria

Two independent defects break one loop; this WP fixes the **write side (#4899)**. Today the
`in_review → in_progress` (re-implement) rejection edge is silently feedback-lossy because four
write-side gates are each keyed on `target_lane == Lane.PLANNED`. The edge therefore skips
content-read, cycle-persist, resolvable-pointer emission, and the no-rationale refusal — leaving no
record, an empty feedback location, and a non-resolvable synthetic `review:<WP>` reference.

**Done when:**

- **SC-001 / FR-001,FR-002,FR-003** — A rejection onto the re-implement edge with feedback produces a
  committed review-cycle record, a populated feedback location, and a resolvable `review-cycle://…`
  reference — matching the `in_review → planned` edge **by value** on a shared fixture (feedback text
  resolves equal to the reviewer's input; every parity field equal field-for-field, not merely the same
  set of populated fields).
- **SC-002 / FR-004** — A no-rationale rejection on the re-implement edge is **refused** as an
  observable failure (aborts / non-zero), never a logged no-op that still records the transition.
- **FR-008 (conditional, #3451)** — If the review-cycle counter double-increments on the re-implement
  edge, it is corrected to increment **exactly once** with its own red-first scenario; if it does not
  reproduce, it stays out of scope (recorded as such).
- **NFR-003** — The arbiter-override moment (`in_review → {approved, done}`, #4809) is NOT regressed.
- **NFR-002** — Every defect scenario is committed RED before its fix and green after.
- Complexity: no touched function exceeds C901/S3776 ≤15; `ruff`, `ruff format --check`, and `mypy`
  are clean with zero new suppressions.

## Context & Constraints

- Charter: `.kittify/charter/charter.md`. Mission docs: `kitty-specs/review-feedback-to-implementer-01M3GKZ8/`
  `plan.md` (§"Architecture: the coupled write-side seam"), `spec.md` (US1), `data-model.md`
  (field-level parity contract), `contracts/is-review-rejection-edge.md` (**FROZEN** — this WP
  introduces exactly this signature/semantics).
- **FROZEN read-only dependency (NFR-001)**: `src/specify_cli/review/cycle.py` grammar and
  `tasks_verdict_persistence.py::persist_rejected_review_cycle_for_rollback` — the parity **oracle**.
  Read them; do NOT modify them (they are NOT in this WP's `owned_files`).
- **Terminology**: "Mission" not "feature"; no `feature*` aliases.

### The FIVE rejection-family sites (verified @ current lines on `issue-4899-review-feedback-to-implementer`)

> Gates 1–4 are the write-side edge; **gate 5 (`_mt_hop_review_result`) is the EMITTED-event `review_result`
> selector** and was missed by the plan's four-gate framing. Routing gates 1–4 alone is NOT enough to
> prove SC-001 field-for-field VALUE parity — see the gate-5 note in T003.

| # | Gate | Site | Today | Effect on `in_review → in_progress` |
|---|------|------|-------|-------------------------------------|
| 1 | Feedback content read | `tasks_move_task.py:615` in `_mt_resolve_feedback` `if st.target_lane == Lane.PLANNED:` | Reads content only for →planned | Content never read → empty feedback location |
| 2 | Persist-call gate | `tasks_move_task.py:2334` `if decision.planned_rollback and st.resolved_feedback_source is not None:` (sole caller of `persist_rejected_review_cycle_for_rollback`); flag set at `tasks_transition_core.py:829` | Persists cycle only for →planned | No review-cycle record written |
| 3 | `emit_review_ref` selection | `tasks_transition_core.py:296` `if target_lane == Lane.PLANNED and review_feedback_pointer:` | Real pointer only for →planned; else synthetic `review:<WP>` | Non-resolvable reference left behind |
| 4 | No-rationale refusal | `tasks_transition_core.py:595` `_guard_planned_rollback` `if req.target_lane != Lane.PLANNED: return None` | Refuses no-rationale only for →planned | No-rationale re-implement rejection silently accepted |
| 5 | Emitted-event `review_result` selection | `tasks_move_task.py:2539` `_mt_hop_review_result` `if target == Lane.PLANNED and rejected is not None:` — `st.rejected_review_result` is set at `tasks_verdict_persistence.py:966` once gate 2 fires | Returns the rejection `review_result` only for →planned | Skipped on the re-implement edge → control falls to the approval-shaped branch at `:2562` (verdict=`APPROVED`, reference=`auto-forward:<WP>`), which does NOT match the resolvable `review-cycle://` pointer gate 3 emits → trips `_check_review_result_consistency`; **SC-001 value parity unprovable from gates 1–4 alone** |

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> Populated automatically by finalize-tasks. Do NOT change manually. Prepare the execution workspace
> with `spec-kitty implement WP01` (allocates the per-lane worktree from `lanes.json`); consume the
> resolved workspace path, do NOT reconstruct it.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first: parity + no-rationale + predicate truth-table scenarios

- **Purpose**: Establish the ATDD safety net (NFR-002). These MUST be committed RED before any
  implementation subtask.
- **Steps**:
  1. In `tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py` add **SC-001** — reject an
     in-review WP onto the re-implement edge (`--to in_progress`, alias `doing`) with a specific
     feedback text; assert (a) a committed `review-cycle-<N>.md` exists, (b) the feedback body is
     populated, (c) `event.review_ref` is resolvable (`is_non_resolvable_review_ref(ref) is False`) and
     resolves to feedback text **equal by value** to the input, and (d) — **gate 5 coverage** — the
     EMITTED event's `review_result` matches the `in_review → planned` edge **by value**
     (`reviewer` / `verdict` / `reference`): it must be the rejection result carrying the resolvable
     `review-cycle://` reference, NOT the approval-shaped fallback (`verdict=APPROVED`,
     `reference="auto-forward:<WP>"`). This assertion FAILS if gate 5 (`tasks_move_task.py:2539`) is not
     also routed through the predicate, so it proves the fix cannot be masked by gates 1–4 alone.
     Compare field-for-field against the `in_review → planned` edge on the **same** feedback fixture
     (`cycle_number`, reviewer, verdict, body, reference, and the emitted `review_result`).
  2. Add **SC-002** — a re-implement rejection with **no** rationale is refused (non-zero / raised
     abort), paired with an accepted with-rationale rejection on the same fixture.
  3. In `tests/characterization/test_trio_pure_cores.py` add the `is_review_rejection_edge`
     **truth-table** (`in_review→in_progress`=True, `*→planned`=True from multiple sources,
     `in_review→{approved,done}`=False, `doing` alias normalized) and a value-parity assertion.
- **Files**: `tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py`,
  `tests/characterization/test_trio_pure_cores.py`.
- **Notes**: Prove RED on the base first. Commit the failing tests as their own commit before T002+.

### Subtask T002 – Introduce the pure predicate `is_review_rejection_edge`

- **Purpose**: One canonical source of truth for the rejection-edge decision (C-003).
- **Steps**: In `tasks_transition_core.py`, co-located with lane logic, add exactly the FROZEN contract
  signature:

  ```python
  def is_review_rejection_edge(old_lane: str, target_lane: str) -> bool:
      old = resolve_lane_alias(old_lane)
      target = resolve_lane_alias(target_lane)
      return target == Lane.PLANNED or (old == Lane.IN_REVIEW and target == Lane.IN_PROGRESS)
  ```

- **Files**: `src/specify_cli/cli/commands/agent/tasks_transition_core.py`.
- **Notes**: Pure, no I/O, alias-normalizing, ≤3 lines. The union (`target == PLANNED` OR the
  re-implement edge) is **load-bearing**: gates 1 & 4 fire today for `* → planned` from ANY source;
  narrowing them to the `in_review` family would REGRESS `_planned_rollback_message`'s Arm A/Arm B guard.

### Subtask T003 – Route the FIVE rejection-family sites + generalize the `Emit` flag through the predicate

- **Purpose**: Enforce C-003 by construction — one decision, not five.
- **Steps** (per `contracts/is-review-rejection-edge.md`):
  - Gate 1 `tasks_move_task.py:615` → `is_review_rejection_edge(st.old_lane, st.target_lane)`.
  - Gate 3 `tasks_transition_core.py:296` →
    `is_review_rejection_edge(old_lane, target_lane) and review_feedback_pointer`.
  - Gate 4 `tasks_transition_core.py:595` `_guard_planned_rollback` →
    `if not is_review_rejection_edge(req.old_lane, req.target_lane): return None`.
  - **Gate 5 `tasks_move_task.py:2539` `_mt_hop_review_result`** → route the
    `if target == Lane.PLANNED and rejected is not None:` selector through
    `is_review_rejection_edge(st.old_lane, target)` so the re-implement edge returns `rejected`
    (`st.rejected_review_result`, set at `tasks_verdict_persistence.py:966` once gate 2 fires) and NEVER
    falls through to the approval-shaped branch at `:2562` (which would emit `verdict=APPROVED`,
    `reference="auto-forward:<WP>"` and trip `_check_review_result_consistency` against gate 3's
    resolvable pointer). This is the site that makes SC-001 value parity provable; without it gates 1–4
    persist the record but the EMITTED event still carries an approval-shaped `review_result`.
  - `Emit.planned_rollback` (`tasks_transition_core.py:829`) → rename to `is_review_rejection`, set from
    `is_review_rejection_edge(req.old_lane, req.target_lane)`. Flip its two consumers together: the
    persist-call gate (`tasks_move_task.py:2334`) and the plan-rebuild trigger (`tasks_move_task.py:2371`),
    whose now-redundant explicit `in_review → {planned,in_progress}` clause is removed (tidy-first).
  - **Pointer flow**: on the re-implement edge the persist call now runs and sets
    `st.review_feedback_pointer`; the plan rebuild (`:2395`) threads
    `review_feedback_pointer=st.review_feedback_pointer`; gate 3's predicate is now true → the real
    `review-cycle://…` pointer is emitted instead of the synthetic token (FR-002/FR-003); gate 5 then
    carries the matching rejection `review_result` onto the emitted event.
- **Files**: `src/specify_cli/cli/commands/agent/tasks_transition_core.py`,
  `src/specify_cli/cli/commands/agent/tasks_move_task.py`.
- **Files**: `tasks_transition_core.py`, `tasks_move_task.py`.
- **Notes**: Keep each gate ≤3 lines (a single predicate call, not a grown `or` clause).

### Subtask T004 [P] – Campsite tidy-first: extract `_mt_persist_rejection_cycle`

- **Purpose**: Keep `tasks_move_task.py` (≈3670 lines) under the C901/S3776 ≤15 ceiling.
- **Steps**: Extract the pointer-restore-and-persist block `tasks_move_task.py:2334-2348` (the
  `st.agent` save/restore around `persist_rejected_review_cycle_for_rollback`) into a named helper
  `_mt_persist_rejection_cycle(st, ports)`. Behavior-preserving; its own commit + a focused unit test.
- **Files**: `tasks_move_task.py`, `tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py`.
- **Parallel?**: Yes — independent of the gate wiring once T002 exists.
- **Notes**: Confirm no touched function crosses complexity 16; add the helper's unit test in this WP
  (Sonar new-code coverage).

### Subtask T005 – Conditional FR-008 (#3451) review-cycle counter

- **Purpose**: Correct the cycle counter on the new edge only if the miscount reproduces there.
- **Steps**: Write a red-first scenario asserting `cycle_number` increments **exactly once** on a
  re-implement rejection. If it reproduces (double-increment) → fix at root and keep the scenario green.
  If it does NOT reproduce on this edge → leave #3451 out of scope and record that explicitly in the
  Activity Log + PR body (do not fold speculative changes).
- **Files**: `tasks_move_task.py` (+ `tasks_transition_core.py` if the count path lives there),
  `tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py`.

### Subtask T006 – NFR-003 arbiter-override non-regression guard

- **Purpose**: Prove the arbiter-override moment is untouched.
- **Steps**: Confirm `is_review_rejection_edge` returns `False` for `in_review → {approved, done}`
  (`target ∉ {planned, in_progress}`). Do NOT touch `is_arbiter_override` (`tasks_move_task.py:1146`)
  or `arb_review_ref` (`tasks_transition_core.py:300-303`) or the `arbiter_forward` rebuild trigger.
  Keep existing arbiter-override coverage green as the guard.
- **Files**: read-only verification against arbiter paths; assertion may live in the seam test.

### Subtask T007 – Run the WP01 validation surface, record counts

- **Purpose**: Charter Testing Requirements — run your blast radius and record it.
- **Steps**: Run the Test Strategy commands below; record exact commands + passed/failed counts in the
  PR *Tests run* section. Classify any pre-existing baseline reds per the CLAUDE.md gotcha.

## Adjacent rejection-family sites — explicit decisions (brownfield scout folds)

Beyond the five gates routed by T003, three neighbouring `== Lane.PLANNED`-keyed sites sit in the
re-implement blast radius. Each carries an explicit decision so a later reader neither misses a required
change nor over-folds and regresses resume-in-place. These are **decisions to honour**, not new subtasks.

| Site | Today | Decision for `in_review → in_progress` |
|------|-------|----------------------------------------|
| `_mt_release_review_lock` `tasks_move_task.py:3145` (`release_to = (Lane.APPROVED, Lane.PLANNED)`) | Releases the review lock only for →approved/→planned | **MUST decide (Fold 4).** On the re-implement edge the lock is currently NOT released → a stuck review-lock can block the next `for_review → in_review` claim. Preferred: extend the release to the re-implement edge (add `Lane.IN_PROGRESS` to `release_to`, or gate the release on `is_review_rejection_edge`). If instead left out of scope, record the reasoning + the follow-up in the Activity Log/PR. Cover the chosen behaviour with a test cell. |
| `release_runtime_claim` restamp-suppress `tasks_move_task.py:3063` and claim-review-override `:3083` (both keyed `st.target_lane == Lane.PLANNED`) | Releases the runtime claim to the pool only for →planned | **KEEP AS-IS (Fold 5).** The re-implement edge INTENTIONALLY retains the implementer's claim (resume-in-place). Do NOT route these through `is_review_rejection_edge` — doing so would release the claim on re-implement and regress resume-in-place. Add a code comment + a truth-table cell asserting the claim is retained on `in_review → in_progress`. |
| `is_rejection_save` `tasks_transition_core.py:462` (`target_lane == Lane.PLANNED and req.feedback_provided`) | Agent-mismatch causal *diagnostic* is keyed on →planned | **NIT / OUT OF SCOPE (Fold 6).** A re-implement rejection degrades to the generic diagnostic message (cosmetic only — no behavioural loss). Leave unchanged; record a one-line known/out-of-scope note. Do not fold into the predicate. |

## Test Strategy (required)

Run the targeted module + owning-subsystem surface for this WP's diff, plus the shared baseline:

```bash
make test-fast
.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py -q
.venv/bin/python -m pytest tests/characterization/test_trio_pure_cores.py -q
# blast radius for the two owned transition modules:
.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/ -q
```

Also run `ruff check .`, `uv run --frozen ruff format --check .` (whole-repo format gate, #3952), and
`mypy` over the changed files. Do NOT run `make test-full` / whole-repo suites — the CI agent owns that.

## Risks & Mitigations

- **Regressing any-source `→planned`** → union predicate + T001 parity across sources.
- **Regressing arbiter-override (#4809/NFR-003)** → predicate excludes forward edges by construction; T006.
- **Complexity ceiling** → T004 tidy-first extraction; keep gates to one predicate call each.
- **Touching frozen grammar** → `review/cycle.py` and `persist_rejected_review_cycle_for_rollback` are
  read-only oracles; a change there is out of scope (NFR-001).

## Review Guidance

- Verify the predicate is the SINGLE source for all five rejection-family sites — including
  `_mt_hop_review_result` (`tasks_move_task.py:2539`), whose omission would silently ship a
  gates-1–4-only partial fix that fails SC-001 value parity (no residual `== Lane.PLANNED` on a
  rejection-edge decision) and that the `Emit` flag rename flipped both consumers together.
- Verify SC-001 parity is asserted **by value** (resolved feedback text equals input), not just field
  presence, and SC-002 refusal is an observable failure.
- Confirm arbiter-override coverage is still green and untouched.
- Confirm the #4899 issue-matrix row exists (approval gate).

## Activity Log

> **CRITICAL**: entries MUST be in chronological order (oldest first, newest last). Append at the END.

- 2026-09-27T05:48:09Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task WP01 --to <status>`
to change WP status.
- 2026-09-27T07:13:53Z – claude – shell_pid=896679 – WP01 disposition notes (#4899): (1) FR-008/#3451 counter double-increment does NOT reproduce on the re-implement edge -- the fix routes gate2's persist through a SINGLE call site (_mt_persist_rejection_cycle, called once per CLI invocation from _mt_finalize_plan); a two-rejection regression test (TestFr008ReviewCycleCounterOnReimplementEdge) proves cycle_number advances exactly 1->2, never double-incrementing. Recorded out-of-scope per T005. (2) Fold 4 (:3145 review-lock release): CHOSE to extend the release to the re-implement edge via the same is_review_rejection_edge predicate (not a bare Lane.IN_PROGRESS add to release_to), scoped by old_lane in release_from so ordinary claimed/for_review->in_progress moves are unaffected. (3) Fold 5 (:3063/:3083 runtime-claim retention): KEPT AS-IS per instructions -- NOT routed through the predicate; code comments + the SC-002/parity tests cover retention on the reimplement edge. (4) Fold 6 (:462 is_rejection_save diagnostic): left unchanged, out of scope -- cosmetic diagnostic-message-only degradation on the reimplement edge, no behavioral loss. (5) _planned_rollback_message's wording still says the literal string "to 'planned'" even when the refusal now also fires on the reimplement edge (target=in_progress) -- out of scope per the contract's call-site table, which does not list this helper; flagging as a known cosmetic gap for a follow-up.
