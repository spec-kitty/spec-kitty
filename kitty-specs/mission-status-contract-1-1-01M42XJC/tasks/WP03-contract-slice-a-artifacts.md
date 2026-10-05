---
work_package_id: WP03
title: 'Contract slice A: listArtifacts and getArtifactContent'
dependencies:
- WP02
requirement_refs:
- FR-009
- FR-010
- FR-011
- FR-012
- FR-013
- FR-017
- FR-018
- FR-019
- C-001
- C-002
- C-004
- SC-001
planning_base_branch: issue-5625-mission-status-contract-1-1
merge_target_branch: issue-5625-mission-status-contract-1-1
branch_strategy: Planning artifacts for this mission were generated on issue-5625-mission-status-contract-1-1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5625-mission-status-contract-1-1 unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
- T014
- T015
- T016
history: []
agent_profile: implementer-ivan
authoritative_surface: contracts/mission-status/
create_intent:
- contracts/mission-status/paths/missions_missionId_artifacts.yaml
- contracts/mission-status/paths/missions_missionId_artifacts_content.yaml
- contracts/mission-status/parameters/ArtifactPath.yaml
- contracts/mission-status/schemas/ArtifactKind.yaml
- contracts/mission-status/schemas/ArtifactEntry.yaml
- contracts/mission-status/schemas/ArtifactListing.yaml
- contracts/mission-status/schemas/ArtifactContent.yaml
- contracts/mission-status/schemas/ArtifactRefusalCode.yaml
- contracts/mission-status/schemas/ArtifactRefusal.yaml
- contracts/mission-status/schemas/ArtifactPath.yaml
- contracts/mission-status/responses/ArtifactPathRefused.yaml
- contracts/mission-status/responses/ArtifactNotFound.yaml
- contracts/mission-status/responses/ArtifactTooLarge.yaml
- contracts/mission-status/responses/ArtifactNotText.yaml
- contracts/mission-status/responses/ArtifactSecretRefused.yaml
- contracts/mission-status/responses/ArtifactUnreadable.yaml
- contracts/mission-status/responses/ArtifactListingUnreadable.yaml
- contracts/mission-status/examples/ArtifactListing.populated.yaml
- contracts/mission-status/examples/ArtifactListing.truncated.yaml
- contracts/mission-status/examples/ArtifactContent.markdown.yaml
- contracts/mission-status/examples/ArtifactContent.redacted.yaml
- contracts/mission-status/examples/ArtifactContent.json.yaml
- contracts/mission-status/examples/ArtifactContent.empty.yaml
- contracts/mission-status/examples/ArtifactRefusal.invalid-artifact-path.yaml
- contracts/mission-status/examples/ArtifactRefusal.not-found.yaml
- contracts/mission-status/examples/ArtifactRefusal.artifact-too-large.yaml
- contracts/mission-status/examples/ArtifactRefusal.artifact-not-text.yaml
- contracts/mission-status/examples/ArtifactRefusal.artifact-secret.yaml
- contracts/mission-status/examples/ArtifactRefusal.artifact-unreadable.yaml
- contracts/mission-status/examples/ArtifactRefusal.artifact-listing-unreadable.yaml
execution_mode: code_change
model: ''
owned_files:
- contracts/mission-status/openapi.yaml
- contracts/mission-status/CHANGELOG.md
- contracts/mission-status/schemas/_index.yaml
- contracts/mission-status/parameters/_index.yaml
- contracts/mission-status/responses/_index.yaml
- contracts/mission-status/examples/_index.yaml
- contracts/tools/enum_pins.json
- tests/contract/test_mission_status_examples.py
- tests/contract/test_enum_pin_check.py
- contracts/mission-status/paths/missions_missionId_artifacts.yaml
- contracts/mission-status/paths/missions_missionId_artifacts_content.yaml
- contracts/mission-status/parameters/ArtifactPath.yaml
- contracts/mission-status/schemas/ArtifactKind.yaml
- contracts/mission-status/schemas/ArtifactEntry.yaml
- contracts/mission-status/schemas/ArtifactListing.yaml
- contracts/mission-status/schemas/ArtifactContent.yaml
- contracts/mission-status/schemas/ArtifactRefusalCode.yaml
- contracts/mission-status/schemas/ArtifactRefusal.yaml
- contracts/mission-status/schemas/ArtifactPath.yaml
- contracts/mission-status/responses/ArtifactPathRefused.yaml
- contracts/mission-status/responses/ArtifactNotFound.yaml
- contracts/mission-status/responses/ArtifactTooLarge.yaml
- contracts/mission-status/responses/ArtifactNotText.yaml
- contracts/mission-status/responses/ArtifactSecretRefused.yaml
- contracts/mission-status/responses/ArtifactUnreadable.yaml
- contracts/mission-status/responses/ArtifactListingUnreadable.yaml
- contracts/mission-status/examples/ArtifactListing.populated.yaml
- contracts/mission-status/examples/ArtifactListing.truncated.yaml
- contracts/mission-status/examples/ArtifactContent.markdown.yaml
- contracts/mission-status/examples/ArtifactContent.redacted.yaml
- contracts/mission-status/examples/ArtifactContent.json.yaml
- contracts/mission-status/examples/ArtifactContent.empty.yaml
- contracts/mission-status/examples/ArtifactRefusal.invalid-artifact-path.yaml
- contracts/mission-status/examples/ArtifactRefusal.not-found.yaml
- contracts/mission-status/examples/ArtifactRefusal.artifact-too-large.yaml
- contracts/mission-status/examples/ArtifactRefusal.artifact-not-text.yaml
- contracts/mission-status/examples/ArtifactRefusal.artifact-secret.yaml
- contracts/mission-status/examples/ArtifactRefusal.artifact-unreadable.yaml
- contracts/mission-status/examples/ArtifactRefusal.artifact-listing-unreadable.yaml
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP03 – Contract slice A: listArtifacts and getArtifactContent

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Add the artifact-read half of the 1.1 contract: `listArtifacts` and `getArtifactContent` with their schemas, the `ArtifactPath` parameter, responses and examples, the version `1.1.0-SNAPSHOT`, the CHANGELOG entry skeleton and the two enum pins.

## Context

Plan IC-03; file set and shapes in `kitty-specs/mission-status-contract-1-1-01M42XJC/contracts/operations-and-schemas.md`. All new files are additive under `contracts/mission-status/` (spec C-001, C-002, CL-1). Depends on WP02 so the extended scanner meets every new file as it is written. Chokepoint: `openapi.yaml`, the four `_index.yaml` files, `CHANGELOG.md` and `enum_pins.json` serialise WP03, WP04 and the final CHANGELOG edit of WP07 (one computed lane, dependency order). The final provisional list is NOT decided here: WP07 takes it from `provisional_check.py`.

Decisions honoured (spec.md, Decisions and Traceability; read `kitty-specs/mission-status-contract-1-1-01M42XJC/spec.md` with this prompt; the rows are `tasks.md`, section Coverage): CL-1, CL-2, CL-3, CL-5; AD-1, AD-2, AD-4, AD-5, AD-6, AD-7, AD-8, AD-9, AD-10, AD-11, AD-14, AD-16, AD-17, AD-19, AD-21, AD-22; AC-LIST, AC-CONTENT, AC-VERSION; OQ-1, OQ-5; OD-2, OD-4.

Plan concern: IC-03 (plan section Implementation Concern Map). Requirement refs: FR-009, FR-010, FR-011, FR-012, FR-013, FR-017, FR-018, FR-019, C-001, C-002, C-004, SC-001. Dependencies: WP02. Branch contract: planning base and merge target are `issue-5625-mission-status-contract-1-1`; work runs in the lane workspace `spec-kitty agent action implement` resolves for you (never reconstruct a path by hand).

## Owned files (write scope)

Edit only these paths (declared shared-file exceptions are dependency chains, never concurrent; plan section Lanes):

- `contracts/mission-status/openapi.yaml`
- `contracts/mission-status/CHANGELOG.md`
- `contracts/mission-status/schemas/_index.yaml`
- `contracts/mission-status/parameters/_index.yaml`
- `contracts/mission-status/responses/_index.yaml`
- `contracts/mission-status/examples/_index.yaml`
- `contracts/tools/enum_pins.json`
- `tests/contract/test_mission_status_examples.py`
- `tests/contract/test_enum_pin_check.py`
- `contracts/mission-status/paths/missions_missionId_artifacts.yaml`
- `contracts/mission-status/paths/missions_missionId_artifacts_content.yaml`
- `contracts/mission-status/parameters/ArtifactPath.yaml`
- `contracts/mission-status/schemas/ArtifactKind.yaml`
- `contracts/mission-status/schemas/ArtifactEntry.yaml`
- `contracts/mission-status/schemas/ArtifactListing.yaml`
- `contracts/mission-status/schemas/ArtifactContent.yaml`
- `contracts/mission-status/schemas/ArtifactRefusalCode.yaml`
- `contracts/mission-status/schemas/ArtifactRefusal.yaml`
- `contracts/mission-status/schemas/ArtifactPath.yaml`
- `contracts/mission-status/responses/ArtifactPathRefused.yaml`
- `contracts/mission-status/responses/ArtifactNotFound.yaml`
- `contracts/mission-status/responses/ArtifactTooLarge.yaml`
- `contracts/mission-status/responses/ArtifactNotText.yaml`
- `contracts/mission-status/responses/ArtifactSecretRefused.yaml`
- `contracts/mission-status/responses/ArtifactUnreadable.yaml`
- `contracts/mission-status/responses/ArtifactListingUnreadable.yaml`
- `contracts/mission-status/examples/ArtifactListing.populated.yaml`
- `contracts/mission-status/examples/ArtifactListing.truncated.yaml`
- `contracts/mission-status/examples/ArtifactContent.markdown.yaml`
- `contracts/mission-status/examples/ArtifactContent.redacted.yaml`
- `contracts/mission-status/examples/ArtifactContent.json.yaml`
- `contracts/mission-status/examples/ArtifactContent.empty.yaml`
- `contracts/mission-status/examples/ArtifactRefusal.invalid-artifact-path.yaml`
- `contracts/mission-status/examples/ArtifactRefusal.not-found.yaml`
- `contracts/mission-status/examples/ArtifactRefusal.artifact-too-large.yaml`
- `contracts/mission-status/examples/ArtifactRefusal.artifact-not-text.yaml`
- `contracts/mission-status/examples/ArtifactRefusal.artifact-secret.yaml`
- `contracts/mission-status/examples/ArtifactRefusal.artifact-unreadable.yaml`
- `contracts/mission-status/examples/ArtifactRefusal.artifact-listing-unreadable.yaml`

30 of these paths do not exist yet on the planning base and are declared in the frontmatter `create_intent` (finalisation refuses a literal path that matches zero files unless it is declared there); you create them.

Nothing under `kitty-specs/` is written by this work package: records you must make (a contract-note refinement, a decision, a friction observation, the baseline) go into your hand-off report; the orchestrator appends them add-only to the tracer files. A small, well-justified out-of-map edit is acceptable only with a one-line rationale in the hand-off report; the no-overlap rule is the real guard against collisions.

### Subtask T011: Red-first: examples, path-map and enum-pin tests for the artifact reads

**Purpose**: First commit: tests that fail until the artifact reads exist.

**Steps**:

1. In `tests/contract/test_mission_status_examples.py`: `EXPECTED_PATH_KEYS` gains the two artifact paths (the file is re-pinned in WP04 to eight), the path-count test and `MIN_EXAMPLES` move, and the in-test required-case manifest (operator decision OD-2 Y: the guard lives in-test, not in `required_examples.json`) gains: every artifact refusal code has an example, both `redacted` values occur, both `readable` values occur, `truncated: true` occurs.
2. Add the third leg of the predicate agreement test (the `ArtifactPath` schema pattern against `malformed_artifact_path` and the literal restatement, over the same 30 cases, restated as data in the examples test: never import one test module from another). Add planted copies through the resolver and the library path: an extra property, a missing property, and an absolute path in an example each fail.
3. In `tests/contract/test_enum_pin_check.py` change the pinned counts line to `enums=5 values=38` (`ArtifactKind` 12 and `ArtifactRefusalCode` 7 added to 3 and 19).
4. Run against the planning base: the new expectations fail. Commit.

**Files**: `tests/contract/test_mission_status_examples.py` (about 90 lines), `tests/contract/test_enum_pin_check.py` (a few lines).

**Validation**: Red on the planning base for the stated reasons.

### Subtask T012: Version 1.1.0-SNAPSHOT, the two path keys and the CHANGELOG entry skeleton

**Purpose**: Version, path keys and the CHANGELOG skeleton.

**Steps**:

1. `openapi.yaml`: `info.version` becomes `1.1.0-SNAPSHOT`; add the two path keys `/missions/{missionId}/artifacts` and `/missions/{missionId}/artifacts/content` to the root map; no new tag; nothing else changes.
2. `CHANGELOG.md`: new top entry `## 1.1.0-SNAPSHOT` with `### Added` for the artifact reads (the two operations, their schemas, parameter, responses; invalid UTF-8 is a 415; the two root status records are no artifacts), `### Changed` and `### Removed` saying `Nothing.`. WP04 appends its detail lines; WP07 finalises Provisional and Deferred.

**Files**: `contracts/mission-status/openapi.yaml`, `contracts/mission-status/CHANGELOG.md`.

**Validation**: `structure_check.py` and `layout_check.py` still pass; `git diff` of `openapi.yaml` shows only the version and two path keys.

### Subtask T013: The seven artifact schemas and the ArtifactPath parameter

**Purpose**: The seven schemas and the parameter, closed, cited, with one x-source or x-derived per property.

**Steps**:

1. Create `ArtifactPath`, `ArtifactKind` (twelve values, the classifier order in the description), `ArtifactEntry`, `ArtifactListing` (`maxItems: 1000`), `ArtifactContent` (`encoding` const `utf-8`), `ArtifactRefusalCode` (seven values), `ArtifactRefusal` (shared `Problem` plus required `code` and one `if`/`then` per code pinning the status 400, 404, 413, 415, 422, 500, 500, built like `StreamRefusal`) as listed in the contract note; `title` equals the file stem, `additionalProperties: false`.
2. `ArtifactPath` pattern: copy the pattern from the contract note, using the hex escape for NUL, never a unicode escape. After writing, check the file for raw NUL bytes.
3. Mark the provisional elements of AD-14: `ArtifactKind`, `ArtifactRefusalCode`, `ArtifactRefusal` (`code`), `ArtifactListing.truncated`, `ArtifactContent.redacted`, via-`kind` references. Citations name symbols, never line numbers (research R-12).
4. `parameters/ArtifactPath.yaml`: query parameter `path`, required, schema `ArtifactPath`.
5. `readable` and the 422 description list the credential kinds by name: GitHub token prefixes (`ghp`, `gho`, `ghu`, `ghs`, `ghr`, fine-grained `github_pat`), AWS access key id prefixes (`AKIA`, `ASIA`) and the header line of a PEM private key (WP07 compares these words with `SECRET_PATTERNS`).

**Files**: Seven files under `schemas/` and one under `parameters/` (about 54 lines per schema).

**Validation**: `leak_scan.py`, `layout_check.py`, `citation_check.py` pass over the tree.

### Subtask T014: The seven responses, the two path files and the index entries

**Purpose**: Responses, the two path files and index entries.

**Steps**:

1. Seven responses (`application/problem+json`; schema `ArtifactRefusal`): `ArtifactPathRefused` (400), `ArtifactNotFound` (404), `ArtifactTooLarge` (413), `ArtifactNotText` (415), `ArtifactSecretRefused` (422), `ArtifactUnreadable` (500, content), `ArtifactListingUnreadable` (500, listing).
2. Path files `paths/missions_missionId_artifacts.yaml` and `paths/missions_missionId_artifacts_content.yaml` (names computed with `contract_resolver.path_file_name`), tagged `Missions`, no security scheme, shared `Problem` as `default`. The content description states the order of decision (400, 404, 413, 500, 415, 422), the 262,144-byte cap, that `path` is decoded once at the HTTP layer, that a symlink is never followed and that the two root status records are not artifacts.
3. New entries only in the `_index.yaml` files of `schemas/`, `parameters/`, `responses/`.

**Files**: Seven files under `responses/`, two under `paths/`, three index files edited.

**Validation**: `layout_check.py` passes; `example_check.py` is run after T015.

### Subtask T015: The thirteen artifact examples and the examples index

**Purpose**: Examples for every new schema and every refusal code, leak-free.

**Steps**:

1. Create the 13 example files named in the contract note (listing populated and truncated; content markdown, redacted, json, empty; the seven refusal examples), plus short inline `examples` on the small leaf schemas.
2. Every example is leak-free: no absolute path, no host path, no address, no credential, no unredacted content; a path in an example satisfies the `ArtifactPath` pattern. **No committed contract example holds an at-sign path** (the scan's acceptance of such a path is proved by the WP02 run-time-built tests and the reader tests; a YAML file cannot be built at run time); examples may carry a `home/<x>/` directory-segment name, a name with a space and a name with an accented letter (AD-19). The `truncated: true` example holds a short list with a comment (a real one holds exactly 1000 entries; plan departure 11).
3. Add the entries to `examples/_index.yaml`.

**Files**: 13 files under `examples/` (about 41 lines each), `examples/_index.yaml`.

**Validation**: `example_check.py --root contracts`, the extended `test_mission_status_examples.py` required cases.

### Subtask T016: Enum pins for ArtifactKind and ArtifactRefusalCode, and the contract checks over the tree

**Purpose**: Pin the enums and run the checks over the finished slice.

**Steps**:

1. `contracts/tools/enum_pins.json`: under `mission-status` add `ArtifactKind` (12 values) and `ArtifactRefusalCode` (7). A pinned title absent from the module exits 2 (`ENUM_UNREADABLE`), so the pins land with their schemas.
2. Run the ten Python checks (quickstart section Python checks), `run_negative_cases.py` with the three exclusion tags, and the targeted tests. T011's tests are now green.
3. Check every new file for raw NUL bytes.

**Files**: `contracts/tools/enum_pins.json` (about 20 lines).

**Validation**: `leak_scan.py`, `example_check.py`, `run_negative_cases.py`, `layout_check.py`, `enum_pin_check.py` exit 0 over the tree.

## Validation: gates and targeted test surface

Charter: no full `tests/architectural/`, end-to-end, performance or `make test-full` sweep in mission work (`NO_FULL_HEAVY_SUITES_IN_MISSION`); run exactly the commands below, record each command and its passed/failed counts in the hand-off report. Use the checkout's own environment (`.venv/bin/...`), never a bare `uv run`. `<scratch>` means a scratch directory outside the repository.

**Targeted test surface of this work package**:

- The ten Python checks of quickstart section Python checks (each `.venv/bin/python contracts/tools/<name>.py --root contracts`; `codeowners_check.py` and `no_pytest_scan.py` need no `--root`).
- `PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_mission_status_examples.py tests/contract/test_enum_pin_check.py tests/contract/test_leak_scan.py tests/contract/test_example_round_trip.py`

**Tool-job selection (the whole `tests/contract` corpus selection; the router job `tests (contract tools)`, step `Run the contract tool unit tests` of `.github/workflows/ci-router.yml`).** This is the job that runs the new test modules and every neighbour of the contract files this Mission changes, so it is part of the targeted surface (a directory-scoped contract run, not an architectural sweep). Verbatim from the workflow (CI-owned form):

```text
uv run --frozen --no-sync pytest -m "corpus and not windows_ci" tests/contract \
  --ignore=tests/contract/test_example_round_trip.py \
  --ignore=tests/contract/test_mission_status_payloads.py \
  --ignore=tests/contract/test_mission_status_reality.py \
  -n 4 --dist loadfile
```

Runnable as written here (the checkout's interpreter, no `uv run`; the same arguments):

```text
PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -m "corpus and not windows_ci" tests/contract \
  --ignore=tests/contract/test_example_round_trip.py \
  --ignore=tests/contract/test_mission_status_payloads.py \
  --ignore=tests/contract/test_mission_status_reality.py \
  -n 4 --dist loadfile -q
```

Record the passed and skipped counts in the hand-off report and compare them with the Mission baseline (1,016 passed and 37 skipped at the plan fix; the WP01 T001 table in `tracer-approach.md` is the authoritative comparison, and the counts rise by the tests this Mission adds).

**Gates every code work package passes before hand-off** (baselines at the plan fix: 368 passed and 1 skipped; 171 passed; 83 passed; ruff clean; TID251 clean):

1. Router, registry and hygiene gate files, ruff and cutover guard:

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/ci/test_contracts_workflows.py tests/ci/test_contracts_routing.py tests/ci/test_corpus_blocking_home.py \
  tests/architectural/test_ci_corpus_trigger_completeness.py tests/architectural/test_same_tier_uniqueness.py \
  tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_module_shard_registry.py \
  tests/architectural/test_workflow_coherence.py tests/architectural/test_no_legacy_terminology.py
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/spec-kitty cutover-guard --base-ref origin/main
```

2. Architectural files that census `tests/` (real-git fixtures, worktrees, git identity setup, `os.chdir`/`os.environ`/`sys.path` changes in a new test module are what they inspect; no allowlist or baseline entry may be added to make a module pass: use `monkeypatch` and a scratch HOME). Run after every new or edited test module:

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/architectural/test_no_manual_global_state_mutation.py tests/architectural/test_global_state_allowlist_sealed.py \
  tests/architectural/test_spec_kitty_home_pin_census.py tests/architectural/test_spec_kitty_home_pin_guard.py \
  tests/architectural/test_spec_kitty_home_pin_budget.py tests/architectural/test_home_pin_gate_verdict.py \
  tests/architectural/test_no_dead_symbols.py tests/architectural/test_dead_symbol_allowlist_contract.py
```

3. Layer rules and import boundaries:

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/architectural/test_layer_rules.py tests/architectural/test_pyproject_shape.py
.venv/bin/ruff check --select TID251 .
```

4. Per-file format check where useful: `.venv/bin/ruff format --check --force-exclude <files>`.

## Red-first rule (C-011, charter ATDD-First Discipline)

The FIRST commit of this work package is its failing test or planted fixture, red on the planning base (the lane's base before your first commit), committed BEFORE any implementation commit. Verify the red and record the failing test ids and the reason in the hand-off report: run the test file against the base by extracting the base into a scratch directory (`git archive <base-commit> | tar -x -C <scratch>/base`, copy the new test file in, run pytest from that directory with the checkout's interpreter); do not use `git stash`. The reviewer verifies red then green: red on the planning base AND green on the final commit. Declared exceptions are named in the subtasks (the behaviour-preserving campsite commit, the three regression-control leak kinds, the old-kind digest test). Never weaken, skip or retry-to-green a test to pass.

## Baseline rule: pre-existing red versus introduced red

Before your first change, run this work package's targeted commands once on the unchanged lane base. Any red is binned before work continues: (1) pre-existing known-P0 red on `main` (leave it red, never green-wash), (2) CI-environment failure (auth, opt-out variables; passes locally), (3) stale install, (4) stale venv (re-run `uv sync --frozen --all-extras`, then retry), or (5) introduced by you. Only a red that is red on your branch AND green on the base is yours to fix. A pre-existing red: STOP and report to the orchestrator in your hand-off (command, failure summary, why you believe it is pre-existing); the orchestrator owns the tracker issue (Pre-existing Failure Reporting Rule). Do not open an issue or post a comment yourself, do not absorb it, do not retry until green.

**Comparison base.** The Mission baseline is the planning-base commit and the counts recorded by WP01 T001, appended add-only to `tracer-approach.md` by the orchestrator. Your lane base already holds the commits of earlier work packages, so "green on the base" alone does not make a red pre-existing. Reconcile your own pre-change run with the WP01 table for the same command and explain any difference. A red that is red on your lane base but green at the Mission baseline was introduced by an earlier work package of this Mission: report it with the work package it belongs to; do not bin it as pre-existing (bin 1).

## Git, commits and public-repo hygiene

- **Commit locally. NEVER push, never open a pull request, never comment on an issue, never merge.** One pull request per Mission is opened by the orchestrator after the wrap-up sequence.
- Conventional commit subjects ending with `(#5625)`; end each commit message with the attribution trailers the orchestrator supplies. Commit through `spec-kitty safe-commit` where a guarded branch requires it; never bypass a guard with raw git or an environment override.
- **This repository is PUBLIC**: everything you write ships visibly and permanently. No absolute path under a home directory and no drive path, no user name, no e-mail address, no private reference, no credential in any file, test, fixture, commit message or report. Use repo-relative paths and placeholders such as `<repo>`, `<scratch>`, `<user>`. A username-leak is folded before anything leaves the machine; report any you find.
- Leaking values a test needs (host paths, addresses, tokens, an at-sign file name) are assembled from fragments at run time and never typed as literals. Editing tools decode a unicode escape typed into a file into the raw character: write NUL as `chr(0)` and backslash as `chr(92)` in tests, use the hex escape in contract patterns, and check every new file for raw NUL bytes.
- Terminology: Mission, never feature; say which sense of lane (status lane versus code lane); no `--feature` flag text. New code passes `ruff check` and `ruff format --check` with no suppression added; complexity ceiling 15; literals used three or more times in a module become constants.
- `kitty-specs/` is archive-frozen on `main`: this Mission's own files are add-only on the branch. Never hand-edit `meta.json`, `status.events.jsonl`, `lanes.json` or work package frontmatter; never call `materialize`. Never run a pattern kill (`pkill`/`killall`), `git stash`, or `rm` with a variable glob.
- **Subagents dispatch nothing**: you work alone; do not start, fork or brief other agents. A denied command means STOP and report it; never retry a denied command.

## Hand-off report (your final message)

Commits (hash and subject, in order, first commit marked as the red-first commit), the red evidence (failing ids, reason, how it was verified on the base), every command run with passed/failed counts, baseline bins, any refinement of a contract note or design decision, any friction observation (for `tracer-tooling-friction.md`), anything not done and why. The orchestrator records decisions and friction add-only; you do not write them under `kitty-specs/`.

## Definition of Done

- First commit: red tests (T011); version, two path keys, 7 schemas, parameter, 7 responses, 2 path files, 13 examples, index entries, pins.
- `1.1.0-SNAPSHOT`; `git diff` of existing files shows only the allowed edits (version, path keys, index entries, CHANGELOG entry, pins).
- Leak scan, example check, negative cases, layout check and enum-pin check green over the tree; no raw NUL byte; no leaking literal.
- Hand-off report lists any refinement of the contract note (the orchestrator records it in `tracer-design-decisions.md`).
- Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- Nothing pushed; no pull request; no tracker write.

## Risks

- The `ArtifactPath` pattern: a unicode escape becomes a raw NUL; use the hex escape and verify.
- `provisional_check` is word-satisfied by older entries (friction F-4): do not finalise the provisional list here.
- A schema property without exactly one `x-source` or `x-derived` fails the citation check.

## Reviewer Guidance

The reviewer is a separate role from the implementer. Review the diff of this work package against its owned files and its full targeted test surface (every file the change touches), plus the specific named architectural gate files it implicates; never a full sweep.

- Verify red then green for T011; check the planted copies fail through the resolver and the library path.
- Diff against the planning base: nothing under `contracts/mission-status/` that existed changes except the listed edits (byte identity of every other file).
- Run the leak scan and check no example or description holds a host path, address or credential; check closed schemas and pinned status pairing.
- Verify the first commit is the red-first commit and that it is red on the planning base; verify green on the final commit; check the baseline bins in the hand-off.
- Check public hygiene: no absolute path, user name, address, credential or private detail in any added line or commit message; no leaking literal.

## Wrap-up reference (orchestrator-owned, NOT part of this work package)

After every work package is approved the orchestrator runs plan steps W-1 to W-7 in this order: W-1 accept, then lane consolidation (`spec-kitty consolidate`, strategy `rebase` recommended), then registration and wiring check, scripted scope check and issue-matrix rows; W-2 JVM shake-out; W-3 dev-assist cleanup; W-4 aggregate adversarial squad (report-only, pre-rebase tree); W-5 history compaction; W-6 rebase onto upstream including the 1.0.0 release commit; W-7 final evidence. Only then is the draft pull request opened, and it needs the `contract-mission-status-v1.0.0` tag. Evidence recorded earlier is labelled pre-tag or pre-rebase. You do none of this.

## Implementation command

`spec-kitty agent action implement WP03 --agent claude`
