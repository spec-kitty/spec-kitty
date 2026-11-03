# Implementation Plan: A stray `.git` name is not an identity refusal

**Branch**: `issue-7084-stray-git-anchor-identity` | **Date**: 2026-11-03 | **Spec**: `kitty-specs/stray-git-anchor-identity-01M6G9QV/spec.md`
**Input**: Mission specification from `kitty-specs/stray-git-anchor-identity-01M6G9QV/spec.md`
**Issue**: spec-kitty/spec-kitty#7084

## Summary

`read_tracked_meta` decides "git holds a copy I cannot give back" by scanning ancestor **names**: any
ancestor carrying a `.git` entry, of any shape, is an anchor. So a `.git` directory that is not a
repository (this fleet host's `/tmp/.git` holds only `hooks/` and `spec-kitty-locks/`) makes
`backfill_mission` refuse with `TRACKED_META_UNAVAILABLE` for every mission below it, and the
refusal's own remedy (`git checkout -- meta.json`) cannot run. The fix narrows the predicate from
"an ancestor carries a `.git` name" to "an ancestor's `.git` entry can be a repository home": a
`.git` *file* (worktree/submodule pointer) and a `.git` *directory carrying `HEAD`* stay anchors and
keep refusing; a `.git` directory without `HEAD` is not a repository — git holds nothing there — so
the identity is minted. One predicate, one helper, no new walk.

## Technical Context

**Language/Version**: Python 3.11+ (`pyproject.toml` `requires-python = ">=3.11"`), stdlib `pathlib` only
**Primary Dependencies**: none added; uses the existing `kernel.git.run_git` answers already obtained by `_meta_checkout_prefix`
**Storage**: `kitty-specs/<slug>/meta.json` (JSON, written through `mission_metadata.write_meta`)
**Testing**: pytest, `@pytest.mark.unit`/`fast`/`git_repo`; targeted files only (`NO_FULL_HEAVY_SUITES_IN_MISSION`)
**Target Platform**: Linux/macOS/Windows developer workstations and CI containers (all filesystem shapes are handled through `pathlib`)
**Project Type**: single Python package (`src/specify_cli/`)
**Performance Goals**: no added filesystem walk; at most one extra `stat` per ancestor the existing loop already visits
**Constraints**: no new git invocation; fail-closed on any unreadable ancestor; the #6673 refusal contract unchanged where a repository may hold the identity
**Scale/Scope**: one private predicate and one private helper in one module, plus tests and a changelog fragment

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority | The anchor rule keeps one owner (`specify_cli/mission_metadata.py`); no second copy in `backfill_identity.py`. |
| ATDD-First / `DIRECTIVE_034` (red-first bug fixing) | The regression test is written and observed red through `backfill_mission` and `read_tracked_meta` before the predicate changes; the issue's own node is the outer ring. |
| `change-apply-smallest-viable-diff` / `DIRECTIVE_024` locality | One predicate body, one helper, no signature change, no error-code change. |
| Pre-existing Failure Reporting Rule | #7084 is the reported failure; the `/tmp/.git` pollution source and the name-only root resolver are recorded as Deferred rather than folded in. |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | Only `tests/lanes/test_refinalize_mission_branch.py`, `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py`, `tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py`, `tests/integration/migration/test_upgrade_tracked_meta_identity_6673.py` plus ruff/mypy on the changed module. |
| Testing Requirements (positive control on absence assertions) | Every new "mints" assertion is paired on the same fixture shape with a "still refuses" assertion (anchor shapes), per `acceptance-criteria-non-vacuity`. |
| Architectural gate discipline | No hand-rolled ancestor walk is added: the existing loop keeps its shape, which is also what keeps this composable with in-flight PR #7082. |

No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/stray-git-anchor-identity-01M6G9QV/
├── plan.md              # This file
├── research.md          # Discovery + Phase 0 findings (repro, cause, decisions)
├── reasons-canvas.md    # SPDD canvas (charter-selected)
├── spec.md              # Mission specification
├── meta.json            # Mission metadata (declares contracts: none)
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

`data-model.md`, `quickstart.md` and `contracts/` are omitted deliberately: the mission introduces
no interface, no persisted schema and no entity beyond the two the spec and canvas name. `meta.json`
records `"contracts": "none"` with a rationale so a strict `accept` waives the directory.

### Source Code (repository root)

```
src/specify_cli/mission_metadata.py        # the anchor predicate (`_has_no_git_anchor`) + one helper
tests/specify_cli/upgrade/test_read_tracked_meta_6673.py       # probe-level regression + retained refusals
tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py  # entry-point regression
tests/lanes/test_refinalize_mission_branch.py                  # the issue's node, unedited
docs/changelog/unreleased/<pr>.fixed.md                        # per-PR fragment
docs/guides/how-to/installation/upgrade-project.md             # one sentence: what is and is not refused
```

**Structure Decision**: single-project layout, because the change is one private predicate inside
the existing module that already owns "what does git hold for this `meta.json`".

## Implementation Concern Map

### IC-01 — The anchor predicate asks a repository question

- **Purpose**: Stop a non-repository `.git` name from turning into a tracked-identity refusal, while
  keeping every shape that could hide a real copy fail-closed.
- **Relevant requirements**: FR-001, FR-002, FR-004, NFR-001, NFR-002, C-001, C-002, C-003
- **Affected surfaces**: `src/specify_cli/mission_metadata.py` — `_has_no_git_anchor` and a new
  private `_is_repository_home`; `read_tracked_meta`'s and `_meta_checkout_prefix`'s docstrings.
- **Sequencing/depends-on**: none
- **Risks**: the `HEAD` test must not accidentally accept a `.git` *file* as a directory (it is
  checked first, and a file pointer is an anchor by itself); a `.git` directory carrying `HEAD` but
  no `objects/` stays a refusal by design (broken repository, nothing recoverable either way).

### IC-02 — Red-first coverage at both layers plus the issue's own node

- **Purpose**: Prove the widened branch through the production entry points, and prove the
  unchanged refusals with positive controls on the same fixtures.
- **Relevant requirements**: FR-002, FR-003, SC-001, SC-002, SC-003
- **Affected surfaces**: `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py` (probe: stray
  `.git` directory above a temp root; `.git` directory carrying `HEAD` still refuses),
  `tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py` (entry point:
  `backfill_mission` reports `wrote` and writes the id), `tests/lanes/test_refinalize_mission_branch.py`
  (unchanged; it goes green).
- **Sequencing/depends-on**: IC-01 for the green state, but the tests are written and observed red
  first.
- **Risks**: a fixture that creates a *real* repository above `tmp_path` would pass for the wrong
  reason; the stray anchor is therefore a bare directory named `.git`, exactly the shape the host
  demonstrates.

### IC-03 — Operator-facing changelog fragment and the upgrade guide sentence

- **Purpose**: Tell operators that a folder git does not track gets its identity minted, and that the
  refusal now only appears where git may really hold a copy.
- **Relevant requirements**: FR-001, FR-004 (stated where it is implemented), SC-002
- **Affected surfaces**: `docs/changelog/unreleased/<pr>.fixed.md`,
  `docs/guides/how-to/installation/upgrade-project.md`
- **Sequencing/depends-on**: IC-01 (wording must match delivered behaviour); fragment named after the
  PR number once the PR exists.
- **Risks**: changelog style gate (`check_changelog_style`) rejects `[Unreleased]`-shaped entries;
  the fragment is content-only, US spelling.
