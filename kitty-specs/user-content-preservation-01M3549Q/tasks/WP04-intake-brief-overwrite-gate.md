---
work_package_id: WP04
title: intake brief overwrite gate keys on existence (#4910)
dependencies: []
requirement_refs:
- FR-005
planning_base_branch: fix/user-content-preservation
merge_target_branch: fix/user-content-preservation
branch_strategy: Planning artifacts for this mission were generated on fix/user-content-preservation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/user-content-preservation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-user-content-preservation-01M3549Q
base_commit: 597b095bc3dfee61670be7e2020a8fb487e445a0
created_at: '2026-09-22T18:42:56.375912+00:00'
subtasks:
- T013
- T014
- T015
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/intake.py
create_intent:
- tests/regressions/test_issue_4910_intake_brief_overwrite_gate.py
execution_mode: code_change
model: claude-sonnet
owned_files:
- src/specify_cli/cli/commands/intake.py
- tests/specify_cli/cli/commands/test_intake.py
- tests/regressions/test_issue_4910_intake_brief_overwrite_gate.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load **python-pedro** via `/ad-hoc-profile-load` (profile YAML), then return.

## Objective

`spec-kitty intake <doc>` silently overwrites a hand-authored `.kittify/mission-brief.md`
whenever the provenance sidecar `.kittify/brief-source.yaml` is absent (#4910), because the
overwrite gate ANDs both files' existence. Make the gate key on the **brief's existence
alone** at BOTH entry points. This is a pure refuse-without-`--force` gate — **no backup**
(hybrid contract: user-driven, `--force` is the natural escape).

## Ground truth (verified on main@d57619a900)

- `cli/commands/intake.py:296` (explicit/stdin) and `:156` (`--auto`):
  `if brief_path.exists() and _source_path.exists() and not force:` — the `and` lets a
  missing sidecar bypass the refusal; `_commit_brief` → `write_mission_brief` (`:132`) then overwrites.
- With both files present the refusal already works (exit 1, `Use --force to overwrite`).

## Subtasks

### T013 — [RED FIRST] Regression repro
`tests/regressions/test_issue_4910_intake_brief_overwrite_gate.py` (`@pytest.mark.regression`),
real CLI:
- brief present, sidecar absent, explicit `intake <doc>` (no `--force`) → exit non-zero, `Use --force`, brief byte-identical. (RED on base.)
- same via the `--auto` entry point → same refusal (RED on base — the second site).
- **anchors (green-on-base)**: `--force` overwrites; both files present already refuses.
Capture RED output; commit tests first.

### T014 — Fix both gates
- Drop the `and _source_path.exists()` conjunct at `:296` and `:156` so the gate is `if brief_path.exists() and not force:`.
- Treat a missing sidecar as "unknown provenance ⇒ refuse", per the issue's Expected.

### T015 — Message + `--force`
- Keep the existing `Brief already exists … Use --force to overwrite.` message and exit code; ensure `--force` still overwrites and recreates the sidecar.

## Branch strategy

Planning base + merge target `fix/user-content-preservation`; PR later to upstream `main`. Worktree per lane from `lanes.json`.

## Definition of Done

- Regression RED on base, GREEN on fix; both entry points fixed; anchors green.
- No backup logic added (pure refuse gate).
- mypy --strict + ruff clean; complexity ≤ 15.
- Targeted tests: `PWHEADLESS=1 .venv/bin/python -m pytest tests/regressions/test_issue_4910_*.py tests/specify_cli/cli/commands/test_intake.py -q` — record counts.

## Reviewer guidance (reviewer-renata, opus)

- BOTH `:296` and `:156` patched (a one-site fix leaves `--auto` clobbering).
- No backup wiring crept in; the fix is the gate only.
