# Mission Specification: Git paths are data, not text

**Mission Branch**: `claude/git-path-remediation-rnrzfz`
**Created**: 2026-09-30
**Status**: Draft
**Input**: User description: "Git paths are data, not text (#5392, #5400): kernel/git owns running git, NUL-safe path listing and a GitPath value type; specify_cli/core/vcs owns intent-named queries; migrate ref_advance first (P0), then every path-listing caller until the no--z allowlist is empty; record the ratchet-as-priced-debt ruling in a 4.x ADR and the charter."

## Intent Summary

Source: Stijn's steering messages of 2026-09-30 (18:10Z, 18:33Z, 18:35Z) and the
milestone-11 slice-A brief. Stijn is async, so the brief stands in for the
discovery interview; the four forks it left open are recorded as resolved
Decision Moments on this mission.

- **Primary actor:** a Spec Kitty operator running `spec-kitty consolidate`
  (and any other command that inspects the working tree) in a repository whose
  paths contain spaces, non-ASCII characters, or directories that the mission
  replaces with files.
- **Trigger:** a command asks git which paths are dirty, tracked, changed or
  present in a tree.
- **Outcome:** the command sees the real paths, so a guard that must refuse
  (because a reset would destroy local bytes) refuses, whatever the shape of the
  path.
- **Rule that always holds:** no Spec Kitty command reads git's path output as
  display text. Paths come from one shared git owner that asks git for
  NUL-delimited output and compares paths component by component.
- **Boundary:** the "how" (running git, NUL-safe listing, byte-safe decode, the
  path value type, and generic listing queries such as status entries, tree
  paths and changed paths) is shared infrastructure in the lowest layer, usable
  by every layer including the branch-advance plumbing. The "what" stays with
  its owner: the reset-obstruction decision stays in the branch-advance module
  (its single existing authority), built on the path value type; composed
  helpers that carry Spec Kitty rules stay in the core VCS module. Callers never
  build path-listing argv or parse output.
- **Governance:** allowlist ratchets are priced debt (they cost CI money on
  every run). This mission's gate closes with an empty allowlist, and the ruling
  is recorded in an ADR and the project charter.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consolidate refuses to overwrite an ignored file under a quoted path (Priority: P1)

An operator has an ignored local file `src/local data/notes.txt` (the directory
name contains a space). The mission they consolidate tracks a file at that same
path. Consolidation must refuse before moving the target branch, naming the
obstruction, exactly as it already does for `src/local-data/notes.txt` (#5392).

**Why this priority**: data loss with exit 0 on a routine command; release blocker.

**Independent Test**: a real-git fixture advances a checked-out branch over an
ignored file whose directory contains a space; the advance refuses and the
local bytes survive.

**Acceptance Scenarios**:

1. **Given** an ignored local `src/local data/notes.txt` and an incoming commit
   that tracks that path, **When** the branch advance runs, **Then** it refuses
   with the obstructing path in the message, the target ref is unchanged and
   the local bytes are unchanged.
2. **Given** the same fixture with `src/local-data/` (positive control),
   **When** the advance runs, **Then** it refuses identically.
3. **Given** a non-ASCII directory name with `core.quotePath=true`, or a file
   name containing ` -> `, **When** the advance runs, **Then** it refuses
   identically.
4. **Given** an *untracked* local file under a quoted directory (`?? "a b/"`)
   that collides with an incoming tracked path, **When** the advance runs,
   **Then** it refuses identically.
5. **Given** a fully ignored directory reported collapsed (`!! .venv/`) and an
   incoming tracked path beneath it that is absent locally, **When** the
   advance runs, **Then** it refuses (deliberately conservative: git cannot
   tell us which children exist without listing them).
6. **Given** each of the three public entry points that consult the
   obstruction rule (branch advance, the reset-obstruction probe, and the
   guarded worktree removal with untracked-as-dirty), **When** a quoted-path
   collision exists, **Then** each reports it.

**Half-by-half proof**: the lossless path decode (FR-001) and the ancestor
relation (FR-002) are independent halves; reverting either one alone turns its
own regression test red.

---

### User Story 2 - Consolidate refuses to delete ignored descendants of a replaced directory (Priority: P1)

A mission replaces tracked directory `src/store/` with a file `src/store`. The
operator has ignored local data at `src/store/local.txt`. Consolidation must
refuse rather than delete it (#5400).

**Why this priority**: data loss with exit 0 on ordinary ASCII paths; release blocker.

**Independent Test**: a real-git fixture advances a branch whose incoming
commit replaces a directory with a file while an ignored descendant exists.

**Acceptance Scenarios**:

1. **Given** ignored `src/store/local.txt` and an incoming file `src/store`,
   **When** the advance runs, **Then** it refuses and the ignored bytes survive.
   The same holds for an untracked descendant and for more than one level of ancestry.
2. **Given** ignored `src/storehouse/x` and an incoming file `src/store`,
   **When** the advance runs, **Then** it succeeds (no false refusal on a shared
   text prefix).

---

### User Story 3 - Every command reads paths the same, lossless way (Priority: P2)

Commands other than consolidate (implement, safe-commit, move-task, mission
finalize, accept, doctors, migrations) also list dirty, staged, tracked or
changed paths. They ask the shared git owner by intent and receive real paths,
so a quoted or non-ASCII path never makes them miss, misclassify or mangle a
file.

**Why this priority**: the defect class, not only its two reported instances.

**Independent Test**: an architectural gate finds no path-listing git call and
no hand-written porcelain parser outside the shared owner, with an empty
allowlist; focused unit tests cover each new query against quoted, spaced and
non-ASCII paths.

**Acceptance Scenarios**:

1. **Given** the source tree, **When** the gate runs, **Then** it reports zero
   path-listing git invocations outside the shared owner and its allowlist is empty.
2. **Given** a deliberately re-introduced `git status --porcelain` call in a
   scratch copy, **When** the gate runs, **Then** it fails (self-mutation proof).

---

### User Story 4 - Ratchets are recorded as priced debt (Priority: P3)

A maintainer reading the charter or ADRs learns that an allowlist ratchet costs
money on every CI run, must be time-boxed and owned, and should be drained to a
zero-allowlist invariant rather than kept as a permanent fixture.

**Why this priority**: governance so future missions stop adding long-lived ratchets.

**Independent Test**: the ADR exists under the 4.x ADR directory, the charter's
standing order 5 and Burn-down Policy state the ruling, and docs freshness and
terminology checks pass.

**Acceptance Scenarios**:

1. **Given** the charter, **When** a maintainer reads standing order 5, **Then**
   it says a ratchet is priced debt to drain, preferring an empty-allowlist invariant.

### Edge Cases

- Rename and copy status entries (`R`/`C`) carry an original path; both paths
  must be exposed as data, and a file literally named `a -> b` must not be split.
- A directory entry reported by status with a trailing slash (`!! dir/`) must
  compare as a directory against tracked descendants.
- Paths are compared component by component: `src/store` is an ancestor of
  `src/store/local.txt` but not of `src/storehouse`.
- Output that is not valid UTF-8 must not crash the query; it is decoded
  losslessly (surrogate escape) so it round-trips to the filesystem.
- An empty path, an empty tree and an empty status listing are handled without error.
- Git failure (non-zero exit) is a typed error, never an empty result that a
  guard could read as "nothing dirty".

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Quoted-path obstruction refuses | As an operator, I want the branch advance to refuse when an ignored or untracked file whose path git would quote collides with an incoming tracked path, so that my local bytes are never overwritten (#5392). | High | Open | [build] | no — paired with the unquoted `src/local-data/` control on the same fixture |
| FR-002 | Ancestor obstruction refuses | As an operator, I want the branch advance to refuse when an incoming tracked file replaces a directory that holds my ignored or untracked files, so that they are never deleted (#5400). | High | Open | [build] | no — paired with the `storehouse` non-collision on the same fixture |
| FR-003 | One shared git owner for path output | As a maintainer, I want one shared module to run git, request NUL-delimited path output and decode it losslessly, so that no caller parses git's quoted display text. | High | Open | [build] | no |
| FR-004 | Path value type with component-wise relations | As a maintainer, I want a repository path value type whose equality, ancestry and containment compare path components, so that `store` never matches `storehouse`. | High | Open | [build] | no |
| FR-005 | Typed status entries | As a maintainer, I want status results as typed entries (status code, path, original path for renames/copies), so that callers never split on ` -> `. | High | Open | [build] | no |
| FR-006 | Intent-named queries | As a maintainer, I want generic intent-named listing queries (status entries, tree paths, changed paths and entries, commit paths, log-range paths, tracked paths, index entries, tracked check) in the shared owner, and domain decisions (such as reset obstruction) kept with their existing owner, so that callers state what they need and never build path-listing argv. | High | Open | [build] | no |
| FR-007 | ref_advance on the shared owner | As a maintainer, I want the branch-advance module to take its status and tree paths from the shared owner and decide obstruction with the path value type, keeping its existing public behaviour and messages. | High | Open | [build] | no |
| FR-008 | Every path-listing caller migrated | As a maintainer, I want every path-listing git call and every hand-written porcelain or `-z` parser in the source tree migrated onto the shared queries, so that the defect class is closed, not just its two instances. | High | Open | [build] | no |
| FR-009 | Empty-allowlist gate | As a maintainer, I want an architectural gate that fails on any path-listing git invocation or hand-written porcelain parsing outside the shared owner, with an empty allowlist at mission close and a self-mutation proof, so that the class cannot return. | High | Open | [build] | no — self-mutation test proves it bites |
| FR-010 | Follow-up for plain git runners | As a maintainer, I want the remaining hand-built git argv that do not list paths filed as a follow-up issue, with its gate added only once it can start empty. | Medium | Open | [build] | yes — tracked by the issue existing, not by code |
| FR-011 | Ratchet ruling in an ADR | As a maintainer, I want a 4.x ADR recording that allowlist ratchets are priced per-CI-run debt, linked to the 2026-09-14 census-ratchet ADR. | Medium | Open | [build] | no |
| FR-013 | Fail-open callers classified | As a maintainer, I want every migrated caller that today treats a git failure as "no paths" classified: a guard lets the typed error propagate (fail closed); an advisory caller catches it at the call site with a one-line rationale; tests that pinned fail-open behaviour in a guard are updated as pinned buggy behaviour. | High | Open | [build] | no |
| FR-014 | Literal path arguments | As a maintainer, I want paths passed to git by the shared owner to be literal by default (after `--`, with literal pathspecs), so that a file named `-x`, `*` or `:(top)` is never read as an option or pattern; callers needing a pattern opt in explicitly. | Medium | Open | [build] | no — paired with a literal `*` filename fixture |
| FR-012 | Ratchet ruling in the charter and packs | As a maintainer, I want the charter's standing order 5 and Burn-down Policy amended, a generic "ratchets carry recurring cost; drain them" note in the consumer ratchet tactic, and the CI-cost rationale in the internal pack. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No behaviour drift | Every existing test of a migrated module passes unchanged, except tests that pinned the buggy quoted/ancestor behaviour or a guard's fail-open behaviour (FR-013), each listed in the PR; 0 new failures in the targeted blast radius. | Reliability | High | Open |
| NFR-002 | Complexity ceiling | Every new or changed function has cyclomatic complexity ≤ 15 (ruff C901); ruff, ruff format and mypy report 0 issues on changed files. | Maintainability | High | Open |
| NFR-003 | Coverage of new code | New shared-owner and query code has ≥ 90% line coverage from focused unit tests. | Maintainability | High | Open |
| NFR-004 | Fail closed | 100% of query failures (git non-zero exit) raise a typed error; 0 queries return an empty result on git failure. | Reliability | High | Open |
| NFR-005 | No extra git processes on the hot path | A migrated call site spawns no more git processes than before (≤ 1:1). | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Layer direction | The shared "how" lives in the kernel layer and imports nothing from charter, runtime, mission_runtime or specify_cli; the enforced chain `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli` holds. | Technical | High | Open |
| C-002 | ref_advance stays plumbing | The branch-advance module keeps importing zero `specify_cli` modules (existing NFR-004 ratchet). | Technical | High | Open |
| C-003 | Red-first per P0 | #5392 and #5400 each get an issue-pinned regression test that is shown red on the base before the fix, per ADR 2026-07-17-1; converted to focused unit tests afterwards. | Process | High | Open |
| C-004 | No version bump | No version bump past the untagged rc. | Process | High | Open |
| C-005 | Pack tiers | Consumer doctrine goes in `packs/built-in/`, in-house rationale in `packs/internal/`; the graph is regenerated after any pack edit. | Technical | Medium | Open |
| C-007 | Runner is command-agnostic | The shared runner knows no specific git command. Destructive argv (`reset --hard`, `update-ref`, `worktree remove`, `stash`, `clean`) stays at its current guarded call sites; the existing destructive-op and merge-pipeline gates keep scanning them (token lines re-pinned, not moved); a test asserts the shared owner contains no destructive literal. | Technical | High | Open |
| C-008 | Git 2.25 floor | The shared owner uses only flags available in git 2.25 (no `ls-files --format`; `merge-tree -z` stays behind the existing ≥ 2.38 guard). | Technical | High | Open |
| C-009 | P0 separately landable | FR-001–FR-007 with C-003 form a slice that can land on its own. The class gate (FR-009) lands only once it can start empty, so no temporary allowlist ever ships. | Process | High | Open |
| C-006 | No heavy suites in mission | Implement and review run targeted tests and the named gate files only; no full architectural/e2e/perf sweep. | Process | Medium | Open |

### Key Entities

- **Repository path**: a path relative to the repository root, compared by its components; relations: equal, ancestor-of, contains.
- **Status entry**: a two-character status code, a repository path, and an optional original path (renames and copies); flags for untracked and ignored.
- **Path query**: an intent-named question about a checkout or ref (what is dirty, what a tree contains, what changed between two points, what would a reset obstruct) answered with repository paths or status entries.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The #5392 and #5400 reproduction scenarios both end in a refusal with the local bytes preserved, in 4 of 4 fixture variants (quoted space, non-ASCII, ` -> ` name, ancestor). — [build] · no-op passable: no
- **SC-002**: The class gate counts N > 0 offending sites on the base (it is red there) and 0 at close, with an empty allowlist. — [build] · no-op passable: no
- **SC-003**: The only allowlist this mission introduces has 0 entries at close. — [build] · no-op passable: no
- **SC-004**: The ratchet ruling appears in 1 new ADR and 2 charter sections. — [build] · no-op passable: no

## Assumptions

- PR #5437 (external, closes #5400) may land before this mission. Its commit is carried with authorship intact so either landing order rebases cleanly, and its tests are the oracle for FR-002.
- `ls-files --error-unmatch` existence checks are migrated to a tracked-path query even though they do not parse paths, so the gate can be a simple, empty-allowlist rule.
- The supported git floor is 2.25 (`_coordination_doctor.py`). `worktree list --porcelain -z` needs git 2.36, so `worktree list` parsing is out of scope: worktree paths are never quoted there.
- The seven existing hand-written `-z` parsers (each decoding differently) are folded onto the shared owner too, so there is one decode rule.
- The existing T019 gate (`tests/architectural/test_destructive_op_routing.py`) scans `git/`, `consolidation/`, `coordination/` and `core/vcs/` for porcelain literals; the shared owner lives in the kernel, outside that scan, and T019's baseline shrinks as sites migrate.
