---
work_package_id: WP05
title: setup-plan requirement-ID check and orchestrator-api plan parity
dependencies:
- WP01
requirement_refs:
- FR-013
- FR-014
- FR-015
- C-009
planning_base_branch: issue-2991-requirement-id-grammar
merge_target_branch: issue-2991-requirement-id-grammar
branch_strategy: Planning artifacts for this mission were generated on issue-2991-requirement-id-grammar. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2991-requirement-id-grammar unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-requirement-id-grammar-01M3NRCA
base_commit: 3968211cacb90f2503571daa3a1d54208e91827c
created_at: '2026-09-29T09:59:40.528548+00:00'
subtasks:
- T024
- T025
- T026
- T027
phase: Phase 2 - Consumers adopt the grammar
history:
- at: '2026-09-29T06:28:45Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/
create_intent:
- src/specify_cli/requirement_mapping/lint.py
- tests/specify_cli/test_requirement_id_lint.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/requirement_mapping/lint.py
- src/specify_cli/cli/commands/agent/mission_setup_plan.py
- src/specify_cli/orchestrator_api/commands.py
- tests/specify_cli/test_requirement_id_lint.py
- tests/specify_cli/cli/commands/agent/test_mission_setup_plan_phases.py
- tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – setup-plan requirement-ID check and orchestrator-api plan parity

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Also run `.venv/bin/spec-kitty profiles show python-pedro` and `.venv/bin/spec-kitty charter context --action implement`.

---

## ⛔ HARD RULE: no heavy suites

Never run any of these:
- the whole `tests/architectural/` directory;
- e2e or full-integration suites;
- performance, stress or timing suites;
- `make test-full`;
- a whole-repo `pytest`.

Run ONLY what `## Validation surface` lists: this WP's named test files, the owning module's fast tier, and the named architectural gate files, each by file name. Always invoke tests as:

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q <files>
```

This is charter C-007 / `NO_FULL_HEAVY_SUITES_IN_MISSION`. The corpus smoke in T027 is a read-only one-off script, not a suite.

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

Today `setup-plan` never reads the spec text for IDs: a malformed declared ID such as `C-007-mission` or `FR-001.1` goes unnoticed until finalize, or forever (#2066, SC-004). After this WP:

1. **FR-013.** `spec-kitty agent mission setup-plan` refuses a spec that holds a malformed kind-prefixed token in a declared position. It exits **1** with `error_code: SPEC_REQUIREMENT_IDS_INVALID` and `invalid_requirement_ids: [{token, line, rule}]`. The corrected spec on the same fixture proceeds.
2. **FR-014 / C-009.** An unqualified, well-formed, undeclared requirement-shaped token in prose produces a non-blocking warning in the additive `requirement_id_warnings` key. Qualified `<mission-slug>#<ID>` citations and table description-cell citations never warn. Prose never blocks.
3. **FR-015.** The orchestrator-api `plan` verb refuses the same spec. The envelope `error_code` is the contract-registered `PLAN_SETUP_FAILED`, and `data` carries `reason: SPEC_REQUIREMENT_IDS_INVALID` plus `invalid_requirement_ids`. No `upstream_contract.json` change, and no behaviour change for `tasks`/`specify`.
4. The live `spec-template.md` passes the lint: its `| FR-EXAMPLE |` row is inside an HTML comment.
5. NFR-004 holds. ruff (lint + format) and `mypy --strict` are clean on the touched src files. Every function is at complexity ≤ 15, and `setup_plan` stays at its current 11. Every new helper is tested in the same commit.

## Context & Constraints

- **Read in full before coding:**
  - `kitty-specs/requirement-id-grammar-01M3NRCA/spec.md`: US4 (AC1–AC4), FR-013/014/015, C-009, and Edge Cases (uppercase suffix, first-ID-per-line, prose compounds);
  - `plan.md`: "Behavioural changes by surface" (setup-plan and orchestrator-api rows) and IC-05;
  - `data-model.md`: "Grammar API" and "SpecLintResult";
  - `contracts/json-payload-deltas.md`: the setup-plan and orchestrator-api sections. These are your wire contract;
  - `research.md`: R4 (placeholders), R6 (why exit 1) and R7 (why the reason goes in data);
  - `tasks/WP01-requirement-id-grammar-package.md` T003: the grammar API you consume.
- **Grammar API (WP01, on your lane base).** Import it from `specify_cli.requirement_mapping.grammar`: `parse`, `canonical`, `find_all(text, *, spec_scan=)`, `blank_html_comments`, `DECLARED_SHAPE_PATTERNS`, `MALFORMED_DECLARED_LEAD`, `RULE_TEXT` and `RequirementId` (`.canonical`, `.is_foreign`). The declared-ID set comes from the public `specify_cli.requirement_mapping.parse_requirement_ids_from_spec_md(text)["all"]`, which after WP01 includes SC and suffixed IDs. Before you use `MALFORMED_DECLARED_LEAD`, read its docstring and tests in `tests/specify_cli/test_requirement_id_grammar.py` for the capture-group contract. You are its first consumer; it has had no caller until now.
- **C-001.** `lint.py` must contain NO requirement-ID regex literal. The single-source gate allows only `grammar.py`. Do not write an alternation such as `FR|NFR` in any string, message included; write "FR, NFR, C or SC". Blank HTML comments with `grammar.blank_html_comments`, never with a local helper, so the lint and the declared-ID scan hide exactly the same text.
- **Layering.** `lint.py` imports only stdlib, `grammar`, and the package's public `parse_requirement_ids_from_spec_md`. `mission_setup_plan.py` imports the lint function-locally, following the `_substantive` precedent at `:440`, so CLI cold-import cost does not grow.
- **Out of scope:**
  - a requirement-ID check on `plan.md` (C-008);
  - changing `_substantive.py`'s frozen FR-table pattern (C-001 allowlist);
  - bumping `CONTRACT_VERSION` (WP06 bumps it once, to 1.8.0, covering this WP's `requirement_id_warnings` and the `plan` remap);
  - `finalize-tasks` and `map-requirements` (WP02/WP03).
- **CLI:** always use `.venv/bin/spec-kitty`. Start with `.venv/bin/spec-kitty agent action implement WP05 --agent claude`, and work only in the workspace path it prints. Your lane base already contains WP01. Never pick a base by hand.

### Verified seam facts (current tree; re-verify on your base)

- **`mission_setup_plan.py`**
  - `SetupPlanLocalOutcome(payload, exit_code, render_kind)`: `:165-171`.
  - `_enforce_spec_gate`: `:367-401`. It prints `human_message`, emits JSON, and raises `typer.Exit(outcome.exit_code)` when the code is non-zero, so an evaluator outcome with exit 1 needs no change here.
  - `_evaluate_spec_gate`: `:404-475`. `SPEC_FILE_MISSING` (exit 1, `render_kind="error"`) is at `:415-429`. `is_committed`/`is_substantive` are at `:440-444`. The pass return `return None, None` is at `:445-446`. The `SPEC_NOT_SUBSTANTIVE_OR_UNCOMMITTED` blocked payload (exit 0) is at `:448-475`.
  - `_build_setup_plan_result`: `:896-954`. `_emit_setup_plan_result`: `:957-993`.
  - `setup_plan`: `:996-1173` (complexity 11). The gate call is at `:1089-1099` and the emit call at `:1133-1148`.
- **`orchestrator_api/commands.py`**
  - `is_allowed_error_code` import: `:147`. `_fail`: `:359-384`.
  - `_DECISION_UNREGISTERED_CODE_FALLBACK` + `_fail_from_decision_error`: `:401-433`. `_DESTRUCTIVE_OP_REFUSED_FALLBACK` + `_fail_from_destructive_op_refused`: `:449-479`. These are the fallback pattern you copy.
  - `_extract_json_payload`: `:2298-2316`. `_classify_delegate_error`: `:2319-2345`; it trusts any payload `error_code` at `:2342-2344`.
  - `plan`: `:2437-2497`. Its `except typer.Exit` is at `:2465-2475`, and the literal `_fail(cmd, "PLAN_SETUP_FAILED", …)` is at `:2481-2486`.
  - The module docstring describes `PLAN_SETUP_FAILED` at `:37-38`.
- **`core/upstream_contract.json` → `orchestrator_api.allowed_error_codes`.** `PLAN_SETUP_FAILED` is registered. `SPEC_REQUIREMENT_IDS_INVALID`, `SPEC_FILE_MISSING`, `TEMPLATE_CONFIGURATION_ERROR` and `PLAN_CONTEXT_UNRESOLVED` are NOT. So `plan` leaks unregistered codes today; that is the latent leak R7 names.
- **`tests/contract/test_orchestrator_api.py:245-254`.** It regex-scans `_fail(<cmd>, "<LITERAL>"` sites and asserts ⊆ allowed. A code passed through a variable is invisible to it; that is why the runtime `is_allowed_error_code` guard exists.
- **`tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py`** (integration + git_repo, owned)
  - `_PLAN_SUCCESS_DATA_KEYS` (`:148-179`) is an EXACT key-set pin checked by `test_specify_plan_tasks_success_data_key_shape_is_pinned` (`:617`). Your additive key reds it, so re-pin it in the same commit. `_TASKS_SUCCESS_DATA_KEYS` (`:181-204`) is re-pinned by WP02 as a sanctioned out-of-map edit; do not touch it.
  - Harness: `_init_repo` (`:218`, with a provisioned charter), `_run` (`:240`), `_envelope` (`:253`) and `_specify` (`:257`).
  - The fallback test is at `:550-576`.
- **`tests/specify_cli/cli/commands/agent/test_mission_setup_plan_phases.py`** (unit + fast, owned)
  - The spec-gate tests are at `:101-208`.
  - Four tests patch `seam._enforce_spec_gate` to `False` (`:394`, `:483`, `:545`, `:880`). Their spec may not sit at the resolved `spec_file`, so the warnings helper must tolerate an absent file.
  - No test pins an exact setup-plan payload key-set.
- **`spec-template.md`.** An HTML comment spans `:81-102`. `| FR-EXAMPLE |` is at `:101`, and `FR-###` / `NFR-###` / `C-###` at `:84`, both inside comments. Declared rows sit at `:108-126`, and `- **SC-00N**:` bullets at `:145-148`. There are no requirement tokens outside comments except those declarations.
- **Corpus (verified, read-only grep).** Exactly 4 specs hold kind-prefixed malformed tokens in declared positions:
  - `doctrine-enrichment-frontend-brownfield-normalization-01KQ48XA` (about 69 `| FR-00x.y |` rows);
  - `coord-read-residuals-merge-lanes-and-identity-routing-01KW2M8V` (`| C-EXCL-2167 |`, `| C-EXCL-FALLBACK |`);
  - `mission-type-drg-edges-01KXKY2N` (`| C-S1 |`, `| SC-S2 |`);
  - `doctrine-public-api-surface-01KZPDSR` (`| C-007-mission |` at `:202`).

  `FR-00N` appears in the corpus only in prose, never in a declared position.

### Out-of-map edits allowed in this WP (each with rationale)

- `tests/architectural/_interpreter_shard_roster.py`, shard 5 (next to `tests/specify_cli/test_requirement_mapping.py`, ~`:352`, sorted after WP01's `test_requirement_id_grammar.py`), and the matching shard-5 `run:` line in `.github/workflows/ci-nightly.yml` (~`:687`). Rationale: root-level `tests/specify_cli/test_*.py` files are enumerated one by one, so the new `test_requirement_id_lint.py` needs enrolling in both. Verify with `git diff`; do NOT run the shard-coverage gate.
- `docs/api/orchestrator-api.md:335-338`, the `plan` "Error codes" paragraph only. Rationale: it says a typed upstream code "is passed through verbatim". After T026 an unregistered code becomes `PLAN_SETUP_FAILED` with `data.reason`. Keep the `### plan` heading (`tests/docs/test_orchestrator_api_verb_doc_presence.py`).
- **Parallel-lane hunk (D4).** A parallel lane also edits `tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py` in a distant hunk (WP02 re-pins `_TASKS_SUCCESS_DATA_KEYS` at `:181-204`; you re-pin `_PLAN_SUCCESS_DATA_KEYS` at `:148-179`); keep your hunk minimal and do not reformat the file. The multi-dependency lane merge fails closed on a conflict.
- **Not allowed:** editing `src/specify_cli/requirement_mapping/__init__.py`. Import the lint directly from `specify_cli.requirement_mapping.lint`; a package re-export would collide with WP02/WP03's edits to that file.
- **Not allowed:** editing `grammar.py`. If `MALFORMED_DECLARED_LEAD`'s capture cannot support the pins below even after the string normalisation in T024, stop and escalate to the orchestrator. WP02–WP04 consume the grammar in parallel.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-2991-requirement-id-grammar`; completed changes merge back into `issue-2991-requirement-id-grammar`.
- **Planning base branch**: `issue-2991-requirement-id-grammar`
- **Merge target branch**: `issue-2991-requirement-id-grammar`

> These fields are populated automatically by `.venv/bin/spec-kitty agent mission finalize-tasks`. The execution worktree comes from `lanes.json` through `.venv/bin/spec-kitty agent action implement WP05 --agent claude`.

## Commit sequence (one concern per commit)

1. **ATDD acceptance tests** (T027 tests, written first). These are US4 AC1–AC4 plus the live-template case. They are RED on the WP01 base: AC1 proceeds instead of refusing, AC3 has no `requirement_id_warnings`, AC4 enveloped as success, and the lint import fails. AC2 is the positive control and is already green; say so in the commit body. Red-first is not required, because this is new behaviour and not a defect, so use no `regression` marker.
2. **T024**: `lint.py` plus `test_requirement_id_lint.py` (unit tests first, then the code), plus the shard enrolment.
3. **T025**: setup-plan wiring, the phases unit tests, and the `_PLAN_SUCCESS_DATA_KEYS` re-pin.
4. **T026**: the orchestrator `plan` remap, its helper tests, and the doc paragraph.
5. **T027**: validation evidence (Activity Log). Tracer notes and changelog notes go in the hand-off.

## Subtasks & Detailed Guidance

### Subtask T024 – `src/specify_cli/requirement_mapping/lint.py`

- **Purpose**: FR-013 detection and FR-014 warnings, as one pure function over spec text.
- **API** (give the module an `__all__` listing only names `mission_setup_plan.py` imports; `test_no_dead_symbols.py` fails an `__all__` member with no src caller):
  - `lint_spec_requirement_ids(spec_text: str) -> SpecLintResult`.
  - `SpecLintResult`: a frozen dataclass with `errors: tuple[InvalidRequirementId, ...]` and `warnings: tuple[RequirementIdWarning, ...]`, plus a `blocking` property (`bool(errors)`).
  - `InvalidRequirementId(token: str, line: int, rule: str)` and `RequirementIdWarning(token: str, line: int, message: str)`: frozen dataclasses, each with `as_dict() -> dict[str, object]` producing exactly the contract keys (`{token, line, rule}` / `{token, line, message}`). `line` is 1-based in the ORIGINAL `spec.md`.
- **Algorithm** (keep each helper ≤ 15 and test each one directly):
  1. `visible = grammar.blank_html_comments(spec_text)`. WP01's function replaces every `<!-- … -->` span (multi-line included; an unterminated `<!--` runs to end of text) with spaces and keeps the newlines, so line numbers and columns survive. Do not write a local blanking helper.
  2. `declared = set(parse_requirement_ids_from_spec_md(spec_text)["all"])`, the same declared set finalize and the runtime use. WP01's `_declared_ids` blanks comments with the same function, so the declared set already ignores commented-out declarations.
  3. Walk `visible.splitlines()` with `enumerate(…, start=1)`. For each line:
     - (a) **Error check.** If `MALFORMED_DECLARED_LEAD` (uppercase-kind only, case-sensitive; see `contracts/grammar.md`) matches, take the captured lead token (capture charset `[A-Za-z0-9_.-]+`, per `contracts/grammar.md`, analysis B6) and normalise it with string operations only: strip `*`/`~` wrappers and ONE trailing `.`, `:` or `,`. Then call `_is_well_formed_declaration(token)`, which is `canonical(token) is not None` and `find_all(token, spec_scan=True)` yielding exactly one unqualified ID whose `.canonical == canonical(token)`. If it is not well-formed, record an error and `continue` (no warnings from an error line, so `C-007-mission` is never double-reported as an error plus a `C-007` warning).
     - (b) **Declaration line.** If any `DECLARED_SHAPE_PATTERNS` matches, `continue`. This is the first-ID-per-line rule: citations in a table row's description cell never warn.
     - (c) **Prose.** For each `rid` in `find_all(line, spec_scan=True)`: skip `rid.is_foreign` (qualified citations never warn), skip `rid.canonical in declared`, and skip a canonical already warned. Otherwise record a warning at this line. That gives one warning per distinct token, at its first occurrence.
  4. **Rule text.**
     - The grammar rule is `grammar.RULE_TEXT` (`"<kind>-<digits>[<lowercase letter>]"`, exactly the contract example). Import it; never restate the string. Kinds are named in the refusal `error` text.
     - `RULE_LOWERCASE_SUFFIX` is a lint-local module constant (hoisted because it is used 3+ times in tests and code), used when `parse(token)` (case-tolerant) succeeds but the spec-scan check fails. That is the uppercase-suffix case, `FR-006A` → "write the letter suffix in lowercase (FR-006a); replace placeholders such as FR-00N with a real ID".
- **Placeholder decision (record it in your hand-off's `## Tracer notes`).** `FR-00N` in a declared position IS malformed and gets `RULE_LOWERCASE_SUFFIX`: case-tolerant `parse` accepts it, spec scanning does not. This is safe for the corpus, because `FR-00N` is prose-only there (R4) and the template keeps placeholders inside comments. In prose, `FR-00N` is never a warning, because spec scanning does not recognise it.
- **Relationship to `find_undeclared_requirement_citations` (FR-014: extend, do not duplicate).** Document this in the module docstring.
  - That function is the finalize/runtime scope-level signal. It fires only when a whole scope declares nothing, and it returns prose without line numbers, so its output cannot fill `{token, line, message}`.
  - The lint is its per-token, line-numbered extension for the planning hand-off. It is built on the SAME declared set (`parse_requirement_ids_from_spec_md`), the SAME declared shapes (`DECLARED_SHAPE_PATTERNS`) and the SAME comment blanking (`grammar.blank_html_comments`, which WP01's `_declared_ids` also applies), so the two can never disagree about what is declared. The lint re-implements none of the three.
  - Pin the extension with a containment test: on the "nothing declared" fixture where `find_undeclared_requirement_citations` fires, every token it names appears in the lint's warnings.
  - The message wording echoes its remediation: declare it in a recognised shape, or cite another mission's ID as `<mission-slug>#<ID>`.
- **Tests: `tests/specify_cli/test_requirement_id_lint.py`** (`pytestmark = [pytest.mark.unit, pytest.mark.fast]`). Every refusal is paired with a same-fixture positive control.
  - **Errors, one parametrised case each:** `| C-007-mission |`, `| FR-001.1 |`, `| C-S1 |`, `| FR_001 |` → `grammar.RULE_TEXT`; `| FR-006A |` → `RULE_LOWERCASE_SUFFIX`. Each case has a control line in the same text: `| C-007 |`, `| FR-001 |`, `| C-001 |`, `| FR-001 |`, `| FR-006a |` produce no error. Assert `token` and `line` exactly.
  - **All four declared positions** (table first cell, heading, bullet/numbered lead, bold lead) refuse `C-007-mission`, and each accepts `C-007` on the next line.
  - **No false positives from normalisation:** `### FR-001: Title`, `- FR-001. Do X`, `**FR-001 — Title.** body`, `| **FR-001** |`, `| ~~FR-006~~ |`, `- **SC-001**: …` and `| fr-001 |` all produce 0 errors.
  - **Uppercase-kind-only detection (B5; `contracts/grammar.md` "Malformed declared lead").** The malformed-lead check is case-sensitive over an uppercase kind (`FR`/`NFR`/`SC`/`C`, then `-` or `_`, then a digit or uppercase letter) and runs spec-wide over declared positions, not only inside requirement sections. Negative controls on declared-position lines, placed outside any requirements section, none of which may error: `- C-style strings`, `| C-suite |`, `- c-001 lowercase`. Same-fixture positive control: `| C-S1 |` in the same spec errors. **Lead-capture charset (analysis B6):** the lead capture is `[A-Za-z0-9_.-]+`. More negative controls in declared positions, none of which may error: `- **FR-009's** note`, `| FR-001/FR-002 |`, `| FR-002–FR-006 |` (en dash), `- **SC-001…004**:`. Each captures a well-formed ID. The T027 corpus smoke must refuse exactly the 4 known specs; if it refuses more, escalate rather than loosen.
  - **Placeholder:** `| FR-00N |` gives an error with `RULE_LOWERCASE_SUFFIX`, while prose `see FR-00N` gives 0 errors and 0 warnings.
  - **HTML comments.** A single-line and a multi-line comment holding `| C-007-mission |` give 0 errors. Positive control: the same text with the comment markers removed gives 1 error. A line after a multi-line comment reports its true line number.
  - **Live template** (`Path(__file__).resolve().parents[2] / "packs/built-in/missions/software-dev/templates/spec-template.md"`) gives 0 errors and 0 warnings. Positive control: the same text with `<!--`/`-->` removed yields an error for `FR-EXAMPLE`, which proves that comment skipping is what saves it. WP07 edits this template later, and this test is its guard.
  - **Warnings:**
    - Prose `see FR-099` with `FR-099` undeclared gives exactly one warning naming `FR-099` at its line.
    - `other-mission#FR-013` and `requirement-id-grammar-01M3NRCA#FR-013` in the same prose give none.
    - A declared `FR-001` cited in prose gives none.
    - `| FR-001 | … see FR-098 … |` gives no warning for `FR-098`, while `FR-098` bare in a prose line of the same spec gives one.
    - `IC-01` never errors or warns (C-004).
    - The C-009 half: warnings never set `blocking`.
  - **Containment test** against `find_undeclared_requirement_citations`, as described above.
  - **Agreement with the declared set:** a spec with `| FR-004 |` inside a comment gives 0 errors AND `FR-004` is absent from `parse_requirement_ids_from_spec_md(...)["all"]`; a prose `see FR-004` elsewhere in that spec then warns (it is undeclared for both).
  - **Helper tests:** `_is_well_formed_declaration` (`FR-001` / `fr-006a` / `SC-002b` true; `FR-006A` / `FR-008-mandated` false). `blank_html_comments` is tested by WP01.

### Subtask T025 – setup-plan wiring

- **Purpose**: FR-013 refusal (exit 1) and FR-014 warnings on `spec-kitty agent mission setup-plan`.
- **Refusal** (in `_evaluate_spec_gate`, at the pass point `:445-446`):
  - Replace `return None, None` with `return _evaluate_requirement_id_gate(spec_file, feature_dir, mission_slug)`.
  - That new pure helper reads `spec_file.read_text(encoding="utf-8")`, runs the lint, and returns `(None, None)` when there are no errors.
  - On errors it returns `SetupPlanLocalOutcome(payload, 1, "error")` plus a human message. Exit **1** is mandatory: the orchestrator `plan` classifies failures only inside `except typer.Exit` (`commands.py:2465-2475`), so an exit-0 block would be enveloped as success.
  - Payload: `{"result": "error", "phase_complete": False, "error_code": SPEC_REQUIREMENT_IDS_INVALID, "error": "spec.md declares requirement IDs that do not match the requirement-ID grammar", "invalid_requirement_ids": [e.as_dict() …]}`. Add the identity keys `SPEC_FILE_MISSING` carries (`mission_slug`, `mission_dir`, the `feature_dir` legacy alias, `spec_file`), plus a `remediation` list. The remediation names the kinds (FR, NFR, C, SC), the lowercase suffix, the `<mission-slug>#<ID>` citation form, and "commit spec.md and re-run setup-plan".
  - Hoist `SPEC_REQUIREMENT_IDS_INVALID = "SPEC_REQUIREMENT_IDS_INVALID"` and the `error` text to module constants next to `:83-86`.
  - `_enforce_spec_gate` is unchanged, because it already emits the JSON and raises `Exit(1)`.
- **Human output.** Follow the `SPEC_FILE_MISSING` style (`:428`): `[red]Error:[/red] <error>`, then one line per ID, `  - line N: <token> (rule: <rule>)`. Escape dynamic text with `rich.markup.escape`. `grammar.RULE_TEXT` contains `[<lowercase letter>]`, which rich would otherwise parse as markup. Pin this in a test.
- **Warnings** (additive key `requirement_id_warnings`):
  - Add `_spec_requirement_id_warnings(spec_file) -> list[dict[str, object]]`. It returns `[]` when `spec_file` is not a file (the spec gate owns existence, and the tests at `:394/:483/:545/:880` bypass the gate), and otherwise returns `lint(...).warnings` as dicts.
  - Call it in `setup_plan` right after the `_enforce_spec_gate` block (`:1099`), as a plain assignment, and pass it through `_emit_setup_plan_result(..., requirement_id_warnings=...)` to `_build_setup_plan_result`. Both gain a keyword `requirement_id_warnings: Sequence[Mapping[str, object]] = ()`, and the builder always sets `result["requirement_id_warnings"] = [dict(w) for w in …]`.
  - This adds NO branch to `setup_plan`, which stays at 11. Confirm with `.venv/bin/ruff check --select C901`.
- **"Every non-error payload" = every payload without an `error_code` key**, which means everything `_build_setup_plan_result` produces (success, scaffold, and the plan-not-substantive blocked result). The spec-gate `SPEC_NOT_SUBSTANTIVE_OR_UNCOMMITTED` payload carries an `error_code` and is emitted before the lint runs, so it does not carry the key. Record this in your hand-off's `## Tracer notes`.
- **Human warnings.** In `_emit_setup_plan_result`'s non-JSON branch, print one escaped `[yellow]Warning:[/yellow] line N: <token> — <message>` per warning before the `✓ Plan scaffolded` line.
- **Lint runs twice on the pass path** (once in the pure evaluator for errors, once for warnings). This is deliberate: it keeps `_evaluate_spec_gate`'s 2-tuple contract, which the tests at `:155-208` pin, and it keeps the refusal inside the pure evaluator, as plan.md/IC-05 specify. The cost is a linear scan of one file. Record it in your hand-off's `## Tracer notes`. Do not add caching.
- **Tests (`test_mission_setup_plan_phases.py`, unit/fast, no git):**
  - `_evaluate_requirement_id_gate`: a malformed spec gives exit 1, `render_kind == "error"`, the exact contract keys and a message containing the token. Same fixture corrected: `(None, None)`.
  - `_evaluate_spec_gate` with `is_committed` and `is_substantive` patched `True`: a malformed spec gives the error outcome. The existing `# real` test (`:136-152`) stays green unchanged as the positive control.
  - Human-message escaping: the rendered message contains the literal `[<lowercase letter>]`.
  - `_spec_requirement_id_warnings`: an absent file gives `[]`; a prose-token spec gives one dict.
  - `_build_setup_plan_result`: the key is present and `[]` by default, and carries the passed warnings.
  - The human emit prints the warning line.
- **Re-pin** `_PLAN_SUCCESS_DATA_KEYS` in `test_specify_plan_tasks_verbs.py:148-179`: add `"requirement_id_warnings"` with a one-line comment naming FR-014 / NFR-002 (additive). Do NOT touch `_TASKS_SUCCESS_DATA_KEYS`: WP02 re-pins it (sanctioned out-of-map edit).

### Subtask T026 – orchestrator-api `plan` keeps the envelope in contract

- **Purpose**: FR-015. The envelope is `PLAN_SETUP_FAILED` (registered), and the reason travels in `data`.
- **Steps**:
  1. Add `_PLAN_SETUP_FAILED_FALLBACK = "PLAN_SETUP_FAILED"`, with a `#:` comment in the style of `_DESTRUCTIVE_OP_REFUSED_FALLBACK` (`:436-449`).
  2. Add `_plan_contract_error(error_code: str, error_data: dict[str, Any]) -> tuple[str, dict[str, Any]]`. A registered code (`is_allowed_error_code("orchestrator_api", code)`) passes through unchanged. Otherwise it returns `(_PLAN_SETUP_FAILED_FALLBACK, {**error_data, "reason": error_code})`. The delegate payload stays verbatim (including its own `invalid_requirement_ids`), so `data.reason` is the one added key.
  3. In `plan`'s `except typer.Exit` (`:2465-2475`), pass `_classify_delegate_error`'s result through `_plan_contract_error` before `_fail`. Use the constant for `fallback_code=` at `:2471`.
  4. Keep the literal `_fail(cmd, "PLAN_SETUP_FAILED", …)` at `:2481-2486` as it is, so the static contract scan still sees the code. That leaves 2 literal occurrences, within S1192.
  5. Do NOT change `_classify_delegate_error`, because `tasks` and `specify` still use it unchanged.
  6. Update the module docstring (`:37-38`) and the doc paragraph (out-of-map edit) to say that an unregistered delegate code becomes `PLAN_SETUP_FAILED` with `data.reason`.
- **Scope note (record in your hand-off's `## Tracer notes` and the Activity Log).** The remap also closes, inside `plan` only, the pre-existing leaks of `SPEC_FILE_MISSING`, `TEMPLATE_CONFIGURATION_ERROR` and `PLAN_CONTEXT_UNRESOLVED`. The same leak remains in `tasks`/`specify` through the shared helper. That is a follow-up candidate; name it for closeout, and do not fix it here.
- **Tests** (in `test_specify_plan_tasks_verbs.py`; helper tests need no git and may use the module's harness-free path):
  - `_plan_contract_error("SPEC_REQUIREMENT_IDS_INVALID", {...})` gives `PLAN_SETUP_FAILED` and `reason`. Positive control: `_plan_contract_error("PLAN_SETUP_FAILED", data)` (a registered code) returns both unchanged, with no `reason` key.
  - `SPEC_FILE_MISSING` is remapped as well (this documents the latent-leak fix).
  - `is_allowed_error_code("orchestrator_api", commands._PLAN_SETUP_FAILED_FALLBACK)` is true.
  - The shared helper is unchanged: `_classify_delegate_error({"error_code": "SPEC_FILE_MISSING", "error": "x"}, "", fallback_code="TASKS_FINALIZE_FAILED", fallback_message="m")[0] == "SPEC_FILE_MISSING"`.
  - The existing `:550-576` fallback test stays green unchanged.

### Subtask T027 – Acceptance tests, validation and wrap-up

- **Acceptance tests** (commit 1; in `test_specify_plan_tasks_verbs.py`, reusing `_init_repo`/`_specify`/`_git`/`_run`/`_envelope`):
  - **Fixture.** `_specify` a mission. Write `_SUBSTANTIVE_SPEC` plus a `### Constraints` table row `| C-007-mission | Scoped constraint | Real description text. | Technical | High | Open |`, and a `## User Scenarios` prose line citing `FR-099` and `other-mission-01KAAAAA#FR-013`. Commit it.
  - **Host CLI.** Use `typer.testing.CliRunner().invoke(mission_app, ["setup-plan", "--mission", slug, "--json"], catch_exceptions=False)` under `contextlib.chdir(repo)`, with `from specify_cli.cli.commands.agent.mission import app as mission_app`. Parse the first `{`-line of the output as JSON.
  - **AC1.** The malformed spec gives `exit_code == 1`, `error_code == "SPEC_REQUIREMENT_IDS_INVALID"`, and an `invalid_requirement_ids` entry with token `C-007-mission`, the right `line`, and `rule`. `plan.md` was NOT created.
  - **AC2.** The same fixture with `C-007-mission` → `C-007`, recommitted, gives `exit_code == 0`, no `error_code`, and `plan.md` exists.
  - **AC3.** The AC2 run's payload `requirement_id_warnings` names `FR-099` with its line, and names nothing for the qualified citation. The run proceeded, which shows the warning does not refuse.
  - **AC4** (orchestrator `plan` on the AC1 fixture): `success is False`, `error_code == "PLAN_SETUP_FAILED"`, `is_allowed_error_code("orchestrator_api", envelope["error_code"])`, `data["reason"] == "SPEC_REQUIREMENT_IDS_INVALID"`, and `data["invalid_requirement_ids"]` is non-empty. Positive control: after the correction, `plan` gives `success is True` and `"requirement_id_warnings" in data`.
  - The live-template test is in `test_requirement_id_lint.py` (T024). Commit it with the acceptance tests.
- **Corpus smoke (read-only; informs WP08).** Run it from your worktree root:

  ```bash
  .venv/bin/python - <<'PY'
  from pathlib import Path
  from specify_cli.requirement_mapping.lint import lint_spec_requirement_ids
  hits = sorted(p.parent.name for p in Path("kitty-specs").glob("*/spec.md")
                if lint_spec_requirement_ids(p.read_text(encoding="utf-8")).errors)
  print(len(hits)); print("\n".join(hits))
  PY
  ```

  Expected: exactly the 4 specs under "Verified seam facts", and this mission's own spec is not among them. If the set differs, do NOT loosen the lint. Record the diff in the Activity Log and in your hand-off's `## Tracer notes`, and escalate.
- **Notes to record (Activity Log, for WP06, WP08 and closeout):**
  - The 4 corpus specs would now be refused on a re-plan (NFR-001(b), expected).
  - `CONTRACT_VERSION` (`orchestrator_api/envelope.py`, 1.7.0) is NOT bumped here. WP06 bumps it once, to 1.8.0, covering WP02's finalize keys, this WP's `requirement_id_warnings` and the `plan` remap.
- **Changelog notes (NFR-002).** `docs/changelog/CHANGELOG.md` is written by the orchestrator at closeout; this WP does not edit it. Put one-liners in a `## Changelog notes` section of your hand-off: `setup-plan` refuses a malformed declared ID with `SPEC_REQUIREMENT_IDS_INVALID` (exit 1); the additive `requirement_id_warnings` key; the orchestrator-api `plan` envelope now reports previously leaked unregistered codes as `PLAN_SETUP_FAILED` with `data.reason`.
- **Tracer notes** (1–3 sentences each, dated `- 2026-09-29: …`, in the `## Tracer notes` section of your hand-off):
  - design decisions: the placeholder treatment, the non-error-payload definition, the double lint, warning dedupe, the scope of the `plan` remap and the `SPEC_FILE_MISSING` follow-up;
  - approach: the commit sequence as landed;
  - tooling friction: anything that fought you (for example the `MALFORMED_DECLARED_LEAD` capture contract).

## Validation surface

**Test files** (run all of them together):

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q \
  tests/specify_cli/test_requirement_id_lint.py \
  tests/specify_cli/cli/commands/agent/test_mission_setup_plan_phases.py \
  tests/specify_cli/cli/commands/agent/test_setup_plan_read_surface.py \
  tests/specify_cli/cli/commands/agent/test_mission_planning_entry.py \
  tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py \
  tests/contract/test_orchestrator_api.py \
  tests/docs/test_orchestrator_api_verb_doc_presence.py
```

`test_setup_plan_read_surface.py` and `test_mission_planning_entry.py` are not yours. They must stay green unmodified.

**Smoke (unmodified; they exercise touched code; report breaks, do not edit):**

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q \
  tests/specify_cli/orchestrator_api/test_typed_error_fail_closed.py \
  tests/specify_cli/cli/commands/agent/test_mission_cli_golden_contract.py \
  tests/specify_cli/test_requirement_id_grammar.py
```

**Named architectural gates (by file, never the directory):**

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q \
  tests/architectural/test_requirement_id_grammar_single_source.py \
  tests/architectural/test_no_dead_symbols.py \
  tests/architectural/test_no_dead_modules.py
```

- `test_no_dead_symbols.py`: `MALFORMED_DECLARED_LEAD` gains its first real consumer here.
- `test_no_dead_modules.py`: added by the planner, because `lint.py` is a new module.
- `test_requirement_id_grammar_single_source.py`: `lint.py` must contribute no site.

**Owning module fast tier (baseline):** `make test-fast`.

**Static checks** (on the touched files; zero findings, no new `noqa` / `type: ignore`):

```bash
.venv/bin/ruff check src/specify_cli/requirement_mapping/lint.py src/specify_cli/cli/commands/agent/mission_setup_plan.py src/specify_cli/orchestrator_api/commands.py tests/specify_cli/test_requirement_id_lint.py tests/specify_cli/cli/commands/agent/test_mission_setup_plan_phases.py tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py
.venv/bin/ruff format --check src/specify_cli/requirement_mapping/lint.py src/specify_cli/cli/commands/agent/mission_setup_plan.py src/specify_cli/orchestrator_api/commands.py tests/specify_cli/test_requirement_id_lint.py tests/specify_cli/cli/commands/agent/test_mission_setup_plan_phases.py tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py
.venv/bin/ruff check --select C901 src/specify_cli/cli/commands/agent/mission_setup_plan.py src/specify_cli/orchestrator_api/commands.py src/specify_cli/requirement_mapping/lint.py
.venv/bin/mypy --strict src/specify_cli/requirement_mapping/lint.py src/specify_cli/cli/commands/agent/mission_setup_plan.py src/specify_cli/orchestrator_api/commands.py
```

If `mypy --strict` reports findings in `commands.py` that also appear on the planning base, they are not yours. Record them and do not fix them. Zero NEW findings is the bar.

Record every command with its passed/failed/skipped counts in the Activity Log. Classify any red with the CLAUDE.md baseline-red procedure: re-run on the planning base with `PYTHONPATH=<worktree>/src`. Only a red that is new on your branch is yours.

## Risks & Mitigations

- **An exit-0 block is enveloped as success.** The refusal MUST exit 1, and AC4 proves it end to end.
- **The template comment row.** `| FR-EXAMPLE |` sits at `spec-template.md:101`. Comment blanking has a live-template test with an unwrapped-comment positive control. WP07 must keep that test green when it edits the template.
- **The 4 corpus specs** will be refused on a re-plan. This is expected (NFR-001(b)); the T027 smoke confirms the exact set, and WP08 owns the committed scan.
- **Warnings noise.**
  - Qualified citations are skipped through `is_foreign`.
  - Declaration lines are skipped whole (first-ID-per-line), so description-cell citations never warn.
  - Error lines do not also warn.
  - There is one warning per distinct token.
- **Normalisation false positives** (`### FR-001: Title`, `- FR-001. Do X`) are pinned by the no-false-positive tests. Any failure there that string normalisation cannot fix is an escalation, not a `grammar.py` edit.
- **Rich markup** eats `[<lowercase letter>]`. Escape the text and pin it with a test.
- **Additive key breaks exact pins.** `_PLAN_SUCCESS_DATA_KEYS` is re-pinned here. `_TASKS_SUCCESS_DATA_KEYS` is re-pinned by WP02. There is no other exact setup-plan key-set pin (verified).
- **Tests that bypass the gate.** The warnings helper tolerates an absent `spec_file`, so the four patched tests stay green unchanged.
- **Contract drift.** `SPEC_REQUIREMENT_IDS_INVALID` must never become a `_fail` literal, and `upstream_contract.json` is not edited.

## Review Guidance

- **Exit code 1** on refusal, both through the host CLI (AC1) and through the orchestrator (AC4).
- **The envelope code is registered.** AC4 asserts `is_allowed_error_code`, `data.reason` is present, and `_classify_delegate_error` is byte-unchanged (diff check plus the shared-helper test).
- **The template passes the lint**, and the paired unwrapped-comment control fails.
- **Positive controls are present** for every refusal and absence assertion: AC2, the per-case control lines, the registered-code pass-through, and the qualified-citation versus bare-token pair.
- **`setup_plan` complexity stays at 11**, and every new function is at ≤ 15 (`.venv/bin/ruff check --select C901` output in the Activity Log).
- **C-001.** `lint.py` has no ID regex literal and no `FR|NFR` string. `grep -nE 'FR\|NFR|FR-\\d' src/specify_cli/requirement_mapping/lint.py` returns nothing.
- **C-009.** No warning ever blocks, and the bare-prose predicate is untouched.
- **Additive only (NFR-002).** Every pre-existing setup-plan and `plan` key is unchanged, and `requirement_id_warnings` is the only new success key.
- **The Activity Log** carries the commands and counts, the corpus-smoke result and the closeout notes; the hand-off carries the `## Changelog notes` and `## Tracer notes` sections.

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

- 2026-09-29T06:28:45Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `.venv/bin/spec-kitty agent tasks move-task WP05 --to <status>` to change WP status.
