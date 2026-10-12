# Tracer — Approach

How the mission's approach evolves. One dated entry per shift.

- **2026-10-12 (initial)** — Two read-only pre-spec squads (code-grounding + tickets-discovery) ran before the spec. Approach fixed by their findings: move the marker-gated `validate_stage` into the shared top-layer seam `specify_cli/cli/commands/next_cmd.py::next_step` (covers native + orchestrator-api `next`), and wrap native `agent … finalize-tasks` in the existing `finalization_scope` (covers the agent-lifecycle surface and makes native finalize take `authoring_lock`). The orchestrator-api `_completion_gate` is removed so there is a single enforcement authority.
- **2026-10-12** — Divergence from the operator's literal seam hint ("runtime-bridge composition advance / `plan_advance`-`commit_advance`"): the runtime layer may not import `specify_cli.design` validators (`test_layer_rules.py`), so the gate lands in `next_step` (top layer) which the same completion path flows through. Honours intent, respects the enforced boundary. Will be called out in the PR.
- **2026-10-12** — ATDD red-first: native `next` + native `finalize-tasks` refusal cases added to `tests/specify_cli/orchestrator_api/test_planning_client_journey.py`, RED on `origin/main`, GREEN on the fix.
