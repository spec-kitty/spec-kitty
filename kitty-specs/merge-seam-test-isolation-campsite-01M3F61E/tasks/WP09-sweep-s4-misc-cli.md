---
work_package_id: WP09
title: 'Sweep S4: misc CLI tests'
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
base_commit: da17791c85ee8d57c5535d41b7ce7f619f34c387
created_at: '2026-09-26T18:11:38.195736+00:00'
subtasks:
- T041
- T042
- T043
- T044
- T045
phase: Phase 3 - Test-isolation sweep
history:
- at: '2026-09-26T16:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/specify_cli/cli/commands/agent/test_setup_plan_branch_match.py
- tests/specify_cli/cli/commands/agent/test_setup_plan_read_surface.py
- tests/specify_cli/cli/commands/test_completion_fast_path.py
- tests/specify_cli/cli/commands/test_init_hybrid.py
- tests/specify_cli/cli/commands/test_init_schema_stamp.py
- tests/specify_cli/cli/commands/test_issue_2876_plan_non_interactive_hang.py
- tests/specify_cli/cli/commands/test_issue_3033_post_consolidation_write.py
- tests/specify_cli/cli/commands/test_merge_cli_golden.py
- tests/specify_cli/cli/commands/test_research_read_surface.py
- tests/specify_cli/cli/commands/test_safe_commit_cli.py
- tests/specify_cli/cli/commands/test_safe_commit_cmd.py
- tests/specify_cli/cli/commands/test_session_start.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP09 – Sweep S4: misc CLI tests

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (`packs/built-in/agent_profiles/python-pedro.agent.yaml`), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `.venv/bin/spec-kitty agent profile list` and select the best match for `task_type: implement` on `tests/specify_cli/cli/commands/`.

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

Issue **#5118** (FR-006, NFR-002, C-005). This work package converts every **manual global-state mutation** in shard **S4** (48 sites across 12 files) to a **scoped patching facility**, then drains shard S4's `transitional-sweep` rows from the census allowlist landed by WP01.

Done means:

- Every `transitional-sweep` row in `tests/architectural/global_state_allowlist/S4.yaml` is gone; only genuinely justified rows (`process-bootstrap` / `subprocess-entry` / `leak-sentinel`, each with a truthful `reason`) remain, and their counts are exact.
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
- **Ownership**: edit only the files in `owned_files`, plus exactly one recorded out-of-map edit: `tests/architectural/global_state_allowlist/S4.yaml` (drain step). Never edit other shards, the detector, the gate, or files owned by mission `01M3EW3Z`.

### Shard notes

- **Shard focus**: `safe_commit*` (14 in `safe_commit_cli`), `completion`, `commands/agent/`, and misc CLI command tests — 12 files, mixed classes.
- Five files are class `B-mock.patch.dict/object` (`completion_fast_path`, `merge_cli_golden`, `research_read_surface`, `setup_plan_*`): block-scoped env/argv helpers.
- `safe_commit` tests often chdir into a git repo fixture and back; prefer `monkeypatch.chdir(repo)` when the whole test runs in the repo, `contextlib.chdir` when only a block does.

### Owned files (12 files / 48 sites)

| File | Sites |
|---|---|
| `tests/specify_cli/cli/commands/agent/test_setup_plan_branch_match.py` | 5 |
| `tests/specify_cli/cli/commands/agent/test_setup_plan_read_surface.py` | 5 |
| `tests/specify_cli/cli/commands/test_completion_fast_path.py` | 7 |
| `tests/specify_cli/cli/commands/test_init_hybrid.py` | 1 |
| `tests/specify_cli/cli/commands/test_init_schema_stamp.py` | 1 |
| `tests/specify_cli/cli/commands/test_issue_2876_plan_non_interactive_hang.py` | 2 |
| `tests/specify_cli/cli/commands/test_issue_3033_post_consolidation_write.py` | 2 |
| `tests/specify_cli/cli/commands/test_merge_cli_golden.py` | 2 |
| `tests/specify_cli/cli/commands/test_research_read_surface.py` | 2 |
| `tests/specify_cli/cli/commands/test_safe_commit_cli.py` | 14 |
| `tests/specify_cli/cli/commands/test_safe_commit_cmd.py` | 6 |
| `tests/specify_cli/cli/commands/test_session_start.py` | 1 |

### Fix-class distribution

| Class | Sites |
|---|---|
| A-monkeypatch | 13 |
| B-contextlib.chdir | 13 |
| B-mock.patch.dict/object(block) | 19 |
| D1-delete-redundant-insert | 3 |

### Site to-do list

Line numbers are navigation only (the allowlist is keyed on file + qualname + kind). Re-run the detector if lines drifted.

| File | Qualname | Kind | Form | Fix class | Line (nav only) |
|---|---|---|---|---|---|
| `tests/specify_cli/cli/commands/agent/test_setup_plan_branch_match.py` | `_run_setup_plan_from` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 127 |
| `tests/specify_cli/cli/commands/agent/test_setup_plan_branch_match.py` | `_run_setup_plan_from` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 129 |
| `tests/specify_cli/cli/commands/agent/test_setup_plan_branch_match.py` | `_run_setup_plan_from` | os.environ | `call:.pop` | B-mock.patch.dict/object(block) | 143 |
| `tests/specify_cli/cli/commands/agent/test_setup_plan_branch_match.py` | `_run_setup_plan_from` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 145 |
| `tests/specify_cli/cli/commands/agent/test_setup_plan_branch_match.py` | `_run_setup_plan_from` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 147 |
| `tests/specify_cli/cli/commands/agent/test_setup_plan_read_surface.py` | `_run_setup_plan` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 139 |
| `tests/specify_cli/cli/commands/agent/test_setup_plan_read_surface.py` | `_run_setup_plan` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 145 |
| `tests/specify_cli/cli/commands/agent/test_setup_plan_read_surface.py` | `_run_setup_plan` | os.environ | `call:.pop` | B-mock.patch.dict/object(block) | 170 |
| `tests/specify_cli/cli/commands/agent/test_setup_plan_read_surface.py` | `_run_setup_plan` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 172 |
| `tests/specify_cli/cli/commands/agent/test_setup_plan_read_surface.py` | `_run_setup_plan` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 174 |
| `tests/specify_cli/cli/commands/test_completion_fast_path.py` | `_drive` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 51 |
| `tests/specify_cli/cli/commands/test_completion_fast_path.py` | `_drive` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 52 |
| `tests/specify_cli/cli/commands/test_completion_fast_path.py` | `_drive` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 53 |
| `tests/specify_cli/cli/commands/test_completion_fast_path.py` | `_drive` | os.environ | `call:.pop` | B-mock.patch.dict/object(block) | 61 |
| `tests/specify_cli/cli/commands/test_completion_fast_path.py` | `_drive` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 63 |
| `tests/specify_cli/cli/commands/test_completion_fast_path.py` | `test_generate_manifest_ignores_ambient_argv_narrowing` | sys.argv | `rebind-store` | A-monkeypatch | 236 |
| `tests/specify_cli/cli/commands/test_completion_fast_path.py` | `test_generate_manifest_ignores_ambient_argv_narrowing` | sys.argv | `rebind-store` | A-monkeypatch | 240 |
| `tests/specify_cli/cli/commands/test_init_hybrid.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 17 |
| `tests/specify_cli/cli/commands/test_init_schema_stamp.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 27 |
| `tests/specify_cli/cli/commands/test_issue_2876_plan_non_interactive_hang.py` | `_invoke_plan_non_interactive` | cwd | `call:os.chdir` | B-contextlib.chdir | 133 |
| `tests/specify_cli/cli/commands/test_issue_2876_plan_non_interactive_hang.py` | `_invoke_plan_non_interactive` | cwd | `call:os.chdir` | B-contextlib.chdir | 151 |
| `tests/specify_cli/cli/commands/test_issue_3033_post_consolidation_write.py` | `test_safe_commit_succeeds_for_primary_kind_write_on_e2_mission` | cwd | `call:os.chdir` | A-monkeypatch | 427 |
| `tests/specify_cli/cli/commands/test_issue_3033_post_consolidation_write.py` | `test_safe_commit_succeeds_for_primary_kind_write_on_e2_mission` | cwd | `call:os.chdir` | B-contextlib.chdir | 440 |
| `tests/specify_cli/cli/commands/test_merge_cli_golden.py` | `_registered_top_level_commands` | sys.argv | `rebind-store` | B-mock.patch.dict/object(block) | 193 |
| `tests/specify_cli/cli/commands/test_merge_cli_golden.py` | `_registered_top_level_commands` | sys.argv | `rebind-store` | B-mock.patch.dict/object(block) | 197 |
| `tests/specify_cli/cli/commands/test_research_read_surface.py` | `_run_research` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 183 |
| `tests/specify_cli/cli/commands/test_research_read_surface.py` | `_run_research` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 199 |
| `tests/specify_cli/cli/commands/test_safe_commit_cli.py` | `test_cli_with_to_branch` | cwd | `call:os.chdir` | A-monkeypatch | 70 |
| `tests/specify_cli/cli/commands/test_safe_commit_cli.py` | `test_cli_with_to_branch` | cwd | `call:os.chdir` | B-contextlib.chdir | 85 |
| `tests/specify_cli/cli/commands/test_safe_commit_cli.py` | `test_cli_without_to_branch_infers_head_with_warning` | cwd | `call:os.chdir` | A-monkeypatch | 110 |
| `tests/specify_cli/cli/commands/test_safe_commit_cli.py` | `test_cli_without_to_branch_infers_head_with_warning` | cwd | `call:os.chdir` | B-contextlib.chdir | 117 |
| `tests/specify_cli/cli/commands/test_safe_commit_cli.py` | `test_cli_head_mismatch` | cwd | `call:os.chdir` | A-monkeypatch | 146 |
| `tests/specify_cli/cli/commands/test_safe_commit_cli.py` | `test_cli_head_mismatch` | cwd | `call:os.chdir` | B-contextlib.chdir | 161 |
| `tests/specify_cli/cli/commands/test_safe_commit_cli.py` | `test_cli_dir_arg_mixed_modified_and_untracked_commits_all_with_report` | cwd | `call:os.chdir` | A-monkeypatch | 215 |
| `tests/specify_cli/cli/commands/test_safe_commit_cli.py` | `test_cli_dir_arg_mixed_modified_and_untracked_commits_all_with_report` | cwd | `call:os.chdir` | B-contextlib.chdir | 222 |
| `tests/specify_cli/cli/commands/test_safe_commit_cli.py` | `test_cli_to_branch_honored_from_non_target_cwd` | cwd | `call:os.chdir` | A-monkeypatch | 263 |
| `tests/specify_cli/cli/commands/test_safe_commit_cli.py` | `test_cli_to_branch_honored_from_non_target_cwd` | cwd | `call:os.chdir` | B-contextlib.chdir | 272 |
| `tests/specify_cli/cli/commands/test_safe_commit_cli.py` | `test_cli_retired_env_var_has_no_effect` | cwd | `call:os.chdir` | A-monkeypatch | 300 |
| `tests/specify_cli/cli/commands/test_safe_commit_cli.py` | `test_cli_retired_env_var_has_no_effect` | cwd | `call:os.chdir` | B-contextlib.chdir | 307 |
| `tests/specify_cli/cli/commands/test_safe_commit_cli.py` | `test_cli_genuinely_different_file_never_reports_no_changes` | cwd | `call:os.chdir` | A-monkeypatch | 339 |
| `tests/specify_cli/cli/commands/test_safe_commit_cli.py` | `test_cli_genuinely_different_file_never_reports_no_changes` | cwd | `call:os.chdir` | B-contextlib.chdir | 347 |
| `tests/specify_cli/cli/commands/test_safe_commit_cmd.py` | `test_public_safe_commit_does_not_honor_internal_protected_branch_exceptions` | cwd | `call:os.chdir` | A-monkeypatch | 165 |
| `tests/specify_cli/cli/commands/test_safe_commit_cmd.py` | `test_public_safe_commit_does_not_honor_internal_protected_branch_exceptions` | cwd | `call:os.chdir` | B-contextlib.chdir | 175 |
| `tests/specify_cli/cli/commands/test_safe_commit_cmd.py` | `test_public_safe_commit_rejects_protected_branch_in_test_mode` | cwd | `call:os.chdir` | A-monkeypatch | 211 |
| `tests/specify_cli/cli/commands/test_safe_commit_cmd.py` | `test_public_safe_commit_rejects_protected_branch_in_test_mode` | cwd | `call:os.chdir` | B-contextlib.chdir | 226 |
| `tests/specify_cli/cli/commands/test_safe_commit_cmd.py` | `test_public_safe_commit_succeeds_after_merged_branch_deleted_3033` | cwd | `call:os.chdir` | A-monkeypatch | 346 |
| `tests/specify_cli/cli/commands/test_safe_commit_cmd.py` | `test_public_safe_commit_succeeds_after_merged_branch_deleted_3033` | cwd | `call:os.chdir` | B-contextlib.chdir | 359 |
| `tests/specify_cli/cli/commands/test_session_start.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 27 |

## Branch Strategy

- **Strategy**: lane-based execution worktree
- **Planning base branch**: `issue-5119-merge-seam-test-isolation`
- **Merge target branch**: `issue-5119-merge-seam-test-isolation`
- The execution worktree is allocated per computed lane from `lanes.json`. Prepare it only with `.venv/bin/spec-kitty agent action implement WP09 --agent claude` (never reconstruct the path). This WP depends on **WP01** (the census gate and shard files must exist).
- Use `.venv/bin/python` / `.venv/bin/spec-kitty` — the `spec-kitty` on PATH may resolve to a different checkout. Never a bare `uv run` (it re-syncs the hand-built `.venv`).

## Subtasks & Detailed Guidance

### Subtask T041 – Capture the behavior baseline

- **Purpose**: Freeze per-test-id outcomes of the owned files before any edit (NFR-002).
- **Steps**:
  1. In the lane worktree, before editing, run:
     ```bash
     .venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_setup_plan_branch_match.py tests/specify_cli/cli/commands/agent/test_setup_plan_read_surface.py tests/specify_cli/cli/commands/test_completion_fast_path.py ... -p no:randomly -q --junitxml=$SCRATCH/WP09-before.xml
     ```
     (pass **all** owned files; `$SCRATCH` = a temp dir outside the repo).
  2. Record pass/skip/xfail counts in the Activity Log. Any pre-existing red: classify via the baseline-red gotcha (CLAUDE.md) — confirm it is red on the WP base too; never "fix" an unrelated known-P0 red.
  3. Run the gate and note the shard's current row set: `.venv/bin/python -m pytest tests/architectural/test_no_manual_global_state_mutation.py -q` (green at WP01 head).
- **Files**: none edited.
- **Parallel?**: no — first.

### Subtask T042 – Convert class A sites (`monkeypatch.*`)

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

### Subtask T043 – Convert class B sites (block-scoped)

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

### Subtask T044 – Class C / D sites and justified-row review

- **Purpose**: Handle scope-wide and import-time mutations, and validate every remaining justified row.
- **Recipes**:
  - **C** — module/session-scoped fixture: `with pytest.MonkeyPatch.context() as mp: mp.setenv(...); yield`.
  - **D1** — redundant import-time `sys.path.insert` of the repo root, `src`, a worktree `src`, or `Path.cwd()/"src"`: **delete** it. The repo root is on `sys.path` via pytest rootdir-prepend (`tests/__init__.py` exists) and `src` via `pythonpath = src` in `pytest.ini`. Re-run the file to prove every import still resolves. Do **not** change `pytest.ini` (cross-cutting; out of scope).
  - **D2** — `src/specify_cli` inserted so `import gitignore_manager` works bare: import `specify_cli.gitignore_manager` (a bare import gives the module a second identity).
  - **D3** — `scripts`/`scripts/<pkg>` inserted for bare sibling imports: rewrite to the canonical `scripts.<pkg>.<mod>` import where it resolves; delete the insert.
  - **E rows** in this shard (`process-bootstrap` / `subprocess-entry` / `leak-sentinel`): read each site. Keep the row only if the mutation genuinely must touch real process state (e.g. runs in a child process / subprocess entry, must precede any fixture, or is the leak detector itself). If it can be converted, convert it **and** remove the row. Make each kept row's `reason` accurate.
- **Parallel?**: per file.

### Subtask T045 – Drain shard S4 and verify

- **Purpose**: Prove the shard is clean and behavior is unchanged.
- **Steps**:
  1. Recorded out-of-map edit (add a one-line rationale to the Activity Log): in `tests/architectural/global_state_allowlist/S4.yaml` delete **all** `transitional-sweep` rows; adjust justified rows' `count` to the exact remaining site count (or delete rows you converted). Touch no other shard.
  2. Gate: `.venv/bin/python -m pytest tests/architectural/test_no_manual_global_state_mutation.py -q` — must pass.
  3. Behavior: rerun the owned files with `--junitxml=$SCRATCH/WP09-after.xml` and compare:
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
  9. Mark subtasks: `.venv/bin/spec-kitty agent tasks mark-status T041 T042 T043 T044 T045 --status done --mission merge-seam-test-isolation-campsite-01M3F61E`.

## Test Strategy

- No new test files: this WP changes how existing tests patch state, not what they assert.
- Evidence to record in the Activity Log: before/after junit comparison output ("identical"), the gate result, the xdist run result, and the final row list of `S4.yaml`.
- Commit granularity: one commit per class or per coherent file group (e.g. `test(isolation): contextlib.chdir in charter CLI invoke helpers (#5118)`); end each commit message with the repo's attribution lines.

## Risks & Mitigations

- **Order dependence surfaces**: a test that silently relied on state leaked by an earlier test may now fail. Fix the root cause in the dependent test (give it the state explicitly) — never reorder, retry, or skip. If it is a pre-existing red unrelated to this shard, classify it via the baseline-red gotcha and note it; do not chase it.
- **`monkeypatch.chdir` too late**: restores only at teardown — a helper called twice per test, or a test that asserts on cwd after a block, needs `contextlib.chdir`.
- **Thread-pool timeouts**: cwd is process-wide; a worker thread that outlives the block observes the restored cwd either way — preserve the original ordering of join/restore.
- **xdist**: `--dist loadfile` keeps a file on one worker; module-level mutations previously leaked to every later file on that worker — the fix removes that coupling, so expect previously-masked failures elsewhere only if some later file depended on the leak (fix that file's setup if it is in this shard; otherwise record it).
- **`sys.modules` re-import**: deleting a submodule without the parent attribute leaves `pkg.sub` pointing at the stale module.
- **Scope creep**: do not refactor tests beyond the mutation sites; boy-scout only inside owned files.

## Review Guidance

- Every row in the shard's site table is either converted or justified; `S4.yaml` has no `transitional-sweep` rows.
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
- 2026-09-26T21:10:00Z – claude – Captured before-junit (92 passed, 1 skipped) over all 12 owned files, then converted all 21 shard-S4 transitional-sweep sites: monkeypatch.setenv (setup_plan_from/read_surface env try/finally, 2 files, 10 sites — also fixed a latent leak where the original finally skipped restoration when the prior value was unset), mock.patch.dict(os.environ, ...) block-scoped helpers (`_drive` in test_completion_fast_path.py, `_run_research` in test_research_read_surface.py), monkeypatch.setattr(sys, "argv", ...) / mock.patch.object(sys, "argv", ...) for the two argv sites (test_completion_fast_path.py, test_merge_cli_golden.py), contextlib.chdir for the single-caller `_invoke_plan_non_interactive` helper, monkeypatch.chdir for 10 whole-test os.chdir(target)/finally-restore pairs across test_safe_commit_cli.py (7) and test_safe_commit_cmd.py (3) — each A+B row pair collapsed into one conversion per contract guidance — and deleted 3 redundant import-time `sys.path.insert` calls (test_init_hybrid.py, test_init_schema_stamp.py, test_session_start.py) now covered by pytest.ini's `pythonpath = src`. Drained S4.yaml's `rows:` to `[]` (all 21 rows were transitional-sweep; none justified). Verified: census gate green (44 passed); direct `_global_state_scan.scan()` probe shows zero remaining sites in the 12 owned files; after-junit identical to before (93 testcases, 92 passed/1 skipped, 0 deleted/newly-skipped); green under `-n 4 --dist loadfile`; `tests/architectural/test_home_pin*.py` + `test_no_sys_modules_patch_dict.py` green (154 passed); ruff check/format clean on all touched files; one pre-existing mypy `arg-type` finding in test_completion_fast_path.py:58 (`shell_complete(command, ...)` — `command: object` vs `Command`) confirmed red on the unmodified base file, not touched by this WP's edits, left alone per the baseline-red gotcha. Moved WP09 to for_review.
