---
work_package_id: WP04
title: move-task --agent persistence (#3029, representation half)
dependencies:
- WP03
requirement_refs:
- FR-009
planning_base_branch: fix/actor-identity-representation
merge_target_branch: fix/actor-identity-representation
branch_strategy: Planning artifacts for this mission were generated on fix/actor-identity-representation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/actor-identity-representation unless the human explicitly redirects the landing branch.
subtasks:
- T015
- T016
- T017
- T018
history:
- event: created
  at: '2026-09-18T10:41:10Z'
  note: Initial generation from /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_move_task_agent_persistence_3029.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- tests/specify_cli/cli/commands/agent/test_move_task_agent_persistence_3029.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile:

```
/ad-hoc-profile-load python-pedro
```

**Verify before you fix.** The reported symptom may be partially stale on current `main`. Do NOT
re-fix a working path; if it already works, close #3029 with evidence.

---

## Objective

Fold #3029 (representation half only): `move-task --agent <identity>` must persist the acting
identity into the reduced ownership slot so downstream ownership checks see it (the same slot as
WP03). Excluded (C-004): #3029's alternative resolutions (dropping the flag; demoting the accept
gate to a warning) and its #2993 precondition.

## Context (grounded)

- The claim fold writes `agent` on `planned → claimed` (`emit.py:269` threads `agent`), so the
  original "no agent key at all" symptom is likely partially stale. The open question is whether a
  plain `move-task --agent` (a non-claim hop) persists the acting identity.
- `_mt_emit_runtime_state` writes `fields["agent"] = st.agent` under `if not st.claim_emitted and
  st.agent` — verify whether that path actually fires for a `move-task --agent` and whether the
  reduced slot ends up carrying the identity.

## Subtasks

### T015 — Verify-first on the base
On the lane tip at WP start (WP01–WP03 landed), drive `move-task --agent <identity>` and read the
reduced ownership slot. Record the base SHA, the exact command, and the reduced-slot read. **Evidence
home (MF4):** put this transcript in the PR body AND append a dated note to the mission trace
`kitty-specs/actor-identity-representation-01M2T0ER/traces/design-decisions.md` (a small, allowed
out-of-map edit — record a one-line rationale; do NOT add a `kitty-specs/` path to this
code_change WP's `owned_files`, which would trip the kitty-specs ownership ban). If the identity
does NOT persist → red repro (T016/T017 fix). If it DOES persist → proceed to close-with-evidence.
Note the brownfield finding: `_mt_emit_runtime_state:2753-2754` DOES persist `agent` for a
non-claim, non-rollback `move-task --agent`, so the symptom is likely already green — lean toward
characterization + close.

### T016 — Regression (commit FIRST if reproducible; RED on base)
Add `tests/specify_cli/cli/commands/agent/test_move_task_agent_persistence_3029.py`
(`@pytest.mark.regression`, issue ref) asserting `move-task --agent <identity>` persists the acting
identity into the reduced ownership slot visible to a later ownership check. If reproducible: commit
the regression as its OWN commit before the fix, RED on base (record base SHA + verbatim failure). If
already green: land a **characterization** test pinning the correct behavior and say so explicitly.
Harness: extend `test_move_task_durability.py` / `test_tasks_move_task_pre_review_identity_read.py`.

### T017 — Fix or close-with-evidence
If reproducible: make `move-task --agent` persist the acting identity (minimal diff in
`tasks_move_task.py`; do NOT touch the `target_lane == PLANNED` suppression WP03 added). If already
green: make NO code change; close #3029 citing the T015 evidence (PR body + mission trace) and the
characterization test. Do not manufacture a no-op "fix".

### T018 — Green + gates
Witness green; `ruff`/`ruff format`/`mypy --strict` clean; complexity ≤15; zero new suppressions.

## Branch Strategy

Planning branch and local merge target: `fix/actor-identity-representation`. Runs in the shared
mission lane worktree from `lanes.json`, after WP03.

## Test strategy

`tests/specify_cli/cli/commands/agent/` (move-task persistence). Verify-first live check, then the
regression.

## Definition of Done

- FR-009 satisfied OR #3029 closed with evidence (no redundant change); SC-005 met; C-004 scope
  respected. Gates clean. Distinct reviewer approves.

## Reviewer guidance

Confirm the verify-first step was actually run (transcript present); that the WP either fixes a real
gap or closes with evidence rather than making a no-op "fix"; and that none of the excluded #3029
alternatives crept in.
