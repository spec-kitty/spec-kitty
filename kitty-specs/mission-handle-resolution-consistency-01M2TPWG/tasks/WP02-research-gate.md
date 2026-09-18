---
work_package_id: WP02
title: 'research: existence gate (kill the phantom write)'
dependencies:
- WP01
requirement_refs:
- FR-001
planning_base_branch: issue-4631-4682-mission-handle-resolution
merge_target_branch: issue-4631-4682-mission-handle-resolution
branch_strategy: Planning artifacts for this mission were generated on issue-4631-4682-mission-handle-resolution. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4631-4682-mission-handle-resolution unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
history:
- Created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/research.py
create_intent:
- tests/research/test_research_missing_mission.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/research.py
- tests/research/test_research_missing_mission.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (role: implementer) via `/ad-hoc-profile-load` before anything else.

## Objective

Stop `research --mission <nonexistent>` from scaffolding a phantom `kitty-specs/<handle>/`
directory. It must refuse with the canonical `Mission not found: <handle>` (from WP01) and
change nothing on disk. This is the only data-corruption defect in the mission — highest care.

## Context

- File: `src/specify_cli/cli/commands/research.py`. Today it resolves the mission dir via
  `_read_mission_dir_or_exit` (`research.py:88-90`, guards path-safety only, NO existence
  check) then `planning_dir.mkdir(parents=True, exist_ok=True)` (`research.py:118`) — the
  phantom write. The mkdir runs BEFORE plan validation.
- Exemplar to mirror: `materialize.py:94-99` — resolve, then `if not feature_dir.exists():
  emit "Mission not found: {slug}"; raise typer.Exit(1)`.
- research has **no `--json`** — it is human-only. Do NOT add a JSON surface (out of scope,
  per FR-011). The not-found is a human message + non-zero exit.
- Do NOT modify the lenient `read_dir`/`_read_mission_dir_or_exit` seam; gate in the command.

## Subtasks

### T007 — Red test
Create `tests/research/test_research_missing_mission.py` (add a `pytestmark` marker). Prefer
**in-process `typer.testing.CliRunner`** over the subprocess `run_cli` fixture (avoids
stale-install false-reds + ~90s cost). Stage 2 real missions in a `tmp_path` repo. Snapshot
`sorted(p.relative_to(root) for p in (root/"kitty-specs").rglob("*"))` before; run
`research --mission zznope`; assert: exit non-zero, output contains `Mission not found: zznope`,
snapshot after == before (no `kitty-specs/zznope/`, no `data-model.md`/`research.md`/
`research/evidence-log.csv`/`research/source-register.csv`). Initially fails (dir gets created).

### T008 — Add the existence gate
Immediately after the resolve at `research.py:88-90`, add `.exists()` gating before any
`mkdir`/scaffold (before `:98` re-key and `:115-118`). Model on `materialize.py:94-99`.

### T009 — Emit canonical not-found
On the not-found branch, emit `Mission not found: <handle>` via the WP01 constant and
`raise typer.Exit(1)` — before any filesystem mutation. Preserve the existing path-safety
refusal for `../x` (distinct error, unchanged).

### T010 — Green
T007 passes; confirm manually per quickstart.md that no phantom dir appears. `ruff`/`mypy` clean.

## Definition of Done
- `research --mission <bad>` → `Mission not found: <bad>`, non-zero, zero filesystem change.
- Path-safety and valid-handle behavior unchanged.
- Blast radius: `PWHEADLESS=1 .venv/bin/python -m pytest tests/research/ -q`.

## Branch Strategy
Base/merge target `issue-4631-4682-mission-handle-resolution`; work in the lane worktree from `lanes.json`.

## Reviewer guidance
Verify the gate is BEFORE every mkdir/scaffold call, the message uses the WP01 constant, and
the snapshot assertion actually covers the `research/` subtree (the specific phantom paths).
