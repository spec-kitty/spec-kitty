---
work_package_id: WP03
title: LANGUAGE_TOKENS on the offering seam (#6541)
dependencies: []
requirement_refs:
- C-003
- FR-007
- FR-008
- NFR-001
- SC-004
planning_base_branch: tidy-charter-6539-followups
merge_target_branch: tidy-charter-6539-followups
branch_strategy: Planning artifacts for this mission were generated on tidy-charter-6539-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into tidy-charter-6539-followups unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-followups-tidy-01M5CCYJ
base_commit: fd3ab4a3816178ccb0af0fb5c58f3f271c73f40b
created_at: '2026-10-20T11:46:30.641779+00:00'
subtasks:
- T013
- T014
- T015
- T016
phase: Phase 1 - Parallel work packages
history:
- at: '2026-10-20T11:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/
create_intent:
- src/charter/languages.py
- tests/charter_offering/test_language_tokens_seam.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/charter/offering/shared/language_catalog.py
- src/charter/offering/api.py
- src/charter/languages.py
- src/charter/activation/synthesizer/write_pipeline.py
- tests/architectural/test_charter_facades_reexport_offering.py
- tests/architectural/test_no_dead_modules.py
- tests/charter_offering/test_language_tokens_seam.py
- tests/architectural/test_doctrine_census.py
- docs/adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – LANGUAGE_TOKENS on the offering seam (#6541)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter (`python-pedro`, role `implementer`). Behave according to it before reading the rest of this prompt. If the skill is unavailable, read `packs/built-in/agent_profiles/python-pedro.agent.yaml` directly.

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` in the event log. If this WP came back from review, every feedback item is your TODO list. Record what you changed with `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Objectives & Success Criteria

Issue #6541. Operator decisions: `seam_language_catalog` and `seam_language_export_shape`.

- `charter.offering.shared.language_catalog` gains `LANGUAGE_TOKENS: tuple[str, ...]`. It is derived from `LANGUAGES` (the `token` of each `LanguageSpec`, in catalog order), read-only, and declared once next to `LANGUAGES`.
- `charter.offering.api` exports `LANGUAGE_TOKENS`:
  - `__all__` stays sorted;
  - it gets a `PUBLIC` disposition in `tests/architectural/test_doctrine_census.py::DISPOSITION`;
  - at least one charter facade re-exports it **from `charter.offering.api`**, as `test_every_public_symbol_is_routed_through_a_facade` requires.
- **The seam does not export `LANGUAGES`, `LanguageSpec`, `expand_language_families`, `is_language_family`, or any family map** (FR-008).
- ADR 2026-10-03-1 gets a short dated amendment note. It records that the frozen seam is widened by `LANGUAGE_TOKENS` (#6541), why, and that a conformance-corpus case belongs to epic #6099.
- Spec: User Story 3; FR-007/008; C-003; SC-004.

## Context & Constraints

- Read `.kittify/charter/charter.md`.
- `src/charter/offering/api.py`:
  - its module docstring explains the layering (C-001): runtime code under `src/specify_cli/` must **not** import `charter.offering.api` directly, and charter facades re-export it;
  - `__all__` is at about :69-80.
- Existing facades: `src/charter/drg.py` (ArtifactKind), `src/charter/assets.py` and `src/charter/model_routing.py`, each written `from charter.offering.api import …`. Follow their pattern.
- Census: `tests/architectural/test_doctrine_census.py::DISPOSITION` (about :120). The `model_task_routing` entry (about :153-154) is a precedent for a symbol-level PUBLIC entry.
- Gates:
  - `tests/architectural/test_charter_offering_public_surface.py` (sorted, importable, disposition-coupled, facade-routed);
  - `test_charter_facades_reexport_offering.py`, if present;
  - `tests/charter_offering/test_api_surface_import.py`, if present;
  - `test_no_dead_modules.py` and `test_no_dead_symbols.py`. A new facade module needs a live in-repo importer.
- **Do not edit files owned by WP02:** `src/charter/activation/language_authority.py`, `language_settlement.py`, `src/charter/activation/api.py`, `interview.py`. 
- **Live caller for the facade:** `src/charter/activation/synthesizer/write_pipeline.py` (about :319) builds its own `_CATALOG_LANGUAGE_TOKENS` from the catalog. Replace that with `from charter.languages import LANGUAGE_TOKENS`. This removes a duplicate derivation and gives the facade a real caller. Check that `tests/architectural/test_layer_rules.py` stays green.
- **Facade table:** `tests/architectural/test_charter_facades_reexport_offering.py` keeps `_FACADE_TABLE` (precedents about :202 `charter.model_routing` and :210 `charter.assets`). Its inverse-containment gate (about :369) and `test_facade_all_lists_every_reexport` (about :405) check every `charter.*` facade, so the new facade must be added there.

## Branch Strategy

- **Strategy**: lanes_with_coord (populated by finalize-tasks)
- **Planning base branch**: tidy-charter-6539-followups
- **Merge target branch**: tidy-charter-6539-followups

Start with `spec-kitty agent action implement WP03 --agent claude --mission charter-followups-tidy-01M5CCYJ`.

## Subtasks & Detailed Guidance

### Subtask T013 – Red-first seam test

- New `tests/charter_offering/test_language_tokens_seam.py` (match the marker conventions of its neighbours). It must be red on the unchanged source. Record the red run with `add-history`. It asserts:
  1. `from charter.offering.api import LANGUAGE_TOKENS` works.
  2. It is a `tuple` of `str`, equal to `tuple(spec.token for spec in language_catalog.LANGUAGES)` in order, and it contains `"python"`, `"kotlin"` and `"java"`.
  3. None of `LANGUAGES`, `LanguageSpec`, `expand_language_families`, `is_language_family` (or any other family helper the catalog defines; read the module) is an attribute of `charter.offering.api` or in its `__all__`.
  4. The facade re-exports the same object.

### Subtask T014 – `LANGUAGE_TOKENS`

- In `language_catalog.py`, directly after `LANGUAGES`: `LANGUAGE_TOKENS: tuple[str, ...] = tuple(spec.token for spec in LANGUAGES)`.
  - Add a one-line comment: it is the public token list; the records stay internal.
  - Check whether the module defines its own `__all__`. If so, add the name there.
- **No behaviour change:** nothing else in the catalog changes.

### Subtask T015 – Seam, census, facade

1. In `src/charter/offering/api.py`, import `LANGUAGE_TOKENS` from the catalog and add it to `__all__` in sorted position. If the docstring lists the surface, update it.
2. In `tests/architectural/test_doctrine_census.py::DISPOSITION`, add `"charter.offering.shared.language_catalog": "PUBLIC"`. The census is module-keyed and looked up by longest module prefix (`test_charter_offering_public_surface.py` about :72-85); it has no per-symbol entries. FR-008 is therefore enforced by `charter.offering.api.__all__` plus T013 test 3. Say so in a comment beside the entry and in the ADR note.
3. Facade: create `src/charter/languages.py`, a small facade in the style of `charter/model_routing.py`.
   - Its module docstring names the public language vocabulary.
   - It does `from charter.offering.api import LANGUAGE_TOKENS` and sets `__all__ = ["LANGUAGE_TOKENS"]`.
   - Add `charter.languages: [("LANGUAGE_TOKENS", "charter.offering.shared.language_catalog")]` to `_FACADE_TABLE` in `test_charter_facades_reexport_offering.py`.
   - Repoint `write_pipeline.py`'s `_CATALOG_LANGUAGE_TOKENS` to the facade (the live caller). If the dead-module gate still flags the module, add an `_ALLOWLIST` entry in `test_no_dead_modules.py` (about :663) with a one-line reason.
   - Also run `tests/architectural/test_charter_facades_reexport_offering.py` and `tests/charter/synthesizer/`.
   - Prefer the existing mechanism over adding an artificial caller.
4. Run:
   - `tests/architectural/test_charter_offering_public_surface.py`
   - `tests/architectural/test_doctrine_census.py`
   - `tests/architectural/test_no_dead_modules.py`
   - `tests/architectural/test_no_dead_symbols.py`
   - `tests/architectural/test_layer_rules.py`
   - `tests/architectural/test_single_language_vocabulary.py` (it flags literals only and exempts the catalog file)
   - any `test_charter_facade*` gate

### Subtask T016 – ADR amendment note

- `docs/adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md`: append a short dated amendment (2026-10-20, #6541) to its seam scope. It says:
  - `charter.offering.api` gains `LANGUAGE_TOKENS`, a read-only tuple of plain language tokens, for the charter service and the conformance corpus;
  - the catalog records, their family data and the family expansion stay internal (operator decisions `seam_language_catalog` and `seam_language_export_shape`);
  - a conformance-corpus case for the token list belongs to epic #6099.
- Run `PYTHONPATH=. uv run --frozen python scripts/docs/check_docs_freshness.py --ci`.

## Test Strategy

- **Blast radius:** `uv run --frozen pytest tests/charter_offering/ tests/charter/ -n 4 --dist loadfile`, plus the gates listed in T015.
- **Baseline:** `make test-fast`.
- **Static checks:** ruff, `ruff format --check --force-exclude` and mypy on the changed files, with 0 new issues.

## Risks & Mitigations

- **Widening a frozen seam:** the ADR note documents it.
- **Never hand-copy the tokens:** derive them from `LANGUAGES` in the catalog. The vocabulary gate flags literals only and exempts the catalog file.
- **The census entry marks the whole catalog module PUBLIC-eligible:** the seam's `__all__` and the negative test keep the records and helpers off the seam.

## Review Guidance

- Only `LANGUAGE_TOKENS` is added to the seam. The records and the family helpers are absent.
- It is derived, not hand-copied.
- The facade re-exports it from `charter.offering.api`.
- The census entry is PUBLIC.
- The ADR note is present.
- No WP02-owned file was touched.

## Progress & Status

Record progress with `mark-status` and `add-history`, as in the other WPs.
