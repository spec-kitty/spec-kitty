---
work_package_id: WP03
title: Vocabularies, project and Mission overview resources (IC-02)
dependencies:
- WP02
requirement_refs:
- FR-003
- FR-004
- FR-008
- FR-009
- FR-010
- FR-011
- FR-013
- FR-024
- C-006
- C-007
- C-010
- SC-001
- SC-004
planning_base_branch: issue-5558-mission-status-contract-v1
merge_target_branch: issue-5558-mission-status-contract-v1
branch_strategy: Planning artifacts for this mission were generated on issue-5558-mission-status-contract-v1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5558-mission-status-contract-v1 unless the human explicitly redirects the landing branch.
subtasks:
- T016
- T017
- T018
- T019
- T020
- T021
- T022
history: []
agent_profile: implementer-ivan
authoritative_surface: contracts/mission-status/
create_intent:
- contracts/mission-status/openapi.yaml
- contracts/mission-status/CHANGELOG.md
- contracts/mission-status/paths/project.yaml
- contracts/mission-status/paths/missions.yaml
- tests/contract/test_mission_status_examples.py
- contracts/tools/contract_resolver.py
- tests/contract/test_contract_resolver.py
execution_mode: code_change
model: sonnet
owned_files:
- contracts/mission-status/openapi.yaml
- contracts/mission-status/CHANGELOG.md
- contracts/mission-status/paths/project.yaml
- contracts/mission-status/paths/missions.yaml
- contracts/mission-status/schemas/**
- contracts/mission-status/parameters/**
- contracts/mission-status/responses/**
- contracts/mission-status/examples/**
- tests/contract/test_mission_status_examples.py
- tests/architectural/test_ci_corpus_trigger_completeness.py
- contracts/tools/contract_resolver.py
- tests/contract/test_contract_resolver.py
- contracts/tools/fixtures/contract_resolver/**
role: implementer
tags: []
tracker_refs: []
---

# WP03 - Vocabularies, project and Mission overview resources (IC-02)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Create the `contracts/mission-status/` module skeleton and its first two resources, `GET /project` and `GET /missions`, with the three fixed vocabularies, closed schemas, cited properties and validating examples.

## Context

- Plan concern **IC-02**. First of the three **sequential content WPs** (WP03, WP04, WP05). They are serialised by dependencies because the **contract root map** (`openapi.yaml` path-to-file map), every `_index.yaml` and the path files are append-only chokepoints: concurrent edits would conflict (plan Branch contract exception 2). WP03 creates them; WP04 and WP05 append.
- No `src/` change (C-002). Contract and examples only. **Does not touch** the migration chain, runtime-state schema, event contract implementation, or a shared CI gate (one registry row append in `tests/architectural/test_ci_corpus_trigger_completeness.py` for the new examples test module; the registry file is a declared append-only shared file owned here for that one row).
- Binding sources: `spec.md` CL-5, CL-7, CL-8, D-1 to D-5, D-11, D-13, FR-003, FR-004, FR-008, FR-009, FR-010, FR-011, FR-013, FR-024 and the "Contract Field Catalogue" (Project and Mission overview tables); `data-model.md` (vocabularies, derivation rules, projection rules); `plan.md` section (l) "Dashboard references re-verified" **governs where it differs from the spec** (scanner.py is gone; derivations become `x-derived` with the rule in the schema description; `friendlyName` cites `MissionMetaRequired` in `specify_cli/mission_metadata.py`; `acceptedAt`/`mergedAt`/`discardedAt` citations as corrected there; `discardedAt` names the raw meta mapping from `load_meta` and the `discarded_at` key).
- Naming rules: status-lane stem `statusLane` (`statusLane`, `statusLaneCounts`, `fromStatusLane`, `toStatusLane`), enum `StatusLane`; never the bare `lane` stem (D-1). Path files: `/` becomes `_`, `{param}` kept (`missions.yaml`, `project.yaml` here). Relative file `$ref` only; the root maps path items to files; no URL, absolute or `~1` refs. Brace-named files are WP04's; use the `BRACE_REF_SPELLING` constant's value if you reference one.
- Response object schemas are closed (`additionalProperties: false`, or `unevaluatedProperties: false` where composed); open maps only where documented. Every property is described and carries `x-source` (repo-relative file path plus symbol) or structured `x-derived` (`{rule: <non-empty prose>, inputs: [<non-empty list>]}`; inputs are code citations or contract-field property paths). Never cite a path `git ls-files` does not list on the branch tip; verify every cited symbol by reading the file (defined name via `def`, `class`, assignment or annotated target).
- **Preview point (partial)**: the last commit of this WP is an "earlier partial point" (project header and Mission list usable by a UI team, unvalidated). The plan defines no tag name for partial points, only `p0`, `p1`, `p2`; no tag is created for it unless the orchestrator decides otherwise. Record the commit hash in the hand-off.
- Baseline: judge against WP01's baseline hand-off (recorded by the orchestrator in `research.md` R-8).
- **Precondition (verify read-only, stop and report if absent):** the IC-07a record (WP02's orchestrator record step) is committed: `git show <target-branch>:kitty-specs/mission-status-contract-v1-01M3WC5X/research.md` contains the dated sentence "IC-07a complete". It fixes the canonical brace `$ref` spelling that WP04 will use.
- **Open-PR overlap check (2026-10-02)**: #5540 and #5326 touch none of this WP's files. Re-check at start.
- Red-first (C-010): the first commit is a failing examples test and a planted malformed `date-time` example; the contract makes it green.
- Terminology: Mission, never feature; examples and descriptions follow the same rule. No absolute host path, e-mail address, credential or private-discussion reference anywhere (C-006). Example actors are handles such as `claude`, `implementer`, never person names or addresses.

### Test surface, gates and baseline

- Targeted: `tests/contract/test_mission_status_examples.py`, and the already-landed `tests/contract/test_layout_check.py` plus a local run of `.venv/bin/python contracts/tools/layout_check.py --root contracts` (WP01 tool) which must exit 0 once the module exists and its index files are consistent.
- Named gates: `tests/architectural/test_ci_corpus_trigger_completeness.py`, `tests/architectural/test_workflow_coherence.py` (router globs must match a tracked path; `contracts/**` now does). No architectural directory sweep.

## Subtasks

### Subtask T022: Failing examples test with a planted malformed timestamp

**Purpose**: red-first harness for every example (also the basis of preview claim "every example validates").

**Steps**:
1. Create `tests/contract/test_mission_status_examples.py` (single-line `pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]`; append a sorted registry row). Load the contract through `contract_resolver` (import by file path with `importlib.util`), enumerate examples from a directory listing of `contracts/mission-status/examples/` (no hard-coded names), validate each against the schema that references it with `jsonschema` using `schema_formats.FORMAT_CHECKER`.
2. Assert a minimum number of examples validated before asserting properties (FR-025). Add a planted malformed `date-time` example case that must be rejected both through the resolver path and through an independent library path (`jsonschema` with a `referencing.Registry` retrieving the split files); the same verdict whether or not `rfc3339-validator` is importable (D-P14).
3. Red because there is no module yet.

**Files**: test module (~180 lines).
**Validation**: test fails on the base for the right reason (no module), passes after T019.

### Subtask T020: Vocabularies and shared-style schemas

**Purpose**: FR-008, FR-009.

**Steps**:
1. `schemas/StatusLane.yaml`: nine values exactly (planned, claimed, in_progress, for_review, in_review, approved, done, blocked, canceled); cite `Lane` in `src/specify_cli/status/models.py`; neither `genesis` nor `uninitialized` is a value.
2. `schemas/LifecycleStatus.yaml` (active, planned, done, draft, discarded), `schemas/Topology.yaml` (lanes, single_branch, coord, lanes_with_coord, unknown; description states it is the stored `meta.json` shape and unrelated to `MissionStatus.topology`), `schemas/ActorHandle.yaml` (nullable string, pattern letters, digits, `.`, `_`, `:`, `-`, max 128, no `@`, `/`, whitespace; D-10), `schemas/MissionId.yaml` (pattern `^[0-9A-HJKMNP-TV-Z]{26}$`, citing the ULID pattern in `src/specify_cli/status/models.py`), `schemas/StreamCursor.yaml` (`offset` integer, `invariant` 64 hex characters; cites `TailCursor` and its `content_invariant` attribute in `src/specify_cli/status/tail_reader.py`; no `$ref` relationship to the shared page cursor, FR-009 of the plan test table), `_index.yaml` listing every file.
3. No `columns` or board-grouping schema anywhere; the README (WP11) documents the board mapping as a consumer convention.

**Files**: ~7 YAML files (~25 lines each) plus `_index.yaml`.
**Validation**: `layout_check` passes on the directory; enum values match exactly.

### Subtask T021: `Project` resource

**Purpose**: FR-003.

**Steps**:
1. `schemas/Project.yaml`: `name` (string, cited to `.kittify/config.yaml` key `project.slug` and `ProjectIdentity` in `src/specify_cli/identity/project.py`) and `missionCount` (integer, `x-derived`: rule "number of overview records, that is of Missions the service lists", inputs a contract-field reference to the overview list). No project path, worktree path or token fields. Closed schema.
2. `paths/project.yaml`: `GET /project`, `operationId`, tag, 200 with `Project`, error responses via the shared `Problem` response only.
3. `examples/project.yaml` (or the naming scheme `layout_check` enforces), referenced by the response.

**Validation**: example validates; `missionCount` description states the definition.

### Subtask T022: `MissionOverview` schema and progress, with citations

**Purpose**: FR-004 field catalogue, FR-010.

**Steps**:
1. `schemas/MissionOverview.yaml` with exactly the catalogue fields: `missionId`, `mid8` (nullable, never empty string), `slug`, `friendlyName`, `displayNumber` (nullable, display-only, described as not unique), `missionType` (nullable open string), `targetBranch`, `topology`, `createdAt`, `statusLaneCounts` (object with the nine keys all required, integers, none grouped), `wpTotal` (definition D-4: `len(snapshot.work_packages)`, may differ from the number of `tasks/WP*.md` files), `blockedCount` (`x-derived`), `progress` (`weightedPercentage`, `donePercentage`, `doneCount`, `semantics` const `weighted_readiness`), `lifecycleStatus` (`x-derived`, rule D-5 written in the description, inputs `statusLaneCounts`, `wpTotal`, `discardedAt`, `acceptedAt`; pin the two quirks in the description), `acceptedAt`, `mergedAt`, `discardedAt` (nullable `date-time`), `lastEventId`, `lastActivityAt` (`x-derived`, max work package last transition), `eventCount`, `streamCursor`, `nextAction` (nullable string, `x-provisional: true`, `x-derived`, description naming the open decision on #5528; the two prose strings are described, both embed the Mission slug).
2. Citations: every property cites a surviving symbol. Verify each by opening the file: `specify_cli/mission_metadata.py` (`load_meta`, `MissionMetaRequired`, `MissionMetaOptional`, `record_acceptance`, `record_discard`), `mission_runtime/identity.py` (`resolve_mid8`), `specify_cli/status/models.py` (`StatusSnapshot`), `specify_cli/status/progress.py` (`compute_weighted_progress`, `ProgressResult`), `specify_cli/consolidation/baseline.py` (`record_baseline_merge_commit`). A derivation whose only implementation lived in the removed dashboard is `x-derived` with no `x-source` to the removed file.
3. Provisional fields are nullable, and `x-provisional` descriptions say what is undecided.

**Files**: `MissionOverview.yaml` (~220 lines), `MissionProgress.yaml`, `StatusLaneCounts.yaml`.
**Validation**: schema parses through the resolver; every property has a citation (WP06's `citation_check` will enforce on the real tree later; until it lands, count by hand and record the count).

### Subtask T020: `GET /missions` path, pagination and ordering

**Purpose**: FR-004 ordering and paging.

**Steps**:
1. `paths/missions.yaml`: `GET /missions`, shared page parameters from `_shared`, 200 body a closed `MissionOverviewPage` (items plus `PageInfo` from `_shared`). The operation description names the sort key `createdAt` descending, ties broken by `missionId` ascending (a total key), and states pagination uses the shared opaque page cursor.
2. Query parameters live in `parameters/`; error responses reference the shared `Problem` response only.

**Validation**: layout check passes; description names both sort keys (the reality check in WP10 asserts strict ordering).

### Subtask T021: Examples for project and overview, including list pages

**Purpose**: FR-013 examples that exercise nullable and provisional branches.

**Steps**:
1. Examples: a project example; an overview example with a populated Mission; an overview with `displayNumber` null, `topology` `unknown`, `mid8` null; a populated provisional example (`nextAction` non-null) and a discarded-Mission example (`lifecycleStatus` `discarded` with `discardedAt`); list-page examples for first page, a middle page and the exhausted cursor.
2. No example contains an absolute path, e-mail address or person name; use placeholder slugs such as `example-mission-01ABCDEF`.

**Validation**: all validate in the examples test; every example is referenced by a schema or response (orphans fail later in `example_check`).

### Subtask T022: Root map, info, CHANGELOG and registry row

**Purpose**: module skeleton, FR-024 initial entry.

**Steps**:
1. `openapi.yaml`: OpenAPI 3.1, `info.version` `1.0.0`, `servers` with the `/api/v1` prefix, tags, and a path-to-file map only (the two paths of this WP; WP04 and WP05 append). No component definitions inline.
2. `CHANGELOG.md`: headings for added, changed, removed, provisional, and a heading for the module's current version `1.0.0` with the initial entry (American spelling; the changelog-style checker is for `docs/changelog/CHANGELOG.md` but keep the same house shape).
3. Append the registry row for `tests/contract/test_mission_status_examples.py` (sorted).
4. Run the targeted commands; record counts.

**Validation**: examples test green; `layout_check` exits 0 on the real tree; registry gate green.

## Definition of Done

- Module skeleton exists; `GET /project` and `GET /missions` defined; vocabularies exact; schemas closed; 100 percent of resource properties carry `x-source` or structured `x-derived` (hand-counted until WP06; count recorded in the hand-off).
- Examples test red first, then green, including the planted malformed-timestamp rejection through both resolution paths.
- `layout_check` over the real `contracts/` exits 0; `contracts/_shared/` untouched except by reference.
- Registry row appended in sorted order; the two named architectural gates green.
- No `src/` change; no absolute path or e-mail in any file.
- Per-subtask completion recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Risks

- Citing a symbol that exists only in a comment or string (the citation check will fail loudly): read the file before citing.
- Root map and index conflicts: this WP is serialised ahead of WP04 and WP05, which only append.
- Making a field optional or nullable later is breaking for generated clients (DD-15): decide nullability carefully now; later changes are logged under a `Pre-release shape change` heading in the module CHANGELOG.

## Reviewer Guidance

Check every cited path against `git ls-files` and every symbol against the file. Check closed schemas, the exact vocabularies, the sort-key text, the absence of board grouping and of any leak-shaped value. Verify the examples test failed first. Confirm `lifecycleStatus` and `nextAction` carry the rules and markers described, and that nothing in the contract uses the bare word lane or the word feature.

Implementation command: `spec-kitty agent action implement WP03 --agent claude`
