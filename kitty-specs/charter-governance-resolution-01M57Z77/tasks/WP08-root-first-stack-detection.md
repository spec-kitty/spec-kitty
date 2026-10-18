---
work_package_id: WP08
title: Root-first stack detection and neutrality slug matching
dependencies: []
requirement_refs:
- FR-015
- FR-016
- C-006
subtasks:
- T035
- T036
- T037
- T038
phase: Phase 1 - Foundation
agent: claude
history:
- at: '2026-10-18T17:40:00Z'
  actor: claude-code/opus
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/evidence/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/activation/evidence/code_reader.py
- src/charter/activation/synthesizer/write_pipeline.py
- tests/charter/evidence/test_code_reader.py
- tests/charter/synthesizer/test_write_pipeline.py
role: implementer
task_type: implement
---

# Work Package Prompt: WP08 – Root-first stack detection and neutrality slug matching

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt. Then load action doctrine: `spec-kitty charter context --action implement --mission-type software-dev --no-mark-loaded`.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission charter-governance-resolution-01M57Z77`). Address every feedback item; record progress with `spec-kitty agent tasks add-history <WPID> --note "..."`.

---

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `issue-6404-charter-governance-resolution-work`
- **Merge target branch**: `issue-6404-charter-governance-resolution-work`

Execution worktrees are allocated per computed lane from `lanes.json`. Start with:

```bash
spec-kitty agent action implement <WPID> --agent claude --mission charter-governance-resolution-01M57Z77
```

Never construct a workspace path by hand.

## Shared Rules (every WP)

- **Red first** (ADR 2026-07-17-1): write the issue-pinned failing test(s) for the WP's acceptance scenarios and commit them on their own *before* the fix commit (`test: red repro for #NNNN ...`). After the fix, keep them as focused tests (not left marked `regression`).
- **Non-vacuity**: every absence/refusal assertion is paired with a positive control on the same fixture (tactic `acceptance-criteria-non-vacuity`).
- **Quality gates** (NFR-001): `uv run --frozen ruff check <changed files>`, `uv run --frozen ruff format --check --force-exclude <changed files>`, `uv run --frozen mypy --strict <changed src files>`; cyclomatic complexity ≤ 15; no new `# noqa` / `# type: ignore`.
- **Tests**: run the WP's own test files plus the owning subsystem directory (`tests/charter/` and, for `src/charter/offering/**`, `tests/charter_offering/`). Do not run `make test-full` or the whole `tests/architectural/` directory; run only the named gate files.
- **Terminology**: "Mission", never the retired term. Run `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q` when touching prose or `src/charter/offering/`.
- **Commits**: conventional types (`fix`, `feat`, `test`, `refactor`, `docs`); end every commit message with the session attribution lines given to you.
- Stay inside `owned_files`; a small out-of-map edit is acceptable only with a one-line rationale in the commit message and `add-history` note.

## Objectives & Success Criteria

The code-signal reader prefers root-level indicators, recognises Gradle Kotlin DSL / wrapper / Maven wrapper as Java, and breaks ties between same-depth manifests by source-file counts; the neutrality gate matches the scope tag against slug components (#6405).

Done when:
- fixture (root `build.gradle.kts`, `settings.gradle.kts`, `gradlew`, `src/main/java/App.java`; `site/package.json`, `site/tsconfig.json`) → `primary_language == "java"`, `scope_tag == "java"`;
- Kotlin-DSL-only Gradle build with Java sources → `java`; `gradlew`/`mvnw`-only root → `java`; Maven `pom.xml` → `java`;
- docs-only fixture (only `site/package.json` + `site/tsconfig.json`) → still `typescript` (control);
- root `pyproject.toml` + nested `a/b/c/package.json` + `tsconfig.json` → `python`;
- equal-depth tie broken by file counts; indicator order breaks count ties;
- frameworks/test frameworks still detected from nested files;
- `_is_generic_scoped("java", "java-style-guide")` is False and `_is_generic_scoped("java", "javascript-style-guide")` is True.

Requirement refs: FR-015, FR-016, C-006.

## Context & Constraints

- `src/charter/activation/evidence/code_reader.py`: `LANGUAGE_INDICATORS` :49-62 (insertion order = priority; only `pom.xml`, `build.gradle` for JVM); `_TreeScan` :100-107 (`indicator_files: set[str]`, `source_files`, `test_files`, `ts_files`, `js_files`); `_detect` :183-206 (returns `CodeSignals(primary_language, scope_tag=language, ...)` — keep shape); `_scan_tree` :208-268 (`max_depth=3`, prunes `EXCLUDED_DIRS` :29, basenames only :243, ts/js counts :246-249); `_detect_language` :319-344 (early return on any `package.json`).
- `src/charter/activation/synthesizer/write_pipeline.py:308-337` `_is_generic_scoped`: final line `return scope_tag not in target_slug` (substring).
- Culprit: `602a8ca99` (#688). Kotlin is not a language token (C-006 / assumption): `.kt` maps to `java`.
- Tests: `tests/charter/evidence/test_code_reader.py` (helper `_make_file` :22; per-stack tests; perf tests :180, :193 — keep within budget); `tests/charter/synthesizer/test_write_pipeline.py:156+` (`test_is_generic_scoped_*`).
- Behaviour change to flag in the PR: a repository with only nested manifests in two languages now resolves by file counts instead of JS winning.

## Subtasks & Detailed Guidance

### Subtask T035 – Red tests

- Add the fixtures above to `test_code_reader.py` (calling `CodeReadingCollector(Path).collect()` or the module's public entry used by existing tests) and the two `_is_generic_scoped` cases to `test_write_pipeline.py`. Commit red: `test: red repro for #6405 stack detection`.

### Subtask T036 – Scan restructuring

- `_TreeScan.indicator_depths: dict[str, int]` (shallowest depth per basename) + `ext_counts: Counter[str]`; property `indicator_files -> set[str]` (returns `set(indicator_depths)`) so `_detect_frameworks` / `_detect_test_frameworks` are unchanged.
- Extract `_observe(scan, filename, rel_path, depth)` from the inner loop.
- Add `build.gradle.kts`, `settings.gradle`, `settings.gradle.kts`, `gradlew`, `mvnw` → `java` to `LANGUAGE_INDICATORS`; add `SOURCE_EXT_LANG` (`.py` python, `.go` go, `.rs` rust, `.java`/`.kt` java, `.rb` ruby, `.php` php, `.ts/.tsx` typescript, `.js/.jsx/.mjs` javascript).

### Subtask T037 – Root-first `_detect_language`

- `hits = {n: d for n, d in indicator_depths.items() if n in LANGUAGE_INDICATORS}`; none → `"unknown"`; `top = min(hits.values())`; candidate languages in indicator order for names at `top` (`package.json` → `_js_or_ts(scan)`, the existing tsconfig/majority rule); one → return; several → `_break_tie(langs, ext_counts)` (max count; ties by order). Every function ≤ 15 (target ≤ 8).

### Subtask T038 – Neutrality slug components

- `return scope_tag not in target_slug.split("-")`; update the docstring bullet.

## Test Strategy

```bash
uv run --frozen pytest tests/charter/evidence/ tests/charter/synthesizer/test_write_pipeline.py tests/charter/test_phase3_integration.py -q
uv run --frozen pytest tests/charter/ -q -p no:randomly
uv run --frozen mypy --strict src/charter/activation/evidence/code_reader.py src/charter/activation/synthesizer/write_pipeline.py
```

## Risks & Mitigations

- Perf budget tests → no extra filesystem passes; counting happens in the existing walk.
- `build` in `EXCLUDED_DIRS` is a directory name, unrelated to `build.gradle*` files.

## Review Guidance

- Docs-only control and nested-only behaviour change covered.
- `CodeSignals` shape unchanged.
