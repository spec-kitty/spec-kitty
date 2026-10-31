---
work_package_id: WP01
title: The migration stops asserting a clocked position
dependencies: []
requirement_refs:
- FR-003
- FR-004
- NFR-001
- NFR-002
- NFR-003
- C-002
- SC-002
- SC-005
planning_base_branch: issue-6414-optional-lamport-clock-consumer-audit
merge_target_branch: issue-6414-optional-lamport-clock-consumer-audit
branch_strategy: Planning artifacts for this mission were generated on issue-6414-optional-lamport-clock-consumer-audit. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6414-optional-lamport-clock-consumer-audit unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Production fix
history:
- at: '2026-10-31T12:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- tests/status/test_optional_lamport_clock_migration.py
execution_mode: code_change
model: deepseek-v4.1-flash
owned_files:
- src/specify_cli/status/migrate_lifecycle_envelope.py
- tests/status/test_optional_lamport_clock_migration.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – The migration stops asserting a clocked position

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status --mission optional-lamport-clock-consumer-audit-01M68ZMF` for a
`review_ref`; if this WP was returned from review, the feedback is your TODO list.

---

## Objectives & Success Criteria

- A legacy 9-key lifecycle envelope row rewritten by
  `specify_cli.status.migrate_lifecycle_envelope.migrate_lifecycle_envelope` carries
  `lamport_clock: None` (unclocked), not `lamport_clock: 0` (clocked at zero).
- The migrated row still validates as a `spec_kitty_events.Event` with all 14 strict keys present.
- A re-run over an already-migrated file remains a byte-identical no-op, whatever sentinel the earlier
  run wrote.
- No payload byte changes: `pre_hash == post_hash` for every migrated row, still.

## Context & Constraints

- Issue #6414 (parent epic #6411). Discovery: `kitty-specs/optional-lamport-clock-consumer-audit-01M68ZMF/research.md`
  (D1 contract direction, D3 row 4 the defect, D5 fix boundary).
- `spec-kitty-events>=11.3.0,<12` (`pyproject.toml:80`) makes `Event.lamport_clock: Optional[int]`
  (`spec_kitty_events/models.py:120`) and orders with `canonical_order_key` =
  `(1 if clocked else 0, clock or 0, utc_timestamp_iso, event_id)`
  (`spec_kitty_events/ordering.py:41`). Unclocked rows sort **before** clocked ones.
- The defect: a fixed `0` claims "clocked, position zero", so the migrated row sorts after every
  unclocked row of the same log regardless of timestamp, and joins one "concurrent" group with every
  other migrated row for a consumer that groups by `(wp_id, lamport_clock)`.
- **Out of scope**: #6609 (Lamport-primary ordering for the status log, parked post-GA). Do not
  change the CLI's wall-clock `(at, event_id)` fold anywhere.
- **Do not** rewrite rows already carrying `lamport_clock: 0`: `_is_already_strict_shaped` recognises
  them by key presence, and rewriting them would break the MIG2 no-op guarantee.
- The module docstring at `migrate_lifecycle_envelope.py:35-39` states "0 means no causal order
  recorded" — that prose must change with the code, not lag behind it.

## Branch Strategy

- **Strategy**: single-branch mission. Planning artifacts and code both land on
  `issue-6414-optional-lamport-clock-consumer-audit`; completed changes merge back into it.
- **Planning base branch**: `issue-6414-optional-lamport-clock-consumer-audit`
- **Merge target branch**: `issue-6414-optional-lamport-clock-consumer-audit`

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first reproduction

- **Purpose**: Prove the defect through the existing entry point before touching production code, so
  the PR carries red-first evidence (charter, ATDD-First Discipline; DIRECTIVE_034).
- **Steps**: Create `tests/status/test_optional_lamport_clock_migration.py`. Reuse the shape of the
  existing suite `tests/status/test_migrate_lifecycle_envelope.py` (its `_legacy_row` helper builds the
  exact 9-key legacy shape; copy the fixture recipe, do not import private test helpers across modules).
  Write one row through `migrate_lifecycle_envelope` and assert the migrated row's `lamport_clock` is
  `None`. Run it and capture the failure output.
- **Files**: `tests/status/test_optional_lamport_clock_migration.py`
- **Parallel?**: No — it is the gate for T002.
- **Notes**: Marks: mirror the existing migration suite (`pytest.mark.integration`, `pytest.mark.git_repo`)
  because the migration resolves a git repo root and writes a `.bak` sibling.

### Subtask T002 – Emit the unclocked sentinel

- **Purpose**: Remove the false causal claim.
- **Steps**: In `_migrate_row`, set the synthesized key to `None` instead of `0`. Update the module
  docstring bullet (`* ``lamport_clock``: fixed ``0`` sentinel ...`) to say the row is emitted
  *unclocked* (`null`) because a legacy row recorded no causal clock, and that the contract's unclocked
  representation — not a local `0` sentinel — is what the strict profile carries. Keep the key present.
- **Files**: `src/specify_cli/status/migrate_lifecycle_envelope.py`
- **Parallel?**: No.
- **Notes**: Do not introduce a module constant; the value is the dependency's own representation (C-002).
  Keep the line-local comment style of its neighbours.

### Subtask T003 – Ordering and idempotency proofs

- **Purpose**: Pin the two behaviours the change is justified by, so a later "simplify back to 0" is
  caught.
- **Steps**: Add (a) a test that orders a migrated row and a strictly newer *fresh* unclocked row with
  `spec_kitty_events.ordering.canonical_order_key` and asserts the older migrated row sorts first —
  the assertion fails if the sentinel is `0`; (b) a test that re-runs the migration over its own output
  and asserts the file is byte-identical and `migrated_count == 0`; (c) a test that a hand-written row
  already carrying `lamport_clock: 0` is left untouched (`unchanged`, byte-identical).
- **Files**: `tests/status/test_optional_lamport_clock_migration.py`
- **Parallel?**: Yes, with T004's suite runs.
- **Notes**: Read the ordering assertion through `canonical_order_key`, never by re-implementing the
  tuple (single canonical authority).

### Subtask T004 – Targeted verification

- **Purpose**: Prove the change is safe on the shipped suites.
- **Steps**: Run `uv run pytest tests/status/test_optional_lamport_clock_migration.py tests/status/test_migrate_lifecycle_envelope.py tests/status/test_migrate_lifecycle_envelope_node_id_parity.py tests/status/test_lifecycle_events.py -q`,
  then `uv run ruff check` and `uv run mypy` on the touched paths. Do not run a full heavy suite
  (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
- **Files**: none (verification only)
- **Parallel?**: No.
- **Notes**: If a pre-existing failure appears, check whether it reproduces on `origin/main` in a clean
  worktree before attributing it to this WP.

## Test Strategy

- Commands:
  - `uv run pytest tests/status/test_optional_lamport_clock_migration.py -q` (red first, then green)
  - `uv run pytest tests/status/test_migrate_lifecycle_envelope.py tests/status/test_migrate_lifecycle_envelope_node_id_parity.py -q`
  - `uv run ruff check src/specify_cli/status/migrate_lifecycle_envelope.py tests/status/test_optional_lamport_clock_migration.py`
  - `uv run mypy src/specify_cli/status/migrate_lifecycle_envelope.py`
- Fixtures: build rows with the same recipe as the existing migration suite (9-key legacy shape,
  `schema_version: "5.0.0"`, a real `project_uuid`), in a `git init`-ed `tmp_path`.

## Risks & Mitigations

- **Risk**: the migration touches user files. **Mitigation**: only the value of one synthesized key
  changes; the atomic write, `.pre-migration.bak` snapshot and refusal paths are untouched.
- **Risk**: idempotency regresses if the key were dropped instead of nulled. **Mitigation**: T003(b)/(c)
  pin both the re-run no-op and the already-migrated-row case.
- **Risk**: a reader somewhere requires an `int`. **Mitigation**: WP02's inventory + mixed-stream proofs
  cover every core reader; `spec_kitty_events.Event` accepts `None` by contract.

## Review Guidance

- Confirm the red-first evidence: the same command failing before T002 and passing after.
- Confirm `pre_hash == post_hash` still holds and the 14 strict keys are all present on a migrated row.
- Confirm no other production file changed, and no ordering behaviour outside the migration moved.
- Confirm the docstring matches the code (a stale "0 means no causal order" bullet is a review reject).

## Progress & Status

Record each subtask with `spec-kitty agent tasks mark-status <Txxx> --status done --mission optional-lamport-clock-consumer-audit-01M68ZMF`.
