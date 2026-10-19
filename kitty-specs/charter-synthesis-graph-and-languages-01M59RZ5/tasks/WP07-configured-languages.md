---
work_package_id: WP07
title: 'Configured project languages: detect at interview, store in config.yaml, adhere'
dependencies:
- WP05
requirement_refs:
- FR-020
- FR-009
- SC-006
planning_base_branch: issue-6442-charter-synthesis-graph-work
merge_target_branch: issue-6442-charter-synthesis-graph-work
branch_strategy: Planning artifacts for this mission were generated on issue-6442-charter-synthesis-graph-work. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6442-charter-synthesis-graph-work unless the human explicitly redirects the landing branch.
subtasks:
- T030
- T031
- T032
- T033
phase: Phase 3 - Languages
history: []
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- src/charter/activation/language_authority.py
- tests/charter/test_language_authority.py
- tests/charter/test_configured_languages.py
- tests/specify_cli/cli/commands/charter/test_interview_languages.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/charter/activation/language_authority.py
- src/charter/activation/language_scope.py
- src/charter/activation/evidence/code_reader.py
- src/charter/activation/interview.py
- src/specify_cli/cli/commands/charter/interview.py
- tests/charter/test_configured_languages.py
- tests/charter/test_language_authority.py
- tests/charter/test_language_scope.py
- tests/specify_cli/cli/commands/charter/test_interview_languages.py
- docs/api/charter-commands.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Configured project languages: detect at interview, store in config.yaml, adhere

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## Objective

Store one operator-confirmed language list in `.kittify/config.yaml`. `charter interview` detects and proposes it. When the list is set, it is the single source for synthesis evidence `languages` and for doctrine scoping. Detection and free-text parsing remain only as the fallback (FR-020, plan D-11, decision DM-01M5AJ5X6FQD7CXK0TWARQPBEX).

## Context

- WP04 and WP05 built the catalog (`charter.offering.shared.language_catalog`) and the authority (`charter.activation.language_authority`: `resolve_languages` over the collector's single walk, `declared_languages`, family expansion at match time).
- Doctrine scoping reads `infer_repo_languages` (`language_scope.py`). That is stamped into charter.yaml `catalog.languages` by the compiler and read first at runtime.
- Evidence is filled in `evidence/code_reader.py`.
- Why this exists: the operator does not want heuristics such as a tooling-only `package.json` to decide the language list. The interview proposes, the operator confirms, and the stored list wins.

### Subtask T030: Brownfield read and key choice

- Find how `.kittify/config.yaml` is read and written today: grep for the loaders used by `charter_packs` / `activated_*`, `resolve_activation_write_target`, and the kernel path helpers.
- Pick a key that follows existing conventions, preferably under an existing charter-related section; otherwise a top-level `languages:` with a comment.
- Use atomic writes through the existing config writer, and never clobber other keys.
- Record the choice and why in the WP history; the orchestrator will put it in docs and the CHANGELOG.
- Also determine how `charter interview` collects answers: interactive, `--defaults`, and the non-interactive/JSON modes, since `SPEC_KITTY_NON_INTERACTIVE` may be set. Find where the `languages_frameworks` question is asked.

### Subtask T031: Red-first tests

- `tests/charter/test_configured_languages.py` (`@pytest.mark.regression`, #6444). With the key set to `[python]` in a repository that has a tooling-only root `package.json` plus `.js` config files:
  - evidence `languages == ("python",)` and `primary_language == "python"`;
  - `infer_repo_languages` returns `["python"]` regardless of the interview free text;
  - a `jvm`-tagged artifact still matches when the key is `[kotlin]` (expanded at match time; `jvm` is never written to the key).
- With the key absent, today's behaviour is unchanged: detection plus free-text parsing.
- An invalid entry (a token not in the catalog, or a family token such as `jvm`) is refused when written. On read it is dropped with a diagnostic, and the fallback is not silently used if valid entries remain. Pick and document the rule.
- `tests/specify_cli/cli/commands/charter/test_interview_languages.py`:
  - the interview proposes the detected languages;
  - the confirmed list is written to config.yaml;
  - a later interview shows the stored list as the default;
  - non-interactive or `--defaults` runs store the detected list only when the key is absent, and never overwrite an operator-set key.
- Confirm the tests fail on real assertions before the fix.

### Subtask T032: Implement

- **Authority:** `language_authority.configured_languages(repo_root) -> tuple[str, ...] | None` (a pure read), plus a writer used only by the interview.
- **Evidence:** `code_reader` uses the configured list when set. The primary language is the first entry; skip the source-count walk then, because NFR-005 wants nothing extra.
- **Doctrine scoping:** `infer_repo_languages` returns the configured list first when set (tier 0, ahead of `catalog.languages`), keeping its four-state contract.
- **Hash:** evidence hash rules are unchanged: the configured list enters only when it holds more than one language.
- **Interview:** add the detection proposal and write in the interview command. Keep the existing `languages_frameworks` question working.
- **Statics:** complexity ≤ 15, zero new `# noqa` / `# type: ignore`, `ruff format --check --force-exclude` before every commit, `mypy --strict` clean on new code.

### Subtask T033: Docs

- Document the key, the interview behaviour and the precedence in `docs/api/charter-commands.md`.

## Definition of Done

- The T031 tests were red before the fix and are green after it.
- These pass:
  - `tests/charter/evidence/`, `tests/charter/test_language_*.py`, `tests/charter/test_configured_languages.py`
  - `tests/specify_cli/cli/commands/charter/` (except the known baseline reds `test_resynthesize_and_hotpath.py::test_{activate,deactivate}_without_resynthesize_*`)
  - every test referencing `infer_repo_languages`
  - `tests/architectural/test_single_language_vocabulary.py`, `tests/architectural/test_layer_rules.py`, `tests/architectural/test_no_dead_symbols.py`, `tests/architectural/test_json_contract_enumeration.py`, `tests/charter/test_default_in_force_snapshot.py`

## Risks

- The interview runs in agent harnesses with `SPEC_KITTY_NON_INTERACTIVE=1`. Never block on input there.
- The config writer must preserve all other keys and their comments, if the existing writer does.

## Reviewer Guidance

- One stored list governs both evidence and scoping.
- Fallback behaviour is unchanged when the key is absent.
- An operator-set key is never overwritten by a non-interactive run.
