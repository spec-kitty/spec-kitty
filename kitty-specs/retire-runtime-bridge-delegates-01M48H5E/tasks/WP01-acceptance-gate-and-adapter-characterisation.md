---
work_package_id: WP01
title: Acceptance gate and adapter characterisation
dependencies: []
requirement_refs:
- FR-001
- FR-003
- FR-005
- FR-008
- NFR-001
planning_base_branch: issue-2561-retire-runtime-bridge-delegates
merge_target_branch: issue-2561-retire-runtime-bridge-delegates
branch_strategy: Planning artifacts for this mission were generated on issue-2561-retire-runtime-bridge-delegates. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2561-retire-runtime-bridge-delegates unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Red-first contract
history:
- at: '2026-10-06T12:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/runtime/test_bridge_
create_intent:
- tests/runtime/test_bridge_no_compat_delegates.py
- tests/runtime/test_bridge_adapter_characterisation.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/runtime/test_bridge_no_compat_delegates.py
- tests/runtime/test_bridge_adapter_characterisation.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Acceptance gate and adapter characterisation

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission retire-runtime-bridge-delegates-01M48H5E`) or the Activity Log below.
- **You must address all feedback** before your work is complete.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Objectives & Success Criteria

Make the end state checkable before any code changes, and pin the three adapter behaviours.

Done when:
- `tests/runtime/test_bridge_no_compat_delegates.py` exists, pins the 36 names by seam, and every per-seam row is `xfail(strict=True)` (red today, so it is a real red-first test, and strict so it cannot silently pass).
- A self-mutation test proves the scanner flags a synthetic forwarding module and a synthetic `_rb.<name>` lookup (non-vacuity, charter SO#5).
- `tests/runtime/test_bridge_adapter_characterisation.py` pins `_load_feature_runs`, `_parse_requirement_refs_from_tasks_md` and `_build_run_ref` behaviour **through the bridge's production entry points** and is GREEN on this commit. It must stay green, unmodified, through WP02–WP05.
- No source file changes in this WP.

Requirement refs: FR-001, FR-003, FR-005, FR-008, NFR-001. Depends on: none.

## Context & Constraints

- Charter: `.kittify/charter/charter.md` (ATDD red-first, campsite cleaning, no full heavy suites).
- Spec: `kitty-specs/retire-runtime-bridge-delegates-01M48H5E/spec.md`; plan: `plan.md`; ownership map: `data-model.md`; back-edge inventory and hazards: `research.md`; target surface: `contracts/bridge-surface.md`.
- Reference only: the grounding prototype `git show 20547b2d` on `origin/spike/runtime-bridge-grounding-2560-2562` maps the call sites. Read it for orientation; do NOT cherry-pick it (C-003).
- **Call-style rule** (decision `plan.design.internal-call-style`): inside `src/runtime/next/` call a seam-owned name on its owner (`_io_seam._build_run_ref(...)`, `runtime_bridge_retrospective._classify_exc(...)`); a seam calls its own functions directly. A deferred import of the *owning seam* is fine where a cycle forces it (io <-> composition). A lookup of a removed name on the bridge (`_rb.<name>`) is not.
- **Back-edges to names the bridge still owns stay** (FR-004): `_should_advance_wp_step`, `_is_wp_iteration_step`, `_map_runtime_decision`, `_resolve_runtime_feature_dir`, `_has_raw_dependencies_field`, `_check_requirement_mapping_ready`, `_check_bare_prose_requirements_ready`, `_occurrence_gate_failures`. Moving those is #2560's job (C-002).
- Stay inside `src/runtime/next/` for source edits (C-001). Test edits are limited to tests that reference the names this WP removes.
- **Repointing rule for tests**: for every test that patches, imports or reads a removed name, ask "which binding does the code under test look up?" and patch that binding. Do not mechanically rewrite strings. A patch on a removed bridge name fails loudly (`AttributeError`), which is good; a patch on a name that still exists but is no longer looked up passes silently, which is the hazard. Where a test's only purpose was to pin the compat mechanism (a forwarder exists / a live lookup goes through the bridge), delete it or rewrite it as a test of the owning seam's patch point, and list it in the Activity Log with the reason.
- Rewrite any docstring or comment in the files you touch that describes the compat-delegate / live-lookup mechanism for the names you remove, so it states what the seam owns (FR-010, campsite cleaning).

## Branch Strategy

- **Strategy**: single_branch (work packages run in sequence in the repository root checkout)
- **Planning base branch**: issue-2561-retire-runtime-bridge-delegates
- **Merge target branch**: issue-2561-retire-runtime-bridge-delegates

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

Implementation command: `spec-kitty agent action implement WP01 --agent claude --mission retire-runtime-bridge-delegates-01M48H5E`.

## Subtasks & Detailed Guidance

### Subtask T001 – Static acceptance gate (per seam)

- **Purpose**: FR-001/FR-003/FR-005 as an executable contract.
- **Steps**:
  1. Create `tests/runtime/test_bridge_no_compat_delegates.py`. Mark it `pytestmark = [pytest.mark.fast]` if that marker is the norm in `tests/runtime/` (check neighbours).
  2. Define `REMOVED: dict[str, tuple[str, ...]]` keyed by seam (`identity`, `cores`, `engine`, `retrospective`, `composition`, `io`) with exactly the names in `data-model.md` (3/2/1/9/8/13 = 36). Assert the total is 36 in a separate test (concrete floor).
  3. `_PENDING_SEAMS = {"identity", "cores", "engine", "retrospective", "composition", "io"}`. Parametrize the checks over seams; apply `pytest.mark.xfail(strict=True, reason="migrated in WPxx")` to a param when its seam is in `_PENDING_SEAMS` (use `pytest.param(..., marks=...)`). Each later WP removes its seam from the set.
  4. Check A (no definition): parse `src/runtime/next/runtime_bridge.py` with `ast`; for the seam's names, fail if any top-level `FunctionDef`/`AsyncFunctionDef`/`ClassDef`/`Assign`/`AnnAssign` binds the name. Allow binding only by `ImportFrom` from `runtime.next.runtime_bridge_io`, and only for `get_or_start_run` and `build_operational_context_for_claim`.
  5. Check B (no back-edge): for every `src/runtime/next/runtime_bridge_*.py`, collect aliases bound to the bridge module (`from runtime.next import runtime_bridge as X`, `import runtime.next.runtime_bridge as X`, at any scope), then fail on any `ast.Attribute(value=Name(id=X), attr=<seam name>)`. Report file:line in the failure message.
  6. Check C (io only): `runtime_bridge.get_or_start_run is runtime_bridge_io.get_or_start_run` and the same for `build_operational_context_for_claim`; both still in `runtime_bridge.__all__`.
  7. A docstring check: `"Thin compat delegate"` occurs 0 times in the bridge. Mark it `xfail(strict=True, reason="WP06")`.
  8. **Hardening from the post-tasks squad (M3), all per seam row:**
     - **Check D (runtime, catches every binding form):** `not hasattr(runtime_bridge, name)` for every removed name except the two re-exports. This covers imports of private names, bindings inside top-level `if`/`try`, tuple unpacking, `globals()[...]` and a PEP 562 `__getattr__`.
     - **Check A′:** no `ast.Name` *load* of a removed name anywhere in the bridge (the bridge has `from __future__ import annotations`, so a stale annotation such as `buffer: _BufferingRuntimeEmitter`, bridge:2479/2624, would survive at runtime).
     - **Check B′:** across all of `src/`, no `ImportFrom` of a removed name from `runtime.next.runtime_bridge` (catches `from runtime.next.runtime_bridge import _x` inside a seam function), no `getattr(<bridge alias>, "<removed name>")`, and no fully dotted `runtime.next.runtime_bridge.<removed name>`.
     - **Floor:** every `REMOVED` name exists on its owning seam (map `_load_feature_runs` → `load_feature_runs`, `_advance_run_state_after_composition` → `advance_run_state_after_composition`) so a typo cannot make a check pass vacuously.
     - **Call style (io row):** no bare call `get_or_start_run(` / `build_operational_context_for_claim(` inside the bridge; internal calls must be `_io_seam.<name>(` (decision `plan.design.internal-call-style`). This is what makes the WP05 hazard-1 classification enforceable.
- **Files**: `tests/runtime/test_bridge_no_compat_delegates.py` (new).
- **Notes**: Keep helpers small (complexity <= 15). Prefer pure functions `scan_definitions(source, names)` and `scan_back_edges(source, names)` that take source text, so T002 can feed them synthetic modules.

### Subtask T002 – Self-mutation (non-vacuity) tests

- **Purpose**: prove the gate can fail.
- **Steps**: feed `scan_definitions` a synthetic source with `def _build_run_ref(...): return _io._build_run_ref(...)` and assert it is flagged; feed `scan_back_edges` a synthetic `def f():\n    from runtime.next import runtime_bridge as _rb\n    return _rb._build_run_ref()` and assert it is flagged; feed a bridge-owned name (`_should_advance_wp_step`) and assert it is **not** flagged (FR-004 positive control); feed a synthetic `from runtime.next.runtime_bridge import _classify_exc` inside a function and a synthetic bare `get_or_start_run(...)` call and assert both are flagged.
- **Files**: same new file.

### Subtask T003 – Characterise `_load_feature_runs` and `_build_run_ref`

- **Purpose**: GROUNDING hazard 2. The prototype's naive rename of `_load_feature_runs(repo_root)` to `load_feature_runs(repo_root)` regressed; only a patch-free test caught it.
- **Steps**:
  1. Read `runtime_bridge._load_feature_runs`, `runtime_bridge._build_run_ref`, and their callers (`git grep -n "_load_feature_runs\|_build_run_ref" src/runtime/next`).
  2. Write patch-free tests that drive a **production entry** (e.g. `runtime_bridge_io.get_or_start_run` / `runtime_bridge.get_or_start_run` on a scaffolded mission; reuse `tests/runtime/_next_mission_scaffold.py` or the fixtures in `tests/runtime/test_bridge_io.py`): start a run, then call again and assert the **same** run is returned (proves the runs index is read from the resolved path); assert the returned object is a `MissionRunRef` with the expected `run_id`, `run_dir` and `mission_type`.
  3. Also pin the direct adapter contract while it exists, in a way that survives deletion: e.g. `runtime_bridge_io.load_feature_runs(runtime_bridge_io._feature_runs_path(repo_root))` returns the entry the entry point wrote.
- **Files**: `tests/runtime/test_bridge_adapter_characterisation.py` (new).
- **Notes**: Do not reference any of the 36 names on `runtime_bridge` in this file; reference only the owning seams and the two kept re-exports. That keeps the file untouched by later WPs.

### Subtask T004 – Characterise `_parse_requirement_refs_from_tasks_md`

- **Purpose**: the delegate injects `grammar=` from `specify_cli.requirement_mapping`.
- **Steps**: find its bridge call sites (`git grep -n "_parse_requirement_refs_from_tasks_md" src`); write a test that drives that production caller (or, if it is only reachable through a deep path, the closest public function that reaches it) with a `tasks.md` containing requirement references in several grammar forms (plain `FR-001`, suffixed `FR-002a`, `NFR-001`, `C-001`, a cross-mission `<slug>#FR-003` if the grammar accepts it, and a malformed one). Assert the parsed result per WP. Also assert `runtime_bridge_cores._parse_requirement_refs_from_tasks_md(content, grammar=grammar)` gives the same result, which is what the call sites will use after WP02.
- **Files**: `tests/runtime/test_bridge_adapter_characterisation.py`.


## Test Strategy

Run, and record commands with pass/fail counts in the Activity Log:

```bash
.venv/bin/python -m pytest tests/runtime/test_bridge_no_compat_delegates.py -q
.venv/bin/python -m pytest tests/runtime/test_bridge_no_compat_delegates.py tests/runtime/test_bridge_adapter_characterisation.py -q   # gate rows xfail (strict), characterisation green
.venv/bin/ruff check src/runtime/next <changed test files>
.venv/bin/ruff format --check --force-exclude src/runtime/next <changed test files>
.venv/bin/mypy src/runtime/next | tail -1   # must stay <= 21 errors (main baseline); none in changed lines
.venv/bin/ruff check --select C901 src/runtime/next   # complexity <= 15
```

Run on a clean tree (commit first): `tests/runtime/test_reassess_under_lock.py` reports
"Baseline source is dirty" on a dirty worktree, which is environmental.
Never run `make test-full`, the whole `tests/architectural/` directory, or any whole-repo sweep.

## Risks & Mitigations

- **Vacuous gate**: mitigated by the 36-name floor, strict xfail, and the self-mutation tests.
- **Characterisation coupled to removed names**: the file must not touch `runtime_bridge.<removed name>`; otherwise WP05 would have to edit it and the "unchanged characterisation" proof is lost.

## Review Guidance

- Reviewer is a different agent from the implementer (charter SO#8).
- Check the gate rows for this WP's seam(s) moved from strict-xfail to passing **in this WP's diff** and nowhere else.
- For every repointed patch, open the code under test and confirm the patched binding is the one it looks up. Spot-check at least five by call path; check every one that touches a kept re-export.
- Check the adapters' characterisation tests (WP01) are untouched and green.
- Confirm no logic moved out of the bridge (C-002) and no source outside `src/runtime/next/` changed (C-001).
- Confirm mypy did not grow and ruff/format are clean.

## Activity Log

- 2026-10-06T12:10:00Z – system – Prompt created.
- 2026-10-06T12:40:00Z – claude (python-pedro) – Implemented T001-T004, commit c7ffcd00 (tests only, no source changes). Gate: 36 names pinned (3/2/1/9/8/13), per-seam Checks A, A', B, B', C, D, floor, call style, docstring (WP06). Non-vacuity: 14 self-mutation tests incl. FR-004 positive control. Rows already holding on `main` (B for cores/engine, B' for all seams) are plain guards, not xfail. Characterisation does not reference any removed name on `runtime_bridge`.
- Tests: `pytest tests/runtime/test_bridge_no_compat_delegates.py tests/runtime/test_bridge_adapter_characterisation.py -q -p no:cacheprovider` -> 44 passed, 26 xfailed (strict), 0 failed. ruff check, ruff format --force-exclude and `ruff check --select C901` clean; mypy on the two files reports only the pre-existing `tests/lane_test_utils.py:85` error.

