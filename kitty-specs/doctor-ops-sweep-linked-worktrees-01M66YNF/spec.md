# Mission Specification: `doctor ops` sweeps Op records in every checkout

**Mission Branch**: `issue-6661-doctor-ops-sweep-linked-worktrees`
**Created**: 2026-10-30
**Status**: Draft
**Input**: GitHub issue #6661 — "`doctor ops` sweeps Op records only in the repository root checkout, not linked worktrees (follow-up to #6564)". Remaining scope after #6664 landed the mission-step half.

## Context

Before #6564 every Op record was written in the repository root checkout, because
`find_repo_root` maps a linked worktree back to it. #6564 moved write custody to the
invoking checkout (`resolve_op_record_root`), and #6664 finished the mission-step half
(`mission_step_contracts/executor.py` passes `record_root=resolve_op_record_root(...)`).
An Op opened by `spec-kitty dispatch`, `profile-invocation complete`, the
`agent action --invocation-id` claim seam or a mission step now lives in
`<invoking checkout>/kitty-ops/<id>.jsonl`.

The `doctor ops` sweep never followed. Both its halves still scan one directory:

- `list_orphan_ops(repo_root)` globs `<repo_root>/kitty-ops/*.jsonl` only
  (`src/specify_cli/doctor/ops.py`), and reads the closure spine under the same root.
- `close_stale_ops(repo_root, ...)` enumerates through that function and builds
  `ProfileInvocationExecutor(repo_root)` with no `record_root`, so even a record it
  were handed would be closed — and its spine appended — in the root checkout.

So an Op opened in a linked worktree is invisible to `doctor ops` and
`doctor ops --close-stale`, and the sweep silently under-reports on exactly the
workflow it exists for. `locate_op_record_root` in `src/specify_cli/invocation/op_custody.py`
already enumerates every checkout with `git worktree list --porcelain`, and
`profile-invocation complete` and `agent action` already use it to find a record
from any checkout; the sweep just does not use it.

Grounding on `512567eee7` (main): a linked worktree holding a started-only Op
record is reported as zero orphans by `spec-kitty doctor ops --json`, exit 0, both
from the repository root checkout and from inside the worktree.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An Op opened in a worktree is listed (Priority: P1)

A maintainer runs `spec-kitty doctor ops` from the repository root checkout after
working in a linked worktree where an Op was dispatched and never closed. The
sweep lists that Op, with a path that says which checkout holds it, and exits 1.

**Why this priority**: This is the reported defect. The listing is how an operator
learns that work is open; a listing that misses worktree Ops is wrong on the
workflow the tool is for.

**Independent Test**: Create a repository with a committed Op record, add a linked
worktree, write a started-only Op record in the worktree's `kitty-ops/`, run
`spec-kitty doctor ops --json` from the root checkout, and assert the record is
reported.

**Acceptance Scenarios**:

1. **Given** a linked worktree with an open Op record and a root checkout with none,
   **When** `doctor ops --json` runs from the root checkout, **Then** the payload
   contains one entry whose path is relative to the project root
   (`../lane/kitty-ops/<id>.jsonl`) and the command exits 1.
2. **Given** the same repository, **When** `doctor ops --json` runs from inside the
   worktree, **Then** the same record is reported (the project root is resolved the
   same way from either side).
3. **Given** open Op records in the root checkout and in two linked worktrees,
   **When** `doctor ops` runs without `--json`, **Then** all three are listed, root
   records first, and each path identifies its checkout.
4. **Given** a repository with no linked worktrees, **When** `doctor ops` runs,
   **Then** the output and exit code are byte-identical to today's.

### User Story 2 - `--close-stale` sweeps every checkout, safely (Priority: P1)

A maintainer runs `spec-kitty doctor ops --close-stale --threshold 0` after a long
parallel session with several worktrees. Every stale Op is closed, and each closure
is recorded on the closure spine of the checkout that owns the record — never in a
checkout the sweep does not own, and never by mutating a byte-frozen per-record file.

**Why this priority**: A sweep that finds records it cannot close is only half a fix;
and a sweep that writes one checkout's closures into another checkout's branch is a
new defect.

**Independent Test**: Seed a stale Op in the root checkout and another in a linked
worktree, run the sweep once, and assert both are closed, that each checkout's
`kitty-ops/op-closures.jsonl` holds exactly its own closure, and that a second run
reports no orphans.

**Acceptance Scenarios**:

1. **Given** one stale Op in the root checkout and one in a linked worktree, **When**
   `--close-stale --threshold 0` runs, **Then** both entries report
   `closed_abandoned`, the root spine carries only the root invocation id and the
   worktree spine only the worktree one.
2. **Given** a record in a worktree on a branch whose commit is refused (or whose
   spine commit is skipped), **When** the sweep runs, **Then** that entry carries the
   existing `not_committed:<refusal>` / `skipped:<reason>` value and the other
   checkouts are still swept.
3. **Given** a record already closed on a worktree's spine, **When** the sweep runs,
   **Then** it is not listed and not re-closed (idempotent, per checkout).
4. **Given** a repository that is not a git checkout, or where `git worktree list`
   fails, **When** `doctor ops` runs, **Then** it behaves exactly as today (root
   checkout only) and never raises.

### User Story 3 - Session presence stays cheap (Priority: P2)

The session-start/stop Open-Ops reminder runs on every agent session boundary and
must stay a single-directory, git-free scan. It keeps reporting the root checkout's
open Ops only.

**Why this priority**: The enumeration change must not leak into a hot path whose
documented contract is "no git calls, < 0.5 s at 1,000 files". Widening it there is a
performance and latency regression with no operator asking for it; it needs its own
decision.

**Independent Test**: Run `render_open_ops_section` on a repository with a worktree
Op and assert (a) no git subprocess is spawned and (b) the worktree Op is not
reported, so the boundary is explicit rather than accidental.

**Acceptance Scenarios**:

1. **Given** any repository, **When** `list_orphan_ops(repo_root)` is called, **Then**
   it spawns no git subprocess and scans one directory.
2. **Given** a linked worktree with an open Op, **When** the session-start section
   renders, **Then** the worktree Op is not listed, and the docstrings of
   `list_orphan_ops` and the session-presence module say so.

### Edge Cases

- **`git worktree list` unavailable or failing** (not a git checkout, git missing,
  timeout): fall back to the project root alone, exactly as today. Never raise.
- **A worktree listed by git but gone from disk** (prunable, or on an unmounted
  volume): no `kitty-ops/` to read, so it contributes nothing.
- **A checkout with no `kitty-ops/`**: contributes nothing; the enumeration does not
  create the directory.
- **The same checkout listed twice** (root checkout is also the first
  `git worktree list` entry; a worktree nested in another): de-duplicated by resolved
  path, so no record is listed or closed twice.
- **A stale path in `git worktree list --porcelain`** that is not under the project
  root: still that repository's checkout; its records are in scope, and the listing
  path is expressed relative to the project root (`../…`).
- **A record whose invocation id is invalid**: ignored exactly as today
  (`InvocationWriter.invocation_path` raises `ValueError`), never a crash.
- **A per-checkout failure** (spine unreadable, executor cannot be built): recorded
  as a per-op error entry where an op is involved, and never aborts the sweep of the
  other checkouts.
- **Windows path separators**: listing paths render with `/` regardless of platform.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Enumerate every checkout through the shared enumeration | As a maintainer, I want `doctor ops` to read Op records from every checkout of the repository so that worktree work is never invisible. | High | Open | [build] | no — the same fixture with the record only in the root checkout lists it today, so the multi-worktree case is the discriminator |
| FR-002 | Close each stale Op in the checkout that owns it | As a maintainer, I want `--close-stale` to close a worktree Op through that worktree's executor so that the closure spine lands where the record lives. | High | Open | [build] | no — asserts each spine holds exactly its own closure, which is impossible when one root executor closes both |
| FR-003 | Report a checkout-relative, root-relative path | As a maintainer, I want each listed record's path to say which checkout holds it, without changing the JSON payload shape. | Medium | Open | [build] | no — a worktree record must render as `../lane/kitty-ops/<id>.jsonl`, not raise and not be absolute |
| FR-004 | Keep the session-presence scan single-checkout and git-free | As an agent host, I want the session-start/stop reminder to stay a git-free single-directory scan so that its latency budget holds. | High | Open | [ratchet] | no — a test asserts zero git subprocesses from `list_orphan_ops` |
| FR-005 | Degrade to today's behavior without git | As an operator outside a git checkout, I want `doctor ops` to keep working on the project root so that a broken or absent git never breaks the command. | Medium | Open | [build] | no — a non-git fixture asserts the root-only result rather than an exception |
| FR-006 | One enumeration, not a second walk | As a maintainer, I want the checkout enumeration to have a single owner (`op_custody`) so that custody and the sweep cannot drift. | Medium | Open | [ratchet] | no — a test asserts the doctor module uses the shared enumeration and defines no walk of its own |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded git cost | A `doctor ops` invocation spawns at most one `git worktree list` subprocess regardless of record count (one per run, not one per record or per checkout), and the sweep spawns no git process to *find* records. | Performance | High | Open |
| NFR-002 | Failure isolation | One unreadable checkout or one failing close leaves the other checkouts' records listed and swept; the command still exits per the existing contract (`1` on errors or fresh Ops left, `0` otherwise). | Reliability | High | Open |
| NFR-003 | Deterministic order | Records are ordered by checkout — the project root first, then `git worktree list` order — and by file name within a checkout, so repeated runs and `--json` output are stable. | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | JSON shapes frozen | `doctor ops --json` stays a list of `{"path": <string>}` objects; the sweep report keeps `open_ops`/`swept`/`skipped_fresh`/`threshold_hours`/`closure_spine` and the per-entry keys it already emits. No new keys, no new value vocabulary. | Technical | High | Open |
| C-002 | Session-presence budget untouched | The session-start/stop path keeps its documented contract: no git calls, one directory scan, < 0.5 s at 1,000 Op files. | Technical | High | Open |
| C-003 | Scope stays on `doctor ops` | The mission-step custody half landed in #6664 and is not reopened; no new flag, config key, environment variable or transport is introduced. | Technical | High | Open |
| C-004 | Archive freeze respected | The sweep still closes only through `ProfileInvocationExecutor.complete_invocation` and still writes only the append-only spine; no per-record file is mutated. | Technical | High | Open |

### Key Entities

- **Checkout**: the repository root checkout or one of its linked worktrees, as `git worktree list --porcelain` reports it; the unit that owns `kitty-ops/` and its closure spine.
- **Op record**: `kitty-ops/<invocation_id>.jsonl`, byte-frozen once committed, never mutated by a sweep.
- **Closure spine**: `kitty-ops/op-closures.jsonl` inside one checkout; the only durable record of a sweep closure, committed on that checkout's branch.
- **Orphan Op**: a record with no `completed` event and no closure on *its own checkout's* spine.

## Success Criteria *(mandatory)*

- **SC-001**: On a repository with an open Op in a linked worktree, `doctor ops --json` run from the root checkout reports it and exits 1 — and reports it from inside the worktree too — [build] · no-op passable: no
- **SC-002**: `doctor ops --close-stale --threshold 0` closes stale Ops in the root checkout and in linked worktrees in one run, each closure on its own checkout's spine, with a second run reporting none — [build] · no-op passable: no
- **SC-003**: `list_orphan_ops` and the session-presence reminder spawn zero git subprocesses, and a test pins that boundary to the single root checkout — [ratchet] · no-op passable: no
- **SC-004**: A `doctor ops` run over a repository with three checkouts spawns exactly one `git worktree list` — [ratchet] · no-op passable: no
- **SC-005**: A non-git directory, a git repository with no worktrees, and a failed `git worktree list` all produce today's output and exit code — [build] · no-op passable: no

## Assumptions

- `git worktree list --porcelain` is available wherever Op custody is already in use; #6564 relies on the same call through `locate_op_record_root`.
- Paths reported relative to the project root (`../lane/kitty-ops/<id>.jsonl`) are unambiguous for an operator reading doctor output, and keep the JSON payload free of machine-local absolute paths.
- The session-presence surface is deliberately out of scope for the enumeration; widening it is a separate decision with its own latency budget.
- Checkout existence is not re-verified beyond reading `kitty-ops/`; a stale worktree entry contributes nothing and is not pruned by this command.
