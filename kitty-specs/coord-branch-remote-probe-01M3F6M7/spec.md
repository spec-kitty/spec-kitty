# Mission Specification: Coordination branch remote-existence probe

**Mission Branch**: `issue-4979-coord-branch-remote-probe`
**Created**: 2026-09-26
**Status**: Draft
**Input**: GitHub issue #4979 — `doctor coordination --fix` in a checkout without the remote coordination branch (single-branch/shallow/CI clone, pruned origin ref) flattens a live coord mission as 'never created'; `implement` auto-commits the flatten and every teammate's pull hides their approvals.

## Context & Problem

A coordination-topology mission is in flight on a shared remote. Teammate 1 has real
approvals on the coordination branch `kitty/mission-<slug>` and has pushed all branches.
Teammate 2 works from a checkout that **cannot see the remote coordination branch** — a
`git clone --single-branch -b main` (same ref shape as a `--depth 1` / CI checkout), or a
normal clone after origin's coord branch was deleted and `git fetch --prune` ran. There is
no local head `refs/heads/<coord>` and no remote-tracking ref `refs/remotes/origin/<coord>`,
**yet the branch still exists on origin**.

Following only the CLI's own hints, teammate 2:
1. `agent status emit … --to claimed` → refused: "Coordination branch … declared in
   meta.json but deleted from git … run `spec-kitty doctor coordination --fix` to flatten
   automatically".
2. `doctor coordination --fix` → flattens `meta.json` (drops `coordination_branch`, demotes
   `topology: coord → lanes`, sets `flattened: true`), left uncommitted.
3. `implement WP##` → auto-commits every uncommitted planning artifact under
   `kitty-specs/<slug>/`, **carrying the flattened `meta.json` to `main`**, then pushes.
4. Teammate 1 pulls `main` (clean fast-forward). The mission is now flattened for everyone:
   approved WPs read `planned`, dependents are refused, and `doctor coordination` reports
   healthy because the mission no longer declares a coordination branch. The two status
   histories (primary vs. coordination log) silently diverge.

The `refs/remotes/` scan added by #2614 does not cover this vector — it names "fresh clone,
CI checkout, pruned local branch" but only inspects **already-fetched** remote-tracking
refs, which a single-branch/shallow/pruned checkout does not carry. The residual: no probe
consults the remote authority itself (`git ls-remote`).

Bounded: nothing is deleted; the coordination branch keeps every row, and a `git revert` of
the auto-commit (or hand-restoring the keys) recovers the view. But no shipped command
un-flattens, and the trigger is any checkout without the remote coord ref.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The branch-existence probe consults the remote before declaring a coordination branch never-created (Priority: P1)

A teammate on a single-branch / shallow / CI clone (or after a pruned origin ref) runs a
coord-writer command against a mission whose coordination branch has no local or
remote-tracking ref but still exists on origin. The CLI must recognise the branch as
present — it must not raise `CoordinationBranchDeleted` / emit
`COORDINATION_WORKTREE_NEVER_CREATED`, because the branch was not deleted.

**Why this priority**: This is the root cause. Fixing the single shared probe
(`_coord_branch_exists`) simultaneously stops the read-path refusal AND the doctor
emission (the doctor gates on the same probe), closing the defect class at its source.

**Independent Test**: In a `git clone --single-branch -b main` of a repo whose origin holds
`kitty/mission-<slug>`, the probe reports the branch present (a `git ls-remote` hit),
`agent status emit` is not refused with the deleted-branch error, and `doctor coordination`
does not emit `COORDINATION_WORKTREE_NEVER_CREATED`.

**Acceptance Scenarios**:

1. **Given** a single-branch clone with no `refs/heads/<coord>` and no `refs/remotes/*/<coord>`, but origin's `git ls-remote` lists `refs/heads/<coord>`, **When** the branch-existence probe runs, **Then** it reports the branch present (never fires the deleted-branch path), and a coord read raises `CoordinationWorktreeUnmaterialized` (materialize/fetch), never a silent empty surface.
2. **Given** a checkout with a reachable origin that no longer carries the coordination branch (no local ref, no remote-tracking ref, `git ls-remote` exits 0 empty), **When** the probe runs, **Then** it reports the branch absent (the legitimate never-created/deleted path is preserved).
3. **Given** an origin-less repo (zero remotes configured) with no local `refs/heads/<coord>`, **When** the probe runs, **Then** it retains local-authority behaviour and reports the branch absent (existing origin-less DELETED/flatten tests stay green).
4. **Given** a configured remote that errors / times out / would prompt for credentials, **When** the probe cannot prove absence, **Then** it fails closed and treats the branch as present (no hang, no credential prompt, no fabricated deleted verdict).
5. **Given** a full clone that already carries `refs/remotes/origin/<coord>`, **When** the probe runs, **Then** behaviour is unchanged — the local-head and `refs/remotes/` fast paths short-circuit before any remote round-trip (a regression pins "no ls-remote when refs/remotes hits").

### User Story 2 - `doctor coordination --fix` refuses to flatten a mission whose coordination branch still exists on any remote (Priority: P1)

Even if a `COORDINATION_WORKTREE_NEVER_CREATED` finding is reached, the destructive flatten
must re-verify that the branch is truly gone before dropping `coordination_branch` /
demoting topology. A mission whose coordination branch still exists on a remote must never
be flattened by `--fix`.

**Why this priority**: This is the last line of defence before irreversible-by-default data
loss (no shipped command un-flattens). It guards the flatten site independently of the
probe, so a future probe regression cannot silently reach the destructive mutation.

**Independent Test**: With a stubbed/short-circuited finding present, `_fix_never_created_branches`
leaves `meta.json` untouched (keeps `coordination_branch`, keeps `topology: coord`) when the
branch is present on a remote, and reports the refusal.

**Acceptance Scenarios**:

1. **Given** a `COORDINATION_WORKTREE_NEVER_CREATED` finding for a mission whose coordination branch is present on origin, **When** `doctor coordination --fix` runs, **Then** the flatten is refused, `meta.json` is unchanged, and the user is told the branch exists remotely and the fix was skipped.
2. **Given** a finding for a mission whose coordination branch is genuinely absent everywhere, **When** `--fix` runs, **Then** the flatten proceeds exactly as today.

### User Story 3 - `implement`'s planning-artifact auto-commit never silently carries a topology demotion to the target branch (Priority: P2)

`spec-kitty implement` auto-commits uncommitted planning artifacts under `kitty-specs/<slug>/`
before creating the lane worktree. A `meta.json` whose diff **removes `coordination_branch`
or demotes `topology`** (a flatten) must not ride along silently into that commit and onto
the target branch.

**Why this priority**: Defense-in-depth. With US1 in place the doctor no longer flattens, so
`meta.json` is not dirtied — but any other source of an uncommitted flatten (a hand-edit, a
future regression) must not silently propagate a routing change for the whole team through a
`chore: planning artifacts` commit.

**Independent Test**: With an uncommitted `meta.json` flatten present in the planning-artifact
source dir, `implement`'s staging REFUSES with an actionable message (deterministic contract)
and does not carry the demotion to the target branch.

**Acceptance Scenarios**:

1. **Given** a tracked `meta.json` whose HEAD carries a non-null `coordination_branch` and whose working copy drops it / demotes `topology`, **When** `implement`'s planning-artifact staging runs, **Then** it REFUSES with an actionable message naming the demotion (deterministic default; never a silent commit).
2. **Given** an ordinary uncommitted `meta.json` change that does not demote topology (e.g. adding `source_description`), **When** staging runs, **Then** it is committed exactly as today (no false refusal).
3. **Given** an untracked `meta.json` with no HEAD baseline (`git show HEAD:…` exit 128 — a legitimate first commit, including a genuinely-flat mission), **When** staging runs, **Then** it is ALLOWED (fail-open here is correct — a first commit establishes meta.json).
4. **Given** a corrupt/unparseable `meta.json` on either the HEAD or working side, **When** staging runs, **Then** it fails closed and REFUSES with an actionable message.

### Edge Cases

- **Zero remotes configured (origin-less repo)**: there is no remote authority to consult. The probe must NOT treat this as "present" — it retains today's local-authority behaviour (missing local head ⇒ absent ⇒ DELETED/flatten). This keeps the genuine-deletion path and the existing origin-less tests (`test_coord_never_created.py`, `test_backfill_topology` T007) green. The real trigger (`--single-branch`, `--depth 1`, pruned origin) ALWAYS has a remote configured, so this scoping fixes the vector without over-reaching.
- **Reachable remote, branch absent (clean-miss)**: `git ls-remote` exits 0 with empty output ⇒ that remote votes absent; if no configured remote lists the branch, it is genuinely absent ⇒ the flatten path is preserved.
- **Unreachable / erroring / timing-out remote**: a configured remote that errors, times out, or prompts for credentials ⇒ fail-closed "present" (never fabricate a deleted verdict from a transient network condition). `GIT_TERMINAL_PROMPT=0` + SSH BatchMode + bounded `timeout=` prevent a hang.
- **Multiple remotes**: the branch may exist on a non-`origin` remote. "Exists on any configured remote" is the guard; the probe iterates all remotes, not only `origin`.
- **`git ls-remote` latency**: the remote round-trip only occurs after the cheap local checks (local head, then `refs/remotes/` scan) miss, and is memoized per-process, so the common full-clone path pays nothing (US1 scenario 4, NFR-001).
- **Foreign / non-repo context**: the existing `_roots_own_checkout` fail-closed guard (#154) must remain and must precede the remote probe — a probe from an ad-hoc dir or a guest of an enclosing repo still treats the branch as present and never ls-remotes a stranger's remotes.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Remote-existence probe | As a teammate on a single-branch/shallow/CI/pruned checkout, I want the branch-existence probe to consult the remote (`git ls-remote`) when no local head and no remote-tracking ref match, so that a coordination branch that still exists on origin is recognised as present rather than "never created". | High | Open |
| FR-002 | Preserve genuine-deletion path | As a maintainer, I want the probe to still report a coordination branch absent when it is gone from every remote and locally, so that the legitimate flatten/recovery path is preserved. | High | Open |
| FR-003 | Tri-state fail-closed remote discrimination | As a teammate, I want the probe to discriminate three `git ls-remote` outcomes: a MATCH ⇒ present; a REACHABLE CLEAN-MISS (exit 0, empty) ⇒ that remote votes absent; and ERROR / TIMEOUT / unreachable ⇒ fail-closed present. When ZERO remotes are configured, retain today's local-authority behaviour (missing local head ⇒ absent), so a genuinely-deleted branch in an origin-less repo still flattens and the network flake never fabricates a deleted verdict. | High | Open |
| FR-004 | Doctor flatten remote re-verification | As a maintainer, I want `doctor coordination --fix` to re-verify against the remote (via the same shared primitive) before flattening a `COORDINATION_WORKTREE_NEVER_CREATED` finding, and refuse (leaving `meta.json` unchanged, with an actionable message) when the coordination branch still exists on any remote. | High | Open |
| FR-005 | Implement auto-commit demotion guard (REFUSE) | As a teammate, I want `implement`'s planning-artifact staging to REFUSE with an actionable message (never silently commit) when the uncommitted `meta.json` change is a topology demotion — `coordination_branch` present-and-non-null at HEAD becomes absent/null in the working copy (corroborated by `routes_through_coordination(HEAD) AND NOT routes_through_coordination(working)`). A meta.json with no HEAD baseline (untracked, `git show HEAD:…` exit 128) is a legitimate first commit ⇒ ALLOW; a corrupt/unparseable meta.json on either side ⇒ fail-closed REFUSE. | Medium | Open |
| FR-006 | Fetch-first actionable guidance | As a teammate on a remote-only checkout who hits the emit-refusal, I want the next-step to branch on local-head vs remote-only and tell me to `git fetch origin <coord_branch>` (or fix `remote.origin.fetch`) FIRST — never steer me to flatten and never hand a `git worktree add` that fails because the ref isn't fetched locally. The genuine-deletion guidance is preserved for the truly-absent case. | Medium | Open |
| FR-007 | Read-path fails closed, never silent-empty | As a teammate on a remote-only checkout, I want a coord read to raise `CoordinationWorktreeUnmaterialized` (materialize/fetch recovery), never silently substitute the empty primary surface, so "no content" is never mistaken for "nothing was ever written" (#4959 clobber class). | High | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Local-first probe cost + memoization | The remote (`git ls-remote`) round-trip runs ONLY after the local-head check and the `refs/remotes/` scan both miss; the common full-clone / local-head path performs zero extra network calls. Because a single-branch/CI checkout never materializes the coord worktree, the probe would otherwise fire the network arm on EVERY coord read in one invocation — so the remote lookup is memoized per-process keyed `(repo_root, coord_branch)` (one round-trip per invocation). CLI stays < 2s for typical projects. | Performance | High | Open |
| NFR-002 | Fail-closed safety + no hang/prompt | The probe fails closed toward "branch present" on any error (unreadable git, unreachable remote, non-zero exit, timeout), never toward "deleted". The network call passes a bounded `timeout=` (~5s) and catches `subprocess.TimeoutExpired`, and sets `GIT_TERMINAL_PROMPT=0` plus SSH `BatchMode` so a private-origin credential prompt can never block the CLI. | Reliability | High | Open |
| NFR-003 | Type & lint clean | New code passes `mypy --strict`, `ruff check`, and `ruff format --check` with zero issues and no new suppressions; new helpers stay at cyclomatic complexity ≤ 15. | Maintainability | High | Open |
| NFR-004 | Test coverage | New branches/helpers carry focused tests in the same commit (≥ 90% new-code coverage); each of the three defects lands a red-first regression pinned to #4979 through its pre-existing entry point. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single canonical remote-lookup primitive | A second remote-branch probe already ships (`_branch_resolvable`, `mission_type.py`, fail-closed toward FALSE). Do NOT add a third. Extract ONE shared tri-state remote-lookup primitive returning `{HIT, CLEAN_MISS, ERROR}` (iterate all configured remotes, bounded timeout, no prompt) in a canonical git-probe home; `_coord_branch_exists` consumes it fail-closed-toward-present, `_branch_resolvable` is refactored onto it fail-closed-toward-false (killing the duplicate + its missing-timeout hang). WP02/WP03 consume the same primitive, never hand-roll a remote check. | Technical | High | Open |
| C-002 | Preserve write-gate strictness | `_coord_branch_is_local_head` (the WRITE self-materialization gate, #4970) must remain STRICTER than `_coord_branch_exists` — a remote-only branch stays "not a local head" so the write gate keeps refusing self-materialization. Do not loosen the write gate. | Technical | High | Open |
| C-003 | Red-first / ATDD | Each defect lands an issue-pinned `@pytest.mark.regression` reproduction that is RED through the pre-existing entry point before the fix and GREEN after; transitional repros become focused unit/functional tests, never left marked `regression`. | Process | High | Open |
| C-004 | Terminology canon | All new prose, error strings, and identifiers use canonical terms (Mission, not Feature; `--mission`, not `--feature`); no forbidden terms. | Technical | Medium | Open |
| C-005 | No new external dependency | The remote probe uses `git` (already a required dependency); no new library or network client is introduced. | Technical | Medium | Open |

### Key Entities

- **Coordination branch**: `kitty/mission-<slug>` — the branch carrying a coord-topology mission's lifecycle surfaces (status log, issue-matrix). Its existence determines whether a mission is coord vs. flattened.
- **Branch-existence probe (`_coord_branch_exists`)**: the single canonical function deciding "branch present vs. never-created/deleted", consumed by both the coord read path (`CoordinationBranchDeleted`) and `doctor coordination --fix`.
- **`meta.json` topology fields**: `coordination_branch`, `topology`, `flattened` — the routing-authority fields a flatten mutates.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a single-branch / shallow / pruned checkout whose origin holds the coordination branch, following the CLI's own hints (`status emit` → `doctor coordination --fix` → `implement`) leaves the mission's `coordination_branch` and `topology: coord` intact — the flatten never happens (the issue's `trigger` arm now matches its `control` arm).
- **SC-002**: After the fix, teammate 1's pull of `main` still shows their approved WPs as `approved` and permits dependents to be claimed — approvals are never hidden by a teammate's `doctor --fix`.
- **SC-003**: A genuinely deleted coordination branch (gone everywhere) still flattens on `--fix`, and a full-clone workflow shows zero added git round-trips (the local fast paths short-circuit).
- **SC-004**: Three red-first regressions (probe, doctor flatten, implement auto-commit), each pinned to #4979, are RED on the mission base and GREEN on the final commit; the targeted test surfaces pass.
