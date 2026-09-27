---
work_package_id: WP08
title: 'Sweep S3: doctrine/doctor/upgrade CLI tests'
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
base_commit: ac926671fe9de4ad199cd5892d4bc01a41a7aa09
created_at: '2026-09-26T18:11:15.966153+00:00'
subtasks:
- T036
- T037
- T038
- T039
- T040
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
- tests/specify_cli/cli/commands/test_bytecode_doctor.py
- tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py
- tests/specify_cli/cli/commands/test_doctor_doctrine_collisions.py
- tests/specify_cli/cli/commands/test_doctor_doctrine_selections.py
- tests/specify_cli/cli/commands/test_doctrine_new.py
- tests/specify_cli/cli/commands/test_upgrade_command.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Sweep S3: doctrine/doctor/upgrade CLI tests

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

Issue **#5118** (FR-006, NFR-002, C-005). This work package converts every **manual global-state mutation** in shard **S3** (52 sites across 6 files) to a **scoped patching facility**, then drains shard S3's `transitional-sweep` rows from the census allowlist landed by WP01.

Done means:

- Every `transitional-sweep` row in `tests/architectural/global_state_allowlist/S3.yaml` is gone; only genuinely justified rows (`process-bootstrap` / `subprocess-entry` / `leak-sentinel`, each with a truthful `reason`) remain, and their counts are exact.
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
- **Ownership**: edit only the files in `owned_files`, plus exactly one recorded out-of-map edit: `tests/architectural/global_state_allowlist/S3.yaml` (drain step). Never edit other shards, the detector, the gate, or files owned by mission `01M3EW3Z`.

### Shard notes

- **Shard focus**: `test_doctrine_new.py` (18: 9 A / 9 B restore pairs), `test_upgrade_command.py` (16: 14 A / 2 B), the `doctor_*` tests and `test_bytecode_doctor.py`.
- `SPEC_KITTY_HOME` writes via `setenv`/`[]=`/`.setdefault` are owned by the `_home_pin_scan` gate and are **not** in this shard; deletes/pops of that key are.
- **`sys.modules` sites in this shard** (check whether each relies on a fresh re-import; if so also restore the parent-package attribute): `tests/specify_cli/cli/commands/test_bytecode_doctor.py`.

### Owned files (6 files / 52 sites)

| File | Sites |
|---|---|
| `tests/specify_cli/cli/commands/test_bytecode_doctor.py` | 1 |
| `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py` | 3 |
| `tests/specify_cli/cli/commands/test_doctor_doctrine_collisions.py` | 6 |
| `tests/specify_cli/cli/commands/test_doctor_doctrine_selections.py` | 8 |
| `tests/specify_cli/cli/commands/test_doctrine_new.py` | 18 |
| `tests/specify_cli/cli/commands/test_upgrade_command.py` | 16 |

### Fix-class distribution

| Class | Sites |
|---|---|
| A-monkeypatch | 34 |
| B-contextlib.chdir | 18 |

### Site to-do list

Line numbers are navigation only (the allowlist is keyed on file + qualname + kind). Re-run the detector if lines drifted.

| File | Qualname | Kind | Form | Fix class | Line (nav only) |
|---|---|---|---|---|---|
| `tests/specify_cli/cli/commands/test_bytecode_doctor.py` | `_purge_pkg_modules` | sys.modules | `subscript-del` | A-monkeypatch | 56 |
| `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py` | `test_sparse_checkout_fix_reaches_refusal_or_clean_path` | os.environ | `subscript-store` | A-monkeypatch | 628 |
| `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py` | `test_sparse_checkout_fix_reaches_refusal_or_clean_path` | os.environ | `call:.pop` | A-monkeypatch | 633 |
| `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py` | `test_sparse_checkout_fix_reaches_refusal_or_clean_path` | os.environ | `subscript-store` | A-monkeypatch | 635 |
| `tests/specify_cli/cli/commands/test_doctor_doctrine_collisions.py` | `test_doctor_doctrine_text_shows_collisions` | cwd | `call:os.chdir` | A-monkeypatch | 87 |
| `tests/specify_cli/cli/commands/test_doctor_doctrine_collisions.py` | `test_doctor_doctrine_text_shows_collisions` | cwd | `call:os.chdir` | B-contextlib.chdir | 90 |
| `tests/specify_cli/cli/commands/test_doctor_doctrine_collisions.py` | `test_doctor_doctrine_text_reports_no_collisions_when_pack_disjoint` | cwd | `call:os.chdir` | A-monkeypatch | 115 |
| `tests/specify_cli/cli/commands/test_doctor_doctrine_collisions.py` | `test_doctor_doctrine_text_reports_no_collisions_when_pack_disjoint` | cwd | `call:os.chdir` | B-contextlib.chdir | 118 |
| `tests/specify_cli/cli/commands/test_doctor_doctrine_collisions.py` | `test_doctor_doctrine_json_emits_collisions_array` | cwd | `call:os.chdir` | A-monkeypatch | 140 |
| `tests/specify_cli/cli/commands/test_doctor_doctrine_collisions.py` | `test_doctor_doctrine_json_emits_collisions_array` | cwd | `call:os.chdir` | B-contextlib.chdir | 143 |
| `tests/specify_cli/cli/commands/test_doctor_doctrine_selections.py` | `test_doctor_doctrine_renders_selections_header` | cwd | `call:os.chdir` | A-monkeypatch | 70 |
| `tests/specify_cli/cli/commands/test_doctor_doctrine_selections.py` | `test_doctor_doctrine_renders_selections_header` | cwd | `call:os.chdir` | B-contextlib.chdir | 73 |
| `tests/specify_cli/cli/commands/test_doctor_doctrine_selections.py` | `test_doctor_doctrine_empty_kinds_render_as_none` | cwd | `call:os.chdir` | A-monkeypatch | 86 |
| `tests/specify_cli/cli/commands/test_doctor_doctrine_selections.py` | `test_doctor_doctrine_empty_kinds_render_as_none` | cwd | `call:os.chdir` | B-contextlib.chdir | 89 |
| `tests/specify_cli/cli/commands/test_doctor_doctrine_selections.py` | `test_doctor_doctrine_lists_declared_project_selections` | cwd | `call:os.chdir` | A-monkeypatch | 105 |
| `tests/specify_cli/cli/commands/test_doctor_doctrine_selections.py` | `test_doctor_doctrine_lists_declared_project_selections` | cwd | `call:os.chdir` | B-contextlib.chdir | 108 |
| `tests/specify_cli/cli/commands/test_doctor_doctrine_selections.py` | `test_doctor_doctrine_json_includes_selections_block` | cwd | `call:os.chdir` | A-monkeypatch | 125 |
| `tests/specify_cli/cli/commands/test_doctor_doctrine_selections.py` | `test_doctor_doctrine_json_includes_selections_block` | cwd | `call:os.chdir` | B-contextlib.chdir | 128 |
| `tests/specify_cli/cli/commands/test_doctrine_new.py` | `test_new_styleguide_writes_stub_under_project_doctrine_root` | cwd | `call:os.chdir` | A-monkeypatch | 42 |
| `tests/specify_cli/cli/commands/test_doctrine_new.py` | `test_new_styleguide_writes_stub_under_project_doctrine_root` | cwd | `call:os.chdir` | B-contextlib.chdir | 47 |
| `tests/specify_cli/cli/commands/test_doctrine_new.py` | `test_new_validates_stub_against_schema_so_validate_passes` | cwd | `call:os.chdir` | A-monkeypatch | 66 |
| `tests/specify_cli/cli/commands/test_doctrine_new.py` | `test_new_validates_stub_against_schema_so_validate_passes` | cwd | `call:os.chdir` | B-contextlib.chdir | 81 |
| `tests/specify_cli/cli/commands/test_doctrine_new.py` | `test_new_special_kind_suffixes_validate_on_first_emit` | cwd | `call:os.chdir` | A-monkeypatch | 111 |
| `tests/specify_cli/cli/commands/test_doctrine_new.py` | `test_new_special_kind_suffixes_validate_on_first_emit` | cwd | `call:os.chdir` | B-contextlib.chdir | 124 |
| `tests/specify_cli/cli/commands/test_doctrine_new.py` | `test_new_asset_scaffolds_where_project_resolver_reads` | cwd | `call:os.chdir` | A-monkeypatch | 147 |
| `tests/specify_cli/cli/commands/test_doctrine_new.py` | `test_new_asset_scaffolds_where_project_resolver_reads` | cwd | `call:os.chdir` | B-contextlib.chdir | 152 |
| `tests/specify_cli/cli/commands/test_doctrine_new.py` | `test_new_asset_stub_validates_on_first_emit` | cwd | `call:os.chdir` | A-monkeypatch | 171 |
| `tests/specify_cli/cli/commands/test_doctrine_new.py` | `test_new_asset_stub_validates_on_first_emit` | cwd | `call:os.chdir` | B-contextlib.chdir | 184 |
| `tests/specify_cli/cli/commands/test_doctrine_new.py` | `test_new_directive_scaffolds_kebab_filename_with_screaming_id_preserved` | cwd | `call:os.chdir` | A-monkeypatch | 201 |
| `tests/specify_cli/cli/commands/test_doctrine_new.py` | `test_new_directive_scaffolds_kebab_filename_with_screaming_id_preserved` | cwd | `call:os.chdir` | B-contextlib.chdir | 206 |
| `tests/specify_cli/cli/commands/test_doctrine_new.py` | `test_scaffolder_engine_and_manifest_slugs_converge_for_screaming_directive` | cwd | `call:os.chdir` | A-monkeypatch | 241 |
| `tests/specify_cli/cli/commands/test_doctrine_new.py` | `test_scaffolder_engine_and_manifest_slugs_converge_for_screaming_directive` | cwd | `call:os.chdir` | B-contextlib.chdir | 255 |
| `tests/specify_cli/cli/commands/test_doctrine_new.py` | `test_new_refuses_to_overwrite_existing_file` | cwd | `call:os.chdir` | A-monkeypatch | 286 |
| `tests/specify_cli/cli/commands/test_doctrine_new.py` | `test_new_refuses_to_overwrite_existing_file` | cwd | `call:os.chdir` | B-contextlib.chdir | 296 |
| `tests/specify_cli/cli/commands/test_doctrine_new.py` | `test_new_rejects_unknown_kind` | cwd | `call:os.chdir` | A-monkeypatch | 308 |
| `tests/specify_cli/cli/commands/test_doctrine_new.py` | `test_new_rejects_unknown_kind` | cwd | `call:os.chdir` | B-contextlib.chdir | 313 |
| `tests/specify_cli/cli/commands/test_upgrade_command.py` | `_invoke_upgrade` | cwd | `call:os.chdir` | B-contextlib.chdir | 197 |
| `tests/specify_cli/cli/commands/test_upgrade_command.py` | `_invoke_upgrade` | cwd | `call:os.chdir` | B-contextlib.chdir | 200 |
| `tests/specify_cli/cli/commands/test_upgrade_command.py` | `test_cli_update_available_dry_run_shows_nag` | cwd | `call:os.chdir` | A-monkeypatch | 370 |
| `tests/specify_cli/cli/commands/test_upgrade_command.py` | `test_cli_update_available_dry_run_shows_nag` | cwd | `call:os.chdir` | A-monkeypatch | 388 |
| `tests/specify_cli/cli/commands/test_upgrade_command.py` | `test_project_migration_needed_planner_json` | cwd | `call:os.chdir` | A-monkeypatch | 442 |
| `tests/specify_cli/cli/commands/test_upgrade_command.py` | `test_project_migration_needed_planner_json` | cwd | `call:os.chdir` | A-monkeypatch | 459 |
| `tests/specify_cli/cli/commands/test_upgrade_command.py` | `test_project_too_new_for_cli_project_state` | cwd | `call:os.chdir` | A-monkeypatch | 571 |
| `tests/specify_cli/cli/commands/test_upgrade_command.py` | `test_project_too_new_for_cli_project_state` | cwd | `call:os.chdir` | A-monkeypatch | 584 |
| `tests/specify_cli/cli/commands/test_upgrade_command.py` | `test_project_not_initialized_planner_state` | cwd | `call:os.chdir` | A-monkeypatch | 620 |
| `tests/specify_cli/cli/commands/test_upgrade_command.py` | `test_project_not_initialized_planner_state` | cwd | `call:os.chdir` | A-monkeypatch | 641 |
| `tests/specify_cli/cli/commands/test_upgrade_command.py` | `test_install_method_unknown_cli_prints_note_not_command` | cwd | `call:os.chdir` | A-monkeypatch | 656 |
| `tests/specify_cli/cli/commands/test_upgrade_command.py` | `test_install_method_unknown_cli_prints_note_not_command` | cwd | `call:os.chdir` | A-monkeypatch | 686 |
| `tests/specify_cli/cli/commands/test_upgrade_command.py` | `test_planner_json_too_new_project_has_exit_code_5_in_payload` | cwd | `call:os.chdir` | A-monkeypatch | 828 |
| `tests/specify_cli/cli/commands/test_upgrade_command.py` | `test_planner_json_too_new_project_has_exit_code_5_in_payload` | cwd | `call:os.chdir` | A-monkeypatch | 847 |
| `tests/specify_cli/cli/commands/test_upgrade_command.py` | `test_project_mode_no_cli_nag_in_output` | cwd | `call:os.chdir` | A-monkeypatch | 925 |
| `tests/specify_cli/cli/commands/test_upgrade_command.py` | `test_project_mode_no_cli_nag_in_output` | cwd | `call:os.chdir` | A-monkeypatch | 946 |

## Branch Strategy

- **Strategy**: lane-based execution worktree
- **Planning base branch**: `issue-5119-merge-seam-test-isolation`
- **Merge target branch**: `issue-5119-merge-seam-test-isolation`
- The execution worktree is allocated per computed lane from `lanes.json`. Prepare it only with `.venv/bin/spec-kitty agent action implement WP08 --agent claude` (never reconstruct the path). This WP depends on **WP01** (the census gate and shard files must exist).
- Use `.venv/bin/python` / `.venv/bin/spec-kitty` — the `spec-kitty` on PATH may resolve to a different checkout. Never a bare `uv run` (it re-syncs the hand-built `.venv`).

## Subtasks & Detailed Guidance

### Subtask T036 – Capture the behavior baseline

- **Purpose**: Freeze per-test-id outcomes of the owned files before any edit (NFR-002).
- **Steps**:
  1. In the lane worktree, before editing, run:
     ```bash
     .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_bytecode_doctor.py tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py tests/specify_cli/cli/commands/test_doctor_doctrine_collisions.py ... -p no:randomly -q --junitxml=$SCRATCH/WP08-before.xml
     ```
     (pass **all** owned files; `$SCRATCH` = a temp dir outside the repo).
  2. Record pass/skip/xfail counts in the Activity Log. Any pre-existing red: classify via the baseline-red gotcha (CLAUDE.md) — confirm it is red on the WP base too; never "fix" an unrelated known-P0 red.
  3. Run the gate and note the shard's current row set: `.venv/bin/python -m pytest tests/architectural/test_no_manual_global_state_mutation.py -q` (green at WP01 head).
- **Files**: none edited.
- **Parallel?**: no — first.

### Subtask T037 – Convert class A sites (`monkeypatch.*`)

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

### Subtask T038 – Convert class B sites (block-scoped)

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

### Subtask T039 – Class C / D sites and justified-row review

- **Purpose**: Handle scope-wide and import-time mutations, and validate every remaining justified row.
- **Recipes**:
  - **C** — module/session-scoped fixture: `with pytest.MonkeyPatch.context() as mp: mp.setenv(...); yield`.
  - **D1** — redundant import-time `sys.path.insert` of the repo root, `src`, a worktree `src`, or `Path.cwd()/"src"`: **delete** it. The repo root is on `sys.path` via pytest rootdir-prepend (`tests/__init__.py` exists) and `src` via `pythonpath = src` in `pytest.ini`. Re-run the file to prove every import still resolves. Do **not** change `pytest.ini` (cross-cutting; out of scope).
  - **D2** — `src/specify_cli` inserted so `import gitignore_manager` works bare: import `specify_cli.gitignore_manager` (a bare import gives the module a second identity).
  - **D3** — `scripts`/`scripts/<pkg>` inserted for bare sibling imports: rewrite to the canonical `scripts.<pkg>.<mod>` import where it resolves; delete the insert.
  - **E rows** in this shard (`process-bootstrap` / `subprocess-entry` / `leak-sentinel`): read each site. Keep the row only if the mutation genuinely must touch real process state (e.g. runs in a child process / subprocess entry, must precede any fixture, or is the leak detector itself). If it can be converted, convert it **and** remove the row. Make each kept row's `reason` accurate.
- **Parallel?**: per file.

### Subtask T040 – Drain shard S3 and verify

- **Purpose**: Prove the shard is clean and behavior is unchanged.
- **Steps**:
  1. Recorded out-of-map edit (add a one-line rationale to the Activity Log): in `tests/architectural/global_state_allowlist/S3.yaml` delete **all** `transitional-sweep` rows; adjust justified rows' `count` to the exact remaining site count (or delete rows you converted). Touch no other shard.
  2. Gate: `.venv/bin/python -m pytest tests/architectural/test_no_manual_global_state_mutation.py -q` — must pass.
  3. Behavior: rerun the owned files with `--junitxml=$SCRATCH/WP08-after.xml` and compare:
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
  9. Mark subtasks: `.venv/bin/spec-kitty agent tasks mark-status T036 T037 T038 T039 T040 --status done --mission merge-seam-test-isolation-campsite-01M3F61E`.

## Test Strategy

- No new test files: this WP changes how existing tests patch state, not what they assert.
- Evidence to record in the Activity Log: before/after junit comparison output ("identical"), the gate result, the xdist run result, and the final row list of `S3.yaml`.
- Commit granularity: one commit per class or per coherent file group (e.g. `test(isolation): contextlib.chdir in charter CLI invoke helpers (#5118)`); end each commit message with the repo's attribution lines.

## Risks & Mitigations

- **Order dependence surfaces**: a test that silently relied on state leaked by an earlier test may now fail. Fix the root cause in the dependent test (give it the state explicitly) — never reorder, retry, or skip. If it is a pre-existing red unrelated to this shard, classify it via the baseline-red gotcha and note it; do not chase it.
- **`monkeypatch.chdir` too late**: restores only at teardown — a helper called twice per test, or a test that asserts on cwd after a block, needs `contextlib.chdir`.
- **Thread-pool timeouts**: cwd is process-wide; a worker thread that outlives the block observes the restored cwd either way — preserve the original ordering of join/restore.
- **xdist**: `--dist loadfile` keeps a file on one worker; module-level mutations previously leaked to every later file on that worker — the fix removes that coupling, so expect previously-masked failures elsewhere only if some later file depended on the leak (fix that file's setup if it is in this shard; otherwise record it).
- **`sys.modules` re-import**: deleting a submodule without the parent attribute leaves `pkg.sub` pointing at the stale module.
- **Scope creep**: do not refactor tests beyond the mutation sites; boy-scout only inside owned files.

## Review Guidance

- Every row in the shard's site table is either converted or justified; `S3.yaml` has no `transitional-sweep` rows.
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
- 2026-09-26T19:05:00Z – claude – Captured before-baseline junit (147 testcases, 2 pre-existing reds unrelated to this shard: `test_registered_command_names_match_frozen_subcommands` and `test_subcommand_help_snapshot[coordination]` in `test_doctor_cli_surface_golden.py`, a golden-snapshot drift confirmed pre-existing on the base commit — not chased). Census gate green on WP01 head before edits.
- 2026-09-26T19:20:00Z – claude – T037: converted `test_bytecode_doctor.py`'s `_purge_pkg_modules` helper to accept `monkeypatch` and use `monkeypatch.delitem(sys.modules, name, raising=False)`; converted `test_doctor_cli_surface_golden.py`'s whole-test `os.environ["CI"]` try/finally to `monkeypatch.setenv`, dropping the now-unused `import os`.
- 2026-09-26T19:35:00Z – claude – T038: converted all A+B `os.chdir`/`os.getcwd()` try/finally pairs in `test_doctor_doctrine_collisions.py` (3), `test_doctor_doctrine_selections.py` (4), and `test_doctrine_new.py` (9) to `with contextlib.chdir(...)`, dropping the now-unused `import os` in each file. Each A/B pair collapsed to one conversion per T037's rule.
- 2026-09-26T19:50:00Z – claude – T038: converted the `_invoke_upgrade` helper in `test_upgrade_command.py` (called by many tests, block-scoped) plus the 6 remaining whole-test `os.chdir` try/finally sites to `with contextlib.chdir(...)`; dropped the now-unused `import os`.
- 2026-09-26T20:00:00Z – claude – T039: reviewed the shard for class C/D sites and justified rows — none exist in S3 (all 26 original rows were `transitional-sweep`; no `process-bootstrap`/`subprocess-entry`/`leak-sentinel` rows to validate). No-op for this subtask.
- 2026-09-26T20:05:00Z – claude – T040: drained `S3.yaml` to `rows: []` (all 26 transitional-sweep rows converted); census gate (`test_no_manual_global_state_mutation.py`) green — 44 passed. After-junit identical to before (147 testcases, same 2 pre-existing failures). `-n 4 --dist loadfile` on owned files: identical result. `tests/architectural/test_home_pin*.py tests/architectural/test_no_sys_modules_patch_dict.py`: 154 passed. `ruff format`/`ruff check` clean on touched files. `mypy` on touched files: same 5 pre-existing errors confirmed present (line-shifted) on the base commit — none introduced by this sweep. Subtasks T036–T040 marked done.
- 2026-09-26T21:10:00Z – claude – **Review cycle 1 (reviewer-renata) REJECTED, HIGH.** `test_bytecode_doctor.py::fake_pkg`'s teardown call to `_purge_pkg_modules(monkeypatch)` leaked `skbcd_fake_pkg` into `sys.modules`: `monkeypatch.delitem` records the value present at call time and re-inserts it on undo, so the teardown-time `delitem` (called after the real import) made monkeypatch's own undo (which runs after this fixture tears down) restore the just-deleted module for the rest of the worker. Reviewer's probe: lane `LEAKED: ['skbcd_fake_pkg']` (1 failed) vs base b4608ff731 `LEAKED: []` (21 passed).
- 2026-09-26T21:15:00Z – claude – **Fix applied.** Changed `_purge_pkg_modules` to register `monkeypatch.setitem(sys.modules, name, None)` then `monkeypatch.delitem(sys.modules, name)` for `_PKG` (and any already-present submodule) once, before the import; dropped the teardown purge call entirely. This pins monkeypatch's undo history to always end in "delete" regardless of what the later plain `importlib.import_module` call writes into `sys.modules`, so a single purge before the import is sufficient and safe.
- 2026-09-26T21:20:00Z – claude – **Probe run** (same process, `test_bytecode_doctor.py` + a leak-probe test asserting no `skbcd_fake_pkg*` key in `sys.modules`, `-p no:cacheprovider -p no:randomly`): **21 passed**, zero leaked entries — matches base's expected result exactly, fixing the prior 1-failed leak. Re-ran full gate suite: census gate 44 passed; `test_home_pin*.py`/`test_no_sys_modules_patch_dict.py` 154 passed; owned files under `-n 4 --dist loadfile` 2 failed/145 passed (same 2 pre-existing golden-snapshot reds, unchanged); `ruff format`/`ruff check` clean. New commit `22e5eb3afb` (no history rewrite). Re-claimed WP08 via `spec-kitty agent action implement WP08 --profile python-pedro --allow-sparse-checkout` (repo-wide legacy sparse-checkout state on an unrelated worktree `startup-assess-cold-concurrency-01M3EQ9S-lane-a` blocks the bare command; override is unrelated to this WP's diff and only proceeds past that unrelated precondition check). Subtasks T036–T040 re-marked done; moving WP08 to for_review.
