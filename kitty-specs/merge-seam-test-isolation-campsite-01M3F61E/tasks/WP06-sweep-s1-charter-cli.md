---
work_package_id: WP06
title: 'Sweep S1: charter CLI tests'
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
base_commit: f0f88dfd0a861b46fc808b17b7706897e128b541
created_at: '2026-09-26T18:10:40.162349+00:00'
subtasks:
- T026
- T027
- T028
- T029
- T030
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
- tests/specify_cli/cli/commands/charter/test_recompile_preserves_mission_4908.py
- tests/specify_cli/cli/commands/charter/test_synthesize_cli_reconcile.py
- tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py
- tests/specify_cli/cli/commands/test_charter_generate_autotrack.py
- tests/specify_cli/cli/commands/test_charter_interview_org_prefill.py
- tests/specify_cli/cli/commands/test_charter_interview_promotion.py
- tests/specify_cli/cli/commands/test_end_of_interview_pending_pass.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Sweep S1: charter CLI tests

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

Issue **#5118** (FR-006, NFR-002, C-005). This work package converts every **manual global-state mutation** in shard **S1** (54 sites across 7 files) to a **scoped patching facility**, then drains shard S1's `transitional-sweep` rows from the census allowlist landed by WP01.

Done means:

- Every `transitional-sweep` row in `tests/architectural/global_state_allowlist/S1.yaml` is gone; only genuinely justified rows (`process-bootstrap` / `subprocess-entry` / `leak-sentinel`, each with a truthful `reason`) remain, and their counts are exact.
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
- **Ownership**: edit only the files in `owned_files`, plus exactly one recorded out-of-map edit: `tests/architectural/global_state_allowlist/S1.yaml` (drain step). Never edit other shards, the detector, the gate, or files owned by mission `01M3EW3Z`.

### Shard notes

- **Shard focus**: charter CLI command tests. `test_charter_generate_autotrack.py` carries 24 sites (12 A / 12 B: in-test `chdir(target)` + `chdir(original)` restore pairs); the `charter/` sub-dir files are `_invoke_*` / `_run_*` helpers of the `getcwd → chdir → try: invoke → finally chdir` shape (class B → `contextlib.chdir`). Convert a shared helper once; every call site inherits the fix.
- `tests/specify_cli/cli/commands/charter/` sub-tests share fixtures with the flat files — check each shared helper is converted exactly once and not duplicated.

### Owned files (7 files / 54 sites)

| File | Sites |
|---|---|
| `tests/specify_cli/cli/commands/charter/test_recompile_preserves_mission_4908.py` | 2 |
| `tests/specify_cli/cli/commands/charter/test_synthesize_cli_reconcile.py` | 2 |
| `tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py` | 8 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | 24 |
| `tests/specify_cli/cli/commands/test_charter_interview_org_prefill.py` | 6 |
| `tests/specify_cli/cli/commands/test_charter_interview_promotion.py` | 8 |
| `tests/specify_cli/cli/commands/test_end_of_interview_pending_pass.py` | 4 |

### Fix-class distribution

| Class | Sites |
|---|---|
| A-monkeypatch | 30 |
| B-contextlib.chdir | 24 |

### Site to-do list

Line numbers are navigation only (the allowlist is keyed on file + qualname + kind). Re-run the detector if lines drifted.

| File | Qualname | Kind | Form | Fix class | Line (nav only) |
|---|---|---|---|---|---|
| `tests/specify_cli/cli/commands/charter/test_recompile_preserves_mission_4908.py` | `_invoke_generate` | cwd | `call:os.chdir` | B-contextlib.chdir | 100 |
| `tests/specify_cli/cli/commands/charter/test_recompile_preserves_mission_4908.py` | `_invoke_generate` | cwd | `call:os.chdir` | B-contextlib.chdir | 103 |
| `tests/specify_cli/cli/commands/charter/test_synthesize_cli_reconcile.py` | `_invoke_synthesize` | cwd | `call:os.chdir` | B-contextlib.chdir | 279 |
| `tests/specify_cli/cli/commands/charter/test_synthesize_cli_reconcile.py` | `_invoke_synthesize` | cwd | `call:os.chdir` | B-contextlib.chdir | 297 |
| `tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py` | `_run_generate` | cwd | `call:os.chdir` | B-contextlib.chdir | 70 |
| `tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py` | `_run_generate` | cwd | `call:os.chdir` | B-contextlib.chdir | 73 |
| `tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py` | `_run_synthesize` | cwd | `call:os.chdir` | B-contextlib.chdir | 79 |
| `tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py` | `_run_synthesize` | cwd | `call:os.chdir` | B-contextlib.chdir | 82 |
| `tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py` | `test_generate_from_linked_worktree_fails_closed` | cwd | `call:os.chdir` | A-monkeypatch | 246 |
| `tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py` | `test_generate_from_linked_worktree_fails_closed` | cwd | `call:os.chdir` | B-contextlib.chdir | 249 |
| `tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py` | `test_synthesize_from_linked_worktree_fails_closed` | cwd | `call:os.chdir` | A-monkeypatch | 263 |
| `tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py` | `test_synthesize_from_linked_worktree_fails_closed` | cwd | `call:os.chdir` | B-contextlib.chdir | 266 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generate_then_bundle_validate_succeeds_in_fresh_git_repo` | cwd | `call:os.chdir` | A-monkeypatch | 145 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generate_then_bundle_validate_succeeds_in_fresh_git_repo` | cwd | `call:os.chdir` | A-monkeypatch | 165 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generate_in_non_git_dir_fails_fast` | cwd | `call:os.chdir` | A-monkeypatch | 182 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generate_in_non_git_dir_fails_fast` | cwd | `call:os.chdir` | B-contextlib.chdir | 188 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generate_stages_produced_files` | cwd | `call:os.chdir` | A-monkeypatch | 223 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generate_stages_produced_files` | cwd | `call:os.chdir` | B-contextlib.chdir | 233 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generate_from_interview_fails_when_answers_missing` | cwd | `call:os.chdir` | A-monkeypatch | 262 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generate_from_interview_fails_when_answers_missing` | cwd | `call:os.chdir` | B-contextlib.chdir | 268 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generate_from_interview_missing_answers_json_is_parseable` | cwd | `call:os.chdir` | A-monkeypatch | 290 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generate_from_interview_missing_answers_json_is_parseable` | cwd | `call:os.chdir` | B-contextlib.chdir | 296 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `_assert_generate_refuses_symlinked_charter_before_side_effects` | cwd | `call:os.chdir` | B-contextlib.chdir | 322 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `_assert_generate_refuses_symlinked_charter_before_side_effects` | cwd | `call:os.chdir` | B-contextlib.chdir | 328 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generate_fails_when_auto_stage_fails` | cwd | `call:os.chdir` | A-monkeypatch | 388 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generate_fails_when_auto_stage_fails` | cwd | `call:os.chdir` | B-contextlib.chdir | 394 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generate_does_not_disturb_unrelated_staged_changes` | cwd | `call:os.chdir` | A-monkeypatch | 422 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generate_does_not_disturb_unrelated_staged_changes` | cwd | `call:os.chdir` | B-contextlib.chdir | 432 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generic_safe_commit_commits_generated_charter_files` | cwd | `call:os.chdir` | A-monkeypatch | 452 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generic_safe_commit_commits_generated_charter_files` | cwd | `call:os.chdir` | B-contextlib.chdir | 474 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generic_safe_commit_targets_current_git_worktree` | cwd | `call:os.chdir` | A-monkeypatch | 516 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generic_safe_commit_targets_current_git_worktree` | cwd | `call:os.chdir` | B-contextlib.chdir | 529 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_interview_then_generate_consumes_answers` | cwd | `call:os.chdir` | A-monkeypatch | 587 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_interview_then_generate_consumes_answers` | cwd | `call:os.chdir` | B-contextlib.chdir | 605 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generate_from_interview_reports_malformed_answers_distinctly` | cwd | `call:os.chdir` | A-monkeypatch | 638 |
| `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` | `test_generate_from_interview_reports_malformed_answers_distinctly` | cwd | `call:os.chdir` | B-contextlib.chdir | 644 |
| `tests/specify_cli/cli/commands/test_charter_interview_org_prefill.py` | `test_interview_defaults_picks_up_org_charter_pre_fill` | cwd | `call:os.chdir` | A-monkeypatch | 101 |
| `tests/specify_cli/cli/commands/test_charter_interview_org_prefill.py` | `test_interview_defaults_picks_up_org_charter_pre_fill` | cwd | `call:os.chdir` | A-monkeypatch | 119 |
| `tests/specify_cli/cli/commands/test_charter_interview_org_prefill.py` | `test_interview_without_org_packs_has_no_pre_fill` | cwd | `call:os.chdir` | A-monkeypatch | 137 |
| `tests/specify_cli/cli/commands/test_charter_interview_org_prefill.py` | `test_interview_without_org_packs_has_no_pre_fill` | cwd | `call:os.chdir` | A-monkeypatch | 150 |
| `tests/specify_cli/cli/commands/test_charter_interview_org_prefill.py` | `test_interview_user_answer_survives_org_default` | cwd | `call:os.chdir` | A-monkeypatch | 180 |
| `tests/specify_cli/cli/commands/test_charter_interview_org_prefill.py` | `test_interview_user_answer_survives_org_default` | cwd | `call:os.chdir` | A-monkeypatch | 198 |
| `tests/specify_cli/cli/commands/test_charter_interview_promotion.py` | `test_interview_promotes_selections_preserving_builtins_on_absent_key` | cwd | `call:os.chdir` | A-monkeypatch | 75 |
| `tests/specify_cli/cli/commands/test_charter_interview_promotion.py` | `test_interview_promotes_selections_preserving_builtins_on_absent_key` | cwd | `call:os.chdir` | A-monkeypatch | 104 |
| `tests/specify_cli/cli/commands/test_charter_interview_promotion.py` | `test_interview_normalizes_canonical_form_directive_id` | cwd | `call:os.chdir` | A-monkeypatch | 119 |
| `tests/specify_cli/cli/commands/test_charter_interview_promotion.py` | `test_interview_normalizes_canonical_form_directive_id` | cwd | `call:os.chdir` | A-monkeypatch | 136 |
| `tests/specify_cli/cli/commands/test_charter_interview_promotion.py` | `test_interview_promotion_is_idempotent_across_runs` | cwd | `call:os.chdir` | A-monkeypatch | 148 |
| `tests/specify_cli/cli/commands/test_charter_interview_promotion.py` | `test_interview_promotion_is_idempotent_across_runs` | cwd | `call:os.chdir` | A-monkeypatch | 163 |
| `tests/specify_cli/cli/commands/test_charter_interview_promotion.py` | `test_interview_with_no_selections_leaves_config_untouched` | cwd | `call:os.chdir` | A-monkeypatch | 173 |
| `tests/specify_cli/cli/commands/test_charter_interview_promotion.py` | `test_interview_with_no_selections_leaves_config_untouched` | cwd | `call:os.chdir` | A-monkeypatch | 193 |
| `tests/specify_cli/cli/commands/test_end_of_interview_pending_pass.py` | `TestCharterEndOfInterviewPendingPass.test_pending_pass_not_called_when_widen_disabled` | cwd | `call:os.chdir` | A-monkeypatch | 828 |
| `tests/specify_cli/cli/commands/test_end_of_interview_pending_pass.py` | `TestCharterEndOfInterviewPendingPass.test_pending_pass_not_called_when_widen_disabled` | cwd | `call:os.chdir` | B-contextlib.chdir | 836 |
| `tests/specify_cli/cli/commands/test_end_of_interview_pending_pass.py` | `TestCharterEndOfInterviewPendingPass.test_pending_pass_called_when_widen_enabled_and_store_empty` | cwd | `call:os.chdir` | A-monkeypatch | 861 |
| `tests/specify_cli/cli/commands/test_end_of_interview_pending_pass.py` | `TestCharterEndOfInterviewPendingPass.test_pending_pass_called_when_widen_enabled_and_store_empty` | cwd | `call:os.chdir` | B-contextlib.chdir | 879 |

## Branch Strategy

- **Strategy**: lane-based execution worktree
- **Planning base branch**: `issue-5119-merge-seam-test-isolation`
- **Merge target branch**: `issue-5119-merge-seam-test-isolation`
- The execution worktree is allocated per computed lane from `lanes.json`. Prepare it only with `.venv/bin/spec-kitty agent action implement WP06 --agent claude` (never reconstruct the path). This WP depends on **WP01** (the census gate and shard files must exist).
- Use `.venv/bin/python` / `.venv/bin/spec-kitty` — the `spec-kitty` on PATH may resolve to a different checkout. Never a bare `uv run` (it re-syncs the hand-built `.venv`).

## Subtasks & Detailed Guidance

### Subtask T026 – Capture the behavior baseline

- **Purpose**: Freeze per-test-id outcomes of the owned files before any edit (NFR-002).
- **Steps**:
  1. In the lane worktree, before editing, run:
     ```bash
     .venv/bin/python -m pytest tests/specify_cli/cli/commands/charter/test_recompile_preserves_mission_4908.py tests/specify_cli/cli/commands/charter/test_synthesize_cli_reconcile.py tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py ... -p no:randomly -q --junitxml=$SCRATCH/WP06-before.xml
     ```
     (pass **all** owned files; `$SCRATCH` = a temp dir outside the repo).
  2. Record pass/skip/xfail counts in the Activity Log. Any pre-existing red: classify via the baseline-red gotcha (CLAUDE.md) — confirm it is red on the WP base too; never "fix" an unrelated known-P0 red.
  3. Run the gate and note the shard's current row set: `.venv/bin/python -m pytest tests/architectural/test_no_manual_global_state_mutation.py -q` (green at WP01 head).
- **Files**: none edited.
- **Parallel?**: no — first.

### Subtask T027 – Convert class A sites (`monkeypatch.*`)

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

### Subtask T028 – Convert class B sites (block-scoped)

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

### Subtask T029 – Class C / D sites and justified-row review

- **Purpose**: Handle scope-wide and import-time mutations, and validate every remaining justified row.
- **Recipes**:
  - **C** — module/session-scoped fixture: `with pytest.MonkeyPatch.context() as mp: mp.setenv(...); yield`.
  - **D1** — redundant import-time `sys.path.insert` of the repo root, `src`, a worktree `src`, or `Path.cwd()/"src"`: **delete** it. The repo root is on `sys.path` via pytest rootdir-prepend (`tests/__init__.py` exists) and `src` via `pythonpath = src` in `pytest.ini`. Re-run the file to prove every import still resolves. Do **not** change `pytest.ini` (cross-cutting; out of scope).
  - **D2** — `src/specify_cli` inserted so `import gitignore_manager` works bare: import `specify_cli.gitignore_manager` (a bare import gives the module a second identity).
  - **D3** — `scripts`/`scripts/<pkg>` inserted for bare sibling imports: rewrite to the canonical `scripts.<pkg>.<mod>` import where it resolves; delete the insert.
  - **E rows** in this shard (`process-bootstrap` / `subprocess-entry` / `leak-sentinel`): read each site. Keep the row only if the mutation genuinely must touch real process state (e.g. runs in a child process / subprocess entry, must precede any fixture, or is the leak detector itself). If it can be converted, convert it **and** remove the row. Make each kept row's `reason` accurate.
- **Parallel?**: per file.

### Subtask T030 – Drain shard S1 and verify

- **Purpose**: Prove the shard is clean and behavior is unchanged.
- **Steps**:
  1. Recorded out-of-map edit (add a one-line rationale to the Activity Log): in `tests/architectural/global_state_allowlist/S1.yaml` delete **all** `transitional-sweep` rows; adjust justified rows' `count` to the exact remaining site count (or delete rows you converted). Touch no other shard.
  2. Gate: `.venv/bin/python -m pytest tests/architectural/test_no_manual_global_state_mutation.py -q` — must pass.
  3. Behavior: rerun the owned files with `--junitxml=$SCRATCH/WP06-after.xml` and compare:
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
  9. Mark subtasks: `.venv/bin/spec-kitty agent tasks mark-status T026 T027 T028 T029 T030 --status done --mission merge-seam-test-isolation-campsite-01M3F61E`.

## Test Strategy

- No new test files: this WP changes how existing tests patch state, not what they assert.
- Evidence to record in the Activity Log: before/after junit comparison output ("identical"), the gate result, the xdist run result, and the final row list of `S1.yaml`.
- Commit granularity: one commit per class or per coherent file group (e.g. `test(isolation): contextlib.chdir in charter CLI invoke helpers (#5118)`); end each commit message with the repo's attribution lines.

## Risks & Mitigations

- **Order dependence surfaces**: a test that silently relied on state leaked by an earlier test may now fail. Fix the root cause in the dependent test (give it the state explicitly) — never reorder, retry, or skip. If it is a pre-existing red unrelated to this shard, classify it via the baseline-red gotcha and note it; do not chase it.
- **`monkeypatch.chdir` too late**: restores only at teardown — a helper called twice per test, or a test that asserts on cwd after a block, needs `contextlib.chdir`.
- **Thread-pool timeouts**: cwd is process-wide; a worker thread that outlives the block observes the restored cwd either way — preserve the original ordering of join/restore.
- **xdist**: `--dist loadfile` keeps a file on one worker; module-level mutations previously leaked to every later file on that worker — the fix removes that coupling, so expect previously-masked failures elsewhere only if some later file depended on the leak (fix that file's setup if it is in this shard; otherwise record it).
- **`sys.modules` re-import**: deleting a submodule without the parent attribute leaves `pkg.sub` pointing at the stale module.
- **Scope creep**: do not refactor tests beyond the mutation sites; boy-scout only inside owned files.

## Review Guidance

- Every row in the shard's site table is either converted or justified; `S1.yaml` has no `transitional-sweep` rows.
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
- 2026-09-26T20:30:00Z – claude – Converted all 54 shard-S1 cwd-mutation sites across the 7 owned files. B-contextlib.chdir applied to multi-invoke helpers (`_invoke_generate`, `_invoke_synthesize`, `_run_generate`, `_run_synthesize`, `_assert_generate_refuses_symlinked_charter_before_side_effects`). All remaining whole-test-scope A+B chdir/restore pairs (including two sites originally table-classified A-monkeypatch in `test_synthesize_freshgate_4785.py`'s worktree-refusal tests, and every generate/interview/promotion/widen test) converted to `monkeypatch.chdir` per the "one A+B pair = one conversion" rule — no reclassification disagreements found; the table's B-only helper sites and A+B whole-test sites both resolved as documented. No class C/D or justified-row sites existed in this shard (all 54 were `cwd`/`call:os.chdir`). Drained all 27 `transitional-sweep` rows from `tests/architectural/global_state_allowlist/S1.yaml` (out-of-map recorded edit); `rows: []` remains, `owns:` list untouched. Evidence: census gate `tests/architectural/test_no_manual_global_state_mutation.py` — 44 passed both before and after the drain. Before/after junit comparison over all 7 owned files: 80 testcases, "identical (80 testcases)" (79 passed, 1 skipped, both runs). `-n 4 --dist loadfile` run on owned files: 79 passed, 1 skipped (parallel-lane-shared machine, per orchestrator instruction, not `-n auto`). `ruff check` clean on all touched files; `ruff format --check` clean on the 3 non-ratchet files (the other 4 owned files are pre-existing entries in `pyproject.toml`'s `[tool.ruff.format].exclude` ratchet, confirmed present before this WP's edits — not introduced here) — one genuine format issue in `test_synthesize_freshgate_4785.py` (line wrap after adding a `monkeypatch` parameter) was fixed via `ruff format`. mypy: ran `python -m mypy <file>` per touched file; every reported error was verified pre-existing by running the WP06-base commit's version of the same file in place (identical error sets/counts, zero new errors). Neighbouring gates `tests/architectural/test_home_pin*.py tests/architectural/test_no_sys_modules_patch_dict.py`: 154 passed. No `src/**` touched; no new `# noqa`/`# type: ignore`. No order-dependence surfaces found. Tracer note (for orchestrator to file, not committed from lane): none of this shard's sites were `sys.modules` kind, so the sibling WP08 rejection heads-up (monkeypatch.delitem-as-teardown-purge leaking modules) does not apply to WP06's diff.
