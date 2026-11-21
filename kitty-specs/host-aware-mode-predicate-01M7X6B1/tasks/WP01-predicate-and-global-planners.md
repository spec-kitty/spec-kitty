---
work_package_id: WP01
title: Shared host-aware mode predicate and global planners converge
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- C-001
- C-002
- SC-001
- SC-002
planning_base_branch: issue-4927-host-aware-mode-predicate
merge_target_branch: issue-4927-host-aware-mode-predicate
branch_strategy: Planning artifacts for this mission were generated on issue-4927-host-aware-mode-predicate. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4927-host-aware-mode-predicate unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-host-aware-mode-predicate-01M7X6B1
base_commit: 7cd05233c5b51bc925738c74d2a294f118ca86ef
created_at: '2026-11-20T19:26:20.703998+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundation and reported leak
history:
- at: '2026-11-20T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/tool_surface/operations.py
create_intent:
- tests/specify_cli/tool_surface/ntfs_emulation.py
- tests/specify_cli/tool_surface/test_mode_equivalence.py
- tests/specify_cli/runtime/test_global_mode_convergence_windows.py
execution_mode: code_change
owned_files:
- src/specify_cli/tool_surface/operations.py
- src/specify_cli/runtime/asset_preparation.py
- tests/specify_cli/tool_surface/ntfs_emulation.py
- tests/specify_cli/tool_surface/test_mode_equivalence.py
- tests/specify_cli/runtime/test_global_mode_convergence_windows.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Shared host-aware mode predicate and global planners converge

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission host-aware-mode-predicate-01M7X6B1`). Address every item and record progress with `spec-kitty agent tasks add-history WP01 --note "..."`.

## Objectives & Success Criteria

- One host-aware mode equivalence lives in `src/specify_cli/tool_surface/operations.py` (FR-001).
- `effect_action(before, after)` is the single action function; `PhysicalEffect.__post_init__` validates with it (FR-002).
- `runtime/asset_preparation.py` no longer has its own `_action`; global runtime/commands/skills effects are decided by `effect_action` (FR-002, FR-003).
- On an emulated Windows host a converged global home plans **0** effects after one apply (today 253) (SC-001).
- POSIX twins (0o777 dir, lost exec bit, read-only file) still plan exactly one repair each and converge (FR-004, SC-002).

## Context & Constraints

- Spec: `kitty-specs/host-aware-mode-predicate-01M7X6B1/spec.md`; plan IC-01/IC-02; research R-1, R-3, R-5, R-6; data-model.md.
- Host detection ONLY via `kernel.paths.is_windows`, called as a module attribute at call time (`from kernel import paths as kernel_paths; kernel_paths.is_windows()`), never `from kernel.paths import is_windows` (binding prevents monkeypatching) and never `os.name` (C-001; `tests/architectural/test_os_detection_ban.py`).
- No new layer edge (C-002): `operations.py` may import `kernel.paths` (root layer).
- POSIX behaviour of `effect_action` must be identical to today's `_action`.
- Red first (C-004, charter ATDD): commit T001–T003 tests alone first, show them red, then implement.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-4927-host-aware-mode-predicate`
- **Merge target branch**: `issue-4927-host-aware-mode-predicate`

Implement with: `spec-kitty agent action implement WP01 --agent claude --mission host-aware-mode-predicate-01M7X6B1`

## Subtasks & Detailed Guidance

### Subtask T001 – NTFS emulation fixture

- **Purpose**: a faithful, reusable Windows file-system emulation on Linux so every later test (WP01, WP02) shares one definition.
- **File**: `tests/specify_cli/tool_surface/ntfs_emulation.py` (new). Expose a function `emulate_ntfs(monkeypatch) -> None` and a pytest fixture `ntfs_host` (yield after emulation). Also `posix_host` fixture that pins `kernel_paths.is_windows` to False (so the harness's real host is irrelevant).
- **Semantics** (operator ruling):
  - `os.stat`, `os.lstat`, `os.fstat` return a `os.stat_result` whose `st_mode` permission bits are synthesized: directory → `0o777`; regular file → `0o666` if the real mode has `0o200`, else `0o444`; symlinks and others unchanged. Preserve the `S_IFMT` bits and every other field (build via `list(result)`, replace index 0).
  - `os.chmod(path, mode, *, dir_fd=None, follow_symlinks=True)`: if the target is a directory → no-op; else set the real mode to `0o644` if `mode & 0o200` else `0o444`. `os.fchmod(fd, mode)` likewise via `os.fstat` on the real fd.
  - `kernel.paths.is_windows` → `lambda: True` via `monkeypatch.setattr(kernel_paths, "is_windows", ...)`.
  - Do **not** patch `os.name` (pathlib would switch to WindowsPath).
  - Check whether `specify_cli.core.no_follow` / `kernel.no_follow` call `os.chmod`/`os.fchmod` or `os.lchmod`; patch anything they use for mode setting so the emulation stays faithful (grep `chmod` in `src/kernel/no_follow.py`).
- **Docstring**: state the emulation's known gap (no `os.DirEntry.stat`), referencing research R-6.

### Subtask T002 – Red: predicate unit matrix

- **File**: `tests/specify_cli/tool_surface/test_mode_equivalence.py` (new); markers `pytest.mark.unit, pytest.mark.fast`.
- Parametrize over host (`windows` True/False via monkeypatching `kernel_paths.is_windows`):
  - `modes_equivalent("directory", 0o777, 0o755)` → Windows True, POSIX False.
  - `modes_equivalent("symlink", 0o777, 0o755)` → Windows True, POSIX False.
  - `modes_equivalent("file", 0o666, 0o644)` → Windows True; `("file", 0o666, 0o755)` → Windows True (exec bit unrepresentable); `("file", 0o444, 0o644)` → Windows False; `("file", 0o666, 0o444)` → Windows False; `("file", 0o444, 0o444)` → True on both. POSIX: exact equality in every case.
  - `mode_equivalent(FileState(...), FileState(...))`: different kinds → False on both hosts; absent/absent → True.
  - `state_equivalent`: differing sha256 → False on both hosts even when modes are equivalent; differing mtime ignored by default, honoured with `ignore_mtime=False`; differing target → False.
  - `effect_action`: POSIX parity table against the old ladder (create/delete/replace/update/retarget/chmod/None) for a representative set of pairs; Windows: dir 0o777 vs 0o755 → None; file 0o666 vs 0o644 → None; file 0o444 vs 0o644 → "chmod".
  - `PhysicalEffect(... action="chmod", before=dir 0o777, after=dir 0o755)` raises `ValueError` on Windows, is accepted on POSIX.
- These import names that do not exist yet → red (ImportError) on the base commit. That is the expected red.

### Subtask T003 – Red: global convergence + POSIX twins

- **File**: `tests/specify_cli/runtime/test_global_mode_convergence_windows.py` (new).
- Isolate HOME: set `HOME` and `SPEC_KITTY_HOME` to `tmp_path` dirs via `monkeypatch.setenv` (see how `tests/specify_cli/runtime/test_global_skills_empty_selection.py` or `tests/runtime/test_global_asset_inventory_anchor.py` isolate the home; reuse their helpers if any). Check for module-level caches (`lru_cache`) on registry/home resolution and clear them if present.
- Scenarios:
  1. `test_global_skills_converge_under_emulated_windows`: on POSIX run `ensure_global_agent_skills()` (materialize), then `emulate_ntfs`, assert `assess_global_agent_skills().effects == ()`... Today: 253 chmods. Also: after `ensure_global_agent_skills()` under emulation, still 0.
  2. `test_fresh_home_converges_in_one_pass_under_emulated_windows`: emulate first, `ensure_global_agent_skills()`, then reassess → no effects.
  3. `test_global_assets_combined_converge_under_emulated_windows`: materialize with `assess_global_assets()` + apply (find the canonical apply entry: `apply_with_reassess` or `apply_assets` under `recheck_assets`; mirror `ensure_runtime` / upgrade's usage), emulate, assess → no `chmod` effects.
  4. POSIX twin: after materialize on POSIX, `chmod` one managed skill dir to 0o777 → assessment has exactly one `chmod` effect for that path with `after.mode == 0o755`; apply; reassess → none.
  5. POSIX exec-bit twin: find a runtime asset whose source is executable (runtime bootstrap scripts; grep `ensure_runtime`/`bootstrap.py` for scripts). If none is executable in the package, construct the case through a skill file with an exec bit in a source tree you control via `GlobalSkillSelection` — otherwise document why and assert on a file planned 0o644 that was chmodded 0o600 instead (still "drift converges on POSIX").
  6. Windows read-only twin for global assets: under emulation, make a managed file planned writable read-only (`os.chmod(p, 0o444)` through the emulation) → exactly one `chmod` effect; apply; reassess → none.
- Commit T001–T003 together as the red commit (`test(tool-surface): ... (red)`), run them, record the red output in the WP history.

### Subtask T004 – Predicate, effect_action and validator

- **File**: `src/specify_cli/tool_surface/operations.py`.
- Add (with `__all__` if the module declares one; check):
  ```python
  from kernel import paths as kernel_paths

  _WRITE_BIT = 0o200

  def modes_equivalent(kind: str, observed: int | None, planned: int | None) -> bool:
      """The one host-aware mode equivalence (#4927, #4810). ..."""
      if observed is None or planned is None or not kernel_paths.is_windows():
          return observed == planned
      if kind in ("directory", "symlink"):
          return True
      return bool(observed & _WRITE_BIT) == bool(planned & _WRITE_BIT)

  def mode_equivalent(observed: FileState, planned: FileState) -> bool:
      return observed.kind == planned.kind and modes_equivalent(observed.kind, observed.mode, planned.mode)

  def state_equivalent(observed: FileState, planned: FileState, *, ignore_mtime: bool = True) -> bool:
      return (
          (observed.kind, observed.sha256, observed.target) == (planned.kind, planned.sha256, planned.target)
          and (ignore_mtime or observed.mtime_ns == planned.mtime_ns)
          and mode_equivalent(observed, planned)
      )

  def effect_action(before: FileState, after: FileState) -> str | None:
      ... same ladder as _action, last rung: return None if mode_equivalent(before, after) else "chmod"
  ```
- Rename `_action` → `effect_action` (public), update the validator call in `PhysicalEffect.__post_init__` and every in-module caller. Do NOT keep `_action` as an alias (single authority).
- Docstrings: state the Windows semantics (operator ruling 2026-11-20), the POSIX invariant (exact equality), and that observed-vs-observed guards and planned-vs-planned conflict checks must NOT use it (they compare exactly).
- Complexity ≤ 15 per function; mypy strict clean.

### Subtask T005 – asset_preparation delegates

- **File**: `src/specify_cli/runtime/asset_preparation.py`.
- Delete the local `_action` (lines ~78-89 on base) and import `effect_action` from `specify_cli.tool_surface.operations` (the module already imports `FileState` etc. from there — extend that import). Replace every `_action(` call with `effect_action(`.
- Leave `check_assets` (observed-vs-observed drift, ~:1206) and the conflicting-outputs check (~:463, planned-vs-planned) exact — add a one-line comment at each naming it a guard / conflict check so WP03's adjudication is obvious.
- `_write_asset` stays as is (chmod of a skipped effect never runs; a planned chmod on Windows toggles only the write bit).
- Run the T002/T003 tests → green.

## Test Strategy

Run (record commands + counts in the WP history):
```bash
.venv/bin/python -m pytest tests/specify_cli/tool_surface/test_mode_equivalence.py tests/specify_cli/runtime/test_global_mode_convergence_windows.py -q
.venv/bin/python -m pytest tests/specify_cli/tool_surface/test_operations.py tests/runtime/test_upgrade_preview_bootstrap.py tests/runtime/test_generic_asset_scope.py tests/runtime/test_global_asset_inventory_anchor.py tests/specify_cli/runtime/test_global_skills_historical_proof.py tests/specify_cli/runtime -q -n 4 --dist loadfile
.venv/bin/python -m pytest tests/upgrade/test_preview_oracle.py -q
make test-fast
.venv/bin/ruff check <changed files> && .venv/bin/ruff format --check --force-exclude <changed files>
.venv/bin/mypy --explicit-package-bases src/specify_cli/tool_surface/operations.py src/specify_cli/runtime/asset_preparation.py
```
Note: other Windows-emulated paths (command_installer, project skills, bundles) may now raise in the validator under emulation; that is WP02's scope. Do not run WP02's tests as acceptance here.

## Risks & Mitigations

- **Validator sharpness** (research R-3): on real Windows, a raw chmod planner now raises instead of phantom-repairing. WP02 converts every remaining planner before the PR ships; WP03's gate prevents regressions.
- **Home isolation**: global assessment reads the real package catalog; keep HOME under `tmp_path` so no user directory is touched.
- **Emulation leaks**: patch via `monkeypatch` only, so teardown restores `os.*`.

## Review Guidance

- Verify red→green: T001–T003 commit is red on the WP base and green at the WP tip.
- `effect_action` on POSIX is byte-for-byte the old ladder (read the diff); no `_action` alias left.
- Host check only through `kernel_paths.is_windows()` at call time.
- ruff/format/mypy clean; no new suppressions.

## Progress & Status

Use `spec-kitty agent tasks add-history WP01 --note "..."` and `spec-kitty agent tasks move-task WP01 --to <status>`; never hand-edit this file's history.
