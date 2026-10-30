---
title: 'ADR: the applied-migration ledger is an explicit, two-partition record that is the execution authority for what has run'
description: 'An explicit two-partition migration ledger replaces metadata.yaml and the version window as the authority for what has run; selection becomes ledger-diff.'
status: Accepted
date: '2026-10-17'
updated: '2026-10-25'
---

**Status:** Accepted (2026-10-17).

**Date:** 2026-10-17

**Deciders:** Stijn Dejongh (operator).

**Technical Story:** epic #2933 (explicit, machine-readable migration ledger); spike #5230
(decide ledger location/authority, declared ordering, selection, drift, visibility, adoption,
and the module/directory placement). Builds directly on #6233 / PR #6350 (`clone_local_effect`
on `BaseMigration`, the per-clone reselection seam) and its ADR amendment. Related: ADR
[2026-10-04-4](2026-10-04-4-upgrade-writes-project-global-state-once.md) (upgrade writes
project-global state once), ADR [2026-10-07-1](2026-10-07-1-upgrade-never-runs-mission-state-repair.md).

**Reader:** a maintainer working on the `spec-kitty upgrade` migration subsystem, or authoring
a new migration.

**Supersedes / extends:** ADR
[2026-07-07-1](../3.x/2026-07-07-1-ignored-surface-backfill-migration-pattern.md), specifically
its **Amendment 2026-10-17 (#6233)**, which introduced the per-clone reselection seam as an
interim fix and explicitly deferred "the explicit, machine-readable clone-local ledger that
would record the effect's presence directly" to epic #2933. This ADR is that deferred design.

---

## Context and Problem Statement

The upgrade subsystem records which migrations have run in the `migrations.applied` block of
the tracked, pushed `.kittify/metadata.yaml` (`ProjectMetadata.applied_migrations`,
`src/specify_cli/upgrade/metadata.py:71`). Two authorities decide whether a migration runs:

1. The **version window** — `MigrationRegistry.get_applicable` selects a migration when
   `from_v < target <= to_v` (`src/specify_cli/upgrade/registry.py:119`).
2. The **applied record** — the runner skips a migration already recorded applied
   (`src/specify_cli/upgrade/runner.py:357`, `ProjectMetadata.has_migration`
   `metadata.py:276`).

This design has accumulated three structural faults:

- **The ledger is the wrong authority for clone-local effects (#6233).** A migration whose
  effect lives *outside* version control — `.git/info/exclude`, `git config --local`,
  `.git/hooks` — records into the shared, pushed `metadata.yaml`. The record propagates to
  every clone, but the effect does not. A pulled clone inherits the record without the effect
  and skips the migration forever. PR #6350 patched this with `clone_local_effect`
  (`src/specify_cli/upgrade/migrations/base.py:122`) plus a version-window reselection branch
  (`registry.py:175 _clone_local_selected_below_window`) and a skip-gate override
  (`base.py:135 reselect_when_recorded`). That is a workaround for the authority being in the
  wrong file.

- **The version window strands migrations.** Anything below `from_v` is never reconsidered —
  the very reason the clone-local reselection branch and the symlink fail-closed path
  (`runner.py:366-393`) had to be bolted on. A migration that failed, or that a pulled
  `metadata.yaml` reset, can be stranded past the window.

- **`metadata.yaml` is a multi-writer surface (#5229).** The applied list shares the file with
  the version stamp, the schema-capabilities stamp (`canonical_schema_capabilities`
  `metadata.py:364`), the environment block, `project_uuid` and operator keys. The
  merge-preserving `save` (`metadata.py:184-241`, `_merge_onto_disk :348`) *mitigates* the
  second-writer hazard; it does not remove it. A list that grows on every migration is the
  part most in need of leaving that contested file.

- **Execution order has an implicit tiebreak.** `get_all` sorts by `Version(target_version)`
  (`registry.py:79-80`); migrations that share a `target_version` (several exist, e.g. two
  `m_0_13_0_*`, two `m_2_1_2_*`) fall back to filename import order from
  `auto_discover_migrations` (`src/specify_cli/upgrade/migrations/__init__.py:46`) — an
  unstable, undeclared tiebreak.

Spike #5230 asked for a decisive design across six deliverables, led by a verdict on *where*
the ledger and its machinery live, defended against the enforced modularity SSOT.

## Decision Drivers

- Correctness for clone-local effects without per-site compensation logic.
- Remove the applied record from the `metadata.yaml` multi-writer surface.
- Make execution order and "what has run" explicit, auditable, and the single authority.
- Change no architectural layer rule and no wheel package set.

## Decision

### 0. Module / directory placement — stays in `specify_cli/upgrade`

The ledger and all its machinery **stay in `src/specify_cli/upgrade/`**. A new module
`src/specify_cli/upgrade/ledger.py` owns the ledger data, its read/write, and its authority.
It consumes two root-layer primitives *downward* across the existing, legal boundary: atomic
writes via `specify_cli/core/atomic.py:53 atomic_write` (itself a thin wrapper over
`kernel.atomic`), and content hashing via `kernel.content_digest.sha256_digest`
(`src/kernel/content_digest.py:19`).

**SSOT defense.** The enforced chain is
`kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`
(`tests/architectural/conftest.py:88-118` `landscape`; `tests/architectural/test_layer_rules.py:83-85`
`_DEFINED_LAYERS`; `pyproject.toml [tool.hatch.build.targets.wheel].packages`). Every reader of
applied-migration state is already in `specify_cli` and none is below it: `registry.py`,
`runner.py`, `detector.py:44`, `compat.py`, `core/version_checker.py`, the doctor family
(`cli/commands/_*_doctor.py`), `cli/commands/upgrade.py`, and migrations that read other
migrations' applied state (`m_3_2_6_*`, `m_4_0_0rc6_charter_pack_cutover.py`,
`m_3_1_1_charter_rename.py`, all via `has_migration`). The whole subsystem — `BaseMigration`,
`MigrationRegistry`, `MigrationRunner`, `VersionDetector` — is `specify_cli`.

Placing the ledger in `kernel` (or a new sibling package) is **rejected**: it would create
consumer-less public surface in the dependency-free root layer and would force a new
`_DEFINED_LAYERS` entry plus a new `pyproject.toml` wheel package (the meta-tests
`test_no_unregistered_src_packages` `test_layer_rules.py:421` and
`test_all_defined_layers_match_at_least_one_module` `:460` require it), for zero benefit. The
genuinely root-layer mechanics (atomic write, hashing, locking) already live in `kernel` and are
consumed downward exactly as `metadata.py:14` already consumes `atomic_write`. **No layer rule
and no wheel package set change.** Adding a file inside `specify_cli` touches none of the three
enforced authorities.

### 1. Ledger location & authority — two partitions

The explicit ledger is **two append-only JSONL files, partitioned by whether a migration's
effect is tracked or clone-local**, and it becomes **the** execution authority for "already
applied", replacing both `metadata.yaml.applied_migrations` and the version window.

| | Tracked ledger | Per-clone ledger |
|---|---|---|
| Path | `.kittify/migration-ledger.jsonl` (tracked) | `.kittify/migrations/clone-local.jsonl` (untracked) |
| Authority for | migrations with `clone_local_effect == False` | migrations with `clone_local_effect == True` |
| Propagates on clone/pull | yes — correct; a tracked effect travels with the commit | no — correct; the effect (`.git/info/exclude`, `git config --local`, `.git/hooks`) does not travel |
| Record shape | `{id, applied_at, result, identity, content_hash, cli_version}` | same, plus `clone_local: true` |

This maps onto a split the repository already has. `.kittify/metadata.yaml` is tracked;
`.kittify/migrations/`, `.kittify/logs/`, `.kittify/encoding-provenance/` and the per-clone
sentinel files `.kittify/legacy-warning-shown-*` are untracked per-clone state. The tracked
ledger is a new tracked sibling of `metadata.yaml` (confirmed not git-ignored). The per-clone
ledger lives **inside the already-IGNORED `.kittify/migrations/` surface**
(`src/specify_cli/state/contract.py:308`, back-compat ignore #4928; `git check-ignore
.kittify/migrations/clone-local.jsonl` confirms it is ignored), so it needs no new gitignore
entry and is untracked by construction.

`clone_local_effect` (`base.py:122`) **stops being a reselection trigger and becomes a routing
key**: it decides which ledger a record is written to and read from. Because a clone-local
record lives only in the per-clone ledger, a freshly pulled clone has no such record, so the
migration is pending by plain ledger-diff (§3), applies, and records into *this clone's*
per-clone ledger.

**This supersedes the #6233 machinery.** `registry.py:175 _clone_local_selected_below_window`
and the sub-window reselection it drives are **removed**. `base.py:135 reselect_when_recorded`
collapses to "is this id in the applicable ledger for its partition?" `detect()`
(e.g. `m_4_0_0rc7_exclude_spec_kitty.py:detect`) **remains, as the idempotency guard only** — a
belt-and-suspenders check before `apply()` re-runs, never the authority for selection.

**Atomic write, single-writer.** The ledger is a full-file atomic rewrite of the JSONL on each
append, consistent with `metadata.py:240` and `VersionStamp` (`metadata.py:466/491`), not
`O_APPEND`. The subsystem is single-writer: `upgrade` runs in one process, worktrees
sequentially (`runner.py` `_upgrade_worktrees`), and integrating worktrees are skipped (ADR
2026-10-04-4). If concurrent cross-process upgrade ever becomes real, wrap the append in
`kernel.locks` (`src/kernel/locks.py:151`); this is the named extension point, deliberately
**not** built now.

**Rejected:** keeping the applied record inside `metadata.yaml`. It is the #5229 multi-writer
surface; a YAML block is a whole-document read-modify-write per record; and it cannot represent
the tracked/clone-local partition without a per-record scope flag inside a tracked file — which
re-creates the #6233 propagation bug for the clone-local rows.

### 2. Declared ordering — a checked-in order manifest

A single checked-in **order manifest** (a changelog-style list of `migration_id`s in canonical
execution order) is the authority for order. `Version(target_version)` is demoted to a
validation cross-check (the manifest must be version-monotonic save for explicitly annotated
ties). A build-time check (a new `tests/architectural/` gate) enforces: every registered
`migration_id` appears in the manifest exactly once (orphan / missing-entry check); every
manifest entry resolves to a registered migration (dangling-entry check); the order is
version-monotonic except where annotated; and at most one `runs_first` migration leads (already
guarded `registry.py:61-67`). Touchpoints: the sort in `registry.py:79-80 get_all` becomes a
manifest-index lookup; discovery (`__init__.py:18`) is unchanged.

**Rejected:** per-migration `after:`/`before:` DAG edges. They need a runtime topological sort
and cycle detection, and the total order is not readable at a glance. A single ordered list is
auditable in one read and the exactly-once / resolves checks are trivial. The `runs_first` flag
remains the escape hatch for the rare "must lead regardless of version" case.

### 3. Selection — ledger-diff replaces the version window

Selection becomes **declared minus applied**:
`pending = [m for m in manifest_order if m.id not in applicable_ledger(m)]`, then filtered by
`detect()` / `can_apply`, where `applicable_ledger(m)` is the per-clone ledger when
`m.clone_local_effect` else the tracked ledger. The version window
(`registry.py:119 from_v < target <= to_v`) is **retired as the applied authority**;
`target_version` survives only as the ordering/monotonicity reference (§2).

Consequences:
- **Stranded / skipped migrations.** Ledger-diff re-selects any declared migration whose id is
  not a `success` record, independent of the version stamp. The symlink fail-closed strand
  (`runner.py:366-393`) and the pulled-clone strand (#6233) both resolve for free.
- **Retired pre-3.0 modules (#2322).** `SupersededMigration` (`base.py:186`, `detect()==False`)
  and neutralised no-ops (`tests/specify_cli/upgrade/test_neutralised_migrations.py`) **stay in
  the manifest**. Ledger-diff selects them; `detect()==False` yields a `skipped` record; the
  skipped record keeps them from re-firing. Behaviour is identical to today, now anchored on the
  ledger rather than the version stamp.
- **Legacy-id aliases.** The legacy-id normalization map (`metadata.py:18
  _LEGACY_MIGRATION_ID_MAP`, applied today by `normalize_and_save_legacy_ids`
  `metadata.py:158`) is applied to ledger ids **on read**, so a constitution-era id and its
  charter-era id resolve to one record.

### 4. Drift detection — audit/report only, never auto-reapply

Each applied record carries an author-declared `identity` (defaulting to `migration_id`) and a
`content_hash = sha256_digest(<migration module source bytes>)`
(`kernel.content_digest.sha256_digest`). On a later run, a recorded migration whose current
`content_hash` differs from the stored one is flagged as **drift** and surfaced read-only
(§5). Drift is **never** acted on automatically.

This matches established practice for *code* migrations: Alembic and Django omit per-migration
checksums precisely because migrations are immutable once shipped, and editing a shipped
migration is itself the error (DIRECTIVE_044: do not edit shipped migrations). The hash does
not gate or re-run anything; it is the audit that makes a violation of that rule visible.
**Rejected:** checksum-mismatch → auto re-apply — it would fight `detect()` idempotency and
could re-run destructive `apply()` against a project that already carries the old effect.

### 5. Visibility — one pending-source, two read surfaces

A new doctor sub-surface `spec-kitty doctor migrations`
(`src/specify_cli/cli/commands/_migration_ledger_doctor.py`, following the existing doctor
family shape) and an `upgrade --list-applied` flag (`cli/commands/upgrade.py`) render: the
declared set (manifest), the applied set (both ledgers), the pending set, the
tracked/clone-local partition, and drift flags. Both consume the single pending-source
`VersionDetector.applicable_migrations` (`detector.py:49`) — the same method the compat planner
and `--dry-run` already delegate to — so the reported pending set can never diverge from the
applied set.

### 6. Adoption / backfill — hard cutover, detect-gated for clone-local

Transition is a **hard cutover**. A one-way backfill migration reads the existing
`ProjectMetadata.applied_migrations` (normalizing legacy ids, `metadata.py:171`) and writes
records into the new ledgers, then `metadata.yaml.applied_migrations` is **removed as the
authority — no dual-write mirror**. Backfill rules:

- **Tracked-effect records backfill unconditionally** into the tracked ledger.
- **Clone-local records are detect-gated.** The existing `metadata.yaml` record for a
  `clone_local_effect` migration is ambiguous — it was written into the shared file (the #6233
  bug), so it does not prove the effect is present on *this* clone. A clone-local record is
  backfilled into the per-clone ledger **only when `detect()` confirms the effect is present on
  this checkout**; if `detect()` reports it absent, nothing is written and ledger-diff
  re-applies it (safe, because `apply()` is idempotent).

The backfill is ordered first in the manifest so every later selection in the same run sees a
populated ledger. The new tracked ledger file is added to the state contract as a
`GitClass.TRACKED` surface (`src/specify_cli/state/contract.py`), and the repository's own
`.gitignore` must not ignore it.

## Consequences

**Positive.**
- Clone-local correctness falls out of the partition with no per-site reselection logic; the
  #6233 compensation code is deleted.
- The applied record leaves the `metadata.yaml` multi-writer surface; the runner stops being a
  second writer of the growing list there (it still stamps `version` / `schema_version`),
  shrinking the #5229 hazard.
- "What has run" and "in what order" are explicit, auditable, and the single authority.
- Stranded/skipped migrations and the retired pre-3.0 modules are handled uniformly by
  ledger-diff; no version-window special cases.
- No architectural layer rule and no wheel package set change.

**Negative / accepted costs.**
- **Back-compat (accepted ruling).** After the hard cutover, an *older* CLI reading a migrated
  project no longer finds applied-migration state in `metadata.yaml` and loses
  applied-migration visibility. This is a documented, accepted consequence — the new CLI is the
  authority; there is no dual-write mirror.
- A new tracked `.kittify/` file (`migration-ledger.jsonl`) is added to the state contract.
- One-time at adoption, a clone-local migration whose effect `detect()` cannot confirm on a
  given checkout re-runs its idempotent `apply()` once.

## Touchpoints

- `src/specify_cli/upgrade/migrations/base.py:122` `clone_local_effect` (becomes routing key),
  `:135` `reselect_when_recorded` (collapses to a ledger lookup), `:74` `BaseMigration`,
  `:186` `SupersededMigration`.
- `src/specify_cli/upgrade/registry.py:79-80` `get_all` sort → manifest index; `:82-135`
  `get_applicable` → ledger-diff; `:175` `_clone_local_selected_below_window` (**removed**);
  `:198` `_runs_first_selected_outside_window`; `:212` `_order_runs_first`; `:61-67` one-runs_first guard.
- `src/specify_cli/upgrade/runner.py:206-310` `upgrade`; `:337-393` `_apply_migration`
  (skip gate `:357`, symlink fail-closed `:366-393`).
- `src/specify_cli/upgrade/metadata.py:71` `applied_migrations` (removed as authority),
  `:184-241` `save` merge-preserving (#5229), `:276` `has_migration`, `:287` `record_migration`,
  `:18` `_LEGACY_MIGRATION_ID_MAP`, `:158` `normalize_and_save_legacy_ids`, `:410` `VersionStamp`.
- `src/specify_cli/upgrade/detector.py:44` `detect_version`, `:49` `applicable_migrations`
  (single pending-source).
- `src/specify_cli/upgrade/migrations/__init__.py:18` `auto_discover_migrations` (discovery
  unchanged; manifest is the order layer above it).
- `src/specify_cli/core/atomic.py:53` `atomic_write`; `src/kernel/content_digest.py:19`
  `sha256_digest`; `src/kernel/locks.py:151/241` (lock extension point, not built now).
- `src/specify_cli/state/contract.py:308` `.kittify/migrations/` IGNORED surface (per-clone
  ledger home); new `GitClass.TRACKED` surface for `.kittify/migration-ledger.jsonl`.
- Reference clone-local migrations: `m_4_0_0rc7_exclude_spec_kitty.py`,
  `m_0_13_1_exclude_worktrees.py`, `m_3_1_1_event_log_merge_driver.py`,
  `m_4_0_0rc5_install_lane_tip_recorder.py`, `_merge_driver_seeding.py`.
- Layer SSOT: `tests/architectural/conftest.py:88-118`, `tests/architectural/test_layer_rules.py:83-85`,
  `pyproject.toml [tool.hatch.build.targets.wheel].packages`.
- Idempotency gates to extend: `tests/upgrade/test_clone_local_migration_idempotent.py`,
  `tests/upgrade/test_clone_local_selection.py`.

## Follow-up child issues (spike #5230 output, epic #2933)

- **#A — Ledger module + dual-partition data model.** `src/specify_cli/upgrade/ledger.py`;
  tracked `.kittify/migration-ledger.jsonl` + per-clone `.kittify/migrations/clone-local.jsonl`;
  append-only JSONL via `kernel.atomic`; `clone_local_effect` as routing key. (Deliverable 1.)
- **#B — Declared-ordering manifest + build-time check.** Order manifest file + new
  `tests/architectural/` gate (exactly-once / resolves / version-monotonic). (Deliverable 2.)
- **#C — Ledger-diff selection; retire the version-window authority and the #6233 reselection
  machinery.** Rewrite `registry.get_applicable` / `get_all`; delete
  `_clone_local_selected_below_window`; collapse `reselect_when_recorded`; keep `detect()` as
  idempotency guard. (Deliverable 3; depends on #A, #B.)
- **#D — Drift identity/checksum on apply.** `identity` + `content_hash`
  (`kernel.content_digest`) stored per record; audit/report only. (Deliverable 4; depends on #A.)
- **#E — Visibility surface.** `doctor migrations` + `upgrade --list-applied` via
  `detector.applicable_migrations`. (Deliverable 5; depends on #A, #C.)
- **#F — Adoption backfill (hard cutover, detect-gated for clone-local).** Backfill from
  `metadata.yaml.applied_migrations`, then remove it as authority; no dual-write mirror; add the
  tracked ledger to `state/contract.py`. (Deliverable 6; depends on #A.)
- **#G — Docs / ADR.** Land this ADR; update the 2026-07-07-1 cross-reference; update the
  `CLAUDE.md` migration-authoring guidance and the ADR 2026-07-07-1 author checklist to the
  ledger model.

## References

- ADR [2026-07-07-1](../3.x/2026-07-07-1-ignored-surface-backfill-migration-pattern.md)
  (IGNORED-surface backfill pattern; this ADR supersedes its Amendment 2026-10-17).
- ADR [2026-10-04-4](2026-10-04-4-upgrade-writes-project-global-state-once.md) (upgrade writes
  project-global state once, skips integrating worktrees).
- Epic #2933 (explicit migration ledger); spike #5230; #6233 / PR #6350 (`clone_local_effect`);
  #5229 (metadata.yaml second-writer); #2322 (retired pre-3.0 modules).

---

## Amendment 2026-10-18 (closeout findings)

Two design facts were discovered and ruled during the mission's closeout. They are recorded
here so this ADR matches shipped behaviour; the Decision body above is unchanged.

### 1. Init-seed baseline (finding-1 remediation)

**Problem found.** §3 retires the version window and makes selection a plain ledger-diff
(`pending = declared − applied`). A *fresh* `spec-kitty init` wrote no ledger, so the first
`spec-kitty upgrade` on that brand-new project diffed an **empty** ledger against the full
declared set and selected **all ~114 historical migrations**. Replaying them against an
already-current project is not idempotent: `m_3_2_0rc35_activate_builtin_mission_types` and the
charter-bundle fold disagree over `mission_type_activations` (the rc35 migration adds it to
`config.yaml`; the fold relocates it into `charter.yaml`), so the first upgrade mutated config
and auto-committed — breaking NFR-002 (upgrade idempotency) on a second run.

**Decision / shipped behaviour.** A fresh `spec-kitty init` now **seeds** the ledger via
`src/specify_cli/upgrade/init_seed.py` (`seed_migration_ledger_for_init`), consuming the
`ledger.py` API — it does not re-implement ledger I/O. It records every migration a
brand-new, current project has effectively already satisfied, so the first `upgrade` selects
nothing. This is the Liquibase "changelog-sync for a new project" baseline: a **one-time init
stamp**, explicitly **not** a revived version-window selection authority (§3 stands).

The seed is **partition-correct** (§1): a tracked-effect migration (`clone_local_effect ==
False`) is seeded unconditionally into the tracked ledger; a clone-local migration
(`clone_local_effect == True`) is seeded into the per-clone (gitignored) ledger **only when its
effect is already present on this checkout** (`detect()` reports the old state absent). Because
the per-clone ledger never travels, a pulled clone still has an empty per-clone partition and
re-applies the clone-local effect — the #6233 guarantee is preserved, not undone, by the seed.
The seed is idempotent (`migration_settled` skips a migration already recorded `success`).

The disagreement itself was also closed at its root: `m_3_2_0rc35_activate_builtin_mission_types`
now **short-circuits** when `mission_type_activations` already lives in the resolved activation
write target — it reads the single authority
`charter.activation.pack_manager.resolve_activation_write_target` (which the fold points at
`charter.yaml` post-fold), so the rc35 migration and the provisioning predicate agree on
"already present" and the migration is a no-op there.

### 2. "Recorded elsewhere" vs "pending" for a fresh clone (finding-2)

**Clarification.** §1 deliberately keeps **no shared clone-local declaration marker** in the
tracked ledger (a per-record scope flag / dual-write was rejected because it would re-create the
#6233 propagation bug). A consequence, confirmed at closeout: for a **genuine freshly-pulled
clone**, the `spec-kitty migrate ledger` report state for a clone-local step is **pending**
("not yet applied" / not yet in place on this checkout), **not** "recorded elsewhere". The
per-clone ledger is gitignored and never travels, so a fresh clone has an **empty** per-clone
partition; `assemble_report` finds no matching record (`applied == False`) and the surface
classifies the step as `pending` (`src/specify_cli/cli/commands/migrate_cmd.py`
`_ledger_step_state`).

The `recorded-elsewhere` state (`_STATE_RECORDED_ELSEWHERE`) remains valid only for the
**distinct** real case of a clone that *applied* the clone-local effect and then *lost* it —
i.e. a per-clone record exists (`applied == True`) but `detect()` reports the effect absent now
(`in_place_here is False`). Acceptance scenario C was re-authored to assert the **pending**
state for the fresh-clone case accordingly.

### 3. Incidental notes

- **Visibility surface command name.** The shipped read surface is `spec-kitty migrate ledger`
  (read-only; `--json` emits the same report), rather than the `spec-kitty doctor migrations`
  spelling named in §5. Both consume the single pending-source
  (`VersionDetector.applicable_migrations`), so the §5 no-divergence property holds; only the
  command path differs.
- **R4 mirror strip location.** The retirement of the stale on-disk `migrations:` block from
  `metadata.yaml` (§6, no dual-write mirror) ships in `metadata.py::save()`, **gated on ledger
  adoption** (`_ledger_adopted`), rather than inside the backfill migration — so a `save()` that
  runs before the backfill never strips the block prematurely, and once the ledger owns the fact
  the dead second authority is removed on the next write.

### 4. Amendment 2026-10-20 (#6539): the `requires_git_repository` ClassVar

- **Contract.** `BaseMigration.requires_git_repository: ClassVar[bool] = False`. A migration that
  resolves the canonical repo root (`charter.resolution.resolve_canonical_repo_root`, directly or
  through `charter.activation.*`) sets it. Outside a git repository the runner skips it **before
  `detect()`**, warns "not inside a git repository", and writes **no ledger record**, so it stays
  selected and applies on a run inside a repository. "Inside" means exactly what the resolver
  accepts (a project in a repository subdirectory counts). `upgrade --dry-run --verbose` reports
  such a migration as skipped through the same probe.
- **`apply()` failure.** A `NotInsideRepositoryError` raised from `apply()` is no longer a skip: an
  `apply()` may already have written state. It is a recorded `failed` (a `runs_first` migration
  records nothing, as for any failure), the run stops and exits non-zero. The `detect()` and
  `can_apply()` catches stay: they run before any write.
  A repository probe that cannot run (`GitCommonDirUnavailableError`: git missing or unusable) is
  neither inside nor outside: it is a recorded failure at all three sites, and
  `upgrade --dry-run --verbose` says it would fail.
- **Accepted drift (C-002).** Adding the ClassVar changes the `content_hash` of each migration that
  declares it, which surfaces as audit-only drift (it is never re-selected). Migrations that
  declare it: `3.2.0rc35_unified_bundle`. The executed audit
  `tests/specify_cli/upgrade/test_requires_git_repository_audit.py` fails for any migration that
  reaches the resolver without declaring the flag.

---

## Amendment 2026-10-20 (#6431: adoption baseline, requested-target cap)

Three refinements, ruled by the operator on 2026-10-20 after the nightly found the first
ledger-era upgrade replaying older migrations (#6431, #6369). The Decision body above is
unchanged except where this amendment says so.

### 1. §6 adoption also settles the version floor (reverses the 2026-10-18 metadata-only ruling)

**Problem found.** Pre-ledger `spec-kitty init` stamped `spec_kitty.version` and wrote
`migrations: applied: []`; the retired version window then never selected a migration at or
below that version. So the version stamp, not the applied list, was what settled a
project's older migrations, and the list of a real pre-ledger project is empty or partial.
The metadata-only backfill (closeout ruling 2026-10-18) left all those migrations pending,
and the first ledger-era upgrade replayed them against a current project:
`2.0.6_consistency_sweep` rewrote Mission `meta.json`, `3.0.0_canonical_context` rewrote
`status.events.jsonl` (undoing a forced lane transition), and the upgrade auto-committed.

**Decision.** On **first adoption only**, until the backfill
(`m_4_0_0rc8_backfill_migration_ledger.py`, unreleased when amended) is itself recorded as
applied, it also records as `success` every registered migration whose `target_version` is below
both the recorded `spec_kitty.version` and the backfill's own `4.0.0rc8`, and that neither
`applied_migrations` nor a ledger partition mentions. A migration AT the recorded version stays
pending, as the retired window still selected it when its `detect()` held. Adoption is keyed on the backfill's own
record, not on a ledger file existing: a gitignored per-clone ledger survives a checkout of a
pre-ledger branch and is not adoption. The bound below `4.0.0rc8` exists because no CLI without
the ledger shipped a migration at that version, while an rc8 build that predates the ledger
stamped `4.0.0rc8`. The records are written with one atomic write per partition, so an
interrupted adoption leaves none of them. Partition routing is the same as the listed
records (§1): tracked unconditionally, clone-local only when its effect is present here (see
3). A listed `skipped` or `failed` record keeps its result, so §3's "a failed migration is
retried" still holds. An unparseable recorded version stamps nothing. This is the adoption
counterpart of the init seed (Amendment 2026-10-18 §1), a one-time stamp. It does not revive
the selection window: once the backfill is recorded, nothing is stamped from the version.

The backfill declares the new `BaseMigration.ledger_adoption` ClassVar. While it is unsettled,
`get_applicable` treats the ids it will settle (`adoption_settled_ids`) as already settled, so
`upgrade --dry-run`, the plan preview, the compat planner and `migrate ledger` list exactly what
the real run applies (§5's single pending-source promise).

### 2. §3 the run's requested target stays an upper bound

§3 retired the version window as the **applied** authority. Its upper bound
(`target <= to_v`) was the scope of the run the operator asked for, not an applied fact, and
retiring it let `spec-kitty upgrade --target X` apply migrations declared for later
versions and then stamp the project as `X`. `MigrationRegistry.get_applicable` now selects
only migrations whose `target_version <=` the requested target. Selection is still a
ledger-diff, and a migration above the target is out of scope for that run: it is neither
selected nor settled. An unparseable target caps nothing. A `ledger_adoption` migration is
never capped: an upgrade to an older target that skipped adoption would still record the
migrations it ran, and those records would then hide the adoption for good. A default upgrade
(target = CLI version) is unaffected. `target_version` is therefore both the ordering cross-check (§2)
and this cap. The lower bound stays retired.

### 3. A clone-local effect is "present" only inside a git repository

The init seed and the adoption backfill record a clone-local migration without running it
only when its effect is present on this checkout. Both now ask one predicate,
`ledger.clone_local_effect_in_place`: a git repository exists **and** `detect()` reports
nothing to do. Without a repository, `detect()` of such a migration reports "nothing to do"
only because there is nowhere to put the effect yet, so an `init` outside git used to seed
the step as done, and the first upgrade after `git init` never installed it. A `detect()`
error reads as "not in place", leaving the migration pending.

## Amendment 2026-10-22 (#6582: the lead block, the charter-pack cutover after its prerequisites)

§2 allowed a single `# runs-first:` lead, and §6 gave it to the ledger backfill. That moved the
charter-pack cutover (`charter_pack_cutover`, spec FR-012 of mission
`charter-pack-cutover-01M491G6`) from the head of the run, where its retired front-pull used to
put it, back to its `4.0.0rc6` version slot. About forty pending migrations then ran ahead of it
on a pre-cutover project, so a refused collision ("moves nothing") left `.gitattributes` merge
driver lines behind, and FR-012 ("runs before every other pending migration") no longer held.

**Decision (operator ruling, 2026-10-22).** The manifest's `# runs-first:` annotation marks an
entry of the **lead block**: a contiguous prefix of annotated entries that run first, in the order
listed, regardless of their `target_version`. The block holds the cutover and the two migrations
it depends on:

1. `4.0.0rc8_backfill_migration_ledger` leads, as §6 requires.
2. `3.2.0rc35_charter_bundle_v2` follows. The cutover parses `.kittify/charter/synthesis-manifest.yaml`
   with the current model, which accepts only schema `2`/`3`; only this migration upgrades a `v1`
   bundle. Without it ahead, a pre-3.2.0rc35 project with a `v1` manifest failed at the cutover on
   every run (found in pre-PR review; pinned by
   `test_fr012_v1_synthesis_manifest_upgrades_through_the_cutover`). It changes only the charter
   bundle under `.kittify/charter/` and is detect-gated.
3. `charter_pack_cutover`. It cannot lead ahead of the backfill: its first-application check
   (`_is_first_application`, which gates the one-time activation-list resets) reads the ledger, so
   on a pre-ledger project that already applied the cutover it would redo those resets against
   deliberate `[]` lists. The shipped migration is not edited (DIRECTIVE_044), so ordering is the
   fix.

FR-012 is read as "the cutover runs before every other pending *project* migration, after the
migrations it depends on": the backfill only writes ledger records and the bundle upgrade only
brings the charter bundle to the schema the cutover reads.

**Residual.** On a constitution-era project (`.kittify/constitution/`, before `3.1.1_charter_rename`)
the bundle upgrade now runs before the rename, finds no `.kittify/charter/`, and records `skipped`.
Later migrations in the same run bring the bundle current: the resulting `.kittify/` tree equals
the one the version-slot order produced. The step stays a re-skipped, `pending` row in
`spec-kitty migrate ledger`, which is §3's behaviour for a not-needed migration.

**Assumption (legacy `.specify/` layout).** The cutover now runs before `0.2.0_specify_to_kittify`,
so on a project that still has `.specify/` the cutover finds no `.kittify/` inventory and records
`skipped` in that run. This costs nothing: the CLI creates `.kittify/` before the migrations run, so
`0.2.0_specify_to_kittify` itself skips ("`.kittify/` already exists - manual merge required") with
or without this order, and a pre-0.2 project never reaches the cutover's inputs through the rename.
A project whose `.kittify/` is brought to the legacy shape by hand converges on its next
`spec-kitty upgrade`, because a `skipped` record does not settle the cutover. Checked with a
throwaway `.specify/` project (two runs), not pinned by a test.

The build-time gate (`tests/architectural/test_migration_order_manifest.py`) now requires every
`# runs-first:` entry to sit in the lead block and checks version monotonicity over the entries
after it; the gate's `lead_block_length` is the one definition. The
`runs_first` ClassVar is unchanged: it governs reselection, not order, and at most one migration
sets it.

## Amendment 2026-10-25 (#6589: superseding a shipped migration without editing it)

**Correction.** The Consequences bullet on retired modules says the `skipped` record "keeps them
from re-firing". It does not: §3 settles a migration only on a `success` record, so a
`SupersededMigration` is selected and re-skipped on every run. That is harmless for a no-op, and it
is why two live backfills could undo a later migration. `3.2.5_agents_skills_gitignore_backfill`
and `3.2.6rc3_narrow_cursor_gitignore`, once recorded `skipped`, were selected again after
`4.0.0rc8_narrow_agent_gitignore` removed their rows. Their `detect()` then went True, and they
wrote `.agents/skills/` and the `.cursor/` rows back.

**Decision (operator ruling, 2026-10-25).** Both are superseded by
`4.0.0rc8_narrow_agent_gitignore`. Their modules are not edited (DIRECTIVE_044). Instead,
`src/specify_cli/upgrade/supersession.py` holds `SUPERSEDED_MIGRATIONS` (superseded id → successor
id). `MigrationRegistry.register` registers a `SupersededMigration` substitute for each listed id,
built at register time. The substitute keeps:

- the shipped class's id, `target_version`, `description`, routing key (`clone_local_effect`),
  `identity`, `requires_git_repository` and `runs_on_worktrees`;
- its defining module, so `content_hash` stays the shipped module's hash and recorded history never
  reads as drift.

The decorator still returns the shipped class, so a direct import keeps the old behaviour (its
unit tests stay valid). Every registry consumer sees the no-op: selection, the runner, the
worktree loop, `upgrade --dry-run`, `migrate ledger`, the init seed and the adoption backfill.
The successor must come later in `order_manifest.txt`; `tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py`
pins that, the byte-identical hash, and the no-re-add behaviour for a pre-ledger and a
ledger-era project.

**This is now the way to supersede a shipped migration.** The three earlier precedents
(`m_2_1_2_fix_glossary_context_skill`, `m_3_2_x_normalize_activation_absence`,
`m_3_2_0rc35_default_charter_pack`) were rewritten in place before the ledger and its hash existed.
Do not repeat that.

**Accepted loss.** A project upgrading from before 3.2.5 no longer gets two things the 3.2.5 backfill
provided:

- the `.kittify/skills-manifest.json` ignore row (`4.0.0rc8_narrow_agent_gitignore` keeps that row
  but does not add it);
- the `git rm --cached` of committed projected skills (#3393), so those files stay tracked while
  the rc8 agent-files block ignores them.

`upgrade --dry-run --verbose` and `migrate ledger` keep listing both ids as pending/`skipped`, and the runner reports them as "not needed" (its `detect()` is False before `can_apply` returns the `superseded_by` text); marking superseded ids in that read surface is left for later. A run capped below 4.0.0rc8 (`upgrade --target 3.2.6rc3`) no longer narrows a blanket `.cursor/`
row; the rc8 migration does. The #5443 upgrade-commit tests now use the untrack of
`3.2.0rc35_kittify_runtime_git_hygiene`. Other shipped migrations with the same re-selection shape
(`0.4.8_gitignore_agents`, `3.1.2_globalize_commands`, #6547) are not changed here.

## Amendment 2026-10-25 (#6629: the interview promotion is superseded)

**Decision.** `unify_charter_activation_promote_answers` is superseded by
`4.0.0rc8_promote_interview_selections`, through the same `SUPERSEDED_MIGRATIONS` table and
with its module left byte-identical (DIRECTIVE_044). The shipped step seeded an absent
`activated_<kind>` key with the kind's whole in-force set before it appended the interview
selections. `charter synthesize` then read that list as an operator's activation: it demanded a
companion tactic per directive and skipped the fresh-project seed. The step also read only
`.kittify/config.yaml`, so after the keys had moved it wrote a stale second list there (#6549).

The successor works differently:

- it is listed after `4.0.0rc8_activation_ledger`;
- it appends only the interview selections a present list lacks, writing through the activation
  write target and the promotion primitive;
- it never writes an absent key.

**Settling.** The successor's `detect()` is always True, and `apply()` succeeds even when nothing is
left to promote. Its first run is therefore recorded `success` and settles it. A `skipped` record would re-select it on every upgrade (the
correction above), and that run would append the interview ids back into a list an operator
had narrowed with `charter activate --only`.

**Only where the shipped step never settled.** Since #2526 the interview record has not been an
activation source, so promotion is a one-time backstop for a project that crosses that change.
When the Migration Ledger records that `unify_charter_activation_promote_answers` ran, a
present list that lacks an interview id has had it removed, or never had it in force, so the
successor appends nothing. That is a `success` record (the shipped step ran, or the adoption
backfill settled it for a project created after it) or a `skipped` record the shipped step wrote
itself: the pre-ledger runner recorded `skipped` ("Not applicable") when the interview had already
promoted, and the backfill copies it. The substitute's own `skipped` does not count. The runner
marks it with the substitute's `superseded_by` note (an optional record field, written only when
set), so the two read apart. On a project still being adopted, a dry run writes no record, so the
successor also asks the pending adoption what it will record (`registry.pending_adoption_ids`,
plus the legacy `skipped` in `metadata.yaml`), as selection does. Appending would change
activation silently (#6499). This adds a reading rule. A successor may read the record of the
migration it supersedes, through its authoritative partition. It never branches on the record of
any other migration: the Migration Ledger stays the selection authority, not a general state input.

**Residual.** A shipped `skipped` can also mean the step did nothing at all: it read only
`.kittify/config.yaml`, so on a project whose keys were in `charter.yaml` and that had no
`config.yaml` it skipped without promoting (#6549). The successor appends nothing there either.
Interview-side promotion since #2526 covers most of those projects.

**Version.** The successor sits at 4.0.0rc8. The ledger-adoption backfill settles only steps
below both the recorded version and 4.0.0rc8, so it is never settled without running.
`tests/upgrade/test_upgrade_keeps_absent_activation_6629.py` drives a project stamped
below 3.2.6rc1 through the runner and `charter synthesize --dry-run --json`. On a project stamped
above 3.2.6rc1, adoption settles the shipped step without running it in that upgrade, so a
reproduction stamped there would never witness the bug.

**Accepted loss.** A project an earlier build already seeded keeps its list. The successor only
warns when a present list holds every available artifact while the interview selected fewer,
and it names `charter interview --narrow-activation` and `charter activate <kind> <id> --only`.
## Amendment 2026-10-25b (#6669: residue-aware successors)

**Problem.** Four shipped migrations enumerate every `kitty-specs/` child and write into it:
`0.9.0_frontmatter_only_lanes`, `0.9.1_complete_migration`, `2.0.6_consistency_sweep` and
`3.1.1_normalize_status_json`. A residue folder (no `spec.md` or `meta.json` on disk, and git does
not recognize it as a Mission) therefore had its lane folders flattened, its work packages
rewritten, a baseline `meta.json` written and a `status.json` normalised. Their modules are
byte-frozen (DIRECTIVE_044, `content_hash`), so the fix cannot be an edit.

**Decision (operator ruling, 2026-10-25).** Each is superseded, through the table of Amendment
2026-10-25, by a successor that is a **new migration**, not a rewrite of the old module:

| Superseded (recorded no-op) | Successor |
|-----------------------------|-----------|
| `0.9.0_frontmatter_only_lanes` | `0.9.0_residue_safe_frontmatter_only_lanes` |
| `0.9.1_complete_migration` | `0.9.1_residue_safe_complete_migration` |
| `2.0.6_consistency_sweep` | `2.0.6_residue_safe_consistency_sweep` |
| `3.1.1_normalize_status_json` | `3.1.1_residue_safe_normalize_status_json` |

- **New migrations, not substitutes.** A `SupersededMigration` substitute is a no-op by design, so
  it cannot carry the repair. The successor must repair the same real Missions, in one of two
  patterns:
  - **Subclass (`0.9.0`, `0.9.1`).** The successor subclasses the shipped class, so the shipped walk
    still runs and every repair is inherited. It is made residue-safe only by the methods it
    overrides: `_is_legacy_format` (0.9.0), `_has_remaining_lane_dirs` and
    `_normalize_all_frontmatter` (0.9.1). Both also list `ResidueSafeLaneSuccessorMixin` first in
    their bases; it carries the shared `detect`/`apply` wrappers and the `_is_residue` decision the
    overrides call. The walker gate pins each override, and the mixin's `_is_residue`, to the residue
    predicate.
  - **Re-implementation (`2.0.6`, `3.1.1`).** The successor subclasses `BaseMigration`, re-implements
    `detect`/`apply` over the Mission folders that `partition_kitty_specs` returns (3.1.1 also its
    status writer), and reuses the shipped module's helpers (`_repair_feature`,
    `_needs_normalisation`, and so on). Nothing of the shipped class is inherited.

  In both patterns the shipped module is imported as a module alias, or only its module-level
  helpers, never the class by name: `auto_discover_migrations` skips a module whose `dir()` holds a
  class with an already-registered `migration_id`, so a name import would make the successor vanish
  after `MigrationRegistry.clear()`. Drift scope: each successor's `content_hash` covers its own
  module only. A change to the shared `_residue_successor.py` or to the residue predicate is outside
  drift scope, as for any other migration that imports helpers.
- **Same slot.** Each successor sits immediately after its predecessor in `order_manifest.txt`, with
  a `# tie:` annotation, because the successor has the predecessor's `target_version`. A later step
  (the lifecycle normalisation, the status migrations) must see the successor's output exactly where
  it saw the predecessor's. `tests/architectural/test_migration_order_manifest.py` still gates the
  order; `test_each_successor_sits_right_after_its_predecessor_in_the_order_manifest` pins the slot.
- **The selection-view gate.** A project that already ran the predecessor must not run the successor
  on top of it. Each successor's `detect()` returns False when
  `registry.settled_in_selection_view(project_path, predecessor_id)` is True. That helper uses the one
  predicate of `MigrationRegistry.get_applicable` (`_settled_in_view`): the id is a `success` record
  in its authoritative partition, or an unsettled ledger-adoption migration will settle it on apply.
  Reading the ledger directly would miss the second case, so the successor would repair a project the
  adoption backfill is about to mark as done. The gate is a `detect()` guard only: selection stays
  ledger-diff (§3), and `detect()` remains the runner's idempotency check.
- **One residue rule, one walk.** The successors share `_residue_successor.py` (a non-migration
  module, never auto-discovered): the lane mixin, `partition_kitty_specs` /
  `partition_checkout_specs` (a Mission walk that also covers `.worktrees/*/kitty-specs/`, each
  worktree judged against itself as the checkout root) and one residue notice per folder. The tracked
  paths are probed once per walk with `mission_resolver.probe_tracked_mission_paths`.
  `tests/architectural/test_migration_walkers_use_mission_predicate.py` fails a walker that does not
  reach `is_kitty_specs_residue` / `is_mission_dir`.
- **No edit to a shipped module.** `git diff --diff-filter=MDR origin/main -- 'src/specify_cli/upgrade/migrations/m_*.py'`
  prints nothing.

**Accepted residuals.**

- **C-006: a retry is lost on first adoption.** A pre-ledger project whose `metadata.yaml` records a
  predecessor as `failed` or `skipped` at a version above it has the successor stamped as settled by
  the first-adoption backfill (ADR Amendment 2026-10-20: it settles every migration below the recorded
  version). The backfill migration is frozen (C-006), so the repair the predecessor never finished is
  not retried by the successor. Neither a selection-view hook (the backfill still writes the
  `success` record the runner's skip gate reads) nor a manifest slot change reopens it without
  frozen code or a manifest-semantics change. `test_c006_an_unsettled_predecessor_record_still_lets_the_successor_run`
  asserts the desired retry as a strict `xfail`.
- **A stale "pending" listing.** A `skipped` record does not settle a migration (§3, Amendment
  2026-10-25), and an inert successor is `skipped`. On a project whose predecessor already ran,
  `migrate ledger` and `upgrade --dry-run --verbose` therefore keep listing the successor as not yet
  applied, and the runner re-skips it every run. This is idempotent and harmless; marking it in the
  read surface is left for later, with the same item for the superseded ids.
- **Git-aware residue.** In a project where git tracks some Mission path, a committed folder holding only
  `tasks.md` or `tasks/` counts as residue, and the successors leave it alone. The notice names the
  folder and the remedy (add a `spec.md` or `meta.json`, or remove the folder).
- **The audit's residue rule is stricter than upgrade's.** `RESIDUE_DIRECTORY` uses strict
  `is_mission_dir`. Without usable git, or with `kitty-specs/` ignored, it reports a folder holding
  only `plan.md` or `tasks.md` as residue, while upgrade's file-presence mode treats that folder as a
  Mission and repairs it.
- **The mode flips on one tracked file.** Git-aware mode applies as soon as git tracks any path under
  `kitty-specs/`. In a project where `kitty-specs/` is gitignored but one file was force-added,
  untracked legacy Missions without `spec.md` or `meta.json` become residue and are left alone.
- **`FABRICATED_IDENTITY_SUSPECTED` false negative.** The finding compares the slug's trailing mid8
  with the `mission_id`. A fabricated `meta.json` in a legacy `NNN-slug` residue folder, whose slug
  carries no mid8, is not flagged.
- **A degraded probe only warns.** A non-timeout git failure of the tracked-path probe (for example a
  corrupt index) falls back to file-presence mode and logs one warning per checkout and run. A timeout
  is a retryable `failed` record, in the main checkout and in each worktree.

## Amendment 2026-10-30 (#6613: the `runs_first` structural reselection, and the ledger lock)

**Problem.** Two statements in this ADR did not match the code that implements it, so a reader
taking them at face value would be wrong about when a migration runs again.

- §1 says selection "collapses to 'is this id in the applicable ledger'". It does not, quite.
  `BaseMigration.reselect_when_recorded` (`upgrade/migrations/base.py`) returns
  `runs_first and structural_detect(project_path)`: a `runs_first` migration whose structural
  predicate reports its old state present is re-selected **even though a `success` record exists**.
  `structural_detect` appeared nowhere in this ADR or in its amendments, and the touchpoint list
  below still describes `reselect_when_recorded` as one that "collapses to a ledger lookup".
- §1 ("Atomic write, single-writer") said the ledger append takes no lock and that wrapping it in
  `kernel.locks` was the named extension point, "deliberately **not** built now". #6613 built it.

**Decision (recorded, not re-decided).**

- **The selection rule is ledger-diff *plus* one structural reselection.** For every migration the
  authority is its applicable partition: a `success` record settles it. For the single migration
  allowed to set `runs_first`, a recorded migration is still re-selected when
  `structural_detect(project_path)` reports the old state present — state a pulled `metadata.yaml`
  or a merge can revive after the first application. `structural_detect` is therefore part of
  selection, not an optimisation, and it must stay content-driven (never version-driven).
- **It is bounded and it does not become a second authority.** At most one registered migration may
  set `runs_first` (`registry.py`'s `_order_runs_first` guard). `detect()` remains the pre-`apply()`
  idempotency guard and never the skip authority (C-003 of §3); a `runs_first` migration's `apply()`
  must be idempotent, because reselection re-applies it. `clone_local_effect` is unaffected: it is
  the ledger's routing key only, and clone-local reselection is plain ledger-diff (§3).
- **Recording is not deciding.** Removing the reselection — making §1's "collapses to a ledger
  lookup" literally true — is an **open operator decision**, filed as the other half of #6613. This
  amendment documents the behaviour as shipped; it neither widens it nor removes it.
- **The append is locked (supersedes the "deliberately not built now" sentence of §1).** Every
  append holds a dedicated sidecar lock across its read and its `os.replace`, taken through
  `kernel.locks.machine_file_lock` — the extension point §1 named — with a bounded wait
  (`ledger.LEDGER_LOCK_TIMEOUT_S`, 30 s) that raises `ledger.MigrationLedgerLockTimeoutError`
  having appended nothing. The lock file is
  `<project root>/.kittify/migrations/<ledger file name>.lock`: a dedicated sidecar (never the
  payload, which the primitive truncates on release) inside the already-IGNORED per-clone surface,
  so a lock is never a `git status` entry and never reaches an upgrade autocommit.
- **The lock is per ledger *file*, not per repository.** The file is the thing that can lose a
  record; a git-common-dir key would over-serialize unrelated checkouts and would need a git
  invocation on a path that must also run outside a repository (`init` outside git deliberately
  leaves clone-local steps pending, #6431). No anchored-lock-path helper is added here: #6727 owns
  consolidating that rule, and the ledger derives its path from a path it already holds.
- **Durability is unchanged (NFR-001).** The write is still the full-file atomic rewrite of
  `core/atomic.py`, never `O_APPEND`; the lock serialises the read-modify-write, it does not change
  the write.

**Accepted residuals.**

- **A timed-out append aborts the run.** A lock still held after 30 s raises out of `runner` at the
  point the record was to be written — which can be after `apply()` succeeded, or before it ran at
  all when the record is a `skipped` one. Nothing is recorded for that migration, the run stops, and
  the message says what happened and to retry. Re-running is safe because `apply()` is idempotent
  (above) and the record is simply re-attempted; no false `success` is ever written.
- **The duplicate pre-check is outside the lock.** `runner._record_ledger_result` reads the
  partition to skip a `(id, result)` it already has, then appends. Two concurrent runs can both
  decide "not recorded" and both append, so a partition may hold the same `(id, result)` twice.
  `ledger._normalize_records` collapses by id on every read, so the authority is unaffected and the
  duplicate never settles anything twice; only the raw line count can grow.
- **Closure of gap-table row G-15 is deferred.** `docs/architecture/event-ledger-writers-and-readers.md`
  (the "No lock" writer row and the G-15 row) is frozen by `tests/architectural/test_events_import_frozen.py`
  (ADR 2026-10-29-1 D-9, blob `c2943d49…`). Correcting it needs an operator-approved re-pin of
  `_FROZEN_OBJECTS`; this amendment carries the facts in the meantime.
