---
work_package_id: WP02
title: Global asset preparation primitives
dependencies: []
requirement_refs:
- FR-007
- FR-008
planning_base_branch: issue-7700-skill-surfaces-converge
merge_target_branch: issue-7700-skill-surfaces-converge
branch_strategy: Planning artifacts for this mission were generated on issue-7700-skill-surfaces-converge. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7700-skill-surfaces-converge unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-skill-surfaces-converge-01M7VRS0
base_commit: 4a9e8eb6d3d90813edcd75c87c066a0de38b105d
created_at: '2026-11-20T06:51:17.372410+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Foundation
history:
- at: '2026-11-20T07:00:00Z'
  actor: claude::planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/runtime/
create_intent:
- tests/runtime/test_global_asset_inventory_anchor.py
- tests/runtime/test_asset_preparation_retire_proof.py
- docs/changelog/unreleased/7722.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/runtime/asset_preparation.py
- tests/runtime/test_global_asset_inventory_anchor.py
- tests/runtime/test_asset_preparation_retire_proof.py
- docs/changelog/unreleased/7722.fixed.md
- src/specify_cli/runtime/agent_skills.py
- src/specify_cli/runtime/agent_commands.py
- tests/runtime/test_build_serialized.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Global asset preparation primitives

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Record status moves as `claude::python-pedro` (no model name).

---

## Review Feedback

Check `review_ref` in the event log. Address every item before handing back.

## Objectives & Success Criteria

- The global asset inventory (`~/.kittify/cache/<owner>-assets.json`) stays valid when one user-global root moves outside `$HOME` (#7722). Applies to all three owners: `global_skills`, `slash_commands`, `runtime_bootstrap`.
- Schema-1 inventories keep resolving and are rewritten once as schema 2.
- `AssetPreparation.retire()` can accept a caller-supplied byte proof for a file with no inventory record (used by WP03 for retired skills).

## Context & Constraints

- Plan IC-05, research R-3, data-model "Global asset inventory".
- Today: `global_asset_root` anchors on `commonpath(home, *roots).parent`; `AssetPreparation.__init__` loads anchor-relative keys; `finish()` writes schema 1. In-memory semantics (`self.previous`/`self.entries` keyed anchor-relative) must stay, so `asset`, `retire`, `prune_missing`, `backup` and `agent_commands._retire_antigravity_workflows` (which reads `prepared.previous`) are unchanged.
- Never widen proof: a migrated key that cannot be placed is dropped from proof (the file is then judged by today's unproven path), never guessed onto another file.

## Branch Strategy

Populated by finalize-tasks. Planning base and merge target: `issue-7700-skill-surfaces-converge` via the Mission branch `kitty/mission-skill-surfaces-converge-01M7VRS0`.

```bash
spec-kitty agent action implement WP02 --agent claude --mission skill-surfaces-converge-01M7VRS0
```

## Subtasks & Detailed Guidance

### Subtask T006 – Red tests

- `tests/runtime/test_global_asset_inventory_anchor.py` (real files, isolated `HOME`):
  1. `test_moved_root_keeps_other_roots_proven`: build an `AssetPreparation` with roots under home, `asset()` a file under `~/.agents/skills/x/SKILL.md`, apply/persist the inventory (simplest: call `finish()` and write the inventory bytes from the effect, or run `assess_global_agent_skills` + `apply_assets` end to end with a tiny selection). Then set `CLAUDE_CONFIG_DIR` to a dir outside home (`tmp_path/"outside"`), re-assess; the same unchanged file must be `unchanged` (owned), not `preserve`/"Unproven existing asset". Then change the canonical bytes: the owned file is refreshed (effect), not preserved.
  2. `test_schema1_inventory_migrates_once`: hand-write a schema-1 inventory relative to `home.parent`, re-assess with a moved root: entries still prove ownership; the written inventory is schema 2 with absolute keys.
  3. `test_unplaceable_schema1_key_is_not_proof`: a schema-1 key that resolves under no candidate is not used as proof.
- `tests/runtime/test_asset_preparation_retire_proof.py`:
  4. `test_retire_with_byte_proof_removes_unrecorded_file`: no inventory record, proof callable returns True for the file's digest → removal effect with `OwnershipProof("canonical_content", ...)`.
  5. `test_retire_with_failing_proof_preserves_and_reports`: proof False → `preserve` disposition, no effect, bytes unchanged.
  6. `test_retire_directory_partially_proven_preserves_directory`.
- Commit red tests alone first.

### Subtask T007 – Schema 2

- In `__init__`: accept `schema_version` 1 or 2. For 2: each key must be an absolute POSIX path with no `..`/`.` segments; convert to anchor-relative when under `self.root.path` (store in `self.previous`), else keep it in `self._foreign_entries` (carried through untouched on write).
- In `finish()`: write schema 2: `{root.path / rel: state}` as POSIX strings, merged with `_foreign_entries`. Write when the serialized bytes differ from what was read (so a schema-1 file is rewritten once even when entries are equal).
- Windows: `PureWindowsPath` absolute keys like `C:/Users/...` — use `Path(key).is_absolute()` after `as_posix()`; keep validation free of `:` rejection for schema 2 only.

### Subtask T008 – Schema-1 migration

- Candidates: ancestors of `_normalized(Path.home())` from deepest (`home.parent`) up to the filesystem anchor, then the current anchor. For each key take the first candidate where `candidate / key` lies under `$HOME`, the kittify home (`get_kittify_home()`), or one of the owner's current roots. Pass the "known roots" into `AssetPreparation` via an optional constructor argument `known_roots: tuple[Path, ...] = ()` that callers already have (`global_asset_root` inputs); default keeps today's behaviour for any other caller.
- Unplaceable keys: drop (log at debug).

### Subtask T009 – `retire()` byte proof

- Signature: `retire(self, path: Path, *, proven: Callable[[Path, str | None], bool] | None = None) -> bool`. When no inventory record exists (or it doesn't match) and `proven(path, before.sha256)` is True for a regular file, remove it with `OwnershipProof("canonical_content", f"{owner}:{relative}:historical-render")`. Directories recurse passing `proven`. Symlinks are never proven by bytes.
- Disposition reasons stay as today for the unproven case ("Unproven or edited retired asset").

### Subtask T010 – Changelog fragment

- `docs/changelog/unreleased/7722.fixed.md`: one entry, Before/After style (see `docs/changelog/unreleased/README.md`); run the two style checks it names.

## Test Strategy

```bash
uv run --frozen pytest -q tests/runtime/test_global_asset_inventory_anchor.py tests/runtime/test_asset_preparation_retire_proof.py tests/runtime/ tests/specify_cli/runtime/
```

## Risks & Mitigations

- Many tests assert disposition paths relative to the anchor: in-memory keys stay anchor-relative, so they should not change. Run `tests/runtime/` and `tests/specify_cli/runtime/` fully.
- `check_assets`/`recheck` compare written inventory bytes: they use the effect's content, unaffected.

## Review Guidance

- Red→green; no behaviour change when no root moves (byte-identical dispositions on the existing suites); schema-1 files rewritten exactly once.
