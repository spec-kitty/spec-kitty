# Tasks: Preserve user assets in `migrate --force` and git-source fetch

**Mission**: `asset-preservation-migrate-fetch-01M3E857` | **Branch**: `spec/asset-preservation-migrate-fetch`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Contract**: [contracts/preservation-contract.md](./contracts/preservation-contract.md) · **Research**: [research.md](./research.md)

Design authority: `research.md` F1–F10 (post-plan adversarial pass, dispositioned). All fixes are
ATDD red-first, reuse the `asset_preservation` primitives, and add no CLI version bump.

## Subtask Index (reference table — completion is event-sourced via `mark-status`)

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: customised template survives `execute_migration(dry_run=False)`, exit 0 | WP01 | |
| T002 | Thread package-counterpart bytes into `execute_migration` (via `_find_package_counterpart`) | WP01 | |
| T003 | Route IDENTICAL+SUPERSEDED removal through `guard_destructive_removal(CanonicalContentProver(canonical=…), backup_parent=None, dry_run)`; drop raw `unlink` | WP01 | |
| T004 | Keep `classify_asset`/`--dry-run` reporting honest (differing → customised/preserved) | WP01 | |
| T005 | Re-pin deletion tests in `test_migrate_integration.py` (incl. #285 version-skew) to corrected contract | WP01 | |
| T006 | Re-pin `test_e2e_runtime_integration.py` SUPERSEDED+IDENTICAL pins; run `test_global_runtime_convergence_unit.py` | WP01 | |
| T007 | Red-first regressions in `test_sources.py`: pre-existing-pack, checkout-fail, empty-dir permitted, dirty-update, committed-ahead, ref-advance, tag/SHA non-regression | WP02 | |
| T008 | `_first_install`: clone-to-temp + snapshot move-aside promote; refuse on exists-&-non-empty (permit empty); rmtree only the temp | WP02 | |
| T009 | `_update`: ref-type resolution (`origin/<ref>` branch / bare tag-SHA) + ahead & dirty checks + git-native backup or fail-closed refuse before reset | WP02 | |
| T010 | Re-pin `test_sources.py:188-191` call-order; verify `:214`/`:264` | WP02 | |
| T011 | Extend FS-op gate `_module_set()` to `migrate.py` + `git_source.py` | WP03 | |
| T012 | Add `migrate.py` to `_ROUTED_MODULES`; keep `git_source.py` scanned-not-routed + never-allowlist guard | WP03 | |
| T013 | Allowlist `migrate.py:239` empty `rmdir` + `git_source.py` temp `rmtree`; re-pin git-argv reset allowlist entry + fix rationale | WP03 | |
| T014 | Prove both gates fail-able (add/remove a raw literal) | WP03 | |
| T015 | CHANGELOG entry (no version bump) | WP03 | |

WP01 ∥ WP02 (disjoint write scopes). WP03 depends on WP01 AND WP02.

---

## WP01 — migrate preserves customised assets (#4961)

- **Goal**: `migrate --force`/`--dry-run` never delete a `.kittify/` asset that differs from its package
  default; only byte-identical defaults are removed. FR-001, FR-002.
- **Priority**: P1 (headline data-loss). **Independent test**: customise a shipped template → it survives.
- **Subtasks**: T001, T002, T003, T004, T005, T006
- **Sketch**: red-first regression → thread counterpart bytes → route removal through the guard with a
  byte-match canonical prover (`backup_parent=None`) → honest dry-run labels → re-pin the deletion tests
  (this file + `test_e2e_runtime_integration.py`).
- **Dependencies**: none. **Prompt**: `tasks/WP01-migrate-preserve-customised-assets.md`
- **Risks**: NFR-004 regression if the prover can't prove identical defaults — mitigated by
  `CanonicalContentProver(canonical=<counterpart bytes>)` (F5). #285 version-skew becomes preserve (intended).

## WP02 — git-source fetch preserves hand-authored packs (#4960, #4989)

- **Goal**: `charter/doctrine fetch` never `rmtree`s a pre-existing pack on a failed clone and never
  silently discards local pack edits; a configured `ref` advances. FR-003, FR-004.
- **Priority**: P1. **Independent test**: seed a pack, fail the clone → pack survives; dirty/ahead update → preserved.
- **Subtasks**: T007, T008, T009, T010
- **Sketch**: red-first regressions → `_first_install` clone-to-temp + move-aside + refuse-on-nonempty
  (permit empty) → `_update` ref-type resolution + ahead/dirty git-native backup-or-refuse → re-pin call-order test.
- **Dependencies**: none. **Prompt**: `tasks/WP02-git-source-preserve-packs.md`
- **Risks**: blanket `origin/<ref>` regresses tag/SHA packs (F6); worktree archive loses committed history
  (F7) — both handled explicitly. Cross-platform swap onto existing dir (F8).

## WP03 — close the destructive-op class + document (FR-005)

- **Goal**: the destructive-op / mutation-ownership arch gate scans both product modules and stays
  fail-able; CHANGELOG documents the fix. FR-005.
- **Priority**: P2 (regression guard). **Independent test**: adding a raw literal to either module reds the gate.
- **Subtasks**: T011, T012, T013, T014, T015
- **Sketch**: extend `_module_set()` → add `migrate.py` to `_ROUTED_MODULES`, `git_source.py` scanned-not-routed
  + never-allowlist guard → allowlist the guarded literals + re-pin the git-argv reset entry → prove fail-able → CHANGELOG.
- **Dependencies**: WP01, WP02 (the gate can only pass once both fixes exist).
- **Prompt**: `tasks/WP03-close-destructive-op-class.md`
- **Risks**: line-pinned allowlist entry drift (F4/F9); `_ROUTED_MODULES` completeness test.
