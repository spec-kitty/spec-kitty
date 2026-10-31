# Mission Specification: Centralized-runtime detection is a project property

**Mission Branch**: `issue-6551-centralized-runtime-detection-is-project-local`
**Created**: 2026-10-30
**Status**: Ready for planning
**Input**: GitHub issue spec-kitty/spec-kitty#6551 — "upgrade: on a machine with no
`~/.kittify` yet, re-runs legacy mission migrations and commits 22 frozen overrides"

## Problem

`spec-kitty upgrade --project` behaves differently for two people running the same
build against the same commit. Whether `0.6.7_ensure_missions` and
`0.12.0_documentation_mission` copy the packaged missions into the project depends
on whether the *operator's home* has `~/.kittify/cache/version.lock`, not on the
project.

`uses_centralized_runtime()` (`src/specify_cli/upgrade/compat.py`) gates its
"this project uses the 2.x centralized runtime" answer on
`global_runtime_configured()` before it ever looks at the project's own
`metadata.yaml`. `upgrade` deliberately does not bootstrap the global runtime
before running migrations (#3900), so on a machine where `upgrade` is the first
spec-kitty command, both migrations answer `detect() is True` for a project whose
`metadata.yaml` says `4.0.0rc8`. They copy the packaged missions in,
`2.0.6_consistency_sweep` reclassifies the copies as overrides, and the upgrade
auto-commits 23 files / 2,587 lines with exit 0. From then on the project resolves
`mission.yaml` from those frozen copies instead of from the global runtime.

The ledger does not save us: a `skipped` record does not settle a migration, and
re-evaluating `detect()` is only idempotent if `detect()` is a function of project
state. Here it is not.

## User Scenarios & Testing

### User Story 1 - Same commit, same result on a fresh machine (Priority: P1)

A maintainer clones a Spec Kitty project onto a second machine (or a CI runner)
whose `~/.kittify` has never been bootstrapped, and runs `spec-kitty upgrade
--project --yes` as the first spec-kitty command there. The upgrade makes no
tracked change: no `.kittify/missions/`, no `.kittify/overrides/missions/`, no
auto-commit beyond ledger bookkeeping.

**Why this priority**: This is the reported defect, and it silently freezes all
three built-in missions at the build that ran the upgrade. It is the only story
that has to land for the issue to be closed.

**Independent Test**: Build a git-backed project at `4.0.0rc8` whose ledger
records both legacy mission migrations as `skipped` (the converged state the
issue measured under user A), point `SPEC_KITTY_HOME` at an empty directory, run
the real `upgrade --project` command, then assert `git status --porcelain` is
empty and neither `.kittify/missions/` nor `.kittify/overrides/` exists.

**Acceptance Scenarios**:

1. **Given** a project whose `metadata.yaml` version is `>= 2.0.0` and a home with
   no `cache/version.lock`, **When** `uses_centralized_runtime()` is asked,
   **Then** it answers `True` without consulting the home.
2. **Given** the same project and the same home, **When**
   `0.6.7_ensure_missions.detect()` and `0.12.0_documentation_mission.detect()`
   run, **Then** both answer `False`.
3. **Given** the same project and home, **When** `upgrade --project --yes` runs,
   **Then** the run exits 0 and leaves the tracked tree unchanged.

### User Story 2 - The pinned legacy paths still repair (Priority: P2)

A genuinely pre-2.x project, or a metadata-less worktree, still receives the
legacy repair migrations.

**Why this priority**: The fix must not trade a false positive for a false
negative. Existing tests pin these two shapes and exist for a reason.

**Independent Test**: Keep the four existing `tests/upgrade/test_compat.py` cases
and the two migration-level pins green, and add the missing pre-2.0 metadata case.

**Acceptance Scenarios**:

1. **Given** a project whose `metadata.yaml` version is `1.2.0`, **When**
   `uses_centralized_runtime()` is asked under a bootstrapped home, **Then** it
   answers `False` and `0.6.7_ensure_missions.detect()` answers `True`.
2. **Given** a repo that has `.kittify/` but no `metadata.yaml`, **When** asked
   under a bootstrapped home, **Then** the answer stays `False`.
3. **Given** a metadata-less worktree path with no `.kittify/`, **When** asked
   under a bootstrapped home, **Then** the answer stays `True`.

### Edge Cases

- **Unreadable / malformed `metadata.yaml`**: `ProjectMetadata.load()` returns
  `None` or a non-version string; the answer falls back to the metadata-less
  logic rather than raising.
- **Unparseable version stamp** (for example `unknown`): treated as not-2.x, as
  today; a project we cannot date is not assumed modern.
- **`SPEC_KITTY_HOME` unset and unresolvable**: `get_kittify_home()` can raise
  `RuntimeError`; `global_runtime_configured()` already turns that into `False`
  and that behaviour is preserved for the metadata-less path.
- **Already-affected projects** with the 22 frozen overrides: not repaired here.
  That is the repair-path half of the issue and belongs with #6548.

## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Project metadata decides first | As an operator, I want centralized-runtime detection to read the project's own `metadata.yaml` before the home, so that the same commit gives the same answer on any machine. | High | Open | [build] | no |
| FR-002 | Legacy mission migrations skip 2.x+ projects | As an operator on a fresh machine, I want `0.6.7_ensure_missions` and `0.12.0_documentation_mission` to answer `detect() is False` for a 2.x+ project, so that no mission copies land in it. | High | Open | [build] | no |
| FR-003 | Converged upgrade is a no-op under an empty home | As a CI runner, I want `upgrade --project` on a converged project with no `~/.kittify` to make no tracked change, so that an upgrade cannot freeze the shipped missions. | High | Open | [build] | no |
| FR-004 | Pre-2.x projects still repair | As an operator upgrading a 1.x project, I want the legacy mission migrations to still run, so that the fix does not lose the repair they exist for. | High | Open | [ratchet] | no — paired with FR-001's 2.x case on the same fixture shape |
| FR-005 | Metadata-less shapes unchanged | As a maintainer, I want the metadata-less repo and metadata-less worktree answers to stay exactly as pinned today, so that the blast radius is one predicate. | Medium | Open | [ratchet] | no — the existing four `test_compat.py` cases are the positive control |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No-op upgrade leaves the tree clean | A converged project's `upgrade --project --yes` under an empty `SPEC_KITTY_HOME` leaves `git status --porcelain` empty (zero dirty paths) and creates neither `.kittify/missions/` nor `.kittify/overrides/`. | Reliability | High | Open |
| NFR-002 | Detection is side-effect free | `uses_centralized_runtime()` performs no writes: it must not bootstrap, create `~/.kittify`, or touch the project (asserted by comparing the home and project trees before/after). | Reliability | High | Open |
| NFR-003 | Regression test stays in the fast tier budget | The new production-path regression test runs in under 60 seconds on CI hardware and carries `pytest.mark.integration` + `pytest.mark.git_repo`, matching its sibling upgrade harness. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Do not change ledger selection | The `skipped`-does-not-settle rule in `registry.get_applicable` and ADR `2026-10-17-1` §3 stay as they are; this mission fixes `detect()`, not selection. | Technical | High | Open |
| C-002 | One predicate, one owner | The change stays inside `src/specify_cli/upgrade/compat.py` plus tests and docs; no new second source of truth for "is this a 2.x runtime project". | Technical | High | Open |
| C-003 | Repair of affected projects is out of scope | Repointing or removing historical overrides is #6548's problem and is recorded in the PR's `## Deferred`. | Business | Medium | Open |

### Key Entities

- **Project metadata stamp**: `.kittify/metadata.yaml` → `spec_kitty.version`. The
  project's own statement of which runtime model it was created or last migrated
  under. The authority this mission promotes to first place.
- **Global runtime marker**: `~/.kittify/cache/version.lock`. Evidence that *this
  machine's* home has been bootstrapped. Not evidence about the project.
- **Migration ledger record**: `.kittify/migration-ledger.jsonl` line with
  `result` in `success|skipped|failed`. `skipped` is re-evaluated every run by
  design, which is why `detect()` must be deterministic.

## Success Criteria

- **SC-001**: A 4.0.0rc8 project with an empty `SPEC_KITTY_HOME` produces `detect() is False` for both legacy mission migrations and `git status --porcelain` empty after `upgrade --project --yes` — [build] · no-op passable: no
- **SC-002**: `tests/upgrade/test_compat.py` gains the missing pre-2.0.0-without-home case and all of its cases stay green — [ratchet] · no-op passable: no
- **SC-003**: The full `tests/upgrade/` suite is green on the PR head with no new skip, xfail or deselection — [ratchet] · no-op passable: no
- **SC-004**: Zero user-visible behaviour change on a machine whose home *is* bootstrapped — [ratchet] · no-op passable: no
