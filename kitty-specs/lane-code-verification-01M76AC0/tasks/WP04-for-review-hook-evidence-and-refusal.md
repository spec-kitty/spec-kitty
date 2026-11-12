---
work_package_id: WP04
title: The for_review hook records evidence and refuses a foreign tree
dependencies:
- WP01
- WP02
- WP03
requirement_refs:
- FR-007
- FR-008
- FR-009
- SC-002
- SC-004
- C-006
planning_base_branch: fix/7547-lane-code-verification
merge_target_branch: fix/7547-lane-code-verification
branch_strategy: Planning artifacts for this mission were generated on fix/7547-lane-code-verification. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7547-lane-code-verification unless the human explicitly redirects the landing branch.
subtasks:
- T015
- T016
- T017
- T018
phase: Phase 3 - Gate hook
history:
- at: '2026-11-12T05:35:56Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/tasks_move_task_gates.py
create_intent:
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_evidence_tree.py
- tests/review/fixtures/parity/foreign_tree__block0__force0.json
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/tasks_move_task_gates.py
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_evidence_tree.py
- tests/review/test_transition_gate_parity.py
- tests/review/fixtures/parity/foreign_tree__block0__force0.json
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – The for_review hook records evidence and refuses a foreign tree

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load `spec-kitty charter context --action implement` and read `CLAUDE.md` and `.kittify/charter/charter.md`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check `review_ref` via `spec-kitty agent tasks status --mission lane-code-verification-01M76AC0`.
- Record progress with `spec-kitty agent tasks add-history WP04 --mission lane-code-verification-01M76AC0 --note "..."`.

## Review Feedback

*[Filled from the status event log when this WP returns from review.]*

---

## Objectives & Success Criteria

`spec-kitty agent tasks move-task <WP> --to for_review`:

1. builds the lane test invocation through WP02's adapter
   `review.lane_test_invocation.lane_test_invocation_for(root, config_root=…, mission_slug=…, lane_id=…, probe=True)`
   for the resolved gate root (lane worktree, or the write checkout / owned checkout),
   **inside the existing fail-open** of the pre-dispatch resolution phase;
2. captures the evidence tree (`capture_evidence_tree`, WP01) **before** any test run;
3. when the probe is `foreign`: produces a `FOREIGN_TREE` verdict without dispatching any
   handler or running tests;
4. otherwise passes `run_environment(invocation, os.environ)` as `run_env` into the
   `TransitionGateContext` **and** into the override tier
   (`_mt_pre_review_gate_with_override_scope` → `evaluate_with_scope(run_env=…)`);
5. records `policy_metadata.pre_review_gate.evidence_tree` whenever an invocation was built
   (absent on the skip path, planning lanes and verdicts synthesized before inputs resolved
   — keeps `tests/review/test_verdict_candidate_exit.py` ~L240 green);
6. refuses a foreign tree: exit 1, `transition_applied: false`, human line
   `Pre-review gate refused (EVIDENCE_TREE_MISMATCH): <pkg> loads from <origin>, outside
   <lane>/src. Fix the lane's environment (its .venv's install points elsewhere) or re-run
   with --force to record a bypass.`, JSON diagnostic
   `{"result":"error","error_code":"EVIDENCE_TREE_MISMATCH","error":…,"transition_applied":false,"pre_review_gate":{…}}`
   — regardless of `review.fail_on_pre_review_regression`;
7. with `--force`: proceeds; `force_bypassed: true`, `bypassed_refusal: "EVIDENCE_TREE_MISMATCH"`,
   outcome stays `foreign_tree`, reason says no test run happened;
8. `unverified` never refuses; the skip flag/env var path is untouched (no probe runs).

Requirements: FR-006, FR-007, FR-008, FR-009, FR-010, FR-011, SC-002, SC-004, C-003, C-008.

## Context & Constraints

- `plan.md` §Design "Gate wiring" and "Aggregation (all consumers)"; contracts
  `contracts/pre-review-evidence-tree.md`; research dispositions A3, A5, A9, A10, T7, T10, T11.
- This module runs under mypy `follow_imports = "skip"` (see comments ~L285-298): pin
  cross-module returns with annotated locals as existing code does; no `# type: ignore`.
- `_mt_resolve_pre_review_workspace` returns only a `Path`. You need the lane id: add a
  sibling helper (or extend `_TransitionGateInputs` with `lane_id: str | None` resolved from
  the same `resolve_workspace_for_wp` call — do not resolve twice, and keep
  `tests/architectural/test_owned_checkout_single_authority.py` and
  `test_no_write_side_rederivation.py` green). Owned checkouts → no lane id.
- `config_root` = `_mt_config_authority_root(st)` (the repository root checkout, so a lane's
  stale config cannot change the command).
- Exhaustive consumer list to update (from the post-plan squad, verify each):
  `_mt_gate_representative` (~L1263: prefer `aggregate.refusing_verdicts[0]` when REFUSE),
  `_mt_translate_gate_verdicts` (~L1292: `force_bypassed = (block_enabled and force and
  bool(aggregate.blocking_verdicts)) or (force and bool(aggregate.refusing_verdicts))`, add
  `bypassed_refusal`), `_TransitionGateEffect` (+ `refused: bool`),
  `_mt_emit_transition_gate_effect` (~L1347: third branch, the only `error_code` precedent
  is `tasks_move_task.py` ~L1885 — follow its envelope style), `_mt_pre_review_gate_console_warning`
  (complexity 11: add the `FOREIGN_TREE` line via a small extracted helper so it stays ≤ 15),
  the byproduct restore keyed on `should_exit` (~L1418; follows automatically — verify).
- `--force` on `for_review` also skips other wards (review ward, unchecked-subtask check);
  that is existing behaviour — do not change it, just record which gate refusal was bypassed.
- Keep the signature of `_mt_translate_gate_verdicts` and `_mt_dispatch_transition_gates`
  (parity tests call them directly).

## Branch Strategy

- **Planning base branch**: `fix/7547-lane-code-verification` · **Merge target branch**: `fix/7547-lane-code-verification`

```bash
spec-kitty agent action implement WP04 --agent claude --mission lane-code-verification-01M76AC0
```

## Subtasks & Detailed Guidance

### Subtask T015 – Red tests through move-task (commit first)

- **File**: `tests/specify_cli/cli/commands/agent/test_tasks_move_task_evidence_tree.py` (in the CI matrix).
- **Harnesses to reuse** (read them first):
  - real gate run + evidence: `_run_move` + `_RecordingCoordRouter` + `_fixture_workspace`
    in `tests/review/test_pre_review_gate_integration.py` (~L369-470): real git, no CliRunner;
  - exit code + JSON envelope: `CliRunner().invoke(app, …)` with `_build_command_fixture` in
    `tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_gate_observability.py`
    (~L114); assert `router.status_calls == []` on refusal (no transition written).
- **Fixture**: a lane worktree with tracked `src/pkg/__init__.py`, plus a lane `.venv`
  built with `python -m venv --without-pip` whose `.pth` points at the repository root
  checkout's `src` (foreign) — the same fixture with the `.pth` rewritten to `<lane>/src` is
  the positive control (verified). Configure a cheap `review.test_command` (e.g. a `python3 -c`
  that writes a JUnit file, as existing integration fixtures do).
- **Cells**:
  1. foreign, no force, block off → exit 1, `error_code == "EVIDENCE_TREE_MISMATCH"`,
     `transition_applied is False`, `pre_review_gate.outcome == "foreign_tree"`,
     `evidence_tree.probe.status == "foreign"`, no status event written, test command NOT run
     (assert its marker file absent).
  2. same, block on → same refusal (independent of `fail_on_pre_review_regression`).
  3. verified (same fixture, `.pth` → lane) → transition applied, `evidence_tree` recorded
     with `head` (40-hex), `dirty` bool, `probe.status == "verified"`, path relative.
  4. foreign + `--force`, block off → applied; `force_bypassed is True`,
     `bypassed_refusal == "EVIDENCE_TREE_MISMATCH"` (the old formula would give False — this
     cell goes red against it).
  5. no `src/` packages → `unverified`, never refused, `evidence_tree` present.
  6. skip flag and `SPEC_KITTY_SKIP_PRE_REVIEW_GATE=1` (delete the harness env var first:
     agent containers may export related `SPEC_KITTY_*` values) → probe spy never called,
     no `evidence_tree`; positive control: without the skip the spy is called once.
  7. `run_env` reaches the dispatched handler (spy on `evaluate_pre_review_gate`) and the
     override tier (WP frontmatter `pre_review_test_scope` set; spy on `evaluate_with_scope`).
- Existing ratchets that must stay green unchanged: `tests/review/test_pre_review_gate_integration.py`
  (its fixtures write `src/specify_cli/git/foo.py` without `__init__.py` → not probed →
  `unverified`, no refusal), `test_verdict_candidate_exit.py`, `test_transition_gate_parity.py`
  (existing cells).

### Subtask T016 – Hook builds invocation, probe, evidence

- In `_mt_resolve_transition_gate_inputs` (or a new helper it calls) build the invocation
  when `worktree_path` resolved, store it and the evidence tree on `_TransitionGateInputs`
  (new optional fields). Any exception → `None` (fail-open: evidence absent, gate behaves as
  today), never a refusal.
- In the verdict-resolution phase: if `inputs.invocation.probe.status == "foreign"`, return
  `[GateVerdict(outcome=FOREIGN_TREE, scope=<empty scope like _mt_empty_scope_verdict>, reason=…)]`
  without dispatch. Else `_mt_build_transition_gate_context(..., run_env=run_environment(...))`
  and pass the same `run_env` to the override-scope path.

### Subtask T017 – Refusal effect

- Representative, `refused` flag, emit branch, console line as listed above. Human output
  goes through the same `_tasks._output_error` used by the other two hard stops.

### Subtask T018 – Metadata and parity cell

- `_mt_pre_review_gate_metadata(...)`: add `evidence_tree` (the `to_dict()` form) only when
  provided; add `bypassed_refusal` only when a refusal was bypassed. Keep every existing key.
- Hand-author `tests/review/fixtures/parity/foreign_tree__block0__force0.json` following the
  existing cells' schema (the capture harness is retired) and make
  `tests/review/test_transition_gate_parity.py` pick it up (check whether it globs or lists).

## Test Strategy

```bash
uv run --frozen python -m pytest tests/specify_cli/cli/commands/agent/test_tasks_move_task_evidence_tree.py tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_gate_observability.py tests/review/test_pre_review_gate_integration.py tests/review/test_transition_gate_parity.py tests/review/test_verdict_candidate_exit.py -q
uv run --frozen python -m pytest tests/specify_cli/cli/commands/agent -q   # owning dir; record count
uv run --frozen python -m pytest tests/architectural/test_owned_checkout_single_authority.py tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_status_read_single_door.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen ruff check <changed files>; uv run --frozen ruff format --check --force-exclude <changed files>; uv run --frozen mypy <changed src files>
```

## Risks & Mitigations

- Hidden extra consumers of `AggregateDecision`: `grep -rn "AggregateDecision\.\|should_exit" src/ tests/` before finishing.
- A probe exception must never refuse (C-003 carve-out applies only to a proven foreign tree).
- Evidence paths in a tracked log: relative paths (WP01 handles it); assert in cell 3.

## Review Guidance

- Cells 1/3 share one fixture (foreign vs verified by the `.pth` target only).
- Cell 4 must fail against the old `force_bypassed` formula.
- No test run happens on refusal (cell 1 marker file).

## Activity Log

- 2026-11-12T05:35:56Z – system – Prompt generated via /spec-kitty.tasks
