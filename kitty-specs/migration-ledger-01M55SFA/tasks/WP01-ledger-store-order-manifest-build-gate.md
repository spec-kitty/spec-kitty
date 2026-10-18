---
work_package_id: WP01
title: Ledger store, order manifest & build-time gate (IC-01, IC-02)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-006
- FR-007
- FR-009
- FR-013
- FR-014
- NFR-001
- FR-012
- C-002
- SC-004
- SC-008
planning_base_branch: issue-5230-migration-ledger-impl
merge_target_branch: issue-5230-migration-ledger-impl
branch_strategy: Planning artifacts for this mission were generated on issue-5230-migration-ledger-impl. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5230-migration-ledger-impl unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-migration-ledger-01M55SFA
base_commit: 103b68497fcab2d9e84668a8aa9db27d6d93a4a0
created_at: '2026-10-17T21:15:45.415545+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
- T009
history:
- timestamp: '2026-10-17T21:06:30Z'
  lane: planned
  agent: system
  shell_pid: ''
  action: Prompt generated via /spec-kitty.tasks-packages
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- src/specify_cli/upgrade/ledger.py
- src/specify_cli/upgrade/manifest.py
- src/specify_cli/upgrade/migrations/order_manifest.txt
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_backfill_migration_ledger.py
- tests/architectural/test_migration_order_manifest.py
- tests/upgrade/test_ledger.py
- tests/upgrade/test_order_manifest.py
- tests/upgrade/test_backfill_migration.py
execution_mode: code_change
lane: planned
owned_files:
- src/specify_cli/upgrade/ledger.py
- src/specify_cli/upgrade/manifest.py
- src/specify_cli/upgrade/migrations/order_manifest.txt
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_backfill_migration_ledger.py
- src/specify_cli/state/contract.py
- .gitignore
- tests/architectural/test_migration_order_manifest.py
- tests/upgrade/test_ledger.py
- tests/upgrade/test_order_manifest.py
- tests/upgrade/test_backfill_migration.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 – Ledger store, order manifest & build-time gate

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (`role: implementer`) before parsing the rest of this prompt. If
unavailable, run `spec-kitty agent profile list` and pick the best Python implementer match.

Implementation command (no dependencies): `spec-kitty implement WP01`

---

## Objective

Build the **foundation** the whole mission stands on: the two-partition append-only ledger, the
checked-in order manifest, and the build-time gate that guards it. This WP adds only NEW files — it
does **not** edit `registry.py`/`runner.py`/`base.py` (those belong to WP02). Everything lands
inside `src/specify_cli/upgrade/` (C-002 placement fence; SC-008 — no wheel/landscape/layer change).

Grounded in `plan.md` Pointcut Map **IC-01 (A1–A4)** and **IC-02 (B1–B2, B4)**, ADR
`docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`, and spec FR-001/002/003/006/007/009/013/014,
NFR-001.

## Context & Constraints — design invariants (carry these exactly)

- **Two partitions, routed by `clone_local_effect`.** `clone_local_effect` stops being a
  reselection trigger and becomes the **routing key**: a migration whose effect is clone-local
  reads/writes the per-clone ledger `.kittify/migrations/clone-local.jsonl` (inside the already
  IGNORED `.kittify/migrations/` surface); everything else reads/writes the tracked ledger
  `.kittify/migration-ledger.jsonl`.
- **Atomic single-writer durability (NFR-001).** Every append is a **full-file atomic rewrite**
  via the existing `specify_cli/core/atomic.py` wrapper (→ `kernel.atomic`). **No `O_APPEND`.** A
  crash leaves a valid old-or-new ledger, never a torn/partial file. (`kernel.locks` is a NAMED
  extension point only — do NOT build a cross-process lock here, C-005.)
- **Legacy-id normalization ON READ.** Import `_LEGACY_MIGRATION_ID_MAP` from `metadata.py` so a
  constitution-era id and its charter-era id resolve to ONE ledger record (FR-009). Normalization
  happens on read, not on write.
- **No import-dependency on `base.py`.** `ledger.py` must reference migration identity /
  `content_hash_sources` via **defensive `getattr`** (e.g. `getattr(migration, "identity",
  migration.migration_id)`), NOT by importing `BaseMigration`. The identity/`content_hash_sources`
  ClassVars themselves land in WP02's `base.py`; this WP must work whether or not they exist yet.
- **Order manifest reproduces today's order.** `order_manifest.txt` must reproduce the current
  `registry.get_all()` order for the existing migrations **exactly** (NFR-004 parity), AND list the
  NEW `m_4_0_0rc8_backfill_migration_ledger` — **created in THIS WP (T009)** — **FIRST** (it is
  `runs_first` / ordered first so the same run sees a populated ledger). Because the migration file
  and its manifest entry both live in WP01, the build gate's dangling-entry check stays green in this
  lane (seam fix: the entry never references an unregistered migration).
- **Backfill migration is owned here; the metadata CUTOVER is WP04.** This WP CREATEs the backfill
  migration and proves it WRITES ledger records (tracked unconditional / clone-local detect-gated).
  It MAY attempt the R4 stale-`migrations:`-block strip, but WP01's test asserts only that ledger
  records are written — it does NOT assert a permanent strip. Permanence (the block never re-added,
  because `_model_owned_mapping` no longer owns it) is proven in WP04.
- Complexity ≤15, repeated literals hoisted to module constants (ledger paths, record keys).

## Pointcut Map (file:line → change)

| # | file | change | what |
|---|------|--------|------|
| A1 | `src/specify_cli/upgrade/ledger.py` | **ADD** | `LedgerRecord` dataclass `{id, applied_at, result, identity, content_hash, cli_version, clone_local?}`; `MigrationLedger` with `read()`, `append(record)`, `applicable_records_for(migration)` routed by `clone_local_effect`; two partition paths; atomic full-file rewrite via `core/atomic.py`. |
| A2 | `src/specify_cli/upgrade/ledger.py` (read path) | **ADD** | legacy-id normalization on read — `_LEGACY_MIGRATION_ID_MAP` from `metadata.py` (FR-009). |
| D2 | `src/specify_cli/upgrade/ledger.py` | **ADD** | `compute_content_hash(migration)` via `kernel.content_digest.sha256_digest`; `drift_for(migration)`; report-model assembler (declared/applied/pending, partition, in-place-here via `detect()`, drift) — the one place WP03's surface and `--json` both consume. (Drift ClassVars land in WP02; use defensive `getattr`.) |
| A3 | `src/specify_cli/state/contract.py` ≈`:308` | **MODIFY** | ADD a `GitClass.TRACKED` `StateSurface` for `.kittify/migration-ledger.jsonl`; the per-clone file already falls under the IGNORED `.kittify/migrations/` surface (no new ignore). |
| A4 | repo-root `.gitignore` | **MODIFY** | confirm/ensure `.kittify/migration-ledger.jsonl` is NOT ignored (verify with `git check-ignore`). |
| B1 | `src/specify_cli/upgrade/migrations/order_manifest.txt` | **ADD** | ordered `migration_id` list (one per line; blank / `#` lines ignored), backfilled from current `get_all()` order; `m_4_0_0rc8_backfill_migration_ledger` first; intentional equal-`target_version` runs annotated `# tie:<reason>`. |
| B2 | `src/specify_cli/upgrade/manifest.py` | **ADD** | `load_order_manifest()`, `manifest_index(id)`, tie-annotation parser. |
| B4 | `tests/architectural/test_migration_order_manifest.py` | **ADD** | build-time gate + 4 planted negatives. |
| F1a | `src/specify_cli/upgrade/migrations/m_4_0_0rc8_backfill_migration_ledger.py` | **ADD** | one-way backfill, listed FIRST in the manifest: reads `applied_migrations` (legacy-normalized, read-only), writes tracked records unconditionally + clone-local records only where `detect()` confirms. (The metadata cutover that makes `applied_migrations` non-authoritative is WP04.) |

> `A5` (`base.py:122` `clone_local_effect`) is consumed here read-only; do not edit `base.py`.
> Seam split: the backfill MIGRATION + its manifest entry are WP01; the metadata CUTOVER (drop
> `migrations.applied` from `_model_owned_mapping`, retire `record_migration`/`has_migration`,
> repoint the 4 readers) is WP04 (it needs WP02's record-path flip first).

## Owned files (disjoint)

- `src/specify_cli/upgrade/ledger.py`
- `src/specify_cli/upgrade/manifest.py`
- `src/specify_cli/upgrade/migrations/order_manifest.txt`
- `src/specify_cli/state/contract.py`
- `.gitignore`
- `src/specify_cli/upgrade/migrations/m_4_0_0rc8_backfill_migration_ledger.py`
- `tests/architectural/test_migration_order_manifest.py`
- `tests/upgrade/test_ledger.py`
- `tests/upgrade/test_order_manifest.py`
- `tests/upgrade/test_backfill_migration.py`

## Red-first tests to write FIRST

1. **`tests/upgrade/test_ledger.py`** (NEW): record round-trip in BOTH partitions; a crash-safety
   test asserting no torn file on a simulated mid-write failure (old-or-new only); a legacy-id test
   asserting a constitution-era id and its charter-era id resolve to ONE record; a partition-path
   test asserting the tracked path is NOT git-ignored and the clone-local path IS (via
   `git check-ignore`). — FR-001, FR-002, FR-003, FR-009, FR-013, FR-014, NFR-001.
2. **`tests/upgrade/test_order_manifest.py`** (NEW): `load_order_manifest()` parses ids + ignores
   blank/`#` lines; the tie annotation parses; and a **parity** assertion — manifest order ==
   pre-change `registry.get_all()` order over the existing migrations (NFR-004). — FR-006.
3. **`tests/architectural/test_migration_order_manifest.py`** (NEW): the gate PASSES over the real
   manifest, and FAILS over 4 planted-fixture negatives — (a) an **orphan** (registered migration
   missing from the manifest), (b) a **dangling** entry (manifest id with no registered migration),
   (c) a **non-monotonic** order (unannotated `target_version` decrease), (d) **two `runs_first`**
   migrations. — FR-007, SC-004.
4. **`tests/upgrade/test_backfill_migration.py`** (NEW): the backfill migration, applied to a
   pre-ledger fixture, **WRITES** ledger records — tracked records **unconditional**, clone-local
   records **only where `detect()` confirms** the effect present here (else left pending). Asserts
   the records exist in the correct partitions; does NOT assert a permanent `migrations:`-block strip
   (that end-state is WP04's `test_backfill_ledger.py`). — FR-012.

Write these red FIRST; they must fail before the implementation exists, then go green.

## Subtasks & Detailed Guidance

### T001 – `LedgerRecord` dataclass (FR-003)
Define the append-only record shape `{id, applied_at, result, identity, content_hash, cli_version,
clone_local?}` with JSONL (de)serialization. Hoist record-key strings to module constants (S1192).

### T002 – `MigrationLedger` read/append/route + atomic write (FR-001, FR-002, NFR-001)
Two partition paths as module constants. `read()` parses JSONL; `append(record)` does a full-file
atomic rewrite via `core/atomic.py` (no `O_APPEND`). `applicable_records_for(migration)` selects
the partition by `getattr(migration, "clone_local_effect", False)` (routing key).

### T003 – Legacy-id normalization on read (FR-009)
Apply `_LEGACY_MIGRATION_ID_MAP` (imported from `metadata.py`) when reading so aliased ids collapse
to one record. Keep write paths raw.

### T004 – Content-hash + drift primitives + report assembler (D2)
`compute_content_hash(migration)` = `sha256_digest` over the defining module source by default, or
over the sorted-concatenated `getattr(migration, "content_hash_sources", ())` files when declared.
`drift_for(migration)` compares recorded vs current hash keyed on `identity`
(`getattr(migration, "identity", migration.migration_id)`). Build the report model
(declared/applied/pending, partition, in-place-here via `detect()`, drift) as the single assembler
WP03 will consume. **Defensive getattr throughout — no `base.py` import.**

### T005 – State contract + `.gitignore` (FR-013)
Add the `GitClass.TRACKED` surface for `.kittify/migration-ledger.jsonl` in `state/contract.py`;
ensure `.gitignore` does not catch it; confirm the per-clone file stays under the ignored surface.

### T006 – Order manifest (FR-006, NFR-004)
Generate `order_manifest.txt` from the current `get_all()` order; put
`m_4_0_0rc8_backfill_migration_ledger` first; annotate any intentional equal-`target_version` run
with `# tie:<reason>`.

### T007 – `manifest.py` loader (FR-006)
`load_order_manifest()`, `manifest_index(id)`, tie-annotation parser. Complexity ≤15 (extract
helpers).

### T008 – Build-time gate + the new test files (FR-007, SC-004)
Implement the gate rules (exactly-once / resolves / version-monotonic-save-annotated-ties / ≤1
`runs_first` leading) and the 4 planted negatives; land the red-first gate/ledger/manifest test files
green.

### T009 – Backfill migration (writes ledger records; listed first) (FR-012)
CREATE `src/specify_cli/upgrade/migrations/m_4_0_0rc8_backfill_migration_ledger.py`: read
`applied_migrations` (legacy-normalized via the map, read-only), write **tracked** records
**unconditionally** and **clone-local** records **only where `detect()` confirms** the effect here
(else leave pending — idempotent `apply()` re-runs once; accepted one-time cost). List it FIRST in
`order_manifest.txt` (T006) so it is `runs_first` and the same run sees a populated ledger. It MAY
attempt the R4 stale-`migrations:`-block strip, but the WP01 test asserts only that ledger records
are written — the PERMANENT strip (and dropping `migrations.applied` from `_model_owned_mapping`) is
WP04. Land `tests/upgrade/test_backfill_migration.py` green.

## Test strategy & blast radius (targeted — NOT whole dirs)

Run, and record counts in the PR:
- `tests/upgrade/test_ledger.py`, `tests/upgrade/test_order_manifest.py`,
  `tests/upgrade/test_backfill_migration.py`
- the single named arch gate: `tests/architectural/test_migration_order_manifest.py` (NEVER the
  bare `tests/architectural/`)
- regression surface: `tests/upgrade/` and `tests/specify_cli/upgrade/`

CI owns the full suites.

## Quality gates

- `ruff check` + `ruff format --check` clean on touched files (per-file checks use
  `--force-exclude`); `mypy` zero new issues; complexity ≤15; repeated literals hoisted. No blanket
  `# noqa` / `# type: ignore`.
- SC-008 ratchet: do NOT touch `pyproject.toml` wheel packages, the `landscape` fixture, or
  `test_layer_rules.py`.

## Acceptance criteria satisfied

SC-004 (manifest gate passes real / fails planted negatives); the backfill migration's record-writing
half of SC-003 (end-state cutover is WP04); foundation for SC-001/002/005;
FR-001/002/003/006/007/009/012/013/014, NFR-001.

## Risks & Mitigations

- **R1 parity (NFR-004):** manifest must reproduce today's order — the parity test in
  `test_order_manifest.py` is the guard; diff the ordered id list before/after.
- **Atomic correctness (NFR-001):** reuse `core/atomic.py`; the crash-safety test is the guard.

## Review Guidance

Confirm: no `base.py` import in `ledger.py` (getattr only); tracked vs clone-local partition proven
by `git check-ignore`; manifest lists the backfill first; 4 planted negatives each fail the gate.

## Activity Log

- 2026-10-17T21:06:30Z – system – lane=planned – Prompt created.
