# Mission Specification: a stray `.git` that is not a repository is not an anchor

**Mission Branch**: `issue-7093-stray-git-anchor-not-a-repository`
**Created**: 2026-11-03
**Status**: Draft
**Input**: GitHub issue #7093 — "tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py is red on pristine origin/main (missing kitty-specs meta.json)". Filed by the #6954 mission; reproduced here on `d18c4f1d58` with packs synced.

## Context

`tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py::test_apply_repairs_feature_state_and_legacy_prompt_refs`
is red: the frozen `2.0.6_consistency_sweep` reports `Wrote baseline meta.json` for a
Mission folder whose `meta.json` is missing, and no file appears. The reported
"missing `kitty-specs/.../meta.json`" is a symptom. Two facts pin the cause:

- The sweep is a byte-frozen shipped migration (DIRECTIVE_044; `supersession.SUPERSEDED_MIGRATIONS`
  maps `2.0.6_consistency_sweep` → `2.0.6_residue_safe_consistency_sweep`), so its bytes are its
  `content_hash` and it is not the fix site. Its behaviour in a clean environment is what the
  assertion states, and the assertion is right.
- `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py::test_nothing_tracked_is_not_a_refusal`
  is red on the same host, and that test names the contract directly: a folder **outside any work
  tree** must read as *nothing tracked*.

Both reds come from `specify_cli.mission_metadata._has_no_git_anchor`. It treats *any* `.git`
entry at or above the folder as a repository anchor. This host has `/tmp/.git`, a directory with
`hooks/` and no `HEAD` (the shape the literal-`.git/hooks` writer of #5756 leaves behind). git
positively answers `fatal: not a git repository` for every path below it, which is correct: there
is no repository there. But the anchor check says "a repository exists and git cannot read it",
so `read_tracked_meta` returns `TrackedMeta(None, unavailable=True)` — the *refusal* signal that
means "git tracks this path but cannot give it back". That is false. Nothing is tracked, so there
is no identity to protect.

Downstream, `build_baseline_feature_meta` returns `None` for a folder that is not residue, so:

- the frozen sweep appends `Wrote baseline meta.json` and writes nothing, and its `detect()` stays
  `True` forever (repair reported, never made);
- the residue-safe successor refuses the Mission with a `TRACKED_META_UNAVAILABLE` notice that
  tells the operator to run `git checkout -- <path>` for a path git does not track;
- `backfill_identity` and `normalize_mission_lifecycle` refuse a pre-identity Mission they could
  repair.

The defect is environment-sensitive only in *how often* it fires, not in *whether it is a
defect*: a project that is not a git checkout, sitting under any ancestor holding a non-repository
`.git` (a shared `/tmp`, a scratch volume, a leftover from the literal-`.git` writers), cannot
have its metadata repaired at all.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A non-repository `.git` above the project does not block repair (Priority: P1)

A maintainer runs `spec-kitty upgrade` on a spec project that is not inside a git checkout, under
a directory that happens to contain a `.git` directory git does not recognise as a repository.
The upgrade repairs the Mission's missing `meta.json` from the folder itself, exactly as it does
on a host with no `.git` anywhere above.

**Why this priority**: This is the reported red. It also covers the honest-report half: a sweep
that says it wrote a file must have written it.

**Independent Test**: Build the shape in a temp tree — an ancestor `.git` directory with `hooks/`
and no `HEAD`, a project below it, and a Mission folder with no `meta.json` — and assert
`read_tracked_meta` reports nothing tracked and `build_baseline_feature_meta` returns a payload
instead of `None`.

**Acceptance Scenarios**:

1. **Given** an ancestor `.git` directory that holds no `HEAD` and a Mission folder with no
   `meta.json`, **When** `read_tracked_meta` runs, **Then** it returns
   `TrackedMeta(None, unavailable=False)` — nothing tracked, not a refusal.
2. **Given** the same tree, **When** `build_baseline_feature_meta` runs, **Then** it returns the
   baseline payload (not `None`), so the shared repair writes `meta.json`.
3. **Given** the same tree, **When** the frozen `2.0.6_consistency_sweep` applies, **Then**
   `meta.json` exists afterwards with the inferred `target_branch` and `mission_type`, the work
   package lane is normalized and the legacy prompt reference is rewritten — the pre-existing
   test passes unchanged.

### User Story 2 - A repository git cannot read still refuses (Priority: P1)

A Mission whose `meta.json` is tracked by a repository git refuses to serve (dubious ownership, a
worktree pointer to a gitdir that is gone) is still refused, so no second identity is minted over
history.

**Why this priority**: The fix must not turn the fail-closed refusal into a fabricating branch.
This is the regression guard for #6673 and the positive control for User Story 1.

**Independent Test**: On one shared fixture tree, assert the absent-repository shape reads as
nothing tracked, then swap the stray directory for a `.git` *pointer file* and assert the same
folder now refuses (`unavailable=True`).

**Acceptance Scenarios**:

1. **Given** an ancestor `.git` *file* pointing at a gitdir that does not exist, **When**
   `read_tracked_meta` runs, **Then** it returns `unavailable=True`.
2. **Given** an ancestor `.git` directory that holds `HEAD` and a committed `meta.json` the working
   tree has lost, **When** `read_tracked_meta` runs, **Then** it returns the tracked copy.
3. **Given** the index-only, corrupt, and staged-differs shapes, **When** `read_tracked_meta`
   runs, **Then** each still reports `unavailable=True` with its marker.

### Edge Cases

- **A `.git` that is a symlink to a real git directory**: an anchor (a repository the caller may
  or may not read), so the refusal behaviour is unchanged.
- **`HEAD` present but unreadable** (permission denied): an anchor — fail closed, never fabricate.
- **A `.git` entry that disappears between the walk and the check**: treated as absent, same as a
  tree that never had one.
- **Several ancestors with `.git` entries**: the walk stops at the first *repository* anchor above
  the folder; a non-repository `.git` never shields a real repository higher up.
- **A repository whose git is not installed**: unchanged — `GitCommandError.not_run` already
  answers "nothing is tracked".
- **Residue folders** (`kitty-specs/<child>` with no Mission content): unchanged; the residue rule
  answers before the anchor walk matters.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | An anchor is a repository, not a name | As an operator, I want a `.git` entry counted as an anchor only when it can hold history (a pointer file, or a directory that holds `HEAD`) so that a non-repository `.git` never blocks a repair. | High | Open | [build] | no — the same fixture reads `unavailable=False` after the fix and `unavailable=True` before it |
| FR-002 | A folder outside any work tree reads as nothing tracked | As an operator, I want `read_tracked_meta` to answer "nothing tracked" for a folder outside any work tree so that the shared repair writes the baseline. | High | Open | [build] | no — paired with a pointer-file control on the same fixture that still refuses |
| FR-003 | A repository the caller cannot read still refuses | As a maintainer, I want a `.git` pointer file, an unreadable `HEAD`, or any other git refusal to keep refusing so that no second identity is minted over tracked history. | High | Open | [ratchet] | no — the existing #6673 refusal tests stay green and the new test's second half re-asserts it |
| FR-004 | The frozen sweep's repair is observable | As a maintainer, I want `2.0.6_consistency_sweep.apply` to leave a `meta.json` behind when it reports writing one, so that "repairs feature state" is verified again. | High | Open | [build] | no — the pre-existing red test asserts the file's content, not the change message |
| FR-005 | No assertion is weakened to pass | As a reviewer, I want the fix proven without editing the failing assertion, xfail, skip or a gate, so that the green means the subject changed. | High | Open | [ratchet] | no — the red test and its assertions are byte-identical to `origin/main` |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new git subprocess | The anchor check stays a filesystem stat per ancestor: `read_tracked_meta` spawns no additional git subprocess for the anchor decision, and the number of git calls is unchanged for every existing shape. | Performance | High | Open |
| NFR-002 | Bounded walk | The anchor walk examines each ancestor at most once, stops at the first repository anchor, and resolves a path of depth *d* in O(*d*) stats with no directory listing. | Performance | Medium | Open |
| NFR-003 | Fail closed on the unknown | An unreadable anchor (`OSError` other than "not found") reads as an anchor, so the refusal behaviour is never weakened by an I/O failure. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Frozen migrations untouched | No file under `src/specify_cli/upgrade/migrations/` is edited: those modules' bytes are their `content_hash` (DIRECTIVE_044), and `2.0.6_consistency_sweep` is superseded through `SUPERSEDED_MIGRATIONS` instead. | Technical | High | Open |
| C-002 | Assertions untouched | `tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py` and `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py` keep every existing assertion verbatim; only new tests are added. | Technical | High | Open |
| C-003 | One owner for "what does git hold" | The fix lands in `specify_cli.mission_metadata._has_no_git_anchor` only; no caller gains a second repository-detection walk (`is_kitty_specs_residue`, `probe_tracked_mission_paths` and the project-root walks are not changed). | Technical | High | Open |
| C-004 | Scope stays on the anchor | The reported sweep-lying-about-a-refusal case for a genuinely unreadable tracked copy (`#6673` refusal path) is out of scope: it lives in the frozen module, whose successor already reports honestly. | Technical | Medium | Open |

### Key Entities

- **Git anchor**: the `.git` entry of an ancestor directory, in one of three shapes — a pointer
  *file* (worktree/submodule/separate-git-dir), a *directory* that holds `HEAD` (a repository), or
  a *directory* that does not (a name, not a repository).
- **`TrackedMeta`**: `read_tracked_meta`'s answer — the tracked copy, "nothing tracked", or the
  refusal (`unavailable=True`) that forbids minting an identity.
- **Baseline feature meta**: the `meta.json` payload `build_baseline_feature_meta` builds from the
  tracked copy when git holds one, from the folder itself when nothing is tracked, and never over
  an unreadable tracked copy.

## Success Criteria *(mandatory)*

- **SC-001**: `tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py::test_apply_repairs_feature_state_and_legacy_prompt_refs` passes on this host (where `/tmp/.git` is a non-repository `.git`) with its assertions byte-identical to `origin/main` — [build] · no-op passable: no
- **SC-002**: `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py::test_nothing_tracked_is_not_a_refusal` passes on the same host, unchanged — [ratchet] · no-op passable: no
- **SC-003**: A new test builds a stray non-repository `.git` above a Mission folder, fails before the fix, and passes after it; on the same fixture a `.git` pointer file still refuses — [build] · no-op passable: no
- **SC-004**: Every existing test in `test_read_tracked_meta_6673.py` and `test_m_2_0_6_consistency_sweep.py` stays green, and the suite passes on a host with no stray `.git` above its temp root (both directions of the environment) — [ratchet] · no-op passable: no
- **SC-005**: The change touches one production function plus tests: no migration module bytes change, so `spec-kitty migrate ledger` reports no drift for any shipped migration — [ratchet] · no-op passable: no

## Assumptions

- git defines a repository by its `HEAD` (plus objects); a directory named `.git` without `HEAD` is
  not a repository to git, which is why git answers "not a git repository" for its descendants.
- A project outside a git checkout is a supported upgrade target: `ConsistencySweepMigration.can_apply`
  accepts one with only `.kittify/` or `kitty-specs/`.
- The stray `/tmp/.git` on this host is machine debris from the literal-`.git/hooks` writer of
  #5756, not a fixture the test relies on; the fix is judged on a fixture the test builds itself.
