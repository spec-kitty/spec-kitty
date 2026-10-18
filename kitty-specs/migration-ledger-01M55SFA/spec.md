# Mission Specification: Explicit two-partition migration ledger

**Mission Branch**: `issue-5230-migration-ledger-impl`
**Created**: 2026-10-17
**Status**: Draft
**Input**: Spike #5230 (epic #2933), accepted design ADR `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`. Operator rulings: (1) full ledger redesign, (2) hard cutover with no dual-write mirror, (3) a checked-in order manifest, (4) detect-gated clone-local backfill. Children: #6356 (#A ledger module), #6357 (#B order manifest + build gate), #6358 (#C ledger-diff selection), #6359 (#D drift audit), #6360 (#E visibility), #6361 (#F backfill), #6362 (#G docs).

## Summary

The upgrade subsystem records what has run in the `migrations.applied` block of the tracked,
pushed `.kittify/metadata.yaml`, and decides what to run from **two** authorities: a version
window (`from_v < target <= to_v`) and the applied record. The accepted design (ADR
`2026-10-17-1`) retires both in favour of an explicit, two-partition **ledger** that is the
single execution authority for "already applied", and makes selection a plain **ledger-diff**.

This mission implements that design. It is grounded entirely in the ADR and does not re-decide
any of its choices. Concretely:

- A new module `src/specify_cli/upgrade/ledger.py` owns two append-only JSONL ledgers,
  partitioned by whether a migration's effect is **tracked** (`.kittify/migration-ledger.jsonl`,
  tracked) or **clone-local** (`.kittify/migrations/clone-local.jsonl`, inside the already-ignored
  `.kittify/migrations/` surface). `clone_local_effect` stops being a reselection trigger and
  becomes the **routing key** that picks which ledger a record reads from and writes to.
- Selection becomes `pending = declared-order ∖ applied-in-the-applicable-partition`, then
  filtered by `detect()`/`can_apply()`. The version window is retired as the applied authority,
  and the #6233 compensation machinery (`_clone_local_selected_below_window`, the sub-window
  reselection in `reselect_when_recorded`) is deleted. `detect()` survives **only** as the
  pre-`apply()` idempotency guard, never as the selection authority.
- A single checked-in **order manifest** is the order authority, enforced by a new
  `tests/architectural/` build-time check (exactly-once, resolves, version-monotonic, ≤1
  `runs_first`). `Version(target_version)` is demoted to a monotonicity cross-check.
- Each applied record carries an author-declared `identity` and a `content_hash`; a recorded
  migration whose current source hash differs is flagged as **drift** and surfaced read-only.
  Drift is **never** acted on automatically.
- A visibility surface (`spec-kitty doctor migrations` and `spec-kitty upgrade --list-applied`)
  renders the declared/applied/pending sets, the tracked/clone-local partition, and drift flags,
  both consuming the one pending-source `VersionDetector.applicable_migrations`.
- Adoption is a **hard cutover**: a one-way backfill reads the existing
  `metadata.yaml.applied_migrations` into the ledgers (tracked records unconditionally,
  clone-local records only when `detect()` confirms the effect present on this checkout), then
  `applied_migrations` is removed as the authority — **no dual-write mirror**.

**Stakeholders.** Maintainers of the `spec-kitty upgrade` subsystem and anyone authoring a new
migration (the primary readers); every consumer of `spec-kitty upgrade` (a teammate on a fresh
clone gains their own local git setup; an operator can see and trust what ran); the acceptance-QA
owners who co-own the scenarios this mission makes pass.

**Acceptance basis.** The nine scenarios in `tests/scenarios/upgrade/migration-ledger.feature`.
Two already gate the nightly (reusing bound steps); the seven `@wip` scenarios are what this
mission makes pass by binding their ten new acceptance-jvm steps and building the read surface.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upgrade runs exactly the work a project has not yet had (Priority: P1)

`spec-kitty upgrade` runs each declared migration exactly when the ledger shows it has not
succeeded on this project (in the applicable partition), independent of where the version stamp
sits. A current project is a no-op; a migration stranded by an earlier interrupted run or a
pulled `metadata.yaml` is picked up and finishes; a tracked effect already present is not redone.

**Why this priority**: This is the core authority change (ADR §1, §3). It removes the
version-window strand and is the foundation every other story depends on.

**Independent Test**: On a fully-migrated, committed project, two successive `upgrade --yes` runs
make no commit and change no managed file. On a project with one declared migration absent from
the ledger, `upgrade --yes` applies exactly that one and a re-run is a no-op.

**Acceptance Scenarios** (feature file titles):

1. **Given** a committed, already-set-up project, **When** I run `upgrade --yes` twice, **Then**
   nothing changes and no commit is made. — *"Upgrading a project that is already current changes
   nothing."*
2. **Given** a project declaring a setup step the ledger has not recorded, **When** I run
   `upgrade --yes`, **Then** that step takes effect and a re-run does nothing further. — *"An
   interrupted upgrade finishes the job when re-run."*
3. **Given** a committed project whose tracked refresh already arrived with the pull, **When** I
   run `upgrade --yes`, **Then** the tracked file is unchanged and no commit is made. — *"A tracked
   refresh that already arrived with the pull is not redone."*

---

### User Story 2 - A fresh clone gains its own local git setup (Priority: P1)

A teammate's freshly pulled clone carries the shared record that a clone-local setup "ran"
elsewhere, but not the local effect (`.git/info/exclude`, `git config --local`, `.git/hooks`).
Because that record lives only in the per-clone ledger — which does not travel — the clone has no
record of its own, so ledger-diff selects the migration, it applies, and it records into *this*
clone's per-clone ledger. A second run is a no-op.

**Why this priority**: This is the #6233 correctness hole the whole redesign is built to close,
resolved structurally by the partition rather than by per-site reselection logic (ADR §1).

**Independent Test**: Seed a clone whose tracked state records the clone-local migration applied
but whose local effect is absent; `upgrade --yes` installs the local effect here; a second
`upgrade --yes` makes no change and no commit.

**Acceptance Scenarios**:

1. **Given** a freshly pulled clone whose shared records show its local git setup ran but whose
   own local git state is missing, **When** I run `upgrade --yes`, **Then** this clone's own local
   git setup is in place. — *"A teammate's clone gets its own local git setup even though the
   project was already set up elsewhere."*
2. **Given** the same clone after one upgrade, **When** I run `upgrade --yes` again, **Then**
   nothing changes further and the working tree stays clean. — *"Re-running upgrade on a clone that
   already has its local setup changes nothing further."*

---

### User Story 3 - An old project adopts the ledger without redoing work (Priority: P1)

A project set up before the ledger existed is cut over in one direction: its existing
`metadata.yaml.applied_migrations` is read into the ledgers (tracked records unconditionally,
clone-local records only where `detect()` confirms the effect here), after which
`applied_migrations` is no longer the authority. Work already done is recognised and not redone.

**Why this priority**: Without a correct backfill the cutover would re-run migrations on every
existing project — a regression of the no-op contract (guard G-2).

**Independent Test**: Upgrade a pre-ledger project fixture; assert the previously-applied
migrations are recorded in the ledger and not re-run, and no commit is made.

**Acceptance Scenarios**:

1. **Given** a project set up before Spec Kitty recorded its applied setup steps, **When** I run
   `upgrade --yes`, **Then** the work already done is not done again and no commit is made. — *"A
   project upgraded from before the ledger existed keeps its already-done work recognized."*

---

### User Story 4 - I can see and trust what ran (Priority: P2)

An operator can ask the CLI what migrations ran, in what order, in which partition, and whether a
clone-local step is actually present on this checkout or merely recorded; and the CLI flags any
migration whose content changed since it ran. The reports mutate nothing.

**Why this priority**: Visibility and drift are the operator-facing value of an explicit ledger
(ADR §4, §5); they depend on the ledger (#A) and ledger-diff (#C) existing first.

**Independent Test**: With a populated ledger, the list surface prints the applied set in declared
order; on a seeded clone the report distinguishes "recorded elsewhere, not in place here"; on a
project whose recorded migration's source changed, the report flags drift. No run makes a commit.

**Acceptance Scenarios**:

1. **Given** a set-up project, **When** I run the applied-list surface, **Then** the setup steps
   that ran are listed in the order they ran. — *"I can ask what setup steps ran and in what
   order."*
2. **Given** a freshly pulled clone whose clone-local setup is recorded but absent here, **When** I
   run the migrations report, **Then** it shows that setup as recorded elsewhere but not yet in
   place here. — *"The report tells me whether a local-only step is actually in place here, not just
   recorded."*
3. **Given** a project whose recorded setup step no longer matches its current definition, **When**
   I run the migrations report, **Then** it flags that step as changed since it ran. — *"The system
   tells me when a setup step's content no longer matches what it ran."*

---

### User Story 5 - Execution order is declared and checked (Priority: P2)

The order migrations run in is a single checked-in manifest, and a build-time gate refuses a
manifest that is missing a registered migration, has a dangling entry, is not version-monotonic
(save annotated ties), or leads with more than one `runs_first` migration.

**Why this priority**: Makes order explicit and auditable and removes the unstable filename
tiebreak (ADR §2). Witnessed by an architectural gate rather than a CLI scenario.

**Independent Test**: The new `tests/architectural/` gate passes over the real manifest and fails
over planted fixtures for each rule (orphan, dangling, non-monotonic, two-runs_first).

**Acceptance Scenarios**:

1. **Given** the registered migration set and the order manifest, **When** the build-time gate
   runs, **Then** it passes only when every id appears exactly once, every entry resolves, the
   order is version-monotonic except where annotated, and at most one `runs_first` leads.

### Edge Cases

- **Retired pre-3.0 modules (#2322).** `SupersededMigration` (`detect()==False`) and neutralised
  no-ops stay in the manifest; ledger-diff selects them, `detect()==False` yields a `skipped`
  record, and that record keeps them from re-firing — behaviour identical to today, now anchored
  on the ledger.
- **Legacy-id aliases.** A constitution-era id and its charter-era id resolve to one ledger record
  via the legacy-id map applied **on read**.
- **Clone-local record ambiguous at backfill.** An existing `metadata.yaml` clone-local record does
  not prove the effect is present here (it was written into the shared file — the #6233 bug), so it
  is backfilled only when `detect()` confirms presence; otherwise it is left pending and re-applied
  (idempotent `apply()`).
- **A clone-local migration whose `detect()` cannot confirm presence** re-runs its idempotent
  `apply()` once at adoption — an accepted one-time cost.
- **Crash mid-append.** A full-file atomic rewrite leaves either the old or the new ledger, never a
  torn file.
- **Drift must never auto-reapply**, even when the hash mismatches — it is audit only.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Two-partition ledger module | US1,US2 | High | Open | [build] | no — new `ledger.py`; records read back in both partitions |
| FR-002 | `clone_local_effect` as routing key (not reselection trigger) | US2 | High | Open | [build] | no — clone-local records land in the per-clone ledger only |
| FR-003 | Append-only JSONL record shape `{id, applied_at, result, identity, content_hash, cli_version(, clone_local)}` | US1,US4 | High | Open | [build] | no — asserted by a round-trip read |
| FR-004 | Ledger-diff selection replaces the version window | US1 | High | Open | [build] | no — red-first: a sub-window stranded migration is selected |
| FR-005 | Remove #6233 machinery; `detect()` is idempotency guard only | US1,US2 | High | Open | [build] | no — `_clone_local_selected_below_window` deleted; `reselect_when_recorded` collapsed |
| FR-006 | Checked-in order manifest is the order authority | US5 | High | Open | [build] | no — `get_all` order becomes a manifest-index lookup |
| FR-007 | Build-time manifest gate (exactly-once / resolves / monotonic / ≤1 runs_first) | US5 | High | Open | [build] | no — planted fixtures fail each rule |
| FR-008 | `SupersededMigration` + neutralised no-ops stay in the manifest, skipped via a `skipped` record | US1 | Medium | Open | [ratchet] | no — paired with a re-run no-op control |
| FR-009 | Legacy-id alias applied on read | US1,US3 | Medium | Open | [build] | no — a legacy and charter id resolve to one record |
| FR-010 | Drift: `identity` + `content_hash = sha256_digest(source)` per record; mismatch flagged, read-only, never auto-reapplied | US4 | High | Open | [build] | no — paired with a drifted-source fixture |
| FR-011 | Visibility surface (`doctor migrations` + `upgrade --list-applied`) via the single `detector.applicable_migrations` | US4 | High | Open | [build] | no — binds the three read-surface scenarios |
| FR-012 | Hard-cutover backfill: tracked unconditional, clone-local detect-gated; then remove `applied_migrations` as authority (no dual-write mirror); backfill ordered first | US3 | High | Open | [build] | no — pre-ledger fixture, prior work not redone |
| FR-013 | State contract: tracked ledger is a `GitClass.TRACKED` surface; per-clone ledger inside the ignored `.kittify/migrations/`; project `.gitignore` must not ignore the tracked ledger | US3 | High | Open | [build] | no — `git check-ignore` asserts the partition |
| FR-014 | Atomic single-writer ledger write (full-file atomic rewrite via `core/atomic`→`kernel.atomic`); `kernel.locks` named as the unbuilt extension point | US1 | High | Open | [build] | no — crash-safety / no torn file |
| FR-015 | Bind the ten new acceptance-jvm steps; lift `@wip` from the seven scenarios | US1,US2,US3,US4 | High | Open | [build] | no — `test_scenario_contract` + gating nightly |
| FR-016 | Docs: `CLAUDE.md` migration-authoring guidance and the ADR `2026-07-07-1` author checklist updated to the ledger model | — | Medium | Open | [build] | no — doc diff present |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Atomic, single-writer durability | Every ledger append is a full-file atomic rewrite; a crash leaves a valid old-or-new ledger, never a torn/partial file. No `O_APPEND`. | Reliability | High | Open |
| NFR-002 | No architectural layer / wheel change | All machinery stays in `src/specify_cli/upgrade/`; it consumes `kernel` (atomic, hashing) downward across the existing legal boundary only. The three enforced authorities — `pyproject.toml` wheel packages, the `landscape` fixture, `test_layer_rules.py` — are unchanged. | Compatibility | High | Open |
| NFR-003 | Back-compat (accepted cost) | After the hard cutover an older CLI reading a migrated project no longer finds applied-migration state in `metadata.yaml` and loses applied-migration visibility. This is a documented, accepted consequence; there is no dual-write mirror. | Compatibility | High | Open |
| NFR-004 | Behavioural parity for existing migrations | The set of migrations that actually run on a given project is unchanged except for the intended fixes (version-window strand, pulled-clone clone-local). Existing idempotency gates are extended, not weakened. | Reliability | High | Open |
| NFR-005 | Quality gates clean | New/changed code passes `ruff check`, `ruff format --check`, `mypy` with zero new issues; complexity ≤ 15; repeated literals hoisted. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single applied authority | The ledger is **the** execution authority for "already applied". Both `metadata.yaml.applied_migrations` and the version window are retired as applied authorities; `target_version` survives only as the ordering/monotonicity reference. | Technical | High | Open |
| C-002 | Placement fence | The ledger and its machinery live only in `src/specify_cli/upgrade/` (`ledger.py`). No new wheel package, no new `_DEFINED_LAYERS` entry. | Technical | High | Open |
| C-003 | `detect()` is the idempotency guard only | `detect()` is a pre-`apply()` belt-and-suspenders check, never the selection authority. | Technical | High | Open |
| C-004 | Drift never auto-reapplies | A content-hash mismatch is surfaced read-only; it gates and re-runs nothing. | Technical | High | Open |
| C-005 | Scope fence | The #2688 / #1794 / #2356 / #1172 follow-ups are separate missions. A cross-process ledger lock (`kernel.locks`) is a named extension point, **not** built here. | Technical | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A fully-migrated, committed project re-upgraded (twice) makes no commit and changes no managed file; a project with one unrecorded declared migration applies exactly that one and then no-ops. — [build] · no-op passable: no
- **SC-002**: A seeded fresh clone (clone-local recorded in the tracked state, effect absent) gains the local effect on `upgrade --yes`, and a second run changes nothing. — [build] · no-op passable: no
- **SC-003**: A pre-ledger project's prior migrations are backfilled into the ledger and not re-run; `metadata.yaml.applied_migrations` is removed as the authority with no dual-write mirror. — [build] · no-op passable: no
- **SC-004**: The build-time manifest gate passes over the real manifest and fails over a planted orphan, a dangling entry, a non-monotonic order, and a two-`runs_first` fixture. — [build] · no-op passable: no
- **SC-005**: The visibility surface prints applied-in-declared-order, distinguishes recorded-elsewhere-vs-in-place-here, and flags a drifted migration — all read-only. — [build] · no-op passable: no
- **SC-006**: `_clone_local_selected_below_window` is deleted and `reselect_when_recorded` collapses to a ledger lookup, with no behavioural regression in the extended idempotency/selection gates. — [ratchet] · no-op passable: no
- **SC-007**: The seven `@wip` scenarios in `migration-ledger.feature` pass with their ten steps bound; all nine gate the nightly; `tests/architectural/test_scenario_contract.py` stays green. — [build] · no-op passable: no
- **SC-008**: No change to `pyproject.toml` wheel packages, the `landscape` fixture, or `test_layer_rules.py`. — [ratchet] · no-op passable: no

## Child-issue mapping

| Child | Deliverable | FRs | Depends on |
|-------|-------------|-----|------------|
| #6356 (#A) ledger module + dual-partition data model | 1 | FR-001, FR-002, FR-003, FR-013, FR-014 | — |
| #6357 (#B) order manifest + build-time check | 2 | FR-006, FR-007 | — |
| #6358 (#C) ledger-diff selection; retire version window + #6233 machinery | 3 | FR-004, FR-005, FR-008, FR-009 | #A, #B |
| #6359 (#D) drift identity/checksum on apply | 4 | FR-010 | #A |
| #6360 (#E) visibility surface | 5 | FR-011 | #A, #C |
| #6361 (#F) adoption backfill (hard cutover, detect-gated clone-local) | 6 | FR-012, FR-013 | #A |
| #6362 (#G) docs / ADR follow-through | 7 | FR-016 | #A–#F |
| (acceptance, cross-cutting) bind steps, lift `@wip` | — | FR-015 | #A, #C, #E, #F |

## Out of scope

- The explicit per-migration lock for concurrent cross-process upgrade — named as the
  `kernel.locks` extension point in the ADR, deliberately not built now (single-writer today).
- A dual-write / mirror of applied state back into `metadata.yaml` for old-CLI compatibility —
  explicitly rejected by the hard-cutover ruling.
- The follow-up issues #2688, #1794, #2356, #1172 — separate missions.
- Any change to the architectural layer rules or the wheel package set.
- Per-migration `after:`/`before:` DAG ordering — rejected by the ADR in favour of the single
  ordered manifest.

## Open Questions

- **OQ-1 (read-surface command).** The ADR names **both** `spec-kitty doctor migrations` and
  `spec-kitty upgrade --list-applied`. `/plan` settles which is canonical, whether both ship, and
  how responsibilities split (list vs drift/partition health). The feature scenarios are phrased
  command-agnostically so either resolution binds cleanly.
- **OQ-2 (manifest file format/location).** The ADR fixes the manifest as a changelog-style ordered
  list of `migration_id`s but not its exact path/format. `/plan` picks the file and the
  annotation syntax for intentional version-monotonicity ties.
- **OQ-3 (`content_hash` source scope).** `content_hash = sha256_digest(<migration module source
  bytes>)`; `/plan` fixes whether that is the single module file or a declared set for
  multi-file migrations, and how `identity` defaults/overrides interact with the hash.
