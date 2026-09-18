---
work_package_id: WP01
title: Fresh full-identity claim reconciliation (#4665)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-010
planning_base_branch: fix/actor-identity-representation
merge_target_branch: fix/actor-identity-representation
branch_strategy: Planning artifacts for this mission were generated on fix/actor-identity-representation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/actor-identity-representation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-actor-identity-representation-01M2T0ER
base_commit: a4fb62704da0ea66860b74d4e1dfadd1d4d162f2
created_at: '2026-09-18T11:03:21.985266+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
history:
- event: created
  at: '2026-09-18T10:41:10Z'
  note: Initial generation from /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- tests/status/test_actor_identity_reconciliation_4665.py
- tests/specify_cli/cli/commands/agent/test_implement_compact_identity_4665.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/status/work_package_lifecycle.py
- src/specify_cli/status/emit.py
- src/specify_cli/cli/commands/implement.py
- src/specify_cli/cli/commands/agent/workflow_executor.py
- tests/status/test_actor_identity_reconciliation_4665.py
- tests/specify_cli/cli/commands/agent/test_implement_compact_identity_4665.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile:

```
/ad-hoc-profile-load python-pedro
```

Apply ATDD/red-first discipline (charter C-011, ADR 2026-07-17-1): the failing regression is
committed BEFORE the fix. Never present "looks fixed" as evidence — witness red→green in a real run.

---

## Objective

Fix #4665: `spec-kitty agent action implement WP## --agent codex:gpt-6:python-pedro:implementer`
today creates the lane, moves the WP to `in_progress`, then **rejects its own claim** and prints
no prompt. Reconcile the two actor representations so a fresh full-identity claim completes in one
invocation, same-identity resume is idempotent, a different identity is refused, and generic-actor
claims stay re-claimable.

## Root (grounded, file:line)

- `status/work_package_lifecycle.py:103` `_actor_key` → `status/models.py:152` `actor_identity_str`:
  a **dict** actor projects to bare `tool` (`codex`); a **compact string** actor is returned
  **verbatim** (`codex:gpt-6:python-pedro:implementer`). `_actors_compatible` (`:111`) compares
  these unequal → `WorkPackageClaimConflict` (`:52`).
- Two divergent claim-emit sites: the compact-string workspace-create claim
  (`cli/commands/implement.py:1881` `effective_actor`) vs the structured-dict workflow claim
  (`cli/commands/agent/workflow_executor.py:744` `_implement_start_claim` → `status/emit.py:1305`
  `build_self_asserting_actor`).
- Generic-actor allowance: `GENERIC_IMPLEMENTATION_ACTORS = {"implement-command","unknown","user"}`
  (`work_package_lifecycle.py:49`), a bare-string `in` test — why agentless resume works today.

## Constraints (binding)

- **C-002/C-005**: Do NOT edit `actor_identity_str`/`decode_actor` (byte-identical to the upstream
  `spec-kitty-events` reducer; the reduced `actor` slot is written upstream). Reconcile ONLY in the
  CLI-local comparison layer (`_actor_key`/`_actors_compatible`).
- The identity key stays a **bare string** — never a tuple/struct (the generic-actor `in` test).
- Do NOT fold role/profile into the identity key: the impl-claim key is tool-scoped and role-blind
  by design; reviewer-vs-implementer distinctness is a SEPARATE review-claim role channel
  (`review_claim_decision`, defined in `status/review_claim_predicate.py:56`, called from
  `work_package_lifecycle.py:335`; it degrades to ALLOW on a stale/None role). A full-tuple key
  would also make one agent's dict form (model may be `None`) and compact form (model present)
  compare UNEQUAL — reintroducing #4665.

## Red-first evidence protocol (binding, all regression subtasks)

Commit the regression as its OWN commit BEFORE the fix commit. In that commit body (and the PR)
record: the base SHA, and the VERBATIM failing output of the SPECIFIC red assertion(s). Name which
assertion(s) are red-on-base vs which are pre-existing-green. The baseline is the lane tip at the
moment this WP starts (predecessors have landed); if a predecessor already greened an assertion, do
NOT fabricate a red — record that the defect was coupled to WP0N and cite the predecessor commit. A
distinct reviewer re-runs the regression on the recorded base SHA and must personally witness the
named red assertion(s) fail.

## Subtasks

### T001 — Red-first regression (commit FIRST, RED on base)
Add `tests/status/test_actor_identity_reconciliation_4665.py` (unit) and
`tests/specify_cli/cli/commands/agent/test_implement_compact_identity_4665.py` (live fresh-worktree
integration), both `@pytest.mark.regression` with the issue ref. Assert: (1) fresh
`implement --agent codex:gpt-6:python-pedro:implementer` moves to `in_progress` AND renders the
prompt in one call, no self-conflict; (2) same-identity re-invoke = idempotent resume; (3)
different identity refused; (4) a generic-actor-owned WP is re-claimable.

**Red-on-base assertion (MF2):** the assertion that MUST fail on base is (1)'s *prompt-rendered-in-
one-invocation AND no self-conflict / "already claimed" error* — NOT the move to `in_progress`
(the buggy path already reaches `in_progress`, so a test asserting only that is green-on-base and
does not qualify as the #4665 regression). Follow the Red-first evidence protocol above.

**Harness (extend, don't build):** extend
`tests/specify_cli/cli/commands/agent/test_implement_runtime_frontmatter_claim.py` (drives the real
CLI claim with status emission+reduction, git side monkeypatched; uses `tests/lane_test_utils.py`
`write_single_lane_manifest`/`lane_worktree_path`). Siblings: `test_claim_event_source.py`,
`test_implement_single_resolution.py`.

### T002 — Reconcile the comparison key
In `_actor_key`/`_actors_compatible`, make a compact-string actor project to the SAME tool-scoped
bare-string key a dict yields (parse `tool:model:profile:role` → tool). Keep the return a bare
string; keep the `GENERIC_IMPLEMENTATION_ACTORS` membership intact. Reuse the closed #2861 compact
parser `parse_agent_boundary_string` (`status/emit.py:1277`) rather than inventing new parsing.

### T003 — Align the two emit sites; retain metadata
Ensure the workspace-create claim (`implement.py`) and the workflow claim (`workflow_executor.py`)
agree on the recorded identity so the second claim never conflicts with the first. Prefer the
smallest diff (route `implement.py`'s claim through the canonical actor shape, or rely on T002's
reconciled key). Verify the supplied `model`/`profile`/`role` survive into the recorded state
(FR-003).

### T004 — Matrix + slot-convergence tests (NFR-002, US1-AC5)
Add the representation × comparison matrix with named rows: (a) same agent dict vs compact → EQUAL
on the key; (b) generic actor still matches the allowance; (c) reviewer-vs-implementer same-tool →
REFUSED at the review-claim seam (assert on that channel, NOT the identity key); (d) same-tool
differing-profile implementers → document the tool-scoped behavior (do not silently change it).
Assert the transition `actor` slot and runtime `agent` slot converge to the same canonical identity
after a claim.

### T005 — Green + gates
Witness all regressions GREEN. Run `ruff check`, `ruff format --check`, `mypy --strict` on touched
modules; keep touched-function complexity ≤15; zero new suppressions.

## Branch Strategy

Planning branch: `fix/actor-identity-representation`. Final local merge target:
`fix/actor-identity-representation`. Execution runs in this WP's computed lane worktree from
`lanes.json` (allocated by `spec-kitty implement WP01`). Do not hand-construct worktree paths.

## Test strategy

`tests/status/` (unit) + `tests/specify_cli/cli/commands/agent/` (live claim). Run the targeted
files plus `tests/status/` as the owning subsystem. Red-first before the fix; green after.

## Definition of Done

- FR-001/002/003/010 satisfied; T001/T004 regressions green; SC-001 met (one-invocation claim +
  metadata retained). No edit to `actor_identity_str`/`decode_actor` or the shared reducer. Gates
  clean. Distinct reviewer approves red→green.

## Reviewer guidance

Confirm the key is still a bare string; the generic-actor `in` test still matches; role distinctness
is asserted on the review channel, not the key; the shared projection is byte-unchanged; and the
live integration test genuinely exercises the fresh-worktree compact-identity path (not a stub).
