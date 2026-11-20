---
type: reference
updated: 2026-11-20
---

# Code grounding: #7729 (project-local CODEX_HOME exposed by the rc8 agent-gitignore narrowing)

Audience: the implementer and the independent reviewer of this Mission. Verified against
`origin/main` at `cfa68136` (PR #7770, which added the red-first reproduction).

## Root-cause citations, re-verified

| Issue claim | Current location | Verdict |
|---|---|---|
| `LEGACY_AGENT_ENTRIES` includes `.codex/` and `.cursor/` | `src/specify_cli/upgrade/migrations/m_4_0_0rc8_narrow_agent_gitignore.py:47-72` | Holds (`.codex/` at :50, `.cursor/` at :58) |
| `_classify` / `_is_owned` remove them in Spec Kitty's marked run | same file `:117-151` | Holds |
| `_plan` writes the managed block through `replace_agent_block` | same file `:193-213`; `src/specify_cli/gitignore_manager.py:43-77` | Holds. The block content is computed **live** by `agent_ignore_entries` (`:210`), as the module docstring says (`:20-22`). |
| Protected Codex paths are `_SECRET_ENTRIES` | `src/specify_cli/agent_utils/ignore_entries.py:51-60` (comment `:48-50`) | Holds: only `auth.json`, `history.jsonl`, `sessions/`, `log/` |
| The newly-visible warning is computed in the upgrading clone only | rc8 module `:216-238` (`_newly_visible`, `_visibility_warning`), called only after a write at `:284-290` | Holds; nothing re-checks after a pull |
| `test_ignore_entries.py:260` pins `.codex/config.toml` as not ignored | `tests/specify_cli/agent_utils/test_ignore_entries.py:257` | Holds (line drifted by 3) |

## Key facts that shape the fix

1. **The committed block follows the live entry list.** `agent_ignore_entries` feeds both the rc8
   migration and `GitignoreManager.sync_agent_block` (`gitignore_manager.py:560-585`). Every
   `spec-kitty upgrade` refreshes an existing block in its finalizer
   (`cli/commands/upgrade.py:1673-1684`, `_refresh_agent_ignore_block`), as do skill installs
   (`skills/installer.py:1351`) and surface repair (`tool_surface/repair.py:575`). So widening
   `_SECRET_ENTRIES` reaches every project on its next upgrade **without editing the shipped
   rc8 module** (DIRECTIVE_044).
2. **The committed block must be the same in every clone** (`ignore_entries.py:157-158`: "every
   clone on one CLI version writes the same committed block"). A block that depended on local
   files (option b) would flip between a clone with a Codex home and one without on every
   upgrade. A per-clone decision therefore belongs in `.git/info/exclude`, not `.gitignore`.
3. **Clone-local migrations re-run in every clone.** A migration with `clone_local_effect = True`
   records into the gitignored `.kittify/migrations/clone-local.jsonl` (CLAUDE.md, Migration
   Ledger Model), so a clone that pulls an upgraded commit still has it pending. The pattern for a
   `.git/info/exclude` writer is `m_4_0_0rc7_exclude_spec_kitty.py` through
   `core/git_ops.py:232-285` (`git_exclude_file`, `exclude_from_git_index`, common-dir aware).
4. **A pulled clone is not nudged to upgrade by version.** The compat planner blocks for a project
   migration only on a STALE/LEGACY project version (`compat/planner.py:404-407`); a pulled clone
   whose committed metadata already reads the new version is not STALE. Pending clone-local
   migrations are applied when that clone runs `spec-kitty upgrade` (and shown by
   `upgrade --dry-run` and `spec-kitty migrate ledger`). A clone that never runs `upgrade` is
   protected only by the committed block.
5. **The upgrade target reaches `4.0.0rc9`.** `pyproject.toml` is `4.0.0rc9`; the latest tag is
   `v4.0.0rc8`, so a `target_version = "4.0.0rc9"` migration is in scope for the installed CLI.

## Invariants that must survive

- The shipped rc8 module stays byte-identical (DIRECTIVE_044; its `content_hash` is recorded).
- Team files in agent folders stay visible in a plain project folder: `.claude/settings.json`,
  `.claude/rules/`, `.kiro/steering/`, `.agents/skills/<team skill>/`, and `.codex/config.toml`
  when `.codex/` is not a Codex home (`test_ignore_entries.py:243-258`).
- The committed block is deterministic: same inputs, same block (`agent_ignore_entries`).
- An operator's own ignore rules are never removed; ownership-unproven files are never deleted
  (charter, User Customization Preservation).
- A clone-local `apply()` is idempotent.

## Gates and test seams

- `tests/architectural/test_migration_order_manifest.py`: every registered migration appears once,
  version-monotonic.
- `tests/specify_cli/upgrade/test_requires_git_repository_audit.py`: callers of
  `resolve_canonical_repo_root` must declare `requires_git_repository` (the new migration does not
  call it).
- `tests/specify_cli/upgrade/test_migrate_ledger_cmd.py`, `test_registry_runs_first.py`: ledger and
  manifest readers.
- `tests/architectural/test_lifted_root_gitignore_contract.py`: root `.gitignore` contract (no
  Codex rows; unaffected).
- `tests/architectural/test_no_tmp_paths_in_tests.py`: a literal Codex `tmp` path in a test must be
  spelled split (the reproduction already does).
- Seams: `tests/specify_cli/agent_utils/test_ignore_entries.py` (`_is_ignored`, `protect_all_agents`),
  `tests/specify_cli/upgrade/migrations/test_m_4_0_0rc8_narrow_agent_gitignore.py`,
  `tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py` (`MigrationRunner(...).upgrade`
  with a ledger that settles every other migration).

## 90-day churn

`git log --since=90.days` over `ignore_entries.py`, the rc8 module and `gitignore_manager.py` shows one
commit (`81dd4989`, test-fixture path flavor, #4058). The surfaces are stable; the rc8 module arrived
with #6474 / PR #6594.
