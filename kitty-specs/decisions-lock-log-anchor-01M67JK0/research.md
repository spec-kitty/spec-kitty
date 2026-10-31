# Research: decisions lock log anchor (#6765)

Discovery for mission `decisions-lock-log-anchor-01M67JK0`, run before the spec.
Everything below was gathered by reading current `main` (`512567eee7`) and by running
resolution probes against real git fixtures.

## D-1 The issue still reproduces as a *keying* defect; it was not superseded

`gh pr list --search "decisions lock"` and `git log -S _decisions_lock_path` show the
lock was introduced by `00a0670baf` / `2aa19757f1` / `644ad1a30e` (#4848, PR #6762) and
has not changed since. `docs/changelog/CHANGELOG.md` carries no `#6765` entry, and no
open PR references the issue. The known-limit row is still live in
`kitty-specs/decision-log-integrity-01M5ZAW0/research.md` R-7 ("Lock is per ledger
directory, so opens from two different checkouts with the same explicit `decision_id`
are not serialized").

The sibling PR for this batch (#6841, branch `issue-6763-decisions-lock-timeout-refusal`)
changes the *timeout refusal* for a busy decisions lock. It does not touch keying, and
this mission must not touch timeout reporting (C-001).

## D-2 The lock covers a row that lives somewhere else

`open_decision` (`src/specify_cli/decisions/service.py`) resolves two paths and takes
the lock on the first:

| What | Resolver | Partition |
|---|---|---|
| ledger dir (`decisions/index.json`, `DM-<id>.md`) | `_ledger_dir` → `placement_seam(...).read_dir(DECISION_LEDGER)` | PRIMARY (re-homed from COORD in #5023) |
| event log (`status.events.jsonl`) | `_write_events_path` → `placement_seam(...).write_dir(STATUS_STATE)` | COORD for a coordination-routed Mission |

The critical section (dedup lookup → index append → artifact write → `DecisionPointOpened`
append) is guarded by `_decisions_lock(_decisions_lock_path(mission_dir))` — keyed on the
**ledger directory**, the PRIMARY leg. The row it protects is appended to the **event
log**, the COORD leg. Whenever the two legs resolve to different directories in two
checkouts that append to the same log, the two writers hold different locks.

## D-3 What each checkout actually resolves today (probed, not assumed)

Probes run through the real resolution seams against `make_owned_checkouts` fixtures and
the real `coord_topology_mission` shape:

| Fixture | `_ledger_dir` R vs P | `_write_events_path` R vs P |
|---|---|---|
| `single_branch`, owned fact on P | R: `<R>/kitty-specs/<slug>`; P: `<P>/kitty-specs/<slug>` | same split — P's own log |
| `single_branch`, no owned fact, `repo_root=P` | re-anchors to `<R>/kitty-specs/<slug>` | re-anchors to `<R>/.../status.events.jsonl` |
| `coord` / `lanes_with_coord`, no owned fact | both re-anchor to `<R>/kitty-specs/<slug>` | both resolve the coordination leg |
| `coord` + owned fact (`NEXT_OWNED_TOPOLOGIES`) | P resolves `<P>/kitty-specs/<slug>` | owned COORD write (`establish_coord_write_location`) — the shared coordination leg, or a refusal when the declared branch is absent |

So today the ledger dir and the log co-resolve *per mission identity* in every
`LIFECYCLE_OWNED_TOPOLOGIES` shape, which is why the issue records "no caller does this
today". The divergence is structural, not hypothetical: `DECISION_LEDGER` is a PRIMARY
kind and `STATUS_STATE` is a COORD kind, so any topology change, the `next
--owned-checkout` COORD shape, or the #6196 write-service handover can put two checkouts
on one log with two ledger dirs. Two opens would then take two locks and both append an
opening for one `decision_id`; the fold refuses the decision.

**Consequence for the red test** (recorded for plan/tasks): the divergence cannot be
constructed from a supported topology today, so the reproduction must pin the property
the fix is about — "writers of one log share one lock" — and drive it through the real
entry point with the divergence injected at the two path-resolution helpers. A test that
only asserts equal lock paths for equal ledger dirs would pass before the fix and prove
nothing (tactic `acceptance-criteria-non-vacuity`, "exercise the production path").

## D-4 `kernel.event_log_append` already owns the anchor→lock contract

`kernel/event_log_append.py` (#6606) defines the one existing anchor keying:

- `event_log_lock_path(anchor)` → `<git-common-dir>/spec-kitty-locks/event-logs/<32-hex>.lock`,
  the digest of the resolved, `os.path.normcase`d anchor path;
- every worktree of a repository shares the git common dir, so every writer of one log
  takes one lock;
- outside a git repo it falls back to `<anchor>.event-log.lock`;
- when git cannot be invoked it raises `EventLogLockUnavailableError` rather than locking
  somewhere no other writer locks.

This is the issue's option 1 verbatim ("Key the lock on the event log the opening goes
to (as `kernel.event_log_append` does)"). Reusing it means the fix adds no second digest
or lock-placement scheme (C-003).

## D-5 Decision: widen the lock, do not move it

Rejected alternative — make the sidecar *be* the anchor lock. It would orphan real,
documented, tested machinery: the on-disk `decisions/index.json.lock` is load-bearing for
`repair-runtime-lock` (`cli/commands/decision.py`), `next`'s owned-commit guard
(`next_cmd._commit_owned_next_mutations`), the `.gitignore` provisioning in
`_ensure_runtime_lock_ignore`, the coherence screen `is_decisions_runtime_lock` (#6628)
and the reconciler `_decisions_doctor` — all of which take that exact file to exclude a
concurrent forward write from a repair (#4848). Retiring them is a separate change with
user-facing surface (C-002).

Adopted: the write path holds **both** — the log anchor lock (new, cross-checkout) and the
existing ledger-dir sidecar (unchanged contract), in one global order
anchor → sidecar → Mission status lock (C-004). Both are acquired through the existing
`_decisions_lock` helper, so no new error type, code or envelope is introduced and #6841's
timeout shape stays the single one (NFR-003).

## D-6 Lock-order and re-entrancy notes

- The event append inside the critical section takes the Mission status lock
  (`status.locking.feature_status_lock` keyed on `mission_lock_key`), which is a different
  file (`<git-common-dir>/spec-kitty-locks/<key>.status.lock`). Taking the anchor lock
  first keeps the existing "decisions → status" order and adds no inversion.
- Nothing else in `src/` takes `event_log_lock_path(status.events.jsonl)`: `retention.py`
  takes event-log locks non-blockingly for pruning (`blocking=False`), so a held anchor
  only skips a prune attempt — it cannot deadlock.
- `event_log_lock`'s thread-local re-entrancy is *not* used: the anchor is taken via
  `machine_file_lock` through `_decisions_lock`, like the sidecar, so a timed-out wait is
  the same `DecisionError(LOCK_TIMEOUT)` shape both locks already share.

## Open questions for plan/tasks

1. Should the anchor lock also be taken by the reconciler (`doctor --repair`) and by
   `repair-runtime-lock`? They mutate the ledger, not the log, and they must stay mutually
   exclusive with a forward write through the *sidecar* — which this mission keeps. Not
   needed; recorded as an explicit non-goal rather than silently skipped.
2. Does the anchor lock need an ignore rule? No: it lives under the git common dir, outside
   every working tree. A test will pin `git status --porcelain` staying clean (NFR-004).
3. Non-git checkout: `event_log_lock_path` falls back to a sibling file next to the log.
   Nothing to add; the edge case is asserted.
