---
work_package_id: WP03
title: 'Capstone: honest-failure + e2e + CHANGELOG'
dependencies:
- WP01
- WP02
requirement_refs:
- FR-009
- NFR-001
planning_base_branch: fix/tool-surface-projection-fidelity
merge_target_branch: fix/tool-surface-projection-fidelity
branch_strategy: Planning artifacts for this mission were generated on fix/tool-surface-projection-fidelity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/tool-surface-projection-fidelity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-tool-surface-projection-fidelity-01M2Z1T7
base_commit: 27d50f50fbd1833cd856a785fba55aa6ce86d758
created_at: '2026-09-20T11:15:32.428408+00:00'
subtasks:
- T013
- T014
- T015
phase: Phase 2 - Integration
history:
- at: '2026-09-20T06:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/tool_surface/integration/
create_intent:
- tests/specify_cli/tool_surface/integration/test_projection_honesty_e2e.py
execution_mode: code_change
model: ''
owned_files:
- CHANGELOG.md
- tests/specify_cli/tool_surface/integration/test_projection_honesty_e2e.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Capstone: honest-failure + e2e + CHANGELOG

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (implementer) before parsing the rest of this prompt.

---

## Objectives & Success Criteria

Prove the honesty invariant and SC-001..006 end-to-end across both seams, and record the change. This lane has WP01+WP02 merged in.

Done when:
- **Honest failure (FR-009)**: a selected, detected-stale surface that repair genuinely cannot write is reported `failed`/non-zero, never exit-0 silent.
- **e2e (SC-001..006)**: GEMINI.md + LLXPRT.md refresh with no harness dir (Seam A); Windows-simulated single-pass `upgrade` convergence + zero phantom `--dry-run` repairs (Seam B); POSIX correctness intact.
- **CHANGELOG** `[Unreleased]` Fixed entry; no version bump.

## Context & Constraints

- Depends on WP01+WP02 merged. Verify the shared helpers each WP introduced are genuinely wired (integration gate has historically caught dead-shared-helpers).
- Blast radius (record commands + counts in the PR *Tests run* section): `tests/specify_cli/session_presence/ tests/specify_cli/tool_surface/ tests/specify_cli/skills/` + `make test-fast`. Run `tests/architectural/` only if a gate fires.
- CHANGELOG lives at `docs/changelog/CHANGELOG.md` (symlinked from `CHANGELOG.md` — edit the real target). Append under the EXISTING `[Unreleased]` heading; do NOT add a version heading or touch `pyproject.toml`/`uv.lock`/`.kittify/metadata.yaml`.

## Subtasks

### T013 — Honest-failure path
e2e assertion: a selected+stale+truly-unwritable surface produces a `failed`/non-zero outcome naming the file — never `skipped`/exit-0 (FR-009). (Simulate unwritability, e.g. patch the write to raise.)

### T014 — e2e over both seams
Create `tests/specify_cli/tool_surface/integration/test_projection_honesty_e2e.py` (pytestmark). Seed a project and assert, against real objects: (a) stale GEMINI.md + LLXPRT.md, no `.gemini/`/`.llxprt/` → refreshed by one `--fix`/`upgrade` (SC-001); (b) `is_windows`→True + dir mode≠0o755 → `upgrade` converges in one pass, exit 0 (SC-002), second run no-op, `--dry-run` zero repairs (SC-003); (c) detect==repair parity holds (SC-004); (d) a POSIX wrong-mode still refuses (SC-006).

### T015 — Blast-radius + CHANGELOG
Run the blast-radius suite; classify any red per the baseline-red gotcha (do not fix pre-existing reds). Add the CHANGELOG `[Unreleased]` → Fixed entry: "doctor tool-surfaces --fix / upgrade now repair every detected-stale agent surface and converge in one run: root-level orientation files (GEMINI.md, LLXPRT.md) are refreshed regardless of a harness command dir; the managed-skills completion re-check is host-aware so Windows upgrades converge in one pass with no phantom dry-run repairs; command-skills manifest content is deterministic; residual drift is reported as failure instead of exit-0 (#4782, #4776, #4777, #4134)." No version bump.

## Branch Strategy
- Planning base / merge target: `fix/tool-surface-projection-fidelity` (final PR → `main`). Capstone lane; worktree per `lanes.json`.

## Definition of Done
- T013–T015 green; blast-radius recorded; CHANGELOG updated (no version bump); ruff/mypy clean.

## Reviewer guidance
- Confirm the e2e drives REAL objects (not mocks) for both seams and asserts the honest-failure path. Confirm no version-gate files touched. Confirm WP01/WP02 helpers are genuinely wired.
