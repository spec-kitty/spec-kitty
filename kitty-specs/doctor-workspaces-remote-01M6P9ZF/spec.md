# Mission Specification: doctor workspaces --remote

**Mission Branch**: `issue-7214-doctor-workspaces-remote`
**Created**: 2026-11-05
**Status**: Draft
**Input**: GitHub issue #7214 — "doctor workspaces reads only origin/<primary>, so a fork clone never sees a landed worktree"

## Problem

`spec-kitty doctor workspaces` proves a worktree landed by reading exactly one
local ref, `refs/remotes/origin/<primary>`. In a clone whose `origin` is a fork,
the canonical repository is another remote (`upstream`), and the landing runbook
(`docs/development/how-to/pr-landing.md`, steps 2-3) fetches the PR and `main`
from `upstream`. `origin/<primary>` then never moves, so:

- every landing worktree reports `not_landed` / `CONTENT_NOT_ON_PRIMARY`, forever;
- `--prune` removes nothing, so a maintainer who follows the runbook in a fork
  clone can never clean up;
- the report's own remedy text ("run `git fetch` first") cannot help, because it
  can only refresh the remote the check already reads.

Reproduction (recorded 2026-11-05 against the landed check as merged in #7196):
a bare `upstream.git` holding the rebased landing commit, a bare `origin.git`
left at the pre-landing `main`, git worktree `land-7214` whose commit is on
`upstream/main` → verdict `not_landed: CONTENT_NOT_ON_PRIMARY` with detail
`…has work not on refs/remotes/origin/main`.

## User Scenarios & Testing

### User Story 1 - A fork clone can see and prune landed worktrees (Priority: P1)

A maintainer works in a clone where `origin` is their fork and `upstream` is
`spec-kitty/spec-kitty`. They fetch the PR and `main` from `upstream` (runbook
steps 2-3), then run `spec-kitty doctor workspaces --remote upstream` (and
`--prune`). The worktree whose commits are on `upstream/main` is reported
`landed` and is removed, with the recreate command and the kept tip exactly as
for the `origin` case.

**Why this priority**: without it the check is unusable in the exact clone shape
the runbook prescribes; the user-visible symptom is that the command silently
never works.

**Independent Test**: the fork-clone fixture (worktree landed on `upstream/main`,
`origin/main` still behind) reports `landed` with `--remote upstream`, and the
same fixture still reports `not_landed` without it.

**Acceptance Scenarios**:

1. **Given** a fork clone whose worktree commit is on `upstream/main` only, **When** `doctor workspaces --remote upstream`, **Then** the worktree verdict is `landed` / `LANDED` and the header names `refs/remotes/upstream/main`.
2. **Given** the same clone, **When** `doctor workspaces` (no `--remote`), **Then** the verdict is unchanged from today (`not_landed` / `CONTENT_NOT_ON_PRIMARY` against `refs/remotes/origin/main`).
3. **Given** the same clone, **When** `doctor workspaces --prune --remote upstream`, **Then** the worktree is removed, its branch is deleted, and the printed recreate command is truthful for the tip.
4. **Given** a worktree whose commit is on neither remote, **When** `--prune --remote upstream`, **Then** it is kept and reported `not_landed`.

### User Story 2 - A mistyped or unfetched remote fails loudly, not silently (Priority: P2)

A maintainer types `--remote upstrem`, or names a configured remote they have
never fetched. The command says which remotes exist, or which ref is missing and
which fetch produces it, and exits non-zero instead of reporting every worktree
`unproven` and leaving them all in place.

**Why this priority**: a silently useless report is what the issue complains
about; an explicit option must not recreate that failure mode under a new name.

**Independent Test**: an unknown remote produces one error line naming the
configured remotes and exit 1; a configured-but-unfetched remote produces
`unproven` / `PRIMARY_REF_MISSING` whose detail names `refs/remotes/<remote>/<primary>`
and `git fetch <remote>`.

**Acceptance Scenarios**:

1. **Given** remotes `origin` and `upstream`, **When** `--remote upstrem`, **Then** the report is a single error naming the configured remotes and the exit code is 1.
2. **Given** `upstream` configured but never fetched, **When** `--remote upstream`, **Then** each worktree is `unproven` / `PRIMARY_REF_MISSING` and the detail names the missing ref, the fetch, and the `--remote` hint.
3. **Given** `upstream/HEAD` pointing at a trunk branch that is not one of the common names, **When** `--remote upstream`, **Then** the primary resolves from `refs/remotes/upstream/HEAD` and the proof reads that branch.

### Edge Cases

- `--remote` combined with `--fix`: the husk remediation is unchanged (it never
  prunes); the landed report it also prints honours the option.
- `--remote` combined with `--json`: the payload names the remote it proved
  against, so a script cannot mix up two runs.
- A `--prune` whose assessment came from a different remote: the pre-removal
  re-assessment uses the remote the prune was told to use, so the mismatch fails
  closed (the worktree is kept) rather than removing on the other remote's proof.
- `origin` itself is not configured (a clone with one remote named otherwise):
  the same fail-fast error applies, and the message names the configured remotes.
- A repository with no remote at all keeps the older answer (every worktree
  `unproven` / `PRIMARY_REF_MISSING`), because there is no name to compare.

## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Select the proving remote | As a maintainer in a fork clone, I want to name the remote that holds the canonical `main` so that a landed worktree is proven against the repository it landed in. | High | Open | [build] | no — the assertion is a `landed` verdict the `origin`-only code cannot produce on the same fixture |
| FR-002 | Prune on the same remote | As a maintainer, I want `--prune` to use the remote I named so that the removal decision and its pre-removal re-assessment cannot disagree. | High | Open | [build] | no — the fixture's worktree must be gone afterwards |
| FR-003 | Fail fast on an unconfigured remote | As a maintainer, I want a mistyped remote refused with the configured names so that I do not read a silent all-`unproven` report as "nothing landed". | High | Open | [build] | no — exit code and error text are asserted |
| FR-004 | Name the missing ref and its fetch | As a maintainer, I want the `PRIMARY_REF_MISSING` detail to name `refs/remotes/<remote>/<primary>` and `git fetch <remote>` so that the remedy is one copyable command. | Medium | Open | [build] | no — the detail text is asserted on a configured-but-unfetched remote |
| FR-005 | Resolve the primary from the named remote | As a maintainer whose canonical trunk is not `main`, `master` or `develop`, I want the primary resolved from `refs/remotes/<remote>/HEAD` so that the proof follows the remote I named rather than a guess. | Medium | Open | [build] | no — the fixture's `upstream/HEAD` points at a non-common trunk name |
| FR-006 | Report the remote in machine output and hints | As a script or operator, I want the JSON payload and the printed prune hint to carry the remote so that the report is self-describing. | Low | Open | [build] | no — the payload key and the hint text are asserted |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Still no network contact | `assess_worktrees` and `prune_landed` perform zero fetches/network calls with any `--remote` value: the run must issue no `git fetch`, `git remote update`, `git ls-remote` or `git pull` (asserted by argv capture on the fixture) | Reliability | High | Open |
| NFR-002 | Default behaviour unchanged | With `--remote` omitted, every existing verdict, reason, exit code and JSON key of `doctor workspaces` is unchanged, and the existing assessment and prune CLI suites pass unmodified. The two `unproven` detail messages gain the copyable remedy for the remote they name (`git fetch <remote>`, `git remote set-head <remote> <branch>`); no test asserted their text, and the old text advised `origin` unconditionally in exactly the clone this issue reports. | Compatibility | High | Open |
| NFR-003 | No weaker proof | The proof reads one named remote's `<primary>` ref only; a tip present on some other remote-tracking ref but absent from the named one is still `not_landed` (same-fixture negative control) | Security | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No verdict-contract churn | The `Verdict` and `Reason` enums, their documented first-match order and the exit-code contract are unchanged; only a new option, a new defaulted field and message text are added | Technical | High | Open |
| C-002 | Builds on the merged landed check | The landed worktree check entered `main` with PR #7196 (issue #7173, merged 2026-11-05); this Mission extends it and does not re-open its contract | Business | High | Open |
| C-003 | Destructive guard untouched | The prune keeps using `guarded_worktree_remove`/`guarded_branch_delete` through `LANDED_INTENT`; this Mission changes which ref proves a landing, never how a removal is authorised | Technical | High | Open |

### Key Entities

- **Remote**: the git remote a run proves against; one name, default `origin`.
- **Primary ref**: `refs/remotes/<remote>/<primary>`, the single local ref the absorption proof reads.
- **Assessment**: the per-worktree verdicts plus the remote they were proven against.

## Success Criteria

### Measurable Outcomes

- **SC-001**: On the fork-clone fixture, `--remote upstream` turns the
  `CONTENT_NOT_ON_PRIMARY` verdict into `LANDED` and a `not_landed`-only report
  into an actual removal (1 worktree removed, branch deleted), while the same
  fixture without the option keeps today's verdict. — [build] · no-op passable: no
- **SC-002**: A mistyped remote yields exit 1 with one error line listing the
  configured remotes, and an unfetched one yields `PRIMARY_REF_MISSING` whose
  detail contains the ref and `git fetch <remote>`: 0 silent all-unproven
  reports. — [build] · no-op passable: no
- **SC-003**: The existing landed-worktree assessment suite and the prune CLI
  suite pass without edits, and the new tests fail on the pre-fix code and pass
  after it. — [ratchet] · no-op passable: no
