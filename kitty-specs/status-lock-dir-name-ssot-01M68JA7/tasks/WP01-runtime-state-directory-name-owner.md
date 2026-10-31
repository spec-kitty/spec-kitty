---
work_package_id: WP01
title: Name the runtime-state directory once and put the module back under the guard
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- C-001
- C-002
- SC-001
- SC-002
- SC-003
- SC-004
- SC-005
planning_base_branch: issue-6516-status-lock-dir-name-ssot
merge_target_branch: issue-6516-status-lock-dir-name-ssot
branch_strategy: Planning artifacts for this mission were generated on issue-6516-status-lock-dir-name-ssot. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6516-status-lock-dir-name-ssot unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-status-lock-dir-name-ssot-01M68JA7
base_commit: ee36cbb99e525ad036a671cfe5b0e6d9449a98f5
created_at: '2026-10-31T08:54:07.245056+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
history:
- at: '2026-10-31T08:52:00Z'
  actor: claude
  action: created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/paths/
create_intent:
- tests/audit/test_no_legacy_path_literals.py
execution_mode: code_change
owned_files:
- src/specify_cli/paths/windows_paths.py
- src/specify_cli/paths/__init__.py
- src/specify_cli/status/locking.py
- src/specify_cli/review/lock.py
- tests/audit/test_no_legacy_path_literals.py
role: implementer
tags: []
tracker_refs:
- '6516'
---

# WP01 — Name the runtime-state directory once and put the module back under the guard

## ⚡ Do This First: Load Agent Profile

Load **`python-pedro`** (implementer) with the `/spk-charter-profile-load` skill before reading
anything else. The review runs under **`reviewer-renata`**.

## Objective

`src/specify_cli/status/locking.py` types the runtime-state directory name by hand
(`_NON_GIT_LOCK_HOME = ".spec-kitty"`, #6367) for the bare non-git status-lock fallback, and
`src/specify_cli/review/lock.py` types the same name by hand (`LOCK_DIR = ".spec-kitty"`).
Both name a **repository-local** runtime directory — `<repo_root>/.spec-kitty` — not the
user-global home, so both are exempted from the runtime-home audit gate; the `status/locking.py`
exemption was added by #6582 in a nightly-escalation hurry and is exactly the blind allowlist
issue #6516 forbids.

Move the *name* to its canonical owner (the same path authority the gate already sanctions),
re-point both consumers at it, and drain both exemptions. **Nothing else changes**: the lock
locations, the review lock, and the user-global home resolve to the same values as today.

Spec: FR-001..FR-006, NFR-001..NFR-002, C-001..C-002, SC-001..SC-005.

## Context

Current state on `origin/main`:

```python
# src/specify_cli/status/locking.py:62-65
#: Lock home for a bare non-git tree (no ``.git`` and no ``.kittify``). Not a
#: project or repository marker, so creating it never changes what a later
#: root walk resolves (#6367). Same directory name ``review.lock`` uses.
_NON_GIT_LOCK_HOME = ".spec-kitty"

# src/specify_cli/review/lock.py:36
LOCK_DIR = ".spec-kitty"

# src/specify_cli/paths/windows_paths.py — get_runtime_root(), POSIX + Windows fallback
base = Path.home() / ".spec-kitty"
```

The owner module, `specify_cli/paths/windows_paths.py`, is the runtime-state path authority. Its
module docstring is explicit: *"This module is a leaf — it must not import from
specify_cli.auth, specify_cli.tracker, or any kernel subpackage."* Adding a `str` constant to it
adds no import. `get_runtime_root()` is pinned pure (no I/O) by
`tests/paths/test_runtime_root_spec_kitty_home.py`.

`tests/audit/test_no_legacy_path_literals.py` scans `src/specify_cli` + `src/kernel` for the bare
literal, skipping `_HOME_LITERAL_ALLOWLIST`. Its own comment currently justifies the two entries
this WP removes.

## Subtasks

### T001 — Red-first: drain both exemptions and capture the red *(WP01)*

Remove `src/specify_cli/status/locking.py` and `src/specify_cli/review/lock.py` from
`_HOME_LITERAL_ALLOWLIST` (keep every other entry and the comment block coherent), then run:

```bash
uv run pytest tests/audit/test_no_legacy_path_literals.py \
  -k test_no_handrolled_spec_kitty_home_in_global_state_modules -q
```

Capture the exact failure text in your report: it must name both files and their literal lines.
Commit this step **on its own** so the red is in the history (the fix commits follow).

### T002 — Name the directory once, in its owner *(WP01)*

In `src/specify_cli/paths/windows_paths.py`:

- Add a public module constant next to the other path-name constants, e.g.

  ```python
  #: Canonical name of the runtime STATE directory. The user-global runtime root
  #: ends in it (``~/.spec-kitty``), and the repository-local runtime directory
  #: that holds worktree-scoped lock state deliberately shares it, so neither
  #: scope re-types the name.
  RUNTIME_STATE_DIR_NAME = ".spec-kitty"
  ```

- Use it in `get_runtime_root()`'s POSIX branch and its Windows `platformdirs`-failure branch
  (`Path.home() / RUNTIME_STATE_DIR_NAME`) so the literal appears exactly once in the module.
- Add it to `__all__` in this module and re-export it from `src/specify_cli/paths/__init__.py`
  (both `from ... import` and `__all__`).
- **Do not** add an import to this module (NFR-001). **Do not** change resolution order, the
  `SPEC_KITTY_HOME` branch, purity, or any error message.

### T003 — Status-lock consumer *(WP01)*

In `src/specify_cli/status/locking.py`:

- Delete `_NON_GIT_LOCK_HOME` and replace it with `_NON_GIT_LOCK_DIR` sourced from the owner
  (`from specify_cli.paths import RUNTIME_STATE_DIR_NAME`, then
  `_NON_GIT_LOCK_DIR = RUNTIME_STATE_DIR_NAME`), placed where the old constant was.
- Rewrite the constant's comment so it says what the value is (a repository-local lock directory,
  never the user-global home; no root walk treats it as a project or repository marker — #6367)
  and that the name comes from the path authority.
- Update the `_git_common_dir` docstring reference from `:data:`_NON_GIT_LOCK_HOME`` to the new
  name, and keep the three-branch explanation intact.
- The returned path must stay `Path(repo_root / _NON_GIT_LOCK_DIR)`.

### T004 — Review-lock consumer *(WP01)*

In `src/specify_cli/review/lock.py`:

- Keep the public name `LOCK_DIR` (imported by `cli/commands/agent/workflow.py` and four test
  modules) but source its value from the owner:
  `LOCK_DIR = RUNTIME_STATE_DIR_NAME`.
- Keep `LOCK_FILE`, `LOCK_REL_PATH` and every consumer unchanged. `LOCK_REL_PATH` stays
  `".spec-kitty/review-lock.json"`.
- Check the import cannot form a cycle: `specify_cli.review.lock` already imports
  `specify_cli.core.process_liveness` and kernel modules; `specify_cli.paths` imports only
  `kernel.paths` and `platformdirs`.

### T005 — Pin the exemption out (self-mutation half of the gate) *(WP01)*

In `tests/audit/test_no_legacy_path_literals.py`, after `test_home_literal_guard_is_non_vacuous`:

- Add a test that scans with `frozenset()` as the allowlist (the bypass) and asserts **no**
  violation starts with `src/specify_cli/status/locking.py:` or
  `src/specify_cli/review/lock.py:`. Docstring: this is the pin that makes re-adding the literal
  *and* an allowlist entry go red — the shrunken allowlist cannot silently regrow.
- Reference tactic `architectural-gate-non-vacuity` (shrink-only allowlist) in the docstring
  rather than restating it.
- Do not restructure the existing tests; the existing positive control
  (`test_home_literal_guard_is_non_vacuous`, keystone detection) stays exactly as it is.

### T006 — Green and blast radius *(WP01)*

Run and record (commands + passed/failed counts for the PR body):

```bash
uv run pytest tests/audit/test_no_legacy_path_literals.py -q
uv run pytest tests/status/test_lock_fallback_never_mints_marker.py tests/status/test_locking_reentrancy_migration.py -q
uv run pytest tests/status -q -m "fast or unit"
uv run pytest tests/review -q -m "fast or unit"
uv run pytest tests/paths tests/kernel/test_runtime_root_resolver_parity.py -q
uv run pytest tests/specify_cli/test_audit_tail_readers.py tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py -q -k "lock or Lock"
uv run --frozen ruff check src/specify_cli/paths src/specify_cli/status src/specify_cli/review tests/audit
uv run --frozen ruff format --check --force-exclude <changed files>
uv run --frozen mypy src/specify_cli/paths/windows_paths.py src/specify_cli/status/locking.py src/specify_cli/review/lock.py
```

Never run a whole-repo suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`). If a failure is not caused by
this diff, classify it against the base per the repository's baseline-red policy instead of
"fixing" it.

## Branch Strategy

Planning base and merge target: `issue-6516-status-lock-dir-name-ssot`. Worktree per the lane in
`lanes.json`.

```bash
spec-kitty agent action implement WP01 --agent python-pedro --mission status-lock-dir-name-ssot-01M68JA7
```

## Definition of Done

- [ ] T001 red captured and committed before the fix; the failure named both modules.
- [ ] `_HOME_LITERAL_ALLOWLIST` contains neither `src/specify_cli/status/locking.py` nor
      `src/specify_cli/review/lock.py`, and gained no entry.
- [ ] The bare `".spec-kitty"` literal appears in `src/specify_cli` only in
      `paths/windows_paths.py` (once, the owner) and `paths/windows_migrate.py` (legacy
      migration code that must name the legacy directory); `status/locking.py` and
      `review/lock.py` contain none.
- [ ] `specify_cli.paths.RUNTIME_STATE_DIR_NAME == ".spec-kitty"`; both consumers equal it.
- [ ] No test assertion in `tests/status/`, `tests/review/` or `tests/paths/` was changed.
- [ ] ruff check + format clean on changed files; no new mypy errors.
- [ ] No `# noqa`, `# type: ignore` or gate suppression added.

## Risks

- `paths/windows_paths.py` must stay an import leaf — a new import there is a charter violation.
- `LOCK_DIR` must keep its name and value; the four importing test modules build real lock files
  under `tmp_path / LOCK_DIR`.
- The fallback directory must not move: the bare-tree test asserts the exact path and that no
  `.git`/`.kittify` marker appears.

## Reviewer guidance

Verify (a) the red commit precedes the fix commits and fails for the right reason; (b) the
allowlist shrank by exactly two entries and nothing else in the gate moved; (c) the new bypass
test would fail if either literal came back; (d) no path resolution value changed —
`git diff` shows no changes under `tests/status/`, `tests/review/`, `tests/paths/`.
