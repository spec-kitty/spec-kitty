# Contract: interim ledger lock (retires at the #6193 handover)

Every append to an event log other than `status.events.jsonl` / `canonical-events.jsonl` (which keep the status lock):

0. **Anchor.** The log itself. For a family of one-file-per-record logs (`kitty-ops/<op>.jsonl`), the family directory.
1. **Lock file.** `L = <git-common-dir>/spec-kitty-locks/event-logs/<sha256(normcase(resolve(anchor)))[:32]>.lock`.
   - Not a git repository: `L = <anchor>.event-log.lock`.
   - Git cannot be invoked: refuse (`EVENT_LOG_LOCK_UNAVAILABLE`); write nothing.
2. **Lock.** An exclusive `flock(2)` (POSIX) or `msvcrt.locking` (Windows) on `L`, with a bounded wait of 10 s (`EVENT_LOG_LOCK_TIMEOUT`). The lock file holds only a lock record and is never unlinked.
3. **Torn tail.** Under the lock, refuse if the log's last byte is not LF (`EVENT_LOG_TORN_TAIL`).
4. **Write.** One `write(2)` on an `O_APPEND` descriptor of the whole unit, then `fsync`.
5. **Release.**

A Java writer that shares a file with the CLI must take the same `L` with `flock(2)` semantics (ADR 2026-10-22-1 D-4).
