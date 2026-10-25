# Contract: interim ledger lock (retires at the #6193 handover)

Every append to an event log other than `status.events.jsonl` / `canonical-events.jsonl` (which keep the status lock):

1. **Lock file.** `L = <git-common-dir>/spec-kitty-locks/event-ledgers/<sha256(normcase(abspath(resolve(log))))[:32]>.lock`. Outside git: `<log>.lock`.
2. **Lock.** Take an exclusive `flock(2)` (POSIX) or `msvcrt.locking` (Windows) on `L`, with a bounded wait of 10 s. The lock file holds only a lock record; it is never unlinked.
3. **Torn tail.** Under the lock, refuse if the log's last byte is not LF.
4. **Write.** One `write(2)` on an `O_APPEND` descriptor of the whole unit, then `fsync`.
5. **Release.**

A Java writer that shares a file with the CLI must take the same `L` with `flock(2)` semantics (ADR 2026-10-22-1 D-4).
