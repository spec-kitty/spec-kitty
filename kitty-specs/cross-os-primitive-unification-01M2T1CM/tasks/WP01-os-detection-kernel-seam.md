---
work_package_id: WP01
title: OS-detection kernel seam + non-vacuous ban gate
dependencies: []
requirement_refs:
- FR-004
- FR-005
- FR-012
planning_base_branch: feat/cross-os-primitive-unification
merge_target_branch: feat/cross-os-primitive-unification
branch_strategy: Planning artifacts for this mission were generated on feat/cross-os-primitive-unification. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/cross-os-primitive-unification unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Implementation
history:
- at: '2026-09-18T11:05:00Z'
  actor: system
  action: Prompt generated for cross-os-primitive-unification mission
agent_profile: python-pedro
authoritative_surface: src/kernel/paths.py
create_intent:
- tests/architectural/test_os_detection_ban.py
- tests/kernel/test_is_windows_seam.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/kernel/paths.py
- src/specify_cli/runtime/home.py
- src/specify_cli/core/upgrade_notifier.py
- src/specify_cli/status/store.py
- src/specify_cli/bytecode_heal.py
- src/specify_cli/configured_command.py
- src/specify_cli/session_presence/upgrade_check.py
- src/specify_cli/runtime/agent_commands.py
- src/specify_cli/cli/commands/migrate_cmd.py
- src/specify_cli/migration/rewrite_shims.py
- src/specify_cli/encoding.py
- src/specify_cli/manifest.py
- src/specify_cli/core/worktree.py
- src/specify_cli/compat/cache.py
- src/specify_cli/compat/config.py
- src/specify_cli/compat/history.py
- src/specify_cli/compat/_detect/runtime.py
- src/specify_cli/auth/secure_storage/abstract.py
- tests/architectural/test_os_detection_ban.py
- tests/kernel/test_is_windows_seam.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#4714'
---

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (role: implementer) via the profile-load skill before proceeding.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## Objectives & Success Criteria

Promote the OS-detection helper to one canonical, **patchable** kernel seam and
route the routable Windows-detection zoo through it, guarded by a non-vacuous
architectural gate. This is a tidy-first enabler (Wave A): it de-noises
`core/file_lock.py`'s inline check *before* WP03 moves that module to kernel.

Read first: `../spec.md` (FR-004/005/012, C-003, SC-002),
`../contracts/safe-delete-and-os-seam.md` §B/§C, `../research.md` R-05,
`../data-model.md` E-03.

**Success**: `_is_windows` exists once (in kernel), reachable via a patchable
module attribute; routable sites call it; the gate fails on an inline
`os.name`/`sys.platform` Windows check outside the seam.

## Context

Grounding confirmed **3** `def _is_windows` (`kernel/paths.py`,
`runtime/home.py`, `runtime/asset_preparation.py`) + 1 inline check in
`core/file_lock.py`, plus a wider `os.name=="nt"` / `sys.platform=="win32"` /
`platform.system()=="Windows"` zoo. `asset_preparation.py` and
`core/file_lock.py` are routed by their owning WPs (WP04, WP03) — **do not touch
them here**; seed them into the gate allowlist so those WPs shrink their own
entries. `src/specify_cli/__init__.py`'s inline checks are deferred with the
argv work (NG-01, version-bump coupling) — allowlist them, do not route.

**Critical testability constraint (C-003)**: never fake `os.name` in a test — it
flips `pathlib` to `WindowsPath` and crashes pytest. The seam must be overridable
by monkeypatching the imported `is_windows` attribute. Consumers therefore do
`from kernel.paths import is_windows` and call `is_windows()` — not
`import kernel.paths; kernel.paths.is_windows()` bound too early, and never an
inline literal.

## Subtasks

### T001 — Promote the kernel seam
Promote `kernel/paths.py::_is_windows` to a public `is_windows() -> bool`
(`return os.name == "nt"`). Keep a private `_is_windows = is_windows` alias only
if an internal caller needs it. Update the two in-module callers
(`paths.py:79`, `:334`).

### T002 — Route home.py + pure-zoo cluster 1
Route through `from kernel.paths import is_windows`: `runtime/home.py`
(delete its `_is_windows`), `core/upgrade_notifier.py`, `status/store.py`,
`bytecode_heal.py`, `configured_command.py`. Replace inline
`os.name == "nt"` / `sys.platform == "win32"` / `platform.system() == "Windows"`
with `is_windows()`. Leave macOS (`darwin`) branches untouched.

### T003 — Route pure-zoo cluster 2 + compat + abstract
Same for `session_presence/upgrade_check.py`, `runtime/agent_commands.py`,
`cli/commands/migrate_cmd.py`, `migration/rewrite_shims.py`, `encoding.py`
(win-negation via `sys.platform.startswith("win")`), `manifest.py`
(`platform.system()=="Windows"`), `core/worktree.py` (`platform.system()`).
**Also route the previously-uncounted routable sites** (post-tasks squad MF-2/3):
`compat/cache.py:381,505`, `compat/config.py:111`, `compat/history.py:139`,
`compat/_detect/runtime.py:126,176` (make the `Literal["posix","windows"]`
normalizer consume `is_windows()` — one authority, not a parallel one), and
`auth/secure_storage/abstract.py:44` (a routable **backend-selection** branch,
NOT an import guard). Do **not** touch `upgrade/migrations/`.

### T004 — Author the non-vacuous OS-detection ban gate
`tests/architectural/test_os_detection_ban.py`, modelled on
`tests/architectural/test_clock_call_ban.py`:
- **Scan corpus = `src/` ONLY** (post-tasks squad MF-1). This is a **deliberate
  divergence** from the clock template's `SCAN_ROOTS=(src,tests,scripts)`: the
  gate prevents re-forking of *production* OS-detection; `tests/` and `scripts/`
  legitimately exercise platform branches (and the lock parity harness needs raw
  primitives). Record the divergence in the gate docstring.
- Ban **all four idioms** (post-tasks squad S-1) outside `src/kernel/paths.py`
  (AST walk): `os.name == "nt"`, `sys.platform == "win32"`,
  `platform.system() == "Windows"`, and `sys.platform.startswith("win")`.
  FR-005 explicitly enumerates `platform.system()`; a gate that misses it leaves
  the recurrence half-closed.
- **Concrete floor**: assert `kernel/paths.py` actually contains the check
  (deleting the seam must fail, not pass).
- **Self-mutation**: feed the scanner a synthetic violation string → must flag.
- **Per-WP exemption files** (post-tasks squad S-2), like the clock template's
  `tests/architectural/_exemptions/*.txt` plural glob — so WP03/WP04 shrink
  their own file without colliding on rebase.
- **Sanctioned-raw allowlist** (shrink-only) = the **module-scope Windows-only
  C-module import guards ONLY** (the `if <win>: import msvcrt/fcntl` idiom):
  `core/file_lock.py`, `paths/windows_migrate.py`, `tracker/credentials.py`,
  `runtime/bootstrap.py`, `review/pre_review_gate.py` (its `import fcntl` guard,
  NOT its `:260` advisory-skip branch). Plus the not-yet-routed sites owned by
  other WPs, seeded fail-closed for them to shrink: `runtime/asset_preparation.py`
  (WP04), `core/file_lock.py` inline (WP03), `auth/token_manager.py:109`
  (routable path-select, routed by WP03 T012 — NOT an import guard),
  `review/pre_review_gate.py:260` (routable advisory-skip, routed by WP04 T019),
  and `__init__.py` (deferred, NG-01). Exclude `src/specify_cli/upgrade/migrations/`.
- Seeded fail-closed; WP03/WP04 shrink their own entries.

### T005 — Seam unit tests
`tests/kernel/test_is_windows_seam.py`: prove `is_windows()` is patchable via
`monkeypatch.setattr("kernel.paths.is_windows", lambda: True)` and that a routed
consumer honours the override, with **no** test setting `os.name`.

## Branch Strategy

Planning base and merge target: `feat/cross-os-primitive-unification`. During
`/spec-kitty.implement` this WP runs in its computed lane worktree from
`lanes.json`; completed changes merge back into the mission branch, which lands
via PR to `skupstream/main`.

## Definition of Done

- One `is_windows()` in kernel; `home.py`'s copy deleted; routed sites call the seam.
- Gate present, non-vacuous (floor + self-mutation pass), seeded fail-closed.
- Seam unit tests green without faking `os.name`.
- `ruff check`/`ruff format --check` clean on owned files; complexity ≤15.

## Risks

- **Over-routing** a C-module import guard: leave module-scope `import msvcrt`/
  `fcntl` guards raw (allowlisted). Only route *non-import* Windows branching.
- Missing a routable site → the gate stays red for it; either route it (if owned
  here) or allowlist it as owned-by-another-WP with a comment.

## Reviewer guidance (reviewer-renata, opus)

Verify: no inline `os.name`/`sys.platform` Windows check remains in owned files;
the gate is non-vacuous (temporarily break the floor to confirm it fails); no
test fakes `os.name`; macOS branches untouched.
