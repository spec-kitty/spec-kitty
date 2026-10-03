---
work_package_id: WP06
title: 'Content checks: citation, provisional, example, event mapping, enum pin, leak scan (IC-05)'
dependencies:
- WP05
requirement_refs:
- FR-007
- FR-008
- FR-010
- FR-011
- FR-012
- FR-013
- FR-021
- FR-025
- NFR-004
- C-006
- C-010
- SC-004
- SC-005
planning_base_branch: issue-5558-mission-status-contract-v1
merge_target_branch: issue-5558-mission-status-contract-v1
branch_strategy: Planning artifacts for this mission were generated on issue-5558-mission-status-contract-v1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5558-mission-status-contract-v1 unless the human explicitly redirects the landing branch.
subtasks:
- T034
- T035
- T036
- T037
- T038
- T039
- T040
- T041
history: []
agent_profile: python-pedro
authoritative_surface: contracts/tools/
create_intent:
- contracts/tools/citation_check.py
- contracts/tools/provisional_check.py
- contracts/tools/example_check.py
- contracts/tools/event_mapping_check.py
- contracts/tools/enum_pin_check.py
- contracts/tools/enum_pins.json
- contracts/tools/leak_scan.py
- contracts/tools/fixture_builder.py
- tests/contract/test_citation_check.py
- tests/contract/test_provisional_check.py
- tests/contract/test_example_check.py
- tests/contract/test_event_mapping_check.py
- tests/contract/test_enum_pin_check.py
- tests/contract/test_leak_scan.py
- tests/contract/test_fixture_builder.py
execution_mode: code_change
model: sonnet
owned_files:
- contracts/tools/citation_check.py
- contracts/tools/provisional_check.py
- contracts/tools/example_check.py
- contracts/tools/event_mapping_check.py
- contracts/tools/enum_pin_check.py
- contracts/tools/enum_pins.json
- contracts/tools/leak_scan.py
- contracts/tools/fixture_builder.py
- contracts/tools/fixtures/citation_check/**
- contracts/tools/fixtures/provisional_check/**
- contracts/tools/fixtures/example_check/**
- contracts/tools/fixtures/event_mapping_check/**
- contracts/tools/fixtures/enum_pin_check/**
- contracts/tools/fixtures/leak_scan/**
- tests/contract/test_citation_check.py
- tests/contract/test_provisional_check.py
- tests/contract/test_example_check.py
- tests/contract/test_event_mapping_check.py
- tests/contract/test_enum_pin_check.py
- tests/contract/test_leak_scan.py
- tests/contract/test_fixture_builder.py
- tests/architectural/test_ci_corpus_trigger_completeness.py
role: implementer
tags: []
tracker_refs: []
---

# WP06 - Content checks: citation, provisional, example, event mapping, enum pin, leak scan (IC-05)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Implement the six Python content checks that guard the contract, plus the run-time leak-fixture builder, each with a planted-violation fixture, a clean control on the same root, stable message codes and a floor on inputs, all reading the contract through the single resolver.

## Context

- Plan concern **IC-05**. Follows WP05 in the single code lane (WP01 supplies the resolver, leak patterns and schema formats; WP02 is the IC-07a spike). **Precondition (verify read-only, stop and report if absent):** the dated sentence "IC-07a complete" is in `research.md` R-3 on the target branch (`git show <target-branch>:kitty-specs/mission-status-contract-v1-01M3WC5X/research.md`): no content check is built on a resolver tree the bundler later contradicts. A fixture that contains a brace-named `$ref` uses the **recorded** spelling (read `BRACE_REF_SPELLING` from `contract_resolver.py`; never hard-code).
- The plan allowed IC-05 to run in a parallel lane; here it runs after WP05 (see the lane model in WP01), so its checks go green on the real contract as they are written. Scopes stay one fixtures subdirectory per script and one `tests/contract/test_<script>.py` per script.
- Shared-file rule: this WP owns `tests/architectural/test_ci_corpus_trigger_completeness.py` for one purpose: append one sorted row per new corpus-marked module (seven here) and re-run that test.
- Does not touch the migration chain, runtime-state schema, event contract implementation or any shared CI gate other than the registry rows.
- **Conventions (binding, `contracts/tools-and-workflows.md`)**: run as `python contracts/tools/<name>.py [options]`; stdlib plus locked dependencies (PyYAML, jsonschema with `referencing`); import only sibling modules by name; never import pytest, `tests/` or `scripts.`; exit 0 pass, 1 violation, 2 cannot do its job; failures `CONTRACT-CHECK <name>: <CODE>: <detail>`; final `counts:` line on pass and fail; `--root` (default `contracts`); every check asserts a minimum input count before checking properties (FR-025).
- **Codes and counts**:
  - `citation_check.py`: `MISSING_CITATION`, `BAD_DERIVED_FORM`, `EMPTY_RULE`, `EMPTY_INPUTS`, `UNRESOLVED_INPUT`, `CITED_PATH_MISSING`, `CITED_SYMBOL_UNRESOLVED`, `COUNT_MISMATCH`, `CITATION_REUSE` (reported, more than five properties sharing one citation); counts `properties x_source x_derived inputs_resolved`; exit 2 `ZERO_PROPERTIES`, `ZERO_CITATIONS`.
  - `provisional_check.py`: `MISSING_MARKER` (staleness or next action without `x-provisional`), `UNDESCRIBED_MARKER` (marker without a description naming the open decision), `NOT_NULLABLE`; count `provisional_elements`; exit 2 `ZERO_PROVISIONAL`.
  - `example_check.py`: `EXAMPLE_INVALID` (including a malformed `date-time` via `schema_formats.FORMAT_CHECKER`), `ORPHAN_EXAMPLE`, `EXAMPLE_VALIDATES_NOTHING`, `REQUIRED_EXAMPLE_MISSING` against a committed required-example manifest (one per resource, one per event kind, a populated provisional example, a discarded-Mission example, first/middle/last page-cursor cases); counts `examples validated`; exit 2 `ZERO_EXAMPLES`.
  - `event_mapping_check.py`: `NAME_WITHOUT_SCHEMA`, `SCHEMA_WITHOUT_NAME`, `SCHEMA_MULTI_NAME`, plus the informational (never failing) line `LIFECYCLE_TYPE_NOT_FORWARDED` for each member of `LIFECYCLE_EVENT_TYPES` outside the contract-owned seven-type allow-list; counts `event_names event_schemas lifecycle_not_forwarded`; exit 2 `ZERO_EVENT_NAMES`.
  - `enum_pin_check.py`: `ENUM_VALUE_ADDED`, `ENUM_VALUE_REMOVED`, `BOARD_GROUPING_PRESENT`; counts `enums values`; exit 2 `PIN_EMPTY`, `ENUM_UNREADABLE`.
  - `leak_scan.py`: `FORBIDDEN_PROPERTY_NAME` (parsed YAML and JSON keys only), `HOST_PATH`, `EMAIL`, `PLANTED_NOT_DETECTED`; counts `files values_strict values_human values_all`; exit 2 `ZERO_FILES`, `ZERO_VALUES_IN_CLASS`.
- **Citation resolution (FR-010, PQ-10)**: by defined name, not text match. In a `.py` file the symbol must be a `def`, a `class`, or an assignment target (module or class level) found by parsing the syntax tree, **including annotated class-level targets without a value** (`x: int`), because the stream cursor's `invariant` is the bare annotated attribute `content_invariant` of `TailCursor`; a name that appears only in a comment, a string or as a substring of another name does not resolve. In a YAML or JSON file the symbol is a key path that must exist. Line numbers optional and unchecked. Traversal covers every property at any depth (nested objects, array `items`, `allOf`/`oneOf`/`anyOf` branches, `additionalProperties` value schemas, properties reached only through `$ref`); computes the total itself and fails unless the `x-source` and `x-derived` counts sum to it and the total is above zero. `x-derived` is the structured form `{rule, inputs}`; each input is a code citation or a contract-field property path that must exist.
- **D-P11 leak fixtures are built at run time, not committed.** `fixture_builder.py` assembles each leak-class planted fixture (host path, e-mail, forbidden property name, absolute path in a human-text field) from string fragments into a temporary root (`build(kind, out_dir)`, CLI `--out <dir>`); only clean controls are committed. `leak_scan` has no exempt directory and no exempt marker line. Self-reference control: a unit test runs `leak_scan` over the real `contracts/tools` tree, expects zero findings and asserts a floor on files scanned (at least the number of `.py` files found by globbing). `leak_patterns.py` and `fixture_builder.py` write their patterns from fragments so they do not match their own rules. Committed non-leak plants may sit under `contracts/tools/fixtures/` because they contain nothing leak-shaped.
- **Python hygiene and S-rules (binding for this WP)**: run `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .` before the final commit and record both results (NFR-007). `contracts/tools/*.py` are non-test code, so ruff's bandit rules (`S`) apply there in full: shell out only with argument lists and `shutil.which`-resolved binaries (S603, S607), call `urlopen` only after an explicit `https` scheme check (S310), and make any suppression a one-line `# noqa: S###` with a stated rationale, never a blanket one. Run `mypy --strict` locally over new modules as discipline (no CI job). In `tests/`, never import `datetime` and never call `datetime.now()` or `time.time()` (clock-ban gates, named below): compare ISO-8601 strings or use the kernel clock door.
- Public repository (C-006): nothing in this WP's files holds a literal absolute host path, e-mail address, credential or private-discussion reference.
- Baseline: WP01's hand-off (recorded in `research.md` R-8); overlap check 2026-10-02: #5540 and #5326 touch none of this WP's files.
- Red-first (C-010): first commit per script is its failing unit test and planted fixtures; reviewers verify red then green.

### Test surface, gates and baseline

- Targeted: `tests/contract/test_citation_check.py tests/contract/test_provisional_check.py tests/contract/test_example_check.py tests/contract/test_event_mapping_check.py tests/contract/test_enum_pin_check.py tests/contract/test_leak_scan.py tests/contract/test_fixture_builder.py tests/contract/test_leak_patterns.py tests/contract/test_schema_formats.py`.
- Named gates: `tests/architectural/test_clock_import_ban.py tests/architectural/test_clock_call_ban.py` and `tests/architectural/test_ci_corpus_trigger_completeness.py`. Also `ruff check .`, `ruff format --check .`; local `mypy --strict` over new modules as discipline.
- Each unit-test module carries the single-line marker `pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]` (a multi-line list is not detected by the registry gate).

## Subtasks

### Subtask T034: `fixture_builder.py` and its tests

**Purpose**: foundation for leak-class plants.

**Steps**: failing tests first (each `kind` builds a root containing exactly the planted value; no literal leak-shaped string in the source of the module or its test); implement `build(kind, out_dir)` and the CLI.
**Files**: `fixture_builder.py` (~150 lines), test (~120 lines).
**Validation**: a text scan of both files by `leak_patterns` finds nothing.

### Subtask T035: `citation_check.py` (largest script)

**Purpose**: FR-010.

**Steps**: planted cases (each with a clean control) under `fixtures/citation_check/`: nested property without a citation; a symbol present only in a comment or string; free-text `x-derived`; empty `rule`; empty or missing `inputs`; input naming a missing symbol; input naming a missing contract field; cited path missing; counts that do not sum; reuse above five reported. Annotated-target positive case (the `content_invariant` shape). Implement the AST resolution and traversal; print the counts and the reuse report.
**Files**: ~350 lines plus tests (~300 lines).
**Validation**: all cases give the stable code; zero properties exits 2.

### Subtask T036: `provisional_check.py`

**Purpose**: FR-011.
**Steps**: planted: staleness or next action without the marker; marker without a description naming the open decision; provisional field not nullable; clean control with a populated example validating.
**Files**: ~120 lines plus tests.
**Validation**: codes asserted; `ZERO_PROVISIONAL` exits 2.

### Subtask T037: `example_check.py` and the required-example manifest

**Purpose**: FR-013.
**Steps**: planted invalid example, orphan example, example that validates nothing, missing required example (a contract with no discarded-Mission example must fail), malformed `date-time` through `FORMAT_CHECKER` and an extra property; commit the required-example manifest next to the fixtures and a pointer so WP09 and WP10 can reuse; use the resolver for schema lookup.
**Files**: ~220 lines plus tests and manifest.
**Validation**: codes asserted; floor on examples.

### Subtask T038: `event_mapping_check.py`

**Purpose**: FR-007 mapping consistency.
**Steps**: planted: a name with no schema; a schema with no name; a schema referenced by two names; zero names. Parse the mapping list in `events.yaml`'s description (the format WP05 wrote; read the real file first and match it); print `LIFECYCLE_EVENT_TYPES` minus the allow-list as informational lines (import the module constant by reading `src/specify_cli/status/lifecycle_events.py` as text via AST, not by importing `specify_cli`, to keep the tool dependency-light; confirm the twelve-member set).
**Files**: ~150 lines plus tests.
**Validation**: informational lines never change the exit status.

### Subtask T039: `enum_pin_check.py`

**Purpose**: FR-008.
**Steps**: commit the real pin file `contracts/tools/enum_pins.json` (a non-fixture file next to the script, owned by this WP) with the pinned lists for `StatusLane` (nine), `LifecycleStatus` (five), `Topology` (five); make its path the **default** of `enum_pin_check.py` (`--pins` overrides it for fixtures only); planted add and remove; `BOARD_GROUPING_PRESENT` when a `columns` or board grouping schema appears; empty pin and unreadable enum exit 2.
**Files**: `contracts/tools/enum_pin_check.py` (~110 lines), `contracts/tools/enum_pins.json` (the real pin, default path of the script; WP09 asserts the CI invocation uses this default with a non-empty pin), tests, and planted pins under `contracts/tools/fixtures/enum_pin_check/**`.
**Validation**: codes asserted.

### Subtask T040: `leak_scan.py`

**Purpose**: FR-012 text-level and structured scan.
**Steps**: planted values of each kind in each field class, built by `fixture_builder` at run time; same-fixture positive controls; the two real pass controls (`~/.kittify Runtime Centralization`, `/tmp burn-down: sync`); floors per class; the self-reference test over the real `contracts/tools` tree; scan covers every file under `contracts/` (descriptions, `x-source`/`x-derived` strings, README, CHANGELOG, examples including `promptMarkdown`), and no directory is exempt.
**Files**: ~220 lines plus tests.
**Validation**: planted not detected yields `PLANTED_NOT_DETECTED`; zero values in a class exits 2.

### Subtask T041: Registry rows, runs and hand-off

**Purpose**: keep gates green; record evidence.
**Steps**: append the seven sorted registry rows; run targeted tests and the gate; run each script by hand against its clean control and its plants and record the exit codes and codes; list the real-contract results for WP09 (`citation_check`, `provisional_check`, `example_check`, `event_mapping_check`, `enum_pin_check`, `leak_scan` against `contracts/` once WP05 is merged: record exit codes, or "not yet runnable" with the reason).
**Files**: `tests/architectural/test_ci_corpus_trigger_completeness.py` (+7 rows).
**Validation**: green; counts recorded.

## Definition of Done

- Seven modules with unit tests, each with planted violations and clean control, stable codes asserted, input floors asserted; red first.
- `leak_scan` self-reference test passes with a floor; no literal leak-shaped string committed anywhere in this WP's files.
- Registry rows appended in sorted order; completeness gate green.
- `ruff check .` and `ruff format --check .` clean; no S603, S607 or S310 finding left unjustified; the two clock-ban gate files green; no import of pytest, `tests/` or `scripts.` from `contracts/tools/`.
- Per-subtask completion recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Risks

- Citation check rejects the spec's own cursor citation unless annotated targets count (PQ-10): covered by T035 (the annotated-target positive case).
- A leak pattern literal sneaking into a fixture or test: assemble from fragments.
- Matching the event mapping format of `events.yaml` before it is stable: read the merged file, adapt the parser, keep the check strict.

## Reviewer Guidance

Verify each failure is asserted by code, not just by exit status; that every check fails on zero inputs; that no leak-class plant is committed; that the AST resolution rejects comment-only and substring symbols; and that the clean control shares the planted fixture's root. Check red first by reading the first commit of each script.

Implementation command: `spec-kitty agent action implement WP06 --agent claude`
