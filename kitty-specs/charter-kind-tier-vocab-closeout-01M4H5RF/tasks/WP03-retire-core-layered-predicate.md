---
work_package_id: WP03
title: Retire ArtifactKind.core via has_layered_repository
dependencies:
- WP02
requirement_refs:
- FR-008
- FR-009
- FR-010
- FR-011
- C-001
- C-003
- NFR-001
planning_base_branch: feat/charter-kind-tier-vocab-closeout
merge_target_branch: feat/charter-kind-tier-vocab-closeout
branch_strategy: Planning artifacts for this mission were generated on feat/charter-kind-tier-vocab-closeout. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/charter-kind-tier-vocab-closeout unless the human explicitly redirects the landing branch.
subtasks:
- T030
- T031
- T032
- T033
- T034
- T035
- T036
phase: Phase 3 - Core retirement
history:
- at: '2026-10-09T20:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: ''
authoritative_surface: src/charter/offering/artifact_kinds.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/offering/artifact_kinds.py
- src/charter/drg.py
- src/specify_cli/cli/commands/_charter_pack_collect.py
- src/specify_cli/charter_runtime/lint/checks/org_layer.py
- src/specify_cli/charter_packs/sources/api_source.py
- src/specify_cli/upgrade/migrations/_charter_pack_cutover_snapshots.py
- tests/charter_offering/test_artifact_kinds.py
- tests/architectural/test_charter_facades_reexport_offering.py
- src/charter/offering/packs/pack_manifest.py
- src/charter/offering/packs/pack_assembler.py
- src/charter/activation/context_renderers/fetch_stanza.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Retire ArtifactKind.core via has_layered_repository

Closes #5824. Depends on WP02 (shared `artifact_kinds.py`; the new frozenset must pass the live kind gate).

## Objectives & Success Criteria

- `ArtifactKind.has_layered_repository` added (11 kinds = all EXCEPT `TEMPLATE` and `ANTI_PATTERN`), its own backing frozenset, a "coincides with `org_requirable` today — do NOT merge" docstring, and a derived `LAYERED_REPOSITORY_KIND_PLURALS` tuple. Unit tests pin the exact set.
- The three diagnostic surfaces cover glossary_pack/skill/asset; the API-source 404 fallback is **widened** to the 11 layered kinds (operator decision).
- `DEFAULT_KIND_GATE` gets its own literal (NOT the predicate).
- `ArtifactKind.core`, `_CORE_KINDS`, `CORE_KIND_PLURALS` deleted; `charter.drg` re-export removed; zero references remain repo-wide.

## Context & Constraints

Authority `src/charter/offering/artifact_kinds.py`: `core` property (~229-248), `_CORE_KINDS` (~331-342), `CORE_KIND_PLURALS` (~345), `__all__` entry (~548). The layered base is `BaseArtifactRepository` (`src/charter/offering/base.py`); the 11 layered kinds = 8 core + `glossary_pack` + `skill` + `asset` (agent_profile is layered via its own three-source repo though not a `BaseArtifactRepository` subclass). `has_layered_repository` is **membership-identical to `org_requirable` today** — give it its OWN frozenset and say so; do NOT reuse `_ORG_REQUIRABLE_KINDS` or `has_built_in_content_dir` (10 kinds, wrongly excludes mission_step_contract). Red-first (C-003); single authority (C-001).

**Grounded surfaces (current paths):**
- Surfaces #1+#2 (collision scan + org dir count): `src/specify_cli/cli/commands/_charter_pack_collect.py` `_ORG_ARTIFACT_DIRS` (~line 83, used ~169 count, ~614 collision; warning type is now `ArtifactLayerCollisionWarning`).
- Surface #3 (org-layer lint): `src/specify_cli/charter_runtime/lint/checks/org_layer.py` `_OVERRIDABLE_ARTIFACT_TYPES` (~line 25, used ~71).
- Surface #4 (API fallback): `src/specify_cli/charter_packs/sources/api_source.py` import ~line 25, `DEFAULT_ARTIFACT_TYPES` ~line 49 — widen to the 11 layered plurals.
- **Fifth usage (NOT the predicate):** `src/specify_cli/upgrade/migrations/_charter_pack_cutover_snapshots.py` `DEFAULT_KIND_GATE` (~line 559) is a frozen release-snapshot value pinned by `tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_snapshots.py::test_kind_gates` — give it its own frozenset literal.
- Facade: `src/charter/drg.py` re-export (import ~75, `__all__` ~124); `_FACADE_TABLE["charter.drg"]` has TWO `CORE_KIND_PLURALS` rows (~69 and ~144) + the symbol appears in `charter.drg.__all__` — remove all.

## Subtasks & Detailed Guidance

- **T030**: add predicate + `_HAS_LAYERED_REPOSITORY_KINDS` + `LAYERED_REPOSITORY_KIND_PLURALS` to `artifact_kinds.py` with unit tests in `tests/charter_offering/test_artifact_kinds.py` (RED first) asserting the exact 11-kind set and that it differs from `selection_overlayable`/`has_built_in_content_dir`.
- **T031**: repoint `_ORG_ARTIFACT_DIRS` to `LAYERED_REPOSITORY_KIND_PLURALS` (or a comprehension); add tests proving a glossary_pack/skill/asset collision is reported and the dir count includes them. Consider sorting the collision list for stable order (issue note).
- **T032**: repoint `_OVERRIDABLE_ARTIFACT_TYPES`; add a test proving an org override of glossary_pack/skill/asset is flagged.
- **T033**: widen `DEFAULT_ARTIFACT_TYPES` to the 11 layered plurals; extend the 404-fallback test (`tests/specify_cli/charter_packs/test_sources.py`) to assert the new coverage.
- **T034**: give `DEFAULT_KIND_GATE` its own explicit frozenset literal; keep `test_kind_gates` green.
- **T036 (added — the core-coupling repoint, see design-decisions.md DD-2)**: WP02 anchored three sites on `core`/`CORE_KIND_PLURALS` which this WP deletes, so repoint them BEFORE T035's deletion:
  - `src/charter/offering/packs/pack_manifest.py` `RECOGNISED_ARTIFACT_DIRS` → `frozenset(k.plural for k in ArtifactKind if k.has_built_in_content_dir) | {"drg"}` (drops the import of `CORE_KIND_PLURALS`). This is a CORRECTNESS FIX: the built-in pack ships `assets/`, `glossary_packs/`, `skills/` dirs and no `mission_step_contracts/` dir. Expect `assets`,`glossary_packs`,`skills` to be ADDED and `mission_step_contracts` REMOVED. Update any test pinning the old value, and regenerate the built-in pack manifest (`spec-kitty charter pack regenerate-graph`) then run the packaging-safety + pack suites.
  - `src/charter/offering/packs/pack_assembler.py` `_ARTIFACT_DIRS_AND_GLOBS` → `{k.plural: k.glob_pattern for k in ArtifactKind if k.has_built_in_content_dir}`.
  - `src/charter/activation/context_renderers/fetch_stanza.py` `_VALID_SELECTOR_KINDS` → `frozenset(k.value for k in ArtifactKind if k.activatable) | {"section"}` (behaviorally inert — `format_selector` branches are identical — so no behavior change; update the comment to say activatable, not "eight core").
- **T035**: delete `core`/`_CORE_KINDS`/`CORE_KIND_PLURALS` + `__all__` entry; remove the `charter.drg` import + `__all__` entry and BOTH `_FACADE_TABLE["charter.drg"]` `CORE_KIND_PLURALS` rows; `grep -rn 'CORE_KIND_PLURALS\|_CORE_KINDS\|\.core\b' src/ tests/` → zero relevant hits (run AFTER T036 so nothing still imports the deleted symbols).

## Test Strategy

- `pytest tests/charter_offering/test_artifact_kinds.py tests/charter/ tests/charter_offering/ -q` (both owning trees).
- Surface tests: `tests/specify_cli/cli/commands/test_doctor_charter_packs_collisions.py`, the org-layer lint tests, `tests/specify_cli/charter_packs/test_sources.py`, `tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_snapshots.py`.
- `pytest tests/architectural/test_charter_facades_reexport_offering.py tests/architectural/test_charter_kind_vocabulary_single_authority.py tests/architectural/test_no_legacy_terminology.py -q`. Plus `make test-fast`.
- `ruff` + `mypy` clean on touched files.

## Review Guidance

- Confirm the 11-kind set is exact and distinct from the coincidental predicates; the three surfaces demonstrably cover the three added kinds; the API fallback widening has a test.
- Confirm `DEFAULT_KIND_GATE` is isolated BEFORE deletion; zero `core`/`CORE_KIND_PLURALS` references remain; facade forward+reverse tests green.

## Activity Log

- 2026-10-09T20:40:00Z – system – Prompt created.
