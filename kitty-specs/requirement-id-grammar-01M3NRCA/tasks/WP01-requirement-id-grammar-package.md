---
work_package_id: WP01
title: Requirement-ID grammar package and single-source gate
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-008
- FR-009
- C-001
- C-003
- C-004
- C-005
- C-009
- NFR-004
- NFR-005
planning_base_branch: issue-2991-requirement-id-grammar
merge_target_branch: issue-2991-requirement-id-grammar
branch_strategy: Planning artifacts for this mission were generated on issue-2991-requirement-id-grammar. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2991-requirement-id-grammar unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Grammar foundation
history:
- at: '2026-09-29T06:14:47Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/requirement_mapping/
create_intent:
- src/specify_cli/requirement_mapping/__init__.py
- src/specify_cli/requirement_mapping/grammar.py
- tests/specify_cli/test_requirement_id_grammar.py
- tests/architectural/test_requirement_id_grammar_single_source.py
- tests/architectural/requirement_id_pattern_allowlist.yaml
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/requirement_mapping.py
- src/specify_cli/requirement_mapping/__init__.py
- src/specify_cli/requirement_mapping/grammar.py
- src/specify_cli/cli/commands/agent/mission_parsing.py
- src/specify_cli/status/wp_metadata.py
- src/specify_cli/consolidation/retention.py
- tests/specify_cli/test_requirement_mapping.py
- tests/specify_cli/test_requirement_mapping_coord_surface.py
- tests/specify_cli/test_bare_prose_false_negative_sample.py
- tests/specify_cli/test_requirement_id_grammar.py
- tests/specify_cli/cli/commands/agent/test_mission_parsing.py
- tests/specify_cli/status/test_wp_metadata.py
- tests/consolidation/test_retention.py
- tests/architectural/test_requirement_id_grammar_single_source.py
- tests/architectural/requirement_id_pattern_allowlist.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Requirement-ID grammar package and single-source gate

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Also run `.venv/bin/spec-kitty profiles show python-pedro` and `.venv/bin/spec-kitty charter context --action implement`.

---

## ⛔ HARD RULE: no heavy suites

Never run the whole `tests/architectural/` directory, any e2e or full-integration suite, any performance/stress/timing suite, `make test-full`, or a whole-repo `pytest`. Run ONLY the test files, the owning module's fast tier, and the named architectural gate files listed under `## Validation surface`. Always invoke pytest as:

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q <files>
```

This is charter C-007 / `NO_FULL_HEAVY_SUITES_IN_MISSION`. It also covers `tests/architectural/test_interpreter_shard_coverage.py`, which collects the whole fast tier: do not run it (see the T003 out-of-map note).

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `.venv/bin/spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## 🧭 Orchestrator overrides (take precedence over anything below)

- **Do NOT edit or commit anything under `kitty-specs/requirement-id-grammar-01M3NRCA/traces/`**, and do not commit any other mission-directory bookkeeping on the primary checkout. A dirty mission-dir file on the primary checkout blocks every WP's `move-task`. Put your tracer notes (tooling friction, approach changes, design decisions, each 1–3 dated sentences) in a `## Tracer notes` section of your final hand-off report. The orchestrator appends and commits them.
- **CLI:** always `.venv/bin/spec-kitty`, run from the repo-root checkout. In a lane worktree, run tests with `PYTHONPATH=$(pwd)/src <repo-root>/.venv/bin/python -m pytest …`, and confirm once that `specify_cli.__file__` resolves inside the lane. Never a bare `uv run`.
- **Commit** the `base_commit` that `implement` stamps into this WP's frontmatter before any state move.
- **HARD RULE: no heavy suites** (restated): run only the files and named gates in this prompt's Validation surface.

## Objectives & Success Criteria

This WP creates the single requirement-ID grammar authority (C-001) that WP02–WP05 consume, and the architectural gate that keeps it single. When it is done:

1. `src/specify_cli/requirement_mapping.py` is the package `src/specify_cli/requirement_mapping/`. The history is preserved through `git mv`, and every existing import (public and private) still resolves.
2. `requirement_mapping/grammar.py` is the only place in product code that defines requirement-ID patterns. It implements `RequirementId`, `parse`, `canonical`, `find_all(spec_scan=)`, `tokenize_refs`, `blank_html_comments`, `DECLARED_SHAPE_PATTERNS`, `MALFORMED_DECLARED_LEAD`, `classify`, the reason constants `MALFORMED` / `UNKNOWN_SPEC_ID` / `FOREIGN_QUALIFIED`, `FAILING_REASONS` and `RULE_TEXT`, per `data-model.md` and `contracts/grammar.md`. Every pattern is compiled through `kernel._safe_re` (C-005).
3. The package, the tasks.md fallback parser (`mission_parsing.py`), the `wp_metadata` scalar tokenizer and the merge-cleanup retention reader (`consolidation/retention.py`) all read IDs through the grammar (FR-001; HiC ruling, Decision Moment `01M3P2HXKASQY2ZKSEY3MAWA9H`). SC and letter-suffixed IDs are recognised as declared (FR-003). Matching goes by canonical form (FR-002), and `slug#ID` is always foreign (FR-009).
4. Nothing changes for existing plain FR/NFR/C IDs, except the re-pins listed in T004. The bare-prose candidate set is exactly as today (C-009), and `test_bare_prose_corpus_ratchet.py` still reports exactly 1 flagged spec.
5. `tests/architectural/test_requirement_id_grammar_single_source.py` is green and non-vacuous. It has a concrete floor (it sees the literal in `grammar.py`), a self-mutation test, a stale-allowlist failure and a two-sided entry-count check. Its allowlist holds exactly three entries: two frozen and one transitional, with `baseline: 3`.
6. NFR-004 holds: ruff lint and format are clean, `mypy --strict` is clean on the touched src files, every function is at complexity ≤ 15, and new code is covered by tests (target ≥ 90% diff coverage).

## Context & Constraints

- **Read in full before coding:**
  - `kitty-specs/requirement-id-grammar-01M3NRCA/spec.md` (FR-001/002/003/008/009, C-001/003/004/005/009, NFR-005 defect (c), Edge Cases);
  - `plan.md` ("Grammar (IC-01)", "Behavioural changes by surface", IC-00/IC-01 risks);
  - `data-model.md` and `contracts/grammar.md`, which are the API and grammar contract;
  - `contracts/json-payload-deltas.md`, for context only (WP02/WP03 own the wire changes);
  - `research.md` R2, R4, R5.
- **Charter:** `.kittify/charter/charter.md`. The Quality & Tech-Debt Standing Orders apply: tidy-first (#2), non-vacuous gates (#5), canonical sources (#6).
- **Downstream consumers of this WP:** WP02 (finalize), WP03 (map-requirements), WP04 (runtime, which receives the grammar by injection), and WP05 (setup-plan lint, which consumes `MALFORMED_DECLARED_LEAD`, `DECLARED_SHAPE_PATTERNS`, `blank_html_comments` and `RULE_TEXT`). WP03 and WP05 import the reason constants instead of restating the strings. Keep the grammar API exactly as `data-model.md` names it, because four WPs code against it in parallel.
- **Out of scope here:**
  - Do not touch `mission_finalize.py`, `tasks_map_requirements.py`, `tasks_mapping_core.py` or the runtime modules.
  - Do NOT delete `find_discarded_sc_refs` / `_discarded_sc_warning`; WP02 retires them together with their caller (`mission_finalize.py:79`).
  - `normalize_requirement_refs_value` stays; WP02 stops using it for writes.
  - Concern IDs (`IC-##`) are a separate grammar and are never admitted (C-004). The manifest schema is unchanged (C-003).
- **Layering:** the grammar stays inside `specify_cli`. `grammar.py` imports only stdlib and `kernel._safe_re`. The package `__init__` must keep its `specify_cli.status` / `specify_cli.frontmatter` imports function-local, as they are today (`requirement_mapping.py:520,551`). T005 adds a `status/wp_metadata.py → requirement_mapping.grammar` edge, and a module-level status import in `__init__` would create an import cycle. T005 also adds a `consolidation/retention.py → requirement_mapping.grammar` edge. That edge is intra-`specify_cli`; the only import gate on `specify_cli/consolidation/**` is `TestMergeCliBoundary` in `tests/architectural/test_layer_rules.py`, which forbids `specify_cli.cli.*` imports and is unaffected, but it must be run (it is in the named gates).
- **CLI:** always use `.venv/bin/spec-kitty` (a bare `spec-kitty` resolves to a stale rc3). Start with `.venv/bin/spec-kitty agent action implement WP01 --agent claude`, and work only in the workspace path it prints. Never pick a base branch by hand.

### Out-of-map edits allowed in this WP (each with rationale)

- `tests/specify_cli/missions/test_substantive_gate_formats.py:780-790` (`test_declared_id_set_is_unchanged_by_the_new_columns`). The live spec template declares `- **SC-001**:` … `- **SC-004**:` (`spec-template.md:145-148`). Once `all` includes SC (data-model "Declared-ID set"), this exact-set pin goes red. Add `SC-001`…`SC-004` to the expected set, with a one-line comment naming FR-003. That is the only permitted change to that file. If the orchestrator rules instead that `all` must exclude SC, stop and escalate; do not choose silently.
- `tests/architectural/_interpreter_shard_roster.py` (shard 5 tuple, next to `"tests/specify_cli/test_requirement_mapping.py"`, ~`:352`) and the matching shard-5 `run:` line in `.github/workflows/ci-nightly.yml` (~`:687`). Root-level `tests/specify_cli/test_*.py` files are enumerated one by one, so the new `tests/specify_cli/test_requirement_id_grammar.py` has to be enrolled in both, in the same position, or the nightly shard-coverage gate reports a gap. Do not run that gate (see HARD RULE). Instead, verify both edits with `git diff`.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-2991-requirement-id-grammar`; completed changes merge back into `issue-2991-requirement-id-grammar`.
- **Planning base branch**: `issue-2991-requirement-id-grammar`
- **Merge target branch**: `issue-2991-requirement-id-grammar`

> These fields are populated automatically by `.venv/bin/spec-kitty agent mission finalize-tasks`. The execution worktree comes from `lanes.json` through `.venv/bin/spec-kitty agent action implement WP01 --agent claude`.

## Commit sequence (one concern per commit)

1. T001: tidy-first reader merge (behaviour-preserving; existing tests unchanged).
2. T002: `git mv` to the package (pure rename, no content change).
3. T003: `grammar.py` plus `test_requirement_id_grammar.py` (tests written first), plus shard enrolment.
4. T004a: red-first `#3519` repros, function-level and CLI-level (see T004). T004b: the rewire plus re-pins.
5. T005: parser migration plus pins (including the `consolidation/retention.py` migration and its tests).
6. T006: C-001 gate plus allowlist.
7. T007: validation evidence (Activity Log). Tracer notes go in the `## Tracer notes` section of your hand-off.

## Subtasks & Detailed Guidance

### Subtask T001 – Tidy-first: merge the two WP-frontmatter reader loops

- **Purpose**: IC-00 campsite. `_read_all_wp_refs` (`requirement_mapping.py:509-536`) and `read_all_wp_raw_requirement_refs` (`:544-568`) repeat the same loop: the `tasks_dir.exists()` guard, the `sorted(glob("WP*.md"))`, the `(WP\d{2})` match, and try/except → `[]`. T004 then touches only one reader.
- **Steps**:
  1. Extract one private loop, for example `_read_wp_frontmatter_values(tasks_dir, load_value) -> dict[str, list[str]]`. It takes a per-file loader that returns the extracted list, and yields `[]` when the loader raises.
  2. Express both public readers through it. The two sources differ: the typed `read_wp_frontmatter(...).requirement_refs` (which runs `wp_metadata`'s legacy scalar coercion) versus the raw `FrontmatterManager().read(...)` dict with `.get("requirement_refs")`. Each public reader must keep its own source. Do not unify them onto one source; that is not behaviour-preserving.
  3. Keep the `# MIGRATION-ONLY: raw dict access is intentional here` markers on the raw-dict path.
  4. Keep both imports function-local.
  5. **Binding: merge the readers.** Both public readers MUST go through the one private loop; no second copy of the loop may remain. The raw reader `read_all_wp_raw_requirement_refs` is **the WP01 unified raw reader used by WP02's finalize**. WP02 (finalize), WP03 (map-requirements) and WP04 (runtime) all classify its output, so keep its name and its return shape (`dict[wp_id, list[str]]` of raw tokens, produced by `grammar.tokenize_refs` after T004 step 9).
- **Files**: `src/specify_cli/requirement_mapping.py` only.
- **Acceptance**: `tests/specify_cli/test_requirement_mapping.py`, `test_requirement_mapping_coord_surface.py` and `test_bare_prose_false_negative_sample.py` pass with zero test edits. This commit contains no test changes.
- **Parallel?**: No; it comes first.

### Subtask T002 – Convert the module into a package with `git mv`

- **Steps**:
  1. `mkdir src/specify_cli/requirement_mapping && git mv src/specify_cli/requirement_mapping.py src/specify_cli/requirement_mapping/__init__.py`.
  2. Remove stale bytecode: `rm -f src/specify_cli/__pycache__/requirement_mapping*.pyc`. Two exist today (cpython-311 and cpython-313). A stale `.pyc` next to a package directory masks import errors.
  3. Commit the pure rename, with no content edits, so `git log --follow` keeps the history.
- **Import surface to preserve** (verified callers): `specify_cli.requirement_mapping.X` must still resolve for every name below.
  - Public: `CoverageSummary`, `BareProseCandidate`, `BareProseResult`, `classify_stale_refs`, `compute_coverage`, `find_bare_prose_requirement_ids`, `find_undeclared_requirement_citations`, `find_discarded_sc_refs`, `normalize_requirement_refs_value`, `parse_requirement_ids_from_spec_md`, `read_all_wp_raw_requirement_refs`, `read_all_wp_requirement_refs`, `validate_ref_format`, `validate_refs`.
  - Private, imported by `tests/specify_cli/test_bare_prose_false_negative_sample.py:33-38`: `_DECLARED_ID_PATTERNS`, `_REF_FIND_PATTERN`, `_declared_ids`.
  - Monkeypatched by attribute on the package (the lookup must stay late-bound through the package):
    - `_requirement_named_sections` (`test_requirement_mapping.py:361`, consumed by `find_bare_prose_requirement_ids`);
    - `find_bare_prose_requirement_ids` (`test_mission_finalize_phases.py:516`, `test_tasks_map_requirements_seam.py:431`);
    - `parse_requirement_ids_from_spec_md` (`test_audit_tail_readers.py:732`, `tests/next/test_runtime_bridge_unit.py:1415`);
    - `find_undeclared_requirement_citations` (`tests/next/test_runtime_bridge_unit.py:1461`).
- **Acceptance**: the T001 test set is still green, and `.venv/bin/python -c "import specify_cli.requirement_mapping as m; print(m.__file__)"` prints the package `__init__.py`.

### Subtask T003 – `grammar.py`: the single grammar authority (tests first)

- **Purpose**: FR-001, FR-002, FR-003, FR-009 (finder), FR-019 (verdict table), C-001, C-005.
- **Write `tests/specify_cli/test_requirement_id_grammar.py` FIRST** (`pytestmark = [pytest.mark.unit, pytest.mark.fast]`). It is red because the import fails; then implement. No `regression` marker here, because this subtask fixes no NFR-005 defect.
- **API** (names exactly as `data-model.md`; give `grammar.py` an `__all__`):
  - `RequirementId`: a frozen dataclass with `kind: Literal["FR","NFR","C","SC"]`, `digits: str`, `suffix: str | None` and `mission: str | None`. It has `canonical` (the string), `is_foreign`, `is_functional` and `is_success_criterion`, and equality and hashing on `(kind, digits, suffix, mission)`. A qualified ID renders as `f"{mission}#{canonical}"`.
  - A single core string, `(?:FR|NFR|SC|C)-\d+(?-i:[a-z])?`, from which EVERY pattern is generated: the strict full-match, the finder with its optional qualifier `(?:([a-z0-9][a-z0-9-]*(?:-[0-9A-Z]{8})?)#)?` (mid8 tail exactly 8 characters), the four declared shapes and the tolerant ref-matching variant. Do not write any second ID alternation literal anywhere. The legacy-compat alias `_REF_FIND_PATTERN` (T004 step 1) is composed in `grammar.py` from a kinds constant, e.g. `_LEGACY_KINDS = ("FR", "NFR", "C")` joined with `"|"`, never a second hand-written alternation (analysis F14).
  - **Token boundary** (`contracts/grammar.md`, `data-model.md`): a token must not be preceded or followed by an ASCII word character (`[A-Za-z0-9_]`, i.e. ASCII `\b` semantics); the single lowercase suffix letter is part of the token and must itself not be followed by a word character. A trailing `-word` (`-mandated`, `-mission`) makes the token malformed in declared positions and not an ID in prose. Implement it RE2-safe (analysis F9/F15/F16 rulings): `\b` at BOTH ends of the (optionally qualified) core, with no consumed group, so `group(0)` is exactly the token. Then apply an in-code check on the text right after each match that rejects a following `-<letter or digit>` compound (`FR-008-mandated`, `C-1-2`). No lookbehind, no lookahead. `\b` must have ASCII semantics: under RE2 it does; if `kernel._safe_re` falls back to stdlib `re`, compile with `re.ASCII` (this is also the charter's Identifier Safety rule). Unit cases pin it: `x_FR-001` and `FR-001_` yield nothing; `FR-001é` behaves identically under RE2 and the fallback; `C-1-2` is not an ID in prose. Assert which engine is active in the test.
  - `parse(token) -> RequirementId | None`: strict full match, qualifier optional, suffix case-tolerant (either case → lowercase).
  - `canonical(token) -> str | None`.
  - `find_all(text, *, spec_scan: bool) -> list[RequirementId]`: the qualifier is consumed. With `spec_scan=True` only a lowercase suffix is recognised. Case tolerance is for matching ref items (`spec_scan=False`), never for scanning spec text.
  - `tokenize_refs(value) -> list[str]`: a list keeps its str items (a non-str item becomes `<NON_STRING:…>`, exactly as `_extract_raw_tokens` does today); a scalar string is split on `[,\s]+`; empty tokens are dropped.
  - `DECLARED_SHAPE_PATTERNS`: 4 compiled patterns (table first cell, heading, bullet/numbered lead, bold lead). They reproduce the `**`/`~~` wrapper tolerance and capture group 1 of `requirement_mapping.py:55-78`, and add SC and the lowercase suffix.
  - `MALFORMED_DECLARED_LEAD`: a kind-prefixed token in a declared position that does not full-match the core. Detection is **uppercase-kind only** and case-sensitive: `FR`/`NFR`/`SC`/`C`, then `-` or `_`, then a digit or an uppercase letter (no `(?i:…)` on this pattern). WP05 consumes it and pins the negative controls `- C-style strings`, `| C-suite |` and `- c-001 lowercase` (none may match); add the same three as negative controls here, with `| C-S1 |` and `| C-007-mission |` as same-fixture positives.
  - Reason constants: `MALFORMED = "malformed"`, `UNKNOWN_SPEC_ID = "unknown_spec_id"`, `FOREIGN_QUALIFIED = "foreign_qualified"`. Every reason string in the grammar (and in WP03/WP05, which import them) comes from these three names; no consumer restates the literals.
  - `classify(raw, declared) -> RefVerdict` (`Accepted(RequirementId)` | `Rejected(raw, reason)`), plus `FAILING_REASONS = frozenset({MALFORMED, UNKNOWN_SPEC_ID})`. The order is: does not parse → `MALFORMED`; has a qualifier → `FOREIGN_QUALIFIED`; not in `declared` by canonical form → `UNKNOWN_SPEC_ID`; otherwise Accepted.
  - `RULE_TEXT = "<kind>-<digits>[<lowercase letter>]"`: the grammar rule string (the `rule` value in `contracts/json-payload-deltas.md`). WP03's hint and WP05's lint `rule` derive from it. It must not read as a pattern literal to the C-001 gate (it has no `-\d`), and the gate test proves it.
  - `blank_html_comments(text) -> str`: returns `text` with every `<!-- … -->` span, markers included, replaced by spaces, with every newline inside the span kept, so line count and character positions are preserved. An unterminated `<!--` blanks to the end of the text. `_declared_ids` (T004) and WP05's lint both call it, so finalize, the runtime and setup-plan agree on what a comment hides.
- **Compile rules**: `from kernel._safe_re import re` for every pattern (check `src/kernel/_safe_re.py`: RE2 has no lookbehind or backreferences, and `re.VERBOSE` is unsupported). Scope case-insensitivity to the kind only, with `(?i:FR|NFR|SC|C)` or an equivalent. Do NOT pass `re.IGNORECASE` globally, because it would leak into the suffix class and into the qualifier's slug and mid8 classes. Whichever form you pick, pin it with the tests below and record the choice in the `## Tracer notes` section of your hand-off.
- **Required tests.** Each refusal gets a same-fixture positive control (tactic acceptance-criteria-non-vacuity):
  - Placeholder: `find_all("… FR-00N …", spec_scan=True) == []`, while `FR-006a` in the same text is found. Also pin, explicitly, what `spec_scan=False` does with `FR-00N`.
  - Canonical form: `canonical("FR-006A") == "FR-006a"` and `canonical("fr-006a") == "FR-006a"`, while `canonical("FR-006-a") is None`.
  - Digit width: `parse("C-1") != parse("C-001")`, while `parse("C-001") == parse("c-001")`.
  - Qualifier consumed: `find_all("see other-mission#FR-001", …)` yields one foreign ID and never a local `FR-001`, while a bare `FR-001` in the same text yields a local one.
  - Prose compounds: `parse("FR-008-mandated") is None` and `parse("C-007-mission") is None`, while `parse("FR-008")` is not None. Under the token-boundary rule, `find_all` yields NOTHING from `FR-008-mandated` or `C-007-mission` (not the bare prefix, as today's `_REF_FIND_PATTERN` does), while a bare `FR-008` in the same text is found. This can only shrink the bare-prose candidate set (C-009 keeps its kinds); if `test_bare_prose_corpus_ratchet.py` or the `test_bare_prose_false_negative_sample.py` figures move, stop and record it (T004 step 3), do not re-pin.
  - Boundary negative controls (each with a same-text positive): `IC-01` never yields `C-01`; `XFR-001` yields nothing; `FR-00N` never yields `FR-00`; `FR-008-mandated` yields nothing; `FR-0011x` yields exactly `FR-0011x`, never `FR-0011` or `FR-001`.
  - Dotted: `parse("FR-001.1") is None`, while `parse("FR-001")` is not None.
  - Uppercase mid8 slug tail: `requirement-id-grammar-01M3NRCA#FR-001` parses with `mission == "requirement-id-grammar-01M3NRCA"`. A plain lowercase slug parses too.
  - Declared shapes: each of the 4 shapes declares an `SC-001` and an `FR-006a`. An uppercase-suffix declaration (`| FR-006A |`) declares nothing, while `| FR-006a |` on the next line does. `IC-01` is never an ID (C-004).
  - Verdict table: one row per `data-model.md` RefVerdict case, all on one `declared` set, plus `FAILING_REASONS` membership, with `FOREIGN_QUALIFIED` NOT in it. Each reason constant equals its contract string.
  - `tokenize_refs`: list, scalar with commas, scalar with whitespace, `None`, and a non-str item.
  - `blank_html_comments`: a single-line and a multi-line comment are blanked; `len()` and the line count are unchanged and a token after the comment keeps its line and column; an unterminated `<!--` blanks to the end; text with no comment is returned unchanged (positive control).
  - RE2: `kernel._safe_re.is_re2_active()` is true and every exported pattern compiles (a C-005 guard).
- **Shard enrolment**: add the new test file to `_interpreter_shard_roster.py` shard 5 and to the `ci-nightly.yml` shard-5 `run:` line (see out-of-map edits).
- **Files**: `src/specify_cli/requirement_mapping/grammar.py`, `tests/specify_cli/test_requirement_id_grammar.py`, plus the two enrolment lines.
- **Dead-symbol note**: `tests/architectural/test_no_dead_symbols.py` fails an `__all__` member that has no non-test src caller. Some grammar names have no consumer until a later WP (`MALFORMED_DECLARED_LEAD` waits for WP05). The planned public surface is the package: re-export the grammar API from `requirement_mapping/__init__.py` (plan.md: "re-exports (import path unchanged)"), which the gate counts as a caller. Prefer real consumption wherever T004 gives one (`classify`, `canonical`, `find_all`, `tokenize_refs`, `DECLARED_SHAPE_PATTERNS`, `blank_html_comments`). Record any re-export-only symbol in your hand-off's `## Tracer notes`.

### Subtask T004 – Rewire `requirement_mapping/__init__` onto the grammar

- **T004a (red-first, #3519).** Before the rewire, commit an issue-pinned `@pytest.mark.regression` test in `tests/specify_cli/test_requirement_mapping.py`. It uses the public functions finalize and the runtime call. On a spec declaring `| FR-006a | … |`, it asserts that `parse_requirement_ids_from_spec_md(spec)["functional"]` contains `FR-006a` and that `compute_coverage({}, set(functional))["unmapped_functional"]` lists it. Its docstring names `#3519` / FR-008. The test must be RED on this commit.
  - **CLI-level repro (same commit, same file, also `@pytest.mark.regression`, docstring `#3519` / FR-008).** Invoke `finalize-tasks --validate-only --json` through typer `CliRunner` on `specify_cli.cli.commands.agent.mission.app` (`["finalize-tasks", "--mission", slug, "--json", "--validate-only"]`), copying the `_run_finalize` pattern from `tests/specify_cli/cli/commands/test_finalize_tasks_validate_only_readonly.py:153-169` (it patches `locate_project_root` and `run_git_preflight`). The fixture spec declares `| FR-001 |` and an unmapped `| FR-006a |`; the only WP maps `FR-001`. Assert `exit_code == 1` and that the JSON's `unmapped_functional_requirements` names `FR-006a`. It is RED on the planning base (exit 0: the old finder never sees `FR-006a`) and GREEN after the rewire. Positive control on the same fixture: map `FR-006a` too and assert exit 0.
  - After T004b both go green: demote them to plain tests (remove `regression`) in the same commit. The reason is that this rewire is what closes the NFR-005 defect (c) coverage hole, so the red-first evidence, function-level and CLI-level, is captured here. WP02 cites it. Note both in the Activity Log.
- **T004b steps**:
  1. Delete the pattern literals at `:15-17` and `:55-78`. Keep `_DECLARED_ID_PATTERNS` as an alias of `grammar.DECLARED_SHAPE_PATTERNS`. Keep `_REF_FIND_PATTERN` importable as the grammar-generated **legacy-compat alias** `\b(?:FR|NFR|C)-\d+\b` (unqualified, unsuffixed, no compound check; `group(0)` is the bare token). It exists ONLY so the frozen `test_bare_prose_false_negative_sample.py` keeps its `finditer`/`group(0)` semantics and figures unchanged (analysis F9 ruling). Production code (`_declared_ids`, `find_bare_prose_requirement_ids`, `_raw_ref_tokens`) must use `grammar.find_all`, never the alias. Document this in a comment. The boundary is implemented with `\b` at both ends plus the in-code compound check (`contracts/grammar.md`), not with a consumed leading group. Keep `_SC_REF_FIND_PATTERN` only if `find_discarded_sc_refs` still needs it, and generate it from the grammar either way.
  2. `_declared_ids` still returns `set[str]` of canonical strings, now including SC and lowercase-suffixed IDs. Keep the first-ID-per-line `break` and its docstring rationale. It scans `grammar.blank_html_comments(text)`, so a declaration inside an HTML comment is NOT declared, as `data-model.md` ("Declared-ID set") and `contracts/grammar.md` ("Declared positions") require. Pin it: `| FR-004 |` inside a comment is not in `all`, while the same row outside the comment is (positive control). This is a behaviour change for any spec that declares IDs inside a comment; record it in your hand-off's `## Tracer notes`, and WP08's (c) scan reports every declared-set change it causes.
  3. `_raw_ref_tokens` and `find_bare_prose_requirement_ids`: the candidate set stays unqualified, unsuffixed FR/NFR/C (C-009). Get it by filtering `grammar.find_all(..., spec_scan=True)` on `mission is None and suffix is None and kind in {FR, NFR, C}`, so `slug#FR-001` is never a candidate. Keep `_requirement_named_sections` and `find_bare_prose_requirement_ids` in `__init__` (the monkeypatch at `:361`). **Decision point:** the per-line declared-shape skip now also skips SC/suffixed declaration lines, which can only shrink candidates. Keep it (it is consistent with "first ID on a declaration line"). Verify that `test_bare_prose_corpus_ratchet.py` still reports exactly 1 and that `test_bare_prose_false_negative_sample.py`'s frozen figures hold; if either moves, stop and record it rather than re-pinning.
  4. `parse_requirement_ids_from_spec_md` keeps `all` and `functional`. `all` now includes SC and suffixed IDs, and `functional` includes suffixed FRs. ADD `non_functional`, `constraint` and `success_criteria`, each sorted.
  5. `validate_ref_format` / `validate_refs` keep their 2-tuple signatures. Well-formed output is in canonical form (qualified IDs as `slug#…`). Malformed entries keep today's uppercased form, because WP03 owns their final wire shape. Membership is by canonical form. A qualified ref lands in `validate_refs`' unknown list, as any undeclared ref does.
  6. `classify_stale_refs`: rewire only its membership test to canonical form; keep its signature, its two existing buckets and its current use of the `malformed` parameter. Add NO `foreign_qualified` bucket. WP03 owns that bucket and the unconditional deletion or replacement of `classify_stale_refs`, `validate_refs` and `validate_ref_format`, whose only product callers (`tasks_map_requirements.py:512-538`, `tasks_mapping_core.py:43-44,141-142`) are WP03-owned.
  7. `compute_coverage` matches by `canonical()`; malformed refs never map anything.
  8. `normalize_requirement_refs_value` returns de-duplicated canonical IDs, SC, suffixed and qualified included, found per item with `find_all(item, spec_scan=False)`. Finalize still consumes it until WP02.
  9. `_extract_raw_tokens` delegates to `grammar.tokenize_refs`.
- **Re-pins in `tests/specify_cli/test_requirement_mapping.py`** (each gets a one-line comment naming FR-002 or FR-003):
  - `:64-70`: `FR-003a` moves from `malformed` to `unknown_spec_id`. Feed `classify_stale_refs` the real `validate_ref_format(...)` output instead of the hand-typed `["FR-003A"]`, so the pin exercises the grammar.
  - `:181`: the exact-dict pin gains the three empty grouped keys.
  - Any other pin that asserted a suffixed or SC token as malformed or absent.
- **New cases in `tests/specify_cli/test_requirement_mapping.py`:**
  - FR-009 on the production path: `find_bare_prose_requirement_ids` on a Functional Requirements section holding `other-mission-01KAAAAA#FR-010` and a bare `FR-011` (neither declared) flags `FR-011` only. The bare `FR-011` is the same-fixture positive control.
  - The HTML-comment declaration pin from step 2.
- **Files**: `src/specify_cli/requirement_mapping/__init__.py`, `tests/specify_cli/test_requirement_mapping.py`, and (only if a pin genuinely moves) `test_requirement_mapping_coord_surface.py` / `test_bare_prose_false_negative_sample.py`.

### Subtask T005 – Migrate the other parsers onto the grammar

- **`mission_parsing.py:96-111`** (`_parse_requirement_refs_from_tasks_md`): replace the inline ID literal at `:108` with `grammar.find_all(match, spec_scan=False)`, rendering canonical strings with order-preserving dedupe. The `Requirements?\s*(?:Refs)?` line-selector regex is not an ID pattern; keep it. Keep the function name, because `mission.py:136` and `mission_finalize.py:106` re-export it (`test_mission_shim_reexports.py`).
- **`status/wp_metadata.py:335-336`** (legacy scalar `requirement_refs`): replace `[s.strip() for s in refs.split(",") if s.strip()]` with `grammar.tokenize_refs(refs)`. Leave the `tracker_refs` sibling at `:338-341` alone; it is not a requirement ID. Delta to pin and record: a whitespace-only-separated scalar (`"FR-001 FR-002"`) now splits into two items where it used to stay one. Comma-separated scalars are unchanged.
- **`consolidation/retention.py:12,64`** (HiC ruling, Decision Moment `01M3P2HXKASQY2ZKSEY3MAWA9H`, which supersedes `01M3P07HV88QNVVKP3E2W28VB6`): delete `_CONSTRAINT_ROW_ID = re.compile(r"^C-\d+$", re.IGNORECASE)`. At its only use (`:64`, `if not _CONSTRAINT_ROW_ID.fullmatch(cells[0]):`), accept the cell only when `grammar.parse(cells[0])` returns an ID that is unqualified (`mission is None`) with `kind == "C"`. Kind input stays case-insensitive, as today (the grammar already does this). Keep `constraint_id = cells[0]` verbatim; the consumer changes no case itself (C-001). Keep `import re`: the other module patterns (`_NEGATED_RETENTION`, `_RETENTION_VERB`, …) still use it. **Intended behaviour change:** a letter-suffixed constraint such as `C-007a` now counts as a retention constraint row, as it does everywhere else in the grammar. A qualified `slug#C-001` never counts. After this step the file holds no requirement-ID literal, so T006 does NOT allowlist it.
  - **Tests in `tests/consolidation/test_retention.py`** (reuse `_write_spec_rows`' table shape, with a helper that lets the first cell vary; each fixture row carries a terminal status and a retaining constraint such as "Keep branches after merge.", so only the ID cell decides):
    - Same-fixture positive and negative controls, parametrised over the first cell: `C-001` → retained, `c-001` → retained, `C-007a` → retained, `other-mission#C-001` → `None`, `C-S1` → `None`, `IC-01` → `None`. Assert `constraint_id` equals the cell verbatim on the positives.
    - A pin that existing behaviour for plain `C-###` rows is unchanged: the existing tests stay green with zero edits, plus one explicit pin that a multi-row spec of plain `C-001`/`C-002` rows yields the same `MissionRetention` as on the planning base (first retaining row's ID and constraint, OR-ed flags).
- **Pins (behaviour identical for existing FR/NFR/C)**:
  - `test_mission_parsing.py`: the existing `test_parse_requirement_refs_uppercases_and_dedupes` stays unchanged and green. Add SC and suffixed cases (`fr-006A` → `FR-006a`), and a `slug#FR-001` case that is kept as foreign, never as local `FR-001`.
  - `test_wp_metadata.py`: comma scalar → the same list as before (unchanged behaviour), whitespace scalar → split (the new behaviour, named FR-001), and a list input left untouched.
- **Import**: import the grammar module (`from specify_cli.requirement_mapping import grammar`, or the submodule) and never the whole package's heavy parts. `__init__` must stay import-light (see Context).

### Subtask T006 – C-001 architectural gate and allowlist

- **Model**: read `tests/architectural/test_charter_path_literal_authority.py` and `charter_path_literal_allowlist.yaml` in full. Copy their shape: an AST literal scan, a composite key, a glob-refusal, a staleness twin-guard, and a frozen shrink-only baseline.
- **Detector**: a literal counts as a requirement-ID pattern when its value has regex shape over a kind: an alternation containing `FR|NFR` / `NFR|` / `SC|`, or a kind followed by `-\d` (e.g. `FR-\d`, `NFR-\d`, `C-\d`, `SC-\d`). The kind token must be preceded by the start of the string or a non-letter character, so `IC-\d` (the concern-ID grammar, C-004) never counts. Plain prose IDs (`FR-005`, `FR-NNN`) must not match.
- **Scan context (binding; state it in the gate's module docstring)**: every string `ast.Constant` under `src/`, including `JoinedStr` parts, EXCEPT docstrings (the first-statement `Expr` of a module, class or function). A narrower fallback (only `re.*` call arguments plus module-level pattern constants) is allowed only with orchestrator sign-off: if the full scope produces a false positive you cannot resolve, stop and escalate with the offending literal.
  - Today's census (verified) has exactly 6 files with ID regex literals: `requirement_mapping.py:15-17,55-72`, `mission_parsing.py:108`, `runtime_bridge_cores.py:93`, `retrospective/generator.py:80`, `missions/_substantive.py:107` and `consolidation/retention.py:12` (`_CONSTRAINT_ROW_ID = r"^C-\d+$"`). After T004/T005 exactly three remain outside `grammar.py`: `runtime_bridge_cores.py`, `retrospective/generator.py` and `missions/_substantive.py`. `consolidation/retention.py` is migrated by T005 and holds no ID literal afterwards, so it is NOT allowlisted (a leftover `_CONSTRAINT_ROW_ID` would make the single-source test fail, which is the intended tripwire). The docstring `"Check refs match FR|NFR|C-\\d+ format."` (`requirement_mapping.py:407`) is exactly the false positive the docstring exclusion must drop; add a test for it.
- **Gate tests** (all must exist):
  1. **Floor / non-vacuity**: the live scan finds at least one site in `src/specify_cli/requirement_mapping/grammar.py`, the core literal. If it finds none, the gate fails as vacuous.
  2. **Single source**: every live site is either in `grammar.py` or keyed in the allowlist.
  3. **Self-mutation**: a synthetic module written to `tmp_path` holding an ID regex (both an `re.compile` argument and a module constant) is detected. A same-fixture control module holding only prose `FR-005` and a docstring pattern is not.
  4. **Concern-ID negative control**: a synthetic module holding `re.match(r"^IC-\d{2}$", ref)` (the `core/wps_manifest.py:85` shape) is NOT flagged, while the same module with `r"^C-\d{2}$"` is.
  5. **Stale allowlist**: an allowlist entry with no live site fails, naming the entry. Test this with a synthetic allowlist.
  6. **Shrink-only, two-sided**: the entry count must EQUAL the baseline recorded in the YAML (3 at WP01; WP04 lowers it to 2). Growth fails, and a drop without lowering the baseline in the same edit fails too. Glob-shaped `file` values are refused at load time.
- **`requirement_id_pattern_allowlist.yaml`**: a header comment in the style of the charter allowlist (it is shrink-only and names the drain procedure: remove the entry AND lower the baseline in one edit), a `baseline: 3`, and exactly three entries keyed by file, qualname or constant name, and literal:
  - `src/specify_cli/missions/_substantive.py` (`_FR_TABLE_ROW`): `frozen: true`, `followup: "to be filed at closeout"`, and a rationale naming C-001's setup-plan substantive-gate divergence.
  - `src/specify_cli/retrospective/generator.py` (`_FR_REF_RE`): `frozen: true`, `followup: "to be filed at closeout"`, and a rationale.
  - `src/runtime/next/runtime_bridge_cores.py` (`_REQUIREMENT_REF_PATTERN`): `transitional: "WP04 removes"`. When WP04 deletes the pattern, it removes this entry and lowers the baseline to 2 in the same edit.
  - `src/specify_cli/consolidation/retention.py` gets NO entry: it is a migrated consumer (T005), per the HiC ruling (Decision Moment `01M3P2HXKASQY2ZKSEY3MAWA9H`).
- **Canonicalisation and tokenisation**: this gate is a pattern-literal gate. It cannot see `.upper()` or `split(",")`. Say so in the gate's docstring. Those two halves of C-001 are enforced by review (see Review Guidance).
- **Markers**: `pytestmark = pytest.mark.architectural` plus `fast`, matching the sibling gates. `tests/architectural/` is enrolled as a directory in the shard roster, so it needs no roster edit.

### Subtask T007 – Validation run and evidence

- Run every command under `## Validation surface`. Record in the Activity Log the exact commands, with passed/failed/skipped counts for each.
- **Smoke reports**: WP01 changes what `normalize_requirement_refs_value`, `parse_requirement_ids_from_spec_md` and `validate_ref_format` return while finalize, map-requirements and the runtime still consume them unchanged. The smoke files may therefore show breaks. The expected classes are:
  - byte-contract or malformed-bucket flips (`FR-001a`), which are WP03's;
  - finalize accepting or failing on newly visible SC and suffixed refs, which is WP02's;
  - SC refs no longer dropped, which is WP02's.

  Report each break (test id → owning WP) in the Activity Log. Do NOT fix them here. Classify any other red with the CLAUDE.md baseline-red procedure: re-run on the planning base with `PYTHONPATH=<worktree>/src`, and only a red that is new to your branch is yours.
- **Tracer notes**: add 1–3 sentence dated entries (`- 2026-09-29: …`) to the `## Tracer notes` section of your hand-off, grouped as design decisions (the case-scope form, the gate scan scope, the declared-skip widening, the HTML-comment declared-set change, the re-export-only symbols), approach (the commit sequence as landed) and tooling friction (anything that fought you). The orchestrator commits them.

## Validation surface

**Test files** (run all of them together):

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q \
  tests/specify_cli/test_requirement_mapping.py \
  tests/specify_cli/test_requirement_mapping_coord_surface.py \
  tests/specify_cli/test_bare_prose_false_negative_sample.py \
  tests/specify_cli/test_requirement_id_grammar.py \
  tests/specify_cli/cli/commands/agent/test_mission_parsing.py \
  tests/specify_cli/cli/commands/agent/test_mission_shim_reexports.py \
  tests/specify_cli/status/test_wp_metadata.py \
  tests/consolidation/test_retention.py \
  tests/specify_cli/missions/test_substantive_gate_formats.py
```

`test_substantive_gate_formats.py` must be green. Its only allowed edit is the SC re-pin described under out-of-map edits.

**Smoke only (unmodified; report breaks, do not fix):**

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q \
  tests/specify_cli/cli/commands/agent/test_mission_finalize_phases.py \
  tests/specify_cli/test_cli/test_map_requirements.py
```

**Named architectural gates (by file, never the directory):**

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q \
  tests/architectural/test_requirement_id_grammar_single_source.py \
  tests/architectural/test_layer_rules.py \
  tests/architectural/test_ratchet_baselines.py \
  tests/architectural/test_no_dead_symbols.py \
  tests/architectural/test_no_dead_modules.py \
  tests/architectural/test_bare_prose_corpus_ratchet.py \
  tests/architectural/test_bridge_cores_import_boundary.py \
  tests/architectural/test_cold_import_status_boundary.py
```

`test_bare_prose_corpus_ratchet.py` must report exactly 1 flagged spec. `test_cold_import_status_boundary.py` is added by the planner because T005 creates a new `status → requirement_mapping` import edge; it is a targeted gate, not a sweep. `test_layer_rules.py` also covers the new `consolidation → requirement_mapping` edge through `TestMergeCliBoundary` (the only import-boundary gate on `specify_cli/consolidation/**`).

**Owning module fast tier (baseline):** `make test-fast`.

**Static checks** (on the touched files, zero findings, no new `noqa` / `type: ignore`):

```bash
.venv/bin/ruff check src/specify_cli/requirement_mapping/ src/specify_cli/cli/commands/agent/mission_parsing.py src/specify_cli/status/wp_metadata.py src/specify_cli/consolidation/retention.py tests/specify_cli/test_requirement_id_grammar.py tests/consolidation/test_retention.py tests/architectural/test_requirement_id_grammar_single_source.py
.venv/bin/ruff format --check src/specify_cli/requirement_mapping/ src/specify_cli/cli/commands/agent/mission_parsing.py src/specify_cli/status/wp_metadata.py src/specify_cli/consolidation/retention.py tests/specify_cli/ tests/consolidation/test_retention.py tests/architectural/test_requirement_id_grammar_single_source.py
.venv/bin/mypy --strict src/specify_cli/requirement_mapping/ src/specify_cli/cli/commands/agent/mission_parsing.py src/specify_cli/status/wp_metadata.py src/specify_cli/consolidation/retention.py
```

## Risks & Mitigations

- **Monkeypatch coupling.** Five tests patch attributes on the package: `_requirement_named_sections`, `find_bare_prose_requirement_ids`, `parse_requirement_ids_from_spec_md` and `find_undeclared_requirement_citations` (sites listed in T002).
  - Mitigation: keep all four DEFINED in `__init__`, not re-exported from `grammar.py`. If they were re-exported, a patch on the package would miss intra-grammar calls.
  - Also keep `find_bare_prose_requirement_ids` calling `_requirement_named_sections` through module globals.
  - Callers in finalize, map-requirements and the runtime import these names lazily from the package, so the patches keep working.
- **Private-name imports.** `_DECLARED_ID_PATTERNS`, `_REF_FIND_PATTERN` and `_declared_ids` must stay importable from `specify_cli.requirement_mapping` and keep their object types: a tuple of compiled patterns, a compiled pattern, and `set[str]`.
- **Uppercase suffix scanning parsing placeholders.** `FR-00N` (about 37 corpus hits) would parse as `FR-00n` if spec scanning tolerated case. Mitigation: `spec_scan=True` is lowercase-only; tolerance lives only in `parse`/`canonical` and `find_all(spec_scan=False)` over ref items; there is a paired test.
- **`re.IGNORECASE` leaking into the suffix.** A global flag makes `(?-i:…)` the only thing between you and placeholder parsing. It also makes the slug and mid8 classes case-blind. Mitigation: scope `(?i:…)` to the kind, and use no global flag on any grammar pattern. The tests pin `FR-00N` (not found), `fr-001` (found) and an uppercase-slug control.
- **Stale bytecode.** Two `requirement_mapping*.pyc` files sit in `src/specify_cli/__pycache__/`. Remove them right after the `git mv`. If an import behaves strangely, check them first (see also the stale-venv and stale-install gotchas in CLAUDE.md).
- **Import cycle.** `status/wp_metadata.py` is loaded by `specify_cli.status`, and it will import the grammar, which runs the package `__init__`. Any module-level `specify_cli.status` import in `__init__` closes a cycle. Keep those imports function-local; `test_cold_import_status_boundary.py` is the tripwire.
- **Dead-symbol gate.** Grammar names whose consumer lands in WP02–WP05 must be reachable through a package re-export (see T003). Otherwise `test_no_dead_symbols.py` goes red.
- **`coverage_breadth_baseline.json` key rename (informational).** `tests/release/coverage_breadth_baseline.json:3615` keys `src/specify_cli/requirement_mapping.py`. After the move the measured path is the package. This is informational and not a gate; do not edit the baseline here. Note it in the Activity Log for the closeout.
- **Intermediate-state behaviour.** Between WP01 and WP02/WP03, finalize and map-requirements see SC and suffixed IDs through the old code paths. The smoke breaks are expected and belong to those WPs (see T007).
- **Red-first bookkeeping.** T004a captures NFR-005 defect (c) (#3519) at function level and through the `finalize-tasks` CLI. WP02's end-to-end #2991 repro seeds `FR-006A`, an uppercase-suffix spelling that `normalize_requirement_refs_value` respells, so it is still red on WP02's base; keep that respelling behaviour (T004 step 8).

## Review Guidance

- **Exactly one place defines ID patterns.** `grep -rnE 'FR\|NFR|FR-\\d|NFR-\\d|SC-\\d|[^A-Za-z]C-\\d' src --include='*.py'` returns only `grammar.py` plus the three allowlisted files. `requirement_mapping/__init__.py`, `mission_parsing.py`, `wp_metadata.py` and `consolidation/retention.py` contain no ID literal.
- **Canonicalisation and tokenisation are single-sourced.** There is no `.upper()` on a requirement ref, and no `split(",")` on `requirement_refs`, in the touched files outside `grammar.py`. The gate cannot see these, so review must.
- **The gate is non-vacuous.** The floor test fails if `grammar.py`'s literal disappears. The self-mutation test detects a synthetic offender, with a clean control. The stale-entry test fails on a dead entry. The `IC-` negative control is not flagged. The allowlist has exactly three entries (two `frozen` with `followup:`, one `transitional:`) and a baseline of 3 that the gate checks two-sided. `consolidation/retention.py` is not in it.
- **No behaviour change for existing FR/NFR/C** beyond the documented re-pins, each commented with FR-002 or FR-003. `test_bare_prose_corpus_ratchet.py` is still at 1. The existing `test_mission_parsing.py` pins are unchanged.
- **The tidy-first commit (T001) changes no test file.** The `git mv` commit (T002) is a pure rename.
- **RE2**: all grammar patterns compile under `kernel._safe_re`, and nothing uses lookbehind or backreferences.
- **Typed sources**: confirm that the implementer ran `mypy --strict` and both ruff gates in addition to pytest, and that the Activity Log carries the commands and counts.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Why this matters**: The acceptance system reads the LAST activity log entry as the current state. If entries are out of order, acceptance will fail even when the work is complete.

**Initial entry**:

- 2026-09-29T06:14:47Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `.venv/bin/spec-kitty agent tasks move-task WP01 --to <status>` to change WP status.
