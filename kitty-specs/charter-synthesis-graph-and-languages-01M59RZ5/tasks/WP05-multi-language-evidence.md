---
work_package_id: WP05
title: Multi-language evidence, neutrality gate, stable hash, JSON
dependencies:
- WP04
- WP03
requirement_refs:
- FR-010
- FR-011
- FR-012
- FR-014
- FR-019
- NFR-005
- SC-004
planning_base_branch: issue-6442-charter-synthesis-graph-work
merge_target_branch: issue-6442-charter-synthesis-graph-work
branch_strategy: Planning artifacts for this mission were generated on issue-6442-charter-synthesis-graph-work. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6442-charter-synthesis-graph-work unless the human explicitly redirects the landing branch.
subtasks:
- T021
- T022
- T023
- T024
- T025
phase: Phase 2 - Languages
history: []
agent_profile: python-pedro
authoritative_surface: src/charter/activation/synthesizer/
create_intent:
- src/charter/activation/language_authority.py
- tests/charter/synthesizer/test_multi_language_evidence.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/agent/cli/commands/test_charter_status_cli.py
- tests/agent/cli/commands/test_charter_synthesize_cli.py
- src/charter/activation/language_authority.py
- src/charter/activation/evidence/code_reader.py
- src/charter/activation/synthesizer/evidence.py
- src/charter/activation/synthesizer/request.py
- src/charter/activation/synthesizer/write_pipeline.py
- src/specify_cli/cli/commands/charter/_status_collectors.py
- src/specify_cli/cli/commands/charter/status.py
- src/specify_cli/cli/commands/charter/synthesize.py
- tests/charter/synthesizer/test_multi_language_evidence.py
- tests/charter/synthesizer/test_request.py
- tests/charter/synthesizer/test_write_pipeline.py
- tests/charter/synthesizer/test_evidence.py
- docs/adr/3.x/2026-04-17-1-charter-synthesizer-adapter-seam.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Multi-language evidence, neutrality gate, stable hash, JSON

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## Objective

Describe polyglot repositories in synthesis evidence and gate them correctly. Keep the evidence identity stable for single-language repositories, and expose `languages` additively in JSON (FR-010, FR-011, FR-012, FR-014).

## Context

- Read `spec.md` (User Story 3, scenarios 1, 2, 6; NFR-005) and `plan.md` (D-06). WP04 delivered the catalog and authority.
- **Evidence model:** `synthesizer/evidence.py` (`CodeSignals`, around lines 33-59), where `scope_tag` must equal `primary_language`.
- **Hash:** `synthesizer/request.py` (around lines 195-205 for evidence, and the ADR-guarded `normalize_request_for_hash` around 236-260).
- **Neutrality gate:** `write_pipeline.py` `_is_generic_scoped` (around lines 308-337).
- **JSON:**
  - `cli/commands/charter/_status_collectors.py` (around line 372)
  - `status.py` (around line 193)
  - `synthesize.py` (around lines 414-442)
- The corpus is still loaded by primary language only. Say so in a code comment where it is chosen.

### Subtask T021: Red-first tests

- `tests/charter/synthesizer/test_multi_language_evidence.py` (`@pytest.mark.regression`, #6444):
  - **Kotlin and TypeScript:** a fixture with root `build.gradle.kts`, mostly `.kt` sources, and a root `package.json` with `.ts` sources gives `languages` with both, primary first.
  - **Single-language hash:** a Python-only fixture's evidence-bundle hash is byte-identical to the value computed by today's code. Pin the literal hash captured on `main` before your change.
  - **Residue below the threshold:** a Python repository with a few `.js` config files lists only `python`, because 20% is the inclusion threshold.
  - **Gate:** it exempts a slug naming any observed or declared language, or a family of one (`jvm-…` for a Kotlin repository).
  - **JSON:** `charter status --json` and `charter synthesize --dry-run --json` carry `languages`, and every existing key is unchanged.
  - **Nested manifests:** a polyglot repository whose manifests are all nested still lists both languages.
  - **Languages without doctrine:** `go` and `rust` are listed even though no doctrine exists for them.
  - **Corpus:** it is chosen by the primary language only.
- Confirm they fail before the fix.

### Subtask T022: Observed languages (FR-010)

- In `language_authority`, add `observe_languages(repo_root, max_depth) -> ObservedLanguages(primary, languages)`:
  - include every language with a manifest at the shallowest manifest depth, plus any language whose source share is ≥ 20% of counted sources;
  - order: primary first, then by source count descending, then catalog order.
- **Cost (NFR-005):** run the uncapped source count only when a JVM manifest, or two or more candidate languages, are present. Keep `tests/charter/synthesizer/test_performance_envelopes.py` green.
- Wire `code_reader` to fill `CodeSignals.languages`.

### Subtask T023: Evidence model and hash (FR-012)

- In `CodeSignals`, add `languages: tuple[str, ...] = ()`, with the invariant `not languages or languages[0] == primary_language`. Keep `primary_language`, `scope_tag` and `stack_id`.
- In `request.py`, add `"languages": list(languages)` to the hashed evidence only when `len(languages) > 1`.
- Amend `docs/adr/3.x/2026-04-17-1-charter-synthesizer-adapter-seam.md` with a dated 2026-10-19 note:
  - the evidence hash includes `languages` only for polyglot repositories;
  - Kotlin repositories change hash, because their primary language changes.

### Subtask T024: Neutrality gate (FR-011)

- `_is_generic_scoped` treats a slug as language-scoped when any of its components is in `expand_language_families(observed languages ∪ declared languages)`.
- Take the declared languages from `stage_and_validate(request)` → `request.interview_snapshot["language_scope"]` (or the `languages_frameworks` alias, resolved through `language_authority`), and pass them into `_run_neutrality_gate`.

### Subtask T025: JSON surfaces and pinned tests (FR-014)

- Add `languages` next to `primary_language` in the three CLI surfaces, keeping the text output readable.
- Update `test_evidence.py`, `test_request.py` and `test_write_pipeline.py` only where this WP intentionally changed behaviour, and list each change.
- If `tests/architectural/test_json_contract_enumeration.py` enumerates these payloads, run it, and report any needed update to the orchestrator.

## Definition of Done

- The T021 tests were red before the fix and are green after it, and the markers are converted.
- These pass:
  - `tests/charter/synthesizer/`, `tests/charter/evidence/`
  - `tests/agent/cli/commands/test_charter_status_cli.py`, `tests/agent/cli/commands/test_charter_synthesize_cli.py`
  - `tests/architectural/test_json_contract_enumeration.py`, `tests/architectural/test_no_dead_symbols.py`
- ruff, format and `mypy --strict` are clean; complexity ≤ 15.

## Risks

- **A hash change for single-language repositories would make every provenance look new.** Pin the literal value.
- **Performance of the uncapped walk.**

## Reviewer Guidance

- Single-language hash identity: the literal is pinned.
- The threshold value is documented.
- No JSON key was removed or renamed.
