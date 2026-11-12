---
work_package_id: WP03
title: Gate engine accepts a run environment and a refusal tier
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-011
- C-003
- C-008
- SC-005
planning_base_branch: fix/7547-lane-code-verification
merge_target_branch: fix/7547-lane-code-verification
branch_strategy: Planning artifacts for this mission were generated on fix/7547-lane-code-verification. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7547-lane-code-verification unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-lane-code-verification-01M76AC0
base_commit: e007c728bae78192f850fcf7333243f24ede8e32
created_at: '2026-11-12T06:16:44.131799+00:00'
subtasks:
- T010
- T011
- T012
- T013
- T014
phase: Phase 2 - Surfaces
history:
- at: '2026-11-12T05:35:56Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/review/
create_intent:
- tests/review/test_gate_run_environment.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/review/pre_review_gate.py
- src/specify_cli/review/baseline.py
- src/specify_cli/review/verdict_aggregation.py
- src/specify_cli/review/gate_registry.py
- tests/review/test_verdict_aggregation.py
- tests/review/test_gate_run_environment.py
- tests/review/test_gate_registry.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Gate engine accepts a run environment and a refusal tier

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load `spec-kitty charter context --action implement` and read `CLAUDE.md` and `.kittify/charter/charter.md`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check `review_ref` via `spec-kitty agent tasks status --mission lane-code-verification-01M76AC0`.
- Record progress with `spec-kitty agent tasks add-history WP03 --mission lane-code-verification-01M76AC0 --note "..."`.

## Review Feedback

*[Filled from the status event log when this WP returns from review.]*

---

## Objectives & Success Criteria

The review engine (no CLI concerns) gains:

1. `GateOutcome.FOREIGN_TREE = "foreign_tree"`.
2. A plain `run_env: Mapping[str, str] | None = None` parameter carried
   `TransitionGateContext` → handler → `evaluate_pre_review_gate` → `evaluate_with_scope`
   → `_evaluate_via_scope_source` → `_run_raw_command(env=…)`, and `evaluate_with_scope`
   → `run_scoped_tests_at_head(run_env=…)` (override tier). `None` keeps today's
   `_gate_run_env()` exactly (back-compat). When given, `PWHEADLESS=1` is still forced.
3. The override tier's uv-path strip uses WP01's `INTERPRETER_REDIRECT_KEYS`
   (`_UV_ENV_LEAK_KEYS` removed, one list); with `run_env` given, the `sys.executable`
   fallback runs in that environment (#5985 item 2).
4. Baseline symmetry: `baseline._run_command_for_baseline` runs with
   `run_environment(build_lane_test_invocation(cwd, command=None), _gate_run_env())` so the
   baseline worktree gets the same strip + `<base>/src` rule as the head (no lane test env,
   no lane id). Baseline **source identity is unchanged** (C-008).
5. Aggregation: `AggregateDecision.REFUSE` between TERMINAL and BLOCK; any
   `FOREIGN_TREE` verdict refuses when `not force`, regardless of `block_enabled`;
   `AggregateVerdict.refusing_verdicts`; `should_exit` true for REFUSE. With `force` the
   decision is WARN_PROCEED and `refusing_verdicts` still lists the foreign verdicts (so the
   hook can record the bypass).

Requirements: FR-006, FR-008 (engine half), FR-009 (engine half), FR-011, C-003, C-008.
The hook wiring, refusal message and metadata are WP04.

## Context & Constraints

- `plan.md` §Design "Gate wiring" bullets and the "Aggregation (all consumers)" bullet;
  `research.md` dispositions A2/T5 (baseline symmetry), A3 (override tier is called from
  the hook directly — your `run_scoped_tests_at_head(run_env=…)` and
  `evaluate_with_scope(run_env=…)` parameters are what WP04 passes there), A5, T11.
- `review` may import the WP01 leaf `specify_cli.lanes.lane_invocation`; it must not import
  the probe into the head run path (the probe runs in the hook, WP04).
- `tests/review/test_transition_gate_parity.py` dispatches with a `SimpleNamespace`
  context: read `ctx.run_env` with `getattr(ctx, "run_env", None)` in the handler, and give
  the dataclass field a default of `None`.
- `GateOutcome` is a `StrEnum`; no test iterates over all members, so adding one is safe;
  `test_verdict_aggregation.py` pins `_TERMINAL_OUTCOMES` with explicit tuples — add new
  cells, do not loosen existing ones.
- Complexity ≤ 15; `_observe_process` is at 10 — don't touch it.

## Branch Strategy

- **Planning base branch**: `fix/7547-lane-code-verification` · **Merge target branch**: `fix/7547-lane-code-verification`

```bash
spec-kitty agent action implement WP03 --agent claude --mission lane-code-verification-01M76AC0
```

## Subtasks & Detailed Guidance

### Subtask T010 – Red tests (commit first)

- **`tests/review/test_gate_run_environment.py`** (new):
  1. *Declared path receives `run_env`*: a `ScopeSource` stub whose `test_command()` returns
     `["sh", "-c", "python3 -c 'import json,os;json.dump(dict(os.environ),open(\"env.json\",\"w\"))'"]`
     (or reuse the fake recorder approach in `tests/review/test_interpreter_and_scoped_lock.py`
     ~L140-210); call `evaluate_pre_review_gate(..., run_env={...without PYTHONPATH..., "MARK": "1"})`
     with an inherited `PYTHONPATH`/`VIRTUAL_ENV`/`UV_PROJECT_ENVIRONMENT` monkeypatched into
     `os.environ` → recorded env has `MARK`, `PWHEADLESS=1` and **none** of the three keys.
     Same fixture with `run_env=None` → the three inherited keys are present (back-compat
     positive control).
  2. *Override tier*: `evaluate_with_scope(scope_with_targets, scope_source=None, run_env=…)`
     with `resolve_pytest_command` forced to the `sys.executable` fallback (monkeypatch
     `shutil.which("uv")` → None or the module's own seam) → the launched process env equals
     `run_env` (+ `PWHEADLESS`). Spy on `_launch_scoped_process` to capture `env`; do not
     run real pytest.
  3. *Baseline symmetry*: spy `_run_raw_command` from `baseline._run_command_for_baseline`
     with a baseline cwd that has a tracked `src/pkg/__init__.py` and no `.venv` → `env`
     lacks the redirect keys and has `PYTHONPATH=<cwd>/src`; a cwd without `src/` packages
     → no `PYTHONPATH`. (Add an `env` keyword to `_run_raw_command` in T011 so the spy sees it.)
  4. *Baseline identity untouched*: re-run `tests/review/test_pre_review_gate_source_mismatch.py`
     and `tests/review/test_baseline_head_parity.py` unchanged (C-008 ratchet).
- **`tests/review/test_verdict_aggregation.py`** (add cells, keep all existing):
  `FOREIGN_TREE` × `block_enabled ∈ {False, True}` × `force ∈ {False, True}`:
  not forced → `REFUSE`, `should_exit`, `transition_applied is False`,
  `refusing_verdicts == (v,)`; forced → `WARN_PROCEED`, `refusing_verdicts == (v,)`.
  TERMINAL still wins over FOREIGN_TREE (mixed set). FOREIGN_TREE + NEW_FAILURES with block
  on, not forced → `REFUSE` (refusal precedes block).
- **`tests/review/test_gate_registry.py`**: the handler forwards `ctx.run_env` to
  `evaluate_pre_review_gate` (spy).

### Subtask T011 – `FOREIGN_TREE` and `run_env` plumbing

- `pre_review_gate.py`:
  - add the enum member with a comment (`# #7554: the hook's probe proved the run would load
    another tree's code; refused unless --force`).
  - `def _gate_run_env(run_env: Mapping[str, str] | None = None) -> dict[str, str]`: `None` →
    today's behaviour; else `dict(run_env)` + `PWHEADLESS=1`.
  - `_run_raw_command(..., env: Mapping[str, str] | None = None)` → `_gate_run_env(env)`.
  - `run_scoped_tests_at_head(..., run_env=None)`: `env = _gate_run_env(run_env)`; keep the
    uv-path strip but via `INTERPRETER_REDIRECT_KEYS`; delete `_UV_ENV_LEAK_KEYS` and make
    `_strip_interpreter_path_env` use the imported tuple (or inline its one caller).
  - `evaluate_with_scope(..., run_env=None)` and `_evaluate_via_scope_source(..., run_env=None)`
    and `evaluate_pre_review_gate(..., run_env=None)` thread it through.
  - Update docstrings briefly (one sentence each); no behaviour change when `None`.

### Subtask T012 – Baseline symmetry

- In `baseline._run_command_for_baseline` (lazy imports are already the pattern there):
  `from specify_cli.lanes.lane_invocation import build_lane_test_invocation, run_environment`
  and pass `env=run_environment(build_lane_test_invocation(cwd, command=None), _gate_run_env())`
  to `_run_raw_command`. Leave `source_identity` code untouched.

### Subtask T013 – Context field and handler

- `gate_registry.TransitionGateContext`: add `run_env: Mapping[str, str] | None = None`
  (last field, default). Handler passes `run_env=getattr(ctx, "run_env", None)`.

### Subtask T014 – Aggregation tier

- `verdict_aggregation.py`: `AggregateDecision.REFUSE = "refuse"`; `_REFUSING_OUTCOMES =
  frozenset({GateOutcome.FOREIGN_TREE})`; `AggregateVerdict.refusing_verdicts: tuple[GateVerdict, ...] = ()`
  (default keeps any existing direct constructions valid); precedence in `aggregate_verdicts`:
  terminal → refusing (not force) → block → warn. `should_exit` includes REFUSE. Update the
  module docstring's precedence list.

## Test Strategy

```bash
uv run --frozen python -m pytest tests/review/test_gate_run_environment.py tests/review/test_verdict_aggregation.py tests/review/test_gate_registry.py tests/review/test_transition_gate_parity.py tests/review/test_interpreter_and_scoped_lock.py tests/review/test_pre_review_gate_source_mismatch.py tests/review/test_baseline_head_parity.py tests/review/test_verdict_candidate_exit.py -q
uv run --frozen python -m pytest tests/review -q   # owning subsystem (heavy: ~minutes; record the count)
uv run --frozen ruff check <changed files>; uv run --frozen ruff format --check --force-exclude <changed files>; uv run --frozen mypy <changed src files>
uv run --frozen python -m pytest tests/architectural/test_no_dead_symbols.py tests/architectural/test_os_detection_ban.py -q
```

## Risks & Mitigations

- Existing gate tests that relied on inherited `PYTHONPATH`: with `run_env=None` nothing
  changes; only the baseline now strips. Run `tests/review` fully; if a baseline test relied
  on an inherited `PYTHONPATH`, judge it per Standing Order 4 (stale → re-pin with the new
  recipe; valid → fix the product), never weaken the recipe silently. Report any such case.
- Lazy import cycle `baseline` ↔ `pre_review_gate` already exists; keep the new import lazy.

## Review Guidance

- `run_env=None` path is byte-identical in behaviour (positive control in T010.1).
- REFUSE cannot be reached by any outcome other than `FOREIGN_TREE`; TERMINAL precedence intact.
- No probe or git read added to the engine.

## Activity Log

- 2026-11-12T05:35:56Z – system – Prompt generated via /spec-kitty.tasks
