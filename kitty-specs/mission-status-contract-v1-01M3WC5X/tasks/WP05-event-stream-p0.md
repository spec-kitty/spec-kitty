---
work_package_id: WP05
title: Event stream resource and preview point p0 (IC-04)
dependencies:
- WP04
requirement_refs:
- FR-007
- FR-008
- FR-009
- FR-010
- FR-013
- C-007
- C-010
- SC-001
planning_base_branch: issue-5558-mission-status-contract-v1
merge_target_branch: issue-5558-mission-status-contract-v1
branch_strategy: Planning artifacts for this mission were generated on issue-5558-mission-status-contract-v1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5558-mission-status-contract-v1 unless the human explicitly redirects the landing branch.
subtasks:
- T029
- T030
- T031
- T032
- T033
history: []
agent_profile: implementer-ivan
authoritative_surface: contracts/mission-status/
create_intent:
- contracts/mission-status/openapi.yaml
- contracts/mission-status/CHANGELOG.md
- contracts/mission-status/paths/events.yaml
- tests/contract/test_mission_status_examples.py
- contracts/tools/contract_resolver.py
- tests/contract/test_contract_resolver.py
execution_mode: code_change
model: sonnet
owned_files:
- contracts/mission-status/openapi.yaml
- contracts/mission-status/CHANGELOG.md
- contracts/mission-status/paths/events.yaml
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

# WP05 - Event stream resource and preview point p0 (IC-04)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Add `GET /events` (`text/event-stream`) with exactly three projected event kinds, one data schema each, the documented stream convention, the refusal `Problem` mappings and examples, and close IC-04 with the published **preview point p0**.

## Context

- Plan concern **IC-04**, last of the sequential content WPs. After this WP all five paths exist: `project`, `missions`, `missions/{missionId}`, `missions/{missionId}/work-packages/{wpId}`, `events`. It appends to the root map and `_index.yaml` files (chokepoint, serialised by dependencies).
- Binding sources: `spec.md` FR-007, D-8, D-9, D-18, the Event table of the Field Catalogue; `data-model.md` "Projection rules" (allow-list, stream cursor string form, field classes); `plan.md` section (l) "Event-stream allow-list ownership (binding)": the seven forwarded lifecycle types (`MISSION_CREATED`, `SPECIFY_STARTED`, `SPECIFY_COMPLETED`, `PLAN_STARTED`, `PLAN_COMPLETED`, `TASKS_STARTED`, `TASKS_COMPLETED`) are **contract-owned**, a deliberate subset of the twelve-member `LIFECYCLE_EVENT_TYPES` in `specify_cli/status/lifecycle_events.py`; a type added upstream later is dropped by design.
- Three kinds only: `status-transition` (`missionId`, `eventId`, `wpId`, `fromStatusLane`, `toStatusLane`, `at`, `actor`, `force`, `streamCursor`), `mission-lifecycle` (`missionId`, `eventId`, `eventType` one of the seven, `at`, `streamCursor`), `log-truncated` (`missionId`, `reason` limited to `size_shrink` and `content_mismatch`, `detectedAtOffset`, `streamCursor` reset to offset 0 with the empty digest). Raw log rows never appear; annotation, decision-point, retrospective, reviewer-self-approval and unknown rows are dropped, never forwarded.
- Request shape (D-18): optional `missionId` query parameter; optional `streamCursor` (`<offset>:<invariant>`, decimal offset, colon, 64 hex characters) which requires `missionId`; the `Last-Event-ID` header carries the same string and the SSE `id:` field is the same string; unscoped stream is live-only; per-Mission ordering only; heartbeat is an SSE comment line (`: heartbeat`) every 30 seconds. Documented refusals, exactly: `negative`, `out_of_range`, `misaligned`, `content_mismatch` (the reason values of `ResumeRefused` in `specify_cli/status/tail_reader.py`), each a `Problem` response, plus the refusal of a cursor sent without `missionId`. Cursor field citation: `TailCursor` and its `content_invariant` attribute (a bare annotated class attribute; the citation check treats annotated targets as defined names, PQ-10, implemented in WP06).
- **Python hygiene (binding for this WP)**: this WP edits `tests/contract/test_mission_status_examples.py`, so run `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .` before the final commit and record both results (NFR-007). In `tests/`, never import `datetime` and never call `datetime.now()` or `time.time()` (clock-ban gates, named below): compare ISO-8601 strings or use the kernel clock door.
- **Preview point p0** ("unvalidated preview, no stability promise"): the **last commit of this WP** (working title `feat(contracts): events stream resource and examples (#5558)`). At it only the Python resolver and the examples test have read the split contract; no content check, validator, lint, bundle, reality check or client generator has run. See the close-out section below.
- Baseline, overlap, hygiene, terminology and red-first rules: as in WP03. **Open-PR overlap check (2026-10-02)**: #5540 and #5326 touch none of this WP's files.
- Does not touch the migration chain, runtime-state schema, event contract implementation (this is documentation of a future stream; no emitter, server or transport is built; the live Zeitgeist path is untouched and not described) or a shared CI gate.

### Test surface, gates and baseline

- Targeted: `tests/contract/test_mission_status_examples.py`, `tests/contract/test_contract_resolver.py` (if the resolver is extended), `.venv/bin/python contracts/tools/layout_check.py --root contracts`.
- Named gates: `tests/architectural/test_clock_import_ban.py tests/architectural/test_clock_call_ban.py`, `tests/architectural/test_ci_corpus_trigger_completeness.py`, `tests/architectural/test_workflow_coherence.py`.

## Subtasks

### Subtask T029: Failing example cases for the stream

**Purpose**: red-first.

**Steps**:
1. Extend the examples test: one example per event kind, one per refusal reason (four) plus the cursor-without-`missionId` refusal, and negative cases: an event example carrying a property outside the kind's schema fails; `log-truncated` with another `reason` fails; a `mission-lifecycle` example with an `eventType` outside the seven fails.
2. Assert at least one example per kind validated before asserting properties.

**Files**: `tests/contract/test_mission_status_examples.py` additions (~100 lines).
**Validation**: red on the WP04 tree.

### Subtask T030: Event data schemas and cursor handling

**Purpose**: FR-007 schemas.

**Steps**:
1. `schemas/StatusTransitionEvent.yaml`, `MissionLifecycleEvent.yaml`, `LogTruncatedEvent.yaml`; each closed, each property cited (`StatusEvent` in `specify_cli/status/models.py`, `poll_once` and `_truncation_signal` in `specify_cli/status/tail_reader.py`, lifecycle constants). `missionId` source is the Mission's `meta.json` identity, never `aggregate_id`; say so in the description (aggregate_id is the ULID only for MissionCreated, the slug for several other rows, the work package id for WPCreated).
2. Reuse `StreamCursor`, `ActorHandle` and `StatusLane` from WP03; add the `<offset>:<invariant>` string form as `StreamCursorString` (pattern `^[0-9]+:[0-9a-f]{64}$`) used by the query parameter, header and SSE id.
3. Append to the schemas `_index.yaml`.

**Files**: three event schemas (~60 lines each), one cursor-string schema.
**Validation**: resolver loads them; named events map to schemas one to one.

### Subtask T031: `events.yaml` path, convention prose and refusal problems

**Purpose**: FR-007 documentation as contract.

**Steps**:
1. `paths/events.yaml`: `GET /events` with a `200` of content type `text/event-stream` and a schema; the description documents event name, `id`, resume, heartbeat, per-Mission ordering, unscoped live-only behaviour and consumer actions (on `log-truncated` discard that Mission's stored cursor, re-read the Mission detail, resume from the detail's `streamCursor`; unknown enum values inside a known kind are treated as unknown, not as failures). The description maps each event name to exactly one data schema in a parseable list (the event-mapping check in WP06 reads this; each name appears once, each schema in the mapping is referenced by exactly one name).
2. Parameters: `missionId` (optional query), `streamCursor` (optional query, requires `missionId`), `Last-Event-ID` header. Responses: 400 and 409 style refusals as `Problem` (use the shared `Problem` response; one distinguishing `type` or example per refusal reason; no new content type).
3. Append the path item to the root map in `openapi.yaml`.

**Files**: `contracts/mission-status/paths/events.yaml` (new), `contracts/mission-status/parameters/**`, `contracts/mission-status/openapi.yaml` (append).
**Validation**: `layout_check` exits 0; mapping text lists exactly three names.

### Subtask T032: Examples

**Purpose**: FR-013.

**Steps**: one example per event kind, one `Problem` example per refusal reason and one for the cursor-without-`missionId` refusal; no host path, e-mail address or person name in any (a planted leak in an event example is later detected by WP06's scan, and the event data schemas have no field that could hold one).

**Files**: `contracts/mission-status/examples/**` (about 8 example files).
**Validation**: all validate; each is referenced by a schema or response.

### Subtask T033: CHANGELOG, final runs and p0 close-out

**Purpose**: close IC-04 and publish p0.

**Steps**:
1. Append to `contracts/mission-status/CHANGELOG.md` (added resources; any shape change of earlier fields under `Pre-release shape change`).
2. Run the targeted commands and named gates; record counts. `git diff --stat` shows nothing under `src/` or `contracts/fixtures/`.
3. Record in the hand-off the exact commit (hash) that is the last commit of IC-04 and the five path files and three vocabularies it contains.

**Files**: `contracts/mission-status/CHANGELOG.md` (append), no other file (final run, `git diff --stat` check, hand-off).
**Validation**: all green.

## Close-out step: publish preview point `p0` (ORCHESTRATOR action, recorded in this WP)

Agents never push and never create remote tags. After this WP is **approved**, the preview tag `preview/mission-status/p0` is published, as a lightweight tag on the last commit of this WP (which is the head of seam 2, so the tag is cut at the head of PR 2 and cites PR 2; see the tag-publication rule below), in the non-release namespace `preview/mission-status/p<N>` (outside both `contract-<module>-v<semver>` and the CLI's `v*.*.*`). Semantics, from the plan:

- p0 is an **unvalidated preview**: it carries **no stability promise and no compatibility promise**; it is for an outside UI team to read and plan against. Unproven risk factors: brace-named files in `$ref`, chained refs through `_index.yaml`, refs leaving the module into `../_shared/`, a path-item `$ref` in the root `paths` map, OpenAPI 3.1 type arrays and sibling keywords beside `$ref`.
- From p0 on, no removal, rename, enum-value removal or type narrowing of a published field happens without a `Pre-release shape change` line in the module CHANGELOG with its reason, unless the #5528 acknowledgement requests otherwise. Making a property optional or nullable is itself breaking for generated clients.
- **Re-publication counter rule**: if the history of seam 1 or seam 2 is rewritten (the compact-history step of either seam; a rewrite of seam 1 also rewrites seam 2) or a brace re-sweep lands (WP09) after p0 was published, p0 is re-published (same publication rule) under a new tag with a per-point increasing counter suffix: the first re-publication of p0 is `preview/mission-status/p0-r2`, the next `p0-r3`, and so on; the counters of p1 and p2 are independent; each re-publication names its cause (`compact history` or `brace re-sweep`) in its note on #5528; the old tag stays until the UI team has moved.
- **Tag publication (plan E-3, identical in WP05, WP09 and WP10).** The push of the tag and the note on #5528 are maintainer acts. After this WP is approved, the orchestrator prepares the lightweight-tag command and the #5528 note and publishes them only acting for a maintainer (with that maintainer's go-ahead); agents never push and never create remote tags. Record "prepared" and "published by <maintainer, or orchestrator acting for them>" separately in the hand-off. Fallback if no maintainer publishes: a `git archive` tarball of the split tree with its sha256, posted on #5528.
- The orchestrator records the **tag name (not a hash)**, the date and the "prepared" versus "published by" status in this WP's hand-off; WP12 transcribes it into `tracer-approach.md`.

## Definition of Done

- `events.yaml`, three event schemas, cursor-string schema, refusal problems and examples exist; allow-list statement matches `plan.md` section (l); closed schemas; all properties cited.
- Examples test red first, then green; `layout_check` exits 0; named gates green; `ruff check .` and `ruff format --check .` clean.
- All five v1 paths present in the root map.
- Hand-off names the last IC-04 commit; the orchestrator p0 step is listed as pending or done with the tag name.
- Per-subtask completion recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Risks

- A leak-shaped value in an example (the strict scan later fails the whole contract): write placeholder data only.
- Treating `LIFECYCLE_EVENT_TYPES` as the allow-list: the seven are contract-owned; do not cite the module constant as the allow-list source (cite the markers it defines individually).
- p0 mistaken for a stability promise: the tag note must repeat "unvalidated preview".

## Reviewer Guidance

Check the three kinds and no more; the `missionId` provenance text; the exact refusal reasons; that no raw log row shape appears; the root-map append; and that the last commit of the WP is a clean, self-consistent tree (it will be tagged). Verify red then green.

Implementation command: `spec-kitty agent action implement WP05 --agent claude`
