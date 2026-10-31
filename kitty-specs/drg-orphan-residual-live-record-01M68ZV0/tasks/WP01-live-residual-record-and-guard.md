---
work_package_id: WP01
title: Live residual record + membership guard
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
planning_base_branch: issue-6513-drg-orphan-residual-live-record
merge_target_branch: issue-6513-drg-orphan-residual-live-record
branch_strategy: Planning artifacts for this mission were generated on issue-6513-drg-orphan-residual-live-record. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6513-drg-orphan-residual-live-record unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-drg-orphan-residual-live-record-01M68ZV0
base_commit: 3ca42ba5a0b45104c38a43e8f18636c7b695f9e2
created_at: '2026-10-31T12:47:09.513748+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Documentation truth-up with an additive guard
history:
- at: '2026-10-31T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/specify_cli/cli/commands/test_doctrine_regenerate_graph.py
- docs/architecture/charter-synthesis-drg.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Live residual record + membership guard (#6513)

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (`spec-kitty agent profile show python-pedro`) and behave according to its
guidance before parsing the rest of this prompt.

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status`) and address every item
before declaring the work package complete.

## Objectives & Success Criteria

- `docs/architecture/charter-synthesis-drg.md` carries a **live** current-state record of the
  shipped-graph DRG orphan residual: the measured 25 URNs, grouped by disposition, with per-group
  rationale and the ceiling ledger (14 -> 18 -> 14 -> 29 -> 30 -> 21 -> 25, `#6379`/`#6432`, this
  mission's `#6513`).
- The ceiling test's failure message and `DOCUMENTED_ORPHAN_RESIDUAL` docstring point at that live
  record and the pinned membership ledger — **not** at the frozen
  `kitty-specs/mission-lifecycle-dispatch-drg-closeout-01KV0S99/drg-orphan-residual.md`.
- A new guard asserts set equality between the record's current-state URNs and the measured shipped
  orphans, so an unrecorded orphan **and** a silent ceiling raise both fail a test.
- `DOCUMENTED_ORPHAN_RESIDUAL` stays **25**. No DRG edge is authored. `packs/built-in/` untouched.
  Nothing under `kitty-specs/` is modified except this mission's own directory.

## Context & Constraints

- Issue #6513 reported `orphans 25 > ceiling 21` at `f1663393`. That red is already fixed by
  `bd7fdb7f36` (ceiling 21 -> 25 for the four `mission_step_contract:plan/*` nodes vendored by
  `#6379`); those nodes are edge-less by construction (`_EDGELESS_BY_CONSTRUCTION` in
  `tests/charter_offering/drg/migration/test_extractor_projection.py`). This WP does **not** touch
  the number and does **not** wire an edge — that would be metric-gaming (D-C2 / C-003).
- The record the gate names today is under `kitty-specs/`, an immutable archive root
  (`tests/architectural/test_archive_root_byte_identical.py`). Editing it fails a gate, so the
  gate's remedy is unexecutable. Cite it as the historical as-of-date record; never edit it.
- Related but out of scope (other owners, cite only): #6798, #6801, #6816, #5927.
- Spec: `kitty-specs/drg-orphan-residual-live-record-01M68ZV0/spec.md`; plan:
  `kitty-specs/drg-orphan-residual-live-record-01M68ZV0/plan.md`.

## Branch Strategy

- **Strategy**: coordination lane (`kitty/mission-drg-orphan-residual-live-record-01M68ZV0`)
- **Planning base branch**: `main`
- **Merge target branch**: `main`

> Populated by `spec-kitty agent mission finalize-tasks`; do not hand-edit.

## Subtasks & Detailed Guidance

### T001 – Extract `_orphan_urns(graph)`

- **Purpose**: the guard needs the URN **set**; the ceiling assertion needs the count. One
  computation, two readers.
- **Steps**: add `_orphan_urns(graph) -> set[str]` beside `_count_orphans`; reduce
  `_count_orphans` to `len(_orphan_urns(graph))`. No behaviour change — the existing tests must
  still pass unchanged.
- **Files**: `tests/specify_cli/cli/commands/test_doctrine_regenerate_graph.py`

### T002 – Guard first (red)

- **Purpose**: bind the record to the measurement before the record exists, proving the guard is
  not vacuous.
- **Steps**: add `LIVE_RESIDUAL_RECORD` (repo-root-relative path to
  `docs/architecture/charter-synthesis-drg.md`) and `_documented_orphan_urns(record_path)` which
  returns the set of backticked URNs inside the delimited block between
  `<!-- drg-orphan-residual:begin -->` and `<!-- drg-orphan-residual:end -->` (return an empty set
  when the markers are absent). Add
  `test_documented_residual_matches_measured_shipped_orphans` asserting set equality with
  `_orphan_urns(load_built_in_graph())`; the message must name the two drift directions
  (measured-but-undocumented, documented-but-no-longer-orphan) and the remedy (add the URN to the
  record **and** keep `DOCUMENTED_ORPHAN_RESIDUAL` in step).
- **Files**: same module
- **Notes**: run it and record the red output — it must fail because the block is absent.

### T003 – Author the live record

- **Purpose**: a live, writable, operator-readable current-state residual record.
- **Steps**: add a `## Shipped-graph orphan residual (current state)` section to
  `docs/architecture/charter-synthesis-drg.md` with: the recompute method (call
  `load_built_in_graph()`, count nodes with no incident edge); the delimited block listing all 25
  URNs; grouped dispositions (21 `mission_step_contract:*` edge-less by construction — all
  enumerated; `glossary_pack:spec-kitty-core` awaiting references until enforcement lands;
  `agent_profile:human-in-charge` runtime-assignment sentinel; `styleguide:deployable-skill-authoring`
  direct-activation-only; `toolguide:powershell-syntax` runtime tooling); the ceiling ledger with
  the 21 -> 25 rationale and `#6379`/`#6432` plus `#6513`; pointers to `_INTENTIONAL_ORPHANS` /
  `_SHIPPED_ORPHANS` in `tests/charter_offering/drg/migration/test_extractor_projection.py`; and a
  note that the frozen `kitty-specs/.../drg-orphan-residual.md` is the historical record and stays
  as-of-date.
- **Files**: `docs/architecture/charter-synthesis-drg.md` (bump frontmatter `updated:`)
- **Notes**: recompute the membership, never copy the list from this prompt or from prose.

### T004 – Retarget the ceiling's instructions

- **Purpose**: an operator who fails the gate must be sent to a writable record.
- **Steps**: in `DOCUMENTED_ORPHAN_RESIDUAL`'s docstring, add a dated entry that names the live
  record, states that the `kitty-specs/` file is a frozen archive, and keeps the historical entries
  as as-of-date wording; rewrite the assertion message to offer exactly two remedies — wire a real
  inbound edge, or add the URN to the live record and raise the ceiling together — and to name the
  live record path. **Do not change the constant's value.**
- **Files**: same module

### T005 – Prove the guard in both directions

- **Purpose**: no vacuous guard.
- **Steps**: with the record in place, (a) remove one URN from the record block, run the guard,
  capture the failure naming that URN; (b) add a stale URN (e.g. `tactic:does-not-exist`), run the
  guard, capture the failure; restore the file and confirm green. Record the commands and outputs
  for the PR body.
- **Files**: `docs/architecture/charter-synthesis-drg.md` (temporary only)

### T006 – Changelog

- **Purpose**: user-facing record of the fix.
- **Steps**: add a `### Fixed` bullet under `## [Unreleased] - 4.0.0rc8` in
  `docs/changelog/CHANGELOG.md`: bold impact-first lead, `(#6513)`, before/after, under 1,200
  characters. Note that the ceiling is unchanged and no edge was wired.
- **Files**: `docs/changelog/CHANGELOG.md`

### T007 – Gates

- **Steps**: `uv run pytest -q tests/specify_cli/cli/commands/test_doctrine_regenerate_graph.py`;
  `uv run python -m scripts.docs.check_docs_freshness --ci`; `npx markdownlint-cli2` (or the repo's
  markdown gate) on the two touched docs; `uv run pytest -q
  tests/architectural/test_archive_root_byte_identical.py` to prove `kitty-specs/` is untouched.
  Do **not** run a full heavy suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Test Strategy

- Red-first: T002's guard failing output is the entry evidence; T003 is what makes it green.
- Both-direction proof in T005 (an unrecorded orphan; a stale recorded row).
- No test is skipped, xfailed or loosened; the existing `<=` ceiling assertion stays.

## Risks & Mitigations

- Docs gates: page already in the inventory and explanation ToC → no new page, no inventory churn.
- Markdown lint on HTML comment markers → keep the delimiters on their own lines.
- Guard brittleness → only the delimited block is parsed; URNs are the only extractable token.

## Review Guidance

- Confirm the constant is still 25 and that `git diff` touches nothing under `packs/built-in/` or
  another mission's `kitty-specs/` directory.
- Confirm the record's 25 URNs are the recomputed set, not a copy of the ceiling's prose.
- Confirm the failure message names the live record and offers the two honest remedies.
- Confirm the guard fails when a URN is dropped or invented (ask for the T005 transcripts).

## Progress & Status

Progress, history and status live in the status event log (`status.events.jsonl`) — never in this
prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
