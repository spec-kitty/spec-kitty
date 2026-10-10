---
work_package_id: WP02
title: Migrate charter-activation core consumers
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-008
- NFR-004
- NFR-005
planning_base_branch: kitty/org-pack-chain-authority-stack
merge_target_branch: kitty/org-pack-chain-authority-stack
branch_strategy: Planning artifacts for this mission were generated on kitty/org-pack-chain-authority-stack. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/org-pack-chain-authority-stack unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-org-pack-chain-authority-01M4JXF5
base_commit: 95353cca6e512927c7aef21b1a35029f7782fdab
created_at: '2026-10-10T14:29:03.316723+00:00'
subtasks:
- T007
- T008
- T009
- T012
- T013
phase: Phase 2 - Migration
history:
- at: '2026-10-10T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/effective_set.py
create_intent:
- tests/charter/activation/test_effective_set_chain.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/effective_set.py
- src/charter/activation/preset_application.py
- src/charter/activation/org_charter.py
- tests/charter/activation/test_effective_set_chain.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Migrate charter-activation core consumers

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the frontmatter profile first.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Route the three charter-activation *core* chain consumers through `resolve_pack_chain()` (from WP01), choosing the posture per surface, so none re-derives the chain.

Done when:
- `effective_set`, `preset_application`, and `org_charter` obtain the org chain from `resolve_pack_chain()` — strict where the surface makes a governance decision, lenient (`strict=False`) elsewhere.
- A behavioural positive control proves a pack-2-only artifact is observable through `effective_set` and `preset_application`.
- `kind_vocabulary._org_scan_dirs` flat-wins precedence is untouched (NFR-005) — do not edit `kind_vocabulary.py`.
- ruff/mypy clean; complexity ≤15.

(The CLI charter consumers — `deactivate`, `_resynthesis_preflight`, `interview`, `context`, `pack_asset` — are **WP08**. The remaining activation/offering consumers — `active_charter_service_builder`, `_drg_helpers`, `language_vocabulary`, `profile_resolution`, `project_registration`, `skill_preparation`, `offering/resolver` — are **WP07**. Do not touch them here.)

## Context & Constraints

Spec: FR-002, FR-008, NFR-004, NFR-005. Depends on **WP01**.

Migration map (verified file:line; swap the named call to `resolve_pack_chain`):
- `effective_set.py`: `_declared_org_roots` (:100, `require_declared_org_roots`) → `resolve_pack_chain(strict=True)`; `_readable_roots` (:176, `resolve_org_roots(..., quiet=True)` + `is_dir` filter) → `resolve_pack_chain(strict=False)` (keep best-effort catch-and-skip); `_scanned_ids` org loop keeps its per-root `{**base, "org": root}` scan but sources the chain from the authority.
- `preset_application.py`: `_Roots.of` (:327, strips `"org"` from `resolve_layer_roots`) threads org separately — source it from `resolve_pack_chain`; the DRG load at :301/:417 (`resolve_org_root_chain`) → `resolve_pack_chain(strict=False)`, and :419 (`require_declared_org_roots`) → `resolve_pack_chain(strict=True)`. Keep the `if layer != "org"` strip.
- `org_charter.py`: `:421` and `:966` `resolve_org_root_chain(repo_root)` → `resolve_pack_chain(strict=False)`. Keep the chain↔`resolve_layer_roots` pairing.

Constraints:
- Choose the posture deliberately (research.md Decision 4); when a call was lenient today, keep it lenient.
- Do not change `resolve_layer_roots` or `kind_vocabulary.py`.

## Subtasks

### T007 — `effective_set` migration
`_declared_org_roots`→strict authority; `_readable_roots`/`_fallback_ids`→lenient authority; preserve best-effort degrade and `_scanned_ids` per-root scan semantics.

### T008 — `preset_application` migration
`_Roots.of` / `_available_mission_types` / the DRG-load chain source → `resolve_pack_chain` (posture per call site as above). Keep the `layer != "org"` strip.

### T009 — `org_charter` migration
Swap `resolve_org_root_chain` (:421, :966) → `resolve_pack_chain(strict=False)`; keep the pairing with `resolve_layer_roots`.

### T012 — Behavioural positive control
New `tests/charter/activation/test_effective_set_chain.py`: two-pack fixture where an artifact/id lives only in pack 2 is observable through `effective_set` (scanned ids include it) and `preset_application` (a pack-2 mission type resolves). Same-fixture negative: with only pack 1, it is absent. Issue-pinned `@pytest.mark.regression`.

### T013 — Quality gates + NFR-005
ruff/mypy clean. Run `tests/charter/test_kind_vocabulary_scan_roots.py` and confirm green **unchanged** (NFR-005).

## Test strategy
```bash
.venv/bin/python -m pytest tests/charter/activation/test_effective_set_chain.py tests/charter/test_kind_vocabulary_scan_roots.py tests/charter/ -q
```

## Branch strategy
Planning base / merge target `kitty/org-pack-chain-authority-stack`; worktree per lane from `lanes.json`. Depends on **WP01**.

## Definition of Done
All five subtasks `mark-status` done; the three consumers source the chain from the authority with deliberate postures; behavioural control green; NFR-005 test green unchanged; ruff/mypy clean.

## Risks & reviewer guidance
- **Wrong posture**: best-effort surface made strict regresses NFR-004; governance surface left lenient weakens the seam. Reviewer checks each choice against research.md Decision 4.
- **Scope creep** into `kind_vocabulary.py`/`resolve_layer_roots`/WP07/WP08 files: out of bounds here.
