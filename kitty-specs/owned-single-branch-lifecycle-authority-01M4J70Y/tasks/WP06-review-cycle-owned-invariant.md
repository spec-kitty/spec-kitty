---
work_package_id: WP06
title: Review/cycle owned resolver invariant and defensive hardening
dependencies:
- WP05
requirement_refs:
- C-001
- C-003
- FR-007
- FR-008
- NFR-002
- NFR-003
- SC-002
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T024
- T025
- T026
- T027
phase: Phase 6 - Review cycle invariant
history:
- at: '2026-10-10T06:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/review/cycle.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/review/cycle.py
- tests/specify_cli/test_owned_history_support.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5947'
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile with the `/spk-charter-profile-load` skill (profile: `python-pedro`, role: implementer). Then continue.

# Work Package Prompt: WP06 – Review/cycle owned resolver invariant (#5947)

> Operator decision D4: verify-green + defensive owned hardening. The two named nightly tests are empirically GREEN on current `main`; the red nightly ran on an older commit. Do NOT fabricate a red and do NOT edit any existing test's expectations (charter Standing Order #4 / #9).

## Objectives & Success Criteria

- A validated owned single_branch `review/cycle` arm never consults the primary resolver (`get_main_repo_root`) — pinned by a by-construction test extending the `_ResolverConsulted` poison (FR-007).
- The one latent smell is tidied: `cycle.py` `ProtectionPolicy.resolve(main_repo_root)` → `ProtectionPolicy.resolve_for_owned(owned, mission_slug)` when owned, with an `owned is None` fallback to the existing `resolve(main_repo_root)` (FR-008, locality).
- `tests/specify_cli/test_owned_history_support.py` stays green (no expectation edits); `ruff`/`mypy --strict` clean (NFR-002); new helper/branch covered (NFR-003).

## Context & Constraints

- Grounding + provenance: `../research.md` (row #5947), `../plan.md` IC-06. No repair branch — new work.
- Empirical evidence captured during grounding: `PWHEADLESS=1 uv run --frozen python -m pytest tests/specify_cli/test_owned_history_support.py -q` → 24 passed on `fb8b46c9`; the two named tests (`test_create_rejected_review_cycle_owned_local_only_lands_under_p`, `..._commits_on_p_and_adopts_identical_retry`) pass in isolation. Nightly run #37880273598 was against older `head_sha f1e4e69c`.
- Why nightly-only: the file lives directly under `tests/specify_cli/` (markers `[integration, git_repo]`), which the per-PR CI Modules matrix does not route (only `{consolidation,status,write_side,runtime}`); it is swept only by the nightly `specify-cli-out-of-matrix` job. The full nightly sweep is CI-owned and must NOT be run in-mission (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
- `cycle.py` already threads `owned` on its public entry (`create_rejected_review_cycle(..., owned=...)`) and through every helper (`_operation_root(main_repo_root, owned)` returns `owned.owned_root if owned is not None else main_repo_root`; `placement_seam(..., owned=owned)` at the review-cycle sites). The only latent smell is `ProtectionPolicy.resolve(main_repo_root)` inside `_commit_review_cycle_artifact` (R-only, mission-unscoped) — harmless for the poison today (the router re-scopes via `_mission_scoped(..., owned=owned)`), but it should consume the owned fact for correctness.
- Charter: C-001 single resolver / no `core/paths.py`; C-003 (no test-expectation edits, no fabricated red); DIRECTIVE_024 locality.

## Branch Strategy

- **Planning base branch**: main · **Merge target branch**: main. Runs in the write checkout.

## Subtasks & Detailed Guidance

### Subtask T024 – Verify-green and record evidence

- **Steps**: Run `PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/test_owned_history_support.py -q` (or `uv run --frozen python -m pytest …`) on the WP base and record the pass count in the PR "Tests run" section. This is the scoped evidence that the owned arms are green on the mission base.

### Subtask T025 – By-construction invariant test (new, does not edit existing expectations)

- **Purpose**: Pin that an owned single_branch review/cycle arm never consults `get_main_repo_root`.
- **Steps**: Add a NEW test (in `tests/specify_cli/test_owned_history_support.py`, alongside the existing `_poison_main_repo_root` / `_ResolverConsulted` machinery) that mints a validated owned single_branch `OwnedCheckout`, poisons `specify_cli.core.paths.get_main_repo_root` to raise `_ResolverConsulted`, drives the `review/cycle` owned arm, and asserts it completes without raising `_ResolverConsulted` (resolver not consulted) and writes under the owned checkout. Do not modify the two existing named tests.
- **Notes**: This is a by-construction gate, not a reproduced red — it fails if a future change reintroduces an owned-arm resolver fold.

### Subtask T026 – Tidy the latent smell

- **Steps**: In `cycle.py::_commit_review_cycle_artifact`, replace `policy = ProtectionPolicy.resolve(main_repo_root)` with `policy = ProtectionPolicy.resolve_for_owned(owned, mission_slug) if owned is not None else ProtectionPolicy.resolve(main_repo_root)`. Keep the signature/threading already present; this is a one-line locality fix that makes the owned arm's protection decision consume the owned fact directly.
- **Files**: `src/specify_cli/review/cycle.py`.

### Subtask T027 – Validate green

- **Steps**: Re-run `tests/specify_cli/test_owned_history_support.py` (24 existing + the new invariant case) — all green; format-check + ruff + mypy on the changed file. Record counts.

## Definition of Done

- New invariant test present and green; latent smell tidied; existing 24 tests still green with no expectation edits; lint/type clean; PR notes the scoped-green evidence and that the next green nightly self-closes #5947.

## Reviewer Guidance

- Confirm no existing test expectation was edited; confirm the new test genuinely poisons `get_main_repo_root` and drives an owned review/cycle arm; confirm the `resolve_for_owned` tidy keeps the `owned is None` fallback.
