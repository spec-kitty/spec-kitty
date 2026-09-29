---
work_package_id: WP05
title: Neutral mission context + charter-extension advisory
dependencies:
- WP03
requirement_refs:
- C-002
- FR-009
- FR-010
- NFR-002
planning_base_branch: issue-5283-tech-agnostic-language-fallback
merge_target_branch: issue-5283-tech-agnostic-language-fallback
branch_strategy: Planning artifacts for this mission were generated on issue-5283-tech-agnostic-language-fallback. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5283-tech-agnostic-language-fallback unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-tech-agnostic-language-fallback-01M3NP53
base_commit: a2060146a75be1a4f614a859d5a86433924f4a3d
created_at: '2026-09-29T06:13:41.474210+00:00'
subtasks:
- T026
- T027
- T028
- T029
- T030
phase: Phase 4 - Charter context (lane B)
history:
- at: '2026-09-29T06:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/charter/activation/compact.py
create_intent:
- tests/charter/test_context_unknown_language.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/charter/activation/compact.py
- src/charter/activation/context_renderers/bootstrap_text.py
- tests/charter/test_context_unknown_language.py
- tests/charter/test_context_token_budget.py
- tests/charter/test_context_bootstrap_markers.py
- tests/charter/test_context_selection_render.py
- tests/charter/context_renderers/test_token_budget_sonar.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP05 – Neutral mission context + charter-extension advisory

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

- **Advisory placement (B6):** append the advisory BEFORE `_enforce_token_budget` (the budget only swaps named candidate blocks, `token_budget.py:587-640`, so it never drops a tail; tests pin the warning line as the last line and `len <= budget`, `test_context_token_budget.py:191-225,524`). The compact path also budgets (`compact_governance.py:172`) — same rule.
- Fixture (a) must be built by running `charter generate --from-interview` on a Zig `answers.yaml` (no stale seed — works with WP03 alone), exercising the real Zig→context path (SC-002); a hand-written `[unknown]` charter is only an additional unit-level case.
- Replace "no `python-` id" with: no id of ANY language-scoped shipped artifact appears (compute the set by scanning shipped artifacts with non-empty `applies_to_languages`), `python-pedro` absent, `implementer-ivan` present — in (a); `implementer-ivan` also present in (c). This also covers FR-009's profile half.
- Add control (d): stale `catalog.languages: [python]` + Zig answers, NO regeneration, `charter context` → `Languages: python` (US3 AS3 at CLI level; runtime stays compiled-first).
- Assert the JSON `mode` field (`bootstrap` then `compact`); first-load state lives in `.kittify/charter/context-state.json` (`context_state.py:95`); compact goes `compact_governance.py:105` → `render_compact_view`.
- **Red→green proof (reviewer, mandatory):** re-run the new tests after `git checkout <base> -- src/charter/activation/compact.py src/charter/activation/context_renderers/bootstrap_text.py` (then `git checkout HEAD -- src/charter/activation/compact.py src/charter/activation/context_renderers/bootstrap_text.py`): they must be RED for the intended reason (an assertion, never an ImportError/collection error) and GREEN again at the tip. Base = the **WP03 tip**.
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

#5284 rendering (FR-010). For a project whose resolved languages are `[unknown]` (WP03), `spec-kitty charter context --action <a> --mission-type software-dev` renders:

- **bootstrap (first load)**: the language-neutral guidance as today (context NOT empty; `implementer-ivan` defaults remain), exactly ONE advisory line (`CHARTER_EXTENSION_ADVISORY` from `charter.activation.language_advisory`, WP02), no Python-scoped (or any language-scoped) artifact ids such as `python-conventions`, `python-review-checks`, `python-mutation-tools`;
- **compact (subsequent loads)**: `  - Languages: unknown` followed by exactly ONE advisory line; no `Languages: python`.
- Positive controls: a Python-declaring project still lists `python-conventions` (bootstrap) and `Languages: python` (compact) with NO advisory; a default-interview project (languages absent) shows neither a Languages line nor the advisory (today's behaviour).
- Renderers decide via `is_unknown_language(...)` (never compare the literal string `"unknown"`).
- Campsite: the two broad `except Exception: pass  # pragma: no cover` blocks in `compact.py` (~`:276-281` languages, `:283-288` doctrine root) are narrowed or removed with characterization tests, behaviour-preserving, in their own commit.

## Context & Constraints

- Charter (binding): `.kittify/charter/charter.md` — ATDD/red-first (C-011): the failing test is committed as its own commit BEFORE the fix; reviewer verifies red on the planning base and green at the WP tip.
- Mission docs: `kitty-specs/tech-agnostic-language-fallback-01M3NP53/{spec.md,plan.md,research.md,data-model.md,contracts/cli-outputs.md,quickstart.md}`; tracer files under `traces/` — append a dated 1–3 sentence entry for any tooling friction, approach change, or design decision you make.
- Operator policy (#2330 decision): Spec Kitty doctrine is tech-agnostic; default implementation profile `implementer-ivan`; unknown languages → advise extending the local charter; NEVER fix by adding languages one by one; NEVER suggest Python files/layouts/tools to a non-Python project.
- Sibling-owned, do NOT edit: `src/specify_cli/consolidation/**`, `tests/integration/**`, golden/snapshot fixtures (`tests/specify_cli/skills/__snapshots__/**`, `tests/cli/__snapshots__/**`, `tests/consolidation/merge_driver_goldens/**`, `tests/contract/snapshots/**`), doctor/decision surfaces, `review/arbiter.py`, move-task override, built-in software-dev guidelines (#5202).
- Code quality: `ruff check`, `ruff format --check`, `mypy` (strict) clean on touched files; cyclomatic complexity ≤15; no new `# noqa`/`# type: ignore`; every new branch/helper gets a focused test in the same commit; modules under `src/charter/**` keep `__all__` and every exported name needs a caller in `src/` (dead-symbol gate).
- Terminology canon: Mission, never "feature", in any new prose/identifier.
- In a lane worktree always run tools via `uv run --frozen ...` or the worktree's own interpreter so the LANE `src/` is imported (bare `python`/`pytest` may import the primary checkout).

### Grounded seams

- `compact.py:107` `render_compact_view`, `:206` `_render_text`; languages footnote at `:275-281` (`infer_repo_languages(repo_root)` inside a broad except; renders only `if languages:`).
- `context_renderers/bootstrap_text.py:254` `_render_bootstrap_text`; has NO Languages line today; `_enforce_token_budget` runs last (`:347`) and may truncate/substitute sections — the advisory must be appended where the budget cannot drop it (e.g. after budgeting, or via a reserved tail the budget respects — read `context_renderers/token_budget.py`). `repo_root` is optional there — no repo root → no advisory.
- The language-scoped artifact exclusion itself is already delivered by WP02/WP03 (matcher + resolution); this WP must prove it end-to-end in the rendered context.
- CLI tests: `charter context --json` payload `text` field; first call is bootstrap, the next compact (see `tests/charter/test_context.py` for the session/state handling pattern).

## Branch Strategy

- **Strategy**: lanes (no coordination branch)
- **Planning base branch**: issue-5283-tech-agnostic-language-fallback
- **Merge target branch**: issue-5283-tech-agnostic-language-fallback

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; prepare yours with `spec-kitty agent action implement WP05 --agent claude`.

## Subtasks & Detailed Guidance

### Subtask T026 – Campsite (own commit FIRST)

- Characterize the current behaviour of the two guarded blocks (e.g. a repo with no charter / unreadable config → compact view still renders, no Languages line). Then narrow each `except Exception` to the concrete exceptions those calls can raise (read `infer_repo_languages` / `resolve_project_root`: file/yaml errors) or remove the guard if nothing can raise; no effect-free handler may remain (Sonar). Commit `refactor(charter): campsite compact view exception handling`.

### Subtask T027 – Red-first CLI tests (own commit, RED)

- New `tests/charter/test_context_unknown_language.py`: tmp project; write a compiled charter + answers for (a) Zig (`catalog.languages: [unknown]`), (b) Python, (c) default interview (languages absent). For each run `charter context --action specify --mission-type software-dev --json` twice (bootstrap then compact) through the typer app.
  - (a) bootstrap: `text.count(CHARTER_EXTENSION_ADVISORY) == 1`; no `python-` artifact id; guidance body non-empty (assert a stable neutral heading present in (c) too). compact: contains `Languages: unknown` and exactly one advisory; no `Languages: python`.
  - (b) bootstrap lists `python-conventions` (discover the exact shipped id); compact `Languages: python`; advisory count 0.
  - (c) no Languages line, advisory count 0.
- Must fail now for (a). Commit `test(charter): red-first neutral context for unknown languages (#5284)`.

### Subtask T028 – Compact render

- Replace the footnote: resolve languages once; if `is_unknown_language(languages)` → append `  - Languages: unknown` and the advisory line (prefixed consistently with the compact list style, e.g. `  - Advisory: <text>`); elif languages → today's line. Keep `_render_text` ≤15 complexity (extract `_append_language_lines`).

### Subtask T029 – Bootstrap render

- Resolve languages for `repo_root` (when present) and append the advisory exactly once, placed after/outside `_enforce_token_budget` so budgeting cannot drop it (and budget accounting stays correct — if the budget function asserts a max size, reserve the advisory length). No Languages line needed in bootstrap.

### Subtask T030 – Ripple

- Run the token-budget/marker/selection-render tests; re-pin ONLY assertions that legitimately change for an unknown-language fixture (none should change for existing fixtures — if one does, stop and investigate rather than re-pin). Record any re-pin with a dated rationale comment.

## Test Strategy

- `uv run --frozen pytest tests/charter/test_context_unknown_language.py tests/charter/test_context.py tests/charter/test_context_token_budget.py tests/charter/test_context_bootstrap_markers.py tests/charter/test_context_selection_render.py tests/charter/context_renderers/ -q`
- Neighbours: other `tests/charter/test_context_*.py` files that exercise compact/bootstrap (run those files only).
- ruff check/format + mypy on the two touched src files.

## Risks & Mitigations

- Budget truncation dropping the advisory → tested via count == 1 on a large charter fixture if budget applies.
- Rendering the advisory for default-interview projects → control (c).

## Definition of Done

- [ ] Campsite commit, red commit, fixes.
- [ ] (a)/(b)/(c) green in both renders; no broad effect-free except left in `compact.py`.
- [ ] Existing context tests green without unexplained re-pins; ruff/format/mypy clean; complexity ≤15.

## Review Guidance

Verify advisory exactly once per render, only for unknown projects; verify no literal-string `"unknown"` comparisons in renderers; verify campsite commit is behaviour-preserving. Targeted commands only (HARD RULE).

## Activity Log

> Append entries at the END, oldest first: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>` (UTC now: `date -u "+%Y-%m-%dT%H:%M:%SZ"`).

- 2026-09-29T06:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status; record subtasks with `spec-kitty agent tasks mark-status <Txxx> --status done`.
