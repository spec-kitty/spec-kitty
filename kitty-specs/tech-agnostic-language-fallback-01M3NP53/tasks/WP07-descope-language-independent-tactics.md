---
work_package_id: WP07
title: De-scope language-independent built-in tactics; close the bias-gate scope loophole
dependencies: []
requirement_refs:
- C-001
- C-005
- FR-018
planning_base_branch: issue-5283-tech-agnostic-language-fallback
merge_target_branch: issue-5283-tech-agnostic-language-fallback
branch_strategy: Planning artifacts for this mission were generated on issue-5283-tech-agnostic-language-fallback. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5283-tech-agnostic-language-fallback unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-tech-agnostic-language-fallback-01M3NP53
base_commit: a2060146a75be1a4f614a859d5a86433924f4a3d
created_at: '2026-09-29T05:12:38.586645+00:00'
subtasks:
- T035
- T036
- T037
- T038
- T039
- T040
phase: Phase 2 - Doctrine neutrality (independent lane)
history:
- at: '2026-09-29T06:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: doctrine-daphne
authoritative_surface: packs/built-in/tactics/
create_intent:
- tests/doctrine/test_language_independent_tactics_unscoped.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- packs/built-in/tactics/secure-regex-catastrophic-backtracking.tactic.yaml
- packs/built-in/tactics/code-patterns/chain-of-responsibility-rule-pipeline.tactic.yaml
- packs/built-in/tactics/architecture/dependency-hygiene.tactic.yaml
- packs/built-in/pack-manifest.yaml
- tests/doctrine/test_generic_artifact_language_bias.py
- src/charter/activation/neutrality/language_scoped_allowlist.yaml
- tests/architectural/_builtin_pack_provenance_baseline.yaml
- tests/doctrine/test_language_independent_tactics_unscoped.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP07 – De-scope language-independent built-in tactics; close the bias-gate scope loophole

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill (canonical: `spk-doctrine-profile-load`) to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `doctrine-daphne`
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

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks and use language identifiers in code blocks.

---

## Objectives & Success Criteria

Operator directive (2026-09-29): "our doctrine and especially tactics are supposed to be language independent." Decision Moment `descope_language_independent_tactics`: de-scope ALL THREE (FR-018).

After this WP:
- `secure-regex-catastrophic-backtracking`, `chain-of-responsibility-rule-pipeline` and `dependency-hygiene` declare NO `applies_to_languages` (unscoped = applies to every project, incl. unknown-language ones).
- Their content is language-neutral: language-bound phrasing generalized ("the project's test runner" not `pytest`); language snippets kept only as clearly labelled examples ("Python example", "Java/Maven example"); secure-regex's engine list made consistent (backtracking engines: Python `re`, JS, Java, .NET, Ruby, PHP/PCRE, Perl…; linear-time engines: RE2, Go `regexp`, Rust `regex`); NO Spec Kitty repo-internal paths (`src/specify_cli/...`, `tests/regressions/...`) or Sonar `python:` rule ids in shipped doctrine (review-gates.md "Shippable doctrine" rule).
- `tests/doctrine/test_generic_artifact_language_bias.py` no longer exempts an artifact merely because its text contains `applies_to_languages:` (the loophole that let these tactics dodge the bias check); an exemption requires a genuinely non-empty, non-sentinel declared scope (language-specific artifact) or an explicit neutrality-allowlist entry.
- The stale secure-regex entry in `src/charter/activation/neutrality/language_scoped_allowlist.yaml` is removed; the provenance baseline reflects the removed repo-path citations; the pack manifest is regenerated.
- Accept a rebase against open PR #5324 (it edits dependency-hygiene and keeps its scope) — note the overlap in the Activity Log for the closeout.

## Context & Constraints

- Charter (binding): `.kittify/charter/charter.md` — ATDD/red-first (C-011): the failing test is committed as its own commit BEFORE the fix; reviewer verifies red on the planning base and green at the WP tip.
- Mission docs: `kitty-specs/tech-agnostic-language-fallback-01M3NP53/{spec.md,plan.md,research.md,data-model.md,contracts/cli-outputs.md,quickstart.md}`; tracer files under `traces/` — append a dated 1–3 sentence entry for any tooling friction, approach change, or design decision you make.
- Operator policy (#2330 decision): Spec Kitty doctrine is tech-agnostic; default implementation profile `implementer-ivan`; unknown languages → advise extending the local charter; NEVER fix by adding languages one by one; NEVER suggest Python files/layouts/tools to a non-Python project.
- Sibling-owned, do NOT edit: `src/specify_cli/consolidation/**`, `tests/integration/**`, golden/snapshot fixtures (`tests/specify_cli/skills/__snapshots__/**`, `tests/cli/__snapshots__/**`, `tests/consolidation/merge_driver_goldens/**`, `tests/contract/snapshots/**`), doctor/decision surfaces, `review/arbiter.py`, move-task override, built-in software-dev guidelines (#5202).
- Code quality: `ruff check`, `ruff format --check`, `mypy` (strict) clean on touched files; cyclomatic complexity ≤15; no new `# noqa`/`# type: ignore`; every new branch/helper gets a focused test in the same commit; modules under `src/charter/**` keep `__all__` and every exported name needs a caller in `src/` (dead-symbol gate).
- Terminology canon: Mission, never "feature", in any new prose/identifier.
- In a lane worktree always run tools via `uv run --frozen ...` or the worktree's own interpreter so the LANE `src/` is imported (bare `python`/`pytest` may import the primary checkout).

### Grounded facts (doctrine audit, 2026-09-29)

- secure-regex: scoped to python, javascript, typescript, java, csharp, ruby, go, rust — contradicting its own header (RE2 / Go `regexp` / Rust `regex` are linear-time, not vulnerable) and omitting PHP/Perl/C++; origin 3.2.0rc9 Sonar/ReDoS remediation; mentions `pytest` (~L113) and in-house paths (`src/specify_cli/release/changelog.py`, `tests/regressions/test_changelog_regex_redos.py`, Sonar `python:S6353`).
- chain-of-responsibility: scoped to python, java, typescript, javascript; examples lean on Python `Protocol`/`dataclass` and `tests/migration/*` spec-kitty paths.
- dependency-hygiene: scoped to java, python, javascript, typescript; step "Import BOMs (Java/Maven)" is Java-only (label it an example); mentions `maven` (~L23, L62) which the bias test denylists.
- Bias test loophole: `tests/doctrine/test_generic_artifact_language_bias.py` `_is_allowlisted` skips any file containing the text `applies_to_languages:`.
- Neutrality lint: `tests/charter/test_neutrality_lint.py` fails on stale allowlist entries; the allowlist entry for secure-regex is at `language_scoped_allowlist.yaml:77`.
- Provenance baseline: `tests/architectural/_builtin_pack_provenance_baseline.yaml:236` (secure-regex `repo_paths: 1`).
- Graph fragments do not carry scopes; edges from `action.graph.yaml`/`tactic.graph.yaml` point at these tactics (unchanged). `spec-kitty doctrine regenerate-graph` (supports `--check`) refreshes `packs/built-in/pack-manifest.yaml` content hashes. If regeneration rewrites a `*.graph.yaml`, include only hunks caused by this WP (ownership-map leeway, one-line rationale).
- Pack tiers: these stay in `packs/built-in/` (they govern consumers). Any in-house-only material removed from them may, if worth keeping, go to `packs/internal/` — not required here.

## Branch Strategy

- **Strategy**: lanes (no coordination branch)
- **Planning base branch**: issue-5283-tech-agnostic-language-fallback
- **Merge target branch**: issue-5283-tech-agnostic-language-fallback

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; prepare yours with `spec-kitty agent action implement WP07 --agent claude`.

## Subtasks & Detailed Guidance

### Subtask T035 – Red-first tests (own commit, RED)

- New `tests/doctrine/test_language_independent_tactics_unscoped.py`: for each of the three tactic ids, load via the canonical tactic repository/doctrine service path used by existing doctrine tests (e.g. `tests/doctrine/tactics/test_repository.py` pattern) and assert `applies_to_languages` is empty; assert each resolves for `active_languages=["unknown"]` and `["zig"]` (via `applies_to_languages_match` or the repository's filtered listing — at this WP's base `unknown` is not yet reserved, use `["zig"]` as the RED case and keep `["python"]` as a GREEN control); assert no shipped tactic file contains `src/specify_cli/`, `tests/regressions/` or `python:S` rule ids.
- In `test_generic_artifact_language_bias.py`: a RED test that a synthetic artifact text containing only `applies_to_languages: []` (or a sentinel) plus a denylisted word is NOT exempted.
- Commit `test(doctrine): red-first language-independent tactics are unscoped (FR-018)`.

### Subtask T036 – secure-regex rewrite

- Remove `applies_to_languages`; generalize wording; label Python snippets "Python example"; fix the engine lists; replace in-house paths/Sonar ids with generic phrasing (e.g. "a linear-runtime regression test in your test suite"); keep the tactic's structure/ids so graph edges stay valid.

### Subtask T037 – chain-of-responsibility rewrite

- Remove the scope; label `Protocol`/`dataclass` notes "Python illustration"; generalize `tests/migration/*` examples.

### Subtask T038 – dependency-hygiene rewrite

- Remove the scope; title the BOM step "(Java/Maven example)"; label Maven/uv snippets; reword the bare `maven` mentions the bias test would flag if they are not clearly example-labelled.

### Subtask T039 – Gate + allowlist + baseline

- Close the loophole in `_is_allowlisted` (require a non-empty, non-sentinel parsed scope, or an explicit allowlist entry); drop the secure-regex entry from `language_scoped_allowlist.yaml`; update `_builtin_pack_provenance_baseline.yaml` for the removed repo-path citations (shrink-only — never raise a baseline). Run the bias test and neutrality lint: if any OTHER existing artifact now fails because it relied on the loophole, list it in the Activity Log and fix it only if it is a legitimately language-specific artifact missing a proper scope; otherwise stop and report.

### Subtask T040 – Regenerate graph/manifest

- `uv run --frozen spec-kitty doctrine regenerate-graph` then `... regenerate-graph --check` (must pass); commit the refreshed `pack-manifest.yaml` (+ any graph hunks caused by this WP).

## Test Strategy

- `uv run --frozen pytest tests/doctrine/test_language_independent_tactics_unscoped.py tests/doctrine/test_generic_artifact_language_bias.py tests/charter/test_neutrality_lint.py tests/doctrine/drg/test_reachability.py tests/doctrine/tactics/test_repository.py tests/doctrine/test_supply_chain_security_layer.py -q` (use the paths that exist; `find tests -name test_supply_chain_security_layer.py`).
- Named arch/packaging gates: `tests/cross_cutting/packaging/test_packaging_safety.py`, the provenance-baseline gate that reads `_builtin_pack_provenance_baseline.yaml` (find it: `grep -rl _builtin_pack_provenance_baseline tests/architectural`), and `tests/architectural/test_no_legacy_terminology.py`.
- `spec-kitty doctrine regenerate-graph --check` passes.

## Risks & Mitigations

- Closing the loophole may surface other artifacts that relied on it → classify, fix only legitimately language-specific ones, otherwise report (do not re-open the loophole).
- Rebase conflict with PR #5324 on dependency-hygiene / graph files → expected; resolve at closeout.

## Definition of Done

- [ ] Red commit first; the three tactics unscoped, neutral, example-labelled, no in-house paths.
- [ ] Bias-test loophole closed; stale allowlist entry removed; provenance baseline shrunk (never raised).
- [ ] `regenerate-graph --check` green; named tests and gates green.

## Review Guidance

Reviewer (`reviewer-renata`; doctrine lens `doctrine-daphne` welcome as second opinion): read each rewritten tactic for residual language bias and in-house references (review-gates.md "Shippable doctrine" quick-check greps on the three files); verify the loophole is closed, not moved; verify red→green via `git checkout <planning base> -- <the three tactic files> tests/doctrine/test_generic_artifact_language_bias.py`. Targeted commands only (HARD RULE).

## Activity Log

> Append entries at the END, oldest first: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>` (UTC now: `date -u "+%Y-%m-%dT%H:%M:%SZ"`).

- 2026-09-29T06:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status; record subtasks with `spec-kitty agent tasks mark-status <Txxx> --status done`.
