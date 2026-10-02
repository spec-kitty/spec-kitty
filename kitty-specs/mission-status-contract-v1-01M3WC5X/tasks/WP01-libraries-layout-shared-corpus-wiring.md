---
work_package_id: WP01
title: Baseline, libraries, layout check, shared pieces and corpus wiring (IC-01)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-012
- FR-013
- FR-019
- FR-020
- FR-021
- FR-025
- NFR-001
- NFR-005
- NFR-007
- C-003
- C-004
- C-009
- C-010
- SC-007
- SC-008
planning_base_branch: issue-5558-mission-status-contract-v1
merge_target_branch: issue-5558-mission-status-contract-v1
branch_strategy: Planning artifacts for this mission were generated on issue-5558-mission-status-contract-v1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5558-mission-status-contract-v1 unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
history: []
agent_profile: python-pedro
authoritative_surface: contracts/tools/
create_intent:
- contracts/README.md
- contracts/tools/contract_resolver.py
- contracts/tools/leak_patterns.py
- contracts/tools/schema_formats.py
- contracts/tools/layout_check.py
- tests/ci/test_contracts_routing.py
- tests/contract/test_contract_resolver.py
- tests/contract/test_leak_patterns.py
- tests/contract/test_schema_formats.py
- tests/contract/test_layout_check.py
execution_mode: code_change
model: sonnet
owned_files:
- contracts/README.md
- contracts/_shared/**
- contracts/tools/contract_resolver.py
- contracts/tools/leak_patterns.py
- contracts/tools/schema_formats.py
- contracts/tools/layout_check.py
- contracts/tools/fixtures/contract_resolver/**
- contracts/tools/fixtures/layout_check/**
- .github/workflows/ci-router.yml
- tests/ci/test_fleet_verdict.py
- tests/ci/test_contracts_routing.py
- tests/release/pinning_rule_inventory.json
- tests/release/ci_retirement_scrub.json
- tests/contract/test_contract_resolver.py
- tests/contract/test_leak_patterns.py
- tests/contract/test_schema_formats.py
- tests/contract/test_layout_check.py
- tests/architectural/test_ci_corpus_trigger_completeness.py
role: implementer
tags: []
tracker_refs: []
---

# WP01 - Baseline, libraries, layout check, shared pieces and corpus wiring (IC-01)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Take the Mission baseline before any functional change, then land the single resolution authority, the shared leak-pattern and date-time-format libraries, the layout check, the `contracts/_shared/` pieces, a README skeleton, and the corpus wiring (one router glob, one scrub-copy root, the first registry rows, the routing pin test), with the derived pinning inventory regenerated.

## Context

- Plan concern **IC-01** (baseline, tidy-first, libraries, shared pieces, corpus wiring), as one WP. **Why not split (recorded per the tasks rule on merging or splitting concerns):** the baseline record belongs in `research.md` (`kitty-specs/`), which a `code_change` WP may not own, and a separate `planning_artifact` baseline WP was tried and rejected: spec-kitty places every planning WP in one planning lane and `finalize-tasks` rejects a lane graph in which that lane is both upstream and downstream of a code lane (`LANE_DEPENDENCY_CYCLE`, observed with `--validate-only`). The baseline is therefore measured here, and the **orchestrator** writes it to `research.md` (record step at the end of this WP); the only planning WP (WP12) is last and consolidates every record.
- **Lane model for the whole Mission (read once).** The lane computer unions every code WP whose `owned_files` overlap, even when the WPs are dependency-ordered, and rejects a back-and-forth lane graph. The chokepoint files below (resolver, `contracts.yml`, root map, README, registry file, pinning inventory) are shared write scopes of most code WPs, so all eleven code WPs (WP01 to WP11) land in **one lane and run strictly in dependency order**: the plan's potential parallel lanes for IC-05, IC-06 and IC-07b are not realised. This is the plan's "sequenced" treatment of its chokepoints taken to its conclusion, not a scope change; the order is IC-01, IC-07a, IC-02, IC-03, IC-04, IC-05, IC-06, IC-07b, IC-08, IC-09, IC-10. Putting IC-07a immediately after IC-01 keeps the plan's intent (the CI-only spike runs as early as possible) and lets IC-03 use the spike's recorded brace spelling, so the conditional re-sweep in WP09 is then expected not to be needed. **Cost of serialising IC-07a:** every contract file now waits on an orchestrator-written record that needs several pushed CI runs, so a stalled spike would hold p0 hostage; WP02's time-box and fallback (provisional default spelling, re-sweep by WP09) bound that cost. **CLI notes:** `predicted_surfaces` in `lanes.json` is a CLI heuristic that does not describe this Mission (contracts and CI) and is noise; WP09 (dependencies WP05 to WP08) and WP10 (WP06, WP09) carry transitively redundant dependency edges, kept as authored documentation of what each WP really needs; the chain WP01 to WP11 is strict either way.
- **PR shape (read before dispatching; the decision belongs to the orchestrator and operator).** The Mission is delivered as one draft PR (C-001, CL-1). Size verdict: about 10,000 or more added lines across five kinds of artefact (about 25 `contracts/tools/` scripts and libraries with fixtures, about 22 unit-test modules, two workflow files, about 40 contract YAML files, a reality-check helper with a pinned fixture, and docs), which is **not readable in a sitting as one diff**. Recommendation: keep the single draft PR but state in its body that review is intended per work package in dependency order (the WP list is the table of contents), and consider a split into stacked or sequential PRs on these six seams: (1) WP01 and WP02 (baseline, libraries, routing, shared pieces, workflow skeleton and spike); (2) WP03 to WP05 (contract content, ending at p0, the UI early-start unit); (3) WP06 and WP07 (Python checks and hygiene); (4) WP08 and WP09 (JVM and Go tooling, workflows, release; the highest-risk review); (5) WP10 (reality check); (6) WP11 and WP12 (docs and records). A split is cheapest to decide before WP03 starts, because it changes where the branch is cut and which PR the WP02 orchestrator pre-step opens. `tasks.md` is generated by the CLI (`finalize-tasks`, from `wps.yaml`) and cannot carry this paragraph, which is why it sits here, in the first prompt an orchestrator opens; the full text is repeated in WP12.
- **Orchestrator pre-step (not an agent action).** Re-syncing onto current `main` (rebase, then the compact-history step of the mission wrap-up sequence) rewrites history. The agent running this WP does not rebase, reset, merge or switch branches; the orchestrator performs the re-sync before dispatch and tells the agent the base commit. If it has not been done, record that and stop.
- **Orchestrator action on any pre-existing red.** The agent never opens issues, pull requests or comments. For each red binned pre-existing, the agent records command, failure summary and why it is believed pre-existing; the orchestrator opens the tracker issue (Pre-existing Failure Reporting Rule, C-009).
- Everything else imports from this WP: `contract_resolver.py` is the **resolver chokepoint** (D-P1: one authority, imported by file path by every check, the parity script and the reality check).
- **Shared-CI chokepoints touched here**: `.github/workflows/ci-router.yml` (exactly one added line, `- 'contracts/**'`, in the `corpus` filter group; every existing glob untouched, C-003), `tests/release/pinning_rule_inventory.json` (derived, hidden byte-for-byte gate, tracer F-5), `tests/release/ci_retirement_scrub.json` (hand edit, documentation copy only). The corpus-registry file `tests/architectural/test_ci_corpus_trigger_completeness.py` is a declared append-only shared file (plan "Branch contract" exception 1); every WP that adds a corpus-marked module owns it for that purpose, which is what puts those WPs in one lane. This WP appends rows for the corpus-marked modules it adds, in sorted order, and edits nothing else in that file (`_CORPUS_GLOBS` and `_CORPUS_DATA_ROOTS` stay untouched).
- **Does not touch the migration chain, runtime-state schema or event contract** (no `src/` change, C-002).
- Binding decisions: D-P1, D-P2 (resolver change control: the supported-construct list is one constant; unlisted forms are refused with a stable code), D-P3 (message codes `CONTRACT-CHECK <name>: <CODE>: <detail>`, final `counts:` line, exit 0/1/2), D-P11 (leak patterns written from fragments), D-P14 (`FORMAT_CHECKER = FormatChecker(formats=())` with only `date-time` registered). Full script and code table: `kitty-specs/mission-status-contract-v1-01M3WC5X/contracts/tools-and-workflows.md`.
- `BRACE_REF_SPELLING` is a single constant in `contract_resolver.py`. Its value is provisional (default candidate: percent-encoded braces `%7B` and `%7D`) until the IC-07a spike (WP02) decides and the orchestrator records it; `layout_check.py` imports it and is parametric on it. **Rule BRACE-1 (stated once here; WP02, WP04 and WP09 refer to it, none restates it).** The constant is a 2-tuple of strings `(open, close)`, defined only in `contract_resolver.py`. **Python code** (production scripts and every test module) never contains a literal of either piece or a raw brace path-file name: it imports or derives them from the constant and from a directory listing. **Fixtures are data** (golden trees, planted violations, the IC-07a spike inputs and candidate spellings, resolver-parity and bundle inputs, the contract tree itself) and may hold literal spellings, because a fixture is exactly where a spelling is exercised; they are verified by running them through the tools, not by a text grep, and the only fixture literals the DoD requires are the clean-control file in `layout_check/` and, from WP04, a golden-tree file in `contract_resolver/` (see DoD). Enforcement is the executable single-source test below plus a production-code grep scoped to Python outside fixtures (DoD).
- Baseline: taken in T001 and T002 of this WP, before the first change. A red outside the files you changed is classed against it before you touch it; a pre-existing red is reported, never fixed here (C-009).
- **Open-PR overlap check (2026-10-02)**: open PRs #5540 and #5326 touch none of this WP's files (`ci-router.yml`, `tests/ci/`, `tests/release/`, `contracts/`); #5557 is closed unmerged. Re-run `gh pr list --repo spec-kitty/spec-kitty --state open --json number,files` at start and record any change.
- **Red-first (charter, C-010)**: the first commit of each deliverable is a failing unit test or planted fixture, red on the base; the final commit is green. Every changed behaviour has a test that fails when it is reverted.
- Terminology: Mission, never feature; status lane is not code lane or repo-root lane; `src/specify_cli/contracts/` (CLI shared-contract registry) is unrelated to the top-level `contracts/` tree, and the README says so in one line.

### Test surface, gates and baseline

- Targeted: `tests/contract/test_contract_resolver.py tests/contract/test_leak_patterns.py tests/contract/test_schema_formats.py tests/contract/test_layout_check.py tests/ci/test_contracts_routing.py`.
- Named gate files (no directory sweep): `tests/architectural/test_clock_import_ban.py tests/architectural/test_clock_call_ban.py` (the plan's gate table does not name them, but they scan `tests/` and `scripts/` repository-wide), `tests/architectural/test_ci_corpus_trigger_completeness.py tests/architectural/test_workflow_coherence.py tests/architectural/test_gate_selection_authority.py tests/architectural/test_ci_router_transcription_guards.py tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_module_shard_registry.py tests/ci/test_fleet_verdict.py tests/ci/test_fork_guard.py tests/ci/test_prose_only.py tests/ci/test_ci_module_wiring.py tests/release/test_pinning_inventory_fresh.py`, plus `tests/release` as a directory (the regenerated inventory selects the `release` shard).
- Also: `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, local `mypy --strict` over new modules as discipline.
- **S-rules and clock rule (binding for this WP)**: `contracts/tools/*.py` are non-test code, so ruff's bandit rules (`S`) apply there in full: shell out only with argument lists and `shutil.which`-resolved binaries (S603, S607), call `urlopen` only after an explicit `https` scheme check (S310), and make any suppression a one-line `# noqa: S###` with a stated rationale, never a blanket one. In `tests/`, never import `datetime` and never call `datetime.now()` or `time.time()`: compare ISO-8601 strings or use the kernel clock door.

## Subtasks

### Subtask T001: Record the base and run the baseline test set

**Purpose**: fix the commit everything refers to and take the named-file baseline (plan Baseline steps 1 to 3).

**Steps**:
1. Record `git log --oneline -1` and `git merge-base HEAD origin/main` (read-only) and the open-PR result of the overlap check (numbers, files, #5557 state).
2. Run, as one invocation, the planning-time command and record counts (planning-time result: 265 passed, 1 skipped, 0 failed):
   `PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/architectural/test_ci_corpus_trigger_completeness.py tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_workflow_coherence.py tests/architectural/test_module_shard_registry.py tests/ci/test_fork_guard.py tests/ci/test_fleet_verdict.py tests/ci/test_fleet_main.py tests/release/test_pinning_inventory_fresh.py`
3. Then, each as its own recorded run: `-m "corpus and not windows_ci"` over `tests/contract`; `tests/architectural/test_gate_selection_authority.py tests/architectural/test_ci_router_transcription_guards.py`; `tests/ci/test_prose_only.py tests/ci/test_ci_module_wiring.py`; `tests/architectural/test_no_legacy_terminology.py`; `tests/architectural/test_clock_import_ban.py tests/architectural/test_clock_call_ban.py` (record any pre-existing red so it is classed, not inherited); the whole `tests/release` directory; the named docs files (`tests/docs/test_docs_index_freshness.py tests/docs/test_docs_index.py tests/docs/test_docs_freshness_invariant.py tests/docs/test_changelog_style.py tests/docs/test_check_spelling.py`); `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .` (planning-time: clean over 2922 files); `.venv/bin/python -m scripts.docs.check_spelling` and `.venv/bin/python -m scripts.docs.check_changelog_style`. Do not run the whole `tests/architectural/` directory.
4. Bin every red: pre-existing known-P0, CI-environment, stale install, stale venv, or introduced (CLAUDE.md "Test-run baseline-red gotcha"). A suspected stale venv is reported to the orchestrator (the agent does not run a syncing command).

**Files**: none in this WP's diff (hand-off record only; the orchestrator writes it to `research.md` R-8, and WP12 T074 verifies it later, so the evidence is checkable there). **Validation**: every run has a recorded command and counts, or a recorded reason it could not run; the hand-off follows the template in the Definition of Done.

### Subtask T002: Floors, CI timings, `cutover-guard`

**Purpose**: the remaining baseline numbers (plan Baseline steps 4 to 7) that WP10 and WP12 depend on.

**Steps**:
1. Read-only script in the scratch directory (never committed; never import or call `materialize`): for every `kitty-specs/*/` directory with a `meta.json` count Missions, `tasks/WP*.md` files and the sum of `len(materialize_snapshot(dir).work_packages)` (`specify_cli.status.reducer.materialize_snapshot`); record status-lane, lifecycle and topology coverage as far as raw data shows and the snapshot-versus-files disagreement list length (indicative: 539, 3125, 2936, 52 with 45 fewer and 7 more). `git status --porcelain` identical before and after.
2. Read-only `gh` calls: the `tests-corpus` job duration (10 minute timeout) from a recent `ci-router.yml` run on `main`; the latest push-to-`main` `built-in-corpus-suite` duration (20 minute timeout) from `packs.yml`; and, from an existing PR with the same module selection, whether `diff-cover` ran and what it reported (expected: empty critical diff, no scorable lines, passes). Record job names, run identifiers and durations only.
3. `.venv/bin/spec-kitty cutover-guard --base-ref origin/main` if it is read-only (check `--help`); record the verdict.

**Files**: none in this WP's diff (hand-off record only; verified later by WP12 T074). **Validation**: numbers recorded with method, no absolute paths in the record.

### Subtask T003: Opening campsite commit (conditional) and inventory regeneration

**Purpose**: the plan's one tidy-first commit, only if debt is still there (plan "Campsite-clean").

**Steps**:
1. Count the whole-string literal `".github/workflows"` in `tests/ci/test_fleet_verdict.py` (`grep -c`). Planning count: five (twice in `test_new_pr_workflow_fails_closed`, once in `test_reporter_trigger_covers_every_registered_workflow_and_reruns`, twice in `replay_fixture`).
2. If three or more: run `.venv/bin/python -m pytest -q tests/ci/test_fleet_verdict.py`, record ids and counts; hoist the literal into one module constant; re-run, require identical test ids and counts and unchanged expected values; commit alone as `refactor(ci): name the workflows directory once in the fleet-verdict tests (#5558)`. The constant name must not mention `ci-quality.yml`, the retired sonar job id or `make test-fast`.
3. Regenerate the inventory with `python3 scripts/ci/derive_pinning_inventory.py` in the same commit (never by hand) and run `tests/release/test_pinning_inventory_fresh.py`.
4. If fewer than three: land no commit; write "no domain-matched debt found in the FR-017 edit surface" in the hand-off notes for WP12 to record. Do not tidy anything else (no `_CORPUS_GLOBS` documentation, no `ruff.toml` baseline).

**Files**: `tests/ci/test_fleet_verdict.py` (about 10 lines changed), `tests/release/pinning_rule_inventory.json` (derived).
**Validation**: identical pass counts before and after; freshness test green.

### Subtask T004: `contract_resolver.py` with golden-tree tests

**Purpose**: the single resolution authority (D-P1, OQ-1).

**Steps**:
1. First commit: `tests/contract/test_contract_resolver.py` with golden-tree cases (hand-written expected trees under `contracts/tools/fixtures/contract_resolver/`, one case per supported construct: relative file `$ref`, in-file JSON pointer, sibling keywords next to `$ref`, `allOf`/`oneOf`/`anyOf`, a brace-named file referenced through the constant) and refusal cases for each stable error code: `UNRESOLVED_REF`, `URL_REF`, `ABSOLUTE_REF`, `TILDE_POINTER`, `CYCLE`, `NOT_A_MAPPING`. Also in this first commit, the **single-source test** in the same module (Rule BRACE-1): it parses with `ast` every `*.py` under `contracts/tools/` and `tests/` outside any `fixtures/` directory, asserts `BRACE_REF_SPELLING` is assigned in `contract_resolver.py` only and is a 2-tuple of non-empty strings, asserts `layout_check.py` imports it, and asserts no scanned file other than `contract_resolver.py` contains either piece of the tuple or the raw-brace path-file stem as a string literal (the test builds its own patterns from the constant and `chr(123)`, so it contains no literal itself); a planted offending file under `tmp_path` proves the scan fails (a scan that visited zero files fails too). Red because the module does not exist. Single-line marker `pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]` (a multi-line list is not detected by the registry gate). **Corpus wiring lands in this same first commit** (this is T008 steps 1 to 3 for this module, done first so the completeness gate is never red): the routing test is written red first, then the router glob, the scrub-JSON entry and this module's sorted registry row land together with this first corpus-marked module. Run `tests/architectural/test_ci_corpus_trigger_completeness.py` after this commit.
2. Implement `contracts/tools/contract_resolver.py` (stdlib plus PyYAML, py311 syntax): `resolve(module_dir)` returning the dereferenced tree and counts (`path_items`, `schemas`, `refs_resolved`); the supported-construct list as one constant; the `BRACE_REF_SPELLING` constant; percent-decoding before filesystem lookup. Refuse unlisted forms loudly.
3. The module never imports pytest, anything under `tests/`, or `scripts.` (loaded by tests via `importlib.util` from the file path, because `contracts/` is not a package).
4. Treat annotated class-level targets as defined names where symbol logic is shared later (PQ-10 is implemented by WP06; do not pre-build it here).

**Files**: `contracts/tools/contract_resolver.py` (new, ~250 lines), `tests/contract/test_contract_resolver.py` (~200 lines), `contracts/tools/fixtures/contract_resolver/**`, plus (first commit only, per the wiring step) `.github/workflows/ci-router.yml` (+1 line), `tests/release/ci_retirement_scrub.json` (+1 entry), `tests/ci/test_contracts_routing.py` and the registry row.
**Validation**: tests green; `ruff` and format clean.

### Subtask T005: `leak_patterns.py` and `schema_formats.py`

**Purpose**: single authorities for leak patterns (D-P11) and date-time format policy (D-P14).

**Steps**:
0. Each module's first commit also appends its own sorted registry row to `_CORPUS_MARKED_MODULES` (`test_leak_patterns.py`, `test_schema_formats.py`); the completeness gate stays green after every commit.
1. Failing tests first: `test_leak_patterns.py` (pattern behaviour per field class from spec FR-012: strict-field host-path patterns, human-text host-path patterns, e-mail pattern, forbidden property names incl. camel-case forms; planted values assembled from string fragments at run time so test source holds no literal host path or address; the real pass controls `~/.kittify Runtime Centralization` and `/tmp burn-down: sync` for the human-text class) and `test_schema_formats.py` (registered set of `FORMAT_CHECKER` is exactly `{date-time}`; a malformed timestamp is rejected; subprocess test with two child interpreters, one with a `sys.meta_path` blocker for `rfc3339_validator` and `jsonpointer` installed before `jsonschema` imports, one without, both rejecting; mutation check described in D-P14).
2. Implement both libraries. `leak_patterns.py` writes its pattern sources and name lists from fragments so it does not match its own rules. `schema_formats.py` builds `FormatChecker(formats=())` and registers an explicit stdlib RFC 3339 check (pattern plus `datetime` parse).
3. Checksum or hashing code, if any, needs the narrow `# noqa: TID251` with a file-integrity rationale (ruff bans `hashlib.sha256` otherwise). None is expected in these two modules.

**Files**: two modules (~120 and ~60 lines), two test modules (~150 lines each).
**Validation**: both modules green; the subprocess test shown to fail under the mutation (bare `FormatChecker()`).

### Subtask T006: `layout_check.py` with planted fixtures

**Purpose**: FR-001 layout rules, parametric on `BRACE_REF_SPELLING`.

**Steps**:
0. This module's first commit also appends its own sorted registry row (`test_layout_check.py`); the completeness gate stays green after every commit.
1. Failing tests and fixtures first, one planted violation per rule with a clean control on the same fixture root under `contracts/tools/fixtures/layout_check/`: `PATH_FILE_NAME`, `MAPPED_FILE_MISSING`, `ORPHAN_PATH_FILE`, `SCHEMA_NAME_MISMATCH`, `INDEX_MISSING_FILE`, `INDEX_OMITS_FILE`, `BAD_REF_FORM` (URL, absolute, `~1`), `BRACE_REF_SPELLING`, `SHARED_MISUSE`, `TRACKED_BUNDLE`. Exit 2 codes `NO_MODULE`, `ZERO_PATH_FILES`, `ZERO_INDEX`; each asserts a minimum input count before the property check (FR-025).
2. Implement `layout_check.py` (`--root`, default `contracts`; module discovery = direct subdirectory with a root `openapi.yaml`; `_shared`, `fixtures`, `gradle`, `tools` never modules); output `CONTRACT-CHECK layout_check: <CODE>: <detail>` and `counts: modules=.. path_files=.. index_files=..`.
3. Fixture files contain nothing leak-shaped (committed plants must not hold host paths or e-mail addresses).

**Files**: `contracts/tools/layout_check.py` (~300 lines), tests (~250 lines), fixtures.
**Validation**: tests green; running against the real `contracts/` exits 0 only once a module exists, which is after WP03 (until WP03 lands, the real tree exits 2 `NO_MODULE` by design; that is not a failure of this WP).

### Subtask T007: `contracts/_shared/**` and README skeleton

**Purpose**: FR-002 and the FR-001 README skeleton.

**Steps**:
1. `contracts/_shared/schemas/` (`Problem`, `PageCursor`, `PageInfo`, `_index.yaml`), `parameters/` (`_index.yaml`, page parameters), `responses/` (`_index.yaml`, shared `Problem` response with media type `application/problem+json`). The page cursor is opaque and has no schema relationship to the stream cursor (named differently; the bare word "cursor" is not used in field names). Every property is described. These shared pieces are validated by `layout_check` (name equals file, index lists present files).
2. `contracts/README.md` skeleton with one heading per required topic (final text is WP11). **This list is the single authority for the README headings**; WP07 copies it verbatim into a constant in `structure_check.py` (WP07's `structure_check` is the single heading authority); WP11 only runs `structure_check` on the final README and adds no test: layout; path-file naming; relative `$ref` rules; `_shared/` admission; per-module `info.version` and `/api/v1`; `x-source` / `x-derived` / `x-provisional`; status lane vs code lane vs repo-root lane (execution lane only as umbrella); workflow phase vs glossary `phase`; `Topology` enum vs `MissionStatus.topology`; bundle is a build product; the one local validate-and-bundle command with its prerequisite (a JDK and network access, NFR-006); markdown lint advisory; the `src/specify_cli/contracts/` collision line; board-column mapping as a consumer convention; the versioning rule; the residual-risk statement on handle-shaped strings; the reader-author warning with its local command; the preview tag namespace. List the exact heading strings, in order, in your hand-off.
3. Do not touch `contracts/fixtures/` (C-004); `git diff --stat contracts/fixtures` must be empty.

**Files**: ~8 YAML files (~25 lines each), README (~80 lines).
**Validation**: `layout_check` over a temporary root containing `_shared/` plus a one-file module passes.

### Subtask T008: Router glob, scrub copy, routing pin test and registry rows

**Purpose**: FR-020 corpus wiring, red-first. **Order: steps 1 to 3 are executed as part of T004's first commit** (see T004), so no commit between T004 and T008 leaves the completeness gate red; the rest of this subtask completes and verifies it.

**Steps**:
1. First: `tests/ci/test_contracts_routing.py`, failing because the glob is absent. It asserts: the glob `contracts/**` is present exactly once in the router's `corpus` group (fail on an empty filter); a contracts-only path set selects `tests-corpus` and no module shard (use `scripts.ci.gate_selection.select_gates` and `select_modules`, read-only); `.github/CODEOWNERS` alone selects nothing in the router; the prose-only effect (R-11): a diff made only of `contracts/**` files and docstring-only Python edits can classify as prose-only; preview tags `preview/mission-status/p<N>` are out of scope here (WP09 owns that guard).
2. Add the single line `- 'contracts/**'` to the `corpus` group of `.github/workflows/ci-router.yml` **in the same commit as the first corpus-marked module and its registry row (T004's first commit)**, so the completeness gate is never red. Add the matching root to `non_src_router_groups` (corpus) in `tests/release/ci_retirement_scrub.json` by hand in that commit. Do not touch `.github/ci-module-registry.yml` or `pytest.ini`.
3. Sorted registry rows in `_CORPUS_MARKED_MODULES` for the four modules this WP adds (`test_contract_resolver.py` with T004, `test_leak_patterns.py` and `test_schema_formats.py` with T005, `test_layout_check.py` with T006, each in that module's own first commit); verify all four are present in sorted order and record the one-line rationale (declared append-only exception). No commit from T004 onward may leave `test_ci_corpus_trigger_completeness.py` red.
4. Regenerate the inventory (`python3 scripts/ci/derive_pinning_inventory.py`) because router and test edits can shift scanned lines; run the freshness test and the `tests/release` directory. No new text may mention `ci-quality.yml`, the retired sonar job id or `make test-fast`.
5. Evidence: `.venv/bin/python -m pytest --collect-only -q -m "corpus and not windows_ci" tests/contract/test_contract_resolver.py` collects the module; record it.

**Files**: `ci-router.yml` (+1 line), scrub JSON (+1 entry), `tests/ci/test_contracts_routing.py` (new, ~120 lines), registry (+4 rows).
**Validation**: named gate files above green; routing test red before and green after the glob.

## Orchestrator record step: baseline (writes `kitty-specs/`, so not an agent action)

After this WP is approved the orchestrator writes the baseline hand-off into `research.md` R-8 (new sub-heading "Baseline record") and a dated line into `tracer-approach.md` "Log", commits it with `spec-kitty safe-commit` on the planning surface, files tracker issues for any pre-existing red, and records the issue numbers next to the entries. WP12 re-verifies the record.

## Definition of Done

- Baseline hand-off complete (T001, T002), using this template so it is checkable: `base_hash`; `merge_base`; `open_pr_overlap` (numbers, files, #5557 state); one line per run with `command`, `passed/skipped/failed` counts; `binned_reds` (each with bin, evidence and, for pre-existing, the issue number the orchestrator opened); `floors` (Missions, work package files, snapshot work packages, disagreement count with the method); `ci_durations` (job, run identifier, duration); `cutover_guard` verdict. WP12 T074 verifies the orchestrator's copy in `research.md` R-8.
- All four library/check modules and their unit tests are green, each with a planted-violation case and clean control; first commit of each is red on the base.
- Router diff is exactly one line; scrub JSON diff is exactly one entry; `ci-module-registry.yml`, `pytest.ini`, `_CORPUS_GLOBS`, `_CORPUS_DATA_ROOTS` and `contracts/fixtures/` untouched.
- Registry rows appended in sorted order for every corpus-marked module added; `test_ci_corpus_trigger_completeness.py` green.
- Derived inventory regenerated by its script; `tests/release` directory green.
- Rule BRACE-1 acceptance (two checks, both able to pass and able to fail): (1) the single-source test in `tests/contract/test_contract_resolver.py` passes and its planted-offender case is red; (2) production-code grep, expected empty, with the patterns taken from the constant (never the provisional literal): `.venv/bin/python -c "from contract_resolver import BRACE_REF_SPELLING as B; print('\n'.join(B))" > $TMPDIR/pieces` run with `contracts/tools` on `sys.path`, then `grep -rnF --include='*.py' --exclude-dir=fixtures --exclude=contract_resolver.py -f $TMPDIR/pieces -e 'missions_{' contracts/tools tests/contract tests/ci` matches nothing (fixtures are data and excluded by construction). Non-vacuity: the same grep over `contracts/tools/contract_resolver.py` alone must hit (it defines the constant), and `contracts/tools/fixtures/layout_check/` must contain at least one fixture file with a piece of the tuple, and that hit comes from the clean-control file (the file holding the canonical spelling), not from the planted `BRACE_REF_SPELLING` violation, which holds the non-canonical form (both exist from this WP; the `contract_resolver/` golden tree is added by WP04, which carries the same guard from then on). `plan.md` is not edited (out of scope for the tasks phase) and its looser wording is deviated from here on purpose.
- `ruff check .` and `ruff format --check .` clean; new modules pass `mypy --strict` locally (discipline, no CI job); no S603, S607 or S310 finding left unjustified; the two clock-ban gate files green.
- No commit between T004 and T008 left the corpus completeness gate red (checked per commit).
- Per-subtask completion recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Risks

- Hidden byte-for-byte pinning gate (tracer F-5): forgetting regeneration is not caught by CI on a `ci`-only diff. Mitigation: regenerate in this WP and run the freshness test by name.
- The router glob changes prose-only classification (R-11): pinned by the routing test.
- Resolver scope creep: keep the supported-construct list minimal; the contract authors extend it in the same commit that first uses a new construct.

## Reviewer Guidance

Verify red then green for each module (check the first commit of each). Confirm the router diff is one line and the registry edit is rows only. Confirm the resolver refuses unlisted constructs with stable codes, and that no Python file outside `contract_resolver.py` hard-codes a brace spelling or path-file name (Rule BRACE-1). Confirm no `src/` change and no import of pytest or `tests/` from `contracts/tools/`. Run the named gate files, not a directory sweep.

Implementation command: `spec-kitty agent action implement WP01 --agent claude`
