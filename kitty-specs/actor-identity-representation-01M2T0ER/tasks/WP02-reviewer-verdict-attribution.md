---
work_package_id: WP02
title: Reviewer verdict attribution (#4670)
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- FR-006
planning_base_branch: fix/actor-identity-representation
merge_target_branch: fix/actor-identity-representation
branch_strategy: Planning artifacts for this mission were generated on fix/actor-identity-representation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/actor-identity-representation unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
history:
- event: created
  at: '2026-09-18T10:41:10Z'
  note: Initial generation from /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_verdict_attribution_4670.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py
- src/specify_cli/cli/commands/agent/tasks_transition_core.py
- src/specify_cli/cli/commands/agent/workflow_executor.py
- tests/specify_cli/cli/commands/agent/test_verdict_attribution_4670.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile:

```
/ad-hoc-profile-load python-pedro
```

Red-first per ADR 2026-07-17-1. Historical events are immutable — corrections are additive
(NFR-001); never rewrite a prior event to fix attribution.

---

## Objective

Fix #4670: the generated review-completion command omits `--agent`, so an agent's verdict is
recorded with `actor.tool: user` (the configured git user) and null model/profile. Carry the
claimed reviewer identity into the recorded verdict — for BOTH approval and rejection — while
preserving genuine human approvals as a distinct case.

## Root (grounded, file:line — corrected by brownfield scout)

- **There is NO `--to rejected` in this 9-lane vocabulary.** A rejection verdict is emitted via
  `move-task --to planned --review-feedback-file`. So the completion-command handoff renders are
  **SIX** sites: approvals `workflow_executor.py:1960/2003/2124` (`--to approved`) AND rejections
  `workflow_executor.py:1966/2014/2125` (`--to planned --review-feedback-file`) — all six omit
  `--agent`. A patch touching only the `--to approved` lines silently leaves rejections attributed
  to the git user.
- **Behavioral root**: `tasks_move_task.py:2122` `st.actor = st.agent or "user"` — with `--agent`
  omitted the verdict actor becomes the git `user`. This is the load-bearing fix (T008).
- A reviewer resolver already exists (`_mt_resolve_reviewer_identity` @ `tasks_move_task.py:2196`)
  but is consulted only for the rejected-cycle artifact, not the approval actor.
- **Secondary / NOT live handoffs — decide explicitly, do NOT blindly force `--agent`:**
  `tasks_verdict_persistence.py:893` is a `reproduction_command` string baked into the
  `review-cycle-N.md` evidence artifact (provenance — thread the resolved identity here for an
  honest, replayable record); `tasks_transition_core.py:703` is a `_guard_done_ancestry` error hint
  (leave — no reviewer identity at render time).
- **OUT OF SCOPE (do not edit, do not assert on):** static docstring examples `tasks.py:757-758`
  and any `next_cmd.py` help text — these are not owned and carry no resolved reviewer at render.

## Subtasks

### T006 — Red-first regression (commit FIRST, RED on base)
Add `tests/specify_cli/cli/commands/agent/test_verdict_attribution_4670.py`
(`@pytest.mark.regression`, issue ref) — a FLAT `agent/` file, NOT a new `review/` subdir (a new
test dir trips the CI shard-map/path-filter routing gate). Drive the real claim → generated handoff
→ completion flow for BOTH approval AND rejection. Assert: verdict event actor == the claimed
reviewer identity (not `user`); `review_result.reviewer` carries the agent; review
evidence/reference retained; an identity-omitting completion resolves the active reviewer; a genuine
human approval (no agent claim) records the human. Red-on-base assertions = verdict-actor-is-agent
and resolver-fills-identity (the human-approval assertion is green-on-base — name it as such per the
Red-first evidence protocol). Model on `tests/integration/test_review_handoff.py`.

### T007 — Single completion-command render seam (six sites)
Thread the resolved reviewer identity through ONE completion-command render helper so every
generated APPROVAL (`--to approved`, `workflow_executor.py:1960/2003/2124`) AND REJECTION
(`--to planned --review-feedback-file`, `:1966/2014/2125`) carries the resolved `--agent`. If a
single helper is infeasible, add an enumerated-site regression whose site list is DERIVED FROM A
COMMITTED GREP (of the completion-command renderers, shown in the PR) — not hand-curated — asserting
each carries `--agent`, so a partial patch or a newly-added site fails. Do NOT assert on the static
help-text sites (out of scope above).

## Red-first evidence protocol (binding)

Commit the regression as its OWN commit BEFORE the fix; record the base SHA + verbatim failing
output of the named red assertion(s); name red-on-base vs pre-existing-green. Baseline = lane tip at
WP start (WP01 landed). A distinct reviewer re-runs on the recorded base SHA and witnesses the red.

### T008 — Resolve the active reviewer when --agent omitted
For an agent-driven completion that omits `--agent`, resolve the active claimed reviewer from the
event log (extend/reuse `_mt_resolve_reviewer_identity`) instead of defaulting to `st.agent or
"user"`. Keep the genuine human-approval path (no agent claim) attributing to the human — do not
fabricate an agent.

### T009 — Green + gates
Witness the regression GREEN (approval + rejection + resolver + human). `ruff`/`ruff format`/`mypy
--strict` clean; complexity ≤15; zero new suppressions.

## Branch Strategy

Planning branch and local merge target: `fix/actor-identity-representation`. Execution in the WP's
computed lane worktree from `lanes.json` (this WP shares the single mission lane with WP01/03/04 and
runs after WP01).

## Test strategy

`tests/specify_cli/cli/commands/agent/review/` (real claim→handoff→completion). Run the review test
directory as the owning surface.

## Definition of Done

- FR-004/005/006 satisfied; SC-002 met (approval AND rejection attributed to the agent, evidence
  retained, human case preserved); no historical event rewritten. Gates clean. Distinct reviewer
  approves red→green.

## Reviewer guidance

Verify the fix is behavioral (event-log resolution), not just report-text; that ALL render sites
carry `--agent` (or the enumerated-site regression covers them); rejection is attributed too; and a
real human approval still records the human.
