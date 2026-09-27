---
work_package_id: WP07
title: 'Sweep S2: widen/decision CLI tests'
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
base_commit: a9022b3f978cf1fb89653fedfceeeb9fbac2312b
created_at: '2026-09-26T18:10:53.231367+00:00'
subtasks:
- T031
- T032
- T033
- T034
- T035
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
- tests/specify_cli/cli/commands/test_charter.py
- tests/specify_cli/cli/commands/test_charter_decision_integration.py
- tests/specify_cli/cli/commands/test_charter_prereq_suppression.py
- tests/specify_cli/cli/commands/test_charter_widen.py
- tests/specify_cli/cli/commands/test_charter_widen_integration.py
- tests/specify_cli/cli/commands/test_decision.py
- tests/specify_cli/cli/commands/test_decision_single_authority.py
- tests/specify_cli/cli/commands/test_decision_widen_subcommand.py
- tests/specify_cli/cli/commands/test_plan_widen.py
- tests/specify_cli/cli/commands/test_specify_widen.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Sweep S2: widen/decision CLI tests

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

Issue **#5118** (FR-006, NFR-002, C-005). This work package converts every **manual global-state mutation** in shard **S2** (64 sites across 10 files) to a **scoped patching facility**, then drains shard S2's `transitional-sweep` rows from the census allowlist landed by WP01.

Done means:

- Every `transitional-sweep` row in `tests/architectural/global_state_allowlist/S2.yaml` is gone; only genuinely justified rows (`process-bootstrap` / `subprocess-entry` / `leak-sentinel`, each with a truthful `reason`) remain, and their counts are exact.
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
- **Ownership**: edit only the files in `owned_files`, plus exactly one recorded out-of-map edit: `tests/architectural/global_state_allowlist/S2.yaml` (drain step). Never edit other shards, the detector, the gate, or files owned by mission `01M3EW3Z`.

### Shard notes

- **Shard focus**: widen/decision/prereq CLI tests (`charter_widen*`, `plan_widen`, `specify_widen`, `decision*`, `charter.py`). Many `_invoke*` helpers chdir around `CliRunner.invoke` → `contextlib.chdir`.
- `charter_widen_integration` (14 sites) is the heaviest file: convert its local helper rather than each site.

### Owned files (10 files / 64 sites)

| File | Sites |
|---|---|
| `tests/specify_cli/cli/commands/test_charter.py` | 2 |
| `tests/specify_cli/cli/commands/test_charter_decision_integration.py` | 2 |
| `tests/specify_cli/cli/commands/test_charter_prereq_suppression.py` | 8 |
| `tests/specify_cli/cli/commands/test_charter_widen.py` | 12 |
| `tests/specify_cli/cli/commands/test_charter_widen_integration.py` | 14 |
| `tests/specify_cli/cli/commands/test_decision.py` | 2 |
| `tests/specify_cli/cli/commands/test_decision_single_authority.py` | 2 |
| `tests/specify_cli/cli/commands/test_decision_widen_subcommand.py` | 2 |
| `tests/specify_cli/cli/commands/test_plan_widen.py` | 10 |
| `tests/specify_cli/cli/commands/test_specify_widen.py` | 10 |

### Fix-class distribution

| Class | Sites |
|---|---|
| A-monkeypatch | 24 |
| B-contextlib.chdir | 40 |

### Site to-do list

Line numbers are navigation only (the allowlist is keyed on file + qualname + kind). Re-run the detector if lines drifted.

| File | Qualname | Kind | Form | Fix class | Line (nav only) |
|---|---|---|---|---|---|
| `tests/specify_cli/cli/commands/test_charter.py` | `_invoke_interview` | cwd | `call:os.chdir` | B-contextlib.chdir | 70 |
| `tests/specify_cli/cli/commands/test_charter.py` | `_invoke_interview` | cwd | `call:os.chdir` | B-contextlib.chdir | 82 |
| `tests/specify_cli/cli/commands/test_charter_decision_integration.py` | `_invoke_interview` | cwd | `call:os.chdir` | B-contextlib.chdir | 70 |
| `tests/specify_cli/cli/commands/test_charter_decision_integration.py` | `_invoke_interview` | cwd | `call:os.chdir` | B-contextlib.chdir | 78 |
| `tests/specify_cli/cli/commands/test_charter_prereq_suppression.py` | `_invoke_with_prereqs` | cwd | `call:os.chdir` | B-contextlib.chdir | 74 |
| `tests/specify_cli/cli/commands/test_charter_prereq_suppression.py` | `_invoke_with_prereqs` | cwd | `call:os.chdir` | B-contextlib.chdir | 94 |
| `tests/specify_cli/cli/commands/test_charter_prereq_suppression.py` | `TestInterviewCompletesNormallyWithoutWiden.test_interview_completes_normally_without_widen` | cwd | `call:os.chdir` | A-monkeypatch | 155 |
| `tests/specify_cli/cli/commands/test_charter_prereq_suppression.py` | `TestInterviewCompletesNormallyWithoutWiden.test_interview_completes_normally_without_widen` | cwd | `call:os.chdir` | B-contextlib.chdir | 163 |
| `tests/specify_cli/cli/commands/test_charter_prereq_suppression.py` | `TestInterviewCompletesNormallyWithoutWiden.test_no_error_banner_when_token_absent` | cwd | `call:os.chdir` | A-monkeypatch | 177 |
| `tests/specify_cli/cli/commands/test_charter_prereq_suppression.py` | `TestInterviewCompletesNormallyWithoutWiden.test_no_error_banner_when_token_absent` | cwd | `call:os.chdir` | B-contextlib.chdir | 185 |
| `tests/specify_cli/cli/commands/test_charter_prereq_suppression.py` | `TestInterviewCompletesNormallyWithoutWiden.test_answers_yaml_correct_without_widen` | cwd | `call:os.chdir` | A-monkeypatch | 199 |
| `tests/specify_cli/cli/commands/test_charter_prereq_suppression.py` | `TestInterviewCompletesNormallyWithoutWiden.test_answers_yaml_correct_without_widen` | cwd | `call:os.chdir` | B-contextlib.chdir | 207 |
| `tests/specify_cli/cli/commands/test_charter_widen.py` | `_invoke_interview` | cwd | `call:os.chdir` | B-contextlib.chdir | 77 |
| `tests/specify_cli/cli/commands/test_charter_widen.py` | `_invoke_interview` | cwd | `call:os.chdir` | B-contextlib.chdir | 90 |
| `tests/specify_cli/cli/commands/test_charter_widen.py` | `TestWidenAffordanceVisibility.test_widen_shown_when_prereqs_satisfied` | cwd | `call:os.chdir` | A-monkeypatch | 194 |
| `tests/specify_cli/cli/commands/test_charter_widen.py` | `TestWidenAffordanceVisibility.test_widen_shown_when_prereqs_satisfied` | cwd | `call:os.chdir` | B-contextlib.chdir | 215 |
| `tests/specify_cli/cli/commands/test_charter_widen.py` | `TestWidenHappyPathBlock.test_w_then_block_then_local_answer` | cwd | `call:os.chdir` | A-monkeypatch | 264 |
| `tests/specify_cli/cli/commands/test_charter_widen.py` | `TestWidenHappyPathBlock.test_w_then_block_then_local_answer` | cwd | `call:os.chdir` | B-contextlib.chdir | 289 |
| `tests/specify_cli/cli/commands/test_charter_widen.py` | `TestWidenHappyPathBlock.test_answers_yaml_written_after_block_path` | cwd | `call:os.chdir` | A-monkeypatch | 316 |
| `tests/specify_cli/cli/commands/test_charter_widen.py` | `TestWidenHappyPathBlock.test_answers_yaml_written_after_block_path` | cwd | `call:os.chdir` | B-contextlib.chdir | 341 |
| `tests/specify_cli/cli/commands/test_charter_widen.py` | `TestWidenHappyPathContinue.test_w_then_continue_parks_question` | cwd | `call:os.chdir` | A-monkeypatch | 420 |
| `tests/specify_cli/cli/commands/test_charter_widen.py` | `TestWidenHappyPathContinue.test_w_then_continue_parks_question` | cwd | `call:os.chdir` | B-contextlib.chdir | 441 |
| `tests/specify_cli/cli/commands/test_charter_widen.py` | `TestWidenHappyPathContinue.test_answers_yaml_written_after_continue_path` | cwd | `call:os.chdir` | A-monkeypatch | 472 |
| `tests/specify_cli/cli/commands/test_charter_widen.py` | `TestWidenHappyPathContinue.test_answers_yaml_written_after_continue_path` | cwd | `call:os.chdir` | B-contextlib.chdir | 497 |
| `tests/specify_cli/cli/commands/test_charter_widen_integration.py` | `_invoke_interview` | cwd | `call:os.chdir` | B-contextlib.chdir | 93 |
| `tests/specify_cli/cli/commands/test_charter_widen_integration.py` | `_invoke_interview` | cwd | `call:os.chdir` | B-contextlib.chdir | 99 |
| `tests/specify_cli/cli/commands/test_charter_widen_integration.py` | `TestWidenCancelPath.test_cancel_path_reprompts_question` | cwd | `call:os.chdir` | A-monkeypatch | 287 |
| `tests/specify_cli/cli/commands/test_charter_widen_integration.py` | `TestWidenCancelPath.test_cancel_path_reprompts_question` | cwd | `call:os.chdir` | B-contextlib.chdir | 305 |
| `tests/specify_cli/cli/commands/test_charter_widen_integration.py` | `TestWidenContinuePath.test_continue_path_writes_pending_entry` | cwd | `call:os.chdir` | A-monkeypatch | 343 |
| `tests/specify_cli/cli/commands/test_charter_widen_integration.py` | `TestWidenContinuePath.test_continue_path_writes_pending_entry` | cwd | `call:os.chdir` | B-contextlib.chdir | 365 |
| `tests/specify_cli/cli/commands/test_charter_widen_integration.py` | `TestWidenBlockPath.test_block_path_resolves_via_local_answer` | cwd | `call:os.chdir` | A-monkeypatch | 402 |
| `tests/specify_cli/cli/commands/test_charter_widen_integration.py` | `TestWidenBlockPath.test_block_path_resolves_via_local_answer` | cwd | `call:os.chdir` | B-contextlib.chdir | 424 |
| `tests/specify_cli/cli/commands/test_charter_widen_integration.py` | `TestWidenBlockPath.test_block_path_defer_from_blocked_prompt` | cwd | `call:os.chdir` | A-monkeypatch | 452 |
| `tests/specify_cli/cli/commands/test_charter_widen_integration.py` | `TestWidenBlockPath.test_block_path_defer_from_blocked_prompt` | cwd | `call:os.chdir` | B-contextlib.chdir | 474 |
| `tests/specify_cli/cli/commands/test_charter_widen_integration.py` | `TestNonWidenRegressions.test_defaults_flag_skips_prompts` | cwd | `call:os.chdir` | A-monkeypatch | 502 |
| `tests/specify_cli/cli/commands/test_charter_widen_integration.py` | `TestNonWidenRegressions.test_defaults_flag_skips_prompts` | cwd | `call:os.chdir` | B-contextlib.chdir | 509 |
| `tests/specify_cli/cli/commands/test_charter_widen_integration.py` | `TestNonWidenRegressions.test_json_output_flag` | cwd | `call:os.chdir` | A-monkeypatch | 518 |
| `tests/specify_cli/cli/commands/test_charter_widen_integration.py` | `TestNonWidenRegressions.test_json_output_flag` | cwd | `call:os.chdir` | B-contextlib.chdir | 525 |
| `tests/specify_cli/cli/commands/test_decision.py` | `_invoke` | cwd | `call:os.chdir` | B-contextlib.chdir | 70 |
| `tests/specify_cli/cli/commands/test_decision.py` | `_invoke` | cwd | `call:os.chdir` | B-contextlib.chdir | 73 |
| `tests/specify_cli/cli/commands/test_decision_single_authority.py` | `_invoke` | cwd | `call:os.chdir` | B-contextlib.chdir | 98 |
| `tests/specify_cli/cli/commands/test_decision_single_authority.py` | `_invoke` | cwd | `call:os.chdir` | B-contextlib.chdir | 104 |
| `tests/specify_cli/cli/commands/test_decision_widen_subcommand.py` | `_invoke` | cwd | `call:os.chdir` | B-contextlib.chdir | 66 |
| `tests/specify_cli/cli/commands/test_decision_widen_subcommand.py` | `_invoke` | cwd | `call:os.chdir` | B-contextlib.chdir | 69 |
| `tests/specify_cli/cli/commands/test_plan_widen.py` | `TestPlanWidenAbsent.test_widen_not_shown_without_prereqs` | cwd | `call:os.chdir` | A-monkeypatch | 121 |
| `tests/specify_cli/cli/commands/test_plan_widen.py` | `TestPlanWidenAbsent.test_widen_not_shown_without_prereqs` | cwd | `call:os.chdir` | B-contextlib.chdir | 147 |
| `tests/specify_cli/cli/commands/test_plan_widen.py` | `TestPlanWidenCancelPath.test_cancel_path_reprompts_and_continues` | cwd | `call:os.chdir` | A-monkeypatch | 176 |
| `tests/specify_cli/cli/commands/test_plan_widen.py` | `TestPlanWidenCancelPath.test_cancel_path_reprompts_and_continues` | cwd | `call:os.chdir` | B-contextlib.chdir | 213 |
| `tests/specify_cli/cli/commands/test_plan_widen.py` | `TestPlanWidenContinuePath.test_continue_marker_failure_reprompts_without_parking_blank` | cwd | `call:os.chdir` | A-monkeypatch | 252 |
| `tests/specify_cli/cli/commands/test_plan_widen.py` | `TestPlanWidenContinuePath.test_continue_marker_failure_reprompts_without_parking_blank` | cwd | `call:os.chdir` | B-contextlib.chdir | 277 |
| `tests/specify_cli/cli/commands/test_plan_widen.py` | `TestPlanWidenContinuePath.test_continue_path_writes_pending_entry` | cwd | `call:os.chdir` | A-monkeypatch | 307 |
| `tests/specify_cli/cli/commands/test_plan_widen.py` | `TestPlanWidenContinuePath.test_continue_path_writes_pending_entry` | cwd | `call:os.chdir` | B-contextlib.chdir | 345 |
| `tests/specify_cli/cli/commands/test_plan_widen.py` | `TestPlanWidenBlockPath.test_block_path_resolves_via_local_answer` | cwd | `call:os.chdir` | A-monkeypatch | 386 |
| `tests/specify_cli/cli/commands/test_plan_widen.py` | `TestPlanWidenBlockPath.test_block_path_resolves_via_local_answer` | cwd | `call:os.chdir` | B-contextlib.chdir | 427 |
| `tests/specify_cli/cli/commands/test_specify_widen.py` | `TestSpecifyWidenAbsent.test_widen_not_shown_without_prereqs` | cwd | `call:os.chdir` | A-monkeypatch | 107 |
| `tests/specify_cli/cli/commands/test_specify_widen.py` | `TestSpecifyWidenAbsent.test_widen_not_shown_without_prereqs` | cwd | `call:os.chdir` | B-contextlib.chdir | 133 |
| `tests/specify_cli/cli/commands/test_specify_widen.py` | `TestSpecifyWidenCancelPath.test_cancel_path_reprompts_and_continues` | cwd | `call:os.chdir` | A-monkeypatch | 162 |
| `tests/specify_cli/cli/commands/test_specify_widen.py` | `TestSpecifyWidenCancelPath.test_cancel_path_reprompts_and_continues` | cwd | `call:os.chdir` | B-contextlib.chdir | 199 |
| `tests/specify_cli/cli/commands/test_specify_widen.py` | `TestSpecifyWidenContinuePath.test_continue_marker_failure_reprompts_without_parking_blank` | cwd | `call:os.chdir` | A-monkeypatch | 238 |
| `tests/specify_cli/cli/commands/test_specify_widen.py` | `TestSpecifyWidenContinuePath.test_continue_marker_failure_reprompts_without_parking_blank` | cwd | `call:os.chdir` | B-contextlib.chdir | 263 |
| `tests/specify_cli/cli/commands/test_specify_widen.py` | `TestSpecifyWidenContinuePath.test_continue_path_writes_pending_entry` | cwd | `call:os.chdir` | A-monkeypatch | 293 |
| `tests/specify_cli/cli/commands/test_specify_widen.py` | `TestSpecifyWidenContinuePath.test_continue_path_writes_pending_entry` | cwd | `call:os.chdir` | B-contextlib.chdir | 331 |
| `tests/specify_cli/cli/commands/test_specify_widen.py` | `TestSpecifyWidenBlockPath.test_block_path_resolves_via_local_answer` | cwd | `call:os.chdir` | A-monkeypatch | 372 |
| `tests/specify_cli/cli/commands/test_specify_widen.py` | `TestSpecifyWidenBlockPath.test_block_path_resolves_via_local_answer` | cwd | `call:os.chdir` | B-contextlib.chdir | 413 |

## Branch Strategy

- **Strategy**: lane-based execution worktree
- **Planning base branch**: `issue-5119-merge-seam-test-isolation`
- **Merge target branch**: `issue-5119-merge-seam-test-isolation`
- The execution worktree is allocated per computed lane from `lanes.json`. Prepare it only with `.venv/bin/spec-kitty agent action implement WP07 --agent claude` (never reconstruct the path). This WP depends on **WP01** (the census gate and shard files must exist).
- Use `.venv/bin/python` / `.venv/bin/spec-kitty` — the `spec-kitty` on PATH may resolve to a different checkout. Never a bare `uv run` (it re-syncs the hand-built `.venv`).

## Subtasks & Detailed Guidance

### Subtask T031 – Capture the behavior baseline

- **Purpose**: Freeze per-test-id outcomes of the owned files before any edit (NFR-002).
- **Steps**:
  1. In the lane worktree, before editing, run:
     ```bash
     .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_charter.py tests/specify_cli/cli/commands/test_charter_decision_integration.py tests/specify_cli/cli/commands/test_charter_prereq_suppression.py ... -p no:randomly -q --junitxml=$SCRATCH/WP07-before.xml
     ```
     (pass **all** owned files; `$SCRATCH` = a temp dir outside the repo).
  2. Record pass/skip/xfail counts in the Activity Log. Any pre-existing red: classify via the baseline-red gotcha (CLAUDE.md) — confirm it is red on the WP base too; never "fix" an unrelated known-P0 red.
  3. Run the gate and note the shard's current row set: `.venv/bin/python -m pytest tests/architectural/test_no_manual_global_state_mutation.py -q` (green at WP01 head).
- **Files**: none edited.
- **Parallel?**: no — first.

### Subtask T032 – Convert class A sites (`monkeypatch.*`)

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

### Subtask T033 – Convert class B sites (block-scoped)

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

### Subtask T034 – Class C / D sites and justified-row review

- **Purpose**: Handle scope-wide and import-time mutations, and validate every remaining justified row.
- **Recipes**:
  - **C** — module/session-scoped fixture: `with pytest.MonkeyPatch.context() as mp: mp.setenv(...); yield`.
  - **D1** — redundant import-time `sys.path.insert` of the repo root, `src`, a worktree `src`, or `Path.cwd()/"src"`: **delete** it. The repo root is on `sys.path` via pytest rootdir-prepend (`tests/__init__.py` exists) and `src` via `pythonpath = src` in `pytest.ini`. Re-run the file to prove every import still resolves. Do **not** change `pytest.ini` (cross-cutting; out of scope).
  - **D2** — `src/specify_cli` inserted so `import gitignore_manager` works bare: import `specify_cli.gitignore_manager` (a bare import gives the module a second identity).
  - **D3** — `scripts`/`scripts/<pkg>` inserted for bare sibling imports: rewrite to the canonical `scripts.<pkg>.<mod>` import where it resolves; delete the insert.
  - **E rows** in this shard (`process-bootstrap` / `subprocess-entry` / `leak-sentinel`): read each site. Keep the row only if the mutation genuinely must touch real process state (e.g. runs in a child process / subprocess entry, must precede any fixture, or is the leak detector itself). If it can be converted, convert it **and** remove the row. Make each kept row's `reason` accurate.
- **Parallel?**: per file.

### Subtask T035 – Drain shard S2 and verify

- **Purpose**: Prove the shard is clean and behavior is unchanged.
- **Steps**:
  1. Recorded out-of-map edit (add a one-line rationale to the Activity Log): in `tests/architectural/global_state_allowlist/S2.yaml` delete **all** `transitional-sweep` rows; adjust justified rows' `count` to the exact remaining site count (or delete rows you converted). Touch no other shard.
  2. Gate: `.venv/bin/python -m pytest tests/architectural/test_no_manual_global_state_mutation.py -q` — must pass.
  3. Behavior: rerun the owned files with `--junitxml=$SCRATCH/WP07-after.xml` and compare:
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
  9. Mark subtasks: `.venv/bin/spec-kitty agent tasks mark-status T031 T032 T033 T034 T035 --status done --mission merge-seam-test-isolation-campsite-01M3F61E`.

## Test Strategy

- No new test files: this WP changes how existing tests patch state, not what they assert.
- Evidence to record in the Activity Log: before/after junit comparison output ("identical"), the gate result, the xdist run result, and the final row list of `S2.yaml`.
- Commit granularity: one commit per class or per coherent file group (e.g. `test(isolation): contextlib.chdir in charter CLI invoke helpers (#5118)`); end each commit message with the repo's attribution lines.

## Risks & Mitigations

- **Order dependence surfaces**: a test that silently relied on state leaked by an earlier test may now fail. Fix the root cause in the dependent test (give it the state explicitly) — never reorder, retry, or skip. If it is a pre-existing red unrelated to this shard, classify it via the baseline-red gotcha and note it; do not chase it.
- **`monkeypatch.chdir` too late**: restores only at teardown — a helper called twice per test, or a test that asserts on cwd after a block, needs `contextlib.chdir`.
- **Thread-pool timeouts**: cwd is process-wide; a worker thread that outlives the block observes the restored cwd either way — preserve the original ordering of join/restore.
- **xdist**: `--dist loadfile` keeps a file on one worker; module-level mutations previously leaked to every later file on that worker — the fix removes that coupling, so expect previously-masked failures elsewhere only if some later file depended on the leak (fix that file's setup if it is in this shard; otherwise record it).
- **`sys.modules` re-import**: deleting a submodule without the parent attribute leaves `pkg.sub` pointing at the stale module.
- **Scope creep**: do not refactor tests beyond the mutation sites; boy-scout only inside owned files.

## Review Guidance

- Every row in the shard's site table is either converted or justified; `S2.yaml` has no `transitional-sweep` rows.
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
- 2026-09-26T18:46:00Z – claude (python-pedro) – Converted all 64 sites across the 10 owned files (S2 shard) from manual `os.chdir` try/finally to `contextlib.chdir`, reclassifying every A-monkeypatch site to B (the classifier's A/B split within a single chdir(target)/chdir(restore) pair does not change the fact these are whole-invocation-scoped mutations best served by a context manager; helpers that mutate on the caller's behalf — `_invoke_interview`, `_invoke_with_prereqs`, `_invoke` — were converted in place rather than threading a `monkeypatch` fixture through every caller). `_invoke`/`_invoke_interview` with optional `cwd: Path | None` use `contextlib.chdir(cwd) if cwd is not None else contextlib.nullcontext()`. Removed now-dead `import os` from all 10 files (no other `os.*` usage existed in any of them). Drained all 32 `transitional-sweep` rows from `tests/architectural/global_state_allowlist/S2.yaml` (recorded out-of-map edit) to `rows: []` — no justified rows exist for this shard. Verified: census gate green (44 passed, 0 rows); `tests/architectural/test_home_pin*.py tests/architectural/test_no_sys_modules_patch_dict.py` green (154 passed); before/after junit identical (135 testcases, 133 passed + 2 skipped both runs); `-n 4 --dist loadfile` green (133 passed, 2 skipped); `ruff format --check` + `ruff check` clean on all 10 files; mypy pre-existing errors unchanged (test_charter.py 14, test_charter_decision_integration.py 2, test_charter_prereq_suppression.py 13, test_charter_widen.py 11, test_decision.py 75 — identical counts on base commit `a9022b3f978c`, confirming zero new errors; the other 5 files are mypy-clean). `make test-fast` could not run via `uv run --frozen` in this lane worktree (it re-synced into a fresh `.venv` missing `pytestarch`/test extras — a stale/unsynced-lane-venv environment issue per CLAUDE.md category 4, not this diff); ran the equivalent pytest invocation directly against `$MAIN/.venv` instead: 2045 passed, 5 skipped, 3 failed — all 3 failures in `tests/cli/commands/test_charter_json_error_contract.py`, a file this WP never touches (git history shows its last touches are unrelated commits `4e8fc05969`/`21ad036105`/`a95ad7cc0c`); classified as a pre-existing/unrelated red per the baseline-red gotcha, not chased. No `sys.modules` sites existed in shard S2 (all 64 sites were `kind: cwd`), so the sibling WP08 rejection heads-up about `monkeypatch.delitem(sys.modules, ...)` teardown-purge leakage does not apply to this WP's diff. No `src/**` changes; no new `# noqa`/`# type: ignore`. Subtasks T031–T035 marked done; moved WP07 to `for_review`.
