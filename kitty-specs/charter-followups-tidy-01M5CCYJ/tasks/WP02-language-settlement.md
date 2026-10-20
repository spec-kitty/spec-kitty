---
work_package_id: WP02
title: 'Language settlement: one-way dependency, write with the answers (#6540, #6542)'
dependencies: []
requirement_refs:
- C-005
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- SC-003
- SC-005
planning_base_branch: tidy-charter-6539-followups
merge_target_branch: tidy-charter-6539-followups
branch_strategy: Planning artifacts for this mission were generated on tidy-charter-6539-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into tidy-charter-6539-followups unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-followups-tidy-01M5CCYJ
base_commit: 9c9041ed2b8ea1fb3819d4e264c2688159c4920c
created_at: '2026-10-20T11:45:36.620987+00:00'
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
phase: Phase 1 - Parallel work packages
history:
- at: '2026-10-20T11:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- src/charter/activation/language_settlement.py
- tests/charter/test_language_settlement.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/charter/activation/language_settlement.py
- src/charter/activation/language_authority.py
- src/charter/activation/api.py
- src/specify_cli/cli/commands/charter/interview.py
- tests/charter/test_language_settlement.py
- tests/charter/test_configured_languages.py
- tests/charter/test_language_authority.py
- tests/specify_cli/cli/commands/charter/test_interview_languages.py
- tests/architectural/test_charter_activation_api_reexport.py
- docs/api/charter-commands.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Language settlement: one-way dependency, write with the answers (#6540, #6542)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter (`python-pedro`, role `implementer`). Behave according to it before reading the rest of this prompt. If the skill is unavailable, read `packs/built-in/agent_profiles/python-pedro.agent.yaml` directly.

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` in the event log (`spec-kitty agent tasks status --mission charter-followups-tidy-01M5CCYJ`). If this WP came back from review, every feedback item is your TODO list. Record what you changed with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

Issues #6540 and #6542. Operator decision: `interview_language_write_order`.

- **#6540, the import cycle.** The language settlement moves into a new module, `src/charter/activation/language_settlement.py`, which imports `charter.activation.language_authority` and `charter.activation.evidence.code_reader` at module level.
  - `language_authority` no longer imports `code_reader` anywhere: not in a function body, not under `TYPE_CHECKING`.
  - The only edge between those two modules stays code reader → authority.
  - The deferred import in `_detect_repository_languages` (about :449-451) is gone.
- **#6542, the write order.** Settling the languages decides; it does not write.
  - A new public `store_language_settlement(repo_root, settlement)` performs the `config.yaml` write.
  - `charter interview` still settles, and asks, at the same point (about :310). It calls the store **after `write_interview_answers` and before `_promote_interview_selections`**. Promotion re-reads `config.yaml`, so it keeps the languages.
  - An interview that aborts or fails before the answers are written writes neither.
- **Unchanged:**
  - the interview JSON keys `languages`, `languages_source` and `languages_notice`;
  - the never-overwrite rule `DM-01M5ASPC7101YP5CQE54DC3G3Z`: store the detected list non-interactively only when the key is absent, notify, and never overwrite a set key, usable or not;
  - the interactive confirmation flow;
  - evidence and bundle hashes (NFR-004).
- **A store failure after the answers are written** is surfaced: a non-zero exit with a visible error, never swallowed. The JSON output, when printed, must not claim the languages were stored.
- Spec: User Stories 2 and 4; FR-004/005/006; C-005; SC-003/005.

## Context & Constraints

- Read `.kittify/charter/charter.md`. Red-first (NFR-003); no new suppressions (NFR-001); complexity ≤ 15 (NFR-002).
- **Current code:**
  - `src/charter/activation/language_authority.py`:
    - `LanguageSettlement`, `parse_language_answer`, `_ask_until_valid`, the notices (`_detected_notice`, …), `_settle_without_asking` (about :495-509, which writes) and `settle_project_languages` (about :512-543, which writes on the interactive path at about :537-543);
    - `_detect_repository_languages` (about :449, with the deferred import);
    - `write_configured_languages` and `configured_languages`.
  - `src/charter/activation/evidence/code_reader.py:16` imports `EXCLUDED_DIRS`, `TreeObservation`, `ObservedLanguages`, `configured_languages`, `count_sources_uncapped` and `resolve_languages` from the authority. These stay in the authority.
  - `src/charter/activation/api.py` (about :110) re-exports `settle_project_languages`, `configured_languages` and `LanguageSettlement`.
  - `tests/architectural/test_charter_activation_api_reexport.py:50-52` pins those to `charter.activation.language_authority`.
  - `tests/architectural/test_language_excluded_dirs_cover_agent_dirs.py:15` pins `EXCLUDED_DIRS` to the authority. **Do not move `EXCLUDED_DIRS`.**
  - `src/specify_cli/cli/commands/charter/interview.py`:
    - `_settle_languages` (about :206-217) calls `charter.activation.api.settle_project_languages`;
    - the settlement happens at about :310;
    - the questions run at about :316-388, the answers are written at about :420-421, and the promotion happens at about :427-432;
    - the JSON keys are at about :450-452;
    - the generic `except` sits at about :476-481.
- **`specify_cli` should reach activation through `charter.activation.api`.** `interview.py` already has one local exception: about :258-264 it imports `write_interview_answers` from `charter.activation.interview` inside the function. Do not add new direct imports.
- ADR 2026-10-16-1: activation stays in core, so changing the `charter.activation.api` settlement surface is allowed. Keep `settle_project_languages` as the decide entry point (same name), and add `store_language_settlement`.

## Branch Strategy

- **Strategy**: lanes_with_coord (populated by finalize-tasks)
- **Planning base branch**: tidy-charter-6539-followups
- **Merge target branch**: tidy-charter-6539-followups

The execution worktree is allocated per computed lane from `lanes.json`. Start with `spec-kitty agent action implement WP02 --agent claude --mission charter-followups-tidy-01M5CCYJ`.

## Subtasks & Detailed Guidance

### Subtask T007 – Red-first tests

- **Files**: `tests/charter/test_language_settlement.py` (new) and `tests/specify_cli/cli/commands/charter/test_interview_languages.py`.
- **Tests**:
  1. **AST import test.** Parse `language_authority.py` and `evidence/code_reader.py` with `ast`. Assert:
     - neither imports the other inside a function body or under `if TYPE_CHECKING:`;
     - `language_authority` does not import `code_reader` at all;
     - `language_settlement` imports both at module level.

     It is red today because of the deferred import.
  2. **Settling writes nothing.** `settle_project_languages(...)` on a tmp project with no key, non-interactive, leaves `config.yaml` without `languages:`. The returned settlement carries the detected list and the notice. Red today, because it writes.
  3. **Store writes, and never overwrites.**
     - `store_language_settlement` on that settlement writes the list.
     - When the key was already set, the settlement says nothing is to be written, and `config.yaml` is unchanged. Use both a usable value and an unusable one, such as a scalar.
  4. **Interview abort before the answers.** Drive `charter interview` through the CLI test harness this file already uses:
     - non-TTY, without `--defaults`, empty stdin, so a prompt raises `typer.Abort` after the language step;
     - no key beforehand.

     After the run: `config.yaml` has no `languages:` key and no answers file exists.
  5. **Answers write fails.** Monkeypatch `charter.activation.interview.write_interview_answers` to raise. Patch it there, because `interview.py` imports it inside the function. After the run, `config.yaml` has no `languages:` key.
  6. **Interactive change, then abort.** The operator confirms a changed list, then a later prompt aborts. The previous `languages:` value is unchanged.
  7. **Completed run.**
     - The answers and `languages:` are both written.
     - The JSON keys are present and their values are unchanged.
     - Promotion still sees the languages: `config.yaml` after the run carries both the promoted `activated_*` changes and `languages:`.
  8. **Store fails after the answers.** Monkeypatch the store to raise.
     - The command exits non-zero with a visible error.
     - The generic `except Exception` (about :479) catches it and exits 1 through `_emit_error`. Assert exit 1, the error payload, and no `"success": true`; the success JSON is printed only later (about :437). Do not invent a new `languages_notice` value.
- **Interactivity controls.** Settlement asks only when `not use_defaults and is_interactive()`. `is_interactive` reads `SPEC_KITTY_NON_INTERACTIVE` and `SPEC_KITTY_FORCE_INTERACTIVE` (`src/specify_cli/core/env.py` about :38-50), and the agent harness exports `SPEC_KITTY_NON_INTERACTIVE`.
  - In tests 4 and 6, call `monkeypatch.delenv("SPEC_KITTY_NON_INTERACTIVE", raising=False)` first.
  - Test 6 then sets `SPEC_KITTY_FORCE_INTERACTIVE=1`, or monkeypatches `is_interactive`.
  - An `Abort` from `typer.prompt` is also caught at about :479 and exits 1.
- Run them on the unchanged source and record the failures with `add-history`. Do not leave `@pytest.mark.regression` markers behind.

### Subtask T008 – New settlement module

- **Create `src/charter/activation/language_settlement.py`.** Give it a module docstring: it owns the decide flow (detect, propose or ask, and decide what to store) and the store step, and why it sits above both the authority and the code reader (#6540).
- **Move into it from `language_authority`:**
  - `LanguageSettlement`;
  - `parse_language_answer`, the ask loop (`_ask_until_valid`) and `LANGUAGE_ANSWER_ATTEMPTS`;
  - the notice builders;
  - the non-interactive decision;
  - `settle_project_languages`;
  - the repository detection (`_detect_repository_languages`), now importing `CodeReadingCollector` at module level.
- **Keep in `language_authority`:** `EXCLUDED_DIRS`, the observation types, `configured_languages`, `write_configured_languages`, `resolve_languages` and the catalog-backed vocabulary helpers. That is everything `code_reader` and other callers import. Grep for every importer of each moved name (`grep -rn "<name>" src tests`) and repoint it.
- Keep each function at complexity ≤ 15.

### Subtask T009 – Decide/store split

- `settle_project_languages(repo_root, *, ask=None, on_invalid=None)` keeps its current decision logic but performs **no write**. `LanguageSettlement` gains whatever it needs to say what to store: for example a `to_store: tuple[str, ...] | None` field, or the existing `written` flag renamed to its new meaning, such as `pending_write`. Pick names that read truthfully; "written" would now be false.
- `store_language_settlement(repo_root, settlement) -> None` calls `write_configured_languages` only when the settlement has something to store. It is idempotent.
- Keep the never-overwrite rule exactly as it is (C-005). Read the existing tests in `tests/charter/test_configured_languages.py` and `test_language_authority.py`; they pin it. Update any test that asserted the old write-inside-settle behaviour so it calls the store, and keep its intent.

### Subtask T010 – `charter.activation.api` and its gate

- `src/charter/activation/api.py`:
  - re-export `settle_project_languages`, `LanguageSettlement` and the new `store_language_settlement` from `charter.activation.language_settlement`;
  - re-export `configured_languages` from the authority, as before.
- `tests/architectural/test_charter_activation_api_reexport.py`: repoint the pinned origins to `charter.activation.language_settlement`, and add a row for `store_language_settlement`.
- Run `tests/architectural/test_runtime_charter_activation_boundary.py`, `test_layer_rules.py`, `test_no_dead_symbols.py` and `test_language_excluded_dirs_cover_agent_dirs.py`.

### Subtask T011 – Interview wiring

- `interview.py`:
  - `_settle_languages` still runs at the same point (settle and ask).
  - Hold the returned settlement.
  - Immediately after `write_interview_answers(...)` succeeds, call `store_language_settlement(repo_root, settlement)` through `charter.activation.api`, **before** `_promote_interview_selections`.
  - If the store raises, the existing generic handler (about :479) exits 1 through `_emit_error`. Confirm the message names the languages store; do not add a second handler.
  - Keep the JSON keys.
- Check every exit path between :310 and :421 (`typer.Abort`, `KeyboardInterrupt`, Decision Moment errors, `ValueError` from answer overrides): none of them may write `languages:`. That holds automatically once nothing writes before the store, but the tests must prove it.

### Subtask T012 – Docs

- `docs/api/charter-commands.md`, in the `charter interview` section that describes `languages:` and the non-interactive notice: state that the languages are stored together with the answers, and that an aborted interview stores neither.
- Keep the text short and in the file's style.
- Run `PYTHONPATH=. uv run --frozen python scripts/docs/check_docs_freshness.py --ci` and `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py`.

## Test Strategy

- **Red-first:** every new test fails on the unchanged source. Record those runs with `add-history`.
- **Blast radius, run all of it:**
  - `uv run --frozen pytest tests/charter/ tests/charter_offering/ -n 4 --dist loadfile`
  - `uv run --frozen pytest tests/specify_cli/cli/commands/charter/ -n 4 --dist loadfile`. This dir is out of the PR CI matrix, so it must be green locally. The `test_resynthesize_and_hotpath` stays-stale pair is a known red (#6536).
  - `uv run --frozen pytest tests/agent/cli/commands/test_charter_synthesize_cli.py tests/agent/cli/commands/test_charter_status_cli.py`
- **Gates:** `tests/architectural/test_charter_activation_api_reexport.py`, `test_runtime_charter_activation_boundary.py`, `test_layer_rules.py`, `test_no_dead_symbols.py`, `test_no_dead_modules.py`, `test_language_excluded_dirs_cover_agent_dirs.py`, `test_single_language_vocabulary.py`.
- **Baseline:** `make test-fast`.
- **Static checks:** ruff, `ruff format --check --force-exclude` and mypy on the changed files, with 0 new issues.

## Risks & Mitigations

- **Missing importers of the moved names:** grep `src/` and `tests/` for each moved name before you finish.
- **Promotion overwrites `languages:`:** it loads and saves `config.yaml`. Storing first, then promoting, keeps the key, and test 7 proves it.
- **Hash drift:** run `tests/charter/test_synthesized_in_force_snapshot.py` and `tests/charter/test_default_in_force_snapshot.py` (NFR-004).

## Review Guidance

- No function-level or `TYPE_CHECKING` import between the authority and the code reader.
- Settling writes nothing; the store is the only writer in the interview flow.
- The store is called after the answers and before promotion.
- The abort tests really abort after the language step, not before it.
- The never-overwrite rule is intact.
- The JSON keys are unchanged.
- A store failure is surfaced.

## Progress & Status

Record progress with `spec-kitty agent tasks mark-status Txxx --status done --mission charter-followups-tidy-01M5CCYJ` and `add-history`.
