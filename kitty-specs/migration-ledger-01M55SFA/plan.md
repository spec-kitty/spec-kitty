# Implementation Plan: Explicit two-partition migration ledger

**Branch**: `issue-5230-migration-ledger-impl` | **Date**: 2026-10-17 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/migration-ledger-01M55SFA/spec.md`; accepted design ADR [`docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`](../../docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md).

## Summary

Make the explicit two-partition migration ledger the single execution authority for "already
applied", exactly as the accepted ADR concluded. This is a **brownfield** change to the live
`src/specify_cli/upgrade/` subsystem: the ledger does not replace the subsystem, it re-seats its
authority. A new `upgrade/ledger.py` owns two append-only JSONL files
(`.kittify/migration-ledger.jsonl`, tracked; `.kittify/migrations/clone-local.jsonl`, per-clone
untracked); `clone_local_effect` becomes the routing key; selection becomes ledger-diff over a
checked-in order manifest; the version window and the #6233 reselection machinery are deleted;
drift is a read-only content-hash audit; a single `spec-kitty migrate ledger` read surface
reports what ran; and a one-way, detect-gated backfill cuts existing projects over hard, with no
dual-write mirror.

The plan is pointcut-driven: §Pointcut Map names every existing `file:line` insertion/modification
point (add / modify / delete), seeded from the ADR Touchpoints section.

## Technical Context

**Language/Version**: Python 3.11+.
**Primary Dependencies**: no new runtime dependency. Consumes `kernel.atomic` (atomic write, via the existing `specify_cli/core/atomic.py:53` wrapper) and `kernel.content_digest.sha256_digest` (`src/kernel/content_digest.py:19`) downward across the existing legal layer boundary. `typer` for the one new `migrate` subcommand. **Supply-chain controls N/A** (no dependency decision).
**Storage**: two append-only JSONL files under `.kittify/` (one tracked, one per-clone untracked). Full-file atomic rewrite on append (NFR-001 — no `O_APPEND`), mirroring `metadata.py:240` and `VersionStamp` (`metadata.py:466/491`).
**Testing**: pytest unit/integration in `tests/upgrade/` and `tests/specify_cli/upgrade/`; a new build-time gate in `tests/architectural/`; ten acceptance-jvm steps + the `@wip`→gating transition in `tests/scenarios/upgrade/migration-ledger.feature`.
**Target Platform**: Linux/macOS/Windows CLI (`spec-kitty upgrade` / `spec-kitty migrate`).
**Project Type**: single (the spec-kitty CLI package).
**Performance Goals**: N/A — upgrade is an interactive one-shot; the ledger read is O(declared migrations).
**Constraints**: the ledger and all machinery stay in `src/specify_cli/upgrade/` (C-002); `detect()` is the idempotency guard only (C-003); drift never auto-reapplies (C-004); the ledger is the only applied authority (C-001); complexity ≤15, no blanket `# noqa`/`# type: ignore` (NFR-005).
**Scale/Scope**: 124 registered migrations (the `m_*.py` + `_*.py` set under `upgrade/migrations/`) whose selection behaviour must stay byte-for-byte except the two intended fixes (version-window strand, pulled-clone clone-local).

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority / no improvisation**: the ledger becomes THE applied authority; both the version window and `metadata.yaml.applied_migrations` are retired as authorities (ADR §1/§3; C-001). The read surface reuses the one existing `migrate` Typer group (`migrate_cmd.py:69`), not a parallel command. ✅
- **Architectural alignment / no parallel authority (NFR-002, C-002, SC-008)**: everything lands in `src/specify_cli/upgrade/`; it consumes `kernel` downward only. The three enforced authorities — `pyproject.toml [tool.hatch.build.targets.wheel].packages`, the `landscape` fixture (`tests/architectural/conftest.py:88-118`), `test_layer_rules.py` (`:83-85`) — are untouched. No new top-level `src/` package → `test_no_unregistered_src_packages` (`test_layer_rules.py:421`) unaffected. ✅
- **ATDD / red-first (ADR 2026-07-17-1)**: every WP lands its red-first test before the fix — the stranded-migration selection test (FR-004), the two-`runs_first`/orphan/dangling manifest fixtures (FR-007), the drifted-source fixture (FR-010), the pre-ledger backfill fixture (FR-012); the acceptance steps red through the CLI entry point before the surface exists. ✅
- **Tiered rigour**: consumer-facing control-plane surface (`spec-kitty upgrade` is the install/upgrade path every consumer runs) → built-in/consumer tier, standard-plus rigour; tests in the same PR (Sonar new-code gate). ✅
- **Terminology**: `migrate`/`upgrade` CLI surface; the scenario text stays consumer language ("setup step", not "migration/ledger") per the feature file's maintainer note. ✅
- **Campsite / mission tracer**: trace/ decisions.md records the three OQ resolutions below. ✅

No charter violations → Complexity Tracking empty.

## Open-question resolutions (settled by `/plan`)

### OQ-1 (RESOLVED by operator) — the read surface is `spec-kitty migrate ledger`

The canonical read surface is a single new subcommand **`spec-kitty migrate ledger`** on the
existing `migrate` Typer group (`src/specify_cli/cli/commands/migrate_cmd.py:69`). It is
**read-only** and prints: the applied set in declared (manifest) order; a partition column
(tracked / clone-local); for a clone-local row, whether the effect is *in place here* vs merely
*recorded elsewhere* (via the migration's own `detect()`); and a drift flag per row. `--json`
emits the structured shape, matching the house pattern of every other `migrate` subcommand.

**Dropped:** `spec-kitty doctor migrations` (no `doctor` surface is added) and
`spec-kitty upgrade --list-applied` (no thin alias — a single canonical surface, per the ruling).
The three `When` lines in the feature file that today name `upgrade --list-applied` /
`doctor migrations` are **rebound to `spec-kitty migrate ledger`** (see Pointcut Map row X1); the
scenarios' Then-asserts are command-agnostic, so the rebind is purely in the `When` step and the
feature footer note.

### OQ-2 — order manifest file & format

**Path:** `src/specify_cli/upgrade/migrations/order_manifest.txt` (beside the migration modules
it orders). **Format:** a line-oriented changelog — one `migration_id` per line in execution
order; blank lines and `#`-prefixed lines ignored. **Tie annotation:** `target_version` must
strictly increase down the file, EXCEPT between adjacent entries that BOTH carry a trailing
`# tie:<reason>` marker (e.g. `m_0_13_0_update_charter_templates  # tie:same-release-independent`),
which permits an intentional equal-`target_version` run. The build-time gate (FR-007) enforces:
every registered `migration_id` appears exactly once; every entry resolves to a registered
migration; the order is version-monotonic save for annotated ties; at most one `runs_first`
migration, and it leads. **Rejected:** a YAML list (`order.yaml`) — adds a parse step and invites
per-entry structure creep; and an in-module `ORDER = [...]` Python list — not review-friendly as a
plain diff and couples the order authority to import. The flat text list is the minimal authority.

### OQ-3 — `content_hash` source scope and `identity`

`content_hash = sha256_digest(<source bytes>)` over the **single migration module file** by
default (the `m_<...>.py` that defines the class, via its source path). A multi-file migration
(e.g. `m_3_1_1_event_log_merge_driver` + its `_merge_driver_seeding.py` helper, the
`_charter_pack_cutover_*` family) MAY declare `content_hash_sources: ClassVar[tuple[str, ...]]` —
module-relative filenames whose **sorted, concatenated** source bytes form the hash input
(deterministic). Unset ⇒ just the defining module. `identity: ClassVar[str]` defaults to
`migration_id` and is the **stable drift key**: the ledger stores `(identity, content_hash)`, and
drift = recorded hash ≠ current hash for the same `identity`. Overriding `identity` lets an author
re-slug/rename a migration module without tripping drift when content is unchanged; a content
change under a stable identity trips drift (DIRECTIVE_044 as audit). **Rejected:** hashing the
whole `migrations/` directory (every new migration would drift every record) and AST-normalized
hashing (over-engineered; raw source bytes are the honest "did the file change" signal).

## Project Structure

### Documentation (this mission)

```
kitty-specs/migration-ledger-01M55SFA/
├── plan.md              # This file
├── spec.md              # Mission spec (FR-001..016)
├── research.md          # Phase 0 output (if generated)
├── data-model.md        # Phase 1 — LedgerRecord + manifest entry shapes
├── contracts/           # Phase 1 — ledger read/write contract; migrate-ledger CLI contract
├── quickstart.md        # Phase 1
└── tasks.md             # Phase 2 (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root) — brownfield touch surface

```
src/specify_cli/upgrade/
├── ledger.py                      # ADD — two-partition ledger: LedgerRecord, MigrationLedger, drift, report model
├── migrations/
│   ├── order_manifest.txt         # ADD — the ordered migration_id list (OQ-2)
│   └── base.py                    # MODIFY — identity/content_hash_sources ClassVars; collapse reselect_when_recorded
├── manifest.py                    # ADD — load_order_manifest(), manifest_index(), tie parse
├── registry.py                    # MODIFY get_all sort→manifest; get_applicable→ledger-diff; DELETE _clone_local_selected_below_window
├── runner.py                      # MODIFY _apply_migration skip gate + record path → ledger (partition-routed)
├── detector.py                    # MODIFY applicable_migrations stays the single pending-source over the new get_applicable
└── metadata.py                    # MODIFY _model_owned_mapping drops the migrations.applied block (hard cutover); applied_migrations read-only for backfill

src/specify_cli/upgrade/migrations/
└── m_4_0_0rc8_backfill_migration_ledger.py   # ADD — first-ordered one-way backfill (tracked unconditional, clone-local detect-gated)

src/specify_cli/state/contract.py             # MODIFY — add .kittify/migration-ledger.jsonl as GitClass.TRACKED
src/specify_cli/cli/commands/migrate_cmd.py   # MODIFY — add @app.command(name="ledger") read surface
.gitignore (repo root)                        # MODIFY — ensure the tracked ledger is not ignored

tests/upgrade/                                # unit: ledger round-trip, ledger-diff, backfill, clone-local
tests/specify_cli/upgrade/                    # unit: registry/runner/metadata changes, idempotency extensions
tests/architectural/test_migration_order_manifest.py   # ADD — build-time manifest gate + planted negatives
tests/scenarios/upgrade/migration-ledger.feature       # MODIFY — lift @wip, rebind 3 When lines, update footer
<acceptance-jvm step module>                  # ADD — 10 new step bindings

CLAUDE.md                                     # MODIFY — migration-authoring guidance → ledger model
docs/adr/3.x/2026-07-07-1-ignored-surface-backfill-migration-pattern.md  # MODIFY — author checklist → ledger model
```

**Structure Decision**: single package; all new modules sit inside `src/specify_cli/upgrade/`
(C-002 placement fence). No new wheel package, no new layer.

## Pointcut Map (file:line → change)

Seeded from the ADR Touchpoints section; `≈` marks an approximate anchor to re-confirm at
implement time. **~30 pointcuts across 7 WPs + cross-cutting acceptance.**

### WP-A / #6356 — ledger module + dual-partition data model (FR-001, 002, 003, 013, 014)
| # | file:line | change | what |
|---|-----------|--------|------|
| A1 | `src/specify_cli/upgrade/ledger.py` | **ADD** | `LedgerRecord` dataclass `{id, applied_at, result, identity, content_hash, cli_version, clone_local?}`; `MigrationLedger` with `read()`, `append(record)`, `applicable_records_for(migration)` routed by `clone_local_effect`; two partition paths; atomic full-file rewrite via `specify_cli/core/atomic.py:53`. |
| A2 | `src/specify_cli/upgrade/ledger.py` (read path) | **ADD** | legacy-id normalization on read — import `_LEGACY_MIGRATION_ID_MAP` from `metadata.py:18` so a constitution-era id and its charter-era id resolve to one record (FR-009 shared with WP-C). |
| A3 | `src/specify_cli/state/contract.py` ≈`:308` | **MODIFY** | ADD a `GitClass.TRACKED` `StateSurface` for `.kittify/migration-ledger.jsonl`; the per-clone `.kittify/migrations/clone-local.jsonl` already falls under the IGNORED `.kittify/migrations/` surface at `:308` (no new ignore). |
| A4 | repo-root `.gitignore` | **MODIFY** | confirm/ensure `.kittify/migration-ledger.jsonl` is NOT ignored (the `.kittify/migrations/` entry does not catch it — `git check-ignore` verified). |
| A5 | `src/specify_cli/upgrade/migrations/base.py:122` | **READ** (no edit here) | `clone_local_effect` is consumed by A1 as the routing key. |

### WP-B / #6357 — order manifest + build-time gate (FR-006, 007)
| # | file:line | change | what |
|---|-----------|--------|------|
| B1 | `src/specify_cli/upgrade/migrations/order_manifest.txt` | **ADD** | the ordered id list, backfilled from the current `get_all()` order (`Version(target_version)` + `runs_first` front); intentional ties annotated `# tie:<reason>` (OQ-2). |
| B2 | `src/specify_cli/upgrade/manifest.py` | **ADD** | `load_order_manifest()`, `manifest_index(id)`, tie-annotation parser. |
| B3 | `src/specify_cli/upgrade/registry.py:79-80` (`get_all`) | **MODIFY** | sort key becomes `manifest_index`; `Version(target_version)` demoted to the monotonicity cross-check consumed by the gate. |
| B4 | `tests/architectural/test_migration_order_manifest.py` | **ADD** | build-time gate: exactly-once, resolves, version-monotonic-save-ties, ≤1 `runs_first` + planted-fixture negatives for each rule (SC-004). |

### WP-C / #6358 — ledger-diff selection; retire version window + #6233 machinery (FR-004, 005, 008, 009)
| # | file:line | change | what |
|---|-----------|--------|------|
| C1 | `src/specify_cli/upgrade/registry.py:82-135` (`get_applicable`) | **MODIFY** | replace the version-window body (`:119 from_v < target <= to_v`, the `:130-132` clone-local branch) with ledger-diff: `pending = [m for m in manifest_order if m.id not in ledger.applicable_records_for(m)]`, partition-aware; then `detect()`/`can_apply` filter. |
| C2 | `src/specify_cli/upgrade/registry.py:175` (`_clone_local_selected_below_window`) | **DELETE** | plus its call site at `:130-132`. |
| C3 | `src/specify_cli/upgrade/migrations/base.py:135` (`reselect_when_recorded`) | **MODIFY/collapse** | collapse to a ledger lookup (or remove and inline at the skip gate); the sub-window clone-local branch is gone — a pulled clone's per-clone ledger simply lacks the record. |
| C4 | `src/specify_cli/upgrade/registry.py:198` (`_runs_first_selected_outside_window`) + `:212` (`_order_runs_first`) | **MODIFY** | reconcile `runs_first` with manifest order (runs_first still leads); `structural_detect` path preserved via the ledger, not the version window. |
| C5 | `src/specify_cli/upgrade/runner.py:357` (`_apply_migration` skip gate) | **MODIFY** | skip decision = "id present in the applicable ledger partition?"; `detect()` at `:377-378` stays as the pre-`apply()` idempotency guard only (C-003). |
| C6 | `src/specify_cli/upgrade/runner.py` (record path: `_apply_migration` success leg, `_record_migration_result`, `_finalize_main_metadata` ≈`:290`) | **MODIFY** | write the applied record into the ledger (partition-routed) instead of `metadata.record_migration`. `SupersededMigration`/neutralised no-ops (`base.py:186`, `detect()==False`) still record `skipped` and never re-fire (FR-008). |
| C7 | `src/specify_cli/upgrade/detector.py:49` (`applicable_migrations`) | **VERIFY/MINOR** | stays the single pending-source; it already delegates to `get_applicable`, so `--dry-run` + the `migrate ledger` surface + the compat planner share one authority (FR-011 dependency). |

### WP-D / #6359 — drift identity/checksum on apply (FR-010)
| # | file:line | change | what |
|---|-----------|--------|------|
| D1 | `src/specify_cli/upgrade/migrations/base.py:74` (`BaseMigration`) | **MODIFY** | ADD `identity: ClassVar[str]` (defaults to `migration_id`) and `content_hash_sources: ClassVar[tuple[str, ...]]` (default empty ⇒ own module file), per OQ-3. |
| D2 | `src/specify_cli/upgrade/ledger.py` | **ADD** | `compute_content_hash(migration)` via `kernel.content_digest.sha256_digest`; `drift_for(migration)` comparing recorded vs current hash by `identity`. |
| D3 | `src/specify_cli/upgrade/runner.py` (apply success leg) | **MODIFY** | compute and store `identity`+`content_hash` in the record at apply time (co-located with C6). |

### WP-E / #6360 — visibility surface (FR-011)
| # | file:line | change | what |
|---|-----------|--------|------|
| E1 | `src/specify_cli/cli/commands/migrate_cmd.py` ≈`:1274+` (end of subcommands) | **ADD** | `@app.command(name="ledger")` read-only surface; `--json`; reads via `detector.applicable_migrations` + `ledger` read API; prints applied-in-declared-order, partition, in-place-here, drift. House pattern (json payload + rich summary) mirrors `backfill-topology` at `:841`. |
| E2 | `src/specify_cli/upgrade/ledger.py` (or `ledger_report.py`) | **ADD** | report-model assembler (declared/applied/pending, partition, in-place-here via `detect()`, drift) — the one place the surface and `--json` both consume. |

### WP-F / #6361 — adoption backfill, hard cutover (FR-012, 013)
| # | file:line | change | what |
|---|-----------|--------|------|
| F1 | `src/specify_cli/upgrade/migrations/m_4_0_0rc8_backfill_migration_ledger.py` | **ADD** | one-way backfill, ordered FIRST in the manifest: reads `ProjectMetadata.applied_migrations` (normalizing legacy ids, `metadata.py:171`), writes tracked records unconditionally and clone-local records only where `detect()` confirms the effect present on this checkout; else leaves pending. |
| F2 | `src/specify_cli/upgrade/metadata.py:243-274` (`_model_owned_mapping`) | **MODIFY** | drop the `migrations.applied` block from the model-owned keys — the hard cutover: `save()` no longer writes applied state. **Decided (operator hard-cutover ruling + C-001 single authority):** F1 ALSO strips any pre-existing on-disk `migrations:` block after a successful backfill (the merge-preserving `_merge_onto_disk :348` would otherwise keep it as a dead second authority), so no stale applied-state lingers. |
| F3 | `src/specify_cli/upgrade/metadata.py:287` (`record_migration`) / `:276` (`has_migration`) | **MODIFY/retire-as-authority** | runner stops calling `record_migration`; `applied_migrations`/`has_migration` survive only for F1 to READ once. Readers in `m_3_2_6_*`, `m_4_0_0rc6_charter_pack_cutover.py`, `m_3_1_1_charter_rename.py` that call `has_migration` on OTHER migrations repoint to the ledger. |
| F4 | `src/specify_cli/upgrade/runner.py:216-229` (no-migrations stamp leg) + `:252-263` (`VersionStamp.capture`) | **VERIFY** | the version/schema stamp in `metadata.yaml` is unchanged (it is NOT the applied authority); only the applied list leaves the file. NFR-003 back-compat cost recorded. |

### WP-G / #6362 — docs / ADR follow-through (FR-016)
| # | file:line | change | what |
|---|-----------|--------|------|
| G1 | `CLAUDE.md` (migration section) | **MODIFY** | author guidance → ledger model (routing key, manifest entry, identity/hash). |
| G2 | `docs/adr/3.x/2026-07-07-1-...md` (Author Checklist ≈`:91`) | **MODIFY** | checklist → ledger model; cross-reference ADR 2026-10-17-1. |

### Cross-cutting — acceptance binding (FR-015)
| # | file:line | change | what |
|---|-----------|--------|------|
| X1 | `tests/scenarios/upgrade/migration-ledger.feature` (3 `When` lines) | **MODIFY** | rebind `spec-kitty upgrade --list-applied` and the two `spec-kitty doctor migrations` to `spec-kitty migrate ledger` (OQ-1). |
| X2 | `tests/scenarios/upgrade/migration-ledger.feature` (`@wip` tags on 7 scenarios + footer note) | **MODIFY** | lift `@wip`; update the footer's read-surface note to name `migrate ledger`. |
| X3 | `<acceptance-jvm step module>` | **ADD** | bind the 10 new steps (4 Given + 6 Then listed in the feature footer), incl. the clone fixture that seeds a recorded-but-locally-absent state. |
| X4 | `tests/architectural/test_scenario_contract.py` | **VERIFY** | stays green after the rebind + `@wip` lift (SC-007). |

## Implementation Concern Map

> Concerns inform WP decomposition; they are not WPs. The seven children below map 1:1 to the
> seven deliverables, which is the right grain here (each is a cohesive, independently-reviewable
> surface with a clean dependency edge), plus one cross-cutting acceptance concern.

### IC-01 — Ledger data & partition (→ #6356 / WP-A)
- **Purpose**: the two-partition append-only store + routing-key read/write that everything else builds on.
- **Requirements**: FR-001, FR-002, FR-003, FR-013, FR-014; NFR-001.
- **Surfaces**: `upgrade/ledger.py` (new), `state/contract.py`, repo `.gitignore`.
- **Depends-on**: none. **Risks**: atomic/crash-safety (NFR-001); partition path correctness vs the existing ignored surface.

### IC-02 — Declared order & its gate (→ #6357 / WP-B)
- **Purpose**: make execution order an explicit, checked artifact and remove the filename tiebreak.
- **Requirements**: FR-006, FR-007.
- **Surfaces**: `migrations/order_manifest.txt` (new), `upgrade/manifest.py` (new), `registry.py:79-80`, `tests/architectural/` (new gate).
- **Depends-on**: none (parallel with WP-A). **Risks**: the backfilled manifest must reproduce today's order exactly for the 124 migrations (NFR-004).

### IC-03 — Selection authority flip (→ #6358 / WP-C)
- **Purpose**: ledger-diff replaces the version window; delete the #6233 compensation; `detect()` demoted to idempotency guard.
- **Requirements**: FR-004, FR-005, FR-008, FR-009; C-001, C-003.
- **Surfaces**: `registry.py:82-135/175/198/212`, `base.py:135`, `runner.py:357 + record path`, `detector.py:49`.
- **Depends-on**: **WP-A and WP-B** (needs the ledger to diff against and the manifest to order by). **Risks**: behavioural parity (NFR-004); the clone-local tests must not regress when `_clone_local_selected_below_window` is deleted (G-risk below).

### IC-04 — Drift audit (→ #6359 / WP-D)
- **Purpose**: record identity+hash on apply; surface mismatch read-only.
- **Requirements**: FR-010; C-004.
- **Surfaces**: `base.py:74`, `ledger.py`, `runner.py` apply leg.
- **Depends-on**: **WP-A**. **Risks**: multi-file hash determinism (OQ-3); never auto-reapply (C-004).

### IC-05 — Operator visibility (→ #6360 / WP-E)
- **Purpose**: the one canonical `migrate ledger` read surface.
- **Requirements**: FR-011.
- **Surfaces**: `migrate_cmd.py`, `ledger.py`/`ledger_report.py`.
- **Depends-on**: **WP-A and WP-C** (needs records + the single pending-source). **Risks**: must consume `detector.applicable_migrations`, not recompute (single-authority).

### IC-06 — Hard-cutover adoption (→ #6361 / WP-F)
- **Purpose**: backfill existing projects once, then remove `applied_migrations` as authority.
- **Requirements**: FR-012, FR-013; NFR-003 (accepted back-compat cost).
- **Surfaces**: new backfill migration, `metadata.py:243-274/276/287`, cross-migration `has_migration` readers.
- **Depends-on**: **WP-A**. **Risks**: clone-local ambiguity (detect-gate); the no-op contract (G-2) — a pre-ledger project must not force-re-migrate.

### IC-07 — Docs (→ #6362 / WP-G)
- **Purpose**: author guidance + checklist to the ledger model.
- **Requirements**: FR-016.
- **Depends-on**: **WP-A–WP-F** (documents the shipped shape).

### IC-08 — Acceptance binding (cross-cutting)
- **Purpose**: bind the 10 steps, rebind 3 When lines, lift `@wip`.
- **Requirements**: FR-015.
- **Depends-on**: **WP-A, WP-C, WP-E, WP-F** (the behaviours and surface the steps assert).

## Dependency order

```
WP-A ─┐
      ├─> WP-C ─┬─> WP-E ─┐
WP-B ─┘         │         ├─> IC-08 acceptance ─> WP-G
WP-A ───> WP-D  │         │
WP-A ───> WP-F ─┴─────────┘
```

- **WP-A + WP-B** first, in parallel (no edge between them).
- **WP-C** after A+B (needs ledger + manifest).
- **WP-D** after A; **WP-F** after A (both parallel with C, but F's cross-migration `has_migration` repoint touches the same readers C's selection flip relies on — sequence F's `metadata.py` edits after C lands to avoid a merge seam).
- **WP-E** after A+C. **IC-08 acceptance** after A, C, E, F. **WP-G** last.

## Test strategy (red-first per WP)

- **WP-A** (`tests/upgrade/test_ledger.py` new): record round-trip in both partitions; atomic crash-safety (no torn file); legacy-id resolves to one record; partition path vs `git check-ignore`.
- **WP-B** (`tests/architectural/test_migration_order_manifest.py` new): gate passes over the real manifest; planted fixtures fail each rule (orphan, dangling, non-monotonic, two-`runs_first`) — SC-004. Plus `tests/specify_cli/upgrade/` parity test: manifest order == pre-change `get_all()` order over the 124 migrations (NFR-004).
- **WP-C** (`tests/upgrade/test_clone_local_selection.py` — EXTEND; `tests/specify_cli/upgrade/test_registry_runs_first.py` — EXTEND; `tests/upgrade/test_clone_local_migration_idempotent.py` — EXTEND): red-first — a sub-window stranded migration is selected by ledger-diff; the pulled-clone clone-local case selects via the empty per-clone ledger (not `_clone_local_selected_below_window`, which is deleted); `SupersededMigration` records `skipped` and never re-fires; runs_first still leads. SC-006.
- **WP-D** (`tests/upgrade/test_ledger_drift.py` new): a drifted-source fixture flags drift; a multi-file migration hashes deterministically; drift NEVER triggers `apply()` (C-004).
- **WP-E** (`tests/specify_cli/upgrade/test_migrate_ledger_cmd.py` new): `migrate ledger` prints applied-in-declared-order; distinguishes recorded-elsewhere vs in-place-here; flags drift; `--json` shape; read-only (no commit, no file write) — SC-005.
- **WP-F** (`tests/upgrade/test_backfill_ledger.py` new): a pre-ledger fixture's prior migrations are recorded and not re-run; clone-local record detect-gated; `metadata.yaml.migrations.applied` removed as authority, no dual-write — SC-003. No-op control: a re-run makes no commit (G-2).
- **Cross-cutting**: the 10 acceptance-jvm steps go green; 7 `@wip` scenarios lift; all 9 gate the nightly; `tests/architectural/test_scenario_contract.py` stays green — SC-007.
- **Blast radius to run** (per WP, targeted — not whole dirs): the WP's own new/extended files above, plus `tests/upgrade/` and `tests/specify_cli/upgrade/` for A/C/D/F; the single new architectural gate file for B (never the bare `tests/architectural/`); `tests/cli/` + `tests/specify_cli/upgrade/` for E. CI owns the full suites.

## Risks

- **R1 — behavioural parity for 124 migrations (NFR-004).** The manifest must reproduce today's
  `get_all()` order exactly, and ledger-diff + `detect()` must select the same set a version-window
  run would, minus the two intended fixes. *Mitigation:* the WP-B parity test (order identity) and
  the WP-C extensions of the existing selection/idempotency gates; diff the selected set on a
  corpus fixture before/after.
- **R2 — #6233 machinery deletion must not regress clone-local behaviour (SC-006).** Deleting
  `_clone_local_selected_below_window` and collapsing `reselect_when_recorded` is the sharpest
  edge. *Mitigation:* extend `test_clone_local_selection.py` / `test_clone_local_migration_idempotent.py`
  red-first so the partition mechanism is proven to carry exactly what the deleted code carried;
  keep `detect()` as the idempotency guard so a present effect still no-ops.
- **R3 — hard-cutover backfill correctness (G-2 no-op contract).** A wrong backfill re-runs
  migrations on every existing project. *Mitigation:* the detect-gate for clone-local; the
  pre-ledger fixture + re-run no-op control; backfill ordered first so the same run sees a
  populated ledger.
- **R4 — stale `migrations:` block lingering after cutover (F2 sub-decision).** The
  merge-preserving `save` keeps unknown on-disk keys; a dropped-but-not-removed `migrations.applied`
  would be a dead second authority. *Resolution (RULED):* F1 removes the on-disk `migrations:` block
  once after a successful backfill — the operator's hard-cutover ruling and C-001 (single authority)
  forbid a dead second authority; this is the direct entailment, not a standalone decision.
- **R5 — acceptance-jvm step/fixture location.** The clone Given needs a fixture seeding a pushed
  record without the local effect. *Mitigation:* locate the existing upgrade step module; reuse the
  `git check-ignore`/commit helpers already bound by the two non-`@wip` scenarios.
- **R6 — placement/SSOT drift.** Any accidental new top-level package or layer edit reds
  `test_layer_rules.py`. *Mitigation:* SC-008 asserts no change to wheel packages / landscape /
  layer rules; everything stays under `upgrade/`.

## Quality gates

- `ruff check .` and `ruff format --check .` clean on all touched files (format is a separate gate;
  per-file checks use `--force-exclude`).
- `mypy` zero new issues; complexity ≤15 (extract helpers in `ledger.py`/`registry.py`); repeated
  literals hoisted (Sonar S1192) — the ledger paths and record-key strings become module constants.
- Every new branch/helper has a focused test in the same WP (Sonar new-code coverage; diff-cover ≥90%).
- Terminology guard not implicated (no charter/offering prose); `test_no_legacy_terminology.py`
  unaffected.
- SC-008 ratchet: `pyproject.toml` wheel packages, `landscape`, `test_layer_rules.py` unchanged.

## Complexity Tracking

*No Charter Check violations — table intentionally empty.*
