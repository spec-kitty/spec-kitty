---
work_package_id: WP12
title: 'Sweep S7: integration + research tests'
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
base_commit: 67732d4edbefe24cb2d8068a59d593c9c867f5fd
created_at: '2026-09-26T18:12:37.102010+00:00'
subtasks:
- T056
- T057
- T058
- T059
- T060
phase: Phase 3 - Test-isolation sweep
history:
- at: '2026-09-26T16:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/integration/review/test_verdict_save_topologies.py
- tests/integration/sparse_checkout/test_implement_preflight_blocks.py
- tests/integration/sparse_checkout/test_merge_preflight_blocks.py
- tests/integration/sparse_checkout/test_merge_with_allow_override.py
- tests/integration/test_charter_synthesize_fresh.py
- tests/integration/test_deferral_enforcement_and_disclosure.py
- tests/integration/test_merge_lane_planning_data_loss.py
- tests/integration/test_placement_partition_golden_path.py
- tests/integration/test_review_durability_matrix.py
- tests/integration/test_specify_plan_commit_boundary.py
- tests/research/test_research_deliverables_unit.py
- tests/research/test_research_workflow_integration.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP12 – Sweep S7: integration + research tests

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (`packs/built-in/agent_profiles/python-pedro.agent.yaml`), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `.venv/bin/spec-kitty agent profile list` and select the best match for `task_type: implement` on `tests/`.

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

Issue **#5118** (FR-006, NFR-002, C-005). This work package converts every **manual global-state mutation** in shard **S7** (51 sites across 12 files) to a **scoped patching facility**, then drains shard S7's `transitional-sweep` rows from the census allowlist landed by WP01.

Done means:

- Every `transitional-sweep` row in `tests/architectural/global_state_allowlist/S7.yaml` is gone; only genuinely justified rows (`process-bootstrap` / `subprocess-entry` / `leak-sentinel`, each with a truthful `reason`) remain, and their counts are exact.
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
- **Ownership**: edit only the files in `owned_files`, plus exactly one recorded out-of-map edit: `tests/architectural/global_state_allowlist/S7.yaml` (drain step). Never edit other shards, the detector, the gate, or files owned by mission `01M3EW3Z`.

### Shard notes

- **Shard focus**: `tests/integration` (29) + `tests/research` (22). All 22 research sites are `sys.path.insert` calls **inside test bodies that are never undone** — they leak into every later test on the worker. Class D1: delete them (repo root + `src` are already on `sys.path` via rootdir-prepend and `pythonpath = src`) and verify the imports that followed still resolve.
- Integration E rows (`test_verdict_save_topologies.py` ×4, `test_review_durability_matrix.py` ×1) are classified subprocess/multiprocessing entries — confirm by reading; keep only if the mutation happens in a child process.
- **`sys.modules` sites in this shard** (check whether each relies on a fresh re-import; if so also restore the parent-package attribute): `tests/integration/test_deferral_enforcement_and_disclosure.py`.

### Owned files (12 files / 51 sites)

| File | Sites |
|---|---|
| `tests/integration/review/test_verdict_save_topologies.py` | 4 |
| `tests/integration/sparse_checkout/test_implement_preflight_blocks.py` | 2 |
| `tests/integration/sparse_checkout/test_merge_preflight_blocks.py` | 2 |
| `tests/integration/sparse_checkout/test_merge_with_allow_override.py` | 4 |
| `tests/integration/test_charter_synthesize_fresh.py` | 4 |
| `tests/integration/test_deferral_enforcement_and_disclosure.py` | 1 |
| `tests/integration/test_merge_lane_planning_data_loss.py` | 2 |
| `tests/integration/test_placement_partition_golden_path.py` | 3 |
| `tests/integration/test_review_durability_matrix.py` | 1 |
| `tests/integration/test_specify_plan_commit_boundary.py` | 6 |
| `tests/research/test_research_deliverables_unit.py` | 14 |
| `tests/research/test_research_workflow_integration.py` | 8 |

### Fix-class distribution

| Class | Sites |
|---|---|
| A-monkeypatch | 3 |
| B-contextlib.chdir | 14 |
| B-mock.patch.dict/object(block) | 9 |
| D1-delete-redundant-insert | 22 |
| E2-subprocess-entry | 3 |

### Site to-do list

Line numbers are navigation only (the allowlist is keyed on file + qualname + kind). Re-run the detector if lines drifted.

| File | Qualname | Kind | Form | Fix class | Line (nav only) |
|---|---|---|---|---|---|
| `tests/integration/review/test_verdict_save_topologies.py` | `_invoke_verdict` | cwd | `call:os.chdir` | B-contextlib.chdir | 289 |
| `tests/integration/review/test_verdict_save_topologies.py` | `_invoke_verdict` | cwd | `call:os.chdir` | B-contextlib.chdir | 292 |
| `tests/integration/review/test_verdict_save_topologies.py` | `_event_mutant_worker` | cwd | `call:os.chdir` | E2-subprocess-entry | 829 |
| `tests/integration/review/test_verdict_save_topologies.py` | `_event_mutant_worker` | cwd | `call:os.chdir` | E2-subprocess-entry | 852 |
| `tests/integration/sparse_checkout/test_implement_preflight_blocks.py` | `_invoke_implement` | cwd | `call:os.chdir` | B-contextlib.chdir | 68 |
| `tests/integration/sparse_checkout/test_implement_preflight_blocks.py` | `_invoke_implement` | cwd | `call:os.chdir` | B-contextlib.chdir | 71 |
| `tests/integration/sparse_checkout/test_merge_preflight_blocks.py` | `TestMergePreflightBlocks._invoke` | cwd | `call:os.chdir` | B-contextlib.chdir | 113 |
| `tests/integration/sparse_checkout/test_merge_preflight_blocks.py` | `TestMergePreflightBlocks._invoke` | cwd | `call:os.chdir` | B-contextlib.chdir | 118 |
| `tests/integration/sparse_checkout/test_merge_with_allow_override.py` | `TestMergeWithAllowOverride.test_override_flag_is_wired_from_cli_to_preflight` | cwd | `call:os.chdir` | A-monkeypatch | 159 |
| `tests/integration/sparse_checkout/test_merge_with_allow_override.py` | `TestMergeWithAllowOverride.test_override_flag_is_wired_from_cli_to_preflight` | cwd | `call:os.chdir` | B-contextlib.chdir | 166 |
| `tests/integration/sparse_checkout/test_merge_with_allow_override.py` | `TestMergeWithAllowOverride.test_override_audit_log_carries_resolved_actor_not_unknown` | cwd | `call:os.chdir` | A-monkeypatch | 239 |
| `tests/integration/sparse_checkout/test_merge_with_allow_override.py` | `TestMergeWithAllowOverride.test_override_audit_log_carries_resolved_actor_not_unknown` | cwd | `call:os.chdir` | B-contextlib.chdir | 246 |
| `tests/integration/test_charter_synthesize_fresh.py` | `_run_generate` | cwd | `call:os.chdir` | B-contextlib.chdir | 73 |
| `tests/integration/test_charter_synthesize_fresh.py` | `_run_generate` | cwd | `call:os.chdir` | B-contextlib.chdir | 79 |
| `tests/integration/test_charter_synthesize_fresh.py` | `_run_synthesize` | cwd | `call:os.chdir` | B-contextlib.chdir | 89 |
| `tests/integration/test_charter_synthesize_fresh.py` | `_run_synthesize` | cwd | `call:os.chdir` | B-contextlib.chdir | 95 |
| `tests/integration/test_deferral_enforcement_and_disclosure.py` | `_load_script_module` | sys.modules | `subscript-store` | A-monkeypatch | 60 |
| `tests/integration/test_merge_lane_planning_data_loss.py` | `_invoke_merge_cli` | cwd | `call:os.chdir` | B-contextlib.chdir | 1450 |
| `tests/integration/test_merge_lane_planning_data_loss.py` | `_invoke_merge_cli` | cwd | `call:os.chdir` | B-contextlib.chdir | 1453 |
| `tests/integration/test_placement_partition_golden_path.py` | `_run_setup_plan` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 250 |
| `tests/integration/test_placement_partition_golden_path.py` | `_run_setup_plan` | os.environ | `call:.pop` | B-mock.patch.dict/object(block) | 267 |
| `tests/integration/test_placement_partition_golden_path.py` | `_run_setup_plan` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 269 |
| `tests/integration/test_review_durability_matrix.py` | `_sc004_worker` | cwd | `call:os.chdir` | E2-subprocess-entry | 1796 |
| `tests/integration/test_specify_plan_commit_boundary.py` | `_run_setup_plan` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 277 |
| `tests/integration/test_specify_plan_commit_boundary.py` | `_run_setup_plan` | os.environ | `call:.pop` | B-mock.patch.dict/object(block) | 302 |
| `tests/integration/test_specify_plan_commit_boundary.py` | `_run_setup_plan` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 304 |
| `tests/integration/test_specify_plan_commit_boundary.py` | `_run_setup_plan_real_resolver` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 432 |
| `tests/integration/test_specify_plan_commit_boundary.py` | `_run_setup_plan_real_resolver` | os.environ | `call:.pop` | B-mock.patch.dict/object(block) | 453 |
| `tests/integration/test_specify_plan_commit_boundary.py` | `_run_setup_plan_real_resolver` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 455 |
| `tests/research/test_research_deliverables_unit.py` | `TestGetDeliverablesPath.test_returns_path_from_meta_json` | sys.path | `call:.insert` | D1-delete-redundant-insert | 20 |
| `tests/research/test_research_deliverables_unit.py` | `TestGetDeliverablesPath.test_returns_default_for_research_mission_without_path` | sys.path | `call:.insert` | D1-delete-redundant-insert | 38 |
| `tests/research/test_research_deliverables_unit.py` | `TestGetDeliverablesPath.test_returns_none_for_software_dev_mission` | sys.path | `call:.insert` | D1-delete-redundant-insert | 56 |
| `tests/research/test_research_deliverables_unit.py` | `TestGetDeliverablesPath.test_uses_mission_slug_for_default_when_provided` | sys.path | `call:.insert` | D1-delete-redundant-insert | 73 |
| `tests/research/test_research_deliverables_unit.py` | `TestGetDeliverablesPath.test_handles_missing_meta_json` | sys.path | `call:.insert` | D1-delete-redundant-insert | 87 |
| `tests/research/test_research_deliverables_unit.py` | `TestGetDeliverablesPath.test_handles_invalid_json` | sys.path | `call:.insert` | D1-delete-redundant-insert | 101 |
| `tests/research/test_research_deliverables_unit.py` | `TestValidateDeliverablesPath.test_rejects_kitty_specs_prefix` | sys.path | `call:.insert` | D1-delete-redundant-insert | 120 |
| `tests/research/test_research_deliverables_unit.py` | `TestValidateDeliverablesPath.test_rejects_just_research_at_root` | sys.path | `call:.insert` | D1-delete-redundant-insert | 131 |
| `tests/research/test_research_deliverables_unit.py` | `TestValidateDeliverablesPath.test_rejects_absolute_paths` | sys.path | `call:.insert` | D1-delete-redundant-insert | 146 |
| `tests/research/test_research_deliverables_unit.py` | `TestValidateDeliverablesPath.test_accepts_valid_docs_research_path` | sys.path | `call:.insert` | D1-delete-redundant-insert | 157 |
| `tests/research/test_research_deliverables_unit.py` | `TestValidateDeliverablesPath.test_accepts_valid_research_outputs_path` | sys.path | `call:.insert` | D1-delete-redundant-insert | 168 |
| `tests/research/test_research_deliverables_unit.py` | `TestValidateDeliverablesPath.test_accepts_custom_valid_path` | sys.path | `call:.insert` | D1-delete-redundant-insert | 179 |
| `tests/research/test_research_deliverables_unit.py` | `TestMetaJsonDeliverablesPath.test_meta_json_stores_deliverables_path` | sys.path | `call:.insert` | D1-delete-redundant-insert | 194 |
| `tests/research/test_research_deliverables_unit.py` | `TestMetaJsonDeliverablesPath.test_default_deliverables_path_when_missing` | sys.path | `call:.insert` | D1-delete-redundant-insert | 220 |
| `tests/research/test_research_workflow_integration.py` | `test_citation_validation_with_valid_data` | sys.path | `call:.insert` | D1-delete-redundant-insert | 58 |
| `tests/research/test_research_workflow_integration.py` | `test_citation_validation_catches_errors` | sys.path | `call:.insert` | D1-delete-redundant-insert | 75 |
| `tests/research/test_research_workflow_integration.py` | `test_source_register_validation` | sys.path | `call:.insert` | D1-delete-redundant-insert | 92 |
| `tests/research/test_research_workflow_integration.py` | `test_full_research_workflow_via_cli` | sys.path | `call:.insert` | D1-delete-redundant-insert | 164 |
| `tests/research/test_research_workflow_integration.py` | `test_deliverables_path_in_meta_json` | sys.path | `call:.insert` | D1-delete-redundant-insert | 178 |
| `tests/research/test_research_workflow_integration.py` | `test_deliverables_path_not_in_kitty_specs` | sys.path | `call:.insert` | D1-delete-redundant-insert | 202 |
| `tests/research/test_research_workflow_integration.py` | `test_research_deliverables_separate_from_planning` | sys.path | `call:.insert` | D1-delete-redundant-insert | 220 |
| `tests/research/test_research_workflow_integration.py` | `test_default_deliverables_path_generation` | sys.path | `call:.insert` | D1-delete-redundant-insert | 257 |

## Branch Strategy

- **Strategy**: lane-based execution worktree
- **Planning base branch**: `issue-5119-merge-seam-test-isolation`
- **Merge target branch**: `issue-5119-merge-seam-test-isolation`
- The execution worktree is allocated per computed lane from `lanes.json`. Prepare it only with `.venv/bin/spec-kitty agent action implement WP12 --agent claude` (never reconstruct the path). This WP depends on **WP01** (the census gate and shard files must exist).
- Use `.venv/bin/python` / `.venv/bin/spec-kitty` — the `spec-kitty` on PATH may resolve to a different checkout. Never a bare `uv run` (it re-syncs the hand-built `.venv`).

## Subtasks & Detailed Guidance

### Subtask T056 – Capture the behavior baseline

- **Purpose**: Freeze per-test-id outcomes of the owned files before any edit (NFR-002).
- **Steps**:
  1. In the lane worktree, before editing, run:
     ```bash
     .venv/bin/python -m pytest tests/integration/review/test_verdict_save_topologies.py tests/integration/sparse_checkout/test_implement_preflight_blocks.py tests/integration/sparse_checkout/test_merge_preflight_blocks.py ... -p no:randomly -q --junitxml=$SCRATCH/WP12-before.xml
     ```
     (pass **all** owned files; `$SCRATCH` = a temp dir outside the repo).
  2. Record pass/skip/xfail counts in the Activity Log. Any pre-existing red: classify via the baseline-red gotcha (CLAUDE.md) — confirm it is red on the WP base too; never "fix" an unrelated known-P0 red.
  3. Run the gate and note the shard's current row set: `.venv/bin/python -m pytest tests/architectural/test_no_manual_global_state_mutation.py -q` (green at WP01 head).
- **Files**: none edited.
- **Parallel?**: no — first.

### Subtask T057 – Convert class A sites (`monkeypatch.*`)

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

### Subtask T058 – Convert class B sites (block-scoped)

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

### Subtask T059 – Class C / D sites and justified-row review

- **Purpose**: Handle scope-wide and import-time mutations, and validate every remaining justified row.
- **Recipes**:
  - **C** — module/session-scoped fixture: `with pytest.MonkeyPatch.context() as mp: mp.setenv(...); yield`.
  - **D1** — redundant import-time `sys.path.insert` of the repo root, `src`, a worktree `src`, or `Path.cwd()/"src"`: **delete** it. The repo root is on `sys.path` via pytest rootdir-prepend (`tests/__init__.py` exists) and `src` via `pythonpath = src` in `pytest.ini`. Re-run the file to prove every import still resolves. Do **not** change `pytest.ini` (cross-cutting; out of scope).
  - **D2** — `src/specify_cli` inserted so `import gitignore_manager` works bare: import `specify_cli.gitignore_manager` (a bare import gives the module a second identity).
  - **D3** — `scripts`/`scripts/<pkg>` inserted for bare sibling imports: rewrite to the canonical `scripts.<pkg>.<mod>` import where it resolves; delete the insert.
  - **E rows** in this shard (`process-bootstrap` / `subprocess-entry` / `leak-sentinel`): read each site. Keep the row only if the mutation genuinely must touch real process state (e.g. runs in a child process / subprocess entry, must precede any fixture, or is the leak detector itself). If it can be converted, convert it **and** remove the row. Make each kept row's `reason` accurate.
- **Parallel?**: per file.

### Subtask T060 – Drain shard S7 and verify

- **Purpose**: Prove the shard is clean and behavior is unchanged.
- **Steps**:
  1. Recorded out-of-map edit (add a one-line rationale to the Activity Log): in `tests/architectural/global_state_allowlist/S7.yaml` delete **all** `transitional-sweep` rows; adjust justified rows' `count` to the exact remaining site count (or delete rows you converted). Touch no other shard.
  2. Gate: `.venv/bin/python -m pytest tests/architectural/test_no_manual_global_state_mutation.py -q` — must pass.
  3. Behavior: rerun the owned files with `--junitxml=$SCRATCH/WP12-after.xml` and compare:
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
  9. Mark subtasks: `.venv/bin/spec-kitty agent tasks mark-status T056 T057 T058 T059 T060 --status done --mission merge-seam-test-isolation-campsite-01M3F61E`.

## Test Strategy

- No new test files: this WP changes how existing tests patch state, not what they assert.
- Evidence to record in the Activity Log: before/after junit comparison output ("identical"), the gate result, the xdist run result, and the final row list of `S7.yaml`.
- Commit granularity: one commit per class or per coherent file group (e.g. `test(isolation): contextlib.chdir in charter CLI invoke helpers (#5118)`); end each commit message with the repo's attribution lines.

## Risks & Mitigations

- **Order dependence surfaces**: a test that silently relied on state leaked by an earlier test may now fail. Fix the root cause in the dependent test (give it the state explicitly) — never reorder, retry, or skip. If it is a pre-existing red unrelated to this shard, classify it via the baseline-red gotcha and note it; do not chase it.
- **`monkeypatch.chdir` too late**: restores only at teardown — a helper called twice per test, or a test that asserts on cwd after a block, needs `contextlib.chdir`.
- **Thread-pool timeouts**: cwd is process-wide; a worker thread that outlives the block observes the restored cwd either way — preserve the original ordering of join/restore.
- **xdist**: `--dist loadfile` keeps a file on one worker; module-level mutations previously leaked to every later file on that worker — the fix removes that coupling, so expect previously-masked failures elsewhere only if some later file depended on the leak (fix that file's setup if it is in this shard; otherwise record it).
- **`sys.modules` re-import**: deleting a submodule without the parent attribute leaves `pkg.sub` pointing at the stale module.
- **Scope creep**: do not refactor tests beyond the mutation sites; boy-scout only inside owned files.

## Review Guidance

- Every row in the shard's site table is either converted or justified; `S7.yaml` has no `transitional-sweep` rows.
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
- 2026-09-26T21:15:00Z – claude – T056-T060 complete. Baseline junit (before-edit, 149 testcases, 10 pre-existing failures in test_merge_lane_planning_data_loss.py TestRetentionConstraintSurvivesCleanup/TestPlanningArtifactReachesTarget/TestMergeIncludesPlanningLane and test_review_durability_matrix.py test_arbiter_override_* — confirmed unmaterialized-coordination-worktree/#... unrelated to this shard, unchanged by baseline-red gotcha) saved to a scratch junit file. Converted all 51 sites across the 12 owned files: 22 D1 sys.path.insert deletes (test_research_deliverables_unit.py ×14, test_research_workflow_integration.py ×8 — sys unused afterward, import dropped too); 14 B-contextlib.chdir conversions (test_verdict_save_topologies.py::_invoke_verdict, test_implement_preflight_blocks.py::_invoke_implement, test_merge_preflight_blocks.py::TestMergePreflightBlocks._invoke [SystemExit-catching except clause preserved, chdir moved inside the with], test_merge_with_allow_override.py's two A+B-paired sites [both rows disappear as one conversion], test_charter_synthesize_fresh.py::_run_generate/_run_synthesize, test_merge_lane_planning_data_loss.py::_invoke_merge_cli [reused the module's existing `import contextlib` instead of adding a redundant local `os`]); 9 B-mock.patch.dict(os.environ) conversions (test_placement_partition_golden_path.py + test_specify_plan_commit_boundary.py's two `_run_setup_plan*` variants — folded the manual get/pop/[]= save-restore into the existing `with (patch.object(...), ...)` tuple); 1 A-monkeypatch.context() conversion (test_deferral_enforcement_and_disclosure.py::_load_script_module — module-level, not per-test, so pytest.MonkeyPatch.context() was used directly rather than the function-scoped monkeypatch fixture; avoided the delitem-as-teardown-purge pitfall by using setitem inside the context and letting __exit__ restore the prior absent state; proved no leak with a probe re-import in the same process). 3 E2-subprocess-entry rows (test_verdict_save_topologies.py::_event_mutant_worker ×2, test_review_durability_matrix.py::_sc004_worker ×1) read and confirmed as genuine child-process/multiprocessing entries — left untouched, kept justified in S7.yaml. Drained S7.yaml: all 34 transitional-sweep rows removed; 2 justified subprocess-entry rows remain with exact counts. Census gate green (44 passed). Home-pin/sys.modules-patch.dict gates green (154 passed), unaffected by this sweep. After-junit: 149 testcases, identical to before (same 10 pre-existing failures, 0 deleted/newly-skipped). Same result under `-n 4 --dist loadfile` (139 passed / 10 failed). ruff check clean on all touched files. mypy: 3 files (test_verdict_save_topologies.py, test_deferral_enforcement_and_disclosure.py, test_placement_partition_golden_path.py, test_specify_plan_commit_boundary.py) clean; test_implement_preflight_blocks.py/test_merge_preflight_blocks.py/test_merge_with_allow_override.py/test_charter_synthesize_fresh.py/test_merge_lane_planning_data_loss.py carry pre-existing mypy errors verified byte-identical (same messages, only line numbers shifted by my deletions) against the pre-edit content — zero new errors introduced. ruff format --check: 7 of the 9 checked files were already format-debt-red pre-edit (confirmed against pre-edit content, same file set) and are not in pyproject.toml's `[tool.ruff.format].exclude` ratchet; left unreformatted per locality-of-change (a full-file reformat would touch far more than the mutation sites) — flagging as a pre-existing gap for the ratchet owner, not fixed here. Skipped `make test-fast` per the orchestrator brief's explicit override for this shared-lane run (it invokes `-n auto`, which the brief forbids on this machine); it also failed in this lane on an unrelated stale-venv issue (fresh `uv run --frozen` venv missing the `pytestarch` dev dependency), a category-4 false red per CLAUDE.md, not attributable to this diff.
