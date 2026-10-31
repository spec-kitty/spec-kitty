# Work Packages: Optional Lamport clock consumer audit

**Inputs**: Design documents from `/kitty-specs/optional-lamport-clock-consumer-audit-01M68ZMF/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md (discovery findings D1-D5)

**Tests**: Required. WP01 carries the red-first reproduction of the migration sentinel defect
(DIRECTIVE_034) through the pre-existing `migrate_lifecycle_envelope` entry point. WP02's mixed-stream
tests are characterization proofs: they must pass on the untouched read paths and stay passing after
the fix, which is what makes the "unaffected" verdicts durable.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work package
is independently deliverable and testable.

**Prompt Files**: Each work package references a matching prompt file in `/tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- **Single project**: `src/specify_cli/`, `tests/`, `docs/`

---

## Work Package WP01: The migration stops asserting a clocked position (Priority: P1) 🎯 MVP

**Goal**: A legacy lifecycle envelope row rewritten by the upgrade migration is marked *unclocked*
(`lamport_clock: null`) instead of clocked at position `0`, so the row no longer claims a causal
order it never recorded, and a second migration pass stays a byte-identical no-op.
**Independent Test**: Run `migrate_lifecycle_envelope` over a log holding one legacy 9-key row and one
newer fresh unclocked row; the migrated row carries `lamport_clock is None`, is accepted by
`spec_kitty_events.Event`, and still sorts before the newer row under `canonical_order_key`.
**Prompt**: `/tasks/WP01-migration-unclocked-sentinel.md`
**Requirement Refs**: FR-003, FR-004, NFR-001, NFR-002, NFR-003, C-002, SC-002, SC-005

### Included Subtasks

T001 Write the red-first tests in `tests/status/test_optional_lamport_clock_migration.py` and prove they fail on the unfixed migration
T002 Set the migration's synthesized sentinel to `None` and update the module docstring's clock prose
T003 Add the ordering-proof test (migrated row still sorts before a newer unclocked row) and the idempotency re-run assertion
T004 Run the targeted status/migration suites, ruff and mypy on the touched paths

### Implementation Notes

- The failing test must exist and fail **before** the production edit: it is the red-first proof quoted in the PR.
- `_is_already_strict_shaped` checks key *presence*, so a `None` value must keep the key present — do not
  delete the key, and do not rewrite rows that already carry `lamport_clock: 0` (idempotency, FR-004).
- The unclocked representation is the dependency's own (`Event.lamport_clock: Optional[int]`); do not
  invent a local sentinel constant for it (C-002).
- No other line in the module changes: `pre_hash == post_hash` (payload untouched) must still hold.

### Dependencies

None. This is the production change the rest of the mission documents.

### Risks

The migration rewrites user files. The whole-file-atomic write and `.pre-migration.bak` snapshot must be
untouched; only the value of one synthesized key changes.

---

## Work Package WP02: Record the audit and prove the read paths clock-agnostic (Priority: P2)

**Goal**: A maintainer can read one reference page listing every core consumer of `Event.lamport_clock`
and the events ordering surface with a verdict and a proof each, and the mixed clocked/unclocked stream
is proven inert for every core read path that can see it.
**Independent Test**: Read `docs/development/reference/optional-lamport-clock-consumers.md`; run
`tests/status/test_optional_lamport_clock_consumers.py`; every row's proof passes, and adding a new
`lamport_clock` reference in `src/` fails the inventory test until it is listed.
**Prompt**: `/tasks/WP02-audit-record-and-mixed-stream-proofs.md`
**Requirement Refs**: FR-001, FR-002, FR-005, FR-006, FR-007, FR-008, NFR-002, NFR-003, C-001, C-003, SC-001, SC-003, SC-004

### Included Subtasks

T001 Write the audit reference page with one row per consumer: path, kind, verdict, proof
T002 Add the mixed clocked/unclocked materialization proof over the shipped replay fixtures
T003 Add the dependency-reducer mixed-stream proof (no raise, permutation-stable)
T004 Add the dry-run normalization proof (synthesized envelopes stay clocked and `(at, event_id)`-ordered)
T005 Add the inventory test that fails when `src/` gains an unlisted ordering/clock reference
T006 Correct the ordering-direction record (unclocked sorts before clocked) and cite the contract
T007 Run the targeted suites, ruff and mypy on the touched paths

### Implementation Notes

- The inventory test scans `src/` for `lamport_clock`, `status_event_sort_key`, `canonical_order_key`,
  `node_order_key`, `total_order_key`, `work_replay` and must require each file to appear in the audit
  page's table — a moved line must not fail it, only a new consumer.
- The mixed-stream proof reuses the replay fixtures shipped in the pinned package
  (`spec_kitty_events/conformance/fixtures/status_diary/replay/`); no new fixture corpus.
- `docs/` changes must satisfy `python -m scripts.docs.check_docs_freshness --ci` (errors=0).
- Keep `#6609` explicitly out of scope in the page's framing (C-001).

### Dependencies

Soft: reads better after WP01 (it records WP01's fix as the "defect found and fixed" row), but its tests
and inventory are independent of WP01's code change.

### Risks

The inventory test can become a brittle whole-repo grep. Bound it to `src/` and to a fixed identifier
list, and match on file path + identifier presence rather than line numbers.

---

## Dependency Graph

```
WP01 (fix)  ->  WP02 (audit record + proofs)
```

WP02 records WP01's outcome, so it lands after it. Both share no owned file.
