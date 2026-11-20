---
work_package_id: WP01
title: Content authority, identity fallback, manager and hook
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-007
- NFR-003
- C-001
- C-002
- SC-003
planning_base_branch: fix/5215-orientation-content-authority
merge_target_branch: fix/5215-orientation-content-authority
branch_strategy: Planning artifacts for this mission were generated on fix/5215-orientation-content-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/5215-orientation-content-authority unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundation
history:
- at: '2026-11-20T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/session_presence/
create_intent:
- src/specify_cli/session_presence/projection.py
- tests/specify_cli/session_presence/test_orientation_projection_5215.py
execution_mode: code_change
owned_files:
- src/specify_cli/session_presence/projection.py
- src/specify_cli/session_presence/manager.py
- src/specify_cli/identity/project.py
- src/specify_cli/cli/commands/session_start.py
- tests/specify_cli/session_presence/test_orientation_projection_5215.py
- tests/specify_cli/session_presence/test_manager.py
- tests/specify_cli/identity/test_project_slug_git_remote.py
- tests/specify_cli/cli/commands/test_session_start.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Content authority, identity fallback, manager and hook

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback before re-submitting.

## Objectives & Success Criteria

- One module, `specify_cli/session_presence/projection.py`, decides the committed orientation content (FR-001).
- The project name is `project.slug`, else the git remote repository name, else `"unknown"`; never the directory name (FR-002).
- Committed content always carries `health="healthy"` and `available_version=None` (FR-003).
- The SessionStart hook keeps live health but uses the same slug (FR-007).
- The shipped rc39 / 3.3.0 migrations are not edited (C-001); they become deterministic because they call `SessionPresenceManager._build_content()`.

## Context & Constraints

- Spec: `kitty-specs/orientation-content-authority-01M7X5W6/spec.md`; plan, research and data model beside it.
- Charter: `.kittify/charter/charter.md` (single canonical authority; ATDD red-first; complexity ≤ 15; `__all__` on new modules).
- No layer change: `identity` and `session_presence` both live in `specify_cli`.

## Branch Strategy

- **Strategy**: single_branch — work directly in the repository root checkout on `fix/5215-orientation-content-authority`.
- **Planning base branch**: fix/5215-orientation-content-authority
- **Merge target branch**: fix/5215-orientation-content-authority (the PR then targets `main`).
- Command: `spec-kitty agent action implement WP01 --agent claude --mission orientation-content-authority-01M7X5W6`

## Subtasks

### T001 — Red-first tests

New file `tests/specify_cli/session_presence/test_orientation_projection_5215.py` (mark `fast`/unit per conftest conventions). Write these first and confirm they FAIL on the base (the module does not exist / manager uses live health):

1. `resolve_project_slug` returns `project.slug` when recorded, even when the directory name differs (fixture dir `dirname-differs`, slug `local-agent-bus`).
2. No `project.slug`, git remote `https://example.invalid/acme/acme-widgets.git` → `acme-widgets` (use a real `git init` + `git remote add origin`).
3. No `project.slug`, no remote → `"unknown"` (assert it is not the directory name).
4. `expected_orientation(root)` has `health == "healthy"` and `available_version is None` even when the upgrade cache reports a newer version (patch `UpgradeChecker.get_available_version`).
5. `SessionPresenceManager(root, cfg)._build_content() == expected_orientation(root)` (the migration path is deterministic).
6. Hook/file agreement: the slug in `live_content()` equals the slug in `expected_orientation(root)`.

### T002 — `slug_from_git_remote`

In `src/specify_cli/identity/project.py` extract the remote-parsing part of `derive_project_slug` into `slug_from_git_remote(repo_root: Path) -> str | None` (returns `None` on `CalledProcessError` / `FileNotFoundError` or an empty name). `derive_project_slug` becomes `slug_from_git_remote(root) or _normalize_slug(root.name)` — behaviour unchanged; existing `tests/specify_cli/identity/test_project_slug_git_remote.py` stays green. Add one test for the `None` case there.

### T003 — Projection module

`src/specify_cli/session_presence/projection.py` with `__all__`:

- `resolve_project_slug(root: Path) -> str` — `load_identity(root / ".kittify" / "config.yaml").project_slug or slug_from_git_remote(root) or "unknown"`. `git` is only spawned when the slug is not recorded (NFR-003).
- `expected_orientation(root: Path) -> SessionPresenceContent` — installed version via `importlib.metadata.version("spec-kitty-cli")`; raise `ValueError` when unavailable (preserves the provider's existing error handling); `SessionPresenceContent(version, slug, "healthy", None)`.
- `orientation_writer(root: Path, key: str, configured: set[str] | None) -> MarkdownRulesWriter | None` — the writer for `key` when `configured is None or key in configured`, it is a `MarkdownRulesWriter`, and `can_write(root)`.

Docstring: name #5215, the operator rulings and that this is the single authority.

### T004 — Manager

- `_build_content()` → `return expected_orientation(self.project_root)` (docstring: committed content, deterministic; migrations call it).
- New public `live_content()`: today's live-health body (UpgradeChecker, compat plan), slug from `resolve_project_slug`.
- `_project_slug` is removed in favour of `resolve_project_slug`.
- `update(dry_run=True)` uses `self._build_content()` too (the variant is gone).
- `install` / `update` select writers with `orientation_writer(root, key, None)` where it fits (keep `has_presence` in install). Keep `local_presence_content` for now; WP02 removes it once the provider no longer imports it.

### T005 — Hook + re-pins

- `cli/commands/session_start.py` calls `live_content()`.
- In `tests/specify_cli/session_presence/test_manager.py`, tests that assert live health through `_build_content()` are stale pins: re-target them to `live_content()`. Tests patching `_build_content` for the hook (`test_session_start.py`, `test_open_ops.py`) patch `live_content` instead.

## Test commands

```bash
.venv/bin/python -m pytest tests/specify_cli/session_presence tests/specify_cli/identity tests/specify_cli/cli/commands/test_session_start.py -q
.venv/bin/ruff check <changed> && .venv/bin/ruff format --check --force-exclude <changed> && .venv/bin/mypy <changed src>
```

## Definition of Done

- T001 tests fail on the base and pass after the change.
- No migration module edited; ruff/format/mypy clean; complexity ≤ 15.

## Reviewer guidance

Verify the slug never falls back to the directory name, committed health is constant, the hook still shows live health, and no migration file changed.
