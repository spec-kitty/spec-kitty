---
work_package_id: WP10
title: 'Sweep S5: other tests/specify_cli'
dependencies:
- WP01
requirement_refs:
- C-005
- C-009
- FR-006
- NFR-002
- NFR-006
planning_base_branch: issue-5119-merge-seam-test-isolation
merge_target_branch: issue-5119-merge-seam-test-isolation
branch_strategy: Planning artifacts for this mission were generated on issue-5119-merge-seam-test-isolation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5119-merge-seam-test-isolation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-merge-seam-test-isolation-campsite-01M3F61E
base_commit: 529d3e5e6331f44f24c1fbe80382e7ef1ceee128
created_at: '2026-09-26T18:11:51.011415+00:00'
subtasks:
- T046
- T047
- T048
- T049
- T050
phase: Phase 3 - Test-isolation sweep
history:
- at: '2026-09-26T16:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py
- tests/specify_cli/charter_runtime/test_boundary_heal.py
- tests/specify_cli/charter_runtime/test_references_parity_refresh.py
- tests/specify_cli/coordination/test_write_seam_thunk.py
- tests/specify_cli/integration/test_context_lifecycle.py
- tests/specify_cli/next/test_runtime_bridge_dispatch.py
- tests/specify_cli/next/test_runtime_bridge_documentation_composition.py
- tests/specify_cli/orchestrator_api/test_answer_decision.py
- tests/specify_cli/orchestrator_api/test_check_prerequisites_record_analysis.py
- tests/specify_cli/orchestrator_api/test_decision_verbs.py
- tests/specify_cli/orchestrator_api/test_design_status.py
- tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py
- tests/specify_cli/session_presence/conftest.py
- tests/specify_cli/test_bytecode_heal.py
- tests/specify_cli/upgrade/migrations/test_m_3_2_0rc39_refresh_orientation_block.py
- tests/specify_cli/upgrade/migrations/test_m_session_presence_all_harnesses.py
- tests/specify_cli/upgrade/migrations/test_m_session_presence_claude_code.py
- tests/specify_cli/upgrade/migrations/test_retired_hosted_target.py
- tests/specify_cli/upgrade/migrations/test_session_presence_upgrade_smoke.py
- tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP10 – Sweep S5: other tests/specify_cli

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (`packs/built-in/agent_profiles/python-pedro.agent.yaml`), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `.venv/bin/spec-kitty agent profile list` and select the best match for `task_type: implement` on `tests/specify_cli/`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `.venv/bin/spec-kitty agent tasks status --mission merge-seam-test-isolation-campsite-01M3F61E` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Issue **#5118** (FR-006, NFR-002, C-005). This work package converts every **manual global-state mutation** in shard **S5** (49 sites across 20 files) to a **scoped patching facility**, then drains shard S5's `transitional-sweep` rows from the census allowlist landed by WP01.

Done means:

- Every `transitional-sweep` row in `tests/architectural/global_state_allowlist/S5.yaml` is gone; only genuinely justified rows (`process-bootstrap` / `subprocess-entry` / `leak-sentinel`, each with a truthful `reason`) remain, and their counts are exact.
- `.venv/bin/python -m pytest tests/architectural/test_no_manual_global_state_mutation.py -q` passes (no unallowlisted, over-count, under-count or wrong-shard verdict).
- For every owned file, the per-test-id outcome (pass / skip / xfail / xpass) captured as junit-xml **before** and **after** is identical — 0 tests deleted, 0 newly skipped (NFR-002).
- The owned files also pass under `-n auto --dist loadfile`.
- No product source (`src/**`) is modified (C-005). No new `# noqa` / `# type: ignore`.

- **Done means** the census gate is green with zero `transitional-sweep` rows in this shard (explicit review evidence), the before/after junit comparison is identical, and neighbouring `tests/`-scanning gates stay green.

## Context & Constraints

- **Spec**: `kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/spec.md` — User Story 2, Domain Language (*manual global-state mutation*, *scoped patching facility*), Edge Cases.
- **Research**: `research.md` R6 (detector), R7 (fix classes), R8 (ordering). Per-site classification: `research/global_state_sites_classified.tsv`; shard file sets: `research/sweep_shards.tsv`.
- **Contract**: `contracts/global-state-allowlist.md` — allowlist row shape, verdicts, scoped replacement per kind.
- **Charter**: `.kittify/charter/charter.md` — standing order #4 (judge the test; never retry-to-green), locality of change.
- A hand-written `try/finally` restore **is** an offender (not auto-restoring; leaks on failure paths). The accepted replacements are exactly: `monkeypatch.chdir/setenv/delenv/setitem/delitem/setattr/syspath_prepend`; `pytest.MonkeyPatch.context()` for module/session-scoped fixtures; `contextlib.chdir` for block-scoped cwd; `unittest.mock.patch.dict(os.environ, ...)` / `mock.patch.object(...)`.
- **Relocating a mutation is not a fix**: moving `os.chdir` into a shared helper or `conftest.py` is still counted by the detector. A helper that mutates on a caller's behalf must receive `monkeypatch` or be a context manager.
- `patch.dict(sys.modules, ...)` is **banned** repo-wide (`tests/architectural/test_no_sys_modules_patch_dict.py`) — never use it as a replacement.
- The detector ignores `SPEC_KITTY_HOME` writes via `setenv`/`[]=`/`.setdefault` (owned by the `_home_pin_scan` gate) — do not "fix" those here.
- **Ownership**: edit only the files in `owned_files`, plus exactly one recorded out-of-map edit: `tests/architectural/global_state_allowlist/S5.yaml` (drain step). Never edit other shards, the detector, the gate, or files owned by mission `01M3EW3Z`.

### Shard notes

- **Shard focus**: 20 files across the rest of `tests/specify_cli/` (decision/answer verbs, runtime_bridge, bytecode_heal, context_lifecycle, upgrade migrations, …) — broadest spread after S6/S8; work file by file, commit per logical group. Five class-D1 sites are import-time inserts in upgrade-migration tests and a `conftest.py`.
- **`sys.modules` sites in this shard** (check whether each relies on a fresh re-import; if so also restore the parent-package attribute): `tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py`, `tests/specify_cli/integration/test_context_lifecycle.py`, `tests/specify_cli/next/test_runtime_bridge_dispatch.py`, `tests/specify_cli/next/test_runtime_bridge_documentation_composition.py`, `tests/specify_cli/test_bytecode_heal.py`.

### Owned files (20 files / 49 sites)

| File | Sites |
|---|---|
| `tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py` | 1 |
| `tests/specify_cli/charter_runtime/test_boundary_heal.py` | 2 |
| `tests/specify_cli/charter_runtime/test_references_parity_refresh.py` | 2 |
| `tests/specify_cli/coordination/test_write_seam_thunk.py` | 4 |
| `tests/specify_cli/integration/test_context_lifecycle.py` | 4 |
| `tests/specify_cli/next/test_runtime_bridge_dispatch.py` | 4 |
| `tests/specify_cli/next/test_runtime_bridge_documentation_composition.py` | 3 |
| `tests/specify_cli/orchestrator_api/test_answer_decision.py` | 6 |
| `tests/specify_cli/orchestrator_api/test_check_prerequisites_record_analysis.py` | 6 |
| `tests/specify_cli/orchestrator_api/test_decision_verbs.py` | 2 |
| `tests/specify_cli/orchestrator_api/test_design_status.py` | 2 |
| `tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py` | 2 |
| `tests/specify_cli/session_presence/conftest.py` | 1 |
| `tests/specify_cli/test_bytecode_heal.py` | 2 |
| `tests/specify_cli/upgrade/migrations/test_m_3_2_0rc39_refresh_orientation_block.py` | 1 |
| `tests/specify_cli/upgrade/migrations/test_m_session_presence_all_harnesses.py` | 1 |
| `tests/specify_cli/upgrade/migrations/test_m_session_presence_claude_code.py` | 1 |
| `tests/specify_cli/upgrade/migrations/test_retired_hosted_target.py` | 2 |
| `tests/specify_cli/upgrade/migrations/test_session_presence_upgrade_smoke.py` | 1 |
| `tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py` | 2 |

### Fix-class distribution

| Class | Sites |
|---|---|
| A-monkeypatch | 17 |
| B-contextlib.chdir | 27 |
| D1-delete-redundant-insert | 5 |

### Site to-do list

Line numbers are navigation only (the allowlist is keyed on file + qualname + kind). Re-run the detector if lines drifted.

| File | Qualname | Kind | Form | Fix class | Line (nav only) |
|---|---|---|---|---|---|
| `tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py` | `_load_inventory_module` | sys.modules | `subscript-store` | A-monkeypatch | 88 |
| `tests/specify_cli/charter_runtime/test_boundary_heal.py` | `_invoke_generate_in_process` | cwd | `call:os.chdir` | B-contextlib.chdir | 462 |
| `tests/specify_cli/charter_runtime/test_boundary_heal.py` | `_invoke_generate_in_process` | cwd | `call:os.chdir` | B-contextlib.chdir | 465 |
| `tests/specify_cli/charter_runtime/test_references_parity_refresh.py` | `_invoke_generate_in_process` | cwd | `call:os.chdir` | B-contextlib.chdir | 83 |
| `tests/specify_cli/charter_runtime/test_references_parity_refresh.py` | `_invoke_generate_in_process` | cwd | `call:os.chdir` | B-contextlib.chdir | 86 |
| `tests/specify_cli/coordination/test_write_seam_thunk.py` | `test_off_checkout_safe_commit_cli_exits_nonzero_with_no_checkout` | cwd | `call:os.chdir` | A-monkeypatch | 467 |
| `tests/specify_cli/coordination/test_write_seam_thunk.py` | `test_off_checkout_safe_commit_cli_exits_nonzero_with_no_checkout` | cwd | `call:os.chdir` | B-contextlib.chdir | 480 |
| `tests/specify_cli/coordination/test_write_seam_thunk.py` | `test_review_post_merge_exits_zero_on_e2_mission` | cwd | `call:os.chdir` | A-monkeypatch | 606 |
| `tests/specify_cli/coordination/test_write_seam_thunk.py` | `test_review_post_merge_exits_zero_on_e2_mission` | cwd | `call:os.chdir` | B-contextlib.chdir | 613 |
| `tests/specify_cli/integration/test_context_lifecycle.py` | `TestContextResolutionNoHeuristics.test_no_detect_feature_called_during_resolution` | sys.modules | `call:.pop` | A-monkeypatch | 173 |
| `tests/specify_cli/integration/test_context_lifecycle.py` | `TestContextResolutionNoHeuristics.test_no_detect_feature_called_during_resolution` | sys.modules | `subscript-store` | A-monkeypatch | 175 |
| `tests/specify_cli/integration/test_context_lifecycle.py` | `TestContextResolutionNoHeuristics.test_no_detect_feature_called_during_resolution` | sys.modules | `subscript-del` | A-monkeypatch | 181 |
| `tests/specify_cli/integration/test_context_lifecycle.py` | `TestContextResolutionNoHeuristics.test_no_detect_feature_called_during_resolution` | sys.modules | `subscript-store` | A-monkeypatch | 183 |
| `tests/specify_cli/next/test_runtime_bridge_dispatch.py` | `_inject_mission_type_repository_mock` | sys.modules | `subscript-store` | A-monkeypatch | 78 |
| `tests/specify_cli/next/test_runtime_bridge_dispatch.py` | `_inject_mission_type_repository_mock` | sys.modules | `subscript-store` | A-monkeypatch | 79 |
| `tests/specify_cli/next/test_runtime_bridge_dispatch.py` | `_restore_modules` | sys.modules | `call:.pop` | A-monkeypatch | 86 |
| `tests/specify_cli/next/test_runtime_bridge_dispatch.py` | `_restore_modules` | sys.modules | `subscript-store` | A-monkeypatch | 88 |
| `tests/specify_cli/next/test_runtime_bridge_documentation_composition.py` | `test_documentation_in_composed_actions` | sys.modules | `subscript-store` | A-monkeypatch | 78 |
| `tests/specify_cli/next/test_runtime_bridge_documentation_composition.py` | `test_documentation_in_composed_actions` | sys.modules | `call:.pop` | A-monkeypatch | 91 |
| `tests/specify_cli/next/test_runtime_bridge_documentation_composition.py` | `test_documentation_in_composed_actions` | sys.modules | `subscript-store` | A-monkeypatch | 93 |
| `tests/specify_cli/orchestrator_api/test_answer_decision.py` | `_next` | cwd | `call:os.chdir` | B-contextlib.chdir | 239 |
| `tests/specify_cli/orchestrator_api/test_answer_decision.py` | `_next` | cwd | `call:os.chdir` | B-contextlib.chdir | 243 |
| `tests/specify_cli/orchestrator_api/test_answer_decision.py` | `_run_answer_decision` | cwd | `call:os.chdir` | B-contextlib.chdir | 252 |
| `tests/specify_cli/orchestrator_api/test_answer_decision.py` | `_run_answer_decision` | cwd | `call:os.chdir` | B-contextlib.chdir | 256 |
| `tests/specify_cli/orchestrator_api/test_answer_decision.py` | `_run_next_raw` | cwd | `call:os.chdir` | B-contextlib.chdir | 668 |
| `tests/specify_cli/orchestrator_api/test_answer_decision.py` | `_run_next_raw` | cwd | `call:os.chdir` | B-contextlib.chdir | 672 |
| `tests/specify_cli/orchestrator_api/test_check_prerequisites_record_analysis.py` | `_run` | cwd | `call:os.chdir` | B-contextlib.chdir | 130 |
| `tests/specify_cli/orchestrator_api/test_check_prerequisites_record_analysis.py` | `_run` | cwd | `call:os.chdir` | B-contextlib.chdir | 134 |
| `tests/specify_cli/orchestrator_api/test_check_prerequisites_record_analysis.py` | `test_check_prerequisites_field_parity_with_host_cli` | cwd | `call:os.chdir` | A-monkeypatch | 258 |
| `tests/specify_cli/orchestrator_api/test_check_prerequisites_record_analysis.py` | `test_check_prerequisites_field_parity_with_host_cli` | cwd | `call:os.chdir` | B-contextlib.chdir | 269 |
| `tests/specify_cli/orchestrator_api/test_check_prerequisites_record_analysis.py` | `_host_record_analysis_error_code` | cwd | `call:os.chdir` | B-contextlib.chdir | 488 |
| `tests/specify_cli/orchestrator_api/test_check_prerequisites_record_analysis.py` | `_host_record_analysis_error_code` | cwd | `call:os.chdir` | B-contextlib.chdir | 499 |
| `tests/specify_cli/orchestrator_api/test_decision_verbs.py` | `_run` | cwd | `call:os.chdir` | B-contextlib.chdir | 105 |
| `tests/specify_cli/orchestrator_api/test_decision_verbs.py` | `_run` | cwd | `call:os.chdir` | B-contextlib.chdir | 109 |
| `tests/specify_cli/orchestrator_api/test_design_status.py` | `_run` | cwd | `call:os.chdir` | B-contextlib.chdir | 122 |
| `tests/specify_cli/orchestrator_api/test_design_status.py` | `_run` | cwd | `call:os.chdir` | B-contextlib.chdir | 126 |
| `tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py` | `_run` | cwd | `call:os.chdir` | B-contextlib.chdir | 249 |
| `tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py` | `_run` | cwd | `call:os.chdir` | B-contextlib.chdir | 253 |
| `tests/specify_cli/session_presence/conftest.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 19 |
| `tests/specify_cli/test_bytecode_heal.py` | `fake_pkg` | sys.modules | `subscript-del` | A-monkeypatch | 44 |
| `tests/specify_cli/test_bytecode_heal.py` | `_purge_pkg_modules` | sys.modules | `subscript-del` | A-monkeypatch | 54 |
| `tests/specify_cli/upgrade/migrations/test_m_3_2_0rc39_refresh_orientation_block.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 20 |
| `tests/specify_cli/upgrade/migrations/test_m_session_presence_all_harnesses.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 21 |
| `tests/specify_cli/upgrade/migrations/test_m_session_presence_claude_code.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 20 |
| `tests/specify_cli/upgrade/migrations/test_retired_hosted_target.py` | `_run_upgrade` | cwd | `call:os.chdir` | B-contextlib.chdir | 285 |
| `tests/specify_cli/upgrade/migrations/test_retired_hosted_target.py` | `_run_upgrade` | cwd | `call:os.chdir` | B-contextlib.chdir | 288 |
| `tests/specify_cli/upgrade/migrations/test_session_presence_upgrade_smoke.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 25 |
| `tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py` | `_run_upgrade` | cwd | `call:os.chdir` | B-contextlib.chdir | 199 |
| `tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py` | `_run_upgrade` | cwd | `call:os.chdir` | B-contextlib.chdir | 202 |

## Branch Strategy

- **Strategy**: lane-based execution worktree
- **Planning base branch**: `issue-5119-merge-seam-test-isolation`
- **Merge target branch**: `issue-5119-merge-seam-test-isolation`
- The execution worktree is allocated per computed lane from `lanes.json`. Prepare it only with `.venv/bin/spec-kitty agent action implement WP10 --agent claude` (never reconstruct the path). This WP depends on **WP01** (the census gate and shard files must exist).
- Use `.venv/bin/python` / `.venv/bin/spec-kitty` — the `spec-kitty` on PATH may resolve to a different checkout. Never a bare `uv run` (it re-syncs the hand-built `.venv`).

## Subtasks & Detailed Guidance

### Subtask T046 – Capture the behavior baseline

- **Purpose**: Freeze per-test-id outcomes of the owned files before any edit (NFR-002).
- **Steps**:
  1. In the lane worktree, before editing, run:
     ```bash
     .venv/bin/python -m pytest tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py tests/specify_cli/charter_runtime/test_boundary_heal.py tests/specify_cli/charter_runtime/test_references_parity_refresh.py ... -p no:randomly -q --junitxml=$SCRATCH/WP10-before.xml
     ```
     (pass **all** owned files; `$SCRATCH` = a temp dir outside the repo).
  2. Record pass/skip/xfail counts in the Activity Log. Any pre-existing red: classify via the baseline-red gotcha (CLAUDE.md) — confirm it is red on the WP base too; never "fix" an unrelated known-P0 red.
  3. Run the gate and note the shard's current row set: `.venv/bin/python -m pytest tests/architectural/test_no_manual_global_state_mutation.py -q` (green at WP01 head).
- **Files**: none edited.
- **Parallel?**: no — first.

### Subtask T047 – Convert class A sites (`monkeypatch.*`)

- **Purpose**: Function-scoped test mutations become fixture-restored patches.
- **Recipes**:
  - `os.chdir(p)` for the whole test → `monkeypatch.chdir(p)`; delete the manual restore. An A-row `os.chdir(target)` paired with a B-row `os.chdir(original)` restore in the same test is **one** conversion (both rows disappear).
  - `os.environ["K"] = v` → `monkeypatch.setenv("K", v)`; `os.environ.pop("K", None)` / `del os.environ["K"]` → `monkeypatch.delenv("K", raising=False)`; `os.environ.update({...})` → one `setenv` per key.
  - `sys.argv = [...]` → `monkeypatch.setattr(sys, "argv", [...])`.
  - `sys.path.insert(0, p)` inside a test → `monkeypatch.syspath_prepend(str(p))` (or delete if redundant — class D1).
  - `sys.modules["m"] = fake` → `monkeypatch.setitem(sys.modules, "m", fake)`; `del sys.modules["m"]` / `.pop("m", None)` → `monkeypatch.delitem(sys.modules, "m", raising=False)`. If the test relies on a fresh re-import of a submodule, also `monkeypatch.delattr(parent_pkg, "sub", raising=False)` — `delitem` does not restore the parent package attribute.
  - Class `A-monkeypatch(autouse-fixture)`: module-level `os.environ.setdefault("K", v)` → an `@pytest.fixture(autouse=True)` in that module doing `monkeypatch.setenv("K", v)` (verify the product reads the variable per call, not at import).
  - Helpers (`_invoke`, `_run`, `_restore_modules`, …) that mutate on the caller's behalf: add a `monkeypatch` parameter and thread it through, or turn the helper into a context manager.
- **Parallel?**: per file, yes.
- **Notes**: keep assertions untouched; the goal is identical behavior with guaranteed restoration.

### Subtask T048 – Convert class B sites (block-scoped)

- **Purpose**: Mutations that must be undone *mid-test* (or inside helpers invoked several times per test) use a context manager, not `monkeypatch` (which restores only at teardown).
- **Recipes**:
  - The canonical helper pattern
    ```python
    old = os.getcwd(); os.chdir(repo)
    try:
        result = runner.invoke(app, args)
    finally:
        os.chdir(old)
    ```
    becomes
    ```python
    with contextlib.chdir(repo):
        result = runner.invoke(app, args)
    ```
    (Python 3.11+; add `import contextlib`; drop the now-unused `os.getcwd()` capture).
  - Block-scoped env → `with mock.patch.dict(os.environ, {"K": "v"}):` (use `clear=False`, the default; for removals inside the block, `patch.dict` then `os.environ.pop` **inside** the `with` is still an offender — prefer building the dict and `clear=True` only if the original test cleared the whole env).
  - Block-scoped argv → `with mock.patch.object(sys, "argv", [...]):`.
- **Parallel?**: per file, yes.
- **Notes**: if the site is really whole-test scoped, class A is fine — the classifier is heuristic; choose the facility that preserves semantics and record reclassifications in the Activity Log.

### Subtask T049 – Class C / D sites and justified-row review

- **Purpose**: Handle scope-wide and import-time mutations, and validate every remaining justified row.
- **Recipes**:
  - **C** — module/session-scoped fixture: `with pytest.MonkeyPatch.context() as mp: mp.setenv(...); yield`.
  - **D1** — redundant import-time `sys.path.insert` of the repo root, `src`, a worktree `src`, or `Path.cwd()/"src"`: **delete** it. The repo root is on `sys.path` via pytest rootdir-prepend (`tests/__init__.py` exists) and `src` via `pythonpath = src` in `pytest.ini`. Re-run the file to prove every import still resolves. Do **not** change `pytest.ini` (cross-cutting; out of scope).
  - **D2** — `src/specify_cli` inserted so `import gitignore_manager` works bare: import `specify_cli.gitignore_manager` (a bare import gives the module a second identity).
  - **D3** — `scripts`/`scripts/<pkg>` inserted for bare sibling imports: rewrite to the canonical `scripts.<pkg>.<mod>` import where it resolves; delete the insert.
  - **E rows** in this shard (`process-bootstrap` / `subprocess-entry` / `leak-sentinel`): read each site. Keep the row only if the mutation genuinely must touch real process state (e.g. runs in a child process / subprocess entry, must precede any fixture, or is the leak detector itself). If it can be converted, convert it **and** remove the row. Make each kept row's `reason` accurate.
- **Parallel?**: per file.

### Subtask T050 – Drain shard S5 and verify

- **Purpose**: Prove the shard is clean and behavior is unchanged.
- **Steps**:
  1. Recorded out-of-map edit (add a one-line rationale to the Activity Log): in `tests/architectural/global_state_allowlist/S5.yaml` delete **all** `transitional-sweep` rows; adjust justified rows' `count` to the exact remaining site count (or delete rows you converted). Touch no other shard.
  2. Gate: `.venv/bin/python -m pytest tests/architectural/test_no_manual_global_state_mutation.py -q` — must pass.
  3. Behavior: rerun the owned files with `--junitxml=$SCRATCH/WP10-after.xml` and compare:
     ```python
     import sys, xml.etree.ElementTree as ET
     def outcomes(p):
         out = {}
         for tc in ET.parse(p).iter("testcase"):
             k = f"{tc.get('classname')}::{tc.get('name')}"
             child = next((c for c in tc if c.tag in ("failure", "error", "skipped")), None)
             # distinguish skip vs xfail (both are <skipped>; the `type` attribute differs)
             out[k] = "passed" if child is None else f"{child.tag}:{child.get('type', '')}"
         return out
     b, a = outcomes(sys.argv[1]), outcomes(sys.argv[2])
     # an empty / collection-error XML must never compare as "identical"
     assert b and a, f"empty junit: before={len(b)} after={len(a)}"
     assert len(b) == len(a), f"testcase count changed: {len(b)} -> {len(a)}"
     diff = {k: (b.get(k), a.get(k)) for k in b.keys() | a.keys() if b.get(k) != a.get(k)}
     print(diff or f"identical ({len(a)} testcases)"); sys.exit(1 if diff else 0)
     ```
  4. Parallel safety: `.venv/bin/python -m pytest <owned files> -q -n auto --dist loadfile`.
  5. `.venv/bin/python -m ruff format <touched files>` then `.venv/bin/python -m ruff check <touched files>`; mypy: check `pyproject.toml` `[tool.mypy]` — if the touched test files are in scope, run `.venv/bin/python -m mypy <touched files>` (zero new errors); otherwise record "mypy N/A: file excluded from mypy (pyproject [tool.mypy])" in the Activity Log.
  6. `make test-fast` (baseline).
  7. Neighbouring `tests/`-scanning gates (the sweep must not disturb their verdicts): `.venv/bin/python -m pytest tests/architectural/test_home_pin*.py tests/architectural/test_no_sys_modules_patch_dict.py -q`.
  8. **Tracer append**: add dated 1–3 sentence entries, as they occur, to the mission's `tracer-tooling-friction.md` / `tracer-approach.md` / `tracer-design-decisions.md` (`kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/`) — friction hit, reclassifications, non-obvious fix choices. Do not commit them from the lane; the orchestrator commits them in the lifecycle trail.
  9. Mark subtasks: `.venv/bin/spec-kitty agent tasks mark-status T046 T047 T048 T049 T050 --status done --mission merge-seam-test-isolation-campsite-01M3F61E`.

## Test Strategy

- No new test files: this WP changes how existing tests patch state, not what they assert.
- Evidence to record in the Activity Log: before/after junit comparison output ("identical"), the gate result, the xdist run result, and the final row list of `S5.yaml`.
- Commit granularity: one commit per class or per coherent file group (e.g. `test(isolation): contextlib.chdir in charter CLI invoke helpers (#5118)`); end each commit message with the repo's attribution lines.

## Risks & Mitigations

- **Order dependence surfaces**: a test that silently relied on state leaked by an earlier test may now fail. Fix the root cause in the dependent test (give it the state explicitly) — never reorder, retry, or skip. If it is a pre-existing red unrelated to this shard, classify it via the baseline-red gotcha and note it; do not chase it.
- **`monkeypatch.chdir` too late**: restores only at teardown — a helper called twice per test, or a test that asserts on cwd after a block, needs `contextlib.chdir`.
- **Thread-pool timeouts**: cwd is process-wide; a worker thread that outlives the block observes the restored cwd either way — preserve the original ordering of join/restore.
- **xdist**: `--dist loadfile` keeps a file on one worker; module-level mutations previously leaked to every later file on that worker — the fix removes that coupling, so expect previously-masked failures elsewhere only if some later file depended on the leak (fix that file's setup if it is in this shard; otherwise record it).
- **`sys.modules` re-import**: deleting a submodule without the parent attribute leaves `pkg.sub` pointing at the stale module.
- **Scope creep**: do not refactor tests beyond the mutation sites; boy-scout only inside owned files.

## Review Guidance

- Every row in the shard's site table is either converted or justified; `S5.yaml` has no `transitional-sweep` rows.
- No site was "fixed" by relocation into a helper/conftest, by `patch.dict(sys.modules)`, or by deleting/skipping a test.
- Class choice preserves semantics (block-scoped restores used `contextlib.chdir` / `patch.dict`, not `monkeypatch`).
- Before/after junit comparison is "identical"; xdist run green; no `src/**` change; no new suppressions.
- Justified rows carry an accurate, specific `reason`.
- **Explicit evidence required**: the census gate `tests/architectural/test_no_manual_global_state_mutation.py` green on this lane (the shard YAML edit is out-of-map, so the `owned_files`-scoped pre-review gate will not run it — check the Activity Log output, or run it).
- Home-pin / `sys.modules` gates green; tracer entries appended for anything non-obvious.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

- 2026-09-26T16:40:00Z – system – Prompt created.
- 2026-09-26T19:05:32Z – claude (python-pedro, WP10) – Converted all 49 sites across 20 owned files: monkeypatch.chdir/setitem for whole-test-scoped cwd/sys.modules mutations and helper pairs (test_write_seam_thunk.py, test_context_lifecycle.py, test_runtime_bridge_dispatch.py, test_runtime_bridge_documentation_composition.py); contextlib.chdir for block-scoped/repeated-invocation cwd helpers (test_boundary_heal.py, test_references_parity_refresh.py, all 5 orchestrator_api files, test_retired_hosted_target.py, test_upgrade_provisions_mission_type_activations.py); deleted 5 redundant import-time sys.path.insert sites (class D1) in session_presence/conftest.py and 4 upgrade-migration test files, re-verified imports resolve via pytest.ini's `pythonpath = src`. Reclassified 2 sites (test_bytecode_heal.py's `fake_pkg` fixture teardown + `_purge_pkg_modules` helper) from transitional-sweep to leak-sentinel: converting to monkeypatch.delitem is unsafe here because the fixture purges and reimports the same synthetic-package sys.modules key twice per test, and monkeypatch replays its undo stack LIFO at teardown, which empirically (verified with a standalone repro) resurrects the FIRST (stale) module object into sys.modules after the test ends — exactly the leak these two sites exist to prevent. Drained all `transitional-sweep` rows from S5.yaml (recorded out-of-map edit) leaving only the 2 justified leak-sentinel rows with accurate reasons. Fixed one incidental ruff SIM117 (nested `with` → combined) and removed one unneeded `# type: ignore[arg-type]` (mypy did not need it after the monkeypatch.setitem conversion) surfaced while verifying the diff, plus 3 stale mypy "Missing type arguments for generic type dict" findings resolved as a side effect of deleting the bare-`dict`-typed `_restore_modules` helper. Evidence: before/after junit comparison over all 20 owned files is "identical (292 testcases)" (290 passed, 2 skipped both times); census gate (`test_no_manual_global_state_mutation.py`) 44 passed; home-pin + sys.modules-patch_dict gates 154 passed; owned files green under `-n 4 --dist loadfile` (290 passed, 2 skipped); `ruff check` clean on all touched files; `ruff format --check` clean on the 9 non-ratchet files (10 files, incl. test_context_lifecycle.py, test_boundary_heal.py, test_references_parity_refresh.py, test_write_seam_thunk.py, test_occurrence_map_field_paths.py, test_runtime_bridge_dispatch.py, test_runtime_bridge_documentation_composition.py, and 3 session_presence-migration files, are pre-existing entries in `[tool.ruff.format].exclude` — left untouched, not reformatted, since lifting the shrink-only ratchet is out of this WP's scope); mypy over all 19 touched files shows zero new errors (diffed against a `git stash`-isolated baseline: identical pre-existing errors at shifted line numbers, net -3 from the dict-type-arg fix). No `src/**` touched. Subtasks T046-T050 marked done.
- 2026-09-26T20:08:13Z – claude (python-pedro, WP10) – Review cycle 1 fix (REJECT, HIGH): the reviewer proved the two test_bytecode_heal.py sites ARE convertible — my naive `monkeypatch.delitem(sys.modules, name, raising=False)` was unsafe because `delitem` records nothing when the key is already absent, so it cannot anchor "absent" as the pre-state, letting a later purge/reimport cycle's stale value get restored at teardown. Applied the reviewer-proven fix: `_purge_pkg_modules(monkeypatch)` now loops over a fixed `_PKG_MODULES` tuple doing `monkeypatch.setitem(sys.modules, name, None)` then `monkeypatch.delitem(sys.modules, name)` per name (setitem always records, so the pair's undo always leaves the key absent); `fake_pkg` calls it once at fixture setup (load-bearing anchor — `test_laundered_genuine_import_bug_is_not_healed` imports without purging first) and no longer purges at teardown; `_import_pkg` and all 6 call-site tests thread `monkeypatch` through. Proof reproduced: this file's 11 tests + a trailing same-process probe (asserts no `skbh_fake_pkg*` key remains in `sys.modules`) — 12 passed; each of the 11 tests run alone followed by the probe — all 11 clean. Removed both `leak-sentinel` rows from `S5.yaml`; shard S5 now ends with `rows: []` (0 rows), matching the reviewer's required end state and keeping the frozen `leak-sentinel` seal cap (2, held entirely by S8) untouched. Re-verified: census gate 44 passed, home-pin + sys.modules-patch_dict gates 154 passed, all 20 owned files under `-n 4 --dist loadfile` 290 passed/2 skipped, `ruff format`+`ruff check` clean on the modified file (reformatted the new multi-line signatures to ruff's single-line preference), mypy shows the same 2 pre-existing `func-returns-value` findings at shifted line numbers (zero new). No tracer files touched; no pyproject.toml edit. Re-claimed via `implement WP10 --allow-sparse-checkout` after the reject reset lane-j's claim; re-ran mark-status T046-T050.
