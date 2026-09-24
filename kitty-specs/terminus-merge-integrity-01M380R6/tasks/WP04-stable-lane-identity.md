---
work_package_id: WP04
title: Stable, origin-aware lane identity (C-4)
dependencies: []
requirement_refs:
- FR-010
planning_base_branch: fix/terminus-merge-integrity
merge_target_branch: fix/terminus-merge-integrity
branch_strategy: Planning artifacts for this mission were generated on fix/terminus-merge-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/terminus-merge-integrity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-terminus-merge-integrity-01M380R6
base_commit: dc2463d1d787363ce665a6b0e9c1f3e2efb6f87b
created_at: '2026-09-23T22:19:32.747168+00:00'
subtasks:
- T016
- T017
- T018
- T019
- T020
phase: Phase 2 - Parallel fan (file-isolated)
history:
- at: '2026-09-23T21:36:42Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/compute.py
create_intent:
- tests/lanes/test_lane_identity.py
execution_mode: code_change
owned_files:
- src/specify_cli/lanes/compute.py
- src/specify_cli/workspace/context.py
- tests/lanes/test_lane_identity.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Stable, origin-aware lane identity (C-4)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (frontmatter) before parsing the rest of
this prompt, and behave according to its guidance.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

Apply the resolved boundaries and TDD discipline. State what you applied, then continue.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use fenced code-block language identifiers.

---

## Objectives & Success Criteria

Bind a lane's identity to its git branch at creation so a WP removal + re-finalize never re-letters a
surviving lane into a different WP's code, and consult `origin/<lane>` before cutting fresh. Success
(FR-010; traces #4945 #4969):

- A lane's `lane_id` is minted **once at creation** (stable), not re-derived positionally on every
  finalize.
- Finalize **reads back** the bound id — positional lettering never overwrites a bound id (PP-F5).
- Base resolution prefers `origin/<lane>` over a fresh cut from local main.

## Context & Constraints

- Spec: [../spec.md](../spec.md) US4 scenario 2, FR-010. Research D9; DEBRIEF §3 C-4, §4 (#4945/#4969).
  Post-plan disposition PP-F5 ([../research.md](../research.md)): **confirm finalize reads back the
  minted id, not also-mints**.
- **Grounded anchors** (verify in-tree; names are the durable anchors):
  - Positional lettering `lane_id = f"lane-{chr(lane_letter)}"` ≈ `lanes/compute.py:536` (inside the
    ≈ `:515-537` region that re-runs every finalize). The `LaneAssignment`/lane dataclass carries
    `lane_id` ≈ `:76`.
  - `workspace/context.py` resolves the execution workspace / lane base (`resolve_workspace_for_wp`
    and the branch/base helpers).
- Data model: [../data-model.md](../data-model.md) `LaneIdentity` (stable `lane_id`, `branch`,
  `base_ref` consulting `origin/<lane>`).
- Locality (C-004): only `lanes/compute.py`, `workspace/context.py`, + the new test. The
  `implement._validate_base_ref` origin site is owned by WP03 — coordinate, don't touch it here.

## Branch Strategy

- **Strategy**: file-isolated parallel-fan — start immediately.
- **Planning base branch / Merge target branch**: `fix/terminus-merge-integrity`.

## Subtasks & Detailed Guidance

### T016 – Red: stable id across re-finalize + origin-aware base
- **Purpose**: reproduce #4945 (re-lettering) and #4969 (origin shadowing) (TDD red).
- **Steps**: create `tests/lanes/test_lane_identity.py`.
  1. Build a mission with lanes A/B/C bound to git branches; **remove** a middle WP and re-run the
     finalize/compute path. Assert every surviving lane keeps its original `lane_id` (fails today:
     positional re-lettering shifts ids, so a surviving lane inherits a removed WP's slot → #4945).
  2. Create a lane that exists only as `origin/<lane>`; drive base resolution and assert it resolves
     to the origin ref, not a fresh cut from local main (fails today → #4969).
- **Files**: `tests/lanes/test_lane_identity.py`.

### T017 – Fix: mint stable `lane_id` once at creation
- **Purpose**: identity bound to branch at creation, not position (D9).
- **Steps**: in `compute.py`, at lane creation, mint a stable `lane_id` (bound to the lane's git
  branch — e.g. derived from the branch name / a minted token, persisted into `lanes.json`) and store
  it on the lane dataclass (≈ `:76`). Do not derive it from `chr(lane_letter)` at creation.
- **Files**: `src/specify_cli/lanes/compute.py`.
- **Notes**: keep the change localized; do not restructure the whole compute pipeline (DIRECTIVE_024).

### T018 – Fix: read back the bound id on finalize (never re-letter over a bound id)
- **Purpose**: PP-F5 — finalize must READ BACK, not also-mint.
- **Steps**: at the ≈ `:515-537` finalize region, when a lane already carries a persisted `lane_id`,
  reuse it verbatim; only mint for genuinely new lanes. Positional `chr(...)` lettering ≈ `:536` may
  remain a fallback **only** for never-before-seen lanes, and must never overwrite a bound id.
- **Files**: `src/specify_cli/lanes/compute.py`.
- **Notes**: add a focused test that a bound id survives a finalize that would otherwise re-letter it.

### T019 – Fix: origin-aware base in `workspace/context.py`
- **Purpose**: prefer `origin/<lane>` when resolving a lane's base workspace.
- **Steps**:
  1. In the lane-base resolution path (near `resolve_workspace_for_wp` and its branch/base helpers),
     before cutting a fresh branch from local main, probe for `origin/<lane>`
     (`git rev-parse --verify --quiet refs/remotes/origin/<lane>`).
  2. When the origin ref exists, use it as the base so a teammate's pushed approved lane is not
     shadowed by a fresh cut from local main (#4969).
  3. When it does not exist (offline / no remote / never pushed), fall back to the existing
     local-cut behavior — do not fail closed here (this is base resolution, not a terminus write).
  4. Mirror the exact semantics WP03 applies in `implement._validate_base_ref` so the two sites agree;
     flag any divergence to WP03 rather than diverging silently.
- **Files**: `src/specify_cli/workspace/context.py`.
- **Notes**: name the `primary`/`merge`/`routing` senses if any appear in touched comments (C-005).

### T020 – Verify red→green + gates
- **Steps**: confirm RED→GREEN; run `PWHEADLESS=1 .venv/bin/python -m pytest tests/lanes/ -q` plus
  any `workspace` tests (`grep -rl "resolve_workspace_for_wp\|lane_id" tests/`); paste output.
  `ruff check` + `ruff format --check` + `mypy src/specify_cli/lanes/compute.py
  src/specify_cli/workspace/context.py` clean.

## Test Strategy

- `tests/lanes/` is the owning subsystem — run in full plus the new identity test and workspace tests.
- Compiler gate on both typed sources.

## Risks & Mitigations

- **PP-F5 trap**: finalize that *also-mints* instead of reading back reopens #4945 — T018 forbids it.
- **Origin ref absent** (offline / no remote): fall back to the existing local-cut behavior only when
  `origin/<lane>` genuinely does not exist.

## Definition of Done

- `test_lane_identity.py` RED on the mission base, GREEN on the fix; WP01's #4945/#4969 repros flip
  GREEN.
- A surviving lane keeps its original `lane_id` across a WP-removal re-finalize (no positional shift).
- Finalize reads back a bound id; positional lettering is a fallback for never-before-seen lanes only.
- Base resolution prefers `origin/<lane>` and falls back to local-cut only when the origin ref is
  genuinely absent.
- `ruff check` + `ruff format --check` + `mypy src/specify_cli/lanes/compute.py
  src/specify_cli/workspace/context.py` clean; no new `# type: ignore`.

## Review Guidance

- Confirm a surviving lane keeps its id across a WP-removal re-finalize.
- Confirm finalize reads back the bound id rather than re-minting positionally (PP-F5).
- Confirm base resolution prefers `origin/<lane>` with a sound offline fallback.
- Confirm the origin semantics match WP03's `_validate_base_ref` site.

## Activity Log

> **CRITICAL**: chronological order, append to END, current UTC time.

- 2026-09-23T21:36:42Z – system – Prompt created.

### Updating Status

`spec-kitty agent tasks move-task WP04 --to <lane>`.
