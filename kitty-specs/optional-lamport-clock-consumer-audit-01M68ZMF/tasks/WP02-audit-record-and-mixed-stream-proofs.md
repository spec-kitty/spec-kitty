---
work_package_id: WP02
title: Record the audit and prove the read paths clock-agnostic
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-005
- FR-006
- FR-007
- FR-008
- NFR-002
- NFR-003
- C-001
- C-003
- SC-001
- SC-003
- SC-004
planning_base_branch: issue-6414-optional-lamport-clock-consumer-audit
merge_target_branch: issue-6414-optional-lamport-clock-consumer-audit
branch_strategy: Planning artifacts for this mission were generated on issue-6414-optional-lamport-clock-consumer-audit. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6414-optional-lamport-clock-consumer-audit unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 2 - Audit record and proofs
history:
- at: '2026-10-31T12:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/status/
create_intent:
- docs/development/reference/optional-lamport-clock-consumers.md
- tests/status/test_optional_lamport_clock_consumers.py
execution_mode: code_change
model: deepseek-v4.1-flash
owned_files:
- docs/development/reference/optional-lamport-clock-consumers.md
- tests/status/test_optional_lamport_clock_consumers.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Record the audit and prove the read paths clock-agnostic

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

- One reference page lists every core site that names `lamport_clock` (the envelope field or a
  same-named local clock) and every core reference to the events ordering surface, each with a verdict
  and the test that pins it.
- A mixed clocked/unclocked status stream cannot change core lane state, and the dependency's
  Lamport-ordered reducer handles such a stream deterministically.
- An inventory test fails when `src/` gains an unlisted reference to the audited identifiers.
- The page states the real ordering direction (unclocked sorts **before** clocked), citing the pinned
  contract, and does not repeat the inverted claim from the issue body.

## Context & Constraints

- Issue #6414, acceptance criteria: findings recorded, each consumer handles `None`/4-tuple or is shown
  unaffected, and tests cover a mixed clocked/unclocked stream where relevant.
- Discovery: `kitty-specs/optional-lamport-clock-consumer-audit-01M68ZMF/research.md` D1-D4 is the
  evidence base; the numbers there were taken at `origin/main` `dfe9efb0e8`. Re-verify line numbers
  before pasting them into the page; if a line moved, cite the symbol, not the number.
- **Out of scope**: #6609 (Lamport-primary ordering for the status log). The CLI keeps its wall-clock
  `(at, event_id)` fold; the page must say so explicitly so a reader does not infer otherwise.
- Documentation standards: `docs/development/reference/` is the home for consumer/contract references;
  the page must satisfy `python -m scripts.docs.check_docs_freshness --ci` (errors=0).

## Branch Strategy

- **Strategy**: single-branch mission. Planning artifacts and code both land on
  `issue-6414-optional-lamport-clock-consumer-audit`; completed changes merge back into it.
- **Planning base branch**: `issue-6414-optional-lamport-clock-consumer-audit`
- **Merge target branch**: `issue-6414-optional-lamport-clock-consumer-audit`

## Subtasks & Detailed Guidance

### Subtask T001 – Write the audit page

- **Purpose**: The issue's first acceptance criterion — findings recorded where maintainers look, not
  only in a GitHub thread.
- **Steps**: Create `docs/development/reference/optional-lamport-clock-consumers.md` with: the
  contract summary (optional clock, real ordering direction, 4-tuple key, merge/work_replay refusal);
  a table of consumers (site, kind, verdict, proof); the "what core does not do" section (no callers of
  the ordering surface, no `merge`/`work_replay` import); the fix WP01 made and the documented residual
  (already-migrated `lamport_clock: 0` rows are left untouched); and an explicit out-of-scope note for
  #6609. Keep it under ~150 lines.
- **Files**: `docs/development/reference/optional-lamport-clock-consumers.md`
- **Parallel?**: No — the table is the source of truth the inventory test reads.
- **Notes**: Match the front-matter/heading conventions of its siblings in
  `docs/development/reference/` (read two of them first).

### Subtask T002 – Mixed-stream materialization proof

- **Purpose**: The read path that consumes status rows must be provably clock-agnostic.
- **Steps**: In `tests/status/test_optional_lamport_clock_consumers.py`, take a shipped replay fixture
  (`spec_kitty_events/conformance/fixtures/status_diary/replay/status_diary_every_lane.jsonl` via
  `importlib.resources`), materialize it, then materialize the same rows with a `lamport_clock` added to
  alternating rows, and assert the written `status.json` is byte-identical.
- **Files**: `tests/status/test_optional_lamport_clock_consumers.py`
- **Parallel?**: Yes, with T003/T004.
- **Notes**: Build the feature dir the way `tests/status/test_shared_reducer_materialization.py` does
  (`meta.json` + `EVENTS_FILENAME`), or use `specify_cli.status.materialize` on a `tmp_path` mission.
  Mark the module `pytest.mark.fast` unless a git repo is required.

### Subtask T003 – Dependency-reducer mixed stream

- **Purpose**: `reduce_status_events` is the only 4-tuple/`lamport_clock` consumer reachable in the
  dependency; prove a CLI-shaped mixed log cannot crash it.
- **Steps**: Build `Event` envelopes for a two-WP status stream where some rows are clocked and some are
  unclocked; assert `spec_kitty_events.status.reduce_status_events` returns without raising and that two
  permutations of the input produce the same per-WP lanes.
- **Files**: `tests/status/test_optional_lamport_clock_consumers.py`
- **Parallel?**: Yes.
- **Notes**: This test documents *why* the CLI does not adopt it (wall-clock fold is the CLI's authority),
  so name it so the intent is obvious. Do not assert a lane order the CLI itself would not produce.

### Subtask T004 – Dry-run normalization proof

- **Purpose**: The TeamSpace dry run re-synthesizes envelopes; prove it discards any source clock rather
  than mixing clocked and unclocked rows.
- **Steps**: With `migrate_lifecycle_envelope`-shaped or plain status rows in a mission dir, run the
  dry-run envelope builder path used by `teamspace_dry_run` (call the module-level builder directly if a
  full repo fixture is disproportionate), and assert every emitted envelope carries an integer
  `lamport_clock` equal to its 1-based position in `(at, event_id)` order.
- **Files**: `tests/status/test_optional_lamport_clock_consumers.py`
- **Parallel?**: Yes.
- **Notes**: Prefer the smallest real entry point that exercises
  `src/specify_cli/migration/mission_state.py`'s sort-and-index; a full `teamspace_dry_run` needs a git
  repo and is heavier than this proof needs.

### Subtask T005 – Inventory drift test

- **Purpose**: The audit cannot silently go stale (FR-002).
- **Steps**: Scan `src/**/*.py` for the identifier list
  (`lamport_clock`, `status_event_sort_key`, `canonical_order_key`, `node_order_key`,
  `total_order_key`, `work_replay`) as text; for every file with a hit, require the audit page's table to
  name that repo-relative path. Fail with the missing paths listed.
- **Files**: `tests/status/test_optional_lamport_clock_consumers.py`
- **Parallel?**: No — depends on T001's table.
- **Notes**: Do not fail on line numbers or on identifiers appearing in prose/comments; the assertion is
  "this file is listed", which is stable. Skip the generated skill-copy tree under `src/charter/offering/`
  only if it genuinely contains no such hit at implementation time — prefer listing it over excluding it.

### Subtask T006 – Correct the direction claim

- **Purpose**: FR-008 — the issue body says unclocked sorts *after* clocked; the contract says before.
- **Steps**: State the direction once in the page's contract summary with the citation
  (`spec_kitty_events/ordering.py`, `Event.lamport_clock` description in `models.py`) and note that the
  issue body's wording is inverted. Do not edit the issue thread.
- **Files**: `docs/development/reference/optional-lamport-clock-consumers.md`
- **Parallel?**: Yes, within T001's write.
- **Notes**: Quote the key shape verbatim so a reader can compare with the installed source.

### Subtask T007 – Targeted verification

- **Purpose**: Prove the docs and tests are green on the shipped gates.
- **Steps**: `uv run pytest tests/status/test_optional_lamport_clock_consumers.py -q`;
  `uv run python -m scripts.docs.check_docs_freshness --ci` (expect errors=0);
  `uv run python -m scripts.docs.docs_index --write` only if the page needs an index entry, then re-check
  freshness; `uv run ruff check` on the new test module and `uv run mypy` on it.
- **Files**: none (verification only)
- **Parallel?**: No.
- **Notes**: Do not rebuild the whole CLI command reference — other agents share the global asset cache.

## Test Strategy

- Commands:
  - `uv run pytest tests/status/test_optional_lamport_clock_consumers.py -q`
  - `uv run python -m scripts.docs.check_docs_freshness --ci`
  - `uv run ruff check tests/status/test_optional_lamport_clock_consumers.py`
  - `uv run mypy tests/status/test_optional_lamport_clock_consumers.py`
- Fixtures: the replay fixtures shipped inside the pinned `spec_kitty_events` package, read through
  `importlib.resources` (never a hardcoded site-packages path).

## Risks & Mitigations

- **Risk**: the inventory test becomes a brittle grep. **Mitigation**: file-path granularity, fixed
  identifier list, `src/` scope only.
- **Risk**: the docs freshness gate wants an index entry. **Mitigation**: run it and follow its output;
  a partial, verifiable regeneration beats a full rebuild on a shared machine.
- **Risk**: duplicating research.md. **Mitigation**: the page is the durable, reader-facing record with
  proofs; research.md is the mission's discovery log. Link between them rather than copying prose.

## Review Guidance

- Every row of the table has a proof a reader can run in one command.
- No verdict is "unaffected" without a reason and a test.
- The direction claim matches `spec_kitty_events` 11.3.0 source, not the issue body.
- No production file outside WP01's owned set changed.

## Progress & Status

Record each subtask with `spec-kitty agent tasks mark-status <Txxx> --status done --mission optional-lamport-clock-consumer-audit-01M68ZMF`.
