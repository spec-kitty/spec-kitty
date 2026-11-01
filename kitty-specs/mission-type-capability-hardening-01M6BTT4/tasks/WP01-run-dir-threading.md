---
work_package_id: WP01
title: Thread the run directory into the WP-driven fact
dependencies: []
requirement_refs:
- FR-001
- FR-004
- NFR-001
- NFR-002
- SC-001
- SC-004
planning_base_branch: issue-6330-run-dir-threading
merge_target_branch: issue-6330-run-dir-threading
branch_strategy: Planning artifacts for this mission were generated on issue-6330-run-dir-threading. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6330-run-dir-threading unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-type-capability-hardening-01M6BTT4
base_commit: 11fa6a74e3cd8c09264a7e1803437737eb42f9d5
created_at: '2026-11-01T15:22:52.790677+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Runtime fact
history:
- at: '2026-11-01T15:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/runtime/next/runtime_bridge_io.py
- src/runtime/next/runtime_bridge.py
- src/runtime/next/runtime_bridge_composition.py
- tests/runtime/test_wp_driven_guard.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Thread the run directory into the WP-driven fact

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission mission-type-capability-hardening-01M6BTT4`) and address every item before handing back.

## Objectives & Success Criteria

Close the one real fail-open left by #6315 (#6332, merged) for GitHub issue #6330 item 1.

Today `gather_artifact_presence` accepts a `run_dir` but **no production caller
supplies it** (`rg -n "run_dir" src/runtime/next/runtime_bridge*.py`), so
`_wp_driven_fact` always re-resolves the run from `feature_dir.name` and
returns `False` on any selector error. For a custom family whose frozen DAG
declares `implement`, that turns the WP-advance guard off — the exact hole
#6315 closed.

Deliver:

- `gather_artifact_presence(..., run_dir=None, mission_slug=None)`: `run_dir`
  is authoritative; `mission_slug` (an explicit mission handle) is the only
  read-only fallback; `feature_dir.name` is never consulted by the fact.
- `_check_cli_guards`, `_check_composed_action_guard` and
  `_dispatch_via_composition` gain `run_dir=` (and `mission_slug=`) pass-through
  kwargs; the three live call sites thread `ctx.run_dir`:
  - `_dn_dependency_gate` → `_check_cli_guards` (two call sites: the
    WP-iteration advance guard and the software-dev non-WP pre-check),
  - `_dn_composition_dispatch` → `_dispatch_via_composition`.
- `tests/runtime/test_wp_driven_guard.py` proves the fail-open is closed and the
  production path forwards the run; the existing controls stay green.

FR-001, FR-004 (built-ins byte-identical), NFR-001 (no new hot-path read),
NFR-002 (nothing new raises), SC-001, SC-004.

## Context

- `src/runtime/next/runtime_bridge_io.py:1505-1519` — `_wp_driven_fact`.
- `src/runtime/next/runtime_bridge_io.py:1538-1552` — the fact-port signature.
- `src/runtime/next/runtime_bridge_io.py:1653` — the `feature_dir.name` call.
- `src/runtime/next/runtime_bridge.py:824-846` and `:884-893` — the two
  `_check_cli_guards` call sites (both in `_dn_dependency_gate`, `ctx` in scope).
- `src/runtime/next/runtime_bridge_composition.py:426-520` —
  `_check_composed_action_guard`; `:523-651` — `_dispatch_via_composition`
  (`:648` is the guard call).
- `src/runtime/next/runtime_bridge.py:1031` — the `_dispatch_via_composition`
  call site (`_dn_composition_dispatch`).
- `AGENTS.md` — `feature_dir.name` is not a mission handle (Terminology Canon).

Read the surrounding docstrings; they explain why the WP-advance call in the
guards is deliberately *not* anchored, and that reasoning must survive.

## Detailed Guidance

### T001 — Red: the guard survives a directory that is not a handle

In `tests/runtime/test_wp_driven_guard.py`, add a test that:

1. scaffolds the existing activated custom family
   (`scaffold_custom_analyze_mission`), whose frozen DAG declares `implement`;
2. moves/renames the planning directory so `feature_dir.name` is **not** the
   mission slug (keep the run resolvable through the index by its real slug);
3. calls `_check_composed_action_guard("implement", <renamed dir>, mission=<family>,
   repo_root=<repo>, run_dir=<real run dir>)`;
4. asserts the pending-WP failure is returned.

Before the fix it must return `[]` (the guard is skipped). Same-fixture positive
control: the un-renamed directory (or the same call with the real directory)
returns the same failure, so the assertion is not vacuous.

### T002 — Red: the production dispatch forwards the run

Add a test that drives `_dispatch_via_composition` (the production entry, not a
helper) with the composed `implement` action and asserts the guard that ran saw
the threaded run directory. Prefer asserting observable behaviour: with the
renamed directory and `run_dir=` supplied, `_dispatch_via_composition` returns
the pending-WP failures. Use the existing composition test doubles in
`tests/next/` only if a real executor run is too heavy; the assertion must be on
the returned failures, not on a mock call.

### T003 — Thread the fact port

- Add `mission_slug: str | None = None` to `gather_artifact_presence` and
  forward it to `_wp_driven_fact`.
- `_wp_driven_fact(step_id, run_dir, repo_root, mission_slug)`:
  `run_dir` wins; else when `repo_root` and an explicit `mission_slug` are both
  given, do the existing read-only `_resolve_run_dir_for_mission` lookup;
  else `False`. Document that a `run_dir` for another mission is the caller's
  contract to keep, not cross-checked here.
- Delete the `feature_dir.name` argument at the call site; nothing else in the
  module may derive a mission handle from a directory name.

### T004 — Thread the guards and the call sites

- `_check_cli_guards(..., run_dir=None, mission_slug=None)` → forward both.
- `_check_composed_action_guard(..., run_dir=None, mission_slug=None)` → forward
  both.
- `_dispatch_via_composition(..., run_dir=None, mission_slug=None)` → forward
  both to the guard.
- `_dn_dependency_gate`: both `_check_cli_guards` calls get `run_dir=ctx.run_dir`.
- `_dn_composition_dispatch`: `_dispatch_via_composition(...)` gets
  `run_dir=ctx.run_dir`.
- Keep the "intentionally NOT anchored" comments accurate — do not anchor
  `wp_advance_ready` as part of this change.

### T005 — Repoint the existing helper

`tests/runtime/test_wp_driven_guard.py::_guard` already calls `get_or_start_run`;
have it pass `run_dir=` from that ref. The `test_non_wp_driven_family_is_unaffected`
control must stay green (its family's DAG has no `implement`).

## Branch Strategy

- Planning base and merge target: `issue-6330-run-dir-threading`.
- Execution worktrees are allocated per computed lane from `lanes.json`; never
  pick a base branch by hand. A WP whose dependencies are not `approved`/`done`
  refuses to be claimed.
- Run `spec-kitty agent action implement WP01 --agent <name> --mission mission-type-capability-hardening-01M6BTT4`.

## Test Strategy

- Red-first (charter ATDD discipline): write T001/T002 and watch them fail for
  the right reason before T003/T004 exist.
- Focused runs only, for example:
  `uv run pytest tests/runtime/test_wp_driven_guard.py -q`,
  `uv run pytest tests/runtime/test_artifact_presence_placement.py -q`,
  `uv run pytest tests/runtime/next/test_cli_guard_family.py tests/runtime/test_cli_guard_family.py -q`.
- Never run a full heavy suite locally (`NO_FULL_HEAVY_SUITES_IN_MISSION`); CI
  owns that.
- Cover the new branch (`run_dir is None and mission_slug is not None`) so
  diff-cover stays ≥ 90 % on changed lines.

## Definition of Done

- T001/T002 tests pass; T001 fails on `main` and on the pre-fix tree.
- `gather_artifact_presence` has no path that reads `feature_dir.name` as a
  mission handle (grep: `_wp_driven_fact(step_id, run_dir, repo_root,` is the
  only call).
- The three production call sites thread `ctx.run_dir`.
- The built-in suites above are green; no test was skipped, xfailed or relaxed.
- `uv run ruff check`, `uv run ruff format --check` and `uv run mypy` on the
  touched modules are clean.

## Risks & Reviewer Guidance

- **Risk**: a caller outside `src/` relies on the implicit fallback. Reviewer:
  grep `gather_artifact_presence(` / `_check_cli_guards(` / `_check_composed_action_guard(`
  and confirm each remaining no-`run_dir` caller either passes `mission_slug` or
  is a non-`implement`/`review` step.
- **Risk**: the change accidentally anchors `wp_advance_ready`. Reviewer: the two
  "Intentionally NOT anchored" comments must still describe the code.
- **Reviewer**: confirm the WP-iteration step still holds *before* the new
  threading is reached (the dependency gate owns the stay-in-step decision).
