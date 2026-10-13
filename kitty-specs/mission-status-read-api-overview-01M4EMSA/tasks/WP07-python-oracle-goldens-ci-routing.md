---
work_package_id: WP07
title: 'Phase 2b: Python oracle, fixtures, goldens, golden-honesty test and CI routing'
dependencies:
- WP01
requirement_refs:
- FR-008
- FR-006
- FR-001
- FR-005
- C-006
- NFR-005
- SC-001
- SC-007
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
subtasks:
- T036
- T037
- T038
- T039
- T040
- T041
history: []
agent_profile: python-pedro
authoritative_surface: tests/contract/
create_intent:
- tests/contract/_mission_status_conformance.py
- tests/contract/test_mission_status_conformance.py
- services/mission-status-api/src/main/resources/leak-patterns.json
- tests/ci/test_mission_status_routing.py
execution_mode: code_change
model: ''
owned_files:
- tests/contract/_mission_status_conformance.py
- tests/contract/test_mission_status_conformance.py
- services/mission-status-api/src/test/resources/conformance/**
- services/mission-status-api/src/main/resources/leak-patterns.json
- .github/workflows/ci-router.yml
- .github/workflows/packs.yml
- tests/ci/test_mission_status_routing.py
- tests/ci/test_contracts_workflows.py
- tests/architectural/test_ci_corpus_trigger_completeness.py
- .gitattributes
- tests/contract/_mission_status_payloads.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP07 - Phase 2b: Python oracle, fixtures, goldens, honesty test and CI routing

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Build the Python side of the conformance gate: the golden generator (with per-fixture temporary git provisioning and the project-header HEAD materialisation), the curated fixture trees and their goldens, `manifest.json`, `resolver-cases.json`, `leak-patterns.json`, the golden-honesty test that fails on any difference, and the CI routing edits that give the new module exactly one home.

## Context

- Plan phase 2b (plan.md sections 1 "Python additions", 2 "Conformance goldens", 7 (Q-3), 11 row 2b, 13 "Projection", test strategy AC-8 rows; the Mission directory's contracts/service-contract-notes.md (kitty-specs/mission-status-read-api-overview-01M4EMSA/contracts/, not the repository-root contracts/) "Conformance data formats" and "Comparison rule"). Spec FR-008 (class table, AC-8a, 8b, 8d, 8e, 8f), FR-006 (AC-6, `resolver-cases.json`), FR-001 (project-header class, AC-1f), FR-005 (AC-5d), AC-9g (projection class), NFR-005, SC-001, SC-007.
- Depends on WP01 ONLY (the campsite constant it fills). The plan sequences 2b after phase 1 for review order, but nothing technical needs phase 1 (the services tree, the workflow and the Gradle build are not inputs of the Python oracle), and keeping WP07 off the Java chain is what lets the lane computation place it in its own lane (a WP07 that depended on WP04 while WP09 depends on WP07 would make the lane graph cyclic). It therefore runs in parallel with WP02-WP06, WP08 and WP17-WP19; WP09 needs it. Write-disjoint from every Java WP: it reads NO Java output and not `portlevel-tests.txt`. Its chokepoints (`ci-router.yml`, `packs.yml`, `tests/ci/test_contracts_workflows.py`, `.gitattributes`) are edited by no other WP except WP01 (earlier, same lane).
- The oracle is the existing helper set, not a third oracle: reuse `tests/contract/_mission_status_payloads.py` (`build_overview`, `resolve_read_dir`, `Projector`, `tree_fingerprint`, `load_contract_tools`) and `tests/contract/_mission_status_project.py` (`read_head`, `head_file`), `specify_cli.status.reducer.materialize_snapshot`, and the anchor `tests/contract/fixtures/mission_status_expected.json` via `load_expected`/`expected_mismatches` (the new module invokes that anchor check too).
- **File-name trap**: `test_the_contract_tools_filter_group_names_every_src_file_the_mission_status_reader_its_tests_import_and_the_contract_cites` derives required `contract_tools` group entries from imports of every `tests/contract/*mission_status*.py`. Both new modules match that glob. Keep their `src` imports inside files the group already names (`status/reducer.py`, `status/store.py`, `status/tail_reader.py`, `status/progress.py`, `missions/_read_path_resolver.py`, `migration/schema_version.py`, `mission_metadata.py`), or add the entries in the same commit.
- The Python oracle needs git: `build_overview` goes through `MissionStatus.load` -> `is_registered_coord_worktree` -> `git worktree list --porcelain` when the resolved read directory has a `.worktrees` ancestor, and `probe_coord_state` runs `git rev-parse`. A committed static tree has no `.git`, so the generator and the honesty test materialise every fixture into a temporary git repository at run time (plan.md section 1 recipe, which you MUST read in full: fresh temp root per fixture; `git init` + one commit only for fixtures that need git; for `coord` class a coordination branch named by `coord_branch_name` and a worktree registered with `git worktree add` at the coordination worktree ROOT `CoordinationWorkspace.worktree_path(...)`, NOT at the Mission directory `coord_feature_dir`; husks are plain unregistered directories; `GIT_CONFIG_GLOBAL` = empty file, `GIT_CONFIG_NOSYSTEM=1`, fixed identity and `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE`, `commit.gpgsign=false`, no remote; no temp path, SHA or git date enters a golden byte).
- Project-header materialisation: a fixture holds a `HEAD` text file (exact text to install as `.git/HEAD`) or a `GITDIR_POINTER` text file (the `.git` pointer file's exact text, a relative `gitdir: gitdir-target`) plus `gitdir-target/HEAD`; no `git init` and no commit run for these. The same step is shared by the generator, the honesty test and (WP09) the Java fixture factory; document its contract in the manifest (`headText` per project-header fixture).
- Canonical form (NFR-005): sorted keys, compact separators `,` and `:`, UTF-8 without ASCII escaping, i.e. `json.dumps(..., sort_keys=True, ensure_ascii=False, separators=(",", ":"))`. The comparison ignore-list is ONE named EMPTY constant, asserted empty by a test. No timestamp, ordering or number is normalised.
- The Packs advisory corpus lane runs `-m "corpus and not windows_ci"` with a hand-written list of 35 `--deselect tests/contract/<module>.py` entries; the new module must be deselected there (it has exactly one home: `tests (contract tools)`).
- Public repo hygiene: fixtures use synthetic ULIDs, `meta.json` contents with no real names, no absolute home-directory paths; avoid `< > : " \ | ? * $ { }` in every path (NFR-009); directory names must not differ only by case.

## Subtask T036: Generator core, provisioning and the canonical writer (red-first)

**Purpose**: `tests/contract/_mission_status_conformance.py` (importable helper + `main()`; the leading underscore keeps it out of collection).

**Steps**:
1. Test-first in `tests/contract/test_mission_status_conformance.py` for the machinery: (a) canonical writer vs a planted unordered dict (AC-8d revert: an unsorted-keys writer turns the byte-identity test red); (b) deterministic-provisioning test: generate twice into differently named temp roots under different fixed dates and require byte-identical goldens (AC-8d); (c) registration check comparing `git worktree list --porcelain` with `CoordinationWorkspace.worktree_path` (the worktree ROOT) for every `coord`-class fixture, asserting `classify_worktree_topology` returns `WorktreeTopology.COORD_WORKTREE` for the coordination read directory and `UNREGISTERED` for every husk, and finding no registry entry for an `own`-class fixture; two planted controls turn it red: skip the registration, or register the Mission directory instead of the worktree root; (d) project-header: the branch the oracle read (`read_head`) equals the branch parsed from the fixture's HEAD text; revert: change one fixture's HEAD text in a scratch copy so it disagrees and the assertion goes red.
2. Implement provisioning per the context recipe, `--write` (writes goldens + manifest + `leak-patterns.json` under `services/mission-status-api/src/test/resources/conformance/` and `.../src/main/resources/`), `--check` (compares, writes nothing), invocation `.venv/bin/python -m tests.contract._mission_status_conformance --write` from the repository root. Only fixtures that need git get a repository; `own`-class fixtures with no `.worktrees` ancestor, including all `project-header`, are materialised WITHOUT one.
3. `MissionStatusIgnoreList: tuple = ()` named constant, asserted empty by a test.
4. Types annotated, `ruff` clean, complexity <= 15, no literal repeated 3+ times (hoist to constants).

**Files**: `tests/contract/_mission_status_conformance.py` (~450 lines), test module (grows to ~600 lines over T036-T040).
**Validation**: `PWHEADLESS=1 .venv/bin/python -m pytest tests/contract/test_mission_status_conformance.py -m "corpus and not windows_ci" -q`.

## Subtask T037: `leak-patterns.json` and the manifest

**Purpose**: One source of truth for the redaction patterns (plan.md section 13 "Projection"; AC-9g).

**Steps**:
1. Generate `services/mission-status-api/src/main/resources/leak-patterns.json` from `contracts/tools/leak_patterns.py` (STRICT and HUMAN host-path patterns, email, secret patterns, the tokens `[path]` and `[email]`): pattern text, flags, class, token. Limit to the subset common to Python `re` and `java.util.regex`; if a pattern uses a Python-only construct, record the divergence in the manifest and raise it as a finding rather than rewriting the pattern.
2. `manifest.json` keys: `specKittyEventsVersion` (from the installed package; AC-5d: the honesty test asserts equality with the installed version, naming both on failure), `supportedSchemaMin`, `supportedSchemaMax` (the test asserts equality with `MIN_SUPPORTED_SCHEMA`/`MAX_SUPPORTED_SCHEMA` in `src/specify_cli/migration/schema_version.py`: AC-1f), `resolverCaseIds`, `classes[]` of `{tag, fixtures[], property, parity}` with parity `python-golden` | `java-only`, per fixture `readDirectoryClass` (`own`|`coord`), `headText` per project-header fixture, `leakPatternsSha256`, and per pattern probe strings with Python's verdicts, and the strict/human class of each projected field (`missionId`, `slug`, `friendlyName`, `targetBranch`, `missionType`).
3. Revert-fails: remove one pattern from a scratch copy of `leak-patterns.json` => the manifest SHA-256 check and the `projection` class go red.

**Files**: generated JSON (reviewed by regeneration command).
**Validation**: the honesty test (T040).

## Subtask T038: Fixture trees, batch A (and `resolver-cases.json`)

**Purpose**: The classes whose outcome is decided by reduction and path resolution.

**Steps** (static trees under `conformance/<class>/<fixture>/kitty-specs/<slug>/{meta.json,status.events.jsonl}` plus `.kittify/*.yaml` where the class needs it; goldens under `<fixture>/golden/*.json`; read the FR-008 table row by row and implement EVERY distinguishing property):
1. `interleaved` (two Missions): non-empty events; equal `at` with different `event_id`; file order differing from sort order; a duplicated `event_id`; rows whose text order of `at` differs from instant order (a `+02:00` row against a `Z` row; two rows differing only in fractional-second digits) so a parsed-instant sort or a text `lastActivityAt` changes a golden value.
2. `coordination` (one coord Mission): a current ledger under `.worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>/` and a primary ledger whose lane counts differ. `coord-husk` (a `single_branch` and a `lanes` Mission): a husk ledger beside the Mission whose counts differ from the primary (AC-6d: the overview reflects the PRIMARY ledger). `absent-topology` (no `topology`, with valid and with corrupt `lanes.json`). `lifecycle-only` (only the seven lifecycle types, `wpTotal` 0). `no-ledger` (two Missions, one with `discardedAt` set => `discarded`, not `draft`). `log-truncated` (a shrunken log and a same-length last-line rewrite, plus the stream scenario description).
3. `resolver-cases.json`: array of `{id, storedTopology, coordRootPresent, coordMissionDirPresent, lanesJson: "valid"|"corrupt"|"absent", expectedClass}`; ids recorded in the manifest (`resolverCaseIds`). No case whose Python answer needs a git verdict that directory existence cannot reproduce (Q-3 interim, plan.md section 7); the coordination husk starts as `same by code reading`; the husk golden decides it. Put the classification record text in your report for the orchestrator (research.md R-9 is orchestrator/WP02-owned, documentation only).
4. Committed trees carry NO `.git`. Line endings are preserved by the scoped `.gitattributes` line (T041). Fixtures avoid Windows-illegal characters and case-colliding names.

**Files**: ~15 fixture trees (data), goldens written by the generator.
**Validation**: `--write` then `--check` clean; the tree contains one golden per fixture.

## Subtask T039: Fixture trees, batch B

**Purpose**: Malformed input, tear, CRLF, project header, projection, canaries, symlinks.

**Steps**:
1. `malformed-rows` (one Mission per variant: invalid JSON line, non-object line, missing required key, unknown lane, unknown `kind`, malformed `meta.json`, empty `meta.json`, non-UTF-8 `meta.json`, a directory without `meta.json` (not a Mission: not listed, no diagnostic), invalid UTF-8 ledger bytes, a blank line): each golden records live Python's outcome (the exception CLASS actually raised: `StoreError`, `DiaryError`, `UnicodeDecodeError`, `ValueError`), not an assumed one. OS-unreadable `meta.json` (L7) and unlistable directory (L11) have no Python golden (Java fault injection, WP08).
2. `torn-final-line` (two Missions): (a) unterminated unparseable last line => Python golden of the refusal; (b) unterminated last line that is valid JSON => Python's mixed-prefix overview tagged `knownDivergence` (the Java assertion is the L4b refusal, WP09).
3. `crlf-and-listing`: a CRLF ledger with an LF twin (equal counts, different `streamCursor`) and Missions whose directory names sort differently by byte order and by case folding (page order equals the contract order).
4. `project-header`: healthy; `.kittify/metadata.yaml` absent; unknown schema version; detached `HEAD`; a branch name failing the pattern; a name over 255 chars; a host-path-shaped name; an unborn branch; a `.git` pointer file with a relative `gitdir:`. Each is a `HEAD`/`GITDIR_POINTER` text file; no repository.
5. `projection`: a friendly name holding a host path and an email (golden has `[path]` and `[email]`); a nullable strict field with a path-shaped value (golden `null`); a non-nullable strict field with a token-shaped value (the oracle raises `ProjectionError`: the golden records the refusal; the Java answer is the 500 of rows L3a/L3b with `projection_refused`).
6. `secret-canaries` (one project; Java assertion only, no canary golden) and `symlink` plan: canary values planted in `.kittify/config.yaml`, `.kittify/metadata.yaml`, `meta.json` and event payload text. Symlink fixtures are created at TEST time, never committed; tag `javaOnly` in the manifest and have the Python test skip them by that tag while asserting the tag is present.

**Files**: ~20 fixture trees.
**Validation**: `--write` / `--check` clean.

## Subtask T040: The golden-honesty test and its perturbations

**Purpose**: FR-008 (ii), AC-8a (Python side), AC-8b, AC-8d, AC-5d, AC-1f.

**Steps**:
1. `pytest.mark.corpus`. For every non-`javaOnly` fixture: provision, run the oracle, canonicalise, and require byte equality with the committed golden; plus the file-set check (one golden per fixture, exactly `manifest.json` and `resolver-cases.json` as non-class files; `portlevel-tests.txt` is NOT in this tree), the class tags, and EACH class's distinguishing property read from golden CONTENT (a trivial golden carrying the right tag fails: AC-8b; test it with a planted trivial document in a scratch copy).
2. The anchor check (`load_expected`/`expected_mismatches`) runs in the same module.
3. Version/range guards: `specKittyEventsVersion` equals the installed version; supported range equals `schema_version.py`; resolver case ids equal the manifest.
4. AC-8a Python-side perturbations: edit one golden value in a temp copy; monkeypatch one derivation helper; each turns the test red.
5. Every discovered set carries a named floor (per-class fixture floor from the manifest, zero matches fails).
6. The test must run in a few seconds per fixture; no network.

**Files**: `tests/contract/test_mission_status_conformance.py`.
**Validation**: `PWHEADLESS=1 .venv/bin/python -m pytest tests/contract/test_mission_status_conformance.py tests/contract/test_gradle_pin_check.py tests/contract/test_verify_pins.py -m "corpus and not windows_ci" -q`, plus `.venv/bin/python -m tests.contract._mission_status_conformance --check`.

## Subtask T041: CI routing, registry, Packs deselect, `.gitattributes` and routing tests

**Purpose**: AC-8e/8f, SC-007, PR-16.

**Steps** (red-first: write `tests/ci/test_mission_status_routing.py` first):
1. `.github/workflows/ci-router.yml`: add `services/mission-status-api/src/test/resources/conformance/**` to the `contract_tools` filter group (the ONE filter-group line; no other router edit). In `tests/ci/test_contracts_workflows.py` add it as the FIRST entry of `ROUTER_ONLY_EXTRA_GLOBS` (WP01's constant) with its one-line rationale.
2. `tests/architectural/test_ci_corpus_trigger_completeness.py`: `_CORPUS_MARKED_MODULES` gains `tests/contract/test_mission_status_conformance.py` (AC-8f; revert: drop the entry and the registry test goes red).
3. `.github/workflows/packs.yml`: add exactly one `--deselect tests/contract/test_mission_status_conformance.py` token to the advisory corpus command (the one-token diff).
4. `.gitattributes`: one scoped line `services/mission-status-api/src/test/resources/conformance/** -text` (never a global rule) so CRLF fixture bytes survive checkout.
5. `tests/ci/test_mission_status_routing.py` (beside `test_contracts_routing.py`): AC-8e - a golden-only diff (`services/mission-status-api/src/test/resources/conformance/manifest.json`) selects `tests (contract tools)` and nothing else Python, via `scripts.ci.gate_selection.select_gates`/`select_modules`; a `services/**`-only diff outside the conformance tree selects no code-shard gate; a `src/**` change does not trigger the native matrix; the Packs `--deselect` of the new module is present, every named module exists, and the discovered-count guard sees 36 entries (35 + the new one). Revert rows: delete the conformance glob from a temp copy of `ci-router.yml` => routing test red; remove the `--deselect` token from a temp copy of `packs.yml` => red.
6. Run the router/packs targeted gates: `.venv/bin/python -m pytest tests/ci/test_contracts_routing.py tests/ci/test_contracts_workflows.py tests/ci/test_mission_status_routing.py tests/ci/test_corpus_blocking_home.py tests/architectural/test_ci_corpus_trigger_completeness.py -q`.
7. `ruff check` and `ruff format --check --force-exclude` on every Python file touched; `.venv/bin/python scripts/generate_contextive_glossaries.py check` stays clean (no glossary change expected).

**Files**: the workflow files (one line, one token), `.gitattributes` (+1 line), three test files.
**Validation**: the command in step 6 green; the diff review check: the `ci-router.yml` diff is exactly one filter-group line.

## Definition of Done

- Generator `--write` is deterministic and `--check` is clean; the honesty test fails on any difference and each AC-8 perturbation was observed red.
- All fixture classes of the FR-008 table exist with machine-checked distinguishing properties read from content; `javaOnly` classes are tagged.
- `leak-patterns.json`, `manifest.json`, `resolver-cases.json` committed, generated by command, never hand-edited.
- Router glob, extras constant entry, corpus registry entry, one Packs deselect token and one `.gitattributes` line are the only shared-surface edits; routing tests pass with revert rows observed red.
- No Java output read; no absolute home path; no Windows-illegal path.

## Risks

- Largest WP of the Mission (generator + about 35 fixtures + CI routing). Report if it will not fit one sitting: the seam is T038-T039 (fixture authoring) versus T036-T037 and T040-T041.
- A hidden git dependence (`probe_coord_state` rev-parse) for a fixture class not predicted: the provisioning test and a failing oracle run reveal it; add git for that class only, never globally.
- Python/Java regex divergence: surfaced by the manifest probes; a pattern that cannot be common-subset is a finding.
- A concurrent Python reducer change (risk PR-2; open PR #5953 touches `status/store.py`): this test goes red first, which is its purpose.

## Reviewer Guidance

- Run `--write` twice and `--check`; confirm byte identity and no git detail in any golden.
- Confirm each class property is read from content and the planted trivial golden fails.
- Confirm the shared-surface diff is exactly the planned one line/token/line and nothing else in `ci-router.yml`.

## Implementation command

`spec-kitty agent action implement WP07 --agent claude`
