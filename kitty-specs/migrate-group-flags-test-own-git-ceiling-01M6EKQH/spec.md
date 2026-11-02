# Mission Specification: Make the migrate group-flag acceptance test own its git-discovery ceiling

**Mission Branch**: `kitty/mission-migrate-group-flags-test-own-git-ceiling-01M6EKQH`
**Created**: 2026-11-02
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#6957 — "tests/cli/test_migrate_group_flags_4964.py: the
positive-control test is red on main — the placement port resolves its primary home to /tmp/kitty-specs"

## Context and grounding (why this mission exists)

Issue #6957 reports that
`tests/cli/test_migrate_group_flags_4964.py::test_non_dry_run_positive_control_writes_on_same_fixture`
fails on a pristine `origin/main` checkout with a placement fail-close:

```text
_flip_phase refuses to write status_phase for '042-demo': the placement port resolved its
PRIMARY home to /tmp/kitty-specs/042-demo, which does not match the write target
<tmp>/kitty-specs/042-demo (fail-closed, FR-001).
```

Grounding on current `origin/main` (`9aed3a8012`) established two facts that define the boundary:

1. **The symptom is currently masked, not cured, in this module.** The file is green
   (`uv run --frozen pytest tests/cli/test_migrate_group_flags_4964.py -q` → 76 passed) only because
   `tests/conftest.py` installs a process-wide `GIT_CEILING_DIRECTORIES` from the run basetemp
   (`tests/_support/git_ceiling.py`, landed for #7022/#5356 on 2026-11-01, after this issue was filed).
   That ceiling bounds `specify_cli.core.paths.resolve_canonical_root`, which
   `specify_cli.migration.runtime_state_cutover._resolve_primary_home_or_degrade` calls, so the
   ancestor walk stops at the run root instead of reaching an ambient `.git` above it.
2. **The module's own isolation is still incomplete, and the exact reported red still reproduces.**
   With the ambient ceiling removed — a nested runner, a child process given a scratch environment, or
   any invocation shape where that process-wide variable is not installed — the module reproduces the
   reported failure verbatim on a host whose platform temp root sits inside a repository (this host has
   a stray `/tmp/.git`). The module poisons `locate_project_root` but never pins the *root walk* the
   cutover uses.

The repository already states the correct ownership for this case. `tests/_support/git_ceiling.py`
says a test that does not inherit the harness ceiling "sets the variable itself", and the closest
sibling module does exactly that:
`tests/specify_cli/migration/test_runtime_state_cutover_placement.py:41`
(`monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))`).

**Boundary.** This mission changes tests only. It does not change `specify_cli.core.paths`,
`runtime_state_cutover`, the migration product behaviour, or the harness-wide ceiling installed by
#7022 — those are correct and stay as they are. The defect is the module's undeclared dependency on a
process-wide environment variable for its own hermeticity.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The module pins its own discovery ceiling (Priority: P1)

As a maintainer running `tests/cli/test_migrate_group_flags_4964.py` on any host — including one whose
platform temp root sits inside a git repository — I want the module's own autouse isolation to stop
git discovery at the test root, so the positive-control test cannot go red because of an ambient
repository above `tmp_path`.

**Why this priority**: It is the defect in #6957, and the only change that removes it.

**Independent Test**: Clear `GIT_CEILING_DIRECTORIES` (removing the harness's process-wide ceiling),
run the module's positive control on a host whose temp root is inside a repository, and observe it
stays green; observe the module's fixture lists the test root as a ceiling.

**Acceptance Scenarios**:

1. **Given** a host whose platform temp root is inside a git repository, **When** the module's autouse
   isolation runs, **Then** `specify_cli.core.paths.git_ceiling_dirs()` contains the test's
   `tmp_path`, so `resolve_canonical_root` cannot climb above it.
2. **Given** `GIT_CEILING_DIRECTORIES` is cleared (no harness ceiling), **When** the non-dry-run
   positive control runs, **Then** the cutover flips `status_phase` on the fixture and the command
   exits 0 — no `/tmp/kitty-specs/<slug>` mismatch.

---

### User Story 2 - The isolation is proven non-vacuously (Priority: P2)

As a reviewer, I want the new guard to be able to fail, so I can trust that a green module means the
leak is closed rather than that the assertion cannot see anything.

**Why this priority**: Per `acceptance-criteria-non-vacuity` and DIRECTIVE_043, a gate that cannot
fail is not a gate.

**Independent Test**: Revert the fixture change; the new assertions must go red on a host whose temp
root is inside a repository, and the ambient test must skip (not pass) where the host shape is absent.

**Acceptance Scenarios**:

1. **Given** the fixture change is reverted, **When** the new ceiling assertion runs, **Then** it
   fails on every host (the test root is not listed as a ceiling).
2. **Given** the host's temp root is *not* inside a repository, **When** the ambient behavioural probe
   runs, **Then** it skips with a reason naming the missing host shape, so it never reports a vacuous
   green.

---

### Edge Cases

- **A repository inside `tmp_path`.** Tests that `git init` a project under `tmp_path` must keep
  working: a ceiling at `tmp_path` is *above* such a repository, so discovery still finds it.
- **An existing ceiling value.** The module appends to whatever the harness installed and never
  replaces it — a leading empty entry is meaningful to git, and `git_ceiling_dirs` ignores relative
  entries, so the helper dedupes against absolute entries only.
- **Duplicate entries.** The fixture must be re-entrant: the variable already containing `tmp_path`
  must not grow a duplicate meaningless entry.
- **No repository above the temp root (CI).** Behaviour is unchanged: the module is green with or
  without the local ceiling.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Module pins its own git ceiling | As a maintainer, I want the acceptance module's autouse isolation to list the test root in `GIT_CEILING_DIRECTORIES`, so discovery cannot climb above it. | High | Open | build | no |
| FR-002 | Pinning appends, never replaces | As a maintainer, I want the fixture to append the test root to any ceiling the harness already installed, so the module never widens discovery for the rest of the run. | High | Open | build | no |
| FR-003 | Positive control is ceiling-independent | As a maintainer, I want the non-dry-run positive control to pass with `GIT_CEILING_DIRECTORIES` cleared, so its greenness does not depend on a process-wide variable the module does not own. | High | Open | ratchet | no |
| FR-004 | Guard can fail | As a reviewer, I want non-vacuous evidence: the standing-invariant assertion fails without the fixture change, and the host-shape probe skips where the host shape is absent. | High | Open | ratchet | no |
| FR-005 | Nested repositories still resolve | As a maintainer, I want a repository created *inside* `tmp_path` to remain discoverable, so the ceiling does not break existing fixtures that `git init` their own project. | Medium | Open | ratchet | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No wall-clock regression | The added guard tests add under 15 s to the module's run time on this host (module currently ~33–145 s depending on tier and cache state). | Performance | Medium | Open |
| NFR-002 | No new ambient state | The module must not leave `GIT_CEILING_DIRECTORIES` modified after teardown; the fixture restores it via `monkeypatch`. | Reliability | High | Open |
| NFR-003 | Harness unchanged | The change adds zero lines to `tests/conftest.py`, `tests/_support/git_ceiling.py`, `src/` or `packs/`; the code diff is confined to the one acceptance module and its changelog fragment. Governance bookkeeping is exempt: the mission's own `kitty-specs/<mission>/` artifacts and the tool-written `kitty-ops/` op records the workflow commits are not code changes. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|--------|--------|
| C-001 | Tests only | Production modules (`specify_cli.core.paths`, `specify_cli.migration.runtime_state_cutover`, `mission_runtime`) must not change: the fail-close they implement is correct. | Technical | High | Open |
| C-002 | No gate weakening | Do not delete, skip, xfail or loosen any existing assertion in the module; the existing 76 tests keep their current semantics. | Technical | High | Open |
| C-003 | Canonical idiom | Use the repository's existing ceiling idiom (`monkeypatch.setenv` + `GIT_CEILING_DIRECTORIES`, per `tests/_support/git_ceiling.py` and the placement sibling test), not a bespoke mechanism. | Technical | High | Open |

### Key Entities

- **Git-discovery ceiling**: a directory listed in `GIT_CEILING_DIRECTORIES`. Git does not examine a
  listed ceiling directory unless the search starts there, and stops below it either way; entries after
  a leading empty entry are used unresolved. Both root walks in `specify_cli.core.paths` read the same
  variable through `git_ceiling_dirs`, which resolves every absolute entry, ignores relative ones, and
  examines a listed directory before stopping — so it also stops at a ceiling that holds no `.git`.
- **Placement PRIMARY home**: the path `resolve_artifact_surface(repo_root, slug, PRIMARY_METADATA)`
  returns for a Mission; `_flip_phase` refuses to write when it disagrees with the write target.
- **Harness ceiling**: the process-wide value `tests/conftest.py` installs from the run basetemp
  (#7022/#5356) — the ambient state this module must not rely on.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With `GIT_CEILING_DIRECTORIES` cleared on a host whose temp root is inside a repository, `pytest tests/cli/test_migrate_group_flags_4964.py -q` is green (76 pre-existing + the new guards). — build · no-op passable: no
- **SC-002**: The new standing-invariant assertion is red before the fixture change and green after it, on every host (no host-shape dependence). — build · no-op passable: no
- **SC-003**: No file outside `tests/cli/test_migrate_group_flags_4964.py` and one `docs/changelog/unreleased/` fragment carries a code change; mission artifacts under `kitty-specs/` and the tool-written `kitty-ops/` records are bookkeeping, not code. — ratchet · no-op passable: no
- **SC-004**: The pre-existing 76 tests in the module keep their assertions; `git diff` shows no deleted or weakened assertion. — ratchet · no-op passable: no
