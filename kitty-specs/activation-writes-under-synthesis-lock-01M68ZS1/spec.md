# Mission Specification: Activation writes under the charter synthesis lock

**Mission Branch**: `issue-6719-activation-writes-under-synthesis-lock`
**Created**: 2026-10-31
**Status**: Draft
**Input**: #6719 — "Activation writes race charter synthesis: activate/deactivate config and the activation-ledger migration's manifest stamp run outside the synthesis lock" (residual of mission `synthesis-record-integrity-01M5ZBC9` / #6453). Grounding: `<mission_dir>/research.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A deactivation is never undone by a synthesis run (Priority: P1)

An operator deactivates a doctrine artifact (`spec-kitty charter deactivate directive 001-...`) while a
`charter synthesize` run is appending the artifacts it created to the activation config. Today one of the
two writers loses: the deactivation either refuses with `precondition_changed` (the artifact stays in
force — "synthesis puts it back") or writes a stale document over the append. With the fix the two writes
are serialized by the run-wide synthesis lock, so the artifact stays deactivated **and** the created
artifact stays appended.

**Why this priority**: It is the issue's first acceptance criterion and the user-visible symptom: an
explicit governance decision silently failing to take effect while an unrelated run is in flight.

**Independent Test**: Deterministic two-writer test — writer A pauses at its activation write, writer B runs
the real synthesis append; before the fix one writer fails (`precondition_changed`) or drops the other's
write, after the fix both writes survive and the artifact stays deactivated
(`tests/charter/activation/test_activation_writes_under_synthesis_lock.py`).

**Acceptance Scenarios**:

1. **Given** a migrated project whose ledger has `activated_directives: [001-...]` and
   `activated_tactics: [existing-tactic]`, **When** a `charter deactivate` of `001-...` races an
   `append_synthesized_activations` of `new-tactic`, **Then** both effects are on disk: the deny entry
   records the deactivation and `new-tactic` is appended.
2. **Given** another thread holds the synthesis lock, **When** the operator runs `charter deactivate`,
   **Then** the command waits, then refuses with `CHARTER_SYNTHESIS_LOCK_HELD` and writes nothing
   (the artifact is still active, the ledger bytes unchanged).
3. **Given** the same held lock, **When** the operator runs `charter activate`, **Then** the same coded
   refusal is produced, in text and under `--json`.

### User Story 2 - The migration's manifest stamp keeps concurrent synthesis entries (Priority: P1)

An operator (or `spec-kitty upgrade`) runs the activation-ledger migration while a synthesis run is writing
the synthesis manifest. The migration's `_stamp_manifest` reads and rewrites the whole manifest; today a
concurrent synthesis write that lands between its read and its write is dropped, so artifacts the run just
recorded vanish from `synthesis-manifest.yaml` (and the bundle hash describes a manifest that no longer
exists). With the fix the migration's stamp is under the same lock.

**Why this priority**: It is the issue's second acceptance criterion; it is data loss in the artifact
registry that later runs read as authoritative.

**Independent Test**: Two-writer test on `synthesis-manifest.yaml`: a synthesis run's manifest write
(under the run-wide lock, as the command holds it) interleaves with `apply_ledger_migration`; the entry
added concurrently is still present after the stamp.

**Acceptance Scenarios**:

1. **Given** a project with a stampable synthesis manifest, **When** `apply_ledger_migration` stamps the
   manifest while a synthesis run writes a new manifest entry, **Then** the new entry is present and the
   manifest validates.
2. **Given** another thread holds the synthesis lock, **When** `apply_ledger_migration` is applied,
   **Then** it refuses with a coded lock error and nothing in the bundle changes (the ledger write, the
   stamp and the legacy-key strips are one unit).

### Edge Cases

- A read-only run (`charter synthesize --dry-run`, `charter resynthesize --list-topics`) takes no lock and
  must stay unaffected.
- The lock is re-entrant: `charter deactivate --resynthesize` (which runs a synthesis inside the command)
  and the nesting `manager.activate` → `restamp_bundle_hash` must not deadlock.
- Outside a git repository the lock lives at `.kittify/runtime/locks/charter-synthesis.lock`; when git
  cannot be invoked at all the writers must refuse (`CHARTER_SYNTHESIS_LOCK_UNAVAILABLE`) rather than write
  unlocked.
- A no-op activation (already active / already deactivated) writes nothing and must not need the lock's
  full wait: it still takes it (the read must be serialized) but performs no write.
- `charter activate --preset` computes its plan from a read; the plan and the write are one unit.
- The cascade path writes several artifacts in one command; each write is serialized, and no write may be
  based on a read that predates another writer's commit.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|-----------|----------|--------|----------|-----------------|
| FR-001 | The positional `charter activate` / `charter deactivate` config read-modify-write runs under the run-wide synthesis lock | US1 | High | Accepted | [build] | no |
| FR-002 | `charter activate --preset` plans and applies under the same lock (the plan's read may not predate another writer's commit) | US1 | High | Accepted | [build] | no |
| FR-003 | The shared append-only primitive (`activation_engine.promote_activations`) takes the lock for its own read-modify-write, so every caller (synthesis append, org-required promotion) is serialized | US1 | High | Accepted | [build] | no |
| FR-004 | `apply_ledger_migration` holds the lock across the ledger write, the manifest stamp and the legacy-key strips, so `_stamp_manifest`'s read-modify-write cannot drop a concurrent synthesis entry | US2 | High | Accepted | [build] | no |
| FR-005 | A lock that cannot be acquired within the bounded wait surfaces as the coded refusal `CHARTER_SYNTHESIS_LOCK_HELD`, and an unplaceable lock as `CHARTER_SYNTHESIS_LOCK_UNAVAILABLE`, both with nothing written, in text and under `--json` | US1 | High | Accepted | [build] | no |
| FR-006 | A two-writer regression test exists for each race (deactivate vs synthesis append; migration stamp vs synthesis manifest write) and is red before the fix | US1, US2 | High | Accepted | [ratchet] | no |

### Non-Functional Requirements

| ID | Requirement (measurable threshold) | Category | Priority | Status |
|----|-----------------------------------|----------|----------|--------|
| NFR-001 | No new lock: the change introduces **0** new lock files, directories or lock modules; the existing `synthesis_lock` path set is used (asserted by the diff and by the tests reusing `synthesis_lock_path`). | Simplicity / Single canonical authority | High | Accepted |
| NFR-002 | A writer that cannot get the lock waits at most the existing bounded 10 s and then refuses; the test-only override keeps the refusal tests under **1 s** wall clock. | Reliability | High | Accepted |
| NFR-003 | Existing suite parity: the charter synthesis-lock, activation, preset and activation-ledger suites keep **100 %** of their current passes; no test is skipped, xfailed or weakened. | Test integrity | High | Accepted |

### Constraints

| ID | Constraint | Category | Priority | Status |
|----|------------|----------|----------|--------|
| C-001 | Reuse the existing run-wide synthesis lock (#6453); a second "activation lock" is prohibited as a second source of truth for mutual exclusion over the same files. | Technical / Governance | High | Accepted |
| C-002 | Read-only runs take no lock (`synthesis_lock_unless` stays the one owner of that policy); the fix must not make `--dry-run` or `--list-topics` wait. | Technical | High | Accepted |
| C-003 | The lock is re-entrant per thread: nesting (`deactivate --resynthesize`, manager → `restamp_bundle_hash`, migration inside a synthesis run) must not deadlock or self-refuse. | Technical | High | Accepted |
| C-004 | Out of scope: the compiled-catalog write reached from the post-write `recompile_or_notify` (a staleness question, re-derived by the next synthesis run, not a lost write); activation writers that are not one of the paths in FR-001–FR-004; and the pre-existing reds on `main` tracked by #6798, #6801, #6816 and #5927, which this mission neither fixes nor hides. | Scope | High | Accepted |

### Key Entities

- **Synthesis lock** — the run-wide, per-worktree, re-entrant file lock introduced by #6453
  (`charter.activation.synthesizer.synthesis_lock`); held by a writing synthesis run for the whole command.
- **Activation config** — the one activation surface the resolver picks: the activation ledger
  (`.kittify/charter/activation.yaml`) when migrated, else the legacy `config.yaml` / pointed
  `charter.yaml`. Its read-modify-write is the unit this mission serializes.
- **Synthesis manifest** — `synthesis-manifest.yaml`; its `bundle_content_hash` must describe the bundle
  that is on disk, so a stamp is only meaningful if no other writer is mid-flight.

## Success Criteria *(mandatory)*

- **SC-001**: The deactivate-vs-append two-writer test fails on `main` at `6f73b2a98e`
  (`precondition_changed`, no deny entry) and passes after the change, with both writers' effects on disk
  (positive control: the appended id is present, so the test cannot pass by writing nothing).
- **SC-002**: The migration-stamp-vs-synthesis two-writer test fails before the change (the concurrently
  written entry is gone) and passes after it.
- **SC-003**: With the lock held by another thread, `charter activate`, `charter deactivate` and
  `apply_ledger_migration` each refuse with `CHARTER_SYNTHESIS_LOCK_HELD` inside the bounded wait and leave
  the bundle byte-identical; `--json` emits the same code in the error envelope.
- **SC-004**: The pre-existing charter activation, preset, synthesis-lock and activation-ledger suites show
  no new failures; the diff adds no lock file, module or path.

## Assumptions

- The operator's 2026-10-27 ruling (file the remaining writers as their own issue rather than widen #6453)
  still stands: this mission is that issue, and the lock it takes is #6453's.
- `charter synthesize` / `charter resynthesize` already hold the lock for their whole run, so a writer that
  serializes against the lock is serialized against them; `restamp_bundle_hash` already does this and is the
  precedent for the pattern.

## Out of Scope

- Any new lock, lock scope, or lock ordering rule.
- The compiled-catalog write and its staleness (follow-up candidate, recorded in the PR's `## Deferred`
  only if it remains real).
- The unrelated pre-existing reds on `main` (#6798, #6801, #6816, #5927).
