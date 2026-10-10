---
work_package_id: WP08
title: Migrate CLI charter consumers
dependencies:
- WP01
requirement_refs:
- FR-002
planning_base_branch: kitty/org-pack-chain-authority-stack
merge_target_branch: kitty/org-pack-chain-authority-stack
branch_strategy: Planning artifacts for this mission were generated on kitty/org-pack-chain-authority-stack. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/org-pack-chain-authority-stack unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-org-pack-chain-authority-01M4JXF5
base_commit: aecea293a63521db043008c55df8a32f126cb3b4
created_at: '2026-10-10T14:30:07.535018+00:00'
subtasks:
- T010
- T011
- T037
phase: Phase 2 - Migration
history:
- at: '2026-10-10T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/deactivate.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/charter/deactivate.py
- src/specify_cli/cli/commands/charter/_resynthesis_preflight.py
- src/specify_cli/cli/commands/charter/interview.py
- src/specify_cli/cli/commands/charter/context.py
- src/specify_cli/cli/commands/charter/pack_asset.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Migrate CLI charter consumers

## ⚡ Do This First: Load Agent Profile

Use `/spk-charter-profile-load` to load the frontmatter profile first.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Route the `src/specify_cli/cli/commands/charter/` chain consumers through `resolve_pack_chain()` so the WP06 path-scoped gate is green. Behaviour-preserving, lenient swaps (plus one re-point of the #6005 `context.py` reader).

Done when `deactivate`, `_resynthesis_preflight`, `interview`, `context`, and `pack_asset` source their org chain from `resolve_pack_chain(strict=False)`, behaviour is unchanged, the charter-CLI suites stay green, and ruff/mypy are clean.

## Context & Constraints

Spec: FR-002. Depends on **WP01**. All lenient (`strict=False`).

Migration map (verified file:line):
- `deactivate.py`: `:179` and `:337` `resolve_org_root_chain(repo_root)` → `resolve_pack_chain(strict=False)`. (The import at :60 and the docstring at :95 update accordingly.)
- `_resynthesis_preflight.py`: `:75` `resolve_org_root_chain(repo_root)` → `resolve_pack_chain(strict=False)`.
- `interview.py`: `:90` `resolve_org_root_chain(repo_root)` (import at :86) → `resolve_pack_chain(strict=False)`.
- `context.py`: `:86` `[p for p in resolve_org_roots(repo_root) if p.exists()]` → `resolve_pack_chain(repo_root, strict=False)`. **Re-point only** — do NOT alter the `--include` body-selection logic #6005 already fixed.
- `pack_asset.py`: `:91` `[root for root in resolve_org_roots(repo_root) if root.exists()]` → `resolve_pack_chain(repo_root, strict=False)`.

Note: `_cascade_shared.py` only mentions `resolve_org_root_chain` in a docstring (no call); the call-based WP06 gate does not flag it, so it is not owned here.

## Subtasks

### T010 — `deactivate` + `_resynthesis_preflight`
Swap the `resolve_org_root_chain` calls to the lenient authority; fix the import and docstring references.

### T011 — `interview` + `context` (re-point) + `pack_asset`
Swap `interview` and `pack_asset` to the lenient authority; re-point `context.py`'s resolution source without changing its `--include` behaviour (#6005).

### T037 — Quality gates
ruff/mypy clean; confirm the charter-CLI suites stay green:
```bash
.venv/bin/python -m pytest tests/specify_cli/cli/commands/charter/ -q
```

## Test strategy
Pure delegate swaps (behaviour-identical) + one re-point; no new behavioural test warranted. The charter-CLI suites and the WP06 gate are the net. For `context.py`, confirm `tests/specify_cli/cli/commands/charter/test_multi_org_pack_chain_5779.py` stays green (it pins #6005's `--include` behaviour — do not regress it).

## Branch strategy
Planning base / merge target `kitty/org-pack-chain-authority-stack`; worktree per lane from `lanes.json`. Depends on **WP01**.

## Definition of Done
All five files source the chain from `resolve_pack_chain(strict=False)`; `context.py` `--include` behaviour unchanged; charter-CLI suites green; ruff/mypy clean.

## Risks & reviewer guidance
- **Re-fixing `context.py`**: it is already correct (#6005) — only the resolution source changes; reviewer confirms `test_multi_org_pack_chain_5779.py` stays green.
- **Posture**: all lenient; a strict swap would regress these best-effort/display paths.
- **Scope**: WP08 owns only these 5 files.
