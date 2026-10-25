# Implementation Plan: Residue-safe migration sweep and fabricated-identity audit

**Branch**: `fix/residue-safe-migration-sweep` | **Date**: 2026-10-25 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/residue-safe-migration-sweep-01M5SS0F/spec.md`

## Summary

`spec-kitty upgrade` still treats a `kitty-specs/` folder holding only untracked, Mission-shaped leftovers as a Mission. It fabricates and auto-commits a second identity there (#6669, P0) and lets four shipped migrations rewrite its files. The fix has five parts:
- **One rule.** The residue decision in `context/mission_resolver.py` becomes git-aware.
- **Four supersessions.** The residue-writing shipped migrations (`0.9.0`, `0.9.1`, `2.0.6`, `3.1.1`) are superseded through `upgrade/supersession.py` by residue-aware successors in the same slots. Each successor is gated off where its predecessor already ran, and no shipped module is edited.
- **One notice.** A single shared residue notice, which the upgrade runner collapses to one line per folder per run.
- **An honest gate.** The migration walker gate is reclassified under the new rule.
- **A doctor finding** (#6668): a report-only, three-signal `doctor mission-state --audit` warning for identities that earlier upgrades already fabricated.

## Engineering Alignment (confirmed by the operator, 2026-10-25)

- **Residue rule.** `is_kitty_specs_residue` decides in one of two modes. Git-aware mode applies when git can run and the project tracks at least one path under `kitty-specs/` (FR-002). In that mode a folder is residue when `is_mission_dir` rejects it and neither `spec.md` nor `meta.json` is on disk. In the other mode, today's file-presence rule applies. `tracked=` and `repo_root=` are threaded through for batched walks (NFR-003).
- **Supersession.**
  - `SUPERSEDED_MIGRATIONS` gains `0.9.0_frontmatter_only_lanes`, `0.9.1_complete_migration`, `2.0.6_consistency_sweep` and `3.1.1_normalize_status_json`.
  - Each successor is a new module with the predecessor's `target_version`, placed immediately after it in `order_manifest.txt` with a `# tie:` annotation.
  - Its `detect()` is False when the predecessor is settled in the same view migration selection uses: a ledger `success`, or pending first-adoption settlement.
- **Notices (DM 01M5SVE8QC28KRAZM25PR2N4PT).** Every residue-aware step emits the same `RESIDUE_NOTICE` text. The upgrade runner collapses repeated identical residue notices for the same folder across steps in one run.
- **Doctor finding.** `audit/classifiers/fabricated_identity.py` reports `FABRICATED_IDENTITY_SUSPECTED` as a WARNING outside `TEAMSPACE_BLOCKER_CODES`, with `artifact_path=meta.json`. Signal 1 uses the allow-list. Signal 2 uses `baseline_slug_fields()`, extracted from `build_baseline_feature_meta`. Signal 3 uses `mission_runtime.identity.mid8_from_slug` (Crockford alphabet).

## Technical Context

**Language/Version**: Python 3.11+ (the CLI's supported floor; CI also runs newer interpreters nightly)
**Primary Dependencies**: no new dependencies. In-repo: `kernel.git` (`run_git`, `tracked_paths`, `is_tracked`, `GitCommandError`), `specify_cli.upgrade` (registry, ledger, runner, supersession), `specify_cli.audit`, `mission_runtime.identity`
**Storage**: files only. `kitty-specs/<slug>/` artifacts, `.kittify/migration-ledger.jsonl` and `.kittify/migrations/clone-local.jsonl` (the migration ledger), `order_manifest.txt`
**Testing**: pytest. Red-first regression through the real `spec-kitty upgrade` CLI (`tests/integration/migration/`), unit tests per seam (`tests/specify_cli/migration/`, `tests/upgrade/`, `tests/context/`, `tests/audit/`), and architectural gates (`tests/architectural/test_migration_walkers_use_mission_predicate.py`, `test_migration_order_manifest.py`, `tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py`-style supersession pins). Every repair scenario is driven through `MigrationRegistry` or the CLI, never a direct import of a shipped class.
**Target Platform**: Linux, macOS and Windows developer machines and CI runners where `spec-kitty upgrade` runs, with or without git installed
**Project Type**: single Python project (`src/` layout)
**Performance Goals**: the residue decision adds at most 2 git calls per folder walk plus at most 2 per identity-less folder; 0 for a folder whose `meta.json` carries a `mission_id` (NFR-003)
**Constraints**: shipped migration modules byte-identical (NFR-001, DIRECTIVE_044); ruff, ruff format and mypy strict clean; complexity ≤ 15; diff coverage ≥ 90 %; no new suppressions
**Scale/Scope**: about 9 source modules touched or added (1 resolver, 1 supersession table, 4 successor modules, 1 runner, 1 audit classifier plus models, 1 feature_meta helper), with an order-manifest edit, an ADR amendment and a changelog entry; 644 `kitty-specs/` children in this repository as the false-positive corpus

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Status | How the plan satisfies it |
|---|---|---|
| Single canonical authority | PASS | One residue rule in `mission_resolver`. Successors call it, and so does the runner's notice collapse (by text identity). No second predicate. |
| DIRECTIVE_044 (never edit a shipped migration) | PASS | Supersession table only; `git diff --diff-filter=MDR` on existing `m_*.py` stays empty (NFR-001). |
| ATDD-first / red-first (standing order 4, ADR 2026-07-17-1) | PASS | `p0_repro(issue=6669)` is already in PR #6672. It is extended to 5 shapes and loses its marker in the fix WP. |
| Architectural gate discipline | PASS | The walker gate is reclassified, not loosened. Any new write-site allowlist entry carries a rationale, and the goal is zero new entries by reusing the frozen helpers. |
| Campsite cleaning | PASS (scoped) | Only domain-matched debt: the stale `RESIDUE_DIRECTORY` remedy text. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | PASS | Targeted gate files only; no bare `tests/architectural/` sweep. |
| Mission tracer files (standing order 3) | PASS | Seeded under `traces/` at planning. |
| Terminology canon (Mission, not feature) | PASS | New identifiers and prose say Mission. Shipped `feature_*` names are untouched (frozen). |
| Agent operating discipline (operator merges) | PASS | The PR is handed off; the operator merges. |

Post-design re-check: PASS. Phase 1 introduced no new violation.

## Project Structure

### Documentation (this mission)

```
kitty-specs/residue-safe-migration-sweep-01M5SS0F/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── checklists/requirements.md
├── decisions/           # Decision Moments
├── traces/              # mission tracer files
└── tasks.md             # /spec-kitty.tasks (not created here)
```

No `contracts/` directory: the Mission adds no API, CLI flag or payload schema. `meta.json` records `contracts: none` with a rationale. The doctor finding is an additive code in an open set, and the `backfill-runtime-state --json` `residue` key from #6662 already exists.

### Source Code (repository root)

```
src/specify_cli/context/mission_resolver.py          # git-aware is_kitty_specs_residue, RESIDUE_NOTICE, git-aware-mode probe
src/specify_cli/upgrade/feature_meta.py               # baseline_slug_fields() extracted; builder uses it and the rule
src/specify_cli/migration/normalize_mission_lifecycle.py   # uses RESIDUE_NOTICE; passes tracked=
src/specify_cli/migration/runtime_state_cutover.py    # rule call unchanged in shape; tracked= when walking
src/specify_cli/migration/backfill_runtime_state.py   # _mission_dirs filtered (FR-003)
src/specify_cli/migration/runner.py                   # _move_derived_files filtered (FR-003)
src/specify_cli/upgrade/supersession.py               # 4 new entries
src/specify_cli/upgrade/migrations/m_0_9_0_residue_safe_frontmatter_only_lanes.py   # new (subclass)
src/specify_cli/upgrade/migrations/m_0_9_1_residue_safe_complete_migration.py       # new (subclass)
src/specify_cli/upgrade/migrations/m_2_0_6_residue_safe_consistency_sweep.py        # new (re-walk over frozen helpers)
src/specify_cli/upgrade/migrations/m_3_1_1_residue_safe_normalize_status_json.py    # new (re-walk over frozen helpers)
src/specify_cli/upgrade/migrations/_residue_successor.py   # shared: predecessor-settled view, residue filter, notice
src/specify_cli/upgrade/migrations/order_manifest.txt # 4 tie entries
src/specify_cli/upgrade/runner.py                     # collapse repeated residue notices per folder per run
src/specify_cli/audit/classifiers/fabricated_identity.py   # new
src/specify_cli/audit/models.py, audit/engine.py      # FABRICATED_IDENTITY_SUSPECTED; call from _scan_missions; RESIDUE_DIRECTORY remedy
docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md   # Amendment 2026-10-25b
docs/changelog/CHANGELOG.md

tests/integration/migration/test_upgrade_residue_with_mission_files_6669.py   # marker removed, 5 shapes
tests/specify_cli/upgrade/test_residue_safe_successors_6669.py                # new
tests/context/test_is_kitty_specs_residue_git_aware.py                        # new
tests/audit/test_fabricated_identity_finding.py                               # new
tests/architectural/test_migration_walkers_use_mission_predicate.py           # reclassified
```

**Structure Decision**: single project. New successor modules sit beside the shipped migrations they supersede. Shared successor plumbing lives in a private `_residue_successor.py`, so four modules don't each carry their own copy of the settled-view and notice logic.

## Complexity Tracking

No charter violations need justifying.

## Implementation Concern Map

> Implementation concerns are not work packages. `/spec-kitty.tasks` translates them.

### IC-01 — Git-aware residue rule and shared notice

- **Purpose**: make the one residue decision git-aware (FR-001, FR-002) and give every step one notice text with a working remedy (FR-008 text half).
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-008, NFR-003
- **Affected surfaces**: `context/mission_resolver.py`, `audit/engine.py` (`RESIDUE_DIRECTORY` remedy), `migration/normalize_mission_lifecycle.py` (notice constant)
- **Sequencing/depends-on**: none
- **Risks**: widening residue past the rulings, for example by losing the tracked-`spec.md`-deleted case. A non-git or unusable-git crash. The git-call budget.

### IC-02 — Residue-aware successors for the four shipped migrations

- **Purpose**: supersede 0.9.0, 0.9.1, 2.0.6 and 3.1.1 with successors that skip residue, keep every repair for Missions, run in their predecessor's slot, and do nothing where the predecessor already ran (FR-004 to FR-007).
- **Relevant requirements**: FR-004, FR-005, FR-006, FR-007, NFR-001, C-002, C-006
- **Affected surfaces**: `upgrade/supersession.py`, four new `m_*_residue_safe_*.py`, `_residue_successor.py`, `order_manifest.txt`, ADR 2026-10-17-1
- **Sequencing/depends-on**: IC-01
- **Risks**:
  - the 0.9.1 module is 575 lines with worktree cleanup, and the subclass override must cover every walker in it (`_find_features_with_lanes`, `_normalize_all_frontmatter`, `detect`);
  - 3.1.1 writes inline in `apply()`, so its successor needs its own write, which may hit a write-site gate and needs a rationale;
  - dry-run/live parity on first adoption;
  - write-site gates keyed on module paths.

### IC-03 — Notice collapse in the upgrade runner

- **Purpose**: name each residue folder at most once per upgrade run, however many steps skip it (FR-008, collapse half).
- **Relevant requirements**: FR-008
- **Affected surfaces**: `upgrade/runner.py` (warning collection), possibly `upgrade/outcome.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: dropping a different warning that happens to share text, so collapse only exact `RESIDUE_NOTICE` lines keyed by folder. Interaction with the worktree loop's per-worktree prefixes.

### IC-04 — Walker gate re-audit and the remaining shared walkers

- **Purpose**: route the remaining shared walkers through the rule and reclassify the gate inventory honestly under the new definition (FR-003, FR-013).
- **Relevant requirements**: FR-003, FR-013
- **Affected surfaces**: `migration/backfill_runtime_state.py`, `migration/runner.py` (`_move_derived_files`), `tests/architectural/test_migration_walkers_use_mission_predicate.py`
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: changing `backfill-runtime-state` / `backfill-wp-status` behaviour for real Missions.

### IC-05 — Fabricated-identity doctor finding

- **Purpose**: report already-committed fabricated identities without changing anything (FR-010 to FR-012).
- **Relevant requirements**: FR-010, FR-011, FR-012, NFR-002
- **Affected surfaces**: `upgrade/feature_meta.py` (`baseline_slug_fields`), `audit/classifiers/fabricated_identity.py`, `audit/models.py`, `audit/engine.py`
- **Sequencing/depends-on**: none (independent of IC-01..04)
- **Risks**: false positives on the 644-folder corpus, signal 2 drifting from the builder, and an import cycle `audit` → `upgrade.feature_meta`.

### IC-06 — Red-first guard, extended reproduction, docs

- **Purpose**: turn the #6669 `p0_repro` into a per-PR guard over all 5 leftover shapes, and record the decisions (FR-009, C-002).
- **Relevant requirements**: FR-009, SC-001, C-002
- **Affected surfaces**: `tests/integration/migration/test_upgrade_residue_with_mission_files_6669.py`, `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`, `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01, IC-02, IC-03
- **Risks**: the reproduction's runtime (~2 min per variant in-process), so keep it to one upgrade per shape and consider a shared template project.
