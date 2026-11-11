---
work_package_id: WP06
title: MissionNextInvoked via the write seam; report the bootstrap materialization
dependencies:
- WP05
requirement_refs:
- C-004
- C-005
- C-006
- FR-003
- FR-004
- FR-009
- FR-011
- SC-002
- SC-003
- SC-005
planning_base_branch: refactor/7310-status-read-door-s5
merge_target_branch: refactor/7310-status-read-door-s5
branch_strategy: Planning artifacts for this mission were generated on refactor/7310-status-read-door-s5. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into refactor/7310-status-read-door-s5 unless the human explicitly redirects the landing branch.
subtasks:
- T029
- T030
- T031
- T032
- T033
- T034
phase: Phase 3 - Writes and reporting
history:
- at: '2026-11-11T05:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent:
- tests/runtime/next/test_materialization_report.py
execution_mode: code_change
model: ''
owned_files:
- src/runtime/next/next_invocation_lifecycle.py
- src/runtime/next/runtime_bridge_decision_log.py
- src/specify_cli/cli/commands/next_cmd.py
- tests/specify_cli/next/test_next_invocation_lifecycle_seam.py
- tests/runtime/next/test_materialization_report.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – MissionNextInvoked via the write seam; report the bootstrap materialization

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

1. **Write through the write seam.** `emit_mission_next_invoked` (`next_invocation_lifecycle.py:341`) writes the `MissionNextInvoked` row into `mission-events.jsonl` in a directory it gets from `mission_context_for(...).artifact(STATUS_STATE).read_dir`. That is a read projection, and in empty or unmaterialized cells the directory does not exist, so the row is silently dropped. Use the status **write** seam instead (`.artifact(STATUS_STATE).write_dir`, or `placement_seam(...).write_dir(STATUS_STATE)`; the gate exempts `write_dir` / `commit_target`), proven by a read-after-write test (FR-009).
2. **Report the bootstrap materialization** (corrected DM-2, Decision Moment `01M73J4X57HKNF5RK7WVN8QHC5`; contract `contracts/next-materialization-report.md`). An advancing `next` whose bootstrap materialized or restored the coordination worktree prints `Materialized the coordination worktree for <mission> at <path>.` and, with `--json`, adds `"remediation": {"kind": "materialized_coordination_worktree", "path": "<path>"}`. It never does so for an already materialized worktree, query mode, a deleted branch, or a Mission without coordination topology (FR-003, FR-004). No new flag.
3. Gate: the last runtime entry is removed (`emit_mission_next_invoked`); floor 34 → 33; baseline 34 → 33. The gate files are an out-of-map edit (owned by WP04).
4. `make test-fast` green; Mission-level closeout checks (SC-002, SC-005).

## Context & Constraints

- Spec FR-003, FR-004, FR-009, FR-011, SC-002, SC-003, SC-005, C-004, C-005, C-006; plan IC-05; research R-4 (corrected), R-6; contract `contracts/next-materialization-report.md`.
- Evidence: `research/code-grounding.md` §0 row `emit_mission_next_invoked` (`mission_v1/events.py:56-66`, `append_event_log_lines` with `create_parents=False`; `emit_event` swallows the failure) and §5 (row dropped in the empty and unmaterialized cells; when materialized, the row lands untracked in the coordination worktree, #5938, which is out of scope here).
- Readers of `mission-events.jsonl`: `runtime_bridge_composition.py:352-394`. The read-after-write test must use the same read path they use.
- Detection of "bootstrap materialized it": the decision-log wrap (`runtime_bridge_decision_log._wrap_with_decision_git_log`) calls `write_dir(DECISION_LOG)`, which materializes, seeds or restores. Before that call, ask the door (`resolve_status_read`) for the declared source. A coordination ref source means the worktree was missing or empty. After the call, check whether the coordination worktree now holds the Mission directory. Carry `(path)` out of the wrap (e.g. a small return value or attribute on the wrapper), never through a global.
- The decision envelope: `Decision` in `src/runtime/next/decision.py:130` (`to_dict` at `:190`). Add an optional `remediation: dict[str, str] | None = None`, emitted by `to_dict` **only when set**, so the envelope stays byte-identical otherwise. That is an **out-of-map edit** in WP03's file; record it with `add-history`. Check consumers that validate the envelope (JSON schema tests for `next`, orchestrator-api) and run them.
- Rendering the human line: `src/specify_cli/cli/commands/next_cmd.py`, where the decision is printed. Print one line before the decision text, only when `remediation` is set, and never in query mode.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: populated by finalize-tasks
- **Merge target branch**: populated by finalize-tasks

> Populated automatically by `spec-kitty agent mission finalize-tasks`. Run `spec-kitty agent action implement WP06 --agent <name> --mission runtime-status-read-door-01M73HHB` (it depends on WP05).

## Subtasks & Detailed Guidance

### Subtask T029 – `MissionNextInvoked` via the write seam (red-first)

- **Steps**:
  1. Red test in `tests/specify_cli/next/test_next_invocation_lifecycle_seam.py`: for a coordination Mission whose worktree is **materialized**, the row is readable after `emit_mission_next_invoked` through the composition reader's path. That is likely green today, so it acts as the control. For a single_branch Mission it is readable as well. For an **unmaterialized** coordination worktree, pin the chosen outcome. If `write_dir` materializes, the row is now persisted (a fix, red today). If `write_dir` refuses, the row is dropped as today and the test pins the drop explicitly. Report which in `add-history`; this is the "open check" of research R-6.
  2. Replace the `read_dir` resolution with the write seam. Keep the best-effort `try/except` → `feature_dir=None`.
  3. Re-pin the existing mechanism pins at `:439` and `:607` (monkeypatched `mission_context_for`) to the write seam, keeping their domain assertions (owned fact used; degrade to None on exception).

### Subtask T030 – Red test: the materialization report

- **Steps**: new `tests/runtime/next/test_materialization_report.py`:
  - fixture: non-owned coordination Mission (WP01 planned, WP02 for_review, committed); cells empty and unmaterialized;
  - drive an advancing decision through `decide_next_via_runtime` (and one CLI run via `CliRunner` / the real `spec-kitty next --json --result success`; reuse `research/repro/advancing_cells.py`'s approach);
  - assert the JSON has `remediation.kind == "materialized_coordination_worktree"` and a `path` equal to the coordination worktree; human output has exactly one line `Materialized the coordination worktree for <mission> at <path>.`;
  - commit red.

### Subtask T031 – Detect in the wrap; carry on the decision

- **Steps**: implement the detection described in Context inside `runtime_bridge_decision_log.py`. Thread the result to where the `Decision` is built (`runtime_bridge.py`, WP05's file, as an out-of-map edit with a rationale) and set `decision.remediation`. Keep functions ≤ 15 complexity.

### Subtask T032 – Render

- **Steps**: add `remediation` to `Decision` and `to_dict` (only when set; out-of-map edit in `decision.py`); print the line in `next_cmd.py`. Run the `next` JSON schema / envelope tests.

### Subtask T033 – Negative tests [P]

- **Steps** (same new file): no `remediation` and no line for a materialized coordination worktree, query mode (no `--result`) on an unmaterialized worktree (query must not materialize; assert the worktree is still absent afterwards), a deleted coordination branch (flatten guidance unchanged, nothing materialized), and a single_branch Mission.

### Subtask T034 – Gate and fast tier

- **Steps** (out-of-map edit of WP04's gate files): delete `src/runtime/next/next_invocation_lifecycle.py::emit_mission_next_invoked::artifact(STATUS_STATE)`; set `_LIVE_HIT_FLOOR = 33`; change `_baselines.yaml` `legacy_read_allowlist` from 34 to 33 and append `Shrunk 34 -> 33 by runtime-status-read-door WP06; no src/runtime/next entry remains` to the justification. Then run `make test-fast`, and check SC-002: no allowlist key starts with `src/runtime/next/`.

## Test Strategy

- `PWHEADLESS=1 .venv/bin/python -m pytest -q -n 4 --dist loadfile tests/runtime/next/test_materialization_report.py tests/specify_cli/next/test_next_invocation_lifecycle_seam.py tests/specify_cli/cli/commands/test_next_owned_fact.py tests/next/test_next_command_integration.py tests/runtime/next/test_bootstrap_read_door.py tests/runtime/next/test_board_query_read_door_7507.py`
- Envelope consumers: `grep -rl "to_dict()\|decision_kind\|\"remediation\"" tests/next tests/runtime tests/orchestrator_api --include=*.py`; run the ones that assert the full envelope.
- Gates: `tests/architectural/test_status_read_single_door.py tests/architectural/test_ratchet_baselines.py tests/architectural/test_layer_rules.py tests/architectural/test_no_legacy_terminology.py`
- `make test-fast`; `ruff check`, `ruff format --check --force-exclude`, `mypy` on every changed source file.

## Risks & Mitigations

- **Envelope consumers reject an unknown key.** The key is only present when set; run the envelope tests.
- **False report** (claiming a materialization that did not happen). Detection needs both "ref source before" and "materialized after"; T033 pins every negative.
- **Query materializing** by accident. T033 asserts the worktree is still absent after a query.

## Review Guidance

- T029/T030 red commits before fixes; the R-6 open check is answered in `add-history`.
- `Decision.to_dict` output is byte-identical when `remediation` is unset (existing envelope tests unchanged).
- Gate at 33; no `src/runtime/next/` key left.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP06 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP06 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
