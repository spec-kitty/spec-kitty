# Mission Specification: Op record auto-commit skips repos that do not track kitty-ops

**Mission Branch**: `issue-6410-op-record-commit-target`
**Created**: 2026-10-18
**Status**: Draft
**Input**: GitHub issue #6410 (title quoted verbatim) — "`profile-invocation complete` auto-commits the Op record onto whatever branch is checked out, so the op(...) commit rides into unrelated topic-branch PRs".

## Context

Closing a governed Op (`spec-kitty profile-invocation complete`, or the
`spec-kitty doctor ops --close-stale` sweep) calls
`ProfileInvocationExecutor._commit_op_record`
(`src/specify_cli/invocation/executor.py`). That commits
`kitty-ops/<id>.jsonl` (or the `kitty-ops/op-closures.jsonl` spine for a sweep
close) through `safe_commit` onto the branch that is checked out. `safe_commit`
stages with `git add --force`, so it commits even when the consumer repository
gitignores `kitty-ops/`. A repository that never tracks Op records on its
primary branch (for example `spec-kitty/doc-kitty`) gets a noise
`op(<profile>): <action> [<id8>]` commit on every issue branch, which then rides
into the PR. Three callers reach this commit: the CLI `complete`, the doctor
sweep (`doctor/ops.py`), and the mission-step-contract executor
(`mission_step_contracts/executor.py`), which closes one Op per composition step.

Grounding (squad, 2026-10-18; reproduced on 4.0.0rc8 in scratch repos):

- **Topic branch.** The commit lands on it silently.
- **`kitty-ops/` gitignored.** The commit lands anyway, because of the force-add.
- **Protected main.** The commit is refused. The record stays on disk, and the warning advises `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`, which the charter forbids agents to use.
- **Nothing reads Op records from git history.** `spec-kitty invocations list`, `doctor ops` and the reality suite read the `kitty-ops/` directory on disk.
- **The only git-history reader is the archive-preservation gate in this repository.** This repository tracks its Op records.
- **The Op executor is the only auto-commit that takes HEAD's branch for non-mission bookkeeping with no gate.**

## Operator decision (branch-target routing for Op records)

Recorded 2026-10-18. The operator chose **"keep the commit, skip it when
untracked"**:

- Keep today's current-branch commit for repositories that track Op records.
  This repository is one; it tracks 544 records, and the operator confirmed it keeps committing.
- Skip the commit when `kitty-ops/` is gitignored, or when the primary branch tracks no Op record.

The alternatives were:

- disk-only by default with an opt-in setting;
- a dedicated `refs/spec-kitty/ops` ref;
- committing only on the primary branch.

They were not chosen and are recorded as open follow-ups in the PR.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A consumer that does not track kitty-ops gets no Op commit (Priority: P1)

An operator in a repository whose primary branch tracks no `kitty-ops/` record, or which
gitignores `kitty-ops/`, closes an Op while a topic branch is checked out. The
branch's commit list is unchanged, and the Op record stays on disk.

**Why this priority**: This is the footgun the issue reports. Every Op close
otherwise pollutes an unrelated PR.

**Independent Test**: Init a repository with a `main` that tracks no Op record and check out a topic branch. Dispatch an Op and complete it. Assert that `git rev-list` on the branch is unchanged, that the record file exists, and that `invocations list` shows it.

**Acceptance Scenarios**:

1. **Given** a repository whose primary branch tracks no file under `kitty-ops/`, **When** an Op is completed on a topic branch, **Then** no commit is added and the record stays on disk.
2. **Given** a repository that gitignores `kitty-ops/`, and whose primary branch tracks Op records from before the ignore was added, **When** an Op is completed on a topic branch, **Then** no commit is added (the ignore wins over the force-add).
3. **Given** a doctor sweep in such a repository, **When** a stale Op is closed, **Then** the `op-closures.jsonl` spine is not committed and the sweep entry reports the skip.

### User Story 2 - A repository that tracks kitty-ops keeps committing (Priority: P1)

An operator in a repository whose primary branch already tracks Op records, such
as spec-kitty itself, closes an Op. The Op record is committed to the current branch exactly as it is today.

**Why this priority**: The operator's decision keeps the existing behavior where
records are tracked. Breaking it would drop the audit history this repository gates.

**Independent Test**: Commit one Op record on `main` and check out a topic branch. Complete an Op and assert that exactly one `op(...)` commit is added that touches only the new record.

**Acceptance Scenarios**:

1. **Given** a primary branch that tracks at least one `kitty-ops/` file and no ignore rule, **When** an Op is completed on a topic branch, **Then** one `op(...)` commit is added containing only that record.
2. **Given** the same repository on protected `main`, **When** an Op is completed, **Then** the commit is refused as today and the record stays on disk.

### User Story 3 - The close says where the record went (Priority: P2)

After a close, the human output says that the record was committed, skipped
(and why) or refused (and why). It never advises the forbidden protected-branch hatch.

**Why this priority**: The issue asks that the close says where the record went. The current
refusal text is wrong in two ways. It advises the hatch, and it claims an uncommitted record "will not survive a checkout or reset", which is not true of an untracked file.

**Independent Test**: Run the CLI `complete` in each of the three cases and assert the printed line.

**Acceptance Scenarios**:

1. **Given** a skipped commit, **When** `complete` runs without `--json`, **Then** it prints that the record is kept on disk at its path, not committed, and the reason.
4. **Given** a doctor sweep whose spine commit was skipped, **When** `doctor ops --close-stale` renders human output, **Then** the skip is reported on its own line, never as a guard refusal. The sweep entry's `commit` value is `skipped:<reason>`. The value set gains this one value; existing values are unchanged.
2. **Given** a refused commit, **When** `complete` runs without `--json`, **Then** the warning names the refusal, says the record is on disk, and does not mention `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`.
3. **Given** `--json`, **When** `complete` runs, **Then** the payload shape is unchanged.

### Edge Cases

- **The primary branch cannot be resolved** (a fresh repository with no commits, or an origin-less repository whose only branches are, say, `trunk` and the issue branch). The commit is skipped with the reason "primary branch unresolved".
  - `core.git_ops.resolve_primary_branch` is NOT used, even with `bias=False`. When its common-branch ladder misses, it falls back to the biased cascade and returns the checked-out branch. The first `op(...)` commit on an issue branch would then satisfy the predicate for the next close on that same branch, so the commit would feed itself.
  - Resolution is: `origin/HEAD`, then `main`, `master`, `develop` as a local or `origin/` ref. Nothing else.
- **Only special files are on the primary branch.** These do not count as tracking Op records: `ops-index.jsonl`, `lifecycle.jsonl` (committed by `spec-kitty next` for owned Missions), `propagation-errors.jsonl` and `op-closures.jsonl` (written only by the sweep's own commit). Only paths matching the Op-record shape `kitty-ops/<26-char ULID>.jsonl` count. This is the same regex as `coordination/coherence.py`.
- **The local primary ref is missing or stale.** The predicate holds when the local primary ref OR `origin/<primary>` tracks an Op record.
- **A tracked file under an ignore rule.** Plain `git check-ignore` reports a tracked path as not ignored, so the ignore check uses `--no-index` on the exact path being committed (the record, or the spine for a sweep close).
- **A doctor sweep closing many Ops.** The primary-tracks decision is computed once per executor and reused. The ignore check runs per path.
- **Not a git worktree, or a detached HEAD.** Unchanged: `committed=False`, refusal `not a git worktree`.
- **A git probe fails during the tracked or ignored check.** The commit is skipped and the reason is reported. The probe never raises out of the close.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Skip the commit when kitty-ops is untracked on the primary branch | As an operator in a repo that does not track Op records, I want closing an Op to add no commit so that unrelated PRs stay clean. | High | Open | [build] | no — paired with FR-003 on the same fixture: committing one record on main flips the outcome |
| FR-002 | Skip the commit when the record path is gitignored | As an operator who gitignores kitty-ops/, I want the ignore honored so that the force-add never overrides my choice. | High | Open | [build] | no — the same fixture without the ignore rule commits |
| FR-003 | Keep the current-branch commit where Op records are tracked | As a maintainer of a repo that tracks Op records, I want the record committed as today so that the audit history stays complete. | High | Open | [ratchet] | no — asserts exactly one op(...) commit touching only the record |
| FR-004 | Report a skipped commit as a distinct outcome | As an operator, I want the close (CLI `complete` and the `doctor ops` sweep, human output) to say the record was kept on disk and why, so that I know where it went. | Medium | Open | [build] | no — asserts the printed skip line and the `skipped:<reason>` sweep entry value |
| FR-005 | Correct the refusal warnings | As an agent operator, I want the `complete` and `doctor ops` warnings to stop advising the forbidden protected-branch hatch and the false checkout/reset claim, so that following them is safe. | Medium | Open | [build] | no — asserts the hatch name and the false claim are absent |
| FR-006 | Primary resolution without current-branch bias | As an operator in an origin-less repository, I want the checked-out issue branch never mistaken for the primary branch, so that an earlier op(...) commit on it cannot re-enable the commit. | High | Open | [build] | no — a `trunk`-only, origin-less fixture with an op(...) commit on the issue branch still skips |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded git cost | The first close per executor adds at most 12 git subprocess calls: origin/HEAD, at most 2 probes of a dangling origin/HEAD name and 6 ladder probes, at most 2 `ls-tree`, and 1 `check-ignore`. Every later close adds exactly 1 call (`check-ignore`), because the primary-tracks decision is cached per executor. | Performance | Medium | Open |
| NFR-002 | Best-effort contract kept | No probe or commit failure raises out of `complete_invocation`. The completed event is always written before the commit decision. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | JSON payload frozen | The `profile-invocation complete --json` payload shape does not change. | Technical | High | Open |
| C-002 | No new hosted or sync surface | The fix stays inside the executor's commit decision. It adds no new ref, config key or transport. | Technical | High | Open |
| C-003 | Terminology | Prose says "branch-target routing", never bare "routing". It says Mission, never feature. | Business | Medium | Open |

### Key Entities

- **Op record**: `kitty-ops/<invocation_id>.jsonl`, the per-Op JSONL event file. The doctor sweep instead appends to `kitty-ops/op-closures.jsonl`.
- **OpCommitOutcome**: the auto-commit result already exposed on `executor.last_op_commit`. It gains a skip reason distinct from a refusal.

## Success Criteria *(mandatory)*

- **SC-001**: In a repository that does not track Op records, completing an Op on a topic branch leaves that branch's commit list byte-identical, and the issue's acceptance test passes.
- **SC-002**: In a repository that tracks Op records, the existing commit assertions hold. Fixtures that relied on an untracked or branch-less repository are reworked to track one ULID record on `main`, with an issue branch checked out.
- **SC-003**: No close output advises `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`.

## Assumptions

- "Tracked on the primary branch" means at least one Op-record-shaped path (`kitty-ops/<ULID>.jsonl`) is in the primary branch's tree, locally or on `origin`. The primary branch is resolved without current-branch bias.
- The archive-preservation gate and this repository's 544 tracked records are unaffected, because this repository tracks Op records.
- **Unverified: `spec-kitty/doc-kitty`.** If that repository's `main` already carries a merged `op(...)` record, the predicate holds there and the commit continues. The remedy is to gitignore `kitty-ops/`, which this fix now honors. The PR states this.
- `doctor ops --json` is not contract-frozen. It gains the new `skipped:<reason>` value for `commit`.
- Docs and comments that describe the unconditional commit change in the same PR: `docs/architecture/trail-model.md`, the executor comment on the hatch, and the `state/contract.py` note.
