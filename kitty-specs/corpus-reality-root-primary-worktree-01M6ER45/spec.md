# Mission Specification: Corpus reality check resolves the repository root, not the checkout root

**Mission Branch**: `corpus-reality-root-primary-worktree-01M6ER45`
**Created**: 2026-11-02
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6966 — "tests/contract/test_mission_status_reality.py is red
(payload/oracle mismatches)"; cf. #5927 (same three symptoms: 240 s timeouts, `KeyError: 'findings'`,
"the drift read answers 500").

## Problem

`tests/contract/test_mission_status_reality.py` is a contract check over the committed dogfood corpus.
It takes its repository root from the checkout it is imported from:

```python
REPO_ROOT = Path(__file__).resolve().parents[2]
```

Every Mission in that corpus is then read through the Mission resolver, and the resolver's canonical
answer for a Mission's read directory is the **primary worktree** of the repository — a Mission whose
topology is coord-less or un-backfilled resolves PRIMARY (`candidate_feature_dir_for_mission`). That is
correct product behaviour: the primary worktree is where a Mission's feature directory lives.

So when the corpus reality check runs from a **linked worktree** (`git worktree add`, or any
`spec-kitty` mission worktree used as a checkout), the check enumerates `kitty-specs/` from one working
tree and reads each Mission out of another:

- `scripts`' drift reader (`tests/contract/_mission_status_drift.py::resolve_scan_dir`) sees a resolved
  directory outside `repo_root` and refuses the **whole** project-wide report with
  `500 drift_scan_unreadable` (`ReadDirOutsideRoot`). Every assertion that indexes `run.scan.body
  ["findings"]` then dies with `KeyError: 'findings'` — five of the eight reds in the report, and the
  exact symptom #5927 recorded.
- The Project reader (`tests/contract/_mission_status_project.py::read_dir_of`) does not refuse: it
  falls back to `repo_root/kitty-specs/<slug>` with a third reason (`outside root`) that the drift
  contract has no vocabulary for and that the independent oracle never derives. The corpus then reports
  `project fallbacks: only the reader has [...]` — a corpus-drift red with no drift behind it.

Reproduced on `main` at `faaceb314f` in a linked worktree:

```
git worktree add --detach /tmp/wt-main origin/main && cd /tmp/wt-main && make sync-packs
uv run pytest tests/contract/test_mission_status_reality.py -q -m "corpus and not windows_ci" \
  -k "kinds_one_and_two or kind_three or project_report or per_mission_reports or payloads_validate"
# 5 failed  (KeyError: 'findings' ×3, project fallbacks ×1, DriftReport schema ×1)
```

## What is *not* wrong (grounding)

- The corpus is not drifted from the oracle. From a primary checkout at the same commit the whole
  corpus suite is green (`870 passed, 5 skipped`), and `main`'s own `tests (corpus-blocking)` runs
  (six consecutive runs on `2026-11-02`) are green.
- Not a regression from #6767 / #6947, and not a payload-schema change.
- The reference readers are right to trust the resolver: a reader that re-derived a Mission's directory
  to make itself agree with the oracle would be a second read-path authority, which the contract
  forbids.

The defect is the **root**: the check treats the checkout root as the repository root, and the resolver
does not.

## Fix

Resolve the corpus root once, to the repository's primary worktree root (the first `worktree` entry of
`git worktree list --porcelain`, `Path.resolve()`d), and keep the current checkout root as the answer
when git cannot say (no git, not a repository, an unreadable listing). Every existing assertion,
floor, ceiling and skip stays exactly as it is: the check stops mixing two working trees.

Consequences, stated plainly:

- From a linked worktree the corpus check reads the **primary worktree's** `kitty-specs/` and
  `kitty-ops/` — the tree the resolver, the corpus and the oracle all mean by "the repository".
- From the primary checkout (CI, every plain clone) nothing changes at all.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A linked-worktree checkout runs the corpus check green (Priority: P1)

A maintainer or agent who works in a `git worktree` of the repository (the report's own repro, and the
normal shape of a spec-kitty mission worktree) runs the corpus reality check and gets the same green
result as from the primary checkout, instead of eight reds that claim the corpus drifted from the
oracle.

**Why this priority**: those reds are currently indistinguishable from real corpus drift, which is why
#6966 was filed as a corpus bug and why #5927 is still open with the same symptoms.

**Independent Test**: create a linked worktree at `origin/main`, sync packs, run the corpus-marked
reality tests from inside it, and expect the same pass count as from the primary checkout.

**Acceptance Scenarios**:

1. **Given** a linked worktree of this repository at the same commit as its primary worktree, **When**
   the corpus-marked reality tests run from the worktree, **Then** they pass, with no
   `KeyError: 'findings'` and no `project fallbacks: only the reader has` line.
2. **Given** the primary checkout, **When** the same tests run, **Then** the root is the checkout root,
   exactly as today, and the pass count is unchanged.

---

### User Story 2 - The root rule is one named, tested decision (Priority: P2)

A reviewer can see, in one place and with one test, which root the corpus check scans and why, instead
of inferring it from a `parents[2]` expression.

**Why this priority**: the same assumption ("the checkout is the repository") produced two different
reader behaviours and two issues; it must be named once.

**Independent Test**: a test builds a real repository with a linked worktree and asserts the root
helper answers the primary worktree for both entry points.

**Acceptance Scenarios**:

1. **Given** a repository with a linked worktree, **When** the corpus root is resolved from either
   path, **Then** both answer the primary worktree root.
2. **Given** a directory git cannot answer for, **When** the corpus root is resolved, **Then** it is
   the given path (never an exception, never a different tree).

### Edge Cases

- `git` absent, not a repository, or `worktree list --porcelain` non-zero: the given path is returned,
  so the module still imports and collects on hosts without git.
- A bare repository or a repository whose primary worktree has been removed: the first listed
  worktree still wins; the helper never raises.
- Symlinked checkouts: the helper answers a resolved path, as the readers already compare resolved
  paths.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Corpus root is the repository's primary worktree | As a maintainer, I want the corpus reality check to scan the repository's primary worktree so that it reads one tree instead of enumerating one and reading another. | High | Open | [build] | no — the linked-worktree red is the negative control on the same fixture |
| FR-002 | The root decision has one owner | As a reviewer, I want a single named helper plus a test that pins both entry points, so that the "checkout is the repository" assumption cannot silently return. | High | Open | [build] | no — FR-001's fix without the pin is how #5927 stayed open |
| FR-003 | Unanswerable git falls back to the given path | As an operator, I want the root helper to answer the given path when git cannot say, so that collection never fails on a git-less or non-repository host. | Medium | Open | [build] | yes — the non-repository case is the positive control of the same test |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | One git invocation per test process | The root lookup runs at most one `git worktree list --porcelain` per test process (module import), and none per test. | Performance | Medium | Open |
| NFR-002 | No gate weakened | The number of collected corpus-marked tests, every floor, ceiling, allow-list and skip in `tests/contract/test_mission_status_reality.py` stay byte-identical; only the root expression changes. | Reliability | High | Open |
| NFR-003 | Read-only on the primary worktree | The corpus check writes nothing into the primary worktree (the module's existing tree-write guard keeps passing when it scans it from a linked worktree). | Security | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Readers keep trusting the resolver | The reference readers must not re-derive a Mission's read directory; the corpus root is fixed, the readers are not. | Technical | High | Open |
| C-002 | Scope | `tests/contract/**` (the reality-check module and the oracle helper module), one docs note, one changelog fragment. No `src/` change. | Technical | High | Open |
| C-003 | No test weakening | No skip, xfail, marker, deselection or assertion edit may be used to reach green. | Technical | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The corpus-marked suite passes from a linked worktree at the same commit as its primary worktree, with zero `KeyError: 'findings'` and zero `project fallbacks:` failures (before: 5 failures on the reported commit) — [build] · no-op passable: no
- **SC-002**: The same suite from the primary checkout reports the same pass/skip counts as before the change (`870 passed, 5 skipped` on `faaceb314f`) — [ratchet] · no-op passable: no
- **SC-003**: One new test pins both roots of a real linked-worktree pair, and it is red on the pre-fix helper — [build] · no-op passable: no
