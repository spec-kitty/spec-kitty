---
work_package_id: WP02
title: 'Ownership-gate agent command-surface removal + manifest pins (#4907, #2691)'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-014
- FR-015
planning_base_branch: fix/user-content-preservation
merge_target_branch: fix/user-content-preservation
branch_strategy: Planning artifacts for this mission were generated on fix/user-content-preservation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/user-content-preservation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-user-content-preservation-01M3549Q
base_commit: e22f0370509b3c08580f0fbbffb6612b576aa93a
created_at: '2026-09-22T18:40:37.977377+00:00'
subtasks:
- T004
- T005
- T006
- T007
- T008
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/config.py
create_intent:
- tests/regressions/test_issue_4907_agent_config_remove_preservation.py
- tests/regressions/test_issue_2691_agent_config_sync_preservation.py
execution_mode: code_change
model: claude-sonnet
owned_files:
- src/specify_cli/cli/commands/agent/config.py
- src/specify_cli/skills/command_installer.py
- src/specify_cli/skills/manifest_store.py
- tests/specify_cli/cli/commands/test_agent_config.py
- tests/agent/cli/commands/test_agent_config.py
- tests/regressions/test_issue_4907_agent_config_remove_preservation.py
- tests/regressions/test_issue_2691_agent_config_sync_preservation.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load **python-pedro** via `/ad-hoc-profile-load` (the profile YAML, not just the name)
before anything else, then return here.

## Objective

Close the two P0/P1 **removal** defects that share one seam: `agent config remove`
(#4907, P0) rmtree's a user's `.claude/commands/**` (gitignored, unrecoverable) and
`agent config sync` (#2691) does the same via its default-on orphan sweep — both through
`_remove_project_agent_surface` — plus #2691's second half where a normal `sync`
rewrites repository-pinned manifests. Route the removal through the EXISTING
`asset_preservation.guard_destructive_removal` guard (do NOT fork a new authority) and
stop the manifest-pin rewrite.

## Ground truth (verified on main@d57619a900)

- `src/specify_cli/cli/commands/agent/config.py:125-147` `_remove_project_agent_surface`
  carries **THREE** destructive literals: `:137 shutil.rmtree(surface)`, `:139 surface.unlink()`
  (file branch), `:142 root.rmdir()` (empty-only). It returns `(True, "Removed …")`.
- Called from `remove_agents` (`:480`, the `remove` verb) and `_remove_orphaned_agent_dirs`
  (`:234`, the `sync` orphan sweep) — with **identical args** `(repo_root, agent_key)`, so
  ONE routed guard call fixes both.
- `sync_agents` (`:577`): `remove_orphaned` defaults **True** (`--remove-orphaned/--keep-orphaned`), so a bare `sync` sweeps.
- The skill-only branch already preserves via manifest/hash proof (`skills/command_installer.py` → `remove_entry`).
- The guard: `guard_destructive_removal(path, project_path, *, prover, is_tree, backup_parent, dry_run)` (`asset_preservation/guard.py`); `ManifestProver` (`asset_preservation/provers.py`) checks the command-skills manifest and fails closed on mixed/untracked dirs.

## Subtasks

### T004 — [RED FIRST] Regression repros (author + run RED on base, commit before the fix)
Create `tests/regressions/test_issue_4907_agent_config_remove_preservation.py` and
`tests/regressions/test_issue_2691_agent_config_sync_preservation.py`, each marked
`@pytest.mark.regression`, exercising the real CLI through the pre-existing entry point:
- **#4907**: init `--ai claude`; create a user `.claude/commands/my-deploy.md` (no manifest entry); `agent config remove claude` → **must** leave the file present, exit 0, output says "Preserved" (NOT "Removed"). (RED on base: today it's deleted.)
- **#2691 removal**: same setup; bare `agent config sync` → user file preserved.
- **Mixed dir**: a manifest-proven file + a user file in the same subdir → whole dir preserved (no partial rmtree).
- **#2691 manifest**: record `.kittify/command-skills-manifest.json` checksum; bare `sync` → checksum byte-identical; `--json` lists zero tracked mutations. (RED on base: pins rewritten.)
- **owned-delete anchors (green-on-base)**: a genuinely manifest-proven surface IS removed via BOTH `remove` and `sync` — so a preserve-everything fix cannot pass.
- **AGENT_DIRS generality**: repeat the preserve assertion for one non-claude agent subdir (e.g. `.github/prompts/`).

Run them, capture the RED output (DIRECTIVE_030), commit the tests as a separate first commit.

### T005 — Route `_remove_project_agent_surface` through the guard (dir-level)
- Replace the `:137/:139` raw removal with ONE dir-level call:
  `guard_destructive_removal(surface, repo_root, prover=ManifestProver(check_command=True), is_tree=surface.is_dir(), backup_parent=None)`.
  Dir-level (not per-file) is mandatory: the guard's `_prove_dir` gives pure-owned⇒remove-whole and any-unproven⇒preserve-whole — per-file routing would re-enable the partial-rmtree loss class.
- Keep `:142 root.rmdir()` as an empty-only prune AFTER the guard (it becomes a no-op OSError-guarded call when the surface was preserved) — it is allowlisted in WP08, so leave it as the one remaining literal, clearly commented "empty-only prune; guard owns the destructive removal".
- Add an in-code comment documenting the ownership proof (charter L479 / NFR-006).

### T006 — Verdict-driven return + messaging (no false "Removed")
- Drive the return tuple and the `remove_agents` / `_remove_orphaned_agent_dirs` rendering by the `OwnershipVerdict`: `verdict.owned` ⇒ "Removed {surface}"; else surface `verdict.diagnostic` ("Preserved …; not package-owned"), exit 0.
- **Critical**: today `root.rmdir()` raising OSError on a non-empty (preserved) dir is caught and STILL returns "Removed" — fix so a preserved surface never reports removal.

### T007 — Stop `sync` rewriting repository-pinned manifests (#2691 manifest half)
- Locate the manifest writer invoked by the sync path (`skills/command_installer.install` / `skills/manifest_store` via `_register_skill_agent`). Confirm with a brownfield read where the pinned `command-skills-manifest.json` release/hash values get overwritten during a normal sync.
- Make a normal `sync` leave pinned values byte-identical; gate any manifest refresh behind an explicit opt-in (prefer: sync never rewrites pins — a dedicated refresh/install path is the only writer). Ensure `--json` enumerates intended tracked mutations (zero on a non-refreshing sync).
- If the safest fix is "sync does not call the manifest writer at all", do that and add a focused test; document the decision in the tracer.

### T008 — AGENT_DIRS-table generality
- Confirm the routed fix is driven by the `AGENT_DIRS` table (`agent_utils/directories.py`), not special-cased to `claude`, so all 12 command-layer agents' managed subdirs are covered. Add/keep the non-claude assertion from T004.

## Branch strategy

Planning base + merge target `fix/user-content-preservation`; PR later to upstream `main`. Worktree allocated per lane from `lanes.json`.

## Definition of Done

- Both regression files RED on base, GREEN on the fix; owned-delete + AGENT_DIRS anchors green.
- `_remove_project_agent_surface` has no raw `rmtree`/`unlink` (only the allowlisted empty-only `:142 rmdir`); messaging verdict-driven.
- Normal `sync` leaves pinned manifest byte-identical.
- mypy --strict + ruff clean; complexity ≤ 15; no suppression.
- Targeted tests: `PWHEADLESS=1 .venv/bin/python -m pytest tests/regressions/test_issue_4907_*.py tests/regressions/test_issue_2691_*.py tests/specify_cli/cli/commands/test_agent_config.py tests/agent/cli/commands/test_agent_config.py -q` — record counts.

## Reviewer guidance (reviewer-renata, opus)

- No second ownership authority; the ONE guard performs the delete.
- Dir-level routing (no partial rmtree on a mixed dir); verify with the mixed-dir test.
- No "Removed" printed on a preserved surface (the load-bearing FR-015 check).
- Manifest byte-identical on a normal sync; `--json` mutation enumeration.
- WP08 will pin config.py into the census — leave `:142` as the single, clearly-commented empty-only literal.
