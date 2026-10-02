---
work_package_id: WP04
title: Mission detail and work package resources (IC-03)
dependencies:
- WP03
requirement_refs:
- FR-005
- FR-006
- FR-009
- FR-010
- FR-011
- FR-012
- FR-013
- C-007
- C-010
- SC-001
- SC-004
planning_base_branch: issue-5558-mission-status-contract-v1
merge_target_branch: issue-5558-mission-status-contract-v1
branch_strategy: Planning artifacts for this mission were generated on issue-5558-mission-status-contract-v1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5558-mission-status-contract-v1 unless the human explicitly redirects the landing branch.
subtasks:
- T023
- T024
- T025
- T026
- T027
- T028
history: []
agent_profile: implementer-ivan
authoritative_surface: contracts/mission-status/
create_intent:
- contracts/mission-status/openapi.yaml
- contracts/mission-status/CHANGELOG.md
- tests/contract/test_mission_status_examples.py
- contracts/tools/contract_resolver.py
- tests/contract/test_contract_resolver.py
execution_mode: code_change
model: sonnet
owned_files:
- contracts/mission-status/openapi.yaml
- contracts/mission-status/CHANGELOG.md
- contracts/mission-status/paths/missions_*.yaml
- contracts/mission-status/schemas/**
- contracts/mission-status/parameters/**
- contracts/mission-status/responses/**
- contracts/mission-status/examples/**
- tests/contract/test_mission_status_examples.py
- contracts/tools/contract_resolver.py
- tests/contract/test_contract_resolver.py
- contracts/tools/fixtures/contract_resolver/**
role: implementer
tags: []
tracker_refs: []
---

# WP04 - Mission detail and work package resources (IC-03)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Add `GET /missions/{missionId}` (overview plus the five Mission phases and work package summaries) and `GET /missions/{missionId}/work-packages/{wpId}` (authored plan, resolved state, review evidence, readiness, history; prompt body only on request), with schemas, parameters, examples and citations.

## Context

- Plan concern **IC-03**, second of the sequential content WPs (WP03, then WP04, then WP05). It appends to the root map, the `_index.yaml` files and the module CHANGELOG written by WP03; it never reorders or rewrites WP03's entries. No registry row is needed (the examples test module already has its row); if you add a new corpus-marked module, add its row (the registry file is owned by the WPs that add corpus-marked modules; this WP does not own it, so make that a one-line recorded out-of-map edit, or avoid adding a module).
- **Brace spelling.** This WP creates the first brace-named path files: `missions_{missionId}.yaml` and `missions_{missionId}_work-packages_{wpId}.yaml` (names derived from the path with `/` to `_` and `{param}` kept). References to them use the value of `BRACE_REF_SPELLING` in `contracts/tools/contract_resolver.py` (provisional default: percent-encoded `%7B`/`%7D`). The IC-07a spike (WP02) runs before this WP in the lane and its result is recorded in `research.md` R-3 by the orchestrator, so **use the recorded spelling now** (verify read-only with `git show <target-branch>:kitty-specs/mission-status-contract-v1-01M3WC5X/research.md`; stop and report if neither the "IC-07a complete" sentence nor the dated time-box fallback sentence "IC-07a pending, default spelling provisional" is present; under the fallback use the default spelling provisionally and expect WP09's re-sweep if the spike later records another), set `BRACE_REF_SPELLING` accordingly in `contracts/tools/contract_resolver.py` (this WP owns the file after WP01) with a red-first change, and no sweep is then needed. WP09 keeps the conditional re-sweep only as a safety net should the spelling change after this WP; your tests and fixtures derive file names from a directory listing and the constant, never hard-code them.
- Binding sources: `spec.md` FR-005, FR-006, FR-009, FR-010, FR-011, FR-012, FR-013, D-1 to D-6, D-8, D-10, D-14 and the Field Catalogue (Mission detail, Work package); `data-model.md` (derivation rules, projection rules, field classes); `plan.md` section (l), which governs over the spec for citations (notably `subtaskProgress` cites `ResolvedGroup.subtasks` reached as `WPView.resolved.subtasks`; `WPView` has no `subtasks` attribute; `AuthoredGroup.subtasks` is not used; `discardedAt` is not declared in either meta TypedDict).
- The prompt body parameter and the `x-derived` phase rules are the review-heavy parts. No property named `promptPath`, `prompt_path`, `feedback_path`, `record_path`, `feature_dir`, `worktree`/`project_path` or their camel-case forms exists anywhere (FR-012).
- Resolved state (status lane, assignment, actor) is read from the status snapshot, not from stale frontmatter keys (`agent`, `shell_pid`, `lane`, `assignee`, `review_status`); the schema descriptions say so, and WP10's equality assertion enforces it.
- History lists status transitions only (`kind` is the single value `transition`); annotation and lifecycle rows never appear. `reason` is a human-text field (D-14).
- Baseline, overlap, hygiene, terminology and red-first rules: as in WP03. **Open-PR overlap check (2026-10-02)**: #5540 and #5326 touch none of this WP's files.
- Does not touch the migration chain, runtime-state schema, event contract implementation or a shared CI gate.
- **Python hygiene (binding for this WP)**: this WP edits `tests/contract/test_mission_status_examples.py`, so run `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .` before the final commit and record both results (NFR-007). In `tests/`, never import `datetime` and never call `datetime.now()` or `time.time()` (clock-ban gates, named below): compare ISO-8601 strings or use the kernel clock door.
- **Preview point (partial)**: the last commit of this WP is an "earlier partial point" (Mission page and work package page, unvalidated). No tag is created for it unless the orchestrator decides; record the commit hash in the hand-off.

### Test surface, gates and baseline

- Targeted: `tests/contract/test_mission_status_examples.py` (extended), `tests/contract/test_contract_resolver.py` (this WP changes the resolver's `BRACE_REF_SPELLING`), `.venv/bin/python contracts/tools/layout_check.py --root contracts`, `tests/contract/test_layout_check.py`.
- Named gates: `tests/architectural/test_clock_import_ban.py tests/architectural/test_clock_call_ban.py`, `tests/architectural/test_ci_corpus_trigger_completeness.py`, `tests/architectural/test_workflow_coherence.py`. No directory sweep.

## Subtasks

### Subtask T023: Extend the examples test red-first

**Purpose**: each new resource gets its failing example case before the contract exists.

**Steps**:
1. In `tests/contract/test_mission_status_examples.py` add cases that require: one example per new resource (Mission detail; work package without `promptMarkdown`; work package with `promptMarkdown` requested), a populated provisional work package example (staleness non-null), and negative cases: a phase entry without `basis` fails; an `implement` or `review` entry with basis `artifact` fails; a `history` entry with `kind` other than `transition` fails; a work package example carrying a `promptPath` property fails (closed schema).
2. FR-009 schema tests in the same file (red first, each with a planted violating schema and a floor on what was found): (a) walking the resolved tree, the transitive `$ref` closures of `PageCursor` and `StreamCursor` are disjoint; (b) every path parameter named `missionId` carries the ULID pattern and no path parameter is named `displayNumber`, with a floor on path parameters found. Name the test ids in the Definition of Done.
3. Names come from a directory listing; counts asserted before properties.

**Files**: `tests/contract/test_mission_status_examples.py` additions (~120 lines).
**Validation**: red on the WP03 tree.

### Subtask T024: Mission detail schema and phases

**Purpose**: FR-005.

**Steps**:
1. `schemas/MissionDetail.yaml`: `allOf` the overview plus `phases` and `workPackages` (use `unevaluatedProperties: false` where composed so the schema stays closed; if the resolver or bundler cannot handle it, restructure rather than open the schema, and note the decision in the hand-off).
2. `schemas/MissionPhase.yaml`: `name` (specify, plan, tasks, implement, review), `status` (pending, in_progress, complete), `basis` (artifact, lifecycle_event, derived_from_status_lanes). `phases` is exactly five entries (`minItems`/`maxItems` 5), `x-derived` with the rules of FR-005 written in the description: specify/plan/tasks from `spec.md`/`plan.md`/`tasks.md` presence, else the matching Completed lifecycle event, else Started, else pending; implement and review derived from `statusLaneCounts` in the stated order (implement before review). Inputs: the six marker constants `SPECIFY_STARTED`, `SPECIFY_COMPLETED`, `PLAN_STARTED`, `PLAN_COMPLETED`, `TASKS_STARTED`, `TASKS_COMPLETED` in `specify_cli/status/lifecycle_events.py` (verify they exist) plus contract-field references. Description says "Mission phase is not the glossary `phase`".
3. `schemas/WorkPackageSummary.yaml`: identifier, title, `phaseLabel`, `statusLane` (nullable), `dependencies`, `readiness`, `readyToStart`, `subtaskProgress`, `lastTransitionAt`; never the prompt body.

**Files**: three schemas (~60 to 150 lines each).
**Validation**: negative cases from T023 now fail for the intended reason.

### Subtask T025: Work package detail schema

**Purpose**: FR-006, field catalogue.

**Steps**:
1. `schemas/WorkPackage.yaml` with the catalogue fields: `wpId`, `title`, `phaseLabel`, `authored` (`role`, `agentProfile`, `model`, `subtasks`), `ownedFiles`, `dependencies`, `requirementRefs`, `executionMode`, `taskType`, `priority`, `mergeTargetBranch`, `trackerRefs`, `statusLane`, `assignment` (agent, assignee, role, agentProfile, agentProfileVersion, model, provider; handle strings, sentinels to null), `subtasks` (open map subtask id to `StatusLane`, the documented exception), `subtaskProgress`, `implementerOfRecord`, `lastTransitionAt`, `forceCount`, `lastEventId`, `actor` (`tool`, `role`, `profile` handles; `model` is not part of the actor), `cancellation`, `readiness` (`satisfied`, `unsatisfied`), `readyToStart` (`x-derived`: true only when `statusLane` is `planned` and readiness satisfied; false otherwise including null), `review` (`latestResult` with reviewer handle, verdict `approved`/`changes_requested`, reference; `override` with at, actor, reason; never `feedback_path`), `history` (entries: eventId, at, `kind` const `transition`, fromStatusLane, toStatusLane, actor, force, reason, reviewVerdict), `staleness` (`x-provisional`, nullable: status fresh/stale/not_applicable, reason, minutesSinceCommit), `promptMarkdown` (nullable, on request only, described as authored markdown excluded from corpus scans but scanned in `examples/`).
2. Citations per `plan.md` section (l) and the catalogue: `specify_cli/status/wp_metadata.py` (`WPMetadata`, `read_authored_wp_frontmatter`), `specify_cli/status/wp_view.py` (`reconstruct_wp_view`, `WPView`, `ResolvedGroup`, `AuthoredGroup`), `specify_cli/status/reducer.py`, `specify_cli/status/wp_review.py`, `specify_cli/core/dependency_graph.py` (`dependency_readiness_for_wp`), `specify_cli/core/stale_detection.py` (`StaleState`), `specify_cli/status/models.py` (`StatusEvent`, `decode_actor`, `actor_identity_str`). Read each file and cite only symbols that exist; line numbers optional.
3. Nullable fields and sentinel handling are described (model sentinel `__resolved_model_absent__` projects to null).

**Files**: `WorkPackage.yaml` (~400 lines across it and small sub-schemas such as `Assignment.yaml`, `Review.yaml`, `HistoryEntry.yaml`, `Staleness.yaml`).
**Validation**: schema resolves; every property cited (hand-count recorded).

### Subtask T026: Paths and parameters

**Purpose**: FR-005, FR-006, FR-009 path rules.

**Steps**:
0. Red first, in `tests/contract/test_contract_resolver.py` with a golden tree under `contracts/tools/fixtures/contract_resolver/`: a case that resolves a brace-named file through the recorded spelling and fails against the unchanged `BRACE_REF_SPELLING`; then set the constant in `contracts/tools/contract_resolver.py` (see Context) and turn it green.
1. `paths/missions_{missionId}.yaml` and `paths/missions_{missionId}_work-packages_{wpId}.yaml` (or the recorded spelling); path parameters `missionId` (ULID pattern, the only identifier accepted; `displayNumber` is accepted nowhere) and `wpId` in `parameters/`; the optional boolean query parameter that requests the prompt body (`includePrompt`, description states the default is absent and the response omits `promptMarkdown`).
2. Append both path items to the root map in `openapi.yaml` and to every affected `_index.yaml`; do not reorder existing entries. All non-2xx responses reference the shared `Problem` response (404 for unknown Mission or work package).

**Files**: `contracts/mission-status/paths/missions_*.yaml` (two new path files), `contracts/mission-status/parameters/**`, `contracts/mission-status/openapi.yaml` (append), `contracts/mission-status/**/_index.yaml` (append), `contracts/tools/contract_resolver.py` (`BRACE_REF_SPELLING`), `tests/contract/test_contract_resolver.py`, `contracts/tools/fixtures/contract_resolver/**`.
**Validation**: `layout_check` over the real tree exits 0 (no orphan path file, names match the rule, indices consistent).

### Subtask T027: Examples

**Purpose**: FR-013, FR-011.

**Steps**:
1. Examples: Mission detail with all five phases (one per basis kind); work package without the prompt body; work package with `promptMarkdown` (authored markdown that contains no host path or e-mail address, since examples are scanned); populated provisional staleness example; a work package with null `statusLane` (event-less); one example per actor source form (structured, plain handle string, e-mail source projected to all-null) per D-10; cancellation and review override populated.
2. Reference each from its response so none is orphaned.

**Files**: `contracts/mission-status/examples/**` (about 10 example files), `contracts/mission-status/responses/**` where referenced.
**Validation**: all validate under `FORMAT_CHECKER`.

### Subtask T028: CHANGELOG, root map consistency, final run

**Purpose**: close the WP.

**Steps**:
1. Append `Added` entries to `contracts/mission-status/CHANGELOG.md` under the current version heading; if any property from WP03 changed shape, log it under a `Pre-release shape change` heading with the reason.
2. Run the targeted commands and gate files; record counts.
3. Confirm no file under `contracts/fixtures/` or `src/` changed (`git diff --stat`).

**Files**: `contracts/mission-status/CHANGELOG.md` (append), no other file (final run and `git diff --stat` check).
**Validation**: examples test and layout check green.

## Definition of Done

- Both resources defined; phases rule text complete; work package schema matches the catalogue; closed schemas; no forbidden property name; no leak-shaped value.
- 100 percent of properties cited or `x-derived` with inputs (hand-count recorded; WP06 enforces later); provisional fields carry `x-provisional` with a description naming the open decision on #5528 and are nullable.
- Examples test red first, then green; `layout_check` exits 0; the FR-009 schema tests (cursor closures disjoint; ULID `missionId` path parameter, no `displayNumber` path parameter) exist with planted violations, are named by test id in the hand-off, and the resolver golden-tree case for the brace spelling failed before the constant changed. Rule BRACE-1 (WP01) holds: the `contract_resolver/` golden tree now contains at least one file with a piece of the `BRACE_REF_SPELLING` tuple, and the single-source test and production-code grep are green.
- `ruff check .` and `ruff format --check .` clean; the two clock-ban gate files green.
- Per-subtask completion recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Risks

- Brace `$ref` spelling may be re-decided by the spike: derive names, never hard-code; WP09 applies any re-sweep.
- Sibling keywords beside `$ref` and `allOf` composition are bundler-fidelity risks (R-3): keep constructs within the resolver's supported list; adding one means extending `contracts/tools/contract_resolver.py` (WP01 wrote it; this WP also owns it, sequentially after WP01) together with its golden-tree test and fixture in the same commit that first uses the construct (resolver change control, D-P2). Whether a construct survives bundling is answered by the IC-07a spike record (`research.md` R-3), so prefer constructs already in the supported list.

## Reviewer Guidance

Verify phase rules against `data-model.md` row by row; verify citations by opening the files; verify `history` and `review` expose no path-like or free-text rows; verify the prompt-body parameter default; verify the exact root-map append (no reordering); verify the examples test failed first.

Implementation command: `spec-kitty agent action implement WP04 --agent claude`
