---
work_package_id: WP07
title: Migrate remaining charter-activation/offering consumers
dependencies:
- WP01
requirement_refs:
- FR-002
planning_base_branch: kitty/org-pack-chain-authority-stack
merge_target_branch: kitty/org-pack-chain-authority-stack
branch_strategy: Planning artifacts for this mission were generated on kitty/org-pack-chain-authority-stack. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/org-pack-chain-authority-stack unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-org-pack-chain-authority-01M4JXF5
base_commit: 179403e0a7ef80bdc6932c2eb0def1a00f879793
created_at: '2026-10-10T14:29:56.946578+00:00'
subtasks:
- T038
- T039
- T040
- T041
- T042
phase: Phase 2 - Migration
history:
- at: '2026-10-10T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/active_charter_service_builder.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/active_charter_service_builder.py
- src/charter/activation/_drg_helpers.py
- src/charter/activation/language_vocabulary.py
- src/charter/activation/profile_resolution.py
- src/charter/activation/project_registration.py
- src/charter/activation/skill_preparation.py
- src/charter/offering/resolver.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Migrate remaining charter-activation/offering consumers

## ⚡ Do This First: Load Agent Profile

Use `/spk-charter-profile-load` to load the frontmatter profile first.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Route the remaining charter-tier primitive callers through `resolve_pack_chain()` so the WP06 path-scoped gate is green. These are **mechanical, behaviour-preserving** swaps — every one is lenient (existing-filtered) today.

Done when every listed file sources its org chain from `resolve_pack_chain(strict=False)` instead of a chain primitive, behaviour is unchanged, the owning module suites stay green, and ruff/mypy are clean.

## Context & Constraints

Spec: FR-002. Depends on **WP01**. All swaps are `strict=False` (these were lenient/existing-filtered); none is a governance decision surface.

Migration map (verified file:line):
- `active_charter_service_builder.py`: `_self_resolve_existing_org_roots` (:193 `resolve_existing_org_roots`) → `resolve_pack_chain(strict=False)`. Keep the `org_roots is not None else …` fallback shape at :239.
- `_drg_helpers.py`: `:239` `resolve_existing_org_roots(repo_root)` → `resolve_pack_chain(strict=False)`.
- `language_vocabulary.py`: `:89` `for org_root in resolve_existing_org_roots(repo_root)` → iterate `resolve_pack_chain(repo_root, strict=False)`.
- `profile_resolution.py`: `:101` `[root for root in resolve_org_roots(repo_root) if root.exists()]` → `resolve_pack_chain(repo_root, strict=False)` (the authority already existence-filters).
- `project_registration.py`: `:267` `resolve_existing_org_roots(root)` → `resolve_pack_chain(root, strict=False)`.
- `skill_preparation.py`: `:324` `resolve_existing_org_roots(repo_root)` → `resolve_pack_chain(repo_root, strict=False)`.
- `charter/offering/resolver.py`: `:213` and `:378` `for org_root in resolve_org_roots(project_dir, quiet=True)` → iterate `resolve_pack_chain(project_dir, strict=False)`. **Verify** the loops do not depend on the UNfiltered set (the `quiet=True` + any internal `is_dir` check) — if a loop currently iterates non-existent roots and skips them internally, the existing-filtered authority is equivalent; note the check in your history.

Constraint: `charter/drg.py` re-exports the primitives (imports + `__all__`, no call) — the call-based WP06 gate does NOT flag it; leave it (its re-export tightening is in the tree-wide follow-up).

## Subtasks

### T038 — `active_charter_service_builder`
Swap `_self_resolve_existing_org_roots`'s primitive call to the lenient authority; keep the external `org_roots` override path.

### T039 — `_drg_helpers`
Swap `:239` to the lenient authority.

### T040 — `language_vocabulary`
Swap the `:89` loop source to the lenient authority.

### T041 — `profile_resolution` + `project_registration` + `skill_preparation`
Swap each existing-filter/`resolve_existing_org_roots` call to `resolve_pack_chain(strict=False)`.

### T042 — `charter/offering/resolver` + gates
Swap the two loop sources (:213/:378) to the lenient authority, verifying the unfiltered-vs-existing equivalence. ruff/mypy clean; run the owning suites (below) green.

## Test strategy
No new behavioural test is warranted (pure delegate swaps, behaviour-identical). Confirm the owning module suites stay green and rely on the WP06 gate to prove the primitive calls are gone:
```bash
.venv/bin/python -m pytest tests/charter/ tests/charter_offering/ -q
```

## Branch strategy
Planning base / merge target `kitty/org-pack-chain-authority-stack`; worktree per lane from `lanes.json`. Depends on **WP01**.

## Definition of Done
Every listed file sources its chain from `resolve_pack_chain(strict=False)`; behaviour unchanged; owning suites green; ruff/mypy clean.

## Risks & reviewer guidance
- **Posture error**: none of these is a governance surface — all stay lenient. A strict swap would regress NFR-004. Reviewer confirms `strict=False` throughout.
- **offering/resolver unfiltered assumption**: reviewer confirms the loops don't need the unfiltered declared set.
- **Scope**: WP07 owns only these 7 files; do not touch WP02/WP08 files or `charter/drg.py`.
