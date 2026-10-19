---
work_package_id: WP04
title: One language catalog and authority, kotlin token and jvm family
dependencies:
- WP03
requirement_refs:
- FR-009
- FR-013
- C-005
planning_base_branch: issue-6442-charter-synthesis-graph-work
merge_target_branch: issue-6442-charter-synthesis-graph-work
branch_strategy: Planning artifacts for this mission were generated on issue-6442-charter-synthesis-graph-work. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6442-charter-synthesis-graph-work unless the human explicitly redirects the landing branch.
subtasks:
- T016
- T017
- T018
- T019
- T020
phase: Phase 1 - Languages
history: []
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- src/charter/offering/shared/language_catalog.py
- src/charter/activation/language_authority.py
- tests/charter_offering/shared/test_language_catalog.py
- tests/charter/test_language_authority.py
- tests/architectural/test_single_language_vocabulary.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/charter/synthesizer/test_interview_mapping.py
- src/charter/activation/synthesizer/interview_mapping.py
- tests/charter_offering/shared/test_scoping_any_all.py
- src/charter/offering/shared/language_catalog.py
- src/charter/offering/shared/scoping.py
- src/charter/activation/language_authority.py
- src/charter/activation/language_scope.py
- src/charter/activation/evidence/code_reader.py
- tests/charter_offering/shared/test_language_catalog.py
- tests/charter/test_language_authority.py
- tests/charter/evidence/test_code_reader.py
- tests/charter/test_language_scope.py
- tests/charter_offering/shared/test_scoping.py
- tests/architectural/test_single_language_vocabulary.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – One language catalog and authority, kotlin token and jvm family

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## Objective

Replace the two parallel language vocabularies with one I/O-free catalog in `charter.offering.shared` and one activation-layer authority. Add a `kotlin` token and a `jvm` family that `java` and `kotlin` both imply, expanded at match time (FR-009, FR-013).

## Context

- Read `spec.md` (User Story 3, scenarios 3, 4, 5, 7, 8) and `plan.md` (D-05).
- **Today's tables:**
  - `evidence/code_reader.py:50-84` (`LANGUAGE_INDICATORS`, `SOURCE_EXT_LANG`, where `.kt` and `build.gradle*` map to `java`) with `_detect_language` (around lines 354-393);
  - `language_scope.py:46-56` (`_LANGUAGE_PATTERNS`, where gradle, maven and junit map to `java`) with `extract_declared_languages` and `infer_repo_languages`.
- **Matching** is in `offering/shared/scoping.py:69` (`applies_to_languages_match`). The offering layer must NOT import `charter.activation`.
- **Out of scope:** the doctrine-derived vocabulary (`language_vocabulary.py`, #5284) stays separate and unchanged.
- **Kept out of this WP:** multi-language evidence (WP05). `_detect_language` still returns one primary.

### Subtask T016: Red-first tests

- `tests/charter/test_language_authority.py` and `tests/charter_offering/shared/test_language_catalog.py` (`@pytest.mark.regression`, #6444):
  - a Gradle repository with more `.kt` than `.java` sources has primary language `kotlin`; with more `.java` it is `java`;
  - declared "Kotlin and Spring" resolves to `[kotlin]`, and "Kotlin, Gradle, JUnit" to `[kotlin]` (never `java` or `unknown`);
  - "Gradle" alone resolves to `[jvm]`, and "Java, Gradle" to `[java]` (unchanged);
  - an artifact tagged `jvm` matches active `[kotlin]` and `[java]`; an artifact tagged `java` does not match `[kotlin]`;
  - `lacks_specialist_guidance` expands families before intersecting.
- `tests/architectural/test_single_language_vocabulary.py`: an AST scan of `src/` that flags dict, set or tuple literals holding three or more catalog language tokens or source extensions anywhere outside `language_catalog.py`. Count string constants anywhere inside a literal's nested tuples and dicts too. Today's `language_scope._LANGUAGE_PATTERNS` is a tuple of `(token, patterns)` pairs, and a flat scan misses it. `src/specify_cli/review/fix_prompt.py` is allowlisted with a rationale: it is a markdown fence-language map, a different concept.
- Confirm the behavioural tests fail before the fix, and that the architectural test fails on today's two tables.

### Subtask T017: Language catalog (offering layer)

- `src/charter/offering/shared/language_catalog.py`, pure data with no I/O:
  - a frozen `LanguageSpec(token, extensions, manifests, declared_patterns, families)` for python, javascript, typescript, java, kotlin, go, rust, ruby, php and swift;
  - build/test-tool declared tokens (gradle, maven, junit) that declare only the `jvm` family;
  - `LANGUAGE_FAMILIES`, `expand_language_families(tokens) -> tuple[str, ...]` (stable order, no duplicates) and `canonical_tokens()`.
- Preserve today's manifest-to-language facts: today's `LANGUAGE_INDICATORS` and `SOURCE_EXT_LANG` are now derived from it. Kotlin's manifest is a JVM manifest (`build.gradle(.kts)`, `settings.gradle(.kts)`, `gradlew`, `mvnw`, `pom.xml`), and the language is chosen by source counts.

### Subtask T018: Authority (activation layer)

- `src/charter/activation/language_authority.py`:
  - `observe_primary_language(repo_root, max_depth)`, which moves today's detection out of `code_reader`. Keep the shallowest-manifest rule and the tie-break, plus the JVM split by `.kt` vs `.java` counts, run only when a JVM manifest is present (NFR-005);
  - `declared_languages(text)`, which replaces `extract_declared_languages`. Apply the build-token rule: add `jvm` only when no JVM language is declared;
  - re-export `expand_language_families`.
- `code_reader` and `language_scope` delegate to it and keep their public signatures. `infer_repo_languages` keeps its four-state contract and never persists families.
- No `specify_cli` caller needs the authority, so do not touch `charter.activation.api` (WP02 and WP03 own it). Keep the signatures of `extract_declared_languages` and `infer_repo_languages`: `interview_mapping` and five activation modules import them.
- **Family tokens never become synthesis targets.** In `interview_mapping`'s language_scope path (`_extract_languages_from_alias` / `_normalize_language_scope_section`), drop family tokens such as `jvm`, so "Gradle" alone synthesizes no `jvm-style-guide`. A declared "Kotlin" synthesizes a `kotlin` language styleguide like any other language. Add a fixture-adapter fixture if the tests need one, following the procedure in WP02 T009.

### Subtask T019: Match-time family expansion

- In `offering/shared/scoping.applies_to_languages_match`, expand the active languages through `expand_language_families` before intersecting with `applies_to_languages`.
- Do not change the any/all semantics; check them in `tests/charter_offering/shared/test_scoping_any_all.py`. It is not owned, so ask the orchestrator if it needs an edit.
- Confirm `charter validate` and the doctrine schema accept `jvm` as an `applies_to_languages` token. If a schema enumerates languages, report it to the orchestrator rather than editing an unowned file.

### Subtask T020: Update pinned tests

- `tests/charter/evidence/test_code_reader.py` (around lines 220, 243 and 324) pins `java` for Gradle and Kotlin input. Keep the Java-majority cases as `java` and change the Kotlin-majority ones to `kotlin`.
- Update `tests/charter/test_language_scope.py` for the declared rules.
- Run every test that references `infer_repo_languages` (`git grep -l infer_repo_languages tests`) and fix only expectations this WP intentionally changed. List them in the history.

## Definition of Done

- The T016 tests were red before the fix and are green after it, and the markers are converted.
- These pass:
  - `tests/charter/evidence/`, `tests/charter/test_language_*.py`
  - `tests/charter_offering/shared/`
  - the `infer_repo_languages` test files
  - `tests/charter/synthesizer/` (the JVM split changes the Kotlin evidence hash)
  - `tests/architectural/test_single_language_vocabulary.py`, `tests/architectural/test_layer_rules.py`, `tests/architectural/test_runtime_charter_activation_boundary.py`, `tests/architectural/test_no_dead_symbols.py`
- ruff, format and `mypy --strict` are clean; complexity ≤ 15.

## Risks

- **Layering:** the catalog must not import activation.
- **A declared "Gradle" changes from `[java]` to `[jvm]`.** This is intended (operator decision). Call it out in the history for the CHANGELOG.

## Reviewer Guidance

- Exactly one vocabulary table.
- Families are never persisted into `catalog.languages`.
- `java`-tagged doctrine is not matched for Kotlin-only projects.
