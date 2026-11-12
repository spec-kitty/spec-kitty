---
work_package_id: WP01
title: 'Reviewer of record: claimant fact, combiner, honest identity'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-006
- FR-007
- NFR-002
- NFR-004
- C-001
- C-002
- C-003
- SC-001
- SC-002
planning_base_branch: fix/3044-approval-honesty
merge_target_branch: fix/3044-approval-honesty
branch_strategy: Planning artifacts for this mission were generated on fix/3044-approval-honesty. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/3044-approval-honesty unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-approval-honesty-01M78J9S
base_commit: ba75556425d7420e35ab4e79cafedb064329f43c
created_at: '2026-11-12T19:42:13.048713+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Foundation
history:
- at: '2026-11-12T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/status/test_review_claim_identity.py
- tests/specify_cli/cli/commands/agent/test_approval_honesty_identity.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/review_roles.py
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- src/specify_cli/cli/commands/agent/tasks_move_task_hops.py
- src/specify_cli/cli/commands/agent/tasks_move_task_executor.py
- src/specify_cli/cli/commands/agent/tasks.py
- tests/status/test_review_claim_identity.py
- tests/specify_cli/cli/commands/agent/test_approval_honesty_identity.py
- tests/specify_cli/cli/commands/agent/test_verdict_attribution_4670.py
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py
- tests/agent/cli/commands/test_tasks_helpers.py
- tests/agent/test_review_feedback_pointer_2x_unit.py
- tests/integration/test_review_durability_matrix.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Reviewer of record: claimant fact, combiner, honest identity

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission approval-honesty-01M78J9S`).
- **You must address all feedback** before your work is complete.
- **Report progress** with `spec-kitty agent tasks add-history WP01 --note "..." --mission approval-honesty-01M78J9S`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

`spec-kitty agent tasks move-task <WP> --to approved|done` today records a reviewer nobody
asserted: `git config user.name` (via `_detect_reviewer_name`). It also records a minted
reference: `auto-approval:<WP>:<date>`, `approval:<WP>` or `auto-forward:<WP>`. After this work
package, every identity field of an approval names **one reviewer of record**, and no token is
minted.

**Done when:**
- With git `user.name` set to `Git User Fallback`, a claim → approve → done flow leaves that string
  nowhere in the approval or done event. Fields checked:
  - event `actor` (all segments);
  - `review_result.reviewer`;
  - `evidence.review.reviewer`;
  - `policy_metadata.tool`.

  This holds on the default path **and** under `--no-auto-commit`.
- No `auto-approval:`, `approval:` or `auto-forward:` reference is minted on any approval or done
  hop. The reference is one of:
  - the `review-cycle://` pointer of the cycle the approval wrote, whether durable or local-only;
  - a caller `--approval-ref`;
  - `force-override` for a forced move, or the arbiter decision's reference;
  - the recorded approval's reference, carried verbatim on `approved -> done`.
- `--reviewer` alone sets the actor, so it is an identity assertion. The **conflict refusal**
  belongs to WP02, not here.
- `_detect_reviewer_name` no longer exists, and neither does its `tasks.py` re-export.
- Requirements: FR-001, FR-002, FR-003, FR-004 (ratchet), FR-006, FR-007; NFR-002, NFR-004;
  C-001, C-002, C-003; SC-001, SC-002.

## Context & Constraints

Read these before coding:
- `kitty-specs/approval-honesty-01M78J9S/spec.md`, `plan.md` (Design: "Two pieces"), `research.md`,
  `data-model.md`, `contracts/move-task-approval.md`.
- `kitty-specs/approval-honesty-01M78J9S/research/code-grounding.md` §1, the field-by-field source
  table.
- Charter `.kittify/charter/charter.md`: Standing Orders 2 (tidy-first), 4 (red-first), 5 (close a
  defect class by construction). Load `spec-kitty charter context --action implement`.
- ADR `docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md`. Do **not** change
  consolidation behaviour (C-004); `approved_bound.py` is read-only for this mission.

**Hard constraints:**
- No events-schema change. The reviewer stays a required, non-empty string (C-001).
- Do not touch `workflow.py`, `workflow_cores.py`, `workflow_executor.py`,
  `runtime/next/prompt_builder.py` or `status/__init__.py` (open PR #7596; C-003). Import new
  status helpers as `from specify_cli.status.review_roles import …`.
- `_do_move_task` is at McCabe 15. Add **no** branch to it. Run `ruff check --select C901` on the
  touched files.
- Never infer or fabricate a reviewer (non-goal of the mission).

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `fix/3044-approval-honesty` (via the Mission topic branch)
- **Merge target branch**: `fix/3044-approval-honesty`

The workspace comes from `lanes.json` through `spec-kitty agent action implement WP01 --agent <name> --mission approval-honesty-01M78J9S`. Do not pick a base branch by hand.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first: honest identity end-to-end

- **Purpose**: Pin the user-observable defect (#7569) before changing code. This is a separate commit, and it must be **red** on the base.
- **Files**: new `tests/specify_cli/cli/commands/agent/test_approval_honesty_identity.py`.
- **Seam to reuse**: `tests/specify_cli/cli/commands/agent/test_verdict_attribution_4670.py`. It builds a real git repo whose `user.name` is `Git User Fallback` (`_build_mission`), seeds hops (`_seed_hops(actor=…, force=…)`), drives the CLI (`_move`) and reads results (`_review_result_reviewer`). Import its helpers or copy the fixture builder into a small local helper; do not create a third fixture style. Seed the review claim **unforced** (`force=False`). That is how `agent action review` records it, and WP01's claimant rule ignores forced claims.
- **Cases** (each one a test; parametrize where natural):
  1. Claim by `claude:sonnet:reviewer-renata`, then `move-task WP01 --to approved` with no `--agent`. Assert:
     - `Git User Fallback` is absent from the whole serialized approval event (search the JSON line, not only named fields);
     - `review_result.reviewer`, `evidence.review.reviewer` and `policy_metadata.tool` all identify the claimant;
     - the reference starts with `review-cycle://`, and the pointed-to file exists.
  2. The same with `--no-auto-commit`. Today this records the git name plus `auto-approval:` (verified by the plan squad).
  3. Then `move-task WP01 --to done`. The done event's reviewer and reference equal the approval's. Neither the git name nor a token appears.
  4. A forced approval (`--force --agent claude:sonnet:operator`) over the claim: reviewer = `claude:sonnet:operator`, reference = `force-override`.
  5. `--reviewer claude:sonnet:reviewer-renata` with no `--agent`: the event `actor` identifies `reviewer-renata`, not `user`.
  6. **Positive control (non-vacuity)**: in the same fixture, assert the claimant identity **is** present. This proves the "absent" assertions are not vacuous.
- **Commit**: `test(review): pin approval identity honesty (red, #7569)`, before any implementation commit. Record the red run's output (failing assertion lines) in the commit body or in an `add-history` note.

### Subtask T002 – Claimant fact and identity equality in `status/review_roles.py`

- **Purpose**: One canonical "who claimed review" reader, shared in meaning with consolidation (`consolidation/approved_bound.py::_entered_review_by_claim`, read-only reference).
- **Steps**:
  1. Add `latest_review_claim_identity(events: Sequence[StatusEvent], wp_id: str) -> str | None`. Walk the WP's events newest-first and return `actor_full_identity(event.actor)` (or the compact identity that `_mt_resolve_active_reviewer_identity` returns today; pick one and use it consistently) of the newest event that satisfies all of:
     - `to_lane == Lane.IN_REVIEW`;
     - `force is False`;
     - `not is_migration_actor(event.actor)`;
     - `_actor_key(event.actor) not in GENERIC_IMPLEMENTATION_ACTORS`.

     Stop at the first `in_review` entry: if the newest entry does not qualify, return `None`. Do not reach back to an older claim.
  2. Add `same_review_identity(left: str | None, right: str | None) -> bool`. Strict equality on the **recorded** segments, with the role segment dropped:
     - the tool must match;
     - model must match if both record one; profile likewise;
     - a segment recorded on **only one** side counts as **not equal** when the other side has a profile or model. Bare `claude` is **not** equal to `claude:sonnet:reviewer-renata`.

     Document the rule in the docstring. Never derive it from `not actor_identities_independent`, which treats one-sided segments as "not independent" and would let a bare tool impersonate.
  3. Add both names to `__all__`.
- **Tests**: new `tests/status/test_review_claim_identity.py`, with pure unit tests:
  - forced claim ignored;
  - migration actor ignored;
  - placeholder (`user`) yields `None`;
  - newest claim wins;
  - equality truth table: same full identity; role-only difference; bare tool vs profiled; different profile, same tool; different model.
- **Parallel?**: no.

### Subtask T003 – Pure reviewer-of-record combiner

- **Purpose**: One function decides the reviewer and reference; every field reads it (Charter "single canonical authority").
- **Steps** (in `tasks_move_task.py`, near `_mt_resolve_active_reviewer_identity`, about line 1762):
  1. A frozen dataclass `ReviewerOfRecord(identity: str, reference: str | None, kind: Literal["review", "forced", "carried"])`. The reference may be `None` for a review whose pointer is known only after the cycle write.
  2. A pure `resolve_reviewer_of_record(*, agent, reviewer, claimant, forced, recorded_approval, arbiter_ref, approval_ref) -> ReviewerOfRecord | None`. Its order (plan.md §Design):
     - **forced**: identity = `agent or reviewer or claimant or "user"`; reference = `arbiter_ref or "force-override"`.
     - **carried** (`recorded_approval` given, i.e. `approved -> done`): the recorded reviewer and reference, verbatim. If none is readable: identity = `agent or reviewer`, reference `force-override`; if that is empty too, return `None`. The caller then lets the existing `REVIEW_NOT_INDEPENDENT` placeholder refusal fire, so no new code is needed.
     - **review**: identity = `agent or reviewer or claimant`; reference = `approval_ref` (validated in WP03) or `None` (the pointer is filled after the write).
  3. Unit-test the function directly; table-driven tests in the T001 file are fine.
- **Notes**: Keep it pure. Gathering the facts (`claimant` from `latest_review_claim_identity` over the event log; `recorded_approval` from `specify_cli.status.event_sourced_review_result`) happens in `_mt_gather_late_facts`. The **arbiter reference** is produced by `_mt_fire_arbiter_persist`, which runs *after* `_mt_gather_late_facts` (`_mt_run_decision`, about lines 1719-1735). Resolve the arbiter reference as a late input after that persist, or leave it on the existing `arb_review_ref` threading (`tasks_transition_core.py` about line 344) and only fix the reviewer. Document which one you chose.

### Subtask T004 – Route the six identity sources through the combiner

- **Purpose**: Today six places pick an identity. After this subtask all of them read the combiner.
- **Sources** (line numbers at base `89217ac8`):
  1. `_mt_approval_facts` (`tasks_move_task.py:1657`): `effective_reviewer` and `effective_approval_ref` come from the combiner.
  2. `_mt_resolve_reviewer_identity` (`:1749`): returns the combiner identity on approval exits; keep its rejection-path behaviour unchanged.
  3. `_mt_resolve_active_reviewer_identity` (`:1762`): delegates to `latest_review_claim_identity`. This changes its meaning to unforced claims only (decision `claimant_definition`), so re-pin the 4670 fixture (T006).
  4. `_mt_hop_actor` (`tasks_move_task_hops.py:155`) and `_mt_approval_actor` (`tasks_move_task.py:1236`): on approval/done hops, `--agent`, else `--reviewer`, else the claimant, else `user`. `--reviewer` now feeds the actor (D-P3). `_mt_structured_actor` (`hops.py` about line 190) must treat a `--reviewer`-sourced identity like `--agent` (a strict parse via `build_status_actor`).
  5. `_mt_approval_policy_metadata.tool` (`hops.py:257`): the combiner identity.
  6. Executor `st.actor` (`tasks_move_task_executor.py:143`): the combiner identity on approval/done.
- **Cycle writer** (`tasks_verdict_persistence.py:914`): it reads `st.reviewer or st.agent or st.actor`. Leave that file to WP03, but make sure `st.actor` now holds the reviewer of record, so the writer is already right when `--reviewer` and `--agent` are absent or equal.
- **Validation**: after this subtask the behaviour is unchanged **except** for the claimant definition. Run the 4670 file and `test_move_task_approval_evidence.py` before T005 (tidy-first: structure first, then behaviour).

### Subtask T005 – Delete the fallbacks; honest references

- **Purpose**: Close the defect class by construction (Standing Order 5): the fabricating code no longer exists.
- **Steps**:
  1. Delete `_detect_reviewer_name` (`tasks_move_task.py:2226-2238`) and its re-export in `tasks.py` (about line 408). Run `grep -rn "_detect_reviewer_name" src tests`; the only hits left should be in tests you re-pin in T006.
  2. Remove the minting of `synthetic_auto_approval_ref` from `_mt_approval_facts` and of `synthetic_approval_ref` from `_mt_plan_review_result` (`hops.py:93`). Remove the `auto-forward:` default from `_mt_hop_review_result` (`hops.py` about line 145): use the combiner's reference there.
     - Do **not** delete the mint functions or the prefix constants in `review/cycle.py`. Readers still classify historical tokens (C-002), and WP03 owns `review/cycle.py`.
     - If a mint function ends up with no caller in `src/`, check whether `tests/architectural/test_no_dead_symbols.py` or the `__all__` gate flags it. If one does, remove the dead mint in WP03, not here; note it in `add-history`.
  3. **Executor overwrite** (`tasks_move_task_executor.py:146-158`): when the approval write produced a `review_cycle`, durable or local-only, the evidence `reference` becomes that cycle's pointer, and the reviewer stays the combiner identity. Remove the dependence on `durably_persisted` for honesty. Keep the durability signal for revert and commit semantics exactly as it is.
     - Check that `_mt_hop_review_result` (`hops.py:107-152`) then selects the same result on the local-only path.
     - The `_check_review_result_consistency` guard requires `review_result.reference == evidence.review.reference`; keep the two in sync.
  4. **Forced / arbiter / done**: thread the combiner's `reference` through `_approval_evidence` (`tasks_transition_core.py:1024`). That file is WP02's, so do **not** edit it. `_approval_evidence` already reads `req.effective_approval_ref or "force-override"`, so feeding `effective_approval_ref` from the combiner is enough. For a review whose pointer is not yet known, the executor overwrite (step 3) replaces the provisional reference before emit.
     - Make sure no path emits `force-override` for an **unforced** review. The plan squad found that `--no-auto-commit` would hit that `or` today.
     - If the provisional value is unavoidable, assert in T001 case 2 that the final emitted reference is the pointer.
- **Notes**: `DoneEvidence` (`status/emit.py:464-477`) and `wp_state._check_review_result` require a non-empty reviewer, verdict and reference; every combiner output satisfies that.

### Subtask T006 – Re-pin stale tests; help text

- **Purpose**: Judge each test, not the git blame (Standing Order 4): stale → re-pin, stub → delete, valid → fix the product.
- **Known re-pins** (plan squad inventory):
  - `tests/agent/cli/commands/test_tasks_helpers.py`: module-level import of `_detect_reviewer_name` (line 21). The 4 `_detect_reviewer_name` tests (`:264-292`) are now stale; delete them and fix the import, since the other ~35 tests in the file must keep running.
  - `tests/agent/test_review_feedback_pointer_2x_unit.py`: import at `:16`; `:168`, `:309`; `:371-395` pins `"Git Reviewer"` in done evidence. Re-pin to the carried or asserted identity.
  - `tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py:302-312`: a patch-bite test asserting the `auto-approval:` default. Re-pin it to assert the combiner is the seam.
  - `tests/integration/test_review_durability_matrix.py:526`: relies on the `auto-approval` default reference; re-pin.
  - `tests/specify_cli/cli/commands/agent/test_verdict_attribution_4670.py`:
    - the fixture seeds its claim with `force=True` (`:62`); give it an unforced claim;
    - `:434-462` counts call sites in source text; keep it green or update it if the count legitimately changes, explaining why in the commit.
- **Help text**: `tasks.py` about line 790, `--reviewer`: replace "Reviewer name (auto-detected from git if omitted)" with "Reviewer identity (tool:model:profile). Sets the approver when --agent is omitted; must match --agent and the review claimant."
- **Do not** re-pin tests owned by WP02 or WP03; they may stay red until those packages land. List any you see go red in `add-history`.

### Subtask T007 – Validation

Run and record each command with its pass/fail count in `add-history`:

```bash
make test-fast
.venv/bin/python -m pytest -q tests/status/test_review_claim_identity.py tests/specify_cli/cli/commands/agent/test_approval_honesty_identity.py tests/specify_cli/cli/commands/agent/test_verdict_attribution_4670.py tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py tests/agent/cli/commands/test_tasks_helpers.py tests/agent/test_review_feedback_pointer_2x_unit.py tests/integration/test_review_durability_matrix.py tests/specify_cli/cli/commands/agent/test_move_task_approval_evidence.py tests/specify_cli/cli/commands/agent/test_move_task_structured_actor_6400.py tests/specify_cli/cli/commands/agent/test_emit_review_result.py tests/specify_cli/cli/commands/agent/test_move_task_done_exit.py tests/integration/review/test_approve_without_force.py
.venv/bin/python -m pytest -q tests/status tests/review
.venv/bin/python -m pytest -q tests/architectural/test_status_events_writes_gate.py tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_no_read_side_bypass.py tests/architectural/test_verdict_vocab_single_source.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_layer_rules.py
.venv/bin/ruff check <changed files>; .venv/bin/ruff format --check --force-exclude <changed files>; .venv/bin/mypy <changed src files>
.venv/bin/ruff check --select C901 src/specify_cli/cli/commands/agent/tasks_move_task.py src/specify_cli/cli/commands/agent/tasks_move_task_hops.py src/specify_cli/cli/commands/agent/tasks_move_task_executor.py
```

Classify any red against the base before calling it yours (CLAUDE.md "baseline-red gotcha"). The base `make test-fast` is 3017 passed / 7 skipped.

## Test Strategy

- Red-first ATDD (T001) through the real CLI and a real git repository. Unit tests for the pure helpers (T002, T003).
- Non-vacuity: every "absent" assertion has a positive control on the same fixture.
- Typed sources: mypy on every changed `src/` file; zero new suppressions.

## Risks & Mitigations

- **Six sources drift apart again.** Mitigation: a single combiner, plus a test asserting that all four event fields are equal on the same approval.
- **Claimant-definition change breaks fixtures that seed forced claims.** Mitigation: re-pin to unforced claims, which is how `agent action review` records them.
- **`_do_move_task` complexity.** Mitigation: fact gathering stays in `_mt_gather_late_facts`.
- **Hidden callers of `_detect_reviewer_name`.** Mitigation: grep `src` and `tests`; `tasks.py` re-export.

## Review Guidance

- Confirm the red commit precedes the implementation commits and was red on the base.
- Confirm the absence assertions search the whole event JSON, with a positive control present.
- Confirm no `durably_persisted` condition still guards the **reviewer** (only the commit and revert semantics).
- Confirm `grep -rn "user.name\|_detect_reviewer_name\|synthetic_auto_approval_ref(" src/specify_cli/cli/commands/agent` shows nothing on the approval path.
- Confirm no edit to `workflow*.py`, `prompt_builder.py`, `status/__init__.py` or the consolidation package.

## Progress & Status

Progress lives in the status event log. Use `spec-kitty agent tasks add-history WP01 --note "<what you did>" --mission approval-honesty-01M78J9S`.

Implementation command:

```bash
spec-kitty agent action implement WP01 --agent <name> --mission approval-honesty-01M78J9S
```
