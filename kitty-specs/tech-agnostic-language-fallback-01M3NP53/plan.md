# Implementation Plan: Tech-agnostic fallback for non-Python consumers

**Branch**: `issue-5283-tech-agnostic-language-fallback` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/tech-agnostic-language-fallback-01M3NP53/spec.md`

Planning questions were answered by the operator at the pre-spec point-cut and recorded as Decision Moments (`unknown_language_representation`, `stale_languages_reset`, `dead_code_not_applicable_shape`, `scope_folds`). The post-spec squad (architect-alphonso scope/sizing, reviewer-renata fakeability) findings are folded into the spec.

## Summary

Make the unknown-language path honest and neutral on three surfaces, without adding languages:

1. **Mission review** (`spec-kitty review`): a change set with nothing the Python-only dead-code gate can scan is recorded as a *skipped* gate with a non-failing `dead_code_not_applicable` finding (`MISSION_REVIEW_DEAD_CODE_NOT_APPLICABLE`) and tech-agnostic remediation; the pytest pre-check becomes a warning.
2. **Language authority** (`charter.activation.language_scope`): a declared-but-unrecognised language resolves to the reserved value `unknown`, which admits no language-scoped artifacts; hyphen-prefixed compounds (`librespot-java`) no longer activate a language.
3. **Charter compile/context**: `charter generate --from-interview` re-derives languages from the interview via an explicit precedence parameter (runtime reads keep compiled-first); unknown-language context renders neutral guidance plus one charter-extension advisory; `available_tools` diagnostics are de-conflated from language.

## Technical Context

**Language/Version**: Python 3.11+ (Spec Kitty CLI, `src/specify_cli`, `src/charter`)
**Primary Dependencies**: typer, rich, ruamel.yaml, pydantic (existing; no dependency added/changed — the supply-chain section does not apply)
**Storage**: files — `.kittify/charter/charter.yaml` (`catalog.languages`), `.kittify/charter/interview/answers.yaml`, mission `meta.json`, `mission-review-report.md`
**Testing**: pytest, targeted files only (NO_FULL_HEAVY_SUITES_IN_MISSION); red-first CLI tests via typer `CliRunner` / real git fixtures; mypy (strict on touched modules), ruff check + ruff format
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: single Python project (monorepo layout `src/<package>`)
**Performance Goals**: no measurable change; review and context stay well under the 2 s CLI budget (NFR-002: ≤100 ms delta)
**Constraints**: C-001..C-007 of the spec; complexity ≤15 per function; no new suppressions; charter/kernel modules keep `__all__`
**Scale/Scope**: ~375 prod LOC + ~990 test LOC + ~90 docs lines (post-spec sizing estimate, ~4× the naive reading)

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Status | Notes |
|---|---|---|
| Single canonical authority (DIRECTIVE_044) | PASS | `infer_repo_languages` stays the SOLE language authority; unknown detection, the re-derive precedence parameter and an `is_unknown_language()` predicate live in `language_scope.py`; renderers call the predicate, never test the literal. The dead-code gate's "supported files" stays a separate concept (file extensions the analyzer can scan) and does not read project languages. |
| Architectural alignment / layer rules | PASS | `charter` must not import `specify_cli`; the advisory constant lives in `src/charter/activation/`; review code stays in `specify_cli`. |
| ATDD / red-first (C-011, DIRECTIVE_034) | PASS | Every WP opens with a failing CLI-level acceptance test committed before the fix; deliberately-pinned tests are re-pinned with dated rationale (not deleted). |
| Campsite (DIRECTIVE_025, SO#2) | PASS | Tidy-first WP precedes functional change on the language surfaces (format defect, mypy no-any-return, broad `except`, characterization tests). |
| Terminology canon | PASS | New prose says Mission; terminology guard run on docs/prose changes. |
| Pack tiers | PASS | No built-in pack edit planned; advisory is product code. If `scoping` sentinel reservation touches doctrine validation only (code), no graph regen needed. |
| `__all__` convention (C-007) | PASS | New public names in `src/charter/**` are added to `__all__` and have ≥1 caller in `src/` (dead-symbol gate). |
| NO_FULL_HEAVY_SUITES_IN_MISSION | PASS | Targeted test surfaces are declared per concern below. |

No violations → Complexity Tracking not needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/tech-agnostic-language-fallback-01M3NP53/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1 (red-first acceptance walkthrough)
├── contracts/           # Phase 1 (CLI output contracts)
├── traces/              # tracer files (tooling-friction, approach, design-decisions)
└── tasks.md             # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/
├── _test_env_check.py                 # (read-only reference) assert_pytest_available
└── review/
    ├── __init__.py                    # _run_dead_code_gate, _record_gate (tri-state), pytest pre-check → warn
    ├── _dead_code.py                  # not-applicable discovery outcome + extension summary + remediation
    ├── _report.py                     # finding formatter for dead_code_not_applicable; GateRecord skip
    ├── _diagnostics.py                # DEAD_CODE_NOT_APPLICABLE enum member
    └── ERROR_CODES.md                 # new section; UNDETERMINABLE cause list; TEST_EXTRA_MISSING → warning

src/charter/
├── activation/
│   ├── language_scope.py              # UNKNOWN_LANGUAGE, is_unknown_language, unknown detection, hyphen rule, precedence param
│   ├── compiler.py                    # compile_charter(rederive_languages=...), available_tools message
│   ├── compact.py                     # Languages line via predicate + advisory; narrow the broad except
│   ├── context_renderers/bootstrap_text.py   # advisory in the full/bootstrap render
│   ├── charter_yaml_io.py             # campsite: no-any-return at :468
│   └── (advisory constant module or language_scope)  # CHARTER_EXTENSION_ADVISORY
├── offering/shared/scoping.py         # reserve "unknown" (authoring-time validator + runtime)
└── (doctrine validate guard)          # reject artifacts declaring applies_to_languages: [unknown]

src/specify_cli/cli/commands/charter/generate.py   # pass rederive_languages=from_interview

docs/guides/how-to/governance/extend-charter-for-unsupported-language.md   # new consumer how-to
docs/changelog/CHANGELOG.md                                                # [Unreleased] entry (closeout)

tests/
├── specify_cli/cli/commands/review/test_dead_code_baseline_git.py   # re-pin :95; new CLI red-first Zig/Go + mixed + tests-only
├── specify_cli/cli/commands/review/test_dead_code_baseline.py       # unit coverage of discovery outcome/formatter
├── specify_cli/cli/commands/review/test_diagnostic_codes_documented.py  # enum count 15 → 16
├── specify_cli/cli/commands/test_review.py                          # re-pin TEST_EXTRA_MISSING exit → warn
├── charter/test_language_scope.py                                   # unknown detection, hyphen rule, predicate
├── charter/test_active_languages_idempotency.py                     # stale [python] regenerate (new), guards kept
├── charter/test_context*.py / compact tests                          # advisory render
└── agent/cli/commands/test_charter_cli.py                           # CLI generate/context red-first
```

**Structure Decision**: existing single-project layout; no new packages. All test edits are non-golden modules (C-004 clarified).

## Research Summary (details in research.md)

- **R1 — What "supported" means for the dead-code gate**: unchanged — `.py` and (`src/`-prefixed or no `test` in the path). Not-applicable = the changed set is non-empty but contains no supported path. The note lists (a) unsupported extensions (sorted, de-duplicated, `(no extension)` for bare files) and (b) the count of excluded test-only Python paths, separately. `.py` is never listed as unsupported.
- **R2 — Gate recording**: `GateRecord.result` already allows `"skip"` (`_report.py:41`) but `_record_gate` is typed `Literal["pass","fail"]` (`review/__init__.py:181-186`) — widen it. `scan_dead_code` returns None (`_dead_code.py:301`), so it (or `_Discovery`) must return the outcome so `_run_dead_code_gate` (`__init__.py:234`) records `skip` for not-applicable while a plain `dead_code` finding still records `fail` (unchanged). `LEGACY_MISSION_DEAD_CODE_SKIP` keeps recording `pass` (unchanged). Gate 4 uses a frontmatter-only `not_applicable` with no finding; dead-code deliberately uses a finding + `pass_with_notes` so the unscanned state is visible in the report (operator). Side effect: the retrospective's findings count includes the note. The not-applicable finding type is not in `_HARD_FAILURE_FINDING_TYPES`, so the verdict is `pass_with_notes` by the existing rule; `_format_finding_line` returns None for unknown types (`_report.py:97`, `:162-164`) and would silently drop the line — the formatter is mandatory, with a test that the line appears in the written report.
- **R3 — pytest pre-check**: no review gate imports or runs pytest (lane check, dead-code string scan, BLE001 audit, issue matrix); `_check_env_skew` compares typer/click only and returns nothing without `uv.lock`. Downgrade `TestExtraMissing` to a printed warning carrying the code; keep the remediation string (as an installation note); keep the stdout JSON diagnostic line, adding `"severity": "warning"`. Re-pins `test_review.py:330/:364` must stub mission resolution (a bare repo would now exit 1 later for a different reason); also check `compat/test_review_migration.py`.
- **R4 — Unknown detection rule**: only `answers["languages_frameworks"]` (`interview.py:181`; `from_dict` stringifies every answer, `:282`, so lists arrive as `"['Zig', 'C']"`, empty as `"[]"`, null as `"None"` — treat `[]`/`None` as placeholders and strip list-repr brackets/quotes) can signal `unknown`, and only if: no recognised language across all answers; answer non-empty after strip/casefold; not equal to the shipped default (`src/charter/defaults.yaml`); not a placeholder (`""`, `n/a`, `na`, `none`, `tbd`, `any`, `language-agnostic`, `unknown`, `-`, `[NEEDS CLARIFICATION…]`). Implemented inside tier 2 of `infer_repo_languages` so pre-compile reads agree with compile. The same placeholder set filters the synthesizer's independent extraction (`activation/synthesizer/interview_mapping.py:271/:280/:413-414`) so `unknown`/placeholders never become an "Unknown Style Guide" target (`targets.py:130`).
- **R4b — Doctrine-derived vocabulary (operator, FR-017; kept after the de-scope decision)**: implemented as a lightweight YAML scan (NOT a raw DoctrineService — sole-door gates forbid it; service route measured ~2 s cold). After WP07 de-scopes language-independent tactics the shipped vocabulary is python, java, javascript, typescript, php, twig, html, css; tests use a synthetic overlay (`elixir`). Original text: before concluding `unknown`, match whole-word (casefolded, `(?<!\w-)` guarded) tokens of the languages/frameworks answer against the union of `applies_to_languages` declared by the active doctrine artifacts (built-in + org + project packs, loaded UNFILTERED, reserved/sentinel tokens excluded). A hit yields that language (e.g. `[go]`). The vocabulary provider lives in `charter.offering` (lowest layer, no call back into `infer_repo_languages` → no cycle), memoized per process/root to stay within NFR-002. It only feeds the languages/frameworks answer, never free prose.
- **R5 — Admit semantics (post-plan M2/M3)**: do NOT add `unknown` to `_SENTINEL_TOKENS` (sentinels mean "unscoped → always load", `scoping.py:59`, which would load an `[unknown]` artifact for every project). Instead: `UNKNOWN_LANGUAGE` + a `RESERVED_LANGUAGE_TOKENS` set in `charter.offering.shared.scoping` (lowest layer; `language_scope` re-exports); `applies_to_languages_match` strips reserved tokens from BOTH sides before matching — artifact scope empty after stripping → False (invalid, validator is the signal; recorded via the existing scope-filtered diagnostics); active set empty after stripping → False (admit none); hand-edited `[python, unknown]` ≡ `[python]`; `any`/`all` unchanged. Authoring-time guard lives in `src/specify_cli/cli/commands/doctrine.py:768-793` (`_check_applies_to_languages`, a duplicated sentinel set with an any/all-specific message) — import the sets from `scoping` (remove the copy) and give `unknown` its own message. `_catalog_miss.py:285-293` gains an `is_unknown_language` branch pointing at the charter-extension advisory (instead of "add 'unknown' to applies_to_languages").
- **R6 — Precedence parameter** (callers verified: `compile_charter` ← generate/activate/pack; `infer_repo_languages` ← compiler:424, compact:277, doctrine_service_builder:134 via the patch seam `charter.activation.context:89` — keep it compatible): `infer_repo_languages(repo_root, *, interview=None, prefer_interview=False)`; when `prefer_interview` is True and an interview is supplied, tier 1 is skipped and the result may be `None` (field absent). `compile_charter(..., rederive_languages: bool = False)` forwards it; only `charter generate` passes `rederive_languages=from_interview`. `activate.py` / `pack.py` untouched (default False). `--from-interview` is the generate default → documented. `--no-from-interview` passes the shipped `default_interview` (`generate.py:352-363`), not None, and must keep compiled precedence. **Split-brain fix (M1)**: `generate` also builds its doctrine service via `_build_doctrine_service_with_org_layer` → `build_activation_aware_doctrine_service` → `infer_repo_languages(repo_root)` compiled-first, which would resolve references under the stale value; both builders gain optional `interview=`/`prefer_interview=` kwargs forwarded to the same `infer_repo_languages` call, passed by `generate` only.
- **R7 — Tool message**: `_sanitize_catalog_selection` gains an optional per-label message formatter; only the `available_tools` caller uses the new wording. Verified: `available_tools` is a separate interview field (`interview.py:249`) and is not in the scanned `answers.values()`; tool words in free prose remain Python signals (out of scope).
- **R8 — Advisory**: one constant `CHARTER_EXTENSION_ADVISORY` in `charter.activation` naming the how-to page by its published title; rendered once in compact (after `Languages: unknown`) and once in bootstrap. The neutrality lint does NOT scan Python constants, `ERROR_CODES.md` or `docs/` (`lint.py:68,:378-380`) → add explicit neutrality tests for the advisory and the review remediation text (no Python file/layout/tool advice). Bootstrap has no Languages line and runs `_enforce_token_budget` last (`bootstrap_text.py:336`) → place the advisory where the budget cannot drop it; needs `repo_root`.
- **R9 — Homonym**: `evidence/code_reader.py:359` `primary_language="unknown"` (nothing detected; `charter status` prints `lang=unknown`; `synthesizer/write_pipeline.py:337` tests it) is a different concept; "renderers never test the literal" applies to `catalog.languages` only.
- **R10 — ADR**: no ADR governs language precedence (#2395/#3292 live in docstrings; ADR `2026-07-18-1` covers the catalog `languages` field). Add a short ADR `docs/adr/3.x/2026-09-29-1-...` (catalog.languages states, reserved `unknown`, doctrine-derived vocabulary, regenerate-only precedence bypass) and list reserved tokens in `docs/architecture/doctrine-kinds.md:95`.

## Implementation Concern Map

### IC-01 — Campsite on the language surfaces (tidy-first)

- **Purpose**: behaviour-preserving cleanup of the language/charter surfaces before functional change, plus characterization tests that pin today's tier semantics (compiled `[]` vs absent vs non-list, compiled wins at runtime, empty scan → None, default interview → None).
- **Relevant requirements**: NFR-001, NFR-003 (enabler for FR-008..FR-015)
- **Affected surfaces**: `src/charter/activation/language_scope.py` (format defect line 21, docstring trim deferred to IC-03), `src/charter/activation/charter_yaml_io.py:468` (mypy no-any-return), `src/charter/activation/compact.py:275-281` (narrow the broad `except Exception: pass` — let it propagate or narrow to the concrete error with a test), `tests/charter/test_language_scope.py`, `tests/charter/test_active_languages_idempotency.py`.
- **Sequencing/depends-on**: none
- **Risks**: `compact.py` except narrowing must not break context rendering on a repo without a charter — characterize that case first.
- **Targeted tests**: the two charter test files above, `tests/charter/test_catalog.py`, compact/context test files touching `compact.py` (grep), `ruff format --check` + mypy on the three files.

### IC-02 — Review: dead-code not applicable + pytest pre-check warning

- **Purpose**: #5283 + the pytest pre-check fold.
- **Relevant requirements**: FR-001..FR-007, NFR-004
- **Affected surfaces**: `src/specify_cli/cli/commands/review/{_dead_code.py,__init__.py,_report.py,_diagnostics.py,ERROR_CODES.md}`; tests `review/test_dead_code_baseline_git.py` (re-pin :95-110 to not-applicable naming `.md`; add CLI red-first Zig/Go-only, mixed Zig+py, tests-only-py), `review/test_dead_code_baseline.py`, `review/test_diagnostic_codes_documented.py` (count 15→16), `commands/test_review.py` (re-pin :330/:364 exit → warn; keep remediation assertions), `commands/test_review_git_baseline.py` (run).
- **Sequencing/depends-on**: none (independent lane)
- **Risks**: `_run_dead_code_gate` currently records `fail` on any appended finding — the skip must be decided from the scan outcome, not the finding list. Renaming the pinned test leaves `review/baselines/issue_2987_red_first.md:40` stale — add a dated note there. Keep `LEGACY_MISSION_DEAD_CODE_SKIP` semantics. Remediation text must be tech-agnostic (no `.py`, `src/`, `pytest` advice). `scan_dead_code` complexity stays ≤15 (extract a `_not_applicable_reason` helper).
- **Targeted tests**: all files under `tests/specify_cli/cli/commands/review/`, `tests/specify_cli/cli/commands/test_review.py`, `test_review_git_baseline.py`, `test_test_env_check.py`.

### IC-03 — Language authority: `unknown`, hyphen rule, precedence parameter

- **Purpose**: #5284 core + #4613 minimal + the authority half of #4614.
- **Relevant requirements**: FR-008, FR-009, FR-012 (parameter), FR-013, FR-014, FR-015
- **Affected surfaces**: `src/charter/activation/language_scope.py` (re-export `UNKNOWN_LANGUAGE`, `is_unknown_language`, detection rule R4, doctrine-derived vocabulary R4b, `(?<!\w-)` prefix guard on every pattern, `prefer_interview` parameter, docstring rewrite), `src/charter/offering/shared/scoping.py` (`UNKNOWN_LANGUAGE`, `RESERVED_LANGUAGE_TOKENS`, strip-both-sides rule), vocabulary provider in `src/charter/offering/` (new small module or existing catalog helper), `src/specify_cli/cli/commands/doctrine.py:768-793` (validator imports the sets, own message), `src/charter/activation/_catalog_miss.py:285-293` (unknown branch), `src/charter/synthesizer/interview_mapping.py` (placeholder filter), tests `tests/charter/test_language_scope.py`, `tests/charter/test_active_languages_idempotency.py` (keep :49/:185/:196 guards unchanged), `tests/doctrine/test_doctrine_validate_lang_guard.py`, `tests/doctrine/shared/test_scoping_any_all.py`, `tests/charter/test_context_catalog_miss.py`, `tests/charter/synthesizer/` (hyphen rule + placeholder filter ripple).
- **Sequencing/depends-on**: IC-01
- **Risks**: a naive rule would relabel default charters as admit-none (#3292 trap) — the default-interview positive control is mandatory. `unknown` combined with real languages in a hand-edited charter must not crash and must still admit the real languages. Dead-symbol gate: every new `__all__` name needs a `src/` caller within this IC (`_catalog_miss` uses `is_unknown_language`; scoping uses the reserved set). Go/C# regression avoided by R4b; verify with a synthetic project-overlay artifact scoped to `elixir` (shipped language-independent tactics are de-scoped by WP07).
- **Targeted tests**: `tests/charter/test_language_scope.py`, `test_active_languages_idempotency.py`, `test_doctrine_service_builder_unification.py`, doctrine validation tests (grep `_SENTINEL_TOKENS` / `any`/`all` guard), `tests/doctrine/` files covering `scoping.py` (grep), `tests/doctrine/` files covering validation/scoping, `tests/charter/synthesizer/`, named arch gates `tests/architectural/test_no_dead_symbols.py` and the layer-rule gate `tests/architectural/test_layer_rules.py` (new offering module).

### IC-04 — Compile wiring: `--from-interview` re-derives; tool message

- **Purpose**: #4614 end-to-end + FR-011.
- **Relevant requirements**: FR-011, FR-012, FR-013
- **Affected surfaces**: `src/charter/activation/compiler.py` (`rederive_languages` kwarg → `infer_repo_languages(..., prefer_interview=...)`; stamp absent when None; per-label message for `available_tools`), `src/specify_cli/cli/commands/charter/generate.py` (pass `rederive_languages=from_interview` and the builder kwargs), `src/charter/activation/doctrine_service_builder.py` + `_build_doctrine_service_with_org_layer` (optional `interview=`/`prefer_interview=` forwarded to the one `infer_repo_languages` call); tests: stale-`[python]` CLI regenerate trio (Zig→`[unknown]`, Rust→`[rust]`, agnostic→absent), `--no-from-interview` preserves, reference parity (no `python-*` reference ids in `charter.yaml` after a Zig regenerate), NEW assertions that activate/pack recompiles preserve `catalog.languages` (the existing `test_recompile_preserves_mission_4908.py` pins mission type only), `tests/charter/test_compiler.py` tool message. Red-first tests in a NEW module owned by this IC (not `test_charter_cli.py`, to avoid lane overlap with IC-05).
- **Sequencing/depends-on**: IC-03
- **Risks**: `generate` with `--no-from-interview` passes the shipped `default_interview` (`generate.py:352-363`) — must keep compiled precedence. Hand edits of `catalog.languages` are now replaced by plain regeneration — documented in IC-05.
- **Targeted tests**: `tests/charter/test_compiler.py`, `test_active_languages_idempotency.py`, `tests/specify_cli/cli/commands/charter/` files touching generate (grep; non-golden), `tests/agent/cli/commands/test_charter_cli.py`.

### IC-05 — Neutral context + advisory + consumer docs

- **Purpose**: #5284 context rendering + FR-016.
- **Relevant requirements**: FR-010, FR-016, C-002, C-005
- **Affected surfaces**: advisory constant (charter activation), `src/charter/activation/compact.py` (Languages line via `is_unknown_language`, advisory once), `src/charter/activation/context_renderers/bootstrap_text.py` (advisory once), new `docs/guides/how-to/governance/extend-charter-for-unsupported-language.md` + docs index/toc + cross-link from `troubleshoot-charter.md`; new ADR (R10) + `docs/architecture/doctrine-kinds.md:95` reserved-token note; tests: CLI context red-first (Zig fixture: `Languages: unknown`, one advisory, no python-* ids, ivan guidance present; Python sibling positive control), explicit neutrality tests for the advisory text, and ripple fixes in `tests/charter/test_context_token_budget.py`, `test_context_bootstrap_markers.py`, `test_context_selection_render.py`, `context_renderers/test_token_budget_sonar.py` limited to the unknown fixture. Red-first tests in a NEW module owned by this IC.
- **Sequencing/depends-on**: IC-03 (can run in parallel with IC-04 — no shared files)
- **Risks**: token-budget tests may assert fixed sizes; keep the advisory one short line and outside what `_enforce_token_budget` may drop. Golden/snapshot files to avoid: `tests/specify_cli/skills/__snapshots__/**`, `tests/cli/__snapshots__/doctor_doctrine_selections.txt`, `tests/consolidation/merge_driver_goldens/`, `tests/contract/snapshots/*.json` (none contain the affected strings). Docs freshness/index scripts must pass (`scripts/docs/docs_index.py --write`, `scripts/docs/check_docs_freshness.py --ci`).
- **Targeted tests**: context/compact/bootstrap test files (grep `bootstrap_text`, `compact`), `tests/agent/cli/commands/test_charter_cli.py`, `tests/architectural/test_no_legacy_terminology.py`, docs checks.

## Post-plan squad dispositions

Split-brain (M1 generate doctrine-service stale languages), sentinel semantics (M2), validator location (M3), catalog-miss advice, homonym, synthesizer path, profile filtering note, ADR, stdout JSON, lane test-module overlap, `_record_gate` typing, mandatory formatter, `--no-from-interview` correction, list-shaped answers, neutrality-lint gap, bootstrap budget placement, stale 2987 record: all `accepted` and folded above. Go/C# scoped-doctrine regression: resolved by operator decision (doctrine-derived vocabulary, R4b). Baseline: 129 passed on the four core targeted paths.

## Doctrine neutrality (operator directive 2026-09-29)

A doctrine audit (doctrine-daphne) found three language-independent tactics carrying language scopes (secure-regex — scope contradicting its own header, likely added to dodge the bias test's `applies_to_languages:` substring exemption; chain-of-responsibility; dependency-hygiene). Operator chose to de-scope all three in this mission (WP07, FR-018), closing the bias-test loophole; supply-chain-install-safety is already de-scoped by PR #5324. Post-tasks squad blockers (sole-door gates, dead-symbol gate, kind-prefixed reference ids, advisory before budget) are folded into each WP's binding-corrections section.

## Lane Sketch (input to /spec-kitty.tasks)

- **Lane A**: IC-02 (review) — independent.
- **Lane B**: IC-01 → IC-03 → {IC-04, IC-05} (IC-04 and IC-05 share no files and may run as parallel lanes after IC-03).

## Post-design Charter Re-check

Re-checked after Phase 1 artifacts: no new authority introduced (`unknown` is a value of the existing `catalog.languages`, owned by `infer_repo_languages`); no pack edits; no sibling-owned files; no dependency changes. PASS.
