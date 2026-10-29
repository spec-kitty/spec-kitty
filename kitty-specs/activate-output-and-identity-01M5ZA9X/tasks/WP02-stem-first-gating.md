---
work_package_id: WP02
title: Pin and document stem-first activation gating
dependencies: []
requirement_refs:
- FR-008
- FR-009
planning_base_branch: issue-6457-activate-output-identity
merge_target_branch: issue-6457-activate-output-identity
branch_strategy: Planning artifacts for this mission were generated on issue-6457-activate-output-identity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6457-activate-output-identity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-activate-output-and-identity-01M5ZA9X
base_commit: 0010456f8049f8af6deda36b0f09471c5714f2ee
created_at: '2026-10-27T18:44:04.550949+00:00'
subtasks:
- T008
- T009
- T010
phase: Phase 1 - Implementation
history:
- at: '2026-10-27T18:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/resolver.py
create_intent:
- tests/charter/activation/test_stem_first_gating_6459.py
execution_mode: code_change
owned_files:
- src/charter/activation/resolver.py
- tests/charter/activation/test_stem_first_gating_6459.py
- docs/architecture/org-doctrine-layer.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Pin and document stem-first activation gating

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter (`python-pedro`, implementer, `claude`) before reading further.

## Review Feedback

*[Filled from the status event log when returned from review.]*

## Objectives & Success Criteria

- FR-008: a resolver-level test fails if a built-in declared id wins over a higher-layer file name. Includes a same-fixture positive control.
- FR-009: `docs/architecture/org-doctrine-layer.md` §Precedence and resolution says that an activation token matching a file name (stem) resolves to that file's artifact **regardless of layer**, before any declared id is consulted; `ActiveCharterService._gated` docstring links it.
- C-002: no behaviour change (this is a Task, #6459). Spelling unification (#6435) stays in epic #6518.

## Context & Constraints

- `src/charter/activation/resolver.py:217-242` (`_gated`) → `IdentityIndex.activation_id` → `IdentityIndex._lookup` (`identity_index.py:244-250`, `by_stem.get(token) or by_id.get(token)`).
- Existing index-level coverage: `tests/charter/activation/test_identity_index.py:319-330` (lower-layer stem beats higher-layer declared id). Do not duplicate it; this WP adds the opposite, resolver-level direction the issue asks for.

## Branch Strategy

- **Planning base branch**: issue-6457-activate-output-identity · **Merge target**: issue-6457-activate-output-identity · worktree per computed lane (`lanes.json`).

## Subtasks & Detailed Guidance

### Subtask T008 – Resolver pinning test

- New `tests/charter/activation/test_stem_first_gating_6459.py`, marker `fast`.
- Fixture (prototype verified during planning): git-init a tmp project, `.kittify/config.yaml` = `{}`; a project-layer file `.kittify/charter-packs/<PROJECT_KIND_DIRS[DIRECTIVE]>/DIRECTIVE_024.directive.yaml` copied from `packs/built-in/directives/024-locality-of-change.directive.yaml` with `id: DIRECTIVE_901` (and a distinct title); `seed_activation_ledger(root, mission_type_activations=["software-dev"], activated_directives=["DIRECTIVE_024"])`.
- Assert `sorted(build_active_charter_service(root).directives) == ["DIRECTIVE_901"]` (built-in `DIRECTIVE_024` NOT admitted).
- Positive control (same setup without the project file): `["DIRECTIVE_024"]` admitted.
- Read the built-in file through the packs tree (`built_in_dir` / the offering root helper used by other tests), not a hard-coded absolute path.

### Subtask T009 – Doc note

- In `org-doctrine-layer.md` under "Precedence and resolution" → "Across layers", add a short subsection (e.g. `#### Activation tokens: a file name beats a declared id`) stating: an activation token (an entry of an `activated_<kind>` list) is matched against file names (stems) first, across every layer, and only then against declared ids; so a file named `foo` in any layer wins over another artifact that declares `id: foo`, regardless of which layer is higher. Layer order decides between two artifacts with the same id, not between a stem and a declared id. Reference #6459 and the pinning test.

### Subtask T010 – Docstring link

- `_gated` docstring: one sentence: "Tokens are matched stem first, regardless of layer (see docs/architecture/org-doctrine-layer.md, 'Activation tokens: a file name beats a declared id')."

## Test Strategy

```bash
uv run --frozen pytest tests/charter/activation/test_stem_first_gating_6459.py tests/charter/activation/test_identity_index.py -q
uv run --frozen ruff check src/charter/activation/resolver.py tests/charter/activation/test_stem_first_gating_6459.py
uv run --frozen ruff format --check --force-exclude src/charter/activation/resolver.py tests/charter/activation/test_stem_first_gating_6459.py
uv run --frozen mypy src/charter/activation/resolver.py
```

Mutation check (non-vacuity): temporarily swap `_lookup` to `by_id.get(token) or by_stem.get(token)` and confirm the test goes red; revert.

## Risks & Mitigations

- The project file must be a valid directive or the layer loader warns/skips: copy the built-in YAML and change only `id`/`title`.

## Review Guidance

- Confirm the mutation check was run and the doc wording says "regardless of layer".
