---
work_package_id: WP02
title: Approver must be the review claimant
dependencies:
- WP01
requirement_refs:
- FR-005
- NFR-003
- C-004
- C-007
- SC-004
planning_base_branch: fix/3044-approval-honesty
merge_target_branch: fix/3044-approval-honesty
branch_strategy: Planning artifacts for this mission were generated on fix/3044-approval-honesty. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/3044-approval-honesty unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
- T010
- T011
- T012
phase: Phase 2 - Refusals and cycles
history:
- at: '2026-11-12T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/tasks_transition_core.py
create_intent:
- tests/specify_cli/cli/commands/agent/test_approval_honesty_claimant.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/tasks_transition_core.py
- tests/specify_cli/cli/commands/agent/test_approval_honesty_claimant.py
- tests/specify_cli/cli/commands/agent/test_move_task_structured_actor_6400.py
- tests/specify_cli/cli/commands/agent/test_move_task_approval_evidence.py
- tests/specify_cli/cli/commands/agent/test_move_task_approval_body_collision.py
- tests/specify_cli/cli/commands/agent/test_move_task_done_issue_matrix_orchestrator.py
- tests/integration/test_ac5_hash_guard.py
- tests/review/test_verdict_save_performance.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Approver must be the review claimant

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check `review_ref` in the event log (`spec-kitty agent tasks status --mission approval-honesty-01M78J9S`).
- **You must address all feedback** before your work is complete.
- **Report progress** with `spec-kitty agent tasks add-history WP02 --note "..." --mission approval-honesty-01M78J9S`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

Today any `--agent` can approve a work package that another identity claimed for review (#7573).
A supervisor running `move-task WP11 --to approved --agent kitty-orchestrator` becomes the
approver. `_guard_agent_ownership` (`tasks_transition_core.py:537-607`) compares only the
**bare tool** (`_actor_key`), so it misses a same-tool supervisor such as
`claude:sonnet:supervisor` against `claude:sonnet:reviewer-renata`.

**Done when:**
- An **unforced** `in_review -> approved` or `in_review -> done` whose approver identity
  (`--agent`, else `--reviewer`) is not `same_review_identity`-equal to the review claimant
  refuses with code **`APPROVER_NOT_CLAIMANT`**. It exits 1, writes nothing, names both identities
  and gives the remedy: "have the claimant record the verdict (`--agent <claimant>`), or, as an
  operator override, `--force` (recorded as a forced move, not a review)".
- `--agent` and `--reviewer` both passed and not identity-equal → the same refusal on any approval
  lane.
- No claimant (a forced or placeholder claim, or no claim) → this guard does not apply. Direct
  approvals from `for_review`/`in_progress` keep today's behaviour, including the existing
  `REVIEW_NOT_INDEPENDENT`.
- `--force` bypasses the guard (operator ruling `closure`; a residual documented in WP04).
- Requirements: FR-005, NFR-003, C-007, C-004; SC-004.

## Context & Constraints

- Read `plan.md` §"Refusals and where they run", `research.md` R2-R4 and R9,
  `contracts/move-task-approval.md`.
- Decisions: `claimant_mismatch`, `claimant_remedy`, `codes_and_reviewer`, `claimant_definition`.
  There is **no** re-claim route: `agent action review` by another identity collides
  (`status/review_claim_predicate.py:75-95`), and `in_review -> for_review` does not exist.
- WP01 delivered `latest_review_claim_identity` and `same_review_identity`
  (`status/review_roles.py`) and the reviewer-of-record combiner. **Reuse them; do not add a second
  equality rule.**
- The guard is **pure** and sits in `_GUARDS` (`tasks_transition_core.py` about line 933) **right
  after** `_guard_agent_ownership`. It is a sibling of the existing ownership authority, not a new
  module.
- The code constant lives in `tasks_transition_core.py`, not in `consolidation/wp_evidence.py`
  (C-004), with no `SINGLE_BRANCH_*` alias.
- Do not touch `workflow*.py`, `prompt_builder.py`, `status/__init__.py` or consolidation.

## Branch Strategy

- **Planning base branch**: `fix/3044-approval-honesty` (via the Mission topic branch)
- **Merge target branch**: `fix/3044-approval-honesty`

Workspace: `spec-kitty agent action implement WP02 --agent <name> --mission approval-honesty-01M78J9S`.

## Subtasks & Detailed Guidance

### Subtask T008 – Red-first: claimant mismatch end-to-end

- **Files**: new `tests/specify_cli/cli/commands/agent/test_approval_honesty_claimant.py`. Reuse WP01's fixture helpers (the 4670 seam) with an **unforced** claim.
- **Cases**:
  1. Claim `claude:sonnet:reviewer-renata`; approve with `--agent kitty-orchestrator`. Expect exit 1, `APPROVER_NOT_CLAIMANT` in stdout/stderr and in the `--json` diagnostic `code`, both identities named, and the remedy text present.
  2. Same tool, different profile: `--agent claude:sonnet:supervisor`. Refused. The existing ownership guard misses this one, so it is the key new behaviour.
  3. `--reviewer kitty-orchestrator` with no `--agent`. Refused.
  4. `--agent claude:sonnet:reviewer-renata --reviewer someone-else`. Refused.
  5. `--to done` straight from `in_review` by a non-claimant. Refused.
  6. Positive control: approval by the claimant (with or without `--agent`) succeeds.
  7. `--force --agent kitty-orchestrator`. Succeeds as a forced move: reviewer `kitty-orchestrator`, reference `force-override`.
  8. **NFR-003**: for cases 1-5, `status.events.jsonl`, every `review-cycle-*.md` and `git status --porcelain` are byte-identical before and after.
  9. **Boundary documentation**: `--skip-review-artifact-check` over a rejected verdict plus a non-claimant. The pre-existing override record is written (out of scope, follow-up). Assert exactly that record and nothing else, with a comment that this pins today's ordering.
  10. Bare tool vs profiled claimant: claim `codex::reviewer-renata`, approve `--agent codex`. Refused (strict equality).
- **Commit**: `test(review): pin approver-must-be-claimant (red, #7573)` before implementation.

### Subtask T009 – Claimant fact on the request

- **Steps**:
  1. Add `review_claimant: str | None = None` to `MoveTaskRequest` (`tasks_transition_core.py:138`).
  2. Populate it where the request is built or rebuilt in `tasks_move_task.py` (`_mt_gather_late_facts`, or the pass-1 request build). Use WP01's `latest_review_claim_identity`.
     - **Out-of-map edit:** `tasks_move_task.py` is WP01-owned. Keep the edit to the minimal wiring line(s), and record the rationale in `add-history`: "one-line wiring of the WP02 guard input (ownership-map leeway)".
  3. The value must be available in **pass 1** of `decide_transition`, because the guard runs there, before any persist this mission adds. If the claimant is only computed in the late facts, populate it in the early request instead. Check `_mt_run_decision` (`tasks_move_task.py` about lines 1719-1735).

### Subtask T010 – Pure guard and code

- **Steps**:
  1. `APPROVER_NOT_CLAIMANT = "APPROVER_NOT_CLAIMANT"` (module constant; add it to the module's public names if the module declares them).
  2. `_guard_review_claimant(req) -> RefuseExit1 | None`:
     - return `None` if `req.force`, if the target is not in `_APPROVAL_LANES`, or if `req.old_lane` is not `in_review` **and** there is no `--agent`/`--reviewer` conflict;
     - `--agent` and `--reviewer` both present and not `same_review_identity` → refuse;
     - from `in_review`, with `req.review_claimant` not `None`, and the approver identity (`req.agent or req.reviewer`, if any) not `same_review_identity`-equal to the claimant → refuse;
     - no approver given → it resolves to the claimant (WP01), so no refusal.
  3. The refusal follows the move-task shape: `RefuseExit1(error, diagnostic={..., "code": APPROVER_NOT_CLAIMANT, ...}, console_warning=(...))`. Mirror `_guard_agent_ownership`'s diagnostic keys. Start the error text with the code, as `REVIEW_NOT_INDEPENDENT` does: `"APPROVER_NOT_CLAIMANT: WP01 is under review by <claimant>; <approver> cannot record its verdict. Have the claimant record it (--agent <claimant>), or, as an operator override, use --force (recorded as a forced move, not a review)."`
  4. Insert it into `_GUARDS` right after `_guard_agent_ownership`. If `_guard_agent_ownership` already refused (different tool), its message stands. Do not double-report, and do not change its text or code.
  5. Check whether `MoveTaskRequest` needs a `reviewer` field. If `req.reviewer` does not exist, add it next to `agent` and populate it alongside `review_claimant` (the same leeway line).
- **Complexity**: keep the guard ≤ 10. Extract a small pure `_approver_identity(req)` if needed.

### Subtask T011 – Re-pin fixtures whose claimant differs from the approver

These tests seed a claim as one identity and approve as another. Under the new rule they refuse.
For each one, **read the test's intent**:
- If it is testing something unrelated to identity, re-pin the fixture so the claim is by the
  approving identity.
- If it deliberately tests a cross-identity approval, convert it to assert `APPROVER_NOT_CLAIMANT`
  or `--force`.

| Test | Shape today |
|---|---|
| `test_move_task_approval_evidence.py` (2 tests) | claim `test`, approve `--reviewer reviewer-renata` |
| `test_move_task_approval_body_collision.py` (4 tests) | claim `test`, approve `--agent reviewer-renata` |
| `test_move_task_done_issue_matrix_orchestrator.py::test_move_task_approved_accepts_the_same_in_mission_row` | same pattern |
| `test_move_task_structured_actor_6400.py::test_review_approval_with_profile_flag_is_a_reviewer_actor` | `--agent codex` vs claimant `codex::reviewer-renata` (strict equality refuses) |
| `tests/integration/test_ac5_hash_guard.py:229-234` | claim `--agent codex`, approve `--agent codex --reviewer reviewer-renata` |
| `tests/review/test_verdict_save_performance.py` (`test_uncontended…`) | claimant `benchmark-fixture`, `--reviewer reviewer-renata` |

Also run `tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py`. If it goes red,
classify it (the plan squad flagged `:866` as possibly already vacuous) and report it; do not
widen ownership without an `add-history` rationale.

### Subtask T012 – Validation

```bash
make test-fast
.venv/bin/python -m pytest -q tests/specify_cli/cli/commands/agent/test_approval_honesty_claimant.py tests/specify_cli/cli/commands/agent/test_approval_honesty_identity.py tests/specify_cli/cli/commands/agent/ -k "move_task or approval or verdict or review"
.venv/bin/python -m pytest -q tests/integration/test_ac5_hash_guard.py tests/review/test_verdict_save_performance.py tests/integration/review/test_approve_without_force.py tests/integration/test_6715_squad_identity_and_evidence.py tests/integration/test_7159_implement_claim_profile.py
.venv/bin/python -m pytest -q tests/status tests/review
.venv/bin/python -m pytest -q tests/architectural/test_status_events_writes_gate.py tests/architectural/test_exemption_registry_ratchet.py tests/architectural/test_layer_rules.py
.venv/bin/ruff check <changed>; .venv/bin/ruff format --check --force-exclude <changed>; .venv/bin/mypy <changed src>; .venv/bin/ruff check --select C901 <changed src>
```

Record each command with its counts in `add-history`. If `tests/integration/test_6715_*` runs
slowly (the plan squad saw >10 minutes), run the single most relevant test with `-k` and say so.

## Test Strategy

- Red-first through the CLI; the positive controls (cases 6, 7) share the refusal fixture.
- The byte-identity check (NFR-003) uses file hashes plus `git status --porcelain`.

## Risks & Mitigations

- **Double refusal with `_guard_agent_ownership`.** The ordering in `_GUARDS` gives the first refusal; test the different-tool case to confirm which text appears, and keep it stable.
- **Claimant missing in pass 1.** The guard silently never fires. Case 2 is the non-vacuity proof: it must be red on base and green after.
- **Over-refusal of direct approvals.** Case 6 and the unchanged direct-approval tests in the 4670 file guard against it.

## Review Guidance

- The guard is pure and uses WP01's `same_review_identity`; no new equality helper.
- Case 2 (same tool, different profile) is red on base and green after.
- The out-of-map wiring in `tasks_move_task.py` is minimal and has its rationale recorded.
- The remedy names `--force` and the claimant, never `agent action review` (decision `claimant_remedy`).

## Progress & Status

`spec-kitty agent tasks add-history WP02 --note "<what you did>" --mission approval-honesty-01M78J9S`.

Implementation command:

```bash
spec-kitty agent action implement WP02 --agent <name> --mission approval-honesty-01M78J9S
```
