# Implementation Plan: Preserve user assets in `migrate --force` and git-source fetch

**Branch**: `spec/asset-preservation-migrate-fetch` | **Date**: 2026-09-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/asset-preservation-migrate-fetch-01M3E857/spec.md`

## Summary

Close the last two unrouted destructive filesystem flows in epic #4915 by routing them through the
existing `asset_preservation` primitives — no new framework. (1) `migrate --force` must stop
`unlink`ing a `.kittify/` asset that merely *differs* from its package default (#4961); (2) git-source
`charter/doctrine fetch` must stop `rmtree`ing a pre-existing hand-authored pack on a failed clone
(#4960) and stop `reset --hard`ing away local pack edits while resolving the wrong ref (#4989). A
fourth work stream extends the destructive-op architectural gate to both modules so the class stays
closed by construction. Technical approach is fully grounded in `research.md` (F1–F4).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: existing `specify_cli.asset_preservation` (guard, provers, backup),
`specify_cli.git.ref_advance` (dirty predicate), `specify_cli.doctrine.snapshot` (atomic-install
reference pattern). No new third-party dependency is added (supply-chain security section N/A).
**Storage**: filesystem (`.kittify/` project assets; git-sourced org packs, possibly outside repo)
**Testing**: pytest (`PWHEADLESS=1 .venv/bin/python -m pytest`), red-first regressions + mutation testing
**Target Platform**: Linux/macOS/Windows dev CLI (cross-platform path/symlink handling required)
**Project Type**: single (CLI/library, `src/specify_cli/**` + `src/charter/**`)
**Performance Goals**: N/A (correctness fix; no hot path touched)
**Constraints**: fail-closed toward preservation; honest exit/messaging; reuse primitives (NFR-001..004);
no CLI version bump (C-002); git-source has no manifest → backup + clone-to-temp-swap (C-003)
**Scale/Scope**: 2 product modules + 1 arch-gate module; ~3 focused fixes + gate extension + CHANGELOG

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Charter present (`.kittify/charter/charter.md`). Relevant binding items:
- **User Customization Preservation invariant** — the mission's whole point; satisfied by routing both
  flows through `asset_preservation` (FR-001..004, NFR-001).
- **Canonical sources / no improvisation** — reuse `guard_destructive_removal`, `backup_before_overwrite`,
  `archive_into`, `_dirty_entries`, and the `snapshot.py` pattern; do not open-code backups (NFR-003).
- **ATDD-first / red-first** — each FR carries an issue-pinned regression, RED on base, GREEN on fix (C-001).
- **USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY** — mutation-test the preservation/fail-close branches:
  a mutant that restores the raw `unlink`/`rmtree`/local-ref-reset must red a test (review gate).
- **Architectural gate discipline** — extend the destructive-op census to both modules; re-pin/trim the
  line-pinned `git_source.py:98:reset_hard` allowlist entry (FR-005, F4).
- **Terminology** — "Mission" not "Feature"; no legacy terms.

No violations to justify → Complexity Tracking empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/asset-preservation-migrate-fetch-01M3E857/
├── plan.md              # This file
├── research.md          # F1–F4 grounding ledger (seeded from the read-only squad)
├── data-model.md        # Phase 1: the ownership/asset/pack entities
├── quickstart.md        # Phase 1: how to reproduce (red) and verify (green) each fix
├── contracts/
│   └── preservation-contract.md   # the invariant each fixed site must honour
├── traces/              # tooling-friction / approach / design-decisions tracer files
└── tasks.md             # Phase 2 (/spec-kitty.tasks) — NOT created here
```

### Source Code (repository root)

```
src/specify_cli/
├── runtime/migrate.py                 # WP01 (#4961): classify_asset + execute_migration removal
├── doctrine/sources/git_source.py     # WP02 (#4960 _first_install, #4989 _update)
├── asset_preservation/                # REUSE ONLY: guard.py, provers.py, backup.py
├── git/ref_advance.py                 # REUSE ONLY: _dirty_entries
└── doctrine/snapshot.py               # REFERENCE ONLY: atomic-install-with-backup pattern

tests/
├── upgrade/test_migrate_integration.py           # WP01: re-pin + red-first
├── specify_cli/doctrine/test_sources.py          # WP02: TestGitSource re-pin + red-first
└── architectural/
    ├── test_destructive_op_routing.py            # WP03: re-pin/trim :160-164 allowlist
    ├── test_mutation_ownership_routing.py        # WP03: extend scanned module set
    └── _destructive_op_census.py                 # WP03: census helper
docs/changelog/CHANGELOG.md                       # WP03: fix entry (no version bump)
```

**Structure Decision**: Single-project CLI. Two disjoint product modules (`migrate.py`,
`git_source.py`) fixed independently; a third stream extends the shared arch gate and adds the
CHANGELOG entry after both fixes land.

## Complexity Tracking

*No Constitution Check violations — section intentionally empty.*

## Parallel Work Analysis

### Dependency Graph

```
WP01 (#4961 migrate)  ─┐
                        ├─→ WP03 (FR-005 arch gate + CHANGELOG)
WP02 (#4960+#4989 git) ─┘
WP01 ∥ WP02 (disjoint file sets → parallel lanes)
WP03 depends on WP01 AND WP02 (the gate asserts the fixed sites carry no raw destructive literal;
    it can only pass once both fixes exist)
```

### Work Distribution (write-scope disjoint → clean lanes)

> **Design corrected by the post-plan adversarial pass — see research.md F5–F10 (dispositioned).**
> The bullets below reflect the corrected design; the earlier naive prover/ref/backup approach was
> found defective and must not be used.

- **WP01 — migrate preservation (FR-001, FR-002; #4961).** Writes: `src/specify_cli/runtime/migrate.py`,
  `tests/upgrade/test_migrate_integration.py`, **`tests/runtime/test_e2e_runtime_integration.py`** (F5/F9).
  Route BOTH the IDENTICAL and SUPERSEDED removal through
  `guard_destructive_removal(path, project_dir, prover=CanonicalContentProver(canonical=<package-counterpart bytes>), backup_parent=None, dry_run=dry_run)` (F5): byte-match to the shipped counterpart
  proves genuine duplicates (still removed → NFR-004), a differing file (customised OR old default) is
  unproven → preserved in place (fixes #4961, closes the marker false-positive). Thread the counterpart
  bytes into `execute_migration` via `_find_package_counterpart` (or have `classify_asset` return them).
  Drop the inert `ManifestProver`. Keep `classify_asset` honest for `--dry-run`. Re-pin every deletion
  pin (the 6 in `test_migrate_integration.py` incl. the #285 `test_version_skew_scenario_end_to_end`
  redefined removed→preserved, the in-file IDENTICAL pins, AND the SUPERSEDED+IDENTICAL pins in
  `test_e2e_runtime_integration.py` ~:299-537); also run `tests/runtime/test_global_runtime_convergence_unit.py`.
  Add a red-first "customised template survives execute_migration(dry_run=False), exit 0" regression.
- **WP02 — git-source preservation (FR-003, FR-004; #4960 + #4989).** Writes:
  `src/specify_cli/doctrine/sources/git_source.py`, `tests/specify_cli/doctrine/test_sources.py`.
  `_first_install` (F8): clone into a `.tmp-<uuid>` sibling and promote via the `snapshot.py:196-228`
  move-aside/restore pattern (NOT a bare `Path.replace`); only ever rmtree the temp; refuse up front
  when `local_path` exists AND is non-empty (drop the "is a clone of url" helper — unobservable here) —
  but PERMIT a pre-existing EMPTY dir (the `resolve.py::_resolve_git` caller passes an empty `mkdtemp`).
  `_update` (F6/F7): resolve reset target by ref type (`origin/<ref>` only when
  `refs/remotes/origin/<ref>` resolves, else bare `<ref>`); before any reset run the ahead check
  (`git rev-list --count origin/<ref>..HEAD` > 0) AND `_dirty_entries` (wired with resolved SHA +
  `_target_tree_paths`); for dirty OR ahead/divergent, preserve git-natively (backup branch/ref) or
  fail-closed refuse — a worktree archive alone is INSUFFICIENT for committed-ahead history. Both bugs
  share the file → ONE lane. Re-pin `test_sources.py:188-191` (call-order fetch→reset breaks) and
  verify :214/:264; add red-first regressions for pre-existing-pack, checkout-failure, dirty-update,
  committed-ahead, ref-advance, and tag/SHA-pin non-regression.
- **WP03 — close the class + document (FR-005; depends on WP01, WP02).** Writes:
  `tests/architectural/test_destructive_op_routing.py`, `test_mutation_ownership_routing.py`,
  `_destructive_op_census.py`, `docs/changelog/CHANGELOG.md`. (F9) git-argv gate already scans all of
  src → only re-pin/trim the `git_source.py:98:reset_hard` allowlist entry + fix its false rationale.
  FS-op gate: add `migrate.py` to BOTH `_module_set()` AND `_ROUTED_MODULES` (else
  `test_pinned_routed_module_set_is_complete` fails); add `git_source.py` to `_module_set()` ONLY
  (scanned-not-routed, mirror the `research.py` never-allowlist guard); add allowlist entries for
  `migrate.py:239` empty-only `rmdir` and the `git_source.py` temp `shutil.rmtree` (+ `shutil.move`
  swap if used). Prove the gate fail-able both ways; add the CHANGELOG entry (no version bump). Owns
  CHANGELOG.md solely so no lane conflicts.

### Coordination Points

- **Integration**: after WP01 ∥ WP02 merge, WP03 runs the extended arch gate over the combined tip.
- **Pre-merge**: full `tests/architectural/` + `tests/ci/` battery + regression lens over the combined
  tip (brownfield discipline); gate = will main's always-on battery be GREEN?
- **Reviews**: adversarial reviewer-renata, mutation-tested on the preservation/fail-close branches
  specifically (a mutant that restores the raw destroy must red a test). Issue-matrix verdict recorded
  (#4961→WP01, #4960→WP02, #4989→WP02) before approval.
