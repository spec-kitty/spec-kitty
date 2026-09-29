---
work_package_id: WP02
title: Reserved unknown vocabulary, validator guard, catalog-miss advice, advisory text
dependencies: []
requirement_refs:
- C-001
- C-002
- C-005
- FR-009
- FR-010
planning_base_branch: issue-5283-tech-agnostic-language-fallback
merge_target_branch: issue-5283-tech-agnostic-language-fallback
branch_strategy: Planning artifacts for this mission were generated on issue-5283-tech-agnostic-language-fallback. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5283-tech-agnostic-language-fallback unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-tech-agnostic-language-fallback-01M3NP53
base_commit: a2060146a75be1a4f614a859d5a86433924f4a3d
created_at: '2026-09-29T05:12:08.820225+00:00'
subtasks:
- T009
- T010
- T011
- T012
- T013
phase: Phase 2 - Language vocabulary foundation (lane B)
history:
- at: '2026-09-29T06:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/charter/offering/shared/
create_intent:
- src/charter/activation/language_advisory.py
- tests/charter/test_language_advisory.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/charter/offering/shared/scoping.py
- src/specify_cli/cli/commands/doctrine.py
- src/charter/activation/_catalog_miss.py
- src/charter/activation/language_advisory.py
- tests/doctrine/shared/test_scoping_any_all.py
- tests/doctrine/test_doctrine_validate_lang_guard.py
- tests/charter/test_context_catalog_miss.py
- tests/charter/test_language_advisory.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP02 – Reserved unknown vocabulary, validator guard, catalog-miss advice, advisory text

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill (canonical: `spk-doctrine-profile-load`) to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Reviewers load `reviewer-renata` (reviewer ≠ implementer).

---

## ⛔ HARD RULE — NO_FULL_HEAVY_SUITES_IN_MISSION (verbatim, binding for implementer AND reviewer)

During implement and every WP review, you must NEVER run full or heavy suites:
- no whole `tests/architectural/`, no e2e or full-integration suites, no performance/stress/timing suites;
- no `make test-full`, no whole-repo pytest.

Per WP, run only:
- the test files covering the files the WP touches;
- the owning module's fast tier;
- the specific NAMED architectural gate files the change implicates.

Leave broad sweeps to the END of the mission (closeout) or to CI.

---

## ⚠️ Post-tasks squad corrections (BINDING — supersede any conflicting guidance further below)

- Truth-table rows that already hold on the base (e.g. `([python],[unknown])` → False, `([], [unknown])` → True) are GREEN controls; RED rows are `([unknown],[unknown])` → False, `([unknown],None)` → False, `([python],[python, unknown])` stays True (control) and all `is_unknown_language` cases. FR-009's end-to-end non-vacuity lives in WP03/WP05; this WP pins the matcher contract.
- `scoping.py` has no `__all__` today: add one listing the existing public names plus the new ones. Dead-symbol gate (observed): an `__all__` name needs a caller OUTSIDE its module — so `UNKNOWN_LANGUAGE` must be imported by `_catalog_miss.py` (or `doctrine.py`) in this WP; `RESERVED_LANGUAGE_TOKENS` by `doctrine.py`; `is_unknown_language` by `_catalog_miss.py`; `CHARTER_EXTENSION_ADVISORY` by `_catalog_miss.py`.
- The catalog-miss function is `classify_scope_filtered_miss` (`_catalog_miss.py:261`; real caller `context_renderers/catalog_diagnosis.py:57`).
- Advisory neutrality: run the constant through the neutrality lint's banned-term matcher (`charter.activation.neutrality` — find the public matcher used by `tests/charter/test_neutrality_lint.py`) instead of only a hand-written substring list; keep the substring assertions as a second check.
- **Red→green proof (reviewer, mandatory):** re-run the new tests after `git checkout <base> -- src/charter/offering/shared/scoping.py src/specify_cli/cli/commands/doctrine.py src/charter/activation/_catalog_miss.py` (then `git checkout HEAD -- src/charter/offering/shared/scoping.py src/specify_cli/cli/commands/doctrine.py src/charter/activation/_catalog_miss.py`): they must be RED for the intended reason (an assertion, never an ImportError/collection error) and GREEN again at the tip. Base = the planning base branch.
- **Red-first labelling:** in the red-first commit, every test is labelled in its docstring either `RED (pins the fix)` or `GREEN control (pins unchanged behaviour)`. Controls may pass on the base; only RED tests must fail. New names that do not exist on the base are imported function-locally (or referenced as literals) so the base can still collect the module.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks and use language identifiers in code blocks.

---

## Objectives & Success Criteria

Foundation for #5284. Introduce the reserved language value **`unknown`** at the lowest layer with these exact semantics (post-plan squad M2/M3, data-model.md):

- `UNKNOWN_LANGUAGE = "unknown"` and `RESERVED_LANGUAGE_TOKENS = frozenset({UNKNOWN_LANGUAGE})` live in `charter.offering.shared.scoping` (lowest layer). `is_unknown_language(languages: Iterable[str] | None) -> bool` returns True iff the normalized set, after removing nothing else, equals `{"unknown"}` (i.e. the project is an unknown-language project) — hand-edited `[python, unknown]` is NOT unknown-language.
- `applies_to_languages_match(artifact, active)` strips reserved tokens from BOTH sides before its existing logic:
  - artifact scope empty after stripping (it was only `[unknown]`) → **False** (invalid scope; the validator is the authoring signal; never load it, for unknown or any other project);
  - active set empty after stripping (active was `[unknown]`) → **False** for every scoped artifact (admit none); unscoped artifacts still load (unchanged rule);
  - `[python, unknown]` behaves exactly like `[python]`;
  - `any`/`all` keep their existing always-load behaviour; `None` active still admits all; `[]` active still admits none.
- `doctrine validate` rejects `applies_to_languages: [unknown]` with its own message (reserved value set by Spec Kitty for unrecognised project languages; artifacts cannot target it), and the validator imports the sentinel/reserved sets from `scoping` instead of duplicating them.
- A scope-filtered catalog miss for an unknown-language project suggests extending the local charter (the advisory) instead of "add the active language to applies_to_languages".
- One consumer-facing constant `CHARTER_EXTENSION_ADVISORY` in `src/charter/activation/language_advisory.py` — a single short line, tech-agnostic, e.g.: "No specialist guidance exists for this project's language; add tech-specific guidelines to your local charter (see 'Extend your charter for an unsupported language')." It is product code, not a pack artifact (C-005).

## Context & Constraints

- Charter (binding): `.kittify/charter/charter.md` — ATDD/red-first (C-011): the failing test is committed as its own commit BEFORE the fix; reviewer verifies red on the planning base and green at the WP tip.
- Mission docs: `kitty-specs/tech-agnostic-language-fallback-01M3NP53/{spec.md,plan.md,research.md,data-model.md,contracts/cli-outputs.md,quickstart.md}`; tracer files under `traces/` — append a dated 1–3 sentence entry for any tooling friction, approach change, or design decision you make.
- Operator policy (#2330 decision): Spec Kitty doctrine is tech-agnostic; default implementation profile `implementer-ivan`; unknown languages → advise extending the local charter; NEVER fix by adding languages one by one; NEVER suggest Python files/layouts/tools to a non-Python project.
- Sibling-owned, do NOT edit: `src/specify_cli/consolidation/**`, `tests/integration/**`, golden/snapshot fixtures (`tests/specify_cli/skills/__snapshots__/**`, `tests/cli/__snapshots__/**`, `tests/consolidation/merge_driver_goldens/**`, `tests/contract/snapshots/**`), doctor/decision surfaces, `review/arbiter.py`, move-task override, built-in software-dev guidelines (#5202).
- Code quality: `ruff check`, `ruff format --check`, `mypy` (strict) clean on touched files; cyclomatic complexity ≤15; no new `# noqa`/`# type: ignore`; every new branch/helper gets a focused test in the same commit; modules under `src/charter/**` keep `__all__` and every exported name needs a caller in `src/` (dead-symbol gate).
- Terminology canon: Mission, never "feature", in any new prose/identifier.
- In a lane worktree always run tools via `uv run --frozen ...` or the worktree's own interpreter so the LANE `src/` is imported (bare `python`/`pytest` may import the primary checkout).

### Grounded seams

- `scoping.py:15` `_SENTINEL_TOKENS = {"any","all"}` (treated as UNSCOPED → always load, `:59`). **Do not add `unknown` there.**
- `applies_to_languages_match` docstring rules at `scoping.py:34-60`; `normalize_languages` above it.
- Validator duplicate set: `src/specify_cli/cli/commands/doctrine.py:768` `_APPLIES_TO_LANGUAGES_SENTINELS`, `_check_applies_to_languages` `:771-793` (message hardcodes "`any`/`all`").
- Catalog miss: `src/charter/activation/_catalog_miss.py:285-300` (scope-filtered suggestion).
- Consumers of the matcher (behaviour must stay correct, no edits expected): `charter/offering/base.py:194`, `agent_profiles/repository.py:542` (language-scoped profiles like python-pedro drop out for an unknown project — intended), styleguide/toolguide/tactic/procedure repositories.
- Layering: `charter.offering` must not import `charter.activation` or `specify_cli`. `language_advisory.py` is in `charter.activation`.

## Branch Strategy

- **Strategy**: lanes (no coordination branch)
- **Planning base branch**: issue-5283-tech-agnostic-language-fallback
- **Merge target branch**: issue-5283-tech-agnostic-language-fallback

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; prepare yours with `spec-kitty agent action implement WP02 --agent claude`.

## Subtasks & Detailed Guidance

### Subtask T009 – Red-first tests (commit alone, RED)

- `tests/doctrine/shared/test_scoping_any_all.py`: add a parametrized truth table for `applies_to_languages_match` covering (artifact, active) = ([python], [unknown]) → False; ([], [unknown]) → True; (None, [unknown]) → True; ([unknown], [unknown]) → False; ([unknown], [python]) → False; ([unknown], None) → False; ([python], [python, unknown]) → True; ([any], [unknown]) → True (unchanged sentinel rule); ([python], None) → True; ([python], []) → False. Plus `is_unknown_language` cases: None → False, [] → False, ["unknown"] → True, ["UNKNOWN "] → True, ["python","unknown"] → False.
- `tests/doctrine/test_doctrine_validate_lang_guard.py`: an artifact YAML with `applies_to_languages: [unknown]` → validation error whose message says `unknown` is reserved (and is NOT the any/all message); `[Unknown]` also rejected; `[python]` passes (control).
- `tests/charter/test_context_catalog_miss.py`: scope-filtered miss with active `["unknown"]` → suggestion contains the advisory's charter-extension wording and does NOT say "Add the active language"; active `["python"]` → existing suggestion unchanged (control).
- `tests/charter/test_language_advisory.py`: advisory is one line, ≤ 200 chars, contains "local charter", contains none of `python`, `pytest`, `.py`, `src/` (case-insensitive), and names the how-to title "Extend your charter for an unsupported language".
- All new assertions must fail now. Commit `test(charter): red-first reserved unknown language vocabulary (#5284)`.

### Subtask T010 – scoping.py

- Add `UNKNOWN_LANGUAGE`, `RESERVED_LANGUAGE_TOKENS`, `is_unknown_language`; implement strip-both-sides in `applies_to_languages_match` (compute stripped tuples up front; keep complexity ≤15 by a tiny `_strip_reserved` helper). Update the docstring rules list. Export via `__all__` if the module declares one (charter convention C-007 — add `__all__` if absent).

### Subtask T011 – doctrine.py validator

- Import `_SENTINEL_TOKENS`-equivalent public names from `scoping` (make public aliases there if needed, e.g. `SENTINEL_LANGUAGE_TOKENS`) and delete the duplicate `_APPLIES_TO_LANGUAGES_SENTINELS`; emit the existing any/all message for sentinels and a distinct message for reserved tokens. Keep the function's complexity ≤15.

### Subtask T012 – language_advisory.py

- New module with a module docstring, `__all__ = ["CHARTER_EXTENSION_ADVISORY"]`, the constant, and nothing else. Its first `src/` caller is `_catalog_miss.py` (T013) — required by the dead-symbol gate.

### Subtask T013 – catalog-miss branch

- In the scope-filtered path: if `is_unknown_language(active_languages)`, return a suggestion built from `CHARTER_EXTENSION_ADVISORY` (e.g. "artifact '<id>' is scoped to specific languages and does not apply to a project whose language Spec Kitty does not recognise. " + advisory). Otherwise unchanged.

## Test Strategy

- `uv run --frozen pytest tests/doctrine/shared/test_scoping_any_all.py tests/doctrine/test_doctrine_validate_lang_guard.py tests/charter/test_context_catalog_miss.py tests/charter/test_language_advisory.py -q`
- Fast tier of the owning modules: `uv run --frozen pytest tests/doctrine/shared/ tests/charter/test_catalog.py -q` and any test file importing `applies_to_languages_match` (`grep -rl applies_to_languages_match tests/ --include=*.py`) — run those files only.
- Named arch gates: `uv run --frozen pytest tests/architectural/test_no_dead_symbols.py tests/architectural/test_layer_rules.py -q`.
- ruff check/format + `mypy` on the four touched src files.

## Risks & Mitigations

- Adding `unknown` to sentinels would load such artifacts everywhere — explicitly tested.
- Changing matcher semantics for `None`/`[]` would regress #3292 — truth-table rows pin them.

## Definition of Done

- [ ] Red commit first; truth table, validator, catalog-miss, advisory tests green at tip.
- [ ] No duplicate sentinel set remains in `doctrine.py`.
- [ ] Dead-symbol + layer-rule gates green; ruff/format/mypy clean.

## Review Guidance

Verify the truth table exactly matches data-model.md; verify no behavioural change for `None`, `[]`, `any`/`all`; verify the advisory is neutral and one line; verify `charter.offering` gained no upward import. Targeted commands only (HARD RULE).

## Activity Log

> Append entries at the END, oldest first: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>` (UTC now: `date -u "+%Y-%m-%dT%H:%M:%SZ"`).

- 2026-09-29T06:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status; record subtasks with `spec-kitty agent tasks mark-status <Txxx> --status done`.
