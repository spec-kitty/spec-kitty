# Mission Specification: Drain the snapshot-versus-files work-package disagreement

**Mission Branch**: `issue-5579-wp-snapshot-backfill`
**Created**: 2026-10-03
**Status**: Draft
**Input**: GitHub issue [#5579](https://github.com/spec-kitty/spec-kitty/issues/5579) — "Mission status: drain the snapshot-versus-files work-package disagreement (reality-check ratchet)". Part of epic #5528.

## Intent Summary (confirmed)

- **Primary actor**: a Spec Kitty maintainer (and, through the shipped CLI, any consumer operator) whose committed Missions have work-package (WP) files that the reduced status snapshot does not count.
- **Trigger**: a read surface (the Mission Status Read API, progress, kanban) counts WPs from the reduced snapshot (`materialize(...).work_packages`) while listing WPs from `tasks/WP*.md`; on this repository 51 Missions disagree.
- **Desired outcome**: one canonical, idempotent repair seeds the missing WP status events so every Mission's snapshot carries every WP file; finished Missions are seeded to a terminal lane so progress stays truthful; this repository's committed corpus is drained to zero disagreements and held there by a gate.
- **Invariant**: the reducer is unchanged. A WP with no lane events never materialises in the snapshot (ADR `2026-06-07-3`); the event log stays the sole lane authority, so the fix repairs the log, never overlays files onto the snapshot.
- **Decisions recorded** (Decision Moments `01M41NVF…`, `01M41NVK…`): the mission bases on `main` and does not depend on unmerged PR #5581 (its ratchet ceiling is set to 0 when it lands); finished Missions are backfilled as seed + forced `done`, not left `planned` and not exempted.

### Observed corpus (main @ `c11d043e54`)

| Bucket | Count | Shape |
|---|---|---|
| A | 20 | No `status.events.jsonl` at all (mostly 2026-08/09 Missions landed as dossier commits; coordination branch gone) |
| B1 | 16 | Log exists; the missing WPs carry only a `WPCreated` lifecycle row |
| B2 | 8 | Log exists; the missing WPs have no rows at all (WPs added or renumbered after seeding) |
| C | 7 | Snapshot carries WPs with no file (deleted/renumbered/never-committed WP files) |

Root cause (A, B1): `finalize-tasks` seeds `planned` through the transactional, topology-routed writer, so coord-topology Missions wrote their lane events to a coordination branch that was never projected into the dossier commit that landed on `main`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Seed missing WP status events for a Mission (Priority: P1)

As an operator, I run one repair against a Mission (or the whole corpus) and every WP file that the snapshot is missing receives a `planned` seed event, so the snapshot WP count equals the file count.

**Why this priority**: it is the core fix; without it no Mission can be drained.

**Independent Test**: build a fixture Mission with three WP files and an event log that seeds only one; run the repair; the snapshot holds three WPs, the pre-existing WP's state is untouched, and a second run appends nothing.

**Acceptance Scenarios**:

1. **Given** a Mission whose log lacks lane events for WP02 and WP03, **When** the repair runs, **Then** WP02 and WP03 each gain exactly one `planned` seed and the snapshot counts all WPs.
2. **Given** a Mission with no `status.events.jsonl`, **When** the repair runs, **Then** the log is created on the Mission's resolved primary status surface and seeded for every WP file.
3. **Given** a WP carrying only a `WPCreated` row, **When** the repair runs, **Then** it is seeded (a lifecycle row is not a lane event).
4. **Given** an already-consistent Mission, **When** the repair runs, **Then** nothing is written (idempotent).
5. **Given** `--dry-run`, **When** the repair runs, **Then** it reports the would-seed plan and writes nothing.

### User Story 2 - Finished Missions land in a terminal lane (Priority: P1)

As an operator, when a Mission is finished, the seeded WPs land in `done` (seed + forced `done` with a reason naming the evidence), so progress for that Mission reads 100%, not 0%.

**Why this priority**: seeding a finished Mission as `planned` records a falsehood (operator ruling).

**Independent Test**: a fixture Mission with `meta.json` `merged_at` set and no log; after repair every WP is `done`, each `done` event is `force: true` with a reason citing the evidence.

**Acceptance Scenarios**:

1. **Given** `meta.json` carries `accepted_at` or `merged_at`, **When** the repair runs, **Then** every seeded WP is driven to `done`.
2. **Given** a Mission with no such field but listed in an operator-supplied evidence manifest with a reason, **When** the repair runs with that manifest, **Then** its seeded WPs are driven to `done` and the reason is recorded on the event.
3. **Given** a Mission with no terminal evidence, **When** the repair runs, **Then** seeded WPs stay `planned`.
4. **Given** a WP already in a non-terminal lane from real events, **When** the repair runs on a finished Mission, **Then** that WP is not rewritten (only seeded WPs are driven).

### User Story 3 - Drain this repository's corpus and keep it drained (Priority: P2)

As a maintainer, the committed corpus is repaired and a gate fails CI when any committed Mission's snapshot disagrees with its WP files, except recorded, reasoned exemptions for snapshot-only WPs.

**Why this priority**: it closes #5579's exit condition and stops regrowth.

**Independent Test**: the corpus gate passes on the branch; injecting a WP file without an event into a copy of a Mission makes it fail.

**Acceptance Scenarios**:

1. **Given** the repaired corpus, **When** the gate runs, **Then** zero non-exempt Missions disagree.
2. **Given** a bucket-C Mission, **When** the gate runs, **Then** it is accepted only via an exemption entry that names the Mission, the orphan WP ids, and a reason.
3. **Given** an exemption whose Mission now agrees (or no longer exists), **When** the gate runs, **Then** it fails as a stale exemption (shrink-only).

### Edge Cases

- A WP file with malformed frontmatter or no `work_package_id` is reported and skipped, never guessed.
- A coord-topology Mission whose coordination branch no longer exists must not abort; the repair writes to the resolved primary surface (degrade, as the cutover migration does), and never mints a coordination branch.
- Missions under the frozen archive root are never written (byte-identity gate).
- Snapshot-only WPs (bucket C) are never "fixed" by inventing files or deleting events.
- A mission whose `meta.json` still names a deleted coordination branch: the CLI `agent status materialize` refuses it (#5286). The repair and the corpus gate use the in-process reducer on the primary directory (which does not consult the coordination branch) and are tested against such a fixture.
- Corpus terminal evidence present today: `accepted_at` on 12 and `merged_at` on 7 of the disagreeing Missions; the rest need explicit evidence-manifest entries (dossier commit / merged PR) or stay `planned`.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Gap detection | As an operator, I want each Mission's file-WP set compared with its snapshot-WP set (both directions) so that the repair knows what to seed and what to report. | High | Open | [build] | no — paired with the consistent-Mission row on the same fixture |
| FR-002 | Planned seeding | As an operator, I want every file WP absent from the snapshot to get one `planned` seed event so that the snapshot counts it. | High | Open | [build] | no |
| FR-003 | Terminal seeding | As an operator, I want seeded WPs of a finished Mission driven to `done` with `force: true` and an evidence-citing reason so that progress stays truthful. | High | Open | [build] | no — paired with the no-evidence row that stays `planned` |
| FR-004 | Terminal evidence | As an operator, I want "finished" decided only by `meta.json` `accepted_at`/`merged_at` or an explicit evidence-manifest entry with a reason so that nothing is marked done by guesswork. | High | Open | [build] | no |
| FR-005 | Idempotence and dry-run | As an operator, I want a re-run to append nothing and `--dry-run` to write nothing so that the repair is safe to repeat. | High | Open | [build] | no |
| FR-006 | Surface-safe writes | As an operator, I want seeds written through the existing migration writer (C-002) onto the resolved primary status surface, degrading (not aborting, not minting a branch) when a coordination branch is gone, so that no second event-log writer appears. | High | Open | [build] | no |
| FR-007 | CLI surface | As an operator, I want a `spec-kitty migrate` subcommand with `--mission`, `--dry-run`, `--evidence-manifest` and `--json` so that the repair is reachable through the canonical CLI. | High | Open | [build] | no |
| FR-008 | Corpus drain | As a maintainer, I want this repository's committed Missions repaired with an evidence manifest so that the disagreement count reaches zero (modulo exemptions). | High | Open | [build] | no |
| FR-009 | Corpus parity gate | As a maintainer, I want a test that fails when a committed Mission's snapshot WP-id **set** differs from its WP-file id set, with a reasoned, shrink-only exemption list for snapshot-only WPs, so that the gap cannot regrow. It lives beside `tests/specify_cli/migration/test_dogfood_corpus_backfilled.py` (not a new architectural file). | High | Open | [ratchet] | no — self-mutation control: an injected unseeded WP must fail it |
| FR-010 | Deterministic seed ids | As an operator, I want seed and forced-done event ids derived deterministically (as `backfill_runtime_state._seed_id` does) and filtered against ids already on disk so that idempotence holds by construction, not by re-scanning lanes. | High | Open | [build] | no |
| FR-011 | Forced-done validity | As a maintainer, I want every forced `planned → done` seed to pass `validate_transition` (force, non-empty actor and reason, `evidence=None`) in a test, and every `done`-evidence reader (acceptance, Zeitgeist bridge) to tolerate it, so that the seeded log is a legal FSM history. | High | Open | [build] | no |
| FR-012 | Runtime-backfill interleaving | As an operator, I want running `migrate backfill-runtime-state` before or after this repair to leave seeded WPs unchanged so that the two seeders cannot fight. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Corpus gate cost | The corpus parity gate completes in under 15 s on this repository's ~550 Missions on a developer laptop. | Performance | Medium | Open |
| NFR-002 | Quality gates | New code passes `ruff check`, `ruff format --check --force-exclude`, and `mypy --strict` with zero findings; every function has cyclomatic complexity ≤ 15. | Maintainability | High | Open |
| NFR-003 | Coverage | New code reaches ≥ 90% line coverage from tests added in the same mission. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Reducer unchanged | Neither the local reducer wrapper nor `spec_kitty_events` reduction semantics change (ADR `2026-06-07-3`). | Technical | High | Open |
| C-002 | Single writer | No new entry in `status._unsafe.ALLOWED_CALLERS`, the status-events writes-gate ledgers, or the legacy-emit/authority gates. The write lives inside the existing `migration/backfill_runtime_state.py` writer (same lock, same `append_event_stream_atomic_verified` call); gap planning lives in a pure, write-free module. | Technical | High | Open |
| C-003 | Migration actor | Seed and forced-done events use an actor with the `migration:` prefix so consolidation attribution windows ignore them (FR-011 of mixed-lane-authorship-soundness). | Technical | High | Open |
| C-004 | No #5581 dependency | The mission must not import or depend on files introduced by unmerged PR #5581. | Process | High | Open |
| C-005 | Archive freeze, sanctioned | `kitty-specs/` is a byte-frozen root (`tests/architectural/test_archive_root_byte_identical.py`). New `status.events.jsonl` files are additions (allowed). Every *modified* frozen file (an existing log, a regenerated `status.json`) is listed in `_OPERATOR_SANCTIONED_CORRECTIONS` with a dated operator-decision comment citing this mission's Decision Moment `01M41NVK…`, following the #5258 precedent. `status.json` is regenerated only where it already exists. | Process | High | Open |

### Key Entities

- **WP gap**: per Mission, `files_only` (WP files without snapshot rows) and `snapshot_only` (snapshot rows without files).
- **Terminal evidence**: a reason a Mission is finished — `meta.json` `accepted_at`/`merged_at`, or an evidence-manifest entry `{mission_slug, reason}`.
- **Evidence manifest**: an operator-authored YAML file mapping Mission slugs to terminal-evidence reasons.
- **Parity exemption**: a committed record `{mission_slug, snapshot_only_wp_ids, reason}` that the corpus gate accepts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the mission branch, zero committed Missions have a snapshot WP-id set different from their WP-file id set, other than recorded bucket-C exemptions (≤ 7). — [build] · no-op passable: no
- **SC-002**: A second run of the repair over the drained corpus appends 0 events. — [build] · no-op passable: no
- **SC-003**: Every finished Mission (terminal evidence present) reads 100% done after the repair. — [build] · no-op passable: no
