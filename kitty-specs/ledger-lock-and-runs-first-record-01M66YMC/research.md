# Research: which existing lock helper the ledger seam should use

Phase 0 survey for `ledger-lock-and-runs-first-record-01M66YMC`. The question this mission had to
settle before planning: *the ledger append needs a lock — which existing helper, given that #6727
is concurrently consolidating lock-path helpers?*

## 1. What the ADR already decided

ADR `2026-10-17-1` §1, "Atomic write, single-writer" says:

> The subsystem is single-writer: `upgrade` runs in one process, worktrees sequentially … If
> concurrent cross-process upgrade ever becomes real, wrap the append in `kernel.locks`
> (`src/kernel/locks.py:151`); this is the named extension point, deliberately **not** built now.

So the mechanism is pre-decided: `kernel.locks`. The open question is only the *path* the lock is
taken on. #6613 is the issue that makes "if it ever becomes real" real.

## 2. The candidate helpers, surveyed

| Candidate | Where | Verdict |
| --- | --- | --- |
| `kernel.locks.machine_file_lock(lock_path, ...)` | `src/kernel/locks.py:641` | **Chosen.** The canonical primitive every lock family bottoms out in (G6 test-double seam by design). Takes any path, so the ledger owns its own sidecar path and adds no lock-path rule. |
| `kernel.event_log_append.event_log_lock_path(anchor)` / `event_log_lock(anchor)` | `src/kernel/event_log_append.py:154/174` | Rejected: an *event-log* lock family. Its name, subdirectory (`spec-kitty-locks/event-logs/`), `.event-log.lock` non-git fallback and git-common-dir keying all say "event log". The migration ledger is a state ledger (the developer reference says so, and forbids writing bare "the ledger"), and it must work with no git repository at all. |
| `charter.activation.synthesizer.synthesis_lock.synthesis_lock(repo_root)` | `src/charter/.../synthesis_lock.py:100` | Rejected: a charter-synthesis lock, deliberately a copy of the event-log shape (its own docstring says so). Same reasons, plus a wrong semantic owner. |
| `specify_cli.status.locking.project_event_log_lock(repo_root)` | `src/specify_cli/status/locking.py:333` | Rejected: keyed `<git-common-dir>/spec-kitty-locks/__project__.status.lock` and documented as serializing writers of `.kittify/canonical-events.jsonl`. Reusing it would make an upgrade and a status write exclude each other for no shared data, and it needs a git common dir. |
| `specify_cli.core.checkout_file_lock.acquire_or_raise(lock, ...)` | `src/specify_cli/core/checkout_file_lock.py:37` | Not applicable: it is an enter-and-translate helper for a lock the caller already built; it owns no path. The ledger does not need a caller-specific typed timeout translation — see §3. |
| `runtime.next.run_index.index_lock` / `run_lock.run_cursor_lock` | `src/runtime/next/` | Pattern precedent, not reusable code: each is a *payload-specific* dedicated sidecar (`<payload>.lock`) built with `machine_file_lock`. The ledger copies the *pattern* (sidecar beside payload), not the code. |

## 3. Why a sidecar beside the ledger, not a repository-scoped key

The issue says "repository-scoped lock". The precise scope is narrower and provably correct:

- The ledger's two partitions are files **in a checkout** (`.kittify/migration-ledger.jsonl`,
  `.kittify/migrations/clone-local.jsonl`). Each git worktree carries its own copy of the tracked
  ledger, so the object that can lose a record is *the file*, and two writers to the same file are
  two writers in the same checkout.
- Keying on the git common dir would (a) over-serialize unrelated checkouts, and (b) require a git
  invocation for a code path that must also run outside a repository (`init` outside git leaves
  the clone-local step pending on purpose, #6431; the ledger is written without git in that flow).
- A per-file sidecar is also exactly what `runtime/next/run_index.py` and `run_lock.py` do, so the
  shape is already the house style.

`machine_file_lock` writes a `LockRecord` payload into the file it locks and truncates it on
release (kernel G3), which is why the lock can never be the ledger file itself — the payload
invariant the run-index module names "G1". The sidecar suffix is therefore mandatory, not cosmetic.

## 4. Not inventing #6727's helper

#6727 (claimed, in flight) proposes `kernel.locks.anchored_lock_path(anchor_dir, subdir, *,
non_git_fallback)` to collapse the digest/common-dir rule that `event_log_lock_path`,
`synthesis_lock_path` and the status lock each re-implement. The ledger needs **none** of that
rule: it derives `<ledger>.lock` from a path it already holds. So this mission adds no fourth copy
and will not conflict with #6727; if #6727 lands first, the ledger's two-line path helper can later
be re-pointed at it without a behaviour change. That is recorded in the ADR amendment and in the
PR's `## Deferred`.

## 5. Re-entrancy

The status lock and the charter synthesis lock both take `reentrant=True`, because their callers
wrap larger transactions around helpers that take the same lock. The ledger's append is a leaf
today, but `_record_ledger_result` (read-then-append) is the natural future place to widen the
protected section, and a second nested `append` would then self-deadlock. `reentrant=True` costs
nothing (the primitive already keeps per-thread holdings) and removes a trap.

## 6. The `runs_first` reselection, surveyed

`BaseMigration.reselect_when_recorded` (base.py) returns `runs_first and structural_detect(...)`.
`runs_first` is a `ClassVar[bool]` guarded to at most one registered migration
(`registry.py:61-67`). ADR §1 says selection "collapses to 'is this id in the applicable ledger for
its partition?'", and its own list of touchpoints calls `reselect_when_recorded` "collapses to a
ledger lookup" — which the code does not do. The ADR's §3 prose does describe `clone_local_effect`
losing its reselection role, so the surviving structural reselection is the one unrecorded
behaviour. It stays (C-004); the amendment records it.
