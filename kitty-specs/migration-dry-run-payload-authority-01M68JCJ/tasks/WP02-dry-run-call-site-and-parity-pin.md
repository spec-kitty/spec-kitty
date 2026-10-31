---
work_package_id: WP02
title: Dry-run call site and byte-parity pin
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-004
- FR-005
- C-004
- NFR-001
- NFR-003
planning_base_branch: issue-6449-migration-dry-run-payload-authority
merge_target_branch: issue-6449-migration-dry-run-payload-authority
branch_strategy: Planning artifacts for this mission were generated on issue-6449-migration-dry-run-payload-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6449-migration-dry-run-payload-authority unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - Call site and parity
history:
- at: '2026-10-31T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/migration/
create_intent:
- tests/migration/test_mission_state_teamspace_payload_authority.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/migration/mission_state.py
- tests/migration/test_mission_state_teamspace_payload_authority.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6449'
---

# Work Package Prompt: WP02 – Dry-run call site and byte-parity pin

## ⚡ Do This First: Load Agent Profile

Load the agent profile in the frontmatter before parsing the rest of this prompt.

- **Profile**: `python-pedro` (`spec-kitty agent profile show python-pedro`)
- **Role**: `implementer`
- **Agent/tool**: `pi`

If the profile cannot be loaded, run `spec-kitty agent profile list` and select the
best match for `task_type: implement` on `authoritative_surface: src/specify_cli/migration/`.

---

## Objective

Replace the hand-built dry-run `WPStatusChanged` payload with the WP01 facade
builder, so the dry-run stops being a second event authority, and pin byte parity
against a **real** transition. Definition of done: `teamspace_dry_run()` over a
repo with one real emitted transition produces a payload byte-identical to that
transition's canonical payload, and a row the model rejects is reported as
`PAYLOAD_INVALID` rather than crashing the run.

## Context & Constraints

- Read: `plan.md` (design decisions 4–5), `contracts/wp-status-changed-payload.md`
  (key set, null policy, historical overrides table), `data-model.md`.
- The call site today: `src/specify_cli/migration/mission_state.py`, function
  `_status_event_to_teamspace_envelope` (~line 1293) — a payload dict literal
  (~1317–1328) under a `# canonical-producer-exempt: #1198` marker.
- Keep the historical overrides in the migration module and pass them as
  `overrides={"from_lane": ..., "evidence": ...}`. They are: the
  `in_progress -> in_review` `for_review` alias, and the approved/done evidence
  synthesis (`_historical_teamspace_evidence`). Nothing else may diverge.
- Keep `validate_event(...)` in place: it still adds JSON-schema conformance and
  the shared semantic transition rules.
- Do not change the envelope shell, the correlation seed, the lamport clock or the
  `build_id`/`node_id` markers.
- Pre-existing CI reds are out of scope; cite, never skip.

## Branch Strategy

- **Planning base branch**: `issue-6449-migration-dry-run-payload-authority`
- **Merge target branch**: `issue-6449-migration-dry-run-payload-authority`
- WP01 must be approved/landed first (it ships the builder this WP imports).

## Subtasks & Detailed Guidance

### Subtask T006 – Red-first parity and authority tests

- **Purpose**: prove the defect before fixing it.
- **Steps**: create `tests/migration/test_mission_state_teamspace_payload_authority.py`:
  1. **Parity with a real transition** — build a real mission dir with
     `meta.json` (`mission_id` present) and emit a transition through the public
     status API (`emit_status_transition` or the coordination path used by
     `tests/status/` helpers). Read the durable row, run `teamspace_dry_run(repo)`,
     and assert `json.dumps(envelope_payload, sort_keys=True)` equals
     `json.dumps(canonical_payload_from_row, sort_keys=True)`. The canonical side
     must be derived from the row's own keys projected onto
     `StatusTransitionPayload.model_fields` — never from the builder under test.
  2. **Construction authority** — monkeypatch
     `specify_cli.migration.mission_state.build_status_event_payload` with a spy
     that records kwargs and delegates, run the dry-run, assert it was called once
     per event row. This is RED on the base (the symbol does not exist).
  3. **Rejected row is reported** — seed one row whose evidence breaks the
     contract (`done` with no `repos` and no `review`, on a non-synthesized lane)
     next to a valid row; assert the report carries a `PAYLOAD_INVALID` error with
     `event_id` and `model_violations`, the run completes, and the valid row is
     still mapped (same fixture positive control).
- **Files**: `tests/migration/test_mission_state_teamspace_payload_authority.py`
- **Notes**: run the file on the base commit and record the RED output; commit the
  test before any implementation change (ATDD-First, C-011).
- **Parallel?**: no.

### Subtask T007 – Rewire the call site

- **Purpose**: one authority.
- **Steps**: import `build_status_event_payload` from `specify_cli.status` (the
  facade — never `status.wire_payload`) and replace the payload literal:
  ```python
  payload = build_status_event_payload(
      status_event,
      overrides={"from_lane": from_lane, "evidence": evidence},
  )
  ```
  Delete the `# canonical-producer-exempt: #1198` marker on
  `_status_event_to_teamspace_envelope` and, if the function's `-> dict[str, Any]`
  return no longer assembles a dict literal containing `event_type`/`payload`,
  confirm the canonical-producer lint is clean for the file.
- **Files**: `src/specify_cli/migration/mission_state.py`
- **Notes**: keep the docstring explaining the two historical overrides.

### Subtask T008 – Non-raising model rejection

- **Purpose**: keep the dry-run's report contract.
- **Steps**: wrap the envelope construction in the event loop with
  `except ValidationError as exc:` (import `ValidationError` from `pydantic`),
  append the existing `PAYLOAD_INVALID` error dict with `mission_slug`,
  `event_id` and `model_violations` mapped from `exc.errors()`
  (`field` = dotted `loc`, `message` = `msg`, `violation_type` = `type`), then
  `continue`. A row that fails construction yields the error and no
  `row_mappings` entry.
- **Files**: `src/specify_cli/migration/mission_state.py`
- **Notes**: the existing `validate_event` block stays for valid payloads.

### Subtask T009 – Targeted verification

- **Steps**: run and record:
  `uv run pytest tests/migration/ -q`,
  `uv run pytest tests/status/test_wire_payload.py tests/architectural/test_status_module_boundary.py tests/architectural/test_integration_boundary.py -q`,
  `uv run python scripts/lint_canonical_producers.py --paths src/ scripts/ tests/ --baseline scripts/canonical_producer_lint_baseline.txt`,
  `uv run ruff check src/specify_cli/migration/mission_state.py`,
  `uv run mypy src/specify_cli/migration/mission_state.py src/specify_cli/status/wire_payload.py`.
- **Notes**: no full heavy suite in-mission (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

### Subtask T010 – Changelog

- **Steps**: add one `[Unreleased]` bullet to `docs/changelog/CHANGELOG.md`
  (root `CHANGELOG.md` is a symlink): bold impact-first lead with `(#6449)`, then
  before/after, under 1,200 characters. State that the dry-run payload now carries
  `mission_id` and can no longer drift from the contract model, and that an
  unrepresentable row is reported as `PAYLOAD_INVALID`.
- **Files**: `docs/changelog/CHANGELOG.md`

## Test Strategy

The three T006 tests are the mandatory red-first proof; T009 lists the commands.
Fixtures: build the mission dir in `tmp_path` with `meta.json` carrying a real
`mission_id`, and use the public status API to write the event log so the oracle
is independent of the code under test.

## Definition of Done

- T006 was RED on the WP01 tip before T007/T008 and is GREEN after.
- No payload dict literal or exemption marker remains at the call site.
- Targeted suites, lint and architectural gates pass; results recorded in the PR.
- Changelog entry present.

## Risks & Mitigations

- Tautological parity test → derive the expectation from the durable row.
- Losing the report contract → the T006 rejected-row case asserts a completed run
  and the valid-row mapping on the same fixture.
- `row_mappings` shrink for invalid rows → documented in plan decision 4; no test
  or consumer depends on the old ordering.

## Review Guidance

- Verify the parity oracle reads the event log, not the builder.
- Verify the builder is imported from the `specify_cli.status` facade.
- Verify the two historical overrides are the only divergences from a real row.

## Progress & Status

Record progress with `spec-kitty agent tasks mark-status <Txxx> --status done` and
`spec-kitty agent tasks add-history WP02 --note "..."`.
