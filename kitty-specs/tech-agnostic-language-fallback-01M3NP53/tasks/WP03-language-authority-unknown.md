---
work_package_id: WP03
title: Language authority - unknown detection, doctrine vocabulary, hyphen rule, precedence parameter
dependencies:
- WP02
requirement_refs:
- C-001
- FR-008
- FR-012
- FR-013
- FR-014
- FR-015
- FR-017
- NFR-001
- NFR-002
planning_base_branch: issue-5283-tech-agnostic-language-fallback
merge_target_branch: issue-5283-tech-agnostic-language-fallback
branch_strategy: Planning artifacts for this mission were generated on issue-5283-tech-agnostic-language-fallback. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5283-tech-agnostic-language-fallback unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-tech-agnostic-language-fallback-01M3NP53
base_commit: a2060146a75be1a4f614a859d5a86433924f4a3d
created_at: '2026-09-29T05:37:53.618803+00:00'
subtasks:
- T014
- T015
- T016
- T017
- T018
- T019
- T020
phase: Phase 3 - Language authority (lane B)
history:
- at: '2026-09-29T06:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/charter/activation/language_scope.py
create_intent:
- src/charter/activation/language_vocabulary.py
- tests/charter/test_language_vocabulary.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/charter/activation/language_scope.py
- src/charter/activation/language_vocabulary.py
- src/charter/activation/synthesizer/interview_mapping.py
- tests/charter/test_language_scope.py
- tests/charter/test_active_languages_idempotency.py
- tests/charter/test_language_vocabulary.py
- tests/charter/synthesizer/test_interview_mapping.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP03 – Language authority - unknown detection, doctrine vocabulary, hyphen rule, precedence parameter

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

- **Vocabulary provider construction (BLOCKER B1):** do NOT construct `charter.offering.service.DoctrineService` or repositories directly — `tests/architectural/test_charter_sole_door_doctrine_service.py` (Policy A/B) and `test_charter_sole_door_agent_profile_repository.py` forbid it outside `resolver.py`/`doctrine_service_builder.py`. Implement the provider as a lightweight **YAML scan** of `applies_to_languages` fields (mirror `charter/offering/catalog.py::_load_yaml_id_catalog_with_presence` style): built-in pack dirs for the kinds that carry the field (tactics, styleguides, toolguides, procedures, agent profiles), the project overlay `<repo>/.kittify/doctrine/<kind-dir>/` (`_doctrine_paths.py:36`, `PROJECT_KIND_DIRS`), and configured org pack roots (`charter.offering.drg.org_pack_config.resolve_existing_org_roots`). Target cold cost well under 300 ms (the service route measured ~2.06 s). Add both sole-door gates to your named gate run.
- Cache: expose clearing via the public function's `functools.lru_cache` (`scoped_language_vocabulary.cache_clear()`); do NOT export a separate `clear_...` name (dead-symbol gate fails for test-only callers).
- **Operator decision (2026-09-29): language-independent tactics are being de-scoped in WP07**, so after this mission no shipped doctrine is scoped to `go`/`rust`/`ruby`/`csharp`. Tests must NOT rely on shipped pack scopes for FR-017: use a synthetic project-overlay artifact scoped to `elixir` and assert end-to-end `infer_repo_languages(tmp_repo, interview=<"Elixir 1.17">) == ["elixir"]` (defeats a hardcoded vocabulary, C-001). Replace every "Go 1.22 → [go]" expectation with this; do not assert anything about `go`. Shipped-pack assertion limited to `"python" in scoped_language_vocabulary(None)` and exclusion of `any`/`all`/`unknown`. "HTML with Zig" → `["html"]` (html backed by frontend-freddy) is acceptable and may be pinned.
- Tokenization: whole words only; "C#"-style tokens are out of scope (resolve to `unknown`) — pin that behaviour with a test and a one-line note.
- Red-first tests in `test_language_scope.py` must reference `"unknown"` as a literal (no new top-level imports), so the `:49` guard test still collects on the base.
- Add the row: default languages answer + another free-prose answer mentioning "Zig" → `None`.
- Synthesizer (B5): string inputs (`"unknown"`, `"N/A"`, `"[]"`) already produce no target on the base — keep them as GREEN controls; the RED cases are list-shaped (`["unknown"]`, `["N/A"]`).
- Default answer text: the loader is private `charter.activation.interview._load_packaged_defaults` (`interview.py:765`); `default_interview` (`:308`) is too heavy. You may add a small public accessor in `interview.py` (add it to your owned files with a one-line rationale — ownership-map leeway) or import the private loader with a comment; do not duplicate the literal.
- The builder imports `infer_repo_languages` at `doctrine_service_builder.py:124` via the `charter.activation.context` seam; `:134` is the call — keep the signature backward compatible.
- One commit per subtask (campsite, red, provider, hyphen, detection, precedence, synthesizer).
- **Red→green proof (reviewer, mandatory):** re-run the new tests after `git checkout <base> -- src/charter/activation/language_scope.py src/charter/activation/synthesizer/interview_mapping.py` (then `git checkout HEAD -- src/charter/activation/language_scope.py src/charter/activation/synthesizer/interview_mapping.py`): they must be RED for the intended reason (an assertion, never an ImportError/collection error) and GREEN again at the tip. Base = the WP02 tip.
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

Core of #5284, #4613 (minimal) and the authority half of #4614. After this WP, the single language authority `infer_repo_languages` (and `extract_declared_languages`) behaves as follows:

| Interview languages/frameworks answer | Resolved languages |
|---|---|
| "Zig 0.16.0 is the primary implementation language" | `["unknown"]` |
| shipped default text (`src/charter/defaults.yaml:13`) | `None` (unchanged) |
| `""`, `[]`, `None`, `N/A`, `na`, `none`, `TBD`, `any`, `language-agnostic`, `unknown`, `-`, `[NEEDS CLARIFICATION…]` | `None` |
| "Python and Zig" | `["python"]` (recognised wins; no `unknown`) |
| "Elixir 1.17" with a synthetic project-overlay artifact scoped to `elixir` | `["elixir"]` (doctrine-derived vocabulary, FR-017) |
| "Rust with cargo" / "TypeScript" / … | as today |
| "Django" (framework only) | `["unknown"]` (accepted false label; advisory covers it) |

and:
- free-prose answers other than `languages_frameworks` can only ADD recognised languages, never signal `unknown`;
- a language token preceded by a word and a hyphen (`librespot-java`) no longer matches; trailing compounds (`Java-based`, `Python-based`) still match;
- `infer_repo_languages(repo_root, *, interview=None, prefer_interview=False)`: when `prefer_interview=True` and an interview is supplied, tier 1 (compiled `catalog.languages`) is skipped and the result comes from the interview alone (may be `None`); default behaviour (compiled-first) is unchanged — the #2395/#3292 guard tests stay green UNCHANGED;
- `UNKNOWN_LANGUAGE` / `is_unknown_language` are re-exported from `language_scope` (defined in `scoping`, WP02);
- the synthesizer's independent extraction (`activation/synthesizer/interview_mapping.py:271/:280/:413-414`) filters the same placeholders so `unknown`/placeholders never become an "Unknown Style Guide" target (`targets.py:130`).

## Context & Constraints

- Charter (binding): `.kittify/charter/charter.md` — ATDD/red-first (C-011): the failing test is committed as its own commit BEFORE the fix; reviewer verifies red on the planning base and green at the WP tip.
- Mission docs: `kitty-specs/tech-agnostic-language-fallback-01M3NP53/{spec.md,plan.md,research.md,data-model.md,contracts/cli-outputs.md,quickstart.md}`; tracer files under `traces/` — append a dated 1–3 sentence entry for any tooling friction, approach change, or design decision you make.
- Operator policy (#2330 decision): Spec Kitty doctrine is tech-agnostic; default implementation profile `implementer-ivan`; unknown languages → advise extending the local charter; NEVER fix by adding languages one by one; NEVER suggest Python files/layouts/tools to a non-Python project.
- Sibling-owned, do NOT edit: `src/specify_cli/consolidation/**`, `tests/integration/**`, golden/snapshot fixtures (`tests/specify_cli/skills/__snapshots__/**`, `tests/cli/__snapshots__/**`, `tests/consolidation/merge_driver_goldens/**`, `tests/contract/snapshots/**`), doctor/decision surfaces, `review/arbiter.py`, move-task override, built-in software-dev guidelines (#5202).
- Code quality: `ruff check`, `ruff format --check`, `mypy` (strict) clean on touched files; cyclomatic complexity ≤15; no new `# noqa`/`# type: ignore`; every new branch/helper gets a focused test in the same commit; modules under `src/charter/**` keep `__all__` and every exported name needs a caller in `src/` (dead-symbol gate).
- Terminology canon: Mission, never "feature", in any new prose/identifier.
- In a lane worktree always run tools via `uv run --frozen ...` or the worktree's own interpreter so the LANE `src/` is imported (bare `python`/`pytest` may import the primary checkout).

### Grounded seams

- `language_scope.py:23-32` `_LANGUAGE_PATTERNS`; `extract_declared_languages` `:35-42`; `_read_compiled_languages` `:45`; `infer_repo_languages` tier logic `:153-168` (tier 2 joins `resolved_interview.answers.values()` at `:163-164`). Line 21 has an extra blank line (`ruff format` fails).
- Interview: `answers["languages_frameworks"]` (`interview.py:181`); `CharterInterview.from_dict` stringifies every answer with `str(v)` (`:282`) → a YAML list arrives as `"['Zig', 'C']"`, empty list `"[]"`, null `"None"`. `available_tools` is a separate field (`:249`) and is NOT in the scanned answers.
- Shipped default answer text: `src/charter/defaults.yaml:13` "Use only the languages, frameworks, and tools explicitly declared by this project." — load it via the same loader the interview uses (do not duplicate the literal); compare after strip/casefold/whitespace-collapse.
- Guard tests that must stay unchanged: `tests/charter/test_language_scope.py:49` (`test_infer_repo_languages_prefers_compiled_charter_over_stale_interview`), `tests/charter/test_active_languages_idempotency.py:185` (default interview → None) and `:196` (compiled tier wins over interview override).
- Patch seam: `charter.activation.context:89` re-exports `infer_repo_languages` and `doctrine_service_builder.py:134` imports it through that seam — keep the signature backward compatible (new params keyword-only with defaults).
- Vocabulary provider construction: `charter.offering.service.DoctrineService(project_root=..., org_roots=..., active_languages=None)` (`service.py:25-34`; `None` = unfiltered). Mirror the canonical discovery in `doctrine_service_builder.py:92-180` (`resolve_project_root`, `resolve_existing_org_roots`) — do not reimplement discovery rules.
- Import-cycle risk: `doctrine_service_builder` → `language_scope` → provider → service. Use function-local imports inside the provider; the provider never calls `infer_repo_languages`.

## Branch Strategy

- **Strategy**: lanes (no coordination branch)
- **Planning base branch**: issue-5283-tech-agnostic-language-fallback
- **Merge target branch**: issue-5283-tech-agnostic-language-fallback

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; prepare yours with `spec-kitty agent action implement WP03 --agent claude`.

## Subtasks & Detailed Guidance

### Subtask T014 – Campsite (behaviour-preserving, own commit FIRST)

- `ruff format src/charter/activation/language_scope.py` (removes the stray blank line).
- Add characterization tests to `tests/charter/test_active_languages_idempotency.py` / `test_language_scope.py` for today's semantics that MUST survive: compiled `[]` → `[]`; compiled absent → falls to interview; compiled non-list → treated absent; empty interview scan → `None`; default interview → `None` (already `:185` — reference it, do not duplicate).
- Commit `refactor(charter): campsite language_scope formatting + characterization tests`. All green (behaviour-preserving).

### Subtask T015 – Red-first tests (own commit, RED)

- In `tests/charter/test_language_scope.py` (unit, via `infer_repo_languages(None, interview=CharterInterview.from_dict(...))` and `extract_declared_languages`): the whole table in Objectives, including list-shaped answers (`languages_frameworks: ["Zig", "C"]` → `["unknown"]`; `[]` → `None`), "Python and Zig" → `["python"]`, placeholders → `None`, default text → `None`, synthetic `elixir` overlay + "Elixir 1.17" → `["elixir"]`, hyphen cases (`librespot-java` → no java; `java-bridge` NOT asserted; "Java-based backend" → java; "Python-based services" → python; "Java 21 with Gradle" → java), and `prefer_interview=True` with a seeded stale compiled `[python]` + Zig interview → `["unknown"]` while the default call still returns `["python"]`.
- `tests/charter/test_language_vocabulary.py` (new): shipped packs with `repo_root=None` → contains `python`; excludes `any`/`all`/`unknown`; a tmp repo with a project-overlay artifact scoped to `elixir` (find the overlay dir via `resolve_project_root`) → contains `elixir`; overlay artifact scoped to `[unknown]`/`[any]` contributes nothing; memoized (loader invoked once; cache-clear hook resets); importing the module does not import `language_scope`.
- `tests/charter/synthesizer/test_interview_mapping.py`: `languages_frameworks: "unknown"` / `"N/A"` / `"[]"` → no style-guide target produced for it.
- All new assertions fail now. Commit `test(charter): red-first unknown-language resolution (#5284 #4613 #4614)`.

### Subtask T016 – Vocabulary provider

- New `src/charter/activation/language_vocabulary.py`: module docstring (operator decision; `unknown` = "no specialist guidance exists"), `__all__ = ["scoped_language_vocabulary", "clear_scoped_language_vocabulary_cache"]`.
- `scoped_language_vocabulary(repo_root: Path | None) -> frozenset[str]`: lazily build the UNFILTERED service (built-in + project layer + configured org packs; `repo_root=None` → built-in only); iterate every repository whose model carries `applies_to_languages` (styleguides, toolguides, tactics, procedures, agent profiles — confirm via `grep -rn applies_to_languages src/charter/offering --include=*.py`); union → `normalize_languages` → subtract sentinel (`any`/`all`) and `RESERVED_LANGUAGE_TOKENS`; cache per resolved root string.
- Measure cold/warm cost with a throwaway scratch script (not committed); record in the Activity Log. Warm must be a cache hit (~0 ms); flag cold > 300 ms to the reviewer (NFR-002).

### Subtask T017 – Hyphen-prefix guard (#4613 minimal)

- Prefix every regex in `_LANGUAGE_PATTERNS` with `(?<!\w-)` (compile once at module level if convenient). Do NOT touch trailing compounds. Do NOT add languages (C-001).

### Subtask T018 – Unknown detection in tier 2

- Implement a small, individually tested helper (e.g. `_declared_language_answer(interview) -> str | None`) that extracts the `languages_frameworks` answer, strips list-repr brackets/quotes, and returns None for empty/placeholder/default text.
- Resolution when tier 2 runs: `declared = extract_declared_languages(all answers)`; if non-empty → return it (unchanged). Else, if the languages/frameworks answer is a real declaration: tokenize it into whole words (casefolded, apply the same `(?<!\w-)` rule) and intersect with `scoped_language_vocabulary(repo_root)` → if non-empty return that sorted/normalized list; else return `[UNKNOWN_LANGUAGE]`. Otherwise → `None`.
- Keep `infer_repo_languages` ≤15 complexity (extract helpers). The placeholder set is a module constant (reused by T020).

### Subtask T019 – Precedence parameter, re-exports, docstring

- Add keyword-only `prefer_interview: bool = False`; when True and an interview is available (in-memory or on disk), skip tier 1. Re-export `UNKNOWN_LANGUAGE`, `is_unknown_language` in `__all__`. Rewrite the (now ~45-line) docstring concisely: the four states (absent/None, `[]`, recognised list, `[unknown]`), tier order, the regenerate-only bypass, and why runtime stays compiled-first (#2395/#3292). Callers of the re-exports arrive in WP04/WP05; `_catalog_miss` already imports from `scoping` (WP02), so the dead-symbol gate is satisfied via `scoping`'s own callers — verify with the gate.

### Subtask T020 – Synthesizer placeholder filter

- In `synthesizer/interview_mapping.py` where `languages_frameworks` is mapped (`:271`, `:280`, `:413-414`), drop placeholder/`unknown` values using the shared placeholder constant from `language_scope` (import it; do not duplicate). Keep list-shaped answers working as today for real values.

## Test Strategy

- `uv run --frozen pytest tests/charter/test_language_scope.py tests/charter/test_active_languages_idempotency.py tests/charter/test_language_vocabulary.py tests/charter/synthesizer/test_interview_mapping.py tests/charter/test_doctrine_service_builder_unification.py -q` (the last one is slow, ~3 min — run once at the end).
- Fast tier neighbours: `uv run --frozen pytest tests/charter/synthesizer/ -q` (hyphen rule ripple), `tests/charter/test_catalog.py`.
- Named arch gates: `tests/architectural/test_no_dead_symbols.py`, `tests/architectural/test_layer_rules.py`.
- ruff check/format + `mypy src/charter/activation/language_scope.py src/charter/activation/language_vocabulary.py src/charter/activation/synthesizer/interview_mapping.py`.

## Risks & Mitigations

- #3292 trap: default interview must stay `None` — pinned by `:185` and the new table.
- Vocabulary loads the doctrine service → latency; cache + timing record.
- Word tokenization of "Go" could match prose like "we go with" — only the languages/frameworks answer is tokenized, never free prose.

## Definition of Done

- [ ] Campsite commit, then red commit, then fix commits (ordering visible in `git log`).
- [ ] Every Objectives table row pinned by a test and green; guard tests `:49/:185/:196` untouched and green.
- [ ] No literal language list added (C-001); vocabulary read from packs.
- [ ] ruff/format/mypy clean; complexity ≤15; arch gates green; timing recorded.

## Review Guidance

Verify red→green on the planning base; verify the guard tests were not edited (`git diff` on those test names); verify placeholder/default handling incl. list reprs; verify no language was added to `_LANGUAGE_PATTERNS`; verify no import cycle and the cache. Targeted commands only (HARD RULE).

## Activity Log

> Append entries at the END, oldest first: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>` (UTC now: `date -u "+%Y-%m-%dT%H:%M:%SZ"`).

- 2026-09-29T06:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status; record subtasks with `spec-kitty agent tasks mark-status <Txxx> --status done`.
