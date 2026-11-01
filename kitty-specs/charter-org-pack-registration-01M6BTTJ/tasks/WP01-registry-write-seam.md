---
work_package_id: WP01
title: Registry write seam for charter_packs.org.packs
dependencies: []
requirement_refs:
- FR-002
- FR-007
- FR-008
- NFR-001
- NFR-002
- C-001
- C-002
planning_base_branch: issue-6267-charter-org-pack-registration
merge_target_branch: issue-6267-charter-org-pack-registration
branch_strategy: Planning artifacts for this mission were generated on issue-6267-charter-org-pack-registration. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6267-charter-org-pack-registration unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-org-pack-registration-01M6BTTJ
base_commit: b73b0fb1bd01cab82d3b172383d1b7e8b18ad9a2
created_at: '2026-11-01T15:20:15.903096+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundational
history:
- at: '2026-11-01T15:20:00Z'
  actor: planner-priti
  action: 'Prompt generated via planning artifacts for #6267'
agent_profile: python-pedro
authoritative_surface: src/charter/offering/drg/org_pack_config.py
create_intent:
- tests/charter_offering/drg/test_org_pack_config_write_seam.py
execution_mode: code_change
model: deepseek-v4.1-flash-1017
owned_files:
- src/charter/offering/drg/org_pack_config.py
- tests/charter_offering/drg/test_org_pack_config_write_seam.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Registry write seam for `charter_packs.org.packs`

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

## Objectives & Success Criteria

- `src/charter/offering/drg/org_pack_config.py` owns BOTH the read and the write of the
  `charter_packs.org.packs` shape: `register_org_pack(repo_root, pack, *, replace=False)` and
  `unregister_org_pack(repo_root, name)`.
- A strict read happens before any mutation, so a config that cannot be read is never rewritten.
- Writes are atomic (`kernel.atomic.atomic_write`) and preserve comments, quoting, key order and
  every unrelated block; add→remove restores the file byte-for-byte.
- Removing the last entry cleans up the empty `org.packs` / `org` / `charter_packs` scaffolding
  without touching sibling keys.

## Context & Constraints

- Spec: `kitty-specs/charter-org-pack-registration-01M6BTTJ/spec.md` (FR-002, FR-007, FR-008,
  NFR-001, NFR-002, C-001, C-002).
- Plan: `kitty-specs/charter-org-pack-registration-01M6BTTJ/plan.md` (Design decisions 1, 2, 8).
- Charter: `.kittify/charter/charter.md` — single canonical authority; no second schema; the
  `charter ↛ specify_cli` boundary means the write primitive comes from `kernel.atomic`.
- Reuse the module's existing `_yaml()` round-trip settings and its `OrgPackConfig` /
  `PackRegistry` models. No new config keys, ever (C-001).

## Branch Strategy

- **Strategy**: `issue-6267-charter-org-pack-registration`
- **Planning base branch**: `main`
- **Merge target branch**: `main`

## Subtasks & Detailed Guidance

### Subtask T001 – Failing seam tests first

- **Purpose**: prove the seam can fail before it exists.
- **Steps**: create
  `tests/charter_offering/drg/test_org_pack_config_write_seam.py` with markers
  `pytest.mark.unit` / `pytest.mark.fast` and a `tmp_path` project fixture that writes a
  `.kittify/config.yaml` carrying comments and two unrelated sections. Assert:
  (a) `register_org_pack` appends the entry and leaves the comments in place;
  (b) `register_org_pack(..., replace=True)` replaces in place and keeps declaration order;
  (c) `unregister_org_pack` removes exactly one entry and the add→remove round-trip is byte-identical
  (compare `read_bytes()`);
  (d) removing the last entry drops the empty scaffolding;
  (e) a malformed existing org block raises and the file is byte-identical afterwards;
  (f) an injected write failure (monkeypatch `kernel.atomic.atomic_write` at the module's import
  site to raise) leaves the original bytes intact.
- **Files**: `tests/charter_offering/drg/test_org_pack_config_write_seam.py`
- **Parallel?**: yes, alongside T002.
- **Notes**: run the file and record the red output before implementing.

### Subtask T002 – `register_org_pack`

- **Purpose**: the canonical add.
- **Steps**: read the registry strictly; build the `CommentedMap` entry from the pydantic model's
  fields **only when set** (`name`, `local_path` always; `subdir`, `source_type`, `url`, `ref` when
  present); append, or replace in place when `replace=True`; if the name exists and
  `replace=False`, raise `ValueError` naming the pack and `--force`.
- **Files**: `src/charter/offering/drg/org_pack_config.py`
- **Notes**: `local_path` is stored exactly as the operator wrote it (never expanded).

### Subtask T003 – `unregister_org_pack`

- **Purpose**: the canonical remove.
- **Steps**: strict read; unknown name raises `ValueError` listing configured names; delete the one
  entry; when `org.packs` is empty remove `org`; when `charter_packs` is empty remove it; return the
  removed `OrgPackConfig`.
- **Notes**: only drop parents that are actually empty; sibling keys survive.

### Subtask T004 – Format-preserving atomic write

- **Purpose**: one writer, no truncation.
- **Steps**: dump with `YAML()` configured exactly like `_yaml()` (preserve_quotes, indent 2/4/2),
  render to a `StringIO`, and write the text through `kernel.atomic.atomic_write(path, text,
  mkdir=True)`.
- **Notes**: no temp file hand-rolling; `kernel.atomic` already handles Windows read-only targets.

### Subtask T005 – Public seam bookkeeping

- **Purpose**: keep the module's public surface honest.
- **Steps**: extend `__all__`, extend the module docstring with the write half, and confirm the
  runtime loader's behaviour is unchanged (no new read path).

## Test Strategy

```bash
uv run pytest tests/charter_offering/drg/test_org_pack_config_write_seam.py -q
uv run pytest tests/charter_offering/drg -q -x -k "org_pack_config"
uv run ruff check src/charter/offering/drg/org_pack_config.py tests/charter_offering/drg/test_org_pack_config_write_seam.py
uv run mypy src/charter/offering/drg/org_pack_config.py
```

## Risks & Mitigations

- ruamel reformatting unrelated blocks → byte-round-trip assertions, not semantic equality.
- Deleting a parent block that still has siblings → only remove when empty.
- Dead-code ratchet → both functions are consumed by WP02 in the same PR.

## Review Guidance

- Confirm the write cannot be reached with an unreadable config.
- Confirm no second schema/parser appeared and `local_path` stays verbatim.
