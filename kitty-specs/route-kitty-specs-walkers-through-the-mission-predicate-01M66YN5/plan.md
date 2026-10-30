# Implementation Plan: Route the remaining `kitty-specs/` walkers through the Mission predicate

**Branch**: `issue-6758-kitty-specs-walkers-mission-predicate` | **Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/route-kitty-specs-walkers-through-the-mission-predicate-01M66YN5/spec.md`

## Summary

Six read-surface walkers enumerate every directory child of `kitty-specs/` and decide for
themselves whether the child is a Mission: `doctor topology`, the `doctor coordination`
whole-repo scan, the `doctor review-cycle-reconcile` scan, `materialize`, the
charter-activate in-flight warning and the release-changelog block. Each gets exactly one
`is_selectable_mission_dir` call per child (with one `TrackedMissionPaths` memo per walk),
so the read-side Mission rule has one authority; `doctor topology` stops rendering residue
rows; and an architectural pin keeps all six on the predicate.

## Technical Context

**Language/Version**: Python 3.11+ (project floor; `uv`-managed)
**Primary Dependencies**: `typer`/`rich` for the CLI surfaces, `kernel.git` for the one batch
`git ls-files`, `specify_cli.context.mission_resolver` for the predicate
**Storage**: filesystem only (`kitty-specs/<child>/meta.json`, `tasks/`, `status.events.jsonl`)
**Testing**: pytest; red-first per changed walker, then blast-radius modules
(`tests/specify_cli/cli/commands`, `tests/cli`, `tests/release`, `tests/charter`,
`tests/architectural/test_mission_resolver_walker_gate.py`). No full heavy suite
(`NO_FULL_HEAVY_SUITES_IN_MISSION`).
**Target Platform**: CLI on Linux/macOS/Windows
**Project Type**: single project (`src/specify_cli`, layer `specify_cli` above `context`)
**Performance Goals**: at most one `git ls-files` per walk; zero when every child carries a
`mission_id` (NFR-001)
**Constraints**: audit engine untouched (C-001); predicate semantics untouched (C-002);
each walker keeps its enumeration posture (C-003)
**Scale/Scope**: 6 source files, 7 test files (6 behavioural + 1 architectural), 1 changelog
entry and 1 docs touch

## Charter Check

*GATE: must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Charter rule | Plan conformance |
| --- | --- |
| Single canonical authority | The predicate stays the one authority; the change adds callers, never a second rule (FR-007, C-002). |
| Locality of change (`DIRECTIVE_024`) / smallest viable diff | One predicate call per walker, no walk rewrite, no shared iterator swap (C-003, D2 in `research.md`). |
| ATDD-first (`DIRECTIVE_034`) | Every walker gets its residue fixture test first and the test must fail before the walker changes (FR-009, SC-002/SC-004). |
| Architectural gate discipline (`DIRECTIVE_041`, architectural-gate-non-vacuity) | The pin is an AST ledger with a planted-walker case proving the checker can fail (FR-008, SC-003). |
| Terminology canon | "Mission" only; "read-side residue" named explicitly per the residue disambiguation, never bare "residue". |
| Docs & changelog duty | `[Unreleased]` changelog entry plus the `doctor` reference sentence that residue is reported by `doctor identity` (user-facing change: `doctor topology` output). |
| Pre-existing Failure Reporting Rule | Any unattributable CI red is reproduced on pristine `origin/main` and cited in the PR's Deferred section. |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | Blast radius is the six modules' own test files plus the four subsystem directories named above. |

No violations, so Complexity Tracking stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/route-kitty-specs-walkers-through-the-mission-predicate-01M66YN5/
├── plan.md              # this file
├── research.md          # discovery + Phase 0 decisions
├── data-model.md        # Phase 1: the walker/predicate decision table
├── tasks.md             # Phase 2 output (/spec-kitty.tasks)
└── spec.md
```

No `contracts/` and no `quickstart.md`: this Mission changes no external interface
(no CLI flag, no JSON schema field, no API). `meta.json` records
`"contracts": "none"` with its rationale instead.

### Source Code (repository root)

```
src/specify_cli/
├── cli/commands/
│   ├── _identity_audit.py                 # _collect_topology_rows  -> shared walk + predicate
│   ├── _coordination_doctor.py            # _resolve_mission_dirs   -> predicate filter
│   ├── _review_cycle_reconcile_doctor.py  # _mission_dirs_for       -> predicate filter
│   └── materialize.py                     # _mission_dirs_to_process -> predicate filter
├── charter_activate.py                    # _collect_inflight_missions -> predicate filter
└── release/changelog.py                   # build_changelog_block   -> predicate filter

tests/
├── _support/mission_residue_fixture.py    # the shared git-aware fixture (Mission + residue)
├── specify_cli/cli/commands/test_identity_audit.py
├── specify_cli/cli/commands/test_coordination_doctor.py
├── specify_cli/cli/commands/test_review_cycle_reconcile_doctor.py
├── specify_cli/cli/commands/test_materialize.py
├── cli/test_charter_activate_warning.py
├── release/test_release_prep.py
└── architectural/test_mission_resolver_walker_gate.py
```

**Structure Decision**: keep every edit inside the module that owns the walk. The
predicate and its memo already live in `specify_cli/context/mission_resolver.py` (a lower
layer that `specify_cli` may import), so no new module and no layer rule changes.

## Per-walker change and proof

| Walker | Change | Test (red first) |
| --- | --- | --- |
| `_identity_audit._collect_topology_rows` | whole-repo branch walks `mission_resolver.iter_kitty_specs_children(repo_root)` (the sanctioned fail-soft walk its `doctor identity` sibling already uses) and keeps only `is_selectable_mission_dir` children; the `--mission` branch is unchanged | `test_collect_topology_rows_skips_residue` (human + `--json`), `test_collect_topology_rows_all` stays as the positive control |
| `_coordination_doctor._resolve_mission_dirs` | filter the existing comprehension; `safe_is_dir` runs first so `#3194` still raises | `test_resolve_mission_dirs_skips_residue` |
| `_review_cycle_reconcile_doctor._mission_dirs_for` | filter the existing comprehension | `test_mission_dirs_for_skips_residue` |
| `materialize._mission_dirs_to_process` | filter the existing comprehension (dot-directory skip kept) | `test_mission_dirs_to_process_skips_residue` |
| `charter_activate._collect_inflight_missions` | filter the existing loop; `repo_root` is the parent of `kitty-specs/` | `test_collect_inflight_missions_skips_residue` |
| `release.changelog.build_changelog_block` | filter `mission_dirs` | `test_changelog_excludes_residue_folder` |

Each new test uses one shared fixture: a git repository with a **Mission** (`meta.json`
carrying `mission_id`) and a **residue** child (`tasks/WP01-*.md`, no `meta.json`,
untracked). Both children sit on the same fixture, so the positive control and the absence
assertion cannot drift (acceptance-criteria-non-vacuity).

## Implementation Concern Map

### IC-01 — the six walker call sites

- **Purpose**: put every one of the six read-side walks behind the one read-side predicate.
- **Relevant requirements**: FR-001..FR-007, NFR-001, C-002, C-003, C-004
- **Affected surfaces**: `src/specify_cli/cli/commands/_identity_audit.py`,
  `_coordination_doctor.py`, `_review_cycle_reconcile_doctor.py`, `materialize.py`,
  `src/specify_cli/charter_activate.py`, `src/specify_cli/release/changelog.py`
- **Sequencing/depends-on**: none (the predicate already exists on `main`)
- **Risks**: silently weakening an existing posture (the `#3194` raise, the dot-directory
  skip, the best-effort scan) or multiplying git probes; both are pinned by existing tests
  and NFR-001.

### IC-02 — the shared residue fixture and the eight behavioural assertions

- **Purpose**: give each changed walker a red-first proof with a residue child and a
  Mission child on one git-aware fixture.
- **Relevant requirements**: FR-009, SC-002, SC-004
- **Affected surfaces**: `tests/_support/mission_residue_fixture.py` and the six owning
  test files
- **Sequencing/depends-on**: IC-01 (the tests are written first, then made green)
- **Risks**: a fixture that is not git-aware cannot exercise the git-tracked-id-less case;
  the helper must commit the Mission's `meta.json` so only the residue child is untracked.

### IC-03 — the architectural pin and the allowlist shrink

- **Purpose**: make the routing structural, not just behavioural: a shrink-only ledger of
  the six `(module, function)` pairs, each verified by AST to call
  `is_selectable_mission_dir`, with a planted-walker case proving the checker can fail.
- **Relevant requirements**: FR-008, SC-003
- **Affected surfaces**: `tests/architectural/test_mission_resolver_walker_gate.py`
- **Sequencing/depends-on**: IC-01 (`_identity_audit.py` leaves the raw-walk allowlist
  once it uses the shared walker)
- **Risks**: a pin keyed on the wrong function name would pass vacuously; the planted
  walker case plus the function-name lookup (asserted to resolve) prevent that.

## Red-first and blast radius

1. Write the shared fixture and the six behavioural tests with the walkers unchanged; run
   them and record every failure (they must all fail).
2. Change the six walkers; rerun to green.
3. Add the architectural pin; run it against the changed tree, then against a temporarily
   planted walker without the predicate (must fail).
4. Run the blast radius: the seven test files above, plus
   `tests/specify_cli/cli/commands/`, `tests/cli/`, `tests/release/`, `tests/charter/`,
   and `make test-fast`.
5. `ruff check .` and `ruff format --check .` on the touched files.
