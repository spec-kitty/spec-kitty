# Work Packages: System status actor

**Inputs**: Design documents from `kitty-specs/system-status-actor-01M67HTR/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md, data-model.md, contracts/system-actor.md, quickstart.md
**Issue**: [#6722](https://github.com/spec-kitty/spec-kitty/issues/6722)

**Tests**: required. This mission changes what is stored in an append-only log, so every
writer family needs a red-first test observed on the base, and the reader invariants need a
mixed-shape proof.

**Organization**: five work packages, each independently testable. WP01 is the authority the
other four consume; WP05 records the rule last, against proven behaviour.

**Prompt Files**: `/tasks/WP01-*.md` … `/tasks/WP05-*.md`.

## Path Conventions

- Source: `src/specify_cli/…`; tests: `tests/…`. Single Python package; the Java tree under
  `services/` and the schemas under `contracts/` are frozen (ADR `2026-10-29-1` D-9) and are
  not in any work package.

---

## Work Package WP01: The system actor authority (Priority: P0)

**Goal**: one builder and one new role value, plus the reader-invariant proof that the shape
never decides a verdict.
**Independent Test**: `build_system_actor("migration:x")` produces the 4-key dict; it crosses
`status.models.decode_actor` and `spec_kitty_events.diary.decode_actor` unchanged; a constructed
log reduces identically whether its seeds are strings or structured actors.
**Prompt**: `/tasks/WP01-system-actor-authority.md`
**Requirement Refs**: FR-001, FR-008, FR-011, FR-012, NFR-001, NFR-002, C-001, C-006

### Included Subtasks

T001 Add `ActorRole.SYSTEM` and `build_system_actor` to `status/actor.py`, exported through `status/__init__.py`
T002 [P] Extend the `decode_actor` / `ActorField` docstrings in `status/models.py` to name the system shape
T003 Red-first: the builder contract (4 keys, null profile/model, whole `tool`, blank refused) in `tests/status/test_system_actor_6722.py`
T004 Red-first: the decoder pin — `status.models.decode_actor` and `spec_kitty_events.diary.decode_actor` both keep a `role: "system"` actor
T005 Red-first: the reader-invariant matrix and the mixed-shape reduction over a constructed log

### Implementation Notes

- `build_system_actor` takes **only** `tool`; `profile` and `model` are literals, so "nothing is
  invented" is a signature guarantee, not a convention.
- The builder must not call `parse_agent_boundary_string`: `migration:backfill_runtime_state`
  would be split into a tool and a model.
- `role_for_hop` stays a two-value answer; nothing routes a lane hop through `system`.
- Do **not** touch `build_status_actor`, `compose_status_actor` or `actor_from_option` — the
  agent and operator paths are #6400's and must not drift.

### Parallel Opportunities

T002 runs alongside T001. T003–T005 are red-first against T001's absence.

### Risks

The mixed-shape reduction test must be a *reader* proof (constructed events), not a writer
proof, so it stays honest while WP02–WP04 are still unimplemented.

---

## Work Package WP02: Bootstrap and recovery writers (Priority: P1)

**Goal**: the `finalize-tasks` seed and the recovery catch-up record the system actor.
**Independent Test**: run the bootstrap seam and the recovery sweep on a fixture mission; each
new event carries `{tool: "finalize-tasks"|"recovery", role: "system", profile: null, model: null}`
and the snapshot `actor` slot still reads the bare tool.
**Prompt**: `/tasks/WP02-bootstrap-and-recovery-writers.md`
**Requirement Refs**: FR-002, FR-003

### Included Subtasks

T001 Red-first: the bootstrap seed's stored actor, through `bootstrap_status` on a fixture mission
T002 Red-first: the recovery catch-up's stored actor, through the recovery sweep
T003 Move `status/bootstrap.py` onto the builder
T004 Move `lanes/recovery.py` onto the builder, keeping `RECOVERY_ACTOR` the identity string its `GuardContext` call needs

### Implementation Notes

- `RECOVERY_ACTOR` stays a `str`: `lanes/recovery.py:80` passes it to `GuardContext(actor=...)`,
  and `tests/lanes/*` compare it. The emit site wraps it.
- Update the existing assertions that read the stored actor
  (`tests/lanes/test_implementation_recovery.py`, `tests/specify_cli/lanes/test_recovery.py`).

### Parallel Opportunities

The two writers are independent of each other once WP01 lands.

### Risks

The recovery sweep swallows exceptions by design; a test that asserts nothing was written must
also assert the sweep ran, or it passes vacuously.

---

## Work Package WP03: Consolidation bookkeeping, the override and both attestations (Priority: P1)

**Goal**: every consolidation-written status event carries the system actor, while the
`ReviewOverride` delta slot keeps its pinned string shape and the attestations keep their
`policy_metadata` identity.
**Independent Test**: mark a merged work package done, record a review-artifact skip and both
attestations on a fixture; each event's actor is the system dict with the right `tool`, and the
independent-review read still ignores the attestations.
**Prompt**: `/tasks/WP03-consolidation-writers.md`
**Requirement Refs**: FR-004, FR-005, FR-006, C-005

### Included Subtasks

T001 Red-first: the approval replay and the done mark store the system actor
T002 Red-first: the done-write refusal probe builds the same shape as the real write
T003 Red-first: the review-artifact override annotation — structured event actor, string `ReviewOverride.actor`
T004 Red-first: both attestations store the system actor and stay out of the reviewer read
T005 Move `done_bookkeeping.py`, `preflight.py`, `approved_attestation.py` and `canceled_attestation.py` onto the builder

### Implementation Notes

- Introduce one `"merge"` identity constant in `done_bookkeeping.py` and use it at both emits and
  at the `preflight.py` probe, so the probe and the write cannot drift.
- `ReviewOverride`'s four `str` fields are a pinned shape (`status/models.py:633`); only the
  event's `actor` changes.
- Update the existing assertions that read the writer's request
  (`tests/consolidation/test_merge_done_recording.py`, `tests/specify_cli/consolidation/test_done_evidence_snapshot.py`,
  `tests/specify_cli/cli/commands/test_merge.py`).

### Risks

The override site reads one variable into two different types; splitting it is the fix, casting it is not.

---

## Work Package WP04: Migration seed writers and the two compatibility seams (Priority: P1)

**Goal**: the three in-process backfills write structured seeds that still classify as seeds,
and a corpus seeded before the change still verifies.
**Independent Test**: each backfill's seed carries `tool: "migration:<id>"` and `role: "system"`;
`is_migration_actor` is true for it; a log whose string seed rows predate the change verifies
`ok`; a seed with a *different* identity still fails verification.
**Prompt**: `/tasks/WP04-migration-seeds-and-seams.md`
**Requirement Refs**: FR-007, FR-009, FR-010, FR-012, C-003

### Included Subtasks

T001 Red-first: each of the three backfills stores the system actor, and `is_migration_actor` is true for it
T002 Red-first: Seam A — the per-backfill seed predicate recognises both shapes and only its own identity
T003 Red-first: Seam B — a pre-change seed row verifies `ok`, and a different identity still fails
T004 Move the three writers onto the builder, keeping each `migration:` constant the identity string
T005 Make Seam A and Seam B shape-blind; update the existing migration tests that read the stored actor

### Implementation Notes

- The constants (`WP_STATUS_BACKFILL_ACTOR`, `BACKFILL_ACTOR`) keep their value as the identity
  string; the emit sites wrap them. Tests and seams then compare identities, never shapes.
- Seam A stays narrower than `status.models.is_migration_actor`: it answers "this backfill's
  seed", not "any seed". Document that it projects rather than widens.
- Seam B tolerates an actor-shape-only difference. Both shapes must project to the same
  identity; anything else stays a hard mismatch.
- Update `tests/unit/migration/test_wp_status_backfill.py`,
  `tests/unit/migration/test_backfill_runtime_state.py`, `tests/migration/test_birth_cutover.py`,
  `tests/migration/test_verdict_provenance_backfill.py`.

### Risks

The highest-risk WP: `verify_backfill` is fail-closed, so a missed tolerance turns a healthy
mission into a terminal abort. The paired negative test (different identity → mismatch) is not
optional.

---

## Work Package WP05: Docs and changelog (Priority: P2)

**Goal**: replace the "Still strings" boundary with the system-actor rule, and record the change.
**Independent Test**: read `docs/architecture/status-model.md` — it names `implementer`,
`reviewer` and `system`, lists the system writers and the null-profile rule; the changelog has
an `[Unreleased]` entry citing `(#6722)`.
**Prompt**: `/tasks/WP05-docs-and-changelog.md`
**Requirement Refs**: FR-013, SC-005

### Included Subtasks

T001 Rewrite the "Still strings" paragraph in `docs/architecture/status-model.md` as the system-writer rule
T002 Extend the role paragraph with the third value and say what sets it
T003 Add the `[Unreleased]` changelog entry (`docs/changelog/CHANGELOG.md`)
T004 Run `check_docs_freshness --ci` and `tests/architectural/test_no_legacy_terminology.py`

### Risks

The docs index/freshness script touches generated files shared with other agents; regenerate only
what this diff changes and verify with `--ci` rather than rebuilding the whole reference.
