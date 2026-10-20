---
title: 'ADR: the applied-migration ledger is an explicit, two-partition record that is the execution authority for what has run'
description: 'An explicit two-partition migration ledger replaces metadata.yaml and the version window as the authority for what has run; selection becomes ledger-diff.'
status: Accepted
date: '2026-10-17'
updated: '2026-10-17'
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
- **Accepted drift (C-002).** Adding the ClassVar changes the `content_hash` of each migration that
  declares it, which surfaces as audit-only drift (it is never re-selected). Migrations that
  declare it: `3.2.0rc35_unified_bundle`. The executed audit
  `tests/specify_cli/upgrade/test_requires_git_repository_audit.py` fails for any migration that
  reaches the resolver without declaring the flag.
